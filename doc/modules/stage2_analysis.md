# 阶段 2：深度分析子系统

> **文档状态**: 2026-02-22 更新  
> **关联源码**: `nodes/stage2/*`, `flow.py`, `config.py`, `utils/web_search.py`  
> **上级文档**: [系统设计总览](../architecture.md)

---

## 1. 概述

Stage2 将 Stage1 增强数据转换为可报告化分析产物，输出：

- `report/analysis_data.json`（图表/表格/执行日志/搜索上下文）
- `report/chart_analyses.json`（图表视觉分析，含论坛视觉复用 + 批量补漏）
- `report/insights.json`（LLM 洞察）
- `report/trace.json`（决策/执行/反思/循环状态）

当前已完成 **Track B 全量（B1~B9）**：双信源 + 动态论坛循环 + 实时补充 + 合并收敛 + 全链路 live API 验证。

上下文能力：

- `analysis_context.time_range / time_range_text`：由增强数据时间字段（`publish_time`/`created_at`）提取。
- `analysis_context.user_analysis_instruction`：来自 `pipeline.user_analysis_instruction`。
- Stage2 提示词在 Decision / Forum / SearchAgent 中统一注入上述上下文，以约束时效与分析重点。

---

## 2. 当前 Flow（B1~B9）

```mermaid
flowchart LR
    CLR[ClearReportDir] --> LD[LoadEnhancedData]
    LD --> DS[DataSummary]
    DS --> QSF[QuerySearchFlow]
    QSF --> PF[ParallelAgentFlow]
    PF --> FH{ForumHost}

    FH -->|supplement_data| SDA[SupplementData]
    FH -->|supplement_search| SSA[SupplementSearch]
    FH -->|supplement_visual| VA[VisualAnalysis]
    SDA --> FH
    SSA --> FH
    VA --> FH

    FH -->|sufficient| MRG[MergeResults]
    MRG --> CA[ChartAnalysis GapFill]
    CA --> LI[LLMInsight]
    LI --> SR[SaveResults]
    SR --> SC[Stage2Completion]
```

---

## 3. 关键能力

### 3.1 QuerySearchFlow（B1）

文件：`nodes/stage2/search.py`

- `ExtractQueriesNode`：基于 `data_summary`、事件关键词与上一轮缺口提取查询词（无结果时使用事件关键词兜底）
- `WebSearchNode`：通过 `utils.web_search.batch_search` 调用 Tavily
- `SearchProcessNode`：去重/规整外部文档
- `SearchReflectionNode`：判断 `need_more/sufficient`（评估提示词包含文档样本 snippet）
- `SearchSummaryNode`：生成 `shared["search_results"]`

循环治理：

- `stage2.search_reflection_max_rounds` 控制最大反思轮次
- 写入 `trace.search_reflections`
- 写入 `trace.loop_status.search_reflection = {current,max,termination_reason}`

### 3.2 双信源并行（B2~B4）

文件：`nodes/stage2/parallel.py`, `nodes/stage2/search_agent.py`

- `ParallelAgentFlow` 并行分支：
  - `data_agent`：复用 DataAgent 决策-执行循环
  - `search_agent`：对搜索摘要结构化分析
- 输出隔离写入 `shared["agent_results"]["data_agent|search_agent"]`
- DataAgent trace 回写主 shared（含 `loop_status.data_agent`）

### 3.3 Forum 动态循环（B5~B8）

文件：`nodes/stage2/forum.py`, `nodes/stage2/supplement.py`, `nodes/stage2/visual.py`, `nodes/stage2/merge.py`

- `ForumHostNode`：中央状态机，动作路由为：
  - `supplement_data`
  - `supplement_search`
  - `supplement_visual`
  - `sufficient`
- `ForumHostNode` 的职责：
  - 输出 `host_narrative`（支持结构化输入并标准化为【事件脉络】【观点综合】【深层分析】【引导问题】文本）
  - 累积 `forum.debate_logs`（跨轮讨论脉络）
- `SupplementDataNode`：按主持人 directive 调用指定 MCP 工具子集
- `SupplementSearchNode`：追加搜索并刷新 SearchAgent 结论
- `VisualAnalysisNode`：按需调用 GLM4.5V 解析图表
- `MergeResultsNode`：合并 Data/Search/Forum 产物，回填兼容 `stage2_results`
- `ForumHostNode` 提示词显式注入“事件关键词 + 分析时间范围 + 用户分析指令”上下文，避免无焦点补充检索。
- 当用户诉求尚未覆盖时，主持人优先引导 `supplement_search` 并输出更明确的查询 directive。
- `MergeResultsNode` 会将 `forum.debate_logs` 注入 `stage2_results.search_context.forum_debate_logs`，供 Stage3 章节生成引用论坛共识/分歧。
- `SearchSummaryNode` 提示词升级为高信息密度结构化摘要，强制时间线/关键主体/官方回应/公众反应/关联事件五要素。
- `LLMInsightNode` 洞察提示词新增“数据与外部事件交叉对比”维度，并输出 `cross_reference_insight` 字段。

