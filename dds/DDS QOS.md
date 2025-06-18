### 一、DDS QoS概述
DDS的QoS策略用于控制数据传输的可靠性、实时性、资源分配等行为，确保分布式系统在复杂场景下的性能。其核心目标是实现 **“在正确的时间、正确的位置传递正确的数据”** 。QoS策略分为四类标准（核心、扩展、网关、API），配置实体包括：
- **DomainParticipant**（域参与者）
- **Publisher/Subscriber**（发布者/订阅者）
- **DataWriter/DataReader**（数据写入器/读取器）
- **Topic**（主题）

---
### 二、22个QoS策略详解

1. **USER_DATA (用户数据)**
    * **作用域**：`DomainParticipant`, `Topic`, `DataWriter`, `DataReader`, `Publisher`, `Subscriber`
    * **目的**：允许应用程序将任意二进制数据（`octet`序列）附加到实体。常用于存储应用特定的元数据（如位置信息、配置标识符、安全凭证）。
    * **协商**：不参与`DataWriter`/`DataReader`匹配协商。仅作为附加信息传递。
    * **类型**：`UserDataQosPolicy` (`value: sequence<octet>`)
    * **默认值**：空序列。

2. **TOPIC_DATA (主题数据)**
    * **作用域**：`Topic`
    * **目的**：允许应用程序将任意二进制数据附加到`Topic`实体。该数据会传播给所有基于此`Topic`创建的`DataWriter`和`DataReader`。常用于存储主题级别的元数据。
    * **协商**：不参与`DataWriter`/`DataReader`匹配协商。信息随`Topic`描述传播。
    * **类型**：`TopicDataQosPolicy` (`value: sequence<octet>`)
    * **默认值**：空序列。

3. **GROUP_DATA (组数据)**
    * **作用域**：`Publisher`, `Subscriber`
    * **目的**：允许应用程序将任意二进制数据附加到`Publisher`或`Subscriber`。该数据会传播给其下创建的所有`DataWriter`或`DataReader`。常用于对一组`DataWriter`/`DataReader`进行逻辑分组标记。
    * **协商**：不参与`DataWriter`/`DataReader`匹配协商。
    * **类型**：`GroupDataQosPolicy` (`value: sequence<octet>`)
    * **默认值**：空序列。

4. **ENTITY_FACTORY (实体工厂)**
    * **作用域**：`DomainParticipantFactory` (创建`DomainParticipant`时), `DomainParticipant` (创建`Publisher`/`Subscriber`时), `Publisher` (创建`DataWriter`时), `Subscriber` (创建`DataReader`时)
    * **目的**：控制当父实体被删除时，其创建的**子实体是否自动删除**。
    * **关键参数**：`autoenable_created_entities` (布尔值)。
        * `TRUE`: (默认) 父实体删除时，自动删除其创建的所有子实体。
        * `FALSE`: 父实体删除时，其创建的子实体**不**被自动删除（应用程序需手动管理其生命周期）。
    * **类型**：`EntityFactoryQosPolicy` (`autoenable_created_entities: boolean`)
    * **默认值**：`TRUE`

5. **DURABILITY (持久性)**
    * **作用域**：`Topic`, `DataWriter`, `DataReader`
    * **目的**：控制`DataWriter`发布的数据样本在发布后对**晚加入的`DataReader`**的可用性。
    * **策略种类 (kind)：**
        * `VOLATILE_DURABILITY_QOS`: (默认) 样本不持久化。晚加入的`DataReader`无法获取`DataWriter`之前发布的历史数据。
        * `TRANSIENT_LOCAL_DURABILITY_QOS`: 数据在`DataWriter`或`DataReader`**本地内存**中缓存（根据`HISTORY`策略）。晚加入的`DataReader`能获取匹配的`DataWriter`缓存的历史数据（只要`DataWriter`在线）。`DataWriter`离线后缓存消失。
        * `TRANSIENT_DURABILITY_QOS`: 数据持久化到**外部持久化服务**（如数据库或文件系统）。晚加入的`DataReader`即使原始`DataWriter`已离线，也能从持久化服务获取数据。需要配置`DURABILITY_SERVICE`策略。
        * `PERSISTENT_DURABILITY_QOS`: 数据持久化到可靠的**外部存储**（通常比`TRANSIENT`更可靠，如支持事务的数据库）。行为类似`TRANSIENT`，但暗示更高的持久性保证。
    * **协商**：`DataReader`的`DURABILITY`必须 >= `DataWriter`的`DURABILITY`才能匹配（`VOLATILE` < `TRANSIENT_LOCAL` < `TRANSIENT` < `PERSISTENT`）。
    * **类型**：`DurabilityQosPolicy` (`kind: DurabilityQosPolicyKind`)
    * **默认值**：`VOLATILE_DURABILITY_QOS`

