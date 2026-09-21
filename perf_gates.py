#!/usr/bin/env python3
"""How fast Sabline starts, checks, proves, compiles and runs, on this machine.

    python perf_gates.py                      # every measurement, a report on stdout
    python perf_gates.py --runs 3 --markdown  # a table to paste into a CHANGELOG entry
    python perf_gates.py --only cold,imports --json perf.json
    python perf_gates.py --against v8.1.1     # the pure-numeric gate

WHAT IS MEASURED, in the tree this file is in, under the Python running it:

  cold     The cold start of `sabline --version`, and of `sabline check` on a
           one-line file: a fresh process each time, one warm-up run first,
           then the median of --runs.
  check    Check time per 1,000 lines: a valid generated program of about
           1,000 and about 10,000 lines (records, loops, branches, lists,
           text and `%`; no contracts, though the prover still settles what
           the operations oblige, such as a divisor), checked in this process
           with sabline.check(timeout=None, max_memory_mb=None) - as `sabline
           check` does, and again with prove=False to show the checker alone;
           one warm-up check, then the median of --runs, in seconds per 1,000
           lines.
  proof    Proof time with z3: every examples/*.vel with a `requires` or
           `ensures` is checked in this process with sabline.check(...,
           timeout=None), after one warm-up check; each file's time is the
           median of --runs, and p50 and p95 (nearest rank) are taken over
           the files. Skipped, and said, when z3 is not installed.
  jit      JIT compile time against the gain, on examples/bench.vel: in a fresh
           process the program is loaded, checked and proved, and then
           llvmlite is imported and compile_native() timed; the run times
           are `sabline examples/bench.vel --time`, native and --no-native
           (the `[--time] ran in` figure: the program's run, not start-up,
           check or compile). The speed-up is interpreted / native, the gain
           their difference.
  lite     The size of a `--lite` build. The repository is searched for one;
           when none exists that is said, and nothing is measured.
  pool     Memory of a sabline.Pool(size=1) worker: its resident set after one
           warm-up run and after --pool-runs (1,000) more runs of a small
           program, read with psutil when it is installed, else with
           GetProcessMemoryInfo on Windows, /proc/PID/status on Linux, and
           `ps` elsewhere. The worker's whole process tree is added up: under
           a Windows virtual environment python.exe is a launcher, and the
           interpreter doing the work is its child.
  imports  Lazy imports: `python -X importtime sabline.py --version`, and
           `check` of a file with no contracts (with PYTHONPROFILEIMPORTTIME
           set as well, so the check's ceiling child reports its imports),
           must import neither z3 nor llvmlite. What importing each costs:
           the cumulative -X importtime figure, and the cold start of
           `python -c "import z3"` and of llvmlite against `python -c pass`.
  numeric  Pure-numeric performance: examples/bench.vel and a generated loop of
           integer arithmetic, each native and --no-native, as the `[--time]
           ran in` figure; median of --runs after a warm-up. Which functions
           of each program the working tree compiles to native code is
           reported beside it: in bench.vel only `burn` is (a recursive
           function such as `fib` is not), so its native time is part
           interpreted.

--against REF checks the ref out (git worktree, removed afterwards) and runs
the numeric measurement there too, on the same two program files, under the
same Python, interleaved: in every round each program and engine runs in the
working tree and then at REF, so both see the same load. For each engine the
two programs' medians are added up, and when the working tree's total is more
than SLOWER_LIMIT (25%) above REF's the exit status is 1. Each median is of
--runs runs, and --against refuses fewer than GATE_RUNS (3): one run a side
would compare one noisy sample with another.

NOISE. These are wall-clock figures on a shared machine. Medians after a
warm-up remove some of the noise and none of the bias of a busy machine; the
report says how busy the machine was when it began. Take the numbers that go
into a CHANGELOG on a quiet machine.

EXIT: 0, or 1 when --against finds an engine more than 25% slower, or 2 when
the measurement could not be made (a ref that cannot be checked out, a
workload that did not run).
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from suite_dirs import isolate  # noqa: E402

MEASURES = ("cold", "check", "proof", "jit", "lite", "pool", "imports",
            "numeric")
SLOWER_LIMIT = 0.25            # --against fails past +25% on either engine
GATE_RUNS = 3                  # --against: the median of at least 3 runs a side
PROCESS_TIMEOUT = 1800
POOL_RUNS = 1000
CHECK_SIZES = (1000, 10000)
ENGINES = ("native", "interpreted")
TIME_LINE = re.compile(r"\[--time\] ran in ([\d.]+) ms")
INT_LOOP_N = 300000

ONE_LINE = 'fn main() uses io { print("hi") }\n'

INT_LOOP = """\
// perf_gates.py: a loop of integer arithmetic. Pure Int, no effects, and no
// `%`: a function using `%` is not compiled to native code (8.1.1 and 8.2).
fn spin(n: Int) -> Int {
    let total = 0
    let i = 0
    while i < n {
        total = total + i * 7 - i
        if total > 1000003 {
            total = total - 1000003
        }
        i = i + 1
    }
    return total
}

fn main() uses io {
    print("spin(@N) = " + spin(@N))
}
"""

POOL_PROGRAM = """\
fn main() uses io {
    let total = 0
    let i = 0
    while i < 200 {
        total = total + i * i
        i = i + 1
    }
    print(total)
}
"""

UNIT = """\
record R@K {
    a: Int
    b: Int
}

