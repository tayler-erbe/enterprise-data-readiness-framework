# Research: what already exists

Stage 1 of the roadmap, completed 9 November 2026.

**The answer:** the pieces exist, the whole doesn't. Warehouses, catalogs and open-source tools each cover parts: data quality monitoring, documentation coverage, AI-drafted descriptions, trust badges and semantic layers for AI query. No product found scores documentation readiness on a published ladder across a whole warehouse, routes AI drafts to owners as unconfirmed, runs that drafting on local models for sensitive tables, works from an existing data dictionary, and exports a portable semantic layer.

| File | Covers |
| --- | --- |
| [platforms.md](platforms.md) | Snowflake, Databricks, Microsoft (Purview, Fabric, Power BI), Workday, Google, AWS |
| [tools-and-standards.md](tools-and-standards.md) | Atlan, Secoda, Collibra, Alation, Informatica and others; OpenMetadata, DataHub, dbt tools, the Open Semantic Interchange; Gartner, ISO, FAIR, VAULTIS |
| [papers.md](papers.md) | AI-drafted metadata and the effect of metadata on text-to-SQL accuracy |
| [ai-judging-readiness.md](ai-judging-readiness.md) | Added 12 November: products that test readiness by running an AI, evidence of how good they are, and research on model certainty |
| [column-meaning-and-test-data.md](column-meaning-and-test-data.md) | Added 12 November: kinds of column meaning, preprocessing operations, where ambiguity comes from, and where to get test data a model has not seen |

## Gap analysis

| Piece of the framework | Exists today? | Best existing option |
| --- | --- | --- |
| Data quality checks on the data itself | Yes, mature | Snowflake DMFs, Databricks monitoring, Purview DQ |
| Documentation and ownership coverage % | Yes | OpenMetadata Data Insights (open source); Atlan, Secoda, CastorDoc |
| Ordinal readiness ladder tied to standards | **No** | Vendor point scores or flat percentages |
| AI-drafted descriptions | Yes | Every major platform and catalog |
| "Unconfirmed" draft state routed to owners | **Partly** | DataHub review flag, Collate accept or reject, SageMaker review-then-publish |
| Local open-weight models for sensitive tables | **No** (as packaged features) | Research code such as ArcheType |
| An existing data dictionary as the source of truth | **Partly** | Catalog importers; none tied to readiness scoring |
| Owner work lists ranked by value and gap | **Partly** | Purview health actions (governance-oriented, not documentation-driven) |
| Portable semantic layer export | Emerging | Open Semantic Interchange, MetricFlow |
| Proof that readiness predicts AI query accuracy | **No** | Papers show the effect in general; nobody measures it per warehouse |

## Recommendation

**Adopt, don't rebuild, the mature pieces:** data quality monitoring and certification in whichever warehouse is chosen; OpenMetadata as a candidate open-source base for coverage metrics; OSI as the semantic-layer export format.

**Build the new pieces:** the readiness ladder, the draft-then-confirm workflow with owner work lists, local-model enrichment for sensitive tables, a loader for data dictionary exports, and the before-and-after accuracy test.

## Still to verify

Vendor pricing; Microsoft Purview metadata-quality scope per table; whether Collate's documentation agent can use a self-hosted model; OSI specification status.
