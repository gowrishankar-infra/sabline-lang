# Velaris from inside your program

Velaris is a library as well as a command. An agent framework, an MCP
server, a CI dashboard or an internal tool can check, audit and run
Velaris without shelling out - and the effect budget is enforced the
same way it is on the command line, whatever a program's source claims
about itself.

```
pip install velaris-lang
```

## Three calls

```python
import velaris

source = open("agent_output.vel").read()

result = velaris.check(source)
if not result.ok:
    for p in result.problems:
        print(p.code, p.line, p.message, p.fixes)

report = velaris.audit(source)
print(report.effects)        # ['fs', 'net'] - what it can touch
print(report.proven_share)   # 66.7 - how much is proven, not just checked
print(report.warnings)       # ffi cannot be contained by a budget

run = velaris.run(source, allow={"io"})
print(run.ok, run.output, run.refused_effect)
```

`velaris.card()` returns the language in about 3,700 words - paste it
into a model before asking for Velaris.

## Limits: time and memory

```python
run = velaris.run(source, allow={"io"}, timeout=30, max_memory_mb=512)
run.timed_out        # True if it ran past the limit and was stopped
run.out_of_memory    # True if it grew past the cap and was stopped
```

The effect budget bounds what a program may *touch*. These bound the
other two things a program can do to the machine running it: spin
forever, or eat memory. With either set, the program runs in a
separate process that is killed on breach, and the result says which
limit it hit (E610 for time, E611 for memory). The budget still holds
inside that process.

Memory caps use whatever the operating system has:

| Platform | Mechanism | Enforced? |
|---|---|---|
| Linux | `RLIMIT_AS`, set by the child on itself | yes |
| Windows | a job object with `JOB_OBJECT_LIMIT_PROCESS_MEMORY`; the child is created suspended, put in the job, and only then resumed | yes, since 3.1 |
| macOS | `RLIMIT_AS` | best-effort - the limit is set and not reliably honoured, and the timeout is what stops a runaway |

If the Windows job object cannot be made, the cap is recorded and not
enforced rather than the run failing - the behaviour before 3.1.
`velaris.memory_cap_is_enforced()` answers for the machine you are on,
so a suite can assert the cap where the mechanism holds and skip it
where it does not. The timeout is enforced on every platform.

An agent framework calling `run` in a loop should set both. On the MCP
server and the HTTP door the operator sets both, as ceilings a caller
may lower and cannot raise: 30 seconds and 512 MB unless the operator
names others (4.0). Before 4.0 those were only the values used when a
caller sent none, and a caller who sent more got more.

## Many runs: a pool

Every bounded run starts a Python interpreter - about a tenth of a
second before a line of Velaris is read. Calling `run` thousands of
times an hour pays that every time. A pool keeps workers alive:

```python
pool = velaris.Pool(size=4, allow={"io"}, timeout=30, max_memory_mb=512)
result = pool.run(source)        # the same RunResult run() returns
pool.close()                     # also a context manager
```

`pool.run` also takes `stdin=`, `args=` and `path=`. On one machine,
200 sequential bounded runs of a small program took 46.6 s one process
at a time and 0.5 s on a pool.

**The isolation rules matter more than the speed, and
`check_pool.py` asserts every one of them.**

* **The budget is the pool's, not the program's.** It is parsed once,
  when the pool is made, and installed by each worker at startup.
  `pool.run` takes no `allow` argument - there is nowhere for a caller
  or a program to ask for more. If you need a different budget, make a
  different pool. The budget is re-asserted from the pool before every
  program, so a `@N` count is spent per program rather than shared
  across a worker's whole life, and a program that reaches into the
  compiler through a granted `ffi` module and widens its own budget
  cannot leave it widened for the next program.

* **A worker is used once unless the run was clean.** Anything other
  than `ok` - a refused effect, a failure that escaped, a program that
  did not compile, the timeout, the memory cap - kills the worker and
  starts a fresh one. Only a run that finished cleanly hands its worker
  back. That costs a restart on every rejected program; it is the rule
  that makes the rest checkable.

* **A reused worker starts empty.** Before every program the child puts
  back every piece of module-level mutable state it has: the arguments
  `args()` answers, Python handles from `py_new` whether the program
  closed them or not, the native compiler's engines and the text arena
  they own, the tracer, the budget and its operation counts - and the
  working directory, the environment and the recursion limit, which a
  program granted `ffi` can change.

* **The parent owns the deadline.** A worker that has not answered
  within `timeout` is killed by the parent process, not asked to stop.
  The call returns E610 and a replacement worker is started.

* **A program cannot reach the pipe.** The worker keeps private copies
  of its own standard input and output for the protocol and points the
  program's at the null device, so a program writing straight at file
  descriptor 1 - which a granted `ffi` module can do - cannot corrupt
  the answer the parent is parsing.

* **Closing kills every worker**, including one still running a
  program. A pool collected without `close()` is closed by its
  finalizer, one that outlives the interpreter is closed at exit, and a
  worker whose pipe closes ends by itself - so a parent that dies
  without doing either still leaves nothing behind.

A pool changes none of the guarantees in
[THREAT_MODEL.md](THREAT_MODEL.md). A granted `ffi` module can still do
whatever that module can do, inside a worker as anywhere else; what a
pool promises is that it cannot do it to the *next* program.

`velaris.PoolRegistry()` keeps one pool per distinct budget and makes
each one the first time that budget is asked for - what a server needs,
since it learns the budget from the request. The MCP server and the
HTTP door each keep one. The CrewAI and LangChain tools stay on plain
`run`: a crew's tool is not called often enough to need a pool, and one
process per call is easier to reason about.

