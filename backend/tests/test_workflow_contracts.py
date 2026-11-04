"""Offline engineering checks using synthetic records, not a Demo/gold benchmark."""

from datetime import datetime, timedelta, timezone
import json
import numpy as np
import pytest
from opinion_core.schemas.records import PostRecord, AnnotationRecord, FieldAnnotation
from opinion_core.schemas.event import EventSchema
from opinion_core.schemas.workflow import RunRequest, ModelSpec, ScenarioSpec
from opinion_core.orchestration import compile_plan
from opinion_core.analytics.toolbox import AnalysisToolbox, TOOLS
from opinion_core.analytics.observations import build_observations
from opinion_core.labeling.sampling import sample_for_schema
from opinion_core.labeling.pipeline import WeakLabeler, LabelBudget
from opinion_core.labeling.system_one import SystemOneProvider
from opinion_core.dynamics.engine import fit_assimilate, forecast
from opinion_core.evidence.forum import discuss
from opinion_gateway.budget import CallLedger


@pytest.fixture
def case():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    schema = EventSchema(
        event_id="fixture",
        schema_version="schema-fixture",
        as_of=start + timedelta(days=8),
        topics=[{"id": f"t{i}", "definition": f"Topic {i}"} for i in range(5)],
        publishers=[{"id": f"p{i}", "definition": f"Publisher {i}"} for i in range(5)],
        emotions=[{"id": f"e{i}", "definition": f"Emotion {i}"} for i in range(10)],
        targets=[{"id": "target", "definition": "公开事件信息"}],
        evidence_refs=["ev-fixture"],
    ).model_dump(mode="json")
    posts = []
    annotations = []
    for i in range(48):
        p = PostRecord(
            post_id=f"post-{i}",
            raw_id=str(i),
            platform="fixture",
            content=f"#北京# #上海# 城市暴雨 道路积水 信息公开 公众担心 救援进展 话题{i % 5}",
            published_at=start + timedelta(hours=i * 3),
            time_status="parsed",
            author_ref=f"a{i % 8}",
            parent_ref=str(i - i % 4) if i % 4 else None,
            kind="comment" if i % 4 else "post",
            read_count=i * 20,
            like_count=i,
            comment_count=i % 7,
            repost_count=i % 4,
            region=["北区", "南区"][i % 2],
        )
        values = {
            "topic": f"t{i % 5}",
            "publisher": f"p{i % 5}",
            "emotion": f"e{i % 10}",
            "sentiment": [-1.0, -0.5, 0.0, 0.5, 1.0][i % 5],
            "stance": ["support", "neutral", "oppose"][i % 3],
        }
        a = AnnotationRecord(
            post_id=p.post_id,
            schema_version="schema-fixture",
            model_version="synthetic-fixture",
            target_id="target",
            **{
                k: FieldAnnotation(status="accepted", value=v)
                for k, v in values.items()
            },
        )
        posts.append(p.model_dump(mode="json"))
        annotations.append(a.model_dump(mode="json"))
    spec = {
        "start": start.isoformat(),
        "end": (start + timedelta(days=6)).isoformat(),
        "window_seconds": 86400,
        "kinds": ["post", "comment"],
    }
    return posts, annotations, schema, spec


def request(case, objectives=None):
    _, _, _, spec = case
    return {
        "event": {
            "event_id": "fixture",
            "input_mode": "existing",
            "dataset_ref": "ds-fixture",
            "keywords": ["暴雨"],
            "as_of": spec["end"],
            "objectives": objectives or ["retrospective"],
        },
        "run_id": "run-fixture",
        "observations": spec,
    }


