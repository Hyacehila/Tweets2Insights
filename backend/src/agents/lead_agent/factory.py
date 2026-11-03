from langgraph.graph import StateGraph, START, END
from opinion_core.schemas.workflow import RunRequest
from src.agents.thread_state import ThreadState
from src.agents.middlewares import prepare_context, validate_request
from src.subagents import SubagentExecutor
from .prompts import SYSTEM_PROMPT


def make_lead_agent(settings, models, tools, skills, checkpointer=None):
    async def prepare(state):
        return prepare_context(state, settings, skills)

    async def reason(state):
        request = state.get("run_request")
        usage = []
        count = 0
        if request is None:
            if settings.max_agent_calls < 1:
                raise ValueError("agent model budget exhausted")
            reply, measurement = await models.request(
                SYSTEM_PROMPT,
                {
                    "event_id": state["event_id"],
                    "datasets": state["datasets"],
                    "messages": state["messages"],
                    "message": state["message"],
                    "memory": state.get("memory", {}),
                    "skills": state["skills"],
                    "request_schema": RunRequest.model_json_schema(),
                },
            )
            request = reply.get("request")
            usage = [measurement]
            count = 1
            if request is None:
                return {
                    "run_request": None,
                    "status": "needs_input",
                    "reply": str(reply.get("reply", "请补充运行参数。")),
                    "model_calls": count,
                    "model_usage": usage,
                }
        request = validate_request(state, request)
        plan = await tools.plan(state, request)
        return {
            "run_request": request,
            "plan": plan,
            "status": "planned",
            "model_calls": count,
            "model_usage": usage,
        }

    async def delegate(state):
        # Explicit structured requests already have complete settings; avoid gratuitous model reviews.
        roles = ["insight", "query"] if state.get("model_calls") else []
        results = []
        usage = list(state["model_usage"])
        count = state["model_calls"]
        executor = SubagentExecutor(models)
        for role in roles[: settings.max_subagents]:
            if count >= settings.max_agent_calls:
                break
            result = await executor.review(
                role, {"request": state["run_request"], "plan": state["plan"]}
            )
            results.append(result)
            usage.append(result["usage"])
            count += 1
        return {"subagent_results": results, "model_calls": count, "model_usage": usage}

    async def submit(state):
        if state.get("execute"):
            job = await tools.submit(state, state["run_request"])
            return {
                "job": job,
                "status": "submitted",
                "reply": "任务已提交至独立领域 Worker。可在任务面板查看阶段、产物和停止原因。",
            }
        return {
            "status": "planned",
            "reply": "计划已生成。可检查并修改运行参数，再通过执行按钮提交。",
        }

    graph = StateGraph(ThreadState)
    graph.add_node("context", prepare)
    graph.add_node("leader", reason)
    graph.add_node("subagents", delegate)
    graph.add_node("dispatch", submit)
    graph.add_edge(START, "context")
    graph.add_edge("context", "leader")
    graph.add_conditional_edges(
        "leader",
        lambda state: "done" if state["status"] == "needs_input" else "review",
        {"done": END, "review": "subagents"},
    )
    graph.add_edge("subagents", "dispatch")
    graph.add_edge("dispatch", END)
    return graph.compile(checkpointer=checkpointer)
