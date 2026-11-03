"""
舆情分析智能体 - MCP服务器
提供所有分析工具的MCP接口
"""

from fastmcp import FastMCP
import sys
import os
from typing import Dict, Any, List

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.analysis_tools import (
    # 情感工具
    sentiment_distribution_stats as _sentiment_distribution_stats,
    sentiment_time_series as _sentiment_time_series,
    sentiment_anomaly_detection as _sentiment_anomaly_detection,
    sentiment_trend_chart as _sentiment_trend_chart,
    sentiment_pie_chart as _sentiment_pie_chart,
    sentiment_bucket_trend_chart as _sentiment_bucket_trend_chart,
    sentiment_attribute_trend_chart as _sentiment_attribute_trend_chart,
    sentiment_focus_window_chart as _sentiment_focus_window_chart,
    sentiment_focus_publisher_chart as _sentiment_focus_publisher_chart,
    # 主题工具
    topic_frequency_stats as _topic_frequency_stats,
    topic_time_evolution as _topic_time_evolution,
    topic_cooccurrence_analysis as _topic_cooccurrence_analysis,
    topic_ranking_chart as _topic_ranking_chart,
    topic_evolution_chart as _topic_evolution_chart,
    topic_network_chart as _topic_network_chart,
    topic_focus_evolution_chart as _topic_focus_evolution_chart,
    topic_keyword_trend_chart as _topic_keyword_trend_chart,
    topic_focus_distribution_chart as _topic_focus_distribution_chart,
    # 地理工具
    geographic_distribution_stats as _geographic_distribution_stats,
    geographic_hotspot_detection as _geographic_hotspot_detection,
    geographic_sentiment_analysis as _geographic_sentiment_analysis,
    geographic_heatmap as _geographic_heatmap,
    geographic_bar_chart as _geographic_bar_chart,
    geographic_sentiment_bar_chart as _geographic_sentiment_bar_chart,
    geographic_topic_heatmap as _geographic_topic_heatmap,
    geographic_temporal_heatmap as _geographic_temporal_heatmap,
    # 交互工具
    publisher_distribution_stats as _publisher_distribution_stats,
    cross_dimension_matrix as _cross_dimension_matrix,
    influence_analysis as _influence_analysis,
    correlation_analysis as _correlation_analysis,
    interaction_heatmap as _interaction_heatmap,
    publisher_bar_chart as _publisher_bar_chart,
    publisher_sentiment_bucket_chart as _publisher_sentiment_bucket_chart,
    publisher_topic_distribution_chart as _publisher_topic_distribution_chart,
    participant_trend_chart as _participant_trend_chart,
    publisher_focus_distribution_chart as _publisher_focus_distribution_chart,
    belief_network_chart as _belief_network_chart,
    # NLP工具
    keyword_wordcloud as _keyword_wordcloud,
    entity_cooccurrence_network as _entity_cooccurrence_network,
    text_cluster_analysis as _text_cluster_analysis,
    sentiment_lexicon_comparison as _sentiment_lexicon_comparison,
    temporal_keyword_heatmap as _temporal_keyword_heatmap,
)
from utils.data_loader import load_enhanced_blog_data

# 创建MCP服务器
mcp = FastMCP("Opinion Analysis Server")

from utils.path_manager import current_run_context, get_images_dir


def get_blog_data():
    """Resolve an explicit run dataset, or read a fresh legacy subprocess snapshot."""
    context = current_run_context()
    if context:
        repo, event_id, dataset_id, _ = context
        return repo.read(event_id, dataset_id)
    path = os.getenv("ENHANCED_DATA_PATH")
    if not path:
        raise ValueError("ENHANCED_DATA_PATH is required in legacy subprocess mode")
    return load_enhanced_blog_data(path)

# =============================================================================
# Canonical tool names (tool_registry)
# =============================================================================

# 情感分析（canonical）
@mcp.tool()
def sentiment_distribution_stats() -> Dict[str, Any]:
    """情感分布统计（canonical）"""
    blog_data = get_blog_data()
    return _sentiment_distribution_stats(blog_data)


@mcp.tool()
def sentiment_time_series(granularity: str = "hour") -> Dict[str, Any]:
    """情感时序统计（canonical）"""
    blog_data = get_blog_data()
    return _sentiment_time_series(blog_data, granularity=granularity)


