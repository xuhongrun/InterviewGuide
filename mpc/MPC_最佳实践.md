# MPC 最佳实践

> 模型预测控制（MPC）从理论到工程落地的最佳实践清单：覆盖建模、离散化、约束、QP 求解、warm start、可行性、稳定性、调参、嵌入式部署、调试。
>
> 配套：[MPC 概念入门](MPC_01_概念与直觉入门.md) / [QP 构建与求解](MPC_03_QP问题构建与求解.md) / [OSQP 与软约束](MPC_04_OSQP求解器_软约束与实时保障.md) / [非线性 MPC](MPC_05_非线性MPC_自行车模型与序列线性化.md) / [工程实践](MPC_06_工程实践_调参鲁棒性与嵌入式部署.md) / [现场调试](MPC_09_现场调试指南.md)

---

## 一、建模

### ✅ 推荐

- **状态选取最小化**：能写小写大模型只会拖慢求解。机器人侧最常用：
  - 横向控制：$x = [e_y, \dot{e}_y, e_\psi, \dot{e}_\psi]$；
  - 纵向控制：$x = [v, a]$；
  - 自行车模型：$x = [x, y, \psi, v]$，$u = [\delta, a]$；
- **输入选取贴近执行器物理量**：$\delta$（前轮转角）、$a$（加速度）— 而非高阶抽象；
- **车辆 / 机器人坐标**：横向控制用 **Frenet (s, l)** 简化车道跟踪；
- **建立误差状态模型**：跟踪问题统一用 $\tilde{x} = x - x_{ref}$，目标变成调节问题；
- **物理量量纲归一化**：把状态量缩放到同量级（典型 [-1, 1]），便于权重调参。

### ❌ 反模式

- 把整车 14 自由度全塞进 horizon 20 的 MPC（求解必超时）；
- 用神经网络黑箱模型直接做 MPC（除非用 RL/学习型 MPC，并配特殊求解器）；
- 不归一化状态 → 权重 Q 跨数量级，难调。

---

## 二、离散化

| 方法 | 适用 |
|------|------|
| **零阶保持 (ZOH)** | 离散时间 LTI，最常用 |
| 前向欧拉 | 简单但精度低，仅 $T_s$ 极小才稳 |
| 龙格-库塔 RK4 | 非线性高精度，嵌入式偏重 |
| 隐式离散 / Trapezoidal | 数值稳定，但矩阵更复杂 |

经验：
- 采样周期 $T_s$ 取**控制器频率的倒数**（控制 100 Hz → $T_s = 10$ ms）；
- $T_s$ 必须 ≪ 系统主导时间常数（一般 1/10）；
- horizon 长度 $N$ 满足 $N \cdot T_s \approx 1\sim3$ 倍系统响应时间；
- 自动驾驶常用 $T_s = 50$ ms、$N = 20\sim40$。

---

## 三、约束设计

### 必须设的约束

| 类型 | 例子 | 备注 |
|------|------|------|
| 输入边界 | $\delta \in [-30°, 30°]$、$a \in [-3, 2]$ m/s² | 防止把执行器烧了 |
| 输入变化率 | $|\Delta \delta| \le 5°$/step | 平滑性 + 执行器寿命 |
| 状态边界 | $|v| \le v_{max}$、$|e_y| \le 0.5$ m | 安全护栏 |
| 障碍/走廊 | $a_l \le f_{lat}(x) \le b_l$ | 用走廊约束（详见 [MPC 自动驾驶](MPC_10_自动驾驶_Frenet_走廊_SCP.md)） |

### ✅ 推荐：硬约束 + 软约束

- **硬约束**：物理 / 安全极限（执行器、几何）；
- **软约束**：跟踪误差、舒适度，**加 slack 变量**：
  $$ a \le f(x) + s, \quad s \ge 0, \quad J += \rho \|s\|_2^2 + \mu \|s\|_1$$
- **slack 上界**也设：避免松到天上去；
- 对状态约束几乎都用软约束（QP 才不会 infeasible）。

详见 [OSQP 求解器与软约束](MPC_04_OSQP求解器_软约束与实时保障.md)。

---

## 四、目标函数

经典二次型代价：
$$J = \sum_{k=0}^{N-1} \big( \tilde{x}_k^T Q \tilde{x}_k + u_k^T R u_k + \Delta u_k^T R_{\Delta} \Delta u_k \big) + \tilde{x}_N^T P \tilde{x}_N$$

权重设计原则：

| 权重 | 作用 | 调参顺序 |
|------|------|----------|
| $Q$ | 跟踪精度 | 先调，越大越紧跟 |
| $R$ | 控制大小 | 太小执行器抖、太大跟不动 |
| $R_\Delta$ | 输入平滑 | 解决高频抖动 |
| $P$ | 终端代价 | LQR Riccati 解（保稳定） |

