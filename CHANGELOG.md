# Velaris changelog

## 8.1 - Receipts, and what a policy can ask

A minor version. A program, a budget or a command line written for 8.0
means the same under 8.1, except for what "What 8.1 refuses that 8.0 did
not" names below: on the two doors, an import from outside the directory
they serve, and in the library, a check or audit past the ceiling the
command line has had since 8.0. The adversarial pass run against this
release found two holes, and both are fixed here, each with an advisory
draft.

**Check and audit have a ceiling in the library and the doors.** 8.0 put
`velaris check` and `velaris audit` under a time and memory ceiling on the
command line. `velaris.check()`, `velaris.audit()` and `velaris.attest()`
now run under the same one: 60 seconds and 2048 MB, raised with `timeout=`
and `max_memory_mb=`, and `None` for both checks in the calling process as
before. Source written to stall the prover or to bloat the checker comes
back as a problem - **E613** past the clock, **E614** past the memory cap -
and an audit that is stopped says `ok: false` with nothing determined.
`velaris.Pool` gains `check()` and `audit()`, which keep their worker
between calls. The HTTP door and the MCP server check and audit on their own
workers under `--check-timeout` and `--check-memory-mb`, and the command
line gains `--check-memory-mb` beside `--check-timeout`. The command line's
memory cap did not hold in 8.0 except on Windows: on Linux and macOS the
child it checked in was started without it, so an audit that 8.0 said was
held to 2048 MB used what it liked until the clock stopped it. It is set
now - on Linux, and on macOS as far as the system honours a cap, as for a
run - and `check_library.py`'s Linux legs are what found it. Setting it
showed a second thing: under a cap, CPython on Linux reports running out
about half the time as `SystemError: error return without exception set`
rather than `MemoryError`, which the command line and `velaris.Pool` read
as a crash (E000). Both now read it as running out: E614 for a check or
an audit, E611 for a run. `run(timeout=...)`
now compiles inside its child, under the deadline: until 8.1 it compiled
first in the caller's process with no limit, so a program crafted to stall
the prover held `run(source, timeout=5)` for as long as it liked. A bounded
run is now a pool of one worker, and reports `effects_used` where it
reported `None`. A library `check()` or `audit()` costs a child process's
start - a third of a second on the machine this was built on - where it cost
nothing; `timeout=None, max_memory_mb=None` avoids that for source you wrote
yourself.

**Receipts.** `velaris.receipt/1` records one run: the program and its
imports by sha256 - the subjects `velaris attest` writes for the same bytes,
so an attestation and a receipt of one program are its before and its
after - the budget, every refusal (code, effect, line), every
declassification with its reason, the run's parameters (seed, frozen clock,
timeout, memory cap, and `confinement: "none"`), the exit status and
outcome, and the wall time. It is an in-toto Statement of a new predicate
type, `https://gowrishankar-infra.github.io/velaris-lang/receipt/v1`, signed
as an attestation is signed. `velaris program.vel --receipt FILE` writes
one, `run()` and `Pool.run()` return one as `RunResult.receipt`, and the
doors return one when a request says `"receipt": true`. A run stopped by its
time or memory limit still has one, marked `complete: false`, holding what
the worker reported before it was killed. A receipt holds no value the
program handled: a refusal is recorded without the path or host it named, a
declassification without its value, and no output, input, argument or
message is kept. The release workflow signs the receipt of one run of
`examples/effects.vel` with cosign and with sigstore-python and verifies
both, so a release holds 27 files. velaris-spec 0.10.0 section 8.7 defines
the format.

**What a policy can ask.** `policies/opa/capability.rego` refuses an in-toto
capability attestation - what `velaris attest` writes - whose effects are
outside an allowed set or whose net hosts are outside an allow-list, and one
whose program did not compile or whose host is built while it runs, since
neither can be held to a list. `capability_test.rego` holds a pass, a fail
and the edges. `policies/kyverno/require-capability-attestation.yaml`
refuses a Pod whose image lacks a capability attestation, using Kyverno's
image verification with a keyless attestor. `check_policies.py` runs `opa
test`, and `opa eval` against Statements `velaris attest` writes, and skips
them with a notice where OPA is not installed; CI installs OPA 1.20.2.
EMBEDDING.md has the example.

**`velaris eject`.** `velaris eject program.vel` writes a directory that
runs, and builds into one executable with PyInstaller, with nothing from
this project installed: the program and what it imports, a copy of the
runtime and of the standard library files it uses, `main.py` with the budget
fixed at eject time, a `requirements.txt` pinning the prover and the native
compiler to the versions installed, `proofs.json` recording what was proven,
`SHA256SUMS`, and a README saying what holds once ejected and what does not.
The copied runtime enforces the budget whatever the program says. `main.py`
refuses `--allow`; refuses a program that differs from eject time unless
given `--changed-ok`, and a runtime that differs whatever it is given; and
refuses a budget that would let the program write into its own directory or
where Python imports from (`sys.path`, `PYTHONPATH`, the site directories),
and a `--receipt` inside its directory. The last two came from the
adversarial pass: a program granted a write to a `PYTHONPATH` directory
left a `sitecustomize.py` that the next Python started there ran, and
`--changed-ok` ran a runtime that had been edited. The proofs are a record
that nothing trusts when the
program runs; `main.py --prove` runs them again. `check_eject.py` ejects
`examples/discount.vel`, runs it from a fresh virtual environment with no
packages, then changes it to reach the network and sees E310.

**The doors.**

- `velaris serve --rate-limit N` answers at most N requests a minute - 600
  unless told otherwise - per token, and per address for requests without
  it, so a caller guessing tokens is limited and cannot spend the holder's
  allowance. Past it the answer is 429 with `Retry-After`, logged
  `rate_limited`.
- `--bind` names the address (`--host` still does). A door bound anywhere
  but loopback says so on stderr before it listens.
- The token comparison was confirmed rather than assumed:
  `secrets.compare_digest` over two sha256 digests, whatever length was
  sent. It is one function now, which a test watches.
- EMBEDDING.md says what can connect to the MCP server and the language
  server, and that neither runs a program to answer a hover, a format, a
  check or an audit; a test sends both a program that writes a file, and no
  file is written.

**What 8.1 refuses that 8.0 did not.**

1. **On the HTTP door and the MCP server, an import from outside the
   directory they serve** - `--root`, the directory they were started in
   unless it names another - or of a file there that is not `.vel`, is
   refused with **E515** before the file is opened. A program sent as text
   is compiled as a file in that directory, so its relative imports resolve
   there. Until 8.1 such a program could import any file the door's user
   could read, and the compiler's error quoted what it found
   (`advisory-import-read.md`). A door serving programs that import files
   elsewhere needs `--root` naming their directory. The library is
   unchanged unless `import_root=` is given. By the reading STABILITY.md
   applied to 3.4, a door that refuses what it accepted is a break; this
   one is made in a minor version, and STABILITY.md records it as such and
   says why.
2. **In the library, a `check()` or `audit()` past 60 seconds or 2048 MB**
   is stopped (E613, E614) where 8.0 waited for it. The command line has
   stopped it at the clock since 8.0, and on Linux now stops it at the
   memory cap too, which 8.0 named and did not set there.

**Two holes, fixed.**

- **A false promise could come back proven** (Goal A;
  `advisory-prover-names.md`; 0.9 through 8.0.0). The prover gave the values
  it made up Z3 names a program could also write: `__g_result_1` for the
  result of a call to `g`, `xs__n` for the length of a list `xs`. A
  parameter with such a name was the same Z3 value, so a parameter named
  `__g_result_1` turned `g`'s promise about its result into an assumption
  about the parameter, and a false `ensures` was reported proven - and,
  compiled to native code, never checked when it ran. The prover's own names
  now begin with `!` or contain `#`, which no identifier can. It was found
  checking this release's item 6: the prover builds every query from the
  syntax tree and parses none from text, so an identifier spelled like
  SMT-LIB is an identifier - but a name the prover spelled for itself could
  be written by a program.
- **An import could read a file and quote it** (Goal C;
  `advisory-import-read.md`; 0.16 through 8.0.0). An imported file that is
  not Velaris source gave an error naming its first token - `import
  "/home/me/.env"` answered `found 'API_KEY'` - through the library and both
  doors. That error now names the file and nothing in it, everywhere, and
  the doors hold imports to their root. THREAT_MODEL.md said an import
  "reads Velaris source, not data"; that was wrong, and it now says what an
  import reads.

**Smaller things.**

- `VELARIS_CACHE_DIR` names the directory the proof cache goes under
  (`<dir>/velaris/proofs`); `velaris clean` still deletes only that
  `velaris` directory. A cache file is written beside itself and renamed
  over the old one, so two checks of one file at once each read a whole
  entry. `audit()` no longer writes the cache, which README.md already said
  the library never did.
- `refused_effect` and the doors' log name the refusals 7.1.2 and 8.0 added
  (E316, E317, E318), which a door logged as `failed`.
- Every suite writes to a temporary directory of its own and keeps its own
  proof cache (`suite_dirs.py`), so two runs from one checkout do not
  collide: until 8.1 `run_tests.py` wrote `report.txt` and `ledger.txt` into
  the checkout, `check_library.py` shared one door log, and seven suites
  wrote a scratch program beside the source. CI runs `run_tests`,
  `check_library`, `check_adversarial` and `fuzz_native` twice at once, in
  one job, to show it. `build_docs.py` and `build_playground.py` write each
  page beside itself and rename it.
- README.md and EMBEDDING.md pin the Action by commit, with its tag in a
  comment, and `run_tests.py` checks that the commit is the one the newest
  tag names. Pinned to a commit, the Action installs the version that
  commit's velaris.py names, as it installs a tag's.
- `packaging/placeholders/` records the names beside `velaris-lang`.
  `velaris` is free on PyPI and on npm, and the packages that would hold it
  are ready, not published: publishing takes a registry account this
  repository keeps no credential for. `velarislang` and `velaris_lang`
  cannot be registered by anyone on either registry.
- `examples/platform` audits a submission under its own limit, 20 seconds
  and 1024 MB, and answers 422 when the audit does not finish.

New codes: E515, E613, E614. velaris-spec goes to 0.10.0.

## 8.0 - What the socket reaches, and other things the audit now says

A major version. Two of its changes refuse programs that ran under 7.x, so
by STABILITY.md rule 1 they ship in a major - and a major is where a user
learns to read the CHANGELOG before upgrading. Four things break; the rest
add.

**The socket peer, not the URL string (the proxy hole; E317).** Through
7.x a `net:` grant checked the URL's host, but an ambient `HTTP_PROXY` /
`HTTPS_PROXY` in the environment then routed the request - its payload
included - to a proxy that need not be a granted host. The grant bounded a
string, not the peer. This was the open hole THREAT_MODEL.md carried and
the adversarial pass against 7.1.1 found (advisory left for a major).
`guarded_opener` now disables ambient proxies unless the proxy's own
host:port is itself inside the net budget, in which case that one proxy is
honoured; a proxy the budget does not cover is refused with **E317**,
naming the proxy and the grant that would allow it, and the refusal cannot
be caught. `velaris add` no longer defers to an ambient proxy either. With
no proxy set, behaviour is identical to 7.2.0.

**A function named like a built-in is refused (E204).** Through 7.x a
program that defined `fn print`, `fn env`, `fn read_file` and the like was
silently shadowed - the built-in won and the function was never reached, a
call that read as one thing and did another. It is now **E204**. The rule
of SPEC.md 10.1 is unchanged: a built-in added in 4.3 or later (the Money
and Secret builtins) still gives way to a program's own function of that
name, so `fn money` and `fn split` in a namespaced library keep working;
only the older built-ins, which a program could never actually shadow, are
the error. The shipped standard library is exempt, since it is always
imported under a name.

**A credential file wants read_file_secret (E318).** `read_file` on a
documented credential location - `~/.aws/*`, `~/.ssh/*`, `.env`,
`~/.config/gcloud/*`, `~/.docker/config.json`, `~/.kube/config`,
`~/.netrc`, `*.pem`, `*.key` - is refused with **E318** and pointed at
`read_file_secret`, which returns a `Secret` the compiler will not let
escape. And a credential location is never covered by a broad `fs:read:`
grant that merely sits above it: an operator names it, or a path within it,
explicitly. `read_file_secret` on an explicitly granted credential path is
the sanctioned way and works.

**`velaris add` refuses two redirects.** It refuses a redirect from `https`
to `http` (which would drop the encrypted connection) and a redirect to a
host outside the URL's origin - the two ways a vendoring fetch could be
steered to bytes other than the ones the URL named.

**What a user of 7.x has to change** (STABILITY.md rule 4):

1. **Proxies.** A program that reaches the network with an ambient
   `HTTP_PROXY` / `HTTPS_PROXY` set and a *scoped* `net:` grant that does
   not cover the proxy is refused (E317). Grant the proxy's host too
   (`net:PROXYHOST:PORT`), or run with no proxy set. `velaris add` ignores
   ambient proxies entirely now.
2. **Built-in names.** A function named like a built-in from before 4.3
   (`print`, `env`, `read_file`, `fetch`, `get`, `length`, `split`, ...) is
   refused (E204). Rename it, or move it into a file imported under a name
   so it is reached as `prefix.name`.
3. **Credential reads.** `read_file` (or `file_exists`) on one of the
   documented credential locations above is refused (E318). Read a secret
   with `read_file_secret` and grant its exact path; a broad `fs:read:`
   grant no longer includes a credential file.
4. **`velaris add` redirects.** A source URL that redirects `https`→`http`,
   or to a host outside its origin, is refused. Vendor from a URL that does
   neither, or fetch and add the file from disk.

**The rest, none of it breaking:**

- **The audit says whether a granted module is native.** `velaris.audit/1`
  gains `ffi_native`: per named Python module, `"native"` when a compiled
  extension (`.so`/`.pyd`/`.dylib`, or a built-in) is found on disk, and
  `"unknown"` otherwise - never `"false"`, because a pure-Python module can
  import a native one without that being visible. It is found from files on
  disk **without importing** the module, so a module whose import would act
  does nothing. A new SARIF note `ffi-native`; a THREAT_MODEL.md paragraph.
- **Secrets in code scanning.** `audit --sarif` emits `secret-source` (note)
  for `env` / `read_file_secret`, and `secret-declassified` (warning) for
  each `declassify` - an error under `--strict` unless its reason is listed
  in `--allow-declassify-reasons <file>`. No rule-id clashes with
  `deps-diff`'s.
- **Errors that teach.** Every compiler error and every runtime refusal now
  ends with one line, `reference: <URL>`, pointing at the card
  (`llms.txt`), served at the documentation site; `--json` and SARIF carry
  it as a field. `velaris check` reports every error in a file, recovering
  at statement boundaries; SPEC.md 14 says the first is authoritative, and
  it is the one a single-error run gives.
- **`--seed <n>` and `--freeze-time <iso8601>`** make a run's randomness and
  clock reproducible, recorded as the run's parameters (the doors log
  `run_params`). Neither is a grant: `random()` still needs `rand` and
  `now()` still needs `clock`, and the budget still refuses them.
- **`check` and `audit` run under a time and memory ceiling** (60 s, 2048 MB
  by default; `--check-timeout` raises the clock), so a crafted contract or
  expression cannot stall a platform that audits before running.
- **The Action installs its own version.** With no `version:` input, the
  Action installs the release matching the tag it was used at (`@v8.0.0`
  installs 8.0.0), and the newest on PyPI only from a branch or a commit.
- **New suites.** `check_metamorphic.py` (an audit is unchanged by renaming,
  reordering, dead code, or splitting a program across files, and one added
  effect changes it in exactly one way) and `check_prover_lies.py` (a corpus
  of false promises that must never come back proven).
- **A TrapDoor benchmark case** (category 13): a program whose stated
  purpose is a security scan and whose behaviour is read-credentials-then-
  post, caught before running.

`velaris-spec` goes to 0.9.0 for the two added `velaris.audit/1` fields.

## 7.2 - Releases that tag themselves

No change to the language, the library, the error codes or the command
line, except one `mcp-verify` default that follows from how releases are
now signed.

**A release is made by the workflow, not by a tag.** `release.yml` no
longer runs when a tag is pushed. It runs when the tests complete on a
push to main with every leg passed, and a gate - `release_checks.py
gate` - decides whether that commit is a release: `VERSION` must be newer
than every tag, CHANGELOG.md must have an entry heading for exactly that
version, and the six version files must agree. Otherwise the run says
why in one line and ends green without doing anything, so an ordinary
push to main stays ordinary. A release must also be the very commit the
tests passed on; if main moved while they ran, the gate refuses.
Everything is built, signed and verified before the commit is tagged,
and then published in order, each step skipping what is already there:
PyPI and npm by OIDC trusted publishing, with no token stored for
either; the VS Code Marketplace, as before; the GitHub release; the MCP
registry, logged in by GitHub OIDC, with `server.json` listing both
packages; and the attestation. Last, PyPI, npm, the registry and the
GitHub release must all report the version, or the run fails and names
the one that does not. [RELEASING.md](RELEASING.md) is the procedure,
what a person still does - publishing an advisory, yanking - and the rule
that nobody tags by hand. `check_release.py` holds the gate to fixtures
(a docs-only commit, a version bump without a CHANGELOG entry, a correct
bump, and what else it refuses), and the release runs it before gating.
test.yml is unchanged.

**The tag is annotated, not signed.** This repository has no
tag-signing setup - no earlier tag is signed - the workflow holds no
signing key and should not, and a keyless gitsign signature is one
GitHub does not show as verified. The release notes say so. What is
signed is every artefact, as before.

**Signed as main.** A `workflow_run` runs on main, so from 7.2.0 the
sigstore certificates name `release.yml@refs/heads/main` instead of
`release.yml@refs/tags/vX.Y.Z`; they also record the commit and the
`workflow_run` trigger, and SECURITY.md shows how to check both.
`velaris mcp-verify` now expects the main identity for a manifest of
7.2.0 or later and the tag's for an earlier one; a Velaris older than
7.2.0 checking a 7.2.0 manifest needs `--identity`.

**An advisory file becomes a draft request, never an advisory.** When a
release adds an `advisory-*.md`, the workflow writes the request for a
draft repository security advisory and prints the two `gh` commands
that create it and request its CVE. It cannot run them - GITHUB_TOKEN
cannot be given the repository-security-advisories permission - and it
never publishes an advisory.

**README said the proof cache lived in `./.velaris/`.** That stopped
being true in 7.1.2, and it described the very behaviour the proof-cache
advisory is about. "Remembered proofs" now says where the cache is, how
it is keyed, that a `./.velaris/` is ignored, and what `--no-cache` and
`velaris clean` do; STABILITY.md's mention is corrected as well.

## 7.1.2 - The proof cache could be lied to

An adversarial pass against 7.1.1 found four things. One is a soundness
hole and the reason for this release; three are hardening.

**The proof cache could be lied to (soundness; SECURITY.md challenge #1;
2.29 through 7.1.1).** A second `velaris check` need not re-run the prover
because proof results are cached on disk. Until now that cache was
`./.velaris/proofs.json`, read from the directory the compiler ran in -
the directory that holds the program. A `"proven": true` entry was trusted
without re-proving, and the cache key is a SHA-256 of public, deterministic
inputs (the version, the function's text and contract, its callees'
contracts, the records). So a `./.velaris/` shipped alongside an untrusted
program - inside a project directory or a tarball - could forge an entry
that made a false `ensures` be reported "proven" by `check`, `proofs`,
`audit`, `explain` and the library; and because a "proven" pure-integer
function is compiled to native code, which carries no runtime promise
check, the false promise was also unenforced when the program ran - it
finished with the wrong result and exit code 0. SPEC.md §9.2 says "proven
means established by Z3 before the program runs"; a poisoned cache made
that a lie.

The fix: the program's directory is never trusted for the cache. It moves
to a per-user directory (`%LOCALAPPDATA%\velaris` on Windows,
`$XDG_CACHE_HOME/velaris` or `~/.cache/velaris` elsewhere), and each entry
is bound to, and re-verified against, the source's absolute path, a hash of
its exact bytes, and the compiler version - so a transplanted or hand-edited
entry is re-proved, not trusted. A `./.velaris/` present in a project is
ignored; `velaris audit` prints `ignored: ./.velaris/`. If no per-user cache
can be written, the run proceeds without one. A poisoned `./.velaris/` is
therefore never read: the first run on a malicious program refutes the false
promise (E700 with the prover, or the runtime check E601 without it). See
[advisory-proof-cache.md](advisory-proof-cache.md) and THREAT_MODEL.md.

**Native recursion is bounded like interpreted recursion (hardening).** A
runaway recursive function compiled to native code looped unbounded, because
the interpreter's E609 "recursion that never stops" guard had no equivalent
in native code; the same function run `--no-native` reported E609 promptly.
A directly or mutually recursive function is now left interpreted so the
guard applies, and the interpreter runs a program on a thread with a large
stack so the guard fires cleanly - as E609, within a few seconds - rather
than overflowing the C stack, which on CPython 3.10 for Windows could
crash the process before the guard was reached.

**A giant expression is a clean error (hardening).** A single expression
chaining thousands of operators, or nesting thousands of brackets, built a
tree deep enough to overflow a later pass with a Python traceback. The
parser now stops such an expression with E102, and the compile pipeline
lifts Python's recursion limit so ordinary deep trees still walk.

**`read_file` has a size ceiling (hardening).** `read_file` and
`read_file_secret` read a whole file into memory at once. They now refuse a
file larger than 64 MiB with E316, raised for a run with `--max-read <MB>`.
`fetch` and `post` already capped their reads; this brings the disk to
parity.

The adversarial pass also confirmed, and this release keeps as regression
cases (`check_adversarial.py`), that secrets reach no sink, the sandbox
paths hold on Windows, the ffi reach check refuses foreign modules,
shadowed builtins never win, bidi and zero-width characters outside a
string are refused, `velaris trace` redacts, and the pool leaks nothing
between runs. One finding is left open on purpose: a `net:` grant does not
bound the socket peer when an ambient `HTTP_PROXY` is set, because closing
it refuses traffic that reaches a proxy today and STABILITY.md rule 1 makes
that a major - it is fixed in 8.0.0 and listed in THREAT_MODEL.md until then.

## 7.1.1 - 7.1.0 did not import on Python 3.10 or 3.11

7.1.0, published earlier today, declares `requires-python >= 3.10` and
does not import on Python 3.10 or 3.11. `velaris.py` held an f-string
with a backslash inside a replacement field - `re.split(r'[\s=]', ...)`,
in the lockfile reader added for `deps-diff` - which is a syntax error
before Python 3.12, so every command, every library call and the MCP
server fail at import there. CI caught it on all six Python 3.10 legs.
The release had been verified locally before tagging, but only under
Python 3.13, and a scan written to look for exactly this construct had
a quoting mistake and checked nothing. The expression is now computed
before the f-string, and every Python file in the repository compiles
under Python 3.10.

The second defect was in `deps-diff`'s pull-request comment. To keep an
`@name` taken from a lockfile from mentioning anyone, 7.1.0 put a
zero-width space after the `@` - the character itself. A console that is
not UTF-8, such as the cp1252 of a Windows runner, cannot encode it, so
`velaris deps-diff --markdown` failed at the first `@` in a report, and
`check_deps.py` failed on both Windows Python 3.12 legs. The comment now
carries the same character as an HTML entity, `&#8203;`, so the text is
ASCII and GitHub still renders no mention. A comment posted with
`--comment` was not affected: its body goes to the API as JSON, with
anything outside ASCII escaped.

Nothing else changed. A 7.1.0 user on Python 3.12 or later has nothing
to change; on 3.10 or 3.11, 7.1.0 cannot have run, and 7.1.1 is the
version to install.

**Verified** before pushing. Every Python file in the repository
compiles under Python 3.10.20, and under that interpreter, with
`.[test]` installed and no prover, the whole list the 7.1 entry names
passes with none wrong: `run_tests.py` 97/97, `check_sandbox.py` 57,
`check_secret.py` 78, `check_pool.py` 39, `check_ratchet.py` 114,
`check_deps.py` 54, `check_fallible.py` 29, `check_refusals.py` 15 with
10 skipped for needing the prover, `check_library.py`,
`check_money.py`, `check_platform.py`, `check_termination.py`,
`fuzz_native.py 30`, conformance at L1, L2 and L3, the 456-case drift
test, `benchmark/run.py --quick --check`, `velaris capabilities check .`,
the formatter, and the docs and playground builds. Under Python 3.13
with the console forced to cp1252 (`PYTHONIOENCODING=cp1252`),
`check_deps.py` passes 54/54, and 7.1.0's escaping raises
`UnicodeEncodeError` where 7.1.1's prints. Neither fix is on a path
the benchmark takes; a full run at 7.1.1 wrote every verdict and every
line of evidence 7.1.0's had, and `benchmark/RESULTS.md` and
`results.json` differ only in the version they record. The paper's
benchmark figures and its reproducibility section now name 7.1.1, the
release to check them out at, rather than 7.1.0.

## 7.1 - What an upgrade gained

A dependency can change what it can do between two versions while its
name, its publisher and its declared dependencies stay the same. Koi
Security's report on the npm package postmark-mcp describes versions
1.0.0 to 1.0.15 working as an email tool, and 1.0.16 adding a blind
copy of every outgoing message to an outside address and nothing else.
A signature from the same publisher verifies 1.0.16 as readily as
1.0.15, and an SBOM lists the same dependencies for both. What changed
was what the package could do. This release compares that where it can
be compared, and says plainly where it cannot - which, for a package
that is not Velaris, is nearly everywhere.

**`velaris deps-diff <package> <old> <new>`** reads two versions of one
dependency - `pypi:NAME`, `npm:NAME`, `git:URL` or a path to a git
repository (versions are tags, branches or commits), or `dir:PATH` (one
subdirectory per version) - and reports what the newer one gained.

- **A Velaris library.** Each version's capability surface is derived
  from its `.vel` files as `capabilities init` derives a tree's, and the
  newer is held to the older by `capabilities check`'s rules, W1 to W5,
  with the older standing as the baseline. What it reports gained is
  what the check reports widened: a new effect; a host, path or Python
  module inside an effect the older version already had; more `fs` or
  `net` operations in a run; a function that declares an effect it did
  not. Each finding names the file, line, function and call that
  introduced it and the chain of calls that reaches it, in the check's
  own shape less the edit to `velaris.capabilities`, since there is no
  such file to edit. A version that narrows, or that only moves text
  around - functions reordered, locals renamed, a literal moved into a
  variable - reports nothing gained.
- **Any other package.** What the registry and the package's archive
  declare is read, and nothing more: the install-time scripts npm runs
  (`preinstall`, `install`, `postinstall`, and `node-gyp rebuild` for a
  package with a `binding.gyp` and neither of the first two), what pip
  runs when it builds a source distribution (`setup.py`, the build
  backend and what that requires), a `.pth` file with an `import` line,
  which Python runs at every start; and the declared dependencies -
  npm's dependencies, optional and peer dependencies, PyPI's
  `Requires-Dist`. A script added or changed is reported, including a
  changed file behind an unchanged command. When a registry's manifest
  and the `package.json` in the tarball disagree, the scripts of both
  are reported, each marked with where it was read, because which one
  npm runs has differed between npm versions and depends on whether it
  installs from a lockfile; a disagreement about dependencies is named,
  and the manifest's, from which npm resolves a fresh install, are the
  ones compared. What a script does is not derived. Nor is
  what the package's code can do: no effect, host or path is read off
  Python or JavaScript, and the report says the capability surface is
  **unknown**. A package holding both Velaris and other code gets the
  `.vel` surface and a statement that the rest is not in it.
- **Exit codes.** 0 when both surfaces were derived and nothing was
  gained; 1 when something was gained - a widening, or an install
  script added or changed; 3 when nothing visible was gained and the
  surface was not derived, so that "this could not be seen" is never a
  0; 2 when a version cannot be read - one that does not exist (the
  message lists what does), an unpublished npm package, a download
  whose digest is not the one the registry lists, an archive past
  64 MB. `--json` is `velaris.deps-diff/1`; `--sarif` reports each
  finding under six new rules on the errors page:
  `dependency-capability-widened`, `dependency-effect-gained` and
  `dependency-install-script` as errors, and
  `dependency-surface-unknown`, `dependency-added` and
  `dependency-narrowed` as notes. A bare package name is refused, so an
  npm package is never read from PyPI, or the reverse, by accident.

