"""Multimodal protocol and fallback checks; external model responses are fixtures."""

import base64
import io
from types import SimpleNamespace

import pytest
from opinion_core.labeling.pipeline import LabelBudget, WeakLabeler
from opinion_core.schemas.event import EventSchema
from opinion_core.schemas.records import PostRecord
from opinion_core.schemas.workflow import LabelOptions, RunRequest
from opinion_gateway.budget import CallLedger
from PIL import Image


def picture(size=(32, 60), color="red"):
    stream = io.BytesIO()
    Image.new("RGB", size, color).save(stream, "PNG")
    return stream.getvalue()


def uri(color="red"):
    return "data:image/png;base64," + base64.b64encode(picture(color=color)).decode()


@pytest.fixture
def schema():
    return EventSchema(
        event_id="images",
        schema_version="v1",
        as_of="2026-01-03T00:00:00Z",
        topics=[{"id": f"t{i}", "definition": str(i)} for i in range(5)],
        publishers=[{"id": f"p{i}", "definition": str(i)} for i in range(5)],
        emotions=[{"id": f"e{i}", "definition": str(i)} for i in range(10)],
        targets=[{"id": "target", "definition": "支持公开信息"}],
        evidence_refs=["e1"],
    )


def post(**kwargs):
    return PostRecord(
        post_id="one", platform="fixture", raw_id="one", content="道路积水", **kwargs
    )


def request(provider="openai_decisions"):
    return {
        "event": {
            "event_id": "images",
            "input_mode": "existing",
            "dataset_ref": "ds-1",
            "keywords": ["暴雨"],
            "as_of": "2026-01-03T00:00:00Z",
        },
        "run_id": "r1",
        "labels": {"provider": provider},
        "observations": {
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-03T00:00:00Z",
        },
    }


def capture_decisions(monkeypatch):
    calls = []

    def send(url, **kwargs):
        calls.append(kwargs)
        payload = kwargs["json"]
        answers = {}
        native = isinstance(payload["questions"], list)
        questions = (
            payload["questions"]
            if native
            else [dict(q, name=k) for k, q in payload["questions"].items()]
        )
        for question in questions:
            keys = (
                [v["value"] for v in question["choices"]]
                if native
                else list(question["criteria"])
            )
            probabilities = {k: float(i == 0) for i, k in enumerate(keys)}
            answers[question["name"]] = {
                "name": question["name"],
                "type": "choice",
                "choice": keys[0],
                "confidence": 0.99,
                "probabilities": [
                    {"value": k, "probability": v} for k, v in probabilities.items()
                ]
                if native
                else probabilities,
            }
        return SimpleNamespace(
            status_code=200,
            json=lambda: {
                "answers": list(answers.values()) if native else answers,
                "usage": {},
            },
        )

    monkeypatch.setattr("requests.post", send)
    return calls


@pytest.mark.parametrize(
    "provider,model,images",
    [
        ("openai_decisions", "gpt-6-luna", True),
        ("jev", "jev-latest", True),
        ("jev", "jev-1.14.0", True),
        ("jev", "jev-1.13.0", True),
        ("jev", "jev-1.12.0", False),
        ("jev", "unknown", False),
        ("aliyun_decision", "decision-model-preview", False),
    ],
)
def test_model_capability_controls_input(provider, model, images):
    from opinion_core.labeling.media import MediaPolicy

    policy = MediaPolicy(provider, model, "text_image", 2)
    assert policy.supports_images is images
    assert policy.effective_mode == ("text_image" if images else "text_only")
    summary = policy.summary([post(media_refs=["a", "b", "c"]).model_dump()])
    assert summary["selected_images"] == (2 if images else 0)
    assert summary["ignored_images"] == (1 if images else 3)
    if not images:
        assert summary["notices"] == ["model_text_only"]
        assert policy.summary([])["notices"] == ["model_text_only"]


def test_default_joint_mode_and_limits_do_not_require_media_connector():
    from opinion_core.orchestration import compile_plan

    req = RunRequest.model_validate(request())
    assert req.media_mode == "text_image"
    assert req.labels.max_images_per_post == 3
    assert "media" not in [task.operation for task in compile_plan(req).tasks]
    for limit in (0, 10, 1.5):
        with pytest.raises(ValueError):
            LabelOptions(max_images_per_post=limit)
    fallback = request("aliyun_decision") | {"media_mode": "text_image"}
    assert "media" not in [task.operation for task in compile_plan(fallback).tasks]


