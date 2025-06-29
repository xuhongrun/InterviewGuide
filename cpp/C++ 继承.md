# C++ 继承

C++ 中的继承是一种面向对象编程的特性，它允许一个类（称为派生类或子类）继承另一个类（称为基类或父类）的属性和方法。继承支持代码的重用，并允许创建一个层次结构的类。

#### 继承类型
- **公有继承（public）**：基类的公有成员和保护成员都会成为派生类的公有成员，私有成员仍然是私有的。
- **保护继承（protected）**：基类的公有成员和保护成员都会成为派生类的保护成员，私有成员仍然是私有的。
- **私有继承（private）**：基类的公有成员和保护成员都会成为派生类的私有成员，私有成员仍然是私有的。

#### 继承语法
```cpp
class 基类名 {
    // 成员声明
};

class 派生类名 : 继承方式 基类名 {
    // 成员声明
};
```

#### 多重继承
C++ 支持多重继承，即一个派生类可以继承多个基类。
```cpp
class A {
    // ...
};

class B {
    // ...
};

class C : public A, public B {
    // ...
};
```
`C` 类继承自 `A` 和 `B`

##### 访问控制
多重继承中的访问控制可能会变得复杂。如果多个基类中有同名成员，派生类需要明确指定使用哪个基类的成员，否则可能会产生二义性。
```cpp
class A {
public:
    int value;
};

class B {
public:
    int value;
};

class C : public A, public B {
public:
    int getValue() {
        return A::value; // 明确指定访问 A 的 value
    }
};
```

##### 构造函数和析构函数调用顺序
1. **构造函数的调用顺序**
    对于多重继承，构造函数的调用顺序是**按照在派生类继承列表中出现的顺序进行**的。这意味着，基类的构造函数会先于派生类的构造函数被调用，并且如果一个类继承自多个基类，那么这些基类的构造函数会按照它们在类声明中的顺序被调用。
2. **析构函数的调用顺序**
    **与构造函数相反，析构函数的调用顺序是逆序的**。这意味着，派生类的析构函数会先于基类的析构函数被调用。如果一个类继承自多个基类，那么这些基类的析构函数会按照它们在类声明中的逆序被调用。
3. **初始化列表**
    在多重继承中，派生类的构造函数可以使用成员初始化列表来显式调用基类的构造函数。这允许更精确地控制基类成员的初始化顺序。

#### 菱形继承
在C++中，菱形继承是一个涉及多重继承的复杂问题，它发生在一个类（我们称之为D）继承自两个类（B和C），而这两个类又都继承自同一个基类（A）时。这种结构在类继承图中形成一个菱形，因此得名。
##### 菱形继承主要带来两个问题：**数据冗余**和**二义性**。
- **数据冗余**：在没有使用虚继承的情况下，D类会从B和C类分别继承A类的成员，导致A类的成员在D类中出现两份拷贝。这不仅造成了数据的冗余，还可能导致数据不一致的问题。
- **二义性**：由于D类通过B和C类两条路径都可以访问到A类的成员，编译器在解析D类中对A类成员的访问时会面临二义性问题，即无法确定应该使用哪一条路径来访问A类的成员。
```cpp
class A {
    // ...
};

class B : public A {
    // ...
};

class C : public A {
    // ...
};

class D : public B, public C {
    // ...
};
```

##### 解决方案：虚继承
为了解决菱形继承的问题，C++提供了虚继承（virtual inheritance）的机制。

通过在中间派生类的继承声明中加上关键字`virtual`，可以将共同继承的基类标记为虚拟基类。这样，无论最终派生类通过多少条路径继承同一个基类，都会保证在最终派生类中只有一份该基类的实例，从而解决了数据冗余和二义性的问题。

#### 虚继承
C++中的虚继承（Virtual Inheritance）是一种特殊的多重继承机制，用于解决菱形继承问题。

在菱形继承中，一个派生类通过两条路径继承同一个基类，如果不使用虚继承，会导致基类的成员在派生类中出现多次，造成数据冗余和不一致。虚继承确保了无论一个类通过多少条路径继承同一个基类，都只有一个基类的实例。

在C++中，虚继承通过在继承列表中使用`virtual`关键字来实现。
```cpp
class A {
    // ...
};

class B : virtual public A {
    // ...
};

class C : virtual public A {
    // ...
};

class D : public B, public C {
    // ...
};
```

`B`和`C`都虚继承自`A`。这意味着`D`类将只包含一个`A`的实例，即使它通过`B`和`C`两条路径继承自`A`。

##### 虚继承访问

在虚继承的情况下，访问基类成员的方式略有不同。你需要使用作用域解析运算符`::`来明确指定访问的基类成员。例如：
```cpp
D d;
d.A::x;		// 访问A类中的成员x
```

##### 虚继承构造和析构

由于虚继承可能导致基类的构造和析构顺序变得复杂，因此在构造和析构`D`对象时，需要特别小心：
- **构造顺序**：基类`A`首先被构造，然后是`B`和`C`，最后是`D`。
- **析构顺序**：与构造顺序相反，`D`首先被析构，然后是`B`和`C`，最后是`A`。

##### 虚继承注意事项
1. **性能考虑**：虚继承可能会增加一些运行时开销，因为需要维护指向基类实例的额外指针。
2. **设计选择**：在设计类层次结构时，应仔细考虑是否需要虚继承，以及它对性能和设计的影响。
3. **多重路径访问**：由于虚继承解决了二义性问题，你可以通过任何路径安全地访问基类成员，而不需要担心数据不一致。

虚继承是C++中处理复杂继承关系的强大工具，它通过确保基类的唯一实例来解决多重继承中的一些常见问题。正确使用虚继承可以提高代码的健壮性和可维护性。
