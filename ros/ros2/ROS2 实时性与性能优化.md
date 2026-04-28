# ROS2 实时性与性能优化

> 自动驾驶/机器人量产系统对**端到端延迟**与**抖动（jitter）**有硬性要求。本篇汇总 ROS2 实时化与性能优化的工程手段。

---

## 一、性能优化层级总览

```
应用层
 ├─ 算法复杂度、数据结构
 ├─ 节点拆分粒度
 ├─ Executor 与 CallbackGroup 设计
 └─ 消息大小、发送频率
进程层
 ├─ Composition + Intra-Process Communication（零拷贝）
 ├─ Loaned Messages（共享内存零拷贝）
 ├─ Lifecycle Node（按需启用）
 └─ 内存预分配（避免运行期 malloc）
中间件层
 ├─ RMW 选择（fastrtps / cyclonedds / zenoh / iceoryx）
 ├─ DDS QoS 调优
 ├─ SHM 传输 + UDP 缓冲区放大
 └─ Discovery Server / 关闭 multicast
OS / 内核层
 ├─ PREEMPT_RT 实时内核
 ├─ CPU 亲和性 + isolcpus
 ├─ SCHED_FIFO / SCHED_RR 优先级
 ├─ 锁内存 mlockall
 └─ 关闭 CPU 频率调节、SMT
```

---

## 二、进程内零拷贝（IPC）

详见 `ROS2 生命周期与组件化.md`，要点回顾：

```cpp
rclcpp::NodeOptions opts;
opts.use_intra_process_comms(true);
auto node = std::make_shared<MyNode>(opts);

// 必须用 unique_ptr + std::move 才能真正零拷贝（单订阅者）
auto msg = std::make_unique<sensor_msgs::msg::PointCloud2>();
fill(*msg);
pub_->publish(std::move(msg));
```

约束：
- 同进程同 Executor；
- QoS：`KEEP_LAST + RELIABLE/BEST_EFFORT + VOLATILE`（**不支持** TRANSIENT_LOCAL）；
- 消息为可移动 C++ 类型；
- 多订阅者退化为共享 `const&`，仍零拷贝读。

---

## 三、跨进程零拷贝：Loaned Messages + SHM

### 3.1 原理

```
Publisher                Shared Memory               Subscriber
   ┌──────────┐  borrow   ┌──────────────┐  return  ┌──────────┐
   │  Node A  │ ────────►│ pool slot #N │ ◄───────│  Node B  │
   └──────────┘  publish  └──────────────┘  take    └──────────┘
                ↑ DDS 仅传送 (slot_id, len)，不拷贝数据
```

### 3.2 代码

```cpp
// 发布端
if (pub_->can_loan_messages()) {
    auto loaned = pub_->borrow_loaned_message();
    auto& msg = loaned.get();
    fill(msg);
    pub_->publish(std::move(loaned));
} else {
    auto msg = std::make_unique<MsgT>();
    fill(*msg);
    pub_->publish(std::move(msg));
}

// 订阅端：消息直接来自 SHM，无拷贝
auto cb = [](const MsgT::ConstSharedPtr msg){ /* read msg */ };
```

### 3.3 启用条件

| RMW | 支持 |
|-----|------|
| `rmw_fastrtps_cpp` | ✅ 内置 SHM 传输 |
| `rmw_cyclonedds_cpp + iceoryx` | ✅ 需安装 iceoryx，启动 RouDi |
| `rmw_connextdds` | ✅（商用） |

iceoryx 启动：
```bash
iox-roudi &
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI='<CycloneDDS><Domain><SharedMemory><Enable>true</Enable></SharedMemory></Domain></CycloneDDS>'
```

> 限制：消息必须为**固定大小**（POD 或带上界的 sequence）。变长消息（如 PointCloud2 不带 capacity）需走非零拷贝路径。

---

## 四、Executor 选型

| 场景 | 推荐 |
|------|------|
| 控制频率 < 100Hz，单回调 | SingleThreadedExecutor |
| 多回调互不依赖 | MultiThreadedExecutor + 多 ReentrantGroup |
| 实时控制（jitter < 1ms） | **StaticSingleThreadedExecutor**（Iron+ 的 `EventsExecutor` 更佳） |

实时友好建议：
- 实体（Pub/Sub/Timer）启动后**不再增删**，避免 wait_set 重建；
- 用 **`SubscriptionOptions::ignore_local_publications`** 避免回环；
- 用 **`MessagePoolMemoryStrategy`** 预分配消息池：

```cpp
using AllocStrategy = rclcpp::strategies::message_pool_memory_strategy::
    MessagePoolMemoryStrategy<MsgT, 16>;
auto strategy = std::make_shared<AllocStrategy>();
rclcpp::SubscriptionOptions opts;
opts.message_memory_strategy = strategy;
sub_ = create_subscription<MsgT>("topic", qos, cb, opts);
```

