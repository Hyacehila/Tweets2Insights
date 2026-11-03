"""
Pipeline console page: configure, validate, and run the pipeline.
"""
from __future__ import annotations

import threading
import os
import time
from datetime import datetime
from typing import List

import streamlit as st

from dashboard.api.pipeline_api import (
    apply_defaults,
    build_config_dict_from_form,
    list_data_candidates,
    load_config_dict,
    merge_config_dict,
    save_config_dict,
    validate_config_dict,
    run_pipeline,
)
from dashboard.api.status_api import read_status, write_status
from dashboard.logic.pipeline_console_logic import build_failure_status_payload, validate_pipeline_form
from utils.run_state import is_running, set_running


def _is_running() -> bool:
    return is_running()


def _set_running(flag: bool) -> None:
    set_running(flag)


def _run_pipeline_safe(config_path: str) -> None:
    try:
        run_pipeline(config_path, dry_run=False)
    except Exception as exc:
        current_status = read_status()
        status = build_failure_status_payload(
            current_status,
            error_message=str(exc),
            stage=str(current_status.get("current_stage", "")).strip(),
            now_utc=datetime.utcnow().isoformat(timespec="seconds") + "Z",
        )
        try:
            write_status(status)
        except Exception as write_exc:
            print(f"[PipelineConsole] 写入 status.json 失败: {write_exc}")
    finally:
        _set_running(False)


def _path_selector(label: str, current: str, options: List[str], key: str) -> str:
    custom_label = "Custom..."
    options = list(dict.fromkeys(options))  # stable unique
    if current and current not in options:
        options.append(current)

    select_options = options + [custom_label]
    if current and current in options:
        default_index = select_options.index(current)
    else:
        default_index = select_options.index(custom_label)

    selected = st.selectbox(label, select_options, index=default_index, key=key)
    if selected == custom_label:
        return st.text_input(f"{label} (custom)", value=current or "", key=f"{key}_custom").strip()
    return selected


def _safe_index(options: List[str] | List[int], value: str | int, fallback: int = 0) -> int:
    try:
        return options.index(value)
    except ValueError:
        return fallback


st.title("Pipeline Console")

config_path = st.text_input("Config Path", value="config.yaml", key="config_path")
raw_config = load_config_dict(config_path)
config = apply_defaults(raw_config)

data_candidates = list_data_candidates("data")

