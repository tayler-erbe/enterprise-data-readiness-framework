# Test set: can a detector tell usable data from garbage?

648 labelled columns across 84 tables. Every column is one of 54 kinds of case, and each case appears 12 times with different values, names and subject areas. Every table exists twice: `raw`, as the data arrives, and `clean`, as it should be after correct preparation.

**Status: the data is built and its answer key is tested. No model has been run on it yet.**

## Four verdicts

Each column carries the verdict a careful reviewer should reach.

| Verdict | Meaning | Cases | Columns |
| --- | --- | ---: | ---: |
| READY | Usable as it is | 10 | 120 |
| FIXABLE | Usable after a fix the data itself determines | 25 | 300 |
| NEEDS_CONTEXT | Can't be read reliably without a data dictionary or the owner | 13 | 156 |
| GARBAGE | No fix recovers it | 6 | 72 |

The costly mistake is treating NEEDS_CONTEXT as FIXABLE: assuming a meaning, applying a confident fix, and being wrong. This set is built to catch that.

## The cases

**READY (10).** Controls. Identifiers, names, ISO dates, amounts whose name states the currency, clean categories, named counts, weekday names, emails, named percentages, and a code column with its description beside it.

**FIXABLE (25).**

| Kind | Cases |
| --- | --- |
| Text | Stray spaces and mixed capitals; garbled accented letters; one category spelled several ways; typos one keystroke from a common value; yes and no written many ways; several facts packed into one cell |
| Dates and times | Several unambiguous formats in one column; slash dates settled by a day above 12; spreadsheet day numbers; seconds since 1970; milliseconds since 1970 |
| Numbers | Thousands separators; decimal commas; currency symbols; percent signs; identifiers that picked up a decimal point; postal codes that lost leading zeros |
| Units | Heights written three ways with their units; inches and centimetres mixed where the ranges can't overlap; six-packs revealed by the line total |
| Missing and impossible | An impossible number standing in for missing; N/A and NULL as words; a far-future date for no date; ages no person can have |
| Codes | A weekday number whose convention the date beside it reveals |

**NEEDS_CONTEXT (13).** Slash dates where every day and month is 12 or below; a currency nobody named; whole numbers that could be dollars or cents; pay that could be monthly or annual; weight in pounds or kilograms; a 1/2 flag; zeros that mean none or not recorded; two-letter codes valid as both states and countries; a timestamp with no zone; a weekday number alone; a quantity alone; opaque codes; plausible numbers under a meaningless name.

**GARBAGE (6).** Nearly all blank; one value in every row; random strings; text cut off at ten characters; a money column full of dates and names; filler such as "test" and "asdf".

## Why the answer key can be trusted

Collected data comes with a question: did whoever cleaned it get it right? Here the clean table is made first and the raw one is derived from it, so the key is exact by construction. Three tests then check it with separate code.

1. **Every FIXABLE case has a second, independent fixer.** It reads only the raw column and must reproduce the clean column exactly. This is checked on 25 seeds in 6 subject areas for each case.
2. **Every NEEDS_CONTEXT case with competing readings is generated under each reading from the same seed, and the raw columns must be identical.** That proves the values can't settle it. Eleven cases are checked this way.
3. **Every READY and GARBAGE case is checked for the property it claims**, such as raw equal to clean, or at least 90% blank.

Nothing here has been published before, so no model has seen it.

## Files

| File | Contents |
| --- | --- |
| [`cases.py`](cases.py) | The 54 cases, with their fixers |
| [`build.py`](build.py) | Deals the cases into tables and writes the files |
| [`data/raw/`](data/raw/), [`data/clean/`](data/clean/) | 84 tables, 120 rows each, in both forms |
| [`data/labels.csv`](data/labels.csv) | One row per labelled column: verdict, issue, meaning, the true reading and the others that fit, what settles it, the fix, how many rows change |
| [`tests/`](tests/) | The checks above |

```bash
cd certainty/testset
python -m unittest discover -s tests
python build.py --variations 12        # rebuilds data/; raise the number for more examples
```

Python 3.10 or later. Nothing to install.

## What is not in it yet

- **Table-level failures.** Duplicate rows, a missing or misplaced header row, columns shifted sideways, tables at the wrong grain.
- **Cross-column rules.** A city that doesn't match its postal code; an end date before a start date.
- **Real tables.** Generated errors are cleaner than real ones. A small set of real dirty-and-clean pairs would check realism. The well-known public ones are probably memorised by models, so they belong in a control group, not the main test.
- **Wide tables.** These have about eight columns. Real ones have dozens.
- **A harness.** The code that shows these tables to a model and scores its verdicts isn't written. The [column meaning test](../columns/) has the parts it needs.
- **More subject areas.** Six now: retail, clinic, logistics, banking, hotel, utilities.

Kinds of failure and where they come from are catalogued in [`research/column-meaning-and-test-data.md`](../../research/column-meaning-and-test-data.md).
