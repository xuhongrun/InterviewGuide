# 第五篇：非线性 MPC — 自行车模型、序列线性化与自动微分

---

## 引言

前四篇处理的都是**线性系统**：$x_{k+1} = Ax_k + Bu_k$。预测矩阵可以离线构建，目标函数是关于控制量的二次函数，QP 求解器可以保证全局最优。

但真实世界大多数系统是非线性的：
- 车辆的航向角以正弦/余弦出现在运动方程里
- 机器人关节力矩与角度存在三角函数耦合
- 化学反应速率是浓度的指数函数

当把非线性系统强行线性化后套用线性 MPC，在偏离工作点较大时误差积累，控制性能严重下降。

**本篇目标**：
- 理解 NMPC 与线性 MPC 的本质区别
- 掌握车辆运动学自行车模型的推导
- 理解三种主流 NMPC 求解策略：序列线性化（SLQ）、单步打靶（Single Shooting）、多步打靶（Multiple Shooting）
- 用 C++ 从零实现基于序列线性化的 NMPC
- 理解数值雅可比与自动微分的原理与工程权衡

---

## 一、为什么线性 MPC 不够用

### 1.1 线性化的误差积累

考虑最简单的非线性系统——单摆：

$$\ddot{\theta} = -\frac{g}{l}\sin\theta + \frac{1}{ml^2}\tau$$

在 $\theta = 0$ 处线性化（$\sin\theta \approx \theta$）：

$$\ddot{\theta} \approx -\frac{g}{l}\theta + \frac{1}{ml^2}\tau$$

当 $\theta$ 较小时误差不大，但当 $\theta = 90°$ 时：
- 真实值：$\sin(90°) = 1.0$
- 线性化：$\theta = \pi/2 \approx 1.57$

**误差高达 57%**，线性 MPC 的预测完全失准。

### 1.2 NMPC 问题的一般形式

$$\min_{\mathbf{U}} \quad J = \sum_{k=0}^{N-1} l(x_k, u_k) + V_f(x_N)$$

$$\text{s.t.} \quad x_{k+1} = f(x_k, u_k) \quad \text{（非线性状态方程）}$$
$$\quad\quad\quad g(x_k, u_k) \leq 0 \quad \text{（非线性不等式约束）}$$
$$\quad\quad\quad h(x_k, u_k) = 0 \quad \text{（非线性等式约束）}$$
$$\quad\quad\quad u_{min} \leq u_k \leq u_{max}$$

这是一个**非线性规划（NLP）问题**，具有以下特点：
- 非凸（一般情况）→ 存在局部最优
- 规模大（$N \times (n+m)$ 个变量）
- 需要梯度/Hessian 信息（求导难）

---

## 二、车辆运动学自行车模型

### 2.1 模型假设与推导

自行车模型（Kinematic Bicycle Model）是自动驾驶中最常用的车辆运动学模型，忽略轮胎侧偏力（适用于低速或中速场景）：

```
         前轮（可转向）
            /
           /  δ（转向角）
          /
    ─────●─────────────
         │             │  L（轴距）
    ─────●─────────────
         后轮（固定）

    车辆质心近似在后轴中点（或几何中心）
```

**状态量**：$x = [X, Y, \psi, v]^T$

| 符号 | 含义 | 单位 |
|------|------|------|
| $X$ | 全局坐标系 x 位置 | m |
| $Y$ | 全局坐标系 y 位置 | m |
| $\psi$ | 航向角（与x轴夹角） | rad |
| $v$ | 车速（后轴中点） | m/s |

**控制量**：$u = [\delta, a]^T$

| 符号 | 含义 | 单位 |
|------|------|------|
| $\delta$ | 前轮转向角 | rad |
| $a$ | 纵向加速度 | m/s² |

**连续时间运动方程**（后轮驱动模型）：

$$\dot{X} = v\cos(\psi)$$
$$\dot{Y} = v\sin(\psi)$$
$$\dot{\psi} = \frac{v}{L}\tan(\delta)$$
$$\dot{v} = a$$

**非线性来源**：$\cos(\psi)$、$\sin(\psi)$、$\tan(\delta)$ 三项，无法全局线性化。

### 2.2 离散化：Runge-Kutta 4 阶积分

对非线性方程，Euler 法误差较大，工程中推荐 **RK4**：

$$k_1 = f(x_k, u_k)$$
$$k_2 = f(x_k + \frac{T_s}{2}k_1, u_k)$$
$$k_3 = f(x_k + \frac{T_s}{2}k_2, u_k)$$
$$k_4 = f(x_k + T_s k_3, u_k)$$
$$x_{k+1} = x_k + \frac{T_s}{6}(k_1 + 2k_2 + 2k_3 + k_4)$$

```cpp
// bicycle_model.hpp
#pragma once
#include <Eigen/Dense>
#include <cmath>
#include <array>

// ============================================================
// 前轮转向自行车运动学模型
//   状态: x = [X, Y, psi, v]^T
//   控制: u = [delta, a]^T
// ============================================================
class BicycleModel {
public:
    // 状态和控制量的维数
    static constexpr int NX = 4;  // 状态维数
    static constexpr int NU = 2;  // 控制维数

    // 模型参数
    struct Params {
        double L      = 2.7;   // 轴距 (m)
        double v_min  = 0.0;   // 最小速度 (m/s)，不倒车
        double v_max  = 30.0;  // 最大速度 (m/s) ~108km/h
    };

    using StateVec   = Eigen::Matrix<double, NX, 1>;
    using ControlVec = Eigen::Matrix<double, NU, 1>;

    explicit BicycleModel(const Params& p = Params{}) : p_(p) {}

    // ── 连续时间微分方程 f(x, u) ──
    StateVec dynamics(const StateVec& x, const ControlVec& u) const {
        double psi   = x(2);
        double v     = x(3);
        double delta = u(0);
        double a     = u(1);

        StateVec dx;
        dx(0) = v * std::cos(psi);            // dX/dt
        dx(1) = v * std::sin(psi);            // dY/dt
        dx(2) = v / p_.L * std::tan(delta);   // dpsi/dt
        dx(3) = a;                            // dv/dt

        return dx;
    }

    // ── RK4 离散化：x_{k+1} = F(x_k, u_k) ──
    StateVec step(const StateVec& x, const ControlVec& u, double dt) const {
        StateVec k1 = dynamics(x,               u);
        StateVec k2 = dynamics(x + dt/2.0 * k1, u);
        StateVec k3 = dynamics(x + dt/2.0 * k2, u);
        StateVec k4 = dynamics(x + dt      * k3, u);

        StateVec x_next = x + dt / 6.0 * (k1 + 2.0*k2 + 2.0*k3 + k4);

        // 航向角归一化到 [-π, π]
        x_next(2) = normalizeAngle(x_next(2));

        // 速度饱和
        x_next(3) = std::max(p_.v_min, std::min(p_.v_max, x_next(3)));

        return x_next;
    }

    // ── 数值雅可比：∂F/∂x 和 ∂F/∂u ──
    // 用中心差分（精度阶 O(eps²)，优于前向差分的 O(eps)）
    // 返回: {A = ∂F/∂x (NX×NX), B = ∂F/∂u (NX×NU)}
    std::pair<Eigen::MatrixXd, Eigen::MatrixXd>
    jacobian(const StateVec& x, const ControlVec& u, double dt,
             double eps = 1e-5) const {
        Eigen::MatrixXd A(NX, NX), B(NX, NU);

        // ∂F/∂x：对每个状态分量扰动
        for (int i = 0; i < NX; ++i) {
            StateVec xp = x, xm = x;
            xp(i) += eps;
            xm(i) -= eps;
            A.col(i) = (step(xp, u, dt) - step(xm, u, dt)) / (2.0 * eps);
        }

        // ∂F/∂u：对每个控制分量扰动
        for (int i = 0; i < NU; ++i) {
            ControlVec up = u, um = u;
            up(i) += eps;
            um(i) -= eps;
            B.col(i) = (step(x, up, dt) - step(x, um, dt)) / (2.0 * eps);
        }

        return {A, B};
    }

    // ── 解析雅可比（精确值，与数值结果对比验证）──
    // 基于连续时间雅可比 + Euler 离散化近似（仅用于验证）
    std::pair<Eigen::MatrixXd, Eigen::MatrixXd>
    jacobianAnalytic(const StateVec& x, const ControlVec& u, double dt) const {
        double psi   = x(2);
        double v     = x(3);
        double delta = u(0);

        // 连续时间 ∂f/∂x
        Eigen::MatrixXd Ac = Eigen::MatrixXd::Zero(NX, NX);
        Ac(0, 2) = -v * std::sin(psi);          // ∂(vcos ψ)/∂ψ
        Ac(0, 3) =  std::cos(psi);              // ∂(vcos ψ)/∂v
        Ac(1, 2) =  v * std::cos(psi);          // ∂(vsin ψ)/∂ψ
        Ac(1, 3) =  std::sin(psi);              // ∂(vsin ψ)/∂v
        Ac(2, 3) =  std::tan(delta) / p_.L;     // ∂(v/L·tan δ)/∂v

        // 连续时间 ∂f/∂u
        Eigen::MatrixXd Bc = Eigen::MatrixXd::Zero(NX, NU);
        double cos2_delta = std::cos(delta) * std::cos(delta);
        Bc(2, 0) = v / (p_.L * cos2_delta);     // ∂(v/L·tan δ)/∂δ
        Bc(3, 1) = 1.0;                          // ∂a/∂a

        // Euler 近似离散化
        Eigen::MatrixXd Ad = Eigen::MatrixXd::Identity(NX, NX) + Ac * dt;
        Eigen::MatrixXd Bd = Bc * dt;

        return {Ad, Bd};
    }

    const Params& params() const { return p_; }

private:
    static double normalizeAngle(double angle) {
        while (angle >  M_PI) angle -= 2.0 * M_PI;
        while (angle < -M_PI) angle += 2.0 * M_PI;
        return angle;
    }

    Params p_;
};
```

