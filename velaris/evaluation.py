"""velaris eval: one program run the way an evaluation sandbox runs code it
was handed (8.3).
"""
import json
import os
import signal
import sys
import tempfile
import threading
import time

from .version import VERSION
from .tables import ALL_EFFECTS, ALLOW_ALL
from .budget import Budget, BudgetError, _ascii_digits
from .results import Problem
from .pool import Pool, _Worker
from . import confine as _confine
from .receipts import _confinement_fields
from typing import Any

# ---------------------------------------------------------------------------
# 20b. EVAL - a profile, not a budget
#
#     `velaris eval program.vel --receipt FILE` runs one program under a
#     profile that cannot be relaxed from its command line: no net, no ffi,
#     no env; an fs grant only under a named path; a time and a memory limit
#     always, with a most for each; interpreted, so every call and loop turn
#     can see a stop; the worker confined where the operating system offers
#     it, and the level named; a receipt always, written where the budget
#     cannot reach or sent to a URL, recording a stop when one was asked for
#     and how it was honoured. Anything that would widen one of those is
#     refused before the program is read, exit 2. docs/eval.md says what the
#     profile guarantees and what it does not.
# ---------------------------------------------------------------------------

EVAL_SCHEMA = "velaris.eval/1"                       # provisional
RECEIPT_STREAM_SCHEMA = "velaris.receipt-stream/1"   # provisional
EVAL_TIMEOUT_DEFAULT = 30
EVAL_TIMEOUT_MOST = 600
EVAL_MEMORY_MB_DEFAULT = 512
EVAL_MEMORY_MB_MOST = 4096
EVAL_GRACE_DEFAULT = 5
EVAL_GRACE_MOST = 60
EVAL_STDIN_MOST = 16 * 1024 * 1024
EVAL_REFUSED_EFFECTS = ("net", "ffi", "env")
# flags other commands take that would relax the profile, and why each is
# refused here; any other flag velaris eval does not know is refused too
EVAL_REFUSED_FLAGS = (
    ("--no-check-ceiling", "the program is checked inside the run's worker, "
                           "under the run's own time and memory limits"),
    ("--check-timeout", "the program is checked inside the run's worker, "
                        "under the run's own time limit"),
    ("--check-memory-mb", "the program is checked inside the run's worker, "
                          "under the run's own memory limit"),
    ("--max-read", "the profile keeps the 64 MiB read ceiling"),
    ("--no-confine", "confinement is part of the profile and has no switch: "
                     "a run under it is held by the operating system, fully "
                     "or partly, or it does not start"),
    ("--no-receipt", "a run under the profile always has a receipt"),
)
_VALUED = ("--allow", "--deny", "--timeout", "--max-memory-mb", "--receipt",
           "--receipt-url", "--root", "--stop-file", "--grace", "--seed",
           "--freeze-time")
_SWITCHES = ("--json", "--confinement-probe")


class EvalRefused(Exception):
    """A command line that asks for less than the eval profile holds."""


def _number(flag: str, text: str, most: float, whole: bool = False) -> float:
    try:
        value = float(text) if not whole else float(int(text))
    except ValueError:
        raise EvalRefused(f"{flag} needs a number above zero, not {text!r}")
    if not (value > 0) or value != value or value > most:
        raise EvalRefused(f"{flag} must be above zero and at most {most:g} "
                          f"under the eval profile, not {text}")
    return value


def _inside(path: str, base: str) -> bool:
    try:
        return os.path.commonpath([path, base]) == base
    except ValueError:                    # another drive, on Windows
        return False


def eval_budget(allow: str, deny: str | None) -> Budget:
    """The budget a run under the profile gets, or EvalRefused: `all`, net,
    ffi and env are refused, and so is an fs grant that names no path."""
    words = [w.strip() for w in allow.split(",") if w.strip()]
    if ALLOW_ALL in words:
        raise EvalRefused(f"--allow {ALLOW_ALL} grants every effect; the eval "
                          f"profile grants no net, ffi or env")
    try:
        budget = Budget.parse(allow)
    except BudgetError as e:
        raise EvalRefused(str(e))
    if deny:
        names = [w.strip() for w in deny.split(",") if w.strip()]
        unknown = [n for n in names if n not in ALL_EFFECTS]
        if unknown:
            raise EvalRefused(f"--deny takes effect names; {unknown[0]!r} is "
                              f"not one")
        budget.deny(names)
    for effect in EVAL_REFUSED_EFFECTS:
        if effect in budget.effects:
            raise EvalRefused(f"the eval profile grants no {effect}; a run "
                              f"under it reaches no network, no Python module "
                              f"and no environment variable")
    if "fs" in budget.effects and (budget.fs is None or any(
            prefix is None for _kind, prefix in budget.fs)):
        raise EvalRefused("an fs grant under the eval profile names its path "
                          "(fs:read:DIR, fs:write:DIR), so the receipt can be "
                          "kept outside it")
    return budget


