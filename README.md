# InterviewGuide

> 一份面向 **C++ / Python / DDS / ROS2** 方向的技术面试知识库，涵盖核心语言特性、分布式中间件、机器人框架、网络协议及项目实战经验总结。适合有一定工程经验的开发者在面试前系统复习。

---

## 📚 内容模块

### 💻 C++ [`cpp/`](cpp/)

涵盖现代 C++ 的核心知识点，每个文件独立成章，可按需查阅：

| 文件 | 内容简介 |
|------|----------|
| [C++ 最佳实践](cpp/C++%20最佳实践.md) | ⭐ RAII / Rule of Zero / 现代 C++17/20 / Sanitizer / Top 20 Checklist |
| [C++ 简介](cpp/C++%20简介.md) | C++ 标准演进、编译流程、核心特性概览 |
| [C++ 移动语义与完美转发](cpp/C++%20移动语义与完美转发.md) | 值类别 / 右值引用 / `std::move` / `std::forward` / Rule of 5 / NRVO |
| [C++ 数据类型](cpp/C++%20数据类型.md) | 基本类型、类型转换、`sizeof` 等 |
| [C++ 指针、智能指针、引用](cpp/C++%20指针、智能指针、引用.md) | 裸指针、`unique_ptr`/`shared_ptr`/`weak_ptr`、循环引用 |
| [C++ 内存管理](cpp/C++%20内存管理.md) | 堆栈分配、`new`/`delete`、内存对齐、RAII |
| [C++ 类（Class）](cpp/C++%20类（Class）.md) | 构造/析构、拷贝控制、`static`/`const` 成员 |
| [C++ 继承](cpp/C++%20继承.md) | 单继承、多继承、虚继承、菱形继承 |
| [C++ 多态](cpp/C++%20多态.md) | 虚函数表（vtable）、`override`/`final`、纯虚函数 |
| [C++ 模板](cpp/C++%20模板.md) | 函数模板、类模板、模板特化、CRTP |
| [C++ Lambda 表达式](cpp/C++%20Lambda%20表达式.md) | 捕获列表、可变 lambda、泛型 lambda |
| [C++ 容器](cpp/C++%20容器.md) | `vector`/`map`/`unordered_map` 等底层实现与复杂度 |
| [C++ 字符串](cpp/C++%20字符串.md) | `string` 操作、`string_view`、格式化 |
| [C++ 多线程](cpp/C++%20多线程.md) | `thread`、`mutex`、`condition_variable`、`atomic` |
| [C++ 进程 线程](cpp/C++%20进程%20线程.md) | 进程与线程的区别、创建与管理 |
| [C++ 进程间通信（IPC）](cpp/C++%20进程间通信（IPC）.md) | 管道、消息队列、共享内存、信号量、Socket |
| [C++ 线程池](cpp/C++%20线程池.md) | 线程池设计与实现 |
| [C++ 任务队列](cpp/C++%20任务队列.md) | 无锁队列、任务调度 |
| [C++ 单例模式 实现](cpp/C++%20单例模式%20实现.md) | 懒汉式、饿汉式、`Meyers` Singleton |
| [C++ 结构体（Struct）](cpp/C++%20结构体（Struct）.md) | 与 class 的区别、内存布局、位字段 |
| [C++ 预处理器（Preprocessor）](cpp/C++%20预处理器（Preprocessor）.md) | 宏、条件编译、`#include` 防卫 |
| [C++ 数组类型](cpp/C++%20数组类型.md) | 原生数组、`std::array`、动态数组 |
| [C++ 格式说明符](cpp/C++%20格式说明符.md) | `printf`/`scanf` 格式说明符速查 |

#### Eigen 线性代数库 [`cpp/eigen/`](cpp/eigen/)

