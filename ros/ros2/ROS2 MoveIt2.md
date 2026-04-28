# ROS2 MoveIt 2

> MoveIt 2 = ROS2 上的机械臂运动规划框架，基于 OMPL/Pilz/STOMP planner，支持 RViz 拖拽、Cartesian path、Servo 实时遥操作。

---

## 一、架构

```
┌──────────────── MoveIt 2 ────────────────────┐
│                                                │
│  RViz2 MotionPlanning Plugin   <───────┐      │
│        ↓                                │      │
│  move_group (Action Server)            │      │
│        ↓                                │      │
│  ┌──────────────────────────────────┐  │      │
│  │ Planning Pipeline (插件)         │  │      │
│  │   ├── OMPL                       │  │      │
│  │   ├── Pilz Industrial            │  │      │
│  │   ├── STOMP                      │  │      │
│  │   └── CHOMP                      │  │      │
│  └──────────────────────────────────┘  │      │
│        ↓                                │      │
│  Planning Scene (碰撞 / 附着物 / ACM) ─┘      │
│        ↓                                       │
│  Trajectory Execution Manager                  │
│        ↓                                       │
│  FollowJointTrajectory Action ───→ ros2_control│
└────────────────────────────────────────────────┘
```

入口 Action：`/move_action`、`/execute_trajectory`、`/move_group/cartesian_path`。

---

## 二、生成 moveit_config 包

`moveit_setup_assistant` GUI 步骤：

1. 加载 URDF；
2. **Self-Collisions** 自动计算 ACM（Allowed Collision Matrix）；
3. **Virtual Joints**：base 与 world 关系；
4. **Planning Groups**：定义 group（如 `arm`、`gripper`），指定 KinematicChain；
5. **Robot Poses**：预定义姿态（home / ready）；
6. **End Effectors**：把 group 标为末端；
7. **Passive Joints**；
8. **ros2_control**：选择 hardware plugin；
9. **Author Information**；
10. 生成 `<robot>_moveit_config` 包。

产物（关键文件）：

| 文件 | 作用 |
|------|------|
| `config/<robot>.srdf` | 语义机器人描述 |
| `config/kinematics.yaml` | IK 求解器配置 |
| `config/joint_limits.yaml` | 速度/加速度限位 |
| `config/ompl_planning.yaml` | OMPL planner 参数 |
| `config/moveit_controllers.yaml` | controller 映射 |
| `launch/move_group.launch.py` | 启动 move_group |
| `launch/moveit_rviz.launch.py` | RViz + plugin |

---

## 三、SRDF 关键

```xml
<robot name="my_arm">
  <group name="arm">
    <chain base_link="base_link" tip_link="ee_link"/>
  </group>
  <group name="gripper">
    <link name="finger_left"/>
    <link name="finger_right"/>
  </group>
  <group_state name="home" group="arm">
    <joint name="joint1" value="0"/>
    <joint name="joint2" value="-1.57"/>
  </group_state>
  <end_effector name="ee" parent_link="ee_link" group="gripper"/>
  <disable_collisions link1="link1" link2="link2" reason="Adjacent"/>
</robot>
```

---

## 四、编程接口（C++）

```cpp
#include <moveit/move_group_interface/move_group_interface.h>

auto node = std::make_shared<rclcpp::Node>("moveit_demo",
              rclcpp::NodeOptions().automatically_declare_parameters_from_overrides(true));
moveit::planning_interface::MoveGroupInterface group(node, "arm");

geometry_msgs::msg::PoseStamped target;
target.header.frame_id = "base_link";
target.pose.position = ... ;
target.pose.orientation = ...;
group.setPoseTarget(target);

moveit::planning_interface::MoveGroupInterface::Plan plan;
if (group.plan(plan) == moveit::core::MoveItErrorCode::SUCCESS) {
    group.execute(plan);
}

// 关节空间目标
group.setJointValueTarget({0.0, -1.57, 1.57, 0.0, 0.0, 0.0});
group.move();

// Cartesian path
std::vector<geometry_msgs::msg::Pose> waypoints = {p1, p2, p3};
moveit_msgs::msg::RobotTrajectory traj;
double frac = group.computeCartesianPath(waypoints, /*step*/0.01,
                                          /*jump*/0.0, traj);
```

