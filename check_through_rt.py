#!/usr/bin/env python3
"""`sabline run`, `sabline.run`, a bounded run and a Pool through sabline-rt
(9.0, M3), held to the same runs in the Python package.

    python check_through_rt.py

The agreement gate holds the two interpreters to each other through the
run document, which neither a user nor a suite calls. This holds the two
entry points that do: the command line and `sabline.run`, each asked for
the same run with SABLINE_REFERENCE_RUNTIME unset and set to `rust`
(sabline/through_rt.py). What it shows is the part the gate cannot: that
what sabline-rt's run writes reaches the user through the package's own
standard streams byte for byte, that the program reads what the package's
run reads, that the exit status, the error printed, the receipt written by
`--receipt` and the stream written by `--audit-stream` are the same, and
that `RunResult` is - its output and logs, its problems, the effect a
refusal names, its exit code, what each effect let through, its receipt.

**Four entry points**: the command line; `sabline.run` with no limit, which
runs in the caller's process; `sabline.run` with a timeout and a memory
cap, whose pool of one checks the program in a worker and whose caller
then starts sabline-rt under the limits; and a `sabline.Pool` of four that
serves every program in turn. The limits are generous - every program ends
well inside them - so what is compared is the run, not where a limit fell;
check_pool.py and check_library.py ask the limits themselves. The last two
take every STRIDE-th program, not all of them: what they add to the first
two is the way the run is started and its receipt finished, the same for
every program, and each run there is the program proved again by a worker,
which over all of them is most of an hour.

**And `sabline test`**, whose run calls each test function rather than
`main`: examples/std_test.vel and TESTED, every way a test can end, under
`io` and under a budget granting what one of them reads - the output, the
status and the error channel the same.

**And under their own budgets**: the gate's budgeted programs
(agreement_runs.BUDGETED) in its tree, through `sabline.run` with and
without limits and through a `sabline.PoolRegistry` - a pool per budget, as
the doors keep them - each runtime in a tree made afresh: the grants and
the counts, the credential rule, a seed, a frozen clock given as an ISO
8601 instant (the library and a receipt give one; sabline-rt's request
takes epoch seconds), the environment and the import root. Left out: the
two rows that set the read ceiling, which the library has no argument for,
and a row whose run ends only at the run document's step limit, as above.

**And the examples written for a budget** (run_tests.py's ALLOW), through
the command line as run_tests.py runs each - its budget, its arguments and
its input - in a scratch folder made afresh for each runtime.

**And the network, Python and tools** (agreement_runs.RELAYED_RUNS), whose
calls sabline-rt relays to the package: through the command line too, and
against the gate's stand-in servers - this process the host of an
unbounded run and of the command line's, a pool's worker the host of a
bounded one and of a pool's. Left out: the rows that need a tool session,
which only `sabline run --tools` opens, over a door this check does not
hold (the gate's run document has a stand-in host for them, and
check_runner.py asks the door). And the two lists of what is relayed - the
package's runtime.OUTSIDE_BUILTINS and the crate's interp::RELAYED - are
held to each other and to every builtin of the network, Python and tools.

**What it runs**: every program of the run corpus (agreement_runs.py) and
of examples/ that ends within the run document's limits and escapes
nothing - the programs the gate runs, as a user runs them, with the run
document's input and arguments. The run corpus's size-limit programs
(LAUGHS and the room cases) are not: without the gate's limit they are
programs that make a terabyte, which is what they are for.

**A program the checks or the prover refuse** runs nothing, and stays the
package's under either value - the prover is the package's for good
(decisions/0002), and what it finds decides whether a program runs. For
those both receipts must be the package's, and the output and the status
the same; the error channel is not compared, because the prover's
counterexample is z3's, and z3 may find a different one each time.

**What it does not compare**, each named: the receipt's producer, version,
start and duration, which the gate normalises too; confinement, which
sabline-rt does not do before M4 - the command line runs with
`--no-confine`, the bounded runs and the pool with `confine=False`, and the
library's own run is unconfined - so the gate's rule holds both at `none`; the one line a run through sabline-rt adds to
the error channel when it falls back to the Python package, which none of
these does; and the note the package's native compiler gives where
llvmlite is not installed, which a run through sabline-rt - interpreted,
with no native code to speed up - has no reason to give. And it requires the other way round too: a run through
sabline-rt is one - its receipt's producer is `sabline-rt` - and the
package's is not.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import agreement_runs  # noqa: E402
import check_agreement as gate  # noqa: E402
import sabline  # noqa: E402
from sabline import run_dump, through_rt  # noqa: E402

SKIPPED_KINDS = ("run-laughs/", "run-room/")

# `sabline test` programs: (name, source, budget) - every way a test ends,
# and one that ends sabline test itself.
_ENDINGS = '''fn test_true() -> Bool {
    return true
}

fn test_false() -> Bool {
    return false
}

fn test_gives_back_a_number() -> Int {
    return 3
}

fn test_gives_back_a_list() -> List of Text {
    return ["a", "b"]
}

fn test_prints_and_logs_first() -> Bool uses io {
    print("printed by a test")
    log("logged by a test")
    return true
}

fn test_divides_by_zero() -> Int {
    let zero = 0
    return 7 / zero
}

fn test_lets_a_failure_escape() -> Int or fail {
    let n = try to_int("not a number")
    return n
}

fn test_reads_a_file() -> Bool uses io, fs {
    check read_file("no-such-file.txt") {
        ok t {
            print(t)
        }
        fail why {
            print("could not: " + why)
        }
    }
    return true
}

fn test_takes_an_argument(n: Int) -> Bool {
    return n > 0
}

fn not_a_test() -> Bool {
    return false
}

fn main() uses io {
    print("main is not run by sabline test")
}
'''
_EXITS = '''fn test_first() -> Bool {
    return true
}

fn test_exits() -> Bool uses io {
    print("about to exit")
    exit_with(3)
    return true
}

fn test_never_reached() -> Bool {
    return true
}
'''
TESTED: tuple[tuple[str, str, str], ...] = (
    ("tests/every-ending", _ENDINGS, "io"),
    ("tests/every-ending-with-fs", _ENDINGS, "io,fs"),
    ("tests/exit-ends-them", _EXITS, "io"),
)

# The limits a bounded run and the pool are given: far past what any of
# these programs needs, so that both runtimes finish every one.
LIMITS: dict[str, Any] = {"timeout": 120, "max_memory_mb": 1024}

# a bounded run and a pool take every STRIDE-th program (above)
STRIDE = 4

# sabline/native.py's note where llvmlite is missing, which only the
# package's own run gives (it is the native compiler's)
NATIVE_NOTE = re.compile(rb"note: llvmlite is not installed - running fully "
                         rb"interpreted[^\n]*\n")


def programs(work: Path) -> list[tuple[str, Path]]:
    """Every program to run, written to `work`, that ends within the run
    document's limits and escapes nothing."""
    out = []
    corpus = [(name, src) for name, src in agreement_runs.cases()
              if not name.startswith(SKIPPED_KINDS)]
    corpus += [(f"examples/{p.name}", p.read_bytes())
               for p in sorted((HERE / "examples").glob("*.vel"))]
    for k, (name, source) in enumerate(corpus):
        path = work / f"p{k:04d}.vel"
        path.write_bytes(source)
        doc = run_dump.run_document(str(path))
        if doc["stopped"] is None and doc["raised"] is None:
            out.append((name, path))
    return out


