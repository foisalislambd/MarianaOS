"""Vision / screenshot analysis tool."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from tools.base import BaseTool, ToolParam, ToolResult


class AnalyzeScreenshotTool(BaseTool):
    name = "analyze_screenshot"
    description = (
        "Analyze a screenshot image with vision AI. "
        "Pass a screenshot path from take_screenshot. "
        "Ask specific questions like 'Where is the model picker?' or "
        "'What dialog is open? Give click coordinates if possible.'"
    )
    parameters = [
        ToolParam(
            name="path",
            type="string",
            description="Path to the screenshot PNG file.",
        ),
        ToolParam(
            name="question",
            type="string",
            description="What to look for / analyze in the image.",
        ),
    ]

    def __init__(self, llm_client: Any, vision_model: str) -> None:
        self.llm = llm_client
        self.vision_model = vision_model

    async def execute(self, path: str, question: str, **_: Any) -> ToolResult:
        p = Path(path)
        if not p.exists():
            return ToolResult(success=False, output=f"Screenshot not found: {path}")

        raw = p.read_bytes()
        b64 = base64.standard_b64encode(raw).decode("ascii")
        mime, _ = mimetypes.guess_type(str(p))
        if not mime or not mime.startswith("image/"):
            mime = "image/png"
        if mime == "image/jpg":
            mime = "image/jpeg"
        data_url = f"data:{mime};base64,{b64}"

        prompt = (
            "You are helping a desktop AI agent control a Windows PC. "
            "Analyze this screenshot carefully. "
            "If the user asks for UI element locations, estimate pixel coordinates (x, y) "
            "from the top-left of the image. Be specific and actionable.\n\n"
            f"Question: {question}"
        )

        try:
            analysis = await self.llm.analyze_image(
                model=self.vision_model,
                image_data_url=data_url,
                prompt=prompt,
            )
        except Exception as e:
            return ToolResult(success=False, output=f"Vision analysis failed: {e}")

        return ToolResult(
            success=True,
            output=analysis,
            data={"path": str(p)},
            media_paths=[str(p)],
        )
