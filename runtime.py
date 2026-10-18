from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

import config
from playwright.async_api import async_playwright
from database import Database
from models import Project
from monitors.category_monitor import CategoryMonitor
from scrapers.crowdworks import CrowdWorksScraper
from scrapers.lancers import LancersScraper
from services.notification_worker import notification_worker
from services.slack_notifier import SlackNotifier

logger = logging.getLogger("RUNTIME")
StatusCallback = Callable[[str, str], None]


class MonitorRuntime:
    """Owns the async browser, database, monitors, and notification worker."""

    def __init__(self, status_callback: StatusCallback | None = None, *, interval_seconds: float | None = None,
                 webhook_url: str | None = None) -> None:
        self.status_callback = status_callback
        self._loop: asyncio.AbstractEventLoop | None = None
        self._global_stop: asyncio.Event | None = None
        self._category_stops: dict[str, asyncio.Event] = {}
        self._monitor_tasks: dict[str, asyncio.Task[None]] = {}
        self._running = False
        self._interval_seconds = interval_seconds or config.SCAN_INTERVAL_SECONDS
        self._webhook_url = config.SLACK_WEBHOOK_URL if webhook_url is None else webhook_url
        self._monitors: dict[str, CategoryMonitor] = {}
        self._notifier: SlackNotifier | None = None

    @property
    def running(self) -> bool:
        return self._running

    def request_stop(self) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._stop_all_in_loop)

    def request_stop_category(self, category_key: str) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._stop_category_in_loop, category_key)

    def update_settings(self, interval_seconds: float, webhook_url: str) -> None:
        self._interval_seconds = max(1.0, interval_seconds)
        self._webhook_url = webhook_url.strip()
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._apply_settings_in_loop)

    def _apply_settings_in_loop(self) -> None:
        for monitor in self._monitors.values():
            monitor.set_interval(self._interval_seconds)
        if self._notifier is not None:
            self._notifier.configure(config.SLACK_ENABLED, self._webhook_url)
        logger.info("Settings updated: scan interval=%gs, Slack=%s", self._interval_seconds,
                    "ENABLED" if self._webhook_url else "MOCK MODE")

    def _stop_all_in_loop(self) -> None:
        if self._global_stop is not None:
            self._global_stop.set()
        for key in tuple(self._monitor_tasks):
            self._stop_category_in_loop(key)

    def _stop_category_in_loop(self, category_key: str) -> None:
        event = self._category_stops.get(category_key)
        if event is not None:
            event.set()
        task = self._monitor_tasks.get(category_key)
        if task is not None and not task.done():
            task.cancel()

    def _status(self, key: str, status: str) -> None:
        if self.status_callback is not None:
            self.status_callback(key, status)

    async def run(self) -> None:
        if self._running:
            raise RuntimeError("Monitor runtime is already running")
        self._running = True
        self._loop = asyncio.get_running_loop()
        self._global_stop = asyncio.Event()
        self._category_stops = {category.key: asyncio.Event() for category in config.CATEGORIES}
        database = Database(config.DATABASE_PATH, config.LEGACY_DATABASE_PATH)
        notifier = SlackNotifier(config.SLACK_ENABLED, self._webhook_url)
        self._notifier = notifier
        queue: asyncio.Queue[Project] = asyncio.Queue()
        worker: asyncio.Task[None] | None = None
        await database.connect()
        try:
            for project in await database.pending_notifications():
                await queue.put(project)
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=config.HEADLESS)
                try:
                    context = await browser.new_context(locale="ja-JP", timezone_id="Asia/Tokyo")
                    worker = asyncio.create_task(notification_worker(queue, database, notifier), name="notification-worker")
                    for category in config.CATEGORIES:
                        page = await context.new_page()
                        scraper = LancersScraper() if category.platform == "lancers" else CrowdWorksScraper()
                        monitor = CategoryMonitor(
                            category, page, scraper, database, queue,
                            self._interval_seconds, config.PAGE_TIMEOUT_MS, self._status,
                        )
                        self._monitors[category.key] = monitor
                        task = asyncio.create_task(
                            self._run_category(category.key, monitor, self._category_stops[category.key], page),
                            name=f"monitor-{category.key}",
                        )
                        self._monitor_tasks[category.key] = task
                        self._status(category.key, "RUNNING")
                    logger.info("Seven independent category monitors started")
                    await self._global_stop.wait()
                finally:
                    self._stop_all_in_loop()
                    await asyncio.gather(*self._monitor_tasks.values(), return_exceptions=True)
                    if worker is not None:
                        try:
                            await asyncio.wait_for(queue.join(), timeout=5)
                        except TimeoutError:
                            logger.warning("Timed out waiting for pending notifications")
                        worker.cancel()
                        await asyncio.gather(worker, return_exceptions=True)
                    await browser.close()
        finally:
            await database.close()
            self._running = False
            self._loop = None
            self._monitor_tasks.clear()
            self._monitors.clear()
            self._notifier = None
            for category in config.CATEGORIES:
                self._status(category.key, "STOPPED")
            logger.info("Monitor runtime stopped")

    async def _run_category(self, key: str, monitor: CategoryMonitor, stop_event: asyncio.Event, page) -> None:
        try:
            await monitor.run(stop_event)
        finally:
            await page.close()
            self._status(key, "STOPPED")