fn f@K_mix(x: Int, y: Int) -> Int {
    let total = 0
    let i = 0
    while i < 10 {
        if (x + i) % 3 == 0 {
            total = total + x * i
        } else {
            total = total - y + i
        }
        i = i + 1
    }
    return total
}

fn f@K_swap(p: R@K) -> R@K {
    return R@K(a: p.b, b: p.a + 1)
}

fn f@K_show(xs: List of Int) -> Text {
    let out = "n="
    for v in xs {
        out = out + v + ","
    }
    return out
}

fn f@K_use(n: Int) -> Text {
    let p = f@K_swap(R@K(a: n, b: f@K_mix(n, 2)))
    return f@K_show([p.a, p.b, n])
}
"""

JIT_HELPER = """\
import json, sys, time
root, path = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
import sabline
funcs, records = sabline.load_program(path)
errors = []
sabline.check_effects(funcs, errors)
if not errors:
    sabline.check_types(funcs, records, errors)
proven = set()
if not errors:
    sabline.check_proofs(funcs, records, errors, proven)
t0 = time.perf_counter()
try:
    import llvmlite.ir, llvmlite.binding
    have = True
except ImportError:
    have = False
t1 = time.perf_counter()
native = sabline.compile_native(funcs, proven) if have and not errors else {}
t2 = time.perf_counter()
print(json.dumps({"errors": [str(e) for e in errors], "llvmlite": have,
                  "import_s": t1 - t0, "compile_s": t2 - t1,
                  "compiled": sorted(native)}))
