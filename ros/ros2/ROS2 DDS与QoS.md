# ROS2 DDS、RMW 与 QoS

> ROS2 不再自研传输协议，而是通过 **RMW（ROS Middleware）** 抽象层对接多种 DDS 实现。理解 DDS 与 QoS 是排查 ROS2 通信问题的核心能力。

---

## 一、整体关系

```
┌──────── 用户代码 ────────┐
│  rclcpp / rclpy          │
└──────────┬───────────────┘
           │ rcl C API
┌──────────▼──────────────────────────────────────────────┐
│           rmw（Middleware Abstraction）                  │
│   rmw_create_publisher / rmw_take / rmw_publish ...     │
└──────────┬──────────────────────────────────────────────┘
           │ 不同实现
   ┌───────┼─────────────┬────────────────┬───────────────┐
   ▼       ▼             ▼                ▼               ▼
fastrtps  cyclonedds   connextdds      gurumdds       zenoh
  (default,  (Apache 2,    (商用)          (商用)        (Jazzy
  eProsima)  Eclipse)                                  Tier-1)
```

---

## 二、RMW 切换

```bash
# 编译期可同时安装多个 RMW
sudo apt install ros-humble-rmw-cyclonedds-cpp \
                 ros-humble-rmw-fastrtps-cpp

# 运行期切换
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ros2 doctor                # 查询当前 RMW
ros2 run demo_nodes_cpp talker
```

| RMW | 默认版本 | 特点 |
|-----|----------|------|
| `rmw_fastrtps_cpp` | Humble/Jazzy 默认 | 功能全、Shared Memory 支持、社区活跃 |
| `rmw_cyclonedds_cpp` | Foxy 期默认 | 启动快、内存小、低延迟，搭配 iceoryx 实现真零拷贝 |
| `rmw_connextdds` | 商用 | 工业 / 自动驾驶量产，工具链强（Admin Console） |
| `rmw_zenoh_cpp` | Jazzy Tier-1 | 不基于 DDS，**去除发现风暴**，跨网友好 |

> 同一网络内**不同 RMW 默认无法互通**（DDS 实现间的 Discovery 兼容性差）。统一全局 RMW 是最佳实践。

---

## 三、DDS 在 ROS2 中的映射

| ROS2 概念 | DDS 概念 |
|-----------|----------|
| Node | DomainParticipant（多 Node 默认共享 1 个 Participant，详见 Iron+ 上下文） |
| Topic | Topic |
| Publisher | DataWriter |
| Subscription | DataReader |
| Domain ID | DDS Domain ID |
| 消息类型 | IDL Type（XTypes） |

**Topic 命名映射**：ROS2 话题 `/chatter` 在 DDS 层名为 `rt/chatter`（`rt` = ROS topic）；Service 为 `rq/...Request`、`rr/...Reply`；Action 类似。这就是为什么 ROS2 可以与原生 DDS 应用互操作（修改名字即可）。

---

## 四、QoS（Quality of Service）

ROS2 暴露的 QoS 是 DDS QoS 的子集，重点关注 7 个策略：

### 4.1 Reliability（可靠性）

| 值 | 含义 |
|----|------|
| `RELIABLE` | 保证投递（ACK/NACK + 重传），适合关键控制信号 |
| `BEST_EFFORT` | 不保证（类 UDP），适合高频传感器（图像、激光） |

### 4.2 History（历史）

| 值 | 含义 |
|----|------|
| `KEEP_LAST` + depth=N | 仅保留最后 N 条，超出丢旧 |
| `KEEP_ALL` | 保留全部（受资源限制） |

### 4.3 Durability（持久化）

| 值 | 含义 |
|----|------|
| `VOLATILE` | 仅给当前订阅者；后加入者拿不到旧数据 |
| `TRANSIENT_LOCAL` | Pub 缓存最近 N 条，新订阅者可拿到（latched 行为） |

> ⚠️ `TRANSIENT_LOCAL` **不支持** Intra-Process Communication。

### 4.4 Deadline / Liveliness / Lifespan

| 策略 | 用途 |
|------|------|
| `DEADLINE` | 期望最大发布间隔；违反触发 `requested_deadline_missed` 事件 |
| `LIVELINESS` | `AUTOMATIC` / `MANUAL_BY_TOPIC` + `lease_duration`，超时则 Sub 收到 liveliness 丢失事件 |
| `LIFESPAN` | 数据样本的最大有效期，超时被丢弃 |

