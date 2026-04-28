# ROS2 调试、诊断与 rosbag2

> 生产级 ROS2 系统的可观测性：日志、诊断、tracing、bag 录制回放，以及常见问题排查方法论。

---

## 一、日志系统

### 1.1 日志级别

| 级别 | 宏（C++） | rclpy | 默认开启 |
|------|-----------|-------|----------|
| DEBUG | `RCLCPP_DEBUG` | `get_logger().debug` | ❌ |
| INFO | `RCLCPP_INFO` | `info` | ✅ |
| WARN | `RCLCPP_WARN` | `warn` | ✅ |
| ERROR | `RCLCPP_ERROR` | `error` | ✅ |
| FATAL | `RCLCPP_FATAL` | `fatal` | ✅ |

辅助宏：
```cpp
RCLCPP_INFO(get_logger(), "x=%d", x);
RCLCPP_INFO_STREAM(get_logger(), "x=" << x);
RCLCPP_INFO_THROTTLE(get_logger(), *get_clock(), 2000, "every 2s");
RCLCPP_INFO_ONCE(get_logger(), "first time only");
RCLCPP_INFO_FIRST_N(get_logger(), 3, "first 3 times");
```

### 1.2 运行时调整

```bash
# 启动时
ros2 run my_pkg my_node --ros-args --log-level DEBUG
ros2 run my_pkg my_node --ros-args --log-level my_node:=DEBUG
ros2 run my_pkg my_node --ros-args --log-level rclcpp:=WARN

# 运行时（通过 service）
ros2 service call /my_node/set_logger_levels rcl_interfaces/srv/SetLoggerLevels \
    "{levels: [{name: 'my_node', level: 10}]}"      # 10=DEBUG, 20=INFO, ...
```

### 1.3 日志位置

```bash
ROS_LOG_DIR=/tmp/ros_logs    # 默认 ~/.ros/log/<run>/
RCUTILS_COLORIZED_OUTPUT=1
RCUTILS_CONSOLE_OUTPUT_FORMAT="[{severity}] [{time}] [{name}]: {message}"
```

---

## 二、诊断（diagnostics）

### 2.1 核心包

- `diagnostic_msgs/DiagnosticArray`：标准诊断消息；
- `diagnostic_updater`：在节点中发布单点诊断；
- `diagnostic_aggregator`：聚合多源诊断成树（`rqt_robot_monitor` 显示）。

### 2.2 节点侧（C++）

```cpp
#include <diagnostic_updater/diagnostic_updater.hpp>

diagnostic_updater::Updater updater(this);
updater.setHardwareID("imu_serial_001");

updater.add("IMU Status", [this](diagnostic_updater::DiagnosticStatusWrapper& s){
    if (last_data_age_ > 0.1) {
        s.summary(diagnostic_msgs::msg::DiagnosticStatus::WARN, "stale data");
    } else {
        s.summary(diagnostic_msgs::msg::DiagnosticStatus::OK, "alive");
    }
    s.add("rate_hz", actual_rate_);
    s.add("temperature", temperature_);
});

// 频率检查辅助类
diagnostic_updater::HeaderlessTopicDiagnostic freq_diag(
    "imu_topic", updater,
    diagnostic_updater::FrequencyStatusParam(&min_freq_, &max_freq_, 0.1, 10));
// 在每次接收回调里调用 freq_diag.tick();
```

`Updater` 默认 1Hz 发布到 `/diagnostics`。

### 2.3 聚合

```yaml
# diagnostic_aggregator yaml
analyzers:
  sensors:
    type: diagnostic_aggregator/AnalyzerGroup
    path: Sensors
    analyzers:
      imu:
        type: diagnostic_aggregator/GenericAnalyzer
        path: IMU
        startswith: ['IMU']
```

可视化：
```bash
ros2 run rqt_robot_monitor rqt_robot_monitor
ros2 topic echo /diagnostics_agg
```

---

## 三、命令行内省工具

### 3.1 总览

```bash
ros2 doctor                          # 整体健康检查
ros2 doctor --report                 # 详细环境
ros2 wtf                             # 同上别名

ros2 node list / info /talker
ros2 topic list / info / echo / hz / bw / delay / find / pub
ros2 service list / call / type
ros2 action list / send_goal / info
ros2 param list / get / set / dump / load / describe
ros2 lifecycle nodes / list / get / set
ros2 component list / load / unload / standalone
ros2 interface list / show / proto / package / packages
ros2 pkg list / executables / prefix / xml
ros2 daemon start / stop / status
```

### 3.2 常用排查命令

```bash
# QoS 检查（Pub/Sub 不通时第一时间用）
ros2 topic info /chatter --verbose

# 跨节点延迟（需消息带 header.stamp）
ros2 topic delay /chatter

# 发现是否成功
ros2 topic list -t                    # 含类型
ros2 node info /talker                # 看 Pub/Sub/Service 端点

# 看实时 CPU/内存（按节点）
top -p $(pgrep -d, -f my_node)
pidstat -ut -p $(pgrep talker) 1
```

### 3.3 ros2 daemon

ROS2 工具命令默认走 **本地后台 daemon** 缓存发现结果。如果 `ros2 topic list` 卡顿或漏 topic，重启 daemon：

```bash
ros2 daemon stop
ros2 daemon start
```

---

## 四、tracing：ros2_tracing + LTTng

### 4.1 安装

```bash
sudo apt install ros-humble-tracetools-launch ros-humble-ros2trace lttng-tools liblttng-ust-dev
```

构建时启用：
```bash
colcon build --cmake-args -DTRACETOOLS_DISABLED=OFF
```

