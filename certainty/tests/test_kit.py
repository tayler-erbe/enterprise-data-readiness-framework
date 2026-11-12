"""Checks on the certainty kit. Run from certainty/:

    python -m unittest discover -s tests

The database tests need the legacy database (build_legacy.py) and the source
parquet folder, given in the SOURCE_DATA environment variable. They are skipped
when either is missing. The rest need nothing.
"""
import json
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import context as ctx  # noqa: E402
import report  # noqa: E402
import run  # noqa: E402

DB = HERE / "build" / "legacy.duckdb"
SOURCE = os.environ.get("SOURCE_DATA", "")
HAVE_DATA = DB.exists() and SOURCE and Path(SOURCE, "fact_assignment.parquet").exists()


class Scoring(unittest.TestCase):
    def test_order_of_rows_and_columns_does_not_matter(self):
        self.assertTrue(run.same([("Sales", 10), ("Claims", 7)], [(7, "Claims"), (10, "Sales")]))

    def test_tolerance(self):
        self.assertTrue(run.same([(100.4,)], [(101,)], tol=1))
        self.assertFalse(run.same([(100.4,)], [(102,)], tol=1))
        self.assertFalse(run.same([(8816,)], [(8724,)]))

    def test_shape_must_match(self):
        self.assertFalse(run.same([(1, 2)], [(1,)]))
        self.assertFalse(run.same([(1,), (1,)], [(1,)]))

    def test_only_one_select_is_allowed(self):
        for bad in ["drop table ASG_HST", "select 1; select 2", "", "update x set y = 1"]:
            with self.assertRaises(ValueError):
                run.safe_sql(bad)
        self.assertEqual(run.safe_sql(" select 1; "), "select 1")

    def test_reply_parsing(self):
        r = run.parse_reply('<think>hmm {"x": 1}</think>```json\n{"sql": "select 1", "confidence": 140, "cannot_answer": false}\n```')
        self.assertEqual((r["sql"], r["confidence"], r["cannot_answer"]), ("select 1", 100.0, False))
        self.assertIsNone(run.parse_reply("I think the answer is 12."))
        self.assertIsNone(run.parse_reply('{"sql": '))


class Contexts(unittest.TestCase):
    layer = ctx.load_layer()
    schema = {t: [(c, "VARCHAR") for c in d["columns"]] for t, d in layer["tables"].items()}

    def test_level_zero_shows_names_only(self):
        text = ctx.render(self.layer, self.schema, [])
        self.assertIn("BASE_RT", text)
        for leak in ["per month", "entered in error", "New hire", "Grain:", "VERIFIED"]:
            self.assertNotIn(leak, text)

    def test_each_level_adds_to_the_one_below(self):
        sizes = [len(ctx.render(self.layer, self.schema, ctx.LEVELS[n])) for n in sorted(ctx.LEVELS)]
        self.assertEqual(sizes, sorted(sizes))
        self.assertEqual(len(set(sizes)), 5)

    def test_what_each_kind_carries(self):
        only = lambda k: ctx.render(self.layer, self.schema, [k])
        self.assertIn("per month", only("units"))
        self.assertIn("'T62' = Retirement", only("codes"))
        self.assertIn("VOID_FL = 'Y'", only("rules"))
        self.assertIn("Grain:", only("structure"))
        self.assertNotIn("per month", only("descriptions"))
        self.assertNotIn("T62", only("descriptions"))

    def test_example_queries_are_not_the_test_questions(self):
        asked = {q["question"] for q in run.load_questions()}
        gold = {q.get("gold_sql") for q in run.load_questions()}
        for e in self.layer["examples"]:
            self.assertNotIn(e["question"], asked)
            self.assertNotIn(e["sql"], gold)

    def test_every_column_is_documented(self):
        for t, d in self.layer["tables"].items():
            for c, cd in d["columns"].items():
                self.assertTrue(cd.get("description"), t + "." + c)

    def test_modes(self):
        self.assertEqual(len(ctx.contexts("ladder")), 5)
        self.assertEqual(len(ctx.contexts("add-one")), 7)
        self.assertEqual(len(ctx.contexts("leave-one-out")), 7)
        self.assertEqual(len(ctx.contexts("controls")), 4)
        keys = [(tuple(sorted(k)), ctx.VARIANTS.get(n)) for n, k in ctx.contexts("all")]
        self.assertEqual(len(keys), len(set(keys)))

    def test_padded_control_adds_length_and_no_facts(self):
        plain = ctx.render(self.layer, self.schema, [])
        padded = ctx.render(self.layer, self.schema, [], "padded")
        full = ctx.render(self.layer, self.schema, ctx.LEVELS[4])
        self.assertTrue(padded.startswith(plain))
        self.assertLess(abs(len(padded) - len(full)), 200)
        for leak in ["per month", "entered in error", "New hire", "Grain:"]:
            self.assertNotIn(leak, padded)

    def test_misleading_control_changes_only_the_listed_facts(self):
        good = ctx.render(self.layer, self.schema, ctx.LEVELS[3]).splitlines()
        bad = ctx.render(self.layer, self.schema, ctx.LEVELS[3], "misleading").splitlines()
        self.assertEqual(len(good), len(bad))
        changed = [b for g, b in zip(good, bad) if g != b]
        self.assertEqual(len(changed), len(self.layer["misleading"]["changes"]))
        self.assertTrue(any("BASE_RT" in c and "per year" in c for c in changed))
        self.assertIn("per month", " ".join(good))


