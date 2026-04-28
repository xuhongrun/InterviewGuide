# micro-ROS 与嵌入式 ROS2

> micro-ROS 把 ROS2 客户端库适配到 **MCU / RTOS**（Cortex-M、ESP32、Renesas、STM32、NuttX、FreeRTOS、Zephyr 等），通过 **Agent** 桥接到主网 DDS。

---

## 一、定位与场景

- **目标硬件**：内存 ≥ 32KB RAM 的微控制器（如 STM32F4、ESP32、Teensy）；
- **典型应用**：传感器节点、电机控制器、IO 扩展板、低功耗边缘节点；
- **替代场景**：替代旧式 CAN/Modbus → 直接成为 ROS2 节点，统一架构。

整体拓扑：

```
┌──────────── ROS2 Domain ────────────────┐
│  ┌──────┐   ┌──────┐                     │
│  │ Node │   │ Node │  (普通 rclcpp/rclpy) │
│  └──┬───┘   └──┬───┘                     │
│     │ DDS     │                          │
│     └─────────┴──────► micro-ROS Agent ──┼──┐ Serial / UDP / TCP / CAN
│                       (rmw + middleware) │  │
└──────────────────────────────────────────┘  ▼
                                       ┌────────────────┐
                                       │ MCU            │
                                       │  micro-ROS     │
                                       │  (rclc + rmw_  │
                                       │   microxrcedds)│
                                       └────────────────┘
```

---

## 二、技术栈分层

```
应用代码 (C)
   │
rclc            ← ROS Client Library for C（专为 MCU，与 rcl 同级）
   │
rcl + rcutils   ← 共享 ROS2 核心
   │
rmw_microxrcedds_c  ← MCU 端 RMW 实现
   │
Micro XRCE-DDS Client  ← OMG XRCE-DDS（精简版 DDS）
   │
Transport (UART / UDP / TCP / Custom)
   │
   ▼
Micro XRCE-DDS Agent (PC/网关侧)
   │
rmw_fastrtps_cpp 或 rmw_cyclonedds_cpp
   │
DDS Network → 普通 ROS2 节点
```

| 组件 | 说明 |
|------|------|
| **rclc** | C 语言精简客户端，无 STL、无异常、无动态分配（默认） |
| **Micro XRCE-DDS** | OMG 标准 “XRCE = eXtremely Resource Constrained Environments”：客户端只承担订阅/发布请求，DDS 实体由 Agent 代理 |
| **Agent** | 守护进程，把 XRCE 客户端的请求转化为真正的 DDS Pub/Sub |

---

## 三、构建系统

micro-ROS 提供 **micro_ros_setup** 元包：

```bash
# 主机侧（构建 firmware）
mkdir microros_ws && cd microros_ws
git clone -b humble https://github.com/micro-ROS/micro_ros_setup src/micro_ros_setup
rosdep install --from-paths src --ignore-src -y
colcon build
source install/local_setup.bash

# 创建 firmware workspace（如 STM32CubeMX + FreeRTOS）
ros2 run micro_ros_setup create_firmware_ws.sh freertos crazyflie21
ros2 run micro_ros_setup configure_firmware.sh
ros2 run micro_ros_setup build_firmware.sh
ros2 run micro_ros_setup flash_firmware.sh

# Agent 侧
ros2 run micro_ros_setup create_agent_ws.sh
ros2 run micro_ros_setup build_agent.sh
ros2 run micro_ros_agent micro_ros_agent serial --dev /dev/ttyACM0 -b 115200
# 或 UDP：
ros2 run micro_ros_agent micro_ros_agent udp4 --port 8888
```

也可作为 **Arduino 库** / **PlatformIO 包** / **ESP-IDF component** 集成。

---

## 四、最小示例（C / FreeRTOS）

