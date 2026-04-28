# ROS1 vs ROS2 全面对比与迁移建议

> 系统化梳理两代框架的差异，覆盖架构、API、构建、部署、迁移路径。

---

## 一、整体架构对比

| 维度 | ROS1 | ROS2 |
|------|------|------|
| 中心节点 | **roscore（Master）** 必需 | **无中心**，DDS 自动发现 |
| 通信协议 | TCPROS / UDPROS（自研） | **DDS / RTPS**（OMG 标准），可换 Zenoh |
| 中间件 | 单一实现 | **RMW 抽象**，可换 fastrtps/cyclonedds/connext/zenoh |
| 进程模型 | 节点 = 进程（多进程） | 支持 **Composition**（进程内多节点） |
| 实时性 | 不支持 | 内核 RT + Static Executor + Loaned Msgs |
| QoS | 无 | 丰富（Reliability/Durability/Deadline/...） |
| 安全 | 无 | **SROS2**（DDS-Security） |
| 节点状态机 | 无 | **Managed Lifecycle Node** |
| 跨平台 | Linux 为主 | Linux / Windows / macOS / micro-ROS |
| Python | rospy（Py2/3） | **rclpy**（Py3） |
| 构建 | catkin（CMake）| **colcon + ament** |
| Launch | XML | **Python**（也支持 XML/YAML） |
| Bag 格式 | `.bag` | **MCAP**（Iron+） / `.db3`（SQLite） |
| 工具命令 | `rosX` 散落 | **统一 `ros2 X`** |

---

## 二、API 对照（C++）

| 任务 | ROS1（roscpp） | ROS2（rclcpp） |
|------|----------------|----------------|
| 初始化 | `ros::init(argc, argv, "node")` | `rclcpp::init(argc, argv)` + `Node` 子类 |
| 节点 | `ros::NodeHandle nh;` | `class N : public rclcpp::Node` |
| 发布 | `nh.advertise<T>("t", 10)` | `create_publisher<T>("t", 10)` |
| 订阅 | `nh.subscribe("t", 10, cb)` | `create_subscription<T>("t", 10, cb)` |
| Service Server | `nh.advertiseService("s", cb)` | `create_service<T>("s", cb)` |
| Service Client | `nh.serviceClient<T>("s")` | `create_client<T>("s")` |
| Action | `actionlib::SimpleActionServer/Client` | `rclcpp_action::create_server/client` |
| 参数 | `nh.param("k", v, def)` | `declare_parameter("k", def)` + `get_parameter` |
| 时间 | `ros::Time::now()` | `this->now()` |
| Spin | `ros::spin()` | `rclcpp::spin(node)` |
| Logger | `ROS_INFO("...")` | `RCLCPP_INFO(get_logger(), "...")` |

---

## 三、API 对照（Python）

| 任务 | ROS1（rospy） | ROS2（rclpy） |
|------|---------------|---------------|
| 初始化 | `rospy.init_node("n")` | `rclpy.init()` + `Node("n")` |
| Publisher | `rospy.Publisher(...)` | `node.create_publisher(...)` |
| Subscriber | `rospy.Subscriber(...)` | `node.create_subscription(...)` |
| Spin | `rospy.spin()` | `rclpy.spin(node)` |
| Sleep | `rospy.sleep(1.0)` | `rclpy.spin_once(node, timeout_sec=1.0)` 或 `rate.sleep()` |
| 参数 | `rospy.get_param("k")` | `node.declare_parameter("k").value` |

---

## 四、消息/接口

```idl
# ROS1 .msg          # ROS2 .msg（语法相同，类型生成走 rosidl）
std_msgs/Header header
geometry_msgs/Pose pose
```

差异：
- ROS2 添加了 **bounded sequences**（`int32[<=10]`）、**bounded strings**（`string<=64`）以支持 SHM；
- IDL 顶层格式：ROS2 内部把 `.msg` 转成 OMG IDL（`.idl`），可直接互通 DDS 应用；
- 自定义消息**必须**用 rosidl 生成器，不再用 `gencpp/genpy`。

---

## 五、Bag 数据

| 维度 | ROS1 | ROS2 |
|------|------|------|
| 格式 | `.bag`（自定义） | `.db3`（SQLite，默认） / `.mcap`（Iron+ 推荐） |
| 工具 | `rosbag record/play/info` | `ros2 bag record/play/info/convert` |
| 跨版本兼容 | 仅 ROS1 | ROS2，支持转换 ROS1 ↔ ROS2（`rosbags` 工具） |

---

## 六、迁移路径

### 6.1 共存方案：ros1_bridge

```bash
sudo apt install ros-humble-ros1-bridge
# 同时 source ROS1 与 ROS2
source /opt/ros/noetic/setup.bash
source /opt/ros/humble/setup.bash
ros2 run ros1_bridge dynamic_bridge --bridge-all-topics
```

适合**渐进式迁移**：保留 ROS1 节点（如老硬件驱动），新模块走 ROS2，bridge 桥接同名话题。注意：
- 大消息桥接有拷贝开销；
- 自定义消息需要 ROS1 与 ROS2 各编一份并提供映射；
- 不支持完整 QoS 语义。

### 6.2 代码迁移要点

1. **CMakeLists.txt**：`catkin_package` → `ament_package` + `find_package` 全部包；
2. **package.xml**：`format=2` → `format=3`，`build_depend/run_depend` → `depend`；
3. **消息**：`gencpp` → `rosidl_generate_interfaces`，依赖加 `rosidl_default_*`；
4. **节点类**：从 `NodeHandle` 改为继承 `rclcpp::Node`；
5. **回调签名**：参数从 `const T::ConstPtr&` 改为 `const T::SharedPtr` 或 `T::ConstSharedPtr`；
6. **参数**：必须先 `declare_parameter`；
7. **Time/Duration**：`ros::Time` → `rclcpp::Time`，注意 clock source（仿真时间需 `use_sim_time`）；
8. **Logger**：`ROS_INFO` → `RCLCPP_INFO(get_logger(), ...)`；
9. **launch**：XML → Python（也支持 XML），且 `<node>` 写法改变；
10. **测试**：`rostest` → `launch_testing` + `pytest`/`gtest`。

### 6.3 自动化辅助工具

- `ros2-migration-tools`（社区）：扫描 ROS1 包并提示迁移点；
- `roscpp_to_rclcpp` 转换脚本（部分）；
- 生产项目通常需要**人工审查 + 单元测试覆盖**才能上线。

---

## 七、何时不迁移？

- 项目即将下线，无新功能；
- 强依赖只在 ROS1 存在的工具/驱动，且短期不会移植；
- 团队无 DDS/QoS 认知储备，且无安全/实时需求。

否则建议直接选择 **Humble**（22.04 LTS，2027-05 EOL）或 **Jazzy**（24.04 LTS，2029-05 EOL）。Noetic 已于 **2025-05 EOL**。

---

## 八、面试速记

- 一句话差异：**ROS2 = 去中心化（DDS） + 可配置（QoS） + 实时跨平台（RMW + RT + Composition）**
- 迁移核心动作：**Master 移除、catkin → colcon、roscpp → rclcpp、launch.xml → launch.py、param 必须 declare**
- 共存方案：**ros1_bridge**
- 选版本：生产 LTS（Humble/Jazzy）；学习用最新非 LTS 看新特性
