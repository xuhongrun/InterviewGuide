## C风格的字符串（字符数组）

C风格的字符串（字符数组）是C语言中表示字符串的一种方式，在C++中也可以使用。

- C风格的字符串实际上就是一个以 **`\0`**（空字符）结尾的字符数组。
- 字符数组的每个元素都是一个字符，最后一个元素是 `\0`，表示字符串的结束。
- C风格的字符串不记录字符串的长度，所有的字符串操作函数都依赖于`\0`来判断字符串的结束。

### 声明和初始化

```cpp
char str1[] = "Hello, World!";
char str2[20] = "Hello, World!";
char str3[] = {'H', 'e', 'l', 'l', 'o', ',', ' ', 'W', 'o', 'r', 'l', 'd', '!', '\0'};
```

### 操作函数

C风格的字符串操作函数在`<cstring>`头文件中，常用的函数包括：

- `strcpy`: 复制字符串
- `strcat`: 追加字符串
- `strcmp`: 比较字符串
- `strlen`: 获取字符串长度
- `strchr`: 查找字符在字符串中的位置
- `strstr`: 查找子字符串在字符串中的位置
- `strtok`: 分割字符串

```cpp
#include <iostream>
#include <cstring>

int main() {
    char str1[] = "Hello, World!";
    char str2[20];

    // 复制字符串
    strcpy(str2, str1);
    std::cout << str2 << std::endl;

    // 追加字符串
    strcat(str2, " C++");
    std::cout << str2 << std::endl;

    // 比较字符串
    if (strcmp(str1, str2) == 0) {
        std::cout << "str1 and str2 are equal" << std::endl;
    } else {
        std::cout << "str1 and str2 are not equal" << std::endl;
    }

    // 获取字符串长度
    int len = strlen(str1);
    std::cout << "Length of str1: " << len << std::endl;

    return 0;
}
```

> - C风格的字符串操作函数不检查缓冲区溢出，因此使用时需要注意字符串的长度。
> - C风格的字符串操作函数依赖于`\0`来判断字符串的结束，因此不能包含`\0`字符的字符串。
> - C风格的字符串操作函数不支持 Unicode 字符串。

## 2. `std::string`类

`std::string` 类是C++标准库中提供的字符串类，用于表示和操作字符串。

### 构造函数

- `std::string()`: 默认构造函数，创建一个空字符串。
- `std::string(const char*)`: 从C风格的字符串创建一个`std::string`对象。
- `std::string(const std::string&)`: 复制构造函数，从另一个`std::string`对象创建一个新的`std::string`对象。
- `std::string(size_t, char)`: 创建一个指定长度的字符串，并用指定的字符填充。

### 操作函数

- `operator=`: 赋值运算符，复制一个字符串。
- `operator+`: 加法运算符，追加一个字符串。
- `operator==`: 等于运算符，比较两个字符串。
- `operator!=`: 不等于运算符，比较两个字符串。
- `size()`: 获取字符串的长度。
- `length()`: 获取字符串的长度。
- `empty()`: 判断字符串是否为空。
- `clear()`: 清空字符串。
- `substr()`: 提取子字符串。
- `find()`: 查找子字符串。
- `replace()`: 替换子字符串。
- `insert()`: 插入子字符串。
- `erase()`: 删除子字符串。

```cpp
#include <iostream>
#include <string>

int main() {
    std::string str1 = "Hello, World!";
    std::string str2 = "C++";

    // 复制字符串
    std::string str3 = str1;
    std::cout << str3 << std::endl;

    // 追加字符串
    str1 += str2;
    std::cout << str1 << std::endl;

    // 比较字符串
    if (str1 == str3) {
        std::cout << "str1 and str3 are equal" << std::endl;
    } else {
        std::cout << "str1 and str3 are not equal" << std::endl;
    }

    // 获取字符串长度
    int len = str1.length();
    std::cout << "Length of str1: " << len << std::endl;

    // 提取子字符串
    std::string substr = str1.substr(7, 5);
    std::cout << substr << std::endl;

    return 0;
}
```

