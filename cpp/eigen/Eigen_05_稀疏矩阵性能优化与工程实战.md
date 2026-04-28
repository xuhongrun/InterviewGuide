# Eigen C++ 线性代数库（五）：稀疏矩阵、性能优化与工程实战

> **系列导航**
> - 第一篇：入门与基本类型
> - 第二篇：矩阵与向量操作详解
> - 第三篇：线性方程组求解与矩阵分解
> - 第四篇：特征值分解、SVD 与几何变换
> - **第五篇：稀疏矩阵、性能优化与工程实战** ← 当前
> - 第六篇：ROS / SLAM 生态互操作
> - 第七篇：unsupported 模块与非线性优化

---

## 1. 稀疏矩阵基础

### 1.1 什么时候用稀疏矩阵？

当矩阵中**大部分元素为零**时，使用 `SparseMatrix` 可以：
- 内存占用从 $O(n^2)$ 降至 $O(\text{nnz})$（nnz = 非零元素数）
- 矩阵-向量乘法从 $O(n^2)$ 降至 $O(\text{nnz})$

典型场景：
- **有限元分析**：节点只与邻近节点相连，矩阵稀疏度 > 99%
- **图算法**：邻接矩阵、Laplacian 矩阵
- **计算机图形学**：物理模拟中的刚度矩阵
- **优化问题**：Hessian 矩阵在参数较多时极度稀疏
- **自然语言处理**：词袋模型的 TF-IDF 矩阵

### 1.2 CSC/CSR 存储格式

Eigen 的 `SparseMatrix` 默认使用**压缩列存储（CSC，Compressed Sparse Column）**：

```
对于稀疏矩阵：
0  3  0
2  0  0
0  0  1

CSC 格式：
values(非零值，按列):      [2, 3, 1]
inner_indices(行索引):     [1, 0, 2]
outer_ptrs(各列起始位置): [0, 1, 2, 3]
```

行主序版：`SparseMatrix<double, RowMajor>`（CSR 格式）。

---

## 2. 构建稀疏矩阵

### 2.1 Triplet 方式（推荐）

```cpp
#include <Eigen/Sparse>
#include <vector>
#include <iostream>

using SpMat = Eigen::SparseMatrix<double>;        // 列主序（默认）
using SpMatR = Eigen::SparseMatrix<double, Eigen::RowMajor>; // 行主序
using Triplet = Eigen::Triplet<double>;

int main() {
    int n = 5;
    SpMat A(n, n);  // 声明时只指定大小，不分配非零元素

    // 准备 Triplet 列表（行, 列, 值）
    std::vector<Triplet> triplets;
    triplets.reserve(3 * n);  // 预分配，避免反复扩容

    // 构建三对角矩阵
    for (int i = 0; i < n; ++i) {
        triplets.emplace_back(i, i, 4.0);          // 主对角线
        if (i > 0) {
            triplets.emplace_back(i, i - 1, -1.0); // 下对角线
            triplets.emplace_back(i - 1, i, -1.0); // 上对角线
        }
    }

    // 重要：相同位置的 triplet 会自动相加（对有限元矩阵装配很方便）
    triplets.emplace_back(2, 2, 1.0);  // A(2,2) 最终为 4 + 1 = 5

    A.setFromTriplets(triplets.begin(), triplets.end());

    std::cout << "稀疏矩阵 A:\n" << A << "\n";
    std::cout << "非零元素数: " << A.nonZeros() << "\n";
    std::cout << "稀疏率: " << (1.0 - (double)A.nonZeros() / (n * n)) * 100 << "%\n\n";

    // 转为稠密矩阵（仅用于调试）
    Eigen::MatrixXd A_dense = Eigen::MatrixXd(A);
    std::cout << "稠密表示:\n" << A_dense << "\n";

    return 0;
}
```

### 2.2 直接插入（小矩阵 / 已知结构时）

```cpp
SpMat B(4, 4);

// 方式1：压缩前随机插入（内部用链表，很慢）
B.insert(0, 1) = 3.0;  // 不推荐用于大矩阵
B.insert(2, 3) = -1.0;
B.makeCompressed();     // 转换为 CSC 格式，压缩存储

// 方式2：按列顺序插入（比随机插入快）
B.reserve(Eigen::VectorXi::Constant(4, 2));  // 预留每列有2个非零元
// 按列主序插入
B.insert(0, 0) = 1.0;
B.insert(1, 0) = 2.0;  // 列0：(0,0)=1, (1,0)=2
B.insert(1, 1) = 3.0;  // 列1：(1,1)=3
B.makeCompressed();
```

