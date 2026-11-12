"""Deterministic checks. Each one returns pass, fail or unknown, never a guess.

"unknown" means the export doesn't hold enough to tell, for example a table list
with no column metadata. Unknown never counts as a pass.
"""

from __future__ import annotations

import re
import urllib.request
from dataclasses import dataclass, field

from .model import Column, Table

PASS, FAIL, UNKNOWN = "pass", "fail", "unknown"


@dataclass
class Settings:
    column_coverage: float = 0.8  # share of columns that must be described for level 2
    min_verified_questions: int = 5  # level 4
    verified_pass_rate: float = 0.9  # level 4
    short_description_words: int = 8  # below this, warn
    code_column_pattern: str = r"(_CD|_CODE|_TYP|_TYPE_CD)$"
    default_target_level: int = 4
    check_links: bool = False
    link_timeout: float = 5.0
    link_results: dict[str, bool] = field(default_factory=dict)  # url -> resolves


@dataclass
class Check:
    id: str
    level: int
    status: str
    detail: str


# ------------------------------------------------------------ text patterns

PLACEHOLDERS = {
    "", "tbd", "todo", "n/a", "na", "none", "null", "-", "--", "?", ".", "x",
    "description", "no description", "test", "temp", "placeholder", "see above",
}

# Mojibake left behind when UTF-8 text is read as Windows-1252 or Latin-1,
# plus the Unicode replacement character.
ENCODING_DAMAGE = re.compile("Â|â€|Ã[\u0080-¿]|�")

GRAIN = re.compile(
    r"\b(one|a single|1)\s+(row|record|line|entry)\s+(per|for each|for every)\b"
    r"|\beach\s+(row|record)\s+(represents|is|holds|contains)\b"
    r"|\bunique\s+(per|by|for each)\b",
    re.IGNORECASE,
)

# Rules that live in prose and should be fields. Category -> patterns.
PROSE_RULES = {
    "validity window": re.compile(
        r"\bdo not use (for|after|before|from)\b"
        r"|\b(decommissioned|discontinued|retired)\b"
        r"|\bno longer (used|maintained|populated|updated)\b"
        r"|\bnot (valid|populated|maintained) (after|before|since|prior to)\b"
        r"|\b(prior to|before|after|since)\s+([a-z]+\s+)?\d{4}\b",
        re.IGNORECASE,
    ),
    "exclude from reporting": re.compile(
        r"\bnot (useful|intended|meant|to be used) for reporting\b"
        r"|\bdo not (use|report) (for|from|in) reporting\b"
        r"|\bnot for reporting\b"
        r"|\binternal (use|infrastructure) only\b",
        re.IGNORECASE,
    ),
    "trust level": re.compile(
        r"\bself[- ]reported\b|\bunverified\b|\bnot (been )?verified\b"
        r"|\bno (systematic )?verification\b",
        re.IGNORECASE,
    ),
    "known defect": re.compile(
        r"\b(may|might|can) contain (invalid|incorrect|bad|anomalous|duplicate)\b"
        r"|\banomal(y|ies|ous)\b|\bknown (issue|defect|problem)s?\b"
        r"|\bdata quality (advisory|issue)\b|\binvalid (dates?|values?|records?)\b",
        re.IGNORECASE,
    ),
}

RULE_FIELD = {
    "validity window": lambda t: bool(t.valid_from or t.valid_to),
    "exclude from reporting": lambda t: t.exclude_from_reporting is not None,
    "trust level": lambda t: bool(t.trust_level),
    "known defect": lambda t: bool(t.known_defects or t.advisory),
}

URL = re.compile(r"https?://[^\s\"'<>)\]]+", re.IGNORECASE)

# Name fragments that suggest restricted data (privacy tier C). A suggestion
# only: a steward assigns the real tier.
SENSITIVE_NAME = re.compile(
    r"MEDICAL|MED_COND|HEALTH|DISAB|RACE|ETHN|_ETH_|GENDER|SEX_|SSN|BIRTH"
    r"|HR_NOTE|DISCIPL|GRIEV|VISA|CITIZEN|CREDIT_APPL|BENEFIT|SALARY",
    re.IGNORECASE,
)


def is_placeholder(text: str, table_name: str = "") -> bool:
    clean = re.sub(r"\s+", " ", text or "").strip().strip(".").lower()
    if clean in PLACEHOLDERS:
        return True
    squashed = re.sub(r"[^a-z0-9]", "", clean)
    name = re.sub(r"[^a-z0-9]", "", table_name.lower())
    stripped_name = re.sub(r"^t", "", name)
    return bool(squashed) and squashed in {name, stripped_name}


def has_encoding_damage(text: str) -> bool:
    return bool(ENCODING_DAMAGE.search(text or ""))


def is_readable(text: str, name: str = "") -> bool:
    # Encoding damage (a stray Â) is a copy-paste artifact, not missing
    # documentation, so it is a warning rather than a reason to fail.
    return bool((text or "").strip()) and not is_placeholder(text, name)


