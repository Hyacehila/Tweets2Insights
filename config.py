"""
Configuration loader and shared-store builder.

Uses a YAML file as the single source of truth for runtime settings.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import os

import yaml


@dataclass
class DataConfig:
    input_path: str = "data/posts.json"
    output_path: str = "data/enhanced_posts.json"
    resume_if_exists: bool = True
    topics_path: str = "data/topics.json"
    sentiment_attributes_path: str = "data/sentiment_attributes.json"
    publisher_objects_path: str = "data/publisher_objects.json"
    belief_system_path: str = "data/believe_system_common.json"


@dataclass
class PipelineConfig:
    start_stage: int = 1
    user_analysis_instruction: str = ""


@dataclass
class Stage1CheckpointConfig:
    enabled: bool = True
    save_every: int = 100
    min_interval_seconds: float = 20.0


@dataclass
class Stage1NlpConfig:
    enabled: bool = True
    keyword_top_n: int = 8
    similarity_threshold: float = 0.85
    min_cluster_size: int = 2


@dataclass
class Stage1Config:
    mode: str = "async"
    checkpoint: Stage1CheckpointConfig = field(default_factory=Stage1CheckpointConfig)
    nlp: Stage1NlpConfig = field(default_factory=Stage1NlpConfig)


@dataclass
class Stage2Config:
    mode: str = "agent"
    tool_source: str = "mcp"
    agent_max_iterations: int = 10
    search_reflection_max_rounds: int = 2
    forum_max_rounds: int = 5
    forum_min_rounds_for_sufficient: int = 2
    search_provider: str = "tavily"
    search_max_results: int = 5
    search_timeout_seconds: int = 20
    search_api_key: str = ""
    chart_min_per_category: Dict[str, int] = field(default_factory=lambda: {
        "sentiment": 1,
        "topic": 1,
        "geographic": 1,
        "interaction": 1,
        "nlp": 1,
    })
    chart_tool_policy: str = "coverage_first"
    chart_tool_allowlist: List[str] = field(default_factory=list)
    chart_missing_policy: str = "warn"


@dataclass
class Stage3Config:
    max_iterations: int = 5
    chapter_review_max_rounds: int = 2


@dataclass
class RuntimeConfig:
    concurrent_num: int = 60
    max_retries: int = 3
    wait_time: int = 8


@dataclass
class LLMConfig:
    glm_api_key: str = ""
    acceptance_profile: str = "fast"
    reasoning_enabled_stage2: Optional[bool] = None
    reasoning_enabled_stage3: Optional[bool] = None
    vision_thinking_enabled: Optional[bool] = None
    request_timeout_seconds: int = 120


@dataclass
class AppConfig:
    data: DataConfig = field(default_factory=DataConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    stage1: Stage1Config = field(default_factory=Stage1Config)
    stage2: Stage2Config = field(default_factory=Stage2Config)
    stage3: Stage3Config = field(default_factory=Stage3Config)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)


def load_config(path: str) -> AppConfig:
    """Load YAML configuration into AppConfig."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    data_raw = dict(raw.get("data", {}) or {})
    data_raw.pop("publisher_decision_path", None)
    data = DataConfig(**data_raw)
    pipeline = PipelineConfig(**(raw.get("pipeline", {}) or {}))

    stage1_raw = raw.get("stage1", {}) or {}
    checkpoint = Stage1CheckpointConfig(**(stage1_raw.get("checkpoint", {}) or {}))
    nlp_cfg = Stage1NlpConfig(**(stage1_raw.get("nlp", {}) or {}))
    stage1 = Stage1Config(
        mode=stage1_raw.get("mode", Stage1Config().mode),
        checkpoint=checkpoint,
        nlp=nlp_cfg,
    )

    stage2 = Stage2Config(**(raw.get("stage2", {}) or {}))
    stage3_raw = dict(raw.get("stage3", {}) or {})
    stage3_raw.pop("min_score", None)  # backward compatibility for legacy configs
    stage3 = Stage3Config(**stage3_raw)
    runtime = RuntimeConfig(**(raw.get("runtime", {}) or {}))
    llm = LLMConfig(**(raw.get("llm", {}) or {}))
    env_profile = os.environ.get("ACCEPTANCE_PROFILE", "").strip().lower()
    if env_profile:
        llm.acceptance_profile = env_profile

    return AppConfig(
        data=data,
        pipeline=pipeline,
        stage1=stage1,
        stage2=stage2,
        stage3=stage3,
        runtime=runtime,
        llm=llm,
    )


