"""Window management via uiautomation."""

from __future__ import annotations

from typing import Any, Optional

from tools.base import BaseTool, ToolParam, ToolResult
from utils import win_ui


class ListWindowsTool(BaseTool):
    name = "list_windows"
    description = "List visible window titles currently open on the desktop."
    parameters = [
        ToolParam(
            name="filter",
            type="string",
            description="Optional case-insensitive substring filter for titles.",
            required=False,
        ),
    ]

    async def execute(self, filter: Optional[str] = None, **_: Any) -> ToolResult:
        titles = win_ui.list_windows(filter or "")
        return ToolResult(
            success=True,
            output="\n".join(titles) if titles else "No windows found.",
            data={"windows": titles, "count": len(titles)},
        )


class FocusWindowTool(BaseTool):
    name = "focus_window"
    description = "Bring a window to the foreground by title substring match."
    parameters = [
        ToolParam(
            name="title",
            type="string",
            description="Substring of the window title (e.g. 'Cursor', 'Chrome').",
        ),
    ]

    async def execute(self, title: str, **_: Any) -> ToolResult:
        ok, msg = win_ui.focus_window(title)
        return ToolResult(
            success=ok,
            output=f"Focused window: {msg}" if ok else msg,
            data={"title": msg} if ok else {},
        )


class GetActiveWindowTool(BaseTool):
    name = "get_active_window"
    description = "Get the currently active/focused window title and bounds."
    parameters = []

    async def execute(self, **_: Any) -> ToolResult:
        info = win_ui.get_active_window_info()
        if not info:
            return ToolResult(success=False, output="No active window detected.")
        return ToolResult(
            success=True,
            output=(
                f"Active: {info['title']} @ ({info['left']},{info['top']}) "
                f"{info['width']}x{info['height']}"
            ),
            data=info,
        )


class MinimizeWindowTool(BaseTool):
    name = "minimize_window"
    description = "Minimize a window by title substring."
    parameters = [
        ToolParam(name="title", type="string", description="Window title substring."),
    ]

    async def execute(self, title: str, **_: Any) -> ToolResult:
        ok, msg = win_ui.minimize_window(title)
        return ToolResult(success=ok, output=f"Minimized: {msg}" if ok else msg)


class MaximizeWindowTool(BaseTool):
    name = "maximize_window"
    description = "Maximize a window by title substring."
    parameters = [
        ToolParam(name="title", type="string", description="Window title substring."),
    ]

    async def execute(self, title: str, **_: Any) -> ToolResult:
        ok, msg = win_ui.maximize_window(title)
        return ToolResult(success=ok, output=f"Maximized: {msg}" if ok else msg)
