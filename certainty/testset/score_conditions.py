"""Turn the condition runs for one model into conditions_report.md.

    python score_conditions.py runs/<model>

Reads runs/<model>/attempts.jsonl (the base test, if it has been run) and every
runs/<model>/cond_*/attempts.jsonl. Each section states, before the numbers, the
result that would count against the detector idea.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

from report import mean, num, pct  # noqa: E402

VERDICTS = ["READY", "FIXABLE", "NEEDS_CONTEXT", "GARBAGE"]
USABLE = ("READY", "FIXABLE")


def read(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []


def share(rows, test):
    return sum(bool(test(r)) for r in rows) / len(rows) if rows else None


def ok(rows):
    return [r for r in rows if r["status"] == "ok"]


def called_usable(r):
    return r["said"] in USABLE


def verdict_line(name, rows):
    good = ok(rows)
    need = [r for r in good if r["truth"] == "NEEDS_CONTEXT"]
    fine = [r for r in good if r["truth"] in USABLE]
    return (f"| {name} | {len({(r['table'], r['column']) for r in rows})} | {len(rows)} | {pct(share(rows, lambda r: r.get('correct')))} | "
            f"{pct(share(need, called_usable))} | {num(mean([r['confidence'] for r in need if called_usable(r)]), 0)} | "
            f"{pct(share(fine, lambda r: not called_usable(r)))} | {pct(share(rows, lambda r: r['status'] != 'ok'))} |")


def write(folder):
    folder = Path(folder)
    base = [r for r in read(folder / "attempts.jsonl") if r["column"] != "(whole file)"]
    cond = {p.parent.name[5:]: read(p) for p in sorted(folder.glob("cond_*/attempts.jsonl"))}
    every = base + [r for rows in cond.values() for r in rows]
    L = ["# Reported failures, tested: " + (every[0]["model"] if every else folder.name), ""]
    if any(r.get("dry_run") for r in every):
        L += ["**DRY RUN. The replies were made up by the script to test the pipeline. Nothing below is a finding.**", ""]
    L += ["Each condition changes one thing about what the model sees. The base test shows ten sample rows and nothing else.", ""]

    head = ["| Condition | Columns | Attempts | Verdict right | Needs-context called usable | Mean certainty when it did | Usable held back | Unreadable |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]

    # ----- sample size -----
    sized = [(n, cond[c]) for n, c in (("5 rows", "rows5"),) if c in cond]
    if base:
        sized.append(("10 rows (base)", base))
    sized += [(n, cond[c]) for n, c in (("50 rows", "rows50"), ("10 rows plus a whole-column profile", "profile")) if c in cond]
    if len(sized) > 1 or (sized and not base):
        L += ["## More rows, or a profile of the whole column", "",
              "**Counts against the idea if** more rows or a profile sharply cut the share of needs-context columns called usable. "
              "Then it is a sampling problem that any platform solves by reading more of the table.", ""] + head
        L += [verdict_line(n, rows) for n, rows in sized] + [""]

    # ----- documentation -----
    docs = [c for c in ("doc_agree", "doc_conflict", "doc_agree_asked", "doc_conflict_asked") if c in cond]
    if docs:
        L += ["## Documentation that disagrees with the data", "",
              "The model is given a data dictionary entry for the column. In the conflict rows the entry is contradicted by the rows it is shown. "
              "The entries that agree are the control: a model that flags everything would score well on conflicts alone.", "",
              "**Counts against the idea if** the model flags most contradicted entries without being asked, and few of the true ones.", "",
              "| Condition | Columns | Attempts | Flagged without being asked | Held the column back | Mentioned the entry clashing | Said the entry disagrees, when asked | Cleaned values still follow the data |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        names = {"doc_agree": "Entry is true", "doc_conflict": "Entry is contradicted", "doc_agree_asked": "Entry is true, asked", "doc_conflict_asked": "Entry is contradicted, asked"}
        for c in docs:
            rows = ok(cond[c])
            asked = [r for r in rows if r.get("said_doc_disagrees") is not None]
            L.append(f"| {names[c]} | {len({(r['table'], r['column']) for r in rows})} | {len(cond[c])} | {pct(share(rows, lambda r: r.get('flagged')))} | "
                     f"{pct(share(rows, lambda r: not called_usable(r)))} | {pct(share(rows, lambda r: r.get('mentioned')))} | "
                     f"{pct(share(asked, lambda r: r['said_doc_disagrees'])) if asked else ''} | "
                     f"{pct(share([r for r in rows if r.get('cleaned_right') is not None], lambda r: r['cleaned_right']))} |")
        L += ["", "\"Mentioned the entry clashing\" is a keyword match on the model's own words. It will miss some mentions and catch some that are not. "
              "\"Held the column back\" and the asked answer do not depend on it.", ""]
        if "doc_conflict" in cond:
            by = defaultdict(list)
            for r in ok(cond["doc_conflict"]):
                by[r["case"]].append(r)
            L += ["| Case, entry contradicted | Entry given | Flagged without being asked |", "| --- | --- | ---: |"]
            L += [f"| {c} | {rs[0].get('doc', '')} | {pct(share(rs, lambda r: r.get('flagged')))} |" for c, rs in sorted(by.items())] + [""]

    # ----- names -----
    if any(c in cond for c in ("name_conflict", "name_two", "name_clear")):
        L += ["## Column names that mislead", ""]
    if "name_conflict" in cond:
        rows = ok(cond["name_conflict"])
        L += ["The target column is renamed to something its values contradict (dates called `unit_price`, emails called `phone_number`).", "",
              "**Counts against the idea if** the model notices the clash in most cases.", "",
              "| Measure | Value |", "| --- | ---: |",
              f"| Columns | {len({(r['table'], r['column']) for r in rows})} |",
              f"| Noticed: held the column back, or said the name does not fit | {pct(share(rows, lambda r: r.get('noticed')))} |",
              f"| Held the column back | {pct(share(rows, lambda r: not called_usable(r)))} |",
              f"| Called it usable and did not mention the name | {pct(share(rows, lambda r: called_usable(r) and not r.get('mentioned')))} |",
              f"| Mean stated certainty when it called it usable and did not mention the name | "
              f"{num(mean([r['confidence'] for r in rows if called_usable(r) and not r.get('mentioned')]), 0)} |", "",
              "Whether a reply \"said the name does not fit\" is a keyword match on the model's own words; treat the first line as approximate.", ""]
    if "name_two" in cond or "name_clear" in cond:
        L += ["New columns whose name fits two meanings (`sales`: units or money?), and the same values under a name that fits one (`units_sold`).", "",
              "**Counts against the idea if** the model holds back most two-meaning columns and passes most of the plainly named ones.", "",
              "| Name | Columns | Attempts | Called usable | Held back | Mean stated certainty |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
        for title, c in (("Fits two meanings", "name_two"), ("Fits one meaning (control)", "name_clear")):
            rows = ok(cond.get(c, []))
            if rows:
                L.append(f"| {title} | {len({(r['table'], r['column']) for r in rows})} | {len(cond[c])} | {pct(share(rows, called_usable))} | "
                         f"{pct(share(rows, lambda r: not called_usable(r)))} | {num(mean([r['confidence'] for r in rows]), 0)} |")
        L.append("")

    # ----- descriptions -----
    if "describe_forced" in cond or "describe_allowed" in cond:
        L += ["## Descriptions: can it say \"can't tell\"?", "",
              "The model writes a description of the column, as documentation generators do. Forced: it must write one. "
              "Allowed: it may say the table does not show what the column means.", "",
              "**Counts against the idea if** the model, when allowed, declines on most needs-context columns and on few ready ones.", "",
              "| True verdict | Columns | Forced: wording of doubt | Forced: mean certainty | Allowed: declined | Allowed: wording of doubt | Allowed: mean certainty when it described |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        forced, allowed = ok(cond.get("describe_forced", [])), ok(cond.get("describe_allowed", []))
        for v in VERDICTS:
            f, a = [r for r in forced if r["truth"] == v], [r for r in allowed if r["truth"] == v]
            if f or a:
                L.append(f"| {v} | {len({(r['table'], r['column']) for r in f + a})} | {pct(share(f, lambda r: r.get('doubt_wording')))} | "
                         f"{num(mean([r['confidence'] for r in f]), 0)} | {pct(share(a, lambda r: r.get('declined')))} | "
                         f"{pct(share(a, lambda r: r.get('doubt_wording')))} | {num(mean([r['confidence'] for r in a if not r.get('declined')]), 0)} |")
        L += ["", "Wording of doubt is a keyword list (\"unclear\", \"may be\", \"possibly\" and so on). It counts a hedge about one detail as doubt "
              "and misses doubt put another way. Whether a description is RIGHT is not scored here; the text is kept in `attempts.jsonl` for a reader or a judge.", ""]

    L += ["## Limits", "",
          "- Generated tables, one problem per column, about eight columns wide.",
          "- The contradicted entries and misleading names are plain ones. Subtle conflicts would be harder to notice; these give the easy end.",
          "- Calling a renamed column NEEDS_CONTEXT is this test's choice: when a name and its values disagree, only the owner can say which is wrong.",
          "- A model asked directly whether an entry agrees is being pointed at the problem. The unasked rows are the fair measure of noticing.", ""]
    path = folder / "conditions_report.md"
    path.write_text("\n".join(L), encoding="utf-8")
    return path


if __name__ == "__main__":
    print(write(sys.argv[1]))
