"""Whole-table cases: failures that belong to the file, not to one column.

Each case builds a file two ways: `raw`, the rows as they arrive (rows may have
different lengths), and `clean`, a header row followed by tidy rows. FIXABLE
cases come with a reference fixer that turns raw into clean; the tests run it.

    python tables.py --variations 12 --out data
"""
import argparse
import csv
import datetime as dt
import random
from collections import Counter
from pathlib import Path

from cases import DOMAINS, FIRST, FIXABLE, GARBAGE, LAST, NEEDS_CONTEXT, READY

TABLE_CASES = {}
HEADER = ["record_id", "contact_name", "created_date", "amount_usd", "channel", "address"]
STREETS = ["Main St", "Oak Ave", "Mill Rd", "Lake Dr", "Hill Ln", "Park Way"]
LABEL_FIELDS = ["table", "case", "verdict", "issue", "fix", "raw_rows", "clean_rows", "focus_row", "domain", "variation"]


def tcase(cid, verdict, issue, fix_id="", fix=None):
    def register(make):
        TABLE_CASES[cid] = {"id": cid, "verdict": verdict, "issue": issue, "fix": fix_id, "make": make, "fixer": fix}
        return make
    return register


def base(rng, dom, n=60):
    """A tidy table: header plus n rows, every value a string."""
    rows = []
    for i in rng.sample(range(90000), n):
        d = dt.date(2025, 1, 1) + dt.timedelta(days=rng.randrange(600))
        rows.append([f"{dom['prefix']}-{10000 + i}", rng.choice(FIRST) + " " + rng.choice(LAST), d.isoformat(),
                     f"{rng.uniform(5, 900):.2f}", rng.choice(dom["categories"]), f"{rng.randint(1, 999)} {rng.choice(STREETS)}"])
    return [list(HEADER)] + rows


# ---------- reference fixers ----------

def fix_duplicates(raw):
    seen, out = set(), []
    for r in raw:
        if tuple(r) not in seen:
            seen.add(tuple(r))
            out.append(r)
    return out


def fix_preamble(raw):
    width = Counter(len(r) for r in raw).most_common(1)[0][0]
    start = next(i for i, r in enumerate(raw) if len(r) == width)
    return raw[start:]


def fix_repeated_header(raw):
    return [raw[0]] + [r for r in raw[1:] if r != raw[0]]


def fix_total_rows(raw):
    return [r for r in raw if not r[0].strip().lower().startswith(("total", "grand total", "subtotal"))]


def fix_empty(raw):
    rows = [r for r in raw if any(c.strip() for c in r)]
    keep = [j for j in range(len(rows[0])) if any(r[j].strip() for r in rows)]
    return [[r[j] for j in keep] for r in rows]


def fix_split_field(raw):
    width = len(raw[0])
    at = raw[0].index("address")
    return [r if len(r) == width else r[:at] + [r[at] + "," + r[at + 1]] + r[at + 2:] for r in raw]


def fix_wide(raw):
    months = raw[0][1:]
    return [["record_id", "month", "amount_usd"]] + [[r[0], m, v] for r in raw[1:] for m, v in zip(months, r[1:])]


# ---------- cases ----------

@tcase("t_tidy", READY, "A tidy table with one header row.")
def _(rng, dom):
    t = base(rng, dom)
    return {"raw": [list(r) for r in t], "clean": t, "focus": 1}


@tcase("t_duplicate_rows", FIXABLE, "Some rows appear twice, exactly.", "drop_duplicate_rows", fix_duplicates)
def _(rng, dom):
    t = base(rng, dom)
    raw = [list(r) for r in t]
    first = None
    for _ in range(6):
        src = rng.randrange(1, len(raw))
        raw.insert(src + 1, list(raw[src]))
        first = src if first is None else min(first, src)
    return {"raw": raw, "clean": t, "focus": first}


@tcase("t_header_not_first_row", FIXABLE, "Title lines sit above the header row.", "skip_preamble", fix_preamble)
def _(rng, dom):
    t = base(rng, dom)
    pre = [[f"{dom['entity'].title()} export"], [f"Generated {dt.date(2026, 11, 1) + dt.timedelta(days=rng.randrange(10))}"], []]
    return {"raw": pre + [list(r) for r in t], "clean": t, "focus": 0}


@tcase("t_repeated_header_rows", FIXABLE, "The header row repeats part-way down the file.", "drop_repeated_headers", fix_repeated_header)
def _(rng, dom):
    t = base(rng, dom)
    raw = [list(r) for r in t]
    for at in (41, 21):
        raw.insert(at, list(HEADER))
    return {"raw": raw, "clean": t, "focus": 19}


