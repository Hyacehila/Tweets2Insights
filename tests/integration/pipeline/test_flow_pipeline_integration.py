"""
Integration tests for multi-node pipelines.
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

pytestmark = pytest.mark.integration

from nodes import (
    DataLoadNode,
    DataSummaryNode,
    DataValidationAndOverviewNode,
    FormatReportNode,
    LLMInsightNode,
    PlanOutlineNode,
    SaveEnhancedDataNode,
    SaveReportNode,
    Stage1CompletionNode,
    Stage2CompletionNode,
    Stage3CompletionNode,
    TerminalNode,
)


def _complete_stage(shared, completion_cls):
    node = completion_cls()
    p = node.prep(shared)
    e = node.exec(p)
    return node.post(shared, p, e)


class TestStage1PipelineFlow:
    @patch("nodes.stage1.save.save_enhanced_blog_data", return_value=True)
    @patch("nodes.stage1.data_load.load_belief_system", return_value=[])
    @patch("nodes.stage1.data_load.load_publisher_objects")
    @patch("nodes.stage1.data_load.load_sentiment_attributes")
    @patch("nodes.stage1.data_load.load_topics")
    @patch("nodes.stage1.data_load.load_blog_data")
    def test_full_stage1_pipeline(
        self,
        mock_blog,
        mock_topics,
        mock_sa,
        mock_po,
        _mock_bs,
        _mock_save,
        sample_blog_data,
        sample_topics,
        sample_sentiment_attrs,
        sample_publishers,
        minimal_shared,
    ):
        mock_blog.return_value = sample_blog_data
        mock_topics.return_value = sample_topics
        mock_sa.return_value = sample_sentiment_attrs
        mock_po.return_value = sample_publishers

        load_node = DataLoadNode()
        prep = load_node.prep(minimal_shared)
        exec_res = load_node.exec(prep)
        load_node.post(minimal_shared, prep, exec_res)

        assert len(minimal_shared["data"]["blog_data"]) == 3

        val_node = DataValidationAndOverviewNode()
        val_prep = val_node.prep(minimal_shared)
        val_exec = val_node.exec(val_prep)
        val_node.post(minimal_shared, val_prep, val_exec)

        stats = minimal_shared["stage1_results"]["statistics"]
        assert stats["total_blogs"] == 3

        save_node = SaveEnhancedDataNode()
        save_prep = save_node.prep(minimal_shared)
        save_exec = save_node.exec(save_prep)
        save_node.post(minimal_shared, save_prep, save_exec)

        assert minimal_shared["stage1_results"]["data_save"]["saved"] is True


class TestStage2AnalysisFlow:
    @patch(
        "nodes.stage2.insight.call_glm46",
        return_value='{"sentiment_summary":"s","topic_distribution":"t","geographic_distribution":"g","publisher_behavior":"p","overall_summary":"o"}',
    )
    @patch("nodes.stage2.chart_analysis.call_glm45v_thinking", return_value="分析结果")
    def test_summary_to_insight_pipeline(self, _mock_chart_llm, _mock_insight_llm, enhanced_shared):
        enhanced_shared["stage2_results"] = {}

        summary_node = DataSummaryNode()
        sum_prep = summary_node.prep(enhanced_shared)
        sum_exec = summary_node.exec(sum_prep)
        summary_node.post(enhanced_shared, sum_prep, sum_exec)

        assert "data_summary" in enhanced_shared["agent"]

        enhanced_shared["stage2_results"]["charts"] = [{"id": "c1", "title": "情感趋势", "type": "line"}]
        enhanced_shared["stage2_results"]["tables"] = [{"id": "t1", "title": "情感分布", "data": {"summary": "测试"}}]

        from nodes import ChartAnalysisNode

        chart_node = ChartAnalysisNode()
        chart_prep = chart_node.prep(enhanced_shared)
        chart_exec = chart_node.exec(chart_prep)
        chart_node.post(enhanced_shared, chart_prep, chart_exec)

        assert "chart_analyses" in enhanced_shared["stage2_results"]

        insight_node = LLMInsightNode()
        insight_prep = insight_node.prep(enhanced_shared)
        insight_exec = insight_node.exec(insight_prep)
        insight_node.post(enhanced_shared, insight_prep, insight_exec)

        assert "insights" in enhanced_shared["stage2_results"]


class TestStage3UnifiedFlow:
    @patch("nodes.stage3.outline.call_glm46")
    @patch("nodes.stage3.format._load_analysis_charts", return_value=[])
    def test_outline_then_format_then_save(self, _mock_charts, mock_outline_llm, minimal_shared, tmp_path):
        mock_outline_llm.return_value = (
            '{"title":"统一报告","chapters":[{"id":"ch01","title":"执行摘要","target_words":200}]}'
        )
        minimal_shared["stage3_data"] = {
            "analysis_data": {"charts": [], "tables": [], "execution_log": {}},
            "insights": {"summary": "ok"},
            "trace": {"loop_status": {}},
        }
        minimal_shared["stage3_results"] = {
            "reviewed_report_text": "# 报告\n\n## 结论\n内容"
        }
        minimal_shared["trace"] = {"loop_status": {}}

        outline_node = PlanOutlineNode()
        prep = outline_node.prep(minimal_shared)
        res = outline_node.exec(prep)
        outline_node.post(minimal_shared, prep, res)

        assert minimal_shared["stage3_results"]["outline"]["title"] == "统一报告"

        fmt_node = FormatReportNode()
        fmt_prep = fmt_node.prep(minimal_shared)
        fmt_exec = fmt_node.exec(fmt_prep)
        fmt_node.post(minimal_shared, fmt_prep, fmt_exec)

        assert "## 目录" in minimal_shared["stage3_results"]["final_report_text"]

        with patch("nodes.stage3.save.get_report_dir", return_value=str(tmp_path)):
            save_node = SaveReportNode()
            save_prep = save_node.prep(minimal_shared)
            save_exec = save_node.exec(save_prep)
            save_node.post(minimal_shared, save_prep, save_exec)

        assert Path(save_exec["report_md"]).exists()


class TestLinearPipelineStateFlow:
    def test_three_stage_completion_updates_pipeline_state(self, minimal_shared):
        minimal_shared["config"]["enhancement_mode"] = "async"
        minimal_shared["config"]["analysis_mode"] = "agent"
        minimal_shared["config"]["tool_source"] = "mcp"

        action1 = _complete_stage(minimal_shared, Stage1CompletionNode)
        assert action1 == "default"
        assert minimal_shared["pipeline_state"]["completed_stages"] == [1]

        action2 = _complete_stage(minimal_shared, Stage2CompletionNode)
        assert action2 == "default"
        assert minimal_shared["pipeline_state"]["completed_stages"] == [1, 2]

        action3 = _complete_stage(minimal_shared, Stage3CompletionNode)
        assert action3 == "default"
        assert minimal_shared["pipeline_state"]["completed_stages"] == [1, 2, 3]

    def test_terminal_generates_summary(self, minimal_shared):
        minimal_shared["pipeline_state"]["completed_stages"] = [1, 2, 3]
        minimal_shared["stage1_results"]["statistics"]["total_blogs"] = 100
        minimal_shared["stage1_results"]["data_save"]["saved"] = True

        terminal = TerminalNode()
        prep = terminal.prep(minimal_shared)
        exec_res = terminal.exec(prep)
        action = terminal.post(minimal_shared, prep, exec_res)

        assert "final_summary" in minimal_shared
        assert action == "default"
