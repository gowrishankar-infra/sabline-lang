# velaris eval

`velaris eval` runs one Velaris program the way an evaluation sandbox runs
code it was handed: under a profile that its own command line cannot relax,
with a receipt of the run every time. It is new in 8.3.

```sh
velaris eval task.vel --receipt task.receipt.json
velaris eval task.vel --allow io,fs:read:data,fs:write:out \
    --timeout 60 --max-memory-mb 1024 --receipt ../receipts/task.json
velaris eval task.vel --receipt-url https://collector.example.org/receipts
velaris eval --confinement-probe
```

## What it guarantees

- **No network, no Python, no environment.** `net`, `ffi` and `env` are
  refused in every spelling, `--allow all` is refused, and so is an `fs`
  grant that names no path. What is left is `io`, `fs:read:PATH`,
  `fs:write:PATH`, `clock`, `rand` and `declassify`, each enforced by the
  budget as in any run.
- **A time limit and a memory limit, always.** 30 seconds and 512 MB unless
  given; at most 600 seconds and 4096 MB. The program is checked and proved
  inside the same worker, under the same two limits. Past the time limit the
  run ends with E610, past the memory cap with E611 where the cap holds
  (Linux and Windows; on macOS it is best-effort, as everywhere).
- **A receipt, always.** `--receipt FILE`, `--receipt-url URL`, or both, are
  required. The file must not be inside any `fs` grant, read or write, and
  must not be the program; it is written after the run ends, by eval, not
  by the worker. The URL receives one JSON object per POST
  (`velaris.receipt-stream/1`): `started`, then each refusal and
  declassification as the worker reports it, then the receipt; no proxy is
  used and a redirect counts as a failure. If the file cannot be written or
  the receipt is not accepted at the URL, eval exits 3. The receipt is
  `velaris.receipt/1` with `run_parameters.profile` set to `"eval"` and
  `run_parameters.confinement` set to the level the worker got.
- **A stop from outside is honoured and recorded.** SIGINT, SIGTERM
  (SIGBREAK on Windows), or the appearance of the file named by
  `--stop-file`, asks the run to stop. The program runs interpreted, and
  every call and every loop turn can see the request, so a program that is
  running Velaris code stops at the next of them with E615, which it cannot
  catch; its receipt is complete. A worker that has not stopped after
  `--grace` seconds (5 unless given, at most 60) - one still checking the
  program, say - is killed; its receipt says so and is marked incomplete.
  Either way the receipt's `stop` records what asked, when, and how the stop
  was honoured. A signal is taken only where eval runs on the main thread,
  which is CPython 3.11 and later; before that no handler is installed,
  `--json` says `signals: false`, and on Windows a console break ends the
  process outright. `--stop-file` works everywhere.
- **Confinement by the operating system, fully or partly - or no run.** The
  worker asks the operating system to hold the run's budget before it is
  sent anything, as every pool worker does from 8.4
  ([Confinement](confinement.md)): on Linux, Landlock holds reads to the
  directory the program is served from and the `fs:read` grants, and writes
  to the `fs:write` grants and the run's own temporary directory, and
  seccomp-bpf refuses every socket and every new process; on macOS a sandbox
  profile holds writes, the network and fork/exec; on Windows a job object
  refuses a second process and, when the budget grants no write, a low
  integrity level refuses every write to the user's files. The receipt's
  `run_parameters` name the level (`confinement`: `full` or `partial`), why
  (`confinement_reason`), the layers applied (`confinement_layers`) and the
  sha256 of the OS policy the budget derives (`os_policy_sha256`). A worker
  that got **none** is not sent the program: eval refuses, exit 2, and says
  why. Until 8.4 such a run went ahead under the budget alone.

  `velaris eval --confinement-probe` starts a worker confined as a run is,
  has it try a TCP connection, a write and a read outside the granted
  directories and a process start, prints what was refused, and exits 1 if a
  refusal the level claims did not hold.
- **Nothing it runs reads the proof cache.** Velaris has kept no proofs
  between runs since 8.2, so there is no cache for `--no-cache` to turn off.

Anything else that would widen the profile is refused before the program is
read, with exit 2 and no receipt: `--no-check-ceiling`, `--check-timeout`,
`--check-memory-mb` and `--max-read` (the 64 MiB read ceiling stays), a flag
eval does not have, and a flag given twice. Words after `--` are the
program's `args()` and never eval's flags.

## What it does not guarantee

- **More confinement than the level says.** The level is what was applied,
  not what was asked for. `partial` is a run: on macOS reads are refused
  only under the home directory and /Volumes, and on Windows reads, the
  network, and writes under a budget that grants any, are not held. Read
  `confinement` and `confinement_reason` in the receipt, and refuse
  `partial` in whatever consumes it if that matters to you.
- **More than the table lists.** [Confinement](confinement.md) says what
  each system holds for each budget item and what it leaves: a write grant
  naming a file not made yet is held to the nearest directory that exists,
  and the level says partial; a hard link or a bind mount inside a granted
  path is that path's content; on Windows the worker's own job object holds
  one process while the memory job its parent made counts the launcher too,
  where `python.exe` is one.
- **A stop the worker cannot see, in less than the grace period.** A stop
  lands at a call or a loop turn. A worker compiling the program, or inside
  one long builtin, sees no stop point until it finishes that, and is killed
  when the grace period ends.
- **A receipt when eval itself is killed.** If the `velaris eval` process is
  killed outright, the file is not written. A URL has received `started` and
  the events streamed until then, and no `receipt`: its absence is the
  record.
- **More than a receipt says.** Everything
  [THREAT_MODEL.md](../THREAT_MODEL.md) says about receipts holds: no value
  the program handled is in one, and what the program controls that is not a
  value - its exit status, where it stopped, its counts, its time - is. A
  signed receipt is as strong as the machine that made it.
- **Isolation from the operator's machine.** The worker runs as the user who
  started eval, with that user's files readable to it. Put eval inside a
  container or a separate account when the stakes warrant it.

## Exit status

The program's own exit status when it ran and its receipt was delivered;
124 when the time limit stopped it; 2 when eval refused the command line; 3
when the program ran and the receipt could not be written or sent.
`--json` prints `velaris.eval/1` (provisional): the outcome, the code, the
confinement level with its layers and reason, whether signals could be taken, the stop, whether the receipt
was delivered, and the program's output and logs.
