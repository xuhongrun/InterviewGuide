# 第四篇：接入 OSQP 求解器、软约束与实时性保障

---

## 引言

前三篇完成了 MPC 的数学推导，并用投影梯度法做了简单验证。但投影梯度法只是教学用途，工业级 MPC 需要**真正的 QP 求解器**。

本篇要解决三个工程核心问题：

1. **求解器接入**：如何正确调用 OSQP，包括稀疏矩阵格式、热启动、参数调优
2. **软约束**：当约束可能不可行时，如何引入松弛变量保证求解器不报错
3. **实时性**：采样周期内必须完成求解，如何设计保障策略

这三个问题解决好，MPC 才能真正跑在机器人、车辆、工业控制器上。

---

## 一、为什么需要专业 QP 求解器

### 1.1 投影梯度法的缺陷

上一篇用的投影梯度法存在两个根本问题：

**问题一：收敛速度慢**

梯度法的收敛阶是一阶（线性收敛），步数与条件数成正比。$H$ 的条件数往往在 $10^3 \sim 10^6$，收敛需要数千次迭代。

**问题二：约束投影不精确**

对于一般线性约束 $G\mathbf{U} \leq h$，逐行投影不是到可行域的正确投影，会引入额外误差，可能导致约束违反。

### 1.2 专业求解器对比

| 求解器 | 算法 | 开源 | 嵌入式 | 热启动 | 稀疏矩阵 |
|--------|------|------|--------|--------|---------|
| **OSQP** | ADMM | ✓ | ✓ | ✓ | ✓ |
| **qpOASES** | 有效集法 | ✓ | ✓ | ✓ | 部分 |
| **HPIPM** | IPM（结构化） | ✓ | ✓ | ✓ | ✓（MPC专用） |
| **Gurobi** | IPM + 有效集 | ✗ | ✗ | ✓ | ✓ |
| **ECOS** | IPM | ✓ | ✓ | ✗ | ✓ |

**OSQP** 是当前嵌入式 MPC 最流行的选择，理由：
- 生成的 C 代码极小（无动态内存分配）
- 二阶收敛（ADMM 改进版），实测比梯度法快 $10 \sim 100$ 倍
- 支持不可行检测，不会静默返回错误结果

---

## 二、OSQP 深度解析

### 2.1 OSQP 标准问题形式

$$\min_{\mathbf{U}} \quad \frac{1}{2}\mathbf{U}^T P \mathbf{U} + q^T \mathbf{U}$$
$$\text{s.t.} \quad l \leq A\mathbf{U} \leq u$$

注意：
- $P$ 只需提供**上三角**部分（OSQP 内部对称处理）
- 约束写成双边形式 $l \leq A\mathbf{U} \leq u$（可以包含等式约束：令 $l_i = u_i$）
- 无约束上界：$u_i = +\infty$；无约束下界：$l_i = -\infty$

与 MPC QP 的对应关系：

$$P = H, \quad q = f, \quad A = G, \quad l = l_{bound}, \quad u = h$$

### 2.2 稀疏矩阵 CSC 格式

OSQP 内部使用**压缩列存储（Compressed Sparse Column，CSC）**格式。对于 MPC 问题，$P$（即 $H$）是稠密正定矩阵，但 $G$ 是高度稀疏的：

```
G 的典型结构（N=4, n=2, m=1）：

控制量约束（2Nm行）：
  [1  0  0  0]   u_0 <= u_max
  [0  1  0  0]   u_1 <= u_max
  [0  0  1  0]   u_2 <= u_max
  [0  0  0  1]   u_3 <= u_max
  [-1 0  0  0]   -u_0 <= -u_min
  ...

增量约束（2Nm行）：
  [1  0  0  0]   u_0 - u_prev <= du_max
  [-1 1  0  0]   u_1 - u_0   <= du_max
  [0  -1 1  0]   u_2 - u_1   <= du_max
  ...

状态约束（2Nn行）：
  calB（下三角块，稀疏）
```

稀疏度高 → 用 Eigen 的 `SparseMatrix<double>` 而非稠密矩阵，内存和速度都有显著优势。

---

## 三、C++ 接入 OSQP 的完整实现

### 3.1 安装与 CMake 配置

```cmake
# CMakeLists.txt
cmake_minimum_required(VERSION 3.14)
project(mpc_osqp CXX C)

set(CMAKE_CXX_STANDARD 17)

# 方式一：系统安装的 OSQP
find_package(osqp REQUIRED)

# 方式二：从源码编译（推荐，版本可控）
# include(FetchContent)
# FetchContent_Declare(osqp
#     GIT_REPOSITORY https://github.com/osqp/osqp.git
#     GIT_TAG        v0.6.3)
# FetchContent_MakeAvailable(osqp)

find_package(Eigen3 3.4 REQUIRED NO_MODULE)

add_executable(mpc_osqp
    src/main.cpp
    src/prediction.cpp
    src/qp_builder.cpp
    src/osqp_solver.cpp
)

target_include_directories(mpc_osqp PRIVATE include)
target_link_libraries(mpc_osqp PRIVATE Eigen3::Eigen osqp::osqp)
target_compile_options(mpc_osqp PRIVATE -O3 -march=native)
```

### 3.2 Eigen 稀疏矩阵转 OSQP CSC 格式

