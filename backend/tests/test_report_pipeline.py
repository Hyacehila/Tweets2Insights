"""Report composition, immutable publication, and shared web/PDF content."""

import base64
import copy
from io import BytesIO
from pathlib import Path

import pytest
from test_workspace_views import workspace


@pytest.fixture
def source():
    return {
        "event_id": "demo",
        "run_id": "report-test",
        "blocks": [
            {
                "block_id": "inventory",
                "kind": "observed",
                "title": "数据范围",
                "text": "共 {{count}} 条记录",
                "numeric_refs": ["count"],
                "evidence_refs": ["e1"],
            }
        ],
        "metrics": {"count": 300},
        "source_versions": {"observations": "a-source"},
        "evidence": [
            {
                "evidence_id": "e1",
                "kind": "calculation",
                "title": "真实样本统计",
                "excerpt": "共三百条",
                "source_ref": "a-source",
                "retrieved_at": "2026-11-05T00:00:00Z",
                "content_sha256": "abc",
            }
        ],
    }


class ReportModel:
    def __init__(self):
        self.seen = []

    def request(self, prompt, payload):
        self.seen.append((prompt, payload))
        if "ReportUIAgent" in prompt:
            return payload["layout_template"], {}
        if "chapter_plan" in payload:
            return {
                "chapters": [
                    {
                        "chapter_id": c["chapter_id"],
                        "focus": c["title"],
                        "chart_ids": list(payload["chart_catalog"]),
                        "evidence_refs": ["e1"],
                    }
                    for c in payload["chapter_plan"]
                ]
            }, {}
        return {
            "title": "事件复盘报告",
            "paragraphs": [
                {
                    "title": payload["chapter"]["title"],
                    "text": "本次分析覆盖 {{count}} 条帖子，事件讨论体现出不同主体的信息关注差异。",
                    "kind": "observed",
                    "evidence_refs": ["e1"],
                    "numeric_refs": ["count"],
                    "chart_ids": [],
                }
            ],
        }, {}


def test_template_guides_complete_agent_authored_chapters(source):
    from opinion_core.reporting.composition import compose_report, load_template

    model = ReportModel()
    original = copy.deepcopy(source)
    result, audit = compose_report(source, model, {}, "分析舆情", {})
    assert (
        load_template().strip()
        == (Path(__file__).parents[2] / "data/report_template.md")
        .read_text(encoding="utf-8")
        .strip()
    )
    assert len(result["chapters"]) == 11
    assert len(model.seen) == 12
    assert "信念系统分析" in model.seen[7][1]["template"]
    assert all(ch["block_ids"] for ch in result["chapters"])
    assert len(result["blocks"]) == 11 and all(
        "关注差异" in b["text"] for b in result["blocks"]
    )
    assert result["report_title"] == "事件复盘报告"
    assert audit["status"] == "completed" and source == original


def test_invalid_agent_chapter_is_repaired_or_fails_visibly(source):
    from opinion_core.reporting.composition import compose_report

    model = ReportModel()
    valid_request = model.request
    model.request = lambda *args: (
        valid_request(*args)
        if "chapter_plan" in args[1]
        else (
            {
                "paragraphs": [
                    {
                        "title": "伪造",
                        "text": "{{unknown}}",
                        "kind": "observed",
                        "numeric_refs": ["unknown"],
                        "evidence_refs": ["fake"],
                    }
                ]
            },
            {},
        )
    )
    with pytest.raises(ValueError, match="报告摘要"):
        compose_report(source, model, {}, "", {})


def test_chapter_checkpoint_resume_skips_finished_model_calls(source):
    from opinion_core.reporting.composition import compose_report

    cache = {}
    model = ReportModel()
    result, _ = compose_report(
        source,
        model,
        {},
        "",
        {},
        load_chapter=cache.get,
        save_chapter=cache.__setitem__,
    )
    assert len(model.seen) == 12
    model.seen.clear()
    again, _ = compose_report(
        source,
        model,
        {},
        "",
        {},
        load_chapter=cache.get,
        save_chapter=cache.__setitem__,
    )
    assert result == again and model.seen == []


def test_large_chart_context_is_bounded_and_preserves_extremes():
    from opinion_core.reporting.composition import chart_context

    metrics = {}
    rows = [
        {"label": str(i), "value": 9999 if i == 733 else i % 20} for i in range(5000)
    ]
    result = chart_context({"daily": {"data": rows}}, metrics)["daily"]
    assert len(result["rows"]) <= 60
    assert result["row_count"] == 5000 and result["preview_truncated"]
    assert any(r["label"] == "733" for r in result["rows"])
    assert any(r["label"] == "0" for r in result["rows"])
    assert any(r["label"] == "4999" for r in result["rows"])


def test_report_model_defaults_respect_explicit_provider_preferences():
    from opinion_core.reporting.composition import report_model_config
    from opinion_core.schemas.agent_model import AgentModelConfig

    config = AgentModelConfig(
        provider="openai_compatible",
        model="deepseek-flash",
        base_url="https://api.deepseek.com/v1",
        max_tokens=8192,
    )
    assert report_model_config(config).extra_body == {"reasoning_effort": "low"}
    explicit = config.model_copy(
        update={
            "extra_body": {"thinking": {"type": "enabled"}, "reasoning_effort": "high"}
        }
    )
    assert report_model_config(explicit).extra_body == explicit.extra_body
    other = config.model_copy(update={"base_url": "https://example.com/v1"})
    assert report_model_config(other).extra_body == {}
    assert config.extra_body == {}


