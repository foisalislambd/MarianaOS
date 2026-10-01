"""Telegram message formatting helpers.

Primary path: Bot API Rich Messages (`sendRichMessage` + markdown field) —
GitHub-flavored-style Markdown (headings, lists, tables, code, bold/italic).
Fallback: HTML `sendMessage` for older API errors.
"""

from __future__ import annotations

import html
import re
from typing import List


RICH_MAX_CHARS = 30000  # Telegram rich limit ~32768; keep headroom
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
            split_at = text.rfind("\n\n", start, end)
            if split_at <= start:
                split_at = text.rfind("\n", start, end)
            if split_at > start:
                end = split_at + 1
        chunks.append(text[start:end].rstrip())
        start = end
    return [c for c in chunks if c]


def normalize_llm_markdown(text: str) -> str:
    """Cleanup LLM Markdown for Telegram Rich Message markdown field."""
    t = (text or "").replace("\r\n", "\n").strip()
    if not t:
        return ""
    # Strip accidental HTML the model sometimes emits
    if "<b>" in t or "<code>" in t or "<pre>" in t:
        t = (
            t.replace("<b>", "**")
            .replace("</b>", "**")
            .replace("<i>", "*")
            .replace("</i>", "*")
            .replace("<code>", "`")
            .replace("</code>", "`")
        )
        t = re.sub(r"</?pre[^>]*>", "```", t)
    # Collapse 3+ blank lines
    t = re.sub(r"\n{3,}", "\n\n", t)
    # Soft-wrap huge unbroken lines (rare)
    return t


def markdown_to_telegram_html(text: str) -> str:
    """Best-effort Markdown → Telegram HTML (fallback when rich API fails)."""
    t = normalize_llm_markdown(text)
    if not t:
        return ""

    n = len(t)
    fence_re = re.compile(r"```([a-zA-Z0-9_+-]*)\n([\s\S]*?)```", re.MULTILINE)
    last = 0
    segments: List[tuple[str, str]] = []
    for m in fence_re.finditer(t):
        if m.start() > last:
            segments.append(("text", t[last : m.start()]))
        lang = (m.group(1) or "").strip()
        body = m.group(2) or ""
        segments.append(("code", f"{lang}\0{body.rstrip(chr(10))}"))
        last = m.end()
    if last < n:
        segments.append(("text", t[last:]))

    out: List[str] = []
    for kind, payload in segments:
        if kind == "code":
            lang, _, body = payload.partition("\0")
            esc = html.escape(body)
            if lang:
                out.append(
                    f'<pre><code class="language-{html.escape(lang)}">{esc}</code></pre>'
                )
            else:
                out.append(f"<pre>{esc}</pre>")
            continue
        out.append(_inline_md_to_html(payload))
    return "".join(out).strip()


def _inline_md_to_html(text: str) -> str:
    lines_out: List[str] = []
    for line in text.split("\n"):
        raw = line
        hm = re.match(r"^(#{1,6})\s+(.*)$", raw)
        if hm:
            lines_out.append(f"<b>{_format_inline(hm.group(2))}</b>")
            continue
        if raw.startswith("> "):
            lines_out.append(f"<blockquote>{_format_inline(raw[2:])}</blockquote>")
            continue
        if re.match(r"^[-*+]\s+", raw):
            content = _format_inline(re.sub(r"^[-*+]\s+", "", raw))
            lines_out.append(f"- {content}")
            continue
        if re.match(r"^\d+\.\s+", raw):
            content = _format_inline(re.sub(r"^\d+\.\s+", "", raw))
            num = re.match(r"^(\d+)\.", raw).group(1)  # type: ignore[union-attr]
            lines_out.append(f"{num}. {content}")
            continue
        if raw.strip() == "":
            lines_out.append("")
            continue
        lines_out.append(_format_inline(raw))
    return "\n".join(lines_out)


def _format_inline(text: str) -> str:
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
        s = re.sub(
            r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
            lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>',
            s,
        )
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"__(.+?)__", r"<b>\1</b>", s)
        s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", s)
        s = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"<i>\1</i>", s)
        s = re.sub(r"~~(.+?)~~", r"<s>\1</s>", s)
        rendered.append(s)
    return "".join(rendered)
