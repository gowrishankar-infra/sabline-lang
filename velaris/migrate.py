"""velaris migrate: the budget each program needs under 5.0.
"""
import json
import os
import re
import sys
from typing import TYPE_CHECKING, Any

from .version import VERSION
from .tables import DEFAULT_ALLOW
from .library import _audit_here, _safe_grants

if TYPE_CHECKING:
    from .ratchet import _capability_files

# Used inside functions only, from modules after this one: velaris/__init__.py
# binds each here once every module is loaded.
__forward__ = {
    "_capability_files": "ratchet",
}


MIGRATE_TO = ("5.0", "5", "5.0.0")

# A line in a shell script or a CI file that runs a Velaris program:
# the command, the .vel path, and whatever follows it. `velaris`,
# `velaris run`, `python velaris.py` and `npx velaris-lang` all count.
_RUNNER = r"(?:(?:python[0-9.]*\s+)?[\w./\\-]*velaris(?:\.py|-lang)?)"
MIGRATE_LINE = re.compile(
    r"^(?P<head>\s*(?:-\s+)?(?:run:\s*)?)"
    r"(?P<cmd>" + _RUNNER + r"(?:\s+run)?)"
    r"(?P<mid>\s+)"
    r"(?P<file>[\w./\\-]+\.vel)"
    r"(?P<tail>.*)$")

# what stops a line being rewritten: another command after this one, a
# substitution, or output sent somewhere. The flag would still parse,
# but where it belongs on such a line is a guess, and this command does
# not guess.
MIGRATE_UNSURE = ("|", "&", ";", "`", "$(", ">>", "<")


