"""Public contracts for the complete event workflow, independent of any UI/runtime."""

from typing import Literal
from pydantic import Field, model_validator
from .base import Contract, Identifier, UTCDateTime
from .event import EventSpec
from .agent_model import AgentModelConfig


class LabelOptions(Contract):
    @model_validator(mode="before")
    @classmethod
    def provider_defaults(cls, value):
        if isinstance(value, dict):
            value = dict(value)
            defaults = {
                "openai_decisions": ("gpt-6-luna", 1),
                "jev": ("jev-latest", 1),
                "aliyun_decision": ("decision-model-preview", 1),
            }
            provider = value.get("provider", "openai_decisions")
            if provider in defaults:
                model, batch = defaults[provider]
                value.setdefault("model", model)
                value.setdefault("batch_size", batch)
        return value

    model: str = "gpt-6-luna"
    provider: Literal["openai_decisions", "jev", "aliyun_decision", "connector"] = (
        "openai_decisions"
    )
    connector: Identifier | None = None
    confidence_threshold: float = Field(default=0.7, ge=0, le=1)
    batch_size: int = Field(default=1, ge=1, le=100)
    max_calls: int = Field(default=100, ge=1)
    max_schema_calls: int = Field(default=4, ge=2)
    probability_margin: float = Field(default=0.10, ge=0, le=1)
    max_images_per_post: int = Field(default=3, ge=1, le=9)

    @model_validator(mode="after")
    def decision_protocol(self):
        if self.provider == "openai_decisions" and (
            self.model != "gpt-6-luna" or self.batch_size != 1
        ):
            raise ValueError("OpenAI Decisions requires gpt-6-luna and batch_size=1")
        return self


class SamplingSpec(Contract):
    sample_size: int = Field(default=30, ge=1, le=100)
    high_read_quantile: float = Field(default=0.75, ge=0, le=1)
    seed: int = Field(default=42, ge=0)
    missing_reads: Literal["uniform", "error"] = "uniform"


class AnalysisOptions(Contract):
    tools: list[str] = Field(default_factory=list, max_length=50)
    max_tool_calls: int = Field(default=24, ge=1, le=100)
    forum_roles: list[Literal["data", "search", "visual", "insight", "methodology"]] = (
        Field(
            default_factory=lambda: [
                "data",
                "search",
                "visual",
                "insight",
                "methodology",
            ]
        )
    )
    instruction: str = Field(default="", max_length=8000)
    theory_ids: list[str] = Field(
        default_factory=lambda: ["framing", "agenda_setting", "risk_communication"]
    )


class CrawlSpec(Contract):
    platforms: list[Literal['wb', 'xhs', 'dy', 'ks', 'bili', 'tieba', 'zhihu']] = Field(min_length=1, max_length=7)
    max_posts: int = Field(default=500, ge=1, le=100000)
    max_comments: int = Field(default=0, ge=0, le=100000)
    max_pages: int = Field(default=100, ge=1, le=10000)
    interval_seconds: float = Field(default=2, ge=0, le=3600)
    max_retries: int = Field(default=2, ge=0, le=2)
    session_ref: Identifier | None = None
    collect_images: bool = True
    max_images_per_post: int = Field(default=3, ge=1, le=9)
    max_comments_per_post: int = Field(default=20, ge=1, le=1000)
    include_sub_comments: bool = False


class ObservationSpec(Contract):
    start: UTCDateTime
    end: UTCDateTime
    window_seconds: int = Field(default=86400, ge=60)
    kinds: list[Literal["post", "comment"]] = Field(default_factory=lambda: ["post"])
    platforms: list[str] = Field(default_factory=list)
    topic_ids: list[Identifier] = Field(default_factory=list)
    bins: int = Field(default=10, ge=2, le=100)

    @model_validator(mode="after")
    def bounds(self):
        if (
            self.end <= self.start
            or (self.end - self.start).total_seconds() / self.window_seconds > 10000
        ):
            raise ValueError("require positive range and at most 10000 windows")
        return self


class ModelSpec(Contract):
    algorithm: Literal[
        "latent_hk_enkf",
        "joint_hk_enkf",
        "coordinate_hk_enkf",
        "hk_without_assimilation",
    ] = "latent_hk_enkf"
    latent_dimensions: int = Field(default=6, ge=1, le=64)
    calibrate: bool = True
    epsilon_candidates: list[float] = Field(
        default_factory=lambda: [0.2, 0.6, 1.0], min_length=1, max_length=8
    )
    relaxation_candidates: list[float] = Field(
        default_factory=lambda: [0.25, 0.5, 0.75], min_length=1, max_length=8
    )
    particles: int = Field(default=64, ge=8, le=512)
    ensemble_size: int = Field(default=16, ge=4, le=128)
    epsilon: float = Field(default=0.6, gt=0, le=4)
    relaxation: float = Field(default=0.5, ge=0, le=1)
    process_noise: float = Field(default=0.01, ge=0, le=0.5)
    observation_noise: float = Field(default=0.02, gt=0, le=1)
    horizon: int = Field(default=7, ge=1, le=100)
    seed: int = Field(default=42, ge=0)
    training_cutoff: UTCDateTime


