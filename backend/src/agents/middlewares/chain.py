from opinion_core.schemas.workflow import RunRequest


def prepare_context(state, settings, skills):
    return {
        "messages": state.get("messages", [])[-settings.context_messages :],
        "skills": skills.context(skills.enabled),
        "model_calls": 0,
        "model_usage": [],
        "job": None,
        "subagent_results": [],
        "plan": {},
        "reply": "",
        "status": "planning",
    }


def validate_request(state, request):
    req = RunRequest.model_validate(request)
    if req.event.event_id != state["event_id"]:
        raise ValueError("agent cannot change the thread event")
    if not req.event.requires_collection and req.event.dataset_ref not in {
        d["dataset_id"] for d in state["datasets"]
    }:
        raise ValueError("agent can only use datasets registered for this event")
    return req.model_dump(mode="json")
