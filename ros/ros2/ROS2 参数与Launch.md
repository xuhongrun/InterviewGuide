# ROS2 参数与 Launch 系统

> Parameter 提供节点级动态配置，Launch 系统负责**多节点编排启动**。两者构成 ROS2 部署链路的核心。

---

## 一、Parameter（参数）

### 1.1 与 ROS1 的区别

| 维度 | ROS1 | ROS2 |
|------|------|------|
| 存储位置 | 中心化（Master 上的 Parameter Server） | **节点本地**，每个节点独立维护 |
| 类型 | 弱类型（YAML 任意） | **强类型**（bool / int / double / string / array） |
| 变更通知 | 无 | **Parameter Events 话题**（`/parameter_events`） |
| 校验 | 无 | **声明（declare） + 描述符 + 校验回调** |
| 持久化 | Master 内存 | 进程内存（重启丢失，需 YAML 注入） |

### 1.2 声明与读取（C++）

```cpp
// 声明（必须）
this->declare_parameter<double>("max_speed", 1.0);
this->declare_parameter<std::string>("frame_id", "base_link");

// 读取
double v = this->get_parameter("max_speed").as_double();
this->get_parameter_or("frame_id", frame_, std::string("base_link"));

// 写入
this->set_parameter(rclcpp::Parameter("max_speed", 2.0));
```

### 1.3 描述符（约束 + 描述）

```cpp
rcl_interfaces::msg::ParameterDescriptor d;
d.description = "Maximum linear speed";
d.floating_point_range.resize(1);
d.floating_point_range[0].from_value = 0.0;
d.floating_point_range[0].to_value   = 5.0;
d.floating_point_range[0].step       = 0.1;
this->declare_parameter("max_speed", 1.0, d);
```

### 1.4 动态参数变更回调

```cpp
auto cb = [this](const std::vector<rclcpp::Parameter>& params){
    rcl_interfaces::msg::SetParametersResult result;
    result.successful = true;
    for (const auto& p : params) {
        if (p.get_name() == "max_speed" && p.as_double() < 0) {
            result.successful = false;
            result.reason = "must be >= 0";
        }
    }
    return result;
};
on_set_param_handle_ = this->add_on_set_parameters_callback(cb);
```

> Iron+ 推荐使用 `add_post_set_parameters_callback` / `add_pre_set_parameters_callback` 区分校验与生效阶段。

### 1.5 命令行操作

```bash
ros2 param list
ros2 param list /talker
ros2 param get /talker max_speed
ros2 param set /talker max_speed 2.5
ros2 param describe /talker max_speed
ros2 param dump /talker --output-dir ./params
ros2 param load /talker my_params.yaml
```

### 1.6 YAML 注入

```yaml
# params.yaml
talker:
  ros__parameters:
    max_speed: 2.0
    frame_id: "base_link"
    waypoints: [1.0, 2.0, 3.0]
```

启动时：
```bash
ros2 run my_pkg talker --ros-args --params-file params.yaml
```

或在 launch 文件中（见下文）。

### 1.7 命名空间通配符（Iron+）

```yaml
/**:                       # 匹配所有节点
  ros__parameters:
    use_sim_time: true
/robot1/talker:
  ros__parameters:
    max_speed: 2.0
```

---

## 二、Launch 系统

ROS2 用 **Python launch 文件**（`*.launch.py`）替代 ROS1 的 XML，提供更强的编程能力。也支持 XML / YAML 两种声明式格式（适合简单场景）。

### 2.1 最小示例（Python）

```python
# launch/bringup.launch.py
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package="demo_nodes_cpp",
            executable="talker",
            name="talker",
            namespace="robot1",
            output="screen",
            parameters=[{"max_speed": 2.0}],
            remappings=[("chatter", "/global/chatter")],
            arguments=["--ros-args", "--log-level", "INFO"],
        ),
        Node(
            package="demo_nodes_cpp",
            executable="listener",
            name="listener",
            namespace="robot1",
        ),
    ])
```

