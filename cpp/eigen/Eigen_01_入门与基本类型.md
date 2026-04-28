# Eigen C++ 线性代数库（一）：入门与基本类型

> **系列导航**
> - **第一篇：入门与基本类型** ← 当前
> - 第二篇：矩阵与向量操作详解
> - 第三篇：线性方程组求解与矩阵分解
> - 第四篇：特征值分解、SVD 与几何变换
> - 第五篇：稀疏矩阵、性能优化与工程实战
> - 第六篇：ROS / SLAM 生态互操作
> - 第七篇：unsupported 模块与非线性优化

---

## 1. 什么是 Eigen？

Eigen 是一个开源的 C++ 模板库，专门用于**线性代数**运算，包括矩阵、向量、数值求解器及相关算法。它在学术界和工业界均被广泛采用：

- **机器人领域**：ROS/ROS2 中的几何变换、运动规划
- **计算机视觉**：OpenCV 内部大量使用 Eigen；SLAM 框架（ORB-SLAM3、Cartographer）直接暴露 Eigen 接口
- **机器学习**：TensorFlow 的早期版本、Ceres Solver、g2o 等均以 Eigen 为核心
- **自动驾驶**：传感器融合、卡尔曼滤波、点云处理（PCL）

### 1.1 核心设计理念

**表达式模板（Expression Templates）**

Eigen 的核心黑魔法。它通过 C++ 模板元编程将矩阵运算表达为惰性求值的表达式树，在赋值时一次性计算，避免中间临时对象的产生：

```cpp
// 数学上等价的两种写法，Eigen 在底层合并为一个循环
VectorXd y = A * x + B * z + c;  // 不产生临时对象，效率极高
```

**SIMD 自动向量化**

Eigen 会根据编译目标 CPU 自动使用 SSE2/SSE4、AVX/AVX2、NEON（ARM）等 SIMD 指令集，对齐内存确保向量化效率最大化。

**固定大小 vs 动态大小**

Eigen 同时支持编译期确定大小（栈分配）和运行期确定大小（堆分配），根据场景选择可获得截然不同的性能。

---

## 2. 安装

### 2.1 包管理器安装（最简单）

```bash
# Ubuntu / Debian
sudo apt install libeigen3-dev

# macOS（Homebrew）
brew install eigen

# Arch Linux
sudo pacman -S eigen

# 验证安装路径
pkg-config --cflags eigen3
# 输出类似：-I/usr/include/eigen3
```

### 2.2 从源码安装（获取最新版本）

```bash
git clone https://gitlab.com/libeigen/eigen.git
cd eigen
git checkout 3.4.0  # 推荐使用稳定版本

# 方式A：拷贝头文件（最简单，适合嵌入项目）
cp -r Eigen /your/project/include/

# 方式B：系统安装
mkdir build && cd build
cmake ..
sudo make install
```

### 2.3 CMake 集成（推荐方式）

```cmake
cmake_minimum_required(VERSION 3.14)
project(EigenDemo CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 查找已安装的 Eigen3
find_package(Eigen3 3.4 REQUIRED NO_MODULE)

add_executable(demo main.cpp)

# 链接 Eigen3（仅头文件，自动添加 include 路径）
target_link_libraries(demo PRIVATE Eigen3::Eigen)

# 性能优化选项（开发阶段去掉 -DNDEBUG）
target_compile_options(demo PRIVATE
    -O3
    -march=native
    # -DNDEBUG  # 关闭 Eigen 内部断言（生产环境）
)
```

**使用 FetchContent（无需预安装，适合 CI 环境）：**

```cmake
include(FetchContent)
FetchContent_Declare(
    Eigen3
    GIT_REPOSITORY https://gitlab.com/libeigen/eigen.git
    GIT_TAG        3.4.0
    GIT_SHALLOW    TRUE
)
FetchContent_MakeAvailable(Eigen3)

target_link_libraries(demo PRIVATE Eigen3::Eigen)
```

---

## 3. 头文件模块

Eigen 按功能分为若干模块，可以按需引入：

| 头文件 | 包含内容 |
|---|---|
| `<Eigen/Dense>` | **最常用**：矩阵、向量、LU/QR/Cholesky 分解等全家桶 |
| `<Eigen/Core>` | 矩阵/向量基础类（不含分解器） |
| `<Eigen/Geometry>` | 旋转矩阵、四元数、仿射变换 |
| `<Eigen/Eigenvalues>` | 特征值分解 |
| `<Eigen/Sparse>` | 稀疏矩阵 |
| `<Eigen/SparseCholesky>` | 稀疏 Cholesky 分解 |
| `<Eigen/SparseLU>` | 稀疏 LU 分解 |
| `<Eigen/IterativeLinearSolvers>` | 共轭梯度等迭代求解器 |
| `<Eigen/SVD>` | SVD 分解 |