6. **DURABILITY_SERVICE (持久化服务)**
    * **作用域**：`Topic`, `DataWriter` (主要用于`TRANSIENT`或`PERSISTENT` `DURABILITY`)
    * **目的**：当`DURABILITY.kind`为`TRANSIENT`或`PERSISTENT`时，配置**持久化服务**的行为。定义历史数据如何存储、保留多久以及如何清理。
    * **关键参数：**
        * `service_cleanup_delay`: 持久化服务在删除过期样本前等待的时间。
        * `history_kind`: (`KEEP_LAST_HISTORY_QOS` 或 `KEEP_ALL_HISTORY_QOS`) 与`HISTORY`策略相同，但应用于持久化存储。
        * `history_depth`: 与`HISTORY`策略相同，但应用于持久化存储（当`history_kind = KEEP_LAST`时有效）。
        * `max_samples`, `max_instances`, `max_samples_per_instance`: 限制持久化存储的资源使用（类似于`RESOURCE_LIMITS`）。
    * **依赖**：仅在`DURABILITY.kind`设置为`TRANSIENT_DURABILITY_QOS`或`PERSISTENT_DURABILITY_QOS`时生效。
    * **类型**：`DurabilityServiceQosPolicy` (包含上述参数)
    * **默认值**：依赖于具体实现，通常有合理的默认值（如`history_kind = KEEP_LAST`, `history_depth = 1`）。

7. **PRESENTATION (表示)**
    * **作用域**：`Publisher`, `Subscriber`
    * **目的**：控制**实例级**数据的呈现顺序和访问范围。影响同一`Publisher`/`Subscriber`下多个`DataWriter`/`DataReader`的数据传递逻辑。
    * **关键参数：**
        * `access_scope`:
            * `INSTANCE_PRESENTATION_QOS`: (默认) 无额外协调。每个`DataWriter`/`DataReader`独立。
            * `TOPIC_PRESENTATION_QOS`: 协调发生在同一`Publisher`/`Subscriber`内**相同`Topic`**的`DataWriter`/`DataReader`之间。保证该Topic下实例的修改按`coherent_access`设置传递。
            * `GROUP_PRESENTATION_QOS`: 协调发生在同一`Publisher`/`Subscriber`内**所有`DataWriter`/`DataReader`**之间。保证组内所有实例的修改按`coherent_access`设置传递。
        * `coherent_access`: (布尔值) 当`access_scope`不是`INSTANCE`时，是否支持**一致性访问**（即使用`begin_coherent_changes()`和`end_coherent_changes()`来标记一组原子更新）。
        * `ordered_access`: (布尔值) 当`access_scope`不是`INSTANCE`时，是否保证对**同一实例**的修改按`DataWriter`写入的顺序传递给`Subscriber`。
    * **协商**：`Subscriber`的`PRESENTATION.access_scope`必须 >= `Publisher`的`access_scope` (`INSTANCE` < `TOPIC` < `GROUP`) 才能匹配。`coherent_access`和`ordered_access`也必须兼容（`Subscriber`的要求不能比`Publisher`提供的更严格）。
    * **类型**：`PresentationQosPolicy` (包含上述参数)
    * **默认值**：`access_scope = INSTANCE_PRESENTATION_QOS`, `coherent_access = FALSE`, `ordered_access = FALSE`

