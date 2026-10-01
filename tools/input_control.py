"""Mouse and keyboard control via uiautomation."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from tools.base import BaseTool, ToolParam, ToolResult
from utils import win_ui


class MouseClickTool(BaseTool):
    name = "mouse_click"
    description = (
        "Click the mouse at screen coordinates (x, y). "
        "Prefer click_control / get_ui_tree when the UI element name is known."
    )
    parameters = [
        ToolParam(name="x", type="integer", description="X coordinate in screen pixels."),
        ToolParam(name="y", type="integer", description="Y coordinate in screen pixels."),
        ToolParam(
            name="button",
            type="string",
            description="left, right, or middle. Default left.",
            required=False,
            enum=["left", "right", "middle"],
        ),
        ToolParam(
            name="clicks",
            type="integer",
            description="Number of clicks (1 or 2). Default 1.",
            required=False,
        ),
    ]

    async def execute(
        self, x: int, y: int, button: str = "left", clicks: int = 1, **_: Any
    ) -> ToolResult:
        win_ui.click_xy(int(x), int(y), button=button or "left", clicks=int(clicks or 1))
        return ToolResult(
            success=True,
            output=f"Clicked {button} x{clicks} at ({x}, {y})",
            data={"x": x, "y": y, "button": button, "clicks": clicks},
        )


class MouseMoveTool(BaseTool):
    name = "mouse_move"
    description = "Move the mouse cursor to (x, y) without clicking."
    parameters = [
        ToolParam(name="x", type="integer", description="X coordinate."),
        ToolParam(name="y", type="integer", description="Y coordinate."),
    ]

    async def execute(self, x: int, y: int, **_: Any) -> ToolResult:
        win_ui.move_mouse(int(x), int(y))
        return ToolResult(success=True, output=f"Moved mouse to ({x}, {y})")


class MouseScrollTool(BaseTool):
    name = "mouse_scroll"
    description = "Scroll the mouse wheel. Positive = up, negative = down."
    parameters = [
        ToolParam(name="clicks", type="integer", description="Scroll amount (e.g. 3 or -3)."),
        ToolParam(name="x", type="integer", description="Optional X to move to first.", required=False),
        ToolParam(name="y", type="integer", description="Optional Y to move to first.", required=False),
    ]

    async def execute(
        self, clicks: int, x: Optional[int] = None, y: Optional[int] = None, **_: Any
    ) -> ToolResult:
        win_ui.scroll(int(clicks), x=x, y=y)
        return ToolResult(success=True, output=f"Scrolled {clicks}")


class TypeTextTool(BaseTool):
    name = "type_text"
    description = (
        "Type text into the currently focused window (clipboard paste). "
        "Prefer set_control_value when targeting a named edit control."
    )
    parameters = [
        ToolParam(name="text", type="string", description="Text to type."),
    ]

    async def execute(self, text: str, **_: Any) -> ToolResult:
        win_ui.send_keys(text)
        return ToolResult(
            success=True,
            output=f"Typed {len(text)} characters",
            data={"length": len(text)},
        )


class HotkeyTool(BaseTool):
    name = "hotkey"
    description = (
        "Press a keyboard shortcut, e.g. keys=['ctrl','s'] or keys=['ctrl','shift','p']."
    )
    parameters = [
        ToolParam(
            name="keys",
            type="array",
            description='List of keys, e.g. ["ctrl", "shift", "p"].',
            items_type="string",
        ),
    ]

    async def execute(self, keys: list, **_: Any) -> ToolResult:
        if not keys or not isinstance(keys, list):
            return ToolResult(success=False, output="keys must be a non-empty list")
        cleaned = [str(k).lower() for k in keys]
        win_ui.send_hotkey(*cleaned)
        return ToolResult(success=True, output=f"Pressed hotkey: {'+'.join(cleaned)}")


class PressKeyTool(BaseTool):
    name = "press_key"
    description = "Press a single key (enter, escape, tab, backspace, delete, arrows, f1-f12…)."
    parameters = [
        ToolParam(name="key", type="string", description="Key name."),
        ToolParam(
            name="times",
            type="integer",
            description="How many times to press (default 1).",
            required=False,
        ),
    ]

    async def execute(self, key: str, times: int = 1, **_: Any) -> ToolResult:
        n = max(1, min(int(times or 1), 20))
        win_ui.press_key(key, times=n)
        return ToolResult(success=True, output=f"Pressed '{key}' x{n}")


class GetMousePositionTool(BaseTool):
    name = "get_mouse_position"
    description = "Get the current mouse cursor position and screen size."
    parameters = []

    async def execute(self, **_: Any) -> ToolResult:
        x, y = win_ui.mouse_position()
        w, h = win_ui.screen_size()
        return ToolResult(
            success=True,
            output=f"Mouse at ({x}, {y}); screen {w}x{h}",
            data={"x": x, "y": y, "screen_width": w, "screen_height": h},
        )


class WaitTool(BaseTool):
    name = "wait"
    description = "Wait/sleep for a number of seconds (UI animations, app launches)."
    parameters = [
        ToolParam(name="seconds", type="number", description="Seconds to wait (max 30)."),
    ]

    async def execute(self, seconds: float = 1.0, **_: Any) -> ToolResult:
        sec = max(0.1, min(float(seconds), 30.0))
        await asyncio.sleep(sec)
        return ToolResult(success=True, output=f"Waited {sec} seconds")
