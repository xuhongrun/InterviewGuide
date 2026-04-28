# ROS1 最佳实践

> 面向仍在维护 ROS1（Noetic / Melodic）项目的工程师的工程化清单。覆盖包结构、通信、参数、launch、TF、构建、Nodelet、调试与迁移 ROS2 的注意事项。
>
> 配套：[ROS1 简介](ROS1%20简介.md) / [通信机制](ROS1%20通信机制.md) / [vs ROS2 对比](ROS1%20vs%20ROS2%20对比.md) / [性能调优与排查](ROS1%20性能调优与排查.md)

---

## 一、项目与包结构

### ✅ 推荐

```
my_robot/
├── my_robot                    # 元包 metapackage，仅依赖
├── my_robot_bringup            # launch + config 总入口
├── my_robot_description        # URDF / xacro / mesh
├── my_robot_msgs               # .msg / .srv / .action（独立！）
├── my_robot_drivers            # 硬件驱动 nodelet
├── my_robot_perception
├── my_robot_planning
├── my_robot_control
└── my_robot_gazebo             # 仿真 world + plugin
```

- 包名小写下划线；
- **消息独立成包**，避免业务包之间的循环依赖；
- launch / config / urdf 集中在 bringup，外部部署只看一处；
- 每个驱动包同时提供 **node + nodelet** 双入口。

---

## 二、构建（catkin）

| 实践 | 说明 |
|------|------|
| **`catkin build`（catkin_tools）** | 比 `catkin_make` 强，多包并行、隔离、彩色输出 |
| `catkin config --extend /opt/ros/noetic` | 显式声明 underlay |
| `catkin clean -y && catkin build` | 解决奇怪链接错误 |
| `package.xml` 用 **format 2/3** | 区分 build/exec/test 依赖 |
| `add_dependencies(${PROJECT_NAME} ${${PROJECT_NAME}_EXPORTED_TARGETS} ${catkin_EXPORTED_TARGETS})` | 自定义消息编译顺序，新手必踩坑 |
| `find_package(catkin REQUIRED COMPONENTS ...)` | 列出真实用到的包，不要超集 |
| 用 `rosdep install --from-paths src --ignore-src -y` | 拉系统依赖 |

CI：`industrial_ci`（同样适配 ROS1）。

---

## 三、节点与 Nodelet

### ✅ 推荐

- **大数据流（图像 / 点云 / 激光）必须用 Nodelet**：同一进程零拷贝（共享 boost::shared_ptr）；
- Nodelet manager 命名清晰：`/sensors_nodelet_manager`、`/perception_nodelet_manager`，按职能分组；
- `~num_worker_threads` 设为核数，避免回调饥饿；
- 普通节点使用 `ros::AsyncSpinner` 而非 `ros::spin()`，多回调并发处理；
- 一个节点做一件事；订阅队列长度合理（高频 1~10，状态 100）。

### Nodelet 模板

```cpp
class MyNodelet : public nodelet::Nodelet {
  void onInit() override {
    auto& nh   = getNodeHandle();
    auto& pnh  = getPrivateNodeHandle();
    pnh.param("rate", rate_, 50.0);
    sub_ = nh.subscribe("input", 10, &MyNodelet::cb, this);
    pub_ = nh.advertise<sensor_msgs::PointCloud2>("output", 10);
  }
  void cb(const sensor_msgs::PointCloud2ConstPtr& msg) { /* ... */ }
};
PLUGINLIB_EXPORT_CLASS(my_pkg::MyNodelet, nodelet::Nodelet)
```

---

## 四、命名与命名空间

| 资源 | 推荐 | 反例 |
|------|------|------|
| Topic | 分层 `/perception/lidar/points` | `/topic1` |
| 私有参数 | `~speed_limit`（节点私有空间） | 全局参数 |
| Frame | REP-103/105：`base_link` `odom` `map` | `frame_a` |
| Service | 动词+名词：`set_max_speed` | `srv1` |
| Param 命名空间 | 与 launch 文件 push 的 ns 对齐 | 散乱 |

`<group ns="vehicle1">` + remap 是多机部署时**必须**的，详见 [ROS1 多机部署与桥接](ROS1%20多机部署与桥接.md)。

---

## 五、Launch 文件（XML）

### ✅ 推荐

```xml
<launch>
  <arg name="use_sim" default="false"/>
  <arg name="namespace" default=""/>

  <group ns="$(arg namespace)">
    <param name="robot_description" command="$(find xacro)/xacro $(find my_desc)/urdf/robot.xacro"/>

    <!-- 启动 Nodelet manager + 一组 nodelet -->
    <node pkg="nodelet" type="nodelet" name="nm" args="manager" output="screen"/>
    <node pkg="nodelet" type="nodelet" name="lidar"
          args="load my_pkg/LidarNodelet nm"/>

    <!-- 包含子 launch -->
    <include file="$(find my_robot_bringup)/launch/sensors.launch">
      <arg name="use_sim" value="$(arg use_sim)"/>
    </include>

    <!-- YAML 加载参数 -->
    <rosparam command="load" file="$(find my_robot_bringup)/config/control.yaml"/>
  </group>
</launch>
```

