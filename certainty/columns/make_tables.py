"""Generate small tables whose columns run from obvious to unknowable.

    python make_tables.py --instances 4 --out data

Every table is written twice: `raw` is how the data arrives, `clean` is the
same rows after correct preparation. `key.json` says what each column truly
is, what would settle that, and what preparation it needs.

Some columns are built so that two meanings fit the values equally well, and
the true one is chosen by a seeded coin flip for each instance. For those
columns nobody, person or model, can do better than chance from the values
alone, so a stated certainty above 1 in 2 is provably too high.

Everything here is invented. Only the standard library is used.
"""
import argparse
import csv
import datetime as dt
import json
import random
from pathlib import Path

# What a column can be. The model picks one of these.
MEANINGS = {
    "identifier": "Identifier of a record",
    "person_name": "Person's name",
    "product_name": "Product name",
    "category_name": "Category or type, written as a word",
    "city": "City",
    "us_state": "US state (code or name)",
    "country_code": "Country code",
    "postal_code": "Postal code",
    "currency_code": "Currency code",
    "date_iso": "Calendar date, year-month-day",
    "date_day_first": "Calendar date, day first (day/month/year)",
    "date_month_first": "Calendar date, month first (month/day/year)",
    "timestamp_epoch_seconds": "Timestamp, seconds since 1970",
    "timestamp_epoch_millis": "Timestamp, milliseconds since 1970",
    "weekday_name": "Day of the week, as a name",
    "weekday_number_mon1": "Day of the week as a number, Monday = 1",
    "weekday_number_sun1": "Day of the week as a number, Sunday = 1",
    "day_of_month": "Day of the month",
    "day_of_year": "Day of the year",
    "age_years": "Age in years",
    "height_inches": "Height in inches",
    "height_cm": "Height in centimetres",
    "height_feet_inches_text": "Height written as feet and inches",
    "weight_pounds": "Weight in pounds",
    "weight_kg": "Weight in kilograms",
    "waist_inches": "Waist in inches",
    "eye_colour": "Eye colour",
    "hair_colour": "Hair colour",
    "gender_code": "Gender or sex code",
    "marital_status_code": "Marital status code",
    "clothing_size_code": "Clothing size code",
    "flag_text_yes_no": "Yes/no flag written as letters",
    "flag_1_yes": "Yes/no flag where 1 means yes and 2 means no",
    "flag_2_yes": "Yes/no flag where 2 means yes and 1 means no",
    "quantity_units": "Quantity counted in single units",
    "quantity_packs": "Quantity counted in packs of several units",
    "volume_fl_oz": "Volume in fluid ounces",
    "volume_ml": "Volume in millilitres",
    "money_usd": "Money amount in US dollars",
    "money_cad": "Money amount in Canadian dollars",
    "money_usd_cents": "Money amount in US cents",
    "percent_0_to_1": "Share written from 0 to 1",
    "percent_0_to_100": "Percentage written from 0 to 100",
    "rating_score": "Rating or score",
    "status_code": "Status code",
    "duration_minutes": "Duration in minutes",
    "duration_seconds": "Duration in seconds",
    "other": "Something not on this list",
}

# What has to be done to a column before it can be used.
OPS = {
    "parse_date": "Turn date text into a date",
    "parse_timestamp": "Turn a number into a date and time",
    "decode_values": "Look up what each code means",
    "keep_as_text": "Store as text so leading zeros survive",
    "parse_compound_measure": "Split a written measure such as 5'8\" and convert it to one number",
    "scale_number": "Multiply or divide to reach the standard scale, such as cents to dollars",
    "replace_missing_marker": "Replace a stand-in value such as -1 with a true blank",
    "normalise_categories": "Bring spelling, case and spacing variants to one value",
}

# What would settle a column's meaning.
SETTLED_BY = {
    "values": "the values themselves",
    "name": "a clear column name",
    "neighbours": "the other columns in the table",
    "name_or_neighbours": "a clear column name or the other columns",
    "day_gt_12": "a row where the day is above 12",
    "nothing": "nothing in the table; it needs a data dictionary or the owner",
    "judgement": "a judgement call; the evidence makes one reading likely, not certain",
}

