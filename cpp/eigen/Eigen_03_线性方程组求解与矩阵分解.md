# Eigen C++ 线性代数库（三）：线性方程组求解与矩阵分解

> **系列导航**
> - 第一篇：入门与基本类型
> - 第二篇：矩阵与向量操作详解
> - **第三篇：线性方程组求解与矩阵分解** ← 当前
> - 第四篇：特征值分解、SVD 与几何变换
> - 第五篇：稀疏矩阵、性能优化与工程实战
> - 第六篇：ROS / SLAM 生态互操作
> - 第七篇：unsupported 模块与非线性优化

---

## 1. 问题背景

线性方程组 $Ax = b$ 是科学计算中最基础、最核心的问题。它在工程领域无处不在：

- 有限元分析中的节点位移求解
- 计算机图形学中的光线追踪
- 机器人运动学的逆解
- 卡尔曼滤波中的协方差传播
- 机器学习中的最小二乘回归

Eigen 提供了多种分解方法，选择正确的方法能在**速度**与**数值稳定性**之间取得最佳平衡。

---

## 2. 方程类型与分解方法对照表

| 分解方法 | 适用矩阵条件 | 速度 | 数值稳定性 | 内存开销 |
|---|---|---|---|---|
| `PartialPivLU` | **方阵**，可逆 | ★★★★★ | ★★★ | 低 |
| `FullPivLU` | 方阵（可奇异），可判断秩 | ★★ | ★★★★★ | 低 |
| `LLT` | **对称正定（SPD）** | ★★★★★ | ★★ | 低 |
| `LDLT` | **对称半正定** | ★★★★ | ★★★★ | 低 |
| `HouseholderQR` | 任意矩阵 | ★★★★ | ★★★ | 低 |
| `ColPivHouseholderQR` | 任意矩阵，可判断秩 | ★★★ | ★★★★ | 低 |
| `FullPivHouseholderQR` | 任意矩阵，最精确 | ★★ | ★★★★★ | 低 |
| `JacobiSVD` | 任意矩阵，最小二乘 | ★ | ★★★★★ | 高 |
| `BDCSVD` | 大型矩阵 SVD | ★★★ | ★★★★★ | 高 |

**选择原则**（按优先级）：
1. 矩阵是**对称正定**？→ `LLT` 或 `LDLT`（最快）
2. 矩阵是**方阵可逆**？→ `PartialPivLU`（速度与稳定性均衡）
3. 矩阵**可能奇异**或需判断秩？→ `ColPivHouseholderQR` 或 `FullPivLU`
4. 矩阵**非方阵**（最小二乘）？→ `ColPivHouseholderQR` 或 `BDCSVD`

---

## 3. LU 分解

### 3.1 原理

LU 分解将矩阵 $A$ 分解为：

$$PA = LU$$

其中 $P$ 是置换矩阵，$L$ 是单位下三角矩阵，$U$ 是上三角矩阵。解方程组时先前向代入求 $Ly = Pb$，再后向代入求 $Ux = y$。

### 3.2 PartialPivLU（部分主元 LU）

```cpp
#include <iostream>
#include <Eigen/Dense>

int main() {
    Eigen::Matrix3d A;
    A <<  2, -1,  0,
         -1,  2, -1,
          0, -1,  2;

    Eigen::Vector3d b(1.0, 0.0, 1.0);

    // 方式1：直接在矩阵上调用 lu()（便捷方式）
    Eigen::Vector3d x1 = A.lu().solve(b);
    std::cout << "解 x = " << x1.transpose() << "\n";

    // 方式2：分解对象复用（多个右端项时推荐，只分解一次）
    Eigen::PartialPivLU<Eigen::Matrix3d> lu(A);
    Eigen::Vector3d x2 = lu.solve(b);
    Eigen::Vector3d x3 = lu.solve(Eigen::Vector3d(2.0, 1.0, 0.0)); // 不同的 b

    // 验证解的精度
    double residual = (A * x1 - b).norm();
    std::cout << "残差 ||Ax - b|| = " << residual << "\n"; // 应接近 0

    // 矩阵的行列式和逆（通过 LU 计算）
    double det = lu.determinant();
    Eigen::Matrix3d inv = lu.inverse();
    std::cout << "行列式 = " << det << "\n";
    std::cout << "逆矩阵:\n" << inv << "\n";

    return 0;
}
```

