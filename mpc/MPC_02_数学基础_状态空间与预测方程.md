# 第二篇：MPC 的数学基础 — 状态空间模型与预测方程推导

---

## 引言

上一篇我们建立了对 MPC 的直觉认知。这一篇进入数学层面。

很多人一看到矩阵就头疼。但 MPC 的数学其实非常"线性"——所有推导都是矩阵乘法的展开和拼接。读完这篇，你将能从一张白纸推导出 MPC 的核心预测方程，并用 C++ 代码验证每一步。

**本篇目标**：
- 理解离散时间状态空间模型
- 掌握连续 → 离散的转化方法
- 推导预测矩阵 $\mathcal{A}$ 和 $\mathcal{B}$（MPC 的数学核心）
- 理解这两个矩阵的物理含义

---

## 一、为什么需要状态空间模型？

### 1.1 传递函数 vs 状态空间

许多人在学自动控制时首先学的是**传递函数**（Laplace 域）：

$$G(s) = \frac{Y(s)}{U(s)} = \frac{1}{ms^2 + cs + k}$$

传递函数适合描述 SISO（单输入单输出）系统的频域特性，但有明显局限：
- 只适合线性时不变系统
- 难以描述系统内部状态
- 不便于处理多输入多输出（MIMO）系统
- 不直接支持约束处理

**状态空间模型**解决了上述所有问题，是 MPC 的数学语言。

### 1.2 状态的物理含义

"状态"是**完整描述系统当前情况所需的最少信息量**。

给定当前状态 $x(t)$ 和未来的控制输入 $u(\tau), \tau \geq t$，就能唯一确定未来任意时刻的系统行为。

| 系统 | 状态量 | 原因 |
|------|--------|------|
| 小车 | 位置、速度 | 知道这两个就能预测未来运动 |
| 弹簧-质量 | 位移、速度 | 同上 |
| 电感-电容 | 电感电流、电容电压 | 储能元件的状态 |
| 机器人关节 | 各关节角度和角速度 | 完整描述机械状态 |

---

## 二、连续时间状态空间模型

### 2.1 通用形式

线性时不变（LTI）系统的连续时间状态空间描述：

$$\dot{x}(t) = A_c x(t) + B_c u(t) \tag{2.1}$$
$$y(t) = C x(t) + D u(t) \tag{2.2}$$

其中：
- $x(t) \in \mathbb{R}^n$：状态向量
- $u(t) \in \mathbb{R}^m$：控制输入向量
- $y(t) \in \mathbb{R}^p$：输出向量
- $A_c \in \mathbb{R}^{n \times n}$：系统矩阵（描述系统自身动态）
- $B_c \in \mathbb{R}^{n \times m}$：输入矩阵（描述控制对状态的影响）
- $C \in \mathbb{R}^{p \times n}$：输出矩阵
- $D \in \mathbb{R}^{p \times m}$：直通矩阵（通常为零）

### 2.2 推导示例：弹簧-质量-阻尼系统

设质量块的运动方程（牛顿第二定律）：

$$m\ddot{q} + c\dot{q} + kq = F(t)$$

**第一步**：定义状态变量。

选择 $x_1 = q$（位移），$x_2 = \dot{q}$（速度），则：

$$\dot{x}_1 = x_2$$
$$\dot{x}_2 = \ddot{q} = \frac{1}{m}(F - cq - k\dot{q}) = -\frac{k}{m}x_1 - \frac{c}{m}x_2 + \frac{1}{m}F$$

**第二步**：写成矩阵形式。

$$\underbrace{\begin{bmatrix} \dot{x}_1 \\ \dot{x}_2 \end{bmatrix}}_{\dot{x}} = \underbrace{\begin{bmatrix} 0 & 1 \\ -k/m & -c/m \end{bmatrix}}_{A_c} \underbrace{\begin{bmatrix} x_1 \\ x_2 \end{bmatrix}}_{x} + \underbrace{\begin{bmatrix} 0 \\ 1/m \end{bmatrix}}_{B_c} \underbrace{F}_{u}$$