def command_line(path: Path, runtime: str, out: Path,
                 given: dict[str, Any] | None = None,
                 values: dict[str, str] | None = None,
                 args: list[str] | None = None,
                 stdin: str | None = None) -> dict[str, Any]:
    """`sabline FILE --no-confine --receipt R --audit-stream S -- ARGS`,
    given STDIN, under `runtime`: what it wrote, how it ended, and the
    receipt and stream it left. With `given`, a budgeted row's: its
    `--allow`, `--deny`, `--seed` and `--freeze-time`, filled from
    `values`."""
    env = dict(os.environ)
    env.pop(through_rt.VARIABLE, None)
    if runtime == "rust":
        env[through_rt.VARIABLE] = "rust"
    env["PYTHONIOENCODING"] = "utf-8"
    receipt, stream = out.with_suffix(f".{runtime}.receipt"), out.with_suffix(f".{runtime}.stream")
    flags: list[str] = []
    for key, flag in (("allow", "--allow"), ("deny", "--deny"),
                      ("seed", "--seed"), ("freeze_time", "--freeze-time")):
        if given is not None and given.get(key) is not None:
            flags += [flag, str(gate._filled(given[key], values or {}))]
    done = subprocess.run(
        [sys.executable, str(HERE / "sabline.py"), str(path), "--no-confine",
         *flags, "--receipt", str(receipt), "--audit-stream", str(stream),
         "--", *(run_dump.ARGS if args is None else args)],
        input=(run_dump.STDIN if stdin is None else stdin).encode("utf-8"),
        capture_output=True, env=env,
        cwd=str(path.parent), timeout=600)
    return {"stdout": done.stdout, "stderr": NATIVE_NOTE.sub(b"", done.stderr),
            "status": done.returncode, "receipt": _read(receipt),
            "stream": _lines(stream)}


