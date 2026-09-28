# MCAP 读写性能优化总结

> MCAP 的性能调优不是单纯把 chunk 调大。本文以脱离 ROS2 的 C++ SDK 为主：先判断瓶颈在采集/序列化、应用队列、压缩 CPU、内存、磁盘还是网络，再在吞吐、随机访问、文件大小、完整性和故障恢复之间取舍。

---

## 一、先记住 8 个结论

1. **MCAP 的优势是顺序追加 + chunk 压缩 + 尾部索引**，写入路径不需要数据库事务、页和 B-tree。
2. **保留 chunk 通常比关闭 chunk 更实用**：它提供压缩、ChunkIndex、按时间跳读和故障隔离。只有极限实时写才考虑 `fastwrite`/`noChunking`，录完再转换。
3. **MessageIndex 不能绕过 chunk 解压**。压缩以整个 chunk 为单位；MessageIndex 主要帮助读端判断 chunk 是否包含目标 channel，并提供 chunk 内消息偏移。
4. **chunk 越大不一定越快**：通常压缩率和顺序吞吐更好，但内存峰值、压缩停顿、随机读放大和故障影响范围也更大。
5. **应用写队列不等于 `chunkSize`**：前者用于解耦生产者与 writer、吸收速率抖动；后者是 MCAP writer 的未压缩 chunk 目标大小。
6. **优先使用 MCAP 内建 chunk 压缩**。容器外再套整文件压缩会让内部索引无法被直接随机访问。
7. **最快的读取是少读、少解压、少反序列化**：把 topic 和时间范围交给 Reader，过滤前不要先构造业务对象。
8. **参数没有脱离数据集的最优值**。必须同时测丢消息、P99 写入停顿、CPU、内存、磁盘带宽、文件大小和查询延迟。

---

## 二、定位真正的瓶颈

典型写入链路：

```text
数据源 -> 序列化 -> 应用有界队列 -> McapWriter chunk buffer
       -> 压缩/CRC/索引 -> OS page cache -> 文件系统/磁盘
```

| 现象 | 常见瓶颈 | 优先检查 |
|------|----------|----------|
| CPU 满、磁盘不忙、开始丢消息 | 序列化或压缩 | 改 `Lz4`/`None` 或 `Zstd Fastest`；减少录制 topic；用原始序列化字节直写 |
| 磁盘持续满带宽、CPU 有余量 | I/O | 开启快速 chunk 压缩；换独立 NVMe；减少已无价值的数据 |
| 周期性丢帧 | chunk 压缩/落盘造成长尾停顿 | 调小 chunk；调整有界写队列吸收抖动；检查 P99 而非只看均值 |
| 内存持续上涨或 OOM | cache/chunk/消费者积压 | 限制有界队列；调小 cache/chunk；流式消费 |
| 时间/topic 查询仍扫描大量数据 | 索引缺失、chunk 太大或时间戳乱序 | 保留 Summary/ChunkIndex/MessageIndex；调小 chunk；检查 `log_time` |
| 网络对象读取慢 | 请求次数或读放大 | Range Read + 索引；合并邻近范围；缓存 footer/summary 和热点 chunk |

先做 `None`、`Lz4`、`Zstd Fastest` 三组对照。若 `None` 反而更慢，通常说明磁盘/网络已经是瓶颈，压缩减少 I/O 的收益超过了 CPU 成本。

---

## 三、写入性能优化

本节保留决策摘要；完整的 C++ 写入流水线、背压、buffer 生命周期、持久化、轮转恢复与实战经验见：[MCAP 写入优化](MCAP%20写入优化.md)。

### 3.1 压缩选择

| 数据与目标 | 建议起点 | 原因 |
|------------|----------|------|
| CPU 紧张、磁盘足够快 | `None` 或 `Lz4` | 降低压缩 CPU 和长尾停顿 |
| 实时录制且磁盘/网络有限 | `Zstd` + `Fastest`/`Fast` | 常能用少量 CPU 换取显著 I/O 降低 |
| 通用录制/回放 | `Zstd` + `Default` | 体积、写速和读速较平衡 |
| 离线冷归档 | `Zstd` + `Slow`/`Slowest` | 应在录制后转换，不占用实时采集资源 |
| JPEG/H.264/H.265 等已压缩载荷 | `None` 或快速压缩后实测 | 二次压缩收益通常较低 |

