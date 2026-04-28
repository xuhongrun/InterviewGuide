# ROS2 参数与 Launch 高级技巧

> 在 [ROS2 参数与Launch](ROS2%20参数与Launch.md) 基础上，覆盖：参数事件订阅、动态参数、launch_testing、OpaqueFunction、PythonExpression、Lifecycle 与 Launch 联动。

---

## 一、ParameterEventHandler（事件订阅）

```cpp
#include <rclcpp/parameter_event_handler.hpp>

auto param_subscriber = std::make_shared<rclcpp::ParameterEventHandler>(node);
auto cb = [](const rclcpp::Parameter& p){
    RCLCPP_INFO(rclcpp::get_logger("p"), "received %s = %f",
                p.get_name().c_str(), p.as_double());
};
auto handle = param_subscriber->add_parameter_callback(
    "speed_limit", cb, /*node_name=*/"controller_node");
// 持有 handle 期间回调有效
```

特点：
- 跨节点监听（指定目标节点名）；
- 比 ROS1 `dynamic_reconfigure` 更通用；
- 与 `set_on_parameters_set_callback`（**本节点**校验）配合使用。

Python：
```python
from rclpy.parameter_event_handler import ParameterEventHandler
peh = ParameterEventHandler(self)
handle = peh.add_parameter_callback("speed_limit", "controller_node",
    lambda p: self.get_logger().info(f"new={p.value}"))
```

---

## 二、参数校验与拒绝

```cpp
node->add_on_set_parameters_callback(
    [](const std::vector<rclcpp::Parameter>& params){
        rcl_interfaces::msg::SetParametersResult res; res.successful = true;
        for (auto& p : params) {
            if (p.get_name() == "max_vel" && p.as_double() > 5.0) {
                res.successful = false;
                res.reason = "max_vel exceeds 5.0";
            }
        }
        return res;
    });
```

类型/范围用 **descriptor**：
```cpp
rcl_interfaces::msg::ParameterDescriptor d;
d.description = "Maximum velocity m/s";
rcl_interfaces::msg::FloatingPointRange r; r.from_value = 0; r.to_value = 5; r.step = 0.1;
d.floating_point_range = {r};
node->declare_parameter<double>("max_vel", 1.0, d);
```

---

## 三、Launch.py 高级特性

### 3.1 LaunchConfiguration / DeclareLaunchArgument

```python
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

ld = LaunchDescription()
ld.add_action(DeclareLaunchArgument("use_sim_time", default_value="false"))
use_sim = LaunchConfiguration("use_sim_time")
```

### 3.2 OpaqueFunction（运行时计算）

需要在 launch 计算时使用 LaunchConfiguration 的**实际值**：

```python
from launch.actions import OpaqueFunction

def launch_setup(context, *args, **kwargs):
    robot_name = LaunchConfiguration("robot_name").perform(context)
    if robot_name.startswith("car_"):
        # 动态构造节点列表
        return [Node(package="...", namespace=robot_name, ...)]
    return []

ld.add_action(OpaqueFunction(function=launch_setup))
```

### 3.3 PythonExpression / TextSubstitution

```python
from launch.substitutions import PythonExpression, TextSubstitution

# 条件判断
condition_expr = PythonExpression(["'", LaunchConfiguration("mode"), "' == 'sim'"])
Node(..., condition=IfCondition(condition_expr))
```

`AndSubstitution` / `OrSubstitution` / `NotSubstitution` 也可组合。

### 3.4 IncludeLaunchDescription

```python
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource

include = IncludeLaunchDescription(
    PythonLaunchDescriptionSource([
        FindPackageShare("nav2_bringup"), "/launch/bringup_launch.py"]),
    launch_arguments={"use_sim_time": "true",
                       "params_file": params_file}.items())
```

### 3.5 GroupAction + PushRosNamespace

```python
from launch.actions import GroupAction
from launch_ros.actions import PushRosNamespace

GroupAction([
    PushRosNamespace("robot1"),
    Node(package="...", executable="..."),
])
```

