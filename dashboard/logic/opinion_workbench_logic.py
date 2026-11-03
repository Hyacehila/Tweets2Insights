"""Operator-configured storage root; event selection uses IDs, never environment mutation."""
from pathlib import Path


def default_asset_root():
    return Path(__file__).resolve().parents[2] / '.opinion-assets'
