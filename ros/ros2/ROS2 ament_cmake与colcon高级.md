# ROS2 ament_cmake 与 colcon 高级

> 进阶构建：导出库给下游、混合 C++/Python、自定义 cmake 函数、colcon mixin / event-handlers。

---

## 一、ament_cmake 包结构

```
my_pkg/
├── CMakeLists.txt
├── package.xml
├── include/my_pkg/foo.hpp
├── src/foo.cpp
└── test/test_foo.cpp
```

最小 CMakeLists：

```cmake
cmake_minimum_required(VERSION 3.8)
project(my_pkg)

if(NOT CMAKE_CXX_STANDARD) set(CMAKE_CXX_STANDARD 17) endif()
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)

add_library(${PROJECT_NAME} SHARED src/foo.cpp)
target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_features(${PROJECT_NAME} PUBLIC cxx_std_17)
ament_target_dependencies(${PROJECT_NAME} rclcpp std_msgs)

# 可执行
add_executable(${PROJECT_NAME}_node src/main.cpp)
target_link_libraries(${PROJECT_NAME}_node ${PROJECT_NAME})

install(TARGETS ${PROJECT_NAME}
  EXPORT export_${PROJECT_NAME}
  LIBRARY DESTINATION lib
  ARCHIVE DESTINATION lib
  RUNTIME DESTINATION bin
  INCLUDES DESTINATION include)

install(TARGETS ${PROJECT_NAME}_node
  RUNTIME DESTINATION lib/${PROJECT_NAME})

install(DIRECTORY include/ DESTINATION include)

# 让下游 find_package 找到
ament_export_targets(export_${PROJECT_NAME} HAS_LIBRARY_TARGET)
ament_export_dependencies(rclcpp std_msgs)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
```

---

## 二、导出库给下游

下游使用：

```cmake
find_package(my_pkg REQUIRED)
add_executable(my_app main.cpp)
target_link_libraries(my_app my_pkg::my_pkg)   # 或 my_pkg
ament_target_dependencies(my_app my_pkg)
```

关键三件套：
1. `install(TARGETS ... EXPORT export_<name>)`
2. `ament_export_targets(export_<name> HAS_LIBRARY_TARGET)`
3. `ament_export_dependencies(<deps>)` — 让下游自动 `find_package`

旧式 `ament_export_libraries / ament_export_include_directories` 在 Humble+ 已不推荐，优先 `ament_export_targets`。

---

## 三、混合 C++/Python 包

```cmake
# CMakeLists.txt
find_package(ament_cmake_python REQUIRED)
find_package(rclpy REQUIRED)

# C++ 库 / 节点同上

ament_python_install_package(${PROJECT_NAME})

install(PROGRAMS
  scripts/my_python_node.py
  DESTINATION lib/${PROJECT_NAME})
```

```
my_pkg/
├── my_pkg/__init__.py     ← Python 模块
├── my_pkg/foo.py
├── scripts/my_python_node.py
├── src/cpp_node.cpp
└── ...
```

`package.xml`：
```xml
<buildtool_depend>ament_cmake</buildtool_depend>
<buildtool_depend>ament_cmake_python</buildtool_depend>
<exec_depend>rclcpp</exec_depend>
<exec_depend>rclpy</exec_depend>
```

---

## 四、纯 Python 包（ament_python）

```
my_py_pkg/
├── package.xml
├── setup.py
├── setup.cfg
├── resource/my_py_pkg
└── my_py_pkg/__init__.py
```

`setup.py`：
```python
from setuptools import find_packages, setup

package_name = 'my_py_pkg'
setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/bringup.launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    entry_points={
        'console_scripts': [
            'talker = my_py_pkg.talker:main',
        ],
    },
)
```

`package.xml` 设 `<export><build_type>ament_python</build_type></export>`。

> ⚠️ Python 节点必须通过 `entry_points` 暴露才能 `ros2 run my_py_pkg talker`。

---

## 五、自定义 CMake 函数