@mcp.tool()
def sentiment_anomaly_detection(threshold: float = 2.0) -> Dict[str, Any]:
    """情感异常检测（canonical）"""
    blog_data = get_blog_data()
    return _sentiment_anomaly_detection(blog_data, threshold=threshold)


@mcp.tool()
def sentiment_trend_chart() -> Dict[str, Any]:
    """情感趋势图（canonical）"""
    blog_data = get_blog_data()
    return _sentiment_trend_chart(blog_data, output_dir=get_images_dir())


@mcp.tool()
def sentiment_pie_chart() -> Dict[str, Any]:
    """情感饼图（canonical）"""
    blog_data = get_blog_data()
    return _sentiment_pie_chart(blog_data, output_dir=get_images_dir())


@mcp.tool()
def sentiment_bucket_trend_chart(granularity: str = "day") -> Dict[str, Any]:
    """情绪桶趋势图（canonical）"""
    blog_data = get_blog_data()
    return _sentiment_bucket_trend_chart(blog_data, output_dir=get_images_dir(), granularity=granularity)


@mcp.tool()
def sentiment_attribute_trend_chart(granularity: str = "day", top_n: int = 6) -> Dict[str, Any]:
    """情感属性趋势图（canonical）"""
    blog_data = get_blog_data()
    return _sentiment_attribute_trend_chart(
        blog_data, output_dir=get_images_dir(), granularity=granularity, top_n=top_n
    )


@mcp.tool()
def sentiment_focus_window_chart(window_days: int = 14) -> Dict[str, Any]:
    """焦点窗口情感趋势图（canonical）"""
    blog_data = get_blog_data()
    return _sentiment_focus_window_chart(blog_data, output_dir=get_images_dir(), window_days=window_days)


@mcp.tool()
def sentiment_focus_publisher_chart(window_days: int = 14, top_n: int = 5) -> Dict[str, Any]:
    """焦点窗口发布者情感趋势图（canonical）"""
    blog_data = get_blog_data()
    return _sentiment_focus_publisher_chart(
        blog_data, output_dir=get_images_dir(), window_days=window_days, top_n=top_n
    )

# 主题分析（canonical）
@mcp.tool()
def topic_frequency_stats() -> Dict[str, Any]:
    """主题频次统计（canonical）"""
    blog_data = get_blog_data()
    return _topic_frequency_stats(blog_data)


@mcp.tool()
def topic_time_evolution(granularity: str = "day", top_n: int = 5) -> Dict[str, Any]:
    """主题时间演化（canonical）"""
    blog_data = get_blog_data()
    return _topic_time_evolution(blog_data, granularity=granularity, top_n=top_n)


@mcp.tool()
def topic_cooccurrence_analysis(min_support: int = 2) -> Dict[str, Any]:
    """主题共现分析（canonical）"""
    blog_data = get_blog_data()
    return _topic_cooccurrence_analysis(blog_data, min_support=min_support)


@mcp.tool()
def topic_ranking_chart(top_n: int = 10) -> Dict[str, Any]:
    """主题排行图（canonical）"""
    blog_data = get_blog_data()
    return _topic_ranking_chart(blog_data, top_n=top_n)


@mcp.tool()
def topic_evolution_chart() -> Dict[str, Any]:
    """主题演化图（canonical）"""
    blog_data = get_blog_data()
    return _topic_evolution_chart(blog_data)


@mcp.tool()
def topic_network_chart() -> Dict[str, Any]:
    """主题网络图（canonical）"""
    blog_data = get_blog_data()
    return _topic_network_chart(blog_data)


@mcp.tool()
def topic_focus_evolution_chart() -> Dict[str, Any]:
    """焦点窗口主题演化（canonical）"""
    blog_data = get_blog_data()
    return _topic_focus_evolution_chart(blog_data, output_dir=get_images_dir())


@mcp.tool()
def topic_keyword_trend_chart() -> Dict[str, Any]:
    """主题关键词趋势（canonical）"""
    blog_data = get_blog_data()
    return _topic_keyword_trend_chart(blog_data, output_dir=get_images_dir())


@mcp.tool()
def topic_focus_distribution_chart(window_days: int = 14, top_n: int = 5) -> Dict[str, Any]:
    """焦点窗口主题分布（canonical）"""
    blog_data = get_blog_data()
    return _topic_focus_distribution_chart(
        blog_data, output_dir=get_images_dir(), window_days=window_days, top_n=top_n
    )

