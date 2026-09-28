# MCAP Q&A

> MCAP（Message Capture）高频面试问题与参考答案，覆盖格式原理、设计取舍、与 rosbag2/SQLite 对比、压缩、索引、随机访问及工程实践。

---

## 1. 什么是 MCAP？它解决了什么问题？

**MCAP（Message Capture）** 是 Foxglove 开源的**容器无关、自描述、可流式**的机器人数据记录文件格式，用于录制/回放/传输/存储时序消息。

它解决的问题：

- ROS1 `.bag` 强绑定 ROS、跨语言/跨工具弱、无官方压缩与校验；
- ROS2 `.db3`（SQLite）读写性能一般、流式追加受限、依赖 SQLite；
- 需要一个**高性能、可压缩、带校验、自描述、跨生态**的统一记录格式。

核心价值：容器无关（不绑定 ROS）、自描述（schema 内嵌）、可流式（顺序 append）、内置压缩（zstd/lz4）与 crc32 校验、原生 attachment/metadata。

---

## 2. MCAP 文件由哪些部分构成？如何实现流式与随机访问并存？

**顶层是记录序列**：每条记录 = `opcode(1B) + length(8B LE) + payload`，首尾各一个 8 字节 Magic。

结构：`Magic + Header + 数据段(Schema/Channel + Chunk/Message) + DataEnd + Summary段 + Footer + Magic`。

Magic 是固定的 8 字节 `\x89MCAP0\r\n`。它只用于识别文件边界，不是版本号；不要把 `profile` 当成格式版本。

- **流式**：数据段可顺序 append，无需预先知道文件大小或建立索引即可顺序读写（适合实时录制、网络流）。
- **随机**：**summary 段放文件尾部**，`Footer` 记录其偏移；读取器读 Footer → 定位 summary → 读 `ChunkIndex`/`MessageIndex` → 按时间 seek。

> 关键点：索引放尾部，使文件「未写完也能顺序读，写完即可随机读」。

---

## 3. MCAP 有哪些核心概念？Schema 与 Channel 关系？

| 概念 | 作用 |
|------|------|
| **Schema** | 消息类型定义（`.msg`/`.proto`/JSON Schema），含 `encoding` |
| **Channel** | 通道 ≈ topic，引用 schema + 消息编码 + metadata |
| **Message** | 单条消息：channel_id + sequence + log_time/publish_time + data |
| **Chunk** | 批量打包 Message 用于压缩与索引 |
| **MessageIndex / ChunkIndex** | 时间→偏移 的索引（粒度不同） |
| **Statistics** | 汇总统计（消息数、channel 数、时间范围） |
| **Attachment / Metadata** | 附件 / 键值对元数据 |

- **Schema 与 Channel 是 1:N**：一个 schema 可被多个 channel 引用（通过 `schema_id`），避免重复存储。
- `schema.encoding` 描述**类型理解方式**（如 `ros2msg`），`channel.message_encoding` 描述**消息体序列化方式**（如 `cdr`）。

---

## 4. 为什么 MCAP 比 SQLite `.db3` 更快、更小？

1. **无 SQL 事务开销**：MCAP 是纯顺序二进制 append，绕过 SQLite 的 B-tree 索引、事务日志（WAL）、锁等开销。
2. **专用二进制布局**：变长编码、紧凑字段，避免 SQLite 的页（page）填充浪费。
3. **跨消息压缩**：Chunk 级压缩复用多条消息冗余，SQLite 的压缩往往逐页/逐值，效率低。
4. **轻量索引**：summary 段一次性加载，避免逐条 SQL 查询。

结果：写入/读取吞吐更高、文件更小、追加更友好。

---

## 5. MCAP 的压缩是如何工作的？zstd vs lz4 怎么选？

- 压缩**按 Chunk** 进行：一个 Chunk 内的多条 Message 打包后整体压缩（`zstd`/`lz4`/无）。
- `lz4`：速度极快、压缩率一般 → 高频录制、CPU 敏感场景。
- `zstd`：压缩率高、速度可调 → 长期归档、传输、云存储。
- 解压**惰性**：只解压访问到的 chunk，随机访问代价可控。
- ROS2 `rosbag2` 的通用 `file/message` 压缩是 MCAP 容器外的另一层；使用 MCAP 时通常优先用存储插件的 chunk 压缩，以保留内部索引读取能力。