def test_selected_stages_and_scenario_dependencies(case):
    from opinion_core.schemas.workflow import LabelOptions

    defaults = LabelOptions.model_validate({"provider": "jev"})
    assert defaults.model == "jev-latest" and defaults.batch_size == 1
    raw = request(case, ["forecast"])
    raw["model"] = {"training_cutoff": raw["observations"]["end"]}
    plan = compile_plan(raw)
    names = [t.task_id for t in plan.tasks]
    assert "forum" not in names and "analysis" not in names
    assert names.index("sample") < names.index("schema") < names.index("labels")
    assert names[-4:] == ["content", "theory", "structure", "report"]
    raw["scenarios"] = [{"scenario_id": "s", "assumptions": ["synthetic assumption"]}]
    with pytest.raises(ValueError):
        RunRequest.model_validate(raw)
    raw["event"]["objectives"] = ["scenario"]
    assert "recommendations" in [t.task_id for t in compile_plan(raw).tasks]


def test_sampling_does_not_change_population(case):
    posts, annotations, schema, spec = case
    selected = sample_for_schema(
        posts, {"sample_size": 5, "seed": 7, "high_read_quantile": 0.75}
    )
    assert selected == sample_for_schema(
        posts, {"sample_size": 5, "seed": 7, "high_read_quantile": 0.75}
    )
    assert all(
        p["read_count"] >= selected["read_threshold"] for p in selected["sample"]
    )
    observations = build_observations(posts, annotations, schema, spec)
    assert sum(w["raw_n"] for w in observations["windows"]) == len(posts)
    assert selected["sample_count"] == 5


@pytest.mark.parametrize("name", list(TOOLS))
def test_retained_tools_produce_scoped_reproducible_tables(case, name):
    posts, annotations, schema, spec = case
    toolbox = AnalysisToolbox(posts, annotations, schema, spec)
    value = toolbox.execute(name)
    assert value["table"], name
    assert value["provenance"]["schema_version"] == schema["schema_version"]
    assert toolbox.execute(name) == value
    assert len(toolbox.results) == 1
    json.dumps(value, allow_nan=False)


def test_unknown_fields_and_tool_budget(case):
    posts, annotations, schema, spec = case
    for p in posts:
        p["region"] = None
        p["read_count"] = None
    toolbox = AnalysisToolbox(posts, annotations, schema, spec, max_calls=1)
    value = toolbox.execute("geographic_distribution_stats")
    assert value["status"] == "unavailable" and value["coverage"]["valid_n"] == 0
    with pytest.raises(ValueError):
        toolbox.execute("sentiment_time_series")
    with pytest.raises(ValueError):
        toolbox.execute("geographic_distribution_stats", {"command": "arbitrary"})


def test_native_system_one_schema_probabilities_and_margin(case, tmp_path, monkeypatch):
    posts, _, schema, _ = case
    ledger = CallLedger(tmp_path, "native", 2)
    captured = []

    def send(url, **kwargs):
        captured.append(kwargs["json"])
        answers = {}
        for name, q in kwargs["json"]["questions"].items():
            keys = list(q["criteria"])
            probabilities = {k: 0.0 for k in keys}
            probabilities[keys[0]] = 0.95
            probabilities[keys[1]] = 0.05
            answers[name] = {
                "type": "choice",
                "choice": keys[0],
                "confidence": 0.9,
                "probabilities": probabilities,
            }

        class Response:
            status_code = 200

            def json(self):
                return {
                    "answers": answers,
                    "usage": {"input_tokens": 25, "output_tokens": 0},
                }

        return Response()

    monkeypatch.setattr("opinion_core.labeling.system_one.requests.post", send)
    provider = SystemOneProvider(
        "jev",
        "jev-latest",
        "test-placeholder",
        "https://api.typesafe.ai/v1/systemone",
        ledger,
    )
    labeler = WeakLabeler(
        tmp_path, provider, prompt_version="test", batch_size=1, probability_margin=0.1
    )
    result = labeler.label(posts[:1], schema, budget=LabelBudget(1))
    assert len(captured) == 1 and len(captured[0]["questions"]) == 5
    assert result["annotations"][0]["topic"]["probability"] == 0.95
    assert result["annotations"][0]["sentiment"]["value"] == -1.0
    assert result["human_review_required"] is False
    assert ledger.summary()["calls"] == 1
    rejected = labeler._field(
        "topic",
        {"value": "t0", "confidence": 0.9, "probabilities": {"t0": 0.51, "t1": 0.49}},
        EventSchema.model_validate(schema),
    )
    assert (
        rejected.status == "abstained"
        and rejected.reason == "ambiguous_probability_margin"
    )


