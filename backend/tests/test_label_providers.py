from types import SimpleNamespace

import pytest


def test_cli_search_accepts_preparation_api_key_and_uses_saved_credential(monkeypatch):
    import opinion_core.evidence.providers as search_module
    from opinion_gateway.label_workflow import search_with_credentials

    from opinion_gateway import credentials

    monkeypatch.setattr(credentials, "get", lambda key: "synthetic-search-key")
    captured = {}

    def fake_search(query, **kwargs):
        captured.update(kwargs)
        return {"provider": kwargs["provider"], "results": []}

    monkeypatch.setattr(search_module, "search", fake_search)
    search_with_credentials("event", provider="tavily", api_key=None, max_results=5)
    assert captured == {
        "provider": "tavily",
        "api_key": "synthetic-search-key",
        "max_results": 5,
    }


def test_label_cli_only_accepts_decision_providers():
    from opinion_gateway.label_workflow import build_parser

    parser = build_parser()
    required = [
        "--event",
        "event.json",
        "--library",
        "library.json",
        "--run-id",
        "test",
    ]
    args = parser.parse_args(required)
    assert args.provider == "openai_decisions" and args.batch_size == 1
    with pytest.raises(SystemExit):
        parser.parse_args([*required, "--provider", "glm"])
    with pytest.raises(SystemExit):
        parser.parse_args([*required, "--batch-size", "10"])


@pytest.mark.parametrize(
    "name,model",
    [
        ("openai_decisions", "gpt-6-luna"),
        ("jev", "jev-latest"),
        ("aliyun_decision", "decision-model-preview"),
    ],
)
def test_worker_and_cli_share_decision_provider_factory(
    tmp_path, monkeypatch, name, model
):
    from opinion_core.schemas.workflow import LabelOptions
    from opinion_gateway.label_providers import make_label_provider

    from opinion_gateway import credentials

    monkeypatch.setenv("T2I_PROJECT_ROOT", str(tmp_path))
    credentials.save(
        name,
        "synthetic-key",
        "https://workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/systemone"
        if name == "aliyun_decision"
        else None,
    )
    provider = make_label_provider(LabelOptions(provider=name), object())
    assert provider.model == model
    assert provider.api_key == "synthetic-key"


def test_schema_builder_uses_selected_agent_and_preserves_evidence_limits():
    from opinion_core.labeling.schema_builder import SchemaBuilder

    captured = {}

    def request(prompt, payload):
        captured.update(payload)
        return {"topics": []}, {"input_tokens": 10, "output_tokens": 5}

    builder = SchemaBuilder(SimpleNamespace(version="custom-agent", request=request))
    result = builder(
        {
            "results": [
                {
                    "title": "a" * 500,
                    "snippet": "b" * 2000,
                    "url": "https://example.com",
                }
            ]
            * 8,
            "sample": {"sample": [{"content": "c" * 2000, "private_extra": "ignored"}]},
        },
        {},
    )
    assert len(captured["evidence"]) == 5
    assert len(captured["evidence"][0]["snippet"]) == 1500
    assert captured["sample"]["sample"] == [{"content": "c" * 1500}]
    assert builder.version.startswith("custom-agent:")
    assert result == {"topics": []} and builder.last_usage["input_tokens"] == 10
