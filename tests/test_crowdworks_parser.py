from pathlib import Path

import pytest

from config import CategoryConfig
from scrapers.crowdworks import CrowdWorksScraper


@pytest.mark.asyncio
async def test_crowdworks_generated_suffixes_are_not_required(browser_page):
    html = (Path(__file__).parent / "fixtures" / "crowdworks.html").read_text(encoding="utf-8")
    await browser_page.set_content(html)
    category = CategoryConfig("crowdworks", "crowdworks_226", "226", "https://example.test")
    projects = await CrowdWorksScraper().scrape(browser_page, category)
    assert len(projects) == 1
    assert projects[0].project_id == "13497398"
    assert projects[0].title == "【未経験相談可能】 Java エンジニア募集"
    assert projects[0].price == "300,000円 ～ 400,000円"
    assert projects[0].client_name == "インテレクシス松田"

