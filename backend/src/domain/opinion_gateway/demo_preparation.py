"""Prepare local demo assets and executable requests without submitting a job."""

import argparse
import hashlib
import io
import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from opinion_core.ingestion.demo import (
    SHANGHAI,
    local_day,
    normalize_rows,
    read_rows,
    select_daily,
)
from opinion_core.labeling.media import (
    MAX_IMAGE_BYTES,
    MAX_IMAGE_PIXELS,
    MediaPolicy,
    normalize_image,
)
from opinion_core.schemas.workflow import RunRequest
from PIL import Image, ImageOps

from .application import ApplicationService
from .dataset_repository import atomic_json, safe_id
from .media_assets import MediaAssets


def local_image(path):
    """Convert large/unsupported media to a still JPEG; retain original files."""
    if path.stat().st_size > 128 * 1024 * 1024:
        raise ValueError(f"local image exceeds 128 MiB: {path.name}")
    with Image.open(path) as original:
        if original.width * original.height > 2 * MAX_IMAGE_PIXELS:
            raise ValueError(f"unsupported local image dimensions: {path.name}")
        reasons = []
        if original.width * original.height > MAX_IMAGE_PIXELS:
            reasons.append("large_dimensions")
        if path.stat().st_size > MAX_IMAGE_BYTES:
            reasons.append("oversized")
        if getattr(original, "is_animated", False):
            reasons.append("first_frame")
        if original.format not in {"JPEG", "PNG", "WEBP"}:
            reasons.append("format_" + str(original.format).lower())
        if not reasons:
            return path.read_bytes(), None
        original.seek(0)
        prepared = ImageOps.exif_transpose(original)
        prepared.thumbnail((1568, 1568), Image.Resampling.LANCZOS)
        rgba = prepared.convert("RGBA")
        rgb = Image.new("RGB", rgba.size, "white")
        rgb.paste(rgba, mask=rgba.getchannel("A"))
        buffer = io.BytesIO()
        rgb.save(buffer, "JPEG", quality=85, optimize=True)
    return normalize_image(buffer.getvalue()), "+".join(reasons)


def inspect_images(records, source_directory):
    valid, unavailable = {}, []
    for post in records:
        for reference in post["media_refs"]:
            if reference in valid:
                continue
            file = (source_directory / reference).resolve()
            if not file.is_relative_to(source_directory):
                raise ValueError("image path escaped source directory")
            try:
                if file.stat().st_size > 128 * 1024 * 1024:
                    raise ValueError("image exceeds 128 MiB")
                with Image.open(file) as image:
                    if image.width * image.height > 2 * MAX_IMAGE_PIXELS:
                        raise ValueError("image exceeds 80 megapixels")
                    image.verify()
                valid[reference] = True
            except (OSError, ValueError, Image.DecompressionBombError) as exc:
                valid[reference] = False
                unavailable.append(
                    {"source_ref": reference, "reason": type(exc).__name__}
                )
        post["media_refs"] = [ref for ref in post["media_refs"] if valid[ref]]
    return unavailable


def make_request(source, event_id, dataset_id, records, media_mode, image_cap):
    days = sorted(local_day(post) for post in records)
    start = datetime.fromisoformat(days[0]).replace(tzinfo=SHANGHAI)
    end = datetime.fromisoformat(days[-1]).replace(tzinfo=SHANGHAI) + timedelta(days=1)
    keywords = (
        ["北京暴雨", "防汛"]
        if source == "beijingstorm"
        else ["郑州大学生夜骑开封", "夜骑开封"]
    )
    return RunRequest.model_validate(
        {
            "event": {
                "event_id": event_id,
                "input_mode": "existing",
                "dataset_ref": dataset_id,
                "keywords": keywords,
                "start": start,
                "end": end,
                "as_of": datetime.now(UTC),
                "search_provider": "tavily",
                "objectives": ["retrospective"],
            },
            "run_id": "demo-retrospective-1",
            "observations": {"start": start, "end": end, "window_seconds": 86400},
            "labels": {
                "provider": "openai_decisions",
                "model": "gpt-6-luna",
                "batch_size": 1,
                "max_calls": len(records),
                "max_schema_calls": 4,
                "max_images_per_post": image_cap,
            },
            "max_total_calls": len(records) + 64,
            "media_mode": media_mode,
            "analysis": {
                "instruction": "分析每日高互动量帖子组成的 Demo。统计只描述此选取样本；区分源数据的早期零散讨论与事件高峰。"
            },
        }
    ).model_dump(mode="json")


