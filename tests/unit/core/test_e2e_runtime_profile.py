"""
Unit checks for e2e runtime config/profile helpers.
"""
from __future__ import annotations

import pytest
import yaml
from pathlib import Path

from tests.e2e.cli._e2e_config_runtime import (
    assert_full_pipeline_artifacts,
    assert_stage1_contract,
    assert_stage2_contract,
    assert_stage3_contract,
    build_runtime_config,
    build_runtime_env,
    load_yaml,
)


@pytest.fixture(autouse=True)
def isolated_legacy_configuration(tmp_path, monkeypatch):
    """Unit checks use checked-in data, independently of either application config."""
    path = tmp_path / "legacy-fixture.yaml"
    sample = Path(__file__).resolve().parents[2] / "fixtures" / "sample_enhanced.json"
    path.write_text(yaml.safe_dump({"data": {"output_path": str(sample)}, "pipeline": {"start_stage": 1}}), encoding="utf-8")
    monkeypatch.setattr("tests.e2e.cli._e2e_config_runtime.RESERVED_CONFIG_PATH", path)


def test_build_runtime_config_applies_balanced_stage2_loop_caps(tmp_path, monkeypatch):
    monkeypatch.setenv("GLM_API_KEY", "test-key")
    config_path = build_runtime_config(tmp_path, override_runtime=True)
    cfg = load_yaml(config_path)
    stage2 = cfg.get("stage2", {})

    assert stage2.get("agent_max_iterations") == 3
    assert stage2.get("search_reflection_max_rounds") == 2
    assert stage2.get("forum_max_rounds") == 3


def test_build_runtime_config_can_override_start_stage(tmp_path, monkeypatch):
    monkeypatch.setenv("GLM_API_KEY", "test-key")
    config_path = build_runtime_config(
        tmp_path,
        override_runtime=True,
        start_stage_override=2,
    )
    cfg = load_yaml(config_path)
    assert cfg.get("pipeline", {}).get("start_stage") == 2


def test_build_runtime_config_rejects_invalid_start_stage_override(tmp_path, monkeypatch):
    monkeypatch.setenv("GLM_API_KEY", "test-key")
    with pytest.raises(ValueError):
        build_runtime_config(tmp_path, override_runtime=True, start_stage_override=4)


