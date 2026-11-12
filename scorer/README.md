# Readiness scorer

Stage 3 of the [roadmap](../docs/roadmap.md). It reads a data dictionary export and gives every table a level from 0 (undocumented) to 4 (AI-ready), using the checks in [`docs/framework.md`](../docs/framework.md). No AI. Every check is code, and it gives the same answer every time.

It's a prototype. It runs on synthetic data and on an OpenMetadata fixture. The sample is an invented company; nothing here comes from a real organization.

## What it found on the synthetic sample

24 tables for an invented company, built with defects that are common in data dictionaries: blank comments, encoding damage, a description that just repeats the table name, rules buried in prose, a stale `http://` link, coded columns with no lookup.

| Level | Tables |
| --- | ---: |
| 0 Undocumented | 5 |
| 1 Described | 14 |
| 2 Usable | 2 |
| 3 Governed | 2 |
| 4 AI-ready | 1 |

The full output is in [`examples/synthetic/output/`](examples/synthetic/output/).

The more useful finding: **a table list alone can't place anything above level 1.** Run the scorer on just the six columns a typical table list shows (Schema, Name, Comments, Columns, Rows, Indices) and every table lands at 0 or 1. Level 2 needs column descriptions, keys and lookups, and that page doesn't carry them. So a real run needs a column-level export too.

## Run it

Python 3.10 or later. Nothing to install.

```bash
cd scorer
python -m readiness examples/synthetic/tables.csv --columns examples/synthetic/columns.csv --out output
```

From OpenMetadata, save a page of `GET /api/v1/tables?fields=columns,owners,tableConstraints,extension,usageSummary,profile` and point the scorer at it:

```bash
python -m readiness --openmetadata examples/openmetadata/tables.json --out output
```

Tests:

```bash
python -m unittest discover -s tests
```

Options: `--target` (default target level, 4), `--coverage` (share of columns that must be described for level 2, 0.8), `--min-questions` (verified questions for level 4, 5), `--check-links` (request every link; off by default so the scorer never touches the network unless asked).

## What it writes

| File | For |
| --- | --- |
| `scorecard.md` | Leadership. Tables per level, per schema, what blocks the next level, rules sitting in prose, possible restricted tables |
| `worklist.md` | Owners. Their tables below target, ranked by usage x gap, with the exact thing to fix |
| `scores.csv` | Spreadsheets. One row per table with every check's result |
| `columns.csv` | Column scores: described, coded, decoded |
| `scores.json` | Anything downstream, such as the enrichment step |

## Input

**Tables CSV.** Needs `Name`; `Schema` almost always. Headers match loosely (case and spacing don't matter, and `Comments` or `Description` both work). Anything beyond those six columns is optional and holds confirmed fields: `Owner`, `Grain`, `Primary Key`, `Foreign Keys`, `Joins`, `Valid From`, `Valid To`, `Exclude From Reporting`, `Trust Level`, `Known Defects`, `Advisory`, `Advisory Date`, `In Semantic Layer`, `Verified Questions`, `Verified Questions Passed`, `Usage`, `Privacy Tier`, `Target Level`. Lists split on `;`.

**Columns CSV** (optional, but needed for level 2). `Schema`, `Table`, `Column`, `Data Type`, `Comments`, `Lookup` (the lookup table or value list), `Key` (`PK`), `Foreign Key`.

**OpenMetadata.** Owners, columns, primary and foreign key constraints, usage and row count come from the table entity. The framework's own fields (trust level, validity window, semantic layer status and so on) come from custom properties on the Table type, read from `extension`. The names are in `OM_EXTENSION_FIELDS` in [`readiness/load.py`](readiness/load.py). Column lookups come from a `lookup` custom property on columns.

## How each level is decided

A table reaches a level only when every check for that level and every level below it passes. Each check returns **pass**, **fail** or **can't tell**. Can't tell means the export doesn't hold enough to judge, and it never counts as a pass. I'd rather show a table at level 1 with "can't tell" than guess it up to level 2.

| Level | Check | Passes when |
| --- | --- | --- |
| 1 | Table description | Not blank |
| 1 | Readable description | Not a placeholder (`TBD`, `N/A`, a copy of the table name). Encoding damage (`Â`, `â€œ`) only warns, so one garbled character doesn't drop a described table to level 0 |
| 2 | Grain stated | `Grain` field, or the description says "one row per ..." |
| 2 | Keys or joins | Primary key, foreign key or confirmed join path. Indexes alone are "can't tell" |
| 2 | Columns described | At least 80% of columns have a readable description |
| 2 | Codes decoded | Every column ending in `_CD`, `_CODE`, `_TYP` points to a lookup, or is this table's own key |
| 3 | Named owner | Owner or steward present |
| 3 | Trust level | Recorded as a field |
| 3 | Rules out of prose | No validity window, reporting exclusion, trust note or known defect left only in the description |
| 3 | Advisory dated | Any advisory or known defect has a date |
| 3 | Links resolve | Every link in the description or advisory answers. Unchecked links are "can't tell" |
| 4 | In semantic layer | Recorded as in it |
| 4 | Verified questions | At least 5, and at least 90% pass |

Not scored, but flagged: short descriptions, `http://` links, a column count that disagrees with the column list, no row count, encoding damage in table or column descriptions, and names that suggest restricted data (race, health, HR notes, credit applications). That last one is a suggestion for tier C, never a decision. A steward assigns the tier.

## Calls I made

These are my readings of the framework. Each is easy to change.

- **Trust level is the level 3 usage rule every table needs.** Validity windows and exclusions don't apply to every table, but every table has a trust level, even if it's "system of record."
- **A rule found in prose blocks level 3 until it's a field.** If the description says "do not use for 2020 onward" and `Valid To` is empty, the table isn't governed yet. The rule exists. Nobody can query it.
- **Grain in prose counts for level 2.** The framework allows a pattern match. The work list still says to confirm it as a field.
- **A lookup table's own code column is decoded.** `COST_CTR_CD` in the cost centre code table is the decoder.
- **Priority is usage x gap, and only when usage is in the export.** Without usage the work list ranks by gap and says so. It doesn't invent a value.
- **The prose patterns are deliberately narrow.** They catch common phrasings. They'll miss others. That's the enrichment step's job (stage 5): a model pulls rules out of prose, and an owner confirms them.

## Not built yet

- Loaders for the export formats and APIs of specific data dictionary products.
- Spell checking ("ATRRIBUTES", "DELAGATE"). Needs a dictionary that knows warehouse abbreviations, or it flags every column name.
- Writing the score back to OpenMetadata as a custom property.
- Profile statistics by privacy tier (stage 2).
- Usage from query logs. Right now usage is whatever number the export carries.
