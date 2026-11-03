# 新架构运行手册

更新：2026-11-03。以下为新脚本入口；真实供应商与科学验收状态另行登记。

在内层业务仓库执行：

```powershell
uv sync
uv run python main.py register --event rain --file posts.json
# 将返回的 dataset_id 写入 configs/domain-run.example.json 的副本
uv run python main.py plan --request run.json
uv run python main.py submit --request run.json
uv run python main.py worker
uv run streamlit run intelligent_ui/app.py
```

注册/预览/提交不调用模型；独立 Worker 执行外部调用。上传/已有数据的计划不包含 collect。
`--root` 是顶层参数，如 `uv run python main.py --root D:/assets submit --request run.json`。
同一事件/run_id 的请求冻结；修改数据、预算或模型配置需使用新 run_id。

```powershell
uv run python main.py jobs --event rain
uv run python main.py status --event rain --job JOB_ID
uv run python main.py cancel --event rain --job JOB_ID
uv run python main.py retry --event rain --job JOB_ID
uv run python main.py resume --event rain --job JOB_ID
uv run python main.py result --event rain --job JOB_ID
uv run python main.py export --event rain --run run-1 --artifact ARTIFACT_ID --output output-report
uv run python main.py serve
```

retry 为失败/取消/部分完成建立后继；resume 仅恢复 waiting_for_auth。取消后不再进入新阶段。
重试可以复用完整阶段；首次缺失阶段及其下游重新执行，避免混用旧派生产物。
长任务输出以 JobStore 的状态与结果事务提交为准。报告导出包含 Markdown、HTML、SVG 和 JSON。
工作台的 PDF 按钮复用既有隔离导出程序，可能需要本机 Playwright 浏览器组件。

MCP 暴露 17 个工具；新主入口为 preview_plan、submit_run、list_datasets、list_artifacts、
read_domain_artifact、resume_job，兼容工具仍可调用。大数组保存在资产库，读取工具对记录分页并隐藏虚拟粒子数组。
外部 Runtime 的发现结果保存为 JSON 后，可运行：

```powershell
uv run python -m agent_runtime_extension.bind_tools --discovery tools.json --output bound-roles.json
```

只允许唯一匹配的实际工具名；无法匹配时失败，不能直接放宽为所有工具。
参考上游提交仍为 `1dd6d056278536af1cb4fc60347f4ca40fcb629b`，不宣称已经安装或联调通过。

正式运行使用环境变量 GLM_API_KEY 和所选搜索服务的 TAVILY_API_KEY/DEEPSEEK_API_KEY。
第三方采集、决策模型与视觉服务使用[连接器协议](architecture-rewrite.md)，不在 manifest 保存密钥。
当前标准 GLM 标注只处理文本；image_only/text_image 必须显式配置支持相应模式的标签连接器。

旧入口：`uv run python -m legacy.main`，读取原 config.yaml；新 Worker 不调用该入口。
非破坏迁移：`uv run python -m opinion_core.ingestion --source OLD.json --output NEW.json --mapping MAP.json --schema-version VERSION --mapping-version VERSION --timezone Asia/Shanghai`。
迁移保留旧原文与原字段，缺少的立场继续标为 missing，进入新模型标注后再生成正式标签。
