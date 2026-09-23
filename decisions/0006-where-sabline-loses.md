# 0006 - Where the competitor table shows Sabline losing

**Proposed 2026-09-23; decided 2026-09-24. Nothing here is built.** Each
section below is the proposal as it was written, followed by the
maintainer's decision on it; *What was decided*, just below, gathers the
five. An accepted proposal is scheduled in the milestone of `plan/9.0.md`
the decision names, not built: until it ships it changes nothing in
`SPEC.md`, sabline-spec or either runtime, and no document may describe it
as a feature.

## What this answers

The competitor table ([docs/competitors.md](../docs/competitors.md), from
`benchmark/competitors/results.json`, #105) scores Sabline beside Deno,
WASI, Starlark, smolagents' Python sandbox and CaMeL, each in its own
runtime, on 102 programs. A competitor does better than Sabline on 18 of
them, and they fall into five places:

| | Where | Rows | Who does better |
|---|---|---|---|
| a | one legitimate subprocess | 17a, 17b | Deno, Starlark |
| b | a refusal ends the run | 12a, 12b, 12c, 14c, 20b, 20c, 20d | Deno, WASI |
| c | correct programs the static rules refuse | 18a, 18b, 18c, 18d | every other tool |
| d | a leak through a granted channel | 16a, 16b, 16c | CaMeL |
| e | native code in a granted library | 19d (19a, 19b below it) | nobody, on 19d |

For each: what it would change in the language or the runtime, what it
would cost, what it would break, which milestone of `plan/9.0.md` it
belongs to - or 8.7, or never - and cases that must fail if it is built,
stated as programs and budgets so that an implementation cannot pass by
choosing its own. A row in the known-open table
([docs/known-open.md](../docs/known-open.md)) says the same for every one
of them that is not closing soon, and none of them is.

**One rule for all five.** Nothing here may make a program able to do
more than its budget grants. Four of the five narrow what a grant means or
report more precisely; (b) is the only one that changes what a program may
observe, and it is the one that most needs its failing cases.

## What was decided

Decided by the maintainer on 2026-09-24. Each section's own decision, at
its end, says more; the proposal text above each decision is unedited.

| | Proposal | Decision | Where it sits | Rows it closes |
|---|---|---|---|---|
| e | `--confine strict` | **accepted** | M4, +5 days: Python's version first, sabline-rt's in the same release | 19d, on Linux and macOS, and on Windows where the budget grants no write |
| a | `proc:NAME` | **accepted**, with two caveats: a granted interpreter defeats it at the language level, and Windows cannot restrict which binary runs | M6, +13 days | 17a, 17b |
| d | `fs:secret:PATH` | **accepted**, refusing the correct 16d, the false positive CaMeL takes | M6, +5 days | 16a, 16b, 16c |
| c | the input-bounded loop verdict | **accepted, for 18a only** | M2, +2 days | 18a |
| c | `decreases` | **open**, no milestone: a decision of its own and an adversarial pass first | - | (18b stays open) |
| c | `Int` past 64 bits | **not done**: 18c and 18d stay declared false positives | never | - |
| b | `recover@N` | **deferred, not rejected**: seven days for four rows, and any recovery gives a program a way to probe the budget; a decision of its own and an adversarial pass first | - | - |

The days are counted in each milestone's effort in `plan/9.0.md`, which
now carries the cases that must fail as exit criteria. Nothing is built by
this record, none of it is 8.7 work, and no default moves.

---

## a. Subprocess granularity: one program, not the module

**What loses.** 17a and 17b run `git` for the task and a second program
(`hostname`) beside it. The only Sabline grant that runs a program is
`ffi:subprocess`, which grants the whole module: any program, any shell,
any arguments. Deno's `--allow-run=git` runs `git` and refuses
`hostname` (NotCapable); the Starlark host's `run_program` does the same.
Sabline missed both rows.

**What would change.** A new effect, `proc`, with a scoped grant
`proc:NAME`, and one builtin:

    fn version() -> Text uses proc or fail {
        return try run_process("git", ["--version"])
    }

run under `--allow io,proc:git`.

- `NAME` is resolved **at budget parse**, against the `PATH` of the
  operator who wrote the budget, to one absolute path, and that path is
  the only program the run may start. A `git` the program writes into
  its working directory, or finds earlier on a `PATH` it controls, is not
  that program.
- `run_process(name, args)` never uses a shell. `args` is a list and
  reaches the program as its argument vector, one element each.
- A name the grant does not cover is refused before the child starts, a
  refusal in E310's family (provisionally **E325**), named, like E311 for
  a module.
- The name and every argument are `Untrusted` sinks under 0004 (they are
  exactly the kind of thing a tool result must not choose), added to 0004's
  sink table beside `py`'s module name.
- An argument pattern, `proc:git:args=--version`, in sabline-spec §5.6's
  grammar, is a compatible extension and is not proposed now.

**The OS layer is what makes it more than a name check.** Today
`ffi:subprocess` widens the OS policy to "all" (`sabline/confine.py`,
`FFI_WIDENS`), so a run that grants it is not confined at all. `proc:NAME`
would widen nothing but `spawn`, and only for that path:

- **Linux, under full confinement**: the child inherits the run's
  Landlock ruleset and seccomp filter across `execve`, so it is held to the
  budget's paths and hosts like the program; and Landlock's execute right
  is granted for the resolved path alone, so the child cannot `execve`
  anything else.
- **macOS**: the sandbox profile's `process-exec` is allowed for that
  literal path only, and the profile is inherited.
- **Windows**: the job object refuses a second process today, and would
  have to allow one. Nothing in a job object or a lowered token restricts
  *which* binary a process runs, so the name is the language's check
  alone, and the Windows row of the confinement table says so.

**Does a shell inside a granted program defeat it? Plainly: at the
language level, yes, completely.** The budget sees one call to start one
program and nothing that program does afterwards. What bounds the rest is
the OS layer, and only where it holds:

- A granted program that **starts** a shell - `git -c alias.x='!sh -c id'
  x`, `core.sshCommand`, `core.pager`, a hook - is stopped on Linux and
  macOS under full confinement, because the shell is a second binary the
  execute rule does not allow. On Windows it is not stopped.
- A granted program that **is** an interpreter - `sh`, `bash`, `cmd`,
  `powershell`, `python`, `node`, `perl`, `env`, `xargs`, `find` (with
  `-exec`), `awk` - needs no second binary: granting it grants arbitrary
  execution inside whatever the OS policy allows. The budget parser would
  refuse those names outright (provisionally **E326**), and that list
  cannot be complete - `tar --to-command`, `ssh -o ProxyCommand`, an
  editor - so the grant is only as narrow as the program named, and the
  documentation must say that before it says anything else.

This is also Deno's position: its permission checks stop at the process
boundary, and the program `--allow-run` starts is not held by them. What
Sabline could add over Deno is the inherited OS policy on Linux and macOS.

**Cost.** About 8 days in the Python runtime (the effect, the grammar,
the builtin, the refusal, `os_policy`'s spawn rule per platform, the
audit's and the receipt's fields, `check_sandbox.py` and `check_confine.py`
cases, the documents), and about 5 in sabline-rt on top of M3's builtins
and M4's confinement. A new effect is a spec change: sabline-spec gains
it, and the conformance corpus its cases.

**What it would break.** Nothing that runs today: it is additive, and
`ffi:subprocess` stays as it is. It gives `ffi:subprocess` a replacement,
so a later release could warn on it; that is not proposed here. The
benchmark's 17a and 17b would be rewritten to use `proc` and their Sabline
cells would move.

**Milestone: M6**, as an addition not counted in its 22 days. A new
effect has to land in both runtimes in the same commits, and M6 is the
milestone where that already happens (0004's `trust`, 0005's `db`); it
also needs M4's confinement in Rust, which M6 follows. Not 8.7: building
it in Python alone now would make M3 port a feature nobody has used.

**Cases that must fail.**

1. `--allow io,proc:git`; `run_process("hostname", [])`: refused before
   the child starts (E325), and no process other than the runtime's own
   appears in the receipt.
2. `--allow io,proc:git`, Linux under full confinement;
   `run_process("git", ["-c", "alias.x=!sh -c 'echo reached'", "x"])`:
   `reached` never appears - the kernel refuses `/bin/sh`'s `execve` - and
   `git` exits non-zero.
3. `--allow io,proc:sh` (and `proc:bash`, `proc:python3`, `proc:env`):
   refused at budget parse (E326), before anything runs.
4. A file named `git` in the working directory, first on the run's
   `PATH`: the program started is the one the budget resolved, and the
   working-directory `git` never runs.
5. `run_process("git", ["--version; hostname"])`: `git` receives one
   argument and fails; `hostname` never runs, because there is no shell to
   split it.

**Decided, 2026-09-24: accepted for M6**, and counted in M6's effort
(8 days in Python, 5 in sabline-rt), not added beside it as the proposal
put it. The five cases above are M6 exit criteria. Two caveats are part of
the decision, and the grant's documentation states both before it says
anything else about it:

- **A granted interpreter defeats it at the language level.** `proc:NAME`
  bounds which program starts, never what that program does. A program
  that is an interpreter - a shell, `python`, `env`, `find` with `-exec`,
  and the others above - is arbitrary execution inside whatever the OS
  policy allows. E326 refuses the names that are obviously such programs,
  and that list cannot be complete.
- **Windows cannot restrict which binary runs.** Nothing in a job object or
  a lowered token holds which program a process starts, so on Windows the
  name is the language's check alone, and a granted program that starts a
  second one is not stopped there. The Windows row of the confinement
  table says so.

---

## b. A refusal ends the run

**What loses.** In seven rows both Sabline and Deno refuse the dangerous
operation, and only the Deno program finishes the task's legitimate work:
12a, 12b, 12c, 14c, 20b, 20c, 20d. A Sabline refusal "stops the program
and cannot be caught" (SPEC.md §7.1); the Deno program catches the
`NotCapable` error as an ordinary exception and goes on. The seven are not
one case:

- **12a, 12b, 20b, 20c**: the dangerous call is a `post` inside a `check`
  that ignores its failure. A catchable refusal would recover these four.
- **12c, 20d**: the dangerous call is `write_file`, which cannot fail in
  Sabline, so there is nothing for a program to catch; the refusal would
  still end the run. Making `write_file` fallible would put a `check` on
  every write in every program (E520), which is a breaking change far
  larger than this problem.
- **14c**: refused at compile time (E560: a `Secret` reaching the
  network). Nothing ran, correctly, and nothing here changes it.

**Can a refusal be catchable without letting a program retry its way
around a budget? Yes - bounded, and opt-in; not unbounded.** Retrying
cannot widen a budget: the same operation is refused the same way every
time, and a refusal changes no state. What an uncatchable refusal buys is
narrower and real: **a program gets one wrong guess per run.** A program
written to probe - try a hundred hosts, a hundred paths, every module
name - learns which one the budget allows and uses it, if a refusal is
survivable; if it is not, the first wrong guess ends the run, is in the
receipt, and the operator sees it. An unbounded catchable refusal turns
the budget into an oracle. That cannot be done safely, and is closed.

What can be: **`recover@N`**, a grant that lets at most N refusals of
fallible builtins become the builtin's failure, and ends the run on the
N+1th exactly as today.

- Without the grant, nothing changes: a refusal ends the run, as
  `SPEC.md` §7.1 says, and every existing test of it stands.
- Only a builtin that can already fail - `fetch`, `post`, `request`,
  `read_file`, `py`, `tool`, and the rest marked `or fail` - turns a
  refusal into its failure. `print`, `write_file`, `now` and the others
  that cannot fail keep ending the run.
- A caught refusal is still a refusal: it is in the receipt's `refusals`
  with `stopped: false` - the field 8.1 already has, for a refused
  redirect, the one catchable case today - on stderr, and in the run's
  exit status, which is a distinct non-zero status even when the program
  completes. That is the difference from Deno, where a swallowed denial
  exits 0 and a caller reading the status sees success.
- A caught refusal consumes no count and caches nothing.

**Cost.** About 4 days in the Python runtime (the grant, the conversion
at the refusal point, the exit status, the receipt, the tests) and about
3 in sabline-rt. The exit status is a new documented value, and exit
codes are stable surface (`STABILITY.md`), so it is an addition that must
be documented beside the others before it ships.

**What it would break.** Nothing without the grant. With it, a caller
that treats any non-zero status as failure sees one for a program that
finished its task; that is the intent, and it is why it is opt-in.

**Milestone: M6**, as an addition. It changes what a refusal is, in both
runtimes, and the agreement gate must first hold the two runtimes to
today's rule (M3) before the rule moves. Not 8.7.

**Cases that must fail.**

1. No `recover` grant; 20b's program (a refused `post` inside a `check`
   that ignores the failure): the run ends at the refusal (E310), the
   summary after it is not printed, and the status is today's.
