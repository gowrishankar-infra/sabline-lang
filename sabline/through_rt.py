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

**The network, Python and tools** are relayed (decided on 2026-10-11):
sabline-rt spends a call's effect, as it spends every builtin's, and then
asks the process that started it to make the call, over the channel its
output, input and audit events already use - a `call` frame, answered by
one line. That process is the host (`answer`): it makes the call with this
package's own code for it - runtime.outside_builtin, which is urllib with
its redirects and its proxy refusal (E317), the granted module with every
attribute it reaches checked (E311), the tool session - under the run's
budget, and says how it ended and what it recorded while it did: each
grant's event, each refusal and tool call the receipt keeps, what each
grant let through, and the tool session's ceiling. So what a call does is
the same in both runtimes by construction, and the receipt and the audit
stream are sabline-rt's, with what the host recorded in them in the order
it happened. The host is the caller's own process for an unbounded run and
for the command line; for a run on a pool it is the worker that checked
the program - confined, capped, the process that would have run it
(sabline/pool.py) - so a granted module's code runs where it always did.
Porting the network into Rust is M4's and M5's, not M3's (plan/9.0.md).

**What stays this package's**, and says so on the error channel (KEPT):
`sabline trace`, which shows this package's interpreter at work. A run
under the **eval profile** was here until 9.0's M4, when sabline-rt began
to confine its own runs and to honour a stop file: the profile's own
refusals are still this package's and are made before anything is sent
anywhere, and the run itself goes through sabline-rt like any pool's. `--confine strict` and `--require-confinement` were here until 9.0's
M4, when sabline-rt began to confine its own runs: they are now carried in
the request, applied by sabline-rt to its own process before the first
statement, and answered there (E326). Each run says who answered it in the file SABLINE_THROUGH_RT_LOG
names, when it names one (`note`), which is how suites_through_rt.py counts
them.

**What a run through sabline-rt is not:**

- *The network, Python and a tool under confinement* (M4, item 7). Those
  three calls are made in the process that started sabline-rt, so what
  bounds them is what confines **that** process - a pool's worker, which is
  confined, or a command line's own process, which is not. The request says
  which (`host_confinement`), and sabline-rt's level says so rather than
  claiming a boundary around work outside it.
- *Native code.* A run through sabline-rt is interpreted; what it does is
  the same, which is what `fuzz_native.py` holds.
"""
import json
import os
import shutil
import subprocess
from typing import Any, Callable

from . import ceiling as _ceiling
from . import state as _state
from .version import _INSTALL_DIR

# Named `*_ENV`, as every variable sabline/*.py reads is, so that
# check_self_budget.py's scan of what the package reads finds it (and varies
# it: neither may widen what a program can do).
RUNTIME_ENV = "SABLINE_REFERENCE_RUNTIME"
VARIABLE = RUNTIME_ENV
RUNTIMES = ("python", "rust")


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


# Why a run that was to go through sabline-rt stays this package's, for each
# reason that is not an effect, as its notice says it - None where nothing
# runs at all, so that nothing was kept from sabline-rt: the checks or the
# prover refused the program, or an organisation ceiling refused its budget,
# and the package reports that as it always has.
KEPT = (
    ("checks", None),
    ("ceiling", None),
    ("source", "its source is not UTF-8 text, which sabline-rt does not take"),
    ("trace", "sabline trace shows the Python package's interpreter at work"),
)


def notice_for(why: str) -> str | None:
    """What a run kept in this package says on the error channel (decided
    on 2026-10-11: it runs, and says so), for the reason it was kept: a key
    of KEPT."""
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
    or `package`, and `why` the reason it stayed in the package - `checks`,
    or a key of KEPT."""
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


# ---- the host: the calls sabline-rt relays (9.0, M3) -----------------------
#      decided on 2026-10-11: sabline-rt does the network, Python and tools by
#      relaying each call to the process that started it, so that what a
#      call does is this package's code whichever runtime runs the program.

