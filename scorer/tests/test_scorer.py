import tempfile
import unittest
from pathlib import Path

from readiness import Column, Settings, Table, load_csv, load_openmetadata, score_all, score_table
from readiness.load import load_dictionary_pages
from readiness.__main__ import main
from readiness.checks import FAIL, PASS, UNKNOWN, has_encoding_damage, is_placeholder, prose_rules

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def status(score, check_id):
    return next(c.status for c in score.checks if c.id == check_id)


def full_table(**overrides):
    """A table that passes every check. Tests knock pieces out."""
    table = Table(
        schema="FIN", name="CONTRACT", description="Customer contracts held by the company.",
        columns=[
            Column("CONTRACT_ID", description="Contract identifier.", is_primary_key=True),
            Column("CUST_CD", description="Customer.", lookup="REF.CUST_CD"),
        ],
        columns_known=True, row_count=10, grain="One row per contract", primary_key=["CONTRACT_ID"],
        owner="Contract Accounting", trust_level="System of record",
        in_semantic_layer=True, verified_questions=5, verified_questions_passed=5,
    )
    for key, value in overrides.items():
        setattr(table, key, value)
    return table


class TextChecks(unittest.TestCase):
    def test_placeholders(self):
        for text in ["", "TBD", "n/a", " - ", "T_INV_HDR", "INV HDR"]:
            self.assertTrue(is_placeholder(text, "T_INV_HDR"), text)
        self.assertFalse(is_placeholder("Invoice headers.", "T_INV_HDR"))

    def test_encoding_damage(self):
        self.assertTrue(has_encoding_damage("their â€œprofileâ€"))
        self.assertTrue(has_encoding_damage("self-reported.Â"))
        self.assertFalse(has_encoding_damage("Café records, naïve résumé"))

    def test_prose_rules(self):
        found = prose_rules(
            "The old region field was retired with the 2019 payroll change; do not use for 2020 onward. "
            "Self-reported and never checked. Not for reporting. "
            "May contain invalid dates such as 01/01/200."
        )
        self.assertEqual(set(found), {"validity window", "trust level", "exclude from reporting", "known defect"})
        self.assertEqual(prose_rules("Cost centre codes and names."), {})


