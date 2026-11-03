# Agent Runtime、Gateway 与前端分层

更新：2026-11-03。本次采用用户提供的 backend/src 分层布局，复用既有领域代码。

## 参考版本与适配范围

参考 DeerFlow `1dd6d056278536af1cb4fc60347f4ca40fcb629b` 的
[官方架构](https://github.com/bytedance/deer-flow/blob/1dd6d056278536af1cb4fc60347f4ca40fcb629b/docs/ARCHITECTURE.md)。
该版本已使用独立 Harness/App 包；本项目按用户给出的 `backend/src/agents`、`gateway` 等目录表达同样的单向分层。
本系统名称仍为 Leader Agent / Agent Runtime / Domain Tool Service，不把参考项目名作为自有组件名称。
没有复制上游源码，不宣称与其全部功能或 LangGraph Platform HTTP API 兼容。

## 服务路径

Next.js → FastAPI → RunManager → LangGraph Lead graph → MCP → 持久领域 Job → 独立 Worker。
Agent 会话状态使用 LangGraph SQLite checkpointer；领域任务继续使用既有 JobStore，两种状态职责不同。
SSE 事件持久保存并提供游标续读；Agent 被取消与已提交的领域 Job 取消是两个明确操作。
Gateway 重启会将未结束的 Agent execution 标为 interrupted；模型在途调用费用可能未知，不保证恰好一次。

graph 为 context → leader → subagents → dispatch。结构化请求直接校验；自然语言请求通过真实 GLM 模型工厂
编译为 RunRequest。缺参数时返回 needs_input。默认专业评阅角色为 Insight/Query，有调用数量上限；
这是规划层评阅。业务论坛由同一领域 Worker 内的 `evidence/forum.py` 驱动，不能另开第二个任务调度器。

## 业务论坛：改进原第二阶段

保留 CollectTools → DecisionTools → ExecuteTools → ProcessResult → 图表覆盖检查与 ForumHost 反馈的职责。
`analytics/toolbox.py` 将 41 个保留工具接到统一记录契约；`select_tools` 选择互补分析，失败时使用明确记录的基础工具组合。
启用角色为 data、search、visual、insight、methodology 中的任务配置子集，主持人协调 supplement_data/search/visual。
每轮的意见、证据、共识、分歧、缺口、调用和停止原因持久化；无效决策不能推断为充分。
工具调用按数据指纹、工具版本和参数去重；补图也必须有源表。总轮数、工具数及模型/搜索账本共同限制执行。
详见[完整工作流](full-workflow.md)。

## 已写入的横向模块

- middlewares：会话目录、上下文截断、技能注入、字段/事件/数据引用校验；不是照搬上游中间件数量。
- memory：显式编辑的线程事实存储；外部资料不会自动写入长期记忆。
- checkpointer：AsyncSqliteSaver，持久化图状态。
- sandbox：受限线程文件区，不提供任意 shell，不冒充 OS 级执行沙箱。
- mcp：加载 extensions_config.json，发现并精确匹配真实工具名，禁止模糊授权。
- models：生成式 Agent 使用 GLM；决策标注模型独立配置为 GLM/Jev/阿里/连接器，密钥来自本机配置或环境。
- skills：加载已启用的 public/custom SKILL.md；当前提供 3 个项目技能，不声称自带上游 20+ 技能。
- subagents：角色注册和受限评阅执行；不开放嵌套委派。

## REST 与前端

6 组路由：threads、runs、events、datasets、artifacts、system；system 增加工具目录与写入式本机凭据配置。
客户端仅提交会话输入和配置；event_id 从线程记录解析。上传、任务、产物读取都走同一事件范围。
前端使用 App Router，聊天地址 `/workspace/chats/[threadId]`，通过 EventSource 接收阶段事件。
Next 开发代理 `/api`；容器由 Nginx 分流 `/api` 与前端页面。此 SSE 是本项目协议，未宣称兼容 LangGraph SDK。
报告支持 Markdown/HTML/JSON/ZIP 下载；ZIP 包含图表。完整领域分布、预测与情景计算继续复用已有实现。
Next 前端当前提供会话、配置、上传、任务、产物与报告；原 Streamlit 的细分图表交互保留为兼容视图，尚非完全界面等价。
会话模型调用数量按回合受限；领域调用与金额预算独立计算，当前没有跨层累计金额上限。

## 运行

```powershell
uv sync --project backend
npm --prefix frontend install
uv run --project backend python scripts/dev.py start
uv run --project backend python scripts/dev.py stop
```

本机入口 http://127.0.0.1:3000；Gateway 127.0.0.1:8001。无需为本机开发启动 Nginx。
脚本记录 PID 和创建时间，只停止自己启动且身份仍匹配的进程；Windows 后台进程不弹出窗口。
Compose 入口 127.0.0.1:2026；开发/生产模板均已提供，尚未实际启动验证。

根 config.yaml 现在是主应用配置；原配置保存到本机忽略文件 legacy/config.yaml。
backend/uv.lock 与 frontend/package-lock.json 固定依赖；根 pyproject/uv.lock 保留兼容环境。
旧包根目录只有兼容入口，实际实现已迁入 backend/src/domain。

## 验证阶段

按用户指示，Demo、真实标注、采集、科学实验和端到端测试后置。
安装依赖、源码语法/导入、Ruff 错误检查、后端 wheel 构建及 TypeScript 类型检查属于构建准备，不作为业务验收证据。
后端测试位置已建立；现有根目录测试仍保留，统一验证阶段需覆盖新路径和旧兼容入口。

实现依据另参见 [LangGraph 持久化](https://docs.langchain.com/oss/python/langgraph/persistence)、
[Next.js 安装](https://nextjs.org/docs/app/getting-started/installation)、
[FastAPI 生命周期](https://fastapi.tiangolo.com/advanced/events/)、
[UV Docker](https://docs.astral.sh/uv/guides/integration/docker/)。
