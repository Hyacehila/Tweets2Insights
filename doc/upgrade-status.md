# 升级实施记录

更新：2026-11-03。代码基线 c29743a，开发分支 refine。

## 最新：完整阶段工作流与原第二阶段论坛改进

在 README 提交 8d3564a 基础上，实现本轮用户确认的完整业务路径。DeerFlow 仅作为运行时分层参考，
论坛沿用本项目原 Stage 2 的选工具、执行、补图、补搜和主持反馈能力，按任务启用角色。

- 前端选择输入路径及复盘/训练预测/情景/滚动诊断；Leader 编译前置依赖，唯一 Worker 依次执行。
- 高阅读量随机抽样用于 Schema 选词；观测时间范围外的数据不进入样本，正式统计不被抽样截断。
- 原生 Jev/阿里 System One 适配、概率与差距拒判、独立生成式 Agent 模型；本机写入式凭据配置。
- 41 个分析入口完成新契约接线；结果含源表、覆盖、参数、指纹。补充工具可作为独立作业提交。
- 可配置 data/search/visual/insight/methodology + ForumHost；类型化补调用、去重、预算、分歧和停止原因。
- 内容整理、社科解释、页面布局三个 Agent；交互报告、论坛过程、预测分布和配对情景图表。
- PCA 训练、隐空间联合 HK、解码摘要同化、训练内滚动参数选择、六种模型/基线诊断。
- 三类措施机制、共享随机流配对、资源成本与方差 Pareto 对照、条件建议；模型标为 experimental。
- X 官方归档搜索已写入；其他平台和多模态仍通过操作者连接器接入。真实服务未调用。

脚本接线完成后执行离线工程检查：

| 检查 | 结果及含义 |
|---|---|
| 新后端套件 + 4 个既有契约/标注单元模块 | 共 70 项通过，其中新套件 53 项；合成记录和供应商替身，覆盖 41 个工具、阶段选择、模型边界、论坛补调用、真实 MCP 目录及 Worker 资产链 |
| `uv run --project backend python scripts/check_structure.py` | 112 个后端 Python 源码与 JSON/YAML 可解析，依赖方向检查通过 |
| `uv run --project backend ruff check backend/src backend/tests --select E9,F` | 清理无用绑定后通过；不改变原 Demo 校验逻辑 |
| `npm --prefix frontend run build` | Next.js 生产构建、类型检查、路由生成通过 |
| `uv build --project backend --wheel --out-dir backend/dist` | 后端 wheel 构建通过 |
| 文档本地链接检查 | 109 个相对链接可解析 |

离线检查命令：

```powershell
uv run --project backend pytest backend/tests tests/unit/core/test_glm_label_provider.py tests/unit/core/test_weak_labeling.py tests/unit/core/test_event_preparation.py tests/unit/core/test_opinion_contracts.py -q
```

首轮实体共现用例没有提供该规则抽取器支持的 `#话题#`，修正夹具并明确工具仅识别标签/提及；
未修改工具来伪造实体。第三方 Authlib 弃用提示仍存在，未影响离线检查。
上述结果不代表真实 API、浏览器交互、人工 Demo、预测收益、区间覆盖或 Docker/K8s 已验收。
未运行旧全仓真实服务套件；下方早期记录为历史快照，不与当前结果混用。

设计、源码对应、兼容语义与待验收范围见[完整工作流](modules/full-workflow.md)。

## 历史：项目 README 与文档入口重写

在架构提交 e073bd2 之后，独立重写根 README，作为面向首次访问者的项目首页。
参考 DeerFlow、BettaFish、Open Deep Research 的 README 组织方式，重新安排项目定位、核心能力、
快速开始、首次分析、架构图、配置、研究状态和文档导航；参考链接保存在 README 末尾。
页面内容依据本仓库源码与配置撰写，不沿用参考项目的规模、效果、许可证或验证结论。
同步中文文档索引、贡献指南、运行及部署入口，补充跨平台环境文件初始化与标准上传格式示例。
本轮仅改文档，检查本地链接、页内锚点、代码块及示例语法；不执行业务、Demo 或真实模型测试。

## 历史：DeerFlow 风格前后端分层

