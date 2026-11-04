"""Application boundary used by CLI, UI and MCP; one plan and one domain scheduler."""

import json
import sqlite3
from opinion_core.orchestration import compile_plan
from opinion_core.schemas.workflow import RunRequest
from .assets import ArtifactStore
from .mcp_server import DomainService
from .dataset_repository import storage_id


class ApplicationService(DomainService):
    def __init__(self, root):
        super().__init__(root)
        self.assets = ArtifactStore(root)
        self.runs_path = self.repo.root / "runs.sqlite"
        self.repo.root.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.runs_path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS runs (scope TEXT PRIMARY KEY, payload TEXT, job_id TEXT)"
            )

    def preview_plan(self, request: dict) -> dict:
        """Compile and validate a plan without model calls, collection or job submission."""
        return compile_plan(request).model_dump(mode="json")

    def submit_run(self, request: dict) -> dict:
        """Submit the complete event workflow and return immediately; no arbitrary paths or commands."""
        from .agent_models import resolve_request

        req = resolve_request(RunRequest.model_validate(request))
        if not req.event.requires_collection:
            self.repo.read(req.event.event_id, req.event.dataset_ref)
        canonical = json.dumps(
            req.model_dump(mode="json"), ensure_ascii=False, sort_keys=True
        )
        scope = storage_id(req.event.event_id) + ":" + storage_id(req.run_id)
        with sqlite3.connect(self.runs_path, timeout=30) as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT payload,job_id FROM runs WHERE scope=?", (scope,)
            ).fetchone()
            if old and old[0] != canonical:
                raise ValueError("run configuration frozen; use a new run_id")
            if old:
                return self.job_status(req.event.event_id, old[1])
            plan = compile_plan(req)
            ref = self.assets.put(
                req.event.event_id, req.run_id, "request", req.model_dump(mode="json")
            )
            job = self.jobs.submit(
                req.event.event_id,
                req.run_id,
                "analysis_run",
                {
                    "request_ref": ref["artifact_id"],
                    "code_version": self.code_version,
                    "plan": plan.model_dump(mode="json"),
                },
            )
            db.execute(
                "INSERT INTO runs VALUES (?,?,?)", (scope, canonical, job.job_id)
            )
            return job.model_dump(mode="json")

    def list_datasets(self, event_id: str) -> list[dict]:
        """List registered datasets in the selected event only."""
        directory = self.repo.path(storage_id(event_id), "datasets")
        return [
            {"dataset_id": p.stem, "count": len(self.repo.read(event_id, p.stem))}
            for p in sorted(directory.glob("ds-*.json"))
        ]

    def list_artifacts(self, event_id: str, run_id: str) -> list[dict]:
        """List immutable artifact references owned by this event/run."""
        return self.assets.list(event_id, run_id)

    def analysis_tool_catalog(self) -> list[dict]:
        """List allowlisted Stage-2 analyses and typed arguments; no execution."""
        from opinion_core.analytics.toolbox import catalog

        return catalog()

    def submit_analysis_tool(
        self, event_id: str, source_job_id: str, tool: str, parameters: dict
    ) -> dict:
        """Queue one additional analysis of a completed run's frozen labels and input."""
        from opinion_core.analytics.toolbox import TOOLS, ToolParameters

        job = self.job_status(event_id, source_job_id)
        if job["kind"] != "analysis_run" or job["status"] not in {
            "completed",
            "partial",
        }:
            raise ValueError("select a completed or partial domain run")
        source = self.jobs.result(source_job_id)
        required = {"input", "schema", "labels"}
        if not required <= source.get("artifacts", {}).keys():
            raise ValueError("source run has no reusable annotation artifacts")
        if tool not in TOOLS:
            raise ValueError("unknown analytical tool")
        params = ToolParameters.model_validate(parameters).model_dump(mode="json")
        original = self.jobs.parameters(source_job_id)
        return self.jobs.submit(
            event_id,
            job["run_id"],
            "analysis_tool",
            {
                "tool": tool,
                "parameters": params,
                "source_artifacts": source["artifacts"],
                "request_ref": original["request_ref"],
                "code_version": self.code_version,
            },
        ).model_dump(mode="json")

    def read_domain_artifact(
        self,
        event_id: str,
        run_id: str,
        artifact_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> dict:
        """Read bounded artifact data; numerical particle arrays stay outside Agent context."""
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError("invalid pagination")
        references = self.assets.list(event_id, run_id)
        reference = next(
            (r for r in references if r["artifact_id"] == artifact_id), None
        )
        if reference and reference["kind"] == "report":
            published = False
            for job in self.jobs.list_jobs(event_id, 200):
                if (
                    job.kind == "analysis_run"
                    and job.run_id == run_id
                    and job.status in {"completed", "partial"}
                ):
                    result = self.jobs.result(job.job_id)
                    if (
                        result.get("artifacts", {}).get("report", {}).get("artifact_id")
                        == artifact_id
                    ):
                        published = True
                        break
            if not published:
                raise ValueError("report not published by a completed job transaction")
        data = self.assets.read(event_id, run_id, artifact_id)
        if reference and reference["kind"] == "report":
            return {
                "artifact_id": artifact_id,
                "markdown_excerpt": data.get("markdown", "")[:8000],
                "content": data.get("content"),
                "layout": data.get("layout"),
                "charts": {
                    name: {k: v for k, v in chart.items() if k != "svg"}
                    | {
                        "data": chart.get("data", [])[:60],
                        "data_total": len(chart.get("data", [])),
                    }
                    for name, chart in data.get("chart_data", {}).items()
                },
                "available_exports": ["markdown", "html", "images", "json"],
                "source_versions": data.get("content", {}).get("source_versions", {}),
            }
        if reference and reference["kind"] == "charts":
            return {
                name: {
                    "bins": chart.get("bins", []),
                    "title": chart.get("title", name),
                    "chart": chart.get("chart"),
                    "coverage": chart.get("coverage"),
                    "data_total": len(chart["data"]),
                    "data": chart["data"][offset : offset + limit],
                }
                for name, chart in data.items()
            }
        if isinstance(data, list):
            return {"items": data[offset : offset + limit], "total": len(data)}
        result = dict(data)
        result.pop("ensemble", None)
        for key in (
            "annotations",
            "windows",
            "evidence",
            "cards",
            "records",
            "scores",
            "steps",
            "table",
            "results",
            "tool_results",
        ):
            if isinstance(result.get(key), list):
                values = result[key]
                result[key + "_total"] = len(values)
                result[key] = [
                    {
                        k: v
                        for k, v in x.items()
                        if k not in {"joint_vectors", "joint_post_ids"}
                    }
                    if isinstance(x, dict)
                    else x
                    for x in values[offset : offset + limit]
                ]
                for item in result[key]:
                    if isinstance(item, dict) and isinstance(item.get("table"), list):
                        item["table_total"] = len(item["table"])
                        item["table"] = item["table"][:30]
        if isinstance(result.get("evidence"), dict):
            result["evidence"] = {
                "provider": result["evidence"].get("provider"),
                "results": result["evidence"].get("results", [])[
                    offset : offset + limit
                ],
            }
        return result

    def retry_job(self, event_id: str, job_id: str) -> dict:
        self.job_status(event_id, job_id)
        return self.jobs.retry(job_id).model_dump(mode="json")

    def resume_job(self, event_id: str, job_id: str) -> dict:
        """After the operator supplies a local login session, resume the same frozen request."""
        self.job_status(event_id, job_id)
        return self.jobs.resume(job_id).model_dump(mode="json")
