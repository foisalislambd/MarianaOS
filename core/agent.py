"""Agent system prompt and tool-calling loop."""

from __future__ import annotations

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


SYSTEM_PROMPT = """You are {agent_name}, a powerful desktop AI agent controlling a Windows PC for the user via Telegram (and later other channels).

## Tool discovery (token saver)
{tool_discovery_rules}

## Cursor — prefer Python tools (no UI clicking)
- cursor_get_model / cursor_list_models / cursor_select_model / cursor_set_effort → state.vscdb
- cursor_list_chats / cursor_open_chat_session / cursor_import_chat → Python chat headers + workspace DB
- UI-only when needed: cursor_type_in_chat, cursor_add_context, cursor_new_chat, cursor_open_chat, cursor_command_palette
- NEVER use command palette or mouse to change models.

## Operating principles
1. Complete the user's request end-to-end.
2. Need the screen? take_screenshot then analyze_screenshot.
3. Prefer dedicated tools over raw mouse/hotkey.
4. After visual/UI tasks, take a final screenshot (media goes to Telegram).
5. Destructive tools need confirm=true when confirmation mode is on.
6. Keep Telegram replies concise. English.
7. mouse_click uses absolute primary-monitor pixels.
8. Workspace default: {workspace}
9. Never invent tool results.

## Response formatting (Telegram Rich Messages)
Format final replies with Markdown:
- `#` / `##` headings for sections
- **bold** for key results, `inline code` for paths/commands
- fenced ```language``` code blocks when showing code
- `-` bullet lists for steps/results
Keep it mobile-readable; avoid huge tables.
"""


DISCOVERY_ON = """Only a CORE tool set is loaded in each request.
If you need another capability, call search_tools(query="...") first — that enables matching tools for this run.
Examples: search_tools("mouse click"), search_tools("clipboard"), search_tools("cursor type chat").
Use list_tool_catalog for a short name list by category."""

DISCOVERY_OFF = """All tools are available in every request. You may still call search_tools to browse by keyword."""


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

    def _finish(
        self,
        session_id: str,
        final_text: str,
        all_media: List[str],
        trace: List[str],
    ) -> AgentResponse:
        self.memory.add(session_id, {"role": "assistant", "content": final_text})
        seen: set[str] = set()
        unique_media: List[str] = []
        for m in all_media:
            if m not in seen and Path(m).exists():
                seen.add(m)
                unique_media.append(m)
        return AgentResponse(text=final_text, media_paths=unique_media, tool_trace=trace)

    async def run(
        self,
        session_id: str,
        user_text: str,
        on_progress: Optional[ProgressCallback] = None,
    ) -> AgentResponse:
        self.tools.reset_session()
        self.memory.add(session_id, {"role": "user", "content": user_text})
        messages: List[Dict[str, Any]] = [self._system()] + self.memory.get(session_id)

        all_media: List[str] = []
        trace: List[str] = []
        final_text = ""

        for round_i in range(self.settings.agent_max_tool_rounds):
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
            except Exception as e:
                log.exception("LLM error")
                return self._finish(
                    session_id,
                    f"LLM error: {e}",
                    all_media,
                    trace,
                )

            messages.append(turn.assistant_message)

            if not turn.tool_calls:
                final_text = (turn.text or "").strip() or "Done."
                break

            for tc in turn.tool_calls:
                if on_progress:
                    await on_progress(f"🔧 {tc.name}…")

                log.info("Tool call: %s(%s)", tc.name, tc.arguments)
                result: ToolResult = await self.tools.call(
                    tc.name,
                    tc.arguments,
                    require_confirmation=self.settings.require_confirmation,
                )
                trace.append(f"{tc.name}: {'ok' if result.success else 'fail'}")

                if result.media_paths:
                    all_media.extend(result.media_paths)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": result.to_llm(),
                    }
                )
        else:
            final_text = (
                "Reached max tool rounds. Partial work may be done — check screenshots."
            )

        return self._finish(session_id, final_text, all_media, trace)

    async def reset(self, session_id: str) -> None:
        self.memory.clear(session_id)