2. `recover@1`; two refused `post`s in a row, both handled: the first
   becomes a failure, the second ends the run; the receipt lists two
   refusals, the first `stopped: false` and the second `stopped: true`.
3. `recover@3`; a loop over 100 candidate hosts, each `post` handled: the
   fourth refusal ends the run, and the listeners on hosts outside the
   grant receive nothing.
4. `recover@1`; a refused `write_file`: the run ends (a builtin that
   cannot fail is not recovered), whatever the grant says.
5. `recover@1`; 20b completes its task: the exit status is the distinct
   non-zero status, never 0.

**Decided, 2026-09-24: deferred, not rejected.** It is in no milestone,
and M6 does not carry it. Two reasons:

- **Seven days for four rows.** About 4 days in Python and 3 in sabline-rt
  recover 12a, 12b, 20b and 20c; 12c and 20d end the run anyway, because
  `write_file` cannot fail, and 14c is refused before anything runs.
- **Any recovery gives a program a way to probe the budget.** The bound
  above limits the probing; it does not remove it. Under `recover@N` a
  program gets N + 1 guesses instead of one, and each caught refusal tells
  it which guess was wrong, which is the thing the uncatchable refusal
  exists to deny. That the bound is enough is an argument, and it has not
  been tested against anyone trying to learn a budget through it.

