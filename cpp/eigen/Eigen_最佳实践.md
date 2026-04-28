# Eigen 最佳实践

> Eigen C++ 线性代数库的工程化最佳实践：覆盖类型选择、`auto` 陷阱、`Ref` 接口、内存对齐、性能、稀疏矩阵、与 ROS / OpenCV 互操作、数值健壮性、调试。
>
> 配套：[Eigen 入门](Eigen_01_入门与基本类型.md) / [矩阵与向量操作](Eigen_02_矩阵与向量操作详解.md) / [线性方程组与分解](Eigen_03_线性方程组求解与矩阵分解.md) / [稀疏矩阵性能与工程](Eigen_05_稀疏矩阵性能优化与工程实战.md) / [ROS/SLAM 互操作](Eigen_06_ROS_SLAM生态互操作.md)

---

## 一、类型选择

### 1.1 固定大小 vs 动态大小

| 选择 | 用法 |
|------|------|
| **固定大小**（`Vector3d` / `Matrix4d` / `Matrix<double, 6, 6>`） | 维度 ≤ 16 且**编译期已知** |
| **动态大小**（`VectorXd` / `MatrixXd`） | 维度运行时确定或较大 |

**经验值**：
- 维度 ≤ 4：**强烈**用固定大小（Eigen 会展开循环 + SIMD）；
- 维度 5~16：固定大小通常更快但可读性差；
- 维度 > 16：必须动态大小，否则栈溢出 / 编译爆炸。

**栈分配警告**：固定大小矩阵存在栈上，不要把 `Matrix<double, 1000, 1000>` 当成员或局部变量。

### 1.2 标量类型

- 默认 **double**：精度 + 性能折衷最好；
- 嵌入式 / GPU 用 **float**：内存减半，SIMD 通道翻倍；
- 整数计算少用 Eigen（性能不如手写）；
- 复数：`MatrixXcd`（FFT、特征分解需要）。

### 1.3 Row-Major vs Col-Major

- **Eigen 默认列主序**（与 Fortran/MATLAB 一致）；
- 与 OpenCV / NumPy 互操作时常需 **行主序**：
  ```cpp
  using RowMajorMatrix = Eigen::Matrix<double, Dynamic, Dynamic, Eigen::RowMajor>;
  ```
- **不要混用**：同一计算链路全部统一存储顺序，否则隐式转置很慢。

---

## 二、`auto` 陷阱（最高频翻车点）

Eigen 几乎所有运算返回**表达式模板**，不是结果：

```cpp
MatrixXd A = MatrixXd::Random(3, 3);
MatrixXd B = MatrixXd::Random(3, 3);

// ❌ 错误 1：auto 拿到表达式，每访问一次都重算
auto C = A * B;
std::cout << C(0, 0);  // 每次都跑矩阵乘法

// ❌ 错误 2：临时表达式被引用，悬空
auto row = (A + B).row(0);  // (A+B) 立即销毁

// ❌ 错误 3：转置是视图
auto T = A.transpose();
A.setZero();
std::cout << T;  // 输出全零（不是预期快照）
```

### ✅ 正确写法

```cpp
MatrixXd C = A * B;            // 显式类型 → 强制求值
auto    C2 = (A * B).eval();   // 或 .eval()
Vector3d r = (A + B).row(0);   // 显式类型，立即拷贝
MatrixXd T = A.transpose();    // 拿快照
```

> **面试要点**：「Eigen 表达式模板 + 惰性求值 + auto 推导出表达式而非结果」是 C++ 项目中仅次于悬空指针的高频崩溃源。

---

## 三、写库函数：`Eigen::Ref` 标准姿势

### ❌ 反模式

```cpp
// 只能传 MatrixXd 本体，不能传 block / Map / 转置
double frob1(const Eigen::MatrixXd& M);

// 模板版：膨胀编译时间 + 无法分离声明实现
template <typename Derived>
double frob2(const Eigen::MatrixBase<Derived>& M);
```

