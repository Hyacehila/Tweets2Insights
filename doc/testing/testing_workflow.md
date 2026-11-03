# 测试工作流指南

> **Last Updated**: 2026-11-03  
> **关联源码**: `tests/` 目录  
> **上级文档**: [系统设计总览](../architecture.md)

本文档保留项目的常规 TDD 测试分层、执行方式与重构规则。
2026-11-03 用户明确指定本次架构重写先完成全部功能脚本，再统一测试；本轮采用该实施顺序。
目前只做源码、关键导入与前端类型检查，不运行 Demo、真实标注、业务或端到端测试。
新架构入口位于 `backend/src` 和 `frontend/src`；`backend/tests` 是后续新增测试位置，既有根 `tests` 保留待回归。

## 1. 测试架构（分层 + 按域分组）

```text
tests/
├── conftest.py
├── fixtures/
├── unit/
│   ├── core/       # config/pipeline/path/state/基础工具
│   ├── stage1/     # Stage 1 节点与分析逻辑
│   ├── stage2/     # Stage 2 agent/tool 执行链路
│   ├── stage3/     # Stage 3 报告生成与清理逻辑
│   └── tools/      # 分析工具与工具注册/MCP 暴露一致性
├── integration/
│   ├── io/         # 数据文件与加载器契约测试
│   └── pipeline/   # 多节点串联、失败路径与 shared 流转
└── e2e/
    ├── cli/        # CLI 与 Dashboard API 的 live smoke（真实 API）
    └── dashboard_ui/ # Playwright 驱动的人工链路 UI E2E（真实 API）
```

另有 Dashboard 专项测试位于 `dashboard/tests/`（配置 API 与页面配置逻辑）。

## 2. 执行命令

### 2.1 默认回归执行（推荐，跳过 live API）

```bash
uv run pytest tests/unit -v
uv run pytest tests/integration -v
uv run pytest dashboard/tests -v
uv run pytest tests dashboard/tests -v
```

> 默认 `addopts` 已启用 `-m "not live_api and not ui_e2e"`，日常回归不会触发真实 API。

### 2.2 按需执行 Live E2E（手动 / 夜间）

```bash
uv run pytest tests/e2e/cli -v -m "live_api"
uv run pytest tests/e2e/dashboard_ui -v -m "ui_e2e and live_api"
```

### 2.3 真实运行验收（本地人工）

```bash
uv run main.py
```

验收时需额外检查 `report/`：

- `report.md`、`report.html`、`trace.json`、`status.json` 均已刷新
- 报告正文为段落级 `[E#]` 角标引用融合（非“证据说明：...”模板段落）
- `status.json` 事件流显示进入终端节点并完成输出

### 2.4 全量验收（脚本）

```bash
powershell -ExecutionPolicy Bypass -File scripts/run_full_acceptance.ps1
# 可选：指定临时目录根，避免受限目录 ACL 干扰
powershell -ExecutionPolicy Bypass -File scripts/run_full_acceptance.ps1 -BaseTempRoot "$env:TEMP\\analysisposts_pytest"
```

> 验收门禁说明：`whitelist_security_key_check` 为白名单信息检查步骤，允许失败但不会阻塞最终验收结论。

## 3. E2E 与外部依赖策略

- `tests/e2e/` 仅保留真实用户链路的最小 live smoke 集。
- 默认 pytest 回归跳过 `live_api` 与 `ui_e2e`，避免日常开发消耗 API 额度。
- E2E 必须调用真实外部依赖（包括真实 GLM API）。
- E2E 配置来源为项目预留 `config.yaml`，仅在测试运行时覆盖 `runtime`、输出路径与 Stage2 循环上限。
- E2E 的 GLM API Key 优先使用 `config.yaml.llm.glm_api_key`，若为空则回退环境变量 `GLM_API_KEY`；两者都缺失时直接失败（`pytest.fail`）。
- Tavily live E2E 使用 `config.yaml.stage2.search_api_key`，若为空则回退环境变量 `TAVILY_API_KEY`。
- E2E 核心 live 场景固定为 4 个：
  - CLI 全链路 smoke（`start_stage=1`）
  - Dashboard API 入口 smoke（`start_stage=3`）
  - Tavily 单查询 live smoke
  - Dashboard UI 人工链路 smoke
- Live API E2E 的默认平衡档循环限制（在 `tests/e2e/cli/_e2e_config_runtime.py` 注入）：
  - `stage2.agent_max_iterations=3`
  - `stage2.search_reflection_max_rounds=2`
  - `stage2.forum_max_rounds=3`
- Live E2E 验证至少覆盖：
  - 进程退出码
  - `stdout`/`stderr` 关键输出
  - 全链路产物文件（增强数据、Stage2 分析输出、`report.md`、`report.html`、`trace.json`、`status.json`）