### 4.2 启动 tracing

```bash
ros2 trace -s my_session                        # 启动会话
ros2 launch my_pkg bringup.launch.py            # 跑业务
ros2 trace stop                                  # 停止
# trace 数据在 ~/.ros/tracing/my_session/
```

### 4.3 分析

```bash
pip install tracetools_analysis bokeh
ros2 run tracetools_analysis process ~/.ros/tracing/my_session
# 或直接打开 jupyter 用现成 notebook 分析
```

可获得：
- 回调延迟（schedule → start → end）；
- Pub→Sub 端到端时延；
- Executor 队列长度；
- 每回调 CPU 占比。

> 实时性能调优必备工具。

---

## 五、rosbag2

### 5.1 录制

```bash
ros2 bag record -a                     # 录全部
ros2 bag record /scan /odom -o run     # 指定话题
ros2 bag record -e "/sensor/.*" /tf    # 正则
ros2 bag record --storage mcap /scan   # MCAP 格式（推荐）
ros2 bag record --max-bag-size 1073741824 -a    # 1GB 切分
ros2 bag record --compression-mode file --compression-format zstd /scan
```

存储格式：
| 后端 | 默认 | 特点 |
|------|------|------|
| `sqlite3` (`.db3`) | Foxy–Iron 默认 | 单文件 SQLite，可 SQL 查询 |
| `mcap` | **Jazzy 默认** | Foxglove 标准，可流式追加，跨工具广 |

### 5.2 回放

```bash
ros2 bag info run                      # 查看时长/话题
ros2 bag play run                      # 回放
ros2 bag play run --rate 2.0           # 倍速
ros2 bag play run --loop
ros2 bag play run --start-offset 30    # 跳过前 30s
ros2 bag play run --topics /scan       # 仅回放指定 topic
ros2 bag play run --clock 100          # 同时发 /clock
ros2 bag play run --remap /scan:=/scan_replay
ros2 bag play run --qos-profile-overrides-path qos.yaml
```

> 回放时**业务节点必须 `use_sim_time:=true`** 才能用 bag 时间戳。

### 5.3 转换 / 重写

```bash
ros2 bag convert -i run.db3 -o output.yaml          # db3 → mcap
# output.yaml 描述输出参数
ros2 bag reindex broken_bag                          # 重建索引
ros2 bag burst run --topics /scan                    # 单步触发
```

### 5.4 ROS1 ↔ ROS2 bag 转换

```bash
pip install rosbags
rosbags-convert old.bag --dst new      # ROS1 → ROS2 (mcap/db3)
rosbags-convert new.mcap --dst old.bag # ROS2 → ROS1
```

### 5.5 Foxglove Studio 集成

`.mcap` 文件可直接拖入 Foxglove Studio 进行多面板可视化（图、3D、TF、表格、地图）；也可实时连接 `foxglove_bridge` WebSocket。

---

## 六、性能基准：performance_test

apex.ai 维护的 ROS2 标准 benchmark：

```bash
sudo apt install ros-humble-performance-test
ros2 run performance_test perf_test \
    -c rclcpp-single-threaded-executor \
    -t Array1k -p 1 -s 1 --rate 100 -m 1m
```

参数：
- `-c`：通信中间件（rclcpp/rmw/iceoryx/...）；
- `-t`：消息类型（Array1k / PointCloud4m / ...）；
- `--rate`：发布频率；
- `-m`：测试时长。

输出端到端延迟、CPU、丢失率，便于不同 RMW/QoS 对比。

---

## 七、故障排查方法论

### 7.1 通信不通

1. `ros2 doctor`：环境检查（RMW、Domain ID 一致？）；
2. `ros2 topic list -t`：双方确实看到话题？
3. `ros2 topic info <t> -v`：QoS **兼容**？
4. `ros2 node info`：端点是否注册？
5. 防火墙 / 多播：`ros2 multicast send|receive` 测试；
6. 同 RMW？跨 RMW 默认互通失败。

### 7.2 高延迟 / jitter

1. `ros2 topic delay`、`tracing`；
2. 检查 Executor：是否单线程被长回调阻塞？
3. CallbackGroup 死锁？
4. 序列化大小、QoS 历史深度过大；
5. 网络丢包（`netstat -su`、`ss -i`）；
6. 实时性：是否 PREEMPT_RT、SCHED_FIFO？

### 7.3 内存持续增长

1. 是否未 `take()`？检查订阅队列堆积；
2. `RELIABLE` + `KEEP_ALL` + 慢订阅 → 历史无限累积；
3. `valgrind --tool=massif` / `heaptrack`；
4. 自定义消息含变长数组未 reserve？

### 7.4 节点崩溃 / 卡死

1. `~/.ros/log/<run>/` 看 stderr；
2. `gdb` 附加：`gdb -p $(pgrep talker)`；
3. launch 加 `prefix='gdb -ex run --args'`；
4. coredump：`ulimit -c unlimited` + `/proc/sys/kernel/core_pattern`。

---

## 八、面试速记

- 日志：`RCLCPP_*` + `--log-level` + `set_logger_levels` 服务
- 诊断：`diagnostic_updater` + `/diagnostics` + `rqt_robot_monitor`
- 性能追踪：**`ros2_tracing` + LTTng**（端到端时延）
- bag 默认（Jazzy 起）= **MCAP**，`ros2 bag record/play/info/convert`
- daemon 异常 → `ros2 daemon stop && start`
- 通信不通五步：domain → topic list → QoS → 防火墙/multicast → RMW 一致
