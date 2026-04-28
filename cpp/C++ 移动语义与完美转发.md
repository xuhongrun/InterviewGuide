# C++ 移动语义与完美转发

> 现代 C++（11+）三大基石之一：**右值引用 / 移动语义 / 完美转发**。

---

## 1. 值类别（Value Category）

C++11 起把表达式分为 5 类，常用 3 类：

| 类别 | 含义 | 例子 |
|------|------|------|
| **lvalue** | 有名字、有地址 | `int x; x; arr[0];` |
| **prvalue** | 纯右值（临时） | `42; x+1; std::string("hi")` |
| **xvalue** | 即将过期值（要被搬走） | `std::move(x); f().member` |
| glvalue | lvalue ∪ xvalue（**有标识**） | |
| **rvalue** | prvalue ∪ xvalue（**可被移动**） | |

口诀：**有名字的左值，临时的右值，被 `move` 的也是右值（xvalue）**。

---

## 2. 右值引用 `T&&`

```cpp
int  a = 10;
int& l = a;        // ✅ 左值引用 → 左值
int& m = 10;       // ❌ 左值引用不能绑右值（除非 const）
const int& n = 10; // ✅ const 左值引用可延长临时寿命

int&& r = 10;      // ✅ 右值引用绑右值
int&& s = a;       // ❌ 右值引用不能绑左值
int&& t = std::move(a); // ✅ move 把左值转成右值
```

**关键点**：`r` 本身是个左值（有名字），里面绑的是右值。这就是为什么函数内继续传递时还要 `std::move(r)` 或 `std::forward<T>(r)`。

---

## 3. 移动语义

### 3.1 为什么要移动

```cpp
std::vector<std::string> v;
std::string s(1'000'000, 'x');
v.push_back(s);           // 拷贝：复制 1MB
v.push_back(std::move(s));// 移动：偷指针，O(1)；s 进入有效但未指定状态
```

* **拷贝**：分配新资源 + 内容复制（深拷贝）。
* **移动**：转移资源所有权（指针 / 句柄），原对象置空（valid but unspecified）。

### 3.2 移动构造 / 移动赋值

```cpp
class Buffer {
    char* data_ = nullptr;
    size_t n_ = 0;
public:
    Buffer(size_t n) : data_(new char[n]), n_(n) {}
    ~Buffer() { delete[] data_; }

    // 拷贝
    Buffer(const Buffer& o) : data_(new char[o.n_]), n_(o.n_) {
        std::copy(o.data_, o.data_ + n_, data_);
    }
    Buffer& operator=(const Buffer& o) {
        if (this != &o) { Buffer tmp(o); swap(tmp); } return *this;
    }
    // 移动（noexcept ⚠️）
    Buffer(Buffer&& o) noexcept : data_(o.data_), n_(o.n_) {
        o.data_ = nullptr; o.n_ = 0;
    }
    Buffer& operator=(Buffer&& o) noexcept {
        if (this != &o) { delete[] data_; data_=o.data_; n_=o.n_; o.data_=nullptr; o.n_=0; }
        return *this;
    }
    void swap(Buffer& o) noexcept { std::swap(data_,o.data_); std::swap(n_,o.n_); }
};
```

**`noexcept` 极其关键**：`std::vector` 在扩容时需要把元素搬到新内存，**只有 noexcept 的移动构造才会被使用**，否则退化为拷贝（性能崩盘）。

### 3.3 Rule of 0 / 3 / 5

* **Rule of 0**：能用标准库容器和智能指针就别自己写五大件。
* **Rule of 3**：写了析构 / 拷构 / 拷赋之一就要全写。
* **Rule of 5**：C++11 起还要加移动构造 / 移动赋值。

```cpp
class Widget {
public:
    Widget() = default;
    ~Widget();                                 // 1
    Widget(const Widget&);                     // 2
    Widget& operator=(const Widget&);          // 3
    Widget(Widget&&) noexcept;                 // 4
    Widget& operator=(Widget&&) noexcept;      // 5
};
```

### 3.4 编译器自动生成规则

