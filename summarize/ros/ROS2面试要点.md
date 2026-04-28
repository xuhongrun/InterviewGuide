# ROS2 面试要点

> 浓缩版：ROS2 架构、Executor、QoS、Lifecycle、性能优化与高频面试问答。配合 [ros/ros2/](../../ros/ros2/) 系列文档食用。

---

## 一、ROS2 整体架构（必背）

```
┌────────────────────────────────────────────────────┐
│  用户代码                                           │
├────────────────────────────────────────────────────┤
│  rclcpp / rclpy        ← 客户端库，封装 Executor    │
├────────────────────────────────────────────────────┤
│  rcl                   ← C 公共 API（语言无关）     │
├────────────────────────────────────────────────────┤
│  rmw                   ← 中间件抽象层 (ABI 接口)    │
├────────────────────────────────────────────────────┤
│  RMW 实现：fastrtps / cyclonedds / connext / zenoh  │
├────────────────────────────────────────────────────┤
│  DDS / RTPS / 共享内存                              │
└────────────────────────────────────────────────────┘
```

- **无 Master**：DDS 自动发现（SPDP + SEDP），节点对等。
- **rmw 可热切换**：`export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`。
- **Domain ID**：`ROS_DOMAIN_ID`（0–101 推荐），UDP 端口由公式 `7400 + 250*ID + …` 派生。

### 版本

| 版本 | Ubuntu | 状态 |
|------|--------|------|
| Foxy | 20.04 | EOL |
| Humble | 22.04 | LTS（推荐） |
| Iron | 22.04 | EOL |
| **Jazzy** | **24.04** | **LTS（最新生产版）** |
| Rolling | — | 滚动开发 |

---

## 二、Executor 与并发（最常考）

### 四种 Executor

| 类型 | 线程数 | 场景 |
|------|--------|------|
| **SingleThreadedExecutor** | 1 | 默认；简单节点 |
| **MultiThreadedExecutor** | N | I/O 密集、跨组并发 |
| **StaticSingleThreadedExecutor** | 1 | 实体不变的实时控制循环（少 wait_set 重建） |
| **EventsExecutor**（Iron+） | 可配 | 低延迟事件驱动 |

### CallbackGroup（关键）

| 类型 | 同组并发 | 跨组并发 |
|------|----------|----------|
| **MutuallyExclusive**（默认） | ❌ 互斥 | ✅ |
| **Reentrant** | ✅ 可并行 | ✅ |

> ⚠️ **死锁陷阱**：在默认 group 中调 `spin_until_future_complete` 会永远等待。解决：把 Client 放独立 ReentrantGroup，或用 MultiThreadedExecutor，或改异步回调。

---

## 三、QoS 七大策略（必背）

| Policy | 取值 | 默认 |
|--------|------|------|
| **Reliability** | RELIABLE / BEST_EFFORT | RELIABLE |
| **Durability** | VOLATILE / **TRANSIENT_LOCAL** | VOLATILE |
| **History** | KEEP_LAST(N) / KEEP_ALL | KEEP_LAST(10) |
| **Deadline** | period | ∞ |
| **Lifespan** | ttl | ∞ |
| **Liveliness** | AUTOMATIC / MANUAL_BY_TOPIC | AUTOMATIC |
| **Liveness/Lease Duration** | duration | ∞ |

### 兼容性（RxO 规则）

> Pub 提供（Offered）必须 ≥ Sub 请求（Requested），否则**不会建立连接**。

|  | Sub: BEST_EFFORT | Sub: RELIABLE |
|---|---|---|
| **Pub: BEST_EFFORT** | ✅ | ❌ |
| **Pub: RELIABLE** | ✅ | ✅ |

|  | Sub: VOLATILE | Sub: TRANSIENT_LOCAL |
|---|---|---|
| **Pub: VOLATILE** | ✅ | ❌ |
| **Pub: TRANSIENT_LOCAL** | ✅ | ✅ |

### 预设 Profile

- `rclcpp::SystemDefaultsQoS()`：跟随 RMW 默认。
- `rclcpp::SensorDataQoS()`：BEST_EFFORT + KEEP_LAST(5)，传感器流。
- `rclcpp::ServicesQoS()`：RELIABLE + KEEP_LAST(10)，服务用。
- `rmw_qos_profile_parameters` / `rmw_qos_profile_parameter_events`。

---

## 四、Lifecycle Node（生产必备）

### 状态机

```
   create
     ↓
  ┌────────────┐  configure   ┌────────────┐  activate  ┌────────────┐
  │ unconfigured├─────────────►│  inactive  ├───────────►│   active   │
  └─────┬──────┘  cleanup     └────────┬───┘  deactivate└──────┬─────┘
        │                              │                       │
        └──── shutdown ────────────────┴───────────────────────┘
                                       ↓
                                  finalized
```

