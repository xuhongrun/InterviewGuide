# ROS2 Action 与 pluginlib 深入

> Action 是 ROS2 中**长任务 + 反馈 + 取消**的标准模式；pluginlib 是动态加载 C++ 插件机制。两者都是 ROS1 → ROS2 的延续，但接口、调用模式发生明显变化。

---

## 一、Action 状态机

```
        ┌──────────┐
 client │ send_goal│ ──────► server: handle_goal() → ACCEPT / REJECT
        └────┬─────┘
             │ ACCEPT
             ▼
        ┌─────────┐
        │ EXECUTING│ ◄─── execute(goal_handle)：循环 publish_feedback / canceled
        └────┬─────┘
       cancel│              succeed/abort/canceled
             ▼                       │
       ┌──────────┐                  ▼
       │CANCELING │              ┌────────┐
       └────┬─────┘              │TERMINAL│ (succeeded/aborted/canceled)
            ▼                    └────────┘
       handle_cancel() → ACCEPT / REJECT
```

服务端三个回调：
1. `handle_goal(uuid, goal)` → `ACCEPT_AND_EXECUTE / ACCEPT_AND_DEFER / REJECT`
2. `handle_cancel(goal_handle)` → `ACCEPT / REJECT`
3. `handle_accepted(goal_handle)` → 启动 worker 线程执行（**不要在此阻塞**）

---

## 二、Server 实现（C++）

```cpp
#include <rclcpp/rclcpp.hpp>
#include <rclcpp_action/rclcpp_action.hpp>
#include <my_msgs/action/fibonacci.hpp>

class FibServer : public rclcpp::Node {
public:
    using Fib = my_msgs::action::Fibonacci;
    using GH = rclcpp_action::ServerGoalHandle<Fib>;

    FibServer() : Node("fib_server") {
        server_ = rclcpp_action::create_server<Fib>(this, "fibonacci",
            std::bind(&FibServer::handle_goal, this, std::placeholders::_1, std::placeholders::_2),
            std::bind(&FibServer::handle_cancel, this, std::placeholders::_1),
            std::bind(&FibServer::handle_accepted, this, std::placeholders::_1));
    }

private:
    rclcpp_action::Server<Fib>::SharedPtr server_;

    rclcpp_action::GoalResponse handle_goal(
        const rclcpp_action::GoalUUID& uuid, std::shared_ptr<const Fib::Goal> goal) {
        if (goal->order < 1 || goal->order > 9999) return rclcpp_action::GoalResponse::REJECT;
        return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
    }
    rclcpp_action::CancelResponse handle_cancel(std::shared_ptr<GH>) {
        return rclcpp_action::CancelResponse::ACCEPT;
    }
    void handle_accepted(std::shared_ptr<GH> gh) {
        std::thread{std::bind(&FibServer::execute, this, gh)}.detach();
    }
    void execute(std::shared_ptr<GH> gh) {
        rclcpp::Rate r(1);
        auto fb = std::make_shared<Fib::Feedback>();
        auto res = std::make_shared<Fib::Result>();
        auto& seq = fb->partial_sequence; seq = {0, 1};
        for (int i = 1; i < gh->get_goal()->order && rclcpp::ok(); ++i) {
            if (gh->is_canceling()) {
                res->sequence = seq; gh->canceled(res); return;
            }
            seq.push_back(seq[i] + seq[i-1]);
            gh->publish_feedback(fb);
            r.sleep();
        }
        res->sequence = seq;
        gh->succeed(res);
    }
};
```

---

## 三、Client 实现（C++）

```cpp
auto client = rclcpp_action::create_client<Fib>(node, "fibonacci");
client->wait_for_action_server();

auto goal = Fib::Goal(); goal.order = 10;
auto opt = rclcpp_action::Client<Fib>::SendGoalOptions();
opt.goal_response_callback = [](auto handle){
    if (!handle) RCLCPP_ERROR(...);
};
opt.feedback_callback = [](auto, auto fb){
    RCLCPP_INFO(...,"got fb size=%zu", fb->partial_sequence.size());
};
opt.result_callback = [](const auto& result){
    if (result.code == rclcpp_action::ResultCode::SUCCEEDED) ...
};
client->async_send_goal(goal, opt);
```

取消：

```cpp
auto cancel_future = client->async_cancel_goal(goal_handle);
```

---

## 四、并发 Goal 控制

| 配置 | 行为 |
|------|------|
| `ACCEPT_AND_EXECUTE` | 立即执行（多 goal 并行） |
| `ACCEPT_AND_DEFER` | 入队，由 `handle_accepted` 决定何时启动 |
| `REJECT` | 拒绝 |

并发要点：
- 每个 goal_handle 一个 worker 线程或独立 future；
- 共享资源加锁；
- 若只允许单 goal：在 `handle_goal` 中检测当前是否有 active goal，必要时拒绝或先 cancel 上一个。

---

## 五、Action CLI

```bash
ros2 action list
ros2 action info /fibonacci -t
ros2 action send_goal /fibonacci my_msgs/action/Fibonacci "{order: 10}" --feedback
```

发送时按 Ctrl+C 会触发 cancel。

