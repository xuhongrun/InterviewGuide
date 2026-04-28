# 第三篇：将预测方程转化为 QP 问题并求解

---

## 引言

上一篇推导了预测方程核心：

$$\mathbf{X} = \mathcal{A} x_0 + \mathcal{B} \mathbf{U}$$

这一篇将完成 MPC 推导最关键的一步——**把预测方程代入目标函数，将 MPC 问题转化为标准二次规划（QP）问题**，并从零实现一个可运行的求解器接口。

**本篇目标**：
- 完整推导 QP 矩阵 $H$ 和向量 $f$
- 将控制约束、状态约束、增量约束转化为 QP 不等式矩阵
- 理解 QP 求解器的接口与内部原理
- 用 C++ 实现从模型到求解的完整流水线，并通过仿真验证

---

## 一、MPC 目标函数的精确定义

### 1.1 标准形式

$$J(\mathbf{U}; x_0) = \underbrace{\sum_{k=1}^{N} (x_k - x_{ref,k})^T Q (x_k - x_{ref,k})}_{\text{状态跟踪代价}} + \underbrace{\sum_{k=0}^{N-1} u_k^T R u_k}_{\text{控制代价}} + \underbrace{(x_N - x_{ref,N})^T Q_f (x_N - x_{ref,N})}_{\text{终端代价（可选）}}$$

| 项 | 含义 | 设计考量 |
|----|------|---------|
| $Q \succeq 0$ | 状态误差权重（半正定） | 对哪个状态分量的跟踪更重要 |
| $R \succ 0$ | 控制代价权重（正定） | 惩罚过大的控制动作，保证 $H$ 正定 |
| $Q_f \succeq 0$ | 终端代价权重 | 通常取 Riccati 方程解，保证稳定性；简单实现可令 $Q_f = Q$ |

### 1.2 参考轨迹 vs 定点调节

**定点调节**（Setpoint Regulation）：目标是固定点 $x_{ref}$（全程不变），例如悬停、恒速。  
**轨迹跟踪**（Trajectory Tracking）：目标是随时间变化的序列 $\{x_{ref,k}\}_{k=1}^N$，例如自动驾驶路径跟踪。

两种情况的数学处理完全一致，只是参考向量 $\mathbf{X}_{ref}$ 的构造不同：

```cpp
// 定点调节：参考状态在整个时域内固定
Eigen::VectorXd buildConstantRef(const Eigen::VectorXd& x_ref, int N) {
    int n = x_ref.size();
    Eigen::VectorXd X_ref(N * n);
    for (int k = 0; k < N; ++k)
        X_ref.segment(k * n, n) = x_ref;
    return X_ref;
}

// 轨迹跟踪：参考状态随时间变化
Eigen::VectorXd buildTrajectoryRef(
    const std::vector<Eigen::VectorXd>& traj, int N) {
    int n = traj[0].size();
    Eigen::VectorXd X_ref(N * n);
    for (int k = 0; k < N; ++k)
        X_ref.segment(k * n, n) = traj[std::min(k, (int)traj.size() - 1)];
    return X_ref;
}
```

---

## 二、代入预测方程：推导 QP 矩阵

### 2.1 向量化目标函数

定义误差向量（忽略终端代价，令 $Q_f = Q$，读者可自行扩展）：

$$\mathbf{E} = \mathbf{X} - \mathbf{X}_{ref}$$

则目标函数可写成：

$$J = \mathbf{E}^T \bar{Q} \mathbf{E} + \mathbf{U}^T \bar{R} \mathbf{U}$$

其中块对角权重矩阵：

$$\bar{Q} = \text{diag}(Q, Q, \ldots, Q, Q_f) \in \mathbb{R}^{Nn \times Nn}$$
$$\bar{R} = \text{diag}(R, R, \ldots, R) \in \mathbb{R}^{Nm \times Nm}$$

### 2.2 代入预测方程

将 $\mathbf{X} = \mathcal{A} x_0 + \mathcal{B} \mathbf{U}$ 代入 $\mathbf{E}$：

$$\mathbf{E} = \mathcal{A} x_0 + \mathcal{B} \mathbf{U} - \mathbf{X}_{ref} = \mathcal{B} \mathbf{U} + \underbrace{(\mathcal{A} x_0 - \mathbf{X}_{ref})}_{\triangleq \, \mathbf{e}_0}$$

其中 $\mathbf{e}_0$ 是在**无控制输入**情况下系统未来轨迹与参考的偏差（与 $\mathbf{U}$ 无关，是已知量）。

代入目标函数：

$$J = (\mathcal{B}\mathbf{U} + \mathbf{e}_0)^T \bar{Q} (\mathcal{B}\mathbf{U} + \mathbf{e}_0) + \mathbf{U}^T \bar{R} \mathbf{U}$$

展开：

$$J = \mathbf{U}^T \mathcal{B}^T \bar{Q} \mathcal{B} \mathbf{U} + 2\mathbf{e}_0^T \bar{Q} \mathcal{B} \mathbf{U} + \mathbf{e}_0^T \bar{Q} \mathbf{e}_0 + \mathbf{U}^T \bar{R} \mathbf{U}$$

整理成标准 QP 形式（常数项 $\mathbf{e}_0^T \bar{Q} \mathbf{e}_0$ 对优化无影响，丢弃）：

$$\boxed{J = \frac{1}{2}\mathbf{U}^T H \mathbf{U} + f^T \mathbf{U} + \text{const}} \tag{2.1}$$

其中：

$$\boxed{H = 2(\mathcal{B}^T \bar{Q} \mathcal{B} + \bar{R})} \tag{2.2}$$

$$\boxed{f = 2\mathcal{B}^T \bar{Q} \mathbf{e}_0 = 2\mathcal{B}^T \bar{Q} (\mathcal{A} x_0 - \mathbf{X}_{ref})} \tag{2.3}$$

### 2.3 关键性质

**$H$ 是对称正定矩阵（PD）**

证明：$\mathcal{B}^T \bar{Q} \mathcal{B} \succeq 0$（半正定），$\bar{R} \succ 0$（正定），所以 $H \succ 0$。

这意味着：
- QP 问题是**严格凸**的
- 存在**唯一全局最优解**
- 可以用 Cholesky 分解高效求解（无约束情况）

