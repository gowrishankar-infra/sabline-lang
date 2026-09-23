#!/usr/bin/env python3
"""The evidence under each incident, recorded from real runs.

    python incident_evidence.py               run every entry's steps, report
    python incident_evidence.py --write       and write refusal.txt and the
                                              receipts beside each entry
    python incident_evidence.py <slug> ...    only these entries

An entry under incidents/ with a verdict of STOPPED or PARTIAL carries a
`run.json` (`sabline.incident-run/1`) naming the steps that show it. A step
is a command - `sabline` is this checkout's `sabline.py`, `python` is the
interpreter running this - with the files it needs written first, what it
must exit with, and the text that must and must not be in what it printed.
That last one matters: a step whose point is that a credential did not
leave names the credential in `expect_absent`.

A step may name `platforms` (e.g. `["linux"]`): it runs, and is checked,
only on an operating system it names, and is held to its `expect`,
`expect_exit` and `expect_absent` alone - never a byte recording, so it
carries no `receipt` and its output stays out of `refusal.txt`. That is how
a refusal the kernel makes on one operating system, and not on another, is
evidence here without making `refusal.txt` differ from machine to machine.

Each entry runs in a scratch directory of its own, a copy of the entry's
own directory, so nothing here writes into the repository and a `.env` a
step needs is never a file this repository holds. The steps of one entry
share that directory, in order, which is how a step can change a library
under a later one.

WHAT IS NORMALISED. `refusal.txt` and the receipts are what the command
printed and wrote, with the substitutions incidents/README.md lists: the
scratch directory and this checkout become `.` and a backslash becomes a
forward slash, the Sabline and specification versions become `<version>`,
the receipt's `startedAt` and `wall_time_ms` become `<varies>`, and its
`confinement`, `confinement_reason`, `confinement_layers` and
`os_policy_sha256` become `<varies by operating system>` - the kernel holds
a different amount on Linux, macOS and Windows, and a recording made on one
must not read as a claim about another - and the note Sabline prints when
z3-solver is not installed is dropped, because whether an optional
dependency is present is a fact about the machine, not about the program,
and half of test.yml's legs run without it. Nothing else is edited.

check_incidents.py runs this in the mode that changes nothing, on every
push, so an entry that stops refusing - because a refusal moved, a code
changed, or a budget got wider - fails the build before a release is made
from that tree. build_incidents.py reads the same entries to write
docs/incidents.md.

It is not part of Sabline: the wheel includes only what pyproject.toml
names.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parent
INCIDENTS = ROOT / "incidents"
SCHEMA = "sabline.incident-run/1"
# receipt fields that are not the same twice, or not the same on two
# operating systems; incidents/README.md says so, and so does the page
VARIES = ("startedAt", "wall_time_ms")
OS_VARIES = ("confinement", "confinement_reason", "confinement_layers",
             "os_policy_sha256")
# printed on stderr by a run whose program has promises to prove, only on a
# machine without z3-solver (sabline/prover.py); the `deps: minimal` legs of
# test.yml are such machines
Z3_NOTE = re.compile(r"^note: z3-solver is not installed, so promises are "
                     r"checked while running instead of proven beforehand "
                     r"\(install with: pip install z3-solver\)\n",
                     re.MULTILINE)


def sabline_command() -> list[str]:
    """This checkout's launcher when there is one, else the installed
    command - the same rule examples/runner/host.py uses."""
    launcher = ROOT / "sabline.py"
    if launcher.exists():
        return [sys.executable, str(launcher)]
    return [sys.executable, "-m", "sabline"]


def entries() -> list[Path]:
    """Every entry directory, by name."""
    return sorted(p for p in INCIDENTS.iterdir()
                  if p.is_dir() and (p / "incident.md").exists())


def front_matter(path: Path) -> dict[str, str]:
    """The `key: value` block between the first two `---` lines. A small
    reader on purpose: this runs where PyYAML is not installed."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        raise ValueError(f"{path} does not open with a --- frontmatter block")
    end = text.find("\n---\n", 3)
    if end < 0:
        raise ValueError(f"{path}'s frontmatter block is not closed")
    found: dict[str, str] = {}
    for line in text[4:end].replace("\r\n", "\n").split("\n"):
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"{path}: frontmatter line without a key: {line}")
        key, _, value = line.partition(":")
        found[key.strip()] = value.strip()
    return found