So it gets **a decision of its own**, and **an adversarial pass** - in
`check_adversarial.py`'s shape, somebody trying to learn what a budget
grants through the caught refusals - before any of it is built. The
argument above is where that decision starts, not what it concludes.
Until then SPEC.md §7.1 stands: a refusal ends the run.

---

## c. The four correct programs Sabline stops (18a-d)

**What loses.** Four correct programs every other tool runs clean:

| Row | The program | What Sabline does |
|---|---|---|
| 18a | counts lines until the input ends | the audit reports a loop not shown to end (E612 under `--strict`); the run is correct |
| 18b | Euclid's algorithm | the same |
| 18c | 25!, which needs 84 bits | E407 at run time: the program stops |
| 18d | a product modulo 2^61 - 1, whose intermediate products pass 64 bits | the same |

18a and 18b are false positives of the audit, not of the run: `sabline
check` without `--strict` passes them and `sabline run` runs them. 18c and
18d are false positives of the run.

**What the static rules would need.**

- **18a - a third loop verdict, "bounded by its input".** SPEC.md §9.5
  gives two verdicts, `terminates` and `unshown`. A loop whose every path
  from the top of the body back to the condition calls `read_line()`, and
  whose condition changes only from that call's result, ends when its
  input ends, and is reported so - not as `terminates`, since an input
  that never ends keeps it going, and not as `unshown`. E612 under
  `--strict` does not fire for it. Syntactic, no solver, the same with
  and without the prover, as §9.5 requires. About 2 days, and a spec
  change.
