"""Operator CLI with the same configuration as Gateway and Worker."""

import sys
from src.config import load_settings
from opinion_gateway.cli import main


if __name__ == "__main__":
    settings = load_settings()
    arguments = sys.argv[1:]
    if not any(arg == "--root" or arg.startswith("--root=") for arg in arguments):
        arguments = ["--root", str(settings.asset_root), *arguments]
    raise SystemExit(main(arguments))