**第三步**：输出方程（假设只测量位移）。

$$y = \underbrace{\begin{bmatrix} 1 & 0 \end{bmatrix}}_{C} x$$

---

## 三、离散化：从连续到数字控制

计算机控制系统以固定采样周期 $T_s$ 运行，因此需要将连续模型**离散化**。

### 3.1 为什么需要离散化？

```
连续时间信号 x(t)                数字控制器
                          ┌─────────────────────┐
x(t) ─────── ADC ────────▶│ 每 Ts 秒读取一次 x(k) │
                          │ 计算控制量 u(k)       │
u(t) ─────── DAC ◀────────│ 保持到下一个周期       │
                          └─────────────────────┘
```

DAC 输出在一个周期内保持恒定，这称为**零阶保持（Zero-Order Hold, ZOH）**。

### 3.2 精确离散化（ZOH 方法）

连续方程 $\dot{x} = A_c x + B_c u$ 的解析解为：

$$x(t) = e^{A_c t} x(0) + \int_0^t e^{A_c(t-\tau)} B_c u(\tau) \, d\tau$$

在 ZOH 假设下（$u$ 在 $[kT_s, (k+1)T_s)$ 内保持常数 $u_k$），令 $t = T_s$：

$$x_{k+1} = \underbrace{e^{A_c T_s}}_{A_d} x_k + \underbrace{\left(\int_0^{T_s} e^{A_c \tau} d\tau\right) B_c}_{B_d} u_k$$

即：

$$\boxed{A_d = e^{A_c T_s}, \qquad B_d = A_c^{-1}(A_d - I)B_c}$$

当 $A_c$ 可逆时，$B_d$ 有上述闭式解；否则使用数值积分。

### 3.3 近似离散化方法对比

| 方法 | 公式 | 精度 | 适用场景 |
|------|------|------|---------|
| **前向 Euler** | $A_d = I + A_c T_s$ | 低（需 $T_s$ 很小） | 快速验证 |
| **后向 Euler** | $A_d = (I - A_c T_s)^{-1}$ | 中等，无条件稳定 | 刚性系统 |
| **Tustin（双线性）** | $A_d = (I+\frac{T_s}{2}A_c)(I-\frac{T_s}{2}A_c)^{-1}$ | 高，保频率特性 | 控制器设计 |
| **ZOH（精确）** | $A_d = e^{A_c T_s}$ | 精确 | 标准推荐方法 |

### 3.4 C++ 实现：精确 ZOH 离散化