| 文件 | 内容简介 |
|------|----------|
| [Eigen_最佳实践](cpp/eigen/Eigen_最佳实践.md) | ⭐ 类型选择 / `auto` 陷阱 / `Ref<>` / Map 零拷贝 / Top 20 Checklist |
| [Eigen_01_入门与基本类型](cpp/eigen/Eigen_01_入门与基本类型.md) | Matrix/Vector 类型、初始化、表达式模板 |
| [Eigen_02_矩阵与向量操作](cpp/eigen/Eigen_02_矩阵与向量操作详解.md) | 运算、切片 (3.4)、Ref<> 、数值健壮性 |
| [Eigen_03_线性方程与分解](cpp/eigen/Eigen_03_线性方程组求解与矩阵分解.md) | LU/Cholesky/QR/SVD 选型 |
| [Eigen_04_特征值与几何变换](cpp/eigen/Eigen_04_特征值分解SVD与几何变换.md) | EigenSolver / SelfAdjoint / Quaternion |
| [Eigen_05_稀疏矩阵与性能](cpp/eigen/Eigen_05_稀疏矩阵性能优化与工程实战.md) | Triplet / SimplicialLLT / SparseQR |
| [Eigen_06_ROS_SLAM互操作](cpp/eigen/Eigen_06_ROS_SLAM生态互操作.md) | OpenCV / ROS msg / g2o / Ceres |
| [Eigen_07_unsupported与优化](cpp/eigen/Eigen_07_unsupported模块与非线性优化.md) | AutoDiff / Spline / NonLinearOptimization |

---

### 🐍 Python [`python/`](python/)

覆盖 Python 高频面试点与工程实践：

| 文件 | 内容简介 |
|------|----------|
| [Python 最佳实践](python/Python%20最佳实践.md) | ⭐ 类型注解 / asyncio / Ruff / pytest / 安全 / Top 20 Checklist |
| [Python 异步编程 asyncio](python/Python%20异步编程%20asyncio.md) | 事件循环 / TaskGroup / 超时与取消 / uvloop / 常见坑 |
| [Python 类 Class](python/Python%20类%20Class.md) | 继承、`MRO`、`__slots__`、元类 |
| [Python 装饰器](python/Python%20装饰器.md) | 函数装饰器、类装饰器、装饰器链 |
| [Python 内置装饰器](python/Python%20内置装饰器.md) | `@property`、`@classmethod`、`@staticmethod` |
| [Python 迭代器与生成器](python/Python%20迭代器与生成器.md) | `__iter__`/`__next__`、`yield`、惰性求值 |
| [Python Lambda 表达式](python/Python%20Lambda%20表达式.md) | 匿名函数、与 `map`/`filter`/`sorted` 配合 |
| [Python 多线程](python/Python%20多线程.md) | GIL、`threading` 模块、线程同步 |
| [Python 多进程](python/Python%20多进程.md) | `multiprocessing`、进程池、共享内存 |
| [Python 并发](python/Python%20并发.md) | `asyncio`、协程、`async`/`await` |
| [Python 正则表达式](python/Python%20正则表达式.md) | `re` 模块、常用模式、命名分组 |
| [Python 内置函数](python/Python%20内置函数.md) | `map`/`filter`/`zip`/`enumerate` 等速查 |
| [Python 数据类型转换](python/Python%20数据类型转换.md) | 隐式/显式转换、`int`/`str`/`list` 互转 |

---

### 📡 DDS（数据分发服务）[`dds/`](dds/)

DDS（Data Distribution Service）是面向实时分布式系统的发布/订阅中间件，广泛用于自动驾驶、机器人等领域：

| 文件 | 内容简介 |
|------|----------|
| [DDS 最佳实践](dds/DDS%20最佳实践.md) | ⭐ Domain/Partition / QoS 三组合 / 零拷贝 / 发现服务器 / Top 20 Checklist |
| [DDS 概述](dds/DDS.md) | DDS 架构、核心概念（Domain / Topic / DataWriter / DataReader） |
| [DDS QoS](dds/DDS%20QOS.md) | 23 种 QoS 策略详解（可靠性、持久性、截止时间等） |
| [DDS Discovery](dds/DDS%20Discovery.md) | SPDP / SEDP 发现协议、动态发现机制 |
| [DDS RTPS](dds/DDS%20RTPS.md) | RTPS 协议规范、消息格式、可靠传输 |
| [DDS XTypes](dds/DDS%20XTypes.md) | 动态类型、可扩展类型系统 |
| [DDS XTypes IDL](dds/DDS%20XTypes%20IDL.md) | IDL 语法、类型注解、序列化 |
| [DDS Zero-Copy](dds/DDS%20Zero-Copy.md) | 零拷贝传输机制、共享内存优化 |
| [DDS Q&A](dds/DDS%20Q%26A.md) | 高频面试问题与参考答案 |

