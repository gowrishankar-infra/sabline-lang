# Competitors

Sabline's [comparison benchmark](https://sabline.dev/index.html) - 102 programs, 80 with one defect and 22 correct, in 20 categories - run through five tools that claim part of what Sabline claims, each in its own real runtime, beside Sabline and unsandboxed Python. Every verdict comes from a program that ran; none is scored from documentation. This page is generated from `benchmark/competitors/results.json`, which `benchmark/compete.py` records and a CI leg re-derives on every push: a verdict or an evidence line that moves fails the build.

> [!NOTE]
> **Measured** 2026-09-23 on Linux x86_64. **Sabline** 8.6.0, prover present · **Deno** 2.9.7 · **Python (no sandbox)** 3.12.3 · **WASI (wasmtime)** 49.0.0, CPython 3.14.7 WASI build · **Starlark** v0.0.0-20260908191801-89a6a09411d5 · **Python sandbox (smolagents)** 1.26.0 · **CaMeL** 1.0.0, commit f083b6b396399d3b3c7f2ddaf613a5945eaf32d8. A 5 s deadline for every tool but CaMeL, which gets 30 s of interpretation, and a 256 MB cap where the runtime can take one ([how each column is run](#how-each-column-was-run)).

## Where a competitor is ahead

Each row is compared first on what a tool achieved, and only then on when: stopping the danger with the task's legitimate work intact beats stopping it with the work broken too, which beats missing it, and on a correct program running it clean beats flagging it. Only where two tools achieved the same does the timing count - before running or while. A row a tool cannot express, or one outside CaMeL's threat model, is not compared.

- **Deno**, 15 row(s): stopped the danger with the task's work intact, where Sabline's refusal ended the run and the task with it (12a, 12b, 12c, 14c, 20b, 20c, 20d); caught what Sabline missed (17a, 17b, 19a, 19b); ran the correct program clean, where Sabline stopped or flagged it (18a, 18b, 18c, 18d).
- **WASI (wasmtime)**, 10 row(s): stopped the danger with the task's work intact, where Sabline's refusal ended the run and the task with it (12c, 14c, 20b, 20d); ran the correct program clean, where Sabline stopped or flagged it (18a, 18b, 18c, 18d); caught what Sabline missed (19a, 19b).
- **Starlark**, 4 row(s): caught what Sabline missed (17a); caught what Sabline missed, though with the task broken (17b); ran the correct program clean, where Sabline stopped or flagged it (18c, 18d).
- **Python sandbox (smolagents)**, 7 row(s): stopped what Sabline missed, by a failure that is not a refusal and would have stopped the task too (†) (16a, 16b, 16c); ran the correct program clean, where Sabline stopped or flagged it (18a, 18b, 18c, 18d).
- **CaMeL**, 3 row(s): caught what Sabline missed (16a, 16b, 16c).

Against Sabline, row by row. *Tie* is the same outcome at the same time; *earlier* and *later* mean the same outcome, one before running and one while running. *Not compared* counts the rows a tool cannot express, and for CaMeL the rows outside its threat model.

| Competitor | Ahead | Earlier | Tie | Later | Behind | Not compared |
|---|---:|---:|---:|---:|---:|---:|
| Deno | 15 | 0 | 35 | 29 | 23 | 0 |
| WASI (wasmtime) | 10 | 0 | 21 | 49 | 7 | 15 |
| Starlark | 4 | 0 | 64 | 19 | 10 | 5 |
| Python sandbox (smolagents) | 7 | 0 | 28 | 47 | 20 | 0 |
| CaMeL | 3 | 0 | 2 | 2 | 4 | 91 |

Nothing caught 04c, 09c, 19d.

### Where each is stronger by design

A score on this corpus is not what any of these tools is for. What each is actually built to do, and where that makes it stronger than Sabline whatever this table says:

- **Deno.** A permission system for a language people already write, enforced by the runtime at the moment of the call, for JavaScript and TypeScript and everything npm ships. It can grant one program to run (`--allow-run=git`), which Sabline cannot express: Sabline's `ffi:` grants a whole host module, and it has no model of a subprocess. It needs no new language and no rewrite.
- **WASI (wasmtime).** A boundary made by the virtual machine, not by the language: whatever code runs inside - interpreted Python, compiled C, a native extension - reaches only the handles the host passed in, one by one. Sabline's first guard is its own interpreter, with OS confinement (8.4) under it as a second; but a granted `ffi:` module runs as host code, and the OS policy is widened to what that module can do - for `ffi:os` or `ffi:subprocess`, nothing is enforced. Where the code is not Sabline, or the threat is a flaw in the interpreter, a boundary that hands out capabilities one handle at a time is the stronger design.
- **Starlark.** Determinism and termination by construction: no `while`, no recursion, no I/O but what the host predeclares, and the same result on every run. That is exactly what a build or configuration language needs, and it makes a whole class of defect - an unbounded loop, a hidden effect - impossible to write, where Sabline's termination rule only reports what it cannot show. The cost is that programs that need an unbounded loop cannot be written.
- **Python sandbox (smolagents).** Nothing new to learn: the model writes the Python it already writes, and the agent framework runs it. Its restrictions are an import allowlist and a short list of permitted functions, enforced by an interpreter of its own inside the host process - which is why it is convenient, and why its own documentation says it is not a security boundary: an authorised module runs as ordinary Python. It is stronger than Sabline only in that sense: it runs the code people already have.
- **CaMeL.** Information flow per value: every value carries where it came from and who may read it, and a policy decides at each tool call whether *this data* may go *there*. That stops the laundering Sabline has no answer to - read something with a granted read, send it with a granted send - and it is the reason CaMeL leads on AgentDojo. Its threat model is prompt injection into a trusted plan, not an untrusted program, which is why most of this corpus is outside what it tries to stop.

## The table

Per category: caught before running / caught while running / missed, with how many of the catches broke the task's legitimate work too; for the correct programs, clean / false positive; and the rows a tool cannot express, or that are outside CaMeL's threat model, which are not scored. The per-program rows follow, each with its notes.

| Category | Sabline | Deno | Python (no sandbox) | WASI (wasmtime) | Starlark | Python sandbox (smolagents) | CaMeL |
|---|---|---|---|---|---|---|---|
| 1. A file write hidden inside a helper function | 6/0/0 | 0/6/0 | 0/0/6 | 0/6/0 | 6/0/0 | 0/6/0 | 6 outside |
| 2. A network call hidden inside a helper | 6/0/0 | 0/6/0 | 0/0/6 | 0/6/0 | 6/0/0 | 0/6/0 | 6 outside |
| 3. Division by a value that comes from input and can be zero | 3/3/0 | 0/0/6 | 0/6/0 | 0/6/0 | 0/6/0 | 0/6/0 | 6 outside |
| 4. An off-by-one read past the end of a list | 4/1/1 | 0/0/6 | 0/5/1 | 0/5/1 | 0/5/1 | 0/5/1 | 6 outside |
| 5. Integer overflow | 0/6/0 | 0/0/6 | 0/0/6 | 0/0/6 | 0/0/6 | 0/1/5 | 6 outside |
| 6. An ignored failure (a parse that can fail, not handled) | 6/0/0 | 0/1/5 | 0/6/0 | 0/6/0 | 0/6/0 | 0/6/0 | 6 outside |
| 7. An infinite loop | 5/0/0; 1 clean | 0/5/0; 1 clean | 0/5/0; 1 clean | 0/5/0; 1 clean | 5/0/0; 1 clean | 0/5/0; 1 clean | 6 outside |
| 8. Runaway memory growth | 5/1/0 | 5/1/0 | 0/6/0 | 0/6/0 | 5/1/0 | 0/6/0 | 6 outside |
| 9. Reaching a dangerous module (subprocess / child_process / os.system) | 5/0/1 | 0/5/1 | 0/0/6 | 0/5/1 | 5/0/1 | 0/5/1 | 6 outside |
| 10. A plain correct program that must NOT be flagged | 6 clean | 6 clean | 6 clean | 6 clean | 6 clean | 6 clean | 6 outside |
| 11. A grant narrower than the effect: one directory, one host, no secrets (3.0) | 1/2/0 | 0/3/0 | 0/0/3 | 0/2/0; 1 not expressible | 1/2/0 | 0/2/1 | 3 outside |
| 12. Indirect authority: the caller is unchanged, and a dependency's declared budget widened between versions (7.1) | 3/0/0 (3 task broken); 1 clean | 0/3/0; 1 clean | 0/0/3; 1 clean | 0/1/0; 1 clean; 2 not expressible | 0/3/0 (3 task broken); 1 clean | 0/1/2 (1 task broken); 1 clean | 0/0/1; 3 outside |
| 13. A TrapDoor: a program whose stated purpose and behaviour differ | 1/0/0 | 0/1/0 | 0/0/1 | 0/1/0 | 1/0/0 | 0/1/0 | 0/1/0 |
| 14. Skill supply chain: an agent skill whose helper reads a credential and posts it | 3/0/0 (1 task broken); 1 clean | 0/3/0; 1 clean | 0/0/3; 1 clean | 0/3/0; 1 clean | 3/0/0 (3 task broken); 1 clean | 0/3/0 (3 task broken); 1 clean | 0/3/0 (3 task broken); 1 clean |
| 15. Hallucinated dependency: a program that imports a package that does not exist | 3/0/0; 1 clean | 3/0/0; 1 clean | 0/3/0; 1 clean | 0/3/0; 1 clean | 0/3/0; 1 clean | 0/3/0; 1 clean | 4 outside |
| 16. Leaking data through a granted channel: the task needs the read and the send, and the program sends what it read | 0/0/3; 2 clean | 0/0/3; 2 clean | 0/0/3; 2 clean | 5 not expressible | 0/0/3; 2 clean | 0/3/0; 0 clean, **2 FP** | 0/3/0; 1 clean, **1 FP** |
| 17. One legitimate subprocess: the task needs one program, and the program also runs another | 0/0/2; 2 clean | 0/2/0; 2 clean | 0/0/2; 2 clean | 4 not expressible | 0/2/0 (1 task broken); 2 clean | 0/0/2; 2 clean | 4 outside |
| 18. Correct programs a rule can refuse: a loop that ends only when its input does, a whole number past 64 bits, and their defective twins | 1/1/0; 0 clean, **4 FP** | 0/1/1; 4 clean | 0/1/1; 4 clean | 0/1/1; 4 clean | 1/0/1; 2 clean, **2 FP** | 0/1/1; 4 clean | 6 outside |
| 19. Danger below the language: a granted library, or its native code, doing I/O of its own | 0/0/3; 2 clean | 0/2/1; 2 clean | 0/0/3; 2 clean | 0/2/0; 1 clean; 2 not expressible | 5 not expressible | 0/0/3; 2 clean | 5 outside |
| 20. The task still works: the legitimate work and the danger use the same kind of effect, before or after each other | 2/2/0 (3 task broken); 2 clean | 0/4/0; 2 clean | 0/0/4; 2 clean | 0/3/0; 2 clean; 1 not expressible | 2/2/0 (4 task broken); 2 clean | 0/3/1 (3 task broken); 2 clean | 6 outside |
| **Caught, of the dangerous rows scored** | **70** of 80 (54 before; 7 with the task broken) | **51** of 80 (8 before; 0 with the task broken) | **32** of 80 (0 before; 0 with the task broken) | **61** of 70 (0 before; 0 with the task broken) | **65** of 77 (35 before; 11 with the task broken) | **63** of 80 (0 before; 7 with the task broken) | **7** of 8 (0 before; 3 with the task broken) |
| **False positives, of the correct programs scored** | **4** of 22 | **0** of 22 | **0** of 22 | **0** of 17 | **2** of 20 | **2** of 22 | **1** of 3 |
| **Not expressible / outside the threat model** | 0 / 0 | 0 / 0 | 0 / 0 | 15 / 0 | 5 / 0 | 0 / 0 | 0 / 91 |
| **Catches the row itself says were not a refusal** | 0 | 0 | 0 | 0 | 0 | 10 | 0 |

A catch with the task broken stopped the danger and the program's legitimate work with it - a refusal that ends the whole run, a program that did not compile or resolve, a runtime that cannot make the task's own request. The last row counts catches the benchmark's rule credits but whose row note says the program was stopped by something other than a refusal of its danger. Read each column's catches net of both.

## Every scenario

Every program's row, with the verdict for all seven tools and every place a row is not like-for-like, is on a page of its own: [every scenario](competitors-scenarios.md). Every cell's evidence line is on the evidence pages ([part 1](competitors-evidence-1.md), [part 2](competitors-evidence-2.md), [part 3](competitors-evidence-3.md)).

## Expected, and what happened

`benchmark/competitors/expectations.json` was committed before the harness ran anything, and its categories 16 to 20 before any competitor ran on them (countermeasure 1 in plan/8.7.md). Here it is beside the record, for the four columns it predicted; *as expected* means every dangerous row of the category landed in the predicted class, and anything else is shown as it happened. The predictions for categories 1 to 15 were written under the first rules and are left as they were.

| Category | WASI (wasmtime) | Starlark | Python sandbox (smolagents) | CaMeL |
|---|---|---|---|---|
| 1. a file write hidden inside a helper | as expected | as expected | as expected | outside, not scored (predicted missed) |
| 2. a network call hidden inside a helper | as expected | as expected | as expected | outside, not scored (predicted missed) |
| 3. division by a value from input that can be zero | as expected | as expected | as expected | outside, not scored (predicted during) |
| 4. an off-by-one read past the end of a list | as expected; 04c missed | as expected; 04c missed | as expected; 04c missed | outside, not scored (predicted during); 04c outside |
| 5. integer overflow | as expected | as expected | expected missed; got 1 during, 5 missed | outside, not scored (predicted missed) |
| 6. an ignored failure | as expected | as expected | as expected | outside, not scored (predicted during) |
| 7. an infinite loop | as expected | as expected | as expected | outside, not scored (predicted during) |
| 8. runaway memory growth | as expected | expected before; got 5 before, 1 during | as expected | outside, not scored (predicted during) |
| 9. reaching a dangerous module | as expected; 09c missed; 09f during | as expected; 09c missed; 09f before | as expected; 09c missed; 09f during | outside, not scored (predicted during); 09c outside; 09f outside |
| 11. a grant narrower than the effect | expected during; got 2 during, 1 not expressible | expected during (11c before); got 1 before, 2 during | expected 11a missed, 11b missed, 11c during; got 2 during, 1 missed | outside, not scored (predicted missed) |
| 12. indirect authority: a dependency widened between versions | expected during; got 1 during, 2 not expressible; controls: 1 clean | expected during; got 3 during (task broken); controls: 1 clean | expected missed; got 1 during (task broken), 2 missed; controls: 1 clean | expected 12a during, 12b missed, 12c missed; got 1 missed, 2 outside; controls: 1 outside |
| 13. a TrapDoor | as expected | as expected | as expected | as expected |
| 14. skill supply chain | as expected | expected before; got 3 before (task broken); controls: 1 clean | expected during; got 3 during (task broken); controls: 1 clean | expected during; got 3 during (task broken); controls: 1 clean |
| 15. hallucinated dependency | as expected | as expected | as expected | outside, not scored (predicted during) |
| 16. leaking data through a granted channel | expected not-expressible; got 3 not expressible; controls: 2 not expressible | as expected | expected during, by the urllib defect (not a refusal); got 3 during; controls: 2 false positive | expected during (controls clean); got 3 during; controls: 1 clean, 1 false positive |
| 17. one legitimate subprocess | expected not-expressible; got 2 not expressible; controls: 2 not expressible | expected during (a: task done; b: task broken, Starlark has no try); got 1 during, 1 during (task broken); controls: 2 clean | as expected | as expected |
| 18. correct programs a rule can refuse | expected controls clean; e during, f missed; got 1 during, 1 missed; controls: 4 clean | expected a and b false positives (no while), c and d clean; e before, f missed; got 1 before, 1 missed; controls: 2 clean, 2 false positive | expected controls clean; e during, f missed; got 1 during, 1 missed; controls: 4 clean | as expected |
| 19. danger below the language | expected a and b during with the task done; d and e not-expressible; got 2 during, 1 not expressible; controls: 1 clean, 1 not expressible | expected not-expressible; got 3 not expressible; controls: 2 not expressible | as expected | as expected |
| 20. the task still works | expected a, b, d during with the task done; c not-expressible; got 3 during, 1 not expressible; controls: 2 clean | expected a and b before with the task broken; c and d during, task broken; got 2 before (task broken), 2 during (task broken); controls: 2 clean | expected a, b: during with the task broken (the urllib import is refused before the task); c: during by the defect; d: missed; got 3 during (task broken), 1 missed; controls: 2 clean | as expected |

The rows named as exceptions in advance, and what the file said of them: **04c**: missed by every tool: the loop stops early and nothing reads out of range; **09c**: missed by every tool: it only prints text; **09f**: uncertain for wasi (listing '.' inside the guest may succeed on a preopened directory) and expected missed for camel (a directory listing is a read, which CaMeL does not police).

Where an expectation was wrong it is left wrong in the file, and the difference is the finding. The predictions assumed each runtime would stop a program for the reason the category is about; where the record differs, the notes in the scenario rows say what did stop it - most often something other than a refusal of the danger (a smolagents defect, or a language with no try that stops at the first refusal and takes the task with it), which the benchmark's rule credits as a catch and this page ranks as a catch with the task broken.

### Categories no competitor catches

Countermeasure 2: a category that only Sabline catches is either a real property or a rigged question, and is reviewed before it is published. A catch whose own row says it was not a refusal is not counted here. Categories caught by no competitor: 5 (Integer overflow).

- **5. Integer overflow.** Reviewed, and kept, as a judgement call rather than a win. Sabline's whole numbers are 64-bit and arithmetic that leaves the range stops the program (E407); every competitor computes the arithmetically right, larger number, because Python's, JavaScript's (as a double) and Starlark's integers do not wrap. Nothing in the corpus says the result must fit 64 bits, so the category counts a correct answer as a miss. A reader who disagrees can discount its six rows. The other side is category 18: 18c and 18d need numbers past 64 bits, are correct, and Sabline stops both.

Rows only Sabline catches: 05a, 05b, 05c, 05d, 05e, 05f, 18f.

## What changed in the scoring, and why

The first version of this table (pull request #104, never published) had
Sabline ahead or level on every row. That was the benchmark, not the tools,
and these are the corrections, each applied to every column alike.

- *The outcome comes first; the timing only breaks a tie.* A row is scored
  on what a tool achieved: the danger stopped with the task's legitimate
  work intact, stopped with the work broken too, or missed - and on a
  correct program, run clean or not. Before, catching a danger *before
  running* outranked catching it while running, so a design with no static
  step (WASI, the Python sandbox, CaMeL) could never be ahead of one with
  a static step, whatever it did.
- *Whether the legitimate work still succeeded is checked,* on every row
  that has work to check: the output the task asked for, the request it
  was granted, the file it was to write. A runtime that stops everything
  now scores as a catch with the task broken, not as though it had stopped
  only the danger - and a Sabline refusal, which ends the run and cannot be
  caught, is scored the same way. Where a row's own note says a catch came
  from a failure that would have stopped the task as well (a runtime
  without sockets, a defect in smolagents, a deadline), it is scored the
  same way even where there is no task line to check.
- *"Caught before running" is credited only where the tool's own design has
  that step:* Sabline's check, audit and deps-diff, Deno's type check and
  lint, Starlark's resolver. The others are scored on what happened when
  the program ran.
- *A static flag counts only on the marked dangerous line, for every tool.*
  Before, Sabline's audit was credited for an effect or an unbounded loop
  anywhere in the program, while Deno's lint and Starlark's resolver were
  credited only on the dangerous line. Now Sabline's audit is credited only
  for an effect that a call on the dangerous line needs, or a loop its
  termination rule names on that line or on the loop around it; a flag
  anywhere else is recorded and not credited.
- *CaMeL is scored only where its threat model makes a claim:* where a
  value that came from a tool (a file read, a web page, the environment)
  reaches another tool on the dangerous line. Its plan is trusted by
  design, so a hidden write or a runaway loop in the plan is outside what
  it tries to stop. Those cells still ran and say what happened; they read
  *outside* and are not counted.
- *A scenario a runtime cannot express is recorded as such, with the reason,*
  rather than scored or skipped: WASI has no sockets and no processes,
  a Starlark module has no I/O of its own, a native library cannot be
  loaded into a WebAssembly guest.
- *Five categories were added where a competitor should win or Sabline
  should lose* (16 to 20), and their predictions were committed before any
  competitor ran them.

## Where the benchmark is still unfair

**In Sabline's favour.**

- *Most rows of categories 1 to 11 have no task check.* Their dangerous
  programs do nothing but the dangerous thing, so there is no legitimate
  work to measure, and a refusal that ends the run costs nothing there.
  That favours the designs that end the program at the first refusal -
  Sabline, Starlark and CaMeL - over the ones whose programs can catch a
  denial and go on, as Deno's do. Category 20 measures exactly this, and
  Sabline loses it.
- *The corpus is about hidden effects, which is what an effect system is
  for.* Categories 1, 2 and 9 test a write, a request or a process call
  hidden in a helper, and Sabline finds each one before it runs (09c,
  which only prints text, is no hidden effect).
- *Categories 5 and 18f count a correct, larger number as a miss*
  (reviewed above, under the categories no competitor catches).
- *Every program was written by Sabline's author, and every translation by
  agents working for them.* The rows are small, and each is built to
  show one property.

**Against Sabline, and for the competitors.**

- *A catch by an unrelated failure still ranks above a miss.* The Python
  sandbox "catches" rows whose task needs the network because smolagents
  1.26.0 cannot run `urllib.request.urlopen` at all; each such row says so,
  and scores as a catch with the task broken - still ahead of a Sabline
  miss.
- *A swallowed denial counts.* Where a Deno program catches the permission
  error and goes on, the harness credits the catch because it watched the
  socket or the file. A caller reading the exit status would have seen
  success.
- *Crashes on chosen input count.* Categories 3 and 6 are caught by every
  Python-shaped runtime because the harness feeds the input that makes the
  defect fire; with ordinary input they run clean. Sabline's E706 and E520
  do not depend on the input.

## What the benchmark is still missing

- **A model in the loop.** Every CaMeL plan here is a hand translation; CaMeL
  exists to constrain plans a model writes from untrusted input, and the
  [AgentDojo evaluation](agentdojo.md) is where that is measured (Sabline:
  19 of 105 attacks land under a task budget, and 9 under that budget with
  each tool's arguments pinned to what the user task's own text names).
- **An operating-system sandbox column** - bubblewrap, nsjail, gVisor, a
  container - which would stop 19d, where native code in a granted library
  writes a file of its own and no column here stops it. Sabline's own OS
  confinement (8.4) is not in its column: a granted `ffi:` module runs as
  host code and the policy is widened to what the module can do.
- **More correct programs Sabline refuses:** a legitimate read of a
  credential file (E318), a safe division the prover cannot show is safe
  (E706), a loop over a structure that shrinks.
- **Task checks on categories 1 to 11,** so that ending the run at the
  first refusal costs something there too.
- **Other platforms.** Everything was recorded on one Linux machine; how
  Deno, wasmtime and the others behave on Windows or macOS is not measured.

## How each column was run

Each tool gets the narrowest grant that still lets the task's legitimate work run, derived from the program's `needs` by one rule per tool, never tuned per program. The full rules, and why this Python sandbox, are in [benchmark/competitors/README.md](https://github.com/gowrishankar-infra/sabline-lang/blob/main/benchmark/competitors/README.md).

| Column | Runtime | Grant | Time limit | Memory cap |
|---|---|---|---|---|
| Sabline | this checkout | `allow=needs` | its own, 5 s | its own, 256 MB |
| Deno | Deno, pinned | `--allow-read=<dir>`, `--allow-write=<dir>`, `--allow-net=<host:port>`, `--allow-run=<program>`, `--allow-ffi`, or none | the harness's, 5 s | its own, `--max-old-space-size=256` |
| Python (no sandbox) | CPython, no sandbox | none: no budget exists | the harness's, 5 s | the harness's `RLIMIT_AS` |
| WASI (wasmtime) | the same `.py`, in CPython's WASI build under wasmtime | `--dir <dir>` for a read or a write (no read-only form); **a network grant, a process or a native library cannot be expressed**; no environment | its own, `-W timeout=5s` | its own, `-W max-memory-size` |
| Starlark | a translation, in starlark-go | a predeclared function per grant, refusing any other path, host or program; nothing else | its own (the host cancels the thread) | none: the Go runtime cannot start under a 256 MB address limit |
| Python sandbox (smolagents) | the same `.py`, in smolagents' LocalPythonExecutor | an import allowlist and passed-in functions; `open` and `urllib.request` cannot be scoped | the host's watchdog, 5 s of interpretation (smolagents' own cannot fire first) | the harness's `RLIMIT_AS` |
| CaMeL | a translation (a plan), in CaMeL's reference interpreter | CaMeL's tool set and its own policies, the same for every program; scored only on the rows its threat model claims | the host's, **30 s** of interpretation (not like-for-like: see 07c) | none: its imports alone exceed a 256 MB address limit |

## Reproducing it

    python benchmark/competitors/fetch_runtimes.py   # pinned by SHA-256; builds the Starlark host
    pip install -r requirements/competitors.txt      # smolagents and CaMeL, pinned all the way down
    python benchmark/compete.py --check              # every cell, re-derived
    python benchmark/compete.py --only 13a,14c       # a few cells, printed

Nothing costs money: public downloads, pinned packages, no key, no model. A runtime that is not installed reads NOT RUN in every cell rather than an estimate.
