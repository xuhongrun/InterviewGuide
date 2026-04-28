# 网络编程 Socket

> Berkeley socket API、TCP/UDP server/client 模板、关键 socket 选项、常见错误码与排查。

---

## 1. Socket 类型

| 类型 | 域 | 协议 | 适用 |
|------|------|------|------|
| `SOCK_STREAM` | AF_INET/AF_INET6 | TCP | 可靠字节流 |
| `SOCK_DGRAM` | AF_INET/AF_INET6 | UDP | 不可靠数据报 |
| `SOCK_RAW` | AF_INET | 原始 IP | ping、traceroute |
| `SOCK_STREAM` | AF_UNIX | 本地 | 同主机 IPC |
| `SOCK_SEQPACKET` | AF_UNIX | 本地 | 保持边界的可靠数据报 |

---

## 2. TCP 服务端模板（C 语言）

```c
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

int srv = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0);

int yes = 1;
setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof yes);
setsockopt(srv, SOL_SOCKET, SO_REUSEPORT, &yes, sizeof yes);

struct sockaddr_in addr = {
    .sin_family = AF_INET,
    .sin_port   = htons(8080),
    .sin_addr   = { .s_addr = htonl(INADDR_ANY) },
};
bind(srv, (struct sockaddr*)&addr, sizeof addr);
listen(srv, 1024);

for (;;) {
    struct sockaddr_in cli; socklen_t clen = sizeof cli;
    int c = accept4(srv, (struct sockaddr*)&cli, &clen, SOCK_CLOEXEC | SOCK_NONBLOCK);
    if (c < 0) continue;
    handle(c);   // fork / 线程池 / Reactor
}
```

调用顺序：`socket → bind → listen → accept` 服务端；`socket → connect` 客户端。

---

## 3. UDP 模板

```c
int s = socket(AF_INET, SOCK_DGRAM, 0);
bind(s, ...);
char buf[2048];
struct sockaddr_in peer; socklen_t plen = sizeof peer;
ssize_t n = recvfrom(s, buf, sizeof buf, 0, (struct sockaddr*)&peer, &plen);
sendto(s, buf, n, 0, (struct sockaddr*)&peer, plen);
```

* UDP **不需要 listen/accept**。
* 单包 ≤ MTU - IP/UDP 头（典型 1472 字节）；超出走 IP 分片，丢一个全丢。
* 多播：`setsockopt(s, IPPROTO_IP, IP_ADD_MEMBERSHIP, ...)`。

---

## 4. 关键 socket 选项

| 选项 | 用途 |
|------|------|
| `SO_REUSEADDR` | TIME_WAIT 状态下也能 bind 同端口（必开） |
| `SO_REUSEPORT` | 多进程同时 bind 同端口，内核负载均衡 |
| `SO_KEEPALIVE` | TCP 层心跳（默认 2h，太长，业务通常自带应用层心跳） |
| `SO_LINGER` | close 时如何处理未发送数据 |
| `SO_RCVBUF` / `SO_SNDBUF` | 收发缓冲区（受 `net.core.rmem_max` 限制） |
| `TCP_NODELAY` | 关闭 Nagle，立即发小包（低延迟必开） |
| `TCP_CORK` | 反向：聚合小包再发（吞吐优先） |
| `TCP_QUICKACK` | 立即 ACK，不延迟 |
| `TCP_USER_TIMEOUT` | 业务级超时 |
| `IP_TOS` / `SO_PRIORITY` | QoS 标记 |
| `SO_BINDTODEVICE` | 绑定到指定网卡 |
| `MSG_NOSIGNAL` (send) | 对端关闭时返回 EPIPE 而不发 SIGPIPE |

---

## 5. 字节序与地址转换

```c
htons / htonl   // host → network
ntohs / ntohl   // network → host

inet_pton(AF_INET,  "192.168.1.1", &addr.sin_addr);
inet_ntop(AF_INET, &addr.sin_addr, str, sizeof str);

// 通用 DNS / 服务名
struct addrinfo hints = { .ai_family = AF_UNSPEC, .ai_socktype = SOCK_STREAM };
struct addrinfo *res;
getaddrinfo("example.com", "443", &hints, &res);
```

> 不再使用过时的 `inet_addr` / `gethostbyname`（不可重入、无 IPv6）。

---

## 6. read/write 全语义

* `read` 返回 0 = **对端关闭**（半关闭）。
* `read`/`write` 可能**部分读写**，必须循环至完成或错误：

```c
ssize_t writen(int fd, const void *buf, size_t n) {
    size_t left = n; const char *p = buf;
    while (left > 0) {
        ssize_t w = write(fd, p, left);
        if (w < 0) {
            if (errno == EINTR) continue;
            if (errno == EAGAIN) /* 等 EPOLLOUT */ ;
            return -1;
        }
        p += w; left -= w;
    }
    return n;
}
```

* **粘包**：TCP 是字节流，应用层必须自带定长头 / 分隔符 / TLV / Length-Prefixed framing。
* **EPIPE / SIGPIPE**：写到已关闭对端默认 SIGPIPE 杀进程；用 `MSG_NOSIGNAL` 或 `signal(SIGPIPE, SIG_IGN)`。