### 3.3 FullPivLU（全主元 LU，处理奇异矩阵）

```cpp
#include <Eigen/Dense>
#include <iostream>

int main() {
    // 秩缺失矩阵（行2 = 2 * 行1）
    Eigen::Matrix3d A;
    A << 1, 2, 3,
         2, 4, 6,
         0, 1, 2;

    Eigen::FullPivLU<Eigen::Matrix3d> lu(A);

    // 判断矩阵的秩
    std::cout << "矩阵的秩: " << lu.rank() << "\n";     // = 2
    std::cout << "是否可逆: " << lu.isInvertible() << "\n"; // = 0 (false)

    // 检查方程组是否有解
    Eigen::Vector3d b(1, 2, 0);
    if (lu.rank() < A.rows()) {
        std::cout << "方程组可能无解或有无穷多解\n";
    }

    // 即使秩缺失，FullPivLU 也能给出一个特解（若有解）
    Eigen::Vector3d x = lu.solve(b);
    double err = (A * x - b).norm();
    std::cout << "残差: " << err << "\n";  // 如果误差很大则无解

    // 核空间（零空间）= 方程组无穷多解的齐次部分
    // Eigen::MatrixXd kernel = lu.kernel(); // 需要动态大小

    return 0;
}
```

---

## 4. Cholesky 分解

### 4.1 原理

对于**对称正定（SPD）**矩阵 $A$，Cholesky 分解将其分解为：

$$A = LL^T \quad \text{（LLT）}$$
$$A = LDL^T \quad \text{（LDLT，更稳定）}$$

其中 $L$ 是下三角矩阵，$D$ 是对角矩阵。Cholesky 计算量约为 LU 的**一半**，是正定矩阵的首选。

### 4.2 LLT（标准 Cholesky）

```cpp
#include <Eigen/Dense>
#include <iostream>

int main() {
    // 构造一个典型的对称正定矩阵：A = B^T * B + eps*I
    Eigen::MatrixXd B = Eigen::MatrixXd::Random(4, 4);
    Eigen::Matrix4d A = B.transpose() * B + 4 * Eigen::Matrix4d::Identity();
    // A 现在是对称正定矩阵

    Eigen::VectorXd b = Eigen::VectorXd::Random(4);

    // LLT 分解（要求严格正定）
    Eigen::LLT<Eigen::Matrix4d> llt(A);

    if (llt.info() == Eigen::Success) {
        Eigen::VectorXd x = llt.solve(b);
        std::cout << "LLT 解: " << x.transpose() << "\n";

        // 提取 L 因子
        Eigen::Matrix4d L = llt.matrixL();
        std::cout << "验证 L * L^T ≈ A 的误差: "
                  << (L * L.transpose() - A).norm() << "\n";

        // 利用 L 计算 log(det(A)) = 2 * sum(log(diag(L)))
        double log_det = 2.0 * L.diagonal().array().log().sum();
        std::cout << "log(det(A)) = " << log_det << "\n";
        std::cout << "验证: log(det(A)) = " << std::log(A.determinant()) << "\n";
    } else {
        std::cout << "矩阵不是正定的！\n";
    }

    return 0;
}
```

### 4.3 LDLT（鲁棒 Cholesky，推荐）

```cpp
#include <Eigen/Dense>
#include <iostream>

int main() {
    // 对称半正定矩阵（特征值 ≥ 0，但可能等于 0）
    Eigen::Matrix4d A;
    A <<  4,  2, -1,  0,
          2,  5,  0,  1,
         -1,  0,  3,  0,
          0,  1,  0,  2;

    Eigen::LDLT<Eigen::Matrix4d> ldlt(A);

    // 检查分解结果
    if (ldlt.info() == Eigen::Success) {
        std::cout << "正/半正定: "
                  << (ldlt.isPositive() ? "正定" : "半正定") << "\n";

        // 求解多个右端项
        Eigen::Matrix<double, 4, 3> B = Eigen::Matrix<double, 4, 3>::Random();
        Eigen::Matrix<double, 4, 3> X = ldlt.solve(B);
        std::cout << "多右端项残差: " << (A * X - B).norm() << "\n";

        // D 向量（用于检查正定性：所有 d > 0 则正定）
        Eigen::Vector4d D = ldlt.vectorD();
        std::cout << "D 对角线: " << D.transpose() << "\n";

        // 计算行列式（仅对正定矩阵有意义）
        // det(A) = det(L)^2 * det(D) = 1^2 * prod(d_i)
        double det = D.prod();
        std::cout << "det(A) ≈ " << det << "\n";
    }

    return 0;
}
```

