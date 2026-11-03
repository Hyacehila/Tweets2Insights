from pathlib import Path
import re


class ThreadWorkspace:
    """File capability boundary; not an OS sandbox and exposes no arbitrary shell."""

    def __init__(self, root, thread_id):
        if not re.fullmatch(r"[a-f0-9]{32}", thread_id):
            raise ValueError("invalid thread ID")
        base = root.resolve()
        self.root = (base / "threads" / thread_id).resolve()
        if not self.root.is_relative_to(base):
            raise ValueError("thread workspace escaped state directory")
        for name in ("uploads", "outputs", "workspace"):
            area = (self.root / name).resolve()
            if not area.is_relative_to(self.root):
                raise ValueError("thread area escaped workspace")
            area.mkdir(parents=True, exist_ok=True)

    def path(self, area, name):
        if (
            area not in {"uploads", "outputs", "workspace"}
            or Path(name).name != name
            or name in {".", ".."}
        ):
            raise ValueError("invalid workspace path")
        target = (self.root / area / name).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("path escaped workspace")
        return target
