# Confinement

From 8.4 a process that runs a Sabline program asks the operating system to
hold the budget it was given, before the program's first statement runs. The
budget is still enforced by the interpreter, at the moment each effect is
attempted, exactly as before. Confinement is the second guard under it: if a
defect in Sabline itself - in the interpreter, in a builtin, in the budget's
own checks - attempts an effect the budget does not grant, the kernel refuses
it, and the fault is a crash inside a box and not an escape.

```sh
sabline program.vel                     # confined, where the system can
sabline program.vel --confine strict    # and no granted module widens it (9.0)
sabline program.vel --require-confinement full   # or refuse to run (9.0)
sabline program.vel --no-confine        # not confined, and stderr says so
sabline doctor                          # what this machine offers
sabline eval --confinement-probe        # what a confined worker could do
```

It is on by default on the command line, in `sabline.run(timeout=...)`, in
`sabline.Pool`, on the HTTP door, on the MCP server and under `sabline eval`.
`--no-confine` (and `confine=False` in the library) turns it off and writes
one line to stderr. It is a flag of the operator's command line: a program's
words after `--`, a door's request and an MCP tool call cannot carry it.

## One derivation

`sabline/confine.py`'s `os_policy(budget)` is the only place a budget becomes
an OS policy. It reads nothing of the machine, so the same budget gives the
same policy everywhere, and a receipt records its sha256. The policy says
which paths may be read and which written (or that a direction is not
restricted), whether the network is closed, open, or open to named hosts, that
no process is started, and which granted Python modules widened it.

The full table - every budget item, and what Linux, macOS and Windows enforce
for it - is in [THREAT_MODEL.md](../THREAT_MODEL.md), under **What the
operating system enforces**, and `check_confine.py` holds that table to the
module word for word. In short:

| | Linux | macOS | Windows |
|---|---|---|---|
| Mechanism | Landlock and seccomp-bpf | a sandbox profile (`sandbox_init`, the call `sandbox-exec` makes) | a job object, a token with its privileges removed, a low integrity level |
| Files read | held to the `fs:read` grants and what the interpreter itself reads | refused under the home directory and /Volumes only | not held |
| Files written | held to the `fs:write` grants | held to the `fs:write` grants | held only when the budget grants no write at all |
| Network | no socket without `net`; with Landlock ABI 4 or later, TCP ports of the grants | closed without `net`; open with it | not held |
| A new process | refused | refused | refused |
| The level of a run under `io` | full | partial | partial |

`@N` counts stay in the language on every system. So does the host in a
`net:HOST` grant: no kernel here can hold a host name, and a run with one says
partial.

## The level, and its reason

Every confined run reports one of three levels, with the reason:

- **full** - every file, network and process limit of this run's budget is
  held by the kernel.
- **partial** - some are, and the reason names each that is not.
- **none** - nothing is: `--no-confine`, a granted module that widens the
  policy to nothing enforced, a system that offers nothing, or a run that is
  exempt (below).

The level is what was applied and held, not what was asked for. It is in three
places:

- **The receipt.** `run_parameters.confinement` is the level,
  `confinement_reason` why, `confinement_layers` what was applied
  (`landlock-abi3`, `seccomp`, `sandbox-profile`, `job-object`,
  `token-privileges-removed`, `low-integrity`), and `os_policy_sha256` the
  digest of the OS policy the budget derives. `sabline receipts diff` names a
  run whose level is not one an earlier run of the same program had, and says
  when it is weaker.
- **The audit.** `sabline audit --json` has `confinement`: for the program's
  `safe_command`, the level and reason on each of the three systems where
  every layer that system has is there, and `widened_by`, the granted Python
  modules that widen the OS policy and to what. It reads nothing of the
  machine, so the audit stays the same bytes wherever it is made. The command
  line's audit prints what this machine would give.
- **`sabline doctor`.** What this machine offers, and the level a run under
  the default budget gets on it.

`sabline eval` requires full or partial, and refuses to run at none.

## Python modules widen it

A granted `ffi` module does whatever that module does, so the OS policy is
widened to what the module needs: nothing for `ffi:math` or `ffi:json`, any
path for `ffi:sqlite3` or `ffi:pathlib`, any host for `ffi:socket` or
`ffi:urllib`, and nothing enforced for `ffi:os`, `ffi:subprocess`, plain `ffi`
and any module the table in THREAT_MODEL.md does not name. The audit says
which, and a run under such a budget says `none` and why.

