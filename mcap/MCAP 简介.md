# MCAP 简介

> **MCAP（Message Capture）** 是 Foxglove 开源的一种**容器无关（container-agnostic）、自描述、可流式（streamable）**的机器人数据记录文件格式，用于录制、回放、传输与长期存储传感器/日志等时序消息。它是 ROS2 Jazzy 起 `rosbag2` 的**默认存储后端**，也是 ROS1 `.bag` 与 ROS2 `.db3`（SQLite）的现代替代方案。

---

## 一、为什么需要 MCAP

### 1.1 历史痛点

| 格式 | 技术底座 | 主要问题 |
|------|----------|----------|
| ROS1 `.bag` | 自定义二进制 | ROS 专属、只读性差、跨语言支持弱、无官方压缩/校验、格式演进困难 |
| ROS2 `.db3`（默认） | **SQLite** | 单文件即数据库，但**写入/读取性能**一般、追加式流式写入受限、文件膨胀、跨工具依赖 SQLite |
| **MCAP** | 独立二进制规范 | 解决上述：**高性能流式 I/O、内置压缩/校验、自描述 schema、跨语言/跨框架** |

### 1.2 MCAP 的核心价值

1. **容器无关**：不绑定 ROS，可记录任意消息（Protobuf / JSON / CBOR / FlatBuffer / 自定义字节流）。
2. **自描述**：schema（消息定义）与数据同文件存储，无需外部 `.msg` 文件即可解析。
3. **可流式（streamable）**：支持顺序写入（如边录边写网络流），无需随机访问即可顺序读取；同时通过索引支持随机访问。
4. **高性能**：比 SQLite `.db3` 写入/读取更快、文件更小；支持 `zstd` / `lz4` 压缩。
5. **内置完整性**：`crc32` 校验、统计记录（Statistics）、数据段校验（DataEnd CRC）。
6. **可扩展**：`metadata`（元数据）、`attachment`（附件，如标定文件、URDF、配置文件）均可嵌入。
7. **生态成熟**：官方 C++ / Python / Go / TypeScript / Rust 库，`mcap` CLI，Foxglove Studio 直接可视化。

---

## 二、MCAP 顶层结构

MCAP 文件是一个**记录（Record）序列**，每个记录由三部分组成：

```
+--------+--------+------------------+
| opcode | length |  record payload  |
| 1 byte | 8 byte |  length 字节      |
|        |  LE    |                  |
+--------+--------+------------------+
```

- **opcode**：1 字节操作码，标识记录类型；
- **length**：8 字节小端整数，标识 payload 长度；
- **payload**：该记录的具体数据。

文件首尾各有一个 8 字节 **Magic**：`\x89MCAP0\r\n`（头部 / 尾部）。

### 2.1 记录类型（Opcodes）

| Opcode | 记录类型 | 作用 |
|--------|----------|------|
| `0x01` | **Header** | 文件头，含 `profile`（如 `ros2`）、`library` |
| `0x02` | **Footer** | 文件尾，指向 summary 段位置 + CRC |
| `0x03` | **Schema** | 消息类型定义（schema 文本，如 ROS `.msg` / `.proto`） |
| `0x04` | **Channel** | 通道：topic + schema 引用 + 编码方式 + metadata |
| `0x05` | **Message** | 一条实际消息数据（时间戳 + 序列化 payload） |
| `0x06` | **Chunk** | 批量打包的 Message 块（用于压缩与索引） |
| `0x07` | **MessageIndex** | 单 channel 的消息时间→偏移索引 |
| `0x08` | **ChunkIndex** | Chunk 的时间范围/偏移/长度索引 |
| `0x09` | **Attachment** | 附件（任意文件字节，如标定、配置文件） |
| `0x0A` | **AttachmentIndex** | 附件索引 |
| `0x0B` | **Statistics** | 汇总统计（消息数、channel 数、时间范围等） |
| `0x0C` | **Metadata** | 键值对元数据 |
| `0x0D` | **MetadataIndex** | 元数据索引 |
| `0x0E` | **SummaryOffset** | summary 段内某组记录的偏移范围 |
| `0x0F` | **DataEnd** | 数据段结束标记 + 数据段 CRC |

### 2.2 三大逻辑段

