"""Run the detector under extra conditions, to test failures that people have reported.

    python conditions.py --condition rows50 --base-url http://localhost:8000/v1 --model <name>
    python conditions.py --condition all --dry-run        # fake replies, to check the pipeline

The base test (detect.py) shows ten sample rows and nothing else. Each condition
here changes ONE thing about what the model sees:

    rows5, rows50        fewer or more sample rows
    profile              ten rows, plus a profile of the whole target column
    doc_agree            ten rows, plus a data dictionary entry that is true
    doc_conflict         ten rows, plus a data dictionary entry the sample contradicts
    doc_agree_asked      as doc_agree, and the model is asked whether the entry agrees with the sample
    doc_conflict_asked   as doc_conflict, and the model is asked the same
    name_conflict        the target column is renamed to something its values contradict
    name_two             new columns whose name fits two meanings (sales: units or money?)
    name_clear           the same values as name_two under a name that fits one meaning (the control)
    describe_forced      write a description of the column; no way to decline
    describe_allowed     write a description, or say the table does not show what the column means

Each documentation and name conflict is one the shown rows refute; the tests check that row by row.
Results go to runs/<model>/cond_<condition>/attempts.jsonl. A stopped run continues when repeated.
Everything is generated. Nothing here describes a real person or organisation.
"""
import argparse
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import build  # noqa: E402
import detect  # noqa: E402
from cases import CASES, DOMAINS, WEEKDAYS  # noqa: E402

CONDITIONS = ["rows5", "rows50", "profile", "doc_agree", "doc_conflict", "doc_agree_asked", "doc_conflict_asked",
              "name_conflict", "name_two", "name_clear", "describe_forced", "describe_allowed"]


def num(v):
    return float(v) if re.match(r"^-?\d+(\.\d+)?$", str(v).strip()) else None


# ---------- documentation: a true entry, an entry the sample contradicts, and the check that it does ----------

def _order(label, agree):
    day_first = (label["true_reading"] == "day_first") == agree
    return "Calendar date, written day first (DD/MM/YYYY)." if day_first else "Calendar date, written month first (MM/DD/YYYY)."


def _dow(label, agree):
    monday = (label["true_reading"] == "monday_is_1") == agree
    return "Day of the week as a number: " + ("1 is Monday, 7 is Sunday." if monday else "1 is Sunday, 7 is Saturday.")


DOCS = {  # case: (true entry, contradicted entry, does the shown sample refute the contradicted entry?)
    "r_percent_named": ("Percentage, on a scale from 0 to 100.", "Share, as a fraction between 0 and 1.",
                        lambda shown, helper: any((num(v) or 0) > 1 for v in shown)),
    "f_percent_sign": ("Percentage, on a scale from 0 to 100.", "Share, as a fraction between 0 and 1.",
                       lambda shown, helper: any((num(str(v).replace("%", "")) or 0) > 1 for v in shown)),
    "r_email": ("Contact email address.", "Contact telephone number, digits only.",
                lambda shown, helper: any("@" in str(v) for v in shown)),
    "r_weekday_name": ("Day of the week, written out in English.", "Month of the year, written out in English.",
                       lambda shown, helper: any(str(v) in WEEKDAYS for v in shown)),
    "r_date_iso": ("Calendar date, written YYYY-MM-DD.", "Calendar date, written DD/MM/YYYY.",
                   lambda shown, helper: any(re.match(r"^\d{4}-\d{2}-\d{2}$", str(v)) for v in shown)),
    "f_epoch_seconds": ("Moment in time, as seconds since 1 January 1970 UTC.", "Moment in time, as milliseconds since 1 January 1970 UTC.",
                        lambda shown, helper: any((num(v) or 1e12) < 1e11 for v in shown)),   # as milliseconds these fall in 1970
    "f_epoch_millis": ("Moment in time, as milliseconds since 1 January 1970 UTC.", "Moment in time, as seconds since 1 January 1970 UTC.",
                       lambda shown, helper: any((num(v) or 0) > 1e11 for v in shown)),       # as seconds these fall after the year 5000
    "f_currency_symbol": ("Amount in US dollars.", "Amount in euros.",
                          lambda shown, helper: any("$" in str(v) for v in shown)),
    "f_date_slash_order": (lambda l: _order(l, True), lambda l: _order(l, False),
                           lambda shown, helper: any(int(p) > 12 for v in shown for p in str(v).split("/")[:2] if p.isdigit())),
    "f_weekday_number_with_date": (lambda l: _dow(l, True), lambda l: _dow(l, False),
                                   lambda shown, helper: bool(helper)),                       # any dated row settles which day is 1
    "x_amount_with_currency_column": ("Amount, in the currency named in the column beside it.", "Amount in US dollars.",
                                      lambda shown, helper: any(str(h) != "USD" for h in helper)),
    "x_weight_with_unit_column": ("Weight, in the unit named in the column beside it.", "Weight in kilograms.",
                                  lambda shown, helper: any(str(h).lower() != "kg" for h in helper)),
}