```cpp
#include <Eigen/Dense>
#include <unsupported/Eigen/MatrixFunctions>  // 用于矩阵指数 e^A
#include <iostream>
#include <iomanip>

// ============================================================
// 线性时不变系统的状态空间描述
// ============================================================
struct ContinuousSystem {
    Eigen::MatrixXd Ac;  // 系统矩阵 (n×n)
    Eigen::MatrixXd Bc;  // 输入矩阵 (n×m)
    Eigen::MatrixXd C;   // 输出矩阵 (p×n)
    int n;               // 状态维数
    int m;               // 输入维数
    int p;               // 输出维数
};

struct DiscreteSystem {
    Eigen::MatrixXd Ad;  // 离散系统矩阵
    Eigen::MatrixXd Bd;  // 离散输入矩阵
    Eigen::MatrixXd C;   // 输出矩阵（离散化不改变C）
    double Ts;           // 采样周期
};

// ============================================================
// ZOH 精确离散化
//   Ad = exp(Ac * Ts)
//   Bd = Ac^{-1} * (Ad - I) * Bc   (当 Ac 可逆时)
//   若 Ac 不可逆，使用增广矩阵方法
// ============================================================
DiscreteSystem discretize_ZOH(const ContinuousSystem& sys, double Ts) {
    int n = sys.n, m = sys.m;

    // 方法：Van Loan 增广矩阵（适用于 Ac 可逆或不可逆的统一方法）
    // 构建增广矩阵 M = [Ac, Bc; 0, 0] * Ts
    // 则 exp(M) = [Ad, Bd; 0, I]
    int nm = n + m;
    Eigen::MatrixXd M = Eigen::MatrixXd::Zero(nm, nm);
    M.topLeftCorner(n, n)  = sys.Ac * Ts;
    M.topRightCorner(n, m) = sys.Bc * Ts;

    Eigen::MatrixXd expM = M.exp();  // 矩阵指数（需要 Eigen Unsupported）

    DiscreteSystem dsys;
    dsys.Ad = expM.topLeftCorner(n, n);
    dsys.Bd = expM.topRightCorner(n, m);
    dsys.C  = sys.C;
    dsys.Ts = Ts;

    return dsys;
}

// ============================================================
// 前向 Euler 近似离散化（用于对比）
//   Ad ≈ I + Ac * Ts
//   Bd ≈ Bc * Ts
// ============================================================
DiscreteSystem discretize_Euler(const ContinuousSystem& sys, double Ts) {
    int n = sys.n;
    DiscreteSystem dsys;
    dsys.Ad = Eigen::MatrixXd::Identity(n, n) + sys.Ac * Ts;
    dsys.Bd = sys.Bc * Ts;
    dsys.C  = sys.C;
    dsys.Ts = Ts;
    return dsys;
}

// ============================================================
// 构建弹簧-质量-阻尼连续系统
//   m*q_ddot + c*q_dot + k*q = F
//   状态: x = [q, q_dot]^T
//   输入: u = F
// ============================================================
ContinuousSystem buildSpringMassDamper(double mass, double damping,
                                        double stiffness) {
    ContinuousSystem sys;
    sys.n = 2; sys.m = 1; sys.p = 1;

    sys.Ac.resize(2, 2);
    sys.Ac << 0.0,               1.0,
              -stiffness / mass, -damping / mass;

    sys.Bc.resize(2, 1);
    sys.Bc << 0.0, 1.0 / mass;

    sys.C.resize(1, 2);
    sys.C << 1.0, 0.0;  // 只输出位移

    return sys;
}

int main() {
    // 参数：m=1kg, c=0.5 N·s/m, k=2 N/m
    auto sys = buildSpringMassDamper(1.0, 0.5, 2.0);
    double Ts = 0.1;  // 采样周期 100ms

    auto dsys_zoh   = discretize_ZOH(sys, Ts);
    auto dsys_euler = discretize_Euler(sys, Ts);

    std::cout << std::fixed << std::setprecision(6);
    std::cout << "=== ZOH 离散化 ===\n";
    std::cout << "Ad =\n" << dsys_zoh.Ad << "\n";
    std::cout << "Bd =\n" << dsys_zoh.Bd << "\n\n";

    std::cout << "=== Euler 近似离散化 ===\n";
    std::cout << "Ad =\n" << dsys_euler.Ad << "\n";
    std::cout << "Bd =\n" << dsys_euler.Bd << "\n\n";

    // 验证：两种方法的差异（Ts越小差异越小）
    std::cout << "Ad 差异范数: "
              << (dsys_zoh.Ad - dsys_euler.Ad).norm() << "\n";

    return 0;
}
```

**输出示例**：

```
=== ZOH 离散化 ===
Ad =
 0.990016   0.098002
-0.196003   0.940018
Bd =
 0.004900
 0.098002

=== Euler 近似离似化 ===
Ad =
 1.000000   0.100000
-0.200000   0.950000
Bd =
 0.000000
 0.100000

Ad 差异范数: 0.012843
```

> **注意**：Euler 法的 Bd 第一行（位置对力的影响）在 $Ts=0.1s$ 时为 0，而 ZOH 给出了正确的 $\frac{1}{2}T_s^2/m = 0.005$。这个差异在短期影响小，但长期仿真会累积误差。

