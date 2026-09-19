#!/usr/bin/env python3
"""velaris permissions-ratchet: a workflow permission that widens fails,
and nothing else does.

`velaris permissions-ratchet --against REF` compares the permissions:
blocks of every workflow in .github/workflows with the ones REF has, job
by job; velaris/permissions.py says exactly how. This suite holds it in
five parts:

1. tests/permissions/: each directory a base/ and a head/ copy of
   .github/workflows, with the findings expected of the pair written
   below - widenings, narrowings, reformatting that must change nothing,
   and files that cannot be read - compared by
   velaris.permissions_compare, with no git.
2. The reader against PyYAML. Velaris reads these files without a YAML
   library, so every fixture and every workflow of this repository is
   also read with PyYAML, and the blocks, their levels and the line of
   every job, permissions: and scope key must agree. A file the reader
   refuses is named with whether PyYAML refuses it too, or reads it and is
   refused here on purpose (an anchor, a key written twice, id-token: read).
3. Shapes of YAML one at a time, each read both ways.
4. The command line against real git repositories with two commits: exit
   0, 1 and 2, the file and line of each widening, and --json against the
   shape of velaris.permissions-ratchet/1.
5. The Action's step: its input, where it runs and on what condition, and
   its bash run as a runner runs it - `velaris` and `python` stood in for
   on PATH, GITHUB_OUTPUT and RUNNER_TEMP set - in a shallow clone whose
   base commit has to be fetched from its origin.

Nothing here reaches the network. PyYAML and jsonschema are the test
extra; without one, the parts that need it say they skipped.

    python check_permissions.py
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
VELARIS = HERE / "velaris.py"
FIXTURES = HERE / "tests" / "permissions"
sys.path.insert(0, str(HERE))
import velaris  # noqa: E402
from velaris import permissions  # noqa: E402
from suite_dirs import isolate  # noqa: E402

WORK = isolate("check_permissions")      # its own directory

try:
    import yaml
except ImportError:                       # the parts that need it say so
    yaml = None  # type: ignore[assignment]

try:
    from jsonschema import Draft7Validator
except ImportError:
    Draft7Validator = None  # type: ignore[assignment, misc]

HAVE_GIT = shutil.which("git") is not None
PASSED = FAILED = SKIPPED = 0


def ascii_text(text: object) -> str:
    return str(text).encode("ascii", "backslashreplace").decode("ascii")


def ok(label: str, good: object, detail: object = "") -> None:
    global PASSED, FAILED
    if good:
        PASSED += 1
        print(f"  ok       {ascii_text(label)}")
    else:
        FAILED += 1
        print(f"  BROKEN   {ascii_text(label)}")
        if detail:
            print(f"           {ascii_text(detail)[:1500]}")


def skip(label: str, why: str) -> None:
    global SKIPPED
    SKIPPED += 1
    print(f"  skip     {label} ({why})")


# ---- 1. the fixtures -----------------------------------------------------------

def finding(file: str, line: int, label: str, scope: str, before: str,
            after: str, jobs: list[str] | None = None,
            side: str = "head") -> dict[str, Any]:
    """A finding as a case writes it: `label` is the job, or "workflow"
    for the workflow's own block, which names the jobs it reaches."""
    return {"file": file, "line": line, "label": label, "scope": scope,
            "before": before, "after": after,
            "jobs": jobs if jobs is not None else [label], "side": side}


def unread(file: str, side: str, line: int | None,
           word: str) -> dict[str, Any]:
    return {"file": file, "side": side, "line": line, "word": word}


def case(name: str, what: str, widened: list[dict[str, Any]] | None = None,
         narrowed: list[dict[str, Any]] | None = None,
         unreadable: list[dict[str, Any]] | None = None,
         scopes: int | None = None) -> dict[str, Any]:
    return {"name": name, "what": what, "widened": widened or [],
            "narrowed": narrowed or [], "unreadable": unreadable or [],
            "scopes": scopes}


