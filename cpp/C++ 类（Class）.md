## C++ 类（class）
C++中的类（Class）是一种用户定义的数据类型，它封装了数据（成员变量）和操作这些数据的函数（成员函数）。类可以被看作是创建对象的蓝图，它定义了对象的属性和行为。
### 访问修饰符

在C++中，访问修饰符用于控制类成员（包括变量和函数）的**可见性**和**可访问性**。

主要有三种访问修饰符：`public`、`protected`和`private`。
| 访问修饰符 | 定义 | 特点 | 说明 | 访问级别 |
| --- | --- | :--- | --- | --- |
| `public`<br>（公有） | 类成员可以被任何代码访问。 | - 成员对所有用户都是可见的<br>- 类的公共接口<br>- 继承时，基类的`public`成员在派生类中仍然是`public` | 用于类的接口部分，允许外部代码直接访问。 | 类内外均可访问 |
| `protected`<br>（受保护） | 类成员可以被类本身和其派生类访问。 | - 成员对类本身和派生类可见<br>- 继承时，基类的`protected`成员在派生类中仍然是`protected` | 用于类和派生类之间的接口，保护成员不被类的外部代码访问。 | 类内外及子类均可访问 |
| `private`<br>（私有） | 类成员只能被类本身访问。 | - 成员对类本身可见<br>- 继承时，基类的`private`成员在派生类中不可见 | 用于类的内部实现，完全封装，不允许外部代码访问。 | 仅限类内访问 |

- `public`、`protected`和`private`是C++中的三个访问修饰符，它们控制着类成员的可见性和可访问性。
- `public`成员是类的公共接口，可以被任何代码访问，包括类的实例和外部代码。
- `protected`成员是类和其派生类的接口，只能被类本身和其派生类访问。
- `private`成员是类的内部实现细节，只能被类本身访问，完全封装，不允许外部代码访问。
- 在继承中，基类的`public`和`protected`成员会传递给派生类，而`private`成员则不会传递，派生类无法访问基类的`private`成员。
- 访问修饰符是实现**封装和数据隐藏**的重要机制，有助于保护数据的完整性和安全性。

```cpp
#include <iostream>
#include <string>

// 声明一个类Person
class Person {
    // 私有成员变量，只能在类的内部访问
private:
    std::string name;

    // 受保护成员变量，可以在类的内部以及派生类中访问
protected:
    int age;

    // 公有成员变量，可以在任何地方访问
public:
    double height;

    // 私有成员函数，只能在类的内部调用
private:
    void privateFunction() {
        std::cout << "Private function called" << std::endl;
    }

    // 受保护成员函数，可以在类的内部以及派生类中调用
protected:
    void protectedFunction() {
        std::cout << "Protected function called" << std::endl;
    }

    // 公有成员函数，可以在任何地方调用
public:
    void publicFunction() {
        std::cout << "Public function called" << std::endl;
    }

    // 构造函数
public:
    Person(const std::string& nm, int ag, double ht) : name(nm), age(ag), height(ht) {}

    // 公有成员函数，用于外部访问私有成员变量
    std::string getName() const {
        return name;
    }

    // 公有成员函数，用于外部调用私有成员函数
    void callPrivateFunction() {
        privateFunction();
    }
};

// 派生类
class Employee : public Person {
public:
    Employee(const std::string& nm, int ag, double ht) : Person(nm, ag, ht) {}

    // 可以访问基类的受保护成员
    void printAge() {
        std::cout << "Age: " << age << std::endl;
    }

    // 可以调用基类的受保护成员函数
    void printProtectedFunction() {
        protectedFunction();
    }
};

int main() {
    // 创建Employee对象
    Employee emp("John Doe", 30, 175.5);

    // 访问公有成员函数和变量
    emp.publicFunction();
    std::cout << "Height: " << emp.height << std::endl;

    // 通过公有接口访问私有成员变量和私有成员函数
    std::cout << "Name: " << emp.getName() << std::endl;
    emp.callPrivateFunction();

    // 访问受保护成员变量和函数（通过派生类）
    emp.printAge();
    emp.printProtectedFunction();

    return 0;
}
```
`Person`类有三个访问修饰符定义的成员变量和成员函数，分别展示了`private`、`protected`和`public`访问级别。`Employee`类继承自`Person`类，并可以访问`Person`类的`protected`成员。
- `private`成员变量`name`和成员函数`privateFunction`只能在`Person`类内部访问。
- `protected`成员变量`age`和成员函数`protectedFunction`可以在`Person`类及其派生类`Employee`中访问。
- `public`成员变量`height`和成员函数`publicFunction`可以在任何地方访问。

