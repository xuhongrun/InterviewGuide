# 第七篇：MPC 前沿专题 — 鲁棒、随机与学习型 MPC

---

## 引言

前六篇构建了完整的 MPC 实践体系：从线性 QP 到非线性 SLQ，从软约束到嵌入式部署。本篇进入 MPC 的研究前沿。

这些方向不是学术游戏——它们解决的是工程现实中的核心痛点：

- **Tube MPC**：如何在有界扰动下**保证**约束永远不被违反？
- **随机 MPC**：扰动是随机的，如何最小化**期望**代价并约束**违反概率**？
- **学习型 MPC**：当模型不准确时，如何用数据**在线修正**预测误差？

**本篇目标**：理解这三个方向的数学原理、适用场景，并用 C++ 实现核心算法。

---

## 一、Tube MPC：有界扰动下的鲁棒保证

### 1.1 标准 MPC 的鲁棒性缺陷

回忆标准 MPC：假设系统精确满足 $x_{k+1} = Ax_k + Bu_k$，约束 $x_k \in \mathcal{X}$、$u_k \in \mathcal{U}$。

但真实系统：

$$x_{k+1} = Ax_k + Bu_k + w_k, \quad w_k \in \mathcal{W}$$

$w_k$ 是有界但未知的扰动（建模误差、外力、量化误差）。标准 MPC **不考虑** $w_k$，导致：
- 预测轨迹偏离真实轨迹
- 真实状态可能违反约束（即使预测轨迹可行）
- **无法提供约束满足的硬保证**

### 1.2 Tube MPC 的核心思想

**思想**：将系统轨迹分解为两部分：

$$x_k = \bar{x}_k + e_k$$

- $\bar{x}_k$：**标称轨迹**（无扰动时的理想轨迹），由标准 MPC 优化
- $e_k$：**误差**（扰动导致的偏差），用辅助控制器抑制

关键结论：如果误差 $e_k$ 被限制在一个**不变集（Invariant Set）** $\mathcal{E}$ 内，那么：
- 真实状态 $x_k \in \bar{x}_k \oplus \mathcal{E}$（即 $x_k$ 在以 $\bar{x}_k$ 为中心的"管道"内）
- 只需约束标称轨迹在**收紧约束域** $\mathcal{X} \ominus \mathcal{E}$ 内，真实状态就自动满足 $\mathcal{X}$

这个围绕标称轨迹的"管道"就是 **Tube（管道）**，由此得名。

```
真实轨迹（受扰动）：
     ╔═══════════╗
     ║  tube     ║
  ───╬───  ─ ──╬───  ─   真实状态 x_k（在管道内游荡）
     ║  标称轨迹 ║
     ╚═══════════╝

约束域 X 收紧为 X ⊖ E：
┌─────────────────────────────┐
│   X（原始约束）              │
│  ┌───────────────────────┐  │
│  │   X ⊖ E（收紧约束）   │  │  ← 标称轨迹在这里优化
│  │                       │  │
│  └───────────────────────┘  │
│   ←E→                        │  ← 给误差留的裕量
└─────────────────────────────┘
```

### 1.3 鲁棒正不变集（RPI Set）

**定义**：集合 $\mathcal{E}$ 是系统 $e_{k+1} = (A + BK)e_k + w_k$ 的鲁棒正不变集，若：

$$\forall e \in \mathcal{E}, \forall w \in \mathcal{W}: (A+BK)e + w \in \mathcal{E}$$

即：从集合内出发，无论扰动如何，下一步仍在集合内。

**最小鲁棒正不变集（mRPI）**：所有 RPI 集的交集，记为 $\mathcal{E}_\infty$。

对于线性系统，mRPI 集可以用**集合迭代**方法近似计算：

$$\mathcal{E}_\infty \approx \bigoplus_{k=0}^{N_{term}} (A+BK)^k \mathcal{W}$$

其中 $\bigoplus$ 是 Minkowski 和：$A \oplus B = \{a + b \mid a \in A, b \in B\}$。

### 1.4 多面体集合的 Minkowski 运算

```cpp
// polytope.hpp
#pragma once
#include <Eigen/Dense>
#include <vector>
#include <algorithm>

// ============================================================
// 多面体（Polytope）：{x | H*x <= h}
// ============================================================
struct Polytope {
    Eigen::MatrixXd H;  // 约束矩阵 (m × n)
    Eigen::VectorXd h;  // 约束右端 (m)

    int n_constraints() const { return H.rows(); }
    int n_dims()        const { return H.cols(); }

    // 判断点 x 是否在集合内
    bool contains(const Eigen::VectorXd& x, double tol = 1e-8) const {
        return ((H * x).array() <= h.array() + tol).all();
    }

    // 支撑函数 h_P(d) = max_{x in P} d^T x
    // 对于多面体，等价于求解线性规划
    // 简化版本：对于盒型约束（H = [I; -I]），有解析解
    double supportFunction(const Eigen::VectorXd& d) const {
        // 一般情况需要 LP，这里给出盒型约束的解析版本
        // 盒型：-h_lo <= x <= h_up，即 H = [I; -I], h = [h_up; h_lo]
        int n = d.size();
        double val = 0.0;
        for (int i = 0; i < n; ++i) {
            double h_pos = h(i);        // x_i <= h_pos
            double h_neg = h(n + i);    // -x_i <= h_neg，即 x_i >= -h_neg
            val += (d(i) >= 0) ? d(i) * h_pos : -d(i) * h_neg;
        }
        return val;
    }
};

// ============================================================
// 盒型集合：{x | |x_i| <= b_i}  （最常用的 W 的形式）
// ============================================================
struct BoxSet {
    Eigen::VectorXd bounds;  // 每个维度的界 b_i（对称）

    // 转为多面体
    Polytope toPolytope() const {
        int n = bounds.size();
        Polytope P;
        P.H.resize(2 * n, n);
        P.h.resize(2 * n);
        P.H.topRows(n)    =  Eigen::MatrixXd::Identity(n, n);
        P.H.bottomRows(n) = -Eigen::MatrixXd::Identity(n, n);
        P.h.head(n)       =  bounds;
        P.h.tail(n)       =  bounds;
        return P;
    }

    // 线性变换：A * BoxSet
    BoxSet transform(const Eigen::MatrixXd& A) const {
        // 结果的每个维度界 = sum_j |A_{ij}| * bounds_j
        BoxSet result;
        result.bounds = (A.cwiseAbs() * bounds).eval();
        return result;
    }

    // Minkowski 和：BoxSet ⊕ BoxSet
    BoxSet minkowskiSum(const BoxSet& other) const {
        return BoxSet{bounds + other.bounds};
    }

    // 检验点是否在集合内
    bool contains(const Eigen::VectorXd& x) const {
        return (x.cwiseAbs().array() <= bounds.array() + 1e-8).all();
    }
};

// ============================================================
// 计算最小鲁棒正不变集（mRPI）的近似
//
// mRPI ≈ ⊕_{k=0}^{N} (A+BK)^k * W
//
// 采用盒型近似（实际 mRPI 可能不是盒型，但盒型是充分保守的外近似）
//
// 参数：
//   Acl = A + B*K（闭环系统矩阵，必须稳定：谱半径 < 1）
//   W   = 扰动集合（盒型）
//   tol = 迭代收敛容差
// ============================================================
BoxSet computeApproxMRPI(const Eigen::MatrixXd& Acl,
                          const BoxSet& W,
                          double tol = 1e-4,
                          int max_iter = 200)
{
    int n = Acl.rows();

    // 验证闭环稳定性
    Eigen::EigenSolver<Eigen::MatrixXd> eig(Acl);
    double rho = 0.0;
    for (int i = 0; i < n; ++i)
        rho = std::max(rho, std::abs(eig.eigenvalues()(i)));

    if (rho >= 1.0)
        throw std::runtime_error("Acl 不稳定（谱半径 >= 1），无法计算 mRPI");

    std::cout << "闭环谱半径 ρ = " << rho << "\n";

    BoxSet E     = W;       // 初始：E_0 = W（即 (Acl)^0 * W = W）
    BoxSet E_sum = W;       // 累积 Minkowski 和

    Eigen::MatrixXd Acl_pow = Acl;  // Acl^k

    for (int k = 1; k < max_iter; ++k) {
        // 计算 Acl^k * W
        BoxSet term = W;
        term.bounds = (Acl_pow.cwiseAbs() * W.bounds).eval();

        // 累积 Minkowski 和
        BoxSet E_new = E_sum.minkowskiSum(term);

        // 收敛检查：新增项是否已经可以忽略
        double increment = (E_new.bounds - E_sum.bounds).norm();
        E_sum = E_new;
        Acl_pow = Acl * Acl_pow;

        if (increment < tol) {
            std::cout << "mRPI 近似在 " << k << " 次迭代后收敛\n";
            break;
        }
    }

    // 添加少量裕量（确保正不变性）
    E_sum.bounds *= 1.05;
    return E_sum;
}

// ============================================================
// 约束域收紧：X ⊖ E（Pontryagin 差）
// 对于盒型集合：X = {x | |x_i| <= x_max_i}
//               E = {x | |x_i| <= e_i}
//               X ⊖ E = {x | |x_i| <= x_max_i - e_i}
// ============================================================
Polytope tightenConstraints(const BoxSet& X_box,
                              const BoxSet& E)
{
    int n = X_box.bounds.size();
    BoxSet X_tight;
    X_tight.bounds = X_box.bounds - E.bounds;

    for (int i = 0; i < n; ++i) {
        if (X_tight.bounds(i) <= 0)
            throw std::runtime_error(
                "收紧后的约束集为空！扰动过大或约束过紧。");
    }
    return X_tight.toPolytope();
}
```