### 2.3 复杂结构：2D 泊松方程矩阵

```cpp
// 构建 n×n 网格上的泊松方程矩阵（五点差分，行主序更直观）
SpMat build_poisson_2d(int n) {
    int N = n * n;  // 总节点数
    SpMat A(N, N);

    std::vector<Triplet> trips;
    trips.reserve(5 * N);

    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < n; ++j) {
            int idx = i * n + j;       // 节点全局编号

            trips.emplace_back(idx, idx, 4.0);    // 自身

            if (j > 0)   trips.emplace_back(idx, idx - 1, -1.0); // 左
            if (j < n-1) trips.emplace_back(idx, idx + 1, -1.0); // 右
            if (i > 0)   trips.emplace_back(idx, idx - n, -1.0); // 上
            if (i < n-1) trips.emplace_back(idx, idx + n, -1.0); // 下
        }
    }

    A.setFromTriplets(trips.begin(), trips.end());
    return A;
}
```

---

## 3. 稀疏矩阵操作

### 3.1 基本运算

```cpp
SpMat A = build_poisson_2d(10);  // 100×100 稀疏矩阵
SpMat B = build_poisson_2d(10);

// 加减法（非零结构取并集）
SpMat C = A + B;
SpMat D = A - 0.5 * B;

// 标量乘法
SpMat E = 2.0 * A;

// 稀疏×稀疏（结果可能比较稠密，要小心）
SpMat F = A * B;   // 通常不推荐，除非结果仍稀疏

// 稀疏×稠密（最常用！）
Eigen::VectorXd b = Eigen::VectorXd::Ones(100);
Eigen::VectorXd x = A * b;  // 高效：O(nnz)

// 转置
SpMat At = A.transpose();
SpMat Asymm = A + At;  // 对称化

std::cout << "A 非零元数: " << A.nonZeros() << "\n";
std::cout << "A*B 非零元数: " << F.nonZeros() << "\n";
```

### 3.2 元素访问与遍历

```cpp
SpMat A(5, 5);
// ... (填入数据)

// 随机访问（很慢！）
double val = A.coeff(2, 3);  // 不存在则返回 0

// 修改（若已存在才有效，否则需 insert）
A.coeffRef(1, 2) = 5.0;  // 若 (1,2) 不存在会自动插入

// 高效遍历非零元素（按列主序）
for (int j = 0; j < A.cols(); ++j) {
    for (SpMat::InnerIterator it(A, j); it; ++it) {
        std::cout << "A(" << it.row() << ", " << it.col() << ") = " << it.value() << "\n";
        it.valueRef() *= 2.0;  // 可修改值（不能修改结构）
    }
}

// 按行遍历（需要 RowMajor 矩阵更高效）
SpMatR Ar = A;  // 转换为行主序
for (int i = 0; i < Ar.rows(); ++i) {
    for (SpMatR::InnerIterator it(Ar, i); it; ++it) {
        // it.col() 是列索引，it.row() = i
    }
}
```

---

## 4. 稀疏矩阵求解器

### 4.1 直接法求解器

```cpp
#include <Eigen/Sparse>
#include <Eigen/SparseCholesky>
#include <Eigen/SparseLU>
#include <Eigen/SparseQR>
#include <iostream>

int main() {
    int n = 100;
    SpMat A = build_poisson_2d(n);
    int N = n * n;
    Eigen::VectorXd b = Eigen::VectorXd::Ones(N);
    Eigen::VectorXd x;

    // =============================================
    // 方法1：SimplicialLLT（对称正定，最快）
    // =============================================
    Eigen::SimplicialLLT<SpMat> solver_llt;
    solver_llt.compute(A);
    if (solver_llt.info() == Eigen::Success) {
        x = solver_llt.solve(b);
        std::cout << "SimplicialLLT 残差: " << (A * x - b).norm() << "\n";
    }

    // =============================================
    // 方法2：SimplicialLDLT（对称正定/半正定，更稳定）
    // =============================================
    Eigen::SimplicialLDLT<SpMat> solver_ldlt;
    solver_ldlt.compute(A);
    if (solver_ldlt.info() == Eigen::Success) {
        x = solver_ldlt.solve(b);
        std::cout << "SimplicialLDLT 残差: " << (A * x - b).norm() << "\n";
    }

    // =============================================
    // 方法3：SparseLU（通用方阵，无需正定）
    // =============================================
    Eigen::SparseLU<SpMat> solver_lu;
    // 分析稀疏结构（分别调用可重用分析结果）
    solver_lu.analyzePattern(A);   // 符号分析，O(nnz)
    solver_lu.factorize(A);        // 数值分解，O(nnz * fill_factor)

    if (solver_lu.info() == Eigen::Success) {
        x = solver_lu.solve(b);
        std::cout << "SparseLU 残差: " << (A * x - b).norm() << "\n";
    } else {
        std::cout << "SparseLU 分解失败: " << solver_lu.lastErrorMessage() << "\n";
    }

    // =============================================
    // 方法4：SparseQR（矩形矩阵、最小二乘）
    // =============================================
    // SpMat A_rect(150, N);
    // Eigen::SparseQR<SpMat, Eigen::COLAMDOrdering<int>> solver_qr;
    // solver_qr.compute(A_rect);

    return 0;
}
```