# 地理分析（canonical）
@mcp.tool()
def geographic_distribution_stats() -> Dict[str, Any]:
    """地理分布统计（canonical）"""
    blog_data = get_blog_data()
    return _geographic_distribution_stats(blog_data)


@mcp.tool()
def geographic_hotspot_detection(threshold_percentile: float = 90) -> Dict[str, Any]:
    """地理热点检测（canonical）"""
    blog_data = get_blog_data()
    return _geographic_hotspot_detection(blog_data, threshold_percentile=threshold_percentile)


@mcp.tool()
def geographic_sentiment_analysis(min_posts: int = 5) -> Dict[str, Any]:
    """地理情感分析（canonical）"""
    blog_data = get_blog_data()
    return _geographic_sentiment_analysis(blog_data, min_posts=min_posts)


@mcp.tool()
def geographic_heatmap() -> Dict[str, Any]:
    """地理热力图（canonical）"""
    blog_data = get_blog_data()
    return _geographic_heatmap(blog_data, output_dir=get_images_dir())


@mcp.tool()
def geographic_bar_chart() -> Dict[str, Any]:
    """地理柱状图（canonical）"""
    blog_data = get_blog_data()
    return _geographic_bar_chart(blog_data, output_dir=get_images_dir())


@mcp.tool()
def geographic_sentiment_bar_chart(top_n: int = 12) -> Dict[str, Any]:
    """地区情感柱状图（canonical）"""
    blog_data = get_blog_data()
    return _geographic_sentiment_bar_chart(blog_data, output_dir=get_images_dir(), top_n=top_n)


@mcp.tool()
def geographic_topic_heatmap(top_regions: int = 10, top_topics: int = 8) -> Dict[str, Any]:
    """地区×主题热力图（canonical）"""
    blog_data = get_blog_data()
    return _geographic_topic_heatmap(
        blog_data, output_dir=get_images_dir(), top_regions=top_regions, top_topics=top_topics
    )


@mcp.tool()
def geographic_temporal_heatmap(granularity: str = "day", top_regions: int = 8) -> Dict[str, Any]:
    """地区×时间热力图（canonical）"""
    blog_data = get_blog_data()
    return _geographic_temporal_heatmap(
        blog_data, output_dir=get_images_dir(), granularity=granularity, top_regions=top_regions
    )

# 交互分析（canonical）
@mcp.tool()
def publisher_distribution_stats() -> Dict[str, Any]:
    """发布者分布统计（canonical）"""
    blog_data = get_blog_data()
    return _publisher_distribution_stats(blog_data)


@mcp.tool()
def cross_dimension_matrix(dim1: str = "publisher", dim2: str = "sentiment_polarity") -> Dict[str, Any]:
    """交叉维度矩阵（canonical）"""
    blog_data = get_blog_data()
    return _cross_dimension_matrix(blog_data, dim1=dim1, dim2=dim2)


@mcp.tool()
def influence_analysis(top_n: int = 20) -> Dict[str, Any]:
    """影响力分析（canonical）"""
    blog_data = get_blog_data()
    return _influence_analysis(blog_data, top_n=top_n)


@mcp.tool()
def correlation_analysis() -> Dict[str, Any]:
    """相关性分析（canonical）"""
    blog_data = get_blog_data()
    return _correlation_analysis(blog_data)


@mcp.tool()
def interaction_heatmap() -> Dict[str, Any]:
    """交互热力图（canonical）"""
    blog_data = get_blog_data()
    return _interaction_heatmap(blog_data, output_dir=get_images_dir())


@mcp.tool()
def publisher_bar_chart() -> Dict[str, Any]:
    """发布者柱状图（canonical）"""
    blog_data = get_blog_data()
    return _publisher_bar_chart(blog_data, output_dir=get_images_dir())


@mcp.tool()
def publisher_sentiment_bucket_chart(top_n: int = 10) -> Dict[str, Any]:
    """发布者情绪桶（canonical）"""
    blog_data = get_blog_data()
    return _publisher_sentiment_bucket_chart(blog_data, output_dir=get_images_dir(), top_n=top_n)


