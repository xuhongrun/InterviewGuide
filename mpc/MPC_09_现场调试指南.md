# 第九篇：MPC 现场调试指南 —— 从仿真到实车的诊断手册

---

## 引言

MPC 在仿真完美运行，上车却抖、漂、不可行。这是 90% 工程师的真实经历。

本篇给出**三层诊断方法论**：仿真 → 半实物（HiL）→ 实车，配 5 类常见故障的排查流程，以及一套**Python 可视化工具**用于绘制 cost landscape、激活约束、求解时间分布。

---

## 一、三层诊断方法论

```
┌────────────────────────────────────────┐
│  Layer 1：仿真诊断（Sim Debug）         │
│  目标：把模型/算法本身的 bug 排干净     │
├────────────────────────────────────────┤
│  Layer 2：HiL 半实物（Hardware-in-Loop）│
│  目标：测软件实时性 + 注入扰动验证鲁棒性│
├────────────────────────────────────────┤
│  Layer 3：实车诊断（Vehicle Debug）     │
│  目标：消除 Sim-Real Gap，做参数精调   │
└────────────────────────────────────────┘
```

每层不通过，**禁止**进入下一层——许多事故来源于跳级。

---

## 二、Layer 1：仿真诊断 9 件套

### 2.1 检查项目清单

| # | 检查项 | 通过标准 |
|---|-------|---------|
| 1 | 模型连续 vs 离散一致性 | 离散步长 → 0 时离散解收敛到连续解 |
| 2 | DARE 终端权重 | 闭环极点全在单位圆内 |
| 3 | KKT 条件残差 | $\| \nabla L \|_\infty < 10^{-6}$ |
| 4 | 热启动有效性 | 第 2 步起 iter 数减半以上 |
| 5 | 约束相容 | 关闭所有约束 → 解收敛到 LQR 解 |
| 6 | Hessian 条件数 | $\kappa(H) < 10^8$ |
| 7 | 求解时间分布 | 平均 < 50% 周期、峰值 < 90% 周期 |
| 8 | 跟踪 RMSE | 优于基线（PID/LQR）至少 30% |
| 9 | 鲁棒性扫描 | $\pm 20\%$ 模型参数扰动下仍稳定 |

### 2.2 cost landscape 可视化

固定 $x_0$，扫描 $u_0, u_1$ 的二维平面，画出 $J(u_0, u_1)$ 的等高线：

```python
import numpy as np
import matplotlib.pyplot as plt

def plot_cost_landscape(mpc, x0, u_range=(-2, 2), grid=100):
    """绘制 J(u_0, u_1) 的二维等高线，固定其他控制为 0"""
    u0_grid = np.linspace(u_range[0], u_range[1], grid)
    u1_grid = np.linspace(u_range[0], u_range[1], grid)
    J = np.zeros((grid, grid))
    for i, u0 in enumerate(u0_grid):
        for j, u1 in enumerate(u1_grid):
            U = np.zeros(mpc.N)
            U[0], U[1] = u0, u1
            J[j, i] = mpc.evaluate_cost(x0, U)

    fig, ax = plt.subplots(figsize=(8, 6))
    cs = ax.contour(u0_grid, u1_grid, J, levels=30)
    ax.clabel(cs, inline=True, fontsize=8)
    # 标记最优点
    U_star = mpc.solve(x0)
    ax.plot(U_star[0], U_star[1], 'r*', markersize=15, label='optimal')
    ax.set_xlabel('u_0'); ax.set_ylabel('u_1')
    ax.set_title(f'Cost Landscape at x0={x0}')
    ax.legend()
    plt.show()
```

**用途**：
- 等高线呈"细长椭圆" → Hessian 病态（不同方向尺度差大）
- 多个局部极小 → NMPC 初值敏感问题
- 等高线与约束边界相切 → 约束激活点位置

### 2.3 激活约束可视化

```python
def plot_active_constraints(mpc_log):
    """以时间为横轴，把每步激活的约束画成色块"""
    fig, ax = plt.subplots(figsize=(12, 4))
    n_constraints = mpc_log['n_constraints']
    timesteps = len(mpc_log['active'])
    matrix = np.zeros((n_constraints, timesteps))
    for t, active_set in enumerate(mpc_log['active']):
        for idx in active_set:
            matrix[idx, t] = 1
    ax.imshow(matrix, aspect='auto', cmap='Reds', interpolation='nearest')
    ax.set_xlabel('time step'); ax.set_ylabel('constraint index')
    ax.set_title('Active Constraint Heatmap')
    plt.show()
```

