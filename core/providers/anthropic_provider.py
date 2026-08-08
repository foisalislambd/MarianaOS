"""Anthropic Claude via official anthropic SDK.

Docs: https://docs.anthropic.com/en/api/messages
      https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview
"""

from __future__ import annotations

import base64
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from core.llm_types import LLMTurn, ToolCallRequest, openai_tools_to_declarations
from core.providers.base import BaseLLMProvider
from utils.logging import get_logger

log = get_logger("mros.llm.anthropic")


class AnthropicProvider(BaseLLMProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        vision_model: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        provider_id: str = "anthropic",
    ) -> None:
        import anthropic

        self.provider_id = provider_id
        self.model = model
        self.vision_model = vision_model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    def _split_system(
        self, messages: List[Dict[str, Any]]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        system_parts: List[str] = []
        out: List[Dict[str, Any]] = []
        for m in messages:
            if m.get("role") == "system":
                system_parts.append(str(m.get("content") or ""))
                continue
            role = m.get("role")
            if role == "assistant":
                content: Any = []
                if m.get("content"):
                    content.append({"type": "text", "text": str(m["content"])})
                for tc in m.get("tool_calls") or []:
                    fn = tc.get("function") or {}
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    content.append(
                        {
                            "type": "tool_use",
                            "id": tc.get("id"),
                            "name": fn.get("name"),
                            "input": args if isinstance(args, dict) else {},
                        }
                    )
                if not content:
                    content = ""
                out.append({"role": "assistant", "content": content})
            elif role == "tool":
                # Anthropic wants tool_result blocks inside a user message
                if out and out[-1].get("role") == "user" and isinstance(out[-1].get("content"), list):
                    out[-1]["content"].append(
                        {
                            "type": "tool_result",
                            "tool_use_id": m.get("tool_call_id"),
                            "content": str(m.get("content") or ""),
                        }
                    )
                else:
                    out.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": m.get("tool_call_id"),
                                    "content": str(m.get("content") or ""),
                                }
                            ],
                        }
                    )
            elif role == "user":
                out.append({"role": "user", "content": str(m.get("content") or "")})
        return "\n\n".join(system_parts).strip(), out

    async def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> LLMTurn:
        system, anth_messages = self._split_system(messages)

        anth_tools = []
        for d in openai_tools_to_declarations(tools or []):
            anth_tools.append(
                {
                    "name": d["name"],
                    "description": d["description"],
                    "input_schema": d["parameters"],
                }
            )

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": anth_messages,
        }
        if system:
            kwargs["system"] = system
        if anth_tools:
            kwargs["tools"] = anth_tools
            if tool_choice == "none":
                kwargs["tool_choice"] = {"type": "none"}
            elif tool_choice == "required":
                kwargs["tool_choice"] = {"type": "any"}
            else:
                kwargs["tool_choice"] = {"type": "auto"}

        resp = await self._client.messages.create(**kwargs)

        text_bits: List[str] = []
        tool_calls: List[ToolCallRequest] = []
        openai_tool_calls: List[Dict[str, Any]] = []

        for block in resp.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text_bits.append(block.text)
            elif btype == "tool_use":
                args = dict(block.input or {})
                tool_calls.append(
                    ToolCallRequest(id=block.id, name=block.name, arguments=args)
                )
                openai_tool_calls.append(
                    {
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(args, ensure_ascii=False),
                        },
                    }
                )

        text = "\n".join(text_bits).strip()
        assistant: Dict[str, Any] = {"role": "assistant", "content": text or None}
        if openai_tool_calls:
            assistant["tool_calls"] = openai_tool_calls
            assistant["_tool_names"] = {tc.id: tc.name for tc in tool_calls}

        return LLMTurn(
            text=text,
            tool_calls=tool_calls,
            assistant_message=assistant,
        )

    async def analyze_image(
        self,
        image_data_url: str,
        prompt: str,
        model: Optional[str] = None,
    ) -> str:
        mime, raw = _parse_data_url(image_data_url)
        b64 = base64.standard_b64encode(raw).decode("ascii")
        resp = await self._client.messages.create(
            model=model or self.vision_model,
            max_tokens=min(self.max_tokens, 2000),
            temperature=0.1,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        texts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
        return "\n".join(texts).strip()

    async def list_models(self) -> List[str]:
        # Anthropic list endpoint
        try:
            page = await self._client.models.list(limit=100)
            ids = [m.id for m in page.data if getattr(m, "id", None)]
            return sorted(ids, key=str.lower)
        except Exception as e:
            log.warning("Anthropic models.list failed: %s", e)
            return [self.model, self.vision_model]


def _parse_data_url(data_url: str) -> tuple[str, bytes]:
    m = re.match(r"^data:([^;]+);base64,(.+)$", data_url, re.DOTALL)
    if m:
        mime = m.group(1).strip().lower()
        if mime == "image/jpg":
            mime = "image/jpeg"
        return mime, base64.standard_b64decode(m.group(2))
    return "image/png", base64.standard_b64decode(data_url)
