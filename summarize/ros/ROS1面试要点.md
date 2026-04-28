# ROS1 面试要点

> 浓缩版：ROS1 架构、通信机制、构建系统与高频面试问答。配合 [ros/ros1/](../../ros/ros1/) 系列文档食用。

---

## 一、ROS1 是什么

- **元操作系统（meta-OS）**：跑在 Linux（主要 Ubuntu）上的中间件 + 工具链，不是真正 OS。
- **三大要素**：通信框架（Topic/Service/Action）、构建系统（catkin）、工具链（rosbag/rqt/rviz/...）。
- **典型版本**：Indigo / Kinetic / Melodic / **Noetic（最后一个 LTS，2025-05 EOL）**。
- **替代品**：ROS2（自 Foxy 起进入工程化），ROS1 不再有新发行版。

---

## 二、核心架构（必背）

```
        ┌──────────────────────┐
        │   ROS Master (单点)   │   注册中心：节点/话题/服务名
        └──┬────────────────┬──┘
           │ XMLRPC         │ XMLRPC
     ┌─────▼─────┐    ┌─────▼─────┐
     │  Node A   │────│  Node B   │   Master 撮合后 P2P 直连
     │ Publisher │TCP │ Subscriber│   传输：TCPROS / UDPROS
     └───────────┘    └───────────┘
```

- **Master / roscore**：集中式名字服务，**单点故障**。
- **节点发现 = XMLRPC**；**数据传输 = TCPROS（默认）/ UDPROS**。
- 一旦发现完成，数据流**完全 P2P**，不经过 Master。

---

## 三、四种通信机制

| 机制 | 模式 | 同步 | 典型用途 |
|------|------|------|----------|
| **Topic** | 多对多发布订阅 | 异步 | 传感器流、状态广播 |
| **Service** | 一对一 RPC | **同步阻塞** | 配置查询、一次性触发 |
| **Action** | 长任务 + 反馈 + 可取消 | 异步 | 导航、抓取等耗时任务 |
| **Parameter** | 参数服务器 KV | 同步 | 配置参数（运行时可改） |

> Action 底层 = 5 个 Topic（goal/cancel/status/feedback/result），由 actionlib 封装。

### 关键代码骨架

```cpp
// Publisher
ros::NodeHandle nh;
auto pub = nh.advertise<std_msgs::Int32>("topic", 10);  // 第二参数=队列长度

// Subscriber
auto sub = nh.subscribe("topic", 10, callback);          // 必须 ros::spin()

// Service Server
auto srv = nh.advertiseService("add", &add_cb);
// Service Client（同步）
ros::ServiceClient cli = nh.serviceClient<srvT>("add");
cli.call(req);   // ⚠️ 阻塞，超时需自己处理
```

---

## 四、catkin 构建（高频）

- **catkin_make**（早期，整体编译）vs **catkin build**（catkin_tools，按包独立编译，推荐）。
- **工作空间结构**：`src/ + build/ + devel/`，`source devel/setup.bash` 设置环境。
- **package.xml**：format 2，声明依赖（`<depend>`、`<build_depend>`、`<exec_depend>`）。
- **CMakeLists.txt 三步曲**：`find_package` → `catkin_package` → `add_executable` + `target_link_libraries`。

### 必踩的坑

- 自定义消息：必须 `add_dependencies(my_node ${${PROJECT_NAME}_EXPORTED_TARGETS} ${catkin_EXPORTED_TARGETS})`，否则编译时找不到生成的头文件。
- 包间依赖：A 用 B 的消息，B 必须 `catkin_package(... CATKIN_DEPENDS message_runtime)`。

---

## 五、roslaunch 与命名空间

```xml
<launch>
  <arg name="rate" default="10"/>
  <group ns="robot1">
    <node pkg="my_pkg" type="talker" name="talker">
      <param name="rate" value="$(arg rate)"/>
      <remap from="chatter" to="/global_chatter"/>
    </node>
  </group>
  <include file="$(find other_pkg)/launch/x.launch"/>
</launch>
```

- **remap 在节点级生效**，可改 topic/service 名；
- **私有参数 `~name`** vs **全局参数 `/name`**；
- `roslaunch` 自动启动 roscore（如果没启动）。

---

