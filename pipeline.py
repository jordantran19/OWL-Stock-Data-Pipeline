#!/usr/bin/env python3
"""CLI entry point for the stock data pipeline (Commit 1)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from owl_stock.load import export_xlsx_to_csv, load_csv
from owl_stock.queries import format_results, run_cumulative_return_query

ROOT = Path(__file__).resolve().parent
DEFAULT_CSV = ROOT / "data" / "stock-data-se-owl.csv"
DEFAULT_DB = ROOT / "data" / "stocks.db"
DEFAULT_SCHEMA = ROOT / "owl_stock" / "schema.sql"
DEFAULT_XLSX = ROOT / "stock-data-se-owl.xlsx"


def cmd_export(args: argparse.Namespace) -> int:
    count = export_xlsx_to_csv(Path(args.xlsx), Path(args.csv))
    print(f"Wrote {count} rows to {args.csv}")
    return 0


def cmd_load(args: argparse.Namespace) -> int:
    stats = load_csv(
        Path(args.csv),
        Path(args.db),
        Path(args.schema),
        batch_size=args.batch_size,
    )
    print(json.dumps(stats, indent=2))
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    rows = run_cumulative_return_query(Path(args.db))
    print(format_results(rows))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    csv_path = Path(args.csv)
    if args.export_from_xlsx and not csv_path.exists():
        export_xlsx_to_csv(Path(args.xlsx), csv_path)
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        return 1
    load_csv(csv_path, Path(args.db), Path(args.schema), batch_size=args.batch_size)
    if args.query:
        print()
        print("Cumulative return per company (join + aggregation):")
        print(format_results(run_cumulative_return_query(Path(args.db))))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OWL stock data pipeline")
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--xlsx", default=str(DEFAULT_XLSX))

    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser(
        "export", help="Export workbook to denormalized CSV"
    )
    export_parser.set_defaults(func=cmd_export)

    load_parser = subparsers.add_parser("load", help="Load CSV into SQLite")
    load_parser.add_argument("--batch-size", type=int, default=1000)
    load_parser.set_defaults(func=cmd_load)

    query_parser = subparsers.add_parser("query", help="Run example analytics query")
    query_parser.set_defaults(func=cmd_query)

    run_parser = subparsers.add_parser(
        "run", help="Load (and optionally export + query) end-to-end"
    )
    run_parser.add_argument(
        "--export-from-xlsx",
        action="store_true",
        help="Create CSV from xlsx when missing",
    )
    run_parser.add_argument("--query", action="store_true", help="Print example query")
    run_parser.add_argument("--batch-size", type=int, default=1000)
    run_parser.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
