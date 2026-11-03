"""Stage-2 analytical tools on canonical records, with reproducible source tables.

Each call is pure, schema scoped and content addressed. Missing engagement/region
is never imputed to zero. Topic edges use discussion threads, not multi-label posts.
"""

from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations
from typing import Literal
import hashlib
import html
import json
import math
import numpy as np
from pydantic import Field
from opinion_core.schemas.base import Contract
from opinion_core.schemas.records import AnnotationRecord, PostRecord
from opinion_core.schemas.workflow import ObservationSpec
from .nlp.keyword_extractor import extract_keywords
from .nlp.ner import extract_entities
from .nlp.sentiment_lexicon import lexicon_sentiment

# name: (family, operation, display, default group, description)
TOOLS = {
    "sentiment_distribution_stats": (
        "sentiment",
        "distribution",
        "bar",
        "sentiment",
        "情绪分布、均值与分位数",
    ),
    "sentiment_time_series": (
        "sentiment",
        "trend",
        "line",
        "sentiment",
        "固定窗口情绪均值",
    ),
    "sentiment_anomaly_detection": (
        "sentiment",
        "anomaly",
        "line",
        "sentiment",
        "过去窗口基准的情绪异常",
    ),
    "sentiment_trend_chart": (
        "sentiment",
        "trend",
        "line",
        "sentiment",
        "情绪时间趋势",
    ),
    "sentiment_pie_chart": (
        "sentiment",
        "distribution",
        "pie",
        "sentiment",
        "情绪分类占比",
    ),
    "sentiment_bucket_trend_chart": (
        "sentiment",
        "bucket_trend",
        "heatmap",
        "sentiment",
        "情绪类别随时间分布",
    ),
    "sentiment_attribute_trend_chart": (
        "sentiment",
        "group_trend",
        "line",
        "emotion",
        "情绪属性分组趋势",
    ),
    "sentiment_focus_window_chart": (
        "sentiment",
        "trend",
        "line",
        "sentiment",
        "所选时间段情绪趋势",
    ),
    "sentiment_focus_publisher_chart": (
        "sentiment",
        "group_trend",
        "line",
        "publisher",
        "所选发布者情绪趋势",
    ),
    "topic_frequency_stats": ("topic", "frequency", "bar", "topic", "话题频次与占比"),
    "topic_time_evolution": (
        "topic",
        "count_trend",
        "line",
        "topic",
        "话题固定窗口频次",
    ),
    "topic_cooccurrence_analysis": (
        "topic",
        "topic_edges",
        "network",
        "topic",
        "同一讨论线程的话题共现",
    ),
    "topic_ranking_chart": ("topic", "frequency", "bar", "topic", "话题频次排序"),
    "topic_evolution_chart": ("topic", "count_trend", "line", "topic", "话题演变"),
    "topic_focus_evolution_chart": (
        "topic",
        "count_trend",
        "line",
        "topic",
        "所选话题演变",
    ),
    "topic_focus_distribution_chart": (
        "topic",
        "frequency",
        "bar",
        "topic",
        "所选话题分布",
    ),
    "topic_keyword_trend_chart": (
        "topic",
        "keywords_time",
        "heatmap",
        "topic",
        "话题内关键词时间演变",
    ),
    "topic_network_chart": (
        "topic",
        "topic_edges",
        "network",
        "topic",
        "讨论线程话题网络",
    ),
    "geographic_distribution_stats": (
        "geo",
        "frequency",
        "bar",
        "region",
        "可用地区频次",
    ),
    "geographic_hotspot_detection": (
        "geo",
        "hotspot",
        "bar",
        "region",
        "地区频次热点，描述性标准分数",
    ),
    "geographic_sentiment_analysis": (
        "geo",
        "group_mean",
        "bar",
        "region",
        "地区情绪分布摘要",
    ),
    "geographic_heatmap": (
        "geo",
        "matrix",
        "heatmap",
        "region",
        "地区与话题分布热图（无地理坐标推断）",
    ),
    "geographic_bar_chart": ("geo", "frequency", "bar", "region", "地区数量排序"),
    "geographic_sentiment_bar_chart": (
        "geo",
        "group_mean",
        "bar",
        "region",
        "地区情绪均值",
    ),
    "geographic_topic_heatmap": (
        "geo",
        "matrix",
        "heatmap",
        "region",
        "地区与话题交叉表",
    ),
    "geographic_temporal_heatmap": (
        "geo",
        "count_trend",
        "heatmap",
        "region",
        "地区时间分布",
    ),
    "publisher_distribution_stats": (
        "interaction",
        "frequency",
        "bar",
        "publisher",
        "发布者类别分布",
    ),
    "cross_dimension_matrix": (
        "interaction",
        "matrix",
        "heatmap",
        "publisher",
        "所选两维的联合有效交叉表",
    ),
    "influence_analysis": (
        "interaction",
        "influence",
        "bar",
        "author_ref",
        "作者互动指标排名与缺失覆盖",
    ),
    "correlation_analysis": (
        "interaction",
        "correlation",
        "heatmap",
        "publisher",
        "数值指标逐对完整样本 Spearman 相关",
    ),
    "interaction_heatmap": (
        "interaction",
        "engagement",
        "heatmap",
        "publisher",
        "发布者与话题的互动强度",
    ),
    "publisher_bar_chart": (
        "interaction",
        "frequency",
        "bar",
        "publisher",
        "发布者类别频次",
    ),
    "publisher_sentiment_bucket_chart": (
        "interaction",
        "matrix",
        "heatmap",
        "publisher",
        "发布者与情绪类别",
    ),
    "publisher_topic_distribution_chart": (
        "interaction",
        "matrix",
        "heatmap",
        "publisher",
        "发布者与话题分布",
    ),
    "participant_trend_chart": (
        "interaction",
        "participants",
        "line",
        "author_ref",
        "每窗口独立参与者及累计参与者",
    ),
    "publisher_focus_distribution_chart": (
        "interaction",
        "frequency",
        "bar",
        "publisher",
        "所选发布者类别分布",
    ),
    "keyword_wordcloud": (
        "nlp",
        "keywords",
        "wordcloud",
        "topic",
        "文本关键词文档频次",
    ),
    "entity_cooccurrence_network": (
        "nlp",
        "entities",
        "network",
        "topic",
        "同一文本的话题标签与提及共现（规则抽取）",
    ),
    "text_cluster_analysis": (
        "nlp",
        "clusters",
        "bar",
        "topic",
        "字符 TF-IDF 与确定性 KMeans 文本聚类",
    ),
    "sentiment_lexicon_comparison": (
        "nlp",
        "lexicon",
        "bar",
        "sentiment",
        "词典与模型情绪对照",
    ),
    "temporal_keyword_heatmap": (
        "nlp",
        "keywords_time",
        "heatmap",
        "topic",
        "关键词时间分布",
    ),
}