- 官方 C++ writer 默认会在压缩没有收益时把该 chunk 原样存储；一般不要开启 `forceCompression`。
- C++ 使用 `CompressionLevel::{Fastest, Fast, Default, Slow, Slowest}`，不同算法的档位映射不同，不要把它当成固定整数压缩级别。
- 不要笼统认为点云“已压缩”。原始 `PointCloud2` 往往仍有可压缩空间；JPEG/视频码流才是典型已压缩数据。

### 3.2 chunk 大小

`chunkSize` 是**未压缩 payload 的触发阈值，不是严格上限**；写入使其达到阈值的最后一条 record 可能让 chunk 超出该值。

| 较小 chunk | 较大 chunk |
|------------|------------|
| 随机读放大小、单次解压延迟低 | 压缩率通常更高、索引与 I/O 次数更少 |
| 压缩停顿更短、故障影响范围小 | 顺序写/读吞吐通常更好 |
| 索引更大、固定开销更多 | 内存峰值和 P99 停顿可能更高 |

建议从实现默认值或 **1~4 MiB** 起测；只有在大消息、高吞吐顺序读写且内存充足时，再试 8~16 MiB。单条消息本身很大时，chunk 仍可能超过设定阈值。

内存预算不能只算一个 `chunkSize`：writer 可能同时持有未压缩和压缩 buffer，外面还有采集、序列化和应用队列。应以进程 RSS 峰值实测。

### 3.3 索引和 Summary

默认建议保留：

- **ChunkIndex**：按 chunk 的时间范围和文件偏移定位，是高效随机读的基础。
- **MessageIndex**：记录每个 channel 在 chunk 内的消息偏移，并让读取器在按 topic 查询时排除不含目标 channel 的 chunk。
- **Summary**：让工具从 Footer 快速取得 schema、channel、统计与索引。

可优化的顺序：

1. 完全不需要按 topic 查询时，先试 `noMessageIndex: true`，仍保留 chunk 和 ChunkIndex。
2. 极限采集端才使用 `fastwrite`/`noChunking`。它会失去 chunk 压缩和有效的索引访问，不适合作为长期归档格式。
3. 采集后在后台机器转换为带 chunk、压缩和完整索引的新文件，而不是让实时机器做慢压缩。

关闭 Summary 主要减少收尾写入、文件体积和部分 bookkeeping，不应未经基准就宣称会“显著”提高持续写吞吐。

### 3.4 CRC 的取舍

- **Chunk CRC**：推荐保留，能把损坏定位到 chunk；实时 CPU 确实不足时再关闭。
- **Summary CRC**：成本通常很低，建议保留。
- **Data section CRC**：覆盖整个数据段，代价更高；无 chunk 时更有价值。
- “文件里有 CRC”不等于整条归档链路已经验证；归档前还应使用 `mcap doctor` 实际检查。

CRC 只检测意外损坏，不提供防篡改能力。归档/传输还应保存 SHA-256 或对象存储 checksum；multipart ETag 不一定是文件 MD5。

### 3.5 缓冲、并发与落盘

- 使用**有界队列 + 单 writer 线程**：采集线程只入队，writer 顺序追加。队列满时要有明确策略（阻塞、丢低优先级 topic、告警），不能无限增长。
- 不要假定同一个 Writer 可以被多线程并发调用；需要并行时，在序列化/预处理阶段并行，最终集中顺序写。
- 大批量 API 的收益主要来自减少语言边界、锁和小对象分配；MCAP 格式本身仍按 record 写入。
- Writer/stdio 的 `flush`、OS page cache 与真正持久化到介质不是一回事。需要断电耐久性时应设计文件轮转与显式同步策略，并实测同步带来的停顿。

### 3.6 减少无效工作

- schema/channel 注册一次并缓存 ID。官方 C++ Writer **不会自动按内容去重**，重复注册会制造冗余。
- 直接写已有的 CDR/Protobuf 序列化字节，避免“反序列化 -> 修改无关字段 -> 再序列化”。
- 在采集源或进入写队列前过滤，晚到 writer 线程再丢弃已经浪费了序列化和内存带宽。
- 让 `log_time` 尽量单调。严重乱序会扩大多个 chunk 的时间范围，使时间查询命中并解压更多 chunk。
- 按时长/大小轮转文件。轮转能缩短恢复和上传单元，但过小文件会增加对象数量、元数据和打开开销。
- 磁盘保持足够空闲，使用独立 NVMe/SSD，避免与系统日志、swap、数据上传争抢同一设备。

