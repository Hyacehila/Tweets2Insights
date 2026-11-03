# 应用配置

更新：2026-11-03。

| 文件/变量 | 用途 |
|---|---|
| `config.yaml` | Gateway 地址、状态/资产目录、GLM 模型、上下文与调用上限 |
| `config.example.yaml` | 不含密钥的主应用模板 |
| `extensions_config.json` | 启用的本地 stdio MCP 服务、传递的变量名称、项目技能 |
| `.env` | 本机 API Key、连接器与价格文件位置；不提交 |
| `.provider-secrets.json` | 前端配置接口写入的本机凭据，gitignored；优先于环境变量，读取 API 不返回密钥 |
| `T2I_PROJECT_ROOT` | 应用根目录覆盖；默认由后端源码位置定位 |
| `T2I_CONFIG_FILE` | 指定主配置路径 |
| `T2I_STATE_ROOT` / `T2I_ASSET_ROOT` | 覆盖会话状态目录/领域资产目录 |
| `T2I_CONNECTORS_FILE` / `T2I_PRICING_FILE` | 操作者维护的真实连接器、调用价格上界配置 |
| `RunRequest` | 冻结某次运行的数据、唯一搜索供应商、标注、观测、预测、情景和预算 |

`.env` 使用 dotenv 加载，已有进程环境优先。Agent 使用 `models.default.api_key_env` 指定的变量，
领域推理使用 `RunRequest.agent_model`；弱标注模型为 `labels.provider/model`，相互独立。搜索密钥为 `TAVILY_API_KEY` 或 `DEEPSEEK_API_KEY`。
不要将密钥写入聊天、线程记忆、RunRequest 或版本库。

| 标注服务 | 模型示例 | 凭据 | 端点 / 批次 |
|---|---|---|---|
| `jev` | `jev-latest` | `TYPESAFE_API_KEY` | 固定 `https://api.typesafe.ai/v1/systemone`；batch_size=1，每帖五个 choice 问题 |
| `aliyun_decision` | `decision-model-preview` | `DASHSCOPE_API_KEY` | `ALIYUN_DECISION_ENDPOINT` 为业务空间域名，见下文；batch_size=1 |
| `glm` | `glm-4.5-air` | `GLM_API_KEY` | 既有 GLM JSON 协议 |
| `connector` | 由操作者设置 | 由本机连接器解析 | `labels.connector` 选择已安装 ID |

阿里端点为 `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/systemone`，
或同路径的新加坡 `ap-southeast-1` 域名。配置接口仅接受官方 HTTPS 域名，禁止重定向。
依据：[TypeSafe](https://docs.typesafe.ai/api/system-one)、[阿里云](https://help.aliyun.com/zh/model-studio/decision-model-api)。
X 归档采集需要 `X_BEARER_TOKEN` 和账号对应的接口权限；其他平台仍需配置连接器。

`GET /api/providers` 只显示配置状态；`POST /api/providers` 只允许本机客户端及配置的前端 Origin。
凭据以明文保存在本机，受操作系统账户权限保护；容器部署使用环境变量/Secret。
Worker 每次创建服务适配器时重新读取本机配置，无须把密钥写入任务产物。

`domain` 配置区记录固定部署策略：独立 Worker、关闭生产人工复核，以及质量验证状态。
Demo 结果由独立评分工具生成。
`agent_runtime.max_model_calls` 限制每次会话的模型规划/专业评阅调用；领域运行的调用与金额预算由 RunRequest 独立控制。
两者不属于同一本调用账本，当前没有跨会话、跨领域运行的总金额上限。
MCP 的 `$PYTHON`、`$PROJECT_ROOT`、`$T2I_ASSET_ROOT` 由客户端替换，命令只来自操作者配置。
相对路径按项目根解析；容器覆盖为 `/data/state` 与 `/data/assets`。

本机原配置已保留在忽略文件 `legacy/config.yaml`，仅供显式旧入口使用。
新克隆如需旧入口，应自行建立相应旧配置；新应用不需要它。

相关：[目录](project-structure.md)、[连接器协议](modules/architecture-rewrite.md)、[运行手册](modules/domain-application.md)。