## A platform whose customers write Velaris

[`examples/platform/`](examples/platform/) puts `audit` and `Pool`
together in the shape a SaaS team would copy - a FastAPI service in one
file, under 200 lines:

```
POST /scripts           audit the source, store it with its capability
                        surface, answer with what it declares. No run.
GET  /scripts/{id}      that declaration, as a customer is shown it
POST /scripts/{id}/run  on a pool whose budget is the platform's
```

Two guards, and they are not the same guard. The audit is a read of the
text, and submission is refused when what a script declares is wider
than the platform permits - `Budget.covers` names the first thing that
does not fit, and the response lists the grants an operator would have
to add. The pool is the enforcement, and does not depend on the gate
having been right: `check_platform.py` puts a script straight into the
store, past the gate entirely, and asserts the run is still refused.

Submitting [`examples/discount.vel`](examples/discount.vel) answers with
`"proven_share": 100.0` and `"status": "proven"` on each of its
promises. That is what the pattern is for: a platform can tell a
customer, before enabling a rule it did not write, that the rule can
never return a negative total. fastapi is a dependency of the example,
never of Velaris.

## What `run` guarantees

`allow={"io"}` means the program cannot read a file, reach the
network, read the environment, call Python, ask the clock or use
randomness. Not "should not" - the runtime refuses, and a refusal
**cannot be caught** by the program, so it cannot swallow the refusal
and carry on.

**`allow=None` is the same `io`, from 5.0.** It used to be all seven
effects, so a caller who forgot the argument got the widest budget
there is; now forgetting it gets the narrowest useful one. The ways to
ask for everything, both of which say so where you can see them:

```python
velaris.run(source, allow="all")                  # one line to stderr
velaris.run(source, allow=set(velaris.ALL_EFFECTS))
```

`velaris.Pool(...)` and `velaris.run(..., timeout=...)` take the same
default, and so does `velaris <file>` on the command line: one answer
in every place a budget comes from.

A grant can be narrower than an effect, in the same grammar the
command line takes (SPEC.md 7.1):

```python
velaris.run(source, allow={"io", "env",
                           "fs:read:./data", "fs:write:./out@50",
                           "net:api.example.com:443@100",
                           "ffi:math,json"})
```

`fs:read:./data` permits reads under that directory only, resolved
with realpath so `..` and symlinks cannot leave it; `net:host:port`
permits that host and port, `net:*.example.com` one label under the
domain; `@N` caps the operations of that effect for the whole run. A
path, host or count outside the grants is refused (E313, E314, E315)
and cannot be caught; the one catchable case is a redirect to a host
outside the grants, which fails the request naming the target.
`refused_effect` reports `fs:<path>`, `net:<host>` or `fs@count` /
`net@count` for those.

It is not a security boundary. `allow={"ffi"}` and `allow="all"` grant
everything Python can do, and nothing here limits memory, time, or what
a program prints. It is a real guard against accident and casual misbehaviour -
the situation you are in when a model hands you a script.

`run` captures stdout as `output` and stderr as `logs`, accepts
`stdin=` and `args=`, and restores the previous budget afterwards, so
several audits and runs can share a process.

## The audit format

`audit().as_dict()` is a stable, versioned shape. Tools can depend on
it; the `schema` field names the version.

```json
{
  "schema": "velaris.audit/1",
  "velaris_version": "2.52.0",
  "ok": true,
  "problems": [],
  "effects": ["fs", "io"],
  "functions": [
    {"name": "parse_row", "effects": [], "can_fail": true,
     "requires": [], "ensures": ["length(result) >= 1"],
     "status": "proven"}
  ],
  "proven_share": 66.7,
  "safe_command": "velaris <file> --allow fs,io",
  "warnings": []
}
```

Field meanings, all stable within `velaris.audit/1`:

| Field | Meaning |
|---|---|
| `schema` | the format's name and version |
| `velaris_version` | the compiler that produced this |
| `ok` | did it compile |
| `problems` | code, message, line, file, fixes |
| `effects` | everything the program may perform, transitively |
| `functions` | per function: effects, can_fail, contracts, and whether each contract is `proven` before running or `checked at runtime` |
| `proven_share` | percent of promise-carrying functions proven, or null when there are no promises |
| `safe_command` | the narrowest budget the audit can write: `fs:read:<path>` and `net:<host>` for the literals it read, the bare direction or effect where a value was built at runtime |
| `warnings` | human-readable cautions, including which modules to grant |
| `ffi_modules` | top-level Python packages named in py* calls, for `ffi:` grants (added in 2.60 within schema 1) |
| `loops_unshown` | loops the termination rule cannot show to end (added in 2.62) |
| `contract_coverage` | functions that take or return data and promise nothing (added in 2.62) |
| `fs_paths` | `{"read": [...], "write": [...], "read_any": bool, "write_any": bool}` - the path literals a program reads and writes; a flag says a path was built at runtime (added in 3.0) |
| `net_hosts` | `{"hosts": [...], "any": bool}` - the hosts (with ports when given) named in URL literals (added in 3.0) |
| `ffi_any` | true when a py* call names its module with a value built while running, which `ffi_modules` cannot list (added in 4.0) |
| `counts` | `{"fs": n, "net": n}`: the most file and network operations one call to any of the file's functions can perform, by velaris-spec 9.4's fixed rules - `0` for an effect none of them declares, `null` where the text fixes no bound; the whole field `null` when the file does not compile (added in 4.2) |
| `prover` | true when a prover checked the promises; false without one, when no status is `proven` and a `proven_share` of 0 says nothing about what could be proven - and false when the file does not compile (added in 4.2) |
| `secrets` | `{"sources": [...], "declassifies": bool, "declassifications": [{"reason", "function", "line"}]}` - which builtins handed the program a `Secret` (`env`, `read_file_secret`), whether it ever declassifies one, and with what reason. `declassifies: false` with `ok: true` is the answer to "does this program ever let a secret out"; `null` when the file could not be loaded, and not null merely because `ok` is false (added in 6.0) |

