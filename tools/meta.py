"""Meta tools: search / enable tools to keep LLM schemas small."""

from __future__ import annotations

from typing import Any, List, Optional

from tools.base import BaseTool, ToolParam, ToolRegistry, ToolResult


class SearchToolsTool(BaseTool):
    name = "search_tools"
    description = (
        "Search available MarianaOS tools by keyword and ENABLE matching tools "
        "for this turn (saves tokens — only a core set is always loaded). "
        "Examples: query='cursor model', 'screenshot click', 'delete file', 'clipboard'. "
        "Call this BEFORE using a specialized tool that is not in the current tool list."
    )
    category = "meta"
    always_on = True
    parameters = [
        ToolParam(
            name="query",
            type="string",
            description="Keywords: e.g. 'cursor chat', 'mouse', 'write file', 'window'.",
        ),
        ToolParam(
            name="limit",
            type="integer",
            description="Max results to return/enable (default 10).",
            required=False,
        ),
    ]

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    async def execute(self, query: str, limit: int = 10, **_: Any) -> ToolResult:
        hits = self.registry.search(query, limit=int(limit or 10))
        enabled = self.registry.enable([h["name"] for h in hits])
        # Always ensure full schemas for enabled tools are available next round
        lines = [
            f"Enabled {len(enabled)} tool(s) for this session matching '{query}'.",
            "You can call them on the next step. Matches:",
        ]
        for h in hits:
            lines.append(f"- [{h['category']}] {h['name']}: {h['description'][:140]}")
        return ToolResult(
            success=True,
            output="\n".join(lines),
            data={"query": query, "enabled": enabled, "matches": hits},
        )


class ListToolCatalogTool(BaseTool):
    name = "list_tool_catalog"
    description = (
        "List all tool names grouped by category (short). "
        "Prefer search_tools when you know what you need."
    )
    category = "meta"
    always_on = True
    parameters = [
        ToolParam(
            name="category",
            type="string",
            description="Optional category filter: filesystem, cursor, screen, input, window, system, apps, meta.",
            required=False,
        ),
    ]

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    async def execute(self, category: Optional[str] = None, **_: Any) -> ToolResult:
        cat = (category or "").strip().lower()
        groups: dict[str, List[str]] = {}
        for t in self.registry.list():
            if cat and t.category.lower() != cat:
                continue
            groups.setdefault(t.category, []).append(t.name)
        lines = []
        for c in sorted(groups):
            lines.append(f"{c}: {', '.join(sorted(groups[c]))}")
        return ToolResult(
            success=True,
            output="\n".join(lines) or "No tools matched.",
            data={"categories": groups},
        )
