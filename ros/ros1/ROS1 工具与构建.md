# ROS1 工具链、构建与运行时

> ROS1 工具链：catkin 构建、roslaunch 启动、rxx_* 命令行内省、rqt_* GUI 调试、rosbag 录制回放、roswtf 诊断。

---

## 一、catkin 构建系统

### 1.1 工作空间

```
~/catkin_ws/
├── src/
│   ├── CMakeLists.txt          # 由 catkin_init_workspace 生成（toplevel.cmake 软链）
│   ├── pkg_a/
│   │   ├── package.xml
│   │   ├── CMakeLists.txt
│   │   ├── include/pkg_a/
│   │   ├── src/
│   │   ├── launch/
│   │   └── msg/
│   └── pkg_b/
├── build/      # 由 catkin_make / catkin build 生成
├── devel/      # devel space：开发期可用，无需 install 即可 source
└── install/    # 可选：catkin_make install 后产物
```

### 1.2 两种构建器

| 工具 | 特点 |
|------|------|
| `catkin_make` | ROS 自带，一次性整工作空间构建，包之间共享 CMake 上下文（依赖混乱） |
| `catkin build`（catkin_tools） | 推荐，每包独立 CMake 实例，依赖清晰，并行构建 |

```bash
# 初始化（用 catkin_tools）
sudo apt install python3-catkin-tools
mkdir -p ~/catkin_ws/src && cd ~/catkin_ws
catkin init
catkin build                   # 构建全部
catkin build pkg_a             # 只构建一个包及其依赖
catkin clean
catkin config --install        # 启用 install space
catkin config -DCMAKE_BUILD_TYPE=Release
source devel/setup.bash
```

### 1.3 `package.xml`（Format 2）

```xml
<package format="2">
  <name>my_pkg</name>
  <version>0.1.0</version>
  <description>Demo</description>
  <maintainer email="me@example.com">Me</maintainer>
  <license>Apache-2.0</license>

  <buildtool_depend>catkin</buildtool_depend>

  <build_depend>roscpp</build_depend>
  <build_depend>std_msgs</build_depend>
  <build_depend>message_generation</build_depend>

  <build_export_depend>roscpp</build_export_depend>
  <build_export_depend>std_msgs</build_export_depend>

  <exec_depend>roscpp</exec_depend>
  <exec_depend>std_msgs</exec_depend>
  <exec_depend>message_runtime</exec_depend>
</package>
```

### 1.4 `CMakeLists.txt` 模板

```cmake
cmake_minimum_required(VERSION 3.0.2)
project(my_pkg)

find_package(catkin REQUIRED COMPONENTS
    roscpp std_msgs message_generation)

add_message_files(FILES Pose2D.msg)
add_service_files(FILES AddTwoInts.srv)
generate_messages(DEPENDENCIES std_msgs)

catkin_package(
    INCLUDE_DIRS include
    LIBRARIES my_lib
    CATKIN_DEPENDS roscpp std_msgs message_runtime)

include_directories(include ${catkin_INCLUDE_DIRS})

add_library(my_lib src/my_lib.cpp)
add_dependencies(my_lib ${${PROJECT_NAME}_EXPORTED_TARGETS})

add_executable(talker src/talker.cpp)
add_dependencies(talker ${${PROJECT_NAME}_EXPORTED_TARGETS})
target_link_libraries(talker my_lib ${catkin_LIBRARIES})

install(TARGETS talker my_lib
    ARCHIVE DESTINATION ${CATKIN_PACKAGE_LIB_DESTINATION}
    LIBRARY DESTINATION ${CATKIN_PACKAGE_LIB_DESTINATION}
    RUNTIME DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION})
install(DIRECTORY include/${PROJECT_NAME}/ DESTINATION ${CATKIN_PACKAGE_INCLUDE_DESTINATION})
install(DIRECTORY launch DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION})
```

> 关键陷阱：使用自定义消息时**必须** `add_dependencies(target ${${PROJECT_NAME}_EXPORTED_TARGETS} ${catkin_EXPORTED_TARGETS})`，否则编译顺序错乱。

---

## 二、roslaunch（XML）

### 2.1 基础

```xml
<launch>
  <arg name="use_sim" default="false"/>

  <param name="/use_sim_time" value="$(arg use_sim)"/>

  <node pkg="my_pkg" type="talker" name="talker"
        ns="robot1" output="screen"
        respawn="true" respawn_delay="2.0">
      <param name="max_speed" value="2.0"/>
      <rosparam file="$(find my_pkg)/config/params.yaml" command="load"/>
      <remap from="chatter" to="/global/chatter"/>
  </node>

  <include file="$(find nav_pkg)/launch/nav.launch">
    <arg name="map_file" value="map.yaml"/>
  </include>

  <group ns="robot2" if="$(arg multi_robot)">
    <node pkg="my_pkg" type="listener" name="listener"/>
  </group>
</launch>
```

### 2.2 关键字段

| 标签 | 用途 |
|------|------|
| `<node>` | 启动一个进程（必填 `pkg` `type` `name`） |
| `respawn="true"` | 进程退出自动重启 |
| `output="screen"` | stdout/stderr 重定向到终端（默认写日志文件） |
| `launch-prefix` | 加前缀，如 `gdb -ex run --args` 调试 |
| `<machine>` | 多机部署：通过 SSH 在远程主机启动 |
| `<env>` | 设置环境变量 |
| `$(find pkg)` / `$(arg X)` / `$(env VAR)` | substitution |