def tested(path: Path, allow: str, runtime: str) -> dict[str, Any]:
    """`sabline test FILE --allow ALLOW` under `runtime`: what it wrote
    and how it ended."""
    env = dict(os.environ)
    env.pop(through_rt.VARIABLE, None)
    if runtime == "rust":
        env[through_rt.VARIABLE] = "rust"
    env["PYTHONIOENCODING"] = "utf-8"
    done = subprocess.run(
        [sys.executable, str(HERE / "sabline.py"), "test", str(path),
         "--allow", allow], capture_output=True, env=env,
        cwd=str(path.parent), timeout=600)
    return {"stdout": done.stdout, "stderr": NATIVE_NOTE.sub(b"", done.stderr),
            "status": done.returncode}


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _lines(path: Path) -> Any:
    if not path.exists():
        return None
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


class _Runtime:
    """SABLINE_REFERENCE_RUNTIME set to `runtime` - unset for python - for
    as long as the block runs, and put back after."""

    def __init__(self, runtime: str) -> None:
        self.runtime = runtime

    def __enter__(self) -> None:
        self.saved = os.environ.pop(through_rt.VARIABLE, None)
        if self.runtime == "rust":
            os.environ[through_rt.VARIABLE] = "rust"

    def __exit__(self, *_exc: Any) -> None:
        os.environ.pop(through_rt.VARIABLE, None)
        if self.saved is not None:
            os.environ[through_rt.VARIABLE] = self.saved


def _taken(result: Any, events: list[Any]) -> dict[str, Any]:
    doc = result.as_dict()
    return {"result": {k: v for k, v in doc.items() if k != "receipt"},
            "receipt": doc["receipt"], "stream": events}


def library(path: Path, runtime: str, **limits: Any) -> dict[str, Any]:
    """`sabline.run(source, path=FILE, stdin=STDIN, args=ARGS)` under
    `runtime`, with the stream it handed out; with `limits`, a bounded run,
    unconfined so that only the runtime differs."""
    events: list[Any] = []
    with _Runtime(runtime):
        result = sabline.run(path.read_text(encoding="utf-8"), path=str(path),
                             stdin=run_dump.STDIN, args=list(run_dump.ARGS),
                             audit_stream=events.append,
                             **(dict(limits, confine=False) if limits else {}))
    return _taken(result, events)


def pooled(paths: list[Path], runtime: str) -> list[dict[str, Any]]:
    """Each program on one `sabline.Pool` of four under `runtime`, in turn."""
    out = []
    with _Runtime(runtime), sabline.Pool(size=4, confine=False, **LIMITS) as pool:
        for path in paths:
            events: list[Any] = []
            result = pool.run(path.read_text(encoding="utf-8"), path=str(path),
                              stdin=run_dump.STDIN, args=list(run_dump.ARGS),
                              audit_stream=events.append)
            out.append(_taken(result, events))
    return out


def _instant(epoch: int) -> Any:
    """`epoch` as an ISO 8601 instant, as a receipt gives one to a replay -
    or the number itself, past the year 9999 that `datetime` holds; the
    library takes either. Not `fromtimestamp`, which Windows refuses before
    1970 and after 3001."""
    import datetime
    try:
        at = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc) \
            + datetime.timedelta(seconds=epoch)
    except OverflowError:
        return epoch
    return at.isoformat().replace("+00:00", "Z")


