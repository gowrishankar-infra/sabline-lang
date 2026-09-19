# Stability

What this project will not change without a major version, what it
does not promise to keep, the rules for changing either, and the
record of the times it broke its own rule.

## What semantic versioning covers

A change to any of these is a breaking change, and ships only in a
major version.

- **The language**: its syntax and semantics as [SPEC.md](SPEC.md)
  states them. A program that compiles and runs under 7.x compiles,
  runs and means the same under every later 7.x, with the one
  exception under *The prover's reach* below. What a run is *allowed*
  to do is the operator's budget, not the language, and the budget a
  run gets when nobody writes one changed in 5.0 - see *Breaks we have
  made*.
- **The error codes** in `velaris.ERROR_TABLE`, and what each means.
  The [errors page](https://velaris-lang.dev/errors.html)
  is built from that table.
- **`velaris.audit/1`**: the fields and their meanings, as
  [EMBEDDING.md](EMBEDDING.md) and
  [velaris-spec](https://github.com/gowrishankar-infra/velaris-spec)
  section 8 state them. Within version 1 fields may be added; none
  changes meaning or disappears without the `schema` value changing.
  The other versioned documents Velaris writes follow the same rule
  within their version: `velaris.capabilities/1`,
  `velaris.capabilities-check/1`, `velaris.review/1`,
  `velaris.invocation/1`, `velaris.mcp-tools/1`, from 4.1
  `velaris.conformance/1`, and from 8.1 `velaris.receipt/1` and the receipt
  Statement that carries it (velaris-spec section 8.7).
- **The library API**: `velaris.check`, `velaris.audit`, `velaris.run`,
  `velaris.Pool` (with `Pool.check` and `Pool.audit` from 8.1),
  `velaris.card` and, from 4.2, `velaris.attest` - their
  names, their parameters, and the fields of what they return
  (`CheckResult`, `AuditResult`, `RunResult`, `Problem`, and the in-toto
  Statements `attest` returns, whose predicate velaris-spec section 8.5
  defines). A new optional parameter or a new field is an addition, not
  a break.
- **The budget grammar**: SPEC.md section 7.1, stated in full in
  velaris-spec sections 4 and 5. A budget that parses keeps parsing,
  and grants the same thing.
- **The command line**: the command names, the flags documented for
  them (`velaris` with no arguments prints them, and README and
  EMBEDDING.md describe them), and the exit codes those documents give.
  The budget a command line with no `--allow` installs is part of this,
  and 5.0 changed it.

## What it does not cover

- **Anything else in the `velaris` package** (`velaris.py` until 8.2):
  every function, class and
  module-level name not listed above, including those the doors and
  suites use (`Budget`, `InvocationLog`, `inspect_source`,
  `load_program`, ...). They may change in any release.
- **The wording of messages.** Codes are stable; prose is not. That
  covers error messages, their suggested fixes, an audit's `warnings`,
  and every command's text output - read `--json`, not the text.
- **Which promises happen to prove.** A new version may prove a promise
  an older one left to runtime, or leave to runtime one an older one
  proved.
- **The canonical style `velaris fmt` writes.** A change to it is named
  in the CHANGELOG, because `fmt --check` in CI will see it.
- **Anything marked provisional**, in SPEC.md or in velaris-spec. From
  7.1 that includes `velaris.deps-diff/1` and
  `velaris.deps-diff-lockfiles/1`, the JSON `velaris deps-diff` writes:
  their fields may change in a minor release, named in the CHANGELOG,
  until a release says they are covered. The command, its flags and its
  exit codes are covered like any other command's. From 8.3 the same holds
  for `velaris.eval/1`, `velaris.receipt-stream/1`,
  `velaris.receipts-diff/1`, `velaris.replay/1`, `velaris.responses/1`,
  `velaris.from-contracts/1`, `velaris.verify/1` and
  `velaris.permissions-ratchet/1`. `velaris.receipt/1` gains `stop` and
  `run_parameters.profile` within version 1 (velaris-spec section 8.7).

## The rules

1. **A breaking change ships only in a major version.** That includes a
   security fix that refuses something that used to work: if it breaks
   something covered above, it is a major version. Version numbers cost
   nothing, and a major version is how a user learns to read the
   CHANGELOG before upgrading.
2. **A deprecation is announced in a minor version**, warns when the
   deprecated thing is used for at least one minor version after that,
   and is removed no sooner than the next major version.
3. **An error code is never reused for a different meaning.** A code
   that is no longer given stays listed as removed (`REMOVED_ERRORS` in
   `velaris/errors.py`, and the errors page), with what it meant and the
   version that removed it.
4. **Every major version's CHANGELOG entry says what a user of the
   previous major has to change**, item by item.
5. **A minor or patch release that adds an error code, removes a flag or
   changes a default says why that is not a break** (8.2), in its
   CHANGELOG entry, on a line beginning `compatibility:`. A new code can
   be an addition - given only where a Python error used to escape - or a
   refusal of something that used to run, which is a break; the line is
   where the difference is argued, in writing, before the release. The
   release gate reads the compiler's source against the previous tag and
   refuses a minor or patch release that changes one of the three without
   the line - a line of prose that says something, not one in a code
   block or a comment, and not a placeholder (RELEASING.md). It cannot
   tell whether the argument is right; it makes sure one is made.

### Deprecations in force

| Deprecated | Since | What it does now | Removed in |
|---|---|---|---|
| `--no-cache` | 8.2 | nothing: Velaris keeps no proofs between runs. It is accepted wherever it was, and says once on stderr that it does nothing | 9.0 |
| `velaris clean` | 8.2 | nothing, exit 0, with the same notice | 9.0 |

**The prover's reach.** A prover that settles more is not a breaking
change, even when it refuses a program that compiled before: a promise
it now shows false (E700), a call it shows can break a `requires`
(E701), a list read it shows can pass the end (E705), a divisor it
shows can be zero (E706). Each such program could already fail while
running, with the matching runtime error, for the input the prover
names. This is the one way a program that compiled under 4.x can be
refused by a later 5.x, and the CHANGELOG names each release that does
it. 4.3 widened it once: a division whose divisor mentions a loop's
values is translated when the loop's condition and invariants show the
divisor positive. 4.3.1 widened it again, not by translating more but
by allowing more time: a float proof gets 120 seconds where it had
30, so a refutation a slower machine used to abandon now lands.

**A new builtin gives way to your own function.** A builtin added in
4.3 or later is not reached in a program that defines a function of the
same name (SPEC.md 10.1). Without that rule, adding a builtin would
break every program that had already used the name - `examples/ledger.vel`
has had a function called `money` since 1.13 - and adding one would be a
major version. The builtins that existed before 4.3 are unchanged: a
function named like one of those is still never reached.

## Breaks we have made

The README has promised semantic versioning since 2.2. 2.0, 3.0, 4.0,
5.0, 6.0, 7.0 and 8.0 broke things in major versions, as promised; the
rest below did not. None of them is being undone - the versions are published - and
this section exists so the record is whole and so the rules above are
applied from 4.0 on.

**2.0 (major).** `to_int`, `get` on a map, `read_file` and `fetch`
became fallible: a call to one of them not handled with `check` or
`try` was refused with E520, and the compiler pointed at each.

**3.0 (major).** `env` became its own effect. A program that called
`env()` under `uses io` alone was refused at compile time, and an
`io`-only budget no longer let a program read the environment.

**3.4 (minor) shipped three breaking changes it named, and three it
did not.** Named in its CHANGELOG, which said they shipped in a minor
version because each closed an open door: a client of `velaris serve`
had to send a bearer token; the MCP server granted `io` only unless
started with `--max-allow`; and the GitHub Action, with `sarif` on by
default, needed `permissions: security-events: write`. Not named:
`velaris serve` refused an argument it did not know, where it had
ignored it; the MCP server did the same; and `GET /health` stopped
naming the ceiling to a caller without the token. **3.4 should have
been 4.0**: closing an open door is a reason to release soon, not a
reason to call a break something else. It was not retagged, because
3.4.0 was already published to PyPI and GitHub, and moving a published
version breaks everyone who pinned it. This policy exists so that it
does not happen again.

**3.3 (minor) shipped five breaking changes as fixes, and named none as
breaking.** A `uses` clause naming anything but the seven effects was
refused (E300). The budget parser became strict: a count in non-ASCII
digits, `ffi:M@N`, `ffi:` with no module and an unbracketed IPv6
address were refused where they had parsed. `ffi,ffi:math` came to
grant every module, where it had granted `math` alone - the same budget
text granting more. A call through a granted module into a module that
was not granted was refused (E311) where it had run. `%` followed by
`2C`, `40`, `5B`, `5D` or `25` in a path or host began to be decoded.
And `velaris audit --json` changed shape to `velaris.audit/1`. Each was
a correct fix; together they were a major version.

**Earlier minor releases** that broke something covered above:

| Release | What broke |
|---|---|
| 2.20 | Whole numbers became 64-bit: arithmetic past that range stopped with E407, where the interpreter had kept counting |
| 2.42 | `velaris fmt` changed where it puts `requires`, `ensures` and `invariant`, so `fmt --check` failed on files the previous version had formatted |
| 2.44 | `pop`, `slice` and `set_at` had to be handled with `check` or `try` (E520); a missing `main`, a `main` with parameters and a `main` marked `or fail` became compile-time errors (E400, E401, E523); Python calls began to receive arguments that read as numbers as numbers |
| 2.47 | `http.vel`'s `call` returned an `Answer` record instead of text |
| 2.56 | `audit().problems` held `Problem` objects instead of dictionaries |
| 2.59 | The MCP server and the HTTP door stopped a run at 30 seconds and 512 MB, where it had had no limit |
| 2.62 | `args()` stopped including `--allow`, `--deny`, `--timeout` and their values; `check --strict` began refusing a loop not shown to end (E612) |
| 3.1 | The memory cap began to hold on Windows, so a run past it stopped with E611 where it had continued; `velaris add` refused to replace a vendored library with different bytes without `--force` |
| 8.2 | Each named on a `compatibility:` line of its entry, where rule 5 now requires it. On a run, `--` ends Velaris's flags, so `args()` no longer holds `--` and a flag written after it no longer applies (a Goal C fix); a local or parameter named like a builtin, or like one of the program's functions, no longer hides a call from the effect check (E300) or the Secret check (E560); unary minus of the smallest whole number, and that number divided by -1, stop with E407; blocks nested more than 4,000 deep are E102, where more than some thousands were a Python traceback; `velaris check` gives a `main` marked `or fail` E524, as a run always did, where it gave E523; `--no-cache` and `velaris clean` do nothing |

**Refusals from a stronger prover**, which the rule above does not
count as breaks, in 2.6, 2.9, 2.12, 2.18, 2.41.2, 2.43, 2.44 and 2.45:
each refused before running a program that had compiled, for a
division, a map promise, a nested-list read, a record promise, a call
against a `requires` the prover had been dropping, or a list read the
prover could now show wrong.

**A reused error code.** E610 meant a missing map key from 1.4; 2.0
made that lookup a failure instead, and 2.59 gave E610 to the run's
time limit. Rule 3 forbids that from 4.0 on. No code has been removed
since.

**4.0 (major).** Listed item by item in the CHANGELOG under "What a 3.4
user has to change": `velaris serve` without `--max-allow` grants `io`
only; on both doors a request's `timeout` and `max_memory_mb` may not
exceed the operator's `--max-timeout` and `--max-memory-mb`, 30 seconds
and 512 MB by default, and must be numbers; and `velaris serve
--max-memory-mb`, which on Linux and macOS capped the door's own
process, is now the most each run may have.

**5.0 (major), 2026-09-12.** A run given no budget gets `io` - the
console, and nothing else - where it got all seven effects.
`velaris file.vel`, `velaris.run(source)` with no `allow`, and
`velaris.Pool(...)` with no `allow` are all affected; the two doors
were already `io` (the MCP server in 3.4, the HTTP door in 4.0), and
this is the release that makes every place a budget comes from answer
the same way. `--deny` now narrows what `--allow` gave rather than
starting from all seven, so `--deny net` alone leaves `io` where it
left six effects. **The reason**: the one question a capability
language has to get right is what an operator gets when they say
nothing, and until 5.0 the answer was "everything". Every claim this
project makes about running code you have not read depended on the
operator having written a budget, and THREAT_MODEL.md, the README's
related-work paragraph and the paper all conceded the point against
WASI, whose modules reach nothing unless handed something. Prior art
made it plain: Boruna's default policy grants nothing.

A 4.x user has to change: every command, script, CI step, notebook
cell and library call that runs a program needing more than `io` and
did not say so. `velaris migrate --to 5.0 [path]` reads a program or a
tree, works out the narrowest budget each program needs from its own
audit, and prints the command to run it under 5.0; `--write` updates
the shell scripts and CI files it can parse and names the lines it
left alone. `--allow all` is the explicit way to ask for what a run
used to get, and writes one line to standard error when it is used.
The refusal a program now meets names the effect, what the run does
allow, and the flag that would grant it.

**6.0 (major), 2026-09-12.** `env()` returns `Secret of Text` where it
returned `Text`, and a `Secret` cannot be printed, written, sent or
passed to Python (E560). Three shapes of program stop compiling:
one that emits what `env()` returned; one whose signature says it
returns a `Text` and returns what `env()` gave it (E503); and one that
puts it in a `Text` variable, field or parameter (E501). `declassify`
is an eighth effect, so `--allow all` now grants eight, a `uses` clause
may name it, and `velaris.audit/1`'s `effects` may hold it - a change
to a list STABILITY.md's *budget grammar* clause covers.
`stdlib/env_tools.vel` changed with the language: `setting` returns
`Secret of Text`, `number_setting` declares `uses env, declassify`, and
`public_setting` is new. **The reason**: an effect says a program
printed something; it does not say whether what it printed was the
secret, and a language whose whole claim is about running code you
have not read had nothing at all to say about that. It was the one
capability the peer-reviewed design beside this one had and this did
not, and prior art said so in writing.

This one was written as 5.1 first. It is 6.0 because rule 1 says a
break ships in a major version - including a security fix that refuses
something that used to work - and because this file already records two
releases that got that wrong. A version number costs nothing.

A 5.x user has to change: every use of `env()`'s result as a `Text`,
which the compiler points at one by one; and a repository with a
committed `velaris.capabilities` has to record `declassify` the first
time one of its programs needs it, in review, which is the ratchet
working rather than a break.

**7.0 (major), 2026-09-12. 6.0.0 stood for one day.** 6.0 let a
comparison over a secret give an ordinary `Bool`, and said in writing
why: a comparison is one bit, `if key == ""` has to be writable, and
refusing the Bool while allowing the branch would stop nothing. That
is true of one comparison and false of a loop - with `length` and
`code_at`, `key == c` reads the key out a character at a time, and the
program prints what it read. A second route was found the same way: a
failure's reason is text the program can print and the runtime builds
it from the values it was given, so `to_int(key)` printed the key when
it failed. 7.0 makes a comparison over a secret a `Secret of Bool`,
refuses any `if` or `while` on a value that carries a secret (E563),
and refuses a secret to every fallible builtin (E560). Programs that
compiled under 6.0 are refused, so it is a major version by rule 1.

6.0.0 is yanked on PyPI, not deleted. It was published, tagged and
signed, and deleting or moving a published version breaks whoever
pinned it - the same reason 3.4 was not retagged. A yank does neither:
an install pinned to `==6.0.0` still resolves and gets the same file,
and an install that asks for anything looser no longer reaches it. That
is the distinction that lets a bad release stay honest without breaking
anyone who committed to it - it is still there, and listed here as what
it was: a release whose central feature had a hole, closed the same day
it was found. What the rule bought is that the fix arrived as 7.0
rather than as 6.0.1, so nobody upgrades into a refusal without reading
why.

**8.0 (major).** Four changes refuse programs that ran under 7.x, each
a security fix, each therefore a major by rule 1. Listed item by item in
the CHANGELOG under "What a user of 7.x has to change":

- **A proxy the net budget does not cover is refused (E317).** Through
  7.x a `net:` grant checked the URL's host, but an ambient `HTTP_PROXY`
  / `HTTPS_PROXY` routed the request to a proxy that need not be a
  granted host - the grant bounded a string, not the socket's peer. This
  was the open gap THREAT_MODEL.md recorded. 8.0 disables ambient
  proxies unless the proxy's own host:port is inside the net budget;
  `velaris add` no longer defers to a proxy either. With no proxy set,
  behaviour is unchanged.
- **A function named like a built-in is refused (E204).** `fn print`,
  `fn env`, `fn read_file` and the like were silently shadowed by the
  built-in through 7.x; now they are an error. The 4.3-and-later
  give-way rule (SPEC.md 10.1, the Money and Secret builtins) is
  unchanged, and the shipped standard library is exempt.
- **`read_file` on a documented credential location is refused (E318),**
  pointed at `read_file_secret`; and such a location is not covered by a
  broad `fs:read:` grant unless a path within it is named explicitly.
- **`velaris add` refuses a redirect from `https` to `http`, and a
  redirect to a host outside the URL's origin.**

Three new error codes, E204, E317 and E318; none reuses a meaning
(rule 3). `velaris.audit/1` gains `ffi_native` within version 1 (an
addition, not a break), and the invocation log gains an optional
`run_params`. Nothing published before 8.0 is moved.

**8.1 (minor), and two refusals it adds.** Both are listed in its CHANGELOG
under "What 8.1 refuses that 8.0 did not", and are recorded here so the
record stays whole.

- **The HTTP door and the MCP server refuse an import from outside the
  directory they serve** (E515), where 8.0 compiled one. The list above
  names the command line's commands, flags and exit codes, and the library;
  what a door does with a request is not on it. But this file counted 3.4's
  door that began refusing requests it had accepted as a break made in a
  minor version, and by that reading this is one too, and is recorded as
  one. It shipped in 8.1 because it closes a read of the door host's files
  by any caller - a token holder, or whatever an MCP client let a model
  send, under the `io` ceiling (advisory-import-read.md) - and because a
  door whose programs import from elsewhere has one flag to set, `--root`.
  The library, which the list does cover, refuses nothing new:
  `import_root=` is an added parameter.
- **`velaris.check()`, `velaris.audit()` and `velaris.attest()` stop at 60
  seconds and 2048 MB** unless raised, where 8.0 waited. The command line has
  had the same ceiling since 8.0, whose CHANGELOG counted it as an addition
  (its memory cap took hold only on Windows until 8.1, and now holds on
  Linux as documented);
  this applies that reading to the library. A check that needs longer passes
  `timeout=`, and `None` restores 8.0's call exactly.
