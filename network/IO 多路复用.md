# IO 多路复用

> 面试高频：select / poll / epoll / kqueue / IOCP / io_uring，Reactor / Proactor 模型。

---

## 1. 阻塞 / 非阻塞 / 同步 / 异步

| 维度 | 含义 |
|------|------|
| **阻塞 / 非阻塞** | 调用方在数据就绪前是否被挂起 |
| **同步 / 异步** | 数据从内核到用户的拷贝是否由调用方完成 |

5 种 IO 模型（Stevens UNP）：

1. **阻塞 IO**（默认 `read`）—— 等到数据 + 拷贝完才返回。
2. **非阻塞 IO**（`fcntl O_NONBLOCK`）—— 没数据立即返回 EAGAIN，需轮询。
3. **IO 多路复用**（`select`/`poll`/`epoll`）—— 单线程管多 fd，**仍是同步**。
4. **信号驱动 IO**（`SIGIO`）—— 很少用。
5. **异步 IO**（`aio_*`、Windows IOCP、Linux **io_uring**）—— 内核搞定一切，回调通知。

---

## 2. select / poll / epoll 对比

| 维度 | select | poll | **epoll** |
|------|------|------|------|
| FD 上限 | FD_SETSIZE=1024（编译期） | 无（数组） | 无 |
| 数据结构 | 位图 bitmap | `pollfd[]` | 红黑树 + 就绪链表 |
| 每次调用 | 拷贝整张表 → 内核 | 同 | **只注册一次** |
| 时间复杂度 | O(n) 扫描 | O(n) | **O(1)** 取就绪 |
| 触发模式 | LT | LT | **LT + ET** |
| 跨平台 | POSIX | POSIX | Linux 专属 |

口诀：**select 兼容、poll 去 1024 限制、epoll 高并发首选**。

### epoll 三件套

```c
int ep = epoll_create1(EPOLL_CLOEXEC);

struct epoll_event ev = { .events = EPOLLIN | EPOLLET, .data.fd = sock };
epoll_ctl(ep, EPOLL_CTL_ADD, sock, &ev);

struct epoll_event events[1024];
int n = epoll_wait(ep, events, 1024, -1);
for (int i = 0; i < n; ++i) { /* handle events[i] */ }
```

* **LT (Level Triggered)**：只要可读就一直通知（默认，编程简单）。
* **ET (Edge Triggered)**：状态变化才通知一次，**必须配非阻塞 fd + 循环 read 到 EAGAIN**，否则丢事件。
* `EPOLLONESHOT`：避免多线程同时处理同一 fd（处理完需重新 `EPOLL_CTL_MOD`）。

---

## 3. 其他平台

* **kqueue**（BSD/macOS）：和 epoll 等价；额外支持文件、信号、定时器统一事件源。
* **IOCP**（Windows）：完成端口；天然 **Proactor**，内核完成数据拷贝后通知。
* **`/dev/poll`、Solaris event ports**：少见。

---

## 4. io_uring（Linux 5.1+）

* **真正的异步 IO**：用户态 SQ（提交队列）+ 内核态 CQ（完成队列），**零系统调用批量提交**。
* 支持网络 + 文件 + fsync + accept + connect + timeout。
* 5.6 起加入 SQPOLL（内核线程轮询）、5.11 加入 IORING_REGISTER_FILES。
* 高性能服务器（Nginx 实验、TigerBeetle、ScyllaDB、seastar）已采用。
* 推荐封装：**liburing**。

```c
struct io_uring ring;
io_uring_queue_init(256, &ring, 0);

struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
io_uring_prep_read(sqe, fd, buf, len, offset);
io_uring_submit(&ring);

struct io_uring_cqe *cqe;
io_uring_wait_cqe(&ring, &cqe);
// cqe->res 是 read 字节数
io_uring_cqe_seen(&ring, cqe);
```

---

## 5. Reactor / Proactor 模型

### Reactor（同步多路复用 + 同步 IO）

```
事件分发器 epoll_wait → 通知 Handler → Handler 自己 read/write
```

代表：**Redis（单 Reactor 单线程）**、**Memcached / Nginx（多 Reactor 多线程）**、**Netty**、**libevent / libev / libuv**。

变体：

