# ROS2 生命周期与组件化

> 两个生产级特性：**Managed Lifecycle Node**（标准化状态机管理） 与 **Composition / Components**（进程内多节点 + 零拷贝）。在 Navigation2、ros2_control、Autoware 中大量使用。

---

## 一、Managed Lifecycle Node

### 1.1 动机

普通 Node 启动即工作，运维难以**统一控制初始化、运行、暂停、关闭顺序**。Lifecycle Node 引入 OMG 标准的状态机，让上层（如 Nav2 BT）能：

- 控制整套子系统的启停顺序；
- 在不杀进程的前提下重新配置；
- 故障恢复时只重启失效模块。

### 1.2 状态机（4 主态 + 6 过渡态）

```
            ┌──────────────────┐
            │  Unconfigured    │  (初始态)
            └────────┬─────────┘
              configure │  ↑ cleanup
            ┌────────▼─────────┐
            │     Inactive     │  (已配置，未运行)
            └────┬─────────┬───┘
       activate │       ↑ deactivate
            ┌───▼─────────┴───┐
            │      Active     │  (正常运行)
            └────────┬────────┘
                     │ shutdown
            ┌────────▼─────────┐
            │     Finalized    │
            └──────────────────┘

异常态：ErrorProcessing
过渡态：configuring / cleaningUp / activating / deactivating / shuttingDown / errorProcessing
```

### 1.3 C++ 实现要点

```cpp
#include "rclcpp_lifecycle/lifecycle_node.hpp"
using CallbackReturn = rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn;

class MySensor : public rclcpp_lifecycle::LifecycleNode {
public:
    MySensor() : LifecycleNode("my_sensor") {}

    CallbackReturn on_configure(const rclcpp_lifecycle::State&) override {
        pub_ = create_publisher<std_msgs::msg::String>("data", 10);
        // 申请资源、读参数、打开设备...
        return CallbackReturn::SUCCESS;
    }
    CallbackReturn on_activate(const rclcpp_lifecycle::State& s) override {
        LifecycleNode::on_activate(s);  // 激活所有 LifecyclePublisher
        timer_ = create_wall_timer(100ms, [this]{ pub_->publish(...); });
        return CallbackReturn::SUCCESS;
    }
    CallbackReturn on_deactivate(const rclcpp_lifecycle::State& s) override {
        LifecycleNode::on_deactivate(s);
        timer_.reset();
        return CallbackReturn::SUCCESS;
    }
    CallbackReturn on_cleanup(const rclcpp_lifecycle::State&) override {
        pub_.reset(); /* 释放设备 */
        return CallbackReturn::SUCCESS;
    }
    CallbackReturn on_shutdown(const rclcpp_lifecycle::State&) override {
        return CallbackReturn::SUCCESS;
    }

private:
    rclcpp_lifecycle::LifecyclePublisher<std_msgs::msg::String>::SharedPtr pub_;
    rclcpp::TimerBase::SharedPtr timer_;
};
```

> 关键点：必须使用 `LifecyclePublisher`，它在非 Active 态下会丢弃发布；订阅则始终接收（设计选择）。

### 1.4 命令行操作

```bash
ros2 lifecycle nodes
ros2 lifecycle list /my_sensor
ros2 lifecycle get  /my_sensor
ros2 lifecycle set  /my_sensor configure
ros2 lifecycle set  /my_sensor activate
ros2 lifecycle set  /my_sensor deactivate
ros2 lifecycle set  /my_sensor cleanup
```

### 1.5 与 Launch 的整合

```python
from launch_ros.actions import LifecycleNode
from launch.actions import EmitEvent, RegisterEventHandler
from launch_ros.events.lifecycle import ChangeState
from launch_ros.event_handlers import OnStateTransition
from lifecycle_msgs.msg import Transition

node = LifecycleNode(package="my_pkg", executable="my_sensor",
                     name="my_sensor", namespace="")

emit_configure = EmitEvent(event=ChangeState(
    lifecycle_node_matcher=lambda n: n is node,
    transition_id=Transition.TRANSITION_CONFIGURE))

# Inactive → Active
on_inactive = RegisterEventHandler(OnStateTransition(
    target_lifecycle_node=node, goal_state="inactive",
    entities=[EmitEvent(event=ChangeState(
        lifecycle_node_matcher=lambda n: n is node,
        transition_id=Transition.TRANSITION_ACTIVATE))]))
```

### 1.6 Nav2 中的应用

Nav2 的 `lifecycle_manager` 会按依赖顺序对 `controller_server` / `planner_server` / `bt_navigator` / `amcl` 等 Lifecycle Node **批量** configure → activate，启动失败可统一回滚。

---

## 二、Composition（组件化）

### 2.1 为什么需要

ROS1 中“一个节点一个进程”模型导致：
- IPC 必须经过序列化 + 网络/loopback；
- 进程数过多，调度/内存开销大。

ROS2 把节点抽象为 **Component（动态库的一个类）**，由 **Container 进程**通过插件机制加载，多个 Node 共享同一进程的：
- **Executor**（统一调度）
- **DDS Participant**
- **内存空间** → 启用 IPC（Intra-Process Communication）实现**零拷贝**

### 2.2 编写一个 Component

