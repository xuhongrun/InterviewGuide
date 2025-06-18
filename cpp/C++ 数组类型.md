## C++ 数组

**定义 C++ 数组**

C++ 数组可以使用以下语法定义：

```cpp
类型 名称[大小];
```

**初始化 C++ 数组**

C++ 数组可以使用以下语法初始化：

```cpp
类型 名称[大小] = {值1, 值2, ..., 值n};
```

**访问 C++ 数组元素**

C++ 数组元素可以使用以下语法访问：

```cpp
名称[索引]
```

**C++ 数组的特点**

- **固定大小**：C++ 数组的大小在定义时确定，不能动态改变。
- **连续存储**：C++ 数组的元素在内存中连续存储。
- **没有容器操作**：C++ 数组不支持容器操作，如 `size()`、`empty()` 等。
- **支持指针运算**：C++ 数组支持指针运算，如 `arr + 1` 等。

**C++ 数组的使用场景**

- **需要固定大小数组**：C++ 数组适用于需要固定大小数组的场景，如函数参数、结构体成员等。

- **需要高性能**：C++ 数组适用于需要高性能的场景，如游戏开发、科学计算等。

- **需要兼容 C 代码**：C++ 数组适用于需要兼容 C 代码的场景，如调用 C 函数等。

```cpp
// 定义一个名为 arr1 的整型数组，大小为 5。
int arr1[5];

// 定义一个名为 arr2 的整型数组，大小为 5，并且初始化了它的元素。
int arr2[5] = {1, 2, 3, 4, 5};

// 访问 arr3 数组的第一个元素。
int arr3[5] = {1, 2, 3, 4, 5};
int x = arr3[0];  // x = 1
```

## std::array

`std::array` 是 C++11 引入的数组容器。它提供了一个**固定大小**的数组，并且支持一些容器操作。

**定义 `std::array`**

`std::array` 可以使用以下语法定义：

```cpp
#include <array>

std::array<类型, 大小> 名称;
```

**初始化 `std::array`**

`std::array` 可以使用以下语法初始化：

```cpp
std::array<类型, 大小> 名称 = {{值1, 值2, ..., 值n}};
```

**访问 `std::array` 元素**

`std::array` 元素可以使用以下语法访问：

```cpp
名称[索引]
```

**`std::array` 的特点**

- **固定大小**：`std::array` 的大小在定义时确定，不能动态改变。
- **连续存储**：`std::array` 的元素在内存中连续存储。
- **支持容器操作**：`std::array` 支持一些容器操作，如 `size()`、`empty()` 等。
- **支持指针运算**：`std::array` 支持指针运算，如 `arr.data() + 1` 等。
- **支持迭代器**：`std::array` 支持迭代器，可以使用迭代器访问元素。
- **支持 const**：`std::array` 支持 const，可以定义 const 数组。
- **支持 noexcept**：`std::array` 支持 noexcept，可以定义 noexcept 数组。

**`std::array` 的成员函数**

- `size()`: 返回数组的大小。
- `empty()`: 返回数组是否为空。
- `data()`: 返回数组的底层指针。
- `at()`: 返回指定索引的元素。
- `operator[]`: 返回指定索引的元素。
- `front()`: 返回数组的第一个元素。
- `back()`: 返回数组的最后一个元素。
- `begin()`: 返回数组的开始迭代器。
- `end()`: 返回数组的结束迭代器。
- `rbegin()`: 返回数组的反向开始迭代器。
- `rend()`: 返回数组的反向结束迭代器。
- `cbegin()`: 返回数组的常量开始迭代器。
- `cend()`: 返回数组的常量结束迭代器。
- `crbegin()`: 返回数组的常量反向开始迭代器。
- `crend()`: 返回数组的常量反向结束迭代器。
- `fill()`: 用指定值填充整个数组。
- `swap()`: 交换两个数组的内容。

**`std::array` 的使用场景**

- **需要固定大小数组**：`std::array` 适用于需要固定大小数组的场景，如函数参数、结构体成员等。
- **需要支持容器操作**：`std::array` 适用于需要支持容器操作的场景，如需要使用 `size()`、`empty()` 等函数。
- **需要高性能**：`std::array` 适用于需要高性能的场景，如游戏开发、科学计算等。
- **需要安全性**：`std::array` 适用于需要安全性的场景，如需要防止缓冲区溢出等。
- **需要兼容性**：`std::array` 适用于需要兼容性的场景，如需要与 C 代码兼容等。

```cpp
#include <array>

// 定义一个名为 arr1 的整型数组，大小为 5。
std::array<int, 5> arr1;

// 定义一个名为 arr2 的整型数组，大小为 5，并且初始化了它的元素。
std::array<int, 5> arr2 = {{1, 2, 3, 4, 5}};

// 访问 arr3 数组的第一个元素
std::array<int, 5> arr3 = {{1, 2, 3, 4, 5}};
int x = arr3[0];  // x = 1
```

## std::vector

`std::vector` 是 C++ 中最常用的动态数组容器。它可以**动态地增加或减少元素**，并且支持大部分容器操作。

**定义 `std::vector`**

`std::vector` 可以使用以下语法定义：

```cpp
#include <vector>

std::vector<类型> 名称;
```

**初始化 `std::vector`**

