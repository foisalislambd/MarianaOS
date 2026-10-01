#!/usr/bin/env python3
"""List model IDs for OpenAI-compatible providers (httpx).

Usage:
  python list_models.py
  python list_models.py openrouter
  python list_models.py openrouter --filter claude
  python list_models.py --list
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from config.providers import (
    list_providers,
    normalize_provider,
    provider_allows_empty_key,
    resolve_llm,
)
from core.providers.factory import create_llm_provider

load_dotenv(ROOT / ".env", override=True)


def _env_key() -> str:
    return (os.getenv("LLM_API_KEY") or "").strip()


def _env_provider() -> str:
    return (os.getenv("LLM_PROVIDER") or "openrouter").strip()


def _env_base_url() -> str:
    return (os.getenv("LLM_BASE_URL") or "").strip()


def show_providers() -> None:
    print("Supported providers (OpenAI-compatible via httpx):\n")
    for p in list_providers():
        print(f"  {p.id:18}  {p.name:28}  default={p.default_model}")
        if p.notes:
            print(f"    {p.notes}")
    print("\nExample: python list_models.py openrouter --filter gemini")
    print("Then set in .env: LLM_MODEL=<model-id>")


async def fetch_models(
    provider: str,
    api_key: str,
    base_url: str = "",
) -> List[Dict[str, Any]]:
    resolved = resolve_llm(provider=provider, api_key=api_key, base_url=base_url)
    llm = create_llm_provider(resolved)
    ids = await llm.list_models()
    return [{"id": i} for i in ids]


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
        print(
            json.dumps(
                {"provider": resolved.provider_id, "count": len(models), "models": models},
                indent=2,
            )
        )
        return

    print(f"{resolved.provider_name} ({resolved.provider_id})")
    if resolved.notes:
        print(resolved.notes)
    print(f"Models: {len(models)}" + (f"  filter={filt}" if filt else ""))
    print("-" * 60)
    defaults = {resolved.model, resolved.vision_model}
    for i, m in enumerate(models, 1):
        mid = str(m["id"])
        mark = " *" if mid in defaults else ""
        print(f"{i:4}. {mid}{mark}")
    print("-" * 60)
    print("Copy into .env:")
    print(f"  LLM_PROVIDER={resolved.provider_id}")
    print("  LLM_MODEL=<paste-model-id>")
    print("  LLM_VISION_MODEL=<paste-vision-model-id>")
    print("  LLM_API_KEY=<your-key>")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch model IDs via httpx")
    parser.add_argument("provider", nargs="?", default=None)
    parser.add_argument("--list", "-l", action="store_true")
    parser.add_argument("--key", "-k", default="")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--filter", "-f", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.list:
        show_providers()
        return 0

    provider = normalize_provider(args.provider or _env_provider())
    api_key = (args.key or _env_key()).strip()
    base_url = (args.base_url or _env_base_url()).strip()

    if (not api_key or api_key.startswith("your_")) and not provider_allows_empty_key(
        provider
    ):
        print("Missing API key. Set LLM_API_KEY in .env or pass --key")
        show_providers()
        return 1
    if not api_key:
        api_key = provider

    print(f"Fetching models from {provider} …")
    try:
        models = asyncio.run(fetch_models(provider, api_key, base_url=base_url))
    except Exception as e:
        print(f"Failed to list models: {e}")
        return 2

    if not models:
        print("No models returned.")
        return 3

    print_models(provider, models, filt=args.filter, as_json=args.json, base_url=base_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
