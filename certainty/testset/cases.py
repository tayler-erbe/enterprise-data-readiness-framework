"""The catalogue of test cases: every kind of column the detector has to judge.

Each case builds one column (sometimes with helper columns beside it) in two
forms: `raw`, as the data arrives, and `clean`, as it should be after correct
preparation. Each case carries one of four verdicts:

    READY          usable as it is
    FIXABLE        usable after a fix that the data itself determines
    NEEDS_CONTEXT  cannot be read reliably without a data dictionary or the owner
    GARBAGE        no fix recovers it

FIXABLE cases come with a reference fixer that turns raw into clean. The tests
run it, so the answer key is checked by a second piece of code.

NEEDS_CONTEXT cases with `alts` have two or more meanings that fit the values
equally well. The raw values do not depend on which is true; the tests prove
that by generating the column under each meaning from the same seed.

Everything is invented. Standard library only.
"""
import datetime as dt
import difflib
import random
import re
from collections import Counter

READY, FIXABLE, NEEDS_CONTEXT, GARBAGE = "READY", "FIXABLE", "NEEDS_CONTEXT", "GARBAGE"
CASES = {}

FIRST = ["Ana", "Ben", "Chloe", "Dev", "Elif", "Farid", "Grace", "Hiro", "Ines", "Jon", "Kemi", "Luca", "Mona", "Noor", "Omar", "Priya"]
LAST = ["Abel", "Brandt", "Castro", "Dunne", "Eze", "Farrow", "Gallo", "Haas", "Ito", "Jensen", "Koval", "Lindqvist", "Moreau", "Nwosu", "Ortiz", "Petrov"]
ACCENTED = ["José Núñez", "Zoë Müller", "Renée François", "Søren Aaberg", "Iñigo Peña", "Chloé Lefèvre", "Jürgen Köhler", "Noémie Güell"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
BOTH_STATE_AND_COUNTRY = ["AL", "AR", "CA", "CO", "DE", "GA", "ID", "IL", "IN", "LA", "MA", "MD", "ME", "MN", "MO", "MT", "NC", "NE", "PA", "SC", "SD", "TN", "VA"]
ZIPS = ["02134", "07030", "10001", "60614", "94110", "00501", "30301", "73301", "06510", "80202", "01002", "08540"]
EPOCH_BASE = int(dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc).timestamp())


def case(cid, verdict, issue, meaning, op="", settled_by="values", alts=(), name_free=False, fix=None):
    """Register a case. `make(rng, n, dom, truth)` returns {"name", "raw", "clean"} plus optional "helpers" and "truth"."""
    def register(make):
        CASES[cid] = {"id": cid, "verdict": verdict, "issue": issue, "meaning": meaning, "op": op, "settled_by": settled_by,
                      "alts": list(alts), "name_free": name_free, "make": make, "fix": fix}
        return make
    return register


# ---------- helpers ----------

def rand_dates(rng, n, y0=2021, y1=2026):
    start = dt.date(y0, 1, 1)
    span = (dt.date(y1, 12, 31) - start).days + 1
    return [start + dt.timedelta(days=rng.randrange(span)) for _ in range(n)]


