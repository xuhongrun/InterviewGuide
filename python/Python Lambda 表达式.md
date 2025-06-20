Python 中的 lambda 表达式是一种简洁的匿名函数，允许你在不需要完整函数定义的情况下创建函数。它们通常用于编写简单的函数，或者在需要传递函数作为参数时使用。

## Python Lambda 表达式

Python 的 lambda 表达式是一种小型的匿名函数，它可以接受任何数量的参数，但只能有一个表达式。这种函数的语法如下：

```python
lambda arguments: expression
```

- `arguments`：这是传递给 lambda 函数的参数。
- `expression`：这是 lambda 函数返回的表达式。

## Python Lambda 表达式 使用

### 基本用法

```python
# 一个简单的 lambda 表达式，计算两个数的和
add = lambda x, y: x + y
print(add(3, 4))  # 输出 7
```

### 作为参数传递

Lambda 表达式常用于需要函数作为参数的场合，比如排序：

```python
# 使用 lambda 表达式作为排序的键函数
names = ['Alice', 'Bob', 'Charlie']
sorted_names = sorted(names, key=lambda name: len(name))
print(sorted_names)  # 输出 ['Bob', 'Alice', 'Charlie']
```

### 列表推导式

Lambda 表达式也可以在列表推导式中使用：

```python
# 使用 lambda 表达式创建一个新列表，其中包含原列表元素的平方
numbers = [1, 2, 3, 4, 5]
squared_numbers = list(map(lambda x: x**2, numbers))
print(squared_numbers)  # 输出 [1, 4, 9, 16, 25]
```

### 与内置函数结合

Lambda 表达式可以与许多内置函数结合使用，例如 `filter` 和 `reduce`：

```python
# 使用 lambda 表达式和 filter 函数过滤列表
numbers = [1, 2, 3, 4, 5, 6]
even_numbers = list(filter(lambda x: x % 2 == 0, numbers))
print(even_numbers)  # 输出 [2, 4, 6]

# 使用 lambda 表达式和 reduce 函数计算列表元素的乘积
from functools import reduce
product = reduce(lambda x, y: x * y, numbers)
print(product)  # 输出 120
```

### 多个参数和多个表达式

虽然 lambda 表达式只能有一个表达式，但它可以接受多个参数：

```python
# 一个接受多个参数的 lambda 表达式
multiply = lambda x, y, z: x * y * z
print(multiply(2, 3, 4))  # 输出 24
```

### 捕获外部变量

Lambda 表达式可以捕获外部作用域中的变量：

```python
# 外部变量
multiplier = 3

# 一个捕获外部变量的 lambda 表达式
multiply_by_three = lambda x: x * multiplier
print(multiply_by_three(4))  # 输出 12
```


Python 的 lambda 表达式是一种快速定义简单函数的方法，它们在需要函数作为参数或者需要快速定义一个小型函数时非常有用。
Lambda 表达式使得代码更加简洁，并且可以在不定义完整函数的情况下实现函数逻辑。
