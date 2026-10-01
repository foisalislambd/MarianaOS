"""Screenshot capture (Pillow) — use sparingly; prefer get_ui_tree / click_control."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from tools.base import BaseTool, ToolParam, ToolResult


class TakeScreenshotTool(BaseTool):
    name = "take_screenshot"
    description = (
        "Capture a screenshot (only when the user asks, or when UI Automation cannot "
        "see the needed visual content). Prefer get_ui_tree / find_control / click_control "
        "for normal UI work. Returns the saved file path."
    )
    parameters = [
        ToolParam(
            name="region",
            type="string",
            description=(
                "Optional region as 'left,top,width,height' in screen pixels. "
                "If set, only that region is captured."
            ),
            required=False,
        ),
        ToolParam(
            name="label",
            type="string",
            description="Optional short label for the filename.",
            required=False,
        ),
        ToolParam(
            name="send_to_user",
            type="boolean",
            description=(
                "If true, attach image to Telegram reply. Default false — "
                "only set true when the user asked for a screenshot or final proof."
            ),
            required=False,
        ),
    ]

    def __init__(self, screenshot_dir: Path) -> None:
        self.screenshot_dir = screenshot_dir
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    async def execute(
        self,
        region: Optional[str] = None,
        label: Optional[str] = None,
        send_to_user: bool = False,
        **_: Any,
    ) -> ToolResult:
        from PIL import ImageGrab

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tag = f"_{label}" if label else ""
        out_path = self.screenshot_dir / f"shot_{stamp}{tag}.png"

        bbox = None
        if region:
            parts = [int(x.strip()) for x in region.split(",")]
            if len(parts) != 4:
                return ToolResult(
                    success=False,
                    output="region must be 'left,top,width,height'",
                )
            left, top, width, height = parts
            bbox = (left, top, left + width, top + height)

        img = ImageGrab.grab(bbox=bbox, all_screens=True)
        img.save(out_path, "PNG")

        media = [str(out_path)] if send_to_user else []
        return ToolResult(
            success=True,
            output=f"Screenshot saved: {out_path}",
            data={"path": str(out_path), "size": list(img.size)},
            media_paths=media,
        )


class CaptureWindowTool(BaseTool):
    name = "capture_window"
    description = (
        "Screenshot a specific window by title (bounds capture). "
        "Prefer get_ui_tree for normal UI work; use this when the user wants a window image."
    )
    parameters = [
        ToolParam(name="title", type="string", description="Window title substring."),
        ToolParam(
            name="send_to_user",
            type="boolean",
            description="Attach image to Telegram reply. Default true.",
            required=False,
        ),
    ]

    def __init__(self, screenshot_dir: Path) -> None:
        self.screenshot_dir = screenshot_dir
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    async def execute(
        self, title: str, send_to_user: bool = True, **_: Any
    ) -> ToolResult:
        from PIL import ImageGrab

        from utils import win_ui

        ok, name = win_ui.focus_window(title)
        if not ok:
            return ToolResult(success=False, output=name)
        info = win_ui.get_active_window_info()
        if not info:
            return ToolResult(success=False, output="Could not read window bounds")
        bbox = (
            int(info["left"]),
            int(info["top"]),
            int(info["left"]) + int(info["width"]),
            int(info["top"]) + int(info["height"]),
        )
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = self.screenshot_dir / f"shot_{stamp}_window.png"
        img = ImageGrab.grab(bbox=bbox, all_screens=True)
        img.save(out_path, "PNG")
        media = [str(out_path)] if send_to_user else []
        return ToolResult(
            success=True,
            output=f"Captured window '{name}': {out_path}",
            data={"path": str(out_path), "window": name, "bbox": list(bbox)},
            media_paths=media,
        )


class ListScreenshotsTool(BaseTool):
    name = "list_screenshots"
    description = "List recent screenshot files saved by the agent."
    parameters = [
        ToolParam(
            name="limit",
            type="integer",
            description="Max number of files to list (default 10).",
            required=False,
        ),
    ]

    def __init__(self, screenshot_dir: Path) -> None:
        self.screenshot_dir = screenshot_dir

    async def execute(self, limit: int = 10, **_: Any) -> ToolResult:
        files = sorted(
            self.screenshot_dir.glob("shot_*.png"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[: max(1, min(limit, 50))]
        lines = [f"{p.name}  ({p.stat().st_size} bytes)  {p}" for p in files]
        return ToolResult(
            success=True,
            output="\n".join(lines) if lines else "No screenshots yet.",
            data={"files": [str(p) for p in files]},
        )
