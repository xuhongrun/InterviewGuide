# Eigen C++ 线性代数库（四）：特征值分解、SVD 与几何变换

> **系列导航**
> - 第一篇：入门与基本类型
> - 第二篇：矩阵与向量操作详解
> - 第三篇：线性方程组求解与矩阵分解
> - **第四篇：特征值分解、SVD 与几何变换** ← 当前
> - 第五篇：稀疏矩阵、性能优化与工程实战
> - 第六篇：ROS / SLAM 生态互操作
> - 第七篇：unsupported 模块与非线性优化

---

## 1. 特征值分解（EVD）

### 1.1 数学基础

对矩阵 $A$，特征值分解寻找满足以下关系的标量 $\lambda$ 和非零向量 $v$：

$$Av = \lambda v$$

对于可对角化的 $n \times n$ 矩阵：

$$A = V \Lambda V^{-1}$$

其中 $\Lambda = \text{diag}(\lambda_1, \dots, \lambda_n)$，$V$ 的列是对应的特征向量。

**实对称矩阵（Self-Adjoint）** 的特殊性质：
- 特征值必然是**实数**
- 特征向量互相**正交**
- 分解为 $A = Q\Lambda Q^T$（$Q$ 是正交矩阵）

### 1.2 通用实矩阵：EigenSolver

```cpp
#include <iostream>
#include <Eigen/Eigenvalues>

int main() {
    Eigen::Matrix3d A;
    A <<  4, -2,  1,
          2,  0,  1,
         -1,  2,  3;

    // 通用实矩阵特征值（结果可能是复数）
    Eigen::EigenSolver<Eigen::Matrix3d> es(A);

    // 特征值（复数）
    std::cout << "特征值:\n" << es.eigenvalues() << "\n\n";

    // 特征向量（复数矩阵，每列是一个特征向量）
    std::cout << "特征向量:\n" << es.eigenvectors() << "\n\n";

    // 只取实部（若矩阵有实特征值）
    // 可用 es.eigenvalues().real() 和 es.eigenvectors().real()

    // 验证：A * V = V * Lambda
    auto V = es.eigenvectors();
    auto D = es.eigenvalues().asDiagonal();
    double err = (A.cast<std::complex<double>>() * V - V * D).norm();
    std::cout << "验证误差 ||AV - VD||: " << err << "\n"; // 应接近 0

    return 0;
}
```

### 1.3 对称矩阵：SelfAdjointEigenSolver（推荐）

```cpp
#include <iostream>
#include <Eigen/Eigenvalues>

int main() {
    // 构造对称矩阵（A + A^T 一定对称）
    Eigen::Matrix4d B = Eigen::Matrix4d::Random();
    Eigen::Matrix4d A = B + B.transpose();

    // 对称矩阵特征值分解（速度是 EigenSolver 的 2-3 倍，结果全是实数）
    Eigen::SelfAdjointEigenSolver<Eigen::Matrix4d> saes(A);

    if (saes.info() == Eigen::Success) {
        // 特征值从小到大排列（实数向量）
        Eigen::Vector4d eigenvalues = saes.eigenvalues();
        // 对应特征向量（实数矩阵，列正交）
        Eigen::Matrix4d eigenvectors = saes.eigenvectors();

        std::cout << "特征值（升序）: " << eigenvalues.transpose() << "\n\n";
        std::cout << "特征向量（列）:\n" << eigenvectors << "\n\n";

        // 验证正交性：V^T V 应为单位矩阵
        double orth_err = (eigenvectors.transpose() * eigenvectors
                          - Eigen::Matrix4d::Identity()).norm();
        std::cout << "正交性误差: " << orth_err << "\n";

        // 验证分解：A = V * Lambda * V^T
        Eigen::Matrix4d reconstructed = eigenvectors
                                      * eigenvalues.asDiagonal()
                                      * eigenvectors.transpose();
        std::cout << "重建误差: " << (A - reconstructed).norm() << "\n";

        // 最大/最小特征值
        double lambda_min = eigenvalues(0);
        double lambda_max = eigenvalues(eigenvalues.size() - 1);
        std::cout << "条件数 = lambda_max/lambda_min = "
                  << lambda_max / std::abs(lambda_min) << "\n";
    }

    return 0;
}
```

