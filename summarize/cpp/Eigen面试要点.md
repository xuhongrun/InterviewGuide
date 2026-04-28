# Eigen 面试要点

> Eigen 是 C++ / 机器人 / 自动驾驶岗位的高频考点。
> 本篇精选 15 道**真实面试**中常被追问的题目，并给出可直接背诵的答案。
> 配套阅读：[cpp/eigen/](../../cpp/eigen/)

---

## 1. 表达式模板（Expression Templates）的原理与好处？为什么 `auto` 危险？

**原理**：Eigen 把矩阵运算重载为返回**惰性表达式对象**而非具体矩阵。每个二元运算（`+`、`*` 等）返回一个模板类（如 `CwiseBinaryOp`、`Product`），内部只持有操作数的引用，并不计算结果。直到这个表达式被赋值给一个 `Matrix` 对象时，整棵表达式树才被遍历一次、合并到一个循环中求值。

**好处**：

1. **零临时对象**：`y = A*x + B*z + c` 在 NumPy / 朴素 C++ 实现里要分配 3~4 个临时矩阵，Eigen 直接合并成一个 for 循环。
2. **SIMD 友好**：合并后的循环更容易被向量化。
3. **编译期形状/类型检查**：尺寸不匹配在 Debug 下立即断言。

**`auto` 陷阱**：

```cpp
auto C = A * B;      // C 不是 MatrixXd，是 Product<...>
```

C 内部只持有 A、B 的引用：
- 每次访问 `C(i,j)` 都会重算一次 `A*B`。
- 若 A、B 是临时表达式（如 `(A+B).row(0)`），生命周期结束后 C 引用悬空 → UB。

**记法**：Eigen 表达式可以**声明出来**但**不要长存**。需要保留结果时显式写类型，或 `.eval()`。

---

## 2. 固定大小 vs 动态大小怎么选？为什么固定大小更快？

**固定大小**（`Matrix3d`, `Vector4f`）：
- **栈分配**，无 `new`/`delete` 开销。
- 编译期已知尺寸 → **循环可完全展开**。
- SIMD 对齐由编译器保证。

**动态大小**（`MatrixXd`, `VectorXd`）：
- 堆分配；尺寸只能运行时确定。
- 通用循环，不能展开；但仍受益于 SIMD。

**选择规则**：
- ≤ 16×16 且尺寸编译期已知 → **固定大小**。
- > 16×16 或尺寸不确定 → **动态大小**（避免栈溢出）。
- 部分维度已知（如 N×3 点云）→ `Matrix<double, Dynamic, 3>` 混合模式。

性能差异在小矩阵密集运算下可达 **3~10 倍**。

---

## 3. `noalias()` 解决什么问题？什么时候不能用？

Eigen 默认假设赋值左右两侧**可能存在内存重叠**（aliasing），会先把右侧求值到临时变量，再赋给左侧。这个临时变量对矩阵乘法尤其昂贵。

**不存在重叠时**用 `noalias()` 绕过临时对象：

```cpp
C.noalias() = A * B;       // 直接写到 C
C.noalias() += A * B;      // 累加，更常见
```

**禁用场景**：

```cpp
A.noalias() = A * B;       // 错！A 既是输出又是输入
A.noalias() = A.transpose();  // 错！转置和原矩阵共享内存
```

**经验法则**：左侧出现在右侧任何位置时，不要用 `noalias()`。`+=` / `-=` / `*=` 时如果左侧不出现在右侧的乘法链里，可以放心加。

---

## 4. `Map` 是零拷贝吗？生命周期注意点？

是。`Eigen::Map` 让 Eigen 类型直接「指向」一段已有内存，不分配新内存：

```cpp
double arr[6] = {1,2,3,4,5,6};
Eigen::Map<Eigen::Matrix<double, 2, 3>> M(arr);   // 共享 arr
M(0, 0) = 99;       // arr[0] 也变成 99
```

**注意点**：
1. **生命周期**：底层指针失效时 Map 立即悬空。绝不能 Map 一个临时变量。
2. **存储顺序**：默认列主序。映射 C 二维数组、OpenCV `cv::Mat` 这种行主序内存时，必须用 `Eigen::RowMajor`。
3. **对齐**：固定大小 Map 要求指针对齐到 16/32 字节，否则用 `Map<..., Unaligned>` 或 `Map<..., 0>`。
4. **Stride**：用 `Eigen::Stride<>` 支持非连续步长，如取 `cv::Mat` 的 ROI。

---

## 5. 为什么要 `EIGEN_MAKE_ALIGNED_OPERATOR_NEW`？C++17 之后还需要吗？

固定大小 Eigen 类型（如 `Matrix4d`）按 SIMD 边界（16 / 32 字节）对齐。但 C++17 之前的 `operator new` **只保证 `alignof(std::max_align_t)`**（通常 8 字节），堆分配后地址不对齐 → SSE / AVX 崩。

