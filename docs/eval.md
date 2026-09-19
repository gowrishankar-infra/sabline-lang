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
- **Confinement where the operating system offers it, and the level named.**
  The worker is also held by what the OS offers without privileges:

  | Level | Where | What it refuses |
  |---|---|---|
  | `landlock-net` | Linux, Landlock ABI 4 or later | writing, removing or making a file outside the `fs:write` directories and the run's own temporary directory; starting a program; a TCP connection or listening socket |
  | `landlock` | Linux, Landlock ABI 1 to 3 | the same, except TCP |
  | `job-one-process` | Windows, where the job object can be made | starting any process beyond the ones the worker took to start: its own, and a launcher's where `python.exe` is one (a virtual environment's) |
  | `sandbox-exec` | macOS, when a trial of the profile starts Python | the network; forking; writing outside the `fs:write` directories and the run's temporary directory |
  | `none` | anywhere else | nothing: the budget is the only boundary |

  `velaris eval --confinement-probe` starts a worker confined as a run is,
  has it try a TCP connection, a write outside the granted directories and
  a process start, prints what was refused, and exits 1 if a refusal the
  level claims did not hold.
- **Nothing it runs reads the proof cache.** Velaris has kept no proofs
  between runs since 8.2, so there is no cache for `--no-cache` to turn off.

Anything else that would widen the profile is refused before the program is
read, with exit 2 and no receipt: `--no-check-ceiling`, `--check-timeout`,
`--check-memory-mb` and `--max-read` (the 64 MiB read ceiling stays), a flag
eval does not have, and a flag given twice. Words after `--` are the
program's `args()` and never eval's flags.

## What it does not guarantee

- **That the OS confinement is there.** The level is what was applied, not
  what was asked for: a kernel without Landlock, a job object that could not
  be made, or a sandbox profile that failed its trial is `none`, and the run
  goes ahead under the budget alone. Read `confinement` in the receipt, and
  refuse `none` in whatever consumes it if that matters to you.
- **Reads.** No level confines reading. The budget holds a program's reads;
  the worker itself reads Python's own files as it runs.
- **More than it lists.** `job-one-process` does not hold files or the
  network, and it counts the processes the worker was already using when it
  became ready rather than insisting on exactly one; `landlock` does not hold TCP, and no Landlock level holds UDP or
  a Unix socket. A write grant's directory is confined as the nearest
  directory that exists, so a grant naming a file not made yet lets the OS
  layer allow its siblings; the budget still refuses them.
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
confinement, whether signals could be taken, the stop, whether the receipt
was delivered, and the program's output and logs.
