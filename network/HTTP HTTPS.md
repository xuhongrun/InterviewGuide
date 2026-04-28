# HTTP / HTTPS

> HTTP 是应用层协议，承载 90% 互联网流量；HTTPS = HTTP + TLS。本篇覆盖 1.1/2/3 演进、关键字段、TLS 握手与常见问题。

---

## 1. 协议演进对比

| 版本 | 年份 | 传输 | 关键特性 | 痛点 |
|------|------|------|------|------|
| HTTP/0.9 | 1991 | TCP | 只 GET，纯文本 HTML | 无 header |
| HTTP/1.0 | 1996 | TCP | header、状态码、Content-Type | 每请求新连接 |
| **HTTP/1.1** | 1999 | TCP | **Keep-Alive、管线化、Host、分块** | 队头阻塞（HoL） |
| **HTTP/2** | 2015 | TCP + TLS | **二进制帧、多路复用、头压缩 HPACK、Server Push** | TCP 层 HoL |
| **HTTP/3** | 2022 | **QUIC**(UDP) | **0-RTT、QPACK、连接迁移**、彻底解决 HoL | 中间盒兼容、UDP 限速 |

口诀：**1.1 文本管线、2 二进制多路复用、3 跑在 QUIC 上**。

---

## 2. 报文结构

### 请求

```
GET /api/users?id=42 HTTP/1.1
Host: example.com
User-Agent: curl/8.5
Accept: application/json
Authorization: Bearer eyJ...
Cookie: session=abc

<body>     # GET 通常为空
```

### 响应

```
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
Content-Length: 87
Cache-Control: max-age=60
Set-Cookie: session=xyz; HttpOnly; Secure; SameSite=Lax

{"id":42,"name":"Alice"}
```

---

## 3. 方法 Method

| 方法 | 幂等 | 安全 | 用途 |
|------|------|------|------|
| GET | ✅ | ✅ | 查询 |
| HEAD | ✅ | ✅ | 只取响应头（探测） |
| POST | ❌ | ❌ | 创建、动作 |
| PUT | ✅ | ❌ | 全量更新/创建 |
| PATCH | ❌ | ❌ | 增量更新 |
| DELETE | ✅ | ❌ | 删除 |
| OPTIONS | ✅ | ✅ | 预检（CORS） |
| CONNECT | ❌ | ❌ | 代理隧道 |

---

## 4. 状态码

| 区间 | 类别 | 常用 |
|------|------|------|
| 1xx | 信息 | 100 Continue、101 Switching Protocols |
| **2xx** | 成功 | 200 OK、201 Created、204 No Content、206 Partial Content |
| **3xx** | 重定向 | 301 永久、302 临时、304 Not Modified、307 保留方法、308 永久保留方法 |
| **4xx** | 客户端错 | 400、401 未认证、403 禁止、404、405 方法不允许、409 冲突、429 限流 |
| **5xx** | 服务端错 | 500、502 网关错、503 不可用、504 网关超时 |

记忆：**401 缺凭据，403 凭据没权限，404 资源不存在，409 状态冲突，429 限流，502 上游挂，504 上游慢**。

---

## 5. 关键 Header 速查

| 类别 | Header | 作用 |
|------|------|------|
| 缓存 | `Cache-Control` / `ETag` / `Last-Modified` / `If-None-Match` | 协商缓存与强缓存 |
| 内容 | `Content-Type` / `Content-Encoding`(gzip/br) / `Content-Length` / `Transfer-Encoding: chunked` | 实体描述 |
| 协商 | `Accept` / `Accept-Encoding` / `Accept-Language` | 内容协商 |
| 连接 | `Connection: keep-alive` / `Upgrade` | 长连接 / WebSocket |
| 认证 | `Authorization` / `WWW-Authenticate` | 认证挑战 |
| Cookie | `Cookie` / `Set-Cookie`（Secure/HttpOnly/SameSite/Path/Max-Age） | 会话 |
| CORS | `Origin` / `Access-Control-Allow-*` | 跨域 |
| 安全 | `Strict-Transport-Security`(HSTS) / `Content-Security-Policy`(CSP) / `X-Frame-Options` / `X-Content-Type-Options` | 安全加固 |

---

## 6. 缓存语义

* **强缓存**：`Cache-Control: max-age=60` / `Expires` —— 浏览器直接命中本地。
* **协商缓存**：`ETag` + `If-None-Match` 或 `Last-Modified` + `If-Modified-Since` —— 服务器返回 304。
* CDN 边缘按 `Cache-Control: public, s-maxage=300`。
* `no-cache` 不是不缓存，是每次都去协商；`no-store` 才是绝对不存。

---

## 7. HTTP/2 关键

* **二进制分帧层**：HEADERS / DATA / SETTINGS / WINDOW_UPDATE …
* **流 Stream**：单连接上多路复用，每个请求一个 Stream ID（奇数客户端，偶数服务端）。
* **HPACK** 头压缩：静态表 + 动态表 + Huffman。
* **流量控制**：每流 + 整连接两级窗口。
* **优先级 / 依赖**：多数实现简化或废弃（RFC 9113 已 deprecate priority）。
* **Server Push**：实践效果差，主流浏览器移除。

---

## 8. HTTP/3 与 QUIC

