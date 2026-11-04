"""
Base data source interfaces.
"""
from __future__ import annotations

from typing import Any, Dict, List


class BaseDataSource:
    """Abstract interface for data sources."""

    def load_blog_data(self, path: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def load_enhanced_data(self, path: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def load_topics(self, path: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def load_sentiment_attributes(self, path: str) -> List[str]:
        raise NotImplementedError

    def load_publisher_objects(self, path: str) -> List[str]:
        raise NotImplementedError

    def load_belief_system(self, path: str) -> List[Dict[str, Any]]:
        raise NotImplementedError
