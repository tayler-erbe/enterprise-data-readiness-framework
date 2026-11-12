"""The common shape every loader produces. Scoring only ever sees these."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Column:
    name: str
    data_type: str = ""
    description: str = ""
    lookup: str = ""  # lookup table or value list that decodes this column
    is_primary_key: bool = False
    foreign_key: str = ""  # what it points to, e.g. "FIN.CONTRACT.CONTRACT_ID"


@dataclass
class Table:
    schema: str
    name: str
    description: str = ""
    columns: list[Column] = field(default_factory=list)
    columns_known: bool = False  # False when the export has no column metadata
    column_count: int | None = None
    row_count: int | None = None
    index_count: int | None = None

    # Level 2
    grain: str = ""
    primary_key: list[str] = field(default_factory=list)
    foreign_keys: list[str] = field(default_factory=list)
    joins: list[str] = field(default_factory=list)

    # Level 3
    owner: str = ""
    valid_from: str = ""
    valid_to: str = ""
    exclude_from_reporting: bool | None = None
    trust_level: str = ""
    known_defects: str = ""
    advisory: str = ""
    advisory_date: str = ""

    # Level 4
    in_semantic_layer: bool | None = None
    verified_questions: int | None = None
    verified_questions_passed: int | None = None

    # Routing
    usage: float | None = None  # queries, reports, or any value measure
    privacy_tier: str = ""
    target_level: int | None = None
    source: str = ""  # which loader produced it

    @property
    def full_name(self) -> str:
        return f"{self.schema}.{self.name}" if self.schema else self.name
