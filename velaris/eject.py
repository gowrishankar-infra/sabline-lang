"""velaris eject: a directory that runs with nothing from this project.
"""
import json
import os
import sys

from .version import VERSION, _INSTALL_DIR, _PACKAGE_DIR
from .errors import VelarisError
from .tables import ALLOW_ALL, HAVE_Z3
from .loader import _stdlib_dir, load_program
from .budget import Budget, BudgetError, expand_allow, warn_allow_all
from .editor import inspect_source
from .library import _audit_here, _safe_grants
from .findings import REPOSITORY
from typing import Any

# ---------------------------------------------------------------------------
# 21. EJECT - a program that keeps running with nothing from this project
#
#     `velaris eject program.vel` writes a directory that runs, and builds
#     into one executable, with nothing fetched from here: the program and
#     the libraries it imports, the runtime that enforces its budget (this
#     file, copied, and the standard library files the program uses), a
#     launcher whose budget is fixed at eject time, a pinned requirements
#     file, and a README that says what holds once ejected and what does
#     not. The budget is enforced by the copied runtime, whatever the
#     program says. The proofs are a record of what this Velaris proved at
#     eject time, which nothing trusts when the program runs, and which
#     `main.py --prove` runs again.
# ---------------------------------------------------------------------------


EJECT_SCHEMA = "velaris.eject/1"

