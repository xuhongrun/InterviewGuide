# ROS2 环境搭建与 Docker

> 入门第一步：安装、distro 切换、rosdep、Docker 化部署。

---

## 一、Ubuntu 安装（apt 源）

```bash
# 1. locale
sudo locale-gen en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

# 2. apt 源 + key
sudo apt install software-properties-common curl
sudo add-apt-repository universe
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
    http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" \
    | sudo tee /etc/apt/sources.list.d/ros2.list

# 3. 安装（jazzy 为例）
sudo apt update
sudo apt install ros-jazzy-desktop ros-dev-tools

# 4. 环境
echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc
```

桌面包还是基础包：

| 包名 | 内容 |
|------|------|
| `ros-<distro>-ros-base` | 最小核心（rcl + 工具链） |
| `ros-<distro>-ros-core` | 仅库（无 rviz/rqt） |
| `ros-<distro>-desktop` | 加 RViz / rqt / demo |
| `ros-<distro>-desktop-full` | + 仿真 / 教程 |

---

## 二、distro 切换

多 distro 共存：

```bash
# 临时切换
source /opt/ros/humble/setup.bash
ros2 doctor          # 验证

# 切回另一 distro 必须新开 shell（环境变量已被前者污染）
```

工作空间 overlay：

```bash
source /opt/ros/jazzy/setup.bash
cd ~/ros2_ws
colcon build --symlink-install
source install/setup.bash
```

---

## 三、rosdep：依赖安装

```bash
sudo rosdep init                       # 首次
rosdep update                          # 拉取 rosdistro 索引

cd ~/ros2_ws
rosdep install --from-paths src --ignore-src -r -y
```

`package.xml` 里 `<depend>` 的 key 经 `rosdep` 转为 apt 包安装。

自定义规则放 `/etc/ros/rosdep/sources.list.d/50-mycompany.list`，指向公司 yaml。

---

## 四、构建工作空间

```bash
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws/src
ros2 pkg create --build-type ament_cmake my_pkg --dependencies rclcpp std_msgs

cd ~/ros2_ws
colcon build --symlink-install
source install/setup.bash
ros2 run my_pkg my_node
```

---

## 五、Docker 化

### 5.1 官方镜像

```bash
docker pull osrf/ros:jazzy-desktop
docker run -it --rm --network host \
  -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix \
  osrf/ros:jazzy-desktop
```

镜像层级：
- `ros:jazzy-ros-core` — 最小
- `ros:jazzy-ros-base` — 加工具
- `osrf/ros:jazzy-desktop` — 加 RViz

### 5.2 项目 Dockerfile 模板

```dockerfile
FROM ros:jazzy-ros-base

ARG WORKSPACE=/ros2_ws
ENV ROS_DOMAIN_ID=42
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

RUN apt-get update && apt-get install -y \
    ros-jazzy-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

WORKDIR ${WORKSPACE}
COPY src ${WORKSPACE}/src

RUN . /opt/ros/jazzy/setup.sh && \
    rosdep update && \
    rosdep install --from-paths src --ignore-src -y && \
    colcon build --symlink-install

# entrypoint 自动 source
COPY ros_entrypoint.sh /
RUN chmod +x /ros_entrypoint.sh
ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["bash"]
```

`ros_entrypoint.sh`：
```bash
#!/bin/bash
set -e
source /opt/ros/jazzy/setup.bash
[ -f /ros2_ws/install/setup.bash ] && source /ros2_ws/install/setup.bash
exec "$@"
```

### 5.3 网络模式

| 模式 | 适用 |
|------|------|
| `--network host` | 默认推荐，DDS 多播可用 |
| `--network bridge` | 容器互联，但 DDS 多播默认不通；需配 Discovery Server |
| `--network none` | 完全隔离，无法 ROS 通信 |

> **跨主机 / 跨容器**通信要么 host network，要么 Fast DDS Discovery Server，要么 Zenoh router。

### 5.4 多容器组合（docker-compose）

```yaml
version: '3'
services:
  perception:
    build: .
    network_mode: host
    environment:
      - ROS_DOMAIN_ID=42
    command: ros2 launch perception bringup.launch.py
  planner:
    build: .
    network_mode: host
    environment:
      - ROS_DOMAIN_ID=42
    command: ros2 launch planner bringup.launch.py
```

---

## 六、源码编译（高级）

某些场景（嵌入式、定制 RMW）需源码编译：

```bash
mkdir -p ~/ros2_jazzy/src
cd ~/ros2_jazzy
vcs import --input https://raw.githubusercontent.com/ros2/ros2/jazzy/ros2.repos src
rosdep install --from-paths src --ignore-src -y --skip-keys "fastcdr rti-connext-dds-6.0.1 urdfdom_headers"
colcon build --symlink-install
```

---

## 七、跨平台

| 平台 | 状态 |
|------|------|
| Ubuntu 24.04 (Jazzy) | Tier-1 |
| Ubuntu 22.04 (Humble) | Tier-1 LTS |
| Windows 10/11 | Tier-1（部分包受限） |
| macOS | Tier-3（社区支持） |
| RHEL 8/9 | Tier-3 |
| Yocto / Buildroot | 通过 `meta-ros` 集成 |

Windows：用 `chocolatey` + 离线安装包，shell 用 `Visual Studio Developer PowerShell`。

---

## 八、面试速记

- 安装走 apt 源；`source /opt/ros/<distro>/setup.bash`
- 多 distro 切换需新 shell，不要 source 多次
- **rosdep** 解析 package.xml 的依赖键，转为 apt 包安装
- 工作空间用 `colcon build --symlink-install`
- Docker 推荐 **host network + 设 ROS_DOMAIN_ID**；跨主机用 Discovery Server
- 嵌入式 / 定制 RMW 走源码编译（`vcs import + rosdep + colcon`）
