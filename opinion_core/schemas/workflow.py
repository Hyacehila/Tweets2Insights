"""Public contracts for the complete event workflow, independent of any UI/runtime."""
from typing import Literal
from pydantic import Field, model_validator
from .base import Contract, Identifier, UTCDateTime
from .event import EventSpec


class LabelOptions(Contract):
    model: str = 'glm-4.5-air'
    provider: Literal['glm', 'connector'] = 'glm'
    connector: Identifier | None = None
    confidence_threshold: float = Field(default=.7, ge=0, le=1)
    batch_size: int = Field(default=10, ge=1, le=100)
    max_calls: int = Field(default=100, ge=1)
    max_schema_calls: int = Field(default=4, ge=2)


class CrawlSpec(Contract):
    platforms: list[Identifier] = Field(min_length=1)
    max_posts: int = Field(default=500, ge=1, le=100000)
    max_comments: int = Field(default=0, ge=0, le=100000)
    max_pages: int = Field(default=100, ge=1, le=10000)
    interval_seconds: float = Field(default=2, ge=0, le=3600)
    max_retries: int = Field(default=2, ge=0, le=2)
    session_ref: Identifier | None = None


class ObservationSpec(Contract):
    start: UTCDateTime
    end: UTCDateTime
    window_seconds: int = Field(default=86400, ge=60)
    kinds: list[Literal['post', 'comment']] = Field(default_factory=lambda: ['post'])
    platforms: list[str] = Field(default_factory=list)
    topic_ids: list[Identifier] = Field(default_factory=list)
    bins: int = Field(default=10, ge=2, le=100)

    @model_validator(mode='after')
    def bounds(self):
        if self.end <= self.start or (self.end-self.start).total_seconds()/self.window_seconds > 10000:
            raise ValueError('require positive range and at most 10000 windows')
        return self


class ModelSpec(Contract):
    algorithm: Literal['joint_hk_enkf', 'coordinate_hk_enkf', 'hk_without_assimilation'] = 'joint_hk_enkf'
    particles: int = Field(default=64, ge=8, le=512)
    ensemble_size: int = Field(default=16, ge=4, le=128)
    epsilon: float = Field(default=.6, gt=0, le=4)
    relaxation: float = Field(default=.5, ge=0, le=1)
    process_noise: float = Field(default=.01, ge=0, le=.5)
    observation_noise: float = Field(default=.02, gt=0, le=1)
    horizon: int = Field(default=7, ge=1, le=100)
    seed: int = Field(default=42, ge=0)
    training_cutoff: UTCDateTime


class ScenarioSpec(Contract):
    scenario_id: Identifier
    dimension: Literal['stance', 'sentiment'] = 'stance'
    start_step: int = Field(default=1, ge=1)
    duration: int = Field(default=1, ge=1)
    shift: float = Field(default=0, ge=-2, le=2)
    assumptions: list[str] = Field(min_length=1)


class RunRequest(Contract):
    event: EventSpec
    run_id: Identifier
    labels: LabelOptions = Field(default_factory=LabelOptions)
    crawl: CrawlSpec | None = None
    observations: ObservationSpec
    model: ModelSpec | None = None
    scenarios: list[ScenarioSpec] = Field(default_factory=list, max_length=20)
    forum_rounds: int = Field(default=2, ge=0, le=2)
    max_total_calls: int = Field(default=120, ge=1, le=10000)
    max_cost: float | None = Field(default=None, ge=0)
    media_mode: Literal['text_only', 'image_only', 'text_image'] = 'text_only'

    @model_validator(mode='after')
    def route(self):
        if not any(k.strip() for k in self.event.keywords):
            raise ValueError('event keywords required for automatic schema preparation')
        if self.labels.provider=='connector' and not self.labels.connector:
            raise ValueError('label connector ID required')
        if self.media_mode!='text_only' and self.labels.provider!='connector':
            raise ValueError('nontext labeling requires a multimodal connector')
        if self.event.requires_collection != (self.crawl is not None):
            raise ValueError('only keyword input requires a CrawlSpec')
        if self.scenarios and self.model is None:
            raise ValueError('scenarios require a numerical model')
        if self.observations.end > self.event.as_of:
            raise ValueError('observation cutoff cannot exceed event as_of')
        if self.model and not self.observations.start < self.model.training_cutoff <= self.observations.end:
            raise ValueError('training cutoff must fall within observation range')
        unknown = set(self.event.objectives) - {'retrospective', 'forecast', 'scenario', 'backtest'}
        if unknown or (set(self.event.objectives) & {'forecast','scenario','backtest'} and self.model is None):
            raise ValueError('invalid objectives or missing model configuration')
        return self


class StageTask(Contract):
    task_id: Identifier
    role: str
    operation: str
    dependencies: list[Identifier] = Field(default_factory=list)


class TaskPlan(Contract):
    event_id: Identifier
    run_id: Identifier
    tasks: list[StageTask]
    scheduler: Literal['domain_runtime'] = 'domain_runtime'
