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
from tools.extras import (
    AppendFileTool,
    CopyPathTool,
    FileInfoTool,
    GetSelectionTool,
    KillProcessTool,
    ListDrivesTool,
    MediaKeyTool,
    MouseDragTool,
    NotifyTool,
    OpenPathTool,
    UnzipPathTool,
    WaitForControlTool,
    WaitForWindowTool,
    WebSearchTool,
    ZipPathTool,
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
from tools.screenshot import CaptureWindowTool, ListScreenshotsTool, TakeScreenshotTool
from tools.system import (
    ClipboardGetTool,
    ClipboardSetTool,
    ListProcessesTool,
    RunShellTool,
    SystemInfoTool,
)
from tools.ui_automation import (
    ClickControlTool,
    FindControlTool,
    GetUiTreeTool,
    InvokeControlTool,
    SetControlValueTool,
)
from tools.vision import AnalyzeScreenshotTool
from tools.window import (
    CloseWindowTool,
    FocusWindowTool,
    GetActiveWindowTool,
    ListWindowsTool,
    MaximizeWindowTool,
    MinimizeWindowTool,
    ResizeWindowTool,
    RestoreWindowTool,
)

TOOL_CATEGORIES: Dict[str, str] = {
    "search_tools": "meta",
    "list_tool_catalog": "meta",
    "list_directory": "filesystem",
    "list_drives": "filesystem",
    "read_file": "filesystem",
    "write_file": "filesystem",
    "append_file": "filesystem",
    "create_directory": "filesystem",
    "delete_path": "filesystem",
    "move_path": "filesystem",
    "copy_path": "filesystem",
    "search_files": "filesystem",
    "file_info": "filesystem",
    "open_in_explorer": "filesystem",
    "zip_path": "filesystem",
    "unzip_path": "filesystem",
    "open_application": "apps",
    "open_url": "apps",
    "open_path": "apps",
    "web_search": "apps",
    "open_folder_in_cursor": "apps",
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
    "get_ui_tree": "ui",
    "find_control": "ui",
    "click_control": "ui",
    "set_control_value": "ui",
    "invoke_control": "ui",
    "wait_for_control": "ui",
    "take_screenshot": "screen",
    "capture_window": "screen",
    "list_screenshots": "screen",
    "analyze_screenshot": "screen",
    "mouse_click": "input",
    "mouse_move": "input",
    "mouse_scroll": "input",
    "mouse_drag": "input",
    "type_text": "input",
    "hotkey": "input",
    "press_key": "input",
    "get_mouse_position": "input",
    "wait": "input",
    "media_key": "input",
    "list_windows": "window",
    "focus_window": "window",
    "get_active_window": "window",
    "minimize_window": "window",
    "maximize_window": "window",
    "restore_window": "window",
    "close_window": "window",
    "resize_window": "window",
    "wait_for_window": "window",
    "system_info": "system",
    "run_shell": "system",
    "list_processes": "system",
    "kill_process": "system",
    "clipboard_get": "system",
    "clipboard_set": "system",
    "get_selection": "system",
    "notify": "system",
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

    reg.register(SearchToolsTool(reg))
    reg.register(ListToolCatalogTool(reg))

    # Filesystem
    reg.register(ListDirectoryTool(ws))
    reg.register(ListDrivesTool())
    reg.register(ReadFileTool(ws))
    reg.register(WriteFileTool(ws))
    reg.register(AppendFileTool(ws))
    reg.register(CreateDirectoryTool(ws))
    reg.register(DeletePathTool(ws))
    reg.register(MovePathTool(ws))
    reg.register(CopyPathTool(ws))
    reg.register(SearchFilesTool(ws))
    reg.register(FileInfoTool(ws))
    reg.register(OpenInExplorerTool(ws))
    reg.register(ZipPathTool(ws))
    reg.register(UnzipPathTool(ws))

    # Apps / web
    reg.register(OpenApplicationTool())
    reg.register(OpenUrlTool())
    reg.register(OpenPathTool(ws))
    reg.register(WebSearchTool())
    reg.register(OpenFolderInCursorTool(ws))

    # Cursor IDE
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

    # UI Automation
    reg.register(GetUiTreeTool())
    reg.register(FindControlTool())
    reg.register(ClickControlTool())
    reg.register(SetControlValueTool())
    reg.register(InvokeControlTool())
    reg.register(WaitForControlTool())

    # Screen
    reg.register(TakeScreenshotTool(shot))
    reg.register(CaptureWindowTool(shot))
    reg.register(ListScreenshotsTool(shot))
    reg.register(AnalyzeScreenshotTool(llm_client, settings.llm.vision_model))

    # Input
    reg.register(MouseClickTool())
    reg.register(MouseMoveTool())
    reg.register(MouseScrollTool())
    reg.register(MouseDragTool())
    reg.register(TypeTextTool())
    reg.register(HotkeyTool())
    reg.register(PressKeyTool())
    reg.register(GetMousePositionTool())
    reg.register(WaitTool())
    reg.register(MediaKeyTool())

    # Windows
    reg.register(ListWindowsTool())
    reg.register(FocusWindowTool())
    reg.register(GetActiveWindowTool())
    reg.register(MinimizeWindowTool())
    reg.register(MaximizeWindowTool())
    reg.register(RestoreWindowTool())
    reg.register(CloseWindowTool())
    reg.register(ResizeWindowTool())
    reg.register(WaitForWindowTool())

    # System
    reg.register(SystemInfoTool())
    reg.register(RunShellTool())
    reg.register(ListProcessesTool())
    reg.register(KillProcessTool())
    reg.register(ClipboardGetTool())
    reg.register(ClipboardSetTool())
    reg.register(GetSelectionTool())
    reg.register(NotifyTool())

    for t in reg.list():
        if t.name in TOOL_CATEGORIES:
            t.category = TOOL_CATEGORIES[t.name]

    return reg
