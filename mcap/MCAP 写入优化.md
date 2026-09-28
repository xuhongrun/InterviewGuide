# MCAP 写入优化与最佳实践

> 面向脱离 ROS2 的原生 C++ 使用场景，重点讨论写入流水线、背压、序列化与 buffer 生命周期、chunk、压缩、索引、时间戳、落盘、轮转、故障恢复和基准测试。

---

## 一、先建立正确的性能模型

一次 MCAP 写入的成本可以近似拆成：

```text
总成本 = 数据采集与业务处理
       + payload 序列化
       + 应用队列与内存复制
       + MCAP record 编码
       + chunk 压缩、CRC 和索引
       + sink 写入与系统调用
       + 文件系统和介质持久化
```

写入优化的优先级通常是：

1. 先确认消息没有在 Writer 之前被重复转换或复制；
2. 用有界队列隔离生产者和单 Writer，并定义背压策略；
3. 根据 CPU 与 I/O 瓶颈选择压缩算法；
4. 同时按吞吐、P99、内存和读放大调整 chunk；
5. 最后才逐项关闭索引、CRC 或 chunk，并明确牺牲的读取能力。

**应用队列与 `chunkSize` 不是同一层缓冲。** 前者吸收生产速率抖动并定义背压，后者是 Writer 内部未压缩 chunk 的目标阈值。把 `chunkSize` 调大不能解决消费者长期落后，反而可能增加内存峰值和压缩停顿。

---

## 二、按负载选择写入模式

| 目标 | 推荐起点 | 关键取舍 |
|------|----------|----------|
| 实时录制并支持后续查询 | chunk + `Lz4` 或 `Zstd Fast` + 完整索引 | 均衡吞吐、体积与查询能力 |
| CPU 紧张、介质带宽充足 | `None` 或 `Lz4` | 降低压缩 CPU，文件和 I/O 可能增大 |
| 磁盘/网络带宽紧张 | `Zstd Fastest/Fast` | 用 CPU 换更少 I/O，必须看 P99 |
| 已压缩图像/视频为主 | `None` 与快速压缩 A/B 测试 | 二次压缩可能收益很低 |
| 极限采集，只做顺序离线处理 | 先关闭 MessageIndex，最后才关闭 chunk | 提高写入上限，但损失随机读能力 |
| 冷归档 | 实时快速写，离线重写为较慢 zstd | 慢压缩不进入采集关键路径 |
| HTTP/S3/OSS 最终归档 | 本地轮转完成后上传 | MCAP 需要在结尾写 Summary/Footer，不宜把未完成对象当成可查询成品 |

决策顺序：

```text
CPU 是否饱和？
  是 -> 分离序列化与 Writer；依次测试 Zstd Fastest、Lz4、None
  否 -> 介质带宽是否饱和？
          是 -> 测试快速压缩，并减少无价值 topic
          否 -> 检查锁、分配、复制、日志、flush 和队列设计

是否需要窄时间窗或稀疏 topic 查询？
  是 -> 保留 chunk、Summary、ChunkIndex、MessageIndex
  否 -> 才测试 noMessageIndex；仍不够时再测试 noChunking
```

---

## 三、C++ Writer 基线模板

先从保留完整读取能力的配置开始，每次只改变一个参数：

