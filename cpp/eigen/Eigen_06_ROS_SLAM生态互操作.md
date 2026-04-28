# Eigen C++ 线性代数库（六）：ROS / SLAM 生态互操作

> **系列导航**
> - 第一篇：入门与基本类型
> - 第二篇：矩阵与向量操作详解
> - 第三篇：线性方程组求解与矩阵分解
> - 第四篇：特征值分解、SVD 与几何变换
> - 第五篇：稀疏矩阵、性能优化与工程实战
> - **第六篇：ROS / SLAM 生态互操作** ← 当前
> - 第七篇：unsupported 模块与非线性优化

---

## 1. 为什么这一篇重要？

机器人 / 自动驾驶 / SLAM 项目里，Eigen 几乎是事实标准的「中间表示」。但实际工程代码 90% 的时间不是在写 `A*x=b`，而是在 **Eigen 与各类库的相互转换**：

```
传感器驱动                                      上层算法
  │                                                  │
  ▼                                                  ▼
ROS msg ─┐                                  ┌─ Ceres / g2o
PCL      │   ←── Eigen Isometry/Matrix ──→  │  Sophus
OpenCV ──┘                                  └─ 自定义 EKF
```

本篇覆盖工程里最常踩的转换坑。

---

## 2. 位姿表示的选择：`Matrix4d` vs `Affine3d` vs `Isometry3d`

| 类型 | 数学含义 | 推荐场景 |
|---|---|---|
| `Eigen::Matrix4d` | 任意 4×4 矩阵，无几何约束 | 通用计算、自己控制结构 |
| `Eigen::Affine3d` | 仿射变换（旋转+平移+**缩放/剪切**）| 需要缩放的场景，例如可视化 |
| `Eigen::Isometry3d` | **刚体变换**（仅旋转+平移）| ⭐ 机器人/SLAM 首选 |
| `Eigen::Transform<double,3,Projective>` | 投影变换（含透视）| 相机投影、SfM |

**为什么 SLAM 几乎一律用 `Isometry3d`**：

```cpp
#include <Eigen/Geometry>

Eigen::Isometry3d T = Eigen::Isometry3d::Identity();
T.linear()      = R;          // 3x3 旋转部分
T.translation() = t;          // 3x1 平移部分

// 1) 逆变换是 O(1) 的：T^-1 = [R^T, -R^T t; 0, 1]
Eigen::Isometry3d T_inv = T.inverse();   // Isometry 对 inverse() 有快速实现

// 2) 与 Vector3d 复合时自动处理齐次坐标
Eigen::Vector3d p_world = T * p_local;   // 不需要手动加 1 再扔掉

// 3) 链式乘法返回的还是 Isometry3d，不会"退化"成普通矩阵
Eigen::Isometry3d T_ab = T_a * T_b;
```

> **面试坑**：用 `Matrix4d` 求逆 `inverse()` 走的是通用 LU，比 `Isometry3d::inverse()` 慢一个数量级，且数值稳定性更差。

### 2.1 旋转表示三件套

```cpp
// 三种等价表示之间的转换
Eigen::AngleAxisd  aa(M_PI / 4, Eigen::Vector3d::UnitZ());
Eigen::Quaterniond q(aa);                     // AngleAxis -> Quaternion
Eigen::Matrix3d    R = aa.toRotationMatrix(); // AngleAxis -> Matrix
Eigen::Quaterniond q2(R);                     // Matrix -> Quaternion
Eigen::AngleAxisd  aa2(q);                    // Quaternion -> AngleAxis

// Roll-Pitch-Yaw（ZYX 内旋顺序，自动驾驶最常用）
double roll = 0.1, pitch = 0.2, yaw = 0.3;
Eigen::Matrix3d R_rpy =
    (Eigen::AngleAxisd(yaw,   Eigen::Vector3d::UnitZ()) *
     Eigen::AngleAxisd(pitch, Eigen::Vector3d::UnitY()) *
     Eigen::AngleAxisd(roll,  Eigen::Vector3d::UnitX())).toRotationMatrix();

// 反向：Matrix -> Euler。注意 eulerAngles 返回的角度范围/顺序约定
Eigen::Vector3d ypr = R_rpy.eulerAngles(2, 1, 0);   // (yaw, pitch, roll)
```

> **强烈建议**：内部一律用 `Quaterniond` 或 `Isometry3d` 存储，仅在需要可读输出时再转 RPY。Euler 角的奇异点（万向节锁）和符号约定差异在工程中是 bug 重灾区。

---

## 3. 四元数的存储顺序坑（必考）

`Eigen::Quaterniond` 的内部存储顺序是 `[x, y, z, w]`，但**构造函数是 `(w, x, y, z)`**：

