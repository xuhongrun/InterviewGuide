# ROS2 Nav2 深入与行为树（BT）

> 在 [ROS2 ros2_control与Nav2生态](ROS2%20ros2_control与Nav2生态.md) 概述基础上深入：BT 自定义、planner/controller 调参、Costmap 高级层、AMCL/SLAM 选型、collision_monitor。

---

## 一、Nav2 完整组件图

```
                  ┌──────────────────┐
                  │ lifecycle_manager│  统一启停
                  └────────┬─────────┘
       ┌──────────────────┼─────────────────────┐
       │                   │                     │
  ┌────▼─────┐ ┌──────────▼──────────┐ ┌────────▼────────┐
  │bt_navigator│ │ planner_server     │ │controller_server│
  │ (BT 主控)  │ │ NavFn/Smac/Theta*  │ │DWB/MPPI/RPP     │
  └────┬───────┘ └──────────┬─────────┘ └────────┬────────┘
       │                    │                     │
       │           ┌────────▼─────────┐           │
       └──────────►│ smoother_server  │◄──────────┘
                   │ Simple/SavGol    │
                   └────────┬─────────┘
                            │
                  ┌─────────▼─────────┐
                  │ velocity_smoother │
                  └─────────┬─────────┘
                            │
                  ┌─────────▼─────────┐
                  │ collision_monitor │  ← /scan, /pointcloud
                  └─────────┬─────────┘
                            ▼ /cmd_vel
                  ┌────────────────────┐
                  │ recoveries_server  │ Spin/BackUp/Wait
                  └────────────────────┘
                            ▲
                            │
                  ┌────────────────────┐
                  │ behavior_server    │
                  └────────────────────┘
```

---

## 二、Action 入口

| Action | 用途 |
|--------|------|
| `/navigate_to_pose` | 单目标导航（最常用） |
| `/navigate_through_poses` | 多 waypoint |
| `/follow_path` | 跟踪给定 path |
| `/compute_path_to_pose` | 仅规划不执行 |
| `/spin` / `/backup` / `/wait` | recovery 行为 |

```bash
ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose \
    "{pose: {header: {frame_id: map}, pose: {position: {x: 1, y: 1}, orientation: {w: 1}}}}"
```

---

## 三、Planner 选型

| Plugin | 算法 | 特点 |
|--------|------|------|
| `nav2_navfn_planner/NavfnPlanner` | Dijkstra（默认） | 快、依赖膨胀 |
| `nav2_smac_planner/SmacPlanner2D` | A*（栅格） | 比 NavFn 平滑 |
| `nav2_smac_planner/SmacPlannerHybrid` | Hybrid-A*（含朝向） | **Ackermann/差速车型，转弯半径约束** |
| `nav2_smac_planner/SmacPlannerLattice` | State Lattice | 更平滑、可加运动学约束 |
| `nav2_theta_star_planner/ThetaStarPlanner` | Theta*（任意角度） | 路径更直 |
| `nav2_straightline_planner/StraightLine` | 直线 | 调试用 |

`planner_server` 配置：
```yaml
planner_server:
  ros__parameters:
    expected_planner_frequency: 1.0
    planner_plugins: ["GridBased"]
    GridBased:
      plugin: "nav2_smac_planner/SmacPlannerHybrid"
      tolerance: 0.5
      motion_model_for_search: "DUBIN"      # or "REEDS_SHEPP"
      angle_quantization_bins: 72
      minimum_turning_radius: 0.4
      reverse_penalty: 2.0
```

---

## 四、Controller 选型

| Plugin | 算法 |
|--------|------|
| `dwb_core::DWBLocalPlanner` | DWA 重写版（默认） |
| `nav2_mppi_controller::MPPIController` | **采样 MPPI**（轨迹优化） |
| `nav2_regulated_pure_pursuit_controller/RegulatedPurePursuitController` | **RPP**（差速最佳） |
| `nav2_rotation_shim_controller/RotationShimController` | 起步先转向再前进 |

`controller_server` 配置：
```yaml
controller_server:
  ros__parameters:
    controller_frequency: 20.0
    FollowPath:
      plugin: "nav2_mppi_controller::MPPIController"
      time_steps: 56
      model_dt: 0.05
      vx_max: 0.5
      vx_min: -0.35
      wz_max: 1.9
      ax_max: 3.0
      critics: ["ConstraintCritic", "ObstaclesCritic", "GoalCritic",
                "GoalAngleCritic", "PathFollowCritic"]
```

MPPI 调参口诀：先 `time_steps × model_dt = 视野`，然后 `critics` 权重决定行为偏好。

---

## 五、Costmap 高级层

```yaml
local_costmap:
  ros__parameters:
    update_frequency: 10.0
    publish_frequency: 5.0
    rolling_window: true
    width: 6
    height: 6
    resolution: 0.05
    plugins: ["voxel_layer", "inflation_layer"]
    voxel_layer:
      plugin: "nav2_costmap_2d::VoxelLayer"
      observation_sources: scan
      scan: {topic: /scan, sensor_frame: laser, data_type: LaserScan, marking: true, clearing: true}
    inflation_layer:
      plugin: "nav2_costmap_2d::InflationLayer"
      inflation_radius: 0.55
      cost_scaling_factor: 5.0
```

