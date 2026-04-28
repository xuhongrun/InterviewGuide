# 第二·五篇：MPC 稳定性保证 —— Lyapunov 函数、终端约束与递归可行性

---

## 引言

前两篇推导了线性 MPC 的预测方程与状态空间形式。一个核心问题被刻意回避：

> **MPC 在每个采样时刻只求解一个 *有限时域* 的开环最优控制问题，并只执行第一步控制——这种"短视滚动"的方案为什么能保证闭环系统稳定？**

工程师在调参 $Q, R, N$ 时往往凭直觉，但在面试与论文中，必须能**严格回答**以下三类问题：

1. **稳定性（Stability）**：闭环 $x_{k+1} = (A - BK_{MPC})x_k$ 是否渐近稳定？
2. **可行性（Feasibility）**：第 $k$ 步 QP 有解，能保证第 $k+1$ 步也有解吗？
3. **最优性（Optimality）**：有限时域 MPC 能否逼近无穷时域 LQR 的性能？

本篇给出**三大保证条件**与**完整 Lyapunov 证明框架**，并通过 C++ 仿真验证。

---

## 一、Lyapunov 稳定性回顾（离散版）

### 1.1 离散 Lyapunov 定理

设 $x_{k+1} = f(x_k)$，$f(0) = 0$。若存在连续函数 $V(x)$ 满足：

$$V(x) > 0 \quad \forall x \neq 0, \quad V(0) = 0$$
$$\Delta V(x_k) := V(x_{k+1}) - V(x_k) \leq -\alpha(\|x_k\|), \quad \alpha \in \mathcal{K}_\infty$$

则原点 $x = 0$ **全局渐近稳定**（GAS）。

### 1.2 MPC 中的"自然"Lyapunov 候选

把 MPC 的**最优值函数** $V_N(x_k) := J^*(x_k)$（即 QP 的最优目标函数值）作为 Lyapunov 函数候选。

只要能证明：

$$V_N(x_{k+1}) - V_N(x_k) \leq -\ell(x_k, u_k^*) \leq -\lambda_{\min}(Q) \|x_k\|^2$$

闭环系统就稳定。**核心难点**：在滚动时域中，第 $k+1$ 步的优化问题与第 $k$ 步*不是同一个问题*——时域窗口向前滑动了一步——直接比较 $V_N(x_{k+1})$ 与 $V_N(x_k)$ 并不平凡。

---

## 二、稳定性三大设计要素

经过 Mayne 等人 2000 年的经典综述，**线性 MPC 闭环渐近稳定性**的充分条件归纳为三件套：

| 要素 | 数学表述 | 工程含义 |
|------|---------|---------|
| **终端代价** $V_f(x)$ | $V_f(x) = x^T P x$，$P$ 为 DARE 解 | 把"未来无穷时域代价"压缩到一个项 |
| **终端约束集** $\mathcal{X}_f$ | $\mathcal{X}_f$ 是某个状态反馈 $K_f$ 下的**正不变集**，且满足约束 | 确保 $x_N \in \mathcal{X}_f$ 后能"安全收尾" |
| **终端控制器** $\kappa_f(x) = -K_f x$ | 在 $\mathcal{X}_f$ 内，$\kappa_f$ 镇定且约束相容 | 滚动一步后仍可"接续"上一时刻的解 |

这三者必须**协调设计**——单独满足任何一个都不够。

### 2.1 DARE 终端代价：把无穷压缩到一项

考虑无约束 LQR 问题：

$$\min_{u_0, u_1, \ldots} \sum_{k=0}^{\infty} (x_k^T Q x_k + u_k^T R u_k)$$

它的最优值函数恰好是 $V_\infty(x) = x^T P_\infty x$，其中 $P_\infty$ 是离散 Riccati 方程（DARE）的解：

$$P = A^T P A - A^T P B (R + B^T P B)^{-1} B^T P A + Q$$

**关键定理**（Mayne et al. 2000）：

> 若选 $V_f(x) = x^T P_\infty x$ 为终端代价，且终端约束集为对应 LQR 反馈 $K_\infty$ 下的不变集，则**对于任意 $N \geq 1$**，MPC 闭环渐近稳定，且性能不劣于 LQR 的 $N$ 步截断。