8. **DEADLINE (截止期限)**
    * **作用域**：`Topic`, `DataWriter`, `DataReader`
    * **目的**：定义`DataWriter`预期发布**每个实例**新样本的**最大间隔时间**。`DataReader`期望在此间隔内收到更新。
    * **关键参数**：`period: Duration_t` (例如 `{ sec: 1, nanosec: 0 }` 表示1秒)。
    * **行为：**
        * `DataWriter`：承诺尝试以快于此`period`的速率更新每个实例。
        * `DataReader`：期望在`period`时间内收到每个实例的更新。
        * **监控**：如果`DataWriter`未能按时更新实例，或`DataReader`未能按时收到预期实例的更新，会触发相应的`Listener`回调 (`on_offered_deadline_missed` / `on_requested_deadline_missed`) 或设置`StatusCondition`。
    * **协商**：`DataReader`的`DEADLINE.period`必须 <= `DataWriter`的`DEADLINE.period`。如果`DataReader`要求更短的周期（更频繁的更新）而`DataWriter`无法满足，则**不匹配**。
    * **类型**：`DeadlineQosPolicy` (`period: Duration_t`)
    * **默认值**：`period = { sec: DURATION_INFINITE_SEC, nanosec: DURATION_INFINITE_NSEC }` (无限期)

9. **LATENCY_BUDGET (延迟预算)**
    * **作用域**：`Topic`, `DataWriter`, `DataReader`
    * **目的**：指示应用程序对**端到端传输延迟**的期望或预算。这是一个**提示**，而非严格保证。中间件可以利用此提示优化内部传输调度（如网络优先级）。
    * **关键参数**：`duration: Duration_t` (预期的最大延迟)。
    * **注意**：不强制执行，也不直接导致不匹配。主要用于服务质量管理和资源优化。
    * **类型**：`LatencyBudgetQosPolicy` (`duration: Duration_t`)
    * **默认值**：`duration = { sec: 0, nanosec: 0 }` (零延迟，即尽快)

10. **OWNERSHIP (所有权)**
    * **作用域**：`Topic`, `DataWriter`, `DataReader`
    * **目的**：控制当**多个`DataWriter`**写入**同一个数据实例**时，`DataReader`应该接收哪个`DataWriter`的数据。
    * **策略种类 (kind)：**
        * `SHARED_OWNERSHIP_QOS`: (默认) 多个`DataWriter`可以写入同一实例。`DataReader`会收到**所有**匹配`DataWriter`对该实例的更新（可能导致实例状态冲突）。
        * `EXCLUSIVE_OWNERSHIP_QOS`: 同一时刻，**只有一个`DataWriter`**（即`OWNERSHIP_STRENGTH`最高的那个）被允许“拥有”并更新一个实例。只有拥有者的更新会被传递给`DataReader`。拥有者离线或降低强度时，强度次高的`DataWriter`自动成为新拥有者。
    * **依赖**：当`kind = EXCLUSIVE_OWNERSHIP_QOS`时，必须同时使用`OWNERSHIP_STRENGTH`策略。
    * **协商**：`DataReader`和`DataWriter`的`OWNERSHIP.kind`必须**完全一致**才能匹配。
    * **类型**：`OwnershipQosPolicy` (`kind: OwnershipQosPolicyKind`)
    * **默认值**：`SHARED_OWNERSHIP_QOS`

11. **OWNERSHIP_STRENGTH (所有权强度)**
    * **作用域**：`DataWriter` (仅在`OWNERSHIP.kind = EXCLUSIVE_OWNERSHIP_QOS`时有效)
    * **目的**：当使用独占所有权(`EXCLUSIVE_OWNERSHIP_QOS`)时，定义`DataWriter`的“强度”。用于仲裁哪个`DataWriter`拥有写入特定实例的权利。
    * **关键参数**：`value: long`。值越大表示强度越高。
    * **行为**：对于同一个实例，强度最高的在线`DataWriter`获得所有权。强度值在运行时可以修改(`Mutable`)。
    * **协商**：不直接导致不匹配，但`DataReader`必须也使用`EXCLUSIVE_OWNERSHIP_QOS`。
    * **类型**：`OwnershipStrengthQosPolicy` (`value: long`)
    * **默认值**：0