**用途**：
- 某约束**长期激活** → 是性能瓶颈，考虑放宽
- 某约束**频繁切换** → 数值抖振，考虑加增量约束
- 某约束**从不激活** → 可去除以加速求解

### 2.4 求解时间分布

```python
def plot_solve_time_histogram(times_ms, deadline_ms):
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.hist(times_ms, bins=50, alpha=0.7, edgecolor='black')
    ax.axvline(deadline_ms, color='red', linestyle='--',
               label=f'deadline {deadline_ms} ms')
    ax.axvline(np.percentile(times_ms, 99), color='orange',
               linestyle='--', label='P99')
    ax.set_xlabel('Solve time (ms)'); ax.set_ylabel('Count')
    ax.legend()
    plt.show()

    print(f"Mean: {np.mean(times_ms):.2f} ms")
    print(f"P50:  {np.median(times_ms):.2f} ms")
    print(f"P99:  {np.percentile(times_ms, 99):.2f} ms")
    print(f"Max:  {np.max(times_ms):.2f} ms")
    print(f"违反 deadline 比例: {(times_ms > deadline_ms).mean()*100:.2f}%")
```

**警戒线**：P99 > 80% deadline 即需优化（Move Blocking、缩 N、热启动）。

---

## 三、Layer 2：HiL 半实物诊断

### 3.1 HiL 必查项

| 项 | 工具 | 通过标准 |
|----|------|---------|
| 实时性抖动 | RT-PREEMPT 内核、cyclictest | 周期抖动 < 5% |
| 求解超时频率 | 自家 logger | < 1/10000 |
| 内存动态分配 | Valgrind / sanitizer | 控制循环内 = 0 |
| CPU 占用 | top/htop | < 70% |
| 通信延迟 | tcpdump / can-utils | < 期望值 1.5 倍 |

### 3.2 注入扰动测试

```cpp
// 在 HiL 中注入已知扰动，验证 DOB / 积分增广能否识别
void injectStepDisturbance(double t, double amplitude) {
    if (t > 1.0 && t < 1.001) {
        plant_state(0) += amplitude;  // 在 t=1s 注入阶跃
    }
}
```

**判据**：
- 闭环响应应在 5 个采样周期内回到参考 ± 5%
- DOB 估计的扰动幅值与注入值偏差 < 10%
- 控制量平滑过渡（无阶跃跳变）

### 3.3 频率扫描（Bode 测试）

注入正弦激励 $u_{\text{exc}} = A\sin(2\pi f t)$，记录闭环响应：

```python
def closed_loop_bode(plant_log, freqs):
    """从 HiL 数据估计闭环 Bode 图"""
    mag_db, phase_deg = [], []
    for f, segment in zip(freqs, plant_log):
        # 用 FFT 提取主频率分量
        Y = np.fft.fft(segment['y'])
        U = np.fft.fft(segment['u'])
        idx = int(f * len(segment) / segment_dt)
        H = Y[idx] / U[idx]
        mag_db.append(20 * np.log10(abs(H)))
        phase_deg.append(np.angle(H, deg=True))
    return np.array(mag_db), np.array(phase_deg)
```

**用途**：
- 比较实测 vs 理论 Bode → 量化模型误差
- 检测谐振 → 加入 Notch 滤波器或调整 $R$

---

## 四、Layer 3：实车诊断

### 4.1 Sim-Real Gap 三步法

**Step 1：录制实车开环数据**

```
固定输入序列 u_record（如方波）
同时录制 u_record 与车辆响应 y_meas
```

**Step 2：仿真重放**

```
在仿真中输入相同的 u_record，得到 y_sim
对比 y_sim vs y_meas → 残差 e(t) = y_meas - y_sim
```

**Step 3：诊断残差**

| 残差特征 | 诊断 | 修复 |
|---------|------|------|
| 常值偏差 | 模型常值偏置 | 加入扰动观测器 / 偏置参数 |
| 线性增长 | 积分误差（陀螺零漂） | 校准 IMU、加积分增广 |
| 周期性 | 模型遗漏共振模 | 增加状态维度或 Notch 滤波 |
| 大幅随机 | 测量噪声或模型严重失配 | 重新做系统辨识 |
| 与速度相关 | 动力学非线性（轮胎、阻力） | 升级到动力学模型 |

### 4.2 实车精调 5 步流程

```
1. 关闭 MPC，让车手动驾驶 → 录制典型轨迹（10~30 分钟）
2. 用录制数据离线辨识模型参数 → 在仿真验证
3. 用辨识后的模型重跑 MPC 仿真 → 与实车老 MPC 对比
4. 启用 MPC 但限速 / 限转向 → 在空场测试
5. 逐步放开约束，监测 KKT 残差与 active set
```

