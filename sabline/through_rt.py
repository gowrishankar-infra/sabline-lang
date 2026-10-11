"""A run through sabline-rt (9.0, M3): every run a command or the library
makes, when `SABLINE_REFERENCE_RUNTIME` is `rust` - `sabline run`,
`sabline.run` with limits and without, a Pool and a PoolRegistry (and so
the HTTP door and the MCP server, whose runs are a registry's), `sabline
replay` and `sabline test`.

decisions/0002: the commands stay in Python and the run inside them goes
through sabline-rt. Here that is literal. The command line still reads its
flags, builds the budget, and loads, checks and proves the program - the
prover stays in this package for good, and what it finds is what decides
whether a program runs - and then, instead of interpreting it, asks
`sabline-rt exec` to run it (rt/crates/sabline-rt/src/exec.rs says how the
two talk). What the program prints is written through this process's own
`sys.stdout`, what it logs through `sys.stderr`, and what it reads comes
from `sys.stdin` - or from the library's `stdin=` - so a run writes and
reads exactly what the same run in this package does. The receipt is
sabline-rt's, and says so: its producer is `sabline-rt`.

**A run with a timeout or a memory cap**, and every run on a pool, is
checked and proved by the pool's worker, under the pool's limits, as it
always was; but that worker is confined at its start (8.4) and cannot
start a process, so it says whether sabline-rt may run the program and
the pool's own process starts sabline-rt - under the cap, and killed at
what is left of the deadline (`run`'s `timeout` and `max_memory_mb`).
A run a limit stopped has no receipt of its own, so its audit stream is
always asked for, and the pool makes one of what it says the run did
(sabline/pool.py), named sabline-rt's.

**What chooses it.** The variable MAINTENANCE.md reserved for 9.0, read
when a run starts: `rust` routes the run through sabline-rt, unset or
`python` leaves it to this package, as before, and anything else is
refused rather than guessed at. M7 is where its default flips and the call
moves from the binary to the C ABI; until then it is opt-in, and the
agreement gate reads nothing of it - the gate runs both runtimes whatever
it says (check_gate.py sets it both ways).

**What sabline-rt does not do yet**, and so what a run through it is not:

- *The network, Python and tools.* A run whose budget grants one of them
  to a program that can reach it - a function of the program uses it -
  is this package's, as it always was, and says so on the error channel
  (decided on 2026-10-11: it is not refused, and not started in sabline-rt
  to stop at the first call it cannot make). So is a run under the eval
  profile, which holds a run to the operating system's confinement, and
  `sabline trace`, which shows this package's interpreter at work (KEPT).
  Each run says who answered it in the file SABLINE_THROUGH_RT_LOG names,
  when it names one (`note`), which is how suites_through_rt.py counts
  them.
- *Confinement* (M4). Nothing is asked of the operating system, and the
  receipt's confinement says `none`, with the reason "nothing was asked of
  the operating system". Nothing else says so (decided on 2026-10-11):
  whoever set the variable chose a runtime that does not confine yet, and
  the receipt is the record. A run on a pool made with confine=True is not
  confined either: its worker is, and the worker runs nothing.
- *Native code.* A run through sabline-rt is interpreted; what it does is
  the same, which is what `fuzz_native.py` holds.
"""
import json
import os
import shutil
import subprocess
from typing import Any, Callable

from .version import _INSTALL_DIR

# Named `*_ENV`, as every variable sabline/*.py reads is, so that
# check_self_budget.py's scan of what the package reads finds it (and varies
# it: neither may widen what a program can do).
RUNTIME_ENV = "SABLINE_REFERENCE_RUNTIME"
VARIABLE = RUNTIME_ENV
RUNTIMES = ("python", "rust")

# The effects whose work sabline-rt does not do yet, as a run's notice
# names them.
NOT_PORTED = (("net", "the network"), ("ffi", "Python"), ("tool", "a tool"))


class RuntimeChoiceError(ValueError):
    """SABLINE_REFERENCE_RUNTIME names no runtime."""


def chosen() -> str:
    """The runtime a run goes to: "python" or "rust". A value that is
    neither is refused - a typo that silently meant `python` would be a
    run in the runtime its user said not to use."""
    said = os.environ.get(RUNTIME_ENV, "").strip()
    if said in ("", "python"):
        return "python"
    if said == "rust":
        return "rust"
    raise RuntimeChoiceError(f"{VARIABLE} is {said!r}; it takes one of "
                             f"{', '.join(RUNTIMES)}, or nothing for python")