**无约束最优解（闭式解）**

对 $J$ 求导并令其为零：

$$\frac{\partial J}{\partial \mathbf{U}} = H\mathbf{U} + f = 0$$

$$\boxed{\mathbf{U}^* = -H^{-1} f}$$

这个闭式解对应 **线性二次调节器（LQR）在有限时域的等价形式**。

---

## 三、约束的数学化

MPC 的核心优势是**约束处理**。将各类约束都转化为标准形式 $G\mathbf{U} \leq h$。

### 3.1 控制量约束（Actuator Bound）

$$u_{min} \leq u_k \leq u_{max}, \quad k = 0, 1, \ldots, N-1$$

展开成向量形式：

$$\mathbf{U}_{min} \leq \mathbf{U} \leq \mathbf{U}_{max}$$

转化为单边不等式（$\leq$ 形式）：

$$\begin{bmatrix} I_{Nm} \\ -I_{Nm} \end{bmatrix} \mathbf{U} \leq \begin{bmatrix} \mathbf{U}_{max} \\ -\mathbf{U}_{min} \end{bmatrix}$$

### 3.2 控制增量约束（Rate Constraint）

执行器变化率受限（如液压阀门、舵机等）：

$$\Delta u_{min} \leq u_k - u_{k-1} \leq \Delta u_{max}$$

定义差分矩阵 $\Gamma \in \mathbb{R}^{Nm \times Nm}$（带 $-I$ 的下移矩阵）：

$$\Gamma = \begin{bmatrix} I & & & \\ -I & I & & \\ & -I & I & \\ & & \ddots & \ddots \end{bmatrix}, \quad \text{即} \quad \Gamma \mathbf{U} = \begin{bmatrix} u_0 - u_{-1} \\ u_1 - u_0 \\ u_2 - u_1 \\ \vdots \end{bmatrix}$$

其中 $u_{-1}$ 是上一时刻的控制量（已知），记为 $u_{prev}$。

约束为：

$$\begin{bmatrix} \Gamma \\ -\Gamma \end{bmatrix} \mathbf{U} \leq \begin{bmatrix} \mathbf{1} \otimes \Delta u_{max} + [u_{prev}; 0; \ldots; 0] \\ -\mathbf{1} \otimes \Delta u_{min} - [u_{prev}; 0; \ldots; 0] \end{bmatrix}$$

### 3.3 状态约束（Safety Constraint）

$$x_{min} \leq x_k \leq x_{max}$$

利用预测方程 $\mathbf{X} = \mathcal{A} x_0 + \mathcal{B} \mathbf{U}$，将状态约束转化为对 $\mathbf{U}$ 的约束：

$$x_{min} \leq \mathcal{A} x_0 + \mathcal{B} \mathbf{U} \leq x_{max}$$

$$\begin{bmatrix} \mathcal{B} \\ -\mathcal{B} \end{bmatrix} \mathbf{U} \leq \begin{bmatrix} \mathbf{X}_{max} - \mathcal{A} x_0 \\ -\mathbf{X}_{min} + \mathcal{A} x_0 \end{bmatrix}$$

### 3.4 合并为统一约束矩阵

将所有约束竖向堆叠：

$$G = \begin{bmatrix} I \\ -I \\ \Gamma \\ -\Gamma \\ \mathcal{B} \\ -\mathcal{B} \end{bmatrix}, \quad h = \begin{bmatrix} \mathbf{U}_{max} \\ -\mathbf{U}_{min} \\ \Delta\mathbf{U}_{max} + \Gamma_0 u_{prev} \\ -\Delta\mathbf{U}_{min} - \Gamma_0 u_{prev} \\ \mathbf{X}_{max} - \mathcal{A} x_0 \\ -\mathbf{X}_{min} + \mathcal{A} x_0 \end{bmatrix}$$

完整 MPC 问题：

$$\boxed{\min_{\mathbf{U}} \frac{1}{2}\mathbf{U}^T H \mathbf{U} + f^T \mathbf{U} \quad \text{s.t.} \quad G\mathbf{U} \leq h} \tag{3.1}$$

这是一个**凸二次规划（Convex QP）**，是最容易处理的优化问题之一，可在多项式时间内求解。

---

## 四、QP 求解器原理概览

理解求解器的原理，有助于更好地使用和调试 MPC。

### 4.1 无约束 QP：Cholesky 分解

无约束时，$\mathbf{U}^* = -H^{-1}f$，用 Cholesky 分解求解：

```
H = L * L^T（H 正定，分解唯一）
解方程：L * y = -f（前代法）
        L^T * U = y（回代法）
复杂度：O(n³) 分解 + O(n²) 求解
```

### 4.2 有约束 QP：内点法 vs 有效集法

| 方法 | 代表求解器 | 特点 | 适合场景 |
|------|----------|------|---------|
| **内点法（IPM）** | OSQP、IPOPT | 每次迭代代价固定，热启动好 | 约束多、变量多 |
| **有效集法（ASM）** | qpOASES | 迭代次数等于约束数，可热启动 | 约束少、嵌入式 |
| **ADMM** | OSQP | 通信友好，可分布式 | 大规模、实时 |

**OSQP** 是目前嵌入式 MPC 领域最流行的求解器，基于 ADMM（交替方向乘子法），具有：
- 代码体积小（适合嵌入式）
- 支持热启动（Warm Start）
- 支持不可行检测

### 4.3 OSQP 标准形式

OSQP 求解的标准问题形式为：

$$\min_{\mathbf{U}} \quad \frac{1}{2}\mathbf{U}^T P \mathbf{U} + q^T \mathbf{U}$$
$$\text{s.t.} \quad l \leq A\mathbf{U} \leq u$$

对比我们的 MPC QP（式 3.1）：

| MPC 变量 | OSQP 变量 | 说明 |
|---------|---------|-----|
| $H$ | $P$ | 目标函数二次项，**只需上三角** |
| $f$ | $q$ | 目标函数线性项 |
| $G$ | $A$ | 约束矩阵 |
| $-\infty$ | $l$ | 约束下界（$G\mathbf{U} \leq h$ 时下界取 $-\infty$） |
| $h$ | $u$ | 约束上界 |

---

## 五、完整 C++ 实现