* **单 Reactor 单线程**（Redis）：简单、单核饱和；CPU 多核浪费。
* **单 Reactor 多线程**：主线程 accept + read，业务线程池处理；写回主线程或线程池。
* **主从 Reactor 多线程**（Nginx/Netty 推荐）：mainReactor 负责 accept，subReactors 负责 read/write，业务线程池处理。

### Proactor（异步 IO）

```
发起异步操作 → 内核完成 → 通知 Handler → Handler 直接处理结果
```

代表：**Windows IOCP**、**Boost.Asio**、**io_uring + 上层封装**。

口诀：**Reactor 等可读，Proactor 等读完**。

---

## 6. 惊群与 SO_REUSEPORT

* 多进程/多线程 `accept` 同一监听 fd，旧内核会全部唤醒（**惊群 thundering herd**）。
* Linux 现代内核：`accept` 已修复，但 `epoll_wait` 仍可能惊群。
* 推荐：**`SO_REUSEPORT`** —— 内核负载均衡到多个监听 socket，每个 worker 一个，无惊群。

```c
int opt = 1;
setsockopt(sock, SOL_SOCKET, SO_REUSEPORT, &opt, sizeof(opt));
```

---

## 7. C10K → C10M

| 规模 | 关键技术 |
|------|------|
| **C10K** | epoll/kqueue + Reactor + 非阻塞 |
| **C100K** | 上面 + 内存池 + 零拷贝 sendfile + tcp_nopush |
| **C1M** | SO_REUSEPORT + 多核独立 Reactor + DPDK / XDP |
| **C10M** | 用户态协议栈（mTCP、F-Stack）+ DPDK；CPU pinning + NUMA 优化 |

---

## 8. 典型坑

1. **ET 模式下没循环 read 到 EAGAIN** —— 数据残留，下次不再通知。
2. **fd 关闭后再注册到 epoll** —— 文件描述符回收，挂错。
3. **多线程同时 epoll_wait 同一个 epfd** 不加 `EPOLLONESHOT` —— 同一事件被多线程处理。
4. **epoll_wait 返回 EINTR** 没重试 —— 信号导致退出。
5. **写缓冲区满后没注册 EPOLLOUT** —— write 阻塞或丢数据。
6. **timer 用 sleep 实现** —— 阻塞 Reactor；用 `timerfd` / `epoll` 超时参数。
7. **接收一次只 accept 一个连接**（LT 下还行，ET 下必须循环到 EAGAIN）。

---

## 9. 选型建议

| 场景 | 推荐 |
|------|------|
| Linux 高并发服务器 | epoll + ET + SO_REUSEPORT 多 Reactor |
| 跨平台库 | libuv / libevent（自动选 epoll/kqueue/IOCP） |
| 现代 Linux 极致性能 | **io_uring** + 用户态调度（seastar） |
| Windows 服务 | IOCP + Boost.Asio |
| 业务为主的应用层 | Netty (Java) / Tokio (Rust) / asyncio (Python) / Boost.Asio (C++) |

---

## 面试速记

1. **5 种 IO 模型**：阻塞、非阻塞、多路复用、信号驱动、异步。
2. **select/poll/epoll** 三选一比较：FD 上限、复杂度、ET/LT。
3. **epoll ET** 必须非阻塞 + 循环读到 EAGAIN。
4. **Reactor**（同步多路复用） vs **Proactor**（异步 IO）。
5. **Redis 单 Reactor 单线程** 为何还快：内存 + 无锁 + epoll。
6. **Nginx 主从 Reactor 多进程**，每 worker 独立 epoll，SO_REUSEPORT 负载均衡。
7. **io_uring** 是 Linux 真异步未来；批量 SQE/CQE，零拷贝、零系统调用。
8. **惊群** 用 SO_REUSEPORT 解决。
9. **C10K → C10M**：epoll → SO_REUSEPORT/多核 → DPDK/io_uring。
10. **EAGAIN/EWOULDBLOCK** 是非阻塞 IO 的常态返回，必须处理。

---

## 关联阅读

* [TCP UDP](TCP%20UDP.md) · [HTTP HTTPS](HTTP%20HTTPS.md) · [网络编程 Socket](网络编程%20Socket.md) · [网络 最佳实践](网络%20最佳实践.md)