class ScenarioSpec(Contract):
    scenario_id: Identifier
    dimension: Literal["stance", "sentiment"] = "stance"
    start_step: int = Field(default=1, ge=1)
    duration: int = Field(default=1, ge=1)
    shift: float = Field(default=0, ge=-2, le=2)
    assumptions: list[str] = Field(min_length=1)
    measure: str = Field(default="条件状态偏移", max_length=500)
    mechanism: Literal["state_shift", "confidence_change", "relaxation_change"] = (
        "state_shift"
    )
    parameter_value: float | None = Field(default=None, ge=0, le=4)
    resource_cost: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def mechanism_bounds(self):
        if self.mechanism != "state_shift" and self.parameter_value is None:
            raise ValueError("parameter interventions require parameter_value")
        if self.mechanism == "relaxation_change" and self.parameter_value > 1:
            raise ValueError("relaxation must be in [0,1]")
        if self.mechanism == "confidence_change" and self.parameter_value <= 0:
            raise ValueError("confidence bound must be positive")
        return self


class RunRequest(Contract):
    event: EventSpec
    run_id: Identifier
    labels: LabelOptions = Field(default_factory=LabelOptions)
    agent_model: str | None = Field(default=None, min_length=1, max_length=160)
    agent_config: AgentModelConfig | None = None
    crawl: CrawlSpec | None = None
    observations: ObservationSpec
    sampling: SamplingSpec = Field(default_factory=SamplingSpec)
    analysis: AnalysisOptions = Field(default_factory=AnalysisOptions)
    model: ModelSpec | None = None
    scenarios: list[ScenarioSpec] = Field(default_factory=list, max_length=20)
    forum_rounds: int = Field(default=3, ge=0, le=8)
    max_total_calls: int = Field(default=120, ge=1, le=100000)
    max_cost: float | None = Field(default=None, ge=0)
    media_mode: Literal["text_only", "image_only", "text_image"] = "text_image"

    @model_validator(mode="after")
    def route(self):
        if self.event.requires_collection and not any(k.strip() for k in self.event.keywords):
            raise ValueError("keyword collection requires search keywords")
        if self.labels.provider == "connector" and not self.labels.connector:
            raise ValueError("label connector ID required")
        if (
            self.labels.provider in {"jev", "aliyun_decision"}
            and self.labels.batch_size != 1
        ):
            raise ValueError(
                "System One labeling requires batch_size=1; five questions share each request"
            )
        if len(self.analysis.tools) > self.analysis.max_tool_calls:
            raise ValueError("tool budget must cover every explicitly selected tool")
        if (
            self.forum_rounds
            and "retrospective" in self.event.objectives
            and not self.analysis.forum_roles
        ):
            raise ValueError("select at least one forum role or disable the forum")
        if len(set(self.analysis.forum_roles)) != len(self.analysis.forum_roles):
            raise ValueError("forum roles must be unique")
        if self.event.requires_collection and (
            not self.event.start or not self.event.end
        ):
            raise ValueError("keyword collection requires an explicit time interval")
        if self.event.requires_collection != (self.crawl is not None):
            raise ValueError("only keyword input requires a CrawlSpec")
        if self.scenarios and self.model is None:
            raise ValueError("scenarios require a numerical model")
        if self.observations.end > self.event.as_of:
            raise ValueError("observation cutoff cannot exceed event as_of")
        if (
            self.model
            and not self.observations.start
            < self.model.training_cutoff
            <= self.observations.end
        ):
            raise ValueError("training cutoff must fall within observation range")
        unknown = set(self.event.objectives) - {
            "retrospective",
            "forecast",
            "scenario",
            "backtest",
        }
        if unknown or (
            set(self.event.objectives) & {"forecast", "scenario", "backtest"}
            and self.model is None
        ):
            raise ValueError("invalid objectives or missing model configuration")
        if not self.event.objectives or len(set(self.event.objectives)) != len(
            self.event.objectives
        ):
            raise ValueError("select unique research stages")
        if "scenario" in self.event.objectives and not self.scenarios:
            raise ValueError("scenario stage requires at least one intervention")
        if self.scenarios and "scenario" not in self.event.objectives:
            raise ValueError("interventions require selecting the scenario stage")
        if self.model:
            if any(v <= 0 or v > 4 for v in self.model.epsilon_candidates):
                raise ValueError("invalid confidence calibration grid")
            if any(v < 0 or v > 1 for v in self.model.relaxation_candidates):
                raise ValueError("invalid relaxation calibration grid")
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
    scheduler: Literal["domain_runtime"] = "domain_runtime"
