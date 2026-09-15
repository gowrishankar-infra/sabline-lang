#!/usr/bin/env python3
"""Does a model write correct Velaris from the card on the first attempt?

    ANTHROPIC_API_KEY=... python evals/card_eval.py            # claude-opus-5
    OPENAI_API_KEY=... MODEL=<model> python evals/card_eval.py
    MODEL=claude-sonnet-5 python evals/card_eval.py

The model is given LLM.md (`velaris card`) as its system prompt and the
five tasks in tasks.json, one at a time, with no retries and no hints.
Each answer is checked (`velaris check`), audited (`velaris audit`) and
run under `--allow io` - plus `ffi:` modules only where a task needs
them - with a 10 second timeout, and the outcome goes into RESULTS.md:
compiled first try, ran correctly, proven promises.

With no API key set the script prints one line and exits 0. It never
calls an API it was not given a key for. Answers are kept under
evals/answers/<model>/ so a row can be inspected.

Providers: Anthropic (ANTHROPIC_API_KEY, the `anthropic` package) and
OpenAI (OPENAI_API_KEY, the `openai` package; MODEL is required).
PROVIDER=anthropic|openai chooses when both keys are set.
"""
import json
import os
import re
import sys
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import velaris  # noqa: E402

TIMEOUT = 10
MEMORY_MB = 256
RESULTS = os.path.join(HERE, "RESULTS.md")
SEED_ROWS = [
    # rows reported in HALL_OF_FAME.md / CHANGELOG.md, not produced here
    ("Gemini (Aug 2026 review)", "reported, not reproduced by this script"),
    ("ChatGPT (Aug 2026 review)", "reported, not reproduced by this script"),
    ("Claude (Aug 2026 review)", "reported, not reproduced by this script"),
]


def pick_provider() -> tuple[Any, ...]:
    """(provider, model) or (None, reason)."""
    want = os.environ.get("PROVIDER", "").lower()
    have_a = bool(os.environ.get("ANTHROPIC_API_KEY"))
    have_o = bool(os.environ.get("OPENAI_API_KEY"))
    if want == "anthropic" or (not want and have_a):
        if not have_a:
            return None, "PROVIDER=anthropic but ANTHROPIC_API_KEY is not set"
        return "anthropic", os.environ.get("MODEL") or "claude-opus-5"
    if want == "openai" or (not want and have_o):
        if not have_o:
            return None, "PROVIDER=openai but OPENAI_API_KEY is not set"
        model = os.environ.get("MODEL")
        if not model:
            return None, "OPENAI_API_KEY is set; MODEL must name the model"
        return "openai", model
    return None, ("no API key set (ANTHROPIC_API_KEY or OPENAI_API_KEY); "
                  "nothing to evaluate")