### 4.4 实战：多元高斯分布的对数似然

```cpp
#include <Eigen/Dense>
#include <cmath>
#include <iostream>

// 计算多元高斯分布的对数似然：
// log p(x | mu, Sigma) = -0.5 * [d*log(2pi) + log(det(Sigma)) + (x-mu)^T Sigma^{-1} (x-mu)]
double log_gaussian(const Eigen::VectorXd& x,
                    const Eigen::VectorXd& mu,
                    const Eigen::MatrixXd& Sigma) {
    int d = x.size();
    Eigen::VectorXd diff = x - mu;

    // 用 LDLT 分解（推荐用于协方差矩阵）
    Eigen::LDLT<Eigen::MatrixXd> ldlt(Sigma);
    double log_det = ldlt.vectorD().array().log().sum();
    double mahal   = diff.dot(ldlt.solve(diff));  // Mahalanobis距离平方

    return -0.5 * (d * std::log(2.0 * M_PI) + log_det + mahal);
}

int main() {
    int d = 3;
    Eigen::VectorXd mu(d);
    mu << 1.0, 2.0, 3.0;

    Eigen::MatrixXd Sigma(d, d);
    Sigma <<  4, 1, 0,
              1, 3, 0,
              0, 0, 2;

    Eigen::VectorXd x(d);
    x << 1.5, 2.5, 3.5;

    std::cout << "log p(x) = " << log_gaussian(x, mu, Sigma) << "\n";

    return 0;
}
```

---

## 5. QR 分解

### 5.1 原理

QR 分解将矩阵 $A$（$m \times n$，$m \geq n$）分解为：

$$A = QR$$

其中 $Q$ 是正交矩阵（$Q^TQ = I$），$R$ 是上三角矩阵。用于求解超定方程组（最小二乘）和全秩判断。

### 5.2 HouseholderQR

```cpp
#include <Eigen/Dense>
#include <iostream>

int main() {
    // 精确方程组（方阵）
    Eigen::Matrix3d A;
    A << 12, -51,   4,
          6, 167, -68,
         -4,  24, -41;

    Eigen::Vector3d b(1, 2, 3);

    // HouseholderQR（无列主元，速度快但数值稳定性略差）
    Eigen::HouseholderQR<Eigen::Matrix3d> qr(A);
    Eigen::Vector3d x = qr.solve(b);
    std::cout << "QR 解: " << x.transpose() << "\n";

    // 提取 Q 和 R
    Eigen::Matrix3d Q = qr.householderQ();
    Eigen::Matrix3d R = qr.matrixQR().triangularView<Eigen::Upper>();
    std::cout << "验证 Q^T Q ≈ I 误差: " << (Q.transpose() * Q - Eigen::Matrix3d::Identity()).norm() << "\n";
    std::cout << "验证 QR ≈ A 误差: " << (Q * R - A).norm() << "\n";

    return 0;
}
```

### 5.3 ColPivHouseholderQR（列主元 QR，推荐）

```cpp
#include <Eigen/Dense>
#include <iostream>

int main() {
    // 超定方程组：6 个方程，3 个未知数
    Eigen::MatrixXd A(6, 3);
    A << 1, 0, 0,
         0, 1, 0,
         0, 0, 1,
         1, 1, 0,
         0, 1, 1,
         1, 0, 1;

    Eigen::VectorXd b(6);
    b << 1, 2, 3, 3, 5, 4;

    // ColPivHouseholderQR：带列主元，自动处理秩缺失情况
    Eigen::ColPivHouseholderQR<Eigen::MatrixXd> qr(A);

    // 判断矩阵的秩
    std::cout << "矩阵的秩: " << qr.rank() << "\n";

    // 求最小二乘解（最小化 ||Ax - b||）
    Eigen::VectorXd x = qr.solve(b);
    std::cout << "最小二乘解: " << x.transpose() << "\n";
    std::cout << "残差 ||Ax - b||: " << (A * x - b).norm() << "\n";

    return 0;
}
```

---

## 6. 最小二乘问题深度解析

### 6.1 问题定义