CASES = [
    # ---- widenings, which fail
    case("widened-read-to-write", "a scope's level rises from read to write",
         widened=[finding("ci.yml", 7, "build", "contents", "read", "write")]),
    case("widened-new-scope", "a scope the block did not list is given write",
         widened=[finding("ci.yml", 8, "build", "issues", "none", "write")]),
    case("widened-write-all-replaces-map", "write-all replaces a mapping: one "
         "finding at the permissions: key, naming all 16 scopes that rose",
         widened=[finding("ci.yml", 6, "build", "permissions",
                          "{contents: read}", "write-all")], scopes=16),
    case("widened-block-removed", "a job's block is removed, and with no "
         "workflow block it falls to the repository default, at the job key",
         widened=[finding("ci.yml", 4, "build", "permissions",
                          "{contents: read}", "repository default")]),
    case("widened-new-job-no-block", "a new job with no block anywhere takes "
         "the repository default",
         widened=[finding("ci.yml", 10, "lint", "permissions", "{}",
                          "repository default")]),
    case("widened-new-file-write", "a new workflow file gives its job "
         "contents: write, from the workflow's block",
         widened=[finding("release.yaml", 6, "workflow", "contents", "none",
                          "write", ["publish"])]),
    case("widened-workflow-block", "the workflow's block rises, reaching two "
         "jobs: one finding, naming both",
         widened=[finding("ci.yml", 3, "workflow", "contents", "read",
                          "write", ["build", "test"])]),
    case("widened-workflow-block-removed", "the workflow's block is removed: "
         "each job that took it falls to the repository default, at its key",
         widened=[finding("ci.yml", 3, "build", "permissions",
                          "{contents: read}", "repository default"),
                  finding("ci.yml", 7, "test", "permissions",
                          "{contents: read}", "repository default")]),
    case("widened-unknown-scope", "a scope this does not know, given read, "
         "is still a widening",
         widened=[finding("ci.yml", 8, "build", "future-scope", "none",
                          "read")]),
    case("widened-id-token", "id-token: write added",
         widened=[finding("ci.yml", 8, "build", "id-token", "none",
                          "write")]),
    case("widened-job-falls-to-workflow-block", "a job's own block removed "
         "so it takes the workflow's read-all: the 14 scopes that rose, at "
         "the workflow's permissions: key",
         widened=[finding("ci.yml", 2, "workflow", "permissions",
                          "{contents: read}", "read-all", ["build"])],
         scopes=14),
    case("widened-job-renamed", "a job renamed is a job removed and a new "
         "job, and the new job is compared with no permissions",
         widened=[finding("ci.yml", 7, "compile", "contents", "none",
                          "read")],
         narrowed=[finding("ci.yml", 4, "build", "permissions",
                           "{contents: read}", "removed", side="base")]),
    # ---- narrowings, which never fail
    case("narrowed-write-to-read", "a scope falls from write to read",
         narrowed=[finding("ci.yml", 7, "build", "contents", "write",
                           "read")]),
    case("narrowed-scope-dropped", "a scope dropped from the block, named at "
         "the permissions: key",
         narrowed=[finding("ci.yml", 6, "build", "issues", "write",
                           "none")]),
    case("narrowed-job-removed", "a job removed, named at its line in the "
         "base",
         narrowed=[finding("ci.yml", 10, "lint", "permissions",
                           "repository default", "removed", side="base")]),
    case("narrowed-file-deleted", "a workflow file deleted",
         narrowed=[finding("release.yaml", 8, "publish", "permissions",
                           "{contents: write}", "removed", side="base")]),
    case("narrowed-default-to-block", "a job that had the repository default "
         "is given a block",
         narrowed=[finding("ci.yml", 6, "build", "permissions",
                           "repository default", "{contents: read}")]),
    # ---- the same permissions, written another way
    case("unchanged-identical", "the same file"),
    case("unchanged-flow-vs-block", "a block mapping written as a flow "
         "mapping, its keys in another order"),
    case("unchanged-reformatted", "comments, quoting, key order, "
         "indentation, a --- marker, and text that looks like a permissions "
         "key in a comment, a quoted name over two lines, a script and a "
         "folded value"),
    case("unchanged-crlf", "the same file with CRLF line ends"),
    case("unchanged-read-all-spelled-out", "read-all against a mapping that "
         "lists every known scope read and id-token none"),
    case("unchanged-empty-block", "{} against a mapping listing scopes as "
         "none"),
    # ---- files that cannot be read with confidence
    case("unreadable-anchor-alias", "an anchor and an alias",
         unreadable=[unread("ci.yml", "head", 5, "anchor")]),
    case("unreadable-tab", "a tab in the indentation",
         unreadable=[unread("ci.yml", "head", 6, "tab")]),
    case("unreadable-two-documents", "a second document",
         unreadable=[unread("ci.yml", "head", 13, "more than one document")]),
    case("unreadable-duplicate-key", "permissions: written twice in one job",
         unreadable=[unread("ci.yml", "head", 10, "twice")]),
    case("unreadable-id-token-read", "id-token: read, a level id-token does "
         "not have",
         unreadable=[unread("ci.yml", "head", 8, "id-token")]),
    case("unreadable-at-the-base", "a base file that cannot be read: what it "
         "gave is not known",
         unreadable=[unread("ci.yml", "base", 6, "tab")]),
    case("unreadable-beside-a-widening", "a file that cannot be read beside a "
         "widening in another: exit 2, and the widening still reported",
         widened=[finding("ci.yml", 7, "build", "contents", "read", "write")],
         unreadable=[unread("other.yml", "head", 6, "tab")]),
]

# refused here although PyYAML reads the YAML
DELIBERATE = {
    "unreadable-anchor-alias/head/ci.yml": "an anchor, which is not followed",
    "unreadable-duplicate-key/head/ci.yml": "a key written twice, where "
                                            "PyYAML keeps the last",
    "unreadable-id-token-read/head/ci.yml": "id-token: read, a level "
                                            "id-token does not have",
}

FINDING_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["file", "line", "side", "where", "job", "jobs", "scope",
                 "scopes", "before", "after", "reason"],
    "properties": {
        "file": {"type": "string"},
        "line": {"type": "integer", "minimum": 1},
        "side": {"enum": ["head", "base"]},
        "where": {"enum": ["job", "workflow"]},
        "job": {"type": ["string", "null"]},
        "jobs": {"type": "array", "minItems": 1,
                 "items": {"type": "string"}},
        "scope": {"type": "string"},
        "scopes": {"type": "array", "items": {"type": "string"}},
        "before": {"type": "string"},
        "after": {"type": "string"},
        "reason": {"type": "string", "minLength": 1}}}
RESULT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["schema", "against", "widened", "narrowed", "unreadable"],
    "properties": {
        "schema": {"const": "velaris.permissions-ratchet/1"},
        "against": {"type": "string"},
        "widened": {"type": "array", "items": FINDING_SCHEMA},
        "narrowed": {"type": "array", "items": FINDING_SCHEMA},
        "unreadable": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["file", "side", "line", "reason"],
            "properties": {
                "file": {"type": "string"},
                "side": {"enum": ["head", "base"]},
                "line": {"type": ["integer", "null"]},
                "reason": {"type": "string", "minLength": 1}}}}}}


def shape_problems(doc: Any) -> list[str]:
    """What is wrong with a velaris.permissions-ratchet/1 document: its keys
    by hand, the rest against RESULT_SCHEMA when jsonschema is here."""
    want = {"schema", "against", "widened", "narrowed", "unreadable"}
    if not isinstance(doc, dict) or set(doc) != want:
        return [f"not the document's keys: {doc!r}"[:300]]
    problems = []
    if Draft7Validator is not None:
        problems += [e.message for e in
                     Draft7Validator(RESULT_SCHEMA).iter_errors(doc)]
    for f in doc["widened"] + doc["narrowed"]:
        if (f.get("where") == "workflow") != (f.get("job") is None):
            problems.append(f"job and where disagree: {f}")
    return problems


