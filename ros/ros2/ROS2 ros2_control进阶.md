# ROS2 ros2_control 进阶

> 在 [ROS2 ros2_control与Nav2生态](ROS2%20ros2_control与Nav2生态.md) 之上深入：链式控制器、传动、admittance/impedance、实时编程模式。

---

## 一、架构回顾

```
┌────────────────────── controller_manager ─────────────────────┐
│  read()   →   update(controllers)   →   write()              │
│   ▲            ▲                          ▼                   │
│   │            │                          │                   │
│  HW state ─ controller chains ─ HW commands                  │
└───────────────────────────────────────────────────────────────┘
        │                                     │
        ▼                                     ▼
   SystemInterface                   /joint_states (sensor_msgs)
   (插件，URDF <ros2_control>)
```

控制循环周期由 `controller_manager` 参数 `update_rate` 决定（典型 100/250/1000 Hz）。

---

## 二、Hardware Interface 三类

| 类 | 用途 |
|----|------|
| `hardware_interface::SystemInterface` | 多关节系统（最常见） |
| `hardware_interface::ActuatorInterface` | 单关节执行器 |
| `hardware_interface::SensorInterface` | 仅传感器 |

骨架：

```cpp
class MyHW : public hardware_interface::SystemInterface {
    CallbackReturn on_init(const HardwareInfo& info) override {
        joint_pos_.resize(info_.joints.size(), 0.0);
        joint_cmd_.resize(info_.joints.size(), 0.0);
        return CallbackReturn::SUCCESS;
    }
    std::vector<StateInterface> export_state_interfaces() override {
        std::vector<StateInterface> v;
        for (size_t i=0; i<info_.joints.size(); ++i) {
            v.emplace_back(info_.joints[i].name, "position", &joint_pos_[i]);
            v.emplace_back(info_.joints[i].name, "velocity", &joint_vel_[i]);
        }
        return v;
    }
    std::vector<CommandInterface> export_command_interfaces() override {
        std::vector<CommandInterface> v;
        for (size_t i=0; i<info_.joints.size(); ++i)
            v.emplace_back(info_.joints[i].name, "position", &joint_cmd_[i]);
        return v;
    }
    return_type read(const Time&, const Duration&) override {
        // 读硬件...
        return return_type::OK;
    }
    return_type write(const Time&, const Duration&) override {
        // 写硬件...
        return return_type::OK;
    }
};
PLUGINLIB_EXPORT_CLASS(MyHW, hardware_interface::SystemInterface)
```

URDF：
```xml
<ros2_control name="MySys" type="system">
  <hardware><plugin>my_pkg/MyHW</plugin></hardware>
  <joint name="joint1">
    <command_interface name="position"/>
    <state_interface name="position"/>
    <state_interface name="velocity"/>
  </joint>
</ros2_control>
```

---

## 三、内置 Controllers

| 控制器 | 命令接口 | 用途 |
|--------|----------|------|
| `joint_state_broadcaster` | (无) | 发布 `/joint_states` |
| `joint_trajectory_controller` | position/velocity | MoveIt 默认执行器 |
| `forward_command_controller` | 任意 | 透传 |
| `effort_controllers/JointGroupEffortController` | effort | 力矩控制 |
| `velocity_controllers/JointGroupVelocityController` | velocity | 速度组 |
| `diff_drive_controller` | velocity | 差速底盘 |
| `tricycle_controller` | velocity+position | 三轮车 |
| `ackermann_steering_controller` | velocity+position | Ackermann |
| `bicycle_steering_controller` | velocity+position | 两轮自行车模型 |
| `admittance_controller` | force/position | 力控/柔顺 |

`controllers.yaml`：

```yaml
controller_manager:
  ros__parameters:
    update_rate: 250
    joint_state_broadcaster:
      type: joint_state_broadcaster/JointStateBroadcaster
    arm_controller:
      type: joint_trajectory_controller/JointTrajectoryController

arm_controller:
  ros__parameters:
    joints: [j1, j2, j3, j4, j5, j6]
    command_interfaces: [position]
    state_interfaces: [position, velocity]
    state_publish_rate: 50.0
    action_monitor_rate: 20.0
    allow_partial_joints_goal: false
```

启动：
```bash
ros2 run controller_manager spawner joint_state_broadcaster
ros2 run controller_manager spawner arm_controller
ros2 control list_controllers
```

---

## 四、链式控制器（chainable controller）

ROS2 新增机制：一个 controller 输出可作为另一个 controller 的输入接口。