### 3.6 RegisterEventHandler

监听节点退出 / 启动信号：

```python
from launch.actions import RegisterEventHandler
from launch.event_handlers import OnProcessExit, OnProcessStart

RegisterEventHandler(
    OnProcessExit(target_action=node_a,
                  on_exit=[LogInfo(msg="A exited"), node_b]))
```

---

## 四、Lifecycle 与 Launch 联动

`launch_ros.actions.LifecycleNode` + `events_to_request_state_transition`：

```python
from launch_ros.actions import LifecycleNode, Node
from launch.actions import EmitEvent, RegisterEventHandler
from launch_ros.events.lifecycle import ChangeState
from launch_ros.event_handlers import OnStateTransition
import lifecycle_msgs.msg

ln = LifecycleNode(name="motor",
                   package="my_pkg", executable="motor_node",
                   namespace="")

# 启动后立刻 configure
configure = EmitEvent(event=ChangeState(
    lifecycle_node_matcher=launch.events.matches_action(ln),
    transition_id=lifecycle_msgs.msg.Transition.TRANSITION_CONFIGURE))

# inactive 后自动 activate
activate_after_configure = RegisterEventHandler(OnStateTransition(
    target_lifecycle_node=ln,
    goal_state="inactive",
    entities=[EmitEvent(event=ChangeState(
        lifecycle_node_matcher=launch.events.matches_action(ln),
        transition_id=lifecycle_msgs.msg.Transition.TRANSITION_ACTIVATE))]))
```

或简单做法：用 `nav2_lifecycle_manager` 自动管理一组节点。

---

## 五、launch_testing：自动化测试

```python
# my_pkg/test/test_my_node.launch.py
import launch
import launch_ros.actions
import launch_testing.actions
import unittest

def generate_test_description():
    node = launch_ros.actions.Node(
        package="my_pkg", executable="my_node", output="screen")
    return launch.LaunchDescription([
        node,
        launch_testing.actions.ReadyToTest()
    ]), {"node": node}

class MyNodeTest(unittest.TestCase):
    def test_publish(self, proc_output, node):
        proc_output.assertWaitFor("Ready", process=node, timeout=5)
```

CMakeLists：
```cmake
if(BUILD_TESTING)
  find_package(launch_testing_ament_cmake REQUIRED)
  add_launch_test(test/test_my_node.launch.py)
endif()
```

---

## 六、参数 YAML 多节点

```yaml
/**:
  ros__parameters:
    use_sim_time: true

robot1/controller:
  ros__parameters:
    rate: 50.0

robot2/controller:
  ros__parameters:
    rate: 100.0
```

`/**` 通配匹配所有节点。

---

## 七、Substitutions 速查

| 替换 | 用途 |
|------|------|
| `LaunchConfiguration("x")` | 读取参数 |
| `EnvironmentVariable("ROS_DOMAIN_ID")` | 读环境变量 |
| `FindPackageShare("pkg")` | 包 share 目录 |
| `PathJoinSubstitution([...])` | 路径拼接 |
| `Command(["xacro", " ", file])` | 运行命令取 stdout |
| `ParameterValue(..., value_type=str)` | 强制类型 |
| `ThisLaunchFileDir()` | 当前 launch 文件目录 |

---

## 八、面试速记

- 跨节点监听参数变化：**`ParameterEventHandler`**
- 校验/拒绝写：`add_on_set_parameters_callback`，配合 **descriptor 范围**
- launch.py 动态逻辑用 **`OpaqueFunction`** 取得 LaunchConfiguration 真实值
- 条件用 `IfCondition` + `PythonExpression`
- Lifecycle 自动起停：`EmitEvent(ChangeState)` + `OnStateTransition`，或直接 `nav2_lifecycle_manager`
- 集成测试：**`launch_testing` + `ReadyToTest`**，CMake `add_launch_test`
- 多节点 YAML 用 `/**` 通配
