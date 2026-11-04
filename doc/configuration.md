# 应用配置

更新：2026-11-04。

| 文件/变量 | 用途 |
|---|---|
| `config.yaml` | Gateway 地址、状态/资产目录、Agent 模型、上下文与调用上限 |
| `config.example.yaml` | 不含密钥的主应用模板 |
| `extensions_config.json` | 启用的本地 stdio MCP 服务、传递的变量名称、项目技能 |
| `.env` | 本机 API Key、连接器与价格文件位置；不提交 |
| `.provider-secrets.json` | 前端配置接口写入的本机凭据，gitignored；优先于环境变量，读取 API 不返回密钥 |
| `T2I_PROJECT_ROOT` | 应用根目录覆盖；默认由后端源码位置定位 |
| `T2I_CONFIG_FILE` | 指定主配置路径 |
| `T2I_STATE_ROOT` / `T2I_ASSET_ROOT` | 覆盖会话状态目录/领域资产目录 |
| `T2I_CONNECTORS_FILE` / `T2I_PRICING_FILE` | 操作者维护的真实连接器、调用价格上界配置 |
| `RunRequest` | 冻结某次运行的数据、唯一搜索供应商、标注、观测、预测、情景和预算 |

`.env` 使用 dotenv 加载，已有进程环境优先。搜索密钥为 `TAVILY_API_KEY` 或 `DEEPSEEK_API_KEY`。

## Agent 模型

“API 设置 → Agent 模型”用于配置 Leader、标签设计、论坛和报告 Agent。默认推荐 `qwen3.8-max`，另提供 `glm-5.3`；也可填写任意兼容服务的 Base URL、Model ID 和 API Key。Qwen 预设关闭思考输出，GLM-5.3 预设使用开启思考及 low 推理强度，兼顾结构化任务与响应时间。按服务商文档在高级参数中调整。

模型要求：文本生成/指令模型，支持 `POST /chat/completions`、`system/user` 消息及 `response_format: {type: json_object}`，能根据证据完成多步骤分析。建议至少 32K 上下文，长报告优先 128K；当前工具由 JSON 指令调度，原生 Function Calling 是扩展能力。Embedding、重排、图像生成与专用决策模型用于各自任务，不作为主 Agent。

```yaml
models:
  default:
    provider: qwen                 # qwen / glm / openai_compatible
    model: qwen3.8-max
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    max_tokens: 8192
    timeout_seconds: 120
    extra_body:
      enable_thinking: false
```

界面保存配置优先于 YAML。`GET /api/agent-model` 返回当前公开参数、凭据状态和推荐配置；`POST /api/agent-model` 先发送一次简短 JSON 请求，检查连接、格式与简单指令遵循，通过后原子保存。检测计入服务商用量；研究效果通过项目 Demo 评测。失败时保留原配置。

API Key 按 Base URL 分别保存，切换厂商不会把原密钥发送到新地址；同地址留空可复用密钥。官方 Qwen 中国内地端点可读取 `QWEN_API_KEY` 或 `DASHSCOPE_API_KEY`，官方 GLM 端点读取 `GLM_API_KEY`。其他地域及自定义端点在页面输入对应密钥。本机 `localhost/127.0.0.1/::1` 可使用 HTTP 和免鉴权服务。

任务在提交时把公开模型参数冻结到 `RunRequest.agent_config`，密钥在执行时按接口地址读取；切换配置只影响后续新任务。旧的显式 `agent_model` 字段仍兼容，GLM 名称指向官方 GLM 端点。弱标注使用独立的 `labels.provider/model`。

依据：[Qwen 模型列表](https://help.aliyun.com/zh/model-studio/models)、[GLM-5.3](https://docs.bigmodel.cn/cn/guide/models/text/glm-5.3)。

## 标注与外部服务

新任务默认选择 **OpenAI Decisions / `gpt-6-luna`**，通过 `POST https://api.openai.com/v1/decisions` 调用。一条帖子提出五个命名 choice 问题，接收完整类别概率和单独的 confidence，保留 unknown 与拒答状态；每条帖子一次调用进入持久预算。缺失、重复答案或无效概率会记录为失败；拒答字段记为弃权，其余字段继续处理。模型当前只支持 `gpt-6-luna`，本项目适配器使用 `batch_size=1`，文本输入。旧 GLM 标注配置需改选决策模型并创建新任务；历史产物仍可查看。

在“API 设置 → OpenAI Decisions”输入 API Key，或设置 `OPENAI_API_KEY`。[官方 Decisions 指南](https://developers.openai.com/api/docs/guides/decisions)与[请求/响应定义](https://developers.openai.com/api/reference/resources/decisions/methods/create)。

| 标注服务 | 模型示例 | 凭据 | 端点 / 批次 |
|---|---|---|---|
| `openai_decisions`（默认） | `gpt-6-luna` | `OPENAI_API_KEY` | 固定 `https://api.openai.com/v1/decisions`；batch_size=1，每帖五个 choice 问题 |
| `jev` | `jev-latest` | `TYPESAFE_API_KEY` | 固定 `https://api.typesafe.ai/v1/systemone`；batch_size=1，每帖五个 choice 问题 |
| `aliyun_decision` | `decision-model-preview` | `DASHSCOPE_API_KEY` | `ALIYUN_DECISION_ENDPOINT` 为业务空间域名，见下文；batch_size=1 |
| `connector` | 自定义决策模型 | 由本机连接器解析 | `labels.connector` 选择已安装 ID |

阿里端点为 `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/systemone`，
或同路径的新加坡 `ap-southeast-1` 域名。配置接口仅接受官方 HTTPS 域名，禁止重定向。
依据：[TypeSafe](https://docs.typesafe.ai/api/system-one)、[阿里云](https://help.aliyun.com/zh/model-studio/decision-model-api)。
X 归档采集需要 `X_BEARER_TOKEN` 和账号对应的接口权限；其他平台仍需配置连接器。

`GET /api/providers` 只显示配置状态；`POST /api/providers` 只允许本机客户端及配置的前端 Origin。
凭据以明文保存在本机，受操作系统账户权限保护。
Worker 每次创建服务适配器时重新读取本机配置，无须把密钥写入任务产物。

`domain` 配置区记录固定部署策略：独立 Worker、关闭生产人工复核，以及质量验证状态。
Demo 结果由独立评分工具生成。
`agent_runtime.max_model_calls` 限制每次会话的模型规划/专业评阅调用；领域运行的调用与金额预算由 RunRequest 独立控制。
两者不属于同一本调用账本，当前没有跨会话、跨领域运行的总金额上限。
MCP 的 `$PYTHON`、`$PROJECT_ROOT`、`$T2I_ASSET_ROOT` 由客户端替换，命令只来自操作者配置。
相对路径按项目根解析。

本机原配置已保留在忽略文件 `legacy/config.yaml`，仅供显式旧入口使用。
新克隆如需旧入口，应自行建立相应旧配置；新应用不需要它。

相关：[目录](project-structure.md)、[连接器协议](modules/architecture-rewrite.md)、[运行手册](modules/domain-application.md)。
