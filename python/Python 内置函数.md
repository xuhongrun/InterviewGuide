> 官方文档：[Built-in Functions](https://docs.python.org/3/library/functions.html)

| 函数名称 | 描述 |
| --- | --- |
| `abs(x)` | 返回数字 `x` 的绝对值。 |
| `all(iterable)` | 如果 `iterable` 中的所有元素都为真（非空），则返回 `True`。 |
| `any(iterable)` | 如果 `iterable` 中至少有一个元素为真，则返回 `True`。 |
| `ascii(object)` | 返回对象的字符串表示，该字符串只包含 ASCII 字符。 |
| `bin(x)` | 将整数 `x` 转换为二进制字符串，结果前缀为 `'0b'`。 |
| `bool(x)` | 将 `x` 转换为布尔值；`None`、`0`、`False`、空字符串、空列表等为 `False`，其他为 `True`。 |
| `bytearray([source])` | 创建一个新的字节数组对象；如果 `source` 是字符串，将其转换为字节数组。 |
| `bytes([source])` | 创建一个新的字节对象；如果 `source` 是整数，返回长度为该整数的字节对象。 |
| `chr(i)` | 返回一个字符，其 Unicode 编码为整数 `i`。 |
| `complex([real[, imag]])` | 创建一个复数对象。 |
| `delattr(object, name)` | 删除对象的 `name` 属性。 |
| `dict(**kwargs)` | 创建一个新字典，`kwargs` 中的键值对作为字典的项。 |
| `dir([object])` | 返回对象的属性列表，如果没有提供对象，则返回当前局部符号表中的名称。 |
| `divmod(a, b)` | 返回一个包含商和余数的元组，对应于 `a // b` 和 `a % b`。 |
| `enumerate(iterable, [start])` | 在 `iterable` 上返回一个枚举对象，从 `start` 开始计数。 |
| `eval(expression, [globals[, locals]])` | 计算表达式节点并返回结果。 |
| `exec(object[, globals[, locals]])` | 执行动态 Python 代码。 |
| `filter(function or None, iterable)` | 构造一个迭代器，包含 `iterable` 中使得 `function` 返回值为真的元素。 |
| `float([x])` | 将 `x` 转换为浮点数；如果 `x` 未提供，则返回 `0.0`。 |
| `format(value[, format_spec])` | 格式化值。 |
| `frozenset([source])` | 返回一个冻结集合对象，如果 `source` 是集合，则复制它。 |
| `getattr(object, name[, default])` | 获取对象的 `name` 属性，如果不存在则返回 `default`。 |
| `globals()` | 返回一个代表当前全局符号表的字典。 |
| `hasattr(object, name)` | 检查对象是否有 `name` 属性，如果有则返回 `True`。 |
| `hash(object)` | 返回对象的哈希值。 |
| `help([object])` | 启动一个帮助系统。如果提供了对象，则显示该对象的帮助文档。 |
| `hex(x)` | 将整数 `x` 转换为十六进制字符串，结果前缀为 `'0x'`。 |
| `id(object)` | 返回对象的唯一标识符。 |
| `input([prompt])` | 从标准输入读取一行文本，如果提供了 `prompt`，则显示提示。 |
| `int([x[, base]])` | 将 `x` 转换为整数；如果 `x` 是字符串，则根据 `base` 转换。 |
| `isinstance(object, classinfo)` | 检查 `object` 是否是 `classinfo` 的实例或子类。 |
| `issubclass(class, classinfo)` | 检查 `class` 是否是 `classinfo` 的子类。 |
| `iter(object[, sentinel])` | 返回对象的迭代器。如果提供了 `sentinel`，则返回一个迭代器，当对象返回 `sentinel` 时停止。 |
| `len(s)` | 返回对象 `s` 的长度。 |
| `list([iterable])` | 将 `iterable` 转换为列表；如果没有提供，则返回空列表。 |
| `locals()` | 返回一个代表当前局部符号表的字典。 |
| `map(function, iterable, ...)` | 构造一个迭代器，将 `function` 应用于 `iterable` 中的每个项目。 |
| `max(iterable[, default=obj], key=None)` | 返回 `iterable` 中的最大项。 |
| `memoryview(object)` | 返回对象的内存视图。 |
| `min(iterable[, default=obj], key=None)` | 返回 `iterable` 中的最小项。 |
| `next(object[, default])` | 返回迭代器的下一个项目，如果迭代器耗尽，则返回 `default`。 |
| `object()` | 返回一个新创建的对象。 |
| `oct(x)` | 将整数 `x` 转换为八进制字符串，结果前缀为 `'0o'`。 |
| `open(file, mode='r', buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None)` | 打开一个文件并返回文件对象。 |
| `ord(c)` | 返回一个字符的 Unicode 编码。 |
| `pow(x, y)` | 返回 `x` 的 `y` 次幂。 |
| `print(*objects, sep=' ', end='\n', file=sys.stdout, flush=False)` | 打印对象到文件。 |
| `property([fget[, fset[, fdel[, doc]]]])` | 创建一个属性对象。 |
| `range(start, stop[, step]])` | 返回一个代表整数序列的对象。 |
| `repr(object)` | 返回对象的官方字符串表示形式。 |
| `reversed(seq)` | 返回一个反向迭代器。 |
| `round(number[, ndigits])` | 对数字进行四舍五入。 |
| `set([iterable])` | 返回一个新的集合对象，如果提供了 `iterable`，则复制它。 |
| `setattr(object, name, value)` | 设置对象的 `name` 属性为 `value`。 |
| `slice(start, stop[, step])` | 创建一个 slice 对象。 |
| `sorted(iterable[, key=None][, reverse=False]])` | 返回一个新的排好序的列表。 |
| `staticmethod(function)` | 将函数转换为静态方法。 |
| `str(object='')` | 将对象转换为字符串。 |
| `sum(iterable[, start])` | 返回 `iterable` 中所有项的总和。 |
| `super().__init__()` | 返回一个代理对象，用于表示超类方法。 |
| `tuple([iterable])` | 将 `iterable` 转换为元组；<br>如果没有提供，则返回空元组。 |
| `type(object)` | 返回对象的类型。 |
| `vars([object])` | 返回对象的 `__dict__` 属性。 |
| `zip(*iterables)` | 返回一个迭代器，将多个迭代器中的对应元素打包为元组。 |