def ask_anthropic(model: str, system: str, prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic()
    # thinking is on by default on this model family; a short program
    # does not need streaming
    response = client.messages.create(
        model=model, max_tokens=8000, system=system,
        messages=[{"role": "user", "content": prompt}])
    if response.stop_reason == "refusal":
        return ""
    return "".join(b.text for b in response.content if b.type == "text")


def ask_openai(model: str, system: str, prompt: str) -> str:
    from openai import OpenAI
    client = OpenAI()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": prompt}])
    return response.choices[0].message.content or ""


def extract_program(answer: str) -> str:
    """The first fenced code block, or the whole answer if none."""
    m = re.search(r"```[a-zA-Z]*\n(.*?)```", answer, re.S)
    return (m.group(1) if m else answer).strip() + "\n"


def judge(task: dict[Any, Any], source: str, path: str) -> dict[Any, Any]:
    """check, audit, run: one dict per task with the three verdicts."""
    out = {"id": task["id"], "compiled": False, "ran": False,
           "proven": 0, "promising": 0, "evidence": ""}
    chk = velaris.check(source, path=path)
    if not chk.ok:
        p = chk.problems[0]
        out["evidence"] = f"check: {p.code} line {p.line}"
        return out
    out["compiled"] = True
    aud = velaris.audit(source, path=path)
    promising = [f for f in aud.functions if f["requires"] or f["ensures"]]
    out["promising"] = len(promising)
    out["proven"] = sum(1 for f in promising if f["status"] == "proven")
    r = velaris.run(source, path=path, allow=set(task["needs"]),
                    stdin=task["stdin"], timeout=TIMEOUT,
                    max_memory_mb=MEMORY_MB)
    want = task["expect"]
    if "refused_effect" in want:
        ok = r.refused_effect == want["refused_effect"]
        out["evidence"] = (f"run: refused {r.refused_effect}" if r.refused_effect
                           else f"run: exit {r.exit_code}, not refused")
    else:
        got = r.output.strip()
        ok = r.ok and got == want["stdout"]
        out["evidence"] = ("run: ok" if ok else
                           f"run: exit {r.exit_code}, stdout {got[:40]!r}"
                           + (f", {r.problems[0].code}" if r.problems else ""))
    if task.get("proof_required") and out["proven"] == 0:
        ok = False
        out["evidence"] += "; no proven promise"
    out["ran"] = ok
    return out


def write_results(model_rows: dict[Any, Any]) -> None:
    """RESULTS.md: the seed rows, then one row per model measured."""
    L = ["# Card eval results", "",
         "Generated by `python evals/card_eval.py`; one attempt per task, no "
         "retries, no hints beyond LLM.md. Columns: how many of the five "
         "tasks compiled on the first attempt, ran correctly under the "
         "task's budget with a 10 s timeout, and how many promise-carrying "
         "functions in the answers were proven rather than left to runtime.",
         "", "| model | compiled first try | ran correctly | proven promises | notes |",
         "|---|---|---|---|---|"]
    for name, note in SEED_ROWS:
        L.append(f"| {name} | - | - | - | {note} |")
    for name, rows in sorted(model_rows.items()):
        compiled = sum(1 for r in rows if r["compiled"])
        ran = sum(1 for r in rows if r["ran"])
        proven = sum(r["proven"] for r in rows)
        promising = sum(r["promising"] for r in rows)
        notes = "; ".join(f"{r['id']}: {r['evidence']}" for r in rows
                          if not r["ran"]) or "all five"
        L.append(f"| {name} | {compiled}/5 | {ran}/5 | "
                 f"{proven}/{promising} | {notes} |")
    L.append("")
    with open(RESULTS, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def read_existing() -> dict[Any, Any]:
    """Rows already in RESULTS.md that this script produced, by model."""
    rows: dict[str, str] = {}
    if not os.path.exists(RESULTS):
        return rows
    for line in open(RESULTS, encoding="utf-8"):
        if line.startswith("| ") and "/5 |" in line:
            rows[line.split("|")[1].strip()] = line.rstrip("\n")
    return rows


def main() -> int:
    provider, model = pick_provider()
    if provider is None:
        print(f"card eval skipped: {model}")
        return 0
    card = open(os.path.join(ROOT, "LLM.md"), encoding="utf-8").read()
    tasks = json.load(open(os.path.join(HERE, "tasks.json"),
                           encoding="utf-8"))["tasks"]
    ask = ask_anthropic if provider == "anthropic" else ask_openai
    outdir = os.path.join(HERE, "answers", re.sub(r"[^\w.-]", "_", model))
    os.makedirs(outdir, exist_ok=True)
    rows = []
    print(f"{provider}: {model}, {len(tasks)} tasks")
    for task in tasks:
        answer = ask(model, card, task["prompt"])
        source = extract_program(answer)
        path = os.path.join(outdir, task["id"] + ".vel")
        with open(path, "w", encoding="utf-8") as f:
            f.write(source)
        row = judge(task, source, path)
        rows.append(row)
        print(f"  {task['id']:<16} compiled={row['compiled']!s:<5} "
              f"ran={row['ran']!s:<5} proven={row['proven']}/"
              f"{row['promising']}  {row['evidence']}")
    existing = read_existing()
    # keep rows other models produced; replace this model's own row
    kept = {}
    for name, line in existing.items():
        if name != model and name not in dict(SEED_ROWS):
            kept[name] = line
    write_results({model: rows})
    if kept:
        with open(RESULTS, "a", encoding="utf-8") as f:
            for line in kept.values():
                f.write(line + "\n")
    print(f"wrote {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