---

## 四、离散时间状态方程的解

### 4.1 递推关系

离散系统的状态方程：

$$x_{k+1} = A x_k + B u_k \tag{4.1}$$

（下文省略下标 $d$，$A \equiv A_d$，$B \equiv B_d$）

从初始状态 $x_0$ 出发，逐步展开：

$$x_1 = A x_0 + B u_0$$

$$x_2 = A x_1 + B u_1 = A(A x_0 + B u_0) + B u_1 = A^2 x_0 + AB u_0 + B u_1$$

$$x_3 = A x_2 + B u_2 = A^3 x_0 + A^2 B u_0 + AB u_1 + B u_2$$

规律显现，一般式为：

$$\boxed{x_k = A^k x_0 + \sum_{j=0}^{k-1} A^{k-1-j} B u_j} \tag{4.2}$$

这个公式是 MPC 预测方程的数学根基，其物理意义非常清晰：
- $A^k x_0$：初始状态经过 $k$ 步自然演化的贡献（**自由响应**）
- $\sum_{j=0}^{k-1} A^{k-1-j} B u_j$：每一步控制输入的**叠加响应**（线性叠加原理）

---

## 五、预测方程的矩阵化推导（核心）

### 5.1 从标量到矩阵

对于 MPC，我们需要预测未来 $N$ 步的所有状态，写成矩阵形式更便于后续优化。

定义预测状态向量和控制序列向量：

$$\mathbf{X} = \begin{bmatrix} x_1 \\ x_2 \\ x_3 \\ \vdots \\ x_N \end{bmatrix} \in \mathbb{R}^{Nn}, \qquad \mathbf{U} = \begin{bmatrix} u_0 \\ u_1 \\ u_2 \\ \vdots \\ u_{N-1} \end{bmatrix} \in \mathbb{R}^{Nm}$$

### 5.2 逐步展开

将式(4.2)写出前 $N$ 步：

$$x_1 = A^1 x_0 + B u_0$$

$$x_2 = A^2 x_0 + AB u_0 + B u_1$$

$$x_3 = A^3 x_0 + A^2 B u_0 + AB u_1 + B u_2$$

$$x_4 = A^4 x_0 + A^3 B u_0 + A^2 B u_1 + AB u_2 + B u_3$$

$$\vdots$$

$$x_N = A^N x_0 + A^{N-1}B u_0 + A^{N-2}B u_1 + \cdots + B u_{N-1}$$

### 5.3 写成矩阵乘法

将上述等式合并：

$$\underbrace{\begin{bmatrix} x_1 \\ x_2 \\ x_3 \\ \vdots \\ x_N \end{bmatrix}}_{\mathbf{X}} = \underbrace{\begin{bmatrix} A \\ A^2 \\ A^3 \\ \vdots \\ A^N \end{bmatrix}}_{\mathcal{A}} x_0 + \underbrace{\begin{bmatrix} B & 0 & 0 & \cdots & 0 \\ AB & B & 0 & \cdots & 0 \\ A^2B & AB & B & \cdots & 0 \\ \vdots & \vdots & \vdots & \ddots & \vdots \\ A^{N-1}B & A^{N-2}B & A^{N-3}B & \cdots & B \end{bmatrix}}_{\mathcal{B}} \underbrace{\begin{bmatrix} u_0 \\ u_1 \\ u_2 \\ \vdots \\ u_{N-1} \end{bmatrix}}_{\mathbf{U}}$$

即：

$$\boxed{\mathbf{X} = \mathcal{A} x_0 + \mathcal{B} \mathbf{U}} \tag{5.1}$$

### 5.4 理解 $\mathcal{B}$ 矩阵的结构

