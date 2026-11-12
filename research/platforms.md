# What the enterprise platforms already do

**Short answer:** no platform does the whole job. Each one covers pieces separately (quality monitoring, AI-drafted descriptions, trust badges, semantic models for AI query), but none scores documentation readiness across a whole warehouse, builds owner work lists from it, routes AI drafts for confirmation, and exports the result as a semantic layer.

Research as of 9 November 2026. Facts come from vendor documentation as returned by web search; vendor doc sites could not be opened directly from the research environment, so treat specifics as "verify before quoting." Marketing claims are labeled.

## At a glance

| Need | Closest built-in | Gap |
| --- | --- | --- |
| Estate-wide documentation and readiness scoring | Microsoft Purview metadata quality and health controls (missing owner, short description, severity-ranked actions) | Aimed at data products and governance domains; per-table and per-column coverage not confirmed; preview with limited rule creation |
| A "ready" flag | Databricks `system.certification_status`; Fabric Promoted / Certified / Master data; Snowflake tags (convention only) | Binary trust badges, not a readiness ladder |
| Owner work lists | Purview health actions; Databricks rules that auto-deprecate unused tables and email owners | None is driven by documentation completeness |
| AI-drafted documentation | Snowflake Cortex descriptions; Databricks AI comments; Google Gemini data insights; AWS SageMaker Catalog recommendations | User-initiated, one table at a time; no "unconfirmed" state or owner routing (SageMaker's review-then-publish is closest) |
| Data quality | Snowflake Data Metric Functions; Databricks data quality monitoring; Purview DQ scores; AWS Glue DQ; Google Dataplex | Mature, but measures the data, not the documentation |
| Semantic layer for AI query | Snowflake semantic views, verified queries, custom instructions, Autopilot; Databricks metric views, Genie instructions, trusted assets; Power BI AI data schema, verified answers, AI instructions | Built by hand per platform; nothing generates it from catalog readiness |

## Snowflake

- **AI descriptions:** Cortex Powered Object Descriptions generate table, view and column descriptions in Snowsight (GA December 2024); `AI_GENERATE_TABLE_DESC` does the same from SQL (GA September 2025). Saved text becomes an ordinary comment, with no "AI-drafted" marker or approval step. [docs](https://docs.snowflake.com/en/user-guide/ui-snowsight-cortex-descriptions) · [release note](https://docs.snowflake.com/release-notes/2025/other/2025-09-29-sql-object-descriptions)
- **Data quality:** Data Metric Functions (system and custom: nulls, uniqueness, freshness), scheduled per table, with expectations, anomaly detection and notifications. Enterprise Edition or higher (third-party source). [intro](https://docs.snowflake.com/user-guide/data-quality-intro)
- **Certification:** no native certified badge found in Horizon Catalog (unverified); tags and Internal Marketplace listings can carry a convention. [Horizon](https://docs.snowflake.com/en/user-guide/snowflake-horizon)
- **Semantic layer:** native semantic views; Cortex Analyst Verified Query Repository (question and SQL pairs used for answers and evaluation); custom instructions; Semantic View Autopilot proposes relationships and verified queries from query history. [blog](https://www.snowflake.com/en/blog/engineering/native-semantic-views-ai-bi/) · [Autopilot](https://docs.snowflake.com/user-guide/views-semantic/autopilot)
- **Missing:** no documentation-completeness or readiness score; buildable by querying `INFORMATION_SCHEMA` comments and tags. Features apply to data in Snowflake.

## Databricks

- **AI comments:** AI-generated comments for Unity Catalog tables and columns, reviewed and saved by a user; Databricks advises human review. No unconfirmed state or owner routing. [docs](https://docs.databricks.com/aws/en/comments/ai-comments)
- **Data quality:** data quality monitoring (formerly Lakehouse Monitoring) learns freshness and completeness per table; a 2026 preview ranks issues by lineage and certified tags; table health indicators in Catalog Explorer (Public Preview, March 2026, per release-note summaries). [docs](https://docs.databricks.com/aws/en/data-quality-monitoring)
- **Certification:** `system.certification_status` tag (`certified`, `deprecated`), with rules that can apply it automatically and email owners. [docs](https://docs.databricks.com/data-governance/unity-catalog/certify-deprecate-data)
- **Semantic layer:** metric views in Unity Catalog business semantics; Genie spaces with instructions, example SQL, trusted assets and benchmarks (up to 50 tables per space). Metadata edited inside a Genie space stays in that space. [metric views](https://docs.databricks.com/aws/en/business-semantics/metric-views) · [Genie](https://docs.databricks.com/genie/index.html)
- **Missing:** no native documentation-completeness or AI-readiness score; consultancies sell readiness audits (marketing).

## Microsoft (Purview, Fabric, Power BI)

- **Data quality:** Purview Unified Catalog DQ scans across six dimensions, scores, thresholds, alerts, severity-ranked actions and a 13-month health report. Supports Snowflake and Azure Databricks as sources. [health report](https://learn.microsoft.com/en-us/purview/data-quality-health-report) · [overview](https://learn.microsoft.com/en-us/purview/data-quality-overview)
- **Metadata quality (closest to documentation readiness):** health controls with rules such as description length and missing owners, failing into Low/Medium/High health actions. Aimed at data products and domains; some pages say Preview, and one says you can edit but not create controls. [metadata quality](https://learn.microsoft.com/en-us/purview/metadata-quality) · [health actions](https://learn.microsoft.com/en-us/Purview/data-estate-health-actions)
- **AI:** suggested glossary terms (private preview), AI-assisted data product curation and DQ rule generation (preview). No documented AI description generation found.
- **Endorsement:** Fabric Promoted, Certified, Master data; the OneLake catalog Govern tab shows endorsement coverage and recommended actions for Fabric items. [endorsement](https://learn.microsoft.com/en-GB/fabric/governance/endorsement-overview)
- **Prepare data for AI:** Power BI "Prep data for AI" sets an AI data schema, verified answers and AI instructions on a semantic model (Preview; Copilot needs Fabric F2+ or Premium P1). [docs](https://learn.microsoft.com/power-bi/create-reports/copilot-prepare-data-ai)
- **Cost:** pay-as-you-go per governed asset per day plus processing units for DQ. [billing](https://learn.microsoft.com/en-us/purview/data-governance-billing)

## Workday

- Workday Data Cloud (announced September 2025) shares Workday data with Snowflake and Databricks over Apache Iceberg; Snowflake reports its integration is GA with Worker, Position and Payroll objects "with Workday's semantic layer intact." [press](https://newsroom.workday.com/2025-09-16-Workday-Introduces-Workday-Data-Cloud-to-Unlock-the-Power-of-People-and-Money-Data-and-Accelerate-AI-Powered-Innovation) · [Snowflake blog](https://www.snowflake.com/en/blog/workday-data-cloud-snowflake-zero-copy-integration/)
- Prism Analytics has a data catalog with tags, lineage, profiles and validation steps. [datasheet](https://www.workday.com/content/dam/web/uk/documents/datasheets/datasheet-workday-prism-analytics.pdf)
- No data quality scoring, documentation completeness or readiness feature found. Workday is a source system here, not a readiness tool.

## Google and AWS

- **Google:** Dataplex data profile and quality scans; Gemini data insights generate table and column descriptions plus suggested questions with SQL, optionally published to the catalog (Preview). BigQuery only; no completeness score. [data insights](https://docs.cloud.google.com/bigquery/docs/data-insights)
- **AWS:** Glue Data Quality scores; SageMaker Catalog drafts business descriptions with Bedrock that a user reviews before publishing, the closest match to an "unconfirmed draft" state found anywhere. [Glue DQ](https://docs.aws.amazon.com/glue/latest/dg/glue-data-quality) · [what's new](https://aws.amazon.com/about-aws/whats-new/2025/07/amazon-sagemaker-catalog-adds-ai)

## What this means for the framework

1. **The new pieces are the readiness ladder and the draft-then-confirm workflow.** Everything else exists somewhere.
2. **Both are platform-neutral.** They can sit on top of the data dictionary, which already holds the definitions and steward roles, and export to whichever semantic layer the organization picks.
3. **Use the platforms for what they do well:** data quality monitoring, certification badges, and the semantic layer runtime. Don't rebuild them.
4. **Most native features only see data inside that platform.** Purview is the exception. A readiness layer that reads the data dictionary works before, during and after a migration.

## Not verified

Snowflake DMF credit rates; standalone Cortex Analyst pricing; Databricks monitoring and Genie pricing; Purview dollar rates. Opening Microsoft Learn directly would confirm the Microsoft items.
