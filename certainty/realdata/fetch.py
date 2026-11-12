"""Download real dirty-and-clean table pairs to use as a control group.

    python fetch.py            # hospital, flights, beers, rayyan, movies_1
    python fetch.py --all      # also tax (about 29 MB)

These are the benchmark tables published with the Raha and Baran error
detection and correction systems (github.com/BigDaMa/raha). Each has a dirty
file and a clean file with the same rows, so every cell that differs is a
known error with a known correction.

They are NOT part of the main test. They have been public for years and are
used in most data-cleaning papers, so a model has probably seen them. They are
here for two things: to check that the detector's behaviour on generated
errors carries over to real ones, and to show what a score looks like on data
a model may have memorised.

The files are downloaded to data/, which is not committed. Nothing is
redistributed from this repository.
"""
import argparse
import csv
import io
import json
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
BASE = "https://raw.githubusercontent.com/BigDaMa/raha/master/datasets/{name}/{kind}.csv"
DEFAULT = ["hospital", "flights", "beers", "rayyan", "movies_1"]
LABEL_FIELDS = ["dataset", "column", "rows", "cells_changed", "share_changed", "has_errors", "examples"]


def read_csv(text):
    return list(csv.reader(io.StringIO(text)))


def compare(name, dirty, clean):
    """One label per column: how many cells differ between the dirty and the clean file."""
    header, drows, crows = dirty[0], dirty[1:], clean[1:]
    n = min(len(drows), len(crows))
    out = []
    for j, col in enumerate(header):
        pairs = [(drows[i][j], crows[i][j]) for i in range(n) if j < len(drows[i]) and j < len(crows[i])]
        diff = [(d, c) for d, c in pairs if d != c]
        out.append({"dataset": name, "column": col, "rows": n, "cells_changed": len(diff),
                    "share_changed": round(len(diff) / n, 4) if n else 0, "has_errors": bool(diff),
                    "examples": json.dumps([list(p) for p in diff[:3]], ensure_ascii=False)})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--all", action="store_true", help="also download the large tax table")
    ap.add_argument("--out", default=str(HERE / "data"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    labels = []
    for name in DEFAULT + (["tax"] if a.all else []):
        texts = {}
        for kind in ("dirty", "clean"):
            path = out / f"{name}_{kind}.csv"
            if not path.exists():
                req = urllib.request.Request(BASE.format(name=name, kind=kind), headers={"User-Agent": "readiness-testset"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    path.write_bytes(r.read())
            texts[kind] = path.read_text(encoding="utf-8", errors="replace")
        dirty, clean = read_csv(texts["dirty"]), read_csv(texts["clean"])
        cols = compare(name, dirty, clean)
        labels += cols
        print(f"{name:10} {len(dirty) - 1:>7,} rows  {len(cols):>3} columns  {sum(c['has_errors'] for c in cols):>3} with errors  "
              f"{sum(c['cells_changed'] for c in cols):>7,} cells differ")
    with (out / "labels.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LABEL_FIELDS)
        w.writeheader()
        w.writerows(labels)
    print("labels:", out / "labels.csv")


if __name__ == "__main__":
    main()
