# Tweets2Insights 文档索引

项目介绍、核心能力和首次启动步骤见[项目 README](../README.md)。

## 开始使用

| 任务 | 文档 |
|---|---|
| 安装、配置凭据、启动工作台 | [README：快速开始](../README.md#quickstart) |
| 上传数据并完成第一次分析 | [README：第一次分析](../README.md#first-analysis) |
| 使用本地事件 Demo，查看图文分析用量 | [本地 Demo 数据集](testing/event-demo-datasets.md) |
| CLI、任务管理、导出与兼容入口 | [运行手册](modules/domain-application.md) |
| 模型、环境变量、连接器和预算 | [应用配置](configuration.md) |
| 页面、会话与产物交互 | [前端说明](frontend-guide.md) |
| 本机启动、停止与日志 | [运行说明](deployment.md) |

## 理解架构与扩展

- [完整工作流](modules/full-workflow.md)：阶段依赖、论坛角色、41 个工具、决策模型、隐空间模型和报告 Agent。
- [系统架构](architecture.md)：架构总览图、应用分层、Agent 协作与数据流。
- [项目目录](project-structure.md)：应用入口、领域源码与兼容目录。
- [Agent Runtime](modules/agent-runtime-architecture.md)：Leader、子 Agent、记忆、检查点、MCP 与 SSE。
- [OpenUI 交互分析](modules/intelligent-ui.md)：组件库、模型流、真实数据绑定和情景实验接口。
- [Agent 复盘报告](modules/report-generation.md)：旧模板写作、Agent 排版、交互网页与 PDF 下载。
- [架构重写与迁移清单](modules/architecture-rewrite.md)：复用归属、连接器协议与数值假设。
- [贡献指南](../CONTRIBUTING.md)：环境、模块依赖和文档同步要求。
- [安全边界](../SECURITY.md)：本机部署、凭据、文件能力和访问控制范围。

## 数据与研究方法

- [数据契约与迁移](modules/opinion-contracts.md)：事件、数据版本、标签及无损历史迁移。
- [自动弱标注](modules/automatic-labeling.md)：搜索前置、冻结 Schema、字段状态和供应商接入。
- [搜索供应商](modules/search-providers.md)：Tavily/DeepSeek 配置、证据字段与调用方法。
- [领域 MCP 接入](modules/domain-gateway.md)：领域服务的基础接口与早期接入记录；当前启动方式以运行手册为准。

## 开发文档

- [升级实施记录](upgrade-status.md)：版本变更、检查结果及后续任务。
- [弱标注 Demo 协议](testing/weak-label-demo-protocol.md)：独立人工金标准、质量与覆盖率评测；不进入日常标注流程。
- [测试工作流](testing/testing_workflow.md)：测试分层、执行命令与用例映射。
- [启动页背景素材](diagrams/landing-background-prompt.md)：原创背景的素材路径与生成提示词。

## 历史与兼容文档

以下文档介绍保留的 PocketFlow、旧 Dashboard 和工具实现：

- [旧项目说明](../legacy/README.md) · [历史架构](legacy-architecture.md)
- [Stage 1 数据增强](modules/stage1_enhancement.md)
- [Stage 2 分析与论坛](modules/stage2_analysis.md)
- [Stage 3 报告生成](modules/stage3_report.md)
- [旧 Dashboard 结果查看器](modules/dashboard_results_viewer.md)
- [旧分析工具](modules/analysis_tools.md) · [通用工具](modules/utils.md)
- [旧 MCP 集成](mcp/mcp_integration.md) · [工具审计清单](mcp/mcp_tool_audit.md)