---

## 7. 优雅关闭

* `close(fd)` 立即关闭双向；尚未发送的数据可能丢（受 SO_LINGER 控制）。
* `shutdown(fd, SHUT_WR)` 半关闭：发送 FIN，仍可读对端剩余数据；适合"我说完了你慢慢说"。
* 标准退出：写完 → `shutdown(SHUT_WR)` → 读到 EOF → `close`。

---

## 8. 常见错误码

| errno | 含义 | 通常处理 |
|------|------|------|
| EAGAIN/EWOULDBLOCK | 非阻塞下没数据/不可写 | 注册 epoll 等待 |
| EINTR | 系统调用被信号打断 | 重试 |
| ECONNREFUSED | 对端无监听 | 重连 / 报错 |
| ECONNRESET | 对端 RST | 关闭、清理 |
| EPIPE | 写到已关闭连接 | 关闭 |
| ETIMEDOUT | 内核超时 | 重连 |
| EADDRINUSE | 端口被占 | 开 SO_REUSEADDR / 换端口 |
| ENETUNREACH | 网络不可达 | 检查路由 |
| EMFILE / ENFILE | fd 用尽 | 调 ulimit / 排查泄漏 |

---

## 9. 多路复用骨架（epoll + 非阻塞）

```c
int ep = epoll_create1(EPOLL_CLOEXEC);
epoll_ctl(ep, EPOLL_CTL_ADD, srv,
    &(struct epoll_event){ .events = EPOLLIN, .data.fd = srv });

for (;;) {
    struct epoll_event evs[1024];
    int n = epoll_wait(ep, evs, 1024, -1);
    for (int i = 0; i < n; ++i) {
        int fd = evs[i].data.fd;
        if (fd == srv) {
            for (;;) {
                int c = accept4(srv, NULL, NULL, SOCK_NONBLOCK | SOCK_CLOEXEC);
                if (c < 0) break;     // EAGAIN
                epoll_ctl(ep, EPOLL_CTL_ADD, c,
                    &(struct epoll_event){ .events = EPOLLIN | EPOLLET, .data.fd = c });
            }
        } else {
            handle_io(fd, evs[i].events);
        }
    }
}
```

---

## 10. Unix Domain Socket（同主机 IPC）

```c
struct sockaddr_un un = { .sun_family = AF_UNIX };
strcpy(un.sun_path, "/tmp/app.sock");
unlink(un.sun_path);
bind(s, (struct sockaddr*)&un, sizeof un);
```

* 比 TCP 快 2~3×（无 IP 栈、无校验和）。
* 支持 **传递 fd**（`SCM_RIGHTS`）—— Docker、systemd socket activation 大量使用。
* `SOCK_SEQPACKET` 保留消息边界，介于 TCP/UDP 之间。

---

## 11. 高级网络栈

* **DPDK**：用户态网卡驱动 + 大页 + poll mode driver，绕开内核协议栈，10G+ 线速。
* **XDP / eBPF**：在驱动入口包处理（DDoS 过滤、负载均衡）。
* **mTCP / F-Stack**：用户态 TCP/IP 栈。
* **SO_ZEROCOPY**（Linux 4.14+）：`MSG_ZEROCOPY` send 零拷贝。
* **sendfile / splice**：文件 → socket 不经用户态。

---

## 12. 调试工具速查

| 工具 | 用途 |
|------|------|
| `ss -tunap` | 替代 netstat，查连接/监听 |
| `tcpdump -i any -nn 'port 8080'` | 抓包 |
| `wireshark` | 图形化分析 |
| `strace -e trace=network` | 看系统调用 |
| `lsof -i :8080` | 谁占用了端口 |
| `iperf3` / `nuttcp` | 带宽测试 |
| `mtr` / `traceroute` | 路径丢包 |
| `tc qdisc add ... netem delay 100ms loss 1%` | 模拟劣质网络 |

---

## 面试速记

1. **TCP 服务端 5 步**：socket → bind → listen → accept → close。
2. `SO_REUSEADDR` 解决重启 bind 失败；`SO_REUSEPORT` 解决多进程惊群。
3. **TCP_NODELAY** 关 Nagle，低延迟必开。
4. **read 返 0** = 对端关闭。
5. **TCP 粘包**靠应用层 framing 解决（length-prefixed、分隔符、TLV）。
6. `shutdown` 半关闭 vs `close` 全关闭。
7. **EPIPE / SIGPIPE** 用 `MSG_NOSIGNAL` 屏蔽。
8. **EAGAIN** 是非阻塞常态，挂回 epoll 等待。
9. **inet_pton/ntop + getaddrinfo** 替代过时 API，原生支持 IPv6。
10. **Unix Domain Socket** 同主机最快，能传 fd。

---

## 关联阅读

* [TCP UDP](TCP%20UDP.md) · [HTTP HTTPS](HTTP%20HTTPS.md) · [IO 多路复用](IO%20多路复用.md) · [网络 最佳实践](网络%20最佳实践.md)