@pytest.mark.parametrize("name", ["openai_decisions", "jev", "aliyun_decision"])
def test_native_joint_payload_limit_and_text_fallback(
    name, schema, tmp_path, monkeypatch
):
    from opinion_gateway.label_providers import make_label_provider

    monkeypatch.setattr(
        "opinion_gateway.credentials.get",
        lambda key: (
            "https://workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/systemone"
            if key.endswith("ENDPOINT")
            else "synthetic"
        ),
    )
    calls = capture_decisions(monkeypatch)
    provider = make_label_provider(
        LabelOptions(provider=name, max_images_per_post=2),
        CallLedger(tmp_path, name, 5),
        "text_image",
    )
    refs = [uri(), uri("blue"), "this-third-image-must-not-be-read"]
    record = post(media_refs=refs)
    result = WeakLabeler(tmp_path, provider, prompt_version="test", batch_size=1).label(
        [record], schema, budget=LabelBudget(1)
    )
    assert result["status"] == "completed"
    assert record.media_refs == refs
    body = calls[0]["json"]
    if name == "openai_decisions":
        content = body["input"][0]["content"]
        assert len([c for c in content if c["type"] == "input_image"]) == 2
        assert "道路积水" in content[0]["text"]
        assert "media_refs" not in content[0]["text"]
    elif name == "jev":
        assert len(body["assets"]) == 2
        assert body["state"]["images"] == list(body["assets"])
        assert calls[0]["headers"]["TypeSafe-Danger-Zone-Images"] == "true"
        for asset in body["assets"].values():
            assert asset["format"] == "jpg"
            assert (
                min(Image.open(io.BytesIO(base64.b64decode(asset["data_base64"]))).size)
                >= 280
            )
    else:
        assert "assets" not in body and "media_refs" not in body["state"]
        assert body["state"]["content"] == "道路积水"
        assert "TypeSafe-Danger-Zone-Images" not in calls[0]["headers"]


def test_text_only_does_not_load_images_and_cache_tracks_mode_and_limit(
    schema, tmp_path, monkeypatch
):
    from opinion_core.labeling.openai_decisions import OpenAIDecisionsProvider

    calls = capture_decisions(monkeypatch)
    ledger = CallLedger(tmp_path, "cache", 5)
    providers = [
        OpenAIDecisionsProvider(
            "gpt-6-luna", "test", ledger, media_mode=mode, max_images_per_post=limit
        )
        for mode, limit in [("text_only", 2), ("text_image", 1), ("text_image", 2)]
    ]
    assert len({p.version for p in providers}) == 3
    p = post(media_refs=["file:///must-not-read"])
    result = WeakLabeler(
        tmp_path, providers[0], prompt_version="test", batch_size=1
    ).label([p], schema, budget=LabelBudget(1))
    assert result["status"] == "completed" and len(calls) == 1
    assert "must-not-read" not in str(calls)


def test_media_assets_are_event_scoped_and_images_normalized(tmp_path):
    from opinion_gateway.media_assets import MediaAssets

    assets = MediaAssets(tmp_path, "images")
    ref = assets.save(picture())
    assert ref.startswith("dataset-image:")
    assert assets.save(picture()) == ref
    data = assets.load(ref)
    assert Image.open(io.BytesIO(data)).size == (280, 280)
    with pytest.raises((ValueError, FileNotFoundError)):
        MediaAssets(tmp_path, "other").load(ref)
    with pytest.raises(ValueError):
        assets.load("dataset-image:../../secrets")


@pytest.mark.parametrize(
    "ref",
    [
        "file:///C:/secret.png",
        "C:/secret.png",
        "http://127.0.0.1/a",
        "http://169.254.169.254/a",
        "http://[::1]/a",
        "data:image/png;base64,broken",
    ],
)
def test_image_loader_rejects_local_paths_and_invalid_images(ref):
    from opinion_core.labeling.media import load_image

    with pytest.raises(ValueError):
        load_image(ref)


def test_execution_records_fallback_even_without_images(tmp_path):
    from opinion_gateway.application import ApplicationService
    from opinion_gateway.runtime import Execution

    service = ApplicationService(tmp_path)
    ds = service.register_dataset("images", [post().model_dump(mode="json")])
    raw = request("aliyun_decision")
    raw["event"]["dataset_ref"] = ds["dataset_id"]
    result = Execution(service, raw, lambda: None).execute("load_dataset")
    assert result["media_input"]["effective_mode"] == "text_only"
    assert result["media_input"]["notices"] == ["model_text_only"]


