# ROS2 安全（SROS2）实操与 PKI

> 在 [ROS2 安全SROS2](ROS2%20安全SROS2.md) 概述基础上，实操 CA、签发流程、permissions 编写、密钥轮换、企业 PKI 集成。

---

## 一、SROS2 安全模型

```
DDS Security 插件
├── Authentication       ← X.509 证书 + RSA/ECDSA
├── Access Control       ← XML 权限文件 (governance / permissions)
├── Cryptographic        ← AES-GCM 加密签名
└── Logging              ← 安全事件审计
```

环境变量：
```bash
export ROS_SECURITY_ENABLE=true
export ROS_SECURITY_STRATEGY=Enforce        # Permissive / Enforce
export ROS_SECURITY_KEYSTORE=$HOME/sros2_keystore
```

---

## 二、Keystore 与 CA

```bash
# 创建 keystore
ros2 security create_keystore $ROS_SECURITY_KEYSTORE
# 自动生成 CA 私钥 + 证书 (ca.cert.pem / ca.key.pem)
```

为节点签发：
```bash
ros2 security create_enclave $ROS_SECURITY_KEYSTORE /talker
ros2 security create_enclave $ROS_SECURITY_KEYSTORE /listener
```

每个 enclave 包含：
- `cert.pem` — 节点身份证书
- `key.pem` — 节点私钥
- `governance.p7s` — 全局策略
- `permissions.p7s` — 该节点权限
- `identity_ca.cert.pem`, `permissions_ca.cert.pem`

启动节点：
```bash
ros2 run demo_nodes_cpp talker --ros-args -e /talker
```

`-e` = `--enclave`。

---

## 三、Governance 文件

`governance.xml`（全局，决定整个域的安全策略）：

```xml
<dds><domain_access_rules>
  <domain_rule>
    <domains><id>0</id></domains>
    <allow_unauthenticated_participants>false</allow_unauthenticated_participants>
    <enable_join_access_control>true</enable_join_access_control>
    <discovery_protection_kind>ENCRYPT</discovery_protection_kind>
    <liveliness_protection_kind>ENCRYPT</liveliness_protection_kind>
    <rtps_protection_kind>SIGN</rtps_protection_kind>
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
</domain_access_rules></dds>
```

签名：
```bash
openssl smime -sign -in governance.xml -text -out governance.p7s \
    -signer permissions_ca.cert.pem -inkey permissions_ca.key.pem
```

---

## 四、Permissions 文件

`permissions.xml` 为每个 enclave 定制：

```xml
<dds><permissions>
  <grant name="/talker">
    <subject_name>CN=/talker</subject_name>
    <validity>
      <not_before>2024-01-01T00:00:00</not_before>
      <not_after>2026-01-01T00:00:00</not_after>
    </validity>
    <allow_rule>
      <domains><id>0</id></domains>
      <publish>
        <topics>
          <topic>rt/chatter</topic>          <!-- 注意 ROS2 topic 前加 rt/ -->
        </topics>
      </publish>
      <subscribe>
        <topics>
          <topic>rq/talker/parameter_eventsRequest</topic>
        </topics>
      </subscribe>
    </allow_rule>
    <default>DENY</default>
  </grant>
</permissions></dds>
```

ROS2 topic 在 DDS 层有前缀：
- `rt/<topic>` — Topic
- `rq/<service>Request` / `rr/<service>Reply` — Service
- `ra/<action>/...` — Action

签名：
```bash
openssl smime -sign -in permissions.xml -text -out permissions.p7s \
    -signer permissions_ca.cert.pem -inkey permissions_ca.key.pem
```

---

## 五、密钥轮换

策略：
1. 短有效期（年 / 季）；
2. 提前签发新证书 → 部署 → 双信任期；
3. 撤销旧证书：CRL（证书撤销列表）或 OCSP；
4. CA 私钥离线保管（HSM / 离线机）。

CRL 配置（DDS 配置中）：
```xml
<authentication>
  <ca_crl>file://crl.pem</ca_crl>
</authentication>
```

---

## 六、企业 PKI 集成

不要用 `ros2 security create_keystore` 生成的自签 CA 上线。生产推荐：

| 场景 | 方案 |
|------|------|
| 已有企业 PKI | 用现有 Root CA 签发中间 CA，再签 SROS2 enclaves |
| 私有 CA | 使用 step-ca / HashiCorp Vault PKI / EJBCA |
| 云端 | AWS Private CA / GCP CA Service |

集成步骤：
1. 用企业 CA 签 `permissions_ca.cert.pem` / `identity_ca.cert.pem`；
2. 把这两个 CA 拷到所有节点的 keystore；
3. 节点证书走脚本批量生成 / 由 PKI 颁发；
4. 配置 CRL/OCSP，节点定期刷新。

---

## 七、调试与权限错误

| 现象 | 原因 |
|------|------|
| 节点起不来：`Cannot find permissions file` | enclave 路径写错 / `-e` 没加 |
| 通信无法建立 | governance 不一致 / 时钟偏差大（证书 not_before / not_after） |
| Topic publish 被拒 | permissions 没列；用前缀 `rt/` |
| Service 通不过 | 未列 `rq/...Request` 与 `rr/...Reply` 双向 |
| Discovery 漏 | `discovery_protection_kind=ENCRYPT` 全员需开 |

调试：
```bash
export RCUTILS_CONSOLE_OUTPUT_FORMAT="[{severity}] [{name}]: {message}"
export RMW_FASTRTPS_USE_QOS_FROM_XML=1
# 或使用 RTI Connext，开 Security Plugin verbose
```

---

## 八、性能开销

加密带来的额外延迟（典型）：
- 签名（SIGN）：+5~15%；
- 加密（ENCRYPT）：+15~35%；
- 大消息影响更大；
- 推荐：**控制类用 ENCRYPT，传感器大流量用 SIGN 或部分话题不保护**（对应 governance topic_rule 细化）。

---

## 九、面试速记

- SROS2 = DDS Security 4 大插件：**Authentication / AccessControl / Crypto / Logging**
- 关键命令：`ros2 security create_keystore / create_enclave`，节点 `--enclave /name`
- 三层 XML：**identity_ca / governance / permissions**，用 `openssl smime -sign` 签名
- ROS2 topic 在 DDS 加前缀：**`rt/`、`rq/`/`rr/`、`ra/`**
- 生产用企业 PKI（step-ca / Vault / AWS PCA），CA 私钥进 HSM
- 性能：ENCRYPT 比 SIGN 贵；大流量话题精细配置
- 时钟同步是必备前置（chrony / PTP），否则证书有效期判错