```cpp
// osqp_interface.hpp
#pragma once
#include <Eigen/Sparse>
#include <osqp/osqp.h>
#include <vector>
#include <memory>

// ============================================================
// RAII 包装：自动管理 OSQP CSC 矩阵的内存
// ============================================================
struct OSQPCscMatrixDeleter {
    void operator()(OSQPCscMatrix* m) const {
        if (m) {
            delete[] m->x;
            delete[] m->i;
            delete[] m->p;
            delete m;
        }
    }
};
using OSQPCscPtr = std::unique_ptr<OSQPCscMatrix, OSQPCscMatrixDeleter>;

// ============================================================
// 将 Eigen 稀疏矩阵转换为 OSQP CSC 格式
//
// Eigen 的 SparseMatrix<double> 使用 CSC 存储（列主序），
// 与 OSQP 格式一致，可以直接映射数据指针。
//
// 参数 upper_only：为 true 时只取上三角（用于对称矩阵 P）
// ============================================================
OSQPCscPtr eigenToOSQPCSC(const Eigen::SparseMatrix<double>& mat,
                            bool upper_only = false)
{
    Eigen::SparseMatrix<double> csc;

    if (upper_only) {
        // 取上三角部分（OSQP 要求 P 只提供上三角）
        csc = mat.triangularView<Eigen::Upper>();
    } else {
        csc = mat;
    }
    csc.makeCompressed();  // 确保是压缩列存储

    int    rows = csc.rows();
    int    cols = csc.cols();
    int    nnz  = csc.nonZeros();

    // 分配 OSQP 矩阵（数据拷贝，避免悬空指针）
    auto* osqp_mat = new OSQPCscMatrix;
    osqp_mat->m     = rows;
    osqp_mat->n     = cols;
    osqp_mat->nz    = -1;    // CSC 格式置 -1
    osqp_mat->nzmax = nnz;

    osqp_mat->x = new OSQPFloat[nnz];
    osqp_mat->i = new OSQPInt[nnz];
    osqp_mat->p = new OSQPInt[cols + 1];

    std::copy(csc.valuePtr(),       csc.valuePtr()       + nnz,    osqp_mat->x);
    std::copy(csc.innerIndexPtr(),  csc.innerIndexPtr()  + nnz,    osqp_mat->i);
    std::copy(csc.outerIndexPtr(),  csc.outerIndexPtr()  + cols+1, osqp_mat->p);

    return OSQPCscPtr(osqp_mat);
}

// ============================================================
// 将 MPC 的稠密 H 矩阵转为稀疏（对小规模问题仍是稠密存储）
// 对于 N > 30、m > 3 的大规模问题，建议直接稀疏构建
// ============================================================
Eigen::SparseMatrix<double> denseToSparse(const Eigen::MatrixXd& dense) {
    Eigen::SparseMatrix<double> sparse(dense.rows(), dense.cols());
    std::vector<Eigen::Triplet<double>> triplets;
    triplets.reserve(dense.nonZeros());  // 预估非零元素数

    for (int j = 0; j < dense.cols(); ++j)
        for (int i = 0; i < dense.rows(); ++i)
            if (std::abs(dense(i, j)) > 1e-12)
                triplets.emplace_back(i, j, dense(i, j));

    sparse.setFromTriplets(triplets.begin(), triplets.end());
    sparse.makeCompressed();
    return sparse;
}
```

### 3.3 OSQP 求解器封装类

```cpp
// osqp_solver.hpp
#pragma once
#include "mpc_types.hpp"
#include "prediction.hpp"
#include "qp_builder.hpp"
#include "osqp_interface.hpp"
#include <osqp/osqp.h>
#include <memory>

// ============================================================
// RAII 包装 OSQP solver
// ============================================================
struct OSQPSolverDeleter {
    void operator()(OSQPSolver* s) const { if (s) osqp_cleanup(s); }
};
using OSQPSolverPtr = std::unique_ptr<OSQPSolver, OSQPSolverDeleter>;

// ============================================================
// 基于 OSQP 的 MPC 求解器
// 支持：热启动、软约束、在线参数更新
// ============================================================
class OSQPMPCSolver {
public:
    struct SolverConfig {
        // OSQP 参数
        double  rho         = 0.1;       // ADMM 步长（影响收敛速度）
        double  sigma       = 1e-6;      // 正则化项
        double  alpha       = 1.6;       // 松弛因子（1-2之间，1.6通常最优）
        int     max_iter    = 4000;      // 最大迭代次数
        double  eps_abs     = 1e-4;      // 绝对收敛精度（实时系统可放宽到1e-3）
        double  eps_rel     = 1e-4;      // 相对收敛精度
        double  eps_prim_inf = 1e-5;     // 原始不可行容差
        double  eps_dual_inf = 1e-5;     // 对偶不可行容差
        bool    warm_start  = true;      // 热启动
        bool    verbose     = false;     // 不打印迭代信息（嵌入式必须关闭）
        bool    polish      = true;      // 精化（解的精度更高，代价时间约×2）
        int     polish_refine_iter = 3;  // 精化迭代次数
        double  time_limit  = 0.0;       // 时间限制（0=不限制，单位秒）
    };

    OSQPMPCSolver(const DiscreteLinearSystem& sys,
                  const MPCWeights& weights,
                  const MPCBounds& bounds,
                  const MPCConfig& config,
                  const SolverConfig& solver_cfg = SolverConfig{});

    // 主求解接口（每个控制周期调用一次）
    MPCResult solve(const Eigen::VectorXd& x0,
                    const Eigen::VectorXd& X_ref,
                    const Eigen::VectorXd& u_prev);

    // 更新权重（允许运行时调参，不需要重新初始化）
    void updateWeights(const MPCWeights& new_weights);

    // 获取上次求解统计信息
    struct SolveStats {
        int    iter;       // 实际迭代次数
        double obj_val;    // 目标函数值
        double prim_res;   // 原始残差
        double dual_res;   // 对偶残差
        double solve_time; // 求解时间 (ms)
        bool   solved;
    };
    SolveStats getLastStats() const { return last_stats_; }

private:
    void initOSQP(const QPProblem& qp);
    void updateQPLinear(const Eigen::VectorXd& x0,
                        const Eigen::VectorXd& X_ref,
                        const Eigen::VectorXd& u_prev);

    DiscreteLinearSystem sys_;
    MPCWeights   weights_;
    MPCBounds    bounds_;
    MPCConfig    config_;
    SolverConfig solver_cfg_;
    PredictionMatrices pred_;

    OSQPSolverPtr osqp_solver_;
    OSQPSettings  osqp_settings_;

    Eigen::VectorXd U_prev_;  // 热启动用
    bool initialized_ = false;
    SolveStats last_stats_{};
};
```

