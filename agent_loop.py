#!/usr/bin/env python3
"""Write Velaris with a model, and iterate against the compiler.

Most agent loops iterate against tests: run it, see what breaks, try
again. This iterates against a *proof*. The compiler answers with
structured errors - a code, a message, a line, and numbered fixes - and
for contracts it answers with the exact input that breaks a promise.
That is a much stronger signal than a failing test, and it is what
makes Velaris a good target for generated code.

    export ANTHROPIC_API_KEY=...
    python agent_loop.py "read a CSV of expenses and print the total"
    python agent_loop.py --file draft.vel        # fix an existing draft
    python agent_loop.py --dry-run               # no model, show the loop

The result is written to the file you name (default: generated.vel) and
audited, so you can see what it may touch before you run it.
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
VELARIS = HERE / "velaris.py"
CARD = HERE / "LLM.md"
MODEL = os.environ.get("VELARIS_MODEL", "claude-sonnet-4-6")
ROUNDS = 6


def check(path: Path) -> list:
    """Every problem the compiler can see, as data."""
    done = subprocess.run(
        [sys.executable, str(VELARIS), "check", str(path), "--json",
         "--no-cache"],
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
        return report.get("errors", [])
    out = []
    for item in report:                 # a flat list of errors, or a
        if "code" in item:              # list of per-file reports
            out.append(item)
        else:
            out.extend(item.get("errors", []))
    return out


def proof_state(path: Path) -> tuple:
    """How many promises are proven rather than checked while running."""
    done = subprocess.run(
        [sys.executable, str(VELARIS), "proofs", str(path), "--json",
         "--no-cache"],
        capture_output=True, text=True, timeout=900)
    try:
        report = json.loads(done.stdout)
    except Exception:
        return (0, 0)
    totals = report.get("totals", {})
    return (totals.get("proven", 0),
            totals.get("proven", 0) + totals.get("runtime", 0))


def complain(errors: list) -> str:
    lines = []
    for e in errors[:8]:
        lines.append(f"line {e.get('line')}: [{e.get('code')}] "
                     f"{e.get('message')}")
        for fix in (e.get("fixes") or [])[:2]:
            lines.append(f"    possible fix: {fix}")
    return "\n".join(lines)


def ask_model(messages: list) -> str:
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


def just_the_code(reply: str) -> str:
    if "```" not in reply:
        return reply.strip()
    chunk = reply.split("```", 2)[1]
    if chunk.startswith("velaris"):
        chunk = chunk[len("velaris"):]
    return chunk.strip("\n")


def main() -> int:
    argv = sys.argv[1:]
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
        print(f"  card:  {CARD} ({len(CARD.read_text().split())} words)")
        print(f"  task:  {task}")
        print(f"  then:  velaris check {out} --json, "
              f"fed back for up to {ROUNDS} rounds")
        print(f"  then:  velaris audit {out}")
        return 0

    card = CARD.read_text(encoding="utf-8")
    messages = [{"role": "user", "content":
                 f"{card}\n\n---\n\nWrite a Velaris program that does "
                 f"this:\n\n{task}\n\nReturn only the program in one "
                 f"code block. It must pass `velaris check`."}]

    for attempt in range(1, ROUNDS + 1):
        reply = ask_model(messages)
        code = just_the_code(reply)
        out.write_text(code + "\n", encoding="utf-8")
        errors = check(out)
        if not errors:
            proven, promising = proof_state(out)
            print(f"round {attempt}: compiles.", end=" ")
            if promising:
                print(f"{proven} of {promising} promise(s) proven "
                      f"before running.")
            else:
                print("no contracts to prove.")
            print(f"\nwritten to {out}\n")
            subprocess.run([sys.executable, str(VELARIS), "audit",
                            str(out), "--no-cache"], timeout=900)
            return 0
        print(f"round {attempt}: {len(errors)} problem(s), asking again")
        for line in complain(errors).splitlines()[:4]:
            print(f"    {line}")
        messages.append({"role": "assistant", "content": reply})
        messages.append({"role": "user", "content":
                         "`velaris check` reported this. Fix it and "
                         "return the whole program again, only the code "
                         f"block:\n\n{complain(errors)}"})

    print(f"\ngave up after {ROUNDS} rounds. The last attempt is in "
          f"{out}; run `velaris check {out}` to see what remains.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
