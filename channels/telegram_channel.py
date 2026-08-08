"""Telegram bot channel — uses Bot API Rich Messages for AI replies."""

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
from utils.telegram_format import (
    HTML_MAX_CHARS,
    RICH_MAX_CHARS,
    chunk_text,
    markdown_to_telegram_html,
    normalize_llm_markdown,
)

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
        mode = (message.parse_mode or "rich").strip().lower()

        if text:
            if mode in {"rich", "markdown", "md"}:
                await self._send_rich_markdown(chat_id, text)
            elif mode in {"html"}:
                await self._send_html(chat_id, text)
            elif mode in {"markdownv2", "markdown_v2"}:
                await self._send_plain_with_mode(chat_id, text, ParseMode.MARKDOWN_V2)
            else:
                await self._send_plain_with_mode(chat_id, text, None)

        for media in message.media_paths:
            path = Path(media)
            if path.exists() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                try:
                    with path.open("rb") as f:
                        await self.app.bot.send_photo(chat_id=chat_id, photo=f)
                except Exception as e:
                    log.warning("Failed to send photo %s: %s", path, e)

    async def _send_rich_markdown(self, chat_id: int, text: str) -> None:
        """Bot API 10.1+ Rich Messages — best for AI / LLM Markdown replies."""
        assert self.app is not None
        md = normalize_llm_markdown(text)
        for chunk in chunk_text(md, RICH_MAX_CHARS):
            try:
                await self.app.bot._post(  # noqa: SLF001 — PTB has no public sendRichMessage yet
                    "sendRichMessage",
                    {
                        "chat_id": chat_id,
                        "rich_message": {"markdown": chunk},
                    },
                )
            except Exception as e:
                log.warning("sendRichMessage failed (%s) — falling back to HTML", e)
                await self._send_html(chat_id, chunk)

    async def _send_html(self, chat_id: int, text: str) -> None:
        assert self.app is not None
        html_text = markdown_to_telegram_html(text)
        for chunk in chunk_text(html_text, HTML_MAX_CHARS):
            try:
                await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=chunk,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
            except Exception as e:
                log.warning("HTML send failed (%s) — plain text", e)
                await self.app.bot.send_message(chat_id=chat_id, text=chunk)

    async def _send_plain_with_mode(
        self, chat_id: int, text: str, parse_mode: Optional[str]
    ) -> None:
        assert self.app is not None
        for chunk in chunk_text(text, HTML_MAX_CHARS):
            try:
                await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=chunk,
                    parse_mode=parse_mode,
                    disable_web_page_preview=True,
                )
            except Exception:
                await self.app.bot.send_message(chat_id=chat_id, text=chunk)

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if not user or not update.message:
            return
        if not self._authorized(user.id):
            await self._send_rich_markdown(
                user.id,
                f"⛔ **Unauthorized**\n\nYour Telegram ID: `{user.id}`\n\n"
                "Add it to `TELEGRAM_ALLOWED_USERS` in `.env`",
            )
            return
        await self._send_rich_markdown(
            user.id,
            """# MarianaOS Agent online

You can control this PC — Cursor, folders, screenshots, mouse/keyboard, model select, and more.

## Examples
- `open D:\\Projects\\MarianaOS in Cursor`
- `in Cursor select model Sonnet 5`
- `take a screenshot and tell me what is on screen`

/help · /reset · /id""",
        )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return
        if not self._authorized(update.effective_user.id):
            await update.message.reply_text("Unauthorized")
            return
        await self._send_rich_markdown(
            update.effective_user.id,
            """# Commands
- /start — intro
- /help — this help
- /reset — clear conversation memory
- /id — show your Telegram user id

# What I can do
- Open folders/files in Cursor IDE
- Select Cursor AI models (Python / state.vscdb)
- Take & analyze screenshots
- Click, type, hotkeys
- Files, shell, windows, clipboard
- Send final screenshots back to you""",
        )

    async def _cmd_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return
        await self._send_rich_markdown(
            update.effective_user.id,
            f"Your Telegram ID: `{update.effective_user.id}`",
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
