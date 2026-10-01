"""Path helpers."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional


COMMON_CURSOR_PATHS = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "cursor" / "Cursor.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "cursor" / "Cursor.exe",
    Path(os.environ.get("PROGRAMFILES", "")) / "Cursor" / "Cursor.exe",
    Path.home() / "AppData" / "Local" / "Programs" / "cursor" / "Cursor.exe",
]


def find_cursor_exe() -> Optional[Path]:
    """Auto-detect Cursor CLI / executable (PATH, then common install folders)."""
    which = shutil.which("cursor")
    if which:
        return Path(which)
    for candidate in COMMON_CURSOR_PATHS:
        if candidate.exists():
            return candidate
    return None


def safe_resolve(path: str | Path, workspace: Path | None = None) -> Path:
    """Resolve a path; expand ~ and relative paths against workspace."""
    p = Path(str(path)).expanduser()
    if not p.is_absolute() and workspace is not None:
        p = workspace / p
    return p.resolve()
