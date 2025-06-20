# [SQLite3](https://www.sqlite.org/index.html) ~~(来自ChatGPT)~~ 
SQLite3 是一个提供关系数据库管理系统的软件库，它嵌入在应用程序中，不需要单独的服务器进程来运行。SQLite3以轻量级、快速和易于使用而闻名。
 - 不需要一个单独的服务器进程或操作的系统（无服务器的）。
 - SQLite 不需要配置，这意味着不需要安装或管理。
 - 一个完整的 SQLite 数据库是存储在一个单一的跨平台的磁盘文件。
 - SQLite 是非常小的，是轻量级的，完全配置时小于 400KiB，省略可选功能配置时小于250KiB。
 - SQLite 是自给自足的，这意味着不需要任何外部的依赖。
 - SQLite 事务是完全兼容 ACID 的，允许从多个进程或线程安全访问。
 - SQLite 支持 SQL92（SQL2）标准的大多数查询语言的功能。
 - SQLite 使用 ANSI-C 编写的，并提供了简单和易于使用的 API。
 - SQLite 可在 UNIX（Linux, Mac OS-X, Android, iOS）和 Windows（Win32, WinCE, WinRT）中运行。
# API 接口
## [C/C++ 接口](https://www.sqlite.org/c3ref/intro.html)
### [sqlite3_open(const char *filename, sqlite3 **ppDb)](https://www.sqlite.org/c3ref/open.html)
打开与 SQLite 数据库文件的连接并返回数据库连接对象，是数据库连接对象的构造函数。
这通常是应用程序进行的第一个 SQLite API 调用，也是大多数其他 SQLite API 的先决条件。许多 SQLite 接口都需要指向数据库连接对象的指针作为其第一个参数，可以将其视为数据库连接对象上的方法。
> 如果 filename 参数是 **NULL 或 ':memory:'**，那么 sqlite3_open() 将会在 **RAM** 中创建一个内存数据库，这只会在 session 的有效时间内持续。

> 如果文件名 filename 不为 NULL，那么 sqlite3_open() 将使用这个参数值尝试打开数据库文件。如果该名称的文件不存在，sqlite3_open() 将**创建一个新的命名为该名称的数据库文件**并打开。
### [sqlite3_exec(sqlite3*, const char *sql, sqlite_callback, void *data, char **errmsg)](https://www.sqlite.org/c3ref/exec.html)
该例程提供了一个执行 SQL 命令的快捷方式，SQL 命令由 sql 参数提供，可以由多个 SQL 命令组成。
sqlite3_exec() 程序解析并执行由 sql 参数所给的每个命令，直到字符串结束或者遇到错误为止。
> sqlite3 是打开的数据库对象，sqlite_callback 是一个回调，data 作为其第一个参数，errmsg 将被返回用来获取程序生成的任何错误。
### [sqlite3_close(sqlite3*)](https://www.sqlite.org/c3ref/close.html)
关闭先前通过调用 sqlite3_open() 打开的数据库连接。与该连接相关的所有准备好的语句都应在关闭连接之前完成。
> 如果还有查询没有完成，sqlite3_close() 将返回 **SQLITE_BUSY** 禁止关闭的错误消息。

### 示例

```cpp
#include <stdio.h>
#include <sqlite3.h>

static int callback(void *NotUsed, int argc, char **argv, char **azColName){
  int i;
  for(i=0; i<argc; i++){
    printf("%s = %s\n", azColName[i], argv[i] ? argv[i] : "NULL");
  }
  printf("\n");
  return 0;
}

int main(int argc, char **argv){
  sqlite3 *db;
  char *zErrMsg = 0;
  int rc;

  if( argc!=3 ){
    fprintf(stderr, "Usage: %s DATABASE SQL-STATEMENT\n", argv[0]);
    return(1);
  }
  rc = sqlite3_open(argv[1], &db);
  if( rc ){
    fprintf(stderr, "Can't open database: %s\n", sqlite3_errmsg(db));
    sqlite3_close(db);
    return(1);
  }
  rc = sqlite3_exec(db, argv[2], callback, 0, &zErrMsg);
  if( rc!=SQLITE_OK ){
    fprintf(stderr, "SQL error: %s\n", zErrMsg);
    sqlite3_free(zErrMsg);
  }
  sqlite3_close(db);
  return 0;
}
```

