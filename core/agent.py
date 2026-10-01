"""Agent system prompt and tool-calling loop — human-like desktop operator."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from config.settings import Settings
from core.llm import LLMClient
from core.memory import ConversationMemory
from tools.base import ToolRegistry, ToolResult
from utils.logging import get_logger

log = get_logger("marianaos.agent")

ProgressCallback = Callable[[str], Awaitable[None]]


SYSTEM_PROMPT = """You are {agent_name}, a capable Windows desktop operator helping the user via Telegram.

You control a real unlocked PC. Work like a careful human assistant: understand the goal, look at the UI state, act with the right tools, verify, then report clearly.

## Workspace
Default workspace root: `{workspace}`
Resolve relative paths against this folder unless the user gives an absolute path.

## Tool discovery
{tool_discovery_rules}

## How to operate (human workflow)
1. **Understand** the goal. If ambiguous, make a reasonable assumption and state it briefly.
2. **Observe** before acting when the UI matters:
   - `list_windows` / `get_active_window` / `focus_window`
   - `get_ui_tree` or `find_control` to locate buttons, edits, menus by name
3. **Act** with the most reliable tool:
   - Named UI: `click_control`, `set_control_value`, `invoke_control`
   - Shortcuts: `hotkey`, `press_key`, `type_text`
   - Apps: `open_application`, `open_url`, `open_folder_in_cursor`
   - Files: `list_directory`, `read_file`, `write_file`, `search_files`, …
   - Shell: `run_shell` only when dedicated tools are not enough
4. **Wait** briefly after launches/animations (`wait`) before the next UI step.
5. **Recover** if something fails: re-list windows, re-read UI tree, try an alternate control name or hotkey. Do not spam the same failing call.
6. **Finish** the whole request end-to-end in one turn when possible. Then reply with what you did and the outcome.

## Screenshots (rare)
Do **not** screenshot by default.
Use `take_screenshot` / `analyze_screenshot` only when:
- the user explicitly asks for a screenshot, OR
- UI Automation cannot see the control (canvas / game / custom-drawn UI) and you need vision.
When sending a screenshot back to the user: `take_screenshot(send_to_user=true)`.

## Cursor IDE
Prefer Python/DB tools (no clicking):
- `cursor_get_model`, `cursor_list_models`, `cursor_select_model`, `cursor_set_effort`
- `cursor_list_chats`, `cursor_open_chat_session`
UI only when needed: `cursor_type_in_chat`, `cursor_new_chat`, `cursor_open_chat`, `cursor_command_palette`
Never change models via the command palette.

## Safety
- Destructive tools (`delete_path`, `run_shell`, overwrite writes, …) require `confirm=true` when confirmation mode is on.
- Never invent tool results. Never claim success if a tool failed.
- Do not exfiltrate secrets. Be careful with shell commands.

