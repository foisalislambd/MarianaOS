"""Telegram bot channel — aiogram 3.x with Rich Message Markdown + Stop button."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Set

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputRichMessage,
    Message,
)

from channels.base import BaseChannel, InboundMessage, OutboundMessage
from utils.logging import get_logger
from utils.telegram_format import (
    HTML_MAX_CHARS,
    RICH_MAX_CHARS,
    chunk_text,
    markdown_to_telegram_html,
    normalize_llm_markdown,
)

log = get_logger("marianaos.telegram")

STOP_CALLBACK = "stop_task"


def _stop_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏹ Stop", callback_data=STOP_CALLBACK)]
        ]
    )


class TelegramChannel(BaseChannel):
    name = "telegram"

    def __init__(self, token: str, allowed_user_ids: List[int]) -> None:
        super().__init__()
        self.token = token
        self.allowed: Set[int] = set(allowed_user_ids)
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self._busy: Set[int] = set()
        self._polling_task = None
        self._cancel_events: Dict[int, asyncio.Event] = {}
        self._run_tasks: Dict[int, asyncio.Task] = {}

    def _authorized(self, user_id: int) -> bool:
        if not self.allowed:
            log.warning("TELEGRAM_ALLOWED_USERS is empty — denying all users for safety")
            return False
        return user_id in self.allowed

    async def start(self) -> None:
        self.bot = Bot(
            token=self.token,
            default=DefaultBotProperties(parse_mode=None),
        )
        self.dp = Dispatcher()
        self.dp.message.register(self._cmd_start, Command("start"))
        self.dp.message.register(self._cmd_help, Command("help"))
        self.dp.message.register(self._cmd_reset, Command("reset"))
        self.dp.message.register(self._cmd_id, Command("id"))
        self.dp.message.register(self._on_photo, F.photo)
        self.dp.message.register(self._on_text, F.text)
        self.dp.callback_query.register(
            self._on_stop_callback, F.data == STOP_CALLBACK
        )

        me = await self.bot.get_me()
        log.info("Telegram bot online as @%s", me.username)

        self._polling_task = asyncio.create_task(
            self.dp.start_polling(self.bot, handle_signals=False)
        )

    async def stop(self) -> None:
        # Cancel any in-flight user tasks
        for uid, task in list(self._run_tasks.items()):
            ev = self._cancel_events.get(uid)
            if ev:
                ev.set()
            if task and not task.done():
                task.cancel()
        if self.dp:
            await self.dp.stop_polling()
        if self._polling_task:
            try:
                await self._polling_task
            except Exception:
                pass
        if self.bot:
            await self.bot.session.close()
        log.info("Telegram bot stopped")

    async def send(self, user_id: str, message: OutboundMessage) -> None:
        if not self.bot:
            return
        chat_id = int(user_id)
        text = (message.text or "").strip()
        if text:
            await self._send_rich_markdown(chat_id, text)

        for media in message.media_paths:
            path = Path(media)
            if path.exists() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                try:
                    data = path.read_bytes()
                    await self.bot.send_photo(
                        chat_id=chat_id,
                        photo=BufferedInputFile(data, filename=path.name),
                    )
                except Exception as e:
                    log.warning("Failed to send photo %s: %s", path, e)

    async def _send_rich_markdown(self, chat_id: int, text: str) -> None:
        assert self.bot is not None
        md = normalize_llm_markdown(text)
        if not md:
            return

        for chunk in chunk_text(md, RICH_MAX_CHARS):
            try:
                await self.bot.send_rich_message(
                    chat_id=chat_id,
                    rich_message=InputRichMessage(markdown=chunk),
                )
                continue
            except Exception as e:
                log.warning("sendRichMessage failed (%s) — HTML fallback", e)

            html_text = markdown_to_telegram_html(chunk)
            for hchunk in chunk_text(html_text, HTML_MAX_CHARS):
                try:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=hchunk,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                    )
                except Exception as e2:
                    log.warning("HTML send failed (%s) — plain", e2)
                    await self.bot.send_message(chat_id=chat_id, text=hchunk)

    async def _cmd_start(self, message: Message) -> None:
        user = message.from_user
        if not user:
            return
        if not self._authorized(user.id):
            await self._send_rich_markdown(
                user.id,
                f"## Unauthorized\n\nYour Telegram ID: `{user.id}`\n\n"
                "Add it to `TELEGRAM_ALLOWED_USERS` in `.env`, then restart the agent.",
            )
            return
        await self._send_rich_markdown(
            user.id,
            """# MarianaOS online

I can operate this Windows PC for you — apps, files, Cursor IDE, UI controls, shell, and more.

## Try saying
- `Open Notepad and type Hello World`
- `Open C:\\Users\\…\\MarianaOS in Cursor`
- `Select Sonnet in Cursor`
- `What windows are open right now?`
- `Take a screenshot` *(only when you ask)*

While a task is running, tap **⏹ Stop** to cancel it.

## Commands
/help · /reset · /id""",
        )

    async def _cmd_help(self, message: Message) -> None:
        user = message.from_user
        if not user:
            return
        if not self._authorized(user.id):
            await message.answer("Unauthorized")
            return
        await self._send_rich_markdown(
            user.id,
            """# Help

## Commands
- `/start` — intro
- `/help` — this help
- `/reset` — clear conversation memory
- `/id` — your Telegram user id