def shown(f: dict[str, Any]) -> dict[str, Any]:
    """A finding of a result, in the terms a case writes."""
    return {"file": f["file"], "line": f["line"],
            "label": f["job"] if f["where"] == "job" else "workflow",
            "scope": f["scope"], "before": f["before"], "after": f["after"],
            "jobs": f["jobs"], "side": f["side"]}


def fixture_side(name: str, side: str) -> dict[str, bytes]:
    folder = FIXTURES / name / side
    if not folder.is_dir():
        return {}
    return {p.name: p.read_bytes() for p in sorted(folder.iterdir())
            if p.is_file()}


def fixture_text(name: str, side: str, file: str) -> str:
    return (FIXTURES / name / side / file).read_bytes().decode("utf-8")


def exit_of(c: dict[str, Any]) -> int:
    return 2 if c["unreadable"] else 1 if c["widened"] else 0


def fixture_cases() -> None:
    print("the fixtures in tests/permissions, compared without git")
    print("-" * 62)
    on_disk = sorted(p.name for p in FIXTURES.iterdir() if p.is_dir())
    named = sorted(c["name"] for c in CASES)
    ok("every fixture directory is a case here, and every case has one",
       on_disk == named, sorted(set(on_disk) ^ set(named)))
    if Draft7Validator is None:
        skip("each result against the JSON Schema of "
             "velaris.permissions-ratchet/1 (its keys are still checked)",
             "jsonschema is not installed")
    misprinted: list[Any] = []
    for c in CASES:
        base = fixture_side(c["name"], "base")
        head = fixture_side(c["name"], "head")
        result = permissions.permissions_compare(base, head, "base")
        unreadable = [(u["file"], u["side"], u["line"])
                      for u in result["unreadable"]]
        words = all(w["word"] in u["reason"] for w, u in
                    zip(c["unreadable"], result["unreadable"]))
        good = ([shown(f) for f in result["widened"]] == c["widened"]
                and [shown(f) for f in result["narrowed"]] == c["narrowed"]
                and unreadable == [(u["file"], u["side"], u["line"])
                                   for u in c["unreadable"]]
                and words and not shape_problems(result)
                and permissions.permissions_exit(result) == exit_of(c))
        if c["scopes"] is not None:
            good = good and bool(result["widened"]) and len(
                result["widened"][0]["scopes"]) == c["scopes"]
        ok(f"{c['name']}: {c['what']} (exit {exit_of(c)})", good,
           json.dumps(result)[:1400] + " " + str(shape_problems(result)))
        text = permissions.permissions_lines(result)
        for key, word in (("widened", "WIDENED"), ("narrowed", "narrowed")):
            for f in result[key]:
                line = (f"{word} {f['file']}:{f['line']} {shown(f)['label']} "
                        f"{f['scope']}: {f['before']} -> {f['after']}")
                at = text.index(line) if line in text else -1
                if at < 0 or not text[at + 1].startswith("    ") \
                        or f["reason"] not in text[at + 1]:
                    misprinted.append(line)
    ok("each finding prints as `WIDENED|narrowed <file>:<line> <job or "
       "workflow> <scope>: <before> -> <after>`, its reason on the line "
       "after", not misprinted, misprinted[:3])

    renamed = permissions.permissions_compare(
        fixture_side("widened-job-renamed", "base"),
        fixture_side("widened-job-renamed", "head"))
    ok("...a rename's narrowing says that a job renamed is a job removed and "
       "a new job", "renamed" in renamed["narrowed"][0]["reason"],
       renamed["narrowed"])
    new_job = permissions.permissions_compare(
        fixture_side("widened-new-job-no-block", "base"),
        fixture_side("widened-new-job-no-block", "head"))
    ok("...and a new job with no block says it takes the repository's "
       "default permissions", "repository's default" in
       new_job["widened"][0]["reason"], new_job["widened"])
    crlf_base = fixture_side("unchanged-crlf", "base")["ci.yml"]
    crlf_head = fixture_side("unchanged-crlf", "head")["ci.yml"]
    ok("unchanged-crlf's head holds CRLF line ends and its base LF "
       "(.gitattributes keeps them as they are)",
       b"\r\n" in crlf_head and b"\r\n" not in crlf_base
       and crlf_head.replace(b"\r\n", b"\n") == crlf_base)
    tab = fixture_side("unreadable-tab", "head")["ci.yml"]
    ok("unreadable-tab's head holds a tab", b"\t" in tab)
    bad = permissions.permissions_compare(
        {"a.yml": b"on: push\n"},
        {"a.yml": b"on: \xff\n",
         "b.yml": permissions.WorkflowUnreadable(None, "a symbolic link")})
    ok("a file that is not UTF-8, and one given as not read, are unreadable "
       "with no line, never read as having no permissions",
       [(u["file"], u["line"]) for u in bad["unreadable"]]
       == [("a.yml", None), ("b.yml", None)]
       and "UTF-8" in bad["unreadable"][0]["reason"]
       and permissions.permissions_exit(bad) == 2, bad)


# ---- 2 and 3. the reader against PyYAML -------------------------------------------

def all_levels(level: str) -> dict[str, str]:
    return {s: ("none" if s == "id-token" and level == "read" else level)
            for s in permissions.PERMISSION_SCOPES}


def pyyaml_block(node: Any, line: int) -> dict[str, Any]:
    """A permissions: block as the module docstring defines it, read from
    PyYAML's node: the form, the key's line, every level, each scope's line."""
    if isinstance(node, yaml.ScalarNode):
        return {"form": node.value, "line": line,
                "levels": all_levels(node.value.split("-")[0]),
                "scope_lines": {}}
    levels = all_levels("none")
    scope_lines = {}
    for key, value in node.value:
        levels[key.value] = value.value
        scope_lines[key.value] = key.start_mark.line + 1
    return {"form": "map", "line": line, "levels": levels,
            "scope_lines": scope_lines}


