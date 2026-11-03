"""Stage handlers for the new architecture. Legacy PocketFlow is never imported."""

import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
import subprocess
import sys
from opinion_core.schemas.workflow import RunRequest
from opinion_core.labeling.glm_provider import GLMJsonProvider, GLMSchemaBuilder
from opinion_core.labeling.event_preparation import EventPreparation
from opinion_core.labeling.pipeline import WeakLabeler
from opinion_core.labeling.sampling import sample_for_schema
from opinion_core.labeling.system_one import SystemOneProvider
from opinion_core.analytics.toolbox import AnalysisToolbox, chart_svg
from opinion_core.analytics.observations import build_observations, summarize
from opinion_core.analytics.charts import build_charts
from opinion_core.evidence.providers import search as provider_search
from opinion_core.evidence.cards import web_cards, post_cards
from opinion_core.evidence.forum import (
    discuss,
    select_tools,
    calculation_card,
    brief_tool,
)
from opinion_core.evidence.media import analyze_media
from opinion_core.dynamics.engine import fit_assimilate, forecast
from opinion_core.dynamics.backtest import rolling_backtest
from opinion_core.scenarios.paired import compare_scenarios
from opinion_core.reporting.content import build_content
from opinion_core.reporting.agents import (
    organize_content,
    interpret_theory,
    arrange_report,
    recommend,
)
from opinion_core.reporting.render import render_report
from .connectors import (
    DecisionConnector,
    invoke_connector,
    WaitingForAuthentication,
    ConnectorUnavailable,
)
from .budget import CallLedger
from .label_workflow import DurableLabelBudget
from .dataset_repository import storage_id
from . import credentials


class MeteredGLM(GLMJsonProvider):
    def __init__(self, ledger, **kwargs):
        super().__init__(**kwargs)
        self.ledger, self.stage = ledger, "model"

    def request(self, instruction, payload):
        call = self.ledger.reserve(self.stage, self.version)
        try:
            result, usage = super().request(instruction, payload)
            self.ledger.settle(call, usage)
            return result, usage
        except Exception:
            self.ledger.settle(call, status="uncertain")
            raise


class IncompleteStage(RuntimeError):
    pass


