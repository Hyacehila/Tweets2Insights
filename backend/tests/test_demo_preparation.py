import json
import zipfile

import pytest
from opinion_core.ingestion.demo import normalize_rows, select_daily


def row(number, day, heat, images=None):
    return {
        "user_id": str(number),
        "content": f"帖子 {number}",
        "publish_time": f"2024-11-{day:02d} 12:00:00",
        "like_count": heat,
        "comment_count": 0,
        "repost_count": 0,
        "image_urls": images or [],
    }


def test_normalize_retains_rows_and_strips_images_for_text():
    source = [row(1, 3, 4, ["media/one.jpg"]), row(2, 4, 2)]
    records, rejected = normalize_rows(source, "henan", "text_only")
    assert not rejected
    assert len(records) == 2
    assert all(not p["media_refs"] for p in records)
    assert records[0]["published_at"] == "2024-11-03T04:00:00Z"
    assert records[0]["read_count"] is None
    assert records == normalize_rows(source, "henan", "text_only")[0]


def test_beijing_mapping_heat_and_invalid_time_are_explicit():
    records, rejected = normalize_rows(
        [
            {
                "content": "暴雨",
                "pubtime": "2023年07月29日23:59",
                "url": "https://weibo.com/123/AbC",
                "like": "1.2万",
                "transfer": "3",
                "comment": "4",
                "place": "北京",
            },
            {"content": "未知时间", "pubtime": "-"},
        ],
        "beijingstorm",
        "text_image",
    )
    assert len(records) == 1
    assert records[0]["like_count"] == 12000
    assert records[0]["raw_id"] == "AbC"
    assert records[0]["media_refs"] == []
    assert rejected == [{"source_row": 2, "reason": "invalid_time"}]


def test_daily_selection_covers_days_and_uses_top_heat_within_every_day():
    rows = [row(i, 3, i) for i in range(10)] + [row(20, 4, 2), row(21, 4, 80)]
    records, _ = normalize_rows(rows, "henan", "text_only")
    chosen, daily = select_daily(records, 5)
    assert len(chosen) == 5
    assert len(daily) == 2
    assert sum(d["selected"] for d in daily) == 5
    for day in daily:
        selected = [
            p["like_count"] for p in chosen if p["original_time"][:10] == day["day"]
        ]
        available = [
            p["like_count"] for p in records if p["original_time"][:10] == day["day"]
        ]
        assert (
            sorted(selected, reverse=True)
            == sorted(available, reverse=True)[: len(selected)]
        )
    assert chosen == select_daily(list(reversed(records)), 5)[0]


def test_under_limit_uses_all_and_multimodal_trial_requires_images():
    records, _ = normalize_rows(
        [row(1, 3, 100), row(2, 3, 2, ["media/a.jpg"])], "henan", "text_image"
    )
    assert len(select_daily(records, 10000)[0]) == 2
    chosen, _ = select_daily(records, 300, images_only=True)
    assert len(chosen) == 1 and chosen[0]["media_refs"] == ["media/a.jpg"]
    with pytest.raises(ValueError, match="images"):
        select_daily(records[:1], 300, images_only=True)


def test_daily_windows_use_shanghai_midnight_and_limit_is_hard():
    records, _ = normalize_rows(
        [row(1, 3, 1), row(2, 4, 2), row(3, 5, 3)], "henan", "text_only"
    )
    records[0]["published_at"] = "2024-11-02T16:01:00Z"
    chosen, daily = select_daily(records, 2)
    assert len(chosen) == 2
    assert daily[0]["day"] == "2024-11-03"
    assert sum(d["selected"] for d in daily) == 2


def test_identical_duplicate_rows_have_unique_traceable_ids():
    original = row(1, 3, 10)
    records, _ = normalize_rows([original, original], "henan", "text_only")
    assert len({p["post_id"] for p in records}) == 2
    assert [p["raw_id"] for p in records] == ["row-1", "row-2"]


def test_read_excel_inline_and_shared_strings(tmp_path):
    from opinion_core.ingestion.demo import read_rows

    path = tmp_path / "input.xlsx"
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "xl/sharedStrings.xml", f'<sst xmlns="{ns}"><si><t>暴雨</t></si></sst>'
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f'''<worksheet xmlns="{ns}"><sheetData>
        <row r="1"><c r="A1" t="inlineStr"><is><t>content</t></is></c></row>
        <row r="2"><c r="A2" t="s"><v>0</v></c></row></sheetData></worksheet>''',
        )
    assert read_rows(path) == [{"content": "暴雨"}]


def test_prepare_registers_images_and_plan_without_creating_paid_job(tmp_path):
    from opinion_gateway.application import ApplicationService
    from opinion_gateway.demo_preparation import prepare_demo
    from opinion_gateway.media_assets import MediaAssets
    from PIL import Image

    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (40, 50), "blue").save(source / "photo.png")
    path = source / "posts.json"
    path.write_text(json.dumps([row(1, 3, 10, ["photo.png"])]), encoding="utf-8")
    original = path.read_bytes()
    root, output = tmp_path / "assets", tmp_path / "demo"
    result = prepare_demo(
        path, "henan", output, "demo", 300, "text_image", root, images_only=True
    )
    assert result["selected_posts"] == 1
    assert result["selected_images_for_model"] == 1
    records = json.loads((output / "posts.json").read_text(encoding="utf-8"))
    assert records[0]["media_refs"][0].startswith("dataset-image:")
    assert MediaAssets(root, "demo").load(records[0]["media_refs"][0])
    app = ApplicationService(root)
    request = json.loads((output / "run.json").read_text(encoding="utf-8"))
    assert request["labels"]["max_calls"] == 1
    assert request["media_mode"] == "text_image"
    assert app.preview_plan(request)["tasks"][-1]["task_id"] == "report"
    assert not app.list_jobs("demo")
    assert path.read_bytes() == original