```cpp
// my_pkg/include/my_pkg/talker.hpp
#include <rclcpp/rclcpp.hpp>
namespace my_pkg {
class Talker : public rclcpp::Node {
public:
    explicit Talker(const rclcpp::NodeOptions& opts) : Node("talker", opts) {
        pub_ = create_publisher<std_msgs::msg::String>("chatter", 10);
        timer_ = create_wall_timer(500ms, [this]{ /*...*/ });
    }
private:
    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr pub_;
    rclcpp::TimerBase::SharedPtr timer_;
};
}
```

```cpp
// src/talker.cpp
#include "my_pkg/talker.hpp"
#include <rclcpp_components/register_node_macro.hpp>
RCLCPP_COMPONENTS_REGISTER_NODE(my_pkg::Talker)
```

`CMakeLists.txt`：
```cmake
add_library(talker_component SHARED src/talker.cpp)
ament_target_dependencies(talker_component rclcpp rclcpp_components std_msgs)
rclcpp_components_register_nodes(talker_component "my_pkg::Talker")

install(TARGETS talker_component
        ARCHIVE DESTINATION lib
        LIBRARY DESTINATION lib
        RUNTIME DESTINATION bin)
ament_export_libraries(talker_component)
```

### 2.3 三种容器进程

| 可执行 | 调度模型 | 用途 |
|--------|----------|------|
| `component_container` | SingleThreadedExecutor | 简单组合 |
| `component_container_mt` | MultiThreadedExecutor | 推荐：并发回调 |
| `component_container_isolated` | 每 Node 独立线程 | 强隔离需求 |

### 2.4 加载方式

**命令行动态加载**：
```bash
ros2 run rclcpp_components component_container_mt &
ros2 component load /ComponentManager my_pkg my_pkg::Talker
ros2 component list
ros2 component unload /ComponentManager 1
```

**Launch 静态加载**（推荐生产用）：
```python
ComposableNodeContainer(
    name="perception", namespace="",
    package="rclcpp_components", executable="component_container_mt",
    composable_node_descriptions=[
        ComposableNode(
            package="image_proc", plugin="image_proc::RectifyNode",
            name="rectify",
            extra_arguments=[{"use_intra_process_comms": True}]),
        ComposableNode(
            package="my_pkg", plugin="my_pkg::Talker", name="talker",
            extra_arguments=[{"use_intra_process_comms": True}]),
    ],
)
```

### 2.5 Intra-Process Communication（IPC）

启用条件：
1. Pub/Sub 都在**同一进程**且**同一 Executor**；
2. `NodeOptions::use_intra_process_comms(true)`；
3. **QoS 一致**且 `Reliability=RELIABLE`，`History=KEEP_LAST`，`Durability=VOLATILE`（注意：`TRANSIENT_LOCAL` **不支持** IPC）；
4. 消息类型为可托管的 C++ 类型（不是 IDL 占位符）。

发布方式（实现真正零拷贝）：
```cpp
// 移动语义（一个订阅者）→ 直接转移所有权
auto msg = std::make_unique<std_msgs::msg::String>();
msg->data = "zero copy!";
pub_->publish(std::move(msg));
```

> 多订阅者 + IPC 时退化为共享 `const&`，仍然零拷贝读，但不能修改。

### 2.6 Loaned Messages（跨进程零拷贝）

DDS 厂商支持下（如 iceoryx via rmw_cyclonedds + iceoryx2，Fast DDS SHM），可使用：
```cpp
auto loaned = pub_->borrow_loaned_message();
loaned.get().data = ...;
pub_->publish(std::move(loaned));
```

数据放在共享内存池中，订阅者直接映射，避免序列化。详见 `ROS2 实时性与性能优化.md`。

---

## 三、Lifecycle + Component 组合

Nav2 的 `composable_nodes_with_lifecycle` 模式：把 Lifecycle Node 作为 Component 加载到容器，再由 lifecycle_manager 批量管理状态。这是**生产级 ROS2 系统的标准结构**：

```
┌─────────────────── nav2_container_mt 进程 ──────────────────┐
│  ┌─ controller_server (Lifecycle Component) ──────────────┐ │
│  │   Pub /cmd_vel  Sub /odom  Action /follow_path         │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌─ planner_server (Lifecycle Component)  ────────────────┐ │
│  └────────────────────────────────────────────────────────┘ │
│  Executor: MultiThreadedExecutor                            │
│  Intra-Process Communication: ON (零拷贝)                    │
└─────────────────────────────────────────────────────────────┘
        ▲ 由外部 lifecycle_manager 统一 configure/activate
```

---

## 四、面试速记

- **Lifecycle Node**：4 主态（Unconfigured / Inactive / Active / Finalized），用 `LifecyclePublisher` 在非 Active 时丢弃发布。
- **Composition**：动态库 + `RCLCPP_COMPONENTS_REGISTER_NODE`，通过 Container 加载。
- **IPC** 启用三件套：同进程同 Executor、`use_intra_process_comms=true`、QoS 兼容（VOLATILE + KEEP_LAST + RELIABLE）。
- 真零拷贝发布：`std::unique_ptr<Msg>` + `std::move`；跨进程零拷贝靠 **Loaned Messages + SHM**。
- 生产架构：**Lifecycle Component + MultiThreadedContainer + IPC**。
