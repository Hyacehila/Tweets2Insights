from opinion_core.schemas.workflow import ScenarioSpec
from opinion_core.dynamics.engine import forecast


def compare_scenarios(state, specs, check_cancel=lambda:None):
    baseline = forecast(state,check_cancel=check_cancel)
    branches = []
    for raw in specs:
        check_cancel()
        spec = ScenarioSpec.model_validate(raw)
        if spec.start_step > state['config']['horizon']:
            raise ValueError('scenario starts beyond forecast horizon')
        result = forecast(state,spec,check_cancel)
        differences = [{'step':b['step'], **{field:s['fields'][field]['mean']-b['fields'][field]['mean']
                         for field in ('stance','sentiment')}} for b,s in zip(baseline['steps'],result['steps'])]
        branches.append({'spec':spec.model_dump(mode='json'),'result':result,'mean_differences':differences})
    return {'kind':'simulated','baseline':baseline,'branches':branches,
            'interpretation':'conditional model differences under stated assumptions; not causal effects'}
