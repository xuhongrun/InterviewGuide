## 数据类型

| 数据类型 | 32位系统 | 64位系统 |
| --- | --- | --- |
| bool | 1字节 | 1字节 |
| | true 或 false | true 或 false |
| char | 1字节 | 1字节 |
| | -128 到 127 | -128 到 127 |
| unsigned char | 1字节 | 1字节 |
| | 0 到 255 | 0 到 255 |
| short | 2字节 | 2字节 |
| | -32768 到 32767 | -32768 到 32767 |
| unsigned short | 2字节 | 2字节 |
| | 0 到 65535 | 0 到 65535 |
| int | 4字节 | 4字节 |
| | -2147483648 到 2147483647 | -2147483648 到 2147483647 |
| unsigned int | 4字节 | 4字节 |
| | 0 到 4294967295 | 0 到 4294967295 |
| long | 4字节 | 8字节 |
| | -2147483648 到 2147483647 | -9223372036854775808 到 9223372036854775807 |
| unsigned long | 4字节 | 8字节 |
| | 0 到 4294967295 | 0 到 18446744073709551615 |
| long long | 8字节 | 8字节 |
| | -9223372036854775808 到 9223372036854775807 | -9223372036854775808 到 9223372036854775807 |
| unsigned long long | 8字节 | 8字节 |
| | 0 到 18446744073709551615 | 0 到 18446744073709551615 |
| float | 4字节 | 4字节 |
| | 1.4e-45 到 3.4e+38 | 1.4e-45 到 3.4e+38 |
| double | 8字节 | 8字节 |
| | 4.9e-324 到 1.8e+308 | 4.9e-324 到 1.8e+308 |
| long double | 12字节 | 16字节 |
| | 3.4e-4932 到 1.2e+4932 | 3.4e-4932 到 1.2e+4932 |
| void* | 4字节 | 8字节 |
| | - | - |

## 数据类型转换

C++ 类型转换是指将一个类型的值转换为另一个类型的值。C++ 提供了多种类型转换的方法，包括隐式转换和显式转换。

### 隐式转换

隐式转换是指编译器自动进行的类型转换。这种转换发生在表达式中，当一个类型的值被赋给另一个类型的变量时，或者当一个类型的值被用于另一个类型的运算时。

```cpp
int x = 5;
double y = x;  // 隐式转换：int -> double
```

### 显式转换

显式转换是指使用特定的语法进行类型转换。这种转换可以使用 `static_cast`、`dynamic_cast`、`const_cast` 和 `reinterpret_cast` 等运算符。

#### `static_cast`

`static_cast` 用于**静态类型转换**。它可以将一个类型的值转换为另一个类型的值，但不进行运行时检查。

**语法**

```cpp
static_cast<目标类型>(表达式)
```

**特点**

1. **静态类型转换**：`static_cast` 只能用于静态类型转换，即在编译时就能确定类型转换的结果。
2. **不进行运行时检查**：`static_cast` 不进行运行时检查，即不检查转换后的类型是否正确。
3. **可以转换指针和引用**：`static_cast` 可以转换指针和引用类型。

**使用场景**

1. **类型转换**：当需要将一个类型的值转换为另一个类型的值时，使用 `static_cast`。
2. **指针转换**：当需要将一个指针类型的值转换为另一个指针类型的值时，使用 `static_cast`。
3. **引用转换**：当需要将一个引用类型的值转换为另一个引用类型的值时，使用 `static_cast`。

```cpp
// 类型转换
int x = 5;
double y = static_cast<double>(x);  // static_cast：int -> double

// 指针转换
int* p = new int;
void* q = static_cast<void*>(p);  // static_cast：int* -> void*

// 引用转换
int x = 5;
double& y = static_cast<double&>(x);  // static_cast：int -> double&
```

> **注意点**
>
> - **类型转换错误**：`static_cast` 可能会导致类型转换错误，需要检查转换后的类型是否正确。
> - **不进行运行时检查**：`static_cast` 不进行运行时检查，即不检查转换后的类型是否正确。
> 

#### `dynamic_cast`

`dynamic_cast` 用于动态类型转换。它可以将一个类型的值转换为另一个类型的值，并进行运行时检查。

**语法**

```cpp
dynamic_cast<目标类型>(表达式)
```

**特点**

1. **动态类型转换**：`dynamic_cast` 可以将一个类型的值转换为另一个类型的值，并进行运行时检查。
2. **运行时检查**：`dynamic_cast` 进行运行时检查，即检查转换后的类型是否正确。
3. **可以转换指针和引用**：`dynamic_cast` 可以转换指针和引用类型。
4. **需要虚函数表**：`dynamic_cast` 需要虚函数表来进行运行时检查。

**使用场景**

1. **类型转换**：当需要将一个类型的值转换为另一个类型的值，并进行运行时检查时，使用 `dynamic_cast`。
2. **指针转换**：当需要将一个指针类型的值转换为另一个指针类型的值，并进行运行时检查时，使用 `dynamic_cast`。
3. **引用转换**：当需要将一个引用类型的值转换为另一个引用类型的值，并进行运行时检查时，使用 `dynamic_cast`。