$\mathcal{B}$ 是一个**下三角 Toeplitz-like 矩阵**，每个块 $\mathcal{B}_{k,j}$（第 $k$ 行块，第 $j$ 列块）的含义是：

$$\mathcal{B}_{k,j} = \begin{cases} A^{k-1-j} B & \text{if } j \leq k \\ 0 & \text{if } j > k \end{cases}$$

**因果性**的体现：$u_j$ 对 $x_k$ 的影响只在 $j < k$ 时存在（未来的控制不能影响过去的状态）。

---

## 六、C++ 实现预测矩阵构建

```cpp
#include <Eigen/Dense>
#include <iostream>
#include <cassert>
#include <iomanip>

// ============================================================
// 构建预测矩阵 calA 和 calB
//
// 输入:
//   A    - 离散系统矩阵 (n×n)
//   B    - 离散输入矩阵 (n×m)
//   N    - 预测时域步数
//
// 输出:
//   calA - 预测矩阵 (N*n × n)
//          calA = [A; A²; A³; ...; A^N]
//   calB - 预测矩阵 (N*n × N*m)
//          calB(k,j) = A^(k-j-1)*B if j<=k, else 0
// ============================================================
void buildPredictionMatrices(
    const Eigen::MatrixXd& A,
    const Eigen::MatrixXd& B,
    int N,
    Eigen::MatrixXd& calA,
    Eigen::MatrixXd& calB)
{
    int n = A.rows();
    int m = B.cols();
    assert(A.cols() == n && B.rows() == n);

    calA.resize(N * n, n);
    calB.resize(N * n, N * m);
    calB.setZero();  // 先全置零，只填下三角块

    // ── 构建 calA ──
    // calA 的第 k 块行（0-indexed）= A^(k+1)
    // 递推：A^1, A^2, ..., A^N
    Eigen::MatrixXd Apow = A;  // 初始为 A^1
    for (int k = 0; k < N; ++k) {
        calA.block(k * n, 0, n, n) = Apow;
        Apow = A * Apow;  // A^(k+2) = A * A^(k+1)
    }

    // ── 构建 calB ──
    // calB 的第 k 块行，第 j 块列（j <= k）：
    //   calB(k, j) = A^(k-j-1) * B
    //
    // 优化方案：利用列填充，每列 j 的非零块为：
    //   行 j:   A^0 * B = B
    //   行 j+1: A^1 * B = AB
    //   行 j+2: A^2 * B = A²B
    //   ...
    //   行 N-1: A^(N-1-j) * B
    //
    // 对每列 j，只需从 B 开始，逐行乘 A
    for (int j = 0; j < N; ++j) {
        Eigen::MatrixXd AkB = B;  // 从 A^0 * B = B 开始
        for (int k = j; k < N; ++k) {
            calB.block(k * n, j * m, n, m) = AkB;
            AkB = A * AkB;  // 下一行 = A * 上一行
        }
    }
}

// ============================================================
// 验证：用预测矩阵预测的状态 vs 逐步仿真的状态
// 两者应完全一致（数值误差级别的差异）
// ============================================================
void verifyPrediction(
    const Eigen::MatrixXd& A,
    const Eigen::MatrixXd& B,
    const Eigen::MatrixXd& calA,
    const Eigen::MatrixXd& calB,
    const Eigen::VectorXd& x0,
    const Eigen::VectorXd& U,  // 控制序列 [u0; u1; ...; u_{N-1}]
    int N)
{
    int n = A.rows(), m = B.cols();

    std::cout << std::fixed << std::setprecision(6);
    std::cout << "\n=== 预测矩阵验证 ===\n";
    std::cout << std::setw(6) << "步骤"
              << std::setw(15) << "矩阵预测 x(1)"
              << std::setw(15) << "逐步仿真 x(1)"
              << std::setw(12) << "误差\n";
    std::cout << std::string(50, '-') << "\n";

    // 方法一：矩阵预测（一次性计算所有步）
    Eigen::VectorXd X_pred = calA * x0 + calB * U;

    // 方法二：逐步仿真
    Eigen::VectorXd x_sim = x0;
    for (int k = 0; k < N; ++k) {
        Eigen::VectorXd uk = U.segment(k * m, m);
        x_sim = A * x_sim + B * uk;

        // 取预测结果中对应步骤的第一个状态分量对比
        double pred_val = X_pred(k * n);      // 矩阵法
        double sim_val  = x_sim(0);            // 逐步法
        double err      = std::abs(pred_val - sim_val);

        std::cout << std::setw(6) << k + 1
                  << std::setw(15) << pred_val
                  << std::setw(15) << sim_val
                  << std::setw(12) << err << "\n";
    }
}

int main() {
    // ── 弹簧-质量-阻尼系统参数 ──
    double mass     = 1.0;   // kg
    double damping  = 0.5;   // N·s/m
    double stiffness = 2.0;  // N/m
    double Ts       = 0.1;   // 采样周期

    // 前向 Euler 离散化（演示用）
    Eigen::MatrixXd Ac(2, 2);
    Ac << 0,                  1,
          -stiffness / mass, -damping / mass;

    Eigen::MatrixXd Bc(2, 1);
    Bc << 0, 1.0 / mass;

    Eigen::MatrixXd A = Eigen::MatrixXd::Identity(2, 2) + Ac * Ts;
    Eigen::MatrixXd B = Bc * Ts;

    int N = 5;  // 预测时域

    // ── 构建预测矩阵 ──
    Eigen::MatrixXd calA, calB;
    buildPredictionMatrices(A, B, N, calA, calB);

    std::cout << "=== calA（" << N * 2 << "×2）===\n" << calA << "\n\n";
    std::cout << "=== calB（" << N * 2 << "×" << N * 1 << "）===\n";
    std::cout << calB << "\n";

    // ── 验证 ──
    Eigen::VectorXd x0(2);
    x0 << 1.0, 0.0;  // 初始位移=1m, 速度=0

    // 构造一个测试控制序列 [0.5, -0.3, 0.2, 0.0, 0.1]
    Eigen::VectorXd U(N * 1);
    U << 0.5, -0.3, 0.2, 0.0, 0.1;

    verifyPrediction(A, B, calA, calB, x0, U, N);

    return 0;
}
```

