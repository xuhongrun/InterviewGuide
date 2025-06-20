Python 提供了一些内置的装饰器，这些装饰器在日常编程中非常有用。

### 1. `@property`
`@property` 装饰器用于将类的方法转换为属性，允许你通过属性访问的方式调用方法，而不需要使用括号。通常用于实现 `getter` 方法。

```python
class Person:
    def __init__(self, name, age):
        self._name = name
        self._age = age

    @property
    def name(self):
        return self._name

    @property
    def age(self):
        return self._age

    @age.setter
    def age(self, value):
        if value < 0:
            raise ValueError("Age cannot be negative")
        self._age = value

person = Person("Alice", 30)
print(person.name)  # 输出: Alice
print(person.age)   # 输出: 30

person.age = 31
print(person.age)   # 输出: 31

# person.age = -1  # 会抛出 ValueError
```

### 2. `@classmethod`
`@classmethod` 装饰器用于定义类方法。类方法的第一个参数是类本身（通常命名为 `cls`），而不是实例（`self`）。类方法可以访问类属性和方法，但不能访问实例属性。

```python
class MyClass:
    count = 0

    def __init__(self):
        MyClass.count += 1

    @classmethod
    def get_count(cls):
        return cls.count

obj1 = MyClass()
obj2 = MyClass()
print(MyClass.get_count())  # 输出: 2
print(obj1.get_count())     # 输出: 2
```

### 3. `@staticmethod`
`@staticmethod` 装饰器用于定义**静态方法**。静态方法不接受类或实例作为第一个参数，它们可以像普通函数一样调用，但属于类的命名空间。

```python
class MyClass:
    @staticmethod
    def static_method(x, y):
        return x + y

print(MyClass.static_method(3, 5))  # 输出: 8
obj = MyClass()
print(obj.static_method(3, 5))      # 输出: 8
```

### 4. `@functools.lru_cache`
`@functools.lru_cache` 装饰器用于缓存函数的结果。这可以显著**提高函数的性能**，特别是对于**计算密集型**的函数。
缓存的大小可以通过 `maxsize` 参数指定。

```python
from functools import lru_cache

@lru_cache(maxsize=32)
def fibonacci(n):
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

print(fibonacci(10))  # 输出: 55
print(fibonacci.cache_info())  # 输出缓存信息
```

### 5. `@functools.wraps`
`@functools.wraps` 装饰器用于保留被装饰函数的元数据（如函数名、文档字符串等）。
这在自定义装饰器时非常有用，可以避免元数据丢失。

```python
from functools import wraps

def my_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        print("Something is happening before the function is called.")
        result = func(*args, **kwargs)
        print("Something is happening after the function is called.")
        return result
    return wrapper

@my_decorator
def say_hello():
    """Prints a greeting."""
    print("Hello!")

print(say_hello.__name__)  # 输出: say_hello
print(say_hello.__doc__)   # 输出: Prints a greeting.
```

### 6. `@dataclasses.dataclass`
`@dataclasses.dataclass` 装饰器用于自动生成特殊方法，如 `__init__`、`__repr__`、`__eq__` 等。
这可以**简化类的定义**，特别是对于数据类。

```python
from dataclasses import dataclass

@dataclass
class Person:
    name: str
    age: int

person = Person("Alice", 30)
print(person)  # 输出: Person(name='Alice', age=30)
```

### 7. `@contextlib.contextmanager`
`@contextlib.contextmanager` 装饰器用于定义上下文管理器。这可以简化资源管理，如文件操作、锁等。

```python
from contextlib import contextmanager

@contextmanager
def open_file(path, mode):
    file = open(path, mode)
    try:
        yield file
    finally:
        file.close()

with open_file('example.txt', 'w') as f:
    f.write('Hello, world!')
```