FIRST = ["Ana", "Ben", "Chloe", "Dev", "Elif", "Farid", "Grace", "Hiro", "Ines", "Jon", "Kemi", "Luca", "Mona", "Noor", "Omar", "Priya"]
LAST = ["Abel", "Brandt", "Castro", "Dunne", "Eze", "Farrow", "Gallo", "Haas", "Ito", "Jensen", "Koval", "Lindqvist", "Moreau", "Nwosu", "Ortiz", "Petrov"]
PLACES = [("02134", "Boston", "MA"), ("07030", "Hoboken", "NJ"), ("10001", "New York", "NY"), ("60614", "Chicago", "IL"),
          ("94110", "San Francisco", "CA"), ("00501", "Holtsville", "NY"), ("30301", "Atlanta", "GA"), ("73301", "Austin", "TX"),
          ("06510", "New Haven", "CT"), ("80202", "Denver", "CO")]
PRODUCTS = [("Trail Bottle", "Hydration"), ("Grip Socks", "Apparel"), ("Recovery Band", "Equipment"), ("Studio Towel", "Accessories"),
            ("Protein Shake", "Nutrition"), ("Foam Roller", "Equipment"), ("Training Tee", "Apparel"), ("Electrolyte Mix", "Nutrition")]
STATE_VARIANTS = {"Texas": ["TX", "tx", " TX", "Texas", "texas "], "Ohio": ["OH", "oh", "Ohio", " OH "], "Georgia": ["GA", "Ga", "Georgia", "ga"],
                  "Colorado": ["CO", "co", "Colorado", " Co"], "Oregon": ["OR", "or", "Oregon", "OR "]}
