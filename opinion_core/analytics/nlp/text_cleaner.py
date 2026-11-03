"""
Text cleaning utilities for lightweight NLP.

Keep it minimal and deterministic (no external model dependencies).
"""
from __future__ import annotations

import re


_URL_RE = re.compile(r"(https?://\S+|www\.\S+)", re.IGNORECASE)
_HTML_RE = re.compile(r"<[^>]+>")
_MULTI_SPACE_RE = re.compile(r"\s+")

# Basic emoji blocks (covers most common emoji ranges)
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "\U00002700-\U000027BF"
    "]+",
    flags=re.UNICODE,
)


def clean_text(text: str) -> str:
    """Remove URLs, HTML tags, emoji, and normalize whitespace."""
    if not text:
        return ""
    cleaned = _URL_RE.sub(" ", str(text))
    cleaned = _HTML_RE.sub(" ", cleaned)
    cleaned = _EMOJI_RE.sub(" ", cleaned)
    cleaned = cleaned.replace("\u200b", " ")
    cleaned = _MULTI_SPACE_RE.sub(" ", cleaned).strip()
    return cleaned
