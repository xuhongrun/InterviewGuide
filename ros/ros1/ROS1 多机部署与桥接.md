# ROS1 多机部署与 ros1_bridge

> 多机部署是 ROS1 的常见痛点（Master 单点 + 时钟同步 + 网络发现）；ros1_bridge 是 ROS1↔ROS2 共存阶段的关键过渡。

---

## 一、多机网络配置

### 1.1 必备条件

1. **网络互通**：ping 通；
2. **主机名互相可解析**：`/etc/hosts` 加双向解析；
3. **时钟同步**：chrony / NTP（误差 < 1ms 推荐）；
4. **防火墙打开端口**：默认 11311（Master），节点用动态端口（Linux 32768–60999）。

### 1.2 环境变量

| 变量 | 含义 | 示例 |
|------|------|------|
| `ROS_MASTER_URI` | Master 地址 | `http://master-host:11311` |
| `ROS_HOSTNAME` | **本机对外可解析名**（推荐） | `robot1.local` |
| `ROS_IP` | 或者直接用 IP | `192.168.1.10` |

> ⚠️ `ROS_HOSTNAME` 与 `ROS_IP` 二选一；不设容易报 `Couldn't connect to a publisher`，因为节点把 localhost 注册到了 Master。

### 1.3 典型场景

A 机（master + 感知）：
```bash
export ROS_MASTER_URI=http://A:11311
export ROS_HOSTNAME=A
roscore
```

B 机（计算）：
```bash
export ROS_MASTER_URI=http://A:11311
export ROS_HOSTNAME=B
rosrun my_pkg planner
```

`/etc/hosts` 在双方都有：
```
192.168.1.10  A
192.168.1.20  B
```

### 1.4 时钟同步

```bash
# chrony（推荐）
sudo apt install chrony
# /etc/chrony/chrony.conf 添加
server A iburst minpoll 4 maxpoll 4
allow 192.168.1.0/24

sudo systemctl restart chrony
chronyc tracking            # 看偏差
chronyc sources -v
```

仿真时用 `/clock` 话题 + `use_sim_time=true`，所有节点订阅同一时间源。

---

## 二、子网 / NAT / 跨段

ROS1 P2P 直连，**对 NAT 不友好**。常用方案：

| 方案 | 说明 |
|------|------|
| 同一二层网络 | 最简单，性能最好 |
| L2 隧道（OpenVPN tap / wireguard tap）| 把多机虚拟为同网段 |
| `multimaster_fkie` / `master_sync` | **多 Master 各自工作**，跨 Master 通过桥接同步选定 topic |
| MQTT / WebSocket 桥接 | 业务级桥接（非透明） |

`multimaster_fkie` 示例：每台机器跑自己 roscore，通过 `master_discovery` + `master_sync` 把感兴趣的 topic 在 Master 间镜像。

---

## 三、压缩与带宽

跨网传感器流务必压缩：

```xml
<!-- 图像 -->
<node name="republish" pkg="image_transport" type="republish"
      args="raw in:=/camera/image compressed out:=/camera/image"/>
```

订阅端 `image_transport::SubscriberFilter` 自动选择 `compressed`。

点云：
- `pcl_ros` 提供 `voxel_grid` 抽稀；
- 自研 zstd 压缩 republisher；
- 直接降低发布频率 / ROI 裁剪。

---

## 四、ros1_bridge：ROS1 ↔ ROS2 互通

### 4.1 工作原理

```
┌──────── ROS1 节点 ────────┐         ┌──────── ROS2 节点 ────────┐
│  rospy/roscpp + Master    │         │  rclcpp + DDS             │
└──────────┬────────────────┘         └────────────┬──────────────┘
           │     (TCPROS)                          │ (DDS)
           ↓                                       ↓
       ┌──────────────────────────────────────────────┐
       │   ros1_bridge   (同时连接两侧)               │
       │   双向桥接 topic / service / action          │
       └──────────────────────────────────────────────┘
```

ros1_bridge 必须在**同时安装 ROS1 + ROS2** 的环境中编译，可桥接 std_msgs / geometry_msgs / sensor_msgs 等内置类型，自定义消息需要手工映射。

### 4.2 启动

```bash
# 终端 1：ROS1
source /opt/ros/noetic/setup.bash
roscore

# 终端 2：ROS2 + bridge
source /opt/ros/noetic/setup.bash
source /opt/ros/humble/setup.bash
ros2 run ros1_bridge dynamic_bridge
# 选项：--bridge-all-topics / --bridge-all-1to2-topics ...
```

`dynamic_bridge` 自动检测两侧已发布且类型匹配的 topic 并桥接。

### 4.3 自定义消息映射

```yaml
# my_mapping_rules.yaml
-
  ros1_package_name: 'my_msgs1'
  ros1_message_name: 'Pose2D'
  ros2_package_name: 'my_msgs2'
  ros2_message_name: 'Pose2D'
  fields_1_to_2:
    x: x
    y: y
    theta: theta
```

`package.xml` 加：
```xml
<export>
  <ros1_bridge mapping_rules="my_mapping_rules.yaml"/>
</export>
```

重新 colcon build ros1_bridge 后才能识别。

### 4.4 性能与限制

- 桥接增加**一次反序列化 + 一次序列化** + 一次拷贝；
- 高频 / 大消息桥接是瓶颈；
- 推荐：性能敏感模块整体迁移；非敏感（可视化、慢配置）保留桥接。

### 4.5 迁移路径

```
ROS1 全栈
  ↓ 引入 bridge，新模块写 ROS2
ROS1 + ROS2 共存
  ↓ 逐模块 ROS2 化（roscpp→rclcpp、catkin→colcon）
  ↓ 替换 latched 为 TRANSIENT_LOCAL，Nodelet → Composition
ROS2 全栈
```

---

## 五、面试速记

- 多机三件套：**ROS_MASTER_URI + ROS_HOSTNAME + 时钟同步**
- `/etc/hosts` 双向可解析；不要让节点注册到 localhost
- 跨 Master 用 `multimaster_fkie`，跨 NAT 用 VPN
- 跨网带宽不够 → `image_transport` compressed / 点云抽稀
- ros1_bridge：双向桥接 ROS1 ↔ ROS2 内置消息，自定义需 mapping
- 桥接性能损耗大，迁移以**模块**为单位
- 长期方案：彻底迁 ROS2
