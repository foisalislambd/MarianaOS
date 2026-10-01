"""LLM provider factory — httpx OpenAI-compatible clients only."""

from __future__ import annotations

from config.providers import ResolvedLLM
from core.providers.base import BaseLLMProvider
from core.providers.openai_compat import OpenAICompatProvider
from utils.logging import get_logger

log = get_logger("marianaos.llm.factory")


def create_llm_provider(
    resolved: ResolvedLLM,
    *,
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> BaseLLMProvider:
    log.info(
        "Using httpx OpenAI-compatible client provider=%s base=%s",
        resolved.provider_id,
        resolved.base_url,
    )
    return OpenAICompatProvider(
        provider_id=resolved.provider_id,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        model=resolved.model,
        vision_model=resolved.vision_model,
        max_tokens=max_tokens,
        temperature=temperature,
        default_headers=resolved.default_headers,
    )
