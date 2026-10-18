from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import aiosqlite

from models import Project
from utils.time_utils import now_jst_iso


class Database:
    def __init__(self, path: Path, legacy_path: Path | None = None) -> None:
        self.path = path
        self.legacy_path = legacy_path
        self._connection: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if (self.legacy_path is not None and self.legacy_path != self.path
                and self.legacy_path.exists() and not self.path.exists()):
            await asyncio.to_thread(self._migrate_legacy_database)
        self._connection = await aiosqlite.connect(self.path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute("PRAGMA journal_mode=WAL")
        await self._connection.execute("PRAGMA foreign_keys=ON")
        await self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                platform TEXT NOT NULL,
                project_id TEXT NOT NULL,
                category_key TEXT NOT NULL,
                category_name TEXT NOT NULL,
                project_url TEXT NOT NULL,
                title TEXT,
                price TEXT,
                client_name TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                initial_position INTEGER,
                notification_required INTEGER NOT NULL DEFAULT 0,
                notification_sent INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (platform, project_id)
            );
            CREATE INDEX IF NOT EXISTS idx_projects_notification
                ON projects(notification_required, notification_sent);
            CREATE INDEX IF NOT EXISTS idx_projects_category ON projects(category_key);
            CREATE TABLE IF NOT EXISTS monitor_state (
                category_key TEXT PRIMARY KEY,
                initialized INTEGER NOT NULL DEFAULT 0,
                initialized_at TEXT,
                last_successful_scan TEXT
            );
            """
        )
        # Builds before this fix treated the first three baseline rows as new.
        # They are identifiable by initial_position and must never be retried.
        await self._connection.execute(
            """UPDATE projects SET notification_required = 0
               WHERE initial_position IS NOT NULL AND notification_sent = 0"""
        )
        await self._connection.commit()

    def _migrate_legacy_database(self) -> None:
        source = sqlite3.connect(self.legacy_path)
        destination = sqlite3.connect(self.path)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()

    @property
    def connection(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError("Database is not connected")
        return self._connection

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def is_initialized(self, category_key: str) -> bool:
        async with self._lock:
            cursor = await self.connection.execute(
                "SELECT initialized FROM monitor_state WHERE category_key = ?", (category_key,)
            )
            row = await cursor.fetchone()
            return bool(row and row["initialized"])

    async def ingest_scan(self, category_key: str, projects: list[Project]) -> tuple[list[Project], int]:
        """Atomically persist one successful non-empty scan and return notifications and insert count."""
        if not projects:
            raise ValueError("Refusing to initialize or update a category from an empty parse")
        async with self._lock:
            db = self.connection
            await db.execute("BEGIN IMMEDIATE")
            try:
                cursor = await db.execute(
                    "SELECT initialized FROM monitor_state WHERE category_key = ?", (category_key,)
                )
                state = await cursor.fetchone()
                baseline = not bool(state and state["initialized"])
                notifications: list[Project] = []
                inserted_count = 0
                for project in projects:
                    # The first successful scan establishes history only. Every
                    # later insert is genuinely new and requires notification.
                    required = not baseline
                    cursor = await db.execute(
                        """
                        INSERT INTO projects (
                            platform, project_id, category_key, category_name, project_url,
                            title, price, client_name, first_seen_at, last_seen_at,
                            initial_position, notification_required, notification_sent
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                        ON CONFLICT(platform, project_id) DO NOTHING
                        """,
                        (
                            project.platform, project.project_id, project.category_key,
                            project.category_name, project.project_url, project.title,
                            project.price, project.client_name, project.scraped_at,
                            project.scraped_at, project.position if baseline else None, int(required),
                        ),
                    )
                    if cursor.rowcount == 1:
                        inserted_count += 1
                        if required:
                            notifications.append(project.requiring_notification())
                    else:
                        await db.execute(
                            "UPDATE projects SET last_seen_at = ? WHERE platform = ? AND project_id = ?",
                            (project.scraped_at, project.platform, project.project_id),
                        )
                now = now_jst_iso()
                await db.execute(
                    """
                    INSERT INTO monitor_state(category_key, initialized, initialized_at, last_successful_scan)
                    VALUES (?, 1, ?, ?)
                    ON CONFLICT(category_key) DO UPDATE SET
                        initialized = 1,
                        initialized_at = COALESCE(monitor_state.initialized_at, excluded.initialized_at),
                        last_successful_scan = excluded.last_successful_scan
                    """,
                    (category_key, now, now),
                )
                await db.commit()
                return notifications, inserted_count
            except BaseException:
                await db.rollback()
                raise

    async def pending_notifications(self) -> list[Project]:
        async with self._lock:
            cursor = await self.connection.execute(
                """SELECT * FROM projects
                   WHERE notification_required = 1 AND notification_sent = 0
                   ORDER BY first_seen_at"""
            )
            rows = await cursor.fetchall()
        return [self._row_to_project(row) for row in rows]

    async def mark_notification_sent(self, platform: str, project_id: str) -> None:
        async with self._lock:
            await self.connection.execute(
                "UPDATE projects SET notification_sent = 1 WHERE platform = ? AND project_id = ?",
                (platform, project_id),
            )
            await self.connection.commit()

    async def count_projects(self) -> int:
        async with self._lock:
            cursor = await self.connection.execute("SELECT COUNT(*) AS count FROM projects")
            row = await cursor.fetchone()
            return int(row["count"])

    async def get_project(self, platform: str, project_id: str) -> aiosqlite.Row | None:
        async with self._lock:
            cursor = await self.connection.execute(
                "SELECT * FROM projects WHERE platform = ? AND project_id = ?", (platform, project_id)
            )
            return await cursor.fetchone()

    @staticmethod
    def _row_to_project(row: aiosqlite.Row) -> Project:
        return Project(
            platform=row["platform"], category_key=row["category_key"],
            category_name=row["category_name"], project_id=row["project_id"],
            project_url=row["project_url"], title=row["title"] or "",
            price=row["price"] or "", client_name=row["client_name"] or "",
            scraped_at=row["first_seen_at"], position=row["initial_position"],
            notification_required=bool(row["notification_required"]),
        )
