"""Local operator credentials: write-only API, no values in artifacts or logs."""

import json
import os
from pathlib import Path
import tempfile
import threading

LOCK = threading.Lock()
KEYS = {
    "openai_decisions": "OPENAI_API_KEY",
    "jev": "TYPESAFE_API_KEY",
    "aliyun_decision": "DASHSCOPE_API_KEY",
    "tavily": "TAVILY_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}


def path():
    return (
        Path(os.environ.get("T2I_PROJECT_ROOT", Path(__file__).resolve().parents[4]))
        / ".provider-secrets.json"
    )


def read():
    file = path()
    return json.loads(file.read_text(encoding="utf-8")) if file.exists() else {}


def get(name):
    # Re-read on every run: a long-running worker sees UI credential updates.
    return read().get(name) or os.environ.get(name, "")


def save(provider, api_key, endpoint=None):
    if (
        provider not in KEYS
        or not api_key
        or len(api_key) > 4000
        or any(c in api_key for c in "\r\n\0")
    ):
        raise ValueError("invalid provider credential")
    if endpoint:
        from opinion_core.labeling.system_one import validate_endpoint

        validate_endpoint(provider, endpoint)
    if provider == "aliyun_decision" and not endpoint:
        raise ValueError("Alibaba workspace System One endpoint is required")

    def change(data):
        data[KEYS[provider]] = api_key
        if endpoint:
            data[
                "ALIYUN_DECISION_ENDPOINT"
                if provider == "aliyun_decision"
                else "TYPESAFE_ENDPOINT"
            ] = endpoint

    update(change)
    return {"provider": provider, "configured": True}


def update(change):
    with LOCK:
        data = read()
        change(data)
        destination = path()
        handle, temp = tempfile.mkstemp(prefix=".credential-", dir=destination.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(data, stream)
            os.chmod(temp, 0o600)
            os.replace(temp, destination)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)


def status():
    return [
        {"provider": provider, "configured": bool(get(key))}
        for provider, key in KEYS.items()
    ]
