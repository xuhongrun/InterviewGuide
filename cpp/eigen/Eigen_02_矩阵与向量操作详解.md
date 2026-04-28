# Eigen C++ 线性代数库（二）：矩阵与向量操作详解

> **系列导航**
> - 第一篇：入门与基本类型
> - **第二篇：矩阵与向量操作详解** ← 当前
> - 第三篇：线性方程组求解与矩阵分解
> - 第四篇：特征值分解、SVD 与几何变换
> - 第五篇：稀疏矩阵、性能优化与工程实战
> - 第六篇：ROS / SLAM 生态互操作
> - 第七篇：unsupported 模块与非线性优化

---

## 1. 矩阵初始化详解

### 1.1 工厂方法

```cpp
#include <Eigen/Dense>
using namespace Eigen;

// --- 零矩阵 ---
Matrix3d Z3  = Matrix3d::Zero();        // 固定大小
MatrixXd Zd  = MatrixXd::Zero(4, 5);   // 动态大小

// --- 全一矩阵 ---
Matrix3d O3  = Matrix3d::Ones();
MatrixXd Od  = MatrixXd::Ones(3, 3);

// --- 单位矩阵（仅方阵有意义）---
Matrix4d I4  = Matrix4d::Identity();
MatrixXd Id  = MatrixXd::Identity(5, 5);

// --- 常数矩阵 ---
Matrix3d C3  = Matrix3d::Constant(2.71828);
MatrixXd Cd  = MatrixXd::Constant(3, 4, 3.14159);

// --- 随机矩阵（元素均匀分布在 [-1, 1]）---
Matrix3d Rand3 = Matrix3d::Random();
MatrixXd Randd = MatrixXd::Random(4, 4);

// --- 线性空间向量 ---
// LinSpaced(size, low, high) 生成等间隔序列
VectorXd v = VectorXd::LinSpaced(6, 0.0, 1.0);
// 结果: [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]

// 固定大小的 LinSpaced
Vector<double, 5> v5 = Vector<double, 5>::LinSpaced(0.0, 4.0);
// 结果: [0, 1, 2, 3, 4]
```

### 1.2 就地赋值方法

```cpp
MatrixXd M(3, 3);

M.setZero();                  // 全零
M.setOnes();                  // 全一
M.setIdentity();              // 单位矩阵
M.setConstant(42.0);          // 全部设为 42
M.setRandom();                // 随机值

// 向量特有
VectorXd v(5);
v.setLinSpaced(0.0, 1.0);    // 等间隔序列
```

### 1.3 逗号初始化（Comma Initializer）

```cpp
// 基本用法：按行从左到右填入
Matrix3d A;
A << 1, 2, 3,
     4, 5, 6,
     7, 8, 9;

// 用子矩阵/向量拼接
Matrix<double, 4, 4> B;
Matrix<double, 2, 2> top_left  = Matrix<double, 2, 2>::Identity();
Matrix<double, 2, 2> top_right = Matrix<double, 2, 2>::Zero();
Matrix<double, 2, 2> bot_left  = Matrix<double, 2, 2>::Ones();
Matrix<double, 2, 2> bot_right = Matrix<double, 2, 2>::Random();

B << top_left,  top_right,
     bot_left,  bot_right;

// 向量拼接
Vector4d v;
Vector2d a(1, 2), b(3, 4);
v << a, b;    // [1, 2, 3, 4]

// 混合拼接
VectorXd w(5);
w << 0.0, v;  // [0, 1, 2, 3, 4]
```

---

## 2. 元素访问

### 2.1 单元素访问

```cpp
MatrixXd M(3, 4);
M << 1,  2,  3,  4,
     5,  6,  7,  8,
     9, 10, 11, 12;

// 二维索引（行, 列），均从 0 开始
double val = M(1, 2);     // = 7（第2行第3列）
M(0, 0) = 99;             // 修改元素

// 一维索引（按列主序展开，即先列后行）
double v0 = M(0);  // = 99（第0列第0行）
double v1 = M(1);  // = 5（第0列第1行）
double v3 = M(3);  // = 2（第1列第0行）
// 对于向量，一维索引最直观
VectorXd vec(5);
vec << 10, 20, 30, 40, 50;
double e2 = vec(2);   // = 30
double e2b = vec[2];  // = 30（向量支持 [] 语法）
```

### 2.2 行与列访问

