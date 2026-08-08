"""Unified LLM turn / tool-call types (provider-agnostic)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolCallRequest:
    """One tool/function call requested by the model."""

    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class LLMTurn:
    """One model response in the agent loop."""

    text: str
    tool_calls: List[ToolCallRequest] = field(default_factory=list)
    # Message dict to append to OpenAI-style history (may include `_native` blob)
    assistant_message: Dict[str, Any] = field(default_factory=dict)


def openai_tools_to_declarations(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize OpenAI tool schemas to {name, description, parameters}."""
    out: List[Dict[str, Any]] = []
    for t in tools or []:
        fn = t.get("function") if isinstance(t, dict) else None
        if not fn and isinstance(t, dict) and t.get("name"):
            fn = t
        if not fn:
            continue
        out.append(
            {
                "name": fn["name"],
                "description": fn.get("description") or "",
                "parameters": fn.get("parameters")
                or {"type": "object", "properties": {}},
            }
        )
    return out
