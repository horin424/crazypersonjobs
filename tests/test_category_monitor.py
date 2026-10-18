from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from config import CategoryConfig
from monitors.category_monitor import CategoryMonitor


def monitor_for(platform: str, page: Mock) -> CategoryMonitor:
    category = CategoryConfig(platform, "category", "Category", "https://example.test/category")
    return CategoryMonitor(category, page, Mock(), Mock(), Mock(), 60, 30_000)


@pytest.mark.asyncio
async def test_crowdworks_first_load_then_explicit_reload_each_cycle() -> None:
    page = Mock(goto=AsyncMock(), reload=AsyncMock())
    monitor = monitor_for("crowdworks", page)

    await monitor._load_category_page()
    await monitor._load_category_page()
    await monitor._load_category_page()

    page.goto.assert_awaited_once_with(
        "https://example.test/category", wait_until="domcontentloaded", timeout=30_000
    )
    assert page.reload.await_count == 2


@pytest.mark.asyncio
async def test_lancers_navigates_to_category_each_cycle() -> None:
    page = Mock(goto=AsyncMock(), reload=AsyncMock())
    monitor = monitor_for("lancers", page)

    await monitor._load_category_page()
    await monitor._load_category_page()

    assert page.goto.await_count == 2
    page.reload.assert_not_awaited()