class HostGone(RuntimeError):
    """The process a call was relayed to - a pool's worker - went away
    before it answered: the deadline, the memory cap, or a fault. Its one
    argument is what that process said instead, {} for nothing."""


def _value_in(v: Any) -> Any:
    """A value a `call` frame carries, as the package's runtime holds it:
    itself, or a HandleValue for `{"handle": id, "what": name}`."""
    from .values import HandleValue
    if isinstance(v, dict):
        return HandleValue(int(v["handle"]), str(v["what"]))
    if isinstance(v, list):
        return [_value_in(x) for x in v]
    return v


def _value_out(v: Any) -> Any:
    """What a call gave back, as the answer carries it: itself, a handle as
    `{"handle": id, "what": name}`, and a map - which only a recorded
    response `sabline replay` hands back can be - as `{"dict": [[k, v]]}`.
    TypeError for anything else, which the answer says was raised."""
    from .values import HandleValue
    if isinstance(v, HandleValue):
        return {"handle": v.id, "what": v.what}
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, list):
        return [_value_out(x) for x in v]
    if isinstance(v, dict):
        return {"dict": [[_value_out(k), _value_out(x)] for k, x in v.items()]}
    raise TypeError(f"{type(v).__name__} is not a value a run holds")


class _HostRecorder:
    """The recorder a relayed call is made under: what the package's own
    recorder would be told while the call is made - a grant's event, a
    refusal, a tool call - kept in order for the answer, which sabline-rt
    records in its own receipt and audit stream. A grant is told whether or
    not the run's stream was asked for: sabline-rt's recorder knows."""

    # not None: budget._grant_used tells a grant only to a recorder with a
    # stream
    stream = True

    def __init__(self) -> None:
        self.did: list[dict[str, Any]] = []

    def grant(self, grant: str) -> None:
        self.did.append({"grant": grant})

    def note(self, kind: str, **fields: Any) -> None:
        self.did.append({"note": dict(fields, kind=kind)})

    def effect(self, effect: str, builtin: str, line: int) -> None:
        pass                              # sabline-rt spent it, and told it

    def tell(self, event: dict[str, Any]) -> None:
        pass


TOOL_CALLS = ("tool", "tool_secret")


def answer(call: dict[str, Any]) -> dict[str, Any]:
    """The answer to one `call` frame, made in this process under the run's
    budget, which the caller has installed - the command line's, a
    library run's own (library._hosting), a pool worker's: the builtin's
    work, runtime.outside_builtin, as this package's own runtime makes it
    once the effect is spent, and how it ended - `value`, `fail` (a failure
    the program can handle), `error` (a coded error, which stops the run),
    `exit` (a granted module's SystemExit) or `raised` (an exception that
    escaped it, a defect) - with `did`, what it recorded in order, `counted`,
    what each grant let through, and after a tool call the session's
    `tool_ceiling`. MemoryError is not an answer: it is this process's."""
    from .errors import SablineError
    from .runtime import outside_builtin
    from .values import FailSignal
    name, line = str(call.get("name")), int(call.get("line") or 0)
    recorder = _HostRecorder()
    g = vars(_state)
    saved = g["RUN_RECORDER"]
    before = dict(_state.GRANT_USES)
    g["RUN_RECORDER"] = recorder
    said: dict[str, Any]
    try:
        try:
            args = [_value_in(a) for a in call.get("args") or []]
            said = {"value": _value_out(outside_builtin(name, args, line))}
        except FailSignal as e:
            reason = e.reason
            said = {"fail": reason if isinstance(reason, str) else str(reason)}
        except SablineError as e:
            said = {"error": {"code": e.code, "message": e.message,
                              "line": e.line or 0, "fixes": list(e.fixes or []),
                              "file": e.file}}
        except SystemExit as e:
            said = {"exit": e.code if isinstance(e.code, int)
                    else (0 if e.code is None else 1)}
        except MemoryError:
            raise
        except Exception as e:             # a defect, as the package's run
            said = {"raised": type(e).__name__}    # would show it
    finally:
        g["RUN_RECORDER"] = saved
    said["did"] = recorder.did
    said["counted"] = {grant: n - before.get(grant, 0)
                       for grant, n in _state.GRANT_USES.items()
                       if n != before.get(grant, 0)}
    if name in TOOL_CALLS and _state.TOOL_SESSION is not None:
        said["tool_ceiling"] = _state.TOOL_SESSION.ceiling_record()
    return said


