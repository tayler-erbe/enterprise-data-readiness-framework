"""Checks on the column meaning test. Run from certainty/columns/:

    python -m unittest discover -s tests
"""
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import ask  # noqa: E402
import make_tables as mt  # noqa: E402
import score_columns  # noqa: E402

INSTANCES = [mt.build(i) for i in range(6)]


def column(tables, table, name):
    cols = tables[table]["columns"]
    i = [c["name"] for c in cols].index(name)
    return i, cols[i]


class Generator(unittest.TestCase):
    def test_same_seed_gives_the_same_tables(self):
        a, fa = mt.build(2)
        b, fb = mt.build(2)
        self.assertEqual(json.dumps(a), json.dumps(b))
        self.assertEqual(fa, fb)

    def test_shape(self):
        tables, _ = INSTANCES[0]
        self.assertEqual(len(tables), 6)
        self.assertEqual(sum(len(t["columns"]) for t in tables.values()), 53)
        for t in tables.values():
            self.assertEqual(len(t["raw"]), 200)
            self.assertEqual(len(t["clean"]), 200)
            for r in t["raw"] + t["clean"]:
                self.assertEqual(len(r), len(t["columns"]))

    def test_every_label_is_on_the_lists_the_model_is_shown(self):
        for tables, _ in INSTANCES:
            for t in tables.values():
                for c in t["columns"]:
                    self.assertIn(c["truth"], mt.MEANINGS)
                    self.assertIn(c["truth"], c["candidates"])
                    self.assertIn(c["settled_by"], mt.SETTLED_BY)
                    for x in c["candidates"]:
                        self.assertIn(x, mt.MEANINGS)
                    for op in c["ops"]:
                        self.assertIn(op, mt.OPS)

    def test_coin_flips_land_both_ways(self):
        seen = {}
        for _, flips in INSTANCES + [mt.build(i) for i in range(6, 30)]:
            for k, v in flips.items():
                seen.setdefault(k, set()).add(v)
        self.assertEqual(len(seen), 10)
        for k, vs in seen.items():
            self.assertEqual(len(vs), 2, k)

    def test_files_are_written(self):
        with tempfile.TemporaryDirectory() as d:
            mt.write(d, 2, rows=20)
            key = json.loads(Path(d, "instance1", "key.json").read_text())
            self.assertEqual(len(key["tables"]), 6)
            self.assertTrue(Path(d, "instance0", "raw", "members.csv").exists())
            self.assertTrue(Path(d, "instance0", "clean", "members.csv").exists())


class AnswerKey(unittest.TestCase):
    """The clean table really is the raw table, correctly prepared."""

    def test_dates_parse_to_the_clean_date_under_the_true_format(self):
        for tables, _ in INSTANCES:
            for table, name in [("members", "joined"), ("payments", "paid_on")]:
                i, c = column(tables, table, name)
                fmt = "%d/%m/%Y" if c["truth"] == "date_day_first" else "%m/%d/%Y"
                for raw, clean in zip(tables[table]["raw"], tables[table]["clean"]):
                    self.assertEqual(dt.datetime.strptime(raw[i], fmt).date().isoformat(), clean[i])

    def test_height_text_converts_to_centimetres(self):
        tables, _ = INSTANCES[0]
        i, _ = column(tables, "members", "height")
        for raw, clean in zip(tables["members"]["raw"], tables["members"]["clean"]):
            feet, inches = raw[i].rstrip('"').split("'")
            self.assertAlmostEqual((int(feet) * 12 + int(inches)) * 2.54, clean[i], places=1)

    def test_zip_codes_keep_their_leading_zeros(self):
        tables, _ = INSTANCES[0]
        i, _ = column(tables, "members", "zip")
        zips = {r[i] for r in tables["members"]["raw"]}
        self.assertTrue(any(z.startswith("0") for z in zips))
        self.assertTrue(all(len(z) == 5 for z in zips))

    def test_missing_marker_becomes_blank(self):
        tables, _ = INSTANCES[0]
        i, _ = column(tables, "shift_events", "score")
        pairs = list(zip(tables["shift_events"]["raw"], tables["shift_events"]["clean"]))
        self.assertTrue(any(r[i] == -1 for r, _ in pairs))
        for r, c in pairs:
            self.assertEqual(c[i], "" if r[i] == -1 else r[i])

    def test_state_variants_collapse_to_one_name(self):
        tables, _ = INSTANCES[0]
        i, _ = column(tables, "shift_events", "site_state")
        self.assertGreater(len({r[i] for r in tables["shift_events"]["raw"]}), 10)
        self.assertEqual(len({r[i] for r in tables["shift_events"]["clean"]}), 5)


