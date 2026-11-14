# Running the test set inside Snowflake

This loads the raw test tables into a Snowflake account and asks two questions of it:

1. **What does Snowflake's own description feature write for each column?** It is asked twice: from names and types only, and with sample data.
2. **What verdict does a model hosted in Snowflake give?** It gets the same prompt the local harness uses, so the results are scored the same way.

**Status: built and tested locally with made-up replies. Every generated SQL file passes a Snowflake-dialect syntax check (`python check_sql.py`, needs `sqlglot`). The two procedure and function calls follow the examples in Snowflake's documentation. It has not been run inside an account, so account-side problems (permissions, a model your region doesn't offer, cost limits) can still appear on the first run.**

## Before you start

- **Use an account you are allowed to use for this.** A personal trial account is the safe choice. The data is generated and contains nothing real.
- **It costs credits.** Each description call and each verdict is a model request. Run the smoke test first and read the cost in Snowsight before running the rest.
- **Values are stored exactly as they arrived.** Whole numbers load as numbers, decimals with a fixed number of places keep those places, and everything else loads as text.
- **Only raw tables are loaded.** The clean tables and the labels stay on your machine, so nothing in the account can see the answer key.
- Your role needs the `SNOWFLAKE.CORTEX_USER` database role, and the model you pick must be offered in your region.

## Steps

```bash
cd certainty/platforms/snowflake
python make_sql.py --model llama3.3-70b      # writes sql/ ; pick a model your region offers
python check_sql.py                          # optional: syntax check of every file
```

In a Snowsight worksheet, with a database selected:

1. Run `sql/00_setup.sql`.
2. Run `sql/10_load_v00.sql`, then `sql/20_describe_v00.sql`.
3. In `sql/30_verdicts.sql`, run only the first statement (the smoke test).
4. Run the two queries in `sql/40_export.sql` and download each result as CSV: `descriptions.csv` and `verdicts.csv`.

```bash
python score_snowflake.py --verdicts verdicts.csv --descriptions descriptions.csv
```

That is 8 tables and 60 columns. If it looks right and the cost is acceptable, run the other `10_load` and `20_describe` files and the rest of `30_verdicts.sql`, then export and score again.

To remove everything afterwards: `DROP SCHEMA READINESS_TEST;`

## What the scores mean

- **Verdicts** get the same report as a local model: verdict right, dangerous, over-cautious, and so on.
- **Descriptions** are free text. Without a judge the script counts only whether a description was written and whether it contains any wording of doubt. Whether each description is right goes into `runs/descriptions_sheet.csv` for a reader or a judge model.

## Keeping it fair

- The description feature is used as documented, with and without sample data.
- The verdict prompt is identical to the one local models get.
- This tests a bare, undocumented table, which is the situation the test set is about. It says nothing about how Snowflake performs once a semantic model has been built, and it should not be reported as if it did.
- A feature that was not run is "not tested", never "fails".
