# ROS2 话题、服务与 Action

> ROS2 提供三种核心通信机制：**Topic**（异步发布订阅）、**Service**（同步请求响应）、**Action**（带反馈的长耗时任务）。所有机制都构建在 DDS 的 Topic 之上。

---

## 一、三种机制速览

| 机制 | 模式 | 方向 | 阻塞性 | 数量关系 | 典型场景 |
|------|------|------|--------|----------|----------|
| **Topic** | 发布订阅 | 单向 | 异步 | 多对多 | 传感器数据流、控制指令 |
| **Service** | 请求响应 | 双向 | 调用方可同步/异步 | 一对一（多 Server 不推荐） | 配置查询、一次性触发 |
| **Action** | 请求 + 反馈 + 结果 + 取消 | 双向 | 异步 | 一对一 | 导航到点、机械臂运动 |

---

## 二、Topic（话题）

### 2.1 接口（C++）

```cpp
// Publisher
auto pub = create_publisher<std_msgs::msg::String>(
    "chatter",
    rclcpp::QoS(10).reliable().transient_local());
pub->publish(msg);

// Subscription
auto sub = create_subscription<std_msgs::msg::String>(
    "chatter",
    rclcpp::SensorDataQoS(),
    [](const std_msgs::msg::String::SharedPtr m){ /*...*/ });
```

### 2.2 命名规则

- **绝对名**：`/sensors/imu`
- **相对名**：`imu` → 受节点 namespace 影响（节点 ns=`/robot1` → `/robot1/imu`）
- **私有名**：`~/cmd_vel` → `<node_name>/cmd_vel`
- **重映射**：启动时 `--ros-args -r imu:=/sensors/imu_filtered`

### 2.3 消息生成

定义在包的 `msg/` 目录下：

```idl
# msg/Pose2D.msg
float64 x
float64 y
float64 theta
```

`CMakeLists.txt` 中：
```cmake
find_package(rosidl_default_generators REQUIRED)
rosidl_generate_interfaces(${PROJECT_NAME}
    "msg/Pose2D.msg"
    DEPENDENCIES std_msgs)
```

构建后生成 C++/Python/IDL 多语言绑定。底层使用 OMG IDL（DDS XTypes 兼容）。

### 2.4 QoS 兼容性

发布与订阅 QoS 不匹配则**无法建立连接**（参见 `ROS2 DDS与QoS.md`）。常见预设：

```cpp
rclcpp::QoS(10)                 // 默认 RELIABLE + VOLATILE
rclcpp::SensorDataQoS()         // BEST_EFFORT + KEEP_LAST(5)
rclcpp::ServicesQoS()           // RELIABLE + KEEP_LAST(10)
rclcpp::SystemDefaultsQoS()     // 用 RMW 默认
```

---

## 三、Service（服务）

### 3.1 接口定义

`srv/AddTwoInts.srv`：
```idl
int64 a
int64 b
---
int64 sum
```

构建后生成 `Request` / `Response` 类型。

### 3.2 Server（C++）

```cpp
auto srv = create_service<example_interfaces::srv::AddTwoInts>(
    "add",
    [](const std::shared_ptr<rmw_request_id_t> /*hdr*/,
       const std::shared_ptr<example_interfaces::srv::AddTwoInts::Request> req,
             std::shared_ptr<example_interfaces::srv::AddTwoInts::Response> res){
        res->sum = req->a + req->b;
    });
```

### 3.3 Client（C++）

**异步推荐**：
```cpp
auto cli = create_client<example_interfaces::srv::AddTwoInts>("add");
cli->wait_for_service(std::chrono::seconds(2));

auto req = std::make_shared<example_interfaces::srv::AddTwoInts::Request>();
req->a = 1; req->b = 2;

cli->async_send_request(req,
    [](rclcpp::Client<...>::SharedFuture future){
        RCLCPP_INFO(rclcpp::get_logger("cli"), "sum=%ld", future.get()->sum);
    });
```

**同步（可能死锁）**：
```cpp
auto fut = cli->async_send_request(req);
if (rclcpp::spin_until_future_complete(node, fut)
        == rclcpp::FutureReturnCode::SUCCESS) {
    auto resp = fut.get();
}
```

> ⚠️ 在另一个回调里调用同步等待 → 死锁。务必使用**异步回调**或独立 ReentrantGroup（参见 `ROS2 节点与执行器.md`）。

### 3.4 Service 的限制

- **一对一语义**：虽然可以多个 Server 注册同一服务名，但客户端默认连第一个发现的，行为不确定。
- 不支持长耗时任务（无中间反馈、无取消）→ 使用 Action。
- 服务 QoS 通常 **RELIABLE + KEEP_LAST(10)**，不可改成 BEST_EFFORT。

---

## 四、Action（动作）

适用于**长耗时、可反馈、可取消**的任务。

