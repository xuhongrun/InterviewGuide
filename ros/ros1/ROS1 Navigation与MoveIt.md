# ROS1 Navigation 与 MoveIt1

> 两大经典框架：**Navigation Stack（move_base）** 用于移动底盘自主导航；**MoveIt 1** 用于机械臂运动规划。

---

## 一、Navigation Stack 总览

```
┌──────────── move_base (核心 Action Server) ────────────┐
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Global       │  │ Local        │  │ Recovery     │  │
│  │ Planner      │  │ Planner      │  │ Behaviors    │  │
│  │ (NavFn/      │  │ (DWA/TEB/    │  │ (rotate/     │  │
│  │  global_     │  │  base_local_ │  │  clear_      │  │
│  │  planner)    │  │  planner)    │  │  costmap)    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                          │
│  ┌────────────────────┐  ┌────────────────────┐         │
│  │ global_costmap     │  │ local_costmap      │         │
│  │  (static + 障碍)    │  │  (rolling window)  │         │
│  └────────────────────┘  └────────────────────┘         │
└──────────────────────────────────────────────────────────┘
        ↑                                    ↑
    /map (map_server)               sensor: /scan, /odom
        ↑
    AMCL (定位)
```

入口 Action：`/move_base` 接收 `geometry_msgs/PoseStamped` 目标，输出 `/cmd_vel`。

---

## 二、关键节点

| 节点 | 用途 |
|------|------|
| `map_server` | 加载/发布 `/map` 静态栅格 |
| `amcl` | 蒙特卡洛定位，订阅 `/scan` + `/map` 输出 `map → odom` |
| `move_base` | 规划主循环 |
| `gmapping` / `slam_toolbox` / `karto` | 同时建图（SLAM 模式时替代 amcl + map_server） |
| `global_planner` | A*/Dijkstra |
| `dwa_local_planner` / `teb_local_planner` | DWA / 时间弹性带 |
| `costmap_2d` | 多层栅格地图 |

---

## 三、Costmap 层（plugin）

```yaml
plugins:
  - {name: static_layer,    type: "costmap_2d::StaticLayer"}
  - {name: obstacle_layer,  type: "costmap_2d::ObstacleLayer"}
  - {name: voxel_layer,     type: "costmap_2d::VoxelLayer"}
  - {name: inflation_layer, type: "costmap_2d::InflationLayer"}
```

- **static_layer**：来自 `/map`；
- **obstacle_layer**：激光实时障碍；
- **voxel_layer**：3D 体素，处理悬空障碍；
- **inflation_layer**：膨胀（按机器人半径 + 安全余量）。

`inflation_radius` 与 `cost_scaling_factor` 是最关键调参点。

---

## 四、本地规划器对比

| Planner | 算法 | 优势 | 不足 |
|---------|------|------|------|
| **DWA** | 动态窗口采样 | 简单稳定，调参少 | 在窄通道、动态障碍下表现一般 |
| **TEB** | 时间弹性带优化 | 平滑、可处理 Ackermann/差速/全向 | 调参多，对地图敏感 |
| **MPC**（自定义） | 滚动优化 | 可加复杂约束 | 算力 / 工程成本高 |

---

## 五、典型 launch 流程

```xml
<launch>
  <!-- 静态地图 + 定位 -->
  <node pkg="map_server" type="map_server" name="map" args="$(find my_pkg)/maps/map.yaml"/>
  <node pkg="amcl" type="amcl" name="amcl">
    <rosparam file="$(find my_pkg)/config/amcl.yaml"/>
  </node>

  <!-- move_base + 参数 -->
  <node pkg="move_base" type="move_base" name="move_base" output="screen">
    <rosparam file="$(find my_pkg)/config/costmap_common.yaml" ns="global_costmap"/>
    <rosparam file="$(find my_pkg)/config/costmap_common.yaml" ns="local_costmap"/>
    <rosparam file="$(find my_pkg)/config/global_costmap.yaml"/>
    <rosparam file="$(find my_pkg)/config/local_costmap.yaml"/>
    <rosparam file="$(find my_pkg)/config/dwa.yaml"/>
    <param name="base_global_planner" value="navfn/NavfnROS"/>
    <param name="base_local_planner"  value="dwa_local_planner/DWAPlannerROS"/>
  </node>
</launch>
```

发目标：

```bash
rostopic pub /move_base_simple/goal geometry_msgs/PoseStamped \
    "{header: {frame_id: map}, pose: {position: {x: 1, y: 1}, orientation: {w: 1}}}"
```

---

## 六、调参检查清单

