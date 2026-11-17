"""Checks on the extra test conditions. Standard library only; no model is used."""
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent))

import build  # noqa: E402
import conditions as cond  # noqa: E402
import detect  # noqa: E402

VARIATIONS = 12


class Conditions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables, cls.labels = build.build(variations=VARIATIONS)
        cls.items = {c: list(cond.items(c, VARIATIONS)) for c in cond.CONDITIONS}

    def test_base_prompt_is_unchanged(self):
        """A condition must differ from the base test only in the one thing it changes."""
        label = self.labels[0]
        table = self.tables[label["table"]]
        want, want_clean = detect.prompt(label["table"], table, label, 10)
        got, got_clean = cond.make_prompt(label["table"], table, label["column"], detect.sample_rows(table, label, 10))
        self.assertEqual(want, got)
        self.assertEqual(want_clean, got_clean)

    def test_row_counts(self):
        for c, n in (("rows5", 5), ("rows50", 50), ("profile", 10)):
            self.assertEqual(len(self.items[c]), len(self.labels))
            self.assertTrue(all(len(rows) == n for *_, rows in self.items[c]), c)

    def test_profile_adds_only_the_profile(self):
        _, user, label, _, _, rows = self.items["profile"][0]
        base, _ = cond.make_prompt(label["table"], self.tables[label["table"]], label["column"], rows)
        self.assertIn("PROFILE OF THE TARGET COLUMN", user)
        self.assertEqual(user.split("\n\nPROFILE")[0] + "\n\nFIXES" + user.split("\n\nFIXES")[1], base)

    def test_every_contradicted_entry_is_refuted_by_the_rows_shown(self):
        seen = set()
        for _, user, label, _, extra, rows in self.items["doc_conflict"]:
            seen.add(label["case"])
            self.assertFalse(extra["doc_true"])
            self.assertIn("DATA DICTIONARY ENTRY for " + label["column"] + ": " + extra["doc"], user)
            self.assertTrue(cond.doc_refuted(label, self.tables[label["table"]], rows), label["table"] + "." + label["column"])
        self.assertEqual(seen, set(cond.DOCS))
        self.assertEqual(len(self.items["doc_conflict"]), len(cond.DOCS) * VARIATIONS)

    def test_true_and_contradicted_entries_differ_and_cover_the_same_columns(self):
        agree = {(l["table"], l["column"]): e["doc"] for _, _, l, _, e, _ in self.items["doc_agree"]}
        clash = {(l["table"], l["column"]): e["doc"] for _, _, l, _, e, _ in self.items["doc_conflict"]}
        self.assertEqual(set(agree), set(clash))
        self.assertTrue(all(agree[k] != clash[k] for k in agree))

    def test_only_usable_columns_get_entries(self):
        for _, _, label, _, _, _ in self.items["doc_agree"]:
            self.assertIn(label["verdict"], ("READY", "FIXABLE"))

    def test_asked_prompt_adds_the_question(self):
        system = self.items["doc_conflict_asked"][0][0]
        self.assertIn("doc_agrees", system)
        self.assertNotIn("doc_agrees", self.items["doc_conflict"][0][0])
        self.assertNotIn("There is no data dictionary", system)

    def test_every_misleading_name_is_refuted_by_the_rows_shown(self):
        seen = set()
        for _, user, label, _, extra, rows in self.items["name_conflict"]:
            seen.add(label["case"])
            table = self.tables[label["table"]]
            i = table["header"].index(label["column"])
            refutes = cond.NAME_CONFLICT[label["case"]][1]
            self.assertTrue(any(refutes(table["raw"][r][i]) for r in rows), label["table"] + "." + label["column"])
            self.assertIn("TARGET COLUMN: " + extra["shown_as"], user)
            self.assertNotIn(label["column"], user.split("SAMPLE")[1].split("\n")[1].split(","))
            self.assertEqual(label["verdict"], "NEEDS_CONTEXT")
            self.assertIn(extra["base_truth"], ("READY", "FIXABLE"))
        self.assertEqual(seen, set(cond.NAME_CONFLICT))

    def test_two_meaning_and_clear_names_hold_the_same_values(self):
        two_t, two_l = cond.name_tables(VARIATIONS, clear=False)
        clear_t, clear_l = cond.name_tables(VARIATIONS, clear=True)
        self.assertEqual(len(two_l), len(cond.TWO_MEANING) * VARIATIONS)
        for a, b in zip(two_l, clear_l):
            self.assertEqual(a["table"], b["table"])
            self.assertNotEqual(a["column"], b["column"])
            self.assertEqual(two_t[a["table"]]["raw"], clear_t[b["table"]]["raw"])
            self.assertEqual((a["verdict"], b["verdict"]), ("NEEDS_CONTEXT", "READY"))
            self.assertTrue(a["other_readings"])

    def test_describe_prompts(self):
        system, user, *_ = self.items["describe_forced"][0]
        self.assertNotIn("can_tell", system)
        self.assertNotIn("FIXES", user)
        self.assertIn("can_tell", self.items["describe_allowed"][0][0])
        self.assertEqual(len(self.items["describe_forced"]), len(self.labels))

    def test_scoring(self):
        label = dict(self.labels[0], verdict="READY")
        reply = lambda **kw: json.dumps(dict({"verdict": "READY", "fix": "", "issue": "", "assumed": "", "confidence": 90, "cleaned": []}, **kw))
        r = cond.score("doc_conflict_asked", label, reply(doc_agrees=False), [])
        self.assertTrue(r["said_doc_disagrees"])
        self.assertFalse(r["flagged"])
        r = cond.score("doc_conflict", label, reply(issue="The dictionary says euros but the values show US$."), [])
        self.assertTrue(r["flagged"])
        r = cond.score("doc_conflict", label, reply(verdict="NEEDS_CONTEXT"), [])
        self.assertTrue(r["flagged"])
        r = cond.score("name_conflict", dict(label, verdict="NEEDS_CONTEXT"), reply(issue="Column name says price but values are dates."), [])
        self.assertTrue(r["noticed"] and r["dangerous"])
        r = cond.score("name_conflict", dict(label, verdict="NEEDS_CONTEXT"), reply(), [])
        self.assertFalse(r["noticed"])
        r = cond.score("describe_allowed", label, json.dumps({"description": "Unclear; could be dollars or cents.", "confidence": 40, "can_tell": False}), [])
        self.assertEqual((r["said"], r["declined"], r["doubt_wording"]), ("DECLINED", True, True))
        r = cond.score("describe_forced", label, json.dumps({"description": "Order total in US dollars.", "confidence": 95}), [])
        self.assertEqual((r["said"], r["declined"], r["doubt_wording"]), ("DESCRIBED", None, False))
        self.assertEqual(cond.score("describe_forced", label, "no json here", [])["status"], "bad_reply")
        self.assertEqual(cond.score("rows5", label, "no json here", [])["status"], "bad_reply")

    def test_dry_run_writes_a_report(self):
        import argparse
        import tempfile
        import score_conditions
        with tempfile.TemporaryDirectory() as tmp:
            a = argparse.Namespace(out=tmp, variations=1, rows=10, limit=0, reps=2, dry_run=True, base_url="", temperature=0.7, quiet=True)
            for c in cond.CONDITIONS:
                cond.run_one(c, a, None, "dry-run")
            first = (Path(tmp) / "cond_rows5" / "attempts.jsonl").read_text(encoding="utf-8")
            cond.run_one("rows5", a, None, "dry-run")           # a second run adds nothing
            self.assertEqual(first, (Path(tmp) / "cond_rows5" / "attempts.jsonl").read_text(encoding="utf-8"))
            text = score_conditions.write(tmp).read_text(encoding="utf-8")
            for part in ("DRY RUN", "More rows", "Documentation that disagrees", "Column names that mislead", "can't tell"):
                self.assertIn(part, text)


if __name__ == "__main__":
    unittest.main()
