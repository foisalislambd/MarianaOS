"""Structured Windows UI Automation tools (prefer over screenshots + blind clicks)."""

from __future__ import annotations

from typing import Any, Optional

from tools.base import BaseTool, ToolParam, ToolResult
from utils import win_ui


class GetUiTreeTool(BaseTool):
    name = "get_ui_tree"
    category = "ui"
    description = (
        "Inspect the UI Automation tree of a window (or the active window). "
        "Returns control names, types, AutomationIds, and bounds. "
        "PREFER this over screenshots to find buttons, edits, menus, etc."
    )
    parameters = [
        ToolParam(
            name="window",
            type="string",
            description="Window title substring (e.g. 'Cursor', 'Notepad'). Empty = active window.",
            required=False,
        ),
        ToolParam(
            name="max_depth",
            type="integer",
            description="Tree depth (default 4, max 8).",
            required=False,
        ),
        ToolParam(
            name="max_nodes",
            type="integer",
            description="Max controls to return (default 80).",
            required=False,
        ),
    ]

    async def execute(
        self,
        window: str = "",
        max_depth: int = 4,
        max_nodes: int = 80,
        **_: Any,
    ) -> ToolResult:
        nodes = win_ui.ui_tree(window=window or "", max_depth=max_depth, max_nodes=max_nodes)
        if not nodes:
            return ToolResult(
                success=False,
                output="No UI nodes found. Is the window open / title correct?",
            )
        lines = []
        for n in nodes:
            indent = "  " * int(n.get("depth") or 0)
            aid = n.get("automation_id") or ""
            aid_s = f" id={aid}" if aid else ""
            lines.append(
                f"{indent}- {n.get('type')}: '{n.get('name')}'{aid_s} "
                f"@({n.get('left')},{n.get('top')}) {n.get('width')}x{n.get('height')}"
            )
        return ToolResult(
            success=True,
            output="\n".join(lines),
            data={"nodes": nodes, "count": len(nodes)},
        )


class FindControlTool(BaseTool):
    name = "find_control"
    category = "ui"
    description = (
        "Find a UI control by Name and/or AutomationId (optionally under a window). "
        "Returns bounds so you can click it with click_control (preferred) or mouse_click."
    )
    parameters = [
        ToolParam(name="name", type="string", description="Control Name (visible text).", required=False),
        ToolParam(name="automation_id", type="string", description="AutomationId if known.", required=False),
        ToolParam(
            name="control_type",
            type="string",
            description="button, edit, text, menuitem, listitem, checkbox, combobox, tabitem, pane, any…",
            required=False,
        ),
        ToolParam(name="window", type="string", description="Window title substring.", required=False),
    ]

    async def execute(
        self,
        name: str = "",
        automation_id: str = "",
        control_type: str = "",
        window: str = "",
        **_: Any,
    ) -> ToolResult:
        if not name and not automation_id:
            return ToolResult(success=False, output="Provide name and/or automation_id")
        ctrl = win_ui.find_control(
            window=window or "",
            name=name or "",
            automation_id=automation_id or "",
            control_type=control_type or "",
        )
        if not ctrl:
            return ToolResult(success=False, output="Control not found")
        info = win_ui.describe_control(ctrl)
        return ToolResult(
            success=True,
            output=(
                f"Found {info['type']} '{info['name']}' "
                f"@({info['left']},{info['top']}) {info['width']}x{info['height']}"
            ),
            data=info,
        )


