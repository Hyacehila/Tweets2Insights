"""Local agent model preferences shared by Gateway and domain Worker."""

import hashlib
import os
from pathlib import Path
import yaml
from opinion_core.schemas.agent_model import AgentModelConfig
from . import credentials

QWEN_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
GLM_URL = "https://open.bigmodel.cn/api/paas/v4"


def presets():
    return [
        {
            "id": "qwen",
            "name": "Qwen3.8-Max",
            "source": "https://help.aliyun.com/zh/model-studio/models",
            "config": AgentModelConfig(
                extra_body={"enable_thinking": False}
            ).model_dump(),
        },
        {
            "id": "glm",
            "name": "GLM-5.3",
            "source": "https://docs.bigmodel.cn/cn/guide/models/text/glm-5.3",
            "config": AgentModelConfig(
                provider="glm",
                model="glm-5.3",
                base_url=GLM_URL,
                extra_body={"thinking": {"type": "enabled"}, "reasoning_effort": "low"},
            ).model_dump(),
        },
    ]


def defaults():
    root = Path(os.environ.get("T2I_PROJECT_ROOT", Path(__file__).resolve().parents[4]))
    file = Path(os.environ.get("T2I_CONFIG_FILE", "config.yaml"))
    if not file.is_absolute():
        file = root / file
    raw = (
        (yaml.safe_load(file.read_text(encoding="utf-8")) or {})
        if file.exists()
        else {}
    )
    model = raw.get("models", {}).get("default", {})
    preset = next(
        (
            item["config"]
            for item in presets()
            if item["id"] == model.get("provider", "qwen")
        ),
        {},
    )
    values = {
        **preset,
        **{k: v for k, v in model.items() if k in AgentModelConfig.model_fields},
    }
    return AgentModelConfig(**values)


def active_config(fallback=None):
    stored = credentials.read().get("AGENT_MODEL")
    return AgentModelConfig.model_validate(stored) if stored else fallback or defaults()


def _endpoint_key(config):
    return hashlib.sha256(config.base_url.encode()).hexdigest()


def api_key_for(config):
    stored = credentials.read().get("AGENT_KEYS", {}).get(_endpoint_key(config))
    if stored:
        return stored
    # Built-in credentials are only usable at their own official endpoint.
    if config.base_url == QWEN_URL:
        return credentials.get("QWEN_API_KEY") or credentials.get("DASHSCOPE_API_KEY")
    if config.base_url == GLM_URL:
        return credentials.get("GLM_API_KEY")
    return ""


def is_local(config):
    from urllib.parse import urlsplit

    return urlsplit(config.base_url).hostname in {"localhost", "127.0.0.1", "::1"}


def save_config(config, api_key):
    if any(c in api_key for c in "\r\n\0") or len(api_key) > 4000:
        raise ValueError("invalid credential")
    key = api_key or api_key_for(config)
    if not key and not is_local(config):
        raise ValueError("API key required for this endpoint")

    def change(data):
        data["AGENT_MODEL"] = config.model_dump(mode="json")
        data.setdefault("AGENT_KEYS", {})[_endpoint_key(config)] = key

    credentials.update(change)
    return {"config": config.model_dump(), "configured": bool(key) or is_local(config)}


def resolve_request(req):
    if req.agent_config is None:
        config = active_config()
        if req.agent_model:
            # Preserve explicitly selected legacy GLM models at the GLM endpoint.
            if req.agent_model.startswith("glm-"):
                config = AgentModelConfig(
                    provider="glm", model=req.agent_model, base_url=GLM_URL
                )
            else:
                config = config.model_copy(update={"model": req.agent_model})
        req.agent_config = config
    req.agent_model = req.agent_config.model
    return req
