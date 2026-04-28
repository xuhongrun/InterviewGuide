# Eigen C++ 线性代数库（七）：unsupported 模块与非线性优化

> **系列导航**
> - 第一篇：入门与基本类型
> - 第二篇：矩阵与向量操作详解
> - 第三篇：线性方程组求解与矩阵分解
> - 第四篇：特征值分解、SVD 与几何变换
> - 第五篇：稀疏矩阵、性能优化与工程实战
> - 第六篇：ROS / SLAM 生态互操作
> - **第七篇：unsupported 模块与非线性优化** ← 当前

---

## 1. 什么是 `unsupported/`？

Eigen 源码中除了核心模块 `Eigen/`，还有一个 `unsupported/Eigen/` 目录。这里放的是**功能完整但 API 还可能演进**的模块——很多其实已经稳定使用多年。

| 模块 | 用途 |
|---|---|
| `unsupported/Eigen/AutoDiff` | 前向模式自动微分 |
| `unsupported/Eigen/NumericalDiff` | 数值微分 |
| `unsupported/Eigen/NonLinearOptimization` | Levenberg-Marquardt 非线性最小二乘 |
| `unsupported/Eigen/Polynomials` | 多项式求根 |
| `unsupported/Eigen/MatrixFunctions` | 矩阵指数 / 对数 / 平方根 |
| `unsupported/Eigen/KroneckerProduct` | Kronecker 积 |
| `unsupported/Eigen/CXX11/Tensor` | N 维张量（TensorFlow 早期内核） |
| `unsupported/Eigen/Splines` | B 样条插值 |
| `unsupported/Eigen/FFT` | 快速傅里叶变换 |
| `unsupported/Eigen/IterativeSolvers` | GMRES、MINRES 等迭代求解器 |

> 命名「unsupported」≠ 不可用。Ceres、g2o 内部都使用了这些模块。
> 真正的含义是：**Eigen 团队不保证这些 API 跨版本稳定**。

---

## 2. 矩阵函数（MatrixFunctions）

```cpp
#include <unsupported/Eigen/MatrixFunctions>

Eigen::Matrix3d A;
A << 0, -1, 0,
     1,  0, 0,
     0,  0, 1;

Eigen::Matrix3d expA  = A.exp();      // 矩阵指数 e^A
Eigen::Matrix3d logA  = A.log();      // 矩阵对数（要求可对角化）
Eigen::Matrix3d sqrtA = A.sqrt();     // 矩阵平方根
Eigen::Matrix3d sinA  = A.sin();
Eigen::Matrix3d cosA  = A.cos();

// 任意矩阵幂（包括分数次幂）
Eigen::Matrix3d A_pow = A.pow(0.5);   // 等价 sqrt
```

**典型应用**：连续时间状态空间模型的离散化。

```cpp
// 连续模型: dx/dt = A x + B u
// 离散化（零阶保持）：x[k+1] = Ad x[k] + Bd u[k]
//   Ad = exp(A * dt)
//   Bd = A^-1 (Ad - I) B   （A 可逆时）
double dt = 0.01;
Eigen::Matrix4d Ac = /* ... */;
Eigen::Matrix4d Ad = (Ac * dt).exp();
```

---

## 3. 多项式求根（Polynomials）

```cpp
#include <unsupported/Eigen/Polynomials>

// 求 x^3 - 6x^2 + 11x - 6 = 0 的根（应为 1, 2, 3）
Eigen::VectorXd coeffs(4);
coeffs << -6, 11, -6, 1;       // 注意：低次项在前

Eigen::PolynomialSolver<double, Eigen::Dynamic> solver;
solver.compute(coeffs);

const auto& roots = solver.roots();   // 复数根
for (int i = 0; i < roots.size(); ++i) {
    std::cout << roots[i] << "\n";
}

// 仅取实根
std::vector<double> real_roots;
const double tol = 1e-8;
solver.realRoots(real_roots, tol);
```

> 内部实现是构造伴随矩阵后做特征值分解，复杂度 $O(n^3)$。
> 阶数 ≤ 30 时性能完全够用；更高阶建议用专门的多项式求根算法。