当方程数 $m >$ 未知数 $n$（**超定方程组**），精确解不存在，需求：

$$\min_x \|Ax - b\|_2^2$$

几何意义：将 $b$ 正交投影到 $A$ 的列空间。

### 6.2 三种方法对比

```cpp
#include <Eigen/Dense>
#include <iostream>
#include <chrono>

int main() {
    int m = 1000, n = 100;
    Eigen::MatrixXd A = Eigen::MatrixXd::Random(m, n);
    Eigen::VectorXd b = Eigen::VectorXd::Random(m);

    auto time_it = [](auto&& fn) {
        auto t1 = std::chrono::high_resolution_clock::now();
        auto result = fn();
        auto t2 = std::chrono::high_resolution_clock::now();
        auto ms = std::chrono::duration_cast<std::chrono::microseconds>(t2 - t1).count();
        return std::make_pair(result, ms);
    };

    // 方法1：法方程（Normal Equation）
    // x = (A^T A)^{-1} A^T b
    // 最快，但条件数会变成 cond(A)^2，数值不稳定
    auto [x1, t1] = time_it([&]() {
        return (A.transpose() * A).ldlt().solve(A.transpose() * b);
    });

    // 方法2：QR 分解（推荐，速度与稳定性均衡）
    auto [x2, t2] = time_it([&]() {
        return A.colPivHouseholderQr().solve(b);
    });

    // 方法3：SVD（最稳定，最慢）
    auto [x3, t3] = time_it([&]() {
        return A.bdcSvd(Eigen::ComputeThinU | Eigen::ComputeThinV).solve(b);
    });

    std::cout << "法方程  : " << t1 << " μs，残差 = " << (A*x1-b).norm() << "\n";
    std::cout << "QR 分解 : " << t2 << " μs，残差 = " << (A*x2-b).norm() << "\n";
    std::cout << "SVD    : " << t3 << " μs，残差 = " << (A*x3-b).norm() << "\n";

    return 0;
}
```

### 6.3 带正则化的最小二乘（Ridge Regression）

$$\min_x \|Ax - b\|_2^2 + \lambda \|x\|_2^2$$

解析解：$x = (A^TA + \lambda I)^{-1}A^Tb$

```cpp
#include <Eigen/Dense>
#include <iostream>

Eigen::VectorXd ridge_regression(const Eigen::MatrixXd& A,
                                  const Eigen::VectorXd& b,
                                  double lambda) {
    int n = A.cols();
    // A^T A + lambda * I 是对称正定矩阵，用 LDLT 求解
    Eigen::MatrixXd ATA = A.transpose() * A;
    ATA.diagonal().array() += lambda;  // 添加正则化项
    return ATA.ldlt().solve(A.transpose() * b);
}

int main() {
    int m = 50, n = 100;  // 欠定：方程数 < 未知数
    Eigen::MatrixXd A = Eigen::MatrixXd::Random(m, n);
    Eigen::VectorXd b = Eigen::VectorXd::Random(m);

    // 不同正则化强度
    for (double lambda : {0.0, 0.01, 0.1, 1.0, 10.0}) {
        Eigen::VectorXd x = ridge_regression(A, b, lambda);
        double fit_err = (A * x - b).norm();
        double x_norm  = x.norm();
        std::printf("λ = %5.2f: 拟合误差 = %6.4f，||x|| = %6.4f\n",
                    lambda, fit_err, x_norm);
    }
    // lambda 增大：||x|| 缩小（正则化效果），拟合误差增大（欠拟合）

    return 0;
}
```

### 6.4 加权最小二乘（WLS）

$$\min_x \sum_i w_i (a_i^T x - b_i)^2 = \min_x \|W^{1/2}(Ax - b)\|_2^2$$

