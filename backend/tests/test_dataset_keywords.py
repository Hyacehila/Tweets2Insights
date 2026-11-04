import pytest

from opinion_core.schemas.workflow import RunRequest
from opinion_core.labeling.event_preparation import EventPreparation
from opinion_core.labeling.schema_builder import SchemaBuilder


def request():
    return {
        "event": {
            "event_id": "demo",
            "input_mode": "existing",
            "dataset_ref": "ds-demo",
            "as_of": "2026-01-03T00:00:00Z",
            "keywords": [],
        },
        "run_id": "run",
        "observations": {
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-02T00:00:00Z",
        },
    }


def test_existing_dataset_can_omit_keywords_but_collection_cannot():
    assert RunRequest.model_validate(request()).event.keywords == []
    value = request()
    value["event"].update(input_mode="keywords", dataset_ref=None)
    value["crawl"] = {"platforms": ["wb"]}
    with pytest.raises(ValueError):
        RunRequest.model_validate(value)


def test_keyword_discovery_precedes_search_and_is_cached(tmp_path):
    library = {
        name: [{"id": f"{name}{i}", "definition": str(i)} for i in range(count)]
        for name, count in [("topics", 5), ("publishers", 5), ("emotions", 10)]
    }
    calls = []

    class Model:
        version = "fixture"

        def request(self, instruction, payload):
            calls.append("model")
            if "keywords" in instruction and "topics" not in instruction:
                return {"keywords": ["夜骑开封", "郑州大学生"]}, {"input_tokens": 10}
            return {
                **library,
                "targets": [{"id": "target", "definition": "支持夜骑安全管理"}],
            }, {"input_tokens": 20}

    def search(query, **kwargs):
        calls.append(query)
        return {
            "provider": "tavily",
            "results": [
                {
                    "title": "夜骑消息",
                    "url": "https://example.com/news",
                    "snippet": "讨论夜骑",
                    "date": "2026-01-01T00:00:00Z",
                }
            ],
        }

    builder = SchemaBuilder(Model())
    service = EventPreparation(
        tmp_path, search=search, builder=builder, builder_version=builder.version
    )
    sample = {
        "sample": [{"post_id": "one", "content": "#夜骑开封# 郑州大学生关注骑行安全"}]
    }
    first = service.prepare(request()["event"], library, sample=sample)
    assert first["status"] == "frozen"
    assert first["keywords"] == ["夜骑开封", "郑州大学生"]
    assert first["keyword_source"] == "sample_agent"
    assert first["calls"] == 3
    assert calls == ["model", "夜骑开封 郑州大学生", "model"]
    assert service.prepare(request()["event"], library, sample=sample) == first
    assert len(calls) == 3


def test_keyword_agent_rejects_empty_or_unbounded_output():
    class Model:
        version = "fixture"

        def request(self, *args):
            return {"keywords": []}, {}

    with pytest.raises(ValueError):
        SchemaBuilder(Model()).discover_keywords({"sample": [{"content": "正文"}]})


def test_research_focus_only_changes_keyword_cache_not_unchanged_schema_prompt():
    from types import SimpleNamespace

    first = SchemaBuilder(SimpleNamespace(version="model"), research_focus="focus one")
    second = SchemaBuilder(SimpleNamespace(version="model"), research_focus="focus two")
    assert first.version == second.version == "model:schema-sampled-prompt-v2"
    assert first.keyword_version != second.keyword_version