def pyyaml_view(text: str) -> dict[str, Any]:
    """What read_workflow must give for `text`, derived with PyYAML."""
    root = yaml.compose(text, Loader=yaml.SafeLoader)
    view: dict[str, Any] = {"workflow": None, "jobs": {}}
    if not isinstance(root, yaml.MappingNode):   # empty, or refused by the reader
        return view
    top = {k.value: (k.start_mark.line + 1, v) for k, v in root.value}
    if "permissions" in top:
        view["workflow"] = pyyaml_block(top["permissions"][1],
                                        top["permissions"][0])
    if "jobs" in top and isinstance(top["jobs"][1], yaml.MappingNode):
        for key, job in top["jobs"][1].value:
            if not isinstance(job, yaml.MappingNode):   # refused by the reader
                view["jobs"][key.value] = {"line": key.start_mark.line + 1,
                                           "block": None}
                continue
            own = {k.value: (k.start_mark.line + 1, v) for k, v in job.value}
            view["jobs"][key.value] = {
                "line": key.start_mark.line + 1,
                "block": (pyyaml_block(own["permissions"][1],
                                       own["permissions"][0])
                          if "permissions" in own else None)}
    return view


def both_ways(text: str) -> tuple[Any, Any, Any, Any]:
    """(the reader's view, its refusal, PyYAML's view, PyYAML's error)."""
    try:
        mine, refused = permissions.read_workflow(text), None
    except permissions.WorkflowUnreadable as e:
        mine, refused = None, e
    try:
        theirs, error = pyyaml_view(text), None
    except yaml.YAMLError as e:
        theirs, error = None, e
    return mine, refused, theirs, error


def same_view(mine: Any, theirs: Any) -> bool:
    return (mine is not None and theirs is not None and mine == theirs
            and list(mine["jobs"]) == list(theirs["jobs"]))


def reader_cases() -> None:
    print()
    print("the reader against PyYAML, file by file")
    print("-" * 62)
    if yaml is None:
        skip("every fixture and workflow read both ways",
             "PyYAML is not installed")
        return
    files = [(p.relative_to(FIXTURES).as_posix(), p)
             for p in sorted(FIXTURES.rglob("*")) if p.is_file()]
    own = sorted((HERE / ".github" / "workflows").glob("*.y*ml"))
    files += [(p.relative_to(HERE).as_posix(), p) for p in own]
    ok("this repository's own workflows are among them", len(own) >= 3,
       [p.name for p in own])
    for rel, path in files:
        text = path.read_bytes().decode("utf-8")
        mine, refused, theirs, error = both_ways(text)
        if refused is None:
            ok(f"{rel}: read as PyYAML reads it - the blocks, levels and "
               f"lines of {len(mine['jobs'])} job(s)",
               same_view(mine, theirs),
               f"reader: {mine}\n           PyYAML: {theirs or error}")
        elif rel in DELIBERATE:
            ok(f"{rel}: refused at line {refused.line}, {DELIBERATE[rel]}; "
               f"PyYAML reads the YAML", error is None, refused.reason)
        else:
            ok(f"{rel}: refused at line {refused.line}, and PyYAML refuses "
               f"it too", error is not None, refused.reason)


JOB = "jobs:\n  a:\n    runs-on: x\n"
READ_ALL = ("read-all", {s: "read" for s in permissions.PERMISSION_SCOPES
                         if s != "id-token"})
WRITE_ALL = ("write-all", {s: "write" for s in permissions.PERMISSION_SCOPES})

