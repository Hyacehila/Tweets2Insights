"""
Shared helpers for config-driven live E2E tests.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
RESERVED_CONFIG_PATH = REPO_ROOT / "legacy" / "config.yaml"
DATA_PATH_KEYS = (
    "input_path",
    "topics_path",
    "sentiment_attributes_path",
    "publisher_objects_path",
    "belief_system_path",
)


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_reserved_config() -> dict[str, Any]:
    if not RESERVED_CONFIG_PATH.exists():
        pytest.fail(f"Reserved config is missing: {RESERVED_CONFIG_PATH}")
    return load_yaml(RESERVED_CONFIG_PATH)


def require_yaml_api_key(config_dict: dict[str, Any]) -> str:
    yaml_key = str(config_dict.get("llm", {}).get("glm_api_key", "")).strip()
    if yaml_key:
        return yaml_key

    env_key = os.environ.get("GLM_API_KEY", "").strip()
    if env_key:
        return env_key

    pytest.fail(
        "GLM API key is required for e2e live API tests "
        "(set config.yaml.llm.glm_api_key or env GLM_API_KEY)."
    )


def require_tavily_api_key(config_dict: dict[str, Any]) -> str:
    stage2_cfg = config_dict.get("stage2", {}) or {}
    yaml_key = str(stage2_cfg.get("search_api_key", "")).strip()
    if yaml_key:
        return yaml_key

    env_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if env_key:
        return env_key

    pytest.fail(
        "Tavily API key is required for Tavily live e2e tests "
        "(set config.yaml.stage2.search_api_key or env TAVILY_API_KEY)."
    )


def _to_absolute_path(raw_path: str) -> str:
    path_obj = Path(raw_path)
    if path_obj.is_absolute():
        return str(path_obj)
    return str((REPO_ROOT / path_obj).resolve())


def _deep_merge(dst: dict[str, Any], src: dict[str, Any]) -> None:
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            _deep_merge(dst[key], value)
        else:
            dst[key] = copy.deepcopy(value)


def build_runtime_config(
    tmp_path: Path,
    *,
    override_runtime: bool = True,
    start_stage_override: int | None = None,
    overrides: dict[str, Any] | None = None,
) -> Path:
    """
    Build a temporary config derived from legacy/config.yaml.
    Keeps stage/pipeline settings, redirects outputs, and optionally overrides runtime.
    """
    config_dict = copy.deepcopy(load_reserved_config())
    require_yaml_api_key(config_dict)
    if overrides:
        _deep_merge(config_dict, overrides)

    data_cfg = config_dict.setdefault("data", {})
    for key in DATA_PATH_KEYS:
        raw = data_cfg.get(key)
        if raw:
            data_cfg[key] = _to_absolute_path(str(raw))

    source_enhanced_path = Path(_to_absolute_path(str(data_cfg.get("output_path", ""))))

    output_name = Path(str(data_cfg.get("output_path", "enhanced_posts_sample_30.json"))).name
    output_path = (tmp_path / "data" / output_name).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data_cfg["output_path"] = str(output_path)
    data_cfg["resume_if_exists"] = False

    pipeline_cfg = config_dict.setdefault("pipeline", {})
    if start_stage_override is not None:
        if int(start_stage_override) not in {1, 2, 3}:
            raise ValueError("start_stage_override must be one of [1,2,3]")
        pipeline_cfg["start_stage"] = int(start_stage_override)
    start_stage = int(pipeline_cfg.get("start_stage", 1))

    if start_stage >= 2:
        if not source_enhanced_path.is_file():
            pytest.fail(f"Missing reserved enhanced data for stage>=2 runs: {source_enhanced_path}")
        shutil.copy2(source_enhanced_path, output_path)

    if start_stage >= 3:
        _seed_stage3_inputs(tmp_path)

    if override_runtime:
        runtime_cfg = config_dict.setdefault("runtime", {})
        runtime_cfg["concurrent_num"] = 4
        runtime_cfg["max_retries"] = 1
        runtime_cfg["wait_time"] = 1

        # Balanced profile for live API E2E: lower loop caps to control cost and duration.
        stage2_cfg = config_dict.setdefault("stage2", {})
        stage2_cfg["agent_max_iterations"] = 3
        stage2_cfg["search_reflection_max_rounds"] = 2
        stage2_cfg["forum_max_rounds"] = 3

        llm_cfg = config_dict.setdefault("llm", {})
        llm_cfg["acceptance_profile"] = "fast"
        llm_cfg["reasoning_enabled_stage2"] = False
        llm_cfg["reasoning_enabled_stage3"] = False
        llm_cfg["vision_thinking_enabled"] = False

        if overrides:
            if isinstance(overrides.get("runtime"), dict):
                _deep_merge(runtime_cfg, overrides["runtime"])
            if isinstance(overrides.get("stage2"), dict):
                _deep_merge(stage2_cfg, overrides["stage2"])
            if isinstance(overrides.get("llm"), dict):
                _deep_merge(llm_cfg, overrides["llm"])

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(config_dict, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    _prepare_runtime_workspace(tmp_path)
    return config_path


def _seed_stage3_inputs(tmp_path: Path) -> None:
    """Seed Stage3 prerequisite files under tmp_path/report for start_stage=3 scenarios."""
    source_report_dir = REPO_ROOT / "report"
    target_report_dir = tmp_path / "report"
    target_report_dir.mkdir(parents=True, exist_ok=True)

    required_json = ("analysis_data.json", "chart_analyses.json", "insights.json", "trace.json")
    fallback_payloads = {
        "analysis_data.json": {"charts": [], "tables": [], "execution_log": {}, "search_context": {}},
        "chart_analyses.json": {},
        "insights.json": {},
        "trace.json": {"decisions": [], "executions": [], "reflections": [], "insight_provenance": {}, "loop_status": {}},
    }
    for file_name in required_json:
        source = source_report_dir / file_name
        target = target_report_dir / file_name
        if source.exists():
            shutil.copy2(source, target)
        else:
            target.write_text(json.dumps(fallback_payloads[file_name], ensure_ascii=False), encoding="utf-8")

    # Normalize copied files to keep stage2/stage3 contract stable for start_stage=3 runs.
    analysis_path = target_report_dir / "analysis_data.json"
    try:
        analysis_data = json.loads(analysis_path.read_text(encoding="utf-8"))
    except Exception:
        analysis_data = {}
    if not isinstance(analysis_data, dict):
        analysis_data = {}
    analysis_data.setdefault("charts", [])
    analysis_data.setdefault("tables", [])
    analysis_data.setdefault("execution_log", {})
    analysis_data.setdefault("search_context", {})
    analysis_path.write_text(json.dumps(analysis_data, ensure_ascii=False), encoding="utf-8")

    trace_path = target_report_dir / "trace.json"
    try:
        trace_data = json.loads(trace_path.read_text(encoding="utf-8"))
    except Exception:
        trace_data = {}
    if not isinstance(trace_data, dict):
        trace_data = {}
    loop_status = trace_data.setdefault("loop_status", {})
    if not isinstance(loop_status, dict):
        loop_status = {}
        trace_data["loop_status"] = loop_status
    loop_status.setdefault("forum", {"current": 0, "max": 0, "termination_reason": "seeded"})
    trace_path.write_text(json.dumps(trace_data, ensure_ascii=False), encoding="utf-8")

    source_images = source_report_dir / "images"
    target_images = target_report_dir / "images"
    if source_images.exists():
        if target_images.exists():
            shutil.rmtree(target_images)
        shutil.copytree(source_images, target_images)
    else:
        target_images.mkdir(parents=True, exist_ok=True)


def _prepare_runtime_workspace(tmp_path: Path) -> None:
    """
    Prepare runtime files expected by subprocess workers when cwd is tmp_path.
    Stage2 MCP currently resolves server path from cwd (utils/mcp_server.py).
    """
    target_utils = tmp_path / "utils"
    if target_utils.exists():
        return
    shutil.copytree(REPO_ROOT / "utils", target_utils)


def build_runtime_env(config_path: Path, tmp_path: Path) -> dict[str, str]:
    config_dict = load_yaml(config_path)
    key = require_yaml_api_key(config_dict)

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "").strip()
    env["PYTHONPATH"] = (
        str(REPO_ROOT)
        if not existing_pythonpath
        else str(REPO_ROOT) + os.pathsep + existing_pythonpath
    )
    env["GLM_API_KEY"] = key
    env["PROJECT_ROOT"] = str(REPO_ROOT)
    env["REPORT_DIR"] = str((tmp_path / "report").resolve())
    return env


@contextmanager
def patched_environ(overrides: dict[str, str]) -> Iterator[None]:
    original = {key: os.environ.get(key) for key in overrides}
    for key, value in overrides.items():
        os.environ[key] = value
    try:
        yield
    finally:
        for key, previous in original.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous


@contextmanager
def working_directory(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_stage1_contract(config_path: Path, tmp_path: Path) -> None:
    del tmp_path
    config_dict = load_yaml(config_path)
    enhanced_data_path = Path(config_dict.get("data", {}).get("output_path", ""))
    assert enhanced_data_path.exists(), f"Missing enhanced data output: {enhanced_data_path}"
    assert enhanced_data_path.stat().st_size > 0, f"Enhanced output is empty: {enhanced_data_path}"

    posts = _load_json(enhanced_data_path)
    assert isinstance(posts, list), "Enhanced output must be a JSON list"
    assert posts, "Enhanced output list is empty"

    required_fields = (
        "sentiment_polarity",
        "sentiment_attribute",
        "topics",
        "publisher",
    )
    for field in required_fields:
        covered = 0
        for item in posts:
            value = item.get(field) if isinstance(item, dict) else None
            if value not in (None, "", [], {}):
                covered += 1
        assert covered > 0, f"Enhanced output has no populated '{field}' field"


def assert_stage2_contract(tmp_path: Path) -> None:
    report_dir = tmp_path / "report"
    analysis_path = report_dir / "analysis_data.json"
    chart_path = report_dir / "chart_analyses.json"
    insights_path = report_dir / "insights.json"
    trace_path = report_dir / "trace.json"

    for artifact in (analysis_path, chart_path, insights_path, trace_path):
        assert artifact.exists(), f"Missing stage2 artifact: {artifact}"
        assert artifact.stat().st_size > 0, f"Stage2 artifact is empty: {artifact}"

    analysis_data = _load_json(analysis_path)
    assert isinstance(analysis_data, dict), "analysis_data.json must be a dict"
    assert {"charts", "tables", "execution_log", "search_context"} <= set(analysis_data.keys())
    assert isinstance(analysis_data.get("charts", []), list)
    assert isinstance(analysis_data.get("tables", []), list)
    assert isinstance(analysis_data.get("execution_log", {}), dict)
    assert isinstance(analysis_data.get("search_context", {}), dict)

    chart_analyses = _load_json(chart_path)
    assert isinstance(chart_analyses, dict), "chart_analyses.json must be a dict"

    insights = _load_json(insights_path)
    assert isinstance(insights, dict), "insights.json must be a dict"
    assert insights, "insights.json should not be empty"

    trace = _load_json(trace_path)
    assert isinstance(trace, dict), "trace.json must be a dict"
    loop_status = trace.get("loop_status", {})
    assert isinstance(loop_status, dict), "trace.loop_status must be a dict"
    assert "forum" in loop_status, "trace.loop_status must include forum status after Stage2"


def assert_stage3_contract(tmp_path: Path) -> None:
    report_dir = tmp_path / "report"
    report_md = report_dir / "report.md"
    report_html = report_dir / "report.html"
    trace_path = report_dir / "trace.json"
    status_path = report_dir / "status.json"

    for artifact in (report_md, report_html, trace_path, status_path):
        assert artifact.exists(), f"Missing stage3 artifact: {artifact}"
        assert artifact.stat().st_size > 0, f"Stage3 artifact is empty: {artifact}"

    markdown_text = report_md.read_text(encoding="utf-8")
    assert "#" in markdown_text, "report.md should contain markdown headings"

    html_text = report_html.read_text(encoding="utf-8").lower()
    assert "<html" in html_text and "<body" in html_text, "report.html should contain html/body tags"

    trace = _load_json(trace_path)
    assert isinstance(trace, dict), "trace.json must be a dict"
    loop_status = trace.get("loop_status", {})
    assert isinstance(loop_status, dict), "trace.loop_status must be a dict"
    assert "stage3_chapter_review" in loop_status, "trace.loop_status must include stage3_chapter_review"

    status = _load_json(status_path)
    assert isinstance(status, dict), "status.json must be a dict"
    assert int(status.get("version", 0)) == 2, "status.json must be v2"
    events = status.get("events", [])
    assert isinstance(events, list), "status.events must be a list"
    terminal_success = [
        item
        for item in events
        if item.get("node") == "TerminalNode"
        and item.get("event") == "exit"
        and item.get("status") == "completed"
    ]
    assert terminal_success, "status.events must include TerminalNode completed exit"


def assert_full_pipeline_artifacts(config_path: Path, tmp_path: Path) -> None:
    assert_stage1_contract(config_path, tmp_path)
    assert_stage2_contract(tmp_path)
    assert_stage3_contract(tmp_path)
