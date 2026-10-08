"""The canonical check document: what `sabline check` finds in one file,
written so that a second implementation can be held to it (9.0, M2).

`sabline check-dump <file>` writes it from here; `sabline-rt check <file>`
writes it from the Rust crate. `check_agreement.py` compares the two over
every Sabline source this project has, the way it compares the AST dump
(sabline/ast_dump.py). It is not a stable interface and is not in
`tests/api/golden.json`: it is a comparison surface, and STABILITY.md's
"anything else in the package" clause covers it.

**What is in it** is what `sabline check` reports, with the prover left
out - sabline-rt does not prove, and never will in 9.0 (decisions/0002),
so a check here runs the stages a run needs and stops before
`check_proofs`:

    load        load_program: the file and everything it imports, or the
                one refusal that stopped it
    main        check_main as `sabline check` asks it (a library needs no
                main)
    main_run    check_main as a run asks it, where a missing main is E400
    effects     check_effects
    types       check_types, which runs only when the three above found
                nothing - exactly as `sabline check` runs it - and is
                null when it did not run
    raised      the stage that ended the check by raising rather than
                appending - "load", "effects" (only a program nested too
                deeply for Python's own stack), "types" (a parameter or
                result of a type that does not exist) - or null
    errors      every problem, in order, once each: what
                `sabline check --json` prints, less the `reference` line
                every error carries
    loops       every loop of every function, lifted ones included, with
                its termination verdict and the reason

Each stage is there separately, in the order the stages ran, so that a
difference is reported at the stage it is in. `raised` is there because
the command and the library read a raise differently: `sabline check`
reports what the stage had appended and then what it raised, and
`sabline.check` reports what it raised and nothing else. The document
holds both answers, so a suite held to either can be held to it.

**One thing it does that `sabline check` does not**: it sets
`Parser.lambda_n` to zero before each file, as the AST dump does, so that a
generated `fn#N` in a message is a function of that file and of nothing
else. Inside one file and what it imports the counter runs on as it does
in a check - across every file the loader parses, in the order it parses
them - and the Rust loader carries it the same way.
"""
import sys
from typing import Any

from .ast_dump import RECURSION_LIMIT, _out, _write, canonical
from .checker import check_main, check_types
from .effects import check_effects
from .errors import SablineError, _too_deep_error
from .loader import load_program
from .parser import Parser
from .tables import (
    ALL_EFFECTS,
    BUILTINS,
    CURRENCIES,
    FALLIBLE_BUILTINS,
    HMAC_BUILTINS,
    KNOWN_TYPES,
    MONEY_BUILTINS,
    NEW_BUILTINS,
    ROUNDING,
    SECRET_SOURCES,
)
from .termination import loop_termination

# What `sabline check-dump --help` says. Like `ast`, the command is not in
# `usage_lines`: the document is a comparison surface, not a feature.
USAGE = """usage: sabline check-dump <file.vel>
       sabline check-dump --list <paths-file>
       sabline check-dump --tables

The canonical check document: what `sabline check` finds in one program,
without the prover, which check_agreement.py compares with sabline-rt's.
rt/README.md states the format. It is not a stable interface and nothing
else reads it.

  --list FILE       one path per line; writes a framed stream, so that
                    comparing some thousands of files is one process
  --tables          the builtin tables the checkers read, as one document

Exit 0 when every program checked clean, 1 when one did not, 2 when the
command line itself was wrong."""

# The format's version, carried in every document.
CHECK_VERSION = 1

# The header of the framed stream `--list` writes; the records are framed
# as the AST dump's are.
BATCH_HEADER = "sabline.check-batch/1"


def _error(e: SablineError, path: str) -> dict[str, Any]:
    """One problem as `sabline check --json` writes it, less `reference`."""
    return {"code": e.code, "file": e.file or path, "fixes": list(e.fixes),
            "line": e.line, "message": e.message}