### 1.4 广义特征值问题

$$Av = \lambda Bv \quad \text{（B 对称正定）}$$

```cpp
#include <Eigen/Eigenvalues>
#include <iostream>

int main() {
    // 广义特征值问题：Ax = lambda * B * x
    // 常见于有限元分析（刚度矩阵 K，质量矩阵 M）
    Eigen::Matrix3d A, B;
    A << 4, 1, 0,
         1, 3, 1,
         0, 1, 2;
    B << 2, 0, 0,
         0, 3, 0,
         0, 0, 1;

    // 方法：变换为标准特征值问题
    // B = L L^T，令 y = L^T x，则 L^{-1} A L^{-T} y = lambda y
    Eigen::LLT<Eigen::Matrix3d> llt_B(B);
    Eigen::Matrix3d L = llt_B.matrixL();
    Eigen::Matrix3d L_inv = L.inverse();

    Eigen::Matrix3d C = L_inv * A * L_inv.transpose();

    Eigen::SelfAdjointEigenSolver<Eigen::Matrix3d> saes(C);
    Eigen::Vector3d gen_eigenvalues = saes.eigenvalues();

    // 广义特征向量（还原）
    Eigen::Matrix3d gen_eigenvectors = L_inv.transpose() * saes.eigenvectors();

    std::cout << "广义特征值: " << gen_eigenvalues.transpose() << "\n";
    return 0;
}
```

### 1.5 实战：PCA 主成分分析

```cpp
#include <Eigen/Dense>
#include <Eigen/Eigenvalues>
#include <iostream>

// PCA：找数据的主成分方向
// 输入：data（N×D），n_components（保留的维数）
// 输出：降维后的数据（N×n_components）和主成分方向
struct PCAResult {
    Eigen::MatrixXd projected;    // 降维后数据
    Eigen::MatrixXd components;   // 主成分（每列是一个方向）
    Eigen::VectorXd explained;    // 各主成分解释的方差比例
};

PCAResult pca(const Eigen::MatrixXd& data, int n_components) {
    int N = data.rows();

    // 1. 中心化
    Eigen::RowVectorXd mean = data.colwise().mean();
    Eigen::MatrixXd centered = data.rowwise() - mean;

    // 2. 计算协方差矩阵（或直接对中心化矩阵做 SVD 更稳定）
    Eigen::MatrixXd cov = (centered.transpose() * centered) / (N - 1);

    // 3. 对称矩阵特征值分解（特征值从小到大）
    Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> saes(cov);

    // 4. 取最大的 n_components 个特征值（在末尾）
    int D = data.cols();
    Eigen::MatrixXd components = saes.eigenvectors().rightCols(n_components);
    Eigen::VectorXd eigenvalues = saes.eigenvalues().tail(n_components).reverse();
    // 方向从大方差到小方差

    // 5. 计算方差解释比
    double total_var = saes.eigenvalues().sum();
    Eigen::VectorXd explained = eigenvalues / total_var;

    // 6. 投影
    Eigen::MatrixXd projected = centered * components.rowwise().reverse();
    // 注意：最大特征值在末尾，需翻转列顺序

    return {projected, components, explained};
}

int main() {
    // 生成 3D 数据：主要沿 (1,1,0)/sqrt(2) 和 (0,0,1) 方向分布
    int N = 500;
    Eigen::MatrixXd data(N, 3);
    data = Eigen::MatrixXd::Random(N, 3);
    data.col(0) = data.col(0) * 3.0;   // x 方向方差 = 9
    data.col(1) = data.col(1) * 3.0;   // y 方向方差 = 9
    data.col(2) = data.col(2) * 0.1;   // z 方向方差 ≈ 0

    // 降维到 2D
    auto [proj, comps, exp_var] = pca(data, 2);

    std::cout << "方差解释比 (PC1, PC2): "
              << exp_var(0) * 100 << "%, "
              << exp_var(1) * 100 << "%\n";
    std::cout << "累计方差解释比: "
              << exp_var.sum() * 100 << "%\n";
    std::cout << "降维后数据尺寸: " << proj.rows() << " x " << proj.cols() << "\n";

    return 0;
}
```