```cpp
#include <cstddef>
#include <stdexcept>
#include <string_view>
#include <vector>

#include <mcap/writer.hpp>

mcap::McapWriterOptions options("telemetry");
options.chunkSize = 4 * 1024 * 1024; // 起始值，不是严格上限
options.compression = mcap::Compression::Zstd;
options.compressionLevel = mcap::CompressionLevel::Fast;
options.forceCompression = false;
options.noChunkCRC = false;
options.enableDataCRC = false;
options.noChunking = false;
options.noMessageIndex = false;
options.noSummary = false;

mcap::McapWriter writer;
auto status = writer.open("run.mcap", options);
if (!status.ok()) {
  throw std::runtime_error(status.message);
}

std::string_view schemaData = "...";
mcap::Schema schema("telemetry.Sample", "protobuf", schemaData);
status = writer.addSchema(schema);
if (!status.ok()) {
  throw std::runtime_error(status.message);
}

mcap::Channel channel("/telemetry", "protobuf", schema.id);
status = writer.addChannel(channel);
if (!status.ok()) {
  throw std::runtime_error(status.message);
}

std::vector<std::byte> payload = serializeSample();
mcap::Message message;
message.channelId = channel.id;
message.sequence = sequence;
message.logTime = logTimeNs;
message.publishTime = publishTimeNs;
message.data = payload.data();
message.dataSize = payload.size();

status = writer.write(message);
if (!status.ok()) {
  throw std::runtime_error(status.message);
}

writer.close(); // 刷新最后一个 chunk，写 DataEnd、Summary 和 Footer
```

这是一组基线，不是通用最优值。`4 MiB` 只用于开始测试；最终值由消息尺寸、可压缩性、查询模式、内存预算和设备性能共同决定。

### 3.1 必须遵守的生命周期

- `message.data` 至少在 `writer.write(message)` 返回前有效。
- Attachment 的 `data` 指针同样必须在其 `write()` 返回前有效。
- Writer 会把 record 写入内部 buffer；调用方可以复用 payload buffer，但不能假定整个链路是零拷贝。
- 不要把临时容器的指针、已经移走的 `vector` 数据或生产者正在改写的环形 buffer 交给 Writer。
- `write()` 成功表示 Writer 接受了该 record，不表示数据已经稳定持久化到介质。

### 3.2 每个状态都要处理

`open()`、`addSchema()`、`addChannel()`、`write()` 等返回的 `Status` 都应检查。生产系统至少记录：

- 文件路径和轮转序号；
- channel/topic；
- sequence、log time 和 payload 大小；
- 错误状态及累计失败数；
- 当前队列深度与已丢弃消息数。

发生写入错误后，不要继续把“入队成功”计作“写入成功”。输入、入队、Writer 成功、丢弃和失败必须是不同计数器。

---

## 四、写入流水线与背压

### 4.1 推荐结构

```text
多个采集线程
  -> 可并行的过滤/序列化
  -> 按字节数和条数受限的队列
  -> 单个 Writer 线程
  -> McapWriter
  -> 文件或自定义 IWritable
```

不要让多个线程并发调用同一个 `McapWriter`。并行应放在采集、过滤、压缩前的业务预处理或序列化阶段，最终由一个线程按确定顺序调用 Writer。

单 Writer 的价值不只是避免数据竞争：它还让 sequence、时间戳、轮转、错误处理和指标归属更清晰，减少 Writer 外层锁竞争。

### 4.2 队列必须有界

队列容量同时按**消息条数**和**总字节数**限制。只限制条数时，一批大图像或点云仍可能瞬间耗尽内存。

常见队列满策略：

| 策略 | 适用场景 | 风险 |
|------|----------|------|
| 阻塞生产者 | 上游允许反压、数据不能丢 | 可能把停顿传播到实时线程 |
| 丢最新消息 | 保留已经排队的数据 | 下游逐渐看到陈旧数据 |
| 丢最旧消息 | 更重视最新状态 | 时间线出现缺口，需记录范围 |
| 按 topic/优先级丢弃 | 关键 topic 不得丢 | 策略和审计更复杂 |
| 触发降采样 | 高频连续信号 | 必须保留降采样配置和计数 |
| 轮转/停止录制并告警 | 介质故障或持续过载 | 服务可用性下降但行为明确 |

不能使用无限队列“避免丢数据”。当平均输入速率长期高于输出速率时，无限队列只是把丢消息变成更晚发生的 OOM。

### 4.3 用积压时间衡量队列

除了队列长度，还应监控：

