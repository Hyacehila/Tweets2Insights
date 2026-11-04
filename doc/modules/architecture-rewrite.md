# 全项目架构重写与迁移清单

本文记录模块职责、代码复用与外部服务接入方式。

## 主链与边界

当前默认主链为 `Next.js → FastAPI → LangGraph Leader → MCP → ApplicationService → SQLite Job → DomainWorker → 阶段产物`。
领域包已迁入 `backend/src/domain`；下表 `opinion_core`、`opinion_gateway`、`crawler_worker` 均指此处的真实源码。
根目录同名包仅转发导入；前端为 `frontend/src`，旧 `intelligent_ui` 保留兼容。
外部 Agent Runtime 通过 MCP 提交同一份 RunRequest，不能与领域 Worker 同时调度重试或补搜。
LangGraph Leader 将自然语言需求转换为 RunRequest，领域编译器据此确定阶段依赖。

| 层 | 源码 | 职责 |
|---|---|---|
| 契约 | opinion_core/schemas/workflow.py、artifacts.py | 运行、采集、窗口、模型、情景、内容、布局、证据与产物引用 |
| Leader 与角色 | backend/src/agents/lead_agent、subagents；opinion_core/orchestration.py | 模型规划与有限评阅；确定性领域阶段编译 |
| 应用服务 | opinion_gateway/application.py、cli.py | CLI/MCP/UI 共用入口、冻结运行请求、任务和产物访问 |
| 执行器 | opinion_gateway/domain_worker.py、runtime.py | 独立进程、租约、心跳、检查点、取消、登录等待、部分结果 |
| 基础设施 | assets.py、budget.py、jobs.py、dataset_repository.py | 版本资产、数据隔离、调用预留与持久任务 |
| 数据采集 | crawler_worker/ | 独立子进程、连接器分页、限速重试、去重、时间筛选、恢复检查点 |
| 自动标注 | opinion_core/labeling/ | 复用搜索前置 schema、批处理、逐字段拒判与版本缓存 |
| 取证与论坛 | opinion_core/evidence/ | 原 Stage 2 反馈循环；data/search/visual/insight/methodology 按需启用，主持人补调白名单工具与检索 |
| 分布分析 | opinion_core/analytics/ | 41 个保留入口、字段分母、主题切片、联合向量、交互图表元数据与源表 |
| 数值引擎 | opinion_core/dynamics/ | PCA 训练、隐空间联合 HK、解码观测摘要 EnKF、预测、滚动诊断与基线 |
| 条件情景 | opinion_core/scenarios/ | 相同状态与配对种子的条件差异 |
| 内容与结构 | opinion_core/reporting/ | 内容 Agent、社科 Agent、布局 Agent；证据与数值绑定、引用校验及确定性渲染 |
| 智能工作台 | frontend/src；intelligent_ui/ 兼容视图 | 默认会话、配置、任务与产物；旧专项图表与按需 PDF 保留 |

## 代码复用与兼容入口

