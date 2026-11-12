# Column meaning, preprocessing, ambiguity, and where to get test data

Research as of 12 November 2026, for a test of one question: shown a table's names, data types and a few random rows, can an AI model say what each column means, say what has to be done to make it usable, and state a certainty that matches how often it's right?

"Opened" means the source page was read. Tables A to C are a synthesis of the sources listed at the end, not a copy of any one paper's taxonomy. Contamination ratings are judgement from a source's age and exposure unless a study is cited.

## Summary

- **No study found measures whether a model's certainty about column meaning or data cleaning is accurate.** The nearest work is on question answering over tables.
- **The well-known dirty-and-clean datasets are probably memorised.** Use them as a control, not as the test.
- **The best test data is clean tables nobody has seen, dirtied by a tool that logs every change.** The log is the answer key.
- **More rows resolve format questions, not meaning questions.** A day greater than 12 settles day-month order. No number of rows tells you the currency.
- **People do badly at this too.** Shown 10 values and 78 choices, crowd workers agreed on the right column type about a third of the time.

## Table A: kinds of column meaning

| Category | Sub-kinds | Example |
| --- | --- | --- |
| Record identifier | surrogate key, natural key, foreign key | CUST_ID 004512 |
| Numeric-looking code | ZIP or postcode, phone, account, SKU, ISBN | 02134 |
| Categorical code | needs a lookup; cryptic abbreviations | experience = "B" |
| Flag | Y/N, 1/0, T/F, 1/2 | ACTIVE = 1 |
| Person attribute | sex or gender, marital status, age, birth date | M / F / U / X |
| Name or free text | person, organisation, description, several facts in one cell | "J. Smith 12.02.70 New York" |
| Calendar date | ISO, day-first, month-first, Excel serial, two-digit year | 03/04/2025 |
| Time or timestamp | local or UTC; epoch in seconds, milliseconds or finer | 1731400000 |
| Date part or period | day of week, day of month, week, fiscal period | DAY = 1 to 7 |
| Duration or interval | start and end, open-ended end date | 9999-12-31 |
| Count or quantity | units, packs, cases | QTY = 6 |
| Physical measure | length, mass, volume, each with a unit | 62; 5'8" |
| Money | currency, minor units, scale, gross or net, period | 1200 |
| Rate, ratio or percent | 0 to 1 or 0 to 100, basis points | 0.05 or 5 |
| Rank, order or score | rank, grade, rating | 1st, #1 |
| Geography | country or state code, city, latitude and longitude | "CA", "AL" |
| Contact | email, URL, address | |
| Status | state, type, class, category | STATUS = 3 |
| Missing-value marker | unknown, not applicable, not asked, masked | -1, N/A, blank |
| Derived or aggregate | totals, snapshots, level of aggregation | sales per product or per group |

Existing vocabularies: Sherlock's 78 types, SOTAB's 91 Schema.org types, Tableau's 12 geographic roles, Frictionless Table Schema's 16 field types, and FHIR's 17 codes for why a value is missing.

## Table B: preprocessing operations

"Automatic?" reads: Yes = safe to automate. Partly = a tool can detect or propose it, and someone confirms. Owner = needs the person who owns the data.