---

### 🤖 ROS / ROS2 [`ros/`](ros/)

ROS（Robot Operating System）是机器人领域事实标准框架，ROS2 在 ROS1 基础上重构，基于 DDS 提供生产级可靠性、实时性与跨平台能力。本节按 **ROS1 / ROS2** 拆分子目录：

#### ROS1 [`ros/ros1/`](ros/ros1/)

| 文件 | 内容简介 |
|------|----------|
| [ROS1 简介](ros/ros1/ROS1%20简介.md) | ROS1 顶层架构、Master、TCPROS、catkin 概览 |
| [ROS1 最佳实践](ros/ros1/ROS1%20最佳实践.md) | ⭐ 包结构 / Nodelet / launch / dynamic_reconfigure / 多机 / 迁移 ROS2 清单 |
| [ROS1 通信机制](ros/ros1/ROS1%20通信机制.md) | Topic / Service / Action / Parameter 详解、Nodelet |
| [ROS1 工具与构建](ros/ros1/ROS1%20工具与构建.md) | catkin_make/catkin build、roslaunch、rxx_* CLI、调试工具 |
| [ROS1 vs ROS2 对比](ros/ros1/ROS1%20vs%20ROS2%20对比.md) | 全维度对比、API 对照、ros1_bridge 迁移路径 |
| [ROS1 文件系统与消息族](ros/ros1/ROS1%20文件系统与消息族.md) | package.xml / CMakeLists、common_msgs、自定义 .msg/.srv/.action |
| [ROS1 TF与坐标变换](ros/ros1/ROS1%20TF与坐标变换.md) | tf vs tf2、TransformListener、static_transform_publisher |
| [ROS1 URDF与xacro](ros/ros1/ROS1%20URDF与xacro.md) | URDF 元素、xacro 宏、check_urdf、Gazebo 标签 |
| [ROS1 ros_control与Gazebo](ros/ros1/ROS1%20ros_control与Gazebo.md) | controller_manager、HardwareInterface、Gazebo 插件 |
| [ROS1 Navigation与MoveIt](ros/ros1/ROS1%20Navigation%E4%B8%8EMoveIt.md) | move_base、costmap、AMCL、MoveIt 1 框架 |
| [ROS1 插件与动态参数](ros/ros1/ROS1%20插件与动态参数.md) | pluginlib、nodelet、dynamic_reconfigure |
| [ROS1 多机部署与桥接](ros/ros1/ROS1%20多机部署与桥接.md) | ROS_MASTER_URI、multi-master、ros1_bridge、网络配置 |
| [ROS1 性能调优与排查](ros/ros1/ROS1%20性能调优与排查.md) | nodelet 零拷贝、TCP_NODELAY、rosbag、rqt_top、常见瓶颈 |

#### ROS2 [`ros/ros2/`](ros/ros2/)

**核心基础**：

| 文件 | 内容简介 |
|------|----------|
| [ROS2 入门教程](ros/ros2/ROS2%20入门教程.md) | 🌱 零基础起步：安装 → 第一个节点 → Topic/Service/Action → URDF+RViz |
| [ROS2 最佳实践](ros/ros2/ROS2%20最佳实践.md) | ⭐ 工程化清单：包结构 / QoS / Executor / Launch / 测试 / 部署 / Top 20 Checklist |
| [ROS2 简介](ros/ros2/ROS2%20简介.md) | 整体架构、版本演进、rcl/rmw 分层、Domain |
| [ROS2 环境搭建与Docker](ros/ros2/ROS2%20环境搭建与Docker.md) | 安装、版本选择、Docker / devcontainer / 多机 |
| [ROS2 节点与执行器](ros/ros2/ROS2%20节点与执行器.md) | Node、Executor 四种类型、CallbackGroup、WaitSet/GuardCondition、死锁陷阱 |
| [ROS2 话题、服务与Action](ros/ros2/ROS2%20话题、服务与Action.md) | Topic / Service / Action 三机制详解与选型 |
| [ROS2 常用消息族](ros/ros2/ROS2%20常用消息族.md) | std/geometry/sensor/nav/control_msgs 速查 |
| [ROS2 参数与Launch](ros/ros2/ROS2%20参数与Launch.md) | Parameter API、launch.py、组合启动、重映射 |
| [ROS2 参数与Launch高级](ros/ros2/ROS2%20参数与Launch高级.md) | ParameterEventHandler、OpaqueFunction、Lifecycle launch、launch_testing |
| [ROS2 生命周期与组件化](ros/ros2/ROS2%20生命周期与组件化.md) | Lifecycle 状态机、Composition、IPC 零拷贝、Loaned Messages |
| [ROS2 DDS与QoS](ros/ros2/ROS2%20DDS与QoS.md) | RMW 切换、QoS 兼容性、RTPS 子消息、Discovery Server、Domain 端口映射 |
| [ROS2 DDS厂商调优与跨域部署](ros/ros2/ROS2%20DDS厂商调优与跨域部署.md) | Fast/Cyclone/Connext/Zenoh 对比、XML profile、跨网段、iceoryx |
| [ROS2 TF2与时间](ros/ros2/ROS2%20TF2与时间.md) | TF Tree、`/tf` 与 `/tf_static`、`use_sim_time` |
| [ROS2 消息序列化与XTypes](ros/ros2/ROS2%20消息序列化与XTypes.md) | rosidl 生成链、CDR/XCDR2、XTypes 注解、ROS2↔DDS Topic 映射 |
| [ROS2 Action与pluginlib深入](ros/ros2/ROS2%20Action与pluginlib深入.md) | Action 状态机、pluginlib 5 步、Python entry_points |

