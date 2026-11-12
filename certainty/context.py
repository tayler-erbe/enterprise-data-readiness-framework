"""Cut the full documentation down to a readiness level, or to any mix of context kinds.

    python context.py --db build/legacy.duckdb --level 2

Six kinds of context, each a thing a data dictionary can hold:

    descriptions  what each table and column is
    structure     grain, key and joins
    codes         what each coded value means
    units         units and formats
    rules         how to count, and which rows to leave out
    examples      metric definitions and verified example queries
"""
import argparse
import copy
import json
from pathlib import Path

HERE = Path(__file__).parent
KINDS = ["descriptions", "structure", "codes", "units", "rules", "examples"]
LEVELS = {
    0: [],
    1: ["descriptions"],
    2: ["descriptions", "structure", "codes", "units"],
    3: ["descriptions", "structure", "codes", "units", "rules"],
    4: ["descriptions", "structure", "codes", "units", "rules", "examples"],
}
LEVEL_NAMES = {0: "Undocumented", 1: "Described", 2: "Usable", 3: "Governed", 4: "AI-ready"}


def load_layer(path=None):
    return json.loads(Path(path or HERE / "semantic_layer.json").read_text(encoding="utf-8"))


def read_schema(con):
    """{table: [(column, type), ...]} straight from the database."""
    rows = con.execute(
        "select table_name, column_name, data_type from information_schema.columns "
        "where table_schema = 'main' order by table_name, ordinal_position"
    ).fetchall()
    schema = {}
    for t, c, d in rows:
        schema.setdefault(t, []).append((c, d))
    return schema


# Two control contexts change the text without adding true information.
VARIANTS = {"level0-padded": "padded", "level3-misleading": "misleading"}


def contexts(mode):
    """The named contexts a run covers. Each is (name, [kinds])."""
    ladder = [("level" + str(n), LEVELS[n]) for n in LEVELS]
    if mode == "ladder":
        return ladder
    if mode == "add-one":       # nothing, plus one kind at a time
        return [("none", [])] + [("only-" + k, [k]) for k in KINDS]
    if mode == "leave-one-out":  # everything, minus one kind at a time
        return [("all", list(KINDS))] + [("no-" + k, [x for x in KINDS if x != k]) for k in KINDS]
    if mode == "controls":
        # level0-padded: no documentation, plus unrelated text as long as the level 4 documentation.
        # level3-misleading: level 3 with a few facts stated wrongly.
        return [("level0", LEVELS[0]), ("level0-padded", LEVELS[0]), ("level3", LEVELS[3]), ("level3-misleading", LEVELS[3])]
    if mode == "all":
        seen, out = set(), []
        for name, kinds in ladder + contexts("add-one") + contexts("leave-one-out") + contexts("controls"):
            key = (tuple(sorted(kinds)), VARIANTS.get(name))
            if key not in seen:
                seen.add(key)
                out.append((name, kinds))
        return out
    raise ValueError("unknown mode " + mode)


def render(layer, schema, kinds, variant=None):
    """The documentation text a model is shown for one context."""
    if variant == "misleading":
        layer = copy.deepcopy(layer)
        for ch in layer["misleading"]["changes"]:
            layer["tables"][ch["table"]]["columns"][ch["column"]][ch["field"]] = ch["value"]
    if variant == "padded":
        base = render(layer, schema, kinds)
        target = len(render(layer, schema, LEVELS[4]))
        lines, i = ["OFFICE NOTICES"], 0
        while len(base) + sum(len(x) + 1 for x in lines) < target:
            lines.append("  - " + layer["filler"][i % len(layer["filler"])])
            i += 1
        return base + chr(10) + chr(10).join(lines) + chr(10)
    kinds = set(kinds)
    out = []
    for table, cols in schema.items():
        doc = layer["tables"].get(table, {})
        out.append("TABLE " + table)
        if "descriptions" in kinds and doc.get("description"):
            out.append("  About: " + doc["description"])
        if "structure" in kinds:
            if doc.get("grain"):
                out.append("  Grain: " + doc["grain"])
            if doc.get("key"):
                out.append("  Key: " + ", ".join(doc["key"]))
            for j in doc.get("joins", []):
                out.append("  Join: " + j)
        out.append("  Columns:")
        for name, dtype in cols:
            cdoc = doc.get("columns", {}).get(name, {})
            line = "    " + name + " " + dtype
            if "descriptions" in kinds and cdoc.get("description"):
                line += " - " + cdoc["description"]
            if "units" in kinds and cdoc.get("units"):
                line += " Units: " + cdoc["units"]
            if "codes" in kinds and cdoc.get("codes"):
                line += " Values: " + "; ".join("'" + k + "' = " + v for k, v in cdoc["codes"].items()) + "."
            out.append(line)
        if "rules" in kinds and doc.get("rules"):
            out.append("  Rules:")
            out.extend("    - " + r for r in doc["rules"])
        out.append("")
    if "examples" in kinds:
        out.append("DEFINITIONS")
        out.extend("  - " + m for m in layer.get("metrics", []))
        out.append("")
        out.append("VERIFIED EXAMPLE QUERIES")
        for e in layer.get("examples", []):
            out.append("  Q: " + e["question"])
            out.append("  SQL: " + e["sql"])
        out.append("")
    return "\n".join(out).rstrip() + "\n"


if __name__ == "__main__":
    import duckdb

    ap = argparse.ArgumentParser(description="Print the documentation a model sees at one readiness level.")
    ap.add_argument("--db", default=str(HERE / "build" / "legacy.duckdb"))
    ap.add_argument("--level", type=int, choices=sorted(LEVELS), default=4)
    a = ap.parse_args()
    con = duckdb.connect(a.db, read_only=True)
    print(render(load_layer(), read_schema(con), LEVELS[a.level]))
