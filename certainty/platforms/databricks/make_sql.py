"""Write the SQL that runs the test set inside a Databricks workspace.

    python make_sql.py --endpoint system.ai.meta-llama-3-3-70b-instruct     # writes sql/

It writes, into sql/:

    00_setup.sql              the schema and the two result tables
    10_load_v00.sql ...       one file per variation: the raw tables and the detector prompts
    30_verdicts.sql           runs the detector prompt through ai_query on the chosen endpoint
    40_export.sql             the two queries whose results you download as CSV

There is no 20_describe file. Databricks writes column descriptions from the
"AI generate" button in Catalog Explorer, and its documentation gives no SQL or
API way to ask for them. The README lists the clicks; 40_export.sql reads back
whatever comments were saved.

Run 00, then 10_load_v00 and the first statement of 30. That is 8 tables and
about 60 columns: enough to see that it works and what it costs.

Only the raw tables are loaded. The clean tables and the labels never leave this
machine, so nothing in the workspace can see the answer key.

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

SCHEMA = "readiness_test"
NAME_OK = re.compile(r"^[a-z][a-z0-9_]*$")
INT = re.compile(r"^-?(0|[1-9]\d{0,17})$")
DEC = re.compile(r"^-?(0|[1-9]\d{0,14})\.\d{1,6}$")


def sql_type(values):
    """The type a plain CSV load would give the column, chosen so the stored value reads exactly as it arrived.

    Whole numbers become BIGINT. Decimals that all have the same number of places become DECIMAL(38, places),
    which keeps 777359.0 and 12.50 as written (DOUBLE would show 777359 and 12.5). Everything else is text.
    """
    filled = [str(v) for v in values if str(v).strip() != ""]
    if filled and all(INT.match(v) for v in filled):
        return "BIGINT"
    if filled and all(DEC.match(v) for v in filled):
        places = {len(v.split(".")[1]) for v in filled}
        if len(places) == 1:
            return f"DECIMAL(38, {places.pop()})"
    return "STRING"


def text(v):
    """A Databricks string literal. Backslash escapes are used because a doubled quote is not an escape there."""
    v = str(v).replace("\\", "\\\\").replace("'", "\\'").replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    return "'" + v + "'"


def lit(v, typ):
    v = str(v)
    if v == "" or (v.strip() == "" and typ != "STRING"):
        return "NULL"
    return text(v) if typ == "STRING" else v


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
    ap.add_argument("--endpoint", default="system.ai.meta-llama-3-3-70b-instruct",
                    help="a chat model endpoint your workspace lists under Serving")
    ap.add_argument("--variations", type=int, default=12)
    ap.add_argument("--rows", type=int, default=10, help="sample rows shown in the detector prompt")
    ap.add_argument("--reps", type=int, default=1, help="repeats of each detector question (3 matches the local harness)")
    ap.add_argument("--out", default=str(HERE / "sql"))
    a = ap.parse_args()
    assert "'" not in a.endpoint, a.endpoint
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.sql"):
        old.unlink()
    tables, labels = build.build(variations=a.variations)

    (out / "00_setup.sql").write_text("\n".join([
        "-- Choose a catalog first, for example:  USE CATALOG workspace;",
        f"CREATE SCHEMA IF NOT EXISTS {SCHEMA};",
        f"CREATE OR REPLACE TABLE {SCHEMA}.t_prompts (table_name STRING, column_name STRING, variation INT, prompt STRING);",
        f"CREATE OR REPLACE TABLE {SCHEMA}.t_verdicts (table_name STRING, column_name STRING, rep INT, model STRING, "
        "reply STRING, error STRING, asked_at TIMESTAMP);",
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
            prompts.append(f"('{l['table']}', '{l['column']}', {var}, {text(detect.SYSTEM + chr(10) + chr(10) + user)})")
        load.append(f"DELETE FROM {SCHEMA}.t_prompts WHERE variation = {var};")
        load.append(f"INSERT INTO {SCHEMA}.t_prompts VALUES\n" + ",\n".join(prompts) + ";")
        (out / f"10_load_v{var:02d}.sql").write_text("\n".join(load) + "\n", encoding="utf-8")

    # failOnError => false returns a struct (response, errorMessage), so one failed request does not stop the rest.
    verdict = lambda where, rep: (
        f"INSERT INTO {SCHEMA}.t_verdicts\n"
        f"SELECT table_name, column_name, {rep}, '{a.endpoint}', r.response, r.errorMessage, current_timestamp()\n"
        f"FROM (\n"
        f"  SELECT table_name, column_name,\n"
        f"         ai_query('{a.endpoint}', prompt,\n"
        f"                  modelParameters => named_struct('max_tokens', 2500, 'temperature', 0.7),\n"
        f"                  failOnError => false) AS r\n"
        f"  FROM {SCHEMA}.t_prompts{where}\n"
        f");")
    lines = ["-- Smoke test: variation 0 only (about 60 short requests). Run this first and check the cost before going on.",
             verdict(" WHERE variation = 0", 0), "",
             "-- The rest. Run only after the smoke test looks right."]
    for rep in range(a.reps):
        lines.append(verdict(" WHERE variation > 0" if rep == 0 else "", rep))
    (out / "30_verdicts.sql").write_text("\n".join(lines) + "\n", encoding="utf-8")

    (out / "40_export.sql").write_text("\n".join([
        "-- Run each query, then download the result as CSV.",
        "-- Save the first as verdicts.csv and the second as comments.csv, next to score_databricks.py.",
        f"SELECT table_name, column_name, rep, model, reply, error FROM {SCHEMA}.t_verdicts ORDER BY table_name, column_name, rep;",
        "-- The second query reads the comments saved from the AI generate button. Columns with no comment come back blank.",
        "SELECT table_name, column_name, comment FROM information_schema.columns\n"
        f"WHERE table_schema = '{SCHEMA}' AND table_name NOT IN ('t_prompts', 't_verdicts') ORDER BY table_name, ordinal_position;",
        "", "-- When finished, to remove everything:", f"-- DROP SCHEMA {SCHEMA} CASCADE;", ""]), encoding="utf-8")

    sizes = {p.name: p.stat().st_size for p in sorted(out.glob("*.sql"))}
    print(f"{len(tables)} tables, {len(labels)} prompts, endpoint {a.endpoint}, {a.reps} repeat(s)")
    print("largest file:", max(sizes, key=sizes.get), f"{max(sizes.values()) / 1024:.0f} KB")
    print("written to", out)


if __name__ == "__main__":
    main()
