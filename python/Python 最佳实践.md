# Python 最佳实践

> 面向 **Python 3.10+**，覆盖工程化、并发、性能、类型与测试。可作为 Code Review 与新项目脚手架清单。

---

## 1. 项目结构与依赖

```
myproj/
├── pyproject.toml          # PEP 621：依赖、元数据、构建后端
├── src/myproj/             # 源码（src layout 防 import 错误）
│   ├── __init__.py
│   └── core.py
├── tests/                  # 测试与代码同级
├── docs/
└── .pre-commit-config.yaml
```

* **src layout**：避免「当前目录被 import」掩盖打包问题。
* 用 **`pyproject.toml`** 统一配置（PEP 621），不要再写 `setup.py`。
* 包管理推荐 **`uv`**（Astral，2024 起事实标准）或 **`poetry`** / **`pdm`**；不再裸 `pip install`。
* 锁文件入仓（`uv.lock` / `poetry.lock` / `requirements.lock`）保证可复现。
* 虚拟环境：`uv venv` / `python -m venv .venv`，**绝不全局 pip install**。

---

## 2. 类型注解 Type Hints

* **新代码强制类型注解**（PEP 484/604/695）；公开 API 必须有。
* 优先使用 **PEP 604** 联合类型 `int | None`（不写 `Optional[int]`）。
* `from __future__ import annotations`（3.10 前）或直接用字符串避免循环导入。
* 检查器：`mypy --strict` 或 **`pyright`**（更快、与 VS Code 同源）。
* 不要写无意义的 `Any`；不会的就写 `object` + 显式 `cast`。

```python
from collections.abc import Iterable, Callable

def reduce[T, R](xs: Iterable[T], f: Callable[[R, T], R], init: R) -> R:
    acc = init
    for x in xs:
        acc = f(acc, x)
    return acc
```

* 数据类用 **`dataclasses`** 或 **`pydantic v2`**（带校验）；不要再用 namedtuple 当模型。

---

## 3. 代码风格与静态检查

| 工具 | 角色 |
|------|------|
| **ruff** | 统一 lint + format（替代 flake8/isort/pyupgrade/black 大部分场景） |
| **black** | 仍可保留作为 formatter；与 ruff format 二选一 |
| **mypy / pyright** | 类型检查 |
| **bandit** | 安全扫描（eval/yaml/subprocess shell=True） |
| **pre-commit** | 提交时强制运行以上 |

`pyproject.toml` 关键片段：

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
[tool.ruff.lint]
select = ["E","F","I","B","UP","SIM","PL","RUF","S"]
ignore = ["E501"]
```

---

## 4. 错误处理

* `try` 范围**尽可能小**，只包住会抛的那一行。
* `except Exception:` 而不是裸 `except:`；自定义异常继承业务基类。
* **不要用异常做控制流**（性能、可读性）。
* 用 `logging.exception()` 自带 traceback，禁止 `print(e)`。
* 上下文管理器封装资源：`with open(...)` / `contextlib.contextmanager`。

```python
import logging
log = logging.getLogger(__name__)

try:
    payload = json.loads(text)
except json.JSONDecodeError:
    log.exception("bad payload: %s", text[:200])
    raise BadInput("invalid json") from None
```

---

## 5. 日志

* 使用标准 `logging`（或 **structlog** / **loguru**），**不要 print**。
* 顶层只配置一次（`logging.config.dictConfig`），库内只 `getLogger(__name__)`。
* JSON 结构化日志便于 ELK/Loki 检索。
* 不要把敏感信息（token、密码）写进 log；写时脱敏。

---

## 6. 并发模型选择

| 任务类型 | 选择 |
|------|------|
| **IO 密集，少量任务** | `threading` / `concurrent.futures.ThreadPoolExecutor` |
| **IO 密集，海量并发** | **`asyncio`**（aiohttp/httpx/asyncpg） |
| **CPU 密集** | **`multiprocessing`** / `ProcessPoolExecutor` / native 扩展 |
| **大数据并行** | Ray / Dask / Spark；或者 `multiprocessing.Pool` |
| **3.13 + 实验** | **No-GIL build (PEP 703)**，可用真多线程 |

口诀：**GIL 让多线程不能加速 CPU，但完全可以并发 IO**。

```python
# 优雅的 asyncio 并发
import asyncio, httpx
async def fetch_all(urls):
    async with httpx.AsyncClient() as c:
        return await asyncio.gather(*(c.get(u) for u in urls))
