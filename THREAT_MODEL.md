# Threat model

What Velaris defends against when it runs a program somebody - or
something - else wrote, what it does not, and what to do about the
gap. Written for the person who has to decide whether agent-written
code may run on a machine they are responsible for. Every claim here
names the suite that tests it; the numbers come from
[benchmark/RESULTS.md](benchmark/RESULTS.md), which one command
regenerates.

## What Velaris is for

A model hands you a script. You want to run it without reading it
line by line, and you want the things it can do to be bounded by what
you said, not by what it says about itself. Velaris is a small
language in which a function's signature declares the effects it may
perform, the failures it may raise and the promises it keeps, and a
runtime that refuses any effect outside the budget the operator set.

It is not a general sandbox. It bounds programs *written in Velaris*;
it does nothing for a Python or shell script the same model might
write instead.

## The trust boundary

| Party | Trusted? | What that means |
|---|---|---|
| The operator | yes | Sets the budget (`--allow`, `--deny`, `timeout`, `max_memory_mb`) and decides what to do with the output; on the doors, sets the ceilings no caller may exceed (`--max-allow`, `--max-timeout`, `--max-memory-mb`). Everything below depends on the budget being narrower than "everything", and from 5.0 an operator who sets nothing gets `io` rather than everything - the widening is the deliberate act, not the narrowing. |
| The program | no | Written by a model or a stranger. Its `uses` clauses, its contracts and its comments are claims the compiler checks; the runtime enforces the operator's budget regardless of them. |
| The compiler and runtime (the `velaris` package) | yes | One package (one file, `velaris.py`, until 8.2), in the same process as the program it runs, or in a child process when a time or memory limit is set - a fresh one per run, or a pooled worker under one fixed budget (3.1). A defect here is a defect in the guard. The suites below exist because of that. |
| The host Python and operating system | yes | The interpreter runs on CPython; the memory cap is the OS's address-space limit; the timeout kills a process. None of these are hardened by Velaris. |
| Python modules granted through `ffi:` | yes, in full | A granted module can do whatever that module can do. Granting `ffi:subprocess` is granting a shell. |
| A caller of the HTTP door (`velaris serve`) | only with the token (3.4), and only as far as the ceilings (4.0) | Anyone who presents the bearer token may send programs, up to the door's `--max-allow` (`io` unless the operator raised it), `--max-timeout` and `--max-memory-mb` (30 seconds and 512 MB unless raised); anyone who does not gets a 401 and nothing else. One token is one principal: the door cannot tell two holders apart. From 8.1 a request's imports stay inside the directory the door serves (`--root`), its checks and audits stop at the check ceiling, and all requests with the token together get at most `--rate-limit` a minute. |
| A caller of the MCP server | as far as the ceilings (3.4, 4.0) | Whoever the MCP client lets drive the server - in practice the model - may ask for any budget up to the server's `--max-allow`, which is `io` unless the operator raised it, and for any time and memory up to `--max-timeout` and `--max-memory-mb`. |
| A change to the repository's code | only inside the declared surface (4.0) | When a repository commits `velaris.capabilities` and runs `velaris capabilities check` in CI, a change that needs more than that file declares fails, whichever commit brought it; widening the surface means editing the file, in review. |
| An MCP tool's description | checkable (3.4) | The client shows it to the model, and the model follows it. `velaris mcp-verify` holds what a running server says against the manifest the release workflow signed. |

The budget is enforced inside the interpreter loop at the moment an
effect is attempted, and a refusal (E310, E311, E313, E314, E315) is
not a failure the program can `check`; it stops the program. The one
catchable case is a redirect to a host outside the grants: the program
did not choose it, so the request fails and the program hears why. `check_sandbox.py` holds
the escape attempts that established this, including a helper two
layers down and a program that tries to catch the refusal and carry
on.

## What it defends against

