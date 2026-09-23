# Contributing

Start with [ARCHITECTURE.md](ARCHITECTURE.md) for how the compiler is laid out, and
[MAINTAINERS.md](MAINTAINERS.md) for small, self-contained places to begin.

to Sabline

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

The compiler is the package `sabline/`, one module per stage, in
pipeline order: lexer -> parser -> loader -> effect checker -> type
checker -> termination -> proof checker (Z3) -> native compiler (LLVM) ->
interpreter -> editor and LSP -> formatter -> ... -> CLI (ARCHITECTURE.md
lists every module; until 8.2 it was one file, `sabline.py`, now a
launcher). `tests/unit/test_pipeline_order.py` fails if a module imports
one after it. Examples live in `examples/` (half are DESIGNED to
be rejected - each rejection demonstrates a guarantee). The standard
library is `stdlib/std.vel`, written in Sabline.

## Adding a feature

New syntax touches, in order: KEYWORDS/lexer, AST dataclasses, parser,
expr_str/expr_vars, effect walker (and walk_pure if usable in
contracts), type checker, prover (or an honest Unprovable fallback),
native eligibility, interpreter, formatter spacing if needed. Add at
least one RUNS example and one REJECTED example, register both in
run_tests.py, and run `sabline fmt` on them.

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

## Adding a benchmark category

The comparison benchmark ([benchmark/](benchmark/README.md)) was written by
this project, and a benchmark written by a project is shaped by what that
project does. The most useful contribution to it is a category Sabline
loses: a defect Sabline misses and another tool catches, or a correct
program Sabline refuses. It is also scored against five competitors
([benchmark/competitors/](benchmark/competitors/README.md)), so a category
where Deno, WASI, Starlark, a Python sandbox or CaMeL should win is exactly
what is missing.

A category is a directory under `benchmark/corpus/` with each program
written three times (`.vel`, `.js`, `.py`), a `DANGER` marker on the
dangerous line, at least one control program that must not be flagged, and
an entry in `benchmark/corpus.json` giving each program's `needs` and
`stdin`. For the competitor columns, add the Starlark and CaMeL
translations under `benchmark/competitors/starlark/` and
`benchmark/competitors/camel/`, and say in `expectations.json`, before you
run anything, which tools you expect to catch it and why. Then run
`python benchmark/run.py` and `python benchmark/compete.py --record`, and
open the pull request with the result, whatever it is. A category is not
rejected for making Sabline look worse; it is reviewed for whether its
programs do what they say.

## Naming sources

When a design decision comes from published work - a paper, a
standard, another project's documented design - name the source in the
CHANGELOG entry for the release that makes it. A finding from a review
counts too: say which person, model or bot found it. If you do not know
where something came from, leave it unattributed rather than guess.
