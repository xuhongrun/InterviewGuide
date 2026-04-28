# ROS2 DDS 厂商调优与跨域部署

> 在 [ROS2 DDS与QoS](ROS2%20DDS与QoS.md) 之上深入：四大 RMW 厂商配置、Discovery Server、Zenoh router、WAN/跨网段部署。

---

## 一、RMW 厂商对比

| RMW | 默认距 | 优势 | 劣势 |
|-----|--------|------|------|
| `rmw_fastrtps_cpp` | Humble 默认 | 配置灵活、社区最广 | 默认资源 footprint 偏高 |
| `rmw_cyclonedds_cpp` | Galactic 曾默认 | 性能好、内存小 | 配置项较少 |
| `rmw_connextdds` | 商业（RTI） | 工业稳定、Tooling 强 | 收费 |
| `rmw_zenoh_cpp` | Iron+ 实验 | WAN/路由器原生 | 较新 |

切换：
```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

---

## 二、Fast DDS 调优（XML profile）

```bash
export FASTRTPS_DEFAULT_PROFILES_FILE=$PWD/fastdds_profile.xml
```

`fastdds_profile.xml`：

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<profiles xmlns="http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles">
  <participant profile_name="default_participant" is_default_profile="true">
    <rtps>
      <name>my_robot</name>
      <builtin>
        <discovery_config>
          <discoveryProtocol>SIMPLE</discoveryProtocol>
          <leaseDuration><sec>10</sec></leaseDuration>
        </discovery_config>
        <metatrafficUnicastLocatorList>
          <locator>
            <udpv4>
              <address>192.168.1.10</address>
              <port>7400</port>
            </udpv4>
          </locator>
        </metatrafficUnicastLocatorList>
      </builtin>
    </rtps>
  </participant>

  <data_writer profile_name="image_pub">
    <qos>
      <publishMode><kind>ASYNCHRONOUS</kind></publishMode>
    </qos>
    <historyMemoryPolicy>PREALLOCATED_WITH_REALLOC</historyMemoryPolicy>
  </data_writer>
</profiles>
```

要点：
- 关闭 multicast：`<use_builtin_transports>false</use_builtin_transports>` + 显式 unicast；
- `ASYNCHRONOUS` 发送避免大消息阻塞应用线程；
- `PREALLOCATED_WITH_REALLOC` 预分配减少抖动。

---

## 三、Fast DDS Discovery Server（推荐生产用）

集中式发现，避免广域 multicast 风暴：

```bash
# 启动 Discovery Server (id=0)
fastdds discovery -i 0 -l 192.168.1.100 -p 11811

# 客户端
export ROS_DISCOVERY_SERVER=192.168.1.100:11811
ros2 daemon stop && ros2 daemon start
ros2 run demo_nodes_cpp talker
```

或在 XML 中：
```xml
<discoveryProtocol>SUPER_CLIENT</discoveryProtocol>
<discoveryServersList>
  <RemoteServer prefix="44.53.00.5f.45.50.52.4f.53.49.4d.41">
    <metatrafficUnicastLocatorList>
      <locator><udpv4>
        <address>192.168.1.100</address><port>11811</port>
      </udpv4></locator>
    </metatrafficUnicastLocatorList>
  </RemoteServer>
</discoveryServersList>
```

---

## 四、Cyclone DDS + iceoryx（零拷贝）

`cyclonedds.xml`：

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<CycloneDDS xmlns="https://cdds.io/config">
  <Domain id="any">
    <General>
      <NetworkInterfaceAddress>eth0</NetworkInterfaceAddress>
      <AllowMulticast>spdp</AllowMulticast>
    </General>
    <SharedMemory>
      <Enable>true</Enable>
      <LogLevel>info</LogLevel>
    </SharedMemory>
    <Internal>
      <SocketReceiveBufferSize min="10MB"/>
    </Internal>
  </Domain>