在领域重写提交 7bb678f 之后，按用户给出的目录布局实现 backend/frontend/skills/docker：

- 领域实现迁入 backend/src/domain，根旧包保留导入转发；确定性计划编译迁入 opinion_core。
- 新增 LangGraph Leader、受限子 Agent、上下文中间件、SQLite 检查点、显式记忆和持久 SSE 事件。
- 新增 FastAPI 的 threads/runs/events/datasets/artifacts/system 六组路由及 Next.js 工作台。
- 根 config.yaml、extensions_config.json 与忽略的 .env 分别管理应用、扩展和凭据。
- 新增启动/停止脚本、依赖锁、Compose/Nginx/K8s 模板及目录、配置、部署说明。

静态检查记录：后端源码及 JSON/YAML 可解析，关键新旧包可导入，新增 Runtime 的 Ruff F/E9 检查通过，
后端 wheel 成功构建，前端 tsc --noEmit 通过。
没有运行新增业务测试、Demo、模型或采集调用、浏览器端到端、Docker/K8s 部署或数值研究验证。
backend/tests 当前仅为后置验证位置；不引用下方历史通过数证明新架构可用。
Next.js 已提供主流程界面；旧 Streamlit 专项图表/PDF 仍为兼容功能，尚未全部迁成新组件。
详见 [2.7 目录总览](project-structure.md)、[运行时架构](modules/agent-runtime-architecture.md)。

## 历史：全项目架构重写顺序

用户最新指示：先完成整个项目架构及各功能脚本，保留并迁移可复用代码，之后再统一测试。
本记录下方 454 项通过的结果发生在此次重写之前，不作为重写后的验收证据。
当前主入口、服务、Worker、工作台、领域算法与连接器路径已按新架构写入；
详见[迁移清单](modules/architecture-rewrite.md)和[运行手册](modules/domain-application.md)。
本轮重写阶段不执行 Demo、真实标注、采集或模型回测；历史外部凭据状态没有复测。
采集/决策模型/视觉供应商的实际连接器仍需针对确定的服务配置与实现，不把通用协议视为真实平台接入完成。

## 范围与顺序

PR-01 版本化契约与迁移 → PR-02 数据/运行隔离与持久作业 → PR-03 领域 MCP 和运行时扩展 → PR-04 搜索供应商单选。
后续 M2b 标注、M3 按需采集、M4 证据论坛、M5 内容结构与工作台、M6 预测、M7 情景与多模态均未验收。
不修改外部论文工程；以下为历史实施记录，当前默认业务入口已改为新领域架构。

## 验证记录

- PR-01：新增测试先因缺少 opinion_core 失败；实现后契约/迁移/格式/Stage1 共 24 项通过。
  随后补充真实旧 fixture 的 topics 列表测试，先失败再修复。
- 本轮使用 uv 创建仓库内 .venv；没有付费调用或抓取。
- 标注门槛与规模已按用户补充限定于 Demo 验证，见[弱标注 Demo 协议](testing/weak-label-demo-protocol.md)；尚无真实评测结果，节费 50%–70% 仍是待验证目标。

## PR-01 接口

见[契约与迁移](modules/opinion-contracts.md)。新业务在 opinion_core；旧节点仍消费历史字段，
belief network/publisher_decision 的全链路移除属于 M2b，不能仅通过新契约省略字段就视为已完成。

## PR-02 运行隔离

DatasetRepository 在服务根目录内使用 SHA256(event)/datasets/ds-SHA256.json，运行目录为 SHA256(event)/runs/dataset/SHA256(run)。
数据按内容版本隔离，无共享可变缓存；每次读取核验指纹。文件写入用同目录临时文件和原子替换。
路径拒绝越界 ID 和指向根外的链接。run_context 注入所有旧 MCP 显式输出路径；调用者须显式绑定，
旧 PocketFlow 环境变量模式仍要求独立子进程，不能在同进程并发切换。