class ClickControlTool(BaseTool):
    name = "click_control"
    category = "ui"
    description = (
        "Click a UI control by Name / AutomationId (Windows UI Automation). "
        "Preferred over mouse_click when the control name is known."
    )
    parameters = [
        ToolParam(name="name", type="string", description="Control Name.", required=False),
        ToolParam(name="automation_id", type="string", description="AutomationId.", required=False),
        ToolParam(
            name="control_type",
            type="string",
            description="Optional type hint: button, edit, menuitem, …",
            required=False,
        ),
        ToolParam(name="window", type="string", description="Window title substring.", required=False),
        ToolParam(
            name="double",
            type="boolean",
            description="Double-click. Default false.",
            required=False,
        ),
    ]

    async def execute(
        self,
        name: str = "",
        automation_id: str = "",
        control_type: str = "",
        window: str = "",
        double: bool = False,
        **_: Any,
    ) -> ToolResult:
        if not name and not automation_id:
            return ToolResult(success=False, output="Provide name and/or automation_id")
        ok, msg, info = win_ui.click_control(
            window=window or "",
            name=name or "",
            automation_id=automation_id or "",
            control_type=control_type or "",
            double=bool(double),
        )
        return ToolResult(success=ok, output=msg, data=info or {})


class SetControlValueTool(BaseTool):
    name = "set_control_value"
    category = "ui"
    description = (
        "Focus an Edit/Document control and set its text (paste). "
        "Use for filling text boxes without pixel clicking."
    )
    parameters = [
        ToolParam(name="value", type="string", description="Text to enter."),
        ToolParam(name="name", type="string", description="Control Name.", required=False),
        ToolParam(name="automation_id", type="string", description="AutomationId.", required=False),
        ToolParam(name="window", type="string", description="Window title substring.", required=False),
        ToolParam(
            name="submit",
            type="boolean",
            description="Press Enter after setting value. Default false.",
            required=False,
        ),
    ]

    async def execute(
        self,
        value: str,
        name: str = "",
        automation_id: str = "",
        window: str = "",
        submit: bool = False,
        **_: Any,
    ) -> ToolResult:
        ctrl = win_ui.find_control(
            window=window or "",
            name=name or "",
            automation_id=automation_id or "",
            control_type="edit",
        )
        if not ctrl:
            ctrl = win_ui.find_control(
                window=window or "",
                name=name or "",
                automation_id=automation_id or "",
                control_type="document",
            )
        if not ctrl:
            ctrl = win_ui.find_control(
                window=window or "",
                name=name or "",
                automation_id=automation_id or "",
            )
        if not ctrl:
            return ToolResult(success=False, output="Edit control not found")
        info = win_ui.describe_control(ctrl)
        try:
            ctrl.Click()
        except Exception:
            pass
        try:
            win_ui.send_hotkey("ctrl", "a")
        except Exception:
            pass
        win_ui.send_keys(value)
        if submit:
            win_ui.press_key("enter")
        return ToolResult(
            success=True,
            output=f"Set value on '{info.get('name')}' ({len(value)} chars)",
            data=info,
        )


class InvokeControlTool(BaseTool):
    name = "invoke_control"
    category = "ui"
    description = (
        "Invoke a control's default action (buttons, menu items) via UI Automation pattern."
    )
    parameters = [
        ToolParam(name="name", type="string", description="Control Name.", required=False),
        ToolParam(name="automation_id", type="string", description="AutomationId.", required=False),
        ToolParam(name="window", type="string", description="Window title substring.", required=False),
        ToolParam(name="control_type", type="string", description="Optional type.", required=False),
    ]

    async def execute(
        self,
        name: str = "",
        automation_id: str = "",
        window: str = "",
        control_type: str = "",
        **_: Any,
    ) -> ToolResult:
        ctrl = win_ui.find_control(
            window=window or "",
            name=name or "",
            automation_id=automation_id or "",
            control_type=control_type or "",
        )
        if not ctrl:
            return ToolResult(success=False, output="Control not found")
        info = win_ui.describe_control(ctrl)
        try:
            import uiautomation as auto

            pattern = ctrl.GetPattern(auto.PatternId.InvokePattern)
            if pattern:
                pattern.Invoke()
                return ToolResult(success=True, output=f"Invoked '{info['name']}'", data=info)
        except Exception:
            pass
        ok, msg, clicked = win_ui.click_control(
            window=window or "",
            name=name or "",
            automation_id=automation_id or "",
            control_type=control_type or "",
        )
        return ToolResult(
            success=ok,
            output=msg if ok else f"Invoke failed; click: {msg}",
            data=clicked or info,
        )
