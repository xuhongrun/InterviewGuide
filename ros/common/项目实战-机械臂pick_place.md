# 项目实战：机械臂 Pick-and-Place

> 6/7 自由度机械臂的端到端 pick-and-place：URDF → ros2_control → MoveIt 2 → 视觉抓取检测 → 实机部署。

---

## 一、目标与硬件

- 6-DoF 协作臂（如 UR5e / Franka / 大象 / 节卡）；
- 二指夹爪（Robotiq 2F-85 / 自研 IO 夹爪）；
- RGB-D 相机 eye-in-hand 或 eye-to-hand（RealSense D435）；
- F/T 力传感器（ATI 等，用于装配可选）；
- 控制频率 ≥ 250 Hz。

---

## 二、目录结构

```
my_arm/
├── my_arm_description/        # URDF + meshes
├── my_arm_moveit_config/      # MoveIt Setup Assistant 生成
├── my_arm_hw/                 # ros2_control HardwareInterface
├── my_arm_perception/         # 抓取检测 / 标定
├── my_arm_pick_place/         # 状态机 / 任务编排
├── my_arm_grasp_msgs/         # 自定义消息
└── docker/
```

---

## 三、URDF 与 ros2_control

```xml
<ros2_control name="ArmSystem" type="system">
  <hardware><plugin>my_arm_hw/MyArmHW</plugin></hardware>
  <xacro:macro name="arm_joint" params="name">
    <joint name="${name}">
      <command_interface name="position"/>
      <state_interface name="position"/>
      <state_interface name="velocity"/>
      <state_interface name="effort"/>
    </joint>
  </xacro:macro>
  <xacro:arm_joint name="joint1"/>
  ...
  <xacro:arm_joint name="joint6"/>
</ros2_control>

<ros2_control name="GripperSystem" type="system">
  <hardware><plugin>my_arm_hw/GripperHW</plugin></hardware>
  <joint name="finger_joint">
    <command_interface name="position"/>
    <state_interface name="position"/>
  </joint>
</ros2_control>
```

`controllers.yaml`：
```yaml
controller_manager:
  ros__parameters:
    update_rate: 250
    arm_controller:    { type: joint_trajectory_controller/JointTrajectoryController }
    gripper_controller:{ type: position_controllers/GripperActionController }

arm_controller:
  ros__parameters:
    joints: [joint1, joint2, joint3, joint4, joint5, joint6]
    command_interfaces: [position]
    state_interfaces:   [position, velocity]
    state_publish_rate: 50.0
    action_monitor_rate: 20.0
    constraints:
      stopped_velocity_tolerance: 0.01
      goal_time: 0.5

gripper_controller:
  ros__parameters:
    joint: finger_joint
    action_monitor_rate: 20.0
    goal_tolerance: 0.005
```

---

## 四、MoveIt Setup Assistant

要点：
- self-collision 跑 ≥ 10000 次；
- planning group：`arm`（chain base→ee）+ `gripper`；
- `home`、`ready`、`pre_grasp` 预定义姿态；
- end_effector：gripper group + parent_link = `ee_link`；
- ros2_control 选自定义 plugin；
- IK 求解器换 **TRAC-IK**；
- 输出 `my_arm_moveit_config` 包。

---

## 五、视觉 → 抓取位姿

### 5.1 手眼标定

`easy_handeye2`（ROS2 移植版）：
1. 在末端贴标定板（aruco / charuco）；
2. 录制 N 组 (T_base_ee, T_cam_marker)；
3. 求解 AX = XB → 得到 T_ee_cam（eye-in-hand）或 T_base_cam（eye-to-hand）。

发布 static_transform_publisher 让 TF 包含相机系。

### 5.2 抓取检测

简单几何：物体 pose 来自标记 / 模板匹配。

学习方法：
- **GraspNet** / **Contact-GraspNet**（开源，在点云上回归 6-DoF 抓取候选）；
- **DexNet 2.0**（Berkeley）；
- 自训练 YOLO 物体检测 + 模板配准。

输出 `geometry_msgs/PoseStamped`（grasp_pose），转到 base 系。

---

## 六、Pick-and-Place 状态机

经典流程：
```
HOME ─→ MOVE_TO_PRE_GRASP ─→ APPROACH ─→ CLOSE_GRIPPER ─→ LIFT ─→
        TRANSPORT ─→ PRE_PLACE ─→ PLACE_DOWN ─→ OPEN_GRIPPER ─→
        RETREAT ─→ HOME
```

### 6.1 用 MoveIt MoveGroupInterface

