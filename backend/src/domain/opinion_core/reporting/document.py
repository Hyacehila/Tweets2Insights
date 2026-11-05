"""Common text, citation and component plan shared by web and static exports."""

import json
import re


def resolved_text(block, metrics):
    refs = set(re.findall(r"\{\{([^}]+)\}\}", block.text))
    if refs != set(block.numeric_refs):
        raise ValueError("text numeric placeholders differ from declared references")

    def value(match):
        number = metrics[match.group(1)]
        return f"{number:.6g}" if isinstance(number, float) else str(number)

    return re.sub(r"\{\{([^}]+)\}\}", value, block.text)


def cited_evidence(bundle):
    used = {ref for b in bundle.blocks for ref in b.evidence_refs}
    cards = [e for e in bundle.evidence if e.evidence_id in used]
    return cards, {card.evidence_id: f"E{i + 1}" for i, card in enumerate(cards)}


def openui_program(layout):
    quote = lambda value: json.dumps(value, ensure_ascii=False)
    sections = []
    for index, section in enumerate(layout.sections):
        blocks = [f"ReportBlock({quote(key)})" for key in section.block_ids]
        charts = [f"ReportChart({quote(key)})" for key in section.chart_ids]
        children = (
            charts + blocks if section.chart_position == "before" else blocks + charts
        )
        sections.append(
            f"ReportSection({quote(str(index))}, {quote(section.presentation)}, [{', '.join(children)}])"
        )
    return "root = ReportPage([" + ", ".join(sections) + "])"