```text
积压字节数
预计积压时间 = 积压字节数 / 最近稳定写出带宽
队首等待时间 = 当前时间 - 队首入队时间
```

队首等待时间比“队列里有 1000 条”更有业务意义，因为消息大小和频率可能相差几个数量级。

### 4.4 停止顺序

正常停止建议按下面的顺序：

1. 停止接收新消息；
2. 等待或按策略处理队列中剩余消息；
3. 让 Writer 线程完成最后一次 `write()`；
4. 调用 `writer.close()`；
5. 需要耐久性时再完成应用定义的同步、重命名和目录同步；
6. 将临时文件发布为完成文件。

避免由任意生产者线程直接 `close()`。否则 Writer 线程可能仍在使用对象或向已经关闭的 sink 写入。

---

## 五、减少序列化、复制与分配

### 5.1 优先复用已有序列化 bytes

如果上游已经给出 CDR、Protobuf 或其他最终 payload：

- 直接把这些 bytes 写入 MCAP；
- 不要为录制而先反序列化成对象再重新序列化；
- 在进入高成本序列化前完成 topic、优先级和采样过滤；
- 不要为日志、统计或路由创建完整 payload 副本。

MCAP 保存 payload bytes，不理解业务对象。减少业务层转换通常比调整某个 Writer 开关更有效。

### 5.2 buffer 所有权要明确

队列元素应拥有 payload，或持有能够证明生命周期的所有权对象。常见安全方案：

- 移动 `std::vector<std::byte>` 到队列；
- 使用有上限的共享 buffer pool，并在 `write()` 返回后归还；
- 固定大小消息使用预分配 slab/ring，但生产者不得覆盖尚未消费的槽位。

每条消息都做一次 `shared_ptr` 分配不一定比移动 `vector` 更快。应把“分配次数、复制字节数、队列锁等待”纳入基准，而不是只看 `write()` 调用耗时。

### 5.3 schema/channel 只注册一次

- 每种 schema 注册一次并缓存 `schema.id`；
- 每个逻辑 channel 注册一次并缓存 `channel.id`；
- 多个 channel 可以复用一个 schema；
- 官方 C++ Writer 不按内容自动去重，重复注册会增加文件体积和元数据处理；
- 热路径只做 channel ID 查找，不做 schema 内容比较或字符串拼接。

使用固定 channel 集时，可在开始录制时全部注册。动态 channel 场景使用受控映射，并让注册和消息写入都由 Writer 线程串行执行。

### 5.4 避免热路径噪声

- 不逐条格式化或打印日志；按时间窗口聚合计数。
- 复用小对象和容器容量，避免反复扩容。
- 不为每条消息构造临时 topic 字符串。
- 批量更新指标，不要在每条消息上争用全局锁。
- 把诊断采样与数据录制分开，避免故障日志进一步压垮 I/O。

---

## 六、chunk 与压缩

### 6.1 `chunkSize` 的真实含义

`chunkSize` 是 Writer 内部**未压缩 chunk 数据**的目标阈值，不是文件写入块大小，也不是严格上限。使 chunk 达到阈值的最后一个 record 可以让实际未压缩大小超过该值；单条超大消息也可能独占一个更大的 chunk。

| 较小 chunk | 较大 chunk |
|------------|------------|
| 压缩停顿较短、随机读放大较小 | 压缩率和顺序吞吐通常更好 |
| 故障影响范围较小 | 固定 record/索引开销较低 |
| chunk、索引和系统调用更多 | 峰值内存、P99 停顿和窄查询成本更高 |

建议从 SDK 默认值或 `1~4 MiB` 起测，再按场景测试 `256 KiB`、`1 MiB`、`4 MiB`、`16 MiB` 等档位。不要在没有查询和内存指标时仅凭吞吐选择最大值。

### 6.2 内存预算

写入峰值内存可能包括：

