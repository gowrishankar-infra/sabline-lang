#!/usr/bin/env python3
"""velaris eval (8.3): a run under the profile holds it, and every attempt to
relax the profile from the command line is refused.

    python check_eval.py

What it holds, each against the command line as a user runs it:

  refused    net, ffi and env in any spelling; --allow all; an fs grant
             with no path; a time, memory or grace limit that is missing a
             number, zero, negative, not a number or past the most; no
             receipt; a receipt URL that is not http(s); a receipt inside
             an fs grant or over the program; the flags other commands take
             that would relax it (--no-check-ceiling, --check-timeout,
             --check-memory-mb, --max-read), flags that do not exist, and a
             flag given twice. Each exits 2 and writes no receipt.
  receipt    a run's receipt names the new predicate type, the budget it
             was given, the profile's limits, the confinement level eval
             reported and the profile; it validates against velaris-spec's
             schema when that is here, and `velaris verify` verifies it
  stops      a stop file asked for mid-loop ends the run at a stop point
             with E615 and a complete receipt; a stop the worker cannot see
             (a compile stalled in the checker) ends with the worker killed
             after the grace period, E615 and an incomplete receipt; a
             signal does the same as the stop file where eval can take one;
             the time limit is E610, the memory cap E611 where it holds
  stream     --receipt-url gets the start, each event and the receipt, in
             order; an address that answers nothing makes eval exit 3 and
             the file is still written
  confined   the level is the one this platform offers, and the probe finds
             every refusal that level claims held; a program still writes
             inside its fs:write grant under it
"""
from __future__ import annotations

import http.server
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import velaris  # noqa: E402
from velaris import confine  # noqa: E402
from suite_dirs import isolate  # noqa: E402

WORK = isolate("check_eval")
VELARIS = [sys.executable, str(HERE / "velaris.py")]
PASSED = FAILED = SKIPPED = 0

HELLO = 'fn main() uses io {\n    print("args " + to_text(args()))\n}\n'
SPIN = ("fn main() uses io {\n    let i = 0\n    while i >= 0 {\n"
        "        i = i + 1\n    }\n}\n")
WRITER = ('fn main() uses io, fs {\n    write_file("out/made.txt", "made")\n'
          '    print("wrote")\n}\n')
GROW = ('fn main() uses io {\n    let t = "0123456789"\n'
        '    while length(t) >= 0 {\n        t = t + t\n    }\n}\n')
# a compile the checker spends seconds on, with no stop point in it
INFLATED = "".join(
    f"fn f{i}(n: Int) -> Int {{ return {'+'.join(['n'] * 999)} }}\n"
    for i in range(900)) + "fn main() uses io { print(f0(1)) }\n"


def ok(label: str, good: object, detail: Any = "") -> None:
    global PASSED, FAILED
    if good:
        PASSED += 1
        print(f"  ok      {label}")
    else:
        FAILED += 1
        print(f"  WRONG   {label}")
        if detail:
            print(f"          {str(detail)[:600]}")


def skip(label: str, why: str) -> None:
    global SKIPPED
    SKIPPED += 1
    print(f"  skip    {label} ({why})")


