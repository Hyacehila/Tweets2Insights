from typing import Literal
from pydantic import Field, model_validator
from .base import Contract, Identifier, UTCDateTime


class EventSpec(Contract):
    event_id: Identifier
    input_mode: Literal['upload', 'existing', 'keywords']
    dataset_ref: Identifier | None = None
    keywords: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    start: UTCDateTime | None = None
    end: UTCDateTime | None = None
    as_of: UTCDateTime
    objectives: list[str] = Field(default_factory=lambda: ['retrospective'])
    search_provider: Literal['tavily', 'deepseek'] = 'tavily'

    @model_validator(mode='after')
    def check_route(self):
        if self.input_mode in ('upload', 'existing') and not self.dataset_ref:
            raise ValueError('uploaded/existing data requires dataset_ref')
        if self.input_mode == 'keywords' and (not self.keywords or self.dataset_ref):
            raise ValueError('keyword collection requires keywords and no dataset_ref')
        if (self.start is None) != (self.end is None):
            raise ValueError('window requires both start and end')
        if self.start and not self.start < self.end <= self.as_of:
            raise ValueError('require start < end <= as_of')
        return self

    @property
    def requires_collection(self):
        return self.input_mode == 'keywords'


class LabelDefinition(Contract):
    id: Identifier
    definition: str = Field(min_length=1)


class EventSchema(Contract):
    event_id: Identifier
    schema_version: Identifier
    as_of: UTCDateTime
    topics: list[LabelDefinition]
    publishers: list[LabelDefinition]
    emotions: list[LabelDefinition]
    targets: list[LabelDefinition]
    evidence_refs: list[Identifier] = Field(min_length=1)

    @model_validator(mode='after')
    def unique_labels(self):
        for group in (self.topics, self.publishers, self.emotions, self.targets):
            if len({v.id for v in group}) != len(group):
                raise ValueError('label IDs must be unique within each vocabulary')
        return self
