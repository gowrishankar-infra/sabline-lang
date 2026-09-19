---
title: "Velaris: effects in signatures, budgets at run time, and a baseline for a repository's capability surface"
author: "Palakurthi Gowri Shankar"
date: "Draft of 2026-09-11 - not submitted"
bibliography: references.bib
link-citations: true
---

<!--
A draft for the author's review. To make a PDF:

    pandoc velaris.md --citeproc -o velaris.pdf

Every number below comes from a file in velaris-lang, or in velaris-spec
where it says so; the table in the reproducibility section names the
file for each. Do not add a number that has no file.
-->

## Abstract

Code written by language models is increasingly run by people who have
not read it. Velaris is a small programming language for that
situation. A function's signature declares which of seven effects it
may perform, and the compiler checks the declaration across the whole
call graph. A runtime refuses any operation outside a budget the
operator writes - before the operation happens, and in a way the
program cannot catch. Contracts are checked by the Z3 prover where it
can settle them, and at run time where it cannot. A repository can
commit a baseline of the capability surface its programs need, and a
check fails any change that needs more. The central claim is about
that surface. Suppose a repository's Velaris programs are held to a
committed baseline by a required check. If a change makes a program
need an effect, path, host, module or operation count the baseline does
not grant, the check fails. It goes on failing at every later commit at
which the program still compiles and still needs it, until a person
edits the baseline. The claim is not about which function an effect is
attributed to: a function renamed in the change that gives it an effect
its program already had escapes the function-level rule. On a benchmark
of 76 programs, 66 with one defect and 10 correct, each written in
Velaris, in JavaScript for Deno and in Python, Velaris caught 64 of the
66 defects, 52 of them before running;
Deno caught 42 and Python 31; none of the three flagged a correct
program. One of Velaris's two misses is a logic error with no contract;
the other no tool should catch. The capability format is published
separately, under CC0, with a conformance corpus of 456 cases that an
implementation in any language can run.

## 1. The problem

A model hands someone a script. They can read it line by line, or run
it on trust. Reading every line is the cost they hoped the model would
save them, and each new script asks it again; trust is what the
situation lacks, because the program's comments, names and structure
were written by the same process whose output is in question. Where
code arrives faster than people read it, review is the step that
gives.

Three things would help a person in that position. The first is to
know, before running a program, what it may do to the world outside
it - which files, which hosts, which parts of the host system -
without reading its body. The second is to be sure, while it runs,
that it does nothing the person did not allow, whatever it says about
itself. The third concerns a repository rather than a program: to know
when the capability of the code in it grows.

The third matters because capability can be assembled a little at a
time. A helper that builds a URL, a function that reads a file, then a
call three levels down that sends one to the other: each change looks
harmless in its own diff. Hills, Caspary and Cooper Stickland study this
setting directly [@hills2026distributed]. A coding agent builds software
over a sequence of pull requests in a persistent codebase while
pursuing a covert side task, and attacks that spread the side task
across pull requests evade monitors that read one diff at a time; no
single monitor they test is robust both to such gradual attacks and to
attacks concentrated in one pull request, and a stateful monitor that
tracks suspicious buildup across pull requests does better against the
gradual ones. Capability is binary and cumulative: the steps of such a
change reach exactly as far as one step that did it all at once. A
comparison of each commit with the one before sees each step alone,
and once a step is merged, sees nothing more of it.

Velaris addresses the three needs with three mechanisms, and adds a
fourth, proofs of contracts, that the others do not depend on. Sections
2.1 to 2.4 describe the four, and section 2.5 the format, published
separately, that specifies the three and not the proofs; section 3
describes the implementation, section 4 what has been measured, section
5 related work and section 6 the limitations.

## 2. Design

Figure 1 shows the pieces this section describes: one program from its
signature to a refused operation, and one repository whose commits are
each compared with the same baseline.

```
(a) One program, one run: examples/effects.vel

fn save_report(text: Text) uses fs {       <- the signature
    write_file("report.txt", text)
}
fn main() uses io, fs, clock, rand { ... }
      |
      |  velaris audit, before it runs
      v
effects: clock, fs, io, rand               <- the audit
reads and writes: report.txt
      |
      |  the operator writes the budget
      v
--allow io,clock,rand,fs:read:./data       <- the budget
      |
      |  at the call, before the write
      v
E313, line 13: 'write_file' reaches        <- the refusal
'report.txt', which this run's fs grants
do not cover. Nothing is written; the run
ends, and the program cannot catch it.

(b) One repository, one baseline

c0: baseline committed, with poll.vel at 10 requests a run

         poll.vel     check, against     review, against
commit   needs        the baseline       the commit before
c1       20           fails: 20 > 10     high
c2       20           fails: 20 > 10     low, sees nothing
c3..c8   40..1000     fails at each;     at c8, sees only
                      c8: 1000 > 10      640 -> 1000
c9       1000, and the baseline edited to 1000:
                      passes             high, names the edit
```