@tcase("t_total_rows", FIXABLE, "Subtotal and total rows are mixed in with the data rows.", "drop_total_rows", fix_total_rows)
def _(rng, dom):
    t = base(rng, dom)
    raw = [list(r) for r in t]
    total = sum(float(r[3]) for r in t[1:])
    raw.insert(31, ["Subtotal", "", "", f"{sum(float(r[3]) for r in t[1:31]):.2f}", "", ""])
    raw.append(["Total", "", "", f"{total:.2f}", "", ""])
    return {"raw": raw, "clean": t, "focus": 29}


@tcase("t_empty_rows_and_columns", FIXABLE, "Blank rows and a blank column are scattered through the file.", "drop_empty_rows_columns", fix_empty)
def _(rng, dom):
    t = base(rng, dom)
    raw = [r[:3] + [""] + r[3:] for r in t]
    for at in sorted(rng.sample(range(2, len(raw)), 6), reverse=True):
        raw.insert(at, [""] * 7)
    return {"raw": raw, "clean": t, "focus": 1}


@tcase("t_split_field_shift", FIXABLE, "An unquoted comma inside an address pushes the rest of some rows one column to the right.", "rejoin_split_field", fix_split_field)
def _(rng, dom):
    t = base(rng, dom)
    clean = [list(r) for r in t]
    hit = sorted(rng.sample(range(1, len(clean)), 6))
    for i in hit:
        clean[i][5] = clean[i][5] + f", Apt {rng.randint(1, 40)}"
    raw = [list(r) for r in clean]
    for i in hit:
        a, b = raw[i][5].split(",", 1)
        raw[i] = raw[i][:5] + [a, b]
    return {"raw": raw, "clean": clean, "focus": hit[0] - 1}


@tcase("t_wide_months", FIXABLE, "Months are spread across columns, one column per month, where they should be rows.", "reshape_wide_to_long", fix_wide)
def _(rng, dom):
    months = [f"2026-{m:02d}" for m in range(1, 7)]
    ids = [f"{dom['prefix']}-{10000 + i}" for i in rng.sample(range(90000), 30)]
    raw = [["record_id"] + months] + [[i] + [f"{rng.uniform(5, 900):.2f}" for _ in months] for i in ids]
    return {"raw": raw, "clean": fix_wide(raw), "focus": 1, "independent": [[r[0], m, r[1 + k]] for r in raw[1:] for k, m in enumerate(months)]}


@tcase("t_header_missing", NEEDS_CONTEXT, "There is no header row, and the columns are numbers that could mean many things.")
def _(rng, dom):
    rows = [[f"{dom['prefix']}-{10000 + i}", str(rng.randint(1, 6)), f"{rng.uniform(5, 900):.2f}", str(rng.choice([1, 2])), str(rng.randint(58, 76))]
            for i in rng.sample(range(90000), 60)]
    return {"raw": rows, "clean": [list(r) for r in rows], "focus": 0}


@tcase("t_not_a_table", GARBAGE, "The file is a saved error page, not data.")
def _(rng, dom):
    raw = [["<!DOCTYPE html>"], ["<html><head><title>503 Service Unavailable</title></head>"], ["<body><h1>Service Unavailable</h1>"],
           [f"<p>Request id {rng.randrange(10 ** 8)}. Please try again later.</p>"], ["</body></html>"]]
    return {"raw": raw, "clean": [list(r) for r in raw], "focus": 0}


# ---------- build ----------

def build(variations=12, seed=20261112):
    """Returns ({name: {"raw": rows, "clean": rows}}, labels)."""
    files, labels = {}, []
    domains = list(DOMAINS)
    for var in range(variations):
        for k, (cid, c) in enumerate(TABLE_CASES.items()):
            dom_name = domains[(var + k) % len(domains)]
            t = c["make"](random.Random(f"{seed}|table|{var}|{cid}"), DOMAINS[dom_name])
            name = f"file_{dom_name}_v{var:02d}_{k:02d}"
            files[name] = t
            labels.append({"table": name, "case": cid, "verdict": c["verdict"], "issue": c["issue"], "fix": c["fix"],
                           "raw_rows": len(t["raw"]), "clean_rows": len(t["clean"]), "focus_row": t["focus"], "domain": dom_name, "variation": var})
    return files, labels


def write(out, variations=12):
    out = Path(out)
    files, labels = build(variations)
    for kind, folder in (("raw", "files_raw"), ("clean", "files_clean")):
        (out / folder).mkdir(parents=True, exist_ok=True)
        for old in (out / folder).glob("*.csv"):
            old.unlink()
        for name, t in files.items():
            with (out / folder / (name + ".csv")).open("w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerows(t[kind])
    with (out / "file_labels.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LABEL_FIELDS)
        w.writeheader()
        w.writerows(labels)
    return {"files": len(files), "file_cases": len(TABLE_CASES), "by_verdict": dict(Counter(l["verdict"] for l in labels))}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--variations", type=int, default=12)
    ap.add_argument("--out", default=str(Path(__file__).parent / "data"))
    a = ap.parse_args()
    print(write(a.out, a.variations))