@mcp.tool()
def publisher_topic_distribution_chart(top_publishers: int = 8, top_topics: int = 8) -> Dict[str, Any]:
    """发布者×主题分布（canonical）"""
    blog_data = get_blog_data()
    return _publisher_topic_distribution_chart(
        blog_data, output_dir=get_images_dir(), top_publishers=top_publishers, top_topics=top_topics
    )


@mcp.tool()
def participant_trend_chart(granularity: str = "day") -> Dict[str, Any]:
    """参与趋势（canonical）"""
    blog_data = get_blog_data()
    return _participant_trend_chart(blog_data, output_dir=get_images_dir(), granularity=granularity)


@mcp.tool()
def publisher_focus_distribution_chart(window_days: int = 14, top_n: int = 5) -> Dict[str, Any]:
    """焦点窗口发布者分布（canonical）"""
    blog_data = get_blog_data()
    return _publisher_focus_distribution_chart(
        blog_data, output_dir=get_images_dir(), window_days=window_days, top_n=top_n
    )


@mcp.tool()
def belief_network_chart(event_name: str = "belief_network") -> Dict[str, Any]:
    """信念系统网络图（canonical）"""
    blog_data = get_blog_data()
    return _belief_network_chart(
        blog_data, output_dir=get_images_dir(), data_dir="report", event_name=event_name
    )

# NLP 工具（canonical）
@mcp.tool()
def keyword_wordcloud(top_n: int = 30) -> Dict[str, Any]:
    """关键词频次图（canonical）"""
    blog_data = get_blog_data()
    return _keyword_wordcloud(blog_data, output_dir=get_images_dir(), top_n=top_n)


@mcp.tool()
def entity_cooccurrence_network(top_n: int = 15) -> Dict[str, Any]:
    """实体共现网络（canonical）"""
    blog_data = get_blog_data()
    return _entity_cooccurrence_network(blog_data, output_dir=get_images_dir(), top_n=top_n)


@mcp.tool()
def text_cluster_analysis(threshold: float = 0.85, min_cluster_size: int = 2) -> Dict[str, Any]:
    """文本聚类分析（canonical）"""
    blog_data = get_blog_data()
    return _text_cluster_analysis(
        blog_data, output_dir=get_images_dir(), threshold=threshold, min_cluster_size=min_cluster_size
    )


@mcp.tool()
def sentiment_lexicon_comparison() -> Dict[str, Any]:
    """词典情感分布（canonical）"""
    blog_data = get_blog_data()
    return _sentiment_lexicon_comparison(blog_data, output_dir=get_images_dir())


@mcp.tool()
def temporal_keyword_heatmap(top_n: int = 10, granularity: str = "day") -> Dict[str, Any]:
    """关键词时间热力图（canonical）"""
    blog_data = get_blog_data()
    return _temporal_keyword_heatmap(
        blog_data, output_dir=get_images_dir(), top_n=top_n, granularity=granularity
    )

# =============================================================================
# 情感分析工具
# =============================================================================

@mcp.tool()
def sentiment_distribution() -> Dict[str, Any]:
    """获取情感分布统计数据"""
    blog_data = get_blog_data()
    result = _sentiment_distribution_stats(blog_data)
    return result

@mcp.tool()
def sentiment_timeseries() -> Dict[str, Any]:
    """获取情感时序趋势数据"""
    blog_data = get_blog_data()
    result = _sentiment_time_series(blog_data, granularity="hour")
    return result

@mcp.tool()
def sentiment_anomaly() -> Dict[str, Any]:
    """获取情感异常点检测数据"""
    blog_data = get_blog_data()
    result = _sentiment_anomaly_detection(blog_data)
    return result


# =============================================================================
# 主题分析工具
# =============================================================================

@mcp.tool()
def topic_frequency() -> Dict[str, Any]:
    """获取主题频次统计数据"""
    blog_data = get_blog_data()
    result = _topic_frequency_stats(blog_data)
    return result

@mcp.tool()
def topic_evolution() -> Dict[str, Any]:
    """获取主题演化数据"""
    blog_data = get_blog_data()
    result = _topic_time_evolution(blog_data, granularity="day", top_n=5)
    return result

@mcp.tool()
def topic_cooccurrence() -> Dict[str, Any]:
    """获取主题共现关系数据"""
    blog_data = get_blog_data()
    result = _topic_cooccurrence_analysis(blog_data)
    return result

