# Test set: can a detector tell usable data from garbage?

720 labelled columns across 96 tables, plus 120 whole files. Every one is an example of one of 70 kinds of case, and each case appears 12 times with different values, names and subject areas. Everything exists twice: `raw`, as the data arrives, and `clean`, as it should be after correct preparation.

**Status: the data, its answer key and the scoring harness are built and tested. No model has been run on it yet.**

## Four verdicts

Each column or file carries the verdict a careful reviewer should reach.

| Verdict | Meaning | Column cases | Columns | File cases | Files |
| --- | --- | ---: | ---: | ---: | ---: |
| READY | Usable as it is | 11 | 132 | 1 | 12 |
| FIXABLE | Usable after a fix the data itself determines | 27 | 324 | 7 | 84 |
| NEEDS_CONTEXT | Can't be read reliably without a data dictionary or the owner | 16 | 192 | 1 | 12 |
| GARBAGE | No fix recovers it | 6 | 72 | 1 | 12 |

The costly mistake is treating NEEDS_CONTEXT as FIXABLE: assuming a meaning, applying a confident fix, and being wrong. The harness calls that **dangerous** and reports it separately, because an analysis agent would run on that column and report a result.

## The cases

**READY (11 column, 1 file).** Controls. Identifiers, names, ISO dates, amounts whose name states the currency, clean categories, named counts, weekday names, emails, named percentages, a code column with its description beside it, amounts with a currency column beside them, and a tidy file.

**FIXABLE (27 column, 7 file).**

| Kind | Cases |
| --- | --- |
| Text | Stray spaces and mixed capitals; garbled accented letters; one category spelled several ways; typos one keystroke from a common value; yes and no written many ways; several facts packed into one cell |
| Dates and times | Several unambiguous formats in one column; slash dates settled by a day above 12; spreadsheet day numbers; seconds since 1970; milliseconds since 1970 |
| Numbers | Thousands separators; decimal commas; currency symbols; percent signs; identifiers that picked up a decimal point; postal codes that lost leading zeros |
| Units | Heights written three ways with their units; inches and centimetres mixed where the ranges can't overlap; six-packs revealed by the line total; pounds and kilograms with a unit column beside them |
| Missing and impossible | An impossible number standing in for missing; N/A and NULL as words; a far-future date for no date; ages no person can have |
| Across columns | A weekday number whose convention the date beside it reveals; a line total that disagrees with quantity times price |
| Whole file | Duplicate rows; title lines above the header; the header repeated part-way down; subtotal and total rows among the data; blank rows and a blank column; an unquoted comma that shifts part of a row sideways; months spread across columns |

**NEEDS_CONTEXT (16 column, 1 file).** Slash dates where every day and month is 12 or below; a currency nobody named; whole numbers that could be dollars or cents; pay that could be monthly or annual; weight in pounds or kilograms; a 1/2 flag; zeros that mean none or not recorded; two-letter codes valid as both states and countries; a timestamp with no zone; a weekday number alone; a quantity alone; opaque codes; plausible numbers under a meaningless name; rows that end before they start; a state that contradicts its postal code; one code with two descriptions; a file with no header and only ambiguous numbers.

**GARBAGE (6 column, 1 file).** Nearly all blank; one value in every row; random strings; text cut off at ten characters; a money column full of dates and names; filler such as "test" and "asdf"; a saved error page in place of a data file.

## Why the answer key can be trusted

Collected data comes with a question: did whoever cleaned it get it right? Here the clean version is made first and the raw one is derived from it, so the key is exact by construction. Separate code then checks it.

1. **Every FIXABLE case has a second, independent fixer.** It reads only the raw column or file and must reproduce the clean one exactly. Checked on 25 seeds in 6 subject areas for each of the 34 fixable cases.
2. **Every NEEDS_CONTEXT case with competing readings is generated under each reading from the same seed, and the raw values must be identical.** That proves the values can't settle it. Eleven cases are checked this way.
3. **Every conflict case is checked to really contain the conflict**, and every READY and GARBAGE case for the property it claims.

Nothing here has been published before, so no model has seen it.