### 4.5 兼容性匹配规则

DDS 采用 **Request vs Offered（RxO）** 模型，Sub（Request）与 Pub（Offered）必须满足兼容性才能建立连接：

| 策略 | 兼容条件（Sub ⇐ Pub） |
|------|------------------------|
| Reliability | Sub=BEST_EFFORT 接受任何；Sub=RELIABLE 要求 Pub=RELIABLE |
| Durability | Sub=VOLATILE 接受任何；Sub=TRANSIENT_LOCAL 要求 Pub=TRANSIENT_LOCAL |
| Deadline | Sub.period ≥ Pub.period |
| Liveliness | Sub.kind ≤ Pub.kind 且 Sub.lease ≥ Pub.lease |

> **故障排查首选**：`ros2 topic info /xxx --verbose` 查看双方 QoS。

### 4.6 预设 Profile

| Profile | Reliability | Durability | History/Depth |
|---------|-------------|------------|---------------|
| `rclcpp::QoS(10)` 默认 | RELIABLE | VOLATILE | KEEP_LAST/10 |
| `rclcpp::SensorDataQoS` | BEST_EFFORT | VOLATILE | KEEP_LAST/5 |
| `rclcpp::ServicesQoS` | RELIABLE | VOLATILE | KEEP_LAST/10 |
| `rclcpp::ParametersQoS` | RELIABLE | VOLATILE | KEEP_LAST/1000 |
| `rclcpp::ParameterEventsQoS` | RELIABLE | VOLATILE | KEEP_LAST/1000 |

### 4.7 用法

```cpp
auto qos = rclcpp::QoS(rclcpp::KeepLast(5))
              .best_effort()
              .durability_volatile()
              .deadline(std::chrono::milliseconds(100))
              .lifespan(std::chrono::seconds(1));

auto sub = create_subscription<sensor_msgs::msg::Image>(
    "image_raw", qos, callback);
```

---

## 五、QoS Override（运行时覆盖）

Iron+ 支持通过参数文件覆盖节点内的 QoS（无需改代码）：

```yaml
my_node:
  ros__parameters:
    qos_overrides:
      /chatter:
        publisher:
          reliability: best_effort
          history: keep_last
          depth: 1
```

代码中需显式开启允许覆盖：
```cpp
rclcpp::PublisherOptions opts;
opts.qos_overriding_options =
    rclcpp::QosOverridingOptions::with_default_policies();
```

---

## 六、DDS 调优（Fast DDS / Cyclone DDS）

### 6.1 Fast DDS：XML Profile

```bash
export FASTRTPS_DEFAULT_PROFILES_FILE=/path/to/fastdds.xml
```

```xml
<?xml version="1.0"?>
<dds xmlns="http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles">
  <profiles>
    <transport_descriptors>
      <transport_descriptor>
        <transport_id>shm</transport_id>
        <type>SHM</type>
        <segment_size>20971520</segment_size>
      </transport_descriptor>
    </transport_descriptors>
    <participant profile_name="default" is_default_profile="true">
      <rtps>
        <userTransports>
          <transport_id>shm</transport_id>
        </userTransports>
        <useBuiltinTransports>true</useBuiltinTransports>
      </rtps>
    </participant>
  </profiles>
</dds>
```

### 6.2 Cyclone DDS：XML 配置

```bash
export CYCLONEDDS_URI=file:///path/to/cyclonedds.xml
```

```xml
<CycloneDDS><Domain id="any">
  <General><AllowMulticast>spdp</AllowMulticast></General>
  <Internal>
    <SocketReceiveBufferSize min="10MB"/>
    <Watermarks><WhcHigh>500kB</WhcHigh></Watermarks>
  </Internal>
  <Discovery>
    <ParticipantIndex>auto</ParticipantIndex>
    <Peers><Peer Address="192.168.1.10"/></Peers>
  </Discovery>
</Domain></CycloneDDS>
```

### 6.3 常见调优点

