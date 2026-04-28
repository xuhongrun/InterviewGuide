# ROS1 通信机制详解

> 详述 ROS1 四种通信原语：Topic / Service / Action / Parameter Server，含底层握手与代码示例。

---

## 一、Topic（话题）

### 1.1 通信流程（含底层）

```
Publisher                Master                   Subscriber
   │                        │                         │
   │  registerPublisher()   │                         │
   ├───────────────────────►│                         │
   │                        │   registerSubscriber()  │
   │                        │◄────────────────────────┤
   │                        │  publisherUpdate()      │
   │                        ├────────────────────────►│
   │                                                  │
   │                                  requestTopic()  │
   │◄─────────────────────────────────────────────────┤
   │  TCPROS handshake (header + protocol)            │
   ├─────────────────────────────────────────────────►│
   │  data stream (serialized msg + length-prefix)    │
   ├─────────────────────────────────────────────────►│
```

- Master 仅参与**注册与发现**，**数据走点对点 TCP/UDP**；
- 一旦连接建立，Master 挂掉**已建立的话题不会断开**，但新订阅者无法发现。

### 1.2 TCPROS 协议

每条连接：
1. **握手 Header**：键值对（`callerid`、`topic`、`md5sum`、`type`、`message_definition`、`tcp_nodelay`、`latching`）；
2. **数据流**：`[4-byte length][serialized message bytes]` 反复。

UDPROS 类似但走 UDP 数据报，每条消息可能被分片重组，**不保证可靠**。

### 1.3 Publisher / Subscriber 代码

**C++（roscpp）**：
```cpp
#include <ros/ros.h>
#include <std_msgs/String.h>

int main(int argc, char** argv) {
    ros::init(argc, argv, "talker");
    ros::NodeHandle nh;

    // queue_size=10：发送队列；满则按策略丢弃（latch=false 时）
    // latch=true：保留最后一条给后加入的订阅者（类似 ROS2 的 TRANSIENT_LOCAL）
    auto pub = nh.advertise<std_msgs::String>("chatter", 10, /*latch=*/false);

    ros::Rate rate(10);    // 10Hz
    while (ros::ok()) {
        std_msgs::String msg;
        msg.data = "hello";
        pub.publish(msg);
        ros::spinOnce();
        rate.sleep();
    }
}
```

```cpp
void cb(const std_msgs::String::ConstPtr& msg) {
    ROS_INFO("got: %s", msg->data.c_str());
}

ros::init(argc, argv, "listener");
ros::NodeHandle nh;
auto sub = nh.subscribe("chatter", 10, cb);
ros::spin();   // 阻塞，回调由内部线程池触发
```

### 1.4 队列与 `tcp_nodelay`

| 选项 | 影响 |
|------|------|
| Publisher `queue_size` | 发送侧异步队列，0 表示同步发送（不推荐） |
| Subscriber `queue_size` | 接收侧队列，满则丢最旧；设小可降延迟 |
| `tcp_nodelay=true`（订阅时） | 关闭 Nagle 算法，降低小消息延迟 |
| `latch=true` | 保留最后一条给晚到订阅者 |

```cpp
ros::TransportHints hints;
hints.tcpNoDelay(true).reliable();
auto sub = nh.subscribe("chatter", 1, cb, hints);
```

### 1.5 Topic 命名

| 前缀 | 含义 |
|------|------|
| `/scan` | 全局名 |
| `scan` | 相对名（受 `__ns` 影响） |
| `~scan` | 私有名 → `<node_name>/scan` |

重映射：
```bash
rosrun pkg node /scan:=/sensors/lidar_front
```

---

## 二、Service（服务）

### 2.1 模型

- **同步请求/响应**，本质上一次性 TCP 连接（默认）或长连接（`persistent=true`）；
- 一对一：同名 Service 后注册者**覆盖**前一个。

### 2.2 srv 文件

`srv/AddTwoInts.srv`：
```
int64 a
int64 b
---
int64 sum
```

`CMakeLists.txt`：
```cmake
add_service_files(FILES AddTwoInts.srv)
generate_messages(DEPENDENCIES std_msgs)
catkin_package(CATKIN_DEPENDS message_runtime)
```

### 2.3 Server / Client

```cpp
bool add(my_pkg::AddTwoInts::Request& req,
         my_pkg::AddTwoInts::Response& res) {
    res.sum = req.a + req.b;
    return true;
}
auto srv = nh.advertiseService("add", add);
```

```cpp
auto cli = nh.serviceClient<my_pkg::AddTwoInts>("add", /*persistent=*/false);
my_pkg::AddTwoInts call;
call.request.a = 1; call.request.b = 2;
if (cli.call(call)) {
    ROS_INFO("sum=%ld", call.response.sum);
}
```

> Persistent Service：保持连接，避免反复握手；服务端重启需要客户端检测重连。

---

## 三、Action（actionlib）

适用于**长耗时任务**（带反馈、可取消），底层由 5 个 Topic 组合：

```
client                                          server
   │  /goal     ───────────────────────────────►│
   │  /cancel   ───────────────────────────────►│
   │  /feedback ◄───────────────────────────────│
   │  /status   ◄───────────────────────────────│
   │  /result   ◄───────────────────────────────│
```

### 3.1 action 文件

`action/Fibonacci.action`：
```
int32 order
---
int32[] sequence
---
int32[] partial_sequence
```

