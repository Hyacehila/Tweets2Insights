# Contributing

更新：2026-11-04。

- 后端位于 `backend/src`，Python 环境与锁文件由 UV 管理；使用 `uv sync --project backend`。
- 前端位于 `frontend/src`，使用 Next.js App Router、React、Tremor 组件、Tailwind CSS 和 Recharts，提交 package-lock.json；复用第三方组件时保留许可证。
- Agent harness（agents/models/mcp/tools/skills/subagents/config）不能反向导入 gateway。
- 领域算法位于 backend/src/domain；旧根目录同名包仅为兼容导入，不在两处复制修改。
- API 路由不得直接调用付费标注或采集长流程；提交持久任务，由独立 Worker 执行。
- 新模块同时维护 doc/architecture.md、目录表、接口说明和验证状态。
- README.md 是面向首次访问者的项目首页；修改能力、默认入口、环境要求或配置方式时同步更新对应段落。
- README 和用户手册介绍功能、安装、使用与架构；开发进度、检查结果和待办维护在开发文档中。
- 文档直接说明功能、用法和必要条件；测试结果集中记录在 doc/upgrade-status.md，性能指标附评测配置与来源。
- 开发规范见 AGENTS.md，测试命令见 doc/testing/testing_workflow.md。
- 不提交 .env、legacy/config.yaml、原始私密数据或运行资产；配置只保存环境变量名称。

命令：`make install`、`make dev`、`make stop`、`make check`。
Windows 无 make 时，安装和启动使用 README 中的 UV / npm 命令；静态检查执行：

```bash
uv run --project backend python scripts/check_structure.py
npm --prefix frontend run check
```

测试命令见[测试工作流](doc/testing/testing_workflow.md)，开发进度和检查结果见[实施记录](doc/upgrade-status.md)。
