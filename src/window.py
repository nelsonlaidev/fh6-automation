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
    """檢查目標視窗是否因權限較高而可能攔截 SendInput。

    回傳 True 代表偵測到可能的權限不一致（我們未提升，但無法對目標視窗發送測試訊息）。
    """
    if is_self_elevated():
        return False

    # 嘗試對目標視窗發送一個無害的 WM_NULL 訊息。
    # 如果被 UIPI 攔截，SendMessageTimeout 會失敗。
    import ctypes.wintypes

    SMTO_ABORTIFHUNG = 0x0002
    WM_NULL = 0x0000
    result = ctypes.wintypes.DWORD()

    ret = ctypes.windll.user32.SendMessageTimeoutW(
        win._hWnd,
        WM_NULL,
        0,
        0,
        SMTO_ABORTIFHUNG,
        100,
        ctypes.byref(result),
    )

    if ret == 0:
        logger.warning("window: 偵測到權限不一致，SendInput 無法送達遊戲視窗（請勿以系統管理員身分執行遊戲）")
        return True

    return False
