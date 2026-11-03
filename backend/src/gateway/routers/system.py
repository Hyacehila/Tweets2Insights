from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel, Field, SecretStr, ConfigDict
from urllib.parse import urlsplit
from opinion_gateway import credentials
from opinion_core.analytics.toolbox import catalog
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


@router.get("/api/analysis-tools")
def analysis_tools():
    return catalog()


@router.get("/api/providers")
def providers():
    return credentials.status()


class CredentialInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str
    api_key: SecretStr
    endpoint: str | None = Field(default=None, max_length=500)


@router.post("/api/providers")
def configure_provider(
    body: CredentialInput, request: Request, value=Depends(settings)
):
    origin = request.headers.get("origin")
    if request.client and request.client.host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(
            403, "credential changes are available on the local workstation only"
        )
    if origin and origin != value.frontend_origin:
        expected, actual = urlsplit(value.frontend_origin), urlsplit(origin)
        loopback = {"localhost", "127.0.0.1", "::1"}
        if not (
            actual.hostname in loopback
            and expected.hostname in loopback
            and actual.scheme == expected.scheme
            and actual.port == expected.port
        ):
            raise HTTPException(403, "untrusted origin")
    return credentials.save(
        body.provider, body.api_key.get_secret_value(), body.endpoint
    )
