# 阶段 3：报告生成子系统

本文记录旧 PocketFlow 报告入口。当前 Next.js 工作台沿用本模块的报告模板结构，运行链路见 [Agent 复盘报告](report-generation.md)。

> **文档状态**: 2026-11-03 更新
> **关联源码**: `nodes/stage3/*`, `flow.py`, `config.py`  
> **上级文档**: [系统设计总览](../architecture.md)

---

## 1. 概述

### 1.1 目标

将阶段 2 产出的图表、表格、洞察与 trace 追溯信息，统一生成为可交付报告产物：

- `report/report.md`（主报告）
- `report/report.html`（交互式 HTML）
- `report/trace.json`（追溯数据快照）

### 1.2 输入/输出

| 项目 | 说明 |
|:---|:---|
| 输入（内存优先） | `shared["stage2_results"]` + `shared["trace"]` |
| 输入（文件回退） | `report/analysis_data.json`, `report/chart_analyses.json`, `report/insights.json`, `report/trace.json`, `report/images/` |
| 输出 | `report/report.md`, `report/report.html`, `report/trace.json` |

---

## 2. 统一 Flow 拓扑

```mermaid
flowchart LR
    CL[ClearStage3Outputs] --> LR[LoadAnalysisResults]
    LR --> PO[PlanOutline]
    PO --> GC[GenerateChaptersBatch]
    GC --> RC[ReviewChapters]
    RC -- needs_revision --> GC
    RC -- satisfied --> IR[IRRenderer]
    IR --> IT[InjectTrace]
    IT --> MA[MethodologyAppendix]
    MA --> FR[FormatReport]
    FR --> RH[RenderHTML]
    RH --> SR[SaveReport]
    SR --> SC[Stage3Completion]
```

### 2.1 节点职责

| 节点 | 职责 |
|:---|:---|
| `ClearStage3OutputsNode` | 清理 `report.md/report.html`，保留 Stage2 产物、`images/` 与 `status.json` |
| `LoadAnalysisResultsNode` | 内存优先读取 Stage2 结果，文件回退加载 JSON 与 trace |
| `PlanOutlineNode` | LLM 规划报告布局（标题/副标题/hero/tocPlan/字数预算）；章节级 `allowSwot`/`allowPest` 组件权限锁在节点内做独占校验 |
| `GenerateChaptersBatchNode` | 并行逐章生成 **JSON IR blocks**（支持反馈驱动重生成）；提示词注入图表分析正文、洞察摘要、搜索背景、论坛辩论纪要、证据卡索引、组件权限；输出模式 `generation_mode=unified_json` |
| `ReviewChaptersNode` | 章节级评审循环，输出 `needs_revision/satisfied` 路由；对 `blocks` 先扁平化为文本再评审；占位符命中、段落缺少 `[E#]`、非法引用标记、重复标题、未授权 SWOT/PEST 块均硬失败并强制修订 |
| `IRRendererNode` | 将章节 JSON IR blocks 渲染为 Markdown（含 `paragraph/list/table/swotTable/pestTable/engineQuote/image`）并组装 `reviewed_report_text` |
| `InjectTraceNode` | 追加“参考资料与证据索引”精简附录（正文角标引用为主，附录用于审计） |
| `MethodologyAppendixNode` | 追加方法论附录（工具调用、循环状态、局限性） |
| `FormatReportNode` | 执行摘要注入、重复标题去重、目录生成、图片路径归一化、图表附录兜底 |
| `RenderHTMLNode` | Markdown 渲染为交互 HTML（图片放大预览 + `<details>` 保留 + 标题锚点/Markdown 链接可点击） |
| `SaveReportNode` | 保存 MD/HTML/trace 三类产物 |

---

## 3. 配置契约

`config.yaml` 中 Stage3 配置：

```yaml
stage3:
  max_iterations: 5
  chapter_review_max_rounds: 2
```

运行时映射到 `shared["config"]["stage3_review"]`：

- `chapter_review_max_rounds`

说明：

- `chapter_review_max_rounds` 控制 `ReviewChaptersNode` 的循环上限。
- Stage3 已移除 `min_score` 阈值，是否修订由评审输出与硬性质量规则共同决定。

---

## 4. Shared 契约（Stage3 关键字段）

### 4.1 `shared["stage3_data"]`

由 `LoadAnalysisResultsNode` 写入：

- `analysis_data`
- `analysis_data.analysis_context`
- `chart_analyses`
- `insights`
- `trace`
- `sample_blogs`
- `images_dir`

### 4.2 `shared["stage3_results"]`

统一流程写入：

- `outline`
- `hero`
- `chapters`
- `review_round`
- `chapter_review_history`
- `chapter_feedback`
- `reviewed_report_text`
- `report_text`
- `final_report_text`
- `final_report_html`
- `output_files`（`report_md/report_html/trace_file`）
- `report_file`
- `generation_mode`（章节阶段为 `unified_json`，最终格式化后为统一输出模式）

### 4.3 `shared["trace"]["loop_status"]["stage3_chapter_review"]`

记录章节评审循环状态：

- `current`
- `max`
- `termination_reason`（`sufficient` / `max_iterations_reached` / `continue`）
- `scores`

---

## 5. 报告内容增强规则

### 5.1 执行摘要注入

`FormatReportNode` 在正文前注入“运行执行摘要”，显示各循环的 `current/max/termination_reason`。

### 5.2 图片路径与附录

- 所有图片路径统一标准化为 `./images/...`。
- 若正文无图片引用但存在图表数据，自动追加“图表附录”。

### 5.3 Trace 追溯块

`InjectTraceNode` 将 `trace.insight_provenance` 归一化为证据索引附录，并兼容两种证据结构：

- 旧结构：`insight_key -> [ {source,evidence,...}, ... ]`
- 新结构：`insight_key -> {text, supporting_evidence:[...], confidence,...}`

正文证据融合规则：

- 每个实质性段落必须内嵌证据角标（如 `[E1]`）
- 多证据并列必须写作 `[E1][E2]`（禁止 `[E1, E2]`）
- 禁止输出非证据格式的方括号引用（如 `[topic_distribution]`）
- 禁止在章节正文重复输出同名标题行（避免与汇编标题重复）
- `swotTable/pestTable` 必须受大纲权限控制：全文最多一个 SWOT 块、最多一个 PEST 块，且不能同章出现
- `engineQuote` 仅用于引用论坛辩论纪要或搜索背景中的智能体原始观点
- 若缺失或违规，`ReviewChaptersNode` 会强制进入修订循环

---

## 6. 产物落盘

`SaveReportNode` 固定保存：

- `report/report.md`
- `report/report.html`
- `report/trace.json`

并将路径写回：

```python
shared["stage3_results"]["output_files"] = {
    "report_md": "report/report.md",
    "report_html": "report/report.html",
    "trace_file": "report/trace.json",
}
```

---

## 7. 阶段完成

`Stage3CompletionNode`：

- 将 `3` 追加到 `shared["pipeline_state"]["completed_stages"]`
- 更新 `shared["pipeline_state"]["current_stage"] = 3`
- 返回 `"default"`，在线性主链中继续进入 `TerminalNode`

## 领域工具复用（2026-11-03）

纯函数 _render_inlines/_render_block/render_blocks_to_markdown 迁到 opinion_core/reporting/ir_markdown.py；
旧 nodes.stage3.ir_renderer 保留导入兼容与节点类。领域服务无需为渲染文本导入完整 nodes/NLP/NumPy。
函数逻辑保持原样，旧渲染测试与真实 stdio 短报告同时回归。
