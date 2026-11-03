"""
Rule-based sentiment scoring with a tiny lexicon.
"""
from __future__ import annotations

from typing import Dict, List

from opinion_core.analytics.nlp.tokenizer import tokenize


_POS_WORDS = {
    "好", "赞", "喜欢", "支持", "满意", "认可", "感谢", "顺利", "成功", "稳定",
    "positive", "great", "good", "love", "support",
}
_NEG_WORDS = {
    "差", "糟糕", "不满", "担心", "恐惧", "失败", "失望", "抱怨", "焦虑", "愤怒",
    "negative", "bad", "hate", "angry", "worry",
}


def lexicon_sentiment(text: str) -> Dict[str, object]:
    """Return lexicon-based sentiment label and score."""
    if not text:
        return {"label": "neutral", "score": 0, "positive": 0, "negative": 0}
    tokens: List[str] = tokenize(text)
    if not tokens:
        return {"label": "neutral", "score": 0, "positive": 0, "negative": 0}

    pos = sum(1 for t in tokens if t in _POS_WORDS)
    neg = sum(1 for t in tokens if t in _NEG_WORDS)
    score = pos - neg
    if score > 0:
        label = "positive"
    elif score < 0:
        label = "negative"
    else:
        label = "neutral"
    return {"label": label, "score": score, "positive": pos, "negative": neg}
