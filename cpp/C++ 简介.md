C++是一种由Bjarne Stroustrup在1979年在贝尔实验室开始开发的一种**静态类型**、**编译式**、**通用的**、**面向对象**的编程语言。C++被设计为一种“增强”的C语言，保留了C语言的高效性和灵活性，同时引入了**面向对象编程**、**泛型编程**和**异常处理**等特性。
## C++ 关键特点
1. **面向对象编程（OOP）**：C++支持封装、继承和多态性，这是面向对象编程的三大基本特征。
2. **泛型编程**：C++通过模板提供了泛型编程的支持，允许开发者编写与数据类型无关的代码。
3. **直接操作硬件**：C++提供了接近硬件层面的操作能力，使其在性能要求高的领域（如游戏开发、嵌入式系统）中非常流行。
4. **多重编程范式**：C++不仅支持面向对象编程，还支持过程式编程和泛型编程。
5. **异常处理**：C++提供了一套异常处理机制，允许程序在遇到错误时优雅地处理。
6. **STL（标准模板库）**：C++的STL提供了一系列的数据结构（如向量、列表、映射）和算法（如排序、搜索），极大地提高了开发效率。
7. **RAII（资源获取即初始化）**：C++通过对象的生命周期管理资源，确保资源的正确释放，减少内存泄漏。
8. **编译时多态**：C++通过模板和函数重载支持编译时多态，提高了程序的灵活性和性能。
9. **模块化**：C++支持模块化编程，有助于大型项目的组织和管理。
10. **跨平台**：C++可以在多种操作系统和硬件平台上运行，包括Windows、Linux、macOS等。
11. **性能**：C++以其接近硬件的性能而闻名，通常用于性能敏感型应用。
12. **标准库**：C++有一个丰富的标准库，提供了广泛的功能，如文件操作、网络编程、多线程等。
C++广泛应用于**系统/应用软件、游戏开发、高性能服务器和客户端应用、实时系统、嵌入式固件**等领域。
## C++ 标准
C++语言自1998年发布第一个官方标准以来，经历了多个版本的迭代，每个版本都引入了新特性和改进。以下是C++各版本之间的主要区别：

1. **C++98**：这是第一个 ANSI/ISO 标准化的 C++ 版本，发布于 1998 年。它引入了 STL（标准模板库）、异常处理、I/O Streams、命名空间和 RTTI（运行时类型识别）等重要特性。
2. **C++03**：这个版本主要是对 C++98 的一些修正和改进，发布于 2003 年，并未引入新的语言特性，所以一般不把它当做重要版本。
3. **C++11**：这是 C++ 历史上最重大的更新之一，有时被称为 C++0x。它引入了自动类型推断（auto 关键字）、基于范围的 for 循环、Lambda 表达式、智能指针、并发支持、移动语义、nullptr 和更强大的模板功能等。
4. **C++14**：作为 C++11 的小幅度更新，C++14 引入了一些改进和新特性，包括泛型 Lambda 表达式、返回类型推导、二进制字面量、数字分隔符、弃用属性等。
5. **C++17**：这个版本进一步提升了 C++ 的功能和易用性，新功能不是很多，引入了结构化绑定、if constexpr、std::optional、std::variant、std::string_view、并行算法等特性。
6. **C++20**：继 C++11 之后又一个重大更新，引入了概念（concepts）、范围库（ranges）、协程（coroutines）、模块（modules）、三元运算符的改进、constexpr 的增强、std::span 等新特性。
7. **C++23**：2023 年 7 月份刚确定的新标准，变化包括引入标准库的模块化支持、扩展 constexpr、增加并行算法、ranges 扩展、this 推导、引入更多的属性和注解、增加 std::mdspan、std::generator 等新特性。

每个新版本的发布都旨在提高C++语言的表达力、性能和易用性，同时也为开发者提供了更多的工具和功能来应对不同的编程需求。

| 特性/版本 | C++98 | C++03 | C++11 | C++14 | C++17 | C++20 | C++23 |
|-----------|-------|-------|-------|-------|-------|-------|-------|
| 标准名称  | ISO/IEC 14882:1998 | ISO/IEC 14882:2003 | ISO/IEC 14882:2011 | ISO/IEC 14882:2014 | ISO/IEC 14882:2017 | ISO/IEC 14882:2017 | ISO/IEC 14882:2023 |
| 异常处理  | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| STL       | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| 命名空间  | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| 模板      | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| 智能指针  | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| 基于范围的for循环 | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| Lambda表达式 | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| 自动类型推断（auto） | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| `nullptr`    | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| 并发支持  | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| 移动语义  | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| 变长模板 | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| 数字字面量 | 不支持:x: | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| 二进制字面量 | 不支持:x: | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| `std::thread` | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| `std::optional` | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| `std::variant` | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| `std::string_view` | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| 并行算法  | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| `if constexpr` | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| 模块      | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| 概念      | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| 协程      | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| 范围库    | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| `std::span`  | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| `std::format` | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: | 支持:heavy_check_mark: |
| `std::mdspan` | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: |
| `std::generator` | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 不支持:x: | 支持:heavy_check_mark: |