| 问题 | 调优 |
|------|------|
| 大消息丢包 | 增大 OS UDP 缓冲：`sysctl net.core.rmem_max=2147483647` |
| 多播被路由器拦截 | 禁用多播 + 配置静态 Peer 列表（unicast discovery） |
| 启动慢 | Fast DDS 设 `Initial Announcements`，Cyclone DDS 调 `SPDPInterval` |
| 大量节点发现风暴 | 用 **Discovery Server**（Fast DDS） 或迁移到 **Zenoh** |
| 跨子网通信 | 中转：`fastdds discovery -i 0` 模式或 zenoh router |

---

## 七、安全：SROS2

基于 **DDS-Security** 标准（DDS Security 1.1），提供：
- **认证**（X.509 证书）
- **访问控制**（Permissions XML）
- **加密**（TLS-like AES-GCM 在 RTPS 层）

启用：
```bash
ros2 security create_keystore demo_keystore
ros2 security create_enclave demo_keystore /talker
export ROS_SECURITY_ENABLE=true
export ROS_SECURITY_STRATEGY=Enforce
export ROS_SECURITY_KEYSTORE=$PWD/demo_keystore
ros2 run demo_nodes_cpp talker --ros-args --enclave /talker
```

---

## 八、Zenoh（Jazzy 起 Tier-1）

`rmw_zenoh_cpp` 不再使用 DDS，而是 **Zenoh** 协议：

- **去除 SPDP/SEDP 多播**：避免发现风暴；
- **Router 模式**：天然支持跨子网、NAT 穿透、WAN；
- **保持 ROS2 API 不变**，但 Zenoh 不完全支持所有 DDS QoS（如 Deadline 语义略有差异）。

启动：
```bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
ros2 run rmw_zenoh_cpp rmw_zenohd   # 路由进程
ros2 run demo_nodes_cpp talker
```

适用场景：**多机器人车队**、**云-边-端协同**、**移动网络**。

---

## 九、面试高频问答

**Q1：ROS2 为什么选 DDS？**
工业级标准、丰富 QoS、去中心化发现、跨平台、可插拔（RMW）；对比 ROS1 自研协议，更适合生产。

**Q2：Pub/Sub 不通如何排查？**
1. `ros2 topic list -t` 看名字命名空间；
2. `ros2 topic info <topic> -v` 看 QoS 双方是否兼容；
3. `ros2 doctor` / 检查 `ROS_DOMAIN_ID` 与 `RMW_IMPLEMENTATION` 一致；
4. 防火墙、UDP 多播被禁；MTU 与缓冲区。

**Q3：SensorDataQoS 为什么是 BEST_EFFORT？**
高频数据丢一两帧不致命，要求低延迟；RELIABLE 重传会引入抖动并占用带宽。

**Q4：TRANSIENT_LOCAL 是什么场景？**
代替 ROS1 的 latched topic（如 `/map`、`/tf_static`），让晚到的订阅者也能拿到最近一份。

**Q5：进程内零拷贝怎么实现？**
同 Executor + `use_intra_process_comms=true` + 兼容 QoS（VOLATILE + KEEP_LAST + RELIABLE）+ 用 `unique_ptr` 发布。

**Q6：跨进程零拷贝？**
基于共享内存 Loaned Messages：`pub->borrow_loaned_message()`，需 RMW 与传输支持（Fast DDS SHM、Cyclone DDS+iceoryx）。

**Q7：多机器人发现风暴怎么办？**
1. 用 Fast DDS Discovery Server；
2. 关闭多播改 Peer List；
3. 切换 Zenoh；
4. 拆分 `ROS_DOMAIN_ID`。

---

## 十、RTPS 协议内部（为什么要懂）

### 10.1 发现两阶段

```
阶段 1: SPDP (Simple Participant Discovery Protocol)
   周期向预定 multicast 239.255.0.1:7400+偏移 发送 DATA(p)
   携带本 Participant 的 GUID、metatraffic locator、QoS

阶段 2: SEDP (Simple Endpoint Discovery Protocol)
   发现 Participant 后，在二者之间以 RELIABLE topic 交换：
      DATA(w) — 描述本端 DataWriter
      DATA(r) — 描述本端 DataReader
   完成后进行 QoS 兼容性判定，匹配的才会建连。
```

