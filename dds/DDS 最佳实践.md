# DDS 最佳实践

> 面向 **OMG DDS / RTPS 2.x**（FastDDS、Cyclone DDS、RTI Connext 通用），覆盖发现、QoS、性能、零拷贝、跨域、运维。

---

## 1. Domain / Partition 划分

* **Domain ID** = 物理隔离边界，跨 Domain 默认不发现；不同子系统/不同优先级使用独立 Domain。
* **Partition** = 同 Domain 内的逻辑命名空间，支持通配符（`telemetry.*`），用来区分子团队/版本灰度。
* 推荐：**1 个产品 1 个 Domain，按团队/子系统切 Partition**；测试与生产分 Domain，**禁止用 Domain 0**（默认值，多车互串）。

---

## 2. 发现机制 Discovery

| 模式 | 适用 | 注意 |
|------|------|------|
| **SPDP/SEDP（默认）** | 中小规模、同网段 | 多播必须开（`224.0.0.1`），否则只能单播 |
| **Static Discovery** | 嵌入式 / 受限网络 / 启动时序确定 | XML 描述参与者，无组播开销 |
| **Discovery Server**（FastDDS）/ **Cloud Discovery Service**（RTI） | 跨网段、节点 ≥ 50 | 两台备份，避免单点；版本与端一致 |
| **Initial Peers** | 跨子网，无组播 | 列出对端 IP；规模小可用 |

口诀：**节点 < 30 用默认，30~100 用 DS，>100 必须 DS 或分域**。

详见：[DDS Discovery](../dds/DDS%20Discovery.md) / [DDS-发现阶段网络风暴规避策略](../summarize/dds/DDS-发现阶段网络风暴规避策略.md)

---

## 3. QoS 三组合速查

| 场景 | Reliability | History | Durability | Deadline |
|------|------|------|------|------|
| **传感器 / 高频 IMU/激光** | BEST_EFFORT | KEEP_LAST 1 | VOLATILE | 2× 周期 |
| **控制指令 / 命令** | RELIABLE | KEEP_LAST 1 | VOLATILE | 严格 |
| **状态/参数（迟到订阅者要看到）** | RELIABLE | KEEP_LAST 1 | TRANSIENT_LOCAL | — |
| **配置/事件可靠** | RELIABLE | KEEP_ALL | TRANSIENT_LOCAL/PERSISTENT | — |
| **诊断/日志** | BEST_EFFORT/RELIABLE | KEEP_LAST 100 | VOLATILE | — |

* `RELIABLE + KEEP_ALL + 高频` = 队列爆满 + 内存炸；**严禁默认搭配**。
* `Deadline + LivelinessLost + ResourceLimits` 三件套保护实时控制循环。
* QoS 不匹配会**静默不通信**，必须 `on_offered_incompatible_qos` 监听。

详见：[DDS QOS](../dds/DDS%20QOS.md) / [RTI-DDS流量控制QoS策略](../summarize/dds/RTI-DDS流量控制QoS策略.md)

---

## 4. 数据建模 IDL / XTypes

* **结构稳定优先 mutable extensibility** —— 加字段不破坏老订阅者。
* `final` 用于不会再变的协议（控制指令、安全），最快也最严。
* 大数组优先 **bounded sequence**（`sequence<float, 1024>`），避免无界堆分配。
* 命名空间用 `module`，避免全局名冲突。
* 字符串字段加界 `string<256>`，否则零拷贝退化。
* TypeObject/TypeInformation 自动跨语言传递 schema —— **开启 XTypes** 享受类型演化。

详见：[DDS XTypes IDL](../dds/DDS%20XTypes%20IDL.md) / [DDS XTypes](../dds/DDS%20XTypes.md)

---

## 5. 零拷贝与大数据 Loaned / SHM

* 同主机大消息（≥ 64 KB 或图像/点云）必走 **共享内存 + Loaned Sample**：
  * FastDDS：`SHM transport` + `loan_sample()` / `return_loan()`
  * Cyclone：`iceoryx` 集成
  * RTI：`Zero Copy with FlatData`
* 数据布局必须 **POD / FlatData**：无 STL 容器、无指针、定长字段。
* 内存池预分配大小 ≥ 「队列深度 × 实例数 × 单样本 size」+ 余量。
* 跨主机仍要走 UDP/TCP，但**结构不要变**，用同一份 IDL。

详见：[DDS Zero-Copy](../dds/DDS%20Zero-Copy.md) / [DDS-高频大数据场景优化](../summarize/dds/DDS-高频大数据场景优化.md)