### 1.5 Tube MPC 完整实现

```cpp
// tube_mpc.hpp
#pragma once
#include "polytope.hpp"
#include "mpc_types.hpp"
#include "osqp_solver.hpp"

// ============================================================
// Tube MPC 控制器
//
// 结构：
//   1. 辅助控制律：u_aux = K * (x - x̄)（误差反馈，抑制扰动）
//   2. MPC 控制律：u_mpc = v*（最优标称控制，在收紧约束上优化）
//   3. 实际控制：u = u_mpc + u_aux = v* + K*(x - x̄)
//
// 保证：
//   - 标称轨迹 x̄ 满足收紧约束 X ⊖ E
//   - 真实状态 x 始终在 x̄ ± E 的管道内
//   - 真实状态满足原始约束 X（硬保证）
// ============================================================
class TubeMPC {
public:
    struct TubeConfig {
        // LQR 辅助增益（用于误差反馈）
        Eigen::MatrixXd K;     // m × n

        // Tube 相关
        BoxSet W_disturbance;  // 扰动集合
        BoxSet X_state_box;    // 原始状态约束（盒型）
        BoxSet U_ctrl_box;     // 控制量约束（盒型）

        // MPC 基础配置
        MPCConfig   mpc_cfg;
        MPCWeights  weights;
        OSQPMPCSolver::SolverConfig solver_cfg;
    };

    TubeMPC(const DiscreteLinearSystem& sys,
             const TubeConfig& tube_cfg)
        : sys_(sys), K_(tube_cfg.K)
    {
        // 1. 计算闭环矩阵 Acl = A + B*K
        Acl_ = sys_.A + sys_.B * K_;

        std::cout << "=== Tube MPC 初始化 ===\n";

        // 2. 计算近似 mRPI 集 E
        E_ = computeApproxMRPI(Acl_, tube_cfg.W_disturbance);
        std::cout << "mRPI 集界（每维）: "
                  << E_.bounds.transpose() << "\n";

        // 3. 收紧状态约束：X_tight = X ⊖ E
        X_tight_ = tightenConstraints(tube_cfg.X_state_box, E_);
        std::cout << "收紧后状态约束界: "
                  << (tube_cfg.X_state_box.bounds - E_.bounds).transpose() << "\n";

        // 4. 收紧控制约束：U_tight = U ⊖ K*E
        // K*E 的界：对每个控制维度 i，界 = sum_j |K_{ij}| * E_j
        BoxSet KE;
        KE.bounds = (K_.cwiseAbs() * E_.bounds).eval();
        BoxSet U_tight_box;
        U_tight_box.bounds = tube_cfg.U_ctrl_box.bounds - KE.bounds;
        std::cout << "收紧后控制约束界: "
                  << U_tight_box.bounds.transpose() << "\n";

        // 5. 构建标称 MPC（在收紧约束上优化）
        MPCBounds tight_bounds;
        tight_bounds.u_min = -U_tight_box.bounds;
        tight_bounds.u_max =  U_tight_box.bounds;
        // 状态约束通过 X_tight_ 施加

        nominal_mpc_ = std::make_unique<OSQPMPCSolver>(
            sys_, tube_cfg.weights, tight_bounds,
            tube_cfg.mpc_cfg, tube_cfg.solver_cfg);

        std::cout << "=== Tube MPC 初始化完成 ===\n\n";
    }

    struct TubeResult {
        Eigen::VectorXd u_actual;    // 实际施加的控制量
        Eigen::VectorXd u_nominal;   // 标称 MPC 控制量
        Eigen::VectorXd u_auxiliary; // 辅助误差反馈控制量
        Eigen::VectorXd x_nominal;   // 当前标称状态
        double tube_radius;          // 当前误差范数（应 <= E 范数）
        bool   in_tube;              // 真实状态是否在管道内
    };

    TubeResult solve(const Eigen::VectorXd& x_actual,  // 真实（测量）状态
                      const Eigen::VectorXd& X_ref,     // 参考轨迹（标称用）
                      const Eigen::VectorXd& u_prev_nominal)
    {
        TubeResult result;

        // 1. 标称 MPC：用标称状态 x̄ 求解（收紧约束）
        auto mpc_result = nominal_mpc_->solve(x_nominal_, X_ref, u_prev_nominal);
        result.u_nominal = mpc_result.u_opt;

        // 2. 辅助控制律：u_aux = K * (x - x̄)
        Eigen::VectorXd error   = x_actual - x_nominal_;
        result.u_auxiliary = K_ * error;

        // 3. 实际控制量
        result.u_actual  = result.u_nominal + result.u_auxiliary;

        // 4. 更新标称状态（用标称系统方程，无扰动）
        // x̄_{k+1} = A * x̄_k + B * v*（不加扰动）
        x_nominal_ = sys_.A * x_nominal_ + sys_.B * result.u_nominal;

        // 5. 验证 Tube 属性
        result.x_nominal   = x_nominal_;
        result.tube_radius  = error.norm();
        result.in_tube      = E_.contains(error);

        if (!result.in_tube) {
            fprintf(stderr,
                "[TubeMPC] 警告：真实状态脱离管道！error_norm=%.4f, "
                "E_bound=%.4f\n",
                result.tube_radius, E_.bounds.minCoeff());
        }

        return result;
    }

    // 初始化标称状态（应使 x_actual 在初始 Tube 内）
    void initNominalState(const Eigen::VectorXd& x_nominal_init) {
        x_nominal_ = x_nominal_init;
    }

    const BoxSet& getTubeSet() const { return E_; }

private:
    DiscreteLinearSystem sys_;
    Eigen::MatrixXd      K_;      // 辅助反馈增益
    Eigen::MatrixXd      Acl_;    // 闭环矩阵 A + B*K
    BoxSet               E_;      // mRPI 集（Tube 的截面）
    Polytope             X_tight_; // 收紧后的状态约束

    std::unique_ptr<OSQPMPCSolver> nominal_mpc_;
    Eigen::VectorXd x_nominal_;   // 标称状态（内部维护）
};
```

### 1.6 仿真：验证 Tube MPC 的约束保证

