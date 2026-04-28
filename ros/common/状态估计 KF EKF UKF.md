# 状态估计 KF EKF UKF 与因子图

> 机器人 / 自动驾驶 / 控制核心：从卡尔曼滤波到现代非线性优化。

---

## 1. 为什么需要状态估计？

* 传感器有噪声、采样不同步、有缺失。
* 系统状态（位姿、速度、偏置）不可直接测量。
* 用**模型 + 量测**做最优估计：贝叶斯框架下的后验。

$$ p(x_k \mid z_{1:k}) \propto p(z_k \mid x_k) \int p(x_k \mid x_{k-1}) p(x_{k-1} \mid z_{1:k-1}) dx_{k-1} $$

---

## 2. 卡尔曼滤波 KF（线性高斯）

### 2.1 状态空间模型

$$ x_k = F_k x_{k-1} + B_k u_k + w_k, \quad w_k \sim N(0, Q_k) $$
$$ z_k = H_k x_k + v_k, \quad v_k \sim N(0, R_k) $$

### 2.2 五个公式

**预测：**

$$ \hat{x}_{k|k-1} = F_k \hat{x}_{k-1|k-1} + B_k u_k $$
$$ P_{k|k-1} = F_k P_{k-1|k-1} F_k^\top + Q_k $$

**更新：**

$$ K_k = P_{k|k-1} H_k^\top (H_k P_{k|k-1} H_k^\top + R_k)^{-1} $$
$$ \hat{x}_{k|k} = \hat{x}_{k|k-1} + K_k (z_k - H_k \hat{x}_{k|k-1}) $$
$$ P_{k|k} = (I - K_k H_k) P_{k|k-1} $$

### 2.3 直觉

* `K`（卡尔曼增益）：测量越准（R 小）→ K 越大 → 信任测量；模型越准（P 小）→ K 越小 → 信任预测。
* 是**线性高斯下的最小均方误差最优解**，等价于贝叶斯 + 高斯假设。

### 2.4 适用

* 线性系统 / 噪声高斯。
* 例：恒速运动追踪、单纯位置滤波、雷达匀速目标。

---

## 3. EKF（扩展卡尔曼）

### 3.1 思想

非线性 → 在工作点泰勒一阶展开（雅可比 F、H）。

$$ x_k = f(x_{k-1}, u_k) + w_k $$
$$ z_k = h(x_k) + v_k $$

预测协方差用 `F = ∂f/∂x` 雅可比；更新用 `H = ∂h/∂x` 雅可比。

### 3.2 优缺点

* ✅ 实时性好，工程经典（GPS-INS、机器人定位）。
* ❌ 一阶近似，**强非线性 / 大不确定** 时偏差大、易发散。
* ❌ 雅可比推导易错；难处理大转角。

### 3.3 IEKF（迭代 EKF）

更新时迭代多次（高斯-牛顿）逼近，FAST-LIO2 等用。

### 3.4 ESKF（误差状态 EKF）

* 名义状态 + 误差状态。误差量小 → 局部线性更准。
* 旋转用 SO(3) 参数化（小扰动 δθ ∈ R³），避免奇异。
* VINS / VIO / IMU 紧耦合标配。

---

## 4. UKF（无迹 / Unscented）

### 4.1 思想

不算雅可比，用 **2n+1 个 sigma 点** 经过非线性函数后重建均值协方差（无迹变换）。

* 三阶精度（EKF 一阶）；高非线性更稳。
* 计算量约 EKF 2~3×。

### 4.2 适用

* 强非线性观测 / 旋转分量大。
* 雅可比推导困难时。

---

## 5. 粒子滤波 PF

* 用大量加权粒子近似后验，无高斯假设。
* 适合多模态后验、强非线性、强非高斯（机器人全局定位 AMCL）。
* 缺点：维度灾难（高维状态 → 粒子数指数增长）；重采样退化。

**典型应用**：ROS Nav `amcl`（自适应蒙特卡洛定位）。

---

## 6. 信息滤波 IF / EIF

KF 用 `(x, P)`；IF 用 `(η, Λ) = (P⁻¹x, P⁻¹)`。
* **测量更新简单**（信息相加），适合多传感器融合。
* **预测复杂**（要求逆）。
* 稀疏信息矩阵 → 图优化 / SLAM 中常用。

---

## 7. 平滑器 Smoother

| | 滤波 Filter | 平滑 Smoother |
|---|------------|---------------|
| 用信息 | 仅过去 | 过去 + 未来 |
| 实时 | ✅ | ❌（离线 / 有延迟） |
| 精度 | 低 | 高 |

* **RTS Smoother**（Rauch-Tung-Striebel）：KF 的离线平滑。
* **iSAM2**：因子图增量平滑（GTSAM），LIO-SAM 后端。

