"""
JSON data source implementation.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from utils.data_sources.base import BaseDataSource
from utils import data_loader


class JsonDataSource(BaseDataSource):
    """Load all inputs from JSON files."""

    def __init__(self, loaders: Optional[Dict[str, Callable]] = None):
        loaders = loaders or {}
        self._load_blog_data = loaders.get("load_blog_data", data_loader.load_blog_data)
        self._load_enhanced_data = loaders.get("load_enhanced_blog_data", data_loader.load_enhanced_blog_data)
        self._load_topics = loaders.get("load_topics", data_loader.load_topics)
        self._load_sentiment_attributes = loaders.get("load_sentiment_attributes", data_loader.load_sentiment_attributes)
        self._load_publisher_objects = loaders.get("load_publisher_objects", data_loader.load_publisher_objects)
        self._load_belief_system = loaders.get("load_belief_system", data_loader.load_belief_system)

    def load_blog_data(self, path: str) -> List[Dict[str, Any]]:
        return self._load_blog_data(path)

    def load_enhanced_data(self, path: str) -> List[Dict[str, Any]]:
        return self._load_enhanced_data(path)

    def load_topics(self, path: str) -> List[Dict[str, Any]]:
        return self._load_topics(path)

    def load_sentiment_attributes(self, path: str) -> List[str]:
        return self._load_sentiment_attributes(path)

    def load_publisher_objects(self, path: str) -> List[str]:
        return self._load_publisher_objects(path)

    def load_belief_system(self, path: str) -> List[Dict[str, Any]]:
        return self._load_belief_system(path)