```text
生产者正在序列化的 payload
+ 有界队列持有的所有 payload
+ Writer 未压缩 chunk buffer
+ 压缩输出和压缩器工作内存
+ 索引与 schema/channel 元数据
+ 文件流和应用其他缓存
```

因此 `队列字节上限 + chunkSize` 仍不是完整 RSS 上限。基准必须记录进程峰值 RSS，并覆盖最坏的大消息突发。

### 6.3 压缩算法选择

| 数据与约束 | 建议起点 |
|------------|----------|
| CPU 紧张、本地 NVMe 充足 | `None` 或 `Lz4` |
| 实时录制、带宽有限 | `Zstd Fastest/Fast` |
| 通用录制与回放 | `Lz4` 或 `Zstd Fast/Default` |
| 离线冷归档 | `Zstd Slow/Slowest`，在非实时机器转换 |
| JPEG/H.264/H.265 等已压缩载荷 | `None` 与快速压缩实测 |
| 原始点云/结构化数值 | 不要假定不可压缩，实测 Lz4/zstd |

官方 C++ Writer 默认可在压缩无收益时保存未压缩 chunk，通常保持 `forceCompression=false`。`CompressionLevel` 是抽象档位，不是跨算法可直接比较的固定整数。

`None` 不一定最快：如果磁盘或上传带宽已经饱和，快速压缩减少的 I/O 可能大于压缩 CPU 成本。

### 6.4 识别压缩造成的长尾

只看平均吞吐会漏掉 chunk 封口时的周期性停顿。至少记录：

- 单次 `write()` 延迟直方图和 P95/P99/P99.9；
- chunk 完成频率与压缩耗时；
- Writer 队列深度和队首等待时间；
- CPU user time、磁盘带宽和磁盘 await；
- 丢消息发生时对应的 chunk 与系统指标。

如果停顿与 chunk 完成同步，优先测试更小 chunk、较快压缩级别或更大的有限写前队列；不能只扩大队列掩盖持续吞吐不足。

---

## 七、索引、Summary 与 CRC

### 7.1 写端决定读端能力上限

```text
保留 chunk
  -> 可以做 chunk 压缩、ChunkIndex 和按 chunk 故障隔离

保留 MessageIndex
  -> 支持时间有序读取和更有效的稀疏 topic 查询

保留 Summary/Footer
  -> Reader 可以从文件尾快速取得索引和统计
```

默认保留 chunk、Summary、ChunkIndex、MessageIndex 和 Chunk CRC。只有基准确认它们是瓶颈，并且产品明确接受读端退化时，才逐项关闭。

### 7.2 降级顺序

建议按以下顺序做 A/B 测试：

1. 保持完整能力，只调 `compression` 和 `chunkSize`；
2. 只做物理顺序读取时，测试 `noMessageIndex=true`；
3. CPU 确实被校验占满时，测试 `noChunkCRC=true`；
4. 纯流式临时产物才考虑 `noSummary=true`；
5. 最后才测试 `noChunking=true`，并计划录制后离线重写。

关闭 Summary 主要减少收尾工作和部分 bookkeeping，不一定提高持续写吞吐。关闭 chunk 则会同时失去 chunk 压缩、有效 ChunkIndex 和较好的故障隔离，不能把两者等同为普通性能开关。

### 7.3 CRC 的边界

- Chunk CRC 便于定位压缩 chunk 的意外损坏，通常应保留。
- Summary CRC 成本通常很低，建议保留。
- Data section CRC 覆盖整个数据段，chunk 模式下是否开启按完整性要求和 CPU 基准决定。
- CRC 检测意外损坏，不提供防篡改能力。
- 归档还应保存 SHA-256 或对象存储提供的独立 checksum；multipart ETag 不一定是文件 MD5。

归档前应实际运行 `mcap doctor`。仅仅写入 CRC 字段，不等于归档流程已经做过完整校验。

---

## 八、时间戳、顺序与文件布局

### 8.1 保持 `logTime` 大致单调

