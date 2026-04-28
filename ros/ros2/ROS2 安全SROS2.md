# ROS2 安全：SROS2 与 DDS-Security

> ROS2 通过 **SROS2** 工具与 **DDS-Security 1.1** 标准实现端到端安全：身份认证、访问控制、数据加密。

---

## 一、为什么需要安全

ROS1 完全没有安全机制：任何接入网络的节点可以读写所有话题、调用所有服务、修改任何参数。机器人/汽车出厂部署时这是**致命缺陷**。SROS2 在 DDS 层引入 5 大安全插件，在不修改业务代码的前提下加固通信。

---

## 二、DDS-Security 五大插件

| 插件 | 作用 | 默认实现 |
|------|------|----------|
| **Authentication** | 节点身份认证（X.509 证书 + DH/ECDH 握手） | builtin (PKI) |
| **Access Control** | 主题级权限（哪个节点能 Pub/Sub 哪个 Topic） | builtin (Permissions XML) |
| **Cryptography** | 序列化加密（AES-GCM/AES-GMAC） | builtin (AES) |
| **Logging** | 安全审计日志 | 可选 |
| **Data Tagging** | 数据敏感度标签 | 可选 |

握手流程：

```
Participant A                          Participant B
   │   1) Discovery (SPDP)                 │
   │◄─────────────────────────────────────►│
   │   2) HandshakeRequest (cert_a)        │
   ├──────────────────────────────────────►│
   │   3) HandshakeReply  (cert_b, dh_b)   │
   │◄──────────────────────────────────────┤
   │   4) HandshakeFinal  (dh_a, sig_a)    │
   ├──────────────────────────────────────►│
   │   ◄== 共享会话密钥协商完成 ==►          │
   │   5) Permissions 校验（Access Control）│
   │◄═════════ 加密数据通道（AES-GCM）═════►│
```

---

## 三、SROS2 keystore（密钥库）

### 3.1 创建

```bash
ros2 security create_keystore demo_keystore
```

生成结构：
```
demo_keystore/
├── public/                # CA 证书 + 公钥
│   ├── ca.cert.pem
│   ├── permissions_ca.cert.pem
│   └── identity_ca.cert.pem
└── private/               # CA 私钥（生产环境必须保护！）
    ├── ca.key.pem
    ├── permissions_ca.key.pem
    └── identity_ca.key.pem
```

### 3.2 为节点创建 enclave

每个节点（或一组节点）使用一个 **enclave**：包含身份证书 + 私钥 + 权限 XML + 治理 XML。

```bash
ros2 security create_enclave demo_keystore /talker
ros2 security create_enclave demo_keystore /listener
ros2 security create_enclave demo_keystore /robot1/perception
```

生成 `demo_keystore/enclaves/talker/`：
```
├── cert.pem            # 节点证书（由 identity_ca 签）
├── key.pem             # 节点私钥
├── identity_ca.cert.pem
├── permissions_ca.cert.pem
├── governance.p7s      # 域级安全策略（签名）
└── permissions.p7s     # 节点权限策略（签名）
```

> 一个 enclave 可被多个节点共享（用 `--ros-args --enclave /shared`）。

---

## 四、Governance（域级策略）

`governance.xml`：定义整个 Domain 的默认行为。

```xml
<?xml version="1.0" encoding="UTF-8"?>
<dds xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
 <domain_access_rules>
  <domain_rule>
   <domains>
    <id>0</id>
   </domains>
   <allow_unauthenticated_participants>false</allow_unauthenticated_participants>
   <enable_join_access_control>true</enable_join_access_control>
   <discovery_protection_kind>ENCRYPT</discovery_protection_kind>
   <liveliness_protection_kind>ENCRYPT</liveliness_protection_kind>
   <rtps_protection_kind>ENCRYPT</rtps_protection_kind>
   <topic_access_rules>
    <topic_rule>
     <topic_expression>*</topic_expression>
     <enable_discovery_protection>true</enable_discovery_protection>
     <enable_liveliness_protection>true</enable_liveliness_protection>
     <enable_read_access_control>true</enable_read_access_control>
     <enable_write_access_control>true</enable_write_access_control>
     <metadata_protection_kind>ENCRYPT</metadata_protection_kind>
     <data_protection_kind>ENCRYPT</data_protection_kind>
    </topic_rule>
   </topic_access_rules>
  </domain_rule>
 </domain_access_rules>
</dds>
```