```cpp
MatrixXd M(4, 4);
M = MatrixXd::Random(4, 4);

// 访问整行/整列（返回的是视图，不拷贝！）
auto row1 = M.row(0);    // 第1行（行向量视图）
auto col2 = M.col(1);    // 第2列（列向量视图）

// 修改整行/列
M.row(0).setZero();       // 第1行全置0
M.col(3) *= 2.0;          // 第4列乘2

// 行/列赋值
M.row(1) = M.row(2);     // 将第3行复制到第2行
M.col(0) = VectorXd::Ones(4); // 第1列全置1
```

---

## 3. 块操作（Block Operations）

块操作是 Eigen 最强大的特性之一，所有块操作返回的都是**视图（View）**，修改视图会直接影响原矩阵。

### 3.1 通用块访问

```cpp
MatrixXd M(5, 5);
M = MatrixXd::Zero(5, 5);
for (int i = 0; i < 5; ++i)
    for (int j = 0; j < 5; ++j)
        M(i, j) = i * 5 + j + 1;
// M =
//  1  2  3  4  5
//  6  7  8  9 10
// 11 12 13 14 15
// 16 17 18 19 20
// 21 22 23 24 25

// block(起始行, 起始列, 行数, 列数)
auto B1 = M.block(1, 1, 3, 3);
// = [[ 7,  8,  9],
//    [12, 13, 14],
//    [17, 18, 19]]

// 固定大小块（推荐！编译期优化，更快）
auto B2 = M.block<2, 2>(0, 0);  // 左上 2x2 块

// 修改块（直接影响 M）
M.block(0, 0, 2, 2).setZero();
```

### 3.2 角块快捷方法

```cpp
MatrixXd M = MatrixXd::Random(4, 4);

// 四个角块
auto tl = M.topLeftCorner(2, 2);     // 左上 2x2
auto tr = M.topRightCorner(2, 2);    // 右上 2x2
auto bl = M.bottomLeftCorner(2, 2);  // 左下 2x2
auto br = M.bottomRightCorner(2, 2); // 右下 2x2

// 固定大小版（更快）
auto tl2 = M.topLeftCorner<2, 2>();

// 顶部/底部行块
auto top2 = M.topRows(2);     // 前2行
auto bot2 = M.bottomRows(2);  // 后2行
auto top2f = M.topRows<2>(); // 固定大小版

// 左侧/右侧列块
auto left2  = M.leftCols(2);   // 前2列
auto right2 = M.rightCols(2);  // 后2列
```

### 3.3 向量的块操作

```cpp
VectorXd v = VectorXd::LinSpaced(8, 1.0, 8.0);
// v = [1, 2, 3, 4, 5, 6, 7, 8]

// 头部/尾部
auto h3 = v.head(3);     // [1, 2, 3]
auto t3 = v.tail(3);     // [6, 7, 8]
auto h3f = v.head<3>();  // 固定大小版

// 中间段：segment(起始位置, 长度)
auto mid = v.segment(2, 4);     // [3, 4, 5, 6]
auto midf = v.segment<4>(2);    // 固定大小版

// 修改视图
v.head(3).setZero();
v.tail(2) *= 10.0;
// v = [0, 0, 0, 4, 5, 6, 70, 80]
```

### 3.4 实战：矩阵分块拼接

```cpp
// 将四个子矩阵拼成一个大矩阵
MatrixXd A(2, 2), B(2, 3), C(3, 2), D(3, 3);
A = MatrixXd::Identity(2, 2);
B = MatrixXd::Zero(2, 3);
C = MatrixXd::Zero(3, 2);
D = MatrixXd::Random(3, 3);

MatrixXd Full(5, 5);
Full.topLeftCorner(2, 2)    = A;
Full.topRightCorner(2, 3)   = B;
Full.bottomLeftCorner(3, 2) = C;
Full.bottomRightCorner(3, 3)= D;
```

---

## 4. 算术运算

### 4.1 矩阵基本运算

