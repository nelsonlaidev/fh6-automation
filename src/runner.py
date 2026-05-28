"""StepRunner 共用基底，所有步驟 runner 都繼承這個。

每個步驟在獨立的 thread 裡跑，使用同一套 stop_evt / lock / status 介面，
讓 GUI 可以用一致方式啟停與輪詢狀態。
"""

import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from loguru import logger

import capture
import keys
import vision
import window

USER_STOPPED_MSG = "使用者已停止"


class StopReason(str, Enum):
    USER = "user_stopped"
    DONE = "target_reached"
    STALE = "ui_unrecognized"
    STUCK = "screen_stuck"
    NO_WINDOW = "window_not_found"
    NO_START_SCREEN = "wrong_start_screen"
    USER_DECLINED = "user_declined"
    ERROR = "error"


@dataclass
class Status:
    running: bool = False
    state: str = "-"
    score: float = 0.0
    match_name: str = ""
    progress: int = 0
    target: int = 1
    last_reason: str = ""
    message: str = ""


class StepRunner:
    """所有步驟 runner 的共用基底。

    子類別必須:
      - 宣告 `template_names`(這個步驟需要的模板檔名清單，無副檔名)。
      - 覆寫 `loop(win, rect, templates, grabber)`。

    並可覆寫類別變數:
      - name:            內部 ID (英文，用於 log / 設定檔 section)
      - label:           UI 顯示名稱(中文)
      - quantity_label:  數量輸入框旁的文字
      - progress_label:  進度欄位顯示文字
      - state_labels:    內部狀態 ID -> 中文顯示
    """

    name: str = "step"
    label: str = "步驟"
    quantity_label: str = "數量:"
    progress_label: str = "進度"
    state_labels: dict[str, str] = {}
    template_names: list[str] = []

    def __init__(self, conf) -> None:
        self.conf = conf
        self.stop_evt = threading.Event()
        self.thread: threading.Thread | None = None
        self.status = Status()
        self.lock = threading.Lock()
        self.target = 1

    def start(self, target: int) -> None:
        if self.thread and self.thread.is_alive():
            return

        self.target = max(1, int(target))
        self.stop_evt.clear()

        with self.lock:
            self.status = Status(running=True, target=self.target)

        self.thread = threading.Thread(
            target=self.run_safe, name=f"step-{self.name}", daemon=True
        )

        self.thread.start()

    def stop(self) -> None:
        self.stop_evt.set()

    def mark_declined(self, message: str = "已取消") -> None:
        if self.is_running():
            return
        with self.lock:
            self.status = Status(
                running=False,
                last_reason=StopReason.USER_DECLINED.value,
                message=message,
            )

    def is_running(self) -> bool:
        return bool(self.thread and self.thread.is_alive())

    def get_status(self) -> Status:
        with self.lock:
            return Status(**self.status.__dict__)

    def get_state_label(self, state: str) -> str:
        if not state or state in ("-",):
            return "—"
        return self.state_labels.get(state, state)

    def run(self) -> None:
        if not self.template_names:
            raise NotImplementedError(f"{type(self).__name__} 必須宣告 template_names")

        conf = self.conf
        win = window.find_forza()

        if win is None:
            self.finish(StopReason.NO_WINDOW, "找不到 Forza 視窗")
            return

        rect = window.client_rect(win)
        ratio = rect.height / conf.match.reference_height
        logger.info(
            "Forza found: {}x{} (ratio={:.3f})",
            rect.width,
            rect.height,
            ratio,
        )

        templates = vision.load_templates(self.template_names, ratio=ratio)

        if len(templates) != len(self.template_names):
            missing = set(self.template_names) - set(templates)
            self.finish(StopReason.STALE, f"缺少模板：{', '.join(sorted(missing))}")
            return

        grabber = capture.make_grabber(conf.capture.backend)

        self.win = win
        self.rect = rect
        self.templates = templates
        self.grabber = grabber

        try:
            self.loop(win, rect, templates, grabber)
        finally:
            grabber.close()

    def loop(self, win, rect, templates, grabber) -> None:
        raise NotImplementedError

    def run_safe(self) -> None:
        try:
            self.run()
        except Exception as e:
            logger.exception("{} crashed", self.name)
            self.finish(StopReason.ERROR, f"錯誤:{e}")

    def update(self, **fields) -> None:
        with self.lock:
            for k, v in fields.items():
                setattr(self.status, k, v)

    def finish(self, reason: StopReason, message: str) -> None:
        logger.info("{} finished: {} ({})", self.name, reason.value, message)

        with self.lock:
            self.status.running = False
            self.status.last_reason = reason.value
            self.status.message = message

    def finish_user_stopped(self) -> None:
        self.finish(StopReason.USER, USER_STOPPED_MSG)

    def tap(self, key: str, extra_ms: int = 0) -> None:
        conf = self.conf
        keys.tap(
            key,
            hold_ms=conf.input.press_hold_ms,
            gap_ms=conf.input.between_press_ms + extra_ms,
            jitter_ms=conf.input.jitter_ms,
        )

    def sleep(self, ms: float) -> bool:
        return self.stop_evt.wait(ms / 1000)

    def sleep_or_stop(self, ms: float) -> bool:
        if self.stop_evt.wait(ms / 1000):
            self.finish_user_stopped()
            return True
        return False

    def sleep_remaining(self, tick_start: float, period: float) -> bool:
        elapsed = time.monotonic() - tick_start
        if elapsed < period:
            return self.stop_evt.wait(period - elapsed)
        return False

    def foreground_tick(self, win) -> Literal["ok", "retry", "stopped"]:
        if window.is_foreground(win):
            return "ok"
        if self.sleep(250):
            return "stopped"
        return "retry"