class Evidence(unittest.TestCase):
    """Where the key says the other columns settle a meaning, they really do. Where it says nothing does, nothing does."""

    def test_quantity_is_settled_by_the_line_total(self):
        for tables, _ in INSTANCES:
            t = tables["order_lines"]
            i, c = column(tables, "order_lines", "qty")
            names = [x["name"] for x in t["columns"]]
            p, tot = names.index("unit_price"), names.index("line_total")
            per = 1 if c["truth"] == "quantity_units" else 6
            for r in t["raw"]:
                self.assertAlmostEqual(r[i] * per * r[p], r[tot], places=2)

    def test_weekday_number_is_settled_by_the_date(self):
        for tables, _ in INSTANCES:
            t = tables["health_screening"]
            i, c = column(tables, "health_screening", "visit_dow")
            d = [x["name"] for x in t["columns"]].index("visit_date")
            for r in t["raw"]:
                w = dt.date.fromisoformat(r[d]).isoweekday()
                self.assertEqual(r[i], w if c["truth"] == "weekday_number_mon1" else w % 7 + 1)

    def test_duration_is_settled_by_start_and_end(self):
        for tables, _ in INSTANCES:
            t = tables["shift_events"]
            i, c = column(tables, "shift_events", "duration")
            for r in t["raw"]:
                self.assertEqual(r[2] - r[1], r[i] * (60 if c["truth"] == "duration_minutes" else 1))

    def test_unsettleable_columns_look_the_same_whichever_way_the_coin_fell(self):
        ranges = {}
        for tables, flips in INSTANCES + [mt.build(i) for i in range(6, 30)]:
            for table, name in [("products", "price"), ("payments", "amount")]:
                i, c = column(tables, table, name)
                vals = [r[i] for r in tables[table]["raw"]]
                ranges.setdefault((table, name, c["truth"]), []).append((min(vals), max(vals)))
            i, _ = column(tables, "payments", "region")
            self.assertTrue({r[i] for r in tables["payments"]["raw"]} <= set(mt.BOTH_STATE_AND_COUNTRY))
            i, _ = column(tables, "members", "newsletter")
            self.assertEqual({r[i] for r in tables["members"]["raw"]}, {1, 2})
        for (table, name, truth), rs in ranges.items():
            lo = 2 if name == "price" else 5
            hi = 80 if name == "price" else 400
            for a, b in rs:
                self.assertTrue(lo <= a and b <= hi, (table, name, truth))

    def test_what_each_kind_of_evidence_can_settle(self):
        c = lambda s: {"settled_by": s, "candidates": ["a", "b"]}
        self.assertTrue(ask.determinable(c("values"), "alone5", []))
        self.assertTrue(ask.determinable(c("name"), "alone5", []))
        self.assertFalse(ask.determinable(c("name"), "cryptic5", []))
        self.assertTrue(ask.determinable(c("neighbours"), "cryptic5", []))
        self.assertFalse(ask.determinable(c("neighbours"), "alone5", []))
        self.assertFalse(ask.determinable(c("nothing"), "full50", []))
        self.assertIsNone(ask.determinable(c("judgement"), "full5", []))
        self.assertFalse(ask.determinable(c("day_gt_12"), "full5", ["03/04/2026", "11/12/2026"]))
        self.assertTrue(ask.determinable(c("day_gt_12"), "full5", ["03/04/2026", "25/12/2026"]))
        self.assertTrue(ask.determinable(c("day_gt_12"), "full5", ["12/25/2026"]))
        self.assertEqual(ask.ceiling(c("nothing"), False), 0.5)
        self.assertIsNone(ask.ceiling(c("nothing"), True))
        self.assertIsNone(ask.ceiling(c("name"), False))


