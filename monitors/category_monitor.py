from __future__ import annotations

import asyncio
import logging
from time import monotonic

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
    ) -> None:
        self.category = category
        self.page = page
        self.scraper = scraper
        self.database = database
        self.notification_queue = notification_queue
        self.interval_seconds = interval_seconds
        self.page_timeout_ms = page_timeout_ms
        self.logger = logging.getLogger(category.key.upper())

    async def run(self, stop_event: asyncio.Event) -> None:
        self.page.set_default_timeout(self.page_timeout_ms)
        while not stop_event.is_set():
            started = monotonic()
            try:
                await self.scan_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger.exception("Scan failed; retrying on the next cycle")
            remaining = max(0.0, self.interval_seconds - (monotonic() - started))
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=remaining)
            except TimeoutError:
                pass

    async def scan_once(self) -> list[Project]:
        self.logger.info("Scan started")
        await self.page.goto(self.category.url, wait_until="domcontentloaded", timeout=self.page_timeout_ms)
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