---

## 4. AutoDiff：前向模式自动微分

写一次代码，**同时**得到函数值和雅可比，没有近似误差。

### 4.1 标量函数求导

```cpp
#include <unsupported/Eigen/AutoDiff>

using ADScalar = Eigen::AutoDiffScalar<Eigen::VectorXd>;

// f(x, y) = x^2 * y + sin(x)
// 期望：∂f/∂x = 2xy + cos(x)，∂f/∂y = x^2
auto f = [](const ADScalar& x, const ADScalar& y) {
    return x * x * y + sin(x);
};

ADScalar x(2.0, 2, 0);        // 值=2，2 个变量，自己是第 0 个
ADScalar y(3.0, 2, 1);        // 值=3，2 个变量，自己是第 1 个

ADScalar result = f(x, y);
std::cout << "f       = " << result.value()          << "\n";
std::cout << "df/dx   = " << result.derivatives()[0] << "\n";
std::cout << "df/dy   = " << result.derivatives()[1] << "\n";
// 输出: f = 12.909, df/dx = 11.584, df/dy = 4
```

### 4.2 向量函数的雅可比

```cpp
// f: R^2 -> R^2
// f(x) = [x[0]^2 + x[1], 3*x[0] - x[1]^2]
// 期望雅可比 J = [[2x0, 1], [3, -2x1]]

template <typename T>
Eigen::Matrix<T, 2, 1> f(const Eigen::Matrix<T, 2, 1>& x) {
    Eigen::Matrix<T, 2, 1> y;
    y[0] = x[0] * x[0] + x[1];
    y[1] = T(3) * x[0] - x[1] * x[1];
    return y;
}

using ADVec2 = Eigen::Matrix<ADScalar, 2, 1>;

ADVec2 x_ad;
x_ad[0] = ADScalar(1.0, 2, 0);
x_ad[1] = ADScalar(2.0, 2, 1);

ADVec2 y_ad = f(x_ad);

Eigen::Vector2d val(y_ad[0].value(), y_ad[1].value());
Eigen::Matrix2d J;
J.row(0) = y_ad[0].derivatives().transpose();
J.row(1) = y_ad[1].derivatives().transpose();

std::cout << "J =\n" << J << "\n";
// J = 2 1
//     3 -4
```

> 要求：函数体里的所有运算都必须是模板/重载过的（`T x*x`、`sin(x)` 等）。
> 这正是 Ceres 的代价函数普遍写成 `template <typename T>` 的原因——同一份代码既能算数值也能算雅可比。

### 4.3 何时用 AutoDiff vs Ceres？

| 场景 | 推荐 |
|---|---|
| 单次 / 一次性导数计算 | Eigen `AutoDiffScalar` |
| 复杂目标函数的非线性最小二乘 | **Ceres**（内部也是 AutoDiff） |
| 需要二阶导（Hessian） | 套两层 AutoDiff，或用 Ceres |
| 极端追求性能、变量数极多 | 反向模式 AD（CppAD、autodiff 库） |

> Eigen `AutoDiffScalar` 是**前向模式**，复杂度与变量数成正比。
> 变量 > 几十个时反向模式更优——但写起来复杂得多，工程上直接 Ceres 即可。

---

## 5. NumericalDiff：数值微分

无法显式写出导数（如调用了黑盒物理引擎）时，用有限差分近似：

```cpp
#include <unsupported/Eigen/NumericalDiff>

// 仿函数（functor）：定义输入维 / 输出维 / 计算 operator()
struct MyFunctor {
    using Scalar    = double;
    enum { InputsAtCompileTime = 2, ValuesAtCompileTime = 3 };
    using InputType    = Eigen::Vector2d;
    using ValueType    = Eigen::Vector3d;
    using JacobianType = Eigen::Matrix<double, 3, 2>;

    int inputs() const { return 2; }
    int values() const { return 3; }

    int operator()(const Eigen::Vector2d& x, Eigen::Vector3d& y) const {
        y << x[0] * x[0],
             x[0] * x[1],
             x[1] * x[1] + 2;
        return 0;
    }
};

MyFunctor f;
Eigen::NumericalDiff<MyFunctor> num_diff(f);

Eigen::Vector2d x(1.0, 2.0);
Eigen::Matrix<double, 3, 2> J;
num_diff.df(x, J);

std::cout << "Numerical Jacobian:\n" << J << "\n";
// 期望: [[2, 0], [2, 1], [0, 4]]
```

