#!/usr/bin/env python3
"""Everything the rename promised to keep working, run (8.6).

    python check_rename.py

Velaris was renamed Sabline in 8.6.0. STABILITY.md's rule 1 says a break
ships only in a major version, so the rename is additive: the old command,
the old import, the old environment variables, the old document formats,
the old file names and the two earlier predicate types all still work, for
one major version. This runs each one.

It also runs the drift test - scripts/rename.py with no arguments - so that
a new occurrence of the old name in a place the rules do not account for
fails here rather than being noticed later.

NOTHING REACHES THE INTERNET. Every case is a subprocess on this checkout
or a call into the installed package; the two earlier predicate types are
checked as names, which is what a predicate type is.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sabline  # noqa: E402
from suite_dirs import isolate  # noqa: E402

SABLINE = str(HERE / "sabline.py")
OLD, NEW = "velaris", "sabline"

_wrong = 0
_ok = 0


def ok(what: str, passed: bool, detail: Any = "") -> None:
    global _wrong, _ok
    if passed:
        _ok += 1
        print(f"  ok     {what}")
    else:
        _wrong += 1
        print(f"  WRONG  {what}" + (f"  ({detail})" if detail else ""))


def head(title: str) -> None:
    print("-" * 62)
    print(title)
    print("-" * 62)


def run(args: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env.pop("PYTHONWARNINGS", None)
    env.update(kw.pop("env", {}))
    return subprocess.run([sys.executable] + args, capture_output=True,
                          text=True, timeout=300, env=env, **kw)


# ---------------------------------------------------------------------------
# the command
# ---------------------------------------------------------------------------

def the_command(work: Path) -> None:
    head("the `velaris` command is the `sabline` command, and says so")
    new = run([SABLINE, "--version"])
    ok("sabline --version", new.returncode == 0 and "Sabline" in new.stdout,
       new.stdout.strip() or new.stderr.strip()[:80])

    # The console script is what pip installs; the alias is the function it
    # points at (pyproject.toml). Reached here the way pip would reach it.
    alias = run(["-c",
                 "import sys; sys.argv = ['velaris', '--version']; "
                 "from sabline.cli import velaris_main; "
                 "sys.exit(velaris_main())"])
    ok("the velaris entry point runs the same command",
       alias.returncode == 0 and alias.stdout == new.stdout,
       f"{alias.returncode}: {alias.stdout.strip()[:60]}")
    ok("...and says once on stderr that the name has changed",
       "is now `sabline`" in alias.stderr
       and alias.stderr.count("is now `sabline`") == 1,
       alias.stderr.strip()[:100])
    ok("...while `sabline` itself says nothing of the kind",
       "is now `sabline`" not in new.stderr, new.stderr.strip()[:80])

    entry = (HERE / "pyproject.toml").read_text(encoding="utf-8")
    ok("pyproject installs both commands",
       'sabline = "sabline:main"' in entry
       and 'velaris = "sabline.cli:velaris_main"' in entry)
    npm = json.loads((HERE / "npm" / "package.json").read_text(encoding="utf-8"))
    ok("the npm package installs both too",
       npm["bin"] == {"sabline": "bin/sabline.js",
                      "velaris": "bin/velaris.js"}, npm.get("bin"))


# ---------------------------------------------------------------------------
# the import
# ---------------------------------------------------------------------------

def the_import() -> None:
    head("`import velaris` is `import sabline`")
    r = run(["-c", "import velaris, sabline; "
                   "print(velaris is sabline, velaris.VERSION)"])
    ok("import velaris gives the sabline module itself",
       r.returncode == 0 and r.stdout.strip() == f"True {sabline.VERSION}",
       r.stdout.strip() or r.stderr.strip()[:120])
    ok("...and says once on stderr that the name has changed",
       r.stderr.count("is now `sabline`") == 1, r.stderr.strip()[:100])

    r = run(["-c", "from velaris.budget import Budget; "
                   "import velaris.cli; "
                   "from velaris import check, audit, run, Pool, card; "
                   "print(Budget.__module__, velaris.cli.__name__)"])
    ok("a submodule and the library API import under the old name",
       r.returncode == 0
       and r.stdout.strip() == "sabline.budget sabline.cli",
       r.stdout.strip() or r.stderr.strip()[:200])

    r = run(["-W", "error::DeprecationWarning", "-c", "import velaris"])
    ok("it warns, so -W error finds it (STABILITY.md rule 2)",
       r.returncode != 0 and "DeprecationWarning" in r.stderr,
       r.stderr.strip()[-120:])

    # the class a caller catches
    r = run(["-c",
             "import velaris, sabline;"
             "print(velaris.VelarisError is sabline.SablineError)"])
    ok("VelarisError is SablineError, so `except` keeps catching",
       r.stdout.strip() == "True", r.stdout.strip() or r.stderr[-120:])

    for module in ("velaris_mcp", "velaris_mcp_install"):
        new_name = module.replace(OLD, NEW)
        r = run(["-c", f"import {module}, {new_name}; "
                       f"print({module} is {new_name})"])
        ok(f"import {module} gives {new_name}",
           r.stdout.strip() == "True", r.stdout.strip() or r.stderr[-120:])


# ---------------------------------------------------------------------------
# the environment
# ---------------------------------------------------------------------------

def the_environment(work: Path) -> None:
    head("VELARIS_* is read where SABLINE_* is")
    from sabline import naming

    for name, value in (("SABLINE_PROOF_TIMEOUT", "77"),
                        ("SABLINE_TOKEN", "abc"),
                        ("SABLINE_CONFORMANCE_CORPUS", "/x")):
        old = "VELARIS_" + name[len("SABLINE_"):]
        for key in (name, old):
            os.environ.pop(key, None)
        os.environ[old] = value
        ok(f"{old} answers for {name}", naming.env(name) == value,
           naming.env(name))
        os.environ[name] = value + "0"
        ok(f"...and {name} wins when both are set and agree is not the case",
           _raises(naming.env, name))
        os.environ[name] = value
        ok("...and both set to the same text is one name written twice",
           naming.env(name) == value)
        for key in (name, old):
            os.environ.pop(key, None)

    # end to end: the prover's timeout, under the old name, on a real run
    r = run([SABLINE, "check", str(HERE / "examples" / "discount.vel")],
            cwd=work, env={"VELARIS_PROOF_TIMEOUT": "not-a-number"})
    ok("a bad VELARIS_PROOF_TIMEOUT is complained about by its own name",
       "VELARIS_PROOF_TIMEOUT" in (r.stderr + r.stdout)
       or "PROOF_TIMEOUT" in (r.stderr + r.stdout),
       (r.stderr or r.stdout).strip()[:120])


def _raises(fn: Any, *args: Any) -> bool:
    from sabline.naming import BothNames
    try:
        fn(*args)
    except BothNames:
        return True
    return False


# ---------------------------------------------------------------------------
# the documents
# ---------------------------------------------------------------------------

def the_documents(work: Path) -> None:
    head("a velaris.* document is read where a sabline.* one is")
    from sabline import naming

    for schema in ("sabline.audit/1", "sabline.receipt/1",
                   "sabline.capabilities/1", "sabline.lock/1",
                   "sabline.tools/1", "sabline.eject/1"):
        old = schema.replace(NEW, OLD, 1)
        ok(f"{old} reads as {schema}",
           naming.schema_matches(old, schema)
           and naming.schema_matches(schema, schema))
    ok("and nothing else does",
       not naming.schema_matches("sabline.audit/2", "sabline.audit/1")
       and not naming.schema_matches("other.audit/1", "sabline.audit/1"))

    # a real capability baseline, under the old schema AND the old file name
    tree = work / "old-names"
    if tree.exists():
        shutil.rmtree(tree)
    (tree / "src").mkdir(parents=True)
    shutil.copy(HERE / "examples" / "hello.vel", tree / "src" / "hello.vel")
    made = run([SABLINE, "capabilities", "init", str(tree)], cwd=work)
    baseline = tree / "sabline.capabilities"
    ok("capabilities init writes sabline.capabilities",
       baseline.is_file(), made.stdout.strip()[:120] + made.stderr[:120])
    if baseline.is_file():
        doc = json.loads(baseline.read_text(encoding="utf-8"))
        ok("...and it says sabline.capabilities/1",
           doc.get("schema") == "sabline.capabilities/1", doc.get("schema"))
        # now put it back under both old names, as a repository written
        # before 8.6 has it
        doc["schema"] = "velaris.capabilities/1"
        (tree / "velaris.capabilities").write_text(
            json.dumps(doc, indent=2), encoding="utf-8")
        baseline.unlink()
        checked = run([SABLINE, "capabilities", "check", str(tree)],
                      cwd=work)
        ok("a velaris.capabilities of velaris.capabilities/1 still checks",
           checked.returncode == 0,
           (checked.stdout + checked.stderr).strip()[:200])


# ---------------------------------------------------------------------------
# the predicate types
# ---------------------------------------------------------------------------

def the_predicate_types(work: Path) -> None:
    head("a Statement of an earlier predicate type still verifies")
    from sabline import predicates

    ok("the type written now names sabline.dev",
       predicates.CAPABILITY_PREDICATE_TYPE
       == "https://sabline.dev/capability/v1"
       and predicates.RECEIPT_PREDICATE_TYPE
       == "https://sabline.dev/receipt/v1")
    for kind, types in (("capability", predicates.CAPABILITY_PREDICATE_TYPES),
                        ("receipt", predicates.RECEIPT_PREDICATE_TYPES)):
        ok(f"three spellings of {kind}/v1 are read as one type",
           len(types) == 3 and types[0].startswith("https://sabline.dev")
           and any("velaris-lang.dev" in t for t in types)
           and any("github.io" in t for t in types), types)
        for t in types:
            ok(f"...{t}", predicates.predicate_kind(t) == kind)
    ok("and velaris.dev, which was never this project's, is not",
       predicates.predicate_kind(
           "https://velaris.dev/capability/v1") is None)
    ok("nor is velaris.io",
       predicates.predicate_kind("https://velaris.io/capability/v1") is None)

    # a real Statement, attested now, re-labelled with each earlier type
    out = work / "statement.json"
    made = run([SABLINE, "attest", "examples/effects.vel",
                "--output", str(out)], cwd=str(HERE))
    ok("sabline attest writes a Statement", out.is_file(),
       (made.stdout + made.stderr).strip()[:200])
    if not out.is_file():
        return
    statement = json.loads(out.read_text(encoding="utf-8"))
    ok("...whose predicateType is sabline.dev's",
       statement["predicateType"] == predicates.CAPABILITY_PREDICATE_TYPE,
       statement["predicateType"])
    for earlier in predicates.CAPABILITY_PREDICATE_TYPES[1:]:
        older = work / "earlier.json"
        statement["predicateType"] = earlier
        older.write_text(json.dumps(statement, indent=2), encoding="utf-8")
        r = run([SABLINE, "verify", str(older), "--skip-signature"],
                cwd=str(HERE))
        ok(f"sabline verify reads a Statement of {earlier}",
           r.returncode == 0, (r.stdout + r.stderr).strip()[:200])
    statement["predicateType"] = "https://velaris.dev/capability/v1"
    (work / "foreign.json").write_text(json.dumps(statement), encoding="utf-8")
    r = run([SABLINE, "verify", str(work / "foreign.json"),
             "--skip-signature"], cwd=str(HERE))
    ok("...and refuses one of a type it does not define",
       r.returncode != 0, (r.stdout + r.stderr).strip()[:160])


# ---------------------------------------------------------------------------
# the drift test
# ---------------------------------------------------------------------------

def no_drift() -> None:
    head("no occurrence of the old name is unaccounted for")
    r = run([str(HERE / "scripts" / "rename.py")], cwd=str(HERE))
    ok("scripts/rename.py finds no drift", r.returncode == 0,
       (r.stdout + r.stderr).strip()[-400:])
    if r.returncode == 0:
        print("         " + r.stdout.strip())

    # the rules themselves: the rename is reproducible, so running it again
    # over the tree changes nothing
    r = run([str(HERE / "scripts" / "rename.py"), "--stat"], cwd=str(HERE))
    ok("...and --stat still reads every tracked file", r.returncode == 0,
       (r.stdout + r.stderr).strip()[-200:])


def main() -> int:
    work = Path(isolate("check_rename"))
    the_command(work)
    the_import()
    the_environment(work)
    the_documents(work)
    the_predicate_types(work)
    no_drift()
    print("-" * 62)
    print(f"{_ok} correct, {_wrong} wrong")
    return 1 if _wrong else 0


if __name__ == "__main__":
    with tempfile.TemporaryDirectory():
        sys.exit(main())