def _derive_effective_start_stage(data: DataConfig, pipeline: PipelineConfig) -> int:
    """
    Return the explicit pipeline entry stage from config.yaml.

    ``data.resume_if_exists`` is consumed by Stage1 data loading only; it must
    not silently rewrite the user's selected pipeline entry stage.
    """
    return pipeline.start_stage


def _derive_data_source_type(effective_start_stage: int) -> str:
    if effective_start_stage == 1:
        return "original"
    return "enhanced"


def _resolve_llm_controls(llm: LLMConfig) -> Dict[str, object]:
    profile = str(llm.acceptance_profile or "fast").strip().lower()
    if profile == "quality":
        defaults = {
            "reasoning_enabled_stage2": True,
            "reasoning_enabled_stage3": True,
            "vision_thinking_enabled": True,
        }
    else:
        defaults = {
            "reasoning_enabled_stage2": False,
            "reasoning_enabled_stage3": False,
            "vision_thinking_enabled": False,
        }

    def _pick(value: Optional[bool], default: bool) -> bool:
        if value is None:
            return default
        return bool(value)

    return {
        "acceptance_profile": profile,
        "reasoning_enabled_stage2": _pick(llm.reasoning_enabled_stage2, defaults["reasoning_enabled_stage2"]),
        "reasoning_enabled_stage3": _pick(llm.reasoning_enabled_stage3, defaults["reasoning_enabled_stage3"]),
        "vision_thinking_enabled": _pick(llm.vision_thinking_enabled, defaults["vision_thinking_enabled"]),
        "request_timeout_seconds": max(1, int(llm.request_timeout_seconds or 120)),
    }


def validate_config(config: AppConfig) -> None:
    """Validate configuration constraints and prerequisites."""
    valid_stage1_modes = {"async"}
    valid_stage2_modes = {"agent"}
    valid_tool_sources = {"mcp"}

    if config.stage1.mode not in valid_stage1_modes:
        raise ValueError(f"Invalid stage1 mode: {config.stage1.mode}")
    if config.stage2.mode not in valid_stage2_modes:
        raise ValueError(
            f"Invalid stage2 mode: {config.stage2.mode}. Stage2 only supports agent mode."
        )
    if config.stage2.tool_source not in valid_tool_sources:
        raise ValueError(
            f"Invalid stage2 tool_source: {config.stage2.tool_source}. Stage2 only supports mcp tools."
        )

    effective_key = resolve_glm_api_key(config)
    if not effective_key:
        raise EnvironmentError(
            "GLM API key is required (set env GLM_API_KEY or llm.glm_api_key in YAML)."
        )

    start_stage = config.pipeline.start_stage
    if start_stage not in {1, 2, 3}:
        raise ValueError(f"start_stage must be one of [1,2,3], got {start_stage}")
    if not isinstance(config.pipeline.user_analysis_instruction, str):
        raise ValueError("pipeline.user_analysis_instruction must be a string")

    needs_stage2_output = start_stage > 1
    if needs_stage2_output and not os.path.exists(config.data.output_path):
        raise FileNotFoundError(f"Stage2 requires enhanced data file: {config.data.output_path}")

    needs_stage3_output = start_stage > 2
    if needs_stage3_output:
        required_files = [
            "report/analysis_data.json",
            "report/chart_analyses.json",
            "report/insights.json",
        ]
        missing_files = [p for p in required_files if not os.path.exists(p)]
        if missing_files:
            raise FileNotFoundError(f"Stage3 requires analysis outputs: {missing_files}")

    if config.stage2.mode == "agent" and config.stage2.tool_source == "mcp":
        if not os.environ.get("ENHANCED_DATA_PATH"):
            raise EnvironmentError("ENHANCED_DATA_PATH must be set for agent+mcp mode")

    llm_profile = str(config.llm.acceptance_profile or "fast").strip().lower()
    if llm_profile not in {"fast", "quality"}:
        raise ValueError("llm.acceptance_profile must be one of ['fast', 'quality']")
    for field_name in (
        "reasoning_enabled_stage2",
        "reasoning_enabled_stage3",
        "vision_thinking_enabled",
    ):
        value = getattr(config.llm, field_name)
        if value is not None and not isinstance(value, bool):
            raise ValueError(f"llm.{field_name} must be bool or null")
    if int(config.llm.request_timeout_seconds) <= 0:
        raise ValueError("llm.request_timeout_seconds must be >= 1")

    if config.stage2.chart_tool_policy not in {"coverage_first"}:
        raise ValueError(f"Invalid stage2 chart_tool_policy: {config.stage2.chart_tool_policy}")
    if config.stage2.chart_missing_policy not in {"warn", "fail"}:
        raise ValueError(f"Invalid stage2 chart_missing_policy: {config.stage2.chart_missing_policy}")
    if config.stage2.search_provider not in {"tavily", "deepseek"}:
        raise ValueError(f"Invalid stage2 search_provider: {config.stage2.search_provider}")
    if int(config.stage2.search_max_results) <= 0:
        raise ValueError("stage2.search_max_results must be >= 1")
    if int(config.stage2.search_timeout_seconds) <= 0:
        raise ValueError("stage2.search_timeout_seconds must be >= 1")
    if int(config.stage2.search_reflection_max_rounds) <= 0:
        raise ValueError("stage2.search_reflection_max_rounds must be >= 1")
    if int(config.stage2.forum_max_rounds) <= 0:
        raise ValueError("stage2.forum_max_rounds must be >= 1")
    if int(config.stage2.forum_min_rounds_for_sufficient) <= 0:
        raise ValueError("stage2.forum_min_rounds_for_sufficient must be >= 1")
    if int(config.stage2.forum_min_rounds_for_sufficient) > int(config.stage2.forum_max_rounds):
        raise ValueError("stage2.forum_min_rounds_for_sufficient must be <= stage2.forum_max_rounds")

    if int(config.stage3.max_iterations) <= 0:
        raise ValueError("stage3.max_iterations must be >= 1")
    if int(config.stage3.chapter_review_max_rounds) <= 0:
        raise ValueError("stage3.chapter_review_max_rounds must be >= 1")

    if not isinstance(config.stage2.chart_min_per_category, dict):
        raise ValueError("stage2.chart_min_per_category must be a dict")
    for key, value in config.stage2.chart_min_per_category.items():
        try:
            value_int = int(value)
        except Exception:
            raise ValueError(f"stage2.chart_min_per_category[{key}] must be int")
        if value_int < 0:
            raise ValueError(f"stage2.chart_min_per_category[{key}] must be >= 0")


