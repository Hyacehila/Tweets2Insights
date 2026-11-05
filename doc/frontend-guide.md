# 前端工作台

前端基于 Next.js App Router、React、TypeScript、Tailwind CSS 和 Recharts，采用 [Tremor Templates](https://blocks.tremor.so/templates) 的数据工作台布局。Card、Badge 和样式工具来自 Overview 模板，许可保存在 `frontend/TREMOR_LICENSE`。

## 页面与操作

| 入口 | 用途 |
|---|---|
| 启动页 `/` | “智能舆情研判与情景推演平台”标题、平台简介、“开始舆情研究”入口及三段研究流程 |
| 研究概览 | 默认展示最近分析的指标和图表；无分析时展示已导入 Demo 的统计看板，可切换事件 |
| 研究工作台 → 研究配置与执行 | 上传或选择数据，配置阶段、模型、预算并运行 |
| 研究工作台 → 研究进程追踪 | 监控 Agent 汇报、各角色状态卡片、阶段进度、错误分析、用量及任务操作 |
| 研究工作台 → 分析与报告 | 最终分析报告、章节图表、证据及导出 |
| 研究工作台 → 数据集概览 | 数据版本、每日帖量和互动趋势、模态、平台、地区、字段缺失及高互动帖子 |
| API 设置 | Agent 模型、决策标注、搜索服务和 MediaCrawler 平台登录 |

工作台四个子页在同一事件内切换，配置表单保持不变。概览不显示事件标识或任务状态统计卡片，失败任务已完成的分析仍可进入看板。

启动页使用居中标题、蓝色入口按钮与原创浅蓝背景，以对话气泡、网络节点和流动光线表现信息传播。三个研究节点沿曲线错落排列，窄屏改为纵向排列。右上角“中文 / EN”切换整页语言，包括标题、简介、入口按钮和研究节点。英文标题为 “Public Opinion Intelligence & Scenario Simulation”，入口为 “Start Analysis”。选择自动保存，刷新及进入工作台后继续沿用。

“研究进程追踪”顶部选择运行版本，先展示流程监控 Agent 的当前汇报、阶段完成数、下一阶段和运行时间，再展示各 Agent 的等待、执行、完成与失败状态。错误分析列出原因、证据和处理建议，原始调用栈、运行日志及任务操作可展开查看。页面每两秒同步一次；正常监控不产生模型调用费用。

点击“新建研究”，填写研究名称与事件标识。同一事件标识下的会话共享该事件的数据和任务。
在侧栏“最近研究”中右键某项，可选择“重命名”，输入名称后按 Enter 保存；事件标识、数据和产物保持关联。选择“删除事件”，确认后删除该事件的全部研究会话、标注与分析结果、预测、情景模拟和报告。导入或采集的数据集保留；以后使用相同事件标识新建研究，即可重新选择这些数据。若该事件有任务运行，先停止 Agent 及分析任务，待任务结束后再删除。删除当前事件后自动返回研究概览。
API 设置可在创建研究前直接使用。界面支持明暗主题，窄屏通过顶部导航按钮打开侧栏。
“Agent 模型”提供 Qwen3.8-Max、GLM-5.3 预设以及自定义 OpenAI 兼容服务。页面说明模型能力要求，支持输入 Base URL、Model ID、API Key，并调整输出长度、超时及生成参数。“检测并保存”通过一次简短请求检查接口与 JSON 输出，成功后清空密钥输入。详见[模型配置](configuration.md#agent-模型)。
侧栏展示主导航和最近研究，模型及凭据配置统一从主导航的“API 设置”进入。Next.js 开发工具的黑色 N 浮标由 `next.config.ts` 中的 `devIndicators: false` 关闭；需要调试时可改为 `{ position: "bottom-right" }`。框架编译与运行错误仍正常提示。
顶部“中文 / EN”按钮切换导航、配置表单、任务状态、API 设置及图表和报告操作的显示语言。语言选择保存在本机浏览器，刷新后继续使用；切换时保留研究参数、当前会话和表单输入。事件名称、帖子、Agent 回复与报告正文保持其原始语言。

选择数据和阶段后点击“应用研究配置”，再由 Leader 生成计划或开始执行。需要自然语言规划时，在高级运行配置中选择“改用自然语言规划”。高级配置保留 JSON 编辑入口。
重新打开已有研究时，工作台从已保存计划恢复数据版本、关键词、时间范围、标注预算、输入模态与论坛参数，使表单和实际执行配置一致。
已有数据无需填写事件关键词，Schema Agent 从抽样帖子提取关键词，再检索证据与设计标签。关键词采集时填写搜索词，选择 MediaCrawler 平台及时间范围。预测参数标明 PCA + HK 实验模型。
标注模型按 OpenAI Decisions、TypeSafe Jev、阿里 Decision 排列，默认选择 OpenAI Decisions 的 `gpt-6-luna`。API 设置中保留独立 OpenAI 凭据入口，支持中英文说明。

“帖子输入模态”默认图文联合，可切换为仅文字。“每帖配图上限”默认 3 张，可设为 1–9 张，按原始配图顺序选择。模型能力从后端 `/api/label-capabilities` 获取：OpenAI Decisions 和已登记的 Jev 模型支持配图；选择纯文本模型时，界面显示提醒并停用图片设置，后端同样强制只发送文本。高级 JSON 与 Leader 生成的配置也显示对应提醒。任务产物保留图片选择统计和失败提示。

上传时可同时选择一个帖子 JSON 与对应 JPG、PNG、WebP 文件。JSON 的 `media_refs` 填图片网址或本地文件名，例如 `"media_refs": ["rain-01.jpg", "rain-02.png"]`；本地文件按文件名关联，公网地址保持原值。图片通过独立接口上传，每张不超过 16 MiB。图片资产和帖子数据一起保留，事件删除不会删除它们。

“停止”结束当前 Agent 运行；已提交的领域任务在“研究进程追踪”中单独取消。任务完成后可通过分析工具接口对冻结标签补充分析。

## 数据与图表

任务结果中的“用量与费用”按阶段和模型展示调用次数、输入／输出 Token、缓存 Token 及未返回 Token 的调用数。未返回完整费用时金额显示为未知，可展开原始用量记录核对账单。用量汇总见 `components/usage-summary.tsx` 与 `lib/usage-summary.ts`。本地试用数据的准备与操作见 [Demo 数据集](testing/event-demo-datasets.md)。

所有统计读取实际会话、数据集和任务。未选择事件时，事件内任务指标显示“—”；没有研究结果时显示空状态。
柱图、折线图、区间和环形图使用 Recharts，支持悬停、序列筛选和源数据表。仅在结果页显示时挂载图表，避免隐藏页面的零尺寸绘图。热图、词云和网络保留领域专用绘图。
时间序列缺失值保持 null，折线不跨越缺口。图表使用当前分页预览，完整数据通过 JSON 下载。
报告按章节展示观测、预测、模拟与解释，并提供证据来源和 Markdown/HTML/JSON/ZIP 导出。

## 代码位置

- `components/workspace.tsx`：导航、概览、会话、数据输入、研究配置与 Leader 交互。
- `components/recent-research.tsx`：最近研究、重命名和事件删除。
- `components/launch-page.tsx`：项目启动页。
- `frontend/public/images/opinion-flow-v1.png`：启动页背景，由 Next.js Image 优化加载；[生成提示词](diagrams/landing-background-prompt.md)。
- `components/research-dashboard.tsx`：分析大屏与数据集描述统计。
- `components/research-progress.tsx`：实时阶段、日志、异常和用量。
- `components/report-library.tsx`：最终报告与版本切换。
- `components/crawler-settings.tsx`：七个平台的登录方式、Cookie 与超时。
- `components/tremor/`、`lib/utils.ts`：复用的 Tremor 组件与样式工具。
- `components/provider-settings.tsx`：独立 API 配置页，成功保存后清空密钥输入。
- `components/agent-model-settings.tsx`：Agent 模型推荐、自定义接口、能力说明与兼容性检测。
- `components/workflow-builder.tsx`：阶段、标注、论坛、预测及情景参数。
- `components/media-input-notice.tsx`：模型模态提示、图片数量与失败提醒，中英文显示。
- `lib/dataset-import.ts`：帖子 JSON 与本地配图匹配、去重上传、原始顺序保留。
- `components/job-panel.tsx`：任务筛选、操作、产物切换及补充分析。
- `components/analysis-chart.tsx`、`specialty-chart.tsx`：通用数据图表与专用分析图。
- `components/artifact-viewer.tsx`、`report-view.tsx`、`forum-view.tsx`：产物、章节报告和论坛过程。
- `components/theme-provider.tsx`、`ui.tsx`：主题、对话框、状态与空状态。
- `components/language-provider.tsx`、`lib/i18n.ts`：语言上下文、偏好存储、中英文文案和插值。
- `hooks/use-thread-stream.ts`：带持久游标的 SSE 事件续读。Leader 日志通过 activity 接口恢复；领域进度每两秒读取 JobStore 的阶段、检查点与事件。

Next.js 将 `/api` 代理到本机 FastAPI。工作台入口为 `/workspace`，事件会话地址为 `/workspace/chats/[threadId]`。
代理请求缓冲上限为 24 MiB，容纳单张 16 MiB 图片的独立上传；后端在流式读取时执行图片大小限制。
语言转换检查使用 `npm --prefix frontend test`。开发检查使用 `npm --prefix frontend run check`，生产构建使用 `npm --prefix frontend run build`。

失败记录保存异常类型、正文、阶段和调用栈，过滤 API Key、Token、Cookie 等凭据。旧任务未记录的异常正文不会补造，界面明确显示其记录缺失。