```cpp
Matrix3d A = Matrix3d::Random();
Matrix3d B = Matrix3d::Random();

// 加减法（逐元素，形状必须匹配）
Matrix3d S = A + B;
Matrix3d D = A - B;
A += B;        // 就地加法
A -= B;        // 就地减法

// 标量运算
Matrix3d scaled = 3.14 * A;
Matrix3d half   = A / 2.0;
A *= 2.0;

// 矩阵乘法（注意：不是逐元素！）
Matrix3d prod = A * B;    // 标准矩阵乘法

// 矩阵的幂（需要方阵）
// Eigen 没有直接的矩阵幂，但有矩阵指数（via Eigen/MatrixFunctions）
#include <Eigen/MatrixFunctions>
Matrix3d expA = A.exp();   // 矩阵指数 e^A
Matrix3d logA = A.log();   // 矩阵对数
Matrix3d sqrtA = A.sqrt(); // 矩阵平方根（不是逐元素！）
```

### 4.2 转置、共轭与伴随

```cpp
MatrixXd A = MatrixXd::Random(3, 4);

MatrixXd At  = A.transpose();   // 转置，形状变为 4x3
// A.transposeInPlace();        // 原地转置（方阵）

// 复矩阵
MatrixXcd B = MatrixXcd::Random(3, 3);
MatrixXcd Bconj = B.conjugate();          // 仅共轭，不转置
MatrixXcd Badj  = B.adjoint();            // 共轭转置（Hermitian adjoint）
MatrixXcd Badj2 = B.transpose().conjugate(); // 等价写法
```

### 4.3 向量专用运算

```cpp
Vector3d u(1.0, 2.0, 3.0);
Vector3d v(4.0, 5.0, 6.0);

// 点积（内积）
double dot = u.dot(v);           // = 1*4 + 2*5 + 3*6 = 32

// 叉积（仅限 3D 向量）
Vector3d cross = u.cross(v);    // 垂直于 u 和 v 的向量

// 范数
double l2_norm   = u.norm();          // L2 范数（欧几里得距离）= sqrt(1+4+9) = 3.742
double l2_sq     = u.squaredNorm();   // L2 范数的平方（更快，避免开方）= 14
double l1_norm   = u.lpNorm<1>();     // L1 范数 = 1+2+3 = 6
double linf_norm = u.lpNorm<Eigen::Infinity>(); // L∞ 范数 = max(|1|,|2|,|3|) = 3

// 单位化
Vector3d unit    = u.normalized();    // 返回新向量，u 不变
u.normalize();                        // 就地单位化，等价于 u /= u.norm()

// 外积（张量积）：u 和 v 两个列向量
Matrix3d outer = u * v.transpose();  // 3x3 矩阵（秩为1）

// 元素级操作（需转换为 Array）
VectorXd abs_v  = u.array().abs();           // 逐元素绝对值
VectorXd sq_v   = u.array().square();        // 逐元素平方
VectorXd sqrt_v = u.array().abs().sqrt();    // 逐元素绝对值再开方
VectorXd exp_v  = u.array().exp();           // 逐元素 e^x
```

---

## 5. Array：逐元素操作

Eigen 中矩阵运算默认是**线性代数语义**（`*` 是矩阵乘法），而 `Array` 类提供**逐元素语义**（`*` 是逐元素乘法）。

```cpp
// Matrix 和 Array 自由转换
MatrixXd M = MatrixXd::Random(3, 3);

// Matrix → Array（逐元素操作）
auto A = M.array();

// 逐元素乘法（Hadamard 积）
MatrixXd N = MatrixXd::Random(3, 3);
MatrixXd hadamard = M.array() * N.array();

// 逐元素除法
MatrixXd elem_div = M.array() / N.array();

// 数学函数（逐元素）
MatrixXd abs_M    = M.array().abs();
MatrixXd sq_M     = M.array().square();
MatrixXd sqrt_M   = M.array().abs().sqrt();
MatrixXd exp_M    = M.array().exp();
MatrixXd log_M    = M.array().abs().log();
MatrixXd sin_M    = M.array().sin();
MatrixXd cos_M    = M.array().cos();
MatrixXd pow25_M  = M.array().pow(2.5);  // 逐元素 x^2.5

// 比较运算（返回 bool 数组）
auto mask = (M.array() > 0.0);          // 元素大于0的掩码
int  cnt  = mask.count();               // 正数元素个数
MatrixXd pos_only = M.array().max(0.0); // 相当于 max(M, 0)，ReLU！

// 逐元素条件选择（类似三目运算符）
MatrixXd result = (M.array() > 0).select(M, -M); // abs(M) 的另一种写法

// Array 和 Matrix 混用示例
// 将非负元素保留，负元素置零（ReLU 激活函数）
MatrixXd relu = M.cwiseMax(0.0);     // cwiseMax 是 Matrix 接口
// 等价于：
MatrixXd relu2 = M.array().max(0.0).matrix();
```