`main`函数中创建了一个`Employee`对象，并展示了如何访问不同访问级别的成员。通过`Employee`对象，我们可以访问`Person`类的公有成员和受保护成员，但不能直接访问私有成员。私有成员只能通过`Person`类提供的公有接口（如`getName`和`callPrivateFunction`）来访问。

### 成员变量
在C++中，类的成员变量是定义在类内部的变量，它们代表了类的状态。

| 变量类型 | 定义 | 作用 | 访问级别 | 初始化 | 线程安全 |
| --- | --- | --- | --- | --- | --- |
| 非静态成员变量   | 类中定义的变量，每个对象实例都有一份拷贝。 | 存储对象的状态信息。 | public/private/protected | 默认初始化/在构造函数中初始化/列表初始化 | 否 |
| 静态成员变量 | 类中定义的静态变量，所有对象实例共享同一份拷贝。 | 存储类级别的共享状态信息。 | public/private | 在类外初始化/静态成员初始化器 | 否（需要外部同步） |
| 常量成员变量 | 使用`const`或`constexpr`修饰的成员变量。 | 提供类级别的常量值，不可修改。 | public/private/protected | 必须在声明时初始化或在成员初始化列表中初始化 | 是 |
| 互斥锁成员变量 | 类中定义的互斥锁，如`std::mutex`。 | 用于同步对共享资源的访问，保证同一时间只有一个线程可以访问资源。 | public/private | 默认构造/在构造函数中显式初始化 | 是（正确使用时） |
| 条件变量 | 类中定义的条件变量，如`std::condition_variable`。 | 用于线程间的协调，使线程在特定条件满足之前挂起。 | public/private | 默认构造/在构造函数中显式初始化 | 是（正确使用时） |
| 原子变量 | 使用 C++11 中的原子类型定义的变量，如`std::atomic`。 | 提供无锁的线程安全操作，如原子读写。 | public/private | 默认构造/在构造函数中显式初始化 | 是 |
| 线程局部存储变量 | 使用 `thread_local` 定义的变量，每个线程有自己的独立拷贝。 | 存储线程特定的数据，避免线程间的数据竞争。 | public/private | 默认初始化/在声明时初始化 | 是 |

- **非静态成员变量**：每个对象实例都有自己的拷贝，因此它们不是线程安全的，除非通过外部同步机制来保护。
- **静态成员变量**：所有对象共享同一份拷贝，因此它们也不是线程安全的，除非通过外部同步机制来保护。
- **常量成员变量**：由于它们是不可变的，因此是线程安全的。
- **互斥锁成员变量**：虽然`std::mutex`本身是线程安全的，但需要正确使用（例如避免死锁）来保证线程安全。
- **条件变量**：`std::condition_variable`是线程安全的，但需要与互斥锁结合使用，并正确管理条件变量的唤醒和等待。
- **原子变量**：`std::atomic`类型提供了基本的线程安全操作，适用于简单的同步需求。
- **线程局部存储变量**：`thread_local`变量是线程安全的，因为每个线程都有自己的独立拷贝。

### 成员函数
在C++中，类的成员函数是定义在类内部的函数，它们可以访问类的私有和保护成员。

成员函数定义了类的行为。成员函数可以操作类的成员变量，并且可以被声明为`public`、`protected`或`private`，以控制它们的访问级别。