**经典坑**：

```cpp
struct Foo {
    Eigen::Matrix4d M;        // 需要 16 字节对齐
};
auto* f = new Foo;            // C++17 前：可能未对齐 → SIGSEGV
```

**两类解法**：

1. 类内加 `EIGEN_MAKE_ALIGNED_OPERATOR_NEW` 宏，让该类的 `new` 走对齐分配。
2. `std::vector<Eigen::Matrix4d>` 用 `Eigen::aligned_allocator`。

**C++17 之后**：`new` 已能感知 `alignas(T)` 的 over-aligned 类型，自动走对齐路径。Eigen 3.4 在满足条件时会**自动屏蔽**这些宏的需求。

**结论**：现代代码（C++17 + Eigen 3.4+）大多数情况下不需要再写这些宏；但写库代码、跨编译器、跨 ABI 时仍建议加上保险。

---

## 6. `std::vector<Eigen::Matrix4d>` 为什么会崩？

同上一题——`std::allocator` 默认对齐 8 字节，存放 `Matrix4d`（要求 16 字节对齐）时元素地址错位，触发 SIMD 崩溃。

**解决**：

```cpp
#include <Eigen/StdVector>
std::vector<Eigen::Matrix4d, Eigen::aligned_allocator<Eigen::Matrix4d>> poses;
```

或使用 `Eigen::Isometry3d`（同样的问题，同样的解法）。

C++17 之后此问题在主流编译器上已经消失，但跨平台、嵌入式工具链上仍可能踩到。

---

## 7. 求解 `Ax = b`：LU、Cholesky、QR、SVD 怎么选？

| 矩阵性质 | 首选 | 时间复杂度 |
|---|---|---|
| 对称正定（SPD） | `LLT` (Cholesky) | $\frac{1}{3}n^3$ |
| 对称半正定 | `LDLT` | $\frac{1}{3}n^3$ |
| 一般方阵可逆 | `PartialPivLU` | $\frac{2}{3}n^3$ |
| 方阵可能奇异 / 要判秩 | `FullPivLU` | $\frac{2}{3}n^3$ |
| 任意矩阵（含非方阵） | `HouseholderQR` | $\frac{4}{3}n^3$ |
| 数值最差但精度最高 | `JacobiSVD` / `BDCSVD` | $O(n^3)$，常数大 |

**选择直觉**：能用 Cholesky 用 Cholesky；非对称正定方阵用 LU；超定 / 欠定 / 病态用 QR；要做秩判断、最小二乘最稳妥用 SVD。

**复用**：分解器对象可以保留，对相同 A、不同 b 反复 `solve(b)`：

```cpp
auto llt = A.llt();
auto x1  = llt.solve(b1);
auto x2  = llt.solve(b2);   // 不重新分解
```

---

## 8. `Quaternion` 的存储顺序坑

| 来源 | 顺序 |
|---|---|
| `Eigen::Quaterniond(w, x, y, z)` 构造 | (w, x, y, z) |
| `q.coeffs()` 返回 / 内存布局 | **(x, y, z, w)** |
| `geometry_msgs::Quaternion` | (x, y, z, w) |
| Ceres `QuaternionParameterization` | (w, x, y, z) |
| Ceres `EigenQuaternionParameterization` | (x, y, z, w) ← 与 Eigen 一致 |

跨库传四元数时一定要确认顺序，否则旋转结果天差地别。

---

## 9. `Isometry3d` vs `Matrix4d` 的区别

`Isometry3d` 是「带几何约束」的 4×4 变换：

- 只允许**刚体变换**（旋转 + 平移），不含缩放剪切。
- `inverse()` 是 $O(1)$ 的解析逆（$T^{-1} = [R^T, -R^T t]$），而 `Matrix4d::inverse()` 走通用 LU。
- 与 `Vector3d` 直接相乘自动处理齐次坐标。
- 链式乘法返回类型保持为 `Isometry3d`。

SLAM、ROS、机器人代码都应优先用 `Isometry3d`，性能和数值稳定性都更好。

---

## 10. `JacobiSVD` vs `BDCSVD` 怎么选？

两者都是 SVD：

- **`JacobiSVD`**：Jacobi 旋转，**小矩阵**（< 16×16）下最精确，常数小但渐近 $O(n^3)$。
- **`BDCSVD`**：分治算法（divide-and-conquer），**大矩阵**（> 16×16）显著更快，精度略低但工程足够。

Eigen 3.4 起对 ≥ 16×16 默认推荐 `BDCSVD`。

---

## 11. 稀疏矩阵 CSC vs CSR 的性能差异

Eigen `SparseMatrix` 默认 **CSC（压缩列）**：