class Levels(unittest.TestCase):
    def setUp(self):
        self.settings = Settings()

    def level(self, **overrides):
        return score_table(full_table(**overrides), self.settings).level

    def test_full_table_is_ai_ready(self):
        self.assertEqual(self.level(), 4)

    def test_each_level_gates_the_next(self):
        self.assertEqual(self.level(description=""), 0)
        self.assertEqual(self.level(description="TBD"), 0)
        self.assertEqual(self.level(grain=""), 1)
        self.assertEqual(self.level(owner=""), 2)
        self.assertEqual(self.level(in_semantic_layer=False), 3)

    def test_a_higher_level_cannot_skip_a_lower_one(self):
        # Semantic layer and owner are set, but there's no grain: stays at 1.
        self.assertEqual(self.level(grain=""), 1)

    def test_grain_from_prose_counts(self):
        score = score_table(full_table(grain="", description="One row per contract per month."), self.settings)
        self.assertEqual(status(score, "grain"), PASS)

    def test_missing_columns_is_unknown_not_pass(self):
        score = score_table(full_table(columns=[], columns_known=False), self.settings)
        self.assertEqual(status(score, "column_coverage"), UNKNOWN)
        self.assertEqual(score.level, 1)

    def test_indexes_without_named_keys_is_unknown(self):
        score = score_table(full_table(primary_key=[], columns=[Column("A", description="A thing.")], index_count=2), self.settings)
        self.assertEqual(status(score, "keys_and_joins"), UNKNOWN)

    def test_coverage_threshold(self):
        cols = [Column("A", description="Described."), Column("B"), Column("C")]
        score = score_table(full_table(columns=cols), self.settings)
        self.assertEqual(status(score, "column_coverage"), FAIL)
        self.assertEqual(score.level, 1)

    def test_undecoded_code_column(self):
        cols = [Column("CONTRACT_ID", description="Id.", is_primary_key=True), Column("STAT_CD", description="Status.")]
        score = score_table(full_table(columns=cols), self.settings)
        self.assertEqual(status(score, "codes_decoded"), FAIL)

    def test_lookup_tables_decode_their_own_key(self):
        cols = [Column("COST_CTR_CD", description="Cost centre code.", is_primary_key=True), Column("COST_CTR_NAME", description="Name.")]
        score = score_table(full_table(name="COST_CTR_CD", columns=cols, primary_key=["COST_CTR_CD"]), self.settings)
        self.assertEqual(status(score, "codes_decoded"), PASS)

    def test_rule_in_prose_blocks_level_3_until_it_is_a_field(self):
        desc = "Address history. One row per employee per change. Do not use for 2020 onward."
        self.assertEqual(self.level(description=desc), 2)
        self.assertEqual(self.level(description=desc, valid_to="2019-12-31"), 4)

    def test_unchecked_links_are_unknown(self):
        desc = "Contracts. See http://www.example.com/advisory.aspx"
        self.assertEqual(self.level(description=desc), 2)
        self.settings.check_links = True
        self.settings.link_results = {"http://www.example.com/advisory.aspx": True}
        self.assertEqual(self.level(description=desc), 4)
        self.settings.link_results = {"http://www.example.com/advisory.aspx": False}
        self.assertEqual(self.level(description=desc), 2)

    def test_advisory_needs_a_date(self):
        self.assertEqual(self.level(known_defects="Invalid dates before 2015"), 2)
        self.assertEqual(self.level(known_defects="Invalid dates before 2015", advisory_date="2026-10-01"), 4)

    def test_verified_questions(self):
        self.assertEqual(self.level(verified_questions=4, verified_questions_passed=4), 3)
        self.assertEqual(self.level(verified_questions=10, verified_questions_passed=8), 3)
        self.assertEqual(self.level(verified_questions=10, verified_questions_passed=9), 4)

    def test_priority_is_value_times_gap(self):
        score = score_table(full_table(owner="", usage=100.0), self.settings)
        self.assertEqual((score.level, score.gap, score.priority), (2, 2, 200.0))
        self.assertIsNone(score_table(full_table(owner=""), self.settings).priority)

    def test_sensitive_names_suggest_tier_c(self):
        self.assertEqual(score_table(full_table(name="EMP_HEALTH_COND_HIST"), self.settings).suggested_tier, "C?")
        self.assertEqual(score_table(full_table(name="EMP_HEALTH_COND_HIST", privacy_tier="D"), self.settings).suggested_tier, "D")