> 默认用中心差分，精度 ~1e-7（double）。
> 缺点：需要 $2n$ 次函数求值；对噪声函数不稳定。能用 AutoDiff 就别用数值微分。

---

## 6. Levenberg-Marquardt 非线性最小二乘

完整解决 $\min_x \sum_i \|r_i(x)\|^2$。

### 6.1 经典曲线拟合

拟合 $y = a \cdot e^{b x}$ 中的参数 $(a, b)$：

```cpp
#include <unsupported/Eigen/NonLinearOptimization>
#include <unsupported/Eigen/NumericalDiff>
#include <iostream>
#include <random>

// 残差仿函数：r_i(x) = y_i - a * exp(b * t_i)
struct ExpFitFunctor {
    using Scalar    = double;
    enum { InputsAtCompileTime = 2, ValuesAtCompileTime = Eigen::Dynamic };
    using InputType    = Eigen::VectorXd;
    using ValueType    = Eigen::VectorXd;
    using JacobianType = Eigen::MatrixXd;

    Eigen::VectorXd t_, y_;
    ExpFitFunctor(const Eigen::VectorXd& t, const Eigen::VectorXd& y)
        : t_(t), y_(y) {}

    int inputs() const { return 2; }
    int values() const { return static_cast<int>(t_.size()); }

    int operator()(const Eigen::VectorXd& x, Eigen::VectorXd& fvec) const {
        const double a = x[0], b = x[1];
        for (int i = 0; i < t_.size(); ++i) {
            fvec[i] = y_[i] - a * std::exp(b * t_[i]);
        }
        return 0;
    }
};

int main() {
    // 1. 生成带噪声的样本
    const int N = 50;
    Eigen::VectorXd t = Eigen::VectorXd::LinSpaced(N, 0.0, 2.0);
    Eigen::VectorXd y(N);
    std::mt19937 rng(42);
    std::normal_distribution<double> noise(0.0, 0.05);
    const double a_true = 2.0, b_true = 0.8;
    for (int i = 0; i < N; ++i) {
        y[i] = a_true * std::exp(b_true * t[i]) + noise(rng);
    }

    // 2. 初值
    Eigen::VectorXd x(2);
    x << 1.0, 1.0;

    // 3. 用 NumericalDiff 包装 functor，再交给 LM
    ExpFitFunctor functor(t, y);
    Eigen::NumericalDiff<ExpFitFunctor> num_diff(functor);
    Eigen::LevenbergMarquardt<Eigen::NumericalDiff<ExpFitFunctor>> lm(num_diff);

    // 4. 求解
    lm.parameters.maxfev = 200;       // 最大函数求值次数
    lm.parameters.xtol   = 1e-10;
    int info = lm.minimize(x);

    std::cout << "Status:    " << info << " (1=收敛)\n"
              << "Iterations: " << lm.iter << "\n"
              << "a = " << x[0] << "  (true 2.0)\n"
              << "b = " << x[1] << "  (true 0.8)\n";
}
```

### 6.2 用 AutoDiff 替代 NumericalDiff（更快更准）

