# ROS2 消息序列化、IDL 与 XTypes

> ROS2 的接口体系建立在 **OMG IDL** 之上，通过 **rosidl** 工具链生成多语言绑定，并支持 **DDS XTypes** 动态/可扩展类型。

---

## 一、接口类型与文件

ROS2 支持三类接口文件，全部由 rosidl 编译：

| 类型 | 后缀 | 内容 |
|------|------|------|
| Message | `.msg` | 单一数据结构 |
| Service | `.srv` | Request + Response |
| Action | `.action` | Goal + Result + Feedback |

底层：`.msg` / `.srv` / `.action` 都会被转成 **OMG IDL（`.idl`）**，再由 rosidl 多语言生成器（`rosidl_generator_cpp` / `_py` / `_dds_idl` ...）生成对应代码。

---

## 二、字段类型

### 2.1 基本类型

| ROS 类型 | C++ | Python | DDS IDL |
|----------|-----|--------|---------|
| `bool` | `bool` | `bool` | `boolean` |
| `byte` / `octet` | `uint8_t` | `bytes` | `octet` |
| `char` | `unsigned char` | `str` | `char` |
| `float32` / `float64` | `float` / `double` | `float` | `float` / `double` |
| `int8` / `uint8` | `int8_t` / `uint8_t` | `int` | `int8` / `uint8` |
| `int16/32/64`、`uint16/32/64` | 同名 | `int` | 同名 |
| `string` | `std::string` | `str` | `string` |
| `wstring` | `std::u16string` | `str` | `wstring` |

### 2.2 数组与序列

| 写法 | 含义 |
|------|------|
| `int32[]` | 无界序列（unbounded sequence） |
| `int32[3]` | 固定长度数组 |
| `int32[<=10]` | **有界序列**（最大 10） |
| `string<=64` | 有界字符串 |
| `string<=64[<=10]` | 有界字符串的有界序列 |

> **有界类型**对实时与零拷贝至关重要：固定上界才能在共享内存中预分配。

### 2.3 默认值与常量

```idl
# msg/Mode.msg
uint8 IDLE = 0
uint8 RUNNING = 1
uint8 ERROR = 2

uint8 state 0          # 字段名 + 默认值
string<=32 description "default text"
float64 rate 10.0
```

### 2.4 嵌套与复用

```idl
std_msgs/Header header
geometry_msgs/Pose pose
sensor_msgs/Image[<=4] images
```

依赖在 `package.xml` 用 `<depend>` 声明，`CMakeLists.txt` 中 `rosidl_generate_interfaces(... DEPENDENCIES std_msgs geometry_msgs sensor_msgs)`。

---

## 三、Service / Action 文件

### 3.1 Service

```idl
# srv/AddTwoInts.srv
int64 a
int64 b
---
int64 sum
```

生成：
- `AddTwoInts_Request`
- `AddTwoInts_Response`
- `AddTwoInts`（含上述两者）

### 3.2 Action

```idl
# action/Fibonacci.action
int32 order
---
int32[] sequence
---
int32[] partial_sequence
```

生成：
- `Fibonacci_Goal` / `_Result` / `_Feedback`
- `Fibonacci_SendGoal` / `_GetResult`（内部 Service）
- `Fibonacci_FeedbackMessage`（内部 Topic）

---

## 四、生成产物

```
build/my_msgs/rosidl_generator_cpp/my_msgs/msg/
  ├── pose2_d.hpp                # 用户用
  ├── detail/pose2_d__struct.hpp # 实际结构
  └── detail/pose2_d__traits.hpp # type traits

build/my_msgs/rosidl_generator_py/my_msgs/msg/
  ├── _pose2_d.py
  └── ...

build/my_msgs/rosidl_typesupport_*  # 各 RMW 的 typesupport
```

C++ 用法：
```cpp
#include "my_msgs/msg/pose2_d.hpp"
my_msgs::msg::Pose2D p;
p.x = 1.0; p.theta = M_PI;
```

Python：
```python
from my_msgs.msg import Pose2D
p = Pose2D(x=1.0, theta=3.14)
```

---

## 五、序列化层（CDR）

DDS 默认采用 **OMG CDR（Common Data Representation）** 进行二进制序列化：
- **little-endian** 优先（XCDR2）；
- 自然对齐（4-byte / 8-byte）；
- 字符串 = `uint32 len + bytes + '\0'`；
- 序列 = `uint32 len + element*`。

ROS2 使用：
- **CDR1**（Foxy–Galactic）
- **XCDR2**（Humble+，更紧凑、对齐放宽）