```
[Magic] [Header] [数据段: Schema/Channel + Chunk/Message ...] [DataEnd] [Summary段: 索引+统计 ...] [Footer] [Magic]
```

1. **数据段（Data Section）**：真正的消息数据（`Chunk` 包裹，或未压缩的裸 `Message`）。
2. **Summary 段（Summary Section，可选但推荐）**：`Schema`、`Channel`、`Statistics`、`ChunkIndex`、`AttachmentIndex`、`MetadataIndex`、`SummaryOffset` 等，用于**快速随机访问**。
3. **Footer**：记录 summary 段起始偏移，让读取器能快速定位索引而无需扫描全文件。

> 关键设计：**summary 段放文件尾部**，因此即使文件没写完（录制中/传输中断），数据段依然可顺序读取；写完后再补 summary 即可支持随机访问。

---

## 三、核心概念详解

### 3.1 Schema（消息定义）

```yaml
id: 1
name: "sensor_msgs/msg/PointCloud2"   # 类型名
encoding: "ros2msg"                   # 编码方式
data: "<.msg 定义文本>"                # 实际 schema 内容
```

- `encoding` 常见值：`ros2msg`、`ros1msg`、`protobuf`、`jsonschema`、`flatbuffer`、`cbor`、`cdr` 等。
- 同一 schema 可被多个 channel 复用（通过 `schema_id` 引用），避免重复存储。

### 3.2 Channel（通道）

```yaml
id: 1
schema_id: 1
topic: "/points"
message_encoding: "cdr"              # 消息体的实际编码（ROS2 通常 cdr）
metadata: { "offered_qos_profiles": "..." }   # 可选键值对
```

- **Channel ≈ Topic**：一个 topic 对应一个 channel。
- `message_encoding` 与 schema 的 `encoding` 相关但不同：schema 描述**如何理解类型**，`message_encoding` 描述**消息体的序列化方式**（ROS2 里通常是 `cdr`）。

### 3.3 Message（消息）

```yaml
channel_id: 1
sequence: 42                        # 单调递增序号（同 channel 内）
log_time: 1700000000000000000       # 记录时间（纳秒）
publish_time: 1700000000000000000   # 发布方时间戳（纳秒）
data: <序列化字节>
```

- `log_time` vs `publish_time`：前者是录制侧时钟，后者是发布节点时钟；**回放一般用 `publish_time`**。

### 3.4 Chunk（数据块）

- 将多条 `Message`（可跨 channel）**打包成一个 Chunk**，再对 Chunk 整体压缩。
- Chunk 头部记录：`message_start_time` / `message_end_time`（时间范围）、`uncompressed_size`、`uncompressed_crc`、`compression`（`zstd`/`lz4`/空）、压缩后 `records`。
- **作用**：
  1. 压缩效率高（跨消息共享冗余）；
  2. 索引粒度是 Chunk 而非单条消息，索引更小；
  3. 随机访问先定位 Chunk 再内部解压定位。

### 3.5 索引（Index）

| 索引 | 粒度 | 用途 |
|------|------|------|
| `ChunkIndex` | 每个 Chunk | 快速按时间定位到 chunk（时间范围、偏移、长度） |
| `MessageIndex` | 每条消息 | 在 chunk 内按时间定位到单条消息偏移 |
| `AttachmentIndex` / `MetadataIndex` | 每项 | 定位附件 / 元数据 |

### 3.6 Statistics（统计）

```yaml
message_count, schema_count, channel_count,
attachment_count, metadata_count, chunk_count,
message_start_time, message_end_time,
channel_message_counts: {1: 1000, 2: 500}
```

- 供 `mcap info` / 工具**秒级**汇总，无需遍历全文件。

### 3.7 Attachment 与 Metadata

- **Attachment**：嵌入任意文件（字节 + `media_type` + 名称 + crc），如标定 YAML、URDF、模型文件、实验配置。
- **Metadata**：键值对，如 `{"采集地点": "测试场A", "车辆ID": "car-07"}`。

---

## 四、压缩（Compression）

| 压缩 | 说明 | 适用 |
|------|------|------|
| 无（`none`） | 不压缩 | 需要极致随机访问速度 / CPU 受限 |
| `lz4` | 极快、压缩率一般 | 高频录制、低 CPU 开销 |
| `zstd` | 压缩率高、速度可调 | 长期存储、归档、传输 |