def doc_text(label, agree):
    entry = DOCS[label["case"]][0 if agree else 1]
    return entry(label) if callable(entry) else entry


def doc_refuted(label, table, rows_shown):
    """Do the rows the model is shown contradict the false entry? Used by the tests."""
    i = table["header"].index(label["column"])
    helper = []
    if label["helper_columns"]:
        j = table["header"].index(label["helper_columns"].split("; ")[0])
        helper = [table["raw"][r][j] for r in rows_shown]
    return DOCS[label["case"]][2]([table["raw"][r][i] for r in rows_shown], helper)


# ---------- names ----------

NAME_CONFLICT = {  # case: (a name the values contradict, does a value refute it?)
    "r_email": ("phone_number", lambda v: "@" in str(v)),
    "r_weekday_name": ("month_name", lambda v: str(v) in WEEKDAYS),
    "r_date_iso": ("unit_price", lambda v: bool(re.match(r"^\d{4}-\d{2}-\d{2}$", str(v)))),
    "r_person_name": ("email_address", lambda v: "@" not in str(v)),
    "r_category_words": ("birth_date", lambda v: not re.search(r"\d", str(v))),
    "r_amount_named": ("item_count", lambda v: num(v) is not None and float(v) != int(float(v))),
    "f_percent_sign": ("postal_code", lambda v: "%" in str(v)),
    "f_currency_symbol": ("quantity", lambda v: "$" in str(v)),
    "f_date_mixed_formats": ("customer_name", lambda v: bool(re.search(r"\d{4}", str(v)))),
    "f_boolean_variants": ("order_date", lambda v: not re.search(r"\d{2}", str(v))),
    "f_units_written": ("email", lambda v: "@" not in str(v)),
    "f_epoch_millis": ("age_years", lambda v: (num(v) or 0) > 1e11),
}

TWO_MEANING = {  # name that fits two meanings: (readings, a name that fits one, how the values are drawn)
    "sales": (["units sold", "money taken"], "units_sold", lambda rng: rng.randint(3, 400)),
    "rate": (["a percentage", "a price per hour"], "hourly_rate_usd", lambda rng: round(rng.uniform(8, 45), 2)),
    "volume": (["a number of transactions", "a quantity in litres"], "transaction_count", lambda rng: rng.randint(10, 900)),
    "term": (["months", "years", "days"], "term_months", lambda rng: rng.choice([6, 12, 18, 24, 30, 36])),
    "duration": (["minutes", "seconds", "hours"], "duration_minutes", lambda rng: rng.randint(5, 240)),
    "discount": (["a percentage", "an amount of money"], "discount_pct", lambda rng: rng.choice([5, 10, 15, 20, 25, 30, 40, 50])),
}


def name_tables(variations, clear, rows=120, seed=20261117):
    """Small tables holding one column whose name fits two meanings, or (clear=True) the same values under a plain name."""
    tables, labels = {}, []
    domains = list(DOMAINS)
    for var in range(variations):
        for k, (name, (readings, plain, draw)) in enumerate(TWO_MEANING.items()):
            dom_name = domains[(var + k) % len(domains)]
            dom = DOMAINS[dom_name]
            tname = f"{dom_name}_{dom['entity']}_names_v{var:02d}_{k:02d}"
            fill = [CASES[c]["make"](random.Random(f"{seed}|{var}|{k}|{c}"), rows, dom) for c in ("r_identifier", "r_date_iso", "r_category_words")]
            rng = random.Random(f"{seed}|{var}|{name}")          # the same values whichever name is used
            values = [draw(rng) for _ in range(rows)]
            col = plain if clear else name
            header = [f["name"] for f in fill] + [col]
            body = [list(r) for r in zip(*[f["raw"] for f in fill], values)]
            tables[tname] = {"header": header, "raw": body, "clean": [list(r) for r in body]}
            labels.append({"table": tname, "column": col, "case": ("t_clear_" if clear else "t_two_") + name,
                           "verdict": "READY" if clear else "NEEDS_CONTEXT", "fix": "", "settled_by": "name" if clear else "nothing",
                           "true_reading": "", "other_readings": "" if clear else "; ".join(readings), "helper_columns": "",
                           "domain": dom_name, "variation": var})
    return tables, labels


