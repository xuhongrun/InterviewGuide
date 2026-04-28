# ROS2 入门教程

> 面向零基础 / 从 ROS1 转 ROS2 的开发者，**一步一步**带你跑通：安装 → 工作空间 → 第一个 C++/Python 节点 → Topic/Service/Action → 参数 → Launch → URDF → RViz。完成本教程后可独立写 ROS2 项目。
>
> 系统要求：Ubuntu 22.04（推荐）或 24.04；本教程以 **ROS2 Humble**（22.04）为例，Jazzy（24.04）几乎相同。
>
> 配套深入文档：
> - [ROS2 简介](ROS2%20简介.md) / [节点与执行器](ROS2%20节点与执行器.md) / [话题、服务与Action](ROS2%20话题、服务与Action.md)
> - [参数与Launch](ROS2%20参数与Launch.md) / [TF2与时间](ROS2%20TF2与时间.md) / [colcon与ament](ROS2%20colcon与ament.md)
> - [项目实战：差速底盘端到端](../common/项目实战-差速底盘端到端.md)

---

## 一、ROS2 是什么（1 分钟）

ROS2 = 一套**机器人软件中间件 + 工具链 + 生态**。
- **中间件**：节点之间通过 DDS 发布/订阅消息（Topic）、远程调用（Service）、长任务（Action）；
- **工具链**：构建（colcon）、可视化（RViz2/Foxglove）、录制回放（rosbag2）、调试（ros2 cli）；
- **生态**：Nav2 导航、MoveIt2 机械臂、ros2_control、SLAM、micro-ROS……

最重要的两个词：
- **节点（Node）**：一个进程，做一件具体事情（如读雷达、规划路径）；
- **话题（Topic）**：节点之间异步广播数据的总线（如 `/scan`、`/cmd_vel`）。

---

## 二、安装 ROS2 Humble（10 分钟）

```bash
# 1. locale
sudo apt update && sudo apt install -y locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

# 2. 添加 ROS2 apt 源
sudo apt install -y software-properties-common curl
sudo add-apt-repository universe
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
     -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" \
| sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# 3. 安装
sudo apt update
sudo apt install -y ros-humble-desktop ros-dev-tools

# 4. 每开终端 source（也可加到 ~/.bashrc）
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

> Jazzy 用户：`humble` 替换为 `jazzy`，系统改 24.04。

验证：
```bash
ros2 --help              # 应输出帮助
ros2 run demo_nodes_cpp talker          # 终端 A：发消息
ros2 run demo_nodes_cpp listener         # 终端 B：收消息
```

看到 `Hello World: 1 / I heard: Hello World: 1` 即安装成功。

---

## 三、ROS2 命令行 10 分钟速通

| 命令 | 作用 |
|------|------|
| `ros2 pkg list` | 列出所有包 |
| `ros2 pkg create <name> --build-type ament_cmake --dependencies rclcpp std_msgs` | 创建包 |
| `ros2 node list` / `ros2 node info /<name>` | 查看节点 |
| `ros2 topic list` / `echo` / `pub` / `info` / `hz` | 话题工具 |
| `ros2 service list` / `call` | 服务工具 |
| `ros2 param list` / `get` / `set` | 参数工具 |
| `ros2 run <pkg> <exe>` | 运行可执行 |
| `ros2 launch <pkg> <file.py>` | 运行 launch 文件 |
| `ros2 bag record -a` / `play` | 录制/回放 |

实战练习（开两个终端）：
```bash
# T1：把 talker 跑起来
ros2 run demo_nodes_cpp talker

# T2：观察
ros2 topic list
ros2 topic echo /chatter
ros2 topic hz /chatter
ros2 topic pub /chatter std_msgs/msg/String "data: 'hi'" -1
```

---

## 四、创建工作空间与第一个包（15 分钟）

ROS2 工作空间约定：
```
~/ros2_ws/
└── src/                # 你的源码包都放这里
```

### 4.1 建工作空间

```bash
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws
colcon build            # 第一次会创建 build/ install/ log/
source install/setup.bash
```

### 4.2 创建 C++ 包

```bash
cd ~/ros2_ws/src
ros2 pkg create my_first_pkg --build-type ament_cmake \
                 --dependencies rclcpp std_msgs \
                 --node-name hello_node
