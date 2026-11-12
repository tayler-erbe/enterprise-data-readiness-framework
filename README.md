# Enterprise Data Readiness Framework

Most enterprise data isn't ready for AI. Not because the data is wrong, but because nobody has written down what it means in a form a machine can use.

AI query tools like Snowflake Cortex Analyst, Databricks Genie and Power BI Copilot are only as accurate as the semantic layer under them. The vendors' own numbers show it: once business definitions, joins and verified example questions are added, Snowflake reports about twice the accuracy of a plain model, and Databricks reports 84.5% against 52.4%. Building that layer means knowing, table by table, what each one is, who owns it, how it joins, and which rules apply. Most warehouses can't answer that today.

This framework does three things:

1. **Scores every table** from 0 (undocumented) to 4 (AI-ready), mostly with deterministic checks.
2. **Drafts what's missing** with AI, labeled unconfirmed and routed to the table's owner, on owned hardware for sensitive data.
3. **Publishes a portable semantic layer** that works in Snowflake, Databricks or a custom build, then tests it with questions whose answers are known.

**Tayler Erbe** · Document Intelligence Lab

## How it came about

While building accessible chart descriptions, I found that AI chart errors are mostly errors of meaning: the model doesn't know what the numbers stand for. The same problem decides whether text-to-SQL tools work on enterprise data. The companion research is in [semantic-visualizations-for-access](https://github.com/tayler-erbe/semantic-visualizations-for-access).

## What's here

| File | Contents |
| --- | --- |
| [`docs/framework.md`](docs/framework.md) | Readiness levels, signals, where AI helps, privacy tiers, prioritization, outputs |
| [`docs/architecture.md`](docs/architecture.md) | The pipeline, stage by stage, and its design rules |
| [`docs/roadmap.md`](docs/roadmap.md) | Research, framework, prototype, enrichment test, pilot, scale |
| [`research/`](research/) | What already exists: platforms, catalogs, open-source tools, standards, papers |
| [`scorer/`](scorer/) | Prototype scorer: reads a data dictionary export, assigns each table a level, writes a scorecard and owner work lists |
| [`docs/openmetadata.md`](docs/openmetadata.md) | What OpenMetadata covers, and why the scorer reads from it instead of living inside it |
| [`certainty/`](certainty/) | Two tests of how certain a model is about what data means, and whether that certainty is earned |
| [`certainty/testset/`](certainty/testset/) | 648 labelled columns in raw and clean form, covering 54 kinds of case from ready to garbage, with a tested answer key |
| [Proposal page](https://tayler-erbe.github.io/enterprise-data-readiness-framework/) | The idea on one page |

## Status

Research complete, November 2026. The finding: the pieces exist across platforms and catalogs, but nothing does the whole job. See [`research/`](research/).

Prototype scorer started, November 2026. It scores a synthetic export for an invented company, built with defects that are common in data dictionaries. One thing it already shows: a table list alone can't place anything above level 1. Level 2 needs column-level metadata. See [`scorer/`](scorer/).

Two certainty tests built, November 2026, not yet run on a model. The first asks what a column means from its name, type and a few rows, and whether the model's stated certainty is earned. The second asks business questions at five levels of documentation. See [`certainty/`](certainty/).
