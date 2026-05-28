import os
import subprocess
import sys
import time
from tkinter import messagebox

import customtkinter as ctk
from loguru import logger

import config as cfg
from runner import StepRunner
from settings import SettingsWindow
from steps.buy_car import BuyCarRunner
from steps.remove_car import RemoveCarRunner
from steps.farm_sp import FarmSPRunner
from steps.upgrade_car import UpgradeCarRunner
import updater

REFRESH_MS = 200

FONT_SIZE_TITLE = 20
FONT_SIZE_HEADING = 16
FONT_SIZE_BODY = 14


COLOR_RUNNING = "#22c55e"
COLOR_IDLE = "#6b7280"
COLOR_ERROR = "#ef4444"
COLOR_WARNING = "#f59e0b"
COLOR_DONE = "#22c55e"
COLOR_MUTED = "gray60"
COLOR_ACCENT = "#3b82f6"

ERROR_REASONS = {
    "ui_unrecognized",
    "screen_stuck",
    "window_not_found",
    "wrong_start_screen",
    "error",
}

REASON_LABEL = {
    "user_stopped": "已停止",
    "target_reached": "完成",
    "ui_unrecognized": "介面未辨識",
    "screen_stuck": "畫面卡住",
    "window_not_found": "找不到 Forza 視窗",
    "wrong_start_screen": "起始畫面不正確",
    "user_declined": "已取消",
    "error": "發生錯誤",
}


def score_color(score: float, threshold: float) -> str:
    if score >= threshold:
        return COLOR_RUNNING
    if score >= threshold * 0.7:
        return COLOR_WARNING
    return COLOR_MUTED