严重乱序会扩大 chunk 的最小/最大时间范围，使后续时间查询命中更多 chunk，并可能让时间有序读取同时保留更多解压数据。

建议：

- 使用明确且一致的纳秒时间基准；
- 区分接收/记录时间 `logTime` 与源端 `publishTime`；
- 对设备时钟回拨、跳变和重同步设置指标；
- 允许有限重排时使用有界窗口，不能为了全局排序无限等待；
- 不要伪造时间戳来“看起来有序”，应保留真实采集语义。

### 8.2 topic 布局会影响查询成本

MCAP chunk 通常混合多个 channel。把低频关键事件长期与超大高频图像放进很大的 chunk，会增加查询关键事件时的解压放大。

当读写目标冲突明显时，可以：

- 调小 chunk；
- 将负载差异极大的数据拆到不同文件；
- 保留完整原始 MCAP，同时生成面向查询的过滤副本；
- 重复分析时转换为 Parquet/Arrow 等分析格式，而不是强迫 MCAP 承担列式分析职责。

不要为微小读收益随意拆出大量小文件。文件轮转还会增加 Summary、对象数量、目录元数据和打开成本。

---

## 九、I/O、flush 与持久化

### 9.1 三个不同的“完成”

必须区分：

```text
Writer 接受 record
  != 数据已离开进程 buffer
  != 数据已到达 OS page cache
  != 数据已稳定写入物理介质
```

Writer 或 stream 的 `flush()` 通常不等价于 `fsync`/`fdatasync`，而同步文件内容也不一定覆盖重命名和目录项的耐久性。断电一致性必须由应用根据文件系统、平台和存储设备明确设计。

### 9.2 不要每条消息同步

逐条 `flush` 或 `fsync` 会把设备同步延迟直接放进热路径，通常导致严重吞吐和 P99 退化。更实际的策略是：

- 按时间或大小轮转文件；
- 在可接受的数据损失窗口内周期同步；
- 文件完成后同步、原子重命名并发布；
- 对“已接收”“已写入 Writer”“已同步完成”分别确认；
- 实测同步发生时是否导致队列溢出。

耐久性和实时性存在真实冲突，不能通过命名一个 `flush()` 调用消除。

### 9.3 自定义 `IWritable`

写入网络、内存或特殊介质时可实现 `mcap::IWritable`。关键约束：

- `size()` 始终等于此前**成功写出**的累计字节数；
- 短写、重试和失败必须有明确语义，不能让索引偏移与真实 sink 不一致；
- 保持 append 顺序，不要异步重排 record；
- `flush()` 的完成语义要写入接口契约；
- Writer 线程与异步 sink 之间仍需要有界缓冲和背压；
- 出错后不要静默继续并生成看似完整的 Footer。

直接流式上传对象存储时，还要处理 multipart 完成前不可随机读取、失败分片清理、对象版本和最终发布原子性。多数系统更容易验证的方案是本地完成轮转文件，校验后再上传。

---

## 十、轮转、异常退出与恢复

### 10.1 轮转条件

常用条件包括：

- 最大时长；
- 最大文件大小；
- 场景/任务边界；
- schema 或配置版本变化；
- 存储余量阈值；
- 主动故障隔离。

轮转文件过大时，close、上传、校验和恢复耗时更长；过小时，Summary、文件系统和对象存储元数据开销上升。应同时测轮转 P99、文件数量、上传效率和查询范围。

### 10.2 使用临时名称发布

推荐生命周期：

```text
run-000123.mcap.partial
  -> 正常 close
  -> 可选同步和 mcap doctor
  -> 原子重命名为 run-000123.mcap
  -> 写清单/上传/通知消费者
```

消费者只读取已完成名称，避免把仍在增长、尚无 Footer 的文件当作可索引成品。临时文件名还可以让启动恢复流程快速识别异常退出产物。

### 10.3 异常退出的现实边界

进程崩溃或断电时，以下数据可能丢失：

