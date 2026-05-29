"""主視窗。使用 PySide6 實作。"""

import os
import subprocess
import sys
import time
from typing import Callable

from loguru import logger
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIntValidator, QPalette, QColor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import config as cfg
from runner import StepRunner
from settings import SettingsWindow
from steps.buy_car import BuyCarRunner
from steps.farm_sp import FarmSPRunner
from steps.remove_car import RemoveCarRunner
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
COLOR_MUTED = "#9ca3af"
COLOR_ACCENT = "#3b82f6"
COLOR_TEXT = "#e5e7eb"
COLOR_BG = "#1f1f1f"
COLOR_PANEL = "#2a2a2a"
COLOR_BORDER = "#3a3a3a"
COLOR_HOVER = "#3a3a3a"
COLOR_DANGER_HOVER = "#b91c1c"

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


class App(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FH6 自動化")
        self.setMinimumSize(680, 520)
        self.resize(680, 520)

        self.conf = cfg.load()
        if self.conf.general.always_on_top:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        self.runners: dict[str, StepRunner] = {
            "farm_sp": FarmSPRunner(self.conf),
            "buy_car": BuyCarRunner(self.conf),
            "upgrade_car": UpgradeCarRunner(self.conf),
            "remove_car": RemoveCarRunner(self.conf),
        }
        self.step_order = list(self.runners.keys())
        self.current = self.step_order[0]

        self.step_btns: dict[str, QPushButton] = {}
        self.step_btn_selected: dict[str, bool | None] = {}
        self.step_frames: dict[str, "StepFrame"] = {}

        self.build_ui()
        self.show_step(self.current)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(REFRESH_MS)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start()

        if self.conf.general.auto_update:
            QTimer.singleShot(500, self.start_auto_update_check)

    def start_auto_update_check(self) -> None:
        updater.check_async(self, self.on_auto_update_result)

    def on_auto_update_result(self, result: "updater.CheckResult") -> None:
        if result.status != "available" or result.info is None:
            return
        if result.info.tag == self.conf.general.skipped_version:
            logger.info(
                "Skipping update prompt for {} (user previously skipped)",
                result.info.tag,
            )
            return
        updater.prompt_update(self, result.info)

    def trigger_manual_update_check(
        self,
        on_done: "Callable[[updater.CheckResult], None] | None" = None,
    ) -> None:
        """從設定頁觸發手動檢查；忽略 skipped_version。"""

        def callback(result: "updater.CheckResult") -> None:
            if result.status == "available" and result.info is not None:
                updater.prompt_update(self, result.info)
            if on_done:
                on_done(result)

        updater.check_async(self, callback)

    def runner(self, step_id: str) -> StepRunner:
        return self.runners[step_id]

    def any_running(self) -> str | None:
        for sid, r in self.runners.items():
            if r.is_running():
                return sid
        return None

    def build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)

        outer = QVBoxLayout(central)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(0)

        # Header
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        title = QLabel("超級轉盤刷取")
        title.setStyleSheet(
            f"color: {COLOR_TEXT}; font-size: {FONT_SIZE_TITLE}px; font-weight: bold;"
        )
        header.addWidget(title)
        header.addStretch(1)

        self.pill_dot = QLabel("●")
        self.pill_dot.setStyleSheet(
            f"color: {COLOR_IDLE}; font-size: {FONT_SIZE_TITLE}px;"
        )
        header.addWidget(self.pill_dot)

        self.pill_text = QLabel("閒置")
        self.pill_text.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: {FONT_SIZE_BODY}px;"
        )
        self.pill_text.setContentsMargins(4, 0, 0, 0)
        header.addWidget(self.pill_text)

        outer.addLayout(header)

        # Body: sidebar + stack
        body = QHBoxLayout()
        body.setContentsMargins(0, 12, 0, 0)
        body.setSpacing(12)

        sidebar = QFrame()
        sidebar.setStyleSheet(
            f"QFrame {{ background-color: {COLOR_PANEL}; border-radius: 6px; }}"
        )
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(6, 6, 6, 6)
        sidebar_layout.setSpacing(3)

        for sid in self.step_order:
            r = self.runner(sid)
            btn = QPushButton(r.label)
            btn.setFixedSize(120, 36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, s=sid: self.show_step(s))
            sidebar_layout.addWidget(btn)
            self.step_btns[sid] = btn
            self.step_btn_selected[sid] = None

        sidebar_layout.addStretch(1)
        body.addWidget(sidebar, 0)

        # Stacked content area
        self.stack = QStackedWidget()
        for sid in self.step_order:
            r = self.runner(sid)
            initial_quantity = self.initial_quantity_for(sid)
            frame = StepFrame(
                runner=r,
                initial_quantity=initial_quantity,
                on_start=lambda s=sid: self.on_start(s),
                on_stop=lambda s=sid: self.on_stop(s),
                on_save=lambda s=sid: self.on_save(s),
            )
            self.step_frames[sid] = frame
            self.stack.addWidget(frame)

        body.addWidget(self.stack, 1)
        outer.addLayout(body, 1)

        # Footer
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 12, 0, 0)
        footer.setSpacing(8)

        for text, cmd in (
            ("模板", self.open_templates),
            ("設定", self.open_config),
            ("紀錄", self.open_logs),
        ):
            btn = QPushButton(text)
            btn.setFixedSize(100, 30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {COLOR_TEXT};
                    border: 1px solid {COLOR_BORDER};
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background-color: {COLOR_HOVER};
                }}
                """)
            btn.clicked.connect(cmd)
            footer.addWidget(btn)

        footer.addStretch(1)
        outer.addLayout(footer)

    def initial_quantity_for(self, step_id: str) -> int:
        conf = self.conf

        return {
            "farm_sp": conf.farm_sp.target_runs,
            "buy_car": conf.buy_car.quantity,
            "upgrade_car": conf.upgrade_car.quantity,
            "remove_car": conf.remove_car.quantity,
        }[step_id]

    def update_tab_highlight(self) -> None:
        for sid, btn in self.step_btns.items():
            selected = sid == self.current
            if self.step_btn_selected[sid] != selected:
                if selected:
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {COLOR_ACCENT};
                            color: white;
                            border: none;
                            border-radius: 4px;
                            text-align: left;
                            padding-left: 12px;
                        }}
                        """)
                else:
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: transparent;
                            color: {COLOR_TEXT};
                            border: none;
                            border-radius: 4px;
                            text-align: left;
                            padding-left: 12px;
                        }}
                        QPushButton:hover {{
                            background-color: {COLOR_HOVER};
                        }}
                        """)
                self.step_btn_selected[sid] = selected

    def show_step(self, step_id: str) -> None:
        self.current = step_id
        self.stack.setCurrentWidget(self.step_frames[step_id])
        self.update_tab_highlight()

    def on_start(self, step_id: str) -> None:
        running = self.any_running()
        if running is not None:
            return

        frame = self.step_frames[step_id]
        target = frame.read_quantity()
        if target is None:
            return

        if step_id == "remove_car" and not self.confirm_delete(target):
            self.runner(step_id).mark_declined()
            return

        self.conf = cfg.load()
        self.save_step_settings(step_id, target)

        runner = self.runner(step_id)
        runner.conf = self.conf
        runner.start(target=target)

    def confirm_delete(self, target: int) -> bool:
        result = QMessageBox.question(
            self,
            "確認刪除",
            (
                f"即將從車庫刪除 {target} 輛車。\n"
                "此操作無法復原。\n\n"
                "請確認車輛清單頂端是要刪除的目標，確定要繼續嗎?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

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
        elif step_id == "remove_car":
            c.remove_car.quantity = target
        try:
            cfg.save(c)
        except OSError as e:
            logger.warning("Failed to persist config: {}", e)

    def open_templates(self) -> None:
        open_in_explorer(cfg.user_templates_dir())

    def open_config(self) -> None:
        dlg = SettingsWindow(
            self,
            self.conf,
            on_save=self.apply_settings,
            on_check_update=self.trigger_manual_update_check,
        )
        dlg.exec()

    def apply_settings(self, new_conf: cfg.Config) -> None:
        self.conf = new_conf
        # 切換置頂旗標需要重新顯示視窗
        was_visible = self.isVisible()
        self.setWindowFlag(
            Qt.WindowType.WindowStaysOnTopHint, new_conf.general.always_on_top
        )
        if was_visible:
            self.show()
        for r in self.runners.values():
            r.conf = new_conf

    def open_logs(self) -> None:
        open_in_explorer(cfg.logs_dir())

    def refresh(self) -> None:
        running_id = self.any_running()
        any_running = running_id is not None

        if any_running:
            label = self.runners[running_id].label
            self.pill_dot.setStyleSheet(
                f"color: {COLOR_RUNNING}; font-size: {FONT_SIZE_TITLE}px;"
            )
            self.pill_text.setText(f"執行中 ({label})")
            self.pill_text.setStyleSheet(
                f"color: {COLOR_RUNNING}; font-size: {FONT_SIZE_BODY}px;"
            )
        else:
            self.pill_dot.setStyleSheet(
                f"color: {COLOR_IDLE}; font-size: {FONT_SIZE_TITLE}px;"
            )
            self.pill_text.setText("閒置")
            self.pill_text.setStyleSheet(
                f"color: {COLOR_MUTED}; font-size: {FONT_SIZE_BODY}px;"
            )

        self.update_tab_highlight()

        frame = self.step_frames[self.current]
        other_running = any_running and running_id != self.current
        frame.refresh(disabled_due_to_other=other_running)


class StepFrame(QWidget):
    def __init__(
        self,
        runner: StepRunner,
        initial_quantity: int,
        on_start,
        on_stop,
        on_save,
    ) -> None:
        super().__init__()
        self.runner = runner
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_save = on_save
        self.last_btn_state: tuple[bool, bool] | None = None

        self.message_timer = QTimer(self)
        self.message_timer.setSingleShot(True)
        self.message_timer.timeout.connect(self.clear_message)

        # 用 sticky=True 標記目前訊息是錯誤訊息（由 refresh 維持），
        # 與 set_message 設定的暫時訊息區隔。
        self.message_sticky = False

        self.build_ui()
        self.qty_edit.setText(str(initial_quantity))

    def build_ui(self) -> None:
        runner = self.runner

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel(runner.label)
        title.setStyleSheet(
            f"color: {COLOR_TEXT}; font-size: {FONT_SIZE_HEADING}px; font-weight: bold;"
        )
        layout.addWidget(title)

        # 數量列
        qty_row = QHBoxLayout()
        qty_row.setContentsMargins(0, 8, 0, 8)
        qty_row.setSpacing(8)

        qty_label = QLabel(runner.quantity_label)
        qty_label.setStyleSheet(f"color: {COLOR_TEXT}; font-size: {FONT_SIZE_BODY}px;")
        qty_row.addWidget(qty_label)

        self.qty_edit = QLineEdit()
        self.qty_edit.setFixedWidth(80)
        self.qty_edit.setValidator(QIntValidator(1, 99999, self))
        self.qty_edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.qty_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLOR_PANEL};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                padding: 4px 6px;
            }}
            QLineEdit:disabled {{
                color: {COLOR_MUTED};
            }}
            """)
        qty_row.addWidget(self.qty_edit)
        qty_row.addStretch(1)

        layout.addLayout(qty_row)

        # 開始/停止按鈕
        self.toggle_btn = QPushButton("開始")
        self.toggle_btn.setFixedHeight(38)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.handle_toggle)
        self.apply_toggle_default_style()
        layout.addWidget(self.toggle_btn)

        # 儲存設定列
        save_row = QHBoxLayout()
        save_row.setContentsMargins(0, 6, 0, 10)
        save_row.addStretch(1)

        self.save_btn = QPushButton("儲存設定")
        self.save_btn.setFixedSize(100, 28)
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_HOVER};
            }}
            QPushButton:disabled {{
                color: {COLOR_MUTED};
            }}
            """)
        self.save_btn.clicked.connect(self.handle_save)
        save_row.addWidget(self.save_btn)
        layout.addLayout(save_row)

        # 統計面板
        stats = QFrame()
        stats.setStyleSheet(
            f"QFrame {{ background-color: {COLOR_PANEL}; border-radius: 6px; }}"
        )
        stats_layout = QGridLayout(stats)
        stats_layout.setContentsMargins(12, 8, 12, 8)
        stats_layout.setHorizontalSpacing(8)
        stats_layout.setVerticalSpacing(4)
        stats_layout.setColumnStretch(0, 0)
        stats_layout.setColumnStretch(1, 1)

        self.lbl_progress = self.stat(stats_layout, 0, runner.progress_label, "0 / 0")
        self.lbl_state = self.stat(stats_layout, 1, "狀態", "—")
        self.lbl_score = self.stat(stats_layout, 2, "分數", "0.000")
        self.lbl_threshold = self.stat(stats_layout, 3, "門檻", "0.85")
        self.lbl_elapsed = self.stat(stats_layout, 4, "耗時", "0:00")

        layout.addWidget(stats)

        # 訊息列
        self.lbl_message = QLabel("")
        self.lbl_message.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: {FONT_SIZE_BODY}px;"
        )
        self.lbl_message.setContentsMargins(0, 8, 0, 0)
        layout.addWidget(self.lbl_message)

        layout.addStretch(1)

    def apply_toggle_default_style(self) -> None:
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ACCENT};
                color: white;
                border: none;
                border-radius: 4px;
                font-size: {FONT_SIZE_BODY}px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #2563eb;
            }}
            QPushButton:disabled {{
                background-color: {COLOR_BORDER};
                color: {COLOR_MUTED};
            }}
            """)

    def apply_toggle_stop_style(self) -> None:
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ERROR};
                color: white;
                border: none;
                border-radius: 4px;
                font-size: {FONT_SIZE_BODY}px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLOR_DANGER_HOVER};
            }}
            """)

    def stat(self, grid: QGridLayout, row: int, label: str, value: str) -> QLabel:
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {COLOR_MUTED}; font-size: {FONT_SIZE_BODY}px;")
        grid.addWidget(lbl, row, 0, Qt.AlignmentFlag.AlignLeft)

        v = QLabel(value)
        v.setStyleSheet(
            f"color: {COLOR_TEXT}; font-size: {FONT_SIZE_BODY}px; font-weight: bold;"
        )
        grid.addWidget(v, row, 1, Qt.AlignmentFlag.AlignLeft)
        return v

    def read_quantity(self) -> int | None:
        raw = self.qty_edit.text().strip()

        try:
            target = int(raw)
        except ValueError:
            self.set_message("數量無效 (請輸入正整數)。", COLOR_ERROR)
            return None

        if target < 1:
            self.set_message("數量至少要 1。", COLOR_ERROR)
            return None

        return target

    def refresh(self, disabled_due_to_other: bool) -> None:
        runner = self.runner
        status = runner.get_status()
        running = status.running

        btn_state = (running, disabled_due_to_other)

        if btn_state != self.last_btn_state:
            if running:
                self.toggle_btn.setText("停止")
                self.toggle_btn.setEnabled(True)
                self.apply_toggle_stop_style()
            else:
                self.toggle_btn.setText("開始")
                self.toggle_btn.setEnabled(not disabled_due_to_other)
                self.apply_toggle_default_style()

            locked = running or disabled_due_to_other
            self.qty_edit.setEnabled(not locked)
            self.save_btn.setEnabled(not locked)

            self.last_btn_state = btn_state

        # 狀態顯示
        state_info = self.compute_state_display(status)
        self.lbl_state.setText(state_info["text"])
        self.lbl_state.setStyleSheet(
            f"color: {state_info['color']}; font-size: {FONT_SIZE_BODY}px; "
            f"font-weight: bold;"
        )

        from_conf_threshold = runner.conf.match.threshold

        score_text = (
            f"{status.score:.3f}  ({status.match_name})"
            if status.match_name
            else f"{status.score:.3f}"
        )
        self.lbl_score.setText(score_text)
        self.lbl_score.setStyleSheet(
            f"color: {score_color(status.score, from_conf_threshold)}; "
            f"font-size: {FONT_SIZE_BODY}px; font-weight: bold;"
        )

        target_str = str(status.target) if status.target >= 1 else "—"

        self.lbl_progress.setText(f"{status.progress} / {target_str}")
        self.lbl_threshold.setText(f"{from_conf_threshold:.2f}")

        elapsed = int(status.elapsed_s)
        m, s = divmod(elapsed, 60)
        h, m = divmod(m, 60)
        self.lbl_elapsed.setText(f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}")

        if status.last_reason in ERROR_REASONS:
            self.message_sticky = True
            self.message_timer.stop()
            self.lbl_message.setText(status.message or "")
            self.lbl_message.setStyleSheet(
                f"color: {COLOR_ERROR}; font-size: {FONT_SIZE_BODY}px;"
            )
        elif self.message_sticky:
            # 從錯誤狀態切回正常，清掉訊息
            self.message_sticky = False
            self.lbl_message.setText("")
            self.lbl_message.setStyleSheet(
                f"color: {COLOR_MUTED}; font-size: {FONT_SIZE_BODY}px;"
            )

    def compute_state_display(self, status) -> dict:
        """根據 runner 狀態決定 lbl_state 要顯示什麼字、什麼顏色。"""
        running = status.running
        reason = status.last_reason

        if running:
            return {
                "text": self.runner.get_state_label(status.state),
                "color": COLOR_TEXT,
            }

        if reason in ERROR_REASONS:
            return {"text": "錯誤", "color": COLOR_ERROR}

        if reason == "target_reached":
            return {"text": REASON_LABEL[reason], "color": COLOR_RUNNING}

        if reason:
            return {
                "text": REASON_LABEL.get(reason, reason),
                "color": COLOR_MUTED,
            }

        return {"text": "—", "color": COLOR_TEXT}

    def handle_toggle(self) -> None:
        if self.runner.is_running():
            self.on_stop()
        else:
            self.on_start()

    def handle_save(self) -> None:
        self.on_save()

    def show_saved(self) -> None:
        self.set_message("設定已儲存。", COLOR_RUNNING)

    def set_message(self, text: str, color: str, duration_ms: int = 3000) -> None:
        self.message_sticky = False
        self.lbl_message.setText(text)
        self.lbl_message.setStyleSheet(
            f"color: {color}; font-size: {FONT_SIZE_BODY}px;"
        )
        self.message_timer.start(duration_ms)

    def clear_message(self) -> None:
        if self.message_sticky:
            return
        self.lbl_message.setText("")
        self.lbl_message.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: {FONT_SIZE_BODY}px;"
        )


def apply_dark_palette(app: QApplication) -> None:
    app.setStyle("Fusion")

    palette = QPalette()
    bg = QColor(COLOR_BG)
    panel = QColor(COLOR_PANEL)
    text = QColor(COLOR_TEXT)
    disabled = QColor(COLOR_MUTED)
    accent = QColor(COLOR_ACCENT)

    palette.setColor(QPalette.ColorRole.Window, bg)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, panel)
    palette.setColor(QPalette.ColorRole.AlternateBase, bg)
    palette.setColor(QPalette.ColorRole.ToolTipBase, panel)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled)
    palette.setColor(QPalette.ColorRole.Button, panel)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled
    )
    palette.setColor(QPalette.ColorRole.Highlight, accent)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    palette.setColor(QPalette.ColorRole.Link, accent)

    app.setPalette(palette)


def run() -> None:
    log_path = cfg.logs_dir() / "fh6-automation.log"
    logger.add(str(log_path), rotation="2 MB", retention=5, enqueue=True)
    logger.info("Launching FH6 Automation (python {})", sys.version.split()[0])

    # 避免 Qt 嘗試重複設定 DPI awareness 時輸出警告（已由系統或其他模組設定）。
    os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.window=false")

    qt_app = QApplication.instance() or QApplication(sys.argv)
    apply_dark_palette(qt_app)  # type: ignore[arg-type]

    window = App()
    window.show()

    sys.exit(qt_app.exec())