> 初学阶段直接用 `<Eigen/Dense>` 即可，它包含了绝大多数需要的功能。

---

## 4. 核心类型系统

### 4.1 Matrix 模板类

Eigen 所有矩阵和向量类型都基于同一个模板类：

```cpp
template<
    typename Scalar,       // 元素类型：double, float, int, std::complex<double>...
    int Rows,              // 行数：具体数字 或 Eigen::Dynamic
    int Cols,              // 列数：具体数字 或 Eigen::Dynamic
    int Options,           // 存储顺序：ColMajor（默认）或 RowMajor
    int MaxRows,           // 最大行数（用于固定上限的动态矩阵）
    int MaxCols            // 最大列数
>
class Matrix;
```

### 4.2 类型别名命名规律

```
Matrix + [行数|X] + [列数|X（可省略表示列向量）] + 标量类型
```

| 类型别名 | 展开 | 含义 |
|---|---|---|
| `Matrix2d` | `Matrix<double, 2, 2>` | 2×2 double 矩阵（固定） |
| `Matrix3f` | `Matrix<float, 3, 3>` | 3×3 float 矩阵（固定） |
| `Matrix4d` | `Matrix<double, 4, 4>` | 4×4 double 矩阵（固定） |
| `MatrixXd` | `Matrix<double, Dynamic, Dynamic>` | 动态大小 double 矩阵 |
| `MatrixXf` | `Matrix<float, Dynamic, Dynamic>` | 动态大小 float 矩阵 |
| `MatrixXi` | `Matrix<int, Dynamic, Dynamic>` | 动态大小 int 矩阵 |
| `Vector2d` | `Matrix<double, 2, 1>` | 2D double 列向量（固定）|
| `Vector3d` | `Matrix<double, 3, 1>` | 3D double 列向量（固定）|
| `Vector4f` | `Matrix<float, 4, 1>` | 4D float 列向量（固定）|
| `VectorXd` | `Matrix<double, Dynamic, 1>` | 动态大小 double 列向量 |
| `RowVector3d` | `Matrix<double, 1, 3>` | 3D double 行向量（固定）|

**标量类型后缀：**

| 后缀 | 类型 |
|---|---|
| `d` | `double` |
| `f` | `float` |
| `i` | `int` |
| `l` | `long` |
| `cd` | `std::complex<double>` |
| `cf` | `std::complex<float>` |

---

## 5. 第一个完整程序

```cpp
#include <iostream>
#include <Eigen/Dense>

int main() {
    // ============================================================
    // 1. 固定大小矩阵（编译期确定，栈分配，速度最快）
    // ============================================================
    Eigen::Matrix3d A;

    // 逗号初始化（按行填入）
    A << 1, 2, 3,
         4, 5, 6,
         7, 8, 9;

    std::cout << "=== 固定大小矩阵 A (3x3 double) ===\n";
    std::cout << A << "\n\n";

    // ============================================================
    // 2. 固定大小向量
    // ============================================================
    Eigen::Vector3d v(1.0, 2.0, 3.0);
    std::cout << "=== 列向量 v ===\n";
    std::cout << v << "\n\n";

    // 矩阵-向量乘法
    Eigen::Vector3d result = A * v;
    std::cout << "=== A * v ===\n";
    std::cout << result << "\n\n";

    // ============================================================
    // 3. 动态大小矩阵（运行期确定，堆分配）
    // ============================================================
    Eigen::MatrixXd B(2, 3);  // 构造时指定大小
    B << 1, 2, 3,
         4, 5, 6;

    std::cout << "=== 动态矩阵 B (2x3) ===\n";
    std::cout << B << "\n";
    std::cout << "行数: " << B.rows() << "，列数: " << B.cols()
              << "，元素总数: " << B.size() << "\n\n";

    // ============================================================
    // 4. 基本信息查询
    // ============================================================
    std::cout << "=== 矩阵属性 ===\n";
    std::cout << "A 的行数: " << A.rows() << "\n";
    std::cout << "A 的列数: " << A.cols() << "\n";
    std::cout << "A(1,2) = " << A(1, 2) << "\n";  // 第2行第3列，从0开始
    std::cout << "A 的 Frobenius 范数: " << A.norm() << "\n";

    return 0;
}
```

**编译与运行：**
```bash
g++ -std=c++17 -O2 -I/usr/include/eigen3 main.cpp -o demo
./demo
```