| Threat | Mechanism | Tested by |
|---|---|---|
| A program that reads or writes files, reaches the network, asks the clock, draws randomness, or calls Python when the operator did not allow it | The effect budget: `--allow io` - and, from 5.0, no `--allow` at all - refuses `fs`, `net`, `env`, `clock`, `rand` and `ffi` at the call, whatever the source declares, and the refusal cannot be caught. The refusal names the effect, what the run does allow, and the flag that would grant it | `check_sandbox.py` - 39 escape attempts refused, each with the code it must carry (from 4.1), 19 honest programs still run, four of them added in 5.0 for the default budget and two in 6.0 for `declassify`; `velaris conformance` holds the 40 of them that need no Python host and no default to velaris-spec's corpus, which any implementation can run |
| A program that reaches a Python module outside the ones the operator named | The module allow-list: `--allow io,ffi:math` refuses `ffi:os` with E311, through `py`, `py_json`, `py_new`, a submodule path, and the bounded child process. From 3.3 the whole dotted path a call names is checked, not only its module: the attribute chain is walked step by step and any object owned by a module outside the grants is refused, naming the module actually reached, so `py("json", "codecs.encode", ...)` under `ffi:json` is E311 for `codecs`. An object whose owning module cannot be determined is refused rather than allowed | `check_sandbox.py` - the module list, a submodule path, codecs through json, os.system through os, importlib to another module, a builtins type reached through a value, a `__globals__`/`__class__` traversal, and a foreign object exposed through a handle, all refused; a deep attribute inside the granted module (`json.decoder.JSONDecoder`) and a two-module grant still run |
| A program that reads or writes a file outside the directory the operator named, or writes when only reading was granted | Scoped fs grants (3.0): `fs:read:./data`, `fs:write:./out`. Every path is resolved with `realpath` before comparison, so `..` and symlinks cannot leave a prefix; E313 names the path and cannot be caught | `check_sandbox.py` - a read outside the prefix, a write under a read-only grant, a `..` escape, a symlink escape (where the system will make a link), and an existence check a write grant allows (4.1); `check_library.py` - the same through `velaris.run` and through the HTTP door's ceiling |
| A program that reaches a host, or a port, the operator did not name | Scoped net grants (3.0): `net:api.example.com:443`, `net:*.example.com` (one label). The URL's host and port are checked before any connection; E314 cannot be caught. A redirect to an ungranted host fails the request as a catchable failure naming the target | `check_sandbox.py` - a host not in the list, a port not in the list, a wildcard that must not match its parent domain, a redirect to an ungranted host; `check_fallible.py` - the redirect failure formats and is caught |
| A program that reads the environment under a budget meant for the console | `env` is its own effect (3.0): `env()` needs `uses env`, and `--allow io` refuses it with E310. A program written for 2.x that calls `env()` under `uses io` alone is refused at compile time with "env() now needs 'uses env'" | `check_sandbox.py` - `env()` with only io granted; `check_library.py` - the same, and the exact message |
| A program granted `env` or `fs` printing, writing, sending or handing to Python the secret it read, or working it out and printing that | `Secret of T` (6.0, SPEC.md 3.1): `env()` and `read_file_secret()` return one; every builtin that declares an effect refuses an argument carrying one (E560, naming the value and where the secret came from), and so does every builtin that can fail, because a failure's reason is text the program can print; a list, map or record holding one carries it; every pure operation keeps it, a comparison included, so `key == c` is a `Secret of Bool`; and nothing branches on one (E563, from 7.0) - which is what stops the loop that would read a key out a character at a time. `declassify(value, reason)` is the only way out: `uses declassify` in the signature, a reason written in the call, and the `declassify` grant at run time, with `velaris audit`'s `secrets` section reporting every one with its reason - so "does this program ever let a secret out" is answered without running it. What this still does not bound is under **What it explicitly does NOT defend against** below | `check_secret.py` - 76 checks: every emitting builtin and every fallible builtin refused, a record, a list, a map and a nested record refused whole, a secret through two helpers, through a generic function of any kind - a pure one hands the answer back just as readily - through a `fail` reason and through a signature that does not say Secret; the extraction loop refused at the branch and the same program accepted with `declassify` and recorded in the audit; `declassify` refused without the effect, without the grant and without a written reason; the audit's `secrets` section for each shape; `velaris trace` and a broken promise printing `<secret>`; and honest programs that still run. `check_sandbox.py` - `declassify` refused by the budget (E310) and allowed with the grant; `check_refusals.py` - E560, E561, E562 and E563 each for the right reason |
| A program that does more file or network operations than the operator expected | Counts (3.0): `fs:read:./data@50`, `net:api.example.com@100` - at most that many operations of that effect in the run; E315 cannot be caught. A budget with no count is a budget on what, not on how much | `check_sandbox.py`, `check_library.py` - the count reached on fs and on net; from 4.1, `@0`, and a count spent by an operation that then failed |
| A program that never ends, or eats memory | `velaris.run(timeout=, max_memory_mb=)` runs the program in a child process killed on breach and reports E610 or E611. On the MCP server and the HTTP door the operator sets both as ceilings, `--max-timeout` and `--max-memory-mb`, 30 s and 512 MB when not given: a run that names neither gets them, and a caller asking for more is refused like an over-wide budget (4.0). Before 4.0 a caller could send any timeout and any memory cap and have it | `check_library.py` - a program that never ends is stopped in 2 s on every platform; a program that doubles a text is stopped at 150 MB, asserted wherever the mechanism holds: Linux (`RLIMIT_AS`) and Windows (a job object, 3.1), best-effort on macOS - see below; on both doors a request for more time or memory than the ceiling is refused, less runs, and a run naming no timeout stops at the operator's. `check_pool.py` asserts both limits again on a pool |
| A promise that is false - a contract the code does not keep, a division by a value that can be zero, a list read that can go past the end | The prover: `requires`/`ensures`/`invariant` are checked by Z3 before running (E700, E701, E703, E705, E706) with an exact counterexample; a premise it cannot translate abandons the proof to a runtime check rather than proving with a gap. Every query is built from the syntax tree through Z3's API, never parsed from text, and from 8.1 every name the prover makes up for its own values begins with `!` or contains `#`, which no identifier can - until then a parameter named `__g_result_1` was the same Z3 value as a call's result, and a false promise came back proven (advisory-prover-names.md) | `check_refusals.py` - 21 wrong programs each refused with the specific code; `check_prover_lies.py` - false promises that must never be proven, the prover's old names among them, and identifiers and text spelled like SMT-LIB; `fuzz_native.py` - random programs run natively and interpreted must agree exactly, so a proven-and-compiled function cannot behave differently from an interpreted one |
| A failure the program ignores - a parse, a map lookup, a pop, a network call, a Python call that can fail | Fallibility in the signature (`or fail`), and E520 for any fallible call not handled with `check` or passed up with `try` | `check_fallible.py` - every builtin in `FALLIBLE_BUILTINS` is refused when ignored and formats its failure when caught; a builtin added without a recipe fails the suite |
| A loop that never ends, before running it | The termination rule (SPEC.md 9.5): a loop is `terminates` only when a counter moves one step toward a limit the body leaves alone, `unshown` otherwise; reported by `audit` as `loops_unshown` and refused by `check --strict` as E612 | `check_termination.py` - 44 adversarial loops, each with its required verdict; the rule was wrong twice while being built, both times refusing a loop that ends, never the reverse |
| One program's leftovers becoming the next program's starting state, when runs share a process | `velaris.Pool` (3.1) fixes the budget when the pool is made and re-asserts it before every program; a worker is killed and replaced unless the run finished cleanly; a reused worker has every module-level mutable reset - arguments, Python handles, native engines and their arena, the tracer, the budget and its counts, and the working directory, environment and recursion limit a granted `ffi` module can change | `check_pool.py` - 39 checks, including a program that widens its own budget through `ffi` and cannot widen it for the next, a handle nobody closed, args from a previous run, a counted grant spent per program, and a program writing straight at file descriptor 1 |
| Not knowing what a program does before running it | `velaris audit`: effects, Python modules named, proven share, what can fail, loops not shown to end, functions that promise nothing about the data they handle, and the exact budget to run it under | `check_library.py` - the library and the MCP server report the same audit; the format is versioned (`velaris.audit/1`) |
| Source written to stall or bloat the checker - a promise the prover spends its whole budget on, an expression the checker takes minutes to read - sent to a platform that audits before it runs | From 8.1 `velaris.check`, `velaris.audit` and `velaris.attest`, the doors' check and audit, and `run(timeout=...)`'s compile all run in a child under a ceiling: 60 seconds and 2048 MB unless raised, as `velaris check` has had since 8.0 (whose memory cap took hold only on Windows until 8.1; on macOS a cap is best-effort, and the clock is what holds). Past it the answer is E613 or E614, and an audit that stopped says `ok: false` | `check_library.py` - an inflated expression and a crafted float contract stopped through the library, `Pool.check`, `run(timeout=)`, `attest`, the command line, the HTTP door and the MCP server; `check_platform.py` - the reference platform answers a stalled audit with 422 and stores nothing |
| A program sent to a door, or to a platform's audit, reading a file on the host through an import | From 8.1 an error inside an imported file that is not `.vel` names the file and none of its content, everywhere; the HTTP door and the MCP server compile a request as a file in the directory they serve and refuse (E515), before opening it, an import that resolves outside that directory or to a file there that is not `.vel`; the library does the same with `import_root=`. Until 8.1 `import "/home/me/.env"` answered `found 'API_KEY'` (advisory-import-read.md) | `check_library.py` - a relative escape, an absolute path, a non-`.vel` file inside the root and a symbolic link out of it, each E515 with nothing of the file in the answer, through the door, the MCP server and the library; `check_adversarial.py` I1, I2 |
| Not knowing what one run did, or who says so | `velaris.receipt/1` (8.1): the program and its imports by the digests `attest` uses, the budget, every refusal by code, effect and line, every declassification by reason and line, the run's parameters, how it ended and how long it took, as an in-toto Statement for a signature to bind. It holds no value the program handled. A run killed by its limit still has one, marked incomplete | `check_library.py` - receipts from `run`, a pool, the command line and both doors, validated against velaris-spec's schema, a declassified secret and a refused sink built from one kept out, a killed run's declassification kept; `check_adversarial.py` R1-R5, a forged receipt file among them; the release workflow signs one with cosign and sigstore-python and verifies both |
| A caller of the HTTP door guessing the token, or flooding it | From 8.1 at most `--rate-limit` requests a minute (600 by default) for the token, and the same for each address without it; a wrong token or a forwarded-for header gets no allowance of its own, and cannot spend the token's. The token is compared with `secrets.compare_digest` over sha256 digests | `check_library.py` - 429 once an address's allowance is spent, the token's allowance untouched by it, and the comparison watched; `check_adversarial.py` D1 |
| An ejected program changing what its next run is | `velaris eject` (8.1) refuses a budget whose writes reach the ejected directory; its `main.py` refuses one that reaches its own directory or a directory Python imports from where it is launched, refuses a runtime that differs from eject time, and refuses `--allow`, `--deny` and a `--receipt` inside itself | `check_eject.py`; `check_adversarial.py` E1-E6 - grants written several ways, a runtime with its budget check removed, a planted `velaris.py` |
| Not knowing which source an audit describes, or who says so | `velaris attest` (4.2): the audit in an in-toto Statement whose subjects are the audited file and its imports by sha256, for a signature to bind; a file that changes while it is attested is refused | `check_library.py` - the Statement validates against in-toto's Statement v1, the capability/v1 predicate and `velaris.audit/1` schemas, its audit is `audit()`'s field for field, each digest is the file's; the release workflow signs one with cosign and with sigstore-python and verifies both as itself |
| Anyone who can reach the HTTP door's port running programs through it | A bearer token on every endpoint but `GET /health` (3.4), from `--token-file`, `VELARIS_TOKEN` or made and printed once; never taken as an argument. Compared in constant time; a missing, wrong or misplaced token is the same 401 on every path, unknown ones included. `VELARIS_TOKEN` is removed from the environment before any worker starts, so a program granted `env` cannot read it. `--no-auth` is refused on any host but `127.0.0.1`/`localhost` and warns on every start; without a token, a request must name a loopback `Host`, carry no foreign `Origin` and post JSON, which keeps a browser page off the door | `check_library.py` - no token, a wrong one, another scheme, a bare `Bearer` and the token in the query string are each 401 with identical bytes; `/card` and an unknown path are 401 too; the token is accepted; a program cannot read `VELARIS_TOKEN`; the made token is printed once and never logged; `--token` in both spellings and a bare value are refused without being repeated; `--no-auth` is refused on `0.0.0.0`, `::1` and another address, and on loopback refuses `text/plain`, a foreign `Host` and a foreign `Origin` |
| A caller of either door asking for more than the operator allows | `--max-allow` on the MCP server (3.4) and the HTTP door, the same grammar and the same `Budget.covers`; `io` on both when the flag is absent - on the HTTP door from 4.0, where before a door started without it granted every effect, `ffi` included; a request past it at any level is refused with the ceilings named | `check_library.py` - fs and ffi refused under the default on both doors; a narrower path passes while a wider path, unscoped `fs`, another host, a larger count and another module are refused under a scoped ceiling; a ceiling that does not parse stops the server |
| Capability added to a repository a little at a time - many commits, each harmless on its own, that together reach a new host, path, module or effect | The capability ratchet (4.0): `velaris.capabilities` records the surface the repository declares - every grant its programs need, the most fs and net operations a run can perform, and each function's effects - and `velaris capabilities check` fails when the code needs more. The comparison is with that file, never with the previous commit, so a widening merged once keeps failing until someone edits the file, and forty small steps are reported as their whole sum. The GitHub Action runs it when the file exists, and fails a pull request that deletes it | `check_ratchet.py` - a six-commit history whose sixth commit reaches a new host three calls down, failing only there and naming the file, function, line and call chain; a widening through an import and through the standard library; a path prefix, a count, a host made a wildcard, a computed URL, path and module; an effect added to a function while the program's grants stay the same; and changes that must pass - narrowing, reordering, reformatting, a file with no effects, a literal moved into a variable |
| A Velaris dependency whose new version can do more than the old one - a new effect, a host or path inside an effect it already had, a Python module, more operations, a function that gained an effect - while the code that calls it stays the same and still compiles | `velaris deps-diff` (7.1) derives both versions' declared capability surfaces and holds the newer to the older with the ratchet's rules, naming what was gained and the file, line and call that introduced it. For a package that is not Velaris it reports install-time scripts added or changed and declared dependencies, and says the surface is unknown - see below for how little that is. The Action's `deps-diff` input runs it on every upgrade a pull request makes in a lockfile | `check_deps.py` - a library gaining net, a host inside net, a count, a module, a function's effect; one that narrows and one only rewritten, both not flagged; a JavaScript package whose new source reaches the network, reported as unknown with no host read off it; install scripts added and changed, including a changed file behind the same command and a registry manifest that hides the tarball's script; a version that does not exist; the SARIF; the pull-request comment edited, not duplicated; and benchmark category 12's four programs |
| A tool description or schema changed under the client (tool poisoning, OWASP MCP Top 10 MCP03) | A manifest of every MCP tool's name, description hash and input-schema hash, made by the release workflow from the server in the published wheel and signed with sigstore; `velaris mcp-verify` checks the signature and reports every tool that differs, was added, or is missing | `check_library.py` - a server with a changed description, a changed schema and an added tool is reported for each, with exit 1; a manifest without a signature bundle, or with one that does not verify, stops the check (exit 2); the release workflow runs `mcp-verify` with the real signature against the server in the wheel before attaching the manifest |
| Not knowing what the doors were asked to do | One JSON line per call on both doors (3.4): when, which door, the endpoint or tool, the outcome, the duration, the budget granted, the effects performed, what was refused and by what, and the source's sha256 - never the source or the token. No setting turns it off | `check_library.py` - one line per call on the HTTP door and on the MCP server, with neither the token, a wrong token nor any source in the file |

