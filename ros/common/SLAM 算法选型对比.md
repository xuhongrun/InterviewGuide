# SLAM 算法选型与对比

> 视觉 / LiDAR / 多传感器融合 SLAM 算法横向对比与工程选型。

---

## 1. SLAM 分类

```
            ┌─────────────────┐
SLAM ───────┤ 按传感器        ├── 视觉（单目/双目/RGB-D）
            │                 ├── LiDAR（2D / 3D）
            │                 ├── 视觉惯性 VIO / VI-SLAM
            │                 └── LiDAR-惯性 LIO / LIO-SAM
            │
            ├ 按方法 ────────── 滤波（EKF / 粒子滤波）
            │                 ├ 优化（图优化 / Bundle Adjustment）
            │                 └ 学习型（NeRF-SLAM / DeepSLAM）
            │
            └ 按目标 ────────── 稀疏（特征点） / 半稠密 / 稠密
```

---

## 2. 主流算法对比表

### 2.1 视觉 SLAM

| 算法 | 类型 | 传感器 | 后端 | 闭环 | 特色 | 工程成熟度 |
|------|------|--------|------|------|------|-----------|
| **ORB-SLAM3** | 特征点稀疏 | 单 / 双 / RGB-D + IMU | BA + Pose Graph | ✅DBoW2 | 多地图 Atlas、IMU 紧耦合 | ⭐⭐⭐⭐⭐ |
| **VINS-Fusion** | 半直接 + IMU | 双 / 单目 + IMU | 滑窗 BA | ✅ | 港科大，VIO 经典 | ⭐⭐⭐⭐⭐ |
| **OKVIS** | 关键帧 + IMU | 双目 + IMU | 滑窗 | ❌ | 早期 VIO 经典 | ⭐⭐⭐ |
| **DSO** | 直接法稀疏 | 单目 | 光度 BA | ❌ | 不靠特征，光度残差 | ⭐⭐⭐⭐ |
| **LSD-SLAM** | 半稠密直接 | 单目 | Pose Graph | ✅ | 半稠密深度图 | ⭐⭐⭐ |
| **SVO 2.0** | 半直接 | 单 / 双 / RGB-D | 稀疏 | ❌ | 极快，无人机常用 | ⭐⭐⭐⭐ |
| **RTAB-Map** | RGB-D / 双目 | RGB-D / 双目 + LiDAR | Pose Graph | ✅ | ROS 集成度高、稠密重建 | ⭐⭐⭐⭐⭐ |
| **Maplab / OpenVINS** | VIO + 多会话 | 多目 + IMU | 滑窗 / 滤波 | ✅ | 工业级长航时 | ⭐⭐⭐⭐ |
| **NeRF-SLAM / iMAP / NICE-SLAM** | 学习型 | RGB-D | NeRF 优化 | 部分 | 神经场景表征，研究热点 | ⭐⭐ |

### 2.2 LiDAR / LiDAR-IMU SLAM

| 算法 | 类型 | 传感器 | 特色 | 工程成熟度 |
|------|------|--------|------|-----------|
| **LOAM**（2014） | 特征 + 扫描配准 | 3D LiDAR | 边缘点+平面点；扫到扫匹配；车辆SLAM鼻祖 | ⭐⭐⭐⭐ |
| **A-LOAM** | LOAM 简洁实现 | 3D LiDAR | 学习易上手 | ⭐⭐⭐ |
| **LeGO-LOAM** | LOAM + 地面分割 | 3D LiDAR | 地面机器人 | ⭐⭐⭐⭐ |
| **LIO-SAM** | LiDAR-IMU 紧耦合 + GPS | 3D LiDAR + IMU + (GPS) | 因子图，长航时无人车 | ⭐⭐⭐⭐⭐ |
| **FAST-LIO / FAST-LIO2** | iEKF + ikd-Tree | 3D LiDAR + IMU | 极快、低算力，无人机/手持 | ⭐⭐⭐⭐⭐ |
| **Faster-LIO** | 体素哈希加速 | 3D LiDAR + IMU | 工业部署友好 | ⭐⭐⭐⭐ |
| **LIO-Livox** | Livox 非旋转扫描 | Livox + IMU | 适配 Livox 硬件 | ⭐⭐⭐⭐ |
| **HDL-SLAM** | NDT + GPS | 3D LiDAR + GPS | 自动驾驶建图 | ⭐⭐⭐ |
| **Cartographer** | 子图 + 分支限界回环 | 2D / 3D LiDAR | Google，2D 室内非常稳 | ⭐⭐⭐⭐⭐ |
| **Hector SLAM** | 2D 扫描匹配 | 2D LiDAR | 不需 odom，无人机室内 | ⭐⭐⭐⭐ |
| **GMapping / Karto / SLAM Toolbox** | 粒子滤波 / 图优化 | 2D LiDAR | 室内地面机器人 | ⭐⭐⭐⭐ |
| **KISS-ICP** | 纯 Point-to-Point ICP | 3D LiDAR | 极简、跨硬件、CVPR 2023 | ⭐⭐⭐⭐ |