**直观解释**：终端代价 $x_N^T P_\infty x_N$ 等于"如果从 $x_N$ 开始用 LQR 继续控制下去的总代价"——这相当于**把无限时域代价精确补偿在 $N$ 步窗口的尾部**，因此短视的 $N$ 步问题与无限时域问题"等价"。

```cpp
// 用 Eigen 求 DARE：迭代法（简单但可靠）
Eigen::MatrixXd solveDARE(const Eigen::MatrixXd& A,
                          const Eigen::MatrixXd& B,
                          const Eigen::MatrixXd& Q,
                          const Eigen::MatrixXd& R,
                          int max_iter = 1000,
                          double tol = 1e-10) {
    Eigen::MatrixXd P = Q;
    for (int i = 0; i < max_iter; ++i) {
        Eigen::MatrixXd P_next = A.transpose() * P * A
            - A.transpose() * P * B
              * (R + B.transpose() * P * B).ldlt().solve(B.transpose() * P * A)
            + Q;
        if ((P_next - P).norm() < tol) return P_next;
        P = P_next;
    }
    return P;  // 未收敛时返回最后一次迭代结果
}

// 对应的 LQR 增益
Eigen::MatrixXd computeLQRGain(const Eigen::MatrixXd& A,
                               const Eigen::MatrixXd& B,
                               const Eigen::MatrixXd& R,
                               const Eigen::MatrixXd& P) {
    return (R + B.transpose() * P * B).ldlt()
            .solve(B.transpose() * P * A);
}
```

### 2.2 终端约束集 $\mathcal{X}_f$：可镇定的"安全区"

$\mathcal{X}_f$ 必须满足三条性质：

1. **正不变性**：$x \in \mathcal{X}_f \Rightarrow (A - BK_\infty) x \in \mathcal{X}_f$
2. **约束相容**：$\forall x \in \mathcal{X}_f$，$x \in \mathbb{X}$ 且 $-K_\infty x \in \mathbb{U}$
3. **包含原点**

构造方法：取**最大正不变集**（Maximum Positively Invariant Set, MPIS），算法上常用 **Gilbert-Tan 递归**：

```
Ω_0 = X ∩ {x : -K∞ x ∈ U}
Ω_{i+1} = Ω_i ∩ {x : (A - B K∞) x ∈ Ω_i}
直到 Ω_{i+1} = Ω_i 收敛
```

### 2.3 终端反馈与递归

终端反馈 $\kappa_f(x) = -K_\infty x$ 是 LQR 增益。它在 $\mathcal{X}_f$ 内**可行且镇定**，是后面证明递归可行性的关键。

---

## 三、闭环稳定性完整证明

### 3.1 设定

线性系统 $x_{k+1} = A x_k + B u_k$，约束 $x \in \mathbb{X}, u \in \mathbb{U}$。在第 $k$ 步求解：

$$
\begin{aligned}
\min_{u_{0|k}, \ldots, u_{N-1|k}} \quad & \sum_{i=0}^{N-1} \ell(x_{i|k}, u_{i|k}) + V_f(x_{N|k}) \\
\text{s.t.} \quad & x_{i+1|k} = A x_{i|k} + B u_{i|k} \\
& x_{i|k} \in \mathbb{X}, \ u_{i|k} \in \mathbb{U} \\
& x_{N|k} \in \mathcal{X}_f \\
& x_{0|k} = x_k
\end{aligned}
$$

记最优解为 $\mathbf{u}^*_k = \{u^*_{0|k}, \ldots, u^*_{N-1|k}\}$，最优值 $V_N(x_k)$，闭环执行 $u_k = u^*_{0|k}$。

### 3.2 递归可行性证明

**断言**：若第 $k$ 步可行，则第 $k+1$ 步必可行。

**证明（构造法）**：取**移位序列**

$$\tilde{\mathbf{u}}_{k+1} = \{u^*_{1|k}, u^*_{2|k}, \ldots, u^*_{N-1|k}, \kappa_f(x^*_{N|k})\}$$

即把上一步解的后 $N-1$ 步往前挪一格，最后用终端反馈补一步。

- 前 $N-1$ 步显然可行（继承自上一步最优）
- 最后一步 $u_{N-1|k+1} = \kappa_f(x^*_{N|k})$，由 $\mathcal{X}_f$ 的不变性，$x_{N|k+1} = (A - BK_\infty) x^*_{N|k} \in \mathcal{X}_f$ ✓

故第 $k+1$ 步至少存在一个可行解 $\tilde{\mathbf{u}}_{k+1}$。$\square$