---

## 2. 奇异值分解（SVD）

### 2.1 数学基础

对任意 $m \times n$ 矩阵 $A$（$m \geq n$）：

$$A = U \Sigma V^T$$

- $U$：$m \times m$ 正交矩阵（左奇异向量）
- $\Sigma$：$m \times n$ 对角矩阵（奇异值，从大到小排列）
- $V$：$n \times n$ 正交矩阵（右奇异向量）

**Thin SVD**（紧 SVD）：只计算前 $n$ 列的 $U$，$\Sigma$ 为 $n \times n$：

$$A = U_n \Sigma_n V^T$$

### 2.2 JacobiSVD vs BDCSVD

```cpp
#include <Eigen/Dense>
#include <iostream>

int main() {
    Eigen::MatrixXd A(5, 3);
    A << 1, 2, 3,
         4, 5, 6,
         7, 8, 9,
         10,11,12,
         13,14,15;

    // JacobiSVD：小矩阵（< 16），精度最高
    Eigen::JacobiSVD<Eigen::MatrixXd> svd_j(A,
        Eigen::ComputeThinU | Eigen::ComputeThinV);

    // BDCSVD：大矩阵（推荐用这个）
    Eigen::BDCSVD<Eigen::MatrixXd> svd_b(A,
        Eigen::ComputeThinU | Eigen::ComputeThinV);

    // 奇异值（从大到小）
    std::cout << "奇异值: " << svd_b.singularValues().transpose() << "\n";

    // 左/右奇异矩阵
    Eigen::MatrixXd U = svd_b.matrixU();  // 5x3（Thin U）
    Eigen::MatrixXd V = svd_b.matrixV();  // 3x3

    // 重建：A = U * Sigma * V^T
    Eigen::MatrixXd Sigma = svd_b.singularValues().asDiagonal();
    Eigen::MatrixXd A_rec = U * Sigma * V.transpose();
    std::cout << "重建误差: " << (A - A_rec).norm() << "\n"; // ≈ 0

    // 矩阵的秩（奇异值 > 阈值的个数）
    double threshold = 1e-10;
    int rank = (svd_b.singularValues().array() > threshold).count();
    std::cout << "矩阵的秩: " << rank << "\n"; // = 2（行线性相关）

    return 0;
}
```

### 2.3 低秩近似（信息压缩）

保留最大的 $k$ 个奇异值，可得到原矩阵的最优秩 $k$ 近似（Eckart-Young 定理）：

$$A_k = U_k \Sigma_k V_k^T = \sum_{i=1}^k \sigma_i u_i v_i^T$$

```cpp
#include <Eigen/Dense>
#include <iostream>

// 计算矩阵的低秩近似
Eigen::MatrixXd low_rank_approx(const Eigen::MatrixXd& A, int k) {
    Eigen::BDCSVD<Eigen::MatrixXd> svd(A,
        Eigen::ComputeThinU | Eigen::ComputeThinV);

    // 只保留前 k 个奇异值
    auto U_k = svd.matrixU().leftCols(k);
    auto V_k = svd.matrixV().leftCols(k);
    auto S_k = svd.singularValues().head(k).asDiagonal();

    return U_k * S_k * V_k.transpose();
}

int main() {
    // 模拟一张 20x20 的灰度图像
    Eigen::MatrixXd image = Eigen::MatrixXd::Random(20, 20);
    double total_energy = image.norm();

    std::cout << "原始矩阵大小: " << image.rows() << "x" << image.cols()
              << " = " << image.size() << " 个元素\n\n";

    // 不同秩的近似
    for (int k : {1, 2, 5, 10, 20}) {
        Eigen::MatrixXd approx = low_rank_approx(image, k);
        double err = (image - approx).norm() / total_energy;
        int storage = k * (image.rows() + image.cols() + 1); // U_k + V_k + S_k
        double compress_ratio = (double)storage / image.size();

        std::printf("秩 k=%2d: 相对误差 = %.4f，存储占比 = %.1f%%\n",
                    k, err, compress_ratio * 100);
    }

    return 0;
}
```

