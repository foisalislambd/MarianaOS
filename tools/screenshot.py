"""Screenshot capture tools."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from tools.base import BaseTool, ToolParam, ToolResult


class TakeScreenshotTool(BaseTool):
    name = "take_screenshot"
    description = (
        "Capture a screenshot of the desktop (or a specific monitor / region). "
        "Returns the saved file path. Use this to see the current screen before acting, "
        "and again after finishing a task so the user can verify."
    )
    parameters = [
        ToolParam(
            name="monitor",
            type="integer",
            description="Monitor index (1 = primary). 0 = all monitors stitched. Default 1.",
            required=False,
        ),
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
            description="Optional short label for the filename (e.g. 'before', 'after', 'cursor').",
            required=False,
        ),
    ]

    def __init__(self, screenshot_dir: Path) -> None:
        self.screenshot_dir = screenshot_dir
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    async def execute(
        self,
        monitor: int = 1,
        region: Optional[str] = None,
        label: Optional[str] = None,
        **_: Any,
    ) -> ToolResult:
        import mss
        from PIL import Image

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tag = f"_{label}" if label else ""
        out_path = self.screenshot_dir / f"shot_{stamp}{tag}.png"

        with mss.mss() as sct:
            if region:
                parts = [int(x.strip()) for x in region.split(",")]
                if len(parts) != 4:
                    return ToolResult(
                        success=False,
                        output="region must be 'left,top,width,height'",
                    )
                left, top, width, height = parts
                mon = {"left": left, "top": top, "width": width, "height": height}
            else:
                monitors = sct.monitors
                idx = max(0, min(monitor, len(monitors) - 1))
                mon = monitors[idx]

            raw = sct.grab(mon)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            img.save(out_path, "PNG")

        return ToolResult(
            success=True,
            output=f"Screenshot saved: {out_path}",
            data={"path": str(out_path), "size": list(img.size)},
            media_paths=[str(out_path)],
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
