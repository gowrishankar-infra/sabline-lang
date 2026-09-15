"""velaris.Pool: bounded runs without a new interpreter each time, and nothing
carried between programs.
"""
import atexit
import json
import os
import queue as _queue
import sys
import threading
import weakref
from typing import TYPE_CHECKING, Any

from . import state as _state
from .version import VERSION, _launch_command
from .recorder import _RunRecorder, _entry_name, _utc_now_ms
from .budget import Budget, BudgetError, set_run_params
from .results import AuditResult, CheckResult, Problem, RunResult, _problem_of
from .library import (
    _audit_here,
    _budget_from,
    _cap_this_process,
    _check_here,
    _out_of_memory,
    _run_in_process,
    _spawn_capped,
    _unfinished_audit,
)

if TYPE_CHECKING:
    from .receipts import _run_parameters, receipt_statement

# Used inside functions only, from modules after this one: velaris/__init__.py
# binds each here once every module is loaded.
__forward__ = {
    "_run_parameters": "receipts",
    "receipt_statement": "receipts",
}

# ---------------------------------------------------------------------------
# 15. THE POOL — bounded runs without a new interpreter every time
#
#     A run with a timeout or a memory cap starts a Python interpreter,
#     which costs about a tenth of a second before a line of Velaris is
#     read. An agent platform calling run() thousands of times an hour
#     pays that every time. A Pool keeps workers alive and hands each
#     program to an idle one.
#
#     Speed is why it exists; isolation is why it can be used. Every
#     rule in Pool's docstring is asserted in check_pool.py, because a
#     fast sandbox that leaks state between programs is worse than a
#     slow one.
# ---------------------------------------------------------------------------


# Every module-level container a running program can reach. The rest of
# the module-level containers in this file - KEYWORDS, BUILTINS,
# FALLIBLE_BUILTINS, TOKEN_SPEC and so on - are constants nothing writes
# to. check_pool.py walks this file and fails if a new mutable one
# appears that is named in neither list.
MUTABLE_GLOBALS = ("PROGRAM_ARGS", "EFFECT_BUDGET", "FFI_MODULES",
                   "FS_GRANTS", "NET_GRANTS", "OP_LIMITS", "OP_COUNTS",
                   "EFFECT_USES", "PY_OBJECTS", "PY_NEXT", "TRACE",
                   "_NATIVE_KEEPALIVE", "SEED", "FROZEN_TIME", "_RNG",
                   "RUN_RECORDER", "IMPORT_ROOT")


def program_state_baseline() -> dict[str, Any]:
    """What this process looked like before it ran anyone's program."""
    return {"cwd": os.getcwd(), "env": dict(os.environ),
            "recursion": sys.getrecursionlimit(),
            "import_root": _state.IMPORT_ROOT}


def reset_program_state(budget: "Budget | None" = None,
                        baseline: dict[Any, Any] | None = None) -> None:
    """Put every piece of module-level mutable state back to how a
    fresh process would find it.

    A pool worker runs one program after another in one process, so
    anything a program leaves behind here is state the next program
    could see. Exhaustively, as of 3.1, that is:

        PROGRAM_ARGS        what args() answers
        EFFECT_BUDGET       the effects granted
        FFI_MODULES         the Python modules granted
        FS_GRANTS           the directions and paths granted
        NET_GRANTS          the hosts and ports granted
        OP_LIMITS           the @N caps
        OP_COUNTS           how many fs and net operations have run
        EFFECT_USES         which effects the program has used (3.4)
        PY_OBJECTS          handles from py_new, closed by the program
                            or not
        PY_NEXT             the number the next handle would get
        TRACE               the tracer's switch, depth and call count
        _NATIVE_KEEPALIVE   the JIT engines, and the text arena each
                            engine owns

    Nothing about one program's proofs survives to reach the next: a
    proof is made when it is needed and kept nowhere (8.2).

    With a baseline, three things that are the process's rather than
    this module's are put back too, because a program granted ffi can
    change all three: the working directory, the environment, and
    Python's recursion limit (which the interpreter raises so that its
    own depth limit is the one that fires).

    Passing no budget grants nothing, which is the right answer for a
    reset outside a pool: the budget must be chosen deliberately, never
    inherited from whatever ran last.
    """
    _state.PROGRAM_ARGS[:] = []
    _state.PY_OBJECTS.clear()
    _state.PY_NEXT[0] = 1
    _state._NATIVE_KEEPALIVE.clear()
    _state.TRACE.update({"on": False, "depth": 0, "calls": 0, "limit": 4000})
    set_run_params(None, None)         # --seed / --freeze-time, per program
    vars(_state)["RUN_RECORDER"] = None   # a receipt is one program's (8.1)
    (budget if budget is not None else Budget()).install()
    if baseline is None:
        return
    # the root imports are held to is the pool's, like its budget: a program
    # granted ffi could reach this module and clear it for the next one
    vars(_state)["IMPORT_ROOT"] = baseline.get("import_root")
    try:
        if os.getcwd() != baseline["cwd"]:
            os.chdir(baseline["cwd"])
    except OSError:
        pass
    if dict(os.environ) != baseline["env"]:
        os.environ.clear()
        os.environ.update(baseline["env"])
    if sys.getrecursionlimit() != baseline["recursion"]:
        try:
            sys.setrecursionlimit(baseline["recursion"])
        except (ValueError, RecursionError):
            pass


