"""System info and shell tools."""

from __future__ import annotations

import asyncio
import os
import platform
from typing import Any

from tools.base import BaseTool, ToolParam, ToolResult


class SystemInfoTool(BaseTool):
    name = "system_info"
    description = "Get basic system information (OS, CPU, memory, hostname)."
    parameters = []

    async def execute(self, **_: Any) -> ToolResult:
        import psutil

        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\" if os.name == "nt" else "/")
        info = {
            "hostname": platform.node(),
            "os": f"{platform.system()} {platform.release()} ({platform.version()})",
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=0.3),
            "memory_total_gb": round(mem.total / (1024**3), 2),
            "memory_used_gb": round(mem.used / (1024**3), 2),
            "memory_percent": mem.percent,
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_used_percent": disk.percent,
            "user": os.environ.get("USERNAME") or os.environ.get("USER"),
        }
        lines = [f"{k}: {v}" for k, v in info.items()]
        return ToolResult(success=True, output="\n".join(lines), data=info)


class RunShellTool(BaseTool):
    name = "run_shell"
    description = (
        "Run a shell command on the PC (PowerShell on Windows). "
        "Destructive / powerful — only use when needed. Timeout default 60s."
    )
    destructive = True
    parameters = [
        ToolParam(name="command", type="string", description="Command to run."),
        ToolParam(
            name="timeout",
            type="integer",
            description="Timeout in seconds (default 60, max 180).",
            required=False,
        ),
        ToolParam(
            name="shell",
            type="string",
            description="powershell or cmd. Default powershell.",
            required=False,
            enum=["powershell", "cmd"],
        ),
    ]

    async def execute(
        self,
        command: str,
        timeout: int = 60,
        shell: str = "powershell",
        **_: Any,
    ) -> ToolResult:
        timeout = max(5, min(int(timeout), 180))
        if shell == "cmd":
            args = ["cmd", "/c", command]
        else:
            args = [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                return ToolResult(success=False, output=f"Command timed out after {timeout}s")
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to run command: {e}")

        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        out = stdout
        if stderr.strip():
            out = (out + "\n[stderr]\n" + stderr).strip()
        if len(out) > 15000:
            out = out[:15000] + "\n...[truncated]"
        return ToolResult(
            success=proc.returncode == 0,
            output=out or f"(no output, exit={proc.returncode})",
            data={"exit_code": proc.returncode},
        )


class ListProcessesTool(BaseTool):
    name = "list_processes"
    description = "List running processes, optionally filtered by name."
    parameters = [
        ToolParam(
            name="filter",
            type="string",
            description="Optional case-insensitive name filter (e.g. 'chrome', 'cursor').",
            required=False,
        ),
        ToolParam(
            name="limit",
            type="integer",
            description="Max results (default 30).",
            required=False,
        ),
    ]

    async def execute(self, filter: str = "", limit: int = 30, **_: Any) -> ToolResult:
        import psutil

        rows = []
        fl = filter.lower().strip()
        for p in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                name = p.info["name"] or ""
                if fl and fl not in name.lower():
                    continue
                mem_mb = round((p.info["memory_info"].rss / (1024**2)), 1) if p.info["memory_info"] else 0
                rows.append(f"{p.info['pid']:>6}  {mem_mb:>8} MB  {name}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            if len(rows) >= max(1, min(limit, 100)):
                break
        header = f"{'PID':>6}  {'MEMORY':>8}     NAME\n"
        return ToolResult(
            success=True,
            output=header + "\n".join(rows) if rows else "No matching processes.",
            data={"count": len(rows)},
        )


class ClipboardGetTool(BaseTool):
    name = "clipboard_get"
    description = "Read the current clipboard text."
    parameters = []

    async def execute(self, **_: Any) -> ToolResult:
        import pyperclip

        try:
            text = pyperclip.paste()
        except Exception as e:
            return ToolResult(success=False, output=f"Clipboard read failed: {e}")
        if len(text) > 8000:
            shown = text[:8000] + "\n...[truncated]"
        else:
            shown = text
        return ToolResult(success=True, output=shown or "(empty clipboard)", data={"length": len(text)})


class ClipboardSetTool(BaseTool):
    name = "clipboard_set"
    description = "Set the clipboard text."
    destructive = True
    parameters = [
        ToolParam(name="text", type="string", description="Text to put on the clipboard."),
    ]

    async def execute(self, text: str, **_: Any) -> ToolResult:
        import pyperclip

        pyperclip.copy(text)
        return ToolResult(success=True, output=f"Clipboard set ({len(text)} chars)")