## 六、Nodelet（性能利器）

- 同一进程内多个 Nodelet **共享内存指针**（`boost::shared_ptr`），实现**零拷贝**；
- 适合点云、图像等大消息（如 `pcl_ros`/`image_proc`）；
- **是 ROS2 Composition 的前身**。

---

## 七、调试工具速查

| 工具 | 用途 |
|------|------|
| `rostopic list/echo/hz/bw/info` | 话题内省 |
| `rosnode list/info/ping` | 节点状态 |
| `rosservice list/call/info` | 服务调用 |
| `rosparam get/set/dump/load` | 参数操作 |
| `rosbag record/play/info` | 数据录制回放（`.bag`） |
| `rqt_graph` / `rqt_plot` / `rqt_console` | 可视化 |
| `roswtf` | 整体诊断 |
| `rviz` | 3D 可视化 |
| `tf_echo` / `tf view_frames` | TF 树调试 |

---

## 八、ROS1 vs ROS2（一句话版本）

| 维度 | ROS1 | ROS2 |
|------|------|------|
| 中心节点 | **Master 必需** | 无中心，DDS 自动发现 |
| 传输 | TCPROS/UDPROS | DDS（Fast/Cyclone/Connext/Zenoh） |
| QoS | 仅队列长度 | **完整 QoS 体系** |
| 实时 | 不支持 | 支持（PREEMPT_RT + Static Executor） |
| 语言 | roscpp / rospy | rclcpp / rclpy（基于 rcl） |
| 多机 | 配置 ROS_MASTER_URI | DDS 自动发现 |
| 安全 | 无 | SROS2（DDS-Security） |
| 嵌入式 | 不支持 | micro-ROS |
| 构建 | catkin | colcon + ament |

---

## 九、面试高频问答

**Q1：ROS Master 挂了会怎样？**
已经建立的连接**继续工作**（数据流 P2P），但新节点无法加入、无法解析新 topic、无法启动新 service。这是 ROS1 单点故障痛点。

**Q2：Topic 队列满了会丢吗？**
Publisher 端队列满 → **丢最旧**；Subscriber 端队列满 → **丢最旧**。所以队列长度需要根据消费速度合理设置。

**Q3：Service 调用是阻塞的吗？怎么避免卡死？**
**默认同步阻塞**。避免方法：① 用 Action（长任务）；② 自己开线程异步调用；③ 设置超时 `cli.waitForExistence(ros::Duration(1))`。

**Q4：actionlib 和 Service 有什么区别？**
Service 一来一回不可中断；Action 支持**取消**、**进度反馈**、**长时间运行**，底层是 5 个 Topic。

**Q5：rospy 和 roscpp 性能差距？**
rospy 受 GIL 限制，吞吐与延迟均明显劣于 roscpp，CPU 密集型任务建议 C++。

**Q6：Nodelet 为什么快？**
同进程加载 + `shared_ptr` 传指针，避免序列化与拷贝。

**Q7：怎么实现 latched topic？**
`advertise<T>("topic", 1, /*latch=*/true)`。新订阅者会立即收到最近一条（如 `/map`）。**ROS2 用 `TRANSIENT_LOCAL` QoS 替代**。

**Q8：跨主机通信怎么配？**
两台机器 `/etc/hosts` 互相可解析；A 机跑 roscore，两台都设 `ROS_MASTER_URI=http://A:11311`、`ROS_HOSTNAME=自己`。

**Q9：消息版本不一致会怎样？**
节点连接时校验 **MD5 sum**，不匹配 → 拒绝订阅，typical error: `Client wants topic xxx to have datatype/md5sum [...], but our version has [...]`。

**Q10：怎么从 ROS1 迁移到 ROS2？**
1. 先用 `ros1_bridge` 双向转发，新模块写 ROS2，旧模块保留；
2. 替换 catkin → colcon、roscpp → rclcpp；
3. 设置合适 QoS 替代 latched / 队列；
4. Nodelet → Composition。

---

## 十、一行速记

- ROS1 = **Master + TCPROS + catkin + roscpp/rospy**
- 单点故障、无 QoS、无实时、无安全、无嵌入式 → 这些是 ROS2 存在的理由
- Noetic 是终点，新项目应直接上 ROS2
