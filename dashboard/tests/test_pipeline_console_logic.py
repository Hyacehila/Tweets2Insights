"""
Tests for Pipeline Console page-side validation helpers.
"""

from dashboard.logic.pipeline_console_logic import build_failure_status_payload, validate_pipeline_form


def _valid_flat_config():
    return {
        "data.input_path": "data/posts_sample_30.json",
        "data.output_path": "data/enhanced_posts_sample_30.json",
        "data.topics_path": "data/topics.json",
        "data.sentiment_attributes_path": "data/sentiment_attributes.json",
        "data.publisher_objects_path": "data/publisher_objects.json",
        "data.belief_system_path": "data/believe_system_common.json",
        "stage2.forum_max_rounds": 5,
        "stage2.forum_min_rounds_for_sufficient": 2,
    }


def test_validate_pipeline_form_accepts_valid_inputs():
    errors = validate_pipeline_form(_valid_flat_config())
    assert errors == []


def test_validate_pipeline_form_rejects_empty_required_path():
    flat = _valid_flat_config()
    flat["data.input_path"] = ""

    errors = validate_pipeline_form(flat)

    assert any("Input data path" in err for err in errors)


def test_validate_pipeline_form_rejects_forum_min_over_max():
    flat = _valid_flat_config()
    flat["stage2.forum_max_rounds"] = 2
    flat["stage2.forum_min_rounds_for_sufficient"] = 3

    errors = validate_pipeline_form(flat)

    assert any("forum_min_rounds_for_sufficient" in err for err in errors)


def test_build_failure_status_payload_normalizes_event_shape():
    payload = build_failure_status_payload(
        {},
        error_message="boom",
        stage="stage2",
        now_utc="2026-02-20T00:00:00Z",
    )

    assert payload["version"] == 2
    assert payload["run_id"]
    assert payload["current_stage"] == "stage2"
    assert payload["current_node"] == "PipelineConsole"
    assert isinstance(payload["events"], list)


def test_build_failure_status_payload_appends_failed_exit_event():
    payload = build_failure_status_payload(
        {
            "version": 2,
            "run_id": "run-123",
            "current_stage": "stage1",
            "current_node": "NodeA",
            "events": [],
        },
        error_message="run failed",
        stage="stage3",
        now_utc="2026-02-20T00:00:05Z",
    )

    assert payload["events"][-1]["event"] == "exit"
    assert payload["events"][-1]["status"] == "failed"
    assert payload["events"][-1]["stage"] == "stage3"
    assert payload["events"][-1]["node"] == "PipelineConsole"
