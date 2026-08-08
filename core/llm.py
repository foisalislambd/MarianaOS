"""LLM facade — creates the correct native/compatible provider."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config.providers import ResolvedLLM
from core.llm_types import LLMTurn
from core.providers.base import BaseLLMProvider
from core.providers.factory import create_llm_provider


class LLMClient:
    """Thin wrapper so the rest of the app talks to one interface."""

    def __init__(self, provider: BaseLLMProvider) -> None:
        self.provider = provider
        self.provider_id = provider.provider_id
        self.model = provider.model
        self.vision_model = provider.vision_model

    @classmethod
    def from_resolved(
        cls,
        resolved: ResolvedLLM,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> "LLMClient":
        return cls(
            create_llm_provider(
                resolved,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        )

    async def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> LLMTurn:
        return await self.provider.complete(
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
        )

    async def analyze_image(
        self,
        image_data_url: str,
        prompt: str,
        model: Optional[str] = None,
    ) -> str:
        return await self.provider.analyze_image(
            image_data_url=image_data_url,
            prompt=prompt,
            model=model,
        )

    async def list_models(self) -> List[str]:
        return await self.provider.list_models()
