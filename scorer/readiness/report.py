"""Write the scorecard, owner work lists, and machine-readable scores."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from .checks import Settings, sensitive_columns
from .score import LEVEL_NAMES, PASS, UNKNOWN, TableScore, ranked

CHECK_IDS = [
    "table_description", "description_readable",
    "grain", "keys_and_joins", "column_coverage", "codes_decoded",
    "owner", "usage_rules", "prose_rules_captured", "advisory_dated", "links_resolve",
    "in_semantic_layer", "verified_questions",
]

CHECK_LABELS = {
    "table_description": "Table description",
    "description_readable": "Readable description",
    "grain": "Grain stated",
    "keys_and_joins": "Keys or joins",
    "column_coverage": "Columns described",
    "codes_decoded": "Codes decoded",
    "owner": "Named owner",
    "usage_rules": "Trust level",
    "prose_rules_captured": "Rules out of prose",
    "advisory_dated": "Advisory dated",
    "links_resolve": "Links resolve",
    "in_semantic_layer": "In semantic layer",
    "verified_questions": "Verified questions",
}


def _md(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ")


def write_scores_csv(scores: list[TableScore], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "schema", "table", "level", "level_name", "target", "gap", "usage", "priority",
            "owner", "privacy_tier", "next_steps", "cannot_tell", "rules_in_prose", "warnings",
            *CHECK_IDS,
        ])
        for s in ranked(scores):
            status = {c.id: c.status for c in s.checks}
            writer.writerow([
                s.table.schema, s.table.name, s.level, LEVEL_NAMES[s.level], s.target, s.gap,
                "" if s.table.usage is None else f"{s.table.usage:g}",
                "" if s.priority is None else f"{s.priority:g}",
                s.table.owner, s.suggested_tier,
                " | ".join(c.detail for c in s.blocking()),
                " | ".join(c.detail for c in s.unknowns),
                " | ".join(f"{k}: {v}" for k, v in s.prose_rules.items()),
                " | ".join(s.warnings),
                *[status.get(cid, "") for cid in CHECK_IDS],
            ])


def write_columns_csv(scores: list[TableScore], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["schema", "table", "column", "described", "coded", "decoded"])
        for s in scores:
            for c in s.columns:
                writer.writerow([
                    s.table.schema, s.table.name, c.name,
                    "yes" if c.described else "no",
                    "yes" if c.coded else "no",
                    "" if c.decoded is None else ("yes" if c.decoded else "no"),
                ])


def write_json(scores: list[TableScore], path: Path) -> None:
    out = []
    for s in ranked(scores):
        out.append({
            "schema": s.table.schema,
            "table": s.table.name,
            "level": s.level,
            "level_name": LEVEL_NAMES[s.level],
            "target": s.target,
            "gap": s.gap,
            "usage": s.table.usage,
            "priority": s.priority,
            "owner": s.table.owner,
            "privacy_tier": s.suggested_tier,
            "checks": [{"id": c.id, "level": c.level, "status": c.status, "detail": c.detail} for c in s.checks],
            "rules_in_prose": s.prose_rules,
            "warnings": s.warnings,
            "columns": [vars(c) for c in s.columns],
        })
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")


def scorecard_markdown(scores: list[TableScore], settings: Settings, source: str) -> str:
    total = len(scores)
    by_level = Counter(s.level for s in scores)
    by_schema: dict[str, Counter] = defaultdict(Counter)
    for s in scores:
        by_schema[s.table.schema or "(none)"][s.level] += 1

    lines = [
        "# Readiness scorecard",
        "",
        f"{total} tables from {source}, scored {date.today().isoformat()}.",
        "",
        "| Level | Tables | Share |",
        "| --- | ---: | ---: |",
    ]
    for level in range(5):
        n = by_level.get(level, 0)
        lines.append(f"| {level} {LEVEL_NAMES[level]} | {n} | {n / total:.0%} |" if total else f"| {level} {LEVEL_NAMES[level]} | 0 | |")

    lines += ["", "## By schema", "", "| Schema | 0 | 1 | 2 | 3 | 4 | Tables |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for schema in sorted(by_schema):
        counts = by_schema[schema]
        lines.append(f"| {schema} | " + " | ".join(str(counts.get(l, 0) or "") for l in range(5)) + f" | {sum(counts.values())} |")

    fails, unknowns = Counter(), Counter()
    for s in scores:
        for c in s.blocking():
            (unknowns if c.status == UNKNOWN else fails)[(c.level, c.id)] += 1
    blocking = set(fails) | set(unknowns)
    if blocking:
        lines += [
            "", "## What blocks the next level", "",
            "Each table counts against the level it's trying to reach. \"Fails\" means the documentation is missing;",
            "\"can't tell\" means the export doesn't carry enough to check.", "",
            "| Next level | Check | Fails | Can't tell |", "| --- | --- | ---: | ---: |",
        ]
        for level, cid in sorted(blocking, key=lambda k: (k[0], -(fails[k] + unknowns[k]), CHECK_IDS.index(k[1]))):
            lines.append(f"| {level} {LEVEL_NAMES[level]} | {CHECK_LABELS[cid]} | {fails[(level, cid)] or ''} | {unknowns[(level, cid)] or ''} |")

    unknown = Counter(c.id for s in scores for c in s.unknowns)
    if unknown:
        lines += ["", "## What this export can't tell", "", "These count as not met. Better metadata, not better documentation, would settle them.", "",
                  "| Check | Tables |", "| --- | ---: |"]
        for cid, n in unknown.most_common():
            lines.append(f"| {CHECK_LABELS[cid]} | {n} |")

    rules = Counter(cat for s in scores for cat in s.prose_rules)
    if rules:
        lines += ["", "## Rules sitting in prose", "",
                  "Candidates for extraction into fields. A person confirms each one.", "",
                  "| Rule | Tables |", "| --- | ---: |"]
        for cat, n in rules.most_common():
            lines.append(f"| {cat} | {n} |")

    tiers = [s for s in scores if s.suggested_tier == "C?"]
    if tiers:
        lines += ["", "## Possible restricted tables", "",
                  "Names suggest privacy tier C. A steward confirms the tier before any profiling or AI drafting.", ""]
        lines.append(", ".join(f"`{s.table.full_name}`" for s in tiers))

    lines += [
        "", "## Settings", "",
        f"- Column coverage for level 2: {settings.column_coverage:.0%}",
        f"- Verified questions for level 4: {settings.min_verified_questions}, pass rate {settings.verified_pass_rate:.0%}",
        f"- Default target level: {settings.default_target_level}",
        f"- Links checked: {'yes' if settings.check_links else 'no'}",
        "",
    ]
    return "\n".join(lines)


def worklist_markdown(scores: list[TableScore]) -> str:
    by_owner: dict[str, list[TableScore]] = defaultdict(list)
    for s in scores:
        if s.gap > 0:
            by_owner[s.table.owner.strip() or "No owner on record"].append(s)

    has_usage = any(s.table.usage is not None for s in scores)
    lines = [
        "# Owner work lists",
        "",
        ("Ranked by priority (usage x gap)." if has_usage else
         "Ranked by gap. This export has no usage figures, so priority can't be computed yet."),
        "Nothing here changes a score until the owner confirms it.",
        "",
    ]
    order = sorted(by_owner, key=lambda o: (o == "No owner on record", -len(by_owner[o]), o))
    for owner in order:
        items = ranked(by_owner[owner])
        lines += [f"## {owner}", "", f"{len(items)} table(s) below target.", ""]
        for s in items:
            head = f"### `{s.table.full_name}`: level {s.level} {LEVEL_NAMES[s.level]}, target {s.target}"
            if s.priority is not None:
                head += f", priority {s.priority:g}"
            lines += [head, ""]
            if s.suggested_tier:
                tier = s.suggested_tier
                cols = sensitive_columns(s.table)
                why = f"columns {', '.join(cols[:6])}" if cols else "the name"
                lines.append(f"- Privacy tier: {f'C, suggested from {why}; confirm with the steward' if tier == 'C?' else tier}")
            blocking = s.blocking()
            for c in blocking:
                prefix = "Can't tell yet" if c.status == UNKNOWN else f"To reach level {c.level}"
                lines.append(f"- {prefix}: {_md(c.detail)}")
            # Rules still in prose, when they aren't already listed as a blocker.
            rules_open = any(c.id == "prose_rules_captured" and c.status != PASS for c in s.checks)
            if rules_open and not any(c.id == "prose_rules_captured" for c in blocking):
                captured = next(c for c in s.checks if c.id == "prose_rules_captured")
                lines.append(f"- Later, for level 3: {_md(captured.detail)}")
            for w in s.warnings:
                lines.append(f"- Note: {_md(w)}")
            lines.append("")
    return "\n".join(lines)


def write_all(scores: list[TableScore], out_dir: Path, settings: Settings, source: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "scores.csv": lambda p: write_scores_csv(scores, p),
        "columns.csv": lambda p: write_columns_csv(scores, p),
        "scores.json": lambda p: write_json(scores, p),
        "scorecard.md": lambda p: p.write_text(scorecard_markdown(scores, settings, source), encoding="utf-8"),
        "worklist.md": lambda p: p.write_text(worklist_markdown(scores), encoding="utf-8"),
    }
    written = []
    for name, write in paths.items():
        path = out_dir / name
        write(path)
        written.append(path)
    return written


def summary_text(scores: list[TableScore]) -> str:
    by_level = Counter(s.level for s in scores)
    parts = [f"{by_level.get(l, 0)} at {l} {LEVEL_NAMES[l]}" for l in range(5)]
    passed_all = sum(all(c.status == PASS for c in s.checks) for s in scores)
    return f"{len(scores)} tables: " + ", ".join(parts) + f". {passed_all} pass every check."
