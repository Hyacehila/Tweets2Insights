"""
test_stage1_analysis.py — Stage 1 五维分析节点单元测试

测试异步批量分析节点的核心方法:
  - exec_async: Prompt 构建与 LLM 响应解析
  - exec_fallback_async: 异常情况的安全默认值
  - apply_item_result: 结果写回 blog_post
  - post_async: 批量结果合并到 shared
"""
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from nodes import (
    AsyncSentimentPolarityAnalysisBatchNode,
    AsyncSentimentAttributeAnalysisBatchNode,
    AsyncTwoLevelTopicAnalysisBatchNode,
    AsyncPublisherObjectAnalysisBatchNode,
    AsyncBeliefSystemAnalysisBatchNode,
)


# =============================================================================
# 辅助函数
# =============================================================================

def run_async(coro):
    """在同步测试中运行协程"""
    return asyncio.run(coro)


# =============================================================================
# AsyncSentimentPolarityAnalysisBatchNode
# =============================================================================

class TestSentimentPolarityNode:

    def test_apply_item_result(self, sample_blog_data):
        """结果立即写回 blog_post 的 sentiment_polarity 字段"""
        node = AsyncSentimentPolarityAnalysisBatchNode()
        post = sample_blog_data[0]
        node.apply_item_result(post, 4)
        assert post["sentiment_polarity"] == 4

    @patch("nodes.stage1.sentiment.call_glm_45_air", return_value="3")
    def test_exec_async_text_only(self, mock_llm, sample_blog_data):
        """无图博文 → 调用 call_glm_45_air"""
        node = AsyncSentimentPolarityAnalysisBatchNode()
        # 确保博文的 image_urls 为空
        post = dict(sample_blog_data[1])  # user B, 无图
        post.pop("sentiment_polarity", None)
        result = run_async(node.exec_async(post))
        assert result == 3
        mock_llm.assert_called_once()

    @patch("nodes.stage1.sentiment.call_glm4v_plus", return_value="5")
    def test_exec_async_with_images(self, mock_llm, sample_blog_data):
        """带图博文 → 调用 call_glm4v_plus"""
        node = AsyncSentimentPolarityAnalysisBatchNode()
        post = dict(sample_blog_data[0])  # user A, 有图
        post.pop("sentiment_polarity", None)
        result = run_async(node.exec_async(post))
        assert result == 5
        mock_llm.assert_called_once()

    @patch("nodes.stage1.sentiment.call_glm_45_air", return_value="abc")
    def test_exec_async_non_numeric_raises(self, mock_llm, sample_blog_data):
        """LLM 返回非数字 → 抛异常"""
        node = AsyncSentimentPolarityAnalysisBatchNode()
        post = dict(sample_blog_data[1])
        post.pop("sentiment_polarity", None)
        with pytest.raises(ValueError, match="不是数字"):
            run_async(node.exec_async(post))

    @patch("nodes.stage1.sentiment.call_glm_45_air", return_value="7")
    def test_exec_async_out_of_range_raises(self, mock_llm, sample_blog_data):
        """LLM 返回范围外数字 → 抛异常"""
        node = AsyncSentimentPolarityAnalysisBatchNode()
        post = dict(sample_blog_data[1])
        post.pop("sentiment_polarity", None)
        with pytest.raises(ValueError, match="不在1-5范围"):
            run_async(node.exec_async(post))

    def test_exec_async_skip_existing(self, sample_enhanced_data):
        """已有 sentiment_polarity 的博文 → 跳过，返回现有值"""
        node = AsyncSentimentPolarityAnalysisBatchNode()
        post = sample_enhanced_data[0]  # 已有 polarity=5
        result = run_async(node.exec_async(post))
        assert result == 5

    def test_fallback_returns_neutral(self, sample_blog_data):
        """异常时 fallback 返回中性值 3"""
        node = AsyncSentimentPolarityAnalysisBatchNode()
        result = run_async(
            node.exec_fallback_async(sample_blog_data[0], Exception("test"))
        )
        assert result == 3

    def test_post_async_writes_results(self, minimal_shared, sample_blog_data):
        """post_async 将结果批量写入 blog_data"""
        minimal_shared["data"]["blog_data"] = sample_blog_data
        node = AsyncSentimentPolarityAnalysisBatchNode()
        exec_res = [4, 2, 3]  # 3条博文的结果
        action = run_async(node.post_async(minimal_shared, sample_blog_data, exec_res))
        assert sample_blog_data[0]["sentiment_polarity"] == 4
        assert sample_blog_data[1]["sentiment_polarity"] == 2
        assert sample_blog_data[2]["sentiment_polarity"] == 3
        assert action == "default"


