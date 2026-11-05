"""Publish one authored document as OpenUI, standalone HTML, Markdown and PDF."""

import base64
import html
import re
from urllib.parse import urlsplit, quote

from .structure import validate_structure, build_structure
from .document import resolved_text, cited_evidence, openui_program
from .pdf import render_pdf
from .charts import static_chart


def render_report(bundle, layout, charts=None):
    charts = {key: static_chart(value) for key, value in (charts or {}).items()}
    for key, value in charts.items():
        if key in {"sentiment", "stance"} and not value.get("title"):
            value["title"] = {
                "sentiment": "情绪分布随时间变化",
                "stance": "立场分布随时间变化",
            }[key]
    # Existing stored layouts predate chart placement. Retain their text order on export.
    if charts and not any(s.get("chart_ids") for s in layout["sections"]):
        layout = {**layout, "sections": [{**s} for s in layout["sections"]]}
        layout["sections"][-1]["chart_ids"] = list(charts)
    bundle, layout = validate_structure(bundle, layout, charts)
    blocks = {b.block_id: b for b in bundle.blocks}
    cards, refs = cited_evidence(bundle)
    markdown, sections, images = ["# " + layout.title], [], {}

    def chart_fragment(key):
        if not re.fullmatch(
            r"(sentiment|stance|t-[a-f0-9]{64}|forecast-(stance|sentiment|topic|emotion|mass-stance|mass-sentiment)|scenario-(stance|variance))",
            key,
        ):
            raise ValueError("unsupported chart reference")
        chart = charts[key]
        images[key + ".svg"] = chart["svg"]
        title = chart.get("title", key)
        markdown.append("![" + title + "](images/" + key + ".svg)")
        rows = chart.get("data", [])
        columns = list(dict.fromkeys(k for row in rows for k in row if k != "post_ids"))
        table = (
            '<div class="table-scroll"><table><thead><tr>'
            + "".join("<th>" + html.escape(k) + "</th>" for k in columns)
            + "</tr></thead><tbody>"
        )
        for row in rows:
            table += (
                "<tr>"
                + "".join(
                    "<td>" + html.escape(str(row.get(k, ""))) + "</td>" for k in columns
                )
                + "</tr>"
            )
        table += "</tbody></table></div>"
        return (
            "<figure><figcaption>"
            + html.escape(title)
            + "</figcaption>"
            + chart["svg"]
            + "<details><summary>查看图表数据</summary>"
            + table
            + "</details></figure>"
        )

    for index, section in enumerate(layout.sections):
        markdown.append("## " + section.title)
        body = []
        if section.chart_position == "before":
            body.extend(chart_fragment(key) for key in section.chart_ids)
        for key in section.block_ids:
            block = blocks[key]
            text = resolved_text(block, bundle.metrics)
            citations = " ".join("[" + refs[r] + "]" for r in block.evidence_refs)
            markdown.extend(["### " + block.title, text + " " + citations])
            links = " ".join(
                f'<a class="citation" href="#ref-{refs[r]}">[{refs[r]}]</a>'
                for r in block.evidence_refs
            )
            body.append(
                "<article><h3>"
                + html.escape(block.title)
                + "</h3><p>"
                + html.escape(text).replace("\n", "<br>")
                + " "
                + links
                + "</p></article>"
            )
        if section.chart_position == "after":
            body.extend(chart_fragment(key) for key in section.chart_ids)
        sections.append(
            f'<section id="chapter-{index}" class="{section.presentation}"><h2><span>{index + 1:02d}</span> '
            + html.escape(section.title)
            + "</h2>"
            + "".join(body)
            + "</section>"
        )
    markdown.append("## 参考资料与证据索引")
    reference_html = []
    for card in cards:
        source = card.source_url or card.source_ref or ""
        url = urlsplit(source)
        encoded = quote(source, safe=":/?&=#%+@;,-._~")
        link = (
            '<a href="'
            + html.escape(encoded, quote=True)
            + '" rel="noopener noreferrer">'
            + html.escape(source)
            + "</a>"
            if url.scheme in {"http", "https"} and url.netloc
            else html.escape(source)
        )
        markdown.append(f"[{refs[card.evidence_id]}] {card.title} | {source}")
        reference_html.append(
            f'<article id="ref-{refs[card.evidence_id]}"><h3>[{refs[card.evidence_id]}] '
            + html.escape(card.title)
            + "</h3><p>"
            + link
            + "</p></article>"
        )
    toc = "".join(
        f'<a href="#chapter-{i}">{i + 1:02d} {html.escape(s.title)}</a>'
        for i, s in enumerate(layout.sections)
    )
    document = (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'
        + html.escape(layout.title)
        + """</title><style>
    *{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f4f7fb;color:#17243a;font:16px/1.9 system-ui,"Microsoft YaHei",sans-serif}header,main,nav{max-width:1040px;margin:auto;padding:36px}header{padding-top:72px}header small{color:#3d60b1;letter-spacing:3px}h1{font-size:38px;line-height:1.45}nav{display:flex;flex-wrap:wrap;gap:8px 20px;padding-top:0}nav a{font-size:14px}a{color:#285aca;text-decoration:none}section{padding:30px 36px;margin-bottom:28px;border:1px solid #e1e7f0;border-radius:18px;background:white;scroll-margin-top:20px}h2{font-size:24px;line-height:1.5}h2 span{color:#637ebc;font-size:17px;margin-right:8px}h3{font-size:18px;line-height:1.6;margin-top:28px}p{overflow-wrap:anywhere}.spotlight{background:#eef4ff;border-color:#ceddfa}.citation{font-size:12px;white-space:nowrap}figure{margin:30px 0}figcaption{font-weight:600;margin-bottom:16px}svg{max-width:100%;height:auto}details{font-size:13px;color:#536680}summary{cursor:pointer}.table-scroll{overflow:auto}table{border-collapse:collapse;width:100%}td,th{padding:6px;border-bottom:1px solid #ddd;text-align:left}footer{text-align:center;color:#63718a;padding:32px}@media(max-width:650px){header,main,nav{padding:20px}section{padding:20px}h1{font-size:28px}}@media print{body{background:white}nav,details{display:none}section{break-before:page;border:0}figure{break-inside:avoid}header{padding-top:50mm}}
    </style></head><body><header><small>TWEETS2INSIGHTS</small><h1>"""
        + html.escape(layout.title)
        + "</h1></header><nav>"
        + toc
        + "</nav><main>"
        + "".join(sections)
        + "<section><h2>参考资料与证据索引</h2>"
        + "".join(reference_html)
        + "</section></main><footer>Tweets2Insights</footer></body></html>"
    )
    pdf, page_count = render_pdf(bundle, layout, charts)
    return {
        "markdown": "\n\n".join(markdown),
        "html": document,
        "images": images,
        "chart_data": charts,
        "content": bundle.model_dump(mode="json"),
        "layout": layout.model_dump(mode="json"),
        "openui": openui_program(layout),
        "pdf_base64": base64.b64encode(pdf).decode("ascii"),
        "pdf_pages": page_count,
        "report_version": "template-agents-v2",
    }
