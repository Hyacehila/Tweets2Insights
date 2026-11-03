# 全项目架构重写与迁移清单

更新：2026-11-03。用户调整实施顺序：先写完功能脚本，再统一测试；Demo 与真实标注评测后置。
此前 454 项通过是重写前的快照，不能用于证明本次新架构已验收。

## 主链与边界

当前默认主链为 `Next.js → FastAPI → LangGraph Leader → MCP → ApplicationService → SQLite Job → DomainWorker → 阶段产物`。
领域包已迁入 `backend/src/domain`；下表 `opinion_core`、`opinion_gateway`、`crawler_worker` 均指此处的真实源码。
根目录同名包仅转发导入；前端为 `frontend/src`，旧 `intelligent_ui` 保留兼容。
外部 Agent Runtime 通过 MCP 提交同一份 RunRequest，不能与领域 Worker 同时调度重试或补搜。
LangGraph Leader 的自然语言规划脚本已经实现；领域计划编译仍为确定性函数。模型与完整工作流尚未联调验收。

| 层 | 源码 | 职责 |
|---|---|---|
| 契约 | opinion_core/schemas/workflow.py、artifacts.py | 运行、采集、窗口、模型、情景、内容、布局、证据与产物引用 |
| Leader 与角色 | backend/src/agents/lead_agent、subagents；opinion_core/orchestration.py | 模型规划与有限评阅；确定性领域阶段编译 |
| 应用服务 | opinion_gateway/application.py、cli.py | CLI/MCP/UI 共用入口、冻结运行请求、任务和产物访问 |
| 执行器 | opinion_gateway/domain_worker.py、runtime.py | 独立进程、租约、心跳、检查点、取消、登录等待、部分结果 |
| 基础设施 | assets.py、budget.py、jobs.py、dataset_repository.py | 版本资产、数据隔离、调用预留与持久任务 |
| 数据采集 | crawler_worker/ | 独立子进程、连接器分页、限速重试、去重、时间筛选、恢复检查点 |
| 自动标注 | opinion_core/labeling/ | 复用搜索前置 schema、批处理、逐字段拒判与版本缓存 |
| 取证与论坛 | opinion_core/evidence/ | 来源卡、文本指纹去重、Insight/Critic 有限补证、Media 连接器 |
| 分布分析 | opinion_core/analytics/ | 时间窗口、字段分母、主题切片、联合向量、SVG 与源数据 |
| 数值引擎 | opinion_core/dynamics/ | 联合 HK、分布摘要 EnKF、预测、滚动诊断与基线 |
| 条件情景 | opinion_core/scenarios/ | 相同状态与配对种子的条件差异 |
| 内容与结构 | opinion_core/reporting/ | 内容绑定证据和数值、布局引用已有块、验证及确定性渲染 |
| 智能工作台 | frontend/src；intelligent_ui/ 兼容视图 | 默认会话、配置、任务与产物；旧专项图表与按需 PDF 保留 |

## 真实复用与兼容归属