| Operation | When needed | What must be known | Automatic? |
| --- | --- | --- | --- |
| Trim, case, whitespace | always | whether case carries meaning | Yes |
| Encoding repair | garbled characters | source encoding | Partly |
| Header detection and naming | header row not found | which row is the header | Partly |
| Reshape to tidy form | variables stored in headers or rows | what the variables are | Partly |
| Split embedded values | several facts in one cell | delimiter or pattern | Partly |
| Fix misfielded values | value in the wrong column | what each column means | Partly |
| Storage type inference | loading CSV or Excel | a large enough sample | Yes, falling back to text |
| Keep identifiers as text | ZIP, phone, card numbers | that it's a code, not a quantity | Partly |
| Date parsing | any date string | day-month order, century, calendar | Partly |
| Excel serial to date | five-digit "dates" | 1900 or 1904 date system | Owner |
| Epoch to timestamp | large integers | unit and starting point | Partly, from magnitude |
| Time-zone normalisation | timestamps | source zone, daylight saving | Owner |
| Unit conversion | mixed or foreign units | the unit of each value | Owner, unless a unit column exists |
| Parse compound measures | 5'8", "6 x 330ml" | the pattern and the target unit | Partly |
| Currency normalisation | amounts | currency, minor units, rate date | Owner |
| Scale normalisation | thousands, cents, percent | the multiplier | Owner |
| Decimal and group separators | "1.234,56" | locale | Partly |
| Missing-marker to null | -1, 9999, N/A, 0 | which values are markers, and what each means | Partly |
| Imputation | nulls | why the values are missing | Owner decides |
| Code decoding | coded values | the lookup table and its version | Owner |
| Category harmonisation | synonyms, typos, variants | the canonical list | Partly |
| Flag normalisation | Y/N, 1/2 | which value means true | Partly |
| Outlier handling | values far from the rest | the plausible range | Detect yes, fix no |
| Rule checks | nulls, uniqueness, dependencies | the rules | Yes, once rules exist |
| Deduplication | the same entity twice | match keys | Partly |
| Schema matching | merging sources | synonyms and same-name-different-meaning | Partly |
| Aggregation and time alignment | sources at different grain or date | grain and snapshot date | Owner |
| Money as decimal, not float | arithmetic on money | precision | Yes |

## Table C: where ambiguity comes from

| Ambiguity | Competing readings | What resolves it | From the data alone? |
| --- | --- | --- | --- |
| DAY 1 to 7 | weekday starting Monday or Sunday, day of month, day in a period | maximum over more rows; a nearby date column; owner | Sometimes |
| Day-month order | day first or month first | any value with a day above 12; locale; owner | Sometimes |
| Mixed date formats in one column | some rows swapped | cross-check with another date; source system | Sometimes |
| Two-digit year | 19xx or 20xx | plausible range | Sometimes |
| Five-digit integer | Excel serial, ZIP, identifier, count | name, neighbours, range | Sometimes |
| Excel 1900 or 1904 | a 1,462-day shift | workbook setting | No |
| Large integer time | seconds, milliseconds, finer | magnitude | Usually |
| Timestamp with no zone | local or UTC | zone column, system documentation | No |
| Bare number, such as 62 | height, waist, age, weight | name, unit column, distribution, neighbours | Sometimes |
| Unit of a measure | inches or centimetres, pounds or kilograms | unit column; range, for human-scale measures | Sometimes |
| QTY | units, packs, ounces, millilitres | unit-of-measure column; price divided by quantity | Sometimes |
| Amount: currency | USD, CAD, EUR | currency column, country, owner | No |
| Amount: scale | dollars, cents, thousands | reconcile against a known total | Sometimes |
| Amount: basis | gross or net, monthly or annual, with or without tax | owner or data dictionary | No |
| Percent | 0.05 or 5 | range over more rows | Sometimes |
| Letters M / F / U / X | gender, marital status, size, another code | number of distinct values, name, lookup table | Sometimes |
| 0/1 or 1/2 flags | which value means true | lookup table or owner | No |
| Two-letter place code | US state or country (AL is Alabama or Albania) | other values in the column; a country column | Sometimes |
| Marker or real value | 0, -1, 99999, 9999-12-31, blank | a spike in frequency, an impossible value; the meaning needs the owner | Detect sometimes; meaning no |
| Kind of missing | unknown, not applicable, not asked, masked | source system | No |
| "NULL" or "NA" text | missing, or a real surname or code | column type, owner | Sometimes |
| Abbreviated column name | several expansions | table name, values, data dictionary | Sometimes |
| Granularity | city, location or birthplace | the other columns | Sometimes |
| Rank, count or sales | which of the three | name, neighbours | Sometimes |
| Aggregation level or snapshot date | per item or per group; yesterday or last week | documentation | No |

