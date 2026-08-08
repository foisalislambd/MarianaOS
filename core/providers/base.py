"""Abstract LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from core.llm_types import LLMTurn


class BaseLLMProvider(ABC):
    provider_id: str = ""
    model: str = ""
    vision_model: str = ""

    @abstractmethod
    async def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> LLMTurn:
        """Run one chat completion turn (may include tool calls)."""

    @abstractmethod
    async def analyze_image(
        self,
        image_data_url: str,
        prompt: str,
        model: Optional[str] = None,
    ) -> str:
        """Vision: analyze an image (data URL) with a text prompt."""

    async def list_models(self) -> List[str]:
        """Optional: return model ids for this provider."""
        return []
