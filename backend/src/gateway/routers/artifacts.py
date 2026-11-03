from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
import io, json, zipfile
from opinion_gateway.assets import ArtifactStore
from ..dependencies import runtime, store, settings

router = APIRouter(
    prefix="/api/threads/{thread_id}", tags=["domain jobs and artifacts"]
)


@router.get("/jobs")
async def jobs(thread_id: str, db=Depends(store), manager=Depends(runtime)):
    return await manager.mcp.call(
        "list_jobs", {"event_id": db.get(thread_id)["event_id"]}
    )


@router.get("/jobs/{job_id}")
async def job(thread_id: str, job_id: str, db=Depends(store), manager=Depends(runtime)):
    return await manager.mcp.call(
        "job_status", {"event_id": db.get(thread_id)["event_id"], "job_id": job_id}
    )


@router.post("/jobs/{job_id}/{action}")
async def action(
    thread_id: str,
    job_id: str,
    action: str,
    db=Depends(store),
    manager=Depends(runtime),
):
    tools = {"cancel": "cancel_job", "retry": "retry_job", "resume": "resume_job"}
    if action not in tools:
        raise ValueError("unknown job action")
    return await manager.mcp.call(
        tools[action], {"event_id": db.get(thread_id)["event_id"], "job_id": job_id}
    )


@router.get("/jobs/{job_id}/result")
async def result(
    thread_id: str, job_id: str, db=Depends(store), manager=Depends(runtime)
):
    return await manager.mcp.call(
        "read_job_artifact",
        {"event_id": db.get(thread_id)["event_id"], "job_id": job_id},
    )


@router.get("/artifacts/{run_id}/{artifact_id}")
async def artifact(
    thread_id: str,
    run_id: str,
    artifact_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(store),
    manager=Depends(runtime),
):
    return await manager.mcp.call(
        "read_domain_artifact",
        {
            "event_id": db.get(thread_id)["event_id"],
            "run_id": run_id,
            "artifact_id": artifact_id,
            "offset": offset,
            "limit": limit,
        },
    )


@router.get("/exports/{run_id}/{artifact_id}")
async def export(
    thread_id: str,
    run_id: str,
    artifact_id: str,
    format: str = "json",
    db=Depends(store),
    manager=Depends(runtime),
    config=Depends(settings),
):
    if format not in {"json", "markdown", "html", "zip"}:
        raise ValueError("unsupported export format")
    event = db.get(thread_id)["event_id"]
    await manager.mcp.call(
        "read_domain_artifact",
        {"event_id": event, "run_id": run_id, "artifact_id": artifact_id},
    )
    data = ArtifactStore(config.asset_root).read(event, run_id, artifact_id)
    if format == "json":
        return Response(
            json.dumps(data, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="artifact.json"'},
        )
    if format == "zip":
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            for key, name in [("markdown", "report.md"), ("html", "report.html")]:
                if key in data:
                    archive.writestr(name, data[key])
            for name, value in data.get("images", {}).items():
                if name not in {"sentiment.svg", "stance.svg"}:
                    raise ValueError("unknown chart name")
                archive.writestr("images/" + name, value)
            archive.writestr(
                "artifact.json", json.dumps(data, ensure_ascii=False, indent=2)
            )
        return Response(
            stream.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="report.zip"'},
        )
    if format not in data:
        raise ValueError("artifact does not contain requested format")
    extension = "md" if format == "markdown" else "html"
    return Response(
        data[format],
        media_type="text/plain" if format == "markdown" else "text/html",
        headers={"Content-Disposition": f'attachment; filename="report.{extension}"'},
    )
