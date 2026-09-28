# MCAP 读取优化与最佳实践

> 面向脱离 ROS2 的原生 C++ 使用场景，重点讨论顺序读、索引读、过滤、解压、反序列化、并行、远程 Range Read、内存控制和故障处理。

---

## 一、先建立正确的性能模型

一次 MCAP 查询的成本可以近似拆成：

```text
总延迟 = Footer/Summary 读取
       + 命中 chunk 的 I/O
       + 整个命中 chunk 的解压
       + record 解析
       + 目标消息反序列化
       + 排序/归并
       + 业务处理
```

读取优化的优先级通常是：

1. 少命中 chunk；
2. 少读取和解压字节；
3. 过滤后再反序列化；
4. 不需要时不要排序；
5. 最后才考虑并行和微观拷贝优化。

**MessageIndex 不能让压缩 chunk 局部解压**。MCAP 的 zstd/lz4 压缩单位是整个 chunk；命中后仍需分配其未压缩大小的 buffer，并完成整块解压。

---

## 二、按任务选择读取模式

| 任务 | 推荐模式 | 关键配置 |
|------|----------|----------|
| 全文件回放、ETL、校验 | 顺序读 | `FileOrder`，通常不必先读 Summary |
| 小时间窗口 | 索引范围读 | 先读 Summary，设置 `startTime/endTime` |
| 稀疏 topic | 索引 topic 读 | 完整 MessageIndex，通常用 `LogTimeOrder` |
| 倒序找最近消息 | 反向索引读 | `ReverseLogTimeOrder` + 小时间窗 |
| 多文件数据集 | 文件级并行 | 每个 worker 独立 Reader |
| HTTP/S3/OSS | 自定义 `IReadable` | 缓存 Summary，Range Read，合并邻近请求 |
| pipe/socket | 线性流式解析 | 不依赖 Footer/Summary，不做全局排序 |

决策原则：

```text
是否读取大部分消息？
  是 -> FileOrder 顺序读
  否 -> 是否有完整 Summary + ChunkIndex + MessageIndex？
          是 -> 时间/topic 索引读
          否 -> 线性扫描，或先 recover/重写索引
```

---

## 三、C++ 顺序读取

### 3.1 全量读取模板

```cpp
#include <mcap/reader.hpp>

mcap::McapReader reader;
auto status = reader.open("run.mcap");
if (!status.ok()) {
  throw std::runtime_error(status.message);
}

uint64_t problemCount = 0;
auto onProblem = [&problemCount](const mcap::Status& problem) {
  ++problemCount;
  logError(problem.message);
};

mcap::ReadMessageOptions options;
options.readOrder = mcap::ReadMessageOptions::ReadOrder::FileOrder;

for (const auto& view : reader.readMessages(onProblem, options)) {
  consume(view.channel->topic, view.message.data, view.message.dataSize);
}

reader.close();
```

最佳实践：

- 全量读取优先 `FileOrder`，避免 MessageIndex 调度和时间排序。
- 始终提供 `onProblem`。只传时间范围的便捷重载使用空错误回调，损坏或解析问题可能不易察觉。
- 循环内先处理廉价字段，如 channel、时间戳和 `dataSize`，确认需要后再反序列化 payload。
- 不要在热路径逐条打印日志；采样记录或累计计数后批量输出。

### 3.2 FileOrder 的边界

`FileOrder` 设置时间范围后，Reader 会利用 ChunkIndex 找出所有时间相交 chunk 的最小和最大文件偏移，然后扫描这段**连续字节范围**。

这意味着：

- 时间范围可以减少头尾 I/O；
- 位于最早和最晚命中 chunk 之间的其他 chunk 仍可能被扫描；
- `topicFilter` 在消息解析阶段生效，不能保证跳过不含目标 topic 的 chunk 解压；
- chunk 时间范围严重重叠时，范围查询的收益会下降。

所以 `FileOrder + topicFilter` 适合“仍会读取较大比例数据”的场景，不是稀疏 topic 查询的最佳路径。

---

## 四、索引读取与过滤

