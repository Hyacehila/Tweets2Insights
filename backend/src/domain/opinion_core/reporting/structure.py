from opinion_core.schemas.artifacts import ContentBundle, LayoutSpec, LayoutSection


def build_structure(bundle, charts=None):
    bundle = ContentBundle.model_validate(bundle)
    blocks = {b.block_id: b for b in bundle.blocks}
    groups = [(c.title, c.block_ids) for c in bundle.chapters] or [
        (b.title, [b.block_id]) for b in bundle.blocks
    ]
    covered = {key for _, keys in groups for key in keys}
    groups += [
        (b.title, [b.block_id]) for b in bundle.blocks if b.block_id not in covered
    ]
    used = set()
    sections = []
    for i, (title, keys) in enumerate(groups):
        selected = list(
            dict.fromkeys(
                chart
                for key in keys
                for chart in blocks[key].chart_ids
                if chart not in used
            )
        )
        used.update(selected)
        sections.append(
            LayoutSection(
                title=title,
                block_ids=keys,
                chart_ids=selected,
                presentation="spotlight" if i == 0 else "narrative",
            )
        )
    if sections:
        sections[-1].chart_ids.extend(key for key in (charts or {}) if key not in used)
    return LayoutSpec(
        event_id=bundle.event_id,
        run_id=bundle.run_id,
        title=bundle.report_title or f"{bundle.event_id} 舆情研究报告",
        sections=sections,
    ).model_dump(mode="json")


def validate_structure(bundle, layout, charts=None):
    bundle, layout = (
        ContentBundle.model_validate(bundle),
        LayoutSpec.model_validate(layout),
    )
    if (bundle.event_id, bundle.run_id) != (layout.event_id, layout.run_id):
        raise ValueError("content and layout belong to different runs")
    selected = [key for section in layout.sections for key in section.block_ids]
    if len(selected) != len(set(selected)) or set(selected) != {
        b.block_id for b in bundle.blocks
    }:
        raise ValueError(
            "layout must reference every existing content block exactly once"
        )
    chart_ids = [key for section in layout.sections for key in section.chart_ids]
    if charts is not None and (
        len(chart_ids) != len(set(chart_ids)) or set(chart_ids) != set(charts)
    ):
        raise ValueError("layout must reference every available chart exactly once")
    if bundle.chapters:
        for chapter in bundle.chapters:
            if not any(
                set(chapter.block_ids) <= set(s.block_ids) for s in layout.sections
            ):
                raise ValueError("keep each authored chapter together")
    return bundle, layout