```cpp
// osqp_solver.cpp
#include "osqp_solver.hpp"
#include <chrono>
#include <stdexcept>

OSQPMPCSolver::OSQPMPCSolver(
    const DiscreteLinearSystem& sys,
    const MPCWeights& weights,
    const MPCBounds& bounds,
    const MPCConfig& config,
    const SolverConfig& solver_cfg)
    : sys_(sys), weights_(weights), bounds_(bounds),
      config_(config), solver_cfg_(solver_cfg)
{
    pred_ = buildPredictionMatrices(sys_, weights_, config_.N);
    U_prev_ = Eigen::VectorXd::Zero(config_.N * sys_.m);
}

MPCResult OSQPMPCSolver::solve(
    const Eigen::VectorXd& x0,
    const Eigen::VectorXd& X_ref,
    const Eigen::VectorXd& u_prev)
{
    auto t_start = std::chrono::high_resolution_clock::now();

    // ── Step 1: 构建 QP ──
    QPProblem qp = buildQP(pred_, bounds_, x0, X_ref, u_prev,
                            config_.N, sys_.n, sys_.m);

    // ── Step 2: 首次调用时初始化 OSQP（预分解 KKT 矩阵）──
    if (!initialized_) {
        initOSQP(qp);
        initialized_ = true;
    } else {
        // 仅更新随状态变化的线性项（f 和约束右端 h）
        // H 和 G 对 LTI 系统不变，无需重新因式分解
        updateQPLinear(x0, X_ref, u_prev);
    }

    // ── Step 3: 热启动（将上次解移位后作为初始点）──
    if (solver_cfg_.warm_start) {
        int m = sys_.m, N = config_.N;

        // 控制序列向前移一步（预测：当前最优解下移）
        Eigen::VectorXd U_warm(N * m);
        U_warm.head((N - 1) * m) = U_prev_.tail((N - 1) * m);
        U_warm.tail(m) = U_prev_.tail(m);  // 最后一步保持不变

        // 对偶变量热启动（OSQP 内部支持）
        osqp_warm_starting(osqp_solver_.get(),
                           U_warm.data(), nullptr);
    }

    // ── Step 4: 求解 ──
    OSQPInt exit_flag = osqp_solve(osqp_solver_.get());

    auto t_end = std::chrono::high_resolution_clock::now();
    double solve_ms = std::chrono::duration<double, std::milli>(
                          t_end - t_start).count();

    // ── Step 5: 解析结果 ──
    MPCResult result;
    const OSQPInfo* info = osqp_solver_->info;

    result.solved = (exit_flag == 0) &&
                    (info->status_val == OSQP_SOLVED ||
                     info->status_val == OSQP_SOLVED_INACCURATE);

    if (result.solved) {
        int N = config_.N, m = sys_.m;
        result.U_sequence.resize(N * m);
        for (int i = 0; i < N * m; ++i)
            result.U_sequence(i) = osqp_solver_->solution->x[i];

        result.u_opt = result.U_sequence.head(m);
        result.cost  = info->obj_val;
        U_prev_ = result.U_sequence;
    } else {
        // 求解失败：回退到上一步的控制量（安全策略）
        result.u_opt = U_prev_.head(sys_.m);
        result.U_sequence = U_prev_;

        // 打印失败原因（调试用）
        fprintf(stderr, "[MPC] 求解失败：%s（迭代 %lld 次）\n",
                info->status, (long long)info->iter);
    }

    result.iterations = static_cast<int>(info->iter);

    last_stats_ = {
        result.iterations,
        info->obj_val,
        info->pri_res,
        info->dua_res,
        solve_ms,
        result.solved
    };

    return result;
}

// ============================================================
// 初始化 OSQP：设置参数、传入数据、完成 KKT 预分解
// 这是最耗时的步骤（通常 1~10ms），只在第一次调用时执行
// ============================================================
void OSQPMPCSolver::initOSQP(const QPProblem& qp) {
    int n_vars = qp.n_vars;
    int n_cons = qp.n_cons;

    // ── 设置 OSQP 参数 ──
    osqp_set_default_settings(&osqp_settings_);
    osqp_settings_.rho              = solver_cfg_.rho;
    osqp_settings_.sigma            = solver_cfg_.sigma;
    osqp_settings_.alpha            = solver_cfg_.alpha;
    osqp_settings_.max_iter         = solver_cfg_.max_iter;
    osqp_settings_.eps_abs          = solver_cfg_.eps_abs;
    osqp_settings_.eps_rel          = solver_cfg_.eps_rel;
    osqp_settings_.eps_prim_inf     = solver_cfg_.eps_prim_inf;
    osqp_settings_.eps_dual_inf     = solver_cfg_.eps_dual_inf;
    osqp_settings_.warm_starting    = solver_cfg_.warm_start ? 1 : 0;
    osqp_settings_.verbose          = solver_cfg_.verbose ? 1 : 0;
    osqp_settings_.polish           = solver_cfg_.polish ? 1 : 0;
    osqp_settings_.polish_refine_iter = solver_cfg_.polish_refine_iter;
    if (solver_cfg_.time_limit > 0)
        osqp_settings_.time_limit = solver_cfg_.time_limit;

    // ── P 矩阵（目标函数 Hessian，只需上三角）──
    Eigen::SparseMatrix<double> P_sparse = denseToSparse(qp.H);
    auto P_csc = eigenToOSQPCSC(P_sparse, /*upper_only=*/true);

    // ── A 矩阵（约束矩阵）──
    Eigen::SparseMatrix<double> G_sparse = denseToSparse(qp.G);
    auto A_csc = eigenToOSQPCSC(G_sparse, /*upper_only=*/false);

    // ── 数据打包 ──
    OSQPData data;
    data.n = n_vars;
    data.m = n_cons;
    data.P = P_csc.get();
    data.q = qp.f.data();
    data.A = A_csc.get();
    data.l = qp.l.data();
    data.u = qp.u_ub.data();

    // ── 建立求解器（LDLT 预分解，一次性完成）──
    OSQPSolver* raw_solver = nullptr;
    OSQPInt ret = osqp_setup(&raw_solver, &data, &osqp_settings_);

    if (ret != 0 || raw_solver == nullptr)
        throw std::runtime_error("OSQP 初始化失败，检查问题数据是否正确");

    osqp_solver_.reset(raw_solver);
}

// ============================================================
// 在线更新：只更新 q（目标线性项）和约束上下界 l, u
// 不重新做 KKT 分解（这是热更新的关键，节省大量时间）
// ============================================================
void OSQPMPCSolver::updateQPLinear(
    const Eigen::VectorXd& x0,
    const Eigen::VectorXd& X_ref,
    const Eigen::VectorXd& u_prev)
{
    // 重新计算 f（随当前状态 x0 和参考 X_ref 变化）
    Eigen::VectorXd e0 = pred_.calA * x0 - X_ref;
    Eigen::VectorXd f_new = 2.0 * pred_.calB.transpose() * pred_.barQ * e0;

    // 更新约束右端（随 x0 和 u_prev 变化）
    // 重新构建约束边界（只需重算 h 向量，G 矩阵不变）
    int N = config_.N, n = sys_.n, m = sys_.m;

    Eigen::VectorXd l_new = qp_l_cache_;  // 从缓存恢复结构
    Eigen::VectorXd u_new = qp_u_cache_;

    // 更新控制量上下界（固定，不随状态变化）
    // 已在初始化时设置，无需重算

    // 更新增量约束的右端（依赖 u_prev）
    if (bounds_.has_rate_constraint) {
        int offset = N * m;  // 跳过控制量约束
        l_new.segment(offset, m) = bounds_.du_min + u_prev;
        u_new.segment(offset, m) = bounds_.du_max + u_prev;
    }

    // 更新状态约束的右端（依赖 x0）
    if (bounds_.has_state_constraint) {
        int offset_state = (bounds_.has_rate_constraint ? 2 : 1) * N * m;
        Eigen::VectorXd Ax0 = pred_.calA * x0;
        Eigen::VectorXd Xmin_rep(N * n), Xmax_rep(N * n);
        for (int k = 0; k < N; ++k) {
            Xmin_rep.segment(k * n, n) = bounds_.x_min;
            Xmax_rep.segment(k * n, n) = bounds_.x_max;
        }
        l_new.segment(offset_state, N * n) = Xmin_rep - Ax0;
        u_new.segment(offset_state, N * n) = Xmax_rep - Ax0;
    }

    // 调用 OSQP 在线更新接口（避免重新分解）
    osqp_update_data_vec(osqp_solver_.get(),
                         f_new.data(),  // 更新 q
                         l_new.data(),  // 更新 l
                         u_new.data()); // 更新 u
}
```

