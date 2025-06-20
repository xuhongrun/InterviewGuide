> 正则在线实用工具：[regex101](https://regex101.com/)

正则表达式（regular expression）是一种用于匹配字符串中字符组合模式的工具。它可以用来检查一个字符串是否匹配某个模式、提取字符串中的信息、替换字符串中的某些部分等。

Python 的 `re` 模块提供了对正则表达式的支持，允许你执行复杂的字符串搜索、替换、匹配和分割操作。

### 正则表达式匹配
- **`re.match()`**：如果正则表达式与字符串的开始部分匹配，则返回一个匹配对象；否则返回 `None`。
  ```python
  import re
  if re.match(r'^\d+', '123abc'):
      print("Match found")
  ```

- **`re.search()`**：扫描整个字符串，返回第一个成功的匹配。
  ```python
  match = re.search(r'\d+', 'abc123def')
  if match:
      print("Match found at position:", match.start(), match.end())
  ```

- **`re.fullmatch()`**：如果整个字符串匹配正则表达式，则返回一个匹配对象；否则返回 `None`。
  ```python
  if re.fullmatch(r'\d+', '123'):
      print("Full match")
  ```

### 正则表达式查找
- **`re.findall()`**：返回一个列表，包含字符串中所有匹配正则表达式的子串。
  ```python
  numbers = re.findall(r'\d+', 'abc123def456')
  print(numbers)
  ```

- **`re.finditer()`**：返回一个迭代器，产生每个匹配的 `Match` 对象。
  ```python
  for match in re.finditer(r'\d+', 'abc123def456'):
      print("Match found at position:", match.start(), match.end())
  ```

### 正则表达式替换
- **`re.sub()`**：替换字符串中所有匹配正则表达式的部分。
  ```python
  new_string = re.sub(r'\d+', 'XXX', 'abc123def456')
  print(new_string)
  ```

- **`re.subn()`**：与 `re.sub()` 类似，但返回一个元组，包含替换后的字符串和替换次数。
  ```python
  new_string, count = re.subn(r'\d+', 'XXX', 'abc123def456')
  print("Replacements made:", count)
  ```

### 正则表达式分割
- **`re.split()`**：按照匹配正则表达式的部分分割字符串。
  ```python
  parts = re.split(r'\d+', 'abc123def456')
  print(parts)
  ```

### 编译正则表达式
- **`re.compile()`**：编译一个正则表达式模式，返回一个 `Pattern` 对象。
  ```python
  pattern = re.compile(r'\d+')
  match = pattern.search('abc123def')
  if match:
      print("Match found at position:", match.start(), match.end())
  ```

### 正则表达式转义
- **`re.escape()`**：转义所有可能被解释为正则表达式操作符的字符。
  ```python
  escaped_string = re.escape('$1,000')
  print(escaped_string)
  ```

### 正则表达式模式
- **`re.purge()`**：清除正则表达式的缓存（主要供调试使用）。

### 正则表达式断言
- **`re.assert()`**：用于确保一个正则表达式在指定的字符串中匹配，否则抛出 `AssertionError`。


| 特殊序列 | 含义 |
| --- | :--- |
| `.` | 匹配任意单个字符（除了换行符） |
| `\d` | 匹配任意数字，等同于 `[0-9]` |
| `\D` | 匹配任意非数字字符，等同于 `[^0-9]` |
| `\w` | 匹配任意字母数字字符，包括下划线，等同于 `[a-zA-Z0-9_]` |
| `\W` | 匹配任意非字母数字字符，等同于 `[^a-zA-Z0-9_]` |
| `\s` | 匹配任意空白字符，包括空格、制表符、换行符等 |
| `\S` | 匹配任意非空白字符 |
| `^` | 匹配字符串的开始 |
| `$` | 匹配字符串的结束 |
| `*` | 匹配前面的子表达式零次或多次 |
| `+` | 匹配前面的子表达式一次或多次 |
| `?` | 匹配前面的子表达式零次或一次 |
| `{n}` | 匹配确定的 n 次 |
| `{n,}` | 至少匹配 n 次 |
| `{n,m}` | 最少匹配 n 次且最多 m 次 |
| `()` | 捕获组，用于创建一个组，可以提取匹配的部分 |
| `\1`, `\2`, ... | 引用分组中的匹配，`\1` 引用第一组的匹配 |
| `\|` | 匹配两项之间的任意一项（或） |
| `(?:...)` | 非捕获组，用于分组但不捕获匹配的文本 |
| `(?=...)` | `lookahead` 正向前瞻断言，匹配后面跟着特定模式的字符串 |
| `(?!...)` | `negative lookahead` 负向前瞻断言，匹配后面不跟着特定模式的字符串 |
| `(?<=...)` | `lookbehind` 正向后瞻断言，匹配前面是特定模式的字符串 |
| `(?<!...)` | `negative lookbehind` 负向后瞻断言，匹配前面不是特定模式的字符串 |
| `\` | 用于转义特殊字符，使其失去特殊含义，例如 `\.` 匹配点字符 `.` |
| `\p{L}` | 匹配任何Unicode字母 |
| `\P{L}` | 匹配任何非Unicode字母 |
