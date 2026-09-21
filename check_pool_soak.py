#!/usr/bin/env python3
"""sabline.Pool, soaked: thousands of runs, and nothing grows or leaks.

check_pool.py asserts each rule once. This runs them at volume, as a
platform running Sabline for a month would (item 15 of 8.2; the monthly
workflow runs it with --runs 5000):

- **Flat memory.** One worker runs the same small program --runs times;
  its resident memory is sampled every 100 runs, and after the first 500
  (the interpreter and the imports settling) it may not grow by more than
  --grow MB.
- **Kill mid-run.** Every 250 runs a worker running a program that never
  ends is killed from outside; the next run on that pool must succeed on a
  replacement, and the killed process must be gone.
- **Parallel pressure.** A pool of four serves sixteen threads, each running
  programs that print their own number; no answer may be another's.
- **Nothing leaks between runs.** Runs alternate between programs that
  leave state behind - an argument, a Python handle nobody closed, an
  environment variable and the working directory changed through ffi - and
  programs that look for it; none may find it.

    python check_pool_soak.py                 1,000 runs (a few minutes)
    python check_pool_soak.py --runs 5000     the monthly soak
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import cast

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sabline  # noqa: E402
from suite_dirs import isolate  # noqa: E402

WORK = isolate("check_pool_soak")
PASS = FAIL = 0

SMALL = 'fn main() uses io {\n    print(to_text(21 * 2))\n}\n'
FOREVER = ('fn main() uses io {\n    let i = 0\n    while i >= 0 {\n'
           '        i = i + 1\n        if i > 1000000 {\n            i = 0\n'
           '        }\n    }\n}\n')
LEAVES = ('fn main() uses io, ffi, env {\n'
          '    check py_new("io", "StringIO", "[\\"left behind\\"]") {\n'
          '        ok h { print("handle") }\n        fail w { print(w) }\n    }\n'
          '    check py("os", "putenv", ["SABLINE_SOAK_LEFT", "yes"]) {\n'
          '        ok v { print("env") }\n        fail w { print(w) }\n    }\n'
          '    check py("os", "chdir", [".."]) {\n'
          '        ok v { print("moved") }\n        fail w { print(w) }\n    }\n'
          '}\n')
LOOKS = ('fn main() uses io, ffi, env {\n'
         '    print(to_text(length(args())))\n'
         '    let none: List of Text = []\n'
         '    check py("os", "getcwd", none) {\n'
         '        ok v { print(v) }\n        fail w { print(w) }\n    }\n'
         '}\n')


def ok(label: str, good: bool, detail: str = "") -> None:
    global PASS, FAIL
    if good:
        PASS += 1
        print(f"  ok      {label}")
    else:
        FAIL += 1
        print(f"  BROKEN  {label}" + (f"\n          {detail}" if detail else ""))


def rss_mb(pid: int) -> float | None:
    """A process's resident memory in MB, or None where it cannot be read."""
    try:
        import psutil
        return psutil.Process(pid).memory_info().rss / 1048576
    except ImportError:
        pass
    except Exception:
        return None
    if sys.platform.startswith("linux"):
        try:
            for line in Path(f"/proc/{pid}/status").read_text().splitlines():
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
        except OSError:
            return None
    if sys.platform == "darwin":
        done = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                              capture_output=True, text=True)
        return int(done.stdout.strip()) / 1024 if done.stdout.strip() else None
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD),
                        ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
        psapi = ctypes.WinDLL("psapi", use_last_error=True)  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
        k32.OpenProcess.restype = wintypes.HANDLE
        handle = k32.OpenProcess(0x1000 | 0x0010, False, pid)
        if not handle:
            return None
        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        try:
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters),
                                          counters.cb):
                return cast(int, counters.WorkingSetSize) / 1048576
            return None
        finally:
            k32.CloseHandle(handle)
    return None


def kill(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                       capture_output=True)
    else:
        import signal
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def alive(pid: int) -> bool:
    import check_pool
    return check_pool.alive(pid)