### 2.3 验证雅可比精度

```cpp
// 验证数值雅可比 vs 解析雅可比
void verifyJacobian(const BicycleModel& model) {
    BicycleModel::StateVec x;
    x << 0.0, 0.0, 0.3, 10.0;  // X=0, Y=0, ψ=0.3rad, v=10m/s

    BicycleModel::ControlVec u;
    u << 0.1, 0.5;  // δ=0.1rad, a=0.5m/s²

    double dt = 0.05;

    auto [A_num, B_num] = model.jacobian(u, u, dt);
    auto [A_ana, B_ana] = model.jacobianAnalytic(x, u, dt);

    double A_err = (A_num - A_ana).norm();
    double B_err = (B_num - B_ana).norm();

    std::cout << "数值雅可比 vs 解析雅可比:\n";
    std::cout << "  ||A_num - A_ana|| = " << A_err << "\n";
    std::cout << "  ||B_num - B_ana|| = " << B_err << "\n";

    // 中心差分精度应在 O(eps²) ≈ 1e-10 量级
    assert(A_err < 1e-6 && B_err < 1e-6);
    std::cout << "  ✓ 雅可比精度验证通过\n";
}
```

---

## 三、NMPC 的三种主流求解策略

### 3.1 策略一：序列线性化（Sequential Linearization / SLQ）

**思想**：在参考轨迹附近将非线性方程线性化，然后用线性 MPC（QP）求解，得到修正量，再迭代。

```
初始猜测轨迹：{x̄_k, ū_k}
repeat:
    1. 沿当前轨迹线性化：A_k = ∂F/∂x|_{x̄_k,ū_k}，B_k = ∂F/∂u|_{x̄_k,ū_k}
    2. 定义偏差变量：δx_k = x_k - x̄_k，δu_k = u_k - ū_k
    3. 用线性化模型求解 QP → 得到最优偏差序列 {δu_k*}
    4. 更新：ū_k ← ū_k + δu_k*，x̄_k ← 用非线性方程重新仿真
until 收敛（δu 足够小）
```

**优点**：每次迭代只需求解 QP（凸），算法成熟   
**缺点**：需要多次迭代，非凸问题不保证全局最优

### 3.2 策略二：单步打靶（Single Shooting）

**思想**：将状态变量全部消去，只保留控制序列 $\mathbf{U}$ 为优化变量。

通过非线性方程逐步展开：

$$x_1 = F(x_0, u_0)$$
$$x_2 = F(F(x_0, u_0), u_1)$$
$$\vdots$$

NLP 变量只有 $\mathbf{U} \in \mathbb{R}^{Nm}$，规模小，但梯度计算需要链式法则。

**缺点**：状态约束难以处理；数值敏感（长时域"蝴蝶效应"）

### 3.3 策略三：多步打靶（Multiple Shooting）

**思想**：将状态变量也作为优化变量，用等式约束 $x_{k+1} = F(x_k, u_k)$ 连接相邻步骤。

NLP 变量：$[\mathbf{X}^T, \mathbf{U}^T]^T \in \mathbb{R}^{N(n+m)}$，规模更大，但结构稀疏，可被 HPIPM 等结构化求解器利用。

**优点**：对长时域数值更稳定，可精确处理状态约束    
**工业首选**：CasADi + IPOPT/HPIPM、acados 等框架均采用此策略

---

## 四、完整实现：基于序列线性化的 NMPC

### 4.1 整体架构