---

## 8. 因子图 / 图优化（现代 SLAM 后端）

```
              ┌── factor (IMU pre-integration)
   x0 ── x1 ──┼── x2 ── x3 ── ...
        │     │     │
       z1    z2    z3   (观测因子)
```

* **节点**：状态变量（位姿、速度、IMU 偏置）。
* **因子**：约束（运动、观测、闭环、GPS、先验）。
* 求解：最小化 $\sum_i \|r_i(x)\|^2_{\Sigma_i^{-1}}$，本质是**最大后验** = MAP。
* 工具：g2o / Ceres / GTSAM。
* **iSAM2**：增量贝叶斯树，O(变化部分) 而非全图。

**与滤波关系**：批量 MAP 在线性高斯下等价于 KF；图优化迭代精度高，工程上现代 SLAM 几乎全用因子图。

---

## 9. 多传感器融合常见架构

### 9.1 松耦合 vs 紧耦合

| | 松耦合 | 紧耦合 |
|---|--------|--------|
| 输入 | 各模块输出位姿 | 原始传感器数据 |
| 难度 | 简单 | 复杂 |
| 精度 | 一般 | 高 |
| 鲁棒性 | 故障切换易 | 单传感器故障可能拖垮 |
| 例子 | GNSS+IMU+轮速分别 EKF | VIO（视觉特征点 + IMU 在同一优化） |

### 9.2 GNSS-IMU 组合（车辆）

* **ESKF**：名义状态 (位置、速度、姿态、IMU 偏置)；GNSS 作位置 / 速度量测。
* RTK + IMU + 轮速融合：城市峡谷下 RTK 失锁靠 IMU 短时维持。

### 9.3 VIO（视觉惯性里程计）

* 状态：位姿、速度、IMU 偏置、相机外参（可在线标定）。
* 量测：IMU 预积分（短时高频）+ 视觉特征重投影残差。
* 常用：VINS-Fusion / OpenVINS / OKVIS。

### 9.4 LIO（LiDAR-惯性）

* iEKF / 因子图。
* FAST-LIO2 = iEKF + ikd-Tree（Faster-LIO 用 voxel hash）。
* LIO-SAM = GTSAM 因子图 + GNSS 因子。

---

## 10. 工程实现细节

### 10.1 SO(3) / SE(3) 参数化

* 旋转用四元数（4 维归一化）/ 旋转向量（3 维李代数 so(3)）/ 旋转矩阵。
* 优化中扰动用切空间 δθ ∈ R³，再 retract 回流形：`R_new = Exp(δθ) * R`。
* 避免欧拉角奇异（Gimbal Lock）。

### 10.2 IMU 预积分

* 把高频 IMU 积分成两关键帧之间的相对约束（Forster 论文）。
* 显著减少优化变量数量；偏置变化可线性传播。

### 10.3 数值稳定性

* 协方差矩阵保对称：`P = (P + P.T) / 2`。
* Joseph 形式更新协方差防失正定：`P = (I-KH) P (I-KH)^T + KRK^T`。
* 大数值差用平方根滤波（SR-UKF / SRIF）。

### 10.4 调参经验

| 参数 | 调整 |
|------|------|
| Q（过程噪声）大 | 信任测量 → 跟得快但抖 |
| Q 小 | 信任模型 → 平滑但跟不上 |
| R（量测噪声）大 | 不信测量 → 平滑 |
| R 小 | 信测量 → 抖动 |

* IMU Q 用 Allan 方差直接得到 noise density。
* 视觉重投影 R 与像素噪声平方相关（典型 1~2 pixel）。

### 10.5 异常检测

* **马氏距离**判断量测是否离群：$d^2 = r^\top S^{-1} r$，超过卡方阈值则丢弃。
* GPS 跳变：连续多帧 RTK 状态 + 协方差判断。
* 光流退化：跟踪点数 / 视差判断。

---

## 11. 代码骨架

### 11.1 KF（C++ Eigen）

```cpp
struct KF {
    Eigen::VectorXd x;     // 状态
    Eigen::MatrixXd P;     // 协方差
    Eigen::MatrixXd F, Q, H, R;

    void predict() {
        x = F * x;
        P = F * P * F.transpose() + Q;
    }
    void update(const Eigen::VectorXd& z) {
        Eigen::VectorXd y = z - H * x;
        Eigen::MatrixXd S = H * P * H.transpose() + R;
        Eigen::MatrixXd K = P * H.transpose() * S.inverse();
        x = x + K * y;
        Eigen::MatrixXd I = Eigen::MatrixXd::Identity(P.rows(), P.cols());
        P = (I - K * H) * P;
        P = 0.5 * (P + P.transpose());      // 对称化
    }
};
```