12. **LIVELINESS (活跃性)**
    * **作用域**：`Topic`, `DataWriter`, `DataReader`
    * **目的**：定义`DataWriter`如何宣告其“活跃”（Alive）状态，以及`DataReader`如何检测`DataWriter`是否“不活跃”（Not Alive）。用于检测发布者故障。
    * **关键参数：**
        * `kind`:
            * `AUTOMATIC_LIVELINESS_QOS`: (默认) 中间件代表`DataWriter`自动发送活跃性声明（通常基于心跳）。
            * `MANUAL_BY_PARTICIPANT_LIVELINESS_QOS`: `DataWriter`的活跃性依赖于其所属`DomainParticipant`的活跃性。应用程序需通过`DomainParticipant`的`assert_liveliness()`方法显式声明活跃性。
            * `MANUAL_BY_TOPIC_LIVELINESS_QOS`: `DataWriter`必须通过自身的`assert_liveliness()`方法显式声明活跃性。
        * `lease_duration: Duration_t`: `DataReader`判断`DataWriter`不活跃的最大时间窗口。如果在此时间内未收到`DataWriter`的活跃性声明，则认为其不活跃。
    * **行为**：`DataReader`根据`kind`和`lease_duration`监控`DataWriter`活跃性。检测到不活跃会触发`Listener` (`on_liveliness_changed`, `on_liveliness_lost`) 或设置`StatusCondition`。
    * **协商**：`DataReader`的`LIVELINESS.lease_duration`必须 <= `DataWriter`的`LIVELINESS.lease_duration`。如果`DataReader`要求更短的租约（更严格的监控）而`DataWriter`无法满足，则**不匹配**。`kind`也必须兼容（`DataReader`的要求不能比`DataWriter`提供的更严格，即`DataReader`不能要求`MANUAL`而`DataWriter`只提供`AUTOMATIC`）。
    * **类型**：`LivelinessQosPolicy` (`kind: LivelinessQosPolicyKind`, `lease_duration: Duration_t`)
    * **默认值**：`kind = AUTOMATIC_LIVELINESS_QOS`, `lease_duration = { sec: DURATION_INFINITE_SEC, nanosec: DURATION_INFINITE_NSEC }`

13. **TIME_BASED_FILTER (基于时间的过滤器)**
    * **作用域**：`DataReader`
    * **目的**：控制`DataReader`接收**相同实例**样本的**最小时间间隔**。用于**降低接收端的数据速率**，过滤掉过于频繁的更新。
    * **关键参数**：`minimum_separation: Duration_t` (例如 `{ sec: 0, nanosec: 100000000 }` 表示100ms)。
    * **行为**：对于每个实例，`DataReader`在收到一个样本后，会忽略该实例后续到达的样本，直到`minimum_separation`时间过去。之后收到的第一个样本被传递。**注意**：这是基于**源时间戳(`Source Timestamp`)** 或**接收时间**（取决于实现）的过滤。
    * **协商**：不直接影响匹配。但`DataWriter`应了解`DataReader`可能不会接收所有样本。
    * **类型**：`TimeBasedFilterQosPolicy` (`minimum_separation: Duration_t`)
    * **默认值**：`minimum_separation = { sec: 0, nanosec: 0 }` (不过滤，接收所有样本)

14. **PARTITION (分区)**
    * **作用域**：`Publisher`, `Subscriber`
    * **目的**：对`Publisher`及其`DataWriter`、`Subscriber`及其`DataReader`进行**逻辑分组**。只有位于**至少一个相同分区**的`Publisher`和`Subscriber`，其下的`DataWriter`和`DataReader`才能匹配并通信。提供额外的命名空间隔离。
    * **关键参数**：`name: sequence<string>` (分区名称列表)。
    * **特殊分区：**
        * 空名称列表 (`""`): 表示默认分区（通常所有实体隐式在此分区）。
        * 通配符: 某些实现支持通配符 (如 `*`, `?`) 进行模式匹配。
    * **匹配规则**：`Publisher`的分区列表与`Subscriber`的分区列表**有交集**（至少一个分区名相同）。
    * **类型**：`PartitionQosPolicy` (`name: sequence<string>`)
    * **默认值**：包含一个空字符串 `""` 的列表 (即默认分区)。