# ---------- prompts ----------

DOC_SYSTEM = detect.SYSTEM.replace("There is no data dictionary and nobody to ask.",
                                   "You are given the data dictionary entry for the target column. There is nobody to ask.")
assert DOC_SYSTEM != detect.SYSTEM
DOC_ASKED = '\n  "doc_agrees": true or false. Does the data dictionary entry agree with what the sample shows?'

DESCRIBE_FORCED = (
    "You write documentation for data tables. You see one table as it arrived: its name, columns, data types and a sample "
    "of rows. There is no data dictionary and nobody to ask. Write the description of the ONE target column.\n"
    "Reply with one JSON object and nothing else, with these keys:\n"
    '  "description": one or two sentences saying what the column holds, for someone who will analyse it\n'
    '  "confidence": a number from 0 to 100, your estimate of the chance that the description is right'
)
DESCRIBE_ALLOWED = DESCRIBE_FORCED + (
    '\n  "can_tell": true or false. Say false if the table does not show what the column means well enough to describe it reliably; '
    'then use "description" to say what would have to be confirmed.'
)

DOUBT = re.compile(r"\b(unclear|unknown|ambiguous|cannot be determined|can't be determined|not clear|uncertain|unspecified|"
                   r"not specified|may be|might be|could be|possibly|likely|appears to|seems to|either|presumably|"
                   r"cannot tell|undetermined|needs? (clarification|confirmation|context))\b", re.I)
NAME_MENTION = re.compile(r"(column name|\bname\b|header|mislabel|misnamed|mis-named|labell?ed)", re.I)
DOC_MENTION = re.compile(r"(dictionary|documentation|description|documented|\bentry\b)", re.I)
CLASH = re.compile(r"(conflict|contradict|disagree|inconsisten|mismatch|wrong|incorrect|not match|out of date|differ|"
                   r"\bbut\b|however|whereas|instead|rather than|\bnot (a|an|the)\b|suggests otherwise)", re.I)


def shape(v):
    return re.sub(r"[a-z]", "a", re.sub(r"[A-Z]", "A", re.sub(r"\d", "9", str(v))))


def profile(values):
    """A plain profile of the whole column, of the kind any profiling tool gives."""
    filled = [v for v in values if str(v).strip() != ""]
    L = [f"  rows: {len(values)}", f"  blank: {len(values) - len(filled)}", f"  distinct values: {len(set(map(str, filled)))}"]
    nums = [num(v) for v in filled]
    if filled and all(x is not None for x in nums):
        L.append(f"  smallest: {min(nums):g}   largest: {max(nums):g}")
    else:
        L.append(f"  shortest: {min((len(str(v)) for v in filled), default=0)} characters   longest: {max((len(str(v)) for v in filled), default=0)}")
    L.append("  most common values: " + "; ".join(f"{v} ({k})" for v, k in Counter(map(str, filled)).most_common(6)))
    L.append("  most common shapes (9 = digit, A = capital, a = small letter): "
             + "; ".join(f"{s} ({k})" for s, k in Counter(map(shape, filled)).most_common(6)))
    return "\n".join(L)


def renamed(table, column, new):
    """A copy of the table with one column called `new`. Returns (table, the name used)."""
    while new in table["header"]:
        new += "_x"
    i = table["header"].index(column)
    return dict(table, header=table["header"][:i] + [new] + table["header"][i + 1:]), new