### 11.2 EKF 关键差异

* `predict`：`x = f(x, u)`；`P = F P Fᵀ + Q`，其中 `F = ∂f/∂x|_x`。
* `update`：`y = z - h(x)`；`H = ∂h/∂x|_x`。

### 11.3 GTSAM 因子图（C++）

```cpp
NonlinearFactorGraph graph;
Values initial;

graph.add(PriorFactor<Pose3>(0, prior_pose, prior_noise));
graph.add(BetweenFactor<Pose3>(0, 1, odom01, odom_noise));
graph.add(GPSFactor(1, gps_xyz, gps_noise));

initial.insert(0, Pose3());
initial.insert(1, Pose3());

LevenbergMarquardtOptimizer opt(graph, initial);
Values result = opt.optimize();
```

---

## 12. 选型决策

| 场景 | 推荐 |
|------|------|
| 简单线性系统 | KF |
| GPS+IMU+轮速融合，要求实时 | ESKF |
| VIO（视觉惯性） | ESKF / 滑窗 BA |
| LIO（LiDAR 惯性） | iEKF / 因子图（FAST-LIO2 / LIO-SAM） |
| 强非线性观测，雅可比难 | UKF |
| 多模态后验、全局定位 | 粒子滤波 |
| 多传感器、长航时、有闭环 | 因子图 + iSAM2 |
| 离线高精度 | 平滑器 / 全局 BA |

---

## 13. 高频面试题

1. KF 的 5 个公式，K 的物理意义？
2. EKF 与 KF 区别？什么时候 EKF 会发散？
3. EKF vs UKF：选型理由？
4. ESKF 是什么？为什么 VIO 都用 ESKF？
5. 粒子滤波适合什么场景？为什么有维度灾难？
6. 为什么 SLAM 后端从 EKF 转向因子图？
7. IMU 预积分解决了什么问题？
8. 因子图与 KF 等价吗？
9. iSAM2 增量是怎么做的？
10. 协方差矩阵失正定怎么办？
11. 旋转参数化为什么用四元数 / 李代数？
12. 多传感器松 / 紧耦合区别？
13. 给定 IMU 噪声密度怎么转 Q？
14. 量测异常怎么剔除？
15. RTK 失锁，纯 IMU 能维持多久？

---

## 14. Top 15 状态估计 Checklist

1. ☐ 噪声参数有依据（手册 / Allan / 实验），不要拍脑袋。
2. ☐ 协方差强制对称化 + Joseph 形式。
3. ☐ 旋转用四元数 / 李代数；避免欧拉角。
4. ☐ 状态量纲量级一致（单位 / 缩放）。
5. ☐ 时间同步 + 时延补偿。
6. ☐ 量测异常用马氏距离 + 卡方阈值。
7. ☐ IMU 紧耦合用 ESKF / iEKF / 预积分。
8. ☐ 强非线性优先 UKF / 因子图。
9. ☐ 粒子滤波限制状态维度（≤ 6）。
10. ☐ 因子图后端用 GTSAM iSAM2 / Ceres。
11. ☐ 退化场景识别（协方差爆炸、残差突增）。
12. ☐ 估计输出含协方差 / 退化标志。
13. ☐ 离线 evo / 自定义指标做回归。
14. ☐ 单元测试：覆盖单步 KF / EKF / 雅可比正确性（数值微分对照）。
15. ☐ 实车 / 实机鲁棒性演练（断 GPS、断 IMU、抖动）。

---

## 面试速记

1. **KF 五公式**：预测 2 + 更新 3，记住 `K = PHᵀ(HPHᵀ+R)⁻¹`。
2. **K 大** = 信任测量；**K 小** = 信任模型。
3. **EKF** = KF + 雅可比线性化。
4. **ESKF** 处理姿态：误差量小 → 线性近似准。
5. **UKF** 用 sigma 点，不算雅可比，三阶精度。
6. **粒子滤波** 适合多模态、低维。
7. **因子图 = MAP 优化**；现代 SLAM 后端首选。
8. **iSAM2** 增量更新贝叶斯树。
9. **IMU 预积分** 高频积成关键帧间相对约束。
10. **马氏距离 + 卡方** 检测量测离群。
11. **协方差对称化 + Joseph** 防失正定。
12. **松耦合简单、紧耦合精度高**。

---

## 关联阅读

* [SLAM 算法选型对比](./SLAM%20算法选型对比.md) · [机器人工程 最佳实践](./机器人工程%20最佳实践.md)
* [MPC 数学基础](../../mpc/MPC_02_数学基础_状态空间与预测方程.md)
* [Eigen 入门](../../cpp/eigen/Eigen_01_入门与基本类型.md)
