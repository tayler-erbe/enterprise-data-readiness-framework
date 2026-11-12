"""Command line: python -m readiness TABLES.csv [--columns COLUMNS.csv] --out DIR"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .checks import Settings
from .load import load_dictionary_pages, load_csv, load_openmetadata
from .report import summary_text, write_all
from .score import score_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m readiness",
        description="Score each table in a data dictionary export from 0 (undocumented) to 4 (AI-ready).",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("tables", nargs="?", help="CSV of tables (a data dictionary's table-list export works)")
    source.add_argument("--openmetadata", metavar="JSON", help="saved response from OpenMetadata GET /api/v1/tables")
    source.add_argument("--dictionary-pages", metavar="TXT", help="data dictionary table pages copied from the browser into one text file")
    parser.add_argument("--columns", metavar="CSV", help="CSV of columns: schema, table, column, type, comments, lookup, key")
    parser.add_argument("--out", metavar="DIR", default="readiness-output", help="where to write results (default: readiness-output)")
    parser.add_argument("--target", type=int, default=4, help="target level when a table has none (default: 4)")
    parser.add_argument("--coverage", type=float, default=0.8, help="share of columns described for level 2 (default: 0.8)")
    parser.add_argument("--min-questions", type=int, default=5, help="verified questions needed for level 4 (default: 5)")
    parser.add_argument("--check-links", action="store_true", help="request every link in descriptions and advisories")
    args = parser.parse_args(argv)

    settings = Settings(
        column_coverage=args.coverage,
        min_verified_questions=args.min_questions,
        default_target_level=args.target,
        check_links=args.check_links,
    )

    if args.dictionary_pages:
        tables = load_dictionary_pages(args.dictionary_pages)
        label = Path(args.dictionary_pages).name
    elif args.openmetadata:
        tables = load_openmetadata(args.openmetadata)
        label = Path(args.openmetadata).name
    else:
        tables = load_csv(args.tables, args.columns)
        label = Path(args.tables).name + (f" and {Path(args.columns).name}" if args.columns else "")

    if not tables:
        print("No tables found. Check the file's headers: it needs at least Name (and usually Schema).", file=sys.stderr)
        return 1

    scores = score_all(tables, settings)
    written = write_all(scores, Path(args.out), settings, label)
    print(summary_text(scores))
    for path in written:
        print(f"  wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
