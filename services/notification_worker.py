from __future__ import annotations

import asyncio
import logging

from database import Database
from models import Project
from services.slack_notifier import SlackNotifier

logger = logging.getLogger("NOTIFICATIONS")


async def notification_worker(
    queue: asyncio.Queue[Project], database: Database, notifier: SlackNotifier
) -> None:
    while True:
        project = await queue.get()
        try:
            await notifier.send_project_notification(project)
            await database.mark_notification_sent(project.platform, project.project_id)
            logger.info("Notification sent: %s:%s", project.platform, project.project_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Notification failed; it remains pending: %s:%s", project.platform, project.project_id)
            await asyncio.sleep(5)
            await queue.put(project)
        finally:
            queue.task_done()