**构建与生态**：

| 文件 | 内容简介 |
|------|----------|
| [ROS2 colcon与ament](ros/ros2/ROS2%20colcon与ament.md) | 构建系统、package.xml、ament_cmake / ament_python、rosidl |
| [ROS2 ament_cmake与colcon高级](ros/ros2/ROS2%20ament_cmake与colcon高级.md) | export 三件套、混合 C++/Python、CMake 钩子、industrial_ci |
| [ROS2 RViz2与可视化](ros/ros2/ROS2%20RViz2与可视化.md) | RViz2 插件、Foxglove、PlotJuggler、rqt 工具链 |
| [ROS2 调试诊断与bag](ros/ros2/ROS2%20调试诊断与bag.md) | 日志/diagnostic/tracing、rosbag2（MCAP）、performance_test、排错方法论 |
| [ROS2 测试_CI_CD](ros/ros2/ROS2%20测试_CI_CD.md) | gtest / pytest、launch_testing、ament_lint、industrial_ci、Docker buildx |
| [ROS2 rclpy异步与GIL](ros/ros2/ROS2%20rclpy异步与GIL.md) | Python Executor、asyncio 集成、GIL 影响、性能注意 |

**机器人栈**：

| 文件 | 内容简介 |
|------|----------|
| [ROS2 URDF_xacro与Gazebo](ros/ros2/ROS2%20URDF_xacro与Gazebo.md) | URDF/xacro、SDF、Gazebo Sim (gz)、ros_gz_bridge |
| [ROS2 ros2_control与Nav2生态](ros/ros2/ROS2%20ros2_control与Nav2生态.md) | HardwareInterface、控制器框架、Nav2 BT/Lifecycle/Costmap |
| [ROS2 ros2_control进阶](ros/ros2/ROS2%20ros2_control进阶.md) | 链式控制器、admittance、real-time 编程、PREEMPT_RT |
| [ROS2 Nav2深入与BT](ros/ros2/ROS2%20Nav2深入与BT.md) | planner/controller 选型、costmap layers、BT XML、collision_monitor |
| [ROS2 SLAM工具链](ros/ros2/ROS2%20SLAM工具链.md) | slam_toolbox / Cartographer / Fast-LIO / RTAB-Map、evo |
| [ROS2 MoveIt2](ros/ros2/ROS2%20MoveIt2.md) | 架构、Setup Assistant、planner、IK、MoveIt Servo |
| [ROS2 Autoware与自动驾驶集成](ros/ros2/ROS2%20Autoware与自动驾驶集成.md) | Autoware Universe、Lanelet2、AWSIM/CARLA、Apollo 对比 |

**实时 / 安全 / 嵌入式 / AI**：