---

## 6. 归约操作

### 6.1 全局归约

```cpp
MatrixXd M(3, 3);
M << 1, 2, 3,
     4, 5, 6,
     7, 8, 9;

double total   = M.sum();            // 45（所有元素之和）
double product = M.prod();           // 362880（所有元素之积）
double max_val = M.maxCoeff();       // 9
double min_val = M.minCoeff();       // 1
double mean    = M.mean();           // 5（均值）
double trace   = M.trace();          // 15（主对角线之和）
double frob    = M.norm();           // Frobenius 范数 = sqrt(sum of squares)

// 带位置的最大/最小值
Eigen::Index max_row, max_col, min_row, min_col;
M.maxCoeff(&max_row, &max_col);  // max_row=2, max_col=2
M.minCoeff(&min_row, &min_col);  // min_row=0, min_col=0
std::cout << "最大值在 (" << max_row << ", " << max_col << ")\n"; // (2, 2)

// 判断
bool all_pos  = (M.array() > 0.0).all();   // 是否所有元素 > 0
bool any_gt8  = (M.array() > 8.0).any();   // 是否存在元素 > 8
bool none_neg = (M.array() < 0.0).any();   // 反向检查
```

### 6.2 按行/列归约

```cpp
MatrixXd M(3, 4);
M << 1,  2,  3,  4,
     5,  6,  7,  8,
     9, 10, 11, 12;

// 按列归约（结果是行向量）
RowVectorXd col_sum  = M.colwise().sum();    // [15, 18, 21, 24]
RowVectorXd col_max  = M.colwise().maxCoeff(); // [9, 10, 11, 12]
RowVectorXd col_mean = M.colwise().mean();   // [5, 6, 7, 8]
RowVectorXd col_norm = M.colwise().norm();   // 每列的 L2 范数

// 按行归约（结果是列向量）
VectorXd row_sum  = M.rowwise().sum();    // [10, 26, 42]
VectorXd row_max  = M.rowwise().maxCoeff(); // [4, 8, 12]
VectorXd row_mean = M.rowwise().mean();   // [2.5, 6.5, 10.5]

// 对每一列找最大值所在行
// （没有直接的 API，用循环实现）
for (int j = 0; j < M.cols(); ++j) {
    Eigen::Index max_idx;
    M.col(j).maxCoeff(&max_idx);
    std::cout << "第" << j << "列最大值在行 " << max_idx << "\n";
}
```

### 6.3 广播运算

```cpp
MatrixXd M = MatrixXd::Random(4, 3);
RowVectorXd col_mean = M.colwise().mean();  // 每列均值，形状 1x3

// 减去每列均值（中心化）—— 广播
MatrixXd centered = M.rowwise() - col_mean;

// 与每行的某向量做运算
VectorXd row_scale(4);
row_scale << 1, 2, 3, 4;
MatrixXd scaled = M.array().colwise() * row_scale.array();
// 等价于：每一列乘以 row_scale
```

---

## 7. Map：零拷贝数据映射

`Eigen::Map` 是 Eigen 与外部数据交互的核心工具，它将一段内存映射为 Eigen 矩阵/向量，**不发生任何数据拷贝**。

### 7.1 基本用法

```cpp
#include <Eigen/Dense>
#include <vector>

// ---- 将 double 数组映射为列向量 ----
double arr[6] = {1, 2, 3, 4, 5, 6};
Eigen::Map<Eigen::VectorXd> v(arr, 6);
std::cout << v.sum() << "\n";  // 21

// 修改 v 会直接修改 arr
v(0) = 99.0;
std::cout << arr[0] << "\n";  // 99

// ---- 将数组映射为矩阵（列主序，Eigen 默认）----
Eigen::Map<Eigen::MatrixXd> col_mat(arr, 2, 3);
// arr 按列填入：
// col 0: arr[0], arr[1]
// col 1: arr[2], arr[3]
// col 2: arr[4], arr[5]
// col_mat =
// 99  3  5
//  2  4  6

// ---- 行主序映射（对应 C 二维数组）----
using RowMajorMatrix = Eigen::Matrix<double, Eigen::Dynamic, Eigen::Dynamic, Eigen::RowMajor>;
Eigen::Map<RowMajorMatrix> row_mat(arr, 2, 3);
// arr 按行填入：
// row 0: arr[0], arr[1], arr[2]
// row 1: arr[3], arr[4], arr[5]
// row_mat =
// 99  2  3
//  4  5  6
```