### 2.4 伪逆（Moore-Penrose Inverse）

对于任意矩阵 $A$，伪逆 $A^+$ 给出最小范数最小二乘解：

```cpp
#include <Eigen/Dense>
#include <iostream>

// 计算矩阵的 Moore-Penrose 伪逆
Eigen::MatrixXd pseudo_inverse(const Eigen::MatrixXd& A,
                                double tolerance = 1e-10) {
    Eigen::JacobiSVD<Eigen::MatrixXd> svd(A,
        Eigen::ComputeFullU | Eigen::ComputeFullV);

    const auto& sv = svd.singularValues();
    Eigen::VectorXd sv_inv(sv.size());
    for (int i = 0; i < sv.size(); ++i) {
        sv_inv(i) = (sv(i) > tolerance) ? 1.0 / sv(i) : 0.0;
    }

    return svd.matrixV() * sv_inv.asDiagonal() * svd.matrixU().transpose();
}

int main() {
    Eigen::MatrixXd A(3, 4);
    A << 1, 2, 3, 4,
         5, 6, 7, 8,
         9,10,11,12;

    Eigen::MatrixXd A_plus = pseudo_inverse(A);
    std::cout << "A (3x4):\n" << A << "\n\n";
    std::cout << "A+ (4x3):\n" << A_plus << "\n\n";

    // 验证伪逆性质：A * A+ * A = A
    double err = (A * A_plus * A - A).norm();
    std::cout << "验证 A A+ A = A，误差: " << err << "\n";

    return 0;
}
```

---

## 3. 几何模块（Eigen/Geometry）

### 3.1 旋转表示方式概览

| 表示方式 | 优点 | 缺点 | 适用场景 |
|---|---|---|---|
| 旋转矩阵（3×3）| 直接变换向量，无歧义 | 9参数冗余，正交约束 | 矩阵运算主导 |
| 欧拉角（3个角）| 直观易理解 | **万向锁**问题，顺序依赖 | 用户交互、简单角度显示 |
| 轴角（axis-angle）| 紧凑，物理直观 | 不便于插值 | 存储、可视化 |
| 四元数（4参数）| 无奇异性，插值友好 | 不直观，有 ±q 等价 | **工程首选**，SLAM、ROS |
| 李代数 so(3) | 便于优化 | 理解复杂 | 图优化、状态估计 |

### 3.2 旋转矩阵

```cpp
#include <Eigen/Dense>
#include <Eigen/Geometry>
#include <iostream>

int main() {
    // === 绕轴旋转 ===
    double angle = M_PI / 3;  // 60°

    // 绕 Z 轴旋转 60°
    Eigen::AngleAxisd rot_z(angle, Eigen::Vector3d::UnitZ());
    Eigen::Matrix3d R_z = rot_z.toRotationMatrix();
    std::cout << "绕 Z 旋转 60° 的旋转矩阵:\n" << R_z << "\n\n";

    // 绕任意单位轴旋转（Rodrigues 公式）
    Eigen::Vector3d axis(1, 1, 0);
    axis.normalize();
    Eigen::AngleAxisd rot_axis(M_PI / 4, axis);  // 45°
    Eigen::Matrix3d R_axis = rot_axis.toRotationMatrix();

    // === 验证旋转矩阵性质 ===
    std::cout << "R^T R 误差（应≈0）: "
              << (R_z * R_z.transpose() - Eigen::Matrix3d::Identity()).norm() << "\n";
    std::cout << "det(R) = " << R_z.determinant() << " （应=1.0）\n\n";

    // === 旋转复合 ===
    Eigen::AngleAxisd rot_x(M_PI / 6, Eigen::Vector3d::UnitX());
    Eigen::Matrix3d R_x = rot_x.toRotationMatrix();
    // 先绕 X 转，再绕 Z 转（注意顺序：矩阵从右往左读）
    Eigen::Matrix3d R_composed = R_z * R_x;

    // === 变换向量 ===
    Eigen::Vector3d p(1, 0, 0);
    Eigen::Vector3d p_rot = R_z * p;
    std::cout << "旋转后的点: " << p_rot.transpose() << "\n";
    // (1,0,0) 绕Z旋转60° → (cos60°, sin60°, 0) = (0.5, 0.866, 0)

    // === 从旋转矩阵恢复轴角 ===
    Eigen::AngleAxisd aa(R_z);
    std::cout << "恢复轴: " << aa.axis().transpose() << "\n";
    std::cout << "恢复角度: " << aa.angle() * 180 / M_PI << "°\n";

    return 0;
}
```

