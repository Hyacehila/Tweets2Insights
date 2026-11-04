# 前端工作台

前端基于 Next.js App Router、React、TypeScript、Tailwind CSS 和 Recharts，采用 [Tremor Templates](https://blocks.tremor.so/templates) 的数据工作台布局。Card、Badge 和样式工具来自 Overview 模板，许可保存在 `frontend/TREMOR_LICENSE`。

## 页面与操作

| 入口 | 用途 |
|---|---|
| 研究概览 | 查看研究会话、事件数量和当前事件的任务统计；搜索并继续研究 |
| 研究工作台 | 上传或选择数据、填写关键词、配置复盘/预测/情景/回测，与 Leader Agent 对话并执行 |
| 数据集 | 上传标准帖子 JSON 数组及对应配图、筛选数据版本、选择本次研究的数据 |
| 分析与报告 | 按状态筛选任务，取消/重试/恢复，查看图表、论坛、报告及下载产物 |
| API 设置 | 选择通用 Agent 模型，配置 OpenAI Decisions、Jev、阿里 Decision、Tavily、DeepSeek 和 X |

点击“新建研究”，填写研究名称与事件标识。同一事件标识下的会话共享该事件的数据和任务。
在侧栏“最近研究”中右键某项，选择“删除事件”，确认后删除该事件的全部研究会话、标注与分析结果、预测、情景模拟和报告。导入或采集的数据集保留；以后使用相同事件标识新建研究，即可重新选择这些数据。若该事件有任务运行，先停止 Agent 及分析任务，待任务结束后再删除。删除当前事件后自动返回研究概览。
API 设置可在创建研究前直接使用。界面支持明暗主题，窄屏通过顶部导航按钮打开侧栏。
“Agent 模型”提供 Qwen3.8-Max、GLM-5.3 预设以及自定义 OpenAI 兼容服务。页面说明模型能力要求，支持输入 Base URL、Model ID、API Key，并调整输出长度、超时及生成参数。“检测并保存”通过一次简短请求检查接口与 JSON 输出，成功后清空密钥输入。详见[模型配置](configuration.md#agent-模型)。
侧栏展示主导航和最近研究，模型及凭据配置统一从主导航的“API 设置”进入。Next.js 开发工具的黑色 N 浮标由 `next.config.ts` 中的 `devIndicators: false` 关闭；需要调试时可改为 `{ position: "bottom-right" }`。框架编译与运行错误仍正常提示。
顶部“中文 / EN”按钮切换导航、配置表单、任务状态、API 设置及图表和报告操作的显示语言。语言选择保存在本机浏览器，刷新后继续使用；切换时保留研究参数、当前会话和表单输入。事件名称、帖子、Agent 回复与报告正文保持其原始语言。

选择数据和阶段后点击“应用研究配置”，再由 Leader 生成计划或开始执行。需要自然语言规划时，在高级运行配置中选择“改用自然语言规划”。高级配置保留 JSON 编辑入口。
上传数据只进行校验与登记；使用关键词采集时，配置平台及时间范围。预测参数标明 PCA + HK 实验模型。
标注模型按 OpenAI Decisions、TypeSafe Jev、阿里 Decision 排列，默认选择 OpenAI Decisions 的 `gpt-6-luna`。API 设置中保留独立 OpenAI 凭据入口，支持中英文说明。

“帖子输入模态”默认图文联合，可切换为仅文字。“每帖配图上限”默认 3 张，可设为 1–9 张，按原始配图顺序选择。模型能力从后端 `/api/label-capabilities` 获取：OpenAI Decisions 和已登记的 Jev 模型支持配图；选择纯文本模型时，界面显示提醒并停用图片设置，后端同样强制只发送文本。高级 JSON 与 Leader 生成的配置也显示对应提醒。任务产物保留图片选择统计和失败提示。

上传时可同时选择一个帖子 JSON 与对应 JPG、PNG、WebP 文件。JSON 的 `media_refs` 填图片网址或本地文件名，例如 `"media_refs": ["rain-01.jpg", "rain-02.png"]`；本地文件按文件名关联，公网地址保持原值。图片通过独立接口上传，每张不超过 16 MiB。图片资产和帖子数据一起保留，事件删除不会删除它们。

“停止”结束当前 Agent 运行；已提交的领域任务在“分析与报告”中单独取消。任务完成后，可在产物区域选择工具，对冻结标签补充分析。

## 数据与图表

所有统计读取实际会话、数据集和任务。未选择事件时，事件内任务指标显示“—”；没有研究结果时显示空状态。
柱图、折线图、区间和环形图使用 Recharts，支持悬停、序列筛选和源数据表。仅在结果页显示时挂载图表，避免隐藏页面的零尺寸绘图。热图、词云和网络保留领域专用绘图。
时间序列缺失值保持 null，折线不跨越缺口。图表使用当前分页预览，完整数据通过 JSON 下载。
报告按章节展示观测、预测、模拟与解释，并提供证据来源和 Markdown/HTML/JSON/ZIP 导出。

## 代码位置

- `components/workspace.tsx`：导航、概览、会话、数据输入、研究配置与 Leader 交互。
- `components/recent-research.tsx`：最近研究列表、右键菜单与事件删除确认。
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
- `hooks/use-thread-stream.ts`：带持久游标的 SSE 事件续读。

Next.js 将 `/api` 代理到本机 FastAPI。工作台入口为 `/workspace`，事件会话地址为 `/workspace/chats/[threadId]`。
代理请求缓冲上限为 24 MiB，容纳单张 16 MiB 图片的独立上传；后端在流式读取时执行图片大小限制。
语言转换检查使用 `npm --prefix frontend test`。开发检查使用 `npm --prefix frontend run check`，生产构建使用 `npm --prefix frontend run build`。
