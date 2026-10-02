from __future__ import annotations

import pytest_asyncio
from playwright.async_api import async_playwright


@pytest_asyncio.fixture
async def browser_page():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            yield page
        finally:
            await browser.close()

