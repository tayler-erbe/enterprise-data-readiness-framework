"""Build the labelled test set from the case catalogue.

    python build.py --variations 12 --out data

Each variation uses every case once, in a different domain with different
values, so `--variations 12` gives twelve examples of every kind of failure.
Cases are dealt into tables of about eight columns.

Writes:
    data/raw/<table>.csv      the table as it arrives
    data/clean/<table>.csv    the same rows, correctly prepared
    data/labels.csv           one row per column: the verdict, the issue, what settles it, the fix
    data/summary.json         counts
"""
import argparse
import csv
import json
import random
from collections import Counter
from pathlib import Path

from cases import CASES, DOMAINS

LABEL_FIELDS = ["table", "column", "case", "verdict", "issue", "meaning", "true_reading", "other_readings", "settled_by", "fix",
                "rows", "rows_changed", "helper_columns", "domain", "variation"]


def abbreviate(name):
    """customer_name -> cstmr_nm. Used only where the name is not the evidence."""
    parts = []
    for word in name.split("_"):
        short = word[0] + "".join(c for c in word[1:] if c not in "aeiou")
        parts.append(short if len(short) >= 2 else word)
    return "_".join(parts)


def build(variations=12, rows=120, per_table=8, seed=20261112):
    """Returns (tables, labels). tables: {name: {"header": [...], "raw": [[...]], "clean": [[...]]}}."""
    tables, labels = {}, []
    domains = list(DOMAINS)
    for var in range(variations):
        rng = random.Random(f"{seed}|{var}")
        order = list(CASES)
        rng.shuffle(order)
        for t, start in enumerate(range(0, len(order), per_table)):
            dom_name = domains[(var + t) % len(domains)]
            dom = DOMAINS[dom_name]
            tname = f"{dom_name}_{dom['entity']}_v{var:02d}_{t:02d}"
            header, raw_cols, clean_cols, used = [], [], [], set()

            def add(name, raw, clean):
                base, k = name, 2
                while name in used:
                    name = f"{base}_{k}"
                    k += 1
                used.add(name)
                header.append(name)
                raw_cols.append(raw)
                clean_cols.append(clean)
                return name

            for cid in order[start:start + per_table]:
                c = CASES[cid]
                col = c["make"](random.Random(f"{seed}|{var}|{cid}"), rows, dom)
                name = col["name"]
                if c["name_free"] and rng.random() < 0.3:
                    name = abbreviate(name)
                name = add(name, col["raw"], col["clean"])
                helpers = [add(h, v, v) for h, v in col.get("helpers", {}).items()]
                truth = col.get("truth", "")
                labels.append({
                    "table": tname, "column": name, "case": cid, "verdict": c["verdict"], "issue": c["issue"], "meaning": c["meaning"],
                    "true_reading": truth, "other_readings": "; ".join(a for a in c["alts"] if a != truth), "settled_by": c["settled_by"],
                    "fix": c["op"], "rows": rows, "rows_changed": sum(str(a) != str(b) for a, b in zip(col["raw"], col["clean"])),
                    "helper_columns": "; ".join(helpers), "domain": dom_name, "variation": var,
                })
            tables[tname] = {"header": header, "raw": [list(r) for r in zip(*raw_cols)], "clean": [list(r) for r in zip(*clean_cols)]}
    return tables, labels


def write(out, **kw):
    out = Path(out)
    tables, labels = build(**kw)
    for kind in ("raw", "clean"):
        (out / kind).mkdir(parents=True, exist_ok=True)
        for old in (out / kind).glob("*.csv"):
            old.unlink()
        for name, t in tables.items():
            with (out / kind / (name + ".csv")).open("w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(t["header"])
                w.writerows(t[kind])
    with (out / "labels.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LABEL_FIELDS)
        w.writeheader()
        w.writerows(labels)
    summary = {
        "synthetic": True,
        "tables": len(tables),
        "labelled_columns": len(labels),
        "cases": len(CASES),
        "examples_per_case": kw.get("variations", 12),
        "by_verdict": dict(Counter(l["verdict"] for l in labels)),
        "cases_by_verdict": dict(Counter(c["verdict"] for c in CASES.values())),
    }
    import tables as file_cases
    summary["whole_file"] = file_cases.write(out, kw.get("variations", 12))
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--variations", type=int, default=12, help="examples of each case")
    ap.add_argument("--rows", type=int, default=120)
    ap.add_argument("--out", default=str(Path(__file__).parent / "data"))
    a = ap.parse_args()
    print(json.dumps(write(a.out, variations=a.variations, rows=a.rows), indent=2))
