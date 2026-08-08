"""Cursor IDE tools — prefer Python/state.vscdb; UI only when necessary.

Python (no clicking):
  cursor_get_model, cursor_list_models, cursor_select_model, cursor_set_effort,
  cursor_list_chats, cursor_open_chat_session

UI (hotkeys / paste) — only for live interaction:
  cursor_open_chat, cursor_new_chat, cursor_type_in_chat, cursor_add_context,
  cursor_command_palette
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from tools.base import BaseTool, ToolParam, ToolResult


def _pg():
    import pyautogui

    pyautogui.FAILSAFE = True
    return pyautogui


async def _cursor_window():
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


async def _focus_cursor() -> Optional[str]:
    win = await _cursor_window()
    return win.title if win else None


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


async def _reload_cursor() -> str:
    title = await _focus_cursor()
    if not title:
        return "Cursor window not found — open/reload Cursor manually to apply DB changes."
    try:
        await _palette("Developer: Reload Window", submit=True)
        await asyncio.sleep(1.0)
        return "Triggered Developer: Reload Window."
    except Exception as e:
        return f"Reload failed ({e}). Restart Cursor manually."


# ----- Python / DB tools -----


class CursorGetModelTool(BaseTool):
    name = "cursor_get_model"
    category = "cursor"
    always_on = True
    description = (
        "Read the current Cursor Agents/Composer model + effort from state.vscdb (Python)."
    )
    parameters = []

    async def execute(self, **_: Any) -> ToolResult:
        from tools.cursor_state import get_composer_model

        try:
            cur = get_composer_model()
        except Exception as e:
            return ToolResult(success=False, output=str(e))
        return ToolResult(
            success=True,
            output=f"Current model: {cur.display_name} ({cur.model_id}), effort={cur.effort}",
            data={
                "model_id": cur.model_id,
                "display_name": cur.display_name,
                "effort": cur.effort,
                "max_mode": cur.max_mode,
            },
        )


class CursorListModelsTool(BaseTool):
    name = "cursor_list_models"
    category = "cursor"
    always_on = True
    description = (
        "List Cursor models available in the Agents picker (from state.vscdb, Python). "
        "Use before cursor_select_model if unsure of the exact name."
    )
    parameters = [
        ToolParam(
            name="filter",
            type="string",
            description="Optional filter, e.g. 'sonnet' or 'gpt'.",
            required=False,
        ),
    ]

    async def execute(self, filter: Optional[str] = None, **_: Any) -> ToolResult:
        from tools.cursor_state import list_models_brief, resolve_model

        models = list_models_brief()
        q = (filter or "").strip().lower()
        if q:
            models = [
                m
                for m in models
                if q in m["id"].lower()
                or q in m["name"].lower()
                or q in m.get("short", "").lower()
            ]
        lines = [f"{m['name']}  [{m['id']}]" for m in models]
        hint = ""
        if filter and not models:
            try:
                match = resolve_model(filter)
                hint = f"\nClosest resolve: {match.display_name} ({match.model_id})"
            except Exception as e:
                hint = f"\nNo matches ({e})"
        return ToolResult(
            success=True,
            output=("\n".join(lines) if lines else "No models.") + hint,
            data={"models": models, "count": len(models)},
        )


class CursorSelectModelTool(BaseTool):
    name = "cursor_select_model"
    category = "cursor"
    always_on = True
    description = (
        "Set Cursor Agents/Composer model via Python (writes state.vscdb). "
        "No UI clicking. Examples: 'Sonnet 5', 'Grok', 'Composer 2.5', 'Opus 5', 'Auto'."
    )
    parameters = [
        ToolParam(
            name="model",
            type="string",
            description="Model search text, e.g. 'Sonnet 5' or 'Grok'.",
        ),
        ToolParam(
            name="effort",
            type="string",
            description="Optional effort: Low, Medium, High.",
            required=False,
            enum=["Low", "Medium", "High"],
        ),
        ToolParam(
            name="reload",
            type="boolean",
            description="Reload Cursor so UI updates (default true).",
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
            return ToolResult(success=False, output=f"Failed to set model via DB: {e}")

        reload_note = "Reload skipped."
        if reload:
            reload_note = await _reload_cursor()

        try:
            current = get_composer_model()
            verify = (
                f"DB now: {current.display_name} ({current.model_id}), "
                f"effort={current.effort}."
            )
        except Exception:
            verify = "Could not re-read DB."

        return ToolResult(
            success=True,
            output=(
                f"Set model '{result['display_name']}' ({result['model_id']}) "
                f"from '{model}'. {verify} {reload_note}"
            ),
            data=result,
        )


class CursorSetEffortTool(BaseTool):
    name = "cursor_set_effort"
    category = "cursor"
    description = (
        "Set Cursor Agent effort (Low/Medium/High) via Python state.vscdb."
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
            description="Reload Cursor after writing (default true).",
            required=False,
        ),
    ]

    async def execute(self, effort: str, reload: bool = True, **_: Any) -> ToolResult:
        from tools.cursor_state import set_composer_effort

        try:
            result = set_composer_effort(effort)
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to set effort: {e}")

        reload_note = "Reload skipped."
        if reload:
            reload_note = await _reload_cursor()

        return ToolResult(
            success=True,
            output=(
                f"Set effort '{result['effort']}' for {result['model_id']}. {reload_note}"
            ),
            data=result,
        )


class CursorListChatsTool(BaseTool):
    name = "cursor_list_chats"
    category = "cursor"
    always_on = True
    description = (
        "List recent Cursor Agent/Composer chats via Python (composer.composerHeaders). "
        "Returns composer_id — use cursor_open_chat_session to open one."
    )
    parameters = [
        ToolParam(
            name="filter",
            type="string",
            description="Optional title/subtitle keywords.",
            required=False,
        ),
        ToolParam(
            name="limit",
            type="integer",
            description="Max chats (default 20).",
            required=False,
        ),
    ]

    async def execute(
        self,
        filter: Optional[str] = None,
        limit: int = 20,
        **_: Any,
    ) -> ToolResult:
        from tools.cursor_state import list_chats

        try:
            chats = list_chats(filter, limit=int(limit or 20))
        except Exception as e:
            return ToolResult(success=False, output=str(e))

        lines = []
        for c in chats:
            lines.append(
                f"- {c['name']} | id={c['composer_id']} | "
                f"{c.get('workspace_path') or c.get('workspace_id')}"
            )
        return ToolResult(
            success=True,
            output="\n".join(lines) if lines else "No chats found.",
            data={"chats": chats, "count": len(chats)},
        )


class CursorOpenChatSessionTool(BaseTool):
    name = "cursor_open_chat_session"
    category = "cursor"
    always_on = True
    description = (
        "Open a past Cursor chat by composer_id (Python writes workspace state.vscdb). "
        "Get ids from cursor_list_chats. Reloads Cursor by default."
    )
    parameters = [
        ToolParam(
            name="composer_id",
            type="string",
            description="Chat id from cursor_list_chats.",
        ),
        ToolParam(
            name="reload",
            type="boolean",
            description="Reload Cursor after writing (default true).",
            required=False,
        ),
    ]

    async def execute(
        self,
        composer_id: str,
        reload: bool = True,
        **_: Any,
    ) -> ToolResult:
        from tools.cursor_state import open_chat_session

        try:
            result = open_chat_session(composer_id)
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to open chat: {e}")

        reload_note = "Reload skipped."
        if reload:
            reload_note = await _reload_cursor()

        return ToolResult(
            success=True,
            output=(
                f"Opened chat '{result.get('name')}' ({result['composer_id']}) "
                f"in workspace {result.get('workspace_path')}. {reload_note}"
            ),
            data=result,
        )


# ----- UI tools (fallback / live interaction) -----


class CursorCommandPaletteTool(BaseTool):
    name = "cursor_command_palette"
    category = "cursor"
    description = (
        "UI: Open Cursor command palette (Ctrl+Shift+P) and optionally run a command. "
        "Do NOT use for model select — use cursor_select_model instead."
    )
    parameters = [
        ToolParam(
            name="command",
            type="string",
            description="Command text to run.",
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
    category = "cursor"
    description = (
        "UI: Focus Cursor Agents/Chat panel (Ctrl+L). "
        "For opening a past chat by id, prefer cursor_open_chat_session."
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
            pg.hotkey("ctrl", "l")
        await asyncio.sleep(0.45)
        return ToolResult(
            success=True,
            output=f"Focused Cursor {mode} panel on '{title}'.",
            data={"window": title, "mode": mode},
        )


class CursorNewChatTool(BaseTool):
    name = "cursor_new_chat"
    category = "cursor"
    description = "UI: Start a new Agent/Chat in Cursor (hotkey + palette)."
    parameters = []

    async def execute(self, **_: Any) -> ToolResult:
        title = await _focus_cursor()
        if not title:
            return ToolResult(success=False, output="Cursor window not found.")
        pg = _pg()
        pg.hotkey("ctrl", "l")
        await asyncio.sleep(0.3)
        await _palette("Chat: New Chat", submit=True)
        await asyncio.sleep(0.25)
        await _palette("New Agent", submit=True)
        return ToolResult(
            success=True,
            output="Attempted new Cursor Agent/Chat.",
            data={"window": title},
        )


class CursorTypeInChatTool(BaseTool):
    name = "cursor_type_in_chat"
    category = "cursor"
    description = (
        "UI: Paste a prompt into Cursor Agent/Chat input and optionally send Enter."
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
    category = "cursor"
    description = "UI: Type @query in Cursor chat to attach file/folder context."
    parameters = [
        ToolParam(
            name="query",
            type="string",
            description="Text after @: e.g. 'main.py'.",
        ),
        ToolParam(
            name="confirm",
            type="boolean",
            description="Press Enter on first match. Default true.",
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
            output=f"Inserted @{query} in Cursor chat.",
            data={"query": query, "window": title},
        )


# Back-compat aliases used by older prompts / imports
class CursorOpenHistoryTool(CursorListChatsTool):
    name = "cursor_open_history"
    always_on = False
    description = (
        "Alias of cursor_list_chats (Python). Lists chats — then use "
        "cursor_open_chat_session(composer_id=...)."
    )


class CursorImportChatTool(BaseTool):
    name = "cursor_import_chat"
    category = "cursor"
    description = (
        "Find a past chat by filter (Python list) and open the best match via DB. "
        "Prefer cursor_list_chats + cursor_open_chat_session for more control."
    )
    parameters = [
        ToolParam(
            name="filter",
            type="string",
            description="Title keywords to find the chat.",
        ),
        ToolParam(
            name="reload",
            type="boolean",
            description="Reload Cursor after opening (default true).",
            required=False,
        ),
    ]

    async def execute(
        self,
        filter: str,
        reload: bool = True,
        **_: Any,
    ) -> ToolResult:
        from tools.cursor_state import list_chats, open_chat_session

        chats = list_chats(filter, limit=5)
        if not chats:
            return ToolResult(success=False, output=f"No chats matched '{filter}'.")
        best = chats[0]
        try:
            result = open_chat_session(best["composer_id"])
        except Exception as e:
            return ToolResult(success=False, output=str(e))
        reload_note = await _reload_cursor() if reload else "Reload skipped."
        return ToolResult(
            success=True,
            output=(
                f"Opened best match '{best['name']}' ({best['composer_id']}). "
                f"{reload_note}"
            ),
            data={"match": best, "open": result},
        )
