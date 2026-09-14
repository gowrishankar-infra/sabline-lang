#!/usr/bin/env python3
"""A pool must be faster than a fresh process AND leak nothing between
programs.

The speed is why velaris.Pool exists. The isolation is why it can be
used at all: a worker that serves one program after another in one
process is exactly the place where one program's leftovers become the
next program's starting state. Every rule in Pool's docstring is
asserted here, and the last check is the speed, so the trade is visible
in one run.

    python check_pool.py

Nothing here depends on the prover. Run it in a Python with no
z3-solver as well; ARCHITECTURE.md rule 6 says why.
"""
import ast
import gc
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import velaris  # noqa: E402
from suite_dirs import isolate  # noqa: E402

# its own directory and proof cache, so two runs at once do not collide
WORK = isolate("check_pool")

TIMEOUT = 60
MEMORY_MB = 300

PRINTS = 'fn main() uses io {\n    print(21 * 2)\n}\n'

SHOWS_ARGS = 'fn main() uses io {\n    print(args())\n}\n'

ECHOES_STDIN = ('fn main() uses io {\n'
                '    print("heard " + ask("say:"))\n}\n')

NEVER_ENDS = ('fn main() uses io {\n    let i = 0\n    while i >= 0 {\n'
              '        i = i + 1\n        if i > 1000000 {\n'
              '            i = 0\n        }\n    }\n    print(1)\n}\n')

EATS_MEMORY = ('fn main() uses io {\n    let s = "xxxxxxxxxxxxxxxx"\n'
               '    let i = 0\n    while i < 40 {\n        s = s + s\n'
               '        i = i + 1\n    }\n    print(length(s))\n}\n')

READS_A_FILE = ('fn main() uses io, fs {\n'
                '    check read_file("velaris.py") {\n'
                '        ok t { print("READ IT") }\n'
                '        fail w { print("could not read") }\n    }\n}\n')

WONT_COMPILE = 'fn main() {\n    print("no effect declared")\n}\n'

# a handle nobody closes: the next program must not find it, and must
# not find the number it took either
LEAKS_A_HANDLE = (
    'fn main() uses io, ffi {\n'
    '    check py_new("io", "StringIO", "[\\"held\\"]") {\n'
    '        ok h { print(h) }\n'
    '        fail w { print("failed " + w) }\n    }\n}\n')

# The ffi cliff, used deliberately: this program reaches into the
# compiler and grants itself fs, then reads a file to show the widening
# really took - a check that has to be here, because the first version
# of this test named "velaris" instead of "__main__" and so mutated a
# SECOND import of the module rather than the live budget. It passed,
# and proved nothing. A worker runs velaris.py as __main__, so that is
# the name that reaches the budget the interpreter is enforcing.
# THREAT_MODEL.md says a granted module can do whatever that module can
# do; the pool promises only that it cannot do it to the NEXT program.
WIDENS_ITS_BUDGET = (
    'fn main() uses io, ffi, fs {\n'
    '    check py("__main__", "EFFECT_BUDGET.add", ["fs"]) {\n'
    '        ok v { print("widened") }\n'
    '        fail w { print("failed " + w) }\n'
    '    }\n'
    '    check read_file("velaris.py") {\n'
    '        ok t { print("READ IT") }\n'
    '        fail w { print("could not read") }\n    }\n}\n')

MOVES_DIRECTORY = (
    'fn main() uses io, ffi {\n'
    '    check py("os", "chdir", [".."]) {\n'
    '        ok v { print("moved") }\n'
    '        fail w { print("failed " + w) }\n    }\n}\n')

SAYS_DIRECTORY = (
    'fn main() uses io, ffi {\n'
    '    let none: List of Text = []\n'
    '    check py("os", "getcwd", none) {\n'
    '        ok v { print(v) }\n'
    '        fail w { print("failed " + w) }\n    }\n}\n')

# fd 1 belongs to the parent's pipe. This writes at it through a shell,
# under the eyes of nobody, and the protocol must survive.
SHOUTS_AT_FD_ONE = (
    'fn main() uses io, ffi {\n'
    '    check py_int("os", "system", ["echo CORRUPT_THE_PIPE"]) {\n'
    '        ok n { print("shell said " + n) }\n'
    '        fail w { print("failed " + w) }\n    }\n}\n')