A new field may be added within version 1; a field will not change
meaning or disappear without the schema name changing. `effects` and
each function's `effects` hold only real effect names - the seven, and
`declassify` from 6.0 - even in the audit of a program that does not
compile because it names another in a `uses` clause (from 4.1; until
then that name was listed, and made `safe_command` a budget that does
not parse).

## Setting it up in your assistant

**One command, every client on the machine:**

```
velaris mcp-install          # adds it wherever it finds a client
velaris mcp-install --list   # show what it found, change nothing
velaris mcp-install --remove # take it back out
```

It knows where Claude Code, Cline, Cursor, Windsurf, Continue and Zed
keep their configuration, adds a `velaris` server without disturbing
anything else already there, and backs up each file first. Restart the
assistant afterwards - closing the window is usually not enough.

**Claude Desktop:** newer builds only accept remote connectors in the
Add-connector dialog, so use the bundle instead. Download
`velaris.mcpb` from any release and open it, or drag it into
Settings -> Extensions. The compiler travels inside the bundle, so
nothing needs installing first. (The prover does not travel with it -
without `pip install z3-solver` promises are checked while running
rather than proven, and the tools say so rather than hiding it.)

## As an MCP server

`velaris_mcp.py` speaks the Model Context Protocol over stdin/stdout,
so an assistant can write Velaris, check it, audit it and run it in a
box without leaving the conversation.

```json
{"mcpServers": {"velaris": {"command": "python",
                            "args": ["-m", "velaris_mcp"]}}}
```

Three spellings start the same server, and it is the same process
whichever you use: `python -m velaris_mcp`, `velaris mcp` through the
console script, and `npx velaris-lang mcp` through the npm wrapper -
which calls the Python package, so it still needs
`pip install velaris-lang`. Every flag below is the server's own and is
taken by all three.

Four tools: `velaris_card`, `velaris_check`, `velaris_audit` and
`velaris_run` (which takes `allow`, defaulting to `["io"]`).

**The server has a ceiling, and it is `io` unless you raise it.**
`allow` is what the caller asks for; `--max-allow` is the most the
server will grant, in the same grammar the HTTP door and the command
line take - effects, `fs:read:`/`fs:write:` paths, `net:` hosts and
ports, `ffi:` modules, `@N` counts:

```json
{"mcpServers": {"velaris": {"command": "python",
  "args": ["-m", "velaris_mcp", "--max-allow", "io,fs:read:./data"]}}}
```

A `velaris_run` that asks for more than the ceiling at any level - an
effect, a module, a wider path, another host, a larger count, or plain
`fs` against a scoped ceiling - does not run. The result is marked
`isError` and holds the same body the HTTP door sends with its 403:

```json
{"error": "this server does not grant ffi", "max_allow": ["io"],
 "max_timeout": 30, "max_memory_mb": 512}
```

**The operator also sets the time and memory (4.0).** `--max-timeout`
and `--max-memory-mb` are the most one run may have, 30 seconds and
512 MB when the flags are absent. A `velaris_run` that names no
`timeout` or `max_memory_mb` gets the ceiling; one that asks for less
gets less; one that asks for more is refused the same way, naming the
ceiling (`"this server allows at most 30 second(s) per run; the request
asked for 60"`). A value that is not a number above zero is refused as
a bad request. Before 4.0 a caller could ask for any timeout and any
memory cap and have it.

```json
{"mcpServers": {"velaris": {"command": "python",
  "args": ["-m", "velaris_mcp", "--max-timeout", "10",
           "--max-memory-mb", "256"]}}}
```

Without the flag the server grants `io` alone: a program can print,
read its arguments and its stdin, and nothing else. The `.mcpb` bundle
and `velaris mcp-install` start the server without the flag; add it to
the `args` above to widen it. A `--max-allow` that does not parse
stops the server before it answers anything.

### Checking the tools against the signed manifest

An MCP client shows the model each tool's description, and a model
follows what a description says - which is why a changed description is
an attack (tool poisoning, OWASP MCP Top 10 MCP03). Every release from
3.4 carries `velaris-mcp-tools-X.Y.Z.json`: the name of every tool the
server offers, the sha256 of its description and the sha256 of its
input schema, generated by the release workflow from the server inside
the wheel it publishes and signed with sigstore
(`velaris-mcp-tools-X.Y.Z.json.sigstore.json`), like the wheel.

To check the server you run against it:

```
gh release download v4.0.0 --repo gowrishankar-infra/velaris-lang \
  --pattern 'velaris-mcp-tools-4.0.0.json*'
pip install sigstore
velaris mcp-verify velaris-mcp-tools-4.0.0.json \
  -- python -m velaris_mcp --max-allow io
```

Everything after `--` is the command your client's configuration runs;
`mcp-verify` starts it the way the client does, asks it for its tools,
and compares:

```
manifest:  velaris-mcp-tools-4.0.0.json (4 tool(s), velaris 4.0.0)
signature: verified, signed by https://github.com/gowrishankar-infra/velaris-lang/.github/workflows/release.yml@refs/tags/v4.0.0
server:    python -m velaris_mcp --max-allow io (velaris 4.0.0)
  ok       velaris_audit
  ok       velaris_card
  CHANGED  velaris_check: input schema
  CHANGED  velaris_run: description
  NEW      velaris_shell: offered by the server, not in the manifest
2 of 5 tool(s) match the manifest; 3 differ
```

