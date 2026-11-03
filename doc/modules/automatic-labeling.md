# 自动弱标注实现与运行方法

更新：2026-11-03。范围为新领域链路的显式实验入口；旧 PocketFlow 默认入口尚未切换。

## 已落实行为

1. EventPreparation 先调用 EventSpec.search_provider 指定的唯一搜索供应商，成功并获得可用证据后才调用 schema builder。
2. 从固定词库选择 5–10 个平面主题、5–10 个发布者类别和 10 个情绪词，生成一个明确的立场命题。
   第一版按 ID 选择且保留定义，不做未经映射的主题合并。非法输出保存为 recoverable_failure。
3. SQLite 保存冻结 schema、证据与生成状态。事件信息、截止点、供应商、词库内容、builder 版本一致时复用，
   更换任何影响标签定义的输入都会使用新键。失败可在剩余调用预算内再次运行，无静默跳过搜索或换供应商。
4. 自动批量标注 topic/publisher/emotion/sentiment/stance，情绪首版为主情绪单选。
   立场必须绑定 schema 的 target_id；情感为五档显示编码 -1/-0.5/0/0.5/1，不能推导立场。
5. 每字段独立 accepted/abstained/failed/missing；未知标签、低置信度、错误命题分别拒判。
   接受字段保留 provider_confidence；不填充 probability，不声称模型自报置信度已校准。
6. 缓存键含完整帖子、完整 schema、provider/model 版本、提示词版本、阈值与解析器版本。
   完整校验后才原子提交一批缓存；调用失败、不完整响应不作为中性或成功缓存。
7. 共享调用预算先预留再发请求。CLI 的标注预算在 SQLite 中跨进程/重启计数，同一运行的预算上限不可隐式增加。
   无后台重试，GLM SDK max_retries=0。记录 token 用量、调用数、缓存命中、覆盖率与费用是否完整。
8. 正常运行不接收人工真值，也不创建人工审核任务。人工标签只由独立 Demo 评分工具使用。

## 供应商状态

新增 LabelProvider 协议和 GLMJsonProvider，后者复用项目已有 zai-sdk 接口，默认模型 glm-4.5-air 可显式调整。
该适配器是同标签通用模型基线的工程入口，不代表 Jev 或阿里决策模型已接入，也不代表任何模型已达到 Demo 门槛。
Jev/阿里接入前仍需核验实际端点、字段、批次限制和置信度语义；没有虚构接口。
SDK 调用形式参考[官方 Python SDK](https://github.com/zai-org/z-ai-sdk-python)，并核对本机安装版本的构造参数。

## 使用

先通过 DomainService/MCP 注册标准 PostRecord 数据，得到 dataset_ref。建立 EventSpec JSON，例如：

```json
{"event_id":"rain","input_mode":"existing","dataset_ref":"替换为注册所得ID","keywords":["城市暴雨"],"as_of":"2026-11-03T00:00:00Z","search_provider":"deepseek"}
```

本机设置 GLM_API_KEY 与所选搜索供应商的 DEEPSEEK_API_KEY 或 TAVILY_API_KEY，然后执行：

```powershell
uv run python -m opinion_gateway.label_workflow --root .opinion-assets --event event.json --library opinion_core/labeling/vocabularies/common-v1.json --run-id label-demo-1 --max-schema-calls 4 --max-label-calls 10 --batch-size 10 --confidence-threshold 0.7
```

CLI 属于操作者入口，显式启动会调用配置的外部 API；本轮未执行真实标注。
默认阈值 0.7 只是可调整的工程初值，应在 Demo 校准集上选定并冻结，不是已验证的最佳阈值。
common-v1 是可编辑的通用候选词库，不是已完成实证验证的分类体系。
返回码 0 表示处理完成，2 表示 partial/可恢复失败。completed 只表示程序处理完毕，不表示高质量或高覆盖率。
每次尝试在对应运行目录另存 labels-<attempt_id>.json，不覆盖输入或其他并发尝试。
manifest 保存事件、数据引用、源码 SHA256、词库指纹、模型/提示词版本、阈值和预算；同一 run_id 的配置冻结，变更参数需新建运行。

## 边界与剩余工作

- CLI 已串通实际搜索/模型适配器，但本轮集成测试用固定响应，没有真实模型准确率、费用或节费结论。
- 当前 schema builder 调用上限以准备键累计，标签调用上限以 event/dataset/run 累计；金额预算预留、统一收费账本仍待实现。
- LabelBudget 的内存版本供库调用共享；CLI 使用持久预算。没有保证供应商端恰好调用一次，超时按不确定调用记录。
- 新标注链路尚未接入持久 Label Worker 与工作台；库存概览 Worker 只处理 inventory_report。
- 旧 belief network/publisher_decision 工具与消费者尚未全量移除；只在新标注输出中不再生成这些字段。
- 发布时间晚于 as_of 的来源会过滤，缺失日期会单列；检索发生在当前时间，historical_availability_verified=false，不能用于宣称无泄漏历史回测。
- 当前仅处理文本，媒体引用随记录保留但没有发送图片内容；多模态贡献仍待后续实现与消融验证。

相关验证：test_event_preparation、test_weak_labeling、test_glm_label_provider、test_automatic_label_workflow。
