# Docker 与 Kubernetes 基础

> 容器化与编排是现代后端 / 机器人 / AI 工程的部署底座。

---

## 1. 容器原理

### 1.1 容器 vs 虚拟机

| | 容器 | 虚拟机 |
|---|------|--------|
| 隔离层级 | 进程 (Linux ns + cgroup) | 硬件 (Hypervisor) |
| 启动速度 | 秒级 | 分钟级 |
| 资源开销 | MB 级 | GB 级 |
| OS | 共享宿主内核 | 独立 GuestOS |
| 安全 | 弱（共享内核） | 强 |
| 适用 | 微服务、CI/CD | 强隔离、跨内核 |

### 1.2 容器 = ?

容器 = **Namespace（隔离视图）+ Cgroup（资源限额）+ Image 层（OverlayFS 联合挂载）**。详见 [Linux 基础](../os/Linux%20基础.md)。

### 1.3 镜像分层

```
+---------------+ 容器可写层（Copy-on-Write）
+---------------+ 镜像层 N: CMD / ENTRYPOINT
+---------------+ 镜像层 ...: pip install
+---------------+ 镜像层 1: apt-get update
+---------------+ Base: ubuntu:24.04 / python:3.12-slim
```

每条 `RUN` / `COPY` / `ADD` 产生一层；只读、按内容寻址（sha256），可共享。

---

## 2. Docker 核心

### 2.1 命令速查

```bash
# 镜像
docker pull nginx:1.27-alpine
docker images
docker rmi <id>
docker build -t myapp:1.0 .
docker tag myapp:1.0 registry.example.com/team/myapp:1.0
docker push registry.example.com/team/myapp:1.0

# 容器
docker run -d --name web -p 8080:80 \
  -e ENV=prod -v $PWD/data:/data \
  --restart=unless-stopped --memory=512m --cpus=1 \
  nginx:1.27-alpine
docker ps -a
docker logs -f web
docker exec -it web sh
docker stop web && docker rm web

# 调试 / 排查
docker inspect web                       # 完整元数据
docker stats                             # 资源占用
docker top web                           # 进程
docker system df / prune                 # 空间
docker history myapp:1.0                 # 镜像层

# 网络 / 卷
docker network create app-net
docker volume create db-data
```

### 2.2 Dockerfile 关键指令

| 指令 | 用途 |
|------|------|
| `FROM` | 基础镜像（必须） |
| `RUN` | 构建期执行命令 |
| `COPY` / `ADD` | 复制；ADD 多支持 URL/解压（一般用 COPY） |
| `WORKDIR` | 设工作目录（不要用 RUN cd） |
| `ENV` / `ARG` | 环境变量 / 构建参数 |
| `EXPOSE` | 声明端口（仅文档） |
| `USER` | 切换非 root |
| `HEALTHCHECK` | 健康检查 |
| `ENTRYPOINT` + `CMD` | 启动命令；ENTRYPOINT 主程序 + CMD 默认参数 |

### 2.3 多阶段构建（必学）

```dockerfile
# ---------- builder ----------
FROM golang:1.23 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /out/app ./cmd/app

# ---------- runtime ----------
FROM gcr.io/distroless/static:nonroot
COPY --from=build /out/app /app
USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/app"]
```

* 镜像体积从 1 GB+ 降到 < 20 MB。
* 运行时不含编译器、shell（distroless）→ 攻击面小。

### 2.4 镜像优化要点

1. **Base 选小**：`alpine` / `distroless` / `slim`；GLIBC 兼容看依赖。
2. **合并 RUN**：`RUN apt-get update && apt-get install -y x y && rm -rf /var/lib/apt/lists/*`。
3. **缓存友好**：先拷依赖清单（`go.mod` / `package.json` / `requirements.txt`） + 安装，再拷源码。
4. **`.dockerignore`**：排除 `.git` `node_modules` `*.pyc`。
5. **固定版本**：`python:3.12.7-slim` 而非 `latest`。
6. **多平台**：`docker buildx build --platform linux/amd64,linux/arm64`。
7. **签名 / 扫描**：cosign + trivy / grype 集成 CI。

### 2.5 Compose 本地开发

