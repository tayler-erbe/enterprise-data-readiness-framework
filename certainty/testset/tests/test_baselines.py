import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import baselines  # noqa: E402


class Baselines(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = baselines.run(*baselines.load())

    def test_accept_all_passes_every_unsafe_column(self):
        m = baselines.measures(self.results["accept_all"])
        self.assertEqual(m["dangerous"], 1.0)
        self.assertEqual(m["over_cautious"], 0.0)

    def test_rules_never_say_needs_context(self):
        self.assertFalse(any(r["said"] == "NEEDS_CONTEXT" for r in self.results["rules"]))

    def test_no_baseline_holds_back_a_ready_column(self):
        for name, recs in self.results.items():
            self.assertTrue(all(r["said"] == "READY" for r in recs if r["truth"] == "READY"), name)

    def test_profiler_sees_unresolvable_slash_dates(self):
        recs = [r for r in self.results["profiler"] if r["case"] == "n_date_slash_unresolvable"]
        self.assertTrue(recs and all(r["said"] == "NEEDS_CONTEXT" for r in recs))

    def test_profiler_is_at_least_as_good_as_rules(self):
        a, b = baselines.measures(self.results["profiler"]), baselines.measures(self.results["rules"])
        self.assertGreaterEqual(a["verdict_right"], b["verdict_right"])
        self.assertLessEqual(a["dangerous"], b["dangerous"])


if __name__ == "__main__":
    unittest.main()