```c
#include <rcl/rcl.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>
#include <std_msgs/msg/int32.h>

rcl_publisher_t pub;
std_msgs__msg__Int32 msg;
rclc_support_t support;
rcl_node_t node;
rclc_executor_t executor;
rcl_timer_t timer;

void timer_cb(rcl_timer_t* t, int64_t last_call_time) {
    (void)t; (void)last_call_time;
    rcl_publish(&pub, &msg, NULL);
    msg.data++;
}

void appMain(void* arg) {
    rcl_allocator_t alloc = rcl_get_default_allocator();
    rclc_support_init(&support, 0, NULL, &alloc);
    rclc_node_init_default(&node, "micro_node", "", &support);

    rclc_publisher_init_default(
        &pub, &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int32),
        "micro_topic");

    rclc_timer_init_default(&timer, &support, RCL_MS_TO_NS(100), timer_cb);

    rclc_executor_init(&executor, &support.context, 1, &alloc);
    rclc_executor_add_timer(&executor, &timer);

    msg.data = 0;
    while (1) {
        rclc_executor_spin_some(&executor, RCL_MS_TO_NS(100));
    }
}
```

特点：
- 无 `new`/`malloc`（资源在初始化时一次性分配）；
- 显式声明执行器容量（`rclc_executor_init(..., max_handles, ...)`）；
- 可与 RTOS 任务、ISR 协作。

---

## 五、内存占用（典型）

| 资源 | 占用 |
|------|------|
| Flash | 100–200 KB（含 1 个 Pub + 1 个 Sub + Agent 协议栈） |
| RAM | 25–50 KB（含 transport buffer） |

可裁剪项：禁用 Service/Action、固定字符串长度、固定数组上限（IDL `string<=N` / `seq<=N`）。

---

## 六、Transport（传输层）

| Transport | 适用 |
|-----------|------|
| **Serial / UART** | STM32 / Arduino，最简单稳定 |
| **UDP4** | ESP32 WiFi / 以太网 |
| **TCP4** | 需要可靠 + 不在意延迟 |
| **CAN-FD**（社区） | 车载 ECU |
| **自定义** | 用户实现 `rmw_uros_set_custom_transport()` |

---

## 七、Agent 与多客户端

一个 Agent 可服务多个 micro-ROS 客户端，每个客户端在 DDS 网络中对应一个独立 Participant。多 Agent 也可级联（边缘网关汇聚多个 MCU 数据后再上传到主域）。

```bash
# 同时支持 serial + udp
ros2 run micro_ros_agent micro_ros_agent multiserial --devs /dev/ttyACM0 /dev/ttyACM1 -b 115200 &
ros2 run micro_ros_agent micro_ros_agent udp4 --port 8888 &
```

---

## 八、与传统 RTOS 集成

| RTOS | 状态 |
|------|------|
| FreeRTOS | 一等公民 |
| Zephyr | 一等公民（zephyr meta-module） |
| NuttX | 一等公民 |
| ThreadX / RT-Thread | 社区 |
| Bare-metal | 支持（需要自实现 OS 抽象层） |

---

## 九、调试

```bash
# 查看 client 是否连上 Agent
ros2 run micro_ros_agent micro_ros_agent serial --dev /dev/ttyACM0 -b 115200 -v6

# 主机侧
ros2 topic list                      # 应能看到 micro 节点的话题
ros2 topic echo /micro_topic
```

常见问题：
- Agent 看不到 client → 串口波特率/线序错；
- Topic 列表缺失 → MCU 端 `entity_creation` 失败（内存不足？看 `rclc_*` 返回值）；
- Pub 频率不达预期 → executor `spin_some` 调用频率不足。

---

## 十、面试速记

- micro-ROS = **rclc + rmw_microxrcedds + Micro XRCE-DDS Agent**
- 适配 **MCU / RTOS**，最小 ~30KB RAM
- Pub/Sub 实体由 **Agent 代理** 加入主 DDS 网络
- Transport：UART / UDP / TCP / 自定义
- 无动态内存（默认）；执行器容量必须预声明
- 一句话价值：**让 ECU 也能直接成为 ROS2 节点**，统一上层栈