def ending_rows(work: Path) -> set[str]:
    """The budgeted rows whose run ends within the run document's limits,
    in a tree of their own: a run that ends only at the step limit runs for
    ever through the library, which has none."""
    root = work / "tree-ending"
    values = agreement_runs.tree(root)
    variables = agreement_runs.run_variables(values)
    saved = {k: os.environ.get(k) for k in variables}
    os.environ.update(variables)
    out = set()
    try:
        for k, (name, source, given) in enumerate(agreement_runs.BUDGETED):
            path = root / f"row{k:04d}.vel"
            path.write_text(gate._filled(source, values), encoding="utf-8")
            doc = run_dump.run_document(
                str(path), **{key: gate._filled(v, values) for key, v in given.items()})
            if doc["stopped"] is None and doc["raised"] is None:
                out.add(name)
    finally:
        for variable, was in saved.items():
            if was is None:
                os.environ.pop(variable, None)
            else:
                os.environ[variable] = was
    return out


def budgeted(work: Path, runtime: str, how: str,
             ending: set[str] | None,
             ports: dict[str, str] | None = None) -> list[tuple[str, dict[str, Any]]]:
    """Every budgeted row of the gate but the read ceiling's, in order, in
    a tree made afresh under `work`, through the entry point `how` names -
    `run`, `bounded` or `pools`, or `cli` - under `runtime`: (name, what it
    did). With `ports`, the relayed rows instead, against the stand-in
    servers there, but for those that need a tool session."""
    import shutil
    # one path for both runtimes, the tree made afresh for each, as the gate
    # makes it: a path is in a message, a budget and the program's own text
    root = work / f"tree-{how}"
    shutil.rmtree(root, ignore_errors=True)
    values = agreement_runs.tree(root)
    if ports is not None:
        values.update(ports)
        rows = [(name, source, given)
                for name, source, given in agreement_runs.RELAYED_RUNS
                if "tools" not in given]
    else:
        rows = [(name, source, given)
                for name, source, given in agreement_runs.BUDGETED
                if "max_read" not in given and ending is not None
                and name in ending]
    variables = agreement_runs.run_variables(values)
    saved = {k: os.environ.get(k) for k in variables}
    os.environ.update(variables)
    out: list[tuple[str, dict[str, Any]]] = []
    try:
        with _Runtime(runtime), sabline.PoolRegistry(size=1, keep=4,
                                                     confine=False) as pools:
            for k, (name, source, given) in enumerate(rows):
                path = root / f"program{k:04d}.vel"
                path.write_text(gate._filled(source, values), encoding="utf-8")
                # a row's own variables, over the tree's, for its run alone
                own = gate._filled(given.get("environ") or {}, values)
                before = {v: os.environ.get(v) for v in own}
                os.environ.update(own)
                try:
                    if how == "cli":
                        out.append((name, command_line(
                            path, runtime, path, given=given, values=values)))
                    else:
                        out.append((name, _budgeted_run(
                            path, given, values, how, pools)))
                finally:
                    _put_back(before)
    finally:
        _put_back(saved)
    return out


def _put_back(saved: dict[str, str | None]) -> None:
    """The environment's variables put back as they were."""
    for variable, was in saved.items():
        if was is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = was


def _budgeted_run(path: Path, given: dict[str, Any], values: dict[str, str],
                  how: str, pools: Any) -> dict[str, Any]:
    """One budgeted row through the library - `run`, `bounded` or `pools` -
    and what it did."""
    asked: dict[str, Any] = {
        "allow": gate._filled(given.get("allow", "io"), values),
        "seed": given.get("seed"),
        "freeze_time": (None if given.get("freeze_time") is None
                        else _instant(given["freeze_time"]))}
    if given.get("deny"):
        asked["deny"] = set(given["deny"].split(","))
    if "import_root" in given:
        asked["import_root"] = gate._filled(given["import_root"], values)
    if how != "run":
        asked.update(LIMITS)
    events: list[Any] = []
    common: dict[str, Any] = {
        "path": str(path), "stdin": run_dump.STDIN,
        "args": list(run_dump.ARGS), "audit_stream": events.append}
    if how == "bounded":
        common["confine"] = False
    source_text = path.read_text(encoding="utf-8")
    try:
        if how == "pools":
            result = pools.run(source_text, **common, **asked)
        else:
            result = sabline.run(source_text, **common, **asked)
    except ValueError as e:
        # a clock past the year 9999 is refused before anything runs, by
        # either runtime: that it is, is compared
        return {"result": {"raised": str(e)}, "receipt": None, "stream": []}
    return _taken(result, events)