**输出：**
```
=== 固定大小矩阵 A (3x3 double) ===
1 2 3
4 5 6
7 8 9

=== 列向量 v ===
1
2
3

=== A * v ===
14
32
50

=== 动态矩阵 B (2x3) ===
1 2 3
4 5 6
行数: 2，列数: 3，元素总数: 6

=== 矩阵属性 ===
A 的行数: 3
A 的列数: 3
A(1,2) = 6
A 的 Frobenius 范数: 16.8819
```

---

## 6. 固定大小 vs 动态大小：深入对比

### 6.1 内存分配

```cpp
// 固定大小：栈分配，没有堆分配开销
Eigen::Matrix<double, 4, 4> M_fixed;   // 128 字节直接在栈上

// 动态大小：堆分配，有 new/delete 开销
Eigen::MatrixXd M_dynamic(4, 4);       // 在堆上分配 128 字节 + 控制块开销
```

### 6.2 性能差异

```cpp
#include <chrono>
#include <Eigen/Dense>

void benchmark() {
    const int N = 1000000;

    // 固定大小矩阵乘法（编译器可完全展开循环）
    auto t1 = std::chrono::high_resolution_clock::now();
    for (int i = 0; i < N; ++i) {
        Eigen::Matrix3d A = Eigen::Matrix3d::Random();
        Eigen::Matrix3d B = Eigen::Matrix3d::Random();
        Eigen::Matrix3d C = A * B;  // 编译期知道大小，循环完全展开
        (void)C;
    }
    auto t2 = std::chrono::high_resolution_clock::now();

    // 动态大小矩阵乘法
    auto t3 = std::chrono::high_resolution_clock::now();
    for (int i = 0; i < N; ++i) {
        Eigen::MatrixXd A = Eigen::MatrixXd::Random(3, 3);
        Eigen::MatrixXd B = Eigen::MatrixXd::Random(3, 3);
        Eigen::MatrixXd C = A * B;  // 运行时才知道大小，有额外开销
        (void)C;
    }
    auto t4 = std::chrono::high_resolution_clock::now();

    auto us_fixed   = std::chrono::duration_cast<std::chrono::milliseconds>(t2 - t1).count();
    auto us_dynamic = std::chrono::duration_cast<std::chrono::milliseconds>(t4 - t3).count();

    std::cout << "固定大小 3x3 乘法 x" << N << ": " << us_fixed   << " ms\n";
    std::cout << "动态大小 3x3 乘法 x" << N << ": " << us_dynamic << " ms\n";
    // 固定大小通常快 3~10 倍
}
```

### 6.3 选择原则

| 情形 | 推荐类型 | 原因 |
|---|---|---|
| 矩阵尺寸编译期已知且 ≤ 约 12×12 | 固定大小 | 栈分配 + 循环展开，最快 |
| 矩阵尺寸编译期已知但很大（> 16×16）| 动态大小 | 避免栈溢出 |
| 矩阵尺寸运行期才能确定 | 动态大小 | 别无选择 |
| 3D 旋转、变换（机器人/游戏）| 固定大小 4×4、3×3 | 最高性能 |
| 传感器数据处理（N 个点）| 动态大小 N×3 | 尺寸取决于输入 |

---

## 7. 常用构造方式汇总

```cpp
#include <Eigen/Dense>
using namespace Eigen;

// ---- 固定大小 ----
Matrix3d A;             // 未初始化（内容随机）
Matrix3d Z = Matrix3d::Zero();      // 全零矩阵
Matrix3d O = Matrix3d::Ones();      // 全一矩阵
Matrix3d I = Matrix3d::Identity();  // 单位矩阵
Matrix3d R = Matrix3d::Random();    // 随机矩阵（[-1, 1]）
Matrix3d C = Matrix3d::Constant(3.14); // 常数矩阵

// ---- 动态大小 ----
MatrixXd M1(3, 4);                      // 3行4列，未初始化
MatrixXd M2 = MatrixXd::Zero(3, 4);     // 3行4列，全零
MatrixXd M3 = MatrixXd::Ones(3, 4);     // 3行4列，全一
MatrixXd M4 = MatrixXd::Identity(3, 3); // 3x3 单位矩阵
MatrixXd M5 = MatrixXd::Random(3, 4);   // 3行4列，随机

// ---- 向量 ----
Vector3d v1(1.0, 2.0, 3.0);            // 直接初始化（仅限小尺寸）
VectorXd v2 = VectorXd::Zero(5);        // 5维全零向量
VectorXd v3 = VectorXd::Ones(5);        // 5维全一向量
VectorXd v4 = VectorXd::LinSpaced(5, 0.0, 1.0); // [0, 0.25, 0.5, 0.75, 1.0]

// ---- 对角矩阵 ----
Vector3d diag(1.0, 2.0, 3.0);
Matrix3d D = diag.asDiagonal();
// D =
// 1 0 0
// 0 2 0
// 0 0 3

// ---- 逗号初始化 ----
Matrix<double, 2, 3> M6;
M6 << 1, 2, 3,   // 按行填入
      4, 5, 6;

// 用其他向量/矩阵拼接
Vector4d v_concat;
Vector2d a(1, 2), b(3, 4);
v_concat << a, b;  // [1, 2, 3, 4]
```