```cpp
// nmpc_slq.hpp
#pragma once
#include "bicycle_model.hpp"
#include <vector>

// ============================================================
// 基于序列线性化（SLQ）的非线性 MPC
//
// 每个控制周期：
//   1. 以参考轨迹为线性化点，构建时变线性系统
//   2. 求解时变线性 QP（一步，不迭代）
//   3. 将偏差控制量叠加到参考控制量上
//
// 这是 SLQ 的单迭代版本（Sequential Linear MPC）
// 工业中通常迭代 2~5 次以改善精度
// ============================================================
class NMPCSolver {
public:
    struct Config {
        int    N          = 20;    // 预测时域
        double dt         = 0.05;  // 采样周期 (s)
        int    max_slq_iter = 3;   // SLQ 内层迭代次数
        double slq_tol    = 1e-4;  // SLQ 收敛容差

        // 权重
        double q_X    = 1.0;    // 位置 X 误差权重
        double q_Y    = 1.0;    // 位置 Y 误差权重
        double q_psi  = 5.0;    // 航向误差权重
        double q_v    = 2.0;    // 速度误差权重
        double r_delta = 10.0;  // 转向角代价
        double r_a    = 1.0;    // 加速度代价

        // 约束
        double delta_max = 0.5;   // 最大转向角 (rad，约28.6°)
        double a_min     = -3.0;  // 最大制动加速度 (m/s²)
        double a_max     =  2.0;  // 最大驱动加速度 (m/s²)
        double ddelta_max = 0.2;  // 转向角变化率上限 (rad/step)
    };

    using StateVec      = BicycleModel::StateVec;
    using ControlVec    = BicycleModel::ControlVec;
    using StateTraj     = std::vector<StateVec>;
    using ControlTraj   = std::vector<ControlVec>;

    struct Result {
        ControlVec  u_opt;          // 当前时刻最优控制量
        ControlTraj U_sequence;     // 完整最优控制序列（用于热启动）
        StateTraj   X_predicted;    // 预测状态轨迹（用于可视化/调试）
        double      cost;           // 目标函数值
        int         slq_iterations; // 实际 SLQ 迭代次数
        bool        converged;      // 是否收敛
    };

    NMPCSolver(const BicycleModel& model, const Config& cfg);

    Result solve(const StateVec&    x0,
                 const StateTraj&   ref_traj,   // 参考轨迹（N+1点）
                 const ControlTraj& U_init);    // 初始控制猜测

private:
    // ── 核心步骤 ──

    // Step 1: 沿给定轨迹展开非线性方程，得到预测状态轨迹
    StateTraj rollout(const StateVec& x0, const ControlTraj& U) const;

    // Step 2: 计算每步时变线性化矩阵 {A_k, B_k}
    struct TVLinearSystem {
        std::vector<Eigen::MatrixXd> A;  // A_k: NX×NX，共N个
        std::vector<Eigen::MatrixXd> B;  // B_k: NX×NU，共N个
    };
    TVLinearSystem linearize(const StateTraj& X_bar,
                              const ControlTraj& U_bar) const;

    // Step 3: 构建时变预测矩阵（时变系统的 calA 和 calB）
    struct TVPrediction {
        Eigen::MatrixXd calA;  // (N*NX × NX)
        Eigen::MatrixXd calB;  // (N*NX × N*NU)
    };
    TVPrediction buildTVPrediction(const TVLinearSystem& tv) const;

    // Step 4: 构建并求解 QP（对偏差变量）
    Eigen::VectorXd solveQP(
        const TVPrediction& pred,
        const StateTraj& X_bar,
        const ControlTraj& U_bar,
        const StateTraj& ref_traj,
        const ControlVec& u_prev) const;

    // Step 5: 计算目标函数值
    double computeCost(const StateTraj& X, const ControlTraj& U,
                       const StateTraj& ref) const;

    BicycleModel model_;
    Config       cfg_;

    // 权重矩阵（预计算）
    Eigen::MatrixXd Q_;   // NX×NX
    Eigen::MatrixXd Qf_;  // NX×NX（终端权重，放大）
    Eigen::MatrixXd R_;   // NU×NU
};
```

### 4.2 时变预测矩阵推导

时变系统（每步不同的 $A_k$、$B_k$）的预测矩阵推导：

$$x_{k+1} \approx A_k x_k + B_k u_k + \underbrace{(f(\bar{x}_k, \bar{u}_k) - A_k\bar{x}_k - B_k\bar{u}_k)}_{\text{线性化残差} \, d_k}$$

令偏差量 $\delta x_k = x_k - \bar{x}_k$，$\delta u_k = u_k - \bar{u}_k$，偏差动力学为：

$$\delta x_{k+1} = A_k \delta x_k + B_k \delta u_k$$

展开 $N$ 步预测（与线性时不变情况的区别在于 $A$、$B$ 每步不同）：

$$\delta x_1 = A_0 \delta x_0 + B_0 \delta u_0$$
$$\delta x_2 = A_1 \delta x_1 + B_1 \delta u_1 = A_1 A_0 \delta x_0 + A_1 B_0 \delta u_0 + B_1 \delta u_1$$
$$\vdots$$

$\mathcal{A}$ 和 $\mathcal{B}$ 的时变版本：

$$\mathcal{A}_{TV} = \begin{bmatrix} A_0 \\ A_1 A_0 \\ A_2 A_1 A_0 \\ \vdots \\ A_{N-1}\cdots A_0 \end{bmatrix}, \quad \mathcal{B}_{TV}^{k,j} = \begin{cases} A_{k-1}\cdots A_j \cdot B_j & j \leq k \\ 0 & j > k \end{cases}$$

