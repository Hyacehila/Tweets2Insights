"""Public model configuration. Credentials never enter workflow artifacts."""

from urllib.parse import urlsplit
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["qwen", "glm", "openai_compatible"] = "qwen"
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model: str = Field(default="qwen3.8-max", min_length=1, max_length=160)
    max_tokens: int = Field(default=8192, ge=1024, le=131072)
    timeout_seconds: int = Field(default=120, ge=10, le=600)
    extra_body: dict = Field(default_factory=dict)

    @field_validator("base_url")
    @classmethod
    def endpoint(cls, value):
        url = urlsplit(value)
        if (
            not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.scheme not in {"http", "https"}
            or (
                url.scheme == "http"
                and url.hostname not in {"localhost", "127.0.0.1", "::1"}
            )
        ):
            raise ValueError(
                "use an HTTPS Base URL, or HTTP on localhost, without credentials or query parameters"
            )
        if url.path.rstrip("/").endswith("/chat/completions"):
            raise ValueError("Base URL must not include /chat/completions")
        return value.rstrip("/")

    @field_validator("extra_body")
    @classmethod
    def options(cls, value):
        # Only model-generation options; never permit credentials, routing or tools here.
        if set(value) - {
            "enable_thinking",
            "thinking",
            "reasoning_effort",
            "thinking_budget",
            "temperature",
            "top_p",
        }:
            raise ValueError("unsupported model option")
        return value