JobStore 持久保存参数、幂等键、状态、修订号、租约和批次结果。状态变更必须传当前 revision；
终态不能复活，取消已接受后完成不能覆盖。Worker 可领取排队/租约过期任务，heartbeat 续约，
commit_batch 验证所有者、租约、运行状态并按 batch_id 幂等提交。API 费用不确定性仍需标注 Worker 接入时记录。
当前仅提供作业基础设施，未接付费标注/采集 Worker；不能宣称崩溃后外部请求恰好执行一次。

定向测试：13 项通过，包括不同事件并发目录、跨事件读取拒绝、数据版本、取消/完成竞争、
重启读回、批次归属，以及旧 PathManager/status/MCP 暴露回归。

## PR-03 最小领域接入

新增可运行的领域 MCP 与 Streamlit 上传概览页，复用旧 IR 渲染器。7 个工具提供注册、统计、
分页证据、短报告、产物读取、任务查询/取消。配置示例保留真实上游出处；无上游源码复制。
定向测试 19 项通过，包含真实 Windows stdio 子进程。报告输入/阶段前提测试先失败再实现。
全量测试暴露旧 Windows os.kill(pid,0) 探测导致中断，新增失败测试后修为 tasklist 精确 PID 读取。
上游 Agent Runtime/浏览器/真实模型验收仍未执行，M1 不标为完成。见[运行手册](modules/domain-gateway.md)。

## PR-04 搜索单选

统一 provider 接口和两个实际 HTTP adapter，旧 web_search 返回兼容投影，保留完整证据与响应。
配置和 Pipeline Console 支持二选一；不跨供应商回退，不新增禁用搜索模式。
46 项定向测试通过。Tavily 单次真实 smoke 因认证失败未通过；DeepSeek 无环境凭据，未调用。
PR-01 至 PR-03 的全量离线回归为 413 passed / 1 skipped / 4 deselected，4 个旧图表警告。
后续全量结果以本文件最后一次记录为准。详见[搜索接口](modules/search-providers.md)。

## 第一轮边界修复

新增回归发现并修复 Windows 文件系统大小写串事件问题：目录键改为原始 ID 的 SHA256，逻辑 ID 保留原值。
新增取消发生在渲染期间的回归：取消请求最终落为 cancelled，未完成报告拒绝发布。
RunManifest.code_version 改为 opinion_core/opinion_gateway 与渲染源码指纹，不使用功能名称冒充代码版本。
真实 stdio 短报告初次超时，定位到旧 nodes 包引入 NumPy；将既有纯 IR 渲染函数抽至
opinion_core/reporting/ir_markdown.py，由新旧入口共用。完整 stdio 链路和定向回归共 10 项通过。

## 第一轮验证快照（2026-11-03）

`uv run pytest tests dashboard/tests -v`：425 passed、1 skipped、5 deselected、4 warnings（21.38 秒）。
完整日志保留在本地 `.opinion-assets/validation/offline.txt`（运行资产，不入 Git）。
默认跳过 live_api/ui_e2e；真实 stdio 上传→统计→证据→短报告集成已通过。
Tavily live 单查询返回 authentication；DeepSeek 未配置凭据。没有真实浏览器或上游 Agent Runtime 验收结论。
4 个警告来自既有图表刻度/相同坐标范围，未影响断言。

## 下一批实施与前置条件

1. M0：Demo 协议与评分入口已落实；下一步准备真实 Demo 样本及候选/基线预测。600 条（校准 200／独立测试 400）、逐字段 macro-F1 ≥ 0.80、覆盖率 ≥ 85%、相对同标签基线下降 ≤ 0.03 仍待实测。正式运行不进行人工标注验证。
2. M1：运行时工具前缀绑定、上游固定版本环境验证、实际标注/采集 Worker 接入仍待完成（资料概览 Worker 与刷新恢复 UI 已落实）。
3. M2a：修复本机 Tavily 凭据并配置 DeepSeek 环境密钥后，各执行一次小规模真实 smoke；无需重新跑付费大链路。
4. M2b：成功先导搜索→冻结词库/target→字段级标注与拒判已提供首版 CLI；下一步接入标注 Worker/工作台，迁移旧字段消费者，并验证实际决策模型供应商。
5. M3–M7 尚未开始正式实现或科学验收。当前基础提交不表示整个升级或第一层产品已完成。

## 用户补充：人工验证仅用于 Demo（2026-11-03）

