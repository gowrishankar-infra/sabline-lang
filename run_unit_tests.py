#!/usr/bin/env python3
"""The stage-isolated unit tests (8.2): tests/unit, one module per stage.

    python run_unit_tests.py                   every stage
    python run_unit_tests.py --stage lexer     one stage (repeat for more)
    python run_unit_tests.py --verbose         name each test as it runs

One line per stage: tests run, failed (failures, errors and unexpected
successes), skipped, and known discrepancies - tests asserting what
SPEC.md or LLM.md says where the stage does otherwise. Those are marked
expected failures, so that a stage fixed to match the documents fails
here as an unexpected success until the marker is removed. Exits 1 on
any failure, 2 on a stage it does not know. Output is ASCII.
"""
import argparse
import os
import sys
import time
import unittest
from typing import Any, cast

ROOT = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.join(ROOT, "tests", "unit")
ORDER = ("lexer", "parser", "loader", "effects", "checker", "prover",
         "pipeline_order")


class AsciiOut:
    """sys.stdout, with anything outside ASCII written as an escape."""

    def write(self, text: str) -> int:
        sys.stdout.write(text.encode("ascii", "backslashreplace")
                         .decode("ascii"))
        return len(text)

    def flush(self) -> None:
        sys.stdout.flush()


class Quiet:
    def write(self, text: str) -> int:
        return len(text)

    def flush(self) -> None:
        pass


def stages_on_disk() -> list[Any]:
    found = sorted(name[len("test_"):-len(".py")] for name in os.listdir(UNIT)
                   if name.startswith("test_") and name.endswith(".py"))
    return [s for s in ORDER if s in found] + [s for s in found
                                               if s not in ORDER]


def main(argv: Any = None) -> int:
    known = stages_on_disk()
    parser = argparse.ArgumentParser(
        description="Run the stage-isolated unit tests in tests/unit.")
    parser.add_argument("--stage", action="append", metavar="NAME",
                        help="run only this stage: " + ", ".join(known))
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="name each test as it runs")
    args = parser.parse_args(argv)
    chosen = args.stage or known
    unknown = [s for s in chosen if s not in known]
    if unknown:
        print(f"unknown stage: {', '.join(unknown)}; the stages are "
              f"{', '.join(known)}")
        return 2

    # this checkout's compiler, never one installed elsewhere
    sys.path.insert(0, ROOT)
    out = AsciiOut()
    failed_tests: list[tuple[str, unittest.TestCase | None, str]]
    test: unittest.TestCase | None
    failed_tests, discrepancies = [], []
    totals = {"run": 0, "failed": 0, "skipped": 0, "known": 0}
    started = time.perf_counter()
    for stage in chosen:
        suite = unittest.TestLoader().discover(
            UNIT, pattern=f"test_{stage}.py", top_level_dir=UNIT)
        runner = unittest.TextTestRunner(
            stream=out if args.verbose else Quiet(),
            verbosity=2 if args.verbose else 0)
        if args.verbose:
            out.write(f"\n== {stage}\n")
        t0 = time.perf_counter()
        result = runner.run(suite)
        seconds = time.perf_counter() - t0
        failed = (len(result.failures) + len(result.errors)
                  + len(result.unexpectedSuccesses))
        counts = {"run": result.testsRun, "failed": failed,
                  "skipped": len(result.skipped),
                  "known": len(result.expectedFailures)}
        for key, value in counts.items():
            totals[key] += value
        out.write(f"{stage:<16}{counts['run']:>5} run {failed:>4} failed "
                  f"{counts['skipped']:>4} skipped {counts['known']:>4} "
                  f"known discrepancies {seconds:>8.2f}s\n")
        for test, trace in result.failures + result.errors:
            failed_tests.append((stage, test, trace))
        for test in result.unexpectedSuccesses:
            failed_tests.append((stage, test,
                                 "UNEXPECTED SUCCESS: the stage now does what "
                                 "the documents say; remove the expected-"
                                 "failure marker\n"))
        for test, _trace in result.expectedFailures:
            discrepancies.append((stage, test))
        for test, reason in result.skipped:
            if not args.verbose:
                out.write(f"    skipped {test.id()}: {reason}\n")

    package = sys.modules.get("sabline")
    if package is not None and not os.path.normcase(
            os.path.abspath(cast(str, package.__file__))).startswith(
            os.path.normcase(os.path.join(ROOT, "sabline")) + os.sep):
        failed_tests.append(("(runner)", None,
                             f"imported sabline from {package.__file__}, not "
                             f"from this checkout\n"))
        totals["failed"] += 1

    if discrepancies:
        out.write("\nknown discrepancies (documented, not done):\n")
        for stage, test in discrepancies:
            doc = (test.shortDescription() or "").split(" - documented, "
                                                        "not done: ")
            said = doc[1] if len(doc) > 1 else doc[0]
            out.write(f"  {stage}: {test.id().split('.', 1)[-1]}\n"
                      f"      {said}\n")
    for stage, test, trace in failed_tests:
        name = test.id() if test is not None else stage
        out.write(f"\n{'=' * 70}\nFAILED [{stage}] {name}\n{'-' * 70}\n"
                  f"{trace}")
    out.write(f"\nall stages: {totals['run']} run, {totals['failed']} failed, "
              f"{totals['skipped']} skipped, {totals['known']} known "
              f"discrepancies, {time.perf_counter() - started:.2f}s\n")
    return 1 if totals["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
