# Agent 复盘报告

更新：2026-11-05

报告按“内容主笔 → 社科解读 → 版式编辑 → 网页与 PDF 发布”执行。主笔采用旧版 `data/report_template.md` 的章节结构，包内模板为 `opinion_core/reporting/report_template.md`，测试检查两者一致。

## 内容与排版

ContentAgent 先阅读全部分析概要与证据目录，规划各章论证重点、图表和证据，再按章写出完整正文。模板的 11 章覆盖摘要、发展脉络、总体趋势、焦点窗口、传播主体、内容结构、信念系统、区域差异、风险、建议与附录；有预测或情景结果时加入对应章节。没有数据支持的议题简述资料缺口。

每章最多选用 4 张图与 8 条证据。长表提供首尾、各序列极值和等间隔预览，明确标记预览范围；完整数据仍随报告图表保存，统计不因预览而改变。

每段保存标题、正文、内容类型、证据 ID、数值引用和图表 ID。统计量由原始指标与图表源表提供，正文通过 `{{numeric_ref}}` 引用。系统校验引用、占位符和内容结构；无效章节向同一 Agent 提供错误修订一次，仍失败则将具体章节与错误传给进程追踪。

章节完成后保存到事件的 `report-drafts/`，检查点包含输入内容指纹。失败重试复用已完成章节；改变来源数据或报告模板后使用新指纹。ContentAgent 每次开始新章发送 `report_chapter` 事件，监控 Agent 汇报章名和进度。

SocialScienceAgent 补充框架理论、议程设置和风险沟通解释。ReportUIAgent 阅读完整内容，组织章节标题、段落顺序、重点摘要、双栏比较和图表位置。校验每个内容块、每张图表恰好使用一次，并保持各原章节完整；排版错误同样修订一次后显式失败。

## 一份内容，两类交付

- **工作台网页版**：验证后的 Agent 布局编译为 OpenUI Lang，使用 `ReportPage / ReportSection / ReportBlock / ReportChart` 四类组件。支持目录、关键词定位、章节切换、证据展开和真实交互图表；数据固定为该报告运行版本。
- **PDF**：ReportLab 在服务端直接生成 A4 文件，包含封面、目录、章节正文、矢量图表、引用索引和页码。与网页共用内容、数值解析和布局引用；PDF 单栏排版适配打印阅读。
- **其他导出**：独立 HTML、Markdown、JSON 和包含 PDF/HTML/Markdown/SVG 的 ZIP。

PDF 随报告生成并写入不可变报告资产，下载不再调用模型。已有旧报告可在下载时使用同一导出器生成 PDF。中文字体优先使用 `T2I_REPORT_FONT` 指定的 TrueType 字体或本机宋体/文泉驿；无本机字体时使用 PDF 的 STSong CJK 字体。字体通过 ReportLab 处理，无需浏览器打印服务。

静态折线图、条形图和热图由完整冻结数据表重新绘制，长时间序列采用横向时间轴，缺失值留空或显示灰色。图内标签使用同一中文字体。参考资料给出来源及精简摘录，完整证据仍可在网页展开查看。

## 接口与版本

`POST /api/threads/{thread_id}/jobs/{job_id}/report` 从已完成或部分完成的分析/报告任务提交新报告版本，返回 `report_run` 作业。它复用冻结的分析、标签与图表，只执行 content、theory、structure、report 四个阶段，使用当前 Agent 模型配置并独立记录调用用量。原研究配置中的调用次数和费用上限继续适用。

`GET /api/threads/{thread_id}/exports/{run_id}/{artifact_id}?format=pdf` 返回 `application/pdf` 附件。事件归属与报告发布状态由服务端验证；报告在全部生成步骤成功后发布。`format=zip` 包含 PDF。

报告中心提供“重新生成报告”、版本选择与“下载 PDF”。进程追踪保留监控汇报、各 Agent 状态、逐章日志、停止、重试及失败详情。删除事件时一并清理报告、草稿和计算结果，输入数据仍保留。

DeepSeek 官方端点的 `deepseek-flash` / `deepseek-v4-pro` 默认开启高强度思考。报告阶段在用户未显式设置 `thinking` 或 `reasoning_effort` 时采用 `reasoning_effort=low`，使逐章写作适配已配置的输出上限；显式参数保持优先。其他供应商沿用其配置。[官方参数说明](https://api-docs.deepseek.com/guides/thinking_mode/)

## 实现位置

| 文件 | 职责 |
|---|---|
| `reporting/composition.py` | 模板、逐章生成、引用校验与章节检查点 |
| `reporting/agents.py` | 内容、社科和排版 Agent |
| `reporting/structure.py` | 章节与图表完整性 |
| `reporting/document.py` | 同源数值、证据编号与 OpenUI 程序 |
| `reporting/render.py` / `pdf.py` / `charts.py` | 网页、文本和 PDF 发布、完整数据矢量图 |
| `opinion_gateway/application.py` / `domain_worker.py` | 报告任务与版本 |
| `frontend/src/lib/report-schema.mjs` | OpenUI 报告组件契约 |
| `frontend/src/components/report-view.tsx` | 阅读、目录、图表与证据 |

`backend/tests/test_report_pipeline.py` 覆盖模板一致、完整内容、引用修订、章节复用、PDF 内容、下载及事件隔离；既有 Worker 测试覆盖主流程调用。前端测试使用实际 OpenUI SDK 解析组件程序。
