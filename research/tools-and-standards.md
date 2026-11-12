# Catalogs, open-source tools and standards

**Short answer:** several tools score documentation completeness, and several draft descriptions with AI. None combines a published readiness ladder, an "unconfirmed draft" state routed to owners, local open-weight models for sensitive tables, and an existing data dictionary as the source of truth.

Research as of 9 November 2026, from search results and documentation summaries. Marked items need checking before they are quoted. Pricing was rarely published.

## Commercial catalogs

| Tool | Scores documentation or "AI readiness" | AI-drafted descriptions |
| --- | --- | --- |
| [Atlan](https://docs.atlan.com/product/capabilities/discovery/references/metadata-completeness) | Yes, configurable: a metadata completeness score per asset (points for description, owner, certificate), a governance scorecard query, and an "AI Readiness" custom-metadata pattern. One Atlan skill scores readiness as the lowest dimension, not the average | Yes, paid; Context Agents Studio in private preview |
| [Secoda](https://www.secoda.co/data-quality-score) | Yes: a Data Quality Score with Stewardship, Usability (documentation-centred), Reliability and Accuracy | Yes; vendor claims it automates "90% of documentation tasks" |
| [CastorDoc / Coalesce Catalog](https://docs.coalesce.io/docs/catalog/administration/analytics/data-documentation-coverage) | Documentation coverage analytics page | "Describe with AI" |
| Select Star | No coverage score found | AI documentation (private preview when announced) |
| Collibra | AI Command Center assesses AI agents' readiness, not tables | Not confirmed |
| Alation | Marketing and a checklist; no published scoring formula | Not confirmed |
| [Informatica CLAIRE](https://www.informatica.com/blogs/informatica-spring-2025-release-genai-amplifies-the-impact-of-ai.html) | No readiness score found | Generates glossary descriptions; runs on hosted models (Azure OpenAI, AWS Bedrock), so no air-gapped option |
| data.world | Knowledge-graph "AI Context Engine"; ServiceNow announced its acquisition in May 2025 | Not found |
| Monte Carlo, Bigeye, Soda, Great Expectations | Data observability and quality tests; they measure the data, not the documentation | n/a |

## Open source

- **[OpenMetadata](https://docs.open-metadata.org/latest/how-to-guides/data-insights/kpi)** is the only one found that computes documentation and ownership coverage out of the box: Data Insights KPIs for completed descriptions and ownership, recomputed daily, plus tier coverage. A table counts as described only if the table and all its columns are described. The AI documentation agent (suggest, then accept or reject) is in Collate, the commercial edition; whether it can use a self-hosted model is unverified.
- **[DataHub](https://docs.datahub.com/docs/automations/ai-docs)** has documentation forms that require fields, and AI-generated documentation flagged for human review (appears to be a Cloud feature; status differs between doc versions).
- **dbt ecosystem:** [dbt-coverage](https://pypi.org/project/dbt-coverage), dbt-checkpoint, dbt-project-evaluator, dbt-bouncer and dbt-score gate or score documentation coverage, but only for dbt-managed models, not a whole legacy warehouse.
- **Semantic layer interchange:** the [Open Semantic Interchange (OSI)](https://open-semantic-interchange.github.io/osi-website/) launched in September 2025 with Snowflake, Salesforce and dbt Labs; partners now include Databricks, DataHub, Collate, Atlan, Collibra and Alation. dbt's [MetricFlow was open-sourced under Apache 2.0](https://ossie.apache.org/updates/announcing-open-source-metricflow-governed-metrics-for-ai-and-agents/) as an OSI reference implementation. **The framework's semantic layer export should target OSI.** Spec version status unverified.
- Amundsen, Marquez and Apache Atlas: no built-in coverage score found.

## Standards and definitions

| Source | What it gives the framework |
| --- | --- |
| [Gartner, 26 February 2025](https://www.gartner.com/en/newsroom/press-releases/2025-02-26-lack-of-ai-ready-data-puts-ai-projects-at-risk) | Predicts organizations "will abandon 60% of AI projects unsupported by AI-ready data" through 2026; 63% of organizations "either do not have or are unsure if they have the right data management practices for AI." Gartner frames AI readiness around [metadata](https://www.gartner.com/en/articles/ai-ready-data). (Survey size differs between secondary sources; verify on Gartner's page.) |
| [ISO/IEC 25012](https://quality.arc42.org/standards/iso-iec-25012) | 15 data quality characteristics, including understandability and traceability, which map to documentation |
| [ISO 8000](https://journals.sagepub.com/doi/10.15388/23-INFOR534) | Master data quality, provenance and completeness (parts 100 to 150) |
| [RDA FAIR Data Maturity Model](https://zenodo.org/record/3909563) | Graded indicators (Essential, Important, Useful) for findable, accessible, interoperable, reusable data; the closest published model of graded maturity |
| [DoD VAULTIS](https://apps.dtic.mil/sti/trecms/pdf/AD1112684.pdf) | Visible, Accessible, Understandable, Linked, Trustworthy, Interoperable, Secure; described by a former DoD official as the path to AI-ready data |
| [US Department of Commerce, January 2025](https://www.commerce.gov/sites/default/files/2025-01/GenerativeAI-Open-Data.pdf) | Generative AI and open data guidelines: documentation, formats, dissemination, licensing, integrity |
| DAMA-DMBOK | Commonly cited dimensions: accuracy, completeness, consistency, timeliness, validity, uniqueness (not retrieved this session) |

## Closest existing solutions

1. **OpenMetadata or Collate:** coverage KPIs, tiers, data quality, and a paid AI documentation agent with accept or reject. Self-hostable. The best base to build on or borrow from.
2. **Atlan:** configurable completeness and AI-readiness scoring. Proprietary SaaS.
3. **Secoda:** automatic per-asset score with documentation as a weighted part.
4. **DataHub:** required-field forms plus AI docs flagged for review.
5. **dbt coverage tools plus MetricFlow and OSI:** coverage gates and an open semantic-layer path, for dbt-managed models only.