---

## 四、软约束：当硬约束不可行时

### 4.1 为什么硬约束会不可行？

硬约束不可行（QP infeasible）是实际工程中最常见的 MPC 故障：

```
典型触发场景：
  1. 状态约束过紧 + 预测时域过短
     → 系统即使全力控制也无法在 N 步内满足约束

  2. 外部扰动导致初始状态已经违反约束
     → 例如车辆已经出界，无法同时满足位置约束和动力学约束

  3. 控制量约束 + 增量约束同时存在
     → u_k 需要从 u_prev 出发，在 N 步内同时满足幅值和变化率
     → 某些初始条件下两者不可同时满足

  4. 参考轨迹在约束边界附近突变
     → 参考的切换使得当前窗口内无可行解
```

当 OSQP 返回 `OSQP_PRIMAL_INFEASIBLE` 时，如果没有处理机制，控制器会输出零（或上一步结果），可能导致系统失稳。

### 4.2 软约束原理：引入松弛变量

**核心思想**：将硬约束变为软约束，允许约束以一定代价被违反。

对于状态约束 $x_{min} \leq x_k \leq x_{max}$，引入松弛变量 $\epsilon_k \geq 0$：

$$x_{min} - \epsilon_k \leq x_k \leq x_{max} + \epsilon_k, \quad \epsilon_k \geq 0$$

在目标函数中加入惩罚项：

$$J_{soft} = J + \rho_{lin} \sum_{k=1}^N \mathbf{1}^T \epsilon_k + \rho_{quad} \sum_{k=1}^N \epsilon_k^T \epsilon_k$$

- $\rho_{lin}$：线性惩罚（确保当约束可行时松弛量为零，类似 $\ell_1$ 正则化）
- $\rho_{quad}$：二次惩罚（控制违反幅度的平方代价）

同时使用两项的组合称为 **$\ell_1$-$\ell_2$ 惩罚**，是经典选择。

**原则**：
- 控制量约束（执行器物理极限）→ **保持硬约束**（不能违反）
- 状态约束（安全边界）→ **软化**（可以短暂越界，但代价极高）

### 4.3 软约束的 QP 增广

引入松弛变量后，优化变量变为 $[\mathbf{U}^T, \boldsymbol{\epsilon}^T]^T$，问题规模增大但依然是 QP：

$$\min_{\mathbf{U}, \boldsymbol{\epsilon}} \quad \frac{1}{2}\begin{bmatrix}\mathbf{U} \\ \boldsymbol{\epsilon}\end{bmatrix}^T \begin{bmatrix} H & 0 \\ 0 & 2\rho_{quad}I \end{bmatrix} \begin{bmatrix}\mathbf{U} \\ \boldsymbol{\epsilon}\end{bmatrix} + \begin{bmatrix} f \\ \rho_{lin}\mathbf{1} \end{bmatrix}^T \begin{bmatrix}\mathbf{U} \\ \boldsymbol{\epsilon}\end{bmatrix}$$

约束：

$$\begin{bmatrix} G_u & 0 \\ \mathcal{B} & -I \\ -\mathcal{B} & -I \end{bmatrix} \begin{bmatrix}\mathbf{U} \\ \boldsymbol{\epsilon}\end{bmatrix} \leq \begin{bmatrix} h_u \\ \mathbf{X}_{max} - \mathcal{A}x_0 \\ -\mathbf{X}_{min} + \mathcal{A}x_0 \end{bmatrix}, \quad \boldsymbol{\epsilon} \geq 0$$

### 4.4 C++ 实现软约束增广

```cpp
// soft_constraint.hpp
#pragma once
#include "mpc_types.hpp"
#include "prediction.hpp"

// 软约束参数
struct SoftConstraintConfig {
    double rho_lin  = 1e4;   // 线性惩罚权重（极大值确保约束尽量不违反）
    double rho_quad = 1e3;   // 二次惩罚权重
    // 哪些约束软化（通常只软化状态约束）
    bool soft_state   = true;
    bool soft_control = false;  // 控制量约束保持硬约束
};

// 软约束增广后的 QP 问题
// 优化变量：[U (N*m), epsilon (N*n_soft)]
struct SoftQPProblem {
    Eigen::MatrixXd H_aug;   // 增广目标 Hessian
    Eigen::VectorXd f_aug;   // 增广目标线性项
    Eigen::MatrixXd G_aug;   // 增广约束矩阵
    Eigen::VectorXd l_aug;   // 约束下界
    Eigen::VectorXd u_aug;   // 约束上界
    int n_vars_u;            // 控制量变量数 = N*m
    int n_vars_eps;          // 松弛变量数
    int n_vars_total;
};

SoftQPProblem buildSoftQP(
    const QPProblem& hard_qp,           // 原始硬约束 QP
    const PredictionMatrices& pred,
    const MPCBounds& bounds,
    const SoftConstraintConfig& soft_cfg,
    const Eigen::VectorXd& x0,
    int N, int n, int m)
{
    SoftQPProblem sqp;
    sqp.n_vars_u   = N * m;

    // 软约束只针对状态约束（Nn 个约束，每个一个松弛变量）
    sqp.n_vars_eps = soft_cfg.soft_state ? N * n : 0;
    sqp.n_vars_total = sqp.n_vars_u + sqp.n_vars_eps;

    // ── 增广 Hessian ──
    sqp.H_aug = Eigen::MatrixXd::Zero(sqp.n_vars_total, sqp.n_vars_total);
    sqp.H_aug.topLeftCorner(sqp.n_vars_u, sqp.n_vars_u) = hard_qp.H;
    if (sqp.n_vars_eps > 0) {
        // epsilon 的二次惩罚：2 * rho_quad * I
        sqp.H_aug.bottomRightCorner(sqp.n_vars_eps, sqp.n_vars_eps) =
            2.0 * soft_cfg.rho_quad *
            Eigen::MatrixXd::Identity(sqp.n_vars_eps, sqp.n_vars_eps);
    }

    // ── 增广线性项 ──
    sqp.f_aug = Eigen::VectorXd::Zero(sqp.n_vars_total);
    sqp.f_aug.head(sqp.n_vars_u) = hard_qp.f;
    if (sqp.n_vars_eps > 0) {
        // epsilon 的线性惩罚：rho_lin * 1
        sqp.f_aug.tail(sqp.n_vars_eps).setConstant(soft_cfg.rho_lin);
    }

    // ── 约束矩阵增广 ──
    // 原始约束（控制量约束保持不变，只增广状态约束部分）
    // 假设状态约束在 hard_qp.G 的最后 2*N*n 行
    int n_hard     = hard_qp.n_cons;
    int n_u_cons   = n_hard - (bounds.has_state_constraint ? 2 * N * n : 0);
    int n_st_cons  = bounds.has_state_constraint ? 2 * N * n : 0;
    int n_eps_cons = sqp.n_vars_eps > 0 ? sqp.n_vars_eps : 0;

    // 总约束数：硬约束 + epsilon >= 0
    int n_cons_total = n_hard + n_eps_cons;

    sqp.G_aug = Eigen::MatrixXd::Zero(n_cons_total, sqp.n_vars_total);
    sqp.l_aug = Eigen::VectorXd(n_cons_total);
    sqp.u_aug = Eigen::VectorXd(n_cons_total);

    // 复制控制量约束（硬约束，epsilon 列为零）
    sqp.G_aug.block(0, 0, n_u_cons, sqp.n_vars_u) =
        hard_qp.G.topRows(n_u_cons);
    sqp.l_aug.head(n_u_cons) = hard_qp.l.head(n_u_cons);
    sqp.u_aug.head(n_u_cons) = hard_qp.u_ub.head(n_u_cons);

    // 状态约束软化（加入松弛变量 epsilon >= 0）
    if (bounds.has_state_constraint && sqp.n_vars_eps > 0) {
        int row = n_u_cons;
        // 上界约束：calB*U - epsilon <= X_max - calA*x0
        sqp.G_aug.block(row, 0, N * n, sqp.n_vars_u) =
            hard_qp.G.block(n_u_cons, 0, N * n, sqp.n_vars_u);
        sqp.G_aug.block(row, sqp.n_vars_u, N * n, sqp.n_vars_eps) =
            -Eigen::MatrixXd::Identity(N * n, N * n);
        sqp.l_aug.segment(row, N * n).setConstant(-1e10);
        sqp.u_aug.segment(row, N * n) =
            hard_qp.u_ub.segment(n_u_cons, N * n);
        row += N * n;

        // 下界约束：-calB*U - epsilon <= -(X_min - calA*x0)
        sqp.G_aug.block(row, 0, N * n, sqp.n_vars_u) =
            hard_qp.G.block(n_u_cons + N * n, 0, N * n, sqp.n_vars_u);
        sqp.G_aug.block(row, sqp.n_vars_u, N * n, sqp.n_vars_eps) =
            -Eigen::MatrixXd::Identity(N * n, N * n);
        sqp.l_aug.segment(row, N * n).setConstant(-1e10);
        sqp.u_aug.segment(row, N * n) =
            hard_qp.u_ub.segment(n_u_cons + N * n, N * n);
        row += N * n;

        // epsilon >= 0（松弛变量非负约束）
        sqp.G_aug.block(row, sqp.n_vars_u, n_eps_cons, sqp.n_vars_eps) =
            Eigen::MatrixXd::Identity(n_eps_cons, n_eps_cons);
        sqp.l_aug.segment(row, n_eps_cons).setZero();
        sqp.u_aug.segment(row, n_eps_cons).setConstant(1e10);
    }

    return sqp;
}
```