### 4.0 `ReadMessageOptions` 详细说明

`ReadMessageOptions` 是 C++ Reader 的统一查询描述对象。它不改变文件，也不改变消息内容，只决定“哪些消息、以什么顺序、通过哪条读取路径”返回。

```cpp
struct ReadMessageOptions {
  Timestamp startTime = 0;
  Timestamp endTime = MaxTime;
  std::function<bool(std::string_view)> topicFilter;
  enum struct ReadOrder {
    FileOrder,
    LogTimeOrder,
    ReverseLogTimeOrder,
  };
  ReadOrder readOrder = ReadOrder::FileOrder;
};
```

#### `startTime`

- 消息的 `logTime >= startTime` 才会返回。
- 单位是 MCAP 的 `uint64_t` 纳秒时间戳，不是秒，也不是 `publishTime`。
- 默认值 `0`，适合 Unix epoch 或从零开始的相对时间。
- 若数据使用设备启动后的相对时间，查询端必须使用同一时间基准，不能直接拿系统 Unix 时间比较。

#### `endTime`

- 消息的 `logTime < endTime` 才会返回，**右边界是开区间** `[startTime, endTime)`。
- 默认值 `MaxTime`，表示没有上界。
- 使用半开区间可以安全拼接相邻窗口：`[t0, t1)` 与 `[t1, t2)` 不会重复，也不会漏掉恰好位于 `t1` 的消息。
- `startTime > endTime` 时配置无效，应在调用前检查；SDK 的 `validate()` 会返回 `InvalidMessageReadOptions`。

#### `topicFilter`

- 回调参数是 Channel 的 topic；返回 `true` 才返回该 channel 的消息。
- 未设置时选择所有 topic。
- 它不是正则表达式，也不是文件级过滤器。建议在外部预先构建 `unordered_set<string>`，回调中只做简单查找。
- 在 `FileOrder` 下，过滤发生在 record/chunk 解析过程中；对于压缩 chunk，不能保证在解压前排除无关 topic。
- 在 `LogTimeOrder`/`ReverseLogTimeOrder` 下，MessageIndex 可先按 channel 排除不含目标 topic 的 chunk，稀疏 topic 查询收益更明显。

#### `readOrder`

| 值 | 返回顺序 | 是否依赖 MessageIndex | 适用场景 |
|----|----------|----------------------|----------|
| `FileOrder` | 文件中实际出现的顺序 | 否 | 全量回放、顺序 ETL、校验 |
| `LogTimeOrder` | `logTime` 升序 | 是 | 多 topic 时间线、时间同步分析 |
| `ReverseLogTimeOrder` | `logTime` 降序 | 是 | 从结尾查找最近事件 |

注意：`FileOrder` 的“顺序”不是时间顺序。多传感器写入交错、线程调度或设备时钟异常时，两者可能不同。只有业务确实需要全局时间序时才选择 `LogTimeOrder`。

#### 参数组合的执行含义

```text
FileOrder + 无时间范围
  -> 从 Data section 顺序扫描，吞吐最高

FileOrder + 时间范围
  -> 有 Summary 时先缩小连续 byte range，再顺序扫描该范围

LogTimeOrder/ReverseLogTimeOrder + topic/time
  -> 读取 ChunkIndex，筛选 chunk
  -> 读取 MessageIndex，筛选 channel 和消息偏移
  -> 解压命中 chunk，按时间归并输出
```

即使设置了很窄的时间范围，也可能因为 chunk 时间范围重叠而命中多个 chunk；即使设置了 topicFilter，也仍然需要解压包含该 topic 的整个压缩 chunk。

#### 推荐的构造方式

```cpp
mcap::ReadMessageOptions options;
options.startTime = windowStartNs;
options.endTime = windowEndNs;

const std::array<std::string_view, 2> wanted{
  "/imu", "/camera/front"};
options.topicFilter = [&wanted](std::string_view topic) {
  return std::find(wanted.begin(), wanted.end(), topic) != wanted.end();
};
options.readOrder = mcap::ReadMessageOptions::ReadOrder::FileOrder;

auto status = options.validate();
if (!status.ok()) {
  throw std::invalid_argument(status.message);
}
```

