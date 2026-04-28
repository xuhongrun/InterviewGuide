# ROS2 ros2_control 与 Navigation2 生态

> 两大核心生态包：**ros2_control**（实时硬件抽象 + 控制器框架）与 **Navigation2 / Nav2**（自主导航栈）。本篇梳理架构与关键扩展点。

---

## 一、ros2_control 概览

ros2_control 是 ROS1 `ros_control` 的重构版，提供：
- **HardwareInterface** 抽象（统一驱动接口）；
- **Controller Manager** 调度（实时循环 read → update → write）；
- **Controller 插件**（位置/速度/力矩/JointTrajectory/Admittance...）；
- **资源仲裁**（多个控制器申请同一关节时按状态机切换）。

### 1.1 架构

```
┌──────────────── controller_manager (一个进程) ───────────────┐
│   ┌─────────────────────────────────────────────────────────┐│
│   │  Real-time loop (典型 1kHz, SCHED_FIFO)                  ││
│   │   for each cycle:                                        ││
│   │     1. hw->read(time, period)                            ││
│   │     2. for each active controller: c->update(time, dt)   ││
│   │     3. hw->write(time, period)                           ││
│   └─────────────────────────────────────────────────────────┘│
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│   │ JointTraj... │  │ DiffDrive    │  │ Admittance   │      │
│   │ Controller   │  │ Controller   │  │ Controller   │      │
│   └──────────────┘  └──────────────┘  └──────────────┘      │
│   ┌─────────────────────────────────────────────────────────┐│
│   │  Hardware Interface (plugin)                             ││
│   │   ├─ state_interfaces: position/velocity/effort          ││
│   │   └─ command_interfaces: position/velocity/effort        ││
│   └─────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
                  ↓ 真实驱动 (CAN/EtherCAT/USB/SPI...)
```

### 1.2 URDF + ros2_control 标签

```xml
<robot name="my_robot">
  <ros2_control name="MySystem" type="system">
    <hardware>
      <plugin>my_pkg/MyHardwareInterface</plugin>
      <param name="device">/dev/ttyUSB0</param>
    </hardware>
    <joint name="joint1">
      <command_interface name="position"/>
      <state_interface name="position"/>
      <state_interface name="velocity"/>
    </joint>
  </ros2_control>
</robot>
```

### 1.3 自定义 HardwareInterface（C++）

```cpp
#include "hardware_interface/system_interface.hpp"

class MyHW : public hardware_interface::SystemInterface {
public:
    CallbackReturn on_init(const hardware_interface::HardwareInfo& info) override {
        // 解析 info.joints, info.hardware_parameters
        positions_.resize(info.joints.size(), 0.0);
        commands_.resize(info.joints.size(), 0.0);
        return CallbackReturn::SUCCESS;
    }
    std::vector<hardware_interface::StateInterface> export_state_interfaces() override {
        std::vector<hardware_interface::StateInterface> ifs;
        for (size_t i = 0; i < info_.joints.size(); ++i)
            ifs.emplace_back(info_.joints[i].name, "position", &positions_[i]);
        return ifs;
    }
    std::vector<hardware_interface::CommandInterface> export_command_interfaces() override {
        std::vector<hardware_interface::CommandInterface> ifs;
        for (size_t i = 0; i < info_.joints.size(); ++i)
            ifs.emplace_back(info_.joints[i].name, "position", &commands_[i]);
        return ifs;
    }
    return_type read(const rclcpp::Time&, const rclcpp::Duration&) override {
        // 从硬件读 positions_
        return return_type::OK;
    }
    return_type write(const rclcpp::Time&, const rclcpp::Duration&) override {
        // 把 commands_ 下发硬件
        return return_type::OK;
    }
private:
    std::vector<double> positions_, commands_;
};
PLUGINLIB_EXPORT_CLASS(my_pkg::MyHW, hardware_interface::SystemInterface)
```

### 1.4 启动

```python
# launch
controller_manager_node = Node(
    package="controller_manager",
    executable="ros2_control_node",
    parameters=[robot_description, controllers_yaml],
    output="screen",
)
```

`controllers.yaml`：
```yaml
controller_manager:
  ros__parameters:
    update_rate: 1000             # Hz
    joint_state_broadcaster:
      type: joint_state_broadcaster/JointStateBroadcaster
    arm_controller:
      type: joint_trajectory_controller/JointTrajectoryController

arm_controller:
  ros__parameters:
    joints: [joint1, joint2, joint3]
    command_interfaces: [position]
    state_interfaces: [position, velocity]
```

激活：
```bash
ros2 control list_hardware_interfaces
ros2 control list_controllers
ros2 control load_controller --set-state active arm_controller
```

### 1.5 实时性

- `ros2_control_node` 用 **StaticSingleThreadedExecutor** + **SCHED_FIFO** 跑控制周期；
- 推荐启用 `mlockall` + 预分配；
- 控制器插件 `update()` 必须**实时安全**（no malloc / no log / no lock）。

---

## 二、Navigation2 (Nav2) 概览

Nav2 是 ROS1 `move_base` 的重构版，行为树驱动、模块化、Lifecycle 化。

### 2.1 架构

