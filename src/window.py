from dataclasses import dataclass

import pygetwindow as gw
import win32gui

WINDOW_TITLE_HINTS = "Forza Horizon 6"


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
            return wins[0]

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
