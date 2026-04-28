# 第十篇：自动驾驶专题 —— Frenet 坐标系、走廊约束与 SCP 序列凸优化

---

## 引言

自动驾驶规划-控制的事实标准是：

```
全局路径 (HD Map)
   ↓
局部路径规划 (lattice / 采样 / 优化)
   ↓
轨迹平滑 (Frenet 坐标系下五次多项式)
   ↓
轨迹跟踪 (MPC，本篇主角)
```

本篇聚焦三个工业必备技能：
1. **Frenet 坐标系**：把全局路径转化为 MPC 友好的 1D 进度 + 1D 偏移
2. **走廊约束（Corridor Constraint）**：把复杂障碍场景化为多面体约束
3. **SCP（Sequential Convex Programming）**：处理非凸约束下的轨迹优化

---

## 一、Frenet 坐标系基础

### 1.1 定义

参考曲线 $\gamma(s)$（中心车道线），用弧长 $s$ 参数化。任意点 $P$ 的 Frenet 坐标：

- $s$：从 $\gamma$ 起点到 $P$ 的最近投影点的弧长
- $d$（亦称 $n$）：$P$ 到投影点的有符号距离（左正右负）

```
       d > 0
         ↑
─────────┼────────  reference γ(s)
         │
         ↓
       d < 0
```

### 1.2 笛卡尔 ↔ Frenet 转换

**笛卡尔 → Frenet**：

```cpp
struct FrenetState { double s, d, ds_dt, dd_ds; };

FrenetState toFrenet(double x, double y, const ReferencePath& path) {
    // 1. 找最近投影点 s*
    double s_star = path.findNearestS(x, y);
    Eigen::Vector2d p_ref = path.point(s_star);
    Eigen::Vector2d t_ref = path.tangent(s_star);  // 单位切向
    Eigen::Vector2d n_ref(-t_ref.y(), t_ref.x()); // 单位法向

    // 2. 投影
    Eigen::Vector2d offset(x - p_ref.x(), y - p_ref.y());
    double d = offset.dot(n_ref);
    return {s_star, d, 0, 0};  // 速度量另算
}
```

**Frenet → 笛卡尔**：