### 4.2 迭代法求解器

对于超大规模问题（$n > 10^5$），直接法的内存和时间开销不可接受，需用迭代法：

```cpp
#include <Eigen/Sparse>
#include <Eigen/IterativeLinearSolvers>
#include <iostream>

int main() {
    int n = 200;
    SpMat A = build_poisson_2d(n);
    int N = n * n;
    Eigen::VectorXd b = Eigen::VectorXd::Ones(N);
    Eigen::VectorXd x;

    // =============================================
    // 共轭梯度法（CG）：对称正定矩阵
    // =============================================
    Eigen::ConjugateGradient<SpMat, Eigen::Lower | Eigen::Upper> cg;
    cg.setMaxIterations(1000);   // 最大迭代次数
    cg.setTolerance(1e-8);       // 收敛阈值

    cg.compute(A);
    x = cg.solve(b);

    std::cout << "CG 迭代次数: " << cg.iterations() << "\n";
    std::cout << "CG 估计误差: " << cg.error() << "\n";
    std::cout << "CG 真实残差: " << (A * x - b).norm() / b.norm() << "\n\n";

    // 热启动（用已知近似解初始化）
    Eigen::VectorXd x0 = Eigen::VectorXd::Zero(N);
    x = cg.solveWithGuess(b, x0);

    // =============================================
    // 带不完全 Cholesky 预条件子的 CG（ICCG）
    // =============================================
    Eigen::ConjugateGradient<SpMat,
        Eigen::Lower | Eigen::Upper,
        Eigen::IncompleteCholesky<double>> iccg;
    iccg.compute(A);
    x = iccg.solve(b);

    std::cout << "ICCG 迭代次数: " << iccg.iterations() << "\n";
    std::cout << "ICCG 真实残差: " << (A * x - b).norm() / b.norm() << "\n\n";

    // =============================================
    // BiCGSTAB：非对称矩阵
    // =============================================
    // 构造非对称矩阵（泊松矩阵加上非对称扰动）
    SpMat B = A;
    // 添加随机非对称项...

    Eigen::BiCGSTAB<SpMat> bicg;
    bicg.setMaxIterations(500);
    bicg.setTolerance(1e-8);
    bicg.compute(A);  // 用对称的 A 测试
    x = bicg.solve(b);

    std::cout << "BiCGSTAB 迭代次数: " << bicg.iterations() << "\n";
    std::cout << "BiCGSTAB 真实残差: " << (A * x - b).norm() / b.norm() << "\n";

    return 0;
}
```

### 4.3 求解器选择指南

| 矩阵特性 | 尺寸 | 推荐求解器 |
|---|---|---|
| 对称正定 | 中小（< 10^4）| `SimplicialLDLT` |
| 对称正定 | 大（> 10^4）| `ConjugateGradient` + 预条件子 |
| 一般方阵 | 中小 | `SparseLU` |
| 一般方阵 | 大 | `BiCGSTAB` + 预条件子 |
| 超定（最小二乘）| 任意 | `SparseQR` |

---

## 5. 性能优化

### 5.1 表达式模板与懒求值

