# Who uses AI to check whether data is ready for AI, and how well

Research as of 12 November 2026. It adds to the 9 November review in three places that review left thin: products that test readiness by running an AI over the data, independent evidence of how good they are, and published research on whether models know when they're wrong about what data means.

"Opened" means the source page itself was read. "Search only" means a search summary was seen and the page was not opened. Treat search-only items as leads, not facts.

**Short answer.** The leading products have moved from scoring metadata to running question sets through the AI and grading the answers. Snowflake goes furthest. Nobody publishes a graded ladder for documentation readiness, and nobody shows that a readiness score predicts answer accuracy on a given warehouse. In research, model certainty and documentation completeness have been studied separately and, as far as this search found, not together.

## Products

| Product | What it scores or tests | AI as judge | Method published | Source | Opened |
| --- | --- | --- | --- | --- | --- |
| Snowflake Semantic View Autopilot and "Agentic Optimize" | Builds semantic views from query history, SQL examples, Tableau and Power BI files, and table metadata. Optimize compares generated SQL with verified queries and proposes fixes to descriptions, synonyms, metrics and filters | Yes | The loop is described; the rubric is not | [engineering blog](https://www.snowflake.com/en/engineering-blog/using-ai-improving-ai/), [docs](https://docs.snowflake.com/en/user-guide/views-semantic/autopilot) | Yes |
| Snowflake Cortex Agent evaluations | Answer correctness, logical consistency, tool selection and execution against a ground-truth set | Yes, except tool selection | Yes | [docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-evaluations) | Yes |
| Databricks Genie benchmarks | Up to 500 questions per space, each run as a fresh conversation | Chat mode compares result sets; agent mode uses an LLM judge | Yes | [docs](https://docs.databricks.com/aws/en/genie/benchmarks) | Yes |
| Atlan Context Engineering Studio | Builds a per-use-case context repository from warehouse metadata, glossary, column profiles, query history and BI SQL; deploys to Cortex Analyst, Genie, dbt and MCP | Not stated | Partly | [docs](https://docs.atlan.com/product/capabilities/governance/context-engineering-studio/concepts/what-is-context-engineering-studio) | Yes |
| Atlan "AI-ready data audit" skill | 12 checks across meaning, trust, boundaries and reproducibility, each pass, fail or unknown. Not averaged into a percentage | An agent runs the checklist | Yes | [skill](https://atlan.com/skills/ai-ready-data-audit.md) | Yes |
| Alation Agent Studio evaluations | Question and expected-SQL cases. "Suggest Improvements" proposes description and instruction fixes for a person to approve | Not stated | Partly | [blog](https://www.alation.com/blog/ai-agent-evaluations/) | Yes |
| Microsoft Fabric and Power BI "Prep data for AI" | A manual test, diagnose and fix loop before a model is marked "Approved for Copilot" | No, a person judges | Yes, as guidance | [training module](https://learn.microsoft.com/en-us/training/modules/fabric-prepare-semantic-layer/6-validate-readiness) | Yes |
| Ataccama Data Trust Index | Trust score per asset from quality, monitoring, stewardship, glossary coverage and descriptions | Not stated | No formula | [product page](https://www.ataccama.com/solutions/data-trust-for-ai) | Yes |
| Qlik Trust Score for AI | Diversity, timeliness and accuracy on top of discoverability and usage. An "LLM readiness" dimension was announced as to follow | Not stated | No | [press release](https://www.qlik.com/us/news/company/press-room/press-releases/qlik-releases-trust-score-for-ai-in-qlik-talend-cloud) | Yes |
| Collibra AI Trust Score | One score per AI system | Unverified | No | collibra.com/products/ai-command-center | Search only |
| Informatica AI-ready data assessment | A "7 pillars" readiness score | Unverified | Unverified | assess.informatica.com | Page failed to load |
| Google Knowledge Catalog (Dataplex, renamed 2026) | Generated sample queries and docs, verified queries, a context evaluation framework | Unverified | Unverified | cloud.google.com/products/knowledge-catalog | Search only |
| Gartner AI-Ready Data Assessment Toolkit | Questionnaire-style readiness score | No | Paywalled | gartner.com/en/documents/6901266 | Search only |
| Context-layer startups (Jedify, Solid, Euno, Qontext and others) | Infer semantics from query logs and metadata | Unverified | No | TechCrunch, June 2026 | Search only |

None of these publishes evidence that its score predicts AI answer accuracy on a customer's warehouse. The benchmark tools measure accuracy directly; the scoring tools score metadata. Nothing found ties the two together.

### Who does it best

- **Snowflake** is the only one confirmed to close the loop automatically: run the questions, have a model judge them, propose metadata fixes as accept or reject cards. Its verified inputs are also the broadest.
- **Databricks Genie benchmarks** are the most transparent test harness. The scoring rules and the 500-question limit are documented.
- **Atlan** has the clearest thinking on meaning. Its audit wants a named artifact for each check and refuses a single percentage. It is a checklist an agent runs.
- **Alation** is the only catalog found with a published worked example of evaluate, suggest a fix, person approves, re-run.
- **Microsoft's** guidance is sound and entirely manual.

### How good is it

Vendor claims:

- Snowflake's own post says the first Optimize version took 1 to 2 hours, was capped at 50 verified queries and caused "decision fatigue." It gives no accuracy numbers.
- dbt Labs (April 2026, 11 questions, 20 runs each, open harness): one model went from 90.0% to 98.2% with the semantic layer after three extra models were built. On the original schema the semantic layer scored 0% on questions needing too many joins.
- Alation: 60% to 100% on 20 questions, one dataset.
- AtScale, Databricks and Snowflake accuracy figures circulate in secondary coverage. Not opened; not used here.

Independent, or closer to it:

- [Semantic Layers for Reliable LLM-Powered Data Analytics](https://arxiv.org/abs/2604.25149) (April 2026): on 100 questions, a 4 KB hand-written semantics document raised three frontier models from 45.5–50.5% to 67.7–68.7%. Which model was used made little difference. Author affiliations aren't shown, so independence is unconfirmed.
- A consultancy review (August 2026) found that Genie's chat-mode benchmark compares rows only, so a structurally wrong query can pass on today's data.
- No practitioner threads on Reddit or Hacker News turned up in the searches.

## Research on model certainty

| Paper | Year | Finding | Opened |
| --- | --- | --- | --- |
| [Text-to-SQL Calibration: No Need to Ask, Just Rescale Model Probabilities](https://arxiv.org/abs/2411.16742) | 2024 | Rescaled sequence probability beats self-check prompts and stated confidence | Yes |
| [Calibrating LLMs for Text-to-SQL Parsing by Leveraging Sub-clause Frequencies](https://arxiv.org/abs/2505.23804) | EMNLP 2025 | A benchmark for post-hoc calibration of text-to-SQL | Yes |
| [Confidence Estimation for Error Detection in Text-to-SQL Systems](https://arxiv.org/abs/2501.09527) | AAAI 2025 | A small fine-tuned model was better calibrated than GPT-4 and Llama 3 | Yes |
| [Confidence Estimation for Text-to-SQL in Large Language Models](https://arxiv.org/abs/2508.14056) | 2025 | Agreement across runs is the best signal when internals are hidden; running the query helps | Yes |
| [What Predicts Correctness in Text-to-SQL? A Selective-Prediction Study](https://arxiv.org/abs/2607.06799) | 2026 | Agreement across runs and token probability reach about 0.61–0.68 AUROC; a separate judge model 0.72–0.78; two judges together 0.82 | Yes |
| [Reliable Text-to-SQL with Adaptive Abstention](https://arxiv.org/abs/2501.10858) | 2025 | Abstaining at the schema-linking step, with a person in the loop | Yes |
| [Certified Against Which Oracle?](https://arxiv.org/abs/2609.25938) | 2026 | Reported abstention risk shifts by many points when the correctness labels change | Yes |
| [TrustSQL](https://arxiv.org/abs/2403.15879) | 2024 | Scores with a penalty for wrong answers, including unanswerable questions | Yes |
| [AmbiQT](https://arxiv.org/abs/2310.13659), [AMBROSIA](https://arxiv.org/abs/2406.19073), [BIRD-INTERACT](https://arxiv.org/abs/2510.05318) | 2023–2026 | Models guess on ambiguous questions; they rarely ask or flag it | Yes |
| [Dr.Spider](https://arxiv.org/abs/2301.08881) | ICLR 2023 | The most robust model drops 14.0% overall under perturbation, 50.7% on the hardest | Yes |
| [Metadata Reconstruction from Values Alone](https://arxiv.org/abs/2608.07946) | 2026 | With names stripped, naive accuracy falls from 0.92 to 0.42; a gated system reaches 86% at 59% coverage | Yes |
| [Text-to-SQL for Enterprise Data Analytics](https://arxiv.org/abs/2507.14372) | 2025 | A knowledge graph built from metadata, query logs, wikis and code; 53% of responses correct or close | Yes |
| [Can LLMs Express Their Uncertainty?](https://arxiv.org/abs/2306.13063) | ICLR 2024 | Models tend to be overconfident when asked to state confidence | Yes |
| [Semantic entropy](https://pmc.ncbi.nlm.nih.gov/articles/PMC11186750) | Nature 2024 | Disagreement in meaning across repeated samples detects made-up answers | Yes |

### Established

- Model confidence on database questions is poorly calibrated unless it's rescaled afterwards on labelled data.
- For SQL, stated confidence is the weakest signal. Token probability and agreement across runs do better.
- Agreement across runs is only a modest predictor. A separate judge model does better.
- Models guess on ambiguous questions.
- Documentation raises accuracy a lot.
- Extra context can hurt a smaller model (one non-peer-reviewed thesis).

### Not found

- Calibration measured at each level of a documentation ladder.
- Whether documentation raises confidence faster than it raises accuracy.
- The effect of each kind of context (grain, keys, code lists, units, rules) on certainty, not only on accuracy.
- Abstention as a function of missing documentation.

About 25 searches and 25 opened pages. Not a systematic review. The safe claim is "to our knowledge, not found."

## Gaps

1. No published, graded ladder for documentation readiness per table and column.
2. Nobody checks, per warehouse, that a readiness score predicts answer accuracy.
3. All testing depends on verified queries written by people. No product was confirmed to generate test questions with trustworthy expected answers.
4. Built-in checks can pass the right number from the wrong logic.
5. Scores are per engine. Nothing is portable across Cortex, Genie and Copilot.
6. No product was confirmed to build context from chat, email, meetings or tickets. Verified inputs are query history, BI files, glossaries and metadata.
7. Finding ambiguous or conflicting definitions before a question is asked exists only in research.
8. No tool was found that assesses meaning before an ERP migration. Migration tools cover format, mapping and sizing (search only).
9. No packaged option was confirmed that runs the judging on local models for sensitive tables.
10. Certainty is not reported. Tools report accuracy; none found reports whether the model knew when it was wrong.

## What this means for the certainty test

Additions the literature points to:

- Collect token probabilities as a second confidence signal where the server exposes them, and consider a separate judge model.
- Add questions that can't be answered from the tables, to test whether the model declines.
- Add a condition with a wrong description, to test over-trust.
- Add a control with irrelevant text of the same length.
- Run at least one small and one large model.
- Report calibration error, Brier score, AUROC of confidence, and accuracy against coverage, with bootstrap intervals.
- Use more than one database before generalising.

## Not verified

Informatica, Collibra, Qlik and Ataccama scoring methods; Google's evaluation framework; current release status of Snowflake Optimize; the AtScale study; the context-layer startups' confirmation process; IBM, ThoughtSpot, Hex, Cube, Select Star, Glean, Sifflet, Acceldata, Anomalo and consulting-firm assessments (nothing usable found); current SAP, Oracle and Workday migration-readiness tooling.
