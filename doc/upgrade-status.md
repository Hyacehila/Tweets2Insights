# 项目实施记录

更新：2026-11-04。开发分支：`refine`。

## 本地事件 Demo 与用量查看

新增逐日热度筛选与图片整理脚本，支持北京 Excel、河南清洗 JSON，源行映射、链接去重、损坏图片补选、GIF 首帧及超大图片副本均保留记录。生成 300 条河南图文试用集，以及各 10,000 条的河南文本／图文、北京文本 Demo。河南正式两版帖子集合一致；北京源文件没有配图。真实帖子和图片仅保存在本地忽略目录。

四个数据集已登记并载入工作台待执行计划。按用户选择，付费模型由用户点击启动，本轮没有运行真实模型复盘。300 条试用包含 611 个图片引用；正式河南图文版含 2,870 条带图帖、5,294 个图片引用。

任务结果新增分阶段调用与 Token 用量；金额缺失保持未知。修复重新进入会话时表单没有恢复已保存时间范围、数据集和标注上限的问题。总调用预算上限调整为 100000，为万条标注之外的搜索、论坛与报告留出调用空间。

检查：后端 127 项、历史模块 451 项、前端 10 项通过；历史套件 3 项缺少本机原始输入跳过、5 项真实 API/UI 测试排除。生产构建、类型及结构检查通过。浏览器核对 300 条计划的数据版本、历史时间范围、3 张图片上限、300 次标注上限与待执行状态；四个事件均无已提交任务。操作说明见[本地事件 Demo](testing/event-demo-datasets.md)。

## 发布者类型精简

`data/publisher_objects.json` 从 108 项收敛为政府机构、新闻媒体、自媒体、企业账号、事业单位、社会组织、个人用户 7 类；新默认流程的 `common-v1.json` 同步分类与边界定义，职业及部门不再单列。词库内容参与缓存指纹，已有冻结标注保持原定义。

删除 `data/publisher_decision.json`，移除兼容流程的关联身份节点、加载器、路径配置、导出及 Dashboard 设置项。旧 YAML 中的 `publisher_decision_path` 在加载时忽略，历史输入字段仍可保留读取。文档和对应测试同步更新。

检查：后端 85 项通过；根目录及 Dashboard 回归 451 项通过、3 项因原始数据文件缺失跳过、5 项真实 API/UI 测试排除。修复一项旧 Stage3 单元测试对本机增强数据文件的依赖，改用临时样本；新增无旧分类文件的数据加载与旧配置兼容回归。结构检查及两份发布者词库一致性检查通过。本机服务已重启加载更新。

## 事件删除与决策标注统一

“最近研究”增加中英文右键菜单和删除确认。删除范围为同一事件的全部会话、消息、记忆、检查点、领域任务与批次、标注缓存、预算记录以及分析/预测/情景/报告产物；导入和采集的数据集保留，使用同一事件 ID 新建研究后可继续选择。运行中或正在取消的任务阻止删除，排队任务在 SQLite 写锁内清理；文件移动失败时回滚，迟到的 Agent 事件不会重建已删除记录。

移除旧 GLM 标注设置卡、工作台选项、服务端标注枚举、适配器与后端 zai-sdk 依赖。标注统一采用 OpenAI Decisions、Jev、阿里 Decision 或决策连接器，CLI 默认 OpenAI Decisions。标签体系设计提取为通用 SchemaBuilder，继续使用所选 Agent 模型；GLM 作为生成式 Agent 的选项保留。修复 CLI 搜索凭据参数重复传入的问题。

检查：后端 85 项通过，历史模块 454 项通过（5 项真实 API/UI 测试按默认标记排除）；前端类型、4 项语言测试和生产构建通过。浏览器核验中文/英文右键菜单、删除范围、取消操作及 GLM 标注入口移除。删除回归使用临时数据库与产物；本机已有事件未删除。115 个后端源文件结构检查通过。真实模型标注与 Demo 效果评测继续后置。

## 通用 Agent 模型与 OpenAI 决策标注

Agent 配置支持 OpenAI 兼容 Chat Completions 接口，预设 Qwen3.8-Max 和 GLM-5.3，开放 Base URL、Model ID、API Key 和生成参数。界面提供能力要求和一次请求的 JSON 兼容性检测；检测失败不覆盖配置，凭据按端点分别保存。Leader、标签设计、论坛和报告共用适配器，任务冻结公开模型参数。

新增 OpenAI Decisions 原生适配器，`openai_decisions / gpt-6-luna` 成为新任务默认标注服务，保留 Jev、阿里 Decision 和 GLM。五个字段共享一次帖子输入，保留类别概率、confidence、unknown 与拒答；接入预算、版本缓存和字段弃权。前端增加独立 OpenAI API Key 入口，中英文同步。

Next.js 的 N 开发浮标已关闭，项目侧栏和设置入口保留。浏览器检查确认推荐预设切换、自定义接口输入、切换语言时表单保留、OpenAI 凭据入口及默认标注选项。

后端及相关契约回归 90 项通过；旧模块回归 455 项通过，5 项真实 API/UI 测试按默认标记排除。修复旧测试配置辅助器误读新应用 YAML 的问题，单元测试改用隔离配置与固定样本。113 个后端源文件结构检查、前端类型与生产构建通过，语言测试 4 项通过。供应商测试使用模拟响应；真实标注效果保留到独立 Demo 评测。

## Tremor 工作台与中英文界面

采用 Tremor Overview 组件，重组概览、研究、数据集、结果和 API 设置；统一图表、主题、移动端导航与报告操作。顶部支持中英文切换，保留当前输入并记住语言选择。
删除 Docker/K8s、旧外接 Agent 脚手架、独立 LangGraph 启动入口和仅创建空目录的线程工作区。领域存储隔离、MCP、技能、检查点和分析工具继续使用。
修复 MCP 自动输出模型丢失动态字典字段的问题，Gateway 改为读取完整结构化结果。新增真实 MCP 传输回归，覆盖任务、嵌套产物和分析工具目录。
本轮后端回归 71 项通过；结构检查覆盖 109 个后端 Python 源文件。前端语言检查 3 项通过，类型检查与生产构建通过。浏览器检查覆盖语言记忆、切换时输入保留、API 设置、移动端导航、报告图表与来源表分页；图表使用独立预览目录中的合成数据。
14 份本轮修改文档的 99 个本地文件链接及代码块检查通过。

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
- MediaCrawler 七个平台采集、平台登录配置与图文帖子输入。

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

真实模型质量与预测效果将在完成对应检查后更新。Demo 采用[预登记协议](testing/weak-label-demo-protocol.md)，正式数据处理自动标注后进入分析。

## 架构与文档迁移

| 提交 | 变更 | 当时的检查 |
|---|---|---|
| `8d3564a` | 重写 README，组织核心能力、快速开始、首次分析、架构、配置和文档导航 | 本地链接、页内锚点、代码块与示例语法检查 |
| `e073bd2` | 引入 backend/frontend/skills 分层；LangGraph Leader、FastAPI 六组路由、Next.js 工作台、检查点与 SSE | 后端语法、配置解析、导入、Ruff、wheel 及前端 TypeScript 检查 |
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