```cpp
// 构造时：先写实部 w
Eigen::Quaterniond q1(1.0, 0.0, 0.0, 0.0);     // 单位四元数 (w=1, x=0, y=0, z=0)

// 但 .coeffs() 返回的顺序是 [x, y, z, w]
std::cout << q1.coeffs().transpose();           // 输出: 0 0 0 1
//                                                       ↑ ↑ ↑ ↑
//                                                       x y z w

// 与 ROS / 其他库交互时务必确认顺序
double x = q1.x(), y = q1.y(), z = q1.z(), w = q1.w();
```

| 库 | 四元数顺序 |
|---|---|
| Eigen 构造函数 | `(w, x, y, z)` |
| Eigen `.coeffs()` 内存布局 | `[x, y, z, w]` |
| ROS `geometry_msgs::Quaternion` | `(x, y, z, w)` |
| Ceres 参数块（`QuaternionParameterization`）| `(w, x, y, z)` |
| Ceres 参数块（`EigenQuaternionParameterization`）| `(x, y, z, w)`（与 Eigen 内存布局一致）|

> 这张表建议背下来。Ceres 默认 `QuaternionParameterization` 与 Eigen 内存布局**不一致**，必须用 `EigenQuaternionParameterization` 才能让 `Eigen::Map<Eigen::Quaterniond>` 直接绑定参数块。

---

## 4. ROS / ROS2 互操作

### 4.1 `tf2_eigen`：标准转换桥

ROS 官方包 `tf2_eigen` 提供 `geometry_msgs` 与 Eigen 类型的双向转换：

```cpp
#include <tf2_eigen/tf2_eigen.hpp>     // ROS2
// #include <tf2_eigen/tf2_eigen.h>    // ROS1

// geometry_msgs::Pose ↔ Eigen::Isometry3d
geometry_msgs::msg::Pose pose_msg = /* ... */;
Eigen::Isometry3d T;
tf2::fromMsg(pose_msg, T);

geometry_msgs::msg::Pose pose_back = tf2::toMsg(T);

// geometry_msgs::Vector3 ↔ Eigen::Vector3d
geometry_msgs::msg::Vector3 v_msg;
Eigen::Vector3d v_eigen;
tf2::fromMsg(v_msg, v_eigen);
v_msg = tf2::toMsg(v_eigen);

// geometry_msgs::Quaternion ↔ Eigen::Quaterniond（注意顺序自动处理）
geometry_msgs::msg::Quaternion q_msg;
Eigen::Quaterniond q;
tf2::fromMsg(q_msg, q);
```

### 4.2 手写转换（不依赖 tf2）

不引入 tf2 时的标准模板（生产代码常见）：

```cpp
inline Eigen::Isometry3d pose_to_eigen(const geometry_msgs::msg::Pose& p) {
    Eigen::Isometry3d T = Eigen::Isometry3d::Identity();
    T.translation() << p.position.x, p.position.y, p.position.z;
    Eigen::Quaterniond q(p.orientation.w, p.orientation.x,
                         p.orientation.y, p.orientation.z);
    T.linear() = q.toRotationMatrix();
    return T;
}

inline geometry_msgs::msg::Pose eigen_to_pose(const Eigen::Isometry3d& T) {
    geometry_msgs::msg::Pose p;
    p.position.x = T.translation().x();
    p.position.y = T.translation().y();
    p.position.z = T.translation().z();
    Eigen::Quaterniond q(T.linear());
    p.orientation.w = q.w();
    p.orientation.x = q.x();
    p.orientation.y = q.y();
    p.orientation.z = q.z();
    return p;
}
```

### 4.3 `nav_msgs::Odometry` 实战

```cpp
void odomCallback(const nav_msgs::msg::Odometry::SharedPtr msg) {
    // 1. 位姿
    Eigen::Isometry3d T_odom = pose_to_eigen(msg->pose.pose);

    // 2. 协方差（行主序 6x6 -> Eigen 列主序矩阵）
    using Mat6d = Eigen::Matrix<double, 6, 6, Eigen::RowMajor>;
    Eigen::Map<const Mat6d> cov_map(msg->pose.covariance.data());
    Eigen::Matrix<double, 6, 6> cov = cov_map;   // 复制并转列主序

    // 3. 速度
    Eigen::Vector3d linear_vel(msg->twist.twist.linear.x,
                               msg->twist.twist.linear.y,
                               msg->twist.twist.linear.z);
}
```

> **协方差坑**：ROS 协方差是 `std::array<double, 36>` 行主序；Eigen 默认列主序。
> 必须显式用 `Eigen::RowMajor` 模板参数，否则取出的矩阵是转置的——对协方差不影响（对称），但对状态转移类矩阵会出 bug。

---

## 5. PCL 互操作

PCL 内部本身就基于 Eigen，因此互转大多是零拷贝。

### 5.1 单点