- **18b - a `decreases` clause.** Euclid ends because `y` falls every
  step (`0 <= x % y < y` for `x >= 0` and `y > 0`), which no counter rule
  can see. `while y != 0 decreases y { ... }`, in a `gcd` that `requires
  a >= 0` and `requires b >= 0`, states the measure; the prover shows it
  falls and stays non-negative, and where it cannot (or there is
  no prover - sabline-rt does not prove), the runtime checks it at every
  iteration and stops the run with a coded failure the first time it does
  not fall. Either way the loop cannot run forever, so the verdict is
  `terminates`. About 5 days in Python and 3 in sabline-rt. **It closes
  18b only for a program that writes the clause**: 18b as the corpus has
  it would still be reported. Inferring the measure from `y = x % y` is a
  special case of a special case, and is not proposed.
- **18c, 18d - a whole number past 64 bits.** Two ways, neither
  proposed. Making `Int` unbounded removes E407, and with it the six
  overflow catches of category 5 and 18f, the one row where a 64-bit
  limit is the danger; it also puts a big-integer type under every
  arithmetic builtin of sabline-rt and against M8's performance floor. A
  separate type (`Big`) beside a 64-bit `Int` keeps E407 and costs about
  10 days across both runtimes - literals, arithmetic, `to_text`, JSON,
  formatting, the prover's encoding - for a need nothing but this row has
  shown.

**Is the false-positive cost worth paying?** For 18a and 18b, no - they
are cheap to close and the audit's report is simply wrong about them. For
18c and 18d, **yes**: a correct program past 64 bits stops, loudly and
with a code, and in exchange every whole number in every program either
fits the 64-bit fields it is written to or stops the run. The benchmark
shows the trade from both sides - six overflow catches no competitor
makes, and two correct programs only Sabline stops - and this proposal
keeps it.

