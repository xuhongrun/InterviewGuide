# 第六篇：MPC 工程实践 — 调参、鲁棒性与嵌入式部署

---

## 引言

前五篇建立了从线性 MPC 到非线性 MPC 的完整理论和代码体系。但从"能跑"到"能用"之间，还有一道工程实践的鸿沟：

- **调参**：权重矩阵怎么选？参数调错会有什么症状？如何系统化诊断？
- **鲁棒性**：模型有误差，外界有扰动，如何让 MPC 在真实环境中稳定运行？
- **嵌入式**：在算力受限的 ECU 或 MCU 上，如何把 MPC 代码压缩到实时可用？

本篇聚焦这三个工程核心问题，所有策略均有对应 C++ 实现。

---

## 一、调参方法论

### 1.1 权重参数的物理意义

MPC 的目标函数形如：

$$J = \sum_{k=1}^{N} x_k^T Q x_k + \sum_{k=0}^{N-1} u_k^T R u_k$$

$Q$ 和 $R$ 不是抽象的数学符号，每个对角元素都对应具体的物理代价：

```cpp
// 以车辆轨迹跟踪为例，权重矩阵的物理解读
//
// 状态: x = [横向误差 e_lat, 航向误差 e_psi, 速度误差 e_v]
// 控制: u = [转向角 delta, 加速度 a]
//
// Q = diag(q_lat, q_psi, q_v)
// R = diag(r_delta, r_a)
//
// q_lat  单位：1/m²   → 横向偏差 1m 的代价是 q_lat
// q_psi  单位：1/rad² → 航向偏差 1rad 的代价是 q_psi
// q_v    单位：1/(m/s)² → 速度偏差 1m/s 的代价是 q_v
// r_delta 单位：1/rad²  → 转向角 1rad 的代价是 r_delta
// r_a    单位：1/(m/s²)² → 加速度 1m/s² 的代价是 r_a
//
// 直觉：如果横向偏差 0.1m 和航向偏差 0.05rad 对你同等重要，
// 则设 q_lat * 0.1^2 = q_psi * 0.05^2
//    => q_lat / q_psi = 0.05^2 / 0.1^2 = 0.25

// 标准化权重设计方法（Bryson 法则）
// Q_ii = 1 / (允许的最大状态误差_i)^2
// R_ii = 1 / (允许的最大控制量_i)^2
struct BrysonWeights {
    static Eigen::MatrixXd computeQ(
        const std::vector<double>& max_state_errors) {
        int n = max_state_errors.size();
        Eigen::MatrixXd Q = Eigen::MatrixXd::Zero(n, n);
        for (int i = 0; i < n; ++i) {
            Q(i, i) = 1.0 / (max_state_errors[i] * max_state_errors[i]);
        }
        return Q;
    }

    static Eigen::MatrixXd computeR(
        const std::vector<double>& max_control_values) {
        int m = max_control_values.size();
        Eigen::MatrixXd R = Eigen::MatrixXd::Zero(m, m);
        for (int i = 0; i < m; ++i) {
            R(i, i) = 1.0 / (max_control_values[i] * max_control_values[i]);
        }
        return R;
    }
};

// 使用示例：车辆轨迹跟踪
// 允许的最大横向误差：0.5m
// 允许的最大航向误差：0.2rad (~11.5°)
// 允许的最大速度误差：2.0 m/s
// 最大转向角：0.4rad (~23°)
// 最大加减速度：3.0 m/s²
//
// Q = diag(1/0.5², 1/0.2², 1/2.0²) = diag(4, 25, 0.25)
// R = diag(1/0.4², 1/3.0²)          = diag(6.25, 0.11)
```

### 1.2 常见控制症状与诊断

```cpp
// 症状诊断器：通过仿真数据自动识别调参问题
class MPCDiagnostics {
public:
    struct ControlLog {
        std::vector<double> times;
        std::vector<Eigen::VectorXd> states;
        std::vector<Eigen::VectorXd> controls;
        std::vector<Eigen::VectorXd> refs;
    };

    struct Diagnosis {
        bool overshoot;        // 超调：误差穿越零后反向超过阈值
        bool oscillation;      // 震荡：误差符号频繁变化
        bool slow_convergence; // 收敛慢：经过 t_settle 后误差仍大于阈值
        bool control_chatter; // 控制抖动：相邻控制量差异过大
        bool steady_error;    // 稳态误差：最终误差不为零

        std::string summary() const;
    };

    static Diagnosis analyze(const ControlLog& log,
                              double error_threshold = 0.05,
                              double t_settle = 2.0) {
        Diagnosis d{};
        int n = log.times.size();
        if (n < 10) return d;

        // ── 提取误差序列（以第一个状态分量为例）──
        std::vector<double> errors(n);
        for (int i = 0; i < n; ++i)
            errors[i] = log.states[i](0) - log.refs[i](0);

        // ── 检测超调 ──
        // 初始误差方向
        double e0_sign = (errors[0] > 0) ? 1.0 : -1.0;
        for (int i = 1; i < n; ++i) {
            // 误差反号且幅度超过阈值的 20%
            if (errors[i] * e0_sign < -error_threshold * 0.2) {
                d.overshoot = true;
                break;
            }
        }

        // ── 检测震荡（符号变化超过3次）──
        int sign_changes = 0;
        for (int i = 1; i < n; ++i) {
            if (errors[i] * errors[i-1] < 0) ++sign_changes;
        }
        d.oscillation = (sign_changes > 3);

        // ── 检测收敛速度 ──
        double dt = log.times[1] - log.times[0];
        int settle_idx = std::min(n - 1, (int)(t_settle / dt));
        double final_error = std::abs(errors[settle_idx]);
        d.slow_convergence = (final_error > error_threshold);

        // ── 检测控制抖动 ──
        if (log.controls.size() > 1) {
            double du_sum = 0.0;
            for (int i = 1; i < n; ++i) {
                du_sum += (log.controls[i] - log.controls[i-1]).norm();
            }
            double du_avg = du_sum / (n - 1);
            // 平均控制增量超过控制量范围的 5% 视为抖动
            d.control_chatter = (du_avg > 0.05 * log.controls[0].norm() + 0.01);
        }

        // ── 检测稳态误差（最后10%时间窗口内的平均误差）──
        int tail_start = (int)(0.9 * n);
        double tail_error = 0.0;
        for (int i = tail_start; i < n; ++i)
            tail_error += std::abs(errors[i]);
        tail_error /= (n - tail_start);
        d.steady_error = (tail_error > error_threshold * 0.1);

        return d;
    }
};

std::string MPCDiagnostics::Diagnosis::summary() const {
    std::string msg;
    if (overshoot)
        msg += "【超调】→ 增大 R（减小控制激进度）或减小 Q\n";
    if (oscillation)
        msg += "【震荡】→ 增大 R 或增加控制增量约束 du_max\n";
    if (slow_convergence)
        msg += "【收敛慢】→ 增大 Q 或增大预测时域 N\n";
    if (control_chatter)
        msg += "【控制抖动】→ 增大 R 对角元素 或 引入增量惩罚\n";
    if (steady_error)
        msg += "【稳态误差】→ 模型存在偏差，引入积分增广（见第二节）\n";
    if (msg.empty())
        msg = "【正常】控制性能满足预期\n";
    return msg;
}
```

### 1.3 系统化参数扫描

