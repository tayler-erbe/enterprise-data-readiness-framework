"""Loaders: turn a data dictionary export into Table objects.

Two sources so far:
- CSV, shaped like a data dictionary's table-list export (Schema, Name, Comments,
  Columns, Rows, Indices), with optional extra columns for confirmed fields and
  an optional second CSV of column metadata.
- OpenMetadata table entities, as returned by GET /api/v1/tables.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from .model import Column, Table

# Header aliases. Keys are normalized (lowercase, letters and digits only).
TABLE_FIELDS = {
    "schema": "schema", "schemaname": "schema", "owner_schema": "schema",
    "name": "name", "table": "name", "tablename": "name",
    "comments": "description", "comment": "description", "description": "description",
    "columns": "column_count", "columncount": "column_count",
    "rows": "row_count", "rowcount": "row_count",
    "indices": "index_count", "indexes": "index_count", "indexcount": "index_count",
    "grain": "grain",
    "primarykey": "primary_key", "pk": "primary_key",
    "foreignkeys": "foreign_keys", "foreignkey": "foreign_keys", "fk": "foreign_keys",
    "joins": "joins", "joinpaths": "joins",
    "owner": "owner", "steward": "owner", "dataowner": "owner", "datasteward": "owner",
    "validfrom": "valid_from", "validto": "valid_to",
    "excludefromreporting": "exclude_from_reporting",
    "trustlevel": "trust_level", "trust": "trust_level",
    "knowndefects": "known_defects",
    "advisory": "advisory", "dataqualityadvisory": "advisory",
    "advisorydate": "advisory_date",
    "insemanticlayer": "in_semantic_layer",
    "verifiedquestions": "verified_questions",
    "verifiedquestionspassed": "verified_questions_passed",
    "usage": "usage", "querycount": "usage", "queries": "usage",
    "privacytier": "privacy_tier", "tier": "privacy_tier",
    "targetlevel": "target_level",
}

COLUMN_FIELDS = {
    "schema": "schema", "schemaname": "schema",
    "table": "table", "tablename": "table",
    "column": "name", "columnname": "name", "name": "name",
    "datatype": "data_type", "type": "data_type",
    "comments": "description", "comment": "description", "description": "description",
    "lookup": "lookup", "valuelist": "lookup", "lookuptable": "lookup",
    "key": "key", "keytype": "key",
    "foreignkey": "foreign_key", "references": "foreign_key",
}

TRUE_WORDS = {"y", "yes", "true", "1", "x"}
FALSE_WORDS = {"n", "no", "false", "0"}


def _norm(header: str) -> str:
    return re.sub(r"[^a-z0-9]", "", header.lower())


def _int(value: str) -> int | None:
    value = (value or "").strip().replace(",", "")
    try:
        return int(float(value)) if value else None
    except ValueError:
        return None


def _float(value: str) -> float | None:
    value = (value or "").strip().replace(",", "")
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _bool(value: str) -> bool | None:
    value = (value or "").strip().lower()
    if value in TRUE_WORDS:
        return True
    if value in FALSE_WORDS:
        return False
    return None


def _list(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[;\n|]", value or "") if part.strip()]


def _read_csv(path: Path, aliases: dict[str, str]) -> list[dict[str, str]]:
    # utf-8-sig drops a byte order mark if Excel added one. Encoding damage in
    # the text itself is left alone on purpose: finding it is one of the checks.
    with open(path, newline="", encoding="utf-8-sig") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        delimiter = "\t" if sample.count("\t") > sample.count(",") else ","
        reader = csv.DictReader(handle, delimiter=delimiter)
        mapping = {h: aliases.get(_norm(h)) for h in reader.fieldnames or []}
        rows = []
        for raw in reader:
            row = {}
            for header, value in raw.items():
                key = mapping.get(header)
                if key and value is not None:
                    row[key] = value.strip()
            rows.append(row)
        return rows


def load_csv(tables_path: str | Path, columns_path: str | Path | None = None) -> list[Table]:
    tables: dict[tuple[str, str], Table] = {}
    for row in _read_csv(Path(tables_path), TABLE_FIELDS):
        if not row.get("name"):
            continue
        table = Table(
            schema=row.get("schema", ""),
            name=row["name"],
            description=row.get("description", ""),
            column_count=_int(row.get("column_count", "")),
            row_count=_int(row.get("row_count", "")),
            index_count=_int(row.get("index_count", "")),
            grain=row.get("grain", ""),
            primary_key=_list(row.get("primary_key", "")),
            foreign_keys=_list(row.get("foreign_keys", "")),
            joins=_list(row.get("joins", "")),
            owner=row.get("owner", ""),
            valid_from=row.get("valid_from", ""),
            valid_to=row.get("valid_to", ""),
            exclude_from_reporting=_bool(row.get("exclude_from_reporting", "")),
            trust_level=row.get("trust_level", ""),
            known_defects=row.get("known_defects", ""),
            advisory=row.get("advisory", ""),
            advisory_date=row.get("advisory_date", ""),
            in_semantic_layer=_bool(row.get("in_semantic_layer", "")),
            verified_questions=_int(row.get("verified_questions", "")),
            verified_questions_passed=_int(row.get("verified_questions_passed", "")),
            usage=_float(row.get("usage", "")),
            privacy_tier=row.get("privacy_tier", "").upper(),
            target_level=_int(row.get("target_level", "")),
            source="csv",
        )
        tables[(table.schema.upper(), table.name.upper())] = table

    if columns_path:
        for row in _read_csv(Path(columns_path), COLUMN_FIELDS):
            key = (row.get("schema", "").upper(), row.get("table", "").upper())
            table = tables.get(key)
            if table is None or not row.get("name"):
                continue
            key_type = row.get("key", "").upper()
            table.columns.append(Column(
                name=row["name"],
                data_type=row.get("data_type", ""),
                description=row.get("description", ""),
                lookup=row.get("lookup", ""),
                is_primary_key=key_type in {"PK", "PRIMARY", "PRIMARY KEY", "PRIMARY_KEY"},
                foreign_key=row.get("foreign_key", ""),
            ))
            table.columns_known = True
        for table in tables.values():
            pk_cols = [c.name for c in table.columns if c.is_primary_key]
            if pk_cols and not table.primary_key:
                table.primary_key = pk_cols
            for column in table.columns:
                if column.foreign_key:
                    link = f"{column.name} -> {column.foreign_key}"
                    if link not in table.foreign_keys:
                        table.foreign_keys.append(link)

    return list(tables.values())


# ---------------------------------------------------------------- OpenMetadata

# Custom property names this scorer reads from a table's `extension` block.
# Create them on the Table entity type in OpenMetadata to hold confirmed fields.
OM_EXTENSION_FIELDS = {
    "grain": "grain",
    "validFrom": "valid_from",
    "validTo": "valid_to",
    "excludeFromReporting": "exclude_from_reporting",
    "trustLevel": "trust_level",
    "knownDefects": "known_defects",
    "advisory": "advisory",
    "advisoryDate": "advisory_date",
    "inSemanticLayer": "in_semantic_layer",
    "verifiedQuestions": "verified_questions",
    "verifiedQuestionsPassed": "verified_questions_passed",
    "privacyTier": "privacy_tier",
    "targetLevel": "target_level",
}


def _om_schema(entity: dict) -> str:
    schema = entity.get("databaseSchema") or {}
    if schema.get("name"):
        return schema["name"]
    parts = (entity.get("fullyQualifiedName") or "").split(".")
    return parts[-2] if len(parts) >= 2 else ""


def _om_owner(entity: dict) -> str:
    owners = entity.get("owners")
    if owners is None and entity.get("owner"):  # releases before 1.5 had one owner
        owners = [entity["owner"]]
    names = [o.get("displayName") or o.get("name") or "" for o in owners or []]
    return ", ".join(n for n in names if n)


def table_from_openmetadata(entity: dict) -> Table:
    columns = []
    for col in entity.get("columns") or []:
        columns.append(Column(
            name=col.get("name", ""),
            data_type=col.get("dataTypeDisplay") or col.get("dataType", ""),
            description=col.get("description") or "",
            lookup=(col.get("extension") or {}).get("lookup", ""),
            is_primary_key=col.get("constraint") == "PRIMARY_KEY",
        ))

    primary_key = [c.name for c in columns if c.is_primary_key]
    foreign_keys = []
    for constraint in entity.get("tableConstraints") or []:
        kind = constraint.get("constraintType")
        cols = constraint.get("columns") or []
        if kind == "PRIMARY_KEY":
            primary_key = primary_key or cols
        elif kind == "FOREIGN_KEY":
            refs = constraint.get("referredColumns") or []
            foreign_keys.append(f"{', '.join(cols)} -> {', '.join(refs)}")
            by_name = {c.name: c for c in columns}
            for name, ref in zip(cols, refs):
                if name in by_name:
                    by_name[name].foreign_key = ref

    usage = None
    summary = entity.get("usageSummary") or {}
    for window in ("monthlyStats", "weeklyStats", "dailyStats"):
        if (summary.get(window) or {}).get("count") is not None:
            usage = float(summary[window]["count"])
            break

    profile = entity.get("profile") or {}
    table = Table(
        schema=_om_schema(entity),
        name=entity.get("name", ""),
        description=entity.get("description") or "",
        columns=columns,
        columns_known="columns" in entity,
        column_count=len(columns) if "columns" in entity else None,
        row_count=profile.get("rowCount"),
        primary_key=primary_key,
        foreign_keys=foreign_keys,
        owner=_om_owner(entity),
        usage=usage,
        source="openmetadata",
    )

    extension = entity.get("extension") or {}
    for om_key, attr in OM_EXTENSION_FIELDS.items():
        if om_key not in extension:
            continue
        value = extension[om_key]
        if attr in {"exclude_from_reporting", "in_semantic_layer"}:
            value = value if isinstance(value, bool) else _bool(str(value))
        elif attr in {"verified_questions", "verified_questions_passed", "target_level"}:
            value = _int(str(value))
        elif attr == "privacy_tier":
            value = str(value).upper()
        else:
            value = str(value)
        setattr(table, attr, value)
    return table


def load_openmetadata(path: str | Path) -> list[Table]:
    """Read a saved response from GET /api/v1/tables?fields=columns,owners,
    tableConstraints,extension,usageSummary,profile (a {"data": [...]} page, a
    list of pages, or a bare list of table entities)."""
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    pages = payload if isinstance(payload, list) else [payload]
    entities = []
    for page in pages:
        if isinstance(page, dict) and "data" in page:
            entities.extend(page["data"])
        elif isinstance(page, dict):
            entities.append(page)
    return [table_from_openmetadata(e) for e in entities]


# ------------------------------------------------------- dictionary pages

def load_dictionary_pages(path: str | Path, schema: str = "DW") -> list[Table]:
    """Read table detail pages copied from a data dictionary tool's browser view
    and pasted into one text file. Each page starts at "Table Name : X" and has
    a Comment line, a Columns grid (Ordinal, Column, Comments, Datatype, PK/FK,
    Primary Definition) and an Indexes list. Index pages are skipped."""
    text = Path(path).read_text(encoding="utf-8-sig")
    tables = []
    for block in re.split(r"(?m)^\s*Table Name\s*:\s*", text)[1:]:
        lines = block.splitlines()
        name = lines[0].strip()
        table = Table(schema=schema, name=name, source="dictionary-page")
        section = None
        for line in lines[1:]:
            stripped = line.strip()
            if re.match(r"^(Data Model\s*:|Index\s*:)", stripped):
                break  # the next page started
            if stripped.startswith("Comment:"):
                table.description = line.split(":", 1)[1].strip()
                continue
            if stripped.startswith("Row count:"):
                table.row_count = _int(line.split(":", 1)[1])
                continue
            if stripped == "Columns":
                section = "columns"
                continue
            if stripped == "Indexes":
                section = "indexes"
                table.index_count = 0
                continue
            if section == "columns":
                cells = line.split("\t")
                if len(cells) < 4 or not cells[0].strip().isdigit():
                    continue
                cells += [""] * 6
                key = cells[4].strip().lower()
                table.columns.append(Column(
                    name=cells[1].strip(),
                    description=cells[2].strip(),
                    data_type=cells[3].strip(),
                    is_primary_key="primary" in key,
                    foreign_key=cells[4].strip() if "foreign" in key else "",
                ))
            elif section == "indexes" and stripped and stripped != "Name":
                table.index_count += 1
        table.columns_known = bool(table.columns)
        table.column_count = len(table.columns) or None
        table.primary_key = [c.name for c in table.columns if c.is_primary_key]
        tables.append(table)
    return tables
