import ctypes
from dataclasses import dataclass

import pygetwindow as gw
import win32gui
from loguru import logger

WINDOW_TITLE_HINTS = ["Forza Horizon 6"]


@dataclass
class Rect:
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


def find_forza() -> gw.Window | None:
    for hint in WINDOW_TITLE_HINTS:
        wins = [w for w in gw.getWindowsWithTitle(hint) if w.title and w.visible]

        if wins:
            wins.sort(key=lambda w: w.width * w.height, reverse=True)
            logger.debug(
                "window: 找到 '{}' ({}x{})",
                wins[0].title,
                wins[0].width,
                wins[0].height,
            )
            return wins[0]

    logger.debug("window: 找不到符合的視窗")
    return None


def client_rect(win: gw.Window) -> Rect:
    hwnd = win._hWnd
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    sx, sy = win32gui.ClientToScreen(hwnd, (left, top))
    return Rect(left=sx, top=sy, width=right - left, height=bottom - top)


def is_foreground(win: gw.Window) -> bool:
    try:
        return win32gui.GetForegroundWindow() == win._hWnd
    except Exception:
        return False


def is_self_elevated() -> bool:
    """檢查本程式是否以系統管理員身分執行。"""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def check_elevation_mismatch(win: gw.Window) -> bool:
    """檢查目標視窗的程序是否以較高權限執行。

    回傳 True 代表我們未提升，但目標程序已提升，SendInput 會被 UIPI 攔截。
    """
    if is_self_elevated():
        return False

    import win32api
    import win32con
    import win32process
    import win32security

    try:
        _, pid = win32process.GetWindowThreadProcessId(win._hWnd)
        hProcess = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        try:
            hToken = win32security.OpenProcessToken(hProcess, win32con.TOKEN_QUERY)
            elevation = win32security.GetTokenInformation(hToken, win32security.TokenElevation)
            if elevation:
                logger.warning("window: 偵測到權限不一致，SendInput 無法送達遊戲視窗（請勿以系統管理員身分執行遊戲）")
                return True
        finally:
            win32api.CloseHandle(hProcess)
    except Exception as e:
        # 無法查詢目標程序 token（例如受保護程序），保守假設有問題
        logger.warning("window: 無法檢查遊戲程序權限：{}", e)
        return True

    return False