```
┌──────────── BT Navigator ────────────┐
│   (behaviortree.cpp 行为树调度)        │
└───┬─────────┬──────────┬──────────────┘
    │         │          │
   Goal     Recovery   Planning
    │         │          │
    ▼         ▼          ▼
 ┌─────────┐ ┌─────────┐ ┌─────────────┐
 │ Planner │ │ Recover │ │ Controller  │
 │ Server  │ │ Server  │ │ Server      │
 │(NavFn/  │ │(spin/   │ │(DWB/MPPI/   │
 │ Smac)   │ │ backup) │ │ Reg.Pure   │
 │         │ │         │ │ Pursuit)    │
 └────┬────┘ └────┬────┘ └─────┬───────┘
      │           │            │
      └───────────┼────────────┘
                  ▼
       ┌────────────────────┐
       │ costmap_2d         │
       │  (global + local)  │
       │  + 多层 plugin      │
       │   - static layer   │
       │   - obstacle layer │
       │   - inflation layer│
       │   - voxel layer    │
       └────────┬───────────┘
                │ TF + sensors
                ▼
       ┌────────────────────┐
       │ AMCL / SLAM        │
       │ /map               │
       └────────────────────┘
                │
       ┌────────▼───────────┐
       │ lifecycle_manager  │  统一 configure/activate/cleanup
       └────────────────────┘
```

### 2.2 关键服务器（均为 Lifecycle Node）

| 服务器 | 职责 | 默认实现 |
|--------|------|----------|
| `bt_navigator` | 行为树调度，Action 入口 `navigate_to_pose` | BehaviorTree.CPP |
| `planner_server` | 全局路径规划 | NavFn / SmacPlanner / Theta* |
| `controller_server` | 局部控制器 | DWB / MPPI / RegulatedPurePursuit |
| `recoveries_server` | 卡死恢复 | spin / backup / wait |
| `smoother_server` | 轨迹平滑 | Simple/Constrained/SavGol |
| `velocity_smoother` | `/cmd_vel` 平滑 |  |
| `collision_monitor` | 安全减速/急停 |  |
| `lifecycle_manager` | 统一管理上述节点的状态 |  |

### 2.3 行为树（BT）

```xml
<root main_tree_to_execute="MainTree">
 <BehaviorTree ID="MainTree">
   <RecoveryNode number_of_retries="6" name="NavigateRecovery">
     <PipelineSequence name="NavigateWithReplanning">
       <RateController hz="1.0">
         <ComputePathToPose goal="{goal}" path="{path}"/>
       </RateController>
       <FollowPath path="{path}" controller_id="FollowPath"/>
     </PipelineSequence>
     <ReactiveFallback name="RecoveryFallback">
       <Spin spin_dist="1.57"/>
       <BackUp backup_dist="0.30" backup_speed="0.05"/>
     </ReactiveFallback>
   </RecoveryNode>
 </BehaviorTree>
</root>
```

可通过自定义 BT Node 与 Plugin 扩展决策逻辑。

### 2.4 Costmap 层（plugin 化）

| 层 | 用途 |
|----|------|
| `static_layer` | 来自 `/map` 的不可变障碍 |
| `obstacle_layer` | 激光/超声实时障碍 |
| `voxel_layer` | 3D 体素，处理悬空障碍 |
| `inflation_layer` | 膨胀，给机器人留余量 |
| `keepout_filter` / `speed_filter` | Map 区域规则 |

### 2.5 启动

```bash
ros2 launch nav2_bringup tb3_simulation_launch.py
ros2 launch nav2_bringup bringup_launch.py \
    map:=$PWD/map.yaml use_sim_time:=False
```

激活生命周期：
```bash
ros2 service call /lifecycle_manager_navigation/manage_nodes \
    nav2_msgs/srv/ManageLifecycleNodes "{command: 1}"   # 1=STARTUP
```

---

## 三、其他重要生态

| 项目 | 用途 |
|------|------|
| **MoveIt 2** | 机械臂运动规划（OMPL / Pilz / STOMP） |
| **rosbag2** | bag 录制/回放（mcap/db3） |
| **tf2** | 坐标系树（已并入核心） |
| **diagnostic_updater** | 节点诊断聚合，发布 `/diagnostics` |
| **rqt** | GUI 集合 |
| **rviz2** | 3D 可视化 |
| **gazebo / ignition** | 物理仿真（gz garden / harmonic） |
| **autoware** | 自动驾驶完整栈 |
| **slam_toolbox / cartographer** | 2D/3D SLAM |

---

## 四、面试速记

- **ros2_control = 实时 read/update/write 循环 + 插件化 Controller + HardwareInterface**
- 控制器频率 typical **1kHz**，`update()` 必须实时安全
- **Nav2 = BT 调度 + Lifecycle Server + plugin（Planner / Controller / Recovery）+ Costmap 层**
- Nav2 入口 Action：`/navigate_to_pose`（也支持 `navigate_through_poses`）
- 启动 Nav2 必须**激活 lifecycle_manager**
- 局部规划器选型：DWB（默认）/ MPPI（采样优化）/ RegulatedPurePursuit（差速底盘）