```

生成结构：
```
my_first_pkg/
├── CMakeLists.txt
├── package.xml
├── include/my_first_pkg/
└── src/hello_node.cpp
```

### 4.3 编译并运行

```bash
cd ~/ros2_ws
colcon build --packages-select my_first_pkg
source install/setup.bash
ros2 run my_first_pkg hello_node
```

> **每开新终端**都要 `source install/setup.bash`，否则找不到包。

---

## 五、写一个发布者 / 订阅者（C++）

### 5.1 发布者 `src/talker.cpp`

```cpp
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"
using namespace std::chrono_literals;

class Talker : public rclcpp::Node {
 public:
  Talker() : Node("talker"), count_(0) {
    pub_ = create_publisher<std_msgs::msg::String>("chatter", 10);
    timer_ = create_wall_timer(500ms, [this]() {
      auto msg = std_msgs::msg::String();
      msg.data = "Hello ROS2 #" + std::to_string(count_++);
      RCLCPP_INFO(get_logger(), "Publishing: '%s'", msg.data.c_str());
      pub_->publish(msg);
    });
  }
 private:
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr pub_;
  rclcpp::TimerBase::SharedPtr timer_;
  size_t count_;
};

int main(int argc, char** argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<Talker>());
  rclcpp::shutdown();
  return 0;
}
```

### 5.2 订阅者 `src/listener.cpp`

```cpp
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"

class Listener : public rclcpp::Node {
 public:
  Listener() : Node("listener") {
    sub_ = create_subscription<std_msgs::msg::String>(
        "chatter", 10,
        [this](std_msgs::msg::String::SharedPtr msg) {
          RCLCPP_INFO(get_logger(), "I heard: '%s'", msg->data.c_str());
        });
  }
 private:
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr sub_;
};

int main(int argc, char** argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<Listener>());
  rclcpp::shutdown();
  return 0;
}
```

### 5.3 `CMakeLists.txt` 关键片段

```cmake
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)

add_executable(talker   src/talker.cpp)
add_executable(listener src/listener.cpp)

ament_target_dependencies(talker   rclcpp std_msgs)
ament_target_dependencies(listener rclcpp std_msgs)

install(TARGETS talker listener DESTINATION lib/${PROJECT_NAME})
ament_package()
```

`package.xml` 至少含：
```xml
<depend>rclcpp</depend>
<depend>std_msgs</depend>
```

### 5.4 跑起来

```bash
cd ~/ros2_ws && colcon build --packages-select my_first_pkg && source install/setup.bash
# T1
ros2 run my_first_pkg talker
# T2
ros2 run my_first_pkg listener
```

---

## 六、Python 版本（rclpy）

ROS2 同时支持 C++ 和 Python，**API 几乎一致**。

```bash
cd ~/ros2_ws/src
ros2 pkg create my_py_pkg --build-type ament_python --dependencies rclpy std_msgs
```

`my_py_pkg/my_py_pkg/talker.py`：
```python
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class Talker(Node):
    def __init__(self):
        super().__init__('py_talker')
        self.pub = self.create_publisher(String, 'chatter', 10)
        self.timer = self.create_timer(0.5, self.tick)
        self.i = 0

    def tick(self):
        msg = String()
        msg.data = f'Hello from Python #{self.i}'
        self.i += 1
        self.pub.publish(msg)
        self.get_logger().info(f'Pub: {msg.data}')

def main():
    rclpy.init()
    rclpy.spin(Talker())
    rclpy.shutdown()
```

`setup.py` 注册入口点：
```python
entry_points={
    'console_scripts': [
        'py_talker = my_py_pkg.talker:main',
    ],
},
```

构建运行：
```bash
cd ~/ros2_ws && colcon build --packages-select my_py_pkg && source install/setup.bash
ros2 run my_py_pkg py_talker
```

---

## 七、自定义消息（5 分钟）

新建包 `my_msgs`（必须 `ament_cmake`）：
```bash
cd ~/ros2_ws/src
ros2 pkg create my_msgs --build-type ament_cmake --dependencies rosidl_default_generators std_msgs
```

`my_msgs/msg/Point2D.msg`：
```
float64 x
float64 y
string label
```

`CMakeLists.txt` 增加：
```cmake
find_package(rosidl_default_generators REQUIRED)
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/Point2D.msg"
  DEPENDENCIES std_msgs
)
ament_export_dependencies(rosidl_default_runtime)
```

`package.xml` 增加：
```xml
<buildtool_depend>rosidl_default_generators</buildtool_depend>
<exec_depend>rosidl_default_runtime</exec_depend>
<member_of_group>rosidl_interface_packages</member_of_group>
```

编译后任何包都可 `#include "my_msgs/msg/point2_d.hpp"` 使用。

---

## 八、Service 与 Action 速览

### 8.1 Service（请求-响应，同步）