def make_prompt(tname, table, column, rows_shown):
    """The same text as detect.prompt, with the rows fixed in advance."""
    lines = ["TABLE " + tname, "COLUMNS"]
    lines += ["  " + h + " " + detect.data_type([r[j] for r in table["raw"]]) for j, h in enumerate(table["header"])]
    lines += ["", f"SAMPLE ({len(rows_shown)} rows)", ",".join(table["header"])]
    lines += [",".join(str(v) for v in table["raw"][r]) for r in rows_shown]
    lines += ["", "TARGET COLUMN: " + column, "", "FIXES"]
    lines += ["  " + k + ": " + v for k, v in detect.FIXES.items()]
    i = table["header"].index(column)
    return "\n".join(lines), [table["clean"][r][i] for r in rows_shown[:detect.SHOW_CLEANED]]


def items(condition, variations=12, n=10):
    """Yields (system, user, label, clean_sample, extra, rows_shown) for every question in one condition."""
    if condition in ("name_two", "name_clear"):
        tables, labels = name_tables(variations, clear=condition == "name_clear")
    else:
        tables, labels = build.build(variations=variations)
    if condition.startswith("doc"):
        labels = [l for l in labels if l["case"] in DOCS]
    if condition == "name_conflict":
        labels = [l for l in labels if l["case"] in NAME_CONFLICT]
    rows = {"rows5": 5, "rows50": 50}.get(condition, n)
    for label in labels:
        table, extra, system = tables[label["table"]], {}, detect.SYSTEM
        rows_shown = detect.sample_rows(table, label, rows)        # chosen before any renaming, so conditions show the same rows
        column = label["column"]
        if condition == "name_conflict":
            table, column = renamed(table, column, NAME_CONFLICT[label["case"]][0])
            # A name its values contradict: the name or the data is wrong, and only the owner can say which.
            extra = {"base_truth": label["verdict"], "shown_as": column}
            label = dict(label, verdict="NEEDS_CONTEXT")
        user, clean_sample = make_prompt(label["table"], table, column, rows_shown)
        if condition == "profile":
            i = table["header"].index(column)
            user = user.replace("\n\nFIXES", "\n\nPROFILE OF THE TARGET COLUMN (every row)\n" + profile([r[i] for r in table["raw"]]) + "\n\nFIXES")
        if condition.startswith("doc"):
            agree = "agree" in condition
            text = doc_text(label, agree)
            user = user.replace("\n\nFIXES", f"\nDATA DICTIONARY ENTRY for {column}: {text}\n\nFIXES")
            system = DOC_SYSTEM + (DOC_ASKED if condition.endswith("asked") else "")
            extra = {"doc": text, "doc_true": agree}
        if condition.startswith("describe"):
            user = user.split("\n\nFIXES")[0]
            system = DESCRIBE_FORCED if condition == "describe_forced" else DESCRIBE_ALLOWED
        yield system, user, label, clean_sample, extra, rows_shown


# ---------- replies ----------

def raw_json(text):
    text = re.sub(r"(?is)<think>.*?</think>", "", text or "")
    a, b = text.find("{"), text.rfind("}")
    try:
        obj = json.loads(text[a:b + 1]) if 0 <= a < b else None
    except ValueError:
        obj = None
    return obj if isinstance(obj, dict) else None


def truthy(v):
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return True if s in ("true", "yes", "1") else False if s in ("false", "no", "0") else None


def score(condition, label, text, clean_sample):
    """One record for one reply."""
    obj = raw_json(text)
    if condition.startswith("describe"):
        desc = str((obj or {}).get("description") or "").strip()
        if not desc:
            return {"status": "bad_reply", "said": "BAD_REPLY", "confidence": None}
        try:
            conf = max(0.0, min(100.0, float(obj.get("confidence"))))
        except (TypeError, ValueError):
            conf = None
        can = truthy(obj.get("can_tell")) if condition == "describe_allowed" else None
        return {"status": "ok", "said": "DECLINED" if can is False else "DESCRIBED",
                "declined": (can is False) if condition == "describe_allowed" else None,
                "doubt_wording": bool(DOUBT.search(desc)), "confidence": conf, "description": desc[:400]}
    rec = detect.score(label, detect.parse(text), clean_sample)
    if rec["status"] != "ok":
        return rec
    said_text = (rec.get("issue") or "") + " " + (rec.get("assumed") or "")
    held = rec["said"] in ("NEEDS_CONTEXT", "GARBAGE")
    if condition == "name_conflict":
        rec["mentioned"] = bool(NAME_MENTION.search(said_text) and CLASH.search(said_text))
        rec["noticed"] = held or rec["mentioned"]
    if condition.startswith("doc"):
        rec["mentioned"] = bool(DOC_MENTION.search(said_text) and CLASH.search(said_text))
        rec["flagged"] = held or rec["mentioned"]          # without being asked
        if condition.endswith("asked"):
            agrees = truthy(obj.get("doc_agrees")) if obj else None
            rec["said_doc_disagrees"] = None if agrees is None else not agrees
    return rec