```yaml
# docker-compose.yml
services:
  api:
    build: .
    ports: ["8080:8080"]
    environment:
      DATABASE_URL: postgres://user:pass@db:5432/app
    depends_on:
      db: { condition: service_healthy }
  db:
    image: postgres:16-alpine
    environment: { POSTGRES_PASSWORD: pass, POSTGRES_DB: app }
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "postgres"]
      interval: 5s
volumes: { pgdata: }
```

`docker compose up -d` / `down` / `logs -f api`。

### 2.6 网络与存储

* **bridge**（默认）：容器间通过容器名解析；
* **host**：共享宿主网络栈，性能高但端口冲突；
* **overlay**：Swarm / 跨主机；
* **none**：无网络。
* **volumes**（推荐）由 Docker 管理；**bind mount** 绑定宿主路径（开发常用）；**tmpfs** 内存。

---

## 3. Kubernetes 核心

### 3.1 架构

```
            +----------------+
            |  控制面 Master |
            |  api-server    |←── kubectl / kubeadm / clients
            |  etcd          |
            |  scheduler     |
            |  controller-mgr|
            +-------+--------+
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   +--------+  +--------+  +--------+
   | Node 1 |  | Node 2 |  | Node N |
   |kubelet |  |kubelet |  |kubelet |
   |kube-pxy|  |kube-pxy|  |kube-pxy|
   |container runtime (containerd)|
   +--------+  +--------+  +--------+
```

* **api-server**：唯一对外入口，REST + 认证授权。
* **etcd**：强一致 KV，存所有集群状态。
* **scheduler**：把 Pod 调度到节点。
* **controller-manager**：各种 controller（Deployment、Node、Endpoint…）调谐到期望状态。
* **kubelet**：节点代理，管 Pod 生命周期。
* **kube-proxy**：Service IP → Pod 转发（iptables / IPVS / eBPF）。
* **CNI**（Calico / Cilium / Flannel）：网络插件。
* **CRI**（containerd / CRI-O）：运行时。
* **CSI**：存储插件。

### 3.2 核心对象

| 对象 | 作用 |
|------|------|
| **Pod** | 最小调度单元，1 个或多个共享网络/存储的容器 |
| **ReplicaSet** | 维持 N 个 Pod 副本 |
| **Deployment** | 管理 RS，提供滚动更新 / 回滚 |
| **StatefulSet** | 有状态：稳定 Pod 名 + 持久存储（DB） |
| **DaemonSet** | 每节点一个（日志、监控代理） |
| **Job / CronJob** | 一次性 / 定时任务 |
| **Service** | 稳定 ClusterIP / DNS，4 层负载均衡（Pod 抽象） |
| **Ingress** | 7 层路由（域名 / 路径 → Service） |
| **ConfigMap / Secret** | 配置与敏感数据 |
| **PersistentVolume / PVC** | 存储申明 |
| **Namespace** | 逻辑隔离 |
| **HorizontalPodAutoscaler** | 按 CPU / 自定义指标扩缩 |
| **NetworkPolicy** | 网络访问控制 |
| **ServiceAccount + RBAC Role/RoleBinding** | 认证授权 |

### 3.3 一个最小 Deployment + Service

```yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: api, labels: { app: api } }
spec:
  replicas: 3
  selector: { matchLabels: { app: api } }
  strategy:
    type: RollingUpdate
    rollingUpdate: { maxSurge: 1, maxUnavailable: 0 }
  template:
    metadata: { labels: { app: api } }
    spec:
      containers:
        - name: api
          image: registry.example.com/api:1.4.2
          ports: [{ containerPort: 8080 }]
          resources:
            requests: { cpu: 100m, memory: 128Mi }
            limits:   { cpu: 500m, memory: 512Mi }
          readinessProbe:
            httpGet: { path: /healthz, port: 8080 }
            periodSeconds: 5
          livenessProbe:
            httpGet: { path: /livez, port: 8080 }
            initialDelaySeconds: 30
          env:
            - name: DB_URL
              valueFrom: { secretKeyRef: { name: db, key: url } }
---
apiVersion: v1
kind: Service
metadata: { name: api }
spec:
  selector: { app: api }
  ports: [{ port: 80, targetPort: 8080 }]
  type: ClusterIP
```

### 3.4 调度与伸缩