with st.form("config_form"):
    user_analysis_instruction = st.text_area(
        "User Analysis Instruction",
        value=str(config.get("pipeline", {}).get("user_analysis_instruction", "") or ""),
        placeholder="例如：重点分析官方回应时效性、公众质疑焦点与证据一致性。",
        help="该指令会注入到 Stage2/Stage3 智能体提示词中，用于定向分析重点。",
    )

    st.subheader("Key Settings")
    left, right = st.columns(2)

    with left:
        input_path = _path_selector(
            "Input data path",
            config["data"]["input_path"],
            data_candidates,
            key="input_path",
        )
        topics_path = _path_selector(
            "Topics path",
            config["data"]["topics_path"],
            data_candidates,
            key="topics_path",
        )
        sentiment_attributes_path = _path_selector(
            "Sentiment attributes path",
            config["data"]["sentiment_attributes_path"],
            data_candidates,
            key="sentiment_attributes_path",
        )
        publisher_objects_path = _path_selector(
            "Publisher objects path",
            config["data"]["publisher_objects_path"],
            data_candidates,
            key="publisher_objects_path",
        )
        belief_system_path = _path_selector(
            "Belief system path",
            config["data"]["belief_system_path"],
            data_candidates,
            key="belief_system_path",
        )

    with right:
        output_path = _path_selector(
            "Enhanced data output path",
            config["data"]["output_path"],
            data_candidates,
            key="output_path",
        )
        publisher_decision_path = _path_selector(
            "Publisher decision path",
            config["data"]["publisher_decision_path"],
            data_candidates,
            key="publisher_decision_path",
        )

        start_stage = st.selectbox(
            "Start stage",
            [1, 2, 3],
            index=_safe_index([1, 2, 3], config["pipeline"]["start_stage"], fallback=0),
        )

        st.markdown("**Stage2**: `agent + mcp` (fixed)")
        st.markdown("**Stage3**: `unified report` (fixed)")

    with st.expander("Advanced settings", expanded=False):
        st.markdown("**LLM settings**")
        acceptance_profile = st.selectbox(
            "LLM acceptance profile",
            ["fast", "quality"],
            index=_safe_index(
                ["fast", "quality"],
                str(config.get("llm", {}).get("acceptance_profile", "fast") or "fast"),
                fallback=0,
            ),
            help="fast: disable reasoning/thinking to reduce cost and runtime; quality: enable richer reasoning.",
        )
        reasoning_enabled_stage2 = st.checkbox(
            "LLM reasoning enabled (Stage 2)",
            value=bool(config.get("llm", {}).get("reasoning_enabled_stage2", False)),
        )
        reasoning_enabled_stage3 = st.checkbox(
            "LLM reasoning enabled (Stage 3)",
            value=bool(config.get("llm", {}).get("reasoning_enabled_stage3", False)),
        )
        vision_thinking_enabled = st.checkbox(
            "LLM vision thinking enabled (Stage 2 visual)",
            value=bool(config.get("llm", {}).get("vision_thinking_enabled", False)),
        )
        request_timeout_seconds = st.number_input(
            "LLM request timeout (seconds)",
            min_value=1,
            step=1,
            value=int(config.get("llm", {}).get("request_timeout_seconds", 120)),
            help="Applied to GLM requests across Stage2/Stage3.",
        )
        glm_api_key = st.text_input(
            "GLM API Key",
            value=config.get("llm", {}).get("glm_api_key", ""),
            type="password",
            help="Saved to config.yaml in plaintext. YAML value overrides GLM_API_KEY env.",
        )

        st.markdown("**Data source**")
        resume_if_exists = st.checkbox(
            "Resume if enhanced data exists",
            value=bool(config["data"].get("resume_if_exists", True)),
        )

        st.markdown("**Runtime settings**")
        concurrent_num = st.number_input(
            "Runtime concurrent num",
            min_value=1,
            step=1,
            value=int(config["runtime"]["concurrent_num"]),
        )
        max_retries = st.number_input(
            "Runtime max retries",
            min_value=0,
            step=1,
            value=int(config["runtime"]["max_retries"]),
        )
        wait_time = st.number_input(
            "Runtime wait time (seconds)",
            min_value=0,
            step=1,
            value=int(config["runtime"]["wait_time"]),
        )

        st.markdown("**Stage 1**")
        stage1_mode = st.selectbox(
            "Stage1 mode",
            ["async"],
            index=0,
        )
        checkpoint_enabled = st.checkbox(
            "Stage1 checkpoint enabled",
            value=bool(config["stage1"]["checkpoint"]["enabled"]),
        )
        checkpoint_save_every = st.number_input(
            "Stage1 checkpoint save every",
            min_value=1,
            step=1,
            value=int(config["stage1"]["checkpoint"]["save_every"]),
        )
        checkpoint_min_interval = st.number_input(
            "Stage1 checkpoint min interval (seconds)",
            min_value=0.0,
            step=1.0,
            value=float(config["stage1"]["checkpoint"]["min_interval_seconds"]),
        )
        nlp_enabled = st.checkbox(
            "Stage1 NLP enabled",
            value=bool(config["stage1"]["nlp"]["enabled"]),
        )
        nlp_keyword_top_n = st.number_input(
            "Stage1 NLP keyword top N",
            min_value=1,
            step=1,
            value=int(config["stage1"]["nlp"]["keyword_top_n"]),
        )
        nlp_similarity = st.number_input(
            "Stage1 NLP similarity threshold",
            min_value=0.0,
            max_value=1.0,
            step=0.01,
            value=float(config["stage1"]["nlp"]["similarity_threshold"]),
        )
        nlp_min_cluster = st.number_input(
            "Stage1 NLP min cluster size",
            min_value=1,
            step=1,
            value=int(config["stage1"]["nlp"]["min_cluster_size"]),
        )

        st.markdown("**Stage 2**")
        agent_max_iterations = st.number_input(
            "Stage2 agent max iterations",
            min_value=1,
            step=1,
            value=int(config["stage2"]["agent_max_iterations"]),
        )
        search_reflection_max_rounds = st.number_input(
            "Stage2 search reflection max rounds",
            min_value=1,
            step=1,
            value=int(config["stage2"].get("search_reflection_max_rounds", 2)),
        )
        forum_max_rounds = st.number_input(
            "Stage2 forum max rounds",
            min_value=1,
            step=1,
            value=int(config["stage2"].get("forum_max_rounds", 5)),
        )
        forum_min_rounds_for_sufficient = st.number_input(
            "Stage2 forum min rounds for sufficient",
            min_value=1,
            step=1,
            value=int(config["stage2"].get("forum_min_rounds_for_sufficient", 2)),
        )
        search_provider = st.selectbox(
            "Stage2 search provider",
            ["tavily", "deepseek"],
            index=_safe_index(["tavily", "deepseek"], config["stage2"].get("search_provider", "tavily"), fallback=0),
        )
        search_max_results = st.number_input(
            "Stage2 search max results",
            min_value=1,
            step=1,
            value=int(config["stage2"].get("search_max_results", 5)),
        )
        search_timeout_seconds = st.number_input(
            "Stage2 search timeout (seconds)",
            min_value=1,
            step=1,
            value=int(config["stage2"].get("search_timeout_seconds", 20)),
        )
        search_api_key = st.text_input(
            f"Stage2 {search_provider} API Key",
            value=config["stage2"].get("search_api_key", "") if search_provider == config["stage2"].get("search_provider", "tavily") else "",
            key=f"search_key_{search_provider}",
            type="password",
            help=f"Selected provider only. Empty uses {search_provider.upper()}_API_KEY. Saved locally in config.yaml.",
        )
        chart_missing_policy = st.selectbox(
            "Stage2 chart missing policy",
            ["warn", "fail"],
            index=_safe_index(["warn", "fail"], config["stage2"].get("chart_missing_policy", "warn")),
            help="warn: continue with warning; fail: stop when chart coverage is missing.",
        )

        stage2_chart_min = config["stage2"].get("chart_min_per_category", {}) or {}
        chart_min_sentiment = st.number_input(
            "Stage2 min sentiment charts",
            min_value=0,
            step=1,
            value=int(stage2_chart_min.get("sentiment", 1)),
        )
        chart_min_topic = st.number_input(
            "Stage2 min topic charts",
            min_value=0,
            step=1,
            value=int(stage2_chart_min.get("topic", 1)),
        )
        chart_min_geographic = st.number_input(
            "Stage2 min geographic charts",
            min_value=0,
            step=1,
            value=int(stage2_chart_min.get("geographic", 1)),
        )
        chart_min_interaction = st.number_input(
            "Stage2 min interaction charts",
            min_value=0,
            step=1,
            value=int(stage2_chart_min.get("interaction", 1)),
        )
        chart_min_nlp = st.number_input(
            "Stage2 min NLP charts",
            min_value=0,
            step=1,
            value=int(stage2_chart_min.get("nlp", 1)),
        )

        st.markdown("**Stage 3**")
        report_max_iterations = st.number_input(
            "Stage3 report max iterations",
            min_value=1,
            step=1,
            value=int(config["stage3"]["max_iterations"]),
        )
        chapter_review_max_rounds = st.number_input(
            "Stage3 chapter review max rounds",
            min_value=1,
            step=1,
            value=int(config["stage3"].get("chapter_review_max_rounds", 2)),
        )

    col1, col2, col3 = st.columns(3)
    save_clicked = col1.form_submit_button("Save Config")
    dry_run_clicked = col2.form_submit_button("Dry Run")
    run_clicked = col3.form_submit_button("Start Analysis")