```cpp
#include <Eigen/Dense>

// Eigen 对简单运算（加法、标量乘法）使用懒求值，只在赋值时计算
// 对矩阵乘法默认立即求值（防止别名）

MatrixXd A = MatrixXd::Random(500, 500);
MatrixXd B = MatrixXd::Random(500, 500);
MatrixXd C = MatrixXd::Random(500, 500);
MatrixXd D(500, 500);

// 懒求值（内部合并为一个循环，无临时对象）：
D = 2.0 * A + B - C;             // 完美，合并计算

// 矩阵乘法：Eigen 默认急求值以防止别名
D = A * B;                        // 创建临时对象，安全
D.noalias() = A * B;              // 不创建临时对象，需保证 D 与 A、B 无内存重叠

// 链式乘法（Eigen 自动选择计算顺序）
D.noalias() = A * B + C;          // 高效：A*B 的结果直接累加到 D，无额外临时对象
D.noalias() += A * B;             // 累积乘法（非常高效）

// eval() 强制立即求值（产生临时对象，解决别名问题）
A = (A + B).eval();               // 等价于 A = A + B（有别名，需 eval）
A.transposeInPlace();             // 就地转置（代替 A = A.transpose()）
```

### 5.2 noalias 与别名问题

```cpp
#include <Eigen/Dense>
#include <iostream>

MatrixXd A = MatrixXd::Random(4, 4);
MatrixXd B = MatrixXd::Random(4, 4);
MatrixXd C(4, 4);

// 危险：A 出现在等号两侧（别名）
// A = A * A;    // 未定义行为！（实际 Eigen 会自动处理，但建议显式）

// 安全方式1：中间变量
C = A * A;
A = C;

// 安全方式2：eval()
A = (A * A).eval();

// 安全方式3：对无别名的情况，用 noalias() 提速
C.noalias() = A * B;         // C 与 A、B 不重叠，无别名，高效

// 正确示例：连续变换
MatrixXd result = MatrixXd::Zero(4, 4);
result.noalias() += A * B;   // 安全，result 独立
result.noalias() += B * A;
```

### 5.3 内存对齐与 SIMD

```cpp
// Eigen 要求固定大小的矩阵按 16/32 字节对齐（SSE/AVX）
// 在结构体中使用 Eigen 固定大小成员时，必须正确处理对齐

struct Pose {
    Eigen::Vector3d position;        // 正常
    Eigen::Quaterniond orientation;  // 正常
    Eigen::Matrix4d transform;       // 需要对齐！

    // 添加以下宏，确保 new 操作符按 Eigen 要求对齐
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW
};

// 或者使用对齐分配器（std::vector 中使用 Eigen 固定大小类型）
#include <Eigen/StdVector>

std::vector<Eigen::Matrix4d, Eigen::aligned_allocator<Eigen::Matrix4d>> poses;
poses.emplace_back(Eigen::Matrix4d::Identity());
// 使用 Eigen::aligned_allocator 确保每个 Matrix4d 正确对齐
```

> **Eigen 3.4 + C++17 的更新**：
> - C++17 起，`new` 操作符已经能正确处理 over-aligned 类型（`alignas(32)` 等）。
>   编译器满足条件时，Eigen 会**自动**走 over-aligned new 路径，
>   `EIGEN_MAKE_ALIGNED_OPERATOR_NEW` 与 `aligned_allocator` 在多数场景**已不再必需**。
> - 仍然推荐加上的场景：
>   1. 编译器/标准库对 over-aligned new 支持不完整（旧 GCC、嵌入式工具链）。
>   2. 与第三方库共享 ABI、对外暴露包含 Eigen 成员的类。
>   3. 需要兼容 Eigen 3.3 及更早版本的代码。
> - 也可以在编译期统一关闭 SIMD 对齐要求：`-DEIGEN_MAX_ALIGN_BYTES=0`，但会损失性能，不推荐。
> - 现代 C++17 项目里 `std::vector<Eigen::Matrix4d>` 在 Eigen 3.4+ 通常工作正常，
>   但跨平台保险起见仍可加 `Eigen::aligned_allocator`。

### 5.4 多线程与并行

Eigen 内部对若干运算（最典型的是**大矩阵-矩阵乘法**、稀疏 LU）支持基于 OpenMP 的并行：

```cpp
#include <Eigen/Core>

// 1. 启用：编译时打开 OpenMP
//    g++ -O3 -fopenmp -DEIGEN_DONT_PARALLELIZE=0 main.cpp

// 2. 运行时控制线程数
Eigen::setNbThreads(4);                // 显式设为 4 线程
int n = Eigen::nbThreads();             // 当前线程数
// 也可通过环境变量：OMP_NUM_THREADS=4 ./demo

// 3. 完全禁用 Eigen 内部并行（防止与外层 OpenMP 嵌套冲突）
//    g++ -DEIGEN_DONT_PARALLELIZE main.cpp
```

