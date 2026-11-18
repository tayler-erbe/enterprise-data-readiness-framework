"""Parse every generated SQL file with a Databricks-dialect parser, and check that every text value survives the trip.

Catches syntax and quoting slips, not workspace or permission problems.
"""
import logging
import sys
from pathlib import Path

import sqlglot
from sqlglot import exp

logging.getLogger("sqlglot").setLevel(logging.ERROR)

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "testset"))
sys.path.insert(0, str(HERE.parent.parent))

import build  # noqa: E402
import detect  # noqa: E402

bad = 0
files = sorted((HERE / "sql").glob("*.sql"))
parsed = {}
for f in files:
    try:
        parsed[f.name] = [s for s in sqlglot.parse(f.read_text(encoding="utf-8"), read="databricks") if s is not None]
        print(f"ok   {f.name:24} {len(parsed[f.name])} statements")
    except Exception as e:  # noqa: BLE001
        bad += 1
        print(f"FAIL {f.name:24} {str(e)[:300]}")

# Round trip: the prompts the parser reads back out of the SQL must equal the prompts the local harness sends.
variations = len([f for f in files if f.name.startswith("10_load_")])
if variations and not bad:
    tables, labels = build.build(variations=variations)
    want = {(l["table"], l["column"]): detect.SYSTEM + "\n\n" + detect.prompt(l["table"], tables[l["table"]], l, 10)[0] for l in labels}
    got = {}
    for name, statements in parsed.items():
        if not name.startswith("10_load_"):
            continue
        for s in statements:
            if isinstance(s, exp.Insert) and s.this.name.lower() == "t_prompts":
                for row in s.expression.expressions:
                    t, c, _, p = row.expressions
                    got[(t.this, c.this)] = p.this
    wrong = [k for k in want if got.get(k) != want[k]]
    print(f"prompts read back from the SQL: {len(got)} of {len(want)}, {len(wrong)} differ")
    bad += bool(wrong) or len(got) != len(want)
sys.exit(1 if bad else 0)
