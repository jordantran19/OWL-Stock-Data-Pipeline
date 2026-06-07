"""Example analytics queries against the normalized schema."""

from __future__ import annotations

import sqlite3
from pathlib import Path

CUMULATIVE_RETURN_SQL = """
SELECT
    c.name AS company,
    s.sector_level1,
    s.sector_level2,
    MIN(dp.asof) AS period_start,
    MAX(dp.asof) AS period_end,
    first_px.close_usd AS start_close_usd,
    last_px.close_usd AS end_close_usd,
    ROUND(last_px.close_usd / first_px.close_usd - 1.0, 6) AS cumulative_return
FROM companies c
JOIN company_sectors cs ON cs.company_id = c.id
JOIN sectors s ON s.id = cs.sector_id
JOIN daily_prices dp ON dp.company_id = c.id
JOIN daily_prices first_px
    ON first_px.company_id = c.id
   AND first_px.asof = (
        SELECT MIN(asof) FROM daily_prices WHERE company_id = c.id
   )
JOIN daily_prices last_px
    ON last_px.company_id = c.id
   AND last_px.asof = (
        SELECT MAX(asof) FROM daily_prices WHERE company_id = c.id
   )
GROUP BY c.id
ORDER BY cumulative_return DESC;
"""


def run_cumulative_return_query(db_path: Path) -> list[sqlite3.Row]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        return list(connection.execute(CUMULATIVE_RETURN_SQL))


def format_results(rows: list[sqlite3.Row]) -> str:
    if not rows:
        return "(no rows)"
    headers = rows[0].keys()
    lines = [" | ".join(headers)]
    lines.append("-" * len(lines[0]))
    for row in rows:
        lines.append(" | ".join(str(row[column]) for column in headers))
    return "\n".join(lines)
