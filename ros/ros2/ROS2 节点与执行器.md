# ROS2 节点、执行器与回调组

> Node 是 ROS2 的基本构建单元，Executor 决定回调如何被调度。理解 Executor + CallbackGroup 是写出**正确多线程节点**的关键，也是面试高频考点。

---

## 一、Node 的本质

`rclcpp::Node` / `rclpy.node.Node` 在底层对应一个 **DDS DomainParticipant**（由 rcl context 共享，可多 Node 复用一个 Participant），并管理：

- **Publishers / Subscriptions**
- **Service Servers / Clients**
- **Action Servers / Clients**
- **Timers**（WallTimer）
- **Parameters**（含 declare/get/set/事件回调）
- **Logger**（节点级 logger）
- **Clock**（系统时间或 `/clock` 话题）

### 创建方式（C++）

```cpp
class MyNode : public rclcpp::Node {
public:
    MyNode(const rclcpp::NodeOptions& opts)
        : rclcpp::Node("my_node", opts) {
        // declare params, create pubs/subs/timers...
    }
};
```

### NodeOptions 关键字段

| 字段 | 作用 |
|------|------|
| `use_intra_process_comms(true)` | 启用进程内零拷贝（同进程多 Node 共享智能指针） |
| `automatically_declare_parameters_from_overrides(true)` | 自动声明 launch 传入的参数 |
| `parameter_overrides({...})` | 注入参数 |
| `arguments({...})` | 命令行风格参数（`--ros-args -r ns:=...`） |
| `use_global_arguments(false)` | 不继承全局命令行参数 |

---

## 二、Spin 与 Executor 概览

“Spin” 即把节点交给 Executor，让其**轮询底层 wait_set，触发就绪的回调**。

```cpp
auto node = std::make_shared<MyNode>(opts);
rclcpp::spin(node);                    // 阻塞，使用默认 SingleThreadedExecutor
// 或：
rclcpp::executors::MultiThreadedExecutor exec;
exec.add_node(node);
exec.spin();
```

### Executor 的核心职责

1. **管理 wait_set**：把所有 Subscription/Timer/Service/Client/GuardCondition 注册进 wait_set。
2. **等待事件**：调 `rcl_wait`（底层 epoll/kqueue/IOCP/DDS WaitSet）阻塞至有就绪实体。
3. **取出可执行项**：按优先级（Timer > Subscription > Service > Client > Waitable）轮询。
4. **执行回调**：在自身线程或线程池中运行。

---

## 三、Executor 类型对比

| Executor | 线程数 | 并发 | 典型场景 |
|----------|--------|------|----------|
| `SingleThreadedExecutor` | 1 | ❌（顺序） | 简单节点；默认 |
| `MultiThreadedExecutor` | N（默认 = 硬件并发数） | ✅（取决于 CallbackGroup） | I/O 密集 / 多话题节点 |
| `StaticSingleThreadedExecutor` | 1 | ❌ | 实体不变时性能更好（少 wait_set 重建） |
| `EventsExecutor`（Iron+） | 可配置 | ✅ | 回调延迟更可控；Tier-1 in Jazzy |

> 经验：**默认 SingleThreaded** 即可应对 90% 业务；当存在**长耗时回调**或**Service 内部又调 Service** 时改用 MultiThreaded + ReentrantGroup。

---

## 四、Callback Group：并发控制的关键

每个回调（Sub/Timer/Service/Client）必须归属一个 **CallbackGroup**。Group 决定了 **同组回调能否并发执行**。

### 两种类型

| 类型 | 同组并发 | 跨组并发 | 默认所属 |
|------|----------|----------|----------|
| **MutuallyExclusive** | ❌ 互斥（同时只能一个跑） | ✅ | 节点的默认 group |
| **Reentrant** | ✅ 可多线程并行 | ✅ | 需显式创建 |

### 用法（C++）

```cpp
auto cb_group_sensors = create_callback_group(
    rclcpp::CallbackGroupType::Reentrant);

auto cb_group_critical = create_callback_group(
    rclcpp::CallbackGroupType::MutuallyExclusive);

rclcpp::SubscriptionOptions sub_opts;
sub_opts.callback_group = cb_group_sensors;

sub_ = create_subscription<Image>(
    "image", 10, &MyNode::on_image, sub_opts);
```

### 决策矩阵

