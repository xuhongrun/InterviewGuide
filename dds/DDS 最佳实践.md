# DDS 最佳实践

> 状态：`reviewed`（2026-10-10）。面向 OMG DDS / RTPS 2.x，厂商能力和配置名仍需按具体版本核对；本文参数均为起点，不是生产环境通用值。

---

## 1. Domain / Partition 划分

* **Domain ID** = DDS 的逻辑通信域。不同 Domain 默认不发现和通信，但它不是网络或安全意义上的物理隔离。
* **Partition** = 同 Domain 内的逻辑命名空间，支持通配符（`telemetry.*`），用来区分子团队/版本灰度。
* 建议显式规划 Domain ID，避免测试节点误入默认 Domain 0。生产隔离还应依赖 VLAN、防火墙和 DDS Security。

---

## 2. 发现机制 Discovery

| 模式 | 适用 | 注意 |
|------|------|------|
| **SPDP/SEDP（默认）** | 中小规模、同网段 | 常用组播完成初始发现；地址和单播回退方式由实现与配置决定 |
| **Static Discovery** | 嵌入式 / 受限网络 / 启动时序确定 | XML 描述参与者，无组播开销 |
| **Discovery Server**（Fast DDS）/ **Cloud Discovery Service**（RTI） | 跨网段或发现流量成为瓶颈 | 评估高可用和版本兼容性 |
| **Initial Peers** | 跨子网，无组播 | 列出对端 IP；规模小可用 |

不要仅按节点数量选择发现方案。应在目标网络中同时启动预期数量的 Participant，测量发现完成时间、峰值带宽、CPU 和丢包后再决定。

详见：[DDS Discovery](../dds/DDS%20Discovery.md) / [DDS-发现阶段网络风暴规避策略](../summarize/dds/DDS-发现阶段网络风暴规避策略.md)

---

## 3. QoS 三组合速查

| 场景 | Reliability | History | Durability | Deadline |
|------|------|------|------|------|
| **传感器 / 高频 IMU/激光** | BEST_EFFORT | KEEP_LAST 1 | VOLATILE | 2× 周期 |
| **控制指令 / 命令** | 按时效与完整性要求选择 | KEEP_LAST 1 | VOLATILE | 按控制周期定义 |
| **状态/参数（迟到订阅者要看到）** | RELIABLE | KEEP_LAST 1 | TRANSIENT_LOCAL | — |
| **配置/事件可靠** | RELIABLE | KEEP_ALL | TRANSIENT_LOCAL/PERSISTENT | — |
| **诊断/日志** | BEST_EFFORT/RELIABLE | KEEP_LAST 100 | VOLATILE | — |

* `RELIABLE + KEEP_ALL + 高频` 在慢消费者下容易造成积压；必须同时设置 Resource Limits、最大阻塞时间和监控。
* Deadline 和 Liveliness 用于检测时序与活性异常，不能替代应用层安全状态机。
* QoS 兼容性遵循 Requested/Offered 关系。Writer 和 Reader 应分别监听不兼容 QoS 状态，而不是只观察 `topic echo`。

详见：[DDS QOS](../dds/DDS%20QOS.md) / [RTI-DDS流量控制QoS策略](../summarize/dds/RTI-DDS流量控制QoS策略.md)

---

## 4. 数据建模 IDL / XTypes

* 根据演化需求选择 `final`、`appendable` 或 `mutable`。`mutable` 更灵活，但并非所有实现、版本和零拷贝路径都具有相同行为或开销。
* `final` 用于不会再变的协议（控制指令、安全），最快也最严。
* 大数组优先 **bounded sequence**（`sequence<float, 1024>`），避免无界堆分配。
* 命名空间用 `module`，避免全局名冲突。
* 字符串字段加界 `string<256>`，否则零拷贝退化。
* TypeObject/TypeInformation 可辅助类型发现与协商，但支持程度取决于厂商、版本和配置。

详见：[DDS XTypes IDL](../dds/DDS%20XTypes%20IDL.md) / [DDS XTypes](../dds/DDS%20XTypes.md)

---

## 5. 零拷贝与大数据 Loaned / SHM

