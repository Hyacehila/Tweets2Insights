"""Operator-owned MediaCrawler settings and private platform sessions."""

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from . import credentials

PLATFORMS = {
    "wb": "微博",
    "xhs": "小红书",
    "dy": "抖音",
    "ks": "快手",
    "bili": "哔哩哔哩",
    "tieba": "百度贴吧",
    "zhihu": "知乎",
}


class CrawlerSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    platform: Literal["wb", "xhs", "dy", "ks", "bili", "tieba", "zhihu"]
    login_type: Literal["qrcode", "cookie"] = "qrcode"
    cookie: SecretStr | None = None
    clear_cookie: bool = False
    headless: bool = False
    timeout_seconds: int = Field(default=1200, ge=60, le=7200)


def root():
    return Path(
        os.environ.get(
            "MEDIACRAWLER_ROOT",
            credentials.path().parent / ".integrations" / "MediaCrawler",
        )
    ).resolve()


def interpreter():
    return (
        root() / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    )


def private_config(platform):
    if platform not in PLATFORMS:
        raise ValueError("unsupported MediaCrawler platform")
    data = credentials.read()
    settings = data.get("MEDIACRAWLER_SETTINGS", {}).get(platform, {})
    return {
        "login_type": "qrcode",
        "headless": False,
        "timeout_seconds": 1200,
        **settings,
        "cookie": data.get("MEDIACRAWLER_COOKIES", {}).get(platform, ""),
    }


def status():
    result = []
    for platform, name in PLATFORMS.items():
        config = private_config(platform)
        result.append(
            {
                "id": platform,
                "name": name,
                **{key: value for key, value in config.items() if key != "cookie"},
                "cookie_configured": bool(config["cookie"]),
            }
        )
    return {
        "installed": (root() / "main.py").is_file() and interpreter().is_file(),
        "platforms": result,
    }


def save(body):
    body = CrawlerSettings.model_validate(body)

    def change(data):
        data.setdefault("MEDIACRAWLER_SETTINGS", {})[body.platform] = body.model_dump(
            exclude={"platform", "cookie", "clear_cookie"}
        )
        if body.clear_cookie:
            data.setdefault("MEDIACRAWLER_COOKIES", {}).pop(body.platform, None)
        elif body.cookie and body.cookie.get_secret_value().strip():
            data.setdefault("MEDIACRAWLER_COOKIES", {})[body.platform] = (
                body.cookie.get_secret_value().strip()
            )

    credentials.update(change)
    return status()
