"""OpenAI-compatible Chat Completions JSON adapter for research agents."""

import hashlib
import json
import requests
import re


class ModelResponseError(ValueError):
    def __init__(self, message, usage=None):
        super().__init__(message)
        self.usage = usage or {}


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
            detail = ''
            try:
                error = response.json().get('error', {})
                if isinstance(error, dict):
                    detail = ' · '.join(str(error[key]) for key in ('code', 'type', 'message') if error.get(key))[:2000]
            except (ValueError, AttributeError):
                pass
            if self.api_key:
                detail = detail.replace(self.api_key, '[redacted]')
            detail = re.sub(r'(?i)(bearer\s+|(?:api[_-]?key|token|cookie)\s*[:=]\s*)[^\s,;]+', r'\1[redacted]', detail)
            raise ModelResponseError(f"{self.model}: HTTP {response.status_code}" + (f" · {detail}" if detail else ''))
        usage = {}
        try:
            body = response.json()
            raw_usage = body.get('usage') or {}
            usage = {'input_tokens': raw_usage.get('prompt_tokens', 0) or 0, 'output_tokens': raw_usage.get('completion_tokens', 0) or 0}
            choice = body["choices"][0]
            if choice.get("finish_reason") not in {None, "stop"}:
                raise ValueError(f"model output incomplete: finish_reason={choice.get('finish_reason')}, max_tokens={self.config.max_tokens}")
            result = json.loads(choice["message"]["content"])
            if not isinstance(result, dict):
                raise ValueError("model output must be an object")
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ModelResponseError(
                f"{self.model}: model must return a complete JSON object in message.content; {exc}", usage
            ) from exc
        return result, usage
