# Known open

This is the known-open table of the [threat model](../THREAT_MODEL.md), on a page of its own so that each gap recorded here does not push the threat model past the size a page of the site may be.

The gaps this model does not close, kept as a table so the list is one
place and stays current. None is a defect to be reported under
SECURITY.md's challenge; each is a stated limit of what the effect
budget is. A finding that a guarantee above is *broken* - a "proven"
promise that breaks at run time, or an effect performed outside the
budget - is a different thing, and SECURITY.md says how it is handled.

Seven of the rows below were written from real incidents rather than from
first principles. [incidents/](../incidents/README.md) is a catalogue of
publicly reported attacks in this lane, each with the shape of the attack
written as a Sabline program, the command, and what the runtime actually
printed; where the answer was "nothing here refuses this", the sentence
saying so is a row here. Nothing in that catalogue is a claim that adopting
Sabline would have prevented the real event, and every entry says which
part of its incident is outside Sabline entirely.

The last three rows, and a sentence in two others, were written from the
[competitor table](competitors.md): each is a place where another tool
does better than Sabline on the benchmark, and each says what
[decisions/0006](../decisions/0006-where-sabline-loses.md) decided for it
on 2026-09-24 - the milestone of `plan/9.0.md` that closes it, or that
nothing is scheduled. None of it is built.