### 3.3 Lyapunov 下降证明

设 $\tilde{V}_N(x_{k+1})$ 为使用移位序列 $\tilde{\mathbf{u}}_{k+1}$ 时的目标函数值。由最优性：

$$V_N(x_{k+1}) \leq \tilde{V}_N(x_{k+1})$$

展开 $\tilde{V}_N$：

$$
\tilde{V}_N = V_N(x_k) - \ell(x_k, u^*_{0|k}) - V_f(x^*_{N|k}) + \ell(x^*_{N|k}, \kappa_f(x^*_{N|k})) + V_f(x_{N|k+1})
$$

**关键不等式**（终端代价的"自衰减"性质）：

$$V_f((A - BK_\infty) x) - V_f(x) + \ell(x, -K_\infty x) \leq 0, \quad \forall x \in \mathcal{X}_f$$

这正是 DARE 的等价形式！代入得：

$$V_N(x_{k+1}) - V_N(x_k) \leq -\ell(x_k, u^*_{0|k}) \leq -\lambda_{\min}(Q) \|x_k\|^2$$

故 $V_N$ 是闭环 Lyapunov 函数，$x_k \to 0$。$\square$

---

## 四、当不能使用终端约束时

终端约束 $x_N \in \mathcal{X}_f$ 会**显著减少 QP 的可行域**——尤其当 $\mathcal{X}_f$ 很小时，初始可行域几乎为空。

### 4.1 准无限时域 MPC（Quasi-Infinite Horizon）

**思想**：去掉显式 $x_N \in \mathcal{X}_f$，但保留 $V_f(x_N) = x_N^T P_\infty x_N$。只要 $N$ 足够大，最优解会"自动"把 $x_N$ 拉进 $\mathcal{X}_f$ 附近。

**充分条件**（Limón et al. 2006）：存在 $N^*$ 使 $\forall N \geq N^*$，$V_N(x_0)$ 有界保证 $x_N \in \mathcal{X}_f$。$N^*$ 的下界与系统稳定性、约束严格度相关。

### 4.2 无终端约束 MPC 的稳定性

实际工程中，**只用大权重 $Q_f \gg Q$ 而省略终端约束**的方案最常见。其稳定性需要：

| 条件 | 工程做法 |
|------|---------|
| $N$ 充分大 | $N \geq$ 系统响应时间 / $T_s$（经验：覆盖 1~3 个开环时常数） |
| $Q_f$ 选 DARE 解 $P_\infty$ | 而非简单令 $Q_f = Q$ |
| 系统稳定可镇定 | $(A, B)$ 可控，$(A, Q^{1/2})$ 可观 |

**警示**：若 $Q_f$ 选小，且 $N$ 短，MPC 可能**振荡或发散**——这不是数值问题，是**理论缺陷**。

---

## 五、面试常见问

### Q1：为什么 MPC 不一定稳定？

> 标准 LQR 在无穷时域下天然稳定（DARE 解 $P_\infty$ 给出闭环极点全在单位圆内）。但 MPC 是 *有限时域* 的——若不补偿"截断的尾部代价"，就丢失了无穷时域的稳定性保证。  
> **三大补偿手段**：终端代价（用 DARE 解）+ 终端约束（不变集）+ 终端反馈（LQR 增益）。

### Q2：DARE 终端权重为什么能保证稳定？

> $V_f(x) = x^T P_\infty x$ 等于"从 $x_N$ 开始用 LQR 控制到无穷的代价"。它把 *被截断的尾部* 完整补回来——MPC 的总目标 $\sum_0^{N-1} \ell + V_f$ 等价于无穷时域 LQR。因此 N 步问题与无限步问题最优解一致。

### Q3：递归可行性为什么不自动成立？

> 第 $k$ 步可行只意味着 $x_k$ 出发存在一条 $N$ 步可行轨迹。第 $k+1$ 步要求从 $x_{k+1} = Ax_k + Bu^*_{0|k}$ 出发同样存在 $N$ 步可行轨迹——但 *这是一个新问题*。  
> 通过"移位 + 终端反馈补一步"的构造可证：若 $\mathcal{X}_f$ 是不变集，构造的序列必然可行，故递归可行成立。

### Q4：实际工程中我们都用 DARE 吗？

