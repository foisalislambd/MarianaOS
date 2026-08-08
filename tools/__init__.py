"""Register all tools."""

from __future__ import annotations

from typing import Any

from config.settings import Settings
from tools.applications import OpenApplicationTool, OpenFolderInCursorTool, OpenUrlTool
from tools.base import ToolRegistry
from tools.cursor_ide import (
    CursorAddContextTool,
    CursorCommandPaletteTool,
    CursorImportChatTool,
    CursorNewChatTool,
    CursorOpenChatTool,
    CursorOpenHistoryTool,
    CursorSelectModelTool,
    CursorSetEffortTool,
    CursorTypeInChatTool,
)
from tools.filesystem import (
    CreateDirectoryTool,
    DeletePathTool,
    ListDirectoryTool,
    MovePathTool,
    OpenInExplorerTool,
    ReadFileTool,
    SearchFilesTool,
    WriteFileTool,
)
from tools.input_control import (
    GetMousePositionTool,
    HotkeyTool,
    MouseClickTool,
    MouseMoveTool,
    MouseScrollTool,
    PressKeyTool,
    TypeTextTool,
    WaitTool,
)
from tools.screenshot import ListScreenshotsTool, TakeScreenshotTool
from tools.system import (
    ClipboardGetTool,
    ClipboardSetTool,
    ListProcessesTool,
    RunShellTool,
    SystemInfoTool,
)
from tools.vision import AnalyzeScreenshotTool
from tools.window import (
    FocusWindowTool,
    GetActiveWindowTool,
    ListWindowsTool,
    MaximizeWindowTool,
    MinimizeWindowTool,
)


def build_registry(settings: Settings, llm_client: Any) -> ToolRegistry:
    reg = ToolRegistry()
    ws = settings.workspace
    shot = settings.screenshot_dir
    cursor = settings.cursor_path

    # Filesystem
    reg.register(ListDirectoryTool(ws))
    reg.register(ReadFileTool(ws))
    reg.register(WriteFileTool(ws))
    reg.register(CreateDirectoryTool(ws))
    reg.register(DeletePathTool(ws))
    reg.register(MovePathTool(ws))
    reg.register(SearchFilesTool(ws))
    reg.register(OpenInExplorerTool(ws))

    # Apps
    reg.register(OpenApplicationTool(cursor))
    reg.register(OpenUrlTool())
    reg.register(OpenFolderInCursorTool(ws, cursor))

    # Cursor IDE / Agents panel
    reg.register(CursorCommandPaletteTool())
    reg.register(CursorOpenChatTool())
    reg.register(CursorNewChatTool())
    reg.register(CursorOpenHistoryTool())
    reg.register(CursorSelectModelTool())
    reg.register(CursorSetEffortTool())
    reg.register(CursorTypeInChatTool())
    reg.register(CursorAddContextTool())
    reg.register(CursorImportChatTool())

    # Screen / input
    reg.register(TakeScreenshotTool(shot))
    reg.register(ListScreenshotsTool(shot))
    reg.register(AnalyzeScreenshotTool(llm_client, settings.llm_vision_model))
    reg.register(MouseClickTool())
    reg.register(MouseMoveTool())
    reg.register(MouseScrollTool())
    reg.register(TypeTextTool())
    reg.register(HotkeyTool())
    reg.register(PressKeyTool())
    reg.register(GetMousePositionTool())
    reg.register(WaitTool())

    # Windows
    reg.register(ListWindowsTool())
    reg.register(FocusWindowTool())
    reg.register(GetActiveWindowTool())
    reg.register(MinimizeWindowTool())
    reg.register(MaximizeWindowTool())

    # System
    reg.register(SystemInfoTool())
    reg.register(RunShellTool())
    reg.register(ListProcessesTool())
    reg.register(ClipboardGetTool())
    reg.register(ClipboardSetTool())

    return reg
