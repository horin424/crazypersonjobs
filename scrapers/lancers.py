from __future__ import annotations

from playwright.async_api import Page

from config import CategoryConfig
from models import Project
from scrapers.base import BaseScraper, absolute_url, extract_project_id
from utils.text import normalize_text
from utils.time_utils import now_jst_iso


class LancersSelectors:
    PROJECT_BLOCK = ".p-search-job-media__content-right"
    TITLE_LINK = "a.p-search-job-media__title.c-media__title"
    PRICE = ".p-search-job-media__price"
    CLIENT = ".p-search-job-media__avatar-note.c-avatar__note"


class LancersScraper(BaseScraper):
    ready_selector = LancersSelectors.PROJECT_BLOCK

    async def scrape(self, page: Page, category: CategoryConfig) -> list[Project]:
        projects: list[Project] = []
        blocks = page.locator(LancersSelectors.PROJECT_BLOCK)
        for index in range(await blocks.count()):
            block = blocks.nth(index)
            link = block.locator(LancersSelectors.TITLE_LINK).first
            href = await link.get_attribute("href") if await link.count() else None
            if not href:
                continue
            url = absolute_url("https://www.lancers.jp", href)
            project_id = extract_project_id(url, "lancers")
            if not project_id:
                continue
            price_node = block.locator(LancersSelectors.PRICE).first
            client_node = block.locator(LancersSelectors.CLIENT).first
            projects.append(Project(
                platform="lancers", category_key=category.key, category_name=category.name,
                project_id=project_id, project_url=url,
                title=normalize_text(await link.inner_text()),
                price=normalize_text(await price_node.inner_text()) if await price_node.count() else "",
                client_name=normalize_text(await client_node.inner_text()) if await client_node.count() else "",
                scraped_at=now_jst_iso(), position=index + 1,
            ))
        return projects

