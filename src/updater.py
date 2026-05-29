"""更新檢查與下載。

公開介面：
- check_async(callback)：背景檢查 GitHub Release，結果丟回 Tk 主執行緒。
- download_async(...)：背景下載 installer，回報進度。
- UpdateDialog：顯示新版資訊 + release notes + 一鍵下載安裝。
- prompt_update(parent, conf, info, on_close)：開啟 UpdateDialog。
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import webbrowser
from dataclasses import dataclass
from typing import Callable, Literal
from urllib.error import URLError
from urllib.request import Request, urlopen

import customtkinter as ctk
from loguru import logger

import config as cfg
from version import __version__

REPO = "nelsonlaidev/fh6-automation"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"
INSTALLER_ASSET_PREFIX = "FH6Automation_Setup"

CHECK_TIMEOUT_S = 5
DOWNLOAD_TIMEOUT_S = 60
CHUNK_SIZE = 64 * 1024


Version = tuple[int, int, int]


@dataclass
class UpdateInfo:
    tag: str
    version: Version
    body: str
    installer_url: str  # 空字串代表沒有 installer asset，需 fallback 開瀏覽器


@dataclass
class CheckResult:
    status: Literal["available", "up_to_date", "error"]
    info: UpdateInfo | None = None
    error: str = ""


def parse_version(tag: str) -> Version | None:
    """嚴格解析 'vX.Y.Z' 或 'X.Y.Z'，無法解析回傳 None。

    後綴（'-rc1', '+build' 等）會被忽略。
    """
    if not tag:
        return None
    m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", tag.strip())
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def find_installer_url(assets: list[dict]) -> str:
    for asset in assets:
        name = asset.get("name", "")
        if name.startswith(INSTALLER_ASSET_PREFIX) and name.endswith(".exe"):
            return asset.get("browser_download_url", "")
    return ""


def check() -> CheckResult:
    """同步檢查；外部請用 check_async。"""
    current = parse_version(__version__)
    if current is None:
        logger.warning("Cannot parse current version: {}", __version__)
        return CheckResult(status="error", error=f"無法解析目前版本：{__version__}")

    try:
        req = Request(API_URL, headers={"Accept": "application/vnd.github.v3+json"})
        with urlopen(req, timeout=CHECK_TIMEOUT_S) as resp:
            data = json.loads(resp.read())
    except (URLError, OSError) as e:
        logger.debug("Update check network error: {}", e)
        return CheckResult(status="error", error=f"連線失敗：{e}")
    except (ValueError, KeyError) as e:
        logger.warning("Update check parse error: {}", e)
        return CheckResult(status="error", error=f"回應格式錯誤：{e}")

    latest_tag = data.get("tag_name", "")
    latest = parse_version(latest_tag)
    if latest is None:
        logger.warning("Cannot parse latest tag: {!r}", latest_tag)
        return CheckResult(status="error", error=f"無法解析版本號：{latest_tag!r}")

    if latest <= current:
        return CheckResult(status="up_to_date")

    info = UpdateInfo(
        tag=latest_tag,
        version=latest,
        body=data.get("body", "") or "",
        installer_url=find_installer_url(data.get("assets", [])),
    )
    logger.info("New version available: {} (current: {})", latest_tag, __version__)
    return CheckResult(status="available", info=info)


def check_async(parent, callback: Callable[[CheckResult], None]) -> None:
    """背景檢查，結果在 Tk 主執行緒回呼。"""

    def worker() -> None:
        result = check()
        try:
            parent.after(0, lambda: callback(result))
        except Exception:
            # parent 可能已被銷毀；忽略
            logger.debug("check_async callback skipped (parent destroyed)")

    threading.Thread(target=worker, name="updater-check", daemon=True).start()


class Download:
    """背景下載 installer，可中途取消。"""

    def __init__(
        self,
        parent,
        url: str,
        dest: str,
        on_progress: Callable[[int, int], None],
        on_done: Callable[[str], None],
        on_error: Callable[[str], None],
    ) -> None:
        self.parent = parent
        self.url = url
        self.dest = dest
        self.on_progress = on_progress
        self.on_done = on_done
        self.on_error = on_error
        self.cancel_evt = threading.Event()
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        self.thread = threading.Thread(
            target=self.run, name="updater-download", daemon=True
        )
        self.thread.start()

    def cancel(self) -> None:
        self.cancel_evt.set()

    def post(self, fn: Callable[[], None]) -> None:
        try:
            self.parent.after(0, fn)
        except Exception:
            pass

    def run(self) -> None:
        tmp_path = self.dest + ".part"
        try:
            req = Request(self.url, headers={"Accept": "application/octet-stream"})
            with urlopen(req, timeout=DOWNLOAD_TIMEOUT_S) as resp:
                total = int(resp.headers.get("Content-Length", "0") or 0)
                downloaded = 0
                with open(tmp_path, "wb") as f:
                    while True:
                        if self.cancel_evt.is_set():
                            raise OSError("使用者取消")
                        chunk = resp.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        self.post(lambda d=downloaded, t=total: self.on_progress(d, t))

            os.replace(tmp_path, self.dest)
            self.post(lambda: self.on_done(self.dest))

        except Exception as e:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            if self.cancel_evt.is_set():
                logger.info("Download cancelled by user")
                return
            logger.warning("Download failed: {}", e)
            self.post(lambda err=str(e): self.on_error(err))


def installer_temp_path(tag: str) -> str:
    safe_tag = re.sub(r"[^A-Za-z0-9._-]", "_", tag) or "latest"
    return os.path.join(tempfile.gettempdir(), f"FH6Automation_Setup_{safe_tag}.exe")


def launch_installer_and_quit(parent, installer_path: str) -> None:
    """啟動 silent installer 然後關閉 app，installer 會自動重啟新版本。"""
    try:
        # 用 detached process 確保 app 退出後 installer 仍能跑
        flags = 0
        creationflags = 0
        if sys.platform == "win32":
            creationflags = (
                subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]
                | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        subprocess.Popen(
            [installer_path, "/VERYSILENT", "/SUPPRESSMSGBOXES"],
            close_fds=True,
            creationflags=creationflags,
        )
        logger.info("Launched silent installer: {}", installer_path)
    except OSError as e:
        logger.error("Failed to launch installer: {}", e)
        raise
    parent.after(200, parent.quit)


def remember_skip(tag: str) -> None:
    """把 tag 寫入 config.ini 的 skipped_version。"""
    conf = cfg.load()
    conf.general.skipped_version = tag
    cfg.save(conf)
    logger.info("Skipped version recorded: {}", tag)


def clear_skip() -> None:
    conf = cfg.load()
    conf.general.skipped_version = ""
    cfg.save(conf)
    logger.info("Skipped version cleared")


def open_releases_page() -> None:
    webbrowser.open(RELEASES_URL)


INLINE_CODE_RE = re.compile(r"`([^`]+)`")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
BULLET_RE = re.compile(r"^[-*]\s+(.*)$")


# Markdown inline 樣式
INLINE_RE = re.compile(
    r"`([^`]+)`"  # group 1: code
    r"|\*\*([^*]+)\*\*"  # group 2: bold
    r"|\[([^\]]+)\]\(([^)]+)\)"  # group 3: link text, group 4: link href
)


def render_markdown(box: ctk.CTkTextbox, body: str) -> None:
    """把 markdown 文字渲染到 CTkTextbox。

    支援：
    - `#`, `##`, `###`+ 標題（最大 3 級，再深的視為 h3）
    - `- item` / `* item` 項目符號
    - `**bold**`、`` `code` `` 行內樣式
    - `[text](url)` 行內連結（藍色底線、可點擊）
    - 其他原樣輸出

    為了讓 CJK 內容能正確斷行（Tk 的 wrap="word" 不認 ZWSP），
    bullet tag 改用 wrap="char"，每字元都是斷點。
    其餘內容（標題、純段落）保持 wrap="word"，英文 word 不會被截斷。
    """
    import tkinter.font as tkfont

    text = box._textbox
    text.configure(state="normal")
    text.delete("1.0", "end")

    # 取 textbox 預設字型，bold/heading 只改 weight 和 size 不換家族。
    box_font = tkfont.Font(font=text.cget("font"))
    family = box_font.actual("family")
    size = box_font.actual("size")

    text.tag_configure("h1", font=(family, size + 6, "bold"), spacing1=10, spacing3=4)
    text.tag_configure("h2", font=(family, size + 3, "bold"), spacing1=8, spacing3=3)
    text.tag_configure("h3", font=(family, size + 1, "bold"), spacing1=6, spacing3=2)
    # 關鍵：bullet 用 wrap="char" 才能在中文之間斷行。
    text.tag_configure("bullet", lmargin1=4, lmargin2=22, spacing3=2, wrap="char")
    text.tag_configure("bold", font=(family, size, "bold"))
    text.tag_configure("code", font=("Consolas", size), background="#2b2b2b")
    text.tag_configure("link", foreground="#3b82f6", underline=True)

    state: dict = {"link_count": 0}

    for raw in body.splitlines():
        line = raw.rstrip()
        if not line.strip():
            text.insert("end", "\n")
            continue

        m = HEADING_RE.match(line)
        if m:
            level = min(len(m.group(1)), 3)
            text.insert("end", m.group(2) + "\n", f"h{level}")
            continue

        m = BULLET_RE.match(line)
        if m:
            text.insert("end", "• ", "bullet")
            insert_inline(text, m.group(1), ("bullet",), state)
            text.insert("end", "\n", "bullet")
            continue

        insert_inline(text, line, (), state)
        text.insert("end", "\n")

    text.configure(state="disabled")


def insert_inline(
    text,
    line: str,
    base_tags: tuple[str, ...] = (),
    state: dict | None = None,
) -> None:
    """處理一行內的 `code`、**bold**、[text](url)，依序插入到 tk.Text。"""
    pos = 0
    for m in INLINE_RE.finditer(line):
        if m.start() > pos:
            text.insert("end", line[pos : m.start()], base_tags)

        if m.group(1) is not None:
            text.insert("end", m.group(1), base_tags + ("code",))
        elif m.group(2) is not None:
            text.insert("end", m.group(2), base_tags + ("bold",))
        else:
            label = m.group(3)
            href = m.group(4)
            if state is not None:
                state["link_count"] += 1
                tag = f"link-{state['link_count']}"
            else:
                tag = "link-0"
            text.tag_configure(tag, foreground="#3b82f6", underline=True)
            text.tag_bind(
                tag,
                "<Button-1>",
                lambda e, url=href: webbrowser.open(url),
            )
            text.tag_bind(tag, "<Enter>", lambda e: text.configure(cursor="hand2"))
            text.tag_bind(tag, "<Leave>", lambda e: text.configure(cursor=""))
            text.insert("end", label, base_tags + ("link", tag))

        pos = m.end()

    if pos < len(line):
        text.insert("end", line[pos:], base_tags)


class UpdateDialog(ctk.CTkToplevel):
    """新版本提示對話框：顯示 release notes，提供下載安裝 / 跳過 / 稍後。"""

    PHASE_PROMPT = "prompt"
    PHASE_DOWNLOAD = "download"
    PHASE_ERROR = "error"

    def __init__(self, parent, info: UpdateInfo) -> None:
        super().__init__(parent)
        self.title("有新版本")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.parent_app = parent
        self.info = info
        self.download: Download | None = None
        self.phase = self.PHASE_PROMPT

        w, h = 520, 460
        try:
            x = parent.winfo_x() + max(0, (parent.winfo_width() - w) // 2)
            y = parent.winfo_y() + max(0, (parent.winfo_height() - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            self.geometry(f"{w}x{h}")

        self.build_ui()
        self.after(100, self.focus)

    def build_ui(self) -> None:
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=20, pady=16)

        ctk.CTkLabel(
            outer,
            text=f"發現新版本 {self.info.tag}",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            outer,
            text=f"目前版本 v{__version__}",
            text_color="gray60",
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", pady=(2, 12))

        ctk.CTkLabel(
            outer,
            text="更新內容",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w")

        self.notes_box = ctk.CTkTextbox(outer, height=240, wrap="word")
        self.notes_box.pack(fill="both", expand=True, pady=(4, 12))
        body = self.info.body.strip() or "（這個版本沒有提供更新說明）"
        render_markdown(self.notes_box, body)
        self.notes_box.configure(state="disabled")

        self.status_lbl = ctk.CTkLabel(outer, text="", text_color="gray60")
        self.status_lbl.pack(anchor="w")

        self.progress = ctk.CTkProgressBar(outer)
        self.progress.set(0)
        # 預設先不 pack；進入下載階段才顯示

        self.btn_row = ctk.CTkFrame(outer, fg_color="transparent")
        self.btn_row.pack(fill="x", pady=(8, 0))

        self.btn_skip = ctk.CTkButton(
            self.btn_row,
            text="跳過此版本",
            fg_color="transparent",
            border_width=1,
            width=110,
            command=self.on_skip,
        )
        self.btn_skip.pack(side="left")

        self.btn_install = ctk.CTkButton(
            self.btn_row,
            text="立即更新",
            width=110,
            command=self.on_install,
        )
        self.btn_install.pack(side="right")

        self.btn_later = ctk.CTkButton(
            self.btn_row,
            text="稍後再說",
            fg_color="transparent",
            border_width=1,
            width=110,
            command=self.on_later,
        )
        self.btn_later.pack(side="right", padx=(0, 8))

    def on_skip(self) -> None:
        try:
            remember_skip(self.info.tag)
        except OSError as e:
            logger.warning("Failed to save skipped_version: {}", e)
        self.destroy()

    def on_later(self) -> None:
        self.destroy()

    def on_install(self) -> None:
        if not self.info.installer_url:
            # 沒有 installer asset：fallback 開瀏覽器
            open_releases_page()
            self.destroy()
            return
        self.enter_download_phase()

    def enter_download_phase(self) -> None:
        self.phase = self.PHASE_DOWNLOAD
        self.btn_skip.configure(state="disabled")
        self.btn_later.configure(state="disabled")
        self.btn_install.configure(text="取消", command=self.on_cancel_download)
        self.progress.pack(fill="x", pady=(4, 4), before=self.status_lbl)
        self.status_lbl.configure(text="準備下載…", text_color="gray60")

        dest = installer_temp_path(self.info.tag)
        # 清掉舊的 .part 殘留
        part = dest + ".part"
        try:
            if os.path.exists(part):
                os.remove(part)
        except OSError:
            pass

        self.download = Download(
            parent=self,
            url=self.info.installer_url,
            dest=dest,
            on_progress=self.on_progress,
            on_done=self.on_download_done,
            on_error=self.on_download_error,
        )
        self.download.start()

    def on_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            self.progress.set(downloaded / total)
            mb_d = downloaded / (1024 * 1024)
            mb_t = total / (1024 * 1024)
            self.status_lbl.configure(text=f"下載中… {mb_d:.1f} / {mb_t:.1f} MB")
        else:
            mb_d = downloaded / (1024 * 1024)
            self.status_lbl.configure(text=f"下載中… {mb_d:.1f} MB")

    def on_cancel_download(self) -> None:
        if self.download:
            self.download.cancel()
        self.destroy()

    def on_download_done(self, installer_path: str) -> None:
        self.status_lbl.configure(text="準備安裝…", text_color="gray60")
        self.progress.set(1.0)
        # 短暫延遲讓使用者看到完成狀態
        self.after(300, lambda: self.start_install(installer_path))

    def start_install(self, installer_path: str) -> None:
        try:
            launch_installer_and_quit(self.parent_app, installer_path)
        except OSError as e:
            self.show_error(f"無法啟動安裝程式：{e}")

    def on_download_error(self, error: str) -> None:
        self.show_error(f"下載失敗：{error}")

    def show_error(self, message: str) -> None:
        self.phase = self.PHASE_ERROR
        self.progress.pack_forget()
        self.status_lbl.configure(text=message, text_color="#ef4444")
        self.btn_skip.configure(state="normal")
        self.btn_later.configure(state="normal", text="關閉", command=self.destroy)
        self.btn_install.configure(
            state="normal", text="開啟下載頁", command=self.fallback_browser
        )

    def fallback_browser(self) -> None:
        open_releases_page()
        self.destroy()

    def on_close(self) -> None:
        if self.phase == self.PHASE_DOWNLOAD and self.download:
            self.download.cancel()
        self.destroy()


def prompt_update(parent, info: UpdateInfo) -> UpdateDialog:
    return UpdateDialog(parent, info)