def reads(path, times: int) -> str:
    """A program that reads one file `times` times over."""
    body = "".join(
        f'    check read_file("{path}") {{\n'
        f'        ok t {{ print("read") }}\n'
        f'        fail w {{ print("failed") }}\n    }}\n'
        for _ in range(times))
    return "fn main() uses io, fs {\n" + body + "}\n"


def alive(pid: int) -> bool:
    """Is there still a process with this id? The operating system's
    answer, not the parent's bookkeeping."""
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:
        pass
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.OpenProcess.restype = wintypes.HANDLE
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL,
                                  wintypes.DWORD]
        k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = k.OpenProcess(0x00100000, False, pid)   # SYNCHRONIZE
        if not handle:
            return False
        running = k.WaitForSingleObject(handle, 0) != 0   # 0 = it ended
        k.CloseHandle(handle)
        return running
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def all_gone(pids, seconds: float = 15.0) -> bool:
    """Every one of these processes has ended, within reason."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if not any(alive(pid) for pid in pids):
            return True
        time.sleep(0.1)
    return not any(alive(pid) for pid in pids)


def main() -> int:                        # noqa: C901 - a suite, not logic
    passed = failed = 0

    def ok(label, condition, detail=""):
        nonlocal passed, failed
        if condition:
            print(f"  ok       {label}")
            passed += 1
        else:
            print(f"  BROKEN   {label}")
            if detail:
                print(f"           {detail}")
            failed += 1

    box = Path(tempfile.mkdtemp(prefix="velaris-pool-"))
    (box / "a.txt").write_text("inside", encoding="utf-8")
    readable = (box / "a.txt").as_posix()

    print("a pool runs programs")
    print("-" * 62)

    with velaris.Pool(size=2, allow={"io"}, timeout=TIMEOUT,
                      max_memory_mb=MEMORY_MB) as pool:
        one = pool.run(PRINTS)
        ok("pool.run returns what run() returns",
           one.ok and one.output.strip() == "42" and one.exit_code == 0
           and not one.timed_out and not one.out_of_memory,
           str(one.as_dict())[:140])
        loose = velaris.run(PRINTS, allow={"io"})
        ok("and the same answer run() gives for the same program",
           one.as_dict() == loose.as_dict()
           or (one.ok == loose.ok and one.output == loose.output),
           f"{one.as_dict()} vs {loose.as_dict()}")

        r = pool.run(ECHOES_STDIN, stdin="hello\n")
        ok("stdin reaches a program through the pool",
           r.ok and "heard hello" in r.output, repr(r.output))

        r = pool.run(WONT_COMPILE)
        ok("a program that does not compile comes back as problems",
           not r.ok and any(p.code == "E300" for p in r.problems),
           str([p.code for p in r.problems]))
        r = pool.run(PRINTS)
        ok("...and the next program on that pool still runs",
           r.ok and r.output.strip() == "42", repr(r.output))

    print()
    print("what one program leaves for the next")
    print("-" * 62)

    pool = velaris.Pool(size=1, allow={"io"}, timeout=5,
                        max_memory_mb=MEMORY_MB)
    pool.run(PRINTS)                      # so there is a worker to lose
    doomed = pool.worker_pids()[0]
    slow = pool.run(NEVER_ENDS)
    ok("a program that never ends is stopped by the pool's deadline",
       slow.timed_out and not slow.ok
       and any(p.code == "E610" for p in slow.problems),
       str(slow.as_dict())[:140])
    ok("the timed-out worker was killed, not asked to stop",
       all_gone([doomed]), f"{doomed} is still alive")
    after = pool.run(PRINTS)
    ok("a timed-out program does not affect the next one on that pool",
       after.ok and after.output.strip() == "42", repr(after.output))
    ok("...which ran on a replacement worker",
       pool.worker_pids() and pool.worker_pids() != [doomed],
       f"{doomed} -> {pool.worker_pids()}")

    if velaris.memory_cap_is_enforced():
        doomed = pool.worker_pids()[0]
        fat = pool.run(EATS_MEMORY)
        ok("a program that fills memory is stopped",
           fat.out_of_memory and not fat.ok
           and any(p.code == "E611" for p in fat.problems),
           str(fat.as_dict())[:140])
        ok("the starved worker was killed", all_gone([doomed]),
           f"{doomed} is still alive")
        after = pool.run(PRINTS)
        ok("its successor runs normally, on a replacement worker",
           after.ok and after.output.strip() == "42"
           and pool.worker_pids() != [doomed],
           f"{after.output!r} {doomed} -> {pool.worker_pids()}")
    else:
        # macOS sets RLIMIT_AS and does not reliably honour it; a
        # Windows that refused the job object is the same case. The
        # timeout is what stops a runaway there, and it is asserted
        # above on every platform.
        print("  skip     a program that fills memory is stopped "
              "(no enforced memory cap on this platform)")
        print("  skip     the starved worker was killed")
        print("  skip     its successor runs normally, on a replacement "
              "worker")

    first = pool.run(SHOWS_ARGS, args=["alpha", "beta"])
    second = pool.run(SHOWS_ARGS)
    ok("args from one run do not appear in the next",
       "alpha" in first.output and "alpha" not in second.output
       and second.output.strip() == "[]",
       f"{first.output!r} then {second.output!r}")
    pool.close()

    # unscoped ffi: from 3.3 a scoped ffi:M grant is bounded to the
    # module actually reached, so io.StringIO (its code lives in _io),
    # os.chdir (nt/posix) and __main__.EFFECT_BUDGET.add (a set method
    # in builtins) are reachable only under an unscoped ffi. The cliff
    # these three exercise - and the pool's reset of what it leaves - is
    # an unscoped-ffi property; scoped grants close the cliff outright.
    with velaris.Pool(size=1, allow={"io", "ffi"},
                      timeout=TIMEOUT) as handles:
        one = handles.run(LEAKS_A_HANDLE)
        two = handles.run(LEAKS_A_HANDLE)
        ok("a Python handle nobody closed leaves nothing for the next "
           "program",
           one.ok and two.ok and one.output == two.output
           and "#2" in two.output,
           f"{one.output!r} then {two.output!r}")
        ok("...on the SAME worker, so the reset is what did it",
           handles.started == 1, f"started {handles.started}")

    with velaris.Pool(size=1, allow={"io", "ffi"},
                      timeout=TIMEOUT) as ffi:
        before = ffi.run(SAYS_DIRECTORY)
        moved = ffi.run(MOVES_DIRECTORY)
        after = ffi.run(SAYS_DIRECTORY)
        ok("a directory a program changed through ffi is put back",
           moved.ok and before.output == after.output
           and ffi.started == 1,
           f"{before.output!r} -> {after.output!r}, "
           f"started {ffi.started}")

        shouted = ffi.run(SHOUTS_AT_FD_ONE)
        still = ffi.run(PRINTS)
        ok("a program writing straight at file descriptor 1 cannot "
           "corrupt the pipe",
           shouted.ok and still.ok and still.output.strip() == "42",
           f"{shouted.as_dict()} then {still.output!r}")

    print()
    print("the budget is the pool's")
    print("-" * 62)

    import inspect
    params = set(inspect.signature(velaris.Pool.run).parameters)
    ok("pool.run takes no allow, deny, timeout or memory argument",
       not params & {"allow", "deny", "timeout", "max_memory_mb"},
       str(sorted(params)))
    with velaris.Pool(size=1, allow={"io"}, timeout=TIMEOUT) as narrow:
        try:
            narrow.run(PRINTS, allow={"fs"})
            ok("asking a pool for a wider budget is a TypeError", False)
        except TypeError:
            ok("asking a pool for a wider budget is a TypeError", True)

        one = narrow.run(READS_A_FILE)
        two = narrow.run(READS_A_FILE)
        ok("an effect outside the pool's budget is refused, every time",
           not one.ok and one.refused_effect == "fs"
           and not two.ok and two.refused_effect == "fs"
           and "READ IT" not in one.output + two.output,
           str(one.as_dict())[:140])

    with velaris.Pool(size=1, allow={"io", "ffi"},
                      timeout=TIMEOUT) as cliff:
        widened = cliff.run(WIDENS_ITS_BUDGET)
        ok("a program CAN widen its own budget through ffi - the cliff "
           "is real, and this is what the next check is against",
           widened.ok and "READ IT" in widened.output,
           str(widened.as_dict())[:160])
        then = cliff.run(READS_A_FILE)
        ok("...and it cannot widen it for the next program",
           not then.ok and then.refused_effect == "fs"
           and "READ IT" not in then.output
           and cliff.started == 1,
           f"{then.as_dict()}, started {cliff.started}")

    with velaris.Pool(size=1, allow={"io", f"fs:read:{box.as_posix()}@2"},
                      timeout=TIMEOUT) as counted:
        a = counted.run(reads(readable, 2))
        b = counted.run(reads(readable, 2))
        c = counted.run(reads(readable, 3))
        ok("a counted grant is spent per program, not per worker",
           a.ok and b.ok and not c.ok
           and any(p.code == "E315" for p in c.problems),
           f"{a.ok} {b.ok} {c.as_dict()}"[:160])

    outside = velaris.Pool(size=1, allow={"io"}, timeout=TIMEOUT)
    inside = velaris.Pool(size=1, allow={"io", f"fs:read:{box.as_posix()}"},
                          timeout=TIMEOUT)
    try:
        prog = reads(readable, 1)
        refused_first = outside.run(prog)
        allowed = inside.run(prog)
        refused_again = outside.run(prog)
        ok("two pools with different budgets do not see each other's "
           "grants",
           not refused_first.ok and refused_first.refused_effect == "fs"
           and allowed.ok
           and not refused_again.ok
           and refused_again.refused_effect == "fs",
           f"{refused_first.refused_effect} / {allowed.ok} / "
           f"{refused_again.refused_effect}")
        ok("...and they are different processes",
           not set(outside.worker_pids()) & set(inside.worker_pids()),
           f"{outside.worker_pids()} vs {inside.worker_pids()}")
    finally:
        outside.close()
        inside.close()

    try:
        velaris.Pool(size=1, allow={"banana"})
        ok("a budget that does not parse fails when the pool is made",
           False)
    except ValueError:
        ok("a budget that does not parse fails when the pool is made",
           True)

    print()
    print("workers, and what happens to them")
    print("-" * 62)

    pool = velaris.Pool(size=1, allow={"io"}, timeout=TIMEOUT)
    try:
        pool.run(PRINTS)
        doomed = pool.worker_pids()[0]
        killer = subprocess.run(
            (["taskkill", "/F", "/PID", str(doomed)] if os.name == "nt"
             else ["kill", "-9", str(doomed)]),
            capture_output=True, text=True)
        assert not alive(doomed) or killer.returncode == 0, killer.stderr
        for _ in range(50):
            if not alive(doomed):
                break
            time.sleep(0.1)
        again = pool.run(PRINTS)
        ok("a worker killed from outside is replaced",
           again.ok and again.output.strip() == "42"
           and pool.worker_pids() != [doomed] and pool.started >= 2,
           f"{again.as_dict()} pids {pool.worker_pids()}")
    finally:
        pool.close()

    pool = velaris.Pool(size=3, allow={"io"}, timeout=TIMEOUT)
    pool.run(PRINTS)
    pool.run(PRINTS)
    pool.run(PRINTS)
    pids = pool.worker_pids()
    pool.close()
    ok("close() leaves no live children",
       len(pids) == 3 and all_gone(pids),
       f"{pids} -> {[p for p in pids if alive(p)]}")
    try:
        pool.run(PRINTS)
        ok("running on a closed pool is refused", False)
    except RuntimeError:
        ok("running on a closed pool is refused", True)
    pool.close()                          # closing twice is not an error

    racing = velaris.Pool(size=1, allow={"io"}, timeout=120)
    caught, busy_pids = [], []

    def keeps_going():
        try:
            caught.append(racing.run(NEVER_ENDS))
        except RuntimeError as e:                          # noqa: BLE001
            caught.append(e)

    runner = threading.Thread(target=keeps_going)
    runner.start()
    for _ in range(200):                  # wait for the worker to exist
        busy_pids = racing.worker_pids()
        if busy_pids:
            break
        time.sleep(0.05)
    racing.close()
    runner.join(timeout=120)
    ok("close() kills a worker that is still running a program",
       bool(busy_pids) and all_gone(busy_pids) and not runner.is_alive()
       and len(caught) == 1,
       f"{busy_pids} -> {[p for p in busy_pids if alive(p)]}, "
       f"caught {caught}")

    def orphans():
        gone = velaris.Pool(size=1, allow={"io"}, timeout=TIMEOUT)
        gone.run(PRINTS)
        return gone.worker_pids()

    dropped = orphans()
    gc.collect()
    ok("a pool nobody closed leaves no children when it is collected",
       len(dropped) == 1 and all_gone(dropped),
       f"{dropped} -> {[p for p in dropped if alive(p)]}")

    leaver = WORK / "_pool_leaver.py"
    leaver.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(HERE)!r})\n"
        "import velaris\n"
        "pool = velaris.Pool(size=2, allow={'io'}, timeout=30)\n"
        f"pool.run({PRINTS!r})\n"
        f"pool.run({PRINTS!r})\n"
        "print(' '.join(str(p) for p in pool.worker_pids()))\n"
        "# and now the process exits without close()\n",
        encoding="utf-8")
    try:
        done = subprocess.run([sys.executable, str(leaver)],
                              capture_output=True, text=True, timeout=180)
        left = [int(x) for x in done.stdout.split()]
        ok("a process that exits without close() leaves no workers",
           len(left) == 2 and all_gone(left),
           f"{done.stdout!r} {done.stderr[-200:]!r}")
    finally:
        leaver.unlink(missing_ok=True)

    print()
    print("several callers at once")
    print("-" * 62)

    with velaris.Pool(size=4, allow={"io"}, timeout=TIMEOUT) as busy:
        answers, blame = {}, []

        def asker(n: int) -> None:
            try:
                got = busy.run(
                    f'fn main() uses io {{\n    print({n} * 1000)\n}}\n')
                answers[n] = got.output.strip()
            except Exception as e:                        # noqa: BLE001
                blame.append(f"{n}: {type(e).__name__}: {e}")

        threads = [threading.Thread(target=asker, args=(n,))
                   for n in range(1, 5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=180)
        ok("a pool used from four threads at once answers each caller "
           "correctly",
           not blame and answers == {n: str(n * 1000) for n in range(1, 5)},
           f"{answers} {blame}")

        many, wrong = 24, []

        def hammer(n: int) -> None:
            for _ in range(3):
                got = busy.run(
                    f'fn main() uses io {{\n    print({n})\n}}\n',
                    args=[str(n)])
                if got.output.strip() != str(n):
                    wrong.append((n, got.output))
        crowd = [threading.Thread(target=hammer, args=(n,))
                 for n in range(many)]
        for t in crowd:
            t.start()
        for t in crowd:
            t.join(timeout=300)
        ok("...and under 72 calls from 24 threads, never a mixed-up "
           "answer", not wrong, str(wrong[:3]))
        ok("a pool of 4 never held more than 4 workers at a time",
           len(busy.worker_pids()) <= 4, str(busy.worker_pids()))

    print()
    print("nothing mutable is left unreset")
    print("-" * 62)

    # The reset is only as good as its list. Read this file's own
    # module-level assignments and insist every mutable one is either
    # reset between programs or a constant nothing writes to.
    source = (HERE / "velaris.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    CONSTANTS = {"KEYWORDS", "TOKEN_SPEC", "ESCAPES", "FALLIBLE_BUILTINS",
                 "BUILTINS", "KNOWN_TYPES", "FLIP", "BUILTIN_EFFECTS",
                 "UNARY_BEFORE", "UNARY_KEYWORDS", "MUTABLE_GLOBALS",
                 "_PCT_DECODE", "ERROR_TABLE", "_EFFECT_WORDS",
                 # the currency table: written once here, never by a
                 # program, so two runs cannot disagree about a currency
                 "CURRENCIES",
                 # deps-diff's table of lockfile names (7.1), read only
                 "_LOCKFILES"}
    makers = {"dict", "list", "set", "defaultdict", "deque", "Counter",
              "OrderedDict"}
    found = set()
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target])
        names = [t.id for t in targets if isinstance(t, ast.Name)]
        value = node.value
        if not names or value is None:
            continue
        mutable = isinstance(value, (ast.List, ast.Dict, ast.Set,
                                     ast.ListComp, ast.DictComp,
                                     ast.SetComp))
        if isinstance(value, ast.Call):
            called = getattr(value.func, "id",
                             getattr(value.func, "attr", ""))
            mutable = mutable or called in makers
        if mutable:
            found.update(names)
    # the budget's four are assigned None here and replaced through
    # globals() by Budget.install, so no literal names them
    found.update({"FFI_MODULES", "FS_GRANTS", "NET_GRANTS"})
    unaccounted = sorted(found - set(velaris.MUTABLE_GLOBALS) - CONSTANTS)
    ok("every module-level mutable in velaris.py is reset or a listed "
       "constant", not unaccounted,
       f"not accounted for: {unaccounted}")

    written = []
    for name in sorted(CONSTANTS - {"MUTABLE_GLOBALS"}):
        change = re.compile(
            rf"\b{name}\s*(?:\[[^\]]*\]\s*=[^=]|\.(?:append|extend|insert|"
            rf"update|clear|add|pop|discard|remove|setdefault|sort|"
            rf"__setitem__)\()")
        if change.search(source):
            written.append(name)
    ok("...and every name on the constant list really is never written to",
       not written, str(written))

    baseline = velaris.program_state_baseline()
    velaris.PROGRAM_ARGS[:] = ["left", "behind"]
    velaris.PY_OBJECTS[99] = object()
    velaris.PY_NEXT[0] = 99
    velaris.TRACE["on"] = True
    velaris._NATIVE_KEEPALIVE.append(object())
    velaris.Budget.parse("io,fs,net,ffi").install()
    velaris.reset_program_state(velaris.Budget.parse("io"), baseline)
    ok("reset_program_state empties every one of them",
       velaris.PROGRAM_ARGS == [] and not velaris.PY_OBJECTS
       and velaris.PY_NEXT == [1] and not velaris.TRACE["on"]
       and not velaris._NATIVE_KEEPALIVE
       and velaris.EFFECT_BUDGET == {"io"}
       and velaris.OP_COUNTS == {"fs": 0, "net": 0},
       f"{velaris.PROGRAM_ARGS} {list(velaris.PY_OBJECTS)} "
       f"{velaris.PY_NEXT} {sorted(velaris.EFFECT_BUDGET)}")
    velaris.Budget.parse(",".join(velaris.ALL_EFFECTS)).install()

    print()
    print("and it has to be faster")
    print("-" * 62)

    rounds = 200
    t0 = time.perf_counter()
    for _ in range(rounds):
        got = velaris.run(PRINTS, allow={"io"}, timeout=TIMEOUT,
                          max_memory_mb=MEMORY_MB)
        assert got.ok, got.as_dict()
    alone = time.perf_counter() - t0

    with velaris.Pool(size=1, allow={"io"}, timeout=TIMEOUT,
                      max_memory_mb=MEMORY_MB) as fast:
        fast.run(PRINTS)                  # start the worker, then measure
        t0 = time.perf_counter()
        for _ in range(rounds):
            got = fast.run(PRINTS)
            assert got.ok, got.as_dict()
        pooled = time.perf_counter() - t0

    print(f"  {rounds} bounded runs, one at a time")
    print(f"    a fresh process each time : {alone:8.2f} s   "
          f"({alone / rounds * 1000:7.1f} ms each)")
    print(f"    one pooled worker         : {pooled:8.2f} s   "
          f"({pooled / rounds * 1000:7.1f} ms each)")
    print(f"    the pool is {alone / pooled:.1f}x faster")
    ok(f"the pool is at least 3x faster over {rounds} sequential runs",
       pooled > 0 and alone / pooled >= 3.0,
       f"{alone:.2f}s vs {pooled:.2f}s")

    import shutil
    shutil.rmtree(box, ignore_errors=True)

    print("-" * 62)
    print(f"{passed} correct, {failed} wrong")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
