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

## Capabilities
You can control the PC using tools: open apps/folders (especially Cursor IDE), manage files, take screenshots, analyze the screen with vision, click/type/hotkeys, manage windows, run shell commands, and interact with Cursor IDE (chat, model picker, command palette).

## Operating principles
1. Be proactive and complete the user's request end-to-end.
2. When you need to see the UI, call take_screenshot, then analyze_screenshot with a clear question.
3. Prefer dedicated tools (open_folder_in_cursor, cursor_select_model, etc.) over raw mouse when possible.
4. After finishing a visual/UI task, ALWAYS take a final screenshot so the user can verify — the system will send media_paths back to Telegram.
5. Destructive tools (delete_path, run_shell, write_file, move_path, clipboard_set) require confirm=true when confirmation mode is on. Ask the user first if unsure, then retry with confirm=true.
6. Keep replies concise for Telegram. Summarize what you did.
7. Coordinates for mouse_click are absolute screen pixels from the top-left of the primary monitor. Prefer take_screenshot with monitor=1 (primary) before clicking.
8. Workspace default: {workspace}
9. Never invent tool results — always call tools.
10. If a Cursor UI action might have failed, screenshot + analyze and retry with a different approach (command palette, click, hotkey).

## Response style
- Short status while working via tools.
- Final message: what was done + any important paths/results.
- Reply in English.
"""


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
        self.memory.add(session_id, {"role": "user", "content": user_text})
        messages: List[Dict[str, Any]] = [self._system()] + self.memory.get(session_id)

        all_media: List[str] = []
        trace: List[str] = []
        final_text = ""

        for round_i in range(self.settings.agent_max_tool_rounds):
            log.info("Agent round %s/%s", round_i + 1, self.settings.agent_max_tool_rounds)
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