</CycloneDDS>
```

```bash
export CYCLONEDDS_URI=file://$PWD/cyclonedds.xml
# 启 iceoryx daemon
iox-roudi
# 启 ROS2 节点
ros2 run my_pkg my_node
```

零拷贝条件：
- 同主机；
- 消息为 fixed-size POD（无变长 string/array）；
- writer/reader 都启用 SHM。

---

## 五、Connext DDS（RTI）特性

- **QoS Library**：可在 USER_QOS_PROFILES.xml 集中定义并复用；
- **Routing Service**：跨域桥接 / 协议网关；
- **Persistence Service**：消息持久化；
- **Monitor / Admin Console**：图形化诊断；
- **Security plugin**：与 ROS2 Security 适配。

```xml
<dds><qos_library name="ROS_QoS">
  <qos_profile name="ImageQos" base_name="BuiltinQosLib::Generic.StrictReliable">
    <datawriter_qos>
      <publish_mode><kind>ASYNCHRONOUS_PUBLISH_MODE_QOS</kind></publish_mode>
    </datawriter_qos>
  </qos_profile>
</qos_library></dds>
```

---

## 六、Zenoh-RMW 与 Zenoh router

Zenoh 是路由化协议，原生支持 WAN：

```bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
ros2 run rmw_zenoh_cpp rmw_zenohd          # 路由 daemon
ros2 run demo_nodes_cpp talker
```

跨主机：
```bash
# 主机 A：
ros2 run rmw_zenoh_cpp rmw_zenohd --connect tcp/host_b:7447
# 主机 B：
ros2 run rmw_zenoh_cpp rmw_zenohd
```

特点：
- 支持任意拓扑（mesh/peer/router）；
- 跨 NAT / WAN 通过 router；
- 没有 multicast 也能 discovery。

---

## 七、WAN / 跨网段部署

| 方案 | 说明 |
|------|------|
| **Discovery Server** | Fast DDS 推荐，单点 unicast |
| **Zenoh router** | 跨 NAT/WAN 最佳 |
| **VPN / WireGuard** | 让远端机器进同一 L3，DDS 视为局域网 |
| **DDS Routing Service** | RTI 商业方案，跨域桥接 |
| **MQTT/HTTP 桥接** | 低速控制 / 远程监控 |

要点：
- 多播 (`239.255.0.1`) 通常不能跨路由器，需替换为 unicast/server；
- 关闭 IPv6 / 限定 `NetworkInterfaceAddress`；
- 增大 socket buffer：`sysctl -w net.core.rmem_max=2097152`。

---

## 八、ROS_DOMAIN_ID 与隔离

| 变量 | 作用 |
|------|------|
| `ROS_DOMAIN_ID` (0~166) | 域 ID，DDS 端口 = 7400 + 250 × domain |
| `ROS_LOCALHOST_ONLY=1` | 只与本机节点通信 |
| `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST/SUBNET/SYSTEM_DEFAULT/OFF` | Iron+ 自动发现范围 |

跨车队建议每车队独占一个 DOMAIN_ID，再叠加 namespace。

---

## 九、调优 checklist

| 维度 | 建议 |
|------|------|
| Discovery 风暴 | Discovery Server / 限定网卡 / 减少 participant |
| 大消息（图像/点云） | ASYNCHRONOUS + PREALLOCATED_WITH_REALLOC + SHM/iceoryx |
| 高频小消息 | KEEP_LAST(1) + BEST_EFFORT |
| 跨主机延迟高 | tcpdump 观察、增 socket buffer、禁用 nagle |
| 内存涨 | 检查 history depth；用 VOLATILE 而非 TRANSIENT_LOCAL |

---

## 十、面试速记

- 切 RMW：`RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`
- 大集群禁多播：用 **Fast DDS Discovery Server**（`ROS_DISCOVERY_SERVER`）
- 同机零拷贝：**Cyclone + iceoryx**（fixed-size POD）
- 跨 WAN：**Zenoh router** 或 RTI Routing Service / VPN
- DDS 端口公式 `7400 + 250 * DOMAIN_ID`
- Iron+ 用 `ROS_AUTOMATIC_DISCOVERY_RANGE` 限定可见范围
- 内核调优 `net.core.rmem_max` / `wmem_max` 增大缓冲