特殊层：
- `keepout_filter`：禁入区（用 mask map 描述）；
- `speed_filter`：限速区；
- `binary_filter`：自定义二值条件。

```yaml
keepout_filter:
  plugin: "nav2_costmap_2d::KeepoutFilter"
  enabled: True
  filter_info_topic: "/costmap_filter_info"
```

---

## 六、AMCL / SLAM 切换

定位（已有地图）：
```yaml
amcl:
  ros__parameters:
    min_particles: 500
    max_particles: 2000
    laser_model_type: likelihood_field
    odom_frame_id: odom
    base_frame_id: base_link
    global_frame_id: map
```

SLAM 在线建图（slam_toolbox）：
```bash
ros2 launch slam_toolbox online_async_launch.py
ros2 service call /slam_toolbox/save_map slam_toolbox/srv/SaveMap \
    "{name: {data: my_map}}"
```

切换：Nav2 启动时不要同时拉起 amcl + slam_toolbox。

---

## 七、行为树（BT）

Nav2 用 [behaviortree.cpp](https://www.behaviortree.dev/) 调度。BT XML：

```xml
<root main_tree_to_execute="MainTree">
 <BehaviorTree ID="MainTree">
   <RecoveryNode number_of_retries="6" name="NavigateRecovery">
     <PipelineSequence name="NavWithReplanning">
       <RateController hz="1.0">
         <RecoveryNode number_of_retries="1" name="ComputePathToPose">
           <ComputePathToPose goal="{goal}" path="{path}" planner_id="GridBased"/>
           <ClearEntireCostmap name="ClearGlobal"
                               service_name="global_costmap/clear_entirely_global_costmap"/>
         </RecoveryNode>
       </RateController>
       <RecoveryNode number_of_retries="1" name="FollowPath">
         <FollowPath path="{path}" controller_id="FollowPath"/>
         <ClearEntireCostmap service_name="local_costmap/clear_entirely_local_costmap"/>
       </RecoveryNode>
     </PipelineSequence>
     <ReactiveFallback name="RecoveryFallback">
       <GoalUpdated/>
       <RoundRobin name="Recoveries">
         <Spin spin_dist="1.57"/>
         <Wait wait_duration="5"/>
         <BackUp backup_dist="0.30" backup_speed="0.05"/>
       </RoundRobin>
     </ReactiveFallback>
   </RecoveryNode>
 </BehaviorTree>
</root>
```

### 自定义 BT 节点

```cpp
#include <behaviortree_cpp/action_node.h>

class CheckBattery : public BT::SyncActionNode {
public:
    CheckBattery(const std::string& name, const BT::NodeConfig& cfg)
        : SyncActionNode(name, cfg) {}
    static BT::PortsList providedPorts() {
        return { BT::InputPort<double>("min_voltage") };
    }
    BT::NodeStatus tick() override {
        double min_v; getInput("min_voltage", min_v);
        return battery_ > min_v ? BT::NodeStatus::SUCCESS : BT::NodeStatus::FAILURE;
    }
private:
    double battery_ = 12.0;
};

// 注册
BT_REGISTER_NODES(factory) {
    factory.registerNodeType<CheckBattery>("CheckBattery");
}
```

`bt_navigator` 通过 plugin 加载注册库。

### Groot

`Groot2` 是图形化 BT 编辑器 + 实时调试，能动态显示节点状态（running/success/failure）。

---

## 八、collision_monitor & velocity_smoother

`collision_monitor`：在 `/cmd_vel` 出口加一道**安全减速 / 急停**：

```yaml
collision_monitor:
  ros__parameters:
    polygons: ["FootprintApproach", "PolygonStop"]
    PolygonStop:
      type: "polygon"
      points: "[[0.4, 0.3], [0.4, -0.3], [-0.1, -0.3], [-0.1, 0.3]]"
      action_type: "stop"
      max_points: 3
      visualize: true
```

`velocity_smoother`：限制 `/cmd_vel` 的加速度，避免硬件突变。

---

## 九、常见坑

| 现象 | 排查 |
|------|------|
| Goal 后机器人不动 | lifecycle 没激活 / `/cmd_vel` 没下游 / collision_monitor 在停 |
| 路径绕远 | inflation 太大；改 cost_scaling_factor / inflation_radius |
| 转弯卡 | controller 与车型不匹配；差速用 RPP，Ackermann 用 SmacHybrid |
| Recovery 频繁触发 | costmap 没及时清理 / 障碍残留；调 `obstacle_layer` clearing |
| 慢速漂移 | AMCL 粒子退化；增大 `update_min_d/a` 触发条件 |

---

## 十、面试速记

- Nav2 入口 Action：**`/navigate_to_pose`**
- 全部组件都是 **Lifecycle Node**，由 `lifecycle_manager` 编排
- Planner 选型：**Smac Hybrid（车型）/ NavFn（默认）/ Theta\***
- Controller 选型：**MPPI（采样）/ RPP（差速）/ DWB（默认）**
- Costmap 加 `keepout_filter` / `speed_filter` 实现规则区
- BT 用 behaviortree.cpp，可自定义节点 + Groot2 调试
- 安全：**collision_monitor + velocity_smoother**