```cpp
// 参数网格搜索：自动评估不同权重组合的性能
struct TuningResult {
    double q_scale;   // Q 缩放因子
    double r_scale;   // R 缩放因子
    double ise;       // 积分平方误差（Integral of Squared Error）
    double itae;      // 时间加权绝对误差（ITAE，惩罚慢收敛）
    double max_du;    // 最大控制增量（衡量平滑性）
    double settle_time; // 调节时间
};

// 性能指标计算
struct PerformanceMetrics {
    static double ISE(const std::vector<double>& errors, double dt) {
        double val = 0.0;
        for (double e : errors) val += e * e * dt;
        return val;
    }

    static double ITAE(const std::vector<double>& errors,
                       const std::vector<double>& times, double dt) {
        double val = 0.0;
        for (size_t i = 0; i < errors.size(); ++i)
            val += times[i] * std::abs(errors[i]) * dt;
        return val;
    }

    // 调节时间：误差首次进入 threshold 带并保持
    static double settleTime(const std::vector<double>& errors,
                              const std::vector<double>& times,
                              double threshold) {
        for (int i = errors.size() - 1; i >= 0; --i) {
            if (std::abs(errors[i]) > threshold)
                return times[std::min((int)times.size()-1, i+1)];
        }
        return 0.0;
    }
};

// 并行扫描（利用 OpenMP）
#include <omp.h>
std::vector<TuningResult> gridSearch(
    const std::vector<double>& q_scales,    // 如 {0.1, 1.0, 10.0, 100.0}
    const std::vector<double>& r_scales,    // 如 {0.01, 0.1, 1.0, 10.0}
    std::function<MPCResult(double, double)> simulate)  // 仿真函数
{
    std::vector<TuningResult> results;
    results.reserve(q_scales.size() * r_scales.size());

    #pragma omp parallel for collapse(2) schedule(dynamic)
    for (size_t qi = 0; qi < q_scales.size(); ++qi) {
        for (size_t ri = 0; ri < r_scales.size(); ++ri) {
            auto [errors, times, controls] =
                simulate(q_scales[qi], r_scales[ri]);

            TuningResult tr;
            tr.q_scale    = q_scales[qi];
            tr.r_scale    = r_scales[ri];
            tr.ise        = PerformanceMetrics::ISE(errors, times[1]-times[0]);
            tr.itae       = PerformanceMetrics::ITAE(errors, times, times[1]-times[0]);
            tr.settle_time = PerformanceMetrics::settleTime(errors, times, 0.05);

            double max_du = 0.0;
            for (size_t i = 1; i < controls.size(); ++i)
                max_du = std::max(max_du,
                    (controls[i] - controls[i-1]).cwiseAbs().maxCoeff());
            tr.max_du = max_du;

            #pragma omp critical
            results.push_back(tr);
        }
    }

    // 按 ITAE 升序排列（ITAE 小 = 综合性能好）
    std::sort(results.begin(), results.end(),
              [](const TuningResult& a, const TuningResult& b) {
                  return a.itae < b.itae;
              });
    return results;
}
```

### 1.4 终端权重的理论计算（离散时间 Riccati 方程）

终端代价 $Q_f$ 若取为**离散时间代数 Riccati 方程（DARE）**的解，可以保证闭环稳定性，且减小对 $N$ 选择的敏感性：

$$Q_f = A^T Q_f A - A^T Q_f B (B^T Q_f B + R)^{-1} B^T Q_f A + Q$$

```cpp
// 求解离散时间代数 Riccati 方程（迭代法）
// 收敛时 P = DARE(A, B, Q, R)，将其作为终端权重 Qf
Eigen::MatrixXd solveDARE(const Eigen::MatrixXd& A,
                            const Eigen::MatrixXd& B,
                            const Eigen::MatrixXd& Q,
                            const Eigen::MatrixXd& R,
                            int max_iter = 1000,
                            double tol   = 1e-10) {
    int n = A.rows();
    Eigen::MatrixXd P = Q;  // 初始猜测
    Eigen::MatrixXd P_new;

    for (int iter = 0; iter < max_iter; ++iter) {
        // S = B^T * P * B + R（m×m，较小矩阵）
        Eigen::MatrixXd S = B.transpose() * P * B + R;

        // K = (S)^{-1} * B^T * P * A（Riccati 增益）
        Eigen::MatrixXd K = S.ldlt().solve(B.transpose() * P * A);

        // P_new = A^T * P * A - A^T * P * B * K + Q
        P_new = A.transpose() * P * A
              - A.transpose() * P * B * K + Q;

        // 对称化（消除浮点累积误差）
        P_new = 0.5 * (P_new + P_new.transpose());

        double delta = (P_new - P).norm();
        P = P_new;

        if (delta < tol) {
            std::cout << "DARE 收敛，迭代 " << iter + 1 << " 次\n";
            break;
        }
    }
    return P;
}

// 同时提取最优 LQR 反馈增益（可用于验证 MPC 稳定性）
std::pair<Eigen::MatrixXd, Eigen::MatrixXd>
computeLQRGain(const Eigen::MatrixXd& A, const Eigen::MatrixXd& B,
               const Eigen::MatrixXd& Q, const Eigen::MatrixXd& R) {
    Eigen::MatrixXd Qf = solveDARE(A, B, Q, R);

    // K = (B^T * Qf * B + R)^{-1} * B^T * Qf * A
    Eigen::MatrixXd S  = B.transpose() * Qf * B + R;
    Eigen::MatrixXd K  = S.ldlt().solve(B.transpose() * Qf * A);

    // 验证闭环稳定性：A_cl = A - B*K 的特征值应在单位圆内
    Eigen::MatrixXd Acl = A - B * K;
    Eigen::EigenSolver<Eigen::MatrixXd> eig(Acl);
    bool stable = true;
    for (int i = 0; i < eig.eigenvalues().size(); ++i) {
        if (std::abs(eig.eigenvalues()(i)) >= 1.0) {
            stable = false;
            break;
        }
    }
    std::cout << "LQR 闭环系统" << (stable ? "稳定\n" : "不稳定！\n");

    return {Qf, K};
}
```

---

## 二、鲁棒性设计：处理模型误差与外部扰动

### 2.1 问题根源：线性 MPC 的稳态误差

考虑真实系统受持续扰动 $d$：

$$x_{k+1} = Ax_k + Bu_k + Gd_k$$

而 MPC 的模型不含扰动项（$G = 0$）。当扰动恒定（如坡度、侧风）时，标准 MPC 会产生**稳态误差**——这与 PID 不加积分时的问题完全类似。

**根本原因**：MPC 的开环最优解满足 $u^* = -(H^{-1})f$，但 $f$ 中没有包含扰动项，优化器"不知道"有持续偏差存在。

### 2.2 方案一：积分状态增广

将积分误差作为新的状态量加入系统，使扰动的影响可以被 MPC 感知和消除：

```cpp
// integral_augmentation.hpp
#pragma once
#include <Eigen/Dense>

// ============================================================
// 积分增广：将输出误差的积分加入状态
//
// 原始系统：x_{k+1} = A*x_k + B*u_k + G*d（d为未知扰动）
//            y_k = C*x_k
//
// 增广状态：[x; xi]，其中 xi_{k+1} = xi_k + (y_k - y_ref)*Ts
//
// 增广系统：
//   [x_{k+1} ]   [A,    0] [x_k]   [B]           [G 0]
//   [xi_{k+1}] = [C*Ts, I] [xi_k] + [0] * u_k   + [ 0 I] * [d; -y_ref*Ts]
//
// 当系统稳定时，积分状态 xi 会驱使 y → y_ref（消除稳态误差）
// ============================================================
struct AugmentedSystem {
    Eigen::MatrixXd A_aug;  // (n+p) × (n+p)
    Eigen::MatrixXd B_aug;  // (n+p) × m
    Eigen::MatrixXd C_aug;  // p × (n+p)
    int n_orig;             // 原始状态维数
    int n_int;              // 积分状态维数（= 输出维数 p）
};

AugmentedSystem buildIntegralAugmentation(
    const Eigen::MatrixXd& A,   // n×n
    const Eigen::MatrixXd& B,   // n×m
    const Eigen::MatrixXd& C,   // p×n（被积分的输出）
    double Ts)
{
    int n = A.rows(), m = B.cols(), p = C.rows();

    AugmentedSystem aug;
    aug.n_orig = n;
    aug.n_int  = p;

    // 增广系统矩阵 A_aug = [A, 0; C*Ts, I]
    aug.A_aug = Eigen::MatrixXd::Zero(n + p, n + p);
    aug.A_aug.topLeftCorner(n, n) = A;
    aug.A_aug.bottomLeftCorner(p, n) = C * Ts;
    aug.A_aug.bottomRightCorner(p, p) = Eigen::MatrixXd::Identity(p, p);

    // 增广输入矩阵 B_aug = [B; 0]
    aug.B_aug = Eigen::MatrixXd::Zero(n + p, m);
    aug.B_aug.topRows(n) = B;

    // 增广输出矩阵（对增广状态观测原状态分量即可）
    aug.C_aug = Eigen::MatrixXd::Zero(p, n + p);
    aug.C_aug.leftCols(n) = C;

    return aug;
}

// 构建增广状态向量（将积分状态初始化为零）
Eigen::VectorXd buildAugmentedState(
    const Eigen::VectorXd& x_orig,
    int p)  // 积分状态维数
{
    Eigen::VectorXd x_aug(x_orig.size() + p);
    x_aug.head(x_orig.size()) = x_orig;
    x_aug.tail(p).setZero();  // 积分状态初始为零
    return x_aug;
}

// 每步更新积分状态（在状态更新后调用）
void updateIntegralState(
    Eigen::VectorXd& x_aug,
    const Eigen::VectorXd& y_meas,  // 实测输出
    const Eigen::VectorXd& y_ref,   // 目标输出
    int n_orig, double Ts,
    double anti_windup_limit = 10.0)  // 防饱和限幅
{
    int p = y_meas.size();
    Eigen::VectorXd error = y_meas - y_ref;

    for (int i = 0; i < p; ++i) {
        x_aug(n_orig + i) += error(i) * Ts;
        // 抗积分饱和（Anti-windup）
        x_aug(n_orig + i) = std::max(-anti_windup_limit,
                             std::min( anti_windup_limit, x_aug(n_orig + i)));
    }
}
```