| 成员函数类型 | 定义 | 作用 | 特点 | 访问级别 | 使用场景 | 示例 |
| --- | --- | --- | --- | --- | --- | --- |
| 构造函数 | 对象创建时调用的函数，用于初始化对象。 | 初始化新创建的对象。 | - 与类同名<br>- 没有返回类型<br>- 可以有参数<br>- 不能是虚函数 | public | 对象创建时需要初始化成员变量时 | `Date::Date(int y, int m, int d) : year(y), month(m), day(d) {}` |
| 析构函数 | 对象销毁时调用的函数，用于清理资源。 | 释放对象占用的资源。 | - 与类同名，前面加上`~`<br>- 没有返回类型<br>- 不能被声明为`const`或`volatile` | public | 对象销毁时需要释放资源，如动态内存时 | `Date::~Date() { delete[] year; }` |
| 拷贝构造函数 | 用于创建一个对象作为另一个对象的副本的函数。 | 创建一个对象作为另一个对象的副本。 | - 带有一个常量引用参数<br>- 可以被用于参数传递和返回值优化 | public/private | 需要深拷贝对象时，或编译器生成的浅拷贝不满足需求时 | `Date::Date(const Date& other) : year(other.year) {}` |
| 拷贝赋值运算符 | 将一个对象的内容赋值给另一个对象的函数。 | 将一个对象的内容赋值给另一个对象。 | - 返回类型为引用<br>- 带有一个常量引用参数<br>- 需要处理自赋值 | public/private | 需要自定义赋值逻辑，或编译器生成的浅拷贝不满足需求时 | `Date& Date::operator=(const Date& other) { /* ... */ return *this; }` |
| 移动构造函数 | 用于创建一个对象，将其作为另一个对象的移动来源的函数。 | 创建一个对象作为另一个对象的移动来源，转移资源所有权。 | - 带有一个右值引用参数<br>- C++11引入 | public/private | 需要移动语义，如转移资源所有权，而不是复制资源时 | `Date::Date(Date&& other) : year(std::move(other.year)) {}` |
| 移动赋值运算符 | 将一个对象的内容移动赋值给另一个对象的函数。 | 将一个对象的内容移动赋值给另一个对象，转移资源所有权。 | - 返回类型为引用<br>- 带有一个右值引用参数<br>- C++11引入 | public/private | 需要移动语义，如转移资源所有权，而不是复制资源时 | `Date& Date::operator=(Date&& other) { /* ... */ return *this; }` |
| 虚函数 | 允许在派生类中被重写的函数。 | 实现多态性，允许派生类提供特定的实现。 | - 被声明为`virtual`<br>- 可以在派生类中被重写为`override` | public/protected | 需要基类和派生类之间存在多态行为时 | `virtual void draw() { /* ... */ }` |
| 纯虚函数 | 强制派生类必须提供具体实现的虚函数。 | 使包含它的类成为抽象类，强制派生类提供实现。 | - 被声明为`virtual`且后面跟`= 0`<br>- 使类成为抽象类 | public/protected | 需要定义接口，但由派生类提供具体实现时 | `virtual void pureVirtual() = 0;` |
| 常量成员函数 | 不修改任何成员变量的成员函数。 | 提供对对象的只读操作。 | - 被声明为`const`<br>- 可以被常量对象调用 | public/protected | 需要对对象进行只读操作，而不改变对象状态时 | `int getValue() const { return value; }` |
| 静态成员函数 | 不依赖于类的特定对象实例的成员函数。 | 提供与类相关但不需要对象实例的操作。 | - 使用`static`关键字声明<br>- 可以通过类名直接调用 | public/protected | 需要定义与类相关，但与特定对象实例无关的函数时 | `static int add(int a, int b) { return a + b; }` |
| 友元函数 | 被赋予访问类的私有和保护成员权限的非成员函数。 | 提供对类私有成员的访问。 | - 使用`friend`关键字声明<br>- 可以是非成员函数或另一个类的成员函数 | 不适用 | 需要非成员函数访问类的私有或保护成员时 | `friend void display(const MyClass&);` |
| 内联函数 | 在编译时被插入到每个调用点的函数。 | 提高性能，减少函数调用的开销。 | - 使用`inline`关键字声明<br>- 通常用于小型函数 | public/protected | 对于小型函数，希望编译器优化为内联调用时 | `inline int add(int a, int b) { return a + b; }` |

- 成员函数的访问级别（public/protected/private）决定了它们可以在类的哪个范围内被访问。
- 构造函数和析构函数是特殊的成员函数，它们在对象的生命周期开始和结束时自动被调用。
- 拷贝构造函数和拷贝赋值运算符用于对象的拷贝操作，移动构造函数和移动赋值运算符用于对象的移动操作。
- 虚函数和纯虚函数是实现多态性的关键，它们允许基类通过指针或引用调用派生类的函数。
- 静态成员函数和友元函数是特殊的成员函数，它们不依赖于对象实例，因此没有初始化列表和初始化顺序的概念。