**与外层 OpenMP 嵌套的注意事项**（典型踩坑）：

```cpp
// 如果上层已经在 OpenMP 区域内对每条数据并行处理，
// 此时 Eigen 又试图并行做矩阵乘法 → 线程爆炸 + 性能反而变差
#pragma omp parallel for
for (int i = 0; i < N; ++i) {
    // 每个线程都会再 fork 出多个 Eigen 线程
    Eigen::MatrixXd C = A[i] * B[i];   // ⚠️
}

// 正确做法：在并行循环中关闭 Eigen 自身并行
Eigen::setNbThreads(1);
#pragma omp parallel for
for (int i = 0; i < N; ++i) {
    Eigen::MatrixXd C = A[i] * B[i];
}
```

**线程安全规则**：

| 操作 | 是否线程安全 |
|---|---|
| 多线程**只读**同一个矩阵 | ✅ 安全 |
| 多线程同时写**不同**矩阵 | ✅ 安全 |
| 多线程并发写**同一**矩阵的不同 block | ⚠️ 仅当 block 不重叠且对齐到 SIMD 边界时安全 |
| 多线程同时调用同一个分解器（`LLT`、`LU` 等）的 `solve()` | ❌ **不安全**，需各自构造 |
| `setNbThreads()` 设置后并行度全局生效 | ✅ |

### 5.5 正确使用 resize/conservativeResize

```cpp
MatrixXd M(100, 100);

// resize：改变大小，原有数据不保留（高效）
M.resize(200, 200);

// conservativeResize：保留左上角原有数据
M.conservativeResize(150, 150);

// 预分配后循环（避免重复申请内存）
MatrixXd result;
result.resize(1000, 1000);

for (int iter = 0; iter < 100; ++iter) {
    result.setZero();  // 清零（不重新分配）
    // ... 计算 ...
}
```

### 5.6 编译器优化与 BLAS

```cmake
# CMakeLists.txt

# 基础优化
target_compile_options(demo PRIVATE
    -O3
    -march=native         # 启用本机 CPU 全部指令集（AVX2、FMA 等）
    -funroll-loops        # 循环展开
    -ffast-math           # 快速浮点（注意：可能导致 NaN/Inf 行为不同）
)

# 链接 OpenBLAS（大矩阵乘法更快）
# Eigen 会自动使用已链接的 BLAS/LAPACK
find_package(BLAS REQUIRED)
find_package(LAPACK REQUIRED)
target_compile_definitions(demo PRIVATE EIGEN_USE_BLAS EIGEN_USE_LAPACKE)
target_link_libraries(demo PRIVATE Eigen3::Eigen ${BLAS_LIBRARIES} ${LAPACK_LIBRARIES})
```

### 5.7 Tensor 模块（高维数组）

```cpp
#include <unsupported/Eigen/CXX11/Tensor>

// Eigen Tensor 用于深度学习等场景
Eigen::Tensor<float, 3> t(2, 3, 4);  // 形状 [2, 3, 4]
t.setRandom();

// 维度操作
Eigen::Tensor<float, 2> mat = t.chip(0, 0);  // 取第0个切片（沿维度0）

// 张量收缩（广义矩阵乘法）
Eigen::Tensor<float, 2> A_mat(3, 4), B_mat(4, 5);
A_mat.setRandom(); B_mat.setRandom();
// 沿维度 1（A）和维度 0（B）收缩（等价于矩阵乘法）
Eigen::array<Eigen::IndexPair<int>, 1> contraction = {Eigen::IndexPair<int>(1, 0)};
Eigen::Tensor<float, 2> C_mat = A_mat.contract(B_mat, contraction);
```

---

## 6. 综合实战：完整的线性卡尔曼滤波器

