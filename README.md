# OWL Stock Data Pipeline

Take-home assignment (Senior Software Engineer, Data): normalize denormalized historical stock CSV data, load it idempotently into SQLite, and demonstrate analytics on the schema.

## Problem summary

Source data is a wide CSV with company name, date, price/volume, and sector columns repeated on every row.

| Commit | Scope |
|--------|--------|
| **Commit 1** | Normalized schema, idempotent loader, join + aggregation query |
| **Commit 2** | Add `mktcap_usd`, backfill existing rows, apply Apple 2-for-1 split price/volume updates |

## Data files

| File | Role |
|------|------|
| `stock-data-se-owl.xlsx` | Commit 1 source |
| `data/stock-data-se-owl.csv` | v1 denormalized CSV |
| `stock-data-se-owl-part2.xlsx` | Commit 2 source (v2) |
| `data/stock-data-se-owl-v2.csv` | v2 denormalized CSV (`mktcap_usd` + Apple split) |

The bundled `owl_stock.xlsx_reader` reads these workbooks directly (their OOXML namespace is not handled cleanly by openpyxl/pandas).

## Schema

- `companies` — one row per issuer (`name` unique)
- `sectors` — distinct `(sector_level1, sector_level2)` pairs
- `company_sectors` — company → sector (one sector per company in this dataset)
- `daily_prices` — grain `(company_id, asof)` with `volume`, `close_usd`, `mktcap_usd` (nullable until v2 backfill)
- `schema_migrations` — tracks applied DDL migrations

Natural key for facts: **company + date**. Upserts use `ON CONFLICT` so re-running the loader updates changed prices/volumes without duplicating rows.

## Usage

```bash
# Commit 1 — v1 source
python pipeline.py export
python pipeline.py run --export-from-xlsx --query

# Commit 2 — migrate + load v2 (backfill mktcap, update Apple split-adjusted rows)
python pipeline.py export --source v2
python pipeline.py run --source v2 --export-from-xlsx --query

# Re-run v1 after v2: price/mktcap from v2 are preserved where v1 omits mktcap
python pipeline.py load --source v1
```

## Commit 2 design

### Schema migration

`owl_stock/migrations.py` adds `mktcap_usd` to existing Commit 1 databases via `ALTER TABLE`, recorded in `schema_migrations`. Fresh installs get the column from `schema.sql`.

### Backfill strategy

When the CSV includes `mktcap_usd`, each upsert writes the value. On conflict:

```sql
mktcap_usd = COALESCE(excluded.mktcap_usd, daily_prices.mktcap_usd)
```

- **v2 load after v1**: NULL mktcap rows receive values from the file (full backfill).
- **v1 load after v2**: rows without `mktcap_usd` in the file do not wipe existing backfilled values.

### Apple split propagation

Apple's v2 rows have split-adjusted `close_usd` (halved) and `volume` (doubled). These flow through the same `(company_id, asof)` upsert as any other correction — no special-case logic. Cumulative return is ratio-based, so split adjustment does not change total return; price and volume levels do update in the database.

## Example queries

**Cumulative return** (`owl_stock/queries.py`) — joins companies, sectors, and first/last daily prices:

\[
\text{cumulative\_return} = \frac{\text{close on last date}}{\text{close on first date}} - 1
\]

**Latest market cap** (Commit 2) — joins companies, sectors, and the most recent `daily_prices` row per company, using backfilled `mktcap_usd`.

## Idempotency

- Dimension tables: `INSERT ... ON CONFLICT DO NOTHING` (companies/sectors) or `DO UPDATE` (company sector assignment).
- Facts: `INSERT ... ON CONFLICT(company_id, asof) DO UPDATE` on `volume`, `close_usd`, and optionally `mktcap_usd`.
- Re-running `load` or `run` on the same or revised CSV leaves the DB consistent with the file contents.

## Scale notes

- **Ingest**: batch commits (default 1000 rows), single SQLite writer; at scale use Postgres + `COPY`/staging tables and merge with `MERGE`/upsert.
- **Migrations**: versioned DDL in `migrations.py`; at scale use Flyway/Liquibase or Alembic with backward-compatible expand-only changes.
- **Change detection**: optional `content_hash` or `updated_at` on `daily_prices` for audit; source row `#` is not a stable key (it can change between file versions).