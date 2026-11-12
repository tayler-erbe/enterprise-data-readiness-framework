# The data readiness framework

**Goal:** know, for every table in an enterprise warehouse, whether people and AI tools can use it correctly today, and fix the gaps in order of value.

AI query tools (Snowflake Cortex Analyst, Databricks Genie, Power BI Copilot) are only as accurate as the meaning they are given. The vendors' own numbers show most of the accuracy comes from a curated semantic layer, not the model. Most warehouses are not documented well enough to build that layer. This framework measures how far each table is from ready, drafts what is missing, and routes it to the people who can confirm it.

## 1. Readiness levels

Every table gets one level. A table reaches a level only when it meets every check for that level and the levels below it.

| Level | Name | Meaning | Checks |
| --- | --- | --- | --- |
| 0 | Undocumented | Nobody has said what it is | No table description; no column descriptions |
| 1 | Described | Roughly known | Table description exists; it is readable (not a placeholder; encoding damage is flagged but doesn't block) |
| 2 | Usable | An analyst could query it correctly | Grain stated (what one row is); keys and join paths documented; most columns described; coded columns link to a lookup or list of values |
| 3 | Governed | Safe to report from | Named owner; usage rules recorded as fields (valid date ranges, exclusions, trust level); quality advisories current and links working |
| 4 | AI-ready | An AI tool can use it without supervision | Entered in the semantic layer (definitions, joins, metrics); verified example questions with known answers; passes the text-to-SQL test |

Columns get a simpler score: described or not, coded or not, decoded or not.

## 2. Signals

Most of the score is deterministic. Code can check it the same way every time.

| Signal | Level it supports | How |
| --- | --- | --- |
| Table and column description coverage | 1, 2 | Count non-empty descriptions |
| Description quality | 1 | Flags for blank, placeholder ("TBD", copies of the table name), encoding damage (`Â`, `â€œ`; a warning, not a fail), very short text |
| Grain statement | 2 | Pattern match ("one row per ...") or confirmed field |
| Keys and joins | 2 | Primary and foreign keys in the catalog or confirmed join paths |
| Code columns decoded | 2 | Column ends in `_CD` or similar and a lookup table or value list exists |
| Owner present | 3 | Named owner or steward in the catalog |
| Usage rules | 3 | Validity window, exclude-from-reporting flag, trust level (for example "self-reported, not verified") |
| Advisory freshness | 3 | Links resolve; advisory has a date |
| In semantic layer | 4 | Table appears in the exported semantic model |
| Verified questions | 4 | At least N questions with known answers pass |

## 3. Where AI helps, and where it doesn't

AI does two jobs. Neither one changes a score until a person confirms it.

1. **Turn prose into fields.** Good descriptions often hide rules in long comments: "do not use after Fall 2010", "not useful for reporting", "self-reported". A model extracts them into structured fields for the owner to confirm.
2. **Draft what's missing.** For undocumented tables, a model drafts a table description and column descriptions from names, types, comments, lookup tables and (where allowed) profile statistics. Every draft is labeled **AI-inferred, unconfirmed**, carries a confidence note, and goes to the owner's work list.

AI never scores a table by itself, and nothing AI-drafted is published as fact. The research supports this split: grounded drafts were accepted by data stewards 87–88% of the time as is or with minor edits, while fully automatic descriptions recovered only about a third of the text-to-SQL gain that human-written ones gave (see `research/papers.md`). This follows the evidence from chart and document research: models state wrong facts with full confidence, and errors build up when output runs unchecked.

## 4. Privacy tiers

The model never needs to see more than the tier allows. Sensitive work runs on owned, air-gapped hardware with open-weight models.

| Tier | Typical tables | What the model sees |
| --- | --- | --- |
| A Open | Code tables, organization and program structures | Metadata plus sample rows |
| B Internal | Purchasing, proposals, positions | Metadata plus profile statistics (null rates, distinct counts, value patterns) |
| C Restricted | Health, race and ethnicity, HR notes, credit applications | Metadata only |
| D Excluded | Anything a data steward refuses | Nothing; flagged for owner documentation |

Every output is scrubbed for personal data before it leaves the secure environment. What leaves is metadata only.

## 5. Prioritization

Priority = value × gap.

- **Value:** how much the table is used. Query logs, reports and dashboards that depend on it, and how many people run those.
- **Gap:** how many levels it is from where it needs to be.

The output is a ranked work list per owner: "these 12 tables you own feed 40 reports and sit at level 1. Here are drafts to confirm."

## 6. Outputs

| Output | For |
| --- | --- |
| Readiness scorecard | Leadership: how ready the estate is, by subject area |
| Owner work lists | Data owners: what to confirm or write, in priority order |
| Enriched metadata | The catalog: confirmed descriptions, grain, keys, rules |
| Semantic layer export | Any platform, using the Open Semantic Interchange (OSI) where supported: Snowflake semantic views and verified queries, Databricks metric views and Genie instructions, dbt MetricFlow, or a custom build |
| Verified question set | Testing: questions with known answers for every AI query tool |

## 7. Measuring that it worked

Ask the same set of verified questions in an AI query tool twice: once against the raw tables, once with the semantic layer. Report accuracy both ways. That before-and-after number is the proof that the data wasn't ready, and that the work closed the gap.

## 8. Alignment with standards

The levels map to published frameworks, so the score means something outside one organization.

| Level | FAIR (RDA maturity model) | ISO/IEC 25012 | DoD VAULTIS |
| --- | --- | --- | --- |
| 1 Described | Findable (rich metadata) | Understandability | Visible |
| 2 Usable | Interoperable (keys, vocabularies) | Understandability, consistency | Understandable, Linked |
| 3 Governed | Reusable (provenance, usage license and rules) | Traceability, credibility | Trustworthy, Secure |
| 4 AI-ready | Reusable and machine-actionable | Accessibility to automated use | Interoperable |

Gartner frames AI-ready data around metadata that lets data be aligned, qualified and governed; this ladder is a way to measure exactly that, table by table.