```cpp
// tube_mpc_simulation.cpp
int main() {
    // 系统：一维小车（加入随机扰动）
    double Ts = 0.1;
    DiscreteLinearSystem sys;
    sys.n = 2; sys.m = 1; sys.p = 1;
    sys.A << 1, Ts,  0, 1;
    sys.B << 0.5*Ts*Ts, Ts;
    sys.C << 1, 0;

    // 辅助 LQR 增益（用于误差反馈）
    Eigen::MatrixXd Q_lqr(2,2); Q_lqr << 1, 0, 0, 1;
    Eigen::MatrixXd R_lqr(1,1); R_lqr << 0.5;
    auto [Qf_lqr, K] = computeLQRGain(sys.A, sys.B, Q_lqr, R_lqr);
    // K 的形状：(1 × 2)

    // 扰动幅度（已知上界）
    BoxSet W;
    W.bounds = Eigen::Vector2d(0.01, 0.05);  // 位置扰动 1cm，速度扰动 5cm/s

    // 原始状态约束
    BoxSet X_box;
    X_box.bounds = Eigen::Vector2d(2.0, 3.0);  // 位置 ±2m，速度 ±3m/s

    // 控制约束
    BoxSet U_box;
    U_box.bounds = Eigen::Vector1d(5.0);  // 力 ±5N

    // Tube MPC 配置
    TubeMPC::TubeConfig tube_cfg;
    tube_cfg.K              = K;
    tube_cfg.W_disturbance  = W;
    tube_cfg.X_state_box    = X_box;
    tube_cfg.U_ctrl_box     = U_box;
    tube_cfg.mpc_cfg.N      = 15;
    tube_cfg.mpc_cfg.Ts     = Ts;
    tube_cfg.weights.Q  << 50, 0,  0, 1;
    tube_cfg.weights.Qf << 50, 0,  0, 1;
    tube_cfg.weights.R  << 0.1;

    TubeMPC controller(sys, tube_cfg);

    // 初始状态
    Eigen::VectorXd x(2);  x << 0.0, 0.0;
    controller.initNominalState(x);

    Eigen::VectorXd x_ref(2);  x_ref << 1.5, 0.0;
    Eigen::VectorXd X_ref(tube_cfg.mpc_cfg.N * 2);
    for (int k = 0; k < tube_cfg.mpc_cfg.N; ++k)
        X_ref.segment(k*2, 2) = x_ref;
    Eigen::VectorXd u_prev_nom = Eigen::VectorXd::Zero(1);

    // 随机数生成器（模拟有界扰动）
    std::mt19937 rng(42);
    std::uniform_real_distribution<double> dist_pos(-0.01, 0.01);
    std::uniform_real_distribution<double> dist_vel(-0.05, 0.05);

    bool constraint_violated = false;
    int  tube_violation_count = 0;

    std::cout << "步骤  位置(m)  速度(m/s) | 约束(±2m)  | 在管道内 | u实际(N)\n";
    std::cout << std::string(70, '-') << "\n";

    for (int step = 0; step < 150; ++step) {
        double t = step * Ts;

        auto result = controller.solve(x, X_ref, u_prev_nom);

        // 检查原始约束
        bool pos_ok = std::abs(x(0)) <= 2.0 + 1e-6;
        bool vel_ok = std::abs(x(1)) <= 3.0 + 1e-6;
        if (!pos_ok || !vel_ok) {
            constraint_violated = true;
            fprintf(stderr, "!!! 约束违反！t=%.2f，x=[%.4f, %.4f]\n",
                    t, x(0), x(1));
        }
        if (!result.in_tube) ++tube_violation_count;

        if (step % 5 == 0) {
            std::cout << std::setw(4) << step
                      << std::setw(8) << x(0)
                      << std::setw(10) << x(1) << "  |"
                      << std::setw(6)  << (pos_ok ? " OK" : "VIOL") << "  |"
                      << std::setw(8)  << (result.in_tube ? " ✓" : " ✗") << "  |"
                      << std::setw(8)  << result.u_actual(0) << "\n";
        }

        // 真实系统演化（含有界扰动）
        Eigen::VectorXd w(2);
        w << dist_pos(rng), dist_vel(rng);
        x = sys.A * x + sys.B * result.u_actual + w;

        u_prev_nom = result.u_nominal;
    }

    std::cout << "\n=== Tube MPC 仿真总结 ===\n";
    std::cout << "硬约束违反：" << (constraint_violated ? "是（BUG！）" : "否（✓ 保证满足）") << "\n";
    std::cout << "管道溢出次数：" << tube_violation_count << "（0 则理论保证成立）\n";
}
```

---

## 二、随机 MPC：概率约束下的期望最优

### 2.1 为什么需要随机 MPC

Tube MPC 对扰动做最坏情况假设（有界集合），因此收紧约束往往非常保守——真实约束裕量远大于必要值，控制性能下降。

当扰动服从**概率分布**（如高斯分布）时，可以更精细地处理：
- 不要求约束**永远**满足（过于保守）
- 只要求约束以**高概率**（如 99%）满足

这就是**随机 MPC（Stochastic MPC）**，也称**机会约束 MPC（Chance-Constrained MPC）**。

### 2.2 机会约束的定义

对于约束 $c^T x_k \leq d$（单个约束）：

$$\text{Prob}(c^T x_k \leq d) \geq 1 - \epsilon$$

其中 $\epsilon \in (0, 1)$ 是允许的违反概率（如 $\epsilon = 0.01$ 表示 99% 满足）。

### 2.3 高斯扰动下的解析化

若 $w_k \sim \mathcal{N}(0, \Sigma_w)$，则经过 $k$ 步传播后，状态的不确定性：

$$x_k = \underbrace{A^k x_0 + \sum_{j=0}^{k-1} A^{k-1-j}Bu_j}_{\text{确定性部分} \bar{x}_k} + \underbrace{\sum_{j=0}^{k-1} A^{k-1-j} w_j}_{\text{随机部分} \xi_k}$$

随机部分的协方差：

$$\Sigma_k = A \Sigma_{k-1} A^T + \Sigma_w, \quad \Sigma_0 = \Sigma_{x_0}$$

对于线性约束 $c^T x_k \leq d$，随机部分 $c^T \xi_k \sim \mathcal{N}(0, c^T \Sigma_k c)$，机会约束等价为：

$$c^T \bar{x}_k \leq d - \Phi^{-1}(1-\epsilon) \cdot \sqrt{c^T \Sigma_k c}$$

其中 $\Phi^{-1}$ 是标准正态分布的分位数函数（如 $\epsilon=0.01$ 时 $\Phi^{-1}(0.99) \approx 2.326$）。

**结论**：概率约束转化为**收紧确定性约束**，收紧量与不确定性大小（$\sqrt{c^T \Sigma_k c}$）和置信水平（$\Phi^{-1}(1-\epsilon)$）成正比。

