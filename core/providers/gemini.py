"""Google Gemini via official google-genai SDK (AI Studio / Gemini API).

Docs:
  https://ai.google.dev/gemini-api/docs/function-calling
  https://ai.google.dev/gemini-api/docs/thought-signatures
  https://googleapis.github.io/python-genai/

Thought signatures are preserved by appending `response.candidates[0].content`
verbatim into history (never rebuild functionCall parts manually).
"""

from __future__ import annotations

import base64
import json
import re
import uuid
from typing import Any, Dict, List, Optional

from core.llm_types import LLMTurn, ToolCallRequest, openai_tools_to_declarations
from core.providers.base import BaseLLMProvider
from utils.logging import get_logger

log = get_logger("mros.llm.gemini")


class GeminiProvider(BaseLLMProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        vision_model: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        provider_id: str = "gemini",
    ) -> None:
        from google import genai

        self.provider_id = provider_id
        self.model = model
        self.vision_model = vision_model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = genai.Client(api_key=api_key)

    def _config(
        self,
        tools: Optional[List[Dict[str, Any]]],
        system: str = "",
    ):
        from google.genai import types

        decls = []
        for d in openai_tools_to_declarations(tools or []):
            decls.append(
                types.FunctionDeclaration(
                    name=d["name"],
                    description=d["description"],
                    parameters_json_schema=d["parameters"],
                )
            )

        kwargs: Dict[str, Any] = {
            "temperature": self.temperature,
            "max_output_tokens": self.max_tokens,
            "automatic_function_calling": types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        }
        if system.strip():
            kwargs["system_instruction"] = system.strip()
        if decls:
            kwargs["tools"] = [types.Tool(function_declarations=decls)]

        return types.GenerateContentConfig(**kwargs)

    def _messages_to_contents(
        self, messages: List[Dict[str, Any]]
    ) -> tuple[str, List[Any]]:
        from google.genai import types

        contents: List[Any] = []
        system_chunks: List[str] = []

        i = 0
        while i < len(messages):
            m = messages[i]
            role = m.get("role")

            if role == "system":
                system_chunks.append(str(m.get("content") or ""))
                i += 1
                continue

            if role == "user":
                text = str(m.get("content") or "")
                contents.append(
                    types.Content(role="user", parts=[types.Part.from_text(text=text)])
                )
                i += 1
                continue

            if role == "assistant":
                native = m.get("_native")
                if native is not None:
                    contents.append(native)
                else:
                    parts = []
                    if m.get("content"):
                        parts.append(types.Part.from_text(text=str(m["content"])))
                    for tc in m.get("tool_calls") or []:
                        fn = tc.get("function") or {}
                        args_raw = fn.get("arguments") or "{}"
                        try:
                            args = json.loads(args_raw)
                        except json.JSONDecodeError:
                            args = {}
                        parts.append(
                            types.Part.from_function_call(
                                name=fn.get("name") or "unknown",
                                args=args if isinstance(args, dict) else {},
                            )
                        )
                    if parts:
                        contents.append(types.Content(role="model", parts=parts))
                i += 1
                continue

            if role == "tool":
                fr_parts = []
                while i < len(messages) and messages[i].get("role") == "tool":
                    tm = messages[i]
                    name = tm.get("name") or _tool_name_from_history(messages, tm)
                    raw = tm.get("content") or "{}"
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        payload = {"output": raw}
                    if not isinstance(payload, dict):
                        payload = {"output": payload}
                    fr_parts.append(
                        types.Part.from_function_response(name=name, response=payload)
                    )
                    i += 1
                contents.append(types.Content(role="user", parts=fr_parts))
                continue

            i += 1

        system = "\n\n".join(system_chunks).strip()
        return system, contents

    async def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> LLMTurn:
        system, contents = self._messages_to_contents(messages)
        if not contents:
            from google.genai import types

            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text="Hello")],
                )
            ]
        config = self._config(tools, system=system)

        response = await self._client.aio.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )

        candidate = (response.candidates or [None])[0]
        if candidate is None or candidate.content is None:
            text = (response.text or "").strip()
            return LLMTurn(
                text=text or "Done.",
                tool_calls=[],
                assistant_message={"role": "assistant", "content": text},
            )

        model_content = candidate.content
        text_bits: List[str] = []
        tool_calls: List[ToolCallRequest] = []
        openai_tool_calls: List[Dict[str, Any]] = []

        for part in model_content.parts or []:
            if getattr(part, "text", None):
                text_bits.append(part.text)
            fc = getattr(part, "function_call", None)
            if fc:
                name = fc.name or "unknown"
                args = _to_plain_dict(getattr(fc, "args", None))
                call_id = f"call_{uuid.uuid4().hex[:24]}"
                tool_calls.append(
                    ToolCallRequest(id=call_id, name=name, arguments=args)
                )
                openai_tool_calls.append(
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": json.dumps(args, ensure_ascii=False),
                        },
                    }
                )

        text = "\n".join(text_bits).strip()
        assistant: Dict[str, Any] = {
            "role": "assistant",
            "content": text or None,
            "_native": model_content,
        }
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
        from google.genai import types

        mime, raw = _parse_data_url(image_data_url)
        response = await self._client.aio.models.generate_content(
            model=model or self.vision_model,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=raw, mime_type=mime),
                    ],
                ),
            ],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=min(self.max_tokens, 2000),
            ),
        )
        return (response.text or "").strip()

    async def list_models(self) -> List[str]:
        ids: List[str] = []
        # aio.models.list() returns AsyncPager — do not await it
        pager = self._client.aio.models.list()
        async for m in pager:
            name = getattr(m, "name", None) or ""
            mid = name.split("/")[-1] if name else ""
            if mid:
                ids.append(mid)
        return sorted(set(ids), key=str.lower)


def _tool_name_from_history(messages: List[Dict[str, Any]], tool_msg: Dict[str, Any]) -> str:
    if tool_msg.get("name"):
        return str(tool_msg["name"])
    call_id = tool_msg.get("tool_call_id")
    for m in reversed(messages):
        if m.get("role") != "assistant":
            continue
        names = m.get("_tool_names") or {}
        if call_id and call_id in names:
            return str(names[call_id])
        for tc in m.get("tool_calls") or []:
            if tc.get("id") == call_id:
                return str((tc.get("function") or {}).get("name") or "tool")
    return "tool"


def _parse_data_url(data_url: str) -> tuple[str, bytes]:
    m = re.match(r"^data:([^;]+);base64,(.+)$", data_url, re.DOTALL)
    if m:
        mime = m.group(1).strip().lower()
        if mime == "image/jpg":
            mime = "image/jpeg"
        return mime, base64.standard_b64decode(m.group(2))
    return "image/png", base64.standard_b64decode(data_url)


def _to_plain_dict(value: Any) -> Dict[str, Any]:
    """Convert Gemini MapComposite / nested structures to plain JSON-safe dicts."""
    if value is None:
        return {}
    try:
        return json.loads(json.dumps(value, default=str))
    except Exception:
        try:
            return dict(value)
        except Exception:
            return {"value": str(value)}