---

## 6. 网络传输 Transport

| Transport | 适用 |
|------|------|
| **UDPv4 多播 + 单播** | 默认；同子网 |
| **UDPv4 单播** | 跨子网，不支持组播 |
| **TCP** | 跨防火墙 / 公网 / 高丢包，需稳定 |
| **SHM** | 同主机零拷贝 |
| **TSN / DDS-XRCE** | 实时以太网 / 受限设备（micro-ROS） |

* 多网卡机器**必须显式绑定 whitelist**，否则可能从错误的网卡发现，引发风暴。
* MTU 路径上一致（典型 1500，TSN 可 1522 / Jumbo 9000）；DDS 大消息走 RTPS 分片。
* 大流量打开 socket buffer：`net.core.rmem_max=8388608`、`wmem_max=8388608`。

详见：[DDS RTPS](../dds/DDS%20RTPS.md) / [DDS-跨域通信大数据场景优化](../summarize/dds/DDS-跨域通信大数据场景优化.md)

---

## 7. 线程模型与执行器

* 高频 topic 配 **专属 ReceiveThread / Listener thread**，避免与控制线程互抢 CPU。
* 用 **WaitSet / Listener** 二选一；混用易死锁。
* 长任务**永远不要在 listener 回调里跑**（会阻塞接收），把数据丢进队列异步处理。
* PREEMPT_RT 内核下，把 DDS 关键线程提升到 SCHED_FIFO 50~80。

---

## 8. 安全 DDS Security

* 5 大插件：**Authentication / AccessControl / Cryptographic / Logging / Tagging**。
* 生产**必启**：身份证书 + Permissions + Governance；车队/医疗等强制要求。
* Permissions 文件按 topic / partition 粒度授权（subscribe/publish）。
* 性能开销：CPU 5~15%，建议核数富余 + 关键 topic 评估是否豁免。

---

## 9. 流量控制 Flow Control

* 大消息 + 高频 → 网卡 / 交换机拥塞，必须配流控：
  * RTI：`flow_controllers` 限令牌速率（bytes/s + period）。
  * FastDDS：`ThroughputController`。
  * Cyclone：`MaxMessageSize` + 内核 `tc qdisc`。
* 无流控的 RELIABLE writer 在 reader 慢时**会无限缓存**，OOM 风险。

详见：[RTI-DDS流量控制QoS策略](../summarize/dds/RTI-DDS流量控制QoS策略.md)

---

## 10. 调试与可观测性

| 工具 | 用途 |
|------|------|
| **Wireshark + RTPS dissector** | 抓包看 SPDP/SEDP/DATA |
| **RTI Admin Console / Monitor** | 拓扑、QoS 不匹配、延迟、吞吐 |
| **`fastdds discovery`** / `fast-dds-shapes-demo` | 拓扑/连通性 |
| **`ros2 doctor` + `ros2 topic hz/bw/echo`** | ROS2 + DDS 复合验证 |
| **`tcpdump -i any 'multicast'`** | 检查多播是否通 |
| **Discovery Server logs** | 查参与者上下线 |

* QoS 不匹配靠 listener 回调（`on_offered_incompatible_qos` / `on_requested_incompatible_qos`），**禁止只看 topic echo**。
* 上线先跑发现风暴压测：N 个节点同时启动看 SPDP 流量峰值。

---

## 11. 工程化 / Vendor 选择

| 维度 | FastDDS | Cyclone DDS | RTI Connext |
|------|------|------|------|
| License | Apache 2.0 | EPL | 商业 |
| ROS2 默认 | Humble/Iron | Jazzy/Rolling 默认 | 商业用户 |
| Discovery Server | ✅ | ❌（用 Cyclone Cloud） | ✅（CDS） |
| 工具链 | OK | 朴素 | 强 |
| 嵌入式 | micro-ROS | 弱 | Connext Micro |
| 安全 | DDS Security | 部分 | 完整 |

口诀：**ROS2 用 Cyclone（默认稳定），跨网段 / 强工具链选 Connext，嵌入式选 FastDDS + micro-ROS**。

---

## 12. 与 ROS2 集成

* **ROS2 Topic = DDS Topic**，名字会被加前缀 `rt/`、`rs/`、`rq/`、`rr/`（话题/服务请求/服务响应）。
* ROS2 QoS profile 实质是 DDS QoS 子集；profile 不匹配同样静默断连。
* `ros2 topic info -v` 查看 QoS 兼容性。
* 用 **Composition + IPC** 在同进程内零拷贝（rclcpp `IntraProcessManager`）。
* 跨域桥接用 **`domain_bridge`** 而非 `ros1_bridge`。