The last column matters for the test. Where it says "No," a model that claims high certainty from the rows alone is wrong to, whatever it guesses.

## How many sample rows are needed

No study found gives a threshold. The evidence is indirect.

- **People with 10 values do badly.** In Sherlock (2019), crowd workers shown 10 values and 78 types reached a consensus F1 of 0.32. The model scored 0.89 on full columns, and 0.95 when the least-confident 10% of columns were set aside for a person.
- **Values alone are often not enough.** Sato (2020) calls predicting a type from values alone "an under-determined problem in many cases." Florence, Warsaw and London could be a location, a city or a birthplace. The other columns settle it; more rows don't.
- **LLM studies use about five rows.** Korini and Bizer (2023, 2025) put the first five rows in the prompt.
- **More samples help a little.** ArcheType (2024) uses five samples per column. Going from 3 to 10 improves results, but "the improvements are slight."
- **Column names are hard for people.** In NameGuess (2023), annotators shown 10 values expanded abbreviated column names correctly about 43% of the time. GPT-4 reached 73.4% with table context.
- **Answer keys disagree with each other.** GitTables (2021) matched a hand-labelled benchmark on 54% of 321 columns, often differing on granularity.
- **Loaders sample far more for storage types.** BigQuery scans up to 500 rows; DuckDB samples 20,480 by default.

## Test data sources

