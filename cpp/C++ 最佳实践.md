# C++ 最佳实践

> 面向 **C++17/20**，以现代 C++ + 工程交付为目标。每条都有「为什么」与「怎么做」，可作为 Code Review 清单。

---

## 1. 资源管理 RAII 与所有权

| 场景 | 推荐 | 反例 |
|------|------|------|
| 独占所有权 | `std::unique_ptr<T>` | `new` + 手动 `delete` |
| 共享所有权 | `std::shared_ptr<T>`（确实需要时） | 处处 `shared_ptr`、循环引用 |
| 观察/不拥有 | 裸指针 `T*` 或 `T&` 或 `std::weak_ptr<T>` | `shared_ptr` 当观察者 |
| 锁/文件/句柄 | `std::lock_guard` / `unique_lock` / `fstream` | 手动 lock/unlock |

口诀：**Rule of Zero** —— 让标准库容器和智能指针管理资源，自定义类尽量不写析构、拷贝、移动。
若必写其一，则同时考虑 **Rule of Five**（析构、拷贝构造/赋值、移动构造/赋值）。

```cpp
// 工厂返回 unique_ptr，调用方决定是否升级为 shared
std::unique_ptr<Sensor> make_sensor(Config cfg);

// shared_ptr 仅用于真正多 owner（cache、observer pattern）
std::shared_ptr<const Map> map = load_map();   // 多线程只读共享

// 不拥有 → 引用 / 裸指针，禁止 .get() 后存活时间不可控
void process(const Sensor& s);                  // 借用
```

---

## 2. const、constexpr、consteval、noexcept

* 默认 `const` —— 形参、成员函数、局部变量能 `const` 就 `const`。
* 编译期能算的常量用 `constexpr`；C++20 起可用 `consteval`（强制编译期）、`constinit`（强制零初始化）。
* 不抛异常的析构、移动、swap 必须 `noexcept`，否则容器扩容时退化为拷贝。

```cpp
class Buffer {
public:
    Buffer(Buffer&&) noexcept = default;       // 关键
    Buffer& operator=(Buffer&&) noexcept = default;
    ~Buffer() noexcept = default;
    void swap(Buffer& other) noexcept;
};
```

---

## 3. 值类别与移动语义

* 函数参数按使用方式选传参：
  * **只读小对象**（≤16B、trivially copyable）：按值
  * **只读大对象**：`const T&`
  * **会修改**：`T&`
  * **会消费/转移**：按值传参 + `std::move`（或 `T&&` + 完美转发）
* `std::move` 只是 `static_cast<T&&>`，不要对 `const T` 用，会失效。
* 返回局部变量按值（**RVO/NRVO** 复制省略），不要画蛇添足 `std::move(local)`。

```cpp
std::vector<int> make_data() {
    std::vector<int> v(1024);
    return v;          // 编译器 NRVO
    // return std::move(v);  // ❌ 反而抑制 RVO
}
```

---

## 4. 容器与算法选择

| 需求 | 首选 | 备选 / 注意 |
|------|------|------|
| 顺序、随机访问 | `std::vector` | 数据极大 → `std::deque`（分段） |
| 频繁中间插入 | `std::list`（少用） | 通常 `vector` + 排序更快 |
| 键值映射 | `std::unordered_map` | 需要有序/范围 → `std::map` |
| 集合 | `std::unordered_set` | 同上 |
| 小固定大小 | `std::array<T,N>` | 栈上零分配 |
| 字符串视图 | `std::string_view`（C++17） | 警惕悬空 |

* **`vector` 默认**：缓存友好、连续内存，几乎总是最快。
* `unordered_map` 默认 hash 对自定义类型不可用，需特化 `std::hash`。
* 大量元素先 `reserve()`，避免多次 realloc。
* 用 `<algorithm>` / `<ranges>`，不要手撸 for 循环。

```cpp
// C++20 ranges
auto evens = data | std::views::filter([](int x){ return x%2==0; })
                  | std::views::transform([](int x){ return x*x; });
```

---

## 5. 字符串与文本

* C++17：`std::string_view` 作为只读形参（不要存为成员）。
* 拼接用 `fmt::format` / C++20 `std::format`，避免 `+` 链或 `stringstream`。
* 解析数字用 `std::from_chars`（无分配、无 locale）。
* UTF-8 默认，不要混用 `wchar_t`；Windows 路径用 `std::filesystem::path`。

---

## 6. 错误处理

| 场景 | 策略 |
|------|------|
| 编程错误（违约） | `assert` / `[[assume]]` / 终止 |
| 可恢复异常 | `throw` + RAII 回滚 |
| 期望失败（如解析） | `std::optional<T>` / `std::expected<T,E>`（C++23） |
| 跨 ABI 边界 | 错误码 `int` / `enum class Status` |
| 实时控制循环 | 错误码，**禁止异常**（不可预测时延） |

