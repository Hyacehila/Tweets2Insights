from types import SimpleNamespace

from opinion_gateway.supervisor import SupervisorAgent


def test_supervisor_tracks_agents_and_hands_off_stages_without_model_calls():
    events = []
    monitor = SupervisorAgent(lambda kind, value: events.append((kind, value)))
    tasks = [
        {"task_id": "analysis", "role": "DataAgent", "operation": "analysis"},
        {"task_id": "forum", "role": "ForumHost", "operation": "forum"},
    ]
    monitor.start(tasks)
    monitor.observe("stage_started", tasks[0] | {"stage": "analysis"})
    monitor.observe("model_started", {"role": "data", "stage": "analysis"})
    assert monitor.snapshot()["agents"]["data"]["status"] == "running"
    monitor.observe("model_finished", {"role": "data", "stage": "analysis"})
    monitor.observe(
        "stage_finished",
        {"role": "DataAgent", "stage": "analysis", "status": "completed"},
    )
    assert monitor.snapshot()["completed"] == 1
    assert monitor.snapshot()["next_stage"] == "forum"
    monitor.tick()
    assert events[-1][0] == "supervisor_status"


def test_supervisor_diagnoses_error_once_with_available_model():
    events, calls = [], []

    def request(instruction, payload):
        calls.append(payload)
        return {
            "summary": "服务商限流",
            "cause": "HTTP 429",
            "evidence": ["HTTP 429"],
            "suggestions": ["等待后重试"],
            "retryable": True,
        }, {}

    monitor = SupervisorAgent(
        lambda kind, value: events.append((kind, value)),
        model_factory=lambda: SimpleNamespace(request=request),
    )
    monitor.start([])
    monitor.fail(ValueError("HTTP 429 rate_limit_exceeded"), stage="forum")
    monitor.fail(ValueError("HTTP 429 rate_limit_exceeded"), stage="forum")
    report = next(value for kind, value in events if kind == "supervisor_diagnosis")
    assert report["source"] == "model"
    assert report["suggestions"] == ["等待后重试"]
    assert len(calls) == 1


def test_supervisor_keeps_actionable_diagnosis_when_budget_is_exhausted():
    events = []

    def unavailable():
        raise RuntimeError("budget exhausted")

    monitor = SupervisorAgent(
        lambda kind, value: events.append((kind, value)), model_factory=unavailable
    )
    monitor.fail(
        ValueError("model output incomplete: finish_reason=length"), stage="forum"
    )
    report = next(value for kind, value in events if kind == "supervisor_diagnosis")
    assert report["source"] == "rules"
    assert any("输出" in item for item in report["suggestions"])
    assert "length" in report["evidence"][0]


def test_supervisor_closes_nested_agent_and_preserves_partial_stage():
    monitor = SupervisorAgent(lambda *args: None)
    monitor.start([{"task_id": "labels", "role": "LabelAgent"}])
    monitor.observe("stage_started", {"stage": "labels", "role": "LabelAgent"})
    monitor.observe("label_progress", {"done": 300, "total": 300, "cache_hits": 251})
    monitor.observe(
        "stage_finished", {"stage": "labels", "role": "LabelAgent", "status": "partial"}
    )
    assert monitor.snapshot()["agents"]["DecisionModel"]["status"] == "partial"
    assert monitor.snapshot()["agents"]["LabelAgent"]["status"] == "partial"
    assert monitor.snapshot()["completed"] == 0


def test_supervisor_marks_waiting_for_login_without_diagnosing_error():
    monitor = SupervisorAgent(lambda *args: None)
    monitor.start([{"task_id": "input", "role": "CollectorAgent"}])
    monitor.observe("stage_started", {"stage": "input", "role": "CollectorAgent"})
    monitor.pause("waiting_for_auth", "请完成平台登录")
    assert monitor.snapshot()["status"] == "waiting_for_auth"
    assert (
        monitor.snapshot()["agents"]["CollectorAgent"]["status"] == "waiting_for_auth"
    )