### 2.3 方案二：扰动观测器（DOB）

当扰动动态已知（如斜坡扰动、谐波扰动）时，可以设计**扰动观测器（Disturbance Observer）**主动估计并前馈补偿：

```cpp
// disturbance_observer.hpp
#pragma once
#include <Eigen/Dense>

// ============================================================
// 基于 Luenberger 观测器的扰动估计
//
// 增广模型（将常值扰动 d 也作为状态）：
//   [x_{k+1}]   [A, G] [x_k]   [B]
//   [d_{k+1}] = [0, I] [d_k] + [0] * u_k
//
// 观测器：
//   [x̂_{k+1}]   [A, G] [x̂_k]   [B]         [L_x]
//   [d̂_{k+1}] = [0, I] [d̂_k] + [0] * u_k + [L_d] * (y_k - C*x̂_k)
// ============================================================
class DisturbanceObserver {
public:
    DisturbanceObserver(const Eigen::MatrixXd& A,
                        const Eigen::MatrixXd& B,
                        const Eigen::MatrixXd& C,
                        const Eigen::MatrixXd& G,   // 扰动进入通道
                        const Eigen::MatrixXd& L)   // 观测器增益 (n+nd)×p
        : A_(A), B_(B), C_(C), G_(G), L_(L)
    {
        int n  = A.rows();
        int nd = G.cols();
        x_hat_ = Eigen::VectorXd::Zero(n + nd);
    }

    // 每步调用：先预测，再修正（预测-校正结构）
    void update(const Eigen::VectorXd& y_meas,  // 当前测量输出
                const Eigen::VectorXd& u_prev)  // 上一步控制量
    {
        int n  = A_.rows();
        int nd = G_.cols();

        Eigen::VectorXd x_hat  = x_hat_.head(n);
        Eigen::VectorXd d_hat  = x_hat_.tail(nd);

        // 预测步（使用上一步的控制量）
        Eigen::VectorXd x_pred = A_ * x_hat + B_ * u_prev + G_ * d_hat;
        Eigen::VectorXd d_pred = d_hat;  // 常值扰动模型

        // 测量残差
        Eigen::VectorXd y_pred = C_ * x_pred;
        Eigen::VectorXd innov  = y_meas - y_pred;

        // 修正步
        x_hat_.head(n)  = x_pred + L_.topRows(n)  * innov;
        x_hat_.tail(nd) = d_pred + L_.bottomRows(nd) * innov;
    }

    // 获取估计的状态
    Eigen::VectorXd stateEstimate() const {
        return x_hat_.head(A_.rows());
    }

    // 获取估计的扰动
    Eigen::VectorXd disturbanceEstimate() const {
        return x_hat_.tail(G_.cols());
    }

    // 将估计的扰动以前馈方式加入 MPC 参考修正
    // 思路：如果预测到下 N 步会有扰动 d̂，修正参考轨迹
    // 或者：直接修正 f 向量 f_corrected = f + 2*calB'*barQ*calA_d*d̂
    Eigen::VectorXd computeFeedforwardCorrection(
        const Eigen::MatrixXd& calB,
        const Eigen::MatrixXd& barQ,
        const Eigen::MatrixXd& calA_d)  // 扰动的预测矩阵
    const {
        Eigen::VectorXd d_hat = disturbanceEstimate();
        // 修正量加到 f 上，等效于把扰动纳入参考
        return 2.0 * calB.transpose() * barQ * calA_d * d_hat;
    }

private:
    Eigen::MatrixXd A_, B_, C_, G_, L_;
    Eigen::VectorXd x_hat_;
};

// 设计观测器增益（极点配置）
// 将增广系统 [A,G;0,I] 的观测器极点配置在期望位置
// 期望极点一般选在控制器闭环极点的 3~5 倍（观测速度更快）
Eigen::MatrixXd designObserverGain(
    const Eigen::MatrixXd& A_aug,  // 增广系统矩阵 (n+nd)×(n+nd)
    const Eigen::MatrixXd& C_aug,  // 增广输出矩阵 p×(n+nd)
    const std::vector<std::complex<double>>& desired_poles)
{
    // 使用 Ackermann 公式（对低维系统）
    // 实际工程中建议调用 MATLAB place() 或类似库
    // 这里给出基于 LQR 对偶的设计方法

    int n_aug = A_aug.rows();
    int p     = C_aug.rows();

    // 等价于：设计 (A_aug^T, C_aug^T) 的 LQR 状态反馈增益
    // 观测器增益 L = (LQR 增益)^T
    Eigen::MatrixXd Q_obs = Eigen::MatrixXd::Identity(n_aug, n_aug) * 1.0;
    Eigen::MatrixXd R_obs = Eigen::MatrixXd::Identity(p, p) * 0.01;

    // 使用 DARE 对偶
    Eigen::MatrixXd P = solveDARE(A_aug.transpose(), C_aug.transpose(),
                                   Q_obs, R_obs);
    Eigen::MatrixXd L_T = (R_obs + C_aug * P * C_aug.transpose()).ldlt()
                               .solve(C_aug * P * A_aug.transpose());

    return L_T.transpose();  // L (n_aug × p)
}
```

### 2.4 方案三：Offset-Free MPC（工业标准方案）

工业 MPC 的标准抗稳态误差方案，将扰动估计与控制解耦：