高频查询中不要在 filter 内构造临时 `std::string`；可将 topic 映射为 `ChannelId` 后使用无分配查找，或捕获预先准备好的小型字符串集合。若 topic 数量固定且很少，直接比较 `topic == "/imu"` 通常最快。上例使用 `std::array<string_view>`，需要包含 `<array>` 和 `<algorithm>`。

#### `readSummary` 与 Options 的配合

- 低延迟查询建议先调用 `readSummary(NoFallbackScan)`，显式确认文件具备可用索引。
- `FileOrder` 全量扫描可以不主动读 Summary；若设置时间范围，Summary 可帮助缩小 byte range。
- `LogTimeOrder` 必须有 chunk、Summary 和 MessageIndex；缺少 MessageIndex 时会得到 `NoMessageIndexesAvailable`。
- 不要用 `AllowFallbackScan` 掩盖生产文件缺索引的问题；它会把一次查询退化为全文件扫描。

### 4.1 时间 + topic 查询模板

```cpp
mcap::McapReader reader;
auto status = reader.open("run.mcap");
if (!status.ok()) {
  throw std::runtime_error(status.message);
}

auto onProblem = [](const mcap::Status& problem) {
  logError(problem.message);
};

status = reader.readSummary(
  mcap::ReadSummaryMethod::NoFallbackScan,
  onProblem);
if (!status.ok()) {
  throw std::runtime_error(status.message);
}

mcap::ReadMessageOptions options;
options.startTime = startNs;
options.endTime = endNs; // endTime 为开区间
options.topicFilter = [](std::string_view topic) {
  return topic == "/camera" || topic == "/imu";
};
options.readOrder = mcap::ReadMessageOptions::ReadOrder::LogTimeOrder;

for (const auto& view : reader.readMessages(onProblem, options)) {
  decodeAndConsume(view);
}
```

`LogTimeOrder`/`ReverseLogTimeOrder` 使用 MessageIndex 建立读取任务：

1. 用 ChunkIndex 的时间范围排除无关 chunk；
2. 用 chunk 中存在的 channel MessageIndex 排除无关 topic；
3. 解压命中 chunk；
4. 从 MessageIndex 选择时间范围内的消息偏移；
5. 按 log time 输出消息。

若文件没有 MessageIndex，时间有序读取会返回 `NoMessageIndexesAvailable`。此时应改用 `FileOrder`，或用 `mcap recover`/`mcap compress` 重写文件。

### 4.2 三种 Summary 策略

| 策略 | 行为 | 使用建议 |
|------|------|----------|
| `NoFallbackScan` | Summary 缺失/损坏立即失败 | 大文件、远程对象、在线查询首选 |
| `AllowFallbackScan` | 失败后扫描数据段重建内存索引 | 本地工具且允许慢回退 |
| `ForceScan` | 不读尾部 Summary，强制全扫 | 诊断 Summary 与数据段不一致 |

经验上，服务端和远程读取应显式使用 `NoFallbackScan`。否则一个缺少 Summary 的对象可能把毫秒级查询退化成整文件下载和扫描。

### 4.3 过滤要尽量前推

- topic、开始时间、结束时间直接放进 `ReadMessageOptions`。
- 不要读取全部消息后才在业务回调里判断 topic。
- 只需要 metadata、schema、channel 或统计时，直接读 Summary，不要调用 `readMessages()`。
- 只需要原始 payload 时，不要构造 JSON、Protobuf 或业务对象。
- 多个相邻小查询可以合并成一个窗口，避免同一个 chunk 被重复解压。

### 4.4 高频重复查询