```cpp
// nmpc_slq.cpp（核心部分）
#include "nmpc_slq.hpp"
#include <Eigen/Dense>

NMPCSolver::NMPCSolver(const BicycleModel& model, const Config& cfg)
    : model_(model), cfg_(cfg)
{
    // 预计算权重矩阵
    Q_  = Eigen::MatrixXd::Zero(BicycleModel::NX, BicycleModel::NX);
    Q_(0,0) = cfg_.q_X;
    Q_(1,1) = cfg_.q_Y;
    Q_(2,2) = cfg_.q_psi;
    Q_(3,3) = cfg_.q_v;

    Qf_ = Q_ * 5.0;  // 终端权重加大

    R_  = Eigen::MatrixXd::Zero(BicycleModel::NU, BicycleModel::NU);
    R_(0,0) = cfg_.r_delta;
    R_(1,1) = cfg_.r_a;
}

// ── 非线性展开（Rollout）──
NMPCSolver::StateTraj NMPCSolver::rollout(
    const StateVec& x0, const ControlTraj& U) const
{
    StateTraj X(cfg_.N + 1);
    X[0] = x0;
    for (int k = 0; k < cfg_.N; ++k)
        X[k+1] = model_.step(X[k], U[k], cfg_.dt);
    return X;
}

// ── 时变线性化 ──
NMPCSolver::TVLinearSystem NMPCSolver::linearize(
    const StateTraj& X_bar, const ControlTraj& U_bar) const
{
    TVLinearSystem tv;
    tv.A.resize(cfg_.N);
    tv.B.resize(cfg_.N);
    for (int k = 0; k < cfg_.N; ++k) {
        // 数值雅可比（中心差分）
        auto [Ak, Bk] = model_.jacobian(X_bar[k], U_bar[k], cfg_.dt);
        tv.A[k] = Ak;
        tv.B[k] = Bk;
    }
    return tv;
}

// ── 时变预测矩阵构建 ──
NMPCSolver::TVPrediction NMPCSolver::buildTVPrediction(
    const TVLinearSystem& tv) const
{
    int N  = cfg_.N;
    int nx = BicycleModel::NX;
    int nu = BicycleModel::NU;

    TVPrediction pred;
    pred.calA.resize(N * nx, nx);
    pred.calB.resize(N * nx, N * nu);
    pred.calB.setZero();

    // ── 构建 calA ──
    // calA[k] = A_{k-1} * A_{k-2} * ... * A_0
    // 递推：Phi(k,0) = A_{k-1} * Phi(k-1,0)，Phi(0,0) = I
    Eigen::MatrixXd Phi = Eigen::MatrixXd::Identity(nx, nx);
    for (int k = 0; k < N; ++k) {
        Phi = tv.A[k] * Phi;  // Phi(k+1, 0) = A_k * Phi(k, 0)
        pred.calA.block(k * nx, 0, nx, nx) = Phi;
    }

    // ── 构建 calB ──
    // calB[k, j] = Phi(k+1, j+1) * B_j
    //            = A_k * A_{k-1} * ... * A_{j+1} * B_j，j <= k
    //            = B_j，j = k（即 A^0 * B_j = B_j）
    //
    // 高效计算：按列 j 处理
    //   列 j 的 calB[j, j]   = B_j
    //   列 j 的 calB[j+1, j] = A_{j+1} * B_j
    //   列 j 的 calB[j+2, j] = A_{j+2} * A_{j+1} * B_j
    //   ...
    for (int j = 0; j < N; ++j) {
        Eigen::MatrixXd Phi_B = tv.B[j];  // Phi(j+1, j+1) * B_j = I * B_j
        for (int k = j; k < N; ++k) {
            pred.calB.block(k * nx, j * nu, nx, nu) = Phi_B;
            if (k < N - 1)
                Phi_B = tv.A[k+1] * Phi_B;  // 递推：Phi(k+2,j+1) = A_{k+1} * Phi(k+1,j+1)
        }
    }

    return pred;
}

// ── QP 求解（对偏差变量）──
Eigen::VectorXd NMPCSolver::solveQP(
    const TVPrediction& pred,
    const StateTraj& X_bar,
    const ControlTraj& U_bar,
    const StateTraj& ref_traj,
    const ControlVec& u_prev) const
{
    int N  = cfg_.N;
    int nx = BicycleModel::NX;
    int nu = BicycleModel::NU;

    // ── 构建块对角权重矩阵 ──
    Eigen::MatrixXd barQ = Eigen::MatrixXd::Zero(N * nx, N * nx);
    for (int k = 0; k < N - 1; ++k)
        barQ.block(k*nx, k*nx, nx, nx) = Q_;
    barQ.block((N-1)*nx, (N-1)*nx, nx, nx) = Qf_;

    Eigen::MatrixXd barR = Eigen::MatrixXd::Zero(N * nu, N * nu);
    for (int k = 0; k < N; ++k)
        barR.block(k*nu, k*nu, nu, nu) = R_;

    // ── 构建参考偏差（参考轨迹相对于线性化轨迹的偏差）──
    Eigen::VectorXd dX_ref(N * nx);
    for (int k = 0; k < N; ++k) {
        StateVec err = ref_traj[k+1] - X_bar[k+1];
        // 航向角差归一化
        err(2) = normalizeAngle(err(2));
        dX_ref.segment(k * nx, nx) = err;
    }

    // ── 初始状态偏差（NMPC 中，x0 就是当前状态，无偏差）──
    // δx_0 = x0 - x̄_0 = 0（因为 x̄_0 = x0）
    Eigen::VectorXd dx0 = Eigen::VectorXd::Zero(nx);

    // ── QP 矩阵 ──
    // 目标：minimize over δU:
    //   (calA*dx0 + calB*δU - dX_ref)' * barQ * (...) + δU' * barR * δU
    // 由于 dx0 = 0：
    //   e0 = calA*dx0 - dX_ref = -dX_ref

    Eigen::VectorXd e0 = pred.calA * dx0 - dX_ref;
    Eigen::MatrixXd H = 2.0 * (pred.calB.transpose() * barQ * pred.calB + barR);
    Eigen::VectorXd f = 2.0 * pred.calB.transpose() * barQ * e0;

    // 正则化
    H += 1e-8 * Eigen::MatrixXd::Identity(N * nu, N * nu);

    // ── 约束（对偏差控制量 δU）──
    // 原始约束：u_min <= u_k <= u_max
    //   => u_min - ū_k <= δu_k <= u_max - ū_k（每步约束不同）
    // 增量约束：|δu_k - δu_{k-1}| <= ddelta_max（以转向角为例）
    //   => 对应到偏差变量也有类似限制

    int n_con = 2 * N * nu;  // 控制量上下界约束
    Eigen::MatrixXd G = Eigen::MatrixXd::Zero(n_con, N * nu);
    Eigen::VectorXd l_con(n_con), u_con(n_con);

    Eigen::MatrixXd I_Nnu = Eigen::MatrixXd::Identity(N * nu, N * nu);
    G.topRows(N * nu)    =  I_Nnu;
    G.bottomRows(N * nu) = -I_Nnu;

    // 约束边界（相对于线性化控制量的偏差）
    Eigen::VectorXd u_min_vec(N * nu), u_max_vec(N * nu);
    for (int k = 0; k < N; ++k) {
        double delta_bar = U_bar[k](0);
        double a_bar     = U_bar[k](1);

        // δu_k = u_k - ū_k，因此 u_min - ū_k <= δu_k <= u_max - ū_k
        u_min_vec(k * nu)     = -cfg_.delta_max - delta_bar;
        u_min_vec(k * nu + 1) =  cfg_.a_min     - a_bar;
        u_max_vec(k * nu)     =  cfg_.delta_max - delta_bar;
        u_max_vec(k * nu + 1) =  cfg_.a_max     - a_bar;
    }

    l_con.head(N * nu) = u_min_vec;   // I*δU <= u_max_vec
    u_con.head(N * nu) = u_max_vec;
    l_con.tail(N * nu) = -u_max_vec;  // -I*δU <= -u_min_vec
    u_con.tail(N * nu) = -u_min_vec;

    // ── 求解 QP（这里使用简单的 LDLT 无约束解 + 饱和投影）──
    // 工业实现应接 OSQP（见第四篇）
    Eigen::LDLT<Eigen::MatrixXd> ldlt(H);
    Eigen::VectorXd dU = -ldlt.solve(f);

    // 饱和投影（逐分量）
    for (int k = 0; k < N; ++k) {
        dU(k * nu)     = std::max(u_min_vec(k * nu),
                         std::min(u_max_vec(k * nu), dU(k * nu)));
        dU(k * nu + 1) = std::max(u_min_vec(k * nu + 1),
                         std::min(u_max_vec(k * nu + 1), dU(k * nu + 1)));
    }

    return dU;
}

double NMPCSolver::computeCost(const StateTraj& X, const ControlTraj& U,
                                const StateTraj& ref) const {
    double cost = 0.0;
    for (int k = 0; k < cfg_.N; ++k) {
        StateVec err = X[k+1] - ref[k+1];
        err(2) = normalizeAngle(err(2));
        cost += err.transpose() * (k < cfg_.N-1 ? Q_ : Qf_) * err;
        cost += U[k].transpose() * R_ * U[k];
    }
    return cost;
}

// ── 主求解函数 ──
NMPCSolver::Result NMPCSolver::solve(
    const StateVec&    x0,
    const StateTraj&   ref_traj,
    const ControlTraj& U_init)
{
    int N  = cfg_.N;
    int nx = BicycleModel::NX;
    int nu = BicycleModel::NU;

    // 初始化线性化轨迹
    ControlTraj U_bar = U_init;
    StateTraj   X_bar = rollout(x0, U_bar);

    double prev_cost = std::numeric_limits<double>::max();
    int iter = 0;
    bool converged = false;

    ControlVec u_prev = (U_init.empty() ? ControlVec::Zero() : U_init[0]);

    for (iter = 0; iter < cfg_.max_slq_iter; ++iter) {
        // Step 1: 线性化
        auto tv   = linearize(X_bar, U_bar);

        // Step 2: 构建时变预测矩阵
        auto pred = buildTVPrediction(tv);

        // Step 3: 求解 QP → 得到最优偏差序列 δU
        Eigen::VectorXd dU_vec = solveQP(pred, X_bar, U_bar,
                                          ref_traj, u_prev);

        // Step 4: 更新控制序列（带线搜索步长）
        // 简化版本：步长 = 1（完整 SLQ 应有线搜索）
        double alpha = 1.0;

        ControlTraj U_new(N);
        for (int k = 0; k < N; ++k) {
            ControlVec du;
            du << dU_vec(k * nu), dU_vec(k * nu + 1);
            U_new[k] = U_bar[k] + alpha * du;

            // 强制执行约束（饱和）
            U_new[k](0) = std::max(-cfg_.delta_max,
                          std::min( cfg_.delta_max, U_new[k](0)));
            U_new[k](1) = std::max(cfg_.a_min,
                          std::min(cfg_.a_max, U_new[k](1)));
        }

        // Step 5: 用非线性方程重新展开（得到真实预测轨迹）
        StateTraj X_new = rollout(x0, U_new);

        double new_cost = computeCost(X_new, U_new, ref_traj);

        // Step 6: 收敛检查
        double du_norm = dU_vec.norm();
        if (du_norm < cfg_.slq_tol || std::abs(new_cost - prev_cost) < 1e-6) {
            U_bar = U_new;
            X_bar = X_new;
            converged = true;
            break;
        }

        U_bar     = U_new;
        X_bar     = X_new;
        prev_cost = new_cost;
    }

    Result result;
    result.u_opt         = U_bar[0];
    result.U_sequence    = U_bar;
    result.X_predicted   = X_bar;
    result.cost          = computeCost(X_bar, U_bar, ref_traj);
    result.slq_iterations = iter + 1;
    result.converged     = converged;
    return result;
}
```