def test_openai_is_default_label_provider_with_legacy_choices_preserved():
    from opinion_core.schemas.workflow import LabelOptions

    default = LabelOptions()
    assert (default.provider, default.model, default.batch_size) == (
        "openai_decisions",
        "gpt-6-luna",
        1,
    )
    with pytest.raises(ValueError):
        LabelOptions(provider="glm", model="glm-4.5-air")
    assert LabelOptions(provider="jev").model == "jev-latest"
    with pytest.raises(ValueError):
        LabelOptions(provider="openai_decisions", model="unsupported")
    with pytest.raises(ValueError):
        LabelOptions(provider="openai_decisions", batch_size=2)


def test_worker_uses_default_openai_label_adapter(case, tmp_path, monkeypatch):
    from opinion_gateway.application import ApplicationService
    from opinion_gateway.runtime import Execution
    from opinion_core.labeling.openai_decisions import OpenAIDecisionsProvider

    monkeypatch.setenv("T2I_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-key")
    called = []

    def predict(self, posts, schema):
        called.append(self.model)
        return {
            "records": [
                {
                    "post_id": p.post_id,
                    "fields": {
                        k: {"refusal": True}
                        for k in (
                            "topic",
                            "publisher",
                            "emotion",
                            "sentiment",
                            "stance",
                        )
                    },
                }
                for p in posts
            ]
        }

    monkeypatch.setattr(OpenAIDecisionsProvider, "predict", predict)
    execution = Execution(ApplicationService(tmp_path), request(case), lambda: None)
    execution.values["schema"] = {"schema": case[2]}
    monkeypatch.setattr(execution, "posts", lambda: case[0][:1])
    result = execution.execute("label")
    assert called == ["gpt-6-luna"]
    assert result["annotations"][0]["topic"]["reason"] == "provider_refusal"


@pytest.mark.parametrize(
    "mode",
    ["valid", "refusal", "missing", "duplicate", "bad_probability", "http_error"],
)
def test_openai_decisions_native_protocol(case, tmp_path, monkeypatch, mode):
    from types import SimpleNamespace
    from opinion_core.labeling.openai_decisions import OpenAIDecisionsProvider

    posts, _, schema, _ = case
    ledger = CallLedger(tmp_path, mode, 1)
    captured = []

    def send(url, **kwargs):
        assert url == "https://api.openai.com/v1/decisions"
        assert kwargs["allow_redirects"] is False
        assert kwargs["headers"]["Authorization"] == "Bearer synthetic-key"
        body = kwargs["json"]
        captured.append(body)
        assert body["model"] == "gpt-6-luna"
        assert json.loads(body["input"][0]["content"][0]["text"])["post_id"] == posts[0]["post_id"]
        assert len(body["questions"]) == 5
        answers = []
        for question in body["questions"]:
            choices = question["choices"]
            assert choices[-1]["value"] == "unknown"
            assert all("description" in choice for choice in choices)
            answers.append(
                {
                    "type": "choice",
                    "name": question["name"],
                    "choice": choices[0]["value"],
                    "confidence": 0.9,
                    "probabilities": [
                        {
                            "value": c["value"],
                            "probability": 0.95 if i == 0 else 0.05 if i == 1 else 0,
                        }
                        for i, c in enumerate(choices)
                    ],
                }
            )
        if mode == "refusal":
            answers[0] = {"type": "refusal", "name": "topic"}
        if mode == "missing":
            answers.pop()
        if mode == "duplicate":
            answers[1] = answers[0]
        if mode == "bad_probability":
            answers[0]["probabilities"][0]["probability"] = float("nan")
        return SimpleNamespace(
            status_code=401 if mode == "http_error" else 200,
            json=lambda: {
                "model": "gpt-6-luna",
                "answers": answers,
                "usage": {"input_tokens": 25, "output_tokens": 0},
            },
        )

    monkeypatch.setattr("opinion_core.labeling.openai_decisions.requests.post", send)
    provider = OpenAIDecisionsProvider("gpt-6-luna", "synthetic-key", ledger)
    labeler = WeakLabeler(tmp_path, provider, prompt_version="test", batch_size=1)
    result = labeler.label(posts[:1], schema, budget=LabelBudget(1))
    assert len(captured) == 1 and ledger.summary()["calls"] == 1
    ann = result["annotations"][0]
    if mode in {"valid", "refusal"}:
        assert result["status"] == "completed"
        assert ann["sentiment"]["value"] == -1.0
        assert result["usage"]["input_tokens"] == 25
        assert (
            ann["topic"]["reason"] == "provider_refusal"
            if mode == "refusal"
            else ann["topic"]["probability"] == 0.95
        )
        assert ann["publisher"]["status"] == "accepted"
    else:
        assert result["status"] == "partial"
        assert ann["topic"]["status"] == "failed"