_EJECT_LAUNCHER = r'''#!/usr/bin/env python3
"""@NAME@: a Velaris program, ejected by Velaris @VERSION@ on @DATE@.

    python -I main.py [arguments]    run it, under the budget below
    python -I main.py --prove        check its promises again
    python build.py                  one executable, with PyInstaller

README.md says what holds once ejected, and what does not.
"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# a PyInstaller build unpacks these files beside a temporary launcher
BASE = getattr(sys, "_MEIPASS", HERE)

ENTRY = @ENTRY@
# the budget the program runs under, fixed when it was ejected
BUDGET = @BUDGET@
# the sha256 of every file this launcher runs, when it was ejected
FILES = @FILES@


def changed():
    """The files that are not what was ejected."""
    wrong = []
    for rel, want in sorted(FILES.items()):
        try:
            with open(os.path.join(BASE, *rel.split("/")), "rb") as fh:
                got = hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            got = None
        if got != want:
            wrong.append(rel)
    return wrong


def writes_here(velaris):
    """Why the budget lets the program write into this directory - where
    one run could change the launcher, the runtime or the program the next
    run uses - or None."""
    budget = velaris.Budget.parse(BUDGET or "''")
    if "fs" not in budget.effects:
        return None
    if budget.fs is None:
        return "plain fs writes anywhere"
    here = os.path.normcase(os.path.realpath(BASE))
    for kind, prefix in budget.fs:
        if kind != "write":
            continue
        if prefix is None:
            return "fs:write names no path"
        if (here == prefix or here.startswith(prefix.rstrip(os.sep) + os.sep)
                or prefix.startswith(here.rstrip(os.sep) + os.sep)):
            return "fs:write:" + prefix + " reaches " + here
    return None


def writes_where_python_imports(velaris):
    """Why the budget lets the program write into a directory Python
    imports from - a PYTHONPATH entry, a site-packages, the user's site -
    where a sitecustomize.py or a module one run leaves is code the next
    Python process runs, or None. PYTHONPATH counts under -I too: the next
    Python may be started without it."""
    import site
    budget = velaris.Budget.parse(BUDGET or "''")
    if "fs" not in budget.effects or budget.fs is None:
        return None
    places = [p for p in sys.path if p]
    places += [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep)
               if p]
    for more in (getattr(site, "getusersitepackages", None),
                 getattr(site, "getsitepackages", None)):
        try:
            got = more() if more else []
            places += [got] if isinstance(got, str) else list(got)
        except Exception:
            pass
    for place in places:
        real = os.path.normcase(os.path.realpath(place))
        for kind, prefix in budget.fs:
            if kind != "write" or prefix is None:
                continue
            if (real == prefix or real.startswith(prefix.rstrip(os.sep) + os.sep)
                    or prefix.startswith(real.rstrip(os.sep) + os.sep)):
                return "fs:write:" + prefix + " reaches " + real
    return None


def main(argv):
    prove = "--prove" in argv
    changed_ok = "--changed-ok" in argv
    rest = [a for a in argv if a not in ("--prove", "--changed-ok")]
    for a in rest:
        if a.split("=", 1)[0] in ("--allow", "--deny"):
            print("the budget is fixed at eject time (" + (BUDGET or "nothing")
                  + "); change BUDGET in main.py to change it",
                  file=sys.stderr)
            return 2
    wrong = changed()
    runtime_changed = [w for w in wrong if not w.startswith("program/")]
    if runtime_changed:
        # the runtime is what enforces the budget: a changed one is never run
        print("these files are not what was ejected: "
              + ", ".join(runtime_changed) + ". They are the runtime that "
              "enforces the budget, so nothing runs them, --changed-ok "
              "included.", file=sys.stderr)
        return 2
    if wrong and not changed_ok:
        print("these files are not what was ejected: " + ", ".join(wrong)
              + ". Pass --changed-ok to run the changed program anyway; "
              "the runtime is unchanged and still holds it to the budget.",
              file=sys.stderr)
        return 2
    if "--receipt" in rest:
        at = rest.index("--receipt")
        target = rest[at + 1] if at + 1 < len(rest) else ""
        real = os.path.normcase(os.path.realpath(target))
        here = os.path.normcase(os.path.realpath(BASE))
        if real == here or real.startswith(here.rstrip(os.sep) + os.sep):
            print("refused: --receipt names a file in this directory, where "
                  "it would replace what the next run is", file=sys.stderr)
            return 2
    runtime = os.path.join(BASE, "runtime")
    sys.path.insert(0, runtime)
    import velaris
    if os.path.normcase(os.path.dirname(os.path.dirname(
            os.path.abspath(velaris.__file__)))) \
            != os.path.normcase(os.path.abspath(runtime)):
        print("refused: velaris was imported from " + velaris.__file__
              + ", not from this directory's runtime/", file=sys.stderr)
        return 2
    reach = writes_here(velaris)
    if reach:
        print("refused: the budget " + BUDGET + " lets the program write "
              "into this directory (" + reach + "), where one run could "
              "change what the next one runs", file=sys.stderr)
        return 2
    reach = writes_where_python_imports(velaris)
    if reach:
        print("refused: the budget " + BUDGET + " lets the program write "
              "where Python imports from (" + reach + "): a file one run "
              "leaves there is code the next Python process runs",
              file=sys.stderr)
        return 2
    entry = os.path.join(BASE, *ENTRY.split("/"))
    if prove:
        sys.argv = [velaris.__file__, "check", entry]
        if getattr(sys, "frozen", False):
            sys.argv.append("--no-check-ceiling")
        return velaris.main()
    sys.argv = [velaris.__file__, entry, "--allow", BUDGET or "''"] + rest
    return velaris.main()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''

_EJECT_BUILD = r'''#!/usr/bin/env python3
"""One executable of this program, built with PyInstaller:

    pip install pyinstaller
    python build.py            (python build.py --print shows the command)

It carries main.py, runtime/ and program/, checks their digests and holds
the program to its budget as main.py does. Add --collect-all z3 and
--collect-all llvmlite to the command when those are installed and should
travel inside it.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = @NAME@


def main():
    sep = ";" if os.name == "nt" else ":"
    cmd = [sys.executable, "-m", "PyInstaller", "--onefile", "--noconfirm",
           "--name", NAME,
           "--add-data", "runtime" + sep + "runtime",
           "--add-data", "program" + sep + "program",
           "main.py"]
    if "--print" in sys.argv:
        print(" ".join(cmd))
        return 0
    return subprocess.call(cmd, cwd=HERE)


if __name__ == "__main__":
    sys.exit(main())
'''

_EJECT_README = """# @NAME@, ejected from Velaris

This directory is `@ENTRY@` and everything it needs to run, taken out of
Velaris @VERSION@ on @DATE@ by `velaris eject`. Nothing in it fetches
anything, and it does not need Velaris installed.

    python -I main.py [arguments]      run it
    python -I main.py --prove          check its promises again
    python build.py                    one executable (needs PyInstaller)
    pip install -r requirements.txt    optional: the prover, native code

`-I` keeps Python from reading `PYTHONPATH`, the user's site-packages and
the current directory before this directory's own files.

## What is here

| Path | What it is |
|---|---|
| `main.py` | the launcher: checks the files, fixes the budget, runs the program |
| `runtime/velaris/` | the Velaris @VERSION@ compiler and runtime, unchanged |
| `runtime/stdlib/` | the standard library files the program imports |
| `program/` | the program, and the libraries it imports |
| `proofs.json` | what Velaris @VERSION@ proved when the program was ejected |
| `requirements.txt` | the prover and the native compiler, pinned to what was installed |
| `build.py` | the PyInstaller command for one executable |
| `SHA256SUMS` | the sha256 of every other file here |
| `LICENSE` | Velaris's licence, which covers `runtime/` |

