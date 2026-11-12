# Readiness scorecard

24 tables from tables.csv and columns.csv, scored 2026-11-12.

| Level | Tables | Share |
| --- | ---: | ---: |
| 0 Undocumented | 5 | 21% |
| 1 Described | 14 | 58% |
| 2 Usable | 2 | 8% |
| 3 Governed | 2 | 8% |
| 4 AI-ready | 1 | 4% |

## By schema

| Schema | 0 | 1 | 2 | 3 | 4 | Tables |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| FIN | 2 | 4 |  | 1 | 1 | 8 |
| HR | 1 | 5 | 2 |  |  | 8 |
| OPS | 2 |  |  |  |  | 2 |
| REF |  | 1 |  | 1 |  | 2 |
| SALES |  | 4 |  |  |  | 4 |

## What blocks the next level

Each table counts against the level it's trying to reach. "Fails" means the documentation is missing;
"can't tell" means the export doesn't carry enough to check.

| Next level | Check | Fails | Can't tell |
| --- | --- | ---: | ---: |
| 1 Described | Readable description | 5 |  |
| 1 Described | Table description | 3 |  |
| 2 Usable | Columns described | 1 | 13 |
| 2 Usable | Codes decoded | 1 | 13 |
| 2 Usable | Keys or joins |  | 13 |
| 2 Usable | Grain stated | 12 |  |
| 3 Governed | Named owner | 1 |  |
| 3 Governed | Trust level | 1 |  |
| 3 Governed | Rules out of prose | 1 |  |
| 4 AI-ready | In semantic layer | 2 |  |
| 4 AI-ready | Verified questions | 2 |  |

## What this export can't tell

These count as not met. Better metadata, not better documentation, would settle them.

| Check | Tables |
| --- | ---: |
| Columns described | 18 |
| Codes decoded | 18 |
| Keys or joins | 13 |
| Links resolve | 1 |

## Rules sitting in prose

Candidates for extraction into fields. A person confirms each one.

| Rule | Tables |
| --- | ---: |
| validity window | 2 |
| trust level | 2 |
| known defect | 1 |
| exclude from reporting | 1 |

## Possible restricted tables

Names suggest privacy tier C. A steward confirms the tier before any profiling or AI drafting.

`HR.EMP_HEALTH_COND_HIST`, `HR.BENEFIT_PLAN_HIST`, `HR.EMP_HR_NOTE`, `SALES.CREDIT_APPL_PART_1`

## Settings

- Column coverage for level 2: 80%
- Verified questions for level 4: 5, pass rate 90%
- Default target level: 4
- Links checked: no