def test_latent_training_cutoff_decoding_and_paired_noop(case):
    posts, annotations, schema, spec = case
    observations = build_observations(posts, annotations, schema, spec)
    config = ModelSpec(
        training_cutoff=datetime.fromisoformat(observations["windows"][3]["end"]),
        particles=8,
        ensemble_size=4,
        horizon=2,
        latent_dimensions=3,
        calibrate=False,
    )
    state = fit_assimilate(observations, config)
    assert np.asarray(state["ensemble"]).shape == (4, 8, 3)
    assert state["codec"]["training_rows"] == 32
    changed = json.loads(json.dumps(observations))
    changed["windows"][5]["joint_vectors"] = [[999.0] * len(observations["features"])]
    assert fit_assimilate(changed, config) == state
    baseline = forecast(state)
    noop = forecast(
        state,
        ScenarioSpec(
            scenario_id="noop",
            mechanism="relaxation_change",
            parameter_value=config.relaxation,
            assumptions=["no change"],
        ),
    )
    assert baseline["steps"] == noop["steps"]
    for step in baseline["steps"]:
        for field in step["fields"].values():
            assert sum(field["mass"]) == pytest.approx(1)
            assert -1 <= field["mean"] <= 1
        for field in step["categories"].values():
            assert sum(field["mass"]) == pytest.approx(1)
            assert all(v >= 0 for v in field["mass"])


def test_forum_executes_typed_supplements_and_records_disagreement(case):
    toolbox = AnalysisToolbox(*case, max_calls=4)
    result = toolbox.execute("sentiment_distribution_stats")

    class Model:
        hosts = 0

        def request(self, prompt, payload):
            if "ForumHost" in prompt:
                self.hosts += 1
                if self.hosts == 1:
                    return {
                        "narrative": "需要补充时间证据",
                        "conflicts": ["关联不代表因果"],
                        "gaps": ["时间趋势缺口"],
                        "directives": [
                            {
                                "action": "supplement_data",
                                "tool": "sentiment_time_series",
                                "reason": "检查演变",
                            }
                        ],
                    }, {}
                return {
                    "narrative": "证据支持有限解释",
                    "gaps": [],
                    "directives": [{"action": "sufficient", "reason": "结论已限定"}],
                }, {}
            return {
                "claims": [
                    {"text": "情绪存在差异", "evidence_refs": [result["tool_id"]]}
                ]
            }, {}

    value = discuss(
        {}, [], Model(), lambda q: [], 2, toolbox=toolbox, roles=["data", "methodology"]
    )
    assert value["termination"] == "evidence_sufficient"
    assert value["roles"] == ["data", "methodology"]
    assert len(value["tool_results"]) == 2 and len(value["rounds"]) == 2
    assert value["rounds"][0]["actions"][0]["status"] == "executed"
    assert value["rounds"][0]["host"]["conflicts"]