`CMakeLists.txt`：
```cmake
find_package(catkin REQUIRED actionlib actionlib_msgs)
add_action_files(FILES Fibonacci.action)
generate_messages(DEPENDENCIES actionlib_msgs)
```

### 3.2 SimpleActionServer

```cpp
#include <actionlib/server/simple_action_server.h>
#include <my_pkg/FibonacciAction.h>

using Server = actionlib::SimpleActionServer<my_pkg::FibonacciAction>;

class FibAction {
public:
    FibAction(ros::NodeHandle& nh)
        : as_(nh, "fibonacci",
              boost::bind(&FibAction::execute, this, _1), false) {
        as_.start();
    }
    void execute(const my_pkg::FibonacciGoalConstPtr& goal) {
        my_pkg::FibonacciFeedback fb;
        my_pkg::FibonacciResult res;
        fb.partial_sequence = {0, 1};
        ros::Rate r(10);
        for (int i = 1; i < goal->order; ++i) {
            if (as_.isPreemptRequested() || !ros::ok()) {
                as_.setPreempted(); return;
            }
            fb.partial_sequence.push_back(
                fb.partial_sequence[i] + fb.partial_sequence[i-1]);
            as_.publishFeedback(fb);
            r.sleep();
        }
        res.sequence = fb.partial_sequence;
        as_.setSucceeded(res);
    }
private:
    Server as_;
};
```

### 3.3 SimpleActionClient

```cpp
#include <actionlib/client/simple_action_client.h>
using Client = actionlib::SimpleActionClient<my_pkg::FibonacciAction>;

Client ac("fibonacci", true);
ac.waitForServer();
my_pkg::FibonacciGoal goal; goal.order = 10;
ac.sendGoal(goal,
    /*done_cb=*/  [](const auto& state, const auto& res){ /*...*/ },
    /*active_cb=*/[]{},
    /*fb_cb=*/    [](const auto& fb){ /* progress */ });
ac.waitForResult(ros::Duration(30.0));
```

---

## 四、Parameter Server

由 Master 维护的全局键值存储：

```cpp
nh.setParam("max_speed", 2.0);
double v;
nh.param("max_speed", v, 1.0);     // 第三个为默认值
nh.getParam("frame_id", frame_);
```

YAML 加载：
```bash
rosparam load config.yaml /robot1
rosparam dump out.yaml /robot1
rosparam list
rosparam get /robot1/max_speed
```

`launch` 文件：
```xml
<param name="max_speed" value="2.0"/>
<rosparam command="load" file="$(find my_pkg)/config/params.yaml"/>
```

**Dynamic Reconfigure**（动态参数）：
- 独立机制，使用 `*.cfg` 文件 + `dynamic_reconfigure` 包；
- 在 `rqt_reconfigure` 中实时调参。
- ROS2 中被 **Parameter Events** + 描述符直接取代。

```python
# cfg/MyParams.cfg
PACKAGE = "my_pkg"
from dynamic_reconfigure.parameter_generator_catkin import *
gen = ParameterGenerator()
gen.add("max_speed", double_t, 0, "Max linear speed", 1.0, 0.0, 5.0)
exit(gen.generate(PACKAGE, "my_node", "MyParams"))
```

---

## 五、TF（坐标系树）

`tf` 已被 **`tf2`** 取代（ROS1 后期与 ROS2 通用）。要点：
- `/tf` 与 `/tf_static` 话题（`tf_static` 用 latched）；
- `tf2_ros::Buffer` + `TransformListener` 缓存 + 查询；
- `lookupTransform(target, source, time)` 与 ROS2 一致。

详细参考 ROS2 文档（[ROS2 TF2与时间.md](../ros2/ROS2%20TF2与时间.md)）—— TF2 API 在两代中基本相同。

---

## 六、Nodelet（进程内零拷贝雏形）

- ROS1 的 Nodelet = **同进程动态加载多个 “mini node”**，共享指针避免序列化；
- 通过 `nodelet_manager` 进程加载多个继承 `nodelet::Nodelet` 的类；
- 是 ROS2 **Composition** 的前身，但接口更繁琐（必须用 `boost::shared_ptr<const T>`）。

```cpp
class MyNodelet : public nodelet::Nodelet {
    void onInit() override {
        ros::NodeHandle& nh = getNodeHandle();
        sub_ = nh.subscribe("in", 10, &MyNodelet::cb, this);
        pub_ = nh.advertise<MsgT>("out", 10);
    }
    void cb(const MsgT::ConstPtr& msg) {
        // 同进程 publisher 直接拿到 const 指针，零拷贝
        pub_.publish(msg);
    }
};
PLUGINLIB_EXPORT_CLASS(my_pkg::MyNodelet, nodelet::Nodelet)
```

---

## 七、面试速记

- 四原语：**Topic（异步）/ Service（同步）/ Action（长任务）/ Parameter（全局 KV）**
- Topic 用 TCPROS（默认）/ UDPROS；Master 不参与数据传输
- Service 一对一同步；persistent 模式可复用连接
- Action 由 5 个 Topic 组合实现，带 feedback / cancel
- Parameter Server 是中心化全局 KV，Dynamic Reconfigure 提供动态调参
- Nodelet 是 ROS1 进程内零拷贝方案（ROS2 Composition 前身）