问题：节点越多，SPDP/SEDP 带宽呈 O(N²) 增长。**Discovery Server** / **Static Discovery** / **Zenoh** 均在解决这个问题。

### 10.2 RTPS 子消息

| Submessage | 用途 |
|------------|------|
| `DATA` | 用户数据 + payload |
| `HEARTBEAT` | Writer 告知 Reader 已发送范围 [first, last] |
| `ACKNACK` | Reader 确认 / 请求重传 |
| `GAP` | Writer 告知缺序号（丢弃） |
| `INFO_TS` | 时间戳 |
| `INFO_DST` | 目标 GUID |
| `NACK_FRAG` | Fragment 重传请求 |

了解这些可以看懂 Wireshark 抓包，定位丢包/重传问题。

### 10.3 GUID 与实体层级

```
GUID = GuidPrefix(12B) + EntityId(4B)
         ↑ Participant 唯一      ↑ 内部实体 ID
```

- DomainParticipant、DataWriter、DataReader 都有 GUID；
- Endpoint 间才能精准 ack/heartbeat。

### 10.4 SequenceNumber & Reliability

Writer 为每个消息分配递增 seq，维护 [first, last] 窗口；由 Reader 反馈决定何时可以丢旧。RELIABLE 下 Writer 需保留历史足够重传。

---

## 十一、Domain、Partition 与隔离手段

| 机制 | 层级 | 隔离强度 | 说明 |
|------|------|----------|------|
| **Domain ID** | DDS | 硬隔离 | 跨 Domain 互不可见 |
| **Partition** | DDS | 软隔离 | 同 Domain 同 Topic 可按名称过滤（ROS2 默认未暴露） |
| **Topic name** | ROS2 | 软 | 不同名互不连接 |
| **Namespace** | ROS2 | 软 | 为 topic/service 加前缀 |
| **Domain Tag**（DDS-Sec） | DDS-Security | 硬 | 在 secured Participant 上另一维隔离 |
| **Enclave** | SROS2 | 硬 | per-node 身份与权限 |

Domain ID 在 UDP 上映射为具体端口：

```
user_traffic_port  = 7400 + 250*domainId + 1 + 2*participantIndex
meta_traffic_port  = 7400 + 250*domainId + 0 + 2*participantIndex
# multicast meta-port 同理
```

这意味着 Domain ID 不同可能冲突另一个系统的端口，选 ID 需避开使用中范围（0–101推荐）。

---

## 十二、Discovery 优化详解

### 12.1 Fast DDS Discovery Server

```
         ┌──────────────────────────┐
         │  Discovery Server (中心化发现)  │
         └─┬──────────────────┬──────────┘
           │  unicast        │  unicast
         ┌─▼───────┐  ┌───────▼──────┐
         │ Robot 1   │  │ Robot 2 ...    │
         └─────────┘  └───────────────┘
```

```bash
fastdds discovery -i 0 -p 11811   # 启动 server
# 客户端
export ROS_DISCOVERY_SERVER=192.168.1.10:11811
ROS_SUPER_CLIENT=true ros2 run demo_nodes_cpp talker
```

优势：
- 逆转发现流量从 O(N²) 降为 O(N)；
- 同场跨子网穿透不需多播。

### 12.2 Cyclone DDS Static Discovery

在控制环境下，可预先静态声明发发现信息，进一步减少启动报文。

### 12.3 Zenoh Routing

`zenohd` 可运行为 router，提供 WAN 中转、订阅过滤、缓存；`rmw_zenoh_cpp` 默认走 router 模式，部署轻量。

---

## 十三、事件与告警

```cpp
rclcpp::PublisherOptions opts;
opts.event_callbacks.deadline_callback =
    [](rclcpp::QOSDeadlineOfferedInfo& e){ /* 错过最大间隔 */ };
opts.event_callbacks.liveliness_callback =
    [](rclcpp::QOSLivelinessLostInfo& e){ /* 丢失 liveliness */ };
opts.event_callbacks.incompatible_qos_callback =
    [](rclcpp::QOSOfferedIncompatibleQoSInfo& e){
        // 某个订阅者因为 QoS 不兼容被拒
    };
```

订阅侧同理：`message_lost_callback`、`requested_deadline_missed_callback`、`liveliness_changed_callback`。这些事件是生产环境下诊断问题的金钥匙。