---

## 8. 命名空间与常见写法

```cpp
// 方式1：全命名空间（推荐，清晰）
Eigen::Matrix3d A;
Eigen::Vector3d v;

// 方式2：using 声明（头文件中禁止，源文件可用）
using Eigen::Matrix3d;
using Eigen::Vector3d;
Matrix3d A;
Vector3d v;

// 方式3：using namespace（不推荐，尤其在头文件中）
using namespace Eigen;
Matrix3d A;

// 常用的 Dynamic 常量
// Eigen::Dynamic == -1，表示运行期确定大小
Eigen::Matrix<double, Eigen::Dynamic, 3> M;  // 行数动态，列数固定为3
```

---

## 9. Eigen 与标准库互操作

```cpp
#include <vector>
#include <array>
#include <Eigen/Dense>

// std::vector<double> → Eigen::VectorXd（用 Map，零拷贝）
std::vector<double> std_vec = {1.0, 2.0, 3.0, 4.0, 5.0};
Eigen::Map<Eigen::VectorXd> eigen_vec(std_vec.data(), std_vec.size());
std::cout << eigen_vec.sum() << "\n";  // 15

// std::array → Eigen::Vector（零拷贝）
std::array<float, 3> arr = {1.f, 2.f, 3.f};
Eigen::Map<Eigen::Vector3f> v(arr.data());

// Eigen → std::vector（需要拷贝）
Eigen::VectorXd ev = Eigen::VectorXd::Random(5);
std::vector<double> sv(ev.data(), ev.data() + ev.size());

// 二维数组 → Eigen 矩阵（注意行/列主序）
double raw[3][4] = {{1,2,3,4},{5,6,7,8},{9,10,11,12}};
// C 二维数组是行主序
using RowMajorMat = Eigen::Matrix<double, 3, 4, Eigen::RowMajor>;
Eigen::Map<RowMajorMat> mat(raw[0]);
std::cout << mat << "\n";
```

---

## 10. 常见错误与调试

### 10.1 尺寸不匹配（运行时断言）

```cpp
Eigen::Matrix3d A;
Eigen::Matrix2d B;

// 以下代码会在 Debug 模式触发断言（不是编译错误！）
// auto C = A * B;  // 错误：3x3 * 2x2 不合法

// 动态大小同样会在运行时检查
Eigen::MatrixXd X(3, 3), Y(2, 2);
// auto Z = X * Y;  // 触发 Eigen 断言："invalid matrix product"
```

**启用断言（默认 Debug 模式已启用）：**
```bash
# Debug 模式：保留断言
g++ -g -DEIGEN_NO_NDEBUG main.cpp -o demo

# Release 模式：关闭断言（更快）
g++ -O3 -DNDEBUG main.cpp -o demo
```

### 10.2 别名问题（Aliasing）

```cpp
Eigen::MatrixXd A = Eigen::MatrixXd::Random(3, 3);

// 危险：A 的右侧引用了 A 本身，结果未定义
// A = A.transpose();          // 错误！

// 正确做法1：eval() 强制求值产生临时变量
A = A.transpose().eval();

// 正确做法2：就地转置（原地操作，适合方阵）
A.transposeInPlace();
```

### 10.3 初始化警告

```cpp
// 固定大小矩阵默认不初始化（包含垃圾值）
Eigen::Matrix3d M;
std::cout << M;  // 未定义行为！可能输出任何值

// 安全做法
Eigen::Matrix3d M2 = Eigen::Matrix3d::Zero();
Eigen::Matrix3d M3;
M3.setZero();  // 等价写法
```

---

## 小结

| 知识点 | 要点 |
|---|---|
| 安装 | 头文件库，`apt install` 或 CMake `FetchContent` |
| 核心类型 | `Matrix<Scalar, Rows, Cols>`，别名如 `Matrix3d`、`VectorXd` |
| 固定 vs 动态 | 固定大小性能更高，动态大小更灵活 |
| 初始化方式 | `Zero()`、`Identity()`、`Random()`、逗号初始化 |
| 互操作 | `Eigen::Map` 零拷贝映射裸指针/std容器 |
| 调试 | Debug 模式有断言，注意别名问题用 `eval()` 或 `InPlace()` |

下一篇将深入讲解矩阵与向量的各种操作：块操作、逐元素运算、广播、归约等。