- **on_configure**：分配资源、声明参数（不发布消息）；
- **on_activate**：激活 Publisher（用 `LifecyclePublisher`）；
- **on_deactivate**：暂停发布；
- **on_cleanup**：释放资源；
- **Nav2、ros2_control 全部基于 Lifecycle**，`lifecycle_manager` 统一编排。

---

## 五、Composition（性能差异化）

- **同进程多 Node 共享 Executor + 智能指针** → 零拷贝；
- 启用：`NodeOptions().use_intra_process_comms(true)`；
- 发布用 `unique_ptr` 配合 `std::move`，订阅同样收到 `unique_ptr`；
- 容器：`component_container`（单线程） / `component_container_mt`（多线程） / `component_container_isolated`（每个 Node 一个 Executor）。

---

## 六、零拷贝层级

| 层级 | 技术 | 条件 |
|------|------|------|
| **进程内 IPC** | `use_intra_process_comms=true` + `unique_ptr` move | 同 Executor、QoS 兼容 |
| **跨进程 SHM** | Loaned Messages + `borrow_loaned_message()` | RMW 支持 + 消息全有界类型 |
| **跨主机** | UDP / TCP（必拷贝） | — |

```cpp
auto loan = pub->borrow_loaned_message();   // 从 SHM 池借
loan.get().data = 42;
pub->publish(std::move(loan));               // 不拷贝
```

---

## 七、实时性（高级岗必考）

- **PREEMPT_RT 内核** + **SCHED_FIFO 优先级**；
- **`mlockall(MCL_CURRENT|MCL_FUTURE)`** 锁内存防换页；
- **TLSF 实时分配器** 替换 malloc；
- **StaticSingleThreadedExecutor** 减少抖动；
- 控制循环典型 **1kHz**，cyclictest 应 < 50µs；
- `isolcpus` + `nohz_full` + `irq affinity` 隔离专用核。

---

## 八、参数（Parameter）

```cpp
declare_parameter<double>("rate", 10.0);
double r = get_parameter("rate").as_double();
auto cb = add_on_set_parameters_callback([](auto& params){...});  // 校验
```

- 参数描述符：`ParameterDescriptor`（类型、范围、只读、动态可改）；
- launch.py 传入：`parameters=[{'rate': 20.0}]`；
- YAML 配置：`/node_name: ros__parameters: ...`。

---

## 九、Launch / 构建

- **launch.py（Python DSL）**：`Node`、`ComposableNodeContainer`、`IncludeLaunchDescription`、`DeclareLaunchArgument`、`OpaqueFunction`。
- **colcon build**：`--symlink-install`、`--packages-select`、`--packages-up-to`。
- **package.xml format 3**：`<exec_depend>`、`<test_depend>`、`<member_of_group>ros2cli</member_of_group>`。
- **ament_cmake**（C++） vs **ament_python**（Python）。
- **rosidl** 生成 `.msg/.srv/.action` 多语言绑定。

---

## 十、调试与性能工具

| 工具 | 用途 |
|------|------|
| `ros2 topic info -v` | 看 QoS、连接数 |
| `ros2 topic delay` | 端到端延迟 |
| `ros2 doctor` / `wtf` | 整体健康 |
| `ros2 daemon stop/start` | 发现缓存异常 |
| `ros2_tracing + LTTng` | 回调级 tracing |
| `performance_test` | 标准 benchmark |
| `rosbag2`（**MCAP**为 Jazzy 默认） | 录制回放 |
| `diagnostic_updater` | 诊断聚合 |
| Foxglove Studio | MCAP 可视化 |

---

## 十一、生态拼图

| 项目 | 用途 |
|------|------|
| **ros2_control** | 实时硬件抽象 + Controller 框架（1kHz read/update/write） |
| **Nav2** | 行为树驱动的导航栈（Planner/Controller/Recovery + Costmap） |
| **MoveIt 2** | 机械臂运动规划 |
| **micro-ROS** | MCU 上的 ROS2（rclc + Micro XRCE-DDS Agent） |
| **SROS2** | DDS-Security 集成（5 插件 + enclave） |
| **Autoware** | 自动驾驶完整栈 |
| **slam_toolbox / cartographer** | SLAM |

---

## 十二、面试高频问答

**Q1：ROS2 为什么不要 Master？**
DDS 提供分布式自动发现（SPDP/SEDP），消除单点故障，天然支持多机。