def body(path: Path) -> str:
    """Everything after the frontmatter block."""
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    return text[text.find("\n---\n", 3) + 5:].lstrip("\n")


def version() -> str:
    """The Sabline this checkout is, which some commands print."""
    sys.path.insert(0, str(ROOT))
    import sabline
    return str(sabline.VERSION)


def normalise(text: str, work: Path) -> str:
    """What a run printed, written so the same bytes come out on every
    machine: the scratch directory and this checkout, however the platform
    spells them, as `.`; the running version as `<version>`; a backslash as
    a forward slash, so a path recorded on Windows reads as one recorded on
    Linux; line endings as line feeds; and the note that z3-solver is not
    installed, dropped."""
    text = text.replace("\r\n", "\n").replace(version(), "<version>")
    text = Z3_NOTE.sub("", text)
    text = re.sub(r"sabline-spec \d+\.\d+\.\d+", "sabline-spec <version>",
                  text)
    spellings = set()
    for base in (work, Path(os.path.realpath(work)),
                 ROOT, Path(os.path.realpath(ROOT))):
        for form in (str(base), str(base).replace("\\", "/")):
            for spelling in (form, form.lower()):
                spellings.add(spelling)
                # the same path inside a JSON string, where every separator
                # is written twice
                spellings.add(spelling.replace("\\", "\\\\"))
    for spelling in sorted(spellings, key=len, reverse=True):
        text = text.replace(spelling, ".")
    # what is left of a Windows path: `.\stdlib\db.vel`
    return text.replace("\\", "/")


def normalise_receipt(receipt: dict[str, Any], work: Path) -> dict[str, Any]:
    """The receipt with what varies replaced, and its paths normalised. The
    strings are normalised where they are, not in the JSON text, so that
    turning a backslash into a forward slash cannot touch an escape."""
    def walk(value: Any) -> Any:
        if isinstance(value, str):
            return normalise(value, work)
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items()}
        if isinstance(value, list):
            return [walk(v) for v in value]
        return value

    out = cast("dict[str, Any]", walk(receipt))
    predicate = out.get("predicate", {})
    for key in VARIES:
        if key in predicate:
            predicate[key] = "<varies>"
    parameters = predicate.get("run_parameters", {})
    for key in OS_VARIES:
        if key in parameters:
            parameters[key] = "<varies by operating system>"
    return out


def argv_of(step: dict[str, Any]) -> list[str]:
    """A step's command, with `sabline` and `python` resolved."""
    given = [str(part) for part in step["command"]]
    if given[0] == "sabline":
        return sabline_command() + given[1:]
    if given[0] == "python":
        return [sys.executable] + given[1:]
    return given


def run_entry(entry: Path, write: bool) -> tuple[bool, list[str]]:
    """Run one entry's steps. Returns (it held, what went wrong)."""
    plan = json.loads((entry / "run.json").read_text(encoding="utf-8"))
    if plan.get("schema") != SCHEMA:
        return False, [f"run.json is not {SCHEMA}"]
    wrong: list[str] = []
    blocks: list[str] = []
    work = Path(tempfile.mkdtemp(prefix=f"sabline-incident-{entry.name}-"))
    try:
        for source in entry.iterdir():
            if source.is_file():
                shutil.copy2(source, work / source.name)
        for step in plan["steps"]:
            platforms = step.get("platforms")
            if platforms and not any(sys.platform.startswith(p)
                                     for p in platforms):
                # a platform-scoped step runs, and is checked, only where it
                # can be: the operating system it names is the point (a Linux
                # confinement refusal reads differently on macOS and Windows).
                # It is held to expect/expect_exit/expect_absent alone and is
                # recorded nowhere, so refusal.txt stays the same bytes on
                # every machine (incidents/README.md).
                continue
            said, problems = run_step(entry, step, work, write)
            if not platforms:
                blocks.append(f"# {step['name']}\n{said}")
            wrong += problems
    finally:
        shutil.rmtree(work, ignore_errors=True)
    wrong += hold(entry / "refusal.txt", "\n".join(blocks), write, entry.name)
    return not wrong, wrong


