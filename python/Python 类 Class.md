在 Python 中，类（Class）是一种创建对象（Object）的模板，它允许我们定义对象的属性和方法。类是 Python 中实现面向对象编程（OOP）的核心结构。

### 定义一个类

定义一个类的基本语法如下：

```python
class ClassName:
    def __init__(self, parameters):
        # 这里是初始化方法，相当于构造函数
        self.attribute = value
```

- `ClassName`：类名，通常采用首字母大写的驼峰命名法。
- `__init__`：类的初始化方法，当创建类的新实例时会自动调用。它的第一个参数总是 `self`，代表类的实例本身。

### 类属性和实例属性

- **类属性**：由类的所有实例共享。
- **实例属性**：每个类实例都有自己的独立拷贝。

```python
class MyClass:
    class_attribute = 100  # 类属性

    def __init__(self, instance_attribute):
        self.instance_attribute = instance_attribute  # 实例属性
```

### 类方法和实例方法

- **实例方法**：方法的第一个参数是 `self`，表示类的实例。
- **类方法**：使用 `@classmethod` 装饰器，第一个参数是 `cls`，表示类本身。

```python
class MyClass:
    def instance_method(self):
        pass

    @classmethod
    def class_method(cls):
        pass
```

### 静态方法

使用 `@staticmethod` 装饰器定义静态方法，静态方法不需要 `self` 或 `cls` 参数。

```python
class MyClass:
    @staticmethod
    def static_method():
        pass
```

### 创建类的实例

```python
my_object = MyClass('some value')
```

### 访问属性和方法

```python
# 访问实例属性
print(my_object.instance_attribute)

# 访问实例方法
my_object.instance_method()

# 访问类属性
print(MyClass.class_attribute)

# 访问类方法
MyClass.class_method()

# 访问静态方法
MyClass.static_method()
```

### 继承

Python 支持单一继承和多重继承。

```python
class BaseClass:
    pass

class DerivedClass(BaseClass):
    pass
```

### 多态

多态允许不同的对象对同一消息做出响应。

```python
class BaseClass:
    def method(self):
        pass

class DerivedClass(BaseClass):
    def method(self):
        pass

base = BaseClass()
derived = DerivedClass()

# 多态行为
base.method()  # 调用 BaseClass 的 method
derived.method()  # 调用 DerivedClass 的 method
```

### 封装

封装是将数据（属性）和代码（方法）捆绑在一起，并对外部隐藏内部实现的细节。

```python
class MyClass:
    def __init__(self, value):
        self.__private_attribute = value  # 私有属性

    @property
    def private_attribute(self):
        return self.__private_attribute

    @private_attribute.setter
    def private_attribute(self, value):
        self.__private_attribute = value
```

### 特殊方法

Python 类可以定义一些特殊方法来响应 Python 执行的操作。
> 官方文档：[Python Special method](https://docs.python.org/3/reference/datamodel.html#special-method-names)

| 方法名称 | 用途 | 示例 |
| --- | --- | --- |
| `__init__(self, ...)` | 构造器，创建实例时初始化对象。 | `def __init__(self, name): self.name = name` |
| `__del__(self)` | 析构器，释放对象时调用。 | `def __del__(self): print("Object destroyed")` |
| `__str__(self)` | 定义对象的可打印字符串表示，`print()` 时调用。 | `def __str__(self): return "Instance of MyClass"` |
| `__repr__(self)` | 定义对象的官方字符串表示，用于调试。 | `def __repr__(self): return "MyClass(name='John')"` |
| `__len__(self)` | 定义 `len()` 函数返回的对象大小。 | `def __len__(self): return len(self.items)` |
| `__getitem__(self, key)` | 定义获取对象元素的行为，如 `obj[key]`。 | `def __getitem__(self, key): return self.items[key]` |
| `__setitem__(self, key, value)` | 定义设置对象元素的行为，如 `obj[key] = value`。 | `def __setitem__(self, key, value): self.items[key] = value` |
| `__delitem__(self, key)` | 定义删除对象元素的行为，如 `del obj[key]`。 | `def __delitem__(self, key): del self.items[key]` |
| `__iter__(self)` | 定义对象迭代器，用于 `for` 循环。 | `def __iter__(self): return iter(self.items)` |
| `__next__(self)` | 定义迭代器的下一个元素，用于 `for` 循环。 | `def __next__(self): return next(self.items)` |
| `__call__(self, ...)` | 定义对象作为函数被调用时的行为。 | `def __call__(self): print("Hello")` |
| `__eq__(self, other)` | 定义等于运算符 `==` 的行为。 | `def __eq__(self, other): return self.name == other.name` |
| `__ne__(self, other)` | 定义不等于运算符 `!=` 的行为。 | `def __ne__(self, other): return self.name != other.name` |
| `__lt__(self, other)` | 定义小于运算符 `<` 的行为。 | `def __lt__(self, other): return self.value < other.value` |
| `__le__(self, other)` | 定义小于等于运算符 `<=` 的行为。 | `def __le__(self, other): return self.value <= other.value` |
| `__gt__(self, other)` | 定义大于运算符 `>` 的行为。 | `def __gt__(self, other): return self.value > other.value` |
| `__ge__(self, other)` | 定义大于等于运算符 `>=` 的行为。 | `def __ge__(self, other): return self.value >= other.value` |
| `__getattr__(self, name)` | 定义访问不存在属性时的行为。 | `def __getattr__(self, name): return f"{name} not found"` |
| `__setattr__(self, name, value)` | 定义设置属性时的行为。 | `def __setattr__(self, name, value): self.__dict__[name] = value` |
| `__getattribute__(self, name)` | 定义获取属性时的行为。 | `def __getattribute__(self, name): return object.__getattribute__(self, name)` |
| `__dir__(self)` | 定义 `dir()` 函数返回的属性列表。 | `def __dir__(self): return ["name", "age"]` |

使用这些特殊方法，你可以自定义类的字符串表示、布尔值、长度等行为。

### `self`和`cls`
在Python中，`self`和`cls`是用于类方法中的特殊参数，它们分别用于实例方法和类方法中。

| 特性 | `self` | `cls` |
| --- | --- | --- |
| **用途** | 指向类的实例本身 | 指向类本身 |
| **方法类型** | 实例方法 | 类方法 |
| **访问范围** | 实例属性和实例方法 | 类属性和类方法 |
| **定义方式** | 不需要装饰器 | 使用`@classmethod`装饰器 |
| **示例** | `def method(self):` | `@classmethod def method(cls):` |
| **使用场景** | 需要访问或修改实例的属性和方法时 | 需要访问或修改类的属性和方法时 |
| **初始化** | 在实例化对象时自动传递 | 在调用类方法时自动传递 |

#### 实例方法
```python
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age

    def greet(self):
        print(f"Hello, my name is {self.name} and I am {self.age} years old.")

# 创建实例
person = Person("Alice", 30)
person.greet()  # 输出: Hello, my name is Alice and I am 30 years old.
```
#### 类方法
```python
class Person:
    count = 0  # 类属性

    def __init__(self, name):
        self.name = name
        Person.count += 1

    @classmethod
    def get_count(cls):
        return cls.count

# 创建实例
person1 = Person("Alice")
person2 = Person("Bob")

print(Person.get_count())  # 输出: 2
```