| 文件 | 内容简介 |
|------|----------|
| [ROS2 实时性与性能优化](ros/ros2/ROS2%20实时性与性能优化.md) | PREEMPT_RT、Loaned Messages、SHM、典型延迟数据、OS 调优清单 |
| [ROS2 安全SROS2](ros/ros2/ROS2%20安全SROS2.md) | DDS-Security 五插件、keystore、enclave、governance/permissions |
| [ROS2 安全Security实操与PKI](ros/ros2/ROS2%20安全Security实操与PKI.md) | enclave 实操、PKI 集成、证书轮换、CRL/OCSP、性能开销 |
| [ROS2 micro-ROS与嵌入式](ros/ros2/ROS2%20micro-ROS与嵌入式.md) | rclc + Micro XRCE-DDS、FreeRTOS 部署、UART/UDP transport |
| [ROS2 嵌入式与micro-ROS进阶](ros/ros2/ROS2%20嵌入式与micro-ROS进阶.md) | Zephyr、自定义 transport、static memory、Yocto、QNX |
| [ROS2 ML集成与CUDA](ros/ros2/ROS2%20ML集成与CUDA.md) | ONNX/TensorRT/libtorch、Isaac NITROS、rosbag2 训练数据 |
| [ROS2 REP规范与故障注入](ros/ros2/ROS2%20REP规范与故障注入.md) | REP-103/105/2003/2004、tc/netem 注入、chaos 工程 |
| [ROS2 多机器人车队](ros/ros2/ROS2%20多机器人车队.md) | DOMAIN_ID/namespace/frame_id 三层隔离、Open-RMF、监控、OTA |

#### ROS 公共知识 [`ros/common/`](ros/common/)

ROS1 / ROS2 共享的数学、传感器、SLAM、规划、控制基础与端到端项目实战：

| 文件 | 内容简介 |
|------|----------|
| [数学与坐标变换基础](ros/common/数学与坐标变换基础.md) | 欧拉/四元数/旋转矩阵/SE(3)、TF 语义、REP-103 |
| [传感器接入实战](ros/common/传感器接入实战.md) | 相机 / LiDAR / IMU / GNSS / F-T 标定与同步、robot_localization |
| [建图与定位综述](ros/common/建图与定位综述.md) | 2D / 3D / 视觉 SLAM 对比、闭环、地图表示、evo 评估 |
| [运动规划综述](ros/common/运动规划综述.md) | 搜索 / 采样 / 优化、Frenet、局部 controller、机械臂、多机协同 |
| [控制综述](ros/common/控制综述.md) | PID / Pure Pursuit / Stanley / LQR / MPC / 力控柔顺 |
| [项目实战 差速底盘端到端](ros/common/项目实战-差速底盘端端到端.md) | URDF→ros2_control→SLAM→Nav2→bag→Docker 全流程 |
| [项目实战 机械臂 pick_place](ros/common/项目实战-机械臂pick_place.md) | URDF→MoveIt2→视觉抓取→状态机→力控装配 |
| [机器人工程 最佳实践](ros/common/机器人工程%20最佳实践.md) | ⭐ 坐标系 / 传感器 / SLAM / 控制 / 安全 / OTA / Top 20 Checklist |
| [SLAM 算法选型对比](ros/common/SLAM%20算法选型对比.md) | ORB-SLAM3 / VINS / FAST-LIO2 / Cartographer / RTAB-Map 横向对比与选型 |
| [状态估计 KF EKF UKF](ros/common/状态估计%20KF%20EKF%20UKF.md) | KF/EKF/ESKF/UKF/PF / 因子图 / GTSAM iSAM2 / VIO / LIO |
| [PID 控制与调参](ros/common/PID%20控制与调参.md) | 位置式 / 增量式 / 护饱和 / 串级 / 前馈 / Z-N 调参 |

---

### 🌐 网络 [`network/`](network/)

| 文件 | 内容简介 |
|------|----------|
| [网络 最佳实践](network/网络%20最佳实践.md) | ⭐ 客户端/服务端调优 / TLS / 心跳 / 服务发现 / 可观测 / Top 20 Checklist |
| [TCP UDP](network/TCP%20UDP.md) | TCP 三次握手/四次挥手、滑动窗口、UDP 特性对比 |
| [HTTP HTTPS](network/HTTP%20HTTPS.md) | HTTP/1.1 vs 2 vs 3、QUIC、TLS、状态码、缓存、CORS、REST |
| [IO 多路复用](network/IO%20多路复用.md) | select/poll/epoll/kqueue/IOCP/io_uring、Reactor/Proactor、C10K→C10M |
| [网络编程 Socket](network/网络编程%20Socket.md) | Berkeley socket、TCP/UDP 模板、关键 socket 选项、Unix Domain Socket |

