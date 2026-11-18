# Running the test set inside Databricks

This loads the raw test tables into a Databricks workspace and asks two questions of it:

1. **What verdict does a model hosted in Databricks give?** It gets the same prompt the local harness uses, through `ai_query`, so the results are scored the same way.
2. **What does Databricks' own description feature write for each column?** This is the "AI generate" button in Catalog Explorer.

**Status: built and tested locally with made-up replies. Every generated SQL file passes a Databricks-dialect syntax check, and all 720 prompts read back out of the SQL identical to the ones the local harness sends (`python check_sql.py`, needs `sqlglot`). The `ai_query` call follows the examples in Databricks' documentation. It has not been run inside a workspace, so workspace-side problems (permissions, an endpoint name your workspace doesn't list, rate or spend limits) can still appear on the first run.**

## Before you start

- **Use a workspace you are allowed to use for this.** A personal trial or free workspace is the safe choice. The data is generated and contains nothing real.
- **It costs money or quota.** Each verdict is a model request. Run the smoke test first and check the cost before running the rest.
- **`ai_query` does not run on a Classic SQL warehouse.** Use a serverless or pro SQL warehouse, or a notebook on a recent runtime.
- **Pick an endpoint your workspace lists.** Open Serving in the workspace and copy the name of a chat model. The default here is `system.ai.meta-llama-3-3-70b-instruct`, the name used in Databricks' own examples.
- **Values are stored exactly as they arrived.** Whole numbers load as numbers, decimals with a fixed number of places keep those places, and everything else loads as text.
- **Only raw tables are loaded.** The clean tables and the labels stay on your machine, so nothing in the workspace can see the answer key.

## Steps

```bash
cd certainty/platforms/databricks
python make_sql.py --endpoint system.ai.meta-llama-3-3-70b-instruct
python check_sql.py                          # optional: syntax and round-trip check of every file
```

In the SQL editor, with a catalog selected (`USE CATALOG <name>;`):

1. Run `sql/00_setup.sql`.
2. Run `sql/10_load_v00.sql`.
3. In `sql/30_verdicts.sql`, run only the first statement (the smoke test).
4. **Descriptions, by hand.** In Catalog Explorer open each of the 8 tables in the `readiness_test` schema whose name contains `_v00_`, click **AI generate** above the column list, and accept every suggested column comment without editing it. Databricks documents no SQL or API way to ask for these, so this step can't be scripted.
5. Run the two queries in `sql/40_export.sql` and download each result as CSV: `verdicts.csv` and `comments.csv`.

```bash
python score_databricks.py --verdicts verdicts.csv --comments comments.csv
```

That is 8 tables and 60 columns. If it looks right and the cost is acceptable, run the other `10_load` files and the rest of `30_verdicts.sql`, then export and score again. Generating descriptions for all 96 tables is 96 rounds of clicking; the first 8 are enough for a first look, and the report states how many columns it covers.

To remove everything afterwards: `DROP SCHEMA readiness_test CASCADE;`

## What the scores mean

- **Verdicts** get the same report as a local model: verdict right, dangerous, over-cautious, and so on. A request that came back with an error is counted as a reply that could not be read. It is not dropped.
- **Descriptions** are free text. Without a judge the script counts only whether a description was written and whether it contains any wording of doubt. Whether each description is right goes into `runs/descriptions_sheet.csv` for a reader or a judge model.

## Keeping it fair

- The description feature is used as documented. Databricks says it reads "object metadata, such as the table schema and column names", so the report files it under "from names and types only". Snowflake's feature can also be given sample data, and the Snowflake kit reports that separately. Compare like with like.
- Accept every suggestion unedited. Editing or skipping a suggestion changes what is being measured.
- The verdict prompt is identical to the one local models and the Snowflake kit get.
- This tests a bare, undocumented table, which is the situation the test set is about. It says nothing about how Databricks performs once comments, a metric view or a Genie space have been built, and it should not be reported as if it did.
- Genie (question answering) is not covered by this kit.
- A feature that was not run is "not tested", never "fails".
