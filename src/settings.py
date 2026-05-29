"""設定視窗。"""

from typing import Callable

import pydirectinput as pdi
from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import config as cfg
import updater

FONT_SIZE_HEADING = 14

LABEL_WIDTH = 180
FIELD_WIDTH = 120


class SettingsWindow(QDialog):
    def __init__(
        self,
        parent,
        conf: cfg.Config,
        on_save=None,
        on_check_update: Callable[[Callable[[updater.CheckResult], None]], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.setModal(True)
        self.setFixedSize(480, 560)
        # 視窗置頂，避免被遊戲視窗遮蓋。
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        self.conf = conf
        self.on_save = on_save
        self.on_check_update = on_check_update

        self.build_ui()

    def build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(8)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        form = QWidget()
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(2)
        form_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.form_layout = form_layout

        scroll.setWidget(form)
        outer.addWidget(scroll, stretch=1)

        conf = self.conf

        # 一般
        self.section("一般")
        self.var_dry_run = self.checkbox("Dry Run（不實際執行消耗操作）", conf.general.dry_run)
        self.var_always_on_top = self.checkbox("視窗置頂", conf.general.always_on_top)
        self.var_auto_update = self.checkbox("啟動時檢查更新", conf.general.auto_update)

        # 立即檢查更新按鈕 + 狀態文字
        update_row = QWidget()
        update_layout = QHBoxLayout(update_row)
        update_layout.setContentsMargins(0, 4, 0, 2)
        update_layout.setSpacing(8)

        self.btn_check_update = QPushButton("立即檢查更新")
        self.btn_check_update.setFixedWidth(140)
        self.btn_check_update.clicked.connect(self.handle_check_update)
        update_layout.addWidget(self.btn_check_update)

        self.lbl_update_status = QLabel("")
        self.lbl_update_status.setStyleSheet("color: gray;")
        update_layout.addWidget(self.lbl_update_status, stretch=1)

        form_layout.addWidget(update_row)

        # 已跳過版本顯示列
        self.skipped_row = QWidget()
        skipped_layout = QHBoxLayout(self.skipped_row)
        skipped_layout.setContentsMargins(0, 2, 0, 2)
        skipped_layout.setSpacing(8)

        self.lbl_skipped = QLabel("")
        skipped_layout.addWidget(self.lbl_skipped, stretch=1)

        self.btn_clear_skip = QPushButton("清除")
        self.btn_clear_skip.setFixedWidth(70)
        self.btn_clear_skip.clicked.connect(self.handle_clear_skip)
        skipped_layout.addWidget(self.btn_clear_skip)

        form_layout.addWidget(self.skipped_row)
        self.refresh_skipped_row()

        # 擷取
        self.section("擷取")
        self.var_backend = self.dropdown("Backend", conf.capture.backend, ["auto", "bettercam", "mss"])
        self.var_fps = self.entry("FPS", conf.capture.fps)

        # 比對
        self.section("比對")
        self.var_threshold = self.entry("門檻 (threshold)", conf.match.threshold)
        self.var_stale_timeout = self.entry("未辨識逾時 (ms)", conf.match.stale_timeout_ms)
        self.var_stuck_timeout = self.entry("卡住逾時 (ms)", conf.match.stuck_timeout_ms)

        # 輸入
        self.section("輸入")
        self.var_press_hold = self.entry("按鍵持續 (ms)", conf.input.press_hold_ms)
        self.var_between_press = self.entry("按鍵間隔 (ms)", conf.input.between_press_ms)
        self.var_jitter = self.entry("抖動 (ms)", conf.input.jitter_ms)

        # 刷技能點
        self.section("刷技能點")
        self.var_accel_key = self.entry("加速按鍵", conf.farm_sp.acceleration_key)
        self.var_accel_key.setToolTip("例如：w、space、up")
        self.var_accel_key.setPlaceholderText("w")

        # 底部按鈕列
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)
        btn_layout.addStretch(1)

        cancel = QPushButton("取消")
        cancel.setFixedWidth(100)
        cancel.clicked.connect(self.reject)
        btn_layout.addWidget(cancel)

        save = QPushButton("儲存")
        save.setFixedWidth(100)
        save.setDefault(True)
        save.clicked.connect(self.save)
        btn_layout.addWidget(save)

        outer.addWidget(btn_row)

    def section(self, title: str) -> None:
        """加上粗體的小節標題。"""
        label = QLabel(title)
        font = label.font()
        font.setPointSize(FONT_SIZE_HEADING)
        font.setBold(True)
        label.setFont(font)
        label.setContentsMargins(0, 12, 0, 4)
        self.form_layout.addWidget(label)

    def checkbox(self, label: str, value: bool) -> QCheckBox:
        cb = QCheckBox(label)
        cb.setChecked(bool(value))
        self.form_layout.addWidget(cb)
        return cb

    def entry(self, label: str, value) -> QLineEdit:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        lbl = QLabel(label)
        lbl.setMinimumWidth(LABEL_WIDTH)
        layout.addWidget(lbl)
        layout.addStretch(1)

        edit = QLineEdit(str(value))
        edit.setFixedWidth(FIELD_WIDTH)
        layout.addWidget(edit)

        self.form_layout.addWidget(row)
        return edit

    def dropdown(self, label: str, value: str, options: list[str]) -> QComboBox:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        lbl = QLabel(label)
        lbl.setMinimumWidth(LABEL_WIDTH)
        layout.addWidget(lbl)
        layout.addStretch(1)

        combo = QComboBox()
        combo.addItems(options)
        if value in options:
            combo.setCurrentText(value)
        combo.setFixedWidth(FIELD_WIDTH)
        layout.addWidget(combo)

        self.form_layout.addWidget(row)
        return combo

    def save(self) -> None:
        try:
            accel_key = self.var_accel_key.text().strip() or "w"
            if not pdi.isValidKey(accel_key):
                QMessageBox.critical(self, "儲存失敗", f"無效的按鍵名稱：{accel_key}")
                return

            conf = cfg.Config(
                general=cfg.GeneralCfg(
                    dry_run=self.var_dry_run.isChecked(),
                    always_on_top=self.var_always_on_top.isChecked(),
                    auto_update=self.var_auto_update.isChecked(),
                    skipped_version=self.conf.general.skipped_version,
                ),
                capture=cfg.CaptureCfg(
                    backend=self.var_backend.currentText(),
                    fps=int(self.var_fps.text()),
                ),
                match=cfg.MatchCfg(
                    threshold=float(self.var_threshold.text()),
                    stale_timeout_ms=int(self.var_stale_timeout.text()),
                    stuck_timeout_ms=int(self.var_stuck_timeout.text()),
                    reference_height=self.conf.match.reference_height,
                ),
                input=cfg.InputCfg(
                    press_hold_ms=int(self.var_press_hold.text()),
                    between_press_ms=int(self.var_between_press.text()),
                    jitter_ms=int(self.var_jitter.text()),
                ),
                farm_sp=cfg.FarmSPCfg(
                    target_runs=self.conf.farm_sp.target_runs,
                    acceleration_key=accel_key,
                ),
                buy_car=self.conf.buy_car,
                upgrade_car=self.conf.upgrade_car,
                remove_car=self.conf.remove_car,
            )

            cfg.save(conf)

            if self.on_save:
                self.on_save(conf)

            self.accept()

        except (ValueError, OSError) as e:
            logger.warning("Failed to save settings: {}", e)
            QMessageBox.critical(self, "儲存失敗", f"無法儲存設定：{e}")

    def refresh_skipped_row(self) -> None:
        skipped = self.conf.general.skipped_version
        if skipped:
            self.lbl_skipped.setText(f"已跳過版本：{skipped}")
            self.btn_clear_skip.setEnabled(True)
            self.skipped_row.setVisible(True)
        else:
            self.lbl_skipped.setText("")
            self.btn_clear_skip.setEnabled(False)
            self.skipped_row.setVisible(False)

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
        self.btn_check_update.setEnabled(False)
        self.btn_check_update.setText("檢查中…")
        self.lbl_update_status.setText("")
        self.lbl_update_status.setStyleSheet("color: gray;")
        self.on_check_update(self.on_check_update_result)

    def on_check_update_result(self, result: "updater.CheckResult") -> None:
        self.btn_check_update.setEnabled(True)
        self.btn_check_update.setText("立即檢查更新")
        if result.status == "available":
            # 對話框已由 App.trigger_manual_update_check 開出
            self.lbl_update_status.setText("發現新版本")
            self.lbl_update_status.setStyleSheet("color: #3b82f6;")
        elif result.status == "up_to_date":
            self.lbl_update_status.setText("已是最新版本")
            self.lbl_update_status.setStyleSheet("color: #22c55e;")
            QMessageBox.information(self, "已是最新版本", "目前已是最新版本。")
        else:
            self.lbl_update_status.setText("檢查失敗")
            self.lbl_update_status.setStyleSheet("color: #ef4444;")
            QMessageBox.critical(self, "檢查失敗", result.error or "無法檢查更新")