def test_report_layout_cannot_drop_chapters_or_invent_charts(source):
    from opinion_core.reporting.composition import compose_report
    from opinion_core.reporting.structure import build_structure, validate_structure

    bundle, _ = compose_report(source, ReportModel(), {}, "", {})
    layout = build_structure(bundle)
    assert len(layout["sections"]) == 11
    layout["sections"][0]["chart_ids"] = ["unknown"]
    with pytest.raises(ValueError, match="chart"):
        validate_structure(bundle, layout, {})


def test_pdf_and_web_use_same_chapters_charts_and_metrics(source):
    from pypdf import PdfReader
    from opinion_core.reporting.composition import compose_report
    from opinion_core.reporting.structure import build_structure
    from opinion_core.reporting.render import render_report

    bundle, _ = compose_report(source, ReportModel(), {}, "", {})
    charts = {
        "sentiment": {
            "title": "情绪分布",
            "svg": '<svg xmlns="http://www.w3.org/2000/svg" width="500" height="200"><rect x="40" y="40" width="300" height="100" fill="#2563eb"/></svg>',
            "data": [{"label": "neutral", "count": 300}],
        }
    }
    layout = build_structure(bundle, charts)
    report = render_report(bundle, layout, charts)
    pdf = base64.b64decode(report["pdf_base64"])
    assert pdf.startswith(b"%PDF-")
    reader = PdfReader(BytesIO(pdf))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "300" in text and "事件复盘报告" in text and "信念系统分析" in text
    assert "300" in report["markdown"] and "300" in report["html"]
    assert "ReportSection" in report["openui"] and "ReportChart" in report["openui"]
    assert report["pdf_pages"] == len(reader.pages) and len(reader.pages) >= 3
    assert "{{count}}" not in text


def test_static_charts_keep_full_series_and_readable_cjk(source):
    from opinion_core.reporting.charts import static_chart
    from opinion_core.reporting.pdf import chart_drawing, report_font
    from reportlab.graphics.shapes import String

    chart = {
        "chart": {"kind": "line"},
        "title": "每日情绪趋势",
        "data": [{"label": str(i), "value": i} for i in range(182)],
        "svg": "<svg/>",
    }
    result = static_chart(chart)
    assert result["data"] == chart["data"] and result["svg"] != chart["svg"]
    # Last observations must survive conversion; the legacy SVG cut at 60 rows.
    assert "181" in result["svg"]
    drawing = chart_drawing(
        {
            "svg": '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="100"><text x="20" y="30">中文标签</text></svg>'
        }
    )

    def strings(node):
        return ([node] if isinstance(node, String) else []) + [
            s for c in getattr(node, "contents", []) for s in strings(c)
        ]

    assert all(s.fontName == report_font() for s in strings(drawing))


def test_pdf_download_and_report_only_job_are_scoped(workspace, source):
    from opinion_core.reporting.composition import compose_report
    from opinion_core.reporting.structure import build_structure
    from opinion_core.reporting.render import render_report
    from opinion_core.schemas.workflow import RunRequest

    r = workspace
    from types import SimpleNamespace

    async def call(name, arguments):
        return getattr(r.service, name)(**arguments)

    r.client.app.state.runtime = SimpleNamespace(mcp=SimpleNamespace(call=call))
    request = {
        "event": {
            "event_id": "demo",
            "input_mode": "existing",
            "dataset_ref": r.dataset["dataset_id"],
            "as_of": "2024-11-04T00:00:00Z",
            "objectives": ["retrospective"],
        },
        "run_id": "report-test",
        "observations": {
            "start": "2024-11-01T00:00:00Z",
            "end": "2024-11-04T00:00:00Z",
            "window_seconds": 86400,
        },
    }
    request = RunRequest.model_validate(request).model_dump(mode="json")
    request_ref = r.service.assets.put("demo", "report-test", "request", request)
    bundle, _ = compose_report(source, ReportModel(), {}, "", {})
    report = render_report(bundle, build_structure(bundle), {})
    ref = r.service.assets.put("demo", "report-test", "report", report)
    refs = {
        key: r.service.assets.put("demo", "report-test", key, {})
        for key in ["input", "schema", "labels", "observations", "evidence", "charts"]
    }
    refs["report"] = ref
    job = r.service.jobs.submit(
        "demo",
        "report-test",
        "analysis_run",
        {"request_ref": request_ref["artifact_id"]},
    )
    claimed = r.service.jobs.claim("test", kinds=["analysis_run"])
    r.service.jobs.finish(claimed, {"artifacts": refs})
    url = f"/api/threads/{r.thread['thread_id']}"
    download = r.client.get(
        url + f"/exports/report-test/{ref['artifact_id']}?format=pdf"
    )
    assert download.status_code == 200 and download.content.startswith(b"%PDF-")
    assert "application/pdf" in download.headers["content-type"]
    assert (
        r.client.get(
            url.replace(r.thread["thread_id"], r.other["thread_id"])
            + f"/exports/report-test/{ref['artifact_id']}?format=pdf"
        ).status_code
        == 404
    )
    response = r.client.post(url + f"/jobs/{job.job_id}/report")
    assert response.status_code == 200, response.text
    new = response.json()
    assert new["kind"] == "report_run" and new["run_id"] != "report-test"
    params = r.service.jobs.parameters(new["job_id"])
    assert [t["task_id"] for t in params["plan"]["tasks"]] == [
        "content",
        "theory",
        "structure",
        "report",
    ]
    assert params["source_artifacts"]["labels"] == refs["labels"]
