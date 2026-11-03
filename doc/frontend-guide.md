# 前端说明

更新：2026-11-03。新默认界面位于 `frontend/src`，使用 Next.js App Router、React 和 TypeScript。

- `app/workspace`：研究工作区；`app/workspace/chats/[threadId]`：事件会话。
- `components/workspace.tsx`：会话列表、聊天、JSON 上传、数据选择、唯一搜索供应商和 RunRequest 编辑。
- `components/job-panel.tsx`：领域任务轮询、取消、重试、登录等待恢复和产物选择。
- `components/artifact-viewer.tsx`：有界产物读取、报告预览、JSON/Markdown/HTML/ZIP 下载。
- `hooks/use-thread-stream.ts`：EventSource 事件，使用持久事件游标重连。
- `lib`：API 客户端与 TypeScript 类型。

生成计划使用 `execute=false`；提交执行才创建领域 Job。若编辑器保留结构化请求，使用该请求；
清空后由 Leader 根据自然语言和现有数据列表规划。上传标准 JSON 不触发采集。
Agent 停止按钮停止当前图运行；已经提交的领域任务需要在任务卡片另行取消。
会话按事件隔离，同一事件的多个会话共享该事件数据和领域任务。

Next 代理 `/api`，容器由 Nginx 提供同源路由；前端不读取任何 API 密钥。
当前只做 TypeScript 检查，尚未浏览器验收。旧 Streamlit 专项图表和 PDF 导出继续保留，
新组件尚未覆盖全部旧交互；数据与计算继续来自复用领域实现。
