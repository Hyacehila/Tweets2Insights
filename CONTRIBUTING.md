# Contributing

更新：2026-11-03。

- 后端位于 `backend/src`，Python 环境与锁文件由 UV 管理；使用 `uv sync --project backend`。
- 前端位于 `frontend/src`，使用 Next.js App Router、React 和 TypeScript，提交 package-lock.json。
- Agent harness（agents/models/mcp/tools/skills/subagents/sandbox/config）不能反向导入 gateway。
- 领域算法位于 backend/src/domain；旧根目录同名包仅为兼容导入，不在两处复制修改。
- API 路由不得直接调用付费标注或采集长流程；提交持久任务，由独立 Worker 执行。
- 新模块同时维护 doc/architecture.md、目录表、接口说明和验证状态。
- 本次用户明确要求功能脚本完成后统一测试；默认开发规范见 AGENTS.md。静态检查与行为测试分别报告。
- 不提交 .env、legacy/config.yaml、原始私密数据或运行资产；配置只保存环境变量名称。

命令：`make install`、`make dev`、`make stop`、`make check`。
Windows 无 make 时使用 README 中对应 UV / npm 命令。