def examples_budgeted(work: Path, runtime: str) -> list[tuple[str, dict[str, Any]]]:
    """Each example run_tests.py gives a budget, through the command line as
    run_tests.py runs it - its budget, its arguments, its input - with a
    seed and a frozen clock, which one of them reads, in one folder made
    afresh for each runtime: two of them write files where they run, and a
    path is in a receipt. (name, what it did)."""
    import shutil
    tests = __import__("run_tests")
    where = work / "examples-budgeted"
    shutil.rmtree(where, ignore_errors=True)
    where.mkdir()
    out = []
    for name, allow in sorted(tests.ALLOW.items()):
        path = where / name
        path.write_bytes((HERE / "examples" / name).read_bytes())
        out.append((name, command_line(
            path, runtime, path,
            given={"allow": allow, "seed": 7,
                   "freeze_time": "2026-01-01T00:00:00Z"},
            args=list(tests.ARGS.get(name, [])),
            stdin=tests.STDIN.get(name) or "")))
    return out


def relayed_lists_agree() -> str | None:
    """Why what the package relays (runtime.OUTSIDE_BUILTINS) and what
    sabline-rt relays (interp::RELAYED) are not the same list, or not every
    builtin of the network, Python and tools - or None."""
    from sabline.runtime import OUTSIDE_BUILTINS
    from sabline.tables import BUILTINS
    text = (HERE / "rt" / "crates" / "sabline-rt" / "src" / "interp.rs").read_text(
        encoding="utf-8")
    found = re.search(r"pub const RELAYED: \[&str; \d+\] = \[(.*?)\];", text, re.S)
    if found is None:
        return "rt/crates/sabline-rt/src/interp.rs no longer says RELAYED"
    crate = set(re.findall(r'"([a-z_]+)"', found.group(1)))
    outside = {n for n, b in BUILTINS.items()
               if set(b["effects"]) & {"net", "ffi", "tool"}}
    if crate != set(OUTSIDE_BUILTINS) or crate != outside:
        return (f"what is relayed differs: the crate {sorted(crate)}, the "
                f"package {sorted(OUTSIDE_BUILTINS)}, the builtins of the "
                f"network, Python and tools {sorted(outside)}")
    return None


def stack_is_the_crates() -> str | None:
    """Why through_rt.RUN_STACK_MB is not the stack sabline-rt runs a
    program on, or None: the memory cap a run through it is given on Linux
    is the cap plus that stack."""
    text = (HERE / "rt" / "crates" / "sabline-rt" / "src" / "lib.rs").read_text(
        encoding="utf-8")
    found = re.search(r"pub const PARSE_STACK: usize = (\d+) \* 1024 \* 1024;", text)
    if found is None:
        return "rt/crates/sabline-rt/src/lib.rs no longer says PARSE_STACK in MiB"
    if int(found.group(1)) != through_rt.RUN_STACK_MB:
        return (f"sabline-rt's run stack is {found.group(1)} MiB and "
                f"through_rt.RUN_STACK_MB says {through_rt.RUN_STACK_MB}")
    return None


def producer(receipt: Any) -> str | None:
    try:
        return str(receipt["predicate"]["producer"]["name"])
    except (TypeError, KeyError):
        return None


def refused_by_checks(receipt: Any) -> bool:
    """Whether the run is one the checks or the prover refused, so that
    nothing ran."""
    try:
        return bool(receipt["predicate"]["exit"]["outcome"] == "did_not_compile")
    except (TypeError, KeyError):
        return False


def receipts_differ(a: Any, b: Any, what: str) -> str | None:
    """The gate's comparison of two receipts, each re-read so that
    normalising one edits nothing the other holds."""
    a, held_a = gate._normalised(json.loads(json.dumps(a)))
    b, held_b = gate._normalised(json.loads(json.dumps(b)))
    return gate._first_difference(a, b, what) or gate._confinement_rule(held_a, held_b)


def streams_differ(a: Any, b: Any, what: str) -> str | None:
    a, held_a = gate._normalised_stream(json.loads(json.dumps(a)))
    b, held_b = gate._normalised_stream(json.loads(json.dumps(b)))
    return gate._first_difference(a, b, what) or gate._confinement_rule(held_a, held_b)