def check_document(path: str) -> dict[str, Any]:
    """The document for one file, staged as `sabline check` runs it."""
    if sys.getrecursionlimit() < RECURSION_LIMIT:
        try:
            sys.setrecursionlimit(RECURSION_LIMIT)
        except Exception:
            pass
    Parser.lambda_n = 0
    stages: dict[str, Any] = {"load": None, "main": None, "main_run": None,
                              "effects": None, "types": None}
    document: dict[str, Any] = {"check": CHECK_VERSION, "stages": stages,
                                "raised": None, "errors": [], "loops": []}
    try:
        funcs, records = load_program(path)
    except SablineError as e:
        stages["load"] = _error(e, path)
        document["raised"] = "load"
        document["errors"] = [stages["load"]]
        return document
    except RecursionError:
        stages["load"] = _error(_too_deep_error(False), path)
        document["raised"] = "load"
        document["errors"] = [stages["load"]]
        return document

    main: list[Any] = []
    check_main(funcs, main, running=False)
    main_run: list[Any] = []
    check_main(funcs, main_run, running=True)
    effects: list[Any] = []
    try:
        check_effects(funcs, effects)
    except RecursionError:
        effects.append(_too_deep_error(False))
        document["raised"] = "effects"
    found = main + effects
    types: list[Any] | None = None
    if not found:
        types = []
        try:
            check_types(funcs, records, types)
        except SablineError as e:      # a raise is still one problem
            types.append(e)
            document["raised"] = "types"
        except RecursionError:
            types.append(_too_deep_error(False))
            document["raised"] = "types"
        found = list(types)
    stages["main"] = [_error(e, path) for e in main]
    stages["main_run"] = [_error(e, path) for e in main_run]
    stages["effects"] = [_error(e, path) for e in effects]
    stages["types"] = (None if types is None
                       else [_error(e, path) for e in types])

    seen = set()
    for problem in found:              # one problem, one message, as
        key = (problem.code, problem.file or path, problem.line,
               problem.message)        # inspect_source has it
        if key not in seen:
            seen.add(key)
            document["errors"].append(_error(problem, path))

    table = {f.name: f for f in funcs}
    for f in funcs:
        for loop in loop_termination(f, table):
            document["loops"].append({
                "function": f.name, "file": f.src_file or path,
                "line": loop["line"], "verdict": loop["verdict"],
                "why": loop["why"]})
    return document


def tables_document() -> dict[str, Any]:
    """Every table the checkers read, as one document: `sabline-rt tables`
    writes the same one from the crate's copy, and the gate compares them,
    so a builtin added to one runtime and not the other is a difference
    whether or not any program calls it yet."""
    return {
        "tables": 1,
        "builtins": [{"name": name, "effects": sorted(row["effects"]),
                      "types": list(row["types"]), "ret": row["ret"]}
                     for name, row in BUILTINS.items()],
        "fallible": sorted(FALLIBLE_BUILTINS),
        "effects": list(ALL_EFFECTS),
        "known_types": sorted(KNOWN_TYPES, key=_KNOWN_ORDER.index),
        "currencies": [[code, digits] for code, digits in
                       sorted(CURRENCIES.items())],
        "rounding": list(ROUNDING),
        "secret_sources": list(SECRET_SOURCES),
        "new_builtins": sorted(NEW_BUILTINS),
        "hmac": sorted(HMAC_BUILTINS),
        "money": sorted(MONEY_BUILTINS),
    }


# KNOWN_TYPES is a set, so the document lists it in the order the table
# is written in sabline/tables.py; a type added there and not here is a
# KeyError rather than a quiet omission.
_KNOWN_ORDER = ("Int", "Text", "Bool", "Float", "Handle")


def check_dump_main(argv: Any) -> int:
    """`sabline check-dump <file>`, and `--list` for many at once."""
    words = list(argv)
    if not words or words[0] in ("--help", "-h"):
        print(USAGE)
        return 0
    if words == ["--tables"]:
        _write(canonical(tables_document()))
        return 0
    if words[:1] == ["--list"] and len(words) == 2:
        try:
            with open(words[1], encoding="utf-8") as fh:
                listed = fh.read()
        except OSError as e:
            print(f"sabline check-dump: cannot read the list '{words[1]}': "
                  f"{e}", file=sys.stderr)
            return 2
        every = True
        _out(BATCH_HEADER.encode("ascii") + b"\n")
        for line in listed.splitlines():
            path = line.rstrip("\r")
            if not path:
                continue
            document = check_document(path)
            every = every and not document["errors"]
            body = canonical(document).encode("ascii")
            _out(f"--- {len(body)} {path}\n".encode("utf-8"))
            _out(body + b"\n")
        return 0 if every else 1
    if len(words) == 1 and not words[0].startswith("-"):
        document = check_document(words[0])
        _write(canonical(document))
        return 0 if not document["errors"] else 1
    print(USAGE, file=sys.stderr)
    return 2
