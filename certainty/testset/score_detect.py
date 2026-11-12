"""Turn the detector's attempts.jsonl into report.md.

    python score_detect.py runs/<model>
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

from report import auroc, bootstrap, brier, calibration_error, mean, num, pct  # noqa: E402

VERDICTS = ["READY", "FIXABLE", "NEEDS_CONTEXT", "GARBAGE"]
HIGH = 80


def share(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return sum(bool(v) for v in vals) / len(vals) if vals else None


def headline(rows):
    ok = [r for r in rows if r["status"] == "ok"]
    unusable = [r for r in rows if r["truth"] in ("NEEDS_CONTEXT", "GARBAGE")]
    usable = [r for r in rows if r["truth"] in ("READY", "FIXABLE")]
    by_col = defaultdict(list)
    for r in rows:
        by_col[(r["table"], r["column"])].append(r)
    acc = lambda groups: (sum(r["correct"] for g in groups for r in g) / sum(len(g) for g in groups)) if groups else None
    agree = [Counter(r["said"] for r in g).most_common(1)[0][1] / len(g) for g in by_col.values()]
    return {
        "attempts": len(rows),
        "verdict_right": sum(r["correct"] for r in rows) / len(rows) if rows else None,
        "verdict_right_ci": bootstrap(by_col, acc),
        "dangerous": share([r for r in unusable if r["status"] == "ok"], "dangerous"),
        "dangerous_and_confident": (sum(bool(r.get("dangerous")) and (r["confidence"] or 0) >= HIGH for r in unusable) / len(unusable)) if unusable else None,
        "over_cautious": share([r for r in usable if r["status"] == "ok"], "over_cautious"),
        "fix_named": share(rows, "fix_right"),
        "fix_carried_out": share([r for r in rows if r["truth"] == "FIXABLE"], "cleaned_right"),
        "confidence": (mean([r["confidence"] for r in ok]) or 0) / 100 if ok else None,
        "auroc": auroc([r["confidence"] for r in ok], [r["correct"] for r in ok]),
        "calibration_error": calibration_error([r["confidence"] for r in ok], [r["correct"] for r in ok]),
        "brier": brier([r["confidence"] for r in ok], [r["correct"] for r in ok]),
        "agreement": mean(agree),
        "bad_reply": sum(r["status"] != "ok" for r in rows) / len(rows) if rows else None,
    }


def write(folder):
    folder = Path(folder)
    rows = [json.loads(l) for l in (folder / "attempts.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    dry = any(r.get("dry_run") for r in rows)
    model = rows[0]["model"] if rows else ""
    h = headline(rows)
    L = ["# Garbage detector test: " + model, ""]
    if dry:
        L += ["**DRY RUN. The replies were made up by the script to test the pipeline. Nothing below is a finding.**", ""]
    cols = len({(r["table"], r["column"]) for r in rows})
    L += [f"{cols} columns, {len({r['case'] for r in rows})} kinds of case, {max(r['rep'] for r in rows) + 1} repeats, {len(rows)} attempts. "
          f"{rows[0].get('rows_shown', '')} sample rows shown.", ""]

    ci = h["verdict_right_ci"]
    L += ["## Headline", "", "| Measure | Value |", "| --- | ---: |",
          f"| Verdict right | {pct(h['verdict_right'])}" + (f" (95% interval {100 * ci[0]:.0f}–{100 * ci[1]:.0f}%)" if ci else "") + " |",
          f"| **Dangerous**: called usable when it needs context or is garbage | {pct(h['dangerous'])} |",
          f"| Dangerous and stated certainty of {HIGH} or more | {pct(h['dangerous_and_confident'])} |",
          f"| Over-cautious: held back a column that is ready or fixable | {pct(h['over_cautious'])} |",
          f"| Fixable columns where the right fix was named | {pct(h['fix_named'])} |",
          f"| Fixable columns where the cleaned values matched the answer key | {pct(h['fix_carried_out'])} |",
          f"| Mean stated certainty | {pct(h['confidence'])} |",
          f"| Certainty separates right from wrong (0.5 = coin, 1.0 = perfect) | {num(h['auroc'])} |",
          f"| Calibration error | {num(h['calibration_error'])} |",
          f"| Repeats agree | {pct(h['agreement'])} |",
          f"| Replies that could not be read | {pct(h['bad_reply'])} |", "",
          "**Dangerous** is the failure that matters most: an analysis agent would run on this column and report a result. "
          "The share is of columns whose true verdict is NEEDS_CONTEXT or GARBAGE.", ""]

    L += ["## What it said, against the truth", "", "Rows are the true verdict. Columns are what the model said.", "",
          "| True verdict | " + " | ".join(VERDICTS) + " | Unreadable | Attempts |", "| --- |" + " ---: |" * (len(VERDICTS) + 2)]
    for t in VERDICTS:
        rs = [r for r in rows if r["truth"] == t]
        if not rs:
            continue
        c = Counter(r["said"] for r in rs)
        L.append(f"| {t} | " + " | ".join(pct(c[v] / len(rs)) for v in VERDICTS) + f" | {pct(c['BAD_REPLY'] / len(rs))} | {len(rs)} |")
    L.append("")

    need = [r for r in rows if r["truth"] == "NEEDS_CONTEXT" and r["status"] == "ok"]
    if need:
        two = [r for r in need if r.get("two_readings")]
        L += ["## Columns that need context", "",
              "| Measure | Value |", "| --- | ---: |",
              f"| Recognised as needing context | {pct(share(need, 'correct'))} |",
              f"| Called usable | {pct(share(need, 'dangerous'))} |",
              f"| Mean stated certainty when called usable | {num(mean([r['confidence'] for r in need if r.get('dangerous')]), 0)} |",
              f"| Stated its assumption when called usable | {pct(share([r for r in need if r.get('dangerous')], 'stated_assumption'))} |",
              f"| Of the two-reading columns it tried to clean, share that matched the true reading | {pct(share(two, 'guessed_right'))} |", "",
              "On a two-reading column a guess is right about half the time by construction. A share near 50% on the last line means the model was guessing.", ""]

    L += ["## By kind of case", "",
          "| Case | True verdict | Verdict right | Most common answer | Mean certainty | Cleaned values right |",
          "| --- | --- | ---: | --- | ---: | ---: |"]
    for case in sorted({r["case"] for r in rows}, key=lambda c: (VERDICTS.index(next(r["truth"] for r in rows if r["case"] == c)), c)):
        rs = [r for r in rows if r["case"] == case]
        said, n = Counter(r["said"] for r in rs).most_common(1)[0]
        L.append(f"| {case} | {rs[0]['truth']} | {pct(share(rs, 'correct'))} | {said} ({pct(n / len(rs))}) | "
                 f"{num(mean([r['confidence'] for r in rs]), 0)} | {pct(share(rs, 'cleaned_right'))} |")
    L.append("")

    assumed = Counter(r["assumed"].strip() for r in rows if r.get("assumed", "").strip() and r.get("dangerous"))
    if assumed and not dry:
        L += ["## Assumptions behind the dangerous answers (most common)", ""]
        L += [f"- {n}x: {text}" for text, n in assumed.most_common(15)]
        L.append("")

    path = folder / "report.md"
    path.write_text("\n".join(L), encoding="utf-8")
    return path


if __name__ == "__main__":
    print(write(sys.argv[1]))
