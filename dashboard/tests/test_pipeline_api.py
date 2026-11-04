"""
Tests for dashboard pipeline API.
"""
import json
from pathlib import Path

from dashboard.api.pipeline_api import (
    apply_defaults,
    build_config_dict_from_form,
    build_shared_from_config,
    list_data_candidates,
    load_config_dict,
    merge_config_dict,
    run_pipeline,
    save_config_dict,
)


def test_load_and_save_config(tmp_path):
    cfg = {"pipeline": {"start_stage": 1}}
    path = tmp_path / "config.yaml"
    save_config_dict(cfg, str(path))
    loaded = load_config_dict(str(path))
    assert loaded["pipeline"]["start_stage"] == 1


def test_build_shared_from_config(tmp_path, monkeypatch):
    cfg = {
        "data": {
            "input_path": "tests/fixtures/sample_posts.json",
            "output_path": "data/enhanced_posts.json",
            "topics_path": "tests/fixtures/sample_topics.json",
            "sentiment_attributes_path": "tests/fixtures/sample_sentiment_attrs.json",
            "publisher_objects_path": "tests/fixtures/sample_publishers.json",
            "belief_system_path": "data/believe_system_common.json",
        },
        "pipeline": {
            "start_stage": 1,
            "user_analysis_instruction": "重点分析官方回应时效性",
        },
        "stage1": {"mode": "async", "checkpoint": {"enabled": False}},
        "stage2": {"mode": "agent", "tool_source": "mcp", "agent_max_iterations": 1},
        "stage3": {"max_iterations": 1, "chapter_review_max_rounds": 1},
        "runtime": {"concurrent_num": 1, "max_retries": 1, "wait_time": 1},
    }
    path = tmp_path / "config.yaml"
    save_config_dict(cfg, str(path))
    monkeypatch.setenv("ENHANCED_DATA_PATH", cfg["data"]["output_path"])
    monkeypatch.setenv("GLM_API_KEY", "test-key")

    shared = build_shared_from_config(str(path))
    assert "config" in shared
    assert shared["pipeline_state"]["start_stage"] == 1
    assert shared["analysis_context"]["user_analysis_instruction"] == "重点分析官方回应时效性"


def test_run_pipeline_dry_run(tmp_path, monkeypatch):
    cfg = {
        "data": {
            "input_path": "tests/fixtures/sample_posts.json",
            "output_path": "data/enhanced_posts.json",
            "topics_path": "tests/fixtures/sample_topics.json",
            "sentiment_attributes_path": "tests/fixtures/sample_sentiment_attrs.json",
            "publisher_objects_path": "tests/fixtures/sample_publishers.json",
            "belief_system_path": "data/believe_system_common.json",
        },
        "pipeline": {
            "start_stage": 1,
            "user_analysis_instruction": "重点分析官方回应时效性",
        },
        "stage1": {"mode": "async", "checkpoint": {"enabled": False}},
        "stage2": {"mode": "agent", "tool_source": "mcp", "agent_max_iterations": 1},
        "stage3": {"max_iterations": 1, "chapter_review_max_rounds": 1},
        "runtime": {"concurrent_num": 1, "max_retries": 1, "wait_time": 1},
    }
    path = tmp_path / "config.yaml"
    save_config_dict(cfg, str(path))
    monkeypatch.setenv("GLM_API_KEY", "test-key")

    shared = run_pipeline(str(path), dry_run=True)
    assert "config" in shared
    assert shared["analysis_context"]["user_analysis_instruction"] == "重点分析官方回应时效性"


def test_list_data_candidates(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "a.json").write_text("[]", encoding="utf-8")
    (data_dir / "b.json").write_text("[]", encoding="utf-8")
    results = list_data_candidates(str(data_dir))
    assert results == [(data_dir / "a.json").as_posix(), (data_dir / "b.json").as_posix()]