def run_step(entry: Path, step: dict[str, Any], work: Path,
             write: bool) -> tuple[str, list[str]]:
    """One step: write its files, run it, hold it to what it must print.
    Returns (what it printed, what went wrong)."""
    name = step["name"]
    wrong: list[str] = []
    for path, content in step.get("setup", {}).items():
        target = work / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
    for path, source in step.get("copy", {}).items():
        target = work / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(work / source, target)
    argv = argv_of(step)
    shown = [str(part) for part in step["command"]]
    receipt_name = step.get("receipt")
    if receipt_name:
        argv = argv + ["--receipt", str(work / "receipt-out.json")]
        shown = shown + ["--receipt", receipt_name]
    # a step that exercises something this repository already ships -
    # examples/runner, say - runs from the repository, not from the copy
    where = ROOT if step.get("in_repo") else work
    # a step that is a Python script of its own - one that has to drive a
    # protocol rather than run a command - is told how to start Sabline,
    # since it runs from a scratch directory with no checkout above it
    passed = {"SABLINE_COMMAND": json.dumps(sabline_command()),
              **step.get("env", {})}
    done = subprocess.run(argv, cwd=where, capture_output=True,
                          stdin=subprocess.DEVNULL, timeout=600,
                          env={**os.environ, **passed})
    # standard output first and standard error after, because a pipe does
    # not keep the order they were written in
    printed = normalise(
        f"$ {' '.join(shown)}\n"
        + done.stdout.decode("utf-8", "replace")
        + done.stderr.decode("utf-8", "replace")
        + f"exit {done.returncode}\n", work)

    if done.returncode != step["expect_exit"]:
        wrong.append(f"{name}: exit {done.returncode}, not "
                     f"{step['expect_exit']}\n{printed}")
    for must in step.get("expect", []):
        if must not in printed:
            wrong.append(f"{name}: {must!r} is not in what it printed\n"
                         f"{printed}")
    for must_not in step.get("expect_absent", []):
        if must_not in printed:
            wrong.append(f"{name}: {must_not!r} IS in what it printed - "
                         f"something left that should not have\n{printed}")

    if receipt_name:
        out = work / "receipt-out.json"
        if not out.exists():
            wrong.append(f"{name}: no receipt was written")
        else:
            receipt = normalise_receipt(
                json.loads(out.read_text(encoding="utf-8")), work)
            wrong += hold(entry / receipt_name,
                          json.dumps(receipt, indent=2) + "\n", write, name)
            out.unlink()
    return printed, wrong


def hold(path: Path, text: str, write: bool, name: str) -> list[str]:
    """Write the recording, or hold what is recorded to what just
    happened."""
    if write:
        path.write_text(text, encoding="utf-8", newline="\n")
        return []
    if not path.exists():
        return [f"{name}: {path.name} has not been recorded "
                f"(python incident_evidence.py --write)"]
    was = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if was != text:
        return [f"{name}: {path.name} is not what this run produced\n"
                f"--- recorded ---\n{was}\n--- now ---\n{text}"]
    return []


def main(argv: list[str]) -> int:
    write = "--write" in argv
    only = [a for a in argv if not a.startswith("--")]
    chosen = [e for e in entries() if not only or e.name in only]
    if only and len(chosen) != len(only):
        missing = sorted(set(only) - {e.name for e in chosen})
        print(f"no such entry: {', '.join(missing)}")
        return 2
    ran = held = 0
    problems: list[str] = []
    for entry in chosen:
        meta = front_matter(entry / "incident.md")
        if not (entry / "run.json").exists():
            if meta["verdict"] in ("STOPPED", "PARTIAL"):
                problems.append(f"{entry.name}: {meta['verdict']} with no "
                                f"run.json - a verdict of STOPPED or "
                                f"PARTIAL needs a program that refuses")
            continue
        ran += 1
        ok, wrong = run_entry(entry, write)
        if ok:
            held += 1
            print(f"  ok       {entry.name}  ({meta['verdict']})")
        else:
            print(f"  WRONG    {entry.name}  ({meta['verdict']})")
            problems += [f"{entry.name}: {w}" for w in wrong]
    print("-" * 62)
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} problem(s); {held} of {ran} entries held")
        return 1
    print(f"all {held} entries with a program behave as their entry says"
          + (" (recorded)" if write else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
