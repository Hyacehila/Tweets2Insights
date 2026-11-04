import json
from types import SimpleNamespace
import pytest
from opinion_core.schemas.agent_model import AgentModelConfig
from opinion_gateway.agent_models import (
    active_config,
    api_key_for,
    save_config,
    presets,
)
from opinion_core.labeling.openai_provider import OpenAIJsonProvider


def test_agent_settings_api_only_saves_after_successful_check(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.gateway.routers.system import router
    from src.gateway.dependencies import settings

    monkeypatch.setenv("T2I_PROJECT_ROOT", str(tmp_path))
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[settings] = lambda: SimpleNamespace(
        frontend_origin="http://localhost:3000", agent_model_config=AgentModelConfig()
    )
    client = TestClient(app)
    config = AgentModelConfig(
        provider="openai_compatible", base_url="https://vendor.test/v1", model="model"
    )
    payload = {"config": config.model_dump(), "api_key": "synthetic-secret"}
    monkeypatch.setattr(
        OpenAIJsonProvider, "request", lambda *args: ({"wrong": True}, {})
    )
    assert client.post("/api/agent-model", json=payload).status_code == 400
    assert not (tmp_path / ".provider-secrets.json").exists()
    monkeypatch.setattr(
        OpenAIJsonProvider,
        "request",
        lambda *args: ({"ok": True, "sum": 5, "labels": ["evidence"]}, {}),
    )
    assert (
        client.post(
            "/api/agent-model", json=payload, headers={"Origin": "https://other.test"}
        ).status_code
        == 403
    )
    assert client.post("/api/agent-model", json=payload).status_code == 200
    public = client.get("/api/agent-model").json()
    assert public["config"] == config.model_dump()
    assert public["configured"] is True
    assert "synthetic-secret" not in json.dumps(public)
    assert (
        client.post(
            "/api/agent-model", json={"config": config.model_dump()}
        ).status_code
        == 200
    )


def test_leader_freezes_selected_model_and_ignores_generated_model_overrides(
    tmp_path, monkeypatch
):
    import asyncio
    from src.agents.lead_agent.factory import make_lead_agent

    monkeypatch.setenv("T2I_PROJECT_ROOT", str(tmp_path))
    selected = AgentModelConfig(
        provider="openai_compatible",
        model="selected-model",
        base_url="https://vendor.test/v1",
    )
    save_config(selected, "synthetic-secret")
    raw = {
        "event": {
            "event_id": "fixture",
            "input_mode": "existing",
            "dataset_ref": "ds",
            "keywords": ["rain"],
            "as_of": "2026-01-02T00:00:00Z",
            "objectives": ["retrospective"],
        },
        "run_id": "one",
        "observations": {
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-02T00:00:00Z",
            "window_seconds": 86400,
        },
    }

    class Models:
        async def request(self, *args):
            return {
                "request": {
                    **raw,
                    "agent_model": "hallucinated-model",
                    "agent_config": AgentModelConfig(
                        base_url="https://wrong.test/v1"
                    ).model_dump(),
                }
            }, {}

    class Tools:
        async def plan(self, state, request):
            assert request["agent_config"] == selected.model_dump()
            assert request["agent_model"] == "selected-model"
            return {}

    settings = SimpleNamespace(
        max_agent_calls=1,
        max_subagents=0,
        context_messages=12,
        agent_model_config=selected,
    )
    skills = SimpleNamespace(enabled=[], context=lambda x: "")
    graph = make_lead_agent(settings, Models(), Tools(), skills)
    for request in (raw, None):
        result = asyncio.run(
            graph.ainvoke(
                {
                    "event_id": "fixture",
                    "datasets": [{"dataset_id": "ds"}],
                    "message": "Analyze",
                    "run_request": request,
                    "execute": False,
                }
            )
        )
        assert result["run_request"]["agent_config"] == selected.model_dump()


def test_model_json_protocol_and_usage(monkeypatch):
    config = AgentModelConfig(**presets()[0]["config"])
    provider = OpenAIJsonProvider(config, "test-key")

    def post(url, **kwargs):
        assert url == config.base_url + "/chat/completions"
        assert kwargs["headers"]["Authorization"] == "Bearer test-key"
        assert kwargs["allow_redirects"] is False
        assert kwargs["json"]["response_format"] == {"type": "json_object"}
        assert kwargs["json"]["enable_thinking"] is False
        return SimpleNamespace(
            status_code=200,
            json=lambda: {
                "choices": [
                    {"finish_reason": "stop", "message": {"content": '{"ok":true}'}}
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 8},
            },
        )

    monkeypatch.setattr(provider.client, "post", post)
    assert provider.request("Return JSON", {}) == (
        {"ok": True},
        {"input_tokens": 12, "output_tokens": 8},
    )


def test_model_configuration_is_redacted_and_keys_are_endpoint_bound(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("T2I_PROJECT_ROOT", str(tmp_path))
    config = AgentModelConfig(base_url="https://vendor.test/v1", model="research-model")
    save_config(config, "synthetic-secret")
    assert active_config() == config
    assert api_key_for(config) == "synthetic-secret"
    assert "synthetic-secret" not in config.model_dump_json()
    other = config.model_copy(update={"base_url": "https://other.test/v1"})
    assert not api_key_for(other)
    with pytest.raises(ValueError):
        save_config(other, "")
    assert (
        "synthetic-secret"
        in json.loads((tmp_path / ".provider-secrets.json").read_text())[
            "AGENT_KEYS"
        ].values()
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://key:secret@example.com/v1",
        "https://example.com/v1?key=secret",
        "http://example.com/v1",
        "file:///tmp/model",
    ],
)
def test_model_endpoint_validation(url):
    with pytest.raises(ValueError):
        AgentModelConfig(base_url=url, model="model")


@pytest.mark.parametrize(
    "content,finish", [("[]", "stop"), ("not json", "stop"), ('{"ok":true}', "length")]
)
def test_invalid_or_truncated_model_output_is_rejected(monkeypatch, content, finish):
    provider = OpenAIJsonProvider(AgentModelConfig(), "test-key")
    monkeypatch.setattr(
        provider.client,
        "post",
        lambda *a, **kw: SimpleNamespace(
            status_code=200,
            json=lambda: {
                "choices": [{"finish_reason": finish, "message": {"content": content}}]
            },
        ),
    )
    with pytest.raises(ValueError):
        provider.request("JSON", {})
