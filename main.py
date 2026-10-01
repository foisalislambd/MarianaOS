"""MarianaOS — Multi-channel Remote OS Agent entrypoint."""

from __future__ import annotations

import asyncio
import signal
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from channels.base import InboundMessage, OutboundMessage
from channels.telegram_channel import TelegramChannel
from config.settings import get_settings
from core.agent import Agent
from core.llm import LLMClient
from core.memory import ConversationMemory
from tools import build_registry
from utils.logging import get_logger, setup_logging


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    log = get_logger("marianaos")
    llm_cfg = settings.llm

    print(f"{settings.agent_name} — Desktop AI Agent")
    print(f"Workspace: {settings.workspace}")
    print(f"Provider: {llm_cfg.provider_name} ({llm_cfg.provider_id})")
    print(f"Model: {llm_cfg.model}")
    print(f"Vision: {llm_cfg.vision_model}")
    print(f"API: {llm_cfg.base_url}")
    if llm_cfg.notes:
        print(llm_cfg.notes)
    print(
        "Allowed Telegram users: "
        f"{settings.allowed_user_ids or '[NONE — set TELEGRAM_ALLOWED_USERS!]'}"
    )

    if not llm_cfg.api_key and llm_cfg.provider_id not in {"ollama", "lmstudio"}:
        print("WARNING: LLM_API_KEY is empty. Set it in .env (OpenRouter recommended).")

    llm = LLMClient.from_resolved(
        llm_cfg,
        max_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
    )
    tools = build_registry(settings, llm)
    memory = ConversationMemory(max_messages=40)
    agent = Agent(settings, llm, tools, memory)

    print(f"Registered {len(tools.list())} tools")
    print(f"Core tools active: {len(tools.active_names())}")

    channel = TelegramChannel(
        token=settings.telegram_bot_token,
        allowed_user_ids=settings.allowed_user_ids,
    )

    async def handle(msg: InboundMessage) -> OutboundMessage:
        if msg.text == "__RESET__":
            await agent.reset(msg.session_id)
            return OutboundMessage(text="")

        on_progress = None
        cancel_event = None
        if isinstance(msg.raw, dict):
            on_progress = msg.raw.get("on_progress")
            cancel_event = msg.raw.get("cancel_event")

        result = await agent.run(
            session_id=msg.session_id,
            user_text=msg.text,
            on_progress=on_progress,
            cancel_event=cancel_event,
        )

        media = result.media_paths[-3:] if result.media_paths else []
        return OutboundMessage(
            text=result.text,
            media_paths=media,
            parse_mode="rich",
        )

    channel.on_message(handle)
    await channel.start()

    stop_event = asyncio.Event()

    def _ask_stop(*_: object) -> None:
        stop_event.set()

    if sys.platform != "win32":
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, _ask_stop)
        except (NotImplementedError, RuntimeError):
            pass

    print("Agent running. Press Ctrl+C to stop.")
    try:
        if sys.platform == "win32":
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
        print("Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