15. **RELIABILITY (可靠性)**
    * **作用域**：`Topic`, `DataWriter`, `DataReader`
    * **目的**：控制数据传输的可靠性保证级别。
    * **策略种类 (kind)：**
        * `BEST_EFFORT_RELIABILITY_QOS`: (默认) 尽力而为传输。不保证送达。可能丢失样本。追求最低延迟和开销。
        * `RELIABLE_RELIABILITY_QOS`: 可靠传输。保证样本最终送达（在资源允许和`DataWriter`存活的情况下）。使用确认(`ACKs`)和重传机制。
    * **关键参数 (仅当`kind = RELIABLE`时)：**
        * `max_blocking_time: Duration_t`: 当`DataWriter`发送样本时，如果底层资源（如发送队列）已满，调用`write()`的线程最多阻塞等待的时间。超时后`write()`可能失败。
    * **协商**：`DataReader`的`RELIABILITY.kind`必须 >= `DataWriter`的`kind` (`BEST_EFFORT` < `RELIABLE`)。即`DataReader`要求`RELIABLE`时，`DataWriter`也必须提供`RELIABLE`才能匹配；`DataReader`用`BEST_EFFORT`则可以匹配提供`BEST_EFFORT`或`RELIABLE`的`DataWriter`。
    * **类型**：`ReliabilityQosPolicy` (`kind: ReliabilityQosPolicyKind`, `max_blocking_time: Duration_t`)
    * **默认值**：`kind = BEST_EFFORT_RELIABILITY_QOS`, `max_blocking_time = { sec: 100, nanosec: 0 }` (典型值，具体实现可能不同)

16. **DESTINATION_ORDER (目标顺序)**
    * **作用域**：`Topic`, `DataWriter`, `DataReader`
    * **目的**：控制当**来自不同`DataWriter`** (相同`Topic`和`Instance`) 的样本到达`DataReader`时，如何排序。
    * **策略种类 (kind)：**
        * `BY_RECEPTION_TIMESTAMP_DESTINATIONORDER_QOS`: (默认) 根据样本**到达`DataReader`的时间戳**排序。
        * `BY_SOURCE_TIMESTAMP_DESTINATIONORDER_QOS`: 根据样本**在`DataWriter`端写入时附加的源时间戳(`Source Timestamp`)** 排序。
    * **协商**：`DataReader`的`DESTINATION_ORDER.kind`必须 >= `DataWriter`的`kind` (`BY_RECEPTION_TIMESTAMP` < `BY_SOURCE_TIMESTAMP`)。即`DataReader`要求`BY_SOURCE_TIMESTAMP`时，`DataWriter`也必须提供`BY_SOURCE_TIMESTAMP`才能匹配；`DataReader`用`BY_RECEPTION_TIMESTAMP`则可以匹配提供任何一种的`DataWriter`。
    * **类型**：`DestinationOrderQosPolicy` (`kind: DestinationOrderQosPolicyKind`)
    * **默认值**：`BY_RECEPTION_TIMESTAMP_DESTINATIONORDER_QOS`

17. **HISTORY (历史记录)**
    * **作用域**：`Topic`, `DataWriter`, `DataReader`
    * **目的**：控制`DataWriter`或`DataReader`为**每个数据实例**缓存多少样本。
    * **策略种类 (kind)：**
        * `KEEP_LAST_HISTORY_QOS`: (默认) 为每个实例保留最新的`depth`个样本。
        * `KEEP_ALL_HISTORY_QOS`: 为每个实例保留所有样本（直到资源耗尽）。
    * **关键参数 (仅当`kind = KEEP_LAST`时)：**
        * `depth: long`: 保留的样本数量（按每个实例计算）。
    * **资源限制**：实际缓存数量还受到`RESOURCE_LIMITS`策略的限制。
    * **协商**：不直接影响匹配。但`DataReader`的缓存深度(`depth`)和策略(`kind`)会影响其能接收多少历史数据（尤其在晚加入或使用`DURABILITY`时）。
    * **类型**：`HistoryQosPolicy` (`kind: HistoryQosPolicyKind`, `depth: long`)
    * **默认值**：`kind = KEEP_LAST_HISTORY_QOS`, `depth = 1`