### 3.7 极限写入模式：按阶梯逐项牺牲能力

如果目标是把吞吐逼近设备上限，建议按下面顺序做 A/B 测试，每次只改变一个变量：

1. **先消除应用层开销**：生产线程直接复用序列化 buffer，避免反序列化后再序列化；预先注册并缓存 schema/channel ID；队列节点和小对象使用对象池或 `reserve`，避免每条消息动态分配。
2. **再降低压缩成本**：`Zstd Fastest` → `Lz4` → `None` 逐级测试。不要默认 `None` 最快；当磁盘或网络受限时，快速压缩反而能提高端到端吞吐。
3. **再减少索引工作**：只做物理顺序扫描时测试 `noMessageIndex=true`；仍不足时才测试 `noChunking=true`。后者同时失去 chunk 压缩、ChunkIndex 的收益和较好的故障隔离，只适合作为临时采集格式。
4. **最后处理持久化边界**：不要每条消息 `flush`/`fsync`；按文件轮转或时间间隔批量同步。`flush` 只代表写入 sink，不代表已经落到稳定介质；需要断电耐久性时必须接受同步造成的长尾停顿并实测。

MCAP Writer 会把 payload 写入自己的 record/chunk buffer，因此“零拷贝”通常只能做到**应用生产者到 Writer 调用前**；不能据此假定整个写入链路完全没有一次复制。极限模式也必须保留输入、成功写入、队列丢弃和 Writer 错误计数，否则吞吐数字没有意义。

---

## 四、读取性能优化

本节保留决策摘要；完整的 C++ 读取路径、内存模型、并行、远程 I/O 与实战经验见：[MCAP 读取优化](MCAP%20读取优化.md)。

### 4.1 选择正确的读取路径

| 任务 | 最优路径 |
|------|----------|
| 全量回放/ETL | 物理顺序读取，关闭不必要的时间排序，逐条消费 |
| 小时间窗查询 | seekable reader + Summary/ChunkIndex + `start_time`/`end_time` |
| 少量 topic 查询 | 再加 `topics` 参数并保留 MessageIndex |
| pipe/socket | non-seeking 流式读取，按文件顺序消费 |
| 对象存储 | Footer/Summary Range Read，再按索引读取命中 chunk |

C++ Reader 用 `ReadMessageOptions` 同时传入时间、topic 和读取顺序：

```cpp
mcap::McapReader reader;
auto status = reader.open("run.mcap");
if (!status.ok()) {
  throw std::runtime_error(status.message);
}

reader.readSummary(mcap::ReadSummaryMethod::NoFallbackScan);
mcap::ReadMessageOptions options;
options.startTime = startNs;
options.endTime = endNs;  // 开区间
options.topicFilter = [](std::string_view topic) {
  return topic == "/points";
};
options.readOrder = mcap::ReadMessageOptions::ReadOrder::FileOrder;

auto onProblem = [](const mcap::Status& problem) {
  // 记录或上报损坏/解析错误
};
for (const auto& view : reader.readMessages(onProblem, options)) {
  process(view.message.data, view.message.dataSize);
}
reader.close();
```

全量读取优先 `FileOrder`，避免排序开销。需要全局时间顺序时再选 `LogTimeOrder`；完整 message index 能支持该路径，但会增加索引读取和调度开销。

### 4.2 降低读放大和解码成本

- 将 `topics`、`start_time`、`end_time` 直接传给 Reader。回调内再过滤只能省业务处理，通常省不了已发生的 I/O 和解压。
- ChunkIndex 先按时间排除 chunk；MessageIndex 的 channel 集合再按 topic 排除 chunk。命中后仍需解压**整个压缩 chunk**。
- 只在过滤完成后反序列化。若只需 topic、时间戳、大小或原始 bytes，不要创建 ROS 消息对象或 JSON。
- 重复查询相邻窗口时，在应用层缓存已解压 chunk 或聚合多个查询；多数 SDK 不保证跨查询保留解压结果。
- 全量分析若会反复扫描，先一次性转换成面向分析的 Parquet/Arrow/数据库。MCAP 是采集与交换格式，不是所有分析查询的终态存储。

### 4.3 并行读取

