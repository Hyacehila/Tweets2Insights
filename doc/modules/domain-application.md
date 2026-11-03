# 新架构运行手册

更新：2026-11-03。以下命令在内层业务仓库执行。源码实现与真实服务/科学验收分别记录。

## 默认工作台

```powershell
uv sync --project backend
npm --prefix frontend ci
uv run --project backend python scripts/dev.py start
uv run --project backend python scripts/dev.py stop
```

入口为 http://127.0.0.1:3000；默认 Gateway 为 127.0.0.1:8001。
先创建事件会话，再上传标准 JSON 或描述采集需求；选择唯一搜索供应商，生成计划后提交执行。
结构化 RunRequest 可直接编辑。自然语言规划会调用 Agent 模型；结构化计划预览不调用模型。
独立领域 Worker 负责搜索、自动标注及分析。Agent 取消与领域 Job 取消分别操作。

## 领域 CLI

新 CLI 包装器加载与 Gateway 相同的 config.yaml/.env，并使用同一个资产根目录：

```powershell
uv run --project backend python -m src.tools.cli register --event rain --file posts.json
# 将返回的 dataset_id 写入 configs/domain-run.example.json 的副本
uv run --project backend python -m src.tools.cli plan --request run.json
uv run --project backend python -m src.tools.cli submit --request run.json
uv run --project backend python -m src.tools.worker
```

上传/已有数据的计划不包含 collect。注册、结构化预览和提交本身不调用模型。
显式覆盖资产目录时，将 `--root D:/assets` 放在子命令前。
同一 event/run_id 的请求冻结；修改数据、预算或模型配置需使用新 run_id。

```powershell
uv run --project backend python -m src.tools.cli jobs --event rain
uv run --project backend python -m src.tools.cli status --event rain --job JOB_ID
uv run --project backend python -m src.tools.cli cancel --event rain --job JOB_ID
uv run --project backend python -m src.tools.cli retry --event rain --job JOB_ID
uv run --project backend python -m src.tools.cli resume --event rain --job JOB_ID
uv run --project backend python -m src.tools.cli result --event rain --job JOB_ID
uv run --project backend python -m src.tools.cli export --event rain --run run-1 --artifact ARTIFACT_ID --output output-report
uv run --project backend python -m src.tools.cli serve
```

retry 为失败/取消/部分完成建立后继；resume 仅恢复 waiting_for_auth。取消后不再进入新阶段。
重试复用完整阶段；首次缺失阶段及下游重新执行。最终结果以 JobStore 的状态与结果事务提交为准。
报告导出包含 Markdown、HTML、SVG 和 JSON，HTTP 导出另提供 ZIP。

## MCP 和供应商

领域 MCP 保留 17 个工具；主路径为 register_dataset → preview_plan → submit_run → job_status/read_job_artifact。
分页读取工具 read_domain_artifact 限制返回记录并隐藏虚拟粒子数组。
默认 Runtime 自动读取根 extensions_config.json 并发现工具；外部工具绑定仍可使用兼容命令：

```powershell
uv run python -m agent_runtime_extension.bind_tools --discovery tools.json --output bound-roles.json
```

唯一匹配失败时拒绝调用，不放宽为所有工具。参考上游版本与适配范围见 [Agent Runtime](agent-runtime-architecture.md)。
领域弱标注使用 GLM_API_KEY，搜索使用所选服务的 TAVILY_API_KEY 或 DEEPSEEK_API_KEY。
采集、决策模型及视觉服务采用[连接器协议](architecture-rewrite.md)；需要操作者配置真实实现。
GLM 标准标注路径处理文本；image_only/text_image 必须配置支持相应模式的标签连接器。

## 兼容入口

根 main.py 仍提供原领域 CLI，旧根包转发到 backend/src/domain。默认新应用使用上方统一配置包装器。
旧 Streamlit 专项视图可执行 `scripts/run_legacy_dashboard.ps1`，其 PDF 导出可能需要本机 Playwright 浏览器组件。
旧 PocketFlow 使用 `uv run python -m legacy.main`，读取 `legacy/config.yaml`。
原配置已保留为本机忽略文件；新克隆需要旧入口时自行建立该旧配置。

非破坏迁移：

```powershell
uv run --project backend python -m opinion_core.ingestion --source OLD.json --output NEW.json --mapping MAP.json --schema-version VERSION --mapping-version VERSION --timezone Asia/Shanghai
```

迁移保留旧原文与字段；缺少的立场继续标为 missing，正式标签由后续模型标注生成。
当前按用户指定顺序仅完成源码及静态检查，Demo、真实标注、完整应用与数值研究测试均后置。
