from fastapi import APIRouter, Depends
from ..dependencies import settings, runtime

router = APIRouter(tags=["system"])


@router.get("/api/health")
def health():
    return {"status": "ok", "application": "Tweets2Insights", "version": "0.2.0"}


@router.get("/api/config")
def config(value=Depends(settings)):
    return {
        "model": value.model,
        "max_agent_calls": value.max_agent_calls,
        "max_subagents": value.max_subagents,
        "domain_validation": "pending",
        "search_providers": ["tavily", "deepseek"],
    }


@router.get("/api/skills")
def skills(manager=Depends(runtime)):
    return [
        {k: v for k, v in item.items() if k != "path"} for item in manager.skills.list()
    ]


@router.get("/api/tools")
async def tools(manager=Depends(runtime)):
    return await manager.mcp.discover()