### ✅ 推荐：`Eigen::Ref`

```cpp
double frob(const Eigen::Ref<const Eigen::MatrixXd>& M) {
    return M.norm();
}

void scale(Eigen::Ref<Eigen::MatrixXd> M, double s) {
    M *= s;
}

// 调用：以下都 OK
frob(A);
frob(A.block(0, 0, 5, 5));
frob(A.transpose());
scale(A.col(0), 2.0);
```

注意：
- `Ref<MatrixXd>` 默认要求**列主序连续内存**，不连续会**隐式拷贝**；
- 接受任意 stride：`Ref<MatrixXd, 0, Stride<Dynamic, Dynamic>>`；
- 固定小尺寸（`Vector3d`）直接 `const Vector3d&` 更优；
- 头文件接口推荐用 `Ref`，模板放实现细节。

---

## 四、内存对齐与 STL 容器

Eigen 固定大小类型可能要求 16/32 字节对齐（SSE/AVX）：

```cpp
// ❌ 编译警告或 crash
std::vector<Eigen::Vector4d> v;        // 在某些平台 / 编译器上未对齐
std::map<int, Eigen::Matrix4d> m;

// ✅ Eigen 17+ / C++17 起多数平台已无问题，但跨平台建议显式：
std::vector<Eigen::Vector4d, Eigen::aligned_allocator<Eigen::Vector4d>> v;

// 或将 Eigen 成员的类用 EIGEN_MAKE_ALIGNED_OPERATOR_NEW
class Foo {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW
    Eigen::Matrix4d M;
};
```

更严谨：
- 头文件加 `#define EIGEN_DONT_ALIGN` 关对齐（损失性能，跨平台稳）；
- 或全用动态大小（不需对齐）；
- C++17 + Eigen 3.3.7+ 标准 STL 容器多数情况已 OK。

