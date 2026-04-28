# ROS1 插件、动态参数与 RViz 可视化

> 三大扩展点：**pluginlib**（C++ 插件机制）、**Dynamic Reconfigure**（运行时调参）、**RViz Display Plugin**（自定义可视化）。

---

## 一、pluginlib：动态加载 C++ 插件

ROS1 中 navigation/MoveIt/RViz 等大量框架使用 pluginlib 让用户**不重编主程序**也能加载新算法。

### 1.1 基础

定义抽象基类（在公共包 `polygon_base`）：

```cpp
// polygon_base/include/polygon_base/regular_polygon.h
namespace polygon_base {
class RegularPolygon {
public:
    virtual void initialize(double side_length) = 0;
    virtual double area() = 0;
    virtual ~RegularPolygon() = default;
protected:
    RegularPolygon() = default;
};
}
```

实现派生类（在 `polygon_plugins`）：

```cpp
#include <pluginlib/class_list_macros.h>
#include <polygon_base/regular_polygon.h>

namespace polygon_plugins {
class Square : public polygon_base::RegularPolygon {
public:
    void initialize(double s) override { side_ = s; }
    double area() override { return side_ * side_; }
private:
    double side_;
};
}
PLUGINLIB_EXPORT_CLASS(polygon_plugins::Square, polygon_base::RegularPolygon)
```

CMakeLists：

```cmake
add_library(polygon_plugins src/square.cpp)
target_link_libraries(polygon_plugins ${catkin_LIBRARIES})
```

`plugins.xml`：

```xml
<library path="lib/libpolygon_plugins">
  <class name="polygon_plugins/Square"
         type="polygon_plugins::Square"
         base_class_type="polygon_base::RegularPolygon">
    <description>A square polygon</description>
  </class>
</library>
```

`package.xml`：

```xml
<exec_depend>polygon_base</exec_depend>
<export>
  <polygon_base plugin="${prefix}/plugins.xml"/>
</export>
```

### 1.2 加载

```cpp
#include <pluginlib/class_loader.h>
pluginlib::ClassLoader<polygon_base::RegularPolygon>
    loader("polygon_base", "polygon_base::RegularPolygon");

auto sq = loader.createInstance("polygon_plugins/Square");
sq->initialize(2.0);
ROS_INFO("area=%.2f", sq->area());
```

### 1.3 实战场景

| 框架 | 插件类型 |
|------|----------|
| `move_base` | global/local planner、recovery、costmap layer |
| `nav_core` | BaseGlobalPlanner / BaseLocalPlanner |
| `MoveIt` | planner_manager、kinematics_solver、collision_detector |
| `RViz` | Display / Tool / Panel |
| `controller_manager` | ControllerInterface |

> ⚠️ 部署时 plugin 库必须随 install 输出（`install(TARGETS ... LIBRARY DESTINATION ${CATKIN_PACKAGE_LIB_DESTINATION})`），否则运行时找不到。

---

## 二、Dynamic Reconfigure：运行时调参

### 2.1 定义 .cfg

`cfg/MyParams.cfg`：

```python
#!/usr/bin/env python
PACKAGE = "my_pkg"
from dynamic_reconfigure.parameter_generator_catkin import *

gen = ParameterGenerator()
#       name           type       level  description    default min  max
gen.add("rate",        double_t,  0,    "Hz",            10.0,  0.1, 100.0)
gen.add("enable",      bool_t,    0,    "Enable feature", True)
gen.add("mode",        int_t,     0,    "Mode",           0,     0,   3)

# 枚举
mode_enum = gen.enum([gen.const("FAST", int_t, 0, "Fast"),
                      gen.const("SLOW", int_t, 1, "Slow")], "mode set")
gen.add("speed_mode", int_t, 0, "speed", 0, 0, 1, edit_method=mode_enum)

exit(gen.generate(PACKAGE, "my_node", "MyParams"))
```

CMakeLists：

```cmake
find_package(catkin REQUIRED COMPONENTS dynamic_reconfigure)
generate_dynamic_reconfigure_options(cfg/MyParams.cfg)
```

### 2.2 服务端

```cpp
#include <dynamic_reconfigure/server.h>
#include <my_pkg/MyParamsConfig.h>

void cb(my_pkg::MyParamsConfig& cfg, uint32_t level) {
    ROS_INFO("rate=%.2f enable=%d", cfg.rate, cfg.enable);
}

dynamic_reconfigure::Server<my_pkg::MyParamsConfig> server;
server.setCallback(cb);
ros::spin();
```

### 2.3 客户端 / GUI

```bash
rosrun rqt_reconfigure rqt_reconfigure       # GUI
rosrun dynamic_reconfigure dynparam set /my_node rate 20.0
rosrun dynamic_reconfigure dynparam dump /my_node dump.yaml
rosrun dynamic_reconfigure dynparam load /my_node dump.yaml
```

> ROS2 不再需要 dynamic_reconfigure，参数本身支持运行时 set + 事件订阅。

---

## 三、RViz Display 插件

RViz 通过 pluginlib 加载 Display / Tool / Panel。下面写一个 Display：

```cpp
// my_rviz_plugins/include/my_rviz_plugins/my_display.h
#include <rviz/display.h>
#include <rviz/properties/color_property.h>
#include <std_msgs/String.h>

namespace my_rviz_plugins {
class MyDisplay : public rviz::Display {
    Q_OBJECT
public:
    MyDisplay();
protected:
    void onInitialize() override;
    void onEnable() override;
    void onDisable() override;
private Q_SLOTS:
    void updateColor();
private:
    rviz::ColorProperty* color_property_;
    ros::Subscriber sub_;
};
}
```

```cpp
#include <pluginlib/class_list_macros.h>
PLUGINLIB_EXPORT_CLASS(my_rviz_plugins::MyDisplay, rviz::Display)
```

`rviz_plugin.xml`：

```xml
<library path="lib/libmy_rviz_plugins">
  <class name="my_rviz_plugins/MyDisplay" type="my_rviz_plugins::MyDisplay"
         base_class_type="rviz::Display">
    <description>Custom display</description>
  </class>
</library>
```

`package.xml`：
```xml
<export>
  <rviz plugin="${prefix}/rviz_plugin.xml"/>
</export>
```

启动 RViz 后在 `Add` 面板可见 `MyDisplay`。

### 渲染

RViz 使用 OGRE 3D 引擎；常用接口：
- `rviz::Display::onInitialize()` 创建场景节点；
- `Ogre::SceneManager` / `Ogre::SceneNode`；
- 复杂图形用 `rviz::Object` 子类（Arrow / Line / Shape）。

### 常见自定义场景

- 自定义消息类型可视化（如雷达自定义点云、车道线 polyline）；
- 自定义工具：地图标注、路径起点选择；
- 自定义 Panel：业务控制按钮（启动/停止）。

---

## 四、面试速记

- pluginlib = **抽象基类 + 派生类 + plugins.xml + PLUGINLIB_EXPORT_CLASS**
- 插件库要在 install 路径下，否则运行时找不到
- Dynamic Reconfigure：`.cfg` 描述参数 → 生成头文件 → `Server::setCallback`
- ROS2 用**参数事件**替代 dynamic_reconfigure
- RViz 自定义 Display 继承 `rviz::Display`，OGRE 渲染
- 三类扩展点共同点：抽象类 + pluginlib 注册 + xml 描述
