# Linux 基础

> 面向后端 / 机器人 / 嵌入式工程师的 Linux 操作系统核心：进程、线程、内存、文件、IO、调度、信号、命名空间。

---

## 1. 进程与线程

### 1.1 进程

* **PID / PPID / PGID / SID**：进程 ID、父进程、进程组、会话。
* **fork() / vfork() / clone()**：
  * `fork` 写时复制（COW），父子各自独立地址空间。
  * `clone` 是 Linux 通用接口，通过 flag 控制共享什么（线程、命名空间、文件描述符）。
* **exec 族** 替换进程映像；fork + exec = 创建新程序。
* **进程状态**：R(running)、S(可中断睡眠)、D(不可中断，常因 IO)、Z(僵尸)、T(stopped)。
* **僵尸 Zombie**：子进程退出但父进程没 `wait`；用 `SIGCHLD` 处理或父进程 `waitpid`。
* **孤儿 Orphan**：父进程先退出，被 init/systemd（PID 1）收养。

### 1.2 线程

* Linux 线程 = **轻量级进程 LWP**，共享地址空间（`clone(CLONE_VM|CLONE_FILES|...)`）。
* `pthread_*` 是 NPTL 实现；`std::thread` / `std::jthread` 底层即 pthread。
* `gettid()` 取线程 ID（≠ pthread_t）。
* TLS（线程本地存储）：`__thread` / `thread_local`。

### 1.3 调度

| 策略 | 说明 |
|------|------|
| `SCHED_OTHER` (CFS) | 默认，公平调度，按 nice 值（-20~19）分权重 |
| `SCHED_FIFO` | 实时，无时间片，优先级 1-99 |
| `SCHED_RR` | 实时，有时间片轮转 |
| `SCHED_DEADLINE` | EDF 算法，硬实时 |
| `SCHED_IDLE` | 最低，CPU 空闲才跑 |

* `nice` / `renice` 调整优先级；实时用 `chrt`。
* CPU 亲和：`taskset -c 2,3 ./app` / `pthread_setaffinity_np`。
* `perf sched` 看调度延迟；PREEMPT_RT 用于硬实时。

---

## 2. 内存管理

### 2.1 虚拟内存

* 每进程独立虚拟地址空间（64 位典型 256 TB 用户态）。
* 4 KB 页（默认）+ **Huge Pages** 2 MB / 1 GB（减少 TLB miss）。
* **MMU + 多级页表** 完成虚拟 → 物理转换；TLB 缓存。
* **写时复制 COW**：fork 后父子共享物理页，写时才分裂。

### 2.2 进程内存布局

```
+-----------------+ 高地址
| 内核空间         |
+-----------------+
| 栈 stack ↓       | 自动变量
+-----------------+
|   ↕ 空洞         |
+-----------------+
| mmap / 共享库   |
+-----------------+
| 堆 heap ↑        | malloc/new
+-----------------+
| BSS              | 未初始化全局
| 数据段           | 已初始化全局
| 代码段 .text     | 只读
+-----------------+ 低地址
```

* `brk/sbrk` 调整堆顶；`mmap` 大块或文件映射。
* `glibc malloc` 用 ptmalloc2，arena + bin 设计；高并发碎片严重，可换 `jemalloc` / `tcmalloc` / `mimalloc`。

### 2.3 OOM 与内存压力

* **OOM Killer**：内存耗尽时按 `oom_score` 杀进程；关键服务调 `oom_score_adj` 降权。
* `/proc/meminfo`、`/proc/<pid>/status`(VmRSS/VmSize)、`vmstat`、`free -h`。
* **swap**：现代服务通常关或最小化（避免抖动）。
* **cgroup memory** 限额；K8s 用同机制。

---

## 3. 文件与 IO

### 3.1 文件系统

* VFS 抽象层 → ext4 / xfs / btrfs / zfs / tmpfs / overlayfs。
* **inode** 存元数据（mode、owner、size、链接数、数据块指针）；目录项 `dentry` 存名字 → inode。
* **硬链接 vs 软链接**：硬链接共享 inode，不能跨 fs / 目录；软链接是另存路径的小文件。
* `df -i` 查 inode 使用，**inode 耗尽** = 容量没满也写不进。

### 3.2 文件描述符 fd

* 进程级 fd 表 → 系统级 file 表 → inode。
* `ulimit -n` 限制（默认 1024，生产改 65536+）。
* `O_CLOEXEC` 防 fd 泄漏给 exec 后的子进程。
* `dup / dup2 / dup3`、`fcntl` 复制与控制。

### 3.3 IO 模型

详见 [IO 多路复用](../network/IO%20多路复用.md)。