### 3.3 欧拉角

```cpp
#include <Eigen/Geometry>
#include <iostream>

int main() {
    // 欧拉角（ZYX 顺序，即 Yaw-Pitch-Roll，航空中最常用）
    double yaw   = M_PI / 6;   // Z 轴旋转 30°
    double pitch = M_PI / 12;  // Y 轴旋转 15°
    double roll  = M_PI / 4;   // X 轴旋转 45°

    // 构造：ZYX 顺序 = 先绕 Z，再绕 Y，再绕 X
    Eigen::Matrix3d R;
    R = Eigen::AngleAxisd(yaw,   Eigen::Vector3d::UnitZ())
      * Eigen::AngleAxisd(pitch, Eigen::Vector3d::UnitY())
      * Eigen::AngleAxisd(roll,  Eigen::Vector3d::UnitX());

    // 从旋转矩阵提取欧拉角（指定顺序）
    // eulerAngles(轴0, 轴1, 轴2)：0=X, 1=Y, 2=Z
    Eigen::Vector3d euler_zyx = R.eulerAngles(2, 1, 0); // ZYX
    std::cout << "提取欧拉角 (ZYX, 弧度): " << euler_zyx.transpose() << "\n";
    std::cout << "原始欧拉角 (ZYX): "
              << yaw << " " << pitch << " " << roll << "\n\n";

    // 警告：万向锁（Gimbal Lock）
    // 当 pitch = ±90° 时，yaw 和 roll 退化为同一个自由度！
    Eigen::Matrix3d gimbal;
    gimbal = Eigen::AngleAxisd(0.5, Eigen::Vector3d::UnitZ())
           * Eigen::AngleAxisd(M_PI/2, Eigen::Vector3d::UnitY()) // pitch = 90°！
           * Eigen::AngleAxisd(0.3, Eigen::Vector3d::UnitX());
    Eigen::Vector3d gimbal_euler = gimbal.eulerAngles(2, 1, 0);
    std::cout << "万向锁情形 pitch = 90° 时：" << gimbal_euler.transpose() << "\n";
    // yaw 和 roll 的值将无法单独恢复，这就是为什么工程中用四元数

    return 0;
}
```

### 3.4 四元数（Quaternion）

四元数是工程中最推荐的旋转表示方式：

