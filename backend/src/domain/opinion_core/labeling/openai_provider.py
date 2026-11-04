"""OpenAI-compatible Chat Completions JSON adapter for research agents."""

import hashlib
import json
import requests


class OpenAIJsonProvider:
    def __init__(self, config, api_key):
        self.config = config
        self.client = requests.Session()
        self.api_key = api_key
        self.model = config.model
        digest = hashlib.sha256(config.model_dump_json().encode()).hexdigest()[:16]
        self.version = f"openai-compatible:{config.model}:{digest}"

    def request(self, instruction, payload):
        response = self.client.post(
            self.config.base_url + "/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": instruction
                        + "\nReturn exactly one JSON object, without Markdown fences.",
                    },
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False),
                    },
                ],
                "response_format": {"type": "json_object"},
                "stream": False,
                "max_tokens": self.config.max_tokens,
                **self.config.extra_body,
            },
            timeout=(10, self.config.timeout_seconds),
            allow_redirects=False,
        )
        if response.status_code != 200:
            # Provider errors can echo credentials or submitted content.
            raise ValueError(f"model endpoint returned HTTP {response.status_code}")
        try:
            body = response.json()
            choice = body["choices"][0]
            if choice.get("finish_reason") not in {None, "stop"}:
                raise ValueError("model output incomplete")
            result = json.loads(choice["message"]["content"])
            if not isinstance(result, dict):
                raise ValueError("model output must be an object")
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError(
                "model must return a complete JSON object in message.content"
            ) from exc
        usage = body.get("usage") or {}
        return result, {
            "input_tokens": usage.get("prompt_tokens", 0) or 0,
            "output_tokens": usage.get("completion_tokens", 0) or 0,
        }