| 原实现 | 新架构处理 |
|---|---|
| main.py | 原逻辑保存到 legacy/main.py；默认 main.py 改用新领域 CLI；历史 helper 延迟兼容导入 |
| flow.py、nodes/ | 保留给显式 legacy 入口；新运行时不导入 PocketFlow，不注册旧信念/发布者决策工具 |
| utils/nlp/*.py | 实现迁入 opinion_core/analytics/nlp；原路径只作兼容转发 |
| 原 IR Markdown 渲染 | 直接复用 opinion_core/reporting/ir_markdown.py |
| dashboard/utils/pdf_* | 复用源码到 intelligent_ui/exports，调整隔离子进程模块名；原文件保留兼容 |
| 数据仓储、JobStore、搜索适配器、标注缓存 | 直接扩展已存在实现，避免复制另一套状态系统 |
| utils/analysis_tools 的旧标签工具 | 仅留在 legacy 路径；新分析直接消费平面标签与字段有效性状态 |
| config.yaml | 新主应用配置；旧配置保存在忽略文件 legacy/config.yaml；领域请求仍由 RunRequest 冻结 |
| dashboard/app.py | 新工作台兼容启动器；旧多页界面不再作为默认导航 |

旧文件仍可供对照与回退，不代表新主链继续消费旧字段。原始数据、旧增强数据及仓库外笔记不改写。

## 功能脚本与外部接入的区别

本轮实现连接器协议和执行路径，不提供未经核验的 Jev/阿里/社交平台 API。
操作者通过 `T2I_CONNECTORS_FILE` 指向本机配置，Agent 只能选择连接器 ID，不能提交命令或任意文件路径。
连接器是 operator 安装的可执行程序，以 stdin/stdout JSON 通信；stderr 不写入任务产物。
未配置平台连接器时采集明确失败，未登录时等待本机会话；不会生成假数据或自动换供应商。

配置格式为 `{"crawl":{"platform-id":{"command":["absolute-executable","arguments"]}},"label":{},"media":{}}`。
命令数组来自本机配置，禁止在 MCP RunRequest 中传入；示例配置故意不包含假的可执行端点。

- crawl：输入 operation=fetch_page、event、cursor、session_ref、remaining_posts/comments；输出 records（标准 PostRecord）、next_cursor。
- label：输入 operation=label、mode、schema、posts；输出 records（post_id/fields）、usage、cost。接口字段与 WeakLabeler 相同。
- media/default：输入指定 post_id/media_ref；输出 items（post_id、media_ref、ocr、interpretation）、usage、cost。
- 未登录可返回 `{"status":"waiting_for_auth"}`。会话内容由连接器从本机环境/会话存储解析，不进入请求清单。
- schema 生成与论坛仍使用现有 GLM SDK；具体决策模型可通过 label 连接器替换分类阶段。

调用账本记录预留、返回或不确定状态。设置金额上限时，每次调用必须有操作者提供的上界价格：
`T2I_PRICING_FILE` 指向 provider-version → 单次上界费用的 JSON；未知价格时停止付费请求。
金额预留按声明的上界工作，不证明声明价格与供应商实际账单一致；未知实际费用不会当作零。

## 数值实现的研究假设

联合特征为 topic/emotion 的 one-hot（模拟中为概率单纯形坐标）与 stance/sentiment 的 [-1,1] 编码。
主模型在联合向量上计算邻域，逐坐标版本仅为对照；不是将类别 ID 当作有序数值。
观测使用全部满足固定筛选及所需字段有效条件的帖子，不截取活跃账号 Top-N。
真实 n_t 随窗口变化；固定 particles 仅为虚拟粒子数。EnKF 用一阶/二阶分布摘要，不逐帖匹配粒子。
每次更新将类别块投影回单纯形，将连续编码限制在 [-1,1]；缺测窗口只预测，不填造观测。

当前是独立实验实现，尚未核实与外部论文模型逐项等价；本机未发现可直接移植的既定论文代码。
候选参数、类别几何与噪声形式都需后续研究验证。预测区间是集合离散范围，未承诺频率覆盖率。
滚动诊断包含 persistence、linear_distribution、无同化 HK、逐坐标 HK-EnKF 与联合 HK-EnKF。
当标签/检索缺乏当时可用性证据时，historical_availability_verified 保持 false，不宣称严格历史回测。
情景是条件计算，不作现实干预因果估计。图像贡献由独立三路消融工具评估，不由视觉解释自动推出。

## 统一测试阶段

依照用户本次指示，先完成上述源码与文档，再执行语法、导入、单元/集成和整体回归。
实际平台、真实模型、浏览器、人工 Demo 及数值科学验收分别记录，不能用固定响应测试代替。
现有 Demo 评分脚本保留，正常运行不读取人工真值、也不设置人工审核状态。

运行方法见[新架构运行手册](domain-application.md)。历史架构见[兼容架构存档](../legacy-architecture.md)。

## 本次源码检查记录

对本轮 58 个新增/修改 Python 文件执行 AST 语法解析，JSON 配置解析成功；
应用服务、运行时、Worker、CLI、工作台、采集和角色绑定模块导入成功。
静态检查未发现新架构包导入 nodes/flow/pocketflow/legacy 的反向依赖，变更 Markdown 的本地引用均可解析。
这些仅为源码与导入检查。本次架构重写后未运行行为回归、Demo、真实标注、采集、浏览器或数值实验。
