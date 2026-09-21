#!/usr/bin/env python3
"""The weekly adversarial pass by other vendors' models (item 30 of 8.2).

adversarial-models.yml runs this between the model and the issue tracker:

    python adversarial_models.py prompt [--focus KEY] > prompt.md
        the standing prompt (.github/adversarial/PROMPT.md) with this
        week's area, which rotates by ISO week through FOCUS
    python adversarial_models.py grok prompt.md [--model M] > grok.out
        Grok, through the xAI API. It has no tools: it is given the prompt
        and the area's files as text, reads them, and runs nothing
    python adversarial_models.py findings claude claude.out --out DIR
        one Markdown issue body per finding in a model's answer, for
        open_issues.py; an answer with no readable findings block becomes
        one issue saying so, with the answer's end attached

Nothing here changes the repository. The model keys are read from the
environment only by `grok`, to call the API, and by `findings`, to strike
any key out of what it writes.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PROMPT = HERE / ".github" / "adversarial" / "PROMPT.md"
KEYS = ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "XAI_API_KEY")
MODELS = ("claude", "gemini", "grok")
XAI_URL = "https://api.x.ai/v1/chat/completions"
FOCUS: list[tuple[str, str, list[str]]] = [
    ("gate", "the release gate and the kill switch",
     ["release_checks.py", ".github/workflows/release.yml", "RELEASING.md"]),
    ("budget", "effect budgets: how a grant is parsed, held and enforced",
     ["sabline/budget.py", "sabline/effects.py"]),
    ("prover", "the prover: what is reported proven",
     ["sabline/prover.py", "sabline/termination.py"]),
    ("native", "native code: whether it keeps every rule the interpreter keeps",
     ["sabline/native.py", "sabline/runtime.py"]),
    ("imports", "imports, the loader and the import root",
     ["sabline/loader.py", "sabline/project.py"]),
    ("doors", "the doors: the MCP server, the HTTP door and the worker pool",
     ["sabline/doors.py", "sabline/pool.py", "sabline_mcp.py"]),
    ("secret", "Secret of T and declassify: what can reach an output",
     ["sabline/wrappers.py", "sabline/checker.py"]),
    ("reports", "the audit, SARIF, receipts and attestations",
     ["sabline/library.py", "sabline/receipts.py", "sabline/attestation.py",
      "sabline/findings.py"]),
    ("cli", "the command line: flags, arguments and the check ceiling",
     ["sabline/cli.py", "sabline/eject.py"]),
]
PER_FILE = 150_000
FENCE = re.compile(r"```json\s*\n(.*?)\n\s*```", re.S)


def version() -> str:
    found = re.search(r'^VERSION = "([^"]+)"',
                      (HERE / "sabline" / "version.py").read_text(encoding="utf-8"),
                      re.M)
    return found.group(1) if found else "(unknown)"


def this_week(key: str | None) -> tuple[str, str, list[str]]:
    if key:
        for item in FOCUS:
            if item[0] == key:
                return item
        sys.exit(f"adversarial_models: no area {key!r}; the areas are "
                 + ", ".join(k for k, _, _ in FOCUS))
    week = datetime.date.today().isocalendar()[1]
    return FOCUS[week % len(FOCUS)]


def prompt(key: str | None) -> str:
    _, title, files = this_week(key)
    return (PROMPT.read_text(encoding="utf-8")
            .replace("{version}", version())
            .replace("{focus_title}", title)
            .replace("{focus_files}", ", ".join(f"`{f}`" for f in files)))


def scrub(text: str) -> str:
    """No key in anything written, and no @mention that pings anyone."""
    for name in KEYS:
        value = os.environ.get(name, "")
        if len(value) >= 8:
            text = text.replace(value, f"[{name} struck out]")
    return re.sub(r"@(?=[A-Za-z0-9-])", "@​", text)


def grok(prompt_file: str, model: str) -> int:
    key = os.environ.get("XAI_API_KEY", "")
    if not key:
        print("XAI_API_KEY is not set", file=sys.stderr)
        return 3
    text = Path(prompt_file).read_text(encoding="utf-8")
    focus = re.search(r"Start from: (.*?)\. Follow", text)
    names = re.findall(r"`([^`]+)`", focus.group(1)) if focus else []
    names += ["SECURITY.md", "THREAT_MODEL.md"]
    given = []
    for name in names:
        path = HERE / name
        if path.is_file():
            body = path.read_text(encoding="utf-8", errors="replace")[:PER_FILE]
            given.append(f"===== {name} =====\n{body}")
    request = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": text + (
                "\n\nYou have no tools in this pass and cannot run anything: "
                "every finding's confidence is `unreproduced`, and its "
                "reproduction is the program or command a person should run.")},
            {"role": "user", "content": "The files named above, as they are "
             "in this checkout:\n\n" + "\n\n".join(given)},
        ],
    }
    req = urllib.request.Request(XAI_URL, data=json.dumps(request).encode(),
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=1800) as response:
            answer = json.load(response)
    except urllib.error.HTTPError as e:
        print(f"the xAI API answered HTTP {e.code}: "
              f"{scrub(e.read().decode('utf-8', 'replace'))[:500]}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, OSError) as e:
        print(f"the xAI API could not be reached: {e}", file=sys.stderr)
        return 1
    print(answer["choices"][0]["message"]["content"])
    return 0


def read_findings(answer: str) -> list[dict[str, Any]] | None:
    """The findings in the last json block of an answer, or None."""
    blocks = FENCE.findall(answer)
    if not blocks:
        return None
    try:
        found = json.loads(blocks[-1])
    except json.JSONDecodeError:
        return None
    if not isinstance(found, list) or not all(isinstance(f, dict) for f in found):
        return None
    return found


def findings(model: str, answer_file: str, out: str) -> int:
    answer = Path(answer_file).read_text(encoding="utf-8", errors="replace") \
        if Path(answer_file).is_file() else ""
    where = Path(out)
    where.mkdir(parents=True, exist_ok=True)
    found = read_findings(answer)
    if found is None:
        (where / "00-unreadable.md").write_text(scrub(
            f"# [{model}] the weekly adversarial answer had no findings block\n\n"
            f"The answer did not end with a json list of findings, so nothing "
            f"in it was opened as an issue of its own. Its last part:\n\n"
            f"```text\n{answer[-20000:].replace('```', chr(39) * 3)}\n```\n"),
            encoding="utf-8")
        print(f"{model}: no readable findings block")
        return 0
    for i, f in enumerate(found, 1):
        title = " ".join(str(f.get("title") or "untitled").split())[:200]
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
        repro = str(f.get("reproduction", "")).replace("```", "'''")
        body = (f"# [{model}] {title}\n\n"
                f"- goal: {f.get('goal', 'other')}\n"
                f"- where: {f.get('where', 'not said')}\n"
                f"- confidence: {f.get('confidence', 'unreproduced')}\n\n"
                f"## Reproduction\n\n```text\n{repro}\n```\n\n"
                f"## Expected\n\n{f.get('expected', '')}\n\n"
                f"## Observed\n\n{f.get('observed', '')}\n\n"
                f"Reported by {model} in the weekly adversarial pass "
                f"(adversarial-models.yml). Unconfirmed until a person "
                f"reproduces it.\n")
        (where / f"{i:02d}-{slug or 'finding'}.md").write_text(
            scrub(body), encoding="utf-8")
    print(f"{model}: {len(found)} finding(s)")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prompt")
    p.add_argument("--focus", help="an area key; default: this week's")
    g = sub.add_parser("grok")
    g.add_argument("prompt_file")
    g.add_argument("--model", default="grok-4")
    f = sub.add_parser("findings")
    f.add_argument("model", choices=MODELS)
    f.add_argument("answer_file")
    f.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    if args.command == "prompt":
        sys.stdout.write(prompt(args.focus))
        return 0
    if args.command == "grok":
        return grok(args.prompt_file, args.model)
    return findings(args.model, args.answer_file, args.out)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
