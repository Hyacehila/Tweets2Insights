"""Install the pinned upstream collector in a separate UV environment."""

import argparse
import json
import subprocess
from pathlib import Path

from opinion_gateway.crawler_settings import interpreter, root

REVISION = "d172fc8369d8479c96793a5b1e4d89fac43914c2"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    directory = root()
    if not args.check:
        if not directory.exists():
            directory.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                [
                    "git",
                    "clone",
                    "https://github.com/NanmiCoder/MediaCrawler.git",
                    str(directory),
                ],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(directory), "checkout", REVISION], check=True
            )
        subprocess.run(
            ["uv", "sync", "--frozen", "--project", str(directory)], check=True
        )
        subprocess.run(
            [
                "uv",
                "run",
                "--project",
                str(directory),
                "python",
                "-m",
                "playwright",
                "install",
                "chromium",
            ],
            check=True,
        )
    bridge = (
        Path(__file__).resolve().parents[1]
        / "backend/src/domain/crawler_worker/mediacrawler_bridge.py"
    )
    result = subprocess.run(
        [str(interpreter()), str(bridge)],
        input=json.dumps({"root": str(directory), "probe": True}),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    value = json.loads(result.stdout)
    if value.get("error") or not value.get("browser_installed"):
        raise RuntimeError(value.get("error", "Chromium is not installed"))
    print("MediaCrawler ready: " + ", ".join(value["platforms"]))


if __name__ == "__main__":
    main()