---

## 6. 如何实现按时间随机访问一条消息？

1. 读文件尾 `Footer` → 获取 summary 段偏移；
2. 读 `SummaryOffset`/索引 → 加载 `ChunkIndex`（每个 chunk 的时间范围、偏移、长度）；
3. 二分/查找目标时间所在 chunk；
4. `MessageIndex` 帮助判断目标 channel 是否在该 chunk，并提供 chunk 内偏移；
5. 解压整个命中 chunk，再读取目标消息。MessageIndex 不能绕过整块解压。

这就是「尾部索引 + chunk 索引 + 消息索引」三级定位。

---

## 7. log_time 与 publish_time 有什么区别？

- `publish_time`：**发布节点**打的时间戳（业务时间）；
- `log_time`：**录制器**收到并落盘的时间（记录时间）。

回放、时间对齐、延迟分析通常用 `publish_time`；`log_time` 可用于诊断录制延迟/乱序。ROS2 bag 回放默认按 `publish_time` 发布。

---

## 8. Attachment 和 Metadata 分别用于什么？

- **Attachment**：嵌入任意文件字节（标定文件、URDF、参数 YAML、模型、实验配置），带名称、`media_type`、crc，保证数据可复现。
- **Metadata**：键值对（车辆 ID、场景、软件版本、操作者），用于检索与追溯。

二者都不参与消息数据流，属于「旁路」元信息。

---

## 9. 文件损坏了怎么办？MCAP 有哪些校验机制？

- 内置校验：Chunk 的 `uncompressed_crc`、`DataEnd` 的数据段 CRC、`Footer` 的 summary CRC（均为 crc32）。
- 数据段损坏 → 可定位到具体 chunk；summary 损坏 → 数据段仍可顺序读。
- 工具修复：`mcap recover` 从未完成/损坏文件恢复并重建 summary/index，`mcap doctor` 检查结构和 CRC。
- 归档后核对对象存储 checksum/ETag。

---

## 10. 流式写入中断（未写 Footer/summary）会丢数据吗？

不能保证完全不丢。已经完整落盘的 record/chunk 通常可以恢复；尚在 writer、rosbag2 cache 或 OS page cache 中的数据，以及末尾写到一半的 record，可能丢失。中断后可用 `mcap recover damaged.mcap -o recovered.mcap` 恢复有效记录并重建索引。

---

## 11. MCAP 与 ROS1 `.bag`、ROS2 `.db3` 的核心差异？

| 维度 | `.bag` | `.db3` | MCAP |
|------|--------|--------|------|
| 底座 | 自定义二进制 | SQLite | 独立二进制规范 |
| ROS 绑定 | 强 | 强 | 容器无关 |
| 自描述 | 否 | 否 | 是 |
| 流式 I/O | 一般 | 受限 | 原生 |
| 压缩/校验 | 无官方 | 有限 | zstd/lz4 + crc32 |
| 随机访问 | 慢 | 快 | 快 |
| 生态 | ROS | ROS2 | 多语言/跨工具 |

---

## 12. 为什么 ROS2 Jazzy 把默认存储后端从 SQLite 换成 MCAP？

- 性能：读写更快、文件更小；
- 流式：支持边录边写、网络流传输；
- 自描述与跨生态：数据可脱离 ROS 被 Foxglove Studio、Python/Go/TS 等工具直接消费；
- 统一格式：衔接 ROS1 bag 迁移与云归档。

`ros2 bag record --storage mcap` 显式指定；`ros2 bag convert` 做 db3↔mcap 转换。

---

## 13. 如何在 Python 中读取 MCAP 里的 ROS2 消息？

```python
from mcap_ros2.reader import read_ros2_messages
with open("run.mcap", "rb") as f:
    for item in read_ros2_messages(f, topics=["/points"]):
        print(item.channel.topic, item.log_time_ns, item.ros_msg)
```

