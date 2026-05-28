"""檢查 GitHub Release 是否有新版本。"""

import threading
import webbrowser
from tkinter import messagebox
from urllib.request import urlopen, Request
from urllib.error import URLError
import json

from loguru import logger

from version import __version__

REPO = "nelsonlaidev/fh6-automation"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"


def parse_version(tag: str) -> tuple[int, ...]:
    """將 'v1.2.3' 或 '1.2.3' 轉為 tuple。"""
    return tuple(int(x) for x in tag.lstrip("v").split("."))


def check_update_async(parent) -> None:
    """在背景 thread 檢查更新，有新版時在主執行緒彈窗。"""
    threading.Thread(target=lambda: check(parent), daemon=True).start()


def check(parent) -> None:
    try:
        req = Request(API_URL, headers={"Accept": "application/vnd.github.v3+json"})
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())

        latest_tag = data.get("tag_name", "")
        if not latest_tag:
            return

        latest = parse_version(latest_tag)
        current = parse_version(__version__)

        if latest <= current:
            return

        logger.info("New version available: {} (current: {})", latest_tag, __version__)
        parent.after(0, lambda: prompt(parent, latest_tag))

    except (URLError, OSError, ValueError, KeyError) as e:
        logger.debug("Update check failed: {}", e)


def prompt(parent, tag: str) -> None:
    result = messagebox.askyesno(
        title="有新版本",
        message=f"發現新版本 {tag}（目前 v{__version__}）\n\n是否前往下載頁面？",
        parent=parent,
    )
    if result:
        webbrowser.open(RELEASES_URL)
