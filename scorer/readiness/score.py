"""Turn checks into a level, a gap and a priority."""

from __future__ import annotations

from dataclasses import dataclass, field

from .checks import FAIL, PASS, UNKNOWN, Check, Settings, is_code_column, is_decoded, is_readable, prose_rules, run_checks, suggest_tier, warnings_for
from .model import Table

LEVEL_NAMES = {0: "Undocumented", 1: "Described", 2: "Usable", 3: "Governed", 4: "AI-ready"}


@dataclass
class ColumnScore:
    name: str
    described: bool
    coded: bool
    decoded: bool | None  # None when the column isn't coded


@dataclass
class TableScore:
    table: Table
    level: int
    checks: list[Check]
    warnings: list[str]
    prose_rules: dict[str, str]
    suggested_tier: str
    target: int
    columns: list[ColumnScore] = field(default_factory=list)

    @property
    def gap(self) -> int:
        return max(0, self.target - self.level)

    @property
    def priority(self) -> float | None:
        """Value x gap. None when the export has no usage figure."""
        if self.table.usage is None:
            return None
        return self.table.usage * self.gap

    @property
    def next_level(self) -> int | None:
        return self.level + 1 if self.level < 4 else None

    def blocking(self) -> list[Check]:
        """What stands between this table and the next level."""
        if self.next_level is None:
            return []
        return [c for c in self.checks if c.level == self.next_level and c.status != PASS]

    @property
    def unknowns(self) -> list[Check]:
        return [c for c in self.checks if c.status == UNKNOWN]


def level_from(checks: list[Check]) -> int:
    """A table reaches a level only when every check for that level and the
    levels below it passes."""
    level = 0
    for candidate in (1, 2, 3, 4):
        if all(c.status == PASS for c in checks if c.level == candidate):
            level = candidate
        else:
            break
    return level


def score_table(table: Table, settings: Settings) -> TableScore:
    checks = run_checks(table, settings)
    columns = []
    for column in table.columns:
        coded = is_code_column(column, settings)
        columns.append(ColumnScore(
            name=column.name,
            described=is_readable(column.description, column.name),
            coded=coded,
            decoded=is_decoded(column, table) if coded else None,
        ))
    target = table.target_level if table.target_level is not None else settings.default_target_level
    return TableScore(
        table=table,
        level=level_from(checks),
        checks=checks,
        warnings=warnings_for(table, settings),
        prose_rules=prose_rules(table.description),
        suggested_tier=suggest_tier(table),
        target=max(0, min(4, target)),
        columns=columns,
    )


def score_all(tables: list[Table], settings: Settings | None = None) -> list[TableScore]:
    settings = settings or Settings()
    return [score_table(t, settings) for t in tables]


def ranked(scores: list[TableScore]) -> list[TableScore]:
    """Tables at target last. Otherwise priority first when usage is known, then
    biggest gap, then name."""
    return sorted(
        scores,
        key=lambda s: (s.gap == 0, -(s.priority if s.priority is not None else -1), -s.gap, s.table.full_name),
    )


__all__ = ["LEVEL_NAMES", "ColumnScore", "TableScore", "level_from", "ranked", "score_all", "score_table", "FAIL", "PASS", "UNKNOWN"]