## [Python 接口](https://docs.python.org/3/library/sqlite3.html)
### sqlite3.connect(database [,timeout ,other optional arguments])
打开一个到 SQLite 数据库文件 database 的链接，返回一个连接对象。
> 可以使用 ":memory:" 来在 RAM 中打开一个到 database 的数据库连接，而不是在磁盘上打开

当一个数据库被多个连接访问，且其中一个修改了数据库，此时 SQLite 数据库被锁定，直到事务提交。timeout 参数表示连接等待锁定的持续时间，直到发生异常断开连接。timeout 参数默认是 5.0（5 秒）。

如果给定的数据库名称 filename 不存在，则该调用将创建一个数据库。如果您不想在当前目录中创建数据库，那么您可以指定带有路径的文件名，这样您就能在任意地方创建数据库。
### connection.cursor([cursorClass])
创建一个 cursor，将在 Python 数据库编程中用到。该方法接受一个单一的可选的参数 cursorClass。如果提供了该参数，则它必须是一个扩展自 sqlite3.Cursor 的自定义的 cursor 类。

### cursor.execute(sql [, optional parameters])
执行一个 SQL 语句。该 SQL 语句可以被参数化（即使用占位符代替 SQL 文本）。
sqlite3 模块支持两种类型的占位符：**问号**和**命名占位符**（命名样式）。

```bash
# Example
cursor.execute("insert into people values (?, ?)", (who, age))
```
### connection.execute(sql [, optional parameters])
上面执行的由光标（cursor）对象提供的方法的快捷方式，它通过调用光标（cursor）方法创建了一个中间的光标对象，然后通过给定的参数调用光标的 execute 方法。
### cursor.executemany(sql, seq_of_parameters)
对 seq_of_parameters 中的所有参数或映射执行一个 SQL 命令。
### connection.executemany(sql[, parameters])
一个由调用光标（cursor）方法创建的中间的光标对象的快捷方式，然后通过给定的参数调用光标的 **executemany** 方法。
### cursor.executescript(sql_script)
一旦接收到脚本，会执行多个 SQL 语句。它首先执行 COMMIT 语句，然后执行作为参数传入的 SQL 脚本。所有的 SQL 语句应该用分号 **;** 分隔。
### connection.executescript(sql_script)
一个由调用光标（cursor）方法创建的中间的光标对象的快捷方式，然后通过给定的参数调用光标的 **executescript** 方法。
### connection.total_changes()
返回自数据库连接打开以来被修改、插入或删除的数据库**总行数**。
### connection.commit()
提交当前的事务。
> 如果未调用该方法，那么自您上一次调用 commit() 以来所做的任何动作对其他数据库连接来说是**不可见**的。

### connection.rollback()
回滚自上一次调用 commit() 以来对数据库所做的更改。
### connection.close()
关闭数据库连接。

> 这不会自动调用 commit()。如果之前未调用 commit() 方法，就直接关闭数据库连接，您所做的所有更改将全部丢失！
### cursor.fetchone()
获取查询结果集中的下一行，返回一个单一的序列，当没有更多可用的数据时，则返回 None。
### cursor.fetchmany([size=cursor.arraysize])
获取查询结果集中的下一行组，返回一个列表。当没有更多的可用的行时，则返回一个空的列表。该方法尝试获取由 size 参数指定的尽可能多的行。

### cursor.fetchall()
获取查询结果集中所有（剩余）的行，返回一个列表。当没有可用的行时，则返回一个空的列表。

```python
# 导入SQLite驱动
import sqlite3
# 连接到SQLite数据库
# 数据库文件是test.db
# 如果文件不存在，会自动在当前目录创建
conn = sqlite3.connect('test.db')
# 创建一个Cursor
cursor = conn.cursor()
# 执行一条SQL语句，创建user表
cursor.execute('create table user (id varchar(20) primary key, name varchar(20))')
# 继续执行一条SQL语句，插入一条记录
cursor.execute('insert into user (id, name) values (\'1\', \'Michael\')')
# 提交事务
conn.commit()
# 关闭Cursor
cursor.close()
# 关闭Connection
conn.close()
```
#  常见问题
## SQLite数据库文件不断增长
### 原因及解决方法
1. **插入密集型工作负载**：如果您的应用程序不断插入大量数据，那么数据库文件的大小自然会增加。要缓解这种情况，可以：
	- 实施数据保留策略，以删除旧或不必要的数据。
	- 使用更高效的存储引擎，例如 WAL（Write-Ahead Log）模式。
	- 优化插入语句，以减少写入次数。
