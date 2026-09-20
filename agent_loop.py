#!/usr/bin/env python3
"""Write Sabline with a model, and iterate against the compiler.

Most agent loops iterate against tests: run it, see what breaks, try
again. This iterates against a *proof*. The compiler answers with
structured errors - a code, a message, a line, and numbered fixes - and
for contracts it answers with the exact input that breaks a promise.
That is a much stronger signal than a failing test, and it is what
makes Sabline a good target for generated code.

    export ANTHROPIC_API_KEY=...
    python agent_loop.py "read a CSV of expenses and print the total"
    python agent_loop.py --file draft.vel        # fix an existing draft
    python agent_loop.py --dry-run               # no model, show the loop
    python agent_loop.py --metric                # the round-trip metric
    python agent_loop.py --metric --offline      # the same, replayed

The result is written to the file you name (default: generated.vel) and
audited, so you can see what it may touch before you run it.

The metric (8.2) is ten tasks, tests/agent_loop/tasks.json. For each, the
loop runs to a program that compiles, and the metric records how many rounds
that took, whether the audit's effects are the ones the task needs, and how
many promises are proven. With a key, the ten tasks go to the model
(SABLINE_MODEL, default claude-sonnet-5) and the numbers are that model's.
With --offline, or with no ANTHROPIC_API_KEY, each task replays the replies
recorded for it, so the loop, the compiler's answers and the metric run with
no model and no network; CI runs that, and fails unless every task ends as
recorded. --json FILE writes the numbers.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).parent
SABLINE = HERE / "sabline.py"
CARD = HERE / "LLM.md"
TASKS = HERE / "tests" / "agent_loop" / "tasks.json"
MODEL = os.environ.get("SABLINE_MODEL", "claude-sonnet-5")
ROUNDS = 6

Ask = Callable[[list[dict[str, str]]], str]


def check(path: Path) -> list[dict[str, Any]]:
    """Every problem the compiler can see, as data."""
    done = subprocess.run(
        [sys.executable, str(SABLINE), "check", str(path), "--json"],
        capture_output=True, text=True, timeout=600)
    text = (done.stdout or "").strip()
    if not text:
        return []
    try:
        report = json.loads(text)
    except json.JSONDecodeError:
        return [{"code": "?", "line": 0,
                 "message": (done.stderr or text)[:300], "fixes": []}]
    if isinstance(report, dict):
        return list(report.get("errors", []))
    out: list[dict[str, Any]] = []
    for item in report:                 # a flat list of errors, or a
        if "code" in item:              # list of per-file reports
            out.append(item)
        else:
            out.extend(item.get("errors", []))
    return out


def proof_state(path: Path) -> tuple[int, int]:
    """How many promises are proven rather than checked while running."""
    done = subprocess.run(
        [sys.executable, str(SABLINE), "proofs", str(path), "--json"],
        capture_output=True, text=True, timeout=900)
    try:
        report = json.loads(done.stdout)
    except (json.JSONDecodeError, TypeError):
        return (0, 0)
    totals = report.get("totals", {})
    return (totals.get("proven", 0),
            totals.get("proven", 0) + totals.get("runtime", 0))


def audit_effects(path: Path) -> list[str]:
    """The effects the audit says the program may cause."""
    done = subprocess.run(
        [sys.executable, str(SABLINE), "audit", str(path), "--json"],
        capture_output=True, text=True, timeout=900)
    try:
        report = json.loads(done.stdout)
    except (json.JSONDecodeError, TypeError):
        return []
    return sorted(report.get("effects", []))


def complain(errors: list[dict[str, Any]]) -> str:
    lines = []
    for e in errors[:8]:
        lines.append(f"line {e.get('line')}: [{e.get('code')}] "
                     f"{e.get('message')}")
        for fix in (e.get("fixes") or [])[:2]:
            lines.append(f"    possible fix: {fix}")
    return "\n".join(lines)


def ask_model(messages: list[dict[str, str]]) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit(
            "set ANTHROPIC_API_KEY, or use --dry-run to see the loop")
    body = json.dumps({
        "model": MODEL, "max_tokens": 4000, "messages": messages,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"content-type": "application/json",
                 "x-api-key": key,
                 "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            answer = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"the model refused: {e.read()[:300].decode()}")
    return "".join(part.get("text", "") for part in answer["content"])


def replay(replies: list[str]) -> Ask:
    """A model that gives the recorded replies in order, and then the last
    one again."""
    left = list(replies)

    def ask(messages: list[dict[str, str]]) -> str:
        return left.pop(0) if len(left) > 1 else left[0]
    return ask


def just_the_code(reply: str) -> str:
    if "```" not in reply:
        return reply.strip()
    chunk = reply.split("```", 2)[1]
    if chunk.startswith("sabline"):
        chunk = chunk[len("sabline"):]
    return chunk.strip("\n")


def loop(task: str, ask: Ask, out: Path, card: str,
         say: Callable[[str], None] = print) -> dict[str, Any]:
    """Ask, check, and ask again with the compiler's answer, until the
    program compiles or ROUNDS run out."""
    messages = [{"role": "user", "content":
                 f"{card}\n\n---\n\nWrite a Sabline program that does "
                 f"this:\n\n{task}\n\nReturn only the program in one "
                 f"code block. It must pass `sabline check`."}]
    seen: list[list[str]] = []
    for attempt in range(1, ROUNDS + 1):
        reply = ask(messages)
        out.write_text(just_the_code(reply) + "\n", encoding="utf-8")
        errors = check(out)
        seen.append(sorted({str(e.get("code")) for e in errors}))
        if not errors:
            proven, promising = proof_state(out)
            return {"compiled": True, "rounds": attempt, "codes": seen,
                    "proven": proven, "promises": promising,
                    "effects": audit_effects(out)}
        say(f"round {attempt}: {len(errors)} problem(s), asking again")
        for line in complain(errors).splitlines()[:4]:
            say(f"    {line}")
        messages.append({"role": "assistant", "content": reply})
        messages.append({"role": "user", "content":
                         "`sabline check` reported this. Fix it and "
                         "return the whole program again, only the code "
                         f"block:\n\n{complain(errors)}"})
    return {"compiled": False, "rounds": ROUNDS, "codes": seen,
            "proven": 0, "promises": 0, "effects": []}


def metric(offline: bool, json_to: Path | None) -> int:
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))["tasks"]
    live = not offline and bool(os.environ.get("ANTHROPIC_API_KEY"))
    mode = f"live, {MODEL}" if live else "offline, recorded replies"
    card = CARD.read_text(encoding="utf-8")
    print(f"agent loop metric: {len(tasks)} tasks, {mode}")
    print("-" * 62)
    rows: list[dict[str, Any]] = []
    wrong: list[str] = []
    with tempfile.TemporaryDirectory(prefix="sabline-agent-") as d:
        for t in tasks:
            got = loop(t["task"], ask_model if live else replay(t["replies"]),
                       Path(d) / f"{t['id']}.vel", card, say=lambda _: None)
            got["effects_match"] = got["effects"] == sorted(t["effects"])
            rows.append({"id": t["id"], **got})
            first = ",".join(got["codes"][0]) or "none"
            print(f"  {t['id']:<12} {'compiled' if got['compiled'] else 'GAVE UP '}"
                  f" in {got['rounds']} round(s); first round: {first}; "
                  f"effects {'as needed' if got['effects_match'] else 'DIFFER'}"
                  f" {got['effects']}; proven {got['proven']}/{got['promises']}")
            if not live and not (got["compiled"]
                                 and got["rounds"] == len(t["replies"])
                                 and got["codes"][0]
                                 and got["effects_match"]):
                wrong.append(t["id"])
    compiled = [r for r in rows if r["compiled"]]
    summary = {
        "mode": "live" if live else "offline",
        "model": MODEL if live else None,
        "tasks": len(rows),
        "compiled": len(compiled),
        "first_round": sum(1 for r in rows if r["compiled"] and r["rounds"] == 1),
        "mean_rounds": round(sum(r["rounds"] for r in compiled) / len(compiled), 2)
        if compiled else None,
        "effects_as_needed": sum(1 for r in rows if r["effects_match"]),
        "proven": sum(r["proven"] for r in rows),
        "promises": sum(r["promises"] for r in rows),
        "results": rows,
    }
    print("-" * 62)
    print(f"{summary['compiled']} of {summary['tasks']} compiled "
          f"({summary['first_round']} in the first round, mean "
          f"{summary['mean_rounds']} rounds); effects as needed in "
          f"{summary['effects_as_needed']}; {summary['proven']} of "
          f"{summary['promises']} promises proven")
    if json_to is not None:
        json_to.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    if wrong:
        print(f"not as recorded: {', '.join(wrong)}")
        return 1
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if "--metric" in argv:
        json_to = Path(argv[argv.index("--json") + 1]) if "--json" in argv else None
        return metric("--offline" in argv, json_to)
    dry = "--dry-run" in argv
    argv = [a for a in argv if a != "--dry-run"]
    out = Path(argv[argv.index("-o") + 1]) if "-o" in argv \
        else HERE / "generated.vel"
    argv = [a for a in argv if a != "-o" and a != str(out)]

    if "--file" in argv:
        draft = Path(argv[argv.index("--file") + 1])
        out.write_text(draft.read_text(encoding="utf-8"), encoding="utf-8")
        task = f"Fix this program:\n\n{draft.read_text(encoding='utf-8')}"
    else:
        task = " ".join(argv).strip()
        if not task:
            print(__doc__)
            return 1

    if dry:
        print("dry run: this is what the model would be told\n")
        print(f"  card:  {CARD} ({len(CARD.read_text(encoding='utf-8').split())} words)")
        print(f"  task:  {task}")
        print(f"  then:  sabline check {out} --json, "
              f"fed back for up to {ROUNDS} rounds")
        print(f"  then:  sabline audit {out}")
        return 0

    got = loop(task, ask_model, out, CARD.read_text(encoding="utf-8"))
    if got["compiled"]:
        print(f"round {got['rounds']}: compiles.", end=" ")
        if got["promises"]:
            print(f"{got['proven']} of {got['promises']} promise(s) proven "
                  f"before running.")
        else:
            print("no contracts to prove.")
        print(f"\nwritten to {out}\n")
        subprocess.run([sys.executable, str(SABLINE), "audit", str(out)],
                       timeout=900)
        return 0
    print(f"\ngave up after {ROUNDS} rounds. The last attempt is in "
          f"{out}; run `sabline check {out}` to see what remains.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