| Open | What it is | What to do |
|---|---|---|
| Timing and other side channels | How long a run takes, how much CPU or cache it uses, the size or timing of its output - none is measured or bounded, and a program can signal through any of them. Not a non-interference result (7.0 bounds a secret's *value*, not the run's timing). | Do not run code whose timing you must not leak on shared hardware; if one bit per run matters, do not grant `env`. |
| A granted `ffi` module | Within a granted module, that module's full behaviour is granted; `ffi:os` is the operating system as the current user. The allow-list narrows which module a call reaches, not what it does. | Grant `ffi` only when the task needs it, name the modules, and treat the grant as trust in those modules. Never grant `ffi:os`, `ffi:subprocess` or plain `ffi` to code you have not read. |
| Native code | A granted module may be or ship a compiled extension with no source and no runtime bound. `sabline.audit/1`'s `ffi_native` reports where it is found (8.0), and never claims a module is free of it. The competitor benchmark's 19d is this case: a vendored library writes a file of its own through `ctypes`, and no tool stops it - a module the confinement table does not name widens the OS policy to nothing enforced. *Closed by:* M4, for a run that opts in - `--confine strict` ([decisions/0006](../decisions/0006-where-sabline-loses.md) section e, accepted), in which an `ffi` grant widens nothing, lets the kernel refuse such a write outside the budget's grants on Linux and macOS, and on Windows only where the budget grants no write. The default does not move: without it, 19d runs unconfined as today. What a native module does inside the grants, nothing will see. | Read `ffi_native`; grant a native module only when you would grant the machine. |
| Secrets arriving another way | `Secret of T` marks the results of `env()` and `read_file_secret()` only. A value read through `read_line`, passed in through `args()`, fetched over `net`, returned by a granted `ffi` module, or hard-coded is an ordinary value with no protection. | Run agent-written programs with a clean environment; do not treat a secret from another source as protected. |
| Confinement on Linux: what it leaves | Full confinement holds files, the network and processes to the budget. It does not hold: a host named in a `net:` grant (the kernel holds ports at most, with Landlock ABI 4 or later, and the level says partial); a credential location under a broad grant (E318 is the language's alone); `env`, which is the process's own memory; a hard link or a bind mount that was inside a granted path before the run, which is that path's content; a Unix socket the process was started holding, and any a granted Python module that widens the policy to any host then opens; the temporary directories of the same user's other confined command-line runs, which share one parent; files on a kernel older than 5.13, which has no Landlock; and sockets and processes where seccomp has no table (anything but x86_64 and aarch64) - the level says partial or none there, and why. It is the kernel's guarantee and no better. | Read `confinement` in the receipt, or `sabline doctor`; give every `net:` grant a port; run on a kernel with Landlock ABI 4 or later. |
| Confinement on macOS: partial | Writes, the network and fork/exec are held by a sandbox profile. Reads are refused only under the home directory and /Volumes, not held to exactly the grants - and the names in the working directory and in each directory above it stay readable, since `getcwd` reads them - because a Python that must read its own installation cannot be started under a deny-all read rule that is also portable; a `net:` grant allows the whole network; signals are not held, and neither is input pushed at the terminal the run was started from (TIOCSTI), which the profile language has no rule for; and Apple has deprecated sandbox profiles (`sandbox-exec` and `sandbox_init` alike), so a later macOS may stop honouring them, at which point the level says none. | Treat macOS as partial; keep what must not be read outside the home directory's reach, or run on Linux. |
| Confinement on Windows: partial | A job object refuses a second process, the clipboard and the desktop; every privilege is removed from the token; and a budget with no write grant runs at the low integrity level, which refuses a write to anything of the user's. Not held: any read; the network; input written to the console the run was started from, which a process attached to a console may always do; and every write once the budget holds a write grant, because lowering the integrity level would then need the granted directory relabelled. Reads and the network need an AppContainer, which is not used: a process cannot enter one after starting, and a `python.exe` started in one cannot read its own installation unless that was made readable to ALL APPLICATION PACKAGES, which python.org's, the Store's and a virtual environment's are not. | Treat Windows as partial; for code whose reads or network reach matter, run on Linux, or in a container or a virtual machine. |
| Runs that are not confined | An in-process `sabline.run()` with no `timeout` and no `max_memory_mb` runs in the caller's process, which Sabline must not confine; the REPL, `sabline test` and `sabline bench` run many programs in one process; and a budget that grants `ffi:os`, `ffi:subprocess`, plain `ffi` or a module the table does not name widens the OS policy to nothing enforced. Each says `"confinement": "none"` and why, and from 8.7 a command-line run whose budget names a module the table does not - even one that does not exist - also says on stderr, once, that the operating system layer is off for this run. And a confined process is still a process of the user's: what the budget grants, it does with the user's own rights. *Closed by:* M4 in part, and only for a run that opts in: under `--confine strict` ([decisions/0006](../decisions/0006-where-sabline-loses.md) section e, accepted) an `ffi` grant widens nothing, and the OS policy is the budget's grants alone. Without it, and for the other runs in this row, nothing changes. | Give `run()` a timeout, or use a `Pool`, so the run has a process of its own; name `ffi` modules the table knows; run code you have not read as a different user, or in a container or a virtual machine, when the stakes warrant it. |
| The fault-injection hook | `SABLINE_FAULT_INJECT`, read from the environment a run was started with, makes the runtime attempt one fixed effect (a read, a write, a connection, a process, a signal, a mount) so the honesty test can show the kernel refusing it. It performs nothing the person who set it could not do themselves, and a program cannot set it. | Do not start Sabline with an environment someone else controls - which was already true of `PATH` and `PYTHONPATH`. |
| What a receipt shows that is not a value | A receipt (8.1) keeps out every value a program handled, but holds its exit status, where it stopped, its counts and its wall time - which a program that declassified something can choose from it. | Do not grant `declassify` to code whose receipts you will share. |
| Writes to where Python imports from | A write grant to a directory on some Python's import path lets a program leave code the next Python process runs. Sabline does not look for this on a plain run; an ejected launcher refuses such a budget where it is launched. | Grant writes to data directories only; run Python with `-I` where you can. |
| An ejected directory | It keeps the Sabline it was ejected with; no fix reaches it, and its launcher cannot check itself. | Eject again after an upgrade; check `SHA256SUMS` when the directory could have been written by someone else. |
| A program that stalls a review | `sabline review` compiles every program under the directory, at the ref and in the working tree, in its own process, with none of the ceiling `check` and `audit` have had since 8.0 and `capabilities check` has had since 8.2.1: a program built to exhaust the type checker holds it, and the Action's pull-request comment step, which runs it, until the job's own timeout (known open in 8.2.1). | Give a job that comments on other people's pull requests a `timeout-minutes`. |
| A predicate type is a name on a domain | `https://sabline.dev/capability/v1` and `https://sabline.dev/receipt/v1` name a domain, and a domain can change hands: whoever holds sabline.dev decides what those pages say, and a lapsed registration would let someone else publish a different description at the same addresses. A type is an identifier, not a signature; nothing is fetched from it to verify a Statement. A reader accepts three names for each type - the two earlier addresses this project used are listed in [docs/renamed.md](renamed.md) - and none is ever dropped, so each move widens the set of domains a verifier trusts the maintainer to keep. Neither `velaris.dev` nor `velaris.io` has ever been this project's, and a type under either is refused. | Trust a Statement by its signature, its signer's identity and its subjects' digests, never by what its type's page says; accept a fixed list of types, as `sabline verify` does. |
| The user running sabline | The user running sabline is trusted; anything running as that user is that user - the receipts, everything. Such a process can edit the program, the budget, a receipt after it is written, or the installed Sabline itself. The proof cache, which such a process could once write, was removed in 8.2; that does not make anything else the user can write trustworthy. | Run code you have not read as a different user, or in a container or a virtual machine. Do not rely on a report made in an account something else controls. |
| Code that is not Sabline | Sabline bounds programs written in Sabline and run by `sabline`. An npm post-install script, a pip build hook, a shell command an agent runs, an IDE extension's own tools - none of them is a Sabline program, and a budget is not near any of them. Most of the incidents in [incidents/](../incidents/README.md) are of exactly this kind, and their entries say so rather than claiming a refusal. *Closed by:* nothing - no milestone brings a post-install script, a build hook, a shell command or an extension's own tools into a budget's reach; the incidents of this shape (nx-s1ngularity, amazon-q-extension-wiper, circleci-oauth-token-theft, shai-hulud-npm-worm) are out of scope on purpose. | Where an agent writes code you must run, have it write Sabline and run it with `sabline`; for everything else the answer is not here, and is a container, a separate user or a different machine. |
| How an artefact was built | A budget starts existing when a program starts running. Nothing here inspects a build, a cache, a workflow trigger, a tarball or a compiled extension, and this repository's own releases are built by a pipeline with the same shape as the ones that were attacked. An attestation attests to the bytes it was given, whatever they are. *Closed by:* nothing - no milestone makes a budget inspect a build, a cache, a workflow trigger or a compiled artefact; ultralytics-pypi-cache-poisoning and xz-utils-backdoor are out of scope on purpose. | Verify a release's signature and its attestation, pin by digest, and read `sabline audit`'s `ffi_native` for granted modules; do not read an attestation as evidence that what it covers is clean. |
| A flow between two granted places | A grant names a resource - an effect, a host, a port, a path, a Python module, a tool, a count - and never a relation between two of them. Nothing can say that data read from one granted place may not be written to another. `Secret of T` is the one place a value's destination is tracked, and it marks the results of `env()` and `read_file_secret()` only, not what came back from a granted read or a granted request. *Closed by:* M6 in part - `Untrusted of T` (planned) makes a tool result `Untrusted` and a tool's arguments a sink, so when the agent is a Sabline program, private content cannot become a tool call's argument without an audited `trust`; a value reaching `post`'s body is not a sink by design, so that flow stays open, and the general per-value case is ChainCaps', which Sabline does not implement. The competitor benchmark's 16a to 16c are this case - a private ledger posted to the one host the task is granted - and CaMeL refuses them where Sabline cannot; M6's reach does not close them, because the ledger travels in a post's body and goes to the same host as the task's own post. An `fs:secret:PATH` grant ([decisions/0006](../decisions/0006-where-sabline-loses.md) section d, accepted for M6) makes a file the operator names a `Secret` however it is read, which closes 16a to 16c; it refuses the correct 16d as well, the same false positive CaMeL takes, and that is the grant's price, not a defect to close. A coarse guard-mode session latch (github-mcp-toxic-agent-flow) would close a slice of it and is built only if guard mode gets users. | Where two granted resources must not meet, separate them into two runs with two budgets, and read each run's receipt; do not expect one budget to express the rule. |
| What an operation means inside a granted effect | A grant decides whether a program may reach something, not what it does once it can. `fs:write:./data` is any write to that directory, including deleting what is there; `ffi:sqlite3` is any statement that module will run, `DROP TABLE` among them; a `net:` host grant is any request to that host, whatever its method. The counts (`@100`) bound how many operations a run makes, not which. *Closed by:* M6 in part - a planned `db` effect (`db:read`/`db:write`) replaces the three-module `ffi` grant for a database, and a planned `fs:delete` makes deletion a direction of its own; but `db:write` would still allow `DROP`, which a planned `db:schema` grant, classified through SQLite's authorizer, would separate. The general limit - a grant names reach, not what is done with it - is closed by no milestone. | Grant the narrowest directory, module and host the task needs, and put anything irreversible behind something outside Sabline: a replica, a backup, a read-only credential. |
| What a host does with a call it was given | A `tool:` grant holds the arguments the *program* passes - `tool:send_email:to=*@corp.com` refuses a recipient outside the pattern before the host hears of the call. It says nothing about what the host does with the call afterwards: a header the server adds, a copy it keeps, a second request it makes. `sabline mcp-verify` checks a signed manifest, and only Sabline's own. *Closed by:* nothing - no rule a caller applies can see inside another process's handling of a call, and guard mode (M5) is blind in the same way; postmark-mcp-bcc-exfiltration is out of scope for this reason. | Treat a tool's implementation as trusted code, the way `ffi:` modules are treated; read the receipt's tool calls for what was asked, not for what happened. |
| A module name a model invented | `ffi:NAME` names a module in the Python environment `sabline` was started in. Sabline does not install it, does not ask where it came from, and has no way to know the name was hallucinated by the model that wrote the program and registered by somebody else. A Sabline import is a path into the project and has no such exposure; a Python grant does. *Closed by:* an `ffi` lock - a distribution and a hash recorded per granted module in `sabline.lock`, refused at import on any change - which is deferred past the 9.0 release candidate on cost; until it lands, package-hallucination stays `PARTIAL`. | Read every `ffi:` grant as the name of a package you are vouching for; run `sabline audit` before granting one, and install into an environment you control. |
| Nothing here reads a tool description | An MCP tool's description, its name and its schema are text a model reads and a person usually does not, and a poisoned one steers the model rather than the program. Sabline is not an MCP client: it neither reads those descriptions nor notices when one changes. Its own MCP server's `--max-allow` bounds what a steered model may ask *this* server for, and nothing more. *Closed by:* M5 in part - guard mode puts an existing server's calls under a budget, so a poisoned description can only steer the model into calls the budget already allows; pinning each upstream tool's description and refusing calls after a change (a planned M5 addition) would catch a rug-pull. Judging whether a description is malicious is a natural-language judgement Sabline does not make, and no milestone closes it. | Leave `sabline mcp` at the narrowest `--max-allow` the task needs, and keep the review of other servers' tool descriptions outside Sabline, where it belongs. |
| One program, not the whole module | A program that runs another program needs `ffi:subprocess`, which grants the whole module - any program, any arguments, a shell among them - and widens the OS policy to nothing enforced. There is no grant for one program, as Deno's `--allow-run=git` is: the competitor benchmark's 17a and 17b run `git` for the task and a second program beside it, and Deno refuses the second where Sabline cannot. *Closed by:* M6 in part - a `proc:NAME` grant ([decisions/0006](../decisions/0006-where-sabline-loses.md) section a, accepted) starts one program, resolved when the budget is read, with no shell, held to the run's OS policy. Two limits stay: a granted program that is itself an interpreter defeats it at the language level and is as wide as that policy allows, and Windows cannot restrict which binary runs, so there the name is the language's check alone. | Do not grant `ffi:subprocess` to code you have not read; run the program the task needs yourself and pass its output in, or run the task in a container. |
| A refusal ends the whole run | A refusal stops the program and cannot be caught, so the legitimate work after it is lost with it. In the competitor benchmark's 12a to 12c and 20b to 20d Deno refused the same operation, the program caught the denial and finished its task, and the Sabline run did not. That is the price of a program getting one wrong guess per run, which is what keeps a budget from becoming an oracle a program can probe. *Closed by:* nothing scheduled. A bounded `recover@N` grant ([decisions/0006](../decisions/0006-where-sabline-loses.md) section b), which would let at most N refusals of builtins that can fail become their failures, is deferred, not rejected: it costs seven days for four rows, and any recovery gives a program a way to probe the budget, so it gets a decision of its own and an adversarial pass before it is built. Unbounded catching is closed, and a builtin that cannot fail, `write_file` among them, would end the run whatever is decided. | Grant what the task needs, including what it will try; put a task's essential work before its optional calls; read the receipt's `refusals`, not only the exit status. |
| Correct programs the rules refuse | The termination rule (SPEC.md section 9.5) reports a correct loop that ends when its input does, or by a measure that is not a counter (Euclid's algorithm), as not shown to end - E612 under `--strict` - and whole numbers stop at 64 bits (E407), so a correct 25! or a product modulo 2^61 - 1 does not run. The competitor benchmark's 18a to 18d are such programs, and every other tool runs them clean. *Closed by:* M2 for 18a - a loop verdict "bounded by its input" ([decisions/0006](../decisions/0006-where-sabline-loses.md) section c, accepted) reports a loop that ends when its input does, and E612 does not fire for it. Nothing scheduled for 18b: Euclid's loop ends by a falling measure, not by its input, and a `decreases` clause that would state the measure is an open proposal that gets a decision of its own and an adversarial pass first. 18c and 18d are declared false positives: nothing will make a whole number wider than 64 bits, since that is the rule that stops the overflows the benchmark's category 5 is made of. | Run `sabline check` without `--strict` where such loops are expected, and let the run's time limit guard them; compute past 64 bits in a granted Python module that returns text, or outside Sabline. |

## Every known-open item, and where it lands

Each row of the table above, with the controls on the [crosswalk](crosswalk.md) that it leaves open. None of these rows is a broken guarantee; each is a stated limit.

### Timing and other side channels

How long a run takes, its CPU and cache use, and the size and timing of its output are not measured or bounded, and a program can signal through any of them.

It leaves open:

- OWASP Agentic Top 10: ASI03 (partial)
- AIUC-1: A006 (partial), A008 (partial)
- NIST AI RMF: MEASURE 2.10 (not addressed)

### A granted `ffi` module

Within a granted module, that module's whole behaviour is granted; the allow-list narrows which module a call reaches, not what the module does.

It leaves open:

- OWASP Agentic Top 10: ASI02 (partial), ASI04 (partial), ASI05 (partial), ASI10 (partial)
- AIUC-1: A003 (partial), A005 (partial), B006 (partial), D003 (partial), F001 (partial)
- NIST AI RMF: MEASURE 2.7 (partial), MANAGE 3.1 (partial)

### Native code

A granted module may be or ship compiled code with no source and no bound; the audit's `ffi_native` reports it where it is found.

It leaves open:

- OWASP Agentic Top 10: ASI02 (partial), ASI04 (partial), ASI05 (partial)
- AIUC-1: B006 (partial), D003 (partial)
- NIST AI RMF: MANAGE 3.1 (partial)

### Secrets arriving another way

`Secret of T` marks only what `env()` and `read_file_secret()` return; a secret from anywhere else is an ordinary value.

It leaves open:

- OWASP Agentic Top 10: ASI03 (partial)
- AIUC-1: A006 (partial), A008 (partial)
- NIST AI RMF: MEASURE 2.10 (not addressed)

### Confinement on Linux: what it leaves

Full confinement holds files, the network and processes to the budget. It does not hold a host named in a `net:` grant, a credential location under a broad grant, `env`, or a hard link or bind mount that was inside a granted path before the run; and it is no better than the kernel.

It leaves open:

- OWASP Agentic Top 10: ASI05 (partial), ASI10 (partial)
- AIUC-1: B006 (partial), B008 (partial), D003 (partial), F001 (partial)
- NIST AI RMF: MEASURE 2.7 (partial)

### Confinement on macOS: partial

Writes, the network and new processes are held by a sandbox profile; reads are refused only under the home directory and /Volumes; and Apple has deprecated the mechanism.

It leaves open:

- OWASP Agentic Top 10: ASI05 (partial), ASI10 (partial)
- AIUC-1: B006 (partial), B008 (partial), D003 (partial), F001 (partial)
- NIST AI RMF: MEASURE 2.7 (partial)

### Confinement on Windows: partial

A second process is refused, every privilege is removed from the token, and a budget with no write grant can write nothing of the user's. Reads, the network, and writes under a budget that grants any, are not held.

It leaves open:

- OWASP Agentic Top 10: ASI05 (partial), ASI10 (partial)
- AIUC-1: B006 (partial), B008 (partial), D003 (partial), F001 (partial)
- NIST AI RMF: MEASURE 2.7 (partial)

### Runs that are not confined

An in-process `sabline.run()` with no limit, the REPL, `sabline test` and `sabline bench` are not confined, and a budget that grants `ffi:os`, `ffi:subprocess`, plain `ffi` or a module the table does not name widens the OS policy to nothing enforced. A confined process still runs as the user.

It leaves open:

- OWASP Agentic Top 10: ASI05 (partial), ASI10 (partial)
- AIUC-1: B006 (partial), B008 (partial), D003 (partial), F001 (partial)
- NIST AI RMF: MEASURE 2.7 (partial)

### The fault-injection hook

`SABLINE_FAULT_INJECT`, read from the environment a run was started with, makes the runtime attempt one fixed effect so the honesty test can show the kernel refusing it. A program cannot set it, and it performs nothing the person who set it could not.

It leaves open:

- AIUC-1: B008 (partial)

### What a receipt shows that is not a value

A receipt keeps out every value, but holds the exit status, where the run stopped, its counts and its wall time, which a program that declassified something can choose.

It leaves open:

- OWASP Agentic Top 10: ASI10 (partial)
- AIUC-1: A006 (partial), A008 (partial), B009 (not addressed), E015 (partial)

### Writes to where Python imports from

A write grant to a directory on some Python's import path lets a program leave code the next Python process runs.

It leaves open:

- OWASP Agentic Top 10: ASI05 (partial)
- AIUC-1: B006 (partial)

### An ejected directory

An ejected directory keeps the Sabline it was ejected with, and its launcher cannot check itself.

It leaves open:

- OWASP Agentic Top 10: ASI04 (partial)
- AIUC-1: B008 (partial)
- NIST AI RMF: MANAGE 3.1 (partial)

### A program that stalls a review

`sabline review` compiles every program with no ceiling, so a program built to exhaust the type checker holds it, and the Action's comment step, until the job times out.

It leaves open:

- AIUC-1: C002 (partial), C007 (partial)
- NIST AI RMF: MEASURE 2.7 (partial)

### A predicate type is a name on a domain

The two predicate types name sabline.dev; whoever holds a domain decides what its pages say, and a type is an identifier, not a signature.

It leaves open:

- OWASP Agentic Top 10: ASI04 (partial)
- AIUC-1: B008 (partial)

### The user running sabline

Anything running as the user who runs Sabline can edit the program, the budget, a receipt after it is written, or Sabline itself.

It leaves open:

- OWASP Agentic Top 10: ASI03 (partial), ASI10 (partial)
- AIUC-1: B008 (partial), E015 (partial)
- NIST AI RMF: MEASURE 2.4 (partial)

### Code that is not Sabline

Sabline bounds programs written in Sabline and run by `sabline`; a post-install script, a build hook, a shell command an agent runs and an extension's own tools are none of them near a budget.

It leaves open:

- OWASP Agentic Top 10: ASI02 (partial), ASI04 (partial), ASI05 (partial), ASI10 (partial)
- AIUC-1: B006 (partial), B010 (partial), D003 (partial)
- NIST AI RMF: MANAGE 3.1 (partial), MEASURE 2.7 (partial)

### How an artefact was built

Nothing here inspects a build, a cache, a workflow trigger, a tarball or a compiled extension, and an attestation attests to the bytes it was given.

It leaves open:

- OWASP Agentic Top 10: ASI04 (partial), ASI05 (partial)
- AIUC-1: B008 (partial), D003 (partial)
- NIST AI RMF: MANAGE 3.1 (partial), MEASURE 2.7 (partial)

### A flow between two granted places

A grant names a resource and never a relation between two of them: nothing can say that data read from one granted place may not be written to another.

It leaves open:

- OWASP Agentic Top 10: ASI02 (partial), ASI03 (partial)
- AIUC-1: A003 (partial), A005 (partial), A008 (partial), D003 (partial)
- NIST AI RMF: MEASURE 2.7 (partial)

### What an operation means inside a granted effect

A grant decides whether a program may reach something, not what it does once it can: `fs:write:` includes deleting, `ffi:sqlite3` includes `DROP TABLE`, and a `net:` host grant is any method.

It leaves open:

- OWASP Agentic Top 10: ASI02 (partial), ASI08 (partial)
- AIUC-1: A003 (partial), B006 (partial), D003 (partial)
- NIST AI RMF: MANAGE 2.2 (partial), MEASURE 2.6 (partial)

### What a host does with a call it was given

A `tool:` grant holds the arguments the program passes and says nothing about what the host does with the call afterwards - a header it adds, a copy it keeps, a second request it makes.

It leaves open:

- OWASP Agentic Top 10: ASI02 (partial), ASI04 (partial)
- AIUC-1: D003 (partial), E009 (partial)
- NIST AI RMF: MEASURE 2.7 (partial)

### A module name a model invented

`ffi:NAME` names a module in the Python environment Sabline was started in; Sabline does not install it, does not ask where it came from, and cannot know the name was hallucinated.

It leaves open:

- OWASP Agentic Top 10: ASI04 (partial), ASI05 (partial)
- AIUC-1: B006 (partial), D001 (not addressed), D003 (partial)
- NIST AI RMF: MANAGE 3.1 (partial)

### Nothing here reads a tool description

An MCP tool's name, description and schema are text a model reads and a person usually does not; Sabline is not an MCP client and neither reads them nor notices when one changes.

It leaves open:

- OWASP Agentic Top 10: ASI01 (not addressed), ASI04 (partial)
- AIUC-1: B002 (not addressed), D003 (partial)
- NIST AI RMF: MEASURE 2.7 (partial)

### One program, not the whole module

A program that runs another program needs `ffi:subprocess`, which grants the whole module; there is no grant for one program.

It leaves open:

- OWASP Agentic Top 10: ASI02 (partial), ASI05 (partial)
- AIUC-1: B006 (partial), D003 (partial)
- NIST AI RMF: MEASURE 2.7 (partial)

### A refusal ends the whole run

A refusal cannot be caught, so the legitimate work after it is lost with it; the budget holds, and the task does not finish.

It leaves open:

- OWASP Agentic Top 10: ASI08 (partial)
- NIST AI RMF: MEASURE 2.5 (partial)

### Correct programs the rules refuse

A correct loop that ends when its input does or by a measure that is not a counter is reported as not shown to end, and a correct whole number past 64 bits stops the run.

It leaves open:

- AIUC-1: C002 (partial)
- NIST AI RMF: MEASURE 2.5 (partial)

No known-open item lands on an ACS row, since every ACS row is not addressed for a reason that comes first: Sabline implements none of ACS.