* 跑在 UDP 之上，**TLS 1.3 内建**（不再有明文握手）。
* 解决 TCP **队头阻塞**：每个流独立丢包恢复。
* **0-RTT**：恢复连接首包带数据；**注意重放风险**，不要用于非幂等请求。
* **连接迁移 Connection ID**：手机切 Wi-Fi/4G 不断流。
* 部署：`Alt-Svc: h3=":443"; ma=86400` 通告升级。

---

## 9. TLS 握手（HTTPS）

```
Client                                              Server
  |--- ClientHello (versions, cipher, key_share) -->|
  |<-- ServerHello (chosen, key_share, cert) -------|
  |<-- {EncryptedExtensions, Finished} -------------|
  |--- {Finished} --------------------------------->|
  |=== Application Data (AEAD encrypted) ===========|
```

* **TLS 1.3** 1-RTT；恢复时 0-RTT（PSK）。
* 证书链验证：根 CA → 中间 → 叶；浏览器内置根证书。
* **OCSP Stapling** 减少证书状态查询。
* 现代加密套件：`TLS_AES_128_GCM_SHA256` / `TLS_CHACHA20_POLY1305_SHA256`。
* HSTS（`Strict-Transport-Security`）强制 HTTPS；preload 列表。
* 证书自动化：**Let's Encrypt + ACME（certbot）**，90 天轮换。

---

## 10. CORS

预检流程：

```
OPTIONS /api/x HTTP/1.1
Origin: https://app.com
Access-Control-Request-Method: POST
Access-Control-Request-Headers: Authorization

→ 204
Access-Control-Allow-Origin: https://app.com
Access-Control-Allow-Methods: POST, GET
Access-Control-Allow-Headers: Authorization
Access-Control-Max-Age: 86400
```

* `Origin: null` 是 `file://` 或 sandbox iframe，警惕。
* `Allow-Origin: *` 与 `Allow-Credentials: true` **不能共存**。

---

## 11. RESTful 设计要点

* 资源名词复数：`/users/42`，不要 `/getUser?id=42`。
* 动作用 HTTP 方法表达；非 CRUD 用子资源：`POST /users/42/activations`。
* 分页 `?page=1&size=20` 或游标 `?cursor=abc`；返回 `Link` header。
* 版本：URL `/v1/`、Accept header `application/vnd.app.v2+json`、或子域 `v2.api`。
* 一致错误体：`{"code":"USER_NOT_FOUND","message":"...","trace_id":"..."}`。

---

## 12. 性能与可观测性

* **连接复用**：客户端必开 keep-alive、连接池。
* **压缩**：`gzip`、`br`（Brotli，比 gzip 多 15~25%）。
* **HTTP/2/3** 减少 RTT；CDN 加速。
* **Trace**：`traceparent`（W3C Trace Context）；OpenTelemetry HTTP instrumentation。
* **指标**：QPS、P50/P95/P99 延迟、错误率、5xx 比例。
* **限流**：`429 Too Many Requests` + `Retry-After`；客户端指数退避 + jitter。

---

## 13. 安全要点

| 风险 | 防御 |
|------|------|
| 明文 | 全站 HTTPS + HSTS + preload |
| MITM | 证书校验、证书 Pinning（移动端） |
| XSS | CSP + 输出编码 + `HttpOnly` cookie |
| CSRF | SameSite=Lax/Strict + CSRF Token |
| 点击劫持 | `X-Frame-Options: DENY` 或 CSP `frame-ancestors` |
| MIME 嗅探 | `X-Content-Type-Options: nosniff` |
| 越权 | 每请求验证授权（不要只前端隐藏） |
| SSRF | 出站请求白名单 IP / 域名 |
| 重放（0-RTT） | 仅用于幂等 GET；写操作走 1-RTT |

---

## 14. 调试工具

| 工具 | 用途 |
|------|------|
| `curl -v` | 看请求/响应头 |
| `httpie` / `xh` | 友好命令行 |
| **Wireshark** + ssl keylog | 抓包 + TLS 解密 |
| **mitmproxy** | 中间人调试 |
| `openssl s_client -connect host:443 -tls1_3` | 看证书与握手 |
| 浏览器 DevTools Network | 时序、瀑布、headers |
| `nghttp` / `h2load` | HTTP/2 测试 |
| `siege` / `wrk` / `k6` | 压测 |

---

## 面试速记

1. **HTTP/1.1 vs 2 vs 3**：管线 → 二进制多路复用 → QUIC 解决 HoL。
2. **TLS 1.3** 1-RTT，0-RTT 需防重放。
3. **状态码 5 类**：1 信息、2 成功、3 重定向、4 客户端、5 服务端。
4. **缓存**：强缓存 vs 协商缓存（ETag / Last-Modified）。
5. **CORS 预检**：OPTIONS + `Access-Control-*`；带凭据时 Origin 不能 `*`。
6. **HSTS / CSP / SameSite** 三件套防 MITM/XSS/CSRF。
7. **HTTP/2** 单连接多路复用 + HPACK；HoL 仍在 TCP 层。
8. **HTTP/3** = HTTP over QUIC over UDP，连接迁移、0-RTT。
9. **REST** 用 HTTP 方法表达动作，名词资源、统一错误体、版本化。
10. **限流**：429 + Retry-After + 指数退避。

---

## 关联阅读

* [TCP UDP](TCP%20UDP.md) · [IO 多路复用](IO%20多路复用.md) · [网络编程 Socket](网络编程%20Socket.md) · [网络 最佳实践](网络%20最佳实践.md)