flat_config = {
    "data.input_path": input_path,
    "data.output_path": output_path,
    "data.resume_if_exists": bool(resume_if_exists),
    "data.topics_path": topics_path,
    "data.sentiment_attributes_path": sentiment_attributes_path,
    "data.publisher_objects_path": publisher_objects_path,
    "data.belief_system_path": belief_system_path,
    "data.publisher_decision_path": publisher_decision_path,
    "pipeline.start_stage": int(start_stage),
    "pipeline.user_analysis_instruction": user_analysis_instruction.strip(),
    "stage1.mode": stage1_mode,
    "stage1.checkpoint.enabled": bool(checkpoint_enabled),
    "stage1.checkpoint.save_every": int(checkpoint_save_every),
    "stage1.checkpoint.min_interval_seconds": float(checkpoint_min_interval),
    "stage1.nlp.enabled": bool(nlp_enabled),
    "stage1.nlp.keyword_top_n": int(nlp_keyword_top_n),
    "stage1.nlp.similarity_threshold": float(nlp_similarity),
    "stage1.nlp.min_cluster_size": int(nlp_min_cluster),
    "stage2.mode": "agent",
    "stage2.tool_source": "mcp",
    "stage2.agent_max_iterations": int(agent_max_iterations),
    "stage2.search_reflection_max_rounds": int(search_reflection_max_rounds),
    "stage2.forum_max_rounds": int(forum_max_rounds),
    "stage2.forum_min_rounds_for_sufficient": int(forum_min_rounds_for_sufficient),
    "stage2.search_provider": search_provider,
    "stage2.search_max_results": int(search_max_results),
    "stage2.search_timeout_seconds": int(search_timeout_seconds),
    "stage2.search_api_key": search_api_key,
    "stage2.chart_tool_policy": "coverage_first",
    "stage2.chart_missing_policy": chart_missing_policy,
    "stage2.chart_min_per_category.sentiment": int(chart_min_sentiment),
    "stage2.chart_min_per_category.topic": int(chart_min_topic),
    "stage2.chart_min_per_category.geographic": int(chart_min_geographic),
    "stage2.chart_min_per_category.interaction": int(chart_min_interaction),
    "stage2.chart_min_per_category.nlp": int(chart_min_nlp),
    "stage3.max_iterations": int(report_max_iterations),
    "stage3.chapter_review_max_rounds": int(chapter_review_max_rounds),
    "runtime.concurrent_num": int(concurrent_num),
    "runtime.max_retries": int(max_retries),
    "runtime.wait_time": int(wait_time),
    "llm.acceptance_profile": acceptance_profile,
    "llm.reasoning_enabled_stage2": bool(reasoning_enabled_stage2),
    "llm.reasoning_enabled_stage3": bool(reasoning_enabled_stage3),
    "llm.vision_thinking_enabled": bool(vision_thinking_enabled),
    "llm.request_timeout_seconds": int(request_timeout_seconds),
    "llm.glm_api_key": glm_api_key,
}

