from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import Response
import io, json, zipfile, re, base64, asyncio
from opinion_gateway.assets import ArtifactStore
from opinion_gateway.application import ApplicationService
from ..dependencies import runtime, store, settings

router = APIRouter(
    prefix="/api/threads/{thread_id}", tags=["domain jobs and artifacts"]
)


@router.post("/jobs/{job_id}/report")
def regenerate_report(
    thread_id: str, job_id: str, db=Depends(store), config=Depends(settings)
):
    from opinion_gateway.application import ApplicationService

    return ApplicationService(config.asset_root).submit_report(
        db.get(thread_id)["event_id"], job_id
    )


@router.get("/jobs/{job_id}/progress")
def progress(thread_id: str, job_id: str, db=Depends(store), config=Depends(settings)):
    from opinion_gateway.workspace_views import job_progress

    return job_progress(config.asset_root, db.get(thread_id)["event_id"], job_id)


@router.post("/jobs/{job_id}/analysis-tools/{tool}")
async def analytical_tool(
    thread_id: str,
    job_id: str,
    tool: str,
    parameters: dict,
    db=Depends(store),
    manager=Depends(runtime),
):
    return await manager.mcp.call(
        "submit_analysis_tool",
        {
            "event_id": db.get(thread_id)["event_id"],
            "source_job_id": job_id,
            "tool": tool,
            "parameters": parameters,
        },
    )


@router.get("/jobs")
def jobs(thread_id: str, db=Depends(store), config=Depends(settings)):
    return ApplicationService(config.asset_root).list_jobs(
        db.get(thread_id)["event_id"]
    )


@router.get("/jobs/{job_id}")
def job(thread_id: str, job_id: str, db=Depends(store), config=Depends(settings)):
    return ApplicationService(config.asset_root).job_status(
        db.get(thread_id)["event_id"], job_id
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
def result(thread_id: str, job_id: str, db=Depends(store), config=Depends(settings)):
    return ApplicationService(config.asset_root).read_job_artifact(
        db.get(thread_id)["event_id"], job_id
    )


@router.get("/artifacts/{run_id}/{artifact_id}")
def artifact(
    thread_id: str,
    run_id: str,
    artifact_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(store),
    config=Depends(settings),
):
    return ApplicationService(config.asset_root).read_domain_artifact(
        db.get(thread_id)["event_id"], run_id, artifact_id, offset, limit
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
    if format not in {"json", "markdown", "html", "zip", "pdf"}:
        raise ValueError("unsupported export format")
    event = db.get(thread_id)["event_id"]
    from opinion_gateway.application import ApplicationService

    try:
        await asyncio.to_thread(
            ApplicationService(config.asset_root).read_domain_artifact,
            event,
            run_id,
            artifact_id,
        )
        data = ArtifactStore(config.asset_root).read(event, run_id, artifact_id)
    except FileNotFoundError:
        raise HTTPException(404, "Report artifact not found") from None
    if format in {"pdf", "zip"} and "content" in data and "layout" in data:
        if data.get("pdf_base64"):
            pdf = base64.b64decode(data["pdf_base64"], validate=True)
        else:
            from opinion_core.reporting.render import render_report

            rendered = await asyncio.to_thread(
                render_report,
                data["content"],
                data["layout"],
                data.get("chart_data", {}),
            )
            pdf = base64.b64decode(rendered["pdf_base64"])
    elif format == "pdf":
        raise ValueError("artifact is not a report")
    else:
        pdf = None
    if format == "pdf":
        return Response(
            pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="report.pdf"'},
        )
    if format == "json":
        return Response(
            json.dumps(data, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="artifact.json"'},
        )
    if format == "zip":
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            if pdf:
                archive.writestr("report.pdf", pdf)
            for key, name in [("markdown", "report.md"), ("html", "report.html")]:
                if key in data:
                    archive.writestr(name, data[key])
            for name, value in data.get("images", {}).items():
                if not re.fullmatch(
                    r"(sentiment|stance|t-[a-f0-9]{64}|forecast-(stance|sentiment|topic|emotion|mass-stance|mass-sentiment)|scenario-(stance|variance))\.svg",
                    name,
                ):
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