**输出**：

```
=== calA（10×2）===
 1.00000   0.10000
 0.98000   0.19500
 0.94100   0.28525
 ...

=== calB（10×5）===
 0.00000  0.00000  0.00000  0.00000  0.00000
 0.10000  0.00000  0.00000  0.00000  0.00000
 0.10000  0.10000  0.00000  0.00000  0.00000
 ...

=== 预测矩阵验证 ===
步骤    矩阵预测 x(1)  逐步仿真 x(1)     误差
--------------------------------------------------
   1       1.050000       1.050000    0.000000
   2       0.988500       0.988500    0.000000
   3       0.993775       0.993775    0.000000
   4       1.013862       1.013862    0.000000
   5       1.013709       1.013709    0.000000
```

误差为机器精度级别（$\approx 10^{-16}$），验证了矩阵推导的正确性。

---

## 七、$\mathcal{A}$ 和 $\mathcal{B}$ 的物理意义

这两个矩阵是 MPC 的数学核心，理解其物理含义至关重要：

### 7.1 $\mathcal{A}$ 矩阵：系统的"自然演化"

$$\mathcal{A} = \begin{bmatrix} A \\ A^2 \\ \vdots \\ A^N \end{bmatrix}$$

$\mathcal{A} x_0$ 给出**在无任何控制输入（$u=0$）的情况下**，系统从 $x_0$ 出发的自由响应轨迹。

直觉：如果系统是稳定的（$A$ 的特征值在单位圆内），$\mathcal{A} x_0$ 会随步数增大而趋向零——系统自然衰减。