It exits 0 when every tool matches, 1 when any description or schema
differs or a tool was added or removed, and 2 when it could not check:
no signature bundle beside the manifest, a signature that does not
verify, `sigstore` not installed, or a server that did not answer. The
signature must come from this repository's release workflow: at the tag
the manifest names, for 7.1.2 and earlier, and on main from 7.2.0, when
releases stopped being started by tags (RELEASING.md). The main identity
names no version, so the version is the one inside the signed manifest,
which `mcp-verify` prints on its first line beside what the server
reports. `--identity` changes the identity for a fork, or for checking a
7.2.0 or later manifest with a Velaris older than 7.2.0; `--bundle`
names the bundle, and `--skip-signature` compares against a manifest
you have verified some other way.

Run it after installing or upgrading, and in the CI that builds the
environment your client runs in. What it does and does not tell you:

* A description or schema that differs from what the release workflow
  built is reported, whichever way it got there - an edited
  `velaris_mcp.py`, a different package answering to the same name, a
  local patch.
* The description hash is of the exact text the server sends; the
  schema hash is of the schema with its keys sorted and no whitespace
  (RFC 8785's form for the objects, arrays, strings and integers a
  schema holds), so a reformatted but equal schema matches.
* It checks what the server says, not what it does. A server that
  presents the signed descriptions and behaves differently is not
  caught here; the wheel's own signature (SECURITY.md) is what covers
  the code.
* It checks one moment. A server that changes its tools after you ran
  it is caught the next time you run it, not before.
* The checker is in `velaris.py`, not in `velaris_mcp.py`, so a changed
  server file does not change the code that checks it. An installation
  in which both were changed is caught by verifying the wheel, or by
  running `mcp-verify` from a separately verified Velaris (a signed
  standalone executable, say) with the server command after `--`.

`velaris mcp-manifest -o tools.json -- <server command>` writes the same
manifest for any server, which is how the release workflow makes it.

## Vendored libraries, and velaris.lock

```
velaris add https://example.com/geo.vel as geo   # vendored into lib/
velaris add https://example.com/geo.vel --force  # replace different bytes
velaris deps                                     # what you depend on
velaris deps --verify                            # do they match the lock?
```

`velaris add` writes two files. `velaris.toml` says what the project
depends on. **`velaris.lock`** says exactly which bytes were vendored:
every library with its source, its sha256 and the version of Velaris
that added it. The digest is of the fetched bytes exactly as they
arrived, so it is the digest the source published and the same on every
platform.

`velaris deps --verify` (`velaris verify` is the older spelling of the
same check) fails if a vendored file's hash differs from the lock, or
if a lock entry has no file on disk. Run it in CI: a library that
changed under you is worth looking at before trusting it.

`velaris add` refuses to overwrite a library that is already vendored
when the incoming bytes are different, and prints both digests;
`--force` replaces it. A project made before 3.1 has no lock, and
`deps --verify` says so and falls back to checking `velaris.toml`.

## From a language that is not Python

`velaris serve` opens a local HTTP door, so a Node service, a Go tool,
a Rust agent or a shell script can use the same three calls.

```
velaris serve --token-file ~/.velaris-token \
              --max-allow io,fs:read:./data,net:api.example.com@100 \
              --max-timeout 10 --max-memory-mb 256
                                       # localhost:8787, grants at most this
```

```
GET  /health         version, whether the prover is installed; with the
                     token, the ceilings too. The one endpoint without a token.
GET  /card           the language, for pasting into a model
POST /check          {"source": "..."}                  -> problems, proven
POST /audit          {"source": "..."}                  -> velaris.audit/1
POST /run            {"source": "...", "allow": ["io"], "stdin": "", "args": [],
                      "timeout": 10, "max_memory_mb": 256}
```

**Every endpoint but `GET /health` needs the token**, as
`Authorization: Bearer <token>`:

```javascript
const answer = await fetch("http://127.0.0.1:8787/run", {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${process.env.VELARIS_TOKEN}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({ source, allow: ["io"] }),
}).then(r => r.json());

console.log(answer.ok, answer.output, answer.refused_effect,
            answer.effects_used);
```

The token comes from one of three places, in this order:

1. `--token-file <path>` - a file holding the token and nothing else
   (surrounding whitespace is ignored). On Linux and macOS the door
   warns if other users can read it.
2. `VELARIS_TOKEN` in the door's environment. The door removes it from
   its environment as it starts, so the worker processes that run
   programs do not inherit it and a program granted `env` cannot read
   it.
3. Neither: the door makes one with `secrets.token_urlsafe(32)` and
   prints it once, on stdout, when it starts. It is not shown again.
   If something captures the door's stdout into a file, use one of the
   other two.

A token must be at least 16 printable ASCII characters. The door
refuses to start with `--token` on its command line, in either spelling,
because every process on the machine can read another's arguments; the
refusal does not repeat what was typed. The token is compared in
constant time (`secrets.compare_digest`, over sha256 digests so its
length does not show either). A request with no token, a wrong one,
another scheme, or the token anywhere but the header gets the same
answer, to any path, `/card` and unknown paths included:

```
401   WWW-Authenticate: Bearer realm="velaris"
      {"error": "unauthorized"}
```

It does not say which was wrong, or whether the path exists. The door
never writes the token to its log, to an error message or to a process
argument.

