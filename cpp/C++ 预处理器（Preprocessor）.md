> 在现代C++编程中，推荐使用==内联函数、模板和constexpr等特性==替代宏，以获得更好的类型安全和代码可维护性。

C++ 预处理器（Preprocessor）是C++编译器的一部分，它在实际编译过程之前对源代码进行处理。预处理器处理源代码中的指令，这些指令以井号（`#`）开头。预处理器的主要功能包括宏定义、文件包含、条件编译等。
## 预处理器指令
### 宏定义（#define）与 取消宏定义（#undef）
用于定义宏。可以定义简单的宏，也可以定义带参数的宏。
```cpp
// 宏定义（#define）
#define MACRO_NAME replacement-text

// 取消宏定义（#undef）
#undef MACRO_NAME
```
- `MACRO_NAME` 是想要定义的宏的名称。
- `replacement-text` 是当宏被使用时将替换宏名称的文本。
#### 组合使用 `#define` 和 `#undef`
有时候，可能想要在包含头文件多次时避免宏被重复定义。这可以通过组合使用 `#ifndef`、`#define` 和 `#endif` 来实现，这种方式被称为“包含卫士”（include guard）：
```cpp
#ifndef HEADER_FILE_H
#define HEADER_FILE_H

// 头文件内容

#endif // HEADER_FILE_H
```
如果头文件被包含多次，`HEADER_FILE_H` 宏将只在第一次包含时被定义，后续包含时由于 `HEADER_FILE_H` 已经定义，所以内容不会被重复处理。
#### 示例
##### 定义一个宏来表示一个常量
```cpp
#define MAX_SIZE 1024
```
`MAX_SIZE` 被定义为 `1024`。在代码中任何使用 `MAX_SIZE` 的地方，预处理器都会将其替换为 `1024`。
##### 定义一个带参数的宏
```cpp
#define SQUARE(x) ((x) * (x))
```
`SQUARE(x)` 被定义为 `((x) * (x))`。当你调用 `SQUARE(5)` 时，预处理器会将其替换为 `((5) * (5))`。
##### 取消之前定义的 `MAX_SIZE` 宏
```cpp
#undef MAX_SIZE
```
`MAX_SIZE` 宏被取消定义。在 `#undef MAX_SIZE` 之后的代码中，`MAX_SIZE` 将不再是一个宏，而是被视为一个普通的标识符。
##### 宏展开（Macro Expansion）
预处理器会在编译之前将宏替换为其定义的内容。
```cpp
int area = SQUARE(5); // 替换为 int area = (5) * (5);
```

> 预定义宏 由编译器自动提供，可以帮助开发者编写更具可移植性和适应性的代码，它们不依赖于用户的定义，并且通常用于调试、日志记录、条件编译等场景。使用这些宏时，不需要`#include`任何头文件，它们是预处理器的一部分。
>
> | 宏名称                       | 描述                                                         | 示例代码                                                     |
> | ---------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
> | `__LINE__`                   | 当前行号，一个整数常量。                                     | `printf("Current line: %d\n", __LINE__);`                    |
> | `__FILE__`                   | 当前文件名，一个字符串常量。                                 | `printf("Current file: %s\n", __FILE__);`                    |
> | `__DATE__`                   | 编译日期，格式为"MMM DD YYYY"的字符串常量。                  | `printf("Compilation date: %s\n", __DATE__);`                |
> | `__TIME__`                   | 编译时间，格式为"HH:MM:SS"的字符串常量。                     | `printf("Compilation time: %s\n", __TIME__);`                |
> | `__func__` 或 `__FUNCTION__` | 当前函数名，一个字符串常量。                                 | `printf("Current function: %s\n", __func__);`                |
> | `__cplusplus`                | 指示编译器支持的C++标准的版本号，例如`199711L`表示C++98。    | `#if __cplusplus >= 201103L\n    // C++11 or later code\n#endif` |
> | `__COUNTER__`                | 一个自增的整数，每次使用时增加，用于生成唯一的标签。         | `static int unique_var_##__COUNTER__ = 0;`                   |
> | `_CPPRTTI`                   | 如果编译器支持RTTI（运行时类型识别），则定义为1。            | `#if defined(_CPPRTTI)\n    // Code using RTTI\n#endif`      |
> | `_CPPUNWIND`                 | 如果编译器支持异常处理，定义为1。                            | `#if defined(_CPPUNWIND)\n    // Code using exception handling\n#endif` |
> | `_WIN32`                     | 如果编译器目标为Windows平台，则定义此宏。                    | `#if defined(_WIN32)\n    // Windows-specific code\n#endif`  |
> | `_WIN64`                     | 如果编译器目标为Windows 64-bit平台，则定义此宏。             | `#if defined(_WIN64)\n    // Windows 64-bit specific code\n#endif` |
> | `__linux__`                  | 如果编译器目标为Linux平台，则定义此宏。                      | `#if defined(__linux__)\n    // Linux-specific code\n#endif` |
> | `__GNUC__`                   | 如果编译器是GNU GCC，则定义此宏，并且`__GNUC__`给出GCC的主要版本号。 | `#if defined(__GNUC__)\n    // GCC-specific code\n#endif`    |
> | `__clang__`                  | 如果编译器是Clang，则定义此宏。                              | `#if defined(__clang__)\n    // Clang-specific code\n#endif` |
> | `_MSC_VER`                   | 如果编译器是Microsoft Visual C++，则定义此宏，并且`_MSC_VER`给出MSVC的版本号。 | `#if defined(_MSC_VER)\n    // MSVC-specific code\n#endif`   |
>
### 文件包含（`#include`）
将一个文件的内容包含到另一个文件中。
```cpp
#include <iostream>
#include "myheader.h"
```

### 编译行控制（`#pragma`）
用于提供编译器特定的指令，如警告控制、优化等。
```cpp
#pragma once // 确保头文件只被包含一次
#pragma warning(disable : 4996) // 禁用特定警告
```

### 错误和警告（`#error`, `#warning`）
在编译时生成错误或警告信息。
```cpp
#error "This is a critical error"
#warning "This is a warning message"
```


## 预处理器的作用

1. **代码复用**：通过宏定义，可以在不同的代码位置重复使用相同的代码片段。
2. **平台和编译器兼容性**：预处理器指令可以用来编写条件编译代码，以适应不同的平台和编译器。
3. **调试和优化**：可以定义宏来开启或关闭调试信息，或者根据需要启用或禁用优化。
4. **代码隐藏**：预处理器可以帮助隐藏实现细节，只暴露接口，有助于保护代码的知识产权。
5. **提高效率**：宏展开在编译之前完成，可以减少运行时的类型检查和函数调用开销。

## 预处理器的限制

1. **类型安全**：宏不进行类型检查，因此可能导致类型相关的错误，特别是在宏函数中。
2. **调试困难**：宏展开后的代码可能会使调试变得困难，因为源代码和编译后的代码之间存在差异。
3. **作用域问题**：宏在全局作用域中定义，可能会导致命名冲突。
4. **代码膨胀**：宏展开可能会导致编译后的代码体积增大，特别是在复杂的宏定义中。
5. **可读性**：复杂的宏可能会降低代码的可读性，特别是在宏涉及多个代码行和条件语句时。
6. **维护性**：宏定义的代码可能难以维护，尤其是当宏逻辑变得复杂时。
7. **预处理指令的限制**：预处理指令不能访问局部变量，因为它们在宏展开阶段之前处理。
