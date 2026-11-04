"""
test_stage3_report.py — Unified Stage3 core node unit tests.
"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from nodes import (
    FormatReportNode,
    LoadAnalysisResultsNode,
    SaveReportNode,
    Stage3CompletionNode,
)


class TestLoadAnalysisResultsNode:
    def test_exec_prefers_memory_and_keeps_trace(self, minimal_shared, tmp_path):
        enhanced_path = tmp_path / "enhanced.json"
        sample = [{"id": "sample-1", "content": "synthetic report sample"}]
        enhanced_path.write_text(json.dumps(sample), encoding="utf-8")
        minimal_shared["config"]["data_source"]["enhanced_data_path"] = str(enhanced_path)
        minimal_shared["pipeline_state"]["completed_stages"] = [1, 2]
        minimal_shared["stage2_results"] = {
            "charts": [{"id": "c1"}],
            "tables": [{"id": "t1"}],
            "chart_analyses": {"c1": {"analysis": "ok"}},
            "insights": {"summary": "ok"},
            "execution_log": {},
        }
        minimal_shared["trace"] = {
            "decisions": [{"id": "d1"}],
            "executions": [],
            "reflections": [],
            "insight_provenance": {"summary": []},
            "loop_status": {"stage3_chapter_review": {"current": 1, "max": 2, "termination_reason": "sufficient"}},
        }

        node = LoadAnalysisResultsNode()
        prep_res = node.prep(minimal_shared)
        exec_res = node.exec(prep_res)
        action = node.post(minimal_shared, prep_res, exec_res)

        assert action == "default"
        assert exec_res["sample_blogs"] == sample
        assert exec_res["analysis_data"]["charts"][0]["id"] == "c1"
        assert exec_res["trace"]["decisions"][0]["id"] == "d1"
        assert minimal_shared["stage3_data"]["trace"]["insight_provenance"] == {"summary": []}

    @patch("os.path.exists", return_value=False)
    def test_prep_raises_when_missing_stage2_files(self, _mock_exists, minimal_shared):
        node = LoadAnalysisResultsNode()
        with pytest.raises(FileNotFoundError):
            node.prep(minimal_shared)

    def test_post_merges_loaded_trace_into_shared_trace(self, minimal_shared):
        node = LoadAnalysisResultsNode()
        minimal_shared["trace"] = {
            "decisions": [],
            "executions": [],
            "reflections": [],
            "insight_provenance": {},
            "loop_status": {},
        }
        exec_res = {
            "analysis_data": {"charts": [], "tables": [], "execution_log": {}, "search_context": {}},
            "chart_analyses": {},
            "insights": {"summary": "ok"},
            "trace": {
                "decisions": [{"id": "d1"}],
                "executions": [],
                "reflections": [],
                "insight_provenance": {},
                "loop_status": {"forum": {"current": 1, "max": 3, "termination_reason": "seeded"}},
            },
            "sample_blogs": [],
            "images_dir": "report/images",
        }

        node.post(minimal_shared, {}, exec_res)

        assert minimal_shared["trace"]["loop_status"]["forum"]["current"] == 1


class TestFormatReportNode:
    @patch("nodes.stage3.format._load_analysis_charts", return_value=[])
    def test_exec_normalizes_paths_and_adds_toc(self, _mock_charts, minimal_shared):
        minimal_shared["stage3_results"] = {
            "report_text": "# 标题\n\n![图](report/images/a.png)\n\n## 结论\n内容"
        }
        minimal_shared["trace"] = {"loop_status": {}}

        node = FormatReportNode()
        prep_res = node.prep(minimal_shared)
        output = node.exec(prep_res)

        assert "./images/a.png" in output
        assert "## 目录" in output

    @patch("nodes.stage3.format._load_analysis_charts", return_value=[])
    def test_exec_injects_loop_execution_summary(self, _mock_charts, minimal_shared):
        minimal_shared["stage3_results"] = {
            "report_text": "# 报告\n\n## 结论\n内容"
        }
        minimal_shared["trace"] = {
            "loop_status": {
                "stage3_chapter_review": {
                    "current": 2,
                    "max": 2,
                    "termination_reason": "max_iterations_reached",
                }
            }
        }

        node = FormatReportNode()
        prep_res = node.prep(minimal_shared)
        output = node.exec(prep_res)

        assert "运行执行摘要" in output
        assert "stage3_chapter_review" in output
        assert "max_iterations_reached" in output

    @patch("nodes.stage3.format._load_analysis_charts", return_value=[])
    def test_exec_removes_immediate_duplicate_heading_lines(self, _mock_charts, minimal_shared):
        minimal_shared["stage3_results"] = {
            "report_text": "# 报告\n\n## 情感分析\n\n### 情感分析\n\n该段结论由趋势图支持[E1]。"
        }
        minimal_shared["trace"] = {"loop_status": {}}

        node = FormatReportNode()
        prep_res = node.prep(minimal_shared)
        output = node.exec(prep_res)

        assert "## 情感分析" in output
        assert "### 情感分析" not in output


class TestSaveReportNode:
    @patch("nodes.stage3.save.get_report_dir")
    def test_exec_writes_md_html_and_trace(self, mock_report_dir, tmp_path):
        mock_report_dir.return_value = str(tmp_path)
        node = SaveReportNode()

        payload = {
            "markdown": "# MD report\n",
            "html": "<html><body>report</body></html>",
            "trace": {"loop_status": {"stage3_chapter_review": {"current": 1}}},
        }

        result = node.exec(payload)

        md_path = Path(result["report_md"])
        html_path = Path(result["report_html"])
        trace_path = Path(result["trace_file"])

        assert md_path.exists()
        assert html_path.exists()
        assert trace_path.exists()
        assert md_path.read_text(encoding="utf-8").startswith("# MD")
        assert "<html" in html_path.read_text(encoding="utf-8")
        assert json.loads(trace_path.read_text(encoding="utf-8"))["loop_status"]["stage3_chapter_review"]["current"] == 1

    def test_post_records_output_files(self, minimal_shared):
        minimal_shared["stage3_results"] = {}
        node = SaveReportNode()
        exec_res = {
            "report_md": "report/report.md",
            "report_html": "report/report.html",
            "trace_file": "report/trace.json",
        }
        action = node.post(minimal_shared, {}, exec_res)

        assert action == "default"
        assert minimal_shared["stage3_results"]["report_file"] == "report/report.md"
        assert minimal_shared["stage3_results"]["output_files"]["report_html"] == "report/report.html"


class TestStage3CompletionNode:
    def test_marks_stage3_completed(self, minimal_shared):
        node = Stage3CompletionNode()
        prep_res = {
            "generation_mode": "unified",
            "iterations": 1,
            "final_score": 88,
        }
        action = node.post(minimal_shared, prep_res, True)

        assert action == "default"
        assert 3 in minimal_shared["pipeline_state"]["completed_stages"]
        assert minimal_shared["pipeline_state"]["current_stage"] == 3