### 2.3 多模态 / 大场景

| 算法 | 传感器 | 特色 |
|------|--------|------|
| **R²LIVE / R³LIVE** | LiDAR + Camera + IMU | 紧耦合、稠密彩色重建 |
| **MULLS / DLO** | 3D LiDAR | 大尺度建图 |
| **OpenVSLAM** | 多种相机 | 易扩展 fork |

---

## 3. 选型决策

### 3.1 按平台 / 场景

| 场景 | 推荐 |
|------|------|
| 无人车室外建图 | **LIO-SAM / FAST-LIO2 / HDL-SLAM**（含 GPS 融合） |
| 无人机室外 / 高速 | **VINS-Fusion / FAST-LIO2 / SVO 2** |
| 无人机室内（无 GPS） | **VINS-Fusion / OpenVINS / Hector** |
| 移动机器人 2D 室内导航 | **Cartographer / SLAM Toolbox / GMapping** |
| 移动机器人 3D 室内 | **RTAB-Map / FAST-LIO2** |
| AR / VR 头显 | **ORB-SLAM3 / OpenVINS** |
| 手持扫描 / 测绘 | **FAST-LIO2 / LIO-SAM** |
| 长航时 / 多会话 | **Maplab / RTAB-Map / ORB-SLAM3 Atlas** |
| 极低算力（嵌入式） | **FAST-LIO2 / SVO** |

### 3.2 按硬件资源

```
高算力（GPU+大CPU）：ORB-SLAM3 / RTAB-Map 稠密 / NeRF-SLAM
中算力（i5/Jetson）：VINS-Fusion / LIO-SAM / FAST-LIO2
低算力（树莓派/MCU）：SVO / Cartographer 2D / FAST-LIO2 减分辨率
```

### 3.3 关键问题对照

| 需求 | 选择标准 |
|------|---------|
| 实时性极高（>30Hz）| FAST-LIO2 / SVO / Hector |
| 闭环必需 | ORB-SLAM3 / RTAB-Map / Cartographer / LIO-SAM |
| 稠密地图 | RTAB-Map / R³LIVE / NeRF-SLAM |
| 长航时无漂移 | LIO-SAM + GPS / Maplab |
| 弱纹理环境 | LiDAR > Vision；DSO 比 ORB 在弱纹理略好 |
| 强光 / 暗光 | LiDAR > Vision；事件相机 / 红外 |
| 动态环境 | DynaSLAM / ORB-SLAM3 + 语义剔除 |

---

## 4. 核心模块解剖

### 4.1 前端

| 方法 | 代表 | 特点 |
|------|------|------|
| 特征点 | ORB-SLAM、VINS | 鲁棒、慢；纹理依赖 |
| 直接法 | DSO、LSD | 全像素光度、无纹理依赖、对光照敏感 |
| 半直接 | SVO | 折中，速度极快 |
| 扫描匹配 | LOAM、KISS-ICP | LiDAR 标配 |
| 滤波（IMU 预积分） | VINS、FAST-LIO | 时序约束 |

### 4.2 后端

| 方法 | 库 | 特点 |
|------|----|------|
| EKF | 自实现 | 实时强、易发散 |
| iEKF | FAST-LIO | 收敛快 |
| 图优化 | g2o / Ceres / GTSAM | 主流，离线/在线均可 |
| 因子图 | GTSAM iSAM2 | 增量优化，LIO-SAM 用 |
| Bundle Adjustment | g2o / Ceres | 视觉黄金标准 |

### 4.3 闭环检测

* **DBoW2 / DBoW3**：词袋，ORB-SLAM 系。
* **NetVLAD / SuperPoint+SuperGlue**：深度学习。
* **Scan Context / Scan Context++**：LiDAR 全局描述子，LIO-SAM 用。

### 4.4 地图表示

| 表示 | 用途 |
|------|------|
| 稀疏特征点 | 定位 |
| 占据栅格 OccupancyGrid | 2D 导航 |
| OctoMap | 3D 体素地图 |
| TSDF / NDT | 稠密 / 配准 |
| Mesh / Surfel | 视觉重建 |
| NeRF / 3D Gaussian | 学习型，研究前沿 |

---

## 5. 常用数据集与评测

| 数据集 | 平台 | 用途 |
|--------|------|------|
| **EuRoC MAV** | 无人机 + 双目 + IMU | VIO 黄金 |
| **TUM RGB-D / VI** | 室内 RGB-D / VI | 视觉 SLAM |
| **KITTI / KITTI-360** | 自动驾驶 双目 + LiDAR | 车辆 SLAM |
| **NCLT / Newer College** | 长航时 LiDAR | 大场景 |
| **Hilti SLAM Challenge** | LiDAR + IMU 极端环境 | 工业级评测 |
| **OpenLORIS / VIODE** | 室内动态 | 鲁棒性 |