class Examples(unittest.TestCase):
    def test_synthetic_sample(self):
        tables = load_csv(EXAMPLES / "synthetic/tables.csv", EXAMPLES / "synthetic/columns.csv")
        levels = {t.table.full_name: t.level for t in score_all(tables)}
        self.assertEqual(len(levels), 24)
        expected = {
            "FIN.CONTRACT_SPEND_FACT": 4,  # everything recorded
            "FIN.CONTRACT": 3,  # not in the semantic layer
            "REF.COST_CTR_CD": 3,  # a lookup table at its target
            "HR.POSITION": 2,  # no owner
            "HR.EMP_ADDRESS_HIST": 2,  # validity rule still in prose
            "SALES.CUST_PERIOD": 1,  # most columns undescribed
            "FIN.QUOTE_ORDER_FACT": 1,  # grain in prose, but no columns in the export
            "HR.EMP_SKILL_HIST": 1,  # encoding damage only warns; no grain
            "FIN.INVOICE_HDR": 0,  # description just repeats the name
            "OPS.POLICY_MAINT": 0,  # "TBD"
            "OPS.SCHED_JOB_DETAILS": 0,  # blank
        }
        for name, level in expected.items():
            self.assertEqual(levels[name], level, name)
        skill = next(s for s in score_all(tables) if s.table.name == "EMP_SKILL_HIST")
        self.assertTrue(any("Encoding damage in description" in w for w in skill.warnings))

    def test_table_list_alone_tops_out_at_level_1(self):
        scores = score_all(load_csv(EXAMPLES / "synthetic/table-list-export.csv"))
        self.assertEqual(max(s.level for s in scores), 1)

    def test_openmetadata(self):
        tables = {t.name: t for t in load_openmetadata(EXAMPLES / "openmetadata/tables.json")}
        fact = tables["contract_spend_fact"]
        self.assertEqual(fact.schema, "fin")
        self.assertEqual(fact.owner, "Contract Accounting")
        self.assertEqual(fact.primary_key, ["contract_id", "fiscal_mo"])
        self.assertEqual(fact.usage, 4200.0)
        self.assertEqual(fact.row_count, 1840221)
        self.assertEqual(tables["emp_cert_hist"].owner, "hr.records")  # older single-owner shape
        self.assertEqual(tables["sched_job_details"].schema, "ops")  # from the fully qualified name
        levels = {s.table.name: s.level for s in score_all(list(tables.values()))}
        self.assertEqual(levels, {"contract_spend_fact": 4, "emp_cert_hist": 1, "sched_job_details": 0})

    def test_cli_writes_every_output(self):
        with tempfile.TemporaryDirectory() as out:
            code = main([str(EXAMPLES / "synthetic/tables.csv"), "--columns", str(EXAMPLES / "synthetic/columns.csv"), "--out", out])
            self.assertEqual(code, 0)
            names = sorted(p.name for p in Path(out).iterdir())
            self.assertEqual(names, ["columns.csv", "scorecard.md", "scores.csv", "scores.json", "worklist.md"])


PAGE = """Data Model : DW : All Tables
Table Name : LEAVE_DEMO
Table properties
Row count:	
Comment:	LEAVE BALANCES BY PAY PERIOD.
Columns
\u25b2 Ordinal\tColumn\tComments\tDatatype\tPK/FK\tPrimary Definition
1\tEMP_ID\tEmployee id.\tNUMBER(9, 0)\tPrimary Key\t
2\tLEAVE_CD\tType of leave.\tVARCHAR2(4)\tPrimary Key\t
3\tLEAVE_LONG_DESC\tFull description of the leave code.\tVARCHAR2(30)\t\t
4\tLEAVE_EFF_DT\tThe date this record became effective in the source system.\tDATE\t\t
5\tLEAVE_EXP_DT\tThe date this record became effective in the source system.\tDATE\t\t
Indexes
Name
PK_LEAVE_DEMO NEXTNEXT
Data Model : DW : All Indexes
Index : PK_LEAVE_DEMO
Columns
1\tEMP_ID\tEmployee id.\tNUMBER(9, 0)\tPrimary Key\t
"""


class DictionaryPages(unittest.TestCase):
    def test_parse_and_score(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "pages.txt"
            path.write_text(PAGE, encoding="utf-8")
            tables = load_dictionary_pages(path)
        self.assertEqual(len(tables), 1)  # the index page is not a table
        t = tables[0]
        self.assertEqual((t.schema, t.name, t.index_count), ("DW", "LEAVE_DEMO", 1))
        self.assertEqual(t.primary_key, ["EMP_ID", "LEAVE_CD"])
        self.assertEqual(len(t.columns), 5)
        score = score_table(t, Settings())
        # LEAVE_CD is decoded by LEAVE_LONG_DESC in the same table
        self.assertEqual(status(score, "codes_decoded"), PASS)
        self.assertTrue(any("same description" in w for w in score.warnings))
        self.assertTrue(any("Draft grain from the key" in w for w in score.warnings))

    def test_sensitive_columns_suggest_tier_c(self):
        t = full_table(name="PAY_DEDUCTIONS", columns=[Column("SSN"), Column("BIRTH_DT")])
        self.assertEqual(score_table(t, Settings()).suggested_tier, "C?")


if __name__ == "__main__":
    unittest.main()