**Lockfiles, and the Action.** `velaris deps-diff --against REF [path]`
finds the lockfiles changed since REF - `package-lock.json`,
`npm-shrinkwrap.json`, `requirements*.txt` pins, `Pipfile.lock`,
`poetry.lock`, `uv.lock`, `pdm.lock` and `velaris.lock` - and compares
every upgraded dependency, up to 30 (`--max`), placing each finding on
the line of the lockfile that pins the new version. A library
`velaris.lock` vendors is compared file against file: the file at REF
against the file in the tree. A lockfile it recognises and does not
read (`yarn.lock`, `pnpm-lock.yaml`, `Cargo.lock` and others) is listed
as changed and not read. An entry resolved from git, a path, a link, or
a registry or index other than the one `deps-diff` reads is listed and
not read, because the public package of the same name is a different
package; so is every pin of a `requirements*.txt` that sets
`--index-url` or `--extra-index-url`. A dependency new in the lockfile
is listed as added, with nothing to compare it with. `--comment --pr N` puts the
report in one pull-request comment, found again by its own marker and
edited in place on later runs, and edits it to say so once no lockfile
changes any more; `--from FILE` renders a saved `--json` result, so the
registries are read once. The GitHub Action's new `deps-diff` input,
off by default, does all of that on a pull request and uploads the
SARIF when `sarif` is on. It never fails the job: for most packages the
answer is "unknown", and a gate on that would stop nothing it could
name. A package name, version or script from a pull request's lockfile
reaches the comment inside a code span, or with HTML and mentions
escaped, and a `velaris.lock` entry naming a file outside the
repository is not read.

The npm wrapper's table of subcommands names `deps-diff` as new in
7.1.0, so `npx velaris-lang deps-diff` against an older compiler says
which version it needs instead of the old compiler taking `deps-diff`
for a file name; `check_library.py`, which holds that table to the
compiler's own dispatch, found it missing before this release.

**What it does not see**, as THREAT_MODEL.md now says: declared
surface, not behaviour. For a Velaris library the ratchet's own limits
apply. For anything else it sees almost nothing, and postmark-mcp is
the example: by Koi Security's account 1.0.16 changed only the code
that sent the copy, which adds no install script and no dependency, so
`deps-diff` would have reported nothing gained and the surface unknown
- exit 3, not a finding. It would not have caught that case and does
not claim to. npm has since unpublished every version of the package,
and asked about it today `deps-diff` reports that the versions cannot
be read.

**The benchmark: category 12, indirect authority.** Three programs
whose calling code is the same file before and after an upgrade, and
whose dependency's declared budget widened between the two versions -
`12a`, a formatting library that declared nothing and starts posting
each line to a second host; `12b`, a mail library that already reached
the mail service and starts sending a copy to a second host; `12c`, a
settings library that read a file and starts writing one - and a
control, `12d`, whose dependency narrows. Each caller already declares
the effect its dependency comes to use, so it compiles against both
versions and the compiler has nothing to refuse; the Velaris static
step is `velaris deps-diff` on the two versions, and it flags the three
before running and not the control. Deno stops all three while
running, each time with the dependency swallowing the denial and the
program exiting 0; Python misses all three. The harness gained what
that needed and nothing tuned per program: a program may import one
dependency at two versions; the `DANGER` marker is in the new version,
and the caller and the old version must carry none; placeholders are
filled in all three source files, with `/` in paths; and two
observations were added - a request that reached the second listener,
told apart from the caller's own request to the granted one, and a file
the dependency wrote. The table is now 67 programs, 59 dangerous and 8
controls: Velaris 45 caught before running, 12 while running, 2
missed; Deno 5, 30, 24; Python 0, 28, 31; no false positives anywhere.
**No existing verdict moved**: the 63 earlier rows have the verdict and
the evidence they had in 7.0.0's `results.json`, and the verdict they
had at 4.1.0. The benchmark README's table, the README's, and the
paper's section 4.1, Table 1, abstract and conclusion carry the new
figures; the rest of the paper stays pinned to 4.2.1, and its
reproducibility section says which figures come from 7.1.0.

Also fixed in the harness: `benchmark/run.py --check` on a full run
compared verdicts with `results.json` after the run had rewritten that
file, so it could not fail. It now compares before writing. The quick
run CI makes was never affected, since it writes nothing.

**The README's CI section pinned `gowrishankar-infra/velaris-lang@v5.0.1`
and `version: "5.0.1"`**, two majors late, and EMBEDDING.md pinned the
same Action. All three now say 7.1.0, and `run_tests.py`'s version
check fails when an Action pin or a `version:` in either file is not
the compiler's `VERSION`, so the pin moves with each release or the
suite stops.

**`check_deps.py`**, 54 checks, runs on every CI leg and reaches no
network: it serves PyPI, npm and the GitHub API on 127.0.0.1. A library
gaining net, a host inside net, a count, a Python module (read from git
tags) and a function's effect; one narrowing and one rewritten without
changing its surface, neither flagged; a version, a tag and a release
that do not exist, an unpublished package, a digest that does not
match, a package named without its registry; a JavaScript package
whose new source reaches the network, reported as unknown with no host
read off it; install scripts added and changed, a changed file behind
the same command, a registry manifest that hides the tarball's script,
a Python package gaining `setup.py` and an importing `.pth`; a package
holding Velaris and JavaScript; a tarball whose paths climb out, are
absolute or name a drive; the lockfile mode, with an unread lockfile
listed, a vendored library compared, a `velaris.lock` entry naming a
file outside the repository refused, and its plain-text report; the
lockfile formats read directly - a v1 `package-lock.json` whose entries
from git and from a private registry are left out, a `Pipfile.lock`
with an entry from another index and two packages pinning one version,
`poetry.lock` and `uv.lock` entries not from PyPI, `requirements*.txt`
with extras, markers, hashes and `===`, and one that sets another index
- and how an upgrade is paired with the version it replaced; a hostile package name and
error text rendered with no HTML, mention or broken code span; the
SARIF of both modes, validated; the pull-request comment
posted once and edited on the second run, edited again when no lockfile
changes, and never posted for a pull request that changed none; and the
four programs of category 12, each asserted directly with its unchanged
caller compiling against both versions.

`velaris.capabilities` is recorded again at 7.1.0: 190 programs, the
new ones being category 12's callers (which do not compile outside the
harness, since their dependency is placed beside them only there) and
its eight dependency versions. The surface is unchanged. velaris-spec
needs no change: SPEC.md sections 6, 7 and 7.1, the budget grammar and
the formats it specifies are untouched, and the comparison `deps-diff`
makes is its section 9.5. The two JSON documents `deps-diff` writes are
marked provisional in STABILITY.md.

**Verified**, on Windows 11 with Python 3.13, in two fresh virtual
environments holding this tree - one with `.[full,test]` (z3 5.1.0,
llvmlite 0.49.0), one with `.[test]` and neither - rather than in this
machine's global Python, which holds an older Velaris. With the prover:
`run_tests.py` 97/97, `check_library.py` 240 correct,
`check_fallible.py` 29, `check_money.py` 81, `check_sandbox.py` 57,
`check_secret.py` 78, `check_pool.py` 39, `check_platform.py` 15,
`check_termination.py` 44, `check_ratchet.py` 114, `check_deps.py` 54,
`check_refusals.py` 25, none wrong; `fuzz_native.py 30` agrees;
`velaris conformance` passes at L1 (307 cases), L2 (39, and one not run
because this system would not make a symbolic link) and L3 (109);
`build_conformance.py --check` matches velaris-spec's 456 cases;
`benchmark/run.py --quick --check` matches `results.json`; `velaris
test examples/std_test.vel` 7/7; `examples/edges.vel` 20 passed;
`velaris fmt --check` is clean; `velaris capabilities check .` passes;
the playground and the docs build. Without the prover the same list
passes, with `check_library.py` 229 correct, `check_platform.py` 14 and
`check_refusals.py` 15 with 10 skipped for needing the prover, the
other counts as above, and the quick benchmark naming 03a and 04a as
caught while running, as it does whenever the prover is absent. Eleven
consecutive full benchmark runs with Deno 2.9.6 - the last after the
final change to `velaris.py` - wrote byte-identical `RESULTS.md` and
`results.json`. velaris-spec's `tools/check_sync.py` passes against this
tree, and its `tools/validate.py --capabilities` accepts the
re-recorded `velaris.capabilities`. The arXiv package was regenerated
with pandoc 3.11 and builds to 12 pages. Verifying found three defects
in this release's own work, each fixed before tagging: inserting
section 20 had deleted the line `def card()`, which `check_library.py`
caught; two new module-level tables were not registered with
`check_pool.py`'s reset scan; and the npm wrapper's table lacked
`deps-diff`.

**Sources, named** (CONTRIBUTING.md rule). The test category 12 is
built on was proposed by Ali Khater (dev.to `alikhatersaibreakroom`) in
a comment of 12 September 2026 on the dev.to post about this benchmark,
https://dev.to/alikhatersaibreakroom/comment/3elgc: "A next test I would
love to see is indirect authority: a safe-looking function calling a
dependency whose declared effect budget changes between versions." The
postmark-mcp case is from Koi Security, "First Malicious MCP in the
Wild: The Postmark Backdoor That's Stealing Your Emails" (Idan
Dardikman, 25 September 2025), read through the Internet Archive's copy
of that date because the original address now redirects elsewhere; its
indicators name 1.0.16 and later as malicious. npm's registry record
lists thirteen version numbers before 1.0.16 (1.0.4 to 1.0.6 were never
published) and every version unpublished on 25 September 2025. That a
registry's manifest and a tarball's `package.json` are published
separately and never checked against each other is from Darcy Clarke,
"The massive bug at the heart of the npm ecosystem" (vlt blog, 27 June
2023). npm maintainers have described which copy npm reads in two
contradicting comments on npm/cli issue 5234, and Arborist's source
shows the answer changed between npm releases; that is why `deps-diff`
reports both copies rather than choosing one. npm's default
`node-gyp rebuild` install script for a package with a `binding.gyp`
is from npm's scripts documentation. The design of the command - the ratchet's comparison with the older version
as the baseline, exit 3 for a surface not derived, the comment - was
specified by the maintainer.

## 7.0 - A secret you cannot look at

6.0, published this morning, shipped `Secret of T` with a hole in it,
and this release closes it. The hole was in a decision 6.0 made
deliberately and argued for in writing, which is the kind worth
describing rather than quietly fixing.

**What 6.0 got wrong.** It let a comparison over a secret give an
ordinary `Bool`. The argument was that a comparison is one bit, that
`if key == ""` has to be writable, and that refusing `print(k == "")`
while allowing `if k == "" { print("empty") }` would stop nothing.
Every step of that is true of *one* comparison. It is false of a loop:

```
let at = 0
while at < 3 {
    for c in alphabet {
        if code_at(key, at) == code_at(c, 0) {
            found = found + c
        }
    }
    at = at + 1
}
print("recovered: " + found)
```

That program compiled under 6.0 and printed the key. A comparison is
not a one-bit channel; with `length` and `code_at` it is a
character-by-character oracle. A type that stopped `print(key)` and
allowed the loop above is not information-flow control, it is a
decoration — and shipping a decoration under that name is worse than
shipping nothing, because somebody relies on it.

**What 7.0 does.** The rule loses its exception and gains a second
half:

- **Every pure operation over a secret gives a secret, a comparison
  included.** `key == ""` is a `Secret of Bool`. So are
  `length(key) < 10` and `contains(key, "a")`. Nothing prints one — it
  is a Secret, so E560 already covers it. What a *container* is, as
  against what it holds, is not: `length` of a list of secrets is an
  ordinary `Int` and `has(m, key)` an ordinary `Bool`, because a
  program cannot have made a list's length depend on a secret without
  branching on one. So a program can still walk a list of secrets.
- **Nothing branches on one.** An `if` or `while` whose condition
  carries a secret is **E563**, naming where the secret came from. The
  loop above is refused at the branch, before the print.
- **A promise is not a branch.** `requires length(key) > 0` is still
  allowed: a broken promise stops the run, cannot be caught and cannot
  accumulate, so it tells a reader one bit per run rather than reading
  a secret out in a loop, and its message already redacts the values
  whose type is secret.

To look at a secret, a program says so:

```
let empty = declassify(key == "",
"whether a key is set at all is not the key")
if empty { ... }
```

which needs `uses declassify`, the operator's grant, and a reason the
audit records. That is the trade the language now offers: not silence,
a statement.

**A third rule, and the second hole.** Looking for the first hole
turned up two more routes, both the same shape - a value derived from a
secret coming back as an ordinary one.

A generic body is checked once, with its type variables standing for
nothing in particular, so inside `fn contains_item(xs: List of T, item:
T) -> Bool` the comparison `get(xs, i) == item` is a plain `Bool`;
there is no secret in sight. Bind `T` to one at the call site and
`contains_item([guess], key)` hands the caller an ordinary `Bool` about
the key. 6.0 refused only *effectful* generics, on the reasoning that a
pure one can reach no sink - which was wrong, because it does not have
to reach a sink, it only has to hand the value back. **No type variable
is now bound to a type that carries a secret** (E560), pure or not. The
way to write a generic over secrets is to say so:
`fn pass(s: Secret of T) -> Secret of T for any T`.

**And the second hole.** A failure's reason is `Text` the
program can print, and the runtime writes it out of the values it was
given — `to_int` quotes the text it could not read. So
`check to_int(key) { fail w { print(w) } }` printed the key under 6.0.
No builtin that can fail now takes an argument carrying a Secret
(E560): `to_int`, `parse_money`, `json_get`, `pop`, `slice`, `set_at`
and the `_or_fail` family. `get` on a map is the exception that proves
the rule — its reason names the key, and a key is `Text` or `Int`.
The whole sink check now lives in one place in the type checker, so a
builtin added later cannot acquire a route quietly.

### What a 6.0 user has to change

6.0 was published for one day. If you wrote anything against it:

1. `if key == ""` and any other branch on a value derived from a
   secret — E563. Declassify the answer with a reason, or decide
   without looking.
2. `to_int(key)`, `parse_money(key, ...)`, `json_get(key, ...)` and any
   other fallible builtin given a secret — E560. Declassify first.
3. `stdlib/env_tools.vel`'s `number_setting` now declassifies before it
   looks, rather than after; its signature is unchanged.

This is a major version because it refuses programs that compiled
under 6.0, and STABILITY.md rule 1 says that ships in a major version
even when — especially when — it is a security fix. STABILITY.md
records 6.0.0 as a release that stood for one day.

### The record

One new code, **E563**. `check_secret.py` grows from 58 checks to 76:
every fallible builtin refused, the comparison rules in both
directions, the branch refused in `if` and in `while`, the extraction
loop refused at the branch and the same program accepted with
`declassify` and recorded in the audit, `contains_item`, `index_of` and
`first` each refused a secret, and the `Secret of T` signature that is
the way to write a generic over one. `check_refusals.py` gains E563.
velaris-spec goes to 0.8.0: no rule of the format changes, and section
8.6 narrows what it claimed. The corpus is 456 cases.

The benchmark is unchanged: 42 caught before running, 12 during, 2
missed, 0 false positives.

## 6.0 - Secrets that cannot be printed

A major version, and a breaking one. Effects tell you a program
printed something. They do not tell you whether what it printed was
the secret. `Secret of T` is the data half of that: a value the type
system tracks so that it cannot reach a sink.