def test_build_config_dict_from_form():
    flat = {
        "data.input_path": "data/sample.json",
        "data.resume_if_exists": False,
        "pipeline.start_stage": 2,
        "pipeline.user_analysis_instruction": "重点分析官方回应时效性",
        "stage1.checkpoint.enabled": False,
    }
    cfg = build_config_dict_from_form(flat)
    assert cfg["data"]["input_path"] == "data/sample.json"
    assert cfg["data"]["resume_if_exists"] is False
    assert cfg["pipeline"]["start_stage"] == 2
    assert cfg["pipeline"]["user_analysis_instruction"] == "重点分析官方回应时效性"
    assert cfg["stage1"]["checkpoint"]["enabled"] is False


def test_apply_defaults_includes_stage2_web_search_defaults():
    merged = apply_defaults({})

    assert merged["stage2"]["search_provider"] == "tavily"
    assert merged["stage2"]["search_max_results"] == 5
    assert merged["stage2"]["search_timeout_seconds"] == 20
    assert merged["stage2"]["search_api_key"] == ""


def test_apply_defaults_includes_stage2_loop_and_chart_defaults():
    merged = apply_defaults({})
    stage2 = merged["stage2"]

    assert stage2["search_reflection_max_rounds"] == 2
    assert stage2["forum_max_rounds"] == 5
    assert stage2["forum_min_rounds_for_sufficient"] == 2
    assert stage2["chart_missing_policy"] == "warn"
    assert stage2["chart_min_per_category"]["sentiment"] == 1
    assert stage2["chart_min_per_category"]["nlp"] == 1


def test_apply_defaults_includes_llm_acceptance_profile_defaults():
    merged = apply_defaults({})
    llm = merged["llm"]

    assert llm["acceptance_profile"] == "fast"
    assert llm["reasoning_enabled_stage2"] is None
    assert llm["reasoning_enabled_stage3"] is None
    assert llm["vision_thinking_enabled"] is None
    assert llm["request_timeout_seconds"] == 120


def test_apply_defaults_stage3_does_not_include_min_score():
    merged = apply_defaults({})

    assert "min_score" not in merged["stage3"]


def test_build_config_dict_from_form_supports_nested_chart_min_category():
    flat = {
        "stage2.chart_min_per_category.sentiment": 2,
        "stage2.chart_min_per_category.topic": 3,
        "stage2.chart_missing_policy": "fail",
    }
    cfg = build_config_dict_from_form(flat)
    assert cfg["stage2"]["chart_min_per_category"]["sentiment"] == 2
    assert cfg["stage2"]["chart_min_per_category"]["topic"] == 3
    assert cfg["stage2"]["chart_missing_policy"] == "fail"


def test_merge_config_dict_preserves_existing_unedited_fields():
    base = {
        "pipeline": {"start_stage": 1},
        "stage2": {
            "forum_max_rounds": 5,
            "chart_tool_allowlist": ["topic_ranking_chart"],
        },
        "custom": {"keep": True},
    }
    updates = {
        "pipeline": {"start_stage": 2},
        "stage2": {
            "forum_max_rounds": 3,
            "search_reflection_max_rounds": 2,
        },
    }

    merged = merge_config_dict(base, updates)

    assert merged["pipeline"]["start_stage"] == 2
    assert merged["stage2"]["forum_max_rounds"] == 3
    assert merged["stage2"]["search_reflection_max_rounds"] == 2
    assert merged["stage2"]["chart_tool_allowlist"] == ["topic_ranking_chart"]
    assert merged["custom"]["keep"] is True


def test_build_config_dict_from_form_supports_llm_controls():
    flat = {
        "llm.acceptance_profile": "fast",
        "llm.reasoning_enabled_stage2": False,
        "llm.reasoning_enabled_stage3": False,
        "llm.vision_thinking_enabled": False,
        "llm.request_timeout_seconds": 120,
    }

    cfg = build_config_dict_from_form(flat)

    assert cfg["llm"]["acceptance_profile"] == "fast"
    assert cfg["llm"]["reasoning_enabled_stage2"] is False
    assert cfg["llm"]["reasoning_enabled_stage3"] is False
    assert cfg["llm"]["vision_thinking_enabled"] is False
    assert cfg["llm"]["request_timeout_seconds"] == 120