def _worker_env(tmp: str) -> dict[str, str]:
    env = dict(os.environ)
    for name in ("TMPDIR", "TEMP", "TMP"):
        env[name] = tmp
    return env


class _EvalPool(Pool):
    """A pool of one worker, held as the profile holds it: interpreted, told
    where its stop file is, and confined where the operating system offers
    it. `confinement` is the level the started worker got."""

    def __init__(self, *, allow: str, timeout: float, max_memory_mb: int,
                 import_root: str, stop_file: str, writable: list[str],
                 on_event: Any = None) -> None:
        super().__init__(size=1, allow=allow, timeout=timeout,
                         max_memory_mb=max_memory_mb, native=False,
                         import_root=import_root)
        self.stop_file, self.writable = stop_file, writable
        self.on_event = on_event
        self.confinement: dict[str, Any] = {"level": _confine.NONE,
                                            "layers": [], "reason":
                                            "no worker has started",
                                            "policy_sha256": None}

    def _worker_command(self) -> list[Any]:
        # the policy is the budget's, derived in the worker like any pool's
        # (8.4); the profile adds nothing to it but the run's own temporary
        # directory, which is the last of `writable`
        return super()._worker_command() + [
            "--stop-file", self.stop_file, "--confine-probe"]

    def _worker_temp(self) -> str | None:
        return str(self.writable[-1])

    def _worker_options(self) -> dict[str, Any]:
        import subprocess
        options: dict[str, Any] = {"one_process": True,
                                   "env": _worker_env(self.writable[-1])}
        # its own process group: a Ctrl+C or Ctrl+Break meant for eval asks
        # the run to stop, and does not end the worker before it can
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
        else:
            options["start_new_session"] = True
        return options

    def _started(self, worker: _Worker) -> None:
        worker.on_event = self.on_event
        self.confinement = dict(worker.confinement)
        if self.confinement.get("level") == _confine.NONE:
            # the profile requires full or partial (8.4): nothing of the
            # program has been sent to this worker, and nothing will be
            worker.dispose()
            raise EvalRefused(
                "the eval profile requires the operating system's "
                "confinement, fully or partly, and this worker got none: "
                + str(self.confinement.get("reason")))

    def kill_running(self) -> None:
        with self._lock:
            live = list(self._live)
        for worker in live:
            worker.kill()


def _stream_opener() -> Any:
    """An opener that sends a receipt where it was asked to go: no ambient
    proxy, and a redirect is a failure to send it."""
    import urllib.request

    class Stay(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req: urllib.request.Request, fp: Any,
                             code: int, msg: str, headers: Any,
                             newurl: str) -> urllib.request.Request | None:
            return None
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), Stay)


class _Stream:
    """--receipt-url: what the receipt records, as it happens, and the
    receipt at the end, each POSTed as one JSON object."""

    def __init__(self, url: str | None, run: str) -> None:
        self.url, self.run, self.seq = url, run, 0
        self.failures: list[str] = []
        self.opener: Any = _stream_opener() if url else None

    def send(self, kind: str, body: dict[str, Any]) -> bool:
        if self.url is None:
            return True
        import urllib.request
        self.seq += 1
        doc = dict(body, schema=RECEIPT_STREAM_SCHEMA, run=self.run,
                   seq=self.seq, kind=kind)
        request = urllib.request.Request(
            self.url, data=json.dumps(doc).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json",
                     "User-Agent": f"velaris/{VERSION}"})
        try:
            with self.opener.open(request, timeout=10) as answer:
                if answer.status >= 300:
                    raise OSError(f"HTTP {answer.status}")
            return True
        except Exception as e:
            self.failures.append(f"{kind} {self.seq}: {type(e).__name__}: "
                                 f"{e}")
            return False

    def event(self, event: Any) -> None:
        self.send("event", {"event": event})