| 场景 | 推荐 |
|------|------|
| 顺序处理传感器，担心数据竞争 | **MutuallyExclusive**（默认） |
| 多个独立子系统，互相无依赖 | 各自一个 **MutuallyExclusive** group + MultiThreadedExecutor |
| 单回调需要并发处理大量请求（如 Service Server） | **Reentrant** |
| **Service A 内部调用 Service B 并 spin_until_future_complete** | A 与 B 必须在**不同 group**！否则死锁 |

> ⚠️ **死锁陷阱**：在默认（MutuallyExclusive）group 中，回调里调用 `spin_until_future_complete` 会永远等待——因为 wait_set 无法被同一个互斥 group 重入。解决方案：
> 1. 把 Client 放到独立的 ReentrantGroup；
> 2. 或使用 `MultiThreadedExecutor`；
> 3. 或改用异步回调（推荐：`async_send_request` + 回调 lambda，不阻塞）。

---

## 五、Spin 的几种用法

```cpp
rclcpp::spin(node);                          // 阻塞至 shutdown
rclcpp::spin_some(node);                     // 处理当前所有就绪回调，不等待
rclcpp::spin_until_future_complete(node, fut); // 等待 future（注意死锁）
rclcpp::spin_all(node, std::chrono::milliseconds(10)); // 限时
```

Python 同名 API：`rclpy.spin / spin_once / spin_until_future_complete`。

---

## 六、Timer

```cpp
auto timer = create_wall_timer(
    std::chrono::milliseconds(20),
    [this]{ /* callback */ },
    cb_group_);  // 可选 group
```

- 基于 **steady clock**（不受 `/clock` 影响），适合控制周期；
- 想跟随仿真时间，使用 `create_timer(get_clock(), ...)` 并启用 `use_sim_time` 参数；
- Timer 回调超时不会抢占——若一次回调耗时 > 周期，下一次会**直接接续**或被丢弃（取决于实现），需自行监控。

---

## 七、跨节点共享 Executor

多个 Node 可共享一个 Executor（典型用于 Composition）：

```cpp
rclcpp::executors::MultiThreadedExecutor exec;
exec.add_node(perception);
exec.add_node(planning);
exec.add_node(control);
exec.spin();
```

这样三个 Node 在**同一进程**内被同一 Executor 调度，可启用 **Intra-Process Communication** 实现进程内零拷贝。

---

## 八、Python（rclpy）差异要点

- rclpy 使用 **Python 线程**调度回调，受 GIL 限制；CPU 密集回调建议用 C++。
- `MultiThreadedExecutor(num_threads=N)` 同样支持。
- CallbackGroup：`MutuallyExclusiveCallbackGroup` / `ReentrantCallbackGroup`。
- 同样存在死锁陷阱，处理方式一致。

```python
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

cb_group = ReentrantCallbackGroup()
self.create_subscription(Image, "image", cb, 10, callback_group=cb_group)
```

---

## 九、面试高频问答

**Q1：ROS2 默认是单线程还是多线程？**
默认 `SingleThreadedExecutor`，所有回调在同一个 spin 线程中**顺序**执行。

**Q2：Reentrant 和 MutuallyExclusive 如何选？**
互斥用于保护共享状态、避免锁；Reentrant 用于无状态/已加锁的高吞吐回调，或避免 Service 嵌套死锁。

**Q3：为什么我的 Service 回调里调用另一个 Service 卡住？**
默认 group 是 MutuallyExclusive，wait_set 不能重入。把 Client 放到独立 ReentrantGroup，或使用 MultiThreadedExecutor，或改异步回调。

**Q4：spin 与 spin_some 区别？**
`spin` 阻塞循环；`spin_some` 处理当前已就绪的回调一次然后返回，常用于自定义主循环。

**Q5：进程内多 Node 怎么避免拷贝？**
共享同一个 Executor + `use_intra_process_comms(true)` + Publisher/Subscription QoS 一致 + 用 `unique_ptr` 发布消息。

**Q6：Timer 漂移怎么处理？**
`create_wall_timer` 使用 steady clock，但回调阻塞会影响周期。必要时改为**外部定时唤醒 + 取最新数据**模式（如硬件中断触发）。

---

## 十、底层：WaitSet、GuardCondition、Waitable

### 10.1 WaitSet 工作原理

Executor 的心跳是 `rcl_wait`，其输入是一个 `rcl_wait_set_t` 结构，包含：

```
WaitSet {
  subscriptions[]
  guard_conditions[]
  timers[]
  clients[]
  services[]
  events[]
  waitables[]   // 如 IPC、Action、Lifecycle
}
```

