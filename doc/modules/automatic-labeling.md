# 自动弱标注实现与运行方法

更新：2026-11-04。独立标注 CLI 与 DomainWorker 共用决策模型适配器，完整链路使用 DomainWorker。

## 标注流程

1. 完整工作流先按固定种子从高阅读量池随机抽样（无阅读量时显式退化为均匀抽样）；EventPreparation 调用唯一搜索供应商，再将样本、搜索证据和固定词库交给 Schema Agent。抽样仅用于标签发现，后续对全部输入标注。
2. 从固定词库选择 5–10 个平面主题、5–7 个基础发布者类别和 10 个情绪词，生成一个明确的立场命题。
   第一版按 ID 选择且保留定义，不做未经映射的主题合并。非法输出保存为 recoverable_failure。
3. SQLite 保存冻结 schema、证据与生成状态。事件信息、截止点、供应商、词库内容、builder 版本一致时复用，
   准备键还包含样本及采样信息，更换任何影响标签定义的输入都会使用新键。失败可在剩余调用预算内再次运行，无静默跳过搜索或换供应商。
   builder_usage 只记录本次成功返回的 schema builder 用量；未调用或未成功返回时为空，不继承旧请求用量。
   失败请求的费用记为未知。
4. 自动批量标注 topic/publisher/emotion/sentiment/stance，情绪首版为主情绪单选。
   立场必须绑定 schema 的 target_id；情感为五档显示编码 -1/-0.5/0/0.5/1，不能推导立场。
5. 每字段独立 accepted/abstained/failed/missing；未知标签、低置信度、错误命题分别拒判。
   接受字段保留 provider_confidence。决策接口返回的 probabilities、被选类别概率及首二项差距均保存；差距低于 probability_margin 自动拒判。概率与 confidence 分别保存，校准质量通过独立 Demo 评估。
6. 缓存键含完整帖子、完整 schema、provider/model 版本、提示词版本、阈值与解析器版本。
   完整校验后才原子提交一批缓存；调用失败、不完整响应不作为中性或成功缓存。
7. 共享调用预算先预留再发请求。CLI 的标注预算在 SQLite 中跨进程/重启计数，同一运行的预算上限不可隐式增加。
   无后台重试。记录 token 用量、调用数、缓存命中、覆盖率与费用是否完整。
8. 正常运行不接收人工真值，也不创建人工审核任务。人工标签只由独立 Demo 评分工具使用。

## 发布者基础类型

新流程的 `common-v1.json` 与兼容入口的 `data/publisher_objects.json` 统一为 7 类，按账号主体和用途分类，不再按职业、行业或具体部门拆分。

| 类型 | 范围 |
|---|---|
| 政府机构 | 党政机关、公安、消防、气象、应急等行政与公共管理部门 |
| 新闻媒体 | 报社、广播电视台、通讯社、新闻网站等机构账号 |
| 自媒体 | 博主、主播、独立内容创作者等以持续内容传播为主的账号 |
| 企业账号 | 公司、品牌、商家及金融、交通、能源、通信等企业账号 |
| 事业单位 | 学校、医院、科研院所、公共文化服务等事业单位账号 |
| 社会组织 | 协会、商会、公益慈善、志愿者等非营利组织账号 |
| 个人用户 | 以个人身份发言的用户；教师、医生、律师、学生等职业身份不再单列 |

机构账号按所属主体分类，职业人士的私人账号归个人用户；专门运营内容的账号归自媒体。新闻机构单列为新闻媒体，不重复归入事业单位或企业。身份信息不足时沿用标注拒判机制。
词库内容参与 schema 与缓存指纹，新任务使用精简分类，已有冻结标签保持原定义。

## 供应商适配

LabelProvider 支持 OpenAIDecisionsProvider（默认）、SystemOneProvider（Jev / 阿里 decision）及操作者安装的决策模型连接器。
原生接口每帖合并五个 choice 问题，包括 unknown 选项；batch_size 必须为 1，保证标注预算与 HTTP 请求数一致。
类别结果校验选项全集、概率范围/和、choice 最大概率一致性；不接受重定向，不后台重试。
接口实现位于 `backend/src/domain/opinion_core/labeling/openai_decisions.py` 和 `system_one.py`，Worker 与 CLI 通过 `opinion_gateway/label_providers.py` 选择适配器。
文档：[TypeSafe API](https://docs.typesafe.ai/api/system-one)、[Choice 概率](https://docs.typesafe.ai/primitives/choice)、[阿里决策模型](https://help.aliyun.com/zh/model-studio/decision-model-api)。
OpenAI 使用 [Decisions API](https://developers.openai.com/api/docs/guides/decisions)。标签体系设计由 `schema_builder.py` 调用所选 Agent 模型，数据标注使用独立决策模型。

## 使用

先通过 DomainService/MCP 注册标准 PostRecord 数据，得到 dataset_ref。建立 EventSpec JSON，例如：

```json
{"event_id":"rain","input_mode":"existing","dataset_ref":"替换为注册所得ID","keywords":["城市暴雨"],"as_of":"2026-11-03T00:00:00Z","search_provider":"deepseek"}
```

在 API 设置中配置 Agent 模型、决策标注与搜索凭据，或设置对应环境变量。默认决策标注使用 OPENAI_API_KEY，Agent 默认使用 QWEN_API_KEY，搜索使用 DEEPSEEK_API_KEY 或 TAVILY_API_KEY：

```powershell
uv run --project backend python -m opinion_gateway.label_workflow --root .opinion-assets --event event.json --library backend/src/domain/opinion_core/labeling/vocabularies/common-v1.json --run-id label-demo-1 --provider openai_decisions --max-schema-calls 4 --max-label-calls 10 --confidence-threshold 0.7
```

执行 CLI 会调用配置的外部 API。
`--provider` 支持 openai_decisions、jev 和 aliyun_decision，模型 ID 默认与供应商对应；`--model` 可显式指定其决策模型。标注批次固定为 1，GLM 仅作为 Agent 模型选项。
默认拒判阈值为 0.7，可在 Demo 校准集上调整并冻结；common-v1 是可编辑的通用候选词库。
返回码 0 表示处理完成，2 表示 partial/可恢复失败。各字段覆盖率和失败数量单独记录。
每次尝试在对应运行目录另存 labels-<attempt_id>.json，不覆盖输入或其他并发尝试。
manifest 保存事件、数据引用、源码 SHA256、词库指纹、模型/提示词版本、阈值和预算；同一 run_id 的配置冻结，变更参数需新建运行。

## 运行细节

- Schema builder 调用上限以准备键累计，标签调用上限以 event/dataset/run 累计；Worker 支持金额上界预留，独立 CLI 使用持久调用预算及决策接口调用账本。
- LabelBudget 的内存版本供库调用共享；CLI 使用持久预算。超时按不确定调用记录。
- 完整标注链路由 DomainWorker 执行，工作台显示阶段与产物；兼容 InventoryWorker 处理 inventory_report。
- 新标注输出采用五字段契约。旧事件关联身份分类及其词库已移除；兼容入口仍保留 belief network。
- 过滤发布时间晚于 as_of 的来源，日期缺失来源单列；当前时间检索结果的 historical_availability_verified=false。
- 独立标注 CLI 处理文本并保留媒体引用；完整工作流的 image_only/text_image 模式通过支持相应输入的标签连接器执行。

相关验证：test_event_preparation、test_weak_labeling、test_label_providers、test_automatic_label_workflow。
