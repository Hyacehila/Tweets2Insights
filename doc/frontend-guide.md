# 前端说明

更新：2026-11-03。新默认界面位于 `frontend/src`，使用 Next.js App Router、React 和 TypeScript。

- `app/workspace`：研究工作区；`app/workspace/chats/[threadId]`：事件会话。
- `components/workspace.tsx`：会话列表、聊天、JSON 上传、数据选择、唯一搜索供应商和 RunRequest 编辑。
- `components/workflow-builder.tsx`：数据/关键词路径、阶段、UTC 时间范围、论坛角色、决策模型、情景参数；本机写入式 API 凭据配置。
- `components/job-panel.tsx`：领域任务轮询、取消、重试、登录等待恢复和产物选择。
- `components/artifact-viewer.tsx`：有界产物读取、报告预览、JSON/Markdown/HTML/ZIP 下载。
- `components/analysis-chart.tsx`：柱、线、热图、网络、饼图、词云的交互显示；序列筛选、悬停、来源表翻页。
- `components/forum-view.tsx`：逐轮专业意见、主持共识/分歧、补充行动及停止原因。
- `components/report-view.tsx`：受约束布局驱动的章节报告，区分观测/预测/模拟/解释，并显示证据引用。
- `hooks/use-thread-stream.ts`：EventSource 事件，使用持久事件游标重连。
- `lib`：API 客户端与 TypeScript 类型。

生成计划使用 `execute=false`；提交执行才创建领域 Job。若编辑器保留结构化请求，使用该请求；
清空后由 Leader 根据自然语言和现有数据列表规划。上传标准 JSON 不触发采集。
修改阶段表单后须点击“将阶段与参数写入运行配置”；未应用时提交会明确提示，避免执行旧配置。
任务完成后可选工具再次分析冻结数据和标签，创建独立 analysis_tool 作业，保留原报告版本。
Agent 停止按钮停止当前图运行；已经提交的领域任务需要在任务卡片另行取消。
会话按事件隔离，同一事件的多个会话共享该事件数据和领域任务。

Next 代理 `/api`，容器由 Nginx 提供同源路由；配置后的密钥不回传前端，密码输入提交成功即清空。
图表展示有界预览，完整源表通过 JSON 导出；时间均值缺测使用 null，不绘制为零。
旧 Streamlit 的 PDF 导出等兼容交互继续保留。
`npm --prefix frontend run check` 先运行 Next typegen，再运行 TypeScript；新克隆无需依赖先前构建留下的路由类型文件。