@mcp.tool()
def topic_focus_evolution() -> Dict[str, Any]:
    """获取带焦点窗口高亮的主题演化数据"""
    blog_data = get_blog_data()
    result = _topic_focus_evolution_chart(blog_data, output_dir=get_images_dir())
    return result

@mcp.tool()
def topic_keyword_trend() -> Dict[str, Any]:
    """获取焦点关键词热度趋势数据"""
    blog_data = get_blog_data()
    result = _topic_keyword_trend_chart(blog_data, output_dir=get_images_dir())
    return result

@mcp.tool()
def topic_focus_distribution(window_days: int = 14, top_n: int = 5) -> Dict[str, Any]:
    """获取焦点窗口主题分布趋势（仅窗口数据）"""
    blog_data = get_blog_data()
    result = _topic_focus_distribution_chart(
        blog_data, output_dir=get_images_dir(), window_days=window_days, top_n=top_n
    )
    return result


# =============================================================================
# 地理分析工具
# =============================================================================

@mcp.tool()
def geographic_distribution() -> Dict[str, Any]:
    """获取地理分布统计数据"""
    blog_data = get_blog_data()
    result = _geographic_distribution_stats(blog_data)
    return result

@mcp.tool()
def geographic_hotspot() -> Dict[str, Any]:
    """获取地理热点区域数据"""
    blog_data = get_blog_data()
    result = _geographic_hotspot_detection(blog_data)
    return result

@mcp.tool()
def geographic_sentiment() -> Dict[str, Any]:
    """获取地区情感分析数据"""
    blog_data = get_blog_data()
    result = _geographic_sentiment_analysis(blog_data)
    return result

@mcp.tool()
def geographic_sentiment_bar(top_n: int = 12) -> Dict[str, Any]:
    """生成地区情感对比条形图"""
    blog_data = get_blog_data()
    result = _geographic_sentiment_bar_chart(blog_data, output_dir=get_images_dir(), top_n=top_n)
    return result

@mcp.tool()
def geographic_topic_heatmap_tool(top_regions: int = 10, top_topics: int = 8) -> Dict[str, Any]:
    """生成地区×主题热力图"""
    blog_data = get_blog_data()
    result = _geographic_topic_heatmap(
        blog_data, output_dir=get_images_dir(), top_regions=top_regions, top_topics=top_topics
    )
    return result

@mcp.tool()
def geographic_temporal_heatmap_tool(granularity: str = "day", top_regions: int = 8) -> Dict[str, Any]:
    """生成地区×时间热力图"""
    blog_data = get_blog_data()
    result = _geographic_temporal_heatmap(
        blog_data, output_dir=get_images_dir(), granularity=granularity, top_regions=top_regions
    )
    return result


# =============================================================================
# 多维交互分析工具
# =============================================================================

@mcp.tool()
def publisher_distribution() -> Dict[str, Any]:
    """获取发布者分布统计数据"""
    blog_data = get_blog_data()
    result = _publisher_distribution_stats(blog_data)
    return result

@mcp.tool()
def cross_matrix(dim1: str = "publisher", dim2: str = "sentiment_polarity") -> Dict[str, Any]:
    """获取交叉维度分析数据"""
    blog_data = get_blog_data()
    result = _cross_dimension_matrix(blog_data, dim1=dim1, dim2=dim2)
    return result


@mcp.tool()
def publisher_sentiment_bucket(top_n: int = 10) -> Dict[str, Any]:
    """生成发布者维度正/中/负情绪桶堆叠图"""
    blog_data = get_blog_data()
    result = _publisher_sentiment_bucket_chart(blog_data, output_dir=get_images_dir(), top_n=top_n)
    return result

@mcp.tool()
def publisher_topic_distribution(top_publishers: int = 8, top_topics: int = 8) -> Dict[str, Any]:
    """生成发布者×主题分布堆叠图"""
    blog_data = get_blog_data()
    result = _publisher_topic_distribution_chart(
        blog_data, output_dir=get_images_dir(), top_publishers=top_publishers, top_topics=top_topics
    )
    return result

@mcp.tool()
def participant_trend(granularity: str = "day") -> Dict[str, Any]:
    """生成新增/累计参与用户趋势"""
    blog_data = get_blog_data()
    result = _participant_trend_chart(blog_data, output_dir=get_images_dir(), granularity=granularity)
    return result

