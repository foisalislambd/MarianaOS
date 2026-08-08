"""Register all tools."""

from __future__ import annotations

from typing import Any, Dict

from config.settings import Settings
from tools.applications import OpenApplicationTool, OpenFolderInCursorTool, OpenUrlTool
from tools.base import DEFAULT_CORE_TOOLS, ToolRegistry
from tools.cursor_ide import (
    CursorAddContextTool,
    CursorCommandPaletteTool,
    CursorGetModelTool,
    CursorImportChatTool,
    CursorListChatsTool,
    CursorListModelsTool,
    CursorNewChatTool,
    CursorOpenChatSessionTool,
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
from tools.meta import ListToolCatalogTool, SearchToolsTool
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

TOOL_CATEGORIES: Dict[str, str] = {
    # meta
    "search_tools": "meta",
    "list_tool_catalog": "meta",
    # filesystem
    "list_directory": "filesystem",
    "read_file": "filesystem",
    "write_file": "filesystem",
    "create_directory": "filesystem",
    "delete_path": "filesystem",
    "move_path": "filesystem",
    "search_files": "filesystem",
    "open_in_explorer": "filesystem",
    # apps
    "open_application": "apps",
    "open_url": "apps",
    "open_folder_in_cursor": "apps",
    # cursor
    "cursor_get_model": "cursor",
    "cursor_list_models": "cursor",
    "cursor_select_model": "cursor",
    "cursor_set_effort": "cursor",
    "cursor_list_chats": "cursor",
    "cursor_open_chat_session": "cursor",
    "cursor_open_history": "cursor",
    "cursor_import_chat": "cursor",
    "cursor_command_palette": "cursor",
    "cursor_open_chat": "cursor",
    "cursor_new_chat": "cursor",
    "cursor_type_in_chat": "cursor",
    "cursor_add_context": "cursor",
    # screen
    "take_screenshot": "screen",
    "list_screenshots": "screen",
    "analyze_screenshot": "screen",
    # input
    "mouse_click": "input",
    "mouse_move": "input",
    "mouse_scroll": "input",
    "type_text": "input",
    "hotkey": "input",
    "press_key": "input",
    "get_mouse_position": "input",
    "wait": "input",
    # window
    "list_windows": "window",
    "focus_window": "window",
    "get_active_window": "window",
    "minimize_window": "window",
    "maximize_window": "window",
    # system
    "system_info": "system",
    "run_shell": "system",
    "list_processes": "system",
    "clipboard_get": "system",
    "clipboard_set": "system",
}


def build_registry(settings: Settings, llm_client: Any) -> ToolRegistry:
    core = set(DEFAULT_CORE_TOOLS)
    if settings.tool_core:
        core = {x.strip() for x in settings.tool_core.split(",") if x.strip()}
        core.add("search_tools")
        core.add("list_tool_catalog")

    reg = ToolRegistry(discovery=settings.tool_discovery, core_tools=core)
    ws = settings.workspace
    shot = settings.screenshot_dir
    cursor = settings.cursor_path

    # Meta (needs registry ref — registered first, then wired)
    search = SearchToolsTool(reg)
    catalog = ListToolCatalogTool(reg)
    reg.register(search)
    reg.register(catalog)

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

    # Cursor IDE — Python-first, then UI fallbacks
    reg.register(CursorGetModelTool())
    reg.register(CursorListModelsTool())
    reg.register(CursorSelectModelTool())
    reg.register(CursorSetEffortTool())
    reg.register(CursorListChatsTool())
    reg.register(CursorOpenChatSessionTool())
    reg.register(CursorOpenHistoryTool())
    reg.register(CursorImportChatTool())
    reg.register(CursorCommandPaletteTool())
    reg.register(CursorOpenChatTool())
    reg.register(CursorNewChatTool())
    reg.register(CursorTypeInChatTool())
    reg.register(CursorAddContextTool())

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

    for t in reg.list():
        if t.name in TOOL_CATEGORIES:
            t.category = TOOL_CATEGORIES[t.name]

    return reg