def migrate_needs(path: str) -> dict[str, Any]:
    """What one program needs to keep running under 5.0.

    The narrowest budget its own audit can write - the same grants
    `safe_command` carries - or why it could not be worked out.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            source = fh.read()
    except OSError as e:
        return {"path": path, "ok": False, "why": str(e), "allow": None}
    try:
        report = _audit_here(source, path=path)
    except Exception as e:                 # a file that does not parse
        return {"path": path, "ok": False, "why": str(e), "allow": None}
    if not report.ok:
        first = report.problems[0] if report.problems else None
        return {"path": path, "ok": False, "allow": None,
                "why": (f"does not compile: [{first.code}] {first.message}"
                        if first else "does not compile")}
    grants = _safe_grants(report.effects, report.ffi_modules,
                          {"read": sorted(report.fs_paths["read"]),
                           "write": sorted(report.fs_paths["write"]),
                           "read_any": report.fs_paths["read_any"],
                           "write_any": report.fs_paths["write_any"]},
                          {"hosts": sorted(report.net_hosts["hosts"]),
                           "any": report.net_hosts["any"]})
    return {"path": path, "ok": True, "allow": ",".join(grants),
            "effects": list(report.effects),
            # io alone, or no effect at all, is what 5.0 grants already
            "enough": set(report.effects) <= {DEFAULT_ALLOW},
            "warnings": list(report.warnings), "why": None}


def _migrate_rewrite(text: str, needs: dict[Any, Any], root: str) -> tuple[Any, ...]:
    """One shell script or CI file with `--allow` added to every line
    that runs a program this migration worked out a budget for.

    Returns (new text, [what changed], [what was left alone and why]).
    A line is rewritten only when all of it is understood: one command,
    a .vel path that resolves to a program in `needs`, no budget flag
    already on it, and nothing that would make the end of the command
    the wrong place for a flag.
    """
    changed, skipped, out = [], [], []
    for n, line in enumerate(text.split("\n"), 1):
        m = MIGRATE_LINE.match(line)
        if not m:
            out.append(line)
            continue
        out.append(line)
        if "--allow" in line or "--deny" in line:
            continue                        # already says what it needs
        target = m.group("file").replace("\\", "/")
        found = None
        for cand in (os.path.normpath(os.path.join(root, target)),
                     os.path.normpath(target)):
            found = needs.get(os.path.normcase(os.path.abspath(cand)))
            if found is not None:
                break
        if found is None:
            skipped.append((n, line.strip(),
                            f"no program of this checkout at {target}"))
            continue
        if not found["ok"]:
            skipped.append((n, line.strip(), f"{target}: {found['why']}"))
            continue
        if found["enough"]:
            continue                        # io, which 5.0 grants anyway
        if any(c in line for c in MIGRATE_UNSURE):
            skipped.append((n, line.strip(),
                            "more than one command on the line, or its "
                            "input or output moved: add --allow "
                            + found["allow"] + " by hand"))
            continue
        # after the file name, before the program's own arguments, which
        # is where the command line reads flags and where a reader of
        # the script looks for them
        out[-1] = (m.group("head") + m.group("cmd") + m.group("mid")
                   + m.group("file") + f" --allow {found['allow']}"
                   + m.group("tail"))
        changed.append((n, target, found["allow"]))
    return "\n".join(out), changed, skipped


MIGRATE_WRITABLE = (".sh", ".bash", ".yml", ".yaml")


def migrate_main(argv: list[Any]) -> int:
    """velaris migrate --to 5.0 [path] [--write] [--json]

    What every program under `path` needs to keep running under 5.0,
    where a run with no --allow gets `io` instead of all seven effects
    (STABILITY.md, "Breaks we have made"). It reads; it writes nothing
    unless --write is given, and then only shell scripts and CI files
    it can parse with no guessing, and it says what it left alone.
    """
    if "--to" not in argv:
        print("usage: velaris migrate --to 5.0 [path] [--write] [--json]",
              file=sys.stderr)
        return 2
    at = argv.index("--to")
    want = argv[at + 1] if at + 1 < len(argv) else ""
    if want not in MIGRATE_TO:
        print(f"velaris migrate knows how to migrate to 5.0, not "
              f"{want or '(nothing)'}", file=sys.stderr)
        return 2
    flags = {"--write", "--json"}
    rest = [a for i, a in enumerate(argv)
            if i not in (at, at + 1) and a not in flags]
    write, as_json = "--write" in argv, "--json" in argv
    unknown = [a for a in rest if a.startswith("-")]
    if unknown:
        print(f"velaris migrate: unknown argument '{unknown[0]}'",
              file=sys.stderr)
        return 2
    target = rest[0] if rest else "."

    if os.path.isdir(target):
        root = target
        programs = [os.path.join(target, f.replace("/", os.sep))
                    for f in _capability_files(target)]
    elif os.path.exists(target):
        root = os.path.dirname(target) or "."
        programs = [target]
    else:
        print(f"no such file or folder: {target}", file=sys.stderr)
        return 1

    rows = [migrate_needs(p) for p in sorted(programs)]
    by_path = {os.path.normcase(os.path.abspath(r["path"])): r
               for r in rows}

    wrote, untouched = [], []
    if write:
        for dp, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d != ".git")
            for f in sorted(files):
                if not f.endswith(MIGRATE_WRITABLE):
                    continue
                full = os.path.join(dp, f)
                try:
                    with open(full, "r", encoding="utf-8") as fh:
                        before = fh.read()
                except (OSError, UnicodeDecodeError) as e:
                    untouched.append((full, 0, str(e)))
                    continue
                after, changed, skipped = _migrate_rewrite(
                    before, by_path, root)
                untouched += [(full, n, why) for n, _, why in skipped]
                if changed and after != before:
                    with open(full, "w", encoding="utf-8",
                              newline="") as fh:
                        fh.write(after)
                    wrote.append((full, changed))

    def command_for(r: dict[Any, Any]) -> str:
        shown = r["path"].replace(os.sep, "/")
        return (f"velaris {shown}" if r["enough"]
                else f"velaris {shown} --allow {r['allow']}")

    if as_json:
        print(json.dumps({
            "schema": "velaris.migrate/1", "velaris_version": VERSION,
            "to": "5.0", "root": root.replace(os.sep, "/"),
            "programs": [
                {"path": r["path"].replace(os.sep, "/"), "ok": r["ok"],
                 "allow": r["allow"], "why": r["why"],
                 "command": command_for(r) if r["ok"] else None}
                for r in rows],
            "written": [{"file": f.replace(os.sep, "/"),
                         "lines": [{"line": n, "program": p, "allow": a}
                                   for n, p, a in ch]}
                        for f, ch in wrote],
            "not_written": [{"file": f.replace(os.sep, "/"), "line": n,
                             "why": why} for f, n, why in untouched],
        }, indent=2))
        return 0

    print(f"velaris migrate --to 5.0   ({len(rows)} program(s) under "
          f"{root.replace(os.sep, '/')})")
    print("a run with no --allow gets io from 5.0; before, it got all "
          "seven effects.")
    print("=" * 68)
    needs_more = [r for r in rows if r["ok"] and not r["enough"]]
    fine = [r for r in rows if r["ok"] and r["enough"]]
    broken = [r for r in rows if not r["ok"]]
    for r in needs_more:
        print(f"\n{r['path'].replace(os.sep, '/')}")
        print(f"    uses:  {', '.join(r['effects'])}")
        print(f"    run:   {command_for(r)}")
        for w in r["warnings"]:
            print(f"    note:  {w}")
    if fine:
        print(f"\n{len(fine)} program(s) need nothing: they use io or no "
              f"effect at all, which 5.0 grants.")
    if broken:
        print(f"\n{len(broken)} file(s) the budget could not be worked "
              f"out for:")
        for r in broken:
            print(f"    {r['path'].replace(os.sep, '/')}: {r['why']}")
    if write:
        print()
        if wrote:
            for f, changed in wrote:
                print(f"wrote {f.replace(os.sep, '/')}")
                for n, p, a in changed:
                    print(f"    line {n}: {p} --allow {a}")
        else:
            print("wrote nothing: no line in a shell script or CI file "
                  "needed a budget added.")
        if untouched:
            print(f"\nleft alone ({len(untouched)}), for you to read:")
            for f, n, why in untouched:
                where = f.replace(os.sep, "/")
                print(f"    {where}{':' + str(n) if n else ''}: {why}")
    else:
        print("\nnothing was changed. --write updates the shell scripts "
              "and CI files it can parse, and says what it did not.")
    return 0
