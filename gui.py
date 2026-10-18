from __future__ import annotations

import asyncio
import logging
import sys
import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QCloseEvent, QFont
from PySide6.QtWidgets import (QApplication, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QMainWindow, QMessageBox, QPushButton,
                               QPlainTextEdit, QVBoxLayout, QWidget)

import config
from app_settings import AppSettings, SettingsStore
from runtime import MonitorRuntime
from services.slack_notifier import SlackNotifier
from utils.logging_setup import configure_logging


class UIBridge(QObject):
    log_received = Signal(str)
    category_status = Signal(str, str)
    runtime_stopped = Signal()


class UILogHandler(logging.Handler):
    def __init__(self, bridge: UIBridge) -> None:
        super().__init__()
        self.bridge = bridge
        self.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.bridge.log_received.emit(self.format(record))
        except Exception:
            self.handleError(record)


class MonitorWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Crowdsourcing Project Monitor")
        self.resize(920, 700)
        self.setMinimumSize(760, 560)
        self.runtime: MonitorRuntime | None = None
        self.runtime_thread: threading.Thread | None = None
        self._allow_close = False
        self.settings_store = SettingsStore()
        self.settings = self.settings_store.load()
        self.bridge = UIBridge()
        self.bridge.log_received.connect(self._append_log)
        self.bridge.category_status.connect(self._apply_category_status)
        self.bridge.runtime_stopped.connect(self._runtime_stopped)
        configure_logging(config.LOG_PATH, [UILogHandler(self.bridge)])
        self.status_labels: dict[str, QLabel] = {}
        self.category_buttons: dict[str, QPushButton] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        self.setCentralWidget(root)

        title = QLabel("Crowdsourcing Project Monitor")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        layout.addWidget(title)
        settings_row = QHBoxLayout()
        settings_row.addWidget(QLabel("Slack webhook:"))
        self.webhook_edit = QLineEdit(self.settings.webhook_url)
        self.webhook_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.webhook_edit.setPlaceholderText("https://hooks.slack.com/services/...")
        settings_row.addWidget(self.webhook_edit, stretch=1)
        settings_row.addWidget(QLabel("Interval (seconds):"))
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(1, 86400)
        self.interval_spin.setDecimals(0)
        self.interval_spin.setValue(self.settings.interval_seconds)
        settings_row.addWidget(self.interval_spin)
        self.save_settings_button = QPushButton("Save settings")
        self.save_settings_button.clicked.connect(self.save_settings)
        settings_row.addWidget(self.save_settings_button)
        layout.addLayout(settings_row)

        controls = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.start_button.setMinimumWidth(130)
        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setMinimumWidth(130)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_monitoring)
        self.overall_status = QLabel("Stopped")
        self._set_status_style(self.overall_status, "STOPPED")
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        controls.addStretch()
        controls.addWidget(self.overall_status)
        layout.addLayout(controls)

        category_frame = QFrame()
        category_frame.setFrameShape(QFrame.Shape.StyledPanel)
        category_layout = QVBoxLayout(category_frame)
        category_heading = QLabel("Categories")
        category_heading.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        category_layout.addWidget(category_heading)
        for category in config.CATEGORIES:
            row = QHBoxLayout()
            display = f"{'Lancers' if category.platform == 'lancers' else 'CrowdWorks'} - {category.name}"
            row.addWidget(QLabel(display))
            row.addStretch()
            status = QLabel("STOPPED")
            status.setMinimumWidth(85)
            status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._set_status_style(status, "STOPPED")
            button = QPushButton("Stop")
            button.setFixedWidth(75)
            button.setEnabled(False)
            button.clicked.connect(lambda _checked=False, key=category.key: self.stop_category(key))
            row.addWidget(status)
            row.addWidget(button)
            category_layout.addLayout(row)
            self.status_labels[category.key] = status
            self.category_buttons[category.key] = button
        layout.addWidget(category_frame)

        log_heading = QLabel("Logs")
        log_heading.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(log_heading)
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("background:#101418; color:#e5e7eb; border:1px solid #38414a;")
        layout.addWidget(self.log_text, stretch=1)

    def start_monitoring(self) -> None:
        if self.runtime_thread is not None and self.runtime_thread.is_alive():
            return
        self.save_settings(show_confirmation=False)
        self.runtime = MonitorRuntime(self.bridge.category_status.emit,
                                      interval_seconds=self.settings.interval_seconds,
                                      webhook_url=self.settings.webhook_url)
        self.runtime_thread = threading.Thread(target=self._run_runtime, name="monitor-runtime", daemon=True)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.overall_status.setText("Starting...")
        self._set_status_style(self.overall_status, "STARTING")
        for key, button in self.category_buttons.items():
            button.setEnabled(True)
            self.bridge.category_status.emit(key, "STARTING")
        self.runtime_thread.start()

    def save_settings(self, _checked: bool = False, *, show_confirmation: bool = True) -> None:
        settings = AppSettings(self.webhook_edit.text().strip(), self.interval_spin.value())
        try:
            self.settings_store.save(settings)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Settings", str(exc))
            return
        self.settings = settings
        if self.runtime is not None and self.runtime.running:
            self.runtime.update_settings(settings.interval_seconds, settings.webhook_url)
        if show_confirmation:
            mode = SlackNotifier(config.SLACK_ENABLED, settings.webhook_url).mode
            QMessageBox.information(self, "Settings", f"Settings saved. Slack: {mode}")

    def stop_monitoring(self) -> None:
        if self.runtime is not None:
            self.overall_status.setText("Stopping...")
            self._set_status_style(self.overall_status, "STOPPING")
            self.stop_button.setEnabled(False)
            self.runtime.request_stop()

    def stop_category(self, category_key: str) -> None:
        if self.runtime is not None:
            self.category_buttons[category_key].setEnabled(False)
            self.bridge.category_status.emit(category_key, "STOPPING")
            self.runtime.request_stop_category(category_key)

    def _run_runtime(self) -> None:
        try:
            asyncio.run(self.runtime.run())  # type: ignore[union-attr]
        except Exception:
            logging.getLogger("GUI").exception("Monitor failed to start or stopped unexpectedly")
        finally:
            self.bridge.runtime_stopped.emit()

    def _append_log(self, message: str) -> None:
        self.log_text.appendPlainText(message)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _apply_category_status(self, key: str, status: str) -> None:
        label = self.status_labels.get(key)
        if label is None:
            return
        label.setText(status)
        self._set_status_style(label, status)
        if status == "STOPPED":
            self.category_buttons[key].setEnabled(False)
        if status in {"RUNNING", "SCANNING", "ERROR"}:
            self.overall_status.setText("Running")
            self._set_status_style(self.overall_status, "RUNNING")

    def _runtime_stopped(self) -> None:
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.overall_status.setText("Stopped")
        self._set_status_style(self.overall_status, "STOPPED")
        for button in self.category_buttons.values():
            button.setEnabled(False)
        if self._allow_close:
            self.close()

    @staticmethod
    def _set_status_style(label: QLabel, status: str) -> None:
        colors = {"RUNNING": "#137333", "SCANNING": "#1769aa", "ERROR": "#b3261e", "STOPPED": "#777777"}
        label.setStyleSheet(f"color:{colors.get(status, '#946200')}; font-weight:600;")

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._allow_close or not (self.runtime_thread and self.runtime_thread.is_alive()):
            event.accept()
            return
        answer = QMessageBox.question(
            self, "Exit", "Stop monitoring and close the application?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._allow_close = True
            self.stop_monitoring()
        event.ignore()


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MonitorWindow()
    window.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