> - `std::string`类的操作函数会自动处理缓冲区溢出等问题。
> - `std::string`类的操作函数会自动处理 Unicode 字符串。
> - `std::string`类的操作函数可能会抛出异常，需要使用 try-catch 语句捕获异常。

## 3. `std::wstring`类

`std::wstring` 类是C++标准库中提供的**宽字符**字符串类，用于表示和操作宽字符字符串。

> 宽字符 与 窄字符
> | 类别 | 宽字符 | 窄字符 |
> | --- | --- | --- |
> | 定义 | 占用多个字节（2 个或 4 个）表示一个字符 | 占用一个字节表示一个字符 |
> | 特点 | 可以表示 Unicode 字符，支持多语言 | 只能表示 ASCII 字符，仅支持英文 |
> | 区别 | 字符集不同，占用空间不同，表示能力不同 | 字符集不同，占用空间不同，表示能力不同 |
> | 编码方式 | UTF-16、UTF-32、UCS-2 等 | ASCII、ISO-8859-1 等 |
> | 优点 | 可以表示更多字符，支持多语言，包括中文、日文、韩文等非拉丁字符。 | 节省存储空间，简单易用 |
> | 缺点 | 占用更多存储空间，处理复杂 | 仅支持有限字符，不支持多语言 |
> | 使用场景 | 需要表示多语言字符的场景，例如 Unicode 环境、需要表示非拉丁字符 | 只需要表示英文字符的场景，例如 ASCII 环境 |
### 特点

- `std::wstring`类是**动态**的，可以根据需要自动调整字符串的长度。
- `std::wstring`类提供了许多方便的操作函数，包括字符串的复制、追加、比较、查找等。
- `std::wstring`类支持宽字符字符串，包括 **Unicode** 字符串。
- `std::wstring`类提供了许多安全的操作函数，避免缓冲区溢出等问题。

### 构造函数

`std::wstring`类提供了以下构造函数：

- `std::wstring()`: 默认构造函数，创建一个空字符串。
- `std::wstring(const wchar_t*)`: 从宽字符C风格的字符串创建一个`std::wstring`对象。
- `std::wstring(const std::wstring&)`: 复制构造函数，从另一个`std::wstring`对象创建一个新的`std::wstring`对象。
- `std::wstring(size_t, wchar_t)`: 创建一个指定长度的字符串，并用指定的宽字符填充。

### 操作函数

`std::wstring`类提供了以下操作函数：

- `operator=`: 赋值运算符，复制一个字符串。
- `operator+`: 加法运算符，追加一个字符串。
- `operator==`: 等于运算符，比较两个字符串。
- `operator!=`: 不等于运算符，比较两个字符串。
- `size()`: 获取字符串的长度。
- `length()`: 获取字符串的长度。
- `empty()`: 判断字符串是否为空。
- `clear()`: 清空字符串。
- `substr()`: 提取子字符串。
- `find()`: 查找子字符串。
- `replace()`: 替换子字符串。
- `insert()`: 插入子字符串。
- `erase()`: 删除子字符串。

```cpp
#include <iostream>
#include <string>

int main() {
    std::wstring wstr1 = L"Hello, World!";
    std::wstring wstr2 = L"C++";

    // 复制字符串
    std::wstring wstr3 = wstr1;
    std::wcout << wstr3 << std::endl;

    // 追加字符串
    wstr1 += wstr2;
    std::wcout << wstr1 << std::endl;

    // 比较字符串
    if (wstr1 == wstr3) {
        std::wcout << L"wstr1 and wstr3 are equal" << std::endl;
    } else {
        std::wcout << L"wstr1 and wstr3 are not equal" << std::endl;
    }

    // 获取字符串长度
    int len = wstr1.length();
    std::wcout << L"Length of wstr1: " << len << std::endl;

    // 提取子字符串
    std::wstring wsubstr = wstr1.substr(7, 5);
    std::wcout << wsubstr << std::endl;

    return 0;
}
```