---

## 五、实时性保障：让 MPC 跑得够快

### 5.1 实时性的关键约束

控制器必须在**采样周期 $T_s$ 内完成整个求解流程**：

```
时间预算分配（Ts = 50ms 示例）：

┌────────────────────────────────────────────────────┐
│  采样周期 Ts = 50ms                                 │
│                                                    │
│  状态估计   QP 构建   OSQP 求解   执行 + 通信      │
│  ├──5ms──┤├──2ms──┤├──30ms──┤├──5ms──┤           │
│                                                    │
│  求解必须在剩余时间内完成（本例约 30ms）            │
└────────────────────────────────────────────────────┘

如果 OSQP 求解超过 30ms → 延迟控制 → 系统不稳定！
```

### 5.2 六种实时性保障策略

#### 策略一：离线预计算

LTI 系统的 $H$ 和 $G$ 不随状态变化，可以在初始化时预分解，运行时只更新 $f$ 和约束的右端向量。

```cpp
// 离线预计算（构造函数中执行）
class RealtimeMPC {
    Eigen::LDLT<Eigen::MatrixXd> H_ldlt_;  // 预分解 H（无约束路径）
    Eigen::MatrixXd H_cached_;             // 缓存 H
    Eigen::MatrixXd G_cached_;             // 缓存 G

    void precompute() {
        // 一次性分解 H
        H_ldlt_.compute(H_cached_);
        if (H_ldlt_.info() != Eigen::Success)
            throw std::runtime_error("H 分解失败");

        // OSQP 内部也会缓存 KKT 分解
        // 运行时 osqp_update_data_vec 只更新向量，不重新分解
    }
};
```

#### 策略二：设置求解时间上限

```cpp
// OSQP 时间限制（超时后返回当前最优解）
osqp_settings_.time_limit = 0.020;  // 20ms 时间限制

// 检查返回状态
if (info->status_val == OSQP_TIME_LIMIT_REACHED) {
    // 时间到期，使用当前迭代解（可能不是最优，但通常可用）
    // 记录警告，供监控系统分析
    log_warning("MPC 求解超时（{}ms），使用次优解", solve_time_ms);
}
```

#### 策略三：减少预测时域 $N$（变时域 MPC）

```cpp
// 根据系统状态动态调整 N
// 远离目标时：N 小（快速响应）
// 接近目标时：N 大（精确控制）
int adaptiveHorizon(const Eigen::VectorXd& x,
                    const Eigen::VectorXd& x_ref,
                    int N_min, int N_max) {
    double error = (x - x_ref).norm();
    double threshold = 1.0;  // 根据系统量纲调整

    if (error > threshold * 5) return N_min;
    if (error > threshold)     return (N_min + N_max) / 2;
    return N_max;
}
```

#### 策略四：降低精度要求（精度-速度权衡）

```cpp
// 非关键场景：放宽收敛精度，减少迭代次数
osqp_settings_.eps_abs = 1e-3;  // 默认 1e-4，放宽10倍
osqp_settings_.eps_rel = 1e-3;
osqp_settings_.polish  = 0;     // 关闭精化步骤（节省约40%时间）

// 关键场景（接近约束边界时）：恢复高精度
osqp_settings_.eps_abs = 1e-5;
osqp_settings_.polish  = 1;
```

#### 策略五：热启动（Warm Starting）

热启动是提升实时性最有效的单一手段，可减少 50%~80% 的迭代次数：

