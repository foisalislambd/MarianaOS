"""Tool base classes and registry (with optional tool discovery to save tokens)."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class ToolResult:
    success: bool
    output: str
    data: Dict[str, Any] = field(default_factory=dict)
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
    items_type: Optional[str] = None


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    parameters: List[ToolParam] = []
    destructive: bool = False
    category: str = "general"
    always_on: bool = False

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

    def brief(self) -> Dict[str, str]:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
        }


# Large core set so the agent can work fluently without constant search_tools.
DEFAULT_CORE_TOOLS: Set[str] = {
    # meta
    "search_tools",
    "list_tool_catalog",
    # windows
    "list_windows",
    "get_active_window",
    "focus_window",
    "minimize_window",
    "maximize_window",
    "restore_window",
    "close_window",
    "resize_window",
    "wait_for_window",
    # UI automation
    "get_ui_tree",
    "find_control",
    "click_control",
    "set_control_value",
    "invoke_control",
    "wait_for_control",
    # input
    "hotkey",
    "press_key",
    "type_text",
    "mouse_click",
    "mouse_move",
    "mouse_scroll",
    "mouse_drag",
    "get_mouse_position",
    "wait",
    "media_key",
    # apps / web
    "open_application",
    "open_url",
    "open_path",
    "web_search",
    "open_folder_in_cursor",
    # files
    "list_directory",
    "list_drives",
    "read_file",
    "write_file",
    "append_file",
    "search_files",
    "file_info",
    "copy_path",
    "move_path",
    "delete_path",
    "create_directory",
    "open_in_explorer",
    "zip_path",
    "unzip_path",
    # system
    "run_shell",
    "system_info",
    "list_processes",
    "kill_process",
    "clipboard_get",
    "clipboard_set",
    "get_selection",
    "notify",
    # screen (available; still prefer UI tools)
    "take_screenshot",
    "capture_window",
    "analyze_screenshot",
    # cursor
    "cursor_select_model",
    "cursor_get_model",
    "cursor_list_models",
    "cursor_list_chats",
    "cursor_open_chat_session",
    "cursor_type_in_chat",
    "cursor_open_chat",
    "cursor_new_chat",
}


class ToolRegistry:
    def __init__(
        self,
        *,
        discovery: bool = True,
        core_tools: Optional[Set[str]] = None,
    ) -> None:
        self._tools: Dict[str, BaseTool] = {}
        self.discovery = discovery
        self.core_tools: Set[str] = set(core_tools or DEFAULT_CORE_TOOLS)
        self._session_enabled: Set[str] = set()

    def register(self, tool: BaseTool) -> None:
        if not tool.name:
            raise ValueError(f"Tool {tool!r} has no name")
        self._tools[tool.name] = tool
        if tool.always_on:
            self.core_tools.add(tool.name)

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list(self) -> List[BaseTool]:
        return list(self._tools.values())

    def reset_session(self) -> None:
        self._session_enabled.clear()

    def enable(self, names: List[str]) -> List[str]:
        enabled: List[str] = []
        for n in names:
            if n in self._tools:
                self._session_enabled.add(n)
                enabled.append(n)
        return enabled

    def active_names(self) -> Set[str]:
        if not self.discovery:
            return set(self._tools.keys())
        names = set(self.core_tools) | set(self._session_enabled)
        for t in self._tools.values():
            if t.always_on:
                names.add(t.name)
        return {n for n in names if n in self._tools}

    def openai_tools(self) -> List[Dict[str, Any]]:
        names = self.active_names()
        ordered = sorted(
            names,
            key=lambda n: (0 if n in self.core_tools else 1, n),
        )
        return [self._tools[n].openai_schema() for n in ordered]

    def search(self, query: str, limit: int = 12) -> List[Dict[str, Any]]:
        q = (query or "").strip().lower()
        tokens = [t for t in re.split(r"[^a-z0-9_]+", q) if t]
        scored: List[tuple[int, BaseTool]] = []
        for tool in self._tools.values():
            blob = f"{tool.name} {tool.category} {tool.description}".lower()
            score = 0
            if not tokens:
                score = 1
            else:
                for t in tokens:
                    if t == tool.name:
                        score += 100
                    elif t in tool.name:
                        score += 40
                    elif t == tool.category:
                        score += 30
                    elif t in blob:
                        score += 10
            if score:
                scored.append((score, tool))
        scored.sort(key=lambda x: (-x[0], x[1].name))
        return [t.brief() for _, t in scored[: max(1, min(limit, 40))]]

    async def call(
        self,
        name: str,
        arguments: Dict[str, Any],
        require_confirmation: bool = False,
    ) -> ToolResult:
        tool = self.get(name)
        if tool is None:
            return ToolResult(success=False, output=f"Unknown tool: {name}")

        if self.discovery and name not in self.active_names():
            self._session_enabled.add(name)

        args = dict(arguments or {})

        for key, value in list(args.items()):
            if isinstance(value, float) and value.is_integer():
                args[key] = int(value)
            elif isinstance(value, str):
                low = value.strip().lower()
                if low in {"true", "false", "yes", "no", "1", "0"}:
                    param = next((p for p in tool.parameters if p.name == key), None)
                    if param and param.type == "boolean":
                        args[key] = low in {"true", "yes", "1"}
                    elif key == "confirm":
                        args[key] = low in {"true", "yes", "1"}

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

        try:
            return await tool.execute(**args)
        except TypeError as e:
            return ToolResult(success=False, output=f"Invalid arguments for {name}: {e}")
        except Exception as e:
            return ToolResult(success=False, output=f"Tool {name} failed: {e}")