可手工序列化/反序列化：
```cpp
#include "rclcpp/serialization.hpp"
#include "rclcpp/serialized_message.hpp"

rclcpp::Serialization<MsgT> ser;
rclcpp::SerializedMessage raw;
ser.serialize_message(&msg, &raw);

MsgT msg2;
ser.deserialize_message(&raw, &msg2);
```

适用场景：bag 录制、网络转发、跨进程零拷贝传递。

### 通用订阅（type-erased）

```cpp
auto sub = create_generic_subscription(
    "/chatter", "std_msgs/msg/String",
    rclcpp::QoS(10),
    [](std::shared_ptr<rclcpp::SerializedMessage> raw){
        // 不依赖具体类型，可做 bag/转发
    });
```

`create_generic_publisher` 同理。`rosbag2` 即基于此机制实现。

---

## 六、XTypes：可扩展类型系统

### 6.1 动机

普通 IDL 类型一旦发布，**字段增删会破坏二进制兼容**。XTypes 引入：
- **可扩展性注解**（FINAL / APPENDABLE / MUTABLE）；
- **DataRepresentation**（XCDR2、XML、JSON）；
- **TypeObject / TypeIdentifier** 在线交换类型描述，发现期协商。

### 6.2 注解（Iron+ 支持）

```idl
@verbatim (language="comment", text="可扩展消息")
@appendable
struct SensorReading {
    int64 timestamp;
    float64 value;
};

@final
struct ImmutableHeader {
    string<32> id;
};

@mutable
struct DynamicState {
    @id(0x0001) int32 mode;
    @id(0x0002) @optional float64 temperature;
};
```

| 注解 | 含义 |
|------|------|
| `@final` | 不可变；增删字段直接不兼容 |
| `@appendable` | **末尾追加新字段**保持向后兼容（默认） |
| `@mutable` | 任意位置增删；用 `@id` 唯一标识；最灵活 |
| `@optional` | 字段可缺失 |
| `@key` | 实例键（DDS Instance / `take_with_key`） |

### 6.3 兼容性规则（XTypes 1.3）

新订阅者收到旧 Pub 的数据时：
- `@final`：必须**完全相同**类型；
- `@appendable`：旧 Pub 数据末尾少字段 → 用默认值填充；
- `@mutable`：按 `@id` 字段映射，缺失字段填默认。

### 6.4 ROS2 中的支持现状

| 版本 | 支持程度 |
|------|----------|
| Humble | 仅 `.msg` → 默认 APPENDABLE 语义；XTypes 注解部分支持 |
| Iron | 增强 XTypes 注解 + Type Description 服务 |
| Jazzy | **Type Description 服务** 默认启用，节点暴露 `~/get_type_description`，rmw 可使用 TypeObject 在发现期校验 |

可在 `ros2 topic info -v` 看到双方使用的 `data_representation` 与类型 hash。

---

## 七、Loaned Messages 与有界类型

只有**全部字段为有界类型**（POD + bounded sequence/string）的消息，才能走真正的零拷贝（Loaned Messages + SHM）。

```idl
# 不能零拷贝
int32[] data            # 无界

# 可以零拷贝
int32[<=1024] data
string<=64 name
```

实践：自动驾驶高频消息建议**显式 bounded**；`sensor_msgs/PointCloud2` 不带上限，需替换为带 capacity 的自定义类型才能走 SHM。

---

## 八、与原生 DDS 互操作

ROS2 在 DDS 层 Topic 名加前缀：

| ROS2 | DDS Topic |
|------|-----------|
| 普通 topic `/chatter` | `rt/chatter` |
| Service Request | `rq/<name>Request` |
| Service Reply | `rr/<name>Reply` |
| Action Goal/Result/Feedback | `rt/...`、`rs/...` |

Type 名由 IDL module 路径 + 类型名构成（如 `std_msgs::msg::dds_::String_`）。原生 DDS 应用按此规则即可与 ROS2 互通。

---

## 九、面试速记

- ROS2 接口由 **rosidl 工具链** 编译，底层是 **OMG IDL + CDR**
- 字段类型：基本类型 / `[]` 无界 / `[N]` 固定 / `[<=N]` 有界 / `string<=N`
- `.msg` / `.srv` / `.action` 三类接口文件，均生成多语言绑定
- 序列化：**CDR1（旧）/ XCDR2（Humble+）**；可用 `Serialization` 手工序列化
- 通用订阅 `create_generic_subscription` 可不依赖具体类型（rosbag2 基础）
- **XTypes 注解**：`@final` / `@appendable`（默认）/ `@mutable` + `@optional` + `@key`
- 零拷贝必须**全有界类型**
- ROS2 ↔ 原生 DDS：Topic 名加 `rt/`、`rq/`、`rr/` 前缀
