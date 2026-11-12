"""Run a model over the test set as a garbage detector, and score it.

    python detect.py --base-url http://localhost:8000/v1 --model <name>
    python detect.py --dry-run            # fake replies, to check the pipeline

For each labelled column the model sees the raw table (name, columns, types and
a sample of rows) and must say whether the column is READY, FIXABLE,
NEEDS_CONTEXT or GARBAGE, name the fix, state its certainty, and write out the
cleaned values for the first few rows. Those cleaned values are compared with
the clean table, so a model that says "fixable" has to show the fix.

The sample always includes some of the rows that need changing. A random ten
rows would often miss the problem, and then READY would be the honest answer.
"""
import argparse
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import build  # noqa: E402
import tables as file_cases  # noqa: E402
import run  # noqa: E402  (model connection shared with the other tests)

VERDICTS = ["READY", "FIXABLE", "NEEDS_CONTEXT", "GARBAGE"]
FIXES = {
    "parse_date": "Turn date text or a day number into a date",
    "parse_timestamp": "Turn a number or text into a date and time",
    "parse_number": "Turn number text into a number (separators, symbols, decimal commas)",
    "convert_unit": "Convert to one unit",
    "scale_number": "Multiply or divide to reach the standard scale",
    "keep_as_text": "Store as text, restoring anything lost when it was read as a number",
    "replace_missing_marker": "Replace a stand-in for missing with a true blank",
    "remove_impossible_values": "Blank out values that cannot be real",
    "normalise_categories": "Bring spelling, case and spacing variants to one value",
    "repair_encoding": "Repair letters garbled by the wrong text encoding",
    "split_values": "Split several facts packed into one cell",
    "decode_values": "Replace codes with what they mean",
    "recompute_derived": "Recompute a value from the columns it is derived from",
}
SHOW_CLEANED = 5

SYSTEM = (
    "You check data before anyone analyses it. You see one table as it arrived: its name, columns, data types and a sample "
    "of rows. There is no data dictionary and nobody to ask. Judge the ONE target column.\n"
    "Reply with one JSON object and nothing else, with these keys:\n"
    '  "verdict": one of\n'
    '      "READY"          usable as it is\n'
    '      "FIXABLE"        usable after a fix that the table itself makes certain\n'
    '      "NEEDS_CONTEXT"  it cannot be read reliably without a data dictionary or the owner, because more than one '
    "reading fits or its meaning is not shown\n"
    '      "GARBAGE"        no fix would make it usable\n'
    '  "fix": the id from FIXES that the column needs, or "" if none\n'
    '  "issue": one short sentence on what is wrong, or "" if nothing\n'
    '  "assumed": if your answer depends on an assumption the table does not confirm, say what it is; otherwise ""\n'
    '  "confidence": a number from 0 to 100, your estimate of the chance that your verdict is right\n'
    f'  "cleaned": the first {SHOW_CLEANED} sample values of the target column as they should be after the fix, in order. '
    'Dates as YYYY-MM-DD, date-times as YYYY-MM-DDTHH:MM:SSZ, numbers as numbers, missing as "". '
    "Give [] if the verdict is NEEDS_CONTEXT or GARBAGE."
)


FILE_FIXES = {
    "drop_duplicate_rows": "Remove rows that repeat another row exactly",
    "skip_preamble": "Skip title lines above the header row",
    "drop_repeated_headers": "Remove copies of the header row from inside the data",
    "drop_total_rows": "Remove subtotal and total rows from the data rows",
    "drop_empty_rows_columns": "Remove blank rows and blank columns",
    "rejoin_split_field": "Rejoin a field that an unquoted comma split in two",
    "reshape_wide_to_long": "Turn columns that are really values, such as months, into rows",
}

FILE_SYSTEM = (
    "You check data files before anyone analyses them. You see lines from one file as it arrived. There is no data "
    "dictionary and nobody to ask. Judge the FILE AS A WHOLE: its layout, not the meaning of single columns.\n"
    "Reply with one JSON object and nothing else, with these keys:\n"
    '  "verdict": "READY" (a tidy table), "FIXABLE" (tidy after a fix the file itself makes certain), '
    '"NEEDS_CONTEXT" (cannot be used without being told what the columns are), or "GARBAGE" (not usable data)\n'
    '  "fix": the id from FIXES that the file needs, or "" if none\n'
    '  "issue": one short sentence on what is wrong, or "" if nothing\n'
    '  "assumed": any assumption the file does not confirm, or ""\n'
    '  "confidence": a number from 0 to 100, your estimate of the chance that your verdict is right'
)


