"""Write the SQL that runs the test set inside a Snowflake account.

    python make_sql.py --model llama3.3-70b            # writes sql/

It writes, into sql/:

    00_setup.sql              the schema and the two result tables
    10_load_v00.sql ...       one file per variation: the raw tables and the detector prompts
    20_describe_v00.sql ...   asks Snowflake to describe every column, with and without sample data
    30_verdicts.sql           runs the detector prompt through AI_COMPLETE on the chosen model
    40_export.sql             the two queries whose results you download as CSV

Run 00, then 10_load_v00, 20_describe_v00 and 30 with the smoke-test line first.
That is 8 tables and about 60 columns: enough to see that it works and what it costs.

Only the raw tables are loaded. The clean tables and the labels never leave this
machine, so nothing in the account can see the answer key.

All of the data is generated. None of it describes a real person or organisation.
"""
import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "testset"))
sys.path.insert(0, str(HERE.parent.parent))

import build  # noqa: E402
import detect  # noqa: E402

SCHEMA = "READINESS_TEST"
NAME_OK = re.compile(r"^[a-z][a-z0-9_]*$")
INT = re.compile(r"^-?(0|[1-9]\d{0,17})$")
DEC = re.compile(r"^-?(0|[1-9]\d{0,14})\.\d{1,6}$")


def sql_type(values):
    """The type a plain CSV load would give the column."""
    filled = [v for v in values if str(v).strip() != ""]
    if filled and all(INT.match(str(v)) for v in filled):
        return "NUMBER"
    if filled and all(INT.match(str(v)) or DEC.match(str(v)) for v in filled):
        return "FLOAT"
    return "VARCHAR"


def lit(v, typ):
    v = str(v)
    if v.strip() == "":
        return "NULL" if typ != "VARCHAR" or v == "" else "'" + v + "'"
    if typ != "VARCHAR":
        return v
    return "'" + v.replace("\\", "\\\\").replace("'", "''") + "'"


def dollar(text):
    assert "$$" not in text, "prompt contains $$"
    return "$$" + text + "$$"


def table_sql(name, t):
    cols = list(zip(*t["raw"]))
    types = [sql_type(c) for c in cols]
    for h in t["header"]:
        assert NAME_OK.match(h), h
    out = [f"CREATE OR REPLACE TABLE {SCHEMA}.{name} (" + ", ".join(f"{h} {ty}" for h, ty in zip(t["header"], types)) + ");"]
    rows = ["(" + ", ".join(lit(v, ty) for v, ty in zip(r, types)) + ")" for r in t["raw"]]
    out.append(f"INSERT INTO {SCHEMA}.{name} VALUES\n" + ",\n".join(rows) + ";")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", default="llama3.3-70b", help="a model name your account's region offers for AI_COMPLETE")
    ap.add_argument("--variations", type=int, default=12)
    ap.add_argument("--rows", type=int, default=10, help="sample rows shown in the detector prompt")
    ap.add_argument("--reps", type=int, default=1, help="repeats of each detector question (3 matches the local harness)")
    ap.add_argument("--out", default=str(HERE / "sql"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.sql"):
        old.unlink()
    tables, labels = build.build(variations=a.variations)

    (out / "00_setup.sql").write_text("\n".join([
        f"CREATE SCHEMA IF NOT EXISTS {SCHEMA};",
        f"CREATE OR REPLACE TABLE {SCHEMA}.T_PROMPTS (table_name VARCHAR, column_name VARCHAR, variation NUMBER, prompt VARCHAR);",
        f"CREATE OR REPLACE TABLE {SCHEMA}.T_DESCRIPTIONS (table_name VARCHAR, used_data BOOLEAN, result VARCHAR, asked_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP());",
        f"CREATE OR REPLACE TABLE {SCHEMA}.T_VERDICTS (table_name VARCHAR, column_name VARCHAR, rep NUMBER, model VARCHAR, reply VARCHAR, asked_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP());",
        ""]), encoding="utf-8")

    by_var = {}
    for l in labels:
        by_var.setdefault(int(l["variation"]), []).append(l)
    for var, ls in sorted(by_var.items()):
        names = sorted({l["table"] for l in ls})
        load = [f"-- Variation {var:02d}: {len(names)} raw tables and {len(ls)} detector prompts. Generated data."]
        load += [table_sql(n, tables[n]) for n in names]
        prompts = []
        for l in ls:
            user, _ = detect.prompt(l["table"], tables[l["table"]], l, a.rows)
            prompts.append(f"('{l['table']}', '{l['column']}', {var}, {dollar(detect.SYSTEM + chr(10) + chr(10) + user)})")
        load.append(f"DELETE FROM {SCHEMA}.T_PROMPTS WHERE variation = {var};")
        load.append(f"INSERT INTO {SCHEMA}.T_PROMPTS VALUES\n" + ",\n".join(prompts) + ";")
        (out / f"10_load_v{var:02d}.sql").write_text("\n".join(load) + "\n", encoding="utf-8")

        desc = [f"-- Variation {var:02d}: ask Snowflake to describe every column, first from names and types only, then with sample data."]
        for n in names:
            for used in ("false", "true"):
                desc.append(f"CALL AI_GENERATE_TABLE_DESC('{SCHEMA}.{n}', {{'describe_columns': true, 'use_table_data': {used}}});")
                desc.append(f"INSERT INTO {SCHEMA}.T_DESCRIPTIONS (table_name, used_data, result) "
                            f"SELECT '{n}', {used}, $1 FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));")
        (out / f"20_describe_v{var:02d}.sql").write_text("\n".join(desc) + "\n", encoding="utf-8")

    verdict = lambda where, rep: (
        f"INSERT INTO {SCHEMA}.T_VERDICTS (table_name, column_name, rep, model, reply)\n"
        f"SELECT table_name, column_name, {rep}, '{a.model}',\n"
        f"       AI_COMPLETE(model => '{a.model}', prompt => prompt, model_parameters => {{'temperature': 0.7, 'max_tokens': 2500}})\n"
        f"FROM {SCHEMA}.T_PROMPTS{where};")
    lines = ["-- Smoke test: variation 0 only (about 60 short requests). Run this first and check the cost in Snowsight.",
             verdict(" WHERE variation = 0", 0), "",
             "-- The rest. Run only after the smoke test looks right."]
    for rep in range(a.reps):
        lines.append(verdict(" WHERE variation > 0" if rep == 0 else "", rep))
    (out / "30_verdicts.sql").write_text("\n".join(lines) + "\n", encoding="utf-8")

    (out / "40_export.sql").write_text("\n".join([
        "-- Run each query, then use Download results (CSV) in Snowsight.",
        "-- Save the first as descriptions.csv and the second as verdicts.csv, next to score_snowflake.py.",
        f"SELECT table_name, used_data, result FROM {SCHEMA}.T_DESCRIPTIONS ORDER BY table_name, used_data;",
        f"SELECT table_name, column_name, rep, model, reply FROM {SCHEMA}.T_VERDICTS ORDER BY table_name, column_name, rep;",
        "", "-- When finished, to remove everything:", f"-- DROP SCHEMA {SCHEMA};", ""]), encoding="utf-8")

    sizes = {p.name: p.stat().st_size for p in sorted(out.glob("*.sql"))}
    print(f"{len(tables)} tables, {len(labels)} prompts, model {a.model}, {a.reps} repeat(s)")
    print("largest file:", max(sizes, key=sizes.get), f"{max(sizes.values()) / 1024:.0f} KB")
    print("written to", out)


if __name__ == "__main__":
    main()
