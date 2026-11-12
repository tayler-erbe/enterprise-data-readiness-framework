"""Run the detector on the real dirty-and-clean tables (the control group).

    python fetch.py
    python run_real.py --base-url http://localhost:8000/v1 --model <name>
    python run_real.py --dry-run

Real columns have no READY / FIXABLE / NEEDS_CONTEXT label, only the cells that
differ between the dirty and the clean file. So this scores three simpler things:

    missed       the column has errors and the model called it READY
    false alarm  the column has no errors and the model did not call it READY
    repaired     the cleaned values the model wrote match the clean file
"""
import argparse
import csv
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "testset"))
sys.path.insert(0, str(HERE.parent))

import detect  # noqa: E402
import run  # noqa: E402
from report import mean, num, pct  # noqa: E402


def load(folder):
    """{dataset: {"header", "raw", "clean"}} and one label per column."""
    folder = Path(folder)
    labels = list(csv.DictReader((folder / "labels.csv").read_text(encoding="utf-8").splitlines()))
    tables = {}
    for name in sorted({l["dataset"] for l in labels}):
        dirty = list(csv.reader((folder / f"{name}_dirty.csv").read_text(encoding="utf-8", errors="replace").splitlines()))
        clean = list(csv.reader((folder / f"{name}_clean.csv").read_text(encoding="utf-8", errors="replace").splitlines()))
        n = min(len(dirty), len(clean)) - 1
        width = len(dirty[0])
        keep = [i for i in range(1, n + 1) if len(dirty[i]) == width and len(clean[i]) == width]
        tables[name] = {"header": dirty[0], "raw": [dirty[i] for i in keep], "clean": [clean[i] for i in keep]}
    out = []
    for l in labels:
        out.append({"table": l["dataset"], "column": l["column"], "case": "real", "has_errors": l["has_errors"] == "True",
                    "verdict": "HAS_ERRORS" if l["has_errors"] == "True" else "READY", "fix": "", "share_changed": float(l["share_changed"])})
    return tables, out


def score(label, reply, clean_sample, raw_sample):
    if reply is None:
        return {"status": "bad_reply", "said": "BAD_REPLY", "confidence": None}
    got = reply["cleaned"]
    repaired = None
    if label["has_errors"] and got:
        repaired = len(got) >= len(clean_sample) and all(detect.same_value(g, w) for g, w in zip(got, clean_sample))
    return {"status": "ok", "said": reply["verdict"], "confidence": reply["confidence"],
            "missed": label["has_errors"] and reply["verdict"] == "READY",
            "false_alarm": (not label["has_errors"]) and reply["verdict"] != "READY",
            "repaired": repaired, "sample_had_errors": clean_sample != raw_sample}


def write_report(out):
    rows = [json.loads(l) for l in (out / "attempts.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    ok = [r for r in rows if r["status"] == "ok"]
    bad = [r for r in ok if r["has_errors"]]
    good = [r for r in ok if not r["has_errors"]]
    share = lambda rs, k: (sum(bool(r[k]) for r in rs if r.get(k) is not None) / max(1, sum(r.get(k) is not None for r in rs))) if rs else None
    L = ["# Control group, real tables: " + (rows[0]["model"] if rows else ""), ""]
    if any(r.get("dry_run") for r in rows):
        L += ["**DRY RUN. The replies were made up by the script. Nothing below is a finding.**", ""]
    L += ["These tables are public and widely used. A model may have seen them, so read these numbers as a control, not as a measure of skill.", "",
          "| Measure | Value |", "| --- | ---: |",
          f"| Columns with errors that the model called READY (missed) | {pct(share(bad, 'missed'))} |",
          f"| Clean columns that the model did not call READY (false alarm) | {pct(share(good, 'false_alarm'))} |",
          f"| Columns with errors where its cleaned values matched the clean file | {pct(share(bad, 'repaired'))} |",
          f"| Mean stated certainty when it missed | {num(mean([r['confidence'] for r in bad if r['missed']]), 0)} |", "",
          "## By table", "", "| Table | Columns with errors | Missed | Clean columns | False alarm |", "| --- | ---: | ---: | ---: | ---: |"]
    for t in sorted({r["table"] for r in ok}):
        b = [r for r in bad if r["table"] == t]
        g = [r for r in good if r["table"] == t]
        L.append(f"| {t} | {len({r['column'] for r in b})} | {pct(share(b, 'missed'))} | {len({r['column'] for r in g})} | {pct(share(g, 'false_alarm'))} |")
    path = out / "report.md"
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base-url", default="http://localhost:8000/v1")
    ap.add_argument("--model", default="")
    ap.add_argument("--api-key", default="")
    ap.add_argument("--data", default=str(HERE / "data"))
    ap.add_argument("--rows", type=int, default=10)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--max-tokens", type=int, default=2500)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.dry_run and not a.model:
        ap.error("--model is required unless --dry-run")
    name = "dry-run" if a.dry_run else re.sub(r"[^A-Za-z0-9._-]+", "_", a.model)
    out = HERE / "runs" / name
    out.mkdir(parents=True, exist_ok=True)
    log = out / "attempts.jsonl"
    done = set()
    if log.exists():
        done = {(r["table"], r["column"], r["rep"]) for r in map(json.loads, log.read_text(encoding="utf-8").splitlines())}
    tables, labels = load(a.data)
    model = None if a.dry_run else run.Model(a.base_url, a.model, a.temperature, a.max_tokens, a.api_key, a.timeout, False)
    with log.open("a", encoding="utf-8") as fh:
        for label in labels:
            t = tables[label["table"]]
            user, clean_sample = detect.prompt(label["table"], t, label, a.rows)
            i = t["header"].index(label["column"])
            raw_sample = [t["raw"][r][i] for r in detect.sample_rows(t, label, a.rows)[:detect.SHOW_CLEANED]]
            for rep in range(a.reps):
                if (label["table"], label["column"], rep) in done:
                    continue
                if a.dry_run:
                    rng = random.Random(f"{label['table']}|{label['column']}|{rep}")
                    text = json.dumps({"verdict": rng.choice(detect.VERDICTS), "confidence": rng.randint(50, 95), "cleaned": []})
                else:
                    text, _ = model.ask(detect.SYSTEM, user)
                rec = score(label, detect.parse(text), clean_sample, raw_sample)
                rec.update(table=label["table"], column=label["column"], has_errors=label["has_errors"], rep=rep, model=name, dry_run=a.dry_run)
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
    print("report:", write_report(out))


if __name__ == "__main__":
    main()
