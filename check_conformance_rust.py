#!/usr/bin/env python3
"""`sabline conformance --runtime rust`: sabline-rt answers what it
implements, and nothing it did not answer is counted as its.

plan/9.0.md, M2 (amended 2026-10-08): the conformance corpus passes against
sabline-rt for the case kinds sabline-rt implements - L1's 280 `budget`
cases - driven through the `sabline-rt` binary; every other kind stays the
Python package's, and is reported as answered by it. This holds the runner
to that:

- every budget case is answered by sabline-rt and passes, and every other
  case says it was answered by the Python package;
- a wrong answer from sabline-rt fails its case - refusing a budget that
  must parse, parsing one that must be refused, a different grant, and a
  document that answers nothing - so the rust half can go red;
- without the flag, nothing changes: no result names a runtime and the
  report has no `runtime`.

    python check_conformance_rust.py [corpus]
"""
import os
import sys
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sabline import conform  # noqa: E402

PASSED = FAILED = 0


def ok(label: str, good: bool, detail: Any = "") -> None:
    global PASSED, FAILED
    if good:
        PASSED += 1
        print(f"  ok      {label}")
    else:
        FAILED += 1
        print(f"  WRONG   {label}" + (f"\n          {detail}" if detail else ""))


def corpus_of(argv: list[str]) -> str:
    found = conform._conformance_corpus(argv[0] if argv else None)
    if found is None:
        for guess in ("sabline-spec/tests", "../sabline-spec/tests"):
            if os.path.isfile(os.path.join(HERE, guess, "index.json")):
                return os.path.join(HERE, guess)
        raise SystemExit("check_conformance_rust.py: give sabline-spec's tests/")
    return str(found)


def main(argv: list[str]) -> int:
    corpus = corpus_of(argv)
    ok("sabline-rt is found (this checkout's build, or one on PATH)",
       conform._rt_binary() is not None)

    report = conform._conformance(corpus, (1,), "rust")
    rows = report["results"]
    budget = [r for r in rows if r["kind"] == "budget"]
    other = [r for r in rows if r["kind"] != "budget"]
    ok(f"L1's {len(budget)} budget cases are answered by sabline-rt",
       len(budget) == 280 and all(r["answered_by"] == "sabline-rt"
                                  for r in budget), len(budget))
    ok("...and every one of them passes",
       all(r["result"] == "pass" for r in budget),
       [r for r in budget if r["result"] != "pass"][:3])
    ok(f"the other {len(other)} L1 cases say the Python package answered",
       bool(other) and all(r["answered_by"] == "python" for r in other))
    ok("the report says how many each runtime answered",
       report.get("runtime", {}).get("answered")
       == {"sabline-rt": len(budget), "python": len(other)},
       report.get("runtime"))

    # a wrong answer from sabline-rt is a failed case, whatever it is
    valid = {"id": "v", "input": {"allow": "io"},
             "expect": {"valid": True, "grants": {"effects": ["io"],
                                                  "counts": {}}}}
    invalid = {"id": "i", "input": {"allow": "x"},
               "expect": {"valid": False}}
    wrong = [
        ("a refusal of a budget that must parse", valid,
         {"valid": False, "refused": "no"}),
        ("a parse of a budget that must be refused", invalid,
         {"valid": True, "shape": {"effects": [], "counts": {}}}),
        ("a different grant", valid,
         {"valid": True, "shape": {"effects": ["env"], "counts": {}}}),
        ("a document that answers nothing", valid, {"valid": True}),
    ]
    for label, case, document in wrong:
        said = conform._conf_budget(case, {"rust_budgets": {case["id"]: document}})
        ok(f"sabline-rt giving {label} fails the case", bool(said), said)
    right = conform._conf_budget(
        valid, {"rust_budgets": {"v": {"valid": True, "shape": {
            "effects": ["io"], "counts": {}}}}})
    ok("...and the right answer passes it", right == "", right)

    plain = conform.conformance(corpus, (1,))
    ok("without --runtime nothing names a runtime",
       "runtime" not in plain and not any("answered_by" in r
                                          for r in plain["results"]))
    print("-" * 62)
    print(f"{PASSED} right, {FAILED} wrong")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