The grant is what is read, not the use: such a module widens the policy
whether or not the program imports it, and one the table does not name does
so whether or not it exists, since nothing is imported to find out. So from
8.7 a command-line run whose grants turn the operating system layer off says
so on stderr, once, as the program is about to run - one line, whenever the
budget's OS policy (the one `sabline audit` prints, and the receipt's
`os_policy_sha256` names) is `enforced: false`:

    sabline: plain ffi grants any module, so the operating system layer is off for this run: the budget is the only boundary
    sabline: ffi:os is granted, so the operating system layer is off for this run: the budget is the only boundary
    sabline: ffi:nosuchmod is not in the confinement table, so the operating system layer is off for this run: the budget is the only boundary

A grant of several says them together, on the same one line. `--no-confine`
says its own line instead. Nothing else changes: the run, its exit status
and its receipt are what they were, and `sabline.run()`, `sabline replay`,
a `Pool` and `sabline serve` write nothing new - the receipt is where they
say it.

## `--confine strict`: a granted module widens nothing (9.0)

`--confine strict` on the command line - `confine="strict"` for
`sabline.run`, a `Pool` or a `PoolRegistry` - takes the policy from the
budget alone. A granted `ffi` module widens nothing: the operating system is
asked to hold exactly the budget's `fs:` and `net:` grants and what the
interpreter itself reads, whatever modules are granted, so a module that
needs a path or a host needs it in the budget. The kernel checks the system
call, not the code that made it, so a module's own native code, its own
`ctypes` calls and its own `os.system` are held as the runtime's are:

```sh
sabline 19d.vel --allow io,ffi:nativefmt --confine strict
# the vendored library's native fopen outside every grant fails; the run
# goes on, and its receipt says the platform's level, not none
```

It is opt-in, and the default does not move: without it a module the table
does not name still widens the policy to nothing enforced, and the receipt
still says so. A module that does I/O the budget does not grant - `sqlite3`'s
journal beside its database, a library reading its own data files - fails
under it with an operating-system error, as it should. Under strict the OS
policy document carries `"strict": true`, so its digest in the receipt is
not that of the same budget without it, and the receipt's reason says no
module widened it. It closes the competitor benchmark's 19d where the
platform holds the write: on Linux and macOS, and on Windows when the budget
grants no write (decisions/0006, section e).

## `--require-confinement`: refuse, rather than warn (9.0)

