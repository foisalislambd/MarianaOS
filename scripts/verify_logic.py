"""One-shot logic verification for MarianaOS rebuild."""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "0000000000:TESTTOKEN")
os.environ.setdefault("TELEGRAM_ALLOWED_USERS", "1")
os.environ.setdefault("LLM_PROVIDER", "openrouter")
os.environ.setdefault("LLM_API_KEY", "test")


def test_syntax() -> None:
    for p in ROOT.rglob("*.py"):
        if ".venv" in p.parts:
            continue
        ast.parse(p.read_text(encoding="utf-8"))


def test_markdown() -> None:
    from utils.telegram_format import markdown_to_telegram_html, normalize_llm_markdown

    md = (
        "# MarianaOS online\n\n"
        "Your Telegram ID: `12345`\n\n"
        "- `open Notepad`"
    )
    assert normalize_llm_markdown(md).startswith("# MarianaOS")
    html = markdown_to_telegram_html(md)
    assert "<b>MarianaOS online</b>" in html, html
    assert "<code>12345</code>" in html, html
    assert "<code>open Notepad</code>" in html, html


def test_providers() -> None:
    from config.providers import normalize_provider, resolve_llm

    assert normalize_provider("opencode") == "openrouter"
    assert normalize_provider("gemini") == "openrouter"
    r = resolve_llm("openrouter", "sk-or-test")
    assert r.provider_id == "openrouter"
    assert "openrouter.ai" in r.base_url


def test_telegram_rich() -> None:
    import inspect

    from aiogram import Bot
    from aiogram.types import InputRichMessage

    from channels.telegram_channel import TelegramChannel

    assert hasattr(Bot, "send_rich_message")
    assert hasattr(Bot, "send_rich_message_draft")
    m = InputRichMessage(markdown="# Hi\n\n**bold**")
    assert m.markdown and m.markdown.startswith("# Hi")

    src = inspect.getsource(TelegramChannel)
    assert "send_rich_message" in src
    assert "InputRichMessage" in src
    assert src.count("async def send(") == 1


def test_ui_invoke() -> None:
    text = (ROOT / "tools" / "ui_automation.py").read_text(encoding="utf-8")
    assert "GetInvokePattern" not in text
    assert "PatternId.InvokePattern" in text


def test_uia_apis() -> None:
    import uiautomation as auto

    assert callable(auto.SetClipboardText)
    assert callable(auto.WheelUp)
    assert hasattr(auto.WindowControl, "IsMinimize")
    auto.SetClipboardText("mariana-verify")
    assert auto.GetClipboardText() == "mariana-verify"


def test_registry_and_agent() -> None:
    from config.settings import reload_settings
    from core.agent import Agent, SYSTEM_PROMPT
    from core.llm import LLMClient
    from core.memory import ConversationMemory
    from tools import build_registry

    s = reload_settings()
    reg = build_registry(s, LLMClient.from_resolved(s.llm))
    active = reg.active_names()
    for name in (
        "get_ui_tree",
        "click_control",
        "hotkey",
        "type_text",
        "wait",
        "open_url",
        "cursor_type_in_chat",
    ):
        assert name in active, name
    assert "take_screenshot" not in active
    assert "Rich Markdown" in SYSTEM_PROMPT or "Telegram reply style" in SYSTEM_PROMPT

    agent = Agent(s, LLMClient.from_resolved(s.llm), reg, ConversationMemory())
    reply = agent._user_reply("## Done\n\nOpened Notepad.", ["open_application: ok", "type_text: ok"])
    assert "`open_application`" in reply
    assert reply.startswith("## Done")


def test_llm_message_strip() -> None:
    from core.providers.openai_compat import _strip_private

    cleaned = _strip_private({"role": "assistant", "content": "x", "_native": 1})
    assert "_native" not in cleaned


def main() -> int:
    tests = [
        test_syntax,
        test_markdown,
        test_providers,
        test_telegram_rich,
        test_ui_invoke,
        test_uia_apis,
        test_registry_and_agent,
        test_llm_message_strip,
    ]
    for fn in tests:
        fn()
        print(f"OK  {fn.__name__}")
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