```cpp
// stochastic_mpc.hpp
#pragma once
#include <Eigen/Dense>
#include <cmath>
#include <vector>

// ============================================================
// 高斯随机 MPC
//
// 扰动模型：w_k ~ N(0, Sigma_w)
// 机会约束：Prob(c_i^T x_k <= d_i) >= 1 - epsilon_i
// 转化为确定性收紧约束：c_i^T x̄_k <= d_i - Φ^{-1}(1-ε_i) * σ_{i,k}
//   其中 σ_{i,k} = sqrt(c_i^T Σ_k c_i)
// ============================================================

// 标准正态分布逆 CDF（近似，最大误差约 0.001）
// 精确实现需要特殊函数库（如 boost::math）
double normalInvCDF(double p) {
    // Beasley-Springer-Moro 近似
    if (p <= 0.0 || p >= 1.0)
        throw std::domain_error("p 必须在 (0, 1) 内");

    static const double a[] = {
        2.50662823884, -18.61500062529, 41.39119773534, -25.44106049637};
    static const double b[] = {
        -8.47351093090, 23.08336743743, -21.06224101826, 3.13082909833};
    static const double c[] = {
        0.3374754822726147, 0.9761690190917186, 0.1607979714918209,
        0.0276438810333863, 0.0038405729373609, 0.0003951896511349,
        0.0000321767881768, 0.0000002888167364, 0.0000003960315187};

    double q = p - 0.5;
    double r, x;

    if (std::abs(q) <= 0.42) {
        r = q * q;
        x = q * (((a[3]*r + a[2])*r + a[1])*r + a[0]) /
              ((((b[3]*r + b[2])*r + b[1])*r + b[0])*r + 1.0);
    } else {
        r = (q < 0) ? p : 1.0 - p;
        r = std::log(-std::log(r));
        x = c[0] + r*(c[1] + r*(c[2] + r*(c[3] + r*(
            c[4] + r*(c[5] + r*(c[6] + r*(c[7] + r*c[8])))))));
        if (q < 0) x = -x;
    }
    return x;
}

// 随机约束（单个）
struct ChanceConstraint {
    Eigen::VectorXd c;    // 约束方向向量
    double d;             // 约束右端
    double epsilon;       // 允许违反概率（如 0.01 对应 99% 满足）
};

// ============================================================
// 不确定性协方差传播
// 给定初始协方差 Sigma_0 和过程噪声 Sigma_w，
// 计算每一步的状态协方差 Sigma_k（k = 0, ..., N）
// ============================================================
std::vector<Eigen::MatrixXd> propagateCovariance(
    const Eigen::MatrixXd& A,
    const Eigen::MatrixXd& Sigma_0,  // 初始状态不确定性
    const Eigen::MatrixXd& Sigma_w,  // 过程噪声协方差
    int N)
{
    std::vector<Eigen::MatrixXd> Sigmas(N + 1);
    Sigmas[0] = Sigma_0;
    for (int k = 0; k < N; ++k) {
        Sigmas[k+1] = A * Sigmas[k] * A.transpose() + Sigma_w;
        // 保证对称性
        Sigmas[k+1] = 0.5 * (Sigmas[k+1] + Sigmas[k+1].transpose());
    }
    return Sigmas;
}

// ============================================================
// 将机会约束转化为收紧的确定性约束
//
// 返回：每步 k 的收紧约束 c^T x̄_k <= d_tight_k
// ============================================================
struct TightenedConstraint {
    Eigen::VectorXd c;
    std::vector<double> d_tight;  // 每步收紧后的右端（长度 N）
};

TightenedConstraint tightenChanceConstraint(
    const ChanceConstraint& cc,
    const std::vector<Eigen::MatrixXd>& Sigmas)
{
    TightenedConstraint tc;
    tc.c = cc.c;
    int N = Sigmas.size() - 1;
    tc.d_tight.resize(N);

    double z_alpha = normalInvCDF(1.0 - cc.epsilon);

    for (int k = 0; k < N; ++k) {
        // 约束方向的不确定性（标准差）
        double sigma_k = std::sqrt(
            std::max(0.0, cc.c.transpose() * Sigmas[k+1] * cc.c));
        // 收紧量
        tc.d_tight[k] = cc.d - z_alpha * sigma_k;
    }
    return tc;
}

// ============================================================
// 随机 MPC 求解器
// ============================================================
class StochasticMPC {
public:
    struct Config {
        DiscreteLinearSystem sys;
        MPCConfig   mpc_cfg;
        MPCWeights  weights;

        // 噪声参数
        Eigen::MatrixXd Sigma_w;    // 过程噪声协方差
        Eigen::MatrixXd Sigma_x0;   // 初始状态不确定性

        // 机会约束
        std::vector<ChanceConstraint> chance_constraints;

        // 确定性约束（控制量）
        Eigen::VectorXd u_min, u_max;
    };

    StochasticMPC(const Config& cfg) : cfg_(cfg) {}

    MPCResult solve(const Eigen::VectorXd& x0_mean,
                    const Eigen::MatrixXd& x0_cov,   // 当前状态分布
                    const Eigen::VectorXd& X_ref)
    {
        int N  = cfg_.mpc_cfg.N;
        int n  = cfg_.sys.n;
        int m  = cfg_.sys.m;

        // 1. 传播协方差（不依赖控制量，只依赖 A 矩阵）
        auto Sigmas = propagateCovariance(
            cfg_.sys.A, x0_cov, cfg_.Sigma_w, N);

        // 2. 收紧机会约束
        std::vector<TightenedConstraint> tc_list;
        for (const auto& cc : cfg_.chance_constraints) {
            tc_list.push_back(tightenChanceConstraint(cc, Sigmas));
        }

        // 打印收紧量（调试用）
        if (!tc_list.empty()) {
            std::cout << "机会约束收紧量（前3步）：\n";
            int n_print = std::min(3, N);
            for (const auto& tc : tc_list) {
                for (int k = 0; k < n_print; ++k)
                    std::cout << "  k=" << k+1
                              << ": d_tight=" << tc.d_tight[k] << "\n";
            }
        }

        // 3. 构建 MPC QP（将收紧约束加入）
        // 这里使用第三篇的 buildPredictionMatrices + buildQP
        auto pred = buildPredictionMatrices(cfg_.sys, cfg_.weights, N);

        // 4. 将收紧的状态约束转化为控制量约束（通过预测方程）
        // 每个收紧约束：c_i^T * (calA*x0 + calB*U)_k <= d_tight_{i,k}
        // 即：(c_i^T * calB_k) * U <= d_tight_{i,k} - c_i^T * calA_k * x0

        int n_tc_cons = 0;
        for (const auto& tc : tc_list) n_tc_cons += N;

        Eigen::MatrixXd G_tc = Eigen::MatrixXd::Zero(n_tc_cons, N * m);
        Eigen::VectorXd h_tc(n_tc_cons);

        int row = 0;
        for (const auto& tc : tc_list) {
            for (int k = 0; k < N; ++k) {
                // calB 的第 k 块行：(n × Nm)
                Eigen::MatrixXd calBk = pred.calB.block(k*n, 0, n, N*m);
                // calA 的第 k 块行：(n × n) * x0
                Eigen::VectorXd calAk_x0 = pred.calA.block(k*n, 0, n, n) * x0_mean;

                G_tc.row(row) = tc.c.transpose() * calBk;
                h_tc(row)     = tc.d_tight[k] - tc.c.dot(calAk_x0);
                ++row;
            }
        }

        // 5. 合并所有约束，求解 QP
        Eigen::VectorXd e0 = pred.calA * x0_mean - X_ref;
        Eigen::MatrixXd H = 2.0*(pred.calB.transpose()*pred.barQ*pred.calB
                                  + pred.barR);
        Eigen::VectorXd f = 2.0 * pred.calB.transpose() * pred.barQ * e0;
        H += 1e-8 * Eigen::MatrixXd::Identity(N*m, N*m);

        // 控制量盒型约束
        int n_u_con = 2 * N * m;
        Eigen::MatrixXd G_u(n_u_con, N * m);
        Eigen::VectorXd h_u(n_u_con);
        G_u.topRows(N*m)    =  Eigen::MatrixXd::Identity(N*m, N*m);
        G_u.bottomRows(N*m) = -Eigen::MatrixXd::Identity(N*m, N*m);
        for (int k = 0; k < N; ++k) {
            h_u.segment(k*m, m)       = cfg_.u_max;
            h_u.segment(N*m + k*m, m) = -cfg_.u_min;
        }

        // 合并
        int n_total = n_u_con + n_tc_cons;
        Eigen::MatrixXd G(n_total, N*m);
        Eigen::VectorXd h(n_total);
        G.topRows(n_u_con)    = G_u;    h.head(n_u_con) = h_u;
        G.bottomRows(n_tc_cons) = G_tc; h.tail(n_tc_cons) = h_tc;

        // 无约束解 + 饱和（简化版，实际接 OSQP）
        Eigen::LDLT<Eigen::MatrixXd> ldlt(H);
        Eigen::VectorXd U_opt = -ldlt.solve(f);

        // 投影到控制量约束
        for (int k = 0; k < N; ++k) {
            for (int i = 0; i < m; ++i) {
                U_opt(k*m+i) = std::max(cfg_.u_min(i),
                               std::min(cfg_.u_max(i), U_opt(k*m+i)));
            }
        }

        MPCResult result;
        result.solved     = true;
        result.u_opt      = U_opt.head(m);
        result.U_sequence = U_opt;
        result.cost       = 0.5*U_opt.dot(H*U_opt) + f.dot(U_opt);
        return result;
    }

private:
    Config cfg_;
};
```

---

## 三、Learning-based MPC：用数据修正模型误差

### 3.1 问题背景

无论线性化还是物理建模，模型都有误差：

$$x_{k+1} = f_{model}(x_k, u_k) + \underbrace{\delta(x_k, u_k)}_{\text{未建模误差}}$$

Learning-based MPC 的目标：**在线学习** $\delta$，然后将学到的误差补偿纳入 MPC 预测。

### 3.2 三种主流方法

| 方法 | 学习模型 | 在线/离线 | 数据效率 | 计算开销 |
|------|---------|---------|---------|---------|
| **高斯过程回归（GPR）** | 非参数贝叶斯 | 两者 | 高 | 高（$O(n^3)$） |
| **神经网络残差模型** | 深度学习 | 离线为主 | 低 | 中（GPU） |
| **在线线性回归（RLS）** | 参数线性 | 在线 | 低 | **极低** |

工业嵌入式系统首选 **RLS**，研究场合常用 **GPR**。

### 3.3 方法一：基于高斯过程的 Learning MPC