class Report(unittest.TestCase):
    def test_measures(self):
        def r(q, rep, status, conf, answer):
            return {"context": "level0", "kinds": [], "question": q, "rep": rep, "status": status,
                    "confidence": conf, "answer": answer, "needs": [], "model": "m", "missing": "", "logprob_mean": None}
        rows = [r("q1", 0, "correct", 90, "a"), r("q1", 1, "correct", 90, "a"),
                r("q2", 0, "wrong", 90, "b"), r("q2", 1, "wrong", 90, "b"),
                r("q3", 0, "abstained", 20, "ABSTAINED"), r("q3", 1, "wrong", 50, "c")]
        report.add_agreement(rows)
        s = report.summarise(rows)
        self.assertAlmostEqual(s["reliability_score"], (2 - 3) / 6)
        self.assertAlmostEqual(s["brier"], (2 * 0.01 + 2 * 0.81 + 0.25) / 5)
        self.assertAlmostEqual(s["auroc_stated"], (2 * 2 * 0.5 + 2 * 1) / 6)
        self.assertAlmostEqual(s["accuracy"], 2 / 6)
        self.assertAlmostEqual(s["accuracy_when_answered"], 2 / 5)
        self.assertAlmostEqual(s["stated_confidence"], 0.82)
        self.assertAlmostEqual(s["overconfidence"], 0.42)
        self.assertAlmostEqual(s["confident_and_wrong"], 2 / 6)
        self.assertAlmostEqual(s["agreement"], (1 + 1 + 0.5) / 3)
        self.assertEqual(s["questions_same_answer_every_time_and_wrong"], 1)


class Signals(unittest.TestCase):
    def test_auroc(self):
        self.assertEqual(report.auroc([90, 80, 20, 10], [True, True, False, False]), 1.0)
        self.assertEqual(report.auroc([10, 20, 80, 90], [True, True, False, False]), 0.0)
        self.assertEqual(report.auroc([50, 50, 50, 50], [True, False, True, False]), 0.5)
        self.assertIsNone(report.auroc([50, 60], [True, True]))

    def test_calibration_error(self):
        self.assertAlmostEqual(report.calibration_error([100, 100, 0, 0], [True, True, False, False]), 0.0)
        self.assertAlmostEqual(report.calibration_error([90, 90, 90, 90], [True, False, False, False]), 0.65)

    def test_token_probability_is_taken_from_the_sql_tokens(self):
        tokens = [('{"sql": "', -5.0), ("select", -0.1), (" 1", -0.3), ('", "confidence": 90}', -5.0)]
        m, p = run.sql_token_stats(tokens, "select 1")
        self.assertAlmostEqual(m, -0.2)
        m, _ = run.sql_token_stats(tokens, "select 2")  # not found: falls back to every token
        self.assertAlmostEqual(m, -10.4 / 4)
        self.assertEqual(run.sql_token_stats(None, "select 1"), (None, None))

    def test_unanswerable_questions_are_scored_on_declining(self):
        q = {"id": "u", "unanswerable": True}
        yes = run.attempt(None, q, None, '{"sql": "", "confidence": 10, "cannot_answer": true}')
        no = run.attempt(None, q, None, '{"sql": "select 1", "confidence": 95, "cannot_answer": false}')
        self.assertEqual((yes["status"], no["status"]), ("declined_ok", "answered_unanswerable"))

    def test_question_set(self):
        qs = run.load_questions()
        self.assertEqual(sum(not q.get("unanswerable") for q in qs), 20)
        self.assertEqual(sum(bool(q.get("unanswerable")) for q in qs), 5)
        self.assertEqual(len({q["id"] for q in qs}), len(qs))
        ids = {q["id"] for q in qs}
        self.assertTrue(set(ctx.load_layer()["misleading"]["affected_questions"]) <= ids)


