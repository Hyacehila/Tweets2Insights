"""
Tokenizer wrapper (jieba) with light normalization.
"""
from __future__ import annotations

import logging
import re
from typing import List

try:
    import jieba  # type: ignore
except Exception:  # pragma: no cover - fallback if jieba missing
    jieba = None

from opinion_core.analytics.nlp.text_cleaner import clean_text


if jieba is not None:
    logging.getLogger("jieba").setLevel(logging.ERROR)
    try:
        jieba.initialize()
    except Exception:
        jieba = None


def tokenize(text: str) -> List[str]:
    """Tokenize text using jieba. Returns a list of non-empty tokens."""
    if not text:
        return []
    cleaned = clean_text(text)
    if not cleaned:
        return []
    if jieba is not None:
        tokens = [t.strip() for t in jieba.lcut(cleaned, HMM=False)]
    else:
        # Fallback: keep CJK chars and word tokens
        tokens = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", cleaned)
    return [t for t in tokens if t]


def tokenize_batch(texts: List[str]) -> List[List[str]]:
    """Tokenize a batch of texts."""
    return [tokenize(t) for t in texts]
