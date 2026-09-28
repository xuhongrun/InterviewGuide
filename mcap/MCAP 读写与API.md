# MCAP 读写与 API

> 以官方 C++ SDK 为主，介绍原生 MCAP Writer/Reader、索引读取、自定义 I/O 和并发边界。Python 与 ROS2 仅作为附录。

---

## 一、读写模型

| 路径 | 写入 | 读取 |
|------|------|------|
| 顺序 | Header → Schema/Channel → Message/Chunk → DataEnd | 按文件顺序扫描，无需索引 |
| 索引 | `close()` 时追加 Summary、索引和 Footer | Footer → Summary → 按时间/topic 筛选 chunk |

数据段在前、索引段在后。Writer 不需要回头修改已写出的内容；文件缺少 Summary 或被截断时，已完整落盘的记录通常仍可恢复。

---

## 二、C++ 写入

### 2.1 完整流程

```cpp
#include <cstddef>
#include <stdexcept>
#include <string_view>
#include <vector>

#include <mcap/writer.hpp>

mcap::McapWriterOptions options("my-profile");
options.chunkSize = 1024 * 1024;
options.compression = mcap::Compression::Zstd;
options.compressionLevel = mcap::CompressionLevel::Fast;
options.noChunkCRC = false;
options.noChunking = false;
options.noMessageIndex = false;
options.noSummary = false;

mcap::McapWriter writer;
auto status = writer.open("out.mcap", options);
if (!status.ok()) {
  throw std::runtime_error(status.message);
}

// schemaData 可以是 std::string_view 或 mcap::ByteArray。
std::string_view schemaData = "...";
mcap::Schema schema("telemetry.Sample", "protobuf", schemaData);
writer.addSchema(schema); // writer 回填 schema.id

mcap::Channel channel("/telemetry", "protobuf", schema.id);
writer.addChannel(channel); // writer 回填 channel.id

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

writer.close(); // 刷新最后一个 chunk，写 Summary/Footer
```

`message.data` 是指针，至少要在 `writer.write(message)` 返回前有效。不要把临时容器的悬空指针交给 Writer。

### 2.2 Schema 与 Channel 复用

- 每种 schema 注册一次，缓存 `schema.id`。
- 每个逻辑 channel 注册一次，缓存 `channel.id`。
- 多个 channel 可以复用一个 `schema.id`。
- C++ 低层 Writer 不按内容自动去重；重复调用 `addSchema`/`addChannel` 会创建新 ID。
- 复用 Writer 写多个文件时，官方 C++ 实现会保留已注册的 schema/channel，可在首次打开前统一注册；应用仍应明确管理其生命周期和映射关系。

### 2.3 关键 WriterOptions

| 选项 | 含义 | 常规建议 |
|------|------|----------|
| `chunkSize` | 未压缩 chunk 触发阈值 | 从默认或 1~4 MiB 起测 |
| `compression` | `None` / `Lz4` / `Zstd` | 实时先测 Lz4、Zstd Fast、None |
| `compressionLevel` | Fastest 到 Slowest | 慢级别放到离线归档 |
| `forceCompression` | 强制压缩无收益的 chunk | 通常为 `false` |
| `noChunkCRC` | 关闭 Chunk CRC | 默认保留，CPU 不足再测关闭 |
| `enableDataCRC` | 计算整个数据段 CRC | chunk 模式通常无需开启 |
| `noMessageIndex` | 不写 MessageIndex | 不按 topic/时间排序读取时可测试 |
| `noSummary` | 不写 Summary | 仅极端流式场景 |
| `noChunking` | 裸写 Message | 极限吞吐最后再考虑 |

关闭 chunk 会同时失去 chunk 压缩和有效的索引访问，不应作为默认归档配置。

### 2.4 Metadata 与 Attachment

