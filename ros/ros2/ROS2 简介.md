# ROS2 简介与整体架构

> ROS2（Robot Operating System 2）是 ROS 的全面重构版本，面向**生产级机器人系统**：去中心化、可配置 QoS、实时友好、跨平台、原生安全。本文从顶层架构切入，后续专题深入展开。

---

## 一、设计目标

| 目标 | 实现手段 |
|------|----------|
| **去中心化** | 基于 DDS Discovery，移除 Master |
| **多机器人/多平台** | DDS 标准 + RMW 抽象层，跨 Linux/Windows/macOS/RTOS |
| **实时性** | 锁无关数据结构、SHM 传输、PREEMPT_RT 支持、静态执行器 |
| **生产级可靠性** | 丰富 QoS、Managed Lifecycle、安全（SROS2） |
| **嵌入式友好** | micro-ROS（基于 micro-XRCE-DDS） |
| **进程内通信** | Composition / Intra-Process Communication（IPC） |

---

## 二、版本与发行节奏

ROS2 采用**字母递增**的发行版命名，每年 5 月发布，对齐 Ubuntu LTS。

| 版本 | 代号 | 发布 | EOL | Ubuntu | 类型 |
|------|------|------|------|--------|------|
| Foxy | Foxy Fitzroy | 2020-06 | 2023-06 | 20.04 | LTS |
| Galactic | — | 2021-05 | 2022-12 | 20.04 | 非 LTS |
| **Humble** | Humble Hawksbill | 2022-05 | **2027-05** | 22.04 | **LTS** |
| Iron | Iron Irwini | 2023-05 | 2024-12 | 22.04 | 非 LTS |
| **Jazzy** | Jazzy Jalisco | 2024-05 | **2029-05** | 24.04 | **LTS** |
| Kilted | Kilted Kaiju | 2025-05 | 2026-12 | 24.04 | 非 LTS |

> 生产项目优先选 **Humble** 或 **Jazzy** LTS。

---

## 三、整体分层架构

```
┌──────────────────────────────────────────────────────────────┐
│  Application Layer                                           │
│   ├─ User Nodes (C++/Python/Rust)                            │
│   ├─ Navigation2 / MoveIt2 / ros2_control / autoware ...     │
│   └─ Lifecycle Nodes / Components                            │
├──────────────────────────────────────────────────────────────┤
│  Client Library Layer                                        │
│   ├─ rclcpp   (C++)                                          │
│   ├─ rclpy    (Python)                                       │
│   ├─ rclrs    (Rust，社区)                                    │
│   └─ 共享 rcl (C 核心) + rcutils / rcl_interfaces             │
├──────────────────────────────────────────────────────────────┤
│  RMW (ROS Middleware) Abstraction                            │
│   ├─ rmw_fastrtps_cpp     (默认，eProsima Fast DDS)           │
│   ├─ rmw_cyclonedds_cpp   (Eclipse Cyclone DDS)              │
│   ├─ rmw_connextdds       (RTI Connext)                      │
│   ├─ rmw_gurumdds         (GurumNetworks)                    │
│   └─ rmw_zenoh_cpp        (Zenoh，Jazzy 起 Tier-1)            │
├──────────────────────────────────────────────────────────────┤
│  DDS / Zenoh Implementation                                  │
│   └─ RTPS / SHM / UDP / TCP / Zenoh protocol                 │
├──────────────────────────────────────────────────────────────┤
│  OS / Network                                                │
└──────────────────────────────────────────────────────────────┘
```

### 关键分层说明

1. **rcl（ROS Client Library）**：C 写的核心实现，所有语言绑定共用，保证语义一致。
2. **rclcpp / rclpy**：用户直接打交道的 API 层，提供 Node、Publisher、Timer、Executor 等抽象。
3. **rmw**：抽象接口（如 `rmw_create_publisher`），不同 DDS 厂商实现各自的 `rmw_*` 包；运行时通过 `RMW_IMPLEMENTATION` 环境变量切换。
4. **DDS/Zenoh**：实际承载发现与数据传输的中间件。

---

## 四、核心概念速览

| 概念 | 说明 | 对应 DDS 概念 |
|------|------|---------------|
| **Node** | 计算单元，可包含多个 Pub/Sub/Server/Client/Timer | DomainParticipant + 内部实体 |
| **Topic** | 命名的异步消息通道 | Topic |
| **Publisher / Subscription** | 单向发布/订阅 | DataWriter / DataReader |
| **Service** | 同步请求/响应（一对一） | 基于两个 Topic 模拟 |
| **Action** | 异步长任务（goal + feedback + result + cancel） | 基于多个 Service + Topic |
| **Parameter** | 节点级动态配置 | 基于 Service + Topic |
| **QoS** | 可靠性/历史/截止时间等策略 | DDS QoS |
| **Executor** | 调度回调（spin） | — |
| **Lifecycle Node** | 受管状态机节点 | — |
| **Component** | 可被 Container 进程动态加载的 Node | — |
| **Domain ID** | 网络隔离 ID（默认 0） | DDS Domain ID |