On the 67-program benchmark (59 dangerous, 8 harmless), Velaris caught
57 of the 59 - 45 before running and 12 while running - and flagged
none of the 8. Under the same rules Deno caught 35 (5 before, 30
during) and plain Python 28 (all while running). The two misses are
named below. Three of the 59 (category 12, 7.1) are dependency
upgrades, and Velaris's catch before running there is `velaris
deps-diff`, whose limits are also below.

## What it explicitly does NOT defend against

**No longer here: the permissive default. Fixed in 5.0, 2026-09-12.**
Until 5.0 a run given no budget - `velaris program.vel`, or
`velaris.run(source)` with no `allow` - got all seven effects, and this
repository said so plainly: the README's related-work paragraph and the
paper both conceded that Velaris's command line granted every effect
when no budget was given, where a WASI module given nothing reaches
nothing. That was true until 5.0. It is not true now. The default is
`io` - the console, and nothing else - in the command line, the
library, `Pool` and both doors, and `--allow all` is the one way to ask
for what a run used to get, which writes a line to stderr when it is
used. The old text is not deleted anywhere it appeared; it is dated.

**Moved, not removed: secrets.** Until 6.0 this section had nothing
about the *values* a program handles, and the residual-risks table
below said only "do not grant `env` to code you have not read." From
6.0 a value read by `env()` or `read_file_secret()` is a
`Secret of Text` the compiler will not let reach anything that emits
it, and from 7.0 it will not let a program branch on one either; that
moves to **What it defends against** above. What stays here is
everything those rules do not cover, and it is more than one line:

- **Only values the type system can see.** A secret that arrives any
  other way is an ordinary `Text` with no protection at all: read
  through `read_line`, passed in through `args()`, fetched from a
  vault over `net`, returned by a granted `ffi` module, or hard-coded
  in the source. `Secret` marks two builtins' results; it does not
  discover secrets. A program that reads a password from standard
  input can print it, and nothing here stops that.
- **Non-interference.** A comparison over a secret gives a `Secret of
  Bool`, nothing prints one and nothing branches on one (E560, E563),
  so a program cannot read a secret out a character at a time and then
  say what it read. That *was* possible in 6.0.0, for one day, and
  closing it is what 7.0 is - see the CHANGELOG. What remains
  unbounded is everything a program controls that is not a value: how
  long it runs, how much it allocates, whether it stops at all. This
  is not a non-interference result and must not be described as one.
- **A promise, once per run.** A `requires`, `ensures` or `invariant`
  may be a `Secret of Bool`, because a broken promise stops the run,
  cannot be caught and cannot accumulate - so it is a statement about
  a secret, not a branch on one. An operator who runs the same program
  many times can still learn one bit per run from whether it stopped.
  If that matters, do not grant `env` at all.
- **Where a declassified value goes.** `declassify` returns an
  ordinary value. After it, the type system has nothing more to say:
  the audit records that it happened and why, and whether the reason
  was true is a person's judgement.
- **What a granted `ffi` module reads for itself.** A Secret is a
  compile-time distinction with no runtime representation, so Python
  code inside a granted module reads the environment directly if it
  wants to. `ffi:os` is the environment, whatever the Velaris types
  say.

What follows is what is still not defended.

- **Anything a granted `ffi` module can do.** `ffi:os` is the whole
  operating system as the current user. The allow-list narrows which
  modules a call may reach; it does not narrow what a module does. Plain
  `ffi` grants every module. From 3.3 the reach check bounds a scoped
  grant to the module actually reached along the attribute chain, so a
  granted module is no longer a door into the other modules it imported;
  but within a granted module, that module's full behaviour is still
  granted. Where the owning module of an object reached along the chain
  cannot be determined, the call is refused rather than allowed - the
  bound errs toward refusing more, not less.
- **Native code inside a granted module.** A granted module may be, or
  may ship, a compiled extension (`.so`/`.pyd`/`.dylib`), which has no
  source to read and whose behaviour a budget does not constrain any more
  than it constrains Python. From 8.0 `velaris audit` reports this per
  granted module in `ffi_native` - `"native"` when it finds a compiled
  extension on disk (found without importing the module), `"unknown"`
  otherwise, and never `"false"`, since a pure-Python module can import a
  native one without that being visible. The audit names the risk; it
  does not remove it. Grant native modules only when you would grant the
  machine.
- **Side channels.** Timing, CPU load, cache effects, the size or
  timing of console output. Nothing measures or bounds them.
- **Resource use below the limits.** A program may run for 29 of its
  30 seconds and hold 511 of its 512 MB, every time it is called. The
  limits stop a runaway; they do not ration.
- **Rate, and the meaning of a request.** A count (`@100`) bounds how
  many operations a run makes, not how fast, how large, or whether a
  request is a GET or a POST. A plain `net` grant is any number of
  requests to any host; a plain `fs` grant is any path the OS user can
  reach. Narrow them.
- **What a granted host does with a request.** The grant names a host
  as written; where the name resolves is DNS's business, and what the
  host does with the data it receives is outside the model.
- **Closed in 8.0.0: the connection endpoint when a proxy is set.**
  Through 7.1.x the network client honoured an ambient `HTTP_PROXY` /
  `HTTPS_PROXY`: a `net:` grant checked the URL's host, but the socket
  then went to the proxy, which need not be a granted host, so an
  `http://` request carried its payload to the proxy. The grant bounded
  the URL string, not the peer. From 8.0 `guarded_opener` builds the
  opener with ambient proxies **disabled**, and honours one only when the
  proxy's own host:port is itself inside the net budget; a proxy the
  budget does not cover is refused (E317, uncatchable), naming the proxy
  and the grant that would allow it. `velaris add` ignores ambient
  proxies too. The grant now bounds the socket's peer, not only the URL -
  this moves to **What it defends against**. What is still not bounded is
  what a *granted* proxy does with the request, like any granted host.
