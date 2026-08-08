"""LLM provider factory — pick native SDK per provider docs."""

from __future__ import annotations

from typing import Set

from config.providers import ResolvedLLM
from core.providers.base import BaseLLMProvider
from core.providers.openai_compat import OpenAICompatProvider
from utils.logging import get_logger

log = get_logger("marianaos.llm.factory")

# Providers that speak real OpenAI Chat Completions (per their own docs).
OPENAI_COMPAT: Set[str] = {
    "openai",
    "openrouter",
    "groq",
    "deepseek",
    "mistral",
    "xai",
    "together",
    "fireworks",
    "ollama",
    "lmstudio",
    "openai_compatible",
    "custom",
}


def create_llm_provider(
    resolved: ResolvedLLM,
    *,
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> BaseLLMProvider:
    pid = resolved.provider_id

    if pid == "gemini":
        from core.providers.gemini import GeminiProvider

        log.info("Using native Google GenAI SDK for Gemini")
        return GeminiProvider(
            api_key=resolved.api_key,
            model=resolved.model,
            vision_model=resolved.vision_model,
            max_tokens=max_tokens,
            temperature=temperature,
            provider_id=pid,
        )

    if pid == "anthropic":
        from core.providers.anthropic_provider import AnthropicProvider

        log.info("Using native Anthropic SDK for Claude")
        return AnthropicProvider(
            api_key=resolved.api_key,
            model=resolved.model,
            vision_model=resolved.vision_model,
            max_tokens=max_tokens,
            temperature=temperature,
            provider_id=pid,
        )

    if pid in OPENAI_COMPAT:
        log.info(
            "Using OpenAI-compatible client for provider=%s base=%s",
            pid,
            resolved.base_url,
        )
        return OpenAICompatProvider(
            provider_id=pid,
            api_key=resolved.api_key,
            base_url=resolved.base_url,
            model=resolved.model,
            vision_model=resolved.vision_model,
            max_tokens=max_tokens,
            temperature=temperature,
            default_headers=resolved.default_headers,
        )

    # Unknown id → still try OpenAI-compatible with the resolved base URL
    log.warning("Unknown provider %s — falling back to OpenAI-compatible API", pid)
    return OpenAICompatProvider(
        provider_id=pid,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        model=resolved.model,
        vision_model=resolved.vision_model,
        max_tokens=max_tokens,
        temperature=temperature,
        default_headers=resolved.default_headers,
    )