* `read/write` 阻塞默认；`O_NONBLOCK` + epoll 高并发。
* `mmap` 映射文件到内存，零拷贝读取。
* `sendfile / splice` 文件 → socket 不经用户态。
* **页缓存 Page Cache**：所有文件 IO 走它；`fsync` 强制刷盘；`O_DIRECT` 绕过（DB 常用）。
* `posix_fadvise` 提示访问模式；`readahead` 预读。

### 3.4 inotify / fanotify

监听文件变更（开发热重载、备份触发）。

---

## 4. 信号 Signal

* 异步通知：`SIGINT(Ctrl-C)`、`SIGTERM(默认 kill)`、`SIGKILL(9, 不可捕获)`、`SIGSEGV`、`SIGCHLD`、`SIGPIPE`、`SIGUSR1/2`。
* 注册：`sigaction`（POSIX 推荐，比 `signal` 行为可控）。
* **信号安全函数**：handler 内只能调 async-signal-safe 的（`write`、`_exit`），**不能** `printf`、`malloc`。
* 多线程下：信号送给进程，由任意线程处理；用 `pthread_sigmask` 屏蔽到专用线程。
* 现代替代：`signalfd` —— 把信号转 fd，融入 epoll 循环。

---

## 5. 进程间通信 IPC

| 机制 | 适用 |
|------|------|
| 管道 pipe | 父子进程，单向 |
| 命名管道 FIFO | 任意进程，单向 |
| Unix Domain Socket | 同主机，双向，可传 fd |
| 共享内存 `shm_open` / `mmap` | 大数据零拷贝，需自行同步 |
| 消息队列 POSIX `mq_*` | 优先级、固定大小 |
| 信号量 `sem_*` | 同步 |
| 信号 | 简单通知 |
| eventfd / signalfd / timerfd | 与 epoll 融合 |

**性能排序**（同主机）：共享内存 > Unix Socket > Pipe > TCP loopback。

详见 [C++ 进程间通信（IPC）](../cpp/C++%20进程间通信（IPC）.md)。

---

## 6. 命名空间 Namespace 与 Cgroup（容器基础）

### 6.1 Namespace（隔离）

| 类型 | 隔离 |
|------|------|
| `mnt` | 文件系统挂载点 |
| `pid` | 进程号空间（容器内 PID 1） |
| `net` | 网卡、路由、iptables |
| `ipc` | System V IPC、POSIX MQ |
| `uts` | hostname、domain |
| `user` | UID/GID 映射（容器 root ≠ 宿主 root） |
| `cgroup` | cgroup 视图 |
| `time` | 时钟（5.6+） |

`unshare`、`nsenter` 命令操作。

### 6.2 Cgroup（资源限额）

* CPU、内存、IO、PID、网络。
* **cgroup v2** 统一层级（推荐）；v1 已 legacy。
* K8s / Docker / systemd 全部基于 cgroup。
* 查看：`/sys/fs/cgroup/`。

容器 = **namespace 隔离 + cgroup 限额 + 镜像层 overlayfs**。

---

## 7. 网络栈基础

* 网卡 → 驱动 → 协议栈（ARP/IP/TCP/UDP）→ socket → 应用。
* `iptables` / `nftables`：netfilter 钩子，过滤、NAT、转发。
* `ip` 命令族：`ip addr / link / route / netns`（替代过时的 `ifconfig` `route`）。
* `ss -tulpn` 看连接（替代 netstat）。
* eBPF / XDP：内核可编程过滤、监控、负载均衡（Cilium）。
* 详见 [网络编程 Socket](../network/网络编程%20Socket.md) / [网络 最佳实践](../network/网络%20最佳实践.md)。

---

## 8. 启动与 init

* **systemd** 是主流 init：`unit` 文件 = `.service` `.socket` `.timer` `.target`。
* `systemctl start/stop/enable/status xxx`。
* `journalctl -u xxx -f` 查日志（替代 syslog 多数场景）。
* 服务模板示例：

```ini
# /etc/systemd/system/myapp.service
[Unit]
Description=My App
After=network-online.target

[Service]
Type=simple
ExecStart=/opt/myapp/bin/server
Restart=on-failure
LimitNOFILE=65536
User=myapp

[Install]
WantedBy=multi-user.target
```

---

## 9. 性能与排查工具速查

| 维度 | 工具 |
|------|------|
| **CPU** | `top` / `htop` / `btop` / `mpstat` / `pidstat -t -p PID` |
| **内存** | `free` / `vmstat 1` / `smem` / `pmap -x PID` |
| **IO** | `iostat -xz 1` / `iotop` / `biolatency`(BCC) |
| **网络** | `ss -i` / `nstat` / `tcpdump` / `iftop` / `nethogs` |
| **追踪** | `strace -c -p PID`（系统调用）/ `ltrace`（库调用）|
| **Profile** | `perf record -g -p PID` + `perf report` / FlameGraph |
| **eBPF** | `bpftrace` / BCC 工具集（`execsnoop`、`tcpconnect`、`offcputime`） |
| **GDB** | `gdb -p PID`（生产慎用，会暂停进程） |
| **核心转储** | `coredumpctl list` / `gdb /path/bin core` |
| **磁盘** | `df -h` / `du -sh *` / `ncdu` / `lsof` |
| **句柄** | `ls -l /proc/<pid>/fd` / `lsof -p <pid>` |

