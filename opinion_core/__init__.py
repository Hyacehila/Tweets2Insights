"""Compatibility namespace; implementation resides in backend/src/domain."""
from pathlib import Path
__path__ = [str(Path(__file__).resolve().parents[1] / "backend" / "src" / "domain" / "opinion_core") ]