- **What a granted path contains.** A hard link inside a granted
  directory is that directory's content. A file system changed by
  another process between the check and the open is outside the
  model; a Velaris program has no threads, so it cannot race itself.
- **Still within `io`:** `args()` and `read_line()`. Command-line
  arguments and standard input are the console.
- **Logic errors with no contract.** A function that returns the wrong
  number and promises nothing is correct as far as the compiler knows.
  Benchmark row 04c (a loop that stops one item early) is this, and
  is a miss. The audit lists such functions under `contract_coverage`
  so the gap is visible; it does not close it.
- **The meaning of text.** A program that prints `rm -rf build` for
  its caller touches nothing (benchmark row 09c, a miss); a program
  that prints the same words in a warning is harmless (row 10d). No
  effect system can tell them apart, and Velaris does not try.
- **Code not written in Velaris.** A model asked for Velaris may hand
  back Python. The guard applies only to what the Velaris runtime
  runs.
- **Memory caps on macOS.** `max_memory_mb` uses the OS address-space
  limit (`RLIMIT_AS`) on POSIX and, since 3.1, a job object with
  `JOB_OBJECT_LIMIT_PROCESS_MEMORY` on Windows - where the child is
  created suspended, put in the job and only then resumed, so nothing
  runs outside the cap. It is enforced on Linux and on Windows. On
  macOS it is best-effort: the limit is set but not reliably honoured,
  and in the suite the runaway program reached the timeout instead. If
  the Windows job object cannot be made, the cap is recorded and not
  enforced rather than the run failing, which is what a Windows before
  3.1 always did. `velaris.memory_cap_is_enforced()` answers for the
  machine you are on. The timeout is enforced on every platform.