| 原实现 | 新架构处理 |
|---|---|
| main.py | 原逻辑保存到 legacy/main.py；默认 main.py 改用新领域 CLI；历史 helper 延迟兼容导入 |
| flow.py、nodes/ | 保留给显式 legacy 入口；新运行时不导入 PocketFlow，不注册旧信念/发布者决策工具 |
| utils/nlp/*.py | 实现迁入 opinion_core/analytics/nlp；原路径只作兼容转发 |
| 原 IR Markdown 渲染 | 直接复用 opinion_core/reporting/ir_markdown.py |
| dashboard/utils/pdf_* | 复用源码到 intelligent_ui/exports，调整隔离子进程模块名；原文件保留兼容 |
| 数据仓储、JobStore、搜索适配器、标注缓存 | 直接扩展已存在实现，避免复制另一套状态系统 |
| utils/analysis_tools 的旧标签工具 | 保留旧实现供兼容；41 个入口在 toolbox.py 按平面单标签重新实现，统计/图表共享纯函数；信念网络不迁入 |
| config.yaml | 新主应用配置；旧配置保存在忽略文件 legacy/config.yaml；领域请求仍由 RunRequest 冻结 |
| dashboard/app.py | 新工作台兼容启动器；旧多页界面不再作为默认导航 |

## 外部服务接入

OpenAI Decisions 使用官方 `/v1/decisions` 原生协议，作为默认决策标注；Jev 和阿里 decision 使用 System One 原生适配，X 使用官方归档搜索 API 分页适配。
其他社交平台及多模态通过连接器接入。
操作者通过 `T2I_CONNECTORS_FILE` 指向本机配置，Agent 只能选择连接器 ID，不能提交命令或任意文件路径。
连接器是 operator 安装的可执行程序，以 stdin/stdout JSON 通信；stderr 不写入任务产物。
平台连接器缺失时返回配置错误，未登录时进入 waiting_for_auth，登录后可恢复任务。

配置格式为 `{"crawl":{"platform-id":{"command":["absolute-executable","arguments"]}},"label":{},"media":{}}`。
命令数组由操作者在本机配置；MCP RunRequest 通过连接器 ID 引用。

- crawl：输入 operation=fetch_page、event、cursor、session_ref、remaining_posts/comments；输出 records（标准 PostRecord）、next_cursor。
- label：输入 operation=label、mode、schema、posts；输出 records（post_id/fields）、usage、cost。接口字段与 WeakLabeler 相同。
- media/default：输入指定 post_id/media_ref；输出 items（post_id、media_ref、ocr、interpretation）、usage、cost。
- 未登录可返回 `{"status":"waiting_for_auth"}`。会话内容由连接器从本机环境/会话存储解析，不进入请求清单。
- Schema、论坛和报告生成共用独立的 OpenAI 兼容 Agent 模型配置，默认 Qwen3.8-Max；标签阶段默认 OpenAI Decisions / gpt-6-luna，也支持 Jev/阿里或决策 label 连接器。

调用账本记录预留、返回或不确定状态。设置金额上限时，每次调用必须有操作者提供的上界价格：
`T2I_PRICING_FILE` 指向 provider-version → 单次上界费用的 JSON；未知价格时停止付费请求。
预算按配置的价格上界预留，实际费用根据供应商回执记录；缺少回执时标为未知。

## 数值实现的研究假设

联合特征为 topic/emotion 的 one-hot（模拟中为概率单纯形坐标）与 stance/sentiment 的 [-1,1] 编码。
当前默认模型先在训练数据上拟合 PCA，在隐空间联合向量上计算邻域，解码后得到观测摘要和预测分布。
原观测坐标联合 HK 保留为对照，逐坐标版本作为基线。
观测使用全部满足固定筛选及所需字段有效条件的帖子，不截取活跃账号 Top-N。
真实 n_t 随窗口变化；固定 particles 仅为虚拟粒子数。EnKF 用一阶/二阶分布摘要，不逐帖匹配粒子。
每次更新将类别块投影回单纯形，将连续编码限制在 [-1,1]；缺测窗口只预测，不填造观测。

该实验模型的研究变量包括候选参数、类别几何和噪声形式。预测区间表示集合离散范围，覆盖率通过独立实验评估。
滚动诊断包含 latent_hk_enkf、joint_hk_enkf、coordinate_hk_enkf、hk_without_assimilation、persistence 与 linear_distribution。
每个起点只使用历史前缀重新拟合编码器和选择参数；比较人口统一为联合字段有效记录。
标签或检索结果缺少历史可用性证据时，historical_availability_verified 保持 false。
情景计算比较给定机制下的条件差异，现实因果效应需要单独验证。图像贡献通过独立三路消融工具评估。

## 运行与测试

运行方法见[运行手册](domain-application.md)，阶段流程见[完整工作流](full-workflow.md)。
检查结果与后续任务见[实施记录](../upgrade-status.md)，旧模块设计见[兼容架构存档](../legacy-architecture.md)。