def tool_ceiling() -> dict[str, Any] | None:
    """The ceiling record of this process's tool session, which a request
    hands sabline-rt so that its receipt lists the tool calls - or None."""
    session = _state.TOOL_SESSION
    return None if session is None else session.ceiling_record()


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
                 "events", "seconds", "host_gone")

    def __init__(self, document: Any, receipt: Any, timed_out: bool,
                 out_of_memory: bool, events: list[dict[str, Any]],
                 seconds: float, host_gone: dict[str, Any] | None = None
                 ) -> None:
        self.document, self.receipt = document, receipt
        self.timed_out, self.out_of_memory = timed_out, out_of_memory
        self.events, self.seconds = events, seconds
        # what the process a call was relayed to said when it went away
        # before it answered, {} for nothing; None when it did not
        self.host_gone = host_gone

    @property
    def finished(self) -> bool:
        return self.document is not None


def _start(cmd: list[str], max_memory_mb: int | None,
           cwd: str | None, own_group: bool = False) -> tuple[Any, Any]:
    """sabline-rt, started under the memory cap: (the process, the Windows
    job to close once it has finished, or None). `sabline-rt exec` reads
    nothing of a program before its request arrives, so a cap put on it
    before the request is sent holds the whole run - on Windows the job
    object a pool worker gets, made before the process runs a single
    instruction; on Linux RLIMIT_DATA, set from here with prlimit (above,
    RESERVED_MB says why not RLIMIT_AS). Where neither can be had - prlimit
    is Linux's, and macOS does not reliably honour either limit - the cap is
    not enforced, which is what `sabline.memory_cap_is_enforced()` says of
    that machine.

    `own_group` puts the run in a process group of its own, so a console
    break meant for whoever started it does not kill it: a run with a stop
    file is asked to stop by that file and by nothing else (9.0, M4,
    `sabline eval`), and its receipt is complete because it stopped rather
    than died."""
    pipes: dict[str, Any] = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE,
             "stderr": subprocess.PIPE, "cwd": cwd}
    if own_group:
        if os.name == "nt":
            pipes["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]  # Windows only
        else:
            pipes["start_new_session"] = True
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
        confine: Any = None,
        freeze_time: Any = None, max_read: int | None = None,
        args: list[str] | None = None, name: str | None = None,
        source: str | None = None, import_root: str | None = None,
        out: Callable[[str], Any], err: Callable[[str], Any],
        read_line: Callable[[], str], ask: Callable[[str], str | None],
        event: Callable[[dict[str, Any]], Any] | None = None,
        cwd: str | None = None, timeout: float | None = None,
        max_memory_mb: int | None = None, keep_events: bool = False,
        test: Callable[[dict[str, Any]], Any] | None = None,
        call: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        on_kill: Callable[[], Any] | None = None,
        stop_file: str | None = None,
        dump: dict[str, Any] | None = None) -> Ended:
    """Run the program at `path` through `sabline-rt exec`. As it runs,
    `out` and `err` are handed what it writes, `read_line` and `ask` answer
    what it asks - `ask` with None for the end of the input - and `event`,
    when given, each event of its audit stream. `allow` is the budget as
    the command line writes it (`Budget.spec()`), so sabline-rt parses the
    budget this package did; `source`, when given, is the program's text,
    where the file at `path` is only where its imports resolve from;
    `import_root` the directory its imports must stay inside (E515);
    `stop_file` the file whose appearance stops the run with E615 at the
    next call or loop turn, which `sabline eval` gives - from the pool
    rather than this process's state, since the pool is what holds it -
    and nothing else does (9.0, M4).

    `timeout` (seconds) and `max_memory_mb` are the limits a pool's worker
    has (8.1, 3.1), held from here because a confined worker cannot start a
    process: this process starts sabline-rt under the cap and kills it at
    the deadline, as a pool kills its worker. A run either stopped has no
    receipt of its own; `keep_events` - and either limit - asks for its
    audit stream whether or not `event` wants it, so that one can be made
    from what it did before it was stopped. Unavailable when sabline-rt
    cannot be started, or ends without finishing for any other reason.

    `confine`, when given, is what this run asked of the operating system
    (`confine.asked_of_runtime`, 9.0, M4): sabline-rt applies it to its own
    process before the program's first statement and records what it got.
    Left out, nothing is asked of the system and the receipt says so. A
    callable is called once sabline-rt has been started and before the
    request is written, and answers the same thing: that is where a command
    confines **itself** (`confine.confine_the_host`), since it is this
    process that makes a relayed call and the policy lets no process be
    started once it is applied.

    `test`, when given, makes it `sabline test`'s run (9.0, M3): each test
    function of the program called in turn rather than `main`, `test`
    handed how each ended as it ends, and the Ended's `document` how the
    tests ended (rt/.../run_dump.rs, `test_relayed`).

    `call` answers each builtin of the network, Python or a tool the run
    relays (`answer`, in this process, unless a pool hands its worker's);
    HostGone from it ends the run, as the Ended's `host_gone`. `on_kill` is
    called when the deadline kills the run, so that a host still making a
    call for it is stopped too. `dump`, a line of the gate's list, makes it
    the gate's hosted run document (rt/.../run_dump.rs, `run_hosted`): the
    Ended's `document` is then the three records, as canonical text."""
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
               "stream": event is not None or keep,
               "tool_ceiling": tool_ceiling(),
               # the organisation ceilings (9.0), whose text sabline-rt reads
               # as the package does, holds the budget to, and names in its
               # receipt - the package has held the run to them already
               "ceilings": _ceiling.for_request(_ceiling.installed()),
               # sabline eval's stop file (9.0, M4), which nothing else
               # sets: the run looks for it every 256 calls and loop turns
               # and stops there with E615, as this package's run does
               "stop_file": stop_file if stop_file is not None
               else _state.STOP_FILE}
    if dump is not None:
        request.update(dump, dump=True)
    host = call if call is not None else answer
    began = time.monotonic()
    try:
        proc, job = _start([exe, "exec", "--install-dir", _INSTALL_DIR],
                           max_memory_mb, cwd,
                           own_group=request["stop_file"] is not None)
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
        if on_kill is not None:
            on_kill()

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
    gone: dict[str, Any] | None = None
    try:
        try:
            # what this run asked of the operating system (9.0, M4):
            # sabline-rt applies it to its own process before the first
            # statement. Absent - which the gate's own runs leave it - means
            # nothing is asked of the system at all. A callable is called
            # here, with sabline-rt already started and inside the block
            # that kills it if anything goes wrong, so that a command can
            # confine itself and say what level it got.
            request.update((confine() if callable(confine) else confine) or {})
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
                elif "call" in frame:
                    try:
                        answered = host(frame["call"])
                    except HostGone as e:
                        last = e.args[0] if e.args else {}
                        gone = last if isinstance(last, dict) else {}
                        break
                    say({"answer": answered})
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
        return Ended(end.get("document", end.get("tests",
                                                 end.get("records"))),
                     end.get("receipt"), False, False, events, seconds)
    if stopped["clock"] and timeout is not None:
        return Ended(None, None, True, False, events, seconds)
    if gone is not None:
        return Ended(None, None, False, False, events, seconds,
                     host_gone=gone)
    if max_memory_mb is not None and OUT_OF_MEMORY_SIGN in said:
        return Ended(None, None, False, True, events, seconds)
    raise Unavailable(f"sabline-rt ended without finishing the run "
                      f"(status {proc.returncode}): "
                      f"{said.decode('utf-8', 'replace')[-2000:]}")