# ---- the wire between a pool and its workers ------------------------------
#      Four bytes of length, then one JSON object. Length-prefixed and
#      not line-delimited, because a program's output is inside the
#      object and can hold anything at all.

def _msg_write(stream: Any, payload: dict[Any, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    stream.write(len(body).to_bytes(4, "little"))
    stream.write(body)
    stream.flush()


def _read_exactly(stream: Any, n: int) -> Any:
    parts = []
    while n > 0:
        try:
            chunk = stream.read(n)
        except (OSError, ValueError):
            return None
        if not chunk:
            return None                    # the other end went away
        parts.append(chunk)
        n -= len(chunk)
    return b"".join(parts)


def _msg_read(stream: Any) -> Any:
    """The next message, or None when the pipe closed or went wrong."""
    head = _read_exactly(stream, 4)
    if head is None:
        return None
    body = _read_exactly(stream, int.from_bytes(head, "little"))
    if body is None:
        return None
    try:
        answer = json.loads(body.decode("utf-8"))
    except ValueError:
        return None
    return answer if isinstance(answer, dict) else None


def pool_worker(argv: list[Any]) -> int:
    """One long-lived child behind velaris.Pool.

    It parses its budget once, from its own command line, installs it,
    and then serves one program at a time: read a request, run it,
    answer with exactly the dict run() returns. A request carries a
    program, its stdin and its arguments - never a budget. There is
    nowhere for a program to ask for more than the pool was made with.
    """
    spec = argv[argv.index("--allow") + 1] if "--allow" in argv else ""
    native = "--no-native" not in argv
    if "--max-memory-mb" in argv:
        # POSIX caps itself here; on Windows the parent put this process
        # in a job object before it was allowed to run at all
        _cap_this_process(argv[argv.index("--max-memory-mb") + 1])
    # a check or an audit asked of this worker is already under its
    # parent's deadline and this process's cap: do it here, not in a child
    vars(_state)["_IN_CHILD"] = True
    if "--import-root" in argv:
        vars(_state)["IMPORT_ROOT"] = argv[argv.index("--import-root") + 1]
    try:
        budget = Budget.parse(spec)
    except BudgetError as e:
        sys.stderr.write(f"velaris worker: {e}\n")
        return 2

    # The protocol gets private copies of fd 0 and fd 1, and the
    # program's own fd 0 and fd 1 are pointed at the null device.
    # Nothing a program writes - print, a hand-redirected stderr, or a
    # write straight at the file descriptor through ffi - can reach the
    # pipe the parent is parsing.
    requests = os.fdopen(os.dup(0), "rb")
    replies = os.fdopen(os.dup(1), "wb")
    null = os.open(os.devnull, os.O_RDWR)
    os.dup2(null, 0)
    os.dup2(null, 1)
    os.close(null)

    baseline = program_state_baseline()
    reset_program_state(budget, baseline)
    _msg_write(replies, {"ready": VERSION, "pid": os.getpid(),
                         "allow": budget.spec()})
    while True:
        request = _msg_read(requests)
        if request is None or request.get("stop"):
            return 0                       # the parent closed the pipe
        reset_program_state(budget, baseline)

        def emit(event: Any) -> None:
            _msg_write(replies, {"event": event})

        op = request.get("op") or "run"
        try:
            if op == "check":
                answer: dict[str, Any] = {"check": _check_here(
                    request.get("source") or "", path=request.get("path"),
                    prove=bool(request.get("prove", True))).as_dict()}
            elif op == "audit":
                answer = {"audit": _audit_here(
                    request.get("source") or "",
                    path=request.get("path")).as_dict()}
            else:
                answer = _run_in_process(
                    request.get("source") or "", path=request.get("path"),
                    budget=budget, args=request.get("args") or [],
                    stdin=request.get("stdin") or "",
                    seed=request.get("seed"),
                    freeze_time=request.get("freeze_time"),
                    native=native, emit=emit,
                    name=request.get("name")).as_dict()
        except MemoryError:
            answer = {"out_of_memory": True}
        except Exception as e:             # a defect in the compiler, not
            answer = {"crashed": f"{type(e).__name__}: {e}"}   # in the run
        reset_program_state(budget, baseline)
        try:
            _msg_write(replies, answer)
        except OSError:
            return 0                       # the parent stopped listening


class _Worker:
    """One child process, and the pipe its pool talks to it over."""

    def __init__(self, cmd: list[Any], max_memory_mb: Any) -> None:
        import subprocess
        self.killed_by_timeout = False
        self.dead = False
        self._kill_lock = threading.Lock()
        self._noise: list[Any] = []
        self.proc, self.job, self.cap = _spawn_capped(
            cmd, max_memory_mb, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.pid = self.proc.pid
        self._drain = threading.Thread(target=self._read_stderr, daemon=True)
        self._drain.start()
        hello = _msg_read(self.proc.stdout)
        if hello is None or not hello.get("ready"):
            self.dispose()
            raise RuntimeError("a pool worker did not start: "
                               + (self.stderr() or "it said nothing"))
        self.allow = hello.get("allow") or ""

    def _read_stderr(self) -> None:
        try:
            for line in self.proc.stderr:
                self._noise.append(line.decode("utf-8", "replace"))
                del self._noise[:-40]      # the last 40 lines are plenty
        except Exception:
            pass

    def stderr(self) -> str:
        return "".join(self._noise).strip()

    def ask(self, request: dict[Any, Any], timeout: Any) -> tuple[Any, ...]:
        """Send one request and wait: (answer, events). The answer is None
        when the worker did not give one - killed by the deadline, or dead
        for another reason. The events are what the worker streamed while
        it worked (what a receipt records), kept even when it was killed."""
        self.killed_by_timeout = False
        events: list[Any] = []
        alarm = None
        if timeout is not None:
            alarm = threading.Timer(timeout, self._deadline)
            alarm.daemon = True
            alarm.start()
        try:
            try:
                _msg_write(self.proc.stdin, request)
            except (OSError, ValueError):
                return None, events
            while True:
                message = _msg_read(self.proc.stdout)
                if message is None or "event" not in message:
                    return message, events
                if isinstance(message["event"], dict):
                    events.append(message["event"])
        finally:
            if alarm is not None:
                alarm.cancel()

    def _deadline(self) -> None:
        # the PARENT owns the deadline: a worker that has not answered
        # is killed, not asked to stop. A program that ignores its own
        # limits cannot ignore this one.
        self.killed_by_timeout = True
        self.kill()

    def kill(self) -> None:
        """Stop the child and reap it. Safe from any thread, and safe
        while another thread is still reading the child's answer - the
        pipes are closed by dispose(), once nobody is reading."""
        with self._kill_lock:
            if self.dead:
                return
            self.dead = True
        if self.job is not None:
            self.job.close()               # kills whatever is in the job
        try:
            self.proc.kill()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=10)
        except Exception:
            pass

    def dispose(self) -> None:
        self.kill()
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            try:
                stream.close()
            except Exception:
                pass
        try:
            self._drain.join(timeout=2)
        except Exception:
            pass


def _kill_workers(live: set[Any], lock: Any) -> None:
    """Every worker in `live`, stopped and forgotten. Used by close(),
    by the finalizer of a pool nobody closed, and at exit."""
    try:
        with lock:
            workers = list(live)
            live.clear()
    except Exception:                      # interpreter shutdown
        workers = list(live)
        live.clear()
    for worker in workers:
        try:
            worker.dispose()
        except Exception:
            pass


_POOLS: "weakref.WeakSet[Pool]" = weakref.WeakSet()


@atexit.register
def _close_pools_at_exit() -> None:
    for pool in list(_POOLS):
        try:
            pool.close()
        except Exception:
            pass


class Pool:
    """Long-lived workers for bounded runs, all under ONE budget.

        pool = velaris.Pool(size=4, allow={"io"}, timeout=30,
                            max_memory_mb=512)
        result = pool.run(source)          # the RunResult run() returns
        pool.close()                       # also a context manager

    A bounded run costs an interpreter's startup - about a tenth of a
    second - before a line of Velaris is read. A pool pays that once
    per worker instead of once per program.

    The isolation rules, which matter more than the speed:

    * THE BUDGET IS THE POOL'S, NOT THE PROGRAM'S. It is parsed once,
      here, and installed by each worker at startup; `run` on a pool
      takes no allow argument. allow=None is `io` from 5.0, as it is
      everywhere else, where it used to be all seven effects. A caller who needs a different budget
      makes a different pool. Nothing a program does can widen it: the
      budget is re-asserted from this object before every program,
      which also puts the per-run operation counts (@N) back to zero,
      so one program cannot spend another's allowance.

    * A WORKER IS USED ONCE UNLESS THE RUN WAS CLEAN. Anything other
      than ok - a refused effect, a failure that escaped, a program
      that did not compile, the timeout, the memory cap - retires the
      worker: it is killed and a fresh one takes its place. Only a run
      that finished cleanly hands its worker back. That costs a
      restart on every rejected program, and it is the rule that makes
      the rest of this list checkable.

    * A REUSED WORKER STARTS EMPTY. Before every program the child
      resets every piece of module-level mutable state there is: the
      arguments, the Python handles, the native compiler's engines and
      the text arena they own, the tracer, the budget and its counts -
      and the working directory, the environment and the recursion
      limit, which a program granted ffi can change.
      `reset_program_state` lists all of it.

    * THE PARENT OWNS THE DEADLINE. A worker that has not answered
      within `timeout` is killed by this process; the call returns
      E610 and a replacement is started. The memory cap is set in the
      child at startup, the same way a bounded `run` sets it.

    * CLOSING KILLS EVERY WORKER, including one still running a
      program. A pool collected without close() is closed by its
      finalizer; a pool that outlives the interpreter is closed at
      exit; and a worker whose pipe closes ends by itself, so a parent
      that dies without doing either still leaves nothing behind.

    `run` is safe to call from several threads: each call takes an idle
    worker and blocks while none is free.

    What a pool does NOT change: the effect budget is the same guard it
    is everywhere else in Velaris, and the same things sit outside it -
    a granted ffi module can do whatever that module can do, in a
    worker as anywhere. THREAT_MODEL.md is the long form.
    """

    _CLOSED = object()

    def __init__(self, size: int = 4, *, allow: set[str] | str | None = None,
                 deny: set[str] | None = None, timeout: float | None = None,
                 max_memory_mb: int | None = None, native: bool = True,
                 import_root: Any = None) -> None:
        if int(size) < 1:
            raise ValueError("a pool needs at least one worker")
        self.size = int(size)
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb
        self.native = native
        # the directory imports must stay inside (8.1), fixed like the
        # budget: every worker is started with it
        self.import_root = (None if import_root is None
                            else os.path.realpath(str(import_root)))
        self._budget = _budget_from(allow, deny)   # a bad grant fails here,
        self.allow = self._budget.spec()           # before any worker starts
        self._free: "_queue.Queue[Any]" = _queue.Queue()
        for _ in range(self.size):
            self._free.put(None)           # a worker starts on first demand
        self._live: set[Any] = set()
        self._lock = threading.Lock()
        self._closed = False
        self.started = 0                   # how many workers ever started
        _POOLS.add(self)
        self._finalizer = weakref.finalize(self, _kill_workers,
                                           self._live, self._lock)

    # ---- using it ----------------------------------------------------
    def run(self, source: str, *, stdin: str = "", args: list[Any] | None = None,
            path: str | None = None, seed: int | None = None,
            freeze_time: Any = None, _name: str | None = None) -> RunResult:
        """Run one program on this pool, under the pool's budget.

        The same RunResult `velaris.run` returns, including timed_out,
        out_of_memory and, from 8.1, the run's receipt. `seed` and
        `freeze_time` fix the run's randomness and clock (8.0); they are
        not grants.
        """
        started_at = _utc_now_ms()
        _run_parameters(seed, freeze_time, self.timeout,
                        self.max_memory_mb)       # a bad instant fails here
        answer, events, worker, seconds = self._use(
            {"op": "run", "source": source, "stdin": stdin or "",
             "args": list(args or []), "path": path, "seed": seed,
             "freeze_time": freeze_time, "name": _name},
            lambda a: bool(a) and bool(a.get("ok")))
        if answer is not None and "ok" in answer:
            result = RunResult(
                bool(answer.get("ok")), answer.get("output") or "",
                answer.get("logs") or "",
                [_problem_of(p) for p in answer.get("problems") or []],
                answer.get("refused_effect"), answer.get("exit_code") or 0,
                bool(answer.get("timed_out")),
                bool(answer.get("out_of_memory")),
                answer.get("effects_used"))
        else:
            result = self._no_answer(worker, answer, path)
        result.receipt = self._receipt(
            source, path, _name, seed, freeze_time, answer, events, result,
            started_at, seconds)
        return result

    def check(self, source: str, *, path: str | None = None,
              prove: bool = True) -> CheckResult:
        """check() on a worker of this pool (8.1): under the pool's timeout
        and memory cap, E613 or E614 when it passes one. A worker that
        answers is kept - nothing of the program ran in it."""
        answer, _events, worker, _s = self._use(
            {"op": "check", "source": source, "path": path,
             "prove": bool(prove)},
            lambda a: bool(a) and isinstance(a.get("check"), dict))
        got = (answer or {}).get("check")
        if isinstance(got, dict):
            return CheckResult(
                bool(got.get("ok")),
                [_problem_of(p) for p in got.get("problems") or []],
                list(got.get("proven") or []),
                list(got.get("runtime_checked") or []))
        return CheckResult(False, [self._stopped(worker, answer, path,
                                                 "check")], [], [])

    def audit(self, source: str, *, path: str | None = None) -> AuditResult:
        """audit() on a worker of this pool (8.1), under its limits."""
        answer, _events, worker, _s = self._use(
            {"op": "audit", "source": source, "path": path},
            lambda a: bool(a) and isinstance(a.get("audit"), dict))
        got = (answer or {}).get("audit")
        if isinstance(got, dict):
            fields = {k: got.get(k) for k in AuditResult.__slots__}
            fields["problems"] = [_problem_of(p)
                                  for p in got.get("problems") or []]
            return AuditResult(**fields)
        return _unfinished_audit(self._stopped(worker, answer, path,
                                               "audit"))

    def _use(self, request: dict[Any, Any], keep_if: Any) -> tuple[Any, ...]:
        """One request to an idle worker: (answer, events, the worker,
        seconds it took). The worker goes back to the pool only when
        keep_if(answer) says so; otherwise it is killed and replaced."""
        import time as _time
        if self._closed:
            raise RuntimeError("this pool is closed")
        slot = self._free.get()
        if slot is self._CLOSED:
            self._free.put(slot)           # leave it for the next waiter
            raise RuntimeError("this pool is closed")
        worker, keep = slot, False
        try:
            if self._closed:
                raise RuntimeError("this pool is closed")
            if worker is not None and worker.proc.poll() is not None:
                self._forget(worker)       # it died while it was idle
                worker = None
            if worker is None:
                worker = self._start()
            began = _time.monotonic()
            answer, events = worker.ask(request, self.timeout)
            seconds = _time.monotonic() - began
            keep = bool(keep_if(answer))
            return answer, events, worker, seconds
        finally:
            if worker is not None and not keep:
                try:
                    self._forget(worker)   # used once
                finally:
                    worker = None          # the slot comes back either
            self._free.put(worker)         # way, or the pool shrinks

    def close(self) -> None:
        """Kill every worker, including one still running a program."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._free.put(self._CLOSED)       # wake anyone waiting
        _kill_workers(self._live, self._lock)
        self._finalizer.detach()

    def __enter__(self) -> "Pool":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    @property
    def closed(self) -> bool:
        return self._closed

    def worker_pids(self) -> list[Any]:
        """The process ids of the workers alive right now."""
        with self._lock:
            return sorted(w.pid for w in self._live)

    # ---- the machinery -----------------------------------------------
    def _start(self) -> "_Worker":
        cmd = _launch_command() + ["--pool-worker",
                                   "--allow", self._budget.spec()]
        if not self.native:
            cmd.append("--no-native")
        if self.max_memory_mb is not None:
            cmd += ["--max-memory-mb", str(int(self.max_memory_mb))]
        if self.import_root is not None:
            cmd += ["--import-root", self.import_root]
        worker = _Worker(cmd, self.max_memory_mb)
        with self._lock:
            # close() may have run between the check in run() and here.
            # A worker added after close() drained the set would outlive
            # the pool, which is the one thing close() promises it will
            # not leave behind.
            too_late = self._closed
            if not too_late:
                self._live.add(worker)
                self.started += 1
        if too_late:
            worker.dispose()
            raise RuntimeError("this pool is closed")
        return worker

    def _forget(self, worker: Any) -> None:
        with self._lock:
            self._live.discard(worker)
        worker.dispose()

    def _starved(self, worker: Any, answer: Any) -> bool:
        """Did the worker run out of the memory this pool capped it at?"""
        if self.max_memory_mb is None:
            return False
        noise = worker.stderr()
        return (bool((answer or {}).get("out_of_memory"))
                or _out_of_memory(noise)
                or _out_of_memory((answer or {}).get("crashed") or "")
                or (not worker.killed_by_timeout
                    and worker.proc.returncode in (-9, 137)))

    def _no_answer(self, worker: Any, answer: Any, path: Any) -> RunResult:
        """The worker handed back no run. Say which limit or which
        fault it was, in the shape run() would have used."""
        where = path or "<source>"
        if worker.killed_by_timeout:
            return RunResult(False, "", "", [Problem(
                "E610", f"the program ran longer than {self.timeout} "
                        f"second(s) and was stopped", 0, where,
                ["give it more time, or fix the loop that never ends"])],
                None, 124, True, False)
        if self._starved(worker, answer):
            return RunResult(False, "", "", [Problem(
                "E611", f"the program used more than {self.max_memory_mb} "
                        f"MB and was stopped", 0, where,
                ["give it more memory, or find what is growing"])],
                None, 1, False, True)
        noise = worker.stderr()
        detail = (answer or {}).get("crashed") or (
            noise.splitlines()[-1][:200] if noise
            else "the worker stopped without answering")
        return RunResult(False, "", "", [Problem("E000", detail, 0, where,
                                                 [])], None, 1)

    def _stopped(self, worker: Any, answer: Any, path: Any, what: str) -> "Problem":
        """Why a check or an audit came back with no answer: the clock
        (E613), the memory cap (E614), or a fault (E000)."""
        where = path or "<source>"
        if worker.killed_by_timeout:
            return Problem(
                "E613", f"the {what} did not finish within {self.timeout:g} "
                        f"second(s) and was stopped; the source may be "
                        f"crafted to stall the checker", 0, where,
                ["raise the ceiling - timeout= in the library, "
                 "--check-timeout on the command line and the doors",
                 "or check it where a stall costs nothing"])
        if self._starved(worker, answer):
            return Problem(
                "E614", f"the {what} used more than {self.max_memory_mb} MB "
                        f"and was stopped; the source may be crafted to "
                        f"bloat the checker", 0, where,
                ["raise the cap - max_memory_mb= in the library, "
                 "--check-memory-mb on the command line and the doors"])
        noise = worker.stderr()
        detail = (answer or {}).get("crashed") or (
            noise.splitlines()[-1][:200] if noise
            else "the worker stopped without answering")
        return Problem("E000", detail, 0, where, [])

    def _receipt(self, source: Any, path: Any, name: Any, seed: Any, freeze_time: Any, answer: Any,
                 events: Any, result: Any, started_at: Any, seconds: Any) -> dict[Any, Any]:
        """The receipt of a run on this pool. The worker's own, when it
        answered, with the limits, the start and the wall time this process
        measured; otherwise one made here from what it streamed before it
        was stopped, marked incomplete."""
        parameters = _run_parameters(seed, freeze_time, self.timeout,
                                     self.max_memory_mb)
        doc = (answer or {}).get("receipt")
        if isinstance(doc, dict) and isinstance(doc.get("predicate"), dict):
            doc["predicate"]["run_parameters"] = parameters
            doc["predicate"]["startedAt"] = started_at
            doc["predicate"]["wall_time_ms"] = round(seconds * 1000, 1)
            return doc
        recorder = _RunRecorder()
        for event in events:
            recorder.take(event)
        return receipt_statement(
            recorder, name=_entry_name(path, name),
            entry_bytes=source.encode("utf-8", "surrogatepass"),
            budget=self.allow, parameters=parameters, result=result,
            started_at=started_at, wall_time_ms=seconds * 1000,
            complete=False)


class PoolRegistry:
    """One pool per distinct budget, made the first time it is asked for.

    A server takes a budget per request, so it cannot make its pools up
    front. This makes one the first time a budget is seen and keeps it
    for the next request that names the same budget - the same grants,
    timeout and memory cap. Budgets that differ never share a pool,
    because a pool's budget is the thing that makes its workers safe to
    reuse.

    At most `keep` pools are held; the least recently used beyond that
    is closed, so a caller who varies the budget on every request
    cannot make a server hold processes without end.

        pools = velaris.PoolRegistry()
        result = pools.run(source, allow={"io"}, timeout=30,
                           max_memory_mb=512)
        pools.close()
    """

    def __init__(self, size: int = 4, keep: int = 8) -> None:
        self.size, self.keep = int(size), max(1, int(keep))
        self._pools: dict[Any, Pool] = {}            # key -> Pool, least used first
        self._lock = threading.Lock()

    def pool(self, *, allow: Any = None, deny: Any = None, timeout: Any = None,
             max_memory_mb: Any = None, native: bool = True,
             import_root: Any = None) -> "Pool":
        # spec() rather than the caller's words: two spellings of one
        # budget are one budget, and a bad grant fails here as it would
        # in run(), before any worker starts
        key = (_budget_from(allow, deny).spec(), timeout, max_memory_mb,
               bool(native), import_root)
        stale = []
        with self._lock:
            found = self._pools.pop(key, None)
            if found is None or found.closed:
                found = Pool(self.size, allow=allow, deny=deny,
                             timeout=timeout, max_memory_mb=max_memory_mb,
                             native=native, import_root=import_root)
            self._pools[key] = found       # most recently used, last
            while len(self._pools) > self.keep:
                stale.append(self._pools.pop(next(iter(self._pools))))
        for old in stale:
            old.close()
        return found

    def run(self, source: str, *, allow: Any = None, deny: Any = None, timeout: Any = None,
            max_memory_mb: Any = None, native: bool = True, stdin: str = "",
            args: list[Any] | None = None, path: str | None = None,
            seed: int | None = None, freeze_time: Any = None,
            import_root: Any = None, _name: str | None = None) -> RunResult:
        return self.pool(allow=allow, deny=deny, timeout=timeout,
                         max_memory_mb=max_memory_mb, native=native,
                         import_root=import_root).run(
            source, stdin=stdin, args=args, path=path,
            seed=seed, freeze_time=freeze_time, _name=_name)

    def close(self) -> None:
        with self._lock:
            pools, self._pools = list(self._pools.values()), {}
        for pool in pools:
            pool.close()

    def __enter__(self) -> "PoolRegistry":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()