E530 has enforced the harder half since 2.x - a function value passed
to a library must be pure, so a closure handed to a library cannot
perform effects. This is the other half, and it is the one capability
the peer-reviewed design this project sits beside
([TACIT](https://github.com/lampepfl/tacit), ACM CAIS '26) had and
Velaris did not. velaris-spec's PRIOR_ART.md said so in writing; it
now says what is true instead, and what TACIT still has that this does
not.

### The type

`Secret of T` wraps any T. Two builtins make one, and nothing else
does:

- `env(name, fallback)` returns `Secret of Text`. **This is the
  breaking change.**
- `read_file_secret(path)` is new: `read_file`'s companion, the same
  `fs` effect and the same failure, returning `Secret of Text`.

A program cannot make a Secret out of a value it already holds, and
nothing else is secret by default. A secret that arrives another way -
`read_line`, `args()`, a granted `ffi` module - is an ordinary `Text`,
and THREAT_MODEL.md says so plainly rather than leaving it implied.

**Where one cannot go.** Every builtin that declares an effect emits
what it is given, so none of them takes an argument that carries a
Secret. That is one rule covering `print`, `log`, `ask`, `exit_with`,
`read_file`, `read_file_secret`, `write_file`, `file_exists`, `fetch`,
`post`, `fetch_status`, `request`, `env` itself, `now`, `random` and
the whole `py_*` family - and the reason given to `fail`, which is
shown to whoever runs the program. The refusal is **E560**, and it
names the value, what would have emitted it, and where the secret came
from, following the trail through the program's own functions:

```
error[E560] argument 1 of 'print' is Secret of Text, and 'print' performs io -
a Secret cannot be printed, written, sent or passed to Python. It came from
env(), line 28, through 'key', which returns Secret of Text (line 63)
```

A program's own effectful function needs no rule: it declares the
types it takes, and a Secret is not one of them unless it says so. One
case does need a rule. A generic body is checked once with its type
variables standing for nothing in particular, so `print(x)` inside
`fn show(x: T) uses io` is allowed there; binding `T` to a secret at a
call site would print it. So a generic function that declares any
effect takes no argument carrying a Secret (E560). A pure generic
function may take one: it can reach no sink.

**A structure is not a way around it.** `List of Secret of Text`, a
map whose values are secrets, a record with a secret field, a record
holding such a record - each carries the secret, and the *whole
structure* is refused at a sink, not only the field. A map's keys are
`Text` or `Int`, so a secret is never a key. This is not the coarse
approximation it might have been: which record types carry a secret is
a fixpoint over the record definitions, computed once per program.

**What keeps one.** Pure computation over a secret gives a secret:
`length(k)` is a `Secret of Int`, `"Bearer " + k` a `Secret of Text`,
and `to_text`, `format`, `json_of`, `upper` and the rest all keep it.
One line states it: a pure operation on a value that carries a secret
gives a Secret of its result type, unless that result is `Bool`. There
is no `Secret of Secret of T` (E562).

### The Bool, stated as a choice

A comparison is the exception. `k == ""`, `length(k) < 10` and
`k > other` give an ordinary `Bool` that may be printed, and a
comparison is the one place a secret and a plain value of the same
type may stand together.

That is a one-bit channel per comparison, and enough comparisons
recover the secret: a loop comparing `length(k)` against 0, 1, 2, ...
tells you the length exactly, and the program may print what it
learned. It is allowed anyway, and the reason is worth writing down.
An `if` condition must be a `Bool`, so a comparison that gave a
`Secret of Bool` could never be branched on, and a program could not
check whether its own API key was empty. And a rule that refused
`print(k == "")` while allowing `if k == "" { print("empty") }` would
stop nothing and cost everything.

**Velaris bounds explicit flow, not implicit flow.** What it
guarantees is that the secret's value never reaches a sink. What a
program can work out about a secret through its own control flow, and
then say, is not bounded. SPEC.md 3.1 states this, THREAT_MODEL.md
states it again among what is not defended, and neither calls it
non-interference, because it is not.

A `Secret of Bool` a program *declares* is different: it is kept, `and`
and `or` over it keep it, and it is not a condition (E504). Only a
comparison makes a plain one.

### declassify, and the eighth effect

`declassify(value, reason)` takes a `Secret of T` and gives back the
`T`. It is the only way out, and it says so three times:

- the function doing it needs `uses declassify`, checked across the
  whole call graph like any other effect (E300);
- `reason` must be written as text in the call, not built while
  running, so `velaris audit` can report it without running the program
  (E561 - and E561 for an empty reason, or for something that is not a
  Secret);
- the operator's budget must grant `declassify`, or the call is refused
  where it happens (E310), like any other effect.

So `declassify` is the eighth effect, and it behaves as the seven do
everywhere: in a signature, in `velaris.audit/1`'s `effects`, in
`safe_command`, in `velaris.capabilities`, in a SARIF note, in
`--deny`. `--allow all` grants it. `all` means all - an operator who
writes it has waived every gate, and it already writes a line to
standard error saying so.

Unlike the seven it reaches nothing outside the program. It is an
effect because it is the one operation that removes the type system's
mark, and an operator has the same reason to refuse it as to refuse
`net`.

### What the audit says

`velaris.audit/1` gains a `secrets` object - an added field within
version 1, so a consumer that does not know it ignores it:

```json
"secrets": {
  "sources": ["env"],
  "declassifies": false,
  "declassifications": []
}
```

`sources` names the builtins the program reaches that hand it a
Secret. `declassifies` answers, without running the program, the
question a consumer actually has: *does this ever let a secret out.*
`declassifications` names each one - the reason written in the call,
the function it is in, and the line. The field is `null` only when the
program could not be loaded; a program refused *for* leaking a secret
still reports the source that made it, which is what a reader wants at
that moment. `velaris audit` prints the same under WHAT IT KEEPS
SECRET.

What it does not claim is written beside it: the reasons are unchecked
text, the rule bounds explicit flow only, and it covers only values
those two builtins produced.

### Two places that print values behind a program's back

A Secret has no runtime representation - it is a compile-time
distinction, so it costs nothing and `declassify` evaluates to the
value itself. Two things print values the program did not ask them to,
and both now write `<secret>` instead: `velaris trace`, and the message
of a broken `requires` or `ensures` (E600, E601), which prints the
values of every name the promise mentions. `requires length(key) > 0`
is exactly the kind of promise to make about a secret, and until now it
would have printed the key when it broke.

### What a 5.x user has to change

**Anything that treats what `env()` returns as a `Text`.** Three
shapes, and the compiler points at each:

1. `print(env("API_KEY", ""))` and every other emission - E560.
   Compare instead (`if key == ""`), or `declassify` it with a reason
   if it genuinely is not a secret.
2. `fn config(n: Text) -> Text uses env { return env(n, "") }` - E503.
   Write `-> Secret of Text`, and let the type travel with the value.
3. `let plain: Text = env("K", "")`, or passing it to a `Text`
   parameter - E501.

A program that only *compares* what it read - `if length(env("PATH",
"")) > 0` - is unaffected: comparisons give ordinary Bools.
`examples/stress.vel` needed no change for exactly that reason.

**`stdlib/env_tools.vel` changed with it.** `setting` now returns
`Secret of Text`. `number_setting` keeps returning `Int` and now
declares `uses env, declassify`, declassifying with the reason "a
numeric setting is a number, not a secret" - which is the honest thing
for it to say, and which now appears in the audit of every program
that uses it. `public_setting(name, fallback) -> Text` is new, for a
setting a program says is not a secret at all.

**A repository with a committed `velaris.capabilities`** will see
`declassify` reported as a widening the first time a program needs it,
and someone has to edit the baseline. That is the ratchet working.

### The demonstration

[`examples/secret.vel`](examples/secret.vel) reads an API key from the
environment, builds the request that would carry it, and prints a
summary of that request. `velaris audit examples/secret.vel --json`
says `"declassifies": false`, which is the whole claim: the key reaches
nothing that emits it.

[`examples/secret_bad.vel`](examples/secret_bad.vel) is the same file
with one more line in `main`. It does not compile, and the refusal
names where the secret came from. Nothing ran, nothing was logged, and
no reviewer had to notice the line. The two of them next to
`discount.vel` and `discount_bad.vel` are the clearest statement of
what this language does.

### Codes, tests and the record

Three new codes: **E560** (a Secret given to something that emits it),
**E561** (a `declassify` without a reason written in the call, or given
something that is not a Secret), **E562** (a Secret of a Secret). None
is reused; STABILITY.md rule 3 holds.

`check_secret.py` is new: 58 checks over every emitting builtin, every
shape of structure, every laundering route, both halves of the Bool
decision, all three ways `declassify` is refused, the audit's `secrets`
section for each shape, the tracer and the broken promise, and honest
programs that must still run. `check_refusals.py` gains E560, E561 and
E562. `check_sandbox.py` gains the `declassify` grant refused and
allowed. `check_fallible.py` gains `read_file_secret`. velaris-spec's
corpus grows from 444 cases to 455: eight L1 cases for the new audit
field and the refusals around it, three L2 cases for the grant, and one
L2 case reworded because the program it held no longer compiles. (7.0
takes it to 456.)

velaris-spec goes to 0.7.0: `declassify` joins section 3.1, and section
8.6 defines `secrets`. PRIOR_ART.md's TACIT entry, which said Velaris
had no information-flow control, now says what it has and what TACIT
still has that this does not; CaMeL's entry is corrected the same way.

The benchmark was rerun in full. **No verdict moved**: 42 caught before
running, 12 during, 2 missed, 0 false positives, unchanged. One row's
evidence changed - `11c c_secret_from_env`, whose "config" helper reads
a secret from the environment and prints it, was already
caught-before-run because the audit showed an effect beyond the
program's stated needs; it is now refused by the compiler instead
(E503 on the helper's signature), so nothing is attempted at all.

The GitHub Action's branding icon is `shield` where it was
`check-circle`. A check-circle reads as "a check passed", which is the
framing 5.0 moved away from.

## 5.0.1 - check_library.py runs on Linux and macOS again

A test-suite fix. Nothing a user runs changes: the compiler, the
library, the doors and every document are as 5.0.0 published them.

`check_library.py`'s npm-wrapper section builds throwaway virtual
environments in which one Velaris is reachable under one spelling of
`python`, so that the wrapper's choice can be asserted. On POSIX a
venv's `bin/python`, `bin/python3` and `bin/pythonX.Y` are a chain of
symbolic links ending at the base interpreter, and the section got two
things wrong about that: copying one of those names onto another is
`SameFileError`, and removing the others would have left whichever name
remained dangling. The first of the two is what failed, and it failed
every Linux and macOS leg of CI from 4.3.4, where the section was
added, through 4.3.4, 4.4.0 and 5.0.0 - eight of the twelve legs, on a
file no release ships. Windows, where a venv's interpreters are real
copies, was unaffected and green throughout. The name is now remade as
a link straight to the end of the chain, so both spellings survive the
removals; `pyvenv.cfg`, not the name of the link, is what makes it a
venv.

## 5.0 - The default is io, not everything

A major version, and a breaking one. Until now, `velaris program.vel`
with no `--allow` granted all seven effects: the program could read
and write any file the OS user could reach, open any socket, read
every environment variable and call any Python module. A capability
language whose answer to "what may this program do if you say nothing"
is "everything" has the one thing it exists for backwards, and this
repository said so in writing - THREAT_MODEL.md conceded it, the
README's related-work paragraph conceded it against WASI, whose
modules reach nothing unless the host hands them something, and
velaris-spec's PRIOR_ART.md recorded that Boruna's default policy
grants nothing where Velaris's granted seven effects.

From 5.0 a run that asks for nothing gets `io`.

**Why `io` and not nothing.** Granting nothing is the stricter answer,
and it is the one Boruna and WASI give. It was considered and not
taken, for two reasons. A program refused under a budget that grants
nothing cannot say why it stopped, and cannot print the diagnosis of
its own refusal - the refusal itself reaches the operator through the
runtime's standard error, but nothing the program wanted to tell you
first does. And `io` is the effect no example, tutorial, README
snippet or notebook cell in this repository can do without: a default
of nothing would have made every one of them fail on upgrade with a
refusal about `print`, which teaches the wrong lesson about what a
budget is for. `io` is the console - `print`, `read_line`, `args` -
and it touches no file, no socket, no environment variable and no
Python module. The gap between this and granting nothing is one
effect, and THREAT_MODEL.md has always listed what `io` still
includes. It is written down here so the choice is on the record
rather than assumed.

### What a 4.x user has to change

**Every command, script, CI step, notebook cell and library call that
runs a program needing more than `io`, and did not say so.** It will
now stop with E310 at the first operation outside `io`, naming the
effect, what the run does allow, and the flag that would grant it:

```
error[E310] 'read_file' needs the 'fs' effect, which this run does not
allow (it allows: io)
  how to fix (pick one):
    1. allow it: velaris <file> --allow io,fs
    2. a run with no --allow gets io (5.0); --allow all grants every effect
    3. or use a program that does not need it
```

Item by item:

- **`velaris program.vel`** grants `io`. It granted all seven.
- **`velaris.run(source)` with no `allow`** grants `io`. It granted
  all seven. So does **`velaris.run(source, timeout=...)`**, whose
  child process is started with the same budget.
- **`velaris.Pool(...)` with no `allow`** grants `io`. It granted all
  seven. `pool.allow` reads `"io"`.
- **`velaris test program.vel`** runs its test functions under a
  budget, `io` unless `--allow` says more. It ran them under all seven.
- **An executable from `velaris build`** grants `io`, and takes
  `--allow` the way the compiler does: `./myprogram --allow io,fs:read`.
  An executable built by 4.x is not affected - it carries the compiler
  it was built with - but one rebuilt on 5.0 is.
- **`velaris trace program.vel`** is the run it traces, so it takes the
  same budget and the same default.
- **`--deny` narrows what `--allow` gave.** `velaris program.vel
  --deny net` leaves `io`, where it left the six effects other than
  `net`. Writing `--allow all --deny net,ffi` is how to get the old
  meaning, and it says what it is doing.
- **The two doors are unchanged.** The MCP server's ceiling has been
  `io` since 3.4 and the HTTP door's since 4.0. 5.0 is the release
  where every other place a budget comes from agrees with them.

**`--allow all` is the explicit way to ask for everything.** It grants
the seven effects and writes one line to standard error:

```
velaris: --allow all grants every effect (io, env, fs, net, clock,
rand, ffi); nothing this run does will be refused by the budget
```

It is an operator's word on a command line - `velaris`, `velaris
serve --max-allow`, `velaris mcp --max-allow`, and `allow="all"` in
the library - and deliberately not part of the budget grammar: a
budget a caller sends to the HTTP door or the MCP server cannot
contain it, and `Budget.parse("all")` is refused as it always was.

**`velaris migrate --to 5.0 [path] [--write] [--json]`** does the
work. It reads a program or a tree, derives the narrowest budget each
program needs from that program's own audit - the same grants
`velaris audit` puts in `safe_command` - and prints the command to run
it under 5.0:

```
examples/wordcount.vel
    uses:  fs, io
    run:   velaris examples/wordcount.vel --allow fs:read,io
```

It changes nothing unless `--write` is given, and then only lines in
shell scripts and CI files it can parse without guessing: one command
on the line, a `.vel` path that resolves to a program it audited, no
budget flag already there, and nothing - a pipe, a chain, a
substitution, a redirection - that would make the end of the command
the wrong place for a flag. Everything else is listed as left alone,
with the budget to add by hand. A program that does not compile is
reported as such rather than guessed at.

### What is not changed

The budget grammar, every refusal code, the audit and capability
formats, the doors' ceilings and every schema. A budget that parsed
under 4.x parses under 5.0 and grants the same thing. A program's
source is untouched: nothing about `uses`, contracts, proofs or
failure moves. This is a change to what an operator gets when they
say nothing, and to nothing else.

### The record

- **STABILITY.md** lists 5.0 under "Breaks we have made", with the
  reason and what a 4.x user has to change.
- **THREAT_MODEL.md** no longer carries the permissive default among
  the things it does not defend against. The concession is dated
  rather than deleted: it says what was true until 5.0, and that the
  README's and the paper's versions of it were true until 5.0 too.
- **velaris-spec 0.6.0** restates section 4.6 (what the reference
  grants when no budget is given) and section 4.4 (a denial narrows
  the runtime's default budget, which the format does not fix). One
  conformance case changes with it:
  `L1-budget-deny-from-all-seven` becomes
  `L1-budget-deny-from-grants-given`, which writes the grants its
  denial applies to; `L2-deny-one` and `L2-deny-several` gain theirs
  too. The corpus is still 444 cases, and every one of them now names
  its own budget rather than leaving an implementation's default to do
  the work.
- **velaris-spec's PRIOR_ART.md** corrects the Boruna and WASI
  entries: Boruna is still the stricter of the two, by one effect
  rather than seven. The paper's related-work paragraph says the same.
- **SPEC.md 7.1** states the default, which it did not.

### Tests

`check_sandbox.py` gains five cases: a program that writes a file and
one that reaches the network, each refused with no `--allow` at all;
the refusal's own text, which must name the effect, what the run
allows and the flag; `--allow all`, which must run the same program
and print its warning; and `--deny` with no `--allow`, which must
narrow the default rather than widen it. `check_library.py` gains
fourteen: `run()` with no `allow` refused and its message checked,
`run(allow="all")` and the seven names spelled out, a bounded run's
child, a pool made with no `allow`, and one that compares the budget
the command line, the library, the pool and both doors start from and
fails unless all five are `io`.

Every suite and both fresh-venv legs pass: `run_tests.py`,
`check_library.py`, `check_sandbox.py`, `check_money.py`,
`check_termination.py`, `check_pool.py`, `check_ratchet.py`,
`check_platform.py`, `check_refusals.py`, `check_fallible.py`,
`velaris conformance` at L1, L2 and L3, `fuzz_native.py 30`,
`benchmark --quick --check`, `velaris test examples/std_test.vel`,
`velaris fmt --check` and `velaris capabilities check`.

## 4.4 - A platform that lets its customers write code it can audit

A minor version. Every program that compiled under 4.3.4 compiles, runs
and means the same; nothing is added to the language, the capability
surface or any document format. What is added is an example: the pattern
a SaaS team would copy to let its own customers write Velaris.

**`examples/platform/` is that pattern in one file.** A small FastAPI
service, under 200 lines, with three endpoints. `POST /scripts` takes a
customer's source, audits it, stores it with its capability surface and
answers with what it declares - the effects it may perform transitively,
the hosts and paths it names, the Python modules it reaches, the most
file and network operations one run can make, its proven share, its
contracts function by function, and the narrowest budget that would run
it. It does not run it. `GET /scripts/{id}` is that declaration again,
as a customer would be shown it before enabling anything. `POST
/scripts/{id}/run` runs it on a `velaris.Pool` whose budget is the
platform's, and answers with the output, or what the budget refused, or
which limit stopped it.

**A surface wider than the platform permits is refused at submission.**
The service holds what the audit derived against one budget constant
with `Budget.covers`, which names the first thing that does not fit, and
the refusal carries the grants an operator would have to add. A script
that reads a file is refused with `would_need_granting: ["fs:read"]`. A
script that builds its host while running is refused too, because the
audit cannot read a value the text does not fix and says plain `net`
rather than guessing - where the same program with the host written out
is accepted as `net:api.example.com`. The gate compares what a script
may touch and not how much of it: an audit bounds operations only where
the text fixes them, and the count is the pool's to hold either way.

**The pool does not depend on the gate having been right.** They are
separate guards, and the example is written so that is visible: the
budget is parsed once when the pool is made, `pool.run` takes no `allow`
argument, each worker installs the budget before the program is read,
and a refusal cannot be caught. `check_platform.py` puts a script
straight into the store, past submission entirely, and asserts the run
is still refused with E310. A bug in a platform's gate is not a bug in
its containment, and that is the property worth copying.

**The worked example is the proven discount.** Submitting
`examples/discount.vel` answers `"proven_share": 100.0` with `"status":
"proven"` on every promise, including the two a platform taking the
payment cares about: the discount is never a surcharge, and what is left
after it is never negative, for every basket and every rule the types
allow. `examples/discount_bad.vel` - the same rule with one guard
deleted - never reaches storage: submission answers E700 with the basket
and rule that break it. No sandbox can produce either answer, and it is
the answer a platform needs before it offers to enable a rule it did not
write.

**fastapi is a dependency of the example, never of Velaris.** It is not
in `[project.dependencies]` and the wheel does not ship `examples/`. It
joins `jsonschema` in the `[test]` extra, which exists so the suites can
run, and `check_platform.py` skips cleanly when it is absent.

**`velaris` with no arguments reports the version it is.** It prints the
module docstring, whose first line named a version - and that line had
said `Velaris v2.36` since the docstring was written, so every reader
since has been told they were running a compiler two major versions old.
The docstring now carries no version of its own and the running version
is filled in when it is printed, which cannot go stale. `run_tests.py`
checks that line against `VERSION` like every other place a version
lives, and now checks the MCP registry manifest as well - it carries the
version three times, its own and one per package, and all three are
published, and until now nothing held them to the compiler.

## 4.3.4 - The npm wrapper picks the right Python, and says when it cannot

A patch version. Every program that compiled under 4.3.3 compiles, runs
and means the same; nothing is added to the language, the capability
surface or any document format. What changes is how the npm package
decides which Python holds the compiler, and what it tells you when the
one it found is not the one you meant.

**The wrapper takes the newest Velaris it finds, not the first.** It
tries `py`, `python` and `python3` in that order on Windows, `python3`
then `python` elsewhere, and until now it took the first of them that
could import `velaris` at all - whatever version that one held. So an
old install earlier in the order silently shadowed a newer one further
down, and every run went to the old compiler. That is how `npx
velaris-lang mcp` failed on the maintainer's machine the day 4.3.3 went
out. Each candidate is now asked for `velaris.VERSION` rather than merely
whether the import works, and the newest answer wins. `velaris.VERSION`
has been there since 1.0, so every real compiler answers; something
importable as `velaris` that is not one is still used if it is the only
candidate, but ranks below every version that can be read, so it cannot
shadow a real install by being earlier in the order.

**A compiler older than the package is never used silently.** If the
newest Velaris found is still older than the npm package that invoked
it, the wrapper runs it - refusing would help nobody - but first prints
one line to stderr naming both versions and the interpreter the compiler
came from. The interpreter is the part worth printing: when two Pythons
each have a Velaris, knowing which file was imported is the difference
between a five-minute fix and a mystery. Nothing else about the run
changes, and stdout is untouched, so a script reading the wrapper's
output still reads only the compiler's.

**A subcommand the compiler is too old to have is named as missing.**
`velaris mcp` arrived in 4.3.3. Handed to a compiler older than that, it
is not a subcommand at all, so the compiler took it for a file name and
said `cannot find file 'mcp'` - true, and no help to anyone. The wrapper
now carries the version each subcommand first shipped in, and when the
compiler it found is older than that, it says so instead of handing the
command over: which command, which version it arrived in, which
interpreter holds which older version. It stops before running, so there
is one message rather than two. A global flag before the subcommand,
such as `--proof-timeout 300`, does not hide it; an argument that is not
a subcommand, such as a file name, is left alone. `check_library.py`
holds the table to the compiler's own dispatch in both directions, so a
subcommand cannot be added to the language without an entry, and the
table cannot claim one the compiler lacks.

**The Node library chooses the same way.** `findPython` in
`npm/index.js` had the same flaw, and it mattered more there: one stale
choice is cached for the life of the process, so every `check`, `audit`
and `run` through the module answered with a version the caller did not
ask for. It now shares the probing with the command line - both import
`npm/python.js` - and prints the same line, once per process rather than
once per call. When no candidate has Velaris at all, both say what they
said before: `pip install velaris-lang`.

**The arXiv package is level with the paper again.** `paper/velaris.md`
gained a paragraph in the reproducibility section saying which two tags
the paper describes; `paper/arxiv/velaris.tex` is pandoc output and is
regenerated rather than edited, so it was left one paragraph behind
until pandoc was available. It has been regenerated with the command in
`paper/arxiv/README-for-me.txt` and rebuilt the way arXiv builds it. The
paper still describes Velaris 4.2.1 and velaris-spec 0.5.1; that pin is
unchanged.

## 4.3.3 - velaris mcp, so the npm package can start the server too

A patch version. Every program that compiled under 4.3.2 compiles, runs
and means the same; nothing is added to the language, the capability
surface or any document format. One subcommand is added, and it is an
alias.

**`velaris mcp` starts the MCP server.** Until now the only way in was
`python -m velaris_mcp`, which an MCP client can only use if it knows
where the module sits. `velaris mcp` reaches the same server through
the console script, and because the npm wrapper passes its arguments
straight to `python -m velaris`, `npx velaris-lang mcp` reaches it too.

It is a thin alias and deliberately nothing more: it hands
`velaris_mcp.main` the arguments after `mcp` and returns what it
returns. The flags, the four tools, the `--max-allow` ceiling, the
timeout and memory ceilings and the invocation log are the server's,
parsed by the server; there is no second copy of any of them here, and
an unknown flag produces the server's own usage message. The one place
the alias is not transparent is `--max-memory-mb`, which for `mcp` -
as for `serve` - is the most each run may have and not a cap on the
server process, so it is excluded from the early self-cap the way
`serve` already was. `check_library.py` pins both halves: that
`velaris mcp` answers `initialize` byte for byte as `python -m
velaris_mcp` does, and that a bad flag stops it with the server's
message.

**The MCP registry entry now declares the npm package.** With
`velaris mcp` in place, `npx velaris-lang mcp` genuinely starts an MCP
server, so `integrations/mcp_registry/server.json` declares the npm
package beside the PyPI one, and `npm/package.json` carries the
`mcpName` the registry checks for npm ownership. It was left out of
4.3.2 on purpose, because until this version the npm package could not
start a server and declaring it would have handed clients a launch
command that started the language CLI instead.

Worth knowing before you rely on it: the npm package is a wrapper, not
a copy. It finds a Python that can import `velaris` and calls it, so
`npx velaris-lang mcp` still needs `pip install velaris-lang`, and if
the Python it finds holds an older Velaris than the wrapper, the
subcommand will not be there. That is how the wrapper has always
chosen a Python and this version does not change it.

## 4.3.2 - The card's true size, and a registry manifest on the current schema

A patch version. Every program that compiled under 4.3.1 compiles, runs
and means the same; nothing is added to the language, the capability
surface or any document format. Three documents were wrong about a
number, and one integration file was written against a schema that has
since been replaced.

**The language card is 3,682 words, and now says so.** Eight places
described its size and none of them were right: `README.md` said 3,300
words in two places, and `EMBEDDING.md`, `velaris_mcp.py` (twice),
`mcpb/manifest.json` and the CrewAI and LangChain tool descriptions all
said about 2,300. The card is generated from `LLM.md`, which has grown
with the language - `Money of CUR` arrived in 4.3 - and the figures were
last touched when it was smaller. Measured from `velaris card` output:
3,682 words in all, 2,537 outside the code blocks. Every one of those
places now says about 3,700. This matters more than a documentation
nit, because two of them are tool descriptions a model reads when
deciding whether to fetch the card at all.

**The MCP registry manifest is on the registry's current schema.**
`integrations/mcp_registry/server.json` was written against
`2025-07-09`, which the registry has replaced with `2025-12-11`. Five
fields were renamed under it - `version_detail.version` to `version`,
`registry_name` to `registryType`, a package's `name` to `identifier`,
`runtime_hint` to `runtimeHint` and `package_arguments` to
`runtimeArguments` - a `transport` object became required, and
`description` is now capped at 100 characters, which the old one
exceeded at 167. The file is now validated against the published schema
rather than by eye.

**A `mcp-name:` marker in `README.md`.** The registry proves that a
PyPI package and the server entry claiming it have the same owner by
looking for `mcp-name: <server name>` in the package's description -
which is this README, as published to PyPI. Without it the registry
refuses the entry. It is an HTML comment at the top of the file, so
nothing renders, and there is a note beside it saying what removing it
would break.

**The npm package says what the compiler is.** `npx velaris-lang`
without `pip install velaris-lang` fell back to a fully interpreted run
with no prover and said so in one line that was easy to miss, so anyone
arriving through npm got the slow path and no proofs without knowing
there was another. `npm/README.md` now has a section on it: the
compiler is a Python package, `pip install "velaris-lang[full]"` adds
z3 and llvmlite, and what each of those buys.

## 4.3.1 - A discount that cannot go negative, and a timeout that says it timed out

A patch version. Every program that compiled under 4.3.0 compiles, runs
and means the same; nothing is added to the language, the capability
surface or any document format.

**A proof that runs out of time now says it ran out of time.** This is
the part that mattered. Z3 answers `unknown` for two unrelated reasons:
the question is outside what it decides, or the clock ran out. Until now
Velaris treated both the same way - it abandoned the proof and fell back
to the runtime check, silently. For `examples/fp_proof_bad.vel`, whose
refutation takes about fifteen seconds against what was a thirty-second
budget, a busy machine could therefore produce this:

    $ velaris check examples/fp_proof_bad.vel
    examples/fp_proof_bad.vel: ok - 2 function(s), 0 with proven promises
    $ echo $?
    0

which is exactly what a clean file looks like. It caused one false alarm
here, and it is the worst failure this compiler can have: a lost
refutation reading as a clean bill of health. The distinction did not
exist, and now it does. A proof that spends its whole budget without an
answer is **abandoned**, and every report says so in those words:

    note: the proof of 'add_twice' ran out of time after 120s and was
    abandoned - nothing was proven and nothing was refuted, so its
    promises are checked while running instead. This is not 'the prover
    found nothing wrong'. Give it longer with --proof-timeout 240 (or
    VELARIS_PROOF_TIMEOUT=240).

The note goes to stderr from the prover itself, so it appears for
`velaris check`, a plain run, `explain`, `proofs` and the library alike.
Beside it: `velaris check` marks the file `(1 proof(s) abandoned: out of
time, nothing settled)` rather than leaving `ok - ...` to speak for
itself; `velaris proofs --detail` marks the function `[timeout]` rather
than `[runtime]`; `check --strict` fails as before but says the proof was
abandoned, not that the promise could not be proven; the `unproven-
promise` SARIF result says the same; and `velaris explain --json` carries
`proof_timeouts` and a `proof_timeout` flag on each function. An
abandoned proof is **not** written to the proof cache, so the next run
spends the budget again instead of remembering a non-answer.

**The budget for float proofs is 120 seconds, and either budget can be
replaced for one run.** A query about `Float` is decided by bit-blasting
and is slow; everything else finishes in milliseconds. The two defaults
are now 120 seconds with `Float` and 3 seconds without - the second is
unchanged - and `--proof-timeout SECONDS` (accepted by every command; the
flag is taken out of the command line before any command reads it) or
`VELARIS_PROOF_TIMEOUT` replaces both. `velaris.set_proof_timeout()` does
the same from the library. SPEC.md 9.3 states the defaults and requires
an implementation to distinguish an abandoned proof from a settled one;
docs/floats.md shows what it looks like.

The larger budget is a widening of the prover's reach as STABILITY.md
defines it: a float promise that a slower machine abandoned at 30
seconds can now be refuted, so a program that compiled on such a
machine may be refused with E700. Every such program could already
break its promise while running, for the input the refutation names.

check_library.py adds seven cases for it, made deterministic with
`--proof-timeout 0.2`: that the words appear, that they say explicitly
this is not a clean result, that the flag is named, that `check`,
`proofs --detail`, `--strict` and the JSON report each mark it, and that
a second run says it again rather than reading a cached non-answer.

**`examples/discount.vel`: a rule the customer wrote, proven before it
runs.** A commerce platform lets each customer write their own discount
rule - a percentage off above a threshold, a flat amount off as well, and
a cap on the two together. The platform cannot read every rule, and no
sandbox can tell it that a rule's arithmetic works: a sandbox stops the
rule reading a file and will happily return a total of minus four hundred
rupees.

Five of five functions prove:

  * `line_total` - a line's quantity times its unit price is not negative
  * `basket_total` - `units_of` over a list of amounts is what they add
    up to, so `ensures units_of(result) == units_of(lines)` is the whole
    of "the total is the sum of its parts"
  * `discount_for` - the discount is never negative, and
    `ensures total - result >= money(0, "INR")`: what is left after it is
    never negative either
  * `total_after` - the payable amount is not negative and not more than
    the basket, from `discount_for`'s promises through a call summary
  * `charged_per_line` - `money.split` again, so the per-line charges add
    up to the payable amount exactly and none of them is negative

The percentage is `percent_of(total, rule.percent, 100, "half_up")`, with
the mode written, because a discount that rounds is a decision. Every
amount is `Money of INR`; the program is pure apart from printing and
runs under `--allow io`.

**`examples/discount_bad.vel`** is the same rule with the last guard
deleted - the one that holds a discount to what the basket is worth. The
cap still holds it to a fixed ceiling, which is not the same thing, and
the program does not run:

    $ velaris check examples/discount_bad.vel
    examples/discount_bad.vel:54: [E700] promise cannot be kept:
    'discount_for' ensures total - result >= money(0, "INR") - proven
    without running the program: rule = Rule(percent: 0, above: 0,
    flat: 2, cap: 1), total = 0 gives result = 1

In paise: a basket worth nothing, a flat discount of two paise held down
to a cap of one, and one paisa handed back anyway. Both files are in
run_tests.py, as RUNS and REJECTED, and both are in `velaris.capabilities`
- `io` only, nothing else. README.md shows the pair.

**The VS Code publish retries, and the job says whether it published.**
The Marketplace answered `Request timeout: /_apis/gallery` on 3.3.0,
3.4.0 and 4.3.0. The step now makes three attempts, waiting 30 and then
120 seconds, treats a publish that landed anyway as a success, and stops
retrying at once if the failure is not an outage (a bad token, a manifest
the Marketplace refuses) - that one still fails the step, because it is
this repository's to fix. A second step, `if: always()`, writes one line
to the job summary saying PUBLISHED or NOT PUBLISHED and why, so the job
is read rather than remembered and ignored. It stays
`continue-on-error`, so a Marketplace outage still cannot fail a release.

## 4.3 - Money, which is not a float

A minor version, and an additive one: every program that compiled under
4.2 compiles, runs and means the same.

A currency amount is not a real number. A `Float` cannot hold 0.10, so a
premium, a claim or a settlement computed in floats is wrong in a way
that compounds quietly and is never signalled. Velaris already proves
things about whole numbers honestly; an amount is now a whole number
with a currency, and it proves the same way.

**The type.** `Money of INR` is an exact amount in **minor units** -
paise, cents, fils - held as a 64-bit `Int`, with the currency part of
the type (SPEC.md 4.3). One way to write one:

    money(1250, "INR")           // 12.50 rupees, as 1250 paise

There is deliberately no `from_major(12, 50, "INR")` or `rupees(12, 50)`
beside it: a major/minor pair is ambiguous for a currency with three
digits after the point and meaningless for one with none, and
`parse_money("12.50", "INR")` already reads the human form. `units_of(m)`
gives the minor units back, and `with_units(m, n)` makes an amount of
`n` units in the currency of `m`, which is how code generic in a
currency builds one.

**Currency is part of the value, and of the type.** Adding INR to USD is
a compile error (E550), not a surprise while running, and so is
comparing them, putting both in one list, or passing one where the other
is declared. There is no conversion builtin: converting needs a rate and
a rounding policy, and both are a program's decisions. A function can be
generic in a currency - `fn fee(m: Money of C) -> Money of C for any C` -
and the currency is then whatever the call site's amount has.

**Arithmetic.** Amounts in one currency add and subtract; an amount
multiplies by an `Int`. An amount times an amount is a type error
(E501), an amount and a `Float` never meet (E501), and an amount past
64 bits stops the program with E407, exactly as an `Int` does.

**Rounding is never implicit.** `/` and `%` on an amount are refused
(E553, a new code), because both would round without saying how. Where
a result can fail to come out even, the mode is a required argument,
written in the call:

    percent_of(amount, numerator, denominator, "half_up")
    divide_or_fail(amount, by, "half_even")        // can fail

`"half_up"` takes a half away from zero, `"half_even"` to the even
neighbour, `"down"` toward zero; anything else, or a mode held in a
variable, is E552. There is no default. `percent_of` multiplies before
it divides and is exact in between however large that product; only its
answer must fit in 64 bits. A denominator of zero is E403 while running,
or E706 where the prover can show it. `divide_or_fail` fails catchably
on zero and on an answer too large to hold, and joins the fallible
builtins, with `parse_money`.

**Splitting, with the sum proven.** `money.split(amount, ways)`, in the
new `stdlib/money.vel`, gives `ways` parts that add up to the amount
exactly, the remainder distributed one minor unit at a time, largest
part first:

    import "money.vel" as money
    let parts = money.split(money(1000, "INR"), 3)   // 334, 333, 333

It is written in Velaris, not in the compiler, so that the code that
runs is the code the prover proves - with your program, every time you
compile it. Its promises, all **proven**: as many parts as asked; the
parts add up to the amount exactly; and no part is negative when the
amount is not (nor positive when the amount is not). A negative amount
gives the negated parts of the positive one, so a charge and its refund
cancel party by party rather than leaving one party a unit up. It is
`money.split` and not `split` because `split` is already the text
builtin; the file is imported with a name, as `dates.vel` and `csv.vel`
are.

**Text.** `text_of(m)` writes the code and then the amount with exactly
as many digits after the point as the currency has minor units: `INR
12.50`, `JPY 1250`, `KWD 1.250`, `INR -0.05`. `to_text`, `print` and
`format` agree with it, and `json_of` writes an amount as its currency
and its units, never as a JSON number with a point. `parse_money(text,
"INR")` reads back what `text_of` wrote, with or without the code and
with fewer digits after the point, and fails on everything else -
including a text with more digits than the currency has, which would
have to round.

**The currency table is small, and says so.** `CURRENCIES` in
`velaris.py` holds 21 codes with their minor-unit counts (2 for INR and
USD, 0 for JPY and KRW, 3 for KWD, BHD, JOD and OMR). It is **not
exhaustive**. A currency outside it is refused (E551) rather than
assumed to have two digits, because a wrong minor unit prints and parses
every amount in that currency wrongly. Adding one is a line in that
table with the count ISO 4217 gives it and a case in `check_money.py`;
a program cannot add its own, because two programs disagreeing about a
currency would write the same amount two ways.

**What the prover makes of it.** An amount is its minor units to the
prover - an `Int` - so `ensures result >= money(0, "INR")` is settled
the way `result >= 0` is, at the same speed, with none of the
bit-blasting `Float` needs. `percent_of` is translated as the exact
rounding the interpreter performs, for a denominator shown positive.
What a list of amounts adds up to is a value the prover is told three
true things about - nothing adds up to zero; items all `>= 0` (all
`<= 0`) add up to something `>= 0` (`<= 0`) - and nothing more, so it is
never claimed as a counterexample. `text_of`, `parse_money` and
`divide_or_fail` are not modelled: a function that uses one keeps its
promises as runtime checks, as with the other fallible builtins.

Four promises were asked for by name. All four **prove**, and
`check_money.py` asserts each:

- a total over a list of amounts is non-negative when every item is -
  both as a loop that adds them and, through the facts above, as
  `units_of(xs)`;
- `money.split`'s parts add up to its amount - in `money.vel` where it
  is written, and at a caller through its promise;
- `percent_of` never exceeds its amount for a numerator at most the
  denominator - with the rate written in the call and with the rate
  symbolic;
- a subtraction guarded by a `requires` cannot go negative.

What does **not** prove, stated rather than weakened: a promise that
needs more about a sum than the three facts - anything needing induction
over a list, such as "the total of a list each of whose items is at
least 10 is at least 10 times its length". Such a promise is checked
while running, and `velaris proofs` says so.

**Money is pure.** No new effect, nothing new in the capability surface,
no change to `velaris.audit/1`, `velaris.capabilities/1` or the ratchet.
A program full of amounts and nothing else declares nothing and runs
under any budget; `examples/settlement.vel` runs under `--allow io`.

**A builtin added from 4.3 on gives way to your own function of that
name** (SPEC.md 10.1). `examples/ledger.vel` has had a function called
`money` since 1.13, and a program that defines `money`, `units_of`,
`text_of` or any of the others keeps meaning what it meant; the builtin
is simply not reached there. Inside a library imported with a name the
builtin is always reached, since the library's own functions carry its
prefix. This is what lets a minor version add a builtin at all; the
builtins that existed before 4.3 keep the precedence they had.

**The prover settles one more thing than it did**, which STABILITY.md's
"prover's reach" covers and which is named here: a division whose
divisor mentions a loop's values is now translated when the loop's own
condition and invariants show it positive, where before any such divisor
was left alone. `money.split` needs it - it divides by "the parts still
to make" - and an average computed after a loop gets it too. No verdict
in this repository moved: every function of all 172 `.vel` files here
was compared, before the change and after, and nothing differed -
neither a proof status nor an error code.

**`examples/settlement.vel`** is the demonstration: rows of claims read
and parsed, totalled, a 2.5% fee taken with `"half_up"` named in the
call, the rest split three ways, and the result printed. Five of its
five functions are proven, among them that the parts add up to the
payout and that no party is paid a negative amount. It runs under
`--allow io` and is in `run_tests.py`.

**`check_money.py`** is the new suite: 81 cases covering mixed-currency
arithmetic refused at compile time, an amount times an amount refused,
the 64-bit edges, `split` for 1, 3, 7 and 100 ways and for amounts that
do not divide and for negative amounts and for zero ways, every rounding
mode on a half case in both signs against Python's `decimal` module as
an independent oracle, JPY with no minor unit and KWD with three, text
and parsing round-trips for all 21 currencies, a property test over 200
random amounts and divisors, the four promises above, and the prover's
rounding formulas checked against the interpreter's on 450 cases.

SPEC.md gains sections 4.3, 4.4 and 10.1; LLM.md gains the type, the
builtins, the module and rule 16, which states the three rules a model
gets wrong - no floats, no two currencies, rounding always named;
`docs/floats.md` gains the section that says currency is the case where
the answer is not "be careful with floats" but "do not use them".

## 4.2.1 - The author name, capitalised correctly

A patch version, and a text change only. The compiler, the runtime and
every document format are as in 4.2.0; in `velaris.py` only `VERSION`
changes. Beside the six version files, the README's Action reference,
`velaris.capabilities` and the documentation pages carry the new
version.

The author is Palakurthi Gowri Shankar: family name Palakurthi, given
name Gowri Shankar, with a capital S. 4.2.0 wrote the given name as
"Gowri shankar". Corrected in `CITATION.cff` (`given-names: Gowri
Shankar`), LICENSE, `editor/vscode/LICENSE`, README.md (twice),
SUPPORT.md, MAINTAINERS.md, PROVENANCE.md, `pyproject.toml`,
`integrations/langchain_velaris/pyproject.toml`, `npm/package.json`,
`mcpb/manifest.json`, `packaging/winget.yaml` (`Publisher`; the
`PackageIdentifier` is an identifier and is unchanged),
`paper/velaris.md`, and `paper/references.bib`, still in the comma form
`{Palakurthi, Gowri Shankar}` so that BibTeX reads Shankar as a given
name and not as a particle. velaris-spec 0.5.1 makes the same
correction. The 4.2 entry below keeps the form 4.2.0 used.

**How it renders, checked.** Both `CITATION.cff` files validate against
the CFF 1.2.0 schema, with jsonschema and with `cffconvert --validate`.
`cffconvert` 2.0.0 writes the BibTeX author as `{Palakurthi, Gowri
Shankar}` and its APA-like line as "Palakurthi G.S. (2026)" - "G.S."
where 4.2.0's file gave "G.s."; that writer puts no comma after the
family name and no space between initials, for any name. BibTeX's
`apalike.bst`, run over `references.bib`, writes "Palakurthi, G. S."
and `IEEEtran.bst` writes "G. S. Palakurthi" (the styles from CTAN, run
by pybtex's implementation of BibTeX). A CSL processor, citeproc-js,
writes "Palakurthi, G. S." in APA and "G. S. Palakurthi" in IEEE from
`CITATION.cff`'s names; a citation in the text is "(Palakurthi, 2026)".

**Verified**, on Windows 11 with Python 3.13 and the prover (z3 5.1.0),
with the proof cache cleared first: `run_tests.py` 92/92,
`check_library.py` 196 correct (one skipped: its symbolic-link case is
POSIX only), and `velaris conformance` conformant at L1, L2 and L3, 443
of the 444 cases run and the symbolic-link case skipped because this
machine will not make a link. `velaris capabilities check .` passes
against the regenerated baseline, and velaris-spec 0.5.1's
`tools/validate.py` and `tools/check_sync.py` pass.

## 4.2 - A producer for the capability predicate

A minor version. 4.1 published an in-toto predicate type for the audit
and wrote no Statements of it; `velaris attest` writes them, and the
release workflow signs one. The author's name is corrected everywhere
it appears.

**`velaris attest <path> [--output FILE] [--json]`** writes an in-toto
Statement v1 of the predicate type
`https://gowrishankar-infra.github.io/velaris-lang/capability/v1`
(velaris-spec 0.5, section 8.5). Its subjects are the audited file and
every file it imports, each by the sha256 of its bytes - a standard
library file named `<stdlib>/NAME`, since where it sits on disk is the
machine's business. Its predicate is the published shape: `producer`
(`velaris-lang` and this repository), `specification` (`velaris-spec
0.5`), `auditedAt` - from `SOURCE_DATE_EPOCH` when it is set, so one
commit gives the same bytes twice - and `audit`, which is `audit()`'s
own `velaris.audit/1` document for those bytes, not a copy recomputed
beside it: effects, `fs_paths`, `net_hosts`, `ffi_modules`, `ffi_any`,
`counts`, `proven_share`, `prover` and `velaris_version` are the
audit's. It sets no `conformance` claim, since it runs no corpus. A
directory gives one Statement per `.vel` file, found as `velaris
capabilities` finds them, one to a line (JSON Lines), because the
predicate type holds one audit per Statement. A file that is not UTF-8,
or that changes while it is being attested, is an error (exit 2), not a
Statement. Without `--output` or `--json` it prints a summary: each
file's digest, whether it compiles, its effects, and `ffi_any` when
set. `velaris.attest(path)` in the library returns the Statements as a
list; STABILITY.md adds it to the stable API.

**When the audit cannot tell, the Statement says so.** Two fields are
added to `velaris.audit/1`, optional within version 1 (velaris-spec
8.2), so that an attestation can state what was not determined instead
of leaving it out:

- `counts`: for `fs` and `net`, the most operations one call to a
  function the file defines can perform, by velaris-spec 9.4's rules -
  the same code (`_operation_bounds`) the capability baseline uses. `0`
  for an effect none of them declares; `null` where the text fixes no
  bound, such as a loop over `args()`; and `null` as a whole when the
  file does not compile.
- `prover`: whether a prover decided the promises' status. It is false
  without one, where no status is `proven` and a `proven_share` of 0
  says nothing about what could be proven; and false when the file does
  not compile.

With the fields already there - `ok` false and its problems, `ffi_any`
for a module named while running rather than a shorter module list,
`read_any`, `write_any` and `any` for a path or URL built while
running - the Statement carries whatever the audit could not determine
as the audit states it. EMBEDDING.md's table of audit fields has both.
`load_program` takes an optional list it appends each file it reads
to, which is how `attest` names the imports it digests.

**Signing is left to Sigstore's tools.** Nothing here signs.
EMBEDDING.md gives working commands for cosign 3 (`cosign attest-blob
--statement`, keyless and with a key pair, and `cosign
verify-blob-attestation`, which fails when the file is not the
Statement's subject by digest) and for sigstore-python 4, whose command
line attests only SLSA provenance, so the library's `sign_dsse` and
`verify_dsse` are used. The cosign key-pair commands were run here
against a Statement from this build with cosign v3.0.6, offline - a
signing config naming no transparency log, and `--insecure-ignore-tlog`
to verify: it signed, verified, and refused an edited `effects.vel`
("provided artifact digest does not match any digest in statement").
The sigstore-python snippet was run as far as the browser sign-in,
which needs a person.

**The release signs one.** `release.yml` has a new job, `attestation`:
it installs this commit with the prover, writes `velaris attest
examples/effects.vel` with `SOURCE_DATE_EPOCH` at the commit's time,
signs the Statement keylessly as a DSSE envelope with cosign and with
sigstore-python, verifies both bundles against the workflow's own
identity - cosign against the example's bytes, sigstore-python by
comparing the signed Statement and the first subject's digest - and
attaches `velaris-attestation-X.Y.Z.intoto.json` and the two
`.sigstore.json` bundles to the release. The workflow can also be run
by hand (`workflow_dispatch`); then only this job runs, signing and
verifying under the branch's identity and publishing nothing, and the
jobs that build and publish packages run only for a tag. SECURITY.md
gives the command to verify the attestation.

**Tests.** `check_library.py` gains 12 checks on five programs in a
scratch directory and a two-file program: a directory gives one
Statement per `.vel` file; every digest is the sha256 of the file's
bytes; each predicate's audit equals `audit()` of the same program,
field for field; every Statement validates against in-toto's Statement
v1 schema, the capability/v1 predicate schema this repository
publishes, and velaris-spec's `velaris.audit/1` schema; a module named
while running is `ffi_any`, with an empty module list; a count the text
fixes is its number and one it does not is `null`; a program that does
not compile is `ok` false with its problem, `counts` null and `prover`
false; `prover` matches whether a prover is installed; an imported file
is the next subject, with its own digest; and the command line's
`--json` is the library's Statement, its time fixed by
`SOURCE_DATE_EPOCH`. in-toto publishes its Statement schema as prose and
protobuf, not JSON Schema, so `tests/in-toto-statement-v1.schema.json`
is written from its `statement.md`, `resource_descriptor.md` and
`digest_set.md` at commit `2dcd055e`, which the file names. CI checks
out velaris-spec before the suites run, so `check_library.py` holds the
audit to the spec's schema on every leg.

**velaris-spec 0.5** records the producer in section 8.5 and the two
fields in 8.2 and its audit schema; its `examples/capability-statement.json`
is now what `velaris attest examples/effects.vel` writes at this tag,
and REGISTRY_SUBMISSION.md names the producer, the command that fetches
the signed Statement, and embeds that Statement. Still not submitted.

**The author's name.** The author is Palakurthi Gowri shankar: family
name Palakurthi, given name Gowri shankar. `CITATION.cff` in both
repositories now says `family-names: Palakurthi` and `given-names:
Gowri shankar`, and both validate against the CFF 1.2.0 schema (with
`jsonschema` and with `cffconvert --validate`). The full name replaces
the earlier forms in LICENSE, the VS Code extension's LICENSE,
README.md, SUPPORT.md, MAINTAINERS.md, PROVENANCE.md, pyproject.toml,
the npm, MCP bundle and winget manifests, the LangChain integration's
metadata, `paper/velaris.md` and `paper/references.bib` (as
`{Palakurthi, Gowri shankar}`, the comma form: without the comma BibTeX
would read `shankar` as a particle like "van"), and in velaris-spec's
NOTICE, README.md and REGISTRY_SUBMISSION.md. In a reference list the
family name leads - "Palakurthi, Gowri shankar" in full; abbreviated,
BibTeX writes "Palakurthi, G. s." and `cffconvert`'s APA-like form
"Palakurthi G.s." - and a citation in the text is "(Palakurthi, 2026)".
A CSL processor (citeproc-js) abbreviates only a capitalised given
name, so its APA style writes "Palakurthi, G. shankar".

**Provenance.** Both PROVENANCE.md files record the second pair of
Software Heritage saves, 2471049 and 2471050, taken after the 4.1.0 and
0.4 push, with their snapshots, beside the first pair.

**Sources, named** (CONTRIBUTING.md rule): the parts of this release
were specified by the maintainer. The Statement follows in-toto's
Statement v1 and ResourceDescriptor specifications, and its directory
form the JSON Lines layout of in-toto's Bundle specification, at commit
`2dcd055e`; the signing commands follow cosign's and sigstore-python's
own documentation and were checked against cosign v3.0.6 and
sigstore-python 4.5.0.

**Verified**, on Windows 11 with Python 3.13, with the proof cache
cleared first. With the prover (z3 5.1.0, llvmlite 0.49.0):
`run_tests.py` 92/92, `check_library.py` 196 correct (one skipped: its
symbolic-link case is POSIX only), `check_sandbox.py` 49 (its
symbolic-link case skipped: this machine will not make a link),
`check_fallible.py` 26, `check_refusals.py` 21, `check_termination.py`
44, `check_pool.py` 39, `check_ratchet.py` 114, none wrong;
`fuzz_native.py 30` agrees; `benchmark/run.py --quick --check` matches
`results.json`; `velaris test examples/std_test.vel` 7/7, `velaris
examples/edges.vel` 20/20, `velaris fmt --check` clean, `velaris
capabilities check .` passes; `velaris conformance` reports L1, L2 and
L3 conformant, 443 of the 444 cases run and the symbolic-link case
skipped, and `--level 1`, `--level 2` and `--level 3` each report their
level conformant; `build_conformance.py --check` matches velaris-spec's
corpus. Without the prover, in a fresh virtual environment holding this
tree and jsonschema and no z3 or llvmlite, all of the same pass, with
`check_library.py` 193 correct (two skipped for needing the prover, one
POSIX only) and `check_refusals.py` 11 with 10 skipped for needing the
prover. With the prover and without it, `velaris attest
examples/effects.vel` at a fixed `SOURCE_DATE_EPOCH` writes the same
Statement except `prover`. The audits of the 107 `.vel` files directly
in `examples/` and `stdlib/` (73 compile, with `counts` set and `prover`
true; 34 do not, with `counts` null and `prover` false) validate against velaris-spec 0.5's audit schema through its
`tools/validate.py --audits`, as does this repository's
`velaris.capabilities`; its `tools/validate.py` (schemas, examples, the
example Statement, the 444 cases) and `tools/check_sync.py` pass. Both
`CITATION.cff` files validate against the CFF 1.2.0 schema. The
release workflow's `attestation` job has not run before this commit's
push, so whether it signs and verifies in GitHub's runners is for that
run to say.

## 4.1 - Conformance you can run, provenance you can check

A minor version. Conformance to the capability format stops being a
sentence naming this repository's suites and becomes a corpus any
implementation can run; `velaris conformance` runs it here, on every CI
leg. The project gets citation files, an entry in an independent
archive, and a predicate type whose URL resolves; and a preprint is
drafted, for the maintainer to read. One defect, found by writing the
corpus, is fixed.

4.0.1 was committed and pushed but never tagged, so it was never
published; its fix to `velaris review` ships in 4.1.0.

**The conformance corpus.** velaris-spec 0.4 holds `tests/`: 444 JSON
cases, each with an id, its level, a description, the input - budget
text, Velaris source, a tree of files and a change to it - and the
outcome an implementation must produce: the grants a budget parses to
or its refusal, an audit's effect surface, a refusal and its code, a
baseline, or a verdict with every widening and the rules it fails. 298
cases at L1, declaration (280 budgets, 18 audits); 37 at L2,
enforcement (programs run under a budget, with a fixture of files and
two local HTTP servers); 109 at L3, the ratchet (14 baselines to write,
51 changes to check, two sequences, the writer's guard, and 32
covering, 3 reduction and 6 operation-bound cases). velaris-spec's
CONFORMANCE.md defines the levels and the behaviours each requires, and
says plainly that no level requires a prover; `tests/README.md` is the
runner contract. Five L3 cases are the ratchet's known limits from the
4.0 entry below, recorded with the outcome the check gives today - two
widenings that pass, three non-widenings that fail - so that another
implementation matches it rather than guessing.

The corpus is not written by hand. `build_conformance.py` transcribes
it from tables in three suites, where the same entries are asserted
against this implementation, and computes nothing itself; `--check`
regenerates it and fails when it differs from what velaris-spec
commits. For that, the suites became tables, and asserting them made
them stricter:

- `check_sandbox.py` holds each case as data, with placeholders for its
  paths and ports, and asserts the refusal code each must carry. Until
  4.1 it accepted any of the five codes, so a runtime refusing a path
  outside its prefix with E310 rather than E313 would have passed. It
  runs its fixture in a temporary directory rather than in the
  repository, and its symbolic-link case wherever the system will make
  a link, not only on POSIX. Four cases are new, the four rules
  velaris-spec 0.3 listed as untested (its Q9): `@0`, a count spent by
  an operation that then fails, a URL with no scheme taken as HTTPS, and
  an existence check under a write-only grant. 34 escape attempts and
  16 honest programs.
- `check_library.py` gains `BUDGETS`, 55 budgets each held to what
  velaris-spec sections 4 and 5 say it means - the grants for 51, a
  refusal for 4 - including the spec's own examples and denials (until
  4.1 the awkward ones were checked to round-trip, not for what they
  parse to); and `AUDITS`, 18 programs each held to the effect surface
  its audit must report, and to the schema. The malformed-budget list
  moved out of `main()` so the corpus can be written from it.
- `check_ratchet.py`'s scenarios became `DERIVE`, `CHECKS`, `SEQUENCES`,
  `WRITE_GUARD`, `COVERING`, `REDUCE` and `BOUNDS`. Each check now
  asserts the complete list of widenings, with the rules each fails,
  where most cases asserted one finding; each derivation asserts the
  whole baseline. New: 14 baselines written for trees; the writer
  refusing, unasked, to write a baseline for a tree that needs more; a
  new effect; a new program outside the surface (W1 alone); `fs`
  declared with no file named, which needs plain `fs`; another spelling
  of a path; a port under a portless grant; 9 covering and 2 reduction
  cases; and the five known limits. What only this implementation
  says, such as the call chain, `velaris review`, SARIF and warning
  text, is asserted after, on the same scenarios.

Thirteen scenarios are left out of the corpus, and `tests/index.json`
says why each: six attempts to reach an ungranted Python module through
a granted one, which depend on Python's object model; four honest
programs that need a Python host; a run given no budget, which the
format leaves to the implementation; and two about this command line's
flags.

**`velaris conformance [--level 1|2|3] [--json] [--corpus DIR]`** runs
the corpus against this implementation, through the doors another
implementation would use: the budget parser, the audit, the command
line under a budget, the baseline writer and the check. It finds the
corpus beside the working directory or the installation, prints a line
per level and a one-line verdict, and exits 1 if any case of a level
asked for fails. `--json` is `velaris.conformance/1`, one result per
case, the report shape `tests/README.md` gives any runner. `--level N`
runs the cases a claim at level N needs: L1 and N. A case that needs a
symbolic link is skipped where none can be made, and the verdict says
so; without `jsonschema` the cases that validate a document against
velaris-spec's schemas are skipped too, and the level is reported as
not shown. It passes at all three levels. Run against a copy of the
corpus with twelve expectations broken, covering all ten kinds of case,
and one case given a kind no runner knows, it fails exactly those 13
cases and exits 1.

**CI.** Every one of the twelve legs checks out velaris-spec, runs the
drift test and `velaris conformance` against its corpus. velaris-spec's
own CI runs the drift test and this implementation's conformance
against its corpus, beside its schema and sync checks.

**Found by the corpus, and fixed.** The audit of a program refused for
naming something that is not an effect in a `uses` clause (`uses io,
teleport`, E300) still listed that name in `effects` and in the
function's `effects`, and wrote a `safe_command` that does not parse.
velaris-spec had said since 0.2 that `effects` holds only the seven
names and that `safe_command` always parses; 3.3 had fixed the compile
check and not the document that reports it. From 4.1 `audit` leaves any
name that is not an effect out of all three; the E300 still names it.
This is not a breaking change under STABILITY.md: the fields' documented
meaning is unchanged, and it is the implementation that now matches it;
what changes is the content of a document whose `ok` is false, which
velaris-spec says bounds nothing. HALL_OF_FAME.md credits the corpus.
velaris-spec 0.4 corrects the sentences that had inferred from 3.3's
rejection more than the implementation did.

**Provenance.** `CITATION.cff` in both repositories (CFF 1.2.0, checked
against the format's schema), with the author, the repository, the
version and its date, and a note that a preprint is forthcoming; both
READMEs say "Cite this repository". Both repositories were submitted to
Software Heritage through its save-code-now API, and `PROVENANCE.md` in
each records the save requests' ids and dates beside the first commit
of the effect system, the date velaris-spec 0.1 was tagged, and that
velaris-lang is the reference implementation.

**A resolvable predicate type.** velaris-spec 0.4 section 8.5 defines
an in-toto predicate type for `velaris.audit/1` bound to the digests of
the files audited, and its URL is on this repository's documentation
site: `https://gowrishankar-infra.github.io/velaris-lang/capability/v1`,
which `build_docs.py` now writes, with `schema.json` beside it,
identical to velaris-spec's `schemas/capability-predicate.v1.schema.json`
(velaris-spec's `tools/check_sync.py` fails if they differ).
`velaris.dev` was not used: on 2026-09-11 it answered every path with a
Vercel `DEPLOYMENT_NOT_FOUND`, and nothing here says who controls it.
This implementation publishes the type and does not yet write
Statements of it; velaris-spec's example was assembled from `velaris
audit --json` and a file's digest. A pull request listing the type in
in-toto's predicate registry is prepared in velaris-spec's
REGISTRY_SUBMISSION.md, and not sent.

**A preprint, drafted.** `paper/velaris.md` and `paper/references.bib`:
the problem, the design, the implementation, the evaluation, related
work, limitations and a reproducibility section, with a table naming
the file each number comes from. Not submitted anywhere.

**Also corrected.** The documentation site's benchmark table said
"Velaris 3.1" and the README's did too, where `benchmark/RESULTS.md`
said the table was produced by 3.0.0. The table was regenerated with
4.1.0: every verdict and every line of evidence is what 3.0.0 produced,
and only the version line of `RESULTS.md` and `results.json` changed;
the pages now say 4.1. EMBEDDING.md's table of audit fields lacked
`ffi_any`, added in 4.0. velaris-spec's PRIOR_ART.md said this
implementation emits no SARIF, untrue since 3.4.

**Sources, named** (CONTRIBUTING.md rule): the parts of this release
were specified by the maintainer. The runner contract follows no
published harness. in-toto's `docs/new_predicate_guidelines.md` and
predicate template, read on 2026-09-11, shaped REGISTRY_SUBMISSION.md.
Hills, Caspary and Cooper Stickland, "Distributed Attacks in
Persistent-State AI Control" (arXiv:2607.02514), is cited by the paper
and by velaris-spec's PRIOR_ART.md as the gradual-attack result the
ratchet addresses; the record does not say it influenced the ratchet's
design in 4.0, and this entry does not claim it did.

**Verified**, on Windows 11 with Python 3.13, with the proof cache
cleared first. With the prover: `run_tests.py` 92/92,
`check_library.py` 184 correct (one skipped: its symbolic-link case is
POSIX only), `check_sandbox.py` 49 (its symbolic-link case skipped: this
machine will not make a link), `check_fallible.py` 26,
`check_refusals.py` 21, `check_termination.py` 44, `check_pool.py` 39,
`check_ratchet.py` 114, none wrong; `fuzz_native.py 30` agrees;
`benchmark/run.py --check` over the whole table and `--quick --check`
match `results.json`; `velaris test examples/std_test.vel` 7/7,
`velaris examples/edges.vel` 20/20, `velaris fmt --check` clean,
`velaris capabilities check .` passes; `velaris conformance` reports
L1, L2 and L3 conformant, 443 of the 444 cases run and the
symbolic-link case skipped; `build_conformance.py --check` matches
velaris-spec's corpus. Without the prover, in a fresh virtual
environment with jsonschema and no z3 or llvmlite, the same pass - the
benchmark with `--quick --check` only - with `check_library.py` 181
correct (two skipped for needing the prover, one POSIX only),
`check_refusals.py` 11 with 10 skipped for needing the prover, and
`velaris conformance` again conformant at L1, L2 and L3. velaris-spec
0.4's `tools/validate.py` (schemas, examples, the example Statement,
all 444 cases against the case schema) and `tools/check_sync.py` (the
quoted sections, and the predicate schema against
`docs/capability/v1/schema.json`) pass against this tree. The symbolic-link cases run where a link can be made - the
Linux and macOS runners, and the Windows runners if they allow it -
and whether they pass there is for this commit's CI to say.

## 4.0.1 - The review read the old files from the wrong place

4.0.0's CI failed on its four Windows legs, in `check_ratchet.py`: the
five checks that go through `velaris review` failed. The capability
check - the gate - passed every one of its cases on all twelve legs.

The cause was in `review`. To find where the checked directory sits in
the repository, it compared the working directory's path with the path
`git rev-parse --show-toplevel` prints, as text. On the Windows runners
the temporary directory is a short name (`C:\Users\RUNNER~1\...`) and
git prints the long one, so the two did not match, and the files at the
ref were materialised and read from a directory that was not the ref's
place in the tree. The review then reported the surface as widened, or
as unchanged, whatever the change was. `review` now asks git where it
is (`git rev-parse --show-prefix`) and compares no paths. The same
mismatch happens wherever the path to a checkout goes through a link or
junction, on any system.

The 4.0.0 entry's "Verified" paragraph was true of the machine it
names, from a path git spells the same way, and was not true of the
Windows runners. `check_ratchet.py` gains a case that runs `review`
from a junction (Windows) or a symbolic link (elsewhere) to a
repository whose working tree needs more than its last commit, and
requires the review to see it: the case fails against 4.0.0 and passes
now. 63 checks.

Affected: `velaris review`, and the review section of the Action's
pull-request comment, on a machine where the two paths differ.
`velaris capabilities init` and `check` were not affected, and neither
was anything else in 4.0.0. This repository's `velaris.capabilities` is
recorded again under 4.0.1; only its `velaris_version` changed.

**Verified**, on Windows 11 with Python 3.13, with the proof cache
cleared first; the new case fails against 4.0.0's `velaris.py` and
passes against this one. With the prover: `run_tests.py` 92/92,
`check_library.py` 165 correct (one skipped, POSIX only),
`check_sandbox.py` 45, `check_fallible.py` 26, `check_refusals.py` 21,
`check_termination.py` 44, `check_pool.py` 39, `check_ratchet.py` 63,
none wrong; `fuzz_native.py 30` agrees, `benchmark --quick --check`
matches, `velaris test examples/std_test.vel` 7/7, `velaris fmt
--check` clean, `velaris capabilities check .` passes. Without the
prover, in a fresh virtual environment with no z3 or llvmlite: the same
thirteen pass, `check_library.py` 162 correct (two skipped for the
prover, one POSIX only) and `check_refusals.py` 11 with 10 skipped.
Whether the Windows runners agree is for this commit's CI to say.

## 4.0 - The operator sets the limits, and the capability surface cannot widen quietly

This is a major version. Two gaps 3.4 left open on the doors are
closed, which changes what a door started without flags will grant;
the project's stability policy is written down for the first time,
with the record of the times it was broken; and a repository can now
declare the capability surface its programs may have and have CI fail
any change that widens it.

**The operator sets the limits, not the caller.** On the HTTP door and
the MCP server a request's `timeout` and `max_memory_mb` were whatever
the caller sent; the 30 seconds and 512 MB the doors have had since
2.59 were only the values used when a caller sent none. **Before 4.0 a
caller could exceed them, by asking.** Both doors now take
`--max-timeout` and `--max-memory-mb`, 30 seconds and 512 MB when the
flags are absent. A request that names neither gets the ceiling; one
that asks for less gets less; one that asks for more is refused the way
an over-wide budget is - 403 from the HTTP door, `isError` from the MCP
server - with the ceilings named in the body (`max_timeout`,
`max_memory_mb`, beside `max_allow`), and logged with outcome
`ceiling`. A value that is not a number above zero - text, `true`,
zero, a negative, a fraction of a MB - is a bad request. A flag value
that is not a limit stops the door at start. `GET /health` with the
token reports all three ceilings. The rule lives in one place,
`velaris.run_limits`, used by both doors.

**The HTTP door's default ceiling is `io`.** Without `--max-allow`,
`velaris serve` granted every effect, `ffi` included, to anyone holding
the token; the MCP server has defaulted to `io` since 3.4. The door now
does too, and starting it wider takes naming the grants:
`--max-allow io,env,fs,net,clock,rand,ffi` is what 3.4 granted by
default. Its start-up lines say which ceiling is the default.

One more change came with the flag: `velaris serve --max-memory-mb`
was accepted before, and - through the command line's process-wide
`--max-memory-mb` - set an address-space cap on the door's own process
on Linux and macOS, never documented. It is now the most each run may
have, and the door's process is not capped.

**STABILITY.md.** What semantic versioning covers here - the language
as SPEC.md states it, the error codes, `velaris.audit/1`, the library
API, the budget grammar, the command line's commands and documented
flags - and what it does not: internals, the proof cache, the wording
of messages, which promises happen to prove, the formatter's style,
anything marked provisional. The rules: breaking changes only in a
major version, security fixes included; a deprecation announced in a
minor version, warning for at least one more, removed no sooner than
the next major; an error code never reused for another meaning, and a
removed one kept listed as removed (`REMOVED_ERRORS`, and a section on
the errors page - empty today). A stronger prover refusing a program
its proof shows wrong is stated as the one exception, and why.

Its "Breaks we have made" section is longer than expected when it was
begun. 2.0 and 3.0 broke in major versions, as promised. **3.4 shipped
three breaking changes in a minor version and named them as such, and
it should have been 4.0**; it was not retagged because 3.4.0 was
already published, and this policy exists so that it does not happen
again. Reading every entry for STABILITY.md found more: 3.4 broke three
further things it did not list (`serve` and the MCP server refusing an
unknown argument, `GET /health` without the token no longer naming the
ceiling); 3.3 shipped five breaking changes as fixes and named none;
and eight earlier minor releases, 2.20 to 3.1, each broke something -
64-bit integers, the formatter's style, three builtins made fallible,
the http module's `call`, `audit().problems`, the doors' 2.59 limits,
`args()`, Windows memory caps. E610 was reused, in 2.59, for a meaning
other than the one 1.4 gave it. All of it is listed there, and 2.0 is
recorded as its entry and commit describe it: four builtins made
fallible. README and CONTRIBUTING link it; SPEC.md section 15 points
to it.

Also corrected: the 3.3 entry of this file lost its heading in the 3.4
release, so its text read as part of 3.4. The heading is restored.

**The capability ratchet.**

    velaris capabilities init [path]          # write velaris.capabilities
    velaris capabilities check [path]         # exit 1 if the surface widened
    velaris review --against <ref> [path]     # a pull request's delta, as facts

A change can add capability to a repository a little at a time - a
helper that builds a URL, a function that reads a file, a call three
levels down that sends one to the other - and no single diff looks
alarming, which is how such a change passes a reviewer and a
diff-based monitor. Capability is binary and cumulative, so the steps
add up to exactly what one large step would have done; but only a
comparison with a declared baseline sees the sum. This release makes
that comparison, and makes it the only one the gate uses.

- **`velaris capabilities init`** reads every `.vel` file under the
  path, except in `.git` and what git ignores, and writes
  `velaris.capabilities` (`velaris.capabilities/1`, velaris-spec 0.3
  section 9): the repository's surface - every grant its programs need,
  in the budget grammar, and for `fs` and `net` the most operations one
  run can perform, or `null` where the text sets no bound - and for each
  program its own grants and counts and the effects each of its
  functions declares, or that it does not compile; with the Velaris
  version and the date. One grant per line and one function per line,
  so accepting a widening is a one-line diff. It refuses to replace an
  existing file without `--force`.
- **`velaris capabilities check`** derives the same from the working
  tree and compares it with the file - never with the previous commit -
  and exits 1 when anything widened: a grant the surface does not cover
  (a new effect, a new module, a path outside every recorded one, so
  `./data` widened to `./` fails; a host, so `api.example.com` made
  `*.example.com` fails; a scoped grant made unscoped); more `fs` or
  `net` operations in a run than recorded (10 raised to 1000 fails); a
  program the file records needing something its own entry does not
  give, even when another program already had it; and a function the
  file records gaining an effect, even when its program's grants and
  counts stay the same. Narrowing never fails and is reported. A new
  program is held to the surface alone. Each widening names what
  widened, the file, function, line and call that introduced it, the
  chain of calls from `main` that reaches it, and the edit to the file
  that would accept it. A baseline from another Velaris version is
  compared with a warning, not a failure. A baseline that is missing,
  is not `/1`, or does not read exits 2 and never passes. `--json` is
  `velaris.capabilities-check/1`; `--sarif` reports each widening as an
  error at its line, through the 3.4 SARIF code, with two new error
  rules, `capability-widened` and `capability-effect-gained`, and a
  note, `capability-narrowed`, on the errors page.
- **What a program needs** is read from its text: the effect and type
  checks run and the prover does not, so the result is the same with
  and without z3. A path, URL or module is taken as named when it is a
  literal or a variable bound once to one; one built while running is
  recorded as the unscoped grant, which a scoped baseline does not
  cover. The operation bound comes from loops whose counter and limit
  the text fixes - `for i in 0 to 10`, a counter started by `let`, a
  list literal - multiplied through nesting and calls; a loop the text
  does not bound, and recursion, have none.
- **`velaris review --against <ref>`** runs the derivation and the
  audit on the files at a git ref - read with `git show <ref>:<path>`,
  nothing checked out - and on the working tree, and reports whether
  the capability surface changed, the proven share before and after,
  functions that became fallible, hosts, paths and modules newly named,
  whether `velaris.capabilities` itself changed, and one word of risk
  computed from those facts alone: `high` when the surface widened, or
  the declared surface widened or was removed; `medium` when it did not
  but a program or function the ref had came to need more, or the
  proven share fell; `low` when nothing widened and the proven share
  did not fall. No count of changed lines enters it. It informs a
  reviewer; the gate is `check`, since a review against the commit
  before loses a widening the moment it is merged.
- **The GitHub Action** has a `capabilities` input, `check` by default
  when `velaris.capabilities` exists and `off` otherwise - except that a
  pull request deleting the file fails, since that would turn the
  ratchet off; `capabilities: off` in the workflow is the visible way to
  do that. Its findings are uploaded to code scanning beside the check's
  when `sarif` is on. The pull-request comment from 2.63 now holds the
  ratchet's result, each widening with the edit to the baseline that
  would accept it, and the review delta against the pull request's
  base.
- **This repository commits its own `velaris.capabilities`**, written by
  `velaris capabilities init .`: 172 programs, 22 of them examples and
  benchmark rows built to be refused, recorded as not compiling. CI runs
  `velaris capabilities check .` on every leg.
- **`velaris.audit/1` gains `ffi_any`**, added within version 1: true
  when some Python call names its module with a value built while
  running, which `ffi_modules` cannot list. The ratchet needs it - a
  computed module name must not slip past a baseline naming `ffi:math`
  - and it closes velaris-spec's open question Q4. The audit also warns
  when it is true.

**`check_ratchet.py`**, 62 checks, proves the rules rather than
asserting them, through the command line in scratch trees and real git
histories. The gradual case: six commits, the first five adding pure
helpers, a text constant holding a URL and a call to print, each
passing against the baseline, and the sixth sending a summary to that
URL through a helper three calls below `main` - which fails, naming
`net:collector.example.net` as a new effect, `lib/deliver.vel` line 2
in `send`, and the chain `main -> summary -> deliver -> send`, while a
review of each commit against the one before calls the first five
`low`. Why the gate must be the baseline: a count widened and merged
anyway keeps failing the check at every later commit, while a review
against the previous commit reports nothing one commit later; and seven
steps from 10 to 1000 are reported as 1000 against the declared 10,
where the previous commit shows 640 to 1000. Widenings through an
import (the surface unchanged, the program's entry not), through the
standard library, through a path prefix, a count, a wildcard host, a
URL, path and module built while running, a new module, a new
direction, a hidden directory, and a program whose `main` is imported
from outside the tree. An effect added to a function whose program's
grants and counts stay exactly as they were, reported. And the changes
that must pass: narrowing; reordering functions, imports, `uses`
clauses and statements, renaming locals, reformatting and `velaris
fmt`; a file with no effects; a new program inside the surface; a
literal moved into a variable; a function renamed or moved to another
file; a program that stops compiling. Declared prefixes, wildcards and
ports; a baseline from an older and from a newer version (a warning
that never hides a widening); `init` without `--force`; four baselines
that cannot be read (exit 2); the JSON and the SARIF, which validates;
23 covering cases and 6 operation-bound cases. CI runs it on every leg.

**What the ratchet cannot do, and the cases where one of the two rules
was not achieved.** A widening never passes and a non-widening change
never fails, among the changes `check_ratchet.py` holds; beyond them,
these are the known limits, each stated in THREAT_MODEL.md:

- *A widening that passes:* a function renamed in the same change that
  gives it an effect is a new function, held to its program's entry and
  the surface but not to what its old name declared - so a pure helper
  renamed while it gains an effect its program already had is not
  reported as a function that gained one. What a granted `ffi` module
  does is outside the text. A symbolic link under a recorded directory
  is that directory's content.
- *A change that does not widen, reported as one:* the bound on
  operations comes from fixed rules, so a loop bound moved behind a
  function call (`for i in 0 to limit()`) loses its bound and is
  reported as unbounded; a path or URL passed to a helper as a
  parameter is taken as unscoped, as it always is, even when every
  caller passes a literal; and a path written with `\` is covered only
  by the same text.

**What a 3.4 user has to change.**

1. A client of `velaris serve` that relied on the door granting more
   than `io` without `--max-allow` must start the door with
   `--max-allow` naming what it needs.
2. A client of either door that sends a `timeout` over 30 seconds or a
   `max_memory_mb` over 512 must have the operator raise
   `--max-timeout` or `--max-memory-mb`, or ask for less.
3. A client that sends `timeout` or `max_memory_mb` as text (`"30"`),
   or `0` to mean the default, must send a number, or leave the field
   out.
4. An operator who passed `--max-memory-mb` to `velaris serve` to cap
   the door's own process gets a per-run ceiling instead; cap the door
   with the operating system (`ulimit -v`, a container limit) if that
   was the intent.

Additions, which break nothing: `velaris capabilities`, `velaris
review`, the Action's `capabilities` input (off unless the file
exists), `ffi_any`, and the new SARIF rules.

**velaris-spec 0.3.** Section 9 stops being provisional:
`velaris.capabilities/1` replaces the provisional `/0`, which no
version of this compiler wrote. The spec states the document, the
derivation from a program's text, the operation bound, the covering
rule (a path holding `\` now compared whole), and the comparison as
five rules, W1 to W5, with a table of what widens for each kind of
scope - effect, path, host, module, count, function - and the rule that
a check compares with the baseline and with nothing else. Q4 is
resolved by `ffi_any`. Its conformance section adds `check_ratchet.py`.
It still quotes this repository's SPEC.md sections 6, 7 and 7.1 word
for word - none of them changed - so its drift check passes; its CI now
also validates this repository's `velaris.capabilities` against the
`/1` schema.

**Sources, named** (CONTRIBUTING.md rule): the four parts of this
release were specified by the maintainer. No published work is on
record as the source of the ratchet's design, so none is named. The
CHANGELOG scan behind STABILITY.md's record was made in this release,
and its findings were checked against the entries and against git
history (E610's two meanings are in commits `616579f`, `79808fc` and
`b5a4582`).

**The MCP manifest changes, by design.** `velaris_run`'s description
and the descriptions of its `timeout` and `max_memory_mb` inputs now
name the ceilings, so the signed `velaris-mcp-tools-4.0.0.json` differs
from 3.4.0's: `velaris mcp-verify` against a 3.4.0 manifest reports
`velaris_run` as CHANGED, which is what it is for.

**Verified**, on Windows 11 with Python 3.13, before tagging, with the
proof cache cleared first. With the prover: `run_tests.py` 92/92,
`check_library.py` 165 correct (one skipped: the symlink case is POSIX
only), `check_sandbox.py` 45, `check_fallible.py` 26,
`check_refusals.py` 21, `check_termination.py` 44, `check_pool.py` 39,
`check_ratchet.py` 62, none wrong; `fuzz_native.py 30` agrees,
`benchmark/run.py --quick --check` matches `results.json`, `velaris
test examples/std_test.vel` 7/7, `velaris fmt --check` clean, and
`velaris capabilities check .` passes on the clean tree. Without the
prover, in a fresh virtual environment holding this tree, jsonschema
and no z3 or llvmlite: the same thirteen pass, with `check_library.py`
162 correct (two skipped for needing the prover, one POSIX only) and
`check_refusals.py` 11 with 10 skipped for needing the prover. Every
workflow file and `action.yml` parse as YAML. The Action's new steps
were run outside GitHub as far as they go: the ratchet step under Git
Bash in four cases (no baseline, off; a baseline and nothing widened,
pass; `clock` added, fail naming it; a pull request deleting the
baseline, fail), and the comment's Python against real `capabilities
check --json` and `review --json` output. `velaris review --against
HEAD` over this repository took 45 s with the prover. velaris-spec
0.3's `tools/check_sync.py` passes against this tree, its
`tools/validate.py` passes with `--capabilities` on this repository's
`velaris.capabilities`, and the `velaris.audit/1` documents 4.0.0
produces for all 109 files in `examples/` and `stdlib/` validate
against its audit schema, `ffi_any` included.

## 3.4 - The doors are locked, and the findings go where findings go

`velaris serve` ran any program sent to it by anyone who could reach
its port; binding to localhost and printing a warning was the whole of
the control. The MCP server granted whatever budget its caller asked
for, `ffi` included. Neither door recorded what it was asked to do, and
nothing let a client operator tell whether the MCP server's tool
descriptions were the ones that were released. This release adds the
four controls, and SARIF output so findings reach code scanning.

- **Bearer authentication on the HTTP door.** Every endpoint but
  `GET /health` needs `Authorization: Bearer <token>`. The token comes
  from `--token-file <path>`, else `VELARIS_TOKEN`, else the door makes
  one with `secrets.token_urlsafe(32)` and prints it once. It is never
  read from the command line: `--token`, in either spelling, is refused
  at start, and the refusal does not repeat the value. Tokens are
  compared with `secrets.compare_digest` over sha256 digests; a missing
  token, a wrong one, another scheme, a bare `Bearer` or the token in a
  query string all get the same 401 body and a bare
  `WWW-Authenticate: Bearer` challenge, on every path including unknown
  ones, so nothing is learned about the door without the token. The
  door removes `VELARIS_TOKEN` from its environment before any worker
  starts, so a program granted `env` cannot read it. `GET /health` no
  longer names the ceiling to a caller without the token.
- **`--no-auth`**, for local development, is refused unless `--host` is
  `127.0.0.1` or `localhost`, and prints a warning on every start. In
  its place a request must name a loopback `Host`, carry no other
  `Origin`, and post as `Content-Type: application/json`, which keeps a
  web page in a browser on the same machine (a cross-site `fetch`, or a
  DNS-rebinding page) from sending the door programs. It does not stop
  another local program, and the warning says so. These three checks
  were not in the request for this release; without them `--no-auth`
  would have let any open web page run programs.
- **The door refuses arguments it does not know**, so `--max-alow io` is
  an error instead of a door whose ceiling silently stayed at every
  effect. A non-local `--host` now also warns that the door speaks
  plain HTTP and the token crosses the network in clear without a TLS
  proxy in front. The `Server` header no longer carries the Python
  version.
- **A ceiling on the MCP server.** `--max-allow` takes the grammar the
  HTTP door takes - effects, `fs:read:`/`fs:write:` paths, `net:` hosts
  and ports, `ffi:` modules, `@N` counts - and the same `Budget.covers`
  check. A `velaris_run` asking for more at any level is refused with
  `isError` and the body the HTTP door sends with its 403: what was not
  granted, and `max_allow`. **Without the flag the ceiling is `io`**,
  and `velaris_run`'s description and the `.mcpb` manifest say so. A
  ceiling that does not parse, or an unknown argument, stops the server
  at start.
- **A signed manifest of the MCP tools.** The release workflow asks the
  MCP server inside the wheel it publishes for its tools, writes
  `velaris-mcp-tools-X.Y.Z.json` (`velaris.mcp-tools/1`: each tool's
  name, the sha256 of its description, the sha256 of its input schema
  in canonical form), signs it with sigstore alongside the wheel, sdist
  and SBOM, checks the signed manifest against the server with
  `velaris mcp-verify`, and attaches both to the release.
  `velaris mcp-verify <manifest> -- <server command>` verifies the
  signature as this workflow at the manifest's tag, starts the server
  the way a client does, and reports every tool whose description or
  schema changed and every tool added or missing (exit 1), or why it
  could not check (exit 2). It lives in `velaris.py`, not in the server
  file it checks. `velaris mcp-manifest` makes a manifest for any
  server. EMBEDDING.md says how a client operator uses it and what it
  does not tell them.
- **Invocation logging on both doors.** One JSON line per call,
  `velaris.invocation/1`: when the call arrived, the door, the endpoint
  or tool, the outcome, the duration, the budget granted, the effects
  performed, what was refused and by what, the caller's address (HTTP),
  and the sha256 of the source - never the source, the output, request
  headers, the path as sent, or the token, which is also struck out of
  any line it could appear in. To stderr, or appended to `--log-file`;
  `--log minimal` keeps six fields, and nothing turns the log off.
  "Effects performed" is new in the runtime: `RunResult.effects_used`
  counts, per effect, the builtin calls the budget let through; it
  comes back from the pool workers the doors use, and is `None` for a
  child that could not report it.
- **SARIF 2.1.0.** `velaris check --sarif`, `proofs --sarif` and
  `audit --sarif` write one run whose driver is `Velaris` at this
  version, with a rule for every code in the compiler's error table and
  for each finding that is not an error, each rule linking to its row
  on the published errors page. Results carry the file, the line and
  the message. Errors are `error`; a promise left to runtime is a
  `warning` (an `error` under `--strict`); a function promising nothing
  about its data, a loop not shown to end and each effect a function
  may perform are `note`. The output is validated against the OASIS
  schema, vendored under `tests/` and held to its digest, in
  `check_library.py`. The GitHub Action has a `sarif` input, true by
  default, that writes the file and uploads it with
  `github/codeql-action/upload-sarif` pinned to the v4.38.0 commit.
- **What SARIF output leaves out.** A Velaris fix is a sentence; a
  SARIF `fix` must carry the exact bytes to change (`artifactChanges` is
  required by the schema). Rather than make up an edit to fill the
  slot, the suggestions go in each result's `properties.fixes`. Figures
  with no line - a proven share, an audit's `safe_command` - go in the
  run's property bag, the latter as each file's `velaris.audit/1`
  document unchanged.
- **The error table.** `velaris.ERROR_TABLE` holds all 62 codes the
  compiler, runtime and library can give, one line each; the published
  errors page and the SARIF rules are both built from it, and
  `check_library.py` reads `velaris.py`'s syntax tree and fails if a code
  is given anywhere that is not in the table, or is in the table and
  given nowhere. The page used to be a scrape of `VelarisError(...)`
  calls and missed E610, E611 and E612, which are reported another way;
  it now lists all 62, with an anchor on each row.

**What a 3.3 user has to change.** README's stability rule is that
breaking changes wait for a major version; these three ship in a minor
version because each closes an open door, and they are listed here so
nobody meets them by surprise:

1. A client of `velaris serve` must send `Authorization: Bearer
   <token>`. Start the door with `--token-file` or `VELARIS_TOKEN`, or
   read the made token from its first lines of output.
2. An MCP client that relied on `velaris_run` granting more than `io`
   must start the server with `--max-allow`, as EMBEDDING.md shows.
3. A workflow using the Action needs `permissions: security-events:
   write` for the upload, and code scanning enabled on a private
   repository - or `sarif: "false"`.

THREAT_MODEL.md did not, in fact, list the unauthenticated door
anywhere, as a residual risk or otherwise; it now has the door and the
MCP server's caller in the trust boundary, the four controls in what is
defended, what they do not defend in the list of what is not, and
residual risks for the token, the ceiling, the tool manifest and the
log. COMPLIANCE.md maps the four controls to OWASP MCP Top 10 (v0.1,
beta) items MCP01, MCP02, MCP03, MCP07 and MCP08.

**Verified**, on Windows 11 with Python 3.13, before tagging, with the
proof cache cleared first. With the prover: `run_tests.py` 92/92,
`check_library.py` 142 correct (one skipped: the symlink case is POSIX
only), `check_sandbox.py` 45, `check_fallible.py` 26, `check_refusals.py`
21, `check_termination.py` 44, `check_pool.py` 39, none wrong;
`fuzz_native.py 30` agrees, `benchmark --quick --check` matches
`results.json`, `velaris test examples/std_test.vel` 7/7, `velaris fmt
--check` clean. Without the prover, in a fresh virtual environment
holding this tree, jsonschema and no z3 or llvmlite: the same eleven
pass, with `check_library.py` 139 correct (two skipped for needing the
prover, one POSIX only; the SARIF output validates there too, and
`check --strict --sarif` reports that it could not check rather than
passing) and `check_refusals.py` 11 with 10 skipped for needing the
prover. Every workflow file and `action.yml` parse as YAML.
velaris-spec's `tools/check_sync.py` and `tools/validate.py` pass
against this tree; SPEC.md §6, §7 and §7.1, the grant grammar and
`velaris.audit/1` are unchanged, so the spec stays at 0.2. The new
release steps were run by hand as far as they go without GitHub's
signing identity: the wheel was built, installed in a clean
environment, `mcp-manifest` made the manifest from its server, and
`mcp-verify --skip-signature` matched 4 of 4 tools; the signature check
itself was run against the sigstore bundle this workflow made for the
3.3.0 SBOM, accepting it and refusing it for changed bytes and for the
wrong tag.

## 3.3 - The capability check now means what the spec says

(This heading was lost from this file in the 3.4 release and restored
in 4.0; the text below it is unchanged.)

velaris-spec 0.1 was extracted from 3.1.1 and, in writing each rule down
precisely, found five places where this compiler did not do what the
format says. 3.2 recorded them and changed no compiler code. 3.3 fixes
all five, and velaris-spec goes to 0.2 in step, resolving the open
questions the fixes close.

- **`ffi:M` is bounded to the module a call actually reaches, not just
  the one it names.** The function argument of `py`, `py_int`,
  `py_float`, `py_json` and `py_new` may be a dotted path of attributes,
  and a granted module's attributes include the modules it imported. So
  `py("json", "codecs.encode", ...)` ran codecs code under `ffi:json`,
  because `json` imports `codecs` into its namespace and the chain walked
  straight into it. The whole dotted path a call names is now checked:
  the attribute chain is resolved step by step, and whenever a step
  yields an object whose owning module (a module's own name, or an
  attribute's `__module__`) has a top-level package outside the grants,
  the call is refused with E311 naming the module actually reached. The
  same check applies to a method or field reached through a handle
  (`py_do`, `py_field`) and to a non-JSON result kept as a handle. Where
  the owning module of an object reached along the chain cannot be
  determined - a bare code object, a frame, a reflective handle - the
  call is refused rather than allowed: the bound errs toward refusing
  more. Inert data (numbers, text, bytes, lists, maps) is not code from
  any module and is not checked, so a legitimate deep attribute like
  `json.decoder.JSONDecoder` still works. This is a security fix; where
  the chain cannot be placed soundly it refuses, and THREAT_MODEL.md and
  the spec say what remains reachable: a granted module can still do
  whatever that module itself can do.

- **`ffi` grants are additive, like `fs` and `net`.** SPEC.md 7.1 says
  grants are additive; the parser restricted `ffi` to the named modules
  when both `ffi` and `ffi:M` appeared, so `ffi,ffi:math` granted `math`
  alone. It now grants every module: a plain `ffi` means every module,
  and the wider grant wins in either order, matching the reference text
  and `fs`/`net`. (velaris-spec Q2.)

- **`safe_command` round-trips.** It wrote an IPv6 host without brackets
  (`net:::1`, which parses as the host `:` at port 1) and could not
  express a path or host containing `,` or `@`. An escaping rule is
  defined in the spec (v0.2 §5.1, §5.2) and implemented on both sides:
  IPv6 hosts are bracketed (`net:[::1]`, `net:[::1]:443`), and `, @ [ ]
  %` are percent-encoded inside a path or host component and decoded when
  the budget is parsed. `parse_budget` of an audit's `safe_command` now
  reproduces the exact budget for awkward paths and hosts.
  (velaris-spec Q5.)

- **The budget parser is strict.** An unknown effect name in a `uses`
  clause is a compile error (E300) naming the seven real effects;
  `uses io, teleport` no longer compiles and no longer reaches
  `velaris.audit/1`. Every malformed budget is a clean budget error, not
  a traceback: a count is ASCII digits only, so `fs@²` is a budget
  error rather than an uncaught `ValueError`; `ffi` takes no count and
  `ffi:` needs a module; an unbracketed IPv6 address, a stray bracket, a
  doubled `@` and a scope on an effect that takes none are each refused
  with a readable message. (velaris-spec Q1, Q6.)

- **The command line's `audit --json` emits `velaris.audit/1`.** It
  printed an older, unversioned shape the schema rejected; it now calls
  the library's `audit().as_dict()`, the same document the library, the
  MCP server, the HTTP door, the npm package, the CrewAI tool and the
  Action all emit. Its `safe_command` for `examples/json_ffi.vel` now
  says `ffi:math,io` rather than `ffi,io`. (velaris-spec Q3.)

**The README's claim about `ffi:M` is restored.** In 3.2 the README's
"grants Python for those modules only; any other is refused" was weakened
to say what was and was not reachable, because the claim was false: a
granted module was a door into the modules it imported. With the first
fix above it is true again, and the strong wording is back.

**velaris-spec 0.2.** The spec is revised where the behaviour changed and
bumped to 0.2 with a dated annotated tag. It resolves Q1 (unknown names
in `uses` are rejected), Q2 (`ffi` is additive; the wider grant wins),
Q3 (the command line emits `velaris.audit/1`), Q5 (`safe_command` and
`net_hosts` bracket IPv6 and the escaping rule holds `,` and `@`), and
Q6 (non-ASCII count digits, `ffi:M@N` and `ffi:` are budget errors); the
escaping rule is added to §5.1 and §5.2. Its section 2 still quotes this
repository's SPEC.md §6, §7 and §7.1 word for word - those sections did
not change, since "grants are additive" is now true for `ffi` too - so
`tools/check_sync.py` still passes.

**Sources, named** (CONTRIBUTING.md rule): every fix here comes from the
velaris-spec 0.1 extraction of 3.1.1, recorded in that spec's section 11
as open questions Q1, Q2, Q3, Q5 and Q6. HALL_OF_FAME.md credits the
extraction under the standing challenge.

**Verified**, on Windows 11 with Python 3.13, before tagging. With the
prover: `run_tests.py` 92/92, `check_library.py` 82 correct,
`check_sandbox.py` 45, `check_pool.py` 39, `check_refusals.py` 21,
`check_fallible.py` 26, `check_termination.py` 44, none wrong. Without
the prover, in a fresh virtual environment holding this tree and no z3 -
the subset the conformance suite requires: `check_termination.py` 44,
`check_sandbox.py` 45, `check_refusals.py` 11 with 10 skipped for needing
the prover, `check_fallible.py` 26, `check_library.py` with the runtime
fallback asserted where a proof was, none wrong. `fuzz_native.py 30`,
`benchmark --quick --check`, `velaris test examples/std_test.vel` and
`velaris fmt --check` all pass. velaris-spec `tools/check_sync.py` and
`tools/validate.py` pass against this tree.

## 3.2 - The capability format, published as a spec

Nothing in the compiler changed: `velaris.py` differs from 3.1.1 only
in its version string.

**velaris-spec 0.1.** The capability format has a specification of its
own now, in a separate repository,
[gowrishankar-infra/velaris-spec](https://github.com/gowrishankar-infra/velaris-spec),
tagged v0.1: the seven effects and what "transitive" means; the grant
grammar - `fs:read:path`, `net:host:port`, `net:*.domain`,
`ffi:module`, `@N` - as this compiler parses and enforces it, edge
cases included; what a budget guarantees at runtime and what it does
not; `velaris.audit/1` field by field; and `velaris.capabilities/0`, a
ratchet baseline for CI that this compiler does not read yet, marked
provisional until it does. It is written so that the format can be
implemented in another language without reading `velaris.py`, and
where a rule could not be stated precisely it says so, as one of eleven
open questions. Its section 2 quotes sections 6, 7 and 7.1 of this
repository's SPEC.md word for word; `tools/check_sync.py` there, run
weekly by its CI, fails if the two drift. The spec is CC0, so anyone
may implement it; this implementation stays MIT.

Conformance is defined here, not there. ARCHITECTURE.md now names
`check_termination.py`, `check_sandbox.py`, `check_refusals.py`,
`check_fallible.py` and `check_library.py` as the conformance suite,
and an implementation claiming velaris.capabilities compliance must
pass the subset that does not require the prover. The spec's JSON
Schema for `velaris.audit/1` was held against the audit of every one of
the 107 `.vel` files in `examples/` and `stdlib/`, and all 107
validate.

**What writing it down found.** Stating each rule precisely enough for
someone else to implement it turned up places where the compiler, its
documentation and its own SPEC.md do not say the same thing. None is
fixed here, because this release changes no compiler code; each is
recorded in the spec as what the reference does, and listed there as an
open question:

- **`velaris audit` on the command line is not `velaris.audit/1`.**
  With `--json` it prints an older, unversioned summary - `compiles`
  for `ok`, `errors` for `problems`, `functions` as a count - and both
  its `safe_command` and the command it prints under HOW TO RUN IT
  SAFELY are built from the coarse effects alone: for
  `examples/json_ffi.vel`, which calls only `math`, it says
  `--allow ffi,io` where `velaris.audit()` says `--allow ffi:math,io`.
  The library, the MCP server, the HTTP door, the npm package, the
  CrewAI tool and the Action's PR comment are all built on
  `velaris.audit/1`; the command line is the exception. The schema
  rejects the command line's output, and the spec says so rather than
  bending the schema to fit.
- **Grants are not all additive.** SPEC.md 7.1 says they are. For `fs`
  and `net` that holds; for `ffi` it does not: `ffi,ffi:math` grants
  `math` alone. The spec follows the parser, since that is the reading
  that refuses.
- **`ffi:M` checks the module name a call gives, not what is reachable
  through the module.** The function argument of `py` may be a dotted
  path of attributes, and a granted module's attributes include the
  modules it imported. THREAT_MODEL.md already said the allow-list
  narrows which modules and not what a module does; the README said
  "any other is refused", and now says what is refused and what is
  not.
- **`safe_command` is wrong in three cases.** It writes an IPv6 host
  without brackets (`net:::1`, which parses as the host `:` at port 1);
  it passes through a path containing `,` or `@`, which the grammar
  cannot hold; and it copies in any name a `uses` clause gives, because
  `uses io, teleport` compiles and `teleport` reaches the audit.
- **The budget parser reads a count with Python's `isdigit`**, so
  `fs@٣` is a count of 3 and `fs@²` stops the parser with an uncaught
  error instead of a budget error; and `ffi:math@5` is accepted as a
  module literally named `math@5`.
- **Six rules the spec states have no case in any `check_*.py`
  suite**: a dotted function path through a granted module, `ffi`
  together with `ffi:M`, a URL without a scheme taken as HTTPS, IPv6
  grants, an existence check under a write-only grant, and `@0` or a
  count spent by an operation that then fails. The spec lists them as
  its Q9; adding the cases is work for a release that may change
  behaviour if a case fails.

**Related work, cited.** The README has a Related work section after
the opening, naming TACIT (ACM CAIS '26, arXiv 2603.00991), CaMeL and
WASI, what each does, and what Velaris does differently, including what
it does not do: it tracks no data flow, and its command line grants
every effect when no budget is given. The spec's PRIOR_ART.md has the
longer account, with object capabilities, in-toto and SLSA, SARIF,
Deno's permissions and effect systems. The README's `velaris card` line
said ~1,500 words, the size of the card in 2.41; it is 3,335 words by
`wc -w` now, and the README says ~3,300 in both places.

**Sources, named.** CONTRIBUTING.md gains a rule: when a design
decision comes from published work, name the source in the CHANGELOG
entry for that release; say which person, model or bot found a review
finding; and when the origin is not known, do not guess. Applied
backwards where the record allows it. 2.41.1 (a Gemini model), 2.41.2
(a ChatGPT model), 2.42 and 2.44 to 2.47 (a Claude model) now say which
model family found what, from the maintainer's account, since none of
those entries recorded it at the time and HALL_OF_FAME.md had declined
to guess; HALL_OF_FAME.md carries the same names now. 2.59 names
CodeRabbit on crewAIInc/crewAI#7279, from the public pull request,
which also dates its review 2026-09-05; HALL_OF_FAME.md had said
2026-09-10, and is corrected. Nothing else was attributed, because no
other entry's provenance is on record.

This release's own sources, under the new rule: the schemas are JSON
Schema draft 2020-12, the spec's requirement words are those of RFC
2119 and RFC 8174, and its license is Creative Commons CC0 1.0. The
work in PRIOR_ART.md is related work, not a source - none of it is on
record as the origin of a Velaris design decision, and the spec says
so.

**Verified**, on Windows 11 with Python 3.13, before tagging. With the
prover: `run_tests.py` 92/92, `check_library.py` 75 correct,
`check_sandbox.py` 34, `check_pool.py` 39, `check_refusals.py` 21,
`check_fallible.py` 26, `check_termination.py` 44, none wrong; the one
skip in each of the first two is the symlink escape, which needs POSIX.
Without the prover, in a fresh virtual environment holding this tree
and no z3, as rule 7 asks - the subset the conformance suite requires:
`check_termination.py` 44, `check_sandbox.py` 34, `check_refusals.py`
11 with 10 skipped for needing the prover, `check_fallible.py` 26,
`check_library.py` 73 with the runtime fallback asserted where a proof
was, none wrong. The reference implementation passes its own
conformance subset.

## 3.1.1 - A pool test that passed for the wrong reason

`check_pool.py` claimed to hold a program that reaches into the
compiler through a granted `ffi` module, adds `fs` to the live budget,
and is then unable to leave it added for the next program. It did not.
The program named `py("velaris", "EFFECT_BUDGET.add", ["fs"])`, and a
worker runs `velaris.py` as `__main__` - so that name imported a
*second* copy of the module and widened that copy's budget, never the
one the interpreter was enforcing. The next program was refused `fs`
because it had never been granted, not because anything was reset. The
check passed, and would have passed just as well with
`reset_program_state` deleted.

It now names `__main__`, which is the live module, and reads a file
immediately afterwards so the suite can assert the widening really took
hold before it asserts that the next program is refused. Two checks
where there was one:

    ok  a program CAN widen its own budget through ffi - the cliff is
        real, and this is what the next check is against
    ok  ...and it cannot widen it for the next program

The reset was correct the whole time - the counted-grant check
(`fs:read:<dir>@2`, spent per program rather than per worker) was
already exercising the same reinstall from a different angle, and it
still passes. What was wrong was a test whose label was stronger than
its body, which is worse than no test at all: it is the one thing that
makes a suite untrustworthy about everything else in it. The 3.1 entry
below says "the suite has one that does exactly this"; of 3.1.0 that
sentence was false, and it is true from 3.1.1.

Also here: `check_library.py`'s skip messages said "(needs the prover)"
for skips that had nothing to do with the prover - the macOS memory cap
and the POSIX-only symlink escape now say why they were actually
skipped.

39 checks in `check_pool.py`, all passing with and without the prover.
Nothing in `velaris.py` changed.

## 3.1 - A pool that keeps its budget, memory caps on Windows, and a lockfile

**velaris.Pool: bounded runs without a new interpreter every time.**
Every run with a `timeout` or a `max_memory_mb` started a Python
process, about a tenth of a second before a line of Velaris was read.
An agent platform calling `run` thousands of times an hour paid that
every time.

    pool = velaris.Pool(size=4, allow={"io"}, timeout=30,
                        max_memory_mb=512)
    result = pool.run(source)          # the same RunResult run() returns
    pool.close()                       # also a context manager

Measured by `check_pool.py` on the machine this was written on, 200
sequential bounded runs of a small program: **46.56 s a process at a
time, 0.48 s on a pool** - 233 ms each against 2.4 ms each, 96.7x. The
suite asserts at least 3x and prints both numbers, so the claim is
re-measured wherever it runs rather than quoted from here.

The speed is why it exists. The isolation is why it can be used, and
these are the rules, each one asserted in `check_pool.py`:

- **The budget is the pool's, not the program's.** It is parsed once,
  when the pool is made, and installed by each worker at startup.
  `pool.run` takes no `allow` argument - there is nowhere for a caller
  or a program to ask for more, and a different budget means a
  different pool. The budget is re-asserted from the pool before every
  program, so an `@N` count is spent per program rather than shared
  across a worker's whole life. A program that reaches into the
  compiler through a granted `ffi` module and adds `fs` to the live
  budget - the suite has one that does exactly this - cannot leave it
  added for the next program.

- **A worker is used once unless the run was clean.** Anything other
  than `ok` - a refused effect, a failure that escaped, a program that
  did not compile, the timeout, the memory cap - kills the worker and
  starts a fresh one. This is stricter than it has to be: a program
  that failed to compile never ran, so it left nothing behind, and
  retiring its worker costs a restart. It is stricter on purpose,
  because "only a clean run hands its worker back" is a rule a reader
  can check in one line of `Pool.run`, and the weaker version is a
  rule about which failures are harmless.

- **A reused worker starts empty.** Before every program the child
  resets every module-level mutable there is. Searching for them was
  the work; the list, exhaustively, is `PROGRAM_ARGS`,
  `EFFECT_BUDGET`, `FFI_MODULES`, `FS_GRANTS`, `NET_GRANTS`,
  `OP_LIMITS`, `OP_COUNTS`, `PY_OBJECTS` (handles from `py_new`,
  closed by the program or not), `PY_NEXT` (so handle numbering starts
  again), `TRACE`, and `_NATIVE_KEEPALIVE` - which holds the JIT
  engines and, through them, the native text arena. There is no proof
  cache in memory to clear: `check_proofs` keeps its cache on disk and
  only when asked (`use_cache=True`), and the library never asks. Three
  things that belong to the process rather than the module are put
  back too, because a granted `ffi` module can change all three: the
  working directory, the environment, and the recursion limit the
  interpreter raises. They are named in `MUTABLE_GLOBALS` and
  `reset_program_state`, and `check_pool.py` parses `velaris.py`'s own
  module-level assignments and fails if a mutable one appears in
  neither that list nor its list of constants - so the next person to
  add a global cannot forget. That is now rule 6 in ARCHITECTURE.md.

- **The parent owns the deadline.** A worker that has not answered
  within `timeout` is killed by the parent, not asked to stop, and a
  replacement is started; the call returns E610.

- **A program cannot reach the pipe.** The worker keeps private
  duplicates of its own file descriptors 0 and 1 for the protocol and
  points the program's at the null device. The suite has a program
  that runs `echo` through `ffi:os` straight at file descriptor 1; the
  shell's output goes nowhere and the next program still runs.

- **Closing kills every worker**, including one still running a
  program. A pool collected without `close()` is closed by its
  finalizer, one that outlives the interpreter is closed at exit, and
  a worker whose pipe closes ends by itself. The suite checks all
  three against the operating system's own answer about the process
  ids, not the parent's bookkeeping.

`velaris.PoolRegistry` keeps one pool per distinct budget and makes
each the first time that budget is asked for - what a server needs,
since it learns the budget from the request. The MCP server and the
HTTP door each keep one and close it on shutdown; a caller who varies
the budget every time cannot make either hold processes without end,
because the registry keeps at most eight pools and closes the least
recently used. The CrewAI and LangChain tools stay on plain `run`: a
crew's tool is not called often enough for a pool to pay for itself,
and one process per call is easier for a reviewer to reason about.

**Memory caps are enforced on Windows.** Windows has no `RLIMIT_AS`.
The equivalent is a job object with `JOB_OBJECT_LIMIT_PROCESS_MEMORY`,
which has to exist before the child does: the child is created
suspended, assigned to the job, and only then resumed, so no
instruction of it runs outside the cap. An allocation past the cap
fails and reaches a Python child as `MemoryError`, which is already
what `_run_bounded` reads as E611. `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`
means closing the handle kills whatever is inside, which is also how a
pool kills a Windows worker. It is `ctypes`; no new dependency. If any
step fails - `CreateJobObject`, `SetInformationJobObject`,
`AssignProcessToJobObject` - the cap is recorded and not enforced,
which is exactly what Windows did before 3.1, rather than the run
failing.

So the platform rule is now: enforced on Linux (`RLIMIT_AS`) and on
Windows (a job object); best-effort on macOS, where the limit is set
and not reliably honoured and the timeout is what stops a runaway.
`velaris.memory_cap_is_enforced()` answers for the machine you are on,
and `check_library.py` asks it rather than reading the platform name,
so the assertion now runs on Windows as well as Linux and skips only
where the mechanism genuinely does not hold. Every place that stated
the old rule was rewritten: EMBEDDING.md, THREAT_MODEL.md,
COMPLIANCE.md, SECURITY.md, the MCP tool description, `run`'s
docstring, `benchmark/README.md` and the header `benchmark/run.py`
writes - the last of which now asks the compiler instead of guessing
from `sys.platform`.

On POSIX the cap moved from a `preexec_fn` in the parent to
`--max-memory-mb` on the child's own command line, which the child
applies before it does anything else. `preexec_fn` is documented as
unsafe when the parent has threads, and the HTTP door has had threads
since 2.54 - a latent hazard, not an observed failure, and it is gone.

**velaris.lock.** `velaris add` already recorded a sha256 in
`velaris.toml`. It now also writes `velaris.lock`: every vendored
library with its source, its sha256 and the version of Velaris that
added it, as JSON, sorted, one library per entry.

    velaris deps --verify      # do the files match the lock?
    velaris add <url> --force  # replace a library with different bytes

`velaris deps --verify` (`velaris verify` is the older spelling of the
same check) fails if a vendored file's hash differs from the lock or a
locked library is not on disk, and says which. A project with no lock
falls back to checking `velaris.toml` and says the lock is missing.
`velaris add` refuses to overwrite a library that is already vendored
when the incoming bytes differ, printing both digests; `--force`
replaces it. A library that does not compile is still not accepted -
and now the file it would have replaced is put back rather than
deleted.

One thing changed underneath: a vendored library is written as the
exact bytes that arrived, in binary, rather than decoded and rewritten
as text. Before 3.1 the same library added on Windows and on Linux
locked two different hashes, because the rewrite translated line
endings - which makes a lockfile useless for the one thing it is for.
The digest is now the digest of what the source published, and the
same everywhere.

**Fixed: an empty budget did not survive the trip to a child process.**
`velaris.run(source, allow=set(), timeout=1)` came back with E000 and
"'''' is not an effect" instead of refusing `io` with E310. The parent
spelled an empty budget as the two characters `''`, which a shell
strips and `subprocess` does not. `Budget.parse` now reads `''` and
`""` as an empty budget. Without a timeout the same call was always
correct, which is why it went unnoticed.

**Fixed: `run` left Python handles behind in a shared process.** It
restored the budget and the program's arguments afterwards and not
`PY_OBJECTS`, so a framework calling `run` in a loop accumulated every
handle every program opened and did not close. It now puts those back
the same way, which is also what a pool worker does between programs.

**The benchmark.** Rerun in full on Windows 11 with Deno 2.9.6 and
Python 3.13: identical verdicts to 3.0 on all 63 programs. Of the 56
dangerous programs Velaris caught 54 - 42 before running, 12 while
running - and missed 2; Deno caught 32 (5 before, 27 during) and
missed 24; plain Python caught 28 (all while running) and missed 28;
none of the three flagged any of the 7 controls. The Windows job
object changed no verdict: in category 8 the interpreter still reaches
the 5-second deadline before 256 MB, and `RESULTS.md` says so rather
than implying the cap did the work. THREAT_MODEL.md had been carrying
the 2.62 figures (60 programs, 53 dangerous, 51 caught) and
COMPLIANCE.md said 60 programs; both now match RESULTS.md, and the
README and docs/index.html carry the table for the first time. Two
other stale counts in the README went with them: `check_sandbox.py` is
24 escape attempts and 10 honest programs, not 11 attempts, and
`check_refusals.py` is 21 wrong programs, not 20.

**The published docs were three versions stale.** `docs/` had last
been rebuilt at 2.60, so the reference page still said the effects were
`io, fs, net, clock, rand, ffi` with no `env`, and the library page
still showed `env_tools.setting` using `io`. Rebuilding for this
release brought the site up to 3.1; the error-code count on the home
page is now read from the generated page rather than typed by hand,
where it had drifted from 49 to 59.

**New suite.** `check_pool.py` - 38 checks, run without the prover
first, as ARCHITECTURE.md rule 7 requires. `check_termination.py`
joined CI at the same time; it had existed since 2.62 and never been
wired in.

## 3.0 - Budgets that name paths, hosts, counts, and secrets
This is a major version because a program that compiled under 2.x can
be refused by 3.0: `env()` is its own effect now, and a function that
called it under `uses io` alone is refused at compile time with exactly
"env() now needs 'uses env'" and the fix. The reason is the sentence
THREAT_MODEL.md had to carry since 2.63 - an `io`-only budget could
read and print every secret in the environment. It cannot now. `io` is
the console: `print`, `read_line`, `args`. `stdlib/env_tools.vel` and
the two examples that read the environment declare `env`.

**The 2.60 module allow-list, extended to every coarse effect.** The
budget grammar (SPEC.md 7.1) narrows `fs` and `net` the way `ffi:math`
narrows `ffi`:

    fs:read:./data  fs:write:./out       one direction, under a path
    net:api.example.com:443              one host and port
    net:*.example.com                    one label in place of the star
    fs:read:./data@50  net:...@100       at most that many operations

Every path is resolved with `realpath` when the budget is parsed and
again at every `read_file`, `write_file` and `file_exists`, then
compared as a prefix, so `..` and symlinks cannot reach past a grant
(E313, naming the path). `fetch`, `post`, `fetch_status` and `request`
check the URL's host and port before any connection (E314); a
wildcard matches exactly one label and never the domain itself, and
no wildcard may stand over an IP literal. A count is the smallest
given for that effect and applies to the whole run (E315); a budget
with no count is a budget on what, not on how much. Every one of
these refusals is uncatchable, like E310 and E311. The one catchable
case is a redirect whose target lies outside the `net:` grants: the
program asked for one host and was sent to another, so the request
fails with the target named and the program hears why.

The grammar travels unchanged through `--allow`, `velaris.run(allow=)`,
the bounded child (which receives the budget re-spelled with absolute
paths), the MCP server, the HTTP door, the CrewAI and LangChain tools
and the Jupyter magic. The door's `--max-allow` takes it too, and a
caller may not ask for more than the server grants at any level - an
effect, a module, a wider path prefix, a host the server does not
name, a port, a larger count, or an unscoped `fs` or `net` against a
scoped ceiling - and is told which. The audit reads the paths and
hosts a program names in literals (`fs_paths`, `net_hosts`, added
within `velaris.audit/1`) and its `safe_command` grants exactly those,
falling back to `fs:read` or `net` where a value is built at runtime.

Stated as outside the rule rather than claimed: a hard link inside a
granted directory is that directory's content; a file system changed
by another process between the check and the open is outside the
model, and a Velaris program has no threads to race itself; where a
granted host name resolves is DNS's business.

**Tested.** `check_sandbox.py` gained twelve cases: a read outside the
prefix, a write with only read granted, a `..` escape, a symlink
escape (POSIX; skipped on Windows), a host not in the list, a wildcard
that must not match its parent domain, a port not in the list, a
redirect to an ungranted host against a local server, the count
reached on fs and on net, `env()` with only io granted, and an honest
program using exactly its grants that must run - plus a redirect to a
granted host that must be followed. `check_library.py` has the same
through `velaris.run` and through the HTTP door with a ceiling
narrower than the request at each level. `check_fallible.py` has the
redirect failure as a recipe. The benchmark gained category 11 - a
read outside the granted directory, a request to an ungranted host, a
secret read through `env` - run under the narrowest budget each task
needs, with Deno given the matching `--allow-read=<dir>` and
`--allow-net=<host:port>`; Velaris refuses all three (the path and the
URL arrive on stdin, so the first two are refused while running, and
the third is flagged before), Deno refuses all three at the call, and
Python, with no budget, does all three. THREAT_MODEL.md moves "io
includes env", "fs has no path list" and "net has no host list" from
the non-defences to the defences, each with its suite.

## 2.63.1 - The memory cap claim, narrowed to where it holds
The tests workflow had failed on every macos-latest leg since 2.62, in
`check_library.py`: "a memory cap STOPS a program that eats memory".
The cap is `RLIMIT_AS`, and macOS treats that limit as best-effort -
the doubling program ran to the 60 second timeout (E610) instead of
being stopped at 150 MB (E611). Linux honours the limit; Windows has
no equivalent and was already skipped. The CrewAI tool's test had been
narrowed to Linux for the same reason.

The assertion now runs on Linux only, unchanged there; macOS prints a
skip line saying why, Windows keeps its skip. Every place that stated
the platform truth says the same thing now - EMBEDDING.md,
THREAT_MODEL.md, COMPLIANCE.md, SECURITY.md, the MCP tool description,
the `run()` docstring (a comment-only change, the only edit to the
compiler), the benchmark README and the header the harness writes:
enforced on Linux, best-effort on macOS, not applied on Windows; the
timeout is enforced everywhere. Neither `check_termination.py` nor the
benchmark harness asserts a memory-cap outcome, so nothing else
needed narrowing.

## 2.63 - What a security reviewer looks for
Nothing in the compiler changed. Six pieces for the person who has to
decide whether agent-written Velaris may run on a machine they answer
for.

**THREAT_MODEL.md.** The trust boundary (the operator sets the budget,
the program is untrusted, the compiler and the granted `ffi` modules
are trusted in full), what is defended against with the mechanism and
the suite that tests each, and what is explicitly not: anything a
granted module does, side channels, use below the limits, request
volume within `net`, logic errors with no contract, the meaning of
text, code not written in Velaris, the memory cap on Windows, a
tampered compiler. Two items that were not in any list before: `io`
includes `env()`, so an `io`-only program can read and print the
environment; and `fs` has no path list. Each residual risk has a
recommendation. The benchmark numbers are cited; the misses are named.

**COMPLIANCE.md.** One row per guarantee against the OWASP Top 10 for
LLM Applications (2025) and NIST AI RMF functions - mechanism,
framework item, suite, what it does not cover. Nearly every cell says
"partially addresses", because that is the truth; the items Velaris
does nothing for are listed by name.

**Signed releases with an SBOM.** `release.yml` now signs the wheel and
sdist through sigstore, the three executables and `velaris.mcpb`
through cosign, attaches the bundles, signatures and certificates, adds
a CycloneDX SBOM and SHA256 checksums, builds the wheel twice under
the same `SOURCE_DATE_EPOCH` and fails if they differ, and publishes to
PyPI the same files it signed. Every third-party action is pinned to a
commit with the tag beside it. SECURITY.md says how to verify a
download, with the exact identity string. None of this could be
exercised locally; the v2.63 tag is its first run, and the recap of
this release names what to watch.

**A standing challenge.** SECURITY.md: make Velaris report "proven"
for a promise that is false at runtime, or escape `--allow io`, and
you are credited by name in the changelog and in HALL_OF_FAME.md, with
the report treated as a security issue and fixed within a week. There
is no money. HALL_OF_FAME.md opens with the three model-family reviews
of August 2026 and the review bot of September; the changelog never
recorded which family produced which review, and the file says so
rather than guessing.

**A card eval.** `evals/card_eval.py` gives a model LLM.md and five
fixed tasks - a CSV total, a grade filter with a proven contract, a
sandboxed file read, a JSON path read, a stack calculator using `pop`
and `div_or_fail` - and checks, audits and runs each answer under
`--allow io` with a 10 s timeout, writing compiled-first-try, ran
correctly and proven promises to `evals/RESULTS.md`. It skips with one
line when no key is set, and was not run against any API for this
release; the results file holds only the three August reviews, marked
as reported rather than reproduced.

**PR audit comments.** The GitHub Action gains `pr-comment`: on a pull
request it posts one comment with the audit of every changed `.vel`
file - effects, modules, proven share, safe command, warnings - and
edits that comment on later runs, found by a hidden marker. Plain
`curl` against the REST API with the job's token; no third-party
action. The comment builder was exercised locally against real files,
including one that does not compile; the posting itself was not.

## 2.62 - Loops that provably end, and a corpus built to fool it
The 2.61 benchmark named three programs Velaris could not catch. Two
stay misses, by construction: an off-by-one that stops early instead of
reading past the end (no contract, so nothing to refuse), and a program
that prints `rm -rf build` for its caller (the only effect is io, and a
harmless warning prints the same words). The third - a loop that ends,
slowly - is now shown to end before the program runs.

**Termination.** Every loop gets one of two verdicts, by a syntactic
rule that needs no solver and so answers the same with and without the
prover. `terminates` is claimed for exactly one shape: the condition
is, or has as an `and` conjunct, `v < E`, `v <= E`, `v > E` or `v >= E`,
where E mentions nothing the body assigns and calls only pure
functions, and every path through the body moves v by exactly one step
toward E, with v assigned nowhere else. Everything else - a step of two,
a step on one arm only, a counter reset on some path, a limit the body
grows, a flag-only condition, an `or` - is `unshown`, whether or not it
happens to end. A `for` loop goes through the same rule rather than
being exempted: `for i in 0 to length(xs)` with a push inside does not
end, and the rule says so. SPEC.md section 9.5 states it.

It surfaces in three places. `velaris explain` prints "loops: 2
terminate, 1 not shown" per function. `velaris audit` and
`velaris.audit()` gain `loops_unshown` per function and a warning
naming the functions, in schema velaris.audit/1 (added fields, not a
change); they also gain `contract_coverage`, the functions that take or
return a List, a Map or a record and promise nothing about it - a
coverage note, not a defect. `velaris check --strict` refuses a loop
whose end is not shown with E612; without `--strict` it is not an
error, and the time limit in `velaris.run` remains the guard.

**Stressed before trusted.** `check_termination.py` holds 44
adversarial loops with their required verdicts: the wrong direction, a
step of two, a step spelled `1 + i`, a reset on one path, a limit the
body changes, a limit changed only inside a nested if, `length(xs)`
with a push inside, nested loops where only the inner qualifies, a flag
alone, a flag with `or`, a float counter, the step inside a `check` on
both arms and on one, a return with and without a step, recursion
instead of a loop. The analysis was wrong twice on the first attempt,
both times in the same direction - refusing a loop that ends: it
counted the standard library's loops when a program imported it (a
scoping error in the report, fixed by carrying the file), and it did
not accept a text literal or a pure builtin such as `split` inside a
limit, so `for part in split(line, " ")` was `unshown` and a control
program in the benchmark was a false positive. Both are fixed in the
analysis, not the tests. No existing example changed proof status
(`velaris proofs examples --json` before and after, diffed).
`examples/termination.vel` and `examples/termination_bad.vel` join the
suite; the latter runs and is refused only by `--strict`.

**The benchmark, doubled.** Sixty programs now, thirty of them written
against the tools: effects three helpers deep or inside a record, a
division guarded on one path and not the other, an off-by-one only on
empty input, an overflow inside a record field and inside a map, a
failure ignored inside an inline function, a loop that ends only when
input says so, growth by repeated text concatenation, subprocess
reached through the JSON-shaped call and through a handle, and control
programs that look suspicious - printing "rm -rf", reading their own
arguments, importing math in a loop - and are harmless. Same three
languages, same rules. On the machine that produced RESULTS.md
(Windows, prover present, Deno 2.9.6): of 53 dangerous programs
Velaris caught 51 - 41 before running, 10 while running - and missed
the two above; Deno caught 29 (5 before, by its lint on a `while
(true)`) and Python 28; no tool flagged any of the 7 control programs,
the slow loop among them. Ten consecutive runs produce identical
output. What the doubling found: the prover does not flag a division on
an unguarded path when another path guards it, a remainder inside a
loop, or a `get(xs, i + 1)` - all three are caught while running, not
before, and the table says so.

**args().** Under `--allow io` the program's `args()` used to contain
`--allow` and `io`. It no longer contains `--allow`, `--deny`,
`--timeout` or their values, from the command line or from
`velaris.run`; `check_sandbox.py` has the case.

## 2.61 - A table anyone can rerun
Every claim this project makes about catching what a model writes has
been a claim. `benchmark/` turns it into a table that one command
regenerates: `python benchmark/run.py`. Thirty programs in ten
categories - a file write hidden in a helper, a network call hidden in
a helper, division by input, an off-by-one read, integer overflow, an
ignored failure, an infinite loop, runaway memory, reaching subprocess
or os.system, and three correct programs that must not be flagged -
each written three times with the same behaviour, in Velaris, in
JavaScript for Deno and in plain Python. The harness runs every program
through `check` + `audit` + `run` under the budget the task needs (io,
plus `ffi:math` for one control program, with timeout 5 and
max_memory_mb 256), through `deno run --no-prompt` with no flags, and
through a Python subprocess with the same timeout, and records
caught-before-run, caught-during-run, missed, not-applicable,
false-positive or tool-absent, with the evidence in the cell.

On the machine that produced the committed RESULTS.md (Windows, prover
present, Deno 2.9.6): of 27 dangerous programs Velaris caught 24 - 15
before running and 9 while running - and missed 3; Deno caught 13 and
Python 13; no tool flagged a control program. The three misses are in
the corpus on purpose and are named in the results: an off-by-one that
stops early instead of reading past the end (no contract, so nothing
to refuse), a slow but finite loop (ends before the deadline), and a
program that prints `rm -rf build` for its caller (the only effect is
io). Deno's `no-unreachable` lint flags the three memory-growth
programs before running, where Velaris only stops them while running;
and on Windows it stops them with the timeout, not the memory cap,
because the cap is not enforced there and the interpreter allocates
slowly. Both are in the table.

Two things learned while building it. Under `--allow`, `args()` hands
the budget words to the program as well (`['--allow', 'io', ...]`), so
the corpus reads its input from stdin; that is a compiler bug to fix in
its own release, not here. And a Deno permission denial is an ordinary
exception, so a `fetch` inside `try/catch` exits 0 - the harness had to
watch the socket rather than trust the exit status. A Velaris refusal
cannot be caught by the program, which is the difference the benchmark
exists to show.

`benchmark/README.md` has the rules and the exact commands so a
stranger can rerun it and dispute a row. CI runs `run.py --quick
--check` on the legs with the prover, with Deno absent there; a verdict
that changes between compiler versions fails the build and names the
row.

## 2.60 - The ffi cliff becomes a permission
Every review of this project, from three model families and one
automated reviewer, raised the same caveat: `allow ffi` grants
everything Python can do. That was true, and it was the sentence a
security reviewer would stop reading at.

The budget can now name modules. `--allow io,ffi:math,json` grants the
ffi effect for those top-level packages only; anything else is refused
with E311, and the message names the exact flag that would permit it.
Plain `ffi` still grants every module, for programs whose author you
trust. The library takes the same form: `run(source, allow={"io",
"ffi:math"})`, and `refused_effect` reports `"ffi:os"` when that is
what was reached for.

The audit reads the modules a program names in its py* calls and
reports them as `ffi_modules`; its `safe_command` grants exactly those.
A reviewer no longer has to choose between "no Python" and "all of
Python".

Four ways around it were tried and refused, in `check_sandbox.py`: a
module outside the list, a submodule path (`os.path`), the same module
through `py_json`, and through a handle via `py_new`. All three FFI
import sites go through one gate, and the bounded child process
receives the same list. An allowed module still works.

## 2.59 - Time and memory limits, prompted by a review bot
The CrewAI pull request's automated reviewer flagged what three human
reviews had also noted and this project kept deferring: the effect
budget bounds what a program may touch, but nothing bounded how long
it could run or how much memory it could take. For an agent framework
calling `run` in a loop, that is the first thing that goes wrong.

`velaris.run(source, allow={"io"}, timeout=30, max_memory_mb=512)`.
With either limit set the program runs in a separate, killable
process. A program that never ends is stopped at the deadline (E610,
`timed_out=True`); one that eats memory is stopped at the cap (E611,
`out_of_memory=True`, caught in 0.4 seconds in the test). The effect
budget still holds inside that child - verified - and an honest program
is unaffected.

Memory caps use the OS address-space limit, so they apply on Linux and
macOS; on Windows the timeout applies and the cap is recorded but not
enforced, which the docs say plainly rather than implying otherwise.

The MCP server and the HTTP door now default to 30 seconds and 512 MB.
The CrewAI tool does too, reports STOPPED with the limit it hit, and
gained the assertion the reviewer asked for: a refused effect must not
reach the program's own fail branch either.

Attribution, added in 3.2 from the public record: the reviewer was
CodeRabbit (`coderabbitai[bot]`), on
[crewAIInc/crewAI#7279](https://github.com/crewAIInc/crewAI/pull/7279)
at 2026-09-05 06:56 UTC, under the heading "Denial of Service (CWE-400):
Uncontrolled Resource Consumption"; the fail-branch assertion answers a
second finding in the same review.

## 2.58 - Ready to submit to the frameworks
Three integrations in `integrations/`, each written to the target's
own conventions and each with tests that assert the effect budget
holds through the framework's tool interface - because a budget that
leaks one layer up would be the worst kind of promise.

**CrewAI** (`crewai/`): `VelarisAuditTool` and `VelarisRunTool(allow=
["io"])`, five tests, a README, and the pull-request text ready to
paste. `crewai-tools` accepts community tools; this goes first.

**LangChain** (`langchain_velaris/`): a partner package,
`langchain-velaris`, since LangChain lists packages rather than
merging tools. Verified through `.invoke()` that a program granted
only `io` is refused `fs`.

**MCP registry** (`mcp_registry/`): the `server.json` for
registry.modelcontextprotocol.io, which every MCP client reads. A form
rather than a PR, and the highest reach of the three.

`integrations/README.md` says what to submit, where, in what order,
and what makes a maintainer say yes: a test that runs in their CI, a
description of the problem rather than the product, no marketing
words, and fast replies to review.

## 2.57 - --strict, from a question on r/Compilers
Someone asked whether users could choose between strict and flexible
proof modes rather than having leniency imposed on them. They were
right, and half the answer already existed - `velaris proofs --min 80`
holds a line across a project - but the compiler itself always
accepted a promise that fell back to a runtime check.

`velaris check program.vel --strict` refuses when any promise could not
be proven, and names them:

    examples/wordcount.vel: 2 promise(s) could not be proven, and
    --strict does not accept runtime checks:
      bar
          needs    biggest > 0
      report
          needs    top > 0

With no prover installed it refuses rather than pretending - a strict
check that silently proves nothing would be the worst of both.

The default stays lenient because the solver is optional and
strict-by-default would mean the language does not run for anyone who
has not installed z3. That is an argument about the default, not a
reason the flag should not exist.

## 2.56 - Seamless means tested, not claimed
Three gaps between "the door exists" and "the door works".

**The Jupyter magic was never installed.** `velaris_magic.py` was not
in the wheel, so `%load_ext velaris_magic` worked in the repository and
failed for everyone who installed from PyPI. Found by checking from
outside the repo rather than inside it - the difference between a door
that opens and a door that appears to.

**One shape for problems.** `audit()` returned dicts while `check()`
and `run()` returned objects, so callers - including this project's own
Jupyter magic - had to handle both. Now everything returns `Problem`
objects and `as_dict()` flattens them for JSON. The magic got simpler
by six lines, which is what an API fix should look like.

**The version guard covers every version.** It watched velaris.py,
pyproject.toml and the VS Code extension, but not the npm package or
the .mcpb manifest - either could have shipped claiming a version the
compiler never had. Both are guarded now.

`check_library.py` grew a section that asserts every door works after
a real install: all four modules importable, both APIs reporting the
same shape, the npm version following the compiler, the hooks present.
39 checks with the prover, 38 without, and rule 6 was followed - the
no-prover run happened before this was written down.

## 2.55 - Four more doors
Velaris was reachable from a terminal, Python, MCP, CI, Docker and
HTTP. Four populations were still locked out.

**npm.** `npx velaris-lang script.vel --allow io`, plus a real library
with TypeScript types: `audit(source)` and `run(source, {allow:
["io"]})` from Node. Verified through Node that a program granted only
`io` is still refused `fs` - the same guarantee, one process further
away. The compiler stays a Python package; the wrapper says so plainly
when it is missing instead of failing with a spawn error.

**Jupyter.** `%%velaris --audit --allow io` runs a cell in a box and
prints what it can touch and how much is proven first. When an effect
is refused it names the flag that would permit it. The natural home for
the finance and measurement work where proven contracts earn their
keep.

**pre-commit.** Three hooks - `velaris-check`, `velaris-fmt`,
`velaris-proofs` - so a repository can require that its Velaris
compiles, is formatted, and keeps its proven share above a threshold.

**Homebrew and winget** manifests in `packaging/`, both with tests
that assert the effect budget still holds in a packaged build. They
need a tap and a pull request respectively, which is paperwork rather
than code, and the files say exactly what to do.

Building the Jupyter magic surfaced a wart in the library: `audit()`
returns problems as dicts while `run()` returns them as objects. The
magic handles both; the API should not need it, and that is worth
straightening when the format version next moves.

## 2.54 - A door for languages that are not Python
Velaris was reachable from a terminal, from Python, from an MCP client
and from CI. Everything else - a Node service, a Go tool, a Rust
agent, a shell script - was locked out.

`velaris serve` opens a local HTTP door with the same three calls:
`POST /check`, `POST /audit`, `POST /run`, plus `GET /card` and
`GET /health`. Same library underneath, so the same guarantees.

**Two ceilings, both enforced.** The `allow` in a request is the
program's budget. `--max-allow` is the server's own limit - a caller
asking for `ffi` on a server started with `--max-allow io,fs` gets 403
and is told what it does grant. Verified both ways in
`check_library.py`, which now drives a real server on a real port.

It binds to localhost unless told otherwise, warns when it is not, and
warns when `ffi` is grantable - because this endpoint runs programs and
that should be said out loud rather than buried.

`ARCHITECTURE.md` gained a table of what each suite is for, and a
sixth rule: run every new suite without the prover BEFORE wiring it
into CI. That mistake has now been made three times; this release is
the first where the rule was followed rather than learned again.

## 2.53.1 - The library suite knows what needs the prover
Three of the 25 checks in `check_library.py` are about proofs - what
was proven, a refuted promise, a 100% proven share - and the no-solver
CI legs have no prover, so every minimal leg failed the moment the
suite joined CI. The same mistake as 2.39.1, in a new suite.

They are now conditional, and without the prover the suite asserts the
**fallback** instead: that a false promise breaks while running (E600
or E601) and that the audit reports nothing proven. That is a stronger
test than skipping, because it checks the degraded path rather than
ignoring it.

25 with the prover, 24 with the fallback. Both green.

## 2.53 - Setting it up should not be a chore
The MCP server worked; getting it into an assistant meant finding a
Python path and editing JSON. Two ways to skip that.

**`velaris mcp-install`** finds every MCP client on the machine -
Claude Code, Cline, Cursor, Windsurf, Continue, Zed - and adds a
`velaris` server to each, using the Python that is running it. It
never disturbs what is already there: tested against a config holding
another server with its own env block and an unrelated top-level key,
both of which survived, and every file is backed up before writing.
`--list` shows what it found without touching anything, `--remove`
undoes it.

**`velaris.mcpb`** is the double-click bundle, 94 KB, with the
compiler and standard library inside it - newer Claude Desktop builds
only accept remote connectors in the add-connector dialog, so a local
server has to arrive as a bundle. Verified by extracting it somewhere
with no Velaris installed, driving it as a client would, and watching
the sandbox still refuse `fs` to a program granted only `io`. It is
built and attached to every release automatically.

The bundled server now finds the compiler whether it was pip-installed,
vendored beside it, or sitting in the repo next door - a user's own
install still wins.

## 2.52 - Velaris from inside other programs
The effect budget is the idea most easily copied out of this project.
The way to make copying pointless is to make importing cheaper - so
Velaris is now a library, a documented format, and an MCP server, as
well as a command.

**The library.** `velaris.check(source)`, `velaris.audit(source)`,
`velaris.run(source, allow={"io"})` and `velaris.card()`. `run`
captures stdout and stderr, accepts stdin and args, reports which
effect was refused, and restores the previous budget afterwards so a
process can audit and run many programs. The guarantee is identical to
the command line: a refused effect stops the program and cannot be
caught by it.

**A versioned format.** `audit().as_dict()` is `velaris.audit/1`:
effects, per-function contracts with proven-or-runtime status, the
proven share, the safe command, and warnings - including that ffi
cannot be contained by a budget. Documented field by field in
EMBEDDING.md, with a stated compatibility rule. Formats outlive the
tools that produce them.

**An MCP server.** `velaris_mcp.py` offers `velaris_card`,
`velaris_check`, `velaris_audit` and `velaris_run` over the Model
Context Protocol, so an assistant can write Velaris, check it, see
what it touches and run it in a box without leaving the conversation.
`velaris_run` defaults to `allow: ["io"]` - the least that is useful.

**`check_library.py`** proves the library and the server keep the same
promises as the command: 25 checks, including that a program refused
`fs` does not carry on, that budgets are restored between runs, and
that a refusal through MCP is reported as such. In CI on every push.

## 2.51 - Smaller per-call costs, and an honest note about the ceiling
Two more measured savings on the interpreted path, both verified
against every suite and the fuzzer.

The evaluator and statement runner compared node types with
`isinstance`, which walks a class hierarchy; the AST dataclasses have
no subclasses, so 22 of those became pointer comparisons. And a
function with no `requires` or `ensures` was copying its entire scope
on every call to snapshot values for promises it does not have.

Interpreted record work is now 1073ms where it was 1314ms at the start
of this run - about 18% - on top of startup halving in 2.48.

**The honest ceiling**: the remaining cost is the sheer number of
evaluator calls, roughly 580,000 for that benchmark. Removing it needs
the AST compiled to closures or bytecode, which is a rewrite of the
execution core rather than an optimisation of it. Native compilation
for records has the same character - it is the LLVM struct ABI work
that already caused a Windows-only bug once. Both are worth doing and
neither is worth starting at the end of a long session; they need a
plan, a branch, and the fuzzer running between every step.

## 2.50 - Function values carry their surroundings
Two reviewing models named the no-capture rule as a real expressiveness
cost, and they were right: writing `fn(n: Int) -> Bool { return n >
limit }` meant hand-writing a loop instead. Inline functions now
capture **by value**.

The values are copied when the function value is made, so later
assignment to those locals cannot change what the function sees -
`examples/lambda_capture.vel` demonstrates a captured `cutoff` staying
2 after the local is set to 99. There are no reference cells, so a
function value can never observe a change it was not handed.

What did not change, verified: a capturing inline function that tries
to print is still rejected (E300 - effects cannot be smuggled past a
signature); a false promise on one is still caught while running
(E601); a name that exists nowhere is still E402. The prover treats
captured values as unknown, which is the conservative direction.

`examples/lambda_bad.vel` was the test asserting capture is an error.
It is now `examples/lambda_capture.vel` and asserts the opposite - the
right way for a language to record a change of mind.

## 2.49 - The card's gaps were hiding three real bugs
A model reviewed `LLM.md` without a compiler and reported five things
the card never explained. Writing them down meant testing them first,
and three turned out to be defects rather than omissions.

**Deep recursion crashed.** Past about 300 frames a program died with a
Python `RecursionError` traceback. Velaris now stops at 2000 frames
with E609 and says the recursion looks like it never ends - and
Python's own ceiling is lifted so that ours is the one that fires.

**`write_file` crashed on any OS failure.** An unwritable path threw a
raw traceback. It is now E608 with the reason from the operating
system. It stays non-catchable by design - a program that cannot write
where it was told to should stop - but it stops as a Velaris error.

**A dead `write_file` branch** sat unreachable in the interpreter,
left from an earlier edit.

**Two card claims were simply wrong.** Recursion works, carries
contracts, and is checked at call sites - the card never mentioned it,
so a reviewing model refused to use it. And `invariant` works on `for`
loops as well as `while`; the card documented only `while`.
`examples/recursion.vel` proves three contracts across both.

**Handle lifecycle, tested and written down**: double close is a
no-op, use after close fails catchably, handles copy by reference.

**Full module signatures** for http, db, dates, csv, log and
env_tools - every parameter type, every return type, which functions
can fail, which carry proven contracts. Guessing these was the
commonest source of wasted attempts for a model with no compiler.

## 2.48 - Speed, without touching a single guarantee
Three measured wins, none of which changes what the language promises.

**Startup halved: 133ms to 67ms.** Every run - including every hello
world - was importing z3 (about 350ms of the cold cost) whether or not
anything needed proving. The prover is now located rather than
imported at startup, and `check_proofs` returns immediately when no
function carries a contract, no division or list read creates an
obligation, and no callee has a promise to satisfy. Programs that do
need proofs pay exactly what they paid before; the counterexamples in
avg_bad, offbyone_bad and conj_bad still appear.

**Interpreted work is faster.** `sorted()` was running on every single
builtin call to check the effect budget - now precomputed once.
`length`, `get` and `push` sat behind thirty string comparisons and two
module imports - now first, with the bounds guard intact. The
evaluator and statement runner dispatch the hottest node classes
directly instead of walking an isinstance chain: 5.8 million isinstance
calls became 3.8 million on a record-heavy benchmark, and that
benchmark went from 1314ms to 1139ms.

**Measured, not claimed:** a 3-million-iteration loop on the native
path runs in about 80ms against Python's 445ms for the same loop. The
fuzzer confirms both engines still agree exactly on 30 random
programs, and all 89 examples, 25 fallible builtins, 15 sandbox cases
and both stress suites pass unchanged.

## 2.47 - The periphery round
A third adversarial pass executed everything the card mentions - every
builtin, all seven modules against live systems, every error code -
and held the score at 88 while finding the roughness had moved from
the core to the edges. All five findings, fixed:

**Division joins the catchable family.** A zero divisor from user
input was the one remaining way to kill a checked program: E403 stops
the process and no `check` sees it. `div_or_fail` and `mod_or_fail`
fail the normal way, for exactly the input-driven case; plain `/` and
`%` stay strict for divisors the code controls. The card says which to
use when.

**The http envelope is a record.** `call` returned Text and `get`
returned Text, so feeding a raw body to `code_of` compiled and died at
runtime with a misleading JSON error. `call` now returns an `Answer`
record (status, body, raw); `code_of` and `body_of` read fields and
cannot fail; the wrong pairing is a type error. `linkcheck` got
simpler for it. Writing this found a genuine language subtlety: a
local named `status` shadowed the module's `status` *function* and
produced a confusing E530 - renamed, and worth remembering.

**`log.die` says what it does.** `fail_with` logged and killed the
process - correct behaviour, wrong name in a language where "fail"
means catchable. `die` is the new name; `fail_with` remains as an
alias so nothing breaks.

**`velaris check` treats a library as a library.** Requiring `main` at
check time (v2.44) was too broad: `velaris check stdlib/http.vel` is a
legitimate thing to do. A missing main is now only an error for the
file being run - which the runtime already enforced.

**The card grew the last empirical truths**: E525 (binding a
void-returning fallible call), sort_by keys are Int, the _or_fail
guidance, the Answer record, and log.die's semantics.

Attribution, added in 3.2 from the maintainer's account: the third pass
was by the Claude model whose review is 2.44.

## 2.46 - Contents, not just lengths
Two additions, both from the adversarial rubric's remaining points.

**`map_to(xs, f)`** - projection that changes type, `fn(T) -> R`, so a
record becomes one of its fields in one call instead of a hand-written
loop. The generics system supported two type variables all along;
nobody had written the function. Its `ensures length(result) ==
length(xs)` proves.

**Quantified contents prove through loops.** `ensures all_of(result,
is_positive)` on a filtering loop was runtime-only; now the inference
harvests each all_of predicate from the function's own ensures and
tries "everything pushed so far satisfies it" as an invariant. Entry
is vacuous, each push must satisfy it on its path, and the promise
follows. The unguarded version correctly does NOT prove - the
candidate is dropped when a step can break it - and the runtime check
catches it with the actual offending list. Sound in both directions,
and the suite's wall time did not move.

Attribution, added in 3.2 from the maintainer's account: the rubric is
that of the Claude model's review in 2.44.

## 2.45 - The road from 84
Three of the four items that separate this language from the low 90s,
by its own adversarial grading.

**The v2.42 mistake cannot recur.** `check_fallible.py` reads
FALLIBLE_BUILTINS from the compiler itself, generates an
ignore-the-failure program for every member, and asserts each is
refused with E520 - then a caught-failure program for each, asserting
the failure formats and never escapes as a traceback. 23 builtins, all
enforced, in CI on every push. A fallible builtin added without
enforcement now fails the build by construction.

**The prover reads record fields through lists.** A `List of Row` is
modelled as one Int array per provable field, so
`get(rows, i).amount` is a real array read: the off-by-one over a
record list - the adversarial report's exact deferral - is refused
before running (E705), and `ensures result >= 0` on a total over
record amounts is **proven**, which was flatly impossible before.
Building this introduced a truthiness bug on a Z3 array (`or` on an
array is not a None-check) that silently un-refuted a v2.38 regression
test; the refusal harness caught it within the same session, which is
the layered suites doing exactly their job.

**The break question has an answer in writing.** SPEC.md §13a: no
`break`, because the prover's exit knowledge - "the condition is
false" - is what pins counters at boundaries and proves loop promises;
a break turns that into a disjunction over hidden paths and abandons
most loop proofs. The supported idiom is the exit in the loop test
(`while i < n and not found`), which the prover can see, and the card
now teaches it with the reasoning. The decision names the condition
under which it would be revisited.

The fourth item is not code: another adversarial round, finding less.

Attribution, added in 3.2 from the maintainer's account: the grading is
the second pass of the Claude model's review in 2.44.

## 2.44 - Everything the adversarial report found
A model ran 86 adversarial artifacts against 2.43 - one production
program, 34 broken fragments, 52 single-point mutations - and scored
the language 76/100 with a list of defects. All of them are fixed.

**The soundness hole (critical).** `pop`, `slice` and `set_at` were
documented fallible but the checker never demanded handling, so a
clean `velaris check` could be followed by a raw Python traceback at
runtime. The list-operations type check returned before the
fallibility check ran. They now require `check` or `try` like every
other fallible call (E520).

**The checker cannot crash.** An unknown parameter type escaped as a
Python traceback instead of E500, breaking `--json` consumers and any
automated fix loop. Every checker pass now reports instead of raising.

**`main` is validated at check time.** No `main` at all (E400), a
`main` with parameters (E401), and a `main` marked `or fail` (E523,
new) are all compile-time findings now, not runtime surprises.

**The typed FFI carries numbers.** `py_float("math", "sqrt", ["16"])`
sent Python the string "16" and failed. Arguments that read as numbers
are now passed as numbers, with an all-strings retry so functions
genuinely wanting text still get it.

**Conjunctions stop masking.** `requires divisor > 0 and
length(items) > 0` over a record list dropped the WHOLE clause when
one conjunct could not translate - the checkable `divisor > 0`
included. Conjunctions are now split and each part checked on its own,
and record lists carry a modelled length even where their contents
cannot be seen. The report's exact shape is rejected at the call site
with a counterexample.

**The card grew fifteen truths** the reviewer had to discover by
experiment: `%` exists, `random(n)` is 0..n-1, `random(0)` is E405,
record fields go one per line, oversized literals are accepted but
arithmetic is checked, unused effects are viral, `time` needs ffi and
can fail, `apply_to_each` maps T to T only, the `--allow`/`--deny`
budget flags, `velaris proofs --detail`, and codes E400 E405 E509 E513
E521 E523 E542 E602 E704 - plus the E506/E507 correction (E507 is
about duplicate records, not empty maps).

Attribution, added in 3.2 from the maintainer's account: the reviewing
model was a Claude model, and the same review's later passes are behind
2.45, 2.46 and 2.47.

## 2.43 - The prover crosses the loop boundary
The sharpest finding in the last review was that the prover went blind
the moment a loop touched a list: a promise like
`ensures length(result) == length(xs) - 1` would not prove even with a
hand-written invariant, and the textbook off-by-one
`while i <= length(xs) { get(xs, i) }` was caught only at runtime. Both
are fixed.

**Two invariants were missing.** A counter walking toward a limit stops
*at* the limit - without that, the state after a loop only says
`i >= limit`, so "the loop ran exactly that many times" could never
follow. And a list built one item per turn has exactly as many items as
the counter has turns. Both are inferred automatically now; the
promises in `examples/loop_lists.vel` prove with no invariant written
at all. The proven share across the examples went from 60% to 64%.

**The off-by-one is refused before running.** Reporting a bug about a
loop's index used to be unsound, because the index inside a loop stands
for *any* state the invariants allow. The sound route is the loop's
**last real turn**: a counter that starts inside the limit and steps by
exactly one takes every value up to the largest the condition allows,
so that turn genuinely happens and a read on it is a genuine read.
`examples/offbyone_bad.vel` is rejected with the position and the
length. Correct loops - `i < length(xs)`, guarded reads, and counting
backwards - are unaffected, which was checked before anything shipped.

## 2.42 - Findings from a model that installed it and tried to break it
A third model read `velaris card`, installed the language, wrote a
30-function calculator that compiled and ran correctly first try, then
spent its time attacking it. Nearly everything it reported was true.

**Lists can shrink.** `pop`, `slice` and `set_at`, all fallible, all
returning new lists. A stack machine - the natural shape for a
calculator - previously required rebuilding the whole list one element
shorter for every pop. `examples/stack.vel` is that program.

**Overflow can be caught.** `a * b` that outgrows 64 bits is still
E407, which stops the program and no `check` can catch - correct for a
bug, wrong when the numbers come from a user. `add_or_fail`,
`sub_or_fail` and `mul_or_fail` fail in the normal way instead.

**`break` says something true.** It used to report "unknown variable
'break'" and suggest declaring one. It now says the language has no
`break`, and suggests keeping a flag.

**The formatter matches the documentation.** `requires`, `ensures` and
`invariant` were being flattened to the margin, contradicting the style
in Velaris's own docs. Every shipped file is reformatted.

**The card states the ceiling.** The sharpest finding was that the
prover goes blind when a loop mutates a list: `ensures length(result)
== length(xs) - 1` will not prove even with an invariant, and
`while i <= length(xs) { get(xs, i) }` is caught at runtime rather than
before. That limit is real and unfixed; `LLM.md` now says so, along
with the overflow rule and the absence of `break`.

Left as-is, deliberately: the ffi escape hatch is total, and
`velaris audit` already says so unprompted - which the model noted
approvingly.

Attribution, added in 3.2 from the maintainer's account: the model was
a Claude model.

## 2.41.2 - A loop no longer hides a divide by zero
A second model read `velaris card`, wrote an expense report, then
deliberately removed a `requires length(items) > 0` guard and predicted
the compiler would catch the division. It did not.

The cause: the divide-by-zero proof skipped itself whenever *any*
condition on the path mentioned a value a loop had made unknown. Since
almost every average sums in a loop before dividing, the check was
hiding exactly where it was needed. The divisor itself was perfectly
knowable the whole time.

Now the divisor is judged on its own terms and loop conditions stay in
the solver rather than cancelling the proof - dropping them would have
invented counterexamples, keeping them costs nothing.
`examples/avg_bad.vel` is the shape, rejected before running.

Still runtime-checked: dividing by the length of a list of **records**,
because the prover cannot model those at all. That limit is real and
documented; this release fixes the case where the limit was being
claimed falsely.

Two models, two programs, two real defects found in one evening. The
card is doing what it was built for.

Attribution, added in 3.2 from the maintainer's account: the model was
a ChatGPT model (the one in 2.41.1 was a Gemini model).

## 2.41.1 - The card worked, and the first program it produced found a bug
Pasting `velaris card` into a model that had never heard of Velaris
produced a correct program on the first attempt - and that program
crashed the prover. Pushing a **record** onto a list inside a `check`
inside a loop reached a comparison that assumed every value has a Z3
sort. Records do not. The rule was already right (a list of records
cannot be modelled, so abandon the proof and let the runtime check);
the translator simply asked the question in a way that crashed instead
of answering it.

`examples/rec_push.vel` is that program, kept as a regression test.

Worth recording plainly: the card's first user found a real defect
within minutes, which is exactly why it was worth building.

Attribution, added in 3.2 from the maintainer's account: the model was
a Gemini model.

## 2.41 - Written by a model, audited by you, run in a box
Three pieces that make one story.

**`velaris card`** prints `LLM.md` - about 1,500 words containing the
whole language, the ten rules models actually get wrong, every builtin
with its effects and whether it can fail, the error table, and a
complete program to imitate. Paste it into any model and it can write
Velaris that compiles. Until now the language's biggest problem with
generated code was that no model had heard of it.

**`velaris audit program.vel`** answers the reviewer's question rather
than the author's: what this program can touch and which functions
reach outside, what it promises and how much of that is **proven**
before running versus checked while running, what can fail, and the
exact command to run it under a budget. When a program calls Python it
says plainly that an effect budget cannot contain that. `--json` for
tooling.

**`agent_loop.py`** writes a program with a model and iterates against
the compiler: `velaris check --json` hands back codes, lines and
numbered fixes, which go straight back to the model, up to six rounds,
then the result is audited. Most agent loops iterate against tests;
this one iterates against a proof, which is a stronger signal - the
compiler does not say "a test failed", it says which input breaks which
promise.

## 2.40.1 - Leading with the sandbox
The README now opens with the thing that matters most in 2026: an AI
wrote you a script, and you can run it anyway because the runtime
refuses whatever you did not allow. The proof story - promises checked
before the program runs - follows immediately after, where it reads as
the reason to believe the first claim rather than competing with it.
New hero image to match, and the limits stated in the same breath as
the feature.

## 2.40 - Running a program you have not read
The compiler has always checked that a function declares what it does.
This is the other half:

    velaris program.vel --allow io          refuse every other effect
    velaris program.vel --deny net,ffi      allow everything but these

The runtime refuses any effect outside the budget granted on the
command line, **whatever the source says about itself**. A refusal is
not a failure the program can catch with `check` - it stops there, so
a program cannot swallow the refusal and carry on.

`check_sandbox.py` proves it holds: eleven escape attempts - reading,
writing, the network, calling Python, opening a database through a
handle, the clock, randomness, hiding the effect behind two layers of
helper, catching the refusal to continue anyway, and both `--deny`
forms - all refused with E310, with a file-existence check confirming
nothing was actually written. Four honest programs still run untouched,
including one with no permissions at all. Needs no prover, so it
behaves identically in every CI configuration.

`examples/sandbox.vel` shows the same thing by hand.

**What this is not**: a security boundary. A program granted `ffi` can
do anything Python can, and nothing here limits memory, time, or what a
program prints. It is a strong guard against accident and casual
misbehaviour - which is the situation you are in when an AI hands you a
script - not a defence against a hostile author you have already
granted permission.

## 2.39.1 - The refusal harness knows what needs the prover
Nine of the twenty refusals in `check_refusals.py` are proof results -
a false promise, a possible divide by zero, an out-of-range read, a
broken invariant. Without z3 installed those programs simply run, so
every no-solver leg in CI failed the moment the harness joined it.
The harness now skips those cases when the prover is absent and says
so, exactly as the example suite already did.

Verified both ways: 20 refused correctly with the prover, 11 refused
and 9 skipped without it.

## 2.39 - The editor asks for what the compiler already knew
The language server has answered hover, completion, go-to-definition,
rename, an outline and proof-status lenses since 2.32 - but the
extension's hand-rolled client only ever listened for errors, so none
of it reached the editor. The client now asks:

- completion for functions in scope with their contracts, and every
  builtin with its effects and whether it can fail
- hover showing a signature with its `requires` and `ensures`
- go to definition, across imported files
- rename across the file
- an outline of the file's functions
- **proof status above every function**, from the real prover

Requests time out after eight seconds and fall back to nothing rather
than hanging the editor.

Plus 17 snippets for the shapes this language actually uses: `fnp` for
a function with promises, `fnfail` for one that can fail, `check` for
handling both outcomes, `whileinv` for a loop with an invariant,
`record`, `test`, `json`, `py`, `importas` and more.

## 2.38 - Testing the places languages break
Two new suites, because a test that only checks correct code passing
is half a test.

`examples/edges.vel` covers boundaries, properties and round trips:
empty and single-element lists, empty text, empty maps, negatives,
zero, division rounding toward minus infinity, the 64-bit limits, and
empty ranges - then **195 generated cases** asserting properties rather
than examples (sort always returns a sorted list of the same length
containing the same elements; reversing twice is the original; the
maximum is always a member; filtering never keeps what it should not),
and round trips that must come back unchanged (28 dates parsed and
printed, JSON built and read, a CSV row written and read, join then
split, upper then lower). 20 checks, all passing.

`check_refusals.py` is stricter than the example suite: it asserts that
each of **20 wrong programs is refused with the specific error the
language promises**, not merely refused. A false promise must be E700,
an undeclared effect E300, an ignored failure E520, a possible divide
by zero E706, an out-of-range read E705, a broken loop invariant E703,
and so on - so a guarantee cannot quietly degrade into a different
guarantee. Both run in CI on every push.

## 2.37 - A stress test written in Velaris
`examples/stress.vel` exercises the whole language and standard library
in one command that asks nothing and exits non-zero if anything fails:
contracts and proofs, inferred loop invariants, division proofs,
records with list fields, map proofs, nested lists, generics, function
values inline and by name, text case and containment, native list and
text scanning, failure through `try` and `check`, JSON reading and
building, dates, CSV, the host language including a real SQLite handle,
the environment, the clock, and a network request that reports itself
as skipped when offline.

33 checks. Two failed on the first run and both were the test's
arithmetic being wrong rather than the language - which is the right
way round, and is why the corrected expectations are in the file.

## 2.36.4 - The Action has its own name
GitHub's Marketplace requires an Action's name to be globally unique,
and "Velaris" was taken. The Action is now "Velaris Language Check",
which describes what it does anyway. Nothing else changed - the way
you use it is identical.

## 2.36.3 - A picture of the point
The README now opens with an image of the compiler refuting a promise
and handing back the input that breaks it. People decide in a few
seconds whether to keep reading, and the most convincing thing about
this language was previously three scrolls down.

## 2.36.2 - Somewhere to start
The README points at the open `good first issue` list and spells out
the four commands a change has to pass before it ships. The tasks
themselves are now issues rather than a paragraph in a file nobody
opens.

## 2.36.1 - Two-part tags publish the extension again
Tags here are two-part (`v2.36`) but npm requires three
(`2.36.0`), so the extension publish failed with
`Invalid version: 2.36`. The workflow now pads a short tag before
using it. Nothing about the language changed.

## 2.36 - A tool worth running, and errors that read like a language
`examples/linkcheck.vel` is a real utility rather than a demonstration:
give it URLs on the command line or pipe a list in, and it reports each
one's status, counts the broken ones, and exits non-zero so a scheduler
can act. Progress goes to the error channel and the report to the
output channel, so `linkcheck ... 2>/dev/null` is a clean report. It
uses the http, log and standard modules together - the first program
here written the way a user would write one.

Writing it found a papercut worth fixing: a failed request handed
Python's own words to the user
(`<urlopen error [Errno -2] Name or service not known>`). Network
failures now say what happened - the address did not resolve, it did
not answer in time, the connection was refused, the certificate was not
accepted - because an error message is part of a language's surface,
not a place to leak the implementation.

## 2.35 - Dates as values, HTTP with headers, and a way in for others
`request(method, url, body, headers)` is one honest HTTP builtin: any
method, headers as JSON, and the whole answer back as JSON - status,
body and response headers together. `http.vel` wraps it as `call`,
`get_with`, `post_json`, `code_of`, `body_of`, `header_of`. Still
`uses net`, still fallible.

`dates.vel` makes a date a **record**, not text: `make` and `parse`
refuse impossible dates, `days_in` is proven to return between 28 and
31, and `before`, `same`, `next_day` and `text_of` work on values.
Writing it, the prover caught a real bug in it: `next_day` called
`days_in` without knowing the month was valid, because a record cannot
promise anything about its own fields. The fix was to say what the
function needs, which is the language working as intended on its own
standard library.

`velaris proofs --detail` lists each promise-carrying function and,
for the ones not proven, the contracts involved - so "60% proven"
becomes a list you can act on.

And the part that is not code: [ARCHITECTURE.md](ARCHITECTURE.md) is a
map of the compiler with a table of where things live and the five
rules this project holds; [MAINTAINERS.md](MAINTAINERS.md) says how
someone becomes a maintainer, what a maintainer may not do (weaken a
guarantee quietly), and lists six real, small, self-contained places
to start. A second maintainer is the single thing that would most
change what this project can promise, and now there is a door.

## 2.34 - Unattended work, and building for machines you do not have
`log(text)` writes to the error channel, and `log.vel` gives it levels
(`info`, `warn`, `error`, `event`, `fail_with`). Messages and results
finally travel separately: a pipeline captures `print` output while a
person watching sees the log, and `fail_with` exits non-zero.

`csv.vel` handles the shape most data arrives in - `fields`, `column`,
`column_int`, `rows_of`, `line_of` - and `time.vel` gains `year_of`,
`month_of` and `day_number`. `examples/pipeline.vel` is what an
unattended job looks like end to end.

`velaris build --for-everyone` writes a workflow that builds your
program on Windows, Linux and macOS and attaches all three to a
release. One machine genuinely cannot build for other machines; three
machines can, and this hands you the three.

The language server also renames: every use of a function this file
owns, comments left alone, and only names the file actually defines.

## 2.33 - A number a team can watch, and an image to run it in
`velaris proofs [path]` reports, for a file or a whole project, how
many promise-carrying functions are **proven before running** versus
**checked while running** - with `--json` for tooling and `--min 80`
to fail a build when the share slips. If a language's claim is proven
promises, that number should be visible and defended, not assumed.
The GitHub Action takes `min-proven`, and this project's own CI now
prints its share on every push.

The language server also completes: functions in scope with their
signatures and contracts, every builtin with its effects and whether
it can fail, and the keywords.

A `Dockerfile` builds an image with the prover and native backend
already installed, so `docker run --rm -v "$PWD:/work" velaris check
/work/main.vel` needs nothing on the machine but Docker.

## 2.32 - The editor knows what is proven, and CI is one line
The language server answers hover (signature, effects and contracts),
go-to-definition across imported files, an outline of the file, and -
the one that matters for this language - **code lenses above every
function saying whether its promises are proven before running or
checked while running**. That status comes from the real prover, using
the proof cache, so it is the truth rather than a guess.

`action.yml` makes Velaris a GitHub Action:

    - uses: gowrishankar-infra/velaris-lang@v2.32
      with:
        files: "src/*.vel"
        format: "true"

It installs Velaris with the prover and fails the build if anything
does not compile or a promise cannot be kept.

`ROADMAP.md` says what is planned, what is deliberately not (and why),
and how to change it. `SUPPORT.md` states plainly what one maintainer
can promise - and that an organisation depending on this today is
taking a real, non-technical risk. Both exist because a company reads
those before it reads code, and silence is worse than an honest limit.

## 2.31 - A standard library that reaches outside
Four modules so nobody writes FFI plumbing by hand:

    import "http.vel" as http        get, status, ok, send, get_json
    import "db.vel" as db            open, run, rows_json, count, close
    import "time.vel" as time        today, clock_text, seconds
    import "env_tools.vel" as sys    setting, number_setting, give_up

They are written in Velaris, so they carry their effects: a program
using `http` shows `net` in `velaris explain`, one using `db` shows
`ffi`, and a pure function still cannot call either.

Three builtins the modules needed, and every real script needs anyway:
`env(name, fallback)` reads the environment, `exit_with(code)` sets the
exit status (0-255, checked), and `read_line()` reads a line from
standard input.

## 2.30 - The language reference, and a position on concurrency
`SPEC.md` is the specification: what Velaris means, precisely. Lexical
structure, types, integer and float semantics, evaluation order,
effect propagation as a property of the whole call graph, failure,
what "proven" actually means and what is proven today, modular proof
and the rule that a dropped premise abandons the proof, modules,
native-versus-interpreted equivalence, the host language boundary,
errors, and versioning.

Two sections are there because a specification that lists only
strengths is advertising. **Concurrency**: Velaris is single-threaded
by design and has no concurrency model - stated as a position, with
the reason (a signature of the current design cannot describe data
races, so adding threads would break the language's central claim) and
what would have to change first. **What this language does not have**:
no exceptions, no closures, no inheritance, no macros, no package
registry, no mutable data structures, and a compiler written in Python
that is clear to read and slower than a production one.

The reference is published with the documentation.

## 2.29 - Remembered proofs
A proof that has already been done is not done again. Results are kept
in `.velaris/proofs.json`, keyed by what the proof actually depends on:
the function's own text **and the contracts of everything it calls** -
because a modular proof assumes those, and a cache that ignored them
would keep telling you something that is no longer true. Weakening a
callee's promise re-proves its callers, as it must.

The float refutation in `examples/fp_proof_bad.vel` takes 16.6 seconds
the first time and 0.10 seconds after, with the same message. Use
`--no-cache` to prove everything again, or `velaris clean` to forget.

## 2.28 - velaris build: hand someone your program
`velaris build program.vel` produces a single executable containing
your program, everything it imports, the standard library, and the
compiler itself. The person you give it to needs nothing installed -
not Python, not Velaris - which is the difference between a language
you write scripts in and one you deliver software with.

The program is compiled and proof-checked before it is built, so a
program that does not compile is never shipped. Command line arguments
reach `args()` as usual. Building needs PyInstaller
(`pip install pyinstaller`), and the compiler says so plainly when it
is missing.

## 2.27 - Handles: real libraries, not just functions
A `Handle` is a ticket for something living on the Python side - a
database connection, an HTTP session, a file. That is the difference
between calling functions and using libraries:

    py_new(module, function, args)   -> Handle    make one
    py_do(handle, method, args)      -> Text      call a method on it
    py_field(handle, name)           -> Text      read an attribute
    py_close(handle)                              let it go

`examples/database.vel` opens a real SQLite database, creates a table,
inserts a row, counts the rows and closes the connection - all from
Velaris, and all behind `uses ffi`, so a program that talks to a
database says so in its signatures.

Arguments travel as JSON and a trailing JSON object becomes keyword
arguments, which many Python APIs require. Handles pass through calls
as arguments too, and anything Python hands back that is not JSON
comes back as a handle rather than being flattened into a string.

## 2.26 - JSON, and calling Python with real data
The FFI shipped in 2.25 could only pass text and receive a scalar,
which is not "call any Python library" - it is "call the ones that
happen to take strings". `py_json(module, function, args_json)` sends
arguments and receives the answer as JSON, so numbers, lists and
nested data survive the trip: `py_json("math", "sqrt", "[16]")` now
gives back 4.0 rather than failing on a string.

JSON is first class and **pure** - reading a document is not an effect:

    json_get(doc, "user.name")     json_int(doc, "user.age")
    json_float(doc, "price")       json_len(doc, "tags")
    json_has(doc, "user.email")    json_of(anything)

Paths walk objects and lists (`tags[1]`, `items[0].price`), records
serialise straight to JSON, and every read can fail - a missing field
is a real possibility, not a crash, and the message says exactly which
step of the path was missing.

## 2.25 - Reaching the outside world, visibly
Velaris can call Python now, which means it can reach every library
Python has - JSON, dates, hashing, databases, anything - through three
builtins:

    py(module, function, args)        -> Text
    py_int(module, function, args)    -> Int
    py_float(module, function, args)  -> Float

They need `uses ffi`, so a function that reaches outside says so in its
signature, and a pure function still cannot do it - nor can anything it
calls. All three can fail (module missing, function absent, bad
argument), so callers handle it like any other failure. `velaris
explain` lists `ffi` next to the functions that use it, which is the
whole point: the power is available and it is never hidden.

Two conveniences, both deterministic: a dotted module path like
`datetime.date` is resolved by importing what imports and reaching the
rest by name, and a function that wants bytes rather than text gets the
text as UTF-8 after the first refusal.

## 2.24.1 - The extension follows the language's version
The 2.23 release tried to publish the extension as 2.22.1 - a version
already on the Marketplace - and reported that as a failure. The
extension's version now comes from the tag itself, an
already-published version is treated as nothing to do rather than an
error, and the test suite fails if the extension's version ever drifts
from the compiler's.

## 2.24 - Lists of text, and split
`List of Text` is modelled symbolically now, so promises about lists of
words are proven rather than checked while running -
`ensures length(result) == length(words) + 1` for a push, for instance.
List literals pick their element sort from their values, and pushing a
value of the wrong sort simply falls back to a runtime check instead of
being forced into a formula that would not mean the same thing.

`split` is modelled as an unknown list with a known minimum: the pieces
themselves are opaque to the prover, but it knows there is always at
least one, which is what contracts about splitting usually rest on.

## 2.23 - Libraries you can actually share
Until now, using someone's Velaris library meant copying a file and
hoping. Three commands fix that:

    velaris add <url or path> [as name]   vendor it into lib/
    velaris deps                          what this project depends on
    velaris verify                        are they exactly as recorded?

`add` fetches the file (local path or https), **compiles it before
accepting it** - a library that does not compile is not added - and
records its exact sha256 in `velaris.toml`. It then tells you what you
just took on: how many functions, how many with proven promises, and
what effects the library performs. `verify` re-checks every hash, so a
library that changed underneath you is something you find out about
rather than run.

Deliberately not a registry: the file lives in your repository where
you can read it, there is no resolver inventing versions for you, and
nothing is fetched at build time.

## 2.22.1 - First extension publish
A version bump so the tagged release has something newer than the
Marketplace has, now that the publisher and token exist. Nothing about
the language changed.

## 2.22 - The editor extension, ready to publish
The VS Code extension is packaged properly: real publisher and
repository metadata, an icon, a license, a written README, settings
for where Velaris lives and whether to check on save, and categories
so it can be found by search. A release workflow publishes it to the
Marketplace when a `VSCE_TOKEN` secret exists, and quietly skips when
it does not - so nothing breaks while that waits on a one-time setup.

## 2.21 - Watching a program run, and case-changing proofs
`velaris trace program.vel` prints every call as it happens - indented
by depth, arguments going in, answer coming back, and `FAILED` with the
reason when a call fails. Native calls are shown too, marked as such,
so a trace never hides half the program. It is the tool a beginner
reaches for when reading is not enough.

The prover models `upper` and `lower` as functions that keep a text's
length, so `ensures length(result) == length(word)` is proven rather
than checked at runtime. Honest limit: a *false* promise about them is
still caught at runtime rather than at compile time, because the
solver cannot pin down the letters themselves - proven claims stay
true, they are just fewer.

## 2.20 - Whole numbers have a size, and outgrowing it is an error
The fuzzer added in 2.16 found a real disagreement: native code holds
whole numbers in 64 bits and wraps around, while the interpreter used
Python's unlimited integers and kept counting. Same program, two
answers, silently.

Neither behaviour is acceptable, so both are gone. A whole number in
Velaris is 64-bit, and arithmetic that outgrows it is an error (E407)
in both engines - the interpreter checks the range, native code uses
the processor's overflow flag through LLVM's checked intrinsics. The
two seeds that found the bug now agree, and so do 250 fresh random
programs.

This is the first bug the fuzzer caught on its own, which is the
entire reason it exists.

## 2.19 - pip install velaris-lang
Velaris is on PyPI. Installing is now one line with no repository URL
to remember, and every release publishes automatically from its tag
through trusted publishing. The README, tutorial and docs site lead
with it.

## 2.18.2 - Minimal-mode expectations for the newest proofs
`div_bad.vel` and `grid_bad.vel` demonstrate bugs only the prover can
see: divide-by-zero on a path that happens not to be taken, and a row
read that is in range for the example data. Without z3 installed both
programs simply run, so the test suite expected the wrong verdict and
every no-dependency leg failed on all three platforms. They are now
listed with the other proof-only examples, and the suite passes with
and without the solver.

## 2.18.1 - Releases stay green
The PyPI job added in 2.18 cannot succeed until a pending publisher
exists on pypi.org, and a release should not be reported as broken for
a step that is waiting on a one-time setup. It no longer blocks the
release; the executables build and attach as before.

## 2.18 - Records holding lists, and publishing
A record's fields may now be lists, floats or text and still take part
in proofs, so `ensures length(result.items) == length(b.items) + 1` is
proven rather than checked at runtime.

Turning that on immediately found a real bug in the ledger app: with
records fully modelled, the prover could see that `describe` calls
`money(e.amount)` on an amount nothing had constrained to be positive.
`money` is now total - a negative amount formats as a refund - and the
app compiles honestly instead of relying on an assumption nobody
checked.

Releases now publish to PyPI on every tag (trusted publishing, no
stored token), so installing becomes `pip install velaris-lang`.

Also: the version in pyproject.toml had drifted to 1.9.0 while the
compiler said 2.17. The test suite now fails if the two ever disagree.

## 2.17 - for loops, tests in Velaris, and text containment proofs
`for i in 0 to n` and `for item in xs` are here. They are turned into
the while loops the rest of the compiler already understands, so
invariant inference and proofs work through them unchanged - the
shorter form costs nothing.

`velaris test program.vel` runs every function named `test_*` that
takes no arguments and reports which returned true.
`examples/std_test.vel` is the first suite: seven tests for the
standard library, written in Velaris, and CI runs them on every push.
The language can now test itself.

The prover models `contains` on text through Z3's string theory, so
`ensures contains(result, word)` is proven rather than checked at
runtime.

## 2.16 - Catching the next one, a third app, and a current tutorial
`fuzz_native.py` generates random Velaris programs - integer maths,
loops, list scans, text scans, floats, branches - runs each one
interpreted and natively, and fails if the two ever disagree. CI runs
it on every push, now across Linux, Windows **and macOS**: the exact
combination that would have caught the 2.15 problem before it reached
anyone.

`examples/fetcher.vel` is a third real program, and the first to use
the network: it reads a URL from the command line, checks the status
before downloading a body, and summarises what it got. Every network
call is behind `uses net` and can fail, so all three failure paths
(bad status, unreachable host, no arguments) are visible in the code
rather than assumed away.

TUTORIAL.md is rewritten for the language as it actually is. The old
one predated lambdas, namespaces, format, args, map proofs, invariant
inference and the whole toolset - someone arriving today was reading a
description of a language from fifteen releases ago.

## 2.15.1 - Native text building, made portable
Two examples failed on Windows in 2.15: a function that RETURNS text
handed a small struct back across the machine-code boundary, and how
that is done depends on the platform's calling convention. Rather than
guess at an ABI this project cannot test everywhere, text results now
stay interpreted. Text built *inside* a native function still uses the
arena and is still fast (183.5 ms interpreted, 4.1 ms native here).

Native compilation is also fail-safe now: if anything about a machine's
backend disagrees with the compiler, the program runs interpreted and
behaves identically, instead of failing. A speed optimisation should
never be able to stop a correct program from running.

## 2.15 - Native text building (the arena)
Concatenation compiles to machine code. Text is built in a scratch
buffer the runtime owns, reset at every call, so native code never has
to decide who frees what. If a call needs more room than the buffer
holds, **nothing is copied**: the buffer grows and the call runs again,
so the answer is always the one the interpreter would have given. A
million characters built through a 64 KB starting buffer comes back
byte-correct, unicode and emoji included, checked against 200 random
strings.

Measured: 172.8 ms interpreted, 0.9 ms native.

Getting there needed one more fix: `length` and `code_at` now work on
any text-valued expression, not just a variable. Before that,
`length(banner(word))` kept a whole loop interpreted, and crossing the
native boundary once per iteration was *slower* than staying
interpreted - the benchmark said so before the fix, which is why the
benchmark is in the example.

## 2.14 - Native text reads, and proven functions run fast
Text scanning compiles to machine code. Text crosses into native code
as Unicode code points plus a length, so `length` still counts
characters and non-English text behaves identically - verified against
300 random strings including accents and emoji. Reads are
bounds-guarded like list reads. Measured: 696.8 ms interpreted, 22.3 ms
native.

New builtin `code_at(text, i)` gives the code point at a position with
no allocation - the operation native scanning needs, and useful
interpreted too.

Two rules changed for the better. A function whose promises are
**proven** may now compile natively: an unproven promise still needs
its runtime check, but a proven one is already true, so there is
nothing to check. And the prover learned `length` on text and a sound
uninterpreted model of `code_at`, so text-scanning loops can be proven
at all.

Building text (concatenation) stays interpreted - that allocates, and
allocation gets its own release.

## 2.13 - Native lists
Pure functions that read `List of Int` now compile to machine code.
The list crosses into native code as a pointer plus a length, and every
read is bounds-guarded: an out-of-range position records the mistake
and returns without touching memory, so you get the same E602 you would
have got interpreted rather than a segfault. Measured on a
500-element list summed 200 times: 782.6 ms interpreted, 2.7 ms native,
identical results. Differential-tested as always.

Writing to lists (push) stays interpreted - that needs allocation, and
allocation needs an ownership story this language has not designed yet.

## 2.12 - Lists of lists, proven
A grid is now modelled symbolically - its rows, each row's length, and
how many rows - so `length`, `get` and `push` on nested lists take part
in proofs, and an out-of-range row is caught before the program runs
exactly as it is for a flat list. Nested list *types* also parse now:
`List of List of Int` was previously a syntax error.

That closes the last container with no proof story. Ints, Bools,
Floats (in IEEE-754), Texts, records, lists, nested lists and maps are
all proof territory; only Text contents remain runtime-checked.

## 2.11 - Invariant inference (the boring ones, for free)
Loops without a written `invariant` can now be crossed by the prover.
Candidate invariants are proposed for every counter a loop moves - it
never goes below, or never above, the value it started at - assumed
together, and whatever one loop step can break is dropped, repeating
until the set is stable. (Houdini, kept small.) `examples/inferred.vel`
proves three promises with no invariant lines at all.

Honest about the limits: this infers simple bounds on counters, not
membership or sortedness, so the standard library's loops still need
their hand-written invariants.

Also fixed something that had been quietly lying since 2.6: `explain`
and the inspector reported a function as "proven" whenever the file had
no errors, even when the prover had actually given up and left the
promise to a runtime check. The status now comes from the prover
itself, so "proven" means proven.

## 2.10 - Contracts on function values
An inline function can carry `requires` and `ensures` of its own, and
they are proven like any other function's - so a function value is a
first class citizen rather than a convenience. Because lambdas are
lifted to real functions, this needed no new machinery in the prover.
Errors about them now say "this function value" instead of leaking the
generated name.

## 2.9 - Map proofs
Maps are now modelled symbolically - the values, plus which keys are
actually present - so `put`, `get_or` and `has` take part in proofs.
Promises like "this key now holds one more than before" are proven
before the program runs, and wrong ones are refuted with the offending
key. Text values became symbolic strings to make map keys work, which
also lets Text cross call summaries.

Lists remain arrays of Ints: anything else (Text lists, lists of
lists) is explicitly guarded now and falls back to runtime checks
rather than being forced into a sort it does not fit.

## 2.8 - A second real app, and Text ordering
`examples/wordcount.vel` reads a file, counts word frequencies and
prints a ranked histogram - a different shape of program from the
ledger, exercising maps, records, lambdas, namespaced imports, format,
args, and three separate failure paths (missing file, unreadable count
argument, no words found).

Writing it found a real hole: Text had no ordering, so `c >= "a"` did
not compile and words could not be sorted alphabetically. `<`, `>`,
`<=` and `>=` now work on Text, comparing alphabetically. Promises
about Text comparisons are checked at runtime rather than proven, and
the prover does not pretend otherwise.

Also: the error de-duplication from 2.5.1 now lives in the shared
analysis, so `check`, `explain` and the browser inspector report one
message per problem too.

## 2.7 - Reading a codebase
`velaris check program.vel` compiles without running - for CI, editors,
and pre-commit hooks - and takes several files at once. `velaris
explain` now puts *your* functions first and summarises imported
libraries in one line (`--all` expands them), because the first real
run of explain buried a ten-function app under eighteen library
functions. `velaris explain <folder>` maps every .vel file under a
directory: functions, proven promises, effects, and any errors.

## 2.6 - Division proofs, and seeing what your code promises
`velaris explain program.vel` walks through a file function by
function: what it may do, what it needs, what it promises, and whether
those promises are proven or left to runtime. The browser playground
gains an **Inspect** button showing the same thing as cards, with
errors and their fixes in place. `--json` gives the whole report as
data for tools.

Contract printing is now precedence-aware, so `(result + 1) * count`
no longer prints as `result + 1 * count` (it did, on the docs site).

## 2.6 - Division proofs
`/` and `%` on whole numbers are now proof territory: the compiler
proves the divisor is never zero (E706, with the value that breaks it)
and can prove what the result means. Translated only when the divisor
is provably positive, because Velaris floors like Python while Z3's
integer division is Euclidean - the two disagree on negative divisors,
so that case falls back to a runtime check rather than a formula that
would quietly lie.

## 2.5.1 - One problem, one message
The effect checker and type checker could both report the same unknown
function, so a single mistake printed twice. Identical errors are now
reported once.

## 2.5 - Namespaced imports
`import "lib/geo.vel" as geo` then `geo.distance(a, b)`. A named import
prefixes that library's functions, rewriting its internal references so
the library is unchanged from the inside. Two libraries exporting the
same name can now be used in one file, which was impossible before.
Unknown namespaces and unknown functions inside a namespace get their
own messages (E200 lists what the namespace does offer), and a local
variable may not shadow an import name (E514). Plus a written piece on
why float proofs use IEEE-754 rather than reals: docs/floats.md.

## 2.4 - The everyday things
Function values inline: `keep_if(xs, fn(n: Int) -> Bool { return n > 4 })`.
They are lifted to real top-level functions, so types, effects, proofs
and native codegen treat them like any other function - and they cannot
capture surrounding variables, which keeps them pure and gives a clear
error when you try. Also: `format("hi {}", name)` with placeholder
count checked at compile time, `args()` for command line arguments,
`post(url, body)` and `fetch_status(url)` alongside `fetch`. The ledger
app now uses a lambda for its report sorting.

## 2.3 - Public launch polish
New visual identity across the docs site, playground, and README:
light professional design, verified-green brand, refined typography.
Landing page rebuilt. Fixed minimal-mode CI: fail_proof_bad's bug is
only findable by proof, so without z3 it is expected to run.

## 2.2 - Out-of-the-box readiness
velaris doctor (self-diagnosing setup with exact fixes), velaris new
(scaffold a project that runs), standalone executables for
Windows/Linux/macOS built and attached to every release (no Python
required), SECURITY.md with soundness-is-security policy, issue
templates, and a semver stability promise in the README.

## 2.1 - Documentation site
build_docs.py generates docs/: landing page, tutorial, a library
reference parsed from stdlib/std.vel by the real compiler (contracts
shown), an error index scraped from velaris.py (cannot go stale), and
the playground. Built in CI; one click from GitHub Pages.

## 2.0 - The builtins keep the language's promise (BREAKING)
to_int, get-on-a-map, read_file, and fetch are now fallible: they must
be called through check or try, and their failures can finally be
handled instead of killing the program. Migration is compiler-guided -
error E520 points at every call needing a wrap. get on a LIST is
unchanged (bounds are the prover's domain, proven at compile time).
New: get_or(m, key, default), a total map lookup. All examples
migrated; guess.vel now survives typos, net.vel survives outages, and
the ledger's loader shrank.

## 1.20 - sort_by + ledger reports
std.vel gains generic sort_by(xs, key) - sort anything by an Int key
function. The ledger uses it for a new report command: sorted-by-amount
listing with biggest, smallest, and totals. The CI session exercises it.

## 1.19 - Standard library sprint
std.vel grows to sixteen functions, all in Velaris: sort (ensures
is_sorted(result)), min/max (ensures membership), sum, keep_if,
count_where, join, range_list, is_sorted, insert_sorted; apply_to_each
and reverse rewritten with typed lets, dropping their nonempty
requirements. Library requires are enforced at importer call sites.

## 1.18 - Float proofs (real IEEE-754)
Float promises proven in Z3's floating-point theory - bit-for-bit the
machine's arithmetic. The prover refutes real-number identities that
rounding breaks, with the exact double as counterexample. FP queries
get a bigger solver budget; integer proofs stay instant.

## 1.17 - Failure-aware proofs
The prover understands fail / check / try: promises on 'or fail'
functions are proven for every returning path, fail-guards become
facts on those paths, and fallible callees' promises flow through try
and check. CI actions bumped past the Node 20 deprecation.

## 1.16 - Quantified list proofs
`all_of` / `any_of` with a predicate function; in contracts they become
Z3 foralls/exists with the predicate's body symbolically inlined.
Fixed a latent soundness-of-reporting hole: an untranslatable
`requires` now aborts the proof instead of being silently dropped
(dropped premises manufacture false counterexamples).

## 1.15 - Native Float and Bool
Typed LLVM codegen (f64, typed allocas/boundaries); division stays
interpreted so divide-by-zero is always a clean error;
differential-tested against the interpreter.

## 1.14 - Record proofs
Symbolic records (one Z3 value per field): field promises proven,
record-aware summaries, records printed in counterexamples.

## 1.13 - The first real app
examples/ledger.vel expense tracker; chars/file_exists builtins; typed
let enabling empty [] and {}; order-flexible signature clauses;
scripted-stdin testing so interactive apps run in CI.

## 1.12 - Continuous integration
GitHub Actions matrix (Linux/Windows x 3.10/3.12 x full/minimal deps),
dependency-aware suite, CHANGELOG, CONTRIBUTING.

## 1.11 - Language server
`velaris lsp`: standard LSP over stdio. Effect/type errors on every
keystroke, full pipeline with Z3 proofs on save; per-file diagnostics
(bugs in imported files squiggle in those files). Dependency-free VS
Code client bundled in `editor/vscode`.

## 1.10 - Formatter
`velaris fmt` (in-place, `--stdout`, `--check`). Comment-preserving,
idempotent, proven meaning-safe by re-running the whole suite on
formatted code. All repo examples reformatted.

## 1.9 - REPL
`velaris repl`: loose lines run immediately; fn/record/import
definitions pass effects, types, and proofs before joining the session.
CLI subcommands (run / repl / version). Unknown functions became a
friendly E200 everywhere.

## 1.8 - Real installation
`pip install ".[full]"` and a `velaris` command. Standard-library
search path: `import "std.vel"` works from any folder.

## 1.7 - Generics + first stdlib
`for any T` with call-site inference and clear conflict errors
(bindings shown). `stdlib/std.vel`: first/last/reverse/index_of/
contains_item/apply_to_each - written in Velaris.

## 1.6 - First-class functions
`fn(Int) -> Int` as a type; pass by name; call through parameters.
Only pure functions travel as values, so nothing is smuggled.

## 1.5 - Unignorable failure
`-> Int or fail`, `fail "reason"`, mandatory `check { ok / fail }`
handling, `try` propagation. Ignoring failure is a compile error.

## 1.4 - Maps
`{"a": 1}` typed `Map of K to V`; get/has/put/keys/length; typed keys
and values; clean E610 for missing keys.

## 1.3 - Float
Decimal numbers with NO silent Int/Float mixing - conversion is
explicit (`to_float`, `round`). Proper negation node.

## 1.2 - Browser playground
The real compiler running in-browser via Pyodide. Zero install.

## 1.1 - Escapes + editor
String escapes (\n \t \" \\) with friendly E002; VS Code syntax
highlighting.

## 1.0 - Testers' release
Multi-error reporting (all broken functions in one run, JSON array for
agents), `to_text`, `--version`, tutorial.

## 0.x - The climb
0.1 effects (io) - 0.2 effect split (io/net/fs/clock/rand) - 0.3 type
checking - 0.4 loops - 0.5 contracts (requires/ensures) - 0.6 lists,
and/or/not, negatives - 0.7 Z3 compile-time proofs - 0.8 modular
verification with sound false-alarm discipline - 0.9 LLVM native
compilation (~10,000x on hot loops) - 0.10 loop invariants - 0.11 real
HTTP fetch - 0.12 interactive input - 0.13 list proofs via array
theory with bounds obligations - 0.14 else-if, %, text tools - 0.15
records - 0.16 imports with per-file error blame.
