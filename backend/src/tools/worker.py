from src.config import load_settings
from opinion_gateway.domain_worker import main


if __name__ == "__main__":
    settings = load_settings()
    raise SystemExit(main(["--root", str(settings.asset_root)]))