| 你定义了… | 自动生成 |
|-----------|---------|
| 任何析构 / 拷贝 / 拷赋 | **不再生成移动** |
| 任何移动 | **拷贝被声明为 deleted** |
| 都没定义 | 五大件全自动 |

**坑**：写了析构 → 移动失效 → vector 退化拷贝。要么不写析构，要么 `= default` 五大件。

### 3.5 `std::move` 是什么？

```cpp
template<typename T>
constexpr std::remove_reference_t<T>&& move(T&& t) noexcept {
    return static_cast<std::remove_reference_t<T>&&>(t);
}
```

**只是个 cast**！不会真的移动，调用对应的移动构造 / 赋值才会发生搬运。

---

## 4. 完美转发 (Perfect Forwarding)

### 4.1 问题

写一个工厂：

```cpp
template<typename T, typename Arg>
T make(Arg arg) { return T(arg); }       // 总是拷贝，性能差
```

希望传左值就拷贝，传右值就移动 → 需要把"原本的值类别"完整传给 `T` 的构造。

### 4.2 转发引用（万能引用）

**`T&&` 在模板类型推导时不是右值引用，而是"转发引用"**：

```cpp
template<typename T>
void wrap(T&& x) {            // 转发引用
    // T = int&  时，T&& 折叠成 int&
    // T = int   时，T&& 是 int&&
}
```

**引用折叠规则**：`& & = &`、`& && = &`、`&& & = &`、`&& && = &&`。

### 4.3 `std::forward`

```cpp
template<typename T, typename... Args>
std::unique_ptr<T> make_unique(Args&&... args) {
    return std::unique_ptr<T>(new T(std::forward<Args>(args)...));
}
```

* `std::forward<T>(x)`：当 `T` 是左值引用 → 返回左值；否则 → 返回右值。**保留原值类别**。
* `std::move`：**无条件**转右值，用于"我确定要搬走"。
* 区分场景：传递参数用 `forward`，本函数最后一次使用且要搬走用 `move`。

### 4.4 何时是真转发引用，何时只是右值引用？

```cpp
template<typename T>
void f(T&& x);           // 转发引用 ✅（T 由调用推导）

template<typename T>
void g(std::vector<T>&& x);  // 右值引用 ❌（不是裸 T&&）

void h(int&& x);         // 右值引用 ❌（不是模板）

template<typename T>
struct C {
    void m(T&& x);       // 右值引用 ❌（T 在类已固定）
};
```

**只有"裸 T&&，且 T 由该函数模板推导"才是转发引用**。

---

## 5. 经典误用与陷阱

### 5.1 在 return 时用 `std::move(局部变量)` 反而抑制 NRVO

```cpp
std::string make() {
    std::string s = compute();
    return s;             // ✅ NRVO，零拷贝零移动
    // return std::move(s); // ❌ 抑制 NRVO，多一次移动
}
```

C++17 起强制省略（mandatory copy elision）针对 prvalue；但具名局部仍可被 NRVO，加 `move` 反而坏事。

### 5.2 `move` const 对象 = 拷贝

```cpp
const std::string s = "hi";
std::string t = std::move(s);  // 编译过，但走拷贝构造（const 不能搬）
```

### 5.3 在多次使用的对象上 `move`

```cpp
auto x = produce();
sink(std::move(x));
use(x);                   // ❌ x 已被搬走，未指定状态
```

### 5.4 转发到模板函数后又 `move`

```cpp
template<typename T>
void f(T&& x) {
    g(std::forward<T>(x));   // ✅
    h(std::move(x));         // ❌ 之后还想用 x 就崩
}
```

### 5.5 `auto&&` 与 `decltype(auto)`

```cpp
auto&& x = f();          // 万能引用：左值绑左值引用，右值绑右值引用
                          // 范围 for 中 for (auto&& e : range) 是通用写法
```

### 5.6 把容器元素 `move` 出循环

```cpp
for (auto& s : vec) sink(std::move(s));  // ✅ 元素状态变 unspecified
// 之后不能再依赖 vec 内容
```

