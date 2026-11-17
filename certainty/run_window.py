"""Run every test on one model, in order of importance, when the GPU is free.

    python run_window.py --base-url http://localhost:8000/v1 --model <name> --time-check
    python run_window.py --base-url http://localhost:8000/v1 --model <name>
    python run_window.py --base-url http://localhost:8000/v1 --model <name> --steps 1,2

--time-check sends 20 questions, times them, and prints how long each step would
take on this model. Nothing is saved. Do this first.

Every step saves each reply as it arrives. If the run stops (the GPU is needed
for something else, the machine sleeps), repeat the same command and it carries
on from where it stopped.

Steps, most important first:

    1  detector       testset/detect.py: 720 columns and 120 files, 3 repeats
    2  column meaning columns/ask.py: full, cryptic and lone-column names, 5 and 50 rows, 3 repeats
    3  descriptions   testset/conditions.py: forced, and allowed to say "can't tell", 1 repeat
    4  conflicts      testset/conditions.py: contradicted documentation and misleading names, 1 repeat
    5  sample size    testset/conditions.py: 5 rows, 50 rows, whole-column profile, 1 repeat
    6  real tables    realdata/run_real.py: the control group, 3 repeats
    7  SQL            run.py: 25 questions at five levels of documentation, 5 repeats
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "testset"))
sys.path.insert(0, str(HERE / "columns"))


def steps():
    """[(number, name, folder, command tail, requests)]"""
    import build
    import conditions as cond
    import make_tables
    import tables as file_cases
    _, labels = build.build(variations=12)
    _, files = file_cases.build(variations=12)
    count = lambda names: sum(len(list(cond.items(c))) for c in names)
    columns = sum(len(t["columns"]) for t in make_tables.build(0)[0].values())
    describe = ["describe_forced", "describe_allowed"]
    conflicts = ["doc_agree", "doc_conflict", "doc_agree_asked", "doc_conflict_asked", "name_conflict", "name_two", "name_clear"]
    size = ["rows5", "rows50", "profile"]
    c = lambda names: ["conditions.py", "--condition", ",".join(names), "--reps", "1", "--quiet"]
    return [
        (1, "detector", "testset", ["detect.py"], (len(labels) + len(files)) * 3),
        (2, "column meaning", "columns", ["ask.py"], columns * 4 * 4 * 3),
        (3, "descriptions", "testset", c(describe), count(describe)),
        (4, "conflicts", "testset", c(conflicts), count(conflicts)),
        (5, "sample size", "testset", c(size), count(size)),
        (6, "real tables", "realdata", ["run_real.py"], 66 * 3),
        (7, "SQL", ".", ["run.py"], 25 * 5 * 5),
    ]


def time_check(a, plan):
    import build
    import detect
    import run
    tables, labels = build.build(variations=1)
    model = run.Model(a.base_url, a.model, 0.7, 2500, a.api_key, a.timeout, False)
    picked = labels[::max(1, len(labels) // 20)][:20]
    took, bad = [], 0
    for k, label in enumerate(picked):
        user, _ = detect.prompt(label["table"], tables[label["table"]], label, 10)
        start = time.time()
        text, _ = model.ask(detect.SYSTEM, user)
        took.append(time.time() - start)
        bad += detect.parse(text) is None
        print(f"  question {k + 1} of {len(picked)}: {took[-1]:.1f} seconds")
    per = sum(took) / len(took)
    print(f"\n{per:.1f} seconds a question on average. {bad} of {len(picked)} replies could not be read.")
    if bad > len(picked) / 2:
        print("More than half the replies could not be read. Check the model name and --max-tokens before a full run.")
    print("\nEstimated time for each step on this model (questions are sent one at a time):\n")
    total = 0
    for n, name, _, _, requests in plan:
        hours = requests * per / 3600
        total += hours
        print(f"  {n}  {name:15} {requests:>6} questions   {hours:5.1f} hours")
    print(f"\n  everything      {sum(p[4] for p in plan):>6} questions   {total:5.1f} hours")
    print("\nThe estimate comes from 20 detector questions. Steps with longer prompts (50 rows, SQL) will run slower than it says.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base-url", default="http://localhost:8000/v1")
    ap.add_argument("--model", required=True)
    ap.add_argument("--api-key", default="")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--steps", default="", help="comma-separated step numbers; default all")
    ap.add_argument("--time-check", action="store_true")
    ap.add_argument("--list", action="store_true", help="print the steps and their sizes, then stop")
    a = ap.parse_args()
    plan = steps()
    if a.steps:
        keep = {int(s) for s in a.steps.split(",")}
        plan = [p for p in plan if p[0] in keep]
    if a.list:
        for n, name, folder, tail, requests in plan:
            print(f"{n}  {name:15} {requests:>6} questions   {folder}/{' '.join(tail)}")
        print(f"   {'total':15} {sum(p[4] for p in plan):>6} questions")
        return
    if a.time_check:
        return time_check(a, plan)
    for n, name, folder, tail, requests in plan:
        print(f"\n===== step {n}: {name} ({requests} questions) =====", flush=True)
        cmd = [sys.executable] + tail + ["--base-url", a.base_url, "--model", a.model, "--timeout", str(a.timeout)]
        if a.api_key:
            cmd += ["--api-key", a.api_key]
        start = time.time()
        done = subprocess.run(cmd, cwd=HERE / folder)
        print(f"step {n} took {(time.time() - start) / 60:.0f} minutes", flush=True)
        if done.returncode != 0:
            raise SystemExit(f"step {n} ({name}) stopped. Finished replies are saved; repeat the same command to carry on.")
    print("\nAll steps finished. Reports are in each folder's runs/ directory.")


if __name__ == "__main__":
    main()