### 4.1 接口定义

`action/Fibonacci.action`：
```idl
# Goal
int32 order
---
# Result
int32[] sequence
---
# Feedback
int32[] partial_sequence
```

底层映射为：**3 个 Service**（goal / result / cancel）+ **2 个 Topic**（feedback / status）。

### 4.2 Action Server（C++）

```cpp
using Fib = example_interfaces::action::Fibonacci;
using GoalHandle = rclcpp_action::ServerGoalHandle<Fib>;

server_ = rclcpp_action::create_server<Fib>(
    this, "fibonacci",
    [](const rclcpp_action::GoalUUID&, std::shared_ptr<const Fib::Goal> goal){
        return goal->order > 0 ? rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE
                                : rclcpp_action::GoalResponse::REJECT;
    },
    [](const std::shared_ptr<GoalHandle>) {
        return rclcpp_action::CancelResponse::ACCEPT;
    },
    [this](const std::shared_ptr<GoalHandle> gh) {
        std::thread([this, gh]{ execute(gh); }).detach();
    });

void execute(const std::shared_ptr<GoalHandle>& gh) {
    auto fb = std::make_shared<Fib::Feedback>();
    auto res = std::make_shared<Fib::Result>();
    fb->partial_sequence = {0, 1};
    for (int i = 1; i < gh->get_goal()->order; ++i) {
        if (gh->is_canceling()) {
            gh->canceled(res); return;
        }
        fb->partial_sequence.push_back(
            fb->partial_sequence[i] + fb->partial_sequence[i-1]);
        gh->publish_feedback(fb);
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    res->sequence = fb->partial_sequence;
    gh->succeed(res);
}
```

### 4.3 Action Client（C++）

```cpp
client_ = rclcpp_action::create_client<Fib>(this, "fibonacci");
client_->wait_for_action_server();

Fib::Goal goal; goal.order = 10;
rclcpp_action::Client<Fib>::SendGoalOptions opts;
opts.goal_response_callback = [](auto gh){ /* accepted? */ };
opts.feedback_callback = [](auto, std::shared_ptr<const Fib::Feedback> fb){
    /* progress */
};
opts.result_callback = [](const auto& wrapped){
    /* SUCCEEDED / ABORTED / CANCELED */
};
client_->async_send_goal(goal, opts);
```

### 4.4 Goal 状态机

```
PENDING → ACCEPTED → EXECUTING → ┬─ SUCCEEDED
                                  ├─ ABORTED
                                  ├─ CANCELING → CANCELED
                                  └─ ...
```

---

## 五、命令行内省

```bash
# Topic
ros2 topic list
ros2 topic info /chatter --verbose          # QoS / 端点
ros2 topic echo /chatter
ros2 topic pub /chatter std_msgs/msg/String "{data: hi}"
ros2 topic hz /scan
ros2 topic bw /image

# Service
ros2 service list
ros2 service type /add
ros2 service call /add example_interfaces/srv/AddTwoInts "{a: 1, b: 2}"

# Action
ros2 action list
ros2 action info /fibonacci
ros2 action send_goal /fibonacci example_interfaces/action/Fibonacci \
     "{order: 5}" --feedback

# Interface 检查
ros2 interface show std_msgs/msg/Header
ros2 interface proto sensor_msgs/msg/Image
```

---

## 六、性能与选型建议

| 选择 | 原则 |
|------|------|
| 高频流式（IMU / Image / PointCloud） | **Topic + SensorDataQoS** + 大消息考虑 Zero-Copy |
| 一次性配置 / 状态查询 | **Service** |
| 路径规划、运动控制、长任务 | **Action**（带反馈/可取消） |
| 多对多事件广播 | **Topic** |
| 跨进程参数热更新 | **Parameter Event Topic** |

---

## 七、常见陷阱

1. **QoS 不匹配导致接收不到数据**：默认 Pub=RELIABLE，Sub=BEST_EFFORT 时不匹配（取决于历史/可靠性策略）。用 `ros2 topic info -v` 确认。
2. **同步 Service 死锁**：见上文，必须异步。
3. **Action 反馈频率过高**：Feedback 走的是 Topic，频率太高会拥塞，建议 ≤ 10Hz。
4. **大消息 + RELIABLE + 历史深度大** → 内存暴涨，及时 take。
5. **多个 Subscriber 处理慢** → 慢者拖累整个 Pub（取决于 RMW），可用 `transient_local` + `keep_last(1)` 隔离。

---

## 八、面试速记

- 三种机制的本质：**Topic = DDS DataWriter/Reader；Service = 两个 Topic；Action = 多 Service + 多 Topic**
- 选型口诀：**流数据 Topic、一问一答 Service、长任务 Action**
- 同步调用必死锁，**始终首选异步回调**
- 通信不通 80% 是 **QoS 不匹配** 或 **namespace/remap 错误**
