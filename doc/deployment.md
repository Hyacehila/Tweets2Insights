# 启动与部署

更新：2026-11-03。以下命令已提供脚本/模板，尚未进行端到端启动和部署验证。

环境要求、获取代码和 `.env` 初始化见 [README：快速开始](../README.md#quickstart)。本页补充进程管理与容器部署。

## 本机

```powershell
uv sync --project backend --frozen
npm --prefix frontend ci
uv run --project backend python scripts/dev.py start
uv run --project backend python scripts/dev.py stop
```

启动器管理 Gateway、领域 Worker、Next.js 开发服务器；默认前端 127.0.0.1:3000、Gateway 127.0.0.1:8001。
日志和进程记录位于 `.app-state`；停止前核对 PID、创建时间及命令，只停止本启动器拥有的进程。
Windows 进程以无窗口方式启动。只运行一个 Gateway 进程，不使用多副本共享 SQLite 会话状态。
主配置中的 Gateway host/port 同时用于启动器和前端代理；前端开发端口固定为 3000。

## Compose

```powershell
docker compose -f docker/docker-compose-dev.yaml up --build
docker compose -f docker/docker-compose-production.yaml up --build -d
```

二选一使用，入口均为 127.0.0.1:2026；四个服务为 backend、worker、frontend、nginx。
backend 与 worker 共享 research-data 卷。使用 `.env` 传递变量，但不把它复制进镜像。
开发模板的后端挂载源码并启用 reload；前端仍由 Dockerfile 构建，未配置热重载。
`T2I_CONNECTORS_FILE` 等路径需在容器内有效；真实连接器应由操作者额外挂载/安装。

## Kubernetes

见 [K8S_QUICK_START.md](../K8S_QUICK_START.md)。模板采用一个 Pod、四个容器、共享 PVC、Secret 引用，
仅提供 ClusterIP 与本机端口转发。需要自行构建/推送镜像并准备真实凭据和存储。
模板没有完成集群验证，也未提供公网认证或多租户部署能力。