---

## 6. 小例子：emplace vs push_back

```cpp
struct Big { Big(int, std::string); };
std::vector<Big> v;

v.push_back(Big(1, "x"));            // 构造临时 + 移动入容器
v.push_back({1, "x"});                // 同上
v.emplace_back(1, "x");               // 直接在容器内构造，零临时
```

`emplace_back` 通过完美转发把构造参数原样转给元素构造函数。

---

## 7. 何时声明 `noexcept`？

* 移动构造 / 移动赋值 / swap / 析构 → **强烈建议 noexcept**（`vector` 扩容、`std::sort` 等会基于此优化）。
* 不会抛的简单操作可以加。
* **不要为了"以防万一"乱加**：抛出会 `std::terminate`。

```cpp
class X {
    X(X&&) noexcept = default;
    X& operator=(X&&) noexcept = default;
    void swap(X&) noexcept;
};
```

---

## 8. 高频面试题

1. 左值 / 右值 / xvalue / prvalue 区别？举例。
2. `T&&` 在什么情况下是右值引用，什么情况下是转发引用？
3. `std::move` 做了什么？运行时有开销吗？
4. `std::move` vs `std::forward` 区别？
5. 为什么移动构造要写 `noexcept`？
6. Rule of 5；写了析构会发生什么？
7. NRVO 是什么？为什么 `return std::move(local)` 反而坏？
8. `emplace_back` vs `push_back` 区别？
9. const 对象能被 move 吗？
10. 移动后的对象能用吗？什么状态？
11. 自实现一个 `make_unique` 模板。
12. 转发引用为什么用引用折叠？折叠规则是什么？

---

## 9. Top 12 Checklist

1. ☐ 资源型类写齐五大件（或 `= default` 全部）。
2. ☐ 移动构造 / 赋值 / swap 加 `noexcept`。
3. ☐ 函数模板形参用 `T&&` + `std::forward<T>` 实现完美转发。
4. ☐ `std::move` 仅用于"最后一次使用且要搬走"。
5. ☐ 不在 return 上 `std::move` 局部对象（保 NRVO）。
6. ☐ 不要 `std::move` const 对象（无效果，编译过但仍拷贝）。
7. ☐ 容器优先 `emplace_back` / `emplace`。
8. ☐ 范围 for 用 `auto&&` 兼容 proxy 容器（`vector<bool>`）。
9. ☐ 自定义 swap 用 ADL：`using std::swap; swap(a,b);`。
10. ☐ 移动后只对对象做析构 / 重新赋值 / `clear()` 等"无前置条件"操作。
11. ☐ 调用方知情成本：传值 + 调用方 `move` 是常见现代风格。
12. ☐ 善用 `std::exchange(p, nullptr)` 简化移动实现。

---

## 面试速记

1. **`T&&` 看上下文**：模板推导是转发引用，否则是右值引用。
2. **std::move 是 cast**，不真搬运。
3. **std::forward 保留值类别**，配合转发引用使用。
4. **noexcept 移动** 才能让 vector 扩容走移动而非拷贝。
5. **Rule of 5**：写一个就要写五个（或 `= default` / `= delete` 显式声明）。
6. **NRVO 优先**，别画蛇添足 `std::move(局部变量)`。
7. **emplace_back** 通过完美转发零临时构造。
8. **引用折叠**：`& && = &`、`&& && = &&`。
9. **移动后状态** valid but unspecified，可析构 / 赋值 / clear。
10. **const T&&** 几乎没意义，删函数重载偶尔用。
11. **auto&& + forward** = 通用包装器经典套路。
12. **transparent move-from**：只用 `std::exchange` 清旧成员。

---

## 关联阅读

* [C++ 简介](C++%20简介.md) · [C++ 模板](C++%20模板.md) · [C++ 类（Class）](C++%20类（Class）.md)
* [C++ 内存管理](C++%20内存管理.md) · [C++ 指针、智能指针、引用](C++%20指针、智能指针、引用.md)
* [C++ 最佳实践](C++%20最佳实践.md)