> - `std::wstring`类的操作函数会自动处理缓冲区溢出等问题。
> - `std::wstring`类的操作函数会自动处理 Unicode 字符串。
> - `std::wstring`类的操作函数可能会抛出异常，需要使用 try-catch 语句捕获异常。
> - `std::wstring`类的字符串需要使用**宽字符常量**，例如 `L"Hello, World!"`。

## 相互转换

### 1. char* 与 char[] 之间的转换

- char* 转换为 char[]：可以直接赋值。

    ```cpp
    char* str = "Hello, World!";
    char arr[20];
    strcpy(arr, str);
    ```

- char[] 转换为 char*：可以直接赋值。

    ```cpp
    char arr[20] = "Hello, World!";
    char* str = arr;
    ```

### 2. char* 与 std::string 之间的转换

- char* 转换为 std::string：可以使用 std::string 的构造函数。

    ```cpp
    char* str = "Hello, World!";
    std::string s(str);
    ```

- std::string 转换为 char*：可以使用 std::string 的 c_str() 函数。

    ```cpp
    std::string s = "Hello, World!";
    char* str = s.c_str();
    ```

### 3. char[] 与 std::string 之间的转换

- char[] 转换为 std::string：可以使用 std::string 的构造函数。

    ```cpp
    char arr[20] = "Hello, World!";
    std::string s(arr);
    ```

- std::string 转换为 char[]：可以使用 std::string 的 copy() 函数。

    ```cpp
    std::string s = "Hello, World!";
    char arr[20];
    s.copy(arr, 20);
    ```

### 4. std::wstring 与 std::string 之间的转换

- std::wstring 转换为 std::string：可以使用 std::wstring_convert 类。

    ```cpp
    std::wstring ws = L"Hello, World!";
    std::wstring_convert<std::codecvt_utf8<wchar_t>, wchar_t> converter;
    std::string s = converter.to_bytes(ws);
    ```

- std::string 转换为 std::wstring：可以使用 std::wstring_convert 类。

    ```cpp
    std::string s = "Hello, World!";
    std::wstring_convert<std::codecvt_utf8<wchar_t>, wchar_t> converter;
    std::wstring ws = converter.from_bytes(s);
    ```

### 5. char* 与 std::wstring 之间的转换

- char* 转换为 std::wstring：可以先将 char* 转换为 std::string，然后再将 std::string 转换为 std::wstring。

    ```cpp
    char* str = "Hello, World!";
    std::string s(str);
    std::wstring_convert<std::codecvt_utf8<wchar_t>, wchar_t> converter;
    std::wstring ws = converter.from_bytes(s);
    ```

- std::wstring 转换为 char*：可以先将 std::wstring 转换为 std::string，然后再将 std::string 转换为 char*。

    ```cpp
    std::wstring ws = L"Hello, World!";
    std::wstring_convert<std::codecvt_utf8<wchar_t>, wchar_t> converter;
    std::string s = converter.to_bytes(ws);
    char* str = s.c_str();
    ```

### 6. char[] 与 std::wstring 之间的转换

- char[] 转换为 std::wstring：可以先将 char[] 转换为 std::string，然后再将 std::string 转换为 std::wstring。

    ```cpp
    char arr[20] = "Hello, World!";
    std::string s(arr);
    std::wstring_convert<std::codecvt_utf8<wchar_t>, wchar_t> converter;
    std::wstring ws = converter.from_bytes(s);
    ```

- std::wstring 转换为 char[]：可以先将 std::wstring 转换为 std::string，然后再将 std::string 转换为 char[]。

    ```cpp
    std::wstring ws = L"Hello, World!";
    std::wstring_convert<std::codecvt_utf8<wchar_t>, wchar_t> converter;
    std::string s = converter.to_bytes(ws);
    char arr[20];
    s.copy(arr, 20);
    ```