- MCAP 原生压缩**按 Chunk**进行；ROS2 `rosbag2` 的通用 `file/message` 压缩属于容器外的另一层，使用 MCAP 时通常优先选存储插件的 chunk 压缩以保留索引读取能力。
- 解压是**惰性**的：只解压访问到的 chunk。

---

## 五、随机访问 vs 流式访问

- **流式写入/读取**：数据顺序 append，无需 summary；适合实时录制、网络流。
- **随机读取**：读 `Footer` → 定位 `Summary` 段 → 读 `ChunkIndex`/`MessageIndex` → 按时间 seek 到 chunk → 解压 → 定位消息。

> 这一「尾部索引 + 可追加数据段」设计是 MCAP 相比 SQLite `.db3` 的核心优势之一：**既能顺序高效写，又能事后快速随机读**。

---

## 六、MCAP vs 其他格式

| 维度 | ROS1 `.bag` | ROS2 `.db3` (SQLite) | **MCAP** |
|------|-------------|----------------------|----------|
| 底座 | 自定义二进制 | SQLite | 独立二进制规范 |
| ROS 绑定 | 强绑定 | 强绑定（依赖 rosidl） | **容器无关** |
| 自描述 schema | 否 | 否 | **是（内嵌）** |
| 流式 I/O | 一般 | 受限 | **原生支持** |
| 压缩 | 无官方 | 有（但基于 SQLite 扩展） | **zstd/lz4，按 chunk** |
| 随机访问 | 慢 | 快（SQL 索引） | **快（尾部 summary）** |
| 跨语言/跨工具 | 弱 | 中 | **强** |
| 附件/元数据 | 有限 | 有限 | **原生 attachment/metadata** |
| 生态 | ROS 专用 | ROS2 专用 | Foxglove / ROS2 / 多语言 |

---

## 七、常用工具与库

### 7.1 库（SDK）

| 语言 | 包名 | 说明 |
|------|------|------|
| C++ | `mcap` | 官方参考实现（读/写/索引/压缩） |
| Python | `mcap` / `mcap-ros2-support` | 读取与写入；`mcap-ros2-support` 解析 ROS2 消息为 Python 对象 |
| Go | `github.com/foxglove/mcap/go/mcap` | 官方 Go 实现 |
| TypeScript | `@mcap/core` | 浏览器/Node 读写 |
| Rust | `mcap` | 社区实现 |

### 7.2 命令行 `mcap` CLI

```bash
mcap info demo.mcap                 # 查看统计/概要
mcap cat demo.mcap --format=ndjson  # 逐条输出 NDJSON
mcap filter in.mcap -o out.mcap -y "/points" # 过滤 topic
mcap compress in.mcap -o out.mcap   # 创建压缩副本
mcap merge a.mcap b.mcap -o out.mcap # 合并
mcap recover in.mcap -o recovered.mcap  # 修复并重建 summary/index
mcap doctor recovered.mcap              # 检查结构与 CRC
```

### 7.3 ROS2 `rosbag2`

```bash
ros2 bag record -o run --storage mcap /scan /points
ros2 bag info run
ros2 bag play run --rate 1.5 --loop
ros2 bag convert -i run.db3 -o out  # db3 → mcap
```

---

## 八、学习路线建议

1. 理解「为什么」：对比 `.bag` / `.db3` / MCAP 的设计取舍（§一、§六）。
2. 吃透「结构」：记录序列 → 数据段 / summary 段 / footer（§二）。
3. 掌握核心概念：schema / channel / message / chunk / index（§三）。
4. 弄清压缩与随机访问机制（§四、§五）。
5. 动手：用 `mcap` CLI 与 Python SDK 读写一个文件。
6. 进阶：结合 ROS2 `rosbag2`、Foxglove Studio 做端到端录制-回放-可视化。

详见：[MCAP 写入优化](MCAP%20写入优化.md) / [MCAP 读取优化](MCAP%20读取优化.md) / [MCAP 读写与API](MCAP%20读写与API.md) / [MCAP 性能优化](MCAP%20性能优化.md) / [MCAP 最佳实践](MCAP%20最佳实践.md) / [MCAP Q&A](MCAP%20Q%26A.md)