"""


class CannotMeasure(Exception):
    """A measurement that could not be made: exit 2."""


def say(text: str = "", err: bool = True) -> None:
    text = text.encode("ascii", "backslashreplace").decode("ascii")
    print(text, file=sys.stderr if err else sys.stdout, flush=True)


def fmt_s(seconds: Any) -> str:
    if seconds is None:
        return "-"
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    return f"{seconds:.2f} s"


def fmt_mb(n: Any) -> str:
    return "-" if n is None else f"{n / (1024 * 1024):.1f} MB"


def summary(values: list[Any]) -> dict[str, Any]:
    return {"median": statistics.median(values), "min": min(values),
            "max": max(values), "runs": len(values)}


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    rank = max(1, -(-len(ordered) * p // 100))     # nearest rank, ceil
    return ordered[int(rank) - 1]


def child_env(**more: Any) -> dict[Any, Any]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.update(PYTHONIOENCODING="utf-8", NO_COLOR="1")
    env.update(more)
    return env


def run_once(cmd: list[Any], cwd: Path, env: Any = None) -> tuple[Any, ...]:
    """(seconds, CompletedProcess) for one fresh process."""
    began = time.perf_counter()
    try:
        done = subprocess.run(cmd, cwd=str(cwd), capture_output=True,
                              env=env or child_env(), timeout=PROCESS_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise CannotMeasure(f"{' '.join(map(str, cmd))} did not finish: {e}")
    return time.perf_counter() - began, done


def must_succeed(done: Any, cmd: Any) -> None:
    if done.returncode != 0:
        said = done.stderr.decode("utf-8", "replace").strip().splitlines()
        raise CannotMeasure(f"{' '.join(map(str, cmd))} exited "
                            f"{done.returncode}: "
                            + " | ".join(said[-4:]))


def timed_processes(cmd: list[Any], cwd: Path, runs: int, env: Any = None) -> dict[Any, Any]:
    """One warm-up, then `runs` fresh processes; their wall times."""
    run_once(cmd, cwd, env)
    times = []
    for _ in range(runs):
        seconds, done = run_once(cmd, cwd, env)
        must_succeed(done, cmd)
        times.append(seconds)
    return summary(times)


def machine_load() -> str:
    cpus = os.cpu_count() or 0
    try:
        one = os.getloadavg()[0]
        return f"load average {one:.2f} over 1 minute, {cpus} CPUs"
    except (AttributeError, OSError):
        pass
    try:
        import psutil
        return (f"CPU {psutil.cpu_percent(interval=1.0):.0f}% busy over 1 s "
                f"before measuring, {cpus} CPUs")
    except ImportError:
        pass
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            def sample() -> list[Any]:
                idle, kernel, user = (wintypes.FILETIME(), wintypes.FILETIME(),
                                      wintypes.FILETIME())
                ctypes.windll.kernel32.GetSystemTimes(  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
                    ctypes.byref(idle), ctypes.byref(kernel),
                    ctypes.byref(user))
                return [(t.dwHighDateTime << 32) | t.dwLowDateTime
                        for t in (idle, kernel, user)]
            a = sample()
            time.sleep(1.0)
            b = sample()
            idle, total = b[0] - a[0], (b[1] - a[1]) + (b[2] - a[2])
            if total > 0:
                return (f"CPU {100 * (1 - idle / total):.0f}% busy over 1 s "
                        f"before measuring, {cpus} CPUs")
        except Exception:
            pass
    return f"unknown ({cpus} CPUs)"


# ------------------------------------------------------------ the tree

# The launcher a tree starts from. It was velaris.py until 8.6 renamed the
# project, and --against checks out a tag that may well predate that, so
# both names are looked for - the current one first. Delete the old one in
# 9.0, once no tag this measures against is older than 8.6.
LAUNCHERS = ("sabline.py", "velaris.py")


class Sabline:
    """A tree of Sabline to start as `python sabline.py` - or velaris.py,
    in a tree from before the 8.6 rename."""

    def __init__(self, root: Path, label: str) -> None:
        self.root, self.label = Path(root), label
        found = next((self.root / n for n in LAUNCHERS
                      if (self.root / n).is_file()), None)
        if found is None:
            raise CannotMeasure(
                f"{label} has none of {', '.join(LAUNCHERS)}")
        self.script = found

    def cmd(self, *args: Any) -> list[Any]:
        return [sys.executable, str(self.script)] + [str(a) for a in args]

    def run_ms(self, program: Path, engine: str, cwd: Path) -> float:
        cmd = self.cmd(program, "--time") + (
            ["--no-native"] if engine == "interpreted" else [])
        _, done = run_once(cmd, cwd)
        must_succeed(done, cmd)
        m = TIME_LINE.search(done.stderr.decode("utf-8", "replace"))
        if not m:
            raise CannotMeasure(f"{' '.join(cmd)} printed no '[--time] ran "
                                f"in' line")
        return float(m.group(1))


def import_sabline() -> Any:
    import sabline
    if Path(sabline.__file__).resolve().parent.parent != HERE:
        raise CannotMeasure(f"import sabline found {sabline.__file__}, not "
                            f"this tree")
    return sabline


# --------------------------------------------------------- measurements

def measure_cold(tree: Sabline, work: Path, runs: int) -> dict[str, Any]:
    one = work / "one_line.vel"
    one.write_text(ONE_LINE, encoding="utf-8")
    version = timed_processes(tree.cmd("--version"), work, runs)
    check = timed_processes(tree.cmd("check", one), work, runs)
    say(f"cold start: --version {fmt_s(version['median'])}, check of a "
        f"one-line file {fmt_s(check['median'])}")
    return {"version": version, "check_one_line": check}


def generate_program(lines: int) -> str:
    out = ["// perf_gates.py: generated for check timing. No contracts.", ""]
    k = 0
    while len(out) < lines - 4:
        out += UNIT.replace("@K", str(k)).splitlines() + [""]
        k += 1
    out += ["fn main() uses io {",
            f"    print(f0_use(1) + f{k - 1}_use(2))", "}"]
    return "\n".join(out) + "\n"


def measure_check(work: Path, runs: int) -> dict[Any, Any]:
    sabline = import_sabline()
    rows = {}
    programs = {}
    for size in CHECK_SIZES:
        path = work / f"generated_{size}.vel"
        source = generate_program(size)
        path.write_text(source, encoding="utf-8")
        programs[size] = (path, source, source.count("\n"))
    path, source, _ = programs[CHECK_SIZES[0]]
    warm = sabline.check(source, path=str(path), timeout=None,
                         max_memory_mb=None)
    for size, (path, source, count) in programs.items():
        times: dict[bool, list[float]] = {True: [], False: []}
        for _ in range(runs):
            for prove in (True, False):
                began = time.perf_counter()
                result = sabline.check(source, path=str(path), prove=prove,
                                       timeout=None, max_memory_mb=None)
                times[prove].append(time.perf_counter() - began)
                if not result.ok:
                    first = result.problems[0] if result.problems else None
                    raise CannotMeasure(
                        f"the generated {count}-line program does not "
                        f"check: " + (f"{first.code} line {first.line}: "
                                      f"{first.message}"
                                      if first else "no problem given"))
        s = summary(times[True])
        alone = summary(times[False])
        s.update(lines=count, per_1000_lines=s["median"] * 1000 / count,
                 without_proofs=alone,
                 per_1000_lines_without_proofs=alone["median"] * 1000 / count)
        rows[str(size)] = s
        say(f"check: {count} lines in {fmt_s(s['median'])}, "
            f"{s['per_1000_lines']:.3f} s per 1,000 lines "
            f"({s['per_1000_lines_without_proofs']:.3f} s with prove=False)")
    del warm
    return rows


CONTRACT = re.compile(r"^\s*(requires|ensures)\b", re.M)
FN_HEADER = re.compile(r"^\s*fn\s+\w+", re.M)


def contracted_functions(source: str) -> int:
    """Functions whose header is followed by requires/ensures before the
    body opens: a label for the report, not what is timed."""
    count = 0
    for m in FN_HEADER.finditer(source):
        rest = source[m.end():]
        body = rest.find("{")
        if body >= 0 and CONTRACT.search(rest[:body]):
            count += 1
    return count


def measure_proof(runs: int) -> dict[Any, Any]:
    sabline = import_sabline()
    if not sabline.HAVE_Z3:
        say("proof: skipped, z3 is not installed under this Python")
        return {"skipped": "z3 is not installed"}
    files = sorted(p for p in (HERE / "examples").glob("*.vel")
                   if CONTRACT.search(p.read_text(encoding="utf-8")))
    if not files:
        return {"skipped": "no example has a contract"}
    first = files[0]
    sabline.check(first.read_text(encoding="utf-8"), path=str(first),
                  timeout=None, max_memory_mb=None)
    per_file: dict[str, list[float]] = {}
    for _ in range(runs):
        for path in files:
            source = path.read_text(encoding="utf-8")
            began = time.perf_counter()
            sabline.check(source, path=str(path), timeout=None,
                          max_memory_mb=None)
            per_file.setdefault(path.name, []).append(
                time.perf_counter() - began)
    medians = {name: statistics.median(t) for name, t in per_file.items()}
    values = list(medians.values())
    out: dict[str, Any]
    out = {"files": len(files),
           "functions_with_contracts": sum(
               contracted_functions(p.read_text(encoding="utf-8"))
               for p in files),
           "p50": percentile(values, 50), "p95": percentile(values, 95),
           "slowest": sorted(medians.items(), key=lambda kv: -kv[1])[:3],
           "per_file": medians, "runs": runs}
    say(f"proof: {len(files)} example files with contracts, p50 "
        f"{fmt_s(out['p50'])}, p95 {fmt_s(out['p95'])}; slowest "
        + ", ".join(f"{n} {fmt_s(s)}" for n, s in out["slowest"]))
    return out


def compile_once(tree: Sabline, program: Path, work: Path) -> dict[Any, Any]:
    """Load, check and prove `program` in a fresh process, then import
    llvmlite and compile it: the helper's report."""
    cmd = [sys.executable, "-c", JIT_HELPER, str(tree.root), str(program)]
    _, done = run_once(cmd, work)
    must_succeed(done, cmd)
    try:
        got: dict[Any, Any] = json.loads(
            done.stdout.decode("utf-8").strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise CannotMeasure(f"the compile helper said nothing readable: "
                            f"{done.stderr.decode('utf-8', 'replace')}")
    if got["errors"]:
        raise CannotMeasure(f"{program.name} does not check: "
                            f"{got['errors'][0]}")
    return got


def jit_compile(tree: Sabline, program: Path, work: Path, runs: int) -> dict[str, Any]:
    compile_once(tree, program, work)                  # the warm-up
    samples = [compile_once(tree, program, work) for _ in range(runs)]
    return {"llvmlite": samples[-1]["llvmlite"],
            "compiled": samples[-1]["compiled"],
            "llvmlite_import": summary([s["import_s"] for s in samples]),
            "compile": summary([s["compile_s"] for s in samples])}


def numeric_programs(work: Path) -> dict[str, Any]:
    bench = work / "bench.vel"
    shutil.copyfile(HERE / "examples" / "bench.vel", bench)
    loop = work / "int_loop.vel"
    loop.write_text(INT_LOOP.replace("@N", str(INT_LOOP_N)), encoding="utf-8")
    return {"examples/bench.vel": bench, "integer loop": loop}


def measure_numeric(trees: list[Any], work: Path, runs: int) -> dict[str, Any]:
    """{workload: {engine: {tree label: summary of ms}}}, interleaved: each
    round runs every workload and engine in each tree, in that order."""
    programs = numeric_programs(work)
    native_functions = {w: compile_once(trees[0], p, work)["compiled"]
                        for w, p in programs.items()}
    for workload, names in native_functions.items():
        say(f"numeric: {workload} compiles "
            + (", ".join(names) if names else "nothing")
            + " to native code in the working tree")
    times: dict[str, dict[str, dict[str, list[float]]]]
    times = {w: {e: {t.label: [] for t in trees} for e in ENGINES}
             for w in programs}
    for rnd in range(runs + 1):
        for workload, path in programs.items():
            for engine in ENGINES:
                for tree in trees:
                    ms = tree.run_ms(path, engine, work)
                    if rnd:                  # round 0 is the warm-up
                        times[workload][engine][tree.label].append(ms)
        if rnd:
            say(f"numeric: round {rnd} of {runs} done")
    out = {w: {e: {label: summary(v) for label, v in by_tree.items()}
               for e, by_tree in engines.items()}
           for w, engines in times.items()}
    for workload, engines in out.items():
        for engine, by_tree in engines.items():
            say(f"numeric: {workload}, {engine}: " + ", ".join(
                f"{label} {s['median']:.0f} ms" for label, s in by_tree.items()))
    return {"programs": {w: str(p.name) for w, p in programs.items()},
            "int_loop_n": INT_LOOP_N, "native_functions": native_functions,
            "ms": out}


def measure_jit(tree: Sabline, work: Path, runs: int, numeric: Any) -> dict[Any, Any]:
    bench = work / "bench.vel"
    if not bench.exists():
        numeric_programs(work)
    compiled = jit_compile(tree, bench, work, runs)
    if numeric:
        ms = {e: numeric["ms"]["examples/bench.vel"][e][tree.label]["median"]
              for e in ENGINES}
    else:
        ms = {e: statistics.median([tree.run_ms(bench, e, work)
                                    for _ in range(runs)])
              for e in ENGINES}
    cost = (compiled["compile"]["median"]
            + compiled["llvmlite_import"]["median"])
    gain = (ms["interpreted"] - ms["native"]) / 1000
    out = dict(compiled, native_ms=ms["native"],
               interpreted_ms=ms["interpreted"],
               speedup=(ms["interpreted"] / ms["native"]
                        if ms["native"] else None),
               gain_s=gain, compile_and_import_s=cost,
               pays_back=gain > cost)
    if not compiled["llvmlite"]:
        say("jit: llvmlite is not installed; both runs were interpreted")
    say(f"jit: bench.vel compiled {compiled['compiled'] or 'nothing'} in "
        f"{fmt_s(compiled['compile']['median'])} (+ llvmlite import "
        f"{fmt_s(compiled['llvmlite_import']['median'])}); run native "
        f"{ms['native']:.0f} ms, interpreted {ms['interpreted']:.0f} ms"
        + (f", {out['speedup']:.2f}x" if out["speedup"] else ""))
    return out


LITE_WORD = re.compile(r"(?i)(?<![\w-])--lite\b|(?<![\w-])lite(?![\w-])"
                       r"|sabline[-_]lite")
LITE_NAME = re.compile(r"(?i)(^|[-_.])lite([-_.]|$)")
TEXT_SUFFIXES = {".py", ".md", ".toml", ".yml", ".yaml", ".json", ".js",
                 ".cfg", ".txt", ".sh", ".ps1", ".in", ".ini", ".spec", ""}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv",
             ".mypy_cache", ".pytest_cache"}


