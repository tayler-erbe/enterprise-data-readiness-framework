"""Show a model a table the way it arrives and ask what one column means.

    python ask.py --base-url http://localhost:8000/v1 --model <name>
    python ask.py --dry-run          # fake replies, to check the pipeline

The model sees the table name, column names, data types and a random sample of
rows. For one target column it picks a meaning from a list, says what
preparation the column needs, states a certainty, and names any other meaning
that fits the evidence equally well.

Each column is asked under four kinds of evidence:

    full5     every column, clear names, 5 rows
    full50    every column, clear names, 50 rows
    cryptic5  every column, 5 rows, the target column's name replaced by a meaningless one
    alone5    the target column alone, clear name, 5 rows
"""
import argparse
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

import make_tables as mt  # noqa: E402
import run  # noqa: E402  (the model connection and reply parsing are shared with the SQL test)

CONDITIONS = {
    "full5": {"rows": 5, "cryptic": False, "alone": False},
    "full50": {"rows": 50, "cryptic": False, "alone": False},
    "cryptic5": {"rows": 5, "cryptic": True, "alone": False},
    "alone5": {"rows": 5, "cryptic": False, "alone": True},
}

SYSTEM = (
    "You are reviewing a data table before it is moved into a new system. You see the table name, the column names, "
    "the data types and a random sample of rows. You cannot see the rest of the table and there is no data dictionary.\n"
    "For the ONE target column, reply with one JSON object and nothing else, with these keys:\n"
    '  "meaning": the id from MEANINGS that best says what the column holds\n'
    '  "preparation": a list of ids from PREPARATION that the column needs before use; [] if none\n'
    '  "confidence": a number from 0 to 100, your estimate of the chance that "meaning" is exactly right\n'
    '  "alternatives": a list of other ids from MEANINGS that fit what you can see just as well; [] if none\n'
    '  "evidence": one sentence on what you relied on'
)


def data_type(values):
    if all(isinstance(v, int) for v in values):
        return "INTEGER"
    if all(isinstance(v, (int, float)) for v in values):
        return "DECIMAL"
    return "TEXT"


def sample_rows(table, n, instance, name):
    rng = random.Random(f"sample|{instance}|{name}|{n}")
    idx = sorted(rng.sample(range(len(table["raw"])), min(n, len(table["raw"]))))
    return [table["raw"][i] for i in idx]


def determinable(column, condition, shown):
    """Can the column's meaning be settled from what this condition shows? True, False, or None for a judgement call."""
    s = column["settled_by"]
    if s == "judgement":
        return None
    if s in ("values", "name_or_neighbours"):
        return True
    if s == "name":
        return condition != "cryptic5"
    if s == "neighbours":
        return condition != "alone5"
    if s == "day_gt_12":
        return any(int(part) > 12 for v in shown for part in str(v).split("/")[:2])
    return False  # nothing


def ceiling(column, settled):
    """Best possible chance of being right when the evidence cannot settle a coin-flip column."""
    if settled is False and len(column["candidates"]) > 1 and column["settled_by"] != "name":
        return 1 / len(column["candidates"])
    return None


def prompt(table_name, table, target, condition, instance):
    c = CONDITIONS[condition]
    rows = sample_rows(table, c["rows"], instance, table_name)
    keep = [i for i, col in enumerate(table["columns"]) if not c["alone"] or i == target]
    names = [(table["columns"][i]["cryptic"] if c["cryptic"] and i == target else table["columns"][i]["name"]) for i in keep]
    types = [data_type([r[i] for r in table["raw"]]) for i in keep]
    shown = [r[target] for r in rows]
    lines = ["TABLE " + table_name, "COLUMNS"]
    lines += ["  " + n + " " + t for n, t in zip(names, types)]
    lines += ["", f"SAMPLE ({len(rows)} random rows)", ",".join(names)]
    lines += [",".join(str(r[i]) for i in keep) for r in rows]
    lines += ["", "TARGET COLUMN: " + names[keep.index(target)], "", "MEANINGS"]
    lines += ["  " + k + ": " + v for k, v in mt.MEANINGS.items()]
    lines += ["", "PREPARATION"]
    lines += ["  " + k + ": " + v for k, v in mt.OPS.items()]
    return "\n".join(lines), shown


