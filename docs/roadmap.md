# Roadmap

Research comes first. Every later stage depends on knowing what already exists.

| Stage | Question | Output | Status |
| --- | --- | --- | --- |
| 1. Research | What do enterprise platforms, catalogs, open-source tools and standards already do for data readiness? | Landscape review and gap analysis (`research/`) | Done, November 2026 |
| 2. Framework | What does "ready" mean, and how is it measured? | Readiness levels, signals, tiers (`docs/framework.md`) | Draft |
| 3. Prototype | Can the deterministic checks score a real data dictionary? | Scorer on a public or synthetic metadata export; evaluate OpenMetadata as a base (`scorer/`, `docs/openmetadata.md`) | In progress: scorer runs on synthetic data |
| 4. Enrichment test | How accurate are AI-drafted descriptions, and how often are they wrong? | Measured accuracy against owner-written descriptions | Not started |
| 5. Pilot | Does the semantic layer improve AI query accuracy on real data? | 50-table pilot with a before-and-after test | Not started |
| 6. Scale | Can owners keep up with their work lists? | Estate-wide scorecard and process | Not started |

## Research questions added November 2026

These sit across stages 4 and 5. Each needs its own measured test.

| Question | How it could be measured |
| --- | --- |
| How certain is an AI model about what a table or column means, given the context it has? | Ask the model to state the meaning and the grain, several times. Score agreement between runs and against a known answer. Compare stated confidence with actual accuracy. A test kit for this and the next two questions is in [`certainty/`](../certainty/); it has not been run on a model yet |
| How complete must the semantic layer be before answers are reliable? | Give the same verified questions at each readiness level, 0 to 4. Plot accuracy and abstention by level. The level where accuracy stops rising is the target |
| When the model is unsure, what helps most? | Add one kind of context at a time (descriptions, grain, keys, code lists, usage rules, example queries) and measure the gain from each |
| Can a semantic layer be drafted where no data dictionary exists? | Extract candidate definitions from emails, meeting transcripts and tickets. Label each with its source and send it to an owner to confirm. Measure how many drafts owners accept |

## Pilot shape

One subject area, about 50 tables, 4 to 6 weeks:

1. Readiness heatmap for those tables
2. Owner work lists with AI drafts to confirm
3. Semantic layer for the top 10 to 15 tables, plus 50 verified questions
4. The same 50 questions in an AI query tool, against raw tables and then with the semantic layer