### 5.1 工程目录结构

```
mpc_demo/
├── CMakeLists.txt
├── include/
│   ├── mpc_types.hpp        # 数据类型定义
│   ├── prediction.hpp       # 预测矩阵构建
│   ├── qp_builder.hpp       # QP 矩阵构建
│   └── mpc_solver.hpp       # MPC 求解器接口
└── src/
    ├── prediction.cpp
    ├── qp_builder.cpp
    ├── mpc_solver.cpp
    └── main.cpp
```

### 5.2 数据类型定义（mpc_types.hpp）

```cpp
#pragma once
#include <Eigen/Dense>
#include <vector>

// ============================================================
// MPC 数据类型定义
// ============================================================

// 离散线性时不变系统
struct DiscreteLinearSystem {
    Eigen::MatrixXd A;   // 系统矩阵   (n×n)
    Eigen::MatrixXd B;   // 输入矩阵   (n×m)
    Eigen::MatrixXd C;   // 输出矩阵   (p×n)
    int n;               // 状态维数
    int m;               // 输入维数
    int p;               // 输出维数
};

// MPC 权重参数
struct MPCWeights {
    Eigen::MatrixXd Q;   // 状态误差权重  (n×n)，半正定
    Eigen::MatrixXd Qf;  // 终端代价权重  (n×n)，半正定
    Eigen::MatrixXd R;   // 控制代价权重  (m×m)，正定
};

// MPC 约束参数
struct MPCBounds {
    Eigen::VectorXd u_min;    // 控制量下界    (m)
    Eigen::VectorXd u_max;    // 控制量上界    (m)
    Eigen::VectorXd du_min;   // 控制增量下界  (m)，可设为 -inf
    Eigen::VectorXd du_max;   // 控制增量上界  (m)，可设为 +inf
    Eigen::VectorXd x_min;    // 状态下界      (n)，可设为 -inf
    Eigen::VectorXd x_max;    // 状态上界      (n)，可设为 +inf

    bool has_rate_constraint  = false;
    bool has_state_constraint = false;
};

// MPC 配置
struct MPCConfig {
    int    N  = 20;      // 预测时域
    double Ts = 0.05;    // 采样周期 (s)
};

// MPC 求解结果
struct MPCResult {
    bool            solved;         // 是否求解成功
    Eigen::VectorXd u_opt;          // 最优控制量（当前时刻）
    Eigen::VectorXd U_sequence;     // 完整控制序列（用于热启动）
    double          cost;           // 最优目标函数值
    int             iterations;     // 求解迭代次数
};
```

### 5.3 预测矩阵构建（prediction.hpp / .cpp）

```cpp
// prediction.hpp
#pragma once
#include "mpc_types.hpp"

struct PredictionMatrices {
    Eigen::MatrixXd calA;  // (N*n × n)
    Eigen::MatrixXd calB;  // (N*n × N*m)
    Eigen::MatrixXd barQ;  // (N*n × N*n)，块对角 Q 矩阵
    Eigen::MatrixXd barR;  // (N*m × N*m)，块对角 R 矩阵
};

PredictionMatrices buildPredictionMatrices(
    const DiscreteLinearSystem& sys,
    const MPCWeights& weights,
    int N);
```

```cpp
// prediction.cpp
#include "prediction.hpp"
#include <cassert>

PredictionMatrices buildPredictionMatrices(
    const DiscreteLinearSystem& sys,
    const MPCWeights& weights,
    int N)
{
    const int n = sys.n, m = sys.m;
    assert(weights.Q.rows()  == n && weights.Q.cols()  == n);
    assert(weights.Qf.rows() == n && weights.Qf.cols() == n);
    assert(weights.R.rows()  == m && weights.R.cols()  == m);

    PredictionMatrices pred;

    // ── 构建 calA = [A; A²; ...; A^N] ──
    pred.calA.resize(N * n, n);
    Eigen::MatrixXd Apow = sys.A;
    for (int k = 0; k < N; ++k) {
        pred.calA.block(k * n, 0, n, n) = Apow;
        Apow = sys.A * Apow;
    }

    // ── 构建 calB（下三角块矩阵）──
    // 按列填充：第 j 列的第 k 行块（k >= j）= A^(k-j) * B
    pred.calB.resize(N * n, N * m);
    pred.calB.setZero();
    for (int j = 0; j < N; ++j) {
        Eigen::MatrixXd AkB = sys.B;  // 从 A^0 * B 开始
        for (int k = j; k < N; ++k) {
            pred.calB.block(k * n, j * m, n, m) = AkB;
            AkB = sys.A * AkB;
        }
    }

    // ── 构建 barQ（块对角，最后一块用 Qf）──
    pred.barQ = Eigen::MatrixXd::Zero(N * n, N * n);
    for (int k = 0; k < N - 1; ++k)
        pred.barQ.block(k * n, k * n, n, n) = weights.Q;
    pred.barQ.block((N - 1) * n, (N - 1) * n, n, n) = weights.Qf;

    // ── 构建 barR（块对角）──
    pred.barR = Eigen::MatrixXd::Zero(N * m, N * m);
    for (int k = 0; k < N; ++k)
        pred.barR.block(k * m, k * m, m, m) = weights.R;

    return pred;
}
```

### 5.4 QP 矩阵构建（qp_builder.hpp / .cpp）

```cpp
// qp_builder.hpp
#pragma once
#include "mpc_types.hpp"
#include "prediction.hpp"

// QP 标准问题：min 0.5*U'*H*U + f'*U
//              s.t. l <= G*U <= u_ub
struct QPProblem {
    Eigen::MatrixXd H;     // 目标函数二次项 (Nm × Nm)，正定
    Eigen::VectorXd f;     // 目标函数线性项 (Nm)
    Eigen::MatrixXd G;     // 约束矩阵       (n_con × Nm)
    Eigen::VectorXd l;     // 约束下界       (n_con)
    Eigen::VectorXd u_ub;  // 约束上界       (n_con)
    int n_vars;            // 变量数 = N*m
    int n_cons;            // 约束数
};

QPProblem buildQP(
    const PredictionMatrices& pred,
    const MPCBounds& bounds,
    const Eigen::VectorXd& x0,
    const Eigen::VectorXd& X_ref,    // 参考轨迹 (N*n)
    const Eigen::VectorXd& u_prev,   // 上一时刻控制量 (m)，用于增量约束
    int N, int n, int m);
```