- 最容易扩展的是**按文件并行**，每个 worker 独立 Reader。
- 单文件可按 ChunkIndex 的偏移/时间范围分区，每个 worker 使用独立文件句柄；不要共享一个会 `seek` 的流对象。
- chunk 时间范围可能因 topic 交错或乱序而重叠。并行后如需全局 `log_time` 顺序，要做归并排序并处理边界去重。
- 并发度超过磁盘队列、解压 CPU 或对象存储限流后只会增加争用，应通过吞吐曲线选拐点。

### 4.4 远程与对象存储

- 缓存文件尾的 Footer、Summary 和索引，避免每次查询重新拉取。
- 用 HTTP/S3 Range Read 精确取命中 chunk；把相邻小 range 合并，减少请求 RTT 和费用。
- chunk 太小会制造大量 range 请求，太大则增加下载/解压放大。远程读取通常需要比本地 NVMe 更大的 chunk，但必须按查询窗口实测。
- 边录边 multipart upload 的对象在完成前通常不能像本地追加文件一样被任意 seek；若要求实时远程读取，应另设流式服务，完成后再发布最终 MCAP 对象及索引。

### 4.5 极限读取模式：让每个字节都产生结果

按查询类型选择最短路径：

| 查询 | 极限路径 | 应避免 |
|---|---|---|
| 全量回放/ETL | `FileOrder` 顺序读，当前迭代内消费 bytes | `LogTimeOrder`、逐条 seek、逐条日志 |
| 单 topic/窄时间窗 | `NoFallbackScan` + Summary/ChunkIndex/MessageIndex + `topicFilter`/时间范围 | 先全扫再在回调里过滤 |
| 只看统计/Schema | 只读 `readSummary()` | 调用 `readMessages()` |
| 只看 payload 头或大小 | 过滤后做局部解析 | 先构造完整 ROS/Protobuf/JSON 对象 |
| 重复热点查询 | 复用 Reader，缓存 Summary 和应用层解压结果 | 每个窗口重新 open、重复解压同一 chunk |

进一步压榨性能时注意：

- 顺序读取优先让文件描述符保持连续访问；`mmap`/direct I/O 只有在基准证明 page cache 或 syscall 是瓶颈时才尝试。
- 解码 CPU 成为瓶颈时，将 Reader 与解码拆成“单 Reader + 有界 bytes 队列 + 多 worker”；队列中的数据必须拥有自己的内存，不能传递短生命周期的 `MessageView` 指针。
- 并行优先按文件，其次按互不重叠的 chunk/时间分区；每个 worker 使用独立 Reader/文件句柄，并限制并发到磁盘带宽或解压 CPU 的拐点。
- 远程读取先拉 Footer/Summary，再合并相邻 chunk 的 Range 请求；把对象版本/ETag 放入缓存键，避免索引和数据错配。
- 用“实际读取字节 / 返回 payload 字节”和“扫描消息数 / 返回消息数”衡量读放大，而不是只看消息/秒。

---

## 五、C++ Writer 配置模板

### 5.1 通用实时写入

```cpp
mcap::McapWriterOptions options("my-profile");
options.chunkSize = 1 * 1024 * 1024; // 起始值，按基准调整
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
```

这套配置保留 chunk、CRC 和完整索引，适合作为第一组基准。CPU 紧张时依次对比 `Lz4`、`None` 或 `noChunkCRC=true`，每次只改一个变量。

### 5.2 极限吞吐与离线归档

极限写入可测试 `noMessageIndex=true`；仍不够时才测试 `noChunking=true`。关闭 chunk 会同时失去 chunk 压缩和高效索引访问，应在录制完成后用 `mcap compress`/`mcap recover` 离线重写。

冷归档则反过来：保留 chunk、索引和 CRC，在非实时机器上使用 `Zstd + Slow/Slowest` 和更大的 chunk，避免把高压缩开销放进采集关键路径。

### 5.3 自定义 I/O

- 写对象存储、环形介质或自定义 buffer 时实现 `mcap::IWritable`；其 `size()` 必须始终等于累计写出的字节数。
- 远程/内存映射读取可实现 `mcap::IReadable::read(output, offset, size)`，把 MCAP 的偏移读取映射到 `pread`、mmap 或 Range Read。
- 自定义 sink 的 `flush()` 仍不等同于介质持久化；耐久性边界由应用决定。

### 5.4 ROS2 仅作边界说明

若以后接入 rosbag2，`--max-cache-size` 是 MCAP 外层的写前缓存，`chunkSize` 才是 MCAP writer 参数；同时优先使用 `rosbag2_storage_mcap` 的 chunk 压缩，不要把通用 `--compression-mode file` 当成 MCAP chunk 压缩。

