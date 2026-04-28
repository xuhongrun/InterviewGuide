# ROS2 SLAM 工具链

> 主流 SLAM 工具：**slam_toolbox**（2D 激光，推荐）、**Cartographer**（2D/3D 激光）、**RTAB-Map**（视觉/激光融合）、**Fast-LIO / LIO-SAM**（激光惯导）。

---

## 一、SLAM 选型矩阵

| 工具 | 传感器 | 维度 | 优势 | 劣势 |
|------|--------|------|------|------|
| **slam_toolbox** | 2D LiDAR | 2D | Lifelong，序列化，回环鲁棒，ROS2 一等公民 | 仅 2D |
| **Cartographer** | 2D/3D LiDAR + IMU | 2D/3D | 谷歌出品，回环优秀 | 维护放缓，配置复杂 |
| **RTAB-Map** | RGB-D / 双目 / LiDAR | 3D | 多传感器融合，丰富可视化 | 性能开销大 |
| **ORB-SLAM3** | 单目 / 双目 / RGB-D | 3D | 视觉强，IMU 融合 | 商用授权约束 |
| **Fast-LIO 2** | LiDAR + IMU | 3D | 高频实时 LIO | 需稠密点云 |
| **LIO-SAM / LVI-SAM** | LiDAR + IMU (+视觉) | 3D | 工程化好 | 调参 |
| **gmapping**（ROS1 经典） | 2D LiDAR | 2D | 简单 | ROS2 已不维护 |

---

## 二、slam_toolbox 实战

### 2.1 安装与启动

```bash
sudo apt install ros-jazzy-slam-toolbox

# 在线异步建图（推荐）
ros2 launch slam_toolbox online_async_launch.py \
    use_sim_time:=true \
    slam_params_file:=$(ros2 pkg prefix --share my_pkg)/config/mapper.yaml
```

### 2.2 关键参数（mapper_params_online_async.yaml）

```yaml
slam_toolbox:
  ros__parameters:
    odom_frame: odom
    map_frame: map
    base_frame: base_link
    scan_topic: /scan
    mode: mapping                  # mapping / localization

    map_update_interval: 5.0
    resolution: 0.05
    max_laser_range: 20.0
    minimum_time_interval: 0.5
    transform_publish_period: 0.05

    # 闭环
    do_loop_closing: true
    loop_search_maximum_distance: 3.0
    loop_match_minimum_chain_size: 10

    # 序列化
    map_file_name: ""              # 启动时加载（继续建图）
    map_start_pose: [0.0, 0.0, 0.0]
```

### 2.3 保存 / 加载地图

```bash
# 保存
ros2 service call /slam_toolbox/save_map slam_toolbox/srv/SaveMap \
    "{name: {data: 'my_map'}}"

# 序列化（含图结构，可继续建图）
ros2 service call /slam_toolbox/serialize_map \
    slam_toolbox/srv/SerializePoseGraph "{filename: 'my_map_graph'}"

# 反序列化继续建图
ros2 service call /slam_toolbox/deserialize_map \
    slam_toolbox/srv/DeserializePoseGraph \
    "{filename: 'my_map_graph', match_type: 1, initial_pose: {x:0,y:0,theta:0}}"
```

### 2.4 三种模式

| Launch | 用途 |
|--------|------|
| `online_async_launch.py` | **在线异步建图**（默认） |
| `online_sync_launch.py` | 在线同步建图 |
| `localization_launch.py` | **基于已建图定位**（替代 amcl） |
| `lifelong_launch.py` | **Lifelong**：可重复建图 |

---

## 三、Cartographer ROS2

### 3.1 安装

```bash
sudo apt install ros-jazzy-cartographer ros-jazzy-cartographer-ros
```

### 3.2 配置（.lua）

