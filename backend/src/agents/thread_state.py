from typing import Any, TypedDict


class ThreadState(TypedDict, total=False):
    thread_id: str
    event_id: str
    message: str
    messages: list[dict[str, str]]
    datasets: list[dict]
    run_request: dict[str, Any] | None
    execute: bool
    plan: dict
    job: dict | None
    reply: str
    status: str
    skills: str
    memory: dict
    subagent_results: list[dict]
    model_calls: int
    model_usage: list[dict]