def measure_lite() -> dict[str, Any]:
    mentions, artefacts, searched = [], [], 0
    me = Path(__file__).resolve()
    for folder, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files + dirs:
            if LITE_NAME.search(Path(name).stem if name in files else name):
                artefacts.append(Path(folder, name))
        for name in files:
            path = Path(folder, name)
            if path.resolve() == me or path.suffix.lower() not in \
                    TEXT_SUFFIXES and name != "Dockerfile":
                continue
            try:
                if path.stat().st_size > 5 * 1024 * 1024:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            searched += 1
            for i, line in enumerate(text.splitlines(), 1):
                if LITE_WORD.search(line):
                    mentions.append(f"{path.relative_to(HERE).as_posix()}:"
                                    f"{i}: {line.strip()[:100]}")
    if not mentions and not artefacts:
        say(f"lite: no --lite build exists in this repository ({searched} "
            f"text files searched); nothing measured")
        return {"exists": False, "searched_files": searched,
                "said": "no --lite build exists in this repository"}
    sizes = {}
    for path in artefacts:
        if path.is_file():
            sizes[path.relative_to(HERE).as_posix()] = path.stat().st_size
        elif path.is_dir():
            sizes[path.relative_to(HERE).as_posix() + "/"] = sum(
                f.stat().st_size for f in path.rglob("*") if f.is_file())
    said = ("a --lite build is mentioned; " + (
        "sizes of what is named lite: " + ", ".join(
            f"{k} {fmt_mb(v)}" for k, v in sizes.items())
        if sizes else "no artefact named lite was found to measure"))
    say(f"lite: {said}")
    for m in mentions[:10]:
        say(f"  {m}")
    return {"exists": bool(sizes), "mentions": mentions[:50],
            "sizes": sizes, "said": said, "searched_files": searched}


