"""Static source checks only; no model, data-processing or scientific tests."""

import ast, json
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors = []
count = 0
for path in (ROOT / "backend/src").rglob("*.py"):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    count += 1
    if "gateway" not in path.relative_to(ROOT / "backend/src").parts:
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "src.gateway"
            ):
                errors.append(str(path) + ": harness imports app")
            if isinstance(node, ast.Import) and any(
                alias.name.startswith("src.gateway") for alias in node.names
            ):
                errors.append(str(path) + ": harness imports app")
for path in [
    ROOT / "extensions_config.json",
    ROOT / "backend/langgraph.json",
    ROOT / "frontend/package.json",
]:
    json.loads(path.read_text(encoding="utf-8"))
for path in [
    ROOT / "config.yaml",
    ROOT / "config.example.yaml",
    *sorted((ROOT / "docker").rglob("*.yaml")),
]:
    list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
for path in [ROOT / "scripts/dev.py", ROOT / "scripts/check_structure.py"]:
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
if errors:
    raise SystemExit("\n".join(errors))
print(
    f"Parsed {count} backend Python sources, launch/check scripts and JSON/YAML configuration; no reverse harness-to-gateway import. Behavior tests not run."
)
