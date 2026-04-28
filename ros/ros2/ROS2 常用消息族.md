# ROS2 常用消息族与接口

> 与 ROS1 的消息族**几乎完全对齐**，类型名相同但路径有 `_msgs::msg::` 前缀。下面汇总最常用的接口及差异。

---

## 一、命名差异（ROS1 → ROS2）

| ROS1 头文件 | ROS2 头文件 |
|-------------|-------------|
| `std_msgs/String.h` | `std_msgs/msg/string.hpp` |
| `geometry_msgs/PoseStamped.h` | `geometry_msgs/msg/pose_stamped.hpp` |
| `sensor_msgs/PointCloud2.h` | `sensor_msgs/msg/point_cloud2.hpp` |
| `nav_msgs/Odometry.h` | `nav_msgs/msg/odometry.hpp` |
| `tf/transform_listener.h` | `tf2_ros/transform_listener.h` |

C++ 命名空间统一为 `<pkg>::msg::Type`、`<pkg>::srv::Type::Request/Response`、`<pkg>::action::Type::Goal/Result/Feedback`。

Python：`from std_msgs.msg import String`。

---

## 二、std_msgs

| 类型 | 字段 |
|------|------|
| `Bool/Int*/UInt*/Float*/String/Empty/Time/Duration` | 同 ROS1 |
| `Header` | `time stamp + string frame_id`（**ROS2 取消 `seq` 字段**） |
| `ColorRGBA` | r g b a |

> ⚠️ ROS2 取消 `Header.seq`，迁移代码时移除引用。

---

## 三、geometry_msgs

完全同 ROS1：`Point/Quaternion/Vector3/Pose/PoseStamped/Twist/TwistStamped/Transform/TransformStamped/Wrench/Accel`。

四元数顺序仍为 **xyzw**。

---

## 四、sensor_msgs

完全同 ROS1：`Imu / LaserScan / PointCloud2 / Image / CompressedImage / CameraInfo / JointState / NavSatFix / Range / BatteryState / MagneticField / FluidPressure / Temperature`。

PointCloud2 字段、Image encoding 完全一致。

---

## 五、nav_msgs / nav2_msgs

`nav_msgs`（与 ROS1 同）：`Odometry / Path / OccupancyGrid / MapMetaData / GridCells`。

`nav2_msgs`（ROS2 新增）：

| 类型 | 用途 |
|------|------|
| `Costmap` | costmap 序列化 |
| `Particle` / `ParticleCloud` | AMCL 粒子 |
| `BehaviorTreeLog` | BT 节点状态日志 |

Action：
- `NavigateToPose`：单点导航；
- `NavigateThroughPoses`：多 waypoint；
- `ComputePathToPose` / `FollowPath` / `Spin` / `BackUp` / `Wait`。

---

## 六、tf2_msgs / action_msgs

- `tf2_msgs/TFMessage` — `/tf`、`/tf_static` 携带；
- `action_msgs/GoalStatus` / `GoalStatusArray` / `GoalInfo` — Action 内部使用；
- `unique_identifier_msgs/UUID` — Action goal id 的标准类型。

---

## 七、interface 命令行内省

```bash
ros2 interface list                          # 全量
ros2 interface list --only-msgs              # 仅消息
ros2 interface packages                      # 含 IDL 的包
ros2 interface package std_msgs              # 列包内接口
ros2 interface show geometry_msgs/msg/PoseStamped
ros2 interface proto sensor_msgs/msg/Imu     # 输出 YAML 模板（用于 ros2 topic pub）
```

---

## 八、自定义 .msg / .srv / .action

`my_msgs/msg/Pose2D.msg`：

```idl
std_msgs/Header header
float64 x
float64 y
float64 theta
uint8 IDLE = 0
uint8 RUNNING = 1
uint8 state 0
```

`my_msgs/srv/AddTwoInts.srv`：
```idl
int64 a
int64 b
---
int64 sum
```

`my_msgs/action/Fibonacci.action`：
```idl
int32 order
---
int32[] sequence
---
int32[] partial_sequence
```

`CMakeLists.txt`：
```cmake
find_package(rosidl_default_generators REQUIRED)
rosidl_generate_interfaces(${PROJECT_NAME}
  msg/Pose2D.msg
  srv/AddTwoInts.srv
  action/Fibonacci.action
  DEPENDENCIES std_msgs
)
ament_export_dependencies(rosidl_default_runtime)
```

`package.xml`：
```xml
<buildtool_depend>ament_cmake</buildtool_depend>
<build_depend>rosidl_default_generators</build_depend>
<exec_depend>rosidl_default_runtime</exec_depend>
<member_of_group>rosidl_interface_packages</member_of_group>
```

C++ 用法：
```cpp
#include <my_msgs/msg/pose2_d.hpp>
my_msgs::msg::Pose2D p; p.x = 1.0;
```

---

## 九、QoS 对常用消息的推荐

| 消息族 | 推荐 QoS |
|--------|----------|
| `/tf` | RELIABLE + KEEP_LAST(100) + VOLATILE |
| `/tf_static` | RELIABLE + TRANSIENT_LOCAL + KEEP_LAST(1) |
| `/scan`, `/imu`, `/image` | **SensorDataQoS**（BEST_EFFORT + KEEP_LAST(5)） |
| `/odom` | RELIABLE + KEEP_LAST(10) + VOLATILE |
| `/map` | RELIABLE + **TRANSIENT_LOCAL** + KEEP_LAST(1)（晚到订阅可拿到） |
| `/cmd_vel` | RELIABLE + KEEP_LAST(1) + VOLATILE |

---

## 十、面试速记

- ROS2 消息族基本与 ROS1 同名，**Header 去掉 `seq`**
- 命名空间 `<pkg>::msg::T` / `<pkg>::srv::T::Request` / `<pkg>::action::T::Goal`
- 自定义接口必须在**单独包**且声明 `<member_of_group>rosidl_interface_packages</member_of_group>`
- `/tf_static` 和 `/map` 必须 **TRANSIENT_LOCAL**，否则晚到订阅看不到
- `ros2 interface show/proto` 速查字段
