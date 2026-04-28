# Python 异步编程 asyncio

> 单线程协程并发：事件循环 + `async/await` + 协议 / 流 / 任务组。Python 3.11+ 现代用法。

---

## 1. 为什么需要 asyncio？

* **IO 密集型**（HTTP、DB、消息队列）：线程切换开销大，协程在单线程内成千上万并发，内存与上下文切换更省。
* **CPU 密集型**：asyncio **不能**加速；用多进程 / C 扩展 / GIL-free（3.13+ free-threaded）。
* 与多线程相比：无锁竞争、无 GIL 切换抖动；但**一段同步阻塞代码会卡死整个事件循环**。

---

## 2. 协程基础

```python
import asyncio

async def hello(name):           # 协程函数（coroutine function）
    await asyncio.sleep(1)        # 让出控制权
    return f"hi, {name}"

async def main():
    r = await hello("world")      # 等待协程
    print(r)

asyncio.run(main())               # 启动事件循环（3.7+）
```

* `async def` 定义协程；调用返回 **协程对象**，需被 `await` 或调度才执行。
* `await` 只能出现在 `async def` 内；只能 await **awaitable**（协程 / Task / Future）。
* `asyncio.run(coro)` 是顶层入口（不要在已运行循环里再调用）。

---

## 3. Task 与并发

### 3.1 并发 N 个任务

```python
async def fetch(i):
    await asyncio.sleep(1)
    return i * 2

# ❌ 顺序，3 秒
async def seq():
    return [await fetch(i) for i in range(3)]

# ✅ 并发，1 秒
async def conc():
    return await asyncio.gather(*(fetch(i) for i in range(3)))
```

### 3.2 `asyncio.gather` 关键参数

```python
results = await asyncio.gather(t1, t2, t3, return_exceptions=True)
# return_exceptions=True：异常作为返回值（混在结果里），不会取消其他
# 默认（False）：任一异常立刻取消其他并向上抛
```

### 3.3 TaskGroup（3.11+，强烈推荐）

```python
async def main():
    async with asyncio.TaskGroup() as tg:
        tg.create_task(work(1))
        tg.create_task(work(2))
    # 退出时等待所有任务；任一失败 → 取消其他 → 一并抛 ExceptionGroup
```

* **结构化并发**：作用域内全部任务必须在 `async with` 退出前完成。
* 比 `gather` 更安全：取消语义清晰、异常合并为 `ExceptionGroup`。

### 3.4 超时

```python
# 3.11+ 推荐
async with asyncio.timeout(5):
    await long_call()

# 旧 API
result = await asyncio.wait_for(long_call(), timeout=5)
```

---

## 4. 同步原语

```python
asyncio.Lock()         # 互斥
asyncio.Semaphore(10)  # 限流（同时最多 10 个 await）
asyncio.Event()        # 标志
asyncio.Queue(maxsize) # 生产消费
```

```python
sem = asyncio.Semaphore(10)
async def fetch_url(url):
    async with sem:                  # 限并发 10
        async with httpx.AsyncClient() as c:
            r = await c.get(url)
            return r.text
```

---

## 5. 阻塞代码怎么办？

**绝不**在协程里调用同步阻塞 IO（`requests.get` / `time.sleep` / 同步 DB 客户端 / `cv2.imread` 大文件）：

```python
# ❌ 阻塞整个事件循环
def heavy(): ...

async def bad():
    heavy()            # 整个循环卡住
```

正确方式：

```python
# 1) 用异步库（首选）：aiohttp / httpx / asyncpg / aiomysql / aiokafka

# 2) 把同步函数丢线程池
import asyncio
result = await asyncio.to_thread(heavy)         # 3.9+ 简洁
# 等价：loop.run_in_executor(None, heavy)

# 3) CPU 密集走进程池
from concurrent.futures import ProcessPoolExecutor
loop = asyncio.get_running_loop()
result = await loop.run_in_executor(ProcessPoolExecutor(), cpu_heavy, *args)
```