def process_memory(pid: int) -> dict[str, Any]:
    """{'rss': bytes, 'peak': bytes or None, 'how': str} of a process."""
    try:
        import psutil
        info = psutil.Process(pid).memory_info()
        return {"rss": info.rss, "peak": getattr(info, "peak_wset", None),
                "how": "psutil"}
    except ImportError:
        pass
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class COUNTERS(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD),
                        ("PageFaultCount", wintypes.DWORD)] + [
                (n, ctypes.c_size_t) for n in (
                    "PeakWorkingSetSize", "WorkingSetSize",
                    "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
                    "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                    "PagefileUsage", "PeakPagefileUsage")]

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL,
                                    wintypes.DWORD)
        k32.K32GetProcessMemoryInfo.argtypes = (
            wintypes.HANDLE, ctypes.POINTER(COUNTERS), wintypes.DWORD)
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = k32.OpenProcess(0x1000 | 0x0010, False, pid)
        if not handle:
            raise CannotMeasure(f"OpenProcess({pid}) failed: "
                                f"{ctypes.get_last_error()}")  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
        try:
            c = COUNTERS()
            c.cb = ctypes.sizeof(COUNTERS)
            if not k32.K32GetProcessMemoryInfo(handle, ctypes.byref(c), c.cb):
                raise CannotMeasure(f"GetProcessMemoryInfo({pid}) failed: "
                                    f"{ctypes.get_last_error()}")  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
            return {"rss": c.WorkingSetSize, "peak": c.PeakWorkingSetSize,
                    "how": "GetProcessMemoryInfo (working set)"}
        finally:
            k32.CloseHandle(handle)
    status = Path(f"/proc/{pid}/status")
    if status.exists():
        fields = {}
        for line in status.read_text().splitlines():
            key, _, value = line.partition(":")
            if key in ("VmRSS", "VmHWM"):
                fields[key] = int(value.split()[0]) * 1024
        return {"rss": fields.get("VmRSS"), "peak": fields.get("VmHWM"),
                "how": "/proc/PID/status"}
    done = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                          capture_output=True, text=True)
    return {"rss": int(done.stdout.strip()) * 1024, "peak": None, "how": "ps"}


