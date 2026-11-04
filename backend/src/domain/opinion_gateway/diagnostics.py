"""Persist useful exception messages and stacks without credentials or local variables."""

import os
import re
import traceback

from . import credentials


def redact(text):
    secrets = []

    def values(value):
        if isinstance(value, dict):
            for child in value.values():
                values(child)
        elif isinstance(value, str) and len(value) >= 6:
            secrets.append(value)

    try:
        for key, value in credentials.read().items():
            if any(
                s in key.upper()
                for s in ("KEY", "TOKEN", "COOKIE", "SECRET", "PASSWORD")
            ):
                values(value)
    except (OSError, ValueError):
        pass
    for key, value in os.environ.items():
        if any(
            s in key.upper() for s in ("KEY", "TOKEN", "COOKIE", "SECRET", "PASSWORD")
        ):
            values(value)
    for value in sorted(set(secrets), key=len, reverse=True):
        text = text.replace(value, "[redacted]")
    text = re.sub(r"(?i)(cookie\s*[:=]\s*)[^\r\n]+", r"\1[redacted]", text)
    text = re.sub(r"(?i)(bearer\s+)[^\s;,\"\']+", r"\1[redacted]", text)
    text = re.sub(
        r"(?i)((?:api[_-]?key|access_token|password|secret)\s*[\"\']?\s*[:=]\s*[\"\']?)[^\s&,;\"\']+",
        r"\1[redacted]",
        text,
    )
    return text


def safe_payload(value):
    if isinstance(value, dict):
        return {key: safe_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [safe_payload(item) for item in value]
    return redact(value) if isinstance(value, str) else value


def exception_details(exc, *, stage=""):
    return {
        "stage": stage,
        "error_type": type(exc).__name__,
        "message": redact(str(exc) or type(exc).__name__)[:12000],
        "traceback": redact("".join(traceback.format_exception(exc)))[-32000:],
    }
