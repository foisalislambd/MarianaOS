"""OpenAI Chat Completions compatible providers.

Used for: OpenAI, OpenRouter, Groq, DeepSeek, Mistral, xAI, Together,
Fireworks, Ollama, LM Studio, OpenCode Zen, and other OpenAI-compatible gateways.

Docs: https://platform.openai.com/docs/api-reference/chat
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set

import httpx
from openai import AsyncOpenAI

from core.llm_types import LLMTurn, ToolCallRequest
from core.providers.base import BaseLLMProvider
from utils.logging import get_logger

log = get_logger("marianaos.llm.openai_compat")

# Placeholder keys that must NOT be sent as Authorization (OpenCode free tier
# returns 401 "Invalid API key" if Bearer opencode is present).
_KEYLESS_PLACEHOLDERS: Set[str] = {
    "",
    "opencode",
    "none",
    "no-key",
    "nokey",
    "ollama",
    "lm-studio",
    "lmstudio",
}


def _should_strip_auth(api_key: str) -> bool:
    return (api_key or "").strip().lower() in _KEYLESS_PLACEHOLDERS


def _make_http_client(*, strip_auth: bool) -> httpx.AsyncClient:
    if not strip_auth:
        return httpx.AsyncClient()

    async def _strip_placeholder_auth(request: httpx.Request) -> None:
        auth = request.headers.get("Authorization") or request.headers.get("authorization")
        if not auth:
            return
        token = auth.split(" ", 1)[-1].strip().lower()
        if token in _KEYLESS_PLACEHOLDERS:
            request.headers.pop("Authorization", None)
            # httpx may store lower-case too depending on version
            try:
                del request.headers["authorization"]
            except Exception:
                pass

    return httpx.AsyncClient(event_hooks={"request": [_strip_placeholder_auth]})


class OpenAICompatProvider(BaseLLMProvider):
    def __init__(
        self,
        *,
        provider_id: str,
        api_key: str,
        base_url: str,
        model: str,
        vision_model: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        default_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.provider_id = provider_id
        self.model = model
        self.vision_model = vision_model
        self.max_tokens = max_tokens
        self.temperature = temperature
        key = (api_key or "").strip() or "opencode"
        strip_auth = provider_id == "opencode" and _should_strip_auth(key)
        self._http = _make_http_client(strip_auth=strip_auth)
        self.client = AsyncOpenAI(
            api_key=key,
            base_url=base_url,
            default_headers=default_headers or None,
            http_client=self._http,
        )

    async def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> LLMTurn:
        # Strip provider-private fields before sending to OpenAI-compatible APIs
        clean_messages = [_strip_private(m) for m in messages]

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": clean_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        try:
            resp = await self.client.chat.completions.create(**kwargs)
        except Exception as e:
            err = str(e).lower()
            if "max_tokens" in err and "max_completion_tokens" in err:
                kwargs.pop("max_tokens", None)
                kwargs["max_completion_tokens"] = self.max_tokens
                resp = await self.client.chat.completions.create(**kwargs)
            else:
                raise

        msg = resp.choices[0].message
        tool_calls_raw = msg.tool_calls or []
        tool_calls: List[ToolCallRequest] = []
        assistant: Dict[str, Any] = {
            "role": "assistant",
            "content": msg.content,
        }

        # OpenCode / DeepSeek thinking models require reasoning_content echoed back
        reasoning = getattr(msg, "reasoning_content", None)
        if reasoning is None:
            extra = getattr(msg, "model_extra", None) or {}
            if isinstance(extra, dict):
                reasoning = extra.get("reasoning_content")
        if reasoning:
            assistant["reasoning_content"] = reasoning

        if tool_calls_raw:
            serialized = []
            for tc in tool_calls_raw:
                args: Dict[str, Any]
                try:
                    parsed = json.loads(tc.function.arguments or "{}")
                    args = parsed if isinstance(parsed, dict) else {}
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(
                    ToolCallRequest(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=args,
                    )
                )
                serialized.append(
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}",
                        },
                    }
                )
            assistant["tool_calls"] = serialized

        return LLMTurn(
            text=(msg.content or "").strip(),
            tool_calls=tool_calls,
            assistant_message=assistant,
        )

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

    async def list_models(self) -> List[str]:
        page = await self.client.models.list()
        rows = getattr(page, "data", None)
        if rows is None:
            # Some SDK versions are iterable; prefer .data when present
            try:
                rows = list(page)
            except Exception:
                rows = []
        ids: List[str] = []
        for m in rows:
            mid = getattr(m, "id", None)
            if mid:
                ids.append(str(mid))
        return sorted(ids, key=str.lower)


def _strip_private(message: Dict[str, Any]) -> Dict[str, Any]:
    """Drop provider-private keys (_native, _tool_names, …) before OpenAI wire format."""
    out = {k: v for k, v in message.items() if not k.startswith("_")}
    # OpenAI tool role: name is optional; keep it when present
    return out