- **A pool worker's budget, once chosen.** A `Pool` fixes its budget
  when it is made. That is the point - it is what lets a worker serve
  the next program safely - but it means a caller who wants a narrower
  budget for one program must make another pool, and a caller who
  hands the same pool to two tenants has given them the same budget.
  A worker is also a process that outlives one program: everything a
  granted `ffi` module could do to a fresh process, it can do to a
  worker, and the pool's promise is only that the *next* program does
  not inherit it. `check_pool.py` is the whole of that promise.

- **The door's token, once it is out.** The token is a password with
  no user behind it: whoever holds it has every grant the ceiling
  allows, and the door cannot tell holders apart or revoke one of them.
  From 8.1 it limits how often the token is used, all its holders
  together; one holder can spend that allowance for the rest. It is only
  as secret as the file or
  environment it came from. A program the ceiling allows to read the
  token file can read it, and one allowed `net` as well can send it
  away. The door speaks plain HTTP: on any address but loopback the
  token crosses the network in clear unless a TLS proxy sits in front.
  A made token printed to a stdout that something writes to a file is
  in that file.
- **`--no-auth`.** Any program on the machine, run by any user, can
  send the door programs. The checks that replace the token stop a web
  page in a browser, not a local process.
- **The MCP server's caller.** The ceiling bounds what `velaris_run`
  grants, not who calls it: the client decides that. A ceiling raised
  to `ffi` is `ffi` for whatever the model is told to do.
