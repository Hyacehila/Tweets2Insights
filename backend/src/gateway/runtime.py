import asyncio
from src.agents.lead_agent import make_lead_agent
from src.models import ModelFactory
from src.mcp import DomainToolClient
from src.tools import DomainTools
from src.skills import SkillLoader


class RunManager:
    def __init__(self, settings, store, checkpointer):
        self.settings, self.store = settings, store
        self.mcp = DomainToolClient(settings)
        self.skills = SkillLoader(settings)
        self.graph = make_lead_agent(
            settings,
            ModelFactory(settings),
            DomainTools(self.mcp),
            self.skills,
            checkpointer,
        )
        self.tasks = {}

    async def start(self, thread_id, message, request, execute):
        thread = self.store.get(thread_id)
        execution_id = self.store.begin_execution(thread_id)
        self.store.append(thread_id, "user", message)
        self.tasks[execution_id] = asyncio.create_task(
            self._run(execution_id, thread, message, request, execute)
        )
        return self.store.execution(execution_id)

    async def _run(self, key, thread, message, request, execute):
        tid = thread["thread_id"]
        self.store.event(tid, "run_started", {"execution_id": key})
        try:
            async with asyncio.timeout(self.settings.request_timeout_seconds):
                datasets = await self.mcp.call(
                    "list_datasets", {"event_id": thread["event_id"]}
                )
                state = {
                    "thread_id": tid,
                    "event_id": thread["event_id"],
                    "datasets": datasets,
                    "messages": thread["messages"],
                    "message": message,
                    "run_request": request,
                    "execute": execute,
                    "memory": thread["memory"],
                }
                config = {"configurable": {"thread_id": tid}, "recursion_limit": 12}
                result = {}
                async for update in self.graph.astream(
                    state, config, stream_mode="updates"
                ):
                    for node, values in update.items():
                        if isinstance(values, dict):
                            result.update(values)
                            visible = {
                                k: v
                                for k, v in values.items()
                                if k
                                in {
                                    "status",
                                    "reply",
                                    "plan",
                                    "job",
                                    "subagent_results",
                                    "run_request",
                                    "model_calls",
                                    "model_usage",
                                }
                            }
                            self.store.event(
                                tid,
                                "agent_update",
                                {"execution_id": key, "node": node, **visible},
                            )
                self.store.append(tid, "assistant", result.get("reply", "处理结束。"))
                self.store.finish_execution(key, "completed")
                self.store.event(
                    tid, "run_finished", {"execution_id": key, "status": "completed"}
                )
        except asyncio.CancelledError:
            self.store.finish_execution(key, "cancelled")
            self.store.event(
                tid,
                "run_finished",
                {
                    "execution_id": key,
                    "status": "cancelled",
                    "in_flight_model_usage": "may_be_unknown",
                },
            )
        except Exception as exc:
            self.store.finish_execution(key, "failed", type(exc).__name__)
            self.store.event(
                tid,
                "run_finished",
                {
                    "execution_id": key,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                },
            )
        finally:
            self.tasks.pop(key, None)

    def cancel(self, thread, key):
        result = self.store.execution(key)
        if result["thread_id"] != thread:
            raise ValueError("execution belongs to another thread")
        task = self.tasks.get(key)
        if task:
            task.cancel()
        return result

    async def shutdown(self):
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