def test_build_runtime_env_requires_yaml_or_env_glm_key(tmp_path, monkeypatch):
    monkeypatch.setenv("GLM_API_KEY", "test-key")
    config_path = build_runtime_config(tmp_path, override_runtime=True)
    config_dict = load_yaml(config_path)
    config_dict.setdefault("llm", {})["glm_api_key"] = ""
    config_path.write_text(
        yaml.safe_dump(config_dict, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    monkeypatch.delenv("GLM_API_KEY", raising=False)

    with pytest.raises(pytest.fail.Exception):
        build_runtime_env(config_path, tmp_path)


def test_assert_full_pipeline_artifacts_requires_html_trace_and_status(tmp_path):
    enhanced_path = tmp_path / "data" / "enhanced.json"
    enhanced_path.parent.mkdir(parents=True, exist_ok=True)
    enhanced_path.write_text(
        '[{"sentiment_polarity":3,"sentiment_attribute":["中性"],"topics":[{"parent":"社会","sub":"民生"}],"publisher":"媒体"}]',
        encoding="utf-8",
    )

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump({"data": {"output_path": str(enhanced_path)}}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    report_dir = tmp_path / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "analysis_data.json").write_text(
        '{"charts":[],"tables":[],"execution_log":{"tools_executed":[]},"search_context":{}}',
        encoding="utf-8",
    )
    (report_dir / "chart_analyses.json").write_text("{}", encoding="utf-8")
    (report_dir / "insights.json").write_text('{"overall_summary":"ok"}', encoding="utf-8")
    (report_dir / "report.md").write_text("# report", encoding="utf-8")
    (report_dir / "report.html").write_text("<html><body>ok</body></html>", encoding="utf-8")
    (report_dir / "trace.json").write_text(
        '{"loop_status":{"forum":{"current":1,"max":1,"termination_reason":"max_rounds_reached"},"stage3_chapter_review":{"current":0,"max":1,"termination_reason":"sufficient","scores":[90]}}}',
        encoding="utf-8",
    )
    (report_dir / "status.json").write_text(
        '{"version":2,"run_id":"run-test","events":[{"seq":1,"ts":"2026-02-20T00:00:00Z","event":"exit","stage":"system","node":"TerminalNode","branch_id":"main","status":"completed","error":""}]}',
        encoding="utf-8",
    )

    assert_full_pipeline_artifacts(config_path, tmp_path)

    (report_dir / "report.html").unlink()
    with pytest.raises(AssertionError):
        assert_full_pipeline_artifacts(config_path, tmp_path)


def test_build_runtime_config_stage3_seeds_required_inputs(tmp_path, monkeypatch):
    monkeypatch.setenv("GLM_API_KEY", "test-key")
    config_path = build_runtime_config(
        tmp_path,
        override_runtime=True,
        start_stage_override=3,
    )
    assert config_path.exists()
    for name in ["analysis_data.json", "chart_analyses.json", "insights.json"]:
        assert (tmp_path / "report" / name).exists(), f"missing seeded stage3 input: {name}"


def test_build_runtime_config_stage3_seeded_analysis_data_keeps_stage2_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("GLM_API_KEY", "test-key")
    build_runtime_config(
        tmp_path,
        override_runtime=True,
        start_stage_override=3,
    )
    analysis_data = load_yaml(tmp_path / "report" / "analysis_data.json")
    assert {"charts", "tables", "execution_log", "search_context"} <= set(analysis_data.keys())


def test_assert_stage_contracts_validate_structured_outputs(tmp_path):
    enhanced_path = tmp_path / "data" / "enhanced.json"
    enhanced_path.parent.mkdir(parents=True, exist_ok=True)
    enhanced_path.write_text(
        '[{"sentiment_polarity":3,"sentiment_attribute":["中性"],"topics":[{"parent":"社会","sub":"民生"}],"publisher":"媒体"}]',
        encoding="utf-8",
    )
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump({"data": {"output_path": str(enhanced_path)}}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    report_dir = tmp_path / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "analysis_data.json").write_text(
        '{"charts": [], "tables": [], "execution_log": {"tools_executed": []}, "search_context": {}}',
        encoding="utf-8",
    )
    (report_dir / "chart_analyses.json").write_text("{}", encoding="utf-8")
    (report_dir / "insights.json").write_text('{"overall_summary":"ok"}', encoding="utf-8")
    (report_dir / "trace.json").write_text(
        '{"loop_status":{"forum":{"current":1,"max":1,"termination_reason":"max_rounds_reached"},"stage3_chapter_review":{"current":0,"max":1,"termination_reason":"sufficient","scores":[90]}}}',
        encoding="utf-8",
    )
    (report_dir / "report.md").write_text("# test report", encoding="utf-8")
    (report_dir / "report.html").write_text("<html><body>test</body></html>", encoding="utf-8")
    (report_dir / "status.json").write_text(
        '{"version":2,"run_id":"run-test","events":[{"seq":1,"ts":"2026-02-20T00:00:00Z","event":"exit","stage":"system","node":"TerminalNode","branch_id":"main","status":"completed","error":""}]}',
        encoding="utf-8",
    )

    assert_stage1_contract(config_path, tmp_path)
    assert_stage2_contract(tmp_path)
    assert_stage3_contract(tmp_path)


def test_build_runtime_config_accepts_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("GLM_API_KEY", "test-key")
    config_path = build_runtime_config(
        tmp_path,
        override_runtime=True,
        start_stage_override=2,
        overrides={
            "stage2": {
                "forum_max_rounds": 1,
                "forum_min_rounds_for_sufficient": 1,
            }
        },
    )
    cfg = load_yaml(config_path)
    stage2 = cfg.get("stage2", {})
    assert stage2.get("forum_max_rounds") == 1
    assert stage2.get("forum_min_rounds_for_sufficient") == 1


def test_build_runtime_config_applies_fast_llm_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("GLM_API_KEY", "test-key")
    config_path = build_runtime_config(tmp_path, override_runtime=True)
    cfg = load_yaml(config_path)
    llm = cfg.get("llm", {})

    assert llm.get("acceptance_profile") == "fast"
    assert llm.get("reasoning_enabled_stage2") is False
    assert llm.get("reasoning_enabled_stage3") is False
    assert llm.get("vision_thinking_enabled") is False
