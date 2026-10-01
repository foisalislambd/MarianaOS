"""Unified LLM turn / tool-call types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class LLMTurn:
    text: str
    tool_calls: List[ToolCallRequest] = field(default_factory=list)
    assistant_message: Dict[str, Any] = field(default_factory=dict)
