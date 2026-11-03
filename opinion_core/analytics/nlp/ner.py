"""
Lightweight entity extraction (rule-based).
"""
from __future__ import annotations

import re
from typing import List

from opinion_core.analytics.nlp.text_cleaner import clean_text


_HASHTAG_RE = re.compile(r"#([^#\s]{2,30})#")
_MENTION_RE = re.compile(r"@([A-Za-z0-9_\-\u4e00-\u9fff]{2,30})")


def extract_entities(text: str) -> List[str]:
    """Extract hashtags and @mentions as lightweight entities."""
    if not text:
        return []
    cleaned = clean_text(text)
    if not cleaned:
        return []
    entities = []
    for tag in _HASHTAG_RE.findall(cleaned):
        entities.append(tag)
    for m in _MENTION_RE.findall(cleaned):
        entities.append(m)

    # De-duplicate while preserving order
    seen = set()
    ordered = []
    for ent in entities:
        if ent not in seen:
            ordered.append(ent)
            seen.add(ent)
    return ordered