* 不要用异常做控制流，不要在析构里抛。
* 在 `main` 顶层 `catch(...)` 写日志，不要让异常 ABI 跨越动态库边界。

---

## 7. 并发与多线程

* 默认 `std::jthread`（C++20，自动 join + stop_token）。
* 锁粒度尽量小：先准备数据再 `lock_guard`。
* 避免嵌套锁；必须时用 `std::scoped_lock` 一次锁多把。
* 共享状态优先 **不可变 + shared_ptr<const T>** 替换式发布，胜过 mutex。
* `std::atomic<T>` 适合标志/计数，不要替代 mutex 保护复杂对象。
* 线程间通信用 `std::condition_variable` + 谓词，永远不要无谓词 wait。
* 高并发场景用任务队列 / 线程池 / coroutine（C++20），不要为每个请求开线程。

---

## 8. 模板与泛型

* C++20 起首选 **concepts**，比 SFINAE 可读得多：

```cpp
template <std::ranges::range R>
    requires std::integral<std::ranges::range_value_t<R>>
auto sum(const R& r) { /*...*/ }
```

* 模板尽量放头文件（或用 `extern template` 控制实例化）。
* 避免过度模板化导致编译时间爆炸；接口可用类型擦除（`std::function`、`std::any`、虚函数）。
* `if constexpr` 替代复杂 SFINAE 分支。

---

## 9. 编译期与构建工程

* 工程使用 **CMake ≥ 3.20**，targets-based；现代写法：

```cmake
add_library(myproj_core src/a.cpp src/b.cpp)
target_include_directories(myproj_core PUBLIC include)
target_compile_features(myproj_core PUBLIC cxx_std_20)
target_compile_options(myproj_core PRIVATE -Wall -Wextra -Wpedantic -Werror)
```

* 不写 `include_directories` / `link_libraries`（全局污染）。
* 第三方库优先 `find_package` + `IMPORTED targets`；离线项目用 `FetchContent` 或子模块。
* 编译选项三件套：`-Wall -Wextra -Wpedantic`，发布加 `-O2 -DNDEBUG`，调试加 `-g -fsanitize=address,undefined`。
* 静态检查：`clang-tidy`、`cppcheck`、`include-what-you-use`。
* 格式化：`.clang-format` 入仓 + pre-commit hook。

---

## 10. 头文件与编译时间

* 一个公共头一个职责；用前向声明替代 include。
* 标准库不可前向声明，用 `#include <iosfwd>` 等专门 forward 头。
* 大项目使用 **PIMPL**（Pointer to Implementation）解耦 ABI：

```cpp
// foo.h
class Foo {
public:
    Foo(); ~Foo();
    void run();
private:
    struct Impl; std::unique_ptr<Impl> p_;
};
```

* C++20 起评估 **Modules**（编译时间提升明显，但工具链需 ≥ GCC 14 / Clang 17）。
* 单元测试不要 include 整个库，按需 include。

---

## 11. 性能与可测量性

* **先 profile 再优化**：`perf`、`vtune`、`gperftools`、`callgrind`。
* 微基准：Google Benchmark；注意 `benchmark::DoNotOptimize`。
* 缓存友好：SoA vs AoS，热点字段聚合，`alignas(64)` 避免 false sharing。
* 分支预测：热路径上避免虚函数和异常；分支提示用 `[[likely]]/[[unlikely]]`（C++20）。
* 避免在循环里堆分配；用 `reserve` / 池 / `std::pmr` 多态资源。
* 别忽视 **链接期优化 LTO / PGO**。

---

## 12. 内存安全 Sanitizer

| 工具 | 检测 |
|------|------|
| ASan (`-fsanitize=address`) | 越界、UAF、堆溢出 |
| UBSan (`-fsanitize=undefined`) | 未定义行为：溢出、空指针、对齐 |
| TSan (`-fsanitize=thread`) | 数据竞争 |
| MSan (`-fsanitize=memory`) | 未初始化读 |
| Valgrind | 通用，慢 10~50× |

CI 至少跑 ASan + UBSan。

---

## 13. 测试与质量门

* 单元测试：**GoogleTest** / Catch2，覆盖率 `gcov` + `lcov`，CI 报告。
* 集成测试：黑盒、容器化（docker-compose）。
* 模糊测试：`libFuzzer`、AFL，对解析/反序列化路径必备。
* 静态分析进 CI（clang-tidy 失败即 PR 不通过）。
* 性能回归：基准跑 baseline diff（如 `bench-record`）。

---

## 14. API 设计

* 优先 **强类型** 替代 `int`/`bool` 串：`enum class Mode`，单位类型 `std::chrono::milliseconds`。
* 输出参数尽量改为返回值（`std::tuple` / `struct`）；OutParam 加 `[[nodiscard]]`。
* 不要导出全局可变状态；线程不安全函数明确文档化。
* 公共头中**不放 `using namespace`**。
* 二进制接口用 C 风格 `extern "C"`，避免 std 类型跨 ABI。