```

* `asyncio` **不要在协程里 `time.sleep` / 同步 IO**，会卡 event loop；用 `asyncio.to_thread()`。
* 子进程间共享数据用 `multiprocessing.shared_memory` / `Queue`；大对象走 mmap / Arrow。

---

## 7. 性能优化套路

1. **先 profile**：`cProfile` + `snakeviz`，火焰图 `py-spy record`。
2. 选对数据结构：`set`/`dict` 查找 O(1)；`list.append` 平均 O(1)。
3. 内置 / 标准库 / numpy **一定比 Python 循环快**：vectorize。
4. 字符串拼接用 `''.join(parts)`，不要 `s += x`。
5. 频繁创建大量小对象 → `__slots__` 节省内存 30~40%。
6. 热点函数用 **Cython / mypyc / numba** 编译；或 Rust + `pyo3` / C++ + `pybind11`。
7. 缓存：`functools.lru_cache` / `cache`。
8. 大 JSON：`orjson` 比 `json` 快 5~10×。
9. CPU 调用 `multiprocessing` 时算清通信开销，否则得不偿失。
10. 3.11 起解释器自带 ~25% 提速（专门优化器），尽量升级。

---

## 8. 数据处理

* 大表用 **polars**（Arrow 底层，多线程，比 pandas 快 5~30×）或 **pandas 2.x（pyarrow 后端）**。
* 流式处理大文件：`yield` 生成器，而不是 `readlines()`。
* CSV / JSONL → Parquet（列式、压缩、谓词下推）。
* 数值计算：`numpy` + 矢量化；GPU 用 `cupy` / `torch`。

```python
def read_lines(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            yield line.rstrip()
```

---

## 9. 包与发布

* 构建后端 **hatchling** / **setuptools**（`pyproject.toml` 配置）。
* 发布到 PyPI：`uv build` + `uv publish`（或 `python -m build` + `twine`）。
* CI 用 GitHub Actions 矩阵跑 3.10/3.11/3.12/3.13。
* 打 wheel 时附 `py.typed` 标记类型可用。

---

## 10. 容器化与部署

* `Dockerfile` 多阶段：builder 阶段 install，runtime 阶段拷贝结果，**镜像 < 200 MB**。
* 基镜像 `python:3.12-slim` 或 **distroless**；安全场景再小用 `python:alpine` 但注意 musl 兼容。
* `--no-cache-dir` + 锁文件 + `PYTHONDONTWRITEBYTECODE=1` + `PYTHONUNBUFFERED=1`。
* WSGI/ASGI 服务进程用 **gunicorn + uvicorn workers** 或 **granian**。
* 健康检查 `/healthz` + `/ready`；不要让进程 OOM 静默重启。

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY src/ ./src/
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1
CMD ["python", "-m", "myproj"]
```

---

## 11. 测试

* **pytest** 一统天下；fixture 替代 setup/teardown。
* 单元 / 集成 / E2E 三层金字塔；mock 用 `unittest.mock` 或 `pytest-mock`。
* 参数化 `@pytest.mark.parametrize` 做表驱动测试。
* 异步测试 `pytest-asyncio`；HTTP 用 `respx` / `httpx.MockTransport`。
* 覆盖率 `coverage.py` ≥ 80%，分支覆盖 `--branch`。
* **属性测试 hypothesis**：找边界 case。
* **快照测试 syrupy**：UI/输出回归。

---

## 12. 安全实践

* 不要 `eval` / `exec` / `pickle.load` 不可信数据（RCE）。
* `subprocess` 用列表参数，**禁止 `shell=True`** + 字符串拼接（命令注入）。
* SQL 用参数化（`?` / `%s`），不要 f-string 拼。
* YAML 用 `yaml.safe_load`。
* 依赖审计 **`pip-audit`** / **`safety`** 进 CI。
* 敏感信息走环境变量 / Secret Manager / `.env` 不入仓。
* HTTP 客户端开 TLS 校验，**禁止 `verify=False`**。

---

## 13. API 设计

* 函数参数：**关键字优先**（`*` 后强制 keyword-only），降低误用。
* 默认参数**禁用可变对象**：

```python
def append(x, lst=None):     # ✅
    lst = [] if lst is None else lst
```

* 可选返回用 `T | None`；多状态返回用 `dataclass` 或 `Result` 类型。
* 公开函数加 docstring（NumPy/Google 风格），`-> ` 类型不可少。
* 兼容性破坏：`DeprecationWarning` + `__deprecated__`（PEP 702）。

---

## 14. 反模式 Top 15

1. 默认参数用 `[]` / `{}`。
2. `import *`。
3. `except:` 裸捕获 / `except Exception: pass`。
4. 在循环里 `s += "x"` 拼字符串。
5. 误把 `is` 当 `==` 用于值比较。
6. 全局可变状态当配置。
7. 在协程里调用阻塞 IO。
8. 用 `eval` 解析 JSON。
9. 把 `print` 当日志。
10. `time.sleep` 实现重试，没有指数退避。
11. CI 不锁版本，发布即坏。
12. `subprocess(..., shell=True)` 拼命令。
13. 直接 `pickle.load(open(file))` 加载用户数据。
14. 类继承 `object` 写空 `__init__` / 空 `pass`。
15. 在 hot loop 里用 `try/except` 替代 `if`。

---

## 15. Top 20 Checklist

1. ☐ `pyproject.toml` + 锁文件入仓。
2. ☐ src layout 工程结构。
3. ☐ ruff + mypy/pyright + pre-commit 全部进 CI。
4. ☐ 公共 API 全类型注解，导出 `py.typed`。
5. ☐ 不可变默认参数。
6. ☐ 用 `logging`，不用 `print`。
7. ☐ 并发模型按 IO/CPU 维度选择。
8. ☐ asyncio 内禁止同步 IO。
9. ☐ `subprocess` 不用 `shell=True`。
10. ☐ SQL 参数化 / `yaml.safe_load`。
11. ☐ 大数据用 polars/pyarrow/parquet。
12. ☐ 字符串拼接用 `join` / `f-string`。
13. ☐ 性能优化前先 `cProfile` / `py-spy`。
14. ☐ 测试覆盖率 ≥ 80%，关键模块 ≥ 90%。
15. ☐ Docker 多阶段、镜像 < 200 MB。
16. ☐ 依赖审计 `pip-audit` 进 CI。
17. ☐ 敏感信息走环境变量 / Secret 管理。
18. ☐ HTTP 客户端 TLS 验证不要关。
19. ☐ 异常带 `from None` / `from cause`。
20. ☐ Python 版本至少 3.11+。

---

## 面试速记

1. **GIL**：CPython 单解释器锁；3.13 起有 No-GIL 实验构建。多线程并发 IO，多进程并行 CPU。
2. **asyncio**：单线程事件循环；切勿在协程里跑阻塞调用，用 `to_thread`。
3. **类型注解** + `mypy --strict`：现代 Python 必备；Union 用 `|`。
4. **数据类**：`@dataclass(slots=True, frozen=True)` 性能 + 安全。
5. **可变默认参数**陷阱：函数定义时绑定一次。
6. **`is` vs `==`**：`is` 比身份，`==` 比值；只对 `None`/单例用 `is`。
7. **生成器**：惰性、节省内存；`yield from` 委托。
8. **打包**：pyproject.toml + uv/poetry，src layout，锁文件入仓。
9. **性能**：先 profile，再考虑 Cython / numpy / orjson / mypyc。
10. **安全四不**：不 eval、不 shell=True、不 pickle 用户数据、不裸 SQL 字符串拼。

---

## 关联阅读

* [Python 类 Class](Python%20类%20Class.md) · [Python 装饰器](Python%20装饰器.md) · [Python 内置装饰器](Python%20内置装饰器.md)
* [Python 多线程](Python%20多线程.md) · [Python 多进程](Python%20多进程.md) · [Python 并发](Python%20并发.md)
* [Python 迭代器与生成器](Python%20迭代器与生成器.md) · [Python Lambda 表达式](Python%20Lambda%20表达式.md)
* [Python 内置函数](Python%20内置函数.md) · [Python 数据类型转换](Python%20数据类型转换.md) · [Python 正则表达式](Python%20正则表达式.md)