```cpp
#include <Eigen/Geometry>
#include <iostream>

int main() {
    // === 四元数基础 ===
    // Eigen 四元数存储顺序：(x, y, z, w)，注意 w 在最后！
    // 但构造函数参数是 (w, x, y, z)

    // 从轴角构造
    Eigen::Quaterniond q1(Eigen::AngleAxisd(M_PI / 3, Eigen::Vector3d::UnitZ()));
    std::cout << "q1 = (w=" << q1.w() << ", x=" << q1.x()
              << ", y=" << q1.y() << ", z=" << q1.z() << ")\n";

    // 从旋转矩阵构造
    Eigen::Matrix3d R = Eigen::AngleAxisd(M_PI / 4, Eigen::Vector3d::UnitX()).toRotationMatrix();
    Eigen::Quaterniond q2(R);

    // 单位四元数（无旋转）
    Eigen::Quaterniond q_identity = Eigen::Quaterniond::Identity();

    // 验证单位长度
    std::cout << "q1 的模长: " << q1.norm() << " （应=1）\n\n";

    // === 四元数运算 ===
    // 复合旋转：q1 后接 q2（等价于 R2 * R1）
    Eigen::Quaterniond q_composed = q2 * q1;

    // 旋转向量
    Eigen::Vector3d p(1, 0, 0);
    Eigen::Vector3d p_rot = q1 * p;   // 用四元数旋转向量
    std::cout << "旋转后的点: " << p_rot.transpose() << "\n";

    // 共轭（逆旋转，对单位四元数等于逆）
    Eigen::Quaterniond q1_inv = q1.conjugate();
    Eigen::Vector3d p_back = q1_inv * p_rot;
    std::cout << "反向旋转验证: " << p_back.transpose() << " （应≈[1,0,0]）\n\n";

    // 相对旋转：从 q1 转到 q2 需要旋转：q_rel = q2 * q1^{-1}
    Eigen::Quaterniond q_rel = q2 * q1.conjugate();

    // === 球面线性插值（SLERP）===
    Eigen::Quaterniond qa = Eigen::Quaterniond::Identity();
    Eigen::Quaterniond qb(Eigen::AngleAxisd(M_PI, Eigen::Vector3d::UnitZ())); // 180°

    std::cout << "SLERP 插值：\n";
    for (double t : {0.0, 0.25, 0.5, 0.75, 1.0}) {
        Eigen::Quaterniond q_mid = qa.slerp(t, qb);
        Eigen::AngleAxisd aa(q_mid);
        std::cout << "  t=" << t << " → 旋转角度 "
                  << aa.angle() * 180 / M_PI << "°\n";
    }

    // === 四元数 ↔ 其他表示互转 ===
    Eigen::Matrix3d R_from_q = q1.toRotationMatrix();
    Eigen::AngleAxisd aa_from_q(q1);
    Eigen::Vector3d axis = aa_from_q.axis();
    double angle = aa_from_q.angle();

    std::cout << "\n旋转轴: " << axis.transpose() << "\n";
    std::cout << "旋转角: " << angle * 180 / M_PI << "°\n";

    return 0;
}
```

### 3.5 刚体变换：Isometry3d

```cpp
#include <Eigen/Geometry>
#include <iostream>

int main() {
    // === 构建 4x4 齐次变换矩阵 ===
    // T = [R | t]
    //     [0 | 1]

    Eigen::Isometry3d T = Eigen::Isometry3d::Identity();

    // 设置旋转（绕 Z 轴 45°）
    Eigen::AngleAxisd rot(M_PI / 4, Eigen::Vector3d::UnitZ());
    T.rotate(rot);

    // 设置平移
    Eigen::Vector3d translation(1.0, 2.0, 3.0);
    T.pretranslate(translation);  // pretranslate：先平移后旋转（等价于 T*t）
    // T.translate(...)           // translate：先旋转后平移（等价于 R*t + t_old）

    std::cout << "4x4 变换矩阵 T:\n" << T.matrix() << "\n\n";

    // === 变换点和向量 ===
    Eigen::Vector3d p(0, 0, 1);

    // 变换点（应用完整的旋转+平移）
    Eigen::Vector3d p_new = T * p;
    std::cout << "变换点: " << p_new.transpose() << "\n";

    // 变换方向向量（只应用旋转，不平移）
    Eigen::Vector3d dir = T.linear() * Eigen::Vector3d(0, 1, 0);
    std::cout << "旋转方向向量: " << dir.transpose() << "\n\n";

    // === 提取分量 ===
    Eigen::Matrix3d R = T.rotation();
    Eigen::Vector3d t = T.translation();
    std::cout << "旋转矩阵:\n" << R << "\n";
    std::cout << "平移向量: " << t.transpose() << "\n\n";

    // === 变换的逆 ===
    Eigen::Isometry3d T_inv = T.inverse();
    std::cout << "T * T_inv 误差（应≈0）: "
              << (T.matrix() * T_inv.matrix() - Eigen::Matrix4d::Identity()).norm() << "\n\n";

    // === 变换复合 ===
    Eigen::Isometry3d T1 = Eigen::Isometry3d::Identity();
    T1.rotate(Eigen::AngleAxisd(M_PI / 6, Eigen::Vector3d::UnitX()));
    T1.pretranslate(Eigen::Vector3d(0.5, 0, 0));

    Eigen::Isometry3d T_total = T * T1;  // 先应用 T1，再应用 T

    return 0;
}
```

