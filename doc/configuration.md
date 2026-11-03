# 应用配置

更新：2026-11-03。

| 文件/变量 | 用途 |
|---|---|
| `config.yaml` | Gateway 地址、状态/资产目录、GLM 模型、上下文与调用上限 |
| `config.example.yaml` | 不含密钥的主应用模板 |
| `extensions_config.json` | 启用的本地 stdio MCP 服务、传递的变量名称、项目技能 |
| `.env` | 本机 API Key、连接器与价格文件位置；不提交 |
| `T2I_PROJECT_ROOT` | 应用根目录覆盖；默认由后端源码位置定位 |
| `T2I_CONFIG_FILE` | 指定主配置路径 |
| `T2I_STATE_ROOT` / `T2I_ASSET_ROOT` | 覆盖会话状态目录/领域资产目录 |
| `T2I_CONNECTORS_FILE` / `T2I_PRICING_FILE` | 操作者维护的真实连接器、调用价格上界配置 |
| `RunRequest` | 冻结某次运行的数据、唯一搜索供应商、标注、观测、预测、情景和预算 |

`.env` 使用 dotenv 加载，已有进程环境优先。Agent 使用 `models.default.api_key_env` 指定的变量，
领域弱标注当前使用 `GLM_API_KEY`；搜索密钥为 `TAVILY_API_KEY` 或 `DEEPSEEK_API_KEY`。
不要将密钥写入聊天、线程记忆、RunRequest 或版本库。

`domain` 配置区表达固定部署策略：独立 Worker、生产人工复核关闭、质量状态待验证；
它不控制研究质量结论，修改配置不能使 Demo 自动达标，也不能改变领域契约。
`agent_runtime.max_model_calls` 限制每次会话的模型规划/专业评阅调用；领域运行的调用与金额预算由 RunRequest 独立控制。
两者不属于同一本调用账本，当前没有跨会话、跨领域运行的总金额上限。
MCP 的 `$PYTHON`、`$PROJECT_ROOT`、`$T2I_ASSET_ROOT` 由客户端替换，命令只来自操作者配置。
相对路径按项目根解析；容器覆盖为 `/data/state` 与 `/data/assets`。

本机原配置已保留在忽略文件 `legacy/config.yaml`，仅供显式旧入口使用。
新克隆如需旧入口，应自行建立相应旧配置；新应用不需要它。

相关：[目录](project-structure.md)、[连接器协议](modules/architecture-rewrite.md)、[运行手册](modules/domain-application.md)。