## What holds once ejected

- **The budget is enforced.** The program runs under `@BUDGET@` whatever
  its source declares, checked by `runtime/velaris/` at the moment each
  effect is attempted - the check `velaris program.vel --allow @BUDGET@`
  makes. An effect outside it stops the program, which cannot catch that.
  The budget is written in `main.py`, and `main.py` refuses `--allow` and
  `--deny` on its command line.
- **A changed file is noticed.** `main.py` holds the sha256 of every file
  in `runtime/` and `program/` from eject time and will not run if one
  differs. `--changed-ok` runs a changed program anyway, still under the
  budget; a changed runtime - the part that enforces the budget - is never
  run.
- **A run cannot rewrite the next one.** `main.py` refuses a budget that
  lets the program write into this directory, or into a directory Python
  imports from where it is launched - a `PYTHONPATH` entry, a
  site-packages - where a file left behind is code the next Python runs.

## What does not

- **The proofs are a record, not a promise.** `proofs.json` says what
  Velaris @VERSION@ proved when the program was ejected (@PROVER@). Nothing
  reads it when the program runs: each run proves the promises again when
  z3-solver is installed and checks them while running when it is not.
  `python -I main.py --prove` runs the check and says what is proven now.
- **No fix arrives.** `runtime/velaris/` is Velaris @VERSION@ and stays
  that. A later Velaris that closes a hole does not reach this directory;
  eject again to take it.
- **`main.py` does not check itself.** A changed `main.py` can skip its own
  checks. If anything but you could have written here, compare every file
  with `SHA256SUMS` first: `sha256sum -c SHA256SUMS` on Linux,
  `shasum -a 256 -c SHA256SUMS` on macOS.
- **What Velaris does not defend against**, it does not defend against
  here either (THREAT_MODEL.md in the Velaris repository): a granted `ffi`
  module does what it does; nothing bounds how long the program runs or
  how much memory it takes unless you run it under limits; and the budget
  is enforced by an interpreter, not by the operating system.
"""


def _eject_write_reach(budget: "Budget", out: str) -> str | None:
    """Why `budget` lets a program write into `out`, or None."""
    if "fs" not in budget.effects:
        return None
    if budget.fs is None:
        return "plain fs writes anywhere"
    here = os.path.normcase(os.path.realpath(out))
    for kind, prefix in budget.fs:
        if kind != "write":
            continue
        if prefix is None:
            return "fs:write names no path"
        if (here == prefix or here.startswith(prefix.rstrip(os.sep) + os.sep)
                or prefix.startswith(here.rstrip(os.sep) + os.sep)):
            return f"fs:write:{prefix} reaches {here}"
    return None


def _velaris_license() -> str:
    """This project's licence text, to travel with the copied runtime."""
    here = _INSTALL_DIR
    for where in (os.path.join(here, "LICENSE"),
                  os.path.join(here, "..", "LICENSE")):
        if os.path.isfile(where):
            with open(where, encoding="utf-8") as fh:
                return fh.read()
    try:
        from importlib import metadata
        dist = metadata.distribution("velaris-lang")
        for f in dist.files or []:
            if os.path.basename(str(f)).upper().startswith("LICENSE"):
                return f.read_text(encoding="utf-8")
    except Exception:
        pass
    return ("Velaris is released under the MIT License:\n"
            f"{REPOSITORY}/blob/main/LICENSE\n")