| 字段 | 选项 | 含义 |
|------|------|------|
| `*_protection_kind` | NONE / SIGN / ENCRYPT | 不保护 / 仅签名 / 签名+加密 |
| `allow_unauthenticated_participants` | true/false | 是否允许无证书节点接入 |
| `enable_join_access_control` | true/false | 是否校验 Participant 加入权限 |

---

## 五、Permissions（节点级权限）

`permissions.xml`：声明该 enclave 能 Pub/Sub 哪些 Topic、调用哪些 Service。

```xml
<?xml version="1.0" encoding="UTF-8"?>
<dds>
 <permissions>
  <grant name="/talker_grant">
   <subject_name>CN=/talker</subject_name>
   <validity>
    <not_before>2025-01-01T00:00:00</not_before>
    <not_after>2030-01-01T00:00:00</not_after>
   </validity>
   <allow_rule>
    <domains><id>0</id></domains>
    <publish>
     <topics>
      <topic>rt/chatter</topic>
      <topic>rt/parameter_events</topic>
     </topics>
    </publish>
    <subscribe>
     <topics>
      <topic>rt/parameter_events</topic>
     </topics>
    </subscribe>
   </allow_rule>
   <default>DENY</default>
  </grant>
 </permissions>
</dds>
```

> 注意 ROS2 Topic 在 DDS 层加前缀：`rt/` (topic), `rq/...Request`, `rr/...Reply`, `rs/...` (service status)。

签名生成 `.p7s`：
```bash
openssl smime -sign -in permissions.xml -text -out permissions.p7s \
    -signer permissions_ca.cert.pem -inkey permissions_ca.key.pem
```

---

## 六、运行带安全的节点

```bash
# 三件环境变量
export ROS_SECURITY_ENABLE=true
export ROS_SECURITY_STRATEGY=Enforce          # Permissive 仅警告
export ROS_SECURITY_KEYSTORE=$PWD/demo_keystore

# 必须指定 enclave
ros2 run demo_nodes_cpp talker --ros-args --enclave /talker
ros2 run demo_nodes_cpp listener --ros-args --enclave /listener
```

| `ROS_SECURITY_STRATEGY` | 行为 |
|-------------------------|------|
| `Enforce` | 强制：缺证书直接拒绝 |
| `Permissive` | 警告：缺证书仍然通信（用于灰度） |

测试：尝试用未注册节点连接，应被 Discovery 阶段拒绝。

---

## 七、launch 集成

```python
from launch_ros.actions import Node

Node(
    package="demo_nodes_cpp",
    executable="talker",
    name="talker",
    arguments=["--ros-args", "--enclave", "/talker"],
)
```

环境变量可在 launch 中通过 `SetEnvironmentVariable` 注入。

---

## 八、生产部署最佳实践

1. **CA 私钥离线保管**：keystore 中的 `private/` 不要随节点分发，仅用于签发证书。
2. **per-node enclave**：避免“万能账号”，每个节点独立证书 + 最小权限。
3. **证书轮换策略**：定期重签节点证书；预留 grace period。
4. **Permissive → Enforce 灰度**：先在测试集群跑 Permissive 收集 deny 日志，调整 permissions 后切 Enforce。
5. **结合网络层**：DDS 层加密 + 网卡 VLAN/MACsec 提供纵深防御。
6. **审计**：开启安全日志插件，对接 SIEM。
7. **防 Discovery 风暴**：与 Discovery Server 配合，避免恶意节点广播。

---

## 九、micro-ROS 与安全

micro-XRCE-DDS 通过 **Agent** 中转到 DDS 网络。Agent 与 micro-ROS 客户端之间走 DTLS / TLS（取决于传输），DDS 网络侧由 Agent 代表 client 加入安全 Domain，并按 enclave 检查权限。

---

## 十、面试速记

- SROS2 = **DDS-Security 1.1** + 工具（`ros2 security ...`）
- 五大插件：**Authentication / Access Control / Cryptography / Logging / Data Tagging**
- 三件套环境变量：`ROS_SECURITY_ENABLE` + `ROS_SECURITY_STRATEGY` + `ROS_SECURITY_KEYSTORE`
- 每节点用独立 **enclave**，启动加 `--enclave /xxx`
- 域策略 **Governance**，节点策略 **Permissions**，均需 CA 签名（`.p7s`）
- 灰度：`Permissive` → 收集 deny → 调整 → `Enforce`