Figure 1: (a) `examples/effects.vel`: what a signature declares, what
the audit reports before the program runs, a budget its operator
writes, and the refusal of the write that budget does not grant. (b)
the second history of section 4.3, from `check_ratchet.py`: c1 raises a
count and is merged, c2 is an unrelated change, and the check compares
every commit with the baseline committed at c0, never with the commit
before it, which is what a review compares.

### 2.1 Effects in signatures

A Velaris function declares what it may do:

    fn save(path: Text, body: Text) uses fs { ... }

There are seven effects: `io` (the console and the program's
arguments), `env` (environment variables), `fs` (files), `net` (the
network), `clock`, `rand` and `ffi` (calling Python, the host
language). A function with no `uses` clause is pure. The rule is
transitive and checked before the program runs: a function may perform
only the effects it declares, and calling a function requires declaring
everything that function declares, whether or not the callee performs
it. A function passed as a value must be pure, and so must any function
a contract calls [@velaris_spec, section 3.2]. A declaration is
therefore an upper bound on what any call to the function can do, at
any depth, and it can be read without reading the body.

An effect name is coarse: `fs` says nothing about which files. The
names are for signatures; the finer distinctions belong to the
operator's budget.

### 2.2 Budgets at run time

The operator writes a budget when running a program:

    velaris agent_output.vel --allow io,fs:read:./data,net:api.example.com:443@100

A grant names an effect and may narrow it: `fs` to a direction and a
path, `net` to a host, a port, or a one-label wildcard (`*.example.com`),
`ffi` to named Python modules, and `fs` and `net` to a count of
operations in the run (`@100`). Grants are additive. Paths are resolved,
symbolic links and `..` included, when the budget is parsed and again at
every file operation, and compared by whole components
[@velaris_spec, sections 4 and 5].

Every operation is checked when it is attempted, in a fixed order: the
effect (refused with E310), then the scope - a module (E311), a path
(E313), a host or port (E314) - then the count (E315). No file is
opened, no connection made and no module imported for a refused
operation. A refusal ends the run: it is not a failure value the
program can inspect, so a `check` or `try` around the call does not see
it. The one exception is a redirect to a host outside the grants, which
fails the request as an ordinary failure naming the target, because the
program did not choose where it was sent. The budget is checked against
what a run attempts, not against what the program declares, so a
program whose declarations were never checked is still held to it
[@velaris_spec, section 6].

A granted Python module is trusted in full. `ffi:os` is the operating
system as the current user. What an `ffi:M` grant does bound is which
modules a call reaches: the attribute chain a call names is walked step
by step, and an object owned by a module outside the grants is refused,
so `py("json", "codecs.encode", ...)` under `ffi:json` is refused for
`codecs`.

### 2.3 Proofs

A function may carry contracts: `requires`, `ensures`, and loop
`invariant`s. The compiler asks the Z3 prover [@demoura2008z3] whether a
contract can be broken, using the contracts of callees rather than
their bodies. A contract shown false is a compile-time error with a
counterexample (E700); so is a call shown to break a callee's
`requires` (E701), a list read shown to pass the end (E705) and a
divisor shown to be zero (E706). A premise the prover cannot translate
abandons the proof, and the contract is checked while running instead:
the compiler does not report a proof it does not have.

Proofs are not part of the capability format. Nothing in sections 2.1,
2.2 and 2.4 depends on them, and an implementation with no prover can
conform to the format at every level (section 2.5).

### 2.4 The ratchet

`velaris capabilities init` reads every `.vel` file in a repository and
writes `velaris.capabilities`: the repository's *surface* - every grant
its programs need, in the budget grammar, and for `fs` and `net` the
most operations one run can perform - and, for each program, its own
grants and counts and the effects each of its functions declares
[@velaris_spec, section 9]. What a program needs is read from its text:
its functions' declarations, and the paths, hosts and modules its calls
name as fixed text - a literal, or a variable bound once to one. A path,
URL or module built while running is recorded as the unscoped grant
(`fs:read`, `net`, `ffi`), which a scoped baseline does not cover. The
operation bound comes from loops whose counter and limit the text
fixes, multiplied through nesting and calls; a loop whose turns the text
does not fix, and recursion, have no bound. The prover takes no part,
so the result is the same with and without it.

`velaris capabilities check` derives the same from the working tree and
compares it with the committed file - with that file, and never with a
previous commit. A change widens the baseline, and the check fails,
under five rules: a grant the surface does not cover (W1); more
operations than the surface's count (W2); for a program the baseline
records, a grant (W3) or a count (W4) beyond its own entry; and an
effect added to a function the baseline records (W5). Narrowing never
fails. A program the baseline does not record is held to the surface
alone. A check that cannot read the baseline - it is missing, is not the
right format, or holds a grant the format does not allow - fails rather
than passes, so deleting the file does not turn the check off. The
writer will not replace an existing baseline unless asked to in so many
words, so every widening that is accepted arrives as an edit to the
file, in review.

Because the comparison is with the baseline, a widening merged once
goes on failing at every later check until someone edits the file, and
a widening assembled over many commits is reported as its whole sum
(Figure 1b). That is the property the gradual attacks of section 1 need
to defeat.