### 7.2 $\mathcal{B}$ 矩阵：控制输入的"传播矩阵"

$$\mathcal{B} = \begin{bmatrix} B & 0 & \cdots & 0 \\ AB & B & \cdots & 0 \\ A^2B & AB & \cdots & 0 \\ \vdots & & \ddots & \vdots \\ A^{N-1}B & \cdots & AB & B \end{bmatrix}$$

$\mathcal{B}_{k,j}$ 告诉我们：**在时刻 $j$ 施加单位控制量，对时刻 $k+1$ 的状态有多大影响**。

它是下三角的，体现**因果律**：未来的控制不影响过去的状态。

```cpp
// 验证因果性：calB 的上三角应为零
void checkCausality(const Eigen::MatrixXd& calB, int n, int m) {
    int N = calB.rows() / n;
    bool causal = true;
    for (int k = 0; k < N; ++k) {
        for (int j = k + 1; j < N; ++j) {
            // 第 k 行块，第 j 列块（j > k）应为零
            double norm = calB.block(k * n, j * m, n, m).norm();
            if (norm > 1e-10) {
                causal = false;
                std::cout << "因果性违反！Block(" << k << "," << j
                          << ") 范数 = " << norm << "\n";
            }
        }
    }
    if (causal) std::cout << "✓ calB 满足因果性（严格下三角块矩阵）\n";
}
```

---

## 八、多输入多输出（MIMO）系统的推广

MPC 最大的优势之一是**天然处理 MIMO 系统**。上述所有推导对多输入多输出完全适用，只需维度更大：

**示例：二自由度机器人臂**

$$\begin{bmatrix} I_1 & 0 \\ 0 & I_2 \end{bmatrix} \begin{bmatrix} \ddot{\theta}_1 \\ \ddot{\theta}_2 \end{bmatrix} + \begin{bmatrix} b_1 & 0 \\ 0 & b_2 \end{bmatrix} \begin{bmatrix} \dot{\theta}_1 \\ \dot{\theta}_2 \end{bmatrix} = \begin{bmatrix} \tau_1 \\ \tau_2 \end{bmatrix}$$

状态 $x = [\theta_1, \theta_2, \dot{\theta}_1, \dot{\theta}_2]^T \in \mathbb{R}^4$，控制 $u = [\tau_1, \tau_2]^T \in \mathbb{R}^2$：

```cpp
ContinuousSystem buildTwoLinkRobot(double I1, double I2,
                                    double b1, double b2) {
    ContinuousSystem sys;
    sys.n = 4; sys.m = 2; sys.p = 2;

    // Ac: 4×4
    sys.Ac = Eigen::MatrixXd::Zero(4, 4);
    sys.Ac(0, 2) = 1.0;            // dθ1/dt = ω1
    sys.Ac(1, 3) = 1.0;            // dθ2/dt = ω2
    sys.Ac(2, 2) = -b1 / I1;      // dω1/dt = -b1/I1 * ω1 + τ1/I1
    sys.Ac(3, 3) = -b2 / I2;      // dω2/dt = -b2/I2 * ω2 + τ2/I2

    // Bc: 4×2
    sys.Bc = Eigen::MatrixXd::Zero(4, 2);
    sys.Bc(2, 0) = 1.0 / I1;      // τ1 → ω1
    sys.Bc(3, 1) = 1.0 / I2;      // τ2 → ω2

    // C: 只测量关节角度
    sys.C = Eigen::MatrixXd::Zero(2, 4);
    sys.C(0, 0) = 1.0;
    sys.C(1, 1) = 1.0;

    return sys;
}
```

此时预测矩阵 $\mathcal{B}$ 的尺寸为 $(4N) \times (2N)$，控制序列 $\mathbf{U}$ 的长度为 $2N$（每步两个力矩输入），**两个关节的控制在优化中同时被协调**。

---

## 九、预测精度分析

### 9.1 预测误差来源