def file_prompt(name, t, label):
    """The first lines of the file, a few lines around the place the problem shows, and the last lines."""
    raw = t["raw"]
    line = lambda r: ",".join(r)
    show = set(range(min(10, len(raw)))) | set(range(max(0, len(raw) - 3), len(raw)))
    show |= {i for i in range(label["focus_row"] - 1, label["focus_row"] + 5) if 0 <= i < len(raw)}
    out, last = ["FILE " + name + ".csv", f"{len(raw)} lines. Line numbers are shown; gaps are lines left out.", ""], -1
    for i in sorted(show):
        if i != last + 1:
            out.append("...")
        out.append(f"{i + 1:>4}: {line(raw[i])}")
        last = i
    out += ["", "FIXES"] + ["  " + k + ": " + v for k, v in FILE_FIXES.items()]
    return "\n".join(out)


def data_type(values):
    if all(isinstance(v, int) for v in values):
        return "INTEGER"
    if all(isinstance(v, (int, float)) for v in values):
        return "DECIMAL"
    return "TEXT"


def sample_rows(table, label, n):
    """Row numbers to show: a few rows that need changing, the rest at random, in a fixed shuffled order."""
    rng = random.Random(f"sample|{label['table']}|{label['column']}|{n}")
    i = table["header"].index(label["column"])
    total = len(table["raw"])
    changed = [r for r in range(total) if str(table["raw"][r][i]) != str(table["clean"][r][i])]
    must = rng.sample(changed, min(3, len(changed)))
    if label["case"] == "f_date_slash_order":  # the row that settles the order has to be visible
        telling = [r for r in range(total) if any(int(p) > 12 for p in str(table["raw"][r][i]).split("/")[:2])]
        must = [rng.choice(telling)] + must[:2]
    rest = [r for r in range(total) if r not in must]
    rows = must + rng.sample(rest, max(0, min(n, total) - len(must)))
    rng.shuffle(rows)
    return rows


def prompt(tname, table, label, n):
    rows = sample_rows(table, label, n)
    lines = ["TABLE " + tname, "COLUMNS"]
    lines += ["  " + h + " " + data_type([r[j] for r in table["raw"]]) for j, h in enumerate(table["header"])]
    lines += ["", f"SAMPLE ({len(rows)} rows)", ",".join(table["header"])]
    lines += [",".join(str(v) for v in table["raw"][r]) for r in rows]
    lines += ["", "TARGET COLUMN: " + label["column"], "", "FIXES"]
    lines += ["  " + k + ": " + v for k, v in FIXES.items()]
    i = table["header"].index(label["column"])
    return "\n".join(lines), [table["clean"][r][i] for r in rows[:SHOW_CLEANED]]


def same_value(got, want):
    """Does one cleaned value match the answer key? Numbers within 0.01; blank, null and None are the same."""
    blank = lambda v: v is None or str(v).strip().lower() in ("", "null", "none", "nan")
    if blank(got) or blank(want):
        return blank(got) and blank(want)
    try:
        return abs(float(got) - float(want)) <= 0.01
    except (TypeError, ValueError):
        return str(got).strip() == str(want).strip()


def parse(text):
    text = re.sub(r"(?is)<think>.*?</think>", "", text or "")
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        obj = json.loads(text[a:b + 1])
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None
    verdict = str(obj.get("verdict", "")).strip().upper().replace(" ", "_")
    if verdict not in VERDICTS:
        return None
    try:
        conf = max(0.0, min(100.0, float(obj.get("confidence"))))
    except (TypeError, ValueError):
        conf = None
    cleaned = obj.get("cleaned")
    return {"verdict": verdict, "fix": str(obj.get("fix") or "").strip(), "issue": str(obj.get("issue") or "")[:200],
            "assumed": str(obj.get("assumed") or "")[:200], "confidence": conf, "cleaned": cleaned if isinstance(cleaned, list) else []}


def score(label, reply, clean_sample):
    """What one reply got right."""
    if reply is None:
        return {"status": "bad_reply", "said": "BAD_REPLY", "correct": False, "confidence": None}
    truth = label["verdict"]
    usable = lambda v: v in ("READY", "FIXABLE")
    cleaned_right = None
    if truth in ("READY", "FIXABLE") and usable(reply["verdict"]):
        got = reply["cleaned"]
        cleaned_right = len(got) >= len(clean_sample) and all(same_value(g, w) for g, w in zip(got, clean_sample))
    # On a column that needs context, did a guessed fix happen to land on the true reading?
    guessed_right = None
    if truth == "NEEDS_CONTEXT" and reply["cleaned"]:
        got = reply["cleaned"]
        guessed_right = len(got) >= len(clean_sample) and all(same_value(g, w) for g, w in zip(got, clean_sample))
    return {
        "status": "ok", "said": reply["verdict"], "correct": reply["verdict"] == truth,
        "dangerous": not usable(truth) and usable(reply["verdict"]),      # would run analysis on data it should not
        "over_cautious": usable(truth) and not usable(reply["verdict"]),  # would hold back data that is fine
        "fix_right": (reply["fix"] == label["fix"]) if truth == "FIXABLE" else None,
        "cleaned_right": cleaned_right, "guessed_right": guessed_right,
        "stated_assumption": bool(reply["assumed"]), "confidence": reply["confidence"],
        "issue": reply["issue"], "assumed": reply["assumed"],
    }