def descendants(pid: int) -> list[Any]:
    """The process ids below `pid`, children first."""
    try:
        import psutil
        return [c.pid for c in psutil.Process(pid).children(recursive=True)]
    except ImportError:
        pass
    pairs = []                                   # (pid, parent pid)
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class ENTRY(ctypes.Structure):
            _fields_ = [("dwSize", wintypes.DWORD),
                        ("cntUsage", wintypes.DWORD),
                        ("th32ProcessID", wintypes.DWORD),
                        ("th32DefaultHeapID", ctypes.c_size_t),
                        ("th32ModuleID", wintypes.DWORD),
                        ("cntThreads", wintypes.DWORD),
                        ("th32ParentProcessID", wintypes.DWORD),
                        ("pcPriClassBase", wintypes.LONG),
                        ("dwFlags", wintypes.DWORD),
                        ("szExeFile", wintypes.WCHAR * 260)]

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
        k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        k32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD,
                                                 wintypes.DWORD)
        k32.Process32FirstW.argtypes = (wintypes.HANDLE,
                                        ctypes.POINTER(ENTRY))
        k32.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(ENTRY))
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        snap = k32.CreateToolhelp32Snapshot(0x2, 0)   # TH32CS_SNAPPROCESS
        if snap in (None, ctypes.c_void_p(-1).value):
            return []
        try:
            entry = ENTRY()
            entry.dwSize = ctypes.sizeof(ENTRY)
            more = k32.Process32FirstW(snap, ctypes.byref(entry))
            while more:
                pairs.append((entry.th32ProcessID,
                              entry.th32ParentProcessID))
                more = k32.Process32NextW(snap, ctypes.byref(entry))
        finally:
            k32.CloseHandle(snap)
    elif Path("/proc").is_dir():
        for d in Path("/proc").iterdir():
            if d.name.isdigit():
                try:
                    stat = (d / "stat").read_text()
                    pairs.append((int(d.name),
                                  int(stat.rsplit(")", 1)[1].split()[1])))
                except (OSError, IndexError, ValueError):
                    pass
    else:
        done = subprocess.run(["ps", "-A", "-o", "pid=,ppid="],
                              capture_output=True, text=True)
        for line in done.stdout.splitlines():
            parts = line.split()
            if len(parts) == 2:
                pairs.append((int(parts[0]), int(parts[1])))
    found, frontier = [], [pid]
    while frontier:
        parent = frontier.pop(0)
        kids = [p for p, pp in pairs if pp == parent and p != parent
                and p not in found]
        found += kids
        frontier += kids
    return found


def tree_memory(pid: int) -> dict[str, Any]:
    """The resident set of `pid` and everything below it, added up."""
    pids = [pid] + descendants(pid)
    parts = []
    for p in pids:
        try:
            parts.append(process_memory(p))
        except Exception:
            continue          # a process that ended between the two reads
    return {"rss": sum(m["rss"] or 0 for m in parts),
            "processes": len(parts),
            "how": parts[0]["how"] if parts else "unread"}


def measure_pool(runs: int) -> dict[Any, Any]:
    sabline = import_sabline()
    with sabline.Pool(size=1) as pool:
        first = pool.run(POOL_PROGRAM)
        if not first.ok:
            raise CannotMeasure(f"the pool's program did not run: "
                                f"{[p.code for p in first.problems]}")
        pids = pool.worker_pids()
        before = tree_memory(pids[0])
        times, failed = [], 0
        for _ in range(runs):
            began = time.perf_counter()
            result = pool.run(POOL_PROGRAM)
            times.append(time.perf_counter() - began)
            failed += not result.ok
        after_pids = pool.worker_pids()
        after = tree_memory(after_pids[0])
        started = pool.started
    same = after_pids == pids and started == 1
    out = {"runs": runs, "failed_runs": failed, "same_worker": same,
           "workers_started": started, "rss_before": before["rss"],
           "rss_after": after["rss"], "processes": after["processes"],
           "growth": after["rss"] - before["rss"], "how": before["how"],
           "per_run": summary(times)}
    say(f"pool: worker RSS {fmt_mb(before['rss'])} after 1 run, "
        f"{fmt_mb(after['rss'])} after {runs} more ({before['how']}, "
        f"{after['processes']} process(es) in the worker's tree); "
        f"{'one worker throughout' if same else f'{started} workers started'}"
        f", {failed} failed run(s), {fmt_s(out['per_run']['median'])} a run")
    return out


IMPORT_LINE = re.compile(r"^import time:\s+(\d+)\s*\|\s*(\d+)\s*\|( *)(\S+)")


def imported(stderr: bytes) -> list[Any]:
    """[(depth, module, cumulative microseconds)] from -X importtime."""
    rows = []
    for line in stderr.decode("utf-8", "replace").splitlines():
        m = IMPORT_LINE.match(line)
        if m:
            rows.append(((len(m.group(3)) - 1) // 2, m.group(4),
                         int(m.group(2))))
    return rows


def roots(rows: list[Any], names: Any = ("z3", "llvmlite")) -> list[Any]:
    return sorted({mod.split(".")[0] for _, mod, _ in rows
                   if mod.split(".")[0] in names})


def measure_imports(tree: Sabline, work: Path, runs: int) -> dict[Any, Any]:
    one = work / "one_line.vel"
    one.write_text(ONE_LINE, encoding="utf-8")
    env = child_env(PYTHONPROFILEIMPORTTIME="1")
    out: dict[str, dict[str, Any]] = {"lazy": {}, "cost": {}}
    for label, args in (("--version", ["--version"]),
                        ("check, no contracts", ["check", str(one)])):
        cmd = [sys.executable, "-X", "importtime", str(tree.script)] + args
        _, done = run_once(cmd, work, env)
        must_succeed(done, cmd)
        rows = imported(done.stderr)
        heavy = roots(rows)
        out["lazy"][label] = {"imports": heavy, "modules_seen": len(rows),
                              "ok": not heavy and bool(rows)}
        say(f"imports: {label} imports "
            + (", ".join(heavy) if heavy else "neither z3 nor llvmlite")
            + f" ({len(rows)} modules seen)")
    baseline = timed_processes([sys.executable, "-c", "pass"], work, runs)
    out["cost"]["python -c pass"] = {"cold_start": baseline}
    for name, stmt in (("z3", "import z3"),
                       ("llvmlite", "import llvmlite.ir, llvmlite.binding")):
        cmd = [sys.executable, "-c", stmt]
        _, done = run_once(cmd, work)
        if done.returncode != 0:
            out["cost"][name] = {"installed": False}
            say(f"imports: {name} is not installed under this Python")
            continue
        cold = timed_processes(cmd, work, runs)
        cumulative = []
        for _ in range(min(runs, 3)):
            _, done = run_once([sys.executable, "-X", "importtime", "-c",
                                stmt], work)
            cumulative.append(sum(us for depth, mod, us in imported(
                done.stderr) if depth == 0 and mod.split(".")[0] == name)
                / 1e6)
        out["cost"][name] = {
            "installed": True, "cold_start": cold,
            "adds_s": cold["median"] - baseline["median"],
            "importtime_s": statistics.median(cumulative)}
        say(f"imports: importing {name} adds "
            f"{fmt_s(out['cost'][name]['adds_s'])} to a cold start "
            f"(importtime {fmt_s(out['cost'][name]['importtime_s'])})")
    return out


