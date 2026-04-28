# ROS1 性能调优与排查案例

> ROS1 节点的常见性能陷阱与诊断套路；附 5 个高频排查案例。

---

## 一、消息流性能要点

### 1.1 队列与丢包

```cpp
ros::Publisher  pub = nh.advertise<T>("topic", queue_size);
ros::Subscriber sub = nh.subscribe("topic", queue_size, cb);
```

- **Publisher 队列满**：丢最旧待发；
- **Subscriber 队列满**：丢最旧待处理；
- 大消息 + 慢订阅 + 大队列 → **内存暴涨**；
- 队列长度建议：状态 1，传感器 5–10，事件 50+。

### 1.2 TCP_NODELAY

默认 TCPROS 启用 Nagle，会合并小包带来 **40ms 延迟**。延迟敏感话题：

```cpp
ros::TransportHints hints;
hints.tcpNoDelay(true);
sub = nh.subscribe("topic", 10, cb, hints);
```

### 1.3 UDPROS

```cpp
sub = nh.subscribe("topic", 10, cb,
        ros::TransportHints().udp().reliable(false));
```

- 大消息（>1500B）UDPROS 会拆包，可靠性弱于 TCP；
- 适用：高频小消息、可丢；
- 局域网 / 视距通信优先 UDP。

### 1.4 Nodelet 共享内存

同一进程多个 Nodelet 共享 `boost::shared_ptr<Msg const>`：

```cpp
void cb(const sensor_msgs::PointCloud2::ConstPtr& msg) { ... }
// 同进程订阅者直接拿到指针，不拷贝
```

> 跨进程仍要序列化拷贝。

---

## 二、定位 & 测量工具

```bash
rostopic hz /scan                    # 频率
rostopic bw /scan                    # 带宽
rostopic delay /scan                 # 端到端延迟（要求带 header.stamp）

rosnode info /node                   # 看 Pub/Sub 列表
rosnode ping /node                   # XMLRPC 往返

# CPU / 内存
top -p $(pgrep -f my_node)
pidstat -ut -p $(pgrep my_node) 1
htop / nethogs / iftop

# 调试器
gdb --args $(rospack find my_pkg)/devel/lib/my_pkg/my_node
valgrind --tool=callgrind ./my_node
perf record -p $(pgrep my_node) -g -- sleep 30
perf report
```

---

## 三、案例 1：订阅者收不到消息

**现象**：A 节点 `rostopic echo` 能看到，B 节点订阅同名 topic 无回调。

**排查**：

1. `rosnode info /B` 看是否真的订阅了；
2. `rostopic info /chatter` 看 publisher 列表里是否有 A、subscriber 列表里是否有 B；
3. 多机：
   - `ROS_HOSTNAME` 是否设置正确？
   - `/etc/hosts` 是否能解析？
   - `telnet A 11311` 通否？
4. 类型 / MD5 不匹配（看 publisher 报错）；
5. `tcpdump -i any port 11311` 看 XMLRPC 注册。

**常见根因**：`ROS_HOSTNAME` 没设导致节点把 `localhost:port` 注册给 Master，跨机连不上。

---

## 四、案例 2：消息延迟阶梯式增长

**现象**：刚启动延迟 5ms，运行 10 分钟变 200ms。

**排查**：
- `rostopic hz` 实际频率小于发布频率 → 消息堆积；
- subscriber 队列满 + 回调慢；
- 可能 publisher RELIABLE 等待 ACK 阻塞。

**修复**：
1. 增大 subscriber 队列 / 减小 publisher 队列；
2. 优化回调（脱离 spin 主线程，用 AsyncSpinner 或工作线程）；
3. 切 UDPROS（容忍丢包）；
4. 启用 `tcpNoDelay`；
5. CPU 不够 → 节点拆分到多机。

```cpp
ros::AsyncSpinner spinner(4);    // 4 线程并发
spinner.start();
ros::waitForShutdown();
```

---

## 五、案例 3：TF extrapolation 报错

**现象**：`Lookup would require extrapolation 0.5s into the past`。

**排查**：
1. `rostopic hz /tf` 频率是否足够（建议 ≥ 30Hz）；
2. `tf_monitor` 看 broadcaster 名单与延迟；
3. **时钟不同步**（多机或 sim_time 没设）；
4. buffer 默认只缓存 10s，查询时间太老。

**修复**：
- 同步时钟（chrony）；
- `Buffer(ros::Duration(30))` 增大缓存；
- 查询用 `ros::Time(0)` 取最新；
- 检查 publisher stamp 不要超前/滞后。

---

## 六、案例 4：高 CPU 但吞吐不高

**现象**：节点 CPU 100%+，rostopic hz 数据率却不高。

**排查**：
- `perf top -p PID` 看热点函数；
- 通常是：
  - **频繁序列化大消息**（点云 / 图像）；
  - JSON 解析、日志频繁；
  - `boost::shared_ptr` 拷贝（应用引用）；
  - cv::Mat clone 不必要。

**修复**：
- Nodelet 化共享指针；
- `image_transport` 压缩；
- `RCUTILS_LOGGING_BUFFERED_STREAM=1`；
- 把发布频率适当降到业务实际需要。

---

## 七、案例 5：bag 重放时间戳错乱

**现象**：bag 回放时下游算法时间戳跳跃 / TF 报错。

**排查**：

1. `rosbag info my.bag` 看 start/end 时间；
2. 重放是否带 `--clock`，节点是否设 `use_sim_time:=true`；
3. 业务节点是否被回放后启动（启动时机错过早期消息）。

**修复**：
```bash
roscore
rosparam set use_sim_time true
rosbag play --clock my.bag

# 节点启动后必须设置 use_sim_time
```

或：录制时确保所有传感器消息 `header.stamp` 用 ROS time（不是壁钟）。

---

## 八、性能调优 cookbook

| 场景 | 措施 |
|------|------|
| 高频小消息延迟 | `tcpNoDelay` + `AsyncSpinner` |
| 大消息（图像/点云） | Nodelet + image_transport / point_cloud_transport |
| CPU 占用高 | perf 找热点；移到 Nodelet；降频；多线程 spinner |
| 内存暴涨 | 队列减小 + 慢订阅排查 + valgrind |
| 多机带宽紧 | 压缩 / 抽稀 / 私有网段 |
| 实时性 | 切 ROS2（ROS1 无 RT 路线） |
| 多机不通 | hosts + ROS_HOSTNAME + 时钟同步 |

---

## 九、面试速记

- 默认 TCPROS 开启 Nagle，**延迟敏感必开 `tcpNoDelay`**
- 大消息同进程用 **Nodelet** 共享指针
- `AsyncSpinner` 多线程 spin 避免长回调阻塞
- 多机三件套：`hosts + ROS_HOSTNAME + chrony`
- TF 报错通常是**时钟不同步 / sim_time 没设 / buffer 太小**
- `bag play --clock` + `use_sim_time=true` 是仿真/回放铁律
- ROS1 没有原生实时路线，硬实时要切 ROS2