| Source | Gives | Size | Licence | Risk the model has seen it | Opened |
| --- | --- | --- | --- | --- | --- |
| [Raha and Baran sets](https://github.com/BigDaMa/raha) | Dirty and clean pairs, per cell | 7 tables: beers, flights, hospital, movies, rayyan, tax, toy | Apache-2.0 | High: public for years, reused by most cleaning papers | Yes |
| [CleanML](https://github.com/chu-data-lab/CleanML) | Dirty data and cleaned versions | 14 datasets | Not stated | High: includes Titanic and census data | Yes |
| [AutoDCWorkflow](https://arxiv.org/abs/2412.06724) | Raw table, hand-cleaned table and the cleaning steps | 96 tables from 6 datasets | Not found | Medium. Download location not found | Abstract |
| [GitTables](https://zenodo.org/records/6517052) | Columns labelled with meaning | 1 million tables | CC0 | Medium: public, but any one table is rarely seen | Yes |
| [SOTAB](https://webdatacommons.org/structureddata/sotab) | Labelled column meaning | 162,351 columns, 91 types | Not stated | Medium to high | Yes |
| [Sherlock / VizNet](https://github.com/mitmedialab/sherlock-project) | Labelled columns | 686,765 columns, 78 types | Code MIT | High: a standard benchmark since 2019 | Yes |
| [ArcheType sets](https://github.com/penfever/ArcheType) | Domain-specific type benchmarks | 20 to 91 labels | MIT | Medium | Yes |
| [NameGuess](https://github.com/amazon-science/nameguess) | Abbreviated column names with full meanings | 9,218 names, 895 tables | Apache-2.0 | Medium | Yes |
| [tab_err](https://github.com/calgo-lab/tab_err) | Tool: dirties a clean table and returns a mask of every change | 12 error types, including wrong unit, wrong type, garbled text, typo, swapped values | Apache-2.0 | Low: output is new each run | Yes |
| [Jenga](https://github.com/schelterlabs/jenga) | Tool: missing values, broken encodings, numeric and text errors | | GPL-3.0 | Low. Last commit October 2022 | Yes |
| [BART](https://github.com/dbunibas/BART) | Tool: rule-violation and random errors | | MIT | Low | Yes |
| [Synthea](https://github.com/synthetichealth/synthea) | Fully synthetic health tables | Unlimited | Apache-2.0 | Rows low; the schema is public | Yes |
| [tabmemcheck](https://github.com/interpretml/LLM-Tabular-Memorization-Checker) | Tool: tests whether a model has memorised a table | | MIT | n/a | Yes |

### What research says about memorisation

- ["Elephants Never Forget"](https://arxiv.org/abs/2404.06209): GPT-3.5 and GPT-4 had memorised the opening rows of every tested dataset public before 2021. Datasets released after training showed no evidence of it.
- ["Evaluating Latent Knowledge of Public Tabular Datasets"](https://arxiv.org/abs/2510.20351): contamination appeared only for the famous, meaning-rich sets. Their summary: "LLMs do not remember data, but they remember meaning."
- The memorisation tests can't prove a model has not seen a table. Their authors say so.
- Renaming columns to hide a dataset removes the signal this test measures. Unseen data is the better route.
- New rows aren't automatically safe. A recurring public release often reuses an old schema, so the column meanings may be known even when the rows are new.

### Recommendation

1. **Main test data: clean tables generated for the test, dirtied with a logging tool.** The answer key is exact and the data can't have been memorised.
2. **Label column meaning by construction.** The generator knows what each column is, including when two meanings fit the sample equally well.
3. **A small set of real paired data as a realism check.** One paper argues that rule-based injected errors miss patterns found in real dirty data.
4. **The famous sets as a control**, to show what a memorised score looks like.

## Not found

- Any study measuring a model's confidence calibration on column type annotation or data cleaning.
- Any study giving a row-count threshold for reliable column typing.
- Any study of how often real business column names are ambiguous.

About 100 searches and opened pages across the two research passes. Not a systematic review.

## Sources

Opened and read: Rahm and Do 2000, ["Data Cleaning: Problems and Current Approaches"](https://egonzal5.github.io/files/data_cleaning.pdf); Abedjan et al. 2016, ["Detecting Data Errors"](https://cs.uwaterloo.ca/~ilyas/papers/AbedjanVLDB2016.pdf); Kandel et al. 2011, [Wrangler](https://homes.cs.washington.edu/~jheer/files/wrangler.pdf); Hulsebos et al. 2019, [Sherlock](https://arxiv.org/pdf/1905.10688); Zhang et al. 2020, [Sato](https://arxiv.org/pdf/1911.06311); Korini, Peeters and Bizer 2022, [SOTAB](https://ceur-ws.org/Vol-3320/paper1.pdf); Korini and Bizer 2023, [Column Type Annotation using ChatGPT](https://arxiv.org/abs/2306.00745); Feuer et al. 2024, [ArcheType](https://arxiv.org/pdf/2310.18208); Zhang et al. 2023, [NameGuess](https://aclanthology.org/2023.emnlp-main.820.pdf); Hulsebos, Demiralp and Groth 2021, [GitTables](https://arxiv.org/pdf/2106.07258); Narayan et al. 2022, ["Can Foundation Models Wrangle Your Data?"](https://www.vldb.org/pvldb/vol16/p738-narayan.pdf); Zhou et al. 2026, [survey of data preparation with LLMs](https://arxiv.org/html/2601.17058); Abeysooriya et al. 2021, ["Gene name errors: Lessons not learned"](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1008984); [Frictionless Table Schema](https://datapackage.org/standard/table-schema/); [FHIR NullFlavor](https://www.hl7.org/fhir/R4/v3/NullFlavor/cs.html); [UCUM](https://ucum.org/ucum); [DuckDB CSV auto-detection](https://duckdb.org/docs/2.0/data/csv/auto_detection.html); [BigQuery schema auto-detection](https://docs.cloud.google.com/bigquery/docs/schema-detect); [Excel date systems](https://support.microsoft.com/en-us/office/date-systems-in-excel-e7fe7167-48a9-4b96-bb53-5612a800b487).

Not verified: Kim et al. 2003, "A Taxonomy of Dirty Data" (paywalled; existence confirmed); Müller and Freytag 2003; Oliveira et al. 2005; Ilyas and Chu 2019; Potter's Wheel; REIN and ED2 details; AutoDCWorkflow's download location; licences for SOTAB, CleanML and Sherlock's data; two 2026 papers on overconfidence in tabular question answering, seen in search summaries only.
