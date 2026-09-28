# MCAP 最佳实践

> 面向 **MCAP 文件格式 / rosbag2 (MCAP 后端) / Foxglove 生态**，覆盖录制配置、压缩选型、索引、校验、组织规范、性能优化与长期归档。

---

## 1. 格式与后端选型

* **新项目一律默认 MCAP**（ROS2 Jazzy 起已是 `rosbag2` 默认后端），不再使用 `.db3`。
* 需要 **跨团队/跨工具/跨语言** 交换数据 → 必选 MCAP（自描述 + 容器无关）。
* 仅当需要 **SQL 直接查询** 消息时才保留 SQLite `.db3`；否则用 `mcap` CLI / 脚本解析更高效。
* ROS1 存量 `.bag` → 用 `rosbags` / `rosbags-convert` 迁移为 MCAP，统一归档格式。

```bash
ros2 bag record -o run --storage mcap /scan /points
```

---

## 2. 压缩（Compression）选型

| 场景 | 推荐 | 理由 |
|------|------|------|
| 高频录制、CPU 敏感（实时车上） | `lz4` 或 `none` | 压缩开销小，避免丢帧 |
| 长期归档、云存储、传输 | `zstd`（级别 1~3） | 压缩率高，节省空间与带宽 |
| 需要低延迟随机访问 | 较小的 `none`/快速压缩 chunk | 压缩 chunk 命中后仍需整块解压 |
| 常规离线数据集 | `zstd` chunk 级 | 压缩率与速度平衡 |

* MCAP 原生压缩以 **chunk** 为单位；rosbag2 的通用 `file/message` 压缩是容器外的另一层机制，不要混为一谈。
* 图像/点云等已压缩数据（JPEG/PNG、压缩点云）**重复压缩收益低**，可考虑 `none` 避免浪费 CPU。

```bash
# 使用 rosbag2_storage_mcap 内建 preset 做 chunk 压缩
ros2 bag record -s mcap -o run --storage-preset-profile zstd_fast /points

# 不压缩
ros2 bag record -o run --compression-mode none /points
```

---

## 3. Chunk 与索引

* 默认 chunk 大小通常够用；高频大数据可分别调 rosbag2 `--max-cache-size` 与 MCAP `chunkSize`：前者是写前缓存，后者是未压缩 chunk 阈值，不能混为同一参数。
* **低延迟随机访问**可减小 chunk，降低单次解压数据量。
* 录制完成后应保留 summary 段（默认写入 footer+summary）；若 summary 缺失或文件被截断，用 `mcap recover` 重写并重建：

```bash
mcap recover in.mcap -o recovered.mcap
```

---

## 4. 自描述 Schema 与编码

* **保留 schema 信息**：MCAP 内嵌 schema，跨工具可读；不要依赖外部 `.msg`/`.proto` 才能解析。
* 使用标准 `profile`（如 `ros2`、`protobuf`），便于 Foxglove Studio 等工具自动识别并可视化。
* **ROS2 可视化**：优先使用 Foxglove 约定的 well-known schema（如 `foxglove.PointCloud`、`foxglove.FrameTransform`），或直接录制原生 `sensor_msgs/*`（Foxglove 已内置转换）。

```bash
# 用 mcap CLI 查看 schema 是否完整
mcap info demo.mcap          # 输出 schema_count / channel_count
mcap cat demo.mcap --format=ndjson | head
```

---

## 5. 元数据与附件（Metadata / Attachment）

* 把**采集上下文**写入 `metadata`：车辆 ID、场景、软件版本、操作者、日期——便于检索与追溯。

```bash
mcap add metadata demo.mcap --key vehicle_id --value car-07
```

* 用 **attachment** 携带标定文件、URDF、参数 YAML、实验配置，保证数据**可复现**：

```bash
mcap add attachment demo.mcap calibration.yaml --name calib --media-type application/yaml
```

---

## 6. 命名与组织规范

* 文件名包含**场景 + 时间戳 + 车辆/设备 ID**：`highway_20260826_car07.mcap`。
* 一个 bag **聚焦单一场景/任务**，避免混录导致检索困难；需要合并用 `mcap merge`。
* 大文件按 **topic 分组过滤**存储（`mcap filter`），便于按需加载：

```bash
mcap filter full.mcap -o points_only.mcap -y "/points"
```

---

## 7. 完整性校验（CRC）

