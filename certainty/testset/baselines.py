"""Score three no-AI baselines on the test set, with the same measures as detect.py.

    python baselines.py            # writes baselines_report.md

These need no model and no GPU, so the numbers are real results, not dry runs.

    accept_all   Calls every column READY. This is the verdict implied by a check
                 that only confirms a copy matches its source, or by a tool that
                 writes a description for every column and never says "can't tell".
    rules        Generic quality rules of the kind found in every data quality
                 tool: share blank, one value only, words standing in for missing,
                 stray spaces, values of the wrong type, extreme numbers. It reads
                 the WHOLE column (120 rows), which is more than the model sees.
                 It can say READY, FIXABLE or GARBAGE, never NEEDS_CONTEXT.
    profiler     The rules, plus shape profiling of the whole column: several
                 date formats, slash dates (settled or not by a day above 12),
                 numbers written with symbols or separators, one category
                 written several ways. It can say NEEDS_CONTEXT in the one
                 case the values themselves reveal: slash dates with no day
                 above 12. It looks at one column at a time and never at names,
                 so it can't see that a currency or unit was never stated, and
                 it can't see a conflict between two columns.

The rules and the profiler are my own plain implementation. They are NOT any vendor's product,
and a vendor's product may do better or worse. They are here as a floor: what a
value-only check can and can't see on this test set.
"""
import csv
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
VERDICTS = ["READY", "FIXABLE", "NEEDS_CONTEXT", "GARBAGE"]
NULL_WORDS = {"n/a", "na", "null", "none", "nan", "missing", "unknown", "-", "--", "?", "nil", "#n/a"}
NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?$")


def kind(v):
    if NUMBER.match(v):
        return "number"
    if ISO_DATE.match(v):
        return "date"
    return "text"


def rules_verdict(values):
    """One verdict from generic value rules, reading the whole column."""
    n = len(values)
    filled = [v for v in values if v.strip() != ""]
    if n == 0 or len(filled) / n <= 0.2:
        return "GARBAGE", "mostly blank"
    if len(set(filled)) == 1:
        return "GARBAGE", "one value in every row"
    if any(v.strip().lower() in NULL_WORDS for v in filled):
        return "FIXABLE", "words standing in for missing"
    if any(v != v.strip() for v in filled):
        return "FIXABLE", "stray spaces"
    kinds = Counter(kind(v) for v in filled)
    top, top_n = kinds.most_common(1)[0]
    if top != "text" and top_n < len(filled):
        return "FIXABLE", "values of the wrong type"
    if top == "number":
        nums = [float(v) for v in filled]
        med = statistics.median(nums)
        mad = statistics.median(abs(x - med) for x in nums)
        if mad > 0 and any(abs(x - med) / mad > 25 for x in nums):
            return "FIXABLE", "extreme numbers"
    return "READY", ""


SLASH_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$")
DATE_SHAPES = [("iso", ISO_DATE), ("slash", SLASH_DATE), ("dash_dmy", re.compile(r"^\d{1,2}-\d{1,2}-\d{4}$")),
               ("month_name", re.compile(r"^(\d{1,2} [A-Za-z]{3,9} \d{4}|[A-Za-z]{3,9} \d{1,2},? \d{4})$")),
               ("compact", re.compile(r"^(19|20)\d{6}$"))]
DRESSED_NUMBER = re.compile(r"^[\s$€£]*-?\(?\d{1,3}([,.\s]\d{3})*([.,]\d+)?\)?\s*%?$")


def profiler_verdict(values):
    """A stronger value-only check: the rules above, plus shape profiling of the whole column."""
    said, why = rules_verdict(values)
    if said != "READY":
        return said, why
    filled = [v for v in values if v.strip() != ""]
    shapes = Counter(next((name for name, rx in DATE_SHAPES if rx.match(v)), None) for v in filled)
    dated = sum(k for s, k in shapes.items() if s)
    if dated >= 0.9 * len(filled):
        if len([s for s in shapes if s]) > 1:
            return "FIXABLE", "several date formats"
        if shapes.get("slash"):
            parts = [SLASH_DATE.match(v) for v in filled]
            firsts = [int(m.group(1)) for m in parts if m]
            seconds = [int(m.group(2)) for m in parts if m]
            if max(firsts) > 12 or max(seconds) > 12:
                return "FIXABLE", "slash dates, order settled by a day above 12"
            return "NEEDS_CONTEXT", "slash dates, day and month can't be told apart"
    plain = sum(bool(NUMBER.match(v)) for v in filled)
    dressed = sum(bool(DRESSED_NUMBER.match(v)) for v in filled)
    if dressed >= 0.9 * len(filled) and plain < dressed:
        return "FIXABLE", "numbers written with symbols or separators"
    folded = defaultdict(set)
    for v in filled:
        folded[re.sub(r"[\s._-]+", "", v).lower()].add(v)
    if len(folded) <= 30 and any(len(s) > 1 for s in folded.values()):
        return "FIXABLE", "one category written several ways"
    return "READY", ""


def accept_all(values):
    return "READY", ""


BASELINES = {"accept_all": accept_all, "rules": rules_verdict, "profiler": profiler_verdict}


