"""One domain scheduler; runtime layering does not dictate research roles."""

from opinion_core.schemas.workflow import RunRequest, StageTask, TaskPlan


def compile_plan(request):
    req = RunRequest.model_validate(request)
    selected = set(req.event.objectives)
    steps = [
        (
            "input",
            "InputAgent",
            "collect" if req.event.requires_collection else "load_dataset",
        ),
        ("sample", "SamplingAgent", "sample"),
        ("schema", "SchemaAgent", "prepare_schema"),
        ("labels", "DecisionModel", "label"),
        ("observations", "ObservationService", "observations"),
        ("evidence", "SearchAgent", "evidence"),
    ]
    if "retrospective" in selected:
        steps.append(("analysis", "DataAgent", "analysis"))
        if req.forum_rounds:
            steps.append(("forum", "ForumHost", "forum"))
    if selected & {"forecast", "scenario", "backtest"}:
        steps += [
            ("state", "DynamicsTrainer", "assimilate"),
            ("forecast", "ForecastAgent", "forecast"),
        ]
        if "backtest" in selected:
            steps.append(("backtest", "BacktestService", "backtest"))
    if "scenario" in selected:
        steps += [
            ("scenarios", "ScenarioService", "simulate"),
            ("recommendations", "RecommendationAgent", "recommend"),
        ]
    steps += [
        ("charts", "VisualizationService", "charts"),
        ("content", "ContentAgent", "content"),
        ("theory", "SocialScienceAgent", "theory"),
        ("structure", "ReportUIAgent", "structure"),
        ("report", "ReportRenderer", "render"),
    ]
    tasks = [
        StageTask(
            task_id=key,
            role=role,
            operation=operation,
            dependencies=[steps[i - 1][0]] if i else [],
        )
        for i, (key, role, operation) in enumerate(steps)
    ]
    return TaskPlan(event_id=req.event.event_id, run_id=req.run_id, tasks=tasks)
