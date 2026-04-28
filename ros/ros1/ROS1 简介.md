# ROS1 简介与架构

> ROS1（Robot Operating System 1）是机器人领域的事实标准框架。本文聚焦顶层架构与版本，详细的通信机制见 [ROS1 通信机制](ROS1%20通信机制.md)，构建工具链见 [ROS1 工具与构建](ROS1%20工具与构建.md)，与 ROS2 的对比见 [ROS1 vs ROS2 对比](ROS1%20vs%20ROS2%20对比.md)。

---

## 一、定位与特点

- **定位**：面向机器人研究与原型开发的**元操作系统**（meta-OS），提供进程间通信、消息序列化、构建系统、可视化与调试工具链。
- **不是**真正的操作系统，而是运行在 Linux（Ubuntu 为主）上的中间件 + 工具集合。
- **设计初衷**：让机器人不同模块（感知/规划/控制/执行）以**节点（Node）+ 话题（Topic）** 的方式松耦合协作。
- **典型版本**：Indigo / Kinetic / Melodic / **Noetic**（最后一个 LTS，对应 Ubuntu 20.04，2025-05 EOL）。

---

## 二、核心架构

```
┌────────────────────────────────────────────────────────────┐
│                       ROS Master                            │
│   （命名服务 / 节点注册 / 话题查找，单点故障）               │
└──────────┬───────────────────────────────────┬─────────────┘
           │ XMLRPC                            │ XMLRPC
   ┌───────▼────────┐                  ┌──────▼─────────┐
   │   Node A       │── TCPROS/UDPROS ─│   Node B       │
   │  (publisher)   │   peer-to-peer   │  (subscriber)  │
   └────────────────┘                  └────────────────┘
```

- **Master（roscore）**：集中式注册中心，所有节点启动时向 Master 注册，发现完成后**点对点直连**传输数据。
- **传输协议**：默认 **TCPROS**（基于 TCP），可选 **UDPROS**（不可靠）。
- **构建系统**：早期 `rosbuild` → 主流 **catkin**（基于 CMake）。
- **包结构**：`package.xml` + `CMakeLists.txt`，源码组织在 `catkin_ws/src` 工作空间下。

---

## 三、通信机制

| 机制 | 用途 | 特点 |
|------|------|------|
| **Topic** | 异步、单向、多对多发布订阅 | 主体通信方式（如 `/scan`、`/cmd_vel`） |
| **Service** | 同步请求/响应（一对一） | 阻塞调用，适合状态查询、配置修改 |
| **Action**（actionlib） | 长耗时任务（带反馈、可取消） | 基于多个 Topic 实现 |
| **Parameter Server** | 全局参数配置（key-value） | 由 Master 维护，所有节点共享 |

---

## 四、常用工具链

- **rosrun / roslaunch**：启动单节点 / 多节点（`.launch` XML 文件）
- **rostopic / rosservice / rosparam / rosnode**：命令行内省工具
- **rqt_*** 系列：图形化调试（`rqt_graph`、`rqt_plot`、`rqt_console`）
- **rviz**：3D 可视化
- **rosbag**：录制/回放话题数据
- **tf / tf2**：坐标系树（TF Tree）管理与变换查询
- **gazebo**：物理仿真

---

## 五、ROS1 的局限（推动 ROS2 诞生）

1. **单点故障**：Master 挂掉则全网瘫痪。
2. **无内置实时性**：基于 TCP/Python 的设计无法满足硬实时要求。
3. **多机部署复杂**：需要配置 `ROS_MASTER_URI` / `ROS_IP`，跨网络穿透差。
4. **无 QoS**：可靠性/历史/截止时间等策略无法配置。
5. **安全性缺失**：无认证、加密。
6. **平台局限**：Windows / 嵌入式 RTOS / 微控制器支持差。
7. **生命周期管理弱**：无标准化的节点状态机。
8. **Python 2 长期绑定**（直到 Noetic 才迁移到 Py3）。

> ROS2 通过引入 **DDS 中间件** 与 **去中心化发现** 系统性地解决了上述问题。

---

## 六、与 ROS2 的关键差异速览

| 维度 | ROS1 | ROS2 |
|------|------|------|
| 中间件 | 自研 TCPROS/UDPROS | **DDS**（可插拔 RMW） |
| 发现机制 | 中心化 Master | **去中心化**（DDS Discovery） |
| 实时性 | 不支持 | 支持（搭配 RT-PREEMPT/Xenomai） |
| QoS | 无 | 丰富（Reliability/Durability/...） |
| 构建系统 | catkin | **colcon + ament** |
| 进程模型 | 多进程 | **进程内组件化（Composition）** |
| 节点生命周期 | 无 | **Managed Lifecycle Node** |
| 安全 | 无 | **SROS2**（DDS-Security） |
| 平台 | Linux 为主 | Linux / Windows / macOS / RTOS |
| Python | rospy（Py2/3） | **rclpy**（Py3） |

---

## 七、典型最小示例

**Publisher（C++/roscpp）**：
```cpp
#include <ros/ros.h>
#include <std_msgs/String.h>

int main(int argc, char** argv) {
    ros::init(argc, argv, "talker");
    ros::NodeHandle nh;
    auto pub = nh.advertise<std_msgs::String>("chatter", 10);
    ros::Rate rate(10);
    while (ros::ok()) {
        std_msgs::String msg;
        msg.data = "hello";
        pub.publish(msg);
        rate.sleep();
    }
}
```

**Subscriber（Python/rospy）**：
```python
import rospy
from std_msgs.msg import String

def cb(msg): rospy.loginfo(msg.data)

rospy.init_node("listener")
rospy.Subscriber("chatter", String, cb)
rospy.spin()
```

---

## 八、面试速记

- ROS1 = **节点 + Master + Topic/Service/Action + catkin**
- 核心痛点：**Master 单点、无 QoS、无实时、跨平台差** → 催生 ROS2
- Noetic 是 ROS1 的终点站，新项目应直接选用 ROS2（Humble/Jazzy）
