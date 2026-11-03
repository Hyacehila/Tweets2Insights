# Tweets2Insights

更新：2026-11-03。主架构为 Leader 计划编译、Domain Tool Service、独立 Worker 和智能工作台。
旧 PocketFlow 入口位于 `legacy/main.py`；新任务不导入旧编排或旧标签工具。

## 使用

```powershell
uv sync
uv run python main.py register --event rain --file posts.json
uv run python main.py plan --request run.json
uv run python main.py submit --request run.json
uv run python main.py worker
uv run streamlit run intelligent_ui/app.py
```

请求模板：[configs/domain-run.example.json](configs/domain-run.example.json)。先用注册返回的 dataset_id 替换模板引用。
注册和计划预览不调用模型；Worker 根据冻结配置执行唯一搜索供应商、自动标注和后续阶段。
生产流程没有人工复核；人工金标准仅用于后置的独立 Demo。

## 文档与状态

- [架构](doc/architecture.md)
- [迁移与复用清单](doc/modules/architecture-rewrite.md)
- [新入口运行方法](doc/modules/domain-application.md)
- [实施记录](doc/upgrade-status.md)
- [Demo 协议](doc/testing/weak-label-demo-protocol.md)

新架构的脚本实现不等于真实平台、真实模型或数值研究已经验收。采集/决策/视觉连接器由操作者配置，
不包含虚构端点；HK、回测与情景模块标为实验实现。测试按用户要求安排在功能脚本完成后统一执行。
旧版文档保存在 [legacy/README.md](legacy/README.md)，其中历史运行说明仅适用于兼容入口。