```cpp
mcap::Metadata metadata;
metadata.name = "capture_context";
metadata.metadata = {{"device_id", "sensor-07"}, {"build", "a1b2c3"}};
writer.write(metadata);

mcap::Attachment attachment;
attachment.logTime = nowNs;
attachment.createTime = nowNs;
attachment.name = "calibration.yaml";
attachment.mediaType = "application/yaml";
attachment.data = calibrationBytes.data();
attachment.dataSize = calibrationBytes.size();
writer.write(attachment);
```

Attachment 的数据指针同样必须在 `write()` 返回前有效。

---

## 三、C++ 读取

### 3.1 全量顺序读取

```cpp
#include <mcap/reader.hpp>

mcap::McapReader reader;
auto status = reader.open("out.mcap");
if (!status.ok()) {
  throw std::runtime_error(status.message);
}

auto onProblem = [](const mcap::Status& problem) {
  // 记录、计数或中止，按业务定义处理
};

mcap::ReadMessageOptions options;
options.readOrder = mcap::ReadMessageOptions::ReadOrder::FileOrder;
for (const auto& view : reader.readMessages(onProblem, options)) {
  consume(view.channel->topic, view.message.data, view.message.dataSize);
}
reader.close();
```

`FileOrder` 不做额外时间排序，适合全量回放和 ETL。`view.message.data` 只在当前迭代有效，需要长期持有时必须复制。

### 3.2 时间与 topic 查询

```cpp
reader.readSummary(mcap::ReadSummaryMethod::NoFallbackScan);

mcap::ReadMessageOptions options;
options.startTime = startNs;
options.endTime = endNs; // 不包含 endNs
options.topicFilter = [](std::string_view topic) {
  return topic == "/telemetry";
};
options.readOrder = mcap::ReadMessageOptions::ReadOrder::LogTimeOrder;

for (const auto& view : reader.readMessages(onProblem, options)) {
  consume(view.message.data, view.message.dataSize);
}
```

- `NoFallbackScan` 在 Summary 缺失时直接报错，避免远程文件或大文件意外全扫。
- 确实允许线性回退时使用 `AllowFallbackScan`；强制重建内存索引时才用 `ForceScan`。
- MessageIndex 可帮助 topic 选择和时间顺序读取，但压缩 chunk 命中后仍需整块解压。
- 只需要文件顺序时不要使用 `LogTimeOrder`，否则会增加索引调度和内存开销。

### 3.3 Summary 与统计

```cpp
auto status = reader.readSummary(mcap::ReadSummaryMethod::NoFallbackScan);
if (status.ok()) {
  const auto& stats = reader.statistics();
  if (stats) {
    auto messageCount = stats->messageCount;
    auto start = stats->messageStartTime;
    auto end = stats->messageEndTime;
  }

  const auto& chunks = reader.chunkIndexes();
  const auto channels = reader.channels();
  const auto schemas = reader.schemas();
}
```

Summary 适合快速展示文件概况、规划并行任务和远程 Range Read，无需扫描整个数据段。

---

## 四、自定义 I/O

### 4.1 自定义写入目标

实现 `mcap::IWritable` 可写入网络流、对象上传器、内存 buffer 或专用存储：

- `handleWrite(data, size)` 顺序接收字节；
- `size()` 必须等于累计成功写出的字节数，Writer 用它生成索引偏移；
- `flush()` 由应用定义刷新语义；
- `end()` 完成或关闭目标。

MCAP 不要求 sink 支持 seek，但 `flush()` 不代表数据已经持久化到介质。断电一致性、重试和分片提交由应用层负责。

### 4.2 自定义读取源

实现 `mcap::IReadable`：

```cpp
uint64_t size() const override;
uint64_t read(std::byte** output, uint64_t offset, uint64_t size) override;
```

可以把 `read(offset, size)` 映射到 `pread`、mmap、HTTP/S3 Range Read。返回 buffer 必须至少保持有效到下一次 `read()` 调用。

远程读取应缓存 Footer/Summary，合并邻近 range，并限制并发度；否则 RTT 和请求费用可能盖过索引带来的收益。

---

## 五、并发与生命周期

