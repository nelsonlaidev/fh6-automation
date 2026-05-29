"""
升級車輛

執行流程:
  1. 開跑前: 必須看到 upgrade_car_target 才會繼續。
  2. 每輛車:
       Enter (開選單) -> Enter (乘駕車輛)
       看到 upgrade_car_explode (Esc 退出 Forzavista) 或看到 upgrade_car_my_cars
       Down (選升級與調校) -> Enter -> Down x7
       看到 upgrade_car_mastery -> Enter (開熟練度)
       Enter (買第一技能，固定延遲) -> Right -> Up -> Up -> Up -> Left (買超級轉盤)
       看到 upgrade_car_wheelspin_unlocked -> Esc -> Esc -> Up -> Enter
       看到 upgrade_car_sort -> x -> Down x6 -> Enter -> (格子移動邏輯)
       看到 upgrade_car_target -> 下一輛
"""

import time

from loguru import logger

import vision
import window
from runner import StepRunner, StopReason

from steps.constants import (
    DEFAULT_TIMEOUT_MS,
    START_SCREEN_TIMEOUT_MS,
    WAIT_AFTER_ENTER_MS,
)

FORZAVISTA_TIMEOUT_MS = 15000
ANIMATION_TIMEOUT_MS = 8000
WAIT_BETWEEN_DOWNS_MS = 500
WAIT_FIRST_SKILL_MS = 1500
WAIT_AFTER_BUY_MS = 500
WAIT_AFTER_SORT_MS = 1000

DOWNS_TO_MASTERY = 7
DOWNS_TO_SORT = 6
GRID_COLUMNS = 3


STATE_LABELS: dict[str, str] = {
    "checking_carlist": "檢查車輛清單",
    "entering_car": "進入車輛",
    "exit_forzavista": "等待 Forzavista 或選單",
    "goto_mastery": "進入車輛熟練度",
    "buying_skills": "購買技能",
    "spin_animation": "等待超級轉盤",
    "back_to_carlist": "回到車輛清單",
    "resort": "重新排序",
    "next_car": "移到下一輛",
    "(none)": "未辨識",
}


