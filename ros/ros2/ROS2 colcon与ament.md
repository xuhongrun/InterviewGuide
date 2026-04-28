# ROS2 colcon 与 ament 构建系统

> ROS2 用 **colcon**（构建工具）+ **ament**（构建系统/约定）替代 ROS1 的 catkin。理解构建链有助于排查依赖、安装、环境问题。

---

## 一、术语区分

| 名称 | 角色 | 类比 |
|------|------|------|
| **colcon** | 多包**构建编排工具**（Python 写成） | catkin_tools / make |
| **ament_cmake** | C/C++ 包的 CMake 构建宏与约定 | catkin CMake macros |
| **ament_python** | 纯 Python 包的 setuptools 集成 | catkin_python |
| **ament_index** | 安装后的资源索引（`share/ament_index/`） | rospack |
| **rosidl** | 接口生成器（msg/srv/action → C++/Py/IDL） | gencpp/genpy |

---

## 二、colcon 工作流

### 2.1 工作空间结构

```
~/ros2_ws/
├── src/
│   ├── pkg_a/
│   ├── pkg_b/
│   └── third_party/...
├── build/      # 中间产物
├── install/    # 安装产物（每包一个子目录）
└── log/
```

### 2.2 常用命令

```bash
# 在 ws 根目录
colcon build                                 # 构建全部
colcon build --packages-select pkg_a         # 只构建指定包
colcon build --packages-up-to pkg_a          # 包含 pkg_a 及其依赖
colcon build --symlink-install               # 用符号链接（开发期改 launch/yaml 不需重编）
colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release
colcon build --executor sequential           # 单进程构建（调试 CMake 报错）

# 测试
colcon test --packages-select pkg_a
colcon test-result --verbose

# 清理
rm -rf build install log

# 列出依赖图
colcon list -t                               # topological order
colcon graph --dot | dot -Tpng > deps.png
```

构建后必须 source：
```bash
source install/setup.bash      # 或 setup.zsh
```

---

## 三、ament_cmake（C++ 包）

### 3.1 最小 `package.xml`（Format 3）

```xml
<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd"?>
<package format="3">
  <name>my_pkg</name>
  <version>0.1.0</version>
  <description>Demo package</description>
  <maintainer email="me@example.com">Me</maintainer>
  <license>Apache-2.0</license>

  <buildtool_depend>ament_cmake</buildtool_depend>

  <depend>rclcpp</depend>
  <depend>std_msgs</depend>
  <depend>sensor_msgs</depend>

  <test_depend>ament_lint_auto</test_depend>
  <test_depend>ament_lint_common</test_depend>

  <export>
    <build_type>ament_cmake</build_type>
  </export>
</package>
```

依赖标签语义：
| 标签 | 用途 |
|------|------|
| `buildtool_depend` | 构建工具（CMake/python setuptools） |
| `build_depend` | 构建期需要 |
| `build_export_depend` | 下游包构建时也需要 |
| `exec_depend` | 运行期需要 |
| `depend` | = build + build_export + exec（最常用） |
| `test_depend` | 仅测试 |

### 3.2 `CMakeLists.txt` 模板

```cmake
cmake_minimum_required(VERSION 3.16)
project(my_pkg)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)

# 库
add_library(my_lib SHARED src/my_lib.cpp)
target_include_directories(my_lib PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>)
ament_target_dependencies(my_lib rclcpp std_msgs)

# 可执行
add_executable(talker src/talker.cpp)
ament_target_dependencies(talker rclcpp std_msgs)
target_link_libraries(talker my_lib)

# 安装
install(DIRECTORY include/ DESTINATION include)
install(TARGETS my_lib
    EXPORT export_${PROJECT_NAME}
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION bin)
install(TARGETS talker DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY launch config DESTINATION share/${PROJECT_NAME})

# 导出
ament_export_include_directories(include)
ament_export_libraries(my_lib)
ament_export_targets(export_${PROJECT_NAME})
ament_export_dependencies(rclcpp std_msgs)

# 测试
if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()    # 必须最后调用
```

### 3.3 自定义消息