**The central claim.** Suppose a repository's Velaris programs are held
to a committed baseline by a required check. If a change makes a
program need an effect, path, host, module or operation count the
baseline does not grant, the check fails. It goes on failing at every
later commit at which the program still compiles and still needs it,
until a person edits the baseline. Which entries count depends on the
program: for one the baseline does not record, or records as not
compiling, the baseline grants what its surface grants; for one it
records as compiling, only what both the surface and the program's own
entry grant.

"Needs" there is what the program's text requires by the derivation of
velaris-spec section 9.3: the declared surface. Three things follow
that the claim does not make. It does not say what a granted module
does: a program newly calling `os.system` through a baseline's `ffi:os`
is inside the surface. It does not say where a path leads: paths in a
baseline are compared as text, and a symbolic link under a recorded
directory is that directory's content; the budget, which resolves every
path at run time, is where that is caught. And it does not say which
function an effect belongs to: a function is known by its file and
name, so a helper renamed in the same change that gives it an effect
its program already had is a new function, held to its program's entry
and the surface but not to what its old name declared, and W5 does not
report it. The declared surface did not widen in that case, and the
check is right to pass it; what escapes is the attribution.

A separate command, `velaris review --against REF`, reports how the
working tree differs from a git ref, with a one-word risk. It compares
with a previous state, so it informs a reviewer and is not the gate.

### 2.5 The format, published separately

The effects, the budget grammar, what a runtime must refuse,
`velaris.audit/1` (the JSON report of what a program declares and names
before it runs) and `velaris.capabilities/1` are specified separately,
under CC0, as velaris-spec [@velaris_spec], so that they can be
implemented without reading the compiler. Its conformance document
defines three levels: L1, declaration - parse the budget grammar,
compute a program's effect surface, emit `velaris.audit/1` that
validates against its schema; L2, enforcement - refuse at run time
every operation outside the budget, uncatchably; L3, the ratchet - write
and read baselines and classify widening against narrowing for every
kind of scope. L2 and L3 each require L1; L3 does not require L2, so a
tool with no runtime can conform at L1 and L3. No level requires a
prover. Conformance is shown by running a corpus of JSON cases,
described in section 4.2. velaris-spec also defines an in-toto predicate
type that binds an audit to the digests of the files audited, so that a
signed statement can say which source an audit describes; velaris-lang
4.2.0 writes such statements, unsigned (`velaris attest`), and leaves
signing to Sigstore's tools.

## 3. Implementation

The implementation, velaris-lang [@velaris_lang], is one Python file,
`velaris.py`, of 13,497 lines - one file by design: nothing to install
but Python, nothing vendored, a single artifact to sign and audit. It
is laid out in the order a program passes through it: lexer, parser,
loader, effect checker, type checker, prover, native code generation,
interpreter. The prover needs the optional `z3-solver` package and the
native code generator the optional `llvmlite`; without them, contracts
are checked while running and everything is interpreted, and the
effect checks and the budget are unchanged.

The budget is enforced in the interpreter, at each builtin that
performs an operation, before the operation. A run with a time limit
or a memory cap runs in a child process that can be killed, and a pool
of such workers re-installs the budget before every program. The same
checks sit behind every interface: the command line, a Python library
(`check`, `audit`, `run`, `Pool`), an HTTP door and an MCP server whose
operators set ceilings callers cannot exceed, and a GitHub Action that
runs the capability check and uploads findings as SARIF. Every error
has a stable code; the compiler's table holds 62.

The budget is not a security boundary. It is enforced by an interpreter
written in Python, in the same process as the compiler and, unless a
limit is set, the program. It is a guard against a program doing what
it was not asked to, and it belongs inside an operating-system sandbox
when the stakes warrant one.

## 4. Evaluation

### 4.1 A benchmark against Deno and Python

The benchmark is 76 small programs, each written three times with the
same behaviour: in Velaris, in JavaScript for Deno, and in Python.
Sixty-six contain one deliberate defect, on one line marked in all three
sources; ten are correct controls. They fall in fifteen categories: a
file write hidden in a helper, a network call hidden in a helper,
division by a value that can be zero, a read past the end of a list,
integer overflow, an ignored failure, an infinite loop, runaway memory,
reaching a dangerous module, correct programs that must not be flagged,
a grant narrower than the effect, indirect authority - a caller
that does not change while a dependency's declared budget widens
between two versions - a TrapDoor, a program whose stated purpose
and behaviour differ, a skill script whose helper reads a credential and
sends it elsewhere, and an import of a library that does not exist where
its program names it. One harness runs every program
through every tool with the same rules: a 5-second timeout, a 256 MB
memory cap, and for Velaris the narrowest budget each task needs. Each
program gets one verdict per tool - caught before running, caught while
running, missed, or, for a control, clean or a false positive - and
after every run the harness observes whether the dangerous effect
actually happened: a file created, a request received by a local
listener, a subprocess's sentinel printed. The committed results were
produced by Velaris 8.3.0, Deno 2.9.6 and Python 3.13.13 on Windows 11,
in ten consecutive runs that wrote identical files, and the 68 programs
of the first thirteen categories kept every verdict they had at Velaris
8.2.0. Before that, the 67 programs of the first twelve categories kept
every verdict and every line of evidence they had at Velaris 7.1.1, and
ten consecutive runs at 7.1.0 had written identical files. The 63
programs of the
first eleven categories kept the verdict each had under Velaris 4.1.0;
Velaris 3.0.0, with the same Deno and Python on the same platform, had
produced that table before 4.1.0, every verdict and every line of
evidence.