def test_invalid_host_is_not_sufficient(case):
    class Model:
        def request(self, *args):
            return {}, {}

    value = discuss(
        {}, [], Model(), lambda q: [], 1, toolbox=AnalysisToolbox(*case), roles=["data"]
    )
    assert value["termination"] == "invalid_host_decision"
    assert value["unresolved"]


def test_worker_selected_pipeline_report_and_supplement_scope(
    case, tmp_path, monkeypatch
):
    """Integration of real job/asset/numeric/report services; external outputs are fixtures."""
    from opinion_gateway.application import ApplicationService
    from opinion_gateway.domain_worker import DomainWorker
    from opinion_gateway.runtime import Execution

    posts, annotations, schema, _ = case
    service = ApplicationService(tmp_path)
    dataset = service.register_dataset("fixture", posts)
    raw = request(case, ["retrospective", "forecast", "scenario"])
    raw["event"]["dataset_ref"] = dataset["dataset_id"]
    raw["model"] = {
        "training_cutoff": raw["observations"]["end"],
        "particles": 8,
        "ensemble_size": 4,
        "horizon": 2,
        "latent_dimensions": 3,
        "calibrate": False,
    }
    raw["scenarios"] = [
        {
            "scenario_id": "fixture-measure",
            "shift": 0.1,
            "assumptions": ["合成条件假设"],
        }
    ]
    raw["analysis"] = {
        "forum_roles": ["data"],
        "tools": ["sentiment_time_series", "topic_frequency_stats"],
    }
    raw["forum_rounds"] = 1

    class Model:
        stage = "fixture"

        def request(self, prompt, payload):
            if "ContentAgent" in prompt:
                return {"block_order": [b["block_id"] for b in payload["blocks"]]}, {}
            if "SocialScienceAgent" in prompt:
                return {
                    "interpretations": [
                        {
                            "theory_id": "framing",
                            "text": "不同话题强调了不同方面",
                            "evidence_refs": [
                                payload["content"]["evidence"][0]["evidence_id"]
                            ],
                            "limitations": "无法据此识别框架因果效应",
                        }
                    ]
                }, {}
            if "ReportUIAgent" in prompt:
                return payload["layout_template"], {}
            if "RecommendationAgent" in prompt:
                return {
                    "recommendations": [
                        {
                            "scenario_id": "fixture-measure",
                            "rationale": "比较模型中的方差变化",
                            "tradeoffs": "同时考虑资源需求",
                            "conditions": "仅在所列假设下成立",
                        }
                    ]
                }, {}
            if "ForumHost" in prompt:
                return {
                    "narrative": "有限解释",
                    "directives": [{"action": "sufficient", "reason": "结果已限定"}],
                }, {}
            return {
                "claims": [
                    {
                        "text": "存在不同话题",
                        "evidence_refs": [payload["calculations"][0]["tool_id"]],
                    }
                ]
            }, {}

    original = Execution.execute

    def execute(self, operation):
        if operation == "prepare_schema":
            return {
                "schema": schema,
                "evidence": {"provider": "fixture", "results": []},
            }
        if operation == "label":
            return {"status": "completed", "annotations": annotations}
        return original(self, operation)

    monkeypatch.setattr(Execution, "execute", execute)
    monkeypatch.setattr(Execution, "model", property(lambda self: Model()))
    job = service.submit_run(raw)
    finished = DomainWorker(tmp_path).run_once()
    assert finished.status == "completed", finished
    result = service.read_job_artifact("fixture", job["job_id"])
    assert {
        "sample",
        "analysis",
        "forum",
        "state",
        "forecast",
        "scenarios",
        "recommendations",
        "content",
        "theory",
        "structure",
        "report",
    } <= result["artifacts"].keys()
    report = result["artifacts"]["report"]
    payload = service.read_domain_artifact(
        "fixture", "run-fixture", report["artifact_id"]
    )
    assert payload["layout"]["sections"] and payload["charts"]
    assert "ensemble" not in json.dumps(payload)
    with pytest.raises((ValueError, FileNotFoundError)):
        service.read_domain_artifact("other", "run-fixture", report["artifact_id"])
    extra = service.submit_analysis_tool(
        "fixture", job["job_id"], "participant_trend_chart", {}
    )
    assert DomainWorker(tmp_path).run_once().status == "completed"
    extra_result = service.read_job_artifact("fixture", extra["job_id"])
    assert extra_result["artifacts"]["analysis-tool"]["run_id"] == "run-fixture"