def open_in_explorer(path) -> None:
    try:
        if os.path.isdir(path):
            os.startfile(str(path))
        else:
            subprocess.Popen(["explorer", "/select,", str(path)])
    except Exception as e:
        logger.warning("Failed to open {}: {}", path, e)


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("FH6 自動化")
        self.geometry("680x520")
        self.resizable(False, False)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.conf = cfg.load()
        self.attributes("-topmost", self.conf.general.always_on_top)

        self.runners: dict[str, StepRunner] = {
            "farm_sp": FarmSPRunner(self.conf),
            "buy_car": BuyCarRunner(self.conf),
            "upgrade_car": UpgradeCarRunner(self.conf),
            "delete": RemoveCarRunner(self.conf),
        }
        self.step_order = list(self.runners.keys())
        self.current = self.step_order[0]

        self.build_ui()
        self.show_step(self.current)
        self.after(REFRESH_MS, self.refresh)

        if self.conf.general.auto_update:
            updater.check_update_async(self)

    def runner(self, step_id: str) -> StepRunner:
        return self.runners[step_id]

    def any_running(self) -> str | None:
        for sid, r in self.runners.items():
            if r.is_running():
                return sid
        return None

    def build_ui(self) -> None:
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=16, pady=16)

        header = ctk.CTkFrame(outer, fg_color="transparent")
        header.pack(fill="x")

        ctk.CTkLabel(
            header,
            text="超級轉盤刷取",
            font=ctk.CTkFont(size=FONT_SIZE_TITLE, weight="bold"),
        ).pack(side="left")

        self.pill_text = ctk.CTkLabel(
            header,
            text="閒置",
            text_color=COLOR_MUTED,
            font=ctk.CTkFont(size=FONT_SIZE_BODY),
        )
        self.pill_text.pack(side="right")

        self.pill_dot = ctk.CTkLabel(
            header,
            text="●",
            text_color=COLOR_IDLE,
            font=ctk.CTkFont(size=FONT_SIZE_TITLE),
        )
        self.pill_dot.pack(side="right", padx=(0, 4))

        body = ctk.CTkFrame(outer, fg_color="transparent")
        body.pack(fill="both", expand=True, pady=(12, 0))
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        tabs = ctk.CTkFrame(body)
        tabs.grid(row=0, column=0, sticky="n", padx=(0, 12))

        self.step_btns: dict[str, ctk.CTkButton] = {}
        self.step_btn_selected: dict[str, bool | None] = {}

        for row, sid in enumerate(self.step_order):
            r = self.runner(sid)
            btn = ctk.CTkButton(
                tabs,
                text=r.label,
                width=120,
                height=36,
                anchor="w",
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray80", "gray25"),
                command=lambda s=sid: self.show_step(s),
            )
            btn.grid(
                row=row,
                column=0,
                sticky="ew",
                padx=6,
                pady=(
                    6 if row == 0 else 3,
                    6 if row == len(self.step_order) - 1 else 0,
                ),
            )
            self.step_btns[sid] = btn
            self.step_btn_selected[sid] = None

        self.content_holder = ctk.CTkFrame(body, fg_color="transparent")
        self.content_holder.grid(row=0, column=1, sticky="nsew")

        self.step_frames: dict[str, StepFrame] = {}
        for sid in self.step_order:
            r = self.runner(sid)
            initial_quantity = self.initial_quantity_for(sid)
            frame = StepFrame(
                self.content_holder,
                runner=r,
                initial_quantity=initial_quantity,
                on_start=lambda s=sid: self.on_start(s),
                on_stop=lambda s=sid: self.on_stop(s),
                on_save=lambda s=sid: self.on_save(s),
            )
            self.step_frames[sid] = frame

        footer = ctk.CTkFrame(outer, fg_color="transparent")
        footer.pack(fill="x", side="bottom", pady=(12, 0))

        for text, cmd in (
            ("模板", self.open_templates),
            ("設定", self.open_config),
            ("紀錄", self.open_logs),
        ):
            ctk.CTkButton(
                footer,
                text=text,
                width=100,
                height=30,
                fg_color="transparent",
                border_width=1,
                command=cmd,
            ).pack(side="left", padx=(0, 8))

    def initial_quantity_for(self, step_id: str) -> int:
        conf = self.conf

        return {
            "farm_sp": conf.farm_sp.target_runs,
            "buy_car": conf.buy_car.quantity,
            "upgrade_car": conf.upgrade_car.quantity,
            "delete": conf.delete.quantity,
        }[step_id]

    def show_step(self, step_id: str) -> None:
        self.current = step_id
        for sid, frame in self.step_frames.items():
            if sid == step_id:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

    def on_start(self, step_id: str) -> None:
        running = self.any_running()
        if running is not None:
            return

        frame = self.step_frames[step_id]
        target = frame.read_quantity()
        if target is None:
            return

        if step_id == "delete" and not self.confirm_delete(target):
            self.runner(step_id).mark_declined()
            return

        self.conf = cfg.load()
        self.save_step_settings(step_id, target)

        runner = self.runner(step_id)
        runner.conf = self.conf
        runner.start(target=target)

    def confirm_delete(self, target: int) -> bool:
        return messagebox.askyesno(
            title="確認刪除",
            message=(
                f"即將從車庫刪除 {target} 輛車。\n"
                "此操作無法復原。\n\n"
                "請確認車輛清單頂端是要刪除的目標，確定要繼續嗎?"
            ),
            parent=self,
        )

    def on_stop(self, step_id: str) -> None:
        self.runner(step_id).stop()

    def on_save(self, step_id: str) -> None:
        if self.any_running() is not None:
            return

        frame = self.step_frames[step_id]
        target = frame.read_quantity()
        if target is None:
            return

        self.conf = cfg.load()
        self.save_step_settings(step_id, target)
        frame.show_saved()

    def save_step_settings(self, step_id: str, target: int) -> None:
        c = self.conf
        if step_id == "farm_sp":
            c.farm_sp.target_runs = target
        elif step_id == "buy_car":
            c.buy_car.quantity = target
        elif step_id == "upgrade_car":
            c.upgrade_car.quantity = target
        elif step_id == "delete":
            c.delete.quantity = target
        try:
            cfg.save(c)
        except OSError as e:
            logger.warning("Failed to persist config: {}", e)

    def open_templates(self) -> None:
        open_in_explorer(cfg.user_templates_dir())

    def open_config(self) -> None:
        SettingsWindow(self, self.conf, on_save=self.apply_settings)

    def apply_settings(self, new_conf: cfg.Config) -> None:
        self.conf = new_conf
        self.attributes("-topmost", new_conf.general.always_on_top)
        for r in self.runners.values():
            r.conf = new_conf

    def open_logs(self) -> None:
        open_in_explorer(cfg.logs_dir())

    def refresh(self) -> None:
        running_id = self.any_running()
        any_running = running_id is not None

        if any_running:
            label = self.runners[running_id].label
            self.pill_dot.configure(text_color=COLOR_RUNNING)
            self.pill_text.configure(text=f"執行中 ({label})", text_color=COLOR_RUNNING)
        else:
            self.pill_dot.configure(text_color=COLOR_IDLE)
            self.pill_text.configure(text="閒置", text_color=COLOR_MUTED)

        for sid, btn in self.step_btns.items():
            selected = sid == self.current
            if self.step_btn_selected[sid] != selected:
                if selected:
                    btn.configure(fg_color=COLOR_ACCENT, text_color="white")
                else:
                    btn.configure(
                        fg_color="transparent", text_color=("gray10", "gray90")
                    )
                self.step_btn_selected[sid] = selected

        for sid, frame in self.step_frames.items():
            other_running = any_running and running_id != sid
            frame.refresh(disabled_due_to_other=other_running)

        self.after(REFRESH_MS, self.refresh)