$$
\begin{aligned}
x &= x_{\text{ref}}(s) - d\sin\theta_{\text{ref}}(s) \\
y &= y_{\text{ref}}(s) + d\cos\theta_{\text{ref}}(s) \\
\psi &= \theta_{\text{ref}}(s) + \arctan\!\big(\frac{d'}{1 - \kappa(s) d}\big)
\end{aligned}
$$

其中 $\kappa(s)$ 是参考曲线在 $s$ 处的曲率，$d'$ 是 $d$ 对 $s$ 的导数。

### 1.3 Frenet 下的车辆动力学

把自行车模型写在 Frenet 坐标下，纵向进度 $s$ 与横向偏离 $d$ 解耦（小 $d$ 假设下）：

$$
\begin{aligned}
\dot{s} &= \frac{v\cos(\psi - \theta_{\text{ref}})}{1 - \kappa(s) d} \\
\dot{d} &= v \sin(\psi - \theta_{\text{ref}}) \\
\dot{\psi} &= \frac{v}{L}\tan\delta
\end{aligned}
$$

**优势**：MPC 状态变量 $[s, d, \psi]$，参考轨迹自然变成 $d_{\text{ref}}(s) = 0$（沿中心线）+ $v_{\text{ref}}(s)$。

```cpp
// Frenet 下的线性化（用于线性 MPC）
struct FrenetLinearModel {
    double v;          // 当前速度
    double kappa_ref;  // 当前 s 处的参考曲率
    double L;          // 轴距

    Eigen::MatrixXd A() const {
        // 状态：[d, ψ_e, ψ̇]，输入：δ
        Eigen::MatrixXd A(3, 3);
        A << 0, v, 0,
             0, 0, 1,
             0, 0, 0;
        return A;
    }

    Eigen::MatrixXd B() const {
        Eigen::MatrixXd B(3, 1);
        B << 0, 0, v / L;
        return B;
    }

    Eigen::VectorXd disturbance() const {
        // 曲率引起的等效扰动（前馈）
        Eigen::VectorXd d(3);
        d << 0, -v * kappa_ref, 0;
        return d;
    }
};
```

### 1.4 Frenet MPC 的关键公式

**横向偏差 dynamics**：

$$
\dot{e}_d = v\sin(e_\psi) \approx v \cdot e_\psi
$$
$$
\dot{e}_\psi = \dot{\psi} - v\kappa_{\text{ref}} = \frac{v}{L}\tan\delta - v\kappa_{\text{ref}}
$$

**前馈 + 反馈结构**：

$$\delta = \underbrace{\arctan(L\kappa_{\text{ref}})}_{\text{曲率前馈}} + \underbrace{\delta_{\text{MPC}}}_{\text{MPC 反馈}}$$

前馈消除参考曲率引起的稳态偏差，MPC 仅负责消除残差扰动——**比纯反馈 MPC 跟踪精度提高 5~10 倍**。

---

## 二、参考轨迹预瞄（Lookahead）

### 2.1 为什么需要预瞄

车辆控制存在不可避免的**纯延迟**：转向指令 → 转向电机 → 车轮转向 → 横向位移 累计 100~200 ms。MPC 时域 $N$ 步覆盖未来 $N \cdot dt$ 时间，正好对应预瞄能力。

预瞄距离 $L_p = v \cdot T_p$，其中 $T_p$ 是预瞄时间（典型 1~2 s）。

### 2.2 高速 vs 低速预瞄策略

| 速度 | 推荐 $T_p$ | $N$ | 备注 |
|------|----------|-----|------|
| < 5 m/s（停车场） | 0.5 s | 5 | 短预瞄，对小曲率敏感 |
| 5~15 m/s（市区） | 1.0 s | 10 | 中等预瞄 |
| 15~30 m/s（高速） | 2.0 s | 20 | 长预瞄，应对大曲率提前转向 |
| > 30 m/s（赛道） | 3.0 s | 30+ | 含动力学模型 |

### 2.3 自适应预瞄

```cpp
double adaptiveLookahead(double v, double curvature) {
    double base_time = 1.0;
    if (v > 20.0) base_time = 1.5 + (v - 20) * 0.05;
    if (std::abs(curvature) > 0.05) base_time *= 1.3;  // 大曲率增加预瞄
    return base_time * v;  // 返回预瞄距离
}
```

---

## 三、走廊约束（Corridor Constraint）

### 3.1 动机：避障约束的 MPC 表达

最朴素的避障约束（圆形障碍 $O_i$ 半径 $r_i$）：

$$\sqrt{(x - x_{O_i})^2 + (y - y_{O_i})^2} \geq r_i$$

这是**非凸**约束（"不在圆内"是凹集），无法直接放进凸 QP。

### 3.2 走廊：把可行域凸化

**走廊**是若干**凸多边形**的序列：

```
路径规划生成 → 凸走廊 = ∪_i { Polytope_i }
              每个 Polytope_i = { x : H_i x ≤ k_i }（半空间交集）
```

车辆在第 $j$ 个时间段必须留在走廊的第 $i(j)$ 个多边形内：

$$H_{i(j)} \, p_j \leq k_{i(j)}, \quad p_j = (x_j, y_j)$$

这就把"避免障碍"变成**线性约束**——可直接放进 QP。

### 3.3 走廊生成算法（Safe Flight Corridor / GCS）

经典实现 IRIS（Iterative Regional Inflation by Semidefinite programming）：

```
输入：路径点 P_0, P_1, ..., P_n + 障碍物集合 O
输出：凸多边形序列 {C_0, C_1, ..., C_n}

算法：
  对每个路径点 P_i：
    1. 初始化椭球 E ⊂ 自由空间，中心 P_i
    2. 迭代直到收敛：
       (a) 求超平面 H 把 E 与所有 O ∈ O 分离
       (b) 把所有 H 求交集 → 得到多边形 C_i
       (c) 把 E 膨胀到 C_i 的最大内切椭球
    3. C_i 即为该路径点的凸多边形
```

简化版本（用于自动驾驶 2D 场景）：

```cpp
struct ConvexCorridor {
    // 多边形序列，每段对应一个时间段
    std::vector<Eigen::MatrixXd> H_list;  // 每段 H_i
    std::vector<Eigen::VectorXd> k_list;  // 每段 k_i
};

// 在 MPC QP 中加入走廊约束
void addCorridorConstraints(
    Eigen::MatrixXd& G, Eigen::VectorXd& h,
    const ConvexCorridor& corridor,
    int N, int n_state, int idx_x, int idx_y) {
    int total_rows = 0;
    for (auto& H : corridor.H_list) total_rows += H.rows();

    int row_start = G.rows();
    G.conservativeResize(row_start + total_rows, G.cols());
    h.conservativeResize(row_start + total_rows);
    G.bottomRows(total_rows).setZero();

    int row = row_start;
    for (int t = 0; t < N; ++t) {
        const auto& H_t = corridor.H_list[t];
        const auto& k_t = corridor.k_list[t];
        // 决策变量布局假设：U = [u_0, ..., u_{N-1}]，状态 X 由 U 经预测矩阵推出
        // 这里需要把 H_t * [x_t; y_t] = H_t * select(X, idx_x, idx_y) 化为 G * U + ...
        // （实际工程中通过预测矩阵的子矩阵实现，篇幅省略）
        h.segment(row, H_t.rows()) = k_t;
        row += H_t.rows();
    }
}
```

### 3.4 走廊约束的工程优势

| 优势 | 说明 |
|------|------|
| **凸 QP** | 标准 OSQP 直接求解 |
| **解释性强** | 走廊可视化即直观可见 |
| **与规划层解耦** | 规划生成走廊，MPC 只负责"在走廊内最优" |
| **保守但安全** | 走廊比真实自由空间小（凸近似），但保证不撞 |

### 3.5 缺陷与对策

| 缺陷 | 对策 |
|------|------|
| 走廊太窄导致不可行 | 走廊膨胀（inflate）+ 软约束 |
| 多边形面数太多 | 限制每段 ≤ 8 个半平面，否则 QP 维度爆炸 |
| 走廊切换瞬间有突变 | 重叠相邻走廊（重合 0.5~1 m），平滑过渡 |

---

## 四、SCP：处理真正的非凸约束

走廊已能处理静态障碍。**动态障碍**或**复杂运动学约束**（如 $|F_x^2 + F_y^2| \leq \mu^2 N^2$ 摩擦圆）是非凸的——SCP 登场。

### 4.1 SCP 思想

把非凸问题在当前迭代点 $z^{(k)}$ 处**线性化**，得到一个凸子问题；在凸子问题加**信任域约束** $\|z - z^{(k)}\| \leq \rho$；求解、更新 $z^{(k+1)}$，重复。

```
SCP 算法：
1. 给定初值 z^(0)
2. for k = 0, 1, 2, ...:
   (a) 线性化非凸约束 g(z) ≤ 0  →  ∇g(z^(k))^T (z - z^(k)) + g(z^(k)) ≤ 0
   (b) 求解凸子问题（QP/SOCP），加信任域 ‖z - z^(k)‖ ≤ ρ_k
   (c) 评估真实代价改进比 r_k
   (d) 若 r_k > 0.75 → ρ_{k+1} = 2 ρ_k（信任域扩大）
       若 r_k < 0.25 → ρ_{k+1} = ρ_k / 2（信任域缩小）
   (e) 收敛检查：‖z^(k+1) - z^(k)‖ < ε 或 |改进| < ε
```

### 4.2 与 SLQ 的区别

| 项 | SLQ（第五篇） | SCP |
|----|------------|-----|
| 处理对象 | 非线性 dynamics | 非凸约束 + 非线性 dynamics |
| 子问题 | LQR / QP | QP / SOCP |
| 信任域 | 通常无 | 有（关键稳定机制） |
| 代价函数 | 二次 | 任意凸 |
| 收敛性 | 局部，依赖初值 | 局部，但更鲁棒（信任域） |

SLQ 是 SCP 的"动力学专用"特例。

### 4.3 SCP 在 MPC 中的应用

```cpp
class SCPMPC {
    int max_iter_ = 10;
    double trust_region_ = 0.5;
    double tol_ = 1e-4;

    Eigen::VectorXd z_prev_;  // 上一帧解作为热启动

public:
    Eigen::VectorXd solve(const Eigen::VectorXd& x0,
                          const NonconvexConstraints& g) {
        Eigen::VectorXd z = z_prev_;  // 热启动
        for (int it = 0; it < max_iter_; ++it) {
            // 1. 线性化非凸约束
            auto [J, b] = g.linearize(z);
            // 2. 构建凸子问题（含信任域）
            auto [H, f, G_ineq, h_ineq] = buildConvexSubproblem(
                x0, z, J, b, trust_region_);
            // 3. 求 QP
            Eigen::VectorXd dz = solveQP(H, f, G_ineq, h_ineq);
            Eigen::VectorXd z_new = z + dz;
            // 4. 评估改进
            double improvement_ratio = evaluateImprovement(z, z_new, g);
            if (improvement_ratio > 0.75) trust_region_ *= 2.0;
            else if (improvement_ratio < 0.25) trust_region_ *= 0.5;
            // 5. 收敛
            if (dz.norm() < tol_) break;
            z = z_new;
        }
        z_prev_ = z;
        return z;
    }
};
```

### 4.4 工程实践要点

| 要点 | 经验值 |
|------|-------|
| 最大迭代数 | 5~10（大部分 3 步内收敛） |
| 初始信任域 | 状态尺度的 10%~20% |
| 收敛容差 | 状态尺度的 0.1% |
| 求解超时回退 | 用上一帧解 + 移位 |

---

## 五、完整自动驾驶 MPC 架构

```
┌──────────────────────────────────────────────────┐
│   感知层（10 Hz）                                │
│   输出：障碍物列表 + 车道线                      │
├──────────────────────────────────────────────────┤
│   行为决策层（5~10 Hz）                          │
│   输出：意图（变道/跟车/停车）                  │
├──────────────────────────────────────────────────┤
│   局部规划（10~20 Hz）                            │
│   输出：候选轨迹 + 凸走廊                         │
├──────────────────────────────────────────────────┤
│   轨迹平滑（50 Hz）                               │
│   输出：Frenet 参考轨迹 [s_ref(t), d_ref(t), v_ref(t)]│
├──────────────────────────────────────────────────┤
│   MPC 控制（100 Hz） ← 本系列主角                 │
│   - 线性 MPC：低速、运动学                       │
│   - 动力学 MPC：高速                             │
│   - SCP MPC：复杂避障                            │
│   输出：[转向角, 加速度]                          │
├──────────────────────────────────────────────────┤
│   底层执行（200~500 Hz）                          │
│   - 转向：电机 PI 控制                           │
│   - 油门/刹车：发动机/制动 PI                    │
└──────────────────────────────────────────────────┘
```

### 5.1 各层接口规范

```cpp
struct PlanningOutput {
    std::vector<FrenetWaypoint> reference_path;  // 参考轨迹
    ConvexCorridor corridor;                      // 凸走廊
    std::vector<DynamicObstacle> moving_obstacles;
    double v_target;
    double t_horizon;
};

struct MPCInput {
    PlanningOutput plan;
    VehicleState current_state;  // 笛卡尔 + Frenet 双坐标
    double current_speed;
};

struct MPCOutput {
    double steer_angle;      // [rad]
    double acceleration;     // [m/s^2]
    double solve_time_ms;
    bool success;
    int active_constraint_count;
};
```

---

## 六、面试常见问

### Q1：为什么用 Frenet 而不是直接笛卡尔？

> 三点：
> 1. **参考变成常数**：在 Frenet 下 $d_{\text{ref}} = 0$，MPC 跟踪问题化简为镇定问题
> 2. **状态量解耦**：$s$（纵向）与 $d$（横向）近似独立，便于分别调权重
> 3. **曲率前馈**：$\delta_{\text{ff}} = \arctan(L\kappa)$ 直接由参考曲率算出，MPC 仅处理残差
>
> 但代价：Frenet 转换需要找最近投影点（O(log n) 二分），且大 $d$ 时近似失效（要求 $|\kappa d| < 1$）。

### Q2：走廊约束的"宽度"怎么定？

> 在保证安全的前提下尽量宽：
> - 至少 = 车宽 + 两侧 0.3 m 安全余量
> - 在曲线段适当扩大（车辆轨迹会切弯）
> - 在执行器饱和场景下进一步加宽（避免 MPC 不可行）

### Q3：SCP 收敛失败怎么办？

> 三步处理：
> 1. 检查初值——SCP 局部收敛，初值远离最优可能发散
> 2. 缩小信任域——大幅缩到 5% 系统尺度
> 3. 改用全局规划求初值——A*/RRT 提供初始轨迹，SCP 做精细化

### Q4：动态障碍 vs 静态障碍处理有何区别？

> 动态障碍要预测其未来轨迹（恒速 / IDM / 神经网络），把每个时间步的占据空间从凸走廊中切除。本质上是**时空走廊**——走廊在每个 $t$ 不同。

---

## 总结

| 概念 | 用途 | 难度 |
|------|------|------|
| Frenet 坐标系 | 把全局参考化为 MPC 友好的局部参考 | ⭐⭐ |
| 曲率前馈 | 消除参考曲率引起的稳态偏差 | ⭐⭐ |
| 自适应预瞄 | 根据速度/曲率动态调整 MPC 时域 | ⭐⭐ |
| 凸走廊 | 把避障变成线性约束 | ⭐⭐⭐ |
| SCP | 处理非凸约束（动态障碍、摩擦圆等） | ⭐⭐⭐⭐ |
| 时空走廊 | 处理动态障碍 | ⭐⭐⭐⭐ |

**自动驾驶 MPC 的"组合拳"**：

```
Frenet 坐标系（化简参考） + 曲率前馈（消除稳态） +
动力学模型（高速精度）   + 凸走廊（避障）       +
SCP（非凸场景）         + Tube MPC（鲁棒性）  → 完整工业级方案
```