```cpp
// gaussian_process.hpp
#pragma once
#include <Eigen/Dense>
#include <vector>
#include <functional>

// ============================================================
// 简化高斯过程回归（GPR）
//
// 训练数据：{(z_i, y_i)}，z_i 为输入特征，y_i 为残差输出
// 核函数：平方指数（RBF）核 k(z, z') = σ²_f * exp(-||z-z'||²/(2l²))
// 预测：均值 μ*(z) 和方差 σ²*(z)（不确定性估计）
// ============================================================
class GaussianProcess {
public:
    struct Params {
        double sigma_f = 1.0;   // 信号方差（输出尺度）
        double length  = 1.0;   // 特征长度尺度
        double sigma_n = 0.1;   // 观测噪声标准差
        int    max_data = 200;  // 最大存储数据量（滑动窗口）
    };

    explicit GaussianProcess(const Params& p) : p_(p) {}

    // 核函数（RBF）
    double kernel(const Eigen::VectorXd& z1,
                   const Eigen::VectorXd& z2) const {
        double sq_dist = (z1 - z2).squaredNorm();
        return p_.sigma_f * p_.sigma_f *
               std::exp(-sq_dist / (2.0 * p_.length * p_.length));
    }

    // 添加新训练点
    void addData(const Eigen::VectorXd& z, double y) {
        Z_.push_back(z);
        Y_.push_back(y);

        // 滑动窗口：超过最大数据量时删除最旧的
        if ((int)Z_.size() > p_.max_data) {
            Z_.erase(Z_.begin());
            Y_.erase(Y_.begin());
            K_inv_dirty_ = true;
        }
        K_inv_dirty_ = true;
    }

    // 更新核矩阵逆（添加数据后调用）
    void updateKernelMatrix() {
        if (!K_inv_dirty_ || Z_.empty()) return;

        int n = Z_.size();
        Eigen::MatrixXd K(n, n);
        for (int i = 0; i < n; ++i)
            for (int j = 0; j < n; ++j)
                K(i,j) = kernel(Z_[i], Z_[j]);

        // 添加噪声方差到对角（正则化）
        K += (p_.sigma_n*p_.sigma_n + 1e-6) *
              Eigen::MatrixXd::Identity(n, n);

        K_inv_ = K.ldlt().solve(Eigen::MatrixXd::Identity(n, n));
        K_inv_dirty_ = false;
    }

    // 预测：返回 {均值, 方差}
    std::pair<double, double> predict(const Eigen::VectorXd& z_star) {
        if (Z_.empty()) return {0.0, p_.sigma_f * p_.sigma_f};

        updateKernelMatrix();

        int n = Z_.size();

        // k*(z_star) = [k(z_star, z_1), ..., k(z_star, z_n)]
        Eigen::VectorXd k_star(n);
        for (int i = 0; i < n; ++i)
            k_star(i) = kernel(z_star, Z_[i]);

        // 目标值向量
        Eigen::VectorXd y_vec = Eigen::Map<Eigen::VectorXd>(
            Y_.data(), Y_.size());

        // 均值：μ* = k*^T * K^{-1} * y
        double mu = k_star.dot(K_inv_ * y_vec);

        // 方差：σ²* = k** - k*^T * K^{-1} * k*
        double k_ss = kernel(z_star, z_star);
        double var  = std::max(0.0, k_ss - k_star.dot(K_inv_ * k_star));

        return {mu, var};
    }

    int dataSize() const { return Z_.size(); }
    bool hasSufficientData(int min_n = 10) const {
        return (int)Z_.size() >= min_n;
    }

private:
    Params p_;
    std::vector<Eigen::VectorXd> Z_;  // 输入特征
    std::vector<double>          Y_;  // 输出（残差）
    Eigen::MatrixXd              K_inv_;
    bool K_inv_dirty_ = true;
};

// ============================================================
// 多维高斯过程（对状态每个维度独立训练一个 GP）
// ============================================================
class MultiOutputGP {
public:
    MultiOutputGP(int output_dim, const GaussianProcess::Params& p)
        : gps_(output_dim, GaussianProcess(p)) {}

    void addData(const Eigen::VectorXd& z, const Eigen::VectorXd& y) {
        for (int i = 0; i < (int)gps_.size(); ++i)
            gps_[i].addData(z, y(i));
    }

    // 返回：均值向量 μ 和方差向量 σ²
    std::pair<Eigen::VectorXd, Eigen::VectorXd>
    predict(const Eigen::VectorXd& z_star) {
        int d = gps_.size();
        Eigen::VectorXd mu(d), var(d);
        for (int i = 0; i < d; ++i) {
            auto [m, v] = gps_[i].predict(z_star);
            mu(i) = m;
            var(i) = v;
        }
        return {mu, var};
    }

    bool hasSufficientData(int min_n = 10) const {
        return !gps_.empty() && gps_[0].hasSufficientData(min_n);
    }

private:
    std::vector<GaussianProcess> gps_;
};
```

### 3.4 方法二：递归最小二乘（RLS）在线学习

```cpp
// rls_learner.hpp
#pragma once
#include <Eigen/Dense>

// ============================================================
// 递归最小二乘（RLS）在线参数估计
//
// 假设残差为线性参数化模型：
//   δ(x, u) = Φ(x, u) * θ
//
// Φ(x, u) 是特征向量（基函数），θ 是待估计参数
// 例：Φ = [1, x(0), x(1), u(0), x(0)^2, ...]（多项式或 RBF 特征）
//
// RLS 递推：
//   P_{k+1} = (P_k - P_k φ φ^T P_k / (λ + φ^T P_k φ)) / λ
//   θ_{k+1} = θ_k + P_{k+1} φ (y - φ^T θ_k)
//   λ ∈ (0, 1]：遗忘因子（<1 时对新数据更敏感，适应时变系统）
// ============================================================
class RLSLearner {
public:
    struct Config {
        int    feature_dim = 10;  // 特征维数
        int    output_dim  =  2;  // 输出维数（状态维数）
        double lambda      = 0.98; // 遗忘因子（0.95~0.999）
        double P_init      = 100.0; // 初始协方差（信任先验程度的倒数）
    };

    explicit RLSLearner(const Config& cfg) : cfg_(cfg) {
        theta_ = Eigen::MatrixXd::Zero(cfg_.feature_dim, cfg_.output_dim);
        P_     = cfg_.P_init * Eigen::MatrixXd::Identity(
                     cfg_.feature_dim, cfg_.feature_dim);
    }

    // 更新（给定特征向量 φ 和观测残差 y_actual - y_predicted）
    void update(const Eigen::VectorXd& phi,  // 特征向量 (feature_dim)
                const Eigen::VectorXd& residual)  // 实测残差 (output_dim)
    {
        // 增益向量
        Eigen::VectorXd Pphi = P_ * phi;
        double denom = cfg_.lambda + phi.dot(Pphi);

        if (std::abs(denom) < 1e-10) return;  // 数值保护

        Eigen::VectorXd K = Pphi / denom;

        // 协方差更新：P = (P - K φ^T P) / λ
        P_ = (P_ - K * phi.transpose() * P_) / cfg_.lambda;
        // 保证对称
        P_ = 0.5 * (P_ + P_.transpose());

        // 参数更新：θ = θ + K * (y - φ^T θ)
        Eigen::VectorXd y_pred = theta_.transpose() * phi;
        theta_ += K * (residual - y_pred).transpose();
    }

    // 预测残差
    Eigen::VectorXd predict(const Eigen::VectorXd& phi) const {
        return theta_.transpose() * phi;
    }

    // 获取当前参数的不确定性（协方差矩阵的迹）
    double uncertainty() const { return P_.trace(); }

    const Eigen::MatrixXd& parameters() const { return theta_; }
    const Eigen::MatrixXd& covariance()  const { return P_; }

private:
    Config          cfg_;
    Eigen::MatrixXd theta_;  // 参数矩阵 (feature_dim × output_dim)
    Eigen::MatrixXd P_;      // 协方差矩阵 (feature_dim × feature_dim)
};

// ============================================================
// 特征向量构建（多项式基函数）
// 输入：当前状态 x（n维）和控制量 u（m维）
// 输出：特征向量 φ（包含常数项、一次项、二次项）
// ============================================================
Eigen::VectorXd buildPolynomialFeatures(
    const Eigen::VectorXd& x,
    const Eigen::VectorXd& u,
    int degree = 2)
{
    int n = x.size(), m = u.size();
    Eigen::VectorXd z(n + m);  // 合并输入
    z.head(n) = x;
    z.tail(m) = u;

    std::vector<double> feats;
    feats.push_back(1.0);  // 常数项

    // 一次项
    for (int i = 0; i < z.size(); ++i) feats.push_back(z(i));

    // 二次项（仅 degree >= 2 时）
    if (degree >= 2) {
        for (int i = 0; i < z.size(); ++i)
            for (int j = i; j < z.size(); ++j)
                feats.push_back(z(i) * z(j));
    }

    return Eigen::Map<Eigen::VectorXd>(feats.data(), feats.size());
}
```

### 3.5 Learning MPC 完整框架

