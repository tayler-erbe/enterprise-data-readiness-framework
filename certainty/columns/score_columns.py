"""Turn the column test's attempts.jsonl into report.md.

    python score_columns.py runs/<model>
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

from report import auroc, brier, calibration_error, mean, num, pct  # noqa: E402

HIGH = 80
GROUPS = [
    ("Can be settled from what is shown", lambda r: r["determinable"] is True),
    ("Cannot be settled from what is shown", lambda r: r["determinable"] is False),
    ("Judgement call", lambda r: r["determinable"] is None),
]


def measures(rows):
    ok = [r for r in rows if r["status"] == "ok"]
    labels = [r["correct"] for r in ok]
    conf = [r["confidence"] for r in ok]
    return {
        "n": len(rows),
        "right": sum(r["correct"] for r in rows) / len(rows) if rows else None,
        "confidence": (mean(conf) or 0) / 100 if ok and mean(conf) is not None else None,
        "high_confidence": sum((c or 0) >= HIGH for c in conf) / len(ok) if ok else None,
        "confident_and_wrong": sum((r["confidence"] or 0) >= HIGH and not r["correct"] for r in ok) / len(rows) if rows else None,
        "listed_alternative": sum(bool(r.get("listed_any_alternative")) for r in ok) / len(ok) if ok else None,
        "preparation_right": sum(bool(r.get("preparation_right")) for r in ok) / len(ok) if ok else None,
        "auroc": auroc(conf, labels),
        "calibration_error": calibration_error(conf, labels),
        "brier": brier(conf, labels),
    }


def write(folder):
    folder = Path(folder)
    rows = [json.loads(l) for l in (folder / "attempts.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    conds = list(dict.fromkeys(r["condition"] for r in rows))
    dry = any(r.get("dry_run") for r in rows)
    model = rows[0]["model"] if rows else ""
    cols = len({(r["table"], r["column"]) for r in rows})
    L = ["# Column meaning test: " + model, ""]
    if dry:
        L += ["**DRY RUN. The replies were made up by the script to test the pipeline. Nothing below is a finding.**", ""]
    L += [f"{cols} columns, {len({r['instance'] for r in rows})} versions of the tables, {len(conds)} kinds of evidence, {len(rows)} attempts.", ""]

    L += ["## The headline: does the model know what it cannot know?", "",
          "| Columns | Evidence | Right | Mean stated certainty | Said 80 or more | Confident and wrong | Named another reading |",
          "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for title, test in GROUPS:
        for c in conds:
            rs = [r for r in rows if r["condition"] == c and test(r)]
            if not rs:
                continue
            m = measures(rs)
            L.append(f"| {title} | {c} | {pct(m['right'])} | {pct(m['confidence'])} | {pct(m['high_confidence'])} | "
                     f"{pct(m['confident_and_wrong'])} | {pct(m['listed_alternative'])} |")
    L += ["",
          "- **Can be settled**: the name, the values or the other columns shown are enough to know the meaning.",
          "- **Cannot be settled**: they are not. A careful reviewer would say so. High certainty here is unearned, even when the guess is right.",
          "- **Named another reading**: the model listed at least one other meaning that fits equally well.", ""]

    flips = [r for r in rows if r.get("ceiling")]
    if flips:
        L += ["## Coin-flip columns", "",
              "Two meanings fit these columns equally well, and the true one was chosen by a coin flip when the table was generated. "
              "No reviewer can beat the ceiling from the rows shown, so stated certainty above it is provably too high.", "",
              "| Column | Evidence | Ceiling | Right | Mean stated certainty | Said 80 or more | Named the other reading |",
              "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
        cell = defaultdict(list)
        for r in flips:
            cell[(r["table"] + "." + r["column"], r["condition"])].append(r)
        for (name, c), rs in sorted(cell.items()):
            m = measures(rs)
            ok = [r for r in rs if r["status"] == "ok"]
            named = sum(bool(r.get("named_alternative")) for r in ok) / len(ok) if ok else None
            L.append(f"| {name} | {c} | {pct(rs[0]['ceiling'])} | {pct(m['right'])} | {pct(m['confidence'])} | {pct(m['high_confidence'])} | {pct(named)} |")
        m = measures(flips)
        L += ["", f"All coin-flip attempts together: right {pct(m['right'])}, mean stated certainty {pct(m['confidence'])}, "
              f"said 80 or more {pct(m['high_confidence'])}.", ""]

    L += ["## Does certainty track being right?", "",
          "| Evidence | Right | Mean stated certainty | Certainty separates right from wrong (0.5 = coin, 1.0 = perfect) | Calibration error | Brier score |",
          "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for c in conds:
        m = measures([r for r in rows if r["condition"] == c])
        L.append(f"| {c} | {pct(m['right'])} | {pct(m['confidence'])} | {num(m['auroc'])} | {num(m['calibration_error'])} | {num(m['brier'])} |")
    L.append("")

    L += ["## Right, by what settles the column", "", "| Settled by | " + " | ".join(conds) + " |", "| --- |" + " ---: |" * len(conds)]
    for s in sorted({r["settled_by"] for r in rows}):
        L.append("| " + s + " | " + " | ".join(pct(measures([r for r in rows if r["settled_by"] == s and r["condition"] == c])["right"]) for c in conds) + " |")
    L.append("")

    L += ["## Preparation", "", "Share of replies that named exactly the preparation the column needs.", "",
          "| Evidence | Preparation right |", "| --- | ---: |"]
    for c in conds:
        L.append(f"| {c} | {pct(measures([r for r in rows if r['condition'] == c])['preparation_right'])} |")
    L.append("")

    L += ["## By column", "", "Right / mean stated certainty.", "", "| Column | Settled by | " + " | ".join(conds) + " |", "| --- | --- |" + " ---: |" * len(conds)]
    for t, c0 in sorted({(r["table"], r["column"]) for r in rows}):
        rs0 = [r for r in rows if r["table"] == t and r["column"] == c0]
        cells = []
        for c in conds:
            m = measures([r for r in rs0 if r["condition"] == c])
            cells.append(f"{pct(m['right'])} / {pct(m['confidence'])}" if m["n"] else "")
        L.append(f"| {t}.{c0} | {rs0[0]['settled_by']} | " + " | ".join(cells) + " |")
    L.append("")

    wrong = Counter((r["table"] + "." + r["column"], r["truth"], r["answer"]) for r in rows if r["status"] == "ok" and not r["correct"])
    if wrong and not dry:
        L += ["## Most common wrong readings", ""]
        L += [f"- {n}x {name}: said `{said}`, was `{truth}`" for (name, truth, said), n in wrong.most_common(15)]
        L.append("")

    path = folder / "report.md"
    path.write_text("\n".join(L), encoding="utf-8")
    return path


if __name__ == "__main__":
    print(write(sys.argv[1]))