要点：
- 顶层 launch **参数化**（sim/真机切换、namespace）；
- 多模块用 `<include>` 拆分，避免单文件超长；
- 用 `<arg>` 不用 env；
- `respawn="true"` + `respawn_delay="2"` 关键节点自动重启；
- `required="true"` 标记主节点退出整体 shutdown。

---

## 六、参数（dynamic_reconfigure）

| 实践 | 说明 |
|------|------|
| 静态参数：`<rosparam>` + 节点 `param<T>("name", default)` | 启动注入 |
| **可调参数：dynamic_reconfigure** | 调试体验比 ROS2 参数好 |
| `cfg/My.cfg` 写枚举 / 范围 / 描述 | rqt_reconfigure 自动生成 GUI |
| 参数 callback 只更新成员变量，不重建对象 | 避免运行时大开销 |
| `~private_param` vs `/global_param` 必须区分 | 多机部署时全局参数易冲突 |

**dynamic_reconfigure 在 ROS2 没有等价品**（ROS2 参数原生支持事件），迁移时记得把这部分代码改造。

---

## 七、TF / 时间

| 实践 | 说明 |
|------|------|
| 用 **`tf2`** 系列接口（`tf2_ros::Buffer/Listener`），别用旧 `tf` API | 旧 API 已弃用 |
| 静态 TF 用 `static_transform_publisher` 或 `tf2_ros::StaticTransformBroadcaster` | 不要周期发 static |
| TF tree 唯一性（一个 frame 只有一个父） | 多链路是常见 bug |
| `lookupTransform` 永远 try-catch | 启动初期 / 时序错乱 |
| `use_sim_time:=true` 时所有节点同步设置 | 不一致会导致 TF extrapolation |
| 多机时间用 chrony / PTP | 漂移会让 TF 错位 |

详见 [ROS1 TF与坐标变换](ROS1%20TF与坐标变换.md)。

---

## 八、消息设计

- **必带 `Header`**：`frame_id` + `stamp`；
- 单位放注释（`# m/s`）；
- 大数据流（图像/点云）独立 topic；
- 用枚举常量代替魔数；
- Topic 列表写在 README，包含 名 / 类型 / QoS（队列长） / 频率 / 含义。

---

## 九、Service vs Action

- 短查询、可立即返回 → **Service**（同步阻塞调用方）；
- 长任务 + 进度反馈 + 可取消 → **Action**（actionlib）；
- 永远不要在 Service 回调里 `sleep` 或调用其他 Service（容易死锁，特别是单线程 spinner）。

模板：
```cpp
ros::AsyncSpinner spinner(4);
spinner.start();
// service / action 都能并发处理
ros::waitForShutdown();
```

---

## 十、性能与零拷贝

ROS1 同进程零拷贝条件：
1. 使用 **Nodelet**，发布订阅都在同一 manager；
2. 发布时用 `boost::shared_ptr<Msg const>`：
   ```cpp
   auto msg = boost::make_shared<sensor_msgs::PointCloud2>();
   pub_.publish(msg);  // ConstPtr 订阅端零拷贝接收
   ```
3. 订阅签名：`void cb(const sensor_msgs::PointCloud2ConstPtr& msg)`。

注意：跨进程仍走 TCPROS / UDPROS，无零拷贝。

其它：
- `tcp_nodelay := true` 高频小消息减少 Nagle 延迟；
- `UDPROS` 用于丢包可容忍的传感器；
- `ros::TransportHints().tcpNoDelay()` 订阅端启用；
- 大消息考虑 **ros_comm_image_transport / point_cloud_transport** 压缩传输；
- 关闭不必要 logging：`/rosout` 大量 INFO 会卡爆 master。

详见 [ROS1 性能调优与排查](ROS1%20性能调优与排查.md)。

---

## 十一、错误处理与日志

- 用 ROS 宏：`ROS_INFO/WARN/ERROR/DEBUG`；
- 限频：`ROS_WARN_THROTTLE(1.0, ...)`；
- DEBUG 用 `<env name="ROSCONSOLE_FORMAT" value="..."/>` 自定义；
- Callback 内**异常不外抛**，包好 try-catch；
- `diagnostic_updater` 暴露关键状态到 `/diagnostics`（rqt_runtime_monitor 实时查看）；
- `rosout` 中心化收集 + 本地 `~/.ros/log/` 保留 N 天。

---

## 十二、调试 / 录制