```cpp
// learning_mpc.hpp
#pragma once
#include "rls_learner.hpp"
#include "gaussian_process.hpp"
#include "osqp_solver.hpp"

// ============================================================
// Learning-based MPC 框架
//
// 流程（每个控制周期）：
//   1. 测量真实状态 x_meas
//   2. 计算残差：δ = x_meas - f_model(x_prev, u_prev)
//   3. 用 (φ(x_prev, u_prev), δ) 更新学习模型
//   4. 在 MPC 预测中使用修正模型：
//      x̂_{k+1} = f_model(x_k, u_k) + φ(x_k,u_k)^T θ
//   5. 求解 MPC，执行控制
// ============================================================
class LearningMPC {
public:
    enum class LearnerType { RLS, GP };

    struct Config {
        DiscreteLinearSystem sys;    // 名义线性模型
        MPCConfig   mpc_cfg;
        MPCWeights  weights;
        MPCBounds   bounds;
        OSQPMPCSolver::SolverConfig solver_cfg;

        LearnerType learner = LearnerType::RLS;
        int         min_data_before_correction = 20; // 数据少于此值不做修正
        double      max_correction_norm = 0.5;       // 修正量限幅（安全）
        int         feature_degree = 2;              // 多项式特征阶次
    };

    LearningMPC(const Config& cfg) : cfg_(cfg) {
        // 初始化基础 MPC
        base_mpc_ = std::make_unique<OSQPMPCSolver>(
            cfg_.sys, cfg_.weights, cfg_.bounds,
            cfg_.mpc_cfg, cfg_.solver_cfg);

        // 初始化学习器
        auto features_dim = buildPolynomialFeatures(
            Eigen::VectorXd::Zero(cfg_.sys.n),
            Eigen::VectorXd::Zero(cfg_.sys.m),
            cfg_.feature_degree).size();

        rls_cfg_.feature_dim = features_dim;
        rls_cfg_.output_dim  = cfg_.sys.n;
        rls_         = std::make_unique<RLSLearner>(rls_cfg_);

        gp_  = std::make_unique<MultiOutputGP>(
            cfg_.sys.n, GaussianProcess::Params{});

        u_prev_ = Eigen::VectorXd::Zero(cfg_.sys.m);
        x_prev_ = Eigen::VectorXd::Zero(cfg_.sys.n);
        initialized_ = false;
        data_count_  = 0;
    }

    struct LearningResult {
        MPCResult    mpc_result;
        Eigen::VectorXd residual;       // 当前步的模型残差
        Eigen::VectorXd correction;     // 预测修正量
        double       model_error_norm;  // 残差范数（模型精度指标）
        int          data_count;        // 已收集的训练数据量
    };

    LearningResult solve(const Eigen::VectorXd& x_meas,
                          const Eigen::VectorXd& X_ref)
    {
        LearningResult lr;
        lr.data_count = data_count_;

        if (initialized_) {
            // ── Step 1: 计算当前步的模型残差 ──
            // 名义模型预测：x̂ = A*x_prev + B*u_prev
            Eigen::VectorXd x_nominal_pred =
                cfg_.sys.A * x_prev_ + cfg_.sys.B * u_prev_;
            lr.residual = x_meas - x_nominal_pred;
            lr.model_error_norm = lr.residual.norm();

            // ── Step 2: 更新学习模型 ──
            Eigen::VectorXd phi = buildPolynomialFeatures(
                x_prev_, u_prev_, cfg_.feature_degree);

            if (cfg_.learner == LearnerType::RLS) {
                rls_->update(phi, lr.residual);
            } else {
                gp_->addData(phi, lr.residual);
            }
            ++data_count_;
        }

        // ── Step 3: 预测修正量（用学习模型） ──
        bool use_correction = (data_count_ >= cfg_.min_data_before_correction);
        lr.correction = Eigen::VectorXd::Zero(cfg_.sys.n);

        if (use_correction) {
            Eigen::VectorXd phi_now = buildPolynomialFeatures(
                x_meas, u_prev_, cfg_.feature_degree);

            if (cfg_.learner == LearnerType::RLS) {
                lr.correction = rls_->predict(phi_now);
            } else if (gp_->hasSufficientData()) {
                auto [mu, var] = gp_->predict(phi_now);
                lr.correction = mu;
                // 可选：根据方差判断是否信任修正量
                // 高方差（不确定性大）时减小修正权重
                double confidence = 1.0 / (1.0 + var.norm());
                lr.correction *= confidence;
            }

            // 限幅（安全保障：防止学习到的修正量过大导致失稳）
            double corr_norm = lr.correction.norm();
            if (corr_norm > cfg_.max_correction_norm) {
                lr.correction *= cfg_.max_correction_norm / corr_norm;
            }
        }

        // ── Step 4: 修正当前状态估计，用于 MPC ──
        // 思路：将已知的当前步残差加入状态，使 MPC 在正确基础上预测
        // x_corrected = x_meas + correction（修正的是"预测起点"）
        Eigen::VectorXd x_for_mpc = x_meas + lr.correction;

        // ── Step 5: 求解 MPC ──
        lr.mpc_result = base_mpc_->solve(x_for_mpc, X_ref, u_prev_);

        // ── Step 6: 记录状态（用于下一步残差计算）──
        x_prev_ = x_meas;
        u_prev_ = lr.mpc_result.u_opt;
        initialized_ = true;

        return lr;
    }

    // 获取学习进度
    double modelError() const {
        // 可以用最近 N 步残差的滑动平均来评估模型精度
        return rls_ ? rls_->uncertainty() : 0.0;
    }

    bool isLearningActive() const {
        return data_count_ >= cfg_.min_data_before_correction;
    }

private:
    Config          cfg_;
    RLSLearner::Config rls_cfg_;
    std::unique_ptr<OSQPMPCSolver> base_mpc_;
    std::unique_ptr<RLSLearner>    rls_;
    std::unique_ptr<MultiOutputGP> gp_;

    Eigen::VectorXd u_prev_, x_prev_;
    bool initialized_;
    int  data_count_;
};
```

---

## 四、实际落地案例分析

### 4.1 案例一：自动驾驶横向控制

```
系统层次：
┌─────────────────────────────────────────────────────────┐
│  感知层（100ms）：摄像头/激光雷达 → 车道线/障碍物         │
├─────────────────────────────────────────────────────────┤
│  规划层（200ms）：A* / RRT → 全局路径                    │
├─────────────────────────────────────────────────────────┤
│  预测层（100ms）：行人/车辆意图预测                       │
├─────────────────────────────────────────────────────────┤
│  决策层（50ms）：行为规划（跟车/变道/超车）               │
├─────────────────────────────────────────────────────────┤
│  → MPC 控制层（20ms，50Hz）←                            │
│    - 非线性 MPC（自行车模型）                             │
│    - 输入：当前位姿 + 参考轨迹                            │
│    - 输出：转向角 + 加速度                                │
│    - 约束：转向角±28°，加速度±3m/s²，侧向加速度±3m/s²   │
├─────────────────────────────────────────────────────────┤
│  执行层（1ms，1kHz）：EPS（电动助力转向）/ 线控制动       │
└─────────────────────────────────────────────────────────┘
```

**关键工程决策**：

```cpp
// 自动驾驶 MPC 的典型配置（实车参数）
struct ADASMPCConfig {
    // ── 时间参数 ──
    double Ts = 0.02;   // 50Hz（受感知延迟限制）
    int    N  = 20;     // 预测 0.4 秒（高速场景需更长）

    // ── 自行车模型参数 ──
    double L_wb     = 2.7;    // 轴距
    double L_f      = 1.2;    // 前轴到质心距离
    double L_r      = 1.5;    // 后轴到质心距离
    double v_min    = 0.0;
    double v_max    = 33.3;   // 120 km/h

    // ── 控制约束 ──
    double delta_max  = 0.49;  // 约 28° 转向角
    double ddelta_max = 0.1;   // 转向角变化率（每步）≈ 5°/step
    double a_min      = -5.0;  // 紧急制动
    double a_max      = 2.5;   // 最大驱动加速度

    // ── 权重（根据场景自适应）──
    // 高速直线段：更大的侧向权重
    // 弯道：更大的航向权重和前瞻时域
    double q_lat  = 20.0;
    double q_psi  = 15.0;
    double q_v    = 5.0;
    double r_delta = 50.0;   // 较大：转向平顺是乘坐舒适的关键
    double r_a    = 2.0;

    // ── 软约束（侧向加速度）──
    double ay_max       = 3.0;   // 最大侧向加速度（舒适性）
    double ay_soft_rho  = 1e3;   // 软约束惩罚权重

    // ── SLQ 迭代 ──
    int slq_iter = 2;  // 实时性限制，迭代次数少
};

// 侧向加速度约束（非线性，通过线性化近似处理）
// a_y = v²/R ≈ v * (v/L) * tan(δ) = v² * tan(δ) / L
// 在工作点线性化后加入 QP 约束
double computeLateralAccel(double v, double delta, double L) {
    return v * v * std::tan(delta) / L;
}
```

**延迟补偿**（自动驾驶的关键细节）：

```cpp
// MPC 感知延迟补偿
// 问题：从感知到控制执行存在约 100ms 延迟
// 方案：用动力学模型将当前状态向前预测延迟时间
Eigen::VectorXd compensateLatency(
    const Eigen::VectorXd& x_meas,  // 当前测量状态
    const Eigen::VectorXd& u_last,  // 上一步实际执行的控制量
    double latency,                  // 系统总延迟 (s)
    double dt,                       // 积分步长
    const BicycleModel& model)
{
    int steps = std::max(1, (int)std::round(latency / dt));
    Eigen::VectorXd x = x_meas;

    // 用上一步控制量向前积分 latency 时间
    for (int i = 0; i < steps; ++i)
        x = model.step(x, u_last, dt);

    return x;  // 延迟补偿后的状态（MPC 的实际出发点）
}
```

### 4.2 案例二：机器人关节力矩控制

```cpp
// 机械臂 MPC 的特殊考量
struct RobotArmMPCNotes {
    // ── 为什么用 MPC 而非 PD + 重力前馈 ──
    // 1. 关节耦合：MPC 可以协调所有关节同时优化
    // 2. 末端执行器约束：可以直接约束末端位置（通过前向运动学线性化）
    // 3. 关节扭矩限幅：执行器物理限制直接在 QP 中处理
    // 4. 关节速度限幅：避免突然的快速运动（安全）

    // ── 非线性处理策略 ──
    // 机械臂动力学：M(q)q̈ + C(q,q̇)q̇ + g(q) = τ
    // 这是高度非线性的（M, C, g 都是关节角的复杂函数）
    //
    // 实用方案：
    // 1. 在当前配置附近线性化（SLQ，每步 1~2 次）
    // 2. 使用计算力矩控制（CTC）+ MPC 的级联结构
    //    ↓ 外环 MPC：生成加速度参考 q̈_ref
    //    ↓ 内环 CTC：τ = M(q)*q̈_ref + C(q,q̇)q̇ + g(q)
    //    ↓ 内环将非线性消除，MPC 只处理线性双积分系统

    // ── 奇异性处理 ──
    // 关节接近奇异配置时，雅可比矩阵退化
    // 通过阻尼最小二乘（DLS）在奇异附近提供数值稳定性
};
```

