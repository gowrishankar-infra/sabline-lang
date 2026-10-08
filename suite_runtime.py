"""Which runtime a suite's questions go to (9.0, M2).

    python check_termination.py --runtime rust

plan/9.0.md's M2 holds `check_refusals.py`, `check_secret.py`,
`check_termination.py`, `check_error_messages.py` and `check_fallible.py`
to both runtimes. A suite asks three kinds of question of a program, and
they belong to three different places:

- **what checking it finds** - the checkers', which sabline-rt has from
  M2. Under `--runtime rust` these go to sabline-rt, and its answer is
  held to exactly what the suite holds the Python package's to.
- **what running it does** - the interpreter's, which sabline-rt has from
  M3. Under `--runtime rust` these are not asked yet, and the suite counts
  them by the rung that will ask them.
- **what the prover shows** - the prover's, which stays in the Python
  package for good (decisions/0002: what was proven is an input to a run,
  not something a run works out). Under `--runtime rust` these are not
  asked of sabline-rt at all, and the suite counts them as the prover's.

A suite under `--runtime rust` therefore says three numbers - asked and
right, asked and wrong, and not asked, with why - and passes only when the
second is zero. A question it did not ask is never counted as passed.

`--runtime python` is the default, and is what every suite did before it
had the flag.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent

RUNTIMES = ("python", "rust")

# Why a question is not sent to sabline-rt under --runtime rust, by kind.
NOT_YET = {
    "run": "a run, which sabline-rt does from M3",
    "prover": "the prover's, which stays in the Python package "
              "(decisions/0002)",
    "audit": "an audit, which stays a Python command (decisions/0002)",
    "ceiling": "the check ceiling, a child process the Python package "
               "starts around its own check",
    "import root": "an import root, which sabline-rt's loader takes from "
                   "M3 with the doors",
    "command": "a command other than check, which stays in Python "
               "(decisions/0002)",
}


def chosen(argv: list[str]) -> str:
    """The runtime `--runtime NAME` names in argv, and argv without it."""
    if "--runtime" not in argv:
        return "python"
    at = argv.index("--runtime")
    name = argv[at + 1] if at + 1 < len(argv) else ""
    if name not in RUNTIMES:
        raise SystemExit(f"--runtime takes one of {', '.join(RUNTIMES)}, "
                         f"not {name!r}")
    del argv[at:at + 2]
    return name


def _binary() -> Path:
    """sabline-rt, built if it is not there, exactly as the agreement gate
    finds it - a suite that passed because there was nothing to ask would
    be worse than one that failed."""
    import check_agreement
    return check_agreement.rt_binary()


def check_document(path: str | Path, cwd: str | Path | None = None) -> Any:
    """sabline-rt's check document for the program at `path`, read with the
    shipped standard library where the Python package beside this file
    keeps its own."""
    done = subprocess.run(
        [str(_binary()), "check", "--install-dir", str(ROOT), str(path)],
        capture_output=True, cwd=str(cwd) if cwd else None, timeout=300)
    if done.returncode not in (0, 1):
        raise RuntimeError(
            f"sabline-rt check ended {done.returncode}: "
            f"{done.stderr.decode('utf-8', 'replace')[:2000]}")
    return json.loads(done.stdout)


def check_output(path: str | Path, cwd: str | Path | None = None) -> tuple[int, str]:
    """What `sabline check <path>` answers, from sabline-rt: the exit
    status, and one `file:line: [CODE] message` line per problem, which is
    the form the command prints a problem in."""
    document = check_document(path, cwd)
    lines = [f"{path}:{e['line']}: [{e['code']}] {e['message']}"
             for e in document["errors"]]
    return (1 if document["errors"] else 0), "\n".join(lines)


def library_problems(document: Any) -> list[Any]:
    """The problems `sabline.check` would report for this document, in its
    order: where a stage ended by raising, that one problem alone, and
    otherwise every problem once - which is where the library and the
    command differ (sabline/check_dump.py says why the document holds
    both)."""
    stages = document["stages"]
    raised = document.get("raised")
    if raised == "load":
        return [stages["load"]]
    if raised in ("effects", "types"):
        return [stages[raised][-1]]
    found = ((stages.get("main") or []) + (stages.get("effects") or [])
             + (stages.get("types") or []))
    seen, out = set(), []
    for e in found:
        key = (e["code"], e["file"], e["line"], e["message"])
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


def own_loops(document: Any, path: str | Path) -> list[Any]:
    """The loops of the program at `path` itself, in line order: an import
    brings a library's own functions along, and their loops are not the
    program's."""
    own = os.path.abspath(str(path))
    loops = [lp for lp in document["loops"]
             if os.path.abspath(lp["file"]) == own]
    return sorted(loops, key=lambda lp: lp["line"])


class Tally:
    """What a suite under --runtime rust did not ask, and why."""

    def __init__(self) -> None:
        self.not_asked: dict[str, int] = {}

    def skip(self, kind: str, many: int = 1) -> None:
        self.not_asked[kind] = self.not_asked.get(kind, 0) + many

    def lines(self) -> list[str]:
        return [f"  not asked of sabline-rt: {n} - {NOT_YET[kind]}"
                for kind, n in sorted(self.not_asked.items())]
