"""Server-side A4 report export; no browser or remote rendering service required."""

from io import BytesIO
import os
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    KeepTogether,
)
from svglib.svglib import svg2rlg
from reportlab.graphics.shapes import String

from .document import resolved_text, cited_evidence


def report_font():
    name = "T2IReportCJK"
    if name in pdfmetrics.getRegisteredFontNames():
        return name
    candidates = [
        os.environ.get("T2I_REPORT_FONT", ""),
        "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
    ]
    for path in candidates:
        if path and Path(path).is_file():
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                return name
            except Exception:
                if path == os.environ.get("T2I_REPORT_FONT"):
                    raise
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    return "STSong-Light"


def chart_drawing(chart):
    drawing = svg2rlg(BytesIO(chart["svg"].encode("utf-8")))
    if drawing is None or not drawing.width or not drawing.height:
        raise ValueError("PDF chart cannot be rendered")
    font = report_font()

    def replace_font(node):
        if isinstance(node, String):
            node.fontName = font
        for child in getattr(node, "contents", []):
            replace_font(child)

    replace_font(drawing)
    return drawing


def render_pdf(bundle, layout, charts):
    font = report_font()
    normal = ParagraphStyle(
        "body",
        fontName=font,
        fontSize=10.5,
        leading=18,
        wordWrap="CJK",
        spaceAfter=10,
        textColor=colors.HexColor("#26334a"),
        alignment=TA_LEFT,
    )
    heading = ParagraphStyle(
        "heading",
        parent=normal,
        fontSize=18,
        leading=26,
        spaceBefore=15,
        spaceAfter=18,
        keepWithNext=True,
        textColor=colors.HexColor("#123979"),
    )
    sub = ParagraphStyle(
        "subheading",
        parent=normal,
        fontSize=12,
        leading=20,
        spaceBefore=9,
        keepWithNext=True,
    )
    small = ParagraphStyle(
        "small",
        parent=normal,
        fontSize=8,
        leading=13,
        textColor=colors.HexColor("#63718a"),
    )
    title = ParagraphStyle(
        "title", parent=heading, fontSize=29, leading=41, spaceAfter=28
    )
    p = lambda text, style=normal: Paragraph(escape(text).replace("\n", "<br/>"), style)
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=22 * mm,
        leftMargin=22 * mm,
        topMargin=23 * mm,
        bottomMargin=22 * mm,
        title=layout.title,
        author="Tweets2Insights",
        pageCompression=1,
    )
    pages = [0]

    def footer(canvas, doc):
        pages[0] = doc.page
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#dce4f0"))
        canvas.line(22 * mm, 17 * mm, A4[0] - 22 * mm, 17 * mm)
        canvas.setFont(font, 8)
        canvas.setFillColor(colors.HexColor("#63718a"))
        canvas.drawString(22 * mm, 12 * mm, "Tweets2Insights · 舆情研究报告")
        canvas.drawRightString(A4[0] - 22 * mm, 12 * mm, str(doc.page))
        canvas.restoreState()

    story = [
        Spacer(1, 30 * mm),
        p("TWEETS2INSIGHTS", sub),
        p(layout.title, title),
        p("事件复盘 · 证据解读 · 研究报告", normal),
        Spacer(1, 12 * mm),
        p("运行版本：" + bundle.run_id, small),
        PageBreak(),
        p("目录", heading),
    ]
    for index, section in enumerate(layout.sections):
        story.append(p(f"{index + 1:02d}  {section.title}", sub))
    story.append(PageBreak())
    blocks = {b.block_id: b for b in bundle.blocks}
    cards, refs = cited_evidence(bundle)

    def chart_items(key):
        chart = charts[key]
        drawing = chart_drawing(chart)
        scale = min(document.width / drawing.width, 175 * mm / drawing.height)
        drawing.scale(scale, scale)
        drawing.width *= scale
        drawing.height *= scale
        return KeepTogether(
            [p(chart.get("title", key), sub), drawing, Spacer(1, 8 * mm)]
        )

    for index, section in enumerate(layout.sections):
        if index:
            story.append(PageBreak())
        story.append(p(f"{index + 1:02d}  {section.title}", heading))
        if section.chart_position == "before":
            story.extend(chart_items(key) for key in section.chart_ids)
        for key in section.block_ids:
            block = blocks[key]
            story.append(p(block.title, sub))
            text = resolved_text(block, bundle.metrics)
            text += " " + " ".join(f"[{refs[r]}]" for r in block.evidence_refs)
            story.extend(p(part) for part in text.split("\n\n") if part)
        if section.chart_position == "after":
            story.extend(chart_items(key) for key in section.chart_ids)
    story.extend([PageBreak(), p("参考资料与证据索引", heading)])
    for card in cards:
        story.append(p(f"[{refs[card.evidence_id]}] {card.title}", sub))
        story.append(p(card.source_url or card.source_ref or card.evidence_id, small))
        if card.kind in {"post", "web", "media"}:
            excerpt = " ".join(card.excerpt.split())
            story.append(p(excerpt[:700] + ("…" if len(excerpt) > 700 else ""), small))
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue(), pages[0]