启动：
```bash
ros2 launch my_pkg bringup.launch.py
```

### 2.2 启动参数（LaunchArgument）

```python
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    use_sim = LaunchConfiguration("use_sim_time")

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        Node(
            package="my_pkg", executable="talker",
            parameters=[{"use_sim_time": use_sim}],
        ),
    ])
```

调用：
```bash
ros2 launch my_pkg bringup.launch.py use_sim_time:=true
```

### 2.3 包含其它 launch

```python
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory
import os

other = IncludeLaunchDescription(
    PythonLaunchDescriptionSource(
        os.path.join(get_package_share_directory("nav2_bringup"),
                     "launch", "bringup_launch.py")),
    launch_arguments={"use_sim_time": "true"}.items(),
)
```

### 2.4 条件与组合动作

```python
from launch.actions import GroupAction, OpaqueFunction, TimerAction
from launch.conditions import IfCondition, UnlessCondition
from launch_ros.actions import PushRosNamespace

GroupAction([
    PushRosNamespace("robot1"),
    Node(package="my_pkg", executable="talker"),
    Node(package="my_pkg", executable="listener",
         condition=IfCondition(LaunchConfiguration("with_listener"))),
])

# 延时启动
TimerAction(period=2.0, actions=[Node(...)])
```

### 2.5 ComposableNodeContainer（组件化启动）

进程内多 Node 共享 Executor，开启零拷贝：

```python
from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode

ComposableNodeContainer(
    name="perception_container",
    namespace="",
    package="rclcpp_components",
    executable="component_container_mt",   # _mt 版本：MultiThreadedExecutor
    composable_node_descriptions=[
        ComposableNode(
            package="image_proc", plugin="image_proc::RectifyNode",
            name="rectify",
            extra_arguments=[{"use_intra_process_comms": True}]),
        ComposableNode(
            package="image_proc", plugin="image_proc::DebayerNode",
            name="debayer",
            extra_arguments=[{"use_intra_process_comms": True}]),
    ],
)
```

详见 `ROS2 生命周期与组件化.md`。

### 2.6 事件处理

```python
from launch.actions import RegisterEventHandler
from launch.event_handlers import OnProcessExit, OnProcessStart

RegisterEventHandler(
    OnProcessExit(
        target_action=talker_node,
        on_exit=[Node(package="my_pkg", executable="finalizer")],
    ),
)
```

### 2.7 XML / YAML 风格（简单场景）

```xml
<!-- bringup.launch.xml -->
<launch>
  <arg name="use_sim_time" default="false"/>
  <node pkg="demo_nodes_cpp" exec="talker" name="talker">
    <param name="max_speed" value="2.0"/>
    <remap from="chatter" to="/global/chatter"/>
  </node>
</launch>
```

---

## 三、参数加载策略

```python
Node(
    package="my_pkg", executable="server",
    parameters=[
        os.path.join(get_package_share_directory("my_pkg"),
                     "config", "params.yaml"),       # YAML 文件
        {"override_param": LaunchConfiguration("x")} # 字典覆盖
    ],
)
```

加载顺序：**后者覆盖前者**。

---

## 四、Namespace 与 Remap

ROS2 支持 launch 级与运行时双重重映射：

```bash
# 节点改名 + 话题重映射 + 命名空间
ros2 run my_pkg talker --ros-args \
    -r __node:=talker_v2 \
    -r __ns:=/robot1 \
    -r chatter:=/global/chatter \
    -p max_speed:=2.0
```

```python
Node(..., remappings=[("/robot1/chatter", "/global/chatter")])
PushRosNamespace("robot1")  # 给同 GroupAction 内全部 Node 加前缀
```

---

## 五、面试速记

- ROS2 参数是**节点本地**的，强类型，支持描述符 + 变更回调 + 通配符 YAML。
- Launch 文件用 **Python**，能编程控制条件、依赖、事件。
- 进程内零拷贝必须 `ComposableNodeContainer` + `use_intra_process_comms`。
- 重映射四件套：`__node` / `__ns` / `topic_remap` / `param`。