def binary() -> str | None:
    """sabline-rt: this checkout's own build (release, then debug), so that
    a checkout runs the crate beside it; else one on PATH (`cargo install
    sabline-rt`)."""
    exe = "sabline-rt.exe" if os.name == "nt" else "sabline-rt"
    for profile in ("release", "debug"):
        candidate = os.path.join(_INSTALL_DIR, "rt", "target", profile, exe)
        if os.path.isfile(candidate):
            return candidate
    return shutil.which("sabline-rt")


def not_ported(funcs: list[Any], budget: Any) -> list[str]:
    """The effects whose work sabline-rt does not do that this run could
    reach: granted by the budget and used by a function of the program -
    none of the program's functions can call a builtin of an effect it does
    not declare (E300), so a run reaches no other."""
    used = set().union(*(set(f.effects) for f in funcs)) if funcs else set()
    return [e for e, _ in NOT_PORTED
            if e in used and e in getattr(budget, "effects", ())]


def fallback_notice(effects: list[str]) -> str:
    """What the command line says when a run that was to go through
    sabline-rt is this package's instead."""
    named = ", ".join(dict(NOT_PORTED)[e] for e in effects)
    return (f"sabline: this run is the Python package's, not sabline-rt's: "
            f"its budget grants {named}, which sabline-rt does not do yet "
            f"({VARIABLE}=rust)")


# Why a run that was to go through sabline-rt stays this package's, for each
# reason that is not an effect, as its notice says it - None where nothing
# runs at all, so that nothing was kept from sabline-rt: the checks or the
# prover refused the program, and the package reports that as it always has.
KEPT = (
    ("checks", None),
    ("source", "its source is not UTF-8 text, which sabline-rt does not take"),
    ("eval", "the eval profile holds a run to the operating system's "
             "confinement, which sabline-rt does not ask for before M4"),
    ("trace", "sabline trace shows the Python package's interpreter at work"),
)


def notice_for(why: str) -> str | None:
    """What a run kept in this package says on the error channel (decided
    on 2026-10-11: it runs, and says so), for the reason it was kept: an
    effect or effects, comma-separated, or a key of KEPT."""
    effects = [e for e in why.split(",") if e in dict(NOT_PORTED)]
    if effects:
        return fallback_notice(effects)
    said = dict(KEPT).get(why, why)
    if said is None:
        return None
    return (f"sabline: this run is the Python package's, not sabline-rt's: "
            f"{said} ({VARIABLE}=rust)")


# ---- what was asked of sabline-rt, counted (9.0, M3) ----------------------
#      SABLINE_THROUGH_RT_LOG names a file; every run that was to go through
#      sabline-rt appends one line to it saying who answered - sabline-rt, or
#      this package and why - so a suite asked through sabline-rt can say how
#      much of it sabline-rt answered (suites_through_rt.py). Nothing else
#      reads it, and nothing is written without it.

LOG_ENV = "SABLINE_THROUGH_RT_LOG"
LOG_VARIABLE = LOG_ENV