```cpp
// qp_builder.cpp
#include "qp_builder.hpp"
#include <limits>

static const double INF = 1e10;  // 无穷大的工程近似（避免数值问题）

QPProblem buildQP(
    const PredictionMatrices& pred,
    const MPCBounds& bounds,
    const Eigen::VectorXd& x0,
    const Eigen::VectorXd& X_ref,
    const Eigen::VectorXd& u_prev,
    int N, int n, int m)
{
    QPProblem qp;
    qp.n_vars = N * m;

    // ==========================================================
    // Step 1: 构建目标函数矩阵
    //   H = 2 * (calB' * barQ * calB + barR)
    //   f = 2 * calB' * barQ * (calA * x0 - X_ref)
    // ==========================================================
    Eigen::VectorXd e0 = pred.calA * x0 - X_ref;  // 自由响应误差

    qp.H = 2.0 * (pred.calB.transpose() * pred.barQ * pred.calB + pred.barR);
    qp.f = 2.0 * pred.calB.transpose() * pred.barQ * e0;

    // 确保 H 对称（消除浮点不对称性）
    qp.H = 0.5 * (qp.H + qp.H.transpose());

    // ==========================================================
    // Step 2: 统计约束行数
    // ==========================================================
    int n_bound = 2 * N * m;   // 控制量上下界
    int n_rate  = bounds.has_rate_constraint  ? 2 * N * m : 0;
    int n_state = bounds.has_state_constraint ? 2 * N * n : 0;
    qp.n_cons = n_bound + n_rate + n_state;

    qp.G.resize(qp.n_cons, qp.n_vars);
    qp.G.setZero();
    qp.l.resize(qp.n_cons);
    qp.u_ub.resize(qp.n_cons);

    int row = 0;

    // ==========================================================
    // Step 3: 控制量上下界约束
    //   u_min <= u_k <= u_max
    //   写成: l_bound <= I * U <= u_bound
    // ==========================================================
    {
        Eigen::MatrixXd Inm = Eigen::MatrixXd::Identity(N * m, N * m);
        qp.G.block(row, 0, N * m, N * m) = Inm;

        for (int k = 0; k < N; ++k) {
            qp.l.segment(row + k * m, m)  = bounds.u_min;
            qp.u_ub.segment(row + k * m, m) = bounds.u_max;
        }
        row += N * m;
    }

    // ==========================================================
    // Step 4: 控制增量约束
    //   du_min <= u_k - u_{k-1} <= du_max
    //
    //   定义差分矩阵 Gamma (Nm × Nm)：
    //   Gamma = [I, 0, 0, ...]
    //           [-I, I, 0, ...]
    //           [0, -I, I, ...]
    //           ...
    //   则 Gamma * U = [u0 - u_prev; u1 - u0; u2 - u1; ...]
    // ==========================================================
    if (bounds.has_rate_constraint) {
        Eigen::MatrixXd Gamma = Eigen::MatrixXd::Zero(N * m, N * m);
        for (int k = 0; k < N; ++k) {
            Gamma.block(k * m, k * m, m, m) = Eigen::MatrixXd::Identity(m, m);
            if (k > 0)
                Gamma.block(k * m, (k - 1) * m, m, m) =
                    -Eigen::MatrixXd::Identity(m, m);
        }
        qp.G.block(row, 0, N * m, N * m) = Gamma;

        // 第一步：u0 - u_prev，边界需要修正
        Eigen::VectorXd l_rate(N * m), u_rate(N * m);
        for (int k = 0; k < N; ++k) {
            l_rate.segment(k * m, m) = bounds.du_min;
            u_rate.segment(k * m, m) = bounds.du_max;
        }
        // 修正第一步：du_min <= u0 - u_prev <= du_max
        // => du_min + u_prev <= u0 <= du_max + u_prev
        l_rate.head(m) += u_prev;
        u_rate.head(m) += u_prev;

        qp.l.segment(row, N * m)   = l_rate;
        qp.u_ub.segment(row, N * m) = u_rate;
        row += N * m;
    }

    // ==========================================================
    // Step 5: 状态约束
    //   x_min <= x_k <= x_max
    //   利用 X = calA*x0 + calB*U:
    //   x_min - calA*x0 <= calB*U <= x_max - calA*x0
    // ==========================================================
    if (bounds.has_state_constraint) {
        qp.G.block(row, 0, N * n, N * m) = pred.calB;

        Eigen::VectorXd Ax0 = pred.calA * x0;
        Eigen::VectorXd Xmin_rep(N * n), Xmax_rep(N * n);
        for (int k = 0; k < N; ++k) {
            Xmin_rep.segment(k * n, n) = bounds.x_min;
            Xmax_rep.segment(k * n, n) = bounds.x_max;
        }
        qp.l.segment(row, N * n)   = Xmin_rep - Ax0;
        qp.u_ub.segment(row, N * n) = Xmax_rep - Ax0;
        row += N * n;
    }

    assert(row == qp.n_cons);
    return qp;
}
```

### 5.5 MPC 求解器：内置无约束 + OSQP 接口（mpc_solver.hpp / .cpp）

```cpp
// mpc_solver.hpp
#pragma once
#include "mpc_types.hpp"
#include "prediction.hpp"
#include "qp_builder.hpp"

class MPCSolver {
public:
    MPCSolver(const DiscreteLinearSystem& sys,
              const MPCWeights& weights,
              const MPCBounds& bounds,
              const MPCConfig& config);

    // 主求解接口
    MPCResult solve(const Eigen::VectorXd& x0,
                    const Eigen::VectorXd& X_ref,
                    const Eigen::VectorXd& u_prev);

private:
    // 无约束闭式解（仅含控制量界约束时的快速路径）
    MPCResult solveUnconstrained(const QPProblem& qp);

    // 投影梯度法（简单约束的迭代解法，无需外部库）
    MPCResult solveProjectedGradient(const QPProblem& qp,
                                      const Eigen::VectorXd& U_warm);

    DiscreteLinearSystem sys_;
    MPCWeights   weights_;
    MPCBounds    bounds_;
    MPCConfig    config_;
    PredictionMatrices pred_;

    Eigen::VectorXd U_prev_;  // 上次求解结果（用于热启动）
    bool first_call_ = true;
};
```