### 7.2 std::vector 映射

```cpp
std::vector<float> data(12, 1.0f);
for (int i = 0; i < 12; ++i) data[i] = static_cast<float>(i);

// 映射为 Eigen 矩阵（列主序）
Eigen::Map<Eigen::Matrix<float, 3, 4>> mat(data.data());
// mat =
// 0  3  6  9
// 1  4  7 10
// 2  5  8 11

// 映射为动态矩阵
Eigen::Map<Eigen::MatrixXf> dyn_mat(data.data(), 4, 3);
```

### 7.3 带步长的 Map（Stride）

```cpp
double arr[12] = {1,2,3,4,5,6,7,8,9,10,11,12};

// InnerStride：相邻元素间距
// 取 arr 的奇数索引元素（步长2）：1,3,5,7,9,11
Eigen::Map<Eigen::VectorXd, 0, Eigen::InnerStride<2>> strided_v(arr, 6);
// strided_v = [1, 3, 5, 7, 9, 11]

// OuterStride：相邻列（或行）间距
// 从 12 个元素的数组中提取 2x3 矩阵，列步长为 4
Eigen::Map<Eigen::Matrix<double, 2, 3>, 0, Eigen::OuterStride<4>> M(arr);
// 列0: arr[0], arr[1]
// 列1: arr[4], arr[5]
// 列2: arr[8], arr[9]
// M =
// 1  5  9
// 2  6 10
```

### 7.4 实战：与 OpenCV Mat 互操作

```cpp
// 假设 cv::Mat 已包含 double 类型数据（行主序）
// cv::Mat cv_mat(rows, cols, CV_64F);

// 将 OpenCV 矩阵映射为 Eigen（零拷贝）
// using RowMajorMat = Eigen::Matrix<double, Dynamic, Dynamic, RowMajor>;
// Eigen::Map<RowMajorMat> eigen_mat(
//     reinterpret_cast<double*>(cv_mat.data),
//     cv_mat.rows, cv_mat.cols
// );

// 注意：需要确保 cv_mat 是连续存储（isContinuous() == true）
```

---

## 8. 类型转换

```cpp
// 标量类型转换
MatrixXd Md = MatrixXd::Random(3, 3);
MatrixXf Mf = Md.cast<float>();         // double → float
MatrixXi Mi = Md.cast<int>();           // double → int（截断）
Matrix3d Md2 = Mf.cast<double>();       // float → double

// 实矩阵 → 复矩阵
MatrixXcd Mcd = Md.cast<std::complex<double>>();

// 矩阵形状重塑（需元素总数不变）
// 注意：Eigen 没有 reshape 成员函数，需借助 Map
MatrixXd A(2, 6);
A = MatrixXd::Random(2, 6);
// 视为 3x4 矩阵（按列主序重新解释）
Eigen::Map<MatrixXd> B(A.data(), 3, 4);
// B 与 A 共享内存
```

---

## 9. 矩阵与向量的相互转换

```cpp
// 向量 → 对角矩阵
Vector3d diag_vals(1.0, 2.0, 3.0);
Matrix3d D = diag_vals.asDiagonal();
// D =
// 1 0 0
// 0 2 0
// 0 0 3

// 矩阵 → 提取对角元素
Matrix3d M = Matrix3d::Random();
Vector3d diag = M.diagonal();         // 主对角线
Vector2d diag1 = M.diagonal(1);      // 上一条次对角线（2元素）
Vector2d diag_m1 = M.diagonal(-1);   // 下一条次对角线（2元素）

// 拉直（向量化）
MatrixXd A(2, 3);
A << 1, 2, 3, 4, 5, 6;
// 按列主序拉直为向量
Eigen::Map<VectorXd> flat(A.data(), A.size());
// flat = [1, 4, 2, 5, 3, 6]（列主序）

// 矩阵展平（不修改原矩阵的新向量）
VectorXd flattened = Eigen::Map<VectorXd>(A.data(), A.size());
```

---

## 10. 性能注意事项

### 10.1 避免不必要的 .eval()