config_patch = build_config_dict_from_form(flat_config)
config_dict = merge_config_dict(raw_config, config_patch)
validation_errors: List[str] = validate_pipeline_form(flat_config)

if save_clicked or dry_run_clicked or run_clicked:
    if validation_errors:
        for err in validation_errors:
            st.error(err)
    else:
        if save_clicked:
            save_config_dict(config_dict, config_path)
            st.success("Config saved.")

        if dry_run_clicked:
            try:
                if output_path:
                    os.environ["ENHANCED_DATA_PATH"] = os.path.abspath(output_path)
                validate_config_dict(config_dict)
                st.success("Dry run validation passed.")
            except Exception as exc:
                st.error(f"Dry run failed: {exc}")

        if run_clicked:
            if _is_running():
                st.warning("Pipeline is already running.")
            else:
                try:
                    if output_path:
                        os.environ["ENHANCED_DATA_PATH"] = os.path.abspath(output_path)
                    validate_config_dict(config_dict)
                    save_config_dict(config_dict, config_path)
                except Exception as exc:
                    st.error(f"Cannot start: {exc}")
                else:
                    _set_running(True)
                    thread = threading.Thread(
                        target=_run_pipeline_safe,
                        args=(config_path,),
                        daemon=True,
                    )
                    thread.start()
                    st.success("Pipeline started.")

st.subheader("Status")
status = read_status()
stage_col, node_col = st.columns(2)
with stage_col:
    st.metric("Current Stage", status.get("current_stage", ""))
with node_col:
    st.metric("Current Node", status.get("current_node", ""))

events = status.get("events", [])
if events:
    st.subheader("Recent Events")
    st.dataframe(events[-50:], width="stretch")

failed_events = [item for item in events if item.get("event") == "exit" and item.get("status") == "failed"]
if failed_events:
    st.subheader("Failed Exits")
    st.dataframe(failed_events[-20:], width="stretch")

auto_refresh = st.toggle("Auto refresh", value=True, key="pipeline_auto_refresh")
if auto_refresh:
    time.sleep(2)
    st.rerun()