### 3.6 仿射变换（Affine3d）

```cpp
#include <Eigen/Geometry>
#include <iostream>

int main() {
    // 仿射变换 = 线性变换（旋转+缩放+剪切）+ 平移
    Eigen::Affine3d A = Eigen::Affine3d::Identity();

    // 旋转
    A.rotate(Eigen::AngleAxisd(M_PI / 4, Eigen::Vector3d::UnitZ()));

    // 非均匀缩放
    A.scale(Eigen::Vector3d(2.0, 1.0, 0.5));

    // 平移
    A.pretranslate(Eigen::Vector3d(3.0, 0.0, 0.0));

    std::cout << "仿射变换矩阵:\n" << A.matrix() << "\n\n";

    // 变换点
    Eigen::Vector3d p(1, 1, 1);
    std::cout << "变换后的点: " << (A * p).transpose() << "\n";

    return 0;
}
```

---

## 4. 综合实战：点云配准（ICP 的核心步骤）

迭代最近点（ICP）算法用于将两组点云对齐。其核心是：给定对应点对，求最优刚体变换。

```cpp
#include <Eigen/Dense>
#include <Eigen/Geometry>
#include <iostream>
#include <random>

// 计算从 src 到 dst 的最优刚体变换（给定对应点对）
// 使用 SVD 解法（Umeyama 算法的核心思路）
Eigen::Isometry3d compute_rigid_transform(
    const Eigen::MatrixXd& src,   // N×3
    const Eigen::MatrixXd& dst)   // N×3
{
    assert(src.rows() == dst.rows() && src.cols() == 3 && dst.cols() == 3);

    // 1. 计算质心
    Eigen::Vector3d src_mean = src.colwise().mean();
    Eigen::Vector3d dst_mean = dst.colwise().mean();

    // 2. 去质心
    Eigen::MatrixXd src_c = src.rowwise() - src_mean.transpose();
    Eigen::MatrixXd dst_c = dst.rowwise() - dst_mean.transpose();

    // 3. 计算协方差矩阵 H = src_c^T * dst_c
    Eigen::Matrix3d H = src_c.transpose() * dst_c;

    // 4. SVD 分解
    Eigen::JacobiSVD<Eigen::Matrix3d> svd(H,
        Eigen::ComputeFullU | Eigen::ComputeFullV);

    Eigen::Matrix3d U = svd.matrixU();
    Eigen::Matrix3d V = svd.matrixV();

    // 5. 恢复旋转矩阵（处理反射情况）
    // det(V * U^T) 应为 +1（旋转），若为 -1（反射）需修正
    double d = (V * U.transpose()).determinant();
    Eigen::Matrix3d D = Eigen::Matrix3d::Identity();
    D(2, 2) = (d > 0) ? 1.0 : -1.0;  // 处理反射

    Eigen::Matrix3d R = V * D * U.transpose();

    // 6. 计算平移
    Eigen::Vector3d t = dst_mean - R * src_mean;

    // 7. 构建变换矩阵
    Eigen::Isometry3d T = Eigen::Isometry3d::Identity();
    T.linear() = R;
    T.translation() = t;

    return T;
}

int main() {
    std::mt19937 rng(42);
    std::normal_distribution<double> noise(0.0, 0.01);

    // 创建源点云
    int N = 100;
    Eigen::MatrixXd src(N, 3);
    src = Eigen::MatrixXd::Random(N, 3);

    // 定义一个真实变换（旋转 30° + 平移）
    Eigen::Isometry3d T_true = Eigen::Isometry3d::Identity();
    T_true.rotate(Eigen::AngleAxisd(M_PI / 6, Eigen::Vector3d(0, 0, 1)));
    T_true.pretranslate(Eigen::Vector3d(0.5, -0.3, 0.1));

    // 生成目标点云（应用真实变换 + 少量噪声）
    Eigen::MatrixXd dst(N, 3);
    for (int i = 0; i < N; ++i) {
        Eigen::Vector3d pt = T_true * src.row(i).transpose();
        dst.row(i) = (pt + Eigen::Vector3d(noise(rng), noise(rng), noise(rng))).transpose();
    }

    // 计算最优变换
    Eigen::Isometry3d T_est = compute_rigid_transform(src, dst);

    // 评估误差
    std::cout << "真实旋转矩阵:\n" << T_true.rotation() << "\n\n";
    std::cout << "估计旋转矩阵:\n" << T_est.rotation() << "\n\n";
    std::cout << "真实平移: " << T_true.translation().transpose() << "\n";
    std::cout << "估计平移: " << T_est.translation().transpose() << "\n\n";

    // 旋转误差（Frobenius 范数）
    double R_err = (T_est.rotation() - T_true.rotation()).norm();
    double t_err = (T_est.translation() - T_true.translation()).norm();
    std::cout << "旋转误差: " << R_err << "\n";   // 应接近 0（噪声导致少量误差）
    std::cout << "平移误差: " << t_err << "\n";

    // 应用估计变换
    Eigen::MatrixXd src_aligned(N, 3);
    for (int i = 0; i < N; ++i)
        src_aligned.row(i) = (T_est * src.row(i).transpose()).transpose();

    double rmse = (src_aligned - dst).rowwise().norm().mean();
    std::cout << "\n点云对齐 RMSE: " << rmse << "\n";

    return 0;
}
```

