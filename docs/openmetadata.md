# OpenMetadata as a base

The research named OpenMetadata the best open-source base to build on. For the prototype I'm reading from it, not building inside it.

## What it gives the framework

I checked the Table entity against OpenMetadata's JSON schema (`openmetadata-spec/.../entity/data/table.json`, main branch, November 2026). It holds most of what levels 1 to 3 need:

| Framework signal | OpenMetadata field |
| --- | --- |
| Table and column descriptions | `description`, `columns[].description` |
| Keys and joins | `columns[].constraint` (`PRIMARY_KEY`), `tableConstraints` (`PRIMARY_KEY`, `FOREIGN_KEY` with `referredColumns`), `joins` |
| Owner | `owners` (older releases: a single `owner`) |
| Value, for priority | `usageSummary` daily, weekly and monthly counts |
| Row count | `profile.rowCount` |
| Grain, trust level, validity window, semantic layer status | Nothing built in. Custom properties on the Table type, stored in `extension` |

Data Insights already computes description and ownership coverage, recomputed daily. A table counts as described there only when the table and all its columns are described.

## What it doesn't give

- **A ladder.** Coverage is a percentage. It can't say "this table is usable but not governed."
- **Rules as fields.** Nothing pulls "do not use after Fall 2010" out of a description.
- **An unconfirmed state for AI drafts.** The documentation agent with accept or reject is in Collate, the paid edition. Whether it can run on a self-hosted model is still unverified.
- **Connectors for every data dictionary tool.** Some dictionary products have none. Getting their content in means a custom ingestion or a CSV.

## The call

The scorer stays a small, standalone tool. It has two loaders: a CSV for data dictionary exports and the OpenMetadata API response. It doesn't need a server to run, so it works on a dictionary export today and on a catalog later.

If the pilot ends up on OpenMetadata, it becomes the system of record for confirmed fields (as custom properties), and the scorer writes each table's level back to it. That keeps the ladder visible where people already look.

Reasons not to start inside it: running OpenMetadata means a server, a database, a search index and ingestion pipelines. That's real infrastructure for a question I can answer with a CSV. And an organization choosing between warehouse platforms will find that each has its own catalog. A scorer tied to one catalog would have to be rebuilt for whichever one wins.

## Still to check

- Load the fixture shape against a running OpenMetadata instance. The loader is written to the schema, not tested against a live server.
- Whether custom properties on columns (for `lookup`) show up in the API the way the loader expects.
- Collate's documentation agent with a self-hosted model.