def iso_ts(seconds):
    return dt.datetime.fromtimestamp(seconds, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sprinkle(rng, n, share):
    """Row positions to alter: at least two, about `share` of the rows."""
    return set(rng.sample(range(n), max(2, int(n * share))))


def pick(rng, truth, alts):
    """Choose the true meaning. Called after every other random draw, so the raw values never depend on it."""
    return truth or rng.choice(alts)


# ---------- reference fixers (raw -> clean) ----------

def fix_strip_title(raw, _):
    return [str(v).strip().title() for v in raw]


def fix_mojibake(raw, _):
    out = []
    for v in raw:
        try:
            out.append(v.encode("latin-1").decode("utf-8"))
        except (UnicodeEncodeError, UnicodeDecodeError):
            out.append(v)
    return out


DATE_FORMATS = ["%Y-%m-%d", "%d %b %Y", "%b %d, %Y", "%Y/%m/%d"]


def fix_mixed_dates(raw, _):
    out = []
    for v in raw:
        for f in DATE_FORMATS:
            try:
                out.append(dt.datetime.strptime(v, f).date().isoformat())
                break
            except ValueError:
                continue
    return out


def fix_slash_dates(raw, _):
    parts = [[int(x) for x in v.split("/")] for v in raw]
    day_first = any(p[0] > 12 for p in parts)
    return [dt.date(p[2], p[1], p[0]).isoformat() if day_first else dt.date(p[2], p[0], p[1]).isoformat() for p in parts]


def fix_excel_serial(raw, _):
    return [(dt.date(1899, 12, 30) + dt.timedelta(days=int(v))).isoformat() for v in raw]


def fix_epoch(raw, _):
    return [iso_ts(v / 1000 if v > 10 ** 11 else v) for v in raw]


def fix_number_text(raw, _):
    return [float(re.sub(r"[^0-9.\-]", "", str(v))) for v in raw]


def fix_decimal_comma(raw, _):
    return [float(str(v).replace(".", "").replace(",", ".")) for v in raw]


def to_cm(v):
    v = str(v).strip()
    m = re.match(r"^(\d+)'(\d+)\"$", v)
    if m:
        return round((int(m.group(1)) * 12 + int(m.group(2))) * 2.54, 1)
    if v.endswith("in"):
        return round(float(v[:-2]) * 2.54, 1)
    if v.endswith("cm"):
        return float(v[:-2])
    x = float(v)
    return round(x * 2.54, 1) if x < 100 else x


def fix_heights(raw, _):
    return [to_cm(v) for v in raw]


def fix_zip(raw, _):
    return [str(v).zfill(5) for v in raw]


def fix_id_float(raw, _):
    return [str(v).split(".")[0] for v in raw]


def fix_range(lo, hi):
    return lambda raw, _: ["" if not (lo <= v <= hi) else v for v in raw]


MISSING_WORDS = {"n/a", "null", "none", "-", "?", "na", "unknown"}


def fix_missing_words(raw, _):
    return ["" if str(v).strip().lower() in MISSING_WORDS else v for v in raw]


def fix_sentinel_dates(raw, _):
    return ["" if v in ("9999-12-31", "1900-01-01") else v for v in raw]


def fix_variants(raw, _):
    """Group values that differ only in case, spacing and punctuation; use each group's most common spelling."""
    key = lambda v: re.sub(r"[^a-z0-9]", "", str(v).lower())
    best = {}
    for v, _n in Counter(raw).most_common():
        best.setdefault(key(v), v)
    return [best[key(v)] for v in raw]


def fix_typos(raw, _):
    counts = Counter(raw)
    canon = [v for v, n in counts.items() if n >= max(3, len(raw) * 0.08)]
    return [v if v in canon else (difflib.get_close_matches(v, canon, n=1, cutoff=0.6) or [v])[0] for v in raw]


TRUE_WORDS = {"y", "yes", "true", "1", "t"}


def fix_boolean(raw, _):
    return ["true" if str(v).strip().lower() in TRUE_WORDS else "false" for v in raw]


def fix_embedded(raw, _):
    out = []
    for v in raw:
        m = re.match(r"^(.+), (.+) \((\d{4}-\d{2}-\d{2})\)$", v)
        out.append(f"name={m.group(2)} {m.group(1)}; birth_date={m.group(3)}")
    return out


def fix_packs(raw, helpers):
    return [round(t / p) for t, p in zip(helpers["line_total"], helpers["unit_price"])]


def fix_weekday(raw, helpers):
    return [WEEKDAYS[dt.date.fromisoformat(d).weekday()] for d in helpers["visit_date"]]


def fix_percent_sign(raw, _):
    return [float(str(v).rstrip("%")) for v in raw]


# ---------- READY: controls. raw and clean are the same ----------

@case("r_identifier", READY, "A plain record identifier.", "identifier", name_free=True)
def _(rng, n, dom, truth=None):
    v = [f"{dom['prefix']}-{10000 + i}" for i in rng.sample(range(90000), n)]
    return {"name": dom["entity"] + "_id", "raw": v, "clean": list(v)}


@case("r_person_name", READY, "Names of people, cleanly written.", "person_name", name_free=True)
def _(rng, n, dom, truth=None):
    v = [rng.choice(FIRST) + " " + rng.choice(LAST) for _ in range(n)]
    return {"name": rng.choice(["contact_name", "full_name", "handled_by"]), "raw": v, "clean": list(v)}


@case("r_date_iso", READY, "Dates in year-month-day order.", "date", name_free=True)
def _(rng, n, dom, truth=None):
    v = [d.isoformat() for d in rand_dates(rng, n)]
    return {"name": rng.choice(["created_date", "opened_on", "service_date"]), "raw": v, "clean": list(v)}


@case("r_amount_named", READY, "A money amount whose name states the currency.", "money_usd", settled_by="name")
def _(rng, n, dom, truth=None):
    v = [round(rng.uniform(5, 900), 2) for _ in range(n)]
    return {"name": rng.choice(["amount_usd", "total_usd", "charge_usd"]), "raw": v, "clean": list(v)}


@case("r_category_words", READY, "A category written as consistent words.", "category", name_free=True)
def _(rng, n, dom, truth=None):
    v = [rng.choice(dom["categories"]) for _ in range(n)]
    return {"name": rng.choice(["category", "type", "channel"]), "raw": v, "clean": list(v)}


@case("r_count_named", READY, "A whole-number count with a clear name.", "count", settled_by="name")
def _(rng, n, dom, truth=None):
    v = [rng.randint(1, 40) for _ in range(n)]
    return {"name": rng.choice(["item_count", "visit_count", "line_count"]), "raw": v, "clean": list(v)}


@case("r_weekday_name", READY, "Days of the week written out.", "weekday_name", name_free=True)
def _(rng, n, dom, truth=None):
    v = [rng.choice(WEEKDAYS) for _ in range(n)]
    return {"name": rng.choice(["day", "weekday", "dow"]), "raw": v, "clean": list(v)}


@case("r_email", READY, "Email addresses.", "email", name_free=True)
def _(rng, n, dom, truth=None):
    v = [f"{rng.choice(FIRST).lower()}.{rng.choice(LAST).lower()}{rng.randint(1, 99)}@example.com" for _ in range(n)]
    return {"name": rng.choice(["email", "contact_email"]), "raw": v, "clean": list(v)}


@case("r_percent_named", READY, "A percentage from 0 to 100 with a clear name.", "percent_0_to_100", settled_by="name")
def _(rng, n, dom, truth=None):
    v = [round(rng.uniform(0, 100), 1) for _ in range(n)]
    return {"name": rng.choice(["discount_pct", "completion_pct", "fill_pct"]), "raw": v, "clean": list(v)}


@case("r_code_with_description", READY, "A code column with its description in the next column.", "status_code", settled_by="neighbours")
def _(rng, n, dom, truth=None):
    table = {"A1": "Open", "B2": "In review", "C3": "Closed", "D4": "Cancelled"}
    v = [rng.choice(list(table)) for _ in range(n)]
    return {"name": "status_cd", "raw": v, "clean": list(v), "helpers": {"status_desc": [table[c] for c in v]}}


# ---------- FIXABLE: the data itself says what to do ----------

@case("f_whitespace_case", FIXABLE, "The same value appears with stray spaces and mixed capitals.", "category", "normalise_categories", name_free=True, fix=fix_strip_title)
def _(rng, n, dom, truth=None):
    clean = [rng.choice(dom["categories"]) for _ in range(n)]
    styles = [str.upper, str.lower, lambda s: " " + s, lambda s: s + "  "]
    alter = sprinkle(rng, n, 0.4)
    raw = [rng.choice(styles)(c) if i in alter else c for i, c in enumerate(clean)]
    return {"name": rng.choice(["category", "segment", "group_name"]), "raw": raw, "clean": clean}


@case("f_mojibake", FIXABLE, "Accented letters arrive garbled because the file was read in the wrong encoding.", "person_name", "repair_encoding", name_free=True, fix=fix_mojibake)
def _(rng, n, dom, truth=None):
    clean = [rng.choice(ACCENTED) for _ in range(n)]
    bad = sprinkle(rng, n, 0.5)
    return {"name": rng.choice(["customer_name", "full_name"]), "raw": [c.encode("utf-8").decode("latin-1") if i in bad else c for i, c in enumerate(clean)], "clean": clean}


@case("f_date_mixed_formats", FIXABLE, "Dates are written several different ways in one column, each one unambiguous.", "date", "parse_date", name_free=True, fix=fix_mixed_dates)
def _(rng, n, dom, truth=None):
    dates = rand_dates(rng, n)
    return {"name": rng.choice(["received_date", "start_date"]), "raw": [d.strftime(rng.choice(DATE_FORMATS)) for d in dates], "clean": [d.isoformat() for d in dates]}


@case("f_date_slash_order", FIXABLE, "Slash dates where some row has a day above 12, which settles the order.", "date", "parse_date", settled_by="a row with a day above 12",
      alts=["day_first", "month_first"], name_free=True, fix=fix_slash_dates)
def _(rng, n, dom, truth=None):
    dates = rand_dates(rng, n)
    if not any(d.day > 12 for d in dates):
        dates[0] = dates[0].replace(day=25)
    truth = pick(rng, truth, ["day_first", "month_first"])
    fmt = "%d/%m/%Y" if truth == "day_first" else "%m/%d/%Y"
    return {"name": rng.choice(["invoice_date", "visit_date"]), "raw": [d.strftime(fmt) for d in dates], "clean": [d.isoformat() for d in dates], "truth": truth}


@case("f_excel_serial_date", FIXABLE, "Dates stored as spreadsheet day numbers.", "date", "parse_date", settled_by="name", fix=fix_excel_serial)
def _(rng, n, dom, truth=None):
    dates = rand_dates(rng, n)
    return {"name": rng.choice(["order_date", "ship_date"]), "raw": [(d - dt.date(1899, 12, 30)).days for d in dates], "clean": [d.isoformat() for d in dates]}


@case("f_epoch_seconds", FIXABLE, "Timestamps stored as seconds since 1970.", "timestamp", "parse_timestamp", name_free=True, fix=fix_epoch)
def _(rng, n, dom, truth=None):
    v = [EPOCH_BASE + rng.randrange(300 * 86400) for _ in range(n)]
    return {"name": rng.choice(["created_at", "logged_at"]), "raw": v, "clean": [iso_ts(x) for x in v]}


@case("f_epoch_millis", FIXABLE, "Timestamps stored as milliseconds since 1970.", "timestamp", "parse_timestamp", name_free=True, fix=fix_epoch)
def _(rng, n, dom, truth=None):
    v = [EPOCH_BASE + rng.randrange(300 * 86400) for _ in range(n)]
    return {"name": rng.choice(["updated_at", "event_ts"]), "raw": [x * 1000 for x in v], "clean": [iso_ts(x) for x in v]}


@case("f_number_text_separators", FIXABLE, "Numbers stored as text with thousands separators.", "number", "parse_number", name_free=True, fix=fix_number_text)
def _(rng, n, dom, truth=None):
    v = [round(rng.uniform(1000, 250000), 2) for _ in range(n)]
    return {"name": rng.choice(["balance_usd", "revenue_usd"]), "raw": [f"{x:,.2f}" for x in v], "clean": v}


@case("f_decimal_comma", FIXABLE, "Numbers written with a comma for the decimal point and a full stop for thousands.", "number", "parse_number", name_free=True, fix=fix_decimal_comma)
def _(rng, n, dom, truth=None):
    v = [round(rng.uniform(1000, 250000), 2) for _ in range(n)]
    return {"name": rng.choice(["betrag_eur", "montant_eur"]), "raw": [f"{x:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".") for x in v], "clean": v}


@case("f_currency_symbol", FIXABLE, "Money stored as text with a dollar sign and separators.", "money_usd", "parse_number", fix=fix_number_text)
def _(rng, n, dom, truth=None):
    v = [round(rng.uniform(5, 9000), 2) for _ in range(n)]
    return {"name": rng.choice(["price", "amount_paid"]), "raw": [f"US${x:,.2f}" for x in v], "clean": v}


@case("f_percent_sign", FIXABLE, "Percentages stored as text with a percent sign.", "percent_0_to_100", "parse_number", name_free=True, fix=fix_percent_sign)
def _(rng, n, dom, truth=None):
    v = [round(rng.uniform(0, 100), 1) for _ in range(n)]
    return {"name": rng.choice(["margin", "share"]), "raw": [f"{x}%" for x in v], "clean": v}


@case("f_units_written", FIXABLE, "Heights written three ways, each stating its unit.", "height_cm", "convert_unit", name_free=True, fix=fix_heights)
def _(rng, n, dom, truth=None):
    inches = [rng.randint(58, 78) for _ in range(n)]
    clean = [round(i * 2.54, 1) for i in inches]
    forms = [lambda i, c: f"{c} cm", lambda i, c: f"{i} in", lambda i, c: f"{i // 12}'{i % 12}\""]
    return {"name": "height", "raw": [rng.choice(forms)(i, c) for i, c in zip(inches, clean)], "clean": clean}


@case("f_units_mixed_separable", FIXABLE, "Heights in inches and centimetres mixed, with no unit shown, but the two ranges cannot overlap.", "height_cm", "convert_unit", settled_by="name and values", fix=fix_heights)
def _(rng, n, dom, truth=None):
    inches = [rng.randint(58, 78) for _ in range(n)]
    clean = [round(i * 2.54, 1) for i in inches]
    as_inches = sprinkle(rng, n, 0.4)
    return {"name": "height", "raw": [inches[i] if i in as_inches else clean[i] for i in range(n)], "clean": clean}


@case("f_leading_zero_lost", FIXABLE, "Postal codes stored as numbers, so leading zeros are gone.", "postal_code", "keep_as_text", settled_by="name", fix=fix_zip)
def _(rng, n, dom, truth=None):
    clean = [rng.choice(ZIPS) for _ in range(n)]
    return {"name": rng.choice(["zip", "postal_code"]), "raw": [int(z) for z in clean], "clean": clean}


@case("f_id_as_float", FIXABLE, "Identifiers that picked up a decimal point on the way in.", "identifier", "keep_as_text", settled_by="name", fix=fix_id_float)
def _(rng, n, dom, truth=None):
    clean = [str(100000 + i) for i in rng.sample(range(800000), n)]
    return {"name": rng.choice(["account_id", "ticket_id"]), "raw": [c + ".0" for c in clean], "clean": clean}


@case("f_sentinel_number", FIXABLE, "A score from 0 to 100 where an impossible number stands in for missing.", "score_0_to_100", "replace_missing_marker", settled_by="name and values", fix=fix_range(0, 100))
def _(rng, n, dom, truth=None):
    clean = [rng.randint(0, 100) for _ in range(n)]
    marker = rng.choice([-1, 999, -999])
    for i in sprinkle(rng, n, 0.15):
        clean[i] = ""
    return {"name": rng.choice(["quality_score", "satisfaction_score"]), "raw": [marker if c == "" else c for c in clean], "clean": clean}


@case("f_sentinel_text", FIXABLE, "Words such as N/A and NULL stand in for missing.", "category", "replace_missing_marker", name_free=True, fix=fix_missing_words)
def _(rng, n, dom, truth=None):
    clean = [rng.choice(dom["categories"]) for _ in range(n)]
    raw = list(clean)
    for i in sprinkle(rng, n, 0.2):
        clean[i] = ""
        raw[i] = rng.choice(["N/A", "NULL", "none", "-", "?"])
    return {"name": rng.choice(["referral_source", "reason"]), "raw": raw, "clean": clean}


@case("f_sentinel_date", FIXABLE, "A far-future or far-past date stands in for no date.", "date", "replace_missing_marker", name_free=True, fix=fix_sentinel_dates)
def _(rng, n, dom, truth=None):
    clean = [d.isoformat() for d in rand_dates(rng, n)]
    marker = rng.choice(["9999-12-31", "1900-01-01"])
    raw = list(clean)
    for i in sprinkle(rng, n, 0.3):
        clean[i] = ""
        raw[i] = marker
    return {"name": rng.choice(["end_date", "closed_date"]), "raw": raw, "clean": clean}


@case("f_category_variants", FIXABLE, "One category spelled with different punctuation and capitals.", "category", "normalise_categories", name_free=True, fix=fix_variants)
def _(rng, n, dom, truth=None):
    canon = ["Bank Transfer", "Credit Card", "Direct Debit", "Gift Voucher"]
    clean = [rng.choice(canon) for _ in range(n)]
    styles = [str.upper, str.lower, lambda s: s.replace(" ", "-"), lambda s: s + ".", lambda s: s.replace(" ", "  ")]
    alter = sprinkle(rng, n, 0.3)
    return {"name": rng.choice(["payment_method", "pay_type"]), "raw": [rng.choice(styles)(c) if i in alter else c for i, c in enumerate(clean)], "clean": clean}


@case("f_category_typos", FIXABLE, "A few values are one keystroke away from a common value.", "category", "normalise_categories", name_free=True, fix=fix_typos)
def _(rng, n, dom, truth=None):
    canon = ["Residential", "Commercial", "Industrial", "Government"]
    clean = [rng.choice(canon) for _ in range(n)]
    raw = list(clean)
    for i in sprinkle(rng, n, 0.08):
        s, k = clean[i], rng.randrange(2, 8)
        raw[i] = s[:k] + s[k + 1:] if rng.random() < 0.5 else s[:k] + s[k + 1] + s[k] + s[k + 2:]
    return {"name": rng.choice(["customer_class", "site_type"]), "raw": raw, "clean": clean}


@case("f_boolean_variants", FIXABLE, "Yes and no written many ways.", "yes_no_flag", "normalise_categories", name_free=True, fix=fix_boolean)
def _(rng, n, dom, truth=None):
    truthy = [rng.random() < 0.5 for _ in range(n)]
    yes, no = ["Y", "yes", "TRUE", "1", "Yes"], ["N", "no", "FALSE", "0", "No"]
    return {"name": rng.choice(["is_active", "opted_in"]), "raw": [rng.choice(yes if t else no) for t in truthy], "clean": ["true" if t else "false" for t in truthy]}


@case("f_embedded_values", FIXABLE, "Several facts packed into one cell in a regular pattern.", "person_name_and_birth_date", "split_values", name_free=True, fix=fix_embedded)
def _(rng, n, dom, truth=None):
    people = [(rng.choice(FIRST), rng.choice(LAST), d.isoformat()) for d in rand_dates(rng, n, 1950, 2004)]
    return {"name": rng.choice(["person", "member"]), "raw": [f"{l}, {f} ({b})" for f, l, b in people], "clean": [f"name={f} {l}; birth_date={b}" for f, l, b in people]}


@case("f_outlier_impossible", FIXABLE, "A few ages that no person can have.", "age_years", "remove_impossible_values", settled_by="name and values", fix=fix_range(0, 120))
def _(rng, n, dom, truth=None):
    clean = [rng.randint(18, 90) for _ in range(n)]
    raw = list(clean)
    for i in sprinkle(rng, n, 0.04):
        clean[i] = ""
        raw[i] = rng.choice([240, -3, 999, 1987])
    return {"name": "age", "raw": raw, "clean": clean}


@case("f_quantity_packs_with_total", FIXABLE, "Quantity is counted in six-packs; the unit price and line total beside it show that.", "quantity_units", "convert_unit", settled_by="neighbours", fix=fix_packs)
def _(rng, n, dom, truth=None):
    packs = [rng.randint(1, 6) for _ in range(n)]
    price = [round(rng.uniform(2, 40), 2) for _ in range(n)]
    units = [p * 6 for p in packs]
    return {"name": "qty", "raw": packs, "clean": units, "helpers": {"unit_price": price, "line_total": [round(u * p, 2) for u, p in zip(units, price)]}}


@case("f_weekday_number_with_date", FIXABLE, "A weekday number whose convention can be worked out from the date beside it.", "weekday_name", "decode_values", settled_by="neighbours",
      alts=["monday_is_1", "sunday_is_1"], fix=fix_weekday)
def _(rng, n, dom, truth=None):
    dates = rand_dates(rng, n, 2026, 2026)
    truth = pick(rng, truth, ["monday_is_1", "sunday_is_1"])
    w = [d.isoweekday() for d in dates]
    return {"name": "visit_dow", "raw": [x if truth == "monday_is_1" else x % 7 + 1 for x in w], "clean": [WEEKDAYS[x - 1] for x in w],
            "helpers": {"visit_date": [d.isoformat() for d in dates]}, "truth": truth}


# ---------- NEEDS_CONTEXT: the values cannot settle it ----------

@case("n_date_slash_unresolvable", NEEDS_CONTEXT, "Slash dates where every day and month is 12 or below.", "date", "parse_date", settled_by="nothing", alts=["day_first", "month_first"])
def _(rng, n, dom, truth=None):
    pairs = [(rng.randint(1, 12), rng.randint(1, 12), rng.randint(2021, 2026)) for _ in range(n)]
    truth = pick(rng, truth, ["day_first", "month_first"])
    clean = [dt.date(y, b, a).isoformat() if truth == "day_first" else dt.date(y, a, b).isoformat() for a, b, y in pairs]
    return {"name": rng.choice(["due_date", "posted_date"]), "raw": [f"{a:02d}/{b:02d}/{y}" for a, b, y in pairs], "clean": clean, "truth": truth}


@case("n_currency_unknown", NEEDS_CONTEXT, "A money amount with nothing to say which currency.", "money", settled_by="nothing", alts=["usd", "cad"])
def _(rng, n, dom, truth=None):
    v = [round(rng.uniform(5, 900), 2) for _ in range(n)]
    return {"name": rng.choice(["amount", "price", "total"]), "raw": v, "clean": list(v), "truth": pick(rng, truth, ["usd", "cad"])}


@case("n_amount_cents_or_dollars", NEEDS_CONTEXT, "Whole numbers that could be dollars or cents.", "money", "scale_number", settled_by="nothing", alts=["dollars", "cents"])
def _(rng, n, dom, truth=None):
    v = [rng.randint(500, 9000) for _ in range(n)]
    truth = pick(rng, truth, ["dollars", "cents"])
    return {"name": rng.choice(["amount", "fee", "charge"]), "raw": v, "clean": [x / 100 if truth == "cents" else x for x in v], "truth": truth}


@case("n_amount_period", NEEDS_CONTEXT, "A pay figure that could be per month or per year.", "pay", "scale_number", settled_by="nothing", alts=["annual", "monthly"])
def _(rng, n, dom, truth=None):
    v = [rng.randint(2500, 9500) for _ in range(n)]
    truth = pick(rng, truth, ["annual", "monthly"])
    return {"name": rng.choice(["pay", "rate", "stipend"]), "raw": v, "clean": [x * 12 if truth == "monthly" else x for x in v], "truth": truth}


@case("n_unit_unknown", NEEDS_CONTEXT, "A weight that could be pounds or kilograms.", "weight", "convert_unit", settled_by="nothing", alts=["kilograms", "pounds"])
def _(rng, n, dom, truth=None):
    v = [round(rng.uniform(1, 50), 1) for _ in range(n)]
    truth = pick(rng, truth, ["kilograms", "pounds"])
    return {"name": rng.choice(["weight", "parcel_weight"]), "raw": v, "clean": [round(x * 0.4536, 2) if truth == "pounds" else x for x in v], "truth": truth}


@case("n_flag_1_2", NEEDS_CONTEXT, "A flag holding 1 and 2 with nothing to say which means yes.", "yes_no_flag", "decode_values", settled_by="nothing", alts=["1_is_yes", "2_is_yes"])
def _(rng, n, dom, truth=None):
    v = [rng.choice([1, 2]) for _ in range(n)]
    truth = pick(rng, truth, ["1_is_yes", "2_is_yes"])
    yes = 1 if truth == "1_is_yes" else 2
    return {"name": rng.choice(["consent", "renewal", "priority"]), "raw": v, "clean": ["true" if x == yes else "false" for x in v], "truth": truth}


@case("n_zero_missing_or_real", NEEDS_CONTEXT, "Many zeros that could mean none or could mean not recorded.", "count", "replace_missing_marker", settled_by="nothing",
      alts=["zero_is_real", "zero_is_missing"])
def _(rng, n, dom, truth=None):
    v = [0 if rng.random() < 0.35 else rng.randint(1, 12) for _ in range(n)]
    truth = pick(rng, truth, ["zero_is_real", "zero_is_missing"])
    return {"name": rng.choice(["complaints", "returns", "late_days"]), "raw": v, "clean": ["" if x == 0 and truth == "zero_is_missing" else x for x in v], "truth": truth}


@case("n_state_or_country", NEEDS_CONTEXT, "Two-letter codes that are valid both as US states and as countries.", "place_code", "decode_values", settled_by="nothing", alts=["us_state", "country"])
def _(rng, n, dom, truth=None):
    v = [rng.choice(BOTH_STATE_AND_COUNTRY) for _ in range(n)]
    return {"name": rng.choice(["region", "origin", "loc"]), "raw": v, "clean": list(v), "truth": pick(rng, truth, ["us_state", "country"])}


@case("n_timestamp_zone", NEEDS_CONTEXT, "Date and time with no time zone.", "timestamp", "parse_timestamp", settled_by="nothing", alts=["utc", "local_utc_minus_6"])
def _(rng, n, dom, truth=None):
    secs = [EPOCH_BASE + rng.randrange(300 * 86400) for _ in range(n)]
    truth = pick(rng, truth, ["utc", "local_utc_minus_6"])
    shown = [dt.datetime.fromtimestamp(s, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S") for s in secs]
    return {"name": rng.choice(["recorded_at", "checked_in"]), "raw": shown, "clean": [iso_ts(s + (21600 if truth == "local_utc_minus_6" else 0)) for s in secs], "truth": truth}


@case("n_weekday_number_alone", NEEDS_CONTEXT, "A weekday number with no date beside it to show which day is 1.", "weekday_name", "decode_values", settled_by="nothing",
      alts=["monday_is_1", "sunday_is_1"])
def _(rng, n, dom, truth=None):
    v = [rng.randint(1, 7) for _ in range(n)]
    truth = pick(rng, truth, ["monday_is_1", "sunday_is_1"])
    return {"name": rng.choice(["dow", "weekday_no"]), "raw": v, "clean": [WEEKDAYS[x - 1] if truth == "monday_is_1" else WEEKDAYS[(x - 2) % 7] for x in v], "truth": truth}


@case("n_quantity_alone", NEEDS_CONTEXT, "A quantity with nothing to say whether it counts units or packs.", "quantity", "convert_unit", settled_by="nothing", alts=["units", "packs_of_6"])
def _(rng, n, dom, truth=None):
    v = [rng.randint(1, 6) for _ in range(n)]
    truth = pick(rng, truth, ["units", "packs_of_6"])
    return {"name": rng.choice(["qty", "quantity"]), "raw": v, "clean": [x * 6 if truth == "packs_of_6" else x for x in v], "truth": truth}


@case("n_opaque_codes", NEEDS_CONTEXT, "Short codes with no description anywhere in the table.", "code", "decode_values", settled_by="nothing")
def _(rng, n, dom, truth=None):
    v = [rng.choice(["K1", "K2", "R7", "Z9", "Q4"]) for _ in range(n)]
    return {"name": rng.choice(["rsn_cd", "typ", "cls"]), "raw": v, "clean": list(v)}


@case("n_cryptic_number", NEEDS_CONTEXT, "Plausible numbers under a name that says nothing.", "unknown_measure", settled_by="nothing")
def _(rng, n, dom, truth=None):
    v = [rng.randint(58, 76) for _ in range(n)]
    return {"name": rng.choice(["v3", "x7", "fld_12"]), "raw": v, "clean": list(v)}


# ---------- GARBAGE: nothing recovers it ----------

@case("g_mostly_missing", GARBAGE, "Nearly every row is blank.", "unknown", name_free=True)
def _(rng, n, dom, truth=None):
    keep = set(rng.sample(range(n), max(1, n // 25)))
    v = [rng.choice(dom["categories"]) if i in keep else "" for i in range(n)]
    return {"name": rng.choice(["notes_2", "legacy_flag", "alt_code"]), "raw": v, "clean": list(v)}


@case("g_constant", GARBAGE, "Every row holds the same value.", "unknown", name_free=True)
def _(rng, n, dom, truth=None):
    v = [rng.choice(["1", "X", "DEFAULT", "0"])] * n
    return {"name": rng.choice(["src", "batch_flag", "ver"]), "raw": v, "clean": list(v)}


@case("g_random_noise", GARBAGE, "Random strings under a name that says nothing.", "unknown")
def _(rng, n, dom, truth=None):
    v = ["".join(rng.choice("abcdef0123456789") for _ in range(12)) for _ in range(n)]
    return {"name": rng.choice(["tmp1", "col_x", "zz"]), "raw": v, "clean": list(v)}


@case("g_truncated", GARBAGE, "Text cut off at a fixed length, so the rest is lost.", "email")
def _(rng, n, dom, truth=None):
    v = [f"{rng.choice(FIRST).lower()}.{rng.choice(LAST).lower()}@example.com"[:10] for _ in range(n)]
    return {"name": rng.choice(["email", "contact"]), "raw": v, "clean": list(v)}


@case("g_wrong_values_mixed_in", GARBAGE, "A money column where many rows hold dates, names or codes instead.", "money")
def _(rng, n, dom, truth=None):
    v = [round(rng.uniform(5, 900), 2) for _ in range(n)]
    for i in sprinkle(rng, n, 0.4):
        v[i] = rng.choice([rand_dates(rng, 1)[0].isoformat(), rng.choice(LAST), rng.choice(dom["categories"]), "#REF!"])
    return {"name": rng.choice(["amount", "total"]), "raw": v, "clean": list(v)}


@case("g_placeholder_text", GARBAGE, "Most rows hold filler such as test, asdf or TBD.", "unknown")
def _(rng, n, dom, truth=None):
    v = [rng.choice(["test", "asdf", "xxx", "TBD", "todo", "."]) if rng.random() < 0.7 else rng.choice(dom["categories"]) for _ in range(n)]
    return {"name": rng.choice(["description", "comment", "detail"]), "raw": v, "clean": list(v)}


DOMAINS = {
    "retail": {"entity": "order", "prefix": "ORD", "categories": ["Online", "Store", "Phone", "Marketplace"]},
    "clinic": {"entity": "visit", "prefix": "VIS", "categories": ["Routine", "Urgent", "Follow Up", "Referral"]},
    "logistics": {"entity": "shipment", "prefix": "SHP", "categories": ["Road", "Rail", "Air", "Sea"]},
    "banking": {"entity": "account", "prefix": "ACC", "categories": ["Personal", "Business", "Joint", "Trust"]},
    "hotel": {"entity": "booking", "prefix": "BKG", "categories": ["Leisure", "Corporate", "Group", "Event"]},
    "utilities": {"entity": "meter", "prefix": "MTR", "categories": ["Electric", "Gas", "Water", "Solar"]},
}


# ---------- cross-column cases: the evidence, or the conflict, is in another column ----------

ZIP_STATE = [("02134", "MA"), ("07030", "NJ"), ("10001", "NY"), ("60614", "IL"), ("94110", "CA"), ("30301", "GA"), ("73301", "TX"), ("80202", "CO")]


def fix_recompute_total(raw, helpers):
    return [round(q * p, 2) for q, p in zip(helpers["qty"], helpers["unit_price"])]


def fix_weight_by_unit(raw, helpers):
    return [round(v * 0.4536, 2) if u == "lb" else v for v, u in zip(raw, helpers["weight_unit"])]


@case("x_amount_with_currency_column", READY, "Amounts in several currencies, with the currency named in the next column.", "money", settled_by="neighbours")
def _(rng, n, dom, truth=None):
    v = [round(rng.uniform(5, 900), 2) for _ in range(n)]
    return {"name": "amount", "raw": v, "clean": list(v), "helpers": {"currency": [rng.choice(["USD", "EUR", "GBP"]) for _ in range(n)]}}


@case("x_weight_with_unit_column", FIXABLE, "Weights in pounds and kilograms mixed, with the unit named in the next column.", "weight_kg", "convert_unit", settled_by="neighbours",
      fix=fix_weight_by_unit)
def _(rng, n, dom, truth=None):
    v = [round(rng.uniform(1, 50), 1) for _ in range(n)]
    unit = [rng.choice(["kg", "lb"]) for _ in range(n)]
    return {"name": "weight", "raw": v, "clean": [round(x * 0.4536, 2) if u == "lb" else x for x, u in zip(v, unit)], "helpers": {"weight_unit": unit}}


@case("x_total_recomputable", FIXABLE, "A line total that disagrees with quantity times unit price in some rows.", "money", "recompute_derived", settled_by="neighbours",
      fix=fix_recompute_total)
def _(rng, n, dom, truth=None):
    qty = [rng.randint(1, 12) for _ in range(n)]
    price = [round(rng.uniform(2, 40), 2) for _ in range(n)]
    clean = [round(q * p, 2) for q, p in zip(qty, price)]
    raw = list(clean)
    for i in sprinkle(rng, n, 0.06):
        raw[i] = round(clean[i] * rng.choice([10, 0.1, 2]) + rng.choice([0, 1]), 2)
    return {"name": "line_total_usd", "raw": raw, "clean": clean, "helpers": {"qty": qty, "unit_price": price}}


@case("x_end_before_start", NEEDS_CONTEXT, "Some rows end before they start, and nothing says which date is wrong.", "date", settled_by="nothing")
def _(rng, n, dom, truth=None):
    start = rand_dates(rng, n, 2024, 2025)
    end = [s + dt.timedelta(days=rng.randint(1, 90)) for s in start]
    for i in sprinkle(rng, n, 0.08):
        end[i] = start[i] - dt.timedelta(days=rng.randint(5, 300))
    v = [d.isoformat() for d in end]
    return {"name": "end_date", "raw": v, "clean": list(v), "helpers": {"start_date": [d.isoformat() for d in start]}}


@case("x_state_zip_conflict", NEEDS_CONTEXT, "Some rows have a state that does not match the postal code, and nothing says which is wrong.", "us_state", settled_by="nothing")
def _(rng, n, dom, truth=None):
    pairs = [rng.choice(ZIP_STATE) for _ in range(n)]
    state = [s for _, s in pairs]
    for i in sprinkle(rng, n, 0.08):
        state[i] = rng.choice([s for _, s in ZIP_STATE if s != pairs[i][1]])
    return {"name": "state", "raw": state, "clean": list(state), "helpers": {"zip": [z for z, _ in pairs]}}


@case("x_code_description_conflict", NEEDS_CONTEXT, "The same code carries different descriptions in different rows.", "status_code", "decode_values", settled_by="nothing")
def _(rng, n, dom, truth=None):
    table = {"A1": "Open", "B2": "In review", "C3": "Closed", "D4": "Cancelled"}
    v = [rng.choice(list(table)) for _ in range(n)]
    desc = [table[c] for c in v]
    for i in sprinkle(rng, n, 0.1):
        desc[i] = rng.choice([d for d in table.values() if d != table[v[i]]])
    return {"name": "status_cd", "raw": v, "clean": list(v), "helpers": {"status_desc": desc}}