# =============================================================================
# AsyncSentimentAttributeAnalysisBatchNode
# =============================================================================

class TestSentimentAttributeNode:

    def test_apply_item_result(self, sample_blog_data):
        """结果写回嵌套 item['blog_data'] 的 sentiment_attribute 字段"""
        node = AsyncSentimentAttributeAnalysisBatchNode()
        post = sample_blog_data[0]
        item = {"blog_data": post}
        node.apply_item_result(item, ["担忧", "恐惧"])
        assert post["sentiment_attribute"] == ["担忧", "恐惧"]

    def test_fallback_returns_neutral(self, sample_blog_data):
        node = AsyncSentimentAttributeAnalysisBatchNode()
        result = run_async(
            node.exec_fallback_async(sample_blog_data[0], Exception("test"))
        )
        assert isinstance(result, list)
        assert len(result) > 0  # 至少一个默认属性


# =============================================================================
# AsyncTwoLevelTopicAnalysisBatchNode
# =============================================================================

class TestTwoLevelTopicNode:

    def test_apply_item_result(self, sample_blog_data):
        node = AsyncTwoLevelTopicAnalysisBatchNode()
        post = sample_blog_data[0]
        item = {"blog_data": post}
        topics = [{"parent_topic": "社会民生", "sub_topic": "居民生活"}]
        node.apply_item_result(item, topics)
        assert post["topics"] == topics

    def test_fallback_returns_empty_list(self, sample_blog_data):
        node = AsyncTwoLevelTopicAnalysisBatchNode()
        result = run_async(
            node.exec_fallback_async(sample_blog_data[0], Exception("test"))
        )
        assert result == []


# =============================================================================
# AsyncPublisherObjectAnalysisBatchNode
# =============================================================================

class TestPublisherObjectNode:

    def test_apply_item_result(self, sample_blog_data):
        node = AsyncPublisherObjectAnalysisBatchNode()
        post = sample_blog_data[0]
        item = {"blog_data": post}
        node.apply_item_result(item, "官方媒体")
        assert post["publisher"] == "官方媒体"

    def test_fallback_returns_default(self, sample_blog_data):
        node = AsyncPublisherObjectAnalysisBatchNode()
        result = run_async(
            node.exec_fallback_async(sample_blog_data[0], Exception("test"))
        )
        assert isinstance(result, str)
        assert len(result) > 0


# =============================================================================
# AsyncBeliefSystemAnalysisBatchNode
# =============================================================================

class TestBeliefSystemNode:

    def test_apply_item_result(self, sample_blog_data):
        node = AsyncBeliefSystemAnalysisBatchNode()
        post = sample_blog_data[0]
        item = {"blog_data": post}
        signals = [{"category": "风险感知类", "subcategories": ["担心公共安全"]}]
        node.apply_item_result(item, signals)
        assert post["belief_signals"] == signals

    def test_fallback_returns_empty(self, sample_blog_data):
        node = AsyncBeliefSystemAnalysisBatchNode()
        result = run_async(
            node.exec_fallback_async(sample_blog_data[0], Exception("test"))
        )
        assert result == []
