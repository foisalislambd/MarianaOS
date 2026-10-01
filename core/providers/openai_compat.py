"""OpenAI-compatible Chat Completions via httpx (OpenRouter, OpenAI, Groq, …)."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set

import httpx

from core.llm_types import LLMTurn, ToolCallRequest
from core.providers.base import BaseLLMProvider
from utils.logging import get_logger

log = get_logger("marianaos.llm.openai_compat")

_KEYLESS: Set[str] = {"", "none", "no-key", "nokey", "ollama", "lm-studio", "lmstudio"}


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
        self.base_url = base_url.rstrip("/")
        self.api_key = (api_key or "").strip()
        self.default_headers = dict(default_headers or {})

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            **self.default_headers,
        }
        if self.api_key and self.api_key.lower() not in _KEYLESS:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=self._headers(), json=body)
            if resp.status_code >= 400:
                detail = resp.text[:800]
                raise RuntimeError(f"LLM HTTP {resp.status_code}: {detail}")
            return resp.json()

    async def _get(self, path: str) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url, headers=self._headers())
            if resp.status_code >= 400:
                detail = resp.text[:800]
                raise RuntimeError(f"LLM HTTP {resp.status_code}: {detail}")
            return resp.json()

    async def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> LLMTurn:
        clean = [_strip_private(m) for m in messages]
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": clean,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = tool_choice

        try:
            data = await self._post("/chat/completions", body)
        except RuntimeError as e:
            err = str(e).lower()
            if "max_tokens" in err and "max_completion_tokens" in err:
                body.pop("max_tokens", None)
                body["max_completion_tokens"] = self.max_tokens
                data = await self._post("/chat/completions", body)
            else:
                raise

        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        tool_calls_raw = msg.get("tool_calls") or []
        tool_calls: List[ToolCallRequest] = []
        assistant: Dict[str, Any] = {
            "role": "assistant",
            "content": msg.get("content"),
        }

        reasoning = msg.get("reasoning_content")
        if reasoning:
            assistant["reasoning_content"] = reasoning

        if tool_calls_raw:
            serialized = []
            for tc in tool_calls_raw:
                fn = tc.get("function") or {}
                try:
                    parsed = json.loads(fn.get("arguments") or "{}")
                    args = parsed if isinstance(parsed, dict) else {}
                except json.JSONDecodeError:
                    args = {}
                tc_id = tc.get("id") or f"call_{len(tool_calls)}"
                name = fn.get("name") or ""
                tool_calls.append(ToolCallRequest(id=tc_id, name=name, arguments=args))
                serialized.append(
                    {
                        "id": tc_id,
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": fn.get("arguments") or "{}",
                        },
                    }
                )
            assistant["tool_calls"] = serialized

        return LLMTurn(
            text=(msg.get("content") or "").strip() if isinstance(msg.get("content"), str) else "",
            tool_calls=tool_calls,
            assistant_message=assistant,
        )

    async def analyze_image(
        self,
        image_data_url: str,
        prompt: str,
        model: Optional[str] = None,
    ) -> str:
        body: Dict[str, Any] = {
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
        data = await self._post("/chat/completions", body)
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        content = msg.get("content") or ""
        return content.strip() if isinstance(content, str) else str(content)

    async def list_models(self) -> List[str]:
        data = await self._get("/models")
        rows = data.get("data") or []
        ids = [str(m["id"]) for m in rows if isinstance(m, dict) and m.get("id")]
        return sorted(ids, key=str.lower)


def _strip_private(message: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in message.items() if not k.startswith("_")}