- Windows 长跑场景建议使用 `%TEMP%` 下的基准临时目录（例如 `--basetemp=$env:TEMP\\analysisposts_pytest\\<case>`），避免仓库内受限目录 ACL 干扰。
- 兼容性说明：`tests/conftest.py` 在 Windows 下对 `os.mkdir(mode=0o700)` 做兼容补丁，避免 Python 3.12 + 受限环境中 `tmp_path` 目录不可读导致的批量误报。
- 全量验收脚本会将 `PLAYWRIGHT_BROWSERS_PATH` 指向本轮 `basetemp` 子目录，避免默认 `AppData` 目录锁导致 Chromium 安装失败。

## 4. 迁移后的关键用例映射

| 关注模块 | 当前测试文件 |
|---|---|
| 配置加载/校验 + A3 搜索配置映射 | `tests/unit/core/test_config.py` |
| Stage3 配置兼容（移除 `min_score` + 兼容旧键） | `tests/unit/core/test_config.py`, `dashboard/tests/test_pipeline_api.py` |
| 仓库配置安全（禁止真实 key 入仓） | `tests/unit/core/test_no_real_secrets.py`, `tests/unit/core/test_e2e_config_runtime_keys.py` |
| A3 搜索封装（Tavily） | `tests/unit/core/test_web_search.py` |
| MCP 客户端解析 + 子进程解释器一致性 | `tests/unit/core/test_mcp_client_parsing.py` |
| 线性主链入口与阶段状态（StageD） | `tests/unit/core/test_flow_entrypoint.py`, `tests/unit/core/test_pipeline_state.py` |
| 状态事件链路（enter/exit + 并行分支） | `tests/unit/core/test_status_events.py`, `tests/unit/core/test_node_status_events.py`, `tests/unit/stage2/test_stage2_parallel_flow.py` |
| E2E 运行时配置构造与产物契约断言 | `tests/unit/core/test_e2e_runtime_profile.py`, `tests/unit/core/test_e2e_config_runtime_keys.py` |
| Stage 1 节点/六维增强/NLP | `tests/unit/stage1/test_stage1_nodes.py`, `tests/unit/stage1/test_stage1_analysis.py`, `tests/unit/stage1/test_stage1_nlp_pipeline.py` |
| Stage 2 Agent 决策与执行 | `tests/unit/stage2/test_stage2_agent.py`, `tests/unit/stage2/test_stage2_execute_tools.py`, `tests/unit/stage2/test_stage2_ensure_charts.py`, `tests/unit/stage2/test_stage2_data_agent_trace.py` |
| Stage 2 QuerySearchFlow + SearchAgent + 并行桥接 | `tests/unit/stage2/test_stage2_search_flow.py`, `tests/unit/stage2/test_stage2_search_agent.py`, `tests/unit/stage2/test_stage2_parallel_flow.py` |
| Stage 2 Forum 动态循环（B5~B8） | `tests/unit/stage2/test_stage2_forum.py`, `tests/unit/stage2/test_stage2_supplement.py`, `tests/unit/stage2/test_stage2_visual.py`, `tests/unit/stage2/test_stage2_merge.py`, `tests/unit/stage2/test_stage2_chart_analysis_gapfill.py` |
| Stage 2 洞察语义兼容（analysis_content/analysis） | `tests/unit/stage2/test_stage2_insight.py` |
| Stage 3 统一报告链路（Outline/Chapters/Review/IRRenderer/Trace/Methodology/Render） | `tests/unit/stage3/test_stage3_outline.py`, `tests/unit/stage3/test_stage3_chapters.py`, `tests/unit/stage3/test_stage3_review.py`, `tests/unit/stage3/test_stage3_ir_renderer.py`, `tests/unit/stage3/test_stage3_trace_inject.py`, `tests/unit/stage3/test_stage3_methodology.py`, `tests/unit/stage3/test_stage3_render_html.py`, `tests/unit/stage3/test_stage3_report.py`, `tests/unit/stage3/test_report_cleanup.py`, `tests/unit/stage3/test_report_image_fallback.py` |
| 工具注册与 MCP 暴露一致性 | `tests/unit/tools/test_tool_registry.py`, `tests/unit/tools/test_mcp_tool_exposure.py` |
| 图表输出契约（无大 `data` 返回）与 Top5 截断 | `tests/unit/tools/test_tool_output_contracts.py` |
| tokenizer fallback 中文连续词回退 | `tests/unit/tools/test_nlp_tools.py` |
| I/O 契约与数据格式 | `tests/integration/io/test_data_loader_integration.py`, `tests/integration/io/test_data_format_contract.py`, `tests/integration/io/test_json_reference_contract.py` |
| 跨阶段串联集成 | `tests/integration/pipeline/test_flow_pipeline_integration.py`, `tests/integration/pipeline/test_stage2_forum_pipeline_integration.py`, `tests/integration/pipeline/test_stage3_unified_pipeline_integration.py` |
| Pipeline 失败路径（key 缺失 / Stage3 前置缺失 / 非法入口） | `tests/integration/pipeline/test_pipeline_failure_modes_integration.py` |
| 真实 API + 完整生命周期端到端（live smoke） | `tests/e2e/cli/test_dashboard_pipeline_e2e.py`, `tests/e2e/cli/test_cli_pipeline_e2e.py` |
| Tavily 搜索真实 API live smoke | `tests/e2e/cli/test_tavily_live_api_e2e.py` |
| Dashboard 人工链路 UI live smoke | `tests/e2e/dashboard_ui/test_dashboard_human_flow_e2e.py` |
| Dashboard 配置读写/默认合并 | `dashboard/tests/test_pipeline_api.py` |
| Dashboard 页面配置校验逻辑 | `dashboard/tests/test_pipeline_console_logic.py` |
| Dashboard Results Viewer 来源分区聚合与证据链回溯 | `dashboard/tests/test_results_viewer_logic.py` |
| Dashboard 报告预览（HTML 优先 + MD 回退 + 本地图片内联） | `dashboard/tests/test_report_preview_logic.py` |
| Dashboard PDF 导出工具链（worker 子进程协议 + 结构化报错 + 临时文件清理） | `dashboard/tests/test_pdf_generator.py` |
| Dashboard Streamlit 页面发现约束（避免暴露 *_logic helper 页签） | `dashboard/tests/test_streamlit_pages.py` |

