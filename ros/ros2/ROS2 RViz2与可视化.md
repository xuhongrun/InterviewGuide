# ROS2 RViz2 与可视化

> RViz2 是 ROS2 的 3D 可视化工具，支持 Marker / TF / Image / PointCloud / 自定义 Display 插件。

---

## 一、启动

```bash
ros2 run rviz2 rviz2
ros2 run rviz2 rviz2 -d $(ros2 pkg prefix --share my_pkg)/rviz/view.rviz
```

`.rviz` 文件保存当前布局：可在 RViz 内 File→Save Config / Save Config As。

---

## 二、内置 Display 列表

| Display | 作用 |
|---------|------|
| `Grid` | 地面网格 |
| `TF` | 显示 TF 树（轴 + 名字） |
| `RobotModel` | 加载 URDF 显示模型 |
| `Image` | 订阅 sensor_msgs/Image 显示 |
| `Camera` | 与 Image 类似但 3D 投影 |
| `LaserScan` | 激光数据 |
| `PointCloud2` | 点云 |
| `Path` | nav_msgs/Path |
| `Odometry` | 历史轨迹 + 协方差椭球 |
| `Pose` / `PoseArray` | 单/多姿态 |
| `Map` | OccupancyGrid |
| `Marker` / `MarkerArray` | 通用图元 |
| `InteractiveMarkers` | 可拖拽标记 |
| `Polygon` | 多边形 |
| `Range` | 超声/红外测距锥 |
| `WrenchStamped` | 力/力矩箭头 |

---

## 三、Marker 详解

通用图元，支持 ARROW / CUBE / SPHERE / CYLINDER / LINE_STRIP / LINE_LIST / POINTS / TEXT_VIEW_FACING / MESH_RESOURCE / TRIANGLE_LIST 等。

```cpp
#include <visualization_msgs/msg/marker.hpp>
#include <visualization_msgs/msg/marker_array.hpp>

visualization_msgs::msg::Marker m;
m.header.frame_id = "map";
m.header.stamp = now();
m.ns = "obstacles";
m.id = 0;
m.type = m.SPHERE;
m.action = m.ADD;            // ADD / DELETE / DELETEALL
m.pose.position.x = 1.0;
m.scale.x = m.scale.y = m.scale.z = 0.2;
m.color.r = 1.0; m.color.a = 1.0;
m.lifetime = rclcpp::Duration::from_seconds(0);   // 永久
pub_->publish(m);
```

`MarkerArray` 用于批量发布（避免逐个 publish）。

> **InteractiveMarker** 用于实现 RViz 中拖拽点、旋转手柄。Nav2 的 `2D Goal Pose` 工具发的就是 PoseStamped，不是 InteractiveMarker。

---

## 四、自定义 Display 插件

RViz2 改用 OGRE Next + Qt5/Qt6，插件接口与 RViz1 不同。

### 4.1 类骨架

```cpp
#include <rviz_common/display.hpp>
#include <rviz_common/properties/color_property.hpp>

namespace my_rviz {
class MyDisplay : public rviz_common::Display {
    Q_OBJECT
public:
    MyDisplay();
protected:
    void onInitialize() override;
    void onEnable() override;
    void onDisable() override;
    void update(float wall_dt, float ros_dt) override;
private Q_SLOTS:
    void updateColor();
private:
    rviz_common::properties::ColorProperty * color_prop_;
};
}
```

### 4.2 注册

```cpp
#include <pluginlib/class_list_macros.hpp>
PLUGINLIB_EXPORT_CLASS(my_rviz::MyDisplay, rviz_common::Display)
```

`plugins_description.xml`：
```xml
<library path="my_rviz_plugins">
  <class name="my_rviz/MyDisplay"
         type="my_rviz::MyDisplay"
         base_class_type="rviz_common::Display">
    <description>Custom display</description>
  </class>
</library>
```

`package.xml`：
```xml
<exec_depend>rviz_common</exec_depend>
<exec_depend>rviz_rendering</exec_depend>
<export>
  <rviz plugin="${prefix}/plugins_description.xml"/>
</export>
```

CMakeLists：
```cmake
find_package(rviz_common REQUIRED)
find_package(pluginlib REQUIRED)
find_package(Qt5 REQUIRED COMPONENTS Widgets)

set(CMAKE_AUTOMOC ON)

add_library(my_rviz_plugins SHARED src/my_display.cpp)
target_link_libraries(my_rviz_plugins
  rviz_common::rviz_common Qt5::Widgets pluginlib::pluginlib)
```

---

## 五、Display 插件类型

| 基类 | 用途 |
|------|------|
| `rviz_common::Display` | 任意可视化（最常用） |
| `rviz_common::MessageFilterDisplay<T>` | 自动 TF 过滤 + topic 订阅 |
| `rviz_common::Tool` | 工具栏按钮（如 2D Goal） |
| `rviz_common::Panel` | 自定义控制面板 |

`MessageFilterDisplay` 模板会自动处理 frame 过滤与 buffer。

---

## 六、Tool / Panel

`Tool` 自定义鼠标交互（点选目标点）：

```cpp
class GoalTool : public rviz_common::Tool {
    int processMouseEvent(rviz_common::ViewportMouseEvent& e) override {
        if (e.leftDown()) { /* 把 e.x,e.y 转成 3D 射线 */ }
        return Render | Finished;
    }
};
```

`Panel` 任意 Qt Widget：

```cpp
class TeleopPanel : public rviz_common::Panel {
    Q_OBJECT
public:
    TeleopPanel(QWidget* parent = nullptr) {
        auto* btn = new QPushButton("STOP", this);
        connect(btn, &QPushButton::clicked, this, &TeleopPanel::stop);
        // 布局...
    }
    void stop() { /* 发 cmd_vel = 0 */ }
};
```

---

## 七、性能与渲染

- 大量 Marker 用 `MarkerArray` 批量发；不再可见的设 `DELETEALL` 清理；
- 大点云：使用 `Decay Time` 限制历史；点 size 不要过大；
- Image Display 不要订 8K 图，先 `image_proc` 缩小；
- RViz 默认按订阅频率刷新；卡顿先关闭多余 Display。

---

## 八、Foxglove Studio 替代

- 直接打开 **MCAP** bag；
- 通过 `foxglove_bridge` WebSocket 连接 ROS2 实时数据；
- 多面板布局（图、3D、表格、地图、URDF），跨平台 Web；
- 远程调试 / 嵌入式车端非常方便。

---

## 九、面试速记

- RViz2 = OGRE + Qt + pluginlib，与 RViz1 插件接口不兼容
- Marker = 通用图元；批量发用 `MarkerArray`
- 静态 TF 必须 `TRANSIENT_LOCAL`，否则 RViz 启动晚 TF 树看不到
- 自定义可视化：继承 `rviz_common::Display` 或 `MessageFilterDisplay<T>`
- Tool / Panel 走同套 pluginlib
- 远程调试推荐 **Foxglove + foxglove_bridge / MCAP**