**安全护栏**：
- 始终保留远程紧急停车开关
- MPC 输出经低通滤波后再下发（截止频率 = 控制带宽 × 1.5）
- 任何异常连续 3 帧立即降级到 PID

---

## 五、5 类典型故障的排查 SOP

### 故障 1：跟踪误差稳态偏移（不可消除）

```
诊断流程：
  ① 检查参考是否含有静态偏置（如转向 0 点偏）
  ② 启用 DOB → 查看估计扰动 d_hat 是否非零
  ③ 若 d_hat 收敛到非零 → 加积分增广或前馈
  ④ 若 d_hat 抖动 → KF 参数过于激进，调小过程噪声 Q_kf
```

### 故障 2：跟踪振荡

```
诊断流程：
  ① 求解器输出 u 是否高频振荡？
     是 → R 太小，增大 R；或加 Δu 增量惩罚
     否 → 振荡来自 plant 或闭环极点
  ② 检查闭环极点 → 接近单位圆 → DARE 失算
  ③ 检查实际控制延迟 → 加入延迟模型
  ④ 加大 N → 是否改善？没改善则模型误差是主因
```

### 故障 3：偶发不可行

```
诊断流程：
  ① 复现：记录不可行那一帧的 x_0、ref、约束矩阵 G, h
  ② 离线在 MATLAB/Python 求解 → 是 真不可行 还是 OSQP 数值问题？
     真不可行 → 软约束 + 高惩罚
     数值问题 → ρ 调整、scaling 启用
  ③ 检测约束矛盾：state lower > state upper（程序 bug）
  ④ 启用 fallback 状态机
```

### 故障 4：求解时间忽快忽慢

```
诊断流程：
  ① 时间分布是否双峰？
     是 → active set 切换导致；考虑稳定 active set 预测
  ② 慢求解时 OSQP iter 数？
     >100 → 热启动失效；冷启动一次重置
  ③ 慢求解时输入参考是否突变？
     是 → 平滑参考，或检测突变后跳过热启动
  ④ 观察 CPU 占用 → 是否被其他线程抢占？
```

### 故障 5：实车性能 < 仿真

```
诊断流程：
  ① Sim-Real Gap 三步法（4.1）→ 找出残差类型
  ② 对照修复表逐项处理
  ③ 重启动 sim 用新模型重跑 → 性能差距是否缩小？
  ④ 仍有差距 → 大概率是高频未建模动态（执行器、传感器滞后）
     → 加入 anti-aliasing 滤波 + 状态扩展
  ⑤ 若高速场景特别差 → 升级到动力学模型（见 MPC_05 附录）
```

---

## 六、实用工具清单

### 6.1 仿真层

| 工具 | 用途 |
|------|------|
| Python + Matplotlib | 可视化（cost landscape、约束热图） |
| MATLAB/Simulink | 模型快速迭代、Bode 分析 |
| ROS rqt_plot | 实时多信号可视化 |
| osqp-eigen | C++ MPC 求解 |

### 6.2 半实物层

| 工具 | 用途 |
|------|------|
| Speedgoat / dSPACE | 工业级 HiL 平台 |
| Linux RT-PREEMPT | 廉价软实时方案 |
| `cyclictest` | 内核延迟测试 |
| `perf` / `valgrind` | 性能分析 |

### 6.3 实车层

| 工具 | 用途 |
|------|------|
| ROS rosbag / MCAP | 数据录制 |
| Foxglove Studio | 多车数据可视化 |
| candump / canalyzer | CAN 抓包 |
| PlotJuggler | 时序数据交互式分析 |

---

## 七、调试工程师的"三个必备习惯"

1. **每次实验记日志**：把 $Q, R, N, $ 软约束权重、求解时间、跟踪 RMSE 全部存文件，便于回溯
2. **永远先在仿真复现**：实车一开始 30 分钟内必先在仿真重放当天数据
3. **保留两个对照基线**：纯 PID（保底） + 上一版稳定 MPC（对照），切换不超过 2 秒

---

## 总结

| 层次 | 重点 | 关键工具 |
|------|------|---------|
| 仿真 | 算法/模型本身 | Python 可视化 + KKT 检查 |
| HiL | 实时性 + 鲁棒性 | RT-PREEMPT + 注入扰动 |
| 实车 | Sim-Real Gap | rosbag + 离线复现 |
| 故障 | 5 类 SOP | 见第五节 |
| 哲学 | 渐进、可回退、有日志 | 系统化习惯 |

> **金句**：MPC 调参 80% 是工程，20% 是数学。本篇给的是 80%。
