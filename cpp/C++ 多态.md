# C++ 多态

C++中的多态性是一种允许不同类的对象对同一消息做出响应的编程技术。多态性使得同一个函数或方法在不同的对象中可以有不同的行为。

在C++中，多态性主要通过以下几种方式实现：

## 静态多态（编译时多态）
#### 函数重载（Function Overloading）
同一个作用域内，函数名相同，但参数列表不同（参数类型、参数个数或参数顺序）。这种机制允许程序员使用同一个函数名来执行不同的操作，具体执行哪个函数取决于传递给函数的参数。
- 函数名必须相同。
- 参数列表必须不同（参数的类型、数量或顺序）。
- 返回类型可以不同，但仅返回类型的不同不足以构成重载。
- 函数重载是编译时决定的，因此也称为静态多态。

```cpp
#include <iostream>
#include <string>

class Printer {
public:
    // 重载print函数，用于打印整数
    void print(int value) {
        std::cout << "Integer: " << value << std::endl;
    }

    // 重载print函数，用于打印浮点数
    void print(double value) {
        std::cout << "Double: " << value << std::endl;
    }

    // 重载print函数，用于打印字符串
    void print(const std::string& value) {
        std::cout << "String: " << value << std::endl;
    }
};

int main() {
    Printer p;
    p.print(42);        // 调用print(int)
    p.print(3.14159);   // 调用print(double)
    p.print("Hello");  // 调用print(const std::string&)
    return 0;
}
```
`Printer`类有三个`print`函数，每个函数接受不同类型的参数。当调用`print`函数时，编译器会根据传递的参数类型来决定调用哪个函数版本。

#### 运算符重载（Operator Overloading）

为已有的运算符提供新的操作功能，使其可以作用于用户自定义的数据类型。运算符重载允许程序员定义操作符对于自定义类型的操作，使得代码更加直观和易于理解。
- 除了`::`（作用域解析运算符）、`.`（成员访问运算符）、`.*`（成员指针访问运算符）和`?:`（条件运算符）之外，大多数运算符都可以被重载。
- 运算符重载可以通过成员函数或非成员函数实现。
- 运算符重载不能改变运算符的优先级和结合性。
- 运算符重载通常需要考虑操作数的类型，以确定是左值还是右值。

```cpp
#include <iostream>

class Complex {
public:
    Complex(double r, double i) : real(r), imag(i) {}

    // 重载加法运算符
    Complex operator+(const Complex& other) const {
        return Complex(real + other.real, imag + other.imag);
    }

    void display() const {
        std::cout << "(" << real << ", " << imag << "i)" << std::endl;
    }

private:
    double real, imag;
};

int main() {
    Complex c1(1.0, 2.0), c2(3.0, 4.0), c3;
    c3 = c1 + c2;  // 使用重载的+运算符
    std::cout << "c1 + c2 = ";
    c3.display();  // 显示结果
    return 0;
}
```
`Complex`类重载了`+`运算符，使得两个`Complex`对象可以直接使用`+`运算符进行加法操作。`operator+`函数返回一个新的`Complex`对象，其实部和虚部分别是两个操作数实部和虚部的和。

## 动态多态（运行时多态）
#### 虚函数（Virtual Functions）

虚函数是基类中声明为`virtual`的函数，允许在派生类中被重写（override）。当通过基类的指针或引用调用虚函数时，会根据对象的实际类型来决定调用哪个函数，这个过程称为动态绑定或晚期绑定。

- 基类中声明虚函数使用`virtual`关键字。
- 派生类中重写基类的虚函数，不需要`virtual`关键字，但可以使用`override`关键字来明确表示该函数是重写基类中的虚函数。
- 必须通过基类的指针或引用来调用虚函数，才能实现动态多态。
- 需要一个虚函数表（vtable）和虚函数指针（vptr）来支持动态绑定。

```cpp
#include <iostream>

class Base {
public:
    virtual void show() {  // 虚函数
        std::cout << "Base class show()" << std::endl;
    }
    virtual ~Base() {}  // 虚析构函数，确保派生类对象的正确析构
};

class Derived : public Base {
public:
    void show() override {  // 重写基类的虚函数
        std::cout << "Derived class show()" << std::endl;
    }
};

int main() {
    Base* b = new Derived();  // 基类指针指向派生类对象
    b->show();  // 调用Derived的show()，体现动态多态
    delete b;
    return 0;
}
```

`Base`类有一个虚函数`show()`，`Derived`类重写了这个函数。在`main()`函数中，通过`Base`类型的指针调用`show()`函数时，实际调用的是`Derived`类的`show()`函数，这就是动态多态的体现。

#### 抽象类（Abstract Classes）

抽象类是包含至少一个纯虚函数（pure virtual function）的类，纯虚函数使用`= 0`定义。抽象类不能被直接实例化，通常用作接口。

- 包含纯虚函数的类称为抽象类。
- 抽象类不能被直接实例化，但可以作为基类来使用。
- 派生类必须重写抽象类中的所有纯虚函数，才能被实例化。

```cpp
#include <iostream>

class AbstractClass {
public:
    virtual void pureVirtualFunction() = 0;  // 纯虚函数
};

class ConcreteClass : public AbstractClass {
public:
    void pureVirtualFunction() override {  // 必须重写纯虚函数
        std::cout << "ConcreteClass::pureVirtualFunction()" << std::endl;
    }
};

int main() {
    ConcreteClass c;
    c.pureVirtualFunction();  // 调用重写的纯虚函数
    return 0;
}
```

`AbstractClass`是一个抽象类，包含一个纯虚函数`pureVirtualFunction()`。`ConcreteClass`继承自`AbstractClass`并重写了纯虚函数。由于`AbstractClass`是抽象类，不能直接实例化，但可以作为基类来使用。

## 重载 与 重写
| 特性 | 重载（Overloading） | 重写（Overriding） |
| --- | --- | --- |
| **定义** | 在同一个作用域内，函数名相同但参数列表不同（类型、个数或顺序）的函数 | 在派生类中，重新定义基类中的虚函数 |
| **目的** | 允许函数根据输入参数的不同执行不同的操作 | 允许派生类改变基类虚函数的行为 |
| **函数名** | 必须相同 | 必须相同 |
| **参数列表** | 必须不同 | 必须相同 |
| **返回类型** | 可以不同 | 必须相同 |
| **访问权限** | 可以不同 | 不能更低 |
| **虚函数** | 不需要 | 需要 |
| **多态性** | 静态多态（编译时多态） | 动态多态（运行时多态）                                       |
| **例子** | `void func(int); void func(double);` | `class Base { virtual void func() {} }; class Derived : public Base { void func() override; };` |

>  重载和重写都是C++中实现多态的方式，但它们在语法和行为上有着明显的区别。
>  - 重载主要解决的是函数名相同但参数不同的问题，而重写则是在继承体系中改变函数的行为。
>  - 重载在编译时就已经确定调用哪个函数，而重写则在运行时根据对象的实际类型来决定调用哪个函数。
