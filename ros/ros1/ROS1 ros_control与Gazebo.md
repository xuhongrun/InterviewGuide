# ROS1 ros_control 与 Gazebo 集成

> ros_control（ROS1 版）：通用的硬件抽象 + 控制器框架，与 Gazebo / 真实硬件通用同一份代码。

---

## 一、架构

```
┌──────────────── controller_manager (1 个 Node) ────────────────┐
│  实时循环：read → update(controllers) → write                   │
│                                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │ JointPos     │ │ DiffDrive    │ │ JointTraj    │  controllers│
│  │ Controller   │ │ Controller   │ │ Controller   │            │
│  └──────────────┘ └──────────────┘ └──────────────┘            │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ HardwareInterface                                            ││
│  │   读：position / velocity / effort                           ││
│  │   写：position / velocity / effort                           ││
│  └─────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────┘
                ↓                                  ↓
        Gazebo (gazebo_ros_control)        真实硬件驱动 (CAN/EtherCAT)
```

---

## 二、Transmissions（URDF）

每个**可控关节**必须有对应的 `<transmission>`：

```xml
<transmission name="joint1_trans">
  <type>transmission_interface/SimpleTransmission</type>
  <joint name="joint1">
    <hardwareInterface>hardware_interface/PositionJointInterface</hardwareInterface>
  </joint>
  <actuator name="joint1_motor">
    <hardwareInterface>hardware_interface/PositionJointInterface</hardwareInterface>
    <mechanicalReduction>1</mechanicalReduction>
  </actuator>
</transmission>
```

接口枚举：
- `PositionJointInterface`
- `VelocityJointInterface`
- `EffortJointInterface`
- `JointStateInterface`（只读）

---

## 三、Gazebo 插件

```xml
<gazebo>
  <plugin name="gazebo_ros_control" filename="libgazebo_ros_control.so">
    <robotNamespace>/</robotNamespace>
    <robotSimType>gazebo_ros_control/DefaultRobotHWSim</robotSimType>
  </plugin>
</gazebo>
```

`DefaultRobotHWSim` 自动遍历 transmission，在 Gazebo 关节上模拟读写。

---

## 四、Controller 配置

`config/controllers.yaml`：

```yaml
joint_state_controller:
  type: joint_state_controller/JointStateController
  publish_rate: 50

joint1_position_controller:
  type: position_controllers/JointPositionController
  joint: joint1
  pid: {p: 100, i: 0.01, d: 10}

arm_traj_controller:
  type: position_controllers/JointTrajectoryController
  joints: [joint1, joint2, joint3]
  constraints:
    goal_time: 1.0
    joint1: {trajectory: 0.1, goal: 0.05}

diff_drive_controller:
  type: diff_drive_controller/DiffDriveController
  left_wheel: ['left_wheel_joint']
  right_wheel: ['right_wheel_joint']
  wheel_separation: 0.30
  wheel_radius: 0.05
  publish_rate: 50
  cmd_vel_timeout: 0.5
```

---

## 五、Launch 文件

```xml
<launch>
  <param name="robot_description"
         command="xacro $(find my_pkg)/urdf/robot.urdf.xacro"/>

  <include file="$(find gazebo_ros)/launch/empty_world.launch"/>
  <node name="spawn" pkg="gazebo_ros" type="spawn_model"
        args="-urdf -param robot_description -model my_robot"/>

  <rosparam file="$(find my_pkg)/config/controllers.yaml" command="load"/>

  <node name="ctrl_spawner" pkg="controller_manager" type="spawner"
        args="joint_state_controller arm_traj_controller"/>

  <node pkg="robot_state_publisher" type="robot_state_publisher"
        name="rsp"/>
</launch>
```

---

## 六、操作命令

```bash
rosservice call /controller_manager/list_controllers
rosrun controller_manager controller_manager list
rosrun controller_manager controller_manager load <name>
rosrun controller_manager controller_manager start <name>
rosrun controller_manager controller_manager stop <name>
rosrun controller_manager controller_manager switch \
       --start ctrl_a --stop ctrl_b
```