- 仍在生产者或应用队列中的消息；
- Writer 尚未封口的 chunk；
- 用户态或 OS cache 中尚未持久化的字节；
- 末尾写到一半的 record；
- 尚未写出的 Summary/Footer。

已经完整落盘的 record/chunk 通常可由 `mcap recover` 重写并重建索引，但 recover 不能恢复从未到达介质的数据。恢复后仍应运行 `mcap doctor`，并把恢复文件作为新产物发布，不要原地覆盖唯一原件。

---

## 十一、基准测试与指标

### 11.1 固定测试矩阵

至少覆盖：

| 维度 | 测试值示例 |
|------|------------|
| 压缩 | `None` / `Lz4` / `Zstd Fastest` / `Zstd Default` |
| chunk | `256 KiB` / `1 MiB` / `4 MiB` / `16 MiB` |
| 索引 | 完整 / `noMessageIndex` / `noChunking` |
| 数据 | 小消息高频 / 原始点云 / JPEG 或视频 / 混合 topic |
| 输入 | 稳态速率 / 突发 / 单条超大消息 / 时间戳乱序 |
| 介质 | tmpfs 基线 / 目标 SSD / 低余量 / 同盘上传干扰 |
| 读取验收 | 全量顺序 / 单 topic / 窄时间窗 / 随机窗口 |

使用相同的输入消息、顺序和时间戳，多轮测试并报告中位数与长尾。tmpfs 可帮助区分 CPU/内存路径和真实磁盘瓶颈，但不能替代目标介质测试。

### 11.2 写入指标

| 类别 | 指标 |
|------|------|
| 正确性 | 输入、入队、成功写入、丢弃、失败消息数与字节数 |
| 延迟 | 入队等待、`write()` P50/P95/P99/P99.9、close/轮转耗时 |
| 队列 | 当前/峰值条数、字节数、队首等待时间、满队列次数 |
| 压缩 | 压缩输入/输出字节、比率、每 chunk 压缩时间 |
| I/O | 写带宽、IOPS、await、同步耗时、磁盘余量 |
| 资源 | CPU user/system、峰值 RSS、分配次数、锁等待 |
| 结果 | 文件大小、chunk/索引数量、doctor/recover 时间 |
| 读端 | 首条消息延迟、查询 P99、实际读取/解压字节 |

建议定义：

```text
有效写入吞吐 = 成功写入 payload 字节 / 墙钟时间
写入放大 = 最终文件字节 / 成功写入 payload 字节
丢弃率 = 丢弃消息数 / 输入消息数
队列利用率 = 当前队列字节 / 队列字节上限
```

压缩文件可能使“写入放大”小于 1，因此它主要用于不同配置间比较，不是传统块存储写放大的同义词。

### 11.3 验收约束

先定义硬约束，再比较性能：

- 关键 topic 是否允许丢失；
- 最大可接受 P99/P99.9；
- 最大内存与磁盘余量；
- 崩溃时允许丢失多少秒数据；
- 是否必须支持窄时间窗和稀疏 topic 查询；
- close 后多久必须完成上传和可查询发布。

不满足正确性和恢复要求的“最高吞吐”不是可用优化。

---

## 十二、场景化配置

### 高频小消息

- 预注册 schema/channel；
- 避免逐条分配、日志和锁；
- 用按字节与条数受限的队列；
- 中等 chunk 起测，观察 record 固定开销；
- Writer 单线程，序列化可在生产者侧并行。

### 点云与多传感器

- 原始点云测试 `Zstd Fast` 与 `Lz4`；
- `1~4 MiB` 起测，覆盖单条消息大于 chunk 阈值的情况；
- 保持时间戳近似有序；
- 监控队列字节而非只看条数；
- 保留完整索引，后续时间窗查询通常很重要。

### JPEG/H.264/H.265 为主