```cpp
// offset_free_mpc.hpp
#pragma once
#include <Eigen/Dense>

// ============================================================
// Offset-Free MPC（Pannocchia & Rawlings，2003）
//
// 思路：
//   1. 增广一个"输出扰动"状态 d（维数 = 输出维数 p）
//   2. 用 Kalman 滤波估计 d
//   3. 修改稳态目标计算（Target Calculator），确保稳态时 y = y_ref
//   4. MPC 跟踪修正后的目标，而非直接跟踪 y_ref
// ============================================================
class OffsetFreeMPC {
public:
    struct Target {
        Eigen::VectorXd x_s;  // 稳态目标状态
        Eigen::VectorXd u_s;  // 稳态目标控制量
    };

    // 稳态目标计算器
    // 求解：[A-I, B; C, 0] [x_s; u_s] = [-G*d_hat; y_ref - d_hat]
    // 确保在扰动 d̂ 存在时，稳态输出 y_s = C*x_s + d̂ = y_ref
    static Target computeSteadyStateTarget(
        const Eigen::MatrixXd& A,
        const Eigen::MatrixXd& B,
        const Eigen::MatrixXd& C,
        const Eigen::VectorXd& y_ref,
        const Eigen::VectorXd& d_hat)  // 估计的扰动
    {
        int n = A.rows(), m = B.cols(), p = C.rows();

        // 构建稳态方程：M * [x_s; u_s] = rhs
        Eigen::MatrixXd M(n + p, n + m);
        M.topLeftCorner(n, n)     = A - Eigen::MatrixXd::Identity(n, n);
        M.topRightCorner(n, m)    = B;
        M.bottomLeftCorner(p, n)  = C;
        M.bottomRightCorner(p, m) = Eigen::MatrixXd::Zero(p, m);

        Eigen::VectorXd rhs(n + p);
        rhs.head(n) = Eigen::VectorXd::Zero(n);  // 假设无状态扰动
        rhs.tail(p) = y_ref - d_hat;

        // 最小二乘求解（系统可能欠定或超定）
        Eigen::VectorXd sol = M.jacobiSvd(
            Eigen::ComputeThinU | Eigen::ComputeThinV).solve(rhs);

        Target target;
        target.x_s = sol.head(n);
        target.u_s = sol.tail(m);
        return target;
    }

    // 在 MPC 目标函数中跟踪修正后的稳态目标
    // J = Σ (x_k - x_s)^T Q (x_k - x_s) + (u_k - u_s)^T R (u_k - u_s)
    // 而非直接跟踪 x_ref（这是 Offset-Free 的关键）
};
```

### 2.5 鲁棒性方案比较与选择指南

```
┌─────────────────────────────────────────────────────────────────┐
│                    扰动类型 × 方案选择矩阵                        │
├───────────────────┬──────────────────┬────────────────────────────┤
│  扰动类型         │  推荐方案         │   关键参数                  │
├───────────────────┼──────────────────┼────────────────────────────┤
│ 常值偏置（坡度）   │ 积分增广          │  anti-windup 限幅           │
│ 慢变扰动（载重）   │ DOB + 前馈        │  观测器带宽（极点位置）      │
│ 输出偏置（传感器） │ Offset-Free MPC   │  稳态目标计算器             │
│ 随机噪声          │ Kalman 滤波状态估计 │  Q_kf, R_kf 噪声协方差     │
│ 已知扰动（风）    │ 前馈补偿           │  扰动模型精度               │
│ 剧烈未知扰动      │ Tube MPC（鲁棒）   │  不变集计算（离线）          │
└───────────────────┴──────────────────┴────────────────────────────┘
```

---

## 三、卡尔曼滤波：状态估计与 MPC 的结合

MPC 依赖当前状态 $x_0$，但传感器只提供含噪声的测量 $y_k = Cx_k + \nu_k$。工程中必须将 MPC 与状态估计器配合使用。

```cpp
// kalman_filter.hpp
#pragma once
#include <Eigen/Dense>

// ============================================================
// 离散时间线性卡尔曼滤波器
//
// 系统模型：x_{k+1} = A*x_k + B*u_k + w_k，w_k ~ N(0, Q_w)
// 测量模型：y_k = C*x_k + v_k，v_k ~ N(0, R_v)
// ============================================================
class KalmanFilter {
public:
    KalmanFilter(const Eigen::MatrixXd& A,
                 const Eigen::MatrixXd& B,
                 const Eigen::MatrixXd& C,
                 const Eigen::MatrixXd& Q_w,    // 过程噪声协方差
                 const Eigen::MatrixXd& R_v,    // 测量噪声协方差
                 const Eigen::VectorXd& x0,     // 初始状态估计
                 const Eigen::MatrixXd& P0)     // 初始误差协方差
        : A_(A), B_(B), C_(C), Q_w_(Q_w), R_v_(R_v),
          x_hat_(x0), P_(P0)
    {}

    // 预测步（在执行控制量后、获得下一测量前调用）
    void predict(const Eigen::VectorXd& u) {
        x_hat_ = A_ * x_hat_ + B_ * u;
        P_     = A_ * P_ * A_.transpose() + Q_w_;
    }

    // 更新步（获得新测量后调用）
    void update(const Eigen::VectorXd& y_meas) {
        // 新息（Innovation）
        Eigen::VectorXd innov = y_meas - C_ * x_hat_;

        // 新息协方差
        Eigen::MatrixXd S = C_ * P_ * C_.transpose() + R_v_;

        // 卡尔曼增益
        Eigen::MatrixXd K = P_ * C_.transpose() * S.ldlt().solve(
            Eigen::MatrixXd::Identity(S.rows(), S.cols()));

        // 状态更新
        x_hat_ += K * innov;

        // 协方差更新（Joseph 形式，数值更稳定）
        Eigen::MatrixXd I_KC = Eigen::MatrixXd::Identity(
                                   x_hat_.size(), x_hat_.size())
                             - K * C_;
        P_ = I_KC * P_ * I_KC.transpose() + K * R_v_ * K.transpose();
    }

    const Eigen::VectorXd& stateEstimate() const { return x_hat_; }
    const Eigen::MatrixXd& covariance()    const { return P_; }

    // 新息的马氏距离（用于传感器故障检测）
    double mahalanobisDistance(const Eigen::VectorXd& y_meas) const {
        Eigen::VectorXd innov = y_meas - C_ * x_hat_;
        Eigen::MatrixXd S     = C_ * P_ * C_.transpose() + R_v_;
        return std::sqrt(innov.transpose() * S.ldlt().solve(innov));
    }

private:
    Eigen::MatrixXd A_, B_, C_, Q_w_, R_v_;
    Eigen::VectorXd x_hat_;
    Eigen::MatrixXd P_;
};

// ── MPC + KF 联合控制器 ──
class MPC_KF_Controller {
public:
    MPC_KF_Controller(/* 参数省略 */)
        : mpc_(/* ... */), kf_(/* ... */) {}

    Eigen::VectorXd step(const Eigen::VectorXd& y_meas,
                          const Eigen::VectorXd& X_ref) {
        // 1. 卡尔曼滤波更新
        kf_.update(y_meas);

        // 2. 获取状态估计，传入 MPC
        Eigen::VectorXd x_hat = kf_.stateEstimate();

        // 3. 可选：传感器故障检测
        double dist = kf_.mahalanobisDistance(y_meas);
        if (dist > 3.0) {
            // 马氏距离过大（超过 3σ）：传感器可能故障
            // 使用预测值代替测量，或触发安全模式
            fprintf(stderr, "警告：传感器异常，马氏距离 = %.2f\n", dist);
        }

        // 4. MPC 求解
        auto result = mpc_.solve(x_hat, X_ref, u_prev_);

        // 5. 卡尔曼预测步（为下一周期准备）
        kf_.predict(result.u_opt);

        u_prev_ = result.u_opt;
        return result.u_opt;
    }

private:
    OSQPMPCSolver mpc_;
    KalmanFilter  kf_;
    Eigen::VectorXd u_prev_;
};
```

---

## 四、嵌入式部署

### 4.1 嵌入式 MPC 的挑战

典型嵌入式控制器的约束：

| 指标 | 普通 PC | 汽车 ECU | 工业 PLC | 微控制器（MCU） |
|------|---------|---------|---------|--------------|
| CPU | 3GHz+ x86 | 300MHz ARM | 400MHz | 100MHz |
| RAM | 16GB | 512KB | 256KB | 64KB |
| 操作系统 | Linux/Windows | AUTOSAR | VxWorks/无 | 无OS |
| 浮点 | 硬件 | 硬件/软件 | 硬件 | 软件（慢） |
| 动态内存 | 可用 | **禁止** | 受限 | **禁止** |

嵌入式 MPC 的三大要求：
1. **无动态内存分配**（malloc/new 禁止）
2. **确定性执行时间**（无随机分支）
3. **内存占用极小**（KB 级别）

### 4.2 静态内存分配：模板化 MPC

