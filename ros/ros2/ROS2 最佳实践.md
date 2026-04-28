# ROS2 最佳实践

> 一份**可直接落地**的 ROS2 工程化最佳实践清单：从代码风格、包结构、通信模式、QoS、生命周期、参数、launch、构建、测试、日志、性能、安全到部署。所有条目都基于生产实践沉淀。
>
> 配套：[ROS2 入门教程](ROS2%20入门教程.md) / [节点与执行器](ROS2%20节点与执行器.md) / [DDS与QoS](ROS2%20DDS与QoS.md) / [实时性与性能优化](ROS2%20实时性与性能优化.md)

---

## 一、项目与包结构

### ✅ 推荐

- **元包（meta-package）模式**：一个产品 = 多个职能拆开的小包
  ```
  my_robot/
  ├── my_robot                    # 元包，仅依赖其余包，便于一次安装
  ├── my_robot_bringup            # launch + config，整体启动入口
  ├── my_robot_description        # URDF / xacro / mesh
  ├── my_robot_msgs               # 自定义消息（独立！）
  ├── my_robot_hw                 # ros2_control HardwareInterface
  ├── my_robot_perception
  ├── my_robot_planning
  ├── my_robot_control
  └── my_robot_tests              # 集成测试 / launch_testing
  ```
- **消息独立成包**：`*_msgs` 永不依赖业务代码，谁都能链接，避免循环依赖。
- **包名小写 + 下划线**：`my_robot_perception` ✅；`MyRobotPerception` ❌。
- **可执行文件名带前缀**：`my_robot_perception_node` 而非 `node`，避免冲突。

### ❌ 反模式

- 一个超大 monorepo 单包写所有节点；
- 业务包同时定义消息（其他包要用就被迫依赖你的业务代码）；
- 把 launch / urdf 散在各业务包，启动时找不到入口。

---

## 二、构建与依赖（colcon / ament）

| 实践 | 说明 |
|------|------|
| **`colcon build --symlink-install`** | Python / launch / config 改了无需重编 |
| **`--packages-up-to <pkg>`** | 只编你关心的子树 |
| **`--event-handlers console_direct+`** | 实时输出编译错误 |
| **`--mixin release`**（colcon mixin） | 统一 -O2 -DNDEBUG |
| `package.xml` 必须**精确声明**依赖 | 漏写在 CI 第一台干净机器上炸 |
| `ament_target_dependencies()` | C++ 优先用，自动传递 include + link |
| **library 导出三件套** | `install(TARGETS ... EXPORT)` + `ament_export_targets` + `ament_export_dependencies`（详见 [ament_cmake与colcon高级](ROS2%20ament_cmake与colcon高级.md)） |
| 用 **`rosdep install --from-paths src --ignore-src -y`** | 一键拉系统依赖，CI/Docker 必备 |