**指标**：APE / RPE（绝对 / 相对位姿误差），用 `evo` 工具评测。

```bash
evo_ape tum gt.txt est.txt -a -p
evo_rpe tum gt.txt est.txt -a --delta 1 -p
```

---

## 6. 工程化要点

1. **时间同步**：传感器硬同步（PTP / GNSS PPS）远胜软同步；时间偏差 1ms 在 100 km/h 上 ≈ 2.8 cm。
2. **外参标定**：相机-IMU（Kalibr）、相机-LiDAR（lidar_camera_calibration）、车体-传感器（手眼标定）。
3. **噪声参数**：IMU Allan 方差测；LiDAR 测角度噪声、相机重投影协方差。
4. **初始化**：VIO 静止 / 匀速激励初始化；LIO 静止初始化重力。
5. **退化场景**：长直走廊（LiDAR 退化）、纯旋转 / 纯平移（视觉退化）；多模态融合是出路。
6. **回环误检**：用语义 / 几何验证（PnP RANSAC inliers 阈值）。
7. **大尺度地图**：地图分块 + 边读边删；磁盘缓存。
8. **多机协同**：CCM-SLAM / Kimera-Multi。
9. **重定位**：Bag-of-Words + ICP 二次精细对齐。
10. **生产部署**：CPU 占用、内存峰值、丢帧、IMU buffer 溢出告警。

---

## 7. 常见问题排查

| 现象 | 怀疑 | 排查 |
|------|------|------|
| 漂移大 | IMU 偏置 / 外参 / 时间不同步 | Allan 方差 / Kalibr 重标 |
| 抖动 | 优化窗口太小 / 传感器噪声 | 调权重 / 降频 |
| 闭环失败 | DBoW 词汇与场景不符 | 重训词汇 / 换 Scan Context |
| 跟踪丢失 | 弱纹理 / 快速运动 / 曝光突变 | 提高曝光控制 / 加 IMU |
| 地图发散 | 退化场景未识别 | 加约束（GPS / 平面 / Wheel） |
| CPU 高 | 体素分辨率 / 关键帧密度 | 调粗 |
| 内存涨 | 关键帧 / 子图无上限 | 滑窗 / 边缘化 |

---

## 8. Top 15 SLAM 工程 Checklist

1. ☐ 时间同步走硬件触发（PTP / PPS / Trigger）。
2. ☐ 外参标定有版本号 + 入仓库；定期复检。
3. ☐ IMU 出厂噪声 + 自测 Allan 方差。
4. ☐ 选型在目标场景实测，不迷信 paper 数字。
5. ☐ 算法配 ROS 包 + 可重入；崩溃自动重启 + 重定位。
6. ☐ 状态可观测：发布位姿 / 协方差 / 退化标志。
7. ☐ Bag 全量录制 + 离线复现是调参主战场。
8. ☐ 评测 evo APE/RPE，跑回归。
9. ☐ 闭环检测有阈值 + 二次几何校验，防误检。
10. ☐ 退化检测：协方差膨胀 / 残差突增告警。
11. ☐ 大场景：分块地图 + LRU 缓存 + 增量保存。
12. ☐ 多传感器融合优先 LiDAR-IMU；视觉作辅助。
13. ☐ 动态物体过滤（语义分割 / 几何一致性）。
14. ☐ 关键帧 / 地图点上限 + 边缘化策略。
15. ☐ 实时监控：CPU / 内存 / 帧率 / 漂移；超阈值告警。

---

## 面试速记

1. **SLAM 三件套**：前端（数据关联）/ 后端（优化）/ 闭环（一致性）。
2. **VIO 黄金组合**：双目 + IMU + 紧耦合（VINS / OKVIS / OpenVINS）。
3. **LIO 当红炸子鸡**：FAST-LIO2（iEKF + ikd-Tree）。
4. **车辆建图首选** LIO-SAM（GTSAM 因子图 + GPS）。
5. **2D 室内** 选 Cartographer / SLAM Toolbox。
6. **闭环 DBoW2** 视觉、**Scan Context** LiDAR。
7. **图优化** 用 g2o / Ceres / GTSAM。
8. **iEKF vs EKF**：迭代逼近高斯-牛顿，收敛更稳。
9. **退化场景**：长走廊（LiDAR）、纯旋转（视觉）。
10. **时间同步 1ms = 高速 cm 级误差**。
11. **稠密重建** 选 RTAB-Map / R³LIVE。
12. **评测用 evo**，APE 看绝对漂移、RPE 看局部精度。

---

## 关联阅读

* [机器人工程 最佳实践](./机器人工程%20最佳实践.md)
* [MPC 知识图谱](../../mpc/MPC_00_知识图谱与系列总览.md)
* [Eigen 入门](../../cpp/eigen/Eigen_01_入门与基本类型.md)