---

## 五、内存：避免运行期分配

```cpp
#include <malloc.h>
#include <sys/mman.h>

// 1) 关闭 mmap 阈值，所有分配走 sbrk
mallopt(M_TRIM_THRESHOLD, -1);
mallopt(M_MMAP_MAX, 0);

// 2) 锁定虚存，避免缺页中断
mlockall(MCL_CURRENT | MCL_FUTURE);

// 3) 预触摸栈空间
char stack[8 * 1024 * 1024];
memset(stack, 0, sizeof(stack));
```

ROS2 提供 **TLSF allocator**（`tlsf_allocator`）用于 Publisher/Subscription，分配确定时间复杂度：
```cpp
using Alloc = tlsf_heap_allocator<void>;
auto alloc = std::make_shared<Alloc>();
rclcpp::PublisherOptionsWithAllocator<Alloc> pub_opts;
pub_opts.allocator = alloc;
pub_ = create_publisher<MsgT>("t", qos, pub_opts);
```

---

## 六、PREEMPT_RT 与调度

### 6.1 内核

```bash
uname -a   # 含 PREEMPT_RT 即为 RT 内核
sudo apt install linux-image-rt-amd64    # Debian 系
```

### 6.2 提升进程优先级

```cpp
struct sched_param sp{};
sp.sched_priority = 80;       // 1–99，越高越紧急
sched_setscheduler(0, SCHED_FIFO, &sp);
```

或通过 `chrt`：
```bash
chrt -f 80 ros2 run my_pkg control_loop
```

### 6.3 CPU 亲和性

```bash
# 内核启动参数：isolate cpu 2,3
isolcpus=2,3 nohz_full=2,3 rcu_nocbs=2,3

taskset -c 2 ros2 run my_pkg control_loop
```

或运行时：
```cpp
cpu_set_t set; CPU_ZERO(&set); CPU_SET(2, &set);
pthread_setaffinity_np(pthread_self(), sizeof(set), &set);
```

### 6.4 中断与 IRQ

将网卡/CAN 控制器的中断绑定到非实时核，避免抢占控制线程。

---

## 七、DDS / 网络调优

### 7.1 OS 层

```bash
sudo sysctl -w net.core.rmem_max=2147483647
sudo sysctl -w net.core.rmem_default=2147483647
sudo sysctl -w net.core.wmem_max=2147483647
sudo sysctl -w net.ipv4.ipfrag_high_thresh=134217728
```

### 7.2 大消息（图像 / 点云）

- 启用 SHM：本机优先（Fast DDS / Cyclone DDS+iceoryx）；
- 拆分：Camera 用 `image_transport` 压缩传输（`compressed`、`theora`）；
- 用 BEST_EFFORT + KEEP_LAST(1) 避免历史堆积；
- 控制 fragment 大小，避免单个 RTPS 包超 MTU。

### 7.3 多机网络

- 关闭多播 + 配置 Peer List 减少广播；
- Fast DDS Discovery Server 适合大规模车队；
- 跨子网用 zenoh router 或 DDS routing service。

---

## 八、性能测量

| 工具 | 用途 |
|------|------|
| `ros2 topic hz / bw / delay` | 频率、带宽、端到端延迟 |
| `ros2 run performance_test perf_test` | 官方基准（apex.ai 维护） |
| `tracetools` + LTTng | rclcpp 内部事件追踪 |
| `ros2 trace` (Iron+) | 一键启动 LTTng 会话 |
| `cyclic_test` | 内核 RT 抖动测试 |
| `perf` / `flamegraph` | CPU 热点剖析 |
| `valgrind --tool=massif` | 内存泄漏与峰值 |
| `htop` / `pidstat -t` | 线程级 CPU |

示例：测端到端延迟
```bash
# 节点 A 发 std_msgs/Header（带 stamp）
# 节点 B 订阅后计算 (now() - stamp)
ros2 topic delay /chatter
```

---

## 九、典型实战 checklist（自动驾驶感知/规划）

1. ✅ 关键链路用 **Composition + IPC**（`component_container_mt`）。
2. ✅ Sensor → Perception 用 **SensorDataQoS + Loaned Messages**。
3. ✅ Planning → Control 用 **RELIABLE QoS + 高优先级 SCHED_FIFO 线程**。
4. ✅ TF / 静态变换 用 **TRANSIENT_LOCAL + TF Static**。
5. ✅ Lifecycle 启停顺序：`sensor_drivers → tf → perception → planner → controller`。
6. ✅ 监控：发布 `diagnostic_updater` + `topic_statistics`（`stats_topic` QoS 选项）。
7. ✅ 关键节点 `mlockall` + 预热分配 + 实时优先级。
8. ✅ CI 做 `performance_test` 回归，端到端延迟基准必须 < 阈值。

---

## 十、面试速记