- 同一线程连续查询同一文件时复用已经 `open()` 的 Reader，Summary 解析结果会保留到 `close()`；不要每个窗口重新创建 Reader。
- Reader 不应跨线程并发复用。并发请求使用 Reader pool，每个实例持有独立 `IReadable`。
- `topicFilter` 应使用预先构建的 channel/topic 集合或简单比较，避免每条消息执行正则、字符串复制和动态分配。
- `channels()`、`schemas()` 返回容器副本，不要在消息热循环中反复调用；读取 Summary 后取一次并缓存。
- 对重叠或相邻窗口做请求合并，一次解压后把结果分发给多个请求。
- SDK 高层 Reader 不保证跨查询缓存解压 chunk。热点查询可在应用层缓存已解码结果；若必须缓存原始解压 chunk，需要使用更低层接口并严格管理内存上限。

---

## 五、解压、内存与对象生命周期

### 5.1 内存为什么可能超过一个 chunk

zstd/lz4 读取器会为命中 chunk 分配完整的未压缩 buffer。使用时间顺序读取时，为了归并时间交错的消息，`IndexedMessageReader` 可能同时保留多个已解压 chunk。

内存峰值近似为：

```text
活跃解压 chunk 数 × chunk 未压缩大小
+ 压缩输入 buffer
+ IReadable buffer
+ 反序列化对象
+ 应用队列和缓存
```

chunk 时间范围重叠越多，时间排序路径越可能同时保留多个 chunk。写入端保持 `logTime` 大致单调，不仅提升查询命中精度，也能降低读端归并内存。

### 5.2 MessageView 生命周期

`MessageView` 中的 `message.data` 指向 Reader 内部 buffer，通常只在当前迭代、迭代器前进前有效。

错误做法：

```cpp
std::vector<const std::byte*> pending;
for (const auto& view : reader.readMessages(onProblem, options)) {
  pending.push_back(view.message.data); // 后续可能悬空
}
```

需要跨线程或延后处理时必须复制，或在当前迭代内完成解码：

```cpp
std::vector<std::byte> owned(
  view.message.data,
  view.message.data + view.message.dataSize);
queue.push(std::move(owned));
```

复制会增加内存带宽，因此更好的结构通常是 Reader 线程当场完成轻量解码，再把尺寸更小的业务结果送入后续队列。

### 5.3 控制反序列化成本

- 每个 channel 缓存对应 decoder，避免逐条查 schema、构建 descriptor。
- Protobuf 等反复创建对象的场景可测试对象复用/arena，但必须正确清理上一条消息状态。
- 只访问固定头字段时，考虑在安全前提下做局部解析，避免完整对象树构造。
- 批量输出结果，减少逐消息分配、锁、日志和系统调用。
- 反序列化比 I/O 更重时，可以 Reader 单线程顺序取 bytes，复制到有界队列后由 worker 并行解码；必须把复制成本计入基准。

---

## 六、并行读取

### 6.1 推荐的并行层级

优先级从高到低：

1. **按文件并行**：边界清晰、几乎没有重复解压；
2. **按互不重叠时间窗并行**：每个 worker 独立 Reader；
3. **Reader 单线程 + 解码 worker**：适合反序列化 CPU 瓶颈；
4. 自己按 ChunkIndex/底层 record 做分区：控制力强，但实现和排序复杂。

不要让多个线程共享同一个 `McapReader` 或同一个会改变内部位置的 `IReadable`。每个 worker 使用独立 Reader、文件描述符和解压上下文。

### 6.2 时间窗并行的代价

把时间轴切成互不重叠的 `[start, end)` 可以避免消息重复，但跨越边界的 chunk 会被相邻 worker 重复读取和解压。chunk 越大、时间范围重叠越严重，重复工作越多。

并行度应通过吞吐曲线选择：

- SATA SSD 往往很快达到 I/O 上限；
- NVMe 可支持更高并发，但解压 CPU 可能先饱和；
- HDD 随机 seek 多时并发通常适得其反；
- 对象存储还受 RTT、请求配额、带宽和费用限制。

### 6.3 保持输出顺序

如果下游要求全局 log time 顺序：

- 单文件直接使用 `LogTimeOrder` 最简单；
- 多文件/多 worker 用小顶堆做 k-way merge；
- 每个输入流只保留一条候选消息，避免把所有结果一次性排序；
- 时间戳相同时定义稳定的次级键，例如文件 ID、channel ID、sequence。

---

