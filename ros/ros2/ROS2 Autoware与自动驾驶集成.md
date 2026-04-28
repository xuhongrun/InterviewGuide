# ROS2 Autoware 与自动驾驶集成

> Autoware 是基于 ROS2 的开源自动驾驶栈。本文聚焦 **Autoware Universe** 模块结构、与 Apollo/CyberRT 的对比、自定义模块接入要点。

---

## 一、Autoware 演进

| 版本 | 备注 |
|------|------|
| Autoware.AI | ROS1 时代，已停止维护 |
| Autoware.Auto | 早期 ROS2 项目，已合并 |
| **Autoware Core / Universe** | 当前主线，ROS2 Humble/Jazzy |

- **Autoware Core**：稳定核心 API；
- **Autoware Universe**：实验性 / 厂商扩展模块。

---

## 二、模块结构

```
sensing  →  localization  →  perception  →  planning  →  control  →  vehicle_interface
   │           │                 │              │           │              │
   ▼           ▼                 ▼              ▼           ▼              ▼
 IMU/GNSS   NDT/EKF        Lidar/Cam DET    BehaviorPL   MPC/PP        CAN/LIN
 LiDAR/Cam  Pose Twist     Tracking/Pred   MotionPL                   Drive-by-Wire
```

| 模块 | 关键节点 |
|------|----------|
| **Sensing** | velodyne / hesai / ouster driver、camera_driver、imu_corrector、gnss_poser |
| **Localization** | `ndt_scan_matcher`（点云配准）、`ekf_localizer`、`pose_initializer` |
| **Perception** | `lidar_centerpoint`（3D 检测）、`euclidean_cluster`、`tensorrt_yolo`、`multi_object_tracker`、`map_based_prediction` |
| **Planning** | `behavior_path_planner`（变道/避障/停车）、`behavior_velocity_planner`（红绿灯/路口）、`obstacle_stop_planner`、`mission_planner`（lanelet2 全局） |
| **Control** | `mpc_lateral_controller`、`pid_longitudinal_controller`、`vehicle_cmd_gate` |
| **Vehicle** | `raw_vehicle_cmd_converter`、CAN 驱动 |
| **Map** | `map_loader`（PCD 点云图 + Lanelet2 语义图） |
| **System** | `system_monitor`、`emergency_handler`、`diagnostic_aggregator` |

---

## 三、Lanelet2 高精地图

Autoware 用 **Lanelet2** 表示道路语义：lane / regulatory_element（红绿灯、停车线、人行道）/ traffic_rules。

```bash
ros2 launch autoware_launch logging_simulator.launch.xml \
    map_path:=/path/to/map vehicle_model:=sample_vehicle \
    sensor_model:=sample_sensor_kit
```

地图组成：
- `pointcloud_map.pcd` — 点云图（NDT 配准）；
- `lanelet2_map.osm` — 语义车道图；
- `map_projector_info.yaml` — 投影信息（MGRS/UTM）。

---

## 四、典型话题

| 话题 | 类型 |
|------|------|
| `/sensing/lidar/concatenated/pointcloud` | sensor_msgs/PointCloud2 |
| `/localization/pose_with_covariance` | geometry_msgs/PoseWithCovarianceStamped |
| `/perception/object_recognition/objects` | autoware_perception_msgs/PredictedObjects |
| `/planning/scenario_planning/trajectory` | autoware_planning_msgs/Trajectory |
| `/control/command/control_cmd` | autoware_control_msgs/Control |
| `/vehicle/status/velocity_status` | autoware_vehicle_msgs/VelocityReport |

---

## 五、自定义模块接入

例：替换 MPC 横向控制器：

1. 实现节点订阅 `/planning/scenario_planning/trajectory`、发布 `/control/command/control_cmd`；
2. 接口类型用 `autoware_*_msgs`；
3. 在 `vehicle_cmd_gate` 之前接入；
4. 修改 launch xml 替换默认 controller。

```cpp
auto sub = node->create_subscription<autoware_planning_msgs::msg::Trajectory>(
    "/planning/scenario_planning/trajectory", rclcpp::QoS(1).best_effort(),
    [&](auto m){ ... });

auto pub = node->create_publisher<autoware_control_msgs::msg::Control>(
    "/control/command/control_cmd", 1);
```

---

## 六、仿真

| 仿真器 | 特点 |
|--------|------|
| **AWSIM** (Unity) | Autoware 官方推荐，传感器仿真好 |
| **CARLA + carla_ros_bridge** | 开源、生态好 |
| **LGSVL Simulator**（已停） | 历史方案 |
| **logging_simulator** | 用录制 bag 重放，用于回归测试 |

```bash
# AWSIM + Autoware 联调
./AWSIM.x86_64 &
ros2 launch autoware_launch e2e_simulator.launch.xml \
    map_path:=/maps/awsim_map vehicle_model:=sample_vehicle \
    sensor_model:=awsim_sensor_kit
```

---

## 七、Autoware vs Apollo CyberRT

| 维度 | Autoware | Apollo |
|------|----------|--------|
| 中间件 | ROS2 (DDS) | CyberRT（Protobuf + 自研 RPC） |
| 通信 | DDS pub/sub + service + action | Topic Channel + Service |
| 语言 | C++ / Python | C++ |
| 调度 | DDS Executor | Scheduler（Choreography / Classic） |
| 模块组织 | Lifecycle Node | Component（DAG） |
| 地图 | Lanelet2 + PCD | Apollo HDMap (proto) |
| 仿真 | AWSIM / CARLA | Apollo Studio / Dreamview |

CyberRT 与 ROS2 桥接：开源项目 `cyber_bridge`、`apollo_ros_bridge`，通过 protobuf ↔ ROS msg 转换。

---

## 八、性能与实时性

要点：
- 感知（CenterPoint / YOLO）跑 GPU；用 TensorRT + zero-copy（CUDA pinned memory）；
- 关键路径（control/planning/localization）跑独立 CPU 核（CPU isolation + chrt）；
- 用 **iceoryx + Cyclone** 做大消息（点云 / 图像）零拷贝；
- 监控用 `autoware_system_msgs`、`diagnostic_aggregator`，异常触发 `emergency_handler`。

---

## 九、安全与失效

- `emergency_handler`：监听各模块 heartbeat / diagnostic，状态恶化触发 MRM（Minimal Risk Maneuver）；
- `vehicle_cmd_gate`：把 control 命令做最后一道限速、限制方向盘角速度、看门狗校验；
- ISO 26262 路径需要进一步 SOTIF 设计。

---

## 十、面试速记

- Autoware = sensing → localization → perception → planning → control → vehicle 流水线
- 当前主线 **Autoware Universe**，ROS2 Humble/Jazzy
- 高精地图 = **PCD（NDT 配准）+ Lanelet2（语义）**
- 控制管道末端 **vehicle_cmd_gate** 做安全裁剪
- 仿真用 **AWSIM** 或 **CARLA**；回归用 logging_simulator + bag
- 与 **Apollo CyberRT** 区别：DDS vs CyberRT、Lanelet2 vs Apollo HDMap
- 大消息生产部署用 **Cyclone + iceoryx 零拷贝**