def main(argv: list[str]) -> int:
    runs = int(argv[argv.index("--runs") + 1]) if "--runs" in argv else 1000
    grow = float(argv[argv.index("--grow") + 1]) if "--grow" in argv else 30.0
    started = time.monotonic()
    print(f"pool soak: {runs} runs")
    print("-" * 62)

    # ---- flat memory, with kills along the way ----------------------------
    samples: list[tuple[int, float]] = []
    wrong, killed, survivors = 0, 0, []
    with sabline.Pool(size=1, allow={"io"}, timeout=5) as pool:
        for n in range(1, runs + 1):
            if n % 250 == 0:
                victim: list[int] = []

                def watch() -> None:
                    for _ in range(200):
                        pids = pool.worker_pids()
                        if pids:
                            time.sleep(0.3)
                            victim.extend(pids)
                            kill(pids[0])
                            return
                        time.sleep(0.02)
                threading.Thread(target=watch, daemon=True).start()
                stopped = pool.run(FOREVER)
                killed += 1
                if stopped.ok:
                    wrong += 1
                survivors += [p for p in victim if alive(p)]
                continue
            got = pool.run(SMALL)
            if not (got.ok and got.output.strip() == "42"):
                wrong += 1
            if n % 100 == 0:
                pids = pool.worker_pids()
                mb = rss_mb(pids[0]) if pids else None
                if mb is not None:
                    samples.append((n, mb))
    ok(f"{runs} runs on one pool, {killed} of them killed from outside "
       f"mid-run: every other run answered, every killed run did not",
       wrong == 0, f"{wrong} wrong")
    time.sleep(1)
    ok("...and every killed worker is gone",
       not [p for p in survivors if alive(p)], str(survivors))
    settled = [mb for n, mb in samples if n > 500]
    if len(settled) >= 2:
        growth = max(settled) - settled[0]
        print(f"          worker memory after 500 runs {settled[0]:.1f} MB, "
              f"at most {max(settled):.1f} MB after {samples[-1][0]} runs")
        ok(f"...and a worker's memory stays flat after the first 500 runs "
           f"(grows under {grow:g} MB)", growth < grow,
           f"grew {growth:.1f} MB: {samples}")
    else:
        print("  skip    flat memory (too few runs, or memory unreadable here)")

    # ---- parallel pressure -------------------------------------------------
    mixed: list[tuple[int, str]] = []
    errors: list[str] = []
    each = max(20, runs // 50)
    with sabline.Pool(size=4, allow={"io"}, timeout=60) as busy:
        def caller(k: int) -> None:
            for _ in range(each):
                try:
                    got = busy.run(f'fn main() uses io {{\n    print({k})\n}}\n')
                    if got.output.strip() != str(k):
                        mixed.append((k, got.output))
                except Exception as e:           # noqa: BLE001 - reported
                    errors.append(f"{type(e).__name__}: {e}")
        threads = [threading.Thread(target=caller, args=(k,))
                   for k in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=1800)
        ok(f"a pool of four under sixteen threads, {16 * each} runs: no "
           f"answer is another caller's", not mixed and not errors,
           f"{mixed[:3]} {errors[:3]}")
        ok("...and it never held more than four workers",
           len(busy.worker_pids()) <= 4, str(busy.worker_pids()))

    # ---- nothing leaks between runs ----------------------------------------
    leaks: list[str] = []
    rounds = max(10, runs // 20)
    baseline_cwd = None
    with sabline.Pool(size=1, allow={"io", "ffi", "env"},
                      timeout=60) as reuse:
        for i in range(rounds):
            reuse.run(LEAVES, args=["one", "two", "three"])
            seen = reuse.run(LOOKS)
            lines = seen.output.strip().splitlines()
            if baseline_cwd is None and len(lines) == 2:
                baseline_cwd = lines[1]
            if not seen.ok or lines[:1] != ["0"] or (
                    baseline_cwd is not None and lines[1:] != [baseline_cwd]):
                leaks.append(f"round {i}: {seen.output!r}")
        handles = reuse.run('fn main() uses io, ffi {\n'
                            '    check py_new("io", "StringIO", "[\\"x\\"]") {\n'
                            '        ok h { print(h) }\n'
                            '        fail w { print(w) }\n    }\n}\n')
        ok(f"{rounds} rounds of a program leaving an argument, a handle, an "
           f"environment variable and a changed directory behind: the next "
           f"program found none of them", not leaks, "; ".join(leaks[:3]))
        # the first handle a program opens is #2, in a fresh process or a
        # reused worker alike (check_pool.py)
        ok("...and handle numbers start again for each program, however many "
           "were left open", handles.ok and "#2" in handles.output,
           handles.output)
    ok("the environment variable a program set through ffi is not in the "
       "parent either", "SABLINE_SOAK_LEFT" not in os.environ)

    print("-" * 62)
    print(f"{PASS} correct, {FAIL} wrong in "
          f"{time.monotonic() - started:.0f}s")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
