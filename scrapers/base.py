from __future__ import annotations

import re
from abc import ABC, abstractmethod
from urllib.parse import urljoin, urlparse

from playwright.async_api import Page

from config import CategoryConfig
from models import Project


def absolute_url(base_url: str, href: str) -> str:
    return urljoin(base_url, href)


def extract_project_id(url: str, platform: str) -> str | None:
    path = urlparse(url).path
    pattern = r"/work/detail/(\d+)" if platform == "lancers" else r"/public/jobs/(\d+)"
    match = re.search(pattern, path)
    return match.group(1) if match else None


class BaseScraper(ABC):
    ready_selector: str

    @abstractmethod
    async def scrape(self, page: Page, category: CategoryConfig) -> list[Project]:
        raise NotImplementedError

