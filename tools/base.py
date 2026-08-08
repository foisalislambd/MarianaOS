"""Tool base classes and registry."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolResult:
    success: bool
    output: str
    data: Dict[str, Any] = field(default_factory=dict)
    # Optional media to send back to the user (e.g. screenshot path)
    media_paths: List[str] = field(default_factory=list)

    def to_llm(self) -> str:
        payload: Dict[str, Any] = {
            "success": self.success,
            "output": self.output,
        }
        if self.data:
            payload["data"] = self.data
        if self.media_paths:
            payload["media_paths"] = self.media_paths
        return json.dumps(payload, ensure_ascii=False, default=str)


@dataclass
class ToolParam:
    name: str
    type: str
    description: str
    required: bool = True
    enum: Optional[List[str]] = None
    items_type: Optional[str] = None  # for type=array


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    parameters: List[ToolParam] = []
    # If True, agent may ask user confirmation when REQUIRE_CONFIRMATION is on
    destructive: bool = False

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        raise NotImplementedError

    def openai_schema(self) -> Dict[str, Any]:
        props: Dict[str, Any] = {}
        required: List[str] = []
        for p in self.parameters:
            prop: Dict[str, Any] = {"type": p.type, "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            if p.type == "array":
                prop["items"] = {"type": p.items_type or "string"}
            props[p.name] = prop
            if p.required:
                required.append(p.name)
        if self.destructive:
            props["confirm"] = {
                "type": "boolean",
                "description": (
                    "Must be true to execute this destructive action after the user confirms."
                ),
            }
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if not tool.name:
            raise ValueError(f"Tool {tool!r} has no name")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list(self) -> List[BaseTool]:
        return list(self._tools.values())

    def openai_tools(self) -> List[Dict[str, Any]]:
        return [t.openai_schema() for t in self._tools.values()]

    async def call(
        self,
        name: str,
        arguments: Dict[str, Any],
        require_confirmation: bool = False,
    ) -> ToolResult:
        tool = self.get(name)
        if tool is None:
            return ToolResult(success=False, output=f"Unknown tool: {name}")

        args = dict(arguments or {})
        confirmed = bool(args.pop("confirm", False))

        if tool.destructive and require_confirmation and not confirmed:
            return ToolResult(
                success=False,
                output=(
                    f"Blocked: '{name}' is destructive and confirmation is required. "
                    "Ask the user to confirm, then call again with the same arguments "
                    "plus confirm=true."
                ),
            )

        # Coerce common JSON number quirks (LLM may send 1.0 for integers)
        for key, value in list(args.items()):
            if isinstance(value, float) and value.is_integer():
                args[key] = int(value)

        try:
            return await tool.execute(**args)
        except TypeError as e:
            return ToolResult(success=False, output=f"Invalid arguments for {name}: {e}")
        except Exception as e:
            return ToolResult(success=False, output=f"Tool {name} failed: {e}")


def tool(
    name: str,
    description: str,
    parameters: Optional[List[ToolParam]] = None,
    destructive: bool = False,
) -> Callable[[Callable[..., Any]], BaseTool]:
    """Decorator to turn an async function into a BaseTool."""

    def decorator(fn: Callable[..., Any]) -> BaseTool:
        class _FnTool(BaseTool):
            pass

        instance = _FnTool()
        instance.name = name
        instance.description = description
        instance.parameters = parameters or []
        instance.destructive = destructive
        instance.execute = fn  # type: ignore[method-assign]
        return instance

    return decorator
