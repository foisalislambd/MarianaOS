"""Mouse and keyboard control tools."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from tools.base import BaseTool, ToolParam, ToolResult


def _pyautogui():
    import pyautogui

    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
    return pyautogui


class MouseClickTool(BaseTool):
    name = "mouse_click"
    description = (
        "Click the mouse at screen coordinates (x, y). "
        "Take a screenshot first if you need to locate UI elements."
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
        pg = _pyautogui()
        pg.click(x=x, y=y, button=button, clicks=max(1, min(clicks, 3)))
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
        ToolParam(
            name="duration",
            type="number",
            description="Move duration in seconds (default 0.2).",
            required=False,
        ),
    ]

    async def execute(self, x: int, y: int, duration: float = 0.2, **_: Any) -> ToolResult:
        pg = _pyautogui()
        pg.moveTo(x, y, duration=max(0.0, min(duration, 3.0)))
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
        pg = _pyautogui()
        if x is not None and y is not None:
            pg.moveTo(x, y)
        pg.scroll(clicks)
        return ToolResult(success=True, output=f"Scrolled {clicks}")


class TypeTextTool(BaseTool):
    name = "type_text"
    description = (
        "Type text with the keyboard into the currently focused window. "
        "Prefer this for normal text; use hotkey for shortcuts."
    )
    parameters = [
        ToolParam(name="text", type="string", description="Text to type."),
        ToolParam(
            name="interval",
            type="number",
            description="Delay between keystrokes in seconds (default 0.02).",
            required=False,
        ),
        ToolParam(
            name="use_clipboard",
            type="boolean",
            description=(
                "If true, paste via clipboard (better for Unicode / long text). Default true."
            ),
            required=False,
        ),
    ]

    async def execute(
        self,
        text: str,
        interval: float = 0.02,
        use_clipboard: bool = True,
        **_: Any,
    ) -> ToolResult:
        pg = _pyautogui()
        if use_clipboard:
            import pyperclip

            old = None
            try:
                old = pyperclip.paste()
            except Exception:
                pass
            pyperclip.copy(text)
            await asyncio.sleep(0.05)
            pg.hotkey("ctrl", "v")
            await asyncio.sleep(0.05)
            if old is not None:
                try:
                    pyperclip.copy(old)
                except Exception:
                    pass
        else:
            pg.write(text, interval=max(0.0, min(interval, 0.2)))
        return ToolResult(
            success=True,
            output=f"Typed {len(text)} characters",
            data={"length": len(text)},
        )


class HotkeyTool(BaseTool):
    name = "hotkey"
    description = (
        "Press a keyboard shortcut, e.g. keys=['ctrl','s'] or keys=['alt','tab']. "
        "Common: ctrl+l (Cursor/VS Code open file), ctrl+shift+p (command palette), "
        "ctrl+k (Cursor chat), ctrl+, (settings)."
    )
    parameters = [
        ToolParam(
            name="keys",
            type="array",
            description="List of keys to press together, e.g. [\"ctrl\", \"shift\", \"p\"].",
            items_type="string",
        ),
    ]

    async def execute(self, keys: list, **_: Any) -> ToolResult:
        if not keys or not isinstance(keys, list):
            return ToolResult(success=False, output="keys must be a non-empty list")
        pg = _pyautogui()
        cleaned = [str(k).lower() for k in keys]
        pg.hotkey(*cleaned)
        return ToolResult(success=True, output=f"Pressed hotkey: {'+'.join(cleaned)}")


class PressKeyTool(BaseTool):
    name = "press_key"
    description = "Press a single key (enter, escape, tab, backspace, delete, up, down, left, right, f1-f12, etc.)."
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
        pg = _pyautogui()
        n = max(1, min(int(times), 20))
        for _ in range(n):
            pg.press(key)
            time.sleep(0.03)
        return ToolResult(success=True, output=f"Pressed '{key}' x{n}")


class GetMousePositionTool(BaseTool):
    name = "get_mouse_position"
    description = "Get the current mouse cursor position and screen size."
    parameters = []

    async def execute(self, **_: Any) -> ToolResult:
        pg = _pyautogui()
        x, y = pg.position()
        w, h = pg.size()
        return ToolResult(
            success=True,
            output=f"Mouse at ({x}, {y}); screen {w}x{h}",
            data={"x": x, "y": y, "screen_width": w, "screen_height": h},
        )


class WaitTool(BaseTool):
    name = "wait"
    description = "Wait/sleep for a number of seconds (UI animations, app launches)."
    parameters = [
        ToolParam(
            name="seconds",
            type="number",
            description="Seconds to wait (max 30).",
        ),
    ]

    async def execute(self, seconds: float = 1.0, **_: Any) -> ToolResult:
        sec = max(0.1, min(float(seconds), 30.0))
        await asyncio.sleep(sec)
        return ToolResult(success=True, output=f"Waited {sec} seconds")
