# 0007 - Items 29 to 36 of the field survey, and two small additions

**PROPOSED 2026-10-04. Nothing here is decided, and nothing here is
built.** Each item below is what it is, where it would sit, what it would
cost, what it would risk, and a recommendation. The maintainer accepts or
changes each one after reading; until an item is accepted *and* shipped it
changes nothing in `SPEC.md`, sabline-spec or either runtime, and no
document may describe it as a feature. That is the same rule
`decisions/0006-where-sabline-loses.md` runs under.

This record started from the maintainer's own recommendations, which are
quoted in each item under **The recommendation this started from**. Six
items are recommended differently here, and each of those says why with
the evidence it rests on. Three of those six rest on measurements made in
the same pull request as this record - AgentDojo's four suites, run
offline under three budgets (item 35) - and the numbers are quoted where
they are used.

## Two rules this record applies to every item

**A day in Python is not a day shipped.** Anything accepted into 9.0 that
adds surface is written twice: once in the Python runtime and once in
sabline-rt, unless it lands inside the milestone that ports that area.
Every estimate below is split the way 0006's were (`5 days - 3 in Python,
2 in the port`), and an item whose natural home is a milestone that has
not yet been ported is cheaper there than anywhere else.

**Nothing here may let a program do more than its budget grants.** Of the
twelve items, eleven narrow what a grant means, report more precisely, or
add a check; item 36's wildcard is the only one that widens what a pattern
can match, and it is the one with the longest risk section.

## What is proposed

| | Item | Recommendation here | Where | Days |
|---|---|---|---|---|
| 29 | order rules | **partly, and later than proposed**: one built-in rule, in M6 *after* `Untrusted of T`; the general rule language after rc | M6 | +4 |
| 30 | `endorse` | **yes, and load-bearing rather than alongside**: 34's step 3 is unusable without it, so the same release | M6 | +6 |
| 31 | a Z3 ratchet | **defer until after rc** | - | 0 |
| 32a | fail hard on weak confinement | **yes** | M4 | +3 |
| 32b | an audit stream, JSON lines | **yes**, and smaller than it looks | M3 | +4 |
| 32c | an organisation ceiling file | **yes**, and it must be in the receipt | M3 | +6 |
| 32d | the MCP specification's own rules | **yes** | M5 | +5 |
| 32e | child-process confinement tests | **already done, except for the one case that cannot be written yet**: fold into M4 and M6 exit criteria | M4, M6 | 0 |
| 33a | pause and resume | **into the open `recover@N` decision** | - | 0 |
| 33b | Cedar | **defer unless a user asks** | - | 0 |
| 33c | how Python-like the syntax is | **decide after the nine-model round trip** | - | 0 |
| 34 | fixing the AgentDojo laundering attacks | **steps 1-2 recorded done; step 3 yes, first in M6, and it needs 30; step 4 yes, now** | M6 | +8 |
| 35 | the other three AgentDojo suites | **closed by this pull request** | - | 0 |
| 36 | the pattern grammar | **partly**: no to negation; yes to a wider wildcard, but as `**` and third in line behind a bound on a number | M5 | +7 |
| + | an analysis-mode field in `capability/v1` | **yes**, and not 9.0 work | now | +1 |
| + | `sabline new` writes an `AGENTS.md` | **yes**, and the command is `new`, not `init` | now | +2 |

**If every yes is taken, 9.0 goes from 196 days to 239**, and 4 more days
sit outside it. The breakdown is at the end.

---

## 29 - order rules

**What it is.** A budget today says *which* effects and tools a run may
use, and how many (`tool:NAME@N`, `...@N`, SPEC.md 7.2). It says nothing
about the *order* they happen in. An order rule would: no `net` after a
`Secret` has been read; no send after an untrusted read; at most N of
something in a window.

**The recommendation this started from.** "PARTLY. A small built-in set in
9.0 (e.g. no network after reading secrets or untrusted data; at most N); a
general rule language after rc."

**Where this record differs, and why.** Two corrections, one of them
measured.

*"At most N" already ships.* `tool:NAME@N`, `tool@N` and `...@N` are in
SPEC.md 7.2 (lines 452-453) and in the manifest's own ceiling. There is
nothing to build; what is missing is a window - "at most N per minute" -
and nothing in the field survey asked for one. 0 days.

*An order rule over reads in general has no useful setting on this
corpus.* AgentDojo's four suites give 97 user tasks with reference
solutions. **44 of them read and then send. Every single reference
solution that sends anything at all reads first: 44 of 44.** A built-in
rule of the form "no send after a read" is therefore exactly equivalent,
on this corpus, to granting no sink at all - it does not cost some
utility, it costs all of it. The rule only becomes usable when it is about
*marked* data rather than about reads: "no send after an **untrusted**
read", which needs `Untrusted of T`, and "no network after a **secret**
read", which needs `Secret`'s reach and `fs:secret:PATH` (0006 (d),
accepted into M6). Both are M6.

So the small built-in set is the right idea in the wrong place. Put it in
M6, **after** `Untrusted of T` has landed, where it reduces to one rule
over marks that already exist rather than a new analysis.

**Cost.** +4 days in M6 - 2 in Python, 2 in the port - for one built-in
rule (`order:no-sink-after-untrusted`, off by default, named in the
receipt) and its refusal code. The general rule language is not estimated
and is not 9.0; a language for ordering constraints is a prover-shaped
problem and the 9.0 ladder has one of those already.

**Risks.** A rule that can refuse mid-run gives a program a way to observe
the budget by probing, which is the objection that deferred `recover@N`
(0006 (b)) and applies here too: the refusal must be hard, not catchable.
A built-in set also invites "just one more", and the right answer to the
second request is the rule language, after rc.

**Recommendation: partly, and later than proposed.** One built-in rule, in
M6 after `Untrusted of T`. Nothing in 9.0 before M6. "At most N" is struck
as already shipped.

---

## 30 - `endorse`

**What it is.** A builtin that takes an `Untrusted of T` and a check, and
returns a plain `T` when the check passes: the one way a mark comes off,
as `declassify` is for `Secret`. The example from the survey is checking
an untrusted name against the workspace member list, so that an attacker
who controls the name can at most pick a real member.

**The recommendation this started from.** "YES, M6, alongside `Untrusted
of T`."

**Where this record differs, and why.** Only in how load-bearing it is -
"alongside" undersells it. Item 34's step 3 says destination arguments
(recipient, URL, channel, file path) must not be untrusted. Measured
against AgentDojo's reference solutions: of **222 destination arguments**
the four suites' reference solutions pass, **133 cannot be pinned, and all
133 are values the legitimate program takes out of what a tool returned** -
an event id a search returned, the smallest channel counted at run time,
the hotel that comparing prices picked, the colleague's address that was on
her website. Under step 3's rule, with no way to clear a mark, **every one
of those 133 legitimate arguments is refused.** `endorse` is not a
companion to step 3; it is the thing that makes step 3 shippable, and the
two must be in the same release, not merely the same milestone.

That also gives `endorse` a test corpus it would otherwise have to invent:
133 real cases, each with the tool that produced the value and the check
that would clear it.

**Cost.** +6 days in M6 - 4 in Python, 2 in the port. It is `declassify`'s
shape: one type rule, one checker rule, the runtime, the audit naming it
the way `declassify` is named, the receipt, the docs.

**Risks.** `endorse` is a hole by design, and the whole value of
`Untrusted` rests on it being narrow. The failing cases matter more than
the passing ones: an `endorse` whose check is a comparison against another
untrusted value must not compile; an `endorse` with a check the prover
cannot read must not quietly pass; and the audit must name every one, so
that "where does the mark come off" is answerable without reading the
program.

**Recommendation: yes, in M6, in the same release as 34's step 3.**

---

## 31 - a Z3 ratchet

**What it is.** A recorded count of what the prover proves, held like
`check_ratchet.py` holds the capability surface: a change that proves less
than the record fails CI.

**The recommendation this started from.** "DEFER until after rc."

**Where this record differs.** It does not.

**Why defer is right.** M2 ports the checkers, and the prover is the part
of the Python runtime whose output is least stable under a port: the Rust
side will reach Z3 differently, time out differently, and give up on
different goals. A ratchet over proof counts during M2 would fail on every
honest difference and teach the maintainer to raise it, which is the
failure mode `docs/` already warns about for page budgets - a ratchet that
gets raised is not a ratchet. After rc there are two runtimes that agree,
and a ratchet then means something.

**Cost if taken after rc.** 3-4 days. Not counted in 9.0.

**Recommendation: defer until after rc.**

---

## 32a - fail hard on weak confinement

**What it is.** From 8.4 the operating system is asked to hold the budget,
and `ENFORCES`/`THREAT_MODEL.md` say per platform which rows it actually
holds. Today a run whose confinement is `partial` or `none` prints a
warning on stderr and runs: "plain ffi grants any module, so the operating
system layer is off for this run: the budget is the only boundary". 32a
adds a mode that refuses instead.

**The recommendation this started from.** "YES, M4."

**Where this record differs.** It does not, and the machinery is further
along than the item implies. `sabline/confine.py`'s `predict()` already
returns the level and the reason, `sabline audit --confinement-probe`
already prints both, and the receipt already records them. 32a is a flag
that turns an existing prediction into an exit code.

It is **not** `--confine strict` (0006 (e), accepted into M4, +5 days).
`strict` is about an `ffi` grant not widening the policy; 32a is about
refusing to run when the platform cannot hold the budget at all. They
compose: under `strict` the level is full more often, so 32a refuses less.

**Cost.** +3 days in M4 - 2 in Python, 1 in the port: the flag, the exit
code and message, an `ENFORCES` row, and the three-platform tests in
`check_confine.py` beside the ones already there.

**Risks.** The blast radius depends on M4's AppContainer spike. If the
spike succeeds, Windows holds reads and the network and 32a is a mode a
Windows operator can actually use. **If the spike fails, 32a on Windows
refuses every budget with an `fs:read:` grant**, which makes it a
Linux-and-macOS feature with a Windows footnote. That is survivable and
honest, but it must be said in the release note rather than discovered.
The second risk is the usual one for a strict mode: it must be opt-in, and
the default must not move.

**Recommendation: yes, M4, and the release note names what it does on
Windows under either spike outcome.**

---

## 32b - an audit stream

**What it is.** The run's effects as they happen, one JSON object per
line, so that a host can watch a run rather than read a receipt
afterwards.

**The recommendation this started from.** "YES, JSON lines; OpenTelemetry
later."

**Where this record differs.** Only to say it is smaller than it sounds.
Two thirds of it exist: `sabline trace` already shows every call as it
happens, and the tool door already speaks JSON lines - `{"event": "call",
...}`, `{"event": "output", ...}` - which is the protocol
`agentdojo_eval.py` reads in this very pull request. What is missing is one
event shape over *every* effect, not just tool calls, and a flag to send
it somewhere.

**Cost.** +4 days in M3 - 2 in Python, 2 in the port. M3 is where the
interpreter and the receipt are ported, and the event stream is the
receipt's fields emitted as they are produced; building it anywhere else
means building it twice over.

**Risks.** M3 is already the largest milestone at 35 days, and this makes
it 45 with 32c. An event stream is also a new way for a run to be
observed, which means a new way to get it wrong: an event must never carry
a `Secret` value, and `check_library.py`'s secrets cases must cover the
stream the way they cover the receipt. OpenTelemetry later is right - it
is a dependency and a wire format, and neither belongs in a milestone that
is porting an interpreter.

**Recommendation: yes, M3, as JSON lines. OpenTelemetry after rc.**

---

## 32c - an organisation ceiling file

**What it is.** A file an organisation installs that caps what any budget
on the machine may grant, so that a developer's `--allow all` is bounded
by something they did not write. The per-door versions exist - the MCP and
HTTP doors take `--max-allow`, a tool manifest carries its own ceiling,
and `sabline capabilities check` fails when a surface widens - and this
generalises them to every entry point.

**The recommendation this started from.** "YES."

**Where this record differs.** It adds one condition. A machine-wide file
that silently narrows a budget is a debugging trap: a program refused for
a reason that is in neither the command line nor the source is the worst
refusal Sabline can produce. So the ceiling must be named in the refusal,
in the receipt, and in `sabline audit`, and it must be possible to see it
without finding the file.

**Cost.** +6 days in M3 - 4 in Python, 2 in the port: the file format, the
precedence rules against `--max-allow` and the manifest ceiling, the
application at every entry point (command line, library, MCP, HTTP, pool,
`eval`, `test`), the refusal code, the receipt field, and tests at each
door.

**Risks.** Precedence is where this goes wrong: three ceilings and a
budget, and the answer must be the intersection, with no order of
application that produces anything else. The file is also a new piece of
ambient state, which is exactly what budgets exist to avoid - it is only
defensible because it can only ever narrow.

**Recommendation: yes, M3, and it is in the receipt or it is not shipped.**

---

## 32d - the MCP specification's own rules

**What it is.** The MCP specification states requirements of a server -
consent before a tool runs, tool annotations, audience and resource
indicators on tokens, not acting as a confused deputy. Sabline ships an
MCP server and, from M5, guard mode: unmodified MCP tools under a Sabline
budget. 32d is asserting those requirements rather than assuming them.

**The recommendation this started from.** "YES, M5."

**Where this record differs.** It does not. M5 is the right place: guard
mode is already there (+6 days), and the two share the manifest and the
door.

**Cost.** +5 days in M5 - 3 in Python, 2 in the port: a check per rule,
the ones Sabline already satisfies asserted so they stay satisfied, and
the ones it does not named in `docs/known-open.md` with a row each.

**Risks.** The specification moves, and a conformance claim pinned to a
version is the only kind worth making - the same rule
`requirements/agentdojo.txt` applies to a benchmark. A rule Sabline cannot
satisfy must get a known-open row rather than a quiet omission; this is
the item most likely to produce an uncomfortable row, which is the reason
to do it.

**Recommendation: yes, M5, pinned to a named specification version.**

---

## 32e - child-process confinement tests

**What it is.** Tests that a child process is held by the same confinement
as its parent.

**The recommendation this started from.** "YES, first, before 9.0 work. If
a test fails, report it as a bug against an existing claim."

**Where this record differs, and why.** This was read against the tests
that exist, and they already cover it. There is no bug to report, and
nothing to do first.

What a child process can be, today, and what already asserts it:

- **A process the program starts.** Under confinement it cannot. Linux:
  seccomp refuses `execve` and `execveat` with EPERM and kills on `fork`,
  `vfork` and `clone` without `CLONE_THREAD`; macOS: `(deny process-fork)`
  and `(deny process-exec)`; Windows: a job object with one active
  process. `check_confine.py` asserts the policy says `spawn: false` on
  every platform and runs the seccomp decision table over those calls.
- **A child the runtime itself starts** - a run with a timeout or a memory
  cap, a pooled worker, the check-and-audit ceiling. That child *is*
  confined, and it is asserted with the fault-injection hook, not
  inferred: `run(timeout=60)` and `Pool(size=1, timeout=60)` each attempt
  a write outside the budget and get E319, and `confine=False` lets the
  same write through. `check_confine.py` lines 405-423.
- **A child under `ffi:os` or `ffi:subprocess`.** Here a child *can* be
  started, and it is unconfined - because with those grants nothing is
  confined at all. That is documented ("widens the OS policy to nothing
  enforced"), asserted (`check_confine.py` checks `enforced is False and
  spawn is True` for both modules), and it is precisely what 0006's
  `--confine strict` closes: under `strict`, `--allow io,ffi:os` with
  `os.system("touch /tmp/x")` must be refused by seccomp, which is already
  one of M4's exit criteria.

The case that is genuinely untested is the one that **cannot be written
yet**: when `proc:NAME` ships (0006 (a), accepted into M6, +13 days) a
program may start a named process for the first time, and then "is the
child held by the parent's Landlock ruleset, seccomp filter, sandbox
profile and job object?" becomes a real question with a real answer. Those
tests belong to `proc:NAME`, in M6, as its exit criteria.

**Cost.** 0 days as an item. The work is two lines added to existing exit
criteria: M4's `--confine strict` already carries the `ffi:os` case, and
M6's `proc:NAME` gains the inheritance cases.

**Risks.** The risk of accepting 32e as written is the one worth naming:
it would schedule days before 9.0 to write tests that exist, and the pass
would report green for a reason that is not the reason anyone wanted. A
test suite that cannot fail is worse than no test, because it is counted.

**Recommendation: struck as a separate item.** Fold the `ffi` case into
M4's `--confine strict` exit criteria, where it already is, and the
inheritance cases into M6's `proc:NAME`. No bug is reported, because none
was found.

---

## 33a - pause and resume

**What it is.** Stopping a run and continuing it later, which is what an
agent loop wants when a tool call needs a human.

**The recommendation this started from.** "Into the open `recover@N`
decision."

**Where this record differs.** It does not, and the reason is the same
one: both give a program a way to carry on past a point where the runtime
had decided something, and both need the same question answered first -
what can a program observe about why it stopped? 0006 deferred `recover@N`
for exactly that and asked for an adversarial pass before a decision.
Pause and resume is a larger version of it, with state serialisation on
top, so it cannot be decided before the smaller one is.

**Cost.** Not estimated. It is not 9.0.

**Recommendation: fold into the open `recover@N` decision**, as the
heavier of the two cases it has to answer for.

---

## 33b - Cedar

**What it is.** Expressing a Sabline budget as a Cedar policy, the way
8.1 exports to OPA and Kyverno.

**The recommendation this started from.** "DEFER unless a user asks."

**Where this record differs.** It does not, and adds one number: two
policy exports already exist, and each one is a format that has to keep
working, be tested and be versioned. A third with no user behind it is
maintenance taken on speculatively, which `MAINTENANCE.md` is the argument
against.

**Cost if asked for.** 3-4 days, on the OPA exporter's shape.

**Recommendation: defer unless a user asks**, and the ask should name the
system they need it for.

---

## 33c - how Python-like the syntax is

**What it is.** Whether Sabline should move closer to Python's syntax, on
the theory that a model writes what it has seen most of.

**The recommendation this started from.** "Decided only after the
nine-model round-trip run."

**Where this record differs.** It does not. The round trip exists
(`evals/roundtrip`, `roundtrip_eval.py`), it already compares Sabline
against Python model by model, and the nine-model run has not happened. A
syntax decision taken before it would be taken on a hunch about the thing
the harness was built to measure.

One caution for when the number arrives: the round trip measures whether a
model writes *working* Sabline, and a syntax change that improves that
number can still be wrong - Python-like syntax with different semantics is
the trap, and `docs/compare-python-sandbox.md` is about the version of it
that already bites.

**Recommendation: decide after the nine-model run, and not before.**

---

## 34 - fixing the AgentDojo laundering attacks

**What it is.** Four steps, agreed 2026-09-26:

1. find which door each landing attack came through - written into the
   program as a literal, or read at run time from tool output;
2. re-run with a third budget, argument-pinned from the user task's text
   only, reporting all three budgets and listing the arguments that cannot
   be known in advance;
3. build `Untrusted of T` in M6 with the destination-versus-content rule:
   everything read from a tool, a web page or a message is marked
   untrusted and the mark follows text operations; destination arguments
   (recipient, URL, channel, file path) must not be untrusted; content
   arguments (a message body) may carry untrusted text but must not carry
   `Secret` data to an outside destination. `endorse` goes alongside.
   `Untrusted of T` goes **first** within M6, since the remaining attacks
   need it;
4. document "write the program before reading data" as the recommended way
   to use Sabline with agents, since the guarantees depend on it.

**The recommendation this started from.** "Steps 1-2 recorded as done; step
3 YES in M6, first; step 4 YES, small, can be done now as documentation."

**Steps 1 and 2: done, in #122, and now measured on four suites rather
than one.** Item 35's work in this pull request re-ran both over the
workspace, banking and travel suites. What that adds to steps 1-2 is
reported on `docs/agentdojo.html` and in the paper's section 4.3; the two
findings that bear on step 3 are these.

*The door question has a real answer now, and it is the one step 3
assumes.* Under ground-truth transcription the door a value arrives
through is fixed by construction - the harness writes the resolved value
out as a literal - so the recorded split could only ever say "the
program". This pull request closes that by generating a **second program**
for every injection whose ground truth marks an argument as read at run
time: the same calls, with that argument built at run time out of the text
the read returned. The attacker's value then comes through the data door
for real, and the budget's verdict is compared pair by pair with the
literal program's - 238 pairs, three budgets each, 714 runs. **The budget
decides the same way, with the same refusal code, in all 714.** In three
of those pairs the laundered value reaches the door under a task budget
and the attack lands, scored by AgentDojo's own security check: door 2 is
no longer a shape the corpus only describes. That the budget cannot tell
the doors apart is not a surprise - a pattern is matched against the value
at the door, whichever door it came through - but it is now measured
rather than argued, and it is the evidence that pinning cannot be made to
do step 3's job.

*The workspace suite has laundering attacks that land, which the Slack
suite did not.* On Slack no injection with the read-then-send shape ever
reached the door, because no user task granted every tool one needed - a
limit of that corpus, and the paper said so. Workspace grants both
`search_emails` and `send_email` to several tasks, so its laundering
injections do reach the door and do land. Step 3's rule is aimed at
attacks this corpus now contains.

**Step 3: yes, first in M6, and it needs item 30 in the same release.** The
sequencing is right and the AgentDojo numbers support it. The one
correction is the dependency, measured above under item 30: **133 of 222
destination arguments** in the reference solutions are values the
legitimate program takes from a tool result, so the rule "destination
arguments must not be untrusted" refuses all 133 unless `endorse` can
clear the mark. Step 3 without `endorse` is not a partial feature; it is a
feature that refuses most legitimate programs.

Two further notes on the rule's shape, from the same data:

- The destination-versus-content distinction does **not** restate the
  pinned-versus-free split, and that is the argument for it. 89 of 222
  destination arguments can be pinned and 133 cannot; of 72 content
  arguments, 21 can be pinned and 51 cannot. Pinning needs to know the
  value in advance; the rule only needs to know the value is not
  untrusted. It reaches the 133 that pinning leaves wholly free.
- The content half of the rule - untrusted text allowed, `Secret` data to
  an outside destination refused - is the only thing in this record that
  would refuse the attacks that still land on Slack and workspace with
  arguments pinned, because those are all a granted tool reached with an
  argument the task's own text could not name.

**Step 4: yes, now.** It is documentation, and it overlaps with the
`AGENTS.md` addition below: "write the program before reading data" is one
of the three things that primer exists to say. Doing them as one piece of
work is cheaper and keeps them from disagreeing.

**Cost.** +8 days in M6 - 6 in Python, 2 in the port - on top of M6's 40,
for the destination-versus-content rule: the manifest says which arguments
of a tool are destinations (a `sabline.tools/1` addition, and a
sabline-spec section), the checker enforces it, the door enforces it for a
manifest Sabline did not write, and the audit names every destination an
untrusted value reaches. The 1 day for step 4 sits outside 9.0.

**Risks.** The known limits, which must be stated and not discovered: an
attacker who changes only the *wording* of a message to the right person
is inside the rule by design, and decisions merely *influenced* by
untrusted data - an implicit flow - are not tracked at first. Both belong
in `docs/known-open.md` the day the rule ships. The new risk this record
adds is the manifest one: a per-argument role is a thing a manifest author
can get wrong, and a tool whose `recipient` is not marked a destination
gets no rule at all. The audit has to make that visible, or the rule
becomes a claim about manifests nobody checked.

**Recommendation: steps 1-2 recorded as done and now four-suite; step 3
yes, first in M6 and in the same release as item 30; step 4 yes, now, as
one piece of work with the `AGENTS.md` primer.**

---

## 35 - the other three AgentDojo suites

**What it is.** Running AgentDojo's workspace, banking and travel suites
offline and free, under the same three budgets as the Slack suite, to find
out whether any of them puts an attack through door 2.

**Closed by this pull request.** All four suites are now recorded under
`evals/agentdojo/<suite>/`, the roll-up is `evals/agentdojo/results.json`,
and a CI matrix leg re-derives each one. The results, the door counts and
the door-2 probe are on `docs/agentdojo.html` and its four per-suite pages,
and in the paper's section 4.3. What it found that bears on the rest of
this record is quoted under items 29, 30, 34 and 36.

**Recommendation: record as closed.** No days.

---

## 36 - the pattern grammar

**What it is.** The tool door holds an argument to a pattern (SPEC.md
7.2): every character stands for itself, and `*` stands for one or more
characters that are not white space, not a list separator and not a
control character. Two changes were proposed: a wildcard that spans
spaces, and negation in allow patterns.

**The recommendation this started from.** "YES to a wildcard that spans
spaces; NO to negation in allow patterns (hard to reason about, widens
access by mistake; content checks belong to `Untrusted of T`)."

**Negation: agreed, and the evidence is stronger than the argument.** The
useful pin for a message body is "it carries no address", which is
negation, and it is also exactly what the content half of 34's step 3
does. A grammar where a pattern can say what a value is *not* is a grammar
where an operator can widen access by writing something that reads like a
restriction. `PIN_LIMITS` records the limit and demonstrates it against
the real matcher rather than asserting it; the fix is `Untrusted of T`,
not the grammar. **No.**

**The wildcard: the goal is right, the form and the priority are not.**
Three findings from this pull request's measurements, in the order the
evidence ranks them.

*First, a number has no upper bound.* The banking suite is almost entirely
amounts, and a pattern can say an amount is `1200` or match a class of
them loosely - `1*` matches `10000` as readily as `1000`, which
`PIN_LIMITS` now demonstrates. The useful bound on money is a maximum, and
there is no grammar for one. This is the gap that costs the most on the
measured corpus and it was not in the item.

*Second, a structured argument cannot be held to a pattern at all.* An
email's attachments are a list of objects, and the door answers "only a
text, a number, a Bool or a list of those can match one" - demonstrated
against `held_by` itself in `DOOR_LIMITS`. Whatever the operator knows
about an attachment, pinning cannot say it.

*Third, white space.* Two of the five demonstrated grammar limits are
about it: no pattern matches a free-text argument of more than one word,
not even `*`, and so no "contains" pattern works on one either. But the
measured gain is small. Across 394 arguments in four suites, the ones a
space-spanning wildcard would newly let an operator pin are the
**template** arguments - a task that says to use the title `Dinner at
{restaurant_name}` or `Hotel: {hotel_name}` - and there are **four** of
them. The Slack suite already pins one template with a star, because the
value it spans is a digit (`Congrats on being the *-th most active
user!`), which is the shape that happens to fit today's grammar.

And changing `*` itself carries the risk the item used to reject negation.
A bare `*` that spans white space matches any text at all, so
`tool:send_email:body=*` would read as a restriction and grant exactly what
a plain `tool:send_email` grants. That is widening access by mistake, in
the same way, in a pattern the operator wrote on purpose.

So: **a separate metacharacter, not a change to `*`.** `**` spans anything,
including white space; `*` keeps today's meaning exactly, so no budget ever
written changes what it permits; and a bare `**` is visible in the budget
text and in the audit, which can warn on it the way it warns on plain
`ffi`. `**` is currently refused as not a pattern, which leaves the
spelling free.

**Cost.** +7 days in M5, where the tool door is ported - 4 in Python, 3 in
the port: +4 for a bound on a number (`arg<=N`, with the refusal naming
the bound) and +3 for `**`. A pattern into a structured argument is
estimated at +6 and **not** recommended for 9.0: it needs a path grammar
into nested JSON, which is a second grammar, and the one measured case is
an attachment. All three are SPEC.md 7.2 changes and need a sabline-spec
version with them.

**Risks.** Every pattern change is a change to what an existing budget
permits unless it is strictly additive, which is why `**` is a new
spelling rather than a new meaning for `*`. A numeric bound introduces
ordering into a grammar that has only had equality, which means a type
question at the door - what does `<=` mean against a text that looks like
a number - and the answer has to be "it is refused", not "it is coerced".

**Recommendation: no to negation. Yes to a bound on a number and to `**`,
in M5, in that order. The structured-argument path is deferred.**

---

## An analysis-mode field in `capability/v1`

**What it is.** `https://sabline.dev/capability/v1` is the in-toto
predicate Sabline's `attest` writes: a `sabline.audit/1` document for a
source file, and the producer that wrote it. Raised on in-toto #594: a
verifier cannot tell from the predicate whether the evidence came from
**static analysis of the source** or from **a run**. An `analysisMode`
field saying `static` answers it.