# ------------------------------------------------------------- reporting

def gate(numeric: dict[Any, Any], new_label: str, ref_label: str) -> dict[Any, Any]:
    verdicts = {}
    for engine in ENGINES:
        new = sum(numeric["ms"][w][engine][new_label]["median"]
                  for w in numeric["ms"])
        ref = sum(numeric["ms"][w][engine][ref_label]["median"]
                  for w in numeric["ms"])
        change = new / ref - 1 if ref else 0.0
        verdicts[engine] = {"new_ms": new, "ref_ms": ref, "change": change,
                            "limit": SLOWER_LIMIT,
                            "ok": change <= SLOWER_LIMIT}
    return verdicts


def result_rows(report: dict[Any, Any]) -> list[Any]:
    """[(measure, result)] for the table and the plain summary."""
    meta = report["meta"]
    rows = []
    r = report.get("cold")
    if r:
        rows.append(("Cold start, `sabline --version`",
                     fmt_s(r["version"]["median"])))
        rows.append(("Cold start, `sabline check` of a one-line file",
                     fmt_s(r["check_one_line"]["median"])))
    r = report.get("check")
    if r:
        for s in r.values():
            rows.append((f"Check, {s['lines']:,}-line program",
                         f"{s['per_1000_lines']:.3f} s per 1,000 lines "
                         f"({fmt_s(s['median'])} in all; "
                         f"{s['per_1000_lines_without_proofs']:.3f} s per "
                         f"1,000 without proofs)"))
    r = report.get("proof")
    if r:
        rows.append(("Proof time per example with contracts (z3), p50 / p95",
                     r.get("skipped") or
                     f"{fmt_s(r['p50'])} / {fmt_s(r['p95'])} over "
                     f"{r['files']} files"))
    r = report.get("jit")
    if r:
        rows.append(("JIT on `examples/bench.vel`: compile (+ llvmlite "
                     "import), functions compiled",
                     f"{fmt_s(r['compile']['median'])} "
                     f"(+ {fmt_s(r['llvmlite_import']['median'])}), "
                     + (", ".join(f"`{n}`" for n in r["compiled"])
                        or "none")))
        rows.append(("JIT on `examples/bench.vel`: native / `--no-native` "
                     "run",
                     f"{r['native_ms']:.0f} ms / {r['interpreted_ms']:.0f} "
                     f"ms, " + (f"{r['speedup']:.2f}x" if r["speedup"]
                                else "-")
                     + f", gain {fmt_s(r['gain_s'])}"))
    r = report.get("lite")
    if r:
        rows.append(("`--lite` build size", r["said"]))
    r = report.get("pool")
    if r:
        rows.append((f"Pool worker RSS, 1 run -> {r['runs']:,} more",
                     f"{fmt_mb(r['rss_before'])} -> {fmt_mb(r['rss_after'])}"
                     f" ({'+' if r['growth'] >= 0 else '-'}"
                     f"{fmt_mb(abs(r['growth']))})"
                     + ("" if r["same_worker"] else ", worker replaced")))
    r = report.get("imports")
    if r:
        lazy = r["lazy"]
        rows.append(("z3 / llvmlite imported by `--version`; by `check` "
                     "(no contracts)",
                     "; ".join((", ".join(v["imports"]) or "neither")
                               for v in lazy.values())))
        for name in ("z3", "llvmlite"):
            c = r["cost"].get(name, {})
            rows.append((f"Importing {name}: cold start added (importtime)",
                         f"+{fmt_s(c['adds_s'])} ({fmt_s(c['importtime_s'])})"
                         if c.get("installed") else "not installed"))
    r = report.get("numeric")
    if r:
        label = meta["tree"]
        for workload, engines in r["ms"].items():
            names = r.get("native_functions", {}).get(workload) or []
            rows.append((f"Pure numeric, {workload}: native / interpreted",
                         " / ".join(f"{engines[e][label]['median']:.0f} ms"
                                    for e in ENGINES)
                         + " (native code: "
                         + (", ".join(f"`{n}`" for n in names) or "none")
                         + ")"))
    g = report.get("gate")
    if g:
        for engine, v in g.items():
            rows.append((f"{engine.capitalize()} vs {meta['against']}, "
                         f"pure numeric",
                         f"{v['new_ms']:.0f} ms vs {v['ref_ms']:.0f} ms "
                         f"({v['change']:+.1%}, limit +{v['limit']:.0%}): "
                         + ("ok" if v["ok"] else "SLOWER")))
    return rows


def heading(report: dict[Any, Any]) -> str:
    meta = report["meta"]
    return (f"Measured by `perf_gates.py` on {meta['platform']}, Python "
            f"{meta['python']}, Sabline {meta['sabline']}: medians of "
            f"{meta['runs']} run(s) after one warm-up. Machine load when it "
            f"began: {meta['load']}. Wall-clock figures on a machine that "
            f"may carry other load are noisy.")