def test_image_upload_api(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.gateway.dependencies import settings, store
    from src.gateway.routers.datasets import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[store] = lambda: SimpleNamespace(
        get=lambda _: {"event_id": "images"}
    )
    app.dependency_overrides[settings] = lambda: SimpleNamespace(asset_root=tmp_path)
    client = TestClient(app)
    reply = client.post(
        "/api/threads/local/datasets/images",
        content=picture(),
        headers={"Content-Type": "image/png"},
    )
    assert reply.status_code == 200
    assert reply.json()["media_ref"].startswith("dataset-image:")
    invalid = client.post(
        "/api/threads/local/datasets/images",
        content=b"not an image",
        headers={"Content-Type": "image/png"},
    )
    assert invalid.status_code == 400


def test_bad_image_and_empty_text_do_not_spend_model_calls(
    schema, tmp_path, monkeypatch
):
    from opinion_core.labeling.openai_decisions import OpenAIDecisionsProvider

    calls = capture_decisions(monkeypatch)
    ledger = CallLedger(tmp_path, "bad", 5)
    provider = OpenAIDecisionsProvider("gpt-6-luna", "test", ledger)
    records = [
        post(media_refs=["file:///bad"]),
        post().model_copy(update={"post_id": "empty", "content": ""}),
    ]
    budget = LabelBudget(5)
    result = WeakLabeler(tmp_path, provider, prompt_version="test", batch_size=1).label(
        records, schema, budget=budget
    )
    assert result["status"] == "partial"
    assert not calls and not ledger.summary()["calls"]
    assert result["calls"] == budget.calls == 0
    assert result["media_input"]["failed_image_posts"] == 1
    assert result["media_input"]["empty_input_posts"] == 1


def test_cache_uses_actual_image_content_not_only_url(schema, tmp_path, monkeypatch):
    from opinion_core.labeling.openai_decisions import OpenAIDecisionsProvider

    calls = capture_decisions(monkeypatch)
    data = [picture()]
    loaded = []

    def image_loader(ref):
        loaded.append(ref)
        return data[0]

    provider = OpenAIDecisionsProvider(
        "gpt-6-luna",
        "test",
        CallLedger(tmp_path, "changed", 5),
        image_loader=image_loader,
    )
    labeler = WeakLabeler(tmp_path, provider, prompt_version="test", batch_size=1)
    records = [post(media_refs=["https://example.com/image.jpg"])]
    assert labeler.label(records, schema, budget=LabelBudget(1))["calls"] == 1
    assert labeler.label(records, schema, budget=LabelBudget(0))["cache_hits"] == 1
    data[0] = picture(color="blue")
    result = labeler.label(records, schema, budget=LabelBudget(1))
    assert result["calls"] == 1 and result["cache_hits"] == 0
    assert len(calls) == 2 and len(loaded) == 3


def test_upload_retains_original_image_bytes(tmp_path):
    from opinion_gateway.dataset_repository import storage_id
    from opinion_gateway.media_assets import MediaAssets

    original = picture(size=(60, 90))
    ref = MediaAssets(tmp_path, "images").save(original)
    stored = (
        tmp_path
        / storage_id("images")
        / "datasets"
        / "images"
        / (ref.split(":")[1] + ".image")
    )
    assert stored.read_bytes() == original


@pytest.mark.parametrize("name", ["openai_decisions", "jev", "aliyun_decision"])
def test_multimodal_worker_to_report(name, schema, tmp_path, monkeypatch):
    from opinion_gateway.application import ApplicationService
    from opinion_gateway.domain_worker import DomainWorker
    from opinion_gateway.media_assets import MediaAssets
    from opinion_gateway.runtime import Execution

    service = ApplicationService(tmp_path)
    ref = MediaAssets(tmp_path, "images").save(picture())
    record = post(
        media_refs=[ref, "ignored-image"],
        published_at="2026-01-01T12:00:00Z",
        time_status="parsed",
    )
    ds = service.register_dataset("images", [record.model_dump(mode="json")])
    raw = request(name)
    raw["event"]["dataset_ref"] = ds["dataset_id"]
    raw["labels"]["max_images_per_post"] = 1
    raw["analysis"] = {"tools": ["topic_frequency_stats"]}
    raw["forum_rounds"] = 0
    monkeypatch.setattr(
        "opinion_gateway.credentials.get",
        lambda key: (
            "https://workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/systemone"
            if key.endswith("ENDPOINT")
            else "synthetic"
        ),
    )
    calls = capture_decisions(monkeypatch)
    original = Execution.execute

    def execute(self, operation):
        if operation == "prepare_schema":
            return {
                "schema": schema.model_dump(mode="json"),
                "evidence": {"provider": "fixture", "results": []},
            }
        return original(self, operation)

    class Model:
        stage = "fixture"

        def request(self, prompt, payload):
            if "ContentAgent" in prompt and "chapter_plan" in payload:
                return {"chapters": [{"chapter_id": c["chapter_id"], "focus": c["title"], "chart_ids": [], "evidence_refs": [payload["evidence_catalog"][0]["evidence_id"]]} for c in payload["chapter_plan"]]}, {}
            if "ContentAgent" in prompt:
                return {"title": "Fixture report", "paragraphs": [{"title": payload["chapter"]["title"], "text": "根据现有事件资料整理章节内容与可核对的研究发现。", "kind": "interpretation", "evidence_refs": [payload["evidence"][0]["evidence_id"]]}]}, {}
            if "SocialScienceAgent" in prompt:
                return {"interpretations": []}, {}
            if "ReportUIAgent" in prompt:
                return payload["layout_template"], {}
            raise AssertionError("unexpected agent operation")

    monkeypatch.setattr(Execution, "execute", execute)
    monkeypatch.setattr(Execution, "model", property(lambda self: Model()))
    job = service.submit_run(raw)
    finished = DomainWorker(tmp_path).run_once()
    assert finished.status in {"completed", "partial"}, finished
    result = service.read_job_artifact("images", job["job_id"])
    assert "labels" not in result.get("partial_stages", [])
    assert "report" in result["artifacts"]
    assert len(calls) == 1
    assert result["media_input"]["selected_images"] == (
        0 if name == "aliyun_decision" else 1
    )
    assert service.repo.read("images", ds["dataset_id"])[0]["media_refs"] == [
        ref,
        "ignored-image",
    ]