def library_differs(name: str, how: str, mine: dict[str, Any],
                    theirs: dict[str, Any]) -> str | None:
    """Why one program's two runs through a library entry point differ,
    or None."""
    if "raised" in mine["result"] or "raised" in theirs["result"]:
        if mine["result"] != theirs["result"]:
            return (f"{name}: {how} raised: python {mine['result']!r:.300}, "
                    f"sabline-rt {theirs['result']!r:.300}")
        return None
    if refused_by_checks(mine["receipt"]):
        made = (producer(mine["receipt"]), producer(theirs["receipt"]))
        if made != ("sabline-lang", "sabline-lang"):
            return (f"{name}: refused by the checks, and {how}'s receipts "
                    f"were made by {made[0]} and {made[1]}")
        return None
    if mine["result"] != theirs["result"]:
        a, b = mine["result"], theirs["result"]
        key = next(k for k in a if a[k] != b.get(k))
        return (f"{name}: {how}'s {key}: python {a[key]!r:.300}, "
                f"sabline-rt {b.get(key)!r:.300}")
    if producer(theirs["receipt"]) != "sabline-rt":
        return f"{name}: {how}'s receipt was made by {producer(theirs['receipt'])}"
    why = (receipts_differ(mine["receipt"], theirs["receipt"], "receipt")
           or streams_differ(mine["stream"], theirs["stream"], "stream"))
    return f"{name}: {how}'s {why}" if why else None


def cli_differs(name: str, mine: dict[str, Any],
                theirs: dict[str, Any]) -> str | None:
    """Why one program's two runs through the command line differ, or
    None: what it wrote to each channel and how it ended, and the receipt
    and the stream, each made by the runtime that ran it - or, for a
    program the checks or the prover refuse, which nothing runs, the output
    and the status, both receipts the package's."""
    if refused_by_checks(mine["receipt"]):
        made = (producer(mine["receipt"]), producer(theirs["receipt"]))
        if made != ("sabline-lang", "sabline-lang"):
            return (f"{name}: refused by the checks, and its receipts were "
                    f"made by {made[0]} and {made[1]}")
        if (mine["stdout"], mine["status"]) != (theirs["stdout"], theirs["status"]):
            return f"{name}: refused by the checks, and the output or status differ"
        return None
    for key in ("stdout", "stderr", "status"):
        if mine[key] != theirs[key]:
            return (f"{name}: the command line's {key}: python "
                    f"{mine[key]!r:.300}, sabline-rt {theirs[key]!r:.300}")
    if (producer(mine["receipt"]), producer(theirs["receipt"])) != (
            "sabline-lang", "sabline-rt"):
        return (f"{name}: the command line's receipts were made by "
                f"{producer(mine['receipt'])} and {producer(theirs['receipt'])}")
    why = (receipts_differ(mine["receipt"], theirs["receipt"], "receipt")
           or streams_differ(mine["stream"], theirs["stream"], "stream"))
    return f"{name}: the command line's {why}" if why else None


