"""sabline test --from-contracts: each function's requires, asked of the
prover for arguments, and its ensures held to what running it on them
returns (8.3).
"""
import copy
import json
import os
import shutil
import sys
import tempfile
import threading

from . import state as _state
from .errors import SablineError
from .parser import nice_name
from .tables import HAVE_Z3, REDACTED
from .loader import load_program
from .effects import check_effects
from .checker import check_types
from .prover import check_proofs
from .runtime import build_runtime
from .values import FailSignal, to_text
from .budget import Budget
from typing import Any

# ---------------------------------------------------------------------------
# 8b. WITNESSES - promises exercised on the inputs they allow
#
#     A promise the prover proved holds for every input its requires allows.
#     One it could not prove is checked while running, and until now only on
#     the inputs a program happened to be given. `sabline test FILE
#     --from-contracts` runs the prover first, then asks it for up to --count
#     argument lists each function's requires allows - the least and the
#     greatest value each whole number, text length and list length can
#     take, then others - and calls the function on each, interpreted, so its
#     ensures is checked on every return (native code has no ensures check).
#     A function that declares an effect is not run at all, and the ones that
#     are run have no effect granted: a witness is a value, and nothing about
#     a value can make a pure function touch anything.
# ---------------------------------------------------------------------------

FROM_CONTRACTS_SCHEMA = "sabline.from-contracts/1"   # provisional
WITNESS_COUNT_DEFAULT = 20
WITNESS_COUNT_MOST = 200
WITNESS_SECONDS_DEFAULT = 5.0


def _shown(fn: Any, args: list[Any]) -> str:
    hush: frozenset[str] | set[str] = getattr(fn, "secret_params",
                                              frozenset())
    return ", ".join(f"{name} = " + (REDACTED if name in hush else
                                     json.dumps(value) if isinstance(value, str)
                                     else to_text(value))
                     for (name, _t), value in zip(fn.params, args))


def _run_one(rt: dict[str, Any], fn: Any, args: list[Any], seconds: float,
             stop: str) -> tuple[str, str]:
    """(outcome, detail) of one call: passed, broken (E601), not_a_witness
    (E600: the requires did not hold when run), did_not_finish, stopped."""
    # The timer thread writes the stop file; this thread removes it. On
    # Windows a remove that lands while that open is in flight raises
    # (WinError 32, "used by another process") - a traceback out of
    # `sabline test --from-contracts` rather than a report - and
    # timer.cancel() does not call back a `late` that has already begun.
    # So writer and remover share a lock, and the remove waits its turn.
    writing = threading.Lock()

    def late() -> None:
        with writing:
            with open(stop, "w", encoding="utf-8"):
                pass

    def forget() -> None:
        with writing:
            for _ in range(50):
                try:
                    if os.path.exists(stop):
                        os.remove(stop)
                    return
                except OSError:
                    threading.Event().wait(0.02)

    forget()
    timer = threading.Timer(seconds, late)
    timer.daemon = True
    timer.start()
    try:
        rt["call"](fn.name, [copy.deepcopy(a) for a in args], fn.line)
        return "passed", ""
    except SablineError as e:
        if e.code == "E601":
            return "broken", e.message
        if e.code == "E600":
            return "not_a_witness", e.message
        if e.code == "E615":
            return "did_not_finish", (f"it had not returned {seconds:g} "
                                      f"second(s) later")
        return "stopped", f"[{e.code}] {e.message}"
    except FailSignal as e:
        if fn.can_fail:
            return "passed", f"failed, as it may: {e.reason}"
        return "stopped", f"a failure escaped: {e.reason}"
    except RecursionError:
        return "stopped", "Python's own recursion limit"
    finally:
        timer.cancel()
        forget()


