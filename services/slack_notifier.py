from __future__ import annotations

import asyncio
import json
import logging
from urllib.request import Request, urlopen

from models import Project
from utils.time_utils import display_jst

logger = logging.getLogger("SLACK")


class SlackNotifier:
    def __init__(self, enabled: bool, webhook_url: str) -> None:
        self.webhook_url = webhook_url
        self.enabled = enabled and bool(webhook_url)
        if enabled and not webhook_url:
            logger.warning("SLACK_ENABLED is true but no webhook is configured; using MOCK MODE")

    @property
    def mode(self) -> str:
        return "ENABLED" if self.enabled else "MOCK MODE"

    def format_message(self, project: Project) -> str:
        platform = "Lancers" if project.platform == "lancers" else "CrowdWorks"
        return (
            f"🆕 *New Project*\n\n"
            f"*Platform:* {platform}\n"
            f"*Category:* {project.category_name}\n\n"
            f"*Title:*\n{project.title or '-'}\n\n"
            f"*Price:*\n{project.price or '-'}\n\n"
            f"*Client:*\n{project.client_name or '-'}\n\n"
            f"*Detected:* {display_jst(project.scraped_at)}\n\n"
            f"*URL:*\n{project.project_url}"
        )

    async def send_project_notification(self, project: Project) -> None:
        message = self.format_message(project)
        if not self.enabled:
            logger.info("MOCK NOTIFICATION\n%s", message)
            return
        await asyncio.to_thread(self._post_webhook, message)

    def _post_webhook(self, message: str) -> None:
        payload = json.dumps({"text": message}).encode("utf-8")
        request = Request(self.webhook_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=15) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"Slack webhook returned HTTP {response.status}")