**`--no-auth`** turns the token off, for local development. It is
refused unless `--host` is `127.0.0.1` or `localhost`, and prints a
warning on every start. Without a token, what stands in for one is
narrow: a request must be addressed to `127.0.0.1` or `localhost`
(the `Host` header), carry no other `Origin`, and send a `POST` as
`Content-Type: application/json` - which keeps a web page in a browser
on the same machine from using the door (a cross-site `fetch` of JSON
needs a preflight, which the door never approves, and a DNS-rebinding
page arrives under its own host name). Nothing stops another program on the
machine, run by any user.

The door speaks plain HTTP. On `127.0.0.1` the token never leaves the
machine; on any other address it crosses the network readable by
anyone on the path, so put a TLS-terminating proxy in front, and the
door says so when it starts.

**The operator sets the limits, not the caller (4.0).** A request's
`allow`, `timeout` and `max_memory_mb` are what the caller asks for;
the door grants them only up to its ceilings, and a caller asking for
more at any of the three gets 403 with the ceilings named:

```
403   {"error": "this server allows at most 30 second(s) per run; the
       request asked for 60", "max_allow": ["io"], "max_timeout": 30,
       "max_memory_mb": 512}
```

| Ceiling | Flag | When the flag is absent |
|---|---|---|
| the budget | `--max-allow` | `io` |
| seconds per run | `--max-timeout` | 30 |
| MB per run | `--max-memory-mb` | 512 |

`--max-allow` takes the full grammar: a caller asking for more at any
level - an effect, a module, a wider path prefix, a host the server
does not name, a port, a larger count, or an unscoped `fs`/`net`
against a scoped ceiling - is refused. A request that names no
`timeout` or `max_memory_mb` gets the ceiling; one that names less gets
less; a value that is not a number above zero is a 400. **Before 4.0
none of this held**: a door started without `--max-allow` granted every
effect, `ffi` included, to anyone holding the token, and a caller could
send any timeout and any memory cap and have it. Starting a door with a
wider ceiling now takes naming it: `--max-allow
io,env,fs,net,clock,rand,ffi` is what 3.4 granted by default, and from
5.0 `--max-allow all` is the same thing written shorter - the door
writes one line to stderr when it is started that way.
`--max-memory-mb` on `velaris serve` used to set a cap on the door's
own process (on Linux and macOS); it is now the most each run may have,
and the door's process is not capped.

It binds to `127.0.0.1` unless told otherwise, because **this endpoint
runs programs**. Do not expose it to a network you do not control, and
prefer `--max-allow io,fs` over granting `ffi` on a shared machine -
the server warns about both. Keep the token file outside every path the
ceiling grants: a program allowed to read it can send it somewhere.

The door refuses an argument it does not know rather than ignoring
it, so a mistyped `--max-alow io` stops it instead of leaving the
ceiling at everything.

## The invocation log