```cpp
// 类型转换
class Base {
public:
    virtual void foo() {}
};

class Derived : public Base {
public:
    void bar() {}
};

Base* p = new Derived();
Derived* q = dynamic_cast<Derived*>(p);  // dynamic_cast：Base* -> Derived*

// 指针转换
Base* p = new Derived();
void* q = dynamic_cast<void*>(p);  // dynamic_cast：Base* -> void*

// 引用转换
Base& r = *p;
Derived& s = dynamic_cast<Derived&>(r);  // dynamic_cast：Base& -> Derived&
```

> **注意点**
>
> - **类型转换错误**：`dynamic_cast` 可能会导致类型转换错误，需要检查转换后的类型是否正确。
> - **需要虚函数表**：`dynamic_cast` 需要虚函数表来进行运行时检查。
> - **性能损失**：`dynamic_cast` 可能会导致性能损失，因为它需要进行运行时检查。
>

#### **`const_cast`**

`const_cast` 用于去除常量性质。它可以将一个常量类型的值转换为一个非常量类型的值。

**语法**

```cpp
const_cast<目标类型>(表达式)
```

**特点**

1. **去除常量性质**：`const_cast` 可以去除一个常量类型的值的常量性质。
2. **不改变值**：`const_cast` 不改变值的内容，只是改变值的类型。
3. **可以转换指针和引用**：`const_cast` 可以转换指针和引用类型。

**使用场景**

1. **去除常量性质**：当需要去除一个常量类型的值的常量性质时，使用 `const_cast`。
2. **指针转换**：当需要将一个常量指针类型的值转换为一个非常量指针类型的值时，使用 `const_cast`。
3. **引用转换**：当需要将一个常量引用类型的值转换为一个非常量引用类型的值时，使用 `const_cast`。

```cpp
// 去除常量性质
const int x = 5;
int& y = const_cast<int&>(x);  // const_cast：const int -> int&

// 指针转换
const int* p = &x;
int* q = const_cast<int*>(p);  // const_cast：const int* -> int*

// 引用转换
const int& r = x;
int& s = const_cast<int&>(r);  // const_cast：const int& -> int&
```

> **注意点**
>
> - **类型转换错误**：`const_cast` 可能会导致类型转换错误，需要检查转换后的类型是否正确。
> - **不改变值**：`const_cast` 不改变值的内容，只是改变值的类型。
> - **可能导致未定义行为**：如果使用 `const_cast` 去除一个常量类型的值的常量性质，然后修改该值，可能会导致未定义行为。
>

#### `reinterpret_cast`

`reinterpret_cast` 用于重新解释类型。它可以将一个类型的值转换为另一个类型的值，但**不进行任何检查**。

**语法**

```cpp
reinterpret_cast<目标类型>(表达式)
```

**特点**

1. **重新解释类型**：`reinterpret_cast` 可以将一个类型的值转换为另一个类型的值，但不进行任何检查。
2. **不改变值**：`reinterpret_cast` 不改变值的内容，只是改变值的类型。
3. **可以转换指针和引用**：`reinterpret_cast` 可以转换指针和引用类型。

**使用场景**

1. **重新解释类型**：当需要将一个类型的值转换为另一个类型的值，但不需要进行任何检查时，使用 `reinterpret_cast`。
2. **指针转换**：当需要将一个指针类型的值转换为另一个指针类型的值，但不需要进行任何检查时，使用 `reinterpret_cast`。
3. **引用转换**：当需要将一个引用类型的值转换为另一个引用类型的值，但不需要进行任何检查时，使用 `reinterpret_cast`。

```cpp
// 重新解释类型
int x = 5;
char* p = reinterpret_cast<char*>(&x);  // reinterpret_cast：int* -> char*

// 指针转换
int* q = new int;
void* r = reinterpret_cast<void*>(q);  // reinterpret_cast：int* -> void*

// 引用转换
int& s = *q;
char& t = reinterpret_cast<char&>(s);  // reinterpret_cast：int& -> char&
```

> **注意点**
>
> - **类型转换错误**：`reinterpret_cast` 可能会导致类型转换错误，需要检查转换后的类型是否正确。
> - **不改变值**：`reinterpret_cast` 不改变值的内容，只是改变值的类型。
> - **可能导致未定义行为**：如果使用 `reinterpret_cast` 重新解释一个类型的值，但该值不符合目标类型的要求，可能会导致未定义行为。
>

#### 类型转换运算符 比较

| 运算符 | 描述 | 特点 | 使用场景 | 运行时检查 | 类型检查 | 值改变 | 类型转换 | 指针转换 | 引用转换 | 去除常量性质 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `static_cast` | 静态类型转换 | 不进行运行时检查 | 类型转换，指针转换，引用转换 | 否 | 否 | 否 | 是 | 是 | 是 | 否 |
| `dynamic_cast` | 动态类型转换 | 进行运行时检查 | 类型转换，指针转换，引用转换 | 是 | 是 | 否 | 是 | 是 | 是 | 否 |
| `const_cast` | 去除常量性质 | 不改变值 | 去除常量性质，指针转换，引用转换 | 否 | 否 | 否 | 否 | 是 | 是 | 是 |
| `reinterpret_cast` | 重新解释类型 | 不进行任何检查 | 重新解释类型，指针转换，引用转换 | 否 | 否 | 否 | 是 | 是 | 是 | 否 |
