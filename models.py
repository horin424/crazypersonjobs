from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class Project:
    platform: str
    category_key: str
    category_name: str
    project_id: str
    project_url: str
    title: str
    price: str
    client_name: str
    scraped_at: str
    position: int | None = None
    notification_required: bool = False

    def requiring_notification(self) -> "Project":
        return replace(self, notification_required=True)

