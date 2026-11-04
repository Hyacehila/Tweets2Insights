"""
test_stage1_nodes.py — Stage 1 通用节点单元测试

测试 DataLoadNode, SaveEnhancedDataNode, DataValidationAndOverviewNode, Stage1CompletionNode
的 prep/exec/post 方法。LLM 和文件 I/O 全部 Mock。
"""
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from nodes import (
    DataLoadNode,
    SaveEnhancedDataNode,
    DataValidationAndOverviewNode,
)


# =============================================================================
# DataLoadNode
# =============================================================================

class TestDataLoadNodePrep:
    """测试 DataLoadNode.prep"""

    def test_enhanced_type_returns_enhanced_path(self, minimal_shared):
        minimal_shared["config"]["data_source"]["type"] = "enhanced"
        minimal_shared["config"]["data_source"]["enhanced_data_path"] = "data/enh.json"
        node = DataLoadNode()
        result = node.prep(minimal_shared)
        assert result["load_type"] == "enhanced"
        assert result["data_path"] == "data/enh.json"

    def test_original_type_returns_all_paths(self, minimal_shared):
        minimal_shared["data"]["data_paths"] = {
            "blog_data_path": "data/posts.json",
            "topics_path": "data/topics.json",
            "sentiment_attributes_path": "data/sa.json",
            "publisher_objects_path": "data/po.json",
            "belief_system_path": "data/bs.json",
        }
        node = DataLoadNode()
        result = node.prep(minimal_shared)
        assert result["load_type"] == "original"
        assert result["blog_data_path"] == "data/posts.json"
        assert result["topics_path"] == "data/topics.json"

    def test_defaults_when_no_data_paths(self, minimal_shared):
        """缺少 data.data_paths 时使用默认值"""
        node = DataLoadNode()
        result = node.prep(minimal_shared)
        assert result["load_type"] == "original"
        assert "beijing_rainstorm" in result["blog_data_path"]


class TestDataLoadNodeExec:
    """测试 DataLoadNode.exec"""

    @patch("nodes.stage1.data_load.load_enhanced_blog_data")
    def test_enhanced_load(self, mock_load, sample_enhanced_data):
        mock_load.return_value = sample_enhanced_data
        node = DataLoadNode()
        result = node.exec({"load_type": "enhanced", "data_path": "data/enh.json"})
        assert result["load_type"] == "enhanced"
        assert result["blog_data"] == sample_enhanced_data
        mock_load.assert_called_once_with("data/enh.json")

    @patch("nodes.stage1.data_load.load_belief_system")
    @patch("nodes.stage1.data_load.load_publisher_objects")
    @patch("nodes.stage1.data_load.load_sentiment_attributes")
    @patch("nodes.stage1.data_load.load_topics")
    @patch("nodes.stage1.data_load.load_blog_data")
    def test_original_load(self, mock_blog, mock_topics, mock_sa, mock_po,
                           mock_bs,
                           sample_blog_data, sample_topics,
                           sample_sentiment_attrs, sample_publishers):
        mock_blog.return_value = sample_blog_data
        mock_topics.return_value = sample_topics
        mock_sa.return_value = sample_sentiment_attrs
        mock_po.return_value = sample_publishers
        mock_bs.return_value = [{"category": "test"}]

        node = DataLoadNode()
        prep_res = {
            "load_type": "original",
            "blog_data_path": "data/posts.json",
            "enhanced_data_path": "nonexistent.json",
            "resume_if_exists": True,
            "topics_path": "data/topics.json",
            "sentiment_attributes_path": "data/sa.json",
            "publisher_objects_path": "data/po.json",
            "belief_system_path": "data/bs.json",
        }
        result = node.exec(prep_res)
        assert result["load_type"] == "original"
        assert len(result["blog_data"]) == 3
        assert len(result["topics_hierarchy"]) == 3
        assert len(result["sentiment_attributes"]) == len(sample_sentiment_attrs)

    @patch("nodes.stage1.data_load.load_enhanced_blog_data")
    @patch("nodes.stage1.data_load.load_belief_system")
    @patch("nodes.stage1.data_load.load_publisher_objects")
    @patch("nodes.stage1.data_load.load_sentiment_attributes")
    @patch("nodes.stage1.data_load.load_topics")
    @patch("nodes.stage1.data_load.load_blog_data")
    @patch("os.path.exists", return_value=True)
    def test_resume_loads_enhanced_data(
        self, mock_exists, mock_blog, mock_topics, mock_sa, mock_po,
        mock_bs, mock_enh_load,
        sample_blog_data
    ):
        """断点续跑: 增强文件存在且匹配 → 使用增强数据"""
        enhanced = [dict(post, sentiment_polarity=3) for post in sample_blog_data]
        mock_blog.return_value = sample_blog_data
        mock_enh_load.return_value = enhanced
        mock_topics.return_value = []
        mock_sa.return_value = []
        mock_po.return_value = []
        mock_bs.return_value = []

        node = DataLoadNode()
        prep_res = {
            "load_type": "original",
            "blog_data_path": "data/posts.json",
            "enhanced_data_path": "data/enhanced.json",
            "resume_if_exists": True,
            "topics_path": "t.json",
            "sentiment_attributes_path": "sa.json",
            "publisher_objects_path": "po.json",
            "belief_system_path": "bs.json",
        }
        result = node.exec(prep_res)
        # 断点续跑成功时，blog_data 应包含 sentiment_polarity 字段
        assert result["blog_data"][0].get("sentiment_polarity") == 3