class StepFrame(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        runner: StepRunner,
        initial_quantity: int,
        on_start,
        on_stop,
        on_save,
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self.runner = runner
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_save = on_save
        self.last_btn_state: tuple[bool, bool] | None = None
        self.message_until: float = 0

        self.build_ui()
        self.qty_var.set(str(initial_quantity))

    def build_ui(self) -> None:
        runner = self.runner

        ctk.CTkLabel(
            self,
            text=runner.label,
            font=ctk.CTkFont(size=FONT_SIZE_HEADING, weight="bold"),
            anchor="w",
        ).pack(fill="x")

        qty_row = ctk.CTkFrame(self, fg_color="transparent")
        qty_row.pack(fill="x", pady=(8, 8))
        ctk.CTkLabel(
            qty_row,
            text=runner.quantity_label,
            font=ctk.CTkFont(size=FONT_SIZE_BODY),
        ).pack(side="left")

        self.qty_var = ctk.StringVar(value="1")
        self.qty_entry = ctk.CTkEntry(
            qty_row,
            textvariable=self.qty_var,
            width=80,
            justify="right",
        )
        self.qty_entry.pack(side="left", padx=(8, 8))

        self.toggle_btn = ctk.CTkButton(
            self,
            text="開始",
            height=38,
            font=ctk.CTkFont(size=FONT_SIZE_BODY, weight="bold"),
            command=self.handle_toggle,
        )
        self.toggle_btn.pack(fill="x", pady=(0, 6))
        self.toggle_default_fg = self.toggle_btn.cget("fg_color")
        self.toggle_default_hover = self.toggle_btn.cget("hover_color")

        save_row = ctk.CTkFrame(self, fg_color="transparent")
        save_row.pack(fill="x", pady=(0, 10))
        self.save_btn = ctk.CTkButton(
            save_row,
            text="儲存設定",
            width=100,
            height=28,
            fg_color="transparent",
            border_width=1,
            command=self.handle_save,
        )
        self.save_btn.pack(side="right")

        stats = ctk.CTkFrame(self)
        stats.pack(fill="x", pady=(0, 8))
        stats.grid_columnconfigure(0, weight=0)
        stats.grid_columnconfigure(1, weight=1)

        self.lbl_progress = self.stat(stats, 0, 0, runner.progress_label, "0 / 0")
        self.lbl_state = self.stat(stats, 1, 0, "狀態", "—")
        self.lbl_score = self.stat(stats, 2, 0, "分數", "0.000")
        self.lbl_threshold = self.stat(stats, 3, 0, "門檻", "0.85")

        self.lbl_state_default_color = self.lbl_state.cget("text_color")

        self.lbl_message = ctk.CTkLabel(
            self,
            text="",
            text_color=COLOR_MUTED,
            anchor="w",
        )
        self.lbl_message.pack(fill="x", pady=(8, 0))

    def stat(self, parent, row: int, col: int, label: str, value: str) -> ctk.CTkLabel:
        ctk.CTkLabel(
            parent,
            text=label,
            text_color=COLOR_MUTED,
            font=ctk.CTkFont(size=FONT_SIZE_BODY),
        ).grid(
            row=row,
            column=col,
            sticky="w",
            padx=(12, 8),
            pady=4,
        )
        v = ctk.CTkLabel(
            parent,
            text=value,
            font=ctk.CTkFont(size=FONT_SIZE_BODY, weight="bold"),
            anchor="w",
        )
        v.grid(
            row=row,
            column=col + 1,
            sticky="ew",
            padx=(0, 12),
            pady=4,
        )
        return v

    def read_quantity(self) -> int | None:
        raw = self.qty_var.get().strip()

        try:
            target = int(raw)
        except ValueError:
            self.lbl_message.configure(
                text="數量無效 (請輸入正整數)。",
                text_color=COLOR_ERROR,
            )
            return None

        if target < 1:
            self.lbl_message.configure(
                text="數量至少要 1。",
                text_color=COLOR_ERROR,
            )
            return None

        self.lbl_message.configure(text_color=COLOR_MUTED)
        return target

    def refresh(self, disabled_due_to_other: bool) -> None:
        runner = self.runner
        status = runner.get_status()
        running = status.running

        btn_state = (running, disabled_due_to_other)

        if btn_state != self.last_btn_state:
            if running:
                self.toggle_btn.configure(
                    text="停止",
                    fg_color=COLOR_ERROR,
                    hover_color="#b91c1c",
                    state="normal",
                )
            else:
                self.toggle_btn.configure(
                    text="開始",
                    fg_color=self.toggle_default_fg,
                    hover_color=self.toggle_default_hover,
                    state="disabled" if disabled_due_to_other else "normal",
                )

            locked = "disabled" if (running or disabled_due_to_other) else "normal"

            self.qty_entry.configure(state=locked)

            self.save_btn.configure(state=locked)

            self.last_btn_state = btn_state

        self.lbl_state.configure(**self.compute_state_display(status))

        from_conf_threshold = runner.conf.match.threshold

        self.lbl_score.configure(
            text=(
                f"{status.score:.3f}  ({status.match_name})"
                if status.match_name
                else f"{status.score:.3f}"
            ),
            text_color=score_color(status.score, from_conf_threshold),
        )

        target_str = str(status.target) if status.target >= 1 else "—"

        self.lbl_progress.configure(text=f"{status.progress} / {target_str}")
        self.lbl_threshold.configure(text=f"{from_conf_threshold:.2f}")

        if status.last_reason in ERROR_REASONS:
            self.lbl_message.configure(
                text=status.message or "",
                text_color=COLOR_ERROR,
            )
        else:
            if time.monotonic() >= self.message_until:
                self.lbl_message.configure(text="", text_color=COLOR_MUTED)

    def compute_state_display(self, status) -> dict:
        """根據 runner 狀態決定 lbl_state 要顯示什麼字、什麼顏色。"""
        running = status.running
        reason = status.last_reason

        if running:
            return {
                "text": self.runner.get_state_label(status.state),
                "text_color": self.lbl_state_default_color,
            }

        if reason in ERROR_REASONS:
            return {"text": "錯誤", "text_color": COLOR_ERROR}

        if reason == "target_reached":
            return {"text": REASON_LABEL[reason], "text_color": COLOR_DONE}

        if reason:
            return {
                "text": REASON_LABEL.get(reason, reason),
                "text_color": COLOR_MUTED,
            }

        return {"text": "—", "text_color": self.lbl_state_default_color}

    def handle_toggle(self) -> None:
        if self.runner.is_running():
            self.on_stop()
        else:
            self.on_start()

    def handle_save(self) -> None:
        self.on_save()

    def show_saved(self) -> None:
        self.lbl_message.configure(text="設定已儲存。", text_color=COLOR_DONE)
        self.message_until = time.monotonic() + 2.0


def run() -> None:
    log_path = cfg.logs_dir() / "fh6-automation.log"
    logger.add(str(log_path), rotation="2 MB", retention=5, enqueue=True)
    logger.info("Launching FH6 Automation (python {})", sys.version.split()[0])
    App().mainloop()