def note(entry: str, answered_by: str, why: str | None = None) -> None:
    """One run's line in the log: `entry` is where it was asked (`cli`,
    `library`, `pool`, `replay`, `test`, ...), `answered_by` `sabline-rt`
    or `package`, and `why` the reason it stayed in the package - an
    effect's name, `checks`, or what sabline-rt does not do yet."""
    where = os.environ.get(LOG_ENV)
    if not where:
        return
    line = json.dumps({"run": entry, "answered_by": answered_by,
                       "why": why}) + "\n"
    try:
        with open(where, "a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass                       # the count is a measurement, not the run


class Unavailable(RuntimeError):
    """sabline-rt cannot be found or cannot be started, or ended without
    finishing a run when no limit stopped it."""


# The stack sabline-rt's run is on (rt/.../lib.rs, PARSE_STACK, 128 MiB),
# which check_through_rt.py holds to the crate's number. On Linux a run's cap
# is RLIMIT_DATA, not the RLIMIT_AS a Python worker sets on itself: an idle
# `sabline-rt exec` already maps 72 MB of address space, nearly all of it a
# malloc arena glibc reserves and never touches, which RLIMIT_DATA does not
# count. What it does count of sabline-rt before a program makes anything is
# this stack - mapped writable whole, though a program touches it only as
# deep as it recurses - and its input thread's, 2.4 MB in all on the machine
# that measured it. So a run capped at N MB is given N MB on top of
# RESERVED_MB; without it a cap under 130 MB would leave no room to start a
# run at all. A Windows job counts committed memory, which a reserved stack
# is not, and is given N.
RUN_STACK_MB = 128
RESERVED_MB = RUN_STACK_MB + 8

# How a Rust process says an allocation failed (std's alloc error handler),
# before it aborts: what a run the memory cap stopped writes on stderr.
OUT_OF_MEMORY_SIGN = b"memory allocation of "


class Ended:
    """How a run through sabline-rt ended. `document` and `receipt` when it
    finished; otherwise `timed_out` or `out_of_memory` says which limit
    stopped it, and `events` holds the audit stream it sent before it was
    stopped - what a receipt can still be made from. `seconds` is how long
    it ran, from the moment it was started."""

    __slots__ = ("document", "receipt", "timed_out", "out_of_memory",
                 "events", "seconds")

    def __init__(self, document: Any, receipt: Any, timed_out: bool,
                 out_of_memory: bool, events: list[dict[str, Any]],
                 seconds: float) -> None:
        self.document, self.receipt = document, receipt
        self.timed_out, self.out_of_memory = timed_out, out_of_memory
        self.events, self.seconds = events, seconds

    @property
    def finished(self) -> bool:
        return self.document is not None


def _start(cmd: list[str], max_memory_mb: int | None,
           cwd: str | None) -> tuple[Any, Any]:
    """sabline-rt, started under the memory cap: (the process, the Windows
    job to close once it has finished, or None). `sabline-rt exec` reads
    nothing of a program before its request arrives, so a cap put on it
    before the request is sent holds the whole run - on Windows the job
    object a pool worker gets, made before the process runs a single
    instruction; on Linux RLIMIT_DATA, set from here with prlimit (above,
    RESERVED_MB says why not RLIMIT_AS). Where neither can be had - prlimit
    is Linux's, and macOS does not reliably honour either limit - the cap is
    not enforced, which is what `sabline.memory_cap_is_enforced()` says of
    that machine."""
    pipes: dict[str, Any] = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE,
             "stderr": subprocess.PIPE, "cwd": cwd}
    if max_memory_mb is None:
        return subprocess.Popen(cmd, **pipes), None
    if os.name == "nt":
        from .library import _spawn_capped
        proc, job, _how = _spawn_capped(cmd, max_memory_mb, **pipes)
        return proc, job
    proc = subprocess.Popen(cmd, **pipes)
    try:
        import resource
        prlimit = resource.prlimit   # Linux
    except (ImportError, AttributeError):
        return proc, None            # not enforced, as a worker's would not be
    try:
        # an address-space cap this process holds itself to (`sabline f.vel
        # --max-memory-mb`) is not the run's: the run's is the one below
        soft, hard = prlimit(proc.pid, resource.RLIMIT_AS)
        if soft != hard:
            prlimit(proc.pid, resource.RLIMIT_AS, (hard, hard))
    except (OSError, ValueError):
        pass
    try:
        cap = (int(max_memory_mb) + RESERVED_MB) * 1024 * 1024
        prlimit(proc.pid, resource.RLIMIT_DATA, (cap, cap))
    except (OSError, ValueError):
        pass
    return proc, None