| Tool | Caught before running | Caught while running | Missed | False positives (10 controls) |
|---|---|---|---|---|
| Velaris | 52 | 12 | 2 | 0 |
| Deno | 8 | 34 | 24 | 0 |
| Python | 0 | 31 | 35 | 0 |

Table 1: the 66 dangerous programs and the 10 controls, from
`benchmark/results.json` at Velaris 8.3.0.

Where the catches come from differs by tool. Velaris's catches before
running come from effects in signatures (the file, network and module
categories, the environment secret of category 11, and the TrapDoor of
category 13), from
unhandled-failure checks and the prover (division, list reads, ignored
failures), from a comparison of two versions of a dependency's declared
surface (category 12), and from its termination rule, which flags a
loop whose
counter does not move one step toward an unchanging limit. That rule
flagged the eleven infinite and memory-growth programs before running;
it claims nothing about whether such a loop ends, and each of these
happened not to. Deno's catches are almost all at the moment of the
call, through its permission flags; nothing in `deno check` or
`deno lint` reads a file write or a fetch as a problem. In one network
program, and in the three upgrades of category 12, Deno denied the
request or the write but the program caught the denial, which is an
ordinary exception in JavaScript, and exited 0; the harness credits
Deno because it observed that the effect did not happen, and a caller
reading only the exit status would have seen success. A Velaris refusal
cannot be caught.

Category 12, added with Velaris 7.1 at a reader's suggestion
(CHANGELOG, 7.1 entry), is indirect authority: a calling program that
is the same file before and after an upgrade, and a dependency whose
declared budget widened between the two versions - gaining `net`,
gaining a second host inside the `net` it already had, or gaining
`fs:write` beside the read it had - with a control whose dependency
narrowed. Each caller already declares the effect its dependency comes
to use, so it compiles against both versions and the compiler has
nothing to refuse. The Velaris static step there is `velaris
deps-diff`, which derives each version's surface as section 2.4 does
and holds the newer one to the older with the same five rules; it
flagged the three before running and did not flag the control. A
JavaScript or Python module declares no surface, and `velaris
deps-diff` reports such a dependency's surface as unknown rather than
reading effects off its source, so the category shows what a declared
surface makes checkable, not a way to check code that declares none.

Category 13, added with Velaris 8.0 (CHANGELOG, 8.0 entry), is one
program whose stated purpose is a scan for secrets and whose behaviour
is to read a credential file and post it to a URL. Velaris flagged it
before running - its audit lists `net`, which a scanner does not need -
and the run was refused at the read (E318). Deno's run stopped before
the request was made; Python's made it.

Velaris alone caught the six integer-overflow programs, while running:
its whole numbers are 64-bit and arithmetic that leaves that range stops
the program (E407). Python's integers do not overflow, so its printed
values are arithmetically right and only wrong for a 64-bit consumer;
the results record those rows as Python misses and say a reader may
discount them. Python's catches in the division and ignored-failure
categories are crashes on the inputs the harness supplies - a zero, a
non-number, a missing key - and with ordinary input those programs run
clean; Velaris's E520, E705 and E706 do not depend on the input. Four
Velaris catches came only at run time where a sibling program was
caught before running: a division on the unguarded one of two paths, a
remainder inside a loop, a division in `main` on `n - 1`, and a read at
`i + 1` in a loop bounded by the list's length. The prover did not
settle those, and the runtime checks stopped them.

Velaris missed two programs, both included on purpose so that the table
is not a list of what the language was built to do. In `04c` a loop
stops one item early: no read is out of range and the function has no
contract, so a wrong total is indistinguishable from a right one. In
`09c` a program prints `rm -rf build` as a hint for its caller and
touches nothing; its only effect is `io`, which the task needs. That
one should not be caught by any tool: control program `10d` prints the
same words in a warning and is harmless, and nothing that looks at the
program from outside can tell the two apart. The danger is in what a
caller does with the text.

**What this benchmark does not show.** The programs were written for it
by this project; in the first ten categories, three of each six were
written after the first three, against the tools, to hide the same
defects better. It is small. The inputs were chosen to trigger each
defect. The committed run is one machine's. Category 12's dependencies
were written for it rather than taken from published packages, and its
Velaris catches come from comparing declared surfaces, which a package
in another language does not have. And it measures programs,
not the ratchet, which section 4.3 treats separately. The harness is
in the repository, its rules are one function each, and the evidence
for every cell is recorded next to the verdict, so a reader who
disagrees with a row can change the rule and rerun it.
`benchmark/run.py --check` reruns the whole table and fails if any
verdict differs from the committed `benchmark/results.json`.