- `None`、`Lz4`、`Zstd Fastest` 做端到端 A/B；
- 不要根据“有压缩选项”就默认必须开启；
- 仍可保留 chunk 和索引，chunk 不等于必须压缩；
- 关注大帧突发对队列和 RSS 的影响。

### 资源受限设备

- 减少无价值 topic 和采样频率优先于关闭文件能力；
- 使用明确的优先级丢弃策略；
- 先测试 `Lz4`/`None` 与较小 chunk；
- 轮转后把慢压缩、doctor 和上传放到非实时任务；
- 监控温度、CPU 降频和磁盘余量，长时间稳态测试。

### 极限采集

- 复用已有序列化 bytes 和 buffer；
- 单 Writer + 有界队列；
- 先降低压缩成本，再测试 `noMessageIndex`；
- 只有确认只需顺序读取时才使用 `noChunking`；
- 完成后离线生成带 chunk、压缩、完整索引和 CRC 的归档副本。

---

## 十三、常见反模式

- 多个线程并发调用同一个 Writer，再用大锁把所有工作串行化。
- 使用无限队列，把持续过载推迟为 OOM。
- 每条消息重复注册 schema/channel。
- 已有序列化 bytes 却反序列化后再次序列化。
- 只限制队列条数，不限制 payload 总字节数。
- 为追求“零拷贝”传递无法证明生命周期的裸指针。
- 只看平均 MB/s，不看 P99、丢消息和队列积压。
- 盲目把 chunk 调大，忽略内存、压缩停顿和随机读放大。
- 默认关闭 MessageIndex、Summary 或 CRC，却没有读端和恢复验收。
- 每条消息 `flush`/`fsync`，又要求低延迟高吞吐。
- 把 `write()` 成功误认为断电后一定存在。
- 把尚未 close 的对象存储上传当成完整可查询 MCAP。
- 用 ETag 代替所有对象存储场景的文件 checksum。
- 出错后继续写并发布看似正常的最终文件。
- 为了写入吞吐关闭 chunk，却没有离线归档转换流程。

---

## 十四、最终 Checklist

- [ ] 先确认瓶颈在序列化、队列、压缩、内存还是介质
- [ ] 使用按消息数和字节数双重限制的有界队列
- [ ] 为队列满定义阻塞、丢弃、降采样或停止策略
- [ ] 单线程调用 Writer，并把可并行工作放在 Writer 之前
- [ ] 复用已有序列化 bytes，减少复制和逐条分配
- [ ] schema/channel 注册一次并缓存 ID
- [ ] 检查 `open`、注册和每次 `write` 的 `Status`
- [ ] 区分输入、入队、成功写入、丢弃与失败计数
- [ ] 从 `Lz4`、`Zstd Fast`、`None` 的实测结果选择压缩
- [ ] chunk 同时按吞吐、P99、RSS 和读放大调优
- [ ] 默认保留 chunk、Summary、ChunkIndex、MessageIndex 和 CRC
- [ ] 关闭能力时记录读端、恢复与完整性影响
- [ ] 保持 `logTime` 时间基准一致且大致单调
- [ ] 不把 `flush` 等同于介质持久化
- [ ] 正常停止时先排空队列，再 `close()` 和发布文件
- [ ] 使用临时名称区分未完成文件
- [ ] 按大小/时长/场景轮转，并监控 close P99
- [ ] 异常文件用 `mcap recover` 生成新文件，再运行 `mcap doctor`
- [ ] 归档保存独立 checksum，不把 multipart ETag 当成 MD5
- [ ] 用真实数据做稳态、突发、超大消息和故障测试

详见：[MCAP 读取优化](MCAP%20读取优化.md) / [MCAP 读写与API](MCAP%20读写与API.md) / [MCAP 性能优化](MCAP%20性能优化.md) / [MCAP 简介](MCAP%20简介.md) / [MCAP 最佳实践](MCAP%20最佳实践.md) / [MCAP Q&A](MCAP%20Q%26A.md)
