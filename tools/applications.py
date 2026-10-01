"""Application launch tools."""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any

from tools.base import BaseTool, ToolParam, ToolResult
from utils.paths import find_cursor_exe, safe_resolve


class OpenApplicationTool(BaseTool):
    name = "open_application"
    description = (
        "Launch an application by executable path, name, or common app id "
        "(e.g. 'notepad', 'chrome', 'explorer', 'calc', 'cursor')."
    )
    parameters = [
        ToolParam(
            name="app",
            type="string",
            description="App name or full path to .exe / .lnk.",
        ),
        ToolParam(
            name="args",
            type="string",
            description="Optional command-line arguments.",
            required=False,
        ),
    ]

    async def execute(self, app: str, args: str = "", **_: Any) -> ToolResult:
        app_l = app.strip().lower()
        known = {
            "notepad": "notepad.exe",
            "calc": "calc.exe",
            "calculator": "calc.exe",
            "explorer": "explorer.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
            "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "code": "code",
            "vscode": "code",
        }

        if app_l in ("cursor", "cursor ide"):
            exe = find_cursor_exe()
            if not exe:
                return ToolResult(
                    success=False,
                    output=(
                        "Cursor.exe not found on PATH or common install locations. "
                        "Install Cursor or add it to PATH."
                    ),
                )
            cmd = [str(exe)]
        elif app_l in known:
            cmd = [known[app_l]]
        else:
            cmd = [app]

        if args:
            cmd.extend(args.split())

        try:
            subprocess.Popen(
                cmd,
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            try:
                os.startfile(app)  # noqa: S606
            except Exception as e:
                return ToolResult(success=False, output=f"Failed to open '{app}': {e}")
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to open '{app}': {e}")

        await asyncio.sleep(0.8)
        return ToolResult(success=True, output=f"Launched: {' '.join(cmd)}")


class OpenUrlTool(BaseTool):
    name = "open_url"
    description = "Open a URL in the default web browser."
    parameters = [
        ToolParam(name="url", type="string", description="URL to open."),
    ]

    async def execute(self, url: str, **_: Any) -> ToolResult:
        import webbrowser

        if not url.startswith(("http://", "https://", "file://")):
            url = "https://" + url
        webbrowser.open(url)
        return ToolResult(success=True, output=f"Opened URL: {url}")


class OpenFolderInCursorTool(BaseTool):
    name = "open_folder_in_cursor"
    description = (
        "Open a folder (or file) in Cursor IDE. "
        "This is the preferred way to open projects in Cursor."
    )
    parameters = [
        ToolParam(name="path", type="string", description="Folder or file path to open."),
        ToolParam(
            name="new_window",
            type="boolean",
            description="Open in a new Cursor window. Default false.",
            required=False,
        ),
    ]

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(
        self, path: str, new_window: bool = False, **_: Any
    ) -> ToolResult:
        target = safe_resolve(path, self.workspace)
        if not target.exists():
            return ToolResult(success=False, output=f"Path not found: {target}")

        exe = find_cursor_exe()
        cmd: list[str]
        if exe:
            cmd = [str(exe)]
            if new_window:
                cmd.append("-n")
            cmd.append(str(target))
        else:
            cmd = ["cursor"]
            if new_window:
                cmd.append("-n")
            cmd.append(str(target))

        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
            )
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to open in Cursor: {e}")

        await asyncio.sleep(1.2)
        return ToolResult(
            success=True,
            output=f"Opened in Cursor: {target}",
            data={"path": str(target), "cmd": cmd},
        )