### 4.2 The suites, and a conformance corpus

Each guarantee has a suite that asserts it, and each suite runs on
every push on Linux, Windows and macOS, with Python 3.10 and 3.12, with
and without the prover. `check_sandbox.py` holds 34 attempts to escape
a budget - an effect two helpers below `main`, a refusal caught to
carry on, a module reached through a submodule path, `py_json` or a
handle, a path out of a prefix by `..` or a symbolic link, a host, a
port, a wildcard's parent domain, a count, a URL with no scheme taken
as HTTPS - each refused with the code it must carry, and 16 honest
programs that must still run. Run on Windows with the prover,
`check_ratchet.py` passes 114 checks of the ratchet, `check_library.py`
196 of the library, the doors, the audit and its attestations (its one
symbolic-link case runs only on POSIX), `check_refusals.py` 21 wrong
programs each refused with the right code, `check_fallible.py` 26
fallible builtins, and `check_termination.py` 44 adversarial loops;
without it, `check_library.py` passes 193 and `check_refusals.py` 11,
skipping the checks that are about proofs, and the rest are unchanged
(CHANGELOG, 4.2).

Those suites drive velaris-lang's own command line and Python library,
so until velaris-lang 4.1 an implementation in another language could
use them only through an adapter. velaris-spec now holds a corpus of
456 JSON cases that any implementation runs its own way: 307 at L1 (280
budgets to parse or refuse, 27 programs to audit), 40 at L2 (programs
to run under a budget, with a fixture of files and two local HTTP
servers) and 109 at L3 (baselines to write, changes to check, two
sequences of changes, the writer's guard, and the covering, reduction
and operation-bound rules case by case). A script writes the corpus
from the tables of three of the suites, where each entry is also
asserted against velaris-lang, and a drift test in both repositories'
CI regenerates it and fails if it differs from what is committed.
Nineteen scenarios are left out and listed with the reason: six depend
on Python's object model, four need a Python host, five turn on what a
run given no budget gets - three such runs, and two denials that narrow
it - which the format leaves to the implementation, two are about
velaris-lang's command-line flags, one is its `all` shorthand, and one
the wording of its messages. `velaris conformance` runs the
corpus against velaris-lang; it passes at all three levels
(velaris-spec `tests/index.json`; CHANGELOG, 4.2).

Writing the corpus found a defect. The audit of a program refused for
naming an unknown effect still listed that name among the program's
effects, and wrote a suggested budget that does not parse, although the
specification said neither could happen. velaris-lang 4.1.0 fixes the
implementation, and velaris-spec 0.4 corrects the text that had claimed
more than the implementation did.

### 4.3 The ratchet

`check_ratchet.py` builds scratch trees and real git histories and
asserts what the check says at every step. In its gradual case, a
greeter program is committed with its baseline, and six changes follow:
a pure text helper; the greeting using it; a pure summary function;
`main` printing a summary; a function returning a collector's URL as
text; and finally a summary delivered to that URL through a helper
three calls below `main`. The first five pass. The sixth fails, naming
`net:collector.example.net` as a new effect, the file `lib/deliver.vel`,
line 2, the function `send`, and the chain `main -> summary -> deliver
-> send`. A review of each change against the one before calls the
first five `low` and the sixth `high`. In a second history a count of
10 requests a run is raised and merged, and keeps failing at every later
commit; seven steps from 10 to 1000 are reported by the check as 1000
against the declared 10, while a comparison with the previous commit
shows only the last step, 640 to 1000. The suite also holds changes
that must pass - reordering, reformatting, renaming locals, a literal
moved into a variable, a function renamed or moved, narrowing, a new
program inside the surface - and baselines that cannot be read, which
must fail.

The five known limits of section 6 are cases too, each recording the
outcome the check gives today, so that another implementation matches
it and so that a change to it is visible. The repository checks itself:
its own `velaris.capabilities` records 172 programs, 22 of them built to
be refused and recorded as not compiling, and CI runs the check on
every leg.

The ratchet has not been measured on the gradual-attack benchmark of
Hills et al., whose code is not Velaris, or on any repository but its
own. What is claimed for it is a property of a deterministic
comparison, in the same sense that soundness is a property of a type
system, and not a detection rate. A rate measures how often a heuristic
notices something. The ratchet does not notice; it computes, and the
cases in `check_ratchet.py` show what it computes. The property is the
one stated in section 2.4, with the three things it does not say there
and the five known limits of section 6, and it rests on the
comparison's definition and on those cases: it has not been proved
mechanically.

## 5. Related work

This section says what each piece of work does and how Velaris differs.
It claims priority over none of it; velaris-lang's changelog does not
name any of it as the source of a design decision.

**Object capabilities.** Dennis and Van Horn introduced the capability,
a reference that both names a resource and carries the right to use it
[@dennis1966semantics]; Miller's object-capability model builds least
authority from references a program has been handed
[@miller2006robust]. A Velaris effect is a name in a signature, and a
budget is ambient to a whole run: any function declaring `fs` may reach
any path the budget allows without holding a reference to it. Nothing
in Velaris is unforgeable, and nothing is handed over. "Capability" in
the format's name follows common usage.