CI/CD：用 [`industrial_ci`](https://github.com/ros-industrial/industrial_ci) 或 `action-ros-ci`，多 distro 矩阵。

---

## 三、节点与执行器

### ✅ 推荐

- **一个节点做一件事**（Single Responsibility）：感知、规划、控制分开。
- **优先 `rclcpp::Node` + Composition**：用 `rclcpp_components` 把多节点跑在同一进程，享受**进程内零拷贝**（IPC）。
- **MultiThreadedExecutor + CallbackGroup**：
  - 每个高频回调（控制环）放 **MutuallyExclusive** group；
  - 服务回调放 **Reentrant** group，避免阻塞主流程；
  - 不要让一个 callback 阻塞另一个 callback 的资源。
- **回调要短**：>10ms 的工作搬去工作线程 / 任务队列。
- 长任务用 **Action**，不要在 Service 里 sleep。

### ❌ 反模式

- 在 callback 里 `std::this_thread::sleep_for` / `wait_for_service`；
- SingleThreadedExecutor + 阻塞服务调用 → **死锁**（自己调自己服务）；
- 全部回调都丢一个默认 group → 失去并行机会或互相阻塞。

详见 [ROS2 节点与执行器](ROS2%20节点与执行器.md)。

---

## 四、命名与坐标系（REP-103 / REP-105）

### 命名规范

| 资源 | 推荐 | 反例 |
|------|------|------|
| Topic | `/perception/lidar/points` 分层 | `/points1`, `/topic_a` |
| 私有参数 | `~speed_limit` | 全局 `speed_limit` |
| Frame | `base_link`、`odom`、`map`、`<sensor>_link` | `link0`, `frame1` |
| Action | 动词 + 名词：`navigate_to_pose` | `do_action`, `task1` |
| Service | 同 Action：`set_max_speed` | `srv1` |

**单位与坐标系（REP-103）**：
- 长度米、角度弧度、速度 m/s、力 N、质量 kg；
- ENU（x 前 / y 左 / z 上）为机体；相机为 z 朝前 x 右 y 下；
- TF 链：`earth → map → odom → base_link → ...`（[REP-105](https://www.ros.org/reps/rep-0105.html)）。

---

## 五、消息设计

| 实践 | 说明 |
|------|------|
| **必带 `Header`** | 凡涉及时间 / 坐标的消息（含 `frame_id` + `stamp`） |
| 单位放注释 | `float64 speed   # m/s`，避免 km/h 误解 |
| 大数据消息**独立 Topic** | 点云 / 图像别和 5 Hz 状态混发 |
| 用**枚举常量**而非魔数 | `uint8 STATE_IDLE=0` 等 |
| 自定义消息 stable 后 **冻结布局** | 后续兼容用 XTypes optional 字段 |
| 不要在消息里塞超大固定数组 | 用 `sequence<>` 动态长度 |

XTypes 与可演化字段：见 [ROS2 消息序列化与XTypes](ROS2%20消息序列化与XTypes.md)。

---

## 六、QoS 选择

通信稳定的关键。**记忆三组合**：

| 数据类型 | reliability | durability | history |
|----------|-------------|------------|---------|
| 命令（cmd_vel） | RELIABLE | VOLATILE | KEEP_LAST(1) |
| 高频传感器（scan/imu） | **BEST_EFFORT** | VOLATILE | KEEP_LAST(5~10) |
| 状态/事件 | RELIABLE | VOLATILE | KEEP_LAST(10) |
| 静态/锁存（map, robot_description） | RELIABLE | **TRANSIENT_LOCAL** | KEEP_LAST(1) |
| 大数据流（图像/点云） | BEST_EFFORT | VOLATILE | KEEP_LAST(2~5) |

代码：
```cpp
auto qos = rclcpp::SensorDataQoS();          // BEST_EFFORT for sensors
auto qos = rclcpp::QoS(1).transient_local(); // latched
```

❗ **Pub/Sub QoS 不匹配 = 收不到消息**。规则：
- reliability：sub ≤ pub（BEST_EFFORT 订阅可收 RELIABLE）；
- durability：sub ≤ pub（VOLATILE 订阅可收 TRANSIENT_LOCAL）；
- 排查：`ros2 topic info /xxx --verbose`。

---

## 七、参数（Parameter）

### ✅ 推荐

- **强类型 + 描述符**：
  ```cpp
  rcl_interfaces::msg::ParameterDescriptor d;
  d.description = "max linear speed (m/s)";
  d.floating_point_range.resize(1);
  d.floating_point_range[0].from_value = 0.0;
  d.floating_point_range[0].to_value   = 5.0;
  declare_parameter("max_speed", 1.0, d);
  ```
- **YAML 文件管理**：每个节点一份 `config/<node>.yaml`，由 launch 加载，避免命令行长串。
- **on_set_parameters_callback** 校验：返回失败拒绝非法值，不要默默接受。
- 高频读：**缓存到成员变量**，参数 callback 中更新（`get_parameter()` 不是零开销）。
- 关键参数（控制器增益、限速）做**热更新**测试。

### ❌ 反模式

- 在控制循环里每次 `get_parameter()`；
- 参数没有默认值，缺失就 crash；
- 多节点共享参数靠拷贝 YAML，更新易漏。

---

## 八、Launch 文件

### ✅ 推荐

```python
def generate_launch_description():
    pkg = get_package_share_directory('my_robot_bringup')

    use_sim_time = LaunchConfiguration('use_sim_time')
    namespace    = LaunchConfiguration('namespace')

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('namespace',    default_value=''),

        GroupAction([
            PushRosNamespace(namespace),
            IncludeLaunchDescription(...),     # 子模块
            Node(..., parameters=[{'use_sim_time': use_sim_time}]),
        ]),

        # 失败检测：核心节点退出整体重启
        RegisterEventHandler(OnProcessExit(
            target_action=critical_node, on_exit=[Shutdown()])),
    ])
```

要点：
- **launch 参数化**：use_sim_time / namespace / log_level / config_file 都可命令行传；
- **顶层只有一个 bringup**，复杂模块靠 `IncludeLaunchDescription` 拼接；
- **lifecycle launch**：用 `EmitEvent(ChangeState)` 显式 configure→activate；
- **launch_testing** 写关键集成测试（节点活性、Topic 频率、Service 通否）。

详见 [ROS2 参数与Launch高级](ROS2%20参数与Launch高级.md)。

---

## 九、生命周期与组合

| 何时用 Lifecycle | 何时用普通 Node |
|------------------|------------------|
| 真实硬件需明确 init/configure/activate 顺序 | 简单工具节点 |
| 需要被外部编排（State Machine / Nav2） | demo |
| 启停节点不重启进程 | 一次性脚本 |
| 资源/带宽要求 deactivate 时为零 | 无 |

最佳实践：
- `on_configure`：分配资源、加载参数、声明 publisher/subscriber；
- `on_activate`：激活 publisher（开始发数据）；
- `on_deactivate`：停 publisher，**保留** sub/参数；
- `on_cleanup`：释放所有资源；
- 失败返回 `FAILURE`，进入 ErrorProcessing；
- 与 Composition 结合：`rclcpp_components::ComponentManager` + lifecycle。

---

## 十、TF / 时间

| 实践 | 说明 |
|------|------|
| 静态变换用 `/tf_static` + TRANSIENT_LOCAL | 永远不要周期发 static |
| 一个 frame 只有**一个**父亲（树而非图） | TF tree 唯一性 |
| `lookupTransform` 永远 try-catch | 数据时序错乱时不要 crash |
| 用 `tf2::TimePointZero` 取最新 | 别用 `now()` 容易超 timeout |
| 仿真节点全部 `use_sim_time:=true` | 否则 TF 时间错位 |
| 高频传感器 → robot_localization EKF | 不要直接发 odom 当 TF |
| 跨机时钟同步 chrony / PTP | 多机 TF 错位是同步问题 |

详见 [ROS2 TF2与时间](ROS2%20TF2与时间.md) / [common/数学与坐标变换基础](../common/数学与坐标变换基础.md)。

---

## 十一、错误处理与日志

### ✅ 推荐

- 用 **RCLCPP 宏**而非 `std::cout`：`RCLCPP_INFO/WARN/ERROR(get_logger(), ...)`，能被 `ros2 launch --log-level` 控制。
- **限频日志**：`RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 1000, ...)`，避免日志风暴。
- 异常：**callback 内绝不让异常穿出**（会 crash executor）；包好 try-catch 转告警。
- 关键状态变化用 **diagnostic_updater** 暴露给 `/diagnostics`，配合 `rqt_runtime_monitor`。
- 部署用 **结构化日志**：JSON 格式 + 集中收集（fluent-bit / loki）。

### ❌ 反模式

- 高频回调里 `RCLCPP_INFO` → 日志写穿磁盘；
- 把异常当流程控制；
- 错误只 print 不 diagnostic，外部无法监测。

---

## 十二、性能与实时

通用：
- **进程内 IPC**：同一 ComponentContainer 启动多组件，享受零拷贝；
- 大消息用 **Loaned Messages** + RMW 零拷贝（Cyclone+iceoryx / FastDDS SHM）；
- **避免不必要的拷贝**：订阅签名用 `ConstSharedPtr`，发布用 `unique_ptr`；
- 高频路径**预分配** `std::vector::reserve`、消息池；
- 控制循环不做：内存分配、文件 IO、锁、ROS 日志。

实时（PREEMPT_RT）：
- 内核 PREEMPT_RT；
- `chrt -f 80 ros2 ...` 设置 SCHED_FIFO；
- 使用 `realtime_tools::RealtimeBuffer/Box`；
- CPU isolation + irqbalance 关闭；
- 关 swap、关 frequency scaling；
- 用 `cyclictest` 验证 latency。

详见 [ROS2 实时性与性能优化](ROS2%20实时性与性能优化.md) / [ros2_control进阶](ROS2%20ros2_control进阶.md)。

---

## 十三、测试

### 测试金字塔

```
            ┌─────────────┐
            │ launch_test │   <- 整系统少量
            └─────────────┘
        ┌────────────────────┐
        │  集成（多节点）     │   <- 关键链路
        └────────────────────┘
   ┌───────────────────────────┐
   │  单元（gtest / pytest）    │   <- 大量、快
   └───────────────────────────┘
```

| 实践 | 工具 |
|------|------|
| 业务逻辑解耦 ROS API | gtest / pytest 单元测试 |
| 节点级集成 | rclcpp / rclpy 拉起节点 + 模拟 publisher |
| 整系统 | `launch_testing` + ReadyToTest + post_shutdown 断言 |
| 静态检查 | `ament_lint_auto` + clang-format / cpplint / flake8 |
| 性能回归 | rosbag 录制 + 离线回放 + ATE/RPE 评估（evo） |
| CI 矩阵 | `industrial_ci` / `action-ros-ci` 多 distro |

详见 [ROS2 测试_CI_CD](ROS2%20测试_CI_CD.md)。

---

## 十四、安全（SROS2）

生产部署最低要求：
- 启用 **DDS-Security**：Authentication + AccessControl + Cryptographic；
- 每个节点独立 **enclave** + 私有证书；
- `governance.xml` 全局策略 + `permissions.xml` 细粒度白名单；
- 私钥**不上 git**；用 PKI 自动签发（step-ca / Vault / AWS PCA）；
- **跨网用 VPN（WireGuard）+ 域内 SROS2** 双层；
- 启用日志审计：所有发布/订阅记录 `enclave_name`。

详见 [ROS2 安全Security实操与PKI](ROS2%20安全Security实操与PKI.md)。

---

## 十五、部署

| 维度 | 推荐 |
|------|------|
| 容器 | Docker `--network host`（DDS 多播）+ ROS_DOMAIN_ID 隔离 |
| 进程管理 | systemd unit `Restart=on-failure` + `WatchdogSec` |
| 配置外置 | `/etc/my_robot/*.yaml`，镜像不打死 |
| 日志 | rosout → journald → 中心化（fluent-bit） |
| 度量 | `node_exporter` + Prometheus + Grafana |
| OTA | mender / balena / 自研增量包 |
| bag | rosbag2 mcap，按场景轮转，自动上传 |
| 跨机时间 | chrony（普通）/ PTP（精度 < 1ms） |
| 紧急遥停 | **独立通道**（4G UDP），不依赖 ROS2 graph |

---

## 十六、文档与协作

- `README.md`：包用途、依赖、构建、运行示例（5 行 `ros2 run` 能跑）；
- `CHANGELOG.rst` 用 `catkin_generate_changelog` 自动生成；
- API 文档用 doxygen / mkdocs，`ament_cmake_sphinx`；
- **Topic 列表表格**写在 README：名 / 类型 / QoS / 频率 / 含义；
- 关键决策（QoS 选型、坐标系约定）写 `docs/decisions/ADR-*.md`；
- 代码风格遵守 [ROS2 Developer Guide](https://docs.ros.org/en/rolling/The-ROS2-Project/Contributing/Developer-Guide.html)；C++ 用 `clang-format`，Python 用 `ament_flake8` + `black`。

---

## 十七、迁移与版本

- **跟 LTS**：生产用 Humble（22.04）/ Jazzy（24.04）/ Kilted。**不要追 Rolling**。
- 升级先在 dev 分支跑全量回归 + bag 回放。
- 多 distro 共存：colcon workspace 隔离，**不要在同 shell** source 两个 distro。
- 与 ROS1 共存：用 `ros1_bridge`，**双向桥接关键 topic**，最终切完拆桥。

---

## 十八、Top 20 速记 Checklist

代码：
- [ ] 包按职能拆分，msgs 独立
- [ ] 消息含 Header + 单位注释
- [ ] QoS 显式选择，不依赖默认
- [ ] 节点用 Composition + IPC
- [ ] CallbackGroup 合理使用
- [ ] 参数有描述符 + 校验
- [ ] 日志限频 + 结构化
- [ ] 异常不穿出 callback

工程：
- [ ] colcon `--symlink-install`
- [ ] CI 多 distro 矩阵
- [ ] launch_testing 覆盖关键链路
- [ ] rosdep 干净机器可装
- [ ] `package.xml` 依赖完整

部署：
- [ ] Docker host 网络 + DOMAIN_ID
- [ ] systemd 守护 + watchdog
- [ ] 配置外置
- [ ] mcap bag 自动轮转
- [ ] 多机 chrony / PTP
- [ ] 启用 SROS2
- [ ] 紧急遥停独立通道

---

## 十九、面试速记（最高频 10 条）

1. **包结构**：业务包 + msgs 独立 + bringup 元包；
2. **通信选择**：周期 Topic / 短查询 Service / 长任务 Action；
3. **QoS 三组合**：sensor=BEST_EFFORT、command=RELIABLE、map/desc=TRANSIENT_LOCAL；
4. **Executor**：MultiThreaded + 合理 CallbackGroup；
5. **零拷贝**：Composition + Loaned Messages + iceoryx；
6. **Lifecycle**：硬件节点必备；
7. **launch**：Python + IncludeLaunchDescription + GroupAction + EventHandler；
8. **测试**：gtest + launch_testing + industrial_ci；
9. **安全**：DDS-Security 五插件 + enclave + PKI；
10. **实时**：PREEMPT_RT + RealtimeBuffer + 预分配 + 控制环零分配。