发指令：

```bash
# 单关节位置
rostopic pub /joint1_position_controller/command std_msgs/Float64 "data: 1.0"

# 轨迹
rostopic pub /arm_traj_controller/command trajectory_msgs/JointTrajectory ...
```

---

## 七、自定义 HardwareInterface（真实硬件）

```cpp
#include <hardware_interface/joint_command_interface.h>
#include <hardware_interface/joint_state_interface.h>
#include <hardware_interface/robot_hw.h>

class MyRobotHW : public hardware_interface::RobotHW {
public:
    MyRobotHW() {
        const std::vector<std::string> names = {"joint1","joint2"};
        pos_.assign(2, 0); vel_.assign(2, 0); eff_.assign(2, 0); cmd_.assign(2, 0);
        for (size_t i = 0; i < 2; ++i) {
            jnt_state_iface_.registerHandle(
                hardware_interface::JointStateHandle(names[i], &pos_[i], &vel_[i], &eff_[i]));
            jnt_pos_iface_.registerHandle(
                hardware_interface::JointHandle(jnt_state_iface_.getHandle(names[i]), &cmd_[i]));
        }
        registerInterface(&jnt_state_iface_);
        registerInterface(&jnt_pos_iface_);
    }
    void read(const ros::Time&, const ros::Duration&) override {
        // pos_[i] = drv.read(i);
    }
    void write(const ros::Time&, const ros::Duration&) override {
        // drv.write(i, cmd_[i]);
    }
private:
    hardware_interface::JointStateInterface  jnt_state_iface_;
    hardware_interface::PositionJointInterface jnt_pos_iface_;
    std::vector<double> pos_, vel_, eff_, cmd_;
};

int main(int argc, char** argv) {
    ros::init(argc, argv, "my_robot_hw");
    ros::NodeHandle nh;
    MyRobotHW hw;
    controller_manager::ControllerManager cm(&hw, nh);

    ros::AsyncSpinner spinner(1); spinner.start();
    ros::Rate rate(100);
    auto last = ros::Time::now();
    while (ros::ok()) {
        auto now = ros::Time::now();
        auto dt  = now - last; last = now;
        hw.read(now, dt);
        cm.update(now, dt);
        hw.write(now, dt);
        rate.sleep();
    }
}
```

---

## 八、控制器选型

| 任务 | 推荐 controller |
|------|----------------|
| 多关节轨迹跟踪（机械臂） | `joint_trajectory_controller` |
| 单关节位置闭环 | `JointPositionController` |
| 速度环（含力矩输出） | `JointVelocityController` + 上层位置环 |
| 差速底盘 | `diff_drive_controller` |
| 全向（mecanum） | `mecanum_drive_controller` |
| Ackermann（车型） | `ackermann_steering_controller` |
| 力 / 阻抗 | `effort_controllers/*` + 自研 |

---

## 九、常见坑

- transmission **不写**或接口与 controller 不匹配 → 控制器 load 失败；
- `joint_state_controller` **必须启动**，否则 `/joint_states` 没有 → TF 也断链；
- Gazebo 物理参数（mass / inertia / damping）不合理 → 控制器抖动 / 发散；
- PID 调参：先 P，再加 I 消除稳态误差，最后 D 抑制超调；
- 真机切换：把 `gazebo_ros_control` 替换为自研 RobotHW，controllers.yaml 完全复用。

---

## 十、面试速记

- ros_control = **HardwareInterface（read/write）+ ControllerManager（update）+ Controller 插件**
- 通过 **transmission** 连接 URDF 关节与 controller 接口
- Gazebo 用 `gazebo_ros_control + DefaultRobotHWSim`
- 真实硬件实现 `RobotHW::read/write` 即可复用所有 controllers
- `joint_state_controller` 必启，否则 TF 断
- 是 **ROS2 ros2_control 的前身**，思想完全一致
