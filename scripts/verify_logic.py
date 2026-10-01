"""Full logic verification for MarianaOS."""

from __future__ import annotations

import ast
import asyncio
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["TELEGRAM_BOT_TOKEN"] = "0000000000:TESTTOKEN"
os.environ["TELEGRAM_ALLOWED_USERS"] = "1"
os.environ["LLM_PROVIDER"] = "openrouter"
os.environ["LLM_API_KEY"] = "test"


def test_syntax() -> None:
    for p in ROOT.rglob("*.py"):
        if ".venv" in p.parts:
            continue
        ast.parse(p.read_text(encoding="utf-8"))


def test_stubs_gone() -> None:
    assert not (ROOT / "channels" / "web_channel.py").exists()
    assert not (ROOT / "channels" / "whatsapp_channel.py").exists()


def test_providers() -> None:
    from config.providers import normalize_provider, resolve_llm

    assert normalize_provider("opencode") == "openrouter"
    assert normalize_provider("gemini") == "openrouter"
    r = resolve_llm("openrouter", "sk-test")
    assert r.base_url.endswith("/api/v1")
    assert r.model


def test_telegram_stop() -> None:
    from aiogram import Bot
    from aiogram.types import InputRichMessage

    from channels.telegram_channel import STOP_CALLBACK, TelegramChannel, _stop_keyboard
    import inspect

    assert hasattr(Bot, "send_rich_message")
    assert InputRichMessage(markdown="# x").markdown == "# x"
    assert _stop_keyboard().inline_keyboard[0][0].callback_data == STOP_CALLBACK
    src = inspect.getsource(TelegramChannel)
    assert "cancel_event" in src
    assert src.count("async def send(") == 1


def test_registry() -> None:
    from config.settings import reload_settings
    from core.llm import LLMClient
    from tools import build_registry
    from tools.base import DEFAULT_CORE_TOOLS

    s = reload_settings()
    reg = build_registry(s, LLMClient.from_resolved(s.llm))
    names = {t.name for t in reg.list()}
    missing_reg = sorted(DEFAULT_CORE_TOOLS - names)
    assert not missing_reg, f"Core tools not registered: {missing_reg}"
    active = reg.active_names()
    missing_active = sorted(DEFAULT_CORE_TOOLS - active)
    assert not missing_active, f"Core tools not active: {missing_active}"
    assert len(reg.list()) >= 70
    assert "web_search" in active
    assert "kill_process" in active
    assert "capture_window" in active


def test_agent_cancel_api() -> None:
    import inspect

    from core.agent import Agent

    sig = inspect.signature(Agent.run)
    assert "cancel_event" in sig.parameters


def test_ui_apis() -> None:
    import uiautomation as auto

    from tools.ui_automation import InvokeControlTool

    assert callable(auto.DragDrop)
    assert hasattr(auto.WindowControl, "GetWindowPattern")
    assert hasattr(auto.WindowControl, "MoveWindow")
    text = (ROOT / "tools" / "ui_automation.py").read_text(encoding="utf-8")
    assert "PatternId.InvokePattern" in text
    assert "GetInvokePattern" not in text


def test_file_tools() -> None:
    from tools.extras import AppendFileTool, CopyPathTool, UnzipPathTool, ZipPathTool

    async def _run() -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "a.txt"
            src.write_text("hello", encoding="utf-8")
            copy = CopyPathTool(root)
            r = await copy.execute(str(src), str(root / "b.txt"))
            assert r.success, r.output
            assert (root / "b.txt").read_text(encoding="utf-8") == "hello"

            ap = AppendFileTool(root)
            r = await ap.execute(str(root / "b.txt"), " world")
            assert r.success, r.output
            assert (root / "b.txt").read_text(encoding="utf-8") == "hello world"

            z = ZipPathTool(root)
            r = await z.execute(str(root / "b.txt"), str(root / "b.zip"))
            assert r.success, r.output
            assert zipfile.is_zipfile(root / "b.zip")

            out = root / "out"
            u = UnzipPathTool(root)
            r = await u.execute(str(root / "b.zip"), str(out))
            assert r.success, r.output
            assert (out / "b.txt").exists()

    asyncio.run(_run())


def test_markdown() -> None:
    from utils.telegram_format import markdown_to_telegram_html, normalize_llm_markdown

    md = "# Title\n\nHello `code` and **bold**"
    assert normalize_llm_markdown(md).startswith("# Title")
    html = markdown_to_telegram_html(md)
    assert "<b>Title</b>" in html
    assert "<code>code</code>" in html
    assert "<b>bold</b>" in html


def main() -> int:
    tests = [
        test_syntax,
        test_stubs_gone,
        test_providers,
        test_telegram_stop,
        test_registry,
        test_agent_cancel_api,
        test_ui_apis,
        test_file_tools,
        test_markdown,
    ]
    for fn in tests:
        fn()
        print(f"OK  {fn.__name__}")
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