def config_to_shared(config: AppConfig) -> dict:
    """Convert AppConfig into the shared store structure used by nodes."""
    effective_start_stage = _derive_effective_start_stage(config.data, config.pipeline)
    data_source_type = _derive_data_source_type(effective_start_stage)
    llm_controls = _resolve_llm_controls(config.llm)

    shared = {
        "data": {
            "blog_data": [],
            "topics_hierarchy": [],
            "sentiment_attributes": [],
            "publisher_objects": [],
            "data_paths": {
                "blog_data_path": config.data.input_path,
                "topics_path": config.data.topics_path,
                "sentiment_attributes_path": config.data.sentiment_attributes_path,
                "publisher_objects_path": config.data.publisher_objects_path,
                "belief_system_path": config.data.belief_system_path,
            },
        },
        "pipeline_state": {
            "start_stage": effective_start_stage,
            "current_stage": 0,
            "completed_stages": [],
        },
        "analysis_context": {
            "user_analysis_instruction": str(config.pipeline.user_analysis_instruction or "").strip(),
            "time_range": None,
            "time_range_text": "",
        },
        "config": {
            "pipeline": {
                "start_stage": effective_start_stage,
                "user_analysis_instruction": str(config.pipeline.user_analysis_instruction or "").strip(),
            },
            "enhancement_mode": config.stage1.mode,
            "stage1_checkpoint": {
                "enabled": config.stage1.checkpoint.enabled,
                "save_every": config.stage1.checkpoint.save_every,
                "min_interval_seconds": config.stage1.checkpoint.min_interval_seconds,
            },
            "stage1_nlp": {
                "enabled": config.stage1.nlp.enabled,
                "keyword_top_n": config.stage1.nlp.keyword_top_n,
                "similarity_threshold": config.stage1.nlp.similarity_threshold,
                "min_cluster_size": config.stage1.nlp.min_cluster_size,
            },
            "analysis_mode": config.stage2.mode,
            "tool_source": config.stage2.tool_source,
            "stage2_chart": {
                "min_per_category": (config.stage2.chart_min_per_category or {
                    "sentiment": 1,
                    "topic": 1,
                    "geographic": 1,
                    "interaction": 1,
                    "nlp": 1,
                }),
                "tool_policy": config.stage2.chart_tool_policy,
                "tool_allowlist": list(config.stage2.chart_tool_allowlist or []),
                "missing_policy": config.stage2.chart_missing_policy,
            },
            "web_search": {
                "provider": config.stage2.search_provider,
                "max_results": int(config.stage2.search_max_results),
                "timeout_seconds": int(config.stage2.search_timeout_seconds),
                "api_key": config.stage2.search_api_key,
            },
            "agent_config": {"max_iterations": config.stage2.agent_max_iterations},
            "stage2_loops": {
                "agent_max_iterations": int(config.stage2.agent_max_iterations),
                "search_reflection_max_rounds": int(config.stage2.search_reflection_max_rounds),
                "forum_max_rounds": int(config.stage2.forum_max_rounds),
                "forum_min_rounds_for_sufficient": int(config.stage2.forum_min_rounds_for_sufficient),
            },
            "stage3_review": {
                "chapter_review_max_rounds": int(config.stage3.chapter_review_max_rounds),
            },
            "llm": llm_controls,
            "data_source": {
                "type": data_source_type,
                "resume_if_exists": config.data.resume_if_exists,
                "enhanced_data_path": config.data.output_path,
            },
        },
        "agent": {
            "available_tools": [],
            "execution_history": [],
            "current_iteration": 0,
            "max_iterations": config.stage2.agent_max_iterations,
            "is_finished": False,
        },
        "search": {
            "round": 0,
            "queries": [],
            "raw_results": [],
            "documents": [],
            "reflections": [],
            "total_results": 0,
        },
        "search_results": {
            "event_timeline": [],
            "key_actors": [],
            "official_responses": [],
            "public_reactions_summary": "",
            "related_events": [],
        },
        "agent_results": {
            "data_agent": {},
            "search_agent": {},
        },
        "forum": {
            "current_round": 0,
            "rounds": [],
            "current_directive": {},
            "visual_analyses": [],
        },
        "report": {
            "iteration": 0,
            "current_draft": "",
            "revision_feedback": "",
            "review_history": [],
        },
        "stage1_results": {
            "statistics": {
                "total_blogs": 0,
                "processed_blogs": 0,
                "empty_fields": {
                    "sentiment_polarity_empty": 0,
                    "sentiment_attribute_empty": 0,
                    "topics_empty": 0,
                    "publisher_empty": 0,
                },
                "engagement_statistics": {
                    "total_reposts": 0,
                    "total_comments": 0,
                    "total_likes": 0,
                    "avg_reposts": 0.0,
                    "avg_comments": 0.0,
                    "avg_likes": 0.0,
                },
                "user_statistics": {
                    "unique_users": 0,
                    "top_active_users": [],
                    "user_type_distribution": {},
                },
                "content_statistics": {
                    "total_images": 0,
                    "blogs_with_images": 0,
                    "avg_content_length": 0.0,
                    "time_distribution": {},
                },
                "geographic_distribution": {},
            },
            "data_save": {
                "saved": False,
                "output_path": "",
                "data_count": 0,
            },
        },
        "stage2_results": {
            "charts": [],
            "tables": [],
            "insights": {
                "sentiment_insight": "",
                "topic_insight": "",
                "geographic_insight": "",
                "cross_dimension_insight": "",
                "summary_insight": "",
            },
            "execution_log": {
                "tools_executed": [],
                "total_charts": 0,
                "total_tables": 0,
                "execution_time": 0.0,
                "charts_by_category": {},
            },
            "search_context": {},
            "output_files": {
                "charts_dir": "report/images/",
                "analysis_data": "report/analysis_data.json",
                "insights_file": "report/insights.json",
            },
        },
        "stage3_results": {
            "report_file": "report/report.md",
            "generation_mode": "unified",
            "iterations": 0,
            "final_score": 0,
            "report_reasoning": "",
            "data_citations": {},
            "hallucination_check": {},
        },
        "trace": {
            "decisions": [],
            "executions": [],
            "reflections": [],
            "insight_provenance": {},
            "loop_status": {},
        },
        "thinking": {
            "stage2_tool_decisions": [],
            "stage3_report_planning": [],
            "stage3_section_planning": {},
            "thinking_timestamps": [],
        },
    }

    return shared


def resolve_glm_api_key(config: AppConfig) -> str:
    """Resolve GLM API key with YAML taking precedence over environment."""
    yaml_key = (config.llm.glm_api_key or "").strip()
    if yaml_key:
        return yaml_key
    return os.environ.get("GLM_API_KEY", "").strip()


def apply_glm_api_key(config: AppConfig) -> None:
    """Apply GLM API key from config to environment when provided."""
    yaml_key = (config.llm.glm_api_key or "").strip()
    if yaml_key:
        os.environ["GLM_API_KEY"] = yaml_key