def run(path: str, *, allow: str | None, seed: Any = None,
        freeze_time: Any = None, max_read: int | None = None,
        args: list[str] | None = None, name: str | None = None,
        source: str | None = None, import_root: str | None = None,
        out: Callable[[str], Any], err: Callable[[str], Any],
        read_line: Callable[[], str], ask: Callable[[str], str | None],
        event: Callable[[dict[str, Any]], Any] | None = None,
        cwd: str | None = None, timeout: float | None = None,
        max_memory_mb: int | None = None, keep_events: bool = False,
        test: Callable[[dict[str, Any]], Any] | None = None) -> Ended:
    """Run the program at `path` through `sabline-rt exec`. As it runs,
    `out` and `err` are handed what it writes, `read_line` and `ask` answer
    what it asks - `ask` with None for the end of the input - and `event`,
    when given, each event of its audit stream. `allow` is the budget as
    the command line writes it (`Budget.spec()`), so sabline-rt parses the
    budget this package did; `source`, when given, is the program's text,
    where the file at `path` is only where its imports resolve from;
    `import_root` the directory its imports must stay inside (E515).

    `timeout` (seconds) and `max_memory_mb` are the limits a pool's worker
    has (8.1, 3.1), held from here because a confined worker cannot start a
    process: this process starts sabline-rt under the cap and kills it at
    the deadline, as a pool kills its worker. A run either stopped has no
    receipt of its own; `keep_events` - and either limit - asks for its
    audit stream whether or not `event` wants it, so that one can be made
    from what it did before it was stopped. Unavailable when sabline-rt
    cannot be started, or ends without finishing for any other reason.

    `test`, when given, makes it `sabline test`'s run (9.0, M3): each test
    function of the program called in turn rather than `main`, `test`
    handed how each ended as it ends, and the Ended's `document` how the
    tests ended (rt/.../run_dump.rs, `test_relayed`)."""
    import threading
    import time
    exe = binary()
    if exe is None:
        raise Unavailable(f"{VARIABLE}=rust, and sabline-rt is neither built "
                          f"in this checkout nor on PATH (cargo install "
                          f"sabline-rt)")
    bounded = timeout is not None or max_memory_mb is not None
    events: list[dict[str, Any]] = []
    keep = keep_events or bounded
    request = {"path": path, "allow": allow, "seed": seed,
               "freeze_time": freeze_time, "max_read": max_read,
               "args": list(args or []), "name": name, "source": source,
               "import_root": import_root, "tests": test is not None,
               "stream": event is not None or keep}
    began = time.monotonic()
    try:
        proc, job = _start([exe, "exec", "--install-dir", _INSTALL_DIR],
                           max_memory_mb, cwd)
    except OSError as e:
        raise Unavailable(f"sabline-rt ({exe}) cannot be started: "
                          f"{e.strerror or e}") from None
    assert proc.stdin is not None and proc.stdout is not None
    stopped = {"clock": False}
    lock = threading.Lock()

    def kill() -> None:
        if job is not None:
            job.close()              # kills whatever is in the job
        try:
            proc.kill()
        except OSError:
            pass

    def deadline() -> None:
        # this process owns the deadline, as a pool owns its worker's: the
        # run is killed, not asked to stop
        with lock:
            if proc.poll() is not None:
                return
            stopped["clock"] = True
        kill()

    alarm = None
    if timeout is not None:
        alarm = threading.Timer(max(float(timeout), 0.0), deadline)
        alarm.daemon = True
        alarm.start()

    def say(doc: dict[str, Any]) -> None:
        assert proc.stdin is not None
        proc.stdin.write(json.dumps(doc).encode("ascii") + b"\n")
        proc.stdin.flush()

    end = None
    try:
        try:
            say(request)
            for raw in proc.stdout:
                try:
                    frame = json.loads(raw)
                except ValueError:       # a line cut short by the kill
                    break
                if "out" in frame:
                    out(frame["out"])
                elif "err" in frame:
                    err(frame["err"])
                elif "read" in frame:
                    say({"line": read_line()})
                elif "ask" in frame:
                    say({"line": ask(frame["ask"])})
                elif "event" in frame:
                    if keep:
                        events.append(frame["event"])
                    if event is not None:
                        event(frame["event"])
                elif "test" in frame:
                    if test is not None:
                        test(frame["test"])
                elif "end" in frame:
                    end = frame["end"]
                    break
        except OSError:                 # its input closed: it was stopped
            pass
    finally:
        if alarm is not None:
            alarm.cancel()
        try:
            proc.stdin.close()
        except OSError:
            pass
        if end is None:            # we are leaving early: so is the run
            kill()
        proc.wait()
        if job is not None:
            job.close()
        said = proc.stderr.read() if proc.stderr else b""
        if proc.stderr:
            proc.stderr.close()
        proc.stdout.close()
    seconds = time.monotonic() - began
    if end is not None:
        return Ended(end.get("document", end.get("tests")),
                     end.get("receipt"), False, False, events, seconds)
    if stopped["clock"] and timeout is not None:
        return Ended(None, None, True, False, events, seconds)
    if max_memory_mb is not None and OUT_OF_MEMORY_SIGN in said:
        return Ended(None, None, False, True, events, seconds)
    raise Unavailable(f"sabline-rt ended without finishing the run "
                      f"(status {proc.returncode}): "
                      f"{said.decode('utf-8', 'replace')[-2000:]}")