> 大量工业 MPC（化工、过程控制）**只用 $Q_f = Q$ + 大 $N$**，靠时域足够长来"自然"逼近无限时域。  
> 自动驾驶/机器人这种实时性敏感场景，**$N$ 不能太大**（否则求解超时），此时建议用 DARE。  
> 嵌入式 MCU 部署时，DARE 可以离线算好烧到 ROM 里，零运行时代价。

### Q5：你的系统不稳定，怎么诊断是稳定性理论问题还是参数选择问题？

> 三步诊断：
> 1. 把 $Q_f$ 换成 DARE 解 $P_\infty$ —— 若稳定，原因是终端代价不当
> 2. 把 $N$ 加倍 —— 若稳定，原因是时域过短
> 3. 关闭所有约束 —— 若稳定，原因是约束激活引起的可行性问题

---

## 六、C++ 完整稳定性诊断工具

```cpp
// stability_diagnostics.hpp
#include <Eigen/Dense>
#include <vector>
#include <iostream>

struct MPCStabilityReport {
    bool dare_converged;
    double dare_residual;
    Eigen::MatrixXd P_inf;          // DARE 解
    Eigen::MatrixXd K_inf;          // LQR 反馈增益
    std::vector<std::complex<double>> closed_loop_poles;  // 闭环极点
    bool spectral_radius_ok;        // 闭环极点全在单位圆内
    double spectral_radius;
};

class MPCStabilityChecker {
public:
    MPCStabilityReport check(const Eigen::MatrixXd& A,
                             const Eigen::MatrixXd& B,
                             const Eigen::MatrixXd& Q,
                             const Eigen::MatrixXd& R) {
        MPCStabilityReport rpt;

        // 1. 求 DARE
        rpt.P_inf = solveDARE(A, B, Q, R);
        rpt.dare_residual = (A.transpose() * rpt.P_inf * A
            - A.transpose() * rpt.P_inf * B
              * (R + B.transpose() * rpt.P_inf * B).ldlt()
                .solve(B.transpose() * rpt.P_inf * A)
            + Q - rpt.P_inf).norm();
        rpt.dare_converged = rpt.dare_residual < 1e-6;

        // 2. LQR 增益
        rpt.K_inf = computeLQRGain(A, B, R, rpt.P_inf);

        // 3. 闭环极点
        Eigen::MatrixXd Acl = A - B * rpt.K_inf;
        Eigen::EigenSolver<Eigen::MatrixXd> es(Acl);
        rpt.closed_loop_poles.clear();
        rpt.spectral_radius = 0;
        for (int i = 0; i < es.eigenvalues().size(); ++i) {
            auto lam = es.eigenvalues()[i];
            rpt.closed_loop_poles.push_back(lam);
            rpt.spectral_radius = std::max(rpt.spectral_radius, std::abs(lam));
        }
        rpt.spectral_radius_ok = rpt.spectral_radius < 1.0;

        return rpt;
    }

    void printReport(const MPCStabilityReport& r) {
        std::cout << "=== MPC 稳定性诊断 ===\n";
        std::cout << "DARE 收敛：" << (r.dare_converged ? "是" : "否")
                  << " (残差 " << r.dare_residual << ")\n";
        std::cout << "闭环谱半径：" << r.spectral_radius
                  << (r.spectral_radius_ok ? " ✓ 稳定" : " ✗ 不稳定") << "\n";
        std::cout << "闭环极点：\n";
        for (auto& p : r.closed_loop_poles)
            std::cout << "  " << p << " |.| = " << std::abs(p) << "\n";
    }
};
```

---

## 总结

| 问题 | 答案要点 |
|------|---------|
| MPC 凭什么稳定？ | 终端代价 + 终端约束 + 终端反馈"三件套" |
| 终端代价怎么选？ | DARE 解 $P_\infty$；退而求其次用大 $N$ + $Q_f = Q$ |
| 递归可行性怎么证？ | 移位序列 + 终端反馈补一步，依赖不变集 $\mathcal{X}_f$ |
| 何时不需要终端约束？ | 准无限时域：$N \geq N^*$，靠时域长度自然满足 |
| 工程上怎么诊断？ | 检查 DARE 残差 + 闭环谱半径 + 不变集大小 |

> **下一篇**：第三篇 — 完成 QP 矩阵推导后，将引入 KKT 条件用于诊断求解器故障，并讨论 $\Delta u$ 增量形式 vs 绝对量形式的工程权衡。
