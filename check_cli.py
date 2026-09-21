#!/usr/bin/env python3
"""The command line answers for itself.

- `sabline --help`, `sabline -h`, and every command followed by --help or
  -h, print usage and exit 0 with nothing on stderr (8.2). The commands are
  the ones main() dispatches, read from its source, and each must have
  lines in the usage list - so a new command cannot arrive without them.
  An outside functional pass of 8.0.0 found commands that took --help for a
  file name. After `run` or a file, --help is the program's argument.
- `sabline stats --ffi` counts what the audit reads, over a directory of
  known programs made here (8.2).
- A command that proves nothing imports neither z3 nor llvmlite: --version,
  card, fmt, and check of a file with no promises, under python -X
  importtime (8.2 item 22). With the prover installed, a check of a promise
  does import z3 - so the measurement is shown to see it.

    python check_cli.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sabline  # noqa: E402
from suite_dirs import isolate  # noqa: E402

WORK = isolate("check_cli")
SABLINE = [sys.executable, str(HERE / "sabline.py")]

try:
    import z3  # noqa: F401
    HAVE_Z3 = True
except ImportError:
    HAVE_Z3 = False

PASS = FAIL = 0


def ok(label: str, good: bool, detail: str = "") -> None:
    global PASS, FAIL
    if good:
        PASS += 1
        print(f"  ok     {label}")
    else:
        FAIL += 1
        print(f"  WRONG  {label}" + (f"\n         {detail}" if detail else ""))


def sabline_cmd(*args: Any, env: Any = None, cwd: Any = None, python_flags: Any = ()) -> tuple[Any, ...]:
    done = subprocess.run([sys.executable, *python_flags, *SABLINE[1:],
                           *args], capture_output=True, text=True,
                          cwd=str(cwd or WORK), timeout=300,
                          env=dict(os.environ, **(env or {})))
    return done.returncode, done.stdout, done.stderr


def sabline_source() -> str:
    """Sabline's own source: sabline.py, or every module of the package."""
    where = Path(sabline.__file__)
    files = (sorted(where.parent.glob("*.py")) if where.name == "__init__.py"
             else [where])
    return "\n".join(p.read_text(encoding="utf-8") for p in files)


def dispatched() -> set[Any]:
    """Every command main() dispatches on, read from its source."""
    names: set[Any] = set()
    for m in re.finditer(r"argv\[:1\] (?:==|in) (.+)", sabline_source()):
        names |= set(re.findall(r'"([a-z][a-z-]*)"', m.group(1)))
    return names


# Commands deliberately left out of `usage_lines`, each with the reason.
# A command here still answers `--help` for itself: the rule this list
# relaxes is that `sabline --help` advertises it, not that it is
# documented.
UNLISTED = {
    "ast": "the canonical AST dump is a comparison surface for the "
           "agreement gate, not a feature (rt/README.md; 9.0.0-alpha.1)",
}


def help_cases() -> None:
    print("--help, for every command and the top level")
    print("-" * 62)
    commands = dispatched()
    usage = sabline.usage_lines()
    missing = commands - set(usage) - set(UNLISTED)
    ok("main() dispatches commands, and the usage list names every one "
       f"but the {len(UNLISTED)} left out on purpose",
       bool(commands) and not missing,
       f"no usage lines for: {sorted(missing)}")
    ok("...and every command left out of the usage list is one this suite "
       "names, with a reason",
       not set(UNLISTED) - commands,
       f"listed as unlisted but not a command: "
       f"{sorted(set(UNLISTED) - commands)}")
    ok("...and names no command main() does not have",
       not set(usage) - commands, str(sorted(set(usage) - commands)))
    for command, why in sorted(UNLISTED.items()):
        code, out, _ = sabline_cmd("--help")
        ok(f"sabline --help does not advertise {command}: {why}",
           f"sabline {command}" not in out, out[:200])
    for flag in ("--help", "-h"):
        code, out, err = sabline_cmd(flag)
        ok(f"sabline {flag}: usage, exit 0, nothing on stderr",
           code == 0 and "usage:" in out and "sabline check" in out
           and not err.strip(), f"{code} {err[:160]}")
    for command in sorted(commands):
        for flag in ("--help", "-h"):
            code, out, err = sabline_cmd(command, flag)
            ok(f"sabline {command} {flag}: its usage, exit 0",
               code == 0 and out.startswith("usage:")
               and f"sabline {command}" in out and not err.strip(),
               f"exit {code}; stdout {out[:120]!r}; stderr {err[:160]!r}")
    prog = WORK / "args.vel"
    prog.write_text('fn main() uses io {\n    print(args())\n}\n',
                    encoding="utf-8")
    for words in ((str(prog), "--help"), ("run", str(prog), "--help"),
                  ("trace", str(prog), "-h")):
        code, out, err = sabline_cmd(*words)
        ok(f"sabline {' '.join(w if w.startswith('-') or w in ('run', 'trace') else 'args.vel' for w in words)}: "
           f"the flag after a file is the program's argument",
           code == 0 and "usage:" not in out
           and ("--help" in out or "-h" in out), f"{code} {out[:120]!r}")


