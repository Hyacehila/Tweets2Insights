"""
Stage3 IR (Intermediate Representation) to Markdown renderer.

Converts JSON block arrays produced by GenerateChaptersBatchNode
into formatted Markdown text for downstream consumption.
"""
from typing import Any, Dict, List

from nodes.base import MonitoredNode


from opinion_core.reporting.ir_markdown import _render_inlines, _render_block, render_blocks_to_markdown


class IRRendererNode(MonitoredNode):
    """Convert JSON IR blocks in all chapters to Markdown text."""

    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        stage3_results = shared.get("stage3_results", {})
        return {
            "chapters": list(stage3_results.get("chapters", []) or []),
            "outline_title": stage3_results.get("outline", {}).get("title", "舆情分析统一报告"),
        }

    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        chapters = prep_res.get("chapters", [])
        rendered_chapters = []
        for chapter in chapters:
            ch = dict(chapter)
            blocks = ch.get("blocks", [])
            if isinstance(blocks, list) and blocks:
                ch["content"] = render_blocks_to_markdown(blocks)
            rendered_chapters.append(ch)
        return {"chapters": rendered_chapters}

    def post(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        stage3_results = shared.setdefault("stage3_results", {})
        stage3_results["chapters"] = exec_res.get("chapters", [])

        title = prep_res.get("outline_title", "舆情分析统一报告")
        lines = [f"# {title}", ""]
        for chapter in exec_res.get("chapters", []):
            chapter_title = chapter.get("title") or chapter.get("id") or "未命名章节"
            lines.append(f"## {chapter_title}")
            lines.append("")
            lines.append(str(chapter.get("content", "")).strip())
            lines.append("")
        assembled = "\n".join(lines).strip() + "\n"
        stage3_results["reviewed_report_text"] = assembled
        return "default"