* 同主机大消息可以评估 **共享内存 + Loaned Sample**，是否值得启用应以端到端延迟、吞吐、RSS 和故障恢复测试决定：
  * FastDDS：`SHM transport` + `loan_sample()` / `return_loan()`
  * Cyclone：`iceoryx` 集成
  * RTI：`Zero Copy with FlatData`
* 真正的零拷贝通常要求受约束的数据布局；具体限制由厂商的共享内存和类型系统实现决定。
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

* 多网卡机器应显式选择接口，避免发现和用户数据走错网卡。新版本配置项可能使用 `allowlist` 等名称，应查阅厂商文档。
* MTU 路径上一致（典型 1500，TSN 可 1522 / Jumbo 9000）；DDS 大消息走 RTPS 分片。
* Socket buffer 应根据峰值速率、调度延迟和可接受排队时间计算，并通过丢包与延迟测试验证，不能直接套用固定值。

详见：[DDS RTPS](../dds/DDS%20RTPS.md) / [DDS-跨域通信大数据场景优化](../summarize/dds/DDS-跨域通信大数据场景优化.md)

---

## 7. 线程模型与执行器

* 先确认 DDS 实现的接收、事件与异步发送线程模型，再决定是否隔离 CPU 或调整优先级。
* WaitSet 和 Listener 可以按职责组合，但要明确回调线程、重入和锁顺序。
* Listener 回调应保持短小、非阻塞；耗时业务通常转移到有界队列和工作线程。
* PREEMPT_RT 下的调度策略与优先级必须结合整机线程清单验证，错误的 `SCHED_FIFO` 设置可能造成优先级反转或饿死。

---

## 8. 安全 DDS Security

* 5 大插件：**Authentication / AccessControl / Cryptographic / Logging / Tagging**。
* 是否启用 DDS Security 由威胁模型、法规、系统边界和性能预算决定；Domain ID 和 Partition 都不能替代访问控制。
* Permissions 文件按 topic / partition 粒度授权（subscribe/publish）。
* 安全开销与算法、消息大小、频率、硬件和厂商实现相关，必须在目标平台测量。

---

## 9. 流量控制 Flow Control

* 大消息 + 高频 → 网卡 / 交换机拥塞，必须配流控：
  * RTI：`flow_controllers` 限令牌速率（bytes/s + period）。
  * FastDDS：`ThroughputController`。
  * Cyclone：`MaxMessageSize` + 内核 `tc qdisc`。
* 慢 Reader 可能让 RELIABLE Writer 积压、阻塞或丢弃数据，具体结果由 History、Resource Limits、可靠性窗口和最大阻塞时间共同决定。

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
| ROS 2 可用性 | 常见 RMW 实现之一 | 常见 RMW 实现之一 | 需要单独获取，常见于商业项目 |
| Discovery Server | ✅ | ❌（用 Cyclone Cloud） | ✅（CDS） |
| 工具链 | OK | 朴素 | 强 |
| 嵌入式 | micro-ROS | 弱 | Connext Micro |
| 安全 | 支持情况随版本变化 | 支持情况随版本变化 | 商业版本提供完整工具链，按版本核对 |

选型应基于许可证、目标平台、所需 QoS、共享内存、安全、工具链、互操作测试和长期支持，不使用单一口诀代替评估。

---

## 12. 与 ROS2 集成

* ROS 2 实体通常经 RMW 映射到 DDS 实体。Topic 名称前缀和服务映射属于 ROS 2/RMW 约定，原生 DDS 应用互通时需核对类型名与名称映射。
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
5. 误以为 Partition 能隔离 Participant 发现流量。
6. listener 回调里阻塞处理。
7. 多网卡未 whitelist，发现飞错网卡。
8. QoS 不匹配只靠 echo 调试。
9. 未做威胁建模就默认 Domain/Partition 已提供安全隔离。
10. 把 IDL 定义为 `final` 后又频繁加字段。
11. Discovery Server 单点没有备份。
12. 未测量线程模型就直接修改实时优先级。

---

## 14. Top 20 Checklist