class Prompt(unittest.TestCase):
    tables, _ = INSTANCES[0]

    def test_alone_shows_only_the_target_column(self):
        i, _ = column(self.tables, "health_screening", "v3")
        text, shown = ask.prompt("health_screening", self.tables["health_screening"], i, "alone5", 0)
        head = text.split("MEANINGS")[0]
        self.assertNotIn("weight", head)
        self.assertNotIn("eye", head)
        self.assertEqual(len(shown), 5)

    def test_cryptic_hides_only_the_target_name(self):
        i, c = column(self.tables, "members", "sex")
        text, _ = ask.prompt("members", self.tables["members"], i, "cryptic5", 0)
        head = text.split("MEANINGS")[0]
        self.assertNotIn("sex ", head)
        self.assertIn("TARGET COLUMN: " + c["cryptic"], head)
        self.assertIn("birth_date", head)

    def test_row_counts(self):
        i, _ = column(self.tables, "members", "joined")
        for cond, n in [("full5", 5), ("full50", 50)]:
            text, shown = ask.prompt("members", self.tables["members"], i, cond, 0)
            self.assertEqual(len(shown), n)
            self.assertIn(f"SAMPLE ({n} random rows)", text)

    def test_the_prompt_never_states_the_answer(self):
        for tname, t in self.tables.items():
            for i, c in enumerate(t["columns"]):
                text, _ = ask.prompt(tname, t, i, "full5", 0)
                head = text.split("MEANINGS")[0]
                if c["truth"] != c["name"]:
                    self.assertNotIn(c["truth"], head)
                self.assertNotIn("settled", head)


class Scoring(unittest.TestCase):
    col = {"truth": "money_usd", "candidates": ["money_usd", "money_cad"], "ops": []}

    def test_reply_parsing(self):
        r = ask.parse('<think>x</think>{"meaning": "money_usd", "preparation": ["none"], "confidence": 120, "alternatives": ["money_cad", 3]}')
        self.assertEqual((r["meaning"], r["preparation"], r["confidence"], r["alternatives"]), ("money_usd", [], 100.0, ["money_cad"]))
        self.assertIsNone(ask.parse("no json here"))
        self.assertIsNone(ask.parse('{"confidence": 50}'))

    def test_right_and_named_the_other_reading(self):
        s = ask.score(self.col, ask.parse('{"meaning": "money_usd", "confidence": 50, "alternatives": ["money_cad"], "preparation": []}'))
        self.assertTrue(s["correct"] and s["named_alternative"] and s["preparation_right"])

    def test_wrong_but_in_the_plausible_set(self):
        s = ask.score(self.col, ask.parse('{"meaning": "money_cad", "confidence": 95, "alternatives": [], "preparation": ["scale_number"]}'))
        self.assertFalse(s["correct"])
        self.assertTrue(s["in_candidates"])
        self.assertFalse(s["named_alternative"])
        self.assertFalse(s["preparation_right"])

    def test_bad_reply(self):
        self.assertEqual(ask.score(self.col, None)["status"], "bad_reply")

    def test_report_is_written(self):
        rows = []
        for cond, settled, ceil in [("full5", True, None), ("alone5", False, 0.5)]:
            for rep in range(2):
                rows.append({"status": "ok", "answer": "money_usd", "correct": rep == 0, "confidence": 90, "listed_any_alternative": False,
                             "named_alternative": False, "preparation_right": True, "instance": 0, "table": "t", "column": "c",
                             "condition": cond, "rep": rep, "truth": "money_usd", "settled_by": "nothing", "determinable": settled,
                             "ceiling": ceil, "model": "m", "dry_run": False})
        with tempfile.TemporaryDirectory() as d:
            Path(d, "attempts.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            text = score_columns.write(d).read_text(encoding="utf-8")
        self.assertIn("Coin-flip columns", text)
        self.assertIn("| t.c | alone5 | 50% | 50% | 90% | 100% | 0% |", text)


if __name__ == "__main__":
    unittest.main()
