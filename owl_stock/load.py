"""Idempotent CSV → SQLite loader for denormalized stock history."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Iterable

REQUIRED_COLUMNS = (
    "name",
    "asof",
    "volume",
    "close_usd",
    "sector_level1",
    "sector_level2",
)


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(db_path: Path, schema_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema_sql = schema_path.read_text(encoding="utf-8")
    with _connect(db_path) as connection:
        connection.executescript(schema_sql)


def _upsert_company(connection: sqlite3.Connection, name: str) -> int:
    connection.execute(
        "INSERT INTO companies (name) VALUES (?)"
        " ON CONFLICT(name) DO NOTHING",
        (name,),
    )
    row = connection.execute(
        "SELECT id FROM companies WHERE name = ?", (name,)
    ).fetchone()
    assert row is not None
    return int(row[0])


def _upsert_sector(
    connection: sqlite3.Connection, level1: str, level2: str
) -> int:
    connection.execute(
        "INSERT INTO sectors (sector_level1, sector_level2) VALUES (?, ?)"
        " ON CONFLICT(sector_level1, sector_level2) DO NOTHING",
        (level1, level2),
    )
    row = connection.execute(
        "SELECT id FROM sectors WHERE sector_level1 = ? AND sector_level2 = ?",
        (level1, level2),
    ).fetchone()
    assert row is not None
    return int(row[0])


def _upsert_company_sector(
    connection: sqlite3.Connection, company_id: int, sector_id: int
) -> None:
    connection.execute(
        "INSERT INTO company_sectors (company_id, sector_id) VALUES (?, ?)"
        " ON CONFLICT(company_id) DO UPDATE SET sector_id = excluded.sector_id",
        (company_id, sector_id),
    )


def _upsert_daily_price(
    connection: sqlite3.Connection,
    company_id: int,
    asof: str,
    volume: int,
    close_usd: float,
) -> None:
    connection.execute(
        """
        INSERT INTO daily_prices (company_id, asof, volume, close_usd)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(company_id, asof) DO UPDATE SET
            volume = excluded.volume,
            close_usd = excluded.close_usd
        """,
        (company_id, asof, volume, close_usd),
    )


def _parse_row(row: dict[str, str]) -> tuple[str, str, int, float, str, str]:
    name = row["name"].strip()
    asof = row["asof"].strip()
    volume = int(float(row["volume"]))
    close_usd = float(row["close_usd"])
    level1 = row["sector_level1"].strip()
    level2 = row["sector_level2"].strip()
    return name, asof, volume, close_usd, level1, level2


def load_csv(
    csv_path: Path,
    db_path: Path,
    schema_path: Path,
    *,
    batch_size: int = 1000,
) -> dict[str, int]:
    """Load or refresh the database from `csv_path`. Safe to run repeatedly."""
    init_db(db_path, schema_path)

    stats = {"rows_read": 0, "rows_upserted": 0}
    with _connect(db_path) as connection, csv_path.open(
        encoding="utf-8", newline=""
    ) as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV {csv_path} has no header row")

        missing = [column for column in REQUIRED_COLUMNS if column not in reader.fieldnames]
        if missing:
            raise ValueError(f"CSV missing required columns: {missing}")

        batch: list[tuple[str, str, int, float, str, str]] = []
        for row in reader:
            stats["rows_read"] += 1
            batch.append(_parse_row(row))
            if len(batch) >= batch_size:
                _flush_batch(connection, batch)
                stats["rows_upserted"] += len(batch)
                batch.clear()

        if batch:
            _flush_batch(connection, batch)
            stats["rows_upserted"] += len(batch)

        connection.commit()

    return stats


def _flush_batch(
    connection: sqlite3.Connection,
    batch: Iterable[tuple[str, str, int, float, str, str]],
) -> None:
    for name, asof, volume, close_usd, level1, level2 in batch:
        company_id = _upsert_company(connection, name)
        sector_id = _upsert_sector(connection, level1, level2)
        _upsert_company_sector(connection, company_id, sector_id)
        _upsert_daily_price(connection, company_id, asof, volume, close_usd)


def export_xlsx_to_csv(xlsx_path: Path, csv_path: Path) -> int:
    from owl_stock.xlsx_reader import sheet_to_records

    records = sheet_to_records(xlsx_path)
    if not records:
        raise ValueError(f"No data rows in {xlsx_path}")

    fieldnames = list(records[0].keys())
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    return len(records)