经验：
- **从对角矩阵起步**：$Q = \text{diag}(...)$，分别调每个状态权重；
- 量级要对：$Q_{ii} \cdot x_{i,max}^2 \approx R_{jj} \cdot u_{j,max}^2$；
- $P = $ LQR Riccati 解 → 提供"看不见的尾部"代价（详见 [稳定性证明](MPC_02_5_稳定性证明_Lyapunov_终端约束_递归可行性.md)）。

---

## 五、QP 求解器选择

| 求解器 | 优势 | 场景 |
|--------|------|------|
| **OSQP** | 开源、ADMM、热启动好、嵌入式友好 | 工业默认 |
| **qpOASES** | active-set，小规模解析最优 | 嵌入式实时 |
| **HPIPM** | 基于 BLAS，高性能 dense/sparse | 高维 / 多步 |
| **acados** | 一站式 NMPC 框架，封装多个 QP solver | NMPC 部署 |
| **CasADi + ipopt** | 通用非线性 | 仿真 / 原型 |
| **ECOS / CLARABEL** | SOCP / 凸优化更广 | 走廊+椭球约束 |
| **Gurobi / MOSEK** | 商业，可处理 MIP | 离线 / 决策层 |

选择：
- 100 Hz + 数十变量 + 凸 QP → **OSQP**；
- 1 kHz + 极小规模 → **qpOASES**；
- NMPC 实时 → **acados**（自动代码生成）。

---

## 六、Warm Start（热启动）

**最重要的实时性技巧**之一：

- 上一周期解 $u^*$ 平移一格作为本周期初值（shift initial guess）；
- OSQP / qpOASES 内部状态保持，避免冷启动迭代；
- 数据结构改变（约束矩阵稀疏模式）会失效，**保持稀疏模式不变**；
- 实测：warm start 比 cold start 快 3~10 倍。

```cpp
osqp.setup(P, q, A, l, u, settings);
// 每周期：
osqp.update_lin_cost(q_new);
osqp.update_bounds(l_new, u_new);
osqp.warm_start(x_prev_shifted, y_prev_shifted);
osqp.solve();
```

---

## 七、可行性与回退（Recursive Feasibility）

MPC 在线求解可能 infeasible：

| 原因 | 处理 |
|------|------|
| 状态约束硬 + 扰动大 | **软化状态约束** |
| 终端约束太紧 | 终端集放宽 / 用终端代价替代 |
| 模型/线性化误差 | 重新线性化、缩短 horizon |
| 数值精度 | 缩放、检查矩阵条件数 |

**回退策略**（求解失败时）：

1. 上次解平移使用一周期；
2. 切换到备用控制器（PID / Pure Pursuit）；
3. 减速 / 紧急停车（最高优先级安全）；
4. 重置 warm start，重新冷启动。

详见 [稳定性证明](MPC_02_5_稳定性证明_Lyapunov_终端约束_递归可行性.md)、[现场调试指南](MPC_09_现场调试指南.md)。

---

## 八、非线性 MPC（NMPC）

策略选择：
- **序列线性化（SQP / SCP）**：每周期围绕预测轨迹线性化 → 求 QP；
- **直接非线性求解器（IPOPT / acados SQP_RTI）**；
- **Real-Time Iteration（RTI）**：每周期只迭代一次 SQP，工程平衡；
- **Multiple Shooting** > Single Shooting（数值更稳）。

实践：
- 先线性 MPC 跑通，再升级 NMPC；
- 自动驾驶横向 → 自行车模型 SCP / RTI 是工业最常用；
- acados 自动代码生成嵌入式可部署。

详见 [非线性 MPC](MPC_05_非线性MPC_自行车模型与序列线性化.md)。

---

## 九、嵌入式部署

| 项目 | 实践 |
|------|------|
| 求解器 | OSQP / acados（带代码生成） |
| 浮点 | 优先 double，确认精度后可降 float |
| 内存 | **静态分配**，不在 update 内 malloc |
| 数学库 | BLIS / Eigen + `-O3 -DNDEBUG` |
| 调度 | SCHED_FIFO + chrt 80；CPU isolation |
| RTOS | PREEMPT_RT Linux / QNX / FreeRTOS |
| 频率 | 控制频率与求解时间留 30% 余量 |
| 看门狗 | 求解超时 → 立即触发回退 |

代码生成：
- `acados` 一键生成 C 代码 → 工业最常见；
- OSQP 也支持 codegen（embedded mode）；
- 静态稀疏模式，禁止动态 resize。

详见 [工程实践_调参鲁棒性与嵌入式部署](MPC_06_工程实践_调参鲁棒性与嵌入式部署.md)。

---

## 十、调参方法论

**步骤**（一定按顺序）：

1. **建好仿真环境**（含执行器延迟、扰动、噪声）；
2. **离散化 + 模型验证**：开环阶跃 vs 实测；
3. **从 LQR 起步**：用 $Q, R$ 同 LQR，让 MPC 退化为 LQR + 约束；
4. 渐进加约束 → 每加一项跑回归；
5. 把 $R_\Delta$ 拉够，**先平滑再追跟踪**；
6. 上车前在 bag 数据上**离线回放调参**；
7. 上车小步加速度，先看横向再看纵向；
8. 极限工况测试（满载、湿地、低速、高速）。