```cmake
find_package(rosidl_default_generators REQUIRED)
rosidl_generate_interfaces(${PROJECT_NAME}
    "msg/Pose2D.msg"
    "srv/AddTwoInts.srv"
    "action/Fibonacci.action"
    DEPENDENCIES std_msgs)
ament_export_dependencies(rosidl_default_runtime)
```

`package.xml` 加：
```xml
<buildtool_depend>rosidl_default_generators</buildtool_depend>
<exec_depend>rosidl_default_runtime</exec_depend>
<member_of_group>rosidl_interface_packages</member_of_group>
```

> **建议**：消息单独放在 `*_msgs` 包中，避免循环依赖。

### 3.4 同包内使用本包消息

```cmake
rosidl_get_typesupport_target(cpp_typesupport_target
    ${PROJECT_NAME} "rosidl_typesupport_cpp")
target_link_libraries(my_node ${cpp_typesupport_target})
```

---

## 四、ament_python（纯 Python 包）

### 4.1 `package.xml`

```xml
<package format="3">
  <name>my_py_pkg</name>
  ...
  <buildtool_depend>ament_python</buildtool_depend>
  <depend>rclpy</depend>
  <depend>std_msgs</depend>
  <export><build_type>ament_python</build_type></export>
</package>
```

### 4.2 `setup.py`

```python
from setuptools import setup
package_name = 'my_py_pkg'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/bringup.launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    entry_points={
        'console_scripts': [
            'talker = my_py_pkg.talker:main',
            'listener = my_py_pkg.listener:main',
        ],
    },
)
```

需要 `resource/<pkg_name>` 空文件 + `setup.cfg`：
```ini
[develop]
script_dir=$base/lib/my_py_pkg
[install]
install_scripts=$base/lib/my_py_pkg
```

---

## 五、安装与运行依赖：rosdep

```bash
sudo rosdep init     # 仅首次
rosdep update
rosdep install --from-paths src --ignore-src -r -y
```

`package.xml` 中的 `<depend>` 会被 rosdep 解析为 apt 包名（在 `ros/rosdistro` 维护映射）。

---

## 六、`.rosignore` 与混合工作空间

- `COLCON_IGNORE`（空文件）：放在子目录中，告诉 colcon 跳过该目录；
- `AMENT_IGNORE`：等价于 `COLCON_IGNORE`；
- `CATKIN_IGNORE`：兼容 ROS1。

---

## 七、Mixin / Defaults

```bash
colcon mixin add default \
    https://raw.githubusercontent.com/colcon/colcon-mixin-repository/master/index.yaml
colcon mixin update default

colcon build --mixin release         # 等价 -DCMAKE_BUILD_TYPE=Release
colcon build --mixin debug
colcon build --mixin coverage-gcc
```

`~/.colcon/defaults.yaml`：
```yaml
build:
  symlink-install: true
  cmake-args: ["-DCMAKE_BUILD_TYPE=Release"]
test:
  parallel-workers: 4
```

---

## 八、调试构建

| 现象 | 排查 |
|------|------|
| `Could not find package configuration file XXXConfig.cmake` | 缺依赖或 source 顺序错；先 source `/opt/ros/humble/setup.bash` 再 `install/setup.bash` |
| `error: 'rclcpp' is not a CMake package` | 没 `find_package(rclcpp REQUIRED)` 或 `ament_target_dependencies` |
| Python 节点 `ros2 run` 找不到 | `entry_points` 写错或 `setup.py` 未把 launch/yaml 装到 share |
| 消息生成后链接失败 | 缺 `rosidl_get_typesupport_target` 或 `ament_export_dependencies(rosidl_default_runtime)` |
| 修改 launch 还需重编 | 改用 `colcon build --symlink-install` |
| 包之间循环依赖 | 拆 `*_msgs` 包 |

---

## 九、面试速记

- ROS2 构建链：**colcon（编排）+ ament_cmake/ament_python（约定）+ rosidl（接口生成）+ rosdep（系统依赖）**
- 工作空间：`src` → `colcon build` → `install/setup.bash`
- 包必须有 `package.xml` + `CMakeLists.txt`/`setup.py`
- 自定义消息 → 必须 `rosidl_generate_interfaces` + `member_of_group rosidl_interface_packages`
- 开发期推荐 `--symlink-install`