---

### 🏗️ 架构设计 [`architecture/`](architecture/)

| 文件 | 内容简介 |
|------|----------|
| [架构 最佳实践](architecture/架构%20最佳实践.md) | ⭐ 12-Factor / C4 / ADR / 容量 / HA / 安全 / DORA / Top 20 Checklist |
| [SOA](architecture/SOA.md) | 面向服务架构 SOA 核心概念、优缺点、模式、技术栈与微服务对比 |
| [微服务架构](architecture/微服务架构.md) | 拆分原则、RPC/MQ、Saga/TCC/Outbox、服务网格、GitOps、金丝雀 |
| [设计模式](architecture/设计模式.md) | GoF 23 模式 + SOLID + 现代 C++/Python 实现要点 |
| [分布式系统](architecture/分布式系统.md) | CAP/BASE、一致性模型、Paxos/Raft、Quorum、时钟、幂等 |

---

### 🔧 工具 [`tools/`](tools/)

| 文件 | 内容简介 |
|------|----------|
| [工具链 最佳实践](tools/工具链%20最佳实践.md) | ⭐ Git/Repo/SQLite/Shell/Docker/密钥管理 / Top 20 Checklist |
| [Docker 与 Kubernetes 基础](tools/Docker%20与%20Kubernetes%20基础.md) | 容器原理 / Dockerfile / 多阶段构建 / Pod / Service / HPA / 调试排查 |
| [git](tools/git.md) | 常用 git 命令、分支管理、rebase vs merge、冲突解决 |
| [repo](tools/repo.md) | Android `repo` 工具使用、多仓库管理 |
| [SQLite3](tools/SQLite3.md) | SQLite3 C++ API、常用 SQL 速查 |

---

### 🖥️ 操作系统 [`os/`](os/)

| 文件 | 内容简介 |
|------|----------|
| [Linux 基础](os/Linux%20基础.md) | 进程线程 / 内存 / 文件 IO / 信号 / IPC / namespace + cgroup / systemd / 排查工具 |

---

### 🧩 算法与数据结构 [`dsa/`](dsa/)

| 文件 | 内容简介 |
|------|----------|
| [数据结构与算法](dsa/数据结构与算法.md) | 复杂度 / 线性结构 / 树与图 / 排序 / DP / 字符串 / 高频 Top 30 |

---

### 🗄️ 数据库 [`database/`](database/)

| 文件 | 内容简介 |
|------|----------|
| [数据库 基础](database/数据库%20基础.md) | SQL / 索引 / 事务与隔离 / MVCC / NoSQL / Redis / 分库分表 |

---

### 📨 消息队列 [`mq/`](mq/)

| 文件 | 内容简介 |
|------|----------|
| [消息队列 选型与实战](mq/消息队列%20选型与实战.md) | Kafka / RabbitMQ / RocketMQ / Pulsar 对比 / 不丢不重有序 / 死信 / Outbox |

---

### 📝 面试总结 [`summarize/`](summarize/)

按领域分类整理的面试准备材料，包含高质量问答示例和实战案例：

#### C++ 方向 [`summarize/cpp/`](summarize/cpp/)

| 文件 | 内容简介 |
|------|----------|
| [IPC与内存管理面试要点](summarize/cpp/IPC与内存管理面试要点.md) | 进程间通信、线程同步、智能指针循环引用、vtable 等高频题 |
| [多态与智能指针面试要点](summarize/cpp/多态与智能指针面试要点.md) | 虚函数原理、抽象类、`shared_ptr`/`unique_ptr`/`weak_ptr` 详解 |
| [系统问题排查](summarize/cpp/系统问题排查.md) | CPU/内存突增排查流程（`top`/`pmap`/`perf` 等工具链） |

#### DDS 方向 [`summarize/dds/`](summarize/dds/)