---

## 六、读写 Option 如何组合

读端 Option 只决定“怎么查”，不会改变文件；写端 Option 决定文件是否具备压缩、Summary 和细粒度索引，直接决定读端能走哪条路径。先记住这条依赖关系：

```text
Writer: chunk / ChunkIndex / MessageIndex / Summary
                ↓ 决定
Reader: FileOrder / LogTimeOrder / topic+time seek / NoFallbackScan
```

### 6.1 Writer 与 Reader 的影响矩阵

| 写端设置 | 写入收益 | 读端影响 | 推荐组合 |
|---|---|---|---|
| 保留 chunk + `compression=Lz4/Zstd` | 跨消息压缩，减少 I/O | 命中后需整块解压 | 实时和归档的默认起点 |
| `chunkSize` 较大 | 压缩率、顺序吞吐更好，索引更小 | 窄窗口读放大、内存和 P99 延迟上升 | 全量回放、训练数据 |
| `chunkSize` 较小 | 单次解压和随机读延迟低 | chunk/索引数量、固定开销增加 | 高频时间窗、远程 Range |
| `noMessageIndex=true` | 少写索引、略降 CPU/体积 | `LogTimeOrder`/稀疏 topic 查询受限 | 只做 `FileOrder` 扫描 |
| `noSummary=true` | 收尾 bookkeeping 略少 | `NoFallbackScan` 直接失败，需回退扫描 | 纯流式临时产物 |
| `noChunking=true` | 最少 chunk/压缩 bookkeeping | 无 chunk 压缩和高效 ChunkIndex，基本只适合顺序读 | 极限采集后离线重写 |
| `noChunkCRC=true` | 少一次校验 CPU | 降低损坏定位能力 | CPU 极紧且有外部 checksum |

### 6.2 四套可直接起测的组合

| 场景 | Writer 起点 | Reader 起点 | 关键取舍 |
|---|---|---|---|
| **均衡：实时录制 + 后续查询** | `chunkSize=1~4 MiB`；`Lz4` 或 `Zstd Fast`；保留 chunk、Summary、两级索引、CRC | 全量用 `FileOrder`；窄窗口/稀疏 topic 用 `NoFallbackScan` + `LogTimeOrder` + topic/time filter | 通常是最稳妥的生产默认值 |
| **极限采集 + 顺序离线处理** | 先 `Lz4/None`；必要时 `noMessageIndex=true`；最后才试 `noChunking=true` | `FileOrder`，不依赖 Summary；录完 `mcap compress/recover` 生成归档副本 | 写入吞吐最高，但牺牲随机读和在线查询 |
| **低延迟随机查询** | 较小 chunk（如 `256 KiB~1 MiB` 起测）；快速压缩；完整 Summary/ChunkIndex/MessageIndex/CRC | `readSummary(NoFallbackScan)`；窄 `[start,end)` + topic filter；`LogTimeOrder` | 查询延迟低，但写放大、索引体积和文件数可能增加 |
| **对象存储/远程 Range** | 中等偏大 chunk（如 `4~16 MiB` 起测）；完整索引；避免 `noSummary` | 先 Footer/Summary，再合并相邻 Range；限制并发和回退扫描 | 减少 RTT 与请求数，但单次下载/解压更大 |

### 6.3 “最好组合”的判断顺序

1. 先定义主查询：全量顺序、窄时间窗、稀疏 topic、还是远程 Range；不要用一套参数服务互相冲突的目标。
2. 写端先保留完整能力，再只调 `compression` 和 `chunkSize`；只有确认不需要随机查询，才关闭 MessageIndex。
3. 读端把 topic/time 条件前推到 `ReadMessageOptions`，全量读取固定用 `FileOrder`；需要全局时间线时才使用 `LogTimeOrder`。
4. 生产/远程服务使用 `NoFallbackScan`，把缺索引当成文件质量问题处理；本地诊断才允许 `AllowFallbackScan` 或 `ForceScan`。
5. 以“成功写入/丢弃消息、写入 P99、查询 P99、峰值 RSS、实际读取字节和解压字节”共同验收；没有这些指标，不能称为效率最优。

一个不偏向极端场景的 C++ 起始配置是：Writer 保留 chunk、Summary、ChunkIndex、MessageIndex 和 CRC，使用 `Lz4` 或 `Zstd Fast`；Reader 先读 Summary，按查询选择 `FileOrder` 或 `LogTimeOrder`。之后每次只改变一个 Option 做 A/B 测试。

