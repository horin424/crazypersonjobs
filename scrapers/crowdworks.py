from __future__ import annotations

from playwright.async_api import Page

from config import CategoryConfig
from models import Project
from scrapers.base import BaseScraper, absolute_url, extract_project_id
from utils.text import normalize_text
from utils.time_utils import now_jst_iso


class CrowdWorksSelectors:
    TITLE_LINK = 'a[class*="_titleLinkPc_"][href*="/public/jobs/"]'
    # Find a card by walking from a valid title link to the nearest ancestor containing payment or client data.
    PROJECT_BLOCK = f'{TITLE_LINK} >> xpath=ancestor::div[.//*[contains(@class,"_amountPc_")] or .//*[contains(@class,"_userNameLink_")]][last()]'
    PRICE = '[class*="_amountPc_"]'
    CLIENT = 'a[class*="_userNameLink_"]'


class CrowdWorksScraper(BaseScraper):
    ready_selector = CrowdWorksSelectors.TITLE_LINK

    async def scrape(self, page: Page, category: CategoryConfig) -> list[Project]:
        projects: list[Project] = []
        links = page.locator(CrowdWorksSelectors.TITLE_LINK)
        seen: set[str] = set()
        for index in range(await links.count()):
            link = links.nth(index)
            href = await link.get_attribute("href")
            if not href:
                continue
            url = absolute_url("https://crowdworks.jp", href)
            project_id = extract_project_id(url, "crowdworks")
            if not project_id or project_id in seen:
                continue
            seen.add(project_id)
            # Generated card class suffixes change; locate the closest sufficiently rich ancestor.
            card = link.locator(
                'xpath=ancestor::div[.//*[contains(@class,"_amountPc_")] and '
                './/*[contains(@class,"_userNameLink_")]][1]'
            )
            if not await card.count():
                card = link.locator(
                    'xpath=ancestor::div[.//*[contains(@class,"_amountPc_")] or '
                    './/*[contains(@class,"_userNameLink_")]][1]'
                )
            price_node = card.locator(CrowdWorksSelectors.PRICE).first
            client_node = card.locator(CrowdWorksSelectors.CLIENT).first
            projects.append(Project(
                platform="crowdworks", category_key=category.key, category_name=category.name,
                project_id=project_id, project_url=url,
                title=normalize_text(await link.inner_text()),
                price=normalize_text(await price_node.inner_text()) if await price_node.count() else "",
                client_name=normalize_text(await client_node.inner_text()) if await client_node.count() else "",
                scraped_at=now_jst_iso(), position=len(projects) + 1,
            ))
        return projects