class _Stopper:
    """A stop asked for from outside - a signal, or --stop-file appearing -
    passed to the worker as its stop file, and the worker killed if it has
    not stopped within the grace period."""

    def __init__(self, stop_file: str, watch: str | None, grace: float,
                 kill: Any) -> None:
        self.stop_file, self.watch, self.grace, self.kill = (
            stop_file, watch, grace, kill)
        self.asked: str | None = None
        self.asked_at: float | None = None
        self.killed = False
        self.began = time.monotonic()
        self._lock = threading.Lock()
        self._done = threading.Event()
        self._thread = threading.Thread(target=self._watch, daemon=True)
        self._thread.start()

    def ask(self, why: str) -> None:
        with self._lock:
            if self.asked is not None:
                return
            self.asked, self.asked_at = why, time.monotonic()
        try:
            with open(self.stop_file, "w", encoding="utf-8"):
                pass
        except OSError:
            pass

    def _watch(self) -> None:
        while not self._done.wait(0.05):
            if self.watch and self.asked is None and os.path.exists(self.watch):
                self.ask("the stop file appeared")
            if (self.asked_at is not None and not self.killed
                    and time.monotonic() - self.asked_at >= self.grace):
                self.killed = True
                self.kill()

    def finish(self) -> None:
        self._done.set()
        self._thread.join(timeout=5)


def _signals(stopper: _Stopper) -> tuple[bool, list[Any]]:
    """Signals that ask for a stop, where this thread can take them."""
    if threading.current_thread() is not threading.main_thread():
        return False, []
    saved = []

    def asker(name: str) -> Any:
        def handler(_signum: int, _frame: Any) -> None:
            stopper.ask(f"the signal {name}")
        return handler

    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        sig = getattr(signal, name, None)
        if sig is None:
            continue
        try:
            saved.append((sig, signal.signal(sig, asker(name))))
        except (ValueError, OSError):
            pass
    return bool(saved), saved


def _write_atomically(path: str, text: str) -> None:
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".receipt-", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read_stdin() -> str:
    stream = getattr(sys.stdin, "buffer", None)
    if stream is None or sys.stdin.isatty():
        return ""
    data = stream.read(EVAL_STDIN_MOST + 1)
    if len(data) > EVAL_STDIN_MOST:
        raise EvalRefused("standard input past 16 MiB")
    return str(data.decode("utf-8", errors="replace"))


def _parse(argv: list[str]) -> dict[str, Any]:
    opts: dict[str, Any] = {"files": []}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in _VALUED:
            if i + 1 >= len(argv):
                raise EvalRefused(f"{a} needs a value")
            if a in opts:
                raise EvalRefused(f"{a} is given twice")
            opts[a] = argv[i + 1]
            i += 2
            continue
        if a in _SWITCHES:
            opts[a] = True
        elif a.startswith("-"):
            name = a.split("=", 1)[0]
            why = next((w for f, w in EVAL_REFUSED_FLAGS if f == name), None)
            raise EvalRefused(f"{name}: {why}" if why else
                              f"{name} is not a flag of velaris eval")
        else:
            opts["files"].append(a)
        i += 1
    return opts


def eval_main(argv: list[str], program_words: list[str] | None = None) -> int:
    """velaris eval program.vel (--receipt FILE | --receipt-url URL) ..."""
    try:
        opts = _parse(list(argv))
    except EvalRefused as e:
        print(f"velaris eval: refused: {e}", file=sys.stderr)
        return 2
    if opts.get("--confinement-probe"):
        return confinement_probe(bool(opts.get("--json")))
    try:
        return _eval(opts, list(program_words or []))
    except EvalRefused as e:
        print(f"velaris eval: refused: {e}", file=sys.stderr)
        return 2


