"""Convert LLM Markdown → Telegram formats.

Prefer Telegram Bot API Rich Messages (sendRichMessage + markdown field),
which accept GitHub-flavored-style Markdown (headings, lists, tables, code).
Fallback: HTML parse_mode for older clients / API errors.
Docs: https://core.telegram.org/bots/api#sendrichmessage
       https://core.telegram.org/bots/api#formatting-options
"""

from __future__ import annotations

import html
import re
from typing import List


RICH_MAX_CHARS = 30000  # Telegram rich limit is 32768; keep headroom
HTML_MAX_CHARS = 4000


def chunk_text(text: str, size: int) -> List[str]:
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            # Prefer breaking on paragraph / newline
            split_at = text.rfind("\n\n", start, end)
            if split_at <= start:
                split_at = text.rfind("\n", start, end)
            if split_at > start:
                end = split_at + 1
        chunks.append(text[start:end].rstrip())
        start = end
    return [c for c in chunks if c]


def normalize_llm_markdown(text: str) -> str:
    """Light cleanup so LLM output plays nicer with Telegram Rich Markdown."""
    t = (text or "").replace("\r\n", "\n").strip()
    if not t:
        return ""
    # Convert ATX underline-style leftovers; keep standard GFM
    # Collapse 3+ blank lines
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t


def markdown_to_telegram_html(text: str) -> str:
    """Best-effort Markdown → Telegram HTML (fallback path)."""
    t = normalize_llm_markdown(text)
    if not t:
        return ""

    n = len(t)

    # Extract fenced code blocks first
    fence_re = re.compile(r"```([a-zA-Z0-9_+-]*)\n([\s\S]*?)```", re.MULTILINE)
    last = 0
    segments: List[tuple[str, str]] = []  # ("text"|"code", payload) ; code payload = lang\0body
    for m in fence_re.finditer(t):
        if m.start() > last:
            segments.append(("text", t[last : m.start()]))
        lang = (m.group(1) or "").strip()
        body = m.group(2) or ""
        segments.append(("code", f"{lang}\0{body.rstrip('\n')}"))
        last = m.end()
    if last < n:
        segments.append(("text", t[last:]))

    out: List[str] = []
    for kind, payload in segments:
        if kind == "code":
            lang, _, body = payload.partition("\0")
            esc = html.escape(body)
            if lang:
                out.append(f'<pre><code class="language-{html.escape(lang)}">{esc}</code></pre>')
            else:
                out.append(f"<pre>{esc}</pre>")
            continue
        out.append(_inline_md_to_html(payload))
    return "".join(out).strip()


def _inline_md_to_html(text: str) -> str:
    # Escape first, then re-introduce tags from markdown patterns on escaped text
    # Work line-by-line for headers / lists / quotes
    lines_out: List[str] = []
    for line in text.split("\n"):
        raw = line
        # Headers
        hm = re.match(r"^(#{1,6})\s+(.*)$", raw)
        if hm:
            content = _format_inline(hm.group(2))
            lines_out.append(f"<b>{content}</b>")
            continue
        # Blockquote
        if raw.startswith("> "):
            content = _format_inline(raw[2:])
            lines_out.append(f"<blockquote>{content}</blockquote>")
            continue
        # Unordered list
        if re.match(r"^[-*+]\s+", raw):
            content = _format_inline(re.sub(r"^[-*+]\s+", "", raw))
            lines_out.append(f"- {content}")
            continue
        # Ordered list
        if re.match(r"^\d+\.\s+", raw):
            content = _format_inline(re.sub(r"^\d+\.\s+", "", raw))
            num = re.match(r"^(\d+)\.", raw).group(1)  # type: ignore[union-attr]
            lines_out.append(f"{num}. {content}")
            continue
        if raw.strip() == "":
            lines_out.append("")
            continue
        lines_out.append(_format_inline(raw))
    # Join with newlines — Telegram HTML preserves \n as line breaks in many clients
    return "\n".join(lines_out)


def _format_inline(text: str) -> str:
    """Escape + apply bold/italic/code/links on a single line."""
    # Protect inline code first
    pieces: List[str] = []
    pos = 0
    for m in re.finditer(r"`([^`]+)`", text):
        if m.start() > pos:
            pieces.append(("t", text[pos : m.start()]))
        pieces.append(("c", m.group(1)))
        pos = m.end()
    if pos < len(text):
        pieces.append(("t", text[pos:]))

    rendered: List[str] = []
    for kind, val in pieces:
        if kind == "c":
            rendered.append(f"<code>{html.escape(val)}</code>")
            continue
        s = html.escape(val)
        # links [text](url)
        s = re.sub(
            r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
            lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>',
            s,
        )
        # bold **text** or __text__
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"__(.+?)__", r"<b>\1</b>", s)
        # italic *text* or _text_ (simple)
        s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", s)
        s = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"<i>\1</i>", s)
        # strikethrough ~~text~~
        s = re.sub(r"~~(.+?)~~", r"<s>\1</s>", s)
        rendered.append(s)
    return "".join(rendered)
