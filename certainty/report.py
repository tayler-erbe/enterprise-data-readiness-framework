"""Turn attempts.jsonl into report.md and summary.csv.

    python report.py runs/<model>                 # one model
    python report.py runs/<model-a> runs/<model-b>  # also writes runs/compare.md
"""
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

HIGH = 80        # stated confidence at or above this counts as "confident"
BINS = 5         # bins for calibration error; stated confidence clusters, so few bins
RESAMPLES = 2000  # bootstrap resamples, drawn over questions
CONF_BANDS = [(0, 49), (50, 69), (70, 79), (80, 89), (90, 100)]


def pct(x):
    return "" if x is None else f"{100 * x:.0f}%"


def num(x, places=2):
    return "" if x is None else f"{x:.{places}f}"


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def auroc(scores, labels):
    """Chance that a right answer has a higher score than a wrong one. 0.5 means the score tells you nothing."""
    pairs = [(s, l) for s, l in zip(scores, labels) if s is not None]
    pos = [s for s, l in pairs if l]
    neg = [s for s, l in pairs if not l]
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def calibration_error(conf, labels, bins=BINS):
    """Expected calibration error: the gap between stated confidence and share right, averaged over bins."""
    pairs = [(c / 100, l) for c, l in zip(conf, labels) if c is not None]
    if not pairs:
        return None
    total = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        inside = [(c, l) for c, l in pairs if (lo <= c < hi) or (b == bins - 1 and c == 1.0)]
        if inside:
            total += len(inside) / len(pairs) * abs(mean([c for c, _ in inside]) - mean([float(l) for _, l in inside]))
    return total


def brier(conf, labels):
    pairs = [(c / 100, l) for c, l in zip(conf, labels) if c is not None]
    return mean([(c - float(l)) ** 2 for c, l in pairs]) if pairs else None


def bootstrap(by_question, stat, seed=0):
    """95% interval for stat, resampling whole questions so repeats of one question stay together."""
    qs = sorted(by_question)
    if len(qs) < 2:
        return None
    rng = random.Random(seed)
    vals = []
    for _ in range(RESAMPLES):
        v = stat([by_question[q] for q in (rng.choice(qs) for _ in qs)])
        if v is not None:
            vals.append(v)
    if not vals:
        return None
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[min(len(vals) - 1, int(0.975 * len(vals)))]


def share_right(groups):
    rows = [r for g in groups for r in g]
    return sum(r["status"] == "correct" for r in rows) / len(rows) if rows else None


def add_agreement(rows):
    """Give each attempt the share of the other repeats that returned the same answer."""
    cells = defaultdict(list)
    for r in rows:
        cells[(r["context"], r["question"])].append(r)
    for rs in cells.values():
        counts = Counter(r["answer"] for r in rs)
        for r in rs:
            r["agree"] = (counts[r["answer"]] - 1) / (len(rs) - 1) if len(rs) > 1 else None


def summarise(rows):
    """Measures for one context, on the questions that have an answer."""
    n = len(rows)
    answered = [r for r in rows if r["status"] in ("correct", "wrong", "sql_error")]
    right = [r for r in rows if r["status"] == "correct"]
    labels = [r["status"] == "correct" for r in answered]
    acc_answered = len(right) / len(answered) if answered else None
    conf = mean([r["confidence"] for r in answered])
    by_q = defaultdict(list)
    for r in rows:
        by_q[r["question"]].append(r)
    agree, same_and_wrong = [], 0
    for rs in by_q.values():
        _, count = Counter(r["answer"] for r in rs).most_common(1)[0]
        agree.append(count / len(rs))
        if len(rs) > 1 and count == len(rs) and rs[0]["status"] in ("wrong", "sql_error"):
            same_and_wrong += 1
    wrong = sum(r["status"] in ("wrong", "sql_error") for r in rows)
    return {
        "attempts": n,
        "accuracy": len(right) / n if n else None,
        "accuracy_ci": bootstrap(by_q, share_right),
        "answered": len(answered) / n if n else None,
        "accuracy_when_answered": acc_answered,
        "abstained": sum(r["status"] == "abstained" for r in rows) / n if n else None,
        "sql_error": sum(r["status"] == "sql_error" for r in rows) / n if n else None,
        "bad_reply": sum(r["status"] == "bad_reply" for r in rows) / n if n else None,
        "stated_confidence": conf / 100 if conf is not None else None,
        "overconfidence": (conf / 100 - acc_answered) if conf is not None and acc_answered is not None else None,
        "confident_and_wrong": sum(r["status"] in ("wrong", "sql_error") and (r["confidence"] or 0) >= HIGH for r in rows) / n if n else None,
        "reliability_score": (len(right) - wrong) / n if n else None,
        "calibration_error": calibration_error([r["confidence"] for r in answered], labels),
        "brier": brier([r["confidence"] for r in answered], labels),
        "auroc_stated": auroc([r["confidence"] for r in answered], labels),
        "auroc_agreement": auroc([r.get("agree") for r in answered], labels),
        "auroc_token_probability": auroc([r.get("logprob_mean") for r in answered], labels),
        "confidence_when_right": mean([r["confidence"] for r in right]),
        "confidence_when_wrong": mean([r["confidence"] for r in answered if r["status"] != "correct"]),
        "agreement": mean(agree),
        "questions_same_answer_every_time_and_wrong": same_and_wrong,
    }


