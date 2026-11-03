# 项目实施记录

更新：2026-11-03。开发分支：`refine`。最新功能提交：`1bbf000`。

## 文档整理

统一项目目录标题，精简 README、架构、模块、部署和评测说明中的重复声明；模块文档侧重功能与用法，测试进度集中在本页。
同步 MCP 工具数量、标注词库路径及兼容入口说明，按版本整理历史检查记录。
27 份文档的 133 个本地链接及页内锚点检查通过，代码块闭合检查通过。

## 当前功能

- 前端选择数据或关键词输入，以及复盘、训练预测、情景和滚动诊断阶段；Leader 编译依赖，DomainWorker 依次执行。
- 高阅读量随机样本用于 Schema 选词，正式标注和统计使用观测范围内的全部适用记录。
- Jev / 阿里 System One 原生适配、字段概率与差距拒判、独立 Agent 模型，以及本机凭据配置。
- 41 个分析入口接入新契约，结果保存源表、覆盖率、参数和指纹；支持独立补充分析任务。
- data/search/visual/insight/methodology 角色按需启用，ForumHost 协调工具、补搜、补图、分歧与停止条件。
- 内容整理、社科解释、页面布局三个 Agent 生成交互报告，展示论坛过程、预测分布和配对情景。
- 实验模型采用 PCA、隐空间联合 HK 和解码摘要同化；包含训练内滚动参数选择及六种模型/基线诊断。
- 情景支持三类措施机制、共享随机流配对、成本与方差 Pareto 对照和条件建议。
- X 官方归档搜索适配器；其他平台和多模态通过操作者连接器扩展。

流程与源码位置见[完整工作流](modules/full-workflow.md)和[迁移清单](modules/architecture-rewrite.md)。

## 已完成的检查

以下为 `1bbf000` 对应的离线检查结果。测试数据采用合成记录与供应商替身。

| 检查 | 结果 |
|---|---|
| 新后端套件及 4 个既有契约/标注模块 | 70 项通过，其中新后端 53 项；覆盖工具、阶段选择、模型约束、论坛补调用、MCP 工具目录和 Worker 产物链 |
| `uv run --project backend python scripts/check_structure.py` | 112 个后端 Python 文件与 JSON/YAML 配置解析通过，依赖方向检查通过 |
| `uv run --project backend ruff check backend/src backend/tests --select E9,F` | 通过 |
| `npm --prefix frontend run build` | Next.js 生产构建、类型检查和路由生成通过 |
| `uv build --project backend --wheel --out-dir backend/dist` | wheel 构建通过 |
| 文档本地链接检查 | 109 个相对链接可解析 |

测试命令：

```powershell
uv run --project backend pytest backend/tests tests/unit/core/test_glm_label_provider.py tests/unit/core/test_weak_labeling.py tests/unit/core/test_event_preparation.py tests/unit/core/test_opinion_contracts.py -q
```

实体共现测试夹具已补充抽取器支持的 `#话题#` 格式。测试仍有第三方 Authlib 弃用提示，断言均通过。

## 后续验证

功能脚本完成后，按以下范围开展服务联调和研究评测：

| 范围 | 待完成任务 |
|---|---|
| 真实服务 | 配置并联调 Jev、阿里 decision、GLM、所选搜索服务、X 采集和其他连接器；记录用量与费用 |
| 浏览器与运行时 | 验证前端到 Worker 的完整流程、会话隔离、图检查点、取消重连、角色限制、上传及产物访问 |
| 弱标注 Demo | 建立 600 条人工金标准，按 200/400 划分校准与独立测试集，评估逐字段质量、覆盖率、基线差异与成本 |
| 预测与情景 | 数值验证、滚动回测、预测区间覆盖、模型基线、措施效果与多模态消融 |
| 部署 | 启动并检查 Docker Compose 与 Kubernetes 环境 |

真实模型质量、预测效果和部署结果将在完成对应检查后更新。Demo 采用[预登记协议](testing/weak-label-demo-protocol.md)，正式数据处理自动标注后进入分析。

## 架构与文档迁移

