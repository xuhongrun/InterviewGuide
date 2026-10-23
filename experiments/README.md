# 可复现实验

这里将保存支持核心文档结论的最小实验。当前为建设阶段，尚无实验达到 `verified` 状态。

## 统一要求

每个实验至少包含：

```text
experiment-name/
├── README.md          # 问题、环境、步骤、预期结果
├── src/               # 最小源码
├── config/            # DDS/ROS 2 配置
├── expected/          # 预期结构化结果
└── run.sh             # 一键运行入口
```

实验 README 必须记录 DDS/ROS 2 实现与准确版本、操作系统和编译器版本、被验证的假设、控制变量、测试矩阵、实际输出和结论边界。

## 第一阶段

| 实验 | 目标 | 状态 |
|---|---|---|
| `reliability-rxo` | 验证 Reliability 的四种 Requested/Offered 组合 | planned |
| `durability-late-joiner` | 验证晚加入订阅者能否收到历史样本 | planned |
| `deadline-liveliness` | 验证状态回调和时间语义 | planned |
| `slow-reader` | 观察 History、Resource Limits 和背压 | planned |
| `rtps-fragment-loss` | 区分 RTPS 分片与 IP 分片，观察可靠重传 | planned |

第一项完成后，再扩展下一项，避免只有目录没有证据。