> 在C++中，如果类没有显式定义某些成员函数，编译器会根据需要自动生成默认成员函数。这些默认成员函数包括：
>
> 1. **默认构造函数**（Default Constructor）：
>    如果类没有定义任何构造函数，编译器会生成一个默认构造函数。这个函数不接受任何参数，并默认初始化成员变量（对于基本数据类型成员变量，通常是零初始化）。
>
> 2. **默认析构函数**（Default Destructor）：
>    如果类没有定义析构函数，编译器会生成一个默认析构函数。这个函数不执行任何操作，除非类有基类或成员对象需要析构。
>
> 3. **默认拷贝构造函数**（Default Copy Constructor）：
>    如果类没有定义拷贝构造函数，并且没有成员函数被声明为`const`、`volatile`，没有虚函数，没有`mutable`成员，没有基类的自定义拷贝构造函数，编译器会生成一个默认拷贝构造函数。这个函数会逐个成员地拷贝对象。
>
> 4. **默认拷贝赋值运算符**（Default Copy Assignment Operator）：
>    如果类没有定义拷贝赋值运算符，并且没有成员函数被声明为`const`、`volatile`，没有虚函数，没有`mutable`成员，没有基类的自定义拷贝赋值运算符，编译器会生成一个默认拷贝赋值运算符。这个运算符会逐个成员地赋值对象。
>
> 5. **默认移动构造函数**（Default Move Constructor）：
>    C++11及以后版本，如果类没有定义移动构造函数，并且没有成员函数被声明为`const`或`volatile`，没有虚函数，没有`mutable`成员，没有基类的自定义移动构造函数，编译器会生成一个默认移动构造函数。这个函数会逐个成员地移动对象。
>
> 6. **默认移动赋值运算符**（Default Move Assignment Operator）：
>    C++11及以后版本，如果类没有定义移动赋值运算符，并且没有成员函数被声明为`const`或`volatile`，没有虚函数，没有`mutable`成员，没有基类的自定义移动赋值运算符，编译器会生成一个默认移动赋值运算符。这个运算符会逐个成员地移动赋值对象。
>
> ```cpp
> #include <iostream>
> 
> class SimpleClass {
> public:
>     int x;
>     double y;
> 
>     // 默认构造函数
>     SimpleClass() = default;
> 
>     // 默认析构函数
>     ~SimpleClass() = default;
> 
>     // 默认拷贝构造函数
>     SimpleClass(const SimpleClass& other) = default;
> 
>     // 默认拷贝赋值运算符
>     SimpleClass& operator=(const SimpleClass& other) = default;
> 
>     // 默认移动构造函数
>     SimpleClass(SimpleClass&& other) = default;
> 
>     // 默认移动赋值运算符
>     SimpleClass& operator=(SimpleClass&& other) = default;
> };
> 
> int main() {
>     SimpleClass obj1; // 使用默认构造函数
>     SimpleClass obj2 = obj1; // 使用默认拷贝构造函数
>     SimpleClass obj3(std::move(obj1)); // 使用默认移动构造函数
>     obj2 = obj3; // 使用默认拷贝赋值运算符
>     obj3 = std::move(obj2); // 使用默认移动赋值运算符
> 
>     return 0;
> }
> ```
>
> `SimpleClass`显式地声明了所有默认成员函数，并使用`default`关键字告诉编译器生成默认实现。即使没有显式声明这些函数，编译器也会为这个类自动生成它们。




## C++ 中 class 与 struct

| | class | struct |
| --- | --- | --- |
| **定义方式** | 使用`class`关键字定义<br />`class 类名 { ... };` | 使用`struct`关键字定义<br />`struct 结构名 { ... };` |
| **默认访问权限** | 私有（private） | 公共（public） |
| **继承方式** | 私有继承（private inheritance） | 公共继承（public inheritance） |
| **构造函数和析构函数** | 可以有构造函数和析构函数 | 可以有构造函数和析构函数 |
| **成员变量和成员函数** | 可以有成员变量和成员函数 | 可以有成员变量和成员函数 |
| **成员变量和成员函数的默认访问权限** | 私有（private） | 公共（public） |
| **运算符重载** | 可以重载运算符 | 可以重载运算符 |
| **模板** | 可以作为模板参数 | 可以作为模板参数 |
| **异常处理** | 可以使用异常处理 | 可以使用异常处理 |
> 在C++中，`struct`和`class`的区别主要在于默认访问权限和继承方式。除此之外，它们的功能和用法基本相同。
- class 和 struct 都可以用来定义自定义数据类型。
- class 的默认访问权限是私有（private），而 struct 的默认访问权限是公共（public）。
- class 的继承方式是私有继承（private inheritance），而 struct 的继承方式是公共继承（public inheritance）。
- class 和 struct 都可以有成员变量和成员函数，构造函数和析构函数，运算符重载，模板和异常处理。

### 选择使用类还是struct

- 如果需要定义一个具有私有成员变量和成员函数的类型，应该使用类。
- 如果需要定义一个具有公共成员变量和成员函数的类型，应该使用struct。
- 如果需要定义一个具有私有继承的类型，应该使用类。
- 如果需要定义一个具有公共继承的类型，应该使用struct。
