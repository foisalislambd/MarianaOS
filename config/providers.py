"""Popular LLM provider presets (OpenAI-compatible chat completions)."""

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
    # Extra HTTP headers some gateways expect
    default_headers: Dict[str, str] = field(default_factory=dict)
    notes: str = ""
    # Some APIs prefer max_completion_tokens; we still send max_tokens by default
    aliases: tuple[str, ...] = ()


PROVIDERS: Dict[str, ProviderPreset] = {}


def _add(p: ProviderPreset) -> None:
    PROVIDERS[p.id] = p
    for a in p.aliases:
        PROVIDERS[a] = p


_add(
    ProviderPreset(
        id="openai",
        name="OpenAI",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o",
        default_vision_model="gpt-4o",
        notes="Get key: https://platform.openai.com/api-keys",
    )
)
_add(
    ProviderPreset(
        id="gemini",
        name="Google AI Studio (Gemini)",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        default_model="gemini-2.5-flash",
        default_vision_model="gemini-2.5-flash",
        aliases=("google", "aistudio", "google-ai-studio", "google_ai_studio"),
        notes="Native google-genai SDK. Key: https://aistudio.google.com/apikey",
    )
)
_add(
    ProviderPreset(
        id="anthropic",
        name="Anthropic (Claude)",
        base_url="https://api.anthropic.com",
        default_model="claude-sonnet-4-5",
        default_vision_model="claude-sonnet-4-5",
        aliases=("claude",),
        notes="Native anthropic SDK. Key: https://console.anthropic.com/",
    )
)
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
        notes="Get key: https://openrouter.ai/keys — access many models via one key",
    )
)
_add(
    ProviderPreset(
        id="groq",
        name="Groq",
        base_url="https://api.groq.com/openai/v1",
        default_model="llama-3.3-70b-versatile",
        default_vision_model="meta-llama/llama-4-scout-17b-16e-instruct",
        notes="Get key: https://console.groq.com/keys — use a vision-capable model for screenshots",
    )
)
_add(
    ProviderPreset(
        id="deepseek",
        name="DeepSeek",
        base_url="https://api.deepseek.com",
        default_model="deepseek-chat",
        default_vision_model="deepseek-chat",
        notes="Get key: https://platform.deepseek.com/ — vision may be limited; use OpenRouter for vision if needed",
    )
)
_add(
    ProviderPreset(
        id="mistral",
        name="Mistral AI",
        base_url="https://api.mistral.ai/v1",
        default_model="mistral-large-latest",
        default_vision_model="pixtral-large-latest",
        notes="Get key: https://console.mistral.ai/",
    )
)
_add(
    ProviderPreset(
        id="xai",
        name="xAI (Grok)",
        base_url="https://api.x.ai/v1",
        default_model="grok-2-latest",
        default_vision_model="grok-2-vision-latest",
        aliases=("grok",),
        notes="Get key: https://console.x.ai/",
    )
)
_add(
    ProviderPreset(
        id="together",
        name="Together AI",
        base_url="https://api.together.xyz/v1",
        default_model="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        default_vision_model="meta-llama/Llama-Vision-Free",
        notes="Get key: https://api.together.xyz/",
    )
)
_add(
    ProviderPreset(
        id="fireworks",
        name="Fireworks AI",
        base_url="https://api.fireworks.ai/inference/v1",
        default_model="accounts/fireworks/models/llama-v3p3-70b-instruct",
        default_vision_model="accounts/fireworks/models/llama-v3p2-11b-vision-instruct",
        notes="Get key: https://fireworks.ai/",
    )
)
_add(
    ProviderPreset(
        id="openai_compatible",
        name="Custom OpenAI-compatible",
        base_url="http://127.0.0.1:1234/v1",
        default_model="local-model",
        default_vision_model="local-model",
        aliases=("custom", "compatible"),
        notes="Set LLM_BASE_URL + LLM_MODEL yourself (LM Studio, vLLM, etc.)",
    )
)
_add(
    ProviderPreset(
        id="opencode",
        name="OpenCode Zen (free tier)",
        base_url="https://opencode.ai/zen/v1",
        default_model="deepseek-v4-flash-free",
        default_vision_model="deepseek-v4-flash-free",
        aliases=("opencode_zen", "opencode-zen", "oc", "zen"),
        default_headers={
            "User-Agent": "opencode",
            "x-opencode-client": "cli",
            "x-opencode-project": "marianaos",
            "HTTP-Referer": "https://github.com/marianaos-agent",
            "X-Title": "MarianaOS Agent",
        },
        notes=(
            "Free, no API key needed for *-free models + big-pickle. "
            "Set LLM_API_KEY=opencode (or leave empty). "
            "Live catalog: https://opencode.ai/zen/v1/models — free ids end with -free "
            "(plus big-pickle). Premium models need a real OpenCode key."
        ),
    )
)
_add(
    ProviderPreset(
        id="ollama",
        name="Ollama (local)",
        base_url="http://127.0.0.1:11434/v1",
        default_model="llama3.2",
        default_vision_model="llava",
        notes="Install Ollama, pull a model. API key can be anything (e.g. ollama).",
    )
)
_add(
    ProviderPreset(
        id="lmstudio",
        name="LM Studio (local)",
        base_url="http://127.0.0.1:1234/v1",
        default_model="local-model",
        default_vision_model="local-model",
        notes="Enable local server in LM Studio. API key can be anything (e.g. lm-studio).",
    )
)