```cpp
#include <Eigen/Dense>
#include <iostream>
#include <random>
#include <vector>
#include <iomanip>

/**
 * @brief 线性卡尔曼滤波器
 *        状态：[x, y, vx, vy]（位置 + 速度）
 *        观测：[x, y]（仅观测位置，速度不可观测）
 */
class KalmanFilter {
public:
    // 类型别名（避免重复写长类型名）
    using Vec2d = Eigen::Vector2d;
    using Vec4d = Eigen::Vector4d;
    using Mat2d = Eigen::Matrix2d;
    using Mat4d = Eigen::Matrix4d;
    using Mat4x2d = Eigen::Matrix<double, 4, 2>;
    using Mat2x4d = Eigen::Matrix<double, 2, 4>;

    /**
     * @param dt 时间步长（秒）
     * @param process_noise 过程噪声强度
     * @param meas_noise 观测噪声强度
     */
    KalmanFilter(double dt, double process_noise = 0.01, double meas_noise = 0.5)
        : dt_(dt) {

        // 状态转移矩阵 F（匀速运动模型）
        F_ << 1, 0, dt, 0,
              0, 1, 0,  dt,
              0, 0, 1,  0,
              0, 0, 0,  1;

        // 观测矩阵 H（只能观测位置）
        H_ << 1, 0, 0, 0,
              0, 1, 0, 0;

        // 过程噪声协方差 Q
        // 假设加速度为高斯噪声，用离散时间过程噪声模型
        double q = process_noise;
        double dt2 = dt * dt;
        double dt3 = dt2 * dt;
        double dt4 = dt3 * dt;
        Q_ << dt4/4*q, 0,       dt3/2*q, 0,
              0,       dt4/4*q, 0,       dt3/2*q,
              dt3/2*q, 0,       dt2*q,   0,
              0,       dt3/2*q, 0,       dt2*q;

        // 观测噪声协方差 R
        R_ = Mat2d::Identity() * meas_noise;

        // 初始状态和协方差
        x_ = Vec4d::Zero();
        P_ = Mat4d::Identity() * 100.0;  // 初始不确定性较大
    }

    /** @brief 初始化状态 */
    void init(const Vec2d& pos, const Vec2d& vel = Vec2d::Zero()) {
        x_.head<2>() = pos;
        x_.tail<2>() = vel;
        P_ = Mat4d::Identity();
    }

    /** @brief 预测步骤（无控制输入）*/
    void predict() {
        x_ = F_ * x_;
        P_ = F_ * P_ * F_.transpose() + Q_;
    }

    /** @brief 预测步骤（带控制输入 u = [ax, ay]）*/
    void predict(const Vec2d& accel) {
        Eigen::Vector4d B_u(0.5 * dt_ * dt_ * accel.x(),
                            0.5 * dt_ * dt_ * accel.y(),
                            dt_ * accel.x(),
                            dt_ * accel.y());
        x_ = F_ * x_ + B_u;
        P_ = F_ * P_ * F_.transpose() + Q_;
    }

    /** @brief 更新步骤（给定位置观测 z = [x, y]）*/
    void update(const Vec2d& z) {
        // 创新（测量残差）
        Vec2d y_innov = z - H_ * x_;

        // 创新协方差
        Mat2d S = H_ * P_ * H_.transpose() + R_;

        // 卡尔曼增益（用 LDLT 求解代替显式求逆，更稳定）
        // K = P H^T S^{-1}  →  K S = P H^T  →  S^T K^T = H P^T = H P（P 对称）
        Mat4x2d K = (S.transpose().ldlt().solve((H_ * P_.transpose()).transpose())).transpose();

        // 状态更新
        x_ = x_ + K * y_innov;

        // 协方差更新（Joseph 形式，数值更稳定）
        Mat4d I_KH = Mat4d::Identity() - K * H_;
        P_ = I_KH * P_ * I_KH.transpose() + K * R_ * K.transpose();
        // 简化形式（可能数值不稳定）：P_ = (Mat4d::Identity() - K * H_) * P_;
    }

    // Getters
    Vec4d state() const { return x_; }
    Vec2d position() const { return x_.head<2>(); }
    Vec2d velocity() const { return x_.tail<2>(); }
    Mat4d covariance() const { return P_; }

    /** @brief 位置不确定性（标准差）*/
    Vec2d position_std() const {
        return P_.diagonal().head<2>().array().sqrt();
    }

    /** @brief Mahalanobis 距离（用于异常值检测）*/
    double mahalanobis(const Vec2d& z) const {
        Vec2d y = z - H_ * x_;
        Mat2d S = H_ * P_ * H_.transpose() + R_;
        return std::sqrt(y.dot(S.ldlt().solve(y)));
    }

private:
    double dt_;
    Mat4d F_, Q_, P_;
    Mat4x2d K_;
    Mat2x4d H_;
    Mat2d R_;
    Vec4d x_;
};

// ---- 测试与仿真 ----

struct TrackingResult {
    double t;
    Eigen::Vector2d true_pos, obs_pos, est_pos;
    double pos_error;
};

int main() {
    std::mt19937 rng(42);
    std::normal_distribution<double> noise(0.0, 1.0);

    double dt = 0.1;  // 100ms
    KalmanFilter kf(dt, 0.01, 0.25);

    // 真实初始状态：位置 (0,0)，速度 (2, 1) m/s
    Eigen::Vector2d true_pos(0, 0);
    Eigen::Vector2d true_vel(2.0, 1.0);

    // 初始化滤波器
    kf.init(true_pos);

    std::cout << std::fixed << std::setprecision(3);
    std::cout << "步骤 |  真实位置    |  观测位置    |  估计位置    | 位置误差\n";
    std::cout << "-----|--------------|--------------|--------------|--------\n";

    double meas_noise_std = 0.5;  // 观测噪声标准差（与 R 一致）
    double total_err = 0.0;

    for (int step = 1; step <= 30; ++step) {
        // 模拟真实运动（匀速，无加速度）
        true_pos += true_vel * dt;

        // 带噪声的观测
        Eigen::Vector2d obs = true_pos + meas_noise_std *
                              Eigen::Vector2d(noise(rng), noise(rng));

        // 异常值检测（Mahalanobis 距离 > 3 则认为是异常值）
        double dist = kf.mahalanobis(obs);
        bool is_outlier = (dist > 3.0);

        // 预测 + 更新
        kf.predict();
        if (!is_outlier) {
            kf.update(obs);
        }

        Eigen::Vector2d est = kf.position();
        double err = (est - true_pos).norm();
        total_err += err;

        if (step <= 10 || step == 30) {
            std::cout << std::setw(4) << step << " | "
                      << std::setw(6) << true_pos.x() << " "
                      << std::setw(6) << true_pos.y() << " | "
                      << std::setw(6) << obs.x() << " "
                      << std::setw(6) << obs.y() << " | "
                      << std::setw(6) << est.x() << " "
                      << std::setw(6) << est.y() << " | "
                      << std::setw(6) << err
                      << (is_outlier ? " [异常值排除]" : "") << "\n";
        }
    }

    std::cout << "\n平均位置估计误差: " << total_err / 30 << " m\n";
    std::cout << "估计速度: " << kf.velocity().transpose() << " m/s（真实: 2.0 1.0）\n";
    std::cout << "位置不确定性（σ）: " << kf.position_std().transpose() << " m\n";

    return 0;
}
```