18. **RESOURCE_LIMITS (资源限制)**
    * **作用域**：`Topic`, `DataWriter`, `DataReader`
    * **目的**：限制`DataWriter`或`DataReader`可使用的资源（主要是内存），防止资源耗尽导致系统不稳定。
    * **关键参数：**
        * `max_samples: long`: 实体可缓存的**总样本数**上限。
        * `max_instances: long`: 实体可管理的**数据实例数**上限。
        * `max_samples_per_instance: long`: 单个数据实例可缓存的**样本数**上限。
    * **关系**：这些参数与`HISTORY`策略共同作用。当`HISTORY.kind = KEEP_ALL`时，`max_samples_per_instance`或`max_samples`可能被触发；当`KEEP_LAST`时，`depth`不能超过`max_samples_per_instance`。
    * **行为**：当资源耗尽时：
        * `DataWriter`: `write()`可能阻塞（如果`RELIABILITY.max_blocking_time`允许）或失败（`RETCODE_OUT_OF_RESOURCES`）。
        * `DataReader`: 新样本可能被拒绝（`BEST_EFFORT`）或导致旧样本被丢弃（根据`HISTORY`策略）。
    * **协商**：不直接影响匹配。
    * **类型**：`ResourceLimitsQosPolicy` (`max_samples: long`, `max_instances: long`, `max_samples_per_instance: long`)
    * **默认值**：具体实现定义，通常足够大（如 `max_samples = DDS_LENGTH_UNLIMITED`）。

19. **TRANSPORT_PRIORITY (传输优先级)**
    * **作用域**：`DataWriter`
    * **目的**：为`DataWriter`发送的数据样本指定一个**网络传输优先级**。这是一个**提示**，供底层传输协议（如TCP/IP DiffServ, UDP/IP TOS, 或共享内存调度）参考，以优先处理高优先级数据。
    * **关键参数**：`value: long`。值越大表示优先级越高。
    * **注意**：实际效果取决于操作系统和网络设备对优先级字段的支持。
    * **协商**：不参与匹配。
    * **类型**：`TransportPriorityQosPolicy` (`value: long`)
    * **默认值**：0

20. **LIFESPAN (生存期)**
    * **作用域**：`Topic`, `DataWriter`
    * **目的**：定义数据样本的**有效期**。超过生存期的样本会被中间件自动从`DataWriter`和`DataReader`缓存中丢弃。
    * **关键参数**：`duration: Duration_t` (例如 `{ sec: 10, nanosec: 0 }` 表示10秒)。
    * **行为**：样本的生存期从其**源时间戳(`Source Timestamp`)** 开始计算。到期后，样本在`DataWriter`端不再用于匹配晚加入的`DataReader`（即使使用`DURABILITY`），在`DataReader`端也不再可用。
    * **协商**：不直接影响匹配。`DataReader`会收到样本及其生存期信息，并据此管理本地缓存。
    * **类型**：`LifespanQosPolicy` (`duration: Duration_t`)
    * **默认值**：`duration = { sec: DURATION_INFINITE_SEC, nanosec: DURATION_INFINITE_NSEC }` (无限生存期)

21. **DATA_REPRESENTATION (数据表示)**
    * **作用域**：`Topic`, `DataWriter`, `DataReader`
    * **目的**：指定数据样本在**线上传输**和**最终在`DataReader`端存储**时所使用的**数据编码格式**。
    * **策略值 (value)**：序列`DataRepresentationId_t`，列出实体支持的表示方式。常见值：
        * `XCDR_DATA_REPRESENTATION`: OMG CDR (Common Data Representation) 格式（通常指CDR v1）。最广泛支持。
        * `XML_DATA_REPRESENTATION`: XML 格式。可读性好，但开销大，性能低。
        * `XCDR2_DATA_REPRESENTATION`: 改进的CDR格式（CDR v2）。支持更高效的可扩展类型。
    * **协商**：`DataReader`和`DataWriter`必须至少有一个**共同的**`DATA_REPRESENTATION`值才能匹配。匹配后，双方协商选择一个都支持的最高优先级表示（通常按列表顺序）。
    * **类型**：`DataRepresentationQosPolicy` (`value: sequence<DataRepresentationId_t>`)
    * **默认值**：通常包含`XCDR_DATA_REPRESENTATION`。具体实现可能不同。

