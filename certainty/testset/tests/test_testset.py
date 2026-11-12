"""Checks that the test set can be trusted. Run from certainty/testset/:

    python -m unittest discover -s tests

The answer key is checked three ways:
1. For every FIXABLE case, a separate fixer turns the raw column into the clean one, exactly.
2. For every NEEDS_CONTEXT case with competing readings, the raw column is identical whichever reading is true.
3. Every READY and GARBAGE case has the property it claims.
"""
import csv
import random
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import build  # noqa: E402
from cases import CASES, DOMAINS, FIXABLE, GARBAGE, NEEDS_CONTEXT, READY  # noqa: E402

SEEDS = range(25)
N = 120


def make(cid, seed, truth=None, domain="retail"):
    return CASES[cid]["make"](random.Random(f"t|{seed}|{cid}"), N, DOMAINS[domain], truth) if truth else \
        CASES[cid]["make"](random.Random(f"t|{seed}|{cid}"), N, DOMAINS[domain])


class Catalogue(unittest.TestCase):
    def test_size_and_spread(self):
        by = Counter(c["verdict"] for c in CASES.values())
        self.assertEqual(sum(by.values()), 60)
        self.assertEqual(by, {READY: 11, FIXABLE: 27, NEEDS_CONTEXT: 16, GARBAGE: 6})

    def test_every_case_is_fully_described(self):
        for cid, c in CASES.items():
            self.assertTrue(c["issue"].endswith("."), cid)
            self.assertTrue(c["meaning"], cid)
            self.assertEqual(c["verdict"] == FIXABLE, c["fix"] is not None, cid)
            if c["verdict"] == FIXABLE:
                self.assertTrue(c["op"], cid)

    def test_columns_are_complete(self):
        for cid in CASES:
            for dom in DOMAINS:
                col = make(cid, 0, domain=dom)
                self.assertEqual(len(col["raw"]), N, cid)
                self.assertEqual(len(col["clean"]), N, cid)
                for h in col.get("helpers", {}).values():
                    self.assertEqual(len(h), N, cid)

    def test_same_seed_same_column(self):
        for cid in CASES:
            self.assertEqual(make(cid, 3), make(cid, 3), cid)


class AnswerKey(unittest.TestCase):
    def test_ready_columns_need_nothing(self):
        for cid, c in CASES.items():
            if c["verdict"] == READY:
                for s in SEEDS:
                    col = make(cid, s)
                    self.assertEqual(col["raw"], col["clean"], cid)

    def test_a_separate_fixer_reproduces_every_clean_column(self):
        for cid, c in CASES.items():
            if c["verdict"] != FIXABLE:
                continue
            for s in SEEDS:
                for dom in DOMAINS:
                    col = make(cid, s, domain=dom)
                    fixed = c["fix"](col["raw"], col.get("helpers", {}))
                    self.assertEqual(fixed, col["clean"], f"{cid} seed {s} {dom}")

    def test_fixable_columns_really_are_dirty(self):
        for cid, c in CASES.items():
            if c["verdict"] == FIXABLE:
                col = make(cid, 1)
                changed = sum(str(a) != str(b) for a, b in zip(col["raw"], col["clean"]))
                self.assertGreaterEqual(changed, 2, cid)

    def test_competing_readings_give_identical_raw_values(self):
        """The proof that these columns cannot be settled from their values."""
        checked = 0
        for cid, c in CASES.items():
            if c["verdict"] != NEEDS_CONTEXT or not c["alts"]:
                continue
            for s in SEEDS:
                cols = [make(cid, s, truth=a) for a in c["alts"]]
                for other in cols[1:]:
                    self.assertEqual(other["raw"], cols[0]["raw"], cid)
                    self.assertEqual(other["name"], cols[0]["name"], cid)
                self.assertEqual([x["truth"] for x in cols], c["alts"], cid)
            checked += 1
        self.assertEqual(checked, 11)

    def test_competing_readings_lead_to_different_clean_values_where_a_fix_exists(self):
        for cid, c in CASES.items():
            if c["verdict"] == NEEDS_CONTEXT and c["alts"] and c["op"] and c["op"] != "decode_values":
                a, b = (make(cid, 2, truth=t) for t in c["alts"][:2])
                self.assertNotEqual(a["clean"], b["clean"], cid)

    def test_both_readings_turn_up(self):
        for cid, c in CASES.items():
            if c["alts"]:
                seen = {make(cid, s).get("truth") for s in range(40)}
                self.assertEqual(seen, set(c["alts"]), cid)

    def test_resolvable_slash_dates_always_have_a_day_above_12(self):
        for s in SEEDS:
            col = make("f_date_slash_order", s)
            i = 0 if col["truth"] == "day_first" else 1
            self.assertTrue(any(int(v.split("/")[i]) > 12 for v in col["raw"]))

    def test_unresolvable_slash_dates_never_do(self):
        for s in SEEDS:
            for v in make("n_date_slash_unresolvable", s)["raw"]:
                a, b, _ = v.split("/")
                self.assertTrue(int(a) <= 12 and int(b) <= 12)

    def test_garbage_columns_are_what_they_claim(self):
        for s in SEEDS:
            self.assertGreaterEqual(make("g_mostly_missing", s)["raw"].count(""), N * 0.9)
            self.assertEqual(len(set(make("g_constant", s)["raw"])), 1)
            self.assertEqual(len(set(make("g_random_noise", s)["raw"])), N)
            self.assertTrue(all(len(v) == 10 for v in make("g_truncated", s)["raw"]))
            mixed = make("g_wrong_values_mixed_in", s)["raw"]
            self.assertGreaterEqual(sum(isinstance(v, str) for v in mixed), N * 0.3)
            filler = make("g_placeholder_text", s)["raw"]
            self.assertGreaterEqual(sum(v in ("test", "asdf", "xxx", "TBD", "todo", ".") for v in filler), N * 0.5)

    def test_no_control_characters_that_would_break_a_csv(self):
        for cid in CASES:
            for v in make(cid, 0)["raw"]:
                self.assertFalse(any(ord(ch) < 32 or 127 <= ord(ch) < 160 for ch in str(v)), cid)


