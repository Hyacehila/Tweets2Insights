from opinion_core.schemas.workflow import ScenarioSpec
from opinion_core.dynamics.engine import forecast


def compare_scenarios(state, specs, check_cancel=lambda: None):
    baseline = forecast(state, check_cancel=check_cancel)
    branches = []
    for raw in specs:
        check_cancel()
        spec = ScenarioSpec.model_validate(raw)
        if spec.start_step > state["config"]["horizon"]:
            raise ValueError("scenario starts beyond forecast horizon")
        result = forecast(state, spec, check_cancel)
        differences = [
            {
                "step": b["step"],
                **{
                    field: s["fields"][field]["mean"] - b["fields"][field]["mean"]
                    for field in ("stance", "sentiment")
                },
            }
            for b, s in zip(baseline["steps"], result["steps"])
        ]
        baseline_variance = baseline["steps"][-1]["fields"]["stance"]["variance"]
        final = result["steps"][-1]["fields"]
        metrics = {
            "final_stance_variance": final["stance"]["variance"],
            "stance_variance_change": final["stance"]["variance"] - baseline_variance,
            "final_negative_sentiment_mass": final["sentiment"]["negative_mass"],
            "resource_cost": spec.resource_cost,
        }
        branches.append(
            {
                "spec": spec.model_dump(mode="json"),
                "result": result,
                "mean_differences": differences,
                "metrics": metrics,
            }
        )
    # Pareto comparison explicitly exposes both objectives; no arbitrary cost/benefit weight.
    for branch in branches:
        metric = branch["metrics"]
        branch["pareto_efficient"] = not any(
            other["metrics"]["final_stance_variance"] <= metric["final_stance_variance"]
            and other["metrics"]["resource_cost"] <= metric["resource_cost"]
            and (
                other["metrics"]["final_stance_variance"]
                < metric["final_stance_variance"]
                or other["metrics"]["resource_cost"] < metric["resource_cost"]
            )
            for other in branches
        )
    return {
        "kind": "simulated",
        "baseline": baseline,
        "branches": branches,
        "comparison_objectives": [
            "minimize final stance variance",
            "minimize stated resource cost",
        ],
        "pairing": "same fitted state and random-number stream for every branch",
        "interpretation": "conditional model differences under stated assumptions; not causal effects",
    }
