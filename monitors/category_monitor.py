from __future__ import annotations

import asyncio
import logging
from time import monotonic
from collections.abc import Callable

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from config import CategoryConfig
from database import Database
from models import Project
from scrapers.base import BaseScraper


class CategoryMonitor:
    def __init__(
        self,
        category: CategoryConfig,
        page: Page,
        scraper: BaseScraper,
        database: Database,
        notification_queue: asyncio.Queue[Project],
        interval_seconds: float,
        page_timeout_ms: int,
        status_callback: Callable[[str, str], None] | None = None,
    ) -> None:
        self.category = category
        self.page = page
        self.scraper = scraper
        self.database = database
        self.notification_queue = notification_queue
        self.interval_seconds = interval_seconds
        self.page_timeout_ms = page_timeout_ms
        self.logger = logging.getLogger(category.key.upper())
        self.status_callback = status_callback
        self._interval_changed = asyncio.Event()
        self._page_loaded = False

    def set_interval(self, interval_seconds: float) -> None:
        self.interval_seconds = max(1.0, interval_seconds)
        self._interval_changed.set()

    async def run(self, stop_event: asyncio.Event) -> None:
        self.page.set_default_timeout(self.page_timeout_ms)
        while not stop_event.is_set():
            started = monotonic()
            try:
                self._set_status("SCANNING")
                await self.scan_once()
                self._set_status("RUNNING")
            except asyncio.CancelledError:
                raise
            except Exception:
                self._set_status("ERROR")
                self.logger.exception("Scan failed; retrying on the next cycle")
            self._interval_changed.clear()
            remaining = max(0.0, self.interval_seconds - (monotonic() - started))
            stop_wait = asyncio.create_task(stop_event.wait())
            interval_wait = asyncio.create_task(self._interval_changed.wait())
            done, pending = await asyncio.wait(
                (stop_wait, interval_wait), timeout=remaining,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

    async def scan_once(self) -> list[Project]:
        self.logger.info("Scan started")
        await self._load_category_page()
        try:
            await self.page.wait_for_selector(self.scraper.ready_selector, timeout=self.page_timeout_ms)
        except PlaywrightTimeoutError as exc:
            title = await self.page.title()
            raise RuntimeError(
                f"Project selector not found (page title={title!r}); possible layout change or security challenge"
            ) from exc
        projects = await self.scraper.scrape(self.page, self.category)
        if not projects:
            raise RuntimeError("Selector appeared but no valid project URLs were parsed")
        notifications, inserted = await self.database.ingest_scan(self.category.key, projects)
        self.logger.info("%d projects parsed; %d new", len(projects), inserted)
        for project in notifications:
            await self.notification_queue.put(project)
            self.logger.info("Notification queued: %s", project.project_id)
        if not notifications:
            self.logger.info("No new notifications")
        return projects

    async def _load_category_page(self) -> None:
        if self.category.platform == "crowdworks" and self._page_loaded:
            self.logger.info("Reloading CrowdWorks category page")
            await self.page.reload(wait_until="domcontentloaded", timeout=self.page_timeout_ms)
        else:
            await self.page.goto(self.category.url, wait_until="domcontentloaded", timeout=self.page_timeout_ms)
            self._page_loaded = True

    def _set_status(self, status: str) -> None:
        if self.status_callback is not None:
            self.status_callback(self.category.key, status)