例：高层 `pid_controller` 输出 velocity → 低层 `velocity_controller` 输入 velocity → 写硬件。

```yaml
high_level:
  type: pid_controller/PidController
  reference_and_state_interfaces: [pos]
  command_interfaces: [vel]      # 暴露给下游

low_level:
  type: velocity_controllers/JointGroupVelocityController
  joints: [j1]
  reference_interface: high_level/j1/vel    # 链式引用
```

执行顺序由依赖关系自动推导。

---

## 五、Transmissions

ROS2 中 transmission 用 `transmission_interface` 库，将 actuator 空间映射到 joint 空间（齿轮比 / 差速 / 平行四杆）。

```xml
<transmission name="trans1">
  <plugin>transmission_interface/SimpleTransmission</plugin>
  <actuator name="motor1" role="actuator1"/>
  <joint name="joint1" role="joint1"/>
  <mechanical_reduction>50</mechanical_reduction>
</transmission>
```

---

## 六、admittance / impedance（柔顺控制）

`admittance_controller` 模型：
$$
M\ddot{x} + D\dot{x} + K(x - x_d) = F_{ext}
$$
力 → 期望位置 / 速度。

```yaml
admittance_controller:
  type: admittance_controller/AdmittanceController
  joints: [j1, j2, j3, j4, j5, j6]
  command_interfaces: [position, velocity]
  state_interfaces:   [position, velocity]
  ft_sensor:
    name: tcp_fts_sensor
    frame: tool0
  control: { frame: { id: base_link } }
  admittance:
    selected_axes: [true, true, true, false, false, false]
    mass:      [3.0, 3.0, 3.0, 1.0, 1.0, 1.0]
    damping_ratio: [2.0, 2.0, 2.0, 1.0, 1.0, 1.0]
    stiffness: [50.0, 50.0, 50.0, 5.0, 5.0, 5.0]
```

需要 6 轴 F/T 传感器接入 SensorInterface。

---

## 七、实时安全编程

控制循环硬实时（≤1ms）需保证 `update()` **无阻塞**：

| 禁忌 | 替代 |
|------|------|
| `new` / `delete` / `malloc` | 预分配、`realtime_tools::RealtimeBuffer` |
| `std::mutex`（可能优先级反转） | `realtime_tools::RealtimeBox`（lock-free） |
| `RCLCPP_INFO` | `RCLCPP_INFO_THROTTLE`、低速旁路 |
| `rclcpp::spin` 在 update 内 | 拒绝；用回调线程接收，update 只读取 buffer |
| `std::cout` / 文件 IO | 全部移出 |

```cpp
realtime_tools::RealtimeBuffer<TwistMsg> cmd_buf_;
sub_ = node->create_subscription<TwistMsg>("cmd_vel", 1,
    [this](const TwistMsg::SharedPtr m){ cmd_buf_.writeFromNonRT(*m); });

// update() 中
auto cmd = cmd_buf_.readFromRT();
```

进程级：
```bash
sudo chrt -f 80 ros2 run controller_manager ros2_control_node
```

PREEMPT_RT 内核 + CPU isolation 是工业部署常见配置。

---

## 八、热插拔与故障注入

`controller_manager` service：
- `/controller_manager/load_controller`
- `/controller_manager/configure_controller`
- `/controller_manager/switch_controller`：可在运行中切换 active controllers（例如安全模式 → 工作模式）
- `/controller_manager/unload_controller`

```bash
ros2 control switch_controllers --activate emergency_stop --deactivate arm_controller
```

---

## 九、常见坑

| 现象 | 排查 |
|------|------|
| controller spawn 卡住 | URDF 中接口与 controller 配置不匹配 |
| update_rate 跑不满 | hardware read/write 太慢；放独立线程 |
| 抖动 | 非 RT 内核 / 抢占 / IO 阻塞 |
| 链式控制器无效 | 引用名称写错；reference_interface 必须 `<ctrl_name>/<joint>/<iface>` |
| MoveIt 执行轨迹失败 | 未启用 `joint_trajectory_controller` 或 PID 没调好 |

---

## 十、面试速记

- 三类 HW：**System / Actuator / Sensor**，URDF `<ros2_control>` 描述
- 控制器链式：上游 `command_interface` 暴露为下游 `reference_interface`
- 工业柔顺：**admittance_controller**（M/D/K + 6 轴 F/T）
- 实时编程：禁 new/锁/log；用 **RealtimeBuffer / RealtimeBox**
- 热切换：`switch_controllers` 实现紧急停 / 工作模式
- 部署：**PREEMPT_RT + chrt + CPU isolation**
