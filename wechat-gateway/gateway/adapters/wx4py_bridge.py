from __future__ import annotations

"""wx4py-based sender for Windows WeChat 4.x.

This adapter is the "OpenClaw receives command, local PC WeChat executes"
path. It uses the accessibility tree exposed by desktop WeChat and does not
modify the WeChat client or use a private protocol.
"""

import ctypes
import ctypes.wintypes
import os
import time
import winreg
from dataclasses import asdict, dataclass

import win32gui
import win32process


EXE_NAMES = {"weixin.exe", "wechat.exe"}
WECHAT_TITLE = "\u5fae\u4fe1"
NARRATOR_REG_PATH = r"SOFTWARE\Microsoft\Narrator\NoRoam"
TARGET_SEPARATORS = ("\r", "\n", ";", "；", ",", "，", "、", "|")
BROADCAST_TARGETS = {"*", "all", "@all", "所有", "所有人", "全部", "全体", "群发"}


@dataclass(frozen=True)
class Wx4pySendResult:
    ok: bool
    target: str
    text: str
    hwnd: int
    foreground_title: str
    window_class: str = ""
    target_type: str = "contact"
    driver: str = "wx4py"
    login_required: bool = False
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def ensure_accessibility_flags() -> dict[str, object]:
    """Enable the Windows flags WeChat 4.x needs to expose UIAutomation nodes."""
    registry_before: int | None = None
    try:
        key = winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            NARRATOR_REG_PATH,
            0,
            winreg.KEY_READ | winreg.KEY_WRITE,
        )
        try:
            try:
                registry_before, _ = winreg.QueryValueEx(key, "RunningState")
            except FileNotFoundError:
                registry_before = None
            winreg.SetValueEx(key, "RunningState", 0, winreg.REG_DWORD, 1)
        finally:
            key.Close()
    except Exception:
        registry_before = None

    flag_enabled = False
    try:
        user32 = ctypes.windll.user32
        user32.SystemParametersInfoW(0x0047, 1, 0, 0x01 | 0x02)
        flag = ctypes.wintypes.BOOL()
        user32.SystemParametersInfoW(0x0046, 0, ctypes.byref(flag), 0)
        flag_enabled = bool(flag.value)
    except Exception:
        flag_enabled = False

    return {"registry_before": registry_before, "screenreader_flag": flag_enabled}


def _process_path(pid: int) -> str:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(0x1000, 0, pid)
    if not handle:
        return ""
    try:
        size = ctypes.c_uint32(2048)
        buffer = ctypes.create_unicode_buffer(2048)
        ok = kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))
        return buffer.value if ok else ""
    finally:
        kernel32.CloseHandle(handle)


def _wechat_windows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    def enum_window(hwnd: int, _extra: object) -> bool:
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            path = _process_path(pid)
            exe_name = os.path.basename(path).lower()
            if exe_name not in EXE_NAMES:
                return True

            title = win32gui.GetWindowText(hwnd) or ""
            class_name = win32gui.GetClassName(hwnd) or ""
            if title != WECHAT_TITLE or not class_name.startswith("Qt"):
                return True

            visible = bool(win32gui.IsWindowVisible(hwnd))
            rect = win32gui.GetWindowRect(hwnd)
            width = max(0, rect[2] - rect[0])
            height = max(0, rect[3] - rect[1])
            on_screen = visible and rect[0] > -10000 and rect[1] > -10000
            rows.append(
                {
                    "hwnd": hwnd,
                    "pid": pid,
                    "path": path,
                    "title": title,
                    "class_name": class_name,
                    "rect": rect,
                    "area": width * height,
                    "on_screen": on_screen,
                    "visible": visible,
                }
            )
        except Exception:
            return True
        return True

    win32gui.EnumWindows(enum_window, None)
    return rows


def _pick_window() -> dict[str, object] | None:
    windows = _wechat_windows()
    if not windows:
        return None
    windows.sort(
        key=lambda row: (
            bool(row.get("on_screen")),
            int(row.get("area", 0)),
            bool(row.get("visible")),
        ),
        reverse=True,
    )
    return windows[0]


def target_validation_error(target: str) -> str:
    clean_target = str(target or "").strip()
    if not clean_target:
        return "target is required"
    if clean_target.lower() in BROADCAST_TARGETS:
        return "broadcast target is not allowed"
    if any(separator in clean_target for separator in TARGET_SEPARATORS):
        return "target must be exactly one chat"
    return ""


def send_text(target: str, text: str, target_type: str = "contact") -> Wx4pySendResult:
    clean_target = target.strip()
    clean_text = text.strip()
    target_error = target_validation_error(clean_target)
    if target_error:
        return Wx4pySendResult(False, target, text, 0, "", target_type=target_type, error=target_error)
    if not clean_text:
        return Wx4pySendResult(False, target, text, 0, "", error="text is required")

    try:
        from wx4py.core import uiautomation as uia
        from wx4py.core.uia_wrapper import UIAWrapper
        from wx4py.core.window import WeChatWindow, _count_uia_descendants
        from wx4py.features.chat import ChatWindow
    except Exception as exc:
        return Wx4pySendResult(
            False,
            clean_target,
            clean_text,
            0,
            "",
            target_type=target_type,
            error=f"wx4py not available: {type(exc).__name__}: {exc}",
        )

    ensure_accessibility_flags()
    selected = _pick_window()
    if not selected:
        return Wx4pySendResult(
            False,
            clean_target,
            clean_text,
            0,
            "",
            target_type=target_type,
            error="wechat window not found",
        )

    hwnd = int(selected["hwnd"])
    try:
        root = uia.ControlFromHandle(hwnd)
        root_class = str(getattr(root, "ClassName", "") or "")
        node_count = _count_uia_descendants(root)
        if "LoginWindow" in root_class:
            return Wx4pySendResult(
                False,
                clean_target,
                clean_text,
                hwnd,
                win32gui.GetWindowText(win32gui.GetForegroundWindow()),
                window_class=root_class,
                target_type=target_type,
                login_required=True,
                error="wechat is at login window",
            )
        if node_count < 5:
            return Wx4pySendResult(
                False,
                clean_target,
                clean_text,
                hwnd,
                win32gui.GetWindowText(win32gui.GetForegroundWindow()),
                window_class=root_class,
                target_type=target_type,
                error=(
                    "wechat UIAutomation tree is not ready; reopen this WeChat "
                    "window after accessibility flags are enabled"
                ),
            )

        window = WeChatWindow()
        window._hwnd = hwnd
        window._activate_hwnd(hwnd)
        time.sleep(0.4)
        window._uia = UIAWrapper(hwnd)
        window._initialized = True

        ok = ChatWindow(window).send_to(clean_target, clean_text, target_type=target_type)
        return Wx4pySendResult(
            ok=bool(ok),
            target=clean_target,
            text=clean_text,
            hwnd=hwnd,
            foreground_title=win32gui.GetWindowText(win32gui.GetForegroundWindow()),
            window_class=root_class,
            target_type=target_type,
            error="" if ok else "wx4py send_to returned false",
        )
    except Exception as exc:
        return Wx4pySendResult(
            False,
            clean_target,
            clean_text,
            hwnd,
            win32gui.GetWindowText(win32gui.GetForegroundWindow()),
            window_class=str(selected.get("class_name", "")),
            target_type=target_type,
            error=f"{type(exc).__name__}: {exc}",
        )