## The harness

`detect.py` shows a model one raw table (name, columns, types and ten sample rows) and asks about one column: the verdict, the fix, its certainty, any assumption it made, and the cleaned values for the first five rows. Those values are compared with the clean table, so a model that says "fixable" has to show the fix. Whole files are shown as numbered lines and judged for layout.

The sample always includes some of the rows that need changing. Ten random rows would often miss the problem, and READY would then be the honest answer.

The report gives the share of verdicts right, the dangerous share, the over-cautious share, whether fixes were named and carried out, whether stated certainty separates right from wrong, a table of what the model said against the truth, and a line for every kind of case. On two-reading columns it also reports how often a guessed fix landed on the true reading. Near 50% means guessing.

```bash
cd certainty/testset
python -m unittest discover -s tests                 # 47 checks
python baselines.py                                  # no-AI baselines, real results
python build.py --variations 12                      # rebuilds data/; raise the number for more examples
python detect.py --dry-run                           # the pipeline, with made-up replies
python detect.py --base-url http://localhost:8000/v1 --model <model name>
```

Building and testing need Python 3.10 or later and nothing else. Running a model also needs `duckdb`, for code shared with the other tests. A full run is (720 columns + 120 files) x 3 repeats = 2,520 short requests. A stopped run continues when you repeat the command.

## A floor to beat: checks with no AI

[`baselines.py`](baselines.py) scores three no-AI checks on the same columns with the same measures. These are real results; see [`baselines_report.md`](baselines_report.md).

| Measure | Accept everything | Generic quality rules | Rules plus shape profiling |
| --- | ---: | ---: | ---: |
| Verdict right | 18% | 28% | 40% |
| Needs-context or garbage columns passed as usable | 100% | 91% | 86% |
| Needs-context columns passed as usable | 100% | 100% | 94% |
| Usable columns held back | 0% | 0% | 0% |

Both checks read all 120 rows of a column and are plain implementations written for this test, not any vendor's product. Most needs-context cases were built so the raw values are identical under each reading, so a value-only check scoring 0% on them is true by construction. The table shows what kind of evidence the problem needs, and the floor a model has to beat.

## Files

| File | Contents |
| --- | --- |
| [`cases.py`](cases.py) | The 60 column cases, with their fixers |
| [`tables.py`](tables.py) | The 10 whole-file cases, with their fixers |
| [`build.py`](build.py) | Deals the cases into tables and writes the files |
| [`detect.py`](detect.py), [`score_detect.py`](score_detect.py) | The harness and its report |
| [`data/raw/`](data/raw/), [`data/clean/`](data/clean/) | 96 tables, 120 rows each, in both forms |
| [`data/labels.csv`](data/labels.csv) | One row per labelled column: verdict, issue, meaning, the true reading and the others that fit, what settles it, the fix, how many rows change |
| [`data/files_raw/`](data/files_raw/), [`data/files_clean/`](data/files_clean/), [`data/file_labels.csv`](data/file_labels.csv) | The 120 whole files and their labels |

## Real tables, as a control

[`../realdata/`](../realdata/) downloads five public dirty-and-clean table pairs (66 columns, 45 with known errors) and runs the same detector on them. They're widely used and probably memorised, so they're a control group and not part of the main test.

## Limits

- **Generated errors are tidier than real ones.** Each column here has one problem. Real columns have several at once.
- **The tables are narrow.** About eight columns. Real ones have dozens, and the evidence for one column can be far from it.
- **Six subject areas**: retail, clinic, logistics, banking, hotel, utilities.
- **Twelve examples per case** is enough to see whether a model handles a kind of failure, and too few to measure small differences between models.
- **The verdict labels are mine.** FIXABLE and NEEDS_CONTEXT cases are backed by tests. Whether a nearly blank column is GARBAGE or merely low-value is a judgement.
- **Not covered yet:** tables at the wrong grain, values that are plausible and wrong, drift over time, free-text fields, several problems in one column.

Kinds of failure and where they come from are catalogued in [`research/column-meaning-and-test-data.md`](../../research/column-meaning-and-test-data.md).