---

## 七、基准测试方法

不要引用脱离环境的“MCAP 固定比 SQLite 快 2~4 倍”。结果取决于消息大小、topic 数、可压缩性、索引、ROS 发行版、CPU、磁盘和查询模式。

### 7.1 固定测试矩阵

至少对比：

- 压缩：`None` / `Lz4` / `Zstd Fastest` / `Zstd Default`
- chunk：默认 / 1 MiB / 4 MiB / 16 MiB
- 索引：完整 / `noMessageIndex` / `fastwrite`
- 数据：小消息高频、原始点云、JPEG/视频、混合 topic
- 读取：全量顺序、单 topic、1 秒窗口、随机 100 个窗口

### 7.2 同时记录这些指标

| 写入 | 读取 | 系统与结果 |
|------|------|------------|
| 输入/成功写入/丢弃消息数 | 冷缓存与热缓存吞吐 | CPU user/system、磁盘带宽/IOPS |
| 平均及 P95/P99 停顿 | 首条消息延迟、P95/P99 查询延迟 | 峰值 RSS、文件大小、压缩比 |
| close/轮转耗时 | 实际读取和解压字节数 | CRC/doctor 检查时间、恢复时间 |

- 先预热，重复多轮，报告中位数和长尾；不要只跑一次。
- 冷缓存与热缓存分开测，避免把 Linux page cache 当成磁盘性能。
- 数据必须可复现，并保证每组输入消息和时间戳完全一致。
- 以“零丢帧/可接受丢帧”作为硬约束，再在满足约束的方案中比较体积和查询速度。

---

## 八、场景化推荐

| 场景 | 推荐起点 |
|------|----------|
| 资源受限设备实时录制 | `Zstd Fastest` 或 `Lz4`；有界队列；独立 SSD；监控丢消息和 P99；仍不够才关闭 chunk |
| 点云/多传感器数据集 | `Zstd Fast/Default`；1~4 MiB 起测；完整索引；按时长轮转 |
| JPEG/H.264 为主 | `None` 与 `Lz4/Zstd Fastest` A/B 测试；不要默认二次压缩有效 |
| 高频时间窗/topic 查询 | 较小 chunk；完整 Summary/ChunkIndex/MessageIndex；时间戳近似有序 |
| 全量训练数据扫描 | 较大 chunk；物理顺序读；延迟解码；按文件/chunk 并行；多次分析则转 Parquet/Arrow |
| 冷归档 | 采集端快速写，离线转 `zstd_small`；保留 CRC；额外保存 SHA-256/checksum |
| S3/OSS 按需读取 | 完整索引；Range Read；缓存 Summary；合并邻近请求；按 RTT 调 chunk |

---

## 九、最终 Checklist

- [ ] 先用 CPU、磁盘、队列积压和丢消息确认瓶颈
- [ ] 区分应用写队列、MCAP chunk、外层整文件压缩
- [ ] 实时场景先试 `Zstd Fastest/Fast`、`Lz4`、`None`，以实测决定
- [ ] chunk 同时按吞吐、P99、内存和随机读放大调优
- [ ] 默认保留 Summary、ChunkIndex、MessageIndex 和 Chunk CRC
- [ ] 仅极限采集关闭 chunk/message index，完成后离线转换为归档格式
- [ ] schema/channel 由应用显式去重并复用 ID
- [ ] 控制时间戳乱序，避免 chunk 时间范围膨胀
- [ ] 读取时把 topic/时间过滤传给 Reader，并在过滤后再解码
- [ ] C++ 全量读取使用 `FileOrder`，只有需要时才做时间排序
- [ ] 并行读取使用独立 Reader/文件句柄，并处理全局排序
- [ ] 远程读取缓存 Summary，使用并合并 Range Read
- [ ] 同时测丢帧、P99、RSS、CPU、I/O、文件大小和查询延迟
- [ ] CRC 用于损坏检测，归档另存密码学 checksum

详见：[MCAP 写入优化](MCAP%20写入优化.md) / [MCAP 读取优化](MCAP%20读取优化.md) / [MCAP 读写与API](MCAP%20读写与API.md) / [MCAP 简介](MCAP%20简介.md) / [MCAP 最佳实践](MCAP%20最佳实践.md)
