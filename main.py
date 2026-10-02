from __future__ import annotations

import asyncio
import logging
import signal

from playwright.async_api import async_playwright

import config
from database import Database
from models import Project
from monitors.category_monitor import CategoryMonitor
from scrapers.crowdworks import CrowdWorksScraper
from scrapers.lancers import LancersScraper
from services.notification_worker import notification_worker
from services.slack_notifier import SlackNotifier
from utils.logging_setup import configure_logging

logger = logging.getLogger("MAIN")


def print_startup(notifier: SlackNotifier) -> None:
    names = "\n".join(f"✓ {c.platform.title()} {c.name}" for c in config.CATEGORIES)
    print(
        "========================================\n"
        "Crowdsourcing Project Monitor\n"
        "========================================\n\n"
        f"Monitoring:\n{names}\n\n"
        f"Scan interval:\n{config.SCAN_INTERVAL_SECONDS:g} seconds\n\n"
        f"Slack:\n{notifier.mode}\n\n"
        f"Database:\n{config.DATABASE_PATH}\n\n"
        "Starting 7 independent monitors...\n"
        "========================================",
        flush=True,
    )


async def run() -> None:
    configure_logging(config.LOG_PATH)
    database = Database(config.DATABASE_PATH)
    await database.connect()
    notifier = SlackNotifier(config.SLACK_ENABLED, config.SLACK_WEBHOOK_URL)
    queue: asyncio.Queue[Project] = asyncio.Queue()
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except (NotImplementedError, RuntimeError):
            pass

    print_startup(notifier)
    worker: asyncio.Task[None] | None = None
    monitor_tasks: list[asyncio.Task[None]] = []
    pages = []
    try:
        pending = await database.pending_notifications()
        for project in pending:
            await queue.put(project)
        if pending:
            logger.info("Recovered %d pending notifications", len(pending))

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=config.HEADLESS)
            try:
                context = await browser.new_context(locale="ja-JP", timezone_id="Asia/Tokyo")
                worker = asyncio.create_task(notification_worker(queue, database, notifier), name="notification-worker")
                for category in config.CATEGORIES:
                    page = await context.new_page()
                    pages.append(page)
                    scraper = LancersScraper() if category.platform == "lancers" else CrowdWorksScraper()
                    monitor = CategoryMonitor(
                        category, page, scraper, database, queue,
                        config.SCAN_INTERVAL_SECONDS, config.PAGE_TIMEOUT_MS,
                    )
                    monitor_tasks.append(
                        asyncio.create_task(monitor.run(stop_event), name=f"monitor-{category.key}")
                    )
                await stop_event.wait()
            finally:
                stop_event.set()
                for task in monitor_tasks:
                    task.cancel()
                await asyncio.gather(*monitor_tasks, return_exceptions=True)
                if worker is not None:
                    try:
                        await asyncio.wait_for(queue.join(), timeout=10)
                    except TimeoutError:
                        logger.warning("Timed out waiting for notification queue during shutdown")
                    worker.cancel()
                    await asyncio.gather(worker, return_exceptions=True)
                await browser.close()
    finally:
        await database.close()
        logger.info("Shutdown complete")


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