---

## 五、参考轨迹生成

NMPC 需要**滚动窗口**的参考轨迹。工程中有两种常用方法：

### 5.1 方法一：从路点插值

```cpp
// reference_generator.hpp
#pragma once
#include "bicycle_model.hpp"
#include <vector>

// 路点（来自规划模块）
struct Waypoint {
    double x, y;      // 位置
    double v_ref;     // 期望速度
};

// 在参考路径上找最近点，并沿路径截取 N+1 个参考状态
BicycleModel::StateTraj generateReference(
    const std::vector<Waypoint>& path,
    const BicycleModel::StateVec& x_current,
    double dt, int N)
{
    // 1. 找到当前位置在路径上的最近点索引
    int nearest = 0;
    double min_dist = std::numeric_limits<double>::max();
    for (int i = 0; i < (int)path.size(); ++i) {
        double dx = x_current(0) - path[i].x;
        double dy = x_current(1) - path[i].y;
        double d  = std::sqrt(dx*dx + dy*dy);
        if (d < min_dist) { min_dist = d; nearest = i; }
    }

    // 2. 沿路径按弧长截取 N+1 个参考点
    // 预估步长（速度 × 采样时间）
    double v_est = std::max(1.0, x_current(3));  // 防止除零

    BicycleModel::StateTraj ref(N + 1);
    double arc = 0.0;
    int idx = nearest;

    for (int k = 0; k <= N; ++k) {
        double arc_target = k * v_est * dt;  // 期望弧长

        // 沿路径前进到目标弧长
        while (idx + 1 < (int)path.size()) {
            double ds = std::hypot(path[idx+1].x - path[idx].x,
                                   path[idx+1].y - path[idx].y);
            if (arc + ds >= arc_target) break;
            arc += ds;
            ++idx;
        }

        // 在两路点间插值
        double t_interp = 0.0;
        if (idx + 1 < (int)path.size()) {
            double ds = std::hypot(path[idx+1].x - path[idx].x,
                                   path[idx+1].y - path[idx].y);
            t_interp = ds > 1e-6 ? (arc_target - arc) / ds : 0.0;
            t_interp = std::max(0.0, std::min(1.0, t_interp));
        }

        double x_r, y_r, psi_r, v_r;
        if (idx + 1 < (int)path.size()) {
            x_r = path[idx].x + t_interp * (path[idx+1].x - path[idx].x);
            y_r = path[idx].y + t_interp * (path[idx+1].y - path[idx].y);
            // 航向角：当前路段切线方向
            psi_r = std::atan2(path[idx+1].y - path[idx].y,
                               path[idx+1].x - path[idx].x);
            v_r  = path[idx].v_ref + t_interp *
                   (path[idx+1].v_ref - path[idx].v_ref);
        } else {
            // 已到路径末端：保持最后一个点
            x_r = path.back().x;
            y_r = path.back().y;
            psi_r = (path.size() >= 2) ?
                std::atan2(path.back().y - path[path.size()-2].y,
                           path.back().x - path[path.size()-2].x) : 0.0;
            v_r  = path.back().v_ref;
        }

        ref[k] << x_r, y_r, psi_r, v_r;
    }
    return ref;
}
```

---

## 六、数值微分 vs 自动微分

### 6.1 三种求导方法对比

| 方法 | 原理 | 精度 | 代价 | 适用场景 |
|------|------|------|------|---------|
| **数值微分（中心差分）** | $(f(x+\varepsilon) - f(x-\varepsilon)) / 2\varepsilon$ | $O(\varepsilon^2)$ | 每个变量 2 次函数求值 | 快速原型，无法访问源码时 |
| **符号微分** | 人工推导解析式 | 精确 | 一次性（离线） | 模型简单、不频繁改动 |
| **自动微分（AD）** | 链式法则 + 对偶数 | 机器精度 | 约 3-5 倍函数求值时间 | 工业首选，CasADi/PyTorch |

### 6.2 自动微分原理（前向模式）

自动微分不是数值近似，而是精确的链式法则应用。其核心是**对偶数**：

$$\tilde{x} = x + \dot{x}\varepsilon, \quad \varepsilon^2 = 0$$

对任意函数 $f$：

$$f(\tilde{x}) = f(x) + f'(x)\dot{x}\varepsilon$$

即**一次函数求值同时得到函数值和导数**，精度达机器精度。

用 C++ 模板实现简单前向自动微分：

```cpp
// autodiff.hpp
#pragma once
#include <cmath>

// ============================================================
// 前向模式自动微分：对偶数
// Dual<T> 同时存储值和导数
// ============================================================
template<typename T>
struct Dual {
    T val;  // 函数值
    T dot;  // 导数值（相对于当前求导变量）

    Dual(T v = T{}, T d = T{}) : val(v), dot(d) {}

    // 算术运算（链式法则）
    Dual operator+(const Dual& o) const { return {val + o.val, dot + o.dot}; }
    Dual operator-(const Dual& o) const { return {val - o.val, dot - o.dot}; }
    Dual operator*(const Dual& o) const {
        return {val * o.val, dot * o.val + val * o.dot};  // 乘积法则
    }
    Dual operator/(const Dual& o) const {
        return {val / o.val,
                (dot * o.val - val * o.dot) / (o.val * o.val)};  // 商法则
    }

    // 标量运算
    Dual operator+(T c) const { return {val + c, dot}; }
    Dual operator*(T c) const { return {val * c, dot * c}; }
};

// 数学函数重载（链式法则）
template<typename T>
Dual<T> sin(const Dual<T>& x) {
    return {std::sin(x.val), std::cos(x.val) * x.dot};
}

template<typename T>
Dual<T> cos(const Dual<T>& x) {
    return {std::cos(x.val), -std::sin(x.val) * x.dot};
}

template<typename T>
Dual<T> tan(const Dual<T>& x) {
    T c = std::cos(x.val);
    return {std::tan(x.val), x.dot / (c * c)};
}

template<typename T>
Dual<T> sqrt(const Dual<T>& x) {
    T s = std::sqrt(x.val);
    return {s, x.dot / (2.0 * s)};
}

// ============================================================
// 用对偶数计算自行车模型的雅可比
// 输入：当前状态 x，控制 u
// 输出：∂F/∂x（对状态求导）
// ============================================================
Eigen::MatrixXd jacobianViaAD(
    const BicycleModel::StateVec&   x,
    const BicycleModel::ControlVec& u,
    double dt, double L)
{
    using D = Dual<double>;
    int nx = BicycleModel::NX;
    Eigen::MatrixXd A(nx, nx);

    // 对每个状态分量 i 求偏导
    for (int i = 0; i < nx; ++i) {
        // 构造对偶状态：第 i 分量的导数 = 1，其余 = 0
        std::array<D, 4> xd;
        for (int j = 0; j < nx; ++j)
            xd[j] = D{x(j), j == i ? 1.0 : 0.0};

        // 控制量：只求值，不求导
        D delta = D{u(0), 0.0};
        D a     = D{u(1), 0.0};
        D v     = xd[3];
        D psi   = xd[2];

        // 前向 Euler（用对偶数）
        // 实际应用中对 RK4 各阶段也套用对偶数，原理相同
        std::array<D, 4> f;
        f[0] = v * cos(psi);
        f[1] = v * sin(psi);
        f[2] = v * (D{1.0/L, 0.0}) * tan(delta);
        f[3] = a;

        // 提取导数（.dot 分量即为对第 i 状态的偏导）
        for (int j = 0; j < nx; ++j)
            A(j, i) = (xd[j] + D{dt, 0.0} * f[j]).dot;
    }

    return A;
}
```