---

## 13. 反模式 Top 12

1. Domain 0 + 默认 QoS 直接上生产。
2. 大消息走默认 UDP，不开 SHM。
3. RELIABLE + KEEP_ALL + 高频 → 队列爆。
4. 用 `string`/`sequence` 无界字段，零拷贝失效。
5. 把所有节点塞同一个 partition，发现风暴。
6. listener 回调里阻塞处理。
7. 多网卡未 whitelist，发现飞错网卡。
8. QoS 不匹配只靠 echo 调试。
9. 不开 Security 的车载 / 医疗系统。
10. 把 IDL 定义为 `final` 后又频繁加字段。
11. Discovery Server 单点没有备份。
12. 调度优先级未提升，控制周期被网络线程抢占。

---

## 14. Top 20 Checklist

1. ☐ Domain ID 规划入仓。
2. ☐ Partition 命名规范文档化。
3. ☐ 节点 ≥ 30 启用 Discovery Server。
4. ☐ 多网卡显式 whitelist。
5. ☐ 同主机大消息开 SHM + Loaned。
6. ☐ IDL 字段全部 bounded（数组/字符串）。
7. ☐ XTypes mutable extensibility 默认开启。
8. ☐ QoS 三组合按场景模板化（YAML 复用）。
9. ☐ Deadline + Liveliness 保护实时 topic。
10. ☐ 大写者配 FlowController。
11. ☐ ResourceLimits 显式封顶。
12. ☐ 监听 `on_*_incompatible_qos` 报警。
13. ☐ socket buffer 调大（rmem/wmem ≥ 8 MB）。
14. ☐ 关键线程 SCHED_FIFO 优先级。
15. ☐ DDS Security 在生产环境启用。
16. ☐ 上线前发现风暴压测（同时启动 N 节点）。
17. ☐ Wireshark + RTPS dissector 备好。
18. ☐ 监控接入：参与者数、丢包率、延迟、缓存深度。
19. ☐ 故障演练：Discovery Server 宕、网卡 down。
20. ☐ vendor 升级走灰度 Domain，回滚预案。

---

## 面试速记

1. **DDS 数据中心模型**：发布订阅 + Topic + 强类型 IDL；无 broker。
2. **Domain / Partition**：物理隔离 vs 逻辑分组。
3. **QoS 不匹配静默不通信** —— RxO（Requested vs Offered）。
4. **Reliability**：RELIABLE = ACK + 重传；BEST_EFFORT = UDP-like。
5. **Durability**：VOLATILE / TRANSIENT_LOCAL / TRANSIENT / PERSISTENT。
6. **History + ResourceLimits** 决定缓冲深度。
7. **零拷贝**两条路：同主机 SHM + Loaned；FlatData/POD 必备。
8. **Discovery**：SPDP（参与者）+ SEDP（端点）；规模大用 Discovery Server。
9. **XTypes** 让 IDL 演化兼容；mutable extensibility。
10. **Security**：5 插件 PKI；车规 / ASIL 必启。

---

## 关联阅读

* [DDS 总览](../dds/DDS.md) · [DDS Discovery](../dds/DDS%20Discovery.md) · [DDS QOS](../dds/DDS%20QOS.md)
* [DDS RTPS](../dds/DDS%20RTPS.md) · [DDS Zero-Copy](../dds/DDS%20Zero-Copy.md)
* [DDS XTypes](../dds/DDS%20XTypes.md) · [DDS XTypes IDL](../dds/DDS%20XTypes%20IDL.md) · [DDS Q&A](../dds/DDS%20Q&A.md)
* [DDS-高频大数据场景优化](../summarize/dds/DDS-高频大数据场景优化.md)
* [DDS-跨域通信大数据场景优化](../summarize/dds/DDS-跨域通信大数据场景优化.md)
* [DDS-发现阶段网络风暴规避策略](../summarize/dds/DDS-发现阶段网络风暴规避策略.md)
* [RTI-DDS流量控制QoS策略](../summarize/dds/RTI-DDS流量控制QoS策略.md)
* [DDS-自动驾驶应用](../summarize/dds/DDS-自动驾驶应用.md)
* [MQTT与DDS对比](../summarize/dds/MQTT与DDS对比.md) · [协议栈对比(CAN-SOMEIP-DDS)](../summarize/dds/协议栈对比(CAN-SOMEIP-DDS).md)