def stats_cases() -> None:
    print()
    print("sabline stats --ffi")
    print("-" * 62)
    box = WORK / "stats"
    box.mkdir()
    (box / "plain.vel").write_text(
        'fn main() uses io {\n    print("no python")\n}\n', encoding="utf-8")
    (box / "named.vel").write_text(
        'fn main() uses io, ffi {\n'
        '    check py("math", "sqrt", ["16"]) {\n'
        '        ok v { print(v) }\n'
        '        fail w { print(w) }\n    }\n}\n', encoding="utf-8")
    (box / "built.vel").write_text(
        'fn main() uses io, ffi {\n'
        '    let m = "ma" + "th"\n'
        '    check py(m, "sqrt", ["16"]) {\n'
        '        ok v { print(v) }\n'
        '        fail w { print(w) }\n    }\n}\n', encoding="utf-8")
    (box / "nested").mkdir()
    (box / "nested" / "two.vel").write_text(
        'fn main() uses io, ffi {\n'
        '    check py("json", "dumps", ["1"]) {\n'
        '        ok v { print(v) }\n'
        '        fail w { print(w) }\n    }\n'
        '    check py("math", "floor", ["2.5"]) {\n'
        '        ok v { print(v) }\n'
        '        fail w { print(w) }\n    }\n}\n', encoding="utf-8")
    (box / "broken.vel").write_text(BROKEN, encoding="utf-8")
    code, out, err = sabline_cmd("stats", "--ffi", str(box), "--json")
    try:
        doc = json.loads(out)
    except ValueError:
        doc = {}
    ok("stats --ffi --json: five files, one not counted, three call Python",
       code == 0 and doc.get("schema") == "sabline.stats-ffi/1"
       and doc.get("files") == 5 and doc.get("not_counted") == ["broken.vel"]
       and doc.get("needing_ffi") == 3, f"{code} {out[:300]} {err[:200]}")
    grants = {p["file"]: p["grant"] for p in doc.get("programs", [])}
    ok("...two name every module and one builds a module name while running",
       doc.get("scoped") == 2 and doc.get("plain") == 1
       and grants == {"named.vel": "ffi:math", "built.vel": "ffi",
                      "nested/two.vel": "ffi:json,math"}, str(grants))
    ok("...and each module is counted once per program that names it",
       {m: e["programs"] for m, e in doc.get("modules", {}).items()}
       == {"json": 1, "math": 2}, str(doc.get("modules")))
    code, out, _ = sabline_cmd("stats", "--ffi", str(box))
    ok("stats --ffi prints the same counts as text",
       code == 0 and "3 call Python" in out and "ffi:json,math" in out,
       out[:300])
    for words, label in ((("stats", str(box)), "without --ffi"),
                         (("stats", "--ffi", str(box / "nope")),
                          "on a directory that is not there")):
        code, out, err = sabline_cmd(*words)
        ok(f"stats {label}: exit 2, with a line saying why",
           code == 2 and err.strip(), f"{code} {err[:160]}")


BROKEN = 'fn main() {\n    print("no effect declared")\n}\n'


def import_cases() -> None:
    print()
    print("z3 and llvmlite are imported only by what proves or compiles")
    print("-" * 62)
    plain = WORK / "plain.vel"
    plain.write_text('fn main() uses io {\n    print("hi")\n}\n',
                     encoding="utf-8")
    promise = WORK / "promise.vel"
    promise.write_text('fn add1(n: Int) -> Int\n    ensures result == n + 1\n'
                       '{\n    return n + 1\n}\n\n'
                       'fn main() uses io {\n    print(add1(1))\n}\n',
                       encoding="utf-8")

    def imported(*args: Any) -> tuple[Any, ...]:
        code, out, err = sabline_cmd(*args, python_flags=("-X", "importtime"))
        names = {ln.rsplit("|", 1)[-1].strip() for ln in err.splitlines()
                 if ln.startswith("import time:")}
        return code, names

    for label, args in (("--version", ("--version",)),
                        ("card", ("card",)),
                        ("fmt --check", ("fmt", str(plain), "--check")),
                        ("check of a file with no promises",
                         ("check", str(plain), "--no-check-ceiling"))):
        code, names = imported(*args)
        heavy = sorted(n for n in names
                       if n.split(".")[0] in ("z3", "llvmlite"))
        ok(f"{label}: neither z3 nor llvmlite is imported",
           code == 0 and not heavy, f"exit {code}, imported {heavy[:5]}")
    if HAVE_Z3:
        code, names = imported("check", str(promise), "--no-check-ceiling")
        ok("...while a check of a promise does import z3 (the measurement "
           "sees it)", code == 0 and "z3" in {n.split(".")[0] for n in names},
           f"exit {code}")


def main() -> int:
    help_cases()
    stats_cases()
    import_cases()
    print("-" * 62)
    print(f"{PASS} passed, {FAIL} wrong")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