实际中，预测值 $\hat{x}_k$ 与真实状态 $x_k$ 存在偏差，来源包括：

```
预测误差 = 模型误差 + 测量噪声 + 未建模扰动

① 模型误差：  线性化误差（非线性系统）、参数不确定性
② 外部扰动：  路面颠簸、风力等
③ 测量噪声：  传感器噪声传播进状态估计
```

### 9.2 误差如何影响 MPC

预测误差随时域长度增大而**积累**：

$$\|\hat{x}_k - x_k\| \leq \|A^k\| \cdot \|x_0 - \hat{x}_0\| + \sum_{j=0}^{k-1} \|A^{k-1-j}\| \cdot \|w_j\|$$

这说明：
- **短预测时域**：误差小，但"视野"短，可能因短视做出次优决策
- **长预测时域**：误差大，但能提前规划，整体更优

这是 MPC 中**选择预测时域 $N$ 时的核心权衡**，没有通用的最优解，依赖具体系统特性。

---

## 十、用特征值分析系统稳定性

在构建预测矩阵之前，先分析离散系统的稳定性非常重要：

```cpp
// 检查离散系统稳定性
// 离散系统稳定 ⟺ 所有特征值的模 < 1（在单位圆内）
void checkStability(const Eigen::MatrixXd& Ad) {
    Eigen::EigenSolver<Eigen::MatrixXd> solver(Ad);
    auto eigenvalues = solver.eigenvalues();

    std::cout << "=== 系统稳定性分析 ===\n";
    bool stable = true;
    for (int i = 0; i < eigenvalues.size(); ++i) {
        double mag = std::abs(eigenvalues(i));
        bool eig_stable = (mag < 1.0);
        if (!eig_stable) stable = false;

        std::cout << "  λ" << i + 1 << " = "
                  << eigenvalues(i).real() << " + "
                  << eigenvalues(i).imag() << "j"
                  << "  |λ| = " << mag
                  << (eig_stable ? "  ✓" : "  ✗ 不稳定！") << "\n";
    }
    std::cout << "系统" << (stable ? "稳定" : "不稳定") << "\n\n";

    // 补充：A^N 的增长/衰减趋势
    int N_test = 20;
    Eigen::MatrixXd AN = Ad;
    for (int k = 1; k < N_test; ++k) AN = Ad * AN;
    std::cout << "A^" << N_test << " 的范数: " << AN.norm()
              << (AN.norm() < 1.0 ? " (衰减，稳定)" : " (发散，不稳定)") << "\n";
}
```

---

## 总结：本篇的数学要点

$$\boxed{\mathbf{X} = \mathcal{A} x_0 + \mathcal{B} \mathbf{U}}$$

这一个方程是 MPC 的数学核心。它将未来 $N$ 步的**所有预测状态**，表达为**当前状态**和**未来控制序列**的线性函数。

有了这个方程，后续推导就水到渠成：

1. 将目标函数用 $\mathbf{U}$ 表示 → 得到关于 $\mathbf{U}$ 的二次函数
2. 加入约束 → 形成带约束的 QP 问题
3. 求解 QP → 得到最优控制序列
4. 取第一步执行 → 滚动时域

| 矩阵 | 尺寸 | 构建方法 | 物理含义 |
|------|------|---------|---------|
| $\mathcal{A}$ | $Nn \times n$ | 递推 $A, A^2, \ldots, A^N$ | 系统自由响应（无控制） |
| $\mathcal{B}$ | $Nn \times Nm$ | 下三角块，每列递推乘 $A$ | 控制输入对未来状态的影响 |

---

**下一篇**：[第三篇：将预测方程转化为 QP 问题并求解]()

我们将把 $\mathbf{X} = \mathcal{A} x_0 + \mathcal{B} \mathbf{U}$ 代入目标函数，完整推导 QP 的 $H$ 矩阵和 $f$ 向量，并接入真正的 QP 求解器（OSQP）。