## 七、本地与远程 I/O

### 7.1 本地文件

- 全量扫描保持顺序访问，不要对每条消息单独 seek。
- 区分冷缓存与热缓存测试，避免把 Linux page cache 当成磁盘性能。
- mmap 可以减少源文件读取时的复制和 syscall 开销，但不会消除压缩 chunk 的整块解压和输出 buffer 分配。
- 文件很多时限制同时打开的 FD 数量，并避免每个小查询反复 open/close。
- 数据盘避免与 swap、日志写入、上传任务争抢。

### 7.2 自定义 IReadable

`mcap::IReadable` 的核心接口是：

```cpp
uint64_t size() const override;
uint64_t read(std::byte** output, uint64_t offset, uint64_t size) override;
```

实现时注意：

- 返回的 buffer 必须至少有效到下一次 `read()`；
- 短读、超时和重试要有明确语义；
- `size()` 应稳定，读取尚在增长的文件需要额外一致性协议；
- 不要在一个实例上无锁并发修改复用 buffer；
- 为 Footer/Summary 和热点 chunk 设置独立缓存比盲目扩大通用缓存更有效。

### 7.3 HTTP/S3/OSS Range Read

推荐流程：

```text
HEAD/metadata 获取 size
  -> 读取尾部 Footer
  -> 读取并缓存 Summary/ChunkIndex/MessageIndex
  -> 计算命中 chunk ranges
  -> 合并相邻 ranges
  -> 有界并发下载
  -> 解压、过滤、解码
```

实践要点：

- 设置 range 合并阈值：多读少量字节往往比多一次 RTT 更便宜；
- 缓存 key 包含对象版本/ETag，避免文件替换后索引与数据错配；
- 缺少 Summary 时默认失败，不要静默整对象下载；
- 重试必须校验返回的 offset/length；
- multipart ETag 不一定是文件 MD5，完整性另用对象 checksum 或 SHA-256。

---

## 八、文件布局对读取的影响

读性能的一半由写入时决定：

| 写入决策 | 对读取的影响 |
|----------|--------------|
| 大 chunk | 顺序吞吐/压缩率通常更好，随机读放大和内存更高 |
| 小 chunk | 时间窗延迟更低，索引和 I/O 固定开销更高 |
| 无 MessageIndex | `FileOrder` 可读，时间排序和稀疏 topic 查询受限 |
| 无 Summary/ChunkIndex | 需要线性扫描，远程查询代价很高 |
| logTime 严重乱序 | chunk 时间范围重叠，命中和归并成本上升 |
| 混合冷热 topic | 查询冷门 topic 时容易解压含大量无关消息的 chunk |
| 适度文件轮转 | 并行、恢复、上传更容易；过小则增加元数据开销 |

若一种文件同时服务“高速全量训练”和“低延迟单 topic 查询”，单一 chunk 配置可能无法兼顾。实际项目可以保留原始 MCAP，再生成面向查询的过滤副本或分析格式。

---

## 九、故障、CRC 与可观测性

### 9.1 错误处理

- 所有 `open()`、`readSummary()` 返回的 `Status` 都要检查。
- `onProblem` 至少记录 status、文件、查询范围和当前计数。
- 区分可跳过的坏消息与必须终止的结构/解压错误。
- 线上服务设置最大 record/chunk/响应尺寸，防止损坏文件触发超大分配。
- 对缺少 Summary 的文件先离线 `recover`，不要让每个查询重复扫描。

### 9.2 CRC 的现实边界

不要因为文件包含 CRC 字段，就假定当前高层读取路径已经完成所有 CRC 验证。归档或导入阶段应显式运行：

```bash
mcap doctor run.mcap
```

CRC 检测意外损坏，不防恶意篡改。长期归档另存密码学 checksum，并把 checksum 与文件版本绑定。

### 9.3 读取指标

至少监控：

