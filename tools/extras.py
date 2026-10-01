"""Popular power tools — files, web, process, notify, zip, wait helpers."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
import urllib.parse
import webbrowser
import zipfile
from pathlib import Path
from typing import Any, Optional

from tools.base import BaseTool, ToolParam, ToolResult
from utils import win_ui
from utils.paths import safe_resolve


class CopyPathTool(BaseTool):
    name = "copy_path"
    category = "filesystem"
    description = "Copy a file or folder to a destination (shutil copy / copytree)."
    parameters = [
        ToolParam(name="source", type="string", description="Source path."),
        ToolParam(name="destination", type="string", description="Destination path."),
    ]

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(self, source: str, destination: str, **_: Any) -> ToolResult:
        src = safe_resolve(source, self.workspace)
        dst = safe_resolve(destination, self.workspace)
        if not src.exists():
            return ToolResult(success=False, output=f"Source not found: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            if dst.exists():
                return ToolResult(success=False, output=f"Destination already exists: {dst}")
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        return ToolResult(
            success=True,
            output=f"Copied {src} → {dst}",
            data={"source": str(src), "destination": str(dst)},
        )


class FileInfoTool(BaseTool):
    name = "file_info"
    category = "filesystem"
    description = "Get size, modified time, and type for a file or folder."
    parameters = [
        ToolParam(name="path", type="string", description="Path to inspect."),
    ]

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(self, path: str, **_: Any) -> ToolResult:
        target = safe_resolve(path, self.workspace)
        if not target.exists():
            return ToolResult(success=False, output=f"Path not found: {target}")
        st = target.stat()
        info = {
            "path": str(target),
            "type": "dir" if target.is_dir() else "file",
            "size_bytes": st.st_size if target.is_file() else None,
            "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
            "extension": target.suffix if target.is_file() else "",
        }
        return ToolResult(
            success=True,
            output=(
                f"{info['type']}: {target}\n"
                f"size: {info['size_bytes']} bytes\n"
                f"modified: {info['modified']}"
            ),
            data=info,
        )


class ListDrivesTool(BaseTool):
    name = "list_drives"
    category = "filesystem"
    description = "List Windows drive letters and free/total space."
    parameters = []

    async def execute(self, **_: Any) -> ToolResult:
        lines = []
        data = []
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            root = Path(f"{letter}:/")
            if not root.exists():
                continue
            try:
                usage = shutil.disk_usage(root)
                row = {
                    "drive": f"{letter}:",
                    "total_gb": round(usage.total / (1024**3), 1),
                    "free_gb": round(usage.free / (1024**3), 1),
                }
                data.append(row)
                lines.append(
                    f"{row['drive']}  free {row['free_gb']} GB / {row['total_gb']} GB"
                )
            except Exception:
                continue
        return ToolResult(
            success=True,
            output="\n".join(lines) if lines else "No drives found.",
            data={"drives": data},
        )


class AppendFileTool(BaseTool):
    name = "append_file"
    category = "filesystem"
    description = "Append text to a file (create if missing)."
    parameters = [
        ToolParam(name="path", type="string", description="File path."),
        ToolParam(name="content", type="string", description="Text to append."),
    ]

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(self, path: str, content: str, **_: Any) -> ToolResult:
        target = safe_resolve(path, self.workspace)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as f:
            f.write(content)
        return ToolResult(
            success=True,
            output=f"Appended {len(content)} chars to {target}",
            data={"path": str(target)},
        )


class ZipPathTool(BaseTool):
    name = "zip_path"
    category = "filesystem"
    description = "Zip a file or folder into a .zip archive."
    parameters = [
        ToolParam(name="source", type="string", description="File or folder to zip."),
        ToolParam(
            name="destination",
            type="string",
            description="Output .zip path (optional).",
            required=False,
        ),
    ]

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(
        self, source: str, destination: Optional[str] = None, **_: Any
    ) -> ToolResult:
        src = safe_resolve(source, self.workspace)
        if not src.exists():
            return ToolResult(success=False, output=f"Source not found: {src}")
        if destination:
            out = safe_resolve(destination, self.workspace)
        else:
            out = src.with_suffix(".zip") if src.is_file() else Path(str(src) + ".zip")
        out.parent.mkdir(parents=True, exist_ok=True)
        if src.is_file():
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(src, arcname=src.name)
        else:
            base = str(out.with_suffix(""))
            archive = shutil.make_archive(base, "zip", root_dir=src)
            out = Path(archive)
        return ToolResult(success=True, output=f"Created zip: {out}", data={"path": str(out)})


class UnzipPathTool(BaseTool):
    name = "unzip_path"
    category = "filesystem"
    description = "Extract a .zip archive to a folder."
    parameters = [
        ToolParam(name="archive", type="string", description="Path to .zip file."),
        ToolParam(
            name="destination",
            type="string",
            description="Extract folder (optional; default next to zip).",
            required=False,
        ),
    ]

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(
        self, archive: str, destination: Optional[str] = None, **_: Any
    ) -> ToolResult:
        src = safe_resolve(archive, self.workspace)
        if not src.exists() or not zipfile.is_zipfile(src):
            return ToolResult(success=False, output=f"Not a zip file: {src}")
        dest = (
            safe_resolve(destination, self.workspace)
            if destination
            else src.with_suffix("")
        )
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(src, "r") as zf:
            zf.extractall(dest)
        return ToolResult(
            success=True,
            output=f"Extracted to {dest}",
            data={"path": str(dest)},
        )


class WebSearchTool(BaseTool):
    name = "web_search"
    category = "apps"
    description = "Open a Google search for the query in the default browser."
    parameters = [
        ToolParam(name="query", type="string", description="Search query."),
    ]

    async def execute(self, query: str, **_: Any) -> ToolResult:
        q = urllib.parse.quote_plus(query or "")
        url = f"https://www.google.com/search?q={q}"
        webbrowser.open(url)
        return ToolResult(success=True, output=f"Opened search: {url}", data={"url": url})


class OpenPathTool(BaseTool):
    name = "open_path"
    category = "apps"
    description = (
        "Open any file/folder/URL with the Windows default app (os.startfile)."
    )
    parameters = [
        ToolParam(name="path", type="string", description="File, folder, or URL."),
    ]

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(self, path: str, **_: Any) -> ToolResult:
        raw = (path or "").strip()
        if raw.startswith(("http://", "https://", "mailto:")):
            webbrowser.open(raw)
            return ToolResult(success=True, output=f"Opened: {raw}")
        target = safe_resolve(raw, self.workspace)
        if not target.exists():
            return ToolResult(success=False, output=f"Path not found: {target}")
        os.startfile(str(target))  # noqa: S606
        await asyncio.sleep(0.4)
        return ToolResult(success=True, output=f"Opened: {target}", data={"path": str(target)})


class KillProcessTool(BaseTool):
    name = "kill_process"
    category = "system"
    destructive = True
    description = "Kill a process by name or PID (taskkill)."
    parameters = [
        ToolParam(
            name="name",
            type="string",
            description="Process name, e.g. 'notepad.exe'. Optional if pid set.",
            required=False,
        ),
        ToolParam(
            name="pid",
            type="integer",
            description="Process ID. Optional if name set.",
            required=False,
        ),
    ]

    async def execute(
        self, name: Optional[str] = None, pid: Optional[int] = None, **_: Any
    ) -> ToolResult:
        if pid:
            args = ["taskkill", "/PID", str(int(pid)), "/F"]
        elif name:
            n = name if name.lower().endswith(".exe") else f"{name}.exe"
            args = ["taskkill", "/IM", n, "/F"]
        else:
            return ToolResult(success=False, output="Provide name or pid")
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=20)
        except Exception as e:
            return ToolResult(success=False, output=str(e))
        out = (r.stdout or "") + (r.stderr or "")
        return ToolResult(
            success=r.returncode == 0,
            output=out.strip() or f"exit={r.returncode}",
            data={"exit_code": r.returncode},
        )


class NotifyTool(BaseTool):
    name = "notify"
    category = "system"
    description = "Show a Windows toast/notification balloon to the user."
    parameters = [
        ToolParam(name="title", type="string", description="Notification title."),
        ToolParam(name="message", type="string", description="Notification body."),
    ]

    async def execute(self, title: str, message: str, **_: Any) -> ToolResult:
        import base64

        # Escape via base64 to avoid PowerShell quoting issues
        t_b64 = base64.b64encode((title or "MarianaOS").encode("utf-16le")).decode("ascii")
        m_b64 = base64.b64encode((message or "").encode("utf-16le")).decode("ascii")
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "Add-Type -AssemblyName System.Drawing; "
            "$t=[Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('"
            + t_b64
            + "')); "
            "$m=[Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('"
            + m_b64
            + "')); "
            "$n=New-Object System.Windows.Forms.NotifyIcon; "
            "$n.Icon=[System.Drawing.SystemIcons]::Information; $n.Visible=$true; "
            "$n.ShowBalloonTip(4000,$t,$m,'Info'); Start-Sleep -Seconds 4; $n.Dispose()"
        )
        try:
            subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            return ToolResult(success=False, output=str(e))
        return ToolResult(success=True, output=f"Notification shown: {title}")


class GetSelectionTool(BaseTool):
    name = "get_selection"
    category = "system"
    description = (
        "Copy the current text selection (Ctrl+C) and return clipboard text. "
        "Focus the target window first."
    )
    parameters = []

    async def execute(self, **_: Any) -> ToolResult:
        # Sentinel so we detect "nothing copied" even when selection == old clipboard.
        sentinel = f"__marianaos_sel_{time.time_ns()}__"
        try:
            win_ui.set_clipboard(sentinel)
        except Exception:
            pass
        win_ui.send_hotkey("ctrl", "c")
        await asyncio.sleep(0.25)
        text = win_ui.get_clipboard()
        if text == sentinel or not text:
            return ToolResult(
                success=False,
                output=(
                    "Clipboard unchanged after Ctrl+C — nothing selected, "
                    "or focus was wrong."
                ),
            )
        return ToolResult(
            success=True,
            output=text if len(text) <= 8000 else text[:8000] + "\n...[truncated]",
            data={"length": len(text)},
        )


class WaitForWindowTool(BaseTool):
    name = "wait_for_window"
    category = "window"
    description = "Wait until a window title appears (substring match)."
    parameters = [
        ToolParam(name="title", type="string", description="Window title substring."),
        ToolParam(
            name="timeout",
            type="number",
            description="Seconds to wait (default 15, max 60).",
            required=False,
        ),
    ]

    async def execute(self, title: str, timeout: float = 15.0, **_: Any) -> ToolResult:
        ok, msg = await asyncio.to_thread(
            win_ui.wait_for_window, title, max(0.5, min(float(timeout or 15), 60))
        )
        return ToolResult(
            success=ok,
            output=f"Window ready: {msg}" if ok else msg,
            data={"title": msg} if ok else {},
        )


class WaitForControlTool(BaseTool):
    name = "wait_for_control"
    category = "ui"
    description = "Wait until a UI control appears (by name / AutomationId)."
    parameters = [
        ToolParam(name="name", type="string", description="Control Name.", required=False),
        ToolParam(name="automation_id", type="string", description="AutomationId.", required=False),
        ToolParam(name="window", type="string", description="Window title substring.", required=False),
        ToolParam(name="control_type", type="string", description="Optional type.", required=False),
        ToolParam(
            name="timeout",
            type="number",
            description="Seconds (default 10, max 60).",
            required=False,
        ),
    ]

    async def execute(
        self,
        name: str = "",
        automation_id: str = "",
        window: str = "",
        control_type: str = "",
        timeout: float = 10.0,
        **_: Any,
    ) -> ToolResult:
        if not name and not automation_id:
            return ToolResult(success=False, output="Provide name and/or automation_id")
        deadline = time.time() + max(0.5, min(float(timeout or 10), 60))
        last = None
        while time.time() < deadline:
            ctrl = win_ui.find_control(
                window=window or "",
                name=name or "",
                automation_id=automation_id or "",
                control_type=control_type or "",
            )
            if ctrl:
                info = win_ui.describe_control(ctrl)
                return ToolResult(
                    success=True,
                    output=f"Control ready: {info.get('type')} '{info.get('name')}'",
                    data=info,
                )
            await asyncio.sleep(0.3)
        return ToolResult(success=False, output="Timed out waiting for control")


class MouseDragTool(BaseTool):
    name = "mouse_drag"
    category = "input"
    description = "Drag the mouse from (x1,y1) to (x2,y2)."
    parameters = [
        ToolParam(name="x1", type="integer", description="Start X."),
        ToolParam(name="y1", type="integer", description="Start Y."),
        ToolParam(name="x2", type="integer", description="End X."),
        ToolParam(name="y2", type="integer", description="End Y."),
        ToolParam(
            name="seconds",
            type="number",
            description="Drag duration seconds (default 0.4).",
            required=False,
        ),
    ]

    async def execute(
        self, x1: int, y1: int, x2: int, y2: int, seconds: float = 0.4, **_: Any
    ) -> ToolResult:
        await asyncio.to_thread(
            win_ui.drag_mouse, int(x1), int(y1), int(x2), int(y2), float(seconds or 0.4)
        )
        return ToolResult(
            success=True,
            output=f"Dragged ({x1},{y1}) → ({x2},{y2})",
        )


class MediaKeyTool(BaseTool):
    name = "media_key"
    category = "input"
    description = "Press a media key: play_pause, next, previous, volume_up, volume_down, mute."
    parameters = [
        ToolParam(
            name="key",
            type="string",
            description="Media key name.",
            enum=["play_pause", "next", "previous", "volume_up", "volume_down", "mute"],
        ),
    ]

    async def execute(self, key: str, **_: Any) -> ToolResult:
        vk = {
            "play_pause": 0xB3,
            "next": 0xB0,
            "previous": 0xB1,
            "volume_up": 0xAF,
            "volume_down": 0xAE,
            "mute": 0xAD,
        }
        code = vk.get((key or "").lower())
        if code is None:
            return ToolResult(success=False, output=f"Unknown media key: {key}")
        ps = (
            "Add-Type -Namespace Win -Name Key -MemberDefinition '"
            "[DllImport(\"user32.dll\")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);"
            "'; "
            f"[Win.Key]::keybd_event({code},0,0,[UIntPtr]::Zero); "
            f"[Win.Key]::keybd_event({code},0,2,[UIntPtr]::Zero)"
        )
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            return ToolResult(
                success=False,
                output=(r.stderr or r.stdout or "media key failed").strip(),
            )
        return ToolResult(success=True, output=f"Pressed media key: {key}")
