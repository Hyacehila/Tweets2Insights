"""
Text similarity and clustering utilities (TF-IDF + cosine).
"""
from __future__ import annotations

from typing import List

import numpy as np

try:
    from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
    from sklearn.metrics.pairwise import cosine_similarity  # type: ignore
    _SKLEARN_AVAILABLE = True
except Exception:  # pragma: no cover
    TfidfVectorizer = None  # type: ignore
    cosine_similarity = None  # type: ignore
    _SKLEARN_AVAILABLE = False

from opinion_core.analytics.nlp.tokenizer import tokenize


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def cluster_similar_texts(
    texts: List[str],
    threshold: float = 0.8,
    min_cluster_size: int = 2,
) -> List[int]:
    """
    Cluster texts by cosine similarity; return group id per text.
    Groups smaller than min_cluster_size are labeled -1.
    """
    if not texts:
        return []
    if len(texts) == 1:
        return [0]

    if _SKLEARN_AVAILABLE:
        cleaned = [" ".join(tokenize(t)) for t in texts]
        vectorizer = TfidfVectorizer(token_pattern=None, tokenizer=lambda s: s.split())
        try:
            tfidf = vectorizer.fit_transform(cleaned)
        except ValueError:
            return [-1 for _ in texts]
        sim = cosine_similarity(tfidf)
    else:
        token_sets = [set(tokenize(t)) for t in texts]
        sim = np.zeros((len(texts), len(texts)))
        for i in range(len(texts)):
            for j in range(len(texts)):
                if i == j:
                    sim[i, j] = 1.0
                else:
                    union = token_sets[i] | token_sets[j]
                    inter = token_sets[i] & token_sets[j]
                    sim[i, j] = len(inter) / len(union) if union else 0.0
    uf = _UnionFind(len(texts))
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if sim[i, j] >= threshold:
                uf.union(i, j)

    # Map root -> group id
    root_to_group = {}
    groups = []
    for idx in range(len(texts)):
        root = uf.find(idx)
        if root not in root_to_group:
            root_to_group[root] = len(root_to_group)
        groups.append(root_to_group[root])

    # Apply min_cluster_size
    group_counts = {}
    for g in groups:
        group_counts[g] = group_counts.get(g, 0) + 1
    final = []
    for g in groups:
        if group_counts.get(g, 0) < min_cluster_size:
            final.append(-1)
        else:
            final.append(g)
    return final