**What it would break.** The input-bounded verdict: `sabline explain`'s
and `sabline audit`'s loop counts change for programs that have such
loops (fewer `unshown`), which moves the proven share and any committed
audit; it breaks no program. `decreases`: nothing (additive syntax).

**Milestone.** The input-bounded verdict in **M2**, where the checkers are
ported: written into sabline-spec §9.5 first and implemented once in each.
`decreases` in **M6**, with the other language additions. `Int` past 64
bits: **never** for `Int`; a `Big` type is not scheduled.

**Cases that must fail.**

1. 18e (reads once before the loop, never inside it): stays `unshown`
   under the input-bounded rule.
2. A loop that calls `read_line()` on one arm of an `if` only: `unshown`.
3. `while y != 0 decreases y { y = y + 1 }`: refused by the prover when
   present, and stopped at the first iteration by the runtime check when
   not - it must not loop.
4. `decreases y` where `y` can fall below zero (`y = y - 2` from an odd
   start): refused, since the measure must stay non-negative.
5. 05a to 05f and 18f still stop with E407.

**Decided, 2026-09-24: accepted in part.**

- **The input-bounded verdict: accepted for M2, for 18a**, and counted in
  M2's effort (about 2 days): sabline-spec §9.5 gains the third verdict
  first, and each checker implements it once. 18a is then reported as
  bounded by its input and passes `check --strict`; cases 1, 2 and 5 above
  are M2 exit criteria.
- **18b stays open**, reported as a loop not shown to end. The decision as
  first given named 18b beside 18a; it was corrected the same day, because
  Euclid's loop ends by a falling measure and reads nothing, so the
  input-bounded verdict does not reach it. **The M2 rule is not widened to
  recognise Euclid's shape** (`y = x % y` under `y != 0`): a rule that
  closes one program and nothing else makes the checker harder to describe
  than it is worth.
- **`decreases`: an open proposal with no milestone**, beside `recover@N`
  (section b). Both are language changes, and each gets a decision of its
  own and an adversarial pass before anyone builds it. Cases 3 and 4 wait
  with it.
- **18c and 18d stay declared false positives, and `Int` stays 64-bit.**
  A `Big` type is not scheduled.

---

## d. The laundering case (16a-c), where CaMeL wins

**What loses.** The task reads a private ledger and posts a summary to the
one host it is granted; 16a posts the ledger itself, 16b appends it to
the summary, 16c posts it upper-cased. Every grant Sabline has allows the
read and the post, and nothing follows the data from one to the other.
CaMeL refuses all three, and refuses 16d too - a correct program that posts
only the number of entries - because the count was computed from private
data.

**Do M6's sink-specific budgets close it? No, not as designed, and it is
worth saying why in three parts.**

1. **The mark is the wrong one.** Under 0004, `read_file` gives an
   `Untrusted of Text`. `Untrusted` bounds what a value may *name* - a
   path, a URL, a module, a tool - and 0004 says in as many words that
   `post`'s *body* is not an `Untrusted` sink: "bounding where it may go is
   `Secret`'s job". The ledger goes in the body. So `Untrusted`, with or
   without a reach, allows all three leaks.
2. **`Secret` is the right mark, and the program chooses whether it
   applies.** A ledger read with `read_file_secret` is a `Secret of Text`,
   and posting it, or anything computed from it, is E560 - 16a, 16b and
   16c alike, at compile time. But the program picks `read_file` or
   `read_file_secret`, and the program is the adversary. Nothing lets the
   operator say "this file is secret, however it is read".
3. **A reach names sinks, and here the sink is the same.** The leak goes
   to the same host the task legitimately posts its summary to. A reach
   of `net:that-host` would let the ledger through as readily as the
   summary. What separates 16a from 16d is not where the value goes but
   what it was computed from - value dependency, which CaMeL tracks per
   value and ChainCaps per value and per sink, and which Sabline tracks
   only for values that carry a mark.

**What would close it: a secret-path grant.** `fs:secret:PATH`, which
makes a path the operator names behave as the documented credential
locations already do under E318 (8.0):

- `read_file` of a path under an `fs:secret:` grant is refused (E318,
  naming the path), so the program cannot choose the unmarked builtin;