```cpp
// static_mpc.hpp
#pragma once
#include <Eigen/Dense>
#include <array>

// ============================================================
// 编译期固定尺寸的 MPC 求解器（零动态内存分配）
//
// 模板参数：
//   NX - 状态维数
//   NU - 控制维数
//   NH - 预测时域
// ============================================================
template<int NX, int NU, int NH>
class StaticMPC {
public:
    // 所有矩阵使用编译期固定尺寸（栈上分配）
    using StateVec   = Eigen::Matrix<double, NX, 1>;
    using ControlVec = Eigen::Matrix<double, NU, 1>;
    using PredState  = Eigen::Matrix<double, NX * NH, 1>;
    using PredCtrl   = Eigen::Matrix<double, NU * NH, 1>;

    using MatA = Eigen::Matrix<double, NX, NX>;
    using MatB = Eigen::Matrix<double, NX, NU>;
    using CalA = Eigen::Matrix<double, NX * NH, NX>;
    using CalB = Eigen::Matrix<double, NX * NH, NU * NH>;
    using H_t  = Eigen::Matrix<double, NU * NH, NU * NH>;
    using f_t  = Eigen::Matrix<double, NU * NH, 1>;

    struct Config {
        double u_min[NU];
        double u_max[NU];
    };

    // 构造函数：离线预计算 H 和预测矩阵
    StaticMPC(const MatA& A, const MatB& B,
               const Eigen::Matrix<double, NX, NX>& Q,
               const Eigen::Matrix<double, NX, NX>& Qf,
               const Eigen::Matrix<double, NU, NU>& R,
               const Config& cfg)
        : cfg_(cfg)
    {
        // 构建预测矩阵（编译期已知尺寸）
        buildPredictionMatrices(A, B);
        buildWeightMatrices(Q, Qf, R);

        // 预计算 H = 2*(calB'*barQ*calB + barR)
        H_ = 2.0 * (calB_.transpose() * barQ_ * calB_ + barR_);
        H_ = 0.5 * (H_ + H_.transpose());  // 对称化

        // 预计算 Cholesky 分解（无约束路径）
        ldlt_.compute(H_);
    }

    // 求解（纯栈操作，无堆分配）
    ControlVec solve(const StateVec& x0,
                     const PredState& X_ref) {
        // 计算线性项
        f_t f = (2.0 * calB_.transpose() * barQ_ *
                (calA_ * x0 - X_ref)).eval();

        // 无约束最优解
        PredCtrl U_opt = -ldlt_.solve(f);

        // 饱和投影（对控制量上下界）
        for (int k = 0; k < NH; ++k) {
            for (int i = 0; i < NU; ++i) {
                int idx = k * NU + i;
                U_opt(idx) = std::max(cfg_.u_min[i],
                             std::min(cfg_.u_max[i], U_opt(idx)));
            }
        }

        return U_opt.template head<NU>();
    }

private:
    void buildPredictionMatrices(const MatA& A, const MatB& B) {
        calA_.setZero();
        calB_.setZero();

        MatA Apow = A;
        for (int k = 0; k < NH; ++k) {
            calA_.template block<NX, NX>(k * NX, 0) = Apow;

            Eigen::Matrix<double, NX, NU> AjB = B;
            for (int j = k; j >= 0; --j) {
                calB_.template block<NX, NU>(k * NX, j * NU) = AjB;
                if (j > 0) AjB = A * AjB;
            }
            Apow = A * Apow;
        }
    }

    void buildWeightMatrices(
        const Eigen::Matrix<double, NX, NX>& Q,
        const Eigen::Matrix<double, NX, NX>& Qf,
        const Eigen::Matrix<double, NU, NU>& R)
    {
        barQ_.setZero();
        barR_.setZero();
        for (int k = 0; k < NH; ++k) {
            barQ_.template block<NX, NX>(k*NX, k*NX) = (k < NH-1) ? Q : Qf;
            barR_.template block<NU, NU>(k*NU, k*NU) = R;
        }
    }

    Config cfg_;
    CalA calA_;
    CalB calB_;
    Eigen::Matrix<double, NX*NH, NX*NH> barQ_;
    Eigen::Matrix<double, NU*NH, NU*NH> barR_;
    H_t  H_;
    Eigen::LDLT<H_t> ldlt_;
};

// 使用示例：2状态，1控制，10步预测时域
// StaticMPC<2, 1, 10> mpc(A, B, Q, Qf, R, cfg);
// 编译后整个求解器只占用固定大小的栈内存
```

### 4.3 代码生成：将 MPC 转为纯 C 代码

OSQP 提供了代码生成功能，将特定问题编译为零依赖的 C 代码：

```cpp
// osqp_codegen_wrapper.hpp
// 演示如何准备 OSQP 代码生成的数据结构

// Step 1: 离线（在 PC 上）运行此函数，生成 C 代码
void generateEmbeddedCode(
    const Eigen::MatrixXd& H,
    const Eigen::MatrixXd& G,
    const std::string& output_dir)
{
    // 将问题数据转为 OSQP 格式
    Eigen::SparseMatrix<double> P = denseToSparse(H).triangularView<Eigen::Upper>();
    Eigen::SparseMatrix<double> A = denseToSparse(G);

    // 由于约束右端 h 随状态变化，这里填入占位符（全零）
    // 运行时通过 osqp_update_data_vec 更新
    Eigen::VectorXd q  = Eigen::VectorXd::Zero(H.rows());
    Eigen::VectorXd l  = Eigen::VectorXd::Constant(G.rows(), -1e30);
    Eigen::VectorXd u  = Eigen::VectorXd::Zero(G.rows());

    // 调用 OSQP 代码生成接口
    // osqp_codegen(solver, output_dir.c_str(), "mpc_qp", &codegen_settings);
    // 生成文件：mpc_qp_data.c, mpc_qp_data.h, mpc_qp_solve.c

    std::cout << "代码已生成到 " << output_dir << "\n";
    std::cout << "在嵌入式端：\n";
    std::cout << "  #include \"mpc_qp_data.h\"\n";
    std::cout << "  osqp_update_data_vec(solver, q_new, l_new, u_new);\n";
    std::cout << "  osqp_solve(solver);\n";
}
```

### 4.4 定点数实现（适用于无 FPU 的 MCU）

```cpp
// fixed_point_qp.hpp
// 将 QP 的核心计算用定点数实现

#include <cstdint>
#include <algorithm>

// Q16.16 定点数格式（16位整数部分 + 16位小数部分）
// 表示范围：约 ±32768，精度约 1.5e-5
using Fixed32 = int32_t;
static constexpr int FRAC_BITS = 16;
static constexpr Fixed32 ONE_FIXED = (1 << FRAC_BITS);

// 浮点 → 定点
inline Fixed32 toFixed(double x) {
    return static_cast<Fixed32>(x * ONE_FIXED);
}

// 定点 → 浮点
inline double toDouble(Fixed32 x) {
    return static_cast<double>(x) / ONE_FIXED;
}

// 定点乘法（防止溢出：使用 64 位中间结果）
inline Fixed32 fixedMul(Fixed32 a, Fixed32 b) {
    return static_cast<Fixed32>(
        (static_cast<int64_t>(a) * b) >> FRAC_BITS);
}

// 定点矩阵-向量乘法
// y = A * x，A (m×n)，x (n)，y (m)，均为 Fixed32
template<int M, int N>
void fixedMatVec(const Fixed32 A[M][N],
                 const Fixed32 x[N],
                 Fixed32 y[M]) {
    for (int i = 0; i < M; ++i) {
        int64_t acc = 0;
        for (int j = 0; j < N; ++j) {
            acc += static_cast<int64_t>(A[i][j]) * x[j];
        }
        // 右移 FRAC_BITS 完成定点对齐
        y[i] = static_cast<Fixed32>(acc >> FRAC_BITS);
    }
}

// 简单定点 MPC（无约束版本，用于 MCU）
// 离线将 H^{-1} * calB' * barQ 预计算为一个增益矩阵
// 在线只做矩阵向量乘法
template<int NU_TOTAL, int NX_TOTAL>
class FixedPointMPC {
public:
    using GainMatrix = Fixed32[NU_TOTAL][NX_TOTAL + NX_TOTAL];
    // 增益 = -H^{-1} * 2 * calB' * barQ
    // = -H^{-1} * [2*calB'*barQ*calA（对x0的增益）,
    //              -2*calB'*barQ（对X_ref的增益）]

    // 离线预计算（在 PC 上完成，结果固化到嵌入式代码）
    static void precompute(const Eigen::MatrixXd& H,
                           const Eigen::MatrixXd& calB,
                           const Eigen::MatrixXd& barQ,
                           const Eigen::MatrixXd& calA,
                           Fixed32 gain_out[NU_TOTAL][NX_TOTAL + NX_TOTAL]) {
        // K = H^{-1} * 2 * calB' * barQ
        Eigen::MatrixXd K = H.ldlt().solve(
            2.0 * calB.transpose() * barQ);

        // 对 x0 的增益（K * calA）
        Eigen::MatrixXd Kx = K * calA;
        // 对 X_ref 的增益（-K）
        Eigen::MatrixXd Kr = -K;

        // 转定点（假设 NU_TOTAL = N*NU，NX_TOTAL = NX）
        for (int i = 0; i < NU_TOTAL; ++i) {
            for (int j = 0; j < NX_TOTAL; ++j) {
                gain_out[i][j] = toFixed(Kx(i, j));
            }
        }
        // X_ref 部分（N*NX 列）可类似存储
        // 此处简化，实际按需实现
    }

    // 在线求解（纯定点整数运算）
    static void solve(
        const Fixed32 gain[NU_TOTAL][NX_TOTAL],
        const Fixed32 x0[NX_TOTAL],            // 当前状态
        Fixed32 u_out[/* NU */],               // 输出第一步控制量
        Fixed32 u_min[/* NU */],
        Fixed32 u_max[/* NU */],
        int NU)
    {
        Fixed32 U_opt[NU_TOTAL];
        fixedMatVec<NU_TOTAL, NX_TOTAL>(gain, x0, U_opt);

        // 饱和
        for (int i = 0; i < NU; ++i) {
            u_out[i] = std::max(u_min[i], std::min(u_max[i], U_opt[i]));
        }
    }
};
```

