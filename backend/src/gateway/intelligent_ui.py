"""Event-scoped data bindings and model streaming for the OpenUI research canvas."""

import json
from datetime import datetime, timedelta, timezone

import httpx

from opinion_gateway.agent_models import active_config, api_key_for, is_local
from opinion_gateway.assets import ArtifactStore
from opinion_gateway.dataset_repository import DatasetRepository
from opinion_gateway.jobs import JobStore
from opinion_gateway.workspace_views import overview, summarize_records


def context_for(config, db, thread_id, filters):
    thread = db.get(thread_id)
    root, event = config.asset_root, thread["event_id"]
    dashboard = overview(root, [thread], thread_id)
    dataset_id = filters.dataset_id or (dashboard.get("dataset") or {}).get("dataset_id")
    try:
        records = DatasetRepository(root).read(event, dataset_id) if dataset_id else []
    except FileNotFoundError as exc:
        raise KeyError(dataset_id) from exc
    total = len(records)
    platforms = sorted({row.get("platform") or "未知" for row in records})

    def include(row):
        if filters.platform and (row.get("platform") or "未知") != filters.platform:
            return False
        if not (filters.start or filters.end):
            return True
        try:
            day = datetime.fromisoformat(row["published_at"]).astimezone(timezone(timedelta(hours=8))).date()
        except (KeyError, TypeError, ValueError):
            return False
        return (not filters.start or day >= filters.start) and (not filters.end or day <= filters.end)

    dataset = summarize_records([row for row in records if include(row)], dataset_id) if dataset_id else None
    # Analysis results keep their immutable run scope instead of pretending that a post filter recomputed them.
    analysis = {"analysis:" + key: value for key, value in dashboard.get("charts", {}).items()}
    charts = {**(dataset or {}).get("charts", {}), **analysis}
    jobs = JobStore(root / "jobs.sqlite")
    model_runs = []
    for job in jobs.list_jobs(event):
        if job.status not in {"completed", "partial"}:
            continue
        refs = jobs.result(job.job_id).get("artifacts", {})
        if refs.get("state"):
            if job.kind == "report_run":
                continue
            state = ArtifactStore(root).read(event, refs["state"].get("run_id", job.run_id), refs["state"]["artifact_id"], "state")
            if "ensemble" in state:
                model_runs.append({"job_id": job.job_id, "run_id": job.run_id, "algorithm": state.get("config", {}).get("algorithm")})
    return {
        "thread_id": thread_id, "event_id": event, "title": thread["title"],
        "dataset": dataset, "total_posts": total, "platforms": platforms,
        "charts": charts, "chart_catalog": [{"key": key, "title": value.get("title", key), "scope": "analysis_run" if key.startswith("analysis:") else "filtered_dataset"} for key, value in charts.items()],
        "run_id": dashboard.get("run_id"), "report": dashboard.get("report"), "model_runs": model_runs,
        "filters": filters.model_dump(mode="json"),
    }


async def stream_model(settings, messages):
    config = active_config(settings.agent_model_config)
    key = api_key_for(config)
    if not key and not is_local(config):
        raise ValueError("请先在模型与服务设置中配置 Agent 模型 / Configure an Agent model in Settings")
    payload = {"model": config.model, "messages": messages, "stream": True,
               "stream_options": {"include_usage": True}, "max_tokens": min(config.max_tokens, 8192), **config.extra_body}
    async with httpx.AsyncClient(timeout=httpx.Timeout(config.timeout_seconds, connect=10), follow_redirects=False) as client:
        async with client.stream("POST", config.base_url + "/chat/completions", headers={"Authorization": f"Bearer {key}"} if key else {}, json=payload) as response:
            if response.status_code != 200:
                body = (await response.aread()).decode("utf8", errors="replace")[:2500]
                raise ValueError(f"{config.model}: HTTP {response.status_code}: " + (body.replace(key, "[redacted]") if key else body))
            finished = False
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    break
                value = json.loads(raw)
                if value.get("error"):
                    raise ValueError(str(value["error"]))
                if value.get("usage"):
                    yield {"usage": value["usage"]}
                for choice in value.get("choices", []):
                    if choice.get("finish_reason"):
                        if choice["finish_reason"] != "stop":
                            raise ValueError("UI generation incomplete: " + choice["finish_reason"])
                        finished = True
                    delta = choice.get("delta", {}).get("content")
                    if isinstance(delta, str) and delta:
                        yield {"delta": delta}
            if not finished:
                raise ValueError("Model stream ended before a complete answer")
