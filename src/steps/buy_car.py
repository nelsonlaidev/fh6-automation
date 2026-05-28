"""
大量購買車輛

流程:
  buy_car_detail    -> 按 SPACE，再按 DOWN
  buy_car_confirm   -> 按 ENTER
  buy_car_purchase  -> 按 ENTER，再按 ENTER (順手關掉成功訊息)

中止條件:
  - `stale_timeout_ms` 期間沒有任何模板分數超過門檻 -> 中止。
  - 同一畫面在按下對應按鍵後，經過 `stuck_timeout_ms` 仍未換頁 -> 中止。
  - 達到目標購買數量 -> 正常結束。
"""

import time
from enum import Enum

from loguru import logger

import vision
from runner import StepRunner, StopReason


class Screen(str, Enum):
    BUY_CAR_DETAIL = "buy_car_detail"
    BUY_CAR_CONFIRM = "buy_car_confirm"
    BUY_CAR_PURCHASE = "buy_car_purchase"


KEYS_FOR_SCREEN: dict[Screen, list[str]] = {
    Screen.BUY_CAR_DETAIL: ["space", "down"],
    Screen.BUY_CAR_CONFIRM: ["enter"],
    Screen.BUY_CAR_PURCHASE: ["enter", "enter"],
}


STATE_LABELS: dict[str, str] = {
    Screen.BUY_CAR_DETAIL.value: "車輛詳細頁",
    Screen.BUY_CAR_CONFIRM.value: "確認在汽車展售中心購買",
    Screen.BUY_CAR_PURCHASE.value: "購買確認",
    "(none)": "未辨識",
}


class BuyCarRunner(StepRunner):
    name = "buy_car"
    label = "購買車輛"
    quantity_label = "購買數量:"
    progress_label = "已購買"
    template_names = [s.value for s in Screen]
    state_labels = STATE_LABELS

    def loop(self, win, rect, templates, grabber) -> None:
        conf = self.conf
        period = 1.0 / max(1, conf.capture.fps)

        last_recognized_at = time.monotonic()
        last_pressed_screen: Screen | None = None
        last_pressed_at = 0.0
        last_perf_log = 0.0

        while not self.stop_evt.is_set():
            tick_start = time.monotonic()

            fg = self.foreground_tick(win)
            if fg == "stopped":
                break
            if fg == "retry":
                continue

            t0 = time.monotonic()
            frame = grabber.grab(rect)
            t1 = time.monotonic()
            if frame is None:
                if self.sleep(period * 1000):
                    break
                continue

            frame = vision.scale_frame(frame, conf.match.scale)

            best = vision.best_match(frame, templates)
            t2 = time.monotonic()
            now = t2

            if now - last_perf_log >= 1.0:
                fh, fw = frame.shape[:2]
                logger.info(
                    "perf: grab={:.0f}ms match={:.0f}ms tick={:.0f}ms frame={}x{}",
                    (t1 - t0) * 1000,
                    (t2 - t1) * 1000,
                    (t2 - tick_start) * 1000,
                    fw,
                    fh,
                )
                last_perf_log = now

            if best is None or best.score < conf.match.threshold:
                self.update(
                    state="(none)",
                    score=best.score if best else 0.0,
                    match_name=best.name if best else "",
                )
                stale_for = (now - last_recognized_at) * 1000
                if stale_for >= conf.match.stale_timeout_ms:
                    self.finish(
                        StopReason.STALE, f"{int(stale_for)} ms 內未辨識到任何介面"
                    )
                    return
                self.sleep_remaining(tick_start, period)
                continue

            last_recognized_at = now
            screen = Screen(best.name)
            self.update(state=screen.value, score=best.score, match_name=best.name)

            if last_pressed_screen == screen:
                stuck_for = (now - last_pressed_at) * 1000
                if stuck_for >= conf.match.stuck_timeout_ms:
                    self.finish(
                        StopReason.STUCK,
                        f"畫面 '{screen.value}' 經過 {int(stuck_for)} ms 仍未推進",
                    )
                    return
                self.sleep_remaining(tick_start, period)
                continue

            self.act(screen)
            logger.info("buy_car: matched {} (score={:.3f})", best.name, best.score)
            last_pressed_screen = screen
            last_pressed_at = time.monotonic()

            if screen == Screen.BUY_CAR_PURCHASE:
                progress = self.status.progress + 1
                self.update(progress=progress)
                if progress >= self.target:
                    self.finish(StopReason.DONE, f"已達成 {progress} 次購買")
                    return

            self.sleep_remaining(tick_start, period)

        self.finish_user_stopped()

    def act(self, screen: Screen) -> None:
        for key in KEYS_FOR_SCREEN[screen]:
            logger.info("press {} for {}", key, screen.value)
            self.tap(key)
