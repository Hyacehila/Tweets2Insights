"""
舆情分析智能体 - 节点定义

根据设计文档, 系统采用中央调度+三阶段顺序依赖架构。
本文件包含所有节点定义, 按以下结构组织:

跨平台路径处理工具:
"""
import os
from pathlib import Path

def normalize_path(path: str) -> str:
    """
    标准化路径为相对于项目根目录的正斜杠路径

    Args:
        path: 输入路径（可能是绝对路径、相对路径或Windows/Unix格式）

    Returns:
        str: 标准化的相对路径, 使用正斜杠
    """
    if not path:
        return path

    # 转换为Path对象以处理路径分隔符
    p = Path(path)

    # 如果是绝对路径, 先转换为相对于当前工作目录的路径
    if p.is_absolute():
        try:
            p = p.relative_to(Path.cwd())
        except ValueError:
            # 如果无法转换为相对路径, 保持原样但使用正斜杠
            return str(p).replace('\\', '/')

    # 转换为字符串并确保使用正斜杠
    normalized = str(p).replace('\\', '/')

    # 确保不以 ./ 开头（除非是当前目录）
    if normalized.startswith('./') and len(normalized) > 2:
        return normalized[2:]

    return normalized

def get_project_relative_path(absolute_path: str) -> str:
    """
    获取相对于项目根目录的路径

    Args:
        absolute_path: 绝对路径

    Returns:
        str: 相对路径, 使用正斜杠
    """
    project_root = Path.cwd()
    try:
        relative_path = Path(absolute_path).relative_to(project_root)
        return str(relative_path).replace('\\', '/')
    except ValueError:
        # 如果路径不在项目根目录下, 返回标准化路径
        return normalize_path(absolute_path)

def ensure_dir_exists(dir_path: str) -> None:
    """
    确保目录存在（跨平台兼容）

    Args:
        dir_path: 目录路径
    """
    Path(dir_path).mkdir(parents=True, exist_ok=True)


# =============================================================================
# 导入依赖
# =============================================================================

import json
import os
import asyncio
import subprocess
import time
import re
from typing import List, Dict, Any, Optional
from pocketflow import Node, BatchNode, AsyncNode, AsyncBatchNode
from utils.call_llm import call_glm_45_air, call_glm4v_plus, call_glm45v_thinking, call_glm46
from utils.data_loader import (
    load_blog_data, load_topics, load_sentiment_attributes,
    load_publisher_objects, save_enhanced_blog_data, load_enhanced_blog_data,
    load_belief_system
)

def _strip_timestamp_suffix(stem: str) -> str:
    return re.sub(r"_\d{8}_\d{6}$", "", stem)

def _build_chart_path_index(charts):
    allowed_paths = set()
    alias_to_path = {}

    for chart in charts or []:
        file_path = (
            chart.get("file_path")
            or chart.get("path")
            or chart.get("chart_path")
            or chart.get("image_path")
            or ""
        )
        if not file_path:
            continue
        filename = Path(file_path).name
        if not filename:
            continue
        rel_path = f"./images/{filename}"
        allowed_paths.add(rel_path)

        stem = Path(filename).stem
        base = _strip_timestamp_suffix(stem)
        if base:
            alias_to_path.setdefault(base, rel_path)

        source_tool = chart.get("source_tool") or ""
        if source_tool:
            tool_alias = source_tool.replace("_chart", "").replace("generate_", "")
            alias_to_path.setdefault(tool_alias, rel_path)

    return allowed_paths, alias_to_path

_MANUAL_IMAGE_ALIAS = {
    "sentiment_timeseries": "sentiment_trend",
    "sentiment_distribution": "sentiment_pie",
    "geographic_distribution": "geographic_bar",
    "geographic_hotspot": "geographic_heatmap",
    "publisher_distribution": "publisher_bar",
    "topic_frequency": "topic_ranking",
    "topic_cooccurrence": "topic_network",
    "geographic_sentiment": "geographic_sentiment_bar",
    "generate_sentiment_focus_window_chart": "sentiment_focus_window",
    "belief_network_chart": "belief_network",
    "influence_analysis": "publisher_bar",
}

def _remap_report_images(content, charts):
    if not content or not charts:
        return content

    allowed_paths, alias_to_path = _build_chart_path_index(charts)
    if not allowed_paths:
        return content

    def _replace(match):
        alt_text = match.group(1)
        raw_path = match.group(2).strip()
        clean_path = raw_path.replace("\\\\", "/")
        filename = Path(clean_path).name
        rel_path = f"./images/{filename}" if filename else clean_path

        if rel_path in allowed_paths:
            return f"![{alt_text}]({rel_path})"

        stem = Path(filename).stem if filename else Path(clean_path).stem
        target_path = alias_to_path.get(stem)
        if not target_path:
            alias = _MANUAL_IMAGE_ALIAS.get(stem)
            if alias:
                target_path = alias_to_path.get(alias)
        if not target_path:
            for alias_key, alias_path in alias_to_path.items():
                if alias_key and (alias_key in stem or stem in alias_key):
                    target_path = alias_path
                    break
        if not target_path:
            target_path = sorted(allowed_paths)[0]

        return f"![{alt_text}]({target_path})"

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _replace, content)

def _load_analysis_charts():
    try:
        with open("report/analysis_data.json", "r", encoding="utf-8") as f:
            return json.load(f).get("charts", [])
    except Exception:
        return []
