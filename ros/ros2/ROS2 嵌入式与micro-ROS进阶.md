# ROS2 嵌入式与 micro-ROS 进阶

> 在 [ROS2 micro-ROS与嵌入式](ROS2%20micro-ROS与嵌入式.md) 之上深入：自定义传输、内存策略、Yocto 集成、QNX/VxWorks。

---

## 一、micro-ROS 架构

```
┌─────────────── MCU 端 ────────────────┐    ┌──── Linux 端 ────┐
│  rcl + rclc                           │    │ micro_ros_agent  │
│   ↓                                   │    │   ↓              │
│  uxrCE-DDS Client (Micro XRCE-DDS)    │◄──►│  Fast DDS / DDS  │
│   ↓                                   │UART│   ↑              │
│  Custom Transport (UART/UDP/CAN/USB)  │    │  ROS2 graph      │
└───────────────────────────────────────┘    └──────────────────┘
```

- **Micro XRCE-DDS**：极简版 DDS，运行在 RTOS / 裸机；
- **Agent**：把 XRCE-DDS 流转换为标准 DDS。

支持平台：FreeRTOS、Zephyr、NuttX、Mbed、ESP-IDF、Renesas、STM32CubeMX 等。

---

## 二、典型工程（Zephyr 示例）

```bash
# 主机端 agent
docker run -it --rm --net=host microros/micro-ros-agent:jazzy \
    serial --dev /dev/ttyUSB0 -b 115200
```

MCU 代码：
```c
#include <rcl/rcl.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>
#include <std_msgs/msg/int32.h>

rclc_support_t support;
rcl_node_t node;
rcl_publisher_t pub;
std_msgs__msg__Int32 msg;

void timer_cb(rcl_timer_t* t, int64_t last) {
    rcl_publish(&pub, &msg, NULL);
    msg.data++;
}

int main() {
    rcl_allocator_t alloc = rcl_get_default_allocator();
    rclc_support_init(&support, 0, NULL, &alloc);
    rclc_node_init_default(&node, "mcu_node", "", &support);
    rclc_publisher_init_default(&pub, &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int32), "mcu_topic");

    rcl_timer_t timer;
    rclc_timer_init_default(&timer, &support, RCL_MS_TO_NS(500), timer_cb);

    rclc_executor_t exec;
    rclc_executor_init(&exec, &support.context, 1, &alloc);
    rclc_executor_add_timer(&exec, &timer);
    while (1) rclc_executor_spin_some(&exec, RCL_MS_TO_NS(100));
}
```

---

## 三、自定义传输

实现 4 个回调即可挂任意物理层：

```c
bool open(struct uxrCustomTransport* t) { ... }
bool close(struct uxrCustomTransport* t) { ... }
size_t write(struct uxrCustomTransport* t, const uint8_t* buf, size_t len, uint8_t* err) { ... }
size_t read (struct uxrCustomTransport* t, uint8_t* buf, size_t len, int timeout, uint8_t* err) { ... }
```

注册：
```c
rmw_uros_set_custom_transport(true /*framing*/, NULL,
    open, close, write, read);
```

常见物理层：UART、USB-CDC、UDP、TCP、CAN-FD、SPI。

CAN-FD 注意：MTU 64B，需自行分片或裁小消息。

---

## 四、内存策略

micro-ROS 默认动态分配 → 嵌入式不友好。可切**static_memory_strategy**：

```c
rcl_init_options_t init_options = rcl_get_zero_initialized_init_options();
static rclc_executor_handle_t exec_handles[8];
rclc_executor_t exec;
rclc_executor_init_with_static_memory(&exec, &ctx,
    8, exec_handles, &alloc);
```

`colcon.meta`：
```json
{
  "names": {
    "rmw_microxrcedds": {
      "cmake-args": [
        "-DRMW_UXRCE_MAX_NODES=4",
        "-DRMW_UXRCE_MAX_PUBLISHERS=8",
        "-DRMW_UXRCE_MAX_SUBSCRIPTIONS=8",
        "-DRMW_UXRCE_MAX_HISTORY=4"
      ]
    }
  }
}
```

预分配实例数后，运行时不再 malloc。

---

## 五、Yocto / Buildroot 集成

`meta-ros` Yocto layer：把完整 ROS2 distro 烤进嵌入式 Linux。

```bash
git clone https://github.com/ros/meta-ros
# 在 build/conf/bblayers.conf 加 meta-ros-common, meta-ros2, meta-ros2-jazzy
# local.conf:
DISTRO = "ros2-jazzy"
IMAGE_INSTALL:append = " ros-core ros-base"
bitbake core-image-minimal
```

适用：i.MX8、Jetson、TI Sitara、瑞芯微等嵌入式 SoC。

Buildroot 可用 `br2-external-ros2`（社区项目）。

---

## 六、QNX / VxWorks（实时 OS）

| 平台 | 状态 |
|------|------|
| QNX 7.x | Tier-3，eProsima 提供 Fast DDS QNX 移植，社区有 ROS2 port |
| VxWorks 7 | Wind River 支持 RTI Connext + ROS2 |
| Integrity | RTI 商业支持 |

要点：
- 编译期需提供 toolchain 文件；
- POSIX 子集差异：`std::thread` 优先级、信号、shm；
- DDS 选 RTI Connext（商业）或 Cyclone DDS（社区）。

---

## 七、micro-ROS 多机部署

- 一个 Agent 可服务多个 MCU（多串口）；
- 也可用 UDP 让多 MCU 共享一个 Agent；
- Agent 桥的 ROS2 节点会以 `<namespace>/<node>` 出现在标准 graph，工具完全可用（rqt、rosbag2）。

---

## 八、调试技巧

| 工具 | 用途 |
|------|------|
| `ros2 topic echo` | 桥后看消息 |
| Agent verbose `--verbose 6` | 看 XRCE 协议 |
| Wireshark + xrce-dds-dissector | 协议层分析 |
| `nm -D firmware.elf \| grep rcl_` | 验证库链接 |
| 串口分析仪 / 逻辑分析仪 | 物理层 |

---

## 九、嵌入式 Linux + 标准 ROS2

不用 micro-ROS，直接在嵌入式 Linux 跑标准 ROS2 时：

- **Cyclone DDS**：占用最小（推荐）；
- 关闭未用 RMW 模块，禁多播：unicast Discovery Server；
- 大消息用 SHM/iceoryx；
- 启用 `ROS_LOCALHOST_ONLY=1` 隔离；
- `update_rate` 控制循环跑实时核（PREEMPT_RT）。

---

## 十、面试速记

- micro-ROS = MCU 上跑 RCL + **Micro XRCE-DDS**，需 Agent 桥到 DDS
- 自定义传输实现 4 callback：open/close/read/write
- 嵌入式必用 **static_memory_strategy**，编译期定上限
- 嵌入式 Linux 集成走 **Yocto meta-ros**
- QNX/VxWorks 走 **RTI Connext**（商业），或 Cyclone 社区移植
- 标准 ROS2 在嵌入式 Linux：**Cyclone + iceoryx + Discovery Server**，CPU isolation