### 4.3 案例三：工业过程控制（DMC / 阶跃响应模型）

工业 MPC（如 DMC, RMPCT, PCT）使用**阶跃响应系数**而非状态空间模型，这是针对从控制实践中学到的模型形式：

```cpp
// step_response_mpc.hpp
// 工业 MPC 使用的阶跃响应模型
//
// 思路：不建立物理方程，直接测量系统对阶跃输入的响应序列
// 响应序列 S = [s_1, s_2, ..., s_N]：
//   s_k = 在 t=0 施加单位阶跃后，t=k*Ts 时刻的输出增量

struct StepResponseModel {
    int    N;       // 响应截断长度（通常取到响应稳定的时刻）
    double Ts;
    std::vector<double> S;  // 阶跃响应系数

    // 从实验数据辨识阶跃响应（直接测量法）
    static StepResponseModel identify(
        const std::vector<double>& u_data,  // 阶跃输入序列
        const std::vector<double>& y_data,  // 实测输出序列
        double step_amplitude)
    {
        StepResponseModel model;
        // 计算输出对单位阶跃的归一化响应
        for (size_t k = 0; k < y_data.size(); ++k)
            model.S.push_back(y_data[k] / step_amplitude);
        model.N  = model.S.size();
        return model;
    }

    // 预测给定控制增量序列 ΔU 下的未来输出
    // y_k = y_0 + Σ_{j=1}^{min(k,N)} s_j * Δu_{k-j}
    std::vector<double> predict(const std::vector<double>& delta_u,
                                 double y0) const {
        int h = delta_u.size();
        std::vector<double> y(h, y0);
        for (int k = 0; k < h; ++k) {
            for (int j = 0; j <= std::min(k, N-1); ++j) {
                y[k] += S[j] * delta_u[k - j];
            }
        }
        return y;
    }
};
```

---

## 五、MPC 领域的发展趋势

```
2024-2026 研究热点
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  1. 神经网络 MPC（NN-MPC）                                   │
│     ● 用 LSTM/Transformer 替代线性预测模型                   │
│     ● 挑战：训练代价 vs 实时性；分布外泛化                   │
│     ● 代表工作：GP-MPC，Koopman MPC                         │
│                                                              │
│  2. Koopman 算子线性化                                       │
│     ● 将非线性系统提升到高维线性空间                         │
│     ● X_{k+1} = K * X_k（K 为线性 Koopman 算子）           │
│     ● 优点：线性 MPC 的计算效率 + 非线性系统的精度           │
│     ● 缺点：提升维数可能很高（数千维）                       │
│                                                              │
│  3. 强化学习 + MPC（RL-MPC）                                │
│     ● MPC 作为 RL 的模型预测引导（MBRL）                    │
│     ● RL 修正 MPC 的价值函数估计（终端代价学习）             │
│     ● 代表：MPPI，CEM-MPC，PETS                             │
│                                                              │
│  4. 分布式 MPC                                               │
│     ● 多智能体系统（多车辆编队、电网）                        │
│     ● 每个 agent 解局部 MPC，通过通信协调                    │
│     ● 算法：ADMM 分布式求解，对偶分解                        │
│                                                              │
│  5. 可微 MPC（Differentiable MPC）                          │
│     ● 将 MPC 作为可微层嵌入神经网络                          │
│     ● 通过 KKT 条件对 QP 解析求导                           │
│     ● 代表：OptNet，DMPO                                     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 5.1 Koopman 算子 MPC 简介

```cpp
// koopman_mpc_intro.hpp
// Koopman MPC：用数据学习线性化提升映射

// ============================================================
// 核心思想：
//   找一个非线性映射 ψ: ℝⁿ → ℝᴺ（N >> n），使得
//   非线性系统 x_{k+1} = f(x_k, u_k) 在提升空间中变线性：
//   ψ(x_{k+1}) = K_x * ψ(x_k) + K_u * u_k
//
// 常用基函数 ψ（提升映射）：
//   - 多项式：[x₁, x₂, x₁², x₁x₂, x₂², ...]
//   - 径向基函数（RBF）
//   - 神经网络编码器（近年主流）
// ============================================================
class KoopmanMPC {
public:
    struct KoopmanModel {
        Eigen::MatrixXd K_x;  // 状态转移（N_lift × N_lift）
        Eigen::MatrixXd K_u;  // 控制输入（N_lift × m）
        int n_orig;           // 原始状态维数
        int n_lift;           // 提升维数

        // 提升映射（多项式基函数示例）
        Eigen::VectorXd lift(const Eigen::VectorXd& x) const {
            // 构建 [x; x⊗x；...]（张量积特征）
            int n = x.size();
            std::vector<double> feats;
            feats.reserve(n_lift);

            for (int i = 0; i < n; ++i) feats.push_back(x(i));
            for (int i = 0; i < n; ++i)
                for (int j = i; j < n; ++j)
                    feats.push_back(x(i) * x(j));
            // 可继续添加三次项...

            while ((int)feats.size() < n_lift) feats.push_back(0.0);
            return Eigen::Map<Eigen::VectorXd>(feats.data(), n_lift);
        }

        // 投影回原空间（取前 n 个分量）
        Eigen::VectorXd project(const Eigen::VectorXd& z) const {
            return z.head(n_orig);
        }
    };

    // 从数据离线辨识 Koopman 算子
    static KoopmanModel identify(
        const std::vector<Eigen::VectorXd>& X,    // 状态序列（当前步）
        const std::vector<Eigen::VectorXd>& X_next, // 状态序列（下一步）
        const std::vector<Eigen::VectorXd>& U,    // 控制序列
        int n_lift)
    {
        KoopmanModel model;
        model.n_orig = X[0].size();
        model.n_lift = n_lift;

        int T = X.size();
        int m = U[0].size();

        // 构建提升空间下的数据矩阵
        Eigen::MatrixXd Psi(n_lift, T);  // 当前步的提升状态
        Eigen::MatrixXd Psi_next(n_lift, T);  // 下一步的提升状态
        Eigen::MatrixXd U_mat(m, T);

        for (int t = 0; t < T; ++t) {
            Psi.col(t)      = model.lift(X[t]);
            Psi_next.col(t) = model.lift(X_next[t]);
            U_mat.col(t)    = U[t];
        }

        // 最小二乘辨识：[K_x, K_u] * [Psi; U] ≈ Psi_next
        Eigen::MatrixXd ZU(n_lift + m, T);
        ZU.topRows(n_lift) = Psi;
        ZU.bottomRows(m)   = U_mat;

        // K = Psi_next * ZU^† （ZU 的 Moore-Penrose 伪逆）
        Eigen::MatrixXd K = Psi_next *
            ZU.transpose() * (ZU * ZU.transpose()).ldlt().solve(
                Eigen::MatrixXd::Identity(n_lift + m, n_lift + m));

        model.K_x = K.leftCols(n_lift);
        model.K_u = K.rightCols(m);

        double fit_error = (Psi_next - K * ZU).norm() / Psi_next.norm();
        std::cout << "Koopman 辨识误差（相对）: " << fit_error * 100 << "%\n";

        return model;
    }
};
```


---

## 附录 A：参数不确定性下的鲁棒 MPC（LMI 方法）

### A.1 问题陈述

考虑系统参数本身不确定（不仅是状态扰动）：

$$x_{k+1} = A(\theta) x_k + B(\theta) u_k, \quad \theta \in \Theta$$

其中 $\Theta$ 通常是**多胞体**（polytopic）：

$$\Theta = \text{Conv}\{(A_1, B_1), \ldots, (A_L, B_L)\}$$

例：车辆质量 $m \in [1200, 1800]$ kg、侧偏刚度 $C_\alpha \in [60, 100]$ kN/rad，多胞体顶点共 $2^2 = 4$ 个。

### A.2 多胞体鲁棒不变集

寻找一个椭球 $\mathcal{E} = \{x : x^T P x \leq 1\}$，对**所有** $(A_i, B_i)$ 都正不变：

$$\forall i, \ x \in \mathcal{E}, \ \exists u \text{ s.t. } A_i x + B_i u \in \mathcal{E}$$

通过状态反馈 $u = -K x$ 描述，等价于：

$$(A_i - B_i K)^T P (A_i - B_i K) - P \prec 0, \quad i = 1, \ldots, L$$

### A.3 LMI 化与求解

引入变量 $X = P^{-1}$，$Y = K X$，应用 Schur 补：

$$
\begin{bmatrix}
X & (A_i X - B_i Y)^T \\
A_i X - B_i Y & X
\end{bmatrix} \succ 0, \quad i = 1, \ldots, L
$$

这是**线性矩阵不等式（LMI）**——对每个顶点一个不等式。用 SDPT3、MOSEK、CVX 等工具直接解。

```cpp
// 伪代码：调用 MOSEK 解 LMI（实际工程通过 CVXOPT/MATLAB CVX 离线计算）
struct RobustMPCDesign {
    Eigen::MatrixXd K;       // 反馈增益
    Eigen::MatrixXd P;       // Lyapunov 矩阵
};

