"""
nodes/ 包 — 向后兼容导出层

保证 ``from nodes import XXX`` 和 ``@patch("nodes.XXX")`` 路径
与拆分前完全一致。所有公开符号在此统一注册。
"""

# ── 工具函数 & 常量 ──────────────────────────────────────────
from nodes._utils import (
    normalize_path,
    get_project_relative_path,
    ensure_dir_exists,
    _strip_timestamp_suffix,
    _build_chart_path_index,
    _MANUAL_IMAGE_ALIAS,
    _remap_report_images,
    _load_analysis_charts,
)

# ── 基类 ──────────────────────────────────────────────────────
from nodes.base import AsyncParallelBatchNode

# ── 管线状态节点 ──────────────────────────────────────────────
from nodes.pipeline_state import (
    TerminalNode,
    Stage1CompletionNode,
    Stage2CompletionNode,
    Stage3CompletionNode,
)

# ── 阶段1：数据增强 ──────────────────────────────────────────
from nodes.stage1 import (
    DataLoadNode,
    SaveEnhancedDataNode,
    DataValidationAndOverviewNode,
    NLPEnrichmentNode,
    AsyncSentimentPolarityAnalysisBatchNode,
    AsyncSentimentAttributeAnalysisBatchNode,
    AsyncTwoLevelTopicAnalysisBatchNode,
    AsyncPublisherObjectAnalysisBatchNode,
    AsyncBeliefSystemAnalysisBatchNode,
)

# ── 阶段2：分析执行 ──────────────────────────────────────────
from nodes.stage2 import (
    LoadEnhancedDataNode,
    DataSummaryNode,
    ClearReportDirNode,
    SaveAnalysisResultsNode,
    ChartAnalysisNode,
    LLMInsightNode,
    CollectToolsNode,
    DecisionToolsNode,
    ExecuteToolsNode,
    ProcessResultNode,
    EnsureChartsNode,
    ExtractQueriesNode,
    WebSearchNode,
    SearchProcessNode,
    SearchReflectionNode,
    SearchSummaryNode,
    create_query_search_flow,
    SearchAgentNode,
    RunParallelAgentBranchNode,
    ParallelAgentFlow,
    create_parallel_agent_flow,
    AssembleStage2ResultsNode,
    ForumHostNode,
    SupplementDataNode,
    SupplementSearchNode,
    VisualAnalysisNode,
    MergeResultsNode,
)

# ── 阶段3：报告生成 ──────────────────────────────────────────
from nodes.stage3 import (
    LoadAnalysisResultsNode,
    PlanOutlineNode,
    GenerateChaptersBatchNode,
    ReviewChaptersNode,
    IRRendererNode,
    InjectTraceNode,
    MethodologyAppendixNode,
    FormatReportNode,
    RenderHTMLNode,
    SaveReportNode,
    ClearStage3OutputsNode,
)

# ── 让 @patch("nodes.xxx") 能找到被 mock 的底层依赖 ─────────
# 测试中有 @patch("nodes.call_glm_45_air") 等写法，
# 需要在 nodes 名称空间中保留这些名称。
from utils.call_llm import call_glm_45_air, call_glm4v_plus
from utils.data_loader import (
    load_blog_data, load_topics, load_sentiment_attributes,
    load_publisher_objects, save_enhanced_blog_data, load_enhanced_blog_data,
    load_belief_system,
)
import os

# 让 @patch("nodes.call_glm46") 等也能找到
try:
    from utils.call_llm import call_glm46, call_glm45v_thinking
except ImportError:
    pass

__all__ = [
    # _utils
    "normalize_path", "get_project_relative_path", "ensure_dir_exists",
    "_strip_timestamp_suffix", "_build_chart_path_index",
    "_MANUAL_IMAGE_ALIAS", "_remap_report_images", "_load_analysis_charts",
    # base
    "AsyncParallelBatchNode",
    # pipeline state
    "TerminalNode",
    "Stage1CompletionNode", "Stage2CompletionNode", "Stage3CompletionNode",
    # stage1
    "DataLoadNode", "SaveEnhancedDataNode", "DataValidationAndOverviewNode",
    "NLPEnrichmentNode",
    "AsyncSentimentPolarityAnalysisBatchNode",
    "AsyncSentimentAttributeAnalysisBatchNode",
    "AsyncTwoLevelTopicAnalysisBatchNode",
    "AsyncPublisherObjectAnalysisBatchNode",
    "AsyncBeliefSystemAnalysisBatchNode",
    # stage2
    "LoadEnhancedDataNode", "DataSummaryNode", "SaveAnalysisResultsNode",
    "ClearReportDirNode",
    "ChartAnalysisNode", "LLMInsightNode",
    "CollectToolsNode", "DecisionToolsNode", "ExecuteToolsNode", "ProcessResultNode",
    "EnsureChartsNode",
    "ExtractQueriesNode", "WebSearchNode", "SearchProcessNode", "SearchReflectionNode",
    "SearchSummaryNode", "create_query_search_flow", "SearchAgentNode",
    "RunParallelAgentBranchNode", "ParallelAgentFlow", "create_parallel_agent_flow",
    "AssembleStage2ResultsNode",
    "ForumHostNode", "SupplementDataNode", "SupplementSearchNode",
    "VisualAnalysisNode", "MergeResultsNode",
    # stage3
    "LoadAnalysisResultsNode", "PlanOutlineNode", "GenerateChaptersBatchNode",
    "ReviewChaptersNode", "IRRendererNode", "InjectTraceNode", "MethodologyAppendixNode",
    "FormatReportNode", "RenderHTMLNode", "SaveReportNode",
    "ClearStage3OutputsNode",
]
