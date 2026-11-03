"""The only domain plan compiler. External Leaders submit plans through the same boundary."""
from opinion_core.schemas.workflow import RunRequest, StageTask, TaskPlan


def compile_plan(request):
    req = RunRequest.model_validate(request)
    steps = [('input', 'Query', 'collect' if req.event.requires_collection else 'load_dataset'),
             ('schema', 'Query', 'prepare_schema'), ('labels', 'Insight', 'label'),
             ('observations', 'Insight', 'observations'), ('charts','Insight','charts'), ('evidence', 'Query', 'evidence')]
    if req.media_mode != 'text_only':
        steps.append(('media', 'Media', 'media'))
    if req.forum_rounds:
        steps.append(('forum', 'Critic', 'forum'))
    if req.model:
        steps += [('state', 'Forecast', 'assimilate'), ('forecast', 'Forecast', 'forecast')]
        if 'backtest' in req.event.objectives:
            steps.append(('backtest', 'Forecast', 'backtest'))
    if req.scenarios:
        steps.append(('scenarios', 'Scenario', 'simulate'))
    steps += [('content', 'Content', 'content'), ('structure', 'Structure', 'structure'), ('report', 'Structure', 'render')]
    tasks = [StageTask(task_id=key,role=role,operation=op,dependencies=[steps[i-1][0]] if i else [])
             for i,(key,role,op) in enumerate(steps)]
    return TaskPlan(event_id=req.event.event_id,run_id=req.run_id,tasks=tasks)
