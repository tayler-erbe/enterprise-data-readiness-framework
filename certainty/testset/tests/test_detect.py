"""Checks on the detector harness. Run from certainty/testset/:

    python -m unittest discover -s tests
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import build  # noqa: E402
import detect  # noqa: E402
import score_detect  # noqa: E402

TABLES, LABELS = build.build(variations=3)


def label_for(case):
    return next(l for l in LABELS if l["case"] == case)


class Sampling(unittest.TestCase):
    def test_the_sample_shows_rows_that_need_changing(self):
        for l in LABELS:
            if l["rows_changed"] == 0:
                continue
            t = TABLES[l["table"]]
            i = t["header"].index(l["column"])
            rows = detect.sample_rows(t, l, 10)
            self.assertEqual(len(rows), 10)
            self.assertEqual(len(set(rows)), 10)
            shown_changed = sum(str(t["raw"][r][i]) != str(t["clean"][r][i]) for r in rows)
            self.assertGreaterEqual(shown_changed, min(2, l["rows_changed"]), l["case"])

    def test_resolvable_slash_dates_show_the_row_that_settles_them(self):
        for l in [x for x in LABELS if x["case"] == "f_date_slash_order"]:
            t = TABLES[l["table"]]
            i = t["header"].index(l["column"])
            shown = [t["raw"][r][i] for r in detect.sample_rows(t, l, 10)]
            self.assertTrue(any(int(p) > 12 for v in shown for p in v.split("/")[:2]))

    def test_same_sample_every_time(self):
        l = LABELS[5]
        self.assertEqual(detect.sample_rows(TABLES[l["table"]], l, 10), detect.sample_rows(TABLES[l["table"]], l, 10))


class Prompt(unittest.TestCase):
    def test_the_prompt_never_shows_the_answer(self):
        for l in LABELS:
            text, clean = detect.prompt(l["table"], TABLES[l["table"]], l, 10)
            head = text.split("FIXES")[0]
            self.assertNotIn(l["case"], head)
            self.assertNotIn(l["issue"], head)
            self.assertIn("TARGET COLUMN: " + l["column"], head)
            self.assertEqual(len(clean), detect.SHOW_CLEANED)

    def test_every_fix_in_the_labels_is_offered(self):
        for l in LABELS:
            if l["fix"]:
                self.assertIn(l["fix"], detect.FIXES, l["case"])


class Scoring(unittest.TestCase):
    def test_value_matching(self):
        self.assertTrue(detect.same_value("172.70", 172.7))
        self.assertTrue(detect.same_value(None, ""))
        self.assertTrue(detect.same_value("null", ""))
        self.assertTrue(detect.same_value(" Bank Transfer ", "Bank Transfer"))
        self.assertFalse(detect.same_value("2026-03-04", "2026-04-03"))
        self.assertFalse(detect.same_value("", 5))

    def test_reply_parsing(self):
        r = detect.parse('<think>..</think>{"verdict": "needs context", "confidence": 55, "cleaned": "x"}')
        self.assertEqual((r["verdict"], r["confidence"], r["cleaned"]), ("NEEDS_CONTEXT", 55.0, []))
        self.assertIsNone(detect.parse('{"verdict": "MAYBE"}'))
        self.assertIsNone(detect.parse("ready"))

    def test_a_right_fix_with_right_values(self):
        l = label_for("f_leading_zero_lost")
        _, clean = detect.prompt(l["table"], TABLES[l["table"]], l, 10)
        s = detect.score(l, detect.parse(json.dumps({"verdict": "FIXABLE", "fix": "keep_as_text", "confidence": 90, "cleaned": clean})), clean)
        self.assertTrue(s["correct"] and s["fix_right"] and s["cleaned_right"])
        self.assertFalse(s["dangerous"] or s["over_cautious"])

    def test_saying_fixable_without_showing_the_fix_does_not_count_as_cleaned(self):
        l = label_for("f_leading_zero_lost")
        _, clean = detect.prompt(l["table"], TABLES[l["table"]], l, 10)
        s = detect.score(l, detect.parse(json.dumps({"verdict": "FIXABLE", "fix": "keep_as_text", "confidence": 90, "cleaned": []})), clean)
        self.assertTrue(s["correct"])
        self.assertFalse(s["cleaned_right"])

    def test_guessing_on_a_column_that_needs_context_is_dangerous(self):
        l = label_for("n_amount_cents_or_dollars")
        _, clean = detect.prompt(l["table"], TABLES[l["table"]], l, 10)
        s = detect.score(l, detect.parse(json.dumps({"verdict": "FIXABLE", "fix": "scale_number", "confidence": 95, "assumed": "values are cents", "cleaned": clean})), clean)
        self.assertTrue(s["dangerous"] and s["guessed_right"] and s["stated_assumption"])
        self.assertFalse(s["correct"])

    def test_holding_back_a_good_column_is_over_caution(self):
        s = detect.score(label_for("r_email"), detect.parse('{"verdict": "GARBAGE", "confidence": 60}'), [])
        self.assertTrue(s["over_cautious"])
        self.assertFalse(s["dangerous"])

    def test_report(self):
        rows = []
        for truth, said, conf in [("READY", "READY", 90), ("NEEDS_CONTEXT", "FIXABLE", 95), ("NEEDS_CONTEXT", "NEEDS_CONTEXT", 60), ("GARBAGE", "GARBAGE", 80)]:
            usable = lambda v: v in ("READY", "FIXABLE")
            rows.append({"status": "ok", "said": said, "correct": said == truth, "dangerous": not usable(truth) and usable(said),
                         "over_cautious": usable(truth) and not usable(said), "fix_right": None, "cleaned_right": None, "guessed_right": None,
                         "stated_assumption": False, "confidence": conf, "issue": "", "assumed": "", "table": "t", "column": truth + said,
                         "case": "c_" + truth, "truth": truth, "settled_by": "", "two_readings": False, "rep": 0, "model": "m", "dry_run": False, "rows_shown": 10})
        h = score_detect.headline(rows)
        self.assertAlmostEqual(h["verdict_right"], 0.75)
        self.assertAlmostEqual(h["dangerous"], 1 / 3)
        self.assertAlmostEqual(h["dangerous_and_confident"], 1 / 3)
        self.assertEqual(h["over_cautious"], 0)
        with tempfile.TemporaryDirectory() as d:
            Path(d, "attempts.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            text = score_detect.write(d).read_text(encoding="utf-8")
        self.assertIn("| NEEDS_CONTEXT | 0% | 50% | 50% | 0% | 0% | 2 |", text)


if __name__ == "__main__":
    unittest.main()
