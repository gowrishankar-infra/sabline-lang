#!/usr/bin/env python3
"""`sabline run` and `sabline.run` through sabline-rt (9.0, M3), held to the
same runs in the Python package.

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
`--no-confine`, and the library's own run is unconfined - so the gate's
rule holds both at `none`; and the one line a run through sabline-rt adds
to the error channel when it falls back to the Python package, which none
of these does. And it requires the other way round too: a run through
sabline-rt is one - its receipt's producer is `sabline-rt` - and the
package's is not.
"""
import json
import os
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


def command_line(path: Path, runtime: str, out: Path) -> dict[str, Any]:
    """`sabline FILE --no-confine --receipt R --audit-stream S -- ARGS`,
    given STDIN, under `runtime`: what it wrote, how it ended, and the
    receipt and stream it left."""
    env = dict(os.environ)
    env.pop(through_rt.VARIABLE, None)
    if runtime == "rust":
        env[through_rt.VARIABLE] = "rust"
    env["PYTHONIOENCODING"] = "utf-8"
    receipt, stream = out.with_suffix(f".{runtime}.receipt"), out.with_suffix(f".{runtime}.stream")
    done = subprocess.run(
        [sys.executable, str(HERE / "sabline.py"), str(path), "--no-confine",
         "--receipt", str(receipt), "--audit-stream", str(stream), "--",
         *run_dump.ARGS],
        input=run_dump.STDIN.encode("utf-8"), capture_output=True, env=env,
        cwd=str(path.parent), timeout=600)
    return {"stdout": done.stdout, "stderr": done.stderr, "status": done.returncode,
            "receipt": _read(receipt), "stream": _lines(stream)}


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _lines(path: Path) -> Any:
    if not path.exists():
        return None
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def library(path: Path, runtime: str) -> dict[str, Any]:
    """`sabline.run(source, path=FILE, stdin=STDIN, args=ARGS)` under
    `runtime`, with the stream it handed out."""
    saved = os.environ.pop(through_rt.VARIABLE, None)
    if runtime == "rust":
        os.environ[through_rt.VARIABLE] = "rust"
    events: list[Any] = []
    try:
        result = sabline.run(path.read_text(encoding="utf-8"), path=str(path),
                             stdin=run_dump.STDIN, args=list(run_dump.ARGS),
                             audit_stream=events.append)
    finally:
        os.environ.pop(through_rt.VARIABLE, None)
        if saved is not None:
            os.environ[through_rt.VARIABLE] = saved
    doc = result.as_dict()
    return {"result": {k: v for k, v in doc.items() if k != "receipt"},
            "receipt": doc["receipt"], "stream": events}


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


def main() -> int:
    if through_rt.binary() is None:
        gate.rt_binary()                 # builds it, as the gate does
    with tempfile.TemporaryDirectory(prefix="sabline-through-rt-") as tmp:
        work = Path(tmp)
        chosen = programs(work)
        print(f"check_through_rt: {len(chosen)} programs, through the command "
              f"line and sabline.run, with {through_rt.VARIABLE} unset and rust")
        with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 2)) as pool:
            cli = list(pool.map(lambda c: (c, command_line(c[1], "python", c[1]),
                                           command_line(c[1], "rust", c[1])), chosen))
        found: list[str] = []
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
            mine, theirs = library(path, "python"), library(path, "rust")
            if refused_by_checks(mine["receipt"]):
                made = (producer(mine["receipt"]), producer(theirs["receipt"]))
                if made != ("sabline-lang", "sabline-lang"):
                    found.append(f"{name}: refused by the checks, and sabline.run's "
                                 f"receipts were made by {made[0]} and {made[1]}")
                continue
            if mine["result"] != theirs["result"]:
                a, b = mine["result"], theirs["result"]
                key = next(k for k in a if a[k] != b.get(k))
                found.append(f"{name}: sabline.run's {key}: python {a[key]!r:.300}, "
                             f"sabline-rt {b.get(key)!r:.300}")
            elif producer(theirs["receipt"]) != "sabline-rt":
                found.append(f"{name}: sabline.run's receipt was made by "
                             f"{producer(theirs['receipt'])}")
            else:
                why = (receipts_differ(mine["receipt"], theirs["receipt"], "receipt")
                       or streams_differ(mine["stream"], theirs["stream"], "stream"))
                if why:
                    found.append(f"{name}: sabline.run's {why}")
    for line in found[:60]:
        print("  " + line)
    print(f"check_through_rt: {len(chosen)} programs, {len(found)} difference(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