---

## 7. 性能调优检查清单

### 7.1 代码层面

```cpp
// ✅ 使用固定大小类型（尺寸已知时）
Eigen::Matrix3d R;         // 而非 Eigen::MatrixXd R(3, 3);

// ✅ 预分配并复用内存
Eigen::MatrixXd result(N, N);
for (int i = 0; i < 100; ++i) {
    result.setZero();      // 不重新分配
    // ...
}

// ✅ 一次分解，多次求解
Eigen::LDLT<MatrixXd> ldlt(A);
for (auto& b : rhs_list) {
    x = ldlt.solve(b);    // 只有 O(n^2) 操作
}

// ✅ 避免别名的乘法
C.noalias() = A * B;

// ✅ 使用 .array() 做逐元素操作
MatrixXd result = M.array().exp().matrix();

// ❌ 避免在循环内构造矩阵对象
for (int i = 0; i < N; ++i) {
    Eigen::MatrixXd tmp(n, n); // 每次堆分配，很慢！
    // ...
}
// ✅ 改为：
Eigen::MatrixXd tmp(n, n);
for (int i = 0; i < N; ++i) {
    tmp.setZero();
    // ...
}

// ❌ 避免不必要的 .inverse()（直接求解更稳定更快）
x = A.inverse() * b;    // 慢，不稳定
// ✅ 改为：
x = A.lu().solve(b);

// ❌ 对大矩阵使用 .determinant()
double d = large_mat.determinant();  // 可能溢出
// ✅ 改为：
auto lu = large_mat.lu();
double log_abs_det = lu.matrixLU().diagonal().array().abs().log().sum();
```

### 7.2 常见性能陷阱