| 工具 | 用途 |
|------|------|
| `rqt_graph` | 节点-话题拓扑 |
| `rqt_console` | 集中查看 ROS log |
| `rqt_plot` / PlotJuggler | 数据时序曲线 |
| `rqt_reconfigure` | 动态调参 |
| `rqt_tf_tree` | TF 树可视化 |
| `rosbag record -a -O run.bag` | 录制（注意磁盘 IO） |
| `rosbag play --clock --rate 0.5` | 回放 + sim_time |
| `rosbag info / filter` | 查看 / 切片 |
| `rosrun rqt_top rqt_top` | 节点资源占用 |

调试三板斧：拓扑（rqt_graph）+ 时间（rosbag/PlotJuggler）+ 现场（rqt_console + diagnostic）。

---

## 十三、多机部署

```bash
# Master 机器
export ROS_MASTER_URI=http://master_ip:11311
export ROS_IP=master_ip
roscore

# Slave 机器
export ROS_MASTER_URI=http://master_ip:11311
export ROS_IP=slave_ip
rosrun ...
```

要点：
- 必须**双向**可解析对方主机名（或全部用 IP）；
- 防火墙放行 11311 + 节点动态端口；
- 时间用 chrony 同步；
- 用 `multimaster_fkie` 做多 master 鲁棒方案；
- 跨网段一律 VPN（WireGuard）。

详见 [ROS1 多机部署与桥接](ROS1%20多机部署与桥接.md)。

---

## 十四、测试

- **单元测试**：`gtest`（`catkin_add_gtest`）/ `pytest`；
- **节点级**：`rostest` + 启动节点 + 模拟 publisher + 断言；
- **rosbag 回归**：录回放 + 关键 topic 频率 / 内容断言；
- 静态检查：`roslint`、`clang-format`、`flake8`；
- CI 用 `industrial_ci` GitHub Actions。

---

## 十五、部署与运维

| 维度 | 推荐 |
|------|------|
| 启动 | systemd unit + `Restart=on-failure` |
| 配置外置 | `/etc/my_robot/*.yaml` 不打死镜像 |
| 日志 | rosout → 本地轮转 → 集中（fluent-bit） |
| 监控 | rosgraph_msgs/diagnostic → Prometheus exporter |
| 紧急遥停 | 独立通道（4G UDP），不依赖 ROS graph |
| OTA | apt 包 / mender / 自研增量 |
| Docker | `--network host` + `ROS_HOSTNAME` |

---

## 十六、迁移 ROS2 的预备工作

提前在 ROS1 阶段就做好的事，能让迁移代价大幅降低：

- ✅ 业务逻辑与 ROS API **解耦**：核心算法用 pimpl / 接口隔离；
- ✅ 消息只用 **common_msgs** 标准消息或自家 `*_msgs` 包，少用 ROS1-only 类型；
- ✅ Nodelet 习惯**等价于 ROS2 Composition**，写法迁移直观；
- ✅ launch 用 args + include 解耦，迁移时改写 Python launch 时容易；
- ✅ 用 tf2（不要 tf1）；
- ✅ 测试覆盖率 ≥ 60%，迁移后跑通即基本稳定；
- ✅ dynamic_reconfigure 替换为 ROS2 ParameterEventHandler；
- ✅ actionlib → rclcpp_action（接口几乎一致）；
- ✅ 桥接阶段：`ros1_bridge` 双向桥接关键 topic，逐个节点替换。

详见 [ROS1 vs ROS2 对比](ROS1%20vs%20ROS2%20对比.md)。

---

## 十七、Top 15 速记 Checklist

- [ ] 包结构按职能拆 + msgs 独立
- [ ] 大数据用 Nodelet 零拷贝
- [ ] AsyncSpinner 替代 spin()
- [ ] tf2 不用 tf1
- [ ] 静态 TF 用 StaticTransformBroadcaster
- [ ] 自定义消息加 EXPORTED_TARGETS 依赖
- [ ] launch 参数化 + include 拆分
- [ ] 关键节点 respawn / required
- [ ] dynamic_reconfigure 调参
- [ ] 日志限频 + diagnostic
- [ ] tcp_nodelay 高频流
- [ ] rosbag 回归测试
- [ ] 多机部署 ROS_MASTER_URI/ROS_IP/时钟同步
- [ ] CI: industrial_ci
- [ ] 解耦业务逻辑，为 ROS2 迁移做准备

---

## 十八、面试速记

1. **零拷贝**：Nodelet + ConstPtr + 同 manager；
2. **AsyncSpinner**：避免单线程 spin 阻塞；
3. **tf2** 替代 tf1；静态 TF 不周期发；
4. **dynamic_reconfigure**：rqt_reconfigure 实时调；
5. **rosbag** 回归 + PlotJuggler 时序分析；
6. **多机**：MASTER_URI/IP + 时钟同步 + 网络可达；
7. **respawn**/required 守护关键节点；
8. **业务解耦** + tf2 + actionlib 是平滑迁移 ROS2 的三板斧。