# (what, the text, what it reads as or ("refused", line, a word of the
# reason), and whether PyYAML reads or refuses the YAML)
SHAPES: list[tuple[str, str, Any, str]] = [
    ("a flow mapping over several lines, with a comment inside",
     "permissions: {\n  contents: read,   # the code\n  issues: write # PRs\n"
     "}\n" + JOB,
     {"workflow": ("map", {"contents": "read", "issues": "write"}),
      "jobs": {"a": None}}, "reads"),
    ("a scalar on the line after its key", "permissions:\n  read-all\n" + JOB,
     {"workflow": READ_ALL, "jobs": {"a": None}}, "reads"),
    ("a flow mapping on the line after its key",
     "jobs:\n  a:\n    permissions:\n      { contents: write }\n",
     {"workflow": None, "jobs": {"a": ("map", {"contents": "write"})}},
     "reads"),
    ("JSON-style keys and values, with an escape in a key",
     'permissions: {"contents":"read","id-\\x74oken":"write"}\n' + JOB,
     {"workflow": ("map", {"contents": "read", "id-token": "write"}),
      "jobs": {"a": None}}, "reads"),
    ("CR alone as the line end",
     "on: push\rjobs:\r  a:\r    permissions: write-all\r",
     {"workflow": None, "jobs": {"a": WRITE_ALL}}, "reads"),
    ("a byte-order mark", "\ufeffpermissions: {}\n" + JOB,
     {"workflow": ("map", {}), "jobs": {"a": None}}, "reads"),
    ("a document start and a document end marker",
     "---\npermissions: read-all\n" + JOB + "...\n",
     {"workflow": READ_ALL, "jobs": {"a": None}}, "reads"),
    ("the top level indented",
     "  on: push\n  jobs:\n    a:\n      permissions: write-all\n",
     {"workflow": None, "jobs": {"a": WRITE_ALL}}, "reads"),
    ("a block scalar with an indentation indicator, holding a decoy",
     "jobs:\n  a:\n    run: |2\n         permissions: write-all\n"
     "    permissions: {}\n",
     {"workflow": None, "jobs": {"a": ("map", {})}}, "reads"),
    ("a keep-chomping block scalar holding a decoy, blank lines, then the "
     "next job",
     "jobs:\n  a:\n    run: |+\n      permissions: write-all\n\n\n  b:\n"
     "    permissions: read-all\n",
     {"workflow": None, "jobs": {"a": None, "b": READ_ALL}}, "reads"),
    ("a plain value over two lines, then the job's permissions",
     "jobs:\n  a:\n    name: build\n      and test\n"
     "    permissions: read-all\n",
     {"workflow": None, "jobs": {"a": READ_ALL}}, "reads"),
    ("a sequence at its key's column, with a decoy in a step's inputs",
     "jobs:\n  a:\n    steps:\n    - run: x\n    - uses: y\n      with:\n"
     "        permissions: write-all\n    permissions:\n      contents: read\n",
     {"workflow": None, "jobs": {"a": ("map", {"contents": "read"})}},
     "reads"),
    ("nested sequences",
     "jobs:\n  a:\n    matrix:\n    - - x\n      - y\n"
     "    permissions: read-all\n",
     {"workflow": None, "jobs": {"a": READ_ALL}}, "reads"),
    ("a job with no block, in a workflow with none", JOB,
     {"workflow": None, "jobs": {"a": None}}, "reads"),
    ("an empty file", "", {"workflow": None, "jobs": {}}, "reads"),
    ("comments and blank lines only", "# nothing\n\n   \n# here\n",
     {"workflow": None, "jobs": {}}, "reads"),
    ("a quoted permissions key and a quoted shorthand",
     "\"permissions\": 'write-all'\n" + JOB,
     {"workflow": WRITE_ALL, "jobs": {"a": None}}, "reads"),
    ("a single quote written twice in a scope's name",
     "permissions:\n  'it''s': read\n" + JOB,
     {"workflow": ("map", {"it's": "read"}), "jobs": {"a": None}}, "reads"),
    ("a tab after a colon", "permissions:\tread-all\n",
     ("refused", 1, "tab"), "refuses"),
    ("a tab inside a plain value", "name: a\tb\n",
     ("refused", 1, "tab"), "refuses"),
    ("a tab on a blank line", "on: push\n\t\nname: x\n",
     ("refused", 2, "tab"), "refuses"),
    ("a tab in the indentation", "jobs:\n\ta:\n    x: 1\n",
     ("refused", 2, "tab"), "refuses"),
    ("an alias in a flow mapping", "permissions: {contents: *a}\n",
     ("refused", 1, "*"), "refuses"),
    ("an alias as a value", "on: push\npermissions: *a\n",
     ("refused", 2, "alias"), "refuses"),
    ("a tag", "permissions: !!str write-all\n",
     ("refused", 1, "tag"), "reads"),
    ("an explicit key", "? permissions\n: write-all\n",
     ("refused", 1, "explicit key"), "reads"),
    ("content after a document end marker", "on: push\n...\nname: x\n",
     ("refused", 3, "document end"), "refuses"),
    ("a second document", "on: push\n---\nname: x\n",
     ("refused", 2, "second document"), "refuses"),
    ("a directive", "%YAML 1.1\n---\non: push\n",
     ("refused", 1, "directive"), "reads"),
    ("content on the --- line", "--- on: push\n",
     ("refused", 1, "content on"), "refuses"),
    ("a line separator, a line end in YAML 1.1 and not in 1.2",
     "name: a\u2028b\n", ("refused", 1, "U+2028"), "refuses"),
    ("a control character", "on: push\nname: a\x07\n",
     ("refused", 2, "U+0007"), "refuses"),
    ("permissions: with no value", "permissions:\n" + JOB,
     ("refused", 1, "no value"), "reads"),
    ("a level where a shorthand belongs", "permissions: read\n" + JOB,
     ("refused", 1, "not read-all"), "reads"),
    ("a level in capitals", "permissions:\n  contents: Read\n" + JOB,
     ("refused", 2, "not read, write or none"), "reads"),
    ("a scope holding a mapping",
     "permissions:\n  contents:\n    x: read\n" + JOB,
     ("refused", 2, "one-line value"), "reads"),
    ("a scope written twice in a flow mapping",
     "permissions: {contents: read, contents: write}\n" + JOB,
     ("refused", 1, "twice"), "reads"),
    ("jobs as a flow mapping", "jobs: {a: {permissions: write-all}}\n",
     ("refused", 1, "block mapping"), "reads"),
    ("a job that is not a mapping", "jobs:\n  a: build\n",
     ("refused", 2, "block mapping"), "reads"),
    ("a quoted value that is never closed", "on: push\nname: \"abc\n",
     ("refused", 2, "never closed"), "refuses"),
    ("a block scalar line less indented than its block",
     "a:\n    b: |\n        x\n      y\n",
     ("refused", 4, "less indented"), "refuses"),
    ("': ' inside a plain value", "jobs:\n  a:\n    run: echo \"a: b\"\n",
     ("refused", 3, "': '"), "refuses"),
    ("a key less indented than the top level", "  on: push\nname: x\n",
     ("refused", 2, "top level"), "refuses"),
    ("a sequence at the top level", "- on: push\n",
     ("refused", 1, "not a mapping"), "reads"),
    ("a bad escape in a double-quoted value", "name: \"\\q\"\n",
     ("refused", 1, "escape"), "refuses"),
    ("a plain value continued after a comment line",
     "name: a\n  # c\n  b\n", ("refused", 3, "continues a plain value"),
     "refuses"),
    ("a line indented under a value already complete",
     "name: \"a\"\n  b: 1\n", ("refused", 2, "already complete"), "refuses"),
    ("a sequence dash where a value belongs", "name: - a\n",
     ("refused", 1, "where a value belongs"), "refuses"),
]


def brief(view: dict[str, Any]) -> dict[str, Any]:
    def one(block: Any) -> Any:
        if block is None:
            return None
        return (block["form"], {s: v for s, v in block["levels"].items()
                                if v != "none"})
    return {"workflow": one(view["workflow"]),
            "jobs": {j: one(v["block"]) for j, v in view["jobs"].items()}}


