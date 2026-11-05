import asyncio
import copy
import json
import uuid
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from opinion_core.scenarios.paired import compare_scenarios
from opinion_gateway.assets import ArtifactStore
from opinion_gateway.diagnostics import exception_details
from opinion_gateway.jobs import JobStore
from ..dependencies import settings, store
from ..intelligent_ui import context_for, stream_model

router = APIRouter(prefix="/api/threads/{thread_id}/intelligence", tags=["intelligent UI"])


class Filters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str | None = Field(default=None, max_length=128)
    start: date | None = None
    end: date | None = None
    platform: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def dates(self):
        if self.start and self.end and self.start > self.end:
            raise ValueError("start must not exceed end")
        return self


class ChatBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=8000)
    locale: Literal["zh-CN", "en-US"] = "zh-CN"
    page: str = Field(default="overview", max_length=40)
    filters: Filters = Field(default_factory=Filters)


@router.get("/context")
def context(thread_id: str, dataset_id: str | None = None, start: date | None = None, end: date | None = None, platform: str | None = None, db=Depends(store), config=Depends(settings)):
    if start and end and start > end:
        raise HTTPException(422, "start must not exceed end")
    return context_for(config, db, thread_id, Filters(dataset_id=dataset_id, start=start, end=end, platform=platform))


@router.get("/messages")
def history(thread_id: str, db=Depends(store)):
    return db.ui_history(thread_id)


@router.post("/chat")
async def chat(thread_id: str, body: ChatBody, request: Request, db=Depends(store), config=Depends(settings)):
    snapshot = await asyncio.to_thread(context_for, config, db, thread_id, body.filters)
    prompt = Path(__file__).resolve().parents[1].joinpath("openui_prompt.txt").read_text(encoding="utf8")
    history = db.ui_history(thread_id)[-12:]
    # Send bounded chart data, never model particles, credential configuration or arbitrary client context.
    snapshot["charts"] = {key: {**value, "data": (value.get("data") or [])[:60]} for key, value in snapshot["charts"].items()}
    messages = [{"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps({"locale": body.locale, "page": body.page, "event_context": snapshot}, ensure_ascii=False)}]
    messages.extend({"role": row["role"], "content": row["content"][:16000]} for row in history if row.get("status") == "completed")
    messages.append({"role": "user", "content": body.message})
    try:
        execution = db.begin_execution(thread_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    db.event(thread_id, "ui_message", {"role": "user", "content": body.message, "status": "completed", "execution_id": execution})

    async def events():
        content, usage, status, error = "", {}, "cancelled", None
        def event(kind, data):
            return f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        try:
            yield event("status", {"phase": "generating", "execution_id": execution})
            async for item in stream_model(config, messages):
                if await request.is_disconnected():
                    break
                if "delta" in item:
                    content += item["delta"]
                    if len(content) > 64000:
                        raise ValueError("UI response exceeds 64000 characters")
                    yield event("delta", item)
                if "usage" in item:
                    usage = item["usage"]
            else:
                if not content.strip():
                    raise ValueError("Model returned an empty UI response")
                status = "completed"
                yield event("complete", {"usage": usage})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            status, error = "failed", exception_details(exc, stage="intelligent_ui")
            yield event("error", error)
        finally:
            db.event(thread_id, "ui_message", {"role": "assistant", "content": content, "status": status, "usage": usage, "error": error, "execution_id": execution, "filters": body.filters.model_dump(mode="json")})
            db.finish_execution(execution, status, error["error_type"] if error else "")

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class SimulationBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    job_id: str = Field(min_length=1, max_length=128)
    horizon: int = Field(default=7, ge=1, le=30)
    dimension: Literal["stance", "sentiment"] = "stance"
    shift: float = Field(default=0.1, ge=-1, le=1)
    duration: int = Field(default=1, ge=1, le=30)
    assumption: str = Field(min_length=1, max_length=1000)


@router.get("/simulations")
def simulations(thread_id: str, db=Depends(store)):
    return db.ui_history(thread_id, "ui_simulation", 10)


@router.post("/simulate")
async def simulate(thread_id: str, body: SimulationBody, db=Depends(store), config=Depends(settings)):
    event = db.get(thread_id)["event_id"]
    jobs, assets = JobStore(config.asset_root / "jobs.sqlite"), ArtifactStore(config.asset_root)
    job = jobs.get(body.job_id)
    if job.event_id != event:
        raise KeyError(body.job_id)
    refs = jobs.result(job.job_id).get("artifacts", {}) if job.status in {"completed", "partial"} else {}
    if not refs.get("state"):
        raise HTTPException(409, "请先完成意见动力学训练 / Train an opinion dynamics model first")
    state = copy.deepcopy(assets.read(event, refs["state"].get("run_id", job.run_id), refs["state"]["artifact_id"], "state"))
    if "ensemble" not in state:
        raise HTTPException(409, "训练结果缺少可用模型状态 / Fitted model state unavailable")
    if body.duration > body.horizon:
        raise HTTPException(422, "duration must not exceed horizon")
    try:
        execution = db.begin_execution(thread_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    try:
        state["config"]["horizon"] = body.horizon
        spec = {"scenario_id": "interactive", "dimension": body.dimension, "shift": body.shift, "duration": body.duration, "assumptions": [body.assumption]}
        value = await asyncio.to_thread(compare_scenarios, state, [spec])
        charts = {}
        for dimension in ("stance", "sentiment"):
            rows = [{"label": str(step["step"]), "series": label, "value": step["fields"][dimension]["mean"]} for label, result in [("baseline", value["baseline"]), ("scenario", value["branches"][0]["result"])] for step in result["steps"]]
            charts[dimension] = {"title": dimension, "chart": {"kind": "line"}, "data": rows}
        ref = assets.put(event, "ui-scenario-" + uuid.uuid4().hex[:12], "scenarios", value)
        saved = {"source_job_id": job.job_id, "source_run_id": job.run_id, "parameters": body.model_dump(), "charts": charts, "metrics": value["branches"][0]["metrics"], "artifact": ref, "kind": "conditional_simulation"}
        db.event(thread_id, "ui_simulation", saved)
        db.finish_execution(execution, "completed")
        return saved
    except Exception as exc:
        db.finish_execution(execution, "failed", type(exc).__name__)
        raise HTTPException(400, exception_details(exc)["message"]) from exc