```cpp
MatrixXd A = MatrixXd::Random(100, 100);
MatrixXd B = MatrixXd::Random(100, 100);
MatrixXd C = MatrixXd::Random(100, 100);

// Eigen 的懒求值会自动合并，不产生临时对象
MatrixXd result1 = A + B + C;         // 只一次分配，合并计算

// 但对于矩阵乘法，Eigen 会先求右侧再赋值（防止别名）
// 如果确定没有别名，用 noalias() 优化
MatrixXd res(100, 100);
res.noalias() = A * B;     // 避免创建临时对象

// 连接多个乘法时
MatrixXd res2(100, 100);
res2.noalias() = A * B + C;  // 仍然安全且高效
```

### 10.2 预先 resize

```cpp
MatrixXd result;
// 在循环外预分配（避免重复内存申请）
result.resize(1000, 1000);

for (int i = 0; i < 100; ++i) {
    MatrixXd tmp = MatrixXd::Random(1000, 1000);
    result += tmp;   // 不会重新分配，因为形状匹配
}
```

### 10.3 `auto` 陷阱（高频面试 / 实战翻车点）

Eigen 的几乎所有运算返回的都是**表达式模板对象**而非具体矩阵。`auto` 推导出来的是这个表达式类型，**不是结果**：

```cpp
MatrixXd A = MatrixXd::Random(3, 3);
MatrixXd B = MatrixXd::Random(3, 3);

// 危险写法 1：auto 拿到的是 Product<...> 表达式
auto C = A * B;              // C 不是 MatrixXd，而是惰性表达式
std::cout << C(0, 0);        // 每访问一次都会重新做矩阵乘法！

// 危险写法 2：临时变量被悬挂引用
auto row = (A + B).row(0);   // (A+B) 是右值表达式，立即销毁
                             // row 内部持有的引用已悬空 → 未定义行为

// 危险写法 3：cwiseProduct/transpose 同理
auto T = A.transpose();      // T 内部引用 A，A 修改后 T 跟着变
A.setZero();
std::cout << T;              // 输出全 0（不是预期的转置快照）
```

**正确做法**：表达式类型作为返回值时一律显式声明类型，或用 `.eval()` 强制求值。

```cpp
MatrixXd C  = A * B;            // 推荐：触发求值，C 是真正的矩阵
auto    C2  = (A * B).eval();   // 也可以，但不如直接写类型清晰

// 函数局部用 auto 接 block/segment 视图是 OK 的，前提是源对象生命周期足够长
const MatrixXd& Aref = A;
auto block = Aref.block(0, 0, 2, 2);   // 安全：Aref 持续存活
```

> **面试要点**：`auto + Eigen` 是 C++ 项目中仅次于「悬空指针」的高频崩溃源。回答时务必提到「表达式模板 + 惰性求值」这个根因。

### 10.4 `Eigen::Ref<>`：写库函数的标准姿势

写函数接收 Eigen 矩阵时，最容易踩的坑：

```cpp
// 写法 A：只能接受 MatrixXd 本体，不能接受 block/Map
void process(const Eigen::MatrixXd& M);

// 写法 B：模板，支持任意表达式但会膨胀编译时间且无法分离实现
template <typename Derived>
void process(const Eigen::MatrixBase<Derived>& M);
```

`Eigen::Ref` 是兼顾两者的官方推荐方式：**接口干净 + 接受任何兼容表达式**。

```cpp
#include <Eigen/Dense>

// 只读输入：接受 MatrixXd / Map / block / 转置 / 类型一致的子表达式
double frobenius(const Eigen::Ref<const Eigen::MatrixXd>& M) {
    return M.norm();
}

// 可写输出：接受可写的 block/Map/MatrixXd
void scale_inplace(Eigen::Ref<Eigen::MatrixXd> M, double s) {
    M *= s;
}

// 调用示例
Eigen::MatrixXd A = Eigen::MatrixXd::Random(10, 10);

frobenius(A);                       // OK
frobenius(A.block(0, 0, 5, 5));     // OK，block 自动适配
frobenius(A.transpose());           // OK，转置也能传

scale_inplace(A.col(0), 2.0);       // OK，对 A 的第 0 列原地缩放
```

**注意事项**：

1. `Ref<MatrixXd>` 默认要求**列主序、连续内存**。不连续的视图（如带 stride 的 Map、`A.row(i)` 在列主序矩阵上）会触发**隐式拷贝**。
2. 想接受任意 stride 时使用：

   ```cpp
   void any_layout(const Eigen::Ref<const Eigen::MatrixXd, 0,
                                    Eigen::Stride<Eigen::Dynamic, Eigen::Dynamic>>& M);
   ```