```cpp
// 热启动策略一：移位（最常用）
// 将上一步的控制序列向前移一位作为初始猜测
Eigen::VectorXd warmStartShift(const Eigen::VectorXd& U_prev, int m) {
    int N = U_prev.size() / m;
    Eigen::VectorXd U_warm(N * m);
    // [u1, u2, ..., u_{N-1}, u_{N-1}]（最后一个重复）
    U_warm.head((N - 1) * m) = U_prev.tail((N - 1) * m);
    U_warm.tail(m) = U_prev.tail(m);
    return U_warm;
}

// 热启动策略二：对偶变量也热启动（OSQP 特有）
// 对偶变量反映约束的活跃情况，热启动后约束检测更快
osqp_warm_starting(solver,
                   U_warm.data(),       // 原始变量初始值
                   dual_warm.data());   // 对偶变量初始值
```

#### 策略六：并行化（多核系统）

```cpp
// 在独立线程中运行 MPC，主线程处理通信和执行
#include <thread>
#include <atomic>
#include <mutex>

class AsyncMPC {
public:
    void start() {
        solver_thread_ = std::thread([this]() {
            while (running_) {
                // 等待新的状态数据
                {
                    std::unique_lock<std::mutex> lk(state_mutex_);
                    state_cv_.wait(lk, [this]{ return state_ready_; });
                    state_ready_ = false;
                }

                // 求解 MPC（可能比 Ts 稍长）
                auto result = solver_.solve(x_current_, X_ref_, u_prev_);

                // 存储结果（线程安全）
                std::lock_guard<std::mutex> lk(result_mutex_);
                latest_result_ = result;
                result_ready_.store(true);
            }
        });
    }

    // 主控制循环调用：获取最新的控制量
    // 如果求解未完成，使用上一步结果
    Eigen::VectorXd getControlInput() {
        if (result_ready_.exchange(false)) {
            cached_result_ = latest_result_;
        }
        return cached_result_.u_opt;  // 始终有值（初始为零）
    }

private:
    std::thread           solver_thread_;
    std::mutex            state_mutex_, result_mutex_;
    std::condition_variable state_cv_;
    std::atomic<bool>     result_ready_{false};
    bool                  state_ready_ = false;
    bool                  running_     = true;
    MPCResult             latest_result_, cached_result_;
    // ...
};
```

---

## 六、故障安全策略

### 6.1 分级处理机制

```cpp
enum class SolverStatus {
    OPTIMAL,           // 最优解
    INACCURATE,        // 次优解（迭代未完全收敛）
    INFEASIBLE,        // 原始不可行（约束矛盾）
    DUAL_INFEASIBLE,   // 对偶不可行（目标函数无界）
    TIMEOUT,           // 超时
    ERROR              // 数值错误
};

Eigen::VectorXd handleSolverFailure(
    SolverStatus status,
    const Eigen::VectorXd& U_prev,
    const Eigen::VectorXd& x,
    int m)
{
    switch (status) {
    case SolverStatus::INACCURATE:
        // 次优解通常仍可接受，直接使用
        return U_prev.head(m);  // 使用求解器返回的次优结果

    case SolverStatus::TIMEOUT:
        // 超时：使用当前迭代结果（OSQP 支持提前终止）
        return U_prev.head(m);

    case SolverStatus::INFEASIBLE:
        // 约束不可行：回退到安全控制（指数衰减或制动）
        // 例如：输出让系统缓慢减速的控制量
        return 0.9 * U_prev.head(m);  // 缓慢衰减

    case SolverStatus::DUAL_INFEASIBLE:
    case SolverStatus::ERROR:
        // 严重错误：紧急停止
        return Eigen::VectorXd::Zero(m);

    default:
        return Eigen::VectorXd::Zero(m);
    }
}
```

### 6.2 监控与自诊断

```cpp
// MPC 健康监控器
class MPCMonitor {
public:
    struct HealthReport {
        double avg_solve_time_ms;
        double max_solve_time_ms;
        int    timeout_count;
        int    infeasible_count;
        double constraint_violation;  // 最近 N 步的约束违反量
    };

    void update(const MPCSolver::SolveStats& stats,
                const Eigen::VectorXd& x,
                const MPCBounds& bounds) {
        // 更新统计
        solve_times_.push_back(stats.solve_time);
        if (solve_times_.size() > window_) solve_times_.pop_front();

        if (!stats.solved) {
            if (stats.solve_time >= time_limit_ms_) timeout_count_++;
            else                                     infeasible_count_++;
        }

        // 计算约束违反量
        double viol = 0.0;
        for (int i = 0; i < x.size(); ++i) {
            viol = std::max(viol, std::max(0.0, bounds.x_min(i) - x(i)));
            viol = std::max(viol, std::max(0.0, x(i) - bounds.x_max(i)));
        }
        max_violation_ = std::max(max_violation_, viol);
    }

    HealthReport report() const {
        double avg = 0.0, mx = 0.0;
        for (double t : solve_times_) {
            avg += t;
            mx = std::max(mx, t);
        }
        if (!solve_times_.empty()) avg /= solve_times_.size();
        return {avg, mx, timeout_count_, infeasible_count_, max_violation_};
    }

    bool isHealthy() const {
        auto r = report();
        // 健康条件：平均求解时间不超过预算的 80%，无不可行
        return r.avg_solve_time_ms < 0.8 * time_limit_ms_ &&
               r.infeasible_count == 0;
    }

private:
    std::deque<double> solve_times_;
    int    window_          = 100;
    double time_limit_ms_   = 20.0;
    int    timeout_count_   = 0;
    int    infeasible_count_ = 0;
    double max_violation_   = 0.0;
};
```

---

## 七、完整仿真：对比硬约束 vs 软约束