---

## 五、ROS Domain：网络隔离

- 通过 `ROS_DOMAIN_ID`（0–101 推荐）区分多套独立的 ROS 网络。
- 同 Domain 的节点互相可见，跨 Domain 默认完全隔离。
- 用法：
  ```bash
  export ROS_DOMAIN_ID=42
  ros2 run demo_nodes_cpp talker
  ```
- 多机器协作场景：每台机器人占用独立 Domain ID，避免话题串扰。

---

## 六、与 ROS1 的核心差异（一图速记）

```
            ROS1                                ROS2
   ┌──────────────────┐               ┌──────────────────┐
   │    Master(中心)   │               │   (无 Master)     │
   │   节点注册查找    │               │   DDS 自动发现    │
   └────────┬─────────┘               └──────────────────┘
            │ register
   ┌────────▼─────────┐               ┌──────────────────┐
   │ Node ── TCPROS ──│               │ Node ─ DDS/RTPS ─│
   │ Node             │               │ Node             │
   │ (catkin)         │               │ (colcon + ament) │
   └──────────────────┘               └──────────────────┘
   单点故障 / 无 QoS                  去中心化 / 丰富 QoS
   无实时 / 弱跨平台                  RT 友好 / 全平台
```

---

## 七、典型项目布局（colcon 工作空间）

```
~/ros2_ws/
├── src/
│   ├── my_pkg/
│   │   ├── package.xml          # 包元数据 + 依赖
│   │   ├── CMakeLists.txt       # ament_cmake (C++) 构建
│   │   ├── include/my_pkg/...
│   │   ├── src/...
│   │   ├── launch/bringup.launch.py
│   │   ├── config/params.yaml
│   │   └── msg/MyMsg.msg        # 自定义消息（IDL 风格）
│   └── my_py_pkg/
│       ├── package.xml
│       ├── setup.py             # ament_python
│       └── my_py_pkg/__init__.py
├── build/   ← colcon 生成
├── install/ ← colcon 生成（source 该目录的 setup.bash）
└── log/
```

---

## 八、最小 Hello World

**C++（rclcpp）**：
```cpp
#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/string.hpp>

class Talker : public rclcpp::Node {
public:
    Talker() : Node("talker") {
        pub_ = create_publisher<std_msgs::msg::String>("chatter", 10);
        timer_ = create_wall_timer(std::chrono::milliseconds(100), [this]{
            std_msgs::msg::String msg; msg.data = "hello";
            pub_->publish(msg);
        });
    }
private:
    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr pub_;
    rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char** argv) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<Talker>());
    rclcpp::shutdown();
}
```

**Python（rclpy）**：
```python
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class Listener(Node):
    def __init__(self):
        super().__init__("listener")
        self.create_subscription(String, "chatter", lambda m: self.get_logger().info(m.data), 10)

def main():
    rclpy.init()
    rclpy.spin(Listener())
    rclpy.shutdown()
```

---

## 九、本系列后续专题

| 文件 | 主题 |
|------|------|
| `ROS2 节点与执行器.md` | Node 生命周期、Executor、CallbackGroup、Spin |
| `ROS2 话题、服务与Action.md` | Pub/Sub、Service、Action 详解与对比 |
| `ROS2 参数与Launch.md` | Parameter API、launch.py 写法、组合启动 |
| `ROS2 生命周期与组件化.md` | Managed Lifecycle、Composition、IPC |
| `ROS2 DDS与QoS.md` | RMW 切换、QoS Profile、DDS 调优 |
| `ROS2 TF2与时间.md` | TF Tree、`/clock`、time source |
| `ROS2 colcon与ament.md` | 构建系统、依赖管理、CMake/Python 写法 |
| `ROS2 实时性与性能优化.md` | RT 调度、Zero-Copy、SHM、Loaned Messages |
| `ROS1 vs ROS2 对比.md` | 全面对比、迁移建议 |

---

## 十、面试速记

- ROS2 = **DDS + rcl/rclcpp/rclpy + colcon/ament + Lifecycle/Component**
- 三大支柱：**去中心化（DDS）/ 可配置（QoS）/ 实时与跨平台**
- 优先掌握：**QoS 兼容性匹配、Executor 多线程模型、Composition 进程内零拷贝**
- 生产版本：**Humble**（22.04）或 **Jazzy**（24.04）
