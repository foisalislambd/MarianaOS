"""Filesystem tools."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Optional

from tools.base import BaseTool, ToolParam, ToolResult
from utils.paths import safe_resolve


class ListDirectoryTool(BaseTool):
    name = "list_directory"
    description = "List files and folders in a directory."
    parameters = [
        ToolParam(name="path", type="string", description="Directory path to list."),
        ToolParam(
            name="show_hidden",
            type="boolean",
            description="Include hidden files. Default false.",
            required=False,
        ),
    ]

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(
        self, path: str = ".", show_hidden: bool = False, **_: Any
    ) -> ToolResult:
        target = safe_resolve(path, self.workspace)
        if not target.exists():
            return ToolResult(success=False, output=f"Path not found: {target}")
        if not target.is_dir():
            return ToolResult(success=False, output=f"Not a directory: {target}")

        entries = []
        for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if not show_hidden and item.name.startswith("."):
                continue
            kind = "dir" if item.is_dir() else "file"
            size = item.stat().st_size if item.is_file() else 0
            entries.append(f"[{kind}] {item.name}" + (f" ({size} B)" if kind == "file" else ""))

        return ToolResult(
            success=True,
            output=f"{target}\n" + ("\n".join(entries) if entries else "(empty)"),
            data={"path": str(target), "count": len(entries)},
        )


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read a text file (truncated for large files)."
    parameters = [
        ToolParam(name="path", type="string", description="File path to read."),
        ToolParam(
            name="max_chars",
            type="integer",
            description="Max characters to return (default 12000).",
            required=False,
        ),
    ]

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(self, path: str, max_chars: int = 12000, **_: Any) -> ToolResult:
        target = safe_resolve(path, self.workspace)
        if not target.exists() or not target.is_file():
            return ToolResult(success=False, output=f"File not found: {target}")
        try:
            text = target.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return ToolResult(success=False, output=f"Cannot read file: {e}")
        truncated = len(text) > max_chars
        if truncated:
            text = text[:max_chars] + f"\n\n...[truncated, total {len(text)} chars]"
        return ToolResult(
            success=True,
            output=text,
            data={"path": str(target), "truncated": truncated},
        )


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Write or overwrite a text file."
    destructive = True
    parameters = [
        ToolParam(name="path", type="string", description="File path to write."),
        ToolParam(name="content", type="string", description="Full file content."),
        ToolParam(
            name="create_dirs",
            type="boolean",
            description="Create parent directories if missing. Default true.",
            required=False,
        ),
    ]

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(
        self, path: str, content: str, create_dirs: bool = True, **_: Any
    ) -> ToolResult:
        target = safe_resolve(path, self.workspace)
        if create_dirs:
            target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return ToolResult(
            success=True,
            output=f"Wrote {len(content)} chars to {target}",
            data={"path": str(target)},
        )


class CreateDirectoryTool(BaseTool):
    name = "create_directory"
    description = "Create a directory (and parents)."
    parameters = [
        ToolParam(name="path", type="string", description="Directory path to create."),
    ]

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(self, path: str, **_: Any) -> ToolResult:
        target = safe_resolve(path, self.workspace)
        target.mkdir(parents=True, exist_ok=True)
        return ToolResult(success=True, output=f"Created directory: {target}", data={"path": str(target)})


class DeletePathTool(BaseTool):
    name = "delete_path"
    description = "Delete a file or empty/non-empty directory. Destructive — use carefully."
    destructive = True
    parameters = [
        ToolParam(name="path", type="string", description="Path to delete."),
    ]

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(self, path: str, **_: Any) -> ToolResult:
        target = safe_resolve(path, self.workspace)
        if not target.exists():
            return ToolResult(success=False, output=f"Path not found: {target}")
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return ToolResult(success=True, output=f"Deleted: {target}")


class MovePathTool(BaseTool):
    name = "move_path"
    description = "Move or rename a file/directory."
    destructive = True
    parameters = [
        ToolParam(name="source", type="string", description="Source path."),
        ToolParam(name="destination", type="string", description="Destination path."),
    ]

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(self, source: str, destination: str, **_: Any) -> ToolResult:
        src = safe_resolve(source, self.workspace)
        dst = safe_resolve(destination, self.workspace)
        if not src.exists():
            return ToolResult(success=False, output=f"Source not found: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return ToolResult(
            success=True,
            output=f"Moved {src} -> {dst}",
            data={"source": str(src), "destination": str(dst)},
        )


class SearchFilesTool(BaseTool):
    name = "search_files"
    description = "Search for files by name glob under a root directory."
    parameters = [
        ToolParam(name="pattern", type="string", description="Glob pattern, e.g. '**/*.py'."),
        ToolParam(
            name="root",
            type="string",
            description="Root directory to search (default workspace).",
            required=False,
        ),
        ToolParam(
            name="limit",
            type="integer",
            description="Max results (default 40).",
            required=False,
        ),
    ]

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(
        self, pattern: str, root: Optional[str] = None, limit: int = 40, **_: Any
    ) -> ToolResult:
        base = safe_resolve(root or ".", self.workspace)
        if not base.exists():
            return ToolResult(success=False, output=f"Root not found: {base}")
        matches = []
        for p in base.glob(pattern):
            matches.append(str(p))
            if len(matches) >= max(1, min(limit, 200)):
                break
        return ToolResult(
            success=True,
            output="\n".join(matches) if matches else "No matches.",
            data={"count": len(matches), "matches": matches},
        )


class OpenInExplorerTool(BaseTool):
    name = "open_in_explorer"
    description = "Open a folder or file in Windows File Explorer."
    parameters = [
        ToolParam(name="path", type="string", description="Path to open in Explorer."),
    ]

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(self, path: str, **_: Any) -> ToolResult:
        target = safe_resolve(path, self.workspace)
        if not target.exists():
            return ToolResult(success=False, output=f"Path not found: {target}")
        os.startfile(str(target if target.is_dir() else target.parent))  # noqa: S606
        return ToolResult(success=True, output=f"Opened in Explorer: {target}")
