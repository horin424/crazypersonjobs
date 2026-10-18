from __future__ import annotations

import asyncio
import certifi
import json
import logging
import ssl
import sys
from typing import Any
from urllib.request import Request, urlopen

from models import Project

logger = logging.getLogger("SLACK")


def create_portable_ssl_context() -> ssl.SSLContext:
    """Trust public CAs everywhere and locally installed enterprise CAs on Windows."""
    context = ssl.create_default_context(cafile=certifi.where())
    if sys.platform == "win32":
        for store_name in ("ROOT", "CA"):
            try:
                certificates = ssl.enum_certificates(store_name)
            except OSError:
                logger.warning("Could not read the Windows %s certificate store", store_name)
                continue
            for certificate, encoding, _trust in certificates:
                if encoding != "x509_asn":
                    continue
                try:
                    context.load_verify_locations(cadata=ssl.DER_cert_to_PEM_cert(certificate))
                except ssl.SSLError:
                    logger.debug("Skipped an unreadable certificate from Windows %s", store_name)
    return context


class SlackNotifier:
    def __init__(self, enabled: bool, webhook_url: str) -> None:
        self.ssl_context = create_portable_ssl_context()
        self.configure(enabled, webhook_url)
        if enabled and not webhook_url:
            logger.warning("SLACK_ENABLED is true but no webhook is configured; using MOCK MODE")

    def configure(self, enabled: bool, webhook_url: str) -> None:
        self.webhook_url = webhook_url.strip()
        self.enabled = enabled and bool(self.webhook_url)

    @property
    def mode(self) -> str:
        return "ENABLED" if self.enabled else "MOCK MODE"

    @staticmethod
    def _escape(text: str) -> str:
        return (text or "-").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def format_message(self, project: Project) -> str:
        """Accessible fallback used by notifications and Slack screen readers."""
        platform = "Lancers" if project.platform == "lancers" else "CrowdWorks"
        return (
            f"{platform} / {project.category_name} | {project.title or '-'} | "
            f"{project.price or '-'} | {project.client_name or '-'} | {project.project_url}"
        )

    def format_payload(self, project: Project) -> dict[str, Any]:
        platform = "Lancers" if project.platform == "lancers" else "CrowdWorks"
        details = (
            f"*Platform:* {self._escape(platform)}   •   *Category:* {self._escape(project.category_name)}\n"
            f"*Title:* {self._escape(project.title)}\n"
            f"*Price:* {self._escape(project.price)}\n"
            f"*Client:* {self._escape(project.client_name)}"
        )
        return {
            "text": self.format_message(project),
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": details}},
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*URL:*\n{self._escape(project.project_url)}"},
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Open URL", "emoji": True},
                        "url": project.project_url,
                        "action_id": "open_project_url",
                    },
                },
                {"type": "divider"},
            ],
        }

    async def send_project_notification(self, project: Project) -> None:
        payload = self.format_payload(project)
        if not self.enabled:
            logger.info("MOCK NOTIFICATION\n%s", payload["text"])
            return
        await asyncio.to_thread(self._post_webhook, payload)

    def _post_webhook(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(self.webhook_url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=15, context=self.ssl_context) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"Slack webhook returned HTTP {response.status}")