2. **事务日志开销**：SQLite 使用事务系统来确保数据一致性。但是，这可能会导致文件大小增长，如果不正确地管理事务日志。要解决这个问题，可以：
	- 使用 VACUUM 命令来回收未使用的空间并重新组织数据库文件。
	- 将 journal_mode 设置为 WAL 或 MEMORY，以减少事务日志开销。
3. **索引膨胀**：随着数据库的增长，索引也会增长。这可能会导致文件大小增加。要缓解这种情况，可以：
	- 定期运行 ANALYZE 命令来更新索引统计信息。
	- 考虑删除并重新创建索引，以维持最佳性能。
4. **未使用的空间**：SQLite 以固定大小的块分配空间，这可能会导致文件中存在未使用的空间。要回收这些空间，可以：
	- 运行 VACUUM 命令来压缩数据库文件。
5. **碎片**：随着数据的插入、更新和删除，数据库文件可能会变得碎片化，导致空间浪费。要解决这个问题，可以：
	- 运行 VACUUM 命令来碎片整理数据库文件。
6. **版本控制和撤销/重做日志**：SQLite 维护撤销和重做日志来支持事务。这些日志可能会随着时间的推移而增长。要管理这些日志，可以：
	- 使用 PRAGMA 命令来设置撤销和重做日志的大小。
7. **数据压缩**：如果您的数据高度可压缩，可以考虑使用压缩库来减少文件大小。

### 监控和分析 SQLite 数据库文件大小，可以使用以下命令：
> `PRAGMA page_size` 查看页大小（默认为 1024 字节）。
> `PRAGMA page_count` 查看数据库中的总页数。
> `PRAGMA freelist_count` 查看空闲页的数量。
> `VACUUM` 命令来压缩数据库文件并回收未使用的空间。
# 高阶使用
## PRAGMA
PRAGMA 是 SQLite3 中的一种命令，用于查看和设置数据库的各种配置选项。
PRAGMA 命令可以帮助**优化数据库性能、诊断问题、管理数据库文件**等。
### 常见 PRAGMA 命令
**1. PRAGMA cache_size**
- 含义：设置数据库缓存的大小
- 用法：`PRAGMA cache_size = <size>;`
- 说明：设置缓存的大小可以**提高查询性能**，但是也可能**增加内存使用量**。

**2. PRAGMA journal_mode**
- 含义：设置日志模式
- 用法：`PRAGMA journal_mode = <mode>;`
- 说明：日志模式有三种：WAL（Write-Ahead Logging）、MEMORY、OFF。
    - WAL 模式可以提供高性能和高可用性。
    - MEMORY 模式可以提供高性能，但可能会丢失数据
    - OFF 模式可以关闭日志功能。

**3. PRAGMA synchronous**
- 含义：设置同步模式
- 用法：`PRAGMA synchronous = <mode>;`
- 说明：同步模式有三种：NORMAL、FULL、OFF。
    - NORMAL 模式可以提供高性能和高可用性。
    - FULL 模式可以提供高可用性，但可能会降低性能。
    - OFF 模式可以关闭同步功能。

**4. PRAGMA encoding**
- 含义：设置数据库编码
- 用法：`PRAGMA encoding = "<encoding>";`
- 说明：设置数据库编码可以支持多语言字符集，例如 UTF-8。

**5. PRAGMA foreign_keys**
- 含义：设置外键约束
- 用法：`PRAGMA foreign_keys = <mode>;`
- 说明：外键约束可以确保数据的一致性和完整性。
    - ON 模式可以启用外键约束。
    - OFF 模式可以关闭外键约束。

