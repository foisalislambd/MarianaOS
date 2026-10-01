"""Windows UI helpers built on uiautomation (+ Pillow for rare screenshots)."""

from __future__ import annotations

import base64
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

import uiautomation as auto


def find_window(title_substr: str, timeout: float = 3.0) -> Optional[auto.WindowControl]:
    """Find a top-level window whose Name contains title_substr (case-insensitive)."""
    needle = (title_substr or "").strip().lower()
    if not needle:
        return None
    deadline = time.time() + max(0.2, timeout)
    while time.time() < deadline:
        try:
            root = auto.GetRootControl()
            for win in root.GetChildren():
                try:
                    name = (win.Name or "").lower()
                    ctype = win.ControlTypeName or ""
                    if needle in name and "Window" in ctype:
                        return auto.WindowControl(Handle=win.NativeWindowHandle)
                except Exception:
                    continue
        except Exception:
            pass
        time.sleep(0.15)
    return None


def focus_window(title_substr: str, timeout: float = 3.0) -> Tuple[bool, str]:
    win = find_window(title_substr, timeout=timeout)
    if not win:
        return False, f"No window matching '{title_substr}'"
    try:
        if hasattr(win, "IsMinimize") and win.IsMinimize():
            win.Restore()
        win.SetActive()
        try:
            win.SetFocus()
        except Exception:
            pass
        return True, win.Name or title_substr
    except Exception as e:
        return False, f"Could not focus window: {e}"


def list_windows(filter_substr: str = "") -> List[str]:
    titles: List[str] = []
    seen: set[str] = set()
    fl = (filter_substr or "").lower().strip()
    try:
        root = auto.GetRootControl()
        for win in root.GetChildren():
            name = (getattr(win, "Name", None) or "").strip()
            if not name:
                continue
            if fl and fl not in name.lower():
                continue
            if name not in seen:
                seen.add(name)
                titles.append(name)
    except Exception:
        pass
    return titles


def get_active_window_info() -> Optional[Dict[str, Any]]:
    try:
        ctrl = auto.GetForegroundControl()
        if not ctrl:
            return None
        win = ctrl
        for _ in range(12):
            if "Window" in (win.ControlTypeName or ""):
                break
            parent = win.GetParentControl()
            if not parent:
                break
            win = parent
        rect = win.BoundingRectangle
        return {
            "title": win.Name or "",
            "left": rect.left,
            "top": rect.top,
            "width": rect.width(),
            "height": rect.height(),
            "control": win.ControlTypeName,
        }
    except Exception:
        return None


def minimize_window(title_substr: str) -> Tuple[bool, str]:
    win = find_window(title_substr)
    if not win:
        return False, f"No window matching '{title_substr}'"
    try:
        win.Minimize()
        return True, win.Name or title_substr
    except Exception as e:
        return False, str(e)


def maximize_window(title_substr: str) -> Tuple[bool, str]:
    win = find_window(title_substr)
    if not win:
        return False, f"No window matching '{title_substr}'"
    try:
        win.Maximize()
        return True, win.Name or title_substr
    except Exception as e:
        return False, str(e)


def restore_window(title_substr: str) -> Tuple[bool, str]:
    win = find_window(title_substr)
    if not win:
        return False, f"No window matching '{title_substr}'"
    try:
        win.Restore()
        return True, win.Name or title_substr
    except Exception as e:
        return False, str(e)


def close_window(title_substr: str) -> Tuple[bool, str]:
    win = find_window(title_substr)
    if not win:
        return False, f"No window matching '{title_substr}'"
    name = win.Name or title_substr
    try:
        pattern = win.GetWindowPattern()
        if pattern:
            pattern.Close()
            return True, name
    except Exception:
        pass
    try:
        focus_window(title_substr, timeout=1.0)
        send_hotkey("alt", "f4")
        return True, name
    except Exception as e:
        return False, str(e)


def resize_window(
    title_substr: str, left: int, top: int, width: int, height: int
) -> Tuple[bool, str]:
    win = find_window(title_substr)
    if not win:
        return False, f"No window matching '{title_substr}'"
    try:
        try:
            if win.IsMaximize():
                win.Restore()
        except Exception:
            pass
        ok = win.MoveWindow(int(left), int(top), max(1, int(width)), max(1, int(height)))
        if ok is False:
            return False, f"MoveWindow returned False for '{win.Name or title_substr}'"
        return True, win.Name or title_substr
    except Exception as e:
        return False, str(e)