- **What `mcp-verify` does not see.** It compares what a server says
  about its tools with what was signed; it does not watch what the
  server does, and a server that returns the signed descriptions and
  behaves differently passes. It checks at the moment it runs. If both
  the `velaris` package and `velaris_mcp.py` in an installation were changed,
  the checker was changed too - verify the wheel (SECURITY.md), or run
  `mcp-verify` from a separately verified Velaris.
- **What the capability ratchet does not see.** It reads the program
  text. What a granted `ffi` module does once called is not in the
  text: `ffi:os` in the baseline is the operating system, and a program
  that newly calls `os.system` through it is inside the surface. A path
  or URL built while running is recorded as the unscoped grant, so it
  is caught, but only as "any path" or "any host". Paths are compared
  as text, never against the file system, so a symbolic link inside a
  recorded directory is that directory's content - the budget, which
  resolves every path, is what stops it at run time. A function is
  known by its file and name: one renamed while it gains an effect is a
  new function, held to its program's entry and the surface, not to
  what its old name declared. A file that does not compile adds
  nothing until it does, since it cannot run. The count bound is
  derived by fixed rules, and a loop whose number of turns is not
  written in the text has no bound. And the ratchet guards nothing if
  it is not required: a pull request that edits `velaris.capabilities`
  has accepted a widening, and the review of that edit is the control.
- **What `velaris deps-diff` does not see.** It sees declared surface,
  not behaviour. For a Velaris library that is the surface the ratchet
  derives from the text, with every limit of the ratchet above: what a
  granted `ffi` module does, a path or URL built while running seen
  only as "any path" or "any host", a function renamed while it gains
  an effect. For a package that is not Velaris it sees almost nothing.
  It reads the install-time scripts and the declared dependencies, says
  whether a script was added or changed - not what the script does -
  and reports the capability surface as unknown, with exit status 3,
  which is not a pass. It would not have caught postmark-mcp 1.0.16: by
  Koi Security's account that release changed only the code that sent
  the copy, which adds no install script and no dependency, so the
  report would have been "nothing gained that could be seen, surface
  unknown". Beyond that: it reads only the lockfile formats it names,
  and lists any other changed lockfile as not read; an entry resolved
  from git, a path, or a private registry or index is left out rather
  than compared with a public package of the same name; a dependency new in
  the upgrade has no earlier version and is listed, not examined; it
  compares at most 30 upgrades in one pull request and names the rest;
  it cannot read a version a registry has removed; it checks downloads
  against the digests the registry publishes, which a compromised
  registry would publish too; and in CI it informs and never fails the
  job, so what it finds is worth what the reading of its comment is.
- **What an attestation does not say.** `velaris attest` signs
  nothing: an unsigned Statement is a claim anyone could write, and a
  signed one says only that its signer ran this producer on those bytes
  and got this audit. It says no more than the audit - not that the
  program is safe, that the audit is right, or that any runtime will
  enforce its `safe_command` - and whatever the audit could not
  determine, it could not either.
- **What a receipt does not say.** A receipt (8.1) holds no value the
  program handled, and nothing more careful than that: it holds what the
  program did, and a program controls some of that without handing it a
  value - its exit status, the line at which it was refused or stopped,
  how many times it did something, how long it ran. After a
  `declassify`, a program can choose any of those from the declassified
  value. A declassification's reason is text the program's author wrote,
  and nothing checks it. Velaris signs no receipt, and a signed one says
  its signer ran this Velaris on these bytes and saw this run - as strong
  as the machine it ran on, with `confinement: "none"` saying the budget
  was the only boundary, and silent about any other run. A receipt marked
  `complete: false` lists what the killed worker reported, and counts at
  least that. A receipt written by `--receipt` is written when the run
  ends; a process killed from outside writes none.
- **What ejecting does not keep.** An ejected directory runs the Velaris
  it was ejected with, and no later fix reaches it. Its `main.py` checks
  the runtime and the program against their digests and cannot check
  itself: if anything but its owner could have written to the directory,
  compare it with `SHA256SUMS` before running. The proofs recorded in it
  are a record, not something the launcher trusts. Its refusal of a budget
  that writes where Python imports from is made where and when it is
  launched: a directory added to `PYTHONPATH` later is not known to it.
- **A write grant to where Python imports from.** A program allowed to
  write into a directory on some Python's import path - a `PYTHONPATH`
  entry, a site-packages, a user site - can leave a `sitecustomize.py` or
  a module there that the next Python process started with that path runs.
  That is not a Velaris effect, and a plain `velaris program.vel --allow
  fs:write:...` does not look for it; the ejected launcher refuses such a
  budget, and `python -I` ignores `PYTHONPATH` and the user site. Grant
  writes to directories that hold data, not code.
- **What the invocation log does not hold.** The program's source,
  output, stdin and arguments, and request headers, are not recorded;
  what a granted `ffi` module does inside Python shows only as `ffi`
  calls. A refusal names the path or host the program tried, which is
  the program's choice of text. A log written to stderr is kept only if
  whatever runs the door keeps stderr.
- **A tampered compiler.** Velaris is one Python file running in the
  same process as the untrusted program's interpreter. If the file,
  the package or the binary you run has been altered, nothing above
  holds. The release workflow signs every artifact and publishes an
  SBOM; [SECURITY.md](SECURITY.md) says how to verify a download.
  Verify it.