- 不要假定同一个 `McapWriter`/`McapReader` 支持并发调用。
- 推荐“多个生产/序列化线程 → 有界队列 → 单 Writer 线程”。
- 队列满时必须定义阻塞、丢弃优先级或背压策略。
- 并行读取优先按文件拆分；单文件按 ChunkIndex 分区时，每个 worker 使用独立 Reader/文件句柄。
- 需要全局时间顺序时，对并行结果做归并，并处理时间范围重叠。
- `close()` 是正常文件完成的必要步骤；进程异常时，当前内存 chunk 和未持久化页可能丢失。

---

## 六、修复与检查

```bash
mcap recover damaged.mcap -o recovered.mcap
mcap doctor recovered.mcap
mcap list chunks recovered.mcap
```

`recover` 会重写有效记录并重建 Summary/index；`doctor` 检查结构和 CRC。CRC 用于意外损坏检测，归档还应单独保存 SHA-256 或对象存储 checksum。

---

## 七、Python 与 ROS2 附录

### 7.1 Python 原生 `mcap` API

Python 底层库只处理 schema/channel 元数据和原始 payload bytes，不需要 ROS。Reader 的 `iter_messages()` 支持 topic、时间范围和 `log_time_order` 参数；非 seekable 输入或只需要物理顺序时设为 `False`，避免为了全局时间排序收集过多消息。

```python
from mcap.reader import make_reader
from mcap.writer import Writer

# 原生写入：bytes 由调用方序列化
with open("out.mcap", "wb") as stream:
    writer = Writer(stream)
    writer.start(profile="protobuf", library="my-recorder")
    schema_id = writer.register_schema(
        name="example.Msg", encoding="protobuf", data=schema_bytes)
    channel_id = writer.register_channel(
        topic="/example", message_encoding="protobuf", schema_id=schema_id)
    writer.add_message(
        channel_id=channel_id, log_time=log_time_ns,
        publish_time=publish_time_ns, data=payload, sequence=sequence)
    writer.finish()  # 写入 Summary/Footer

# 原生读取：返回 (schema, channel, message)，message.data 是 bytes
with open("out.mcap", "rb") as stream:
    reader = make_reader(stream)
    for schema, channel, message in reader.iter_messages(
        topics={"/example"}, start_time=start_ns,
        end_time=end_ns, log_time_order=False):
        consume(channel.topic, message.log_time, message.data)
```

`Writer.finish()` 对应 C++ `McapWriter::close()`；进程异常退出时可能没有尾部 Summary/Footer。不同 Python 版本的可选参数可能略有差异，升级依赖时应以该版本的 `mcap.writer.Writer`/`mcap.reader` 签名为准。

### 7.2 ROS2 支持层

Python 适合快速检查和离线脚本，但高吞吐主链路优先 C++。`mcap-ros2-support` 在原生 bytes 之上提供 CDR 反序列化，把消息转换为 ROS2 Python 对象；它不是 MCAP 格式本身，也不能替代对应的 ROS2 类型支持。ROS2 不是 MCAP 的必要依赖；接入 rosbag2 时要区分其写前 cache 与 MCAP `chunkSize`，并优先使用 `rosbag2_storage_mcap` 内建 chunk 压缩。

---

## 八、速记

- 写：配置 options → `open` → `addSchema` → `addChannel` → `write` → `close`。
- 读：`open` → 可选 `readSummary` → `readMessages` → `close`。
- 全量扫描用 `FileOrder`；范围/topic 查询保留 Summary、ChunkIndex、MessageIndex。
- schema/channel 由应用显式去重。
- message/attachment 的数据指针必须满足调用期生命周期。
- 自定义 I/O 用 `IWritable`/`IReadable`，偏移和 buffer 生命周期必须严格遵守接口。

详见：[MCAP 写入优化](MCAP%20写入优化.md)（含写入流水线与持久化） / [MCAP 读取优化](MCAP%20读取优化.md)（含 `ReadMessageOptions` 详细说明） / [MCAP 性能优化](MCAP%20性能优化.md) / [MCAP 简介](MCAP%20简介.md) / [MCAP 最佳实践](MCAP%20最佳实践.md)