def run_eval(*args: str, stdin: str = "", timeout: float = 300,
             **kw: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(VELARIS + ["eval", *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          input=stdin, timeout=timeout, cwd=str(WORK), **kw)


def receipt_of(name: str) -> dict[str, Any]:
    path = WORK / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() \
        else {}


def expected_level() -> set[str]:
    """What this platform should give, as confine.py names it."""
    if os.name == "nt":
        return {confine.WINDOWS_JOB} if velaris.memory_cap_is_enforced() \
            else {confine.NONE}
    if sys.platform.startswith("linux"):
        abi = confine.landlock_abi()
        return ({confine.NONE} if abi < 1 else
                {confine.LANDLOCK} if abi < 4 else {confine.LANDLOCK_NET})
    if sys.platform == "darwin":
        return {confine.MAC_SANDBOX, confine.NONE}
    return {confine.NONE}


def refusals() -> None:
    print("every relaxation is refused")
    print("-" * 62)
    (WORK / "data").mkdir(exist_ok=True)
    (WORK / "out").mkdir(exist_ok=True)
    cases = [
        ("net", ["--allow", "net"]),
        ("a scoped net grant", ["--allow", "io,net:127.0.0.1:80"]),
        ("ffi", ["--allow", "ffi"]),
        ("a named ffi module", ["--allow", "io,ffi:math"]),
        ("env", ["--allow", "io,env"]),
        ("--allow all", ["--allow", "all"]),
        ("fs with no path", ["--allow", "io,fs"]),
        ("fs:read with no path", ["--allow", "io,fs:read"]),
        ("fs:write with a count and no path", ["--allow", "io,fs:write@3"]),
        ("a budget that does not parse", ["--allow", "io,nonsense"]),
        ("--deny of something that is not an effect", ["--deny", "x"]),
        ("a zero timeout", ["--timeout", "0"]),
        ("a negative timeout", ["--timeout", "-1"]),
        ("a timeout that is not a number", ["--timeout", "nan"]),
        ("an infinite timeout", ["--timeout", "inf"]),
        ("a timeout past the most", ["--timeout", "601"]),
        ("a zero memory cap", ["--max-memory-mb", "0"]),
        ("a memory cap past the most", ["--max-memory-mb", "4097"]),
        ("a memory cap that is not whole", ["--max-memory-mb", "1.5"]),
        ("a grace period past the most", ["--grace", "61"]),
        ("--no-check-ceiling", ["--no-check-ceiling"]),
        ("--check-timeout", ["--check-timeout", "999"]),
        ("--check-memory-mb", ["--check-memory-mb", "9999"]),
        ("--max-read", ["--max-read", "999"]),
        ("--no-confine", ["--no-confine"]),
        ("a flag eval does not have", ["--unheard-of"]),
        ("a flag given twice", ["--timeout", "5", "--timeout", "500"]),
        ("a seed that is not a number", ["--seed", "x"]),
        ("a frozen time that is not an instant", ["--freeze-time", "soon"]),
    ]
    (WORK / "hello.vel").write_text(HELLO, encoding="utf-8")
    for label, extra in cases:
        target = WORK / "refused.json"
        if target.exists():
            target.unlink()
        done = run_eval("hello.vel", "--receipt", "refused.json", *extra)
        # --seed and --freeze-time are read for every command before eval
        # sees them, and refused there, naming the flag
        said = ("refused" in done.stderr
                or (extra[0] in ("--seed", "--freeze-time")
                    and extra[0] in done.stderr))
        ok(f"refused: {label}", done.returncode == 2 and said
           and not target.exists(),
           f"exit {done.returncode}: {done.stderr.strip()[-300:]}")
    for label, extra in [
            ("no receipt at all", []),
            ("a receipt URL that is not http", ["--receipt-url", "ftp://x/y"]),
            ("a receipt inside the fs:write grant",
             ["--allow", "io,fs:write:out", "--receipt", "out/r.json"]),
            ("a receipt inside the fs:read grant",
             ["--allow", "io,fs:read:data", "--receipt", "data/r.json"]),
            ("a receipt that is the program", ["--receipt", "hello.vel"]),
            ("a receipt in a directory that does not exist",
             ["--receipt", "nowhere/r.json"])]:
        done = run_eval("hello.vel", *extra)
        ok(f"refused: {label}", done.returncode == 2
           and "refused" in done.stderr,
           f"exit {done.returncode}: {done.stderr.strip()[-300:]}")
    ok("the program was not changed by a refused run",
       (WORK / "hello.vel").read_text(encoding="utf-8") == HELLO)
    done = run_eval("hello.vel", "--receipt", "words.json", "--", "--allow",
                    "all")
    rec = receipt_of("words.json")
    ok("words after -- are the program's arguments, never eval's flags",
       done.returncode == 0 and "--allow" in done.stdout
       and rec.get("predicate", {}).get("budget") == "io",
       f"{done.returncode} {done.stdout!r} {done.stderr[-200:]}")


def receipts() -> None:
    print()
    print("a run's receipt says the profile it ran under")
    print("-" * 62)
    done = run_eval("hello.vel", "--receipt", "hello.json", "--json")
    report = json.loads(done.stdout or "{}")
    rec = receipt_of("hello.json")
    p = rec.get("predicate", {})
    params = p.get("run_parameters", {})
    ok("a clean run exits 0 and writes its receipt",
       done.returncode == 0 and report.get("delivered") is True and rec,
       done.stderr[-300:])
    ok("...a Statement of receipt/v1 at velaris-lang.dev",
       rec.get("predicateType") == velaris.RECEIPT_PREDICATE_TYPE
       == "https://velaris-lang.dev/receipt/v1")
    ok("...whose budget is what the run was given, io",
       p.get("budget") == "io", p.get("budget"))
    ok("...whose limits are the profile's defaults, 30 s and 512 MB",
       params.get("timeout") == 30 and params.get("max_memory_mb") == 512,
       params)
    ok("...naming the profile and the confinement eval reported",
       params.get("profile") == "eval"
       and params.get("confinement") == report.get("confinement"), params)
    ok("...the confinement this platform offers",
       params.get("confinement") in expected_level(),
       f"{params.get('confinement')} not in {expected_level()}")
    ok("...complete, ok, and no stop", p.get("complete") is True
       and p.get("exit", {}).get("outcome") == "ok" and "stop" not in p, p)
    verified = subprocess.run(VELARIS + ["verify", "hello.json"],
                              capture_output=True, text=True, cwd=str(WORK))
    ok("velaris verify verifies it against the program's bytes",
       verified.returncode == 0, verified.stdout[-400:])
    spec_schema = next((s for s in (
        HERE / "velaris-spec" / "schemas" / "receipt-predicate.v1.schema.json",
        HERE.parent / "velaris-spec" / "schemas"
        / "receipt-predicate.v1.schema.json") if s.exists()), None)
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        Draft202012Validator = None  # type: ignore[assignment, misc]  # jsonschema is optional
    if spec_schema is None or Draft202012Validator is None:
        skip("the receipt validates against velaris-spec's schema",
             "velaris-spec or jsonschema is not here")
    else:
        errors = [e.message for e in Draft202012Validator(json.loads(
            spec_schema.read_text(encoding="utf-8"))).iter_errors(p)]
        ok("the receipt validates against velaris-spec's schema", not errors,
           errors[:3])
    (WORK / "data" / "in.txt").write_text("x", encoding="utf-8")
    done = run_eval("hello.vel", "--receipt", "scoped.json", "--allow",
                    "io,fs:read:data", "--timeout", "20",
                    "--max-memory-mb", "300")
    p = receipt_of("scoped.json").get("predicate", {})
    ok("a scoped grant and lower limits are what the receipt records",
       done.returncode == 0 and "fs:read:" in p.get("budget", "")
       and p.get("run_parameters", {}).get("timeout") == 20
       and p.get("run_parameters", {}).get("max_memory_mb") == 300, p)
    (WORK / "writer.vel").write_text(WRITER, encoding="utf-8")
    made = WORK / "out" / "made.txt"
    if made.exists():
        made.unlink()
    done = run_eval("writer.vel", "--receipt", "writer.json", "--allow",
                    "io,fs:write:out")
    ok("a program writes inside its fs:write grant under the confinement",
       done.returncode == 0 and made.exists(),
       f"{done.returncode} {done.stderr[-300:]}")


def stops() -> None:
    print()
    print("stops, asked for and not")
    print("-" * 62)
    (WORK / "spin.vel").write_text(SPIN, encoding="utf-8")
    stop = WORK / "stop-now"
    if stop.exists():
        stop.unlink()
    threading.Timer(2.5, lambda: stop.write_text("", encoding="utf-8")).start()
    began = time.monotonic()
    done = run_eval("spin.vel", "--receipt", "spin.json", "--stop-file",
                    str(stop), "--timeout", "120", "--json")
    took = time.monotonic() - began
    p = receipt_of("spin.json").get("predicate", {})
    ok("a stop file ends a spinning loop at a stop point, E615, long before "
       "its time limit", p.get("exit", {}).get("code") == "E615"
       and took < 60 and done.returncode == 1, f"{took:.1f}s {p.get('exit')}")
    ok("...and its receipt is complete and says the stop was honoured there",
       p.get("complete") is True
       and (p.get("stop") or {}).get("honoured") == "at a call or loop turn",
       p.get("stop"))
    stop.unlink()
    (WORK / "inflated.vel").write_text(INFLATED, encoding="utf-8")
    threading.Timer(2, lambda: stop.write_text("", encoding="utf-8")).start()
    began = time.monotonic()
    done = run_eval("inflated.vel", "--receipt", "inflated.json",
                    "--stop-file", str(stop), "--grace", "1",
                    "--timeout", "300")
    took = time.monotonic() - began
    p = receipt_of("inflated.json").get("predicate", {})
    # The compile is stalled by 900 functions of 999 additions each, which on
    # some machines exhausts the profile's memory before the grace period is
    # up. Either way the run ends without the worker ever seeing the stop,
    # its receipt is incomplete, and it says which happened.
    exit_now = p.get("exit", {})
    stop_now = p.get("stop") or {}
    grace_killed = (exit_now.get("code") == "E615"
                    and stop_now.get("honoured")
                    == "worker killed after the grace period")
    out_of_memory = (exit_now.get("code") == "E611"
                     and stop_now.get("honoured") == "the run had already "
                     "ended")
    ok("a stop the worker cannot see ends with it killed after the grace "
       "period (or by the memory ceiling first): an incomplete receipt",
       (grace_killed or out_of_memory) and p.get("complete") is False
       and took < 60, f"{took:.1f}s {exit_now} {stop_now}")
    stop.unlink()
    done = run_eval("spin.vel", "--receipt", "timeout.json", "--timeout", "2")
    p = receipt_of("timeout.json").get("predicate", {})
    ok("the time limit ends a run with E610 and an incomplete receipt",
       p.get("exit", {}).get("outcome") == "timeout"
       and p.get("complete") is False, p.get("exit"))
    if velaris.memory_cap_is_enforced():
        (WORK / "grow.vel").write_text(GROW, encoding="utf-8")
        done = run_eval("grow.vel", "--receipt", "grow.json",
                        "--max-memory-mb", "150", "--timeout", "120")
        p = receipt_of("grow.json").get("predicate", {})
        ok("the memory cap ends a run with E611",
           p.get("exit", {}).get("code") == "E611", p.get("exit"))
    else:
        skip("the memory cap ends a run with E611",
             "the cap is not enforced on this machine")
    flags: dict[str, Any] = {}
    if os.name == "nt":
        flags["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]  # Windows only
    proc = subprocess.Popen(VELARIS + ["eval", "spin.vel", "--receipt",
                                       "signal.json", "--timeout", "120",
                                       "--json"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            stdin=subprocess.DEVNULL, text=True,
                            cwd=str(WORK), **flags)
    time.sleep(4)
    proc.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt"  # type: ignore[attr-defined]  # Windows only
                     else signal.SIGTERM)
    out, err = proc.communicate(timeout=120)
    report = json.loads(out or "{}")
    # Where eval runs off the main thread - CPython before 3.11 - no handler
    # is installed, so the run says `signals: false`; and with no handler the
    # signal's own disposition ends the process before it can say even that:
    # a console break on Windows (0xC000013A), SIGTERM elsewhere (-15).
    killed_unhandled = proc.returncode in (0xC000013A, -signal.SIGTERM)
    no_signals = report.get("signals") is False or (
        not report and killed_unhandled and sys.version_info < (3, 11))
    if no_signals:
        skip("a signal asks for a stop as the stop file does",
             "eval runs off the main thread here (CPython before 3.11), "
             "where no signal can be taken")
    else:
        ok("a signal asks for a stop as the stop file does",
           report.get("code") == "E615"
           and "signal" in str((report.get("stop") or {}).get("asked")),
           f"{proc.returncode} {out[-300:]} {err[-300:]}")


def stream() -> None:
    print()
    print("--receipt-url")
    print("-" * 62)
    posts: list[dict[str, Any]] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            posts.append(json.loads(self.rfile.read(length)))
            self.send_response(204)
            self.end_headers()

        def log_message(self, *_args: Any) -> None:
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/receipts"
    try:
        done = run_eval("hello.vel", "--receipt", "both.json",
                        "--receipt-url", url)
    finally:
        server.shutdown()
    kinds = [x.get("kind") for x in posts]
    ok("the URL gets the start, the events and the receipt, in order",
       done.returncode == 0 and kinds[:1] == ["started"]
       and kinds[-1:] == ["receipt"]
       and [x.get("seq") for x in posts] == list(range(1, len(posts) + 1)),
       kinds)
    ok("...each marked velaris.receipt-stream/1 with one run id",
       all(x.get("schema") == "velaris.receipt-stream/1" for x in posts)
       and len({x.get("run") for x in posts}) == 1)
    ok("...and the receipt sent is the receipt written",
       bool(posts) and posts[-1].get("statement") == receipt_of("both.json"))
    done = run_eval("hello.vel", "--receipt", "undelivered.json",
                    "--receipt-url", "http://127.0.0.1:9/nobody")
    ok("an address that takes nothing: exit 3, and the file still written",
       done.returncode == 3 and receipt_of("undelivered.json"),
       f"{done.returncode} {done.stderr[-300:]}")


def confinement() -> None:
    print()
    print("confinement")
    print("-" * 62)
    done = subprocess.run(VELARIS + ["eval", "--confinement-probe", "--json"],
                          capture_output=True, text=True, cwd=str(WORK),
                          timeout=300)
    report = json.loads(done.stdout or "{}")
    ok("the probe's level is the one this platform offers",
       report.get("confinement") in expected_level(),
       f"{report.get('confinement')} not in {expected_level()}")
    ok("...and every refusal that level claims held", done.returncode == 0
       and report.get("held") is True, report)
    tried = report.get("tried") or {}
    ok("...and the probe really tried: a level of none refuses nothing it "
       "claims, and one that claims a refusal shows it refused",
       all(str(tried.get(k, "")).startswith("refused")
           for k in report.get("claims") or []), tried)


def windows_job() -> None:
    """The job eval gives its worker holds the processes starting it took,
    and refuses another (8.3). The count is not always one: where
    `python.exe` is a launcher - a virtual environment's - the real
    interpreter is a second process, and a job that insisted on one would
    stop the worker before it began."""
    print()
    print("the Windows job object, told what to hold")
    print("-" * 62)
    label = "a worker under the job starts no further process"
    if os.name != "nt":
        skip(label, "Windows only")
        return
    if not velaris.memory_cap_is_enforced():
        skip(label, "no job object can be made on this machine")
        return
    from velaris.library import _spawn_capped
    child = WORK / "spawns.py"
    child.write_text(
        "import subprocess, sys\n"
        "print('ready', flush=True)\n"
        "sys.stdin.readline()\n"
        "try:\n"
        "    done = subprocess.run([sys.executable, '-c', \"print('here')\"],\n"
        "                          capture_output=True, text=True, timeout=60)\n"
        "    print('started' if done.returncode == 0 else\n"
        "          f'refused: exit {done.returncode}', flush=True)\n"
        "except Exception as e:\n"
        "    print(f'refused: {type(e).__name__}', flush=True)\n",
        encoding="utf-8")
    proc, job, how = _spawn_capped(
        [sys.executable, str(child)], 512, one_process=True,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True)
    try:
        ok("...and the worker starts at all under it (a launcher needs two "
           "processes)", (proc.stdout.readline() or "").strip() == "ready"
           and how == "job object", how)
        held = job.hold_current() if job is not None else None
        ok("...the job is then told to hold the processes it has",
           held is not None and held >= 1, held)
        proc.stdin.write("go\n")
        proc.stdin.flush()
        said = (proc.stdout.readline() or "").strip()
        ok(label, said.startswith("refused"), said or "it said nothing")
    finally:
        proc.kill()
        proc.wait(timeout=30)
        if job is not None:
            job.close()


def main() -> int:
    refusals()
    receipts()
    stops()
    stream()
    confinement()
    windows_job()
    print("-" * 62)
    print(f"{PASSED} correct, {FAILED} wrong, {SKIPPED} skipped")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
