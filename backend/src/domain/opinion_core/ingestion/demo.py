"""Deterministic daily popularity samples from the two local event exports."""

import hashlib
import json
import re
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

from opinion_core.schemas.records import PostRecord

SHANGHAI = timezone(timedelta(hours=8))
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def read_rows(path):
    """Read source values, without editing the workbook or evaluating formulas."""
    path = Path(path)
    if path.suffix.lower() == ".json":
        rows = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValueError("source must contain an array of posts")
        return rows
    if path.suffix.lower() != ".xlsx":
        raise ValueError("supported sources: JSON and XLSX")
    with zipfile.ZipFile(path) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = [
                "".join(n.itertext())
                for n in ET.fromstring(archive.read("xl/sharedStrings.xml"))
            ]
        root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows, headers = [], {}
        for row in root.findall("m:sheetData/m:row", NS):
            cells = {}
            for cell in row:
                value = cell.find("m:v", NS)
                inline = cell.find("m:is", NS)
                text = (
                    value.text
                    if value is not None
                    else "".join(inline.itertext())
                    if inline is not None
                    else ""
                )
                if cell.get("t") == "s":
                    text = strings[int(text)]
                cells[re.sub(r"\d", "", cell.get("r"))] = text or ""
            if not headers:
                headers = {column: value for column, value in cells.items() if value}
            else:
                rows.append(
                    {name: cells.get(column, "") for column, name in headers.items()}
                )
        return rows


def _count(value):
    if value is None or str(value).strip() in {"", "-", "赞", "评论", "转发"}:
        return None
    text = str(value).strip().replace(",", "").removesuffix("+")
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(万|亿)?", text)
    if not match:
        raise ValueError(f"invalid engagement count: {text[:40]}")
    return int(float(match[1]) * {None: 1, "万": 10000, "亿": 100000000}[match[2]])


def normalize_rows(rows, source, media_mode):
    """Keep source rows distinct; source row numbers make every ID traceable."""
    if source not in {"beijingstorm", "henan"} or media_mode not in {
        "text_only",
        "text_image",
    }:
        raise ValueError("unknown source or media mode")
    records, rejected = [], []
    for index, row in enumerate(rows, 1):
        original_time = str(row.get("publish_time", row.get("pubtime", "")))
        parsed = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y年%m月%d日%H:%M"):
            try:
                parsed = datetime.strptime(original_time, fmt).replace(tzinfo=SHANGHAI)
                break
            except ValueError:
                pass
        if parsed is None:
            rejected.append({"source_row": index, "reason": "invalid_time"})
            continue
        media = row.get("image_urls", []) if media_mode == "text_image" else []
        if not isinstance(media, list) or not all(
            isinstance(ref, str) for ref in media
        ):
            raise ValueError(f"invalid image list at row {index}")
        content = str(row.get("content", "") or "").strip()
        if not content and not media:
            rejected.append({"source_row": index, "reason": "empty_content"})
            continue
        digest = hashlib.sha256(
            json.dumps(row, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:16]
        source_url = row.get("url") or None
        raw_id = (
            urlsplit(source_url).path.rstrip("/").split("/")[-1]
            if source_url
            else f"row-{index}"
        )
        record = PostRecord(
            post_id=f"demo-{source}-{index}-{digest}",
            platform="weibo",
            raw_id=raw_id,
            content=content,
            published_at=parsed,
            original_time=original_time,
            time_status="parsed",
            source_url=source_url,
            author_ref=row.get("user_id") or None,
            region=row.get("location", row.get("place")) or None,
            media_refs=media,
            like_count=_count(row.get("like_count", row.get("like"))),
            comment_count=_count(row.get("comment_count", row.get("comment"))),
            repost_count=_count(row.get("repost_count", row.get("transfer"))),
        )
        records.append(record.model_dump(mode="json"))
    if source == "beijingstorm":
        distinct = {}
        for record in sorted(
            records, key=lambda p: (-heat(p), int(p["post_id"].split("-")[2]))
        ):
            url = urlsplit(record["source_url"] or "")
            key = (
                url.netloc.lower() + url.path
                if url.netloc and url.path
                else record["post_id"]
            )
            if key in distinct:
                rejected.append(
                    {
                        "source_row": int(record["post_id"].split("-")[2]),
                        "reason": "duplicate_permalink",
                    }
                )
            else:
                distinct[key] = record
        records = sorted(
            distinct.values(), key=lambda p: int(p["post_id"].split("-")[2])
        )
    return records, sorted(rejected, key=lambda item: item["source_row"])


def heat(post):
    return sum(
        post.get(key) or 0 for key in ("like_count", "comment_count", "repost_count")
    )


def local_day(post):
    return (
        datetime.fromisoformat(post["published_at"])
        .astimezone(SHANGHAI)
        .date()
        .isoformat()
    )


def select_daily(records, limit, *, images_only=False):
    """Allocate one per day then proportionally by remaining daily population.

    Largest remainders fill the exact cap. Within each day take descending heat;
    ties use publication time then stable ID. Images-only is for vision cost trials.
    """
    if not 1 <= limit <= 10000:
        raise ValueError("demo limit must be between 1 and 10000")
    buckets = defaultdict(list)
    for post in records:
        if not images_only or post["media_refs"]:
            buckets[local_day(post)].append(post)
    if not buckets:
        raise ValueError(
            "no eligible posts with images" if images_only else "no eligible posts"
        )
    days = sorted(buckets)
    for posts in buckets.values():
        posts.sort(key=lambda p: (-heat(p), p["published_at"], p["post_id"]))
    target = min(limit, sum(map(len, buckets.values())))
    quotas = {day: int(target >= len(days)) for day in days}
    remaining = target - sum(quotas.values())
    capacity = {day: len(buckets[day]) - quotas[day] for day in days}
    total_capacity = sum(capacity.values())
    if remaining:
        floors = {day: remaining * capacity[day] // total_capacity for day in days}
        for day in days:
            quotas[day] += floors[day]
        left = remaining - sum(floors.values())
        remainders = sorted(
            days, key=lambda day: (-(remaining * capacity[day] % total_capacity), day)
        )
        for day in remainders[:left]:
            quotas[day] += 1
    selected, daily = [], []
    for day in days:
        chosen = buckets[day][: quotas[day]]
        selected.extend(chosen)
        daily.append(
            {
                "day": day,
                "available": len(buckets[day]),
                "selected": len(chosen),
                "maximum_heat": heat(buckets[day][0]),
                "minimum_selected_heat": min(map(heat, chosen)) if chosen else None,
            }
        )
    selected.sort(key=lambda p: (p["published_at"], p["post_id"]))
    return selected, daily