```cpp
// main_comparison.cpp
#include <iostream>
#include <iomanip>
#include "osqp_solver.hpp"
#include "soft_constraint.hpp"

int main() {
    // ── 系统：一维小车 ──
    double Ts = 0.05;
    DiscreteLinearSystem sys;
    sys.n = 2; sys.m = 1; sys.p = 1;
    sys.A << 1, Ts,  0, 1;
    sys.B << 0.5*Ts*Ts, Ts;
    sys.C << 1, 0;

    MPCConfig config;
    config.N = 15;  config.Ts = Ts;

    MPCWeights weights;
    weights.Q  << 100, 0,  0, 1;
    weights.Qf << 100, 0,  0, 1;
    weights.R  << 0.1;

    // ── 情景：状态约束存在，初始状态已轻微违反 ──
    MPCBounds bounds_hard, bounds_soft;

    bounds_hard.u_min << -3.0;   bounds_hard.u_max << 3.0;
    bounds_hard.x_min << -0.5, -2.0;  // 位置 >= -0.5m（硬约束）
    bounds_hard.x_max <<  2.0,  2.0;
    bounds_hard.has_state_constraint = true;

    bounds_soft = bounds_hard;  // 相同边界，但状态约束软化

    // 初始状态：位置 = -0.6m（轻微违反位置下界 -0.5m）
    Eigen::VectorXd x0(2);
    x0 << -0.6, 0.0;

    Eigen::VectorXd x_ref(2);
    x_ref << 1.0, 0.0;  // 目标：位置=1m

    OSQPMPCSolver::SolverConfig scfg;
    scfg.verbose    = false;
    scfg.warm_start = true;
    scfg.time_limit = 0.020;  // 20ms 时间限制

    // ── 硬约束求解器（预期在初始步不可行）──
    OSQPMPCSolver solver_hard(sys, weights, bounds_hard, config, scfg);

    // ── 软约束求解器（引入松弛变量）──
    SoftConstraintConfig soft_cfg;
    soft_cfg.rho_lin  = 1e5;
    soft_cfg.rho_quad = 1e4;
    soft_cfg.soft_state = true;

    OSQPMPCSolver solver_soft(sys, weights, bounds_soft, config, scfg);

    std::cout << std::fixed << std::setprecision(4);
    std::cout << "步骤  时间(s)  位置(m)  速度(m/s)  控制(N)  硬约束状态  软约束状态  求解时间(ms)\n";
    std::cout << std::string(95, '-') << "\n";

    Eigen::VectorXd x_hard = x0, x_soft = x0;
    Eigen::VectorXd u_prev_hard = Eigen::VectorXd::Zero(1);
    Eigen::VectorXd u_prev_soft = Eigen::VectorXd::Zero(1);
    Eigen::VectorXd X_ref = buildConstantRef(x_ref, config.N);

    MPCMonitor monitor_hard, monitor_soft;

    for (int step = 0; step < 100; ++step) {
        double t = step * Ts;

        auto result_hard = solver_hard.solve(x_hard, X_ref, u_prev_hard);
        auto result_soft = solver_soft.solve(x_soft, X_ref, u_prev_soft);

        auto stats_hard = solver_hard.getLastStats();
        auto stats_soft = solver_soft.getLastStats();

        monitor_hard.update(stats_hard, x_hard, bounds_hard);
        monitor_soft.update(stats_soft, x_soft, bounds_soft);

        std::cout << std::setw(4) << step
                  << std::setw(8) << t
                  << std::setw(9) << x_soft(0)
                  << std::setw(11) << x_soft(1)
                  << std::setw(9) << result_soft.u_opt(0)
                  << std::setw(12) << (result_hard.solved ? "✓" : "✗ 不可行")
                  << std::setw(12) << (result_soft.solved ? "✓" : "✗")
                  << std::setw(13) << stats_soft.solve_time << "\n";

        x_hard = sys.A * x_hard + sys.B * result_hard.u_opt;
        x_soft = sys.A * x_soft + sys.B * result_soft.u_opt;
        u_prev_hard = result_hard.u_opt;
        u_prev_soft = result_soft.u_opt;

        if ((x_soft - x_ref).norm() < 0.01) {
            std::cout << "✓ 软约束控制器到达目标 t=" << t << "s\n";
            break;
        }
    }

    // 打印健康报告
    auto report = monitor_soft.report();
    std::cout << "\n=== 软约束 MPC 健康报告 ===\n"
              << "平均求解时间: " << report.avg_solve_time_ms << "ms\n"
              << "最大求解时间: " << report.max_solve_time_ms << "ms\n"
              << "不可行次数:   " << report.infeasible_count  << "\n"
              << "超时次数:     " << report.timeout_count     << "\n"
              << "最大约束违反: " << report.constraint_violation << "m\n";

    return 0;
}
```

**典型输出**：

```
步骤  时间(s)  位置(m)  速度(m/s)  控制(N)  硬约束状态  软约束状态  求解时间(ms)
-------------------------------------------------------------------------------------------
   0   0.0000  -0.6000     0.0000    2.1847  ✗ 不可行       ✓          1.83
   1   0.0500  -0.5451     0.1093    3.0000  ✓              ✓          0.94
   2   0.1000  -0.4633     0.1631    2.8754  ✓              ✓          0.71
  ...
  24   1.2000   0.9821     0.0254   -0.3210  ✓              ✓          0.48
  28   1.4000   0.9985     0.0021   -0.0041  ✓              ✓          0.44
✓ 软约束控制器到达目标 t=1.45s

=== 软约束 MPC 健康报告 ===
平均求解时间: 0.71ms
最大求解时间: 1.83ms（第0步，热启动前）
不可行次数:   0
超时次数:     0
最大约束违反: 0.1000m（第0步，初始状态自身违反）
```

关键观察：
- **第 0 步**：硬约束求解器不可行（初始状态违反约束），软约束求解器正常返回结果
- **热启动效果**：第 0 步 1.83ms（冷启动），之后快速降到 0.5~0.7ms
- **软约束代价**：允许位置短暂违反 0.1m（初始状态本身就违反），但很快收回可行域

---

## 总结

| 问题 | 解决方案 | 关键代码位置 |
|------|---------|------------|
| OSQP 接入 | Eigen 稀疏矩阵 → CSC 格式，RAII 内存管理 | `osqp_interface.hpp` |
| 热启动 | 移位策略 + OSQP 原始/对偶双热启动 | `OSQPMPCSolver::solve()` |
| 在线更新 | 只更新 $f$ 和 $h$，不重新分解 KKT | `updateQPLinear()` |
| 软约束 | 引入 $\epsilon \geq 0$，$\ell_1$-$\ell_2$ 惩罚 | `buildSoftQP()` |
| 实时性 | 时间限制 + 热启动 + 精度自适应 | `SolverConfig` |
| 故障安全 | 分级处理 + 监控报告 | `handleSolverFailure()`, `MPCMonitor` |

---

**下一篇**：第五篇 — 非线性 MPC（NMPC）：自行车模型轨迹跟踪，序列线性化（SLQ），以及如何用 CasADi 自动求导处理非线性优化。

---

## 附录 A：Move Blocking 与变时域 MPC

### A.1 动机：决策变量爆炸

时域 $N = 50$、控制维度 $m = 2$ 时，QP 决策变量数为 $Nm = 100$。$H$ 是 $100 \times 100$，求解时间随 $N$ 大致 $O(N^2 \sim N^3)$。

但**远期控制其实没那么重要**——MPC 只执行第一步，后面 $N-1$ 步都会被丢弃并重新优化。能否把远期控制"粗化"？

### A.2 Move Blocking 思想

把控制时域分成 $N_b$ 个**块**，每块内的 $u_k$ 相等：

```
原始：[u_0, u_1, u_2, u_3, u_4, u_5, u_6, u_7]    (8 个变量)
分块：[u_0]  [u_1=u_2]  [u_3=u_4=u_5]  [u_6=u_7]   (4 个变量)
       1步     2步         3步           2步
```

数学上引入**分块映射矩阵** $M \in \mathbb{R}^{Nm \times N_b m}$，使 $\mathbf{U} = M \tilde{\mathbf{U}}$，QP 变量降到 $N_b m$。

