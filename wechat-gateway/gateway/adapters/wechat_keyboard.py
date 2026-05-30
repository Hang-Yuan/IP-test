from __future__ import annotations

"""Foreground keyboard fallback for sending a PC WeChat text message.

This is intentionally narrow: it sends one text message to one target in the
currently logged-in desktop WeChat. It is a demo fallback when the installed
WeChat client does not expose a stable message event source.
"""

import ctypes
import os
import time
from dataclasses import asdict, dataclass

import psutil
import pyperclip
import win32api
import win32con
import win32gui
import win32process


WECHAT_TITLE = "\u5fae\u4fe1"
WECHAT_CLASS = "Qt51514QWindowIcon"
DEFAULT_ACCOUNT_WXID = ""
TARGET_SEPARATORS = ("\r", "\n", ";", "；", ",", "，", "、", "|")
BROADCAST_TARGETS = {"*", "all", "@all", "所有", "所有人", "全部", "全体", "群发"}


@dataclass(frozen=True)
class KeyboardSendResult:
    ok: bool
    target: str
    text: str
    hwnd: int
    foreground_title: str
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def process_matches_account(pid: int) -> bool:
    account_wxid = os.getenv("WECHAT_ACCOUNT_WXID", DEFAULT_ACCOUNT_WXID).strip()
    db_root = os.getenv("WECHAT_DB_ROOT", "").strip()
    if not account_wxid and not db_root:
        return False
    try:
        process = psutil.Process(pid)
        for opened in process.open_files():
            path = opened.path
            if db_root and path.startswith(db_root):
                return True
            if account_wxid and account_wxid in path:
                return True
    except Exception:
        return False
    return False


def find_wechat_window() -> int | None:
    matches: list[tuple[int, int, bool]] = []

    def enum_window(hwnd: int, _extra: object) -> None:
        title = win32gui.GetWindowText(hwnd)
        class_name = win32gui.GetClassName(hwnd)
        if title == WECHAT_TITLE and class_name == WECHAT_CLASS and win32gui.IsWindowVisible(hwnd):
            _thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
            matches.append((hwnd, pid, process_matches_account(pid)))

    win32gui.EnumWindows(enum_window, None)
    for hwnd, _pid, account_match in matches:
        if account_match:
            return hwnd
    return matches[0][0] if matches else None


def activate_window(hwnd: int) -> bool:
    user32 = ctypes.windll.user32
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    else:
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

    foreground = win32gui.GetForegroundWindow()
    current_thread = win32api.GetCurrentThreadId()
    foreground_thread, _ = win32process.GetWindowThreadProcessId(foreground)
    target_thread, _ = win32process.GetWindowThreadProcessId(hwnd)
    user32.AttachThreadInput(current_thread, foreground_thread, True)
    user32.AttachThreadInput(current_thread, target_thread, True)
    try:
        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)
        win32gui.SetActiveWindow(hwnd)
    finally:
        user32.AttachThreadInput(current_thread, target_thread, False)
        user32.AttachThreadInput(current_thread, foreground_thread, False)
    time.sleep(0.4)
    return win32gui.GetForegroundWindow() == hwnd


def press_key(vk: int, delay: float = 0.08) -> None:
    win32api.keybd_event(vk, 0, 0, 0)
    time.sleep(0.03)
    win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(delay)


def hotkey(*keys: int) -> None:
    for vk in keys:
        win32api.keybd_event(vk, 0, 0, 0)
        time.sleep(0.02)
    for vk in reversed(keys):
        win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.03)
    time.sleep(0.2)


def paste_text(text: str) -> None:
    pyperclip.copy(text)
    time.sleep(0.1)
    hotkey(win32con.VK_CONTROL, ord("V"))


def target_validation_error(target: str) -> str:
    clean_target = str(target or "").strip()
    if not clean_target:
        return "target is required"
    if clean_target.lower() in BROADCAST_TARGETS:
        return "broadcast target is not allowed"
    if any(separator in clean_target for separator in TARGET_SEPARATORS):
        return "target must be exactly one chat"
    return ""


def send_text(target: str, text: str) -> KeyboardSendResult:
    clean_target = target.strip()
    clean_text = text.strip()
    target_error = target_validation_error(clean_target)
    if target_error:
        return KeyboardSendResult(False, target, text, 0, "", target_error)
    if not clean_text:
        return KeyboardSendResult(False, target, text, 0, "", "text is required")

    hwnd = find_wechat_window()
    if not hwnd:
        return KeyboardSendResult(False, clean_target, clean_text, 0, "", "wechat main window not found")

    try:
        if not activate_window(hwnd):
            return KeyboardSendResult(
                False,
                clean_target,
                clean_text,
                hwnd,
                win32gui.GetWindowText(win32gui.GetForegroundWindow()),
                "failed to activate wechat window",
            )

        foreground_title = win32gui.GetWindowText(win32gui.GetForegroundWindow())
        if foreground_title != WECHAT_TITLE:
            return KeyboardSendResult(False, clean_target, clean_text, hwnd, foreground_title, "foreground is not wechat")

        hotkey(win32con.VK_CONTROL, ord("F"))
        time.sleep(0.5)
        paste_text(clean_target)
        time.sleep(0.6)
        press_key(win32con.VK_RETURN, delay=1.0)
        paste_text(clean_text)
        time.sleep(0.3)
        press_key(win32con.VK_RETURN)
        return KeyboardSendResult(True, clean_target, clean_text, hwnd, foreground_title)
    except Exception as exc:
        return KeyboardSendResult(
            False,
            clean_target,
            clean_text,
            hwnd,
            win32gui.GetWindowText(win32gui.GetForegroundWindow()),
            f"{type(exc).__name__}: {exc}",
        )