The HTTP door and the MCP server each write **one JSON line per call** -
every request the door answers, and every `tools/call` the server gets
(not the protocol's own `initialize` and `tools/list`) - to stderr, or
appended to a file with `--log-file <path>`. There is no way to turn it
off; `--log minimal` writes fewer fields. A full line from the door:

```json
{"schema": "velaris.invocation/1", "ts": "2026-09-11T05:50:30.776Z",
 "door": "http", "endpoint": "POST /run", "outcome": "ok",
 "duration_ms": 284.7, "client": "127.0.0.1", "budget": "env,io",
 "effects": {"env": 1, "io": 1}, "refusals": [],
 "source_sha256": "768e84b1..."}
```

and from the MCP server, a call the ceiling refused:

```json
{"schema": "velaris.invocation/1", "ts": "2026-09-11T05:51:02.114Z",
 "door": "mcp", "tool": "velaris_run", "outcome": "ceiling",
 "duration_ms": 0.3, "budget": null, "effects": null,
 "refusals": [{"by": "ceiling", "what": "this server does not grant ffi"}],
 "source_sha256": "9809d3a9..."}
```

| Field | What it holds |
|---|---|
| `schema` | `velaris.invocation/1` |
| `ts` | when the call arrived, UTC, to the millisecond |
| `door` | `http` or `mcp` |
| `endpoint` / `tool` | `POST /run`, `GET /card`...; an unknown path is written `POST (no such endpoint)`, never as sent. The MCP tool's name, or `(no such tool)` |
| `outcome` | `ok`; `problems` (check or audit found some); `failed`, `refused` (the budget stopped the program), `timeout`, `out_of_memory` for a run; `ceiling` (the door's `--max-allow`, `--max-timeout` or `--max-memory-mb` refused the request); `unauthorized`; `not_local` (`--no-auth` refused a request a browser page could have sent); `bad_request`, `too_large`, `not_found`, `unknown_tool`, `caller_gone`, `error` |
| `duration_ms` | from arrival to the answer |
| `client` | the caller's IP address (HTTP only) |
| `budget` | the budget the program ran under, as the budget grammar writes it (paths absolute); `null` when nothing ran |
| `effects` | `RunResult.effects_used`: each effect and how many builtin calls the budget let through; `null` when nothing ran, or when the worker was killed before it could say |
| `refusals` | `{"by": "ceiling", "what": ...}` for the door's refusal; `{"by": "budget", "code": "E313", "what": "fs:/etc/passwd"}` when the budget stopped the program |
| `source_sha256` | the sha256 of the program's source text (UTF-8); `null` when there was none |

`--log minimal` keeps `schema`, `ts`, `door`, `endpoint`/`tool`,
`outcome` and `duration_ms`.

**Never recorded:** the source itself, the program's output, its stdin
and arguments, request headers, the request path as sent (a query
string included), and the door's token. The token is also struck out
of any line it could appear in, as `[redacted]`. **Recorded that may
matter to you:** a refusal names the path or host refused, which comes
from what the program tried to do, and `budget` names the paths and
hosts granted. **Not seen:** what a granted `ffi` module does inside
Python - it shows as `ffi` calls, nothing more.

If the log file cannot be opened the door and the server do not start;
if a write to it fails later, the line goes to stderr instead.

## From JavaScript

```
npm install velaris-lang        # or: npx velaris-lang script.vel --allow io
```

```javascript
import { audit, run } from "velaris-lang";

const report = await audit(source);
const result = await run(source, { allow: ["io"] });
console.log(result.ok, result.output, result.refusedEffect);
```

Leaving `allow` out is `io`, the same default the command line and the
Python library have from 5.0.

The compiler is a Python package, so `pip install velaris-lang` once;
the npm package says so plainly if it is missing. Types ship with it.

## In a notebook

```
%pip install velaris-lang
%load_ext velaris_magic
```

```
%%velaris --audit --allow io
fn main() uses io {
    print("proven before it ran")
}
```

`--audit` prints what the cell can touch and how much of its promises
are proven before running - useful when the code in the cell came from
a model. Effects outside `--allow` are refused, and the cell says which
flag would permit them. A cell with no `--allow` gets `io`, which the
magic has always done and which 5.0 made true everywhere else too.

## As a GitHub Action

```yaml
permissions:
  contents: read
  security-events: write        # for sarif, on by default
  pull-requests: write          # only for pr-comment

steps:
  - uses: actions/checkout@v5
  - uses: gowrishankar-infra/velaris-lang@v7.2.0
    with:
      min-proven: "80"
      pr-comment: "true"
      capabilities: "check"   # the default when velaris.capabilities exists
      deps-diff: "true"       # off by default
```

The action installs Velaris with the prover, checks every `.vel` file
(or the `files` glob), and fails the job if anything does not compile
or a promise cannot be kept. With `sarif` on (the default), the check's
findings are also written as SARIF 2.1.0 and uploaded to code scanning
by `github/codeql-action/upload-sarif`, pinned to a commit; the README's
CI section says what each result holds and at what level. With `pr-comment: "true"`, on a
`pull_request` event it also posts one comment holding the audit of
each changed `.vel` file - the same `velaris.audit()` this document
describes: effects, Python modules named, proven share, the safe
command, and the warnings (`loops_unshown`, `contract_coverage`) - and
on later runs edits its own comment, found by a hidden HTML marker,
rather than adding another. It talks to the REST API with the job's
`GITHUB_TOKEN` through `curl`; no third-party action is involved.

From 4.0 the comment also holds the capability ratchet's result, with
each widening, where it came from and the edit to
`velaris.capabilities` that would accept it; and a review of the pull
request against its base (`velaris review`, below): whether the
capability surface changed, the proven share before and after, new
fallible functions, new hosts, paths and modules, whether
`velaris.capabilities` itself changed, and a risk word.

With `capabilities` left at its default the action runs the ratchet
whenever `velaris.capabilities` exists at the repository root, and
fails the job if the code needs more than it declares. A pull request
that deletes the file fails too, since that would turn the ratchet off;
`capabilities: "off"` in the workflow is the way to turn it off, where
the change is visible. The ratchet's findings go to code scanning
beside the check's when `sarif` is on.

With `deps-diff: "true"` (7.1), on a pull request the action runs
`velaris deps-diff --against` the base branch's commit: every dependency
the pull request upgrades in a lockfile it reads is compared version
against version, and one comment - its own marker, edited in place like
the audit's - says what each gained. For a Velaris library that is its
declared capability surface; for any other package it is the
install-time scripts and declared dependencies, with the surface said
to be unknown. The step informs and never fails the job. The README's
CI section lists the lockfiles it reads and what it cannot see.

## Holding a repository to its capability surface

```
velaris capabilities init              # record the surface in velaris.capabilities
velaris capabilities check             # exit 1 if the code needs more than that
velaris capabilities check --json      # the same, for tools
velaris capabilities check --sarif     # the same, for code scanning
velaris review --against origin/main   # what a branch changed, as facts
```

A model, a contributor or a dependency update can add capability to a
repository one small commit at a time: a helper that builds a URL, then
a function that reads a file, then a call three levels down that sends
it somewhere. A reviewer who reads each diff sees nothing alarming in
any of them. Capability does not work that way - it is binary and
cumulative, and forty small steps reach exactly as far as one large
one - but only a comparison with a declared baseline sees that. A
comparison with the previous commit sees forty small steps.

`velaris capabilities init` reads every `.vel` file under the path
(not `.git`, and not what git ignores) and writes `velaris.capabilities`
(`velaris.capabilities/1`, specified in velaris-spec section 9):

- the **surface**: every grant the repository's programs need, in the
  budget grammar - effects, `fs:read:`/`fs:write:` paths, `net:` hosts,
  `ffi:` modules - and for `fs` and `net` the most operations one run
  can perform, or `null` where the text sets no bound;
- for each **program**, its own grants and counts, and the effects each
  of its functions declares - or `"compiles": false`;
- the Velaris version that wrote it, and the date.

It refuses to replace an existing file without `--force`: the file is
what the repository declared, and replacing it is a decision.

`velaris capabilities check` derives the same from the working tree and
compares it with the file - never with a previous commit. It fails
(exit 1) when:

1. the code needs a grant the surface does not cover - a new effect, a
   module, a path outside every recorded one (so `./data` widened to
   `./` fails), a host (so `api.example.com` made `*.example.com`
   fails), a scoped grant made unscoped - or more `fs` or `net`
   operations in a run than the surface's count;
2. a program the file records needs something its own entry does not
   give, even if another program already had it; or
3. a function the file records declares an effect it did not declare
   there, even when the program's grants stay the same.

A program or function the file does not record is held to rule 1
alone: a new program that stays inside the surface is not a widening.
Narrowing never fails; it is reported, so the file can be tightened. A
file that does not compile cannot run, so it adds nothing, and it is
reported rather than compared. A file written by another Velaris
version is compared with a warning, never a failure on that account.
Exit 2 means the check could not be made: no file, a file that is not
`velaris.capabilities/1`, or one that does not read.

Each widening names what widened, the file and function that introduced
it - the call, its line, and the chain of calls from `main` that reaches
it - and the edit to `velaris.capabilities` that would accept it:

```
WIDENED  net:collector.example.net - a new effect, net
    needed by app.vel (its entry does not grant it)
      lib/deliver.vel:2  send calls post("https://collector.example.net/v1")
      reached from main -> summary -> deliver -> send
    if intended: add "net:collector.example.net" to surface.grants; add
    "net:collector.example.net" to the grants of app.vel
```

Accepting a widening is an edit to `velaris.capabilities`, or `velaris
capabilities init --force` and a commit, so the change is in the diff
a reviewer reads. `--json` is `velaris.capabilities-check/1`; `--sarif`
reports each widening as an error at the line that introduced it
(`capability-widened`, `capability-effect-gained`) and each narrowing
as a note.

**How the counts are found.** One run's operations are bounded from the
text: a loop counts when a counter moves one step toward a limit on
every turn (SPEC.md 9.5) and both its start and the limit are numbers
the text fixes - `for i in 0 to 10`, a counter started by `let`, a
loop over a list literal or a variable holding one; nested loops
multiply; a branch counts its larger arm; a function counts its bound
at every call; recursion, and a loop whose turns the text does not fix,
have no bound. A path, URL or module is fixed when it is a literal or
a variable bound once to one; one built while running is recorded as
the unscoped grant (`fs:read`, `net`, `ffi`), which a scoped surface
does not cover.

**`velaris review --against REF`** runs the same derivation, and the
audit, on the files at a git ref - read with `git show REF:PATH`, with
nothing checked out - and on the working tree, and reports the delta:
whether the capability surface widened, narrowed or is unchanged, the
proven share before and after, functions that became fallible, hosts,
paths and modules newly named, whether `velaris.capabilities` itself
changed, and one word of risk computed from those facts alone -
`high` when the surface widened, or the declared surface widened or was
removed; `medium` when it did not, but a program or function the ref
had came to need more, or the proven share fell; `low` otherwise. No
count of changed lines enters it. It is a report for a reviewer; the
gate is `capabilities check`, because a review against the previous
commit cannot see a widening that was merged a commit ago.

What the ratchet does not see is in [THREAT_MODEL.md](THREAT_MODEL.md):
it reads text, so what a granted `ffi` module does is beyond it, paths
are compared as written, and a function renamed as it gains an effect
is a new function.

## Moving a 4.x project to 5.0

```
velaris migrate --to 5.0                # every program under .
velaris migrate --to 5.0 src/report.vel # one of them
velaris migrate --to 5.0 --json         # velaris.migrate/1
velaris migrate --to 5.0 --write        # and change what it can parse
```

In 5.0 a run given no budget gets `io` rather than all seven effects,
so a command, script or CI step that runs a program needing more has
to say what it needs. `migrate` works that out: for each program it
reads, it derives the narrowest budget the program's own audit can
write - the grants `safe_command` carries - and prints the command to
run it under 5.0.

```
examples/wordcount.vel
    uses:  fs, io
    run:   velaris examples/wordcount.vel --allow fs:read,io
```

A program that uses `io` or no effect at all is counted and not
listed: 5.0 grants it already. A file that does not compile is named
with the problem, never guessed at.

It changes nothing without `--write`, and with it changes only lines
it can parse with no guessing: one command on the line, a `.vel` path
that resolves to a program it audited, no `--allow` or `--deny`
already there, and no pipe, chain, substitution or redirection that
would make the end of the command the wrong place for a flag. It
writes `.sh`, `.bash`, `.yml` and `.yaml` files, puts the flag after
the file name and before the program's own arguments, and lists every
line it left alone with the budget to add by hand.

## Running velaris-spec's conformance corpus

```
velaris conformance                    # L1, L2 and L3; exit 1 if any case fails
velaris conformance --level 3          # the cases a claim at L3 needs: L1 and L3
velaris conformance --json             # velaris.conformance/1, one result per case
velaris conformance --corpus DIR       # DIR is velaris-spec's tests/
```

[velaris-spec](https://github.com/gowrishankar-infra/velaris-spec)'s
`tests/` is a conformance corpus for the capability format: JSON cases
an implementation in any language runs its own way, at the three levels
of its CONFORMANCE.md - L1 Declaration (the budget grammar, the effect
surface, `velaris.audit/1`), L2 Enforcement (refusals at run time) and
L3 Ratchet (`velaris.capabilities/1`). `velaris conformance` finds it
beside the working directory or this installation (`velaris-spec/tests`
or `../velaris-spec/tests`), or where `--corpus` or
`VELARIS_CONFORMANCE_CORPUS` says, and runs every case through the
budget parser, the audit, the command line under a budget, and the
baseline writer and check. It prints one line per level and a verdict;
a failure names the case and what differed. Validating documents
against velaris-spec's schemas needs `jsonschema`; without it those
cases are skipped and the level is reported as not shown. A case that
needs a symbolic link is skipped where the system will not make one,
and the verdict says so.

## An in-toto Statement of what a program may do

```
velaris attest examples/effects.vel --output effects.intoto.json
velaris attest examples/effects.vel --json          # the Statement on stdout
velaris attest src --output src.jsonl               # one Statement per file
```

`velaris attest` writes an in-toto Statement v1 whose predicate type is
`https://gowrishankar-infra.github.io/velaris-lang/capability/v1`
(velaris-spec section 8.5; the URL is the type's description and
schema). Its subjects are the audited file and every file it imports,
each by the sha256 of its bytes - a file of the standard library named
`<stdlib>/NAME` - and its predicate is

```json
{"producer": {"name": "velaris-lang", "uri": "https://github.com/gowrishankar-infra/velaris-lang"},
 "specification": "velaris-spec 0.5",
 "auditedAt": "2026-09-11T00:00:00Z",
 "audit": { "...": "the velaris.audit/1 document of that file" }}
```

The audit is `audit()`'s output for those bytes, as it stands - effects,
`fs_paths`, `net_hosts`, `ffi_modules`, `ffi_any`, `counts`,
`proven_share`, `prover`, the Velaris version - so the Statement cannot
say more than the audit, or differ from it. What the audit cannot
determine it says in its own fields, and the Statement carries them: a
module named while running is `ffi_any: true`, not a shorter list of
modules; a path or URL built while running is `read_any`, `write_any`
or `any`; a count the text does not fix is `null`; a program that does
not compile is `ok: false` with its problems, `counts: null` and
`prover: false`; and without a prover `prover` is `false`, so a
`proven_share` of 0 is not read as proofs that failed. A file that
changes while it is being attested is an error, not a Statement.

A directory gives one Statement per `.vel` file, found as `velaris
capabilities` finds them, one Statement to a line (JSON Lines), since
the predicate type has one audit per Statement. An in-toto Bundle
(`.intoto.jsonl`) is JSON Lines too, of signed envelopes: sign each line
and write the envelopes one to a line to make one. `SOURCE_DATE_EPOCH`, when
set, fixes `auditedAt`, so one commit gives the same bytes twice.
`velaris.attest(path)` in the library returns the same Statements as a
list.

**Signing.** Velaris writes the Statement and signs nothing. Signing it
turns it into an attestation: a DSSE envelope over the Statement, in a
Sigstore bundle.

With cosign (v3), keyless - a browser sign-in on a workstation, the
job's identity in CI:

```
cosign attest-blob --yes --statement effects.intoto.json \
    --bundle effects.intoto.sigstore.json
cosign verify-blob-attestation --bundle effects.intoto.sigstore.json \
    --type https://gowrishankar-infra.github.io/velaris-lang/capability/v1 \
    --certificate-identity you@example.com \
    --certificate-oidc-issuer https://github.com/login/oauth \
    examples/effects.vel
```

or with a key pair (`cosign generate-key-pair`):

```
cosign attest-blob --yes --key cosign.key --statement effects.intoto.json \
    --bundle effects.intoto.sigstore.json
cosign verify-blob-attestation --key cosign.pub --bundle effects.intoto.sigstore.json \
    --type https://gowrishankar-infra.github.io/velaris-lang/capability/v1 \
    examples/effects.vel
```

`verify-blob-attestation` checks that the file given is the Statement's
subject by digest and that the predicate type is this one, and fails
otherwise. Both forms record the signature in Sigstore's public
transparency log unless a signing config says not to.

With sigstore-python (4.x): its command line's `sigstore attest` takes
only SLSA provenance predicates, so use its library - the same calls the
release workflow makes:

```python
from sigstore.dsse import Statement
from sigstore.models import ClientTrustConfig
from sigstore.oidc import IdentityToken, Issuer, detect_credential
from sigstore.sign import SigningContext

statement = Statement(open("effects.intoto.json", "rb").read())
trust = ClientTrustConfig.production()
token = detect_credential()                 # the job's identity in CI,
identity = (IdentityToken(token) if token   # else a browser sign-in
            else Issuer(trust.signing_config.get_oidc_url()).identity_token())
context = SigningContext.from_trust_config(trust)
with context.signer(identity) as signer:
    bundle = signer.sign_dsse(statement)
open("effects.intoto.sigstore.json", "w").write(bundle.to_json())
```

and to verify, `Verifier.production().verify_dsse(bundle,
Identity(identity=..., issuer=...))` returns the signed Statement, whose
first subject's digest must then be the sha256 of the file.
`sigstore sign effects.intoto.json` also works, and signs the Statement
file as bytes rather than as a DSSE envelope, the way the release signs
its other files.

Every release carries one: `velaris-attestation-X.Y.Z.intoto.json` for
`examples/effects.vel`, signed both ways by the release workflow's
identity and verified in that workflow before it is attached
([SECURITY.md](SECURITY.md)).

## As a commit hook

```yaml
repos:
  - repo: https://github.com/gowrishankar-infra/velaris-lang
    rev: v2.55
    hooks:
      - id: velaris-check      # it compiles, and the promises hold
      - id: velaris-fmt        # canonically formatted
      - id: velaris-proofs     # at least 80% proven, not just checked
```

## Trying it with nothing installed

```
pipx run --spec velaris-lang velaris hello.vel --allow io
```

Or open the [playground](https://gowrishankar-infra.github.io/velaris-lang/playground.html) -
the real compiler, in a browser, nothing to install.
