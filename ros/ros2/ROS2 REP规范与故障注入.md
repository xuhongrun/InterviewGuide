# ROS2 REP 规范与故障注入

> ROS 标准化提案（**REP**, ROS Enhancement Proposal）规定了坐标系、单位、消息接口约定。工程上遵守 REP 才能保证生态互通；故障注入用于验证系统在网络/传感器异常下的健壮性。

---

## 一、关键 REP 列表

| REP | 主题 |
|-----|------|
| **REP-103** | 坐标系约定与单位（**右手系，X 前 Y 左 Z 上**；m / m·s⁻¹ / rad / s） |
| **REP-105** | 移动机器人坐标系：`earth → map → odom → base_link` 链 |
| **REP-117** | sensor_msgs/JointState 标准 |
| **REP-118** | sensor_msgs/Range 锥体定义 |
| **REP-141** | 命名空间与节点名规则 |
| **REP-145** | conventions for compute_path |
| **REP-147** | UAV/无人机坐标系 |
| **REP-2003** | ROS2 QoS 策略约定 |
| **REP-2004** | ROS2 包质量分级（Quality Level 1~5） |
| **REP-2007** | DDS Discovery server |
| **REP-2009** | ROS2 中间件 RMW 通用接口 |

---

## 二、REP-105 详解

```
earth (ECEF/UTM) ── map (世界，固定) ── odom (连续，可漂) ── base_link (车体)
                                              │
                                              ├── base_footprint (投影到地面，去除 z)
                                              ├── laser_link
                                              ├── imu_link
                                              └── camera_link
```

要点：
- `map → odom` 由定位/SLAM 发布，有跳变；
- `odom → base_link` 由里程计发布，**连续**；
- 控制器订阅 `odom` 系（不跳变）；
- 长程导航用 `map` 系；
- TF 不要让两个节点同时发同一对父子；
- `base_footprint` 是地面投影，平面规划用。

---

## 三、REP-103 单位与轴

| 量 | 单位 |
|----|------|
| 长度 | m |
| 角度 | rad |
| 时间 | s |
| 频率 | Hz |
| 力 | N |
| 力矩 | N·m |
| 质量 | kg |

车辆系：X 前 / Y 左 / Z 上；图像系：X 右 / Y 下 / Z 前；NED（航空）需特殊处理。

---

## 四、REP-2003 QoS 推荐

| 数据类型 | QoS Profile |
|----------|-------------|
| 命令 / 控制 | RELIABLE + KEEP_LAST(1) + VOLATILE |
| 服务调用 | service 默认 RELIABLE |
| 传感器流（image/scan/imu） | **SensorDataQoS**（BEST_EFFORT + KEEP_LAST(5)） |
| 长效状态（map/static_tf） | RELIABLE + **TRANSIENT_LOCAL** + KEEP_LAST(1) |
| 默认参数事件 | RELIABLE + KEEP_LAST(1000) + VOLATILE |

---

## 五、REP-2004 包质量等级

| Level | 描述 |
|-------|------|
| 5 | 演示级 |
| 4 | 一般使用 |
| 3 | 已测试 |
| 2 | 生产可用（CI、文档、稳定 API） |
| 1 | 工业关键（额外安全分析、覆盖率、长期支持） |

`package.xml`：
```xml
<export>
  <ros2_quality_declaration>
    <quality_level>3</quality_level>
  </ros2_quality_declaration>
</export>
```

升级 Level 需补：unit/integration test 覆盖率、API 稳定性、文档、安全审计等。

---

## 六、故障注入：网络层（tc / netem）

模拟丢包：
```bash
sudo tc qdisc add dev eth0 root netem loss 5%
```

延迟与抖动：
```bash
sudo tc qdisc add dev eth0 root netem delay 100ms 20ms distribution normal
```

带宽限制：
```bash
sudo tc qdisc add dev eth0 root tbf rate 1mbit burst 32kbit latency 400ms
```

复合：
```bash
sudo tc qdisc add dev eth0 root netem loss 2% delay 50ms 10ms reorder 25% 50%
```

清除：
```bash
sudo tc qdisc del dev eth0 root
```

观察影响：
- BEST_EFFORT 流（`/scan`）丢包直接掉，但不会卡 publisher；
- RELIABLE 流（`/cmd_vel`）丢包重传，KEEP_LAST(1) 时新数据顶旧；
- TRANSIENT_LOCAL 在重连/晚到时仍能补发最后一份；
- Discovery 包（multicast SPDP）丢失会让对端短期看不到。

---

## 七、传感器异常注入

| 异常 | 模拟方式 |
|------|----------|
| 时延 | 在 driver 节点订阅后 sleep 再 republish |
| 频率掉 | timer 跳采样 |
| 数据漂移 | 加随机偏置 / 高斯噪声 |
| 坏值 (NaN/inf) | 替换若干字段 |
| 完全静默 | kill driver 节点 |
| 时间戳异常 | header.stamp 故意倒序 / 跳跃 |

实现工具：`/scan_intercept` 节点订阅原始话题、注入扰动、再发布到 `/scan`，AMCL/Nav2 切换订阅源即可。

---

## 八、Chaos 工程实践

```
       ┌─ chaos controller ─┐
       │  (k8s / 脚本)       │
       └──────┬─────────────┘
              │ 触发
              ▼
   ┌──────────────────────┐
   │ 注入器：tc / 杀进程   │
   │ rosbag 篡改 / fault   │
   │ injection node        │
   └──────────┬───────────┘
              ▼
       目标 ROS2 节点
              │
              ▼
        监控告警 / 日志
```

工具：
- `pumba` — Docker 容器层网络 chaos；
- `chaos-mesh` — k8s chaos；
- ROS2 自定义 fault injector node。

CI 中跑：launch_test 启动节点 + 注入器 + 真值采集；断言安全性指标（最大延迟、是否触发紧急停车、定位漂移上限）。

---

## 九、安全行为约定

故障下应触发的最小风险机动（MRM）：
- 控制断流 > N ms：vehicle_cmd_gate 停止；
- 传感器丢失：lifecycle 切到 `safe` 模式；
- 定位失效：减速 + 报警；
- 计算节点崩：`emergency_handler` 接管。

监控指标：
- ROS2 话题 latency / drop count；
- TF 延迟（`tf_monitor`）；
- 控制循环 jitter；
- DDS 重传统计（厂商 statistics topic）。

---

## 十、面试速记

- 必读三个 REP：**103（坐标/单位）/ 105（TF 链）/ 2003（QoS）**
- TF 链 `earth → map → odom → base_link`，**odom 必须连续**
- `/map`、`/tf_static` 必须 **TRANSIENT_LOCAL**
- 网络故障注入用 **tc netem**（loss/delay/reorder/bandwidth）
- 传感器故障注入用中间 republish 节点
- 系统级 chaos 用 **chaos-mesh / pumba** + 自动化 launch_test
- 失效响应：**MRM** + vehicle_cmd_gate + emergency_handler