```lua
include "map_builder.lua"
include "trajectory_builder.lua"

options = {
  map_builder = MAP_BUILDER,
  trajectory_builder = TRAJECTORY_BUILDER,
  map_frame = "map",
  tracking_frame = "imu_link",
  published_frame = "base_link",
  odom_frame = "odom",
  provide_odom_frame = true,
  use_odometry = false,
  use_nav_sat = false,
  num_laser_scans = 1,
  num_multi_echo_laser_scans = 0,
  num_subdivisions_per_laser_scan = 1,
  num_point_clouds = 0,
  rangefinder_sampling_ratio = 1.,
  ...
}
MAP_BUILDER.use_trajectory_builder_2d = true
TRAJECTORY_BUILDER_2D.min_range = 0.3
TRAJECTORY_BUILDER_2D.max_range = 30.
return options
```

### 3.3 启动

```bash
ros2 launch cartographer_ros cartographer.launch.py \
    configuration_basename:=my_robot.lua
```

输出 `.pbstream`，可用 `cartographer_pbstream_to_ros_map` 转 occupancy grid。

---

## 四、RTAB-Map

视觉/激光/RGB-D 融合，含可视化。

```bash
sudo apt install ros-jazzy-rtabmap-ros

# 立体相机 + IMU + 激光建图
ros2 launch rtabmap_launch rtabmap.launch.py \
    rgb_topic:=/camera/color/image_raw \
    depth_topic:=/camera/aligned_depth_to_color/image_raw \
    camera_info_topic:=/camera/color/camera_info \
    frame_id:=base_link \
    approx_sync:=false
```

特性：
- 闭环检测（Bag-of-Words）；
- 多传感器融合；
- DB 存储（SQLite），可重新打开继续；
- `rtabmap-databaseViewer` 可视化分析。

---

## 五、3D LIO（Fast-LIO 系）

工业部署中常见 LiDAR-IMU 紧耦合方案：

```bash
git clone https://github.com/hku-mars/FAST_LIO
cd FAST_LIO
# 切到 ros2 分支或社区移植版
```

要点：
- `point_cloud_topic` + `imu_topic`；
- IMU 须与激光时戳对齐（< 1ms）；
- 输出 `/Odometry` + `/cloud_registered`；
- 适用 Velodyne / Livox / Ouster。

---

## 六、定位选型

| 场景 | 推荐 |
|------|------|
| 已有 2D 占用栅格 | **slam_toolbox localization** 或 **amcl** |
| 已有 3D 点云 + LiDAR | NDT / ICP / lidar-to-prior-map（如 hdl_localization、Fast-LIO LOC） |
| 视觉先验 | RTAB-Map localization |

amcl 与 slam_toolbox-loc 对比：
- amcl 粒子滤波，传感器模型简单，CPU 占用低；
- slam_toolbox 利用图优化，鲁棒性更好，但 CPU/内存开销大。

---

## 七、性能与精度评估

工具：
- **evo**：`evo_traj` / `evo_ape` / `evo_rpe` 评估轨迹（与真值比较）；
- **rosbag2 + rqt_plot**：实时观察；
- **`/tf` 漂移**：长时间静置看 `map → odom` 是否漂；
- **OctoMap / mapping accuracy**：与高精度真值地图对比。

---

## 八、常见坑

| 现象 | 排查 |
|------|------|
| 建图飞掉 | 时间戳错乱 / TF 频率不足 / IMU 数据未对齐 |
| 闭环失败 | 场景重复纹理少 / 阈值过严；调 `loop_match_minimum_chain_size` |
| `/map` 空白 | 没人订阅 latched map / QoS 不匹配（要 TRANSIENT_LOCAL） |
| 定位漂移 | 传感器外参不准 / 里程计标定差 |
| 大场景内存爆 | slam_toolbox 用 `Lifelong` 模式可裁剪老节点 |

---

## 九、面试速记

- 2D 默认 **slam_toolbox**，已替代 gmapping；可序列化、Lifelong、本地化模式
- 3D 工业部署优选 **Fast-LIO 2** / **LIO-SAM**
- 视觉融合用 **RTAB-Map**
- 定位：amcl（轻量） vs slam_toolbox-loc（鲁棒）
- `/map` 必须 **TRANSIENT_LOCAL** QoS
- 评估用 **evo** 工具链
- IMU+LiDAR **时戳对齐**是 LIO 工程的命门
