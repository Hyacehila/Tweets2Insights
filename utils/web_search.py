"""
Web search wrapper utilities for Stage2 search ingestion.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests


_TAVILY_SEARCH_URL = "https://api.tavily.com/search"


def _normalize_provider(provider: str) -> str:
    name = (provider or "").strip().lower()
    if name not in {"tavily", "deepseek"}:
        raise ValueError(f"Unsupported search provider: {provider}")
    return name


def search_web(query: str, *, provider: str = "tavily", api_key: Optional[str] = None,
               max_results: int = 5, timeout_seconds: int = 20) -> Dict[str, Any]:
    """Legacy five-field projection plus full evidence provenance at the top level."""
    from opinion_core.evidence.providers import search
    result = search(query, provider=_normalize_provider(provider), api_key=api_key,
                    max_results=min(20, max(1, int(max_results))), timeout_seconds=max(1, int(timeout_seconds)))
    cards = result["results"]
    return {**result, "evidence_cards": cards, "results": [
        {key: str(card.get(key) or "") for key in ("title", "url", "snippet", "date", "source")}
        for card in cards]}


def batch_search(
    queries: List[str],
    *,
    provider: str = "tavily",
    api_key: Optional[str] = None,
    max_results: int = 5,
    timeout_seconds: int = 20,
) -> Dict[str, Any]:
    """
    Execute multiple queries via search_web and aggregate outputs.
    """
    provider_name = _normalize_provider(provider)
    normalized_queries = [(q or "").strip() for q in (queries or []) if (q or "").strip()]
    results_by_query: List[Dict[str, Any]] = []
    total_results = 0

    for query in normalized_queries:
        result = search_web(
            query,
            provider=provider_name,
            api_key=api_key,
            max_results=max_results,
            timeout_seconds=timeout_seconds,
        )
        results_by_query.append(result)
        total_results += len(result.get("results", []))

    return {
        "queries": normalized_queries,
        "provider": provider_name,
        "results_by_query": results_by_query,
        "total_results": total_results,
    }


__all__ = ["search_web", "batch_search"]