def load(data=HERE / "data"):
    labels = list(csv.DictReader((data / "labels.csv").open(encoding="utf-8", newline="")))
    tables = {}
    for name in sorted({l["table"] for l in labels}):
        rows = list(csv.reader((data / "raw" / (name + ".csv")).open(encoding="utf-8", newline="")))
        tables[name] = {"header": rows[0], "rows": rows[1:]}
    return tables, labels


def run(tables, labels):
    """{baseline: [ {case, truth, said, why} ]}"""
    out = defaultdict(list)
    for l in labels:
        t = tables[l["table"]]
        i = t["header"].index(l["column"])
        values = [r[i] for r in t["rows"]]
        for name, fn in BASELINES.items():
            said, why = fn(values)
            out[name].append({"case": l["case"], "truth": l["verdict"], "said": said, "why": why})
    return out


def usable(v):
    return v in ("READY", "FIXABLE")


def measures(recs):
    n = len(recs)
    unsafe = [r for r in recs if not usable(r["truth"])]
    safe = [r for r in recs if usable(r["truth"])]
    need = [r for r in recs if r["truth"] == "NEEDS_CONTEXT"]
    return {
        "columns": n,
        "verdict_right": sum(r["said"] == r["truth"] for r in recs) / n,
        "dangerous": sum(usable(r["said"]) for r in unsafe) / len(unsafe),
        "needs_context_passed_as_usable": sum(usable(r["said"]) for r in need) / len(need),
        "over_cautious": sum(not usable(r["said"]) for r in safe) / len(safe),
    }


def pct(x):
    return f"{100 * x:.0f}%"


def report(results):
    L = ["# No-AI baselines on the test set", "",
         "Real results. No model was used. Run `python baselines.py` to reproduce.", "",
         "`accept_all` calls every column READY. `rules` applies generic quality rules to the whole column. "
         "`profiler` adds shape profiling (date formats, dressed-up numbers, category variants). "
         "Both are plain implementations written for this test, not any vendor's product.", "",
         "| Measure | accept_all | rules | profiler |", "| --- | ---: | ---: | ---: |"]
    m = {k: measures(v) for k, v in results.items()}
    rows = [("Verdict right", "verdict_right"),
            ("Dangerous: needs-context or garbage columns passed as usable", "dangerous"),
            ("Needs-context columns passed as usable", "needs_context_passed_as_usable"),
            ("Over-cautious: usable columns held back", "over_cautious")]
    for title, key in rows:
        L.append(f"| {title} | {pct(m['accept_all'][key])} | {pct(m['rules'][key])} | {pct(m['profiler'][key])} |")
    L += ["", f"Columns: {m['rules']['columns']}.", "", "## What the profiler said, against the truth", "",
          "| Truth | Columns | " + " | ".join("said " + v for v in VERDICTS) + " |", "| --- | ---: | " + " | ".join("---:" for _ in VERDICTS) + " |"]
    for truth in VERDICTS:
        recs = [r for r in results["profiler"] if r["truth"] == truth]
        c = Counter(r["said"] for r in recs)
        L.append(f"| {truth} | {len(recs)} | " + " | ".join(str(c.get(v, 0)) for v in VERDICTS) + " |")
    L += ["", "## Profiler, by kind of case", "", "| Case | Truth | Columns | Verdict right | Most common answer |", "| --- | --- | ---: | ---: | --- |"]
    by = defaultdict(list)
    for r in results["profiler"]:
        by[r["case"]].append(r)
    for case in sorted(by, key=lambda c: (VERDICTS.index(by[c][0]["truth"]), c)):
        recs = by[case]
        said, k = Counter(r["said"] for r in recs).most_common(1)[0]
        L.append(f"| {case} | {recs[0]['truth']} | {len(recs)} | {pct(sum(r['said'] == r['truth'] for r in recs) / len(recs))} | {said} ({k}) |")
    L += ["", "## How to read this", "",
          "- `accept_all` is right only on the READY columns, and passes every unsafe column. That is the floor.",
          "- `profiler` catches the needs-context case that values alone reveal (slash dates with no day above 12). "
          "It passes the rest, because they turn on something the values do not contain: an unstated currency, unit or pay period, "
          "what a code stands for, or a conflict with another column. A check that compared columns would catch the conflicts; this one does not.",
          "- Most needs-context cases here were built so that the raw values are identical under each reading. "
          "A value-only check scoring 0% on those is true by construction. It shows what kind of evidence is needed, not that the checks are badly made.",
          "- Both read all 120 rows. A model in `detect.py` sees ten. The comparison favours them on anything a full column reveals.",
          "- These are generated tables with one problem per column. Real columns are messier, and real tools have more rules than these.",
          "- A fair reading: these baselines are the floor a model has to beat, and a model that beats them on verdicts but passes "
          "needs-context columns as usable has not solved the problem either."]
    return "\n".join(L) + "\n"


def main():
    tables, labels = load()
    results = run(tables, labels)
    path = HERE / "baselines_report.md"
    path.write_text(report(results), encoding="utf-8")
    for name, recs in results.items():
        print(name, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in measures(recs).items()})
    print("report:", path)


if __name__ == "__main__":
    main()
