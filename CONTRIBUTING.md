# Contributing

Start with [ARCHITECTURE.md](ARCHITECTURE.md) for how the compiler is laid out, and
[MAINTAINERS.md](MAINTAINERS.md) for small, self-contained places to begin.

to Velaris

Thanks for looking under the hood.

## Setup

```
pip install ".[full]"     # z3-solver for proofs, llvmlite for native
python run_tests.py       # 39 example programs, each with a verdict
```

## The one rule

Every change must keep `run_tests.py` green in BOTH modes - with the
optional dependencies and without them (`pip install .` in a clean
venv). CI enforces this across Linux/Windows and Python 3.10/3.12.

## Layout

The compiler is the package `velaris/`, one module per stage, in
pipeline order: lexer -> parser -> loader -> effect checker -> type
checker -> termination -> proof checker (Z3) -> native compiler (LLVM) ->
interpreter -> editor and LSP -> formatter -> ... -> CLI (ARCHITECTURE.md
lists every module; until 8.2 it was one file, `velaris.py`, now a
launcher). `tests/unit/test_pipeline_order.py` fails if a module imports
one after it. Examples live in `examples/` (half are DESIGNED to
be rejected - each rejection demonstrates a guarantee). The standard
library is `stdlib/std.vel`, written in Velaris.

## Adding a feature

New syntax touches, in order: KEYWORDS/lexer, AST dataclasses, parser,
expr_str/expr_vars, effect walker (and walk_pure if usable in
contracts), type checker, prover (or an honest Unprovable fallback),
native eligibility, interpreter, formatter spacing if needed. Add at
least one RUNS example and one REJECTED example, register both in
run_tests.py, and run `velaris fmt` on them.

## Error style

Every error: a code (Exyz), a plain-English message, a location, and
numbered fixes. Never claim "proven" unless it is literally true.

## Breaking changes

[STABILITY.md](STABILITY.md) says what is covered by semantic
versioning and what is not. A change that breaks anything it covers -
including a security fix that refuses something that used to work -
goes in a major version, and its CHANGELOG entry says what a user has
to change. If you are not sure whether a change breaks something, say
so in the pull request; the answer goes in STABILITY.md.

## Naming sources

When a design decision comes from published work - a paper, a
standard, another project's documented design - name the source in the
CHANGELOG entry for the release that makes it. A finding from a review
counts too: say which person, model or bot found it. If you do not know
where something came from, leave it unattributed rather than guess.
