#!/usr/bin/env python3
"""sabline test --from-contracts (8.3): witnesses from the prover, run.

    python check_from_contracts.py

  caught    a false ensures the prover could not settle - it holds for every
            input but the largest its requires allows - is caught by the
            witness at that boundary, with the argument named, exit 1
  passes    the same function with a requires that rules that input out:
            every witness passes, exit 0
  refused   a function that declares an effect is not run: not reported as
            passed or failed, and the file it would write is not written
  bounded   a witness that never returns is stopped at --witness-seconds
  skipped   a generic function and a record parameter are named, not run
  no budget whatever the witnesses are, what runs has no effect granted
  no prover without z3 the command says so and exits 2
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sabline  # noqa: E402
from suite_dirs import isolate  # noqa: E402

WORK = isolate("check_from_contracts")
SABLINE = [sys.executable, str(HERE / "sabline.py")]
PASSED = FAILED = SKIPPED = 0

DIGITS = """fn digits(n: Int) -> Int
    requires n >= 0 and n <= LIMIT
    ensures result >= 1 and result <= 3
{
    let count = 1
    let m = n
    while m >= 10 {
        m = m / 10
        count = count + 1
    }
    return count
}

fn main() uses io {
    print(to_text(digits(7)))
}
"""
EFFECTS = """fn save(path: Text) -> Int uses fs
    requires length(path) > 0
    ensures result >= 0
{
    write_file("canary.txt", path)
    return 1
}

fn main() uses io {
    print("x")
}
"""
SPIN = """fn spin(n: Int) -> Int
    requires n > 0
    ensures result > 0
{
    let i = n
    let flip = 0
    while i > 0 {
        flip = 1 - flip
    }
    return i
}

fn main() uses io {
    print("x")
}
"""
SHAPES = """record Point {
    x: Int
    y: Int
}

fn first(xs: List of T) -> T for any T
    requires length(xs) > 0
{
    return get(xs, 0)
}

fn left(p: Point) -> Int
    requires p.x > 0
    ensures result > 0
{
    return p.x
}

fn main() uses io {
    print(to_text(left(Point(x: 1, y: 2))))
}
"""


def ok(label: str, good: object, detail: Any = "") -> None:
    global PASSED, FAILED
    if good:
        PASSED += 1
        print(f"  ok      {label}")
    else:
        FAILED += 1
        print(f"  WRONG   {label}")
        if detail:
            print(f"          {str(detail)[:700]}")


def skip(label: str, why: str) -> None:
    global SKIPPED
    SKIPPED += 1
    print(f"  skip    {label} ({why})")


def run(name: str, text: str, *extra: str) -> tuple[int, dict[str, Any]]:
    (WORK / name).write_text(text, encoding="utf-8", newline="\n")
    done = subprocess.run(SABLINE + ["test", name, "--from-contracts",
                                     "--json", *extra],
                          capture_output=True, text=True, cwd=str(WORK),
                          timeout=900)
    try:
        return done.returncode, json.loads(done.stdout)
    except ValueError:
        return done.returncode, {"stdout": done.stdout,
                                 "stderr": done.stderr}


def row(report: dict[str, Any], name: str) -> dict[str, Any]:
    return next((r for r in report.get("functions", [])
                 if r["function"] == name), {})


def main() -> int:
    print("sabline test --from-contracts")
    print("-" * 62)
    if not sabline.HAVE_Z3:
        code, report = run("digits_false.vel", DIGITS.replace("LIMIT", "1000"))
        ok("without the prover the command says so and exits 2",
           code == 2 and any("prover" in p for p in report.get("problems",
                                                               [])), report)
        skip("the witness cases", "z3-solver is not installed")
        print("-" * 62)
        print(f"{PASSED} correct, {FAILED} wrong, {SKIPPED} skipped")
        return 1 if FAILED else 0
    code, report = run("digits_false.vel", DIGITS.replace("LIMIT", "1000"))
    r = row(report, "digits")
    broken = [w for w in r.get("witnesses", []) if w["outcome"] == "broken"]
    ok("the prover leaves the false promise to runtime (it does not refute "
       "or prove it)", r.get("status") == "checked at runtime"
       and not report.get("refuted"), r.get("status"))
    ok("a witness at the requires' boundary breaks the ensures, and is named",
       code == 1 and any("n = 1000" in w["args"] for w in broken),
       [(w["args"], w["outcome"]) for w in r.get("witnesses", [])])
    ok("...among witnesses chosen at both ends of what the requires allows",
       {"n = 0", "n = 1000"} <= {w["args"] for w in r.get("witnesses", [])},
       [w["args"] for w in r.get("witnesses", [])])
    code, report = run("digits_true.vel", DIGITS.replace("LIMIT", "999"))
    r = row(report, "digits")
    ok("the true promise: every witness passes, exit 0", code == 0
       and r.get("witnesses") and r["passed"] == len(r["witnesses"]),
       report)
    ok("...up to --count witnesses (20 unless given)",
       0 < len(r.get("witnesses", [])) <= 20, len(r.get("witnesses", [])))
    code, report = run("digits_few.vel", DIGITS.replace("LIMIT", "999"),
                       "--count", "3")
    ok("--count 3 makes at most three", len(row(report, "digits").get(
        "witnesses", [])) <= 3, report)
    canary = WORK / "canary.txt"
    code, report = run("effects.vel", EFFECTS)
    r = row(report, "save")
    ok("a function with an effect is refused, and nothing of it runs",
       r.get("refused") and not r.get("witnesses") and not canary.exists()
       and code == 0, report)
    ok("what runs has no effect granted, whatever the witnesses are",
       report.get("budget") == "", report.get("budget"))
    code, report = run("spin.vel", SPIN, "--witness-seconds", "1",
                       "--count", "2")
    r = row(report, "spin")
    # the loop turns a flag over and changes nothing it tests, so every n the
    # requires allows spins for ever: which witnesses the prover picks cannot
    # change the outcome, and the timer is the only thing that ends them
    ok("a witness that never returns is stopped at --witness-seconds",
       code == 1 and r.get("witnesses")
       and all(w["outcome"] == "did_not_finish"
               for w in r.get("witnesses", [])), r)
    code, report = run("shapes.vel", SHAPES)
    ok("a generic function is skipped, and says why",
       "generic" in str(row(report, "first").get("skipped")), report)
    ok("a record parameter is skipped, and says why",
       "Point" in str(row(report, "left").get("skipped")), report)
    code, report = run("broken.vel", "fn main( {\n")
    ok("a file that does not compile runs nothing, exit 2",
       code == 2 and report.get("problems"), report)
    print("-" * 62)
    print(f"{PASSED} correct, {FAILED} wrong, {SKIPPED} skipped")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
