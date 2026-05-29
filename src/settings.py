"""設定視窗。"""

from tkinter import messagebox
from typing import Callable

import customtkinter as ctk
from loguru import logger

import config as cfg
import updater

FONT_SIZE_HEADING = 14


class SettingsWindow(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        conf: cfg.Config,
        on_save=None,
        on_check_update: (
            Callable[[Callable[[updater.CheckResult], None]], None] | None
        ) = None,
    ) -> None:
        super().__init__(parent)
        self.title("設定")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.conf = conf
        self.on_save = on_save
        self.on_check_update = on_check_update

        w, h = 480, 560
        x = parent.winfo_x()
        y = parent.winfo_y()
        self.geometry(f"{w}x{h}+{x}+{y}")

        self.build_ui()
        self.after(100, self.focus)

    def build_ui(self) -> None:
        scroll = ctk.CTkScrollableFrame(self)
        scroll.pack(fill="both", expand=True, padx=16, pady=(16, 8))
        conf = self.conf

        self.section(scroll, "一般")
        self.var_dry_run = self.checkbox(
            scroll, "Dry Run（不實際執行消耗操作）", conf.general.dry_run
        )
        self.var_always_on_top = self.checkbox(
            scroll, "視窗置頂", conf.general.always_on_top
        )
        self.var_auto_update = self.checkbox(
            scroll, "啟動時檢查更新", conf.general.auto_update
        )

        self.update_row = ctk.CTkFrame(scroll, fg_color="transparent")
        self.update_row.pack(fill="x", pady=(4, 2))
        self.btn_check_update = ctk.CTkButton(
            self.update_row,
            text="立即檢查更新",
            width=140,
            command=self.handle_check_update,
        )
        self.btn_check_update.pack(side="left")
        self.lbl_update_status = ctk.CTkLabel(
            self.update_row, text="", text_color="gray60", anchor="w"
        )
        self.lbl_update_status.pack(side="left", padx=(8, 0), fill="x", expand=True)

        self.skipped_row = ctk.CTkFrame(scroll, fg_color="transparent")
        self.skipped_row.pack(fill="x", pady=(2, 2))
        self.lbl_skipped = ctk.CTkLabel(self.skipped_row, anchor="w", text="")
        self.lbl_skipped.pack(side="left", fill="x", expand=True)
        self.btn_clear_skip = ctk.CTkButton(
            self.skipped_row,
            text="清除",
            width=70,
            fg_color="transparent",
            border_width=1,
            command=self.handle_clear_skip,
        )
        self.btn_clear_skip.pack(side="right")
        self.refresh_skipped_row()

        self.section(scroll, "擷取")
        self.var_backend = self.dropdown(
            scroll, "Backend", conf.capture.backend, ["auto", "bettercam", "mss"]
        )
        self.var_fps = self.entry(scroll, "FPS", conf.capture.fps)

        self.section(scroll, "比對")
        self.var_threshold = self.entry(
            scroll, "門檻 (threshold)", conf.match.threshold
        )
        self.var_stale_timeout = self.entry(
            scroll, "未辨識逾時 (ms)", conf.match.stale_timeout_ms
        )
        self.var_stuck_timeout = self.entry(
            scroll, "卡住逾時 (ms)", conf.match.stuck_timeout_ms
        )

        self.section(scroll, "輸入")
        self.var_press_hold = self.entry(
            scroll, "按鍵持續 (ms)", conf.input.press_hold_ms
        )
        self.var_between_press = self.entry(
            scroll, "按鍵間隔 (ms)", conf.input.between_press_ms
        )
        self.var_jitter = self.entry(scroll, "抖動 (ms)", conf.input.jitter_ms)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(0, 16))

        ctk.CTkButton(btn_frame, text="儲存", width=100, command=self.save).pack(
            side="right", padx=(8, 0)
        )
        ctk.CTkButton(
            btn_frame,
            text="取消",
            width=100,
            fg_color="transparent",
            border_width=1,
            command=self.destroy,
        ).pack(side="right")

    def section(self, parent, title: str) -> None:
        ctk.CTkLabel(
            parent,
            text=title,
            font=ctk.CTkFont(size=FONT_SIZE_HEADING, weight="bold"),
        ).pack(fill="x", pady=(12, 4))

    def checkbox(self, parent, label: str, value: bool) -> ctk.BooleanVar:
        var = ctk.BooleanVar(value=value)
        ctk.CTkCheckBox(parent, text=label, variable=var).pack(fill="x", pady=2)
        return var

    def entry(self, parent, label: str, value) -> ctk.StringVar:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label, width=180, anchor="w").pack(side="left")
        var = ctk.StringVar(value=str(value))
        ctk.CTkEntry(row, textvariable=var, width=120).pack(side="right")
        return var

    def dropdown(
        self, parent, label: str, value: str, options: list[str]
    ) -> ctk.StringVar:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label, width=180, anchor="w").pack(side="left")
        var = ctk.StringVar(value=value)
        ctk.CTkOptionMenu(row, variable=var, values=options, width=120).pack(
            side="right"
        )
        return var

    def save(self) -> None:
        try:
            conf = cfg.Config(
                general=cfg.GeneralCfg(
                    dry_run=self.var_dry_run.get(),
                    always_on_top=self.var_always_on_top.get(),
                    auto_update=self.var_auto_update.get(),
                ),
                capture=cfg.CaptureCfg(
                    backend=self.var_backend.get(),
                    fps=int(self.var_fps.get()),
                ),
                match=cfg.MatchCfg(
                    threshold=float(self.var_threshold.get()),
                    stale_timeout_ms=int(self.var_stale_timeout.get()),
                    stuck_timeout_ms=int(self.var_stuck_timeout.get()),
                    reference_height=self.conf.match.reference_height,
                ),
                input=cfg.InputCfg(
                    press_hold_ms=int(self.var_press_hold.get()),
                    between_press_ms=int(self.var_between_press.get()),
                    jitter_ms=int(self.var_jitter.get()),
                ),
                farm_sp=self.conf.farm_sp,
                buy_car=self.conf.buy_car,
                upgrade_car=self.conf.upgrade_car,
                remove_car=self.conf.remove_car,
            )

            cfg.save(conf)

            if self.on_save:
                self.on_save(conf)
            self.destroy()

        except (ValueError, OSError) as e:
            logger.warning("Failed to save settings: {}", e)

    def refresh_skipped_row(self) -> None:
        skipped = self.conf.general.skipped_version
        if skipped:
            self.lbl_skipped.configure(text=f"已跳過版本：{skipped}")
            self.btn_clear_skip.configure(state="normal")
            self.skipped_row.pack(fill="x", pady=(2, 2))
        else:
            self.lbl_skipped.configure(text="")
            self.btn_clear_skip.configure(state="disabled")
            self.skipped_row.pack_forget()

    def handle_clear_skip(self) -> None:
        try:
            updater.clear_skip()
        except OSError as e:
            logger.warning("Failed to clear skipped_version: {}", e)
            return
        self.conf = cfg.load()
        self.refresh_skipped_row()

    def handle_check_update(self) -> None:
        if self.on_check_update is None:
            return
        self.btn_check_update.configure(state="disabled", text="檢查中…")
        self.lbl_update_status.configure(text="", text_color="gray60")
        self.on_check_update(self.on_check_update_result)

    def on_check_update_result(self, result: "updater.CheckResult") -> None:
        self.btn_check_update.configure(state="normal", text="立即檢查更新")
        if result.status == "available":
            # 對話框已由 App.trigger_manual_update_check 開出
            self.lbl_update_status.configure(text="發現新版本", text_color="#3b82f6")
        elif result.status == "up_to_date":
            self.lbl_update_status.configure(text="已是最新版本", text_color="#22c55e")
            messagebox.showinfo(
                "已是最新版本",
                "目前已是最新版本。",
                parent=self,
            )
        else:
            self.lbl_update_status.configure(text="檢查失敗", text_color="#ef4444")
            messagebox.showerror(
                "檢查失敗",
                result.error or "無法檢查更新",
                parent=self,
            )