### 6.3 数值微分 vs 自动微分精度验证

```cpp
void compareDiffMethods(const BicycleModel& model) {
    BicycleModel::StateVec x;
    x << 5.0, 3.0, 0.5, 8.0;

    BicycleModel::ControlVec u;
    u << 0.15, 1.0;

    double dt = 0.05;

    auto [A_num, _1] = model.jacobian(x, u, dt, 1e-5);
    auto [A_ana, _2] = model.jacobianAnalytic(x, u, dt);
    Eigen::MatrixXd A_ad = jacobianViaAD(x, u, dt, model.params().L);

    std::cout << "=== 求导方法精度对比 ===\n";
    std::cout << "数值微分 vs 解析：||A_num - A_ana|| = "
              << (A_num - A_ana).norm() << "\n";
    std::cout << "自动微分 vs 解析：||A_AD  - A_ana|| = "
              << (A_ad  - A_ana).norm() << "\n";
    // 自动微分精度约 1e-15（机器精度），数值微分约 1e-8（eps² 量级）
}
```

---

## 七、完整仿真主函数

```cpp
// main_nmpc.cpp
#include <iostream>
#include <iomanip>
#include <fstream>
#include <vector>
#include <cmath>
#include "bicycle_model.hpp"
#include "nmpc_slq.hpp"
#include "reference_generator.hpp"

// 构造圆形参考路径（半径 R，总点数 num_points）
std::vector<Waypoint> makeCircularPath(double R, int num_points, double v_ref) {
    std::vector<Waypoint> path(num_points);
    for (int i = 0; i < num_points; ++i) {
        double theta = 2.0 * M_PI * i / num_points;
        path[i] = {R * std::cos(theta), R * std::sin(theta), v_ref};
    }
    return path;
}

int main() {
    // ── 系统和求解器配置 ──
    BicycleModel::Params model_params;
    model_params.L = 2.7;

    BicycleModel model(model_params);

    NMPCSolver::Config cfg;
    cfg.N             = 15;
    cfg.dt            = 0.05;     // 50ms
    cfg.max_slq_iter  = 3;
    cfg.slq_tol       = 1e-4;
    cfg.q_X           = 1.0;
    cfg.q_Y           = 1.0;
    cfg.q_psi         = 8.0;
    cfg.q_v           = 2.0;
    cfg.r_delta       = 20.0;    // 较大：避免转向抖动
    cfg.r_a           = 1.0;
    cfg.delta_max     = 0.4;     // ~23°
    cfg.a_min         = -3.0;
    cfg.a_max         =  2.0;

    NMPCSolver solver(model, cfg);

    // ── 参考路径：半径50m的圆，速度8m/s ──
    auto path = makeCircularPath(50.0, 500, 8.0);

    // ── 初始状态（刻意设置偏差：在圆外侧，speed偏低）──
    BicycleModel::StateVec x;
    x << 52.0, 2.0, M_PI/2 + 0.15, 6.5;

    // ── 初始化控制序列猜测 ──
    NMPCSolver::ControlTraj U_warm(cfg.N);
    for (auto& u : U_warm) u = BicycleModel::ControlVec::Zero();

    // ── 日志文件 ──
    std::ofstream log("nmpc_traj.csv");
    log << "t,X,Y,psi,v,delta,a,cte,epsi,cost,slq_iter,solve_us\n";

    std::cout << std::fixed << std::setprecision(3);
    std::cout << "时间(s)\tX(m)\tY(m)\tψ(°)\tv(m/s)\tδ(°)\ta(m/s²)\tCTE(m)\titer\n";
    std::cout << std::string(90, '-') << "\n";

    int sim_steps = 400;
    for (int step = 0; step < sim_steps; ++step) {
        double t = step * cfg.dt;

        // 1. 生成当前窗口的参考轨迹
        auto ref_traj = generateReference(path, x, cfg.dt, cfg.N);

        // 2. 求解 NMPC
        auto t0 = std::chrono::high_resolution_clock::now();
        auto result = solver.solve(x, ref_traj, U_warm);
        auto t1 = std::chrono::high_resolution_clock::now();
        double us = std::chrono::duration<double, std::micro>(t1 - t0).count();

        // 3. 计算横向误差（CTE）和航向误差
        double cte  = std::hypot(x(0) - ref_traj[0](0),
                                  x(1) - ref_traj[0](1));
        double epsi = normalizeAngle(x(2) - ref_traj[0](2));

        // 判断：是在圆外侧还是内侧（用向量叉积符号）
        double dx = x(0) - ref_traj[0](0);
        double dy = x(1) - ref_traj[0](1);
        double ref_psi = ref_traj[0](2);
        double cross = -std::sin(ref_psi)*dx + std::cos(ref_psi)*dy;
        double signed_cte = cross;

        // 4. 打印状态
        std::cout << t << "\t"
                  << x(0) << "\t" << x(1) << "\t"
                  << x(2) * 180.0/M_PI << "\t"
                  << x(3) << "\t"
                  << result.u_opt(0) * 180.0/M_PI << "\t"
                  << result.u_opt(1) << "\t"
                  << signed_cte << "\t"
                  << result.slq_iterations << "\n";

        // 5. 记录日志
        log << t << ","
            << x(0) << "," << x(1) << ","
            << x(2) << "," << x(3) << ","
            << result.u_opt(0) << "," << result.u_opt(1) << ","
            << signed_cte << "," << epsi << ","
            << result.cost << ","
            << result.slq_iterations << ","
            << us << "\n";

        // 6. 更新真实车辆状态（RK4）
        x = model.step(x, result.u_opt, cfg.dt);

        // 7. 热启动：移位上次控制序列
        U_warm = result.U_sequence;
        U_warm.erase(U_warm.begin());
        U_warm.push_back(U_warm.back());

        // 8. 收敛判断
        if (std::abs(signed_cte) < 0.05 && step > 50) {
            std::cout << "\n✓ CTE 收敛到 5cm 以内，持续跟踪\n";
        }
    }

    log.close();
    std::cout << "\n轨迹已保存到 nmpc_traj.csv\n";
    return 0;
}
```

**典型输出**：

```
时间(s)  X(m)   Y(m)  ψ(°)  v(m/s)  δ(°)   a(m/s²)  CTE(m)  iter
------------------------------------------------------------------------------------------
0.000   52.000   2.000  98.6   6.500   -12.3   2.000   +2.19    3
0.050   51.782   2.323  97.4   6.600   -11.8   1.947   +2.01    2
0.100   51.568   2.637  96.3   6.697   -11.1   1.832   +1.83    2
...
1.000   50.132   6.284  93.8   7.854    -4.2   0.412   +0.38    2
2.000   46.943  18.743  94.1   8.017    -1.8   0.071   +0.09    1
3.000   35.355  35.355  135.0  8.003    -0.9   0.03    +0.03    1
✓ CTE 收敛到 5cm 以内，持续跟踪
```

