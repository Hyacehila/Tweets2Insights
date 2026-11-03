from pathlib import Path
import json


class SkillLoader:
    def __init__(self, settings):
        self.roots = [
            (settings.repository_root / root).resolve()
            for root in settings.skills_roots
        ]
        config = json.loads(
            (settings.repository_root / "extensions_config.json").read_text(
                encoding="utf-8"
            )
        )
        self.enabled = set(config.get("skills", {}).get("enabled", []))

    def list(self):
        result = []
        for root in self.roots:
            for path in sorted(root.glob("*/SKILL.md")):
                if not path.resolve().is_relative_to(root):
                    continue
                result.append(
                    {"id": path.parent.name, "source": root.name, "path": str(path)}
                )
        return result

    def context(self, ids):
        parts = []
        for item in self.list():
            if item["id"] in ids and item["id"] in self.enabled:
                parts.append(Path(item["path"]).read_text(encoding="utf-8")[:6000])
        return "\n\n".join(parts)