def load(folder):
    rows = [json.loads(l) for l in (Path(folder) / "attempts.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    add_agreement(rows)
    return rows


def step_change(a_rows, b_rows):
    """Change in share right from one context to the next, with an interval paired on questions."""
    qa, qb = defaultdict(list), defaultdict(list)
    for r in a_rows:
        qa[r["question"]].append(r)
    for r in b_rows:
        qb[r["question"]].append(r)
    both = {q: (qa[q], qb[q]) for q in qa if q in qb}
    if not both:
        return None, None

    def diff(groups):
        a = [r for g in groups for r in g[0]]
        b = [r for g in groups for r in g[1]]
        return share_right([b]) - share_right([a]) if a and b else None

    return diff(list(both.values())), bootstrap(both, diff)


def write(folder):
    folder = Path(folder)
    rows = load(folder)
    order = list(dict.fromkeys(r["context"] for r in rows))
    main = [r for r in rows if not r.get("unanswerable")]
    controls = [r for r in rows if r.get("unanswerable")]
    by_ctx = {c: [r for r in main if r["context"] == c] for c in order}
    stats = {c: summarise(rs) for c, rs in by_ctx.items()}
    dry = any(r.get("dry_run") for r in rows)
    model = rows[0]["model"] if rows else ""

    with (folder / "summary.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        keys = [k for k in next(iter(stats.values())).keys()] if stats else []
        w.writerow(["model", "context", "kinds"] + keys)
        for c in order:
            w.writerow([model, c, "+".join(by_ctx[c][0]["kinds"]) if by_ctx[c] else ""] + [stats[c][k] for k in keys])

    L = ["# Certainty test: " + model, ""]
    if dry:
        L += ["**DRY RUN. The replies were made up by the script to test the pipeline. Nothing below is a finding.**", ""]
    reps = max((r["rep"] for r in rows), default=0) + 1
    temps = sorted({r.get("temperature") for r in rows if r.get("temperature") is not None})
    L += [f"{len(set(r['question'] for r in main))} questions with known answers and {len(set(r['question'] for r in controls))} that cannot be answered, "
          f"{reps} repeats each, {len(order)} contexts, {len(rows)} attempts. Temperature {', '.join(str(t) for t in temps) or 'not recorded'}.", ""]

    L += ["## By context", "",
          "| Context | Right | 95% interval | Stated confidence | Overconfidence | Confident and wrong | Repeats agree | Declined | SQL failed | Reliability score |",
          "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for c in order:
        s = stats[c]
        over = "" if s["overconfidence"] is None else f"{100 * s['overconfidence']:+.0f} pts"
        ci = "" if not s["accuracy_ci"] else f"{100 * s['accuracy_ci'][0]:.0f}–{100 * s['accuracy_ci'][1]:.0f}%"
        L.append(f"| {c} | {pct(s['accuracy'])} | {ci} | {pct(s['stated_confidence'])} | {over} | {pct(s['confident_and_wrong'])} | "
                 f"{pct(s['agreement'])} | {pct(s['abstained'])} | {pct(s['sql_error'])} | {num(s['reliability_score'])} |")
    L += ["",
          "- **Right**: share of all attempts that returned the known answer. A declined question counts as not right.",
          "- **95% interval**: from resampling questions, so it reflects how few questions there are.",
          "- **Overconfidence**: stated confidence minus the share right, on answered attempts. Zero is well calibrated.",
          f"- **Confident and wrong**: share of all attempts that were wrong with stated confidence of {HIGH} or more. This is the costly case.",
          "- **Repeats agree**: for each question, the share of repeats giving the most common answer, averaged. High agreement with low accuracy means the model is reliably wrong.",
          "- **Reliability score**: +1 for a right answer, 0 for declining, -1 for a wrong one, averaged. It rewards declining over guessing.",
          ""]

    L += ["## Which signal tells right from wrong?", "",
          "A value of 0.50 means the signal is no better than a coin. 1.00 means it separates right from wrong perfectly.", "",
          "| Context | Stated confidence | Agreement across repeats | Token probability | Calibration error | Brier score |",
          "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for c in order:
        s = stats[c]
        L.append(f"| {c} | {num(s['auroc_stated'])} | {num(s['auroc_agreement'])} | {num(s['auroc_token_probability'])} | {num(s['calibration_error'])} | {num(s['brier'])} |")
    L += ["", f"Calibration error uses {BINS} bins. Lower is better for calibration error and Brier score. "
          "Token probability is blank when the server did not return it.", ""]

    L += ["## How the model spreads its stated confidence", "",
          "| Context | " + " | ".join(f"{lo}–{hi}" for lo, hi in CONF_BANDS) + " |", "| --- |" + " ---: |" * len(CONF_BANDS)]
    for c in order:
        confs = [r["confidence"] for r in by_ctx[c] if r["confidence"] is not None]
        L.append("| " + c + " | " + " | ".join(str(sum(lo <= x < hi + 1 for x in confs)) for lo, hi in CONF_BANDS) + " |")
    L.append("")

    L += ["## Does the model know when it is wrong?", "",
          "| Context | Mean confidence when right | Mean confidence when wrong | Questions answered the same every time, and wrong |",
          "| --- | ---: | ---: | ---: |"]
    for c in order:
        s = stats[c]
        L.append(f"| {c} | {num(s['confidence_when_right'], 0)} | {num(s['confidence_when_wrong'], 0)} | {s['questions_same_answer_every_time_and_wrong']} |")
    L.append("")

    ladder = [c for c in order if c in ("level0", "level1", "level2", "level3", "level4")]
    if len(ladder) > 1:
        L += ["## What each step up the ladder adds", "", "| Step | Change in share right | 95% interval |", "| --- | ---: | ---: |"]
        for a, b in zip(ladder, ladder[1:]):
            d, ci = step_change(by_ctx[a], by_ctx[b])
            L.append(f"| {a} to {b} | {'' if d is None else f'{100 * d:+.0f} pts'} | {'' if not ci else f'{100 * ci[0]:+.0f} to {100 * ci[1]:+.0f} pts'} |")
        L += ["", "An interval that includes zero means this many questions cannot tell the step from no change.", ""]

    if controls:
        L += ["## Questions that cannot be answered", "",
              "The tables do not hold what these questions ask for. The right response is to decline.", "",
              "| Context | Declined, correctly | Answered anyway | Mean confidence when answered anyway |", "| --- | ---: | ---: | ---: |"]
        for c in order:
            rs = [r for r in controls if r["context"] == c]
            if not rs:
                continue
            bad = [r for r in rs if r["status"] == "answered_unanswerable"]
            L.append(f"| {c} | {pct(sum(r['status'] == 'declined_ok' for r in rs) / len(rs))} | {pct(len(bad) / len(rs))} | {num(mean([r['confidence'] for r in bad]), 0)} |")
        L.append("")

    if "level3-misleading" in by_ctx:
        hit = {r["question"] for r in by_ctx["level3-misleading"] if r.get("misled")}
        L += ["## Wrong documentation", "",
              "In `level3-misleading`, the documentation states a few facts wrongly (pay as yearly, the gender codes swapped). "
              "The model cannot detect this, because it never sees a row. The table shows what a wrong description costs.", "",
              "| Context | Right, on the questions the wrong facts touch | Mean stated confidence on them | Right, on the other questions |",
              "| --- | ---: | ---: | ---: |"]
        for c in ("level3", "level3-misleading"):
            if c not in by_ctx:
                continue
            a = [r for r in by_ctx[c] if r["question"] in hit]
            b = [r for r in by_ctx[c] if r["question"] not in hit]
            L.append(f"| {c} | {pct(share_right([a]))} | {num(mean([r['confidence'] for r in a]), 0)} | {pct(share_right([b]))} |")
        L.append("")

    if "level0-padded" in by_ctx and "level0" in by_ctx:
        d, ci = step_change(by_ctx["level0"], by_ctx["level0-padded"])
        L += ["## Length control", "",
              "`level0-padded` is level 0 plus unrelated text as long as the level 4 documentation. "
              "If length alone helped, it would score above level 0.", "",
              f"Change in share right from level0 to level0-padded: {'' if d is None else f'{100 * d:+.0f} pts'}"
              f"{'' if not ci else f' (95% interval {100 * ci[0]:+.0f} to {100 * ci[1]:+.0f} pts)'}.", ""]

    needs = sorted({n for r in main for n in r.get("needs", [])})
    if needs:
        L += ["## Right, by what the question depends on", "", "| Depends on | " + " | ".join(order) + " |", "| --- |" + " ---: |" * len(order)]
        for need in needs:
            cells = []
            for c in order:
                rs = [r for r in by_ctx[c] if need in r.get("needs", [])]
                cells.append(pct(share_right([rs])) if rs else "")
            L.append("| " + need + " | " + " | ".join(cells) + " |")
        L.append("")

    L += ["## Right, by question", "", "| Question | " + " | ".join(order) + " |", "| --- |" + " ---: |" * len(order)]
    for q in sorted({r["question"] for r in main}):
        cells = []
        for c in order:
            rs = [r for r in by_ctx[c] if r["question"] == q]
            cells.append(f"{sum(r['status'] == 'correct' for r in rs)}/{len(rs)}" if rs else "")
        L.append("| " + q + " | " + " | ".join(cells) + " |")
    L.append("")

    gaps = Counter(r["missing"].strip() for r in rows if r.get("missing", "").strip())
    if gaps and not dry:
        L += ["## What the model said it had to guess (most common)", ""]
        L += [f"- {n}x: {text}" for text, n in gaps.most_common(15)]
        L.append("")

    path = folder / "report.md"
    path.write_text("\n".join(L), encoding="utf-8")
    return path


def compare(folders):
    """Side-by-side table for several models."""
    runs = []
    for f in folders:
        rows = [r for r in load(f) if not r.get("unanswerable")]
        runs.append((rows[0]["model"] if rows else Path(f).name, rows))
    order = list(dict.fromkeys(r["context"] for _, rows in runs for r in rows))
    L = ["# Certainty test: models side by side", "",
         "Each cell: share right / overconfidence in points / confident and wrong.", "",
         "| Context | " + " | ".join(m for m, _ in runs) + " |", "| --- |" + " ---: |" * len(runs)]
    for c in order:
        cells = []
        for _, rows in runs:
            rs = [r for r in rows if r["context"] == c]
            if not rs:
                cells.append("")
                continue
            s = summarise(rs)
            over = "" if s["overconfidence"] is None else f"{100 * s['overconfidence']:+.0f}"
            cells.append(f"{pct(s['accuracy'])} / {over} / {pct(s['confident_and_wrong'])}")
        L.append("| " + c + " | " + " | ".join(cells) + " |")
    if any(r.get("dry_run") for _, rows in runs for r in rows):
        L += ["", "**Includes a dry run. Those numbers are made up.**"]
    path = Path(folders[0]).parent / "compare.md"
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    for f in sys.argv[1:]:
        print(write(f))
    if len(sys.argv) > 2:
        print(compare(sys.argv[1:]))