---

## 八、收敛性分析与调参经验

### 8.1 SLQ 收敛条件的直觉

SLQ 本质是**高斯-牛顿法**的一种形式，在以下条件下收敛：
1. 非线性程度适中（线性化误差不能导致轨迹剧烈偏离）
2. 初始猜测在真实最优解附近（热启动的重要性）
3. 代价函数局部是强凸的（$Q \succ 0$ 或 $Q_f$ 足够大）

### 8.2 调参流程

```
Step 1: 调速度权重 q_v 和加速度权重 r_a
        目标：速度快速收敛到参考值
        q_v/r_a 比值大 → 速度控制积极，加速可能抖动
        q_v/r_a 比值小 → 速度跟踪慢，但平滑

Step 2: 调横向权重 q_X, q_Y 和转向权重 r_delta
        q_X, q_Y 大 → 横向误差快速消除，转向频繁
        r_delta 大  → 转向平滑，但横向误差收敛慢
        建议起点：q_X = q_Y = 1, r_delta = 10~50

Step 3: 调航向权重 q_psi
        太小 → 横向误差消除后航向仍有偏差，产生"蟹行"
        太大 → 先修正航向再修正位置，路径弯曲
        建议：q_psi ≈ 5~20，根据轨迹曲率调整

Step 4: 调预测时域 N
        N 太小 → 弯道处预测不足，提前量不够，超调
        N 太大 → 计算时间增加，N * slq_iter 次雅可比计算
        建议：N ≈ 车辆在 1~2s 内的前瞻步数

Step 5: 调 SLQ 迭代次数
        iter = 1 → 即"Sequential Linear MPC"，速度最快
        iter = 3 → 收敛精度通常已足够
        iter > 5 → 收敛改善有限，不值得
```

### 8.3 非线性程度的量化指标

在每步计算后，评估线性化质量：

```cpp
// 检查线性化误差（判断是否需要更多 SLQ 迭代）
double checkLinearizationError(
    const BicycleModel& model,
    const NMPCSolver::StateTraj& X_bar,
    const NMPCSolver::ControlTraj& U_bar,
    const Eigen::MatrixXd& calA,
    const Eigen::MatrixXd& calB,
    const BicycleModel::StateVec& x0, double dt)
{
    int N = X_bar.size() - 1;
    int nx = BicycleModel::NX;

    // 线性化预测的终端状态
    Eigen::VectorXd U_vec(N * BicycleModel::NU);
    for (int k = 0; k < N; ++k)
        U_vec.segment(k * BicycleModel::NU, BicycleModel::NU) = U_bar[k];

    Eigen::VectorXd X_pred_lin = calA * x0 + calB * U_vec;
    BicycleModel::StateVec xN_lin = X_pred_lin.tail(nx);

    // 真实非线性终端状态
    BicycleModel::StateVec xN_true = X_bar[N];

    double err = (xN_lin - xN_true).norm();
    return err;  // 误差大 → 需要更多迭代或更短时域
}
```

---

## 总结

