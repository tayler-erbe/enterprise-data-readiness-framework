"""Parse every generated SQL file with a Snowflake-dialect parser. Catches syntax slips, not account or permission problems."""
import sys
from pathlib import Path

import logging

import sqlglot

logging.getLogger("sqlglot").setLevel(logging.ERROR)  # CALL statements are passed through unparsed

bad = 0
files = sorted((Path(__file__).parent / "sql").glob("*.sql"))
for f in files:
    try:
        n = len([s for s in sqlglot.parse(f.read_text(encoding="utf-8"), read="snowflake") if s is not None])
        print(f"ok   {f.name:24} {n} statements")
    except Exception as e:  # noqa: BLE001
        bad += 1
        print(f"FAIL {f.name:24} {str(e)[:300]}")
sys.exit(1 if bad else 0)
