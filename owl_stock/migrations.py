"""Incremental schema migrations applied after base schema creation."""

from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATIONS: list[tuple[str, str]] = [
    (
        "002_add_mktcap_usd",
        "ALTER TABLE daily_prices ADD COLUMN mktcap_usd REAL",
    ),
]


def _ensure_migrations_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def _column_exists(connection: sqlite3.Connection, table: str, column: str) -> bool:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def apply_migrations(connection: sqlite3.Connection) -> list[str]:
    """Apply pending migrations. Returns versions applied in this run."""
    _ensure_migrations_table(connection)
    applied: list[str] = []
    for version, sql in MIGRATIONS:
        already = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?", (version,)
        ).fetchone()
        if already:
            continue
        if version == "002_add_mktcap_usd" and _column_exists(
            connection, "daily_prices", "mktcap_usd"
        ):
            connection.execute(
                "INSERT INTO schema_migrations (version) VALUES (?)", (version,)
            )
            continue
        connection.execute(sql)
        connection.execute(
            "INSERT INTO schema_migrations (version) VALUES (?)", (version,)
        )
        applied.append(version)
    return applied


def migrate_db(db_path: Path) -> list[str]:
    with sqlite3.connect(db_path) as connection:
        applied = apply_migrations(connection)
        connection.commit()
    return applied