---

## 5. 矩阵函数模块

```cpp
#include <Eigen/Dense>
#include <Eigen/MatrixFunctions>
#include <iostream>

int main() {
    Eigen::Matrix3d A;
    A << 0,  1,  0,
        -1,  0,  0,
         0,  0,  0;
    // A 是 so(3) 李代数中的一个元素（反对称矩阵）

    // 矩阵指数 exp(A)：李代数 → 李群（旋转矩阵）
    // 对于反对称矩阵 A = [θ]×，exp(A) 是绕轴旋转 θ 弧度的旋转矩阵
    Eigen::Matrix3d R = A.exp();

    std::cout << "exp(A) =\n" << R << "\n\n";
    std::cout << "R^T R 误差（应≈0）: "
              << (R * R.transpose() - Eigen::Matrix3d::Identity()).norm() << "\n";
    std::cout << "det(R) = " << R.determinant() << " （应≈1）\n\n";

    // 矩阵对数 log(R)：李群 → 李代数
    Eigen::Matrix3d A_recovered = R.log();
    std::cout << "log(exp(A)) 误差（应≈0）: " << (A_recovered - A).norm() << "\n\n";

    // 矩阵平方根
    Eigen::Matrix4d B = Eigen::Matrix4d::Random();
    B = B.transpose() * B + Eigen::Matrix4d::Identity(); // 对称正定
    Eigen::Matrix4d B_sqrt = B.sqrt();
    std::cout << "B_sqrt^2 ≈ B 误差: " << (B_sqrt * B_sqrt - B).norm() << "\n";

    return 0;
}
```

---

## 小结

| 功能 | 使用场景 | API |
|---|---|---|
| 通用特征值分解 | 一般实矩阵 | `Eigen::EigenSolver<>` |
| 对称特征值分解 | 协方差矩阵、Hessian 矩阵 | `Eigen::SelfAdjointEigenSolver<>` |
| SVD（小矩阵）| 最高精度，伪逆，低秩近似 | `Eigen::JacobiSVD<>` |
| SVD（大矩阵）| 高效处理大型矩阵 | `Eigen::BDCSVD<>` |
| 旋转矩阵 | 直接线性变换 | `Eigen::Matrix3d`，`AngleAxisd` |
| 四元数 | 插值、ROS、SLAM | `Eigen::Quaterniond` |
| 刚体变换 | 点云、机器人坐标系 | `Eigen::Isometry3d` |
| 仿射变换 | 含非均匀缩放的变换 | `Eigen::Affine3d` |
| 矩阵函数 | 李群/李代数转换 | `<Eigen/MatrixFunctions>` |

下一篇将讲解稀疏矩阵、迭代法求解器、性能优化技巧，以及完整的卡尔曼滤波实战。
