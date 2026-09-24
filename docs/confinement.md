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

A module the table does not name widens it whether or not the program
imports it, and whether or not it exists: the grant is what is read, and
nothing is imported to find out. So from 8.7 a command-line run whose budget
names one says so on stderr, once, as the program is about to run:

    sabline: ffi:nosuchmod is not in the confinement table, so the operating system layer is off for this run: the budget is the only boundary

`--no-confine` says its own line instead. `ffi:os` and `ffi:subprocess`,
which the table names as widening to nothing enforced, and plain `ffi`,
which names no module, say nothing more than the receipt does.

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

It also runs every escape target of `check_sandbox.py`, and the file and `ffi`
targets of `check_adversarial.py`, on a Sabline whose budget checks have been
knocked out, and records which the kernel stops and which only the language
does (`tests/confine/kernel-linux.json`, `kernel-windows.json`).