@unittest.skipUnless(HAVE_DATA, "needs build/legacy.duckdb and SOURCE_DATA")
class Database(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import duckdb
        import build_legacy
        cls.legacy = duckdb.connect(str(DB), read_only=True)
        cls.plain = duckdb.connect()
        build_legacy.attach_source(cls.plain, SOURCE)
        cls.questions = [q for q in run.load_questions() if not q.get("unanswerable")]

    def test_gold_answers_match_the_plain_tables(self):
        for q in self.questions:
            truth = self.plain.execute(q["truth_sql"]).fetchall()
            gold = self.legacy.execute(q["gold_sql"]).fetchall()
            self.assertTrue(run.same(gold, truth, q.get("tol", 0.01)), q["id"] + ": " + str(gold) + " vs " + str(truth))

    def test_no_answer_is_empty_or_zero(self):
        for q in self.questions:
            gold = self.legacy.execute(q["gold_sql"]).fetchall()
            self.assertTrue(gold and gold[0][0] not in (None, 0), q["id"])

    def test_the_documentation_covers_exactly_the_real_columns(self):
        schema = ctx.read_schema(self.legacy)
        layer = ctx.load_layer()
        self.assertEqual(set(schema), set(layer["tables"]))
        for t, cols in schema.items():
            self.assertEqual([c for c, _ in cols], list(layer["tables"][t]["columns"]), t)

    def test_documented_codes_are_the_codes_in_the_data(self):
        layer = ctx.load_layer()
        for t, d in layer["tables"].items():
            for c, cd in d["columns"].items():
                codes = set(cd.get("codes", {})) - {"NULL", "9999-12-31"}
                if not codes:
                    continue
                found = {str(r[0]) for r in self.legacy.execute(f"select distinct {c} from {t} where {c} is not null").fetchall()}
                self.assertEqual(found, codes, t + "." + c)

    def test_misleading_facts_change_the_affected_answers(self):
        """Following the wrong documentation gives a different number on each affected question."""
        one = lambda s: self.legacy.execute(s).fetchall()[0][0]
        by_id = {q["id"]: q for q in self.questions}
        swaps = {"q02": ("BASE_RT * 12", "BASE_RT"), "q11": ("BASE_RT * 12", "BASE_RT"), "q12": ("GNDR_CD = '2'", "GNDR_CD = '1'")}
        self.assertEqual(set(swaps), set(ctx.load_layer()["misleading"]["affected_questions"]))
        for qid, (old, new) in swaps.items():
            gold = by_id[qid]["gold_sql"]
            self.assertIn(old, gold)
            self.assertNotEqual(one(gold.replace(old, new)), one(gold), qid)

    def test_unanswerable_questions_have_no_matching_column(self):
        cols = " ".join(c for cs in ctx.read_schema(self.legacy).values() for c, _ in cs)
        for word in ["RMT", "BONUS", "BNS", "SUPV", "MGR", "FTE", "HRS", "LIC", "CERT"]:
            self.assertNotIn(word, cols)

    def test_example_queries_run(self):
        for e in ctx.load_layer()["examples"]:
            self.assertTrue(run.run_sql(self.legacy, e["sql"]), e["question"])

    def test_the_traps_are_real(self):
        """Each shortcut a model might take without documentation gives a different number."""
        one = lambda s: self.legacy.execute(s).fetchall()[0][0]
        right = one("select count(distinct PSN_NO) from ASG_HST where CUR_FL = 'Y' and VOID_FL = 'N'")
        self.assertNotEqual(one("select count(distinct PSN_NO) from ASG_HST where CUR_FL = 'Y'"), right)
        self.assertEqual(one("select count(*) from ASG_HST where END_DT is null"), 0)
        self.assertEqual(one("select count(*) from ACT_LOG where ACT_CD in ('HIRE', 'H', 'NEW_HIRE')"), 0)
        pay = one("select avg(BASE_RT) from ASG_HST where CUR_FL = 'Y' and VOID_FL = 'N'")
        self.assertLess(pay, 20000)


if __name__ == "__main__":
    unittest.main()


class FakeServer(unittest.TestCase):
    """Runs the real HTTP path against a stand-in server on this machine."""

    def serve(self, accept_logprobs):
        import http.server
        import threading

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if body.get("logprobs") and not accept_logprobs:
                    self.send_response(400)
                    self.end_headers()
                    return
                reply = '{"sql": "select 1", "confidence": 70, "cannot_answer": false, "missing": ""}'
                choice = {"message": {"content": reply}}
                if body.get("logprobs"):
                    choice["logprobs"] = {"content": [{"token": reply[:9], "logprob": -3.0}, {"token": "select 1", "logprob": -0.5},
                                                      {"token": reply[17:], "logprob": -3.0}]}
                out = json.dumps({"choices": [choice]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(out)

            def log_message(self, *a):
                pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        return "http://127.0.0.1:" + str(srv.server_address[1]) + "/v1"

    def test_token_probabilities_are_read(self):
        m = run.Model(self.serve(True), "x", 0.7, 100, "", 10)
        text, tokens = m.ask("s", "u")
        self.assertEqual(run.parse_reply(text)["sql"], "select 1")
        self.assertAlmostEqual(run.sql_token_stats(tokens, "select 1")[0], -0.5)

    def test_a_server_without_token_probabilities_still_works(self):
        m = run.Model(self.serve(False), "x", 0.7, 100, "", 10)
        text, tokens = m.ask("s", "u")
        self.assertIsNone(tokens)
        self.assertFalse(m.logprobs)
        self.assertEqual(run.parse_reply(text)["confidence"], 70.0)