```cpp
// 陷阱1：隐式动态分配
void process(Eigen::VectorXd v) {  // ❌ 按值传递，产生拷贝
    // ...
}
void process(const Eigen::VectorXd& v) {  // ✅ 常引用
    // ...
}

// 陷阱2：对整个矩阵调用 eval()
MatrixXd a = (A + B + C).eval();  // ❌ 多余的 eval()，Eigen 已经 lazy eval

// 陷阱3：混合固定和动态（导致动态路径）
Eigen::Matrix3d A;
Eigen::MatrixXd B = A;  // ❌ 将固定大小转为动态大小，丢失编译期优化
// 正确：保持类型一致

// 陷阱4：稀疏矩阵随机插入
for (int i = 0; i < N; ++i) {
    sp.insert(rand() % n, rand() % n) = 1.0;  // ❌ 极慢
}
// 正确：先收集 triplets，一次性 setFromTriplets
```

---

## 8. 调试技巧

```cpp
// 打印矩阵形状
std::cout << "A: " << A.rows() << "×" << A.cols() << "\n";

// 检查有限性（排查 NaN/Inf）
if (!A.allFinite()) {
    std::cerr << "矩阵包含 NaN 或 Inf！\n";
}
if (A.hasNaN()) {
    std::cerr << "矩阵包含 NaN！\n";
}

// Eigen IO 格式控制
Eigen::IOFormat fmt(4, 0, ", ", "\n", "[", "]");
std::cout << A.format(fmt) << "\n";

// 科学计数法
Eigen::IOFormat sci_fmt(Eigen::StreamPrecision, 0, ", ", "\n", "", "", "[", "]");
std::cout << A.format(Eigen::IOFormat(Eigen::FullPrecision)) << "\n";

// 断言矩阵是对称的
auto check_symmetric = [](const Eigen::MatrixXd& M, double tol = 1e-10) {
    return (M - M.transpose()).norm() < tol;
};
assert(check_symmetric(cov_matrix) && "协方差矩阵必须对称！");

// 断言矩阵是正定的
auto check_positive_definite = [](const Eigen::MatrixXd& M) {
    Eigen::LDLT<Eigen::MatrixXd> ldlt(M);
    return ldlt.info() == Eigen::Success && ldlt.isPositive();
};
```

---

## 小结：全系列知识图谱

```
Eigen 知识体系
├── 基础类型
│   ├── Matrix<Scalar, Rows, Cols>
│   ├── 固定大小（Matrix3d）vs 动态（MatrixXd）
│   └── Map：零拷贝映射外部内存
│
├── 矩阵操作
│   ├── 块操作（block, head, tail, topRows...）
│   ├── 逐元素（.array(), cwiseMax, select）
│   └── 归约（sum, colwise, rowwise, broadcast）
│
├── 线性方程组求解
│   ├── 直接法：LU, Cholesky(LLT/LDLT), QR
│   ├── 最小二乘：ColPivHouseholderQR, SVD
│   └── 正则化：Ridge, Weighted LS
│
├── 矩阵分解与分析
│   ├── 特征值：EigenSolver, SelfAdjointEigenSolver
│   ├── SVD：JacobiSVD, BDCSVD
│   └── 应用：PCA, 低秩近似, 伪逆
│
├── 几何变换（Geometry）
│   ├── 旋转：Matrix3d, AngleAxisd, Quaterniond
│   ├── 刚体变换：Isometry3d（4×4 变换矩阵）
│   └── 插值：SLERP
│
├── 稀疏矩阵
│   ├── 构建：Triplet → setFromTriplets
│   ├── 直接法：SimplicialLDLT, SparseLU
│   └── 迭代法：CG, BiCGSTAB + 预条件子
│
└── 性能优化
    ├── 表达式模板（懒求值）
    ├── noalias()：避免临时对象
    ├── SIMD + -march=native
    └── BLAS/LAPACK 链接
```

| 篇章 | 核心内容 | 关键 API |
|---|---|---|
| 第一篇 | 安装、类型系统、第一个程序 | `Matrix3d`、`MatrixXd`、`Map` |
| 第二篇 | 初始化、块操作、Array、归约 | `block()`、`.array()`、`colwise()` |
| 第三篇 | 方程求解、LU/Cholesky/QR、最小二乘 | `ldlt().solve()`、`colPivHouseholderQr()` |
| 第四篇 | 特征值/SVD、旋转/四元数/刚体变换 | `SelfAdjointEigenSolver`、`Quaterniond`、`Isometry3d` |
| 第五篇 | 稀疏矩阵、迭代法、性能优化、KF 实战 | `SparseMatrix`、`ConjugateGradient`、`noalias()` |