class TestDataLoadNodePost:
    """测试 DataLoadNode.post"""

    def test_stores_data_in_shared(self, minimal_shared, sample_blog_data):
        node = DataLoadNode()
        exec_res = {
            "blog_data": sample_blog_data,
            "load_type": "original",
            "topics_hierarchy": [{"parent_topic": "A", "sub_topics": ["B"]}],
            "sentiment_attributes": ["attr1"],
            "publisher_objects": ["pub1"],
            "belief_system": [{"category": "test"}],
        }
        action = node.post(minimal_shared, {}, exec_res)
        assert minimal_shared["data"]["blog_data"] == sample_blog_data
        assert minimal_shared["data"]["load_type"] == "original"
        assert minimal_shared["data"]["topics_hierarchy"] is not None
        assert minimal_shared["stage1_results"]["statistics"]["total_blogs"] == 3
        assert action == "default"

    def test_enhanced_load_stores_only_blog_data(self, minimal_shared, sample_enhanced_data):
        node = DataLoadNode()
        exec_res = {
            "blog_data": sample_enhanced_data,
            "load_type": "enhanced",
        }
        action = node.post(minimal_shared, {}, exec_res)
        assert minimal_shared["data"]["blog_data"] == sample_enhanced_data
        assert minimal_shared["data"]["load_type"] == "enhanced"
        assert action == "default"


# =============================================================================
# SaveEnhancedDataNode
# =============================================================================

class TestSaveEnhancedDataNode:
    def test_prep_extracts_data_and_path(self, minimal_shared, sample_enhanced_data):
        minimal_shared["data"]["blog_data"] = sample_enhanced_data
        node = SaveEnhancedDataNode()
        result = node.prep(minimal_shared)
        assert result["blog_data"] == sample_enhanced_data
        assert "enhanced" in result["output_path"]

    @patch("nodes.stage1.save.save_enhanced_blog_data", return_value=True)
    def test_exec_calls_save(self, mock_save, sample_enhanced_data):
        node = SaveEnhancedDataNode()
        result = node.exec({
            "blog_data": sample_enhanced_data,
            "output_path": "data/out.json",
        })
        assert result["success"] is True
        assert result["data_count"] == 3
        mock_save.assert_called_once_with(sample_enhanced_data, "data/out.json")

    def test_post_updates_save_status_on_success(self, minimal_shared):
        node = SaveEnhancedDataNode()
        exec_res = {"success": True, "output_path": "data/out.json", "data_count": 3}
        action = node.post(minimal_shared, {}, exec_res)
        assert minimal_shared["stage1_results"]["data_save"]["saved"] is True
        assert action == "default"

    def test_post_updates_save_status_on_failure(self, minimal_shared):
        node = SaveEnhancedDataNode()
        exec_res = {"success": False, "output_path": "data/out.json", "data_count": 0}
        action = node.post(minimal_shared, {}, exec_res)
        assert minimal_shared["stage1_results"]["data_save"]["saved"] is False
        assert action == "default"


# =============================================================================
# DataValidationAndOverviewNode
# =============================================================================

class TestDataValidationAndOverviewNode:
    def test_prep_returns_blog_data(self, minimal_shared, sample_enhanced_data):
        minimal_shared["data"]["blog_data"] = sample_enhanced_data
        node = DataValidationAndOverviewNode()
        result = node.prep(minimal_shared)
        assert len(result) == 3

    def test_exec_statistics(self, sample_enhanced_data):
        """验证统计计算的正确性"""
        node = DataValidationAndOverviewNode()
        stats = node.exec(sample_enhanced_data)
        assert stats["total_blogs"] == 3
        # 所有 3 条都有增强字段
        assert stats["processed_blogs"] == 3
        # 参与度统计
        eng = stats["engagement_statistics"]
        assert eng["total_reposts"] == 5 + 0 + 100  # 105
        assert eng["total_likes"] == 10 + 0 + 200  # 210
        # 用户统计
        user_stats = stats["user_statistics"]
        assert user_stats["unique_users"] == 3
        # 地理分布
        assert "北京" in stats["geographic_distribution"]
        assert stats["geographic_distribution"]["北京"] == 2
        # 空字段统计 — 全部有值
        assert stats["empty_fields"]["sentiment_polarity_empty"] == 0
        assert stats["empty_fields"]["topics_empty"] == 0

    def test_exec_empty_fields_counted(self, sample_blog_data):
        """原始数据(无增强字段)统计空字段"""
        node = DataValidationAndOverviewNode()
        stats = node.exec(sample_blog_data)
        assert stats["empty_fields"]["sentiment_polarity_empty"] == 3
        assert stats["empty_fields"]["topics_empty"] == 3
        assert stats["empty_fields"]["publisher_empty"] == 3
        assert stats["processed_blogs"] == 0