```cpp
struct ExpFitADFunctor {
    using Scalar    = double;
    enum { InputsAtCompileTime = 2, ValuesAtCompileTime = Eigen::Dynamic };
    using InputType    = Eigen::VectorXd;
    using ValueType    = Eigen::VectorXd;
    using JacobianType = Eigen::MatrixXd;

    Eigen::VectorXd t_, y_;
    int inputs() const { return 2; }
    int values() const { return static_cast<int>(t_.size()); }

    // 模板版本：让 AutoDiff 介入
    template <typename T>
    int operator()(const Eigen::Matrix<T, Eigen::Dynamic, 1>& x,
                   Eigen::Matrix<T, Eigen::Dynamic, 1>& fvec) const {
        for (int i = 0; i < t_.size(); ++i) {
            fvec[i] = T(y_[i]) - x[0] * exp(x[1] * T(t_[i]));
        }
        return 0;
    }

    // 非模板重载（LM 内部需要）
    int operator()(const Eigen::VectorXd& x, Eigen::VectorXd& fvec) const {
        return operator()<double>(x, fvec);
    }

    // 提供雅可比（用 AutoDiff 算）
    int df(const Eigen::VectorXd& x, Eigen::MatrixXd& fjac) const {
        using AD = Eigen::AutoDiffScalar<Eigen::Vector2d>;
        Eigen::Matrix<AD, Eigen::Dynamic, 1> x_ad(2), f_ad(t_.size());
        x_ad[0] = AD(x[0], 2, 0);
        x_ad[1] = AD(x[1], 2, 1);
        operator()<AD>(x_ad, f_ad);
        for (int i = 0; i < t_.size(); ++i)
            fjac.row(i) = f_ad[i].derivatives().transpose();
        return 0;
    }
};

// 使用时直接：
Eigen::LevenbergMarquardt<ExpFitADFunctor> lm(functor);
```

### 6.3 何时用 Eigen LM，何时上 Ceres？

| 维度 | Eigen LM | Ceres |
|---|---|---|
| 依赖 | 仅 Eigen | 大（含 glog, gflags） |
| 编写复杂度 | 模板 functor，略繁琐 | 仿函数 + AutoDiff，简单 |
| 鲁棒核函数（Huber/Cauchy） | 需自己加 | 内置 |
| 稀疏 Jacobian、Schur 补 | 不支持 | ✅ 完整支持 |
| 流形优化（SO3/SE3） | 需自己写 | ✅ Manifold 接口 |
| 小问题（< 1k 残差，< 50 参数） | 完全够用 | overkill |
| BA / SLAM 后端 | 不要用 | ✅ |

> 经验法则：依赖洁癖且问题小时用 Eigen LM；任何中大型 NLLS 问题直接 Ceres。

---

## 7. KroneckerProduct

线性矩阵方程 $AXB = C$ 可以通过 Kronecker 积转成普通线性方程：
$(B^T \otimes A) \, \text{vec}(X) = \text{vec}(C)$。

```cpp
#include <unsupported/Eigen/KroneckerProduct>

Eigen::Matrix2d A; A << 1, 2, 3, 4;
Eigen::Matrix3d B = Eigen::Matrix3d::Identity();

// A ⊗ B 是 6x6 矩阵
Eigen::Matrix<double, 6, 6> AB = Eigen::kroneckerProduct(A, B);

// 稀疏版本也存在：kroneckerProduct(SparseA, SparseB)
```

应用：李雅普诺夫方程 $A^T P + P A = -Q$、Sylvester 方程的求解。

---

## 8. Splines：B 样条插值

```cpp
#include <unsupported/Eigen/Splines>

// 拟合一条二维曲线（3 阶 B 样条）
Eigen::MatrixXd points(2, 5);
points << 0, 1, 2, 3, 4,
          0, 1, 0, 1, 0;

using Spline2d = Eigen::Spline<double, 2>;
Spline2d spline =
    Eigen::SplineFitting<Spline2d>::Interpolate(points, /*degree=*/3);

// 在参数 u ∈ [0, 1] 上采样
for (double u = 0; u <= 1.0; u += 0.1) {
    Eigen::Vector2d p = spline(u);
    std::cout << u << " -> (" << p.x() << ", " << p.y() << ")\n";
}

// 求一阶导数（曲线切向量）
Eigen::Vector2d dp = spline.derivatives(0.5, 1).col(1);
```

应用：轨迹规划、参考线生成、IMU 时间对齐。

---

## 9. FFT

```cpp
#include <unsupported/Eigen/FFT>
#include <complex>

Eigen::FFT<double> fft;

std::vector<double> input(8);
for (int i = 0; i < 8; ++i) input[i] = std::cos(2 * M_PI * i / 8);

std::vector<std::complex<double>> spectrum;
fft.fwd(spectrum, input);    // 正向 FFT

std::vector<double> recon;
fft.inv(recon, spectrum);    // 逆向 FFT

// 也支持 Eigen 向量直接 FFT
Eigen::VectorXcd freq;
Eigen::VectorXd  time = Eigen::VectorXd::Random(64);
fft.fwd(freq, time);
```