- **按列遍历快**：访问一列只需读连续段。
- 矩阵-向量乘 $y = Ax$ 在 CSC 下是 saxpy 模式，cache 友好。
- 矩阵-向量乘 $y = A^T x$ 等价于 CSR 上的常规乘法。

需要按行频繁访问时切换 `SparseMatrix<double, RowMajor>`。

**插入元素**用 `Triplet` 批量构造再 `setFromTriplets()`，远快于反复 `insert()`。

---

## 12. 转置别名问题、`transposeInPlace()` 的限制

```cpp
A = A.transpose();           // ❌ UB：A 同时是源和目的
A = A.transpose().eval();    // ✅
A.transposeInPlace();        // ✅，但仅适用于方阵或元素总数不变的尺寸
```

`transposeInPlace()` 对非方阵会**重新分配**，并不真的「原地」。对小固定大小矩阵才是真正的零分配交换。

---

## 13. Debug 模式断言关闭对性能的影响

Eigen 内部包含大量 `eigen_assert`（尺寸匹配、对齐、秩等检查）。

```bash
g++ -O3 -DNDEBUG ...   # Release，断言关闭
g++ -g  -O0       ...   # Debug，断言开启
```

工程经验：
- Debug 下断言占总运行时间 **5%~30%**，矩阵越小相对开销越大。
- Release 必须 `-DNDEBUG`，否则性能可能比 NumPy 还慢。
- CI / 测试用例建议保留断言；生产部署版本去掉。

---

## 14. `Eigen::Ref<>` 是什么？为什么写库函数推荐用？

写函数接收矩阵的三种方式：

```cpp
void f1(const MatrixXd& M);                          // 拒绝 block / Map / 表达式
template <class D> void f2(const MatrixBase<D>& M);  // 万能但编译爆炸 + 无法分离
void f3(const Eigen::Ref<const MatrixXd>& M);        // ⭐ 兼顾两者
```

`Ref` 内部存指针 + 步长，能接受 `MatrixXd`、`Map`、`block`、转置等；接口干净；不强制模板化。

**注意**：`Ref<MatrixXd>` 默认要求列主序连续；不连续视图会触发隐式拷贝。需要任意 stride 用 `Ref<MatrixXd, 0, Stride<Dynamic, Dynamic>>`。

---

## 15. Eigen 何时自动并行？怎么和外层 OpenMP 共存？

**自动并行**：编译开 `-fopenmp` 后，Eigen 在以下场景启用多线程：
- 大尺寸矩阵-矩阵乘法（> 阈值，约 32×32）。
- 部分稀疏分解（`SimplicialLDLT` 等）。
- 不并行：分解器的 `solve()`、向量加减、逐元素运算。

**控制 API**：

```cpp
Eigen::setNbThreads(n);     // 显式设置线程数
Eigen::nbThreads();         // 查询
// 编译期完全禁用：-DEIGEN_DONT_PARALLELIZE
```

**外层 OpenMP 嵌套坑**：

```cpp
#pragma omp parallel for     // M 个线程
for (...) {
    C = A * B;               // Eigen 又起 N 个线程 → M*N 线程，性能反降
}
```

**正确做法**：进入并行区前 `Eigen::setNbThreads(1)`，让外层独占并行；或编译时关闭 Eigen 并行。

---

## 加分题：常见数值健壮性 API

```cpp
A.isApprox(B, 1e-9);        // 浮点近似相等
A.allFinite();               // 不含 NaN/Inf
A.hasNaN();                  // 含 NaN
A.isZero(eps);               // 近似全零
A.isIdentity();              // 近似单位阵
A.isUnitary();               // 近似正交矩阵
```

写卡尔曼滤波、优化器时强烈建议在每步加 `assert(x.allFinite())`，能在 NaN 第一次出现时就抓到。

---

## 推荐阅读顺序

1. [Eigen 第一篇：入门与基本类型](../../cpp/eigen/Eigen_01_入门与基本类型.md)
2. [Eigen 第二篇：矩阵与向量操作详解](../../cpp/eigen/Eigen_02_矩阵与向量操作详解.md)
3. [Eigen 第三篇：线性方程组求解与矩阵分解](../../cpp/eigen/Eigen_03_线性方程组求解与矩阵分解.md)
4. [Eigen 第四篇：特征值分解、SVD 与几何变换](../../cpp/eigen/Eigen_04_特征值分解SVD与几何变换.md)
5. [Eigen 第五篇：稀疏矩阵、性能优化与工程实战](../../cpp/eigen/Eigen_05_稀疏矩阵性能优化与工程实战.md)
6. [Eigen 第六篇：ROS / SLAM 生态互操作](../../cpp/eigen/Eigen_06_ROS_SLAM生态互操作.md)
7. [Eigen 第七篇：unsupported 模块与非线性优化](../../cpp/eigen/Eigen_07_unsupported模块与非线性优化.md)