参考 [Eigen 官方页面](https://eigen.tuxfamily.org/dox/group__TopicStlContainers.html)。

---

## 五、性能优化

### 5.1 编译选项

```bash
# 必须开
-O2 / -O3
-DNDEBUG       # 关闭 Eigen 内部 assert（生产）
-march=native  # 让编译器用本机 SIMD（AVX2/AVX-512）
# 可选
-DEIGEN_NO_DEBUG
-DEIGEN_VECTORIZE_AVX2
```

### 5.2 `noalias()`

矩阵乘法默认创建临时变量防止别名：
```cpp
MatrixXd C(n, n);
C.noalias() = A * B;          // 直接写入 C，无临时矩阵
C.noalias() += A * B;         // 累加更典型
```

适用条件：左右两边没有公共内存。

### 5.3 表达式融合

Eigen 自动融合多个操作：
```cpp
MatrixXd D = 2.0 * A + 3.0 * B - C;  // 一次循环搞定，无中间矩阵
```

### 5.4 预分配

```cpp
MatrixXd result;
result.resize(N, N);  // 循环外预分配

for (...) {
    MatrixXd tmp = ...;
    result += tmp;  // 形状匹配不会重新分配
}
```

### 5.5 视图代替拷贝

```cpp
// ❌ 拷贝
VectorXd head_copy = v.head(100);

// ✅ 视图（前提：v 生命周期足够）
auto head_view = v.head(100);
```

### 5.6 避免

- 高频代码里反复 resize / construct 大矩阵；
- 误用 `MatrixXd` 当 4×4 矩阵（拷贝/分配开销）；
- 写循环逐元素操作而不是用 `.array()` 向量化。

详见 [稀疏矩阵性能与工程](Eigen_05_稀疏矩阵性能优化与工程实战.md)。

---

## 六、`Map`：零拷贝互操作

### 6.1 基本

```cpp
double arr[12] = {...};
Eigen::Map<Eigen::Matrix3d>     col_M(arr);              // 列主序固定
Eigen::Map<Eigen::MatrixXd>     dyn_M(arr, 3, 4);        // 列主序动态
Eigen::Map<RowMajorMatrix>      row_M(arr, 3, 4);        // 行主序

// 对 Map 的修改直接写回原数组
col_M(0,0) = 99.0;  // arr[0] = 99
```

### 6.2 与 std::vector

```cpp
std::vector<float> data(12);
Eigen::Map<Eigen::Matrix<float, 3, 4>> M(data.data());
```

### 6.3 与 OpenCV

```cpp
cv::Mat cv_mat(3, 4, CV_64F);
assert(cv_mat.isContinuous());  // 必须连续！
using RowMajorMat = Eigen::Matrix<double, Dynamic, Dynamic, RowMajor>;
Eigen::Map<RowMajorMat> em(reinterpret_cast<double*>(cv_mat.data),
                           cv_mat.rows, cv_mat.cols);
```

### 6.4 与 ROS 消息

```cpp
// sensor_msgs::msg::PointCloud2 → Eigen
const float* data = reinterpret_cast<const float*>(msg.data.data());
size_t N = msg.width * msg.height;
Eigen::Map<const Eigen::Matrix<float, 3, Eigen::Dynamic>> P(data, 3, N);
```

注意：
- 仅在原数据**连续 + 对齐**时使用 Map；
- Map 不持有内存，原数组生命周期必须 ≥ Map；
- 跨线程使用 Map 要确保读写同步。

详见 [ROS/SLAM 互操作](Eigen_06_ROS_SLAM生态互操作.md)。

---

## 七、Eigen 3.4 切片语法（NumPy 风格）

```cpp
using Eigen::seq; using Eigen::all; using Eigen::last;

MatrixXd M = MatrixXd::Random(6, 6);

auto sub  = M(seq(1, 3), all);                   // 第 1~3 行
auto last2 = M(all, seq(last - 1, last));        // 最后 2 列
auto step = M(seq(0, last, Eigen::fix<2>), all); // 步长 2

std::vector<int> idx{0, 2, 4};
auto picked = M(idx, all);

// reshape
VectorXd v = VectorXd::LinSpaced(12, 0, 11);
auto m34 = v.reshaped(3, 4);
auto flat = M.reshaped();   // 列主序拉直
```

优势：可读性接近 NumPy，编译期保留尺寸信息。

---

## 八、数值健壮性

### 8.1 浮点比较

```cpp
// ❌ 永远不要
if (A == B) { ... }

// ✅
if (A.isApprox(B, 1e-9)) { ... }
if (v.isZero(1e-12)) { ... }
```

### 8.2 NaN / Inf 检测

写卡尔曼滤波 / 优化时**强烈建议**：

```cpp
if (!X.allFinite()) {
    RCLCPP_ERROR(logger, "matrix has NaN/Inf");
    return false;
}
if (X.hasNaN()) { ... }
```

### 8.3 矩阵特性判定

```cpp
A.isIdentity();
A.isDiagonal();
A.isUpperTriangular();
A.isApprox(A.transpose());   // 对称？
```

### 8.4 条件数

求解前检查矩阵病态：
```cpp
JacobiSVD<MatrixXd> svd(A);
double cond = svd.singularValues()(0) /
              svd.singularValues()(svd.singularValues().size()-1);
if (cond > 1e10) { /* warning */ }
```

---

## 九、矩阵分解选择

| 分解 | 适用 | API |
|------|------|-----|
| **LU** (PartialPivLU) | 一般方阵 / 求逆 | `A.partialPivLu().solve(b)` |
| **FullPivLU** | 数值稳定但慢 | `A.fullPivLu()` |
| **Cholesky** (LLT) | **正定**对称 | `A.llt().solve(b)` ⚡ 最快 |
| **LDLT** | 半正定对称 | `A.ldlt().solve(b)` |
| **QR** (HouseholderQR) | 最小二乘 / 一般矩形 | `A.householderQr().solve(b)` |
| **ColPivHQR** | 数值稳定 + 秩判定 | `A.colPivHouseholderQr()` |
| **SVD** (JacobiSVD) | 最稳但最慢 | `A.jacobiSvd(ComputeThinU \| ComputeThinV)` |
| **BDCSVD** | 大矩阵 SVD | `A.bdcSvd(...)` 推荐 |

经验：
- 求解 $Ax = b$，A 正定 → **LLT**（最快 ~3 倍 LU）；
- 最小二乘 $\min \|Ax-b\|$ → **householderQr**；
- 病态 / 秩缺失 → **ColPivHQR** 或 **BDCSVD**；
- 求逆只用于固定小尺寸：`A.inverse()`，大矩阵改求解。

详见 [线性方程组与分解](Eigen_03_线性方程组求解与矩阵分解.md)。

---

## 十、稀疏矩阵

| 实践 | 说明 |
|------|------|
| **`SparseMatrix<double>` 默认列压缩 (CSC)** | 大多数求解器要求 |
| **`reserve()` 预估非零元** | 避免反复重分配 |
| **批量 setFromTriplets** | 比 `insert()` 快 10× |
| 求解器：`SimplicialLLT` / `SimplicialLDLT`（正定对称稀疏）；`SparseLU`（一般）；`ConjugateGradient`（迭代） | 按结构选 |
| `BiCGSTAB` 非对称稀疏 | 默认迭代器 |
| `IncompleteLUT` 预条件 | 大幅加速迭代 |
| 与 SLAM g2o / Ceres 互操作 | 稀疏雅可比直接 Map |

```cpp
typedef Eigen::Triplet<double> T;
std::vector<T> triplets;
triplets.reserve(nnz);
for (...) triplets.emplace_back(i, j, val);

SparseMatrix<double> A(n, n);
A.setFromTriplets(triplets.begin(), triplets.end());
A.makeCompressed();

SimplicialLDLT<SparseMatrix<double>> solver(A);
VectorXd x = solver.solve(b);
```

详见 [稀疏矩阵性能与工程](Eigen_05_稀疏矩阵性能优化与工程实战.md)。

---

## 十一、几何变换（Geometry 模块）

```cpp
#include <Eigen/Geometry>

// 四元数
Quaterniond q(w, x, y, z);     // 注意构造顺序 w,x,y,z（与 ROS msg 顺序相反！）
q.normalize();                  // 必做
Vector3d v_rot = q * v;         // 旋转向量

// AngleAxis
AngleAxisd aa(M_PI/4, Vector3d::UnitZ());
Quaterniond q2(aa);

// Rotation matrix
Matrix3d R = q.toRotationMatrix();

// 齐次 SE(3)
Affine3d T = Translation3d(1,2,3) * q;
Vector3d p_world = T * p_local;

// 插值
Quaterniond q_mid = q1.slerp(0.5, q2);
```

**坑**：
- ROS msg 四元数顺序 `(x, y, z, w)`，Eigen 构造 `Quaterniond(w, x, y, z)` 顺序相反；
- 四元数必须**归一化**，否则旋转有缩放；
- 多个 `Affine3d` 串接前考虑**右乘 vs 左乘**约定。

详见 [ROS/SLAM 互操作](Eigen_06_ROS_SLAM生态互操作.md)、[common/数学与坐标变换基础](../../ros/common/数学与坐标变换基础.md)。

---

## 十二、调试

| 技巧 | 说明 |
|------|------|
| 输出格式 | `std::cout << M.format(IOFormat(4, 0, ", ", "\n", "[", "]"))` |
| 转 NumPy | `M.format(IOFormat(...))` 后粘到 Python 复算 |
| `Eigen::ArrayBase::isFinite()` | 找 NaN 元素 |
| Debug 模式 | 编译不要 `-DNDEBUG`，让 assert 抓 size mismatch |
| `EIGEN_NO_DEBUG` 反向开关 | 生产关 assert 提性能 |
| GDB pretty-printer | `git clone eigen` 安装 `debug/gdb/printers.py` |
| 单步打印 SVD/特征值 | 病态前兆 |

---

## 十三、与其他库互操作

| 库 | 注意 |
|----|------|
| **OpenCV** | RowMajor + 连续 + 类型对齐；用 `cv::cv2eigen` / `eigen2cv` |
| **ROS msg** | `tf2_eigen` 提供 `tf2::fromMsg` / `toMsg` |
| **NumPy（Python）** | pybind11 + `Eigen::Ref<>` 自动零拷贝 |
| **g2o / Ceres** | 雅可比直接用 Map；姿态用 `Sophus` 更安全 |
| **CUDA** | 自带 GPU 矩阵库（cuBLAS）；Eigen 仅 CPU |
| **PCL** | `pcl::PointCloud<>` 内部含 Eigen 字段，直接 .getMatrixXfMap() |

---

## 十四、常见坑速查

| 现象 | 原因 |
|------|------|
| `auto x = A * B` 重复计算 | 表达式模板，需 `.eval()` 或显式类型 |
| 跨函数传 block 性能差 | 没用 `Ref<>` |
| 程序奇怪崩溃（SIGSEGV） | 固定大小未对齐 / STL 容器无 aligned_allocator |
| `assertion failed: rows()==cols()` | 形状不匹配，开 debug |
| 矩阵求逆 NaN | 病态 / 奇异，改 SVD 或检查条件数 |
| 稀疏求解奇慢 | 没 `makeCompressed()` / 没 reserve |
| 与 OpenCV 互操作错位 | RowMajor / ColMajor 没统一 |
| 多线程数据竞争 | Eigen 默认非线程安全（Map / 共享对象） |
| 固定大小矩阵超 100×100 编译爆炸 | 改动态 |

---

## 十五、Top 20 Checklist

类型：
- [ ] 维度 ≤ 4 → 固定大小
- [ ] 标量默认 double
- [ ] 互操作明确 RowMajor / ColMajor

API：
- [ ] **不要 `auto` 接 Eigen 表达式**
- [ ] 库函数用 `Eigen::Ref<>`
- [ ] STL 容器用 `aligned_allocator` 或动态大小
- [ ] 浮点比较用 `isApprox`
- [ ] NaN/Inf 用 `allFinite()`

性能：
- [ ] `-O3 -DNDEBUG -march=native`
- [ ] `noalias()` 矩阵乘
- [ ] 循环外预分配
- [ ] 视图代替拷贝
- [ ] 大计算用 `Ref` / Map 避免拷贝

求解：
- [ ] 正定对称 → LLT
- [ ] 最小二乘 → ColPivHQR
- [ ] 病态 → BDCSVD
- [ ] 稀疏：setFromTriplets + makeCompressed

互操作：
- [ ] OpenCV 检查 isContinuous + RowMajor
- [ ] 四元数构造 (w,x,y,z) vs ROS (x,y,z,w)
- [ ] 跨进程 / 多线程不要共享 Map

---

## 十六、面试速记

1. **`auto + Eigen` 是 C++ 项目第二大崩溃源**（表达式模板 + 惰性求值）；
2. 库函数接口用 **`Eigen::Ref<const MatrixXd>`**；
3. 固定大小快但要对齐 + STL `aligned_allocator`；
4. **正定对称用 LLT**（最快），最小二乘用 QR，病态用 SVD；
5. **零拷贝**互操作靠 `Map`；OpenCV 必须 RowMajor + 连续；
6. ROS 四元数顺序 (x,y,z,w) vs Eigen (w,x,y,z) 是经典坑；
7. 高性能：`noalias` + `-O3 -DNDEBUG -march=native` + 预分配；
8. 数值健壮：`isApprox` / `allFinite` 是日常；
9. 稀疏矩阵：`Triplet + setFromTriplets + makeCompressed`；
10. Eigen 3.4 切片 `seq/all/last/reshaped` 接近 NumPy。
