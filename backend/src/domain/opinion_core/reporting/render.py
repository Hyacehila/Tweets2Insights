import html
import re
from urllib.parse import urlsplit, quote
from .structure import validate_structure
from .ir_markdown import render_blocks_to_markdown


def render_report(bundle, layout, charts=None):
    bundle, layout = validate_structure(bundle, layout)
    blocks = {b.block_id: b for b in bundle.blocks}
    markdown = ["# " + layout.title]
    sections = []
    kinds = {
        "observed": "观测",
        "forecast": "预测",
        "simulated": "模拟",
        "interpretation": "解释",
    }
    for section in layout.sections:
        body = []
        for key in section.block_ids:
            b = blocks[key]
            references = set(re.findall(r"\{\{([^}]+)\}\}", b.text))
            if references != set(b.numeric_refs):
                raise ValueError(
                    "text numeric placeholders differ from declared references"
                )
            text = b.text
            for ref in references:
                text = text.replace("{{" + ref + "}}", str(bundle.metrics[ref]))
            text = f"[{kinds[b.kind]}] " + text
            text += "".join(" [" + ref + "]" for ref in b.evidence_refs)
            body.append(text)
        markdown += [
            "## " + section.title,
            render_blocks_to_markdown(
                [{"type": "paragraph", "inlines": [{"text": s}]} for s in body]
            ),
        ]
        sections.append(
            "<section><h2>"
            + html.escape(section.title)
            + "</h2>"
            + "".join("<p>" + html.escape(s) + "</p>" for s in body)
            + "</section>"
        )
    references = ["## 证据索引"]
    reference_html = []
    for card in bundle.evidence:
        source = card.source_url or card.source_ref or ""
        url = urlsplit(source)
        if url.scheme in {"http", "https"} and url.netloc:
            encoded = quote(source, safe=":/?&=#%+@;,-._~")
            markdown_source = "[来源](" + encoded + ")"
            html_source = (
                '<a href="'
                + html.escape(encoded, quote=True)
                + '" rel="noopener noreferrer">来源</a>'
            )
        else:
            markdown_source = source
            html_source = html.escape(source)
        references.append(f"[{card.evidence_id}] {card.title} | {markdown_source}")
        reference_html.append(
            "<p>"
            + html.escape(f"[{card.evidence_id}] {card.title}")
            + " | "
            + html_source
            + "</p>"
        )
    images = {}
    for name, chart in (charts or {}).items():
        if not re.fullmatch(
            r"(sentiment|stance|t-[a-f0-9]{64}|forecast-(stance|sentiment|topic|emotion|mass-stance|mass-sentiment)|scenario-(stance|variance))",
            name,
        ):
            raise ValueError("unsupported chart reference")
        images[name + ".svg"] = chart["svg"]
        title = chart.get("title", name + " 分布")
        markdown += ["## " + title, "![" + title + "](images/" + name + ".svg)"]
        table = chart.get("data", [])
        columns = list(
            dict.fromkeys(k for row in table[:60] for k in row if k not in {"post_ids"})
        )
        source_table = (
            "<table><thead><tr>"
            + "".join("<th>" + html.escape(k) + "</th>" for k in columns)
            + "</tr></thead><tbody>"
        )
        for row in table[:60]:
            source_table += (
                "<tr>"
                + "".join(
                    "<td>" + html.escape(str(row.get(k, ""))) + "</td>" for k in columns
                )
                + "</tr>"
            )
        source_table += "</tbody></table>"
        sections.append(
            "<section><h2>"
            + html.escape(title)
            + "</h2>"
            + chart["svg"]
            + "<details><summary>来源表（前六十行，完整数据见 JSON 导出）</summary>"
            + source_table
            + "</details></section>"
        )
    markdown += references
    document = (
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>'
        + html.escape(layout.title)
        + "</title><style>body{max-width:980px;margin:3rem auto;font:17px/1.8 system-ui;padding:0 1rem}section{border-bottom:1px solid #ddd}p{white-space:pre-wrap}</style><body><h1>"
        + html.escape(layout.title)
        + "</h1>"
        + "".join(sections)
        + "<h2>证据索引</h2>"
        + "".join(reference_html)
        + "</body></html>"
    )
    return {
        "markdown": "\n\n".join(markdown),
        "html": document,
        "images": images,
        "chart_data": charts or {},
        "content": bundle.model_dump(mode="json"),
        "layout": layout.model_dump(mode="json"),
    }
