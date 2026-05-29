"""更新檢查與下載。

公開介面：
- check_async(parent, callback)：背景檢查 GitHub Release，結果丟回主執行緒。
- Download：背景下載 installer，可中途取消。
- UpdateDialog：顯示新版資訊 + release notes + 一鍵下載安裝。
- prompt_update(parent, info)：開啟 UpdateDialog。
"""

import json
import os
import re
import subprocess
import tempfile
import threading
import webbrowser
from dataclasses import dataclass
from typing import Callable, Literal
from urllib.error import URLError
from urllib.request import Request, urlopen

from loguru import logger
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

import config as cfg
from version import __version__

REPO = "nelsonlaidev/fh6-automation"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
API_URL_ALL = f"https://api.github.com/repos/{REPO}/releases?per_page=1"
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

    後綴（'-rc1'、'+build' 等）會被忽略。
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
        logger.warning("updater: 無法解析目前版本：{}", __version__)
        return CheckResult(status="error", error=f"無法解析目前版本：{__version__}")

    conf = cfg.load()
    url = API_URL_ALL if conf.general.update_channel == "beta" else API_URL

    try:
        req = Request(url, headers={"Accept": "application/vnd.github.v3+json"})
        with urlopen(req, timeout=CHECK_TIMEOUT_S) as resp:
            raw = json.loads(resp.read())
            data = raw[0] if isinstance(raw, list) else raw
    except (URLError, OSError) as e:
        logger.warning("updater: 檢查更新連線失敗：{}", e)
        return CheckResult(status="error", error=f"連線失敗：{e}")
    except (ValueError, KeyError) as e:
        logger.warning("updater: 檢查更新回應格式錯誤：{}", e)
        return CheckResult(status="error", error=f"回應格式錯誤：{e}")

    latest_tag = data.get("tag_name", "")
    latest = parse_version(latest_tag)
    if latest is None:
        logger.warning("updater: 無法解析最新版本號：{!r}", latest_tag)
        return CheckResult(status="error", error=f"無法解析版本號：{latest_tag!r}")

    if latest <= current:
        return CheckResult(status="up_to_date")

    info = UpdateInfo(
        tag=latest_tag,
        version=latest,
        body=data.get("body", "") or "",
        installer_url=find_installer_url(data.get("assets", [])),
    )
    logger.info("updater: 發現新版本 {} (目前 {})", latest_tag, __version__)
    return CheckResult(status="available", info=info)


def check_async(parent, callback: Callable[[CheckResult], None]) -> None:
    """背景檢查，結果在主執行緒回呼。"""

    def worker() -> None:
        result = check()
        try:
            QTimer.singleShot(0, parent, lambda: callback(result))
        except Exception:
            # parent 可能已被銷毀；忽略
            logger.debug("updater: 回呼略過（parent 已銷毀）")

    threading.Thread(target=worker, name="updater-check", daemon=True).start()


class _Poster(QObject):
    """跨執行緒回呼用的訊號載體。"""

    posted = Signal(object)


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
        # 用 QObject + Signal 把 worker thread 的回呼安全地丟回主執行緒。
        # _Poster 在主執行緒建立，posted 訊號預設用 AutoConnection，
        # 跨執行緒 emit 會自動轉成 QueuedConnection。
        self.poster = _Poster()
        self.poster.posted.connect(lambda fn: fn())

    def start(self) -> None:
        self.thread = threading.Thread(target=self.run, name="updater-download", daemon=True)
        self.thread.start()

    def cancel(self) -> None:
        self.cancel_evt.set()

    def post(self, fn: Callable[[], None]) -> None:
        try:
            self.poster.posted.emit(fn)
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
                logger.info("updater: 使用者取消下載")
                return
            logger.warning("updater: 下載失敗：{}", e)
            self.post(lambda err=str(e): self.on_error(err))


def installer_temp_path(tag: str) -> str:
    safe_tag = re.sub(r"[^A-Za-z0-9._-]", "_", tag) or "latest"
    return os.path.join(tempfile.gettempdir(), f"FH6Automation_Setup_{safe_tag}.exe")


