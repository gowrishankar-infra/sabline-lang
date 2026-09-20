<!-- mcp-name: io.github.gowrishankar-infra/velaris -->
<!-- The line above proves to the MCP registry that this package and the
     server io.github.gowrishankar-infra/velaris have the same owner. It is
     read from this file as published to PyPI; removing it breaks publishing
     to the registry. See integrations/mcp_registry/server.json. -->

<div align="center">

# Velaris

**An AI wrote you a script. Run it anyway.**

A language where a function's signature declares what it may touch —
and the runtime refuses anything you did not allow, whatever the code
says about itself.

Not a security boundary by itself: an interpreter in the program's own
process enforces the budget. From 8.4 the operating system is asked to hold
the same budget under it - fully on Linux, partly on macOS and on Windows -
and each run says which it got ([THREAT_MODEL.md](THREAT_MODEL.md),
[docs/confinement.md](docs/confinement.md)).

[![PyPI](https://img.shields.io/pypi/v/velaris-lang)](https://pypi.org/project/velaris-lang/)
[![tests](https://github.com/gowrishankar-infra/velaris-lang/actions/workflows/test.yml/badge.svg)](https://github.com/gowrishankar-infra/velaris-lang/actions/workflows/test.yml)
[![release](https://img.shields.io/github/v/release/gowrishankar-infra/velaris-lang)](https://github.com/gowrishankar-infra/velaris-lang/releases)
[![license](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[**Playground**](https://velaris-lang.dev/playground.html) · [**Documentation**](https://velaris-lang.dev/) · [**Reference**](SPEC.md) · [**Library**](https://velaris-lang.dev/library.html) · [**Errors**](https://velaris-lang.dev/errors.html)

</div>

<img src="docs/hero.png" alt="Velaris refusing a network call because the run only allowed io" width="100%">

---

<!-- illustrative lines 1: installs from PyPI -->
```sh
pip install velaris-lang
velaris agent_output.vel
```

That program cannot open a socket, read a file, call Python, or ask the
clock. Not "shouldn't" — the runtime refuses, and a refusal cannot be
caught and carried past. You do not have to read the code, understand
it, or trust the compiler's analysis of it.

Since **5.0** that is what a run with no `--allow` gets: `io`, the
console. It used to be all seven effects, which meant the answer to
"what may this program do?" was "everything" until an operator said
otherwise. Widen it by naming what the program needs
(`--allow io,fs:read:./data`); `--allow all` grants every effect and
writes one line to stderr saying so.

`--allow io,ffi:math,json` grants Python for those modules only; a call
that reaches any other module — named, or reached through an attribute of
a granted one — is refused (E311). A granted module can still do whatever
that module itself can do: `ffi:os` is the operating system. Since 3.0
the same grammar
narrows every coarse effect: `fs:read:./data`, `fs:write:./out`,
`net:api.example.com:443`, `net:*.example.com`, and `@100` for at most
that many operations in a run; `env` is its own effect, so an
`io`-only program cannot read the environment. `timeout` and
`max_memory_mb` are available through the library and every door, and
on a door the operator's limits are ceilings a caller cannot raise.
It is still not a security boundary - but the
caveats every review raised, the ffi cliff, unbounded execution, and
`fs` and `net` with no path or host list, are now precise permissions
rather than holes. It is a real guard for the situation everyone is
now in — running a program someone, or something, else wrote.

## The other half: promises, proven

<!-- expect: E700 -->
```vel
fn discount(price: Int) -> Int
    requires price >= 0
    ensures result >= 0
{
    return price - 10
}
```

<!-- output: codes only; the counterexample is the prover's choice -->
```text
error[E700] promise cannot be kept: 'discount' ensures result >= 0 - proven without running the program: price = 5 gives result = -5
```

That `ensures` is not a comment or a runtime assert. The Z3 theorem
prover verifies it for **every possible input** before execution — and
refutes it with an exact counterexample when it lies.

## A rule the customer wrote

A commerce platform lets each customer write their own discount rule.
This one has the shape most of them have: a percentage off once the
basket passes a threshold, a flat amount off as well, and a cap on the
two together.

```vel
record Rule {
    percent: Int         // this much off, once the basket is
    above: Money of INR  // worth at least this,
    flat: Money of INR   // and this much off as well,
    cap: Money of INR    // but never more than this, all together
}

fn discount_for(total: Money of INR, rule: Rule) -> Money of INR
    requires total >= money(0, "INR")
    requires rule.percent >= 0
    requires rule.percent <= 100
    requires rule.flat >= money(0, "INR")
    requires rule.cap >= money(0, "INR")
    ensures result >= money(0, "INR")
    ensures total - result >= money(0, "INR")
{
    let off = money(0, "INR")
    if total >= rule.above {
        off = percent_of(total, rule.percent, 100, "half_up")
    }
    off = off + rule.flat
    if off > rule.cap {
        off = rule.cap
    }
    if off > total {
        off = total
    }
    return off
}
```

The two `ensures` are what the platform needs to know about a rule it
did not write: a discount is never a surcharge, and what is left after
it is never negative. Both are settled for every basket and every rule
the types allow, before the program runs.
[`examples/discount.vel`](examples/discount.vel) is the whole program —
<!-- count:discount-proven:word -->five<!-- /count --> of the <!-- count:discount-promised:word -->five<!-- /count --> functions that make a promise
proven, and it runs under `--allow io`.

[`examples/discount_bad.vel`](examples/discount_bad.vel) is the same
rule with the last `if` deleted. The cap still holds the discount to a
fixed ceiling; nothing holds it to what the basket is worth:

```console
$ velaris check examples/discount_bad.vel
examples/discount_bad.vel:54: [E700] promise cannot be kept: 'discount_for' ensures total - result >= money(0, "INR") - proven without running the program: rule = Rule(percent: 0, above: 0, flat: 2, cap: 1), total = 0 gives result = 1
```

The amounts are in paise: a basket worth nothing, a flat discount of
two paise held down to a cap of one, and one paisa handed back anyway.
The program does not run.

A sandbox answers a different question. It can stop this rule reading a
file or opening a socket; it cannot tell you whether the arithmetic
holds.

## A key it cannot print

Effects say a program printed something. They do not say whether what
it printed was the secret. `Secret of T` (6.0, 7.0) is the other half: the
compiler tracks the value, and refuses any program that hands it to
anything that emits.

```vel
fn key() -> Secret of Text uses env {
    return env("API_KEY", "")          // env() gives a Secret of Text
}

fn authorization(k: Secret of Text) -> Secret of Text {
    return "Bearer " + k               // still a Secret of Text
}
```

[`examples/secret.vel`](examples/secret.vel) reads an API key, builds
the request that would carry it, and prints a summary of that request.
[`examples/secret_bad.vel`](examples/secret_bad.vel) is the same
program with one more line:

```console
$ velaris examples/secret_bad.vel --allow env,io
error[E560] argument 1 of 'print' is Secret of Text, and 'print' performs io - a Secret cannot be printed, written, sent or passed to Python. It came from env(), line 27, through 'key', which returns Secret of Text (line 58)
  --> examples/secret_bad.vel, line 58
```

Nothing ran, nothing was logged, and no reviewer had to notice the
line. A list of secrets, a map of them, or a record with one secret
field carries it too, so the whole structure is refused at a sink — a
`Request` record holding the key cannot be printed either.

**And a program cannot look at the key either.** `key == ""` is a
`Secret of Bool`, not a `Bool`, and an `if` or `while` on one is
`E563`. That is the rule that makes the rest mean something: with
`length` and `code_at`, a plain `Bool` from `==` is not one bit, it is
a loop that reads the whole key out —

<!-- illustrative: a loop taken out of a program -->
```vel
while at < 3 {
    for c in alphabet {
        if code_at(key, at) == code_at(c, 0) {   // E563
            found = found + c
        }
    }
    at = at + 1
}
print("recovered: " + found)                     // the whole key
```

— so a rule that stopped `print(key)` and allowed that would be a
decoration, not a type. The line is drawn at the branch.

`declassify(value, "why")` is the only way out. It needs
`uses declassify` in the signature, a reason written in the call, and
the `declassify` grant at run time — and it is what the audit reports,
so a consumer can ask whether a program ever lets a secret out without
running it:

```console
$ velaris audit examples/secret.vel --json | jq .secrets
{
  "sources": ["env"],
  "declassifies": false,
  "declassifications": []
}
```

To look at a secret, a program says so — `declassify(key == "", "…")`
gives back a `Bool` you can branch on, at the cost of the effect, the
grant and a reason in the audit. That is the trade: not silence, a
statement.

What this does **not** do: it only sees values `env()` and
`read_file_secret()` produced, so a password read with `read_line`, or
handed in through `args()`, or fetched from a vault over `net`, is an
ordinary `Text` with no protection at all. And it is not
non-interference — a program still chooses how long to run and whether
to stop. [SPEC.md §3.1](SPEC.md) states the rules and
[THREAT_MODEL.md](THREAT_MODEL.md) states the limits.

## Related work

[TACIT](https://github.com/lampepfl/tacit) ("Securing Agents With
Tracked Capabilities", ACM CAIS '26;
[arXiv 2603.00991](https://arxiv.org/abs/2603.00991)) has agents write
Scala 3, whose capture checking tracks file, network and command
capabilities as values in the type system;
[CaMeL](https://arxiv.org/abs/2503.18813) has a model turn the user's
request into a restricted subset of Python and tags every value with its
provenance and permitted readers, checking a policy at each tool call;
[WASI](https://wasi.dev) gives a WebAssembly module only the resources
its host hands it. Velaris is a small language a model learns from a
card of about <!-- count:card-words -->4,600<!-- /count --> words, in which functions declare their effects, the runtime
enforces the operator's budget at each operation, and contracts are
checked by the Z3 theorem prover. From 6.0 it also tracks one kind of
data: `Secret of T`, which `env()` and `read_file_secret()` produce and
which cannot reach anything that emits, cannot be branched on, and
leaves only through `declassify` — an effect of its own. That is
narrower than what CaMeL and TACIT do: they tag every value with its
provenance and permitted readers, and TACIT follows capabilities
through polymorphism, where Velaris marks two builtins' results and
refuses generic code over them unless a signature says so.
Until 5.0 its command line also granted every effect when no budget was
given, where a WASI module given nothing reaches nothing; from 5.0 a
run with no budget gets `io` alone.
The capability
format is published separately, under CC0, as
[velaris-spec](https://github.com/gowrishankar-infra/velaris-spec),
whose [PRIOR_ART.md](https://github.com/gowrishankar-infra/velaris-spec/blob/main/PRIOR_ART.md)
sets out these differences and the older work in full. From 4.1 it
holds a conformance corpus an implementation in any language can run -
<!-- count:conformance-cases -->456<!-- /count --> JSON cases at three levels, declaration, enforcement and the
ratchet, none needing a prover - written from this repository's suites
and held to them by a drift test; `velaris conformance` runs it against
this implementation, and CI does so on every leg.

## Why Velaris

| Guarantee | What it means |
|---|---|
| **Effects are visible** | `uses io, net, fs, ffi` — a function without `uses net` can never touch the network, transitively, and one without `uses ffi` can never call out to Python. Hidden behavior does not compile. |
| **Promises are proven** | `requires` / `ensures` / loop `invariant`, verified by Z3 with modular call summaries — including records, maps, nested lists, quantified list properties, failure paths, and floats in **genuine IEEE-754** (the prover refutes `x + 0.1 + 0.1 == x + 0.2` with the exact double that breaks it). |
| **Failure is unignorable** | `-> Int or fail` in the signature; callers must `check` or `try`. Forgetting the error path is a compile error — builtins included. |
| **Secrets cannot be printed, or looked at** | `Secret of T` — what `env()` and `read_file_secret()` return. Nothing that emits or can fail will take one, a structure holding one carries it, every operation over one keeps it (a comparison included), and no `if` branches on one. `declassify(value, "why")` is the only way out: an effect of its own, with its reason named in the audit. [SPEC.md §3.1](SPEC.md) says what it still does not claim. |
| **Fast where it's safe** | Pure functions over numbers, list reads, and text — including text built inside them — JIT to native code via LLVM (~10,000× on hot arithmetic, ~45× on text building), differential-tested against the interpreter. Native reads are bounds-guarded and text is built in a runtime-owned buffer, so results always match interpreted. |

Why floats are proven in IEEE-754 rather than as real numbers, and what
that costs: [docs/floats.md](docs/floats.md).

Loops without written invariants are handled where the boring
invariants suffice: the compiler proposes bounds on each counter and
keeps the ones a loop step cannot break (see `examples/inferred.vel`).
Anything richer — membership, sortedness — still needs an `invariant`
line.

The prover **never** claims "proven without running" unless the
counterexample is premise-complete — untranslatable assumptions abandon
the proof to runtime checks rather than risk a false alarm. Soundness
reports are treated as [security issues](SECURITY.md).

## Install

<!-- illustrative lines 1: installs from PyPI -->
```sh
pip install velaris-lang
velaris doctor
velaris new hello && cd hello && velaris main.vel
```

**Standalone executable** (no Python required) — download for
Windows / Linux / macOS from the
[latest release](https://github.com/gowrishankar-infra/velaris-lang/releases),
then:

```sh
velaris doctor
```

**With Python 3.10+:**

<!-- illustrative lines 1: installs from PyPI -->
```sh
pip install velaris-lang
velaris new hello && cd hello && velaris main.vel
```

**Zero install** — the
[playground](https://velaris-lang.dev/playground.html)
runs the real compiler in your browser.

Optional extras for source installs: `pip install ".[full]"` adds
`z3-solver` (compile-time proofs) and `llvmlite` (native speed);
without them, promises are checked at runtime and everything runs
interpreted — same language, honestly degraded. With `llvmlite`
installed, native code is the default: a pure function the compiler
can compile runs as machine code unless `--no-native` forces the
interpreter. There is no `--native` flag.

## Everyday ergonomics

<!-- illustrative: calls taken out of programs -->
```vel
keep_if(xs, fn(n: Int) -> Bool { return n % 2 == 0 })   // inline functions
format("hi {}, {} left", name, count)                    // text with holes
args()                                                   // command line
post(url, body) / fetch_status(url)                      // not just GET
```

Function values are lifted to real functions, so proofs and native
compilation apply to them unchanged — and they can carry their own
`requires` / `ensures`, proven like any other function's. A function
value takes a copy of the locals around it when it is made
([SPEC.md §12a](SPEC.md)); a promise on one that does is checked while
it runs.

## Where it plugs in

<!-- illustrative: a list of the ways in, not commands to run -->
```text
velaris script.vel                    the command (io unless you say more)
velaris script.vel --receipt r.json   and a signable record of what that run did
velaris eject script.vel              a directory that runs with nothing from here
import velaris                        a Python library
velaris mcp-install                   tools inside your assistant
velaris.mcpb                          double-click install for Claude Desktop
uses: gowrishankar-infra/velaris-lang a GitHub Action, findings in the Security tab
velaris capabilities check            CI fails when the capability surface widens
velaris serve                         an HTTP door for any language, token required
npx velaris-lang script.vel           npm, for the JavaScript world
%%velaris --audit --allow io          a Jupyter cell
- repo: velaris-lang (pre-commit)     a commit hook
docker run ... velaris check          a container
velaris build --for-everyone          standalone executables
```

## Use it from your own program

```python
import velaris

report = velaris.audit(source)      # what it touches, what's proven
run = velaris.run(source, allow={"io"})   # it cannot touch anything else
print(run.output, run.refused_effect)
```

The budget is enforced the same way it is on the command line. There is
an MCP server too, so an assistant can write, audit and sandbox-run
Velaris without leaving the conversation — see
[EMBEDDING.md](EMBEDDING.md) and the versioned `velaris.audit/1` format.

Calling `run` with a timeout or a memory cap starts a fresh interpreter
every time. A pool keeps workers alive under one fixed budget:

```python
pool = velaris.Pool(size=4, allow={"io"}, timeout=30, max_memory_mb=512)
result = pool.run(source)             # the same RunResult run() returns
pool.close()
```

200 sequential bounded runs of a small program: 46.6 s a process at a
time, 0.5 s on a pool. `pool.run` takes no `allow` — the budget belongs
to the pool, a worker is killed and replaced unless the run finished
cleanly, and a reused worker has every piece of mutable state reset
first. `check_pool.py` asserts each of those, including a program that
widens its own budget through `ffi` and cannot widen it for the next
one. The rules are stated in full in [EMBEDDING.md](EMBEDDING.md).

## A platform whose customers write the rules

[`examples/platform/`](examples/platform/) is that pattern as a small
FastAPI service, in one file. A customer submits Velaris source; the
service audits it, stores it with its capability surface, and answers
with what it declares — effects, hosts, paths, modules, the proven
share, its contracts function by function, and the narrowest budget that
would run it. It does not run it. A surface wider than the platform
permits is refused there, naming the grants that would have to be added.
Running happens on a `velaris.Pool` whose budget is the platform's.

Submit [`examples/discount.vel`](examples/discount.vel) and the answer
says `"proven_share": 100.0` with `"status": "proven"` on every promise,
including the two that matter to whoever is taking the payment: the
discount is never a surcharge, and what is left is never negative. That
is the sentence a platform can show a customer before offering to enable
a rule, and it is not one a sandbox can produce.

## Written by a model, audited by you, run in a box

```sh
velaris card > card.md          # ~4,600 words: paste into any model
velaris audit script.vel        # what it can touch, before you run it
velaris attest script.vel --output script.intoto.json   # the same, bound to its bytes
velaris script.vel              # io, and nothing else, unless you say more
```

`velaris audit` is written for the reviewer: what the program reaches,
what it promises, how much of that is *proven* rather than checked
while running, what can fail, and the exact command to run it safely.
`velaris attest` (4.2) puts that audit in an in-toto Statement whose
subjects are the program's files by sha256, ready to sign with cosign
or sigstore-python; [EMBEDDING.md](EMBEDDING.md) shows both, and every
release carries one, signed, for an example program.
`agent_loop.py` closes the circle — a model writes it, `velaris check
--json` hands back errors with fixes, and it iterates until the program
compiles and its promises prove.

From 8.3, the rest of a run's life: `velaris eval` runs a program as an
evaluation harness does, under a profile its command line cannot relax (no
net, ffi or env, time and memory limits, a stop honoured, the worker
confined where the operating system offers it, and a receipt always -
[docs/eval.md](docs/eval.md)); `velaris receipts diff` names what a run did
that its audit, or its earlier runs, did not; `velaris replay` makes a run
again from its receipt on the same bytes, or refuses; `velaris test
--from-contracts` runs each promise on the inputs the prover finds its
`requires` allows; and `velaris verify` holds an attestation or a receipt to
its type and its bytes. [docs/structurally-impossible.md](docs/structurally-impossible.md)
lists what cannot occur in a Velaris program, each with a test, and
[docs/crosswalk.md](docs/crosswalk.md) maps each guarantee and each known
gap onto the OWASP, AIUC-1 and NIST frameworks.

## Running code you did not write

```sh
velaris agent_output.vel                 # io: it may print, nothing else
velaris agent_output.vel --allow io,fs:read:./data   # and read that folder
velaris agent_output.vel --allow all --deny net,ffi  # everything but these
```

The runtime refuses any effect outside the budget you grant, whatever
the source claims — and a refusal cannot be caught and carried past.
From 8.4 the operating system is asked to hold the same budget, so a fault
in Velaris itself is refused by the kernel: Landlock and seccomp on Linux
(full), a sandbox profile on macOS and a job object with a lowered token on
Windows (both partial). `velaris doctor` says what your machine offers, a
receipt says what a run got, and `--no-confine` turns it off
([docs/confinement.md](docs/confinement.md)).
Not a security boundary (`ffi` grants everything Python can do, and widens
what the system is asked to hold), but a real guard for running a program
you have not read.

## Checking everything at once

<!-- illustrative lines 1-2,5-11: stress.vel reaches the network, and each suite runs on its own in CI -->
```sh
velaris examples/stress.vel --allow clock,env,ffi:datetime,math,sqlite3,io,net:raw.githubusercontent.com
                                # 33 checks across the whole language
velaris examples/edges.vel --allow ffi:datetime,io
                                # 20 boundary, property and round-trip checks
python check_refusals.py        # 25 wrong programs, each refused correctly
python check_sandbox.py         # 39 escape attempts, each refused with its code
python check_confine.py         # the operating system holds the budget too (8.4)
python check_secret.py          # a Secret reaches nothing that emits it
python check_pool.py            # a pool must leak nothing between programs
python check_platform.py        # the reference platform refuses what it says it does
python check_ratchet.py         # every widening fails, nothing else does
velaris conformance             # velaris-spec's 456-case corpus, L1 to L3
```

One command that exercises the language, the standard library, the
prover, native compilation, JSON, dates, CSV, the host language and the
network.

## Measured against other tools

<!-- count:benchmark-programs -->76<!-- /count --> small programs — <!-- count:benchmark-dangerous -->66<!-- /count --> with one deliberate defect,
<!-- count:benchmark-controls -->10<!-- /count --> correct controls —
each written three times with the same behaviour, in Velaris, in
JavaScript for Deno, and in Python. One harness runs every program
through every tool and records what was caught before running, what was
caught while running, and what was missed. The twelfth category (7.1)
is indirect authority: the calling code is the same before and after,
and only a dependency's declared budget widened between two versions.

<!-- generated:benchmark-table -->

| | caught before running | caught while running | missed | false positives on the 10 controls |
|---|---|---|---|---|
| **Velaris 8.4** | 52 | 12 | 2 | 0 |
| Deno 2.9 | 8 | 34 | 24 | 0 |
| Python 3.13 | 0 | 31 | 35 | 0 |

<!-- /generated -->

The <!-- count:benchmark-velaris-missed:word -->two<!-- /count --> Velaris misses are in the table by design: a loop that stops
one item early with no contract to contradict, and a program that
prints `rm -rf build` for its caller and touches nothing. Both are
named, with the reason each is not catchable, in
[benchmark/RESULTS.md](benchmark/RESULTS.md) — regenerated by one
command, `python benchmark/run.py`, which also lists the rows the
prover settles only while running.

## Programs worth running

`examples/ledger.vel` — an expense tracker: records, integer cents,
file persistence, sorted reports.
`examples/wordcount.vel` — text analysis:
`velaris examples/wordcount.vel --allow fs:read,io <file> [n]` counts
word frequencies and prints a ranked histogram.
`examples/linkcheck.vel` — a link checker you would actually run:
`velaris examples/linkcheck.vel --allow io,net <url> ...`, non-zero exit
when something is broken.
`examples/fetcher.vel` — an HTTP tool: checks a status, then summarises
a page, with every network call declared and every failure handled.

## JSON

<!-- illustrative: calls taken out of programs -->
```vel
json_get(doc, "user.name")    json_int(doc, "user.age")
json_len(doc, "tags")         json_of(Person(name: "gowri", age: 30))
```

Paths walk objects and lists, every read can fail (a missing field is
a possibility, not a crash), and none of it is an effect — parsing text
is pure.

## Reaching other languages

```vel
fn today() -> Text uses ffi or fail {
    let nothing: List of Text = []
    return try py("datetime.date", "today", nothing)
}
```

`py` / `py_int` / `py_float` / `py_json` call Python functions, and
`py_new` / `py_do` / `py_field` / `py_close` hold real objects — a
database connection, a session — so every library Python has is
reachable — but only from a function that declares `uses ffi`, and it
can fail like anything else that leaves your program.

## The standard library reaches outside

<!-- illustrative: a sketch; `...` stands for the program's own code -->
```vel
import "http.vel" as http     import "db.vel" as db
import "time.vel" as time     import "env_tools.vel" as sys

check http.get(url) { ok body { ... } fail why { ... } }
check db.count(conn, "notes") { ok n { ... } fail why { ... } }
```

Written in Velaris, so they carry their effects — a program using
`http` shows `net`, one using `db` shows `ffi`, and a pure function
can call neither.

## Libraries

<!-- illustrative lines 1: fetches a library over the network -->
```sh
velaris add https://example.com/geo.vel as geo   # vendored into lib/
velaris deps                                     # what you depend on
velaris deps --verify                            # unchanged since?
```

A library is compiled before it is accepted and kept in your
repository where you can read it. No registry, no resolver, nothing
fetched at build time.

`velaris add` writes `velaris.lock` beside `velaris.toml`: every
vendored library with its source, the sha256 of the exact bytes that
arrived, and the version of Velaris that added it. `velaris deps
--verify` fails if a file's hash differs from the lock or a locked
library is not on disk — a line worth having in CI. Adding a library
that is already vendored, with different bytes, is refused with both
digests printed; `--force` replaces it.

## Imports

<!-- illustrative: import lines taken out of a program -->
```vel
import "lib/geo.vel" as geo      // named: geo.distance(a, b)
import "std.vel"                 // flat: sort(xs)
```

A named import prefixes that library's functions, so two libraries that
both export `distance` can be used in the same file. A program sent to the
HTTP door or the MCP server imports only `.vel` files inside the directory
the door serves, and the library does the same given `import_root=`; any
other import is refused (E515) before the file is read (8.1).

## Shipping a program

<!-- illustrative: builds with PyInstaller, which takes minutes -->
```sh
velaris build myprogram.vel      # one executable, ~90 MB
./myprogram alpha beta           # runs anywhere, nothing installed;
                                 # it takes --allow like the compiler

velaris build myprogram.vel --for-everyone   # a workflow that builds
                                             # Windows, Linux and macOS
```

Your program, its imports, the standard library and the compiler, in
one file. It is compiled and proof-checked before it is built.

```sh
velaris eject myprogram.vel      # a directory that runs with nothing
python -I myprogram-ejected/main.py   # installed from this project
```

`velaris eject` (8.1) writes the program, its imports and a copy of the
runtime into a directory whose `main.py` fixes the budget, checks every
file's digest and refuses a budget that could let one run rewrite the next,
with a pinned `requirements.txt`, the PyInstaller command, and a README
saying what holds once ejected - the budget - and what does not: the
proofs are a record of eject time, and no later fix reaches it.

## Tooling

`velaris trace program.vel` (watch every call as it happens) ·
`velaris test program.vel` (runs every `test_*` function written in
Velaris) ·
`velaris check program.vel` (compile without running; several files at
once, `--json` for tools) ·
`velaris explain program.vel` (a walkthrough of every function: effects,
promises, and whether they are proven — `explain <folder>` maps a whole
project) ·
`velaris repl` (definitions are proof-checked as you type them) ·
`velaris fmt` (canonical style, `--check` for CI) · `velaris lsp`
(errors as you type in any LSP editor; a VS Code extension lives in
[`editor/vscode`](editor/vscode)) ·
`velaris doctor` · `velaris new` · `--json` errors for automation.

## Standard library

Written in Velaris, in [`stdlib/std.vel`](stdlib/std.vel) — and it
keeps its own promises: `sort` carries `ensures is_sorted(result)`,
`max_of` requires a nonempty list, and violating a library `requires`
is a compile error at *your* call site. Full
[reference](https://velaris-lang.dev/library.html),
generated from the real compiler.

## Numbers

Whole numbers are 64-bit. Arithmetic that outgrows that range is an
error, not a silent wrap — and the same error whether your code is
interpreted or running as machine code. Floats are IEEE-754 doubles,
proven as such.

**Money is neither.** `money(1250, "INR")` is 12.50 rupees held as 1250
paise: an exact whole number of minor units, with the currency in its
type, so INR meeting USD is a compile error and no `Float` goes near it.
Dividing an amount says how it rounds — `percent_of(claim, 25, 1000,
"half_up")` — or it does not compile, and `money.split(payout, 3)`
gives parts that **provably** add up to the payout. See
[`examples/settlement.vel`](examples/settlement.vel) and
[SPEC.md §4.3](SPEC.md).

## The reference

[SPEC.md](SPEC.md) states precisely what the language means: semantics,
evaluation order, effect propagation, what "proven" covers today, and
what Velaris deliberately does not have — including
[why it has no concurrency model](SPEC.md#13-concurrency).

## Stability

Semantic versioning: breaking changes **only at major versions**.
[STABILITY.md](STABILITY.md) says what that covers - the language, the
error codes, `velaris.audit/1`, the library API, the budget grammar and
the command line - what it does not, the rules for deprecating and
removing, and every time this project has broken the rule, 3.3 and 3.4
among them. CI tests every push on Linux, Windows and macOS, Python
3.10 and 3.12, with and without the optional dependencies. Errors are
stable, numbered, and
[fully documented](https://velaris-lang.dev/errors.html).

## How much is proven

```sh
velaris proofs .            # how many promises are proven, file by file
velaris proofs . --min 80   # fails the build below 80%
```

Over this repository's examples and standard library, `velaris proofs
examples stdlib` proves the promises of <!-- count:proven -->70<!-- /count --> of the
<!-- count:promised -->99<!-- /count --> functions that make one before they run, a proven share of
<!-- count:proven-share -->70.7<!-- /count -->%; the others are checked while they run. Some of those
examples are built to be refused, and their promises are false on purpose.

## Using Velaris in CI

The GitHub Action audits the **Velaris programs** in a repository - its
`.vel` files - and reports what they may touch to GitHub code scanning.
It does not read Python, JavaScript, Go or anything else: a repository
with no `.vel` file prints `no .vel files found` and the job is green.
The case it serves is narrow, and it is the one this language exists
for - an agent wrote a script, the script is in Velaris, and the
effects it declared and the promises it did not prove should land in
the Security tab rather than in a reviewer's head.

Copy this into `.github/workflows/velaris.yml`:

```yaml
name: velaris
on: [push, pull_request]

permissions:
  contents: read
  security-events: write     # so the findings reach code scanning

jobs:
  velaris:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: gowrishankar-infra/velaris-lang@d457f50acba198b4a712db71788780de0903df65  # v8.3.1
```

The Action is pinned to a commit, with its tag in the comment beside it:
a tag can be moved to other code after you copied it, and a commit cannot.
Pinned that way it installs the Velaris of that commit, as it does at a
tag.

That is the whole workflow. With no `with:` block the Action installs
Velaris and the prover, checks every `.vel` file in the repository,
fails the job if one does not compile or carries a promise the prover
refutes, and uploads its findings as SARIF 2.1.0 with
`github/codeql-action/upload-sarif`, pinned to a commit. A private
repository needs code scanning enabled; set `sarif: "false"` if it has
neither that nor `security-events: write`. On a pull request from a
fork the job's token cannot upload, so that step is skipped - the file
is still written, and its path is the `sarif-file` output. The findings
print to the job log either way.

### What appears in the Security tab

One alert per finding, on the line that caused it, with a link to its
row on the
[errors page](https://velaris-lang.dev/errors.html).
These are the rule IDs, and a real message from each:

| rule | level | what an alert says |
|---|---|---|
| `E300` | error | `function 'fetch' calls 'read_file' which needs effect 'fs', but 'fetch' declares no effects (it is pure)` |
| `E520` | error | `'to_int' can fail - that cannot be ignored` |
| `E700` | error | `promise cannot be kept: 'discount' ensures result >= 0 - proven without running the program: price = 9 gives result = -1` |
| `E701` | error | `this call can break a promise: 'discount' requires price >= 0, but 'main' can call it with price = -3 - proven without running the program` |
| `unproven-promise` | warning | `'count_rows': ensures result >= 0 - not proven before running; checked while the program runs` |
| `contract-coverage` | note | `'total' takes or returns data and promises nothing about it` |
| `capability-widened` | error | `net is needed by sync.vel, not in the surface of velaris.capabilities (a new effect, net)` |
| `capability-effect-gained` | error | `'main' now declares net, which it did not in velaris.capabilities: net: calls pull at line 6, which declares net` |
| `capability-narrowed` | note | `surface: "net" is no longer needed` - the baseline gives more than the code needs; `capabilities init --force` records the narrower surface |
| `dependency-capability-widened` | error | `npm:mixed 0.1.0 -> 0.2.0: net:telemetry.example.net is needed by lib/report.vel (a new effect, net)` |
| `dependency-effect-gained` | error | `npm:mixed 0.1.0 -> 0.2.0: 'render' now declares net: net: calls post at line 3` |
| `dependency-install-script` | error | `npm:textkit 1.0.0 -> 1.1.0: an install-time script was added: npm postinstall: node setup.js [registry manifest, tarball package.json]; what it does is not derived` |
| `dependency-surface-unknown` | note | `npm:textkit 1.0.0 -> 1.1.0: capability surface unknown. Neither 1.0.0 nor 1.1.0 holds a .vel file, so there is no declared capability surface to compare. ...` |
| `dependency-added` | note | `npm:textkit 1.0.0 -> 1.1.0: now declares helper ^2.0.0 (dependencies); its own surface was not examined` |
| `dependency-narrowed` | note | `velaris.lock:mailer 6ed598a1e2bf -> 3f7a9875d0de: surface: "net:collector.example.net" is no longer needed` |

Every code in the compiler's error table is a rule of its own, so a
parse error (`E1xx`), an unknown function (`E200`) or a type error
(`E5xx`) arrives the same way; `E3xx` are the effect codes and `E7xx`
the prover's. Under `check --strict` an unproven promise is an `error`
rather than a warning, and a loop not shown to end is `E612`. The
`uses-io`, `uses-fs` and `loop-not-shown-to-end` notes come from
`velaris audit --sarif`, which the Action does not run; `pr-comment`
below is where the Action reports those. The `dependency-*` rows come
from `deps-diff`, below, and only when that input is on; each lands on
the line of the lockfile that pins the upgraded version.

Velaris's suggested fixes are sentences, while a SARIF `fix` must hold
the exact bytes to change, so they travel in each result's
`properties.fixes` rather than as SARIF fixes with an edit made up to
fill the slot.

### The budget a repository declares

`velaris capabilities init` records the capability surface a
repository's `.vel` files need - effects, paths, hosts, Python modules,
how many file and network operations a run can perform, and each
function's effects - in `velaris.capabilities`; commit it. From then on
the Action runs `velaris capabilities check` on every push and fails
any change that needs more, naming what widened, the file, function and
line that introduced it, and the edit to the baseline that would accept
it. Those are the `capability-*` rows above, and they go to code
scanning beside the check's.

The comparison is always with that file, never with the previous
commit: capability added across many small commits, none alarming by
itself, fails at every one of them until someone widens the file, where
the change shows in review. A pull request that deletes
`velaris.capabilities` fails too, since that would turn the ratchet
off; `capabilities: "off"` in the workflow is the way to turn it off,
where the change is visible. Without the file the ratchet is simply
off. [EMBEDDING.md](EMBEDDING.md) has the rules; `check_ratchet.py`
holds them, including a six-commit history that fails only at the
commit that reaches the network.

### What an upgrade gained

A dependency can change what it can do between two versions while its
name, its publisher and its list of dependencies stay the same. The
npm package postmark-mcp is a documented case: Koi Security reported
in September 2025 that versions 1.0.0 to 1.0.15 worked as an email
tool, and that 1.0.16 added a blind copy of every outgoing message to
an outside address. A signature from the same publisher verifies both
versions; an SBOM lists the same dependencies for both.

`velaris deps-diff` compares two versions of one dependency:

<!-- illustrative lines 2-5: they read git, npm and PyPI, or need a git remote -->
<!-- expect lines 1: exit 1, since 1.5.0 gained something -->
```sh
velaris deps-diff dir:vendor/mailer 1.4.0 1.5.0          # a directory per version
velaris deps-diff git:https://github.com/o/mailer v1.4.0 v1.5.0
velaris deps-diff npm:some-package 1.0.15 1.0.16
velaris deps-diff pypi:some-package 2.31.0 2.32.0 --json
velaris deps-diff --against origin/main                  # every upgrade in the changed lockfiles
```

For a **Velaris library** it computes each version's capability surface
from its `.vel` files, as `capabilities init` would, holds the newer
one to the older one as `capabilities check` holds a tree to its
baseline, and reports what the newer one gained - effects, hosts,
paths, Python modules, operation counts, and functions that declare an
effect they did not - with the file, line and call of each:

<!-- output -->
```text
GAINED  net:collector.example.net - not in 1.4.0's surface
    in mailer.vel
      mailer.vel:3  send calls post("https://collector.example.net/copy")
GAINED  net operations in mailer.vel: at most 2 in a run; 1.4.0 had at most 1
```

A caller that already declared `net` for its own request compiles
against both versions, so the compiler has nothing to refuse; the
difference is in what the dependency declares, and that is what this
reads. The benchmark's category 12 is <!-- count:category-12-dangerous:word -->three<!-- /count --> programs of that shape and
<!-- count:category-12-controls:word -->one<!-- /count --> control.

For **any other package** it reads what the registry and the package's
archive declare, and nothing more: the install-time scripts npm or pip
runs (`preinstall`, `install`, `postinstall`, npm's `node-gyp rebuild`,
`setup.py`, the build backend, a `.pth` file that imports) and whether
each was added or changed - including a changed file behind an
unchanged command, and, when a registry's manifest and the tarball's
`package.json` disagree, the scripts of both, since which one npm runs
has changed between npm versions - and the declared dependencies. It
does not derive what Python or JavaScript code can do, and does not
guess: it reports the capability surface as **unknown**, and exits 3
rather than 0. That
answer is often all there is. By Koi Security's account 1.0.16 of
postmark-mcp changed nothing but the code that added the copy, so
`deps-diff` would have found no install script and no dependency to
report, and would have said the surface is unknown. (npm has since
unpublished every version of that package; today `deps-diff` reports
that neither version can be read.)

Exit codes: 0 when both surfaces were derived and nothing was gained; 1
when something was gained; 3 when nothing visible was gained and the
surface was not derived; 2 when a version could not be read. `--json`
is `velaris.deps-diff/1`; `--sarif` writes the `dependency-*` results
above. A package argument names where to read it - `pypi:`, `npm:`,
`git:` or `dir:` - and a bare name is refused, so an npm package is
never compared with a PyPI package of the same name.
`VELARIS_NPM_REGISTRY` and `VELARIS_PYPI_URL` point it at a mirror.

With `deps-diff: "true"`, on a pull request the Action runs
`velaris deps-diff --against` the base: it reads the lockfiles the pull
request changed - `package-lock.json`, `npm-shrinkwrap.json`,
`requirements*.txt` pins, `Pipfile.lock`, `poetry.lock`, `uv.lock`,
`pdm.lock` and `velaris.lock`, whose vendored libraries it compares
file against file - compares every upgraded dependency, up to <!-- count:deps-max-upgrades -->30<!-- /count -->, and
posts one comment saying what each gained, editing that comment on
later runs rather than adding another. A lockfile it does not read
(`yarn.lock`, `pnpm-lock.yaml`, and others) is named in the comment as
changed and not read. An entry resolved from git, a path, or a registry
or index other than the one it reads is left out and said, because the
public package of the same name would be a different package; so is
every pin of a `requirements*.txt` that sets another index. The
findings go to code scanning when `sarif` is on. It needs
`pull-requests: write`, and it never fails the job.

### The permissions a pull request gives its workflows

With `permissions-ratchet: "true"` (8.3), on a `pull_request` event the
Action runs `velaris permissions-ratchet --against` the pull request's base
commit. It compares the `permissions:` blocks of every workflow file in
`.github/workflows` at the head with the base, job by job, and fails the job
on any widening, with an error on the file and line. A widening is a scope
whose level rises (none < read < write); a job left with no block, its own or
the workflow's, so that it takes the repository's default token permissions;
or a new job or workflow file that gives any permission. A narrowing is
reported and does not fail. A job renamed is a job removed plus a new job,
and the new job is compared with no permissions. The input is off by default.
It is the one input that helps a repository with no `.vel` file, and it runs
whether or not there is one. A workflow it cannot read with confidence - an
anchor, a tab, a key written twice, a second document - fails the step rather
than being taken as having no permissions; so does a base commit it cannot
fetch. It compares files, not what GitHub runs, so it does not see the
permissions of a reusable workflow a job calls, which that workflow's own
block governs; the repository's default token setting; or the base branch's
copy of a `pull_request_target` workflow, which is what runs. `--json` writes
`velaris.permissions-ratchet/1`, which is provisional.

### Everything else the Action takes

```yaml
  - uses: gowrishankar-infra/velaris-lang@d457f50acba198b4a712db71788780de0903df65  # v8.3.1
    with:
      files: "src/*.vel"     # default: every .vel file in the repository
      version: "8.3.1"       # default: the Action's own version (8.3.1)
      proofs: "true"         # the default; installs z3-solver
      format: "true"         # also fail if the code is not canonically formatted
      min-proven: "80"       # fail below this percent of promises proven
      pr-comment: "true"     # audit every changed .vel on the pull request
      sarif: "true"          # the default; findings to code scanning
      capabilities: "check"  # the default once velaris.capabilities exists
      deps-diff: "true"      # comment on what each upgraded dependency gained
```

With `pr-comment: "true"` on a `pull_request` event the Action posts one
comment holding the `velaris audit` of every `.vel` file the pull
request changes - effects and Python modules reached, proven share, the
safe command, and warnings such as a loop not shown to end - and edits
that same comment on later runs instead of adding another. The comment
also carries the ratchet's result and a `velaris review` of the branch
against its base: surface, proven share, new fallible functions, new
hosts and paths, and a one-word risk computed from those facts alone.
It uses the REST API with the job's own `GITHUB_TOKEN`, so the job needs
`permissions: pull-requests: write`. The audit is posted whether or not
the checks passed; a file that does not compile is reported as such.

The same SARIF without the Action, for SonarQube
(`sonar.sarifReportPaths`), Azure DevOps or anything else that reads it:

```sh
velaris check src/*.vel --sarif > velaris.sarif   # exit 1 as the plain check
velaris proofs src --sarif > proofs.sarif         # promises left to runtime
velaris audit src --sarif > audit.sarif           # what each function may touch
velaris capabilities check --sarif > caps.sarif   # what widened past the baseline
```

One run, driver `Velaris` with its version, and a rule for every code in
the error table plus the findings that are not errors. Each result has
the file, the line and Velaris's message.

Or without installing anything:

<!-- illustrative: needs Docker and a velaris image -->
```sh
docker run --rm -v "$PWD:/work" velaris check /work/main.vel
```

What a reviewer should read before allowing agent-written Velaris to
run: [THREAT_MODEL.md](THREAT_MODEL.md), [COMPLIANCE.md](COMPLIANCE.md)
and the verification steps in [SECURITY.md](SECURITY.md).

## Project

[Roadmap](ROADMAP.md) · [Support and expectations](SUPPORT.md) ·
[How the compiler works](ARCHITECTURE.md) · [Maintainers](MAINTAINERS.md) ·
[Security policy](SECURITY.md) · [Stability](STABILITY.md) ·
[Changelog](CHANGELOG.md)

Maintained by one person, in the open, with the limits stated plainly
in [SUPPORT.md](SUPPORT.md).

## Cite this repository

The author is Palakurthi Gowri Shankar (family name Palakurthi).
[CITATION.cff](CITATION.cff) holds the citation, and GitHub offers it as
"Cite this repository" beside the file list. A preprint describing
Velaris is forthcoming; until it is published, cite the repository. The
capability format is cited separately, from
[velaris-spec](https://github.com/gowrishankar-infra/velaris-spec)'s own
CITATION.cff. [PROVENANCE.md](PROVENANCE.md) records the dates and the
archive identifiers.

## Contributing

The implementation is the package [`velaris/`](velaris), one readable
module per stage, in pipeline order — lexer to command line; `velaris.py`
starts it. Start with
[ARCHITECTURE.md](ARCHITECTURE.md) for how it fits together, and
[MAINTAINERS.md](MAINTAINERS.md) for what review looks like.

**Looking for somewhere to start?** See the
[good first issues](https://github.com/gowrishankar-infra/velaris-lang/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
— small, self-contained tasks, each with the file to open and what
"done" means.

The <!-- count:examples -->97<!-- /count --> example programs `run_tests.py` runs, in [`examples/`](examples), each
carry an expected verdict, and <!-- count:examples-rejected -->36<!-- /count --> of them are *designed* to be rejected —
each rejection demonstrates a guarantee. Before any change ships:

<!-- illustrative lines 1,3: suites of their own, run by CI -->
```sh
python run_tests.py                 # every example, expected verdicts
velaris test examples/std_test.vel  # the library's own tests
python fuzz_native.py 60            # both engines must agree
velaris fmt examples/*.vel stdlib/*.vel --check
```

## License

[MIT](LICENSE) © Palakurthi Gowri Shankar