def prose_rules(text: str) -> dict[str, str]:
    """Category -> the sentence that triggered it."""
    found = {}
    sentences = re.split(r"(?<=[.;!?])\s+", text or "")
    for category, pattern in PROSE_RULES.items():
        for sentence in sentences:
            if pattern.search(sentence):
                found[category] = sentence.strip()[:160]
                break
    return found


def is_code_column(column: Column, settings: Settings) -> bool:
    return bool(re.search(settings.code_column_pattern, column.name, re.IGNORECASE))


def _stem(name: str) -> str:
    return re.sub(r"_(CD|CODE|TYP|TYPE_CD)$", "", name.upper())


def is_decoded(column: Column, table: Table) -> bool:
    """A coded column is decoded when it points to a lookup, when this table is
    its lookup (a code table keyed on it), or when the same table carries its
    description alongside (JOB_GRADE_CD next to JOB_GRADE_DESC)."""
    if column.lookup or column.foreign_key:
        return True
    in_key = column.is_primary_key or column.name.upper() in {k.upper() for k in table.primary_key}
    table_stem = re.sub(r"^T_|_HIST$", "", table.name.upper())
    if in_key and (_stem(column.name) == _stem(table_stem) or not re.search(r"_CD(_HIST)?$", table.name.upper()) and len(table.primary_key) == 1):
        return True
    stem = _stem(column.name)
    return any(
        other.name.upper() != column.name.upper()
        and other.name.upper().startswith(stem + "_")
        and re.search(r"_(DESC|NAME|TITLE)$", other.name.upper())
        for other in table.columns
    )


def link_resolves(url: str, settings: Settings) -> bool:
    if url in settings.link_results:
        return settings.link_results[url]
    ok = False
    for method in ("HEAD", "GET"):
        try:
            request = urllib.request.Request(url, method=method, headers={"User-Agent": "readiness-scorer"})
            with urllib.request.urlopen(request, timeout=settings.link_timeout) as response:
                ok = response.status < 400
        except Exception:
            ok = False
        if ok:
            break
    settings.link_results[url] = ok
    return ok


# ------------------------------------------------------------ the checks

def run_checks(table: Table, s: Settings) -> list[Check]:
    checks: list[Check] = []
    add = lambda cid, level, status, detail: checks.append(Check(cid, level, status, detail))
    desc = table.description or ""

    # Level 1: described
    if desc.strip():
        add("table_description", 1, PASS, "Table description present.")
    else:
        add("table_description", 1, FAIL, "No table description.")

    if not desc.strip():
        add("description_readable", 1, FAIL, "Nothing to read.")
    elif is_placeholder(desc, table.name):
        add("description_readable", 1, FAIL, f"Description is a placeholder: {desc.strip()[:40]!r}.")
    else:
        add("description_readable", 1, PASS, "Description is readable.")

    # Level 2: usable
    if table.grain.strip():
        add("grain", 2, PASS, f"Grain recorded: {table.grain.strip()}")
    else:
        match = GRAIN.search(desc)
        if match:
            add("grain", 2, PASS, "Grain stated in the description; confirm it as a field.")
        else:
            add("grain", 2, FAIL, "Grain not stated. Say what one row is.")

    if table.primary_key or table.foreign_keys or table.joins:
        parts = []
        if table.primary_key:
            parts.append("primary key " + ", ".join(table.primary_key))
        if table.foreign_keys:
            parts.append(f"{len(table.foreign_keys)} foreign key(s)")
        if table.joins:
            parts.append(f"{len(table.joins)} confirmed join path(s)")
        add("keys_and_joins", 2, PASS, "Documented: " + "; ".join(parts) + ".")
    elif table.index_count:
        add("keys_and_joins", 2, UNKNOWN, f"{table.index_count} index(es) exist but no key or join is named.")
    else:
        add("keys_and_joins", 2, FAIL, "No primary key, foreign key or join path documented.")

    if not table.columns_known:
        add("column_coverage", 2, UNKNOWN, "No column metadata in this export, so column coverage can't be checked.")
        add("codes_decoded", 2, UNKNOWN, "No column metadata in this export, so coded columns can't be checked.")
    else:
        total = len(table.columns)
        described = sum(is_readable(c.description, c.name) for c in table.columns)
        share = described / total if total else 0.0
        status = PASS if total and share >= s.column_coverage else FAIL
        add("column_coverage", 2, status,
            f"{described} of {total} columns described ({share:.0%}; need {s.column_coverage:.0%}).")

        coded = [c for c in table.columns if is_code_column(c, s)]
        undecoded = [c.name for c in coded if not is_decoded(c, table)]
        if not coded:
            add("codes_decoded", 2, PASS, "No coded columns.")
        elif undecoded:
            add("codes_decoded", 2, FAIL,
                f"{len(undecoded)} of {len(coded)} coded columns have no lookup: {', '.join(undecoded[:6])}"
                + ("..." if len(undecoded) > 6 else ""))
        else:
            add("codes_decoded", 2, PASS, f"All {len(coded)} coded columns link to a lookup.")

    # Level 3: governed
    if table.owner.strip():
        add("owner", 3, PASS, f"Owner: {table.owner.strip()}")
    else:
        add("owner", 3, FAIL, "No named owner or steward.")

    if table.trust_level.strip():
        add("usage_rules", 3, PASS, f"Trust level: {table.trust_level.strip()}")
    else:
        add("usage_rules", 3, FAIL, "No trust level recorded (for example: system of record, self-reported).")

    uncaptured = {cat: text for cat, text in prose_rules(desc).items() if not RULE_FIELD[cat](table)}
    if uncaptured:
        add("prose_rules_captured", 3, FAIL,
            "Rules in prose, not in fields: "
            + " | ".join(f"{cat}: \"{text}\"" for cat, text in uncaptured.items()))
    else:
        add("prose_rules_captured", 3, PASS, "No rules left in prose.")

    has_advisory = bool(table.advisory.strip() or table.known_defects.strip())
    if has_advisory and not table.advisory_date.strip():
        add("advisory_dated", 3, FAIL, "Advisory or known defect has no date.")
    else:
        add("advisory_dated", 3, PASS, "Advisory dated." if has_advisory else "No advisory to date.")

    urls = sorted(set(URL.findall(desc + " " + table.advisory)))
    if not urls:
        add("links_resolve", 3, PASS, "No links.")
    elif not s.check_links:
        add("links_resolve", 3, UNKNOWN, f"{len(urls)} link(s) not checked. Run with --check-links.")
    else:
        broken = [u for u in urls if not link_resolves(u, s)]
        if broken:
            add("links_resolve", 3, FAIL, "Broken link(s): " + ", ".join(broken))
        else:
            add("links_resolve", 3, PASS, f"{len(urls)} link(s) resolve.")

    # Level 4: AI-ready
    if table.in_semantic_layer:
        add("in_semantic_layer", 4, PASS, "In the semantic layer.")
    elif table.in_semantic_layer is None:
        add("in_semantic_layer", 4, FAIL, "Not recorded as in the semantic layer.")
    else:
        add("in_semantic_layer", 4, FAIL, "Not in the semantic layer.")

    asked = table.verified_questions or 0
    passed = table.verified_questions_passed or 0
    if asked < s.min_verified_questions:
        add("verified_questions", 4, FAIL, f"{asked} verified question(s); need {s.min_verified_questions}.")
    elif passed / asked < s.verified_pass_rate:
        add("verified_questions", 4, FAIL,
            f"{passed} of {asked} verified questions pass; need {s.verified_pass_rate:.0%}.")
    else:
        add("verified_questions", 4, PASS, f"{passed} of {asked} verified questions pass.")

    return checks


