"""LLM provider presets (OpenAI-compatible via httpx)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ProviderPreset:
    id: str
    name: str
    base_url: str
    default_model: str
    default_vision_model: str
    default_headers: Dict[str, str] = field(default_factory=dict)
    notes: str = ""
    aliases: tuple[str, ...] = ()


PROVIDERS: Dict[str, ProviderPreset] = {}


def _add(p: ProviderPreset) -> None:
    PROVIDERS[p.id] = p
    for a in p.aliases:
        PROVIDERS[a] = p


_add(
    ProviderPreset(
        id="openrouter",
        name="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        default_model="google/gemini-2.5-flash",
        default_vision_model="google/gemini-2.5-flash",
        default_headers={
            "HTTP-Referer": "https://github.com/marianaos-agent",
            "X-Title": "MarianaOS Agent",
        },
        notes="https://openrouter.ai/keys",
        aliases=("gemini", "anthropic", "claude", "opencode", "zen", "oc"),
    )
)
_add(
    ProviderPreset(
        id="openai",
        name="OpenAI",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o",
        default_vision_model="gpt-4o",
        notes="https://platform.openai.com/api-keys",
    )
)
_add(
    ProviderPreset(
        id="groq",
        name="Groq",
        base_url="https://api.groq.com/openai/v1",
        default_model="llama-3.3-70b-versatile",
        default_vision_model="meta-llama/llama-4-scout-17b-16e-instruct",
        notes="https://console.groq.com/keys",
    )
)
_add(
    ProviderPreset(
        id="deepseek",
        name="DeepSeek",
        base_url="https://api.deepseek.com",
        default_model="deepseek-chat",
        default_vision_model="deepseek-chat",
        notes="https://platform.deepseek.com/",
    )
)
_add(
    ProviderPreset(
        id="ollama",
        name="Ollama (local)",
        base_url="http://127.0.0.1:11434/v1",
        default_model="llama3.2",
        default_vision_model="llava",
        notes="Local Ollama server",
    )
)
_add(
    ProviderPreset(
        id="openai_compatible",
        name="Custom OpenAI-compatible",
        base_url="http://127.0.0.1:1234/v1",
        default_model="local-model",
        default_vision_model="local-model",
        aliases=("custom", "lmstudio", "compatible"),
        notes="Set LLM_BASE_URL + LLM_MODEL",
    )
)


def normalize_provider(name: str) -> str:
    key = (name or "openrouter").strip().lower().replace(" ", "_").replace("-", "_")
    if key in PROVIDERS:
        return PROVIDERS[key].id
    return key


def get_provider(name: str) -> Optional[ProviderPreset]:
    return PROVIDERS.get(normalize_provider(name))


def list_providers() -> List[ProviderPreset]:
    seen: set[str] = set()
    out: List[ProviderPreset] = []
    for p in PROVIDERS.values():
        if p.id in seen:
            continue
        seen.add(p.id)
        out.append(p)
    return sorted(out, key=lambda x: (0 if x.id == "openrouter" else 1, x.name.lower()))


@dataclass
class ResolvedLLM:
    provider_id: str
    provider_name: str
    api_key: str
    base_url: str
    model: str
    vision_model: str
    default_headers: Dict[str, str]
    notes: str = ""


def provider_allows_empty_key(provider_id: str) -> bool:
    return provider_id in {"ollama", "openai_compatible"}


def resolve_llm(
    provider: str,
    api_key: str,
    base_url: str = "",
    model: str = "",
    vision_model: str = "",
) -> ResolvedLLM:
    preset = get_provider(provider)
    if preset is None:
        preset = PROVIDERS["openai_compatible"]
        pid = normalize_provider(provider) or "custom"
        pname = f"Custom ({provider})" if provider else preset.name
    else:
        pid = preset.id
        pname = preset.name

    def _clean(v: str) -> str:
        v = (v or "").strip()
        if not v or v.startswith("your_"):
            return ""
        return v

    url = _clean(base_url) or preset.base_url
    mdl = _clean(model) or preset.default_model
    vis = _clean(vision_model) or preset.default_vision_model or mdl
    key = _clean(api_key)
    if not key and provider_allows_empty_key(pid):
        key = pid

    return ResolvedLLM(
        provider_id=pid,
        provider_name=pname,
        api_key=key,
        base_url=url.rstrip("/"),
        model=mdl,
        vision_model=vis,
        default_headers=dict(preset.default_headers),
        notes=preset.notes,
    )
