#!/usr/bin/env python3
"""CLI entry point for the stock data pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from owl_stock.load import export_xlsx_to_csv, load_csv
from owl_stock.queries import (
    format_results,
    run_cumulative_return_query,
    run_latest_market_cap_query,
)

ROOT = Path(__file__).resolve().parent
DEFAULT_CSV = ROOT / "data" / "stock-data-se-owl.csv"
DEFAULT_CSV_V2 = ROOT / "data" / "stock-data-se-owl-v2.csv"
DEFAULT_DB = ROOT / "data" / "stocks.db"
DEFAULT_SCHEMA = ROOT / "owl_stock" / "schema.sql"
DEFAULT_XLSX = ROOT / "stock-data-se-owl.xlsx"
DEFAULT_XLSX_V2 = ROOT / "stock-data-se-owl-part2.xlsx"


def _resolve_source(args: argparse.Namespace) -> tuple[Path, Path]:
    version = getattr(args, "source", "v1")
    if version == "v2":
        return Path(args.csv_v2), Path(args.xlsx_v2)
    return Path(args.csv), Path(args.xlsx)


def cmd_export(args: argparse.Namespace) -> int:
    csv_path, xlsx_path = _resolve_source(args)
    count = export_xlsx_to_csv(xlsx_path, csv_path)
    print(f"Wrote {count} rows to {csv_path}")
    return 0


def cmd_load(args: argparse.Namespace) -> int:
    csv_path, _ = _resolve_source(args)
    stats = load_csv(
        csv_path,
        Path(args.db),
        Path(args.schema),
        batch_size=args.batch_size,
    )
    print(json.dumps(stats, indent=2, default=list))
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    print("Cumulative return per company:")
    print(format_results(run_cumulative_return_query(db_path)))
    if args.market_cap:
        print()
        print("Latest market cap per company:")
        print(format_results(run_latest_market_cap_query(db_path)))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    csv_path, xlsx_path = _resolve_source(args)
    if args.export_from_xlsx and not csv_path.exists():
        export_xlsx_to_csv(xlsx_path, csv_path)
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        return 1
    stats = load_csv(
        csv_path,
        Path(args.db),
        Path(args.schema),
        batch_size=args.batch_size,
    )
    print(json.dumps(stats, indent=2, default=list))
    if args.query:
        print()
        print("Cumulative return per company (join + aggregation):")
        print(format_results(run_cumulative_return_query(Path(args.db))))
        if stats.get("has_mktcap_column"):
            print()
            print("Latest market cap per company:")
            print(format_results(run_latest_market_cap_query(Path(args.db))))
    return 0


def _add_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source",
        choices=("v1", "v2"),
        default="v1",
        help="Source dataset version (v2 adds mktcap_usd and Apple split fixes)",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OWL stock data pipeline")
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    parser.add_argument("--csv-v2", default=str(DEFAULT_CSV_V2))
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--xlsx", default=str(DEFAULT_XLSX))
    parser.add_argument("--xlsx-v2", default=str(DEFAULT_XLSX_V2))

    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser(
        "export", help="Export workbook to denormalized CSV"
    )
    _add_source_args(export_parser)
    export_parser.set_defaults(func=cmd_export)

    load_parser = subparsers.add_parser("load", help="Load CSV into SQLite")
    _add_source_args(load_parser)
    load_parser.add_argument("--batch-size", type=int, default=1000)
    load_parser.set_defaults(func=cmd_load)

    query_parser = subparsers.add_parser("query", help="Run example analytics queries")
    query_parser.add_argument(
        "--market-cap",
        action="store_true",
        help="Also print latest market cap per company (Commit 2)",
    )
    query_parser.set_defaults(func=cmd_query)

    run_parser = subparsers.add_parser(
        "run", help="Load (and optionally export + query) end-to-end"
    )
    _add_source_args(run_parser)
    run_parser.add_argument(
        "--export-from-xlsx",
        action="store_true",
        help="Create CSV from xlsx when missing",
    )
    run_parser.add_argument("--query", action="store_true", help="Print example queries")
    run_parser.add_argument("--batch-size", type=int, default=1000)
    run_parser.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())