- **The compiler as a target.** Checking runs the parser, the type
  checker and the prover on untrusted source. The prover has a time
  budget per query; the other passes do not, and a hostile source can
  make a check slow or large. From 8.0 `velaris check` and `audit`, and
  from 8.1 the library's `check`, `audit` and `attest`, the doors' check
  and audit, and a bounded run's compile, stop at a ceiling (E613,
  E614); what stays inside the ceiling - 59 seconds of it, every time -
  is still spent. The language server has no ceiling: an editor that opens
  a file written to stall the prover waits for it, and so does a program
  that calls `check(timeout=None)`.
- **Compile-time reads.** `import "path"` reads that file when compiling,
  before any budget applies - the budget governs what a program does when
  it runs. Until 8.1 this section said such a read "reads Velaris source,
  not data". It was wrong: nothing held the path to a `.vel` file, and an
  error inside a file that was not Velaris source quoted what it found, so
  a program sent to a door or a platform could read the first word of a
  file (advisory-import-read.md). From 8.1 that error shows nothing of the
  file, and the doors, and the library given `import_root=`, refuse an
  import outside the directory they serve (E515). Without an import root -
  the command line, and the library by default - an import still reads any
  `.vel` file the process can read, and the audit's `fs_paths`, `net_hosts`
  and `ffi_modules` include that file's literals. Give the library an
  `import_root` for source you were sent.
- **The proof cache: removed in 8.2.** Every proof is made in the
  process that reports on it or runs it, and no proof result is kept
  anywhere between runs, so there is nothing on disk to plant. The cache
  existed from 2.29 to 8.1.1 and held two holes: from **2.29 to 7.1.1** a
  `./.velaris/proofs.json` shipped beside an untrusted program was
  believed ([advisory-proof-cache.md](advisory-proof-cache.md)), and from
  **7.1.2 to 8.1.0** an entry planted in the per-user directory was
  ([advisory-proof-cache-2.md](advisory-proof-cache-2.md)); in both a false
  `ensures` was reported proven and, compiled to native code, ran
  unchecked. `check_adversarial.py`'s `CACHE-1` to `CACHE-10` plant both
  files and hold that nothing reads them.
- **The prover's reach.** Three benchmark rows (03d, 03f, 04e) are
  caught only while running: a division on the unguarded of two
  paths, a remainder inside a loop, a read at `i + 1` in a loop over
  `length(xs)`. The runtime check stopped each; the prover did not
  settle them beforehand. These are limits of the current prover,
  listed in RESULTS.md rather than worked around.

## Known open

The gaps this model does not close, kept as a table so the list is one
place and stays current. None is a defect to be reported under
SECURITY.md's challenge; each is a stated limit of what the effect
budget is. A finding that a guarantee above is *broken* - a "proven"
promise that breaks at run time, or an effect performed outside the
budget - is a different thing, and SECURITY.md says how it is handled.

| Open | What it is | What to do |
|---|---|---|
| Timing and other side channels | How long a run takes, how much CPU or cache it uses, the size or timing of its output - none is measured or bounded, and a program can signal through any of them. Not a non-interference result (7.0 bounds a secret's *value*, not the run's timing). | Do not run code whose timing you must not leak on shared hardware; if one bit per run matters, do not grant `env`. |
| A granted `ffi` module | Within a granted module, that module's full behaviour is granted; `ffi:os` is the operating system as the current user. The allow-list narrows which module a call reaches, not what it does. | Grant `ffi` only when the task needs it, name the modules, and treat the grant as trust in those modules. Never grant `ffi:os`, `ffi:subprocess` or plain `ffi` to code you have not read. |
| Native code | A granted module may be or ship a compiled extension with no source and no runtime bound. `velaris.audit/1`'s `ffi_native` reports where it is found (8.0), and never claims a module is free of it. | Read `ffi_native`; grant a native module only when you would grant the machine. |
| Secrets arriving another way | `Secret of T` marks the results of `env()` and `read_file_secret()` only. A value read through `read_line`, passed in through `args()`, fetched over `net`, returned by a granted `ffi` module, or hard-coded is an ordinary value with no protection. | Run agent-written programs with a clean environment; do not treat a secret from another source as protected. |
| No OS confinement | The budget is enforced by an interpreter written in Python, in a process that also holds the compiler, on a host that trusts that process. It is not an OS sandbox, a network policy or a separate user account. | Put Velaris inside one of those when the stakes warrant it; the budget is a guard against a program doing what it was not asked to, not a substitute for a boundary the OS enforces. |
| What a receipt shows that is not a value | A receipt (8.1) keeps out every value a program handled, but holds its exit status, where it stopped, its counts and its wall time - which a program that declassified something can choose from it. | Do not grant `declassify` to code whose receipts you will share. |
| Writes to where Python imports from | A write grant to a directory on some Python's import path lets a program leave code the next Python process runs. Velaris does not look for this on a plain run; an ejected launcher refuses such a budget where it is launched. | Grant writes to data directories only; run Python with `-I` where you can. |
| An ejected directory | It keeps the Velaris it was ejected with; no fix reaches it, and its launcher cannot check itself. | Eject again after an upgrade; check `SHA256SUMS` when the directory could have been written by someone else. |
| A program that stalls a review | `velaris review` compiles every program under the directory, at the ref and in the working tree, in its own process, with none of the ceiling `check` and `audit` have had since 8.0 and `capabilities check` has had since 8.2.1: a program built to exhaust the type checker holds it, and the Action's pull-request comment step, which runs it, until the job's own timeout (known open in 8.2.1). | Give a job that comments on other people's pull requests a `timeout-minutes`. |
| The user running velaris | The user running velaris is trusted; anything running as that user is that user - the receipts, everything. Such a process can edit the program, the budget, a receipt after it is written, or the installed Velaris itself. The proof cache, which such a process could once write, was removed in 8.2; that does not make anything else the user can write trustworthy. | Run code you have not read as a different user, or in a container or a virtual machine. Do not rely on a report made in an account something else controls. |

## Residual risks, and what to do about each

