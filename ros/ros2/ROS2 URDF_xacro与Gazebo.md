# ROS2 URDF / xacro / SDF 与 Gazebo

> ROS2 的机器人建模与仿真：URDF + xacro 与 ROS1 一致；Gazebo 由经典版（Gazebo Classic）演进到 **Gazebo Sim（gz garden / harmonic / ionic）**，通过 `ros_gz_bridge` 与 ROS2 互通。

---

## 一、URDF / xacro（与 ROS1 通用）

完全复用 ROS1 知识：`<link>/<joint>/<inertial>/<visual>/<collision>` + xacro 宏。详见 [ROS1 URDF与xacro](../ros1/ROS1%20URDF与xacro.md)。

ROS2 加载方式（launch.py）：

```python
import os
from ament_index_python import get_package_share_directory
from launch_ros.actions import Node
from launch import LaunchDescription
import xacro

def generate_launch_description():
    pkg = get_package_share_directory('my_robot_description')
    xacro_file = os.path.join(pkg, 'urdf', 'robot.urdf.xacro')
    robot_description = xacro.process_file(xacro_file).toxml()

    return LaunchDescription([
        Node(package='robot_state_publisher',
             executable='robot_state_publisher',
             parameters=[{'robot_description': robot_description,
                          'use_sim_time': True}]),
        Node(package='joint_state_publisher_gui',
             executable='joint_state_publisher_gui'),
        Node(package='rviz2', executable='rviz2',
             arguments=['-d', os.path.join(pkg, 'rviz', 'view.rviz')]),
    ])
```

---

## 二、URDF 与 ros2_control

URDF 中加 `<ros2_control>` 标签（取代 ROS1 的 `<transmission>`）：

```xml
<ros2_control name="MySystem" type="system">
  <hardware>
    <plugin>gz_ros2_control/GazeboSimSystem</plugin>
  </hardware>
  <joint name="joint1">
    <command_interface name="position"/>
    <state_interface name="position"/>
    <state_interface name="velocity"/>
  </joint>
</ros2_control>
```

参见 [ROS2 ros2_control与Nav2生态](ROS2%20ros2_control与Nav2生态.md)。

---

## 三、SDF（Gazebo Sim 原生格式）

Gazebo Sim 原生用 SDF（Simulation Description Format）。URDF 在加载时会被自动转 SDF，但精细物理参数建议直接写 SDF：

```xml
<?xml version="1.0"?>
<sdf version="1.10">
  <world name="default">
    <plugin filename="gz-sim-physics-system"
            name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-sensors-system"
            name="gz::sim::systems::Sensors">
      <render_engine>ogre2</render_engine>
    </plugin>
    <plugin filename="gz-sim-user-commands-system"
            name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system"
            name="gz::sim::systems::SceneBroadcaster"/>

    <light name="sun" type="directional">
      <cast_shadows>true</cast_shadows>
      <direction>-0.5 0.1 -0.9</direction>
    </light>

    <model name="ground_plane">...</model>
  </world>
</sdf>
```

URDF → SDF 转换：`ign sdf -p robot.urdf` 或 Gazebo 加载时自动。

---

## 四、Gazebo Sim 启动

```bash
# 安装（Jazzy 默认 Harmonic）
sudo apt install ros-jazzy-ros-gz

# 直接启动
ign gazebo empty.sdf
gz sim empty.sdf       # garden+
```

ROS2 launch：

```python
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource

gz_sim = IncludeLaunchDescription(
    PythonLaunchDescriptionSource([
        os.path.join(get_package_share_directory('ros_gz_sim'),
                     'launch', 'gz_sim.launch.py')]),
    launch_arguments={'gz_args': '-r empty.sdf'}.items())
```

Spawn URDF 模型：

```python
spawn = Node(package='ros_gz_sim', executable='create',
             arguments=['-topic', 'robot_description',
                        '-name', 'my_robot',
                        '-x', '0', '-y', '0', '-z', '0.1'])
```

---

## 五、ros_gz_bridge：话题桥接

Gazebo 自有 topic 体系（gz topic），ROS2 用 `ros_gz_bridge` 双向桥接：

```bash
ros2 run ros_gz_bridge parameter_bridge \
    /clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock \
    /cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist \
    /odom@nav_msgs/msg/Odometry[gz.msgs.Odometry \
    /scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan
```

方向符号：
- `@`：双向；
- `[`：仅 Gazebo→ROS；
- `]`：仅 ROS→Gazebo。

YAML 批量配置：

```yaml
- ros_topic_name: "cmd_vel"
  gz_topic_name:  "cmd_vel"
  ros_type_name:  "geometry_msgs/msg/Twist"
  gz_type_name:   "gz.msgs.Twist"
  direction:      "ROS_TO_GZ"
```

`parameter_bridge --ros-args -p config_file:=bridge.yaml`

`ros_gz_image` 单独包含图像桥（性能优化）。

---

## 六、Gazebo 系统插件

| 插件 | 功能 |
|------|------|
| `gz-sim-physics-system` | 物理（DART/Bullet/TPE） |
| `gz-sim-sensors-system` | 渲染传感器（相机/激光/深度） |
| `gz-sim-imu-system` | IMU |
| `gz-sim-diff-drive-system` | 差速驱动 |
| `gz-sim-joint-state-publisher-system` | 发布 JointState |
| `gz-ros2-control-system` | ros2_control 桥 |

通常在 SDF `<plugin>` 里挂载，配合 ros_gz_bridge 输出 ROS2 话题。

---

## 七、传感器示例（在 SDF 中）

```xml
<sensor name="camera" type="camera">
  <topic>camera/image</topic>
  <update_rate>30</update_rate>
  <camera>
    <horizontal_fov>1.047</horizontal_fov>
    <image><width>640</width><height>480</height></image>
    <clip><near>0.1</near><far>100</far></clip>
  </camera>
</sensor>

<sensor name="lidar" type="gpu_lidar">
  <topic>scan</topic>
  <update_rate>10</update_rate>
  <ray>
    <scan>
      <horizontal>
        <samples>720</samples>
        <min_angle>-3.14</min_angle>
        <max_angle> 3.14</max_angle>
      </horizontal>
    </scan>
    <range><min>0.1</min><max>30</max></range>
  </ray>
</sensor>
```

---

## 八、常见坑

| 现象 | 原因 |
|------|------|
| Gazebo 启动机器人乱飞 | URDF 惯量为 0 / mass 太小 |
| ROS2 收不到 Gazebo 话题 | bridge 没启动 / 类型不匹配 |
| TF 没有 `odom→base_link` | 没启用 diff_drive_system 或 odom_publisher |
| 图像 fps 低 | render engine 没用 ogre2 / GPU 资源不足 |
| ros2_control 控不动 | gz_ros2_control plugin 没挂载到 SDF / URDF |
| Sim 时间不对 | 节点没设 `use_sim_time:=true`；bridge 未桥接 `/clock` |

---

## 九、面试速记

- ROS2 用 **Gazebo Sim**（garden+），原生格式 **SDF**
- URDF 仍可用，自动转 SDF
- ROS2 ↔ Gazebo 通过 **ros_gz_bridge** 桥接 topic / service
- 必须桥接 `/clock` 并设 `use_sim_time:=true`
- ros2_control 仿真用 **gz_ros2_control** 插件
- `<ros2_control>` URDF 标签替代 ROS1 `<transmission>`
- Sim 失败先查惯量、bridge、time
