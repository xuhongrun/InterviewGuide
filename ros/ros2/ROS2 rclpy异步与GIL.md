# ROS2 rclpy 异步与 GIL 实战

> rclpy 的并发模型与 C++ 不同：受 **GIL** 影响、回调在 Python 线程中执行。本文聚焦异步、Executor、async/await、与 asyncio 集成的常见坑。

---

## 一、rclpy 基本结构

```python
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class Talker(Node):
    def __init__(self):
        super().__init__('talker')
        self.pub = self.create_publisher(String, 'chatter', 10)
        self.timer = self.create_timer(0.5, self._tick)
        self._i = 0

    def _tick(self):
        msg = String(data=f"hi {self._i}")
        self.pub.publish(msg)
        self._i += 1

def main():
    rclpy.init()
    rclpy.spin(Talker())
    rclpy.shutdown()
```

`rclpy.spin(node)` = 默认 `SingleThreadedExecutor`，回调串行。

---

## 二、Executor 与 CallbackGroup

```python
from rclpy.executors import MultiThreadedExecutor, SingleThreadedExecutor
from rclpy.callback_groups import (
    MutuallyExclusiveCallbackGroup,
    ReentrantCallbackGroup,
)

cb_group = ReentrantCallbackGroup()
node.create_subscription(Image, "img", cb, 10, callback_group=cb_group)

exec = MultiThreadedExecutor(num_threads=4)
exec.add_node(node)
try:
    exec.spin()
finally:
    exec.shutdown()
```

| 类型 | 默认 |
|------|------|
| `MutuallyExclusiveCallbackGroup`（默认） | 同组互斥 |
| `ReentrantCallbackGroup` | 可重入并发 |

> ⚠️ Python 受 **GIL** 影响：即便 MultiThreadedExecutor，CPU 密集回调仍是串行；I/O 阻塞型并发收益明显。

---

## 三、Service 嵌套调用（必踩坑）

错误写法（**死锁**）：

```python
# 默认 group: MutuallyExclusive
def my_service_cb(req, resp):
    future = self.client.call_async(other_req)
    rclpy.spin_until_future_complete(self.node, future)  # ⚠️ 自己等自己
    resp.value = future.result().value
    return resp
```

修复方式：

### 方式 1：把 client 放独立 ReentrantCallbackGroup

```python
self.client = self.create_client(
    SrvT, "other", callback_group=ReentrantCallbackGroup())
self.create_service(
    SrvT2, "self", my_service_cb,
    callback_group=ReentrantCallbackGroup())
```

并使用 `MultiThreadedExecutor`。

### 方式 2：异步回调（推荐）

```python
def my_service_cb(req, resp):
    future = self.client.call_async(other_req)
    future.add_done_callback(
        lambda fut: self._on_other_done(fut, resp))
    return resp   # 注意：rclpy 同步 service 必须返回 resp，不能挂起
```

ROS2 service 回调本身**不支持 async**，要异步只能 `add_done_callback`。

---

## 四、async/await 模式（Action / 协程化业务）

rclpy 提供 `rclpy.task.Future`，可与 asyncio 协同：

```python
import asyncio
from rclpy.executors import MultiThreadedExecutor

async def main_async(node):
    cli = node.create_client(SrvT, "/srv")
    while not cli.wait_for_service(timeout_sec=0.5):
        node.get_logger().info("waiting...")
    req = SrvT.Request(...)
    future = cli.call_async(req)
    # rclpy.Future 不是 asyncio.Future，直接 await 不行
    while not future.done():
        await asyncio.sleep(0.01)
    return future.result()
```

或者用 `rclpy.spin_until_future_complete` + 单独线程跑 spinner：

```python
import threading
def spin_thread():
    rclpy.spin(node, executor=MultiThreadedExecutor())

threading.Thread(target=spin_thread, daemon=True).start()
# 主线程 asyncio.run(...)
```

---

## 五、Action 客户端（典型异步用法）

```python
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose

class NavClient(Node):
    def __init__(self):
        super().__init__("nav_client")
        self._cli = ActionClient(self, NavigateToPose, "navigate_to_pose")

    def send(self, pose):
        self._cli.wait_for_server()
        goal = NavigateToPose.Goal(pose=pose)
        self._send_goal_future = self._cli.send_goal_async(
            goal, feedback_callback=self._fb)
        self._send_goal_future.add_done_callback(self._goal_resp)

    def _goal_resp(self, fut):
        gh = fut.result()
        if not gh.accepted:
            return
        self._result_future = gh.get_result_async()
        self._result_future.add_done_callback(self._on_done)

    def _fb(self, fb):
        self.get_logger().info(f"distance={fb.feedback.distance_remaining:.2f}")

    def _on_done(self, fut):
        result = fut.result().result
        ...
```

---

## 六、跨线程发布

`rclpy` 默认线程安全的 publisher / client，但**回调上下文**只能在 Executor 线程执行。从外部线程发布安全：

```python
# 任何线程都可以
self.pub.publish(msg)
```

但**修改节点状态**（添加/移除 sub）必须在 Executor 线程或加锁。

---

## 七、性能与 GIL

CPU 密集型场景：
- 用 C++ 编写关键节点（rclcpp）；
- 或 `multiprocessing` 进程隔离（每进程一个 ROS Context，性能不重叠）；
- C 扩展（numpy 操作）会释放 GIL，可获得多线程加速；
- numba/torch/cv2 等也释放 GIL。

I/O 阻塞型场景：MultiThreadedExecutor 收益明显。

---

## 八、参数与日志

```python
self.declare_parameter("rate", 10.0)
rate = self.get_parameter("rate").value

self.add_on_set_parameters_callback(self._on_params_changed)

self.get_logger().info("hello")
self.get_logger().warn("warn")
self.get_logger().debug("debug")     # 默认不输出
```

启用 debug：`ros2 run my_pkg my_node --ros-args --log-level DEBUG`。

---

## 九、常见坑

| 现象 | 原因 |
|------|------|
| 回调不被触发 | 没 `rclpy.spin` / 节点未 add 到 executor |
| Service 内部 wait future 死锁 | 默认互斥 group，需 Reentrant + MultiThreaded 或 add_done_callback |
| `Ctrl+C` 不退出 | 用 `try/finally rclpy.shutdown()` 包裹 |
| sleep 后回调延迟 | `time.sleep` 阻塞 Executor 线程，应用 timer 或 async |
| `KeyboardInterrupt` 抛错 | 捕获 `KeyboardInterrupt`、`ExternalShutdownException` |

```python
try:
    rclpy.spin(node)
except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
    pass
finally:
    node.destroy_node()
    rclpy.try_shutdown()
```

---

## 十、面试速记

- rclpy 默认 SingleThreaded + MutuallyExclusive；CPU 密集受 GIL 限制
- **Service 内调 Service 死锁**：放 ReentrantGroup + MultiThreaded，或用 `add_done_callback`
- rclpy `Future` 不是 asyncio `Future`，不能直接 await，需 polling 或 done_callback
- 关键节点 / 实时性能敏感场景用 C++（rclcpp）
- 退出务必 `try/finally` 关 spin，处理 `ExternalShutdownException`
