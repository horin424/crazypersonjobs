from __future__ import annotations

import asyncio
import logging
import config
from services.slack_notifier import SlackNotifier
from runtime import MonitorRuntime
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
    notifier = SlackNotifier(config.SLACK_ENABLED, config.SLACK_WEBHOOK_URL)
    print_startup(notifier)
    runtime = MonitorRuntime()
    await runtime.run()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