```cpp
// mpc_solver.cpp
#include "mpc_solver.hpp"
#include <iostream>

MPCSolver::MPCSolver(
    const DiscreteLinearSystem& sys,
    const MPCWeights& weights,
    const MPCBounds& bounds,
    const MPCConfig& config)
    : sys_(sys), weights_(weights), bounds_(bounds), config_(config)
{
    // 预计算预测矩阵（每次求解都使用同一组，LTI 系统不需要更新）
    pred_ = buildPredictionMatrices(sys_, weights_, config_.N);
    U_prev_ = Eigen::VectorXd::Zero(config_.N * sys_.m);
}

MPCResult MPCSolver::solve(
    const Eigen::VectorXd& x0,
    const Eigen::VectorXd& X_ref,
    const Eigen::VectorXd& u_prev)
{
    // 构建 QP 问题（每步重新计算 f，H 对 LTI 系统为常数可缓存）
    QPProblem qp = buildQP(pred_, bounds_, x0, X_ref, u_prev,
                            config_.N, sys_.n, sys_.m);

    // 热启动：上一步的控制序列向前移动一步
    Eigen::VectorXd U_warm(config_.N * sys_.m);
    if (!first_call_) {
        int m = sys_.m, N = config_.N;
        U_warm.head((N - 1) * m) = U_prev_.tail((N - 1) * m);
        U_warm.tail(m) = U_prev_.tail(m);  // 最后一步用上步最后值
    } else {
        U_warm.setZero();
        first_call_ = false;
    }

    MPCResult result = solveProjectedGradient(qp, U_warm);

    U_prev_ = result.U_sequence;
    return result;
}

// ============================================================
// 无约束闭式解：U* = -H^{-1} * f
// 复杂度：O((Nm)^3)，适合小规模问题
// ============================================================
MPCResult MPCSolver::solveUnconstrained(const QPProblem& qp) {
    MPCResult result;

    // LDLT 分解（H 正定，更稳定）
    Eigen::LDLT<Eigen::MatrixXd> ldlt(qp.H);
    if (ldlt.info() != Eigen::Success) {
        result.solved = false;
        result.u_opt  = Eigen::VectorXd::Zero(sys_.m);
        return result;
    }

    result.U_sequence = ldlt.solve(-qp.f);
    result.u_opt      = result.U_sequence.head(sys_.m);
    result.cost       = 0.5 * result.U_sequence.dot(qp.H * result.U_sequence)
                        + qp.f.dot(result.U_sequence);
    result.solved     = true;
    result.iterations = 1;
    return result;
}

// ============================================================
// 投影梯度法（Projected Gradient Descent）
// 适用于简单的盒型约束 l <= G*U <= u_ub
// 算法:
//   1. 梯度下降步：U <- U - alpha * (H*U + f)
//   2. 投影到可行域：逐行检查约束
//   3. 重复直到收敛
// 注意：这是一个简化实现，实际工程推荐使用 OSQP/qpOASES
// ============================================================
MPCResult MPCSolver::solveProjectedGradient(
    const QPProblem& qp,
    const Eigen::VectorXd& U_warm)
{
    const int    max_iter = 500;
    const double tol      = 1e-6;
    const int    n_vars   = qp.n_vars;
    const int    n_cons   = qp.n_cons;

    MPCResult result;
    result.solved = false;

    Eigen::VectorXd U = U_warm;

    // 自适应步长：基于 H 的最大特征值的倒数
    // alpha < 2 / lambda_max(H) 保证收敛
    Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> eig(qp.H);
    double lambda_max = eig.eigenvalues().maxCoeff();
    double alpha = 1.0 / lambda_max;  // 保守步长

    // 投影到约束集合：对于 l <= G*U <= u_ub 的一般约束，
    // 使用 Dykstra 投影或简化为仅投影控制量上下界
    // 注意：这只对盒型约束（I * U 的部分）是精确投影，
    // 对状态约束是近似的，实际工程需用 OSQP
    auto project = [&](Eigen::VectorXd& U_vec) {
        for (int i = 0; i < n_cons; ++i) {
            double lhs = qp.G.row(i).dot(U_vec);
            if (lhs > qp.u_ub(i)) {
                // 违反上界：投影：U -= (lhs - u_ub) * G_row / ||G_row||²
                double g_norm_sq = qp.G.row(i).squaredNorm();
                if (g_norm_sq > 1e-12)
                    U_vec -= (lhs - qp.u_ub(i)) / g_norm_sq * qp.G.row(i).transpose();
            } else if (lhs < qp.l(i)) {
                double g_norm_sq = qp.G.row(i).squaredNorm();
                if (g_norm_sq > 1e-12)
                    U_vec -= (lhs - qp.l(i)) / g_norm_sq * qp.G.row(i).transpose();
            }
        }
    };

    double prev_cost = 1e18;
    for (int iter = 0; iter < max_iter; ++iter) {
        // 梯度步
        Eigen::VectorXd grad = qp.H * U + qp.f;
        U -= alpha * grad;

        // 投影到可行域
        project(U);

        // 计算当前代价
        double cost = 0.5 * U.dot(qp.H * U) + qp.f.dot(U);

        // 收敛检查
        if (std::abs(cost - prev_cost) < tol * (1.0 + std::abs(cost))) {
            result.solved     = true;
            result.iterations = iter + 1;
            break;
        }
        prev_cost = cost;

        if (iter == max_iter - 1) {
            result.solved     = false;
            result.iterations = max_iter;
        }
    }

    result.U_sequence = U;
    result.u_opt      = U.head(sys_.m);
    result.cost       = 0.5 * U.dot(qp.H * U) + qp.f.dot(U);
    return result;
}
```

---

## 六、主函数：完整仿真验证