### 2.3 多机部署

```xml
<machine name="robot1" address="192.168.1.10" user="ubuntu" env-loader="/opt/ros/noetic/env.sh"/>
<node machine="robot1" pkg="..." type="..." name="..."/>
```

需要在主机配置 `ROS_MASTER_URI` 与 `ROS_IP`/`ROS_HOSTNAME`：
```bash
export ROS_MASTER_URI=http://192.168.1.10:11311
export ROS_IP=192.168.1.20      # 自己的 IP
```

---

## 三、运行与命令行工具

### 3.1 运行控制

```bash
roscore                          # 启动 Master + rosout + Parameter Server
rosrun pkg node                  # 跑单节点
roslaunch pkg file.launch        # 启动多节点
rosnode list / info / kill / ping
rosrun rqt_graph rqt_graph       # 可视化连接图
```

### 3.2 内省命令

```bash
# Topic
rostopic list
rostopic info /chatter
rostopic echo /chatter
rostopic pub /chatter std_msgs/String "data: 'hi'"
rostopic hz /scan
rostopic bw /image

# Service
rosservice list
rosservice info /add
rosservice call /add "{a: 1, b: 2}"

# Param
rosparam list
rosparam get /max_speed
rosparam set /max_speed 2.0
rosparam dump out.yaml
rosparam load in.yaml

# Msg/Srv
rosmsg show std_msgs/Header
rossrv show my_pkg/AddTwoInts
```

### 3.3 GUI 工具（rqt 系列）

| 工具 | 用途 |
|------|------|
| `rqt_graph` | 节点-话题图 |
| `rqt_plot /pose/x` | 实时绘图 |
| `rqt_console` | 滚动日志 |
| `rqt_logger_level` | 运行时改 logger level |
| `rqt_reconfigure` | 动态参数 |
| `rqt_tf_tree` | TF 树 |
| `rqt_bag` | bag 可视化 |
| `rviz` | 3D 可视化（点云 / 机器人模型 / TF / Map） |
| `gazebo` | 物理仿真 |

---

## 四、rosbag

```bash
rosbag record -a                    # 录所有
rosbag record /scan /odom -O run.bag
rosbag record -b 2048 -j /image     # 缓冲 2GB + 压缩

rosbag info run.bag
rosbag play run.bag                 # 实时回放
rosbag play -r 2.0 -l run.bag       # 2 倍速 + 循环
rosbag play --clock run.bag         # 同时发 /clock（配合 use_sim_time）
rosbag filter in.bag out.bag "topic == '/scan'"
rosbag reindex broken.bag
```

C++ API：
```cpp
#include <rosbag/bag.h>
rosbag::Bag bag("data.bag", rosbag::bagmode::Write);
bag.write("chatter", ros::Time::now(), msg);
bag.close();
```

> ROS1 bag 格式：自定义二进制 + chunk + index。可用 `rosbags` 工具转换为 ROS2 mcap。

---

## 五、诊断与调试

### 5.1 roswtf

```bash
roswtf                               # 检查 Master、节点、URI、依赖等常见问题
```

### 5.2 日志

```bash
roscd log                            # 进入日志目录 ~/.ros/log/<run_id>/
ROSCONSOLE_FORMAT='[${severity}][${node}]: ${message}'
ROSCONSOLE_CONFIG_FILE=$PWD/rosconsole.config

ROS_LOG_DIR=/tmp/ros_logs roslaunch ...
```

代码：
```cpp
ROS_DEBUG / ROS_INFO / ROS_WARN / ROS_ERROR / ROS_FATAL
ROS_INFO_THROTTLE(2.0, "every 2s");
ROS_INFO_STREAM("x=" << x);
```

### 5.3 GDB / Valgrind

```xml
<node pkg="..." type="..." name="..." launch-prefix="gdb -ex run --args"/>
<node ... launch-prefix="valgrind --tool=memcheck"/>
```

### 5.4 性能

| 工具 | 用途 |
|------|------|
| `rostopic hz /xxx` | 频率 |
| `rostopic delay /xxx` | 端到端延迟（消息带 header） |
| `rqt_top` | 节点 CPU/内存 |
| `top` / `htop` / `pidstat -p $(pgrep talker)` | 系统级 |
| `wireshark` 过滤 TCP/UDP | 网络抓包 |

---

## 六、rosdep

```bash
sudo rosdep init                # 仅首次
rosdep update
rosdep install --from-paths src --ignore-src -r -y
```

`package.xml` 中的依赖通过 `rosdistro` 仓库映射到 apt 包名。

---

## 七、面试速记

- 构建：**catkin_tools (`catkin build`) 优于 `catkin_make`**
- 运行：`roscore` → `rosrun` / `roslaunch` → `ros{topic,service,param,node}` 内省
- 调试：**roswtf + rqt_* + rosbag + ROS_INFO**
- 多机：`ROS_MASTER_URI` + `ROS_IP`/`ROS_HOSTNAME`，`<machine>` 远程 SSH
- 自定义消息记得 `add_dependencies(... ${${PROJECT_NAME}_EXPORTED_TARGETS})`
- 想录制 → `rosbag record`；想仿真时间 → `rosbag play --clock` + `use_sim_time`