- 性能金字塔：**算法 → IPC/SHM 零拷贝 → DDS QoS → OS/内核**
- 进程内零拷贝：`use_intra_process_comms` + `unique_ptr + move`
- 跨进程零拷贝：`borrow_loaned_message` + SHM 传输
- 实时三件套：**PREEMPT_RT + SCHED_FIFO + mlockall**
- Composition 是 ROS2 性能差异化的核心特性

---

## 十一、典型延迟量级参考（同主机）

> 该数据为一般参考，实际与硬件/RMW/QoS/消息大小有关。

| 场景 | 中位数延迟 | P99 延迟 |
|------|------|------|
| 同进程 IPC + `unique_ptr` move（1KB） | < 5 µs | < 20 µs |
| 同主机 SHM（iceoryx，1MB） | ~30 µs | ~80 µs |
| 同主机 UDP loopback（1KB，默认 QoS） | 80–150 µs | 300–500 µs |
| 同主机 UDP loopback（1MB，默认 QoS） | 1.5–3 ms | > 10 ms |
| 跨主机 1GbE（1KB） | 200–400 µs | 1–3 ms |
| 跨主机 1GbE（1MB, RELIABLE） | 10–20 ms | > 50 ms |

启示：大消息 + RELIABLE 跨机会出现明显长尾，必要时拆货、压缩、走专线。

---

## 十二、选点优化 cookbook

### 12.1 大图像 / 点云跨进程

1. 优先 `image_transport` / `point_cloud_transport` 的压缩插件（`compressed`、`zstd`）；
2. 启用 SHM（fastrtps SHM 或 cyclonedds + iceoryx）；
3. QoS：BEST_EFFORT + KEEP_LAST(1)，避免堆积；
4. 拆分裁剪：ROI、低分辨率预览另发走低 QoS。

### 12.2 高频传感货（IMU 1kHz）

1. SensorDataQoS + 小消息丢包可接受；
2. 发布侧锁定 CPU + 高优先级；
3. 订阅侧用 **MessagePoolMemoryStrategy** 预分配。

### 12.3 控制循环（1kHz）

1. **StaticSingleThreadedExecutor** 或 EventsExecutor；
2. 锁内存 `mlockall(MCL_CURRENT|MCL_FUTURE)`；
3. SCHED_FIFO 80，绑 isolcpu；
4. 驱动优先：SHM > UDP > TCP；
5. 避免调用 ROS 日志（或开启 `rcutils` 的性能模式）。

### 12.4 多节点部署

1. 在一个 `component_container_mt` 里加载同一数据流上的多个 Component；
2. 跨容器才走 SHM/IPC；
3. 与硬件驱动同进程，减少传感驱动→感知 hops。

---

## 十三、OS 调优详细清单

```bash
# 网络缓冲区
sysctl -w net.core.rmem_max=2147483647
sysctl -w net.core.wmem_max=2147483647
sysctl -w net.ipv4.udp_mem="1048576 2097152 16777216"

# 关 NIC 合并中断
ethtool -C eth0 rx-usecs 0 tx-usecs 0

# 关 IRQ balance，手动绑定中断到非 RT 核
systemctl stop irqbalance
echo 1 > /proc/irq/<N>/smp_affinity

# CPU 频率锁高 / 关 P-state idle
cpupower frequency-set -g performance
echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo

# 关 SMT (Hyper-Threading)
echo off > /sys/devices/system/cpu/smt/control

# THP 定期合并会引入抑颗
echo never > /sys/kernel/mm/transparent_hugepage/enabled

# 实时内核参数
isolcpus=2,3 nohz_full=2,3 rcu_nocbs=2,3 processor.max_cstate=1
```

---

## 十四、常见报表/实际指标

- **cyclictest -m -p 80 -i 1000 -t 4 -h 1000**：内核 RT 抑抖 — 线上不应 > 50µs；
- **`ros2 topic delay`**：应稳定 < 周期的 30%；
- **`pidstat -uw -p $(pgrep node) 1`**：实时线程 CPU，nvcswch 不应骤增；
- **performance_test 报表**：IPC zero-copy 0丢失，P99 < 100µs。

---

## 十五、反模式（Anti-patterns）

| 反模式 | 后果 |
|--------|------|
| 控制循环里调 ROS 服务 同步等待 | 死锁 / 拖延 |
| 发布 RELIABLE + KEEP_ALL 大消息 | 内存暴涨 |
| Sub 回调里需要多线程却用默认 group | 隐式串行 |
| 在高频回调里 `RCLCPP_INFO`、`std::cout` | I/O 撞抢 |
| Pub/Sub QoS 不一致依赖 RMW 默认 | 连接不上 / 丢包 |
| 多 Container 外加 IPC 不启 | 未充分发挥零拷贝 |
| `ros2 launch` 中重复 include 同一 launch | 节点重复启动、双发 |
| Lifecycle Node 不 configure 直接 use | Pub 静默 / 服务不响应 |
