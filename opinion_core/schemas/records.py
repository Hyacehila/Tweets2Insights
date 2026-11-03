from typing import Literal
from pydantic import Field, model_validator
from .base import Contract, Identifier, UTCDateTime


class PostRecord(Contract):
    post_id: Identifier
    platform: str
    raw_id: str
    kind: Literal['post', 'comment'] = 'post'
    parent_ref: str | None = None
    content: str
    published_at: UTCDateTime | None = None
    collected_at: UTCDateTime | None = None
    original_time: str | None = None
    time_status: Literal['parsed', 'missing', 'invalid', 'unresolved'] = 'missing'
    source_url: str | None = None
    author_ref: str | None = None
    media_refs: list[str] = Field(default_factory=list)
    raw_asset_ref: str | None = None

    @model_validator(mode='after')
    def time_consistency(self):
        if (self.published_at is not None) != (self.time_status == 'parsed'):
            raise ValueError('published_at requires parsed time status')
        return self


class FieldAnnotation(Contract):
    status: Literal['accepted', 'abstained', 'failed', 'missing'] = 'missing'
    value: str | float | None = None
    reason: str | None = None
    probability: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)

    @model_validator(mode='after')
    def value_consistency(self):
        if (self.status == 'accepted') != (self.value is not None):
            raise ValueError('only accepted fields carry values')
        return self


class AnnotationRecord(Contract):
    post_id: Identifier
    schema_version: Identifier
    model_version: str
    prompt_version: str | None = None
    target_id: Identifier | None = None
    topic: FieldAnnotation = Field(default_factory=FieldAnnotation)
    publisher: FieldAnnotation = Field(default_factory=FieldAnnotation)
    emotion: FieldAnnotation = Field(default_factory=FieldAnnotation)
    sentiment: FieldAnnotation = Field(default_factory=FieldAnnotation)
    stance: FieldAnnotation = Field(default_factory=FieldAnnotation)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode='after')
    def stance_target(self):
        if self.stance.status == 'accepted':
            if not self.target_id or self.stance.value not in ('support', 'oppose', 'neutral'):
                raise ValueError('stance needs a target and support/oppose/neutral value')
        if self.sentiment.status == 'accepted':
            if not isinstance(self.sentiment.value, (int, float)) or not -1 <= self.sentiment.value <= 1:
                raise ValueError('sentiment encoding must be in [-1, 1]')
        return self
