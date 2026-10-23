# Vehicle Middleware Knowledge Base

> 面向 C++ 工程师的 DDS、ROS 2、MCAP 与车载中间件知识库。

这个仓库最初用于面试复习，现在逐步转向一套**可验证、可复现、可持续维护**的系统工程知识库。面试题仍会保留，但不再是唯一目标。

## 这个仓库解决什么问题

- 理解 DDS/RTPS 的发现、QoS、可靠传输、类型演化与零拷贝。
- 理解 ROS 2 从 `rclcpp`、`rmw` 到 DDS 的通信链路。
- 处理通信不匹配、延迟、丢包、积压、内存增长与发现风暴。
- 设计高吞吐数据录制与读取链路，理解 MCAP 的索引、压缩和持久化边界。
- 复习支撑上述工作的现代 C++、Linux、网络和并发基础。

## 内容可信度

仓库中的文档处于不同成熟度。阅读时请关注文首状态：

| 状态 | 含义 |
|---|---|
| `draft` | 学习笔记，可能包含待核对结论 |
| `reviewed` | 已对照规范或官方文档人工检查 |
| `verified` | 附可运行实验、版本信息和预期结果 |

没有标记的历史文档暂按 `draft` 处理。示例参数不是生产环境的通用推荐，使用前应根据 DDS 厂商、版本、网络和硬件重新验证。

详细规则见 [内容质量规范](docs/CONTENT_QUALITY.md)。

## 推荐学习路线

### 路线一：DDS 与车载中间件

1. [DDS 概述](dds/DDS.md)
2. [DDS QoS](dds/DDS%20QOS.md)
3. [DDS Discovery](dds/DDS%20Discovery.md)
4. [DDS RTPS](dds/DDS%20RTPS.md)
5. [DDS XTypes](dds/DDS%20XTypes.md)
6. [DDS Zero-Copy](dds/DDS%20Zero-Copy.md)
7. [DDS 最佳实践](dds/DDS%20最佳实践.md)
8. [DDS 排查清单](dds/DDS%20Q%26A.md)

### 路线二：ROS 2 通信链路

1. [ROS 2 简介](ros/ros2/ROS2%20简介.md)
2. [节点与执行器](ros/ros2/ROS2%20节点与执行器.md)
3. [话题、服务与 Action](ros/ros2/ROS2%20话题、服务与Action.md)
4. [DDS 与 QoS](ros/ros2/ROS2%20DDS与QoS.md)
5. [生命周期与组件化](ros/ros2/ROS2%20生命周期与组件化.md)
6. [实时性与性能优化](ros/ros2/ROS2%20实时性与性能优化.md)
7. [调试诊断与 bag](ros/ros2/ROS2%20调试诊断与bag.md)

### 路线三：数据录制与 MCAP

1. [MCAP 简介](mcap/MCAP%20简介.md)
2. [MCAP 读写与 API](mcap/MCAP%20读写与API.md)
3. [MCAP 写入优化](mcap/MCAP%20写入优化.md)
4. [MCAP 读取优化](mcap/MCAP%20读取优化.md)
5. [MCAP 性能优化](mcap/MCAP%20性能优化.md)

### 路线四：系统基础

- [C++ 最佳实践](cpp/C++%20最佳实践.md)
- [C++ 多线程](cpp/C++%20多线程.md)
- [C++ 进程间通信](cpp/C++%20进程间通信（IPC）.md)
- [Linux 基础](os/Linux%20基础.md)
- [TCP/UDP](network/TCP%20UDP.md)
- [I/O 多路复用](network/IO%20多路复用.md)
- [Socket 编程](network/网络编程%20Socket.md)

## 可复现实验

文档之外，仓库将逐步增加可运行实验。规划和验收标准见 [experiments/](experiments/README.md)。第一阶段包括：

1. Reliability Requested/Offered 四种组合。
2. Durability 与晚加入订阅者。
3. Deadline、Liveliness 状态回调。
4. 慢消费者、History 与 Resource Limits。
5. RTPS 分片、丢包和可靠重传。

实验尚未完成前，相关理论文档不会标记为 `verified`。

## 目录

| 目录 | 定位 |
|---|---|
| [`dds/`](dds/) | DDS、RTPS、QoS、XTypes、零拷贝 |
| [`ros/`](ros/) | ROS 1/2、机器人系统和中间件集成 |
| [`mcap/`](mcap/) | 数据录制、读取、索引与性能 |
| [`cpp/`](cpp/) | C++ 语言、并发、内存与 Eigen |
| [`network/`](network/) | 网络协议与网络编程 |
| [`os/`](os/) | Linux 与系统基础 |
| [`summarize/`](summarize/) | 面试速记和公开教学案例 |
| [`mpc/`](mpc/) | MPC 学习笔记 |
| [`python/`](python/) | Python 学习笔记 |
| [`architecture/`](architecture/) | 架构与分布式系统笔记 |
| [`tools/`](tools/) | Git、Docker、SQLite 等工具笔记 |
| [`reference/`](reference/) | 仅保存可公开分发的索引和来源说明 |

MPC、Python、数据库等内容属于扩展笔记。仓库主线优先维护 DDS、ROS 2、MCAP 和相关系统基础。

## 使用方式

- **准备面试**：阅读 [`summarize/`](summarize/) 和各主题的 Q&A。
- **系统学习**：按上面的路线阅读，并亲自运行对应实验。
- **排查问题**：从 [DDS 排查清单](dds/DDS%20Q%26A.md) 和 [系统问题排查](summarize/cpp/系统问题排查.md) 开始。
- **参与维护**：提交错误、版本差异、复现步骤或实验结果，参见 [贡献指南](CONTRIBUTING.md)。

## 内容与合规边界

- 不提交雇主或客户的代码、配置、日志、抓包、内部名称和未公开参数。
- 工程案例必须脱敏，并优先通过公开技术栈重新构造。
- 不直接收录版权状态不明确的书籍、课程或面试资料 PDF。
- 引用第三方内容时标明来源和许可证；仓库许可证只覆盖有权授权的原创内容。
- AI 可以辅助整理和表达，但技术结论必须由作者核对；标记为 `verified` 的内容还必须有实验依据。

第三方内容处理方式见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 路线图

近期不以收费为目标，优先完成以下基础建设：

- [ ] 核查 10 篇 DDS/ROS 2 核心文档。
- [ ] 完成 5 个可一键运行的 DDS 实验。
- [ ] 为核心文档补齐版本、来源和验证状态。
- [ ] 建立 Markdown 链接与内容边界自动检查。
- [ ] 邀请至少 5 位读者独立复现实验。

当这些目标完成后，可基于公开知识库延伸实验包、系统课程和企业培训；公开 Markdown 本身将继续免费。

## License

除单独注明外，作者拥有授权权利的原创代码与文档采用 [Apache License 2.0](LICENSE)。第三方材料仍适用其原许可证，不因进入本仓库而变更。
