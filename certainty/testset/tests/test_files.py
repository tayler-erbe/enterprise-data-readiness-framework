"""Checks on the whole-file cases. Run from certainty/testset/:

    python -m unittest discover -s tests
"""
import random
import sys
import unittest
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import detect  # noqa: E402
import tables as fc  # noqa: E402
from cases import DOMAINS, FIXABLE, GARBAGE, NEEDS_CONTEXT, READY  # noqa: E402


def make(cid, seed, dom="retail"):
    return fc.TABLE_CASES[cid]["make"](random.Random(f"t|{seed}|{cid}"), DOMAINS[dom])


class FileCases(unittest.TestCase):
    def test_catalogue(self):
        by = Counter(c["verdict"] for c in fc.TABLE_CASES.values())
        self.assertEqual(by, {READY: 1, FIXABLE: 7, NEEDS_CONTEXT: 1, GARBAGE: 1})
        for cid, c in fc.TABLE_CASES.items():
            self.assertEqual(c["verdict"] == FIXABLE, c["fixer"] is not None, cid)
            if c["fix"]:
                self.assertIn(c["fix"], detect.FILE_FIXES, cid)

    def test_a_separate_fixer_reproduces_every_clean_file(self):
        for cid, c in fc.TABLE_CASES.items():
            if c["verdict"] != FIXABLE:
                continue
            for seed in range(25):
                for dom in DOMAINS:
                    t = make(cid, seed, dom)
                    self.assertEqual(c["fixer"]([list(r) for r in t["raw"]]), t["clean"], f"{cid} {seed} {dom}")
                    self.assertNotEqual(t["raw"], t["clean"], cid)

    def test_wide_table_key_was_built_a_second_way(self):
        for seed in range(10):
            t = make("t_wide_months", seed)
            self.assertEqual(t["clean"][1:], t["independent"])
            self.assertEqual(len(t["clean"]) - 1, 30 * 6)

    def test_clean_files_are_tidy(self):
        for cid, c in fc.TABLE_CASES.items():
            if c["verdict"] in (READY, FIXABLE):
                t = make(cid, 1)
                width = len(t["clean"][0])
                self.assertTrue(all(len(r) == width for r in t["clean"]), cid)
                self.assertEqual(len({tuple(r) for r in t["clean"]}), len(t["clean"]), cid)

    def test_the_problems_are_really_there(self):
        t = make("t_duplicate_rows", 2)
        self.assertEqual(len(t["raw"]) - len(t["clean"]), 6)
        t = make("t_split_field_shift", 2)
        self.assertEqual(sum(len(r) == 7 for r in t["raw"]), 6)
        t = make("t_repeated_header_rows", 2)
        self.assertEqual(sum(r == fc.HEADER for r in t["raw"]), 3)
        t = make("t_header_not_first_row", 2)
        self.assertNotEqual(t["raw"][0], fc.HEADER)
        t = make("t_header_missing", 2)
        self.assertTrue(t["raw"][0][0].startswith("ORD-"))

    def test_build_and_prompt(self):
        files, labels = fc.build(variations=3)
        self.assertEqual(len(files), 3 * len(fc.TABLE_CASES))
        for l in labels:
            label = dict(l, column="(whole file)")
            text = detect.file_prompt(l["table"], files[l["table"]], label)
            head = text.split("FIXES")[0]
            self.assertNotIn(l["case"], head)
            self.assertNotIn(l["issue"], head)
            self.assertIn(f"{l['focus_row'] + 1:>4}: ", head)

    def test_the_prompt_shows_the_problem(self):
        files, labels = fc.build(variations=2)
        for l in labels:
            head = detect.file_prompt(l["table"], files[l["table"]], dict(l, column="(whole file)")).split("FIXES")[0]
            raw = files[l["table"]]["raw"]
            if l["case"] == "t_duplicate_rows":
                lines = [x.split(": ", 1)[1] for x in head.splitlines() if ": " in x[:7]]
                self.assertTrue(any(n > 1 for n in Counter(lines).values()))
            if l["case"] == "t_split_field_shift":
                self.assertIn(", Apt" if False else " Apt ", head)
            if l["case"] == "t_total_rows":
                self.assertIn("Subtotal", head)
                self.assertIn("Total,", head)
            if l["case"] == "t_repeated_header_rows":
                self.assertGreaterEqual(head.count(",".join(fc.HEADER)), 2)


if __name__ == "__main__":
    unittest.main()
