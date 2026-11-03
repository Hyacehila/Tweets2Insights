from typing import Any, Literal
from pydantic import Field, model_validator
from .base import Contract, Identifier, UTCDateTime


class EvidenceCard(Contract):
    evidence_id: Identifier
    kind: Literal['post', 'web', 'calculation', 'media']
    title: str
    excerpt: str
    source_url: str | None = None
    source_ref: str | None = None
    provider: str | None = None
    published_at: UTCDateTime | None = None
    retrieved_at: UTCDateTime
    content_sha256: str
    relevance: float | None = None
    historical_availability_verified: bool = False


class ContentBlock(Contract):
    block_id: Identifier
    kind: Literal['observed', 'forecast', 'simulated', 'interpretation']
    title: str
    text: str
    evidence_refs: list[Identifier] = Field(default_factory=list)
    numeric_refs: list[str] = Field(default_factory=list)
    artifact_refs: list[Identifier] = Field(default_factory=list)


class ContentBundle(Contract):
    event_id: Identifier
    run_id: Identifier
    blocks: list[ContentBlock]
    evidence: list[EvidenceCard]
    metrics: dict[str, Any]
    source_versions: dict[str, str]

    @model_validator(mode='after')
    def references(self):
        if len({b.block_id for b in self.blocks}) != len(self.blocks):
            raise ValueError('duplicate content block')
        evidence = {e.evidence_id for e in self.evidence}
        if len(evidence) != len(self.evidence):
            raise ValueError('duplicate evidence ID')
        for block in self.blocks:
            if not set(block.evidence_refs) <= evidence or not set(block.numeric_refs) <= set(self.metrics):
                raise ValueError('unresolved content reference')
            if not set(block.artifact_refs) <= set(self.source_versions.values()):
                raise ValueError('unresolved artifact reference')
        return self


class LayoutSection(Contract):
    title: str
    block_ids: list[Identifier] = Field(min_length=1)


class LayoutSpec(Contract):
    event_id: Identifier
    run_id: Identifier
    title: str
    sections: list[LayoutSection]


class ArtifactRef(Contract):
    artifact_id: Identifier
    event_id: Identifier
    run_id: Identifier
    kind: str
    sha256: str
