# ROS1 文件系统与常用消息族

> 入门必备：ROS 文件结构、命令行查找、`std_msgs/geometry_msgs/sensor_msgs/nav_msgs` 字段速查。

---

## 一、ROS 文件系统

### 1.1 安装目录

```
/opt/ros/noetic/
├── bin/        # rosrun / rosnode / rostopic / ...
├── etc/ros/
├── include/    # 头文件
├── lib/        # 共享库与可执行
├── share/      # package 资源（msg/srv/launch）
└── setup.bash  # 环境脚本
```

工作空间：

```
catkin_ws/
├── src/        # 源码（git clone 的包）
├── build/      # 构建产物
├── devel/      # 开发空间，含 setup.bash
└── install/    # 可选 install 空间
```

### 1.2 Overlay 机制

`source` 顺序决定优先级（后 source 覆盖前）：

```bash
source /opt/ros/noetic/setup.bash         # base
source ~/catkin_ws/devel/setup.bash       # overlay 1
source ~/catkin_ws2/devel/setup.bash      # overlay 2 (优先)
```

变量传递：`CMAKE_PREFIX_PATH` / `ROS_PACKAGE_PATH` / `LD_LIBRARY_PATH` / `PYTHONPATH` 被层叠拼接。

### 1.3 包查找命令

```bash
rospack find <pkg>             # 包绝对路径
roscd <pkg>[/subdir]           # cd 到包目录
rosls <pkg>                    # ls 包内容
rosed <pkg> file.launch        # 编辑包内文件
rospack depends-on <pkg>       # 反向依赖
rospack list | grep <kw>       # 全量列表过滤
```

### 1.4 package.xml（format 2）

```xml
<package format="2">
  <name>my_pkg</name>
  <version>0.1.0</version>
  <description>...</description>
  <maintainer email="x@y">me</maintainer>
  <license>Apache-2.0</license>

  <buildtool_depend>catkin</buildtool_depend>
  <depend>roscpp</depend>                <!-- 编译+运行 -->
  <build_depend>message_generation</build_depend>
  <exec_depend>message_runtime</exec_depend>
</package>
```

---

## 二、std_msgs（基本类型）

| 类型 | 字段 | 用途 |
|------|------|------|
| `Bool` | `bool data` | 布尔信号 |
| `Int8/16/32/64` `UInt8/...` | `* data` | 整型 |
| `Float32/64` | `* data` | 浮点 |
| `String` | `string data` | 字符串 |
| `Header` | `seq, stamp, frame_id` | **消息头**（被无数消息复用） |
| `Time` / `Duration` | — | 时间 |
| `Empty` | — | 信号触发 |
| `ColorRGBA` | `r g b a` | 颜色 |
| `MultiArray` 系列 | `MultiArrayLayout layout + data[]` | 通用数组容器 |

> ⚠️ ROS1/2 都强烈建议**自带 Header** 的消息携带 `stamp`，便于 TF/同步。

### Header 详解

```idl
uint32 seq            # 序列号（ROS1 自动填，ROS2 已弃用）
time stamp            # 时间戳（sec + nsec）
string frame_id       # 坐标系 ID（参考 REP-105 命名）
```

---

## 三、geometry_msgs（几何）

| 类型 | 关键字段 |
|------|----------|
| `Point` | `x y z` |
| `Quaternion` | `x y z w`（**四元数顺序：xyzw**） |
| `Vector3` | `x y z` |
| `Pose` | `Point position + Quaternion orientation` |
| `PoseStamped` | `Header + Pose` ← 最常用 |
| `PoseWithCovariance` | `Pose + float64[36] covariance`（6×6 行优先） |
| `Twist` | `Vector3 linear + Vector3 angular` |
| `TwistStamped` | `Header + Twist` |
| `Transform` | `Vector3 translation + Quaternion rotation` |
| `TransformStamped` | `Header + child_frame_id + Transform` ← TF 基础 |
| `Wrench` | `Vector3 force + Vector3 torque` |
| `Accel` | `Vector3 linear + Vector3 angular` |

### Twist 单位约定（REP-103）

- 直线：m/s
- 角速度：rad/s
- 右手系：x 前、y 左、z 上（机器人坐标系）