**TACIT.** Odersky and colleagues have agents write Scala 3 with capture
checking, in which capabilities - a file system rooted at a directory, a
set of hosts, a set of commands - are values the type system tracks,
and pure computations over classified data cannot leak it
[@odersky2026tacit]. In Velaris capabilities are effect names plus an
operator's budget written as text and enforced by an interpreter, in a
small language a model learns from a card; it has no counterpart to
TACIT's information-flow control, and no grant for running commands.

**CaMeL.** Debenedetti and colleagues have a privileged model turn a
trusted request into a program in a restricted subset of Python, run by
an interpreter that attaches to every value its provenance and permitted
readers and checks a policy at each tool call, while a quarantined
model parses untrusted data [@debenedetti2025camel]. Velaris tracks
nothing about data: a budget bounds which effects, paths, hosts and
modules a run may reach, not which values may flow to them.

**WASI.** The WebAssembly System Interface gives a module only the
directories, sockets and other resources its host hands it as handles,
so a module given nothing reaches nothing [@wasi]. Velaris's grants are
text an operator writes, enforced inside the same process rather than
at a virtual machine's boundary. Until version 5.0 its command line
granted every effect when no budget was given, so deny-by-default held
only once an operator wrote one; 5.0 made the default `io` - the
console and nothing else - in the command line, the library, the worker
pool and both doors, so a run that asks for nothing now gets close to
what a WASI module given nothing gets, and `--allow all` is the
explicit way to ask for everything.

**Deno.** Deno's permission flags give a script no file, network,
environment or subprocess access unless granted, with scoped forms much
like Velaris's grammar [@deno_security]; section 4.1 compares the two
directly. A Deno denial is an exception a script can catch; a Velaris
refusal ends the run. Deno checks at the call; Velaris also declares the
effect in the signature, so it is visible before running.

**Effect systems.** Lucassen and Gifford's polymorphic effect systems
record in an expression's type the side effects evaluating it may have
[@lucassen1988effects]. Velaris's `uses` is a fixed set of seven names
with no polymorphism - a function value is simply required to be pure -
a small instance of the idea.

**in-toto and SLSA.** in-toto binds signed statements about software
artifacts to subjects identified by digest [@torresarias2019intoto;
@intoto_attestation], and SLSA defines levels of build integrity and a
provenance predicate [@slsa]. Velaris's documents describe what a source
text declares, not how or by whom an artifact was built. velaris-spec
defines an in-toto predicate type for the audit, and velaris-lang 4.2.0
writes statements of it; its release workflow signs one for an example
program with Sigstore's tools and verifies it.

**SARIF.** SARIF is a common format for the findings of static analysis
tools [@sarif2020]. velaris-lang writes its compile errors, unproven
promises and capability widenings as SARIF for code scanning; the audit
itself describes a program rather than listing findings, and is not
SARIF.

**Gradual attacks.** Hills, Caspary and Cooper Stickland show that a
coding agent can spread a covert side task across pull requests so that
no single diff looks decisive, that such attacks evade diff monitors,
and that a stateful monitor tracking buildup across pull requests
detects them better [@hills2026distributed]. The ratchet is not a
monitor of intent. It is a deterministic comparison of what a
repository's Velaris programs need with a baseline the repository
declared, at every change. It sees the part of a gradual attack that
needs capability the baseline did not declare, and nothing else: a side
task that stays within the declared surface, or is not written in
Velaris, is outside it.

**AI-first languages.** A catalogue of languages designed for models
rather than for people lists 41 projects in three camps: syntactic ones
that strip ambiguity at the token level, verification ones that make
contracts mechanically checkable, and orchestration ones that treat the
matter as agent coordination [@agentlanguages]. Velaris belongs in the
second and third, and several entries occupy close ground, reached
independently: velaris-lang cites none of them. Boruna is a
deterministic, capability-safe workflow language whose functions
declare effects in a `!{...}` clause, whose virtual machine gates every
call against an operator's policy over capabilities, endpoints, models
and per-step budgets, and whose runs produce hash-chained evidence
bundles that replay to identical outputs [@boruna]; it parses `ensures`
without enforcing it and has no prover, its evidence describes a run
where Velaris's audit describes a source text and binds to in-toto and
SARIF, and it grants nothing by default, where Velaris without a budget
granted all seven effects until version 5.0 and grants `io` - the
console alone - from it. Boruna's default is still the stricter of the
two: it grants nothing, and a Velaris program with no budget can print. Thermite mandates `req`, `ens` and `fx` on
every function and settles each obligation separately on a five-rung
ladder from reconstruction in Lean down to an always-active runtime
check, recording engine and level per clause [@thermite]; its
verification is well ahead of Velaris's single Z3 tier, and the
difference is who writes the policy - Thermite derives a seccomp filter
from the program's own `fx`, where a Velaris budget is the operator's
and may be narrower than the program declares. Vera makes `requires`,
`ensures` and `effects` mandatory and sorts each obligation into Z3's
decidable fragment or a compiled runtime guard, with a conformance
corpus and a draft specification [@vera], but bounds no paths or hosts
at run time and keeps no audit record. AILANG declares effects as rows
in signatures and grants capability categories at the command line, not
wideable from within [@ailang] - Velaris's arrangement, at the
granularity of the category rather than the resource. No entry combines
all four of effects in signatures, an operator's budget refused against
at the operation, a prover with a runtime fallback, and a published
format for the declared surface.