* `requests` 用于调度，`limits` 用于运行时上限（OOMKilled / CPU 限频）。
* **HPA**：CPU / 内存 / Prometheus 自定义指标。
* **VPA**：自动调 requests / limits。
* **Cluster Autoscaler**：节点级伸缩。
* **亲和 / 反亲和 / 污点容忍**：拓扑分布、避免单点。
* **PodDisruptionBudget**：自愿驱逐时保最小可用。

### 3.5 滚动更新 / 回滚 / 蓝绿 / 金丝雀

```bash
kubectl set image deploy/api api=registry/api:1.4.3 --record
kubectl rollout status deploy/api
kubectl rollout undo deploy/api
```

* **金丝雀**：Argo Rollouts / Flagger 按权重渐进，配合 SLO 指标自动回滚。
* **蓝绿**：两套 Deployment + Service 切换。

### 3.6 健康检查

| 探针 | 用途 |
|------|------|
| **startupProbe** | 启动慢的服务，启动期不算 liveness |
| **readinessProbe** | 失败则从 Service 摘除（不重启）|
| **livenessProbe** | 失败则**重启容器** |

**坑**：探针超时短 + 慢 GC → 误杀；要差异化配置。

### 3.7 配置 / 密钥

* `ConfigMap` 明文配置；`Secret` base64（默认非加密，需 KMS / Sealed Secrets / External Secrets）。
* 通过 env / volume 挂载注入；改 ConfigMap 不会自动重启 Pod（需 reloader / 重启 Deployment）。

### 3.8 网络模型

* 每 Pod 独立 IP，跨节点直连，无 NAT。
* `Service.ClusterIP`：稳定虚拟 IP，kube-proxy 做转发。
* `NodePort`：每节点开端口。
* `LoadBalancer`：云厂商 LB。
* `Ingress`：7 层路由 + TLS 终端（nginx-ingress / Traefik / Istio Gateway）。
* **Service Mesh**（Istio / Linkerd）：mTLS、灰度、熔断。

### 3.9 存储

* PV（管理员定义）/ PVC（用户申请）。
* AccessMode：RWO（单节点读写） / ROX / RWX。
* StorageClass + Provisioner（CSI）动态创建。
* 有状态服务（DB、消息队列）用 StatefulSet + 本地 PV / 远端块存储。

---

## 4. 可观测性与排查

| 命令 | 用途 |
|------|------|
| `kubectl get pods -A -o wide` | 集群总览 |
| `kubectl describe pod X` | 事件 / 调度信息 / 探针失败原因 |
| `kubectl logs -f X -c container --previous` | 日志 / 上次崩溃日志 |
| `kubectl exec -it X -- sh` | 进容器调试 |
| `kubectl top pod / node` | 资源占用（需 metrics-server） |
| `kubectl rollout history deploy/X` | 部署历史 |
| `kubectl get events --sort-by=.lastTimestamp` | 集群事件 |
| `crictl ps / logs / inspect` | 直接看 containerd 容器 |

常见问题速查：
* `CrashLoopBackOff`：进程退出 / 启动失败 / 探针误杀 → describe + logs --previous。
* `ImagePullBackOff`：镜像拉不动（私库密钥 / tag 不存在 / 网络）。
* `Pending`：节点资源不足 / 调度约束 / PVC 未绑定。
* `OOMKilled`：内存超限，调 limits 或排查泄漏。
* `Evicted`：节点资源压力，调 priority / requests。

---

## 5. 安全基线

1. **Image**：扫描（trivy / grype）、签名（cosign）、最小 Base、定期重建。
2. **Pod Security**：`securityContext` 设 `runAsNonRoot: true`、`readOnlyRootFilesystem: true`、`allowPrivilegeEscalation: false`、丢弃 capabilities。
3. **RBAC** 最小权限；ServiceAccount 一服务一身份。
4. **NetworkPolicy** 默认拒绝 + 白名单。
5. **Secret** 不入 Git；用 SOPS / Sealed Secrets / Vault / KMS。
6. **Ingress** 强制 HTTPS + HSTS；mTLS 内部。
7. **Audit Log** 开启；接 SIEM。
8. **节点**：不要把宿主关键路径 hostPath 挂进容器；禁 privileged 除非必须。

---

## 6. 高频面试题

