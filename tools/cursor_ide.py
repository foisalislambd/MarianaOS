"""Cursor IDE specific automation helpers."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from tools.base import BaseTool, ToolParam, ToolResult


def _pg():
    import pyautogui

    pyautogui.FAILSAFE = True
    return pyautogui


async def _focus_cursor() -> Optional[str]:
    import pygetwindow as gw

    matches = [
        w
        for w in gw.getAllWindows()
        if w.title and "cursor" in w.title.lower()
    ]
    if not matches:
        return None
    win = matches[0]
    try:
        if win.isMinimized:
            win.restore()
        win.activate()
    except Exception:
        try:
            import win32gui
            import win32con

            hwnd = win32gui.FindWindow(None, win.title)
            if hwnd:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
        except Exception:
            return None
    await asyncio.sleep(0.35)
    return win.title


class CursorCommandPaletteTool(BaseTool):
    name = "cursor_command_palette"
    description = (
        "Open Cursor's command palette (Ctrl+Shift+P), optionally type a command "
        "and press Enter. Use for switching models, opening settings, running commands."
    )
    parameters = [
        ToolParam(
            name="command",
            type="string",
            description=(
                "Optional command text to type into the palette "
                "(e.g. 'Preferences: Open Settings', 'Cursor: Open Chat')."
            ),
            required=False,
        ),
        ToolParam(
            name="submit",
            type="boolean",
            description="Press Enter after typing. Default true.",
            required=False,
        ),
    ]

    async def execute(
        self, command: Optional[str] = None, submit: bool = True, **_: Any
    ) -> ToolResult:
        title = await _focus_cursor()
        if not title:
            return ToolResult(
                success=False,
                output="Cursor window not found. Open Cursor first (open_folder_in_cursor / open_application).",
            )
        pg = _pg()
        pg.hotkey("ctrl", "shift", "p")
        await asyncio.sleep(0.4)
        if command:
            import pyperclip

            pyperclip.copy(command)
            pg.hotkey("ctrl", "v")
            await asyncio.sleep(0.35)
            if submit:
                pg.press("enter")
                await asyncio.sleep(0.3)
        return ToolResult(
            success=True,
            output=(
                f"Opened command palette on '{title}'"
                + (f" and ran: {command}" if command else "")
            ),
            data={"window": title, "command": command},
        )


class CursorOpenChatTool(BaseTool):
    name = "cursor_open_chat"
    description = (
        "Open Cursor AI Chat / Agent panel. Uses Ctrl+L (Chat) or Ctrl+I (Composer/Agent) "
        "depending on mode."
    )
    parameters = [
        ToolParam(
            name="mode",
            type="string",
            description="chat (Ctrl+L) or composer (Ctrl+I). Default chat.",
            required=False,
            enum=["chat", "composer"],
        ),
    ]

    async def execute(self, mode: str = "chat", **_: Any) -> ToolResult:
        title = await _focus_cursor()
        if not title:
            return ToolResult(success=False, output="Cursor window not found.")
        pg = _pg()
        if mode == "composer":
            pg.hotkey("ctrl", "i")
        else:
            pg.hotkey("ctrl", "l")
        await asyncio.sleep(0.4)
        return ToolResult(
            success=True,
            output=f"Opened Cursor {mode} panel on '{title}'",
            data={"window": title, "mode": mode},
        )


class CursorSelectModelTool(BaseTool):
    name = "cursor_select_model"
    description = (
        "Try to select / switch the AI model inside Cursor. "
        "Opens the model picker via UI automation, types the model name, and confirms. "
        "Always take a screenshot afterwards to verify. "
        "model examples: 'claude-sonnet', 'gpt-4o', 'claude-opus', 'gemini', 'composer'."
    )
    parameters = [
        ToolParam(
            name="model",
            type="string",
            description="Model name / search text to select in Cursor's model picker.",
        ),
    ]

    async def execute(self, model: str, **_: Any) -> ToolResult:
        title = await _focus_cursor()
        if not title:
            return ToolResult(success=False, output="Cursor window not found.")

        pg = _pg()
        # Open chat first so model picker is available
        pg.hotkey("ctrl", "l")
        await asyncio.sleep(0.5)

        # Common Cursor UX: model dropdown near chat input.
        # Try command palette approach which is more stable across versions.
        pg.hotkey("ctrl", "shift", "p")
        await asyncio.sleep(0.4)
        import pyperclip

        pyperclip.copy("Cursor: Open Model Toggle")
        pg.hotkey("ctrl", "a")
        await asyncio.sleep(0.05)
        pg.hotkey("ctrl", "v")
        await asyncio.sleep(0.35)
        pg.press("enter")
        await asyncio.sleep(0.6)

        # Fallback / also try typing model directly if a picker is open
        pyperclip.copy(model)
        pg.hotkey("ctrl", "a")
        await asyncio.sleep(0.05)
        pg.hotkey("ctrl", "v")
        await asyncio.sleep(0.4)
        pg.press("enter")
        await asyncio.sleep(0.3)

        return ToolResult(
            success=True,
            output=(
                f"Attempted to select model '{model}' in Cursor. "
                "Take a screenshot now to verify the selection, and retry with "
                "mouse_click if the picker UI differs."
            ),
            data={"model": model, "window": title},
        )


class CursorTypeInChatTool(BaseTool):
    name = "cursor_type_in_chat"
    description = (
        "Focus Cursor chat/composer and type (paste) a prompt. "
        "Optionally submit with Enter."
    )
    parameters = [
        ToolParam(name="text", type="string", description="Prompt text to send to Cursor AI."),
        ToolParam(
            name="mode",
            type="string",
            description="chat or composer. Default chat.",
            required=False,
            enum=["chat", "composer"],
        ),
        ToolParam(
            name="submit",
            type="boolean",
            description="Press Enter to send. Default true.",
            required=False,
        ),
    ]

    async def execute(
        self,
        text: str,
        mode: str = "chat",
        submit: bool = True,
        **_: Any,
    ) -> ToolResult:
        title = await _focus_cursor()
        if not title:
            return ToolResult(success=False, output="Cursor window not found.")
        pg = _pg()
        if mode == "composer":
            pg.hotkey("ctrl", "i")
        else:
            pg.hotkey("ctrl", "l")
        await asyncio.sleep(0.45)
        import pyperclip

        pyperclip.copy(text)
        pg.hotkey("ctrl", "v")
        await asyncio.sleep(0.2)
        if submit:
            pg.press("enter")
        return ToolResult(
            success=True,
            output=f"Typed into Cursor {mode}" + (" and submitted" if submit else ""),
            data={"mode": mode, "length": len(text)},
        )
