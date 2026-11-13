# No-AI baselines on the test set

Real results. No model was used. Run `python baselines.py` to reproduce.

`accept_all` calls every column READY. `rules` applies generic quality rules to the whole column. `profiler` adds shape profiling (date formats, dressed-up numbers, category variants). Both are plain implementations written for this test, not any vendor's product.

| Measure | accept_all | rules | profiler |
| --- | ---: | ---: | ---: |
| Verdict right | 18% | 28% | 40% |
| Dangerous: needs-context or garbage columns passed as usable | 100% | 91% | 86% |
| Needs-context columns passed as usable | 100% | 100% | 94% |
| Over-cautious: usable columns held back | 0% | 0% | 0% |

Columns: 720.

## What the profiler said, against the truth

| Truth | Columns | said READY | said FIXABLE | said NEEDS_CONTEXT | said GARBAGE |
| --- | ---: | ---: | ---: | ---: | ---: |
| READY | 132 | 132 | 0 | 0 | 0 |
| FIXABLE | 324 | 205 | 119 | 0 | 0 |
| NEEDS_CONTEXT | 192 | 180 | 0 | 12 | 0 |
| GARBAGE | 72 | 36 | 12 | 0 | 24 |

## Profiler, by kind of case

| Case | Truth | Columns | Verdict right | Most common answer |
| --- | --- | ---: | ---: | --- |
| r_amount_named | READY | 12 | 100% | READY (12) |
| r_category_words | READY | 12 | 100% | READY (12) |
| r_code_with_description | READY | 12 | 100% | READY (12) |
| r_count_named | READY | 12 | 100% | READY (12) |
| r_date_iso | READY | 12 | 100% | READY (12) |
| r_email | READY | 12 | 100% | READY (12) |
| r_identifier | READY | 12 | 100% | READY (12) |
| r_percent_named | READY | 12 | 100% | READY (12) |
| r_person_name | READY | 12 | 100% | READY (12) |
| r_weekday_name | READY | 12 | 100% | READY (12) |
| x_amount_with_currency_column | READY | 12 | 100% | READY (12) |
| f_boolean_variants | FIXABLE | 12 | 100% | FIXABLE (12) |
| f_category_typos | FIXABLE | 12 | 0% | READY (12) |
| f_category_variants | FIXABLE | 12 | 100% | FIXABLE (12) |
| f_currency_symbol | FIXABLE | 12 | 0% | READY (12) |
| f_date_mixed_formats | FIXABLE | 12 | 0% | READY (12) |
| f_date_slash_order | FIXABLE | 12 | 100% | FIXABLE (12) |
| f_decimal_comma | FIXABLE | 12 | 100% | FIXABLE (12) |
| f_embedded_values | FIXABLE | 12 | 0% | READY (12) |
| f_epoch_millis | FIXABLE | 12 | 0% | READY (12) |
| f_epoch_seconds | FIXABLE | 12 | 0% | READY (12) |
| f_excel_serial_date | FIXABLE | 12 | 0% | READY (12) |
| f_id_as_float | FIXABLE | 12 | 0% | READY (12) |
| f_leading_zero_lost | FIXABLE | 12 | 0% | READY (12) |
| f_mojibake | FIXABLE | 12 | 0% | READY (12) |
| f_number_text_separators | FIXABLE | 12 | 100% | FIXABLE (12) |
| f_outlier_impossible | FIXABLE | 12 | 92% | FIXABLE (11) |
| f_percent_sign | FIXABLE | 12 | 100% | FIXABLE (12) |
| f_quantity_packs_with_total | FIXABLE | 12 | 0% | READY (12) |
| f_sentinel_date | FIXABLE | 12 | 0% | READY (12) |
| f_sentinel_number | FIXABLE | 12 | 67% | FIXABLE (8) |
| f_sentinel_text | FIXABLE | 12 | 100% | FIXABLE (12) |
| f_units_mixed_separable | FIXABLE | 12 | 0% | READY (12) |
| f_units_written | FIXABLE | 12 | 0% | READY (12) |
| f_weekday_number_with_date | FIXABLE | 12 | 0% | READY (12) |
| f_whitespace_case | FIXABLE | 12 | 100% | FIXABLE (12) |
| x_total_recomputable | FIXABLE | 12 | 33% | READY (8) |
| x_weight_with_unit_column | FIXABLE | 12 | 0% | READY (12) |
| n_amount_cents_or_dollars | NEEDS_CONTEXT | 12 | 0% | READY (12) |
| n_amount_period | NEEDS_CONTEXT | 12 | 0% | READY (12) |
| n_cryptic_number | NEEDS_CONTEXT | 12 | 0% | READY (12) |
| n_currency_unknown | NEEDS_CONTEXT | 12 | 0% | READY (12) |
| n_date_slash_unresolvable | NEEDS_CONTEXT | 12 | 100% | NEEDS_CONTEXT (12) |
| n_flag_1_2 | NEEDS_CONTEXT | 12 | 0% | READY (12) |
| n_opaque_codes | NEEDS_CONTEXT | 12 | 0% | READY (12) |
| n_quantity_alone | NEEDS_CONTEXT | 12 | 0% | READY (12) |
| n_state_or_country | NEEDS_CONTEXT | 12 | 0% | READY (12) |
| n_timestamp_zone | NEEDS_CONTEXT | 12 | 0% | READY (12) |
| n_unit_unknown | NEEDS_CONTEXT | 12 | 0% | READY (12) |
| n_weekday_number_alone | NEEDS_CONTEXT | 12 | 0% | READY (12) |
| n_zero_missing_or_real | NEEDS_CONTEXT | 12 | 0% | READY (12) |
| x_code_description_conflict | NEEDS_CONTEXT | 12 | 0% | READY (12) |
| x_end_before_start | NEEDS_CONTEXT | 12 | 0% | READY (12) |
| x_state_zip_conflict | NEEDS_CONTEXT | 12 | 0% | READY (12) |
| g_constant | GARBAGE | 12 | 100% | GARBAGE (12) |
| g_mostly_missing | GARBAGE | 12 | 100% | GARBAGE (12) |
| g_placeholder_text | GARBAGE | 12 | 0% | READY (12) |
| g_random_noise | GARBAGE | 12 | 0% | READY (12) |
| g_truncated | GARBAGE | 12 | 0% | READY (12) |
| g_wrong_values_mixed_in | GARBAGE | 12 | 0% | FIXABLE (12) |

## How to read this

- `accept_all` is right only on the READY columns, and passes every unsafe column. That is the floor.
- `profiler` catches the needs-context case that values alone reveal (slash dates with no day above 12). It passes the rest, because they turn on something the values do not contain: an unstated currency, unit or pay period, what a code stands for, or a conflict with another column. A check that compared columns would catch the conflicts; this one does not.
- Most needs-context cases here were built so that the raw values are identical under each reading. A value-only check scoring 0% on those is true by construction. It shows what kind of evidence is needed, not that the checks are badly made.
- Both read all 120 rows. A model in `detect.py` sees ten. The comparison favours them on anything a full column reveals.
- These are generated tables with one problem per column. Real columns are messier, and real tools have more rules than these.
- A fair reading: these baselines are the floor a model has to beat, and a model that beats them on verdicts but passes needs-context columns as usable has not solved the problem either.