正式数据经模型弱标注后自动进入分析，不设逐批／逐事件人工复核。人工金标准只用于 Demo，
验证 Jev 或其他决策模型是否达到上述规模与质量门槛。保留自动契约校验、字段级拒判和失败处理。
此项更新明确工程边界，不代表 Demo 评测已经通过；不再把人工验证资源作为日常运行前置条件。


## 第二轮：持久 Worker 与工作台恢复

M1 新增独立 inventory Worker、排队提交、原子发布、租约令牌、断点恢复与幂等重试；
工作台支持新会话重连、任务列表、取消重试、产物下载。修复读取不存在报告会创建任务的副作用。
旧同步工具保留，异步链路的正式结果以 SQLite 中完成状态与结果的事务提交为准。
新增 7 项集成/AppTest 用例；既有租约检查点调用改为必须携带领取令牌。详见领域运行手册。

第二轮 Worker/UI 全量离线回归：432 passed、1 skipped、5 deselected，4 个既有图表警告。


## 第二轮：自动弱标注与独立 Demo 评分

已新增搜索前置 schema 准备服务、固定候选词库、单命题冻结、版本缓存、可恢复失败和累计调用上限。
WeakLabeler 提供批处理、每字段校验/拒判、target_id 检查、状态/覆盖统计；异常批次不会留下部分成功缓存。
新增 GLM SDK JSON adapter 与可执行 label_workflow CLI，沿用已有 SDK，禁止隐藏重试；目前属于通用模型基线入口。
正式任务不接人工真值。模型自报置信度与校准概率分开，0.7 是可调整工程初值，未宣称完成校准。
运行清单保存源码、数据、schema、模型/提示词和阈值配置；SQLite 跨进程预留调用额度并冻结同一运行配置。

Demo 评分器独立处理 200/400 划分、每字段 accepted F1/全样本 F1/覆盖率、基线差异、混淆矩阵、共同有效样本比较、
重复 ID/分组泄漏/target 不匹配及样本规模检查。提供 CLI 与可追溯 JSON 输出，评分使用合成 fixture 测试验证。
没有真实人工金标准，不将程序测试通过当作 Jev 或其他决策模型达标。

尚未落实：Jev/阿里真实 adapter、金额预算账本、标注的持久 Worker/工作台接入、旧字段消费者全量清理、
运行时前缀配置与上游环境真实验证。M3–M7 与真实模型 Demo 仍未验收。

复查按 RED→GREEN 修复三个边界：0.03 差值的浮点误判、基线缺失输出仍通过验收、
搜索失败错误继承旧 builder 用量。数值容差仅为 1e-12；基线 missing/failed 将明确阻止该字段 Demo 通过。
搜索未进入 builder 或 builder 未成功返回时用量记为空，不冒充零费用。

## 第二轮最终验证（2026-11-03）

- 默认全量回归 `uv run pytest tests dashboard/tests -v`：454 passed、1 skipped、5 deselected、4 warnings，32.90 秒。
  相比第一轮 425 项通过，新增 29 项通过；警告仍来自既有 Matplotlib 图表。
- 本机真实 Worker 子进程、真实 MCP stdio 集成及工作台 AppTest 均包含在回归中；AppTest 不等同于浏览器 E2E。
- 额外执行 Demo 评分 CLI：合成预测通过时退出码 0，基线缺失时退出码 2，JSON 产物核验通过。
  合成记录只验证评分程序，不能作为人工金标准或模型效果证据。
- 本轮未执行真实标注 API，没有新增准确率、模型费用或节费实测结论。
  搜索联网状态仍沿用此前记录：Tavily 单次认证失败、DeepSeek 未配置凭据，本轮未复测。
- 全量日志：本机 `.opinion-assets/validation/second-round.txt`；CLI 合成 smoke 产物在同目录
  `synthetic-demo-cli/`。这些运行资产不入 Git。

实现提交：1d36c41（持久任务/工作台）、b2fb4b3（自动弱标注）、44ea523（独立 Demo 评分）；
后续边界修复包含上述三项 RED→GREEN 回归及文档状态同步。所有业务修改均在内层仓库 refine 分支。