| 文件 | 内容简介 |
|------|----------|
| [DDS-自动驾驶应用](summarize/dds/DDS-自动驾驶应用.md) | DDS 在自动驾驶中的核心优势与典型应用场景 |
| [DDS-发现阶段网络风暴规避策略](summarize/dds/DDS-发现阶段网络风暴规避策略.md) | 大规模部署时 SPDP 广播风暴的规避方案 |
| [DDS-高频大数据场景优化](summarize/dds/DDS-高频大数据场景优化.md) | QoS 调优、零拷贝、异步发布在高频场景的实践 |
| [DDS-跨域通信大数据场景优化](summarize/dds/DDS-跨域通信大数据场景优化.md) | 跨 Domain 通信的流控与性能优化策略 |
| [RTI-DDS流量控制QoS策略](summarize/dds/RTI-DDS流量控制QoS策略.md) | RTI Connext DDS 流量控制相关 QoS 配置解析 |
| [SR卡顿排查案例](summarize/dds/SR卡顿排查案例.md) | 自动驾驶感知融合模块在复杂路口卡顿问题的完整排查过程 |
| [MQTT与DDS对比](summarize/dds/MQTT与DDS对比.md) | 架构、实时性、QoS、适用场景全面对比 |
| [协议栈对比(CAN-SOMEIP-DDS)](summarize/dds/协议栈对比\(CAN-SOMEIP-DDS\).md) | CAN 总线 / SOME-IP / DDS 三种协议横向对比 |

#### ROS 方向 [`summarize/ros/`](summarize/ros/)

| 文件 | 内容简介 |
|------|----------|
| [ROS1面试要点](summarize/ros/ROS1面试要点.md) | ROS1 架构、四种通信、catkin、Nodelet、高频问答 |
| [ROS2面试要点](summarize/ros/ROS2面试要点.md) | rcl/rmw/DDS、Executor、QoS、Lifecycle、Composition、零拷贝、高频问答 |

---

### 📖 参考资料 [`reference/`](reference/)

收录精选 PDF 书籍与学习笔记：

- **C++**：《Effective Modern C++》笔记、C++ 八股文速查、面经整理
- **DDS**：DDS 规范文档
- **Python**：Python 核心知识速查

---

## 🗂️ 目录结构

```
InterviewGuide/
├── cpp/                    # C++ 核心知识点（23 个专题 + Eigen 子目录）
│   └── eigen/              # Eigen 线性代数库（8 个专题）
├── python/                 # Python 核心知识点（13 个专题）
├── mpc/                    # 模型预测控制（11 个专题）
├── dds/                    # DDS 中间件（9 个专题）
├── ros/                    # ROS / ROS2（60 个专题）
│   ├── ros1/               # ROS1（13 个专题）
│   ├── ros2/               # ROS2（36 个专题）
│   └── common/             # ROS 公共（11 个专题：数学 / 传感器 / SLAM ×2 / 规划 / 控制 ×2 / 状态估计 / 实战×2 + 最佳实践）
├── architecture/           # 架构设计（5 个专题）
├── network/                # 网络协议（5 个专题）
├── tools/                  # 开发工具速查（5 个专题：Git / Repo / SQLite / Docker+K8s / 工具链最佳实践）
├── os/                     # 操作系统（1 个专题：Linux 基础）
├── dsa/                    # 算法与数据结构（1 个专题）
├── database/               # 数据库（1 个专题）
├── mq/                     # 消息队列（1 个专题）
├── summarize/              # 面试总结
│   ├── cpp/                # C++ 面试要点与系统排查
│   ├── dds/                # DDS 技术深度与实战案例
│   └── ros/                # ROS1 / ROS2 面试要点
└── reference/              # 参考资料（PDF + 笔记）
    ├── C++/
    ├── DDS/
    └── Python/
```

---

## 🚀 使用建议

1. **快速复习**：直接查阅 [`summarize/`](summarize/) 下的面试要点文件，包含高质量问答模板
2. **深入学习**：阅读对应领域目录（`cpp/` / `dds/`）下的详细专题文档
3. **项目经验准备**：参考 [SR卡顿排查案例](summarize/dds/SR卡顿排查案例.md) 学习如何结构化描述技术挑战
4. **协议对比题**：查阅 [协议栈对比](summarize/dds/协议栈对比\(CAN-SOMEIP-DDS\).md) 和 [MQTT与DDS对比](summarize/dds/MQTT与DDS对比.md)

---

## 📄 License

[Apache 2.0](LICENSE)