> 默认实现是 KissFFT（纯 C，性能一般）。生产环境通常切换到 FFTW：
> `#define EIGEN_FFTW_DEFAULT` + 链接 `-lfftw3`。

---

## 10. CXX11/Tensor：N 维张量

```cpp
#include <unsupported/Eigen/CXX11/Tensor>

// 构造 [3, 4, 5] 张量
Eigen::Tensor<float, 3> t(3, 4, 5);
t.setRandom();

// 索引（注意是逗号表达式）
float v = t(1, 2, 3);

// 形状变换
Eigen::array<int, 2> new_shape = {12, 5};
Eigen::Tensor<float, 2> flat = t.reshape(new_shape);

// 切片：从 (0,0,0) 起取 (3, 4, 1) 大小
Eigen::array<Eigen::Index, 3> offsets = {0, 0, 0};
Eigen::array<Eigen::Index, 3> extents = {3, 4, 1};
Eigen::Tensor<float, 3> slice = t.slice(offsets, extents);

// 张量收缩（广义矩阵乘法）
Eigen::Tensor<float, 2> A(3, 4); A.setRandom();
Eigen::Tensor<float, 2> B(4, 5); B.setRandom();
Eigen::array<Eigen::IndexPair<int>, 1> dims = {Eigen::IndexPair<int>(1, 0)};
Eigen::Tensor<float, 2> C = A.contract(B, dims);    // 等价 A * B

// 元素归约
Eigen::Tensor<float, 0> total = t.sum();
float total_v = total();
```

> Tensor 模块就是 TensorFlow 1.x CPU kernel 的内核。
> 对常规 2D 矩阵任务，仍然首选 `Matrix` —— Tensor 的 API 和编译时间都更重。

---

## 11. IterativeSolvers（unsupported 版本）

`Eigen/IterativeLinearSolvers` 已经包含 CG / BiCGSTAB / LSCG，但
`unsupported/Eigen/IterativeSolvers` 提供更多：

| 求解器 | 适用 |
|---|---|
| `GMRES` | 一般非对称稀疏矩阵 |
| `MINRES` | 对称（不一定正定）稀疏矩阵 |
| `DGMRES` | 带特征值压缩的 GMRES |
| `IDRS` | 适合非对称大规模问题 |

```cpp
#include <unsupported/Eigen/IterativeSolvers>

Eigen::SparseMatrix<double> A = /* ... */;
Eigen::VectorXd b = /* ... */;

Eigen::GMRES<Eigen::SparseMatrix<double>> solver;
solver.setTolerance(1e-8);
solver.setMaxIterations(500);
solver.compute(A);

Eigen::VectorXd x = solver.solve(b);
std::cout << "iterations: " << solver.iterations()
          << ", error: "    << solver.error() << "\n";
```

---

## 小结

| 模块 | 一句话用途 |
|---|---|
| `MatrixFunctions` | 矩阵 exp/log/sqrt（系统离散化、李代数指数映射） |
| `Polynomials` | 多项式求根（控制系统、轨迹规划） |
| `AutoDiff` | 前向自动微分（小规模一次性导数） |
| `NumericalDiff` | 数值差分（黑盒函数兜底） |
| `NonLinearOptimization` | LM 非线性最小二乘（小规模 NLLS） |
| `KroneckerProduct` | Kronecker 积（线性矩阵方程） |
| `Splines` | B 样条拟合（轨迹/参考线） |
| `FFT` | 快速傅里叶变换 |
| `CXX11/Tensor` | N 维张量（深度学习内核） |
| `IterativeSolvers` | GMRES / MINRES（大型稀疏方程） |

至此，Eigen 系列七篇全部完成。完整路线：
**入门 → 操作 → 求解 → 几何 → 稀疏与工程 → 生态互操作 → 非线性优化**。
