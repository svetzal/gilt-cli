from __future__ import annotations

from pathlib import Path

from gilt.workspace import Workspace


def make_workspace(tmp_path: Path, *, init_dirs: list[str] | None = None) -> Workspace:
    ws = Workspace(root=tmp_path)
    for attr in init_dirs or []:
        path: Path = getattr(ws, attr)
        target = path if not path.suffix else path.parent
        target.mkdir(parents=True, exist_ok=True)
    return ws