```cpp
#include <pcl/point_types.h>

pcl::PointXYZ p_pcl;
p_pcl.x = 1; p_pcl.y = 2; p_pcl.z = 3;

// PCL Point -> Eigen
Eigen::Vector3f v = p_pcl.getVector3fMap();   // 引用！修改 v 会改 p_pcl
Eigen::Vector4f vh = p_pcl.getVector4fMap();  // 齐次坐标，最后一位是 1.f

// Eigen -> PCL Point
Eigen::Vector3f v2(4, 5, 6);
p_pcl.getVector3fMap() = v2;                   // 反向赋值
```

### 5.2 整个点云（关键性能技巧）

```cpp
pcl::PointCloud<pcl::PointXYZ>::Ptr cloud(new pcl::PointCloud<pcl::PointXYZ>);
// ... 填入 N 个点 ...

// 把整个点云映射成 4xN 的 Eigen 矩阵（齐次坐标，零拷贝）
Eigen::Map<Eigen::Matrix<float, 4, Eigen::Dynamic, Eigen::ColMajor>>
    M(reinterpret_cast<float*>(cloud->points.data()), 4, cloud->size());

// 现在可以批量做 Eigen 运算
Eigen::Matrix4f T = /* ... */;
M = T * M;     // 一次完成所有点的刚体变换（向量化）
```

> 注意：`pcl::PointXYZ` 内部是 `float[4]`（含 padding），所以可以安全地按 4 行映射。
> 对 `pcl::PointXYZRGB` 等含 RGB 字段的类型不能这样做。

### 5.3 PCL 的变换函数

```cpp
#include <pcl/common/transforms.h>

Eigen::Affine3f T = Eigen::Affine3f::Identity();
T.translation() << 1, 2, 3;
T.rotate(Eigen::AngleAxisf(M_PI / 4, Eigen::Vector3f::UnitZ()));

pcl::PointCloud<pcl::PointXYZ>::Ptr out(new pcl::PointCloud<pcl::PointXYZ>);
pcl::transformPointCloud(*cloud, *out, T);
```

> 性能提示：`pcl::transformPointCloud` 内部就是用 Eigen + SIMD 实现的批量变换，
> 自己用 for 循环逐点 `T * p` **慢一个数量级**。

---

## 6. OpenCV 互操作

### 6.1 `cv::cv2eigen` / `eigen2cv`

```cpp
#include <opencv2/core/eigen.hpp>      // 必须！

cv::Mat cv_mat = cv::Mat::eye(3, 3, CV_64F);
Eigen::MatrixXd eigen_mat;
cv::cv2eigen(cv_mat, eigen_mat);       // OpenCV -> Eigen（拷贝）

Eigen::Matrix3d M = Eigen::Matrix3d::Random();
cv::Mat cv_back;
cv::eigen2cv(M, cv_back);              // Eigen -> OpenCV（拷贝）
```

### 6.2 零拷贝映射（高频）

```cpp
// OpenCV 是行主序，必须用 RowMajor 的 Eigen 类型才能零拷贝
cv::Mat img = cv::Mat::zeros(480, 640, CV_32F);

using RowMat = Eigen::Matrix<float, Eigen::Dynamic, Eigen::Dynamic, Eigen::RowMajor>;
Eigen::Map<RowMat> view(img.ptr<float>(), img.rows, img.cols);
// view 与 img 共享内存，可双向修改

view.row(0).setOnes();   // OpenCV 第一行也变 1
```

### 6.3 相机内参矩阵约定

```cpp
// OpenCV 的 cameraMatrix 是 3x3 CV_64F，行主序：
//   [ fx  0  cx ]
//   [ 0  fy  cy ]
//   [ 0   0   1 ]
cv::Mat K_cv = (cv::Mat_<double>(3, 3) << 525, 0, 320,
                                          0, 525, 240,
                                          0,   0,   1);

Eigen::Matrix3d K;
cv::cv2eigen(K_cv, K);     // 转换后元素值正确（不会因主序差异错位）

// 反投影
Eigen::Vector3d uv1(u, v, 1.0);
Eigen::Vector3d xyz_norm = K.inverse() * uv1;   // 实际工程应预存 K_inv，避免每帧求逆
```

---

## 7. Sophus 与李代数

Sophus 是基于 Eigen 的 SO(3) / SE(3) 李群库，被 ORB-SLAM3、DSO、VINS-Mono 等广泛使用。