def shape_cases() -> None:
    print()
    print("shapes of YAML, one at a time")
    print("-" * 62)
    if yaml is None:
        skip("each shape against PyYAML (the reader's answers are still "
             "checked)", "PyYAML is not installed")
    for what, text, want, pyyaml_says in SHAPES:
        try:
            mine, refused = permissions.read_workflow(text), None
        except permissions.WorkflowUnreadable as e:
            mine, refused = None, e
        said: Any = refused.reason if refused is not None else (
            brief(mine) if mine is not None else None)
        if isinstance(want, tuple) and want[0] == "refused":
            good = (refused is not None and refused.line == want[1]
                    and want[2] in refused.reason)
            label = f"{what}: refused at line {want[1]}"
        else:
            good = mine is not None and brief(mine) == want
            label = f"{what}: read"
        if yaml is not None:
            _, _, theirs, error = both_ways(text)
            if pyyaml_says == "refuses":
                good = good and error is not None
                label += ", and PyYAML refuses it too"
            elif refused is None:
                good = good and same_view(mine, theirs)
                label += ", as PyYAML reads it, lines included"
            else:
                good = good and error is None
                label += ", though PyYAML reads the YAML"
        ok(label, good, said)


# ---- 4. the command line -------------------------------------------------------------

def git(root: Path, *words: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *words], cwd=str(root), capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=300)


def write(root: Path, files: dict[str, str | None]) -> None:
    for rel, text in files.items():
        path = root / rel
        if text is None:
            path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))


def two_commits(base: dict[str, str | None],
                head: dict[str, str | None]) -> Path:
    """A git repository whose HEAD~1 holds `base` and HEAD `base` changed
    by `head` (None deletes a file)."""
    root = Path(tempfile.mkdtemp(prefix="repo-", dir=WORK))
    git(root, "init", "-q")
    for key, value in (("user.name", "permissions"),
                       ("user.email", "permissions@example.invalid"),
                       ("commit.gpgsign", "false"),
                       ("core.autocrlf", "false")):
        git(root, "config", key, value)
    write(root, base)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    write(root, head)
    git(root, "add", "-A")
    git(root, "commit", "-q", "--allow-empty", "-m", "head")
    return root


def cli(*words: str, cwd: Path,
        env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VELARIS), "permissions-ratchet", *words],
        cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=dict(os.environ, **(env or {})), timeout=300)


def as_json(done: subprocess.CompletedProcess[str]) -> Any:
    try:
        return json.loads(done.stdout)
    except ValueError:
        return {"_stdout": done.stdout[-600:], "_stderr": done.stderr[-600:]}


WF = ".github/workflows/"


def cli_cases() -> None:
    print()
    print("the command line, against git repositories")
    print("-" * 62)
    ok("permissions-ratchet is a command of the command line: velaris/cli.py "
       "dispatches it and its usage list names it",
       "permissions-ratchet" in velaris.usage_lines(),
       sorted(velaris.usage_lines()))
    if not HAVE_GIT:
        skip("the command line against git repositories", "git is not "
             "installed")
        return
    ci_read = fixture_text("widened-read-to-write", "base", "ci.yml")
    ci_write = fixture_text("widened-read-to-write", "head", "ci.yml")
    release = fixture_text("widened-new-file-write", "head", "release.yaml")
    tabbed = fixture_text("unreadable-tab", "head", "ci.yml")
    repo = two_commits(
        {WF + "ci.yml": ci_read, WF + "sub/nested.yml": ci_read,
         WF + "notes.txt": "permissions: read-all\n", "README.md": "hi\n"},
        {WF + "ci.yml": ci_write,
         WF + "sub/nested.yml": fixture_text(
             "widened-write-all-replaces-map", "head", "ci.yml"),
         WF + "notes.txt": "permissions: write-all\n",
         WF + "release.yaml": release})

    done = cli("--against", "HEAD~1", "--json", cwd=repo)
    doc = as_json(done)
    got = [(f["file"], f["line"], f["scope"], f["before"], f["after"])
           for f in doc.get("widened", [])]
    ok("--json against HEAD~1: exit 1, the two widenings with their files "
       "and lines - a changed .yml and a new .yaml - and nothing from a "
       "subdirectory or a file that is not YAML",
       done.returncode == 1 and got == [
           (WF + "ci.yml", 7, "contents", "read", "write"),
           (WF + "release.yaml", 6, "contents", "none", "write")]
       and doc["against"] == "HEAD~1" and doc["narrowed"] == []
       and "nested" not in done.stdout and "notes" not in done.stdout,
       (done.returncode, doc, done.stderr[-400:]))
    ok("...and the document has the shape of velaris.permissions-ratchet/1",
       not shape_problems(doc), shape_problems(doc))

    done = cli("--against", "HEAD~1", cwd=repo)
    ok("as text: exit 1, WIDENED with the file and line of each, and a count",
       done.returncode == 1
       and "WIDENED .github/workflows/ci.yml:7 build contents: read -> write"
       in done.stdout
       and "WIDENED .github/workflows/release.yaml:6 workflow contents: none "
           "-> write" in done.stdout
       and "2 widening(s) against HEAD~1" in done.stdout
       and done.stdout.isascii(), done.stdout + done.stderr)

    elsewhere = Path(tempfile.mkdtemp(prefix="elsewhere-", dir=WORK))
    done = cli("--against", "HEAD~1", "--root", str(repo), "--json",
               cwd=elsewhere)
    ok("--root names the repository from another directory: the same result",
       done.returncode == 1
       and as_json(done).get("widened") == doc.get("widened"),
       done.stdout[-400:] + done.stderr[-400:])

    done = cli("--against", "HEAD", cwd=repo)
    ok("against the commit the working tree holds: exit 0, no widening",
       done.returncode == 0 and "no widening" in done.stdout
       and "WIDENED" not in done.stdout, done.stdout + done.stderr)

    write(repo, {WF + "ci.yml": ci_read, WF + "release.yaml": None})
    done = cli("--against", "HEAD", cwd=repo)
    ok("the head is the working tree: a block narrowed and a file deleted "
       "there, not committed, are narrowings, and exit 0",
       done.returncode == 0
       and "narrowed .github/workflows/ci.yml:7 build contents: write -> read"
       in done.stdout
       and "narrowed .github/workflows/release.yaml:8 publish permissions: "
           "{contents: write} -> removed" in done.stdout
       and "WIDENED" not in done.stdout, done.stdout + done.stderr)

    write(repo, {WF + "bad.yml": tabbed})
    done = cli("--against", "HEAD", cwd=repo)
    doc = as_json(cli("--against", "HEAD", "--json", cwd=repo))
    ok("a workflow in the working tree that cannot be read: exit 2, naming "
       "it with its line and why, in the text and in --json",
       done.returncode == 2
       and "UNREADABLE .github/workflows/bad.yml:6 at the head: a tab"
       in done.stdout
       and [(u["file"], u["side"], u["line"])
            for u in doc.get("unreadable", [])]
       == [(WF + "bad.yml", "head", 6)] and not shape_problems(doc),
       done.stdout + json.dumps(doc)[:400])
    write(repo, {WF + "bad.yml": None})

    done = cli("--against", "no-such-ref", cwd=repo)
    ok("a REF that is no commit: exit 2, naming it, nothing on stdout",
       done.returncode == 2 and "no-such-ref" in done.stderr
       and not done.stdout.strip(), done.stderr)

    plain = Path(tempfile.mkdtemp(prefix="not-a-repo-", dir=WORK))
    write(plain, {WF + "ci.yml": ci_read})
    done = cli("--against", "HEAD", cwd=plain,
               env={"GIT_CEILING_DIRECTORIES": str(WORK)})
    ok("a directory that is not a git repository: exit 2, saying so",
       done.returncode == 2 and "not in a git repository" in done.stderr
       and not done.stdout.strip(), done.stderr)

    bare = two_commits({"README.md": "hi\n"}, {"app.txt": "x\n"})
    done = cli("--against", "HEAD~1", cwd=bare)
    ok("a repository with no workflows on either side: exit 0",
       done.returncode == 0 and "no widening" in done.stdout,
       done.stdout + done.stderr)

    for words, why in ((("--json",), "no --against"),
                       (("--against",), "--against with no REF"),
                       (("--against", "HEAD", "--sarif"), "a flag it has not"),
                       (("--against", "HEAD", "extra"), "a stray word")):
        done = cli(*words, cwd=repo)
        ok(f"{why}: exit 2 and the usage", done.returncode == 2
           and "usage: velaris permissions-ratchet" in done.stderr,
           done.stdout + done.stderr)