---

## 五、MPC 与其他控制器的协同

### 5.1 MPC + PID 级联：内外环架构

```cpp
// ============================================================
// 外环 MPC（慢，计算轨迹参考）+ 内环 PID（快，执行跟踪）
//
// 典型应用：
//   - 四旋翼：MPC 计算位置/速度参考，PID 控制姿态角
//   - 工业机器人：MPC 计算关节速度参考，驱动器内置 PID 执行
//
// 时间尺度分离：
//   外环 MPC：Ts_MPC = 50ms（20Hz）
//   内环 PID：Ts_PID = 5ms（200Hz）
// ============================================================
class CascadeController {
public:
    struct InnerLoopRef {
        Eigen::VectorXd velocity_ref;   // MPC 输出：速度参考
        Eigen::VectorXd accel_ff;       // MPC 前馈：加速度
    };

    CascadeController(/* 参数省略 */)
        : mpc_counter_(0), Ts_ratio_(10) {}

    // 主控制周期（内环 PID 频率调用）
    Eigen::VectorXd update(const Eigen::VectorXd& x_meas,
                           const Eigen::VectorXd& x_ref_global) {
        ++mpc_counter_;

        // 外环 MPC：每 Ts_ratio_ 步更新一次
        if (mpc_counter_ >= Ts_ratio_) {
            mpc_counter_ = 0;
            inner_ref_ = computeOuterLoop(x_meas, x_ref_global);
        }

        // 内环 PID：每步执行
        return computeInnerLoop(x_meas, inner_ref_);
    }

private:
    InnerLoopRef computeOuterLoop(const Eigen::VectorXd& x,
                                   const Eigen::VectorXd& x_ref) {
        // MPC 求解位置/速度轨迹
        auto result = mpc_.solve(x, x_ref, u_prev_mpc_);
        u_prev_mpc_ = result.u_opt;

        InnerLoopRef ref;
        ref.velocity_ref = result.u_opt;  // MPC 输出作为速度参考
        ref.accel_ff     = result.U_sequence.segment(
                               sys_.m, sys_.m);  // 前一步的控制量差分
        return ref;
    }

    Eigen::VectorXd computeInnerLoop(
        const Eigen::VectorXd& x,
        const InnerLoopRef& ref) {
        // PID 跟踪速度参考（加前馈）
        Eigen::VectorXd error = ref.velocity_ref - x.tail(x.size()/2);
        integral_ += error * Ts_pid_;

        Eigen::VectorXd u = Kp_ * error
                          + Ki_ * integral_
                          + Kd_ * (error - prev_error_) / Ts_pid_
                          + ref.accel_ff;  // 前馈补偿

        prev_error_ = error;
        return u;
    }

    OSQPMPCSolver mpc_;
    DiscreteLinearSystem sys_;
    InnerLoopRef inner_ref_;
    Eigen::VectorXd u_prev_mpc_, integral_, prev_error_;
    Eigen::MatrixXd Kp_, Ki_, Kd_;
    int mpc_counter_, Ts_ratio_;
    double Ts_pid_ = 0.005;
};
```

### 5.2 MPC + 安全过滤器（CBF）

控制障碍函数（Control Barrier Function）作为安全过滤层，对 MPC 输出进行安全修正：

```cpp
// ============================================================
// 安全过滤器：CBF-QP
//
// MPC 计算标称控制量 u_nom，CBF-QP 在其基础上
// 求解离 u_nom 最近的、满足安全约束的控制量 u_safe：
//
// min_{u} ||u - u_nom||²
// s.t.  ∇h(x)^T * f(x,u) + α(h(x)) >= 0   (CBF 安全条件)
//
// h(x): 障碍函数（h(x) > 0 表示安全区域内）
// α(): 类 K 函数（如 α(h) = γ*h，γ > 0）
// ============================================================
class CBFSafetyFilter {
public:
    CBFSafetyFilter(double gamma = 1.0) : gamma_(gamma) {}

    // 安全修正（以避障为例：h(x) = ||x_pos - obs||² - r²）
    Eigen::VectorXd filter(
        const Eigen::VectorXd& u_nom,      // MPC 标称控制量
        const Eigen::VectorXd& x,          // 当前状态
        const Eigen::VectorXd& x_obs,      // 障碍物位置
        double obs_radius,                  // 障碍物半径
        const Eigen::MatrixXd& Lf_h,       // ∇h * f（李导数，需线性化）
        const Eigen::MatrixXd& Lg_h)       // ∇h * g（控制增益项）
    {
        // 计算当前障碍函数值 h(x)
        double h = computeCBF(x, x_obs, obs_radius);

        // CBF 约束：Lg_h * u >= -Lf_h - gamma * h
        // 即：A_cbf * u <= b_cbf
        Eigen::VectorXd b_cbf(1);
        b_cbf(0) = Lf_h(0) + gamma_ * h;  // 右端

        // 如果标称控制量已满足安全约束，直接返回
        if (Lg_h * u_nom >= b_cbf) return u_nom;

        // 否则求解 CBF-QP
        // min 0.5*(u-u_nom)'*(u-u_nom)  s.t. Lg_h*u >= b_cbf
        // 解析解（单约束时）：
        // u_safe = u_nom + Lg_h^T * (Lg_h*Lg_h^T)^{-1} * (b_cbf - Lg_h*u_nom)
        Eigen::MatrixXd LgLgT = Lg_h * Lg_h.transpose();
        Eigen::VectorXd violation = b_cbf - Lg_h * u_nom;

        if (LgLgT(0, 0) < 1e-10) return u_nom;  // 无法修正

        Eigen::VectorXd u_safe = u_nom +
            Lg_h.transpose() * violation / LgLgT(0, 0);

        return u_safe;
    }

private:
    double computeCBF(const Eigen::VectorXd& x,
                       const Eigen::VectorXd& obs, double r) const {
        double dx = x(0) - obs(0);
        double dy = x(1) - obs(1);
        return dx*dx + dy*dy - r*r;  // h > 0 表示在安全区域内
    }

    double gamma_;
};
```

---

## 六、完整工程示例：带全套保障的 MPC 控制器

