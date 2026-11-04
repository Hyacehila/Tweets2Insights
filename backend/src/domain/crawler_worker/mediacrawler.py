"""Run official MediaCrawler in its own UV environment and normalize its output."""

import hashlib
import html
import json
import os
import re
import subprocess
import uuid
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from opinion_core.schemas.records import PostRecord
from opinion_gateway.connectors import ConnectorUnavailable, WaitingForAuthentication
from opinion_gateway.crawler_settings import interpreter, private_config, root
from opinion_gateway.dataset_repository import storage_id
from opinion_gateway.diagnostics import redact
from opinion_gateway.media_assets import MediaAssets

from opinion_gateway import credentials


def first(row, *keys):
    return next(
        (row[key] for key in keys if row.get(key) is not None and row[key] != ""), None
    )


def identifier(platform, kind, raw_id):
    return "p-" + hashlib.sha256(f"{platform}:{kind}:{raw_id}".encode()).hexdigest()


def count(value):
    if value is None:
        return None
    try:
        text = str(value).replace(",", "").strip().lower()
        factor = (
            10000
            if text.endswith("万")
            else 100000000
            if text.endswith("亿")
            else 1000
            if text.endswith("k")
            else 1
        )
        return max(0, int(float(text[:-1] if factor != 1 else text) * factor))
    except (ValueError, OverflowError):
        return None


def normalize(platform, row, kind):
    raw_id = (
        first(row, "comment_id")
        if kind == "comment"
        else first(row, "note_id", "aweme_id", "video_id", "content_id")
    )
    if raw_id is None:
        raise ValueError(f"{platform} record is missing an ID")
    raw_time = first(row, "create_time", "time", "created_time", "publish_time")
    date = None
    if raw_time is not None:
        try:
            if isinstance(raw_time, (float, int)) or str(raw_time).isdigit():
                timestamp = float(raw_time)
                date = datetime.fromtimestamp(
                    timestamp / 1000 if timestamp > 1e11 else timestamp, UTC
                )
            else:
                date = datetime.fromisoformat(str(raw_time))
                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone(timedelta(hours=8)))
        except (ValueError, OverflowError, OSError):
            pass
    title = str(row.get("title") or "")
    content = str(first(row, "content", "content_text", "desc", "text") or "")
    text = (title + "\n" if title and title != content else "") + content
    parent = (
        first(row, "note_id", "aweme_id", "video_id", "content_id")
        if kind == "comment"
        else None
    )
    return PostRecord(
        post_id=identifier(platform, kind, raw_id),
        raw_id=str(raw_id),
        platform=platform,
        kind=kind,
        content=html.unescape(re.sub(r"<[^>]*>", "", text)),
        published_at=date,
        original_time=str(raw_time) if raw_time else None,
        time_status="parsed" if date else "invalid" if raw_time else "missing",
        collected_at=datetime.now(UTC),
        parent_ref=identifier(platform, "post", parent) if parent else None,
        author_ref=str(first(row, "creator_hash", "user_id"))
        if first(row, "creator_hash", "user_id")
        else None,
        source_url=first(row, "note_url", "aweme_url", "video_url", "content_url"),
        like_count=count(
            first(
                row, "liked_count", "like_count", "voteup_count", "comment_like_count"
            )
        ),
        comment_count=count(
            first(
                row,
                "comments_count",
                "comment_count",
                "video_comment",
                "total_replay_num",
            )
        ),
        repost_count=count(
            first(row, "shared_count", "share_count", "video_share_count")
        ),
        read_count=count(first(row, "read_count", "video_play_count", "viewd_count")),
    )


def stop_process_tree(process):
    import psutil

    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
        for child in reversed(children):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        parent.kill()
        psutil.wait_procs([parent, *children], timeout=5)
    except psutil.NoSuchProcess:
        pass


def fetch_page(platform, payload):
    if not interpreter().is_file() or not (root() / "main.py").is_file():
        raise ConnectorUnavailable(
            "MediaCrawler is not installed. Run: uv run --project backend python scripts/setup_mediacrawler.py"
        )
    config = private_config(platform)
    if config["login_type"] == "cookie" and not config["cookie"]:
        raise WaitingForAuthentication(
            f"{platform}: configure the platform Cookie in API settings"
        )
    project = credentials.path().parent
    asset_root = Path(
        payload.get("_asset_root") or project / ".opinion-assets"
    ).resolve()
    output = (
        asset_root
        / storage_id(payload["event"]["event_id"])
        / "crawl"
        / uuid.uuid4().hex
    )
    output.mkdir(parents=True)
    config.update(
        platform=platform,
        root=str(root()),
        output=str(output),
        profile=str(project / ".app-state" / "mediacrawler" / "sessions" / "%s"),
        keywords=payload["event"]["keywords"],
        **payload["spec"],
    )
    # Limits in the original spec must not replace the remaining global limits.
    config["max_posts"], config["max_comments"] = (
        payload["remaining_posts"],
        payload["remaining_comments"],
    )
    process = subprocess.Popen(
        [str(interpreter()), str(Path(__file__).with_name("mediacrawler_bridge.py"))],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        try:
            stdout, _ = process.communicate(
                json.dumps(config), timeout=config["timeout_seconds"] + 20
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                f"{platform}: MediaCrawler exceeded the configured time limit"
            ) from exc
        result = json.loads(stdout)
        if result.get("error"):
            raise RuntimeError(
                redact(
                    f"MediaCrawler {platform}: {result['error']}\n{result.get('traceback', '')}"
                )
            )
        records = []
        for file in sorted((output / platform / "jsonl").glob("*.jsonl")):
            kind = "comment" if "comments" in file.name else "post"
            for line in file.read_text(encoding="utf-8").splitlines():
                post = normalize(platform, json.loads(line), kind)
                if config["collect_images"]:
                    directory = (output / platform / "media" / post.raw_id).resolve()
                    if (
                        directory.is_relative_to(output.resolve())
                        and directory.is_dir()
                    ):
                        from opinion_gateway.demo_preparation import local_image

                        for picture in sorted(directory.iterdir()):
                            if len(post.media_refs) >= config["max_images_per_post"]:
                                break
                            if picture.suffix.lower() in (
                                ".jpg",
                                ".jpeg",
                                ".png",
                                ".webp",
                                ".gif",
                            ):
                                try:
                                    content, _ = local_image(picture)
                                    post.media_refs.append(
                                        MediaAssets(
                                            asset_root, payload["event"]["event_id"]
                                        ).save(content)
                                    )
                                except (OSError, ValueError):
                                    continue
                records.append(post.model_dump(mode="json"))
        return {
            "records": records,
            "next_cursor": None,
            "partial": result.get("limited", False),
            "pages": result.get("pages", 0),
        }
    finally:
        if process.poll() is None:
            stop_process_tree(process)
            process.communicate()
