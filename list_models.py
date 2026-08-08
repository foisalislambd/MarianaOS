#!/usr/bin/env python3
"""List all model IDs for a given LLM provider (for LLM_MODEL / LLM_VISION_MODEL).

Usage:
  python list_models.py                  # uses LLM_PROVIDER + LLM_API_KEY from .env
  python list_models.py gemini
  python list_models.py openrouter --filter gemini
  python list_models.py openai --key sk-...
  python list_models.py --list           # show supported providers
  python list_models.py groq --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.table import Table

from config.providers import list_providers, normalize_provider, resolve_llm

console = Console()
load_dotenv(ROOT / ".env")


def _env_key() -> str:
    return (os.getenv("LLM_API_KEY") or "").strip()


def _env_provider() -> str:
    return (os.getenv("LLM_PROVIDER") or "openai").strip()


def _env_base_url() -> str:
    return (os.getenv("LLM_BASE_URL") or "").strip()


def show_providers() -> None:
    table = Table(title="Supported providers", show_lines=False)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Default model", style="yellow")
    table.add_column("Notes", style="dim")
    for p in list_providers():
        table.add_row(p.id, p.name, p.default_model, p.notes[:70] + ("…" if len(p.notes) > 70 else ""))
    console.print(table)
    console.print(
        "\n[dim]Example:[/] python list_models.py gemini\n"
        "[dim]Then set in .env:[/] LLM_MODEL=<model-id>"
    )


def fetch_models(
    provider: str,
    api_key: str,
    base_url: str = "",
) -> List[Dict[str, Any]]:
    resolved = resolve_llm(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
    )
    client = OpenAI(
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        default_headers=resolved.default_headers or None,
    )
    page = client.models.list()
    items: List[Dict[str, Any]] = []
    for m in page:
        data: Dict[str, Any] = {"id": getattr(m, "id", None)}
        # Optional metadata when present
        for attr in ("owned_by", "created", "object"):
            if hasattr(m, attr):
                data[attr] = getattr(m, attr)
        # OpenRouter / some gateways put extra fields in model_extra or raw
        extra = getattr(m, "model_extra", None) or {}
        if isinstance(extra, dict):
            for k in ("name", "description", "context_length", "architecture"):
                if k in extra:
                    data[k] = extra[k]
        items.append(data)

    items = [x for x in items if x.get("id")]
    items.sort(key=lambda x: str(x["id"]).lower())
    return items


def print_models(
    provider: str,
    models: List[Dict[str, Any]],
    filt: str = "",
    as_json: bool = False,
    base_url: str = "",
) -> None:
    resolved = resolve_llm(provider, api_key="x", base_url=base_url)
    if filt:
        fl = filt.lower()
        models = [m for m in models if fl in str(m["id"]).lower()]

    if as_json:
        print(json.dumps({"provider": resolved.provider_id, "count": len(models), "models": models}, indent=2))
        return

    console.print(
        f"[bold]{resolved.provider_name}[/] ([cyan]{resolved.provider_id}[/])\n"
        f"[dim]{resolved.base_url}[/]\n"
        f"Models: [bold green]{len(models)}[/]"
        + (f"  filter=[yellow]{filt}[/]" if filt else "")
    )

    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="dim", width=5, justify="right")
    table.add_column("Model ID", style="cyan")
    table.add_column("Owned by / name", style="dim")

    defaults = {resolved.model, resolved.vision_model}
    for i, m in enumerate(models, 1):
        mid = str(m["id"])
        owned = str(m.get("name") or m.get("owned_by") or "")
        style = "bold yellow" if mid in defaults else "cyan"
        table.add_row(str(i), f"[{style}]{mid}[/{style}]", owned)

    console.print(table)
    console.print(
        "\n[bold]Copy into .env:[/]\n"
        f"  LLM_PROVIDER={resolved.provider_id}\n"
        f"  LLM_MODEL=<paste-model-id>\n"
        f"  LLM_VISION_MODEL=<paste-vision-model-id>"
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch all model IDs from an LLM provider for use in .env",
    )
    parser.add_argument(
        "provider",
        nargs="?",
        default=None,
        help="Provider id (gemini, openai, openrouter, …). Default: LLM_PROVIDER from .env",
    )
    parser.add_argument("--list", "-l", action="store_true", help="List supported providers and exit")
    parser.add_argument("--key", "-k", default="", help="API key (default: LLM_API_KEY from .env)")
    parser.add_argument("--base-url", default="", help="Override base URL (or LLM_BASE_URL)")
    parser.add_argument("--filter", "-f", default="", help="Filter model ids (substring)")
    parser.add_argument("--json", action="store_true", help="Print raw JSON")
    args = parser.parse_args(argv)

    if args.list:
        show_providers()
        return 0

    provider = args.provider or _env_provider()
    provider = normalize_provider(provider)
    api_key = (args.key or _env_key()).strip()
    base_url = (args.base_url or _env_base_url()).strip()

    if not api_key or api_key.startswith("your_"):
        console.print(
            "[red]Missing API key.[/] Set LLM_API_KEY in .env or pass --key\n"
            f"Provider: [cyan]{provider}[/]"
        )
        show_providers()
        return 1

    console.print(f"[dim]Fetching models from[/] [cyan]{provider}[/] …")
    try:
        models = fetch_models(provider, api_key, base_url=base_url)
    except Exception as e:
        console.print(f"[red]Failed to list models:[/] {e}")
        console.print(
            "[dim]Tip: some local servers need the OpenAI-compatible /v1/models route enabled.[/]"
        )
        return 2

    if not models:
        console.print("[yellow]No models returned.[/]")
        return 3

    print_models(provider, models, filt=args.filter, as_json=args.json, base_url=base_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
