"""Window management tools."""

from __future__ import annotations

from typing import Any, Optional

from tools.base import BaseTool, ToolParam, ToolResult


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
        import pygetwindow as gw

        titles = [t for t in gw.getAllTitles() if t and t.strip()]
        if filter:
            f = filter.lower()
            titles = [t for t in titles if f in t.lower()]
        # Dedupe preserving order
        seen = set()
        unique = []
        for t in titles:
            if t not in seen:
                seen.add(t)
                unique.append(t)
        return ToolResult(
            success=True,
            output="\n".join(unique) if unique else "No windows found.",
            data={"windows": unique, "count": len(unique)},
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
        import pygetwindow as gw

        matches = [w for w in gw.getAllWindows() if title.lower() in (w.title or "").lower()]
        if not matches:
            return ToolResult(success=False, output=f"No window matching '{title}'")
        win = matches[0]
        try:
            if win.isMinimized:
                win.restore()
            win.activate()
        except Exception:
            # Fallback via pyautogui alt-tab is unreliable; try Windows API
            try:
                import win32gui
                import win32con

                hwnd = win32gui.FindWindow(None, win.title)
                if hwnd:
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(hwnd)
            except Exception as e:
                return ToolResult(success=False, output=f"Could not focus window: {e}")
        return ToolResult(
            success=True,
            output=f"Focused window: {win.title}",
            data={"title": win.title},
        )


class GetActiveWindowTool(BaseTool):
    name = "get_active_window"
    description = "Get the currently active/focused window title and bounds."
    parameters = []

    async def execute(self, **_: Any) -> ToolResult:
        import pygetwindow as gw

        win = gw.getActiveWindow()
        if win is None:
            return ToolResult(success=False, output="No active window detected.")
        return ToolResult(
            success=True,
            output=f"Active: {win.title} @ ({win.left},{win.top}) {win.width}x{win.height}",
            data={
                "title": win.title,
                "left": win.left,
                "top": win.top,
                "width": win.width,
                "height": win.height,
            },
        )


class MinimizeWindowTool(BaseTool):
    name = "minimize_window"
    description = "Minimize a window by title substring."
    parameters = [
        ToolParam(name="title", type="string", description="Window title substring."),
    ]

    async def execute(self, title: str, **_: Any) -> ToolResult:
        import pygetwindow as gw

        matches = [w for w in gw.getAllWindows() if title.lower() in (w.title or "").lower()]
        if not matches:
            return ToolResult(success=False, output=f"No window matching '{title}'")
        matches[0].minimize()
        return ToolResult(success=True, output=f"Minimized: {matches[0].title}")


class MaximizeWindowTool(BaseTool):
    name = "maximize_window"
    description = "Maximize a window by title substring."
    parameters = [
        ToolParam(name="title", type="string", description="Window title substring."),
    ]

    async def execute(self, title: str, **_: Any) -> ToolResult:
        import pygetwindow as gw

        matches = [w for w in gw.getAllWindows() if title.lower() in (w.title or "").lower()]
        if not matches:
            return ToolResult(success=False, output=f"No window matching '{title}'")
        matches[0].maximize()
        return ToolResult(success=True, output=f"Maximized: {matches[0].title}")