def wait_for_window(title_substr: str, timeout: float = 15.0) -> Tuple[bool, str]:
    deadline = time.time() + max(0.5, timeout)
    while time.time() < deadline:
        win = find_window(title_substr, timeout=0.3)
        if win:
            return True, win.Name or title_substr
        time.sleep(0.25)
    return False, f"Timed out waiting for window '{title_substr}'"


def drag_mouse(x1: int, y1: int, x2: int, y2: int, seconds: float = 0.4) -> None:
    # moveSpeed ~ relative speed; keep modest for reliability
    speed = max(0.5, min(float(seconds or 0.4) * 2.0, 4.0))
    auto.DragDrop(int(x1), int(y1), int(x2), int(y2), moveSpeed=speed)


def click_xy(x: int, y: int, button: str = "left", clicks: int = 1) -> None:
    btn = button.lower()
    n = max(1, min(int(clicks), 3))
    for i in range(n):
        if btn == "right":
            auto.RightClick(x, y)
        elif btn == "middle":
            auto.MiddleClick(x, y)
        else:
            auto.Click(x, y)
        if i + 1 < n:
            time.sleep(0.08)


def move_mouse(x: int, y: int) -> None:
    auto.SetCursorPos(x, y)


def scroll(clicks: int, x: Optional[int] = None, y: Optional[int] = None) -> None:
    if x is not None and y is not None:
        auto.SetCursorPos(x, y)
        time.sleep(0.05)
    amount = abs(int(clicks))
    if clicks >= 0:
        auto.WheelUp(amount)
    else:
        auto.WheelDown(amount)


def send_keys(text: str) -> None:
    """Paste text via clipboard (reliable for Unicode)."""
    set_clipboard(text)
    time.sleep(0.05)
    auto.SendKeys("{Ctrl}v")


def send_hotkey(*keys: str) -> None:
    """Send a key chord. Example: send_hotkey('ctrl','shift','p') → Ctrl+Shift+P."""
    mapping = {
        "ctrl": "Ctrl",
        "control": "Ctrl",
        "alt": "Alt",
        "shift": "Shift",
        "win": "Win",
        "windows": "Win",
        "enter": "Enter",
        "return": "Enter",
        "esc": "Escape",
        "escape": "Escape",
        "tab": "Tab",
        "backspace": "Backspace",
        "delete": "Delete",
        "del": "Delete",
        "up": "Up",
        "down": "Down",
        "left": "Left",
        "right": "Right",
        "space": "Space",
        "home": "Home",
        "end": "End",
        "pageup": "PageUp",
        "pagedown": "PageDown",
    }
    hold = {"ctrl", "control", "alt", "shift", "win", "windows"}
    mods: List[str] = []
    normals: List[str] = []
    for k in keys:
        kl = str(k).lower().strip()
        if kl in hold:
            mods.append("{" + mapping[kl] + "}")
        elif kl in mapping:
            normals.append("{" + mapping[kl] + "}")
        elif len(kl) == 1:
            normals.append(kl)
        elif kl.startswith("f") and kl[1:].isdigit():
            normals.append("{" + kl.upper() + "}")
        else:
            normals.append("{" + kl.capitalize() + "}")
    # uiautomation: {Ctrl}{Shift}p holds modifiers with the following key
    auto.SendKeys("".join(mods + normals))


def press_key(key: str, times: int = 1) -> None:
    n = max(1, min(int(times), 20))
    for _ in range(n):
        send_hotkey(key)
        time.sleep(0.03)


def mouse_position() -> Tuple[int, int]:
    return auto.GetCursorPos()


def screen_size() -> Tuple[int, int]:
    return auto.GetScreenSize()


def get_clipboard() -> str:
    try:
        text = auto.GetClipboardText()
        return text if text is not None else ""
    except Exception:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", "Get-Clipboard"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return r.stdout


def set_clipboard(text: str) -> None:
    try:
        auto.SetClipboardText(text or "")
        return
    except Exception:
        pass
    b64 = base64.b64encode((text or "").encode("utf-16le")).decode("ascii")
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                "Set-Clipboard -Value "
                "([System.Text.Encoding]::Unicode.GetString("
                f"[Convert]::FromBase64String('{b64}')))"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )


_TYPE_MAP = {
    "button": auto.ButtonControl,
    "edit": auto.EditControl,
    "text": auto.TextControl,
    "menu": auto.MenuControl,
    "menuitem": auto.MenuItemControl,
    "list": auto.ListControl,
    "listitem": auto.ListItemControl,
    "tree": auto.TreeControl,
    "treeitem": auto.TreeItemControl,
    "checkbox": auto.CheckBoxControl,
    "combobox": auto.ComboBoxControl,
    "tab": auto.TabControl,
    "tabitem": auto.TabItemControl,
    "document": auto.DocumentControl,
    "pane": auto.PaneControl,
    "window": auto.WindowControl,
    "hyperlink": auto.HyperlinkControl,
    "image": auto.ImageControl,
    "slider": auto.SliderControl,
}


def find_control(
    *,
    window: str = "",
    name: str = "",
    automation_id: str = "",
    control_type: str = "",
    depth: int = 12,
) -> Optional[auto.Control]:
    """Find a UI control by Name / AutomationId under an optional window."""
    root: auto.Control
    if window:
        win = find_window(window)
        if not win:
            return None
        root = win
    else:
        root = auto.GetRootControl()

    kwargs: Dict[str, Any] = {
        "searchFromControl": root,
        "searchDepth": max(1, min(depth, 30)),
    }
    if name:
        kwargs["Name"] = name
    if automation_id:
        kwargs["AutomationId"] = automation_id

    ct = (control_type or "").lower().strip()
    cls = _TYPE_MAP.get(ct)

    if cls is not None:
        try:
            ctrl = cls(**kwargs)
            if ctrl.Exists(1, 0):
                return ctrl
        except Exception:
            pass
    else:
        try:
            ctrl = auto.Control(**kwargs)
            if ctrl.Exists(1, 0):
                return ctrl
        except Exception:
            pass

    # Fuzzy walk fallback (substring name match)
    needle = (name or "").lower()
    aid = automation_id
    try:
        for c, _d in auto.WalkControl(root, maxDepth=depth):
            try:
                if aid and (getattr(c, "AutomationId", "") or "") != aid:
                    continue
                cname = (c.Name or "").lower()
                if needle and needle not in cname and cname != needle:
                    continue
                if not needle and not aid:
                    continue
                if ct and ct not in (c.ControlTypeName or "").lower():
                    continue
                return c
            except Exception:
                continue
    except Exception:
        pass
    return None


def describe_control(ctrl: auto.Control) -> Dict[str, Any]:
    rect = ctrl.BoundingRectangle
    return {
        "name": ctrl.Name or "",
        "automation_id": getattr(ctrl, "AutomationId", "") or "",
        "type": ctrl.ControlTypeName or "",
        "class_name": getattr(ctrl, "ClassName", "") or "",
        "left": rect.left,
        "top": rect.top,
        "width": rect.width(),
        "height": rect.height(),
    }


def ui_tree(
    window: str = "",
    max_depth: int = 4,
    max_nodes: int = 80,
) -> List[Dict[str, Any]]:
    if window:
        win = find_window(window)
        if not win:
            return []
        root: auto.Control = win
    else:
        info = get_active_window_info()
        if info and info.get("title"):
            win = find_window(info["title"])
            root = win if win else auto.GetRootControl()
        else:
            root = auto.GetRootControl()

    nodes: List[Dict[str, Any]] = []
    try:
        for c, d in auto.WalkControl(root, maxDepth=max(1, min(max_depth, 8))):
            name = (c.Name or "").strip()
            aid = getattr(c, "AutomationId", "") or ""
            if not name and not aid:
                continue
            item = describe_control(c)
            item["depth"] = d
            nodes.append(item)
            if len(nodes) >= max(1, min(max_nodes, 200)):
                break
    except Exception:
        pass
    return nodes


def click_control(
    *,
    window: str = "",
    name: str = "",
    automation_id: str = "",
    control_type: str = "",
    double: bool = False,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    ctrl = find_control(
        window=window,
        name=name,
        automation_id=automation_id,
        control_type=control_type,
    )
    if not ctrl:
        return False, "Control not found", None
    info = describe_control(ctrl)
    try:
        ctrl.SetFocus()
    except Exception:
        pass
    try:
        if double:
            ctrl.DoubleClick()
        else:
            ctrl.Click()
        return True, f"Clicked {info['type']} '{info['name']}'", info
    except Exception as e:
        try:
            r = ctrl.BoundingRectangle
            x = r.left + max(1, r.width()) // 2
            y = r.top + max(1, r.height()) // 2
            if double:
                auto.Click(x, y)
                time.sleep(0.05)
                auto.Click(x, y)
            else:
                auto.Click(x, y)
            return True, f"Clicked (coords) {info['type']} '{info['name']}'", info
        except Exception as e2:
            return False, f"Click failed: {e}; {e2}", info