## 6. Limitations

These are stated as velaris-lang's THREAT_MODEL.md states them.

- **Only code written in Velaris.** A model asked for Velaris may hand
  back Python. Nothing here applies to code the Velaris runtime does not
  run.
- **A granted `ffi` module.** A granted module can do whatever it can
  do. `ffi:os` is the operating system; `ffi:subprocess` is a shell. The
  grant narrows which modules a call may reach, not what a module does.
- **Logic errors with no contract.** A function that returns the wrong
  number and promises nothing is correct as far as the compiler knows.
  Benchmark program `04c` is this, and is a miss.
- **The meaning of text.** A program that prints a shell command for its
  caller touches nothing. No effect system can tell it from a program
  that prints the same words as a warning, and Velaris does not try.
- **One maintainer.** The project is maintained by one person. Fixes to
  soundness and sandbox reports are promised within a week, and nothing
  else is promised.
- **Not a security boundary.** The budget is enforced by a Python
  interpreter in the same process as the compiler. A defective or
  altered `velaris.py` holds nothing. Side channels, resource use below
  the limits, where a granted host name resolves, and what a granted
  host does with a request are outside the model.
- **The ratchet.** The declared surface cannot widen without the check
  failing (section 2.4); these are its known limits, each held as a case
  in `check_ratchet.py` and in the corpus with the outcome it has today.
  Two widenings that pass: a function renamed in the same change that
  gives it an effect its program already had evades function-level
  attribution (W5), though the declared surface did not widen; and what
  a granted `ffi` module does is outside the program's text. Three
  changes that do not widen and are reported as widenings, each a
  conservative false positive: a loop limit behind a function call
  (`for i in 0 to limit()`) loses its bound and is reported as
  unbounded; a path passed to a helper as a parameter is taken as
  unscoped even when every caller passes a literal; and a path written
  with a backslash is covered only by the same text, so `data\in.csv`
  is outside a recorded `data` even on Windows, where it is inside. The
  ratchet also guards nothing if the check is not required, and an edit
  to the baseline is an accepted widening whose review is the control.
- **The evaluation.** Section 4.1's benchmark was written by this
  project and is small; no user study has been done; the ratchet's
  properties rest on its definition and its cases, not on a measured
  detection rate.

## 7. Conclusion

Velaris puts what a function may do in its signature and checks it
across the call graph; refuses, while a program runs, every operation
outside a budget its operator wrote, in a way the program cannot catch;
proves contracts where the prover can; and holds a repository's
declared capability surface to a baseline that only an edit can widen.
The first three can be tested program by program, and on the first
eleven categories and the thirteenth to fifteenth of a 76-program
benchmark they caught 61 of 63 defects; the fourth's comparison,
applied to two versions of a
dependency, caught the three defects of the twelfth; and no correct
program was flagged. The fourth is a property, not a rate: under a required check,
the declared surface does not widen without the check failing, however
the change is divided among commits. What it does not do - attribute an
effect to the right function across a rename, see into a granted module,
tell harmless text from a dangerous command - is stated here as
precisely as what it does, because the second list is only worth
believing if the first one is.

## Use of generative AI

The software described here was developed by the author with the
assistance of AI coding agents, and the first draft of this paper was
written by an AI coding agent from the repository's contents under the
author's direction. The author specified the structure and claims,
reviewed and revised the text, and is responsible for its accuracy.
Every number reported was verified against the repository files named
in the reproducibility section. Three adversarial reviews by AI
systems, credited in the repository's HALL_OF_FAME.md, found defects
that are recorded in its changelog.

## Reproducibility

This paper describes Velaris 4.2.1 and velaris-spec 0.5.1, and every
number in it was verified against those two tags except the
benchmark's: the benchmark figures of the abstract, section 4.1,
Table 1 and the conclusion are from `benchmark/results.json` at
Velaris 8.3.0. Releases after 4.2.1
postdate the paper and are not reflected in it: 4.3.0 added `Money of
CUR`, an exact decimal whose split is proven to add back up; 4.3.1 made
a proof that exhausts its time budget say so rather than fall silently
back to a runtime check; 4.4.0 added a reference platform service; and
5.0.0 made `io` the budget a run gets when nobody writes one, where
every version this paper measured granted all seven effects - the
related-work paragraphs on WASI and on Boruna say what changed, and
velaris-spec 0.6.0 restates its sections 4.4 and 4.6 to match; 6.0.0
and 7.0.0 added `Secret of T`, a value a program cannot print, send or
branch on without declassifying it with a stated reason; 7.1.0 added
`velaris deps-diff` and the benchmark's twelfth category; 7.1.1
made 7.1.0 import on Python 3.10 and 3.11, and changed nothing the
benchmark measures; 7.1.2 and 8.1.1 closed two ways for a planted
proof cache to report a false promise as proven; 7.2.0 changed how
releases are made; 8.0.0 made four changes that break programs or
commands 7.x accepted, and added the benchmark's thirteenth category;
8.1.0 added receipts of a run; 8.2.0 split the compiler into one
module per stage and keeps no proof cache at all; and 8.3.0 added an
evaluation profile, a comparison and a replay of receipts, and the
benchmark's fourteenth and fifteenth categories. Later
patches corrected documentation and packaging. What each one changed is
in the two repositories' changelogs.
The tags below are therefore the ones to check out, not the current
releases.