def parse(text):
    text = re.sub(r"(?is)<think>.*?</think>", "", text or "")
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        obj = json.loads(text[a:b + 1])
    except ValueError:
        return None
    if not isinstance(obj, dict) or not isinstance(obj.get("meaning"), str):
        return None
    try:
        conf = max(0.0, min(100.0, float(obj.get("confidence"))))
    except (TypeError, ValueError):
        conf = None
    ids = lambda v: [x for x in v if isinstance(x, str)] if isinstance(v, list) else []
    return {"meaning": obj["meaning"].strip(), "preparation": [x for x in ids(obj.get("preparation")) if x != "none"],
            "confidence": conf, "alternatives": ids(obj.get("alternatives")), "evidence": str(obj.get("evidence") or "")[:300]}


def score(column, reply):
    """What one reply got right."""
    if reply is None:
        return {"status": "bad_reply", "correct": False, "confidence": None, "answer": "BAD_REPLY"}
    others = [c for c in column["candidates"] if c != column["truth"]]
    return {
        "status": "ok",
        "answer": reply["meaning"],
        "correct": reply["meaning"] == column["truth"],
        "in_candidates": reply["meaning"] in column["candidates"],
        "named_alternative": (any(o in reply["alternatives"] or o == reply["meaning"] and column["truth"] in reply["alternatives"] for o in others)
                              if others else None),
        "listed_any_alternative": bool(reply["alternatives"]),
        "preparation_right": set(reply["preparation"]) == set(column["ops"]),
        "confidence": reply["confidence"],
        "evidence": reply["evidence"],
    }


def fake(column, condition, settled, rep):
    rng = random.Random(f"{column['name']}|{condition}|{rep}")
    right = rng.random() < (0.85 if settled else 0.45)
    wrong = rng.choice([m for m in mt.MEANINGS if m != column["truth"]])
    return json.dumps({"meaning": column["truth"] if right else wrong, "preparation": column["ops"] if rng.random() < 0.6 else [],
                       "confidence": rng.randint(55, 98), "alternatives": [], "evidence": ""})


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base-url", default="http://localhost:8000/v1")
    ap.add_argument("--model", default="")
    ap.add_argument("--api-key", default="")
    ap.add_argument("--instances", type=int, default=4, help="versions of the tables, each with its own coin flips")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--max-tokens", type=int, default=2000)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--conditions", default=",".join(CONDITIONS))
    ap.add_argument("--no-logprobs", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.dry_run and not a.model:
        ap.error("--model is required unless --dry-run")

    label = "dry-run" if a.dry_run else re.sub(r"[^A-Za-z0-9._-]+", "_", a.model)
    out = Path(a.out or HERE / "runs" / label)
    out.mkdir(parents=True, exist_ok=True)
    log = out / "attempts.jsonl"
    done = set()
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done.add((r["instance"], r["table"], r["column"], r["condition"], r["rep"]))

    model = None if a.dry_run else run.Model(a.base_url, a.model, a.temperature, a.max_tokens, a.api_key, a.timeout, not a.no_logprobs)
    conditions = [c for c in a.conditions.split(",") if c in CONDITIONS]
    n = 0
    with log.open("a", encoding="utf-8") as fh:
        for inst in range(a.instances):
            tables, _ = mt.build(inst)
            for tname, table in tables.items():
                for ti, column in enumerate(table["columns"]):
                    for cond in conditions:
                        user, shown = prompt(tname, table, ti, cond, inst)
                        settled = determinable(column, cond, shown)
                        for rep in range(a.reps):
                            n += 1
                            if (inst, tname, column["name"], cond, rep) in done:
                                continue
                            if a.dry_run:
                                text, tokens = fake(column, cond, settled, rep), None
                            else:
                                try:
                                    text, tokens = model.ask(SYSTEM, user)
                                except Exception as e:
                                    raise SystemExit("could not reach the model at " + a.base_url + ": " + str(e) +
                                                     "\nFinished attempts are saved; run the same command to continue.")
                            rec = score(column, parse(text))
                            lp = run.sql_token_stats(tokens, None)[0] if tokens else None
                            rec.update(instance=inst, table=tname, column=column["name"], condition=cond, rep=rep,
                                       truth=column["truth"], settled_by=column["settled_by"], determinable=settled,
                                       ceiling=ceiling(column, settled), model=label, dry_run=a.dry_run,
                                       temperature=a.temperature, logprob_mean=lp)
                            fh.write(json.dumps(rec) + "\n")
                            fh.flush()
                            print(f"[{n}] inst{inst} {tname}.{column['name']:14} {cond:9} #{rep} "
                                  f"{'right' if rec['correct'] else 'wrong'} conf={rec['confidence']}")

    import score_columns
    print("\nreport:", score_columns.write(out))


if __name__ == "__main__":
    main()