RobustMPCDesign designRobustMPC(
    const std::vector<Eigen::MatrixXd>& A_vertices,
    const std::vector<Eigen::MatrixXd>& B_vertices) {
    // 离线求解 LMI 系统：
    // min trace(X)
    // s.t. [X  (A_i X - B_i Y)^T; ...; ...] ≻ 0  for each i
    // 返回 K = Y X^{-1}, P = X^{-1}
    // ...（调用第三方 SDP 求解器）
    return {};
}
```

### A.4 在线 LMI MPC（计算量大）

每步在线求解 LMI——计算量远高于 QP，仅适用：

- 离线计算多个 $(A_i, B_i)$ 对应的 $K_i$，在线根据当前 $\theta$ 估计**插值**
- 慢速过程控制（采样周期 > 1 s）

### A.5 与 Tube MPC 的关系

| 方法 | 不确定性来源 | 鲁棒手段 |
|------|------------|---------|
| Tube MPC | 加性扰动 $w_k$ | 鲁棒不变集 + 名义系统跟踪 |
| 多胞体 LMI MPC | 参数 $\theta$ | 椭球不变集 + 顶点 LMI |
| Stochastic MPC | 随机扰动分布 | 概率约束 |

---

## 附录 B：分布式 MPC（DMPC）

### B.1 问题动机

多智能体系统（车队、机器人编队、电网）若用单点 MPC 控制：

- 单点失效 → 全系统瘫痪
- 通信带宽爆炸（$N$ 智能体 × 状态维度）
- 隐私/独立性需求（车厂之间不共享内部状态）

**分布式 MPC**：每个智能体只优化自己的代价 + 与邻居的耦合项。

### B.2 三类典型架构

| 架构 | 通信结构 | 求解 |
|------|---------|------|
| **完全分布式** | 仅邻居通信 | 每智能体本地 QP |
| **协作式** | 共享代价梯度 | ADMM 或 dual decomposition |
| **博弈式** | 仅观察邻居动作 | Best-response 迭代 |

### B.3 ADMM 分布式 MPC 简版

```
重复直到收敛：
  对每个智能体 i 并行：
    (a) 接收邻居的"耦合变量" z_j
    (b) 本地求 QP：min f_i(u_i) + ρ/2 ||u_i - z_i + λ_i/ρ||²
    (c) 把更新后的 u_i 发给邻居
  全局更新拉格朗日乘子 λ_i
```

### B.4 稳定性条件

DMPC 闭环稳定的充分条件（Müller & Allgöwer 2017）：

1. 每个智能体的本地 MPC 满足终端约束/代价
2. 智能体间耦合"足够弱"（Lipschitz 系数 < 1/$N$）
3. 通信图连通（无孤立节点）

### B.5 应用案例

- **车队协同（Platooning）**：每辆车仅与前后车通信，DMPC 维持队形
- **电网频率调节**：多发电机 DMPC 联合调度
- **多机械臂协作**：避免碰撞 + 协同搬运

---

## 附录 C：异步多频率 MPC

### C.1 现实系统的频率层级

```
路径规划      10 Hz      ← 慢，因为搜索空间大
轨迹优化      50 Hz
MPC 控制     100 Hz
PID 内环     500 Hz
执行器       1000 Hz
传感器：相机 30 Hz、IMU 200 Hz、CAN 50 Hz、GPS 10 Hz
```

### C.2 异步问题

不同频率带来的工程挑战：

| 问题 | 描述 |
|------|------|
| 数据时序不同步 | GPS 100 ms 前的位置 vs IMU 现在的姿态 |
| 控制率波动 | 偶发计算阻塞导致采样周期不均 |
| 上层指令延迟到达 | 路径规划耗时不固定 |

### C.3 算法对策

**(a) 时间戳对齐 + 缓冲**

```cpp
struct TimestampedData {
    double t;
    Eigen::VectorXd value;
};

// 用 deque 缓存最近 1 秒数据，按时间戳取值
template<typename T>
T interpolate(const std::deque<TimestampedData>& buf, double t_query) {
    // 二分查找 + 线性插值
}
```

**(b) 把异步建进 MPC 状态空间**

将通信延迟建模为系统状态扩展：

$$x_k^{aug} = [x_k, x_{k-1}, \ldots, x_{k-d}]$$

MPC 用增广状态优化，自动处理"过时输入"。

**(c) 事件触发 MPC（Event-Triggered MPC）**

仅在状态偏离参考超过阈值时才重新求解：

```cpp
if ((x_meas - x_predicted).norm() > trigger_threshold) {
    last_solution = mpc.solve(x_meas);
    last_solve_time = now();
}
// 否则继续 ZOH 上一次的解
return last_solution[(now() - last_solve_time) / dt];
```

效果：求解器调用减少 50%~80%，对计算资源紧张系统极有用。

### C.4 稳定性保证

异步 MPC 的稳定性证明远比同步复杂。关键条件：

1. 最大允许采样间隔 $T_{\max}$ 满足 $T_{\max} \cdot L_f < 1$（$L_f$ 是动态 Lipschitz 系数）
2. 事件触发条件保证采样间隔有上界
3. 需要**自触发**（Self-Triggered）机制保证安全：MPC 在求解时也输出"下次必须重算的时间"

---

## 附录 D：约束不可行时的优雅降级

### D.1 不可行的 5 种根本原因

| 原因 | 检测 | 应急策略 |
|------|------|---------|
| 1. 参考超物理极限 | KKT 证书指向参考方向 | 上层重规划，下层 ZOH 维持 |
| 2. 状态约束在初始就违反 | $x_0 \notin \mathbb{X}$ | 软约束 + 高惩罚，缓慢回归 |
| 3. 终端约束太紧 | 移除终端约束后可行 | 改用大 $Q_f$ 替代显式终端约束 |
| 4. 数值病态 | OSQP `MAX_ITER` | 加正则化 $H \leftarrow H + \epsilon I$ |
| 5. 求解超时 | `TIME_LIMIT_REACHED` | 启用上一步解（移位 + 终端反馈） |

### D.2 约束分级

按安全重要性分三级：

```
Level 0 (硬约束、不可违反)：碰撞约束、物理极限
Level 1 (重要约束)：道路边界、舒适加速度上限
Level 2 (软约束、可临时违反)：参考路径偏移、舒适抖动
```

QP 中通过松弛变量 $\epsilon^{(0)}, \epsilon^{(1)}, \epsilon^{(2)}$ 分别处理，惩罚权重 $w_0 \gg w_1 \gg w_2$（如 $10^9, 10^4, 10$）。

### D.3 Fallback 状态机

```cpp
enum class MPCState {
    NORMAL,           // 标准 MPC
    SOFT_CONSTRAINT,  // 软约束启用
    EMERGENCY_BRAKE,  // 紧急制动
    SAFE_HOLD         // 维持当前位置
};

class MPCFallbackController {
    MPCState state_ = MPCState::NORMAL;
    int consecutive_failures_ = 0;

public:
    Eigen::VectorXd step(const Eigen::VectorXd& x) {
        switch (state_) {
            case MPCState::NORMAL: {
                auto result = mpc_normal_.solve(x);
                if (result.success) {
                    consecutive_failures_ = 0;
                    return result.u;
                }
                if (++consecutive_failures_ > 2) {
                    state_ = MPCState::SOFT_CONSTRAINT;
                }
                return last_safe_u_;
            }
            case MPCState::SOFT_CONSTRAINT: {
                auto result = mpc_soft_.solve(x);
                if (result.success && result.slack < 0.1) {
                    state_ = MPCState::NORMAL;
                    return result.u;
                }
                if (consecutive_failures_ > 5) {
                    state_ = MPCState::EMERGENCY_BRAKE;
                }
                return result.success ? result.u : last_safe_u_;
            }
            case MPCState::EMERGENCY_BRAKE:
                return emergencyBrakeCommand(x);
            case MPCState::SAFE_HOLD:
                return Eigen::VectorXd::Zero(m_);
        }
    }
};
```

**安全准则**：故障切换必须**单调降级**——不能从 EMERGENCY_BRAKE 直接回到 NORMAL，必须先回到 SOFT_CONSTRAINT 观察若干步。
