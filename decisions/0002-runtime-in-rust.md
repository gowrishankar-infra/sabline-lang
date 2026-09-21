# 0002 - A second runtime, in Rust

Decided for 9.0.0, September 2026. It changes no code in 8.6; it says
what 9.0 is.

## What is true

Sabline is a Python package. `sabline/` is 30,113 lines across 50
modules, in the order the compiler uses them (ARCHITECTURE.md), and
every guarantee this project makes is made by that package: the effect
checker, the type checker's `Secret of T` rules, the budget, the
confinement policy, the receipt, the runner's tool door. The prover is
Z3 through its Python bindings; the native compiler is llvmlite.

That has bought what this project is, and three things worth keeping:
one implementation to read, a prover that is a library call away, and a
library API that agent frameworks written in Python - CrewAI, LangChain,
every MCP client - can call in-process.

It has also written down, in this repository, four limits that are not
defects and cannot be fixed inside it.

- **The embedding limit.** EMBEDDING.md says it in as many words:
  "There is no in-process embedding for Node, Go or Rust, and there will
  not be one until the compiler is something other than a Python
  package; the process boundary is the supported way." Everything not
  written in Python pays HTTP framing and a JSON round trip per call, on
  loopback, or starts a process. The agent frameworks that would use
  Sabline hardest are not all Python.
- **Confinement on Windows stops at a boundary Python cannot cross.**
  `sabline/confine.py` says of a run with no `net` grant: "not held: it
  needs an AppContainer, which this Python cannot start in".
  THREAT_MODEL.md says the same of every read. The reason is not
  Windows: it is that a `python.exe` started in an AppContainer cannot
  read its own installation unless that installation was made readable
  to ALL APPLICATION PACKAGES, and python.org's, the Store's and a
  virtual environment's are not. A single static binary has no
  installation to read.
- **Start-up is most of what a short run costs.** The measurements in
  0003 put a typical example's wall time between 0.3 and 1.0 seconds, of
  which the program's own run is under 1%. An interpreter written in
  Python cannot get that back, and the worker pool exists to hide it.
- **The trusted computing base is CPython.** Goal C - no effect outside
  the operator's budget - is enforced by Python code running in a Python
  interpreter, with `ctypes` calls into Landlock and seccomp. The
  confinement layer exists because a fault in Sabline should be a crash
  inside a box; the box is asked for, in Python, by the thing inside it.

## What was decided

**`sabline-rt`: one C-ABI library, written in Rust, that runs a Sabline
program.** A `cdylib` and a `staticlib` from one crate, published to
crates.io, with a C header and no Rust in its interface. It holds:

| In sabline-rt | Why it is there and not in the host |
|---|---|
| lexer, parser, AST | a run has to read the program |
| effect checker, type checker (`Secret of T`, and `Untrusted of T` from 0004), termination | the refusals are the product; a run that took the caller's verdict would be trusting the caller |
| the interpreter | the thing being replaced |
| the budget: every grant, every refusal, the guarded opener, the counts | Goal C |
| confinement: Landlock, seccomp-bpf, `sandbox_init`, and on Windows a job object, a lowered token **and an AppContainer** | the box, asked for by a binary that can live in one |
| the runner's tool door | it is part of a run: the manifest, the schema, the grants, the ceilings, the protocol |
| the recorder and the receipt | a receipt is what a run did; the thing that did it writes it |

**What stays in Python, and is not ported in 9.0:**

- **The reference semantics.** `sabline/` remains the definition of what
  a Sabline program means. Where the two disagree, Python is right and
  sabline-rt has a defect, until the demotion criteria of plan/9.0.md
  are met and MAINTENANCE.md's `SABLINE_REFERENCE_RUNTIME` says
  otherwise. That is the whole reason there are two: a second
  implementation is only worth its cost if something says which one is
  the standard.
- **The Z3 prover host.** `sabline/prover.py` is 1,928 lines against
  Z3's Python API. Rust's Z3 bindings bind the same C API, so a port
  would be a second translation of the same rules into the same solver -
  the one part of this compiler where a second implementation buys
  nothing and risks Goal A, which is the goal that gets a CVE. Proving
  happens before a run and its result - the set of proven names - is an
  input to the run, so a run can be handed it.