## 5. 重构中的测试流程（Red-Green-Refactor）

2026-11-03 本次架构重写的用户指示覆盖下述默认顺序：先完成所有功能脚本，再统一测试。
Demo、真实标注与科研指标验证后置。此前回归结果只适用于其对应提交，不能复用为新架构验收结论。
源码阶段允许语法和依赖边界静态检查；行为回归/外部调用另行登记。

1. **先写测试/更新测试**：先定义期望行为。  
2. **验证 RED**：`uv run pytest <target>` 必须先失败。  
3. **实现最小改动**：仅补足使测试通过的代码。  
4. **验证 GREEN**：目标测试通过。  
5. **回归验证**：至少执行受影响层级；任务收尾执行默认回归命令（非 live）。如涉及真实链路，再追加手动 live E2E。  

### 5.1 状态事件链路（建议）

针对 `utils.status_events` 与 `nodes.base` 的状态写入链路，优先验证以下契约：

- 节点开始写入 `enter`，节点结束写入 `exit`（`completed/failed`）
- 并行分支使用 `branch_id` 区分，事件写入同一 `status.json`
- 状态写入异常不会改变节点业务成功/失败判定

## 6. 失败诊断原则

测试失败时按顺序判断：

1. 需求是否变化（原始需求/文档是否更新）。  
2. 测试断言是否表达了正确需求。  
3. 代码实现是否违背需求。  
4. 结论：修代码、修测试或两者都修，并记录原因。  

禁止“盲修”：

- 仅为过测删除断言/删除用例；
- 用 `assert True` 或 `pass` 替代真实验证；
- 在未定位根因时随意修改期望值。

## 7. 开发过程文件与 Git 忽略约定

为避免将开发过程临时文件误提交到仓库，`.gitignore` 需要至少覆盖以下内容：

- 测试缓存与临时目录：`.pytest_cache/`、`.pytest_tmp/`、`.pytest_tmp_local/`
- 开发过程记录：`/dev_progress.md`、`/development_plan.md`

如果文件在新增忽略规则前已经被 Git 跟踪，需要额外执行：

```bash
git rm --cached <file>
```

## 领域升级测试（2026-11-03）

新增 opinion_contracts、legacy_annotation_migration、job_transitions、multi_event_isolation、
agent_runtime_tool_contract 和 domain_stdio 测试。domain_stdio 使用真实本机子进程，无付费 API，
归类为协议集成测试。完整真实用户链路仍须单独 live_api/ui_e2e 验收。

持久作业验证：tests/integration/pipeline/test_persistent_worker.py 启动真实本机 Worker 子进程；dashboard/tests/test_opinion_workbench.py 使用 Streamlit AppTest 验证新会话重连与取消/重试，属于离线集成验证，不是浏览器 E2E。

自动标注：test_event_preparation/test_weak_labeling/test_glm_label_provider 及 test_automatic_label_workflow
使用固定搜索与模型响应验证失败门禁、预算、缓存和全链路落盘。test_demo_evaluation 用合成金标准验证
评分数学及拒判分母；不能把这些测试结果当作真实模型的 600 条人工 Demo 分数。
评分边界回归覆盖恰好下降 0.03、基线输出不完整；事件准备回归确认失败搜索不会继承旧模型用量。