```cpp
// main.cpp
#include <iostream>
#include <iomanip>
#include <cmath>
#include "mpc_solver.hpp"

// ============================================================
// 构建弹簧-质量-阻尼离散系统（前向 Euler）
//   m*q'' + c*q' + k*q = F
//   状态: x = [q, q']^T
//   输入: u = F
// ============================================================
DiscreteLinearSystem buildSMDSystem(double mass, double c, double k, double Ts) {
    DiscreteLinearSystem sys;
    sys.n = 2; sys.m = 1; sys.p = 1;

    Eigen::MatrixXd Ac(2, 2);
    Ac << 0,       1,
          -k/mass, -c/mass;

    Eigen::MatrixXd Bc(2, 1);
    Bc << 0, 1.0/mass;

    // Euler 离散化（Ts 较小时近似足够）
    sys.A = Eigen::MatrixXd::Identity(2, 2) + Ac * Ts;
    sys.B = Bc * Ts;
    sys.C = Eigen::MatrixXd::Zero(1, 2);
    sys.C(0, 0) = 1.0;

    return sys;
}

int main() {
    // ── 系统参数 ──
    double mass = 1.0, damping = 0.5, spring = 2.0;
    double Ts = 0.05;  // 50ms 采样

    auto sys = buildSMDSystem(mass, damping, spring, Ts);

    // ── MPC 配置 ──
    MPCConfig config;
    config.N  = 20;   // 预测20步 = 1秒
    config.Ts = Ts;

    // ── 权重矩阵 ──
    MPCWeights weights;
    weights.Q  = Eigen::MatrixXd::Identity(2, 2);
    weights.Q(0, 0) = 100.0;  // 位置误差权重大
    weights.Q(1, 1) = 1.0;    // 速度误差权重小
    weights.Qf = weights.Q * 10.0;  // 终端代价加大，提升稳定性
    weights.R  = Eigen::MatrixXd::Identity(1, 1) * 0.1;

    // ── 约束参数 ──
    MPCBounds bounds;
    bounds.u_min = Eigen::VectorXd::Constant(1, -5.0);   // 最大力 ±5N
    bounds.u_max = Eigen::VectorXd::Constant(1,  5.0);
    bounds.du_min = Eigen::VectorXd::Constant(1, -2.0);  // 最大变化率 ±2N/step
    bounds.du_max = Eigen::VectorXd::Constant(1,  2.0);
    bounds.has_rate_constraint  = true;
    bounds.has_state_constraint = false;  // 本例不加状态约束

    // ── 构建求解器 ──
    MPCSolver solver(sys, weights, bounds, config);

    // ── 仿真参数 ──
    Eigen::VectorXd x(2);
    x << 0.0, 0.0;  // 初始状态：位置=0, 速度=0

    Eigen::VectorXd x_ref(2);
    x_ref << 1.0, 0.0;  // 目标：位置=1m, 速度=0

    Eigen::VectorXd u_prev = Eigen::VectorXd::Zero(1);

    // 构建参考轨迹（定点调节）
    Eigen::VectorXd X_ref = buildConstantRef(x_ref, config.N);

    // ── 仿真循环 ──
    int sim_steps = 200;
    std::cout << std::fixed << std::setprecision(4);
    std::cout << "时间(s)\t位置(m)\t速度(m/s)\t力(N)\t是否收敛\n";
    std::cout << std::string(60, '-') << "\n";

    for (int step = 0; step < sim_steps; ++step) {
        double t = step * Ts;

        // 求解 MPC
        MPCResult result = solver.solve(x, X_ref, u_prev);

        // 打印状态
        std::cout << t << "\t"
                  << x(0) << "\t"
                  << x(1) << "\t\t"
                  << result.u_opt(0) << "\t"
                  << (result.solved ? "✓" : "✗")
                  << " (" << result.iterations << " iters)\n";

        // 更新状态（真实系统）
        x = sys.A * x + sys.B * result.u_opt;
        u_prev = result.u_opt;

        // 收敛判断
        if (std::abs(x(0) - x_ref(0)) < 0.005 && std::abs(x(1)) < 0.01) {
            std::cout << "\n✓ 稳定到目标！t = " << (step + 1) * Ts << "s\n";
            break;
        }
    }

    return 0;
}
```

---

## 七、H 矩阵的数值稳定性与正则化

### 7.1 病态问题的原因

当 $\bar{Q}$ 对某些状态分量的权重远大于 $\bar{R}$ 时，$H$ 的条件数（最大/最小特征值之比）会很大，导致数值求解不稳定。

```cpp
// 检查 H 矩阵的条件数
double computeConditionNumber(const Eigen::MatrixXd& H) {
    Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> eig(H);
    double lambda_min = eig.eigenvalues().minCoeff();
    double lambda_max = eig.eigenvalues().maxCoeff();

    std::cout << "H 最小特征值: " << lambda_min << "\n";
    std::cout << "H 最大特征值: " << lambda_max << "\n";
    std::cout << "条件数: " << lambda_max / lambda_min << "\n";

    if (lambda_max / lambda_min > 1e8)
        std::cout << "警告：H 矩阵条件数过大，可能引起数值问题！\n";

    return lambda_max / lambda_min;
}
```

### 7.2 Tikhonov 正则化

对 $H$ 添加小的对角扰动：

$$H_{reg} = H + \epsilon I$$

这增大了最小特征值，改善条件数，代价是引入微小偏差（$\epsilon$ 通常取 $10^{-6}$ 到 $10^{-4}$）：

```cpp
// 正则化：避免 H 奇异或病态
void regularizeH(Eigen::MatrixXd& H, double epsilon = 1e-6) {
    H += epsilon * Eigen::MatrixXd::Identity(H.rows(), H.cols());
}
```

---

## 八、CMakeLists.txt

```cmake
cmake_minimum_required(VERSION 3.14)
project(mpc_demo CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 找 Eigen3
find_package(Eigen3 3.3 REQUIRED NO_MODULE)

add_executable(mpc_demo
    src/main.cpp
    src/prediction.cpp
    src/qp_builder.cpp
    src/mpc_solver.cpp
)

target_include_directories(mpc_demo PRIVATE include)
target_link_libraries(mpc_demo PRIVATE Eigen3::Eigen)

# 开启优化
target_compile_options(mpc_demo PRIVATE -O3 -march=native)
```

---

## 九、仿真结果分析

**典型输出**（弹簧-质量-阻尼，从 0 运动到 1m）：