- **Every command that is not a run.** `check`, `audit`, `proofs`,
  `attest`, `verify`, `receipts diff`, `replay`, `eval`, `migrate`,
  `capabilities`, `review`, `deps-diff`, `permissions-ratchet`,
  `conformance`, `fmt`, `test`, `trace`, `explain`, `serve`, `mcp`,
  `lsp`, `eject`, `new`, `build`, `add`, `deps`, `demo`, `skill verify`,
  `stats`, `doctor`, `card`, `repl`. sabline-rt has a checker because a
  run needs one; `sabline check` keeps calling the Python one. Two
  implementations of `run` is a claim the agreement gate can test on
  every commit. Two implementations of thirty commands is a maintenance
  bill with nothing behind it.
- **`sabline.check`, `sabline.audit`, `sabline.attest`,
  `sabline.card`.** `sabline.run` and `sabline.Pool.run` change what
  they call underneath; their signatures, their results and
  `tests/api/golden.json` do not change at all. That is an exit
  criterion in plan/9.0.md, not a hope.

**One C ABI, five bindings.** The interface is C: opaque handles,
`const char *` in, a result the caller frees, an error code and a
message. Python binds it with `ctypes` over that header and nothing
else - no PyO3, no build-time coupling, no wheel that has to match an
interpreter's ABI. Node binds it with N-API; Go with cgo; Java with JNA
now and the Panama API when the floor is Java 22; Rust uses the crate
directly. The C ABI is the only surface, so there is one thing to keep
stable and one thing to fuzz.

**Nothing published moves.** `sabline-lang` on PyPI keeps its name, its
entry points and its API. sabline-rt is a new artefact with a new name
on a registry this project has not published to before.

## What "9.0 done" means

9.0 ships when `sabline run` and `sabline.run` execute a Sabline program
by calling sabline-rt; when the agreement gate - both runtimes over the
conformance corpus, `examples/`, `benchmark/corpus/` and the lie corpus,
on every commit, disableable by nothing - has been green for the number
of consecutive commits the demotion criteria name, with no difference in
verdict, output, error code, receipt content or audit; when `Untrusted
of T` and the rest of the breaking set are in both runtimes and the spec
states them normatively; when confinement in sabline-rt holds at least
as much as `sabline/confine.py` holds on every platform and strictly
more on Windows, with the honesty test proving it; when sabline-rt is
callable in-process from Python, Node, Go, Rust and Java over one C ABI
with `tests/api/golden.json` unchanged; when the JIT decision of 0003 is
implemented, or written down as not implemented with the numbers that
say why; and when the Python runtime is still installed, still the
reference, and still able to run every program sabline-rt runs - because
9.0 is the release that makes the Rust runtime the one that runs, not
the release that removes the one that defines.

## What it costs

- **Two runtimes.** Every language change, every new builtin, every
  error code, every confinement rule is written twice and proven equal
  by the gate. plan/9.0.md's risk register puts this first, and the
  demotion criteria are how it ends.
- **A second supply chain.** crates.io, `cargo`, and whatever sabline-rt
  depends on. The policy is in plan/9.0.md: `cargo-deny` and
  `cargo-vet` on every leg, and a dependency count that is argued in a
  pull request rather than assumed.
- **`unsafe`.** Landlock, seccomp, `sandbox_init`, AppContainer and the
  C ABI are all `unsafe`. The rule is in plan/9.0.md and it is not "as
  little as possible": every `unsafe` block carries a comment saying
  what invariant makes it sound, and a test that would fail if the
  invariant were broken.
- **The corpus becomes the specification.** Today a question about
  Sabline's behaviour is answered by reading one Python function. From
  9.0 it is answered by reading two implementations and a corpus that
  says they agree. That is where the effort goes, and ARCHITECTURE.md
  rule 8 - a scenario in a suite's table is a conformance case - is the
  rule that makes it work.

## What was not decided here

- **Rewriting the prover in Rust.** Not in 9.0. 0003 is the precedent
  for how it would be decided: from measurement, with what would reverse
  it stated.
- **Removing the Python runtime.** plan/9.0.md item 7 holds the
  criteria and the date, and the date is after 9.0.
- **Self-hosting.** ROADMAP.md lists writing the Sabline compiler in
  Sabline under "Later, and honestly uncertain". A Rust runtime neither
  helps nor hinders it, and this decision says nothing about it.