- 使用 `mcap`（底层格式）+ `mcap-ros2-support`（把 CDR 反序列化为 ROS2 Python 消息对象）。
- 读取原始 bytes 不需要 ROS；但要还原成任意 ROS2 消息对象，仍需要匹配的类型支持/生成类和 CDR 解码器。内嵌 schema 解决的是类型描述随文件携带，不等于运行时自动生成反序列化器。

---

## 14. 大文件如何高效读取而不爆内存？

- 使用 Reader 逐条迭代（`make_reader` + `iter_messages`），而非一次性 `read()` 全部；non-seeking 输入要设置 `log_time_order=False`，否则 Python Reader 会收集全部消息再排序。
- 利用 summary/chunk 索引按时间范围 seek，只解压所需 chunk。
- 压缩可减小 I/O 体积；按 topic `filter` 缩小读取集。

---

## 15. 录制高频点云/图像时如何避免丢帧？

- 压缩选 `lz4` 或 `none`，降低 CPU 竞争；
- 分别调 rosbag2 写前 cache 与 MCAP `chunkSize`，用 cache 吸收抖动，并以 P99 停顿和内存约束 chunk；
- 独立磁盘/SSD、异步写、提高写缓存；
- 必要时调低录制 topic 集（`--topics`），或降低非关键话题频率。

---

## 16. MCAP 的 profile 是什么？有什么用？

`profile` 是 Header 中的字段（如 `""`、`ros1`、`ros2`、`protobuf`、`json`、`flatbuffer`、`cbor`），声明文件的**约定集合**（默认 schema、编码、well-known topic 等），帮助读取工具（尤其 Foxglove）自动识别并正确解析/可视化，无需外部类型定义。

---

## 17. 如何做 MCAP 的合并、过滤与转换？

```bash
mcap merge a.mcap b.mcap -o out.mcap       # 合并
mcap filter in.mcap -o out.mcap -y "/pts" # 仅保留 topic
mcap compress in.mcap -o out.mcap          # 创建压缩副本
ros2 bag convert -i run.db3 -o out            # db3 → mcap
rosbags-convert old.bag --dst new             # ROS1 .bag → mcap
```

---

## 18. 写入一条消息需要哪些步骤？schema 如何复用？

顺序：`start`（写 Header）→ `register_schema`（写/引用 Schema）→ `register_channel`（写 Channel，引用 schema_id）→ `add_message`（写 Message/Chunk）→ `finish`（写 DataEnd + summary + Footer）。

- **schema 复用**：多个 channel 共用同一 `schema_id`，schema 只存一次。
- **chunk 打包**：多条消息攒到 `chunk_size` 再整体压缩落盘。

---

## 19. 顺序读取和随机读取在实现上有什么区别？

- **顺序读取**：non-seeking 输入或按文件顺序逐记录迭代，适合全量重放。
- **随机读取**：seekable 输入由 Reader 自动读取 `Footer`/summary，并利用 `ChunkIndex`/`MessageIndex` 筛选 chunk。Python API 没有 `use_index` 参数。

关键：索引放尾部，使「流式顺序写」与「事后随机读」可共存。

---

## 20. 如何在高频录制下保证写入吞吐（不丢帧）？

1. 先区分 CPU 与磁盘瓶颈，对比 `Zstd Fastest`、`Lz4`、`None`；
2. rosbag2 cache 用来吸收抖动，`chunkSize` 决定 MCAP 压缩/索引粒度，两者分别调参；
3. 默认保留 chunk 和索引；只有极限场景使用 `fastwrite`，录完再离线转换；
4. chunk 应同时按吞吐、P99 停顿、内存和随机读放大调优，并非越大越好；
5. 使用有界队列、独立 SSD、单 writer 顺序写，并只录关键 topic。

---

## 21. chunk 大小如何影响压缩率与随机访问延迟？

- **大 chunk**：压缩率更高、索引更小，但随机访问需解压更大块 → seek 延迟高。
- **小 chunk**：随机访问快（解压少），但压缩率下降、索引变大。

