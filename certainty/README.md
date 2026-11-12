# Certainty test

How sure is an AI model about what the data means, and how much documentation does it take before it's right?

This kit measures that. It asks a model the same 20 questions about the same tables at five levels of documentation, several times each, and compares every answer with a known one. Five more questions can't be answered from the tables at all, to see whether the model says so.

**Status: built and tested, not yet run on a model.** There are no findings here yet. The only run so far is a dry run with made-up replies, which checks the pipeline and nothing else.

## What it measures

| Measure | The question it answers |
| --- | --- |
| Right | How often does the model get the known answer? |
| Stated confidence | How sure does it say it is? |
| Overconfidence | Stated confidence minus the share right. Zero is well calibrated |
| Confident and wrong | How often is it wrong while saying it's 80% sure or more? This is the costly case |
| Repeats agree | Asked the same thing again, does it give the same answer? |
| Declined | How often does it say the documentation isn't enough? |
| Reliability score | +1 for a right answer, 0 for declining, -1 for a wrong one. It rewards declining over guessing |
| Which signal tells right from wrong | Stated confidence, agreement across repeats and token probability, each scored from 0.5 (a coin) to 1.0 (perfect) |
| Calibration error and Brier score | Standard measures of how far stated confidence sits from the truth |

Published work on SQL generation finds that a model's stated confidence is its weakest signal, and that agreement across repeats and token probability do better. So the kit records all three. Token probability is collected when the local server returns it.

Agreement and accuracy are different things. A model can give the same wrong answer five times out of five. The report counts those questions separately.

## The data

The tables come from a synthetic workforce dataset, an invented insurer with about 8,700 staff. Every row is made up, and the true answers are known because the patterns were planted.

The source tables have plain names like `fact_assignment` and `annual_salary`. A model can guess those with no help, so they can't show what documentation is worth. `build_legacy.py` rewrites them the way an older business system stores them:

| What the legacy copy does | The wrong answer it invites |
| --- | --- |
| Short names: `ASG_HST`, `BASE_RT`, `ACT_CD` | Guessing the wrong table or column |
| Pay stored per month | An average salary of 7,938 where the answer is 95,456 |
| Coded values: `T62` is a retirement, `'2'` is female | A filter that matches no rows |
| Open rows end on 9999-12-31, never NULL | A date test that finds nobody |
| Rows entered in error are flagged void and kept | A headcount of 8,816 where the answer is 8,724 |
| People sit only at the lowest level of the org tree | A division with nobody in it |

Six tables: `PSN_MST` (people), `JB_REF` (jobs), `ORG_REF` (units), `ASG_HST` (assignment history), `ACT_LOG` (personnel actions), `LV_HST` (leave). The names and codes are invented for this test.

## The five levels

`semantic_layer.json` holds the complete documentation. `context.py` cuts it down to each level of the [readiness ladder](../docs/framework.md).

| Level | The model is shown |
| --- | --- |
| 0 Undocumented | Table names, column names and data types |
| 1 Described | Adds a short description of each table and column |
| 2 Usable | Adds grain, keys, joins, what each code means, and units |
| 3 Governed | Adds the rules: which rows to leave out and how to count |
| 4 AI-ready | Adds metric definitions and six verified example queries |

Level 1 descriptions are short on purpose ("Base rate of pay."). That's how most real dictionaries read. They name the thing without giving its unit or its grain.

The six example queries at level 4 are not the 20 test questions. A test checks that.

**The levels are my design, and the results depend on it.** I chose which facts sit at which level. To see what each kind of context is worth by itself, run the other two modes:

- `--mode add-one` shows the model nothing, then one kind of context at a time
- `--mode leave-one-out` shows everything, then removes one kind at a time

The six kinds are descriptions, structure, codes, units, rules and examples.

## Controls

`--mode controls` adds two contexts that change the text without adding true information:

| Control | What it is | What it tests |
| --- | --- | --- |
| `level0-padded` | No documentation, plus unrelated office notices as long as the level 4 documentation | Whether a longer prompt helps by length alone |
| `level3-misleading` | Level 3 with a few facts stated wrongly: pay as yearly, the gender codes swapped | What a confident, wrong description costs |

The model can't detect the misleading facts, because it never sees a row. That control measures the cost of a wrong description against the cost of a missing one.

The five unanswerable questions run in every context. They ask for things the tables don't hold: remote work, bonuses, who reports to whom, part-time hours, licences. The right response is to decline.

## Run it

Needs Python 3.10 or later with `duckdb`. The model runs on your own machine. Any server that speaks the OpenAI chat format works, including vLLM and Ollama.

```bash
cd certainty

# 1. Build the legacy tables from the synthetic source (the Parquet folder of the dataset)
python build_legacy.py --source <folder of parquet files>

# 2. Check the kit
SOURCE_DATA=<folder of parquet files> python -m unittest discover -s tests

# 3. See the pipeline work without a model
python run.py --dry-run

# 4. Run a model
python run.py --base-url http://localhost:8000/v1 --model <model name> --reps 5
python run.py --base-url http://localhost:11434/v1 --model <model name> --reps 5 --mode all
```

The default run is 5 levels x 25 questions x 5 repeats = 625 short requests. `--mode all` covers 17 contexts, so 2,125. A stopped run continues from where it left off when you repeat the command.

Results go to `runs/<model>/`: `report.md`, `summary.csv`, and `attempts.jsonl` with every reply's SQL, status and stated confidence.

Keep the temperature above zero. At zero the repeats are copies of each other, and agreement means nothing.

To put two models side by side, run each and then:

```bash
python report.py runs/<small model> runs/<large model>
```

Run at least one small and one large model. One study found that added context lowered a smaller model's accuracy.

## What the model sees, and what it doesn't

The model gets the documentation text and one question. It never sees a row. It writes one SQL query and states its confidence. The script runs that query on the local database, read-only, and compares the result with the known answer. Only a single `SELECT` is accepted.

The model can also decline, by saying the documentation isn't enough. A declined question counts as not right, and is reported separately.

## How the answers are checked

Each question has two queries: one on the plain source tables and one on the legacy tables. The tests check that the two agree, so a "known answer" that misreads the legacy tables is caught before any model is scored. The tests also check that every documented code exists in the data and that each trap in the table above changes the number.

## Limits

- One domain, one database, six tables, 20 questions. Enough to see a pattern, too few to rank models. The report gives a 95% interval on every accuracy figure so the small question count stays visible. Calibration is reported to vary from one schema to another, so a result here needs a second database before it's generalised.
- A right answer is judged by matching the query result on one copy of the data. A query with wrong logic could match by coincidence. The numeric questions make that unlikely, not impossible.
- Synthetic data is cleaner than real data, even with the planted defects.
- The questions are in plain English with exact wording. Real questions are vaguer.
- Stated confidence is what the model says. It's one view of certainty. Agreement across repeats is a second.
- The work this builds on, and what it adds, is in [`research/ai-judging-readiness.md`](../research/ai-judging-readiness.md). The search behind it was about 50 queries, not a systematic review.
- A model that has read a lot of HR schemas may guess some of these conventions. That is part of what the test measures, and it means a result here won't transfer to an unusual domain.
