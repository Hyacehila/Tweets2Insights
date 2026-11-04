# Agent Runtime、Gateway 与前端分层

Agent Runtime 与 Gateway 分层，业务代码集中在 `backend/src/domain`。

## 参考版本与适配范围

参考 DeerFlow `1dd6d056278536af1cb4fc60347f4ca40fcb629b` 的
[官方架构](https://github.com/bytedance/deer-flow/blob/1dd6d056278536af1cb4fc60347f4ca40fcb629b/docs/ARCHITECTURE.md)。
本项目采用 `backend/src/agents`、`gateway` 和 `domain` 分层，分别承担 Agent 编排、应用接口和领域计算。

## 服务路径

Next.js → FastAPI → RunManager → LangGraph Lead graph → MCP → 持久领域 Job → 独立 Worker。
Agent 会话状态使用 LangGraph SQLite checkpointer；领域任务继续使用既有 JobStore，两种状态职责不同。
SSE 事件持久保存并提供游标续读；Agent 被取消与已提交的领域 Job 取消是两个明确操作。
Gateway 重启会将未结束的 Agent execution 标为 interrupted；在途模型请求的执行和费用状态记为未知。

graph 为 context → leader → subagents → dispatch。结构化请求直接校验；自然语言请求通过所选 OpenAI 兼容模型
编译为 RunRequest。缺参数时返回 needs_input。默认专业评阅角色为 Insight/Query，有调用数量上限；
这是规划层评阅。业务论坛由同一领域 Worker 内的 `evidence/forum.py` 驱动，不能另开第二个任务调度器。

## 业务论坛：改进原第二阶段

保留 CollectTools → DecisionTools → ExecuteTools → ProcessResult → 图表覆盖检查与 ForumHost 反馈的职责。
`analytics/toolbox.py` 将 41 个保留工具接到统一记录契约；`select_tools` 选择互补分析，失败时使用明确记录的基础工具组合。
启用角色为 data、search、visual、insight、methodology 中的任务配置子集，主持人协调 supplement_data/search/visual。
每轮持久保存意见、证据、共识、分歧、缺口、调用和停止原因；无效主持决策单独记录为异常停止。
工具调用按数据指纹、工具版本和参数去重；补图也必须有源表。总轮数、工具数及模型/搜索账本共同限制执行。
详见[完整工作流](full-workflow.md)。

## 通用模块

- middlewares：上下文截断、技能注入、字段/事件/数据引用校验。
- memory：显式编辑的线程事实存储；外部资料不会自动写入长期记忆。
- checkpointer：AsyncSqliteSaver，持久化图状态。
- mcp：加载 extensions_config.json，发现并精确匹配工具名；Gateway 读取 MCP 结构化结果，保留任务和产物中的动态字段。
- models：生成式 Agent 共用 OpenAI 兼容 JSON 适配器，默认 Qwen3.8-Max、备选 GLM-5.3，支持自定义接口。Leader 规划使用操作者选择的配置，任务提交后冻结公开模型参数。决策标注默认 OpenAI Decisions / gpt-6-luna，并支持 Jev/阿里/决策连接器；密钥从本机配置或环境读取。
- skills：加载已启用的 public/custom SKILL.md；内置 3 个项目技能。
- subagents：角色注册和受限评阅执行；不开放嵌套委派。

## REST 与前端

6 组路由：threads、runs、events、datasets、artifacts、system；system 增加工具目录与写入式本机凭据配置。
客户端仅提交会话输入和配置；event_id 从线程记录解析。上传、任务、产物读取都走同一事件范围。
`DELETE /api/threads/{thread_id}/event` 删除该会话所属事件的全部研究记录及产物，保留注册数据集。删除包含会话消息、记忆、SSE 事件、LangGraph 检查点、领域任务与批次、标注缓存、预算记录和报告；不同事件的记录保持独立。SQLite 写锁防止排队任务在清理时被 Worker 领取；运行中或正在取消的任务返回 409，需先停止并等待结束。
前端使用 App Router，聊天地址 `/workspace/chats/[threadId]`，通过 EventSource 接收阶段事件。
Next.js 为 `/api` 提供同源代理。SSE 使用本项目的事件协议。
报告支持 Markdown/HTML/JSON/ZIP 下载；ZIP 包含图表。完整领域分布、预测与情景计算继续复用已有实现。
Next 前端当前提供会话、配置、上传、任务、产物与报告；原 Streamlit 的细分图表与 PDF 导出保留为兼容视图。
会话模型调用数量按回合受限；领域调用与金额预算独立计算，当前没有跨层累计金额上限。

## 运行

```powershell
uv sync --project backend
npm --prefix frontend install
uv run --project backend python scripts/dev.py start
uv run --project backend python scripts/dev.py stop
```

本机入口 http://127.0.0.1:3000；Gateway 127.0.0.1:8001。
脚本记录 PID 和创建时间，只停止自己启动且身份仍匹配的进程；Windows 后台进程不弹出窗口。

根 config.yaml 现在是主应用配置；原配置保存到本机忽略文件 legacy/config.yaml。
backend/uv.lock 与 frontend/package-lock.json 固定依赖；根 pyproject/uv.lock 保留兼容环境。
旧包根目录只有兼容入口，实际实现已迁入 backend/src/domain。

## 测试与参考

新后端测试位于 `backend/tests`，领域契约与历史模块测试位于根目录 `tests`。
命令见[测试工作流](../testing/testing_workflow.md)，执行结果见[实施记录](../upgrade-status.md)。

实现依据另参见 [LangGraph 持久化](https://docs.langchain.com/oss/python/langgraph/persistence)、
[Next.js 安装](https://nextjs.org/docs/app/getting-started/installation)、
[FastAPI 生命周期](https://fastapi.tiangolo.com/advanced/events/)。