循环治理：

- `stage2.forum_max_rounds`
- `stage2.forum_min_rounds_for_sufficient`
- 写入 `trace.forum_rounds`
- 写入 `trace.loop_status.forum = {current,max,termination_reason}`

### 3.4 图表补漏分析（B8）

文件：`nodes/stage2/chart_analysis.py`

- 先复用 `forum.visual_analyses`（已分析图表不重复调用视觉模型）
- 对未覆盖图表执行批量分析
- 最终 `stage2_results.chart_analyses` 统一包含：
  - 论坛视觉分析结果
  - 批量补漏分析结果

### 3.5 洞察语义兼容（修复项）

文件：`nodes/stage2/insight.py`

- 洞察节点读取图表分析内容时，优先使用 `analysis_content`
- 同时兼容历史字段 `analysis`，避免旧数据结构导致洞察提示词丢失
- 洞察证据匹配从“英文工具名分词”升级为“中文语义关键词映射”，降低 `supporting_evidence` 为空的概率。

### 3.6 报告目录清理策略（稳定性修复）

文件：`nodes/stage2/cleanup.py`

- `ClearReportDirNode` 不再整目录 `rmtree(report/)`。
- 清理策略改为“选择性删除”：保留 `report/status.json`、`report/acceptance/`、`report/images/`，仅删除 Stage2 可再生产物。
- 该策略避免验收日志与运行状态在 Stage2 重跑时被误删。 

### 3.7 Decision Prompt 收敛门槛（性能优化）

文件：`nodes/stage2/agent.py`

- DecisionTools 提示词新增“强约束收敛门槛”：
  - 五维（情感/主题/地理/交互/NLP）均有有效结果后，且用户指令已被证据覆盖时，允许并鼓励输出 `finish`；
  - 最近两轮无新增洞察或执行工具数达到阈值时，必须优先考虑收敛；
- 该策略用于减少“仅因惯性而继续调用工具”的长尾循环，降低 live 运行耗时和 API 成本。

### 3.8 LoadData 遗留缓存清理（防污染修复）

文件：`nodes/stage2/load_data.py`

- `LoadEnhancedDataNode.prep()` 在读取增强数据前执行 `_clean_legacy_reports(report_dir)`。
- 当前会删除 `report/chart_analyses.json`（若存在），避免复用上次运行残留的图表分析结果。
- 该清理逻辑为幂等操作，不影响 `report/images/` 与其他运行时目录。

---

## 4. Shared 契约（Stage2 新增/稳定字段）

```python
shared["config"]["stage2_loops"] = {
    "agent_max_iterations": int,
    "search_reflection_max_rounds": int,
    "forum_max_rounds": int,
    "forum_min_rounds_for_sufficient": int,
}

shared["analysis_context"] = {
    "user_analysis_instruction": str,
    "time_range": {"start": str, "end": str, "span_hours": float, "source_field": str} | None,
    "time_range_text": str,
}

shared["forum"] = {
    "current_round": 0,
    "rounds": [],
    "debate_logs": [],
    "current_directive": {},
    "visual_analyses": [],
}

shared["trace"]["loop_status"] = {
    "data_agent": {"current": int, "max": int, "termination_reason": str},
    "search_reflection": {"current": int, "max": int, "termination_reason": str},
    "forum": {"current": int, "max": int, "termination_reason": str},
}
```

`stage2_results` 继续向后兼容，核心字段不变，保留 `search_context` 并新增论坛综合上下文（如 `forum_conclusions`）。
其中 `search_context.forum_debate_logs` 为 Stage3 提供可直接引用的主持人纪要上下文。

---

## 5. 测试覆盖（B1~B9）

### 5.1 Unit

- `tests/unit/stage2/test_stage2_search_flow.py`
- `tests/unit/stage2/test_stage2_search_agent.py`
- `tests/unit/stage2/test_stage2_parallel_flow.py`
- `tests/unit/stage2/test_stage2_data_agent_trace.py`
- `tests/unit/stage2/test_stage2_load_data.py`
- `tests/unit/stage2/test_stage2_forum.py`
- `tests/unit/stage2/test_stage2_supplement.py`
- `tests/unit/stage2/test_stage2_visual.py`
- `tests/unit/stage2/test_stage2_merge.py`
- `tests/unit/stage2/test_stage2_chart_analysis_gapfill.py`
- `tests/unit/stage2/test_stage2_insight.py`

### 5.2 Integration

- `tests/integration/pipeline/test_stage2_forum_pipeline_integration.py`

### 5.3 Live API E2E（B9）

- `tests/e2e/cli/test_cli_pipeline_e2e.py`
- `tests/e2e/cli/test_dashboard_pipeline_e2e.py`
- `tests/e2e/cli/test_tavily_live_api_e2e.py`

> E2E 运行态采用平衡档循环上限（`agent=3`, `search_reflection=2`, `forum=3`）以控制 API 成本与总耗时。