```cpp
#include <Eigen/Dense>
#include <iostream>

// 加权最小二乘：min ||W^{1/2}(Ax - b)||^2
// 等价于解 (A^T W A) x = A^T W b
Eigen::VectorXd weighted_ls(const Eigen::MatrixXd& A,
                              const Eigen::VectorXd& b,
                              const Eigen::VectorXd& w) {
    // 构造加权矩阵（对角阵）
    Eigen::MatrixXd AW  = A.array().colwise() * w.array();  // A 的每行乘以权重
    Eigen::MatrixXd AWA = AW.transpose() * A;
    Eigen::VectorXd AWb = AW.transpose() * b;
    return AWA.ldlt().solve(AWb);
}

int main() {
    // 数据点拟合直线（有些点的测量误差较大，权重低）
    Eigen::MatrixXd A(5, 2);
    A << 1, 1,
         2, 1,
         3, 1,
         4, 1,
         5, 1;

    Eigen::VectorXd b(5);
    b << 2.1, 4.0, 5.9, 8.2, 10.1;

    // 普通 LS
    Eigen::VectorXd x_ls = A.colPivHouseholderQr().solve(b);

    // 加权 LS（第3个点可信度低，权重设为 0.1）
    Eigen::VectorXd w(5);
    w << 1.0, 1.0, 0.1, 1.0, 1.0;
    Eigen::VectorXd x_wls = weighted_ls(A, b, w);

    std::cout << "普通 LS：斜率 = " << x_ls(0) << "，截距 = " << x_ls(1) << "\n";
    std::cout << "加权 LS：斜率 = " << x_wls(0) << "，截距 = " << x_wls(1) << "\n";

    return 0;
}
```

---

## 7. 分解的复用与性能

### 7.1 一次分解，多次求解

```cpp
#include <Eigen/Dense>
#include <iostream>

int main() {
    int n = 500;
    Eigen::MatrixXd A = Eigen::MatrixXd::Random(n, n);
    A = A.transpose() * A + n * Eigen::MatrixXd::Identity(n, n); // 确保正定

    // 一次 Cholesky 分解（O(n^3) 计算量）
    Eigen::LDLT<Eigen::MatrixXd> ldlt(A);

    // 多次求解（每次仅 O(n^2)）
    Eigen::MatrixXd B = Eigen::MatrixXd::Random(n, 10); // 10 个右端项
    Eigen::MatrixXd X = ldlt.solve(B);

    // 检查精度
    std::cout << "多右端项残差: " << (A * X - B).norm() << "\n";

    // 矩阵的逆（通过 n 次求解）
    Eigen::MatrixXd I_n = Eigen::MatrixXd::Identity(n, n);
    Eigen::MatrixXd A_inv = ldlt.solve(I_n);
    std::cout << "逆矩阵误差: " << (A * A_inv - I_n).norm() << "\n";

    return 0;
}
```

### 7.2 增量更新（Rank-1 Update）

当矩阵只有微小变化时，可用秩1更新代替完整重分解：

```cpp
// Eigen 的 LDLT 支持秩更新
Eigen::LDLT<Eigen::MatrixXd> ldlt(A);

Eigen::VectorXd u = Eigen::VectorXd::Random(n);
// A' = A + u * u^T（正定矩阵加秩1正定更新后仍正定）
// 使用 rankUpdate 就地更新，避免重新分解
ldlt.rankUpdate(u, 1.0);  // 第二个参数为权重 sigma，A' = A + sigma * u * u^T

Eigen::VectorXd b = Eigen::VectorXd::Random(n);
Eigen::VectorXd x = ldlt.solve(b);  // 使用更新后的分解求解
```

---

## 8. 矩阵的基本性质计算

### 8.1 行列式、迹与范数

```cpp
#include <Eigen/Dense>
#include <iostream>

int main() {
    Eigen::Matrix4d A = Eigen::Matrix4d::Random();

    // 行列式（小矩阵直接调用，大矩阵用 LU 的行列式）
    double det_small = A.determinant();  // 3x3 及以下精确，大矩阵不推荐

    // 用 LU 计算（更稳定）
    Eigen::PartialPivLU<Eigen::Matrix4d> lu(A);
    double det_lu = lu.determinant();

    // 迹（主对角线之和）
    double tr = A.trace();

    // 范数
    double frob = A.norm();           // Frobenius 范数：sqrt(sum of squares)
    double one_norm = A.colwise().lpNorm<1>().maxCoeff(); // 1-范数：最大列绝对和
    double inf_norm = A.rowwise().lpNorm<1>().maxCoeff(); // ∞-范数：最大行绝对和

    std::cout << "det(A) = " << det_lu << "\n";
    std::cout << "tr(A)  = " << tr << "\n";
    std::cout << "||A||_F = " << frob << "\n";
    std::cout << "||A||_1 = " << one_norm << "\n";
    std::cout << "||A||_∞ = " << inf_norm << "\n";

    return 0;
}
```

