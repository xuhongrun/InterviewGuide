## C++ 结构体（struct）
在C++编程语言中，结构体（`struct`）是一种强大的数据结构，它允许我们将不同类型的数据项组合成一个单一的类型。本文将深入探讨C++中结构体的相关知识点，并提供实际应用示例。

## 结构体的定义与特性

结构体是一种用户自定义的数据类型，它允许我们将多个变量组合在一起，这些变量可以是不同的数据类型。
结构体的定义通常如下所示：

```cpp
struct StructName {
    DataType1 member1;
    DataType2 member2;
    // ...
};
```

在C++中，结构体与类（`class`）非常相似，主要区别在于默认的访问权限：结构体的成员默认是`public`，而类的成员默认是`private`。

## 结构体的实例化与访问

结构体可以通过以下方式进行实例化：

```cpp
StructName instanceName;
```

或者在声明时直接初始化：

```cpp
StructName instanceName = {value1, value2};
```

访问结构体成员可以通过点（`.`）操作符：

```cpp
instanceName.member1 = someValue;
DataType2 temp = instanceName.member2;
```

## 结构体与函数

结构体可以作为函数的参数传递，也可以作为函数的返回值。这使得结构体成为处理复杂数据的有力工具。

### 作为参数传递

```cpp
void function(StructName param) {
    // 操作param
}
```

### 作为返回值

```cpp
StructName function() {
    StructName result;
    // 初始化result
    return result;
}
```

## 结构体与数组

结构体可以作为数组的元素，这使得我们可以创建同类型数据项的集合。

```cpp
StructName array[10];
```

## 指针与结构体

结构体指针允许我们访问和操作结构体变量的地址。这对于动态内存分配和复杂的数据操作非常有用。

```cpp
StructName* ptr = &instanceName;
```

## 结构体的应用示例

### 简单的数据封装

```cpp
#include <iostream>
using namespace std;

struct Point {
    int x, y;
};

int main() {
    Point p = {1, 2};
    cout << "Point coordinates: (" << p.x << ", " << p.y << ")" << endl;
    return 0;
}
```

### 复杂数据结构

```cpp
#include <iostream>
using namespace std;

struct Book {
    string title;
    string author;
    int year;
};

int main() {
    Book library[3] = {
        {"The Great Gatsby", "F. Scott Fitzgerald", 1925},
        {"1984", "George Orwell", 1949},
        {"To Kill a Mockingbird", "Harper Lee", 1960}
    };

    for (int i = 0; i < 3; ++i) {
        cout << "Title: " << library[i].title
             << ", Author: " << library[i].author
             << ", Year: " << library[i].year << endl;
    }
    return 0;
}
```
## C++ Struct 的优点
**代码组织性更好**：C++ Struct 可以将相关的变量和函数组合在一起，提高代码的组织性和可读性。
**数据封装**：C++ Struct 可以将数据封装在结构体中，提高数据的安全性和可靠性。
**代码复用**：C++ Struct 可以定义结构体函数，提高代码的复用性。
## C++ Struct 的常见应用
**数据库**：C++ Struct 可以用于定义数据库中的表结构和记录结构。
**文件操作**：C++ Struct 可以用于定义文件中的数据结构和格式。
**网络通信**：C++ Struct 可以用于定义网络通信中的数据包结构和格式。
**游戏开发**：C++ Struct 可以用于定义游戏中的角色、物品和场景结构。

## C/C++中的struct
| 特性 | C语言中的struct | C++语言中的struct |
| --- | --- | --- |
| 默认访问权限 | public（成员默认为公开） | private（成员默认为私有） |
| 包含函数/方法 | 不支持 | 支持（可以包含成员函数） |
| 继承 | 不支持 | 支持（可以继承自其他struct或class） |
| 构造函数和析构函数 | 不支持 | 支持（可以定义构造函数和析构函数） |
| 内存对齐 | 由编译器决定，不可控制 | 可以通过`#pragma pack`控制 |
| 匿名结构体 | 支持 | 不支持 |
| 模板 | 不支持 | 支持（可以创建模板struct） |
| 联合体和枚举 | 支持 | 支持（C++还支持`enum class`） |

> ``struct`` 和 ``typedef struct`` 联系与区别
> | | struct | typedef struct |
> | --- | --- | --- |
> | 定义方式 | 定义一个结构体 | 为一个结构体定义一个新的名称 |
> | 使用方式 | 必须使用 struct 关键字来引用该结构体 | 可以直接使用新的名称来引用该结构体 |
> | 类型名 | ``struct XXX`` | `XXX` |
> | 例子 | ``struct Person { int age; char name[20]; };`` | ``typedef struct { int age; char name[20]; } Person;`` |
> | 优点 | 清晰地定义了结构体的类型 | 使代码更简洁易读 |
> | 缺点 | 每次引用结构体时都需要使用 struct 关键字 | 可能会导致类型名冲突 |
> 1. struct 用于定义一个结构体。
> 2. typedef struct 用于为一个结构体定义一个新的名称。
> 3. struct 和 typedef struct 都可以用来定义结构体，但 typedef struct 更常用，因为它可以使代码更简洁易读。
> 4. 当使用 struct 定义结构体时，必须使用 struct 关键字来引用该结构体，而当使用 typedef struct 定义结构体时，可以直接使用新的名称来引用该结构体。