---

## 四、sensor_msgs（传感器）

| 类型 | 关键字段 / 说明 |
|------|----------------|
| `Imu` | `Header + orientation(Quat) + angular_velocity + linear_acceleration + covariance[3]` |
| `LaserScan` | `angle_min/max, angle_increment, range_min/max, ranges[], intensities[]` |
| `PointCloud2` | `Header + height/width + fields[] + is_bigendian + point_step + row_step + data[]` |
| `Image` | `Header + height + width + encoding + step + data[]`（rgb8/bgr8/mono8/mono16/16UC1...） |
| `CompressedImage` | `Header + format + data[]` |
| `CameraInfo` | `K[9]/D[]/R[9]/P[12]` 内参与畸变 |
| `JointState` | `name[] + position[] + velocity[] + effort[]` |
| `NavSatFix` | `latitude/longitude/altitude + covariance + status` |
| `Range` | 超声/红外测距 |
| `BatteryState` | 电池状态 |
| `MagneticField` | `magnetic_field(Vector3)` |
| `FluidPressure` / `Temperature` / `Illuminance` | 大气/温度/光照 |

### PointCloud2 字段编码

```
fields[i]: name=x/y/z/rgb/intensity..., offset, datatype(FLOAT32=7), count
point_step  = 单点字节数（如 32）
row_step    = point_step * width
data[]      = 紧密打包的二进制
```

`pcl_conversions::fromROSMsg` 转 `pcl::PointCloud<T>` 后再处理。

### Image encoding 速查

| 编码 | 通道 | 字节/像素 |
|------|------|-----------|
| `mono8` | 1 | 1 |
| `mono16` | 1 | 2 |
| `bgr8` / `rgb8` | 3 | 3 |
| `bgra8` / `rgba8` | 4 | 4 |
| `16UC1` | 1 | 2（深度图常用） |
| `32FC1` | 1 | 4（视差/深度浮点） |

---

## 五、nav_msgs（导航）

| 类型 | 字段 |
|------|------|
| `Odometry` | `Header + child_frame_id + PoseWithCovariance pose + TwistWithCovariance twist` |
| `Path` | `Header + PoseStamped poses[]` |
| `OccupancyGrid` | `Header + MapMetaData info + int8 data[]`（-1=未知, 0=空, 100=占用） |
| `MapMetaData` | `resolution + width + height + Pose origin` |
| `GridCells` | 离散单元格集合 |

### Odometry 坐标约定（REP-105）

```
header.frame_id      = "odom"        # 全局参考
child_frame_id       = "base_link"   # 机器人体坐标
pose                 = base_link 相对 odom 的位姿
twist                = base_link 相对自身的速度
```

---

## 六、tf2_msgs / actionlib_msgs

- `tf2_msgs/TFMessage`：`TransformStamped[] transforms` → 用于 `/tf` 话题
- `actionlib_msgs/GoalStatusArray`：Action 状态广播

---

## 七、自定义消息

`my_pkg/msg/Pose2D.msg`：

```idl
Header header
float64 x
float64 y
float64 theta
uint8 IDLE = 0
uint8 RUNNING = 1
uint8 state
```

`CMakeLists.txt` 关键片段：

```cmake
find_package(catkin REQUIRED COMPONENTS message_generation std_msgs)
add_message_files(FILES Pose2D.msg)
generate_messages(DEPENDENCIES std_msgs)
catkin_package(CATKIN_DEPENDS message_runtime std_msgs)
```

`package.xml`：
```xml
<build_depend>message_generation</build_depend>
<exec_depend>message_runtime</exec_depend>
```

---

## 八、面试速记

- ROS 文件系统是**包+manifest**结构，`rospack/roscd/rosls`
- Overlay 机制：后 `source` 覆盖前
- **Header 三件套**：`seq + stamp + frame_id`
- **四元数顺序 xyzw**（不是 wxyz！）
- Twist：m/s + rad/s，机器人坐标系右手 x 前 y 左 z 上
- PointCloud2 是**二进制紧凑布局**，字段描述在 `fields[]`
- OccupancyGrid 占用值：-1/0/100
- Odometry：`odom → base_link`，pose 在 odom，twist 在 base_link