class UpgradeCarRunner(StepRunner):
    name = "upgrade_car"
    label = "升級車輛"
    quantity_label = "升級數量:"
    progress_label = "已升級"
    template_names = [
        "upgrade_car_target",
        "upgrade_car_explode",
        "upgrade_car_my_cars",
        "upgrade_car_mastery",
        "upgrade_car_wheelspin_unlocked",
        "upgrade_car_sort",
    ]
    state_labels = STATE_LABELS

    def loop(self, win, rect, templates, grabber) -> None:
        fg = self.foreground_tick(win)
        if fg == "stopped":
            self.finish_user_stopped()
            return

        self.update(state="checking_carlist")

        if not self.wait_for_template("upgrade_car_target", START_SCREEN_TIMEOUT_MS):
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

            self.update(state="entering_car")

            self.tap("enter")
            self.tap("enter")

            self.update(state="exit_forzavista")

            seen = self.wait_for_any(
                ["upgrade_car_explode", "upgrade_car_my_cars"], FORZAVISTA_TIMEOUT_MS
            )

            if seen is None:
                self.fail_or_stop(StopReason.STALE, "未看到 展開 / 我的車輛")
                return

            if seen == "upgrade_car_explode":
                self.tap("escape")

                if not self.wait_for_template(
                    "upgrade_car_my_cars", DEFAULT_TIMEOUT_MS
                ):
                    self.fail_or_stop(StopReason.STALE, "未看到 我的車輛")
                    return

            self.update(state="goto_mastery")

            if self.sleep_or_stop(WAIT_AFTER_ENTER_MS):
                return

            self.tap("down")
            self.tap("enter")

            if self.sleep_or_stop(WAIT_AFTER_ENTER_MS):
                return

            for _ in range(DOWNS_TO_MASTERY):
                self.tap("down")

            if not self.wait_for_template("upgrade_car_mastery", DEFAULT_TIMEOUT_MS):
                self.fail_or_stop(StopReason.STALE, "未看到 car_mastery")
                return

            self.tap("enter")

            self.update(state="buying_skills")
            if self.sleep_or_stop(WAIT_AFTER_ENTER_MS):
                return

            if not self.conf.general.dry_run:
                self.tap("enter")
            if self.sleep_or_stop(WAIT_FIRST_SKILL_MS):
                return

            for key in ["right", "up", "up", "up", "left"]:
                self.tap(key)
                if not self.conf.general.dry_run:
                    self.tap("enter")

                if self.sleep_or_stop(WAIT_AFTER_BUY_MS):
                    return

            self.update(state="spin_animation")

            if not self.conf.general.dry_run:
                if not self.wait_for_template(
                    "upgrade_car_wheelspin_unlocked", ANIMATION_TIMEOUT_MS
                ):
                    self.fail_or_stop(StopReason.STALE, "未看到 wheelspin_unlocked")
                    return

            self.update(state="back_to_carlist")

            self.tap("escape")
            if self.sleep_or_stop(WAIT_AFTER_ENTER_MS):
                return

            self.tap("escape")
            if self.sleep_or_stop(WAIT_AFTER_ENTER_MS):
                return

            self.tap("up")
            if self.sleep_or_stop(WAIT_BETWEEN_DOWNS_MS):
                return

            self.tap("enter")

            self.update(state="resort")
            if not self.wait_for_template("upgrade_car_sort", DEFAULT_TIMEOUT_MS):
                self.fail_or_stop(StopReason.STALE, "未看到 sort")
                return

            self.tap("x")
            if self.sleep_or_stop(WAIT_AFTER_ENTER_MS):
                return

            for _ in range(DOWNS_TO_SORT):
                self.tap("down")

            self.tap("enter")
            if self.sleep_or_stop(WAIT_AFTER_SORT_MS):
                return

            progress = i + 1
            self.update(progress=progress)
            logger.info("upgrade_car: 進度 {}/{}", progress, self.target)

            if progress < self.target:
                self.update(state="next_car")

                if progress % GRID_COLUMNS == 0:
                    self.tap("right")

                    if self.sleep_or_stop(WAIT_BETWEEN_DOWNS_MS):
                        return

                    self.tap("up")

                    if self.sleep_or_stop(WAIT_BETWEEN_DOWNS_MS):
                        return

                    self.tap("up")
                else:
                    self.tap("down")

                if not self.wait_for_template("upgrade_car_target", DEFAULT_TIMEOUT_MS):
                    self.fail_or_stop(StopReason.STALE, "移動後未看到 carlist")
                    return

        self.finish(StopReason.DONE, f"已升級 {self.target} 輛")

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
                logger.debug("upgrade_car: 比對到 {} (分數={:.3f})", name, score)
                return True

            if self.sleep_remaining(tick_start, period):
                return False

        return False

    def wait_for_any(self, names: list[str], timeout_ms: int) -> str | None:
        """等到任一模板出現，回傳名稱。逾時/中止回 None。"""
        conf = self.conf
        period = 1.0 / max(1, conf.capture.fps)
        tpls = [(n, self.templates[n]) for n in names]
        deadline = time.monotonic() + timeout_ms / 1000.0

        while not self.stop_evt.is_set():
            if time.monotonic() >= deadline:
                return None

            if not window.is_foreground(self.win):
                if self.sleep(250):
                    return None
                continue

            tick_start = time.monotonic()
            frame = self.grabber.grab(self.rect)

            if frame is None:
                if self.sleep(period * 1000):
                    return None
                continue

            frame = vision.to_gray(frame)

            best_name, best_score = names[0], -1.0
            for n, tpl in tpls:
                score, _ = vision.match_one(frame, tpl)
                if score > best_score:
                    best_score = score
                    best_name = n

            self.update(score=best_score, match_name=best_name)

            if best_score >= conf.match.threshold:
                logger.debug(
                    "upgrade_car: 比對到 {} (分數={:.2f})", best_name, best_score
                )
                return best_name

            if self.sleep_remaining(tick_start, period):
                return None

        return None
