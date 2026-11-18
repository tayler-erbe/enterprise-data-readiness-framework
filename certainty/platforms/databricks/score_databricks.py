"""Score what came back from Databricks against the answer key.

    python score_databricks.py --verdicts verdicts.csv --comments comments.csv

verdicts.csv   table_name, column_name, rep, model, reply, error   (from 40_export.sql)
comments.csv   table_name, column_name, comment                    (from 40_export.sql)

Verdicts are scored exactly as detect.py scores a local model, and the same
report is written. Requests that came back with an error have an empty reply and
are counted as unreadable replies, not dropped.

Comments are the column descriptions saved from the AI generate button. They are
free text, so only two things are counted here without a judge: whether a
description was written at all, and whether it contains any wording of doubt.
Whether a description is RIGHT needs a reader or a judge model; the script
writes a sheet for that.
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "snowflake"))
sys.path.insert(0, str(HERE.parent.parent / "testset"))
sys.path.insert(0, str(HERE.parent.parent))

import build  # noqa: E402
import score_snowflake as shared  # noqa: E402  (the scoring is the same for every platform)


def comments(path):
    """(table, column, used sample data?, description). Databricks documents the feature as reading metadata, so False."""
    for r in shared.read_csv(path):
        yield r["table_name"], r["column_name"], False, r.get("comment") or ""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--verdicts")
    ap.add_argument("--comments")
    ap.add_argument("--variations", type=int, default=12)
    ap.add_argument("--rows", type=int, default=10)
    a = ap.parse_args()
    tables, labels = build.build(variations=a.variations)
    if a.verdicts:
        errors = sum(bool((r.get("error") or "").strip()) for r in shared.read_csv(a.verdicts))
        if errors:
            print(errors, "requests came back with an error; they are scored as unreadable replies")
        print("verdict report:", shared.score_verdicts(a.verdicts, tables, labels, a.rows, platform="databricks", here=HERE))
    if a.comments:
        print("description report:", shared.score_descriptions(comments(a.comments), labels, platform="Databricks", here=HERE))
    if not (a.verdicts or a.comments):
        ap.error("give --verdicts and/or --comments")


if __name__ == "__main__":
    main()