## Telegram reply style (Rich Markdown)
Telegram renders real Markdown. Format the **final** user reply with:
- `#` / `##` headings for the result
- **bold** for key outcomes, `inline code` for paths/commands
- fenced ```language``` blocks for multi-line code/output
- short bullet lists for steps or results
Keep it mobile-readable. English. No giant dumps — summarize, put details in code fences if needed.
Do not put tool JSON in the final reply.
"""


DISCOVERY_ON = """Only a CORE tool set is loaded each request.
If you need another capability, call `search_tools(query="...")` first — that enables matching tools for this run.
Examples: `search_tools("screenshot")`, `search_tools("clipboard")`, `search_tools("mouse scroll")`, `search_tools("delete file")`.
Use `list_tool_catalog` for a short name list by category."""

DISCOVERY_OFF = """All tools are available in every request. You may still call `search_tools` to browse by keyword."""


@dataclass
class AgentResponse:
    text: str
    media_paths: List[str] = field(default_factory=list)
    tool_trace: List[str] = field(default_factory=list)


class Agent:
    def __init__(
        self,
        settings: Settings,
        llm: LLMClient,
        tools: ToolRegistry,
        memory: Optional[ConversationMemory] = None,
    ) -> None:
        self.settings = settings
        self.llm = llm
        self.tools = tools
        self.memory = memory or ConversationMemory()

    def _system(self) -> Dict[str, Any]:
        return {
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                agent_name=self.settings.agent_name,
                workspace=self.settings.workspace,
                tool_discovery_rules=(
                    DISCOVERY_ON if self.tools.discovery else DISCOVERY_OFF
                ),
            ),
        }

    def _user_reply(self, final_text: str, trace: List[str]) -> str:
        text = (final_text or "").strip() or "Done."
        if not trace:
            return text
        # Compact footer — looks good in rich markdown
        names = []
        for t in trace[-10:]:
            name = t.split(":", 1)[0].strip()
            if name and name not in names:
                names.append(name)
        if not names:
            return text
        footer = "\n\n---\n*Tools:* " + ", ".join(f"`{n}`" for n in names)
        return text + footer

    def _finish(
        self,
        session_id: str,
        final_text: str,
        all_media: List[str],
        trace: List[str],
    ) -> AgentResponse:
        user_text = self._user_reply(final_text, trace)
        # Memory keeps a short action note so follow-ups stay coherent
        mem = user_text
        if trace:
            mem += "\n[actions: " + "; ".join(trace[-12:]) + "]"
        self.memory.add(session_id, {"role": "assistant", "content": mem})

        seen: set[str] = set()
        unique_media: List[str] = []
        for m in all_media:
            if m not in seen and Path(m).exists():
                seen.add(m)
                unique_media.append(m)
        return AgentResponse(text=user_text, media_paths=unique_media, tool_trace=trace)

    def _cancelled(self, cancel_event: Optional[asyncio.Event]) -> bool:
        return bool(cancel_event and cancel_event.is_set())

    async def run(
        self,
        session_id: str,
        user_text: str,
        on_progress: Optional[ProgressCallback] = None,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> AgentResponse:
        self.tools.reset_session()
        self.memory.add(session_id, {"role": "user", "content": user_text})
        messages: List[Dict[str, Any]] = [self._system()] + self.memory.get(session_id)

        all_media: List[str] = []
        trace: List[str] = []
        final_text = ""
        consecutive_fails = 0

        for round_i in range(self.settings.agent_max_tool_rounds):
            if self._cancelled(cancel_event):
                return self._finish(
                    session_id,
                    "## Stopped\n\nTask stopped by you.",
                    all_media,
                    trace,
                )

            log.info(
                "Agent round %s/%s (tools=%s)",
                round_i + 1,
                self.settings.agent_max_tool_rounds,
                len(self.tools.active_names()),
            )
            try:
                turn = await self.llm.complete(
                    messages=messages,
                    tools=self.tools.openai_tools(),
                )
            except asyncio.CancelledError:
                return self._finish(
                    session_id,
                    "## Stopped\n\nTask stopped by you.",
                    all_media,
                    trace,
                )
            except Exception as e:
                log.exception("LLM error")
                return self._finish(
                    session_id,
                    f"## LLM error\n\n`{e}`",
                    all_media,
                    trace,
                )

            if self._cancelled(cancel_event):
                return self._finish(
                    session_id,
                    "## Stopped\n\nTask stopped by you.",
                    all_media,
                    trace,
                )

            messages.append(turn.assistant_message)

            if not turn.tool_calls:
                final_text = (turn.text or "").strip() or "Done."
                break

            for tc in turn.tool_calls:
                if self._cancelled(cancel_event):
                    return self._finish(
                        session_id,
                        "## Stopped\n\nTask stopped by you.",
                        all_media,
                        trace,
                    )

                if on_progress:
                    await on_progress(f"`{tc.name}`…")

                log.info("Tool call: %s(%s)", tc.name, tc.arguments)
                try:
                    result: ToolResult = await self.tools.call(
                        tc.name,
                        tc.arguments,
                        require_confirmation=self.settings.require_confirmation,
                    )
                except asyncio.CancelledError:
                    return self._finish(
                        session_id,
                        "## Stopped\n\nTask stopped by you.",
                        all_media,
                        trace,
                    )
                status = "ok" if result.success else "fail"
                trace.append(f"{tc.name}: {status}")

                if result.success:
                    consecutive_fails = 0
                else:
                    consecutive_fails += 1

                if result.media_paths:
                    all_media.extend(result.media_paths)

                content = result.to_llm()
                if len(content) > 12000:
                    content = content[:12000] + "...[truncated]"

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": content,
                    }
                )

            if consecutive_fails >= 5:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "[System] Several tools failed in a row. "
                            "Stop retrying the same approach. Summarize what failed "
                            "and what the user can do next."
                        ),
                    }
                )
                consecutive_fails = 0
        else:
            done = ", ".join(t.split(":")[0] for t in trace[-8:]) if trace else "none"
            final_text = (
                "## Partial result\n\n"
                f"Reached the max tool rounds. Actions so far: {done or 'none'}.\n"
                "Tell me to continue if you want me to keep going."
            )

        return self._finish(session_id, final_text, all_media, trace)

    async def reset(self, session_id: str) -> None:
        self.memory.clear(session_id)