`--require-confinement full` (or `partial`) - `require_confinement=` in the
library and for a pool - refuses a run whose confinement, once applied, is
below that level: [E326](https://sabline.dev/errors.html#E326), before its
first statement, with the level and the reason it got. The receipt records
the level and the refusal, so a refused run is accounted for like any
other. It is the level that was applied, never a prediction, and it is not
`--confine strict`: strict is about a granted module not widening the
policy, this is about whether the platform can hold the budget at all. They
compose - under strict a budget with `ffi` is confined more often, so this
refuses less.

What it refuses depends on the platform, and today plainly so:

| | Linux | macOS | Windows |
|---|---|---|---|
| `full` | runs where Landlock and seccomp hold every limit of the budget | refuses every run: the level is partial at best, since Apple has deprecated sandbox profiles | refuses every budget that restricts reads or the network - `io` itself does - because this runtime cannot hold either |
| `partial` | refuses only a run nothing holds: `ffi:os`, `ffi:subprocess`, plain `ffi` or an unnamed module without `--confine strict` | the same | the same |

On Windows that is the Python runtime's limit, not the platform's: an
AppContainer holds reads and the network, and the spike `plan/9.0.md`
asked for showed a Rust binary can start in one and be given exactly its
granted directories (rt/spikes/appcontainer/). When sabline-rt confines
its own runs (9.0, M4), `full` is a level a Windows budget can have; until
then this row says what is true.

`sabline.run` with no limit runs in the caller's process, which Sabline
does not confine, so a level asked of it is always refused. Pass a limit, or
use a `Pool`. Beside `--no-confine` - or `confine=False` - either option asks
for two opposite things, and is refused as a usage error.

With `SABLINE_REFERENCE_RUNTIME=rust`, a run asked for either stays the
Python package's and says so on stderr: sabline-rt does not ask the
operating system for anything until M4's port, so a level asked of it would
be a level it ignored.

## sabline-rt confines its own runs (9.0)

`SABLINE_REFERENCE_RUNTIME=rust` sends the run inside each command to
sabline-rt (`decisions/0002`), which from 9.0's M4 asks the operating system
for the same policy, in its own process, before the program's first
statement. The derivation is the same one twice over: `os_policy` is
ported into the crate, and the agreement gate compares the two documents -
the policy, its digest, what it asks the system to hold - for every budget
it has, under `--confine strict`, without it and under `--no-confine`,
before either runtime asks a kernel for anything. The seccomp filter, the
Landlock access masks for each ABI and the macOS profile are compared the
same way, on every platform and not only on the one that applies them: a
system call number typed wrong in one runtime is a difference on the commit
that types it.

What it applies is this page's table, layer for layer: Landlock and
seccomp-bpf on Linux, `sandbox_init` on macOS, the job object and the
token's privileges on Windows, with the low integrity level for a budget
that grants no write. One sentence differs from the package's, and only one:
Windows says that reads and the network need an AppContainer, and the reason
the package gives - that a `python.exe` started in one cannot read its own
installation - is not sabline-rt's reason. `rt/spikes/appcontainer/`
measured a Rust binary starting inside a container with no ACE on itself,
reading only the directories it was given and refused the network without a
capability, so what is true of sabline-rt is that it **does not enter one
yet**. Its receipt says that, in those words.

Two things a run through sabline-rt holds that the package's cannot, and one
it does not:

- **A `sabline.run()` with no limit can be confined** through sabline-rt,
  because the program runs in another process. In the package it runs in the
  caller's own, which Sabline never confines, so a level asked of it is
  refused (E326); through sabline-rt it is given.
- **A command confines itself too.** The network, a granted Python module
  and a tool are called in the process that started sabline-rt, so that
  process is held to the same policy - after sabline-rt has been started,
  since the policy lets no process be started. For a pool that process is
  its worker, which was already confined; for `sabline run` it is the
  command's own, which ends with the run.
- **An unbounded `sabline.run()`'s host is not confined**, for the same
  reason its own run never was: it is the caller's process. A run there whose
  budget grants `net`, `ffi` or `tool` says so in its receipt's reason, and
  its level is `partial` rather than `full`, because a connection opened in
  another process is not something this policy bounds.

`check_confine.py --runtime rust` asks every question on this page of
sabline-rt: the honesty test with its fault-injection hook, what still
works, what is reported, what a program cannot reach, what is tried against
the confinement itself, and both of 9.0's options. Three parts stay the
package's and say so: the policy, the filter and the table, which the
agreement gate already compares; the escape targets, which are measured on a
Sabline whose *Python* budget checks are knocked out; and `sabline eval`,
whose run sabline-rt does not take yet.

## What is not confined

- **An in-process `sabline.run()`** - one with no `timeout` and no
  `max_memory_mb` - runs in the caller's process. Landlock, seccomp, a sandbox
  profile and a lowered token cannot be taken off again, so Sabline does not
  put them on a process that is not its own. Pass a limit, or use a `Pool`.
- **The REPL, `sabline test` and `sabline bench`** run many programs in one
  process.
- **A `Pool` made without `import_root`** holds writes, the network and
  processes, not reads: its workers compile each program they are sent, and an
  import may name any `.vel` file. Give the pool an `import_root`, as both
  doors do, and reads are held too.
- **Compiling, proving and native code generation** happen before the policy
  is applied in a single run, because imports are read from wherever they are.
  The program's first statement runs after it.

## What it does not make true

Confinement is as good as the kernel, and it narrows a process without making
it another user. A host in a `net:` grant, a credential location under a broad
grant, `env`, a hard link or a bind mount that was inside a granted path before
the run, and timing, are outside it on every system; macOS and Windows are
partial, for the reasons THREAT_MODEL.md gives; and Apple has deprecated
sandbox profiles. Run code you have not read as a different user, or in a
container or a virtual machine, when the stakes warrant it.

## How it is tested

`check_confine.py` runs on every leg of CI. Its fault-injection hook
(`SABLINE_FAULT_INJECT`) makes the runtime itself, from Python and not from
Sabline, read a file, write one, open a connection, start a process and send a
signal outside the budget. Under confinement, what that system's row of the
table says is held is refused by the kernel and the run ends with
[E319](https://sabline.dev/errors.html#E319) naming the layers; what the row says is not held goes
through; and with `--no-confine` every one goes through. All three outcomes are
asserted, so the table is held to be true in both directions.

Under `--confine strict` it holds the five cases decisions/0006 set: 19d's
native `fopen`, a module that opens and writes a file through the C library,
and `os.system`'s process, each refused by the kernel with nothing made;
the hook's write, E319 with an `ffi` grant as without; and, without strict,
19d writing its file as it always has, its receipt saying none. Under
`--require-confinement` it holds E326 on each platform where the level is
below the one asked for, the run when it is not, the hook never tried by a
refused run, and the library's and a pool's refusals.

It also runs every escape target of `check_sandbox.py`, and the file and `ffi`
targets of `check_adversarial.py`, on a Sabline whose budget checks have been
knocked out, and records which the kernel stops and which only the language
does (`tests/confine/kernel-linux.json`, `kernel-windows.json`).