class ToolParameters(Contract):
    top_n: int = Field(default=20, ge=1, le=100)
    start: datetime | None = None
    end: datetime | None = None
    focus: list[str] = Field(default_factory=list, max_length=30)
    group_by: (
        Literal[
            "topic",
            "publisher",
            "emotion",
            "region",
            "platform",
            "author_ref",
            "sentiment",
            "stance",
        ]
        | None
    ) = None
    second_dimension: (
        Literal[
            "topic", "publisher", "emotion", "region", "platform", "sentiment", "stance"
        ]
        | None
    ) = None
    keyword: str = Field(default="", max_length=100)
    clusters: int = Field(default=5, ge=2, le=20)
    anomaly_threshold: float = Field(default=3.0, gt=0, le=10)
    engagement_field: Literal[
        "read_count", "like_count", "comment_count", "repost_count"
    ] = "like_count"


def catalog():
    schema = ToolParameters.model_json_schema()
    return [
        {
            "name": name,
            "category": v[0],
            "description": v[4],
            "parameters": schema,
            "version": "canonical-tools-v1",
            "output": "table + chart + coverage + provenance",
        }
        for name, v in TOOLS.items()
    ]


def scalar_stats(values):
    a = np.asarray(values, dtype=float)
    return {
        "n": len(a),
        "mean": float(a.mean()) if len(a) else None,
        "variance": float(a.var()) if len(a) else None,
        "quantiles": np.quantile(a, [0.1, 0.25, 0.5, 0.75, 0.9]).tolist()
        if len(a)
        else None,
    }