def eject_main(argv: list[Any]) -> int:
    """velaris eject <program.vel> [-o DIR] [--allow GRANTS] [--force]"""
    import datetime
    import hashlib
    import shutil
    usage = ("usage: velaris eject <program.vel> [-o DIR] [--allow GRANTS] "
             "[--force]")
    places, out, allow, force = [], None, None, False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-o", "--output", "--allow") and i + 1 < len(argv):
            if a == "--allow":
                allow = argv[i + 1]
            else:
                out = argv[i + 1]
            i += 2
            continue
        if a == "--force":
            force = True
        elif a.startswith("-"):
            print(usage, file=sys.stderr)
            return 2
        else:
            places.append(a)
        i += 1
    if len(places) != 1 or not places[0].endswith(".vel"):
        print(usage, file=sys.stderr)
        return 2
    entry = places[0]
    if not os.path.isfile(entry):
        print(f"velaris eject: no such file: {entry}", file=sys.stderr)
        return 2
    with open(entry, encoding="utf-8") as fh:
        source = fh.read()
    report = _audit_here(source, path=entry)
    if not report.ok:
        print(f"velaris eject: {entry} does not compile, so it was not "
              f"ejected:", file=sys.stderr)
        for prob in report.problems[:5]:
            print(f"  line {prob.line}: [{prob.code}] {prob.message}", file=sys.stderr)
        return 1
    if allow is None:
        budget_text = ",".join(_safe_grants(
            report.effects, report.ffi_modules,
            {"read": report.fs_paths["read"],
             "write": report.fs_paths["write"],
             "read_any": report.fs_paths["read_any"],
             "write_any": report.fs_paths["write_any"]},
            {"hosts": report.net_hosts["hosts"],
             "any": report.net_hosts["any"]}))
        chosen = "from its audit; --allow to choose another"
    else:
        if allow.strip() == ALLOW_ALL:
            warn_allow_all("velaris eject")
        budget_text = expand_allow(allow)
        chosen = "as --allow said"
    try:
        budget = Budget.parse(budget_text or "''")
    except BudgetError as e:
        print(f"velaris eject: --allow: {e}", file=sys.stderr)
        return 2
    stem = os.path.splitext(os.path.basename(entry))[0]
    out = out or f"{stem}-ejected"
    reach = _eject_write_reach(budget, out)
    if reach:
        print(f"velaris eject: refused: the budget {budget_text} lets the "
              f"program write into {out} ({reach}), where one run could "
              f"change the launcher, the runtime or the program the next "
              f"run uses. Eject somewhere the program cannot write, or "
              f"narrow the budget.", file=sys.stderr)
        return 2

    # which files it loads, and where each goes
    read: list[Any] = []
    load_program(entry, loaded=read)
    std = _stdlib_dir()
    mine: list[str] = []
    shipped: list[str] = []
    seen: set[str] = set()
    for p in read:
        real = os.path.normcase(os.path.realpath(p))
        if real in seen:
            continue
        seen.add(real)
        (shipped if real.startswith(std + os.sep) else mine).append(
            os.path.abspath(p))
    try:
        base = os.path.commonpath([os.path.dirname(p) for p in mine])
    except ValueError:
        print("velaris eject: the program's files are on different drives, "
              "so they cannot keep their places relative to each other",
              file=sys.stderr)
        return 2

    if os.path.exists(out):
        ours = False
        try:
            with open(os.path.join(out, "proofs.json"),
                      encoding="utf-8") as fh:
                ours = json.load(fh).get("schema") == EJECT_SCHEMA
        except (OSError, ValueError, AttributeError):
            ours = False
        if not (os.path.isdir(out) and not os.listdir(out)):
            if not (force and ours):
                print(f"velaris eject: {out} already exists"
                      + ("; --force replaces it" if ours else
                         " and was not made by velaris eject; choose "
                         "another -o"), file=sys.stderr)
                return 2
            shutil.rmtree(out)
    os.makedirs(os.path.join(out, "runtime", "stdlib"), exist_ok=True)

    placed: dict[Any, Any] = {}                 # published path -> source file
    for p in mine:
        placed["program/" + os.path.relpath(p, base).replace(os.sep, "/")] = p
    for p in shipped:
        placed["runtime/stdlib/" + os.path.basename(p)] = p
    for name in sorted(os.listdir(_PACKAGE_DIR)):
        if name.endswith(".py"):
            placed[f"runtime/velaris/{name}"] = os.path.join(
                _PACKAGE_DIR, name)
    for rel, src in placed.items():
        target = os.path.join(out, *rel.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(src, target)
    new_entry = "program/" + os.path.relpath(
        os.path.abspath(entry), base).replace(os.sep, "/")

    # the copy must load only from inside itself: an import written as an
    # absolute path would still reach the original
    again: list[Any] = []
    try:
        load_program(os.path.join(out, *new_entry.split("/")), loaded=again)
    except VelarisError as e:
        shutil.rmtree(out, ignore_errors=True)
        print(f"velaris eject: the copy does not load: [{e.code}] "
              f"{e.message}", file=sys.stderr)
        return 1
    top = os.path.normcase(os.path.realpath(out))
    outside = [p for p in again if not os.path.normcase(os.path.realpath(p))
               .startswith(top + os.sep)
               and not os.path.normcase(os.path.realpath(p))
               .startswith(std + os.sep)]
    if outside:
        shutil.rmtree(out, ignore_errors=True)
        print(f"velaris eject: the program imports {outside[0]} by a path "
              f"that would still reach it after ejecting; import it "
              f"relative to the program instead", file=sys.stderr)
        return 1

    when = datetime.datetime.now(datetime.timezone.utc)
    date = when.strftime("%Y-%m-%d")
    details = inspect_source(entry)
    functions = [{"name": f["name"],
                  "file": "program/" + os.path.relpath(
                      os.path.abspath(f["file"]), base).replace(os.sep, "/")
                  if not os.path.normcase(os.path.realpath(f["file"]))
                  .startswith(std + os.sep)
                  else "runtime/stdlib/" + os.path.basename(f["file"]),
                  "requires": f["requires"], "ensures": f["ensures"],
                  "status": f["status"]}
                 for f in details["functions"]]
    promising = [f for f in functions if f["requires"] or f["ensures"]]
    proven = [f for f in promising if f["status"] == "proven"]
    record = {"schema": EJECT_SCHEMA, "velaris_version": VERSION,
              "ejected_at": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
              "entry": new_entry, "budget": budget_text,
              "prover": bool(HAVE_Z3), "functions": functions,
              "proven": f"{len(proven)} of {len(promising)}"}
    files = {}
    for rel in sorted(placed):
        with open(os.path.join(out, *rel.split("/")), "rb") as bfh:
            files[rel] = hashlib.sha256(bfh.read()).hexdigest()

    def fill(template: str, literal: bool) -> str:
        quote = json.dumps if literal else str
        return (template.replace("@NAME@", quote(stem))
                .replace("@VERSION@", VERSION).replace("@DATE@", date)
                .replace("@ENTRY@", quote(new_entry if literal
                                          else entry.replace(os.sep, "/")))
                .replace("@BUDGET@", quote(budget_text or ("" if literal
                                                          else "nothing")))
                .replace("@FILES@", json.dumps(files, indent=4))
                .replace("@PROVER@", "with the prover" if HAVE_Z3
                         else "without the prover, so nothing was proven"))

    try:
        from importlib import metadata as _metadata
    except ImportError:                    # pragma: no cover
        _metadata = None  # type: ignore[assignment]  # its one use is inside a try that catches the failure
    pins = [f"# Pinned by velaris eject (Velaris {VERSION}, {date}) to what "
            f"was installed then.",
            "# Neither is needed to run: without z3-solver promises are "
            "checked while the",
            "# program runs, and without llvmlite nothing is compiled to "
            "native code."]
    for dist, why in (("z3-solver", "proves promises before running"),
                      ("llvmlite", "compiles pure numeric functions")):
        try:
            pins.append(f"{dist}=={_metadata.version(dist)}    # {why}")
        except Exception:
            pins.append(f"# {dist} was not installed when this was ejected "
                        f"({why})")
    writes = {
        "main.py": fill(_EJECT_LAUNCHER, literal=True),
        "build.py": fill(_EJECT_BUILD, literal=True),
        "README.md": fill(_EJECT_README, literal=False),
        "requirements.txt": "\n".join(pins) + "\n",
        "proofs.json": json.dumps(record, indent=2) + "\n",
        "LICENSE": _velaris_license(),
    }
    for rel, text in writes.items():
        with open(os.path.join(out, rel), "w", encoding="utf-8",
                  newline="\n") as fh:
            fh.write(text)
    sums = []
    for dp, dirs, fns in os.walk(out):
        dirs.sort()
        for fn in sorted(fns):
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, out).replace(os.sep, "/")
            if rel == "SHA256SUMS":
                continue
            with open(full, "rb") as bfh:
                sums.append(f"{hashlib.sha256(bfh.read()).hexdigest()}  {rel}")
    with open(os.path.join(out, "SHA256SUMS"), "w", encoding="utf-8",
              newline="\n") as fh:
        fh.write("\n".join(sorted(sums, key=lambda s: s[66:])) + "\n")

    shown = out.replace(os.sep, "/")
    print(f"velaris eject: {entry.replace(os.sep, '/')} -> {shown}/")
    print(f"  budget:  {budget_text or 'nothing'}   ({chosen})")
    print(f"  files:   {len(mine)} program file(s), {len(shipped)} standard "
          f"library file(s), the Velaris {VERSION} runtime")
    print(f"  proofs:  {record['proven']} proven when ejected"
          + ("" if HAVE_Z3 else " (no prover installed)")
          + "; a record - each run proves again")
    print(f"  run it:  python -I {shown}/main.py")
    return 0
