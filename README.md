# Tweets2Insights

更新：2026-11-03。按 DeerFlow 的分层方式构建事件研究工作台：Next.js 前端、FastAPI Gateway、
LangGraph Leader、MCP 领域工具及独立 Worker。已有标注、分析、预测、情景和报告代码迁入 `backend/src/domain`。

## 本机启动

在当前业务仓库运行；需要 UV、Python 3.12+ 和 Node.js 22+。

```powershell
uv sync --project backend
npm --prefix frontend ci
# 首次使用时将 .env.example 复制为 .env，填写所用服务的密钥
uv run --project backend python scripts/dev.py start
# 停止本启动器拥有的进程
uv run --project backend python scripts/dev.py stop
```

默认工作台 `http://127.0.0.1:3000`，Gateway `http://127.0.0.1:8001`。
`config.yaml` 控制应用与模型；`extensions_config.json` 配置 MCP 和技能；密钥保存在忽略文件 `.env`。
启动器同时管理 Gateway、领域 Worker 和前端，日志位于 `.app-state`。
Windows 也可执行 `scripts/run_dashboard.ps1`；支持 Make 的环境可使用 `make install/dev/stop/check`。

生产流程自动弱标注，不设置人工逐条复核。人工金标准仅用于后置独立 Demo。
已有数据入口不会触发采集；搜索供应商在请求中唯一确定。采集、决策模型及视觉服务需要配置真实连接器。

## 文档

- [2.7 项目目录结构总览](doc/project-structure.md)
- [系统架构](doc/architecture.md)与[Agent Runtime 说明](doc/modules/agent-runtime-architecture.md)
- [运行手册](doc/modules/domain-application.md)、[配置](doc/configuration.md)与[部署](doc/deployment.md)
- [迁移及复用清单](doc/modules/architecture-rewrite.md)、[前端说明](doc/frontend-guide.md)
- [实施记录](doc/upgrade-status.md)与[Demo 协议](doc/testing/weak-label-demo-protocol.md)

当前已完成源码迁移与架构脚本，已做语法、关键导入和 TypeScript 类型检查。
按用户指定顺序，功能与端到端测试、Demo、真实标注和数值研究验收后置；不将静态检查视为业务通过。
Docker/K8s 尚未部署验证。当前面向本机单操作者，详细边界见 [SECURITY.md](SECURITY.md)。

原领域 CLI、Streamlit 专项视图、PDF 导出与 PocketFlow 入口保留兼容，见[运行手册](doc/modules/domain-application.md)。
参考的 DeerFlow 版本与差异在 Agent Runtime 文档中列明；本项目没有复制上游源码或宣称全功能等价。