1. 容器与虚拟机区别？容器为什么轻量？（共享内核 + ns + cgroup）
2. Docker 镜像分层原理；如何减小体积？
3. `ENTRYPOINT` vs `CMD`；如何传参？
4. Pod 内多容器为什么共享网络和存储？（pause 容器持有 ns）
5. Service 的 4 种类型；ClusterIP 怎么实现？
6. Deployment 滚动更新过程；maxSurge/maxUnavailable 含义？
7. StatefulSet 与 Deployment 区别？
8. liveness / readiness / startup 区别？误杀怎么办？
9. CrashLoopBackOff 怎么排查？
10. HPA 工作原理；如何用自定义指标扩缩？
11. K8s 网络模型 + CNI 插件作用？
12. ConfigMap 改了 Pod 会重启吗？怎么自动 reload？
13. RollingUpdate / 蓝绿 / 金丝雀 区别与实现？
14. K8s 怎么实现高可用？（multi-master + etcd 集群 + LB）
15. Pod 为什么 Pending？怎么排查？
16. 容器内时间不对 / 时区问题怎么解？（挂 `/etc/localtime` 或设 TZ）
17. `kubectl apply` vs `create` vs `replace`？
18. Operator 模式是什么？CRD 怎么用？
19. Helm vs Kustomize 区别？
20. 多集群管理（Karmada / Argo CD App-of-Apps）？

---

## 7. Top 20 容器化 Checklist

1. ☐ Dockerfile 多阶段 + distroless / alpine。
2. ☐ 非 root 用户 + 只读根文件系统 + drop capabilities。
3. ☐ `.dockerignore` 完整；构建上下文最小。
4. ☐ 镜像 tag 固定语义化版本，不用 `latest`。
5. ☐ CI 集成 trivy / grype 扫描 + cosign 签名。
6. ☐ 镜像仓库私有 + 拉取密钥 + 镜像签名校验。
7. ☐ Pod 配 resources requests + limits；不要不写。
8. ☐ liveness / readiness / startup 三探针差异化配置。
9. ☐ 配置 + 密钥用 ConfigMap / External Secrets，不写镜像。
10. ☐ 滚动更新 maxUnavailable=0 保零中断；PDB ≥ 1。
11. ☐ HPA + 合理 metrics；冷启动慢的服务配 startupProbe。
12. ☐ 应用做优雅停机：捕获 SIGTERM + preStop hook。
13. ☐ 日志输出 stdout/stderr，由 sidecar / DaemonSet 收集。
14. ☐ Prometheus / OpenTelemetry metrics + traces 接入。
15. ☐ NetworkPolicy 默认拒绝 + 显式白名单。
16. ☐ RBAC 最小权限；禁用 default ServiceAccount 自动挂载。
17. ☐ 命名空间隔离环境（dev / staging / prod）+ ResourceQuota。
18. ☐ GitOps（Argo CD / Flux）声明式管控；禁手工 kubectl apply 到 prod。
19. ☐ 集群备份：etcd 定期 + Velero。
20. ☐ 故障演练：节点挂、网络分区、磁盘满、镜像仓库挂。

---

## 面试速记

1. **容器 = ns + cgroup + overlayfs**。
2. **多阶段构建** 是镜像瘦身首选。
3. **Pod 是最小调度单元**，不是容器。
4. **Service ClusterIP** 由 kube-proxy 通过 iptables/IPVS 转发。
5. **Deployment** 管 ReplicaSet 管 Pod。
6. **StatefulSet** 有稳定名 + 稳定存储。
7. **3 探针**：startup（启动）/ readiness（摘流）/ liveness（重启）。
8. **资源**：requests 调度，limits 上限；超内存 OOMKilled。
9. **HPA** 默认基于 CPU；自定义指标走 metrics-adapter。
10. **滚动更新** 默认 25% surge / unavailable，零中断改 maxUnavailable=0。
11. **CrashLoopBackOff**：先 `describe` 再 `logs --previous`。
12. **GitOps + Helm/Kustomize** 是声明式部署标配。

---

## 关联阅读

* [Linux 基础](../os/Linux%20基础.md)
* [架构 最佳实践](../architecture/架构%20最佳实践.md) · [微服务架构](../architecture/微服务架构.md)
* [工具链 最佳实践](../tools/工具链%20最佳实践.md)
* [网络 最佳实践](../network/网络%20最佳实践.md)
