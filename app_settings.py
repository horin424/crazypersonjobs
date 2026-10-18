from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSettings

import config


@dataclass(frozen=True, slots=True)
class AppSettings:
    webhook_url: str
    interval_seconds: float


class SettingsStore:
    """Persistent, setup-free settings for the packaged Windows application."""

    def __init__(self) -> None:
        self._settings = QSettings("CrowdsourcingMonitor", "CrowdsourcingMonitor")

    def load(self) -> AppSettings:
        webhook = str(self._settings.value("slack/webhook_url", config.SLACK_WEBHOOK_URL)).strip()
        raw_interval = self._settings.value("monitor/interval_seconds", config.SCAN_INTERVAL_SECONDS)
        try:
            interval = max(1.0, float(raw_interval))
        except (TypeError, ValueError):
            interval = config.SCAN_INTERVAL_SECONDS
        return AppSettings(webhook, interval)

    def save(self, settings: AppSettings) -> None:
        self._settings.setValue("slack/webhook_url", settings.webhook_url.strip())
        self._settings.setValue("monitor/interval_seconds", max(1.0, settings.interval_seconds))
        self._settings.sync()
        if self._settings.status() != QSettings.Status.NoError:
            raise RuntimeError("Windows could not persist the application settings")
