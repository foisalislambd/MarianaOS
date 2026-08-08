"""OpenAI-compatible LLM client (works with Gemini, Claude, Groq, OpenRouter, …)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from config.providers import ResolvedLLM
from utils.logging import get_logger

log = get_logger("mros.llm")


class LLMClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        vision_model: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        default_headers: Optional[Dict[str, str]] = None,
        provider_id: str = "",
    ) -> None:
        self.model = model
        self.vision_model = vision_model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.provider_id = provider_id
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers=default_headers or None,
        )

    @classmethod
    def from_resolved(
        cls,
        resolved: ResolvedLLM,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> "LLMClient":
        return cls(
            api_key=resolved.api_key,
            base_url=resolved.base_url,
            model=resolved.model,
            vision_model=resolved.vision_model,
            max_tokens=max_tokens,
            temperature=temperature,
            default_headers=resolved.default_headers,
            provider_id=resolved.provider_id,
        )

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        model: Optional[str] = None,
    ) -> Any:
        kwargs: Dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        log.debug(
            "LLM request provider=%s model=%s tools=%s",
            self.provider_id or "?",
            kwargs["model"],
            bool(tools),
        )
        try:
            return await self.client.chat.completions.create(**kwargs)
        except Exception as e:
            # Some newer OpenAI models reject max_tokens — retry with max_completion_tokens
            err = str(e).lower()
            if "max_tokens" in err and "max_completion_tokens" in err:
                kwargs.pop("max_tokens", None)
                kwargs["max_completion_tokens"] = self.max_tokens
                return await self.client.chat.completions.create(**kwargs)
            raise

    async def analyze_image(
        self,
        image_data_url: str,
        prompt: str,
        model: Optional[str] = None,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": model or self.vision_model,
            "max_tokens": min(self.max_tokens, 2000),
            "temperature": 0.1,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_data_url, "detail": "high"},
                        },
                    ],
                }
            ],
        }
        try:
            resp = await self.client.chat.completions.create(**payload)
        except Exception as e:
            err = str(e).lower()
            if "max_tokens" in err and "max_completion_tokens" in err:
                payload.pop("max_tokens", None)
                payload["max_completion_tokens"] = min(self.max_tokens, 2000)
                resp = await self.client.chat.completions.create(**payload)
            else:
                raise
        return (resp.choices[0].message.content or "").strip()