def normalize_provider(name: str) -> str:
    key = (name or "openai").strip().lower().replace(" ", "_").replace("-", "_")
    # map common variants after replace
    aliases = {
        "google_ai_studio": "gemini",
        "ai_studio": "gemini",
        "aistudio": "gemini",
        "google": "gemini",
        "claude": "anthropic",
        "grok": "xai",
        "custom": "openai_compatible",
        "compatible": "openai_compatible",
        "opencode_zen": "opencode",
        "opencodezen": "opencode",
        "oc": "opencode",
        "zen": "opencode",
    }
    key = aliases.get(key, key)
    if key in PROVIDERS:
        return PROVIDERS[key].id
    return key


def get_provider(name: str) -> Optional[ProviderPreset]:
    key = normalize_provider(name)
    return PROVIDERS.get(key)


def list_providers() -> List[ProviderPreset]:
    seen = set()
    out: List[ProviderPreset] = []
    for p in PROVIDERS.values():
        if p.id in seen:
            continue
        seen.add(p.id)
        out.append(p)
    return sorted(out, key=lambda x: x.name.lower())


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


# Models known to work on OpenCode Zen without an API key (rotates upstream).
# Anything ending in "-free" is also treated as free.
OPENCODE_FREE_MODELS: tuple[str, ...] = (
    "big-pickle",
    "deepseek-v4-flash-free",
    "mimo-v2.5-free",
    "nemotron-3-ultra-free",
    "north-mini-code-free",
    "longcat-2.0-free",
    "ling-3.0-flash-free",
    "ling-3.0-tiny-free",
    "laguna-s-2.1-free",
)


def is_opencode_free_model(model_id: str) -> bool:
    mid = (model_id or "").strip()
    if not mid:
        return False
    if mid.endswith("-free"):
        return True
    return mid in OPENCODE_FREE_MODELS


def provider_allows_empty_key(provider_id: str) -> bool:
    return provider_id in {"opencode", "ollama", "lmstudio"}


def resolve_llm(
    provider: str,
    api_key: str,
    base_url: str = "",
    model: str = "",
    vision_model: str = "",
) -> ResolvedLLM:
    """Apply provider presets; explicit env values always win when non-empty."""
    preset = get_provider(provider)
    if preset is None:
        # Unknown provider → treat as custom OpenAI-compatible
        preset = PROVIDERS["openai_compatible"]
        pid = normalize_provider(provider) or "custom"
        pname = f"Custom ({provider})" if provider else preset.name
    else:
        pid = preset.id
        pname = preset.name

    # Treat placeholder / empty overrides as unset
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
        # OpenAI SDK requires a non-empty string; upstream OpenCode free tier ignores it
        key = "opencode" if pid == "opencode" else pid

    return ResolvedLLM(
        provider_id=pid,
        provider_name=pname,
        api_key=key,
        base_url=url,
        model=mdl,
        vision_model=vis,
        default_headers=dict(preset.default_headers),
        notes=preset.notes,
    )
