# ROS2 测试 / CI / CD

> ROS2 自动化测试体系：单元测试（gtest/pytest）、集成测试（launch_testing）、lint、CI（industrial_ci / GitHub Actions）。

---

## 一、测试金字塔

```
  ┌────────────────────────┐
  │  E2E（仿真+硬件回归）   │  ← AWSIM / CARLA / 实车小循环
  ├────────────────────────┤
  │  集成（launch_testing） │  ← 多节点、Action、bag 回放
  ├────────────────────────┤
  │  组件（gtest/pytest）   │  ← Node fixture、Mock publisher
  ├────────────────────────┤
  │  单元（纯逻辑）         │  ← 算法、数据结构
  └────────────────────────┘
```

---

## 二、C++ 单元测试（gtest）

```cmake
if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test_foo test/test_foo.cpp)
  target_link_libraries(test_foo my_pkg)
endif()
```

```cpp
#include <gtest/gtest.h>
#include "my_pkg/foo.hpp"

TEST(FooTest, AddsTwo) { EXPECT_EQ(my_pkg::add(2,3), 5); }

int main(int argc, char** argv) {
    testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
```

跑：
```bash
colcon test --packages-select my_pkg --event-handlers console_direct+
colcon test-result --verbose
```

含 ROS2 的测试用 fixture：
```cpp
class NodeFixture : public ::testing::Test {
protected:
    void SetUp() override { rclcpp::init(0, nullptr); node_ = std::make_shared<rclcpp::Node>("test"); }
    void TearDown() override { rclcpp::shutdown(); }
    rclcpp::Node::SharedPtr node_;
};
```

---

## 三、Python 单元测试（pytest）

```python
# test/test_foo.py
import pytest
from my_pkg.foo import add

def test_add():
    assert add(2, 3) == 5
```

`setup.cfg`：
```ini
[options]
tests_require = pytest

[tool:pytest]
testpaths = test
```

`package.xml`：
```xml
<test_depend>ament_pep257</test_depend>
<test_depend>python3-pytest</test_depend>
```

---

## 四、launch_testing（集成测试）

```python
# test/test_talker_listener.launch.py
import unittest
import launch
import launch_ros.actions
import launch_testing.actions
import launch_testing.markers
import pytest

@pytest.mark.launch_test
def generate_test_description():
    talker = launch_ros.actions.Node(
        package="demo_nodes_cpp", executable="talker", name="talker")
    listener = launch_ros.actions.Node(
        package="demo_nodes_cpp", executable="listener", name="listener")
    return launch.LaunchDescription([
        talker, listener,
        launch_testing.actions.ReadyToTest(),
    ]), {"talker": talker, "listener": listener}

class TalkerListenerTest(unittest.TestCase):
    def test_talker_publishes(self, proc_output, talker):
        proc_output.assertWaitFor("Publishing:", process=talker, timeout=5)

    def test_listener_receives(self, proc_output, listener):
        proc_output.assertWaitFor("I heard:", process=listener, timeout=5)

@launch_testing.post_shutdown_test()
class ShutdownTest(unittest.TestCase):
    def test_clean_exit(self, proc_info, talker, listener):
        launch_testing.asserts.assertExitCodes(proc_info, process=talker)
```

CMakeLists：
```cmake
if(BUILD_TESTING)
  find_package(launch_testing_ament_cmake REQUIRED)
  add_launch_test(test/test_talker_listener.launch.py)
endif()
```

---

## 五、Lint / 静态检查

`<test_depend>` 列出：
- `ament_lint_auto` + `ament_lint_common` — 全套
- `ament_cmake_cppcheck` / `ament_cmake_cpplint`
- `ament_cmake_uncrustify` — 格式化
- `ament_cmake_clang_format` — clang-format
- `ament_pep257` / `ament_pep8` / `ament_flake8` — Python
- `ament_xmllint` — xml/launch

```cmake
if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()
```

跳过部分检查：
```xml
<test_depend>ament_lint_auto</test_depend>
<test_depend>ament_lint_common</test_depend>
```
不想要的在 CMake 里：
```cmake
list(APPEND AMENT_LINT_AUTO_EXCLUDE
     ament_cmake_uncrustify ament_cmake_cpplint)
```

---

## 六、bag 回放回归测试

```python
import subprocess
def test_with_bag(proc_output):
    p = subprocess.Popen(["ros2", "bag", "play", "test.mcap", "--rate", "1.0"])
    proc_output.assertWaitFor("Detected obstacle", timeout=30)
    p.terminate()
```

或直接 `ExecuteProcess` 在 launch_test 中拉起 `ros2 bag play`。

---

## 七、industrial_ci（最常用）

`.github/workflows/ci.yml`：

```yaml
name: ci
on: [push, pull_request]

jobs:
  ros_ci:
    runs-on: ubuntu-22.04
    strategy:
      fail-fast: false
      matrix:
        ROS_DISTRO: [humble, jazzy]
        ROS_REPO:  [main, testing]
    env:
      ROS_DISTRO: ${{ matrix.ROS_DISTRO }}
      ROS_REPO:   ${{ matrix.ROS_REPO }}
    steps:
      - uses: actions/checkout@v4
      - uses: ros-industrial/industrial_ci@master
```

industrial_ci 会自动：
- 安装 ROS2 distro；
- `rosdep install` 依赖；
- `colcon build`；
- `colcon test`；
- 处理代码覆盖率（CCOV/Codecov）。

---

## 八、setup-ros / action-ros-ci

更轻量自定义流程：

```yaml
- uses: ros-tooling/setup-ros@v0.7
  with: { required-ros-distributions: humble }
- uses: ros-tooling/action-ros-ci@v0.3
  with:
    package-name: my_pkg
    target-ros2-distro: humble
    colcon-defaults: |
      { "build": { "mixin": ["coverage-gcc"] } }
- uses: codecov/codecov-action@v4
```

---

## 九、Docker 矩阵 + Buildx

工业部署常构建多平台镜像：

```yaml
- uses: docker/setup-qemu-action@v3
- uses: docker/setup-buildx-action@v3
- uses: docker/build-push-action@v5
  with:
    platforms: linux/amd64,linux/arm64
    push: true
    tags: ghcr.io/${{ github.repository }}:${{ github.sha }}
```

---

## 十、面试速记

- 单元 → 集成 → E2E 三层
- C++ `ament_add_gtest`，Python `ament_python` + pytest
- 集成测试用 **launch_testing**，`ReadyToTest` 标记启动完成
- Lint 用 `ament_lint_auto + ament_lint_common`，按需 `AMENT_LINT_AUTO_EXCLUDE`
- bag 回放回归是工业标配
- CI 推荐 **industrial_ci**，多 distro × 多 repo 矩阵
- 多平台镜像用 `docker buildx + qemu`
