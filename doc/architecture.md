# Tweets2Insights 项目架构

更新：2026-11-03。默认应用采用 Next.js + FastAPI + LangGraph；领域任务由独立 Worker 执行。
DeerFlow 提供运行时分层参考，业务阶段独立设计；论坛以本项目原第二阶段为直接基础，角色和补证路径由任务决定。参考范围见 [Agent Runtime 说明](modules/agent-runtime-architecture.md)。

## 分层与依赖方向

```mermaid
flowchart TD
  UI[Next.js 工作台] --> API[FastAPI Gateway / 6 组路由]
  API --> RUN[LangGraph Leader / 会话运行管理]
  RUN --> CTX[中间件 / 记忆 / SQLite 检查点]
  RUN --> SUB[受限专业子 Agent]
  RUN --> TOOLS[工具入口 / MCP Client]
  TOOLS --> DOMAIN[Domain Tool Service]
  CLI[兼容 CLI] --> DOMAIN
  DOMAIN --> JOB[冻结请求 / 持久作业 / 版本资产]
  JOB --> WORKER[独立 Domain Worker]
  WORKER --> INPUT[已有数据 / 独立采集进程]
  INPUT --> SAMPLE[高阅读量池随机样本 / Schema Agent]
  SAMPLE --> LABEL[Jev / 阿里 decision / GLM 自动弱标注]
  LABEL --> OBS[分布观测 / 来源表]
  OBS --> EVIDENCE[工具选择与执行 / 按需角色论坛 / 补证反馈]
  OBS --> MODEL[PCA 训练 / 隐空间联合 HK / 同化 / 解码 / 情景]
  EVIDENCE --> CONTENT[内容 Agent / 社科 Agent / UI Agent / 引用校验]
  MODEL --> CONTENT
  CONTENT --> ARTIFACT[报告 / 图表 / 可追溯产物]
  ARTIFACT --> API
```

| 层 | 实际位置 | 职责 |
|---|---|---|
| 前端 | `frontend/src` | 会话、上传、结构化配置、SSE 状态、任务及产物 |
| 应用层 | `backend/src/gateway` | HTTP 协议、生命周期、事件范围、会话执行 |
| Agent Runtime | `backend/src/agents`、`subagents` | LangGraph 图、上下文、检查点、有限专业评阅 |
| 通用能力 | `backend/src/models`、`mcp`、`tools`、`skills`、`sandbox`、`config` | 模型和工具适配、技能、受限文件区、配置 |
| 领域核心 | `backend/src/domain/opinion_core` | 契约、确定性计划、弱标注、分析、实验模型和报告 |
| 领域应用服务 | `backend/src/domain/opinion_gateway` | MCP、冻结请求、JobStore、预算、资产和独立 Worker |
| 采集进程 | `backend/src/domain/crawler_worker` | 按需采集、限额、分页、去重和恢复 |

Gateway 可以调用 Runtime；Runtime 不导入 Gateway。领域核心不依赖 Next.js、HTTP 或 LangGraph。
应用包使用 `src.*` 命名空间，避免 `src/mcp` 与第三方 `mcp` 包、`src/config` 与旧 `config.py` 冲突。

## 会话与领域任务

会话状态保存在 `.app-state`，包括线程、消息、显式记忆、SSE 事件和图检查点。
事件数据与领域任务保存在 `.opinion-assets`，按 event/dataset/run 隔离。
Leader 生成或校验 RunRequest；领域 Worker 是唯一领域执行调度者。停止 Agent 与取消已提交 Job 分别操作。
SSE 支持游标续读；Gateway 重启会将未结束的 Agent execution 标为 interrupted，不自动重发模型请求。

## 研究约束

生产流程自动标注，人工真值用于独立 Demo 的质量与覆盖率评估。
标签采用平面 topic、publisher、emotion、sentiment 和 target-bound stance；缺失、失败、拒判、中性分开保存。
观测使用所有满足筛选条件的帖子并记录各字段分母；虚拟粒子数不替代真实样本量。
产物区分 observed、forecast、simulated 和 interpretation，数值由领域模块计算，Agent 负责组织与解读。

## 项目目录

完整目录见[项目目录](project-structure.md)。
复用文件已实际迁入 `backend/src/domain`；根目录旧包保留导入兼容入口，不维护另一份领域实现。
迁移明细见 [重写与复用清单](modules/architecture-rewrite.md)，启动见 [运行手册](modules/domain-application.md)。

各阶段的执行流程见[完整工作流](modules/full-workflow.md)，测试进度见[实施记录](upgrade-status.md)。
