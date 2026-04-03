# InterviewGuide

> 一份面向 **C++ / Python / DDS** 方向的技术面试知识库，涵盖核心语言特性、分布式中间件、网络协议及项目实战经验总结。适合有一定工程经验的开发者在面试前系统复习。

---

## 📚 内容模块

### 💻 C++ [`cpp/`](cpp/)

涵盖现代 C++ 的核心知识点，每个文件独立成章，可按需查阅：

| 文件 | 内容简介 |
|------|----------|
| [C++ 简介](cpp/C++%20简介.md) | C++ 标准演进、编译流程、核心特性概览 |
| [C++ 数据类型](cpp/C++%20数据类型.md) | 基本类型、类型转换、`sizeof` 等 |
| [C++ 指针、智能指针、引用](cpp/C++%20指针、智能指针、引用.md) | 裸指针、`unique_ptr`/`shared_ptr`/`weak_ptr`、循环引用 |
| [C++ 内存管理](cpp/C++%20内存管理.md) | 堆栈分配、`new`/`delete`、内存对齐、RAII |
| [C++ 类（Class）](cpp/C++%20类（Class）.md) | 构造/析构、拷贝控制、`static`/`const` 成员 |
| [C++ 继承](cpp/C++%20继承.md) | 单继承、多继承、虚继承、菱形继承 |
| [C++ 多态](cpp/C++%20多态.md) | 虚函数表（vtable）、`override`/`final`、纯虚函数 |
| [C++ 模板](cpp/C++%20模板.md) | 函数模板、类模板、模板特化、CRTP |
| [C++ Lambda 表达式](cpp/C++%20Lambda%20表达式.md) | 捕获列表、可变 lambda、泛型 lambda |
| [C++ 容器](cpp/C++%20容器.md) | `vector`/`map`/`unordered_map` 等底层实现与复杂度 |
| [C++ 字符串](cpp/C++%20字符串.md) | `string` 操作、`string_view`、格式化 |
| [C++ 多线程](cpp/C++%20多线程.md) | `thread`、`mutex`、`condition_variable`、`atomic` |
| [C++ 进程 线程](cpp/C++%20进程%20线程.md) | 进程与线程的区别、创建与管理 |
| [C++ 进程间通信（IPC）](cpp/C++%20进程间通信（IPC）.md) | 管道、消息队列、共享内存、信号量、Socket |
| [C++ 线程池](cpp/C++%20线程池.md) | 线程池设计与实现 |
| [C++ 任务队列](cpp/C++%20任务队列.md) | 无锁队列、任务调度 |
| [C++ 单例模式 实现](cpp/C++%20单例模式%20实现.md) | 懒汉式、饿汉式、`Meyers` Singleton |
| [C++ 结构体（Struct）](cpp/C++%20结构体（Struct）.md) | 与 class 的区别、内存布局、位字段 |
| [C++ 预处理器（Preprocessor）](cpp/C++%20预处理器（Preprocessor）.md) | 宏、条件编译、`#include` 防卫 |
| [C++ 数组类型](cpp/C++%20数组类型.md) | 原生数组、`std::array`、动态数组 |
| [C++ 格式说明符](cpp/C++%20格式说明符.md) | `printf`/`scanf` 格式说明符速查 |

---

### 🐍 Python [`python/`](python/)

覆盖 Python 高频面试点与工程实践：

| 文件 | 内容简介 |
|------|----------|
| [Python 类 Class](python/Python%20类%20Class.md) | 继承、`MRO`、`__slots__`、元类 |
| [Python 装饰器](python/Python%20装饰器.md) | 函数装饰器、类装饰器、装饰器链 |
| [Python 内置装饰器](python/Python%20内置装饰器.md) | `@property`、`@classmethod`、`@staticmethod` |
| [Python 迭代器与生成器](python/Python%20迭代器与生成器.md) | `__iter__`/`__next__`、`yield`、惰性求值 |
| [Python Lambda 表达式](python/Python%20Lambda%20表达式.md) | 匿名函数、与 `map`/`filter`/`sorted` 配合 |
| [Python 多线程](python/Python%20多线程.md) | GIL、`threading` 模块、线程同步 |
| [Python 多进程](python/Python%20多进程.md) | `multiprocessing`、进程池、共享内存 |
| [Python 并发](python/Python%20并发.md) | `asyncio`、协程、`async`/`await` |
| [Python 正则表达式](python/Python%20正则表达式.md) | `re` 模块、常用模式、命名分组 |
| [Python 内置函数](python/Python%20内置函数.md) | `map`/`filter`/`zip`/`enumerate` 等速查 |
| [Python 数据类型转换](python/Python%20数据类型转换.md) | 隐式/显式转换、`int`/`str`/`list` 互转 |

---

### 📡 DDS（数据分发服务）[`dds/`](dds/)

DDS（Data Distribution Service）是面向实时分布式系统的发布/订阅中间件，广泛用于自动驾驶、机器人等领域：