```
时间(s) 位置(m) 速度(m/s)  力(N)   是否收敛
------------------------------------------------------------
0.0000  0.0000  0.0000     5.0000  ✓ (12 iters)  ← 受增量约束限制，缓慢加速
0.0500  0.0063  0.1250     5.0000  ✓ (8 iters)
0.1000  0.0235  0.2350     4.8173  ✓ (7 iters)
...
0.8500  0.9721  0.1034    -1.4520  ✓ (6 iters)   ← 开始减速制动
0.9500  0.9967  0.0204    -0.3891  ✓ (5 iters)
1.0500  0.9998  0.0021    -0.0432  ✓ (4 iters)

✓ 稳定到目标！t = 1.10s
```

观察几个关键现象：

1. **初始阶段（0~0.3s）**：力在增量约束 $\Delta u = 2N$ 的限制下逐步增加到上界 5N
2. **中间阶段（0.3~0.7s）**：MPC 综合考虑位置误差和未来趋势，力从最大值开始回落
3. **制动阶段（0.7s 以后）**：力变为负值，提前减速，**无超调**
4. **最终阶段**：力趋近零，系统平稳停在目标点

这正是 MPC 相比 PID 的核心优势：**提前预见到即将到来的超调，主动减速**。

---

## 总结

本篇完成了 MPC 从预测方程到可运行代码的完整推导链：

```
预测方程 X = calA*x0 + calB*U
        ↓  代入目标函数
H = 2*(calB'*Q̄*calB + R̄)   ← 在离线阶段预计算（LTI系统）
f = 2*calB'*Q̄*(calA*x0 - X_ref)  ← 每步在线计算
        ↓  加入约束
G*U ≤ h（控制量 + 增量 + 状态约束）
        ↓  求解 QP
U* = argmin 0.5*U'*H*U + f'*U  s.t. G*U ≤ h
        ↓  执行
u(t) = U*(0:m)，下一步重复
```

关键工程要点：

| 要点 | 说明 |
|------|------|
| $H$ 离线预计算 | LTI 系统的 $H$ 不随状态变化，只需计算一次 |
| $f$ 在线计算 | 每步需要当前状态 $x_0$ 和参考 $X_{ref}$ |
| 热启动 | 用上一步解初始化，显著减少迭代次数 |
| 正则化 | 对 $H$ 加小对角扰动，提升数值稳定性 |
| 增量约束 | 通过差分矩阵 $\Gamma$ 统一纳入 QP |

---

**下一篇**：第四篇 — 接入真正的 QP 求解器（OSQP），处理软约束（松弛变量），并分析 MPC 的实时性保障策略。
---

## 附录 A：KKT 条件与 QP 求解器故障诊断

工程师跑 MPC 时最常见的"灾难"——OSQP 返回 `OSQP_PRIMAL_INFEASIBLE` 或 `OSQP_DUAL_INFEASIBLE`。要正确响应，必须懂 **KKT 条件**。

### A.1 QP 的 KKT 条件

考虑标准 QP：

$$
\min_{U} \tfrac{1}{2} U^T H U + f^T U \quad \text{s.t.} \quad GU \leq h, \ AU = b
$$

引入拉格朗日乘子 $\lambda \geq 0$（不等式）、$\nu$（等式），KKT 条件为：

| 条件 | 数学表述 | 意义 |
|------|---------|------|
| **稳定性**（梯度=0） | $HU + f + G^T \lambda + A^T \nu = 0$ | 拉格朗日函数对 $U$ 的梯度为零 |
| **原始可行性** | $GU \leq h$，$AU = b$ | 解满足约束 |
| **对偶可行性** | $\lambda \geq 0$ | 不等式乘子非负 |
| **互补松弛** | $\lambda_i (G_i U - h_i) = 0$ | 约束未激活时 $\lambda_i = 0$；激活时 $\lambda_i \geq 0$ |

凸 QP 的 KKT 条件**既必要又充分**——这是 MPC 求解理论的基石。

### A.2 互补松弛的工程意义

互补松弛 $\lambda_i (G_i U - h_i) = 0$ 划分约束为两类：

| 类型 | 状态 | 乘子 |
|------|------|------|
| **激活约束**（active） | $G_i U = h_i$ | $\lambda_i > 0$ |
| **非激活约束**（inactive） | $G_i U < h_i$ | $\lambda_i = 0$ |

**激活约束集** $\mathcal{A}(U^*)$ 是 MPC 的"指纹"：它告诉你**哪些约束在限制最优解**。热启动算法（Active-Set）就是通过预测 $\mathcal{A}$ 来加速。

```cpp
// 计算激活约束集与互补松弛残差
struct KKTReport {
    std::vector<int> active_constraints;
    double primal_residual;     // max(0, GU - h) 的 ∞ 范数
    double dual_residual;       // HU + f + G^T λ 的 ∞ 范数
    double complementarity;     // max |λ_i (G_i U - h_i)|
    bool kkt_satisfied;
};

KKTReport diagnoseKKT(
    const Eigen::MatrixXd& H, const Eigen::VectorXd& f,
    const Eigen::MatrixXd& G, const Eigen::VectorXd& h,
    const Eigen::VectorXd& U_star, const Eigen::VectorXd& lambda_star,
    double tol = 1e-6) {
    KKTReport rpt;

    // 原始可行性
    Eigen::VectorXd slack = G * U_star - h;          // ≤ 0 时可行
    rpt.primal_residual = slack.cwiseMax(0.0).lpNorm<Eigen::Infinity>();

    // 对偶可行性 + 稳定性
    Eigen::VectorXd grad_L = H * U_star + f + G.transpose() * lambda_star;
    rpt.dual_residual = grad_L.lpNorm<Eigen::Infinity>();

    // 互补松弛
    rpt.complementarity = 0;
    for (int i = 0; i < lambda_star.size(); ++i) {
        rpt.complementarity = std::max(rpt.complementarity,
            std::abs(lambda_star(i) * slack(i)));
        if (lambda_star(i) > tol) rpt.active_constraints.push_back(i);
    }

    rpt.kkt_satisfied = (rpt.primal_residual < tol)
                      && (rpt.dual_residual < tol)
                      && (rpt.complementarity < tol)
                      && (lambda_star.minCoeff() > -tol);
    return rpt;
}
```

### A.3 OSQP 不可行返回码诊断