def markdown(report: dict[Any, Any]) -> str:
    lines = [heading(report), "", "| Measure | Result |", "|---|---|"]
    lines += [f"| {a} | {b} |" for a, b in result_rows(report)]
    return "\n".join(lines) + "\n"


def plain(report: dict[Any, Any]) -> str:
    rows = result_rows(report)
    width = max((len(a) for a, _ in rows), default=0)
    return "\n".join([heading(report), ""] + [
        f"{a.replace('`', ''):<{width}}  {b}" for a, b in rows]) + "\n"


def main(argv: Any = None) -> int:
    ap = argparse.ArgumentParser(
        description="Measure Sabline's start-up, check, proof, JIT, pool "
                    "memory, lazy imports and pure-numeric speed.")
    ap.add_argument("--runs", type=int, default=5,
                    help="timed runs of each measurement, after one warm-up "
                         "(default 5)")
    ap.add_argument("--pool-runs", type=int, default=POOL_RUNS,
                    help=f"runs on the pool worker (default {POOL_RUNS})")
    ap.add_argument("--only", help="comma-separated: " + ",".join(MEASURES))
    ap.add_argument("--against", metavar="REF",
                    help="also run the pure-numeric workload at REF; exit 1 "
                         f"when either engine is more than "
                         f"{SLOWER_LIMIT:.0%} slower here")
    ap.add_argument("--json", metavar="FILE", help="write the report here")
    ap.add_argument("--markdown", action="store_true",
                    help="print a table to paste into a CHANGELOG entry")
    args = ap.parse_args(argv)
    if args.runs < 1 or args.pool_runs < 1:
        ap.error("--runs and --pool-runs must be at least 1")
    if args.against and args.runs < GATE_RUNS:
        # one run a side is one noisy sample against another (8.2.1)
        ap.error(f"--against compares the median of at least {GATE_RUNS} "
                 f"runs on each side; --runs is {args.runs}")
    chosen = ([m.strip() for m in args.only.split(",") if m.strip()]
              if args.only else list(MEASURES))
    unknown = [m for m in chosen if m not in MEASURES]
    if unknown:
        ap.error(f"--only takes {', '.join(MEASURES)}; not {unknown}")
    if args.against and "numeric" not in chosen:
        chosen.append("numeric")

    work = isolate("perf_gates")
    from check_differential import CannotRun, Checkouts, tree_version
    checkouts = Checkouts(work)
    tree = Sabline(HERE, "working tree")
    report: dict[str, Any] = {"schema": "sabline.perf/1", "meta": {
        # the build number too: Python before 3.12 calls Windows 11 "10"
        "platform": f"{platform.system()} {platform.release()} "
                    f"({platform.version()}) {platform.machine()}",
        "python": platform.python_version(), "sabline": tree_version(HERE),
        "tree": tree.label, "runs": args.runs, "against": args.against,
        "slower_limit": SLOWER_LIMIT, "measures": chosen}}
    say(f"perf_gates: Sabline {report['meta']['sabline']} in {HERE}, Python "
        f"{report['meta']['python']}, {args.runs} run(s) after a warm-up")
    report["meta"]["load"] = machine_load()
    say(f"machine load: {report['meta']['load']}. These are wall-clock "
        f"figures; with other load on the machine they are noisy.")
    code = 0
    try:
        trees = [tree]
        if args.against:
            ref = checkouts.checkout(args.against, "against")
            trees.append(Sabline(ref.root, args.against))
            report["meta"]["against_commit"] = ref.commit
            report["meta"]["against_version"] = ref.version
        if "cold" in chosen:
            report["cold"] = measure_cold(tree, work, args.runs)
        if "imports" in chosen:
            report["imports"] = measure_imports(tree, work, args.runs)
        if "check" in chosen:
            report["check"] = measure_check(work, args.runs)
        if "proof" in chosen:
            report["proof"] = measure_proof(args.runs)
        if "lite" in chosen:
            report["lite"] = measure_lite()
        if "pool" in chosen:
            report["pool"] = measure_pool(args.pool_runs)
        if "numeric" in chosen:
            report["numeric"] = measure_numeric(trees, work, args.runs)
        if "jit" in chosen:
            report["jit"] = measure_jit(tree, work, args.runs,
                                        report.get("numeric"))
        if args.against:
            report["gate"] = gate(report["numeric"], tree.label,
                                  args.against)
            for engine, v in report["gate"].items():
                say(f"gate: pure numeric ({' + '.join(report['numeric']['ms'])}"
                    f"), {engine}: working tree {v['new_ms']:.0f} ms vs "
                    f"{args.against} {v['ref_ms']:.0f} ms, "
                    f"{v['change']:+.1%} (limit +{SLOWER_LIMIT:.0%}): "
                    + ("ok" if v["ok"] else "FAIL, slower past the limit"))
            if not all(v["ok"] for v in report["gate"].values()):
                code = 1
    except (CannotMeasure, CannotRun) as e:
        say(f"perf_gates: could not measure: {e}")
        report["error"] = str(e)
        code = 2
    finally:
        checkouts.remove()
    report["exit"] = code
    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(report, fh, indent=1)
            fh.write("\n")
    if code != 2:
        say(markdown(report) if args.markdown else plain(report), err=False)
    return code


if __name__ == "__main__":
    sys.exit(main())