22. **TYPE_CONSISTENCY_ENFORCEMENT (类型一致性强制)**
    * **作用域**：`DataWriter`, `DataReader`
    * **目的**：控制在`DataWriter`和`DataReader`匹配时，对它们使用的数据类型(`Type`)之间**兼容性检查的严格程度**。
    * **关键参数：**
        * `kind` (已弃用，通常忽略)
        * `ignore_sequence_bounds`: 是否忽略序列(`sequence`)类型长度界限(`bound`)的差异。
        * `ignore_string_bounds`: 是否忽略字符串(`string`)类型长度界限(`bound`)的差异。
        * `ignore_member_names`: 是否忽略结构体(`struct`)成员名称的差异（只匹配类型和顺序）。
        * `prevent_type_widening`: 是否防止类型“拓宽”（如`DataReader`的`short`字段接收`DataWriter`的`long`值）。
        * `force_type_validation`: 是否强制进行完整的类型验证（即使类型名称相同）。
    * **协商**：不直接影响匹配是否发生，但影响匹配过程中类型兼容性的判断规则。通常`DataReader`的设置更关键。
    * **类型**：`TypeConsistencyEnforcementQosPolicy` (包含上述布尔参数)
    * **默认值**：具体实现定义。通常较宽松 (`ignore_*_bounds = TRUE`, `ignore_member_names = FALSE`, `prevent_type_widening = FALSE`, `force_type_validation = FALSE`)，以促进互操作性。在需要严格类型安全时需显式配置。

---

### 三、QoS策略总结表
以下是基于 **OMG DDS 规范 (v1.4)** 的 **22 个 QoS 策略** 的总结表格，涵盖核心作用域、关键参数、协商规则和默认值：

| QoS 策略 | 作用域 | 关键参数/类型 | 协商规则 | 默认值 |
| :--- | :--- | :--- | :--- | :--- |
| **USER_DATA** | `DomainParticipant`, `Topic`, `DataWriter`, `DataReader`, `Publisher`, `Subscriber` | `value: octet[]` (二进制数据) | 不参与协商 | 空序列 |
| **TOPIC_DATA** | `Topic` | `value: octet[]` (二进制数据) | 不参与协商 | 空序列 |
| **GROUP_DATA** | `Publisher`, `Subscriber` | `value: octet[]` (二进制数据) | 不参与协商 | 空序列 |
| **ENTITY_FACTORY** | `DomainParticipant` Fac, `DomainParticipant`, `Publisher`, `Subscriber` | `autoenable_created_entities: boolean` | 不参与协商 | `TRUE` (自动删除子实体) |
| **DURABILITY** | `Topic`, `DataWriter`, `DataReader` | `kind`: `VOLATILE`/`TRANSIENT_LOCAL`/`TRANSIENT`/`PERSISTENT` | `DataReader` ≥ `DataWriter` (级别) | `VOLATILE_DURABILITY_QOS` |
| **DURABILITY_SERVICE** | `Topic`, `DataWriter` (配合`TRANSIENT`/`PERSISTENT`) | `history_kind`, `history_depth`, `max_samples`等 | 依赖`DURABILITY.kind` | 实现相关 (通常 `KEEP_LAST`, `depth=1`) |
| **PRESENTATION** | `Publisher`, `Subscriber` | `access_scope`: `INSTANCE`/`TOPIC`/`GROUP`<br>`coherent_access: boolean`<br>`ordered_access: boolean` | `Subscriber` ≥ `Publisher` (`access_scope`),<br>`coherent_access`和`ordered_access`需兼容 | `INSTANCE`, `FALSE`, `FALSE` |
| **DEADLINE** | `Topic`, `DataWriter`, `DataReader` | `period: Duration_t` (最大更新间隔) | `DataReader` ≤ `DataWriter` (`period`) | `DURATION_INFINITE` (无限期) |
| **LATENCY_BUDGET** | `Topic`, `DataWriter`, `DataReader` | `duration: Duration_t` (期望最大延迟) | **提示**，不强制协商 | `{0, 0}` (零延迟) |
| **OWNERSHIP** | `Topic`, `DataWriter`, `DataReader` | `kind`: `SHARED`/`EXCLUSIVE` | **必须相同** (`kind`) | `SHARED_OWNERSHIP_QOS` |
| **OWNERSHIP_STRENGTH** | `DataWriter` (配合`EXCLUSIVE`) | `value: long` (强度值) | 依赖`OWNERSHIP.kind = EXCLUSIVE` | `0` |
| **LIVELINESS** | `Topic`, `DataWriter`, `DataReader` | `kind`: `AUTOMATIC`/`MANUAL_BY_PARTICIPANT`/`MANUAL_BY_TOPIC`<br>`lease_duration: Duration_t` | `DataReader` ≤ `DataWriter` (`lease_duration`),<br>`DataReader` `kind` ≤ `DataWriter` `kind` (严格度) | `AUTOMATIC`, `DURATION_INFINITE` |
| **TIME_BASED_FILTER** | `DataReader` | `minimum_separation: Duration_t` (最小接收间隔) | 不参与协商 | `{0, 0}` (不过滤) |
| **PARTITION** | `Publisher`, `Subscriber` | `name: string[]` (分区名称列表) | `Publisher` 和 `Subscriber` 的分区列表**必须有交集** | `[""]` (默认分区) |
| **RELIABILITY** | `Topic`, `DataWriter`, `DataReader` | `kind`: `BEST_EFFORT`/`RELIABLE`<br>`max_blocking_time: Duration_t` (仅`RELIABLE`) | `DataReader` ≥ `DataWriter` (`kind`) | `BEST_EFFORT`, `{100, 0}` (典型) |
| **DESTINATION_ORDER** | `Topic`, `DataWriter`, `DataReader` | `kind`: `BY_RECEPTION_TIMESTAMP`/`BY_SOURCE_TIMESTAMP` | `DataReader` ≥ `DataWriter` (`kind`) | `BY_RECEPTION_TIMESTAMP_DESTINATIONORDER_QOS` |
| **HISTORY** | `Topic`, `DataWriter`, `DataReader` | `kind`: `KEEP_LAST`/`KEEP_ALL`<br>`depth: long` (仅`KEEP_LAST`) | 不参与协商 | `KEEP_LAST_HISTORY_QOS`, `depth=1` |
| **RESOURCE_LIMITS** | `Topic`, `DataWriter`, `DataReader` | `max_samples`<br>`max_instances`<br>`max_samples_per_instance` | 不参与协商 | 实现相关 (通常较大或`UNLIMITED`) |
| **TRANSPORT_PRIORITY** | `DataWriter` | `value: long` (优先级数值) | 不参与协商 | `0` |
| **LIFESPAN** | `Topic`, `DataWriter` | `duration: Duration_t` (样本有效期) | 不参与协商 | `DURATION_INFINITE` (永不过期) |
| **DATA_REPRESENTATION** | `Topic`, `DataWriter`, `DataReader` | `value: DataRepresentationId_t[]` (支持的编码列表) | `DataWriter` 和 `DataReader` **必须至少有一个共同支持的编码** | 通常包含 `XCDR_DATA_REPRESENTATION` |
| **TYPE_CONSISTENCY_ENFORCEMENT** | `DataWriter`, `DataReader` | `ignore_sequence_bounds`<br>`ignore_string_bounds`<br>`ignore_member_names`<br>`prevent_type_widening`<br>`force_type_validation` | 影响类型兼容性检查，不阻止匹配 | 实现相关 (通常较宽松) |