发起：
```bash
ros2 service call /add_two_ints example_interfaces/srv/AddTwoInts "{a: 3, b: 4}"
```

C++ Server：
```cpp
auto service = node->create_service<example_interfaces::srv::AddTwoInts>(
    "add_two_ints",
    [](const std::shared_ptr<example_interfaces::srv::AddTwoInts::Request> req,
       std::shared_ptr<example_interfaces::srv::AddTwoInts::Response> res) {
      res->sum = req->a + req->b;
    });
```

### 8.2 Action（长任务 + 反馈 + 取消）

适合：导航到目标点、机械臂运动等耗时任务。详见 [ROS2 话题、服务与Action](ROS2%20话题、服务与Action.md)。

选择口诀：
- 周期数据流 → **Topic**
- 一次性短查询 → **Service**
- 长时间任务 + 进度反馈 + 可取消 → **Action**

---

## 九、参数（Parameter）

```cpp
// 声明 + 取值
declare_parameter<double>("speed_limit", 1.0);
double v = get_parameter("speed_limit").as_double();

// 监听变化
auto cb = add_on_set_parameters_callback([](auto params){
    rcl_interfaces::msg::SetParametersResult r; r.successful = true; return r;
});
```

命令行：
```bash
ros2 param list /talker
ros2 param get  /talker speed_limit
ros2 param set  /talker speed_limit 2.0
```

YAML 加载：
```bash
ros2 run my_first_pkg talker --ros-args --params-file params.yaml
```

`params.yaml`：
```yaml
talker:
  ros__parameters:
    speed_limit: 2.5
    enabled: true
```

---

## 十、Launch（一次启动多个节点）

`my_first_pkg/launch/bringup.launch.py`：
```python
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(package='my_first_pkg', executable='talker',   name='talker'),
        Node(package='my_first_pkg', executable='listener', name='listener'),
    ])
```

`CMakeLists.txt` 安装 launch：
```cmake
install(DIRECTORY launch DESTINATION share/${PROJECT_NAME})
```

运行：
```bash
ros2 launch my_first_pkg bringup.launch.py
```

更进阶：参数、命名空间、IfCondition、IncludeLaunchDescription —— 见 [ROS2 参数与Launch高级](ROS2%20参数与Launch高级.md)。

---

## 十一、URDF + RViz 可视化机器人（10 分钟）

新建 `my_robot_desc/urdf/robot.urdf`（最简两轮小车）：
```xml
<?xml version="1.0"?>
<robot name="my_robot">
  <link name="base_link">
    <visual>
      <geometry><box size="0.4 0.3 0.1"/></geometry>
      <material name="blue"><color rgba="0.2 0.4 0.9 1"/></material>
    </visual>
  </link>
  <link name="left_wheel"><visual><geometry><cylinder radius="0.05" length="0.04"/></geometry></visual></link>
  <link name="right_wheel"><visual><geometry><cylinder radius="0.05" length="0.04"/></geometry></visual></link>
  <joint name="left_wheel_joint" type="continuous">
    <parent link="base_link"/><child link="left_wheel"/>
    <origin xyz="0 0.17 0" rpy="1.5708 0 0"/>
    <axis xyz="0 0 1"/>
  </joint>
  <joint name="right_wheel_joint" type="continuous">
    <parent link="base_link"/><child link="right_wheel"/>
    <origin xyz="0 -0.17 0" rpy="1.5708 0 0"/>
    <axis xyz="0 0 1"/>
  </joint>
</robot>
```

启动可视化：
```bash
sudo apt install -y ros-humble-joint-state-publisher-gui ros-humble-robot-state-publisher

# 终端 1：发布 robot_description + TF
ros2 run robot_state_publisher robot_state_publisher \
     --ros-args -p robot_description:="$(xacro robot.urdf)"
# 终端 2：调关节
ros2 run joint_state_publisher_gui joint_state_publisher_gui
# 终端 3：可视化
rviz2
# RViz 中：Fixed Frame 选 base_link，Add → RobotModel（Description Topic: /robot_description）
```

更进阶（xacro / Gazebo / ros2_control）：[ROS2 URDF_xacro与Gazebo](ROS2%20URDF_xacro与Gazebo.md)。

---

## 十二、QoS（质量服务）入门

ROS2 ≠ ROS1：发布者和订阅者 **QoS 不兼容就收不到消息**。

```cpp
auto qos = rclcpp::QoS(10);                       // 默认 RELIABLE / VOLATILE
auto qos_sensor = rclcpp::SensorDataQoS();         // BEST_EFFORT，传感器常用
auto qos_latched = rclcpp::QoS(1).transient_local();// 类似 ROS1 latched
```