class AnalysisToolbox:
    def __init__(
        self, posts, annotations, schema, spec, max_calls=24, check_cancel=lambda: None
    ):
        self.spec = ObservationSpec.model_validate(spec)
        self.schema = schema
        self.max_calls, self.check_cancel = max_calls, check_cancel
        self.results = {}
        parsed = [AnnotationRecord.model_validate(a) for a in annotations]
        ann = {a.post_id: a for a in parsed}
        if len(ann) != len(parsed) or any(
            a.schema_version != schema["schema_version"] for a in parsed
        ):
            raise ValueError(
                "analysis requires unique annotations from the frozen schema"
            )
        self.rows = []
        self.input_n = len(posts)
        for raw in posts:
            p = PostRecord.model_validate(raw)
            if (
                p.kind not in self.spec.kinds
                or self.spec.platforms
                and p.platform not in self.spec.platforms
                or p.published_at is None
                or not self.spec.start <= p.published_at < self.spec.end
            ):
                continue
            a = ann.get(p.post_id)
            row = p.model_dump(mode="json")
            row["time"] = p.published_at
            row["window"] = int(
                (p.published_at - self.spec.start).total_seconds()
                // self.spec.window_seconds
            )
            for field in ("topic", "publisher", "emotion", "stance", "sentiment"):
                f = getattr(a, field) if a else None
                row[field] = f.value if f and f.status == "accepted" else None
            if self.spec.topic_ids and row["topic"] not in self.spec.topic_ids:
                continue
            self.rows.append(row)
        self.fingerprint = hashlib.sha256(
            json.dumps(
                [posts, annotations, schema, self.spec.model_dump(mode="json")],
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            ).encode()
        ).hexdigest()

    def execute(self, name, parameters=None):
        if name not in TOOLS:
            raise ValueError("unknown analytical tool")
        params = ToolParameters.model_validate(parameters or {})
        for timestamp in (params.start, params.end):
            if timestamp is not None and timestamp.tzinfo is None:
                raise ValueError("tool time filters require timezone offsets")
        if params.start and params.end and params.end <= params.start:
            raise ValueError("invalid tool time range")
        payload = params.model_dump(mode="json")
        key = (
            "t-"
            + hashlib.sha256(
                json.dumps(
                    [name, payload, self.fingerprint, "canonical-tools-v1"],
                    sort_keys=True,
                ).encode()
            ).hexdigest()
        )
        if key in self.results:
            return self.results[key]
        if len(self.results) >= self.max_calls:
            raise ValueError("analysis tool budget exhausted")
        self.check_cancel()
        family, op, view, group, description = TOOLS[name]
        group = params.group_by or group
        rows = [
            r
            for r in self.rows
            if (not params.start or r["time"] >= params.start)
            and (not params.end or r["time"] < params.end)
            and (not params.focus or str(r.get(group)) in params.focus)
            and (
                not params.keyword
                or params.keyword.casefold() in r["content"].casefold()
            )
        ]
        table, metrics, notes = [], {}, []
        required = []
        if op in {"frequency", "hotspot", "distribution"}:
            required = [group]
            counts = Counter(str(r[group]) for r in rows if r.get(group) is not None)
            total = sum(counts.values())
            mu = np.mean(list(counts.values())) if counts else 0
            sd = np.std(list(counts.values())) if counts else 0
            table = [
                {
                    "label": k,
                    "value": v,
                    "share": v / total,
                    "z_score": float((v - mu) / sd) if sd else None,
                }
                for k, v in counts.most_common(params.top_n)
            ]
            metrics = {"valid_n": total, "displayed_n": sum(t["value"] for t in table)}
            if group == "sentiment":
                metrics.update(
                    scalar_stats([r[group] for r in rows if r.get(group) is not None])
                )
            if op == "hotspot":
                notes.append(
                    "Z scores compare observed regions, not population-adjusted geographic risks."
                )
        elif op in {
            "trend",
            "anomaly",
            "bucket_trend",
            "group_trend",
            "count_trend",
            "participants",
        }:
            required = (
                ["sentiment"] if op in {"trend", "anomaly", "bucket_trend"} else [group]
            )
            if op == "group_trend":
                required.append("sentiment")
            n_windows = math.ceil(
                (self.spec.end - self.spec.start).total_seconds()
                / self.spec.window_seconds
            )
            history, cumulative = [], set()
            groups = defaultdict(list)
            for r in rows:
                groups[r["window"]].append(r)
            dim = "sentiment" if op == "bucket_trend" else group
            displayed_groups = [
                label
                for label, _ in Counter(
                    str(r[dim]) for r in rows if r.get(dim) is not None
                ).most_common(params.top_n)
            ]
            for w in range(n_windows):
                self.check_cancel()
                batch = groups[w]
                if op == "participants":
                    authors = {r["author_ref"] for r in batch if r["author_ref"]}
                    cumulative.update(authors)
                    table.extend(
                        [
                            {
                                "label": str(w),
                                "series": "per_window",
                                "value": len(authors),
                            },
                            {
                                "label": str(w),
                                "series": "cumulative",
                                "value": len(cumulative),
                            },
                        ]
                    )
                elif op in {"trend", "anomaly"}:
                    values = [
                        r["sentiment"] for r in batch if r["sentiment"] is not None
                    ]
                    detail = scalar_stats(values)
                    past = history[-7:]
                    sd = float(np.std(past)) if len(past) >= 3 else 0
                    z = (
                        (detail["mean"] - float(np.mean(past))) / sd
                        if values and sd > 1e-12
                        else None
                    )
                    table.append(
                        {
                            "label": str(w),
                            "value": detail["mean"],
                            **detail,
                            "z_score": z,
                            "anomaly": abs(z) >= params.anomaly_threshold
                            if z is not None
                            else None,
                        }
                    )
                    if values:
                        history.append(detail["mean"])
                else:
                    grouped = defaultdict(list)
                    dim = "sentiment" if op == "bucket_trend" else group
                    for r in batch:
                        if r.get(dim) is not None:
                            grouped[str(r[dim])].append(r)
                    for label in displayed_groups:
                        members = grouped[label]
                        values = [
                            r["sentiment"]
                            for r in members
                            if r["sentiment"] is not None
                        ]
                        table.append(
                            {
                                "label": str(w),
                                "series": label,
                                "n": len(members),
                                "value": scalar_stats(values)["mean"]
                                if op == "group_trend"
                                else len(members),
                            }
                        )
            notes.append(
                "Time labels are zero-based fixed windows from observation start; empty means are null."
            )
        elif op == "group_mean":
            required = [group, "sentiment"]
            grouped = defaultdict(list)
            for r in rows:
                if r.get(group) is not None and r["sentiment"] is not None:
                    grouped[str(r[group])].append(r["sentiment"])
            table = [
                {"label": k, "value": scalar_stats(v)["mean"], **scalar_stats(v)}
                for k, v in sorted(grouped.items(), key=lambda x: -len(x[1]))[
                    : params.top_n
                ]
            ]
        elif op in {"matrix", "engagement"}:
            second = params.second_dimension or (
                "sentiment" if name == "publisher_sentiment_bucket_chart" else "topic"
            )
            required = [group, second] + (
                [params.engagement_field] if op == "engagement" else []
            )
            cells = defaultdict(list)
            for r in rows:
                if all(r.get(k) is not None for k in required):
                    cells[(str(r[group]), str(r[second]))].append(
                        r.get(params.engagement_field, 0)
                    )
            table = [
                {
                    "label": a,
                    "series": b,
                    "n": len(v),
                    "value": float(np.mean(v)) if op == "engagement" else len(v),
                }
                for (a, b), v in sorted(cells.items())
            ]
        elif op == "influence":
            required = ["author_ref", params.engagement_field]
            grouped = defaultdict(list)
            for r in rows:
                if all(r.get(k) is not None for k in required):
                    grouped[r["author_ref"]].append(r[params.engagement_field])
            table = [
                {"label": k, "value": sum(v), "n": len(v), "mean": float(np.mean(v))}
                for k, v in sorted(grouped.items(), key=lambda x: -sum(x[1]))[
                    : params.top_n
                ]
            ]
            notes.append(
                "Engagement ranking is not a causal or network influence estimate."
            )
        elif op == "correlation":
            from scipy.stats import spearmanr

            columns = [
                "sentiment",
                "read_count",
                "like_count",
                "comment_count",
                "repost_count",
            ]
            for a, b in combinations(columns, 2):
                pairs = [
                    (r[a], r[b])
                    for r in rows
                    if r.get(a) is not None and r.get(b) is not None
                ]
                value = None
                if (
                    len(pairs) >= 3
                    and len({v[0] for v in pairs}) > 1
                    and len({v[1] for v in pairs}) > 1
                ):
                    value = float(
                        spearmanr(
                            np.asarray(pairs)[:, 0], np.asarray(pairs)[:, 1]
                        ).statistic
                    )
                table.append({"label": a, "series": b, "value": value, "n": len(pairs)})
            notes.append(
                "Pairwise complete descriptive correlations; no independence or significance claim."
            )
        elif op in {"topic_edges", "entities"}:
            groups = defaultdict(set)
            if op == "topic_edges":
                required = ["topic"]
                parents = {
                    (r["platform"], r["raw_id"]): r["parent_ref"] for r in self.rows
                }
                for r in rows:
                    if r["topic"] is not None:
                        root = r["thread_ref"] or r["raw_id"]
                        seen = set()
                        while (
                            not r["thread_ref"]
                            and parents.get((r["platform"], root))
                            and root not in seen
                        ):
                            seen.add(root)
                            root = parents[(r["platform"], root)]
                        if root in seen:
                            root = min(seen)
                        groups[(r["platform"], root)].add(r["topic"])
                notes.append(
                    "Edges count discussion threads containing both labels; a single-label post has no topic co-labels."
                )
            else:
                for r in rows:
                    self.check_cancel()
                    groups[r["post_id"]].update(extract_entities(r["content"])[:30])
                notes.append(
                    "The retained extractor recognizes hashtags and @mentions only; this is not general named-entity recognition."
                )
            edges = Counter(
                pair
                for labels in groups.values()
                for pair in combinations(sorted(labels), 2)
            )
            table = [
                {"label": a, "series": b, "value": v}
                for (a, b), v in edges.most_common(params.top_n)
            ]
        elif op in {"keywords", "keywords_time"}:
            counts, by_window = Counter(), Counter()
            for r in rows:
                self.check_cancel()
                words = set(extract_keywords(r["content"], top_n=10))
                counts.update(words)
                by_window.update((r["window"], word) for word in words)
            chosen = {k for k, _ in counts.most_common(params.top_n)}
            table = (
                [{"label": k, "value": v} for k, v in counts.most_common(params.top_n)]
                if op == "keywords"
                else [
                    {"label": str(w), "series": k, "value": v}
                    for (w, k), v in sorted(by_window.items())
                    if k in chosen
                ]
            )
            notes.append(
                "Document frequency of extracted keywords; each keyword counts at most once per post."
            )
        elif op == "clusters":
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.cluster import KMeans

            usable = [r for r in rows if r["content"].strip()]
            if len(usable) >= 2:
                try:
                    vectorizer = TfidfVectorizer(
                        analyzer="char", ngram_range=(1, 3), max_features=8000
                    )
                    x = vectorizer.fit_transform([r["content"] for r in usable])
                    count = min(params.clusters, len({r["content"] for r in usable}))
                    model = KMeans(n_clusters=count, random_state=42, n_init=10).fit(x)
                    terms = vectorizer.get_feature_names_out()
                    table = [
                        {
                            "label": str(i),
                            "value": int(sum(model.labels_ == i)),
                            "keywords": terms[
                                np.argsort(model.cluster_centers_[i])[-8:][::-1]
                            ].tolist(),
                            "post_ids": [
                                r["post_id"]
                                for r, c in zip(usable, model.labels_)
                                if c == i
                            ],
                        }
                        for i in range(count)
                    ]
                except ValueError:
                    notes.append("Text vocabulary is empty; clustering is unavailable.")
        elif op == "lexicon":
            required = ["sentiment"]
            for r in rows:
                if r["sentiment"] is not None:
                    score = lexicon_sentiment(r["content"])
                    table.append(
                        {
                            "label": r["post_id"],
                            "value": r["sentiment"],
                            "lexicon": score,
                        }
                    )
            notes.append("Lexicon is a diagnostic comparator, not a human gold label.")
        valid_n = sum(all(r.get(k) is not None for k in required) for r in rows)
        result = {
            "tool_id": key,
            "name": name,
            "category": family,
            "description": description,
            "parameters": payload,
            "status": "completed" if table else "unavailable",
            "table": table,
            "metrics": metrics,
            "chart": {"kind": view, "x": "label", "y": "value", "series": "series"},
            "notes": notes,
            "coverage": {
                "input_n": self.input_n,
                "selected_n": len(rows),
                "valid_n": valid_n,
                "required_fields": required,
                "field_available": {
                    k: sum(r.get(k) is not None for r in rows) for k in required
                },
            },
            "provenance": {
                "dataset_fingerprint": self.fingerprint,
                "schema_version": self.schema["schema_version"],
                "observation_spec": self.spec.model_dump(mode="json"),
                "implementation": "canonical-tools-v1",
            },
        }
        self.results[key] = result
        return result


