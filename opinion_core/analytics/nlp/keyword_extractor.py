"""
Keyword extraction using jieba TF-IDF with safe fallbacks.
"""
from __future__ import annotations

from collections import Counter
from typing import List

try:
    import jieba.analyse  # type: ignore
except Exception:  # pragma: no cover
    jieba = None

from opinion_core.analytics.nlp.tokenizer import tokenize


def extract_keywords(text: str, top_n: int = 10) -> List[str]:
    """Extract top-N keywords from text."""
    if not text:
        return []
    top_n = max(1, int(top_n))
    if "jieba" in globals() and jieba is not None:
        try:
            keywords = jieba.analyse.extract_tags(text, topK=top_n)
            return [k for k in keywords if k]
        except Exception:
            pass

    tokens = tokenize(text)
    if not tokens:
        return []
    counter = Counter(tokens)
    return [w for w, _ in counter.most_common(top_n)]


def extract_keywords_batch(texts: List[str], top_n: int = 10) -> List[List[str]]:
    """Extract keywords for a list of texts."""
    return [extract_keywords(t, top_n=top_n) for t in texts]