取舍：高频顺序吞吐可从较大 chunk 起测，频繁 seek 从较小 chunk 起测；最终还要同时满足内存和 P99 停顿约束。

---

## 22. 已压缩的数据（JPEG/PNG/压缩点云）还要再压缩吗？

不建议。已压缩数据熵高，二次压缩收益低却白白消耗 CPU。录制图像/点云时选 `none` 或轻量 `lz4`，避免无谓开销。

---

## 23. 原生 C++ API 中 Writer、Reader、Schema、Channel 各负责什么？

原生 API 操作的是**序列化后的字节**，不依赖 ROS。可以把职责记成：

| API 对象 | 职责 | 是否拥有业务消息对象 |
|---|---|---|
| `McapWriter` | 按记录顺序写入文件，并在结束时生成 Summary/Footer | 否，只在调用期间读取 payload 指针 |
| `McapReader` | 解析记录、Summary、索引并产生 `MessageView` | 否，返回内部 buffer 的视图 |
| `Schema` | 描述类型定义和 schema encoding | 否 |
| `Channel` | 描述 topic、消息编码和 `schema_id` | 否 |
| `Message` | 携带时间戳、序号、channel_id 和原始 bytes | `data` 通常是借用指针 |

典型 C++ 写入顺序如下；每一步的 `Status` 都应检查：

```cpp
mcap::McapWriterOptions options("ros2");
options.chunkSize = 1 * 1024 * 1024;
options.compression = mcap::Compression::Zstd;

mcap::McapWriter writer;
if (auto s = writer.open("run.mcap", options); !s.ok()) {
  throw std::runtime_error(s.message);
}

mcap::Schema schema("example.Msg", "protobuf", schema_bytes);
if (auto s = writer.addSchema(schema); !s.ok()) {
  throw std::runtime_error(s.message);
}
mcap::Channel channel("/example", "protobuf", schema.id);
if (auto s = writer.addChannel(channel); !s.ok()) {
  throw std::runtime_error(s.message);
}

mcap::Message message;
message.channelId = channel.id;
message.sequence = sequence++;
message.logTime = log_time_ns;
message.publishTime = publish_time_ns;
message.data = payload.data();
message.dataSize = payload.size();
if (auto s = writer.write(message); !s.ok()) {
  throw std::runtime_error(s.message);
}
writer.close();
```

`Schema`/`Channel` 的 ID 由 Writer 分配，应用应缓存并复用；C++ Writer 不会按内容自动去重。`writer.close()` 会刷新最后一个 chunk 并写入 DataEnd、Summary 和 Footer，正常结束文件不可省略。

---

## 24. 原生 C++ Reader 如何做全量读取、时间范围和 topic 过滤？

使用 `mcap::ReadMessageOptions` 表达查询条件，而不是先把所有消息读出来再在业务层过滤：

```cpp
mcap::McapReader reader;
if (auto s = reader.open("run.mcap"); !s.ok()) {
  throw std::runtime_error(s.message);
}

auto onProblem = [](const mcap::Status& problem) {
  logError(problem.message);
};
if (auto s = reader.readSummary(mcap::ReadSummaryMethod::NoFallbackScan);
    !s.ok()) {
  throw std::runtime_error(s.message);
}

mcap::ReadMessageOptions options;
options.startTime = start_ns;                 // 包含
options.endTime = end_ns;                     // 不包含
options.topicFilter = [](std::string_view t) {
  return t == "/imu" || t == "/camera";
};
options.readOrder =
  mcap::ReadMessageOptions::ReadOrder::LogTimeOrder;

for (const auto& view : reader.readMessages(onProblem, options)) {
  consume(view.channel->topic, view.message.logTime,
          view.message.data, view.message.dataSize);
}
reader.close();
```

- `FileOrder` 是文件物理顺序，适合全量回放/ETL，通常吞吐最高；它不是时间顺序。
- `LogTimeOrder`/`ReverseLogTimeOrder` 依赖 Summary、ChunkIndex 和 MessageIndex，适合时间线或“查最近一条”。
- 时间区间是半开区间 `[startTime, endTime)`；相邻窗口可以无重复拼接。
- `topicFilter` 是回调，不是正则，也不保证压缩 chunk 在解压前就被排除；命中 chunk 仍需整块解压。
- 在线或远程查询优先 `NoFallbackScan`，缺少 Summary 时快速失败；本地诊断才考虑 `AllowFallbackScan`。

