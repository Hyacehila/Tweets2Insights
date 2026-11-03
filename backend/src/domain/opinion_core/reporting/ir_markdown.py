"""Pure Stage3 IR renderer, shared by legacy nodes and domain tools."""
from typing import Any, Dict, List

def _render_inlines(inlines: List[Dict[str, Any]]) -> str:
    """Render an inlines array into Markdown text."""
    parts: List[str] = []
    for run in inlines:
        if not isinstance(run, dict):
            parts.append(str(run))
            continue
        text = str(run.get("text", ""))
        marks = run.get("marks", [])
        if not isinstance(marks, list):
            marks = []
        for mark in marks:
            if not isinstance(mark, dict):
                continue
            mark_type = mark.get("type", "")
            if mark_type == "bold":
                text = f"**{text}**"
            elif mark_type == "italic":
                text = f"*{text}*"
            elif mark_type == "link":
                url = mark.get("value", "")
                text = f"[{text}]({url})"
            elif mark_type == "color":
                pass
            elif mark_type == "highlight":
                text = f"**{text}**"
        parts.append(text)
    return "".join(parts)


def _render_block(block: Dict[str, Any]) -> str:
    """Render a single IR block to Markdown."""
    if not isinstance(block, dict):
        return str(block or "")

    block_type = block.get("type", "paragraph")

    if block_type == "paragraph":
        inlines = block.get("inlines", [])
        if isinstance(inlines, list):
            return _render_inlines(inlines)
        return str(inlines or "")

    if block_type == "heading":
        level = int(block.get("level", 3))
        level = max(3, min(level, 6))
        text = str(block.get("text", "")).strip()
        return f"{'#' * level} {text}"

    if block_type == "list":
        items = block.get("items", [])
        return "\n".join(f"- {item}" for item in items if str(item).strip())

    if block_type == "table":
        headers = block.get("headers", [])
        rows = block.get("rows", [])
        lines: List[str] = []
        if headers:
            lines.append("| " + " | ".join(str(h) for h in headers) + " |")
            lines.append("| " + " | ".join("---" for _ in headers) + " |")
        for row in rows:
            if isinstance(row, list):
                lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
        return "\n".join(lines)

    if block_type == "swotTable":
        sections: List[str] = []
        dim_labels = {
            "strengths": "优势 (S)",
            "weaknesses": "劣势 (W)",
            "opportunities": "机会 (O)",
            "threats": "威胁 (T)",
        }
        for dim_key, dim_label in dim_labels.items():
            entries = block.get(dim_key, [])
            if not entries:
                continue
            sections.append(f"**{dim_label}**")
            for entry in entries:
                if isinstance(entry, dict):
                    point = entry.get("point", "")
                    detail = entry.get("detail", "")
                    sections.append(f"- {point}：{detail}" if detail else f"- {point}")
                else:
                    sections.append(f"- {entry}")
        return "\n".join(sections)

    if block_type == "pestTable":
        sections = []
        dim_labels = {
            "political": "政治因素 (P)",
            "economic": "经济因素 (E)",
            "social": "社会因素 (S)",
            "technological": "技术因素 (T)",
        }
        for dim_key, dim_label in dim_labels.items():
            entries = block.get(dim_key, [])
            if not entries:
                continue
            sections.append(f"**{dim_label}**")
            for entry in entries:
                if isinstance(entry, dict):
                    factor = entry.get("factor", "")
                    detail = entry.get("detail", "")
                    sections.append(f"- {factor}：{detail}" if detail else f"- {factor}")
                else:
                    sections.append(f"- {entry}")
        return "\n".join(sections)

    if block_type == "engineQuote":
        engine = block.get("engine", "unknown")
        title = block.get("title", f"{engine.capitalize()} Agent")
        inner_blocks = block.get("blocks", [])
        inner_text = "\n".join(
            f"> {_render_block(b)}" for b in inner_blocks if isinstance(b, dict)
        )
        return f"> **💬 {title}**\n{inner_text}" if inner_text else ""

    if block_type == "image":
        alt = block.get("alt", "图表")
        src = block.get("src", "")
        return f"![{alt}]({src})"

    if block_type == "blockquote":
        text = str(block.get("text", "")).strip()
        return f"> {text}"

    if block_type == "hr":
        return "---"

    return str(block.get("text", block.get("content", "")))


def render_blocks_to_markdown(blocks: List[Dict[str, Any]]) -> str:
    """Convert a list of IR blocks into a Markdown string."""
    if not isinstance(blocks, list):
        return str(blocks or "")
    rendered = []
    for block in blocks:
        text = _render_block(block)
        if text:
            rendered.append(text)
    return "\n\n".join(rendered)