| Risk | Recommendation |
|---|---|
| A granted module does harm | Grant no `ffi` unless the task needs it, then name the modules (`ffi:math,json`) and treat the grant as trust in those modules. Never grant `ffi:os`, `ffi:subprocess`, `ffi:shutil` or plain `ffi` to code you have not read. |
| Secrets in the environment | Do not grant `env` to code you have not read; since 3.0 an `io`-only budget cannot read it. From 6.0 what `env()` returns is a `Secret of Text` the compiler will not let the program print, write, send or hand to Python, and from 7.0 not branch on either - so read the audit's `secrets` section: `declassifies: false` means no secret leaves, and a `true` names each reason. Withhold the `declassify` grant from code you have not read. Run agent-written programs with a clean environment regardless: the rule covers the values the type system can see, and a secret that arrives through `read_line`, `args()` or a granted `ffi` module is an ordinary `Text`. |
| A secret a program works out one bit at a time | Defended from 7.0, and it was not in 6.0.0: a comparison over a secret is a `Secret of Bool`, which nothing prints and nothing branches on (E560, E563), so the loop that would read a key out a character at a time does not compile. A program that means to look at a secret writes `declassify(key == "", "why")`, which needs the effect, the grant and a reason the audit records. What is still not defended is what a program controls that is not a value - how long it runs, whether it stops - and one bit per run from a broken promise. If that matters, do not grant `env` at all. |
| Data leaves through `net` | Grant hosts, not `net`: `net:api.example.com:443@100`. A host list bounds where, not what; an egress proxy or a firewall rule outside Velaris still belongs under it when the stakes warrant. |
| A program does damage within `fs` | Grant directions and directories, not `fs`: `fs:read:./data,fs:write:./out`. Run in a directory that holds nothing else regardless. |
| Runaway time or memory | Always set both `timeout` and `max_memory_mb`. The MCP server and the HTTP door hold every run to the operator's `--max-timeout` and `--max-memory-mb`, 30 s and 512 MB unless raised (4.0; before 4.0 a caller could ask them for more and get it). The cap holds on Linux and on Windows; on macOS add an OS-level limit or run on Linux. |
| A vendored library changed under you | `velaris deps --verify` in CI: `velaris.lock` records the sha256 of every vendored library and the Velaris that added it, and `velaris add` refuses to replace one with different bytes unless you say `--force`. |
| The result is wrong and no promise catches it | Require contracts on the functions that matter (`velaris proofs --min 80` in CI) and read the audit's `contract_coverage` list. A program with no promises has proven nothing. |
| Output is trusted downstream | Never pipe a program's stdout into a shell or an interpreter. Treat output as data. |
| The HTTP door's token leaks, or the door is reached from a network | Keep the token in a file only the door's user can read (`chmod 600`), outside every path the ceiling grants; do not pass it in a way that ends up in a process list or a log. Bind to `127.0.0.1`; if the door must be reached from elsewhere, put a TLS-terminating proxy in front and keep the network narrow. Give the door the smallest `--max-allow` the callers need - without one it grants `io` only (4.0; before 4.0 it granted everything, `ffi` included). Change the token by restarting the door with a new one. |
| A dependency upgrade that can do more than the version before | For a Velaris dependency, run `velaris deps-diff` on the upgrade - or set the Action's `deps-diff: "true"` - and read what it reports gained before merging. For anything else, read exit 3 and "unknown" as exactly that: pin exact versions, read the package's own diff, and do not take the absence of a gained install script as evidence of anything. |
| Capability added to the repository over many commits | Commit `velaris.capabilities` (`velaris capabilities init`) and make `velaris capabilities check` - or the Action's `capabilities: check` - a required check on every pull request. Treat an edit to `velaris.capabilities` as a widening that needs its own reviewer (a CODEOWNERS entry for the file does this), and read what the Action's comment and `velaris review` say changed. |
| An MCP client lets the model ask for too much | Leave the MCP server at its default `io` ceiling unless a task needs more, then raise it to exactly that (`--max-allow io,fs:read:./data`), not to an effect. |
| The MCP server's tools are changed after install | Run `velaris mcp-verify` against the signed manifest of the release you installed, after every install or upgrade and in the pipeline that builds the client's environment. |
| Nobody reads the invocation log | Send it to a file (`--log-file`) that something keeps and watches; `outcome` values `unauthorized`, `ceiling` and `refused` are the ones that mean someone tried more than they were given. |
| The model wrote something other than Velaris | Check the file extension and run `velaris check` first; refuse to run anything the checker refuses. |
| A compiler defect | Pin a version, verify the signature of what you install, run the suites (`python run_tests.py`, `check_sandbox.py`, `check_library.py`, `check_refusals.py`, `check_fallible.py`, `check_termination.py`, `check_pool.py`, `check_ratchet.py`, `check_money.py`, `check_secret.py`, `check_platform.py`, `check_deps.py`, `check_adversarial.py`, `check_prover_lies.py`, `check_metamorphic.py`, `check_eject.py`, `check_policies.py`, `fuzz_native.py`) and `velaris conformance` on the machine that will run untrusted code, and report anything that lies through the private channel in SECURITY.md. |
| A single maintainer | Real, and stated in [SUPPORT.md](SUPPORT.md). Fixes to soundness and sandbox reports are promised within a week; nothing else is promised. |

## What "not a security boundary" means here

The README says the effect budget is not a security boundary, and this
document is the long form of that sentence. The budget is enforced by
an interpreter written in Python, in a process that also holds the
compiler, on a host that trusts that process. It is a strong guard
against a program that does what it was not asked to - the situation
you are in when a model hands you a script - and it is tested as such
on every push. It is not a substitute for an OS-level sandbox, a
network policy or a separate user account, and it should sit inside
one of those when the stakes warrant it.