def _eval(opts: dict[str, Any], program_words: list[str]) -> int:
    import posixpath
    import uuid
    if len(opts["files"]) != 1:
        raise EvalRefused("name one program: velaris eval program.vel "
                          "--receipt FILE")
    program = opts["files"][0]
    budget = eval_budget(opts.get("--allow", "io"), opts.get("--deny"))
    timeout = _number("--timeout", opts.get("--timeout",
                                            str(EVAL_TIMEOUT_DEFAULT)),
                      EVAL_TIMEOUT_MOST)
    memory = int(_number("--max-memory-mb",
                         opts.get("--max-memory-mb",
                                  str(EVAL_MEMORY_MB_DEFAULT)),
                         EVAL_MEMORY_MB_MOST, whole=True))
    grace = _number("--grace", opts.get("--grace", str(EVAL_GRACE_DEFAULT)),
                    EVAL_GRACE_MOST)
    seed = opts.get("--seed")
    if seed is not None and not _ascii_digits(seed.lstrip("-")):
        raise EvalRefused("--seed needs a whole number")
    receipt_file, receipt_url = opts.get("--receipt"), opts.get("--receipt-url")
    if receipt_file is None and receipt_url is None:
        raise EvalRefused("a run under the eval profile has a receipt: name "
                          "--receipt FILE, --receipt-url URL, or both")
    if receipt_url is not None and not receipt_url.lower().startswith(
            ("http://", "https://")):
        raise EvalRefused("--receipt-url is an http or https URL")
    if not os.path.isfile(program):
        raise EvalRefused(f"{program}: no such file")
    real_program = os.path.normcase(os.path.realpath(program))
    if receipt_file is not None:
        where = os.path.normcase(os.path.realpath(receipt_file))
        if where == real_program:
            raise EvalRefused("the receipt would overwrite the program")
        for kind, prefix in budget.fs or []:
            if _inside(where, prefix) or _inside(prefix, where):
                raise EvalRefused(
                    f"the receipt {receipt_file} is inside the budget's "
                    f"fs:{kind} grant, where the program could write or read "
                    f"it; keep it outside every grant")
        if not os.path.isdir(os.path.dirname(os.path.abspath(receipt_file))):
            raise EvalRefused(f"the receipt's directory does not exist: "
                              f"{receipt_file}")
    with open(program, "rb") as fh:
        raw = fh.read()
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise EvalRefused(f"{program} is not UTF-8 text")
    root = os.path.realpath(opts.get("--root") or os.path.dirname(
        os.path.abspath(program)))
    stdin_text = _read_stdin()

    home = tempfile.mkdtemp(prefix="velaris-eval-")
    work = os.path.join(home, "tmp")
    os.makedirs(work)
    stream = _Stream(receipt_url, str(uuid.uuid4()))
    writable = [prefix for kind, prefix in budget.fs or []
                if kind == "write"] + [work]
    pool = _EvalPool(allow=budget.spec(), timeout=timeout,
                     max_memory_mb=memory, import_root=root,
                     stop_file=os.path.join(home, "stop"), writable=writable,
                     on_event=stream.event)
    stopper = _Stopper(os.path.join(home, "stop"), opts.get("--stop-file"),
                       grace, pool.kill_running)
    took, saved = _signals(stopper)
    name = posixpath.normpath(program.replace(os.sep, "/"))
    stream.send("started", {"program": name, "budget": budget.spec(),
                            "producer": {"name": "velaris-lang",
                                         "version": VERSION}})
    held: dict[str, Any] = {}

    def go() -> None:
        try:
            held["result"] = pool.run(
                source, stdin=stdin_text, args=program_words, path=program,
                seed=None if seed is None else int(seed),
                freeze_time=opts.get("--freeze-time"), _name=name)
        except BaseException as e:           # reported below, in this thread
            held["error"] = e

    runner = threading.Thread(target=go, daemon=True)
    try:
        runner.start()
        while runner.is_alive():
            runner.join(0.1)                 # a signal is taken between these
    finally:
        stopper.finish()
        pool.close()
        for sig, before in saved:
            try:
                signal.signal(sig, before)
            except (ValueError, OSError):
                pass
        import shutil
        shutil.rmtree(home, ignore_errors=True)
    if "error" in held:
        if isinstance(held["error"], ValueError):
            raise EvalRefused(str(held["error"]))
        raise held["error"]
    result = held["result"]
    receipt = result.receipt
    predicate = receipt["predicate"]
    predicate["run_parameters"].update(_confinement_fields(pool.confinement))
    predicate["run_parameters"]["profile"] = "eval"
    stop = None
    if stopper.asked is not None:
        code = predicate["exit"].get("code")
        if stopper.killed and code not in ("E610", "E611", "E615"):
            predicate["exit"] = {"status": 1, "outcome": "failed",
                                 "code": "E615"}
            predicate["complete"] = False
            result.problems = [Problem(
                "E615", f"this run was asked to stop and had not stopped "
                        f"{grace:g} second(s) later, so its worker was "
                        f"killed", 0, program, [])]
            result.ok, result.exit_code = False, 1
            honoured = "worker killed after the grace period"
        elif code == "E615":
            honoured = "at a call or loop turn"
        else:
            honoured = "the run had already ended"
        stop = {"asked": stopper.asked, "honoured": honoured,
                "after_ms": round(((stopper.asked_at or stopper.began)
                                   - stopper.began) * 1000, 1),
                "grace_seconds": grace}
        predicate["stop"] = stop
    delivered = True
    text = json.dumps(receipt, indent=2, ensure_ascii=False) + "\n"
    if receipt_file is not None:
        try:
            _write_atomically(receipt_file, text)
        except OSError as e:
            delivered = False
            print(f"velaris eval: the receipt could not be written to "
                  f"{receipt_file}: {e.strerror or e}", file=sys.stderr)
    if not stream.send("receipt", {"statement": receipt}):
        delivered = False
    for failure in stream.failures:
        print(f"velaris eval: the receipt stream to {receipt_url} failed: "
              f"{failure}", file=sys.stderr)
    status = int(result.exit_code) if delivered else 3
    if opts.get("--json"):
        print(json.dumps({
            "schema": EVAL_SCHEMA, "ok": bool(result.ok),
            "exit_code": result.exit_code, "exit": status,
            "outcome": predicate["exit"]["outcome"],
            "code": predicate["exit"]["code"],
            "confinement": pool.confinement.get("level"),
            "confinement_layers": pool.confinement.get("layers"),
            "confinement_reason": pool.confinement.get("reason"),
            "signals": took,
            "receipt": receipt_file, "receipt_url": receipt_url,
            "delivered": delivered, "stream_failures": stream.failures,
            "stop": stop, "output": result.output, "logs": result.logs,
            "problems": [{"code": p.code, "message": p.message,
                          "line": p.line} for p in result.problems]},
            indent=2))
        return status
    sys.stdout.write(result.output)
    sys.stderr.write(result.logs)
    for p in result.problems:
        print(f"{program}:{p.line}: [{p.code}] {p.message}", file=sys.stderr)
    print(f"velaris eval: {predicate['exit']['outcome']}"
          + (f" ({predicate['exit']['code']})" if predicate["exit"]["code"]
             else "")
          + f", confinement {pool.confinement.get('level')}, receipt "
          + ("NOT delivered" if not delivered else " and ".join(
              ([f"written to {receipt_file}"] if receipt_file else [])
              + ([f"sent to {receipt_url}"] if receipt_url else []))),
          file=sys.stderr)
    return status


