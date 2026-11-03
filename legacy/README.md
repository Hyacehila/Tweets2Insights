> 历史兼容文档；运行入口现为 `uv run python -m legacy.main`。以下旧默认命令不适用于新架构。

# Intelligence Analysis Agent (舆情分析智能体)

一个基于 LLM 和 PocketFlow 的自动化舆情分析系统，能够对大规模社交媒体数据进行深度挖掘，并生成专业的研究报告。

## 快速开始

### 环境依赖
本项目使用 `uv` 进行依赖管理。

```bash
# 安装依赖
uv sync

# 设置 API Key（GLM + Tavily）
$env:GLM_API_KEY="your_api_key"
$env:TAVILY_API_KEY="your_tavily_key"
```
也可在 `config.yaml` 中设置：
```yaml
pipeline:
  start_stage: 1  # 1/2/3，线性主链入口
llm:
  glm_api_key: "your_api_key"
stage2:
  search_provider: "tavily"
  search_max_results: 5
  search_timeout_seconds: 20
  search_api_key: "your_tavily_key"
```
Dashboard 里也支持配置（会写回 `config.yaml`）。当 YAML 中提供 key 时，会覆盖环境变量。

> 安全建议：仓库内 `config.yaml` 默认应保持空 key（`""`），避免提交真实凭证。

### 运行
```bash
# 修改 config.yaml 后运行
uv run analysis
# 或
uv run main.py
```

### Dashboard (Streamlit)
```bash
# 启动前端界面（推荐，确保使用 .venv 并设置 PYTHONPATH）
powershell -ExecutionPolicy Bypass -File scripts/run_dashboard.ps1

# 或临时方式
$env:PYTHONPATH = (Resolve-Path .)
.\.venv\Scripts\streamlit.exe run dashboard/app.py
```

Report Preview 页面行为：
- 只保留一个预览面板（优先 `report/report.html`，缺失时回退 `report/report.md` 渲染）
- 只保留一个下载逻辑（`report.pdf`，先点击 `Generate PDF` 再下载）
- 预览中本地图表会内联，确保 `report/images/*` 在页面中可见
- 支持 `Run PDF Preflight` 运行时自检；若导出失败会写入 `report/pdf_error.log` 便于定位问题
- PDF 渲染在隔离 worker 子进程中执行（`dashboard.utils.pdf_worker`），避免 Windows + Streamlit 事件循环冲突导致 `NotImplementedError`

### 样本数据运行（30 条）
默认 `config.yaml` 已指向：
- `data/posts_sample_30.json`
- `data/enhanced_posts_sample_30.json`

### 报告导出
Stage3 输出：
- `report/report.md`
- `report/report.html`
- Dashboard 导出：`report.pdf`（从单预览链路生成）

Stage2 追溯数据输出：
- `report/trace.json`

### Troubleshooting
- **Stage2 工具发现失败 / tool_count=0 / no_candidate_tool**：
  - 先在项目根目录执行 `uv sync` 安装依赖（如 `matplotlib`, `fastmcp`, `mcp`）。
  - 运行时务必使用 `uv run analysis` 或 `uv run main.py`，避免使用系统 Python。
  - 若依旧失败，检查报错信息中的 “模块导入错误”，优先修复缺失依赖或导入异常。
- **Tavily 搜索调用报 key 缺失**：
  - 在 `config.yaml.stage2.search_api_key` 填入 key，或设置环境变量 `TAVILY_API_KEY`。
  - Dashboard → Pipeline Console → Advanced settings → Stage 2 也可配置上述字段。

## 文档索引

- **[文档总览](../doc/README.md)** — `doc/` 目录导航与文档入口
- **[系统架构总览](../doc/legacy-architecture.md)** — 核心架构：系统流、`shared` 数据结构、线性主链 Flow 编排定义
- **[Agent 开发指南](../AGENTS.md)** — Agentic Coding 规范及核心原则

### 子系统模块详解 (`doc/modules/`)
- [阶段 1：数据增强子系统](../doc/modules/stage1_enhancement.md) — 六维增强、异步并行、断点续传
- [阶段 2：深度分析子系统](../doc/modules/stage2_analysis.md) — QuerySearchFlow、双信源并行、Forum 动态循环
- [阶段 3：报告生成子系统](../doc/modules/stage3_report.md) — 统一报告流、章节评审循环、追溯注入
- [分析工具库文档](../doc/modules/analysis_tools.md) — 37 个智能分析工具详解
- [通用基础设施库](../doc/modules/utils.md) — LLM 调用层、数据加载层、路径管理

### MCP 协议集成 (`doc/mcp/`)
- [MCP 协议集成指南](../doc/mcp/mcp_integration.md) — MCP 服务端/客户端通信流程
- [MCP 工具审计白皮书](../doc/mcp/mcp_tool_audit.md) — MCP 协议化映射表

### 测试与质量控制 (`doc/testing/`)
- [自动化测试工作流指南](../doc/testing/testing_workflow.md) — TDD 规范、端到端测试链路与执行手册

### 测试命令（TDD）
```bash
uv run pytest tests/unit -v
uv run pytest tests/integration -v
uv run pytest dashboard/tests -v
uv run pytest tests dashboard/tests -v
uv run pytest tests/e2e/cli -v -m "live_api"
uv run pytest tests/e2e/dashboard_ui -v -m "ui_e2e and live_api"
```

> 默认 pytest 配置会跳过 `live_api` 与 `ui_e2e`（节省额度与时长）；仅在手动/夜间执行 live E2E。live 运行态会把 Stage2 循环上限收敛到平衡档（agent=3/search=2/forum=3）以控制成本。

## 主要特性

- **三阶段流水线**: 数据增强 -> 深度分析 -> 报告生成。
- **双信源 + 论坛循环**: Stage2 支持 DataAgent/SearchAgent 并行与 ForumHost 动态补充决策。
- **统一 Stage3 报告**: 单一路由生成 Markdown + HTML，并注入 trace 证据与方法论附录。
- **线性主链入口**: `start_stage=1/2/3` 可从任意阶段进入并顺序执行后续阶段。
- **高性能**: 基于 PocketFlow 框架，轻量且高效。
