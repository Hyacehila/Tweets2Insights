from datetime import UTC, datetime

import pytest
from opinion_core.schemas.workflow import CrawlSpec
from pydantic import ValidationError


def test_supported_platforms_exclude_x():
    for platform in ("wb", "xhs", "dy", "ks", "bili", "tieba", "zhihu"):
        assert CrawlSpec(platforms=[platform]).platforms == [platform]
    with pytest.raises(ValidationError):
        CrawlSpec(platforms=["x"])


def test_normalize_mediacrawler_post_and_comment():
    from crawler_worker.mediacrawler import normalize

    post = normalize(
        "wb",
        {
            "note_id": "7",
            "content": "<b>暴雨</b>",
            "create_time": 1700000000,
            "liked_count": "1.2万",
            "shared_count": "7",
        },
        "post",
    )
    comment = normalize(
        "wb", {"comment_id": "7", "note_id": "7", "content": "评论"}, "comment"
    )
    assert post.content == "暴雨"
    assert post.like_count == 12000
    assert post.repost_count == 7
    assert post.published_at == datetime.fromtimestamp(1700000000, UTC)
    assert post.post_id != comment.post_id
    assert comment.parent_ref == post.post_id
    assert comment.time_status == "missing"


def test_crawler_settings_never_returns_cookie(tmp_path, monkeypatch):
    from opinion_gateway.crawler_settings import private_config, save, status

    from opinion_gateway import credentials

    monkeypatch.setattr(credentials, "path", lambda: tmp_path / "credentials.json")
    save(
        {
            "platform": "wb",
            "login_type": "cookie",
            "cookie": "session=private-value",
            "headless": False,
        }
    )
    assert private_config("wb")["cookie"] == "session=private-value"
    assert "private-value" not in str(status())
    assert next(item for item in status()["platforms"] if item["id"] == "wb")[
        "cookie_configured"
    ]


def test_collection_filters_dates_and_caps_native_records(monkeypatch):
    from crawler_worker import runner

    records = [
        {
            "post_id": f"p{i}",
            "raw_id": str(i),
            "platform": "wb",
            "kind": "post",
            "content": "event",
            "published_at": f"2024-11-{i:02d}T00:00:00Z",
            "time_status": "parsed",
        }
        for i in range(1, 5)
    ]
    monkeypatch.setattr(
        runner,
        "fetch_page",
        lambda platform, payload: {"records": records, "next_cursor": None},
    )
    value = runner.collect(
        {
            "event_id": "demo",
            "input_mode": "keywords",
            "keywords": ["event"],
            "start": "2024-11-02T00:00:00Z",
            "end": "2024-11-04T00:00:00Z",
            "as_of": "2024-11-04T00:00:00Z",
        },
        {"platforms": ["wb"], "max_posts": 1},
    )
    assert len(value["records"]) == 1
    assert value["records"][0]["raw_id"] == "2"