def confinement_probe(as_json: bool) -> int:
    """velaris eval --confinement-probe: start a worker confined as a run
    under the profile is, have it try what the levels claim to stop, and say
    what it could do. Exit 0 when every refusal the level claims held, 1 when
    one did not, 2 when the worker gave no answer."""
    import shutil
    import socket
    home = tempfile.mkdtemp(prefix="velaris-eval-probe-")
    work = os.path.join(home, "tmp")
    os.makedirs(work)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    port = listener.getsockname()[1]
    outside = os.path.join(home, "outside.txt")
    secret = os.path.join(home, "outside-read.txt")
    with open(secret, "w", encoding="utf-8") as fh:
        fh.write("a file outside every grant")
    pool = _EvalPool(allow="io", timeout=120,
                     max_memory_mb=EVAL_MEMORY_MB_DEFAULT, import_root=work,
                     stop_file=os.path.join(home, "stop"), writable=[work])
    answer = None
    try:
        answer, _events, _worker, _seconds = pool._use(
            {"op": "probe", "port": port, "write": outside, "read": secret},
            lambda a: False)
    except EvalRefused as e:
        print(f"velaris eval: {e}", file=sys.stderr)
    finally:
        pool.close()
        listener.close()
        shutil.rmtree(home, ignore_errors=True)
    tried = (answer or {}).get("probe")
    level = str(pool.confinement.get("level"))
    if not isinstance(tried, dict):
        print(f"velaris eval: the confined worker gave no answer "
              f"({answer!r})", file=sys.stderr)
        return 2
    claimed = _confine.claims(pool.confinement, _confine.os_policy(
        Budget.parse("io")))
    broken = [k for k in claimed if not str(tried.get(k, "")).startswith(
        "refused")]
    what = (("connect", "a TCP connection to 127.0.0.1"),
            ("write", "a file written outside the granted directories"),
            ("read", "a file read outside the granted directories"),
            ("spawn", "a process started"))
    if as_json:
        print(json.dumps({"schema": EVAL_SCHEMA, "confinement": level,
                          "confinement_layers": pool.confinement.get("layers"),
                          "confinement_reason": pool.confinement.get("reason"),
                          "claims": list(claimed), "tried": tried,
                          "held": not broken}, indent=2))
    else:
        print(f"confinement: {level} "
              f"({', '.join(pool.confinement.get('layers') or []) or 'no layer'})"
              + (f"\n  why: {pool.confinement.get('reason')}"
                 if level != _confine.FULL else ""))
        for key, label in what:
            said = str(tried.get(key, ""))
            print(f"  {'refused ' if said.startswith('refused') else 'allowed '}"
                  f" {label}"
                  + ("  (this level claims to refuse it)" if key in claimed
                     else ""))
        print("every refusal this level claims held" if not broken else
              f"NOT HELD: {', '.join(broken)}")
    return 1 if broken else 0
