"""Telegram bot channel."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Set

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from channels.base import BaseChannel, InboundMessage, OutboundMessage
from utils.logging import get_logger

log = get_logger("marianaos.telegram")


class TelegramChannel(BaseChannel):
    name = "telegram"

    def __init__(self, token: str, allowed_user_ids: List[int]) -> None:
        super().__init__()
        self.token = token
        self.allowed: Set[int] = set(allowed_user_ids)
        self.app: Optional[Application] = None
        self._busy: Set[int] = set()

    def _authorized(self, user_id: int) -> bool:
        if not self.allowed:
            log.warning("TELEGRAM_ALLOWED_USERS is empty — denying all users for safety")
            return False
        return user_id in self.allowed

    async def start(self) -> None:
        self.app = (
            Application.builder()
            .token(self.token)
            .concurrent_updates(True)
            .build()
        )
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(CommandHandler("reset", self._cmd_reset))
        self.app.add_handler(CommandHandler("id", self._cmd_id))
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text)
        )
        self.app.add_handler(MessageHandler(filters.PHOTO, self._on_photo))

        await self.app.initialize()
        await self.app.start()
        assert self.app.updater is not None
        await self.app.updater.start_polling(drop_pending_updates=True)
        me = await self.app.bot.get_me()
        log.info("Telegram bot online as @%s", me.username)

    async def stop(self) -> None:
        if not self.app:
            return
        if self.app.updater:
            await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
        log.info("Telegram bot stopped")

    async def send(self, user_id: str, message: OutboundMessage) -> None:
        if not self.app:
            return
        chat_id = int(user_id)
        text = (message.text or "").strip()
        if text:
            for chunk in _chunk_text(text, 4000):
                try:
                    await self.app.bot.send_message(
                        chat_id=chat_id,
                        text=chunk,
                        parse_mode=ParseMode.MARKDOWN if message.parse_mode else None,
                    )
                except Exception:
                    await self.app.bot.send_message(chat_id=chat_id, text=chunk)

        for media in message.media_paths:
            path = Path(media)
            if path.exists() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                try:
                    with path.open("rb") as f:
                        await self.app.bot.send_photo(chat_id=chat_id, photo=f)
                except Exception as e:
                    log.warning("Failed to send photo %s: %s", path, e)

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if not user or not update.message:
            return
        if not self._authorized(user.id):
            await update.message.reply_text(
                f"⛔ Unauthorized.\nYour Telegram ID: `{user.id}`\n"
                "Add it to TELEGRAM_ALLOWED_USERS in .env",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        await update.message.reply_text(
            "🖥️ *MarianaOS Agent online*\n\n"
            "You can control this PC — open Cursor, folders, "
            "screenshots, mouse/keyboard, model select, and more.\n\n"
            "Examples:\n"
            "• `open D:\\\\Projects\\\\MarianaOS in Cursor`\n"
            "• `take a screenshot and tell me what is on screen`\n"
            "• `select the claude-sonnet model in Cursor`\n\n"
            "/help · /reset · /id",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return
        if not self._authorized(update.effective_user.id):
            await update.message.reply_text("Unauthorized")
            return
        await update.message.reply_text(
            "*Commands*\n"
            "/start — intro\n"
            "/help — this help\n"
            "/reset — clear conversation memory\n"
            "/id — show your Telegram user id\n\n"
            "*What I can do*\n"
            "• Open folders/files in Cursor IDE\n"
            "• Select Cursor AI models\n"
            "• Take & analyze screenshots\n"
            "• Click, type, hotkeys\n"
            "• Files, shell, windows, clipboard\n"
            "• Send final screenshots back to you",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def _cmd_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return
        await update.message.reply_text(
            f"Your Telegram ID: `{update.effective_user.id}`",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def _cmd_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return
        if not self._authorized(update.effective_user.id):
            await update.message.reply_text("Unauthorized")
            return
        if self._handler:
            inbound = InboundMessage(
                channel=self.name,
                user_id=str(update.effective_user.id),
                session_id=f"tg:{update.effective_user.id}",
                text="__RESET__",
                display_name=update.effective_user.full_name or "",
                raw=update,
            )
            await self._handler(inbound)
        await update.message.reply_text("🧹 Memory cleared.")

    async def _on_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        msg = update.message
        if not user or not msg:
            return
        if not self._authorized(user.id):
            await msg.reply_text(f"⛔ Unauthorized. Your ID: {user.id}")
            return

        photos = msg.photo
        if not photos:
            return

        caption = msg.caption or "Analyze this image and help with the PC task."
        largest = photos[-1]
        file = await context.bot.get_file(largest.file_id)
        from config.settings import get_settings

        dest = get_settings().screenshot_dir / f"tg_{largest.file_unique_id}.jpg"
        await file.download_to_drive(custom_path=str(dest))
        text = f"{caption}\n\n[User attached image saved at: {dest}]"
        # Message objects are immutable in PTB — do not assign msg.text
        await self._handle_user_text(update, context, text)

    async def _on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.message
        if not msg or not msg.text:
            return
        await self._handle_user_text(update, context, msg.text)

    async def _handle_user_text(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        text: str,
    ) -> None:
        user = update.effective_user
        msg = update.message
        if not user or not msg:
            return
        if not self._authorized(user.id):
            await msg.reply_text(f"⛔ Unauthorized. Your ID: {user.id}")
            return
        if user.id in self._busy:
            await msg.reply_text("⏳ Still working on your previous request…")
            return
        if not self._handler:
            await msg.reply_text("Agent handler not ready.")
            return

        self._busy.add(user.id)
        status = await msg.reply_text("🧠 Thinking…")

        async def on_progress(status_text: str) -> None:
            try:
                await context.bot.send_chat_action(
                    chat_id=user.id, action=ChatAction.TYPING
                )
                await status.edit_text(status_text)
            except Exception:
                pass

        inbound = InboundMessage(
            channel=self.name,
            user_id=str(user.id),
            session_id=f"tg:{user.id}",
            text=text,
            display_name=user.full_name or "",
            raw={"update": update, "on_progress": on_progress},
        )

        try:
            outbound = await self._handler(inbound)
            try:
                await status.delete()
            except Exception:
                pass
            await self.send(str(user.id), outbound)
        except Exception as e:
            log.exception("Handler error")
            await msg.reply_text(f"❌ Error: {e}")
        finally:
            self._busy.discard(user.id)


def _chunk_text(text: str, size: int) -> List[str]:
    if not text:
        return []
    return [text[i : i + size] for i in range(0, len(text), size)]
