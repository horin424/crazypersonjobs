from __future__ import annotations

import pytest

from database import Database
from models import Project


def project(project_id: str, position: int, *, platform: str = "lancers", category: str = "cat-a") -> Project:
    return Project(
        platform=platform, category_key=category, category_name=category,
        project_id=project_id, project_url=f"https://example.test/{project_id}",
        title=f"Project {project_id}", price="100円", client_name="Client",
        scraped_at="2026-10-02T12:00:00+09:00", position=position,
    )


@pytest.mark.asyncio
async def test_duplicate_and_cross_platform_ids(tmp_path):
    db = Database(tmp_path / "test.db")
    await db.connect()
    try:
        await db.ingest_scan("cat-a", [project("123", 1)])
        await db.ingest_scan("cat-a", [project("123", 1)])
        await db.ingest_scan("cat-cw", [project("123", 1, platform="crowdworks", category="cat-cw")])
        assert await db.count_projects() == 2
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_baseline_then_subsequent_scan_notification_state(tmp_path):
    db = Database(tmp_path / "test.db")
    await db.connect()
    try:
        baseline = [project(str(number), number) for number in range(1, 11)]
        notifications, inserted = await db.ingest_scan("cat-a", baseline)
        assert inserted == 10
        assert notifications == []
        assert await db.pending_notifications() == []

        updated = baseline + [project("11", 11)]
        notifications, inserted = await db.ingest_scan("cat-a", updated)
        assert inserted == 1
        assert [item.project_id for item in notifications] == ["11"]
        row = await db.get_project("lancers", "10")
        assert row["notification_required"] == 0
        row = await db.get_project("lancers", "11")
        assert row["notification_required"] == 1
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_scrape_history_survives_restart(tmp_path):
    path = tmp_path / "test.db"
    db = Database(path)
    await db.connect()
    await db.ingest_scan("cat-a", [project("old-1", 1), project("old-2", 2)])
    await db.close()

    reopened = Database(path)
    await reopened.connect()
    try:
        notifications, inserted = await reopened.ingest_scan(
            "cat-a", [project("new-1", 1), project("old-1", 2), project("old-2", 3)]
        )
        assert inserted == 1
        assert [item.project_id for item in notifications] == ["new-1"]
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_legacy_database_is_migrated_without_renotifying_baseline(tmp_path):
    legacy_path = tmp_path / "old" / "monitor.db"
    legacy = Database(legacy_path)
    await legacy.connect()
    await legacy.ingest_scan("cat-a", [project("old", 1)])
    await legacy.connection.execute(
        "UPDATE projects SET notification_required = 1 WHERE project_id = 'old'"
    )
    await legacy.connection.commit()
    await legacy.close()

    new_path = tmp_path / "new" / "monitor.db"
    migrated = Database(new_path, legacy_path)
    await migrated.connect()
    try:
        assert await migrated.count_projects() == 1
        assert await migrated.pending_notifications() == []
        notifications, inserted = await migrated.ingest_scan("cat-a", [project("old", 1)])
        assert inserted == 0
        assert notifications == []
    finally:
        await migrated.close()


@pytest.mark.asyncio
async def test_same_project_in_two_categories_only_queues_once(tmp_path):
    db = Database(tmp_path / "test.db")
    await db.connect()
    try:
        await db.ingest_scan("cat-a", [project("old-a", 1, category="cat-a")])
        await db.ingest_scan("cat-b", [project("old-b", 1, category="cat-b")])
        first, _ = await db.ingest_scan("cat-a", [project("42", 1, category="cat-a")])
        second, _ = await db.ingest_scan("cat-b", [project("42", 1, category="cat-b")])
        assert len(first) == 1
        assert second == []
        await db.mark_notification_sent("lancers", "42")
        assert await db.pending_notifications() == []
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_empty_scan_does_not_initialize_category(tmp_path):
    db = Database(tmp_path / "test.db")
    await db.connect()
    try:
        with pytest.raises(ValueError):
            await db.ingest_scan("cat-a", [])
        assert not await db.is_initialized("cat-a")
    finally:
        await db.close()
