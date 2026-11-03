from opinion_core.schemas.artifacts import ContentBundle, LayoutSpec, LayoutSection


def build_structure(bundle):
    bundle=ContentBundle.model_validate(bundle)
    return LayoutSpec(event_id=bundle.event_id,run_id=bundle.run_id,title=f'{bundle.event_id} 舆情研究报告',
        sections=[LayoutSection(title=b.title,block_ids=[b.block_id]) for b in bundle.blocks]).model_dump(mode='json')


def validate_structure(bundle, layout):
    bundle,layout=ContentBundle.model_validate(bundle),LayoutSpec.model_validate(layout)
    if (bundle.event_id,bundle.run_id)!=(layout.event_id,layout.run_id):
        raise ValueError('content and layout belong to different runs')
    selected=[key for section in layout.sections for key in section.block_ids]
    if len(selected)!=len(set(selected)) or set(selected)!={b.block_id for b in bundle.blocks}:
        raise ValueError('layout must reference every existing content block exactly once')
    return bundle,layout
