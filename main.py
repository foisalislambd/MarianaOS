"""MROS — Multi-channel Remote OS Agent entrypoint."""

from __future__ import annotations

import asyncio
import signal
import sys
from pathlib import Path

# Ensure project root on sys.path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from channels.base import InboundMessage, OutboundMessage
from channels.telegram_channel import TelegramChannel
from config.settings import Settings, get_settings, list_providers, reload_settings
from core.agent import Agent
from core.llm import LLMClient
from core.memory import ConversationMemory
from tools import build_registry
from utils.logging import console, get_logger, setup_logging


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    log = get_logger("mros")
    llm_cfg = settings.llm

    console.print(f"[bold cyan]{settings.agent_name}[/] — Desktop AI Agent")
    console.print(f"Workspace: [green]{settings.workspace}[/]")
    console.print(
        f"Provider: [magenta]{llm_cfg.provider_name}[/] ({llm_cfg.provider_id})"
    )
    console.print(f"Model: [yellow]{llm_cfg.model}[/]")
    console.print(f"Vision: [yellow]{llm_cfg.vision_model}[/]")
    console.print(f"API: [dim]{llm_cfg.base_url}[/]")
    if llm_cfg.notes:
        console.print(f"[dim]{llm_cfg.notes}[/]")
    console.print(
        f"Allowed Telegram users: "
        f"{settings.allowed_user_ids or '[NONE — set TELEGRAM_ALLOWED_USERS!]'}"
    )

    llm = LLMClient.from_resolved(
        llm_cfg,
        max_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
    )
    tools = build_registry(settings, llm)
    memory = ConversationMemory(max_messages=40)
    agent = Agent(settings, llm, tools, memory)

    console.print(f"Registered [bold]{len(tools.list())}[/] tools")

    channel = TelegramChannel(
        token=settings.telegram_bot_token,
        allowed_user_ids=settings.allowed_user_ids,
    )

    async def handle(msg: InboundMessage) -> OutboundMessage:
        if msg.text == "__RESET__":
            await agent.reset(msg.session_id)
            return OutboundMessage(text="")

        on_progress = None
        if isinstance(msg.raw, dict):
            on_progress = msg.raw.get("on_progress")

        result = await agent.run(
            session_id=msg.session_id,
            user_text=msg.text,
            on_progress=on_progress,
        )

        # Prefer sending only the last few screenshots to avoid spam
        media = result.media_paths[-3:] if result.media_paths else []
        footer = ""
        if result.tool_trace:
            footer = "\n\ntools: " + ", ".join(result.tool_trace[-8:])
        return OutboundMessage(
            text=(result.text + footer).strip(),
            media_paths=media,
            parse_mode=None,
        )

    channel.on_message(handle)
    await channel.start()

    stop_event = asyncio.Event()

    def _ask_stop(*_: object) -> None:
        stop_event.set()

    # Unix: asyncio signal handlers. Windows: rely on KeyboardInterrupt below.
    if sys.platform != "win32":
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, _ask_stop)
        except (NotImplementedError, RuntimeError):
            pass

    console.print("[bold green]Agent running. Press Ctrl+C to stop.[/]")
    try:
        if sys.platform == "win32":
            # Windows: polling wait so KeyboardInterrupt is delivered reliably
            while not stop_event.is_set():
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
        else:
            await stop_event.wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        await channel.stop()
        console.print("[dim]Shutdown complete.[/]")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