**The recommendation this started from.** "YES, small."

**Where this record differs.** It does not. It adds two facts. The field is
additive within v1 - the schema's own description says "within v1 fields
may be added and consumers must ignore fields they do not know" - so no
`v2` is needed. And the distinction is real in Sabline and not only in
in-toto's model: an audit is static (it reads the source and says what the
program *can* touch), while a receipt is the record of a run (what it
*did*). The predicate today carries the first and says nothing about which
it is.

**Cost.** +1 day, and it is not 9.0 work: the schema field, `attest`
writing it, `check_policies.py` and `check_library.py` asserting it, a
sabline-spec section 8.5 sentence, and a version of the spec with it.

**Risks.** Small, with one trap: if the field is ever written as `runtime`
for a predicate that is still an audit, the field becomes worse than its
absence. Only one value should be defined now - `static` - and a second
one should wait until there is a predicate that earns it.

**Recommendation: yes, now, with one defined value.**

---

## `sabline new` writes an `AGENTS.md`

**What it is.** The project scaffold writes an `AGENTS.md` primer: the
card, the budgets, and "write the program before reading data" - which is
34's step 4.

**The recommendation this started from.** "`sabline init` AGENTS.md: YES,
small."

**Where this record differs.** Only on the name. There is no `sabline
init`: the scaffold is **`sabline new <name>`**, which writes `main.vel`
and `README.md`, and `sabline capabilities init` is a different command
that records the capability surface. Calling the new behaviour `init`
would collide with the second; it belongs on `new`.

