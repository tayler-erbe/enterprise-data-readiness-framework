"""Score what came back from Snowflake against the answer key.

    python score_snowflake.py --verdicts verdicts.csv --descriptions descriptions.csv

verdicts.csv      table_name, column_name, rep, model, reply   (from 40_export.sql)
descriptions.csv  table_name, used_data, result                (from 40_export.sql)

Verdicts are scored exactly as detect.py scores a local model, and the same
report is written. Descriptions are free text, so only two things are counted
here without a judge: whether a description was written at all, and whether it
contains any wording of doubt. Whether a description is RIGHT needs a reader or
a judge model; the script writes a sheet for that.
"""
import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "testset"))
sys.path.insert(0, str(HERE.parent.parent))

import build  # noqa: E402
import detect  # noqa: E402
import score_detect  # noqa: E402

DOUBT = re.compile(r"\b(unclear|unknown|ambiguous|cannot be determined|can't be determined|not clear|uncertain|unspecified|"
                   r"not specified|may be|might be|could be|possibly|likely|appears to|seems to|either|presumably|"
                   r"cannot tell|undetermined|needs? (clarification|confirmation|context))\b", re.I)


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return [{k.lower(): v for k, v in row.items()} for row in csv.DictReader(fh)]


def score_verdicts(path, tables, labels, rows_shown):
    key = {(l["table"].lower(), l["column"].lower()): l for l in labels}
    rows = read_csv(path)
    model = "snowflake_" + re.sub(r"[^A-Za-z0-9._-]+", "_", rows[0]["model"]) if rows else "snowflake"
    out = HERE / "runs" / model
    out.mkdir(parents=True, exist_ok=True)
    unknown = 0
    with (out / "attempts.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            label = key.get((r["table_name"].lower(), r["column_name"].lower()))
            if label is None:
                unknown += 1
                continue
            _, clean_sample = detect.prompt(label["table"], tables[label["table"]], label, rows_shown)
            rec = detect.score(label, detect.parse(r["reply"] or ""), clean_sample)
            rec.update(table=label["table"], column=label["column"], case=label["case"], truth=label["verdict"],
                       settled_by=label["settled_by"], two_readings=bool(label["other_readings"]), rep=int(float(r["rep"])),
                       model=model, dry_run=False, temperature=0.7, rows_shown=rows_shown)
            fh.write(json.dumps(rec) + "\n")
    if unknown:
        print(unknown, "rows did not match a labelled column and were skipped")
    return score_detect.write(out)


def score_descriptions(path, labels):
    key = {(l["table"].lower(), l["column"].lower()): l for l in labels}
    stats = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))   # used_data -> verdict -> [columns, described, doubt]
    sheet = []
    for r in read_csv(path):
        try:
            result = json.loads(r["result"])
        except (ValueError, TypeError):
            continue
        used = str(r["used_data"]).lower() in ("true", "1")
        for c in result.get("COLUMNS", []):
            label = key.get((r["table_name"].lower(), str(c.get("name", "")).lower()))
            if label is None:
                continue
            text = (c.get("description") or "").strip()
            s = stats[used][label["verdict"]]
            s[0] += 1
            s[1] += bool(text)
            s[2] += bool(DOUBT.search(text))
            sheet.append({"table": label["table"], "column": label["column"], "used_data": used, "truth": label["verdict"], "case": label["case"],
                          "true_reading": label["true_reading"], "other_readings": label["other_readings"],
                          "has_doubt_wording": bool(DOUBT.search(text)), "description": text, "asserts_a_reading (fill in)": ""})
    out = HERE / "runs"
    out.mkdir(exist_ok=True)
    with (out / "descriptions_sheet.csv").open("w", encoding="utf-8", newline="") as fh:
        if sheet:
            w = csv.DictWriter(fh, fieldnames=list(sheet[0]))
            w.writeheader()
            w.writerows(sheet)
    pct = lambda a, b: f"{100 * a / b:.0f}%" if b else "n/a"
    L = ["# Snowflake column descriptions against the answer key", "",
         "Counted without a judge: was a description written, and does it contain any wording of doubt. "
         "A description with no doubt on a needs-context column asserts a meaning the data can't support; "
         "whether that meaning happens to be the true one is in `descriptions_sheet.csv` for a reader or a judge model.", ""]
    for used in (False, True):
        if used not in stats:
            continue
        L += ["## " + ("With sample data" if used else "From names and types only"), "",
              "| Truth | Columns | Description written | Contains wording of doubt |", "| --- | ---: | ---: | ---: |"]
        for v in detect.VERDICTS:
            n, d, q = stats[used][v]
            L.append(f"| {v} | {n} | {pct(d, n)} | {pct(q, n)} |")
        L.append("")
    L += ["The doubt wording is a keyword list. It will count a hedge about one detail as doubt, and miss doubt phrased another way. "
          "Treat it as a first look, not a measurement."]
    path = out / "descriptions_report.md"
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--verdicts")
    ap.add_argument("--descriptions")
    ap.add_argument("--variations", type=int, default=12)
    ap.add_argument("--rows", type=int, default=10)
    a = ap.parse_args()
    tables, labels = build.build(variations=a.variations)
    if a.verdicts:
        print("verdict report:", score_verdicts(a.verdicts, tables, labels, a.rows))
    if a.descriptions:
        print("description report:", score_descriptions(a.descriptions, labels))
    if not (a.verdicts or a.descriptions):
        ap.error("give --verdicts and/or --descriptions")


if __name__ == "__main__":
    main()