**6. PRAGMA auto_vacuum**
- 含义：设置自动 vacuum 模式
- 用法：`PRAGMA auto_vacuum = <mode>;`
- 说明：
    - 自动 vacuum 模式可以自动释放数据库中的空闲空间。
    - FULL 模式可以释放所有空闲空间。
    - INCREMENTAL 模式可以释放部分空闲空间。
    - NONE 模式可以关闭自动 vacuum 功能。

**7. PRAGMA page_size**
- 含义：设置数据库页大小
- 用法：`PRAGMA page_size = <size>;`
- 说明：设置数据库页大小可以影响数据库性能和存储空间使用量。

**8. PRAGMA cache_spill**
- 含义：设置缓存溢出阈值
- 用法：`PRAGMA cache_spill = <size>;`
- 说明：设置缓存溢出阈值可以控制缓存的大小和溢出行为。

**9. PRAGMA integrity_check**
- 含义：检查数据库完整性
- 用法：`PRAGMA integrity_check;`
- 说明：检查数据库完整性可以检测数据库中的错误和不一致性。

**10. PRAGMA analyze**
- 含义：收集数据库统计信息
- 用法：`PRAGMA analyze;`
- 说明：收集数据库统计信息可以帮助优化数据库性能和查询计划。

**11. PRAGMA optimize**
- 含义：优化数据库结构
- 用法：`PRAGMA optimize;`
- 说明：优化数据库结构可以提高数据库性能和存储空间使用率。

**12. PRAGMA vacuum**
- 含义：释放数据库中的空闲空间
- 用法：`PRAGMA vacuum;`
- 说明：释放数据库中的空闲空间可以回收存储空间和提高数据库性能。

**13. PRAGMA wal_checkpoint**
- 含义：检查点日志文件
- 用法：`PRAGMA wal_checkpoint;`
- 说明：检查点日志文件可以确保日志文件的一致性和完整性。

**14. PRAGMA data_version**
- 含义：获取数据库版本号
- 用法：`PRAGMA data_version;`
- 说明：获取数据库版本号可以检测数据库的变化和更新。

**15. PRAGMA schema_version**
- 含义：获取数据库架构版本号
- 用法：`PRAGMA schema_version;`
- 说明：获取数据库架构版本号可以检测数据库架构的变化和更新。 
### PRAGMA 命令注意事项
1. PRAGMA 命令只能在当前数据库连接中生效。
2. PRAGMA 命令不能在事务中使用。
3. PRAGMA 命令可能会影响数据库性能，需要根据实际情况进行调整。
4. PRAGMA 命令可能会影响数据库的兼容性，需要根据实际情况进行调整。
## VACUUM
VACUUM 命令是 SQLite3 中的一个命令，用于释放数据库中的空闲空间。该命令可以**帮助回收存储空间、提高数据库性能和减少数据库文件的大小**。
### 语法
```bash
VACUUM;
```
### VACUUM 命令的作用
1. **释放数据库中的空闲空间**：VACUUM 命令可以释放数据库中的空闲空间，使得数据库文件的大小减少。
2. **重建数据库索引**：VACUUM 命令可以重建数据库索引，使得索引更加紧凑和高效。
3. **优化数据库性能**：VACUUM 命令可以优化数据库性能，使得查询和插入操作更加快速。
使用场景
### VACUUM 命令使用场景
1. **数据库文件大小增加**：当数据库文件的大小增加时，可以使用 VACUUM 命令来释放空闲空间。
2. **数据库性能下降**：当数据库性能下降时，可以使用 VACUUM 命令来优化数据库性能。
3. **数据库索引不连续**：当数据库索引不连续时，可以使用 VACUUM 命令来重建索引。
### VACUUM 命令注意事项
1. VACUUM 命令只能在当前数据库连接中生效。
2. VACUUM 命令可能会锁定数据库，影响其他连接的操作。
3. VACUUM 命令可能会花费一些时间，特别是在大型数据库中。
4. VACUUM 命令不适合在事务中使用。
> **VACUUM 命令与其他命令的差异**
> - VACUUM 命令不同于 TRUNCATE 命令，TRUNCATE 命令只能删除表中的所有数据，而 VACUUM 命令可以释放数据库中的空闲空间。
> - VACUUM 命令不同于 OPTIMIZE 命令，OPTIMIZE 命令可以优化数据库性能，但不能释放空闲空间。
