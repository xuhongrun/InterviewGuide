# ROS2 TF2 与时间系统

> TF2 维护机器人**坐标系树**与**时变变换**，是定位、感知、规划、控制全链路的基础设施；时间系统决定 TF 查询语义与传感器数据对齐。

---

## 一、TF2 概览

TF2（`tf2` + `tf2_ros`）是 ROS1 `tf` 的重写版本，特点：
- **缓存历史变换**（默认 10 秒），可按时间戳查询；
- **静态变换**与**动态变换**分离话题；
- **多语言支持**（C++ / Python）；
- **数据驱动**，纯库无主进程，每个节点本地维护 BufferCore。

底层话题：
- `/tf`（动态，通常 50–100Hz，QoS=Reliable+Volatile）
- `/tf_static`（静态，QoS=**Reliable + TransientLocal + KeepLast(深度大)**，新订阅者可拿到全部历史）

---

## 二、坐标系约定（REP-105 / REP-103）

```
                map               (全局，可漂移修正)
                 │ pose update (slow, 1–10 Hz)
                odom              (里程计，连续无跳变)
                 │ TF (high freq)
                base_link         (车体中心)
        ┌────────┼─────────┐
        ▼        ▼         ▼
   imu_link  laser  camera_link
```

- 坐标轴方向（右手系）：**X 前 / Y 左 / Z 上**（机器人机体）；
- `map` → `odom` 由定位模块（如 AMCL/Cartographer）发布，跳变以校正漂移；
- `odom` → `base_link` 由轮式里程计/视觉里程计发布，**保证连续**；
- `base_link` → 各传感器：通常静态。

---

## 三、发布静态变换

```cpp
#include <tf2_ros/static_transform_broadcaster.h>
#include <geometry_msgs/msg/transform_stamped.hpp>

auto static_br = std::make_shared<tf2_ros::StaticTransformBroadcaster>(this);

geometry_msgs::msg::TransformStamped t;
t.header.stamp = this->now();
t.header.frame_id = "base_link";
t.child_frame_id  = "lidar_front";
t.transform.translation.x = 0.5;
t.transform.translation.z = 1.2;
tf2::Quaternion q; q.setRPY(0, 0, 0);
t.transform.rotation = tf2::toMsg(q);
static_br->sendTransform(t);
```

命令行：
```bash
ros2 run tf2_ros static_transform_publisher \
    --x 0.5 --z 1.2 --yaw 0 \
    --frame-id base_link --child-frame-id lidar_front
```

---

## 四、发布动态变换

```cpp
#include <tf2_ros/transform_broadcaster.h>

auto br = std::make_shared<tf2_ros::TransformBroadcaster>(this);

void on_odom_callback(const Odometry::SharedPtr msg) {
    geometry_msgs::msg::TransformStamped t;
    t.header.stamp = msg->header.stamp;
    t.header.frame_id = "odom";
    t.child_frame_id  = "base_link";
    t.transform.translation.x = msg->pose.pose.position.x;
    t.transform.translation.y = msg->pose.pose.position.y;
    t.transform.rotation = msg->pose.pose.orientation;
    br->sendTransform(t);
}
```

---

## 五、查询变换

```cpp
#include <tf2_ros/buffer.h>
#include <tf2_ros/transform_listener.h>

tf2_ros::Buffer buffer_(this->get_clock());
tf2_ros::TransformListener listener_(buffer_);

try {
    auto t = buffer_.lookupTransform(
        "map", "base_link",          // target ← source
        tf2::TimePointZero,           // 0 表示最新可用
        tf2::durationFromSec(0.1));   // 等待超时
    // 使用 t.transform...
} catch (const tf2::TransformException& e) {
    RCLCPP_WARN(get_logger(), "TF lookup failed: %s", e.what());
}
```

### 5.1 时间语义

| `time` 参数 | 含义 |
|-------------|------|
| `tf2::TimePointZero` | 最新可用变换（latest） |
| 具体时间戳 | 在该时刻查询；可能需要内插或外插 |

### 5.2 advanced：跨时间变换（odom 漂移补偿）

```cpp
// 把 t1 时刻 source_frame 中的点，转换到 t2 时刻 target_frame
auto t = buffer_.lookupTransform(
    "target", t2,
    "source", t1,
    "fixed_frame");   // 通常用 odom 作为固定参考
```

---

## 六、与消息绑定（数据 + 帧）

所有需要在不同坐标系间使用的数据，约定使用带 `header.stamp + header.frame_id` 的消息（`std_msgs/Header`），如 `geometry_msgs/PoseStamped`、`sensor_msgs/PointCloud2`、`nav_msgs/Odometry`。

转换工具：
```cpp
#include <tf2_geometry_msgs/tf2_geometry_msgs.hpp>

geometry_msgs::msg::PoseStamped pose_in, pose_out;
buffer_.transform(pose_in, pose_out, "map", tf2::durationFromSec(0.1));
```

`tf2_sensor_msgs`、`tf2_eigen`、`tf2_kdl` 提供针对各类型的转换函数。

---

## 七、时间源（Time Source）

ROS2 节点的 `Clock` 有三种类型：

| 类型 | 来源 | 用途 |
|------|------|------|
| `RCL_SYSTEM_TIME` | 操作系统墙钟 | 默认（生产物理机器人） |
| `RCL_STEADY_TIME` | 单调时钟 | 测周期、超时 |
| `RCL_ROS_TIME` | 可被 `/clock` 话题驱动（**仿真时间**） | Gazebo / Ignition / ROSBag 回放 |

启用仿真时间：
```cpp
this->declare_parameter("use_sim_time", false);
// 或在 launch 中传入
```

```bash
ros2 run my_pkg my_node --ros-args -p use_sim_time:=true
```

启用后，`this->now()` 返回 `/clock` 发布的仿真时间。**重要陷阱**：
- 启用前确保 `/clock` 已发布，否则 `now()` 返回 0；
- TF 查询用 `lookupTransform(..., this->now(), ...)` 避免使用墙钟。

### 7.1 ROSBag 回放与时间

```bash
ros2 bag record -a -o my_bag
ros2 bag play my_bag --clock 100      # 以 100Hz 发布 /clock
```

回放时所有节点都应启用 `use_sim_time:=true`。

---

## 八、TF 调试

```bash
ros2 run tf2_tools view_frames     # 生成 frames.pdf 显示坐标树
ros2 run tf2_ros tf2_echo map base_link
ros2 topic hz /tf
ros2 topic hz /tf_static
ros2 topic echo /tf --field transforms
```

### 常见问题

| 症状 | 原因 |
|------|------|
| `Lookup would require extrapolation into the past` | 缓存太旧；增大 `Buffer` 时长，或检查发布频率 |
| `Lookup would require extrapolation into the future` | 查询时间晚于已知，等待或减小查询时间 |
| `frame X does not exist` | 拼写、namespace 错误 |
| 多源同时发布同一变换 | 不同节点都在发 `odom→base_link`，时序冲突 |
| `/tf_static` 收不到 | QoS 必须是 TRANSIENT_LOCAL；检查 RMW 与订阅 QoS |

---

## 九、面试速记

- TF2 = `/tf`（动态）+ `/tf_static`（latched，TransientLocal QoS）
- REP-105 标准链：**map → odom → base_link → 传感器**
- 查询 `lookupTransform(target, source, time, timeout)`，最新用 `TimePointZero`
- 仿真时间：`use_sim_time:=true` + `/clock` 话题
- 数据带 `header.frame_id + stamp` 才能用 TF 转换
- 排查：`view_frames` + `ros2 topic hz /tf`
