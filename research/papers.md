# Research papers

All titles and IDs confirmed on arXiv on 9 November 2026. Numbers quoted from the abstracts unless marked.

## AI-drafted metadata

| Paper | Year | Finding |
| --- | --- | --- |
| [Leveraging Retrieval Augmented Generative LLMs for Automated Metadata Description Generation to Enhance Data Catalogs](https://arxiv.org/abs/2503.09003) | 2025 | Retrieval-grounded descriptions for catalog tables and columns. **87% to 88% of generated descriptions were accepted by data stewards as is or with minor edits.** The strongest evidence for the draft-then-confirm workflow |
| [AutoDDG: Automated Dataset Description Generation using Large Language Models](https://arxiv.org/abs/2502.01050) | 2025 | Grounds generation in a data profile; evaluation includes human validation |
| [Matching Table Metadata with Business Glossaries Using Large Language Models](https://arxiv.org/abs/2309.11506) | 2023 | Generates column descriptions to map columns to glossary terms; relevant to linking a data dictionary to warehouse columns |
| [Columbo: Expanding Abbreviated Column Names Using LLMs](https://arxiv.org/abs/2508.09403) | 2025 | Expands cryptic column names; beats the previous best by 4% to 29% across five datasets |
| [Column Type Annotation using ChatGPT](https://arxiv.org/abs/2306.00745) | 2023 | F1 above 85% in zero- and one-shot setups |
| [ArcheType: Open-Source Column Type Annotation using LLMs](https://arxiv.org/abs/2310.18208) | 2024 · PVLDB | Column typing with open-weight models; fits air-gapped use |
| [Zero-Shot Topic Classification of Column Headers](https://arxiv.org/abs/2403.00884) | 2024 | LLM classification of column headers for metadata enrichment |
| [ISEE: Interactive Semantic Enrichment for Database Fields](https://arxiv.org/abs/2608.02604) | 2026 | Expert-in-the-loop enrichment of database fields |

## Metadata and text-to-SQL accuracy

| Paper | Year | Finding |
| --- | --- | --- |
| [BIRD: Can LLM Already Serve as a Database Interface?](https://arxiv.org/abs/2305.03111) | 2023 · NeurIPS | Real-database text-to-SQL benchmark with "external knowledge" evidence. ChatGPT reached 40.08% execution accuracy against 92.96% for people |
| [Synthetic SQL Column Descriptions and Their Impact on Text-to-SQL Performance](https://arxiv.org/abs/2408.04691) | 2024 | LLM-generated column descriptions consistently improve text-to-SQL, especially for larger models; models struggle on ambiguous columns, "highlighting the need for manual expert input" |
| [Automatic database description generation for Text-to-SQL](https://arxiv.org/abs/2502.20657) | 2025 | Fully automatic descriptions improved BIRD accuracy by only 0.93%, about 37% of the gain from human-written descriptions |
| [MCI-SQL: Text-to-SQL with Metadata-Complete Context](https://arxiv.org/abs/2603.13390) | 2026 | Fuller metadata context; 74.45% dev and 76.41% test execution accuracy on BIRD |
| [A Benchmark to Understand the Role of Knowledge Graphs on LLM Accuracy for QA on Enterprise SQL Databases](https://arxiv.org/abs/2311.07509) | 2023 | GPT-4 zero-shot: 16% accuracy on raw enterprise SQL, 54% with a knowledge-graph (semantic) layer |
| [BEAVER: An Enterprise Benchmark for Text-to-SQL](https://arxiv.org/abs/2409.02038) | 2024 | Real private enterprise warehouses; top models scored 10.8%, rising to 30.1% with oracle hints |
| [Semantic Layers for Reliable LLM-Powered Data Analytics](https://arxiv.org/abs/2604.25149) | 2026 | Paired benchmark; semantic layer reportedly adds 17 to 23 points first-shot (secondary summary) |
| [Pervasive Annotation Errors Break Text-to-SQL Benchmarks and Leaderboards](https://arxiv.org/abs/2601.08778) | 2026 | 52.8% and 62.8% annotation errors in BIRD Mini-Dev and Spider 2.0-Snow |

## What the papers mean for the framework

1. **Meaning drives accuracy.** Enterprise text-to-SQL is weak on raw schemas (16% and 10.8% in two enterprise benchmarks) and improves sharply with a semantic layer (54%).
2. **AI drafts help, but people make the difference.** Fully automatic descriptions recovered only about a third of the gain from human ones. Steward review accepted 87–88% of grounded drafts with little editing. That supports AI drafting plus owner confirmation, not AI alone.
3. **Measure on your own data.** Public benchmarks carry heavy annotation errors, and enterprise schemas behave differently. The before-and-after test on the organization's own warehouse is the evidence that counts.
