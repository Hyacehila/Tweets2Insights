# Kubernetes 科研部署模板

此模板将 Gateway、Worker、Frontend、Nginx 放在一个 Pod，使用单副本和共享 PVC，适配当前 SQLite 运行范围。
部署前准备容器镜像、服务凭据与可用 StorageClass。公开访问的认证配置见 [安全说明](SECURITY.md)。

```bash
docker build -f docker/backend.Dockerfile -t tweets2insights-backend:0.2.0 .
docker build -f docker/frontend.Dockerfile -t tweets2insights-frontend:0.2.0 .
# 将镜像装入本地集群，或推入自己的镜像仓库后更新清单 image 字段
kubectl create secret generic tweets2insights-env --from-env-file=.env
kubectl apply -f docker/k8s/app.yaml
kubectl port-forward service/tweets2insights 2026:2026 --address 127.0.0.1
```

访问 http://127.0.0.1:2026。PVC 需有可用 StorageClass。
密钥留在 Kubernetes Secret；不要写进清单。节点调度与备份策略由实际集群决定。