| 文件 | 内容简介 |
|------|----------|
| [DDS 概述](dds/DDS.md) | DDS 架构、核心概念（Domain / Topic / DataWriter / DataReader） |
| [DDS QoS](dds/DDS%20QOS.md) | 23 种 QoS 策略详解（可靠性、持久性、截止时间等） |
| [DDS Discovery](dds/DDS%20Discovery.md) | SPDP / SEDP 发现协议、动态发现机制 |
| [DDS RTPS](dds/DDS%20RTPS.md) | RTPS 协议规范、消息格式、可靠传输 |
| [DDS XTypes](dds/DDS%20XTypes.md) | 动态类型、可扩展类型系统 |
| [DDS XTypes IDL](dds/DDS%20XTypes%20IDL.md) | IDL 语法、类型注解、序列化 |
| [DDS Zero-Copy](dds/DDS%20Zero-Copy.md) | 零拷贝传输机制、共享内存优化 |
| [DDS Q&A](dds/DDS%20Q%26A.md) | 高频面试问题与参考答案 |

---

### 🌐 网络 [`network/`](network/)

| 文件 | 内容简介 |
|------|----------|
| [TCP UDP](network/TCP%20UDP.md) | TCP 三次握手/四次挥手、滑动窗口、UDP 特性对比、Socket 编程 |

---

### 🔧 工具 [`tools/`](tools/)

| 文件 | 内容简介 |
|------|----------|
| [git](tools/git.md) | 常用 git 命令、分支管理、rebase vs merge、冲突解决 |
| [repo](tools/repo.md) | Android `repo` 工具使用、多仓库管理 |
| [SQLite3](tools/SQLite3.md) | SQLite3 C++ API、常用 SQL 速查 |

---

### 📝 面试总结 [`summarize/`](summarize/)

按领域分类整理的面试准备材料，包含高质量问答示例和实战案例：

#### C++ 方向 [`summarize/cpp/`](summarize/cpp/)

| 文件 | 内容简介 |
|------|----------|
| [IPC与内存管理面试要点](summarize/cpp/IPC与内存管理面试要点.md) | 进程间通信、线程同步、智能指针循环引用、vtable 等高频题 |
| [多态与智能指针面试要点](summarize/cpp/多态与智能指针面试要点.md) | 虚函数原理、抽象类、`shared_ptr`/`unique_ptr`/`weak_ptr` 详解 |
| [系统问题排查](summarize/cpp/系统问题排查.md) | CPU/内存突增排查流程（`top`/`pmap`/`perf` 等工具链） |

#### DDS 方向 [`summarize/dds/`](summarize/dds/)

| 文件 | 内容简介 |
|------|----------|
| [DDS-自动驾驶应用](summarize/dds/DDS-自动驾驶应用.md) | DDS 在自动驾驶中的核心优势与典型应用场景 |
| [DDS-发现阶段网络风暴规避策略](summarize/dds/DDS-发现阶段网络风暴规避策略.md) | 大规模部署时 SPDP 广播风暴的规避方案 |
| [DDS-高频大数据场景优化](summarize/dds/DDS-高频大数据场景优化.md) | QoS 调优、零拷贝、异步发布在高频场景的实践 |
| [DDS-跨域通信大数据场景优化](summarize/dds/DDS-跨域通信大数据场景优化.md) | 跨 Domain 通信的流控与性能优化策略 |
| [RTI-DDS流量控制QoS策略](summarize/dds/RTI-DDS流量控制QoS策略.md) | RTI Connext DDS 流量控制相关 QoS 配置解析 |
| [SR卡顿排查案例](summarize/dds/SR卡顿排查案例.md) | 自动驾驶感知融合模块在复杂路口卡顿问题的完整排查过程 |
| [MQTT与DDS对比](summarize/dds/MQTT与DDS对比.md) | 架构、实时性、QoS、适用场景全面对比 |
| [协议栈对比(CAN-SOMEIP-DDS)](summarize/dds/协议栈对比\(CAN-SOMEIP-DDS\).md) | CAN 总线 / SOME-IP / DDS 三种协议横向对比 |

---

### 📖 参考资料 [`reference/`](reference/)

收录精选 PDF 书籍与学习笔记：

- **C++**：《Effective Modern C++》笔记、C++ 八股文速查、面经整理
- **DDS**：DDS 规范文档、SOA 架构设计
- **Python**：Python 核心知识速查

---

## 🗂️ 目录结构

```
InterviewGuide/
├── cpp/                    # C++ 核心知识点（21 个专题）
├── python/                 # Python 核心知识点（11 个专题）
├── dds/                    # DDS 中间件（8 个专题）
├── network/                # 网络协议
│   └── TCP UDP.md
├── tools/                  # 开发工具速查
│   ├── git.md
│   ├── repo.md
│   └── SQLite3.md
├── summarize/              # 面试总结
│   ├── cpp/                # C++ 面试要点与系统排查
│   └── dds/                # DDS 技术深度与实战案例
└── reference/              # 参考资料（PDF + 笔记）
    ├── C++/
    ├── DDS/
    └── Python/
```

---

## 🚀 使用建议

1. **快速复习**：直接查阅 [`summarize/`](summarize/) 下的面试要点文件，包含高质量问答模板
2. **深入学习**：阅读对应领域目录（`cpp/` / `dds/`）下的详细专题文档
3. **项目经验准备**：参考 [SR卡顿排查案例](summarize/dds/SR卡顿排查案例.md) 学习如何结构化描述技术挑战
4. **协议对比题**：查阅 [协议栈对比](summarize/dds/协议栈对比\(CAN-SOMEIP-DDS\).md) 和 [MQTT与DDS对比](summarize/dds/MQTT与DDS对比.md)

---

## 📄 License

[Apache 2.0](LICENSE)