def test_local_credentials_never_appear_in_status(tmp_path, monkeypatch):
    from opinion_gateway import credentials

    monkeypatch.setenv("T2I_PROJECT_ROOT", str(tmp_path))
    secret = "synthetic-credential-not-real"
    credentials.save("jev", secret)
    assert credentials.get("TYPESAFE_API_KEY") == secret
    assert secret not in json.dumps(credentials.status())
    assert "glm" not in {row["provider"] for row in credentials.status()}
    with pytest.raises(ValueError):
        credentials.save("glm", secret)
    with pytest.raises(ValueError):
        credentials.save("aliyun_decision", secret, "http://localhost/internal")


def test_schema_sampling_uses_declared_observation_window(case, tmp_path):
    from opinion_gateway.application import ApplicationService
    from opinion_gateway.runtime import Execution

    posts, _, _, _ = case
    future = {
        **posts[0],
        "post_id": "future",
        "raw_id": "future",
        "published_at": "2027-01-01T00:00:00Z",
        "read_count": 10**9,
    }
    service = ApplicationService(tmp_path)
    dataset = service.register_dataset("fixture", posts + [future])
    raw = request(case)
    raw["event"]["dataset_ref"] = dataset["dataset_id"]
    execution = Execution(service, raw, lambda: None)
    execution.values["input"] = dataset
    sampled = execution.execute("sample")
    assert "future" not in sampled["post_ids"]
    assert sampled["excluded_from_schema_sampling"] == 1


def test_pca_calibration_never_uses_post_cutoff_rows(case):
    posts, annotations, schema, spec = case
    observations = build_observations(posts, annotations, schema, spec)
    cutoff = datetime.fromisoformat(observations["windows"][3]["end"])
    config = ModelSpec(
        training_cutoff=cutoff,
        particles=8,
        ensemble_size=4,
        horizon=1,
        latent_dimensions=2,
        epsilon_candidates=[0.2, 0.6],
        relaxation_candidates=[0.5],
    )
    state = fit_assimilate(observations, config)
    assert state["calibration"]["status"] == "fitted"
    assert all(
        datetime.fromisoformat(f["validation_end"]) <= cutoff
        for f in state["calibration"]["folds"]
    )
    changed = json.loads(json.dumps(observations))
    changed["windows"][4]["joint_vectors"] = [[10000.0] * len(observations["features"])]
    assert fit_assimilate(changed, config) == state


def test_mcp_discovers_analysis_catalog_and_job_capability(tmp_path):
    import asyncio
    from fastmcp import Client
    from opinion_gateway.mcp_server import create_server

    async def inspect():
        async with Client(create_server(tmp_path)) as client:
            exposed = {tool.name for tool in await client.list_tools()}
            assert {
                "analysis_tool_catalog",
                "submit_analysis_tool",
                "submit_run",
                "preview_plan",
            } <= exposed
            catalog = await client.call_tool("analysis_tool_catalog", {})
            assert len(catalog.data) == 41
            assert len(exposed) == 19

    asyncio.run(inspect())
