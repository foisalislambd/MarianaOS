"""Cursor IDE / Agents panel automation helpers.

UI map (Agents Window on the right):
- Bottom bar: mode button (Agent) + settings chip (shows Effort e.g. Medium / model name)
- Settings menu: Effort (Low/Medium/High), Fast toggle, Model submenu
- Model list: Auto, Cursor Grok 4.5, Composer 2.5, Opus 5, Sonnet 5, Gemini, …
- Top: New Agent (+), history (clock), more (…)
- Input: type prompt; @ = context; / = skills; paperclip = attach
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from tools.base import BaseTool, ToolParam, ToolResult


def _pg():
    import pyautogui

    pyautogui.FAILSAFE = True
    return pyautogui


async def _focus_cursor() -> Optional[str]:
    win = await _cursor_window()
    return win.title if win else None


async def _cursor_window():
    """Focus Cursor and return the pygetwindow Window object."""
    import pygetwindow as gw

    matches = [
        w for w in gw.getAllWindows() if w.title and "cursor" in w.title.lower()
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
            import win32con
            import win32gui

            hwnd = win32gui.FindWindow(None, win.title)
            if hwnd:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
        except Exception:
            return None
    await asyncio.sleep(0.35)
    return win


async def _open_agents_panel() -> None:
    """Bring up the right-side Agents / Chat panel (not command palette)."""
    pg = _pg()
    pg.hotkey("ctrl", "l")
    await asyncio.sleep(0.55)


def _agents_bottom_bar_points(win) -> dict:
    """
    Approximate click points inside Cursor's right Agents panel bottom bar.

    Layout (from Cursor Agents UI):
      [ Agent ]  [ Medium / model chip ]
    The Agents panel sits on the right ~28-40% of the window.
    """
    left, top, w, h = win.left, win.top, win.width, win.height
    # Right panel horizontal band
    panel_left = left + int(w * 0.62)
    panel_right = left + w - 16
    panel_mid_x = (panel_left + panel_right) // 2
    # Bottom bar just above the window edge / status
    bar_y = top + int(h * 0.935)
    return {
        "agent_mode": (panel_left + 70, bar_y),
        # Settings chip that opens Effort + Model menu (shows "Medium" etc.)
        "settings_chip": (panel_mid_x + 40, bar_y),
        # Slightly right — often closer to the model name on the chip
        "settings_chip_alt": (min(panel_right - 80, panel_mid_x + 120), bar_y),
        # After menu opens: Model row is below Effort / Fast in the popup
        "model_row": (panel_mid_x + 40, bar_y - 95),
        "effort_low": (panel_mid_x + 20, bar_y - 160),
        "effort_medium": (panel_mid_x + 20, bar_y - 135),
        "effort_high": (panel_mid_x + 20, bar_y - 110),
        "search_box": (panel_mid_x + 160, bar_y - 200),
    }


async def _click_xy(x: int, y: int, clicks: int = 1) -> None:
    pg = _pg()
    pg.click(x=int(x), y=int(y), clicks=clicks)
    await asyncio.sleep(0.35)


async def _open_model_picker(win) -> dict:
    """
    Open the Agents bottom settings menu, then the Model submenu.
    Does NOT use the command palette — models are only in this UI.
    """
    pts = _agents_bottom_bar_points(win)
    # 1) Click settings chip (Medium / current model)
    await _click_xy(*pts["settings_chip"])
    await asyncio.sleep(0.25)
    # 2) Click Model row to open the model list + search
    await _click_xy(*pts["model_row"])
    await asyncio.sleep(0.4)
    return pts


async def _paste(text: str) -> None:
    import pyperclip

    pg = _pg()
    pyperclip.copy(text)
    await asyncio.sleep(0.05)
    pg.hotkey("ctrl", "v")
    await asyncio.sleep(0.15)


async def _palette(command: str, submit: bool = True) -> None:
    pg = _pg()
    pg.hotkey("ctrl", "shift", "p")
    await asyncio.sleep(0.45)
    pg.hotkey("ctrl", "a")
    await asyncio.sleep(0.05)
    await _paste(command)
    await asyncio.sleep(0.35)
    if submit:
        pg.press("enter")
        await asyncio.sleep(0.4)


class CursorCommandPaletteTool(BaseTool):
    name = "cursor_command_palette"
    description = (
        "Open Cursor command palette (Ctrl+Shift+P), optionally type a command and Enter. "
        "Useful commands: 'View: Toggle Primary Side Bar', 'Chat: New Chat', "
        "'Cursor: Open Chat', settings, etc."
    )
    parameters = [
        ToolParam(
            name="command",
            type="string",
            description="Command text to run in the palette.",
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
            return ToolResult(success=False, output="Cursor window not found.")
        if command:
            await _palette(command, submit=submit)
            return ToolResult(
                success=True,
                output=f"Ran command palette: {command}",
                data={"window": title, "command": command},
            )
        pg = _pg()
        pg.hotkey("ctrl", "shift", "p")
        await asyncio.sleep(0.3)
        return ToolResult(success=True, output=f"Opened command palette on '{title}'")


class CursorOpenChatTool(BaseTool):
    name = "cursor_open_chat"
    description = (
        "Open Cursor Agents / Chat panel on the right. "
        "mode=agent opens Agent panel (preferred for model select / chat). "
        "mode=chat uses Ctrl+L; mode=composer uses Ctrl+I."
    )
    parameters = [
        ToolParam(
            name="mode",
            type="string",
            description="agent (default), chat, or composer.",
            required=False,
            enum=["agent", "chat", "composer"],
        ),
    ]

    async def execute(self, mode: str = "agent", **_: Any) -> ToolResult:
        title = await _focus_cursor()
        if not title:
            return ToolResult(success=False, output="Cursor window not found.")
        pg = _pg()
        pg.press("escape")
        await asyncio.sleep(0.1)
        if mode == "composer":
            pg.hotkey("ctrl", "i")
        else:
            # Agents / Chat panel on the right (Ctrl+L). No command palette.
            pg.hotkey("ctrl", "l")
        await asyncio.sleep(0.45)
        return ToolResult(
            success=True,
            output=f"Opened Cursor {mode} panel on '{title}'. Take a screenshot to confirm.",
            data={"window": title, "mode": mode},
        )


class CursorNewChatTool(BaseTool):
    name = "cursor_new_chat"
    description = (
        "Start a new Agent/Chat tab in Cursor (like clicking + / New Agent)."
    )
    parameters = []

    async def execute(self, **_: Any) -> ToolResult:
        title = await _focus_cursor()
        if not title:
            return ToolResult(success=False, output="Cursor window not found.")
        # Try dedicated new-chat shortcuts, then palette
        pg = _pg()
        pg.hotkey("ctrl", "n")
        await asyncio.sleep(0.25)
        await _palette("Chat: New Chat", submit=True)
        await asyncio.sleep(0.3)
        await _palette("New Agent", submit=True)
        return ToolResult(
            success=True,
            output="Attempted to open a new Cursor Agent/Chat. Screenshot to verify.",
            data={"window": title},
        )


class CursorOpenHistoryTool(BaseTool):
    name = "cursor_open_history"
    description = (
        "Open Cursor chat/agent history (clock icon). "
        "Then use screenshot + mouse_click to pick a past chat, or type to filter."
    )
    parameters = []

    async def execute(self, **_: Any) -> ToolResult:
        title = await _focus_cursor()
        if not title:
            return ToolResult(success=False, output="Cursor window not found.")
        await _palette("Chat: Show History", submit=True)
        await asyncio.sleep(0.25)
        await _palette("Show Chat History", submit=True)
        return ToolResult(
            success=True,
            output=(
                "Opened chat history (or attempted). "
                "take_screenshot + analyze_screenshot, then mouse_click the chat to open/import."
            ),
            data={"window": title},
        )


class CursorSelectModelTool(BaseTool):
    name = "cursor_select_model"
    description = (
        "Set Cursor Agents/Composer model via Python by writing Cursor's state.vscdb "
        "(no command palette, no UI clicking). "
        "Examples: 'Sonnet 5', 'Grok', 'Composer 2.5', 'Opus 5', 'Gemini 3.1 Pro', 'Auto'. "
        "Optionally reload Cursor so the UI picks it up immediately."
    )
    parameters = [
        ToolParam(
            name="model",
            type="string",
            description="Model search text (partial name OK), e.g. 'Sonnet 5' or 'Grok'.",
        ),
        ToolParam(
            name="effort",
            type="string",
            description="Optional effort: Low, Medium, High (if the model supports it).",
            required=False,
            enum=["Low", "Medium", "High"],
        ),
        ToolParam(
            name="reload",
            type="boolean",
            description="Reload Cursor window after writing so UI updates (default true).",
            required=False,
        ),
    ]

    async def execute(
        self,
        model: str,
        effort: Optional[str] = None,
        reload: bool = True,
        **_: Any,
    ) -> ToolResult:
        from tools.cursor_state import get_composer_model, set_composer_model

        try:
            result = set_composer_model(model, effort=effort)
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to set Cursor model via DB: {e}")

        reload_note = "Reload skipped."
        if reload:
            title = await _focus_cursor()
            if title:
                try:
                    await _palette("Developer: Reload Window", submit=True)
                    reload_note = "Triggered Developer: Reload Window so Cursor applies the change."
                    await asyncio.sleep(1.0)
                except Exception as e:
                    reload_note = f"Wrote DB but reload failed ({e}). Restart Cursor or reload manually."
            else:
                reload_note = "Wrote DB; Cursor window not found to reload — open Cursor to see it."

        try:
            current = get_composer_model()
            verify = f"DB now reports model={current.display_name} ({current.model_id}), effort={current.effort}."
        except Exception:
            verify = "Could not re-read DB for verification."

        return ToolResult(
            success=True,
            output=(
                f"Set Cursor model via Python/state.vscdb: '{result['display_name']}' "
                f"({result['model_id']}) from query '{model}'. {verify} {reload_note}"
            ),
            data=result,
        )


class CursorSetEffortTool(BaseTool):
    name = "cursor_set_effort"
    description = (
        "Set Cursor Agent effort (Low / Medium / High) by writing Cursor state.vscdb in Python. "
        "No UI clicking / command palette."
    )
    parameters = [
        ToolParam(
            name="effort",
            type="string",
            description="Effort level.",
            enum=["Low", "Medium", "High"],
        ),
        ToolParam(
            name="reload",
            type="boolean",
            description="Reload Cursor window after writing (default true).",
            required=False,
        ),
    ]

    async def execute(self, effort: str, reload: bool = True, **_: Any) -> ToolResult:
        from tools.cursor_state import set_composer_effort

        try:
            result = set_composer_effort(effort)
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to set effort via DB: {e}")

        reload_note = "Reload skipped."
        if reload:
            title = await _focus_cursor()
            if title:
                try:
                    await _palette("Developer: Reload Window", submit=True)
                    reload_note = "Triggered Developer: Reload Window."
                    await asyncio.sleep(1.0)
                except Exception as e:
                    reload_note = f"Wrote DB but reload failed ({e})."
            else:
                reload_note = "Wrote DB; Cursor not open to reload."

        return ToolResult(
            success=True,
            output=(
                f"Set Cursor effort to '{result['effort']}' for model {result['model_id']} "
                f"via Python/state.vscdb. {reload_note}"
            ),
            data=result,
        )


class CursorTypeInChatTool(BaseTool):
    name = "cursor_type_in_chat"
    description = (
        "Type (paste) a prompt into Cursor Agent/Chat input and optionally send. "
        "Use mode=agent for the right-side Agents panel."
    )
    parameters = [
        ToolParam(name="text", type="string", description="Prompt text to send."),
        ToolParam(
            name="mode",
            type="string",
            description="agent, chat, or composer. Default agent.",
            required=False,
            enum=["agent", "chat", "composer"],
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
        mode: str = "agent",
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
        await _paste(text)
        await asyncio.sleep(0.2)
        if submit:
            pg.press("enter")
        return ToolResult(
            success=True,
            output=f"Typed into Cursor {mode}" + (" and submitted" if submit else ""),
            data={"mode": mode, "length": len(text)},
        )


class CursorAddContextTool(BaseTool):
    name = "cursor_add_context"
    description = (
        "Add @-context in Cursor chat (files/folders/docs). "
        "Types @ then the query so the user/agent can pick from the picker."
    )
    parameters = [
        ToolParam(
            name="query",
            type="string",
            description="Text after @: e.g. 'main.py' or 'README' or folder name.",
        ),
        ToolParam(
            name="confirm",
            type="boolean",
            description="Press Enter to confirm first match. Default true.",
            required=False,
        ),
    ]

    async def execute(self, query: str, confirm: bool = True, **_: Any) -> ToolResult:
        title = await _focus_cursor()
        if not title:
            return ToolResult(success=False, output="Cursor window not found.")
        pg = _pg()
        pg.hotkey("ctrl", "l")
        await asyncio.sleep(0.4)
        await _paste("@" + query)
        await asyncio.sleep(0.45)
        if confirm:
            pg.press("enter")
            await asyncio.sleep(0.25)
        return ToolResult(
            success=True,
            output=f"Inserted @{query} context picker in Cursor chat.",
            data={"query": query, "window": title},
        )


class CursorImportChatTool(BaseTool):
    name = "cursor_import_chat"
    description = (
        "Open/import a previous Cursor chat from history. "
        "Opens history, optionally types a filter, then you should screenshot "
        "and mouse_click the matching chat. If filter is empty, just opens history."
    )
    parameters = [
        ToolParam(
            name="filter",
            type="string",
            description="Optional text to filter history (chat title keywords).",
            required=False,
        ),
    ]

    async def execute(self, filter: Optional[str] = None, **_: Any) -> ToolResult:
        title = await _focus_cursor()
        if not title:
            return ToolResult(success=False, output="Cursor window not found.")
        pg = _pg()
        pg.hotkey("ctrl", "l")
        await asyncio.sleep(0.35)
        await _palette("Chat: Show History", submit=True)
        await asyncio.sleep(0.35)
        await _palette("Show Chat History", submit=True)
        await asyncio.sleep(0.4)
        if filter:
            await _paste(filter)
            await asyncio.sleep(0.4)
        return ToolResult(
            success=True,
            output=(
                "Opened Cursor chat history"
                + (f" and filtered by '{filter}'" if filter else "")
                + ". NEXT: take_screenshot, analyze_screenshot to find the chat row, "
                "then mouse_click it to open/import that chat."
            ),
            data={"filter": filter, "window": title},
        )
