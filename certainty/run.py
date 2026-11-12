"""Ask a model the same questions at each level of documentation, and score it.

    python run.py --base-url http://localhost:8000/v1 --model <name> --reps 5

Works with any server that speaks the OpenAI chat-completions format, which
includes vLLM and Ollama running on your own machine. Only the documentation
text and the question are sent. The model never sees a row of data: it writes
SQL, and this script runs that SQL locally and compares the result with the
known answer.

    python run.py --dry-run     # no model: fake replies, to check the pipeline

Every attempt is appended to attempts.jsonl as it finishes, so a stopped run
picks up where it left off.
"""
import argparse
import datetime as dt
import decimal
import json
import math
import os
import random
import re
import threading
import urllib.error
import urllib.request
from pathlib import Path

import duckdb

import context as ctx
import report

HERE = Path(__file__).parent

SYSTEM = (
    "You write DuckDB SQL for a read-only human resources database. You are shown the documentation that exists "
    "for the tables and one question. You cannot see any rows.\n"
    "Reply with one JSON object and nothing else, with these keys:\n"
    '  "sql": one SELECT statement that answers the question\n'
    '  "confidence": a number from 0 to 100, your estimate of the chance that the query returns the correct answer\n'
    '  "cannot_answer": true if the documentation is not enough to answer reliably, or the tables do not hold what '
    "the question asks for; otherwise false\n"
    '  "missing": one sentence naming what you had to guess, or "" if nothing'
)


def load_questions(path=None):
    return json.loads(Path(path or HERE / "questions.json").read_text(encoding="utf-8"))["questions"]


# ---------- running SQL and comparing answers ----------

def safe_sql(sql):
    s = (sql or "").strip().rstrip(";").strip()
    if not re.match(r"(?is)^(select|with)\b", s) or ";" in s:
        raise ValueError("not a single SELECT statement")
    return s


def run_sql(con, sql, seconds=30):
    """Run one SELECT with a time limit. Returns at most 1,000 rows."""
    timer = threading.Timer(seconds, con.interrupt)
    timer.start()
    try:
        return con.execute(safe_sql(sql)).fetchmany(1000)
    finally:
        timer.cancel()


def cell(v):
    if v is None:
        return ("0null", "")
    if isinstance(v, bool):
        return ("2text", str(v))
    if isinstance(v, (int, float, decimal.Decimal)):
        return ("1num", float(v))
    if isinstance(v, (dt.date, dt.datetime)):
        return ("2text", v.isoformat())
    return ("2text", str(v).strip())


def canon(rows):
    """Rows and the cells in each row sorted, so column and row order do not matter."""
    return sorted(sorted(cell(v) for v in row) for row in rows)


def same(got, gold, tol=0.01):
    a, b = canon(got), canon(gold)
    if len(a) != len(b):
        return False
    for ra, rb in zip(a, b):
        if len(ra) != len(rb):
            return False
        for (ka, va), (kb, vb) in zip(ra, rb):
            if ka != kb:
                return False
            if ka == "1num":
                if abs(va - vb) > tol:
                    return False
            elif va != vb:
                return False
    return True


def signature(rows):
    """A short string that is equal for equal answers. Used to see whether repeated runs agree."""
    return json.dumps([[v if k != "1num" else round(v, 2) for k, v in row] for row in canon(rows)])[:2000]


# ---------- talking to the model ----------

