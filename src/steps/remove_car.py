"""
從車庫移除車輛

執行流程:
  1. 開跑前: 必須看到 remove_car_target 才會繼續 (沒在「我的車輛」頁就直接中止)。
  2. 每輛車:
       Enter (開選單) -> Down x4 (移到刪除) -> Enter (按下刪除)
       看到 remove_car_confirm 才繼續 (沒看到代表選單結構不對，中止)
       Down (移到「確定」) -> Enter (確認)
  3. 完成數量達標時 DONE。
"""

import time

from loguru import logger

import vision
import window
from runner import StepRunner, StopReason
from steps.constants import START_SCREEN_TIMEOUT_MS, WAIT_AFTER_ENTER_MS

REMOVE_BUTTON_TIMEOUT_MS = 1500
CONFIRM_DIALOG_TIMEOUT_MS = 3000

DOWNS_TO_REMOVE = 4


class RemoveCarRunner(StepRunner):
    name = "remove_car"
    label = "移除車輛"
    quantity_label = "移除數量:"
    progress_label = "已移除"
    template_names = ["remove_car_target", "remove_car_button", "remove_car_confirm"]

    state_labels = {
        "checking_carlist": "檢查車輛清單",
        "opening_menu": "開啟車輛選單",
        "navigating": "移動到刪除",
        "checking_remove": "確認「從車庫移除車輛」",
        "confirming": "確認刪除",
        "settling": "等待清單更新",
        "(none)": "未辨識",
    }

    def loop(self, win, rect, templates, grabber) -> None:
        fg = self.foreground_tick(win)
        if fg == "stopped":
            self.finish_user_stopped()
            return

        self.update(state="checking_carlist")

        if not self.wait_for_template("remove_car_target", START_SCREEN_TIMEOUT_MS):
            self.fail_or_stop(
                StopReason.NO_START_SCREEN,
                "未偵測到車輛清單畫面，請先進入「我的車輛」頁",
            )
            return

        for i in range(self.target):
            if self.stop_evt.is_set():
                self.finish_user_stopped()
                return

            fg = self.foreground_tick(win)
            if fg == "stopped":
                self.finish_user_stopped()
                return
            if fg == "retry":
                continue

            self.update(state="opening_menu")
            self.tap("enter")

            self.update(state="navigating")
            for _ in range(DOWNS_TO_REMOVE):
                self.tap("down")

            self.update(state="checking_remove")
            if not self.wait_for_template(
                "remove_car_button", REMOVE_BUTTON_TIMEOUT_MS
            ):
                self.fail_or_stop(
                    StopReason.STALE,
                    "未停在「從車庫移除車輛」上，流程中止",
                )
                return

            self.sleep(250)

            self.tap("enter")

            if self.sleep_or_stop(WAIT_AFTER_ENTER_MS):
                return

            self.update(state="confirming")

            self.tap("down")

            if not self.wait_for_template(
                "remove_car_confirm", CONFIRM_DIALOG_TIMEOUT_MS
            ):
                self.fail_or_stop(
                    StopReason.STALE,
                    "未偵測到刪除確認對話框，流程中止",
                )
                return

            self.tap("enter")

            self.update(state="settling")

            progress = i + 1
            self.update(progress=progress)
            logger.info("remove_car: progress {}/{}", progress, self.target)

            self.sleep(500)

        self.finish(StopReason.DONE, f"已刪除 {self.target} 輛")

    def fail_or_stop(self, reason: StopReason, msg: str) -> None:
        if self.stop_evt.is_set():
            self.finish_user_stopped()
        else:
            self.finish(reason, msg)

    def wait_for_template(self, name: str, timeout_ms: int) -> bool:
        """等到模板出現(分數 >= 門檻)。逾時或被中止回傳 False。"""
        conf = self.conf
        period = 1.0 / max(1, conf.capture.fps)
        tpl = self.templates[name]
        deadline = time.monotonic() + timeout_ms / 1000.0

        while not self.stop_evt.is_set():
            if time.monotonic() >= deadline:
                return False

            if not window.is_foreground(self.win):
                if self.sleep(250):
                    return False
                continue

            tick_start = time.monotonic()
            frame = self.grabber.grab(self.rect)

            if frame is None:
                if self.sleep(period * 1000):
                    return False
                continue

            frame = vision.to_gray(frame)
            score, _ = vision.match_one(frame, tpl)

            self.update(score=score, match_name=name)

            if score >= conf.match.threshold:
                logger.info("remove_car: matched {} (score={:.3f})", name, score)
                return True

            if self.sleep_remaining(tick_start, period):
                return False

        return False
