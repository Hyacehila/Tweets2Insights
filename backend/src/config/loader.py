import os
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field
from dotenv import load_dotenv
import yaml


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repository_root: Path
    state_root: Path
    asset_root: Path
    model: str = "glm-4.5-air"
    model_api_key_env: str = "GLM_API_KEY"
    gateway_host: str = "127.0.0.1"
    gateway_port: int = Field(default=8001, ge=1, le=65535)
    max_agent_calls: int = Field(default=4, ge=1, le=100)
    context_messages: int = Field(default=12, ge=1, le=1000)
    max_subagents: int = Field(default=2, ge=0, le=5)
    request_timeout_seconds: int = Field(default=180, ge=1, le=3600)
    frontend_origin: str = "http://localhost:3000"
    skills_roots: list[str] = Field(
        default_factory=lambda: ["skills/public", "skills/custom"]
    )


def load_settings():
    root = Path(
        os.environ.get("T2I_PROJECT_ROOT", Path(__file__).resolve().parents[3])
    ).resolve()
    load_dotenv(root / ".env", override=False)

    def rooted(value):
        path = Path(value)
        return (path if path.is_absolute() else root / path).resolve()

    path = rooted(os.environ.get("T2I_CONFIG_FILE", "config.yaml"))
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    app = (raw or {}).get("application", {})
    runtime = (raw or {}).get("agent_runtime", {})
    model = (raw or {}).get("models", {}).get("default", {})
    if model.get("provider", "glm") != "glm":
        raise ValueError("the configured Agent model provider is not implemented")
    settings = Settings(
        repository_root=root,
        state_root=rooted(
            os.environ.get("T2I_STATE_ROOT", app.get("state_dir", ".app-state"))
        ),
        asset_root=rooted(
            os.environ.get("T2I_ASSET_ROOT", app.get("asset_dir", ".opinion-assets"))
        ),
        model=model.get("model", "glm-4.5-air"),
        model_api_key_env=model.get("api_key_env", "GLM_API_KEY"),
        gateway_host=app.get("host", "127.0.0.1"),
        gateway_port=app.get("port", 8001),
        max_agent_calls=runtime.get("max_model_calls", 4),
        max_subagents=runtime.get("max_subagents", 2),
        context_messages=runtime.get("context_messages", 12),
        request_timeout_seconds=runtime.get("timeout_seconds", 180),
        frontend_origin=app.get("frontend_origin", "http://localhost:3000"),
    )
    settings.state_root.mkdir(parents=True, exist_ok=True)
    settings.asset_root.mkdir(parents=True, exist_ok=True)
    return settings