`std::vector` 可以使用以下语法初始化：

```cpp
std::vector<类型> 名称 = {值1, 值2, ..., 值n};
```

**访问 `std::vector` 元素**

`std::vector` 元素可以使用以下语法访问：

```cpp
名称[索引]
```

**`std::vector` 的特点**

- **动态大小**：`std::vector` 的大小可以动态地增加或减少。
- **连续存储**：`std::vector` 的元素在内存中连续存储。
- **支持容器操作**：`std::vector` 支持大部分容器操作，如 `size()`、`empty()`、`push_back()`、`pop_back()` 等。
- **支持指针运算**：`std::vector` 支持指针运算，如 `vec.data() + 1` 等。

**`std::vector` 的成员函数**

- `size()`: 返回数组的大小。
- `empty()`: 返回数组是否为空。
- `data()`: 返回数组的底层指针。
- `at()`: 返回指定索引的元素。
- `operator[]`: 返回指定索引的元素。
- `push_back()`: 在数组末尾添加一个元素。
- `pop_back()`: 删除数组末尾的元素。
- `insert()`: 在指定位置插入一个元素。
- `erase()`: 删除指定位置的元素。
- `clear()`: 清空数组。

**`std::vector` 的使用场景**

- **需要动态大小数组**：`std::vector` 适用于需要动态大小数组的场景，如需要动态增加或减少元素。
- **需要支持容器操作**：`std::vector` 适用于需要支持容器操作的场景，如需要使用 `size()`、`empty()`、`push_back()`、`pop_back()` 等函数。
- **需要高性能**：`std::vector` 适用于需要高性能的场景，如游戏开发、科学计算等。

```cpp
#include <vector>

// 定义一个名为 vec1 的整型动态数组
std::vector<int> vec1;

// 定义一个名为 vec2 的整型动态数组，并且初始化了它的元素
std::vector<int> vec2 = {1, 2, 3, 4, 5};

// 访问 vec3 数组的第一个元素
std::vector<int> vec3 = {1, 2, 3, 4, 5};
int x = vec3[0];  // x = 1
```

## 区别及相互转换

| 特性 | C++ 数组 | std::array | std::vector |
| --- | --- | --- | --- |
| 大小 | 固定大小 | 固定大小 | 动态大小 |
| 存储 | 连续存储 | 连续存储 | 连续存储 |
| 容器操作 | 不支持 | 支持部分容器操作 | 支持大部分容器操作 |
| 指针运算 | 支持 | 支持 | 支持 |
| 安全性 | 不安全 | 安全 | 安全 |
| 兼容性 | 兼容 C 代码 | 兼容 C 代码 | 兼容 C 代码 |
| 性能 | 高性能 | 高性能 | 高性能 |
| 迭代器 | 不支持 | 支持 | 支持 |
| const | 支持 | 支持 | 支持 |
| noexcept | 支持 | 支持 | 支持 |
| 定义 | 类型 名称[大小]; | std::array<类型, 大小> 名称; | std::vector<类型> 名称; |
| 初始化 | 类型 名称[大小] = {值1, 值2, ...}; | std::array<类型, 大小> 名称 = {值1, 值2, ...}; | std::vector<类型> 名称 = {值1, 值2, ...}; |
| 访问 | 名称[索引] | 名称[索引] | 名称[索引] |
| 使用场景 | 需要固定大小数组、需要高性能 | 需要固定大小数组、需要支持容器操作 | 需要动态大小数组、需要支持容器操作 |

- C++ 数组转换为`std::array`：可以使用 `std::array `的构造函数来将C++ 数组转换为 `std::array`。
- C++ 数组转换为`std::vector`：可以使用 `std::vector` 的构造函数来将C++ 数组转换为 `std::vector`。
- `std::array` 转换为C++ 数组：可以使用 `std::array `的 `data()` 函数来将 `std::array` 转换为C++ 数组。
- `std::array` 转换为 `std::vector`：可以使用 `std::vector `的构造函数来将 `std::array `转换为 `std::vector`。
- `std::vector `转换为C++ 数组：可以使用 `std::vector` 的`data()`函数来将 `std::vector` 转换为C++ 数组。
- `std::vector` 转换为 `std::array`：不支持直接转换，但可以使用 `std::vector` 的 `data()`函数和 `std::array` 的构造函数来间接转换。

```cpp
// C++ 数组转换为std::array
int arr[] = {1, 2, 3, 4, 5};
std::array<int, 5> arr_std = std::array<int, 5>(arr, arr + 5);

// C++ 数组转换为std::vector
int arr[] = {1, 2, 3, 4, 5};
std::vector<int> vec(arr, arr + 5);

// std::array转换为C++ 数组
std::array<int, 5> arr_std = {1, 2, 3, 4, 5};
int* arr = arr_std.data();

// std::array转换为std::vector
std::array<int, 5> arr_std = {1, 2, 3, 4, 5};
std::vector<int> vec(arr_std.begin(), arr_std.end());

// std::vector转换为C++ 数组
std::vector<int> vec = {1, 2, 3, 4, 5};
int* arr = vec.data();

// std::vector转换为std::array
std::vector<int> vec = {1, 2, 3, 4, 5};
std::array<int, 5> arr_std = std::array<int, 5>(vec.data(), vec.data() + 5);
```