The numbers in this paper can be regenerated from the two repositories
at their tags:

    git clone https://github.com/gowrishankar-infra/velaris-lang
    git clone https://github.com/gowrishankar-infra/velaris-spec
    git -C velaris-spec checkout v0.5.1
    cd velaris-lang

    # Table 1, at v8.3.0 (Deno 2.x on PATH for the Deno column; 4 to 8 minutes)
    git checkout v8.3.0
    pip install ".[full,test]"         # the prover, the native compiler, jsonschema
    python benchmark/run.py --check    # exit 1 if any verdict differs

    # everything else, from v4.2.1
    git checkout v4.2.1
    pip install ".[full,test]"

    # Figure 1a
    velaris audit examples/effects.vel
    velaris examples/effects.vel --allow io,clock,rand,fs:read:./data

    # section 4.2 and 4.3
    python check_sandbox.py
    python check_library.py
    python check_ratchet.py
    python check_refusals.py
    python check_fallible.py
    python check_termination.py
    velaris conformance --corpus ../velaris-spec/tests
    python build_conformance.py --check ../velaris-spec/tests
    velaris capabilities check .

    # the same without the prover
    python -m venv bare
    bare/bin/pip install ".[test]"     # bare\Scripts\pip on Windows
    bare/bin/python check_sandbox.py   # and each command above

Where each number comes from:

| Number | File |
|---|---|
| 76 programs, 66 dangerous, 10 controls, fifteen categories; 52/12/2, 8/34/24, 0/31/35; 0 false positives; Velaris 8.3.0, Deno 2.9.6, Python 3.13.13, Windows 11; 5 s timeout, 256 MB cap; the misses `04c` and `09c`; 61 of 63 in categories 1 to 11 and 13 to 15; category 12's three upgrades and one control; category 13's program, its verdicts and E318; categories 14 and 15 | `benchmark/results.json` at v8.3.0 |
| three of each six programs written against the tools; about four minutes for a full run, five to eight on a slower machine | `benchmark/README.md` at v8.3.0 |
| the 68 programs of categories 1 to 13 unchanged in verdict since 8.2.0; ten identical runs at 8.3.0; categories 14 and 15 added in 8.3 | `benchmark/results.json` at v8.2.0 and at v8.3.0, and `CHANGELOG.md`, 8.3 entry |
| the 67 programs of categories 1 to 12 unchanged in verdict and evidence since 7.1.1 | `benchmark/results.json` at v7.1.1 and at v8.2.0 |
| category 13 added in 8.0 | `CHANGELOG.md`, 8.0 entry |
| ten identical runs at 7.1.0; the verdicts of the 63 earlier programs unchanged from 4.1.0; the run at 7.1.1 differing only in its version | `CHANGELOG.md`, 7.1 and 7.1.1 entries |
| the same table from Velaris 3.0.0 | `benchmark/RESULTS.md` at v4.0.0, and `CHANGELOG.md`, 4.1 entry |
| seven effects; the refusal codes E310, E311, E313, E314, E315 | `SPEC.md` section 7 and 7.1 |
| E407, E520, E700, E701, E705, E706; 62 error codes | `velaris.py`, `ERROR_TABLE` |
| Figure 1a: the program, its effects and paths, line 13 | `examples/effects.vel` |
| 13,497 lines | `velaris.py` |
| 34 escape attempts and 16 honest programs | `check_sandbox.py`, `ESCAPES` and `HONEST` |
| Linux, Windows and macOS; Python 3.10 and 3.12; with and without the prover | `.github/workflows/test.yml` |
| 114, 196, 21, 26, 44 checks; 193 and 11 without the prover | `CHANGELOG.md`, 4.2 entry |
| 456 cases: 307, 40, 109; 280 budgets, 27 audits; 19 left out | velaris-spec `tests/index.json` |
| the six-commit history; line 2 of `lib/deliver.vel`; 10 to 1000, 640 to 1000, and Figure 1b | `check_ratchet.py`, `SEQUENCES` |
| five known limits | `check_ratchet.py`, `CHECKS`; `CHANGELOG.md`, 4.0 entry |
| 172 programs, 22 not compiling | `velaris.capabilities` |

## References
