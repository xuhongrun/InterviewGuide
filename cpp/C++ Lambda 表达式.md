在现代编程中，匿名函数（Anonymous Functions）或称为 lambda 表达式，已经成为一种非常流行的编程构造。它们允许开发者在不定义传统函数的情况下创建函数。

C++11 引入了对 Lambda 表达式的原生支持，极大地丰富了语言的表达能力和灵活性。

## Lambda 表达式

Lambda 表达式是一种没有名称的函数对象，它允许你在需要函数的地方快速定义函数行为。Lambda 表达式通常用于**简短**、**一次性**的函数，或者当你需要一个函数对象来传递给算法时。

## Lambda 表达式 语法

C++ 中的 lambda 表达式由以下部分组成：

```cpp
[capture](parameters) -> return-type { function-body }
```

- **capture（捕获子句）**：可选，定义了 Lambda 可以访问哪些外部变量。可以按值（`=`）或按引用（`&`）捕获，也可以通过列表（例如，`&var1, var2`）捕获特定的变量。
- **parameters（参数列表）**：Lambda 接受的参数列表，与普通函数的参数列表类似。
- **return-type（返回类型）**：Lambda 的返回类型。如果 Lambda 包含单一的 `return` 语句或没有 `return` 语句，编译器可以自动推断返回类型。
- **function-body（函数体）**：Lambda 执行的代码块，类似于普通函数的函数体。

## Lambda 表达式 示例

### 基本用法

```cpp
auto add = [](int a, int b) { return a + b; };
std::cout << add(2, 3) << std::endl;  // 输出 5
```

### 捕获外部变量

```cpp
int value = 10;
auto addValue = [value](int x) { return x + value; };
std::cout << "Result is " << addValue(5) << std::endl; // 输出 15
```

### 按引用捕获

```cpp
int value = 10;
auto lambda = [&value] { value += 5; };
lambda();
std::cout << value << std::endl;  // 输出 15
```

### 捕获并修改外部变量

```cpp
int a = 1, b = 2;
auto lambda = [a, &b] { a += 3; b += 4; return a + b; };
std::cout << lambda() << std::endl;  // 输出 10
```

### 捕获所有外部变量
可以使用 `&` 捕获所有外部变量，或者使用 `=` 捕获所有变量的副本。
```cpp
int a = 1, b = 2;
auto lambda = [&] { return a + b; };
std::cout << lambda() << std::endl;  // 输出 3
```

### 与 STL 算法结合使用

```cpp
std::vector<int> vec = {1, 2, 3, 4, 5};
auto it = std::find_if(vec.begin(), vec.end(), [](int i) { return i > 3; });
if (it != vec.end()) {
    std::cout << *it << std::endl;  // 输出 4
}
```

### 使用默认参数

```cpp
auto add = [](int a, int b = 2) { return a + b; };
std::cout << add(2) << std::endl;  // 输出 4
```

### 泛型编程

Lambda 表达式在 STL 算法中非常有用，例如 `std::for_each`：

```cpp
#include <algorithm>
#include <vector>
#include <iostream>

int main() {
    std::vector<int> data = {1, 2, 3, 4, 5};
    std::for_each(data.begin(), data.end(), [](int x) { std::cout << x << ' '; });
    std::cout << std::endl;
    return 0;
}
```
### 可变 Lambda 表达式

如果需要在 lambda 表达式中修改捕获的变量，可以使用 `mutable` 关键字。

```cpp
auto increment = [x = 0]() mutable { return ++x; };
std::cout << increment() << ' ' << increment() << std::endl; // 输出 1 2
```

### Lambda 表达式与智能指针

Lambda 表达式可以与智能指针一起使用，以管理动态分配的资源。

```cpp
#include <memory>
#include <iostream>

int main() {
    auto deleter = [](int* p) { delete p; };
    std::unique_ptr<int> ptr(new int(10), deleter);
    std::cout << *ptr << std::endl; // 输出 10
    return 0;
}
```


Lambda 表达式是 C++ 中一个非常强大的特性，它提供了一种简洁的方式来定义和使用匿名函数。它们在**泛型编程、事件处理和异步编程**中尤其有用。
Lambda 表达式不仅仅是一种语法糖，它们是 C++ 语言进化的一部分，使得代码更加简洁和表达力强。
