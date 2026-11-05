"""Print-sized vector charts from complete frozen tables, including missing values."""

from io import StringIO
import math
import os
from pathlib import Path
import threading

import matplotlib
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
import numpy as np

_LOCK = threading.Lock()
_COLORS = ["#2563eb", "#0d9488", "#9333ea", "#d97706", "#e11d48", "#64748b"]


def _number(value):
    return (
        float(value)
        if isinstance(value, (int, float)) and math.isfinite(value)
        else np.nan
    )


def _label(value):
    text = str(value)
    return text[:10] if "T" in text and len(text) >= 20 else text


def static_chart(chart):
    rows = chart.get("data", chart.get("table", []))
    kind = (chart.get("chart") or {}).get("kind", "bar")
    distribution = any("mass" in row for row in rows)
    if not rows or kind not in {"line", "bar", "pie", "heatmap"}:
        return chart
    with (
        _LOCK,
        matplotlib.rc_context(
            {"svg.fonttype": "none", "font.size": 9, "axes.unicode_minus": False}
        ),
    ):
        height = min(7.0, max(3.1, len(rows) * 0.22 + 1)) if kind == "bar" else 3.8
        if distribution:
            height = 3.8
        fig = Figure(figsize=(6.5, height), layout="constrained")
        ax = fig.subplots()
        for spine in ax.spines.values():
            spine.set_color("#dbe3ee")
        ax.tick_params(colors="#475569", labelsize=8, length=0)
        if distribution or kind == "heatmap":
            if distribution:
                bins = chart.get("bins", [])
                n = max(
                    (len(r.get("mass") or []) for r in rows),
                    default=max(1, len(bins) - 1),
                )
                labels = [_label(r.get("start", i)) for i, r in enumerate(rows)]
                groups = [
                    f"{bins[i]:.1f} … {bins[i + 1]:.1f}"
                    if len(bins) > i + 1
                    else str(i)
                    for i in range(n)
                ]
                matrix = np.array(
                    [
                        [_number(v) for v in r["mass"]]
                        if r.get("mass")
                        else [np.nan] * n
                        for r in rows
                    ]
                ).T
            else:
                labels = list(dict.fromkeys(str(r.get("label", "")) for r in rows))
                groups = list(
                    dict.fromkeys(str(r.get("series", "value")) for r in rows)
                )
                matrix = np.full((len(groups), len(labels)), np.nan)
                for row in rows:
                    matrix[
                        groups.index(str(row.get("series", "value"))),
                        labels.index(str(row.get("label", ""))),
                    ] = _number(row.get("value"))
            cmap = matplotlib.colormaps[
                "RdBu_r" if np.any(matrix < 0) else "Blues"
            ].copy()
            cmap.set_bad("#e2e8f0")
            limit = (
                float(np.nanmax(np.abs(matrix))) if np.any(np.isfinite(matrix)) else 1
            )
            image = ax.imshow(
                np.ma.masked_invalid(matrix),
                aspect="auto",
                interpolation="nearest",
                cmap=cmap,
                vmin=-limit if np.any(matrix < 0) else 0,
                vmax=1 if distribution else max(limit, 0.01),
            )
            ticks = np.unique(
                np.linspace(0, len(labels) - 1, min(6, len(labels))).astype(int)
            )
            ax.set_xticks(ticks, [labels[i] for i in ticks], rotation=25, ha="right")
            ax.set_yticks(range(len(groups)), groups)
            ax.set_xlabel(
                "窗口起点（UTC）；灰色表示缺失" if distribution else "灰色表示缺失"
            )
            fig.colorbar(image, ax=ax, shrink=0.8, pad=0.025)
        elif kind == "line":
            labels = list(
                dict.fromkeys(str(r.get("label", r.get("start", ""))) for r in rows)
            )
            groups = list(dict.fromkeys(str(r.get("series", "数值")) for r in rows))
            lookup = {label: i for i, label in enumerate(labels)}
            for j, group in enumerate(groups):
                values = np.full(len(labels), np.nan)
                lower, upper = values.copy(), values.copy()
                for row in rows:
                    if str(row.get("series", "数值")) == group:
                        i = lookup[str(row.get("label", row.get("start", "")))]
                        values[i] = _number(row.get("value"))
                        lower[i] = _number(row.get("lower"))
                        upper[i] = _number(row.get("upper"))
                color = _COLORS[j % len(_COLORS)]
                ax.plot(
                    values,
                    color=color,
                    linewidth=1.5,
                    marker=".",
                    markersize=2,
                    label=group,
                )
                if np.any(np.isfinite(lower) & np.isfinite(upper)):
                    ax.fill_between(
                        range(len(labels)), lower, upper, color=color, alpha=0.12
                    )
            ticks = np.unique(
                np.linspace(0, len(labels) - 1, min(7, len(labels))).astype(int)
            )
            ax.set_xticks(
                ticks, [_label(labels[i]) for i in ticks], rotation=20, ha="right"
            )
            ax.set_xlabel("观测窗口")
            ax.grid(axis="y", color="#e2e8f0", linewidth=0.6)
            if len(groups) > 1:
                ax.legend(
                    loc="upper center",
                    bbox_to_anchor=(0.5, 1.18),
                    ncol=min(3, len(groups)),
                    frameon=False,
                    fontsize=8,
                )
        else:
            labels = [
                str(r.get("label", ""))
                + (" / " + str(r["series"]) if "series" in r else "")
                for r in rows
            ]
            values = [_number(r.get("value")) for r in rows]
            ax.barh(range(len(rows)), values, color=_COLORS[0], height=0.65)
            ax.set_yticks(range(len(rows)), labels)
            ax.invert_yaxis()
            ax.axvline(0, color="#94a3b8", linewidth=0.6)
            ax.grid(axis="x", color="#e2e8f0", linewidth=0.6)
            ax.set_axisbelow(True)
        # SVG retains text; PDF applies the same registered CJK font to every label.
        candidates = [
            os.environ.get("T2I_REPORT_FONT", ""),
            "C:/Windows/Fonts/simsun.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/System/Library/Fonts/Supplemental/Songti.ttc",
        ]
        path = next((p for p in candidates if p and Path(p).is_file()), None)
        if path:
            from matplotlib.text import Text

            for text in fig.findobj(Text):
                text.set_fontproperties(
                    FontProperties(fname=path, size=text.get_fontsize())
                )
        stream = StringIO()
        fig.savefig(stream, format="svg")
        fig.clear()
        return {**chart, "svg": stream.getvalue()}