---

## 6. 取消与异常

```python
task = asyncio.create_task(work())
...
task.cancel()
try:
    await task
except asyncio.CancelledError:
    pass
```

* 取消通过在下一个 `await` 点抛 `CancelledError`。
* **不要吞 CancelledError**：在协程里 `try/except Exception` 不会捕获它（3.8+ 起 CancelledError 直接派生 BaseException）。
* TaskGroup 失败时取消其他任务；最终抛 `ExceptionGroup`，用 `except*`：

```python
try:
    async with asyncio.TaskGroup() as tg: ...
except* ValueError as eg:
    for e in eg.exceptions: ...
```

---

## 7. 流式 IO 与服务器

### 7.1 TCP 客户端

```python
async def echo():
    reader, writer = await asyncio.open_connection("127.0.0.1", 8888)
    writer.write(b"hello\n"); await writer.drain()
    data = await reader.readline()
    writer.close(); await writer.wait_closed()
    return data
```

### 7.2 TCP 服务器

```python
async def handle(reader, writer):
    while data := await reader.readline():
        writer.write(data); await writer.drain()
    writer.close()

async def main():
    srv = await asyncio.start_server(handle, "0.0.0.0", 8888)
    async with srv:
        await srv.serve_forever()
```

### 7.3 HTTP 客户端

```python
import httpx
async def main():
    async with httpx.AsyncClient(timeout=5.0) as c:
        urls = ["https://a", "https://b"]
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(c.get(u)) for u in urls]
        return [t.result().text for t in tasks]
```

---

## 8. 与多线程 / 多进程对比

| 维度 | asyncio 协程 | threading | multiprocessing |
|------|--------------|-----------|-----------------|
| 适用 | IO 密集 + 高并发连接 | IO 密集（库不支持 async 时） | CPU 密集 |
| 切换 | 协作式，await 主动让出 | OS 抢占 | OS 进程 |
| 内存 | 极低（KB/协程） | 中（MB/线程） | 高（独立进程） |
| GIL | 不规避 GIL（单线程） | 受 GIL 限制 CPU | 真并行 |
| 调试 | 栈复杂、上下文跳跃 | 锁竞争 | 序列化、通信成本 |
| 一个慢函数 | 卡死全部 | 仅卡该线程 | 仅卡该进程 |

**经验法则**：
* 千 ~ 十万级并发连接 / 高 IO 等待 → asyncio。
* 几百并发 + 现成同步库 → threading。
* CPU 密集 → 多进程 / Cython / Rust 扩展。

---

## 9. 调试与诊断

```python
asyncio.run(main(), debug=True)     # 检测慢回调、取消未 await 的协程等
```

* 环境变量 `PYTHONASYNCIODEBUG=1`。
* `asyncio.all_tasks()` 列出所有任务。
* `asyncio.current_task()` 取当前任务。
* 性能：`uvloop`（Linux/macOS）替换默认事件循环，吞吐 2~4×。

```python
import uvloop, asyncio
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
```

* 火焰图 / 追踪：`py-spy --native`、`viztracer`、`yappi --clock-type=wall`。

---

## 10. 常见坑

1. **忘记 `await`**：协程对象被丢弃，得到 `RuntimeWarning: coroutine ... was never awaited`。
2. **混用同步阻塞**：`time.sleep`、阻塞 socket、CPU 重计算 → 卡循环。
3. **`asyncio.run` 嵌套**：不能在已有循环内调用；用 `await coro`。
4. **跨循环传 Future**：Future 绑定到创建它的循环；多线程要 `run_coroutine_threadsafe`。
5. **任务被 GC**：`create_task` 返回值不持有引用，可能被 GC 提前取消；用集合存住。
6. **`as_completed` 顺序**：返回的是 future 顺序而非传入顺序。
7. **Windows 选择器**：3.8+ 默认 ProactorEventLoop，部分库不兼容（如 aiokafka 旧版）。
8. **CancelledError 静默吞掉** → 资源未清理；只清理 + re-raise。
9. **`gather` 不传 `return_exceptions=True`**：一个失败取消其他但当前异常会先抛，其他结果丢失。
10. **过度并发**：无限制 `gather` 1 万任务 → 打爆下游；必须限流（Semaphore / 队列 worker）。