| 提交 | 变更 | 当时的检查 |
|---|---|---|
| `8d3564a` | 重写 README，组织核心能力、快速开始、首次分析、架构、配置和文档导航 | 本地链接、页内锚点、代码块与示例语法检查 |
| `e073bd2` | 引入 backend/frontend/skills/docker 分层；LangGraph Leader、FastAPI 六组路由、Next.js 工作台、检查点与 SSE | 后端语法、配置解析、导入、Ruff、wheel 及前端 TypeScript 检查 |
| `7bb678f` | 领域架构重写，迁移可复用算法、任务、预算、报告与连接器；根目录旧包保留兼容转发 | 58 个新增/修改 Python 文件 AST 解析、关键导入及依赖方向检查 |

新应用使用 `backend/src/domain` 中的领域实现。原 PocketFlow 入口、Streamlit 专项图表和 PDF 导出保留兼容路径，见[项目目录](project-structure.md)和[运行手册](modules/domain-application.md)。

## 早期领域开发记录

以下记录对应前后端架构迁移之前的领域开发阶段，初始代码基线为 `c29743a`。

### 契约、隔离与基础 MCP

| 阶段 | 实现与修复 | 检查记录 |
|---|---|---|
| PR-01 契约与迁移 | Pydantic 版本化契约、旧标签迁移；补充旧 Stage1 `topics` 列表兼容 | 契约、迁移、格式和 Stage1 定向测试 24 项通过 |
| PR-02 运行隔离 | SHA256 事件/运行目录、数据指纹、原子写入、JobStore、修订号、租约、批次幂等与取消竞争处理 | 定向测试 13 项通过 |
| PR-03 资料概览 MCP | 注册、统计、分页证据、短报告、产物、任务查询和取消共 7 个接口；复用 IR 渲染器 | 定向测试 19 项通过，含 Windows stdio 子进程 |
| PR-04 搜索单选 | Tavily/DeepSeek 适配、统一证据卡、旧接口兼容和 Dashboard 单选配置 | 定向测试 46 项通过 |

隔离修复包括 Windows 路径大小写碰撞、渲染期间取消、源码指纹记录与旧运行锁 PID 探测。
PID 检查改用隐藏的 tasklist；IR 纯渲染函数提取到 `opinion_core/reporting/ir_markdown.py`，减少 stdio 启动导入。
相关 stdio 链路及回归 10 项通过。

当时的搜索联调记录：Tavily 单查询返回 authentication，DeepSeek 缺少环境凭据。后续功能实现阶段未重新执行这两项调用。

### 持久 Worker、自动标注与 Demo 评分

| 提交 | 变更 |
|---|---|
| `1d36c41` | InventoryWorker、排队提交、租约令牌、阶段检查点、原子发布、取消重试；工作台支持任务列表、新会话恢复和下载 |
| `b2fb4b3` | 搜索前置 schema、固定词库与命题、GLM JSON 标注、字段校验和拒判、版本缓存、持久调用预算与 CLI |
| `44ea523` | 独立 Demo 评分器：200/400 划分、F1、覆盖率、基线比较、混淆矩阵、分组泄漏与命题检查 |

后续修复了 0.03 差值的浮点边界、基线缺失输出误通过，以及失败搜索继承旧 builder 用量的问题。
数值比较采用 1e-12 容差；基线 missing/failed 阻止对应字段通过，未知调用费用单独记录。

### 历史回归快照

默认命令为 `uv run pytest tests dashboard/tests -v`，跳过 live_api/ui_e2e。

| 阶段 | 结果 |
|---|---|
| PR-01 至 PR-03 | 413 passed / 1 skipped / 4 deselected |
| 第一轮修复 | 425 passed / 1 skipped / 5 deselected，21.38 秒 |
| 持久 Worker 与工作台 | 432 passed / 1 skipped / 5 deselected |
| 自动标注与 Demo 评分 | 454 passed / 1 skipped / 5 deselected，32.90 秒 |

上述各次回归均有 4 个既有 Matplotlib 图表警告。覆盖范围包括本机 Worker 子进程、MCP stdio 和 Streamlit AppTest。
Demo 评分 CLI 另使用合成预测检查退出码：通过为 0，基线缺失为 2，并核验 JSON 输出。

本机日志位于 `.opinion-assets/validation/offline.txt`、`second-round.txt`，合成 CLI 产物位于同目录的 `synthetic-demo-cli/`。