def fake(label, clean_sample, rep):
    rng = random.Random(f"{label['table']}|{label['column']}|{rep}")
    right = rng.random() < 0.6
    verdict = label["verdict"] if right else rng.choice([v for v in VERDICTS if v != label["verdict"]])
    return json.dumps({"verdict": verdict, "fix": label["fix"] if right else "", "issue": "", "assumed": "",
                       "confidence": rng.randint(50, 98), "cleaned": clean_sample if verdict in ("READY", "FIXABLE") and rng.random() < 0.7 else []})


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base-url", default="http://localhost:8000/v1")
    ap.add_argument("--model", default="")
    ap.add_argument("--api-key", default="")
    ap.add_argument("--variations", type=int, default=12, help="examples of each case to run")
    ap.add_argument("--rows", type=int, default=10, help="sample rows shown")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--max-tokens", type=int, default=2500)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--no-logprobs", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-files", action="store_true", help="run the column cases only, not the whole-file cases")
    a = ap.parse_args()
    if not a.dry_run and not a.model:
        ap.error("--model is required unless --dry-run")

    label_name = "dry-run" if a.dry_run else re.sub(r"[^A-Za-z0-9._-]+", "_", a.model)
    out = Path(a.out or HERE / "runs" / label_name)
    out.mkdir(parents=True, exist_ok=True)
    log = out / "attempts.jsonl"
    done = set()
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done.add((r["table"], r["column"], r["rep"]))

    tables, labels = build.build(variations=a.variations)
    model = None if a.dry_run else run.Model(a.base_url, a.model, a.temperature, a.max_tokens, a.api_key, a.timeout, not a.no_logprobs)
    total, n = len(labels) * a.reps, 0
    with log.open("a", encoding="utf-8") as fh:
        for label in labels:
            user, clean_sample = prompt(label["table"], tables[label["table"]], label, a.rows)
            for rep in range(a.reps):
                n += 1
                if (label["table"], label["column"], rep) in done:
                    continue
                if a.dry_run:
                    text = fake(label, clean_sample, rep)
                else:
                    try:
                        text, _tokens = model.ask(SYSTEM, user)
                    except Exception as e:
                        raise SystemExit("could not reach the model at " + a.base_url + ": " + str(e) +
                                         "\nFinished attempts are saved; run the same command to continue.")
                rec = score(label, parse(text), clean_sample)
                rec.update(table=label["table"], column=label["column"], case=label["case"], truth=label["verdict"],
                           settled_by=label["settled_by"], two_readings=bool(label["other_readings"]), rep=rep,
                           model=label_name, dry_run=a.dry_run, temperature=a.temperature, rows_shown=a.rows)
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                print(f"[{n}/{total}] {label['case']:30} truth={label['verdict']:13} said={rec['said']:13} conf={rec['confidence']}")

        if not a.skip_files:
            files, file_labels = file_cases.build(variations=a.variations)
            for fl in file_labels:
                label = {"table": fl["table"], "column": "(whole file)", "case": fl["case"], "verdict": fl["verdict"], "fix": fl["fix"],
                         "settled_by": "", "other_readings": "", "focus_row": fl["focus_row"]}
                user = file_prompt(fl["table"], files[fl["table"]], label)
                for rep_no in range(a.reps):
                    if (label["table"], label["column"], rep_no) in done:
                        continue
                    if a.dry_run:
                        text = fake(label, [], rep_no)
                    else:
                        try:
                            text, _tokens = model.ask(FILE_SYSTEM, user)
                        except Exception as e:
                            raise SystemExit("could not reach the model at " + a.base_url + ": " + str(e) +
                                             "\nFinished attempts are saved; run the same command to continue.")
                    rec = score(label, parse(text), [])
                    rec.update(cleaned_right=None, guessed_right=None)
                    rec.update(table=label["table"], column=label["column"], case=label["case"], truth=label["verdict"],
                               settled_by="", two_readings=False, rep=rep_no, model=label_name, dry_run=a.dry_run,
                               temperature=a.temperature, rows_shown=a.rows)
                    fh.write(json.dumps(rec) + "\n")
                    fh.flush()
                    print(f"[file] {label['case']:30} truth={label['verdict']:13} said={rec['said']:13} conf={rec['confidence']}")

    import score_detect
    print("\nreport:", score_detect.write(out))


if __name__ == "__main__":
    main()