```cpp
auto group = MoveGroupInterface(node, "arm");
group.setPlanningTime(2.0);
group.setNumPlanningAttempts(5);
group.setMaxVelocityScalingFactor(0.3);

// 1. Pre-grasp
target = grasp_pose;
target.pose.position.z += 0.10;
group.setPoseTarget(target);
group.move();

// 2. Approach (Cartesian)
std::vector<Pose> wpts = {grasp_pose};
RobotTrajectory traj;
group.computeCartesianPath(wpts, 0.005, 0.0, traj);
group.execute(traj);

// 3. Close gripper (Action client)
gripper_client.send_goal({position: 0.0});

// 4. Attach in planning scene
moveit_msgs::AttachedCollisionObject att; ...
psi.applyAttachedCollisionObject(att);

// 5. Lift
target = grasp_pose; target.pose.position.z += 0.15;
group.setPoseTarget(target); group.move();

// 6. Move to place pose ...
```

### 6.2 用 BehaviorTree.CPP 编排

```xml
<Sequence name="PickPlace">
  <SubTree ID="Pick" target="{grasp_pose}"/>
  <SubTree ID="Move" target="{place_pose}"/>
  <SubTree ID="Place"/>
</Sequence>
```

每个 SubTree 内含 `MoveTo`、`OpenGripper` 等自定义节点。

---

## 七、关键技巧

| 问题 | 处理 |
|------|------|
| Cartesian path fraction < 1 | 增 step、减抖动；ee_link 与碰撞体冲突要 ACM |
| IK 失败 | 换 TRAC-IK；放宽 tolerance；调 grasp 朝向 |
| 规划失败 | 增加 planning_time，换 STOMP，把 obstacle 简化 |
| 抓取打滑 | 力闭环 / 增加摩擦面 / 视觉反馈纠正 |
| 工具碰撞 | Planning Scene 中加 attached object，正确指定形状 |
| 抖动 | controller PID 没调好 / 轨迹时间太短 |

---

## 八、力控 / 装配（进阶）

引入 `admittance_controller`（ros2_control 链式）：
- 输入：F/T 传感器 + 期望位姿；
- 输出：joint position；
- 插孔 / 装配场景把 K（刚度）调小，让末端跟随接触力。

参考 [ROS2 ros2_control进阶](../ros2/ROS2%20ros2_control进阶.md#六admittance--impedance柔顺控制)。

---

## 九、仿真验证（推荐先仿后实）

```bash
# Gazebo Sim + gz_ros2_control
ros2 launch my_arm_bringup gz_sim.launch.py
# MoveIt
ros2 launch my_arm_moveit_config moveit.launch.py use_sim_time:=true
# 跑 demo
ros2 run my_arm_pick_place demo
```

仿真坑：
- URDF 惯量必须正确，否则末端飘；
- 夹爪触点磁性 / mimic joint 设置；
- 仿真 time vs wall time 比例；
- 仿真不能完全预测真实接触动力学，最终须实机调试。

---

## 十、安全 & 部署

- 急停硬件：双通道继电器，断电使能；
- 软件急停：`/cancel_all` 服务 + 速度限位；
- Joint 限位 / 速度限位 / 软限位三层；
- 工作空间 collision objects（笼子 / 桌面 / 工件）；
- 操作员 GUI：dashboard（jog / teach pendant / 状态显示）；
- 维护：日志 mcap、关节负载监控、电流过流告警。

---

## 十一、面试讲法

围绕「**完整闭环**」叙述：
1. **目标**：物料拣选生产线 / 装配；
2. **架构**：URDF + ros2_control + MoveIt 2 + 视觉抓取 + 状态机；
3. **关键技术**：TRAC-IK / Cartesian path / handeye / GraspNet / admittance；
4. **难点**：抓取成功率、规划失败重试、力控装配、节拍优化；
5. **量化**：单次抓取 N 秒、成功率 > X%、节拍 Y 秒；
6. **改进**：换 STOMP / 用 MoveIt Servo 实时遥操作 / 加力控柔顺 / RL 优化。

---

## 十二、面试速记

- URDF + `<ros2_control>` + `joint_trajectory_controller` 是机械臂标配
- IK 默认 KDL 不稳，**生产换 TRAC-IK / pick_ik / IKFast**
- 抓取流：**预抓取 → Cartesian 接近 → 闭爪 → attach 到 scene → 抬起**
- 手眼标定 **AX = XB**（`easy_handeye2`），eye-in-hand vs eye-to-hand
- 力控装配 **admittance_controller**（M/D/K）
- 仿真先行（Gazebo Sim + gz_ros2_control），再实机
- 安全三层：**硬件急停 + 软急停 + 关节/速度软限位**