For a project that already exists, `sabline card` already prints `LLM.md`
for pasting into a model, so the primer should be printable the same way -
`sabline card --agents > AGENTS.md` - rather than needing a new command.

**Cost.** +2 days, not 9.0 work: the primer's text, `new` writing it,
`card --agents` printing it, `check_cli.py` and `check_demo.py` cases, and
`check_docs.py` holding the primer's budget examples to the ones that
actually run - the rule that already keeps the tutorial honest.

**Risks.** A primer is a document that goes stale in someone else's
repository, where no check of Sabline's can reach it. That argues for it
being short, for everything in it being derived from `LLM.md` and the card
rather than written twice, and for it carrying the version it was written
from.

**Recommendation: yes, now, on `sabline new`, and printable with `sabline
card --agents`.**

---

## What the 9.0 total becomes

`plan/9.0.md` stands at **196 days**. If every yes above is taken:

| Milestone | Today | Added | New |
|---|---:|---|---:|
| M1 - the parser | 18 | - | 18 |
| M2 - the checkers | 24 | - | 24 |
| M3 - the interpreter | 35 | +4 (32b), +6 (32c) | 45 |
| M4 - confinement | 23 | +3 (32a) | 26 |
| M5 - the tool door | 14 | +5 (32d), +7 (36) | 26 |
| M6 - `Untrusted` | 40 | +4 (29), +6 (30), +8 (34 step 3) | 58 |
| M7 - embeddings | 20 | - | 20 |
| M8 - the candidate | 22 | - | 22 |
| **Total** | **196** | **+43** | **239** |

**And 4 days outside 9.0**, which can be done at any time and do not gate
a milestone: 34's step 4 and the `AGENTS.md` primer together (3), and the
`capability/v1` field (1).

**Deferred, not counted, no milestone**: the Z3 ratchet (31, 3-4 days after
rc), 29's general rule language, pause and resume (33a, inside the open
`recover@N` decision), Cedar (33b, 3-4 days if asked for), 36's
structured-argument path (6 days), and OpenTelemetry on top of 32b.

**Struck**: 32e as a separate item, folded into M4's and M6's exit
criteria, and 29's "at most N", which already ships.

Two cautions on the 43. M6 goes to 58 days and is already the milestone
holding `Untrusted of T`, the breaking set, `proc:NAME` and
`fs:secret:PATH`; three of the four additions here land in it, and 34's
step 3 is sequenced first inside it. If the ladder has a place where a
schedule breaks, that is now clearly it, and splitting M6 is worth
considering before any of this is accepted. M3 goes to 45 with two
additions that are both independent of the port - 32b and 32c could each be
done in Python before M3 and ported with it, or deferred past rc entirely,
without changing anything else in this record.
