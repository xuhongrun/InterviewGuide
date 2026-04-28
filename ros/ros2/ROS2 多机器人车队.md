# ROS2 多机器人 / 车队部署

> 多机器人协作核心：**域隔离 / 命名空间 / 跨域桥接 / 任务调度**。

---

## 一、隔离层级

```
DOMAIN_ID 级（强隔离，DDS 互不可见）
  ├── 车队 A：DOMAIN_ID=10
  └── 车队 B：DOMAIN_ID=20
        │
        └── namespace 级（同 DOMAIN_ID 内多机器人）
              ├── /robot_1/...
              └── /robot_2/...
                     │
                     └── frame_id 级（TF 树前缀）
                           └── robot_1/base_link
```

---

## 二、Namespace 模板

启动模板（launch.py）：

```python
from launch_ros.actions import Node, PushRosNamespace
from launch.actions import GroupAction, DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

robot_ns = LaunchConfiguration("robot_name")

GroupAction([
    PushRosNamespace(robot_ns),
    Node(package="robot_state_publisher",
         executable="robot_state_publisher",
         parameters=[{"robot_description": ..., "frame_prefix": [robot_ns, "/"]}]),
    Node(package="nav2_bringup", executable="bringup", namespace=robot_ns),
])
```

`frame_prefix` 让 TF 自动加前缀避免冲突：`robot_1/base_link`。

---

## 三、TF 多机器人

策略：每机器人独立 `map → odom → base_link` 子树，前缀避免重名。可选：

| 方案 | 说明 |
|------|------|
| 各车独立 map | 不共享，简单但需融合层 |
| 共享 `map` 不加前缀 | 用统一原点，TF 共用，但调试易混 |
| `multi_map_server` | nav2 提供切图 |
| `map_to_robotN_map` 静态变换 | 把多张 map 拼到 `world` 系 |

工具：
- `tf2_ros static_transform_publisher` 发车间相对关系；
- `nav2_collision_monitor` 多机器人感知互相为障碍。

---

## 四、共享话题与协调

公共话题（不加前缀）放统一 namespace：
- `/fleet/task_assignments`
- `/fleet/heartbeats`
- `/fleet/world_state`

每车订阅 `/fleet/...`，发布 `/<robot>/cmd_vel`。

---

## 五、Open-RMF：开源车队管理

[Open-RMF](https://www.open-rmf.org/) 提供：
- **rmf_traffic_editor**：地图编辑（多楼层 / 通道）；
- **rmf_traffic**：路径冲突协调；
- **rmf_fleet_adapter**：每车队 1 个 adapter，桥接车队私有协议；
- **rmf_task**：任务分配（拾取/送达/巡逻）；
- **rmf_demos**：完整演示。

部署：
```
┌──────────────┐   ┌──────────────┐
│ Fleet A AMR  │   │ Fleet B AGV  │
└──────┬───────┘   └──────┬───────┘
       │ adapter          │ adapter
       ▼                  ▼
   ┌──────── rmf_traffic_schedule ─────────┐
   │         (冲突协调 / 路径预约)          │
   └──────────────┬─────────────────────────┘
                  ▼
          rmf_task / Dashboard
```

---

## 六、跨域 / 跨网段

| 场景 | 方案 |
|------|------|
| 同 LAN 不同 DOMAIN_ID | 启**多 ros2 daemon** 或用 **ros2 domain bridge** |
| 跨 LAN | **Zenoh router** 或 **Fast DDS Discovery Server**（每端 router） |
| WAN / 4G/5G | **Zenoh router + cloud relay**，或 MQTT 桥接 |

`domain_bridge` 例：
```yaml
name: my_bridge
topics:
  /chatter:
    type: std_msgs/msg/String
    from_domain: 1
    to_domain:   2
```

```bash
ros2 run domain_bridge domain_bridge bridge.yaml
```

---

## 七、时间同步

车队必须有统一时间源，否则 TF / 协调失败：

```bash
# 主机 A：chrony 主服务器
sudo apt install chrony
# /etc/chrony/chrony.conf
local stratum 8
allow 192.168.0.0/16

# 主机 B...：客户端
server 192.168.0.10 iburst
```

更高精度（亚毫秒）走 **PTP (IEEE-1588)**：`linuxptp` (`ptp4l + phc2sys`)。

ROS2 节点：
- 用 `use_sim_time:=false`（生产）；
- 时间戳来自硬件（IMU/LiDAR 自带 PTP）。

---

## 八、网络拓扑

| 拓扑 | 优劣 |
|------|------|
| 全 mesh（peer 直连 DDS） | 低延迟，但 N² 增长 |
| 单 router（Zenoh / DiscoveryServer） | 集中可控，单点风险 |
| 双 router 冗余 | 工业最常用 |
| 分层（边缘 + 云） | 大规模车队 |

子网划分：
- 控制网：低延迟、QoS DSCP 标记 EF；
- 感知网：高带宽，独立 VLAN；
- 管理网：OTA / SSH / 监控；
- 公网回传：MQTT / HTTP（限速）。

---

## 九、监控与运维

- **Prometheus + Grafana**：节点延迟、QoS drop、CPU、链路；
- `node_exporter`、`process_exporter`、自定义 `ros2_exporter`（topic Hz/latency）；
- `Foxglove + foxglove_bridge`：远程实时调试；
- `mcap` bag 上传 S3，用 Foxglove Studio 离线复盘；
- **OTA**：使用 `mender`、`balena` 或自研 lifecycle 命令切换 image。

---

## 十、安全

车队通信安全要点：
- SROS2 + 企业 PKI；
- 每车独立 enclave，permissions 限定 namespace；
- VPN（WireGuard）回云；
- API 网关鉴权（JWT / OAuth2）；
- 紧急遥停链路单独通道（最小化软件栈）。

---

## 十一、常见坑

| 现象 | 原因 |
|------|------|
| 多机话题打架 | 没用 namespace；TF 同名冲突 |
| 跨网络看不见对方 | multicast 不通；要 Discovery Server / Zenoh |
| 时序错乱 | 时钟未同步 |
| QoS 不匹配 | 同一话题不同车 QoS 不一致，subscribe 不上 |
| Open-RMF traffic schedule 死锁 | adapter 周期或路径上报延迟过大 |

---

## 十二、面试速记

- 隔离三层：**DOMAIN_ID > namespace > frame_id**
- 命名空间用 `PushRosNamespace + frame_prefix`
- 跨域桥接：**domain_bridge**（同 LAN）/ **Zenoh router**（跨 WAN）/ Fast DDS DS
- 车队管理框架：**Open-RMF**（traffic schedule + fleet adapter + task）
- 时间同步：chrony（毫秒）/ PTP（亚毫秒）
- 安全：每车独立 SROS2 enclave + VPN + 紧急遥停独立链路
