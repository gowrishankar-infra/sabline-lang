# 0001 - The compiler stops being one file

Decided for 8.2.0, September 2026.

## What was true

From its first version Velaris was one file, `velaris.py`, in the order
the compiler uses it: lexer, parser, loader, effects, types, proofs, native
code, the interpreter, and after them the library, the pool and everything
built on those. ARCHITECTURE.md opened with "Everything is in one file ...
If you read it top to bottom you follow a program through the whole
pipeline." That was a principle, and it bought real things:

- **One thing to read, copy and trust.** `velaris eject` copied one file
  into a directory that ran with nothing installed; the playground wrote
  one file into the browser; the `.mcpb` bundle carried one file; a
  reviewer diffed one file.
- **No import graph to get wrong.** Every name could see every other name,
  so no cycle could exist and no module could load before another it
  needed.
- **One namespace for the run state.** `Budget.install()` replaced
  `FS_GRANTS` with `globals()["FS_GRANTS"] = ...`, and every reader saw the
  new value, because there was only one global table.

## Why it aged out

By 8.1.1 the file was 19,780 lines, and what 8.2 set out to add showed
where the principle had stopped paying:

- **Stage-isolated tests need stages.** A test of the lexer that imports
  the whole compiler is not isolated; "the lexer's tests" need a lexer
  module to import.
- **Type checking and linting are per module.** `mypy --strict` and `ruff`
  report and cache by module, and a 20,000-line module is one unit of
  everything: one change re-checks all of it, and one report is thousands
  of lines long.
- **The dependencies were already there, only unwritten.** Measuring them
  (`split.py`, kept with this decision's commit) found that nearly every
  reference between sections pointed backwards through the pipeline, and
  seven pointed forwards: the library to the pool, the ratchet and the
  receipts; the pool to the receipts; `migrate` to the ratchet. One file
  let those stay implicit. A package makes each a line someone can read.
- **The run state was everywhere.** Twenty module-level names are state a
  running program can change, and they were read and rebound from seven
  sections. A pool worker's reset is only as good as its list of them; one
  module that holds exactly them is a list that cannot drift.
- **Starting a command recompiled the compiler.** `python velaris.py ...`
  runs the file as `__main__`, and Python never caches bytecode for
  `__main__`, so every command compiled 19,780 lines before doing anything.
  A package's modules are cached after the first import.

## What was decided

`velaris.py` becomes the package `velaris/`, one module per stage in
pipeline order - `lexer`, `parser`, `loader`, `effects`, `checker`,
`termination`, `prover`, `native`, `runtime` - with the modules they need
placed before them (`version`, `errors`, `nodes`, `tables`, `state`,
`recorder`, `values`, `wrappers`, `budget`) and the modules built on the
pipeline after them (`editor`, `formatter`, `project`, `session`,
`results`, `library`, `pool`, `findings`, `mcp_manifest`, `doors`,
`migrate`, `ratchet`, `conform`, `attestation`, `receipts`, `upgrades`,
`stats`, `eject`, and `cli` last). `velaris._MODULES` names that order.

- **A module imports only from the modules before it.** A name it takes
  from a module after it is listed in its `__forward__`, used only inside
  functions, and bound by `velaris/__init__.py` once every module is
  loaded. There are seven. `tests/unit/test_pipeline_order.py` holds the
  order, the direction of every import, and each forward name.
- **The run state is `velaris/state.py`,** read and written from everywhere
  else as `_state.NAME` - never imported by name, since a rebound name
  imported by name is a copy. `velaris.EFFECT_BUDGET` still reads the live
  value, through the package's `__getattr__`.
- **`import velaris` gives every name it gave before,** and the command
  line behaves as it did. `check_api.py` recorded the library surface, the
  command line, the HTTP door, the MCP server, the language server and the
  Action from the single file, before it was split, and the package matches
  that golden with and without the prover, on Python 3.13 and 3.10.
- **`velaris.py` stays, as a launcher,** so `python velaris.py program.vel`
  keeps working in a checkout and every suite that runs velaris by that
  path still does. It is not installed; pip installs the package.
- **A child process starts this same Velaris by the path of its
  `__main__.py`** (`velaris.version._launch_command`), which puts the
  directory holding the package first on the child's `sys.path`, as
  running `velaris.py` by path did. `python -m velaris` would not: it could
  import another Velaris installed elsewhere.
- **The split was made by a program, not by hand.** Every top-level
  statement went, whole and with its comments, to one module; the few
  places the file named itself (`__file__`) were rewritten to name the
  package. The program checked that no statement uses a later module when
  it is imported, and that no local variable shares a name with the state.

## What it cost

- **More files, and imports to keep right.** The ordering test is what
  keeps them right; a cycle at import time fails it.
- **`_state.NAME` is longer than `NAME`,** and an attribute read in the
  interpreter's hot paths. The 8.2 perf gates measured the pure-numeric
  benchmark against 8.1.1 before this was accepted (CHANGELOG 8.2).
- **Everything that copied the file now copies a directory:** `velaris
  eject` writes `runtime/velaris/` and its launcher checks every module's
  digest; the playground writes each module into the browser's file
  system; the `.mcpb` bundle carries the package; `check_pool.py` scans
  every module for module-level state; the version lives in
  `velaris/version.py`, one of the six version files.
- **Reading the compiler top to bottom** now means reading the modules in
  `_MODULES` order. ARCHITECTURE.md is the map.

## What was not done

- **One namespace split across files** - each file executed into the
  package's globals - would have kept `global` working unchanged. It was
  rejected: the files would not be modules, so mypy, ruff and a stage's own
  tests could not treat them as modules, which is most of the reason to
  split.
- **Classes around the state** (a `RunState` object passed to every
  function) would be the better design in a new program. Here it would
  have rewritten every signature in the interpreter and changed the library
  surface; one state module changes neither.