```cmake
# cmake/my_pkg-extras.cmake
function(my_pkg_register_plugin pkg name)
  pluginlib_export_plugin_description_file(${pkg} plugins/${name}.xml)
endfunction()
```

CMakeLists 里：
```cmake
ament_package(
  CONFIG_EXTRAS "cmake/my_pkg-extras.cmake"
)
```

下游 `find_package(my_pkg)` 会自动 include 这个 cmake 文件。

---

## 六、安装规则速查

| 目标 | 安装位置 |
|------|----------|
| 共享库 (`SHARED`) | `lib/` |
| 可执行 | `lib/${PROJECT_NAME}/`（让 `ros2 run` 找到） |
| 普通脚本 | `lib/${PROJECT_NAME}/`（用 `install(PROGRAMS)`） |
| 头文件 | `include/` |
| Launch / config / urdf | `share/${PROJECT_NAME}/launch/` 等 |
| Python 模块 | `lib/python3.x/site-packages/${PROJECT_NAME}/` |

`ros2 run` 只查 `lib/${PROJECT_NAME}/`。

---

## 七、colcon 高阶用法

### 7.1 常用参数

```bash
colcon build --symlink-install            # 修改 launch/yaml 不用重 build
colcon build --packages-select my_pkg     # 只编一个
colcon build --packages-up-to my_pkg      # 编它和依赖
colcon build --packages-skip my_pkg       # 跳过
colcon build --executor sequential        # 单线程，便于看错误
colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release
colcon build --event-handlers console_direct+   # 实时输出
```

### 7.2 mixin（参数预设）

```bash
sudo apt install python3-colcon-mixin
colcon mixin add default \
    https://raw.githubusercontent.com/colcon/colcon-mixin-repository/master/index.yaml
colcon mixin update default

colcon build --mixin release            # = -DCMAKE_BUILD_TYPE=Release
colcon build --mixin debug coverage-gcc # 多 mixin 组合
```

可在工作空间根目录放 `defaults.yaml`：
```yaml
build:
  mixin: ["release"]
test:
  parallel-workers: 1
```

### 7.3 测试

```bash
colcon test --packages-select my_pkg --event-handlers console_direct+
colcon test-result --verbose
```

测试报告位于 `build/<pkg>/test_results/`。

### 7.4 增量构建

`colcon build` 会缓存；改 cmake 后用 `--cmake-clean-cache` 清。

`build/<pkg>/CMakeCache.txt` 不一致时强制重建：
```bash
rm -rf build/<pkg> install/<pkg>
colcon build --packages-select <pkg>
```

### 7.5 多工作空间 overlay

```bash
source /opt/ros/jazzy/setup.bash
cd ws_lower; colcon build; source install/setup.bash
cd ws_upper; colcon build; source install/setup.bash
# 后 source 的 overlay 优先
```

---

## 八、CI/CD：industrial_ci

`.github/workflows/ci.yml`：

```yaml
name: ci
on: [push, pull_request]
jobs:
  industrial_ci:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        ROS_DISTRO: [humble, jazzy]
    env:
      ROS_DISTRO: ${{ matrix.ROS_DISTRO }}
    steps:
      - uses: actions/checkout@v4
      - uses: ros-industrial/industrial_ci@master
        env: { ROS_DISTRO: ${{ matrix.ROS_DISTRO }} }
```

---

## 九、面试速记

- 导出库三件套：**`install(TARGETS EXPORT)` + `ament_export_targets(...)` + `ament_export_dependencies(...)`**
- ROS2 可执行装到 **`lib/${PROJECT_NAME}/`**，否则 `ros2 run` 找不到
- 混合 C++/Python：用 `ament_cmake_python`；纯 Python 用 `ament_python` + `entry_points`
- `colcon build --symlink-install` 修改 launch/yaml 免重编
- **mixin** 一键应用 cmake 参数预设
- 自定义 cmake 函数走 `CONFIG_EXTRAS` 暴露
- CI 推荐 **industrial_ci** 跑多 distro 矩阵