def main() -> int:
    if through_rt.binary() is None:
        gate.rt_binary()                 # builds it, as the gate does
    found: list[str] = []
    for why in (stack_is_the_crates(), relayed_lists_agree()):
        if why:
            found.append(why)
    with tempfile.TemporaryDirectory(prefix="sabline-through-rt-") as tmp:
        work = Path(tmp)
        chosen = programs(work)
        print(f"check_through_rt: {len(chosen)} programs, through the command "
              f"line, sabline.run with and without limits, and a Pool, with "
              f"{through_rt.VARIABLE} unset and rust")
        with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 2)) as pool:
            cli = list(pool.map(lambda c: (c, command_line(c[1], "python", c[1]),
                                           command_line(c[1], "rust", c[1])), chosen))
        for (name, path), mine, theirs in cli:
            if refused_by_checks(mine["receipt"]):
                made = (producer(mine["receipt"]), producer(theirs["receipt"]))
                if made != ("sabline-lang", "sabline-lang"):
                    found.append(f"{name}: refused by the checks, and its "
                                 f"receipts were made by {made[0]} and {made[1]}")
                elif (mine["stdout"], mine["status"]) != (theirs["stdout"], theirs["status"]):
                    found.append(f"{name}: refused by the checks, and the two "
                                 f"runs' output or status differ")
                continue
            for key in ("stdout", "stderr", "status"):
                if mine[key] != theirs[key]:
                    found.append(f"{name}: the command line's {key}: python "
                                 f"{mine[key]!r:.300}, sabline-rt {theirs[key]!r:.300}")
                    break
            else:
                if (producer(mine["receipt"]), producer(theirs["receipt"])) != (
                        "sabline-lang", "sabline-rt"):
                    found.append(f"{name}: the command line's receipts were made by "
                                 f"{producer(mine['receipt'])} and "
                                 f"{producer(theirs['receipt'])}")
                else:
                    why = (receipts_differ(mine["receipt"], theirs["receipt"], "receipt")
                           or streams_differ(mine["stream"], theirs["stream"], "stream"))
                    if why:
                        found.append(f"{name}: the command line's {why}")
        for name, path in chosen:
            why = library_differs(name, "sabline.run", library(path, "python"),
                                  library(path, "rust"))
            if why:
                found.append(why)
        sampled = chosen[::STRIDE]
        for name, path in sampled:
            why = library_differs(name, "sabline.run with limits",
                                  library(path, "python", **LIMITS),
                                  library(path, "rust", **LIMITS))
            if why:
                found.append(why)
        paths = [path for _, path in sampled]
        for (name, _), mine, theirs in zip(sampled, pooled(paths, "python"),
                                           pooled(paths, "rust")):
            why = library_differs(name, "a Pool", mine, theirs)
            if why:
                found.append(why)
        tests: list[tuple[str, Path, str | None, str]] = [
            (name, work / f"tested{k}.vel", source, allow)
            for k, (name, source, allow) in enumerate(TESTED)]
        tests.append(("examples/std_test.vel", HERE / "examples" / "std_test.vel",
                      None, "io"))
        for name, path, source, allow in tests:
            if source is not None:
                path.write_text(source, encoding="utf-8")
            mine, theirs = tested(path, allow, "python"), tested(path, allow, "rust")
            for key in ("stdout", "stderr", "status"):
                if mine[key] != theirs[key]:
                    found.append(f"{name}: sabline test's {key}: python "
                                 f"{mine[key]!r:.300}, sabline-rt {theirs[key]!r:.300}")
                    break
        held = 0
        ending = ending_rows(work)
        for how, shown in (("run", "sabline.run under its budget"),
                           ("bounded", "sabline.run under its budget, with limits"),
                           ("pools", "a PoolRegistry under its budget")):
            ours, rts = (budgeted(work, "python", how, ending),
                         budgeted(work, "rust", how, ending))
            held += len(ours)
            for (name, a), (_, b) in zip(ours, rts):
                why = library_differs(f"budgeted/{name}", shown, a, b)
                if why:
                    found.append(why)
        # the examples written for a budget, as run_tests.py runs them
        examples = list(zip(examples_budgeted(work, "python"),
                            examples_budgeted(work, "rust")))
        for (name, a), (_, b) in examples:
            why = cli_differs(f"examples/{name} under its budget", a, b)
            if why:
                found.append(why)
        # the network, Python and tools, against the stand-in servers
        relayed = 0
        ports, stop_servers = agreement_runs.servers()
        try:
            for how, shown in (("cli", "the command line under its budget"),
                               ("run", "sabline.run under its budget"),
                               ("bounded", "sabline.run under its budget, with limits"),
                               ("pools", "a PoolRegistry under its budget")):
                ours, rts = (budgeted(work, "python", how, None, ports),
                             budgeted(work, "rust", how, None, ports))
                relayed += len(ours)
                for (name, a), (_, b) in zip(ours, rts):
                    why = (cli_differs(f"relayed/{name}", a, b) if how == "cli"
                           else library_differs(f"relayed/{name}", shown, a, b))
                    if why:
                        found.append(why)
        finally:
            stop_servers()
    for line in found[:60]:
        print("  " + line)
    print(f"check_through_rt: {len(chosen)} programs ({len(chosen[::STRIDE])} of "
          f"them bounded and pooled), {len(tests)} under sabline test, {held} "
          f"runs under their own budgets, {len(examples)} examples under "
          f"theirs, and {relayed} of the network, Python and tools, relayed, "
          f"{len(found)} difference(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