def launch_installer_and_quit(parent, installer_path: str) -> None:
    """啟動 silent installer 然後關閉 app，installer 會自動重啟新版本。"""
    try:
        # 用 detached process 確保 app 退出後 installer 仍能跑
        subprocess.Popen(
            [installer_path, "/VERYSILENT", "/SUPPRESSMSGBOXES"],
            close_fds=True,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        logger.info("updater: 已啟動靜默安裝程式：{}", installer_path)
    except OSError as e:
        logger.error("updater: 無法啟動安裝程式：{}", e)
        raise
    QTimer.singleShot(200, QApplication.quit)


def remember_skip(tag: str) -> None:
    """把 tag 寫入 config.ini 的 skipped_version。"""
    conf = cfg.load()
    conf.general.skipped_version = tag
    cfg.save(conf)
    logger.info("updater: 已記錄跳過版本：{}", tag)


def clear_skip() -> None:
    conf = cfg.load()
    conf.general.skipped_version = ""
    cfg.save(conf)
    logger.info("updater: 已清除跳過版本紀錄")


def open_releases_page() -> None:
    webbrowser.open(RELEASES_URL)


class UpdateDialog(QDialog):
    """新版本提示對話框：顯示 release notes，提供下載安裝 / 跳過 / 稍後。"""

    PHASE_PROMPT = "prompt"
    PHASE_DOWNLOAD = "download"
    PHASE_ERROR = "error"

    def __init__(self, parent, info: UpdateInfo) -> None:
        super().__init__(parent)
        self.setWindowTitle("有新版本")
        self.setFixedSize(520, 460)
        # always-on-top
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        self.parent_app = parent
        self.info = info
        self.download: Download | None = None
        self.phase = self.PHASE_PROMPT

        self.build_ui()

    def build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(0)

        title_lbl = QLabel(f"發現新版本 {self.info.tag}")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_lbl.setFont(title_font)
        outer.addWidget(title_lbl)

        subtitle_lbl = QLabel(f"目前版本 v{__version__}")
        subtitle_lbl.setStyleSheet("color: gray;")
        outer.addWidget(subtitle_lbl)

        outer.addSpacing(12)

        notes_title = QLabel("更新內容")
        notes_title_font = QFont()
        notes_title_font.setPointSize(10)
        notes_title_font.setBold(True)
        notes_title.setFont(notes_title_font)
        outer.addWidget(notes_title)

        outer.addSpacing(4)

        self.notes_box = QTextBrowser()
        self.notes_box.setOpenExternalLinks(True)
        self.notes_box.setMarkdown(self.info.body or "（這個版本沒有提供更新說明）")
        outer.addWidget(self.notes_box, stretch=1)

        outer.addSpacing(8)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: gray;")
        outer.addWidget(self.status_lbl)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()  # 進入下載階段才顯示
        outer.addWidget(self.progress)

        outer.addSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_skip = QPushButton("跳過此版本")
        self.btn_skip.setFixedWidth(110)
        self.btn_skip.clicked.connect(self.on_skip)
        btn_row.addWidget(self.btn_skip)

        btn_row.addStretch(1)

        self.btn_later = QPushButton("稍後再說")
        self.btn_later.setFixedWidth(110)
        self.btn_later.clicked.connect(self.on_later)
        btn_row.addWidget(self.btn_later)

        self.btn_install = QPushButton("立即更新")
        self.btn_install.setFixedWidth(110)
        self.btn_install.setDefault(True)
        self.btn_install.clicked.connect(self.on_install)
        btn_row.addWidget(self.btn_install)

        outer.addLayout(btn_row)

    def on_skip(self) -> None:
        try:
            remember_skip(self.info.tag)
        except OSError as e:
            logger.warning("updater: 無法儲存跳過版本：{}", e)
        self.close()

    def on_later(self) -> None:
        self.close()

    def on_install(self) -> None:
        if not self.info.installer_url:
            # 沒有 installer asset：fallback 開瀏覽器
            open_releases_page()
            self.close()
            return
        self.enter_download_phase()

    def enter_download_phase(self) -> None:
        self.phase = self.PHASE_DOWNLOAD
        self.btn_skip.setEnabled(False)
        self.btn_later.setEnabled(False)
        self.btn_install.setText("取消")
        try:
            self.btn_install.clicked.disconnect()
        except RuntimeError:
            pass
        self.btn_install.clicked.connect(self.on_cancel_download)

        self.progress.show()
        self.progress.setValue(0)
        self.status_lbl.setText("準備下載…")
        self.status_lbl.setStyleSheet("color: gray;")

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
            self.progress.setValue(int(downloaded * 100 / total))
            mb_d = downloaded / (1024 * 1024)
            mb_t = total / (1024 * 1024)
            self.status_lbl.setText(f"下載中… {mb_d:.1f} / {mb_t:.1f} MB")
        else:
            mb_d = downloaded / (1024 * 1024)
            self.status_lbl.setText(f"下載中… {mb_d:.1f} MB")

    def on_cancel_download(self) -> None:
        if self.download:
            self.download.cancel()
        self.close()

    def on_download_done(self, installer_path: str) -> None:
        self.status_lbl.setText("準備安裝…")
        self.status_lbl.setStyleSheet("color: gray;")
        self.progress.setValue(100)
        # 短暫延遲讓使用者看到完成狀態
        QTimer.singleShot(300, lambda: self.start_install(installer_path))

    def start_install(self, installer_path: str) -> None:
        try:
            launch_installer_and_quit(self.parent_app, installer_path)
        except OSError as e:
            self.show_error(f"無法啟動安裝程式：{e}")

    def on_download_error(self, error: str) -> None:
        self.show_error(f"下載失敗：{error}")

    def show_error(self, message: str) -> None:
        self.phase = self.PHASE_ERROR
        self.progress.hide()
        self.status_lbl.setText(message)
        self.status_lbl.setStyleSheet("color: #ef4444;")

        self.btn_skip.setEnabled(True)

        self.btn_later.setEnabled(True)
        self.btn_later.setText("關閉")
        try:
            self.btn_later.clicked.disconnect()
        except RuntimeError:
            pass
        self.btn_later.clicked.connect(self.close)

        self.btn_install.setEnabled(True)
        self.btn_install.setText("開啟下載頁")
        try:
            self.btn_install.clicked.disconnect()
        except RuntimeError:
            pass
        self.btn_install.clicked.connect(self.fallback_browser)

    def fallback_browser(self) -> None:
        open_releases_page()
        self.close()

    def closeEvent(self, event) -> None:
        if self.phase == self.PHASE_DOWNLOAD and self.download:
            self.download.cancel()
        super().closeEvent(event)


def prompt_update(parent, info: UpdateInfo) -> UpdateDialog:
    dlg = UpdateDialog(parent, info)
    dlg.show()
    return dlg