def chart_svg(result):
    """Escaped, deterministic chart projection; complete tables remain in artifacts."""
    rows = [r for r in result["table"] if isinstance(r.get("value"), (int, float))][:60]
    maximum = max((abs(r["value"]) for r in rows), default=1) or 1
    parts = ['<rect width="100%" height="100%" fill="white"/>']
    for i, row in enumerate(rows):
        label = html.escape(
            str(row["label"]) + (" / " + str(row["series"]) if "series" in row else "")
        )
        y = 48 + i * 24
        width = abs(row["value"]) / maximum * 300
        x = 500 if row["value"] >= 0 else 500 - width
        parts += [
            f'<text x="8" y="{y}" font-size="12">{label[:100]}</text>',
            f'<rect x="{x}" y="{y - 12}" width="{width}" height="16" fill="#197c84"/>',
            f'<text x="810" y="{y}" font-size="11">{row["value"]:.4g}</text>',
        ]
    if not rows:
        parts.append(
            '<text x="8" y="48">No available measurements; see coverage and source table.</text>'
        )
    parts.append(
        '<text x="8" y="20" font-size="14">'
        + html.escape(result["description"])
        + "</text>"
    )
    height = max(100, 70 + len(rows) * 24)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 {height}" role="img">'
        + "".join(parts)
        + "</svg>"
    )