经验：
- 普通消息：默认即可；
- LiDAR / IMU 高频流：`SensorDataQoS()` 或 BEST_EFFORT；
- 静态/低频锁存（地图、TF static）：`transient_local()` + `keep_last(1)`；
- **匹配规则**：reliability 与 durability 必须**订阅 ≤ 发布**。

详细见 [ROS2 DDS与QoS](ROS2%20DDS与QoS.md)。

---

## 十三、调试工具速查

| 工具 | 作用 |
|------|------|
| `rqt` | 综合 GUI（拓扑图、控制台、参数面板） |
| `rqt_graph` | 节点-话题拓扑可视化 |
| `ros2 topic hz/bw` | 频率 / 带宽 |
| `ros2 doctor` | 自检环境配置 |
| `ros2 bag record/play` | 录制 mcap，回放调试 |
| `RCUTILS_CONSOLE_OUTPUT_FORMAT` | 自定义日志格式 |
| Foxglove Studio + foxglove_bridge | 现代 Web 可视化（推荐） |
| PlotJuggler | 数值时序绘图 |

详细 → [ROS2 调试诊断与bag](ROS2%20调试诊断与bag.md)、[ROS2 RViz2与可视化](ROS2%20RViz2与可视化.md)。

---

## 十四、新手最常踩 10 个坑

| 问题 | 现因 | 解法 |
|------|------|------|
| `ros2: command not found` | 没 source | `source /opt/ros/humble/setup.bash` |
| `ros2 run` 找不到包 | 没 source overlay | `source ~/ros2_ws/install/setup.bash` |
| 修改 .py 不生效 | 用了 `colcon build` 没用 `--symlink-install` | `colcon build --symlink-install` |
| 收不到消息 | QoS 不匹配 | 用 `ros2 topic info -v` 查 publisher/subscriber QoS |
| 看不到节点 | DOMAIN_ID 不一致 / 多网卡 / 防火墙 | 同 `ROS_DOMAIN_ID`，关防火墙试 |
| `setup.bash` 后 PATH 错乱 | 多 distro 串环境 | 别同时 source humble 和 jazzy |
| `colcon build` 卡住 | 默认并行 + 大依赖 | `colcon build --executor sequential` |
| 找不到自定义消息 | 没在 CMakeLists 调用 `rosidl_generate_interfaces` | 检查 + rebuild |
| Python entry_points 没出现 | `setup.py` 漏写 | 加 `entry_points` 后 rebuild |
| Lookup TF failed | `use_sim_time` 不一致 / 时间戳问题 | 全部节点统一 `use_sim_time:=true` |

---

## 十五、推荐学习路线

1. **本教程** → 跑通 talker/listener、URDF、launch
2. [ROS2 节点与执行器](ROS2%20节点与执行器.md) + [话题、服务与Action](ROS2%20话题、服务与Action.md)：理解执行模型
3. [ROS2 DDS与QoS](ROS2%20DDS与QoS.md)：理解通信底座
4. [URDF/Gazebo](ROS2%20URDF_xacro与Gazebo.md) + [ros2_control](ROS2%20ros2_control与Nav2生态.md)：会描述机器人
5. [SLAM 工具链](ROS2%20SLAM工具链.md) + [Nav2 深入](ROS2%20Nav2深入与BT.md)：建图导航
6. [MoveIt2](ROS2%20MoveIt2.md)：机械臂
7. [生命周期与组件化](ROS2%20生命周期与组件化.md) + [实时性优化](ROS2%20实时性与性能优化.md)：上生产
8. [项目实战：差速底盘](../common/项目实战-差速底盘端到端.md) / [机械臂](../common/项目实战-机械臂pick_place.md)：闭环

---

## 十六、面试速记

- ROS2 三件套：**节点 / 话题 / DDS**
- 工作空间标配：`src/` + `colcon build --symlink-install`
- C++ 用 `rclcpp`，Python 用 `rclpy`，**API 一致**
- 自定义消息须 `rosidl_generate_interfaces` 并加入 `rosidl_interface_packages` group
- 通信选择：周期数据 Topic、短查询 Service、长任务 Action
- **QoS 不匹配是新手最常见的"收不到消息"原因**
- launch 用 Python 脚本（不是 ROS1 的 XML）
- 跑机器人三件套：**robot_state_publisher + ros2_control + RViz2**
- 调试万能：`rqt_graph` / `ros2 topic echo` / `ros2 bag` / Foxglove