1. ☐ Domain ID 规划入仓。
2. ☐ Partition 命名规范文档化。
3. ☐ 在目标规模下测量发现时间和发现流量，再选择发现架构。
4. ☐ 多网卡显式 whitelist。
5. ☐ 同主机大消息对比 SHM/Loaned 与普通传输的收益和恢复行为。
6. ☐ 对实时路径中的可变长字段设置合理上界。
7. ☐ 按类型演化需求选择 XTypes extensibility。
8. ☐ QoS 三组合按场景模板化（YAML 复用）。
9. ☐ Deadline + Liveliness 保护实时 topic。
10. ☐ 大流量 Writer 评估 Flow Controller。
11. ☐ ResourceLimits 显式封顶。
12. ☐ 监听 `on_*_incompatible_qos` 报警。
13. ☐ 根据流量模型测量并设置 Socket buffer。
14. ☐ 记录线程模型、CPU 亲和性与实时调度测试结果。
15. ☐ 完成威胁建模并决定认证、授权与加密策略。
16. ☐ 上线前发现风暴压测（同时启动 N 节点）。
17. ☐ Wireshark + RTPS dissector 备好。
18. ☐ 监控接入：参与者数、丢包率、延迟、缓存深度。
19. ☐ 故障演练：Discovery Server 宕、网卡 down。
20. ☐ vendor 升级走灰度 Domain，回滚预案。

---

## 面试速记

1. **DDS 数据中心模型**：发布订阅 + Topic + 强类型 IDL；无 broker。
2. **Domain / Partition**：逻辑通信域 vs 域内 Topic 分组；两者都不是安全隔离。
3. **QoS 不匹配静默不通信** —— RxO（Requested vs Offered）。
4. **Reliability**：RELIABLE = ACK + 重传；BEST_EFFORT = UDP-like。
5. **Durability**：VOLATILE / TRANSIENT_LOCAL / TRANSIENT / PERSISTENT。
6. **History + ResourceLimits** 决定缓冲深度。
7. **零拷贝**：同主机可评估 SHM + Loaned；数据布局限制和回退行为由实现决定。
8. **Discovery**：SPDP（参与者）+ SEDP（端点）；规模大用 Discovery Server。
9. **XTypes** 提供类型演化机制；`final`、`appendable`、`mutable` 应按兼容目标选择。
10. **Security**：认证、访问控制、加密等能力按威胁模型和系统要求配置；ASIL 与网络安全要求不能直接等同。

---

## 关联阅读

* [DDS 总览](../dds/DDS.md) · [DDS Discovery](../dds/DDS%20Discovery.md) · [DDS QOS](../dds/DDS%20QOS.md)
* [DDS RTPS](../dds/DDS%20RTPS.md) · [DDS Zero-Copy](../dds/DDS%20Zero-Copy.md)
* [DDS XTypes](../dds/DDS%20XTypes.md) · [DDS XTypes IDL](../dds/DDS%20XTypes%20IDL.md) · [DDS Q&A](../dds/DDS%20Q%26A.md)
* [DDS-高频大数据场景优化](../summarize/dds/DDS-高频大数据场景优化.md)
* [DDS-跨域通信大数据场景优化](../summarize/dds/DDS-跨域通信大数据场景优化.md)
* [DDS-发现阶段网络风暴规避策略](../summarize/dds/DDS-发现阶段网络风暴规避策略.md)
* [RTI-DDS流量控制QoS策略](../summarize/dds/RTI-DDS流量控制QoS策略.md)
* [DDS-自动驾驶应用](../summarize/dds/DDS-自动驾驶应用.md)
* [MQTT与DDS对比](../summarize/dds/MQTT与DDS对比.md) · [协议栈对比(CAN-SOMEIP-DDS)](../summarize/dds/协议栈对比(CAN-SOMEIP-DDS).md)

## 核查依据

- [OMG Data Distribution Service (DDS) 1.4](https://www.omg.org/spec/DDS/1.4)
- [OMG DDS Interoperability Wire Protocol (DDSI-RTPS) 2.5](https://www.omg.org/spec/DDSI-RTPS/2.5)
- [OMG DDS Extensible and Dynamic Topic Types (DDS-XTypes) 1.3](https://www.omg.org/spec/DDS-XTypes/1.3)
- [OMG DDS Security 1.1](https://www.omg.org/spec/DDS-SECURITY/1.1)

厂商功能名、默认值和版本支持仍应以对应版本的 Fast DDS、Cyclone DDS、RTI Connext 或 OpenDDS 文档为准。