---

## 十一、与 ROS 集成

ROS 节点架构（ROS2 推荐）：
```
/odometry  ─┐
/path      ─┼─→ MPCNode ─→ /cmd_vel 或 /steering, /accel
/obstacles ─┘
```

要点：
- MPC 在**单独线程**周期跑，不阻塞回调；
- 用 **realtime_tools::RealtimeBuffer** 跨线程传参考轨迹；
- 控制周期内**不分配内存、不日志、不锁**；
- 用 ROS2 lifecycle：`on_activate` 初始化求解器；`on_deactivate` 释放回退；
- 求解器超时 → diagnostic_updater WARN + 回退控制器；
- bag 录制 `mpc_debug` topic（含预测轨迹、目标、cost、求解时间）便于回放分析。

参考 [ROS2 ros2_control 进阶](../ros/ros2/ROS2%20ros2_control进阶.md) 中实时编程章节。

---

## 十二、调试可视化

**必须发布**的调试 topic：
- `/mpc/predicted_path`（预测轨迹 nav_msgs/Path）— RViz 直观；
- `/mpc/reference`（参考轨迹）；
- `/mpc/cost`（每周期 cost 曲线）；
- `/mpc/solve_time_ms`、`/mpc/iterations`、`/mpc/status`；
- `/mpc/slack`（软约束触发量）。

工具：
- **PlotJuggler**：cost / 跟踪误差 / 求解时间时序；
- **Foxglove**：在线 + bag 离线复盘；
- **Python 离线脚本**：从 bag 提取预测 vs 实际，作误差统计。

详见 [现场调试指南](MPC_09_现场调试指南.md)。

---

## 十三、与其他控制器对比时机

| 场景 | 推荐 |
|------|------|
| 轻度跟踪 / 教学 | PID / Pure Pursuit |
| 高速 + 低曲率 | Stanley / LQR |
| 多约束 / 高曲率 / 风险高 | **MPC** |
| 含混合整数（换道决策） | MIQP MPC（离线决策更常见） |
| 系统模型未知 | 学习型 MPC / RL |
| 严重非线性 | NMPC + acados |

不要为了用 MPC 而 MPC：能 PID 解决就别上。

---

## 十四、常见坑速查

| 现象 | 排查 |
|------|------|
| 求解发散 / NaN | 模型矩阵条件数；归一化状态；warm start 状态被脏 |
| 高频抖动 | $R_\Delta$ 太小；执行器延迟未建模；微分项噪声 |
| 跟踪滞后 | horizon 太短；$Q$ 偏小；控制频率不够；前馈缺失 |
| 时常 infeasible | 状态约束没软化；终端约束太紧 |
| 求解超时 | 没 warm start；horizon 过长；矩阵不稀疏 |
| 仿真好实车坏 | 模型与实车不匹配；执行器延迟 / 死区；噪声未建模 |
| 急停时过冲 | 输入率约束太松；终端代价不到位 |

---

## 十五、Top 20 Checklist

建模：
- [ ] 状态最小化 + 归一化
- [ ] $T_s$ 与 horizon 合理（$N \cdot T_s \approx 1\sim3$ 倍系统时间常数）
- [ ] 离散化 ZOH / RK4

约束：
- [ ] 输入边界 + 输入变化率
- [ ] 状态约束**软化**（slack）
- [ ] 走廊 / 障碍约束

求解：
- [ ] 选 OSQP / acados / qpOASES
- [ ] **warm start** 启用
- [ ] 终端代价 $P$ 用 LQR Riccati
- [ ] 求解器超时回退策略

工程：
- [ ] 静态内存分配
- [ ] 单独线程 + RealtimeBuffer
- [ ] 不在 update 内分配 / 日志 / 锁
- [ ] PREEMPT_RT + chrt
- [ ] 看门狗超时

调试：
- [ ] 发布预测/参考/cost/求解时间
- [ ] PlotJuggler + Foxglove 可视化
- [ ] bag 录制可离线复盘
- [ ] 仿真闭环回归测试
- [ ] 渐进上车（仿真 → bag → 低速 → 满载）

---

## 十六、面试速记

1. **MPC = 优化驱动的控制 = 滚动 horizon QP**；
2. 三大杀手：**warm start / 软约束 / 终端代价**；
3. 离散化用 ZOH；状态尽量小；归一化必备；
4. OSQP 默认；高维 acados / HPIPM；NMPC 上 RTI；
5. **回退策略**比单点性能更重要：超时立刻切 PID/急停；
6. 调参从 LQR 起步，渐进加约束；
7. ROS 集成：单独线程 + RealtimeBuffer + lifecycle + 调试 topic；
8. 嵌入式：静态分配 + 代码生成 + PREEMPT_RT；
9. 横向 + Frenet + 走廊约束 = 自动驾驶 MPC 工业范式；
10. 不要为了 MPC 而 MPC，能 PID 就 PID。