```cpp
// production_mpc.hpp
// 整合：积分增广 + 卡尔曼滤波 + OSQP + 热启动 + 健康监控

#pragma once
#include "kalman_filter.hpp"
#include "integral_augmentation.hpp"
#include "osqp_solver.hpp"
#include "osqp_solver.hpp"  // 从第四篇

class ProductionMPC {
public:
    struct ProductionConfig {
        // 系统
        DiscreteLinearSystem sys;
        double Ts;

        // MPC
        MPCConfig   mpc_cfg;
        MPCWeights  weights;
        MPCBounds   bounds;
        OSQPMPCSolver::SolverConfig solver_cfg;

        // 卡尔曼滤波
        Eigen::MatrixXd Q_process;   // 过程噪声协方差
        Eigen::MatrixXd R_meas;      // 测量噪声协方差

        // 积分增广
        bool   enable_integral = true;
        double anti_windup     = 5.0;

        // 故障恢复
        int    max_consecutive_failures = 3;
        double fallback_gain            = 0.9;
    };

    ProductionMPC(const ProductionConfig& cfg)
        : cfg_(cfg)
    {
        // 1. （可选）积分增广
        if (cfg_.enable_integral) {
            aug_ = buildIntegralAugmentation(
                cfg_.sys.A, cfg_.sys.B, cfg_.sys.C, cfg_.Ts);

            // 用增广系统替换原始系统
            DiscreteLinearSystem aug_sys;
            aug_sys.A = aug_.A_aug;
            aug_sys.B = aug_.B_aug;
            aug_sys.C = aug_.C_aug;
            aug_sys.n = aug_.n_orig + aug_.n_int;
            aug_sys.m = cfg_.sys.m;
            aug_sys.p = cfg_.sys.p;

            // 更新权重维数
            MPCWeights aug_weights = cfg_.weights;
            int n_aug = aug_sys.n;
            aug_weights.Q  = Eigen::MatrixXd::Zero(n_aug, n_aug);
            aug_weights.Q.topLeftCorner(cfg_.sys.n, cfg_.sys.n) =
                cfg_.weights.Q;
            aug_weights.Qf = aug_weights.Q;
            aug_weights.R  = cfg_.weights.R;

            mpc_ = std::make_unique<OSQPMPCSolver>(
                aug_sys, aug_weights, cfg_.bounds,
                cfg_.mpc_cfg, cfg_.solver_cfg);
        } else {
            mpc_ = std::make_unique<OSQPMPCSolver>(
                cfg_.sys, cfg_.weights, cfg_.bounds,
                cfg_.mpc_cfg, cfg_.solver_cfg);
        }

        // 2. 卡尔曼滤波（对原始系统）
        int n = cfg_.sys.n;
        kf_ = std::make_unique<KalmanFilter>(
            cfg_.sys.A, cfg_.sys.B, cfg_.sys.C,
            cfg_.Q_process, cfg_.R_meas,
            Eigen::VectorXd::Zero(n),
            Eigen::MatrixXd::Identity(n, n));

        // 3. 初始化其他状态
        u_prev_       = Eigen::VectorXd::Zero(cfg_.sys.m);
        failure_count_ = 0;
    }

    // 主控制接口（每个采样周期调用）
    Eigen::VectorXd step(const Eigen::VectorXd& y_meas,
                          const Eigen::VectorXd& y_ref) {
        // ── 1. 状态估计 ──
        kf_->update(y_meas);
        Eigen::VectorXd x_est = kf_->stateEstimate();

        // ── 2. 积分状态更新 ──
        Eigen::VectorXd x_ctrl = x_est;
        if (cfg_.enable_integral) {
            if (x_aug_.size() == 0)
                x_aug_ = buildAugmentedState(x_est, aug_.n_int);
            else
                x_aug_.head(cfg_.sys.n) = x_est;

            updateIntegralState(x_aug_, y_meas, y_ref,
                                aug_.n_orig, cfg_.Ts,
                                cfg_.anti_windup);
            x_ctrl = x_aug_;
        }

        // ── 3. 构建参考轨迹 ──
        int n_ctrl = x_ctrl.size();
        Eigen::VectorXd x_ref_aug = Eigen::VectorXd::Zero(n_ctrl);
        // 只设置原始状态分量的参考，积分状态目标为零
        x_ref_aug.head(std::min(n_ctrl, (int)y_ref.size())) = y_ref;

        Eigen::VectorXd X_ref(cfg_.mpc_cfg.N * n_ctrl);
        for (int k = 0; k < cfg_.mpc_cfg.N; ++k)
            X_ref.segment(k * n_ctrl, n_ctrl) = x_ref_aug;

        // ── 4. MPC 求解 ──
        auto result = mpc_->solve(x_ctrl, X_ref, u_prev_);
        auto stats  = mpc_->getLastStats();

        // ── 5. 故障处理 ──
        Eigen::VectorXd u_out;
        if (result.solved) {
            u_out = result.u_opt;
            failure_count_ = 0;
        } else {
            ++failure_count_;
            if (failure_count_ <= cfg_.max_consecutive_failures) {
                // 使用指数衰减的上一步控制量
                u_out = std::pow(cfg_.fallback_gain,
                                  failure_count_) * u_prev_;
                fprintf(stderr, "[MPC] 求解失败（%d次），使用衰减控制量\n",
                        failure_count_);
            } else {
                // 超过最大连续失败次数：紧急停车
                u_out = Eigen::VectorXd::Zero(cfg_.sys.m);
                fprintf(stderr, "[MPC] 紧急停车！连续失败 %d 次\n",
                        failure_count_);
            }

            // 记录诊断信息
            monitor_.logFailure(stats);
        }

        // ── 6. 卡尔曼预测 ──
        kf_->predict(u_out);

        // ── 7. 更新监控 ──
        monitor_.update(stats, x_est, cfg_.bounds);

        u_prev_ = u_out;
        return u_out;
    }

    // 健康状态查询
    bool isHealthy() const { return monitor_.isHealthy(); }
    MPCMonitor::HealthReport healthReport() const {
        return monitor_.report();
    }

private:
    ProductionConfig            cfg_;
    std::unique_ptr<OSQPMPCSolver> mpc_;
    std::unique_ptr<KalmanFilter>  kf_;
    AugmentedSystem             aug_;
    Eigen::VectorXd             u_prev_;
    Eigen::VectorXd             x_aug_;
    MPCMonitor                  monitor_;
    int                         failure_count_;
};
```

---

## 总结

本篇覆盖了将 MPC 从实验室带到生产环境所需的全套工程技能：

```
┌──────────────────────────────────────────────────────────────┐
│                   生产级 MPC 的技术栈                         │
├─────────────────────────────────────────────────────────────┤
│  调参层                                                      │
│    ● Bryson 法则确定初始权重比例                              │
│    ● ISE / ITAE / 调节时间评估性能                           │
│    ● 症状诊断器自动识别 Q/R 失衡                             │
│    ● DARE 计算最优终端权重 Qf                                │
├─────────────────────────────────────────────────────────────┤
│  鲁棒性层                                                    │
│    ● 积分增广：消除常值扰动稳态误差                           │
│    ● 扰动观测器 DOB：主动估计并前馈补偿                      │
│    ● Offset-Free MPC：工业标准抗扰方案                      │
│    ● 卡尔曼滤波：噪声测量下的最优状态估计                    │
├─────────────────────────────────────────────────────────────┤
│  嵌入式层                                                    │
│    ● 静态模板化 MPC：零堆内存分配                            │
│    ● OSQP 代码生成：纯 C 代码无依赖                         │
│    ● Q16.16 定点数：无 FPU 的 MCU 实现                      │
├─────────────────────────────────────────────────────────────┤
│  协同层                                                      │
│    ● MPC + PID 级联：外环规划 + 内环执行                     │
│    ● MPC + CBF：安全过滤器保障约束永远满足                   │
│    ● 故障安全：分级降级 → 衰减控制 → 紧急停车               │
└─────────────────────────────────────────────────────────────┘
```

---

**下一篇**：第七篇（终篇）— MPC 前沿专题：Tube MPC（鲁棒）、随机 MPC（Stochastic MPC）、Learning-based MPC（数据驱动），以及在工业界的完整落地案例分析。

---