class Model:
    """One OpenAI-style chat endpoint. Asks for token probabilities and stops asking if the server refuses."""

    def __init__(self, base_url, model, temperature, max_tokens, api_key, timeout, logprobs=True):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model, self.temperature, self.max_tokens = model, temperature, max_tokens
        self.api_key, self.timeout, self.logprobs = api_key, timeout, logprobs

    def _post(self, body):
        req = urllib.request.Request(
            self.url, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + (self.api_key or "none")},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read())

    def ask(self, system, user):
        """Returns (reply text, [(token, log probability), ...] or None)."""
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.logprobs:
            try:
                data = self._post(dict(body, logprobs=True))
            except urllib.error.HTTPError as e:
                if e.code not in (400, 422):
                    raise
                self.logprobs = False
                print("(this server does not return token probabilities; continuing without them)")
                data = self._post(body)
        else:
            data = self._post(body)
        choice = data["choices"][0]
        tokens = None
        content = (choice.get("logprobs") or {}).get("content")
        if content:
            tokens = [(t.get("token", ""), t.get("logprob")) for t in content if t.get("logprob") is not None]
        return choice["message"].get("content") or "", tokens


def sql_token_stats(tokens, sql):
    """Mean log probability of the tokens that spell the SQL, and the probability of the whole SQL.

    Falls back to every token in the reply when the SQL cannot be located in it."""
    if not tokens:
        return None, None
    text = "".join(t for t, _ in tokens)
    needle = json.dumps(sql)[1:-1] if sql else ""
    start = text.find(needle) if needle else -1
    picked, pos = [], 0
    for tok, lp in tokens:
        end = pos + len(tok)
        if start < 0 or (end > start and pos < start + len(needle)):
            picked.append(lp)
        pos = end
    if not picked:
        return None, None
    total = sum(picked)
    return total / len(picked), math.exp(max(total, -700))


def parse_reply(text):
    """Pull the JSON object out of a reply. Returns None when there is none."""
    text = re.sub(r"(?is)<think>.*?</think>", "", text or "")
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(text[start:end + 1])
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None
    try:
        conf = max(0.0, min(100.0, float(obj.get("confidence"))))
    except (TypeError, ValueError):
        conf = None
    return {
        "sql": obj.get("sql") if isinstance(obj.get("sql"), str) else "",
        "confidence": conf,
        "cannot_answer": obj.get("cannot_answer") is True,
        "missing": str(obj.get("missing") or "")[:300],
    }


def fake_reply(q, name, kinds, rep):
    """Stand-in for a model, for --dry-run. Its answers mean nothing."""
    rng = random.Random(q["id"] + "|" + name + "|" + str(rep))
    if q.get("unanswerable"):
        return json.dumps({"sql": "select 0", "confidence": rng.randint(20, 90), "cannot_answer": rng.random() < 0.5, "missing": ""})
    right = rng.random() < 0.15 + 0.14 * len(kinds)
    return json.dumps({
        "sql": q["gold_sql"] if right else "select 0",
        "confidence": rng.randint(45, 95),
        "cannot_answer": rng.random() < 0.05,
        "missing": "",
    })


# ---------- one attempt ----------