Python（rclpy + `moveit_py`）：
```python
from moveit.planning import MoveItPy
moveit = MoveItPy(node_name="moveit_py")
arm = moveit.get_planning_component("arm")
arm.set_start_state_to_current_state()
arm.set_goal_state(pose_stamped_msg=target, pose_link="ee_link")
plan = arm.plan()
if plan: moveit.execute(plan.trajectory, controllers=[])
```

---

## 五、Planning Scene

```cpp
moveit::planning_interface::PlanningSceneInterface psi;

moveit_msgs::msg::CollisionObject obj;
obj.id = "table";
obj.header.frame_id = "world";
shape_msgs::msg::SolidPrimitive box;
box.type = box.BOX;
box.dimensions = {1.0, 1.0, 0.05};
obj.primitives = {box};
geometry_msgs::msg::Pose pose; pose.position.z = -0.025;
obj.primitive_poses = {pose};
obj.operation = obj.ADD;
psi.applyCollisionObject(obj);

// 附着到末端（pick）
moveit_msgs::msg::AttachedCollisionObject att;
att.link_name = "ee_link";
att.object = obj;
att.object.operation = obj.ADD;
psi.applyAttachedCollisionObject(att);
```

ACM（Allowed Collision Matrix）：编辑哪些 link 对忽略碰撞，避免 self-collision 误判。

---

## 六、Planner 选型

| Planner | 类型 | 特点 |
|---------|------|------|
| **OMPL/RRTConnect** | 采样 | 默认；快但抖 |
| **OMPL/PRM** | 采样 | 多查询 |
| **Pilz LIN/PTP/CIRC** | 解析 | 工业确定性运动 |
| **STOMP** | 优化 | 平滑、避障好，慢 |
| **CHOMP** | 优化 | 与 STOMP 类似 |

`ompl_planning.yaml` 调参：`range`、`projection_evaluator`、`max_states`。

---

## 七、IK 求解器

| 求解器 | 速度 | 鲁棒 |
|--------|------|------|
| KDL（默认） | 慢 | 数值，常失败 |
| **TRAC-IK** | 快 | 数值 + Newton-Raphson 备选 |
| **bio_ik** | 慢 | 启发式 + 自定义代价 |
| **pick_ik** | 快 | 较新，专为 pick-and-place |
| **IKFast** | 极快 | 解析式，需离线生成 |

切换：编辑 `kinematics.yaml`：
```yaml
arm:
  kinematics_solver: trac_ik_kinematics_plugin/TRAC_IKKinematicsPlugin
  kinematics_solver_search_resolution: 0.005
  kinematics_solver_timeout: 0.05
```

---

## 八、MoveIt Servo（实时遥操作）

实时 (1kHz) 把 Twist / JointJog 转换为关节速度，实时避障 + 奇异点保护：

```bash
ros2 launch moveit_servo servo_example.launch.py
ros2 topic pub /servo_node/delta_twist_cmds geometry_msgs/msg/TwistStamped \
    "{header: {frame_id: ee_link}, twist: {linear: {x: 0.05}}}"
```

适用：手柄/VR/visual servoing。

---

## 九、常见坑

| 现象 | 解决 |
|------|------|
| 规划失败 | 增大 `planning_time`、改 planner、检查 IK 求解器、检查碰撞 |
| 执行抖动 | controller PID 没调好 / 轨迹 time scaling 太低 |
| `Trajectory message contains waypoints that are not strictly increasing in time` | 轨迹时间戳乱 / `time_from_start` 不递增 |
| ACM 未排除相邻 link | Setup Assistant 时未跑 self-collision；手动 disable |
| Servo 漂移 | `incoming_command_timeout` 设短；停止时发空 Twist |

---

## 十、面试速记

- MoveIt 2 入口：**move_group Action** + RViz 插件 + `MoveGroupInterface`
- Setup Assistant 生成 `srdf + kinematics.yaml + moveit_controllers.yaml`
- Planner：**OMPL（默认）/ Pilz（工业）/ STOMP（平滑）**
- IK：默认 KDL 不靠谱，**生产换 TRAC-IK / pick_ik / IKFast**
- **Cartesian path**：`computeCartesianPath`，注意 jump_threshold
- **Planning Scene** 控制碰撞物 + ACM；附着物用 `AttachedCollisionObject`
- **MoveIt Servo** 是 ROS2 新增的实时遥操作 / 视觉伺服模块
