"""
刷技能點

狀態機:
  WAITING_START   見 farm_sp_start    -> 按 Enter -> 進 DRIVING
  DRIVING         按住 W，持續比對 farm_sp_anna；當 Anna 從畫面上消失代表本輪結束
                  -> 放開 W -> 進 WAITING_RESTART
  WAITING_RESTART 見 farm_sp_restart  -> 按 X -> 進 WAITING_CONFIRM
  WAITING_CONFIRM 見 farm_sp_confirm  -> 按 Enter -> 進度 +1 -> 回 WAITING_START

每個非駕駛狀態各自有一個 STATE_TIMEOUT_MS 等待上限，超過代表畫面對不上預期，
中止整個流程。
DRIVING 另有 DRIVE_HARD_TIMEOUT_MS 作為保險。
"""

import time
from enum import Enum

from loguru import logger

import keys
import vision
import window
from runner import StepRunner, StopReason


class FarmState(str, Enum):
    WAITING_START = "waiting_start"
    DRIVING = "driving"
    WAITING_RESTART = "waiting_restart"
    WAITING_CONFIRM = "waiting_confirm"


KEYS_FOR_STATE: dict[str, list[str]] = {
    FarmState.WAITING_START: ["enter"],
    FarmState.WAITING_RESTART: ["x"],
    FarmState.WAITING_CONFIRM: ["enter"],
}

EXPECTED_TPL: dict[str, str] = {
    FarmState.WAITING_START: "farm_sp_start",
    FarmState.WAITING_RESTART: "farm_sp_restart",
    FarmState.WAITING_CONFIRM: "farm_sp_confirm",
}

ANNA_LABEL = "Anna"

STATE_TIMEOUT_MS = 20000
DRIVE_LOAD_BUFFER_MS = 2000  # 進入駕駛畫面後等這麼久才開始辨識 Anna
ANNA_FIND_TIMEOUT_MS = 15000  # 進入駕駛後最多等這麼久仍未看到 Anna -> 提早放棄
ANNA_GONE_GRACE_MS = 1500  # Anna 連續這麼久沒比對到 -> 視為消失，放開 W
DRIVE_HARD_TIMEOUT_MS = 180000  # 駕駛狀態硬性上限，作為保險


STATE_LABELS: dict[str, str] = {
    FarmState.WAITING_START.value: "等待開始畫面",
    FarmState.DRIVING.value: "駕駛中",
    FarmState.WAITING_RESTART.value: "等待重新開始畫面",
    FarmState.WAITING_CONFIRM.value: "等待確認畫面",
    "(none)": "未辨識",
}