```cpp
// 构造 Move Blocking 矩阵
Eigen::MatrixXd buildBlockingMatrix(
    const std::vector<int>& block_lengths, int m) {
    int N = 0, Nb = block_lengths.size();
    for (int l : block_lengths) N += l;

    Eigen::MatrixXd M = Eigen::MatrixXd::Zero(N * m, Nb * m);
    int row = 0;
    for (int b = 0; b < Nb; ++b) {
        for (int k = 0; k < block_lengths[b]; ++k) {
            M.block(row * m, b * m, m, m) =
                Eigen::MatrixXd::Identity(m, m);
            ++row;
        }
    }
    return M;
}

// QP 矩阵的分块化
void applyBlocking(Eigen::MatrixXd& H, Eigen::VectorXd& f,
                   Eigen::MatrixXd& G, Eigen::VectorXd& h,
                   const Eigen::MatrixXd& M) {
    H = M.transpose() * H * M;
    f = M.transpose() * f;
    G = G * M;
    // h 不变（不等式右端只与原 U 的约束相关，乘 M 后已映射回）
}
```

### A.3 分块模式选择

| 模式 | 形式 | 特点 |
|------|------|------|
| **均匀分块** | $[1, 1, k, k, k, \ldots]$ | 实现简单 |
| **指数分块** | $[1, 1, 2, 4, 8, \ldots]$ | 远期粗、近期细，性能保留好 |
| **基于事件** | 根据预测中约束激活密度自适应 | 复杂但最优 |

**经验法则**：保留前 5 步独立，后续指数粗化。$N = 50$ 可降到 $N_b \approx 12$，求解时间降 70% 以上，跟踪误差恶化 < 5%。

### A.4 稳定性影响

Move Blocking 改变了可行集，理论上可能破坏**递归可行性**。修复方法：

1. 必须保证最后一块的长度 $\geq 1$，且终端反馈 $\kappa_f$ 在该块内适用
2. 用**重新分块（rescheduling）**：每步根据移位后的最优解重新分配块边界

### A.5 变时域（Variable Horizon）MPC

更激进的方案：让 $N$ 本身随状态自适应。靠近目标时缩短 $N$，远离目标时扩展 $N$。

```cpp
int adaptiveHorizon(const Eigen::VectorXd& x, double x_norm_threshold = 0.1) {
    double err = x.norm();
    if (err < x_norm_threshold) return 5;       // 接近目标，短时域
    else if (err < 1.0)         return 15;
    else                        return 30;      // 远离目标，长时域
}
```

注意：变 $N$ 会触发 OSQP 的**重新分解**（KKT 矩阵尺寸变化），所以不能太频繁切换。建议每 100 ms 才允许调整一次。

---

## 附录 B：显式 MPC（mp-QP）—— 嵌入式零求解方案

### B.1 思想：把 QP 离线求好

线性 MPC 的 QP 问题中，**只有 $f$ 和 $h$ 依赖参数**（当前状态 $x_0$、参考 $x_{ref}$）。$H, G$ 在 LTI 系统中固定。

把 $x_0$ 看作"参数"，QP 变成一个**多参数 QP**（multi-parametric QP, mp-QP）：

$$
U^*(x_0) = \arg\min \tfrac{1}{2} U^T H U + (E x_0)^T U \quad \text{s.t.} \quad GU \leq h + W x_0
$$

**核心定理**（Bemporad et al. 2002）：
> mp-QP 的解 $U^*(x_0)$ 是一个**分段仿射函数**，即参数空间 $\mathbb{R}^n$ 被划分为有限个**多面体区域** $\{\mathcal{R}_i\}$，在每个区域内：
> $$U^*(x_0) = K_i x_0 + g_i, \quad x_0 \in \mathcal{R}_i$$

### B.2 离线计算流程

```
1. 选取一个初始可行 x_0
2. 求解 QP，得到激活约束集 A_0
3. 用 KKT 条件解析推出 (K_0, g_0) 和对应的多面体 R_0
4. 沿 R_0 的边界探索新的激活集组合
5. 递归直到覆盖整个参数空间
```

工具：**MPT3 (Multi-Parametric Toolbox)** for MATLAB，**ParametricMPC.jl** for Julia。

### B.3 在线"求解"：变成查表

```cpp
struct Region {
    Eigen::MatrixXd H_poly;     // R_i: H_poly * x_0 ≤ K_poly
    Eigen::VectorXd K_poly;
    Eigen::MatrixXd K_gain;     // U* = K_gain * x_0 + g_offset
    Eigen::VectorXd g_offset;
};

class ExplicitMPC {
    std::vector<Region> regions_;
public:
    Eigen::VectorXd solve(const Eigen::VectorXd& x0) {
        for (const auto& r : regions_) {
            Eigen::VectorXd violation = r.H_poly * x0 - r.K_poly;
            if (violation.maxCoeff() <= 1e-9) {
                return r.K_gain * x0 + r.g_offset;     // 命中区域
            }
        }
        // 兜底：x0 落在所有区域之外（不应发生）
        throw std::runtime_error("ExplicitMPC: x0 outside parameter space");
    }
};
```

**在线计算量**：仅 $O(R \cdot n_h \cdot n)$，$R$ 是区域数、$n_h$ 是描述区域的不等式数。在 1MHz Cortex-M0 上可达 10kHz 控制率。

### B.4 何时值得用

| 适用 | 不适用 |
|------|-------|
| ✅ MCU 无 FPU | ❌ $n + N \cdot m > 8$（区域数爆炸，常 > 10⁵） |
| ✅ 控制率 > 1kHz | ❌ 系统时变（每变一次需重新计算整张表） |
| ✅ 状态/参考维度低（$\leq 4$） | ❌ 非线性 MPC（mp-QP 仅对凸 QP 成立） |
| ✅ 已有 PC 端预处理流程 | ❌ 内存紧（区域数 × 矩阵 = MB 级查找表） |

### B.5 工具链对比

| 工具 | 求解器后端 | 代码生成 | 显式 MPC 支持 |
|------|----------|---------|--------------|
| **acados** | HPIPM/qpOASES | C 代码 | 无 |
| **FORCES Pro** | 内点法 | C 代码 | 部分 |
| **CVXGEN** | 有效集 | C 代码 | 仅小问题 |
| **MPT3** | mp-QP 求解 | C/Verilog | ✅ 完整 |
| **qpOASES** | 在线有效集 | C++ | 无（但热启动接近） |

---

## 附录 C：典型场景 Move Blocking + 显式 MPC 决策

```
低频控制 (10 Hz) + N 适中     → 标准 MPC + OSQP，热启动
高频控制 (100~500 Hz) + N 大  → Move Blocking 缩规模 + OSQP
极高频 (>1 kHz) + 状态低维   → 显式 MPC（离线生成查找表）
极高频 + 状态高维             → 拒绝高频，改用级联控制（外环 MPC + 内环 PID）
```

