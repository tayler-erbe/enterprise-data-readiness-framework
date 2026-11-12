"""Build the "legacy system" copy of a synthetic workforce dataset.

The source tables have plain names (fact_assignment, annual_salary). A model can
guess what those mean with no documentation, so they cannot show what
documentation is worth. This script rewrites them the way an older business
system stores them: short names, coded values, a monthly pay rate, an open-ended
date of 9999-12-31, and rows entered in error that are flagged void but never
deleted. Every one of those is a thing a data dictionary has to explain.

    python build_legacy.py --source <folder of parquet files> --out build/legacy.duckdb

Needs duckdb. The source is synthetic, so the output is too.
"""
import argparse
from pathlib import Path

import duckdb

SOURCE_TABLES = ["dim_person", "dim_job", "dim_org", "fact_assignment", "fact_event", "fact_leave"]

ACTION_CODES = {
    "NEW_HIRE": "H10",
    "MERIT": "M20",
    "PROMOTION": "P30",
    "LATERAL_TRANSFER": "X40",
    "CAREER_CHANGE": "C45",
    "RECLASSIFICATION": "R50",
    "RESIGN": "T61",
    "RETIRE": "T62",
    "INVOLUNTARY": "T63",
    "DEATH": "T64",
    "POSITION_ELIMINATED": "T65",
}
ETHNICITY_CODES = {
    "American Indian or Alaska Native": "01",
    "Asian": "02",
    "Black or African American": "03",
    "Hispanic or Latino": "04",
    "Native Hawaiian or Other Pacific Islander": "05",
    "White": "06",
    "Two or more races": "07",
}
LEAVE_CODES = {"MEDICAL": "M", "FAMILY": "F", "PERSONAL": "P"}


def case(column, mapping):
    parts = " ".join("when '" + k + "' then '" + v + "'" for k, v in mapping.items())
    return "case " + column + " " + parts + " end"


def attach_source(con, source):
    """Expose the source parquet files as views under their plain names."""
    for name in SOURCE_TABLES:
        path = (Path(source) / (name + ".parquet")).as_posix()
        con.execute("create or replace view " + name + " as select * from read_parquet('" + path + "')")


def build(source, out):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    con = duckdb.connect(str(out))
    con.execute("create schema src")
    con.execute("use src")
    attach_source(con, source)
    con.execute("use main")

    con.execute(
        "create table PSN_MST as select person_id as PSN_NO, birth_date as BRTH_DT, "
        "case sex when 'M' then '1' else '2' end as GNDR_CD, "
        + case("race_ethnicity", ETHNICITY_CODES) + " as ETH_CD, first_hire_date as ORIG_HR_DT "
        "from src.dim_person order by 1"
    )

    con.execute(
        "create temp table fam as select family_key, 'F' || lpad(cast(dense_rank() over (order by family_key) as varchar), 2, '0') as FAM_CD "
        "from (select distinct family_key from src.dim_job)"
    )
    con.execute(
        "create table JB_REF as select j.job_code as JB_CD, f.FAM_CD, j.family_name as FAM_DESC, j.track as TRK_CD, "
        "j.level_no as LVL_NO, j.job_title as JB_TTL, j.soc_2018 as SOC_CD, j.ai_exposure_assumed as AI_EXP_VAL, "
        "j.band_min as RNG_MIN, j.band_max as RNG_MAX, j.family_intro_year as FAM_STRT_YR, p.FAM_CD as PRED_FAM_CD, "
        "case when j.critical_family then 'Y' else 'N' end as CRIT_FL, case when j.top_level then 'Y' else 'N' end as TOP_FL "
        "from src.dim_job j join fam f using (family_key) left join fam p on p.family_key = j.predecessor_family order by 1"
    )

    con.execute(
        "create table ORG_REF as select org_code as ORG_CD, parent_org_code as PAR_ORG_CD, org_level as ORG_LVL, "
        "org_title as ORG_TTL, unit_kind as UNIT_TYP, case when is_leaf then 'Y' else 'N' end as LEAF_FL, path_codes as ORG_PATH "
        "from src.dim_org order by 1"
    )

    # Assignment history: the true rows, then two kinds of row entered in error.
    base = (
        "select person_id as PSN_NO, start_date as EFF_DT, end_date as END_DT, job_code as JB_CD, org_code as ORG_CD, "
        "position_id as POS_NO, round(annual_salary / 12, 2) as BASE_RT, " + case("start_reason", ACTION_CODES) + " as ACT_CD, "
        "case when is_current then 'Y' else 'N' end as CUR_FL, 'N' as VOID_FL from src.fact_assignment"
    )
    # 1. A keying mistake: the same row entered with the wrong rate, later voided.
    wrong_rate = (
        "select person_id, start_date, end_date, job_code, org_code, position_id, round(annual_salary * 1.1 / 12, 2), "
        + case("start_reason", ACTION_CODES) + ", case when is_current then 'Y' else 'N' end, 'Y' "
        "from src.fact_assignment where hash(person_id, start_date) % 61 = 0"
    )
    # 2. A row opened for someone who had already left, later voided. It still says "current".
    after_exit = (
        "select person_id, end_date + 1, date '9999-12-31', job_code, org_code, position_id, round(annual_salary / 12, 2), "
        "'M20', 'Y', 'Y' from (select *, row_number() over (partition by person_id order by start_date desc) as rn "
        "from src.fact_assignment where person_id not in (select person_id from src.fact_assignment where is_current)) "
        "where rn = 1 and hash(person_id) % 150 = 0"
    )
    con.execute("create table ASG_HST as select * from (" + base + " union all " + wrong_rate + " union all " + after_exit + ") order by 1, 2, 10")

    con.execute(
        "create table ACT_LOG as select person_id as PSN_NO, event_date as ACT_DT, seq as SEQ_NO, " + case("reason", ACTION_CODES) + " as ACT_CD, "
        "job_code as JB_CD, org_code as ORG_CD, position_id as POS_NO, round(salary_before / 12, 2) as PRV_RT, "
        "round(salary_after / 12, 2) as NEW_RT from src.fact_event order by 1, 2, 3"
    )

    con.execute(
        "create table LV_HST as select person_id as PSN_NO, leave_start as LV_BGN_DT, leave_end as LV_END_DT, "
        + case("reason", LEAVE_CODES) + " as LV_TYP_CD from src.fact_leave order by 1, 2"
    )

    for view in SOURCE_TABLES:
        con.execute("drop view src." + view)
    con.execute("drop schema src")
    counts = {t: con.execute("select count(*) from " + t).fetchall()[0][0] for t in ["PSN_MST", "JB_REF", "ORG_REF", "ASG_HST", "ACT_LOG", "LV_HST"]}
    void = con.execute("select count(*), count(*) filter (where CUR_FL = 'Y') from ASG_HST where VOID_FL = 'Y'").fetchall()[0]
    con.close()
    return counts, void


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", required=True, help="folder holding dim_person.parquet, fact_assignment.parquet and the rest")
    ap.add_argument("--out", default=str(Path(__file__).parent / "build" / "legacy.duckdb"))
    a = ap.parse_args()
    counts, void = build(a.source, a.out)
    for t, n in counts.items():
        print(f"{t:8} {n:>8,} rows")
    print(f"void rows in ASG_HST: {void[0]:,} ({void[1]:,} of them still flagged current)")
    print("wrote", a.out)