# Two-letter codes that are both a US state and a country.
BOTH_STATE_AND_COUNTRY = ["AL", "AR", "CA", "CO", "DE", "GA", "ID", "IL", "IN", "LA", "MA", "MD", "ME", "MN", "MO", "MT", "NC", "NE", "PA", "SC", "SD", "TN", "VA"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def col(name, truth, settled_by, ops=(), candidates=None):
    return {"name": name, "truth": truth, "candidates": list(candidates or [truth]), "settled_by": settled_by, "ops": list(ops)}


def iso(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build(instance, rows=200, seed=20261112):
    """One instance: {table: {"columns": [...], "raw": [[...]], "clean": [[...]]}} and the coin flips made."""
    rng = random.Random(f"{seed}-{instance}")
    flips = {}

    def flip(key, options):
        flips[key] = rng.choice(options)
        return flips[key]

    def rand_date(y0, y1):
        start = dt.date(y0, 1, 1)
        return start + dt.timedelta(days=rng.randrange((dt.date(y1, 12, 31) - start).days + 1))

    tables = {}

    # ---- members ----
    joined_as = flip("members.joined", ["date_day_first", "date_month_first"])
    news_as = flip("members.newsletter", ["flag_1_yes", "flag_2_yes"])
    cols = [
        col("member_id", "identifier", "values"),
        col("full_name", "person_name", "values"),
        col("birth_date", "date_iso", "values", ["parse_date"]),
        col("sex", "gender_code", "name", ["decode_values"]),
        col("marital", "marital_status_code", "name", ["decode_values"]),
        col("height", "height_feet_inches_text", "values", ["parse_compound_measure"]),
        col("joined", joined_as, "day_gt_12", ["parse_date"], ["date_day_first", "date_month_first"]),
        col("newsletter", news_as, "nothing", ["decode_values"], ["flag_1_yes", "flag_2_yes"]),
        col("zip", "postal_code", "name_or_neighbours", ["keep_as_text"]),
        col("city", "city", "values"),
        col("state", "us_state", "name_or_neighbours"),
    ]
    raw, clean, member_ids = [], [], []
    for i in range(rows):
        mid = f"M-{10000 + i}"
        member_ids.append(mid)
        name = rng.choice(FIRST) + " " + rng.choice(LAST)
        birth = rand_date(1950, 2005)
        sex = rng.choices(["M", "F", "U", "X"], [46, 46, 5, 3])[0]
        marital = rng.choice(["S", "M", "D", "W"])
        inches = rng.randint(58, 76)
        joined = rand_date(2016, 2026)
        wants = rng.random() < 0.5
        zip_code, city, state = rng.choice(PLACES)
        news = (1 if wants else 2) if news_as == "flag_1_yes" else (2 if wants else 1)
        raw.append([mid, name, birth.isoformat(), sex, marital, f"{inches // 12}'{inches % 12}\"",
                    joined.strftime("%d/%m/%Y" if joined_as == "date_day_first" else "%m/%d/%Y"), news, zip_code, city, state])
        clean.append([mid, name, birth.isoformat(), {"M": "Male", "F": "Female", "U": "Unknown", "X": "Another gender"}[sex],
                      {"S": "Single", "M": "Married", "D": "Divorced", "W": "Widowed"}[marital], round(inches * 2.54, 1),
                      joined.isoformat(), "yes" if wants else "no", zip_code, city, state])
    tables["members"] = {"columns": cols, "raw": raw, "clean": clean}

    # ---- health_screening ----
    dow_as = flip("health_screening.visit_dow", ["weekday_number_mon1", "weekday_number_sun1"])
    cols = [
        col("person_ref", "identifier", "values"),
        col("eye", "eye_colour", "values"),
        col("hair", "hair_colour", "values"),
        col("weight", "weight_pounds", "name"),
        col("v3", "height_inches", "judgement"),   # a name that says nothing, beside body measurements
        col("age", "age_years", "name"),
        col("waist", "waist_inches", "name"),
        col("visit_date", "date_iso", "values", ["parse_date"]),
        col("visit_dow", dow_as, "neighbours", [], ["weekday_number_mon1", "weekday_number_sun1"]),
    ]
    raw, clean = [], []
    for _ in range(rows):
        visit = rand_date(2026, 2026)
        w = visit.isoweekday()  # Monday = 1
        r = [rng.choice(member_ids), rng.choice(["brown", "blue", "green", "hazel", "grey"]), rng.choice(["black", "brown", "blond", "red", "grey"]),
             rng.randint(105, 260), rng.randint(58, 76), rng.randint(18, 80), rng.randint(26, 46), visit.isoformat(),
             w if dow_as == "weekday_number_mon1" else w % 7 + 1]
        raw.append(r)
        clean.append(r[:8] + [WEEKDAYS[w - 1]])
    tables["health_screening"] = {"columns": cols, "raw": raw, "clean": clean}

    # ---- products ----
    vol_as = flip("products.volume", ["volume_fl_oz", "volume_ml"])
    price_as = flip("products.price", ["money_usd", "money_cad"])
    cols = [
        col("sku", "identifier", "values"),
        col("product_name", "product_name", "values"),
        col("category", "category_name", "values"),
        col("size", "clothing_size_code", "values"),
        col("volume", vol_as, "name", [], ["volume_fl_oz", "volume_ml"]),
        col("price", price_as, "nothing", [], ["money_usd", "money_cad"]),
        col("price_cents", "money_usd_cents", "name", ["scale_number"]),
        col("discount", "percent_0_to_1", "name"),
        col("rating", "rating_score", "name"),
        col("in_stock", "flag_text_yes_no", "values", ["decode_values"]),
    ]
    raw, clean = [], []
    for i in range(rows):
        pname, cat = rng.choice(PRODUCTS)
        vol = rng.choice([8, 12, 16, 20, 24, 32] if vol_as == "volume_fl_oz" else [250, 330, 355, 500, 750, 1000])
        price = round(rng.uniform(2, 80), 2)
        cents = rng.randint(199, 7999)
        stock = rng.random() < 0.8
        r = [f"SKU-{4000 + i}", pname, cat, rng.choice(["S", "M", "L", "XL"]), vol, price, cents, rng.choice([0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.4]),
             rng.randint(1, 5), "Y" if stock else "N"]
        raw.append(r)
        clean.append(r[:6] + [round(cents / 100, 2)] + r[7:9] + ["yes" if stock else "no"])
    tables["products"] = {"columns": cols, "raw": raw, "clean": clean}

    # ---- order_lines ----
    qty_as = flip("order_lines.qty", ["quantity_units", "quantity_packs"])
    cols = [
        col("order_id", "identifier", "values"),
        col("member_id", "identifier", "values"),
        col("ordered_at", "timestamp_epoch_seconds", "values", ["parse_timestamp"]),
        col("shipped_ms", "timestamp_epoch_millis", "values", ["parse_timestamp"]),
        col("qty", qty_as, "neighbours", [], ["quantity_units", "quantity_packs"]),   # line_total = qty x unit_price, or qty x 6 x unit_price
        col("unit_price", "money_usd", "neighbours"),                                  # the currency column says which
        col("currency", "currency_code", "values"),
        col("line_total", "money_usd", "neighbours"),
        col("status", "status_code", "name", ["decode_values"]),
        col("dow", "weekday_name", "values"),
        col("day", "day_of_month", "judgement"),
    ]
    raw, clean = [], []
    base = int(dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc).timestamp())
    for i in range(rows):
        ordered = base + rng.randrange(300 * 86400)
        shipped = ordered + rng.randint(1, 5) * 86400 + rng.randrange(86400)
        qty = rng.randint(1, 6)
        unit = round(rng.uniform(2, 40), 2)
        units = qty if qty_as == "quantity_units" else qty * 6
        when = dt.datetime.fromtimestamp(ordered, dt.timezone.utc)
        status = rng.randint(1, 4)
        raw.append([f"O-{70000 + i}", rng.choice(member_ids), ordered, shipped * 1000, qty, unit, "USD", round(units * unit, 2), status,
                    WEEKDAYS[when.weekday()], when.day])
        clean.append([f"O-{70000 + i}", raw[-1][1], iso(ordered), iso(shipped), units, unit, "USD", round(units * unit, 2),
                      {1: "placed", 2: "packed", 3: "shipped", 4: "returned"}[status], WEEKDAYS[when.weekday()], when.day])
    tables["order_lines"] = {"columns": cols, "raw": raw, "clean": clean}

    # ---- payments ----
    amount_as = flip("payments.amount", ["money_usd", "money_cad"])
    paid_as = flip("payments.paid_on", ["date_day_first", "date_month_first"])
    region_as = flip("payments.region", ["us_state", "country_code"])
    cols = [
        col("payment_id", "identifier", "values"),
        col("amount", amount_as, "nothing", [], ["money_usd", "money_cad"]),
        col("paid_on", paid_as, "day_gt_12", ["parse_date"], ["date_day_first", "date_month_first"]),
        col("method", "category_name", "values"),
        col("fee_pct", "percent_0_to_100", "name"),
        col("region", region_as, "nothing", [], ["us_state", "country_code"]),
    ]
    raw, clean = [], []
    for i in range(rows):
        paid = rand_date(2026, 2026)
        r = [f"P-{90000 + i}", round(rng.uniform(5, 400), 2), paid.strftime("%d/%m/%Y" if paid_as == "date_day_first" else "%m/%d/%Y"),
             rng.choice(["card", "cash", "transfer"]), round(rng.uniform(1.5, 3.5), 2), rng.choice(BOTH_STATE_AND_COUNTRY)]
        raw.append(r)
        clean.append(r[:2] + [paid.isoformat()] + r[3:])
    tables["payments"] = {"columns": cols, "raw": raw, "clean": clean}

    # ---- shift_events ----
    dur_as = flip("shift_events.duration", ["duration_minutes", "duration_seconds"])
    cols = [
        col("event_id", "identifier", "values"),
        col("started", "timestamp_epoch_seconds", "values", ["parse_timestamp"]),
        col("ended", "timestamp_epoch_seconds", "values", ["parse_timestamp"]),
        col("duration", dur_as, "neighbours", [], ["duration_minutes", "duration_seconds"]),   # ended - started says which
        col("score", "rating_score", "name", ["replace_missing_marker"]),
        col("site_state", "us_state", "values", ["normalise_categories"]),
    ]
    raw, clean = [], []
    for i in range(rows):
        started = base + rng.randrange(300 * 86400)
        d = rng.randint(30, 240)
        seconds = d * 60 if dur_as == "duration_minutes" else d
        score = -1 if rng.random() < 0.15 else rng.randint(0, 100)
        state = rng.choice(list(STATE_VARIANTS))
        raw.append([f"E-{5000 + i}", started, started + seconds, d, score, rng.choice(STATE_VARIANTS[state])])
        clean.append([f"E-{5000 + i}", iso(started), iso(started + seconds), seconds, "" if score == -1 else score, state])
    tables["shift_events"] = {"columns": cols, "raw": raw, "clean": clean}

    for t in tables.values():
        for n, c in enumerate(t["columns"], 1):
            c["cryptic"] = "c" + str(n)
    return tables, flips


def write(out, instances, rows=200, seed=20261112):
    out = Path(out)
    for inst in range(instances):
        tables, flips = build(inst, rows, seed)
        folder = out / f"instance{inst}"
        for kind in ("raw", "clean"):
            (folder / kind).mkdir(parents=True, exist_ok=True)
            for name, t in tables.items():
                with (folder / kind / (name + ".csv")).open("w", newline="", encoding="utf-8") as fh:
                    w = csv.writer(fh)
                    w.writerow([c["name"] for c in t["columns"]])
                    w.writerows(t[kind])
        key = {"instance": inst, "seed": seed, "synthetic": True, "flips": flips,
               "tables": {name: t["columns"] for name, t in tables.items()}}
        (folder / "key.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--instances", type=int, default=4)
    ap.add_argument("--rows", type=int, default=200)
    ap.add_argument("--out", default=str(Path(__file__).parent / "data"))
    a = ap.parse_args()
    out = write(a.out, a.instances, a.rows)
    tables, _ = build(0, a.rows)
    print(a.instances, "instances,", len(tables), "tables,", sum(len(t["columns"]) for t in tables.values()), "columns each, written to", out)