def prepare_demo(
    source_path,
    source,
    output,
    event_id,
    limit,
    media_mode,
    asset_root,
    *,
    images_only=False,
    image_cap=3,
):
    safe_id(event_id)
    if not 1 <= image_cap <= 9:
        raise ValueError("image cap must be between 1 and 9")
    source_path, output = Path(source_path).resolve(), Path(output).resolve()
    if output == source_path.parent or output.is_relative_to(source_path.parent):
        raise ValueError("output must be outside the source directory")
    if images_only and media_mode != "text_image":
        raise ValueError("images-only sampling requires text_image mode")
    raw = read_rows(source_path)
    records, rejected = normalize_rows(raw, source, media_mode)
    unavailable = (
        inspect_images(records, source_path.parent)
        if media_mode == "text_image"
        else []
    )
    media = MediaAssets(asset_root, event_id)
    mapping, image_map, transformed_images = [], {}, []
    while True:
        selected, daily = select_daily(records, limit, images_only=images_only)
        if media_mode == "text_image" and not any(
            post["media_refs"] for post in selected
        ):
            raise ValueError(
                "selected dataset has no images; use text_only or supply actual images"
            )
        invalid = set()
        for post in selected:
            for reference in post["media_refs"]:
                if reference in image_map or reference in invalid:
                    continue
                file = (source_path.parent / reference).resolve()
                try:
                    data, transformed = local_image(file)
                    image_map[reference] = media.save(data)
                    if transformed:
                        transformed_images.append(
                            {
                                "source_ref": reference,
                                "source_bytes": file.stat().st_size,
                                "prepared_bytes": len(data),
                                "media_ref": image_map[reference],
                                "transformation": transformed,
                            }
                        )
                except (OSError, ValueError, Image.DecompressionBombError) as exc:
                    invalid.add(reference)
                    unavailable.append(
                        {"source_ref": reference, "reason": type(exc).__name__}
                    )
        if not invalid:
            break
        for post in records:
            post["media_refs"] = [
                ref for ref in post["media_refs"] if ref not in invalid
            ]
    for post in selected:
        mapping.append(
            {
                "post_id": post["post_id"],
                "source_row": int(post["post_id"].split("-")[2]),
                "original_media_refs": list(
                    raw[int(post["post_id"].split("-")[2]) - 1].get("image_urls", [])
                ),
                "usable_media_refs": list(post["media_refs"]),
            }
        )
        post["media_refs"] = [image_map[ref] for ref in post["media_refs"]]
    app = ApplicationService(asset_root)
    dataset = app.register_dataset(event_id, selected)
    request = make_request(
        source, event_id, dataset["dataset_id"], selected, media_mode, image_cap
    )
    plan = app.preview_plan(request)
    policy = MediaPolicy("openai_decisions", "gpt-6-luna", media_mode, image_cap)
    summary = policy.summary(selected)
    manifest = {
        "event_id": event_id,
        "source_path": str(source_path),
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "source_rows": len(raw),
        "valid_rows": len(records),
        "excluded_rows": rejected,
        "selected_posts": len(selected),
        "limit": limit,
        "media_mode": media_mode,
        "images_only_sample": images_only,
        "posts_with_images": summary["posts_with_images"],
        "total_image_references": summary["available_images"],
        "selected_images_for_model": summary["selected_images"],
        "unique_image_assets": len(set(image_map.values())),
        "max_images_per_post": image_cap,
        "transformed_images": transformed_images,
        "unavailable_images": unavailable,
        "day_timezone": "Asia/Shanghai",
        "heat": "like_count + comment_count + repost_count",
        "quota": "one per day when possible, then proportional remaining capacity; largest remainder",
        "daily_windows": len(daily),
        "selected_daily_windows": sum(d["selected"] > 0 for d in daily),
        "date_start": daily[0]["day"],
        "date_end": daily[-1]["day"],
        "dataset": dataset,
        "asset_root": str(Path(asset_root).resolve()),
        "paid_calls_made": 0,
        "rejection_counts": dict(Counter(item["reason"] for item in rejected)),
    }
    for name, value in [
        ("posts.json", selected),
        ("manifest.json", manifest),
        ("daily-selection.json", daily),
        ("source-map.json", mapping),
        ("run.json", request),
        ("plan.json", plan),
    ]:
        atomic_json(output / name, value)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--source-kind", choices=["beijingstorm", "henan"], required=True
    )
    parser.add_argument("--event", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument(
        "--media-mode", choices=["text_only", "text_image"], required=True
    )
    parser.add_argument("--images-only", action="store_true")
    parser.add_argument("--max-images-per-post", type=int, default=3)
    parser.add_argument("--asset-root", type=Path, default=Path(".opinion-assets"))
    args = parser.parse_args()
    result = prepare_demo(
        args.source,
        args.source_kind,
        args.output,
        args.event,
        args.limit,
        args.media_mode,
        args.asset_root,
        images_only=args.images_only,
        image_cap=args.max_images_per_post,
    )
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k
                not in {"excluded_rows", "transformed_images", "unavailable_images"}
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