---

## 25. `readSummary`、索引和 `Status` 应该怎样使用？

`readSummary()` 只读取文件尾部的 Summary，不会返回消息 payload，适合快速获取统计、Schema、Channel 和索引：

```cpp
auto status = reader.readSummary(mcap::ReadSummaryMethod::NoFallbackScan);
if (!status.ok()) {
  // 缺失/损坏 summary 时按策略失败或转离线 recover
  throw std::runtime_error(status.message);
}
if (const auto* stats = reader.statistics()) {
  std::cout << stats->messageCount << '\n';
}
for (const auto& index : reader.chunkIndexes()) {
  planRange(index); // 可用于并行任务或远程 Range Read
}
```

`Status` 不是异常本身：`open`、`readSummary`、`addSchema`、`addChannel`、`write` 等返回值都要显式检查；`onProblem` 用于迭代期间报告坏 record、CRC 或解压问题。生产代码应区分“跳过单条坏消息”和“终止整个文件”两类策略，并记录文件名、查询范围和错误计数。

---

## 26. 原生 Python API 与 `mcap-ros2-support` 有什么区别？

Python 的底层 `mcap` 包读写的是原始 bytes，不需要 ROS；`mcap-ros2-support` 只负责把 ROS2 CDR bytes 反序列化成 ROS 消息对象。

```python
from mcap.reader import make_reader

with open("run.mcap", "rb") as stream:
    reader = make_reader(stream)
    for schema, channel, message in reader.iter_messages(
        topics={"/imu"},
        start_time=start_ns,
        end_time=end_ns,
        log_time_order=False,
    ):
        handle(channel.topic, message.log_time, message.data)
```

原生写入的核心生命周期是 `Writer.start()` → `register_schema()` → `register_channel()` → `add_message()` → `finish()`：

```python
from mcap.writer import Writer

with open("out.mcap", "wb") as stream:
    writer = Writer(stream)
    writer.start(profile="protobuf", library="my-recorder")
    schema_id = writer.register_schema(
        name="example.Msg", encoding="protobuf", data=schema_bytes)
    channel_id = writer.register_channel(
        topic="/example", message_encoding="protobuf", schema_id=schema_id)
    writer.add_message(
        channel_id=channel_id,
        log_time=log_time_ns,
        publish_time=publish_time_ns,
        data=payload,
        sequence=sequence,
    )
    writer.finish()
```

`finish()` 对应 C++ 的 `close()`，负责写尾部索引；异常退出时不要把未完成文件当成已封存文件。ROS2 场景再叠加 `mcap_ros2.reader.read_ros2_messages` 或对应 writer helper，不要把 ROS2 反序列化误认为 MCAP 格式能力。

---

## 27. 为什么不能把 `MessageView` 或 payload 指针直接交给异步线程？

Reader 返回的 `MessageView` 通常引用 Reader 内部的复用 buffer，迭代器前进或下一次读取后可能失效；Writer 的 `Message.data` 也只是借用调用方内存。

```cpp
// 需要跨迭代/跨线程时复制所有权
std::vector<std::byte> owned(
    view.message.data,
    view.message.data + view.message.dataSize);
queue.push(std::move(owned));
```

更高效的做法是在 Reader 线程内完成轻量解析，只把小的业务结果入队。Writer/Reader/底层 stream 默认不要并发调用；推荐“多生产者/解码线程 → 有界队列 → 单 Writer”，并明确队列满时的背压或丢弃策略。

---

## 28. 什么时候需要实现原生 `IWritable`/`IReadable`？

当目标不是普通文件（例如内存 buffer、网络流、对象存储或 mmap）时实现接口：