* 依赖 MCAP 内置 `crc32`（Chunk CRC、DataEnd CRC、Footer summary CRC）检测损坏。
* 归档/传输后**校验**：用 `mcap doctor` 检查文件结构和 CRC，并核对单独保存的 checksum。
* 传输到 S3/OSS 后核对对象 `ETag`/checksum，防止分片上传损坏。

---

## 8. 性能优化清单

| 维度 | 建议 |
|------|------|
| 写入 | 顺序 append；有界写前队列；chunk 按吞吐、P99、内存共同调优 |
| 压缩 | 高频用 `lz4`；归档用 `zstd` |
| 读取 | 利用 summary + chunk index 按时间 seek，勿全量遍历 |
| 内存 | 流式读取（`mcap` Reader 支持迭代），避免一次性加载整个文件 |
| 网络 | MCAP 支持流式传输，边录边传，配合对象存储分段上传 |
| 磁盘 | 采用 append-only 文件系统友好；避免碎片化小文件 |

---

## 9. ROS2 集成要点

* **Jazzy 起默认 MCAP**；`ros2 bag record --storage mcap` 显式指定更稳妥。
* 回放时**业务节点加 `--ros-args -p use_sim_time:=true`** 使用 bag 时间戳。

```bash
ros2 bag play run --clock 100    # 同时发布 /clock，供 use_sim_time
ros2 bag play run --rate 2.0 --loop
ros2 bag play run --topics /scan   # 仅回放指定 topic
```

* 录制跨 ROS2 / 原生非 ROS 数据可统一进 MCAP（容器无关）。

---

## 10. Foxglove 生态

* **Foxglove Studio**：直接拖入 `.mcap` 可视化（图/3D/TF/表格/地图），无需转换。
* **实时连接**：`foxglove_bridge`（WebSocket）实时可视化，与 MCAP 离线复盘互补。
* 用 **well-known schema** 或原生 ROS schema，保证 Studio 自动布局面板。

---

## 11. 长期归档与数据治理

* 原始数据归档用 `zstd` MCAP；定期用 `mcap merge` / `filter` 瘦身。
* 建立 **bag 清单索引**（场景、topic、时长、大小、checksum），可存 metadata 或外部 DB。
* 敏感数据脱敏（车牌/人脸）后再共享；用 attachment 记录授权与用途。
* 对象存储启用生命周期策略（热→冷→归档）。

---

## 12. Top 20 Checklist

- [ ] 1. 新项目默认 MCAP，废弃 `.db3`（除非需 SQL 查询）
- [ ] 2. ROS1 `.bag` 统一迁移为 MCAP
- [ ] 3. 按场景选压缩：实时 `lz4`/`none`，归档 `zstd`
- [ ] 4. 图像/点云等已压缩数据避免重复压缩
- [ ] 5. chunk 大小按数据频率调优
- [ ] 6. 录制完成确保 summary/索引完整，否则用 `mcap recover` 重写
- [ ] 7. 保留内嵌 schema，使用标准 profile
- [ ] 8. 写入 metadata（车辆/场景/版本/操作者）
- [ ] 9. 用 attachment 携带标定/URDF/配置
- [ ] 10. 文件名含场景+时间戳+设备 ID
- [ ] 11. 单 bag 聚焦单场景；多场景用 filter/merge
- [ ] 12. 归档前用 `mcap doctor` 检查并核对 checksum
- [ ] 13. 传输后核对 checksum/ETag
- [ ] 14. 大文件流式读取，避免全量加载
- [ ] 15. 回放节点开启 `use_sim_time`
- [ ] 16. 用 `mcap cat --format=ndjson` 快速排查消息内容
- [ ] 17. 可视化用 Foxglove Studio + well-known schema
- [ ] 18. 实时链路用 `foxglove_bridge`，离线用 MCAP
- [ ] 19. 建立 bag 清单索引（DB/metadata）
- [ ] 20. 敏感数据脱敏后共享，记录授权

详见：[MCAP 写入优化](MCAP%20写入优化.md) / [MCAP 读取优化](MCAP%20读取优化.md) / [MCAP 读写与API](MCAP%20读写与API.md) / [MCAP 性能优化](MCAP%20性能优化.md) / [MCAP 简介](MCAP%20简介.md) / [MCAP Q&A](MCAP%20Q%26A.md)