def warnings_for(table: Table, s: Settings) -> list[str]:
    """Things worth fixing that don't block a level."""
    out = []
    desc = (table.description or "").strip()
    words = len(desc.split())
    if desc and not is_placeholder(desc, table.name) and words < s.short_description_words:
        out.append(f"Short description ({words} words).")
    if any(u.lower().startswith("http://") for u in URL.findall(desc + " " + table.advisory)):
        out.append("Link uses http://; likely an old address.")
    if table.columns_known and table.column_count is not None and table.column_count != len(table.columns):
        out.append(f"Table says {table.column_count} columns; export lists {len(table.columns)}.")
    if table.row_count is None:
        out.append("No row count.")
    if has_encoding_damage(desc):
        out.append("Encoding damage in description (for example Â or â€œ). Re-save as UTF-8.")
    if table.columns_known:
        damaged = [c.name for c in table.columns if has_encoding_damage(c.description)]
        if damaged:
            out.append("Encoding damage in column descriptions: " + ", ".join(damaged[:6]))
        seen: dict[str, str] = {}
        for c in table.columns:
            text = re.sub(r"\s+", " ", c.description or "").strip().lower()
            if len(text.split()) >= 6:
                if text in seen:
                    out.append(f"{c.name} has the same description as {seen[text]}; one is probably a copy-paste error.")
                else:
                    seen[text] = c.name
        if table.primary_key and not table.grain:
            out.append("Draft grain from the key, to confirm: one row per " + ", ".join(table.primary_key) + ".")
    return out


SENSITIVE_COLUMN = re.compile(
    r"^(SSN|SSN_.*|.*_SSN|BIRTH_DT|.*_BIRTH_DT|.*_FNAME|.*_LNAME|.*_MNAME|PASSPORT.*|.*RACE.*|.*ETH_CD|SEX_CD|GENDER.*|.*MEDICAL.*|VISA.*)$",
    re.IGNORECASE,
)


def sensitive_columns(table: Table) -> list[str]:
    return [c.name for c in table.columns if SENSITIVE_COLUMN.match(c.name)]


def suggest_tier(table: Table) -> str:
    if table.privacy_tier:
        return table.privacy_tier
    if SENSITIVE_NAME.search(table.name) or sensitive_columns(table):
        return "C?"
    return ""