- `IWritable::handleWrite(data, size)` 按顺序接收 bytes，`size()` 必须等于累计成功写出的字节数；`flush()` 不等于已经持久化。
- `IReadable::size()` 返回稳定文件大小，`read(output, offset, size)` 支持按偏移读取；buffer 至少保持有效到下一次 `read()`。
- HTTP/S3 读取应先取 Footer/Summary，再按 ChunkIndex 合并 Range；对象仍在追加时要有版本/一致性协议，不能假定 Footer 已存在。

这层 API 只解决字节 I/O，不负责重试、断点提交、权限、对象版本或断电一致性，这些属于应用层。

---

## 29. 如何选择 WriterOptions，哪些开关会牺牲读取能力？

| 选项 | 影响 | 面试回答 |
|---|---|---|
| `chunkSize` | 压缩和索引粒度 | 越大压缩率/顺序吞吐通常越好，随机读放大越大 |
| `compression`/`compressionLevel` | CPU、体积、解压时间 | 实时先测 `Lz4`/`Zstd Fast`，归档再用慢级别 |
| `noMessageIndex` | 失去按 channel 的细粒度索引 | 只做 FileOrder 扫描时才考虑 |
| `noSummary` | 失去快速随机访问 | 仅用于纯流式中间产物，结束后应 recover/重写 |
| `noChunking` | 失去 chunk 压缩和高效索引访问 | 极限吞吐的最后手段，不适合归档 |
| `noChunkCRC` | 降低校验开销 | 只有 CPU 紧张且有外部 checksum 时再评估 |

不要同时改很多参数。先以“零丢帧、可接受 P99、内存上限”为硬约束，再比较文件大小和查询延迟。

---

## 30. 面试中如何解释“MCAP 自描述”并避免过度承诺？

自描述表示 Schema、Channel、编码名称和元数据可以随文件携带，读取器不必先知道 topic 表；它**不表示任何工具都能自动把任意 bytes 反序列化成业务对象**。读取仍需要对应的 decoder（例如 Protobuf descriptor、ROS2 CDR 类型支持），而 `message_encoding` 必须和实际 payload 一致。

还应说明三个边界：

1. CRC 主要检测意外损坏，不提供防篡改能力；归档要另存 SHA-256/对象 checksum。
2. Summary/索引位于文件尾，录制中或异常截断时可能不存在；顺序读取仍可能可用，但随机查询要先 recover。
3. MCAP 是采集/交换容器，不一定是复杂聚合分析的终态存储；反复扫描时可转 Parquet/Arrow 或建立外部 catalog。

---

## 31. 如何把 MCAP 写入吞吐逼近硬件上限？

先用基准确定瓶颈，再按“应用开销 → 压缩 → 索引 → 持久化”逐级优化：

1. 生产者并行序列化，使用**有界队列 + 单 Writer**；复用 payload buffer、预注册 schema/channel，避免每条消息分配和重复编码。
2. 依次对比 `Zstd Fastest`、`Lz4`、`None`。磁盘/网络受限时，快速压缩可能比不压缩更快；CPU 受限时才倾向 `None`。
3. 只做物理顺序读取才测试 `noMessageIndex`；仍不够才测试 `noChunking`。后者失去 chunk 压缩和高效索引，录完应离线重写归档文件。
4. 不要每条消息 `flush`/`fsync`，按轮转文件或时间间隔批量同步；同时监控 P99 停顿、RSS、队列积压和丢消息数。

“零拷贝”不能被绝对化：应用可以避免额外的业务层复制，但 Writer 通常仍需把 payload 放进 record/chunk buffer。最终选择必须以端到端吞吐和可靠性约束为准，而不是单看 `write()` 调用速度。

---

## 32. 如何把 MCAP 读取延迟和读放大做到最低？

- 全量回放或 ETL 使用 `FileOrder` 顺序读，不要为不需要的全局排序加载 MessageIndex。
- 单 topic/窄时间窗查询使用 `NoFallbackScan`、Summary、ChunkIndex、MessageIndex 和 `topicFilter`；时间区间采用 `[startTime, endTime)`。
- 过滤后再反序列化；只看时间戳、长度或 payload 头时不要构造完整 ROS/Protobuf/JSON 对象。
- 复用同一个 Reader 和已解析的 Summary；对重叠窗口在应用层缓存热点 chunk 或合并查询，避免重复解压。
- 解码 CPU 成为瓶颈时采用“单 Reader + 有界 bytes 队列 + 多 worker”；跨线程不能直接传递短生命周期 `MessageView` 指针。
- 远程对象先 Range 读取 Footer/Summary，再合并相邻 chunk 请求；限制并发并监控实际读取字节、解压字节和返回 payload 的比例。

