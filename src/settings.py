"""設定視窗。"""

import customtkinter as ctk
from loguru import logger

import config as cfg


class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent, conf: cfg.Config, on_save=None) -> None:
        super().__init__(parent)
        self.title("設定")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.conf = conf
        self.on_save = on_save

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
        self.var_scale = self.entry(scroll, "縮放 (scale)", conf.match.scale)

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
            font=ctk.CTkFont(size=14, weight="bold"),
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
                    scale=float(self.var_scale.get()),
                ),
                input=cfg.InputCfg(
                    press_hold_ms=int(self.var_press_hold.get()),
                    between_press_ms=int(self.var_between_press.get()),
                    jitter_ms=int(self.var_jitter.get()),
                ),
                farm_sp=self.conf.farm_sp,
                buy_car=self.conf.buy_car,
                upgrade_car=self.conf.upgrade_car,
                delete=self.conf.delete,
            )

            cfg.save(conf)

            if self.on_save:
                self.on_save(conf)
            self.destroy()

        except (ValueError, OSError) as e:
            logger.warning("Failed to save settings: {}", e)