---

## 15. C++ 反模式 Top 15

1. `using namespace std;` 写在头文件。
2. 处处 `shared_ptr`，导致循环引用与原子开销。
3. 用 `new`/`delete`/`malloc`/`free`。
4. `catch(...)` 吞异常不记日志。
5. 析构函数抛异常。
6. 在多线程下读写非 atomic 共享变量没加锁。
7. `auto x = vec.size() - 1;` —— 无符号下溢死循环。
8. `std::vector<bool>` 当布尔数组（不是真正容器）。
9. C 风格强转 `(T*)x` 替代 `static_cast`/`reinterpret_cast`。
10. 把 `std::string_view` 存成成员（生命周期）。
11. 模板放 `.cpp`（链接错）。
12. 误用 `volatile` 当原子。
13. 用 `std::endl` 在热路径（强制 flush）。
14. 单元测试与生产代码 include 不同标准库版本。
15. 假定有符号溢出有定义（UB）。

---

## 16. 现代特性快速速查

| 版本 | 你应该用的 |
|------|------|
| C++11 | `auto`、`nullptr`、范围 for、lambda、`unique_ptr`、`thread`/`mutex`、移动语义 |
| C++14 | 泛型 lambda、`std::make_unique`、变量模板 |
| C++17 | 结构化绑定、`if constexpr`、`std::optional/variant/any/string_view`、`filesystem`、并行算法 |
| C++20 | concepts、ranges、coroutines、modules、`std::span`、`std::format`、`<chrono>` 时区、`std::jthread` |
| C++23 | `std::expected`、`std::print`、`std::flat_map`、`std::mdspan`、`if consteval` |

---

## 17. Top 20 工程化 Checklist

1. ☐ 项目用 CMake target-based 写法，无全局 include/link。
2. ☐ `-Wall -Wextra -Wpedantic -Werror` 全开。
3. ☐ CI 跑 ASan + UBSan + clang-tidy。
4. ☐ 默认 C++17/20，`target_compile_features` 声明。
5. ☐ Rule of Zero，少写析构/拷贝/移动。
6. ☐ 资源用智能指针 / RAII，**禁止裸 new/delete**。
7. ☐ 析构、移动、swap `noexcept`。
8. ☐ 函数能 `const`/`constexpr` 就加。
9. ☐ 形参选择遵循「值/const&/&&」决策表。
10. ☐ `vector` 默认，先 `reserve`。
11. ☐ 字符串拼接用 `fmt::format` / `std::format`。
12. ☐ 错误处理风格统一（异常 OR `expected`），文档化。
13. ☐ 多线程共享数据不可变 + `shared_ptr<const>`，或最小粒度锁。
14. ☐ `std::condition_variable` 必须带谓词。
15. ☐ `clang-format` + pre-commit。
16. ☐ 公共头无 `using namespace`、无大型 include。
17. ☐ ABI 边界用 PIMPL / C 接口。
18. ☐ 单元测试覆盖率 ≥ 70%，关键模块 ≥ 90%。
19. ☐ 性能优化前必先 profile。
20. ☐ 头文件加 `#pragma once`，include 用 `""` vs `<>` 一致。

---

## 面试速记

1. **Rule of Zero / Rule of Five**：让标准库管资源，必写其一则补全其五。
2. `unique_ptr` 默认，`shared_ptr` 真共享，`weak_ptr` 破循环。
3. `noexcept` 移动让 vector 扩容不退化为拷贝。
4. RVO/NRVO：返回局部变量不要 `std::move`。
5. `string_view` 是引用，不延长生命周期。
6. `std::shared_ptr` 控制块原子计数 → 高并发热点用 `intrusive_ptr` / 自定义。
7. C++20 三大件：concepts、ranges、coroutines。
8. 异常不能跨动态库 ABI；实时控制循环禁用异常。
9. Sanitizer 是默认装备：ASan + UBSan + TSan。
10. **先测量再优化**：perf + Google Benchmark；缓存命中比指令数更重要。

---

## 关联阅读

* [C++ 简介](C++%20简介.md) · [C++ 数据类型](C++%20数据类型.md) · [C++ 类（Class）](C++%20类（Class）.md)
* [C++ 指针、智能指针、引用](C++%20指针、智能指针、引用.md) · [C++ 内存管理](C++%20内存管理.md)
* [C++ 多线程](C++%20多线程.md) · [C++ 线程池](C++%20线程池.md) · [C++ 任务队列](C++%20任务队列.md)
* [C++ 模板](C++%20模板.md) · [C++ 多态](C++%20多态.md) · [C++ 继承](C++%20继承.md)
* [C++ Lambda 表达式](C++%20Lambda%20表达式.md) · [C++ 容器](C++%20容器.md)
* [Eigen 最佳实践](eigen/Eigen_最佳实践.md)
