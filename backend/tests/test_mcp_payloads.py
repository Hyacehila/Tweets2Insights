"""Exercise the real MCP serialization path used by the frontend gateway."""

import asyncio
from fastapi.encoders import jsonable_encoder
from opinion_gateway.application import ApplicationService
from opinion_gateway.mcp_server import create_server
from src.mcp.client import DomainToolClient


def test_mcp_preserves_job_and_nested_artifact_fields(tmp_path, monkeypatch):
    service = ApplicationService(tmp_path)
    job = service.jobs.submit("ui-check", "run-check", "analysis_run", {})
    claimed = service.jobs.claim("test-worker")
    payload = {
        "artifacts": {"charts": {"artifact_id": "a-test", "run_id": "run-check"}},
        "result": {"score": 0.5, "labels": ["first", "second"]},
    }
    service.jobs.finish(claimed, payload)
    client = DomainToolClient(None)
    monkeypatch.setattr(client, "configuration", lambda: create_server(tmp_path))

    async def inspect():
        jobs = await client.call("list_jobs", {"event_id": "ui-check"})
        assert jsonable_encoder(jobs) == [
            service.jobs.get(job.job_id).model_dump(mode="json")
        ]
        result = await client.call(
            "read_job_artifact", {"event_id": "ui-check", "job_id": job.job_id}
        )
        assert jsonable_encoder(result) == payload
        catalog = await client.call("analysis_tool_catalog", {})
        assert len(catalog) == 41
        assert isinstance(catalog[0]["name"], str)

    asyncio.run(inspect())