# ---- 5. the Action -------------------------------------------------------------------

STEP_IF = ("${{ !cancelled() && inputs.permissions-ratchet == 'true' && "
           "github.event_name == 'pull_request' && "
           "steps.install.outcome == 'success' }}")


def posix_bash() -> str | None:
    """A bash for the step: Git's on Windows, where the first bash on PATH
    can be WSL's, which runs in another file system."""
    if os.name != "nt":
        return shutil.which("bash")
    for base in (os.environ.get("ProgramW6432"),
                 os.environ.get("ProgramFiles"), r"C:\Program Files"):
        candidate = Path(base or "") / "Git" / "bin" / "bash.exe"
        if base and candidate.is_file():
            return str(candidate)
    return None


def slashed(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def run_step(script: str, bash: str, clone: Path, base_sha: str,
             velaris_shim: str | None = None) -> tuple[int, str]:
    """The step's script as a runner runs it: bash -eo pipefail in the
    clone, `velaris` and `python` on PATH standing for the installed ones
    (this checkout, and this Python), BASE_SHA as the event gives it, and
    GITHUB_OUTPUT and RUNNER_TEMP set. (exit status, the log)"""
    work = Path(tempfile.mkdtemp(prefix="step-", dir=WORK))
    fake = work / "bin"
    fake.mkdir()
    python = slashed(sys.executable)
    shims = {"python": f'#!/usr/bin/env bash\nexec "{python}" "$@"\n',
             "velaris": velaris_shim or (f'#!/usr/bin/env bash\nexec '
                                         f'"{python}" "{slashed(VELARIS)}" '
                                         f'"$@"\n')}
    for name, body in shims.items():
        (fake / name).write_bytes(body.encode("utf-8"))
        (fake / name).chmod(0o755)
    (work / "step.sh").write_bytes(script.encode("utf-8"))
    runner = work / "run.sh"
    runner.write_bytes((
        'fakebin=$FAKE\n'
        'if command -v cygpath > /dev/null; then '
        'fakebin=$(cygpath -u "$FAKE"); fi\n'
        'export PATH="$fakebin:$PATH"\n'
        f'. "{slashed(work / "step.sh")}"\n').encode("utf-8"))
    temp = work / "runner-temp"
    temp.mkdir()
    output = work / "output"
    output.write_text("", encoding="utf-8")
    env = dict(os.environ, FAKE=slashed(fake), BASE_SHA=base_sha,
               GITHUB_OUTPUT=slashed(output), RUNNER_TEMP=slashed(temp),
               GITHUB_EVENT_NAME="pull_request")
    done = subprocess.run(
        [bash, "--noprofile", "--norc", "-eo", "pipefail", slashed(runner)],
        cwd=str(clone), env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=600)
    return done.returncode, done.stdout + done.stderr


def pull_request(base: dict[str, str | None],
                 head: dict[str, str | None]) -> tuple[Path, str]:
    """An origin with a base and a head commit, and a clone of the head one
    commit deep, as actions/checkout leaves it: (the clone, the base sha)."""
    origin = two_commits(base, head)
    base_sha = git(origin, "rev-parse", "HEAD~1").stdout.strip()
    clone = Path(tempfile.mkdtemp(prefix="clone-", dir=WORK)) / "repo"
    git(WORK, "clone", "-q", "--depth=1", origin.as_uri(), str(clone))
    return clone, base_sha


def action_cases() -> None:
    print()
    print("the Action: its input, its step, and the step's bash")
    print("-" * 62)
    if yaml is None:
        skip("the Action's input and step", "PyYAML is not installed")
        return
    doc = yaml.safe_load((HERE / "action.yml").read_text(encoding="utf-8"))
    spec = doc["inputs"].get("permissions-ratchet") or {}
    description = str(spec.get("description", ""))
    ok("the input permissions-ratchet: not required, off by default, and "
       "its description says what it does not see",
       spec.get("required") is False and spec.get("default") == "false"
       and ".vel" in description and "reusable workflow" in description
       and "pull_request_target" in description
       and "default token" in description, spec)
    steps = doc["runs"]["steps"]
    ids = [s.get("id") for s in steps]
    step = steps[ids.index("permissions")] if "permissions" in ids else {}
    ok("its step comes right after Install and before Check",
       "permissions" in ids and ids.index("permissions") == 1
       and ids[0] == "install" and ids[2] == "check", ids)
    ok("it runs on a pull request, when asked, after a successful install, "
       "unless the run was cancelled",
       step.get("if") == STEP_IF, step.get("if"))
    script = str(step.get("run", ""))
    ok("the inputs reach the script through env:, and nothing is "
       "interpolated into it",
       step.get("shell") == "bash"
       and step.get("env") == {
           "BASE_SHA": "${{ github.event.pull_request.base.sha }}"}
       and "${{" not in script, step.get("env"))
    ok("it fetches the base and runs the command against it",
       'git fetch --no-tags --depth=1 origin "$BASE_SHA"' in script
       and 'velaris permissions-ratchet --against "$BASE_SHA"' in script)

    bash = posix_bash()
    if bash is None:
        skip("the step's bash", "no POSIX bash here")
        return
    if not HAVE_GIT:
        skip("the step's bash", "git is not installed")
        return
    ci_read = fixture_text("widened-read-to-write", "base", "ci.yml")
    ci_write = fixture_text("widened-read-to-write", "head", "ci.yml")

    clone, base_sha = pull_request({WF + "ci.yml": ci_read},
                                   {WF + "ci.yml": ci_write})
    before = git(clone, "cat-file", "-e", base_sha + "^{commit}")
    code, log = run_step(script, bash, clone, base_sha)
    ok("a pull request that widens: the clone lacks the base until the step "
       "fetches it; exit 1, an error annotation on the file and line, and "
       "the finding in the log",
       before.returncode != 0 and code == 1
       and "::error file=.github/workflows/ci.yml,line=7::WIDENED build "
           "contents: read -> write. " in log
       and "WIDENED .github/workflows/ci.yml:7" in log, log[-1500:])

    code, log = run_step(script, bash, clone, base_sha, velaris_shim=(
        '#!/usr/bin/env bash\necho "Traceback: something broke" >&2\n'
        'exit 1\n'))
    ok("a command that stops without a result: exit 2 and an error, never "
       "a pass and never taken for a widening",
       code == 2 and "::error::permissions-ratchet stopped without a result "
                     "(exit status 1)" in log, log[-1200:])

    code, log = run_step(script, bash, clone, "1" * 40)
    ok("a base commit that cannot be fetched: exit 2 and an error, and "
       "nothing compared",
       code == 2 and "::error::permissions-ratchet: the base commit" in log
       and "WIDENED" not in log, log[-1200:])

    code, log = run_step(script, bash, clone, "")
    ok("no base commit at all: exit 2 and an error",
       code == 2 and "::error::permissions-ratchet: the pull request's base "
                     "commit is not known" in log, log[-800:])

    clone, base_sha = pull_request({WF + "ci.yml": ci_read},
                                   {"README.md": "a change elsewhere\n"})
    code, log = run_step(script, bash, clone, base_sha)
    ok("a pull request that leaves the permissions alone: exit 0, no error",
       code == 0 and "::error" not in log and "no widening" in log,
       log[-1200:])

    clone, base_sha = pull_request({WF + "ci.yml": ci_write},
                                   {WF + "ci.yml": ci_read})
    code, log = run_step(script, bash, clone, base_sha)
    ok("a pull request that narrows: exit 0, no error, the narrowing in the "
       "log", code == 0 and "::error" not in log
       and "narrowed .github/workflows/ci.yml:7" in log, log[-1200:])

    clone, base_sha = pull_request(
        {WF + "ci.yml": ci_read},
        {WF + "ci.yml": fixture_text("unreadable-tab", "head", "ci.yml")})
    code, log = run_step(script, bash, clone, base_sha)
    ok("a workflow that cannot be read: exit 2, an error on its file and "
       "line", code == 2
       and "::error file=.github/workflows/ci.yml,line=6::could not read "
           "this workflow at the head: a tab" in log, log[-1200:])

    new_workflow = ("on: pull_request\njobs:\n  build:\n    runs-on: "
                    "ubuntu-latest\n    steps:\n      - run: make\n")
    clone, base_sha = pull_request({"README.md": "no workflows, no .vel\n"},
                                   {WF + "ci.yml": new_workflow})
    vel_files = list(clone.rglob("*.vel"))
    code, log = run_step(script, bash, clone, base_sha)
    ok("a repository with no .vel file, whose pull request adds a workflow "
       "with no permissions block: exit 1, the new job's repository default "
       "annotated",
       not vel_files and code == 1
       and "::error file=.github/workflows/ci.yml,line=3::WIDENED build "
           "permissions: {} -> repository default. " in log, log[-1200:])


def main() -> int:
    fixture_cases()
    reader_cases()
    shape_cases()
    cli_cases()
    action_cases()
    print()
    print(f"{PASSED} correct, {FAILED} wrong"
          + (f", {SKIPPED} skipped" if SKIPPED else ""))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