## 附录 A：输出反馈 MPC 与观测器分离原理

### A.1 状态 MPC vs 输出 MPC

到此为止本系列默认**全状态可测**，现实中很少满足：

| 应用 | 可测量 | 不可测但需要 |
|------|------|------------|
| 车辆 | 速度、转向角、IMU | 横向速度 $\dot{y}$、侧偏角 $\beta$ |
| 化工反应釜 | 温度 | 浓度、反应速率 |
| 机器人关节 | 位置编码器 | 速度（数值微分噪声大）、外部力 |

**输出反馈 MPC** = 状态估计器（Observer / KF）+ 状态 MPC。

### A.2 朴素架构

```
y_k → [Kalman Filter] → x̂_k → [MPC] → u_k
                  ↑__________________|
```

在线步骤：

1. **预测**：$\hat{x}_{k|k-1} = A \hat{x}_{k-1|k-1} + B u_{k-1}$
2. **更新**：$\hat{x}_{k|k} = \hat{x}_{k|k-1} + L(y_k - C\hat{x}_{k|k-1})$
3. **MPC 求解**：用 $\hat{x}_{k|k}$ 作为 $x_0$ 求 QP
4. 执行 $u_k = u^*_{0|k}$

### A.3 分离原理（Separation Principle）

**线性 + 高斯噪声**情形下：

> LQG = LQR + KF，且观测器与控制器**可独立设计**。增益 $K$ 仅依赖 $(A, B, Q, R)$，增益 $L$ 仅依赖 $(A, C, W, V)$。

但 MPC 加约束后：**分离原理一般不成立**！原因：

1. KF 的状态估计有不确定性 $\Sigma_k$，MPC 用 $\hat{x}$ 当真值会侵犯约束
2. 估计误差大时，MPC 求解可能"乐观地"违反约束
3. 时变扰动下 KF 与 MPC 互相干扰

### A.4 何时分离原理近似有效

| 条件 | 说明 |
|------|------|
| 扰动小（$\|w\|, \|v\| \ll$ 状态量级）| 估计误差可忽略 |
| 约束远离最优解（约束很少激活） | 估计误差不会触发约束违反 |
| KF 收敛快（极点远在控制极点之内） | 估计误差衰减快于控制响应 |

工程经验：**KF 极点设计在控制带宽 3~5 倍**（即响应快得多），分离原理近似成立。

### A.5 严格做法：考虑估计不确定性

把 KF 的协方差 $\Sigma_k$ 用于**收紧约束**（constraint tightening）：

$$\mathbb{X}_k = \mathbb{X} \ominus B_\sigma(\Sigma_k)$$

其中 $B_\sigma$ 是与置信度对应的椭球（如 99% → $3\sigma$）。这就是"鲁棒输出 MPC"，与第七篇 Tube MPC 思路一致。

```cpp
// 用 KF 协方差收紧约束
class OutputMPC {
    KalmanFilter kf_;
    LinearMPC mpc_;
    double sigma_factor_ = 3.0;  // 99% 置信度

public:
    Eigen::VectorXd step(const Eigen::VectorXd& y) {
        kf_.predict();
        kf_.update(y);
        const auto& x_hat = kf_.state();
        const auto& P_est = kf_.covariance();

        // 根据估计不确定性收紧状态约束
        Eigen::VectorXd tighten = sigma_factor_ * P_est.diagonal().cwiseSqrt();
        mpc_.setStateBoundsTighten(tighten);

        return mpc_.solve(x_hat);
    }
};
```

### A.6 输出 MPC 调试 5 步法

```
1. 关闭 MPC，只跑 KF：检验 ŷ vs y 残差是否白噪声 (innovation test)
2. 关闭 KF，假装全状态可测：检验 MPC 性能（理论上限）
3. 联合运行：对比闭环跟踪误差 与第 2 步差距
   差距 < 10%  → KF 设计 OK
   差距 > 30%  → KF 极点太慢、Q_kf/R_kf 选错
4. 注入已知扰动 → 检查 KF 能否估出扰动方向
5. 摆动测试：突然给 y_meas 一个跳变 → KF 应在 5 步内回收，MPC 不应产生执行器饱和
```

### A.7 LMI 视角的输出反馈 MPC

对于**有约束 + 输出反馈**的最一般情形，闭环稳定性可表为线性矩阵不等式（LMI）：

$$
\begin{bmatrix}
\bar{A}^T P \bar{A} - P + \bar{Q} & \bar{A}^T P \bar{B} \\
\bar{B}^T P \bar{A} & \bar{R} + \bar{B}^T P \bar{B}
\end{bmatrix} \succ 0
$$

其中 $(\bar{A}, \bar{B})$ 是闭环（包含 KF 与 MPC）增广系统。$P$ 通过 LMI 求解器（如 SDPT3、MOSEK）解出，给出**可证稳定的 $K_f, L_f$ 联合设计**。

工程上很少手工解 LMI，但理解其存在能避免"分离原理的盲目使用"。

---

## 附录 B：现场调试 5 类故障速查表

> 完整调试方法论见第九篇《MPC 现场调试指南》。本节是简版应急手册。

| 症状 | 可能原因 | 第一招诊断 | 修复方向 |
|------|---------|----------|---------|
| 跟踪误差稳态偏移 | 模型偏差 / 常值扰动 | 加 DOB 估计扰动 → 看是否非零 | 积分增广或 DOB 前馈 |
| 跟踪振荡 | $R$ 太小 / 模型延迟未补偿 | 求解结果 $u$ 高频 vs 低频？ | 增大 $R$；加入延迟模型 |
| 求解时间忽长 | 热启动失效（参考突变） | log 求解 iter 数 | 检测突变 → 主动冷启动 |
| 偶发不可行 | 软约束未启用 | OSQP 返回码 | 改用软约束 + 大权重 |
| 实车性能<仿真 | Sim-Real Gap | 注入实测扰动到仿真比较 | 模型辨识 / DOB |

---

## 附录 C：与上层规划/下层执行的接口

### C.1 三层架构的典型频率

```
路径规划 (10 Hz)
    ↓ 路径点 [(x, y, ψ, v_target)]
轨迹平滑 (50 Hz) ← 把离散点拟合为参数化光滑曲线
    ↓ Frenet 坐标参考
MPC 控制 (100 Hz) ← 横向 δ + 纵向 a 输出
    ↓ CAN 报文
执行器 (200~500 Hz)
```

### C.2 多频率接口的关键问题

| 问题 | 解决 |
|------|------|
| 规划 10 Hz、控制 100 Hz：参考"楼梯状"突变 | 控制层做时间插值，输出连续参考 |
| MPC 100 Hz、CAN 50 Hz：丢命令 | CAN 缓存最后一帧；MPC 输出 ZOH |
| 执行器响应慢于 MPC 周期 | 把执行器一阶滞后建进 MPC 模型 |
| 时间戳不同步 | 用单一硬件时钟（PPS / IEEE 1588） |

### C.3 延迟补偿（Dead-Time Compensation）

CAN + 执行器累计延迟 $\tau \approx 30~50$ ms。控制周期 10 ms 时，相当于 3~5 个采样步——必须补偿。

**Smith 预估器思路**：把 $u_k$ 看作"立即生效"的虚拟控制，在 MPC 内部维护一个**延迟队列**：

```cpp
class DelayBuffer {
    std::deque<Eigen::VectorXd> queue_;
    int delay_steps_;
public:
    DelayBuffer(int d) : delay_steps_(d) {}
    Eigen::VectorXd push(const Eigen::VectorXd& u) {
        queue_.push_back(u);
        if (queue_.size() > delay_steps_) {
            auto delayed = queue_.front();
            queue_.pop_front();
            return delayed;
        }
        return Eigen::VectorXd::Zero(u.size());
    }
};

// 在 MPC 内部把延迟反映到预测：
// x̂_0 = 当前测量 x_k
// 用过去 d 步的真实输入 u_{k-d}, ..., u_{k-1} 把模型推进到 k+d
// 然后从 k+d 开始 MPC 求解
```

效果：完全补偿确定性延迟；剩余抖动由 DOB 处理。