要注意：MessageIndex 只能缩小 chunk/消息选择，不能对 zstd/lz4 chunk 做局部解压；命中一个压缩 chunk 仍需解压整个 chunk。chunk 大小应按 P99 延迟、内存峰值和查询读放大共同调优。

---

## 33. WriterOptions 和 ReadMessageOptions 如何配合？

核心原则是：**WriterOptions 决定读端的能力上限，ReadMessageOptions 决定本次查询的成本**。写端的 chunk、Summary 和索引不是“越少越快”，而是用写入成本换读取能力。

| 目标 | WriterOptions | ReaderOptions | 适合场景 |
|---|---|---|---|
| 均衡生产 | 保留 chunk/Summary/ChunkIndex/MessageIndex/CRC；`Lz4` 或 `Zstd Fast`；`chunkSize=1~4 MiB` | 全量 `FileOrder`；范围/topic 查询 `NoFallbackScan` + filter | 默认生产配置 |
| 极限顺序写 | 快速压缩或 `None`；可测试 `noMessageIndex`，最后才 `noChunking` | `FileOrder`，不依赖索引 | 临时采集，录完离线重写 |
| 低延迟随机读 | 较小 chunk；完整索引和 Summary；快速压缩 | `[startTime,endTime)` + topic filter + `LogTimeOrder` | 交互式时间窗查询 |
| 远程对象读取 | 中等偏大 chunk；完整索引，不能 `noSummary` | 先 `readSummary(NoFallbackScan)`，合并 Range | S3/OSS/HTTP |

几个容易被问到的依赖关系：

- `noMessageIndex` 仍可 `FileOrder`，但会削弱 `LogTimeOrder` 和稀疏 topic 查询。
- `noSummary` 仍可能顺序读，但 `NoFallbackScan` 会失败；允许回退就会退化成全文件扫描。
- `noChunking` 不只是“少一次压缩”，还会失去 chunk 压缩、ChunkIndex 和较好的故障隔离。
- 大 chunk 偏向写入吞吐和压缩率，小 chunk 偏向随机读取延迟；最终以 P99、RSS 和读放大实测。

因此最稳妥的回答是：先保留完整索引能力，以 `Lz4/Zstd Fast + 中等 chunk` 起步；读端全量用 `FileOrder`，稀疏查询用 `NoFallbackScan + LogTimeOrder`，再根据真实负载逐项降级或调小/调大 chunk。

---

## 34. 面试速记

- MCAP = Foxglove 开源、容器无关、自描述、可流式、带压缩+校验的**记录格式**。
- 结构：`记录序列`（opcode+length+payload），数据段在前、**summary 段在后**。
- 核心：Schema / Channel / Message / Chunk / Index / Statistics / Attachment / Metadata。
- 压缩：`zstd`（归档）/ `lz4`（实时），按 **Chunk** 压缩，惰性解压。
- 随机访问：Footer → summary → ChunkIndex → MessageIndex → 解压定位。
- 校验：crc32（Chunk / DataEnd / Footer summary）；检查用 `mcap doctor`，修复与索引重建用 `mcap recover`。
- 对比：比 `.db3` 快/小、可流式、跨生态；Jazzy 起 rosbag2 默认。
- 工具：`mcap` CLI、Foxglove Studio、Python `mcap` + `mcap-ros2-support`。

详见：[MCAP 写入优化](MCAP%20写入优化.md) / [MCAP 读取优化](MCAP%20读取优化.md) / [MCAP 读写与API](MCAP%20读写与API.md) / [MCAP 性能优化](MCAP%20性能优化.md) / [MCAP 简介](MCAP%20简介.md) / [MCAP 最佳实践](MCAP%20最佳实践.md)