---

## 六、Python (rclpy) 端

```python
from rclpy.action import ActionServer, GoalResponse, CancelResponse, ActionClient

class FibServer(Node):
    def __init__(self):
        super().__init__("fib_server")
        self._srv = ActionServer(self, Fibonacci, "fibonacci",
            execute_callback=self.execute,
            goal_callback=self.goal_cb,
            cancel_callback=self.cancel_cb,
            handle_accepted_callback=self.handle_accepted_cb,
            callback_group=ReentrantCallbackGroup())
    def goal_cb(self, goal):  return GoalResponse.ACCEPT
    def cancel_cb(self, gh):  return CancelResponse.ACCEPT
    def handle_accepted_cb(self, gh): gh.execute()
    async def execute(self, gh):
        feedback = Fibonacci.Feedback()
        seq = [0, 1]
        for i in range(1, gh.request.order):
            if gh.is_cancel_requested:
                gh.canceled()
                return Fibonacci.Result(sequence=seq)
            seq.append(seq[i] + seq[i-1])
            feedback.partial_sequence = seq
            gh.publish_feedback(feedback)
            await asyncio.sleep(1)
        gh.succeed()
        return Fibonacci.Result(sequence=seq)
```

⚠️ rclpy 的 `execute_callback` **必须 `async`**；不要在内部 `time.sleep`，用 `asyncio.sleep` 让出控制。

---

## 七、ROS1 vs ROS2 Action 差异

| 维度 | ROS1 | ROS2 |
|------|------|------|
| 实现 | `actionlib`（基于 5 个 topic） | `rclcpp_action`（基于 service + topic + DDS） |
| 取消 | `cancel_pub` | service `cancel_goal` |
| 多 goal | SimpleActionServer 限制单 goal | 原生支持并发 |
| GoalID | 自定义 | `unique_identifier_msgs/UUID` |
| .action 编译 | `actionlib_msgs` | `rosidl_generate_interfaces` |

---

## 八、pluginlib（ROS2）

### 8.1 基本步骤

1. **基类**（接口）
```cpp
class Planner {
public:
    virtual ~Planner() = default;
    virtual void initialize() = 0;
    virtual nav_msgs::msg::Path plan(...) = 0;
};
```

2. **派生类 + 注册宏**
```cpp
#include <pluginlib/class_list_macros.hpp>
PLUGINLIB_EXPORT_CLASS(my_pkg::AStarPlanner, my_base::Planner)
```

3. **plugins.xml**（CMake 中 `pluginlib_export_plugin_description_file()`）
```xml
<library path="my_pkg">
  <class name="my_pkg/AStarPlanner"
         type="my_pkg::AStarPlanner"
         base_class_type="my_base::Planner">
    <description>A* planner</description>
  </class>
</library>
```

4. **package.xml**
```xml
<export>
  <my_base plugin="${prefix}/plugins.xml"/>
</export>
<exec_depend>my_base</exec_depend>
<exec_depend>pluginlib</exec_depend>
```

5. **CMakeLists**
```cmake
find_package(pluginlib REQUIRED)
add_library(my_pkg SHARED src/astar.cpp)
ament_target_dependencies(my_pkg pluginlib my_base)
pluginlib_export_plugin_description_file(my_base plugins.xml)
ament_export_libraries(my_pkg)
```

### 8.2 加载

```cpp
pluginlib::ClassLoader<my_base::Planner> loader("my_base", "my_base::Planner");
auto p = loader.createSharedInstance("my_pkg/AStarPlanner");
p->initialize();
```

### 8.3 ROS2 与 ROS1 差异

- ROS2 走 ament，宏与头文件均迁到 `pluginlib/class_list_macros.hpp`；
- 编译产物路径变化：`ament_index` 解析；
- `pluginlib_export_plugin_description_file()` 替代 ROS1 的 `<export><plugin/></export>` 自动注入；
- 二进制库需 `ament_export_libraries` + `install(TARGETS ... LIBRARY DESTINATION lib)` 才能被 dlopen。

---

## 九、Python 插件（entry_points）

ROS2 推荐 Python 插件用 `setuptools entry_points`，不强依赖 pluginlib：

`setup.py`：
```python
entry_points={
  'my_pkg.planner_plugins': [
    'astar = my_pkg.astar:AStarPlanner',
  ],
}
```

加载：
```python
from importlib.metadata import entry_points
for ep in entry_points(group='my_pkg.planner_plugins'):
    cls = ep.load()
```

---

## 十、面试速记

- Action = goal + result + feedback + cancel；底层 service + topic
- 服务端三回调：`handle_goal / handle_cancel / handle_accepted`，**accepted 里启动 worker，不要阻塞**
- rclpy 的 `execute_callback` 必须 `async`
- ROS2 原生支持**并发 goal**；rclcpp 在 callback group 配合多线程 executor 下可并行
- pluginlib 三件套：**基类 + PLUGINLIB_EXPORT_CLASS + plugins.xml**
- ROS2 用 `pluginlib_export_plugin_description_file()` 替代 ROS1 export 写法
- Python 插件优先 setuptools `entry_points`
