from pathlib import Path

import pytest

from config import CategoryConfig
from scrapers.lancers import LancersScraper


@pytest.mark.asyncio
async def test_lancers_block_parser(browser_page):
    html = (Path(__file__).parent / "fixtures" / "lancers.html").read_text(encoding="utf-8")
    await browser_page.set_content(html)
    category = CategoryConfig("lancers", "lancers_system", "System Development", "https://example.test")
    projects = await LancersScraper().scrape(browser_page, category)
    assert len(projects) == 1
    assert projects[0].project_id == "5610891"
    assert projects[0].title == "物資運搬装置の 遠隔操作システム"
    assert projects[0].price == "300,000円 ～ 500,000円 / 固定"
    assert projects[0].client_name == "ai_talent"

