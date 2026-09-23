# Competitors, scored on the Sabline benchmark

The benchmark's 76 programs (`../corpus.json`), run through five tools
that make a claim overlapping Sabline's, each in its own real runtime,
beside Sabline and unsandboxed Python. It is `plan/8.7.md` section 3. The
score is published on [/competitors.html](https://sabline.dev/competitors.html);
this directory holds the evidence behind it, and `../compete.py` records
and re-derives it.

    python benchmark/competitors/fetch_runtimes.py   # wasmtime, CPython-WASI, Deno; builds the Starlark host (needs Go)
    pip install -r requirements/competitors.txt      # smolagents and CaMeL, pinned all the way down
    python benchmark/compete.py --check              # re-run all 76 x 7 cells; exit 1 if one moved
    python benchmark/compete.py --only 13a,14c       # print a few cells, write nothing
    python benchmark/compete.py --record             # rewrite results.json
    python benchmark/compete.py --self-test          # show --check's comparison fails on a change
    python build_competitors_page.py                 # rewrite docs/competitors.md from results.json

Everything is free: pinned public downloads checked by SHA-256
(`runtimes.json`), pinned packages, no key and no model. The table is
recorded and re-derived on Linux x86_64, which is what the CI leg runs.

## What is here

    expectations.json   what each category was expected to show, written and
                        committed before anything ran (countermeasure 1)
    results.json        every cell: verdict, evidence line, the commands that
                        ran and what they printed, the grant, the notes
    runtimes.json       wasmtime, CPython's WASI build and Deno, by URL and hash
    fetch_runtimes.py   fetches and verifies those, and builds the Starlark host
    hosts/              the three hosts: starlark/ (Go), sandbox_host.py,
                        camel_host.py - each one's docstring is its whole rule
    starlark/           the Starlark translation of every program
    camel/              the CaMeL translation (plans) of every program

## The rules

Every verdict comes from a program that ran, under `../run.py`'s own rules,
imported rather than restated: `verdict_for` (a static flag on the dangerous
line is caught-before-run; a stop with the effect not observed is
caught-during-run; an observed effect is missed; a control that is flagged or
stopped is a false positive), `observed` (the file written, the listener
reached, the sentinel printed), the same inputs, the same two listeners and
the same credential fixtures. Nothing is scored from documentation or from
what a runtime says it supports. A runtime that is not installed gives every
cell `not-run` with the reason, never an estimate.

Each tool gets the narrowest grant that still lets the task's legitimate work
run, derived from the program's `needs` by one rule per tool and never tuned
per program. Where a tool cannot express a need, that is recorded in the
cell's `grant`, and where it changes what a verdict means, in the cell's
notes.

| Column | Runtime | How it is run | The grant for `needs` | Time limit | Memory cap |
|---|---|---|---|---|---|
| Sabline | this checkout | `../run.py`'s column: `sabline check`, `sabline audit` (and `deps-diff` in category 12), then `sabline.run` | `allow=needs` | its own, 5 s | its own, `max_memory_mb=256` |
| Deno | Deno (pinned) | `../run.py`'s column: `deno check`, `deno lint`, `deno run --no-prompt` | the matching `--allow-read=<dir>`, `--allow-net=<host:port>`, `--allow-import`, or none | the harness's, 5 s | its own, `--max-old-space-size=256` |
| Python | CPython, no sandbox | `python file.py` | none: there is no budget | the harness's, 5 s | the harness's `RLIMIT_AS` |
| WASI | the same `.py` in CPython's WASI build under wasmtime | `wasmtime run --allow-precompiled python.cwasm file.py` | `--dir <dir>` for a read grant (read *and* write: the CLI's `--dir` has no read-only form); **a network grant cannot be expressed** - this build has no sockets; no environment | its own, `-W timeout=5s` | its own, `-W max-memory-size=256MiB` |
| Starlark | a translation, in starlark-go | `hosts/starlark`'s `check`, then `run` | a predeclared function per grant: `read_file` refused outside the directory, `http_get`/`http_post` refused for any other host; never a write, the environment, a process or a listing | its own, the host cancels the thread at 5 s | none: starlark-go has none, and the Go runtime cannot start under a 256 MB address-space limit |
| Python sandbox | the same `.py` in smolagents' `LocalPythonExecutor` | `hosts/sandbox_host.py` | an import allowlist and passed-in functions only: `sys` for input; `open` for a read grant (unscoped); `urllib.request` for a network grant (unscoped); the vendored module in categories 12 and 15 | the host's watchdog, 5 s of interpretation (smolagents' own cannot fire before the program ends; see below) | the harness's `RLIMIT_AS` |
| CaMeL | a translation (a plan), in CaMeL's reference interpreter | `hosts/camel_host.py` | not per task: one tool set for the whole benchmark, and CaMeL's own policies decide | the host's, **30 s** of interpretation (CaMeL has none of its own; see below) | none: the host's imports alone reserve more than 256 MB of address space |

Deno is given no dynamic-loader variable (`LD_LIBRARY_PATH` and its kind,
`run.py`'s `LOADER_VARS`): it needs none, and when the machine has one set -
CI's `setup-python` sets `LD_LIBRARY_PATH` - Deno still refuses to spawn a
process, but names the variable in its message, and the record would then
describe the machine instead of the program.

A runtime with a limit of its own (Sabline, WASI, Starlark) is given 5 s of
it, and the harness waits 10 s before it kills the process, so the limit
that fires is the runtime's. smolagents' limit cannot fire before the
program ends, so its host runs a watchdog that stops the program 5 s after
interpretation begins (every loop in the corpus runs 12 s or more in
smolagents before its own iteration cap would end it, so the watchdog is
what fires on any machine). CaMeL has no limit; its host stops the plan
**30 s** after interpretation begins, and that is not like-for-like: CaMeL's
interpreter needs about 4.5 s for 07c's correct 90,000-step loop on the
recording machine (plain Python: under 0.1 s), so at 5 s its verdict on a
correct program would depend on the machine, and 05c (about 7.4 s) would be
"caught" by the clock. Every unbounded loop in the corpus is a `while`,
which CaMeL refuses, so no danger depends on CaMeL's deadline. Importing
CaMeL takes seconds before the plan starts, so the harness waits 90 s.
The memory caps differ because the runtimes do: three of them cannot start
under a 256 MB address-space limit at all, so for those the column says which
cap applied rather than pretending one did. No program that a column ran was
stopped by a cap that column did not have: every memory-growth program is a
`while` loop, which Starlark rejects and CaMeL refuses.

### Why this Python sandbox

smolagents' `LocalPythonExecutor`, because it is the one a developer gets by
default when a model writes Python in an agent - smolagents' `CodeAgent`
runs model-written code in it unless pointed at a remote executor, and the
remote ones cost money or are not a Python sandbox. It is free, runs
anywhere, and was built for exactly this kind of program. Its own docstring
says it is not a security sandbox; this column measures what it does
anyway, because it is what people run. RestrictedPython is the older, more
general choice; its guards are opt-in, so a fair configuration of it is a
matter of opinion, where smolagents has a default.

Three defects in smolagents 1.26.0 turned up while building this, and each
shapes its column. Its timeout raises inside a `with ThreadPoolExecutor()`
block, whose exit waits for the worker thread, so a program that never ends
is never stopped by smolagents - the harness stops it. After
`import urllib.request` the name `urllib` is not the package, so
`urllib.request.urlopen` fails for every URL, granted or not. And it does
not apply `@dataclass`, so a program that builds a dataclass record fails
there. Where one of them decides a cell, the cell's note says so: a program
stopped by an interpreter defect before its dangerous line is credited as
caught by the benchmark's rule, and the note is what tells the two apart.

### How CaMeL is set up

CaMeL runs a plan written by a privileged model; here the benchmark program
is the plan, translated into the subset CaMeL's interpreter accepts (no
function definitions, no `while`, no `try`, no imports), and run by the
reference implementation (google-research/camel-prompt-injection, pinned by
commit) in its STRICT mode. It reaches the world only through tools. One tool
set serves every program, as one AgentDojo suite serves all its tasks, and
where CaMeL ships an annotation or a policy for a tool of the same shape it
is used as shipped: `read_file` and `get_webpage` results are private and
untrusted; `get_webpage` and `post_webpage` carry the Slack suite's policies
(the URL, and the content, must be public); a file write carries the
workspace suite's `create_file` policy, which allows it. A shell tool has no
CaMeL policy, so CaMeL's engine denies it by default. `hosts/camel_host.py`
lists every tool and says which rule is CaMeL's and which is this host's.

CaMeL's threat model is prompt injection: the plan is trusted, because the
model that wrote it never saw untrusted data. This benchmark's threat model
is the program itself - written by a model that may have been steered, or by
a dependency's author. Where that difference decides a row, the row says so.

## The evidence, and re-deriving a cell by hand

`results.json` has, for every program and every tool, the verdict, the
evidence line the table shows, the grant, any notes, and `calls`: each
command that ran, the stdin it was given, its exit status and the first 600
characters of what it printed, with the scratch directory written as
`<workdir>`, the checkout as `<repo>`, the fetched runtimes as `<runtimes>`,
and the two listener ports as `<port>` (granted) and `<other-port>` (not).
Sabline's column calls the library, so its `calls` give each call, what it
returned, and the command line that reproduces it. To re-derive a cell,
make a scratch directory with `granted/notes.txt`, `granted/.env`,
`granted/service.pem` and `outside/secret.txt` (`../compete.py`'s `main`
writes them), start two listeners, substitute them for the placeholders, and
run the recorded command.

`--check` re-runs every cell and compares the verdict and the evidence line
with the record, and each runtime's version with the one recorded (Python's
by major.minor, since a patch release moves under the CI leg; Sabline's not
at all, since it is this checkout and any verdict it moves fails anyway).

## The three countermeasures (plan/8.7.md section 3)

1. **Stated in advance.** `expectations.json` was committed before the
   harness ran; the page puts each expectation beside what happened, and
   where they differ, says so.
2. **A category no competitor catches is suspect**, and the page lists every
   one, reviewed.
3. **The corpus is published with the results, and a category is welcome.**
   `CONTRIBUTING.md` says how to add one. A category written by somebody who
   wants Sabline to lose is worth more than three written here.