def attempt(con, q, gold, reply_text, tokens=None):
    """Score one reply.

    Answerable question: correct, wrong, sql_error, abstained or bad_reply.
    Unanswerable question: declined_ok or answered_unanswerable (or bad_reply)."""
    rec = {"status": "bad_reply", "confidence": None, "sql": "", "missing": "", "answer": "BAD_REPLY",
           "logprob_mean": None, "sql_prob": None}
    reply = parse_reply(reply_text)
    if reply is None:
        return rec
    rec.update(confidence=reply["confidence"], sql=reply["sql"], missing=reply["missing"])
    rec["logprob_mean"], rec["sql_prob"] = sql_token_stats(tokens, reply["sql"])
    if q.get("unanswerable"):
        ok = reply["cannot_answer"]
        rec.update(status="declined_ok" if ok else "answered_unanswerable", answer="DECLINED" if ok else "ANSWERED")
        return rec
    if reply["cannot_answer"]:
        rec.update(status="abstained", answer="ABSTAINED")
        return rec
    try:
        rows = run_sql(con, reply["sql"])
    except Exception as e:  # the model's SQL failed; that is a result, not a crash
        rec.update(status="sql_error", answer="SQL_ERROR", error=str(e)[:200])
        return rec
    rec.update(status="correct" if same(rows, gold, q.get("tol", 0.01)) else "wrong", answer=signature(rows))
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", default=str(HERE / "build" / "legacy.duckdb"))
    ap.add_argument("--base-url", default="http://localhost:8000/v1")
    ap.add_argument("--model", default="")
    ap.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""), help="local servers ignore this")
    ap.add_argument("--mode", default="ladder", choices=["ladder", "add-one", "leave-one-out", "controls", "all"])
    ap.add_argument("--reps", type=int, default=5, help="times each question is asked in each context")
    ap.add_argument("--temperature", type=float, default=0.7,
                    help="keep above 0: at 0 the repeats are copies and agreement means nothing")
    ap.add_argument("--max-tokens", type=int, default=3000)
    ap.add_argument("--timeout", type=int, default=300, help="seconds to wait for one reply")
    ap.add_argument("--only", default="", help="comma-separated question ids, to run a subset")
    ap.add_argument("--no-logprobs", action="store_true", help="do not ask the server for token probabilities")
    ap.add_argument("--out", default="")
    ap.add_argument("--dry-run", action="store_true", help="use fake replies instead of a model")
    a = ap.parse_args()
    if not a.dry_run and not a.model:
        ap.error("--model is required unless --dry-run")

    label = "dry-run" if a.dry_run else re.sub(r"[^A-Za-z0-9._-]+", "_", a.model)
    out = Path(a.out or HERE / "runs" / label)
    out.mkdir(parents=True, exist_ok=True)
    log = out / "attempts.jsonl"

    con = duckdb.connect(a.db, read_only=True)
    layer, schema = ctx.load_layer(), ctx.read_schema(con)
    questions = [q for q in load_questions() if not a.only or q["id"] in a.only.split(",")]
    gold = {q["id"]: con.execute(q["gold_sql"]).fetchall() for q in questions if not q.get("unanswerable")}
    plan = ctx.contexts(a.mode)
    misled = set(layer["misleading"]["affected_questions"])
    model = None if a.dry_run else Model(a.base_url, a.model, a.temperature, a.max_tokens, a.api_key, a.timeout, not a.no_logprobs)

    done = set()
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done.add((r["context"], r["question"], r["rep"]))

    total = len(plan) * len(questions) * a.reps
    n = 0
    with log.open("a", encoding="utf-8") as fh:
        for name, kinds in plan:
            variant = ctx.VARIANTS.get(name)
            docs = ctx.render(layer, schema, kinds, variant)
            for q in questions:
                user = ("DOCUMENTATION\n" + docs + "\nExtract date (treat as today): " + layer["extract_date"] +
                        "\n\nQUESTION\n" + q["question"] + "\nReturn: " + q["returns"] + ".")
                for rep in range(a.reps):
                    n += 1
                    if (name, q["id"], rep) in done:
                        continue
                    if a.dry_run:
                        text, tokens = fake_reply(q, name, kinds, rep), None
                    else:
                        try:
                            text, tokens = model.ask(SYSTEM, user)
                        except Exception as e:
                            raise SystemExit("could not reach the model at " + a.base_url + ": " + str(e) +
                                             "\nFinished attempts are saved; run the same command to continue.")
                    rec = attempt(con, q, gold.get(q["id"]), text, tokens)
                    rec.update(context=name, kinds=kinds, variant=variant, question=q["id"], rep=rep,
                               model=label, dry_run=a.dry_run, needs=q.get("needs", []),
                               unanswerable=bool(q.get("unanswerable")),
                               misled=variant == "misleading" and q["id"] in misled,
                               temperature=a.temperature)
                    fh.write(json.dumps(rec) + "\n")
                    fh.flush()
                    print(f"[{n}/{total}] {name:22} {q['id']} #{rep} {rec['status']:21} conf={rec['confidence']}")

    path = report.write(out)
    print("\nreport:", path)


if __name__ == "__main__":
    main()
