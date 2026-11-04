"""Entry point executed by MediaCrawler's interpreter, never the application env."""

import asyncio
import contextlib
import importlib
import json
import os
import sys
import traceback
from pathlib import Path


class CollectionLimit(BaseException):
    pass


async def run(options):
    root = Path(options["root"]).resolve()
    os.chdir(root)
    sys.path.insert(0, str(root))
    import config
    import main

    if options.get("probe"):
        from playwright.async_api import async_playwright

        async with async_playwright() as browser:
            executable = Path(browser.chromium.executable_path)
        return {
            "platforms": sorted(main.CrawlerFactory.CRAWLERS),
            "browser_installed": executable.is_file(),
        }
    values = {
        "PLATFORM": options["platform"],
        "KEYWORDS": ",".join(options["keywords"]),
        "CRAWLER_TYPE": "search",
        "LOGIN_TYPE": options["login_type"],
        "COOKIES": options.get("cookie", ""),
        "ENABLE_CDP_MODE": False,
        "CDP_CONNECT_EXISTING": False,
        "HEADLESS": options["headless"] if options["login_type"] == "cookie" else False,
        "SAVE_LOGIN_STATE": True,
        "USER_DATA_DIR": options["profile"],
        "SAVE_DATA_OPTION": "jsonl",
        "SAVE_DATA_PATH": options["output"],
        "START_PAGE": 1,
        "CRAWLER_MAX_NOTES_COUNT": options["max_posts"],
        "MAX_CONCURRENCY_NUM": 1,
        "ENABLE_GET_COMMENTS": options["max_comments"] > 0,
        "CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES": options["max_comments_per_post"],
        "ENABLE_GET_SUB_COMMENTS": options["include_sub_comments"],
        "ENABLE_GET_MEDIA": options["collect_images"],
        "ENABLE_GET_WORDCLOUD": False,
        "CRAWLER_MAX_SLEEP_SEC": max(1, options["interval_seconds"]),
        "ENABLE_IP_PROXY": False,
    }
    for key, value in values.items():
        setattr(config, key, value)
    from tools.async_file_writer import AsyncFileWriter

    write = AsyncFileWriter.write_to_jsonl
    seen = {"contents": set(), "comments": set()}

    async def bounded_write(self, item, item_type):
        bucket = "comments" if item_type == "comments" else "contents"
        identity = str(
            item.get("comment_id")
            if bucket == "comments"
            else next(
                (
                    item[key]
                    for key in ("note_id", "video_id", "aweme_id", "content_id")
                    if key in item
                ),
                "",
            )
        )
        if identity in seen[bucket]:
            return
        limit = (
            options["max_comments"] if bucket == "comments" else options["max_posts"]
        )
        if len(seen[bucket]) >= limit:
            if bucket == "contents":
                raise CollectionLimit()
            return
        seen[bucket].add(identity)
        await write(self, item, item_type)

    AsyncFileWriter.write_to_jsonl = bounded_write
    modules = {
        "wb": ("weibo", "WeiboClient", "get_note_by_keyword"),
        "xhs": ("xhs", "XiaoHongShuClient", "get_note_by_keyword"),
        "dy": ("douyin", "DouYinClient", "search_info_by_keyword"),
        "ks": ("kuaishou", "KuaiShouClient", "search_info_by_keyword_v2"),
        "bili": ("bilibili", "BilibiliClient", "search_video_by_keyword"),
        "tieba": ("tieba", "BaiduTieBaClient", "get_notes_by_keyword"),
        "zhihu": ("zhihu", "ZhiHuClient", "get_note_by_keyword"),
    }
    module, name, method = modules[options["platform"]]
    client = getattr(importlib.import_module(f"media_platform.{module}.client"), name)
    original = getattr(client, method)
    pages = 0

    async def bounded_search(self, *args, **kwargs):
        nonlocal pages
        if pages >= options["max_pages"]:
            raise CollectionLimit()
        pages += 1
        return await original(self, *args, **kwargs)

    setattr(client, method, bounded_search)
    from media_downloader import MediaDownloader, MediaType

    download = MediaDownloader.download_all

    async def image_downloads(self, items, *args, **kwargs):
        images = [item for item in items if item.media_type == MediaType.IMAGE][
            : options["max_images_per_post"]
        ]
        return await download(self, images, *args, **kwargs)

    MediaDownloader.download_all = image_downloads
    main.crawler = main.CrawlerFactory.create_crawler(platform=options["platform"])
    limited = False
    try:
        await asyncio.wait_for(main.crawler.start(), timeout=options["timeout_seconds"])
    except CollectionLimit:
        limited = True
    finally:
        await main.async_cleanup()
    return {"pages": pages, "limited": limited}


def main():
    options = json.load(sys.stdin)
    # Upstream logs may contain session data; only structured status leaves this process.
    with (
        open(os.devnull, "w", encoding="utf-8") as sink,
        contextlib.redirect_stdout(sink),
        contextlib.redirect_stderr(sink),
    ):
        try:
            result = asyncio.run(run(options))
        except (Exception, CollectionLimit) as exc:  # noqa: BLE001 -- CLI returns a structured failure to the parent.
            result = {
                "error": str(exc) or type(exc).__name__,
                "traceback": traceback.format_exc(),
            }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