诊断思路：**USE 方法**（Utilization / Saturation / Errors）+ Brendan Gregg 的 60-second checklist。

---

## 10. /proc 与 /sys 速查

* `/proc/<pid>/status` 进程综合信息
* `/proc/<pid>/maps` 内存映射
* `/proc/<pid>/fd/` 文件描述符
* `/proc/<pid>/limits` 资源上限
* `/proc/<pid>/stack` 内核调用栈
* `/proc/cpuinfo`、`/proc/meminfo`、`/proc/loadavg`
* `/proc/sys/`、`/etc/sysctl.d/` 内核参数
* `/sys/class/`、`/sys/block/` 设备视图

---

## 11. 常见生产问题速查

| 现象 | 怀疑 | 排查 |
|------|------|------|
| Load 高 CPU 不忙 | IO 等待（D 状态多） | `iostat`、`iotop`、`vmstat` |
| 内存占用涨，未释放 | 缓存 / 真泄漏 | `pmap` 看进程 RSS；`/proc/meminfo` Cached |
| 突然 OOM | swap 关 + 短时尖峰 | dmesg 看 OOM Killer |
| 大量 TIME_WAIT | 短连接客户端 | `ss -s`、开 `tcp_tw_reuse`、走连接池 |
| `Too many open files` | fd 泄漏 / ulimit 太小 | `lsof -p` |
| 偶发卡顿 | GC / 内核抖动 / 中断风暴 | `perf sched`、`mpstat -P ALL 1` |
| coredump 不产生 | core_pattern / ulimit -c | `cat /proc/sys/kernel/core_pattern`、`ulimit -c unlimited` |

---

## 12. Top 15 工程化 Checklist

1. ☐ ulimit nofile/stack/core 上线前调好。
2. ☐ 关键进程设 oom_score_adj。
3. ☐ 大流量服务关 swap 或降权。
4. ☐ 内核参数（somaxconn / rmem / BBR / fs.file-max）入 `/etc/sysctl.d/`。
5. ☐ systemd 服务有 Restart + 日志接 journald。
6. ☐ 关键文件描述符设 `O_CLOEXEC`。
7. ☐ 实时控制线程 SCHED_FIFO + CPU pin + mlockall。
8. ☐ glibc malloc 高并发场景换 jemalloc / tcmalloc。
9. ☐ 信号处理用 sigaction + signalfd。
10. ☐ 子进程 wait 防僵尸；或 `SIGCHLD` SA_NOCLDWAIT。
11. ☐ 容器 cgroup 限额配齐（CPU / 内存 / PID）。
12. ☐ 监控接入 USE：`/proc` + Prometheus node_exporter。
13. ☐ 日志走 journald / 结构化 + 日志切割（logrotate）。
14. ☐ 故障演练：fd 满、磁盘满、OOM、时钟回拨。
15. ☐ 团队备好 `perf` / `bpftrace` / `strace` 工具箱与权限。

---

## 面试速记

1. **fork 写时复制**：父子共享物理页直到写。
2. **进程 5 状态**：R/S/D/Z/T；D 不可中断常因 IO。
3. **僵尸进程** = 退出但未被 wait；孤儿被 init 收养。
4. **线程是 LWP**，clone 共享地址空间。
5. **调度策略**：CFS（默认）+ FIFO/RR/DEADLINE（实时）。
6. **虚拟内存 = 页表 + COW + mmap + 页缓存**。
7. **OOM Killer** 按 oom_score；关键服务调 adj。
8. **fd ≤ 1024 默认** 是生产常见坑，必调 ulimit。
9. **container = namespace + cgroup + overlayfs**。
10. **systemd + journalctl** 是现代服务管理标配。
11. **perf + eBPF** 是现代 Linux 性能武器库。
12. **信号 handler 内只能调 async-signal-safe 函数**。

---

## 关联阅读

* [C++ 进程 线程](../cpp/C++%20进程%20线程.md) · [C++ 进程间通信（IPC）](../cpp/C++%20进程间通信（IPC）.md)
* [C++ 多线程](../cpp/C++%20多线程.md) · [C++ 内存管理](../cpp/C++%20内存管理.md)
* [网络编程 Socket](../network/网络编程%20Socket.md) · [IO 多路复用](../network/IO%20多路复用.md)
* [系统问题排查](../summarize/cpp/系统问题排查.md) · [工具链 最佳实践](../tools/工具链%20最佳实践.md)