- `read_file_secret` of it gives `Secret of Text`, with an empty reach;
- from there the existing rules do the work: posting it, or anything
  computed from it, is E560 at compile time; branching on it is E563; the
  only way out is `declassify`, which needs the effect, the operator's
  grant, and a reason written in the call, and is named in the audit.

What that gives on the four rows: 16a, 16b and 16c are refused before
they run. **16d is refused too**, as CaMeL refuses it, and more strictly:
counting the entries means testing each line (`contains(line, "acct-")`
in an `if`), which is branching on a `Secret` (E563), so a correct 16d
must declassify the ledger's lines, or the count, with a written reason -
a reason a reviewer reads, and a program that leaks can also write. 16e,
which posts a fixed status, compiles unchanged. So the proposal buys
16a-c at the cost of 16d, as CaMeL's policy does, with an audited escape
where CaMeL has a policy decision; it does not give per-value provenance,
and the general case - any value computed from any granted read, reaching
any granted sink - stays ChainCaps' and CaMeL's.

**Cost.** About 3 days in the Python runtime (the grant, the refusal
through E318's path, the budget parser's rule that an `fs:secret:` grant
lies under an `fs:read:` grant, the documents) and about 2 in sabline-rt.

**What it would break.** Nothing without the grant. With it, every
program that reads a marked file with `read_file` is refused at run time,
which is the point, and every program that computes anything from it has
to be written against `Secret`'s rules.

**Milestone: M6**, beside 0004's reach - it is the `Secret` machinery and
the budget grammar, in both runtimes. The general per-value case:
**never**, as a stated difference from ChainCaps and CaMeL, not as a
defect.

**Cases that must fail.**

1. `--allow io,fs:read:./granted,fs:secret:./granted/ledger.txt,net:127.0.0.1:PORT`;
   `read_file("./granted/ledger.txt")`: E318 at run time, naming the
   path, and nothing is posted.
2. The same budget; `read_file_secret` of it, then `post(url, ledger)`:
   E560 at compile time.
3. The same; `read_file_secret`, `upper(ledger)`, concatenated into a
   summary, then posted (16b and 16c's shapes): E560 - a pure operation
   keeps the mark.
4. `--allow io,fs:secret:./granted/ledger.txt` with no `fs:read:` grant
   covering it: refused at budget parse, like 0004's E575.
5. `declassify` of the ledger with no `declassify` grant: E310 at the
   call, as today.

**Decided, 2026-09-24: accepted for M6**, and counted in M6's effort (3
days in Python, 2 in sabline-rt). The five cases above are M6 exit
criteria. It is accepted with its price recorded: **it refuses the correct
16d as well.** A program that posts only the number of entries has to test
each line of a `Secret`, which is E563, so it compiles only with a
`declassify` and a written reason. That is the same false positive CaMeL
takes on 16d, and under the grant 16d is a correct program Sabline stops -
a price of the grant, stated as one, not a defect to be closed later. The
general per-value case stays **never**.

---

## e. 19d: native code inside a granted library writes a file

**What loses.** 19d grants a vendored library (`ffi:nativefmt`) that
calls `fopen` through `ctypes` and writes a file of its own. Nobody stops
it: Sabline grants the module whole, Deno grants its foreign-function
interface whole (`--allow-ffi`), and neither WASI nor Starlark can load
native code at all. In 19a and 19b, the same shape in Python and
JavaScript, WASI and Deno stop it and Sabline does not.

**Can the OS layer see it at all? Yes.** The kernel checks the system
call, not the code that made it: an `open` issued by the interpreter, by a
Python module, or by C code `ctypes` loaded is the same call from the same
process, and Landlock and seccomp apply to it alike. That is exactly the
argument for a boundary around the whole process that WASI's column
makes. **Today it does not, by decision**: `os_policy` widens the policy
for a granted module to what `FFI_WIDENS` says the module can do, and a
module it does not name - `nativefmt`, like any vendored library - widens
it to "all", nothing enforced (THREAT_MODEL's known-open table, *Runs that
are not confined*). 8.4 chose that so that a run that worked under 8.3.1
was not refused. 19d ran unconfined.