rmw 层实现会把这些句柄转换为 DDS WaitSet / epoll / IOCP 属性，阻塞至任一就绪。返回后 Executor 遍历该数组以 0/non-zero 区分是否就绪。

### 10.2 GuardCondition

一个可被外部代码主动 trigger 的“事件源”，用于：
- 唤醒 `rcl_wait` （如从另一个线程插入任务）；
- shutdown / context invalidation。

```cpp
auto gc = std::make_shared<rclcpp::GuardCondition>();
// 加入 wait。例如自定义 Waitable。
std::thread([gc]{ /* 外部事件 */ gc->trigger(); }).detach();
```

### 10.3 自定义 Waitable

用于接入非 DDS 事件源（如网络 socket、硬件中断 fd）到 ROS2 wait：

```cpp
class FdWaitable : public rclcpp::Waitable {
    size_t get_number_of_ready_subscriptions() override { return 0; }
    size_t get_number_of_ready_guard_conditions() override { return 0; }
    void add_to_wait_set(rcl_wait_set_t* ws) override { /* rcl_wait_set_add_... */ }
    bool is_ready(rcl_wait_set_t* ws) override { /* check fd */ }
    std::shared_ptr<void> take_data() override { /* read fd */ }
    void execute(std::shared_ptr<void>& data) override { /* user cb */ }
};
node_->get_node_waitables_interface()->add_waitable(my_waitable, group);
```

---

## 十一、Executor 深入对比

### 11.1 SingleThreadedExecutor

```
loop {
  rcl_wait(wait_set, timeout)
  collect_ready()
  for each ready in priority order:
    execute_in_current_thread()
}
```
- 严格顺序，无锁 → 默认选择。
- 问题：任一长耗时回调会阻塞其他。

### 11.2 MultiThreadedExecutor

```
thread_pool[N] all run:
  loop {
    take_next_executable_with_lock()    // 互斥取
    if available: execute()
    else: wait_for_work()
  }
```
- 同一 MutuallyExclusive group 内仅一个线程可出队；跨 group 并行。
- 驾驭难点：锁争用、调度开销、快回调饰会被慢回调“堡垄”。

### 11.3 StaticSingleThreadedExecutor

- 实体添加后**不重建 wait_set**，每轮省 ~20µs；
- 限制：运行期增删 Pub/Sub 会被忽略或需要 `cancel/spin` 重启；
- 推荐给 **实时控制循环** 使用。

### 11.4 EventsExecutor（Iron 引入，Jazzy 增强）

- 不使用 wait+poll，而是让 RMW **主动推送事件到内部队列**；
- 避免“唤醒后遭受”（spurious wake）与诸如 timer drift；
- 启用：
  ```cpp
  rclcpp::experimental::executors::EventsExecutor exec;
  exec.add_node(node);
  exec.spin();
  ```
- 适合 **低延迟 + 事件驱动** 场景，使用前需确认 RMW 支持（fastrtps/cyclone 均已支持）。

### 11.5 选型决策表

| 场景 | 推荐 |
|------|------|
| 一般业务 | SingleThreaded |
| 多独立回调 + 不互锁 | MultiThreaded + ReentrantGroup |
| 1kHz 控制循环，实体固定 | StaticSingleThreaded |
| 低拖延 / 事件驱动 | EventsExecutor |
| Service嵌套调用 | MultiThreaded + Reentrant Client group |

---

## 十二、全局上下文与 Domain

- `rclcpp::Context`：进程级（一个进程可多 Context），`init/shutdown` 实际作用于 Context；
- 默认多 Node 共享同一 Context，并且多 Node 共享 **同一个 DDS DomainParticipant**（Iron+ 默认）；这减少了内存/发现开销，但会导致同进程跨 Node 的调试信息互相交叉；
- 如需隔离：为某些 Node 单独创建 Context + DomainParticipant，或者设 `node_options.context(ctx)`。

---

## 十三、压力与背压（Backpressure）

在 RELIABLE QoS + KEEP_ALL 下，慢订阅者会导致 Pub 发送下沉阐止。防护手段：

1. **限制压力传导**：订阅侧用 KEEP_LAST(N)，N 不过大；
2. **超时丢弃**：`Lifespan` QoS；
3. **压力隔离**：多订阅者场景下，为慢订阅者拆分独立 topic + transient_local；
4. **监控**：`PublisherEvents::offered_deadline_missed` 、`SubscriptionEvents::message_lost`。