### 8.2 条件数

条件数衡量矩阵对扰动的敏感程度，条件数越大，求解越不稳定：

```cpp
#include <Eigen/Dense>
#include <iostream>

double condition_number(const Eigen::MatrixXd& A) {
    // 用 SVD 计算条件数 = sigma_max / sigma_min
    Eigen::JacobiSVD<Eigen::MatrixXd> svd(A);
    auto sv = svd.singularValues();
    return sv(0) / sv(sv.size() - 1);  // 奇异值已从大到小排序
}

int main() {
    // 良态矩阵
    Eigen::Matrix3d A = Eigen::Matrix3d::Identity() * 2.0;
    std::cout << "单位矩阵×2 条件数: " << condition_number(A) << "\n"; // 1.0

    // 病态矩阵（Hilbert 矩阵）
    int n = 8;
    Eigen::MatrixXd H(n, n);
    for (int i = 0; i < n; ++i)
        for (int j = 0; j < n; ++j)
            H(i, j) = 1.0 / (i + j + 1);

    std::cout << "8x8 Hilbert 矩阵条件数: " << condition_number(H) << "\n";
    // 极大（约 10^10），求解精度会损失约 10 位小数！

    return 0;
}
```

---

## 9. 综合实战：三维空间直线拟合

从一组 3D 点中拟合最优直线（最小二乘意义）：

```cpp
#include <Eigen/Dense>
#include <iostream>
#include <random>

// 用 PCA/SVD 方法拟合 3D 直线
// 输入：N×3 点云矩阵
// 输出：直线上一点（均值）+ 方向向量（主成分）
std::pair<Eigen::Vector3d, Eigen::Vector3d>
fit_line_3d(const Eigen::MatrixXd& points) {
    assert(points.cols() == 3);

    // 1. 计算质心
    Eigen::Vector3d centroid = points.colwise().mean();

    // 2. 中心化
    Eigen::MatrixXd centered = points.rowwise() - centroid.transpose();

    // 3. SVD → 最大奇异值对应的右奇异向量即为直线方向
    Eigen::JacobiSVD<Eigen::MatrixXd> svd(centered,
                                           Eigen::ComputeThinU | Eigen::ComputeThinV);

    // V 的第一列对应最大奇异值（方差最大的方向）
    Eigen::Vector3d direction = svd.matrixV().col(0);

    return {centroid, direction};
}

int main() {
    // 生成沿 (1,1,1)/sqrt(3) 方向的有噪声直线点
    std::mt19937 rng(42);
    std::normal_distribution<double> noise(0.0, 0.05);

    int N = 200;
    Eigen::MatrixXd points(N, 3);
    Eigen::Vector3d true_dir(1, 1, 1);
    true_dir.normalize();

    for (int i = 0; i < N; ++i) {
        double t = (i - N/2) * 0.1;
        points.row(i) = (t * true_dir +
                         Eigen::Vector3d(noise(rng), noise(rng), noise(rng))).transpose();
    }

    // 拟合直线
    auto [center, dir] = fit_line_3d(points);

    std::cout << "真实方向:  " << true_dir.transpose() << "\n";
    std::cout << "拟合方向:  " << dir.transpose() << "\n";

    // 方向向量可能方向相反（取绝对值比较误差）
    double angle_err = std::acos(std::abs(dir.dot(true_dir))) * 180.0 / M_PI;
    std::cout << "方向误差: " << angle_err << "°\n";

    return 0;
}
```

---

## 小结

| 场景 | 推荐分解 | API |
|---|---|---|
| 对称正定方阵 | LDLT | `A.ldlt().solve(b)` |
| 一般可逆方阵 | PartialPivLU | `A.lu().solve(b)` |
| 可能奇异 / 需判断秩 | FullPivLU | `Eigen::FullPivLU<> lu(A)` |
| 超定最小二乘 | ColPivHouseholderQR | `A.colPivHouseholderQr().solve(b)` |
| 最稳定（奇异也行）| SVD | `A.bdcSvd(...).solve(b)` |
| 带正则化最小二乘 | LDLT on $(A^TA + \lambda I)$ | 手动构建后 LDLT |
| 多右端项 | 任意分解，一次 compute | `solver.solve(B)` |

下一篇将讲解特征值分解、SVD 的深层含义，以及 3D 几何变换（旋转矩阵、四元数、刚体变换）。
