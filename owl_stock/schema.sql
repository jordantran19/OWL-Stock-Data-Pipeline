-- Normalized stock history schema (Commit 1).

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS sectors (
    id INTEGER PRIMARY KEY,
    sector_level1 TEXT NOT NULL,
    sector_level2 TEXT NOT NULL,
    UNIQUE (sector_level1, sector_level2)
);

-- One sector assignment per company in this dataset.
CREATE TABLE IF NOT EXISTS company_sectors (
    company_id INTEGER NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
    sector_id INTEGER NOT NULL REFERENCES sectors (id),
    PRIMARY KEY (company_id)
);

CREATE TABLE IF NOT EXISTS daily_prices (
    company_id INTEGER NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
    asof TEXT NOT NULL,
    volume INTEGER NOT NULL,
    close_usd REAL NOT NULL,
    PRIMARY KEY (company_id, asof)
);

CREATE INDEX IF NOT EXISTS idx_daily_prices_asof ON daily_prices (asof);