@mcp.tool()
def publisher_focus_distribution(window_days: int = 14, top_n: int = 5) -> Dict[str, Any]:
    """生成焦点窗口发布者类型发布趋势"""
    blog_data = get_blog_data()
    result = _publisher_focus_distribution_chart(
        blog_data, output_dir=get_images_dir(), window_days=window_days, top_n=top_n
    )
    return result


# =============================================================================
# 情感图表扩展
# =============================================================================

@mcp.tool()
def generate_sentiment_bucket_trend_chart(granularity: str = "day") -> Dict[str, Any]:
    """生成正中负情绪桶堆叠趋势图"""
    blog_data = get_blog_data()
    result = _sentiment_bucket_trend_chart(blog_data, output_dir=get_images_dir(), granularity=granularity)
    return result

@mcp.tool()
def generate_sentiment_attribute_trend_chart(granularity: str = "day", top_n: int = 6) -> Dict[str, Any]:
    """生成情感属性热度趋势图"""
    blog_data = get_blog_data()
    result = _sentiment_attribute_trend_chart(
        blog_data, output_dir=get_images_dir(), granularity=granularity, top_n=top_n
    )
    return result

@mcp.tool()
def generate_sentiment_focus_window_chart(window_days: int = 14) -> Dict[str, Any]:
    """生成焦点窗口情感趋势图（独立窗口数据）"""
    blog_data = get_blog_data()
    result = _sentiment_focus_window_chart(blog_data, output_dir=get_images_dir(), window_days=window_days)
    return result

@mcp.tool()
def generate_sentiment_focus_publisher_chart(window_days: int = 14, top_n: int = 5) -> Dict[str, Any]:
    """生成焦点窗口 TopN 发布者情感趋势图"""
    blog_data = get_blog_data()
    result = _sentiment_focus_publisher_chart(
        blog_data, output_dir=get_images_dir(), window_days=window_days, top_n=top_n
    )
    return result


# =============================================================================
# 图表生成工具
# =============================================================================

@mcp.tool()
def generate_sentiment_trend_chart() -> Dict[str, Any]:
    """生成情感趋势折线图/面积图"""
    blog_data = get_blog_data()
    result = _sentiment_trend_chart(blog_data, output_dir=get_images_dir())
    return result

@mcp.tool()
def generate_sentiment_pie_chart() -> Dict[str, Any]:
    """生成情感分布饼图"""
    blog_data = get_blog_data()
    result = _sentiment_pie_chart(blog_data, output_dir=get_images_dir())
    return result

@mcp.tool()
def generate_topic_ranking_chart(top_n: int = 10) -> Dict[str, Any]:
    """生成主题排行柱状图"""
    blog_data = get_blog_data()
    result = _topic_ranking_chart(blog_data, top_n=top_n)
    return result

@mcp.tool()
def generate_topic_evolution_chart() -> Dict[str, Any]:
    """生成主题演化图"""
    blog_data = get_blog_data()
    result = _topic_evolution_chart(blog_data)
    return result

@mcp.tool()
def generate_topic_network_chart() -> Dict[str, Any]:
    """生成主题关系网络图"""
    blog_data = get_blog_data()
    result = _topic_network_chart(blog_data)
    return result

@mcp.tool()
def generate_geographic_heatmap() -> Dict[str, Any]:
    """生成地理分布热力图"""
    blog_data = get_blog_data()
    result = _geographic_heatmap(blog_data, output_dir=get_images_dir())
    return result

@mcp.tool()
def generate_geographic_bar_chart() -> Dict[str, Any]:
    """生成地区分布柱状图"""
    blog_data = get_blog_data()
    result = _geographic_bar_chart(blog_data, output_dir=get_images_dir())
    return result

@mcp.tool()
def generate_interaction_heatmap() -> Dict[str, Any]:
    """生成多维交互热力图"""
    blog_data = get_blog_data()
    result = _interaction_heatmap(blog_data, output_dir=get_images_dir())
    return result

@mcp.tool()
def generate_publisher_bar_chart() -> Dict[str, Any]:
    """生成发布者分布柱状图"""
    blog_data = get_blog_data()
    result = _publisher_bar_chart(blog_data, output_dir=get_images_dir())
    return result

# 启动服务器
if __name__ == "__main__":
    mcp.run()
