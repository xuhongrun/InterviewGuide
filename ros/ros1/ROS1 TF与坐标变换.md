# ROS1 TF 与坐标变换

> TF（Transform Library，新版 `tf2`）是 ROS 的**坐标系树**管理库，为机器人各部件 / 传感器之间维护时变变换。

---

## 一、概念

- **Frame**：一个右手坐标系，每帧有名字 `frame_id`（如 `map`、`odom`、`base_link`、`camera_optical`）。
- **Transform**：父→子的 6-DoF 变换（平移 + 四元数）。
- **TF Tree**：所有 transform 构成一棵**有向树**（**单父**约束，杜绝环路）。

```
map ─→ odom ─→ base_link ─┬─→ laser
                          ├─→ imu
                          └─→ camera_link → camera_optical
```

### REP-105 标准帧

| Frame | 含义 |
|-------|------|
| `map` | 全局静止参考（漂移修正） |
| `odom` | 里程计参考（连续无跳变，但有累计漂移） |
| `base_link` | 机器人本体（载体坐标系） |
| `base_footprint` | 投影到地面的足迹 |

链：`map → odom → base_link`。前两段由定位 / 里程计提供，后续由 URDF + robot_state_publisher 描述。

---

## 二、tf vs tf2

- **tf**（旧）：API 散乱、性能差、已弃用；
- **tf2**（推荐）：模块化（`tf2`、`tf2_ros`、`tf2_geometry_msgs`、`tf2_eigen` ...），ROS2 唯一选择。

迁移：`#include <tf2_ros/transform_broadcaster.h>` 替换 `tf::TransformBroadcaster`。

---

## 三、广播变换

### 3.1 静态（一次性）

```bash
rosrun tf2_ros static_transform_publisher x y z qx qy qz qw parent child
# 例：base_link → laser，平移 (0.2, 0, 0.1)，无旋转
rosrun tf2_ros static_transform_publisher 0.2 0 0.1 0 0 0 1 base_link laser
```

发布到 `/tf_static`（latched），新订阅者也能收到。

### 3.2 动态（C++）

```cpp
#include <tf2_ros/transform_broadcaster.h>
#include <geometry_msgs/TransformStamped.h>

tf2_ros::TransformBroadcaster br;
geometry_msgs::TransformStamped t;
t.header.stamp = ros::Time::now();
t.header.frame_id = "odom";
t.child_frame_id  = "base_link";
t.transform.translation.x = x;
t.transform.translation.y = y;
tf2::Quaternion q; q.setRPY(0, 0, yaw);
t.transform.rotation = tf2::toMsg(q);
br.sendTransform(t);   // 发布到 /tf
```

### 3.3 robot_state_publisher

读取 URDF 的 `<joint>`，结合 `/joint_states` 自动发布 link 间 TF。是 URDF + tf 的标准入口。

---

## 四、监听变换

```cpp
#include <tf2_ros/transform_listener.h>
#include <tf2_ros/buffer.h>

tf2_ros::Buffer tf_buffer;
tf2_ros::TransformListener tf_listener(tf_buffer);

try {
    auto tf = tf_buffer.lookupTransform(
        "map", "base_link",
        ros::Time(0),                      // 0 = 最新可用
        ros::Duration(0.1));               // 超时
    double x = tf.transform.translation.x;
} catch (tf2::TransformException& e) {
    ROS_WARN("%s", e.what());
}
```

**`ros::Time(0)` 取最新；`ros::Time::now()` 必须等到该时刻有数据**（常见报错：`Lookup would require extrapolation into the future`）。

---

## 五、点 / 位姿变换

```cpp
#include <tf2_geometry_msgs/tf2_geometry_msgs.h>

geometry_msgs::PoseStamped p_in, p_out;
p_in.header.frame_id = "laser";
p_in.pose.position.x = 1.0;

tf_buffer.transform(p_in, p_out, "map", ros::Duration(0.1));
```

支持的类型：`Point/Vector3/Pose/PoseStamped/PointStamped/QuaternionStamped/Twist/Wrench`。

**点云 / 自定义类型**：

```cpp
#include <pcl_ros/transforms.h>
sensor_msgs::PointCloud2 cloud_out;
pcl_ros::transformPointCloud("map", *tf, cloud_in, cloud_out);
```

---

## 六、time travel：跨时间查询

```cpp
auto tf = tf_buffer.lookupTransform(
    "map", ros::Time::now(),                 // target frame & time
    "base_link", ros::Time::now() - ros::Duration(1.0),  // source frame & time
    "odom",                                   // fixed frame（"绳"）
    ros::Duration(0.5));
```

用于：传感器数据（1s 前的图像）相对当前位置的位移分析。

---

## 七、调试工具

```bash
rosrun tf view_frames                    # 生成 frames.pdf（默认 5s 采样）
rosrun tf2_tools view_frames.py          # tf2 版

rosrun tf tf_echo <source> <target>      # 实时打印变换
rosrun tf tf_monitor                     # TF 树健康监控（频率/延迟）

rosrun rqt_tf_tree rqt_tf_tree           # 图形化 TF 树
```

RViz 中加 `TF` Display 直接观察。

---

## 八、常见报错

| 报错 | 原因 | 解决 |
|------|------|------|
| `Lookup would require extrapolation into the future/past` | 查询时间超出 buffer | 增大 buffer 大小 / 用 `Time(0)` / 用 `canTransform` 等待 |
| `frame X does not exist` | 没人广播 | 检查 broadcaster 是否启动，frame_id 拼写 |
| `TF_REPEATED_DATA` 警告 | 同一 stamp 重复发布 | 同一 publisher 单例，避免循环重发 |
| `TF_OLD_DATA` | 时间戳老于 buffer | 时钟不同步 / sim_time 没设 |
| `TF_NAN_INPUT` | 数据含 NaN | 检查输入 |
| 生成 TF 树有**多父** | 同 child 被多次声明 | TF 树必须**单父**，调整广播来源 |

---

## 九、坐标系命名约定

光学 / 相机：

```
camera_link            # 相机机械中心
camera_optical_frame   # ROS 标准光学系：z 前、x 右、y 下
```

转换关系：`camera_link → camera_optical` = 旋转使 z 朝前。`tf_static_publisher` 一次声明即可。

---

## 十、面试速记

- TF 树**单父有向**，`map → odom → base_link → ...`（REP-105）
- **静态 TF** 走 `/tf_static`（latched），动态走 `/tf`
- `tf2` 是新版，必须用 `tf2_ros::TransformBroadcaster/Buffer/Listener`
- 查询用 `Time(0) = 最新可用`，推荐 + 超时
- `tf_echo` / `view_frames` / `rqt_tf_tree` 三件套调试
- **extrapolation 报错**多半是时钟没同步或 sim_time 没设
- 相机要区分 `camera_link` 与 `camera_optical_frame`