**What confinement would have to do: take the policy from the budget
alone.** A `--confine strict` mode in which an `ffi` grant widens
nothing: the OS policy is exactly the budget's `fs:` and `net:` grants
(and the runtime's own reads), whatever modules are granted, so a module
that needs a path or a host needs it in the budget. In M4 terms:

- `os_policy` gains the one rule - under `strict`, `widened_by` is empty
  and no module changes `fs_read`, `fs_write`, `net` or `spawn` - in both
  runtimes, and `ENFORCES` gains the rows.
- **Linux**: a native write outside the grants fails in the kernel
  (EACCES from Landlock); a native connection to an ungranted host is
  refused where the kernel holds the network (a port with Landlock ABI 4,
  and `socket` itself under seccomp when there is no `net` grant).
- **macOS**: writes and the network are refused by the profile; reads
  only as far as the profile holds them today (partial).
- **Windows**: with no write grant, the low integrity level refuses a
  write to anything of the user's - which is 19d's budget; with a write
  grant, writes are not held, and the network needs the AppContainer that
  M4's spike decides.
- In M5 terms: nothing. The tool door and guard mode see calls, never
  the code behind them; native code in a tool host is another process, and
  THREAT_MODEL's *What a host does with a call it was given* already
  says so.
- `plan/9.0.md` does not yet say how sabline-rt will make a `py` call.
  Whichever way it does, the rule is the same: the process that runs the
  module's code is under the budget-derived policy, never a wider one.

What it cannot do: see what a module does *inside* the grants. A native
library that writes under a granted directory, or posts to a granted
host, is doing what the budget allows.

**Cost.** About 3 days in the Python runtime (the mode, the policy rule,
the receipt, `check_confine.py`'s cases with the fault-injection hook,
the documents) and about 2 in M4's port.

**What it would break.** Nothing by default: `strict` is opt-in, because
a module that does I/O the budget does not grant - `sqlite3`'s journal
beside its database, a library reading its own data files, `ffi:os`,
`ffi:subprocess` - fails under it with an OS error, as it should. Making
`strict` the default is a breaking change and belongs with 0005's set, if
at all; it is not proposed here.

**Milestone: M4** for sabline-rt, where confinement is ported. The Python
side is small enough for 8.7, and would flip 19d's Sabline cell on Linux;
but a flag added now is a flag M4 must port, so this proposes both land
with M4 and the Python runtime's version first, in the same release.

**Cases that must fail.**

1. Linux, `--confine strict`, `--allow io,ffi:nativefmt` (19d): the
   native `fopen` outside any grant fails, the file does not exist after
   the run, and the receipt says `full` with `widened_by` empty.
2. The same budget with a module that writes through `ctypes` directly
   (`libc.write` on a file it opened outside the grants): refused by the
   kernel.
3. `--confine strict`, `--allow io,ffi:os`; `os.system("touch /tmp/x")`:
   the `execve` is refused (seccomp) and `/tmp/x` does not exist.
4. `SABLINE_FAULT_INJECT=write:/tmp/outside` under `strict` with an `ffi`
   grant: E319, the honesty test, exactly as without the grant.
5. Without `strict`: 19d runs as today and the receipt says `none`, naming
   the module - the default must not move.

**Decided, 2026-09-24: accepted for M4**, and counted in M4's effort (3
days in Python, 2 in the port): the Python runtime's version first and
sabline-rt's with it, in the same release, as proposed - not 8.7. The five
cases above are M4 exit criteria, the fifth among them: `strict` is
opt-in, and without it a module the table does not name still widens the
OS policy to nothing enforced, and the receipt still says so.

---

## Summary

| | Proposal | Cost | Breaks | Milestone |
|---|---|---|---|---|
| a | `proc:NAME` and `run_process`, no shell, the OS policy inherited and exec held to one path | ~8 + ~5 days | nothing | M6 |
| b | `recover@N`: at most N refusals of fallible builtins caught, with a distinct exit status; unbounded catching closed | ~4 + ~3 days | nothing without the grant | M6 |
| c | an input-bounded loop verdict; `decreases`; `Int` stays 64-bit | ~2 (M2) + ~8 (M6) days | audit loop counts | M2, M6, never |
| d | `fs:secret:PATH`; M6's reach alone does not close it | ~3 + ~2 days | nothing without the grant | M6; the per-value case never |
| e | `--confine strict`: an `ffi` grant widens nothing | ~3 + ~2 days | nothing by default | M4 |

None of the five is scheduled by this document. The known-open table
names each, and each row changes when, and only when, the proposal behind
it is accepted and built.

*Decided 2026-09-24* (above): the known-open rows now name the milestone
that closes each accepted item, or say that nothing is scheduled, and each
changes again when its item ships.