---

## 11. 高频面试题

1. asyncio 与 threading 区别？什么场景选哪个？
2. `await` 做了什么？事件循环如何调度？
3. `gather` vs `TaskGroup` 区别？为什么推荐 TaskGroup？
4. 在协程里调 `time.sleep(5)` 会发生什么？正确做法？
5. CPU 密集任务如何与 asyncio 协作？
6. 取消是如何工作的？如何正确处理 CancelledError？
7. asyncio 怎么实现连接限流？
8. `run_in_executor` 与 `to_thread` 区别？
9. uvloop 为什么比默认快？
10. `async for` 和 `async with` 的协议是什么？（`__aiter__/__anext__`、`__aenter__/__aexit__`）
11. 协程对象、Future、Task 三者关系？
12. `loop.call_later` / `call_soon` 用法？
13. asyncio 中如何实现超时？取消语义？
14. 异常传播：`gather` 内某个任务抛错会怎样？
15. asyncio 中如何与 ProcessPool 协作做 CPU 密集子任务？

---

## 12. Top 15 asyncio Checklist

1. ☐ IO 密集才用 asyncio；CPU 密集走进程。
2. ☐ 顶层用 `asyncio.run`；不在循环内嵌套调。
3. ☐ 并发优先 `asyncio.TaskGroup`（3.11+），少用 `gather`。
4. ☐ 超时优先 `asyncio.timeout` 上下文。
5. ☐ 限流必备 Semaphore；不要无限 gather。
6. ☐ 同步阻塞函数走 `asyncio.to_thread`。
7. ☐ 引用持有 `create_task` 返回的 Task，避免 GC。
8. ☐ 取消时清理 + re-raise CancelledError。
9. ☐ 异常聚合用 `except*` 处理 ExceptionGroup。
10. ☐ 库选用：httpx / aiohttp / asyncpg / aiomysql / aiokafka / aioredis。
11. ☐ Linux 服务部署用 uvloop。
12. ☐ 不在事件循环线程内执行重 CPU 工作。
13. ☐ 调试开 `debug=True`；定位慢回调。
14. ☐ 优雅停机：监听 SIGTERM → 取消所有任务 → 等收尾 → 退出。
15. ☐ 写测试：`pytest-asyncio` + `asyncio_mode=auto`。

---

## 面试速记

1. **协程 = 协作式调度**，await 让出。
2. **asyncio 单线程**，一段阻塞卡全部。
3. **TaskGroup（3.11+）= 结构化并发**，比 gather 安全。
4. **超时用 `asyncio.timeout`** 上下文。
5. **限流用 Semaphore**，避免压爆下游。
6. **阻塞代码丢 to_thread**，CPU 密集丢 ProcessPool。
7. **CancelledError ≠ Exception**（3.8+ 派生 BaseException）。
8. **uvloop 加速 2–4×**。
9. **Task 持引用**，否则可能被 GC 取消。
10. **gather + return_exceptions=True** 让异常成为结果。
11. **async for / with** 协议：`__aiter__/__anext__` `__aenter__/__aexit__`。
12. **asyncio.run 是顶层入口**，不要嵌套。

---

## 关联阅读

* [Python 并发](Python%20并发.md) · [Python 多线程](Python%20多线程.md) · [Python 多进程](Python%20多进程.md)
* [Python 装饰器](Python%20装饰器.md) · [Python 迭代器与生成器](Python%20迭代器与生成器.md)
* [Python 最佳实践](Python%20最佳实践.md)
* [IO 多路复用](../network/IO%20多路复用.md)