## Stop a running task
While I am working, the progress message shows an **⏹ Stop** button — tap it to cancel.

## What I do well
- **UI Automation** — find buttons/fields by name, click, type
- **Cursor IDE** — change model / open chats via Python
- **Files & shell** — read/write/search, PowerShell when needed
- **Apps & windows** — launch, focus, list""",
        )

    async def _cmd_id(self, message: Message) -> None:
        user = message.from_user
        if not user:
            return
        await self._send_rich_markdown(user.id, f"Your Telegram ID: `{user.id}`")

    async def _cmd_reset(self, message: Message) -> None:
        user = message.from_user
        if not user:
            return
        if not self._authorized(user.id):
            await message.answer("Unauthorized")
            return
        if self._handler:
            inbound = InboundMessage(
                channel=self.name,
                user_id=str(user.id),
                session_id=f"tg:{user.id}",
                text="__RESET__",
                display_name=user.full_name or "",
                raw=message,
            )
            await self._handler(inbound)
        await self._send_rich_markdown(user.id, "Memory cleared. Fresh start.")

    async def _on_stop_callback(self, callback: CallbackQuery) -> None:
        user = callback.from_user
        if not user:
            return
        if not self._authorized(user.id):
            await callback.answer("Unauthorized", show_alert=True)
            return

        ev = self._cancel_events.get(user.id)
        task = self._run_tasks.get(user.id)
        if not ev and not task:
            await callback.answer("Nothing is running.")
            return

        if ev:
            ev.set()
        if task and not task.done():
            task.cancel()

        try:
            if callback.message:
                await callback.message.edit_text(
                    "⏹ Stopping…",
                    reply_markup=None,
                )
        except Exception:
            pass
        await callback.answer("Stopping task…")
        log.info("User %s requested stop", user.id)

    async def _on_photo(self, message: Message) -> None:
        user = message.from_user
        if not user or not message.photo:
            return
        if not self._authorized(user.id):
            await message.answer(f"Unauthorized. Your ID: {user.id}")
            return

        caption = message.caption or "Analyze this image and help with the PC task."
        largest = message.photo[-1]
        assert self.bot is not None
        from config.settings import get_settings

        dest = get_settings().screenshot_dir / f"tg_{largest.file_unique_id}.jpg"
        await self.bot.download(largest, destination=dest)
        text = f"{caption}\n\n[User attached image saved at: {dest}]"
        await self._handle_user_text(message, text)

    async def _on_text(self, message: Message) -> None:
        if not message.text or message.text.startswith("/"):
            return
        await self._handle_user_text(message, message.text)

    async def _handle_user_text(self, message: Message, text: str) -> None:
        user = message.from_user
        if not user:
            return
        if not self._authorized(user.id):
            await message.answer(f"Unauthorized. Your ID: {user.id}")
            return
        if user.id in self._busy:
            await self._send_rich_markdown(
                user.id,
                "Still working on your previous request.\n\n"
                "Tap **⏹ Stop** on that progress message to cancel it.",
            )
            return
        if not self._handler:
            await message.answer("Agent handler not ready.")
            return

        self._busy.add(user.id)
        cancel_event = asyncio.Event()
        self._cancel_events[user.id] = cancel_event

        status_msg = await message.answer(
            "🔄 Working…\n\nUnderstanding your request…",
            reply_markup=_stop_keyboard(),
        )

        async def on_progress(status_text: str) -> None:
            if cancel_event.is_set():
                return
            try:
                assert self.bot is not None
                await self.bot.send_chat_action(
                    chat_id=user.id, action=ChatAction.TYPING
                )
                body = f"🔄 Working…\n\n{status_text}"
                await status_msg.edit_text(
                    body[:500],
                    reply_markup=_stop_keyboard(),
                )
            except Exception:
                pass

        inbound = InboundMessage(
            channel=self.name,
            user_id=str(user.id),
            session_id=f"tg:{user.id}",
            text=text,
            display_name=user.full_name or "",
            raw={
                "message": message,
                "on_progress": on_progress,
                "cancel_event": cancel_event,
            },
        )

        run_task = asyncio.create_task(self._handler(inbound))
        self._run_tasks[user.id] = run_task

        try:
            outbound = await run_task
        except asyncio.CancelledError:
            try:
                await status_msg.edit_text("⏹ Stopped", reply_markup=None)
            except Exception:
                pass
            await self._send_rich_markdown(
                user.id, "## Stopped\n\nTask stopped by you."
            )
        except Exception as e:
            log.exception("Handler error")
            try:
                await status_msg.edit_text("❌ Error", reply_markup=None)
            except Exception:
                pass
            await self._send_rich_markdown(user.id, f"## Error\n\n`{e}`")
        else:
            was_stopped = cancel_event.is_set()
            try:
                await status_msg.edit_text(
                    "⏹ Stopped" if was_stopped else "✅ Done",
                    reply_markup=None,
                )
            except Exception:
                try:
                    await status_msg.delete()
                except Exception:
                    pass
            if outbound and (outbound.text or outbound.media_paths):
                await self.send(str(user.id), outbound)
        finally:
            self._busy.discard(user.id)
            self._cancel_events.pop(user.id, None)
            self._run_tasks.pop(user.id, None)