class FarmSPRunner(StepRunner):
    name = "farm_sp"
    label = "刷技能點"
    quantity_label = "目標次數:"
    progress_label = "已完成"
    template_names = [
        "farm_sp_start",
        "farm_sp_anna",
        "farm_sp_restart",
        "farm_sp_confirm",
    ]
    state_labels = STATE_LABELS

    def loop(self, win, rect, templates, grabber) -> None:
        conf = self.conf
        period = 1.0 / max(1, conf.capture.fps)

        state = FarmState.WAITING_START
        state_entered_at = time.monotonic()

        self.update(state=state.value)

        while not self.stop_evt.is_set():
            tick_start = time.monotonic()

            fg = self.foreground_tick(win)
            if fg == "stopped":
                break
            if fg == "retry":
                continue

            if state == FarmState.DRIVING:
                self.drive(win)

                if self.stop_evt.is_set():
                    break

                state = FarmState.WAITING_RESTART
                state_entered_at = time.monotonic()

                self.update(state=state.value)

                continue

            tpl_name = EXPECTED_TPL[state]
            tpl = templates[tpl_name]

            frame = grabber.grab(rect)

            if frame is None:
                if self.sleep(period * 1000):
                    break
                continue

            frame = vision.scale_frame(frame, conf.match.scale)
            score, _ = vision.match_one(frame, tpl)

            self.update(score=score, match_name=tpl_name)

            if score >= conf.match.threshold:
                keys_to_press = KEYS_FOR_STATE[state]

                logger.info(
                    "farm_sp: state={} sees {} (score={:.2f}), press {}",
                    state.value,
                    tpl_name,
                    score,
                    "+".join(keys_to_press),
                )

                for key in keys_to_press:
                    self.tap(key)

                if state == FarmState.WAITING_START:
                    state = FarmState.DRIVING
                    state_entered_at = time.monotonic()
                    self.update(state=state.value)

                elif state == FarmState.WAITING_RESTART:
                    state = FarmState.WAITING_CONFIRM
                    state_entered_at = time.monotonic()
                    self.update(state=state.value)

                elif state == FarmState.WAITING_CONFIRM:
                    progress = self.status.progress + 1
                    self.update(progress=progress)

                    if progress >= self.target:
                        self.finish(StopReason.DONE, f"已完成 {progress} 次")
                        return

                    state = FarmState.WAITING_START
                    state_entered_at = time.monotonic()
                    self.update(state=state.value)

                continue

            elapsed_ms = (time.monotonic() - state_entered_at) * 1000

            if elapsed_ms >= STATE_TIMEOUT_MS:
                self.finish(
                    StopReason.STALE,
                    f"狀態「{STATE_LABELS[state.value]}」經過 {int(elapsed_ms)} ms 仍未見預期畫面",
                )
                return

            if self.sleep_remaining(tick_start, period):
                break

        self.finish_user_stopped()

    def drive(self, win) -> None:
        """
        按住 W 直到 Anna 從畫面上消失。

        進入後先 sleep DRIVE_LOAD_BUFFER_MS 讓駕駛畫面載入，再開始辨識 farm_sp_anna：

        - 若一直沒看到 Anna，在 ANNA_FIND_TIMEOUT_MS 後直接放開 W。
        - 看到 Anna 後若連續 ANNA_GONE_GRACE_MS 沒比對到，視為消失，放開 W。
        - 任何狀況下到 DRIVE_HARD_TIMEOUT_MS 都強制放開 W。
        """
        conf = self.conf
        period = 1.0 / max(1, conf.capture.fps)
        tpl = self.templates["farm_sp_anna"]
        threshold = conf.match.threshold

        if self.sleep(DRIVE_LOAD_BUFFER_MS):
            return

        drive_start = time.monotonic()
        last_anna_seen_at: float | None = None

        logger.info("farm_sp: holding W, waiting for {} to disappear", ANNA_LABEL)

        with keys.held("w"):
            while not self.stop_evt.is_set():
                tick_start = time.monotonic()

                if not window.is_foreground(win):
                    logger.info(
                        "farm_sp: Forza lost foreground while driving, releasing W"
                    )
                    return

                frame = self.grabber.grab(self.rect)

                if frame is None:
                    if self.sleep(period * 1000):
                        return
                    continue

                frame = vision.scale_frame(frame, conf.match.scale)
                score, _ = vision.match_one(frame, tpl)

                self.update(score=score, match_name="farm_sp_anna")

                now = time.monotonic()
                drive_elapsed_ms = (now - drive_start) * 1000

                if score >= threshold:
                    last_anna_seen_at = now
                else:
                    if last_anna_seen_at is None:
                        if drive_elapsed_ms >= ANNA_FIND_TIMEOUT_MS:
                            logger.warning(
                                "farm_sp: 等了 {} ms 仍未看到 {}，放開 W",
                                int(drive_elapsed_ms),
                                ANNA_LABEL,
                            )
                            return
                    else:
                        gone_ms = (now - last_anna_seen_at) * 1000
                        if gone_ms >= ANNA_GONE_GRACE_MS:
                            logger.info(
                                "farm_sp: {} 已消失 {} ms，放開 W",
                                ANNA_LABEL,
                                int(gone_ms),
                            )
                            return

                if drive_elapsed_ms >= DRIVE_HARD_TIMEOUT_MS:
                    logger.warning(
                        "farm_sp: 駕駛超過硬性超時 {} ms，放開 W",
                        int(drive_elapsed_ms),
                    )
                    return

                if self.sleep_remaining(tick_start, period):
                    return