> **关键说明：**
>
> 1. **协商符号**：
>     * `≥` / `≤`：表示要求的 QoS 级别必须**不低于**/**不高于**提供的级别 (例如 `DURABILITY`, `RELIABILITY`, `PRESENTATION.access_scope`, `DESTINATION_ORDER`)。
>     * **必须相同**：表示双方的 QoS 值必须**完全一致**才能匹配 (例如 `OWNERSHIP.kind`)。
>     * **有交集**：表示双方的 QoS 值集合必须有重叠部分 (例如 `PARTITION.name`)。
>     * **DR ≤ DW**：表示 `DataReader` 要求的数值必须 **≤** `DataWriter` 提供的数值 (例如 `DEADLINE.period`, `LIVELINESS.lease_duration`)。
>     * **DR ≥ DW**：表示 `DataReader` 要求的数值必须 **≥** `DataWriter` 提供的数值 (例如 `RELIABILITY.kind`, `DESTINATION_ORDER.kind`)。
> 2. **默认值**：`DURATION_INFINITE` 表示无限长的时间。具体数值（如 `RESOURCE_LIMITS.max_samples`, `RELIABILITY.max_blocking_time.sec = 100`）可能因 DDS 实现而异。
> 3. **核心协商策略**：`DURABILITY`, `DEADLINE`, `LIVELINESS`, `RELIABILITY`, `OWNERSHIP`, `PARTITION`, `DATA_REPRESENTATION` 是直接影响 `DataWriter` 和 `DataReader` 能否成功匹配并进行通信的关键 QoS。配置时需特别关注它们的兼容性。
---

> **提示**：2024年中国发布《智能网联汽车用数据分发服务（DDS）测试方法》（T/CSAE 371-2024），为QoS配置提供标准化依据。
