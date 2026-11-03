from typing import Any
from pydantic import Field, field_validator
from .base import Contract, Identifier


class RunManifest(Contract):
    run_id: Identifier
    event_id: Identifier
    dataset_id: Identifier
    data_version: str
    code_version: str
    schema_version: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    seed: int = 0
    max_calls: int = Field(default=0, ge=0)
    max_cost: float = Field(default=0, ge=0, allow_inf_nan=False)

    @field_validator('config_snapshot')
    @classmethod
    def no_secrets(cls, value):
        def check(item):
            if isinstance(item, dict):
                for key, val in item.items():
                    if any(s in key.lower() for s in ('api_key', 'password', 'secret', 'token', 'cookie', 'authorization')):
                        raise ValueError('credentials must not be stored in a manifest')
                    check(val)
            elif isinstance(item, list):
                for val in item:
                    check(val)
        check(value)
        return value