3. 固定大小（如 `Vector3d`）建议直接用 `const Vector3d&`，性能更好。

### 10.5 Eigen 3.4 切片语法（NumPy 风格）

Eigen 3.4 起支持类似 NumPy 的索引语法（需 `#include <Eigen/Dense>`）：

```cpp
using Eigen::seq;        // 区间 [first, last]，含两端
using Eigen::seqN;       // 起点 + 个数
using Eigen::all;        // 全部
using Eigen::last;       // 末尾元素索引（== rows()-1 / cols()-1）
using Eigen::placeholders::lastN;

MatrixXd M = MatrixXd::Random(6, 6);

// 取第 1~3 行所有列（含两端）
auto sub1 = M(seq(1, 3), all);

// 反向：从倒数第二行到第一行
auto sub2 = M(seq(last - 1, 1, Eigen::fix<-1>), all);   // 步长 -1

// 离散索引
std::vector<int> idx{0, 2, 4};
auto sub3 = M(idx, all);            // 取第 0/2/4 行

// 最后 2 列
auto sub4 = M(all, lastN(2));

// reshaped()：等价 NumPy reshape（默认列主序）
VectorXd v = VectorXd::LinSpaced(12, 0, 11);
auto m34 = v.reshaped(3, 4);                          // 3x4 矩阵视图
auto m43_row = v.reshaped<Eigen::RowMajor>(4, 3);     // 行主序 reshape

// reshaped() 不指定大小时拉直为列向量
VectorXd flat = M.reshaped();                          // 36x1 列主序拉直
```

> 优势：可读性接近 NumPy；编译期保留尺寸信息；和老式 `block()` 完全可混用。

### 10.6 数值健壮性 API

工程中浮点比较和异常值检测的标准做法：

```cpp
MatrixXd A = MatrixXd::Random(3, 3);
MatrixXd B = A + MatrixXd::Constant(3, 3, 1e-15);

// 浮点近似相等（默认 prec = NumTraits<Scalar>::dummy_precision()）
bool eq = A.isApprox(B);              // true
bool eq2 = A.isApprox(B, 1e-12);      // 自定义精度

// 与零比较（用相对范数）
VectorXd v = VectorXd::Zero(5);
bool z = v.isZero();                   // true
bool z2 = v.isZero(1e-10);             // 自定义阈值

// "很小"判断（相对于参考量）
double err = 1e-9;
bool small = Eigen::numext::isMuchSmallerThan(err, A.norm());

// NaN / Inf 检测（写卡尔曼/优化时强烈建议加）
MatrixXd X(2, 2);
X << 1.0, std::nan(""), 0.0, 1.0;
bool ok    = X.allFinite();   // false
bool has_n = X.hasNaN();      // true

// 单位矩阵 / 对角阵判定
Matrix3d I = Matrix3d::Identity();
bool isI = I.isIdentity();
bool isD = I.isDiagonal();
```

---

## 小结

| 操作 | API |
|---|---|
| 工厂方法 | `Zero()`, `Ones()`, `Identity()`, `Random()`, `LinSpaced()` |
| 元素访问 | `M(i,j)`, `row(i)`, `col(j)` |
| 块操作 | `block()`, `topRows()`, `head()`, `segment()` |
| 逐元素操作 | `.array()` 转换后使用 `*`, `/`, `exp()`, `max()` 等 |
| 归约 | `sum()`, `maxCoeff()`, `colwise()`, `rowwise()` |
| 零拷贝映射 | `Eigen::Map<T>(ptr, rows, cols)` |
| 类型转换 | `.cast<float>()` |
| 广播 | `.rowwise() - vec`, `.colwise() * vec` |
| `auto` 陷阱 | Eigen 表达式不能用 `auto` 长存，需 `.eval()` 或显式类型 |
| 函数参数 | `Eigen::Ref<const MatrixXd>` 兼容 `MatrixXd`/`Map`/`block` |
| 切片（3.4+）| `M(seq(a,b), all)`、`v.reshaped(r,c)` |
| 数值健壮性 | `isApprox()`, `allFinite()`, `hasNaN()` |

下一篇将进入线性方程组求解的核心：LU、Cholesky、QR 分解与最小二乘问题。
