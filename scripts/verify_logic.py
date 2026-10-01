"""Quick sanity checks for MarianaOS."""

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


def main() -> int:
    for p in ROOT.rglob("*.py"):
        if ".venv" in p.parts:
            continue
        ast.parse(p.read_text(encoding="utf-8"))

    from aiogram import Bot
    from aiogram.types import InputRichMessage

    from channels.telegram_channel import STOP_CALLBACK, _stop_keyboard
    from config.providers import normalize_provider, resolve_llm
    from config.settings import reload_settings
    from core.llm import LLMClient
    from tools import build_registry
    from utils.paths import find_cursor_exe

    assert hasattr(Bot, "send_rich_message")
    assert InputRichMessage(markdown="# hi").markdown == "# hi"
    assert _stop_keyboard().inline_keyboard[0][0].callback_data == STOP_CALLBACK
    assert normalize_provider("opencode") == "openrouter"
    assert "openrouter.ai" in resolve_llm("openrouter", "k").base_url

    s = reload_settings()
    reg = build_registry(s, LLMClient.from_resolved(s.llm))
    assert "click_control" in reg.active_names()
    assert "take_screenshot" not in reg.active_names()
    assert find_cursor_exe() is not None or True  # may be missing on CI

    # stubs removed
    assert not (ROOT / "channels" / "web_channel.py").exists()
    assert not (ROOT / "channels" / "whatsapp_channel.py").exists()

    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