**Q2：QoS 不兼容会发生什么？**
**直接不建立连接**，订阅看不到话题。`ros2 topic info -v` 第一时间排查，注册 `incompatible_qos_callback` 可拿到事件。

**Q3：默认 QoS 是 RELIABLE 还是 BEST_EFFORT？**
`SystemDefaults`（≈ RELIABLE + KEEP_LAST(10) + VOLATILE）。**传感器数据应改 SensorDataQoS**（BEST_EFFORT），否则慢订阅会让 Pub 端堆积。

**Q4：怎么实现 ROS1 的 latched topic？**
`durability = TRANSIENT_LOCAL`，新订阅者也能收到最近一份（典型用法：`/map`、`/tf_static`）。

**Q5：Service 回调里再调 Service 卡死怎么办？**
默认 MutuallyExclusive group 不可重入。把 Client 放独立 ReentrantGroup，或换 MultiThreadedExecutor，或用 `async_send_request` + 回调（推荐）。

**Q6：进程内零拷贝条件？**
共享同一 Executor + `use_intra_process_comms=true` + Pub/Sub QoS 兼容（KEEP_LAST + VOLATILE + RELIABLE）+ 用 `unique_ptr` 发布。

**Q7：跨进程零拷贝怎么做？**
Loaned Messages + RMW SHM 传输（Fast DDS SHM、Cyclone DDS+iceoryx）。**消息所有字段必须有界**（`int32[<=N]`、`string<=N`），否则无法走 SHM。

**Q8：DDS 实现怎么选？**

| RMW | 优势 | 劣势 |
|-----|------|------|
| Fast DDS（默认） | Discovery Server、SHM 完善 | 历史 bug 较多 |
| Cyclone DDS | 轻量、性能稳定，Eclipse 维护 | 商业支持弱 |
| Connext（RTI） | 商业、工具链强 | 收费 |
| Zenoh（rmw_zenoh） | 跨 WAN、低带宽 | 较新 |

**Q9：多机器人发现风暴怎么治？**
① **Fast DDS Discovery Server**（中心化发现）；② 关闭多播改 Peer List；③ 切 Zenoh；④ 拆 Domain ID。

**Q10：Lifecycle Node 解决什么问题？**
**确定性的启动/停止顺序**——避免话题在 unconfigured 时被误用，便于编排（lifecycle_manager 统一管理）。Nav2 / ros2_control 强依赖。

**Q11：Composition 与单独 Node 启动的差别？**
Composition = **同进程**，可享 IPC 零拷贝；单独 Node = **跨进程**，必走 DDS（即便有 SHM 也需 RMW 支持）。生产高频管道（感知-规划-控制）应放同 Container。

**Q12：怎么做 ROS2 实时？**
PREEMPT_RT + SCHED_FIFO + mlockall + StaticSingleThreadedExecutor + 预分配池 + 隔离 CPU + 消息全有界 + SHM 传输。

**Q13：rosbag2 默认存储格式是什么？**
**Jazzy 起默认 MCAP**（更早是 sqlite3 `.db3`）。MCAP 可流式追加、跨工具兼容（Foxglove）。

**Q14：消息版本不兼容怎么办？**
ROS2 用 **XTypes** 注解控制兼容性：`@final`（严格）/ `@appendable`（默认，末尾追加）/ `@mutable`（按 `@id` 增删）+ `@optional`。

**Q15：ROS2 topic 在 DDS 层叫什么？**
加前缀 `rt/topic`、Service Request `rq/...Request`、Reply `rr/...Reply`。原生 DDS 应用按此规则可与 ROS2 互通。

**Q16：micro-ROS 是什么？**
面向 MCU/RTOS（FreeRTOS/Zephyr/NuttX）的 ROS2，使用 **rclc + rmw_microxrcedds_c**，通过 **Micro XRCE-DDS Agent**（运行在 host）桥接到主网，典型 RAM 占用 ~30KB。

**Q17：SROS2 怎么工作？**
基于 **DDS-Security 1.1** 五插件（认证/访问控制/加密/日志/数据标签），用 **enclave + keystore + governance.xml + permissions.xml** 控制每个 Node 的身份与权限。

---

## 十三、一行速记

- ROS2 = **rclcpp + rcl + rmw + DDS**
- 性能金字塔：**算法 → IPC/SHM 零拷贝 → DDS QoS → OS/内核**
- 默认 SingleThreaded + MutuallyExclusive，**避免在默认 group 内同步等 future**
- QoS 兼容是**第一排查项**，`ros2 topic info -v`
- 高频管道用 **Composition + IPC**；实时控制用 **StaticExecutor + PREEMPT_RT**
- Jazzy 起 rosbag2 默认 **MCAP**