| 参数 | 含义 | 经验值 |
|------|------|--------|
| `controller_frequency` | move_base 主频 | 5–20 Hz |
| `inflation_radius` | 膨胀半径 | 略大于机器人半径 + 余量 |
| `cost_scaling_factor` | 膨胀衰减 | 5–10 |
| `xy_goal_tolerance` | 终点容差 | 0.1–0.3 m |
| `yaw_goal_tolerance` | 角度容差 | 0.1–0.3 rad |
| `min_vel_x` / `max_vel_x` | 线速 | 由底盘决定 |
| `acc_lim_x` / `acc_lim_th` | 加速度 | 由动力学决定 |
| `sim_time`（DWA） | 滚动窗时长 | 1–3 s |
| `path_distance_bias` | 跟随路径偏好 | 增大→更靠近全局路径 |
| `goal_distance_bias` | 趋向目标偏好 | 增大→更想直奔目标 |
| `occdist_scale` | 避障权重 | 增大→更躲障碍 |

---

## 七、SLAM 建图

```bash
roslaunch slam_toolbox online_async_launch.py
# 或
rosrun gmapping slam_gmapping scan:=/scan _delta:=0.05

# 结束后保存
rosrun map_server map_saver -f my_map
```

`slam_toolbox`（推荐）支持 lifelong / serialization / loop closure，质量高于 gmapping。

---

## 八、MoveIt 1 概览

```
┌─────── MoveIt! ───────┐
│  RViz Plugin          │   ← 用户拖拽规划
│   ↓                    │
│  move_group (Action)  │
│   ↓                    │
│  Planning Pipeline    │
│   ├ OMPL Planner      │
│   ├ Pilz Industrial   │
│   ├ STOMP / CHOMP     │
│   ↓                    │
│  Planning Scene       │   ← 碰撞、附着物
│   ↓                    │
│  Trajectory Execution │
│   └→ FollowJointTrajectory Action → ros_control
└────────────────────────┘
```

### 8.1 配置

`moveit_setup_assistant` GUI：从 URDF 生成 `<robot>_moveit_config` 包，含：
- SRDF（语义描述：planning groups、虚关节、碰撞矩阵）
- kinematics.yaml（IK 求解器：KDL / TRAC-IK / IKFast）
- joint_limits.yaml
- ompl_planning.yaml

### 8.2 编程接口（C++）

```cpp
#include <moveit/move_group_interface/move_group_interface.h>

moveit::planning_interface::MoveGroupInterface group("arm");
group.setPoseTarget(target_pose);

moveit::planning_interface::MoveGroupInterface::Plan plan;
if (group.plan(plan) == moveit::core::MoveItErrorCode::SUCCESS) {
    group.execute(plan);
}

// Cartesian path
std::vector<geometry_msgs::Pose> waypoints = {...};
moveit_msgs::RobotTrajectory traj;
double frac = group.computeCartesianPath(waypoints, 0.01, 0.0, traj);
```

### 8.3 Planning Scene

```cpp
moveit::planning_interface::PlanningSceneInterface psi;
moveit_msgs::CollisionObject obj;
obj.id = "table";
obj.header.frame_id = "world";
shape_msgs::SolidPrimitive box;
box.type = box.BOX; box.dimensions = {1, 1, 0.05};
obj.primitives = {box};
obj.primitive_poses = {pose};
obj.operation = obj.ADD;
psi.applyCollisionObject(obj);

// 附着到末端
group.attachObject("table", "ee_link");
```

### 8.4 Planner 选型

| Planner | 特点 |
|---------|------|
| **OMPL/RRTConnect** | 默认，快速找解 |
| **OMPL/PRM** | 概率路线图，多查询 |
| **Pilz LIN/PTP/CIRC** | 工业直线/点对点/圆弧（确定性） |
| **STOMP / CHOMP** | 轨迹优化，平滑性好 |

### 8.5 IK 求解器

| 求解器 | 特点 |
|--------|------|
| KDL（默认） | 数值法，慢且常失败 |
| **TRAC-IK** | 数值法但更鲁棒，**推荐替换默认** |
| **IKFast** | 解析法，最快，需为特定机器人离线生成 |
| `bio_ik` | 启发式优化，可加自定义代价 |

修改 `kinematics.yaml`：
```yaml
arm:
  kinematics_solver: trac_ik_kinematics_plugin/TRAC_IKKinematicsPlugin
  kinematics_solver_search_resolution: 0.005
  kinematics_solver_timeout: 0.05
```

---

## 九、面试速记

- 导航三件套：**map_server + amcl + move_base**
- Costmap 层：static / obstacle / voxel / inflation；调 `inflation_radius`
- 局部规划器：**DWA**（默认）vs **TEB**（更平滑）
- SLAM 推荐 **slam_toolbox**（替代 gmapping）
- MoveIt 入口：**move_group Action + RViz 插件**
- IK 默认 KDL 慢且失败率高，**生产建议 TRAC-IK 或 IKFast**
- Planner：OMPL（通用）/ Pilz（工业）/ STOMP（平滑）
- ROS2 中演化为 **Nav2 + MoveIt 2**，思想一脉相承