def test_prepare_rejects_false_multimodal_and_outside_source_paths(tmp_path):
    from opinion_gateway.demo_preparation import prepare_demo

    source = tmp_path / "source"
    source.mkdir()
    path = source / "posts.json"
    path.write_text(json.dumps([row(1, 3, 10)]), encoding="utf-8")
    with pytest.raises(ValueError, match="images"):
        prepare_demo(
            path,
            "henan",
            tmp_path / "out",
            "demo",
            300,
            "text_image",
            tmp_path / "assets",
        )
    path.write_text(json.dumps([row(1, 3, 10, ["../secret.png"])]), encoding="utf-8")
    with pytest.raises(ValueError, match="source directory"):
        prepare_demo(
            path,
            "henan",
            tmp_path / "out",
            "demo",
            300,
            "text_image",
            tmp_path / "assets",
        )


def test_ten_thousand_post_demo_has_budget_for_report_stages():
    from opinion_gateway.demo_preparation import make_request

    records, _ = normalize_rows([row(1, 3, 1)], "henan", "text_only")
    request = make_request(
        "henan", "demo", "ds-example", records * 10000, "text_only", 3
    )
    assert request["max_total_calls"] > request["labels"]["max_calls"] == 10000


def test_oversized_local_image_is_prepared_without_modifying_source(
    tmp_path, monkeypatch
):
    from PIL import Image

    from opinion_gateway import demo_preparation as demo

    file = tmp_path / "large.png"
    Image.new("RGB", (2000, 2000), "green").save(file)
    before = file.read_bytes()
    monkeypatch.setattr(demo, "MAX_IMAGE_BYTES", 100)
    prepared, transformed = demo.local_image(file)
    assert transformed and len(prepared) < len(before)
    assert prepared[:2] == b"\xff\xd8"
    assert file.read_bytes() == before


def test_beijing_deduplicates_same_permalink_and_preserves_unknown_counts():
    records, rejected = normalize_rows(
        [
            {
                "content": "暴雨",
                "pubtime": "2023年07月29日23:59",
                "url": "https://weibo.com/123/ABC?a=1",
                "like": "赞",
                "comment": "评论",
                "transfer": "转发",
            },
            {
                "content": "暴雨",
                "pubtime": "2023年07月29日23:59",
                "url": "https://weibo.com/123/ABC?a=2",
                "like": "12",
            },
        ],
        "beijingstorm",
        "text_only",
    )
    assert len(records) == 1 and records[0]["like_count"] == 12
    assert records[0]["comment_count"] is None
    assert rejected == [{"source_row": 1, "reason": "duplicate_permalink"}]


def test_disguised_animated_gif_uses_documented_first_frame(tmp_path):
    import io

    from opinion_gateway.demo_preparation import local_image
    from PIL import Image

    file = tmp_path / "fake.jpg"
    Image.new("RGB", (40, 40), "red").save(
        file,
        format="GIF",
        save_all=True,
        append_images=[Image.new("RGB", (40, 40), "blue")],
        duration=100,
        loop=0,
    )
    data, transformation = local_image(file)
    assert "first_frame" in transformation
    with Image.open(io.BytesIO(data)) as image:
        assert image.format == "JPEG"
        assert image.getpixel((140, 140))[0] > 200


@pytest.mark.parametrize("truncated", [False, True])
def test_unreadable_images_are_listed_and_trial_refills_from_valid_posts(
    tmp_path, truncated
):
    from opinion_gateway.demo_preparation import prepare_demo
    from PIL import Image

    source = tmp_path / "source"
    source.mkdir()
    (source / "broken.jpg").write_text("not an image", encoding="utf-8")
    if truncated:
        Image.new("RGB", (400, 400), "red").save(source / "broken.jpg")
        (source / "broken.jpg").write_bytes((source / "broken.jpg").read_bytes()[:-100])
    Image.new("RGB", (40, 40), "blue").save(source / "ok.jpg")
    path = source / "posts.json"
    path.write_text(
        json.dumps([row(1, 3, 100, ["broken.jpg"]), row(2, 3, 1, ["ok.jpg"])]),
        encoding="utf-8",
    )
    manifest = prepare_demo(
        path,
        "henan",
        tmp_path / "out",
        "demo",
        1,
        "text_image",
        tmp_path / "assets",
        images_only=True,
    )
    assert manifest["selected_posts"] == 1
    assert manifest["unavailable_images"][0]["source_ref"] == "broken.jpg"
    records = json.loads((tmp_path / "out/posts.json").read_text(encoding="utf-8"))
    assert records[0]["content"] == "帖子 2"