def from_contracts(path: str, count: int = WITNESS_COUNT_DEFAULT,
                   seconds: float = WITNESS_SECONDS_DEFAULT) -> dict[str, Any]:
    """The sabline.from-contracts/1 report of one file, with its exit status
    in 'exit': 0 when no witness broke a promise, 1 when one did or a call
    stopped or did not finish, 2 when nothing could be run."""
    report: dict[str, Any] = {"schema": FROM_CONTRACTS_SCHEMA, "file": path,
                              "prover": HAVE_Z3, "count": count,
                              "seconds": seconds, "budget": "",
                              "functions": [], "problems": []}
    try:
        funcs, records = load_program(path)
    except SablineError as e:
        report["problems"].append(f"[{e.code}] {e.message}")
        report["exit"] = 2
        return report
    errors: list[Any] = []
    check_effects(funcs, errors)
    check_types(funcs, records, errors)
    if errors:
        report["problems"] += [f"line {e.line}: [{e.code}] {e.message}"
                               for e in errors]
        report["exit"] = 2
        return report
    if not HAVE_Z3:
        report["problems"].append("the prover (z3-solver) is not installed, "
                                  "so no witness can be made")
        report["exit"] = 2
        return report
    proven: set[Any] = set()
    witnesses: dict[str, Any] = {}
    refuted: list[Any] = []
    check_proofs(funcs, records, refuted, proven, witnesses_out=witnesses,
                 witness_count=count)
    report["refuted"] = [{"code": e.code, "line": e.line,
                          "message": e.message} for e in refuted]
    entry = os.path.normcase(os.path.abspath(path))
    targets = [f for f in funcs if f.requires and not f.is_lambda
               and f.name != "main"
               and os.path.normcase(os.path.abspath(f.src_file or path))
               == entry]
    home = tempfile.mkdtemp(prefix="sabline-witnesses-")
    stop = os.path.join(home, "stop")
    g = vars(_state)
    saved_stop, saved_budget = g["STOP_FILE"], Budget.snapshot()
    failures = 0
    try:
        g["STOP_FILE"] = stop
        Budget.parse("").install()        # no effect granted to anything run
        rt = build_runtime(funcs, {})     # interpreted: every ensures checked
        for fn in targets:
            row: dict[str, Any] = {
                "function": nice_name(fn.name).strip("'"), "line": fn.line,
                "status": ("proven" if fn.name in proven
                           else "checked at runtime"),
                "refused": None, "skipped": None, "witnesses": [],
                "passed": 0}
            if fn.effects:
                row["refused"] = (f"it uses {', '.join(sorted(fn.effects))}; "
                                  f"only a function with no effects is run")
            elif fn.type_vars:
                row["skipped"] = "it is generic, so its arguments have no one type"
            else:
                made = witnesses.get(fn.name) or {
                    "skipped": "the prover made no witness for it"}
                if "skipped" in made:
                    row["skipped"] = made["skipped"]
                for witness in made.get("witnesses") or []:
                    outcome, detail = _run_one(rt, fn, witness["args"],
                                               seconds, stop)
                    row["witnesses"].append({
                        "args": _shown(fn, witness["args"]),
                        "why": witness["why"], "outcome": outcome,
                        "detail": detail})
                    if outcome == "passed":
                        row["passed"] += 1
                    elif outcome in ("broken", "stopped", "did_not_finish"):
                        failures += 1
                row["uninterpreted"] = bool(made.get("uninterpreted"))
            report["functions"].append(row)
    finally:
        g["STOP_FILE"] = saved_stop
        Budget.restore(saved_budget)
        shutil.rmtree(home, ignore_errors=True)
    report["failures"] = failures
    report["exit"] = 1 if failures else 0
    return report


def from_contracts_main(argv: list[Any]) -> int:
    """sabline test FILE --from-contracts [--count N] [--witness-seconds S]
    [--json]"""
    usage = ("usage: sabline test program.vel --from-contracts [--count N] "
             "[--witness-seconds S] [--json]")
    files, as_json = [], False
    count, seconds = WITNESS_COUNT_DEFAULT, WITNESS_SECONDS_DEFAULT
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--count", "--witness-seconds"):
            try:
                if a == "--count":
                    count = int(argv[i + 1])
                    if not 1 <= count <= WITNESS_COUNT_MOST:
                        raise ValueError
                else:
                    seconds = float(argv[i + 1])
                    if not 0 < seconds <= 600:
                        raise ValueError
            except (IndexError, ValueError):
                print(f"sabline test: {a} needs a number: --count from 1 to "
                      f"{WITNESS_COUNT_MOST}, --witness-seconds above 0 and "
                      f"at most 600", file=sys.stderr)
                return 2
            i += 2
            continue
        if a == "--json":
            as_json = True
        elif a == "--from-contracts":
            pass
        elif a.startswith("-"):
            print(usage, file=sys.stderr)
            return 2
        else:
            files.append(a)
        i += 1
    if len(files) != 1:
        print(usage, file=sys.stderr)
        return 2
    report = from_contracts(files[0], count, seconds)
    if as_json:
        print(json.dumps(report, indent=2))
        return int(report["exit"])
    print(f"sabline test --from-contracts: {files[0]} (up to {count} "
          f"witness(es) a function from the prover, run interpreted with no "
          f"effect granted)")
    for p in report["problems"]:
        print(f"  NOT RUN  {p}")
    for row in report["functions"]:
        if row["refused"]:
            print(f"  {row['function']}: REFUSED - {row['refused']}")
            continue
        if row["skipped"] and not row["witnesses"]:
            print(f"  {row['function']}: skipped - {row['skipped']}")
            continue
        bad = [w for w in row["witnesses"] if w["outcome"] not in
               ("passed", "not_a_witness")]
        print(f"  {row['function']} ({row['status']}): "
              f"{len(row['witnesses'])} witness(es), {row['passed']} passed"
              + (f", {len(bad)} FAILED" if bad else ""))
        for w in row["witnesses"]:
            if w["outcome"] == "passed":
                continue
            label = {"broken": "BROKEN", "stopped": "STOPPED",
                     "did_not_finish": "DID NOT FINISH",
                     "not_a_witness": "not a witness"}[w["outcome"]]
            print(f"      {label}  {w['args']}: {w['detail']}")
            if w["outcome"] == "not_a_witness":
                print("          the requires did not hold when run"
                      + (": it names a function the prover does not model"
                         if row.get("uninterpreted") else ""))
    run = sum(1 for r in report["functions"] if r["witnesses"])
    print(f"{len(report['functions'])} function(s) with requires: {run} run"
          + (f", {report.get('failures', 0)} witness(es) FAILED"
             if report.get("failures") else ", no promise broken"))
    return int(report["exit"])