def fake(condition, label, clean_sample, rep):
    rng = random.Random(f"{condition}|{label['table']}|{label['column']}|{rep}")
    if condition.startswith("describe"):
        obj = {"description": rng.choice(["Holds the " + label["column"] + ".", "Possibly the " + label["column"] + "; the unit is unclear."]),
               "confidence": rng.randint(50, 98)}
        if condition == "describe_allowed":
            obj["can_tell"] = rng.random() < 0.7
        return json.dumps(obj)
    obj = json.loads(detect.fake(label, clean_sample, rep))
    if condition.endswith("asked"):
        obj["doc_agrees"] = rng.random() < 0.6
    return json.dumps(obj)


def run_one(condition, a, model, label_name):
    out = Path(a.out or HERE / "runs" / label_name) / ("cond_" + condition)
    out.mkdir(parents=True, exist_ok=True)
    log = out / "attempts.jsonl"
    done = set()
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done.add((r["table"], r["column"], r["rep"]))
    todo = list(items(condition, a.variations, a.rows))
    if a.limit:
        todo = todo[:a.limit]
    with log.open("a", encoding="utf-8") as fh:
        for k, (system, user, label, clean_sample, extra, _rows) in enumerate(todo):
            for rep in range(a.reps):
                if (label["table"], label["column"], rep) in done:
                    continue
                if a.dry_run:
                    text = fake(condition, label, clean_sample, rep)
                else:
                    try:
                        text, _tokens = model.ask(system, user)
                    except Exception as e:
                        raise SystemExit("could not reach the model at " + a.base_url + ": " + str(e) +
                                         "\nFinished attempts are saved; run the same command to continue.")
                rec = score(condition, label, text, clean_sample)
                rec.update(extra)
                rec.update(condition=condition, table=label["table"], column=label["column"], case=label["case"], truth=label["verdict"],
                           settled_by=label["settled_by"], two_readings=bool(label["other_readings"]), rep=rep, model=label_name,
                           dry_run=a.dry_run, temperature=a.temperature)
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                if not a.quiet:
                    print(f"[{condition} {k + 1}/{len(todo)}] {label['case']:30} truth={label['verdict']:13} said={rec['said']:13} conf={rec['confidence']}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--condition", required=True, help="one of: all, " + ", ".join(CONDITIONS) + " (commas allowed)")
    ap.add_argument("--base-url", default="http://localhost:8000/v1")
    ap.add_argument("--model", default="")
    ap.add_argument("--api-key", default="")
    ap.add_argument("--variations", type=int, default=12)
    ap.add_argument("--rows", type=int, default=10, help="sample rows shown, except in rows5 and rows50")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--max-tokens", type=int, default=2500)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--no-logprobs", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="only the first N columns of each condition (for a timing check)")
    ap.add_argument("--out", default="", help="the model's run folder; default runs/<model>")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    if not a.dry_run and not a.model:
        ap.error("--model is required unless --dry-run")
    wanted = CONDITIONS if a.condition == "all" else a.condition.split(",")
    for c in wanted:
        if c not in CONDITIONS:
            ap.error("unknown condition: " + c)
    label_name = "dry-run" if a.dry_run else re.sub(r"[^A-Za-z0-9._-]+", "_", a.model)
    import run
    model = None if a.dry_run else run.Model(a.base_url, a.model, a.temperature, a.max_tokens, a.api_key, a.timeout, not a.no_logprobs)
    out = None
    for c in wanted:
        out = run_one(c, a, model, label_name)
    import score_conditions
    print("\nreport:", score_conditions.write(out.parent))


if __name__ == "__main__":
    main()