| 类别 | 指标 |
|------|------|
| 查询 | 首条消息延迟、总延迟、P50/P95/P99 |
| I/O | 实际读取字节、range 请求数、cache hit rate |
| 解压 | 命中 chunk 数、压缩/未压缩字节、解压时间 |
| 过滤 | 扫描消息数、返回消息数、读放大比 |
| 资源 | CPU、峰值 RSS、磁盘带宽、并发队列深度 |
| 健壮性 | problem 数、损坏 chunk、回退扫描次数 |

建议定义：

```text
字节读放大 = 实际读取字节 / 返回 payload 字节
消息读放大 = 扫描消息数 / 返回消息数
```

只看“消息/秒”容易掩盖稀疏查询读放大和 P99 延迟。

---

## 十、常见反模式

- 为读取一个 topic 使用 `FileOrder` 扫完整文件，却以为 `topicFilter` 会避免 chunk 解压。
- 每个小时间窗重新打开文件、读取 Summary、解压同一个 chunk。
- 全量读取使用 `LogTimeOrder`，为不需要的排序付出索引和内存成本。
- 把 `MessageView::data` 指针放进异步队列，迭代器前进后继续使用。
- 多线程共享同一个 Reader/stream，通过锁把随机 seek 串行化。
- 盲目增加读取线程，忽略磁盘、解压 CPU 或对象存储限流已经饱和。
- 在过滤前完成 Protobuf/JSON/业务对象反序列化。
- 远程 Summary 缺失时自动整文件扫描，没有传输上限和告警。
- 反复用 MCAP 做复杂聚合分析，却不建立外部目录或转换为列式格式。

---

## 十一、场景化经验

### 高频全量回放

- `FileOrder`；
- 较大 chunk；
- Reader 线程只做必要解析；
- 解码 CPU 重时使用有界 worker 队列；
- 不逐条日志，不保留 `MessageView` 指针。

### 低延迟时间窗查询

- 保留 Summary、ChunkIndex、MessageIndex；
- 较小 chunk；
- `NoFallbackScan`；
- 合并相邻窗口并缓存热点结果；
- 监控字节读放大和首条消息延迟。

### 稀疏 topic 查询

- 使用带 MessageIndex 的 `LogTimeOrder`；
- topicFilter 前推到 `ReadMessageOptions`；
- 写入阶段避免稀疏 topic 长期与超大高频 payload 共处大 chunk；
- 查询非常频繁时生成 topic 过滤副本或外部索引。

### 大规模离线数据集

- 文件级并行优先；
- 预读 Summary 建立外部 catalog；
- 按文件大小/未压缩字节均衡任务，不只按文件数；
- 多次分析时一次转换为 Parquet/Arrow 等面向分析格式。

### 对象存储

- 缓存对象版本对应的 Summary；
- Range Read 合并与有界并发；
- 禁止无上限 fallback scan；
- 把请求数、下载字节和解压字节都纳入成本指标。

---

## 十二、最终 Checklist

- [ ] 全量读取使用 `FileOrder`
- [ ] 稀疏 topic/时间排序查询保留并使用 MessageIndex
- [ ] 明确 `endTime` 是开区间
- [ ] 线上和远程查询使用 `NoFallbackScan`
- [ ] 始终提供 `onProblem` 并检查所有 `Status`
- [ ] 在反序列化前完成 topic/时间过滤
- [ ] 不跨迭代保存 `MessageView::data` 裸指针
- [ ] 评估时间顺序读取同时驻留多个解压 chunk 的内存
- [ ] 每个并行 worker 使用独立 Reader/IReadable
- [ ] 优先按文件并行，再考虑时间窗或解码并行
- [ ] 合并相邻查询和远程 ranges，避免重复解压/RTT
- [ ] 缓存 Footer/Summary 时绑定对象版本
- [ ] 同时测冷/热缓存、P99、读放大、RSS 和错误数
- [ ] 归档导入时运行 `mcap doctor` 并核对 checksum
- [ ] 重复复杂分析考虑转换到列式/数据库格式

详见：[MCAP 写入优化](MCAP%20写入优化.md) / [MCAP 读写与API](MCAP%20读写与API.md) / [MCAP 性能优化](MCAP%20性能优化.md) / [MCAP 简介](MCAP%20简介.md)