class Execution:
    def __init__(self, service, request, check_cancel):
        self.service = service
        self.req = RunRequest.model_validate(request)
        self.check_cancel = check_cancel
        self.values, self.refs = {}, {}
        self.scope = hashlib.sha256(
            (self.req.event.event_id + "\0" + self.req.run_id).encode()
        ).hexdigest()
        self.ledger = CallLedger(
            service.repo.root, self.scope, self.req.max_total_calls, self.req.max_cost
        )
        self._model = None
        self._toolbox = None

    @property
    def model(self):
        if self._model is None:
            self._model = MeteredGLM(
                self.ledger,
                model=self.req.agent_model,
                api_key=credentials.get("GLM_API_KEY"),
            )
        return self._model

    @property
    def toolbox(self):
        if self._toolbox is None:
            self._toolbox = AnalysisToolbox(
                self.posts(),
                self.values["labels"]["annotations"],
                self.values["schema"]["schema"],
                self.req.observations,
                self.req.analysis.max_tool_calls,
                self.check_cancel,
            )
            for value in self.values.get("analysis", {}).get("results", []):
                self._toolbox.results[value["tool_id"]] = value
            for value in self.values.get("forum", {}).get("tool_results", []):
                self._toolbox.results[value["tool_id"]] = value
        return self._toolbox

    def search(self, query, **options):
        self.check_cancel()
        provider = self.req.event.search_provider
        if options.get("provider", provider) != provider:
            raise ValueError("search provider cannot change inside a run")
        reservation = self.ledger.reserve("search", provider)
        try:
            response = provider_search(
                query,
                provider=provider,
                api_key=credentials.get(credentials.KEYS[provider]),
                max_results=options.get("max_results", 5),
                timeout_seconds=20,
            )
            self.ledger.settle(
                reservation, status="failed" if response.get("error") else "returned"
            )
            self.service.assets.put(
                self.req.event.event_id, self.req.run_id, "search-response", response
            )
            return response
        except Exception:
            self.ledger.settle(reservation, status="uncertain")
            raise

    def collect(self):
        checkpoint = self.service.repo.path(
            storage_id(self.req.event.event_id),
            "crawl",
            storage_id(self.req.run_id) + ".json",
        )
        payload = json.dumps(
            {
                "event": self.req.event.model_dump(mode="json"),
                "crawl": self.req.crawl.model_dump(mode="json"),
                "_checkpoint_path": str(checkpoint),
            },
            ensure_ascii=False,
        )
        process = subprocess.Popen(
            [sys.executable, "-m", "crawler_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            # communicate(timeout) drains pipes in a background reader on Windows.
            while True:
                self.check_cancel()
                try:
                    output, _ = process.communicate(input=payload, timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    payload = None
            if process.returncode:
                raise RuntimeError("isolated crawler failed")
            result = json.loads(output)
            if result["status"] == "waiting_for_auth":
                raise WaitingForAuthentication("collection needs local session")
            if result["status"] == "connector_unavailable":
                raise ConnectorUnavailable("configure a platform connector")
            if not result.get("records"):
                raise IncompleteStage(
                    "collection returned no records; coverage is incomplete"
                )
            dataset = self.service.register_dataset(
                self.req.event.event_id, result.pop("records")
            )
            return {**result, **dataset}
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def posts(self):
        return self.service.repo.read(
            self.req.event.event_id, self.values["input"]["dataset_id"]
        )

    def execute(self, operation):
        self.check_cancel()
        req = self.req
        if operation == "collect":
            return self.collect()
        if operation == "load_dataset":
            return {
                "dataset_id": req.event.dataset_ref,
                "count": len(
                    self.service.repo.read(req.event.event_id, req.event.dataset_ref)
                ),
                "status": "completed",
            }
        if operation == "sample":
            posts = self.posts()
            candidates = [
                p
                for p in posts
                if p.get("published_at")
                and req.observations.start
                <= datetime.fromisoformat(p["published_at"])
                < req.observations.end
                and p["kind"] in req.observations.kinds
                and (
                    not req.observations.platforms
                    or p["platform"] in req.observations.platforms
                )
            ]
            return sample_for_schema(candidates, req.sampling) | {
                "input_count": len(posts),
                "excluded_from_schema_sampling": len(posts) - len(candidates),
                "sample_scope": "observation time/kind/platform filters",
            }
        if operation == "prepare_schema":
            self.model.stage = "schema"
            library = json.loads(
                (
                    Path(__file__).resolve().parents[1]
                    / "opinion_core/labeling/vocabularies/common-v1.json"
                ).read_text(encoding="utf-8")
            )
            event = req.event.model_copy(
                update={
                    "input_mode": "existing",
                    "dataset_ref": self.values["input"]["dataset_id"],
                }
            )
            result = EventPreparation(
                self.service.repo.root,
                search=self.search,
                builder=GLMSchemaBuilder(self.model),
                builder_version=GLMSchemaBuilder(self.model).version,
            ).prepare(
                event,
                library,
                max_total_calls=req.labels.max_schema_calls,
                sample=self.values["sample"],
            )
            if result["status"] != "frozen":
                raise IncompleteStage(result["error_type"])
            return result
        if operation == "label":
            if req.labels.provider == "connector":
                if not req.labels.connector:
                    raise ConnectorUnavailable("label connector ID required")
                provider = DecisionConnector(
                    req.labels.connector, req.media_mode, self.ledger
                )
            elif req.labels.provider in {"jev", "aliyun_decision"}:
                provider = SystemOneProvider(
                    req.labels.provider,
                    req.labels.model,
                    credentials.get(credentials.KEYS[req.labels.provider]),
                    "https://api.typesafe.ai/v1/systemone"
                    if req.labels.provider == "jev"
                    else credentials.get("ALIYUN_DECISION_ENDPOINT"),
                    self.ledger,
                )
            else:
                if req.media_mode != "text_only":
                    raise ValueError(
                        "image labeling requires an explicit multimodal connector"
                    )
                provider = MeteredGLM(
                    self.ledger,
                    model=req.labels.model,
                    api_key=credentials.get("GLM_API_KEY"),
                )
                provider.stage = "label"
            labeler = WeakLabeler(
                self.service.repo.root,
                provider,
                prompt_version="weak-json-v1",
                confidence_threshold=req.labels.confidence_threshold,
                batch_size=req.labels.batch_size,
                probability_margin=req.labels.probability_margin,
            )
            budget = DurableLabelBudget(
                self.service.repo.root / "label-budget.sqlite",
                self.scope,
                req.labels.max_calls,
            )
            return labeler.label(
                self.posts(),
                self.values["schema"]["schema"],
                budget=budget,
                check_cancel=self.check_cancel,
            )
        if operation == "observations":
            return build_observations(
                self.posts(),
                self.values["labels"]["annotations"],
                self.values["schema"]["schema"],
                req.observations,
                self.check_cancel,
            )
        if operation == "charts":
            charts = build_charts(self.values["observations"])
            for result in self.values.get("forum", {}).get(
                "tool_results", self.values.get("analysis", {}).get("results", [])
            ):
                charts[result["tool_id"]] = {
                    "svg": chart_svg(result),
                    "data": result["table"],
                    "bins": [],
                    "title": result["description"],
                    "chart": result["chart"],
                    "coverage": result["coverage"],
                }
            for name in ("stance", "sentiment"):
                steps = self.values.get("forecast", {}).get("steps", [])
                if steps:
                    result = {
                        "description": name + " 实验预测均值",
                        "table": [
                            {
                                "label": str(s["step"]),
                                "value": s["fields"][name]["mean"],
                                "lower": s["fields"][name]["mean_interval"][0],
                                "upper": s["fields"][name]["mean_interval"][1],
                            }
                            for s in steps
                        ],
                    }
                    charts["forecast-" + name] = {
                        "svg": chart_svg(result),
                        "data": result["table"],
                        "bins": [],
                        "title": result["description"],
                        "chart": {
                            "kind": "line",
                            "x": "label",
                            "y": "value",
                            "series": "series",
                        },
                    }
                    prediction = self.values["forecast"]
                    table = [
                        {
                            "start": (
                                datetime.fromisoformat(prediction["state_time"])
                                + timedelta(
                                    seconds=s["step"] * prediction["window_seconds"]
                                )
                            ).isoformat(),
                            "mass": s["fields"][name]["mass"],
                        }
                        for s in steps
                    ]
                    mass_result = {
                        "description": name + " 预测分布",
                        "table": [
                            {"label": r["start"], "series": str(i), "value": v}
                            for r in table
                            for i, v in enumerate(r["mass"])
                        ],
                    }
                    charts["forecast-mass-" + name] = {
                        "svg": chart_svg(mass_result),
                        "data": table,
                        "bins": prediction["bins"],
                        "title": mass_result["description"],
                        "chart": {"kind": "heatmap"},
                    }
            for category in ("topic", "emotion"):
                table = [
                    {"label": str(s["step"]), "series": label, "value": mass}
                    for s in self.values.get("forecast", {}).get("steps", [])
                    for label, mass in zip(
                        s["categories"][category]["labels"],
                        s["categories"][category]["mass"],
                    )
                ]
                if table:
                    result = {"description": category + " 解码预测质量", "table": table}
                    charts["forecast-" + category] = {
                        "svg": chart_svg(result),
                        "data": table,
                        "bins": [],
                        "title": result["description"],
                        "chart": {"kind": "heatmap"},
                    }
            simulated = self.values.get("scenarios", {})
            if simulated.get("branches"):
                trajectories = [("baseline", simulated["baseline"])] + [
                    (b["spec"]["scenario_id"], b["result"])
                    for b in simulated["branches"]
                ]
                for name, metric in [("stance", "mean"), ("variance", "variance")]:
                    result = {
                        "description": "情景立场"
                        + ("均值" if metric == "mean" else "方差"),
                        "table": [
                            {
                                "label": str(s["step"]),
                                "series": branch,
                                "value": s["fields"]["stance"][metric],
                            }
                            for branch, value in trajectories
                            for s in value["steps"]
                        ],
                    }
                    charts["scenario-" + name] = {
                        "svg": chart_svg(result),
                        "data": result["table"],
                        "bins": [],
                        "title": result["description"],
                        "chart": {"kind": "line"},
                    }
            return charts
        if operation == "evidence":
            return {
                "cards": web_cards(self.values["schema"]["evidence"], req.event.as_of)
                + post_cards(self.toolbox.rows)
            }
        if operation == "media":

            def invoke(payload):
                call = self.ledger.reserve("media", "media-default")
                try:
                    answer = invoke_connector("media", "default", payload)
                    self.ledger.settle(call, answer.get("usage"), answer.get("cost"))
                    return answer
                except Exception:
                    self.ledger.settle(call, status="uncertain")
                    raise

            return analyze_media(self.posts(), invoke)
        if operation == "analysis":
            self.model.stage = "analysis_planning"
            return select_tools(
                self.toolbox, self.model, req.analysis.instruction, req.analysis.tools
            )
        if operation == "forum":
            self.model.stage = "forum"
            context = summarize(self.values["observations"])
            context["window_total"] = len(context["windows"])
            context["windows"] = context["windows"][-30:]
            return discuss(
                context,
                self.values["evidence"]["cards"]
                + self.values.get("media", {}).get("evidence", []),
                self.model,
                lambda q: web_cards(self.search(q), req.event.as_of),
                req.forum_rounds,
                self.check_cancel,
                toolbox=self.toolbox,
                roles=req.analysis.forum_roles,
                instruction=req.analysis.instruction,
            )
        if operation == "assimilate":
            available = any(
                w["joint_n"]
                and datetime.fromisoformat(w["end"]) <= req.model.training_cutoff
                for w in self.values["observations"]["windows"]
            )
            if not available:
                return {
                    "status": "partial",
                    "reason": "insufficient_joint_observations",
                }
            return fit_assimilate(
                self.values["observations"], req.model, self.check_cancel
            )
        if operation == "forecast":
            if "ensemble" not in self.values["state"]:
                return {
                    "status": "partial",
                    "reason": "model_state_unavailable",
                    "steps": [],
                }
            return forecast(self.values["state"], check_cancel=self.check_cancel)
        if operation == "backtest":
            return rolling_backtest(
                self.values["observations"], req.model, self.check_cancel
            )
        if operation == "simulate":
            if "ensemble" not in self.values["state"]:
                return {
                    "status": "partial",
                    "reason": "model_state_unavailable",
                    "branches": [],
                }
            return compare_scenarios(
                self.values["state"], req.scenarios, self.check_cancel
            )
        if operation == "content":
            evidence = self.values.get("forum", {}).get(
                "evidence", self.values["evidence"]["cards"]
            )
            results = self.values.get("forum", {}).get(
                "tool_results", self.values.get("analysis", {}).get("results", [])
            )
            evidence = evidence + [calculation_card(v) for v in results]
            bundle = build_content(
                req.event.event_id,
                req.run_id,
                self.values["observations"],
                evidence,
                {key: ref["artifact_id"] for key, ref in self.refs.items()},
                self.values.get("forum"),
                self.values.get("forecast"),
                self.values.get("scenarios"),
                results,
                self.values.get("recommendations"),
            )
            self.model.stage = "content"
            all_results = {
                "analyses": [brief_tool(v) for v in results],
                "prediction": self.values.get("forecast"),
                "scenario_comparisons": self.values.get("recommendations"),
                "backtest": {
                    k: v
                    for k, v in self.values.get("backtest", {}).items()
                    if k != "scores"
                },
            }
            bundle, audit = organize_content(
                bundle, self.model, all_results, req.analysis.instruction
            )
            self.service.assets.put(
                req.event.event_id, req.run_id, "content-agent-audit", audit
            )
            return bundle
        if operation == "recommend":
            self.model.stage = "recommendations"
            return recommend(self.values["scenarios"], self.model)
        if operation == "theory":
            self.model.stage = "theory"
            return interpret_theory(
                self.values["content"], self.model, req.analysis.theory_ids
            )
        if operation == "structure":
            self.model.stage = "report_ui"
            return arrange_report(self.values["theory"]["content"], self.model)
        if operation == "render":
            return render_report(
                self.values["theory"]["content"],
                self.values["structure"],
                self.values["charts"],
            )
        raise ValueError("unknown operation")