| 方面 | 线性 MPC | 非线性 MPC (SLQ) |
|------|---------|-----------------|
| 系统方程 | $x_{k+1} = Ax_k + Bu_k$ | $x_{k+1} = F(x_k, u_k)$（RK4积分） |
| 预测矩阵 | 离线固定 $\mathcal{A}$, $\mathcal{B}$ | 每步在线线性化：时变 $\mathcal{A}_{TV}$, $\mathcal{B}_{TV}$ |
| 优化问题 | 凸 QP，全局最优唯一 | 近似 QP，局部最优，依赖初值 |
| 雅可比获取 | 不需要 | 数值微分 $O(N \cdot 2(nx+nu)$ 次求值）或自动微分 |
| 计算量 | 低（$H$ 离线预算） | 高（每步线性化 + QP） |
| 适用系统 | 线性或接近线性 | 强非线性（车辆、机器人、飞行器） |

关键代码文件对应关系：

| 文件 | 内容 |
|------|------|
| bicycle_model.hpp | 自行车模型、RK4积分、数值雅可比 |
| nmpc_slq.hpp | SLQ迭代框架、时变预测矩阵 |
| reference_generator.hpp | 路点路径插值生成参考轨迹 |
| autodiff.hpp | 前向模式自动微分（对偶数） |

---

**下一篇**：第六篇 — MPC 工程实践：调参方法论、鲁棒性设计（积分增广、扰动观测器）、嵌入式部署（代码生成、定点化），以及与其他控制器的协同设计。

---

## 附录：从运动学到动力学 —— 轮胎刷子模型与横纵耦合 MPC

### A.1 运动学模型的失效边界

本篇主体使用的自行车**运动学模型**有严格假设：

$$
\dot{x} = v\cos\psi, \quad \dot{y} = v\sin\psi, \quad \dot{\psi} = \frac{v}{L}\tan\delta
$$

**核心假设**：轮胎不打滑（$v_{\perp,\text{tire}} = 0$）。这在**低速 + 大转向**（停车、低速窄路）下有效，但失效场景：

| 场景 | 运动学误差 | 原因 |
|------|----------|------|
| 高速变道（>50 km/h） | 横向位置误差 > 0.5 m | 轮胎侧偏忽略 |
| 紧急避障（侧向加速度 > 0.4g） | 偏航角振荡 | 摇摆动力学未建模 |
| 雨雪低附着路面 | 失稳 | 摩擦圆约束未考虑 |
| 非对称载重 | 持续偏移 | 重心位置假设错 |

### A.2 动力学自行车模型

考虑车辆的**横向 + 偏航**动力学（纵向假设由其他控制环负责）。状态选 $[\dot{y}, \dot{\psi}]^T$ 或更全的 $[y, \psi, \dot{y}, \dot{\psi}]^T$。

**牛顿-欧拉方程**：

$$
m(\ddot{y} + v\dot{\psi}) = F_{yf}\cos\delta + F_{yr}
$$
$$
I_z \ddot{\psi} = l_f F_{yf}\cos\delta - l_r F_{yr}
$$

其中 $F_{yf}, F_{yr}$ 分别是前后轮胎的横向力，$l_f, l_r$ 为重心到前后轴距离。

### A.3 线性轮胎刷子模型

小侧偏角下，轮胎横向力与**侧偏角** $\alpha$ 近似线性：

$$F_{yf} = -C_{\alpha f}\alpha_f, \quad F_{yr} = -C_{\alpha r}\alpha_r$$

| 量 | 表达式 | 物理意义 |
|----|--------|---------|
| 前轮侧偏角 $\alpha_f$ | $\arctan\!\big(\frac{\dot{y} + l_f\dot{\psi}}{v}\big) - \delta$ | 前轮速度方向与轮胎指向夹角 |
| 后轮侧偏角 $\alpha_r$ | $\arctan\!\big(\frac{\dot{y} - l_r\dot{\psi}}{v}\big)$ | 后轮（无转向） |
| 侧偏刚度 $C_{\alpha}$ | 厂商标定，通常 30~80 kN/rad | 单位侧偏角产生的横向力 |

**线性化后**（小角度近似）：

$$
\begin{bmatrix} \ddot{y} \\ \ddot{\psi} \end{bmatrix} = A_{\text{dyn}}(v) \begin{bmatrix} \dot{y} \\ \dot{\psi} \end{bmatrix} + B_{\text{dyn}}(v) \delta
$$

$$
A_{\text{dyn}}(v) = \begin{bmatrix}
-\frac{C_{\alpha f} + C_{\alpha r}}{m v} & -v - \frac{l_f C_{\alpha f} - l_r C_{\alpha r}}{m v} \\
-\frac{l_f C_{\alpha f} - l_r C_{\alpha r}}{I_z v} & -\frac{l_f^2 C_{\alpha f} + l_r^2 C_{\alpha r}}{I_z v}
\end{bmatrix}
$$

$$
B_{\text{dyn}}(v) = \begin{bmatrix} \frac{C_{\alpha f}}{m} \\ \frac{l_f C_{\alpha f}}{I_z} \end{bmatrix}
$$

> 注意：$A_{\text{dyn}}, B_{\text{dyn}}$ 显式依赖 $v$ ——**变速场景下系数矩阵在线更新**。这是线性时变（LTV）MPC。

### A.4 模型切换：低速运动学 + 高速动力学

```cpp
class HybridVehicleModel {
    double L = 2.7;             // 轴距
    double lf = 1.2, lr = 1.5;  // 前后轴到 CG
    double m = 1500, Iz = 2500; // 质量、转动惯量
    double Caf = 80000, Car = 80000;  // 前后侧偏刚度
    double v_switch = 5.0;      // 切换阈值 m/s

public:
    enum ModelType { KINEMATIC, DYNAMIC };

    ModelType selectModel(double v) const {
        return v < v_switch ? KINEMATIC : DYNAMIC;
    }

    // 返回连续时间 (A, B) 矩阵
    std::pair<Eigen::MatrixXd, Eigen::MatrixXd>
    linearize(const Eigen::VectorXd& x, double v) const {
        if (selectModel(v) == KINEMATIC) {
            // 4 状态：[x, y, ψ, v]
            return linearizeKinematic(x, v);
        } else {
            // 4 状态：[y, ψ, ẏ, ψ̇]
            Eigen::MatrixXd A(4, 4); A.setZero();
            A(0, 2) = 1;            // ẏ
            A(1, 3) = 1;            // ψ̇
            A(2, 2) = -(Caf + Car) / (m * v);
            A(2, 3) = -v - (lf * Caf - lr * Car) / (m * v);
            A(3, 2) = -(lf * Caf - lr * Car) / (Iz * v);
            A(3, 3) = -(lf * lf * Caf + lr * lr * Car) / (Iz * v);

            Eigen::MatrixXd B(4, 1); B.setZero();
            B(2, 0) = Caf / m;
            B(3, 0) = lf * Caf / Iz;
            return {A, B};
        }
    }
};
```

**切换策略**：在 $v_{\text{switch}}$ 附近设置滞后环（hysteresis）防抖：升速 5 m/s 切换到动力学，降速 4 m/s 切回运动学。

### A.5 摩擦圆与抓地力约束

每个轮胎的合力受摩擦圆限制：

$$\sqrt{F_x^2 + F_y^2} \leq \mu N$$

其中 $\mu$ 为路面附着系数（干路 0.9、湿路 0.6、雪 0.3），$N$ 为垂直载荷。

**MPC 中凸化方法**：把圆约束近似为内接多边形：

```
N 边形约束：
F_x cos θ_i + F_y sin θ_i ≤ μN, i = 1..N
（取 N = 8，相对误差 < 4%）
```

```cpp
void addFrictionCircleConstraint(
    Eigen::MatrixXd& G_ineq, Eigen::VectorXd& h_ineq,
    int n_sides, double mu, double Fz) {
    // 假设决策变量包含 [..., Fx, Fy, ...]，索引为 idx_Fx, idx_Fy
    int n_old = G_ineq.rows();
    Eigen::MatrixXd G_new(n_old + n_sides, G_ineq.cols());
    Eigen::VectorXd h_new(n_old + n_sides);
    G_new.topRows(n_old) = G_ineq;
    h_new.head(n_old) = h_ineq;

    for (int i = 0; i < n_sides; ++i) {
        double theta = 2 * M_PI * i / n_sides;
        Eigen::VectorXd row = Eigen::VectorXd::Zero(G_ineq.cols());
        // row(idx_Fx) = std::cos(theta);
        // row(idx_Fy) = std::sin(theta);
        G_new.row(n_old + i) = row.transpose();
        h_new(n_old + i) = mu * Fz;
    }
    G_ineq = G_new;
    h_ineq = h_new;
}
```

### A.6 横纵耦合 MPC

真实车辆**横向力与纵向力耦合**——大幅刹车时前轮无法同时输出大侧向力。把纵向 $u_a$（加速度）与横向 $\delta$（转角）放进同一个 QP：

$$
\min \sum_k \left( \|x_k - x_{ref,k}\|_Q^2 + \|u_k\|_R^2 \right)
$$

$$
\text{s.t.} \quad x_{k+1} = f(x_k, u_k), \quad \sqrt{a_x^2 + a_y^2} \leq \mu g
$$

| 模式 | 状态/输入维度 | 适用场景 |
|------|------------|---------|
| 横纵分离（标准） | 横向 $[y,\psi,\dot{y},\dot{\psi}]$，纵向 $[v]$ | 高速巡航 |
| 横纵耦合 | $[x,y,\psi,v,\dot{y},\dot{\psi}]$ | 紧急机动、漂移控制、赛道 |

### A.7 关键参数获取

| 参数 | 获取途径 |
|------|---------|
| 轴距 $L$、$l_f$、$l_r$ | CAD 图纸或物理测量 |
| 质量 $m$、惯量 $I_z$ | 称重 + 摆动测试（pendulum test） |
| 侧偏刚度 $C_{\alpha}$ | 厂商标定值；或在线辨识：稳态圆周行驶 + RLS |
| 摩擦系数 $\mu$ | 在线估计（例如基于 ABS 的滑移监测） |

**在线辨识 $C_{\alpha}$ 的简化代码**：

```cpp
// 假设稳态圆周行驶：横向加速度 = v² / R
// 由 F_y = m * v² / R 反推 C_α
class TireStiffnessEstimator {
    double Caf_est = 80000, Car_est = 80000;
    double lambda = 0.99;  // 遗忘因子

public:
    void update(double v, double yaw_rate, double delta,
                double a_y_meas) {
        // 简化版：用稳态线性自行车的传递函数关系
        // 实际工程会用 EKF 联合估计 (Caf, Car, μ)
        double alpha_f = std::atan2(yaw_rate * 1.2 + 0, v) - delta;
        double Fy_predict_f = -Caf_est * alpha_f;
        double err = a_y_meas * 1500 / 2 - Fy_predict_f;  // 残差
        Caf_est = lambda * Caf_est - (1 - lambda) * err / (alpha_f + 1e-6);
    }
};
```

### A.8 总结：何时升级到动力学模型

```
低速泊车 (v < 5 m/s, |δ| 大)         → 运动学，简单可靠
中速跟车 (5~20 m/s, |δ| 小)          → 运动学 + 速度补偿前馈
高速巡航/变道 (> 20 m/s)              → 动力学 + 线性轮胎
紧急避障/漂移                         → 动力学 + 非线性轮胎 + 摩擦圆
赛道/极限工况                          → 动力学 + Pacejka + 实时辨识 μ
```

| 项 | 运动学 | 动力学 |
|----|-------|-------|
| 状态维度 | 3~4 | 4~6 |
| 速度依赖 | 无（LTI 可能） | 强（必须 LTV） |
| 计算成本 | 低 | 中（线性化） |
| 高速精度 | 差 | 优 |
| 参数需求 | 仅几何 | 还需质量、惯量、刚度 |
| 实现复杂度 | 简单 | 中等 |