```cpp
#include <sophus/se3.hpp>

// 从 Eigen 构造
Eigen::Matrix3d R = /* ... */;
Eigen::Vector3d t = /* ... */;
Sophus::SE3d T(R, t);

// 取回 Eigen
Eigen::Matrix4d T_mat = T.matrix();
Eigen::Quaterniond q  = T.unit_quaternion();

// 李代数：SE(3) 的对数（6 维向量 [translation; rotation]）
Eigen::Matrix<double, 6, 1> xi = T.log();
Sophus::SE3d T_back = Sophus::SE3d::exp(xi);

// 增量更新（位姿优化的核心操作）
Eigen::Matrix<double, 6, 1> dx = ...;       // 优化器算出的增量
T = Sophus::SE3d::exp(dx) * T;              // 左扰动模型
```

> 为什么不用 `Eigen::Isometry3d`？因为 Isometry 没有 `log()` / `exp()` / 雅可比，
> 而非线性优化（LM / Gauss-Newton）需要在切空间上更新。

---

## 8. Ceres Solver 中的 Eigen 用法

Ceres 的参数块是裸 `double*`，需要用 `Eigen::Map` 套上：

```cpp
struct ReprojectionError {
    template <typename T>
    bool operator()(const T* const camera_q,    // 4 维 (x,y,z,w) — Eigen 顺序
                    const T* const camera_t,    // 3 维
                    const T* const point,       // 3 维
                    T* residuals) const {
        // 用 Map 把裸指针套成 Eigen 类型，零拷贝
        Eigen::Map<const Eigen::Quaternion<T>> q(camera_q);
        Eigen::Map<const Eigen::Matrix<T, 3, 1>> t(camera_t);
        Eigen::Map<const Eigen::Matrix<T, 3, 1>> p(point);
        Eigen::Map<Eigen::Matrix<T, 2, 1>> r(residuals);

        Eigen::Matrix<T, 3, 1> p_cam = q * p + t;
        T u = fx_ * p_cam.x() / p_cam.z() + cx_;
        T v = fy_ * p_cam.y() / p_cam.z() + cy_;
        r << u - T(observed_u_), v - T(observed_v_);
        return true;
    }
    // ...
};

// 关键：必须用 EigenQuaternionParameterization，否则内存顺序不一致
problem.SetManifold(camera_q, new ceres::EigenQuaternionManifold);
```

> Ceres 默认 `QuaternionManifold` 的内存顺序是 `(w,x,y,z)`，
> 而 `EigenQuaternionManifold` 是 `(x,y,z,w)`——和 Eigen `.coeffs()` 一致。

---

## 9. 实战清单：跨库工程模板

写一个新的机器人节点时，建议遵循以下规则：

```cpp
// ❌ 不要在内部用各种异构类型互调
// 输入：tf2::Transform
// 中间：Eigen::Matrix4d
// 计算：cv::Mat
// 输出：geometry_msgs::Pose
// → 转换链 N 次，性能差且容易出 bug

// ✅ 推荐架构：
// 1) 接口边界：消息类型（geometry_msgs / sensor_msgs）
// 2) 内部表示：统一用 Eigen::Isometry3d（位姿）+ Eigen::Vector3d（点）
//              + Sophus::SE3d（需优化时）
// 3) 与第三方库（PCL / OpenCV）交互时再做转换，且用 Map 零拷贝
// 4) 协方差永远用 RowMajor map 显式标注

class MyNode {
    // 内部态：清一色 Eigen
    Eigen::Isometry3d T_world_robot_ = Eigen::Isometry3d::Identity();
    Eigen::Matrix<double, 6, 6> cov_ = Eigen::Matrix<double, 6, 6>::Identity();

    // 仅在 callback 边界做类型转换
    void onPose(const geometry_msgs::msg::PoseWithCovariance& msg) {
        T_world_robot_ = pose_to_eigen(msg.pose);
        using Mat6dRM = Eigen::Matrix<double, 6, 6, Eigen::RowMajor>;
        cov_ = Eigen::Map<const Mat6dRM>(msg.covariance.data());
    }
};
```

---

## 小结

| 主题 | 关键点 |
|---|---|
| 位姿表示 | SLAM 优先 `Isometry3d`，需李代数用 `Sophus::SE3d` |
| 四元数顺序 | Eigen 构造 `(w,x,y,z)` / 内存 `(x,y,z,w)` / ROS msg `(x,y,z,w)` |
| ROS 消息 | 用 `tf2_eigen` 或自写 `pose_to_eigen` 模板 |
| 协方差 | 行主序 → 用 `Eigen::RowMajor` map 显式转换 |
| PCL | `getVector3fMap()` 零拷贝；批量变换用 `transformPointCloud` |
| OpenCV | `cv::cv2eigen()` / `cv::eigen2cv()`；零拷贝必须 `RowMajor` |
| Ceres | 用 `Eigen::Map` 包参数块；四元数选 `EigenQuaternionManifold` |
| 工程原则 | 边界做转换，内部统一用 Eigen |

下一篇将进入 unsupported 模块：`AutoDiff`、`NumericalDiff`、`LevenbergMarquardt` 与非线性优化。