class CrossColumn(unittest.TestCase):
    """The conflicts are really there, and really cannot be settled."""

    def test_conflicts_exist_in_the_raw_data(self):
        import datetime as dt
        for s in SEEDS:
            col = make("x_end_before_start", s)
            bad = sum(dt.date.fromisoformat(e) < dt.date.fromisoformat(b) for e, b in zip(col["raw"], col["helpers"]["start_date"]))
            self.assertGreaterEqual(bad, 2)
            from cases import ZIP_STATE
            want = dict(ZIP_STATE)
            col = make("x_state_zip_conflict", s)
            self.assertGreaterEqual(sum(want[z] != st for st, z in zip(col["raw"], col["helpers"]["zip"])), 2)
            col = make("x_code_description_conflict", s)
            seen = {}
            for c, d in zip(col["raw"], col["helpers"]["status_desc"]):
                seen.setdefault(c, set()).add(d)
            self.assertTrue(any(len(v) > 1 for v in seen.values()))

    def test_wrong_totals_are_wrong(self):
        for s in SEEDS:
            col = make("x_total_recomputable", s)
            bad = sum(abs(t - q * p) > 0.01 for t, q, p in zip(col["raw"], col["helpers"]["qty"], col["helpers"]["unit_price"]))
            self.assertGreaterEqual(bad, 2)


class Build(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables, cls.labels = build.build(variations=4)

    def test_every_case_appears_once_per_variation(self):
        counts = Counter(l["case"] for l in self.labels)
        self.assertEqual(set(counts), set(CASES))
        self.assertEqual(set(counts.values()), {4})

    def test_tables_are_rectangular_with_unique_headers(self):
        for name, t in self.tables.items():
            self.assertEqual(len(set(t["header"])), len(t["header"]), name)
            for kind in ("raw", "clean"):
                self.assertEqual(len(t[kind]), 120)
                self.assertTrue(all(len(r) == len(t["header"]) for r in t[kind]), name)

    def test_every_label_points_at_a_real_column(self):
        for l in self.labels:
            self.assertIn(l["column"], self.tables[l["table"]]["header"])
            for h in filter(None, l["helper_columns"].split("; ")):
                self.assertIn(h, self.tables[l["table"]]["header"])

    def test_labels_match_the_data(self):
        for l in self.labels:
            t = self.tables[l["table"]]
            i = t["header"].index(l["column"])
            changed = sum(str(r[i]) != str(c[i]) for r, c in zip(t["raw"], t["clean"]))
            self.assertEqual(changed, l["rows_changed"])
            if l["verdict"] in (READY, GARBAGE):
                self.assertEqual(changed, 0, l["case"])

    def test_variations_differ(self):
        a = [l for l in self.labels if l["case"] == "f_sentinel_number"]
        cols = []
        for l in a:
            t = self.tables[l["table"]]
            i = t["header"].index(l["column"])
            cols.append(tuple(r[i] for r in t["raw"]))
        self.assertEqual(len(set(cols)), 4)
        self.assertGreater(len({l["domain"] for l in self.labels}), 3)

    def test_files_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            summary = build.write(d, variations=2)
            self.assertEqual(summary["labelled_columns"], 2 * len(CASES))
            rows = list(csv.DictReader(Path(d, "labels.csv").read_text(encoding="utf-8").splitlines()))
            self.assertEqual(len(rows), 2 * len(CASES))
            for kind in ("raw", "clean"):
                files = list(Path(d, kind).glob("*.csv"))
                self.assertEqual(len(files), summary["tables"])
                for f in files:
                    data = list(csv.reader(f.read_text(encoding="utf-8").splitlines()))
                    self.assertEqual(len(data), 121, f.name)

    def test_abbreviation(self):
        self.assertEqual(build.abbreviate("customer_name"), "cstmr_nm")


if __name__ == "__main__":
    unittest.main()