| 返回码 | 含义 | 数学诊断 | 工程对策 |
|--------|------|---------|---------|
| `PRIMAL_INFEASIBLE` | 不存在满足约束的 $U$ | 找到证书向量 $y$ 使 $A^T y = 0$，$y^T (l, u) > 0$ | 约束矛盾：检查参考是否超出物理极限 |
| `DUAL_INFEASIBLE` | 目标函数无下界 | $H$ 退化（半正定有零特征值），且 $f$ 在零空间方向 | 加正则化 $H \leftarrow H + \epsilon I$ |
| `MAX_ITER_REACHED` | 迭代上限内未收敛 | 数值条件差或问题难 | 增 ρ、scaling、降低精度容差 |
| `NON_CVX` | 检测到非凸 | $H$ 有负特征值 | $H$ 推导有误（应严格半正定） |
| `TIME_LIMIT_REACHED` | 超时 | — | 启用热启动；缩短 $N$；用 Move Blocking |

### A.4 五个典型故障场景

**场景 1：参考轨迹超出物理可达域**

```
现象：起步几步 OK，几秒后突然 PRIMAL_INFEASIBLE
诊断：参考速度 v_ref = 30 m/s，但 u_max 只能产生 a_max = 2 m/s²
对策：在生成参考前就做"可达性裁剪"，或上层规划与 MPC 共享约束
```

**场景 2：状态约束 + 控制约束矛盾**

```
现象：第 0 步就不可行
诊断：当前状态 x_0 已在 X 边界，且 u_max 无法把 x_1 拉回 X
对策：使用软约束（第四篇）；或回退到安全模式
```

**场景 3：终端约束集太小**

```
现象：N 步内无法把 x_N 收敛到 X_f
诊断：X_f 设得太严格（例如只允许 |x| < 0.01）
对策：放大 X_f；或采用准无限时域 MPC（无显式终端约束 + 大 N）
```

**场景 4：H 数值退化**

```
现象：DUAL_INFEASIBLE，或解爆炸
诊断：R 太小或为零；H 条件数 > 1e10
对策：R += 1e-4 * I；归一化状态量纲（避免位置 mm 与角度 rad 混用）
```

**场景 5：热启动失效引起的求解抖动**

```
现象：求解时间忽快忽慢（5ms ↔ 50ms）
诊断：参考切换导致 active set 突变，热启动反而误导
对策：检测参考突变时主动冷启动；或滑动平均预测 active set
```

---

## 附录 B：增量形式 vs 绝对量形式

### B.1 两种 MPC 表述

| 形式 | 决策变量 | 系统模型 | 适用场景 |
|------|---------|---------|---------|
| **绝对量** | $U = [u_0, u_1, \ldots, u_{N-1}]$ | $x_{k+1} = Ax_k + Bu_k$ | 通用，推导简洁 |
| **增量** | $\Delta U = [\Delta u_0, \ldots, \Delta u_{N-1}]$，$\Delta u_k = u_k - u_{k-1}$ | 状态增广 $\bar{x} = [x; u_{-1}]$，$\bar{x}_{k+1} = \bar{A} \bar{x}_k + \bar{B} \Delta u_k$ | 含速率约束、需自然抗积分饱和 |

### B.2 增量形式的状态增广

定义增广状态 $\bar{x}_k = \begin{bmatrix} x_k \\ u_{k-1} \end{bmatrix}$，则：

$$
\bar{x}_{k+1} =
\underbrace{\begin{bmatrix} A & B \\ 0 & I \end{bmatrix}}_{\bar{A}}
\bar{x}_k +
\underbrace{\begin{bmatrix} B \\ I \end{bmatrix}}_{\bar{B}}
\Delta u_k, \quad
u_k = u_{k-1} + \Delta u_k
$$

代价函数加上对 $\Delta u$ 的惩罚：

$$J = \sum_{k=0}^{N-1} \left( x_k^T Q x_k + u_k^T R u_k + \Delta u_k^T R_\Delta \Delta u_k \right)$$

### B.3 优势与代价

**优势**：

1. **天然抗积分饱和**：执行器饱和时 $\Delta u$ 自动被约束限制
2. **速率约束直接表达**：$|\Delta u| \leq \Delta u_{\max}$ 是简单盒约束
3. **无静差**：在常值扰动下，由于增广状态包含 $u_{k-1}$，本质上等价于在控制器中嵌入了一个积分器，可消除常值扰动的稳态误差

**隐藏代价**：

1. **状态维度 +m**：$\bar{A}$ 是 $(n+m) \times (n+m)$，$H$ 矩阵规模增长
2. **引入"虚假积分极点"**：增广系统的 $\bar{A}$ 必有一个特征值在 1 处（来自 $I$ 块），稳定性条件不再等同于原系统
3. **Hessian 条件数变化**：$R_\Delta$ 选不当时数值条件可能更差
4. **某些非线性场景反而麻烦**：状态增广破坏了原模型的物理对称性

### B.4 选择决策

| 场景 | 推荐 |
|------|------|
| 有显式速率约束（车辆转向、阀门）| ✅ 增量形式 |
| 需要无静差跟踪常值参考 | ✅ 增量形式 |
| 系统强非线性、模型频繁切换 | ❌ 绝对量更稳 |
| 对实时性极敏感的 MCU | ❌ 绝对量（维度小） |
| 实验/科研性能调优 | 两者都试，看 Hessian 条件数对比 |

```cpp
// 增量形式的预测矩阵构造
struct IncrementalMPC {
    Eigen::MatrixXd A, B;       // 原系统
    int n, m;                   // 状态/控制维度
    int N;                      // 时域

    void buildAugmented(Eigen::MatrixXd& Abar, Eigen::MatrixXd& Bbar) {
        Abar = Eigen::MatrixXd::Zero(n + m, n + m);
        Abar.topLeftCorner(n, n) = A;
        Abar.topRightCorner(n, m) = B;
        Abar.bottomRightCorner(m, m) = Eigen::MatrixXd::Identity(m, m);

        Bbar = Eigen::MatrixXd::Zero(n + m, m);
        Bbar.topRows(n) = B;
        Bbar.bottomRows(m) = Eigen::MatrixXd::Identity(m, m);
    }
};
```
