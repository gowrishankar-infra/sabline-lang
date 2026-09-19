"""velaris replay: a run made again from its receipt, and every difference
named (8.3).
"""
import hashlib
import json
import os
import posixpath
import shutil
import sys
import tempfile

from . import state as _state
from .errors import VelarisError
from .values import FailSignal, log_line
from .budget import Budget, BudgetError, expand_allow
from .library import _run_in_process
from .pool import Pool
from .statements import subject_file
from .receipt_diff import Unread, load_receipt
from .evaluation import EvalRefused, _EvalPool, eval_budget
from typing import Any, cast

# ---------------------------------------------------------------------------
# 19e. REPLAY - the same bytes, the same parameters, the same budget
#
#     `velaris replay RECEIPT` reads each subject the receipt names from disk,
#     refuses if any is missing or is not those bytes, and copies them into a
#     directory of its own before anything runs, so what runs is what was
#     checked: imports are held to that directory, and a file the receipt did
#     not name cannot be imported at all. The run gets the receipt's budget -
#     no more than --max-allow, io unless raised, since a receipt is text
#     from somewhere else - its seed, frozen clock, time and memory limits and
#     read ceiling, and runs under eval's profile when the receipt says it
#     did. The new receipt is compared with the recorded one, field by field;
#     timings and the start time are not compared.
#
#     A receipt holds no output, input or arguments. The program's input and
#     arguments are given again (--stdin FILE, and words after --), and its
#     output is compared only with --expect-output FILE.
#
#     Code mode: a program that calls tools reaches them through Python, as
#     py, py_int, py_float and py_json. `velaris program.vel
#     --record-responses FILE` records what each such call gave back, and
#     `velaris replay --responses FILE` gives those back in the same order in
#     place of calling Python - after the budget and the module grants are
#     checked, as for any call. A call that is not the one recorded in that
#     place stops the run with E616. Handles (py_new, py_do, py_field) are not
#     recorded: they are objects, not answers. Recorded responses are values
#     the program handled; they are never in a receipt.
#
#     Exit 0 when the replay matches, 1 when something differs, 2 when it was
#     refused before running.
# ---------------------------------------------------------------------------

REPLAY_SCHEMA = "velaris.replay/1"            # provisional
RESPONSES_SCHEMA = "velaris.responses/1"      # provisional
REPLAY_MAX_ALLOW_DEFAULT = "io"
RESPONSE_BUILTINS = ("py", "py_int", "py_float", "py_json")
_COMPARED = ("budget", "effects_used", "refusals", "declassifications",
             "exit", "complete", "stop")
_PARAMETERS = ("seed", "freeze_time", "timeout", "max_memory_mb",
               "max_read_bytes", "confinement", "profile")
_MOST_BYTES = 64 * 1024 * 1024


class ResponseLog:
    """--record-responses: each tool call's answer, in order."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def answer(self, builtin: str, call: list[Any], live: Any,
               line: int) -> Any:
        try:
            value = live()
        except FailSignal as e:
            self.calls.append({"builtin": builtin, "call": call,
                               "failed": str(e.reason)})
            raise
        self.calls.append({"builtin": builtin, "call": call,
                           "result": value})
        return value

    def document(self) -> dict[str, Any]:
        return {"schema": RESPONSES_SCHEMA, "calls": self.calls}


class ResponseReplay:
    """--responses: the recorded answers, handed back in order."""

    def __init__(self, calls: list[Any]) -> None:
        self.calls = list(calls)
        self.at = 0

    def answer(self, builtin: str, call: list[Any], live: Any,
               line: int) -> Any:
        if self.at >= len(self.calls):
            raise VelarisError(
                "E616", f"this replayed run made a {self.at + 1}th tool call "
                f"({builtin}), and the recorded responses hold "
                f"{len(self.calls)}", line,
                fixes=["replay the program with the input the recorded run "
                       "had", "or record its responses again"])
        entry = self.calls[self.at]
        self.at += 1
        if entry.get("builtin") != builtin or entry.get("call") != call:
            raise VelarisError(
                "E616", f"tool call {self.at} of this replayed run is "
                f"{builtin} {json.dumps(call)[:120]}, where the recorded run "
                f"made {entry.get('builtin')} "
                f"{json.dumps(entry.get('call'))[:120]}", line,
                fixes=["replay the program with the input the recorded run "
                       "had", "or record its responses again"])
        if "failed" in entry:
            raise FailSignal(str(entry["failed"]))
        return entry.get("result")


def load_responses(path: str) -> ResponseReplay:
    with open(path, "rb") as fh:
        raw = fh.read(_MOST_BYTES + 1)
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise EvalRefused(f"{path} is not a {RESPONSES_SCHEMA} document")
    if not (isinstance(doc, dict) and doc.get("schema") == RESPONSES_SCHEMA
            and isinstance(doc.get("calls"), list)
            and all(isinstance(c, dict) and isinstance(c.get("builtin"), str)
                    and c.get("builtin") in RESPONSE_BUILTINS
                    and ("result" in c or "failed" in c)
                    for c in doc["calls"])):
        raise EvalRefused(f"{path} is not a {RESPONSES_SCHEMA} document")
    return ResponseReplay(doc["calls"])


def snapshot(receipt: dict[str, Any], root: str,
             home: str) -> tuple[str, bytes]:
    """Copy each subject into `home`, after holding it to its digest; (the
    program's path there, its bytes). EvalRefused names what is not the
    receipt's."""
    problems: list[str] = []
    entry: tuple[str, bytes] | None = None
    for index, subject in enumerate(receipt["subject"]):
        name, want = subject["name"], subject["digest"]["sha256"]
        where, why = subject_file(name, root)
        if where is None:
            problems.append(f"{name}: {why}")
            continue
        try:
            if os.path.getsize(where) > _MOST_BYTES:
                problems.append(f"{name}: larger than 64 MiB")
                continue
            with open(where, "rb") as fh:
                data = fh.read()
        except OSError as e:
            problems.append(f"{name}: {e.strerror or e}")
            continue
        found = hashlib.sha256(data).hexdigest()
        if found != want:
            problems.append(f"{name}: the bytes on disk are sha256:"
                            f"{found[:16]}, the receipt names sha256:"
                            f"{want[:16]}")
            continue
        if name.startswith("<stdlib>/"):
            continue                     # read from this installation
        target = os.path.join(home, *posixpath.normpath(name).split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as fh:
            fh.write(data)
        if index == 0:
            entry = (target, data)
    if problems:
        raise EvalRefused("the bytes to replay are not the receipt's - "
                          + "; ".join(problems))
    if entry is None:
        raise EvalRefused("the receipt names no program file to replay")
    return entry


def compare(recorded: dict[str, Any], replayed: dict[str, Any]) -> list[Any]:
    """Every field the two receipts should share and do not."""
    out = []
    names = [(s["name"], s["digest"]["sha256"]) for s in recorded["subject"]]
    again = [(s.get("name"), (s.get("digest") or {}).get("sha256"))
             for s in replayed.get("subject") or []]
    if names != again:
        out.append({"field": "subject", "recorded": names, "replayed": again})
    old, new = recorded["predicate"], replayed["predicate"]
    for field in _COMPARED:
        if old.get(field) != new.get(field):
            out.append({"field": field, "recorded": old.get(field),
                        "replayed": new.get(field)})
    for key in _PARAMETERS:
        a = old["run_parameters"].get(key)
        b = new["run_parameters"].get(key)
        if a != b:
            out.append({"field": f"run_parameters.{key}", "recorded": a,
                        "replayed": b})
    return out


def replay(receipt_path: str, *, root: str = ".", max_allow: str =
           REPLAY_MAX_ALLOW_DEFAULT, stdin: str = "",
           args: list[str] | None = None, expect_output: str | None = None,
           responses: str | None = None) -> dict[str, Any]:
    """The velaris.replay/1 report, with its exit status in 'exit'."""
    report: dict[str, Any] = {"schema": REPLAY_SCHEMA, "receipt": receipt_path,
                              "refused": None, "differences": [],
                              "output_compared": expect_output is not None}
    try:
        receipt = load_receipt(receipt_path)
    except Unread as e:
        report["refused"] = str(e)
        report["exit"] = 2
        return report
    p = receipt["predicate"]
    params = p["run_parameters"]
    home = tempfile.mkdtemp(prefix="velaris-replay-")
    try:
        return _replay(report, receipt, p, params, home, root, max_allow,
                       stdin, list(args or []), expect_output, responses)
    except EvalRefused as e:
        report["refused"] = str(e)
        report["exit"] = 2
        return report
    finally:
        shutil.rmtree(home, ignore_errors=True)


def _replay(report: dict[str, Any], receipt: dict[str, Any],
            p: dict[str, Any], params: dict[str, Any], home: str, root: str,
            max_allow: str, stdin: str, args: list[str],
            expect_output: str | None,
            responses: str | None) -> dict[str, Any]:
    eval_profile = params.get("profile") == "eval"
    try:
        asked = Budget.parse(p["budget"])
        ceiling = Budget.parse(expand_allow(max_allow))
    except BudgetError as e:
        raise EvalRefused(str(e))
    wider = ceiling.covers(asked)
    if wider:
        raise EvalRefused(f"the receipt's budget is wider than --max-allow "
                          f"{max_allow}: "
                          f"{wider.replace('this server', '--max-allow')}")
    if eval_profile:
        eval_budget(p["budget"], None)
    bounded = params.get("timeout") is not None or \
        params.get("max_memory_mb") is not None
    if responses is not None and (bounded or eval_profile):
        raise EvalRefused("recorded responses are given back in this "
                          "process, and this receipt's run had a time or "
                          "memory limit, which runs it in another")
    read_most = params.get("max_read_bytes")
    if (bounded or eval_profile) and read_most not in (
            None, _state.MAX_READ_BYTES):
        raise EvalRefused(f"the receipt's run had a read ceiling of "
                          f"{read_most} bytes, which a run in another process "
                          f"is not given")
    replayer = load_responses(responses) if responses is not None else None
    entry, data = snapshot(receipt, root, home)
    try:
        source = data.decode("utf-8")
    except UnicodeDecodeError:
        raise EvalRefused("the program is not UTF-8 text")
    name = receipt["subject"][0]["name"]
    seed, frozen = params.get("seed"), params.get("freeze_time")
    if eval_profile:
        work = os.path.join(home, ".velaris-tmp")
        os.makedirs(work, exist_ok=True)
        writable = [prefix for kind, prefix in asked.fs or []
                    if kind == "write"] + [work]
        eval_pool = _EvalPool(allow=asked.spec(), timeout=params["timeout"],
                              max_memory_mb=params["max_memory_mb"],
                              import_root=home,
                              stop_file=os.path.join(work, "stop"),
                              writable=writable)
        with eval_pool:
            result = eval_pool.run(source, stdin=stdin, args=args, path=entry,
                                   seed=seed, freeze_time=frozen, _name=name)
        cast("dict[str, Any]", result.receipt)["predicate"][
            "run_parameters"].update(confinement=eval_pool.confinement,
                                     profile="eval")
    elif bounded:
        with Pool(size=1, allow=asked.spec(), timeout=params.get("timeout"),
                  max_memory_mb=params.get("max_memory_mb"),
                  import_root=home) as pool:
            result = pool.run(source, stdin=stdin, args=args, path=entry,
                              seed=seed, freeze_time=frozen, _name=name)
    else:
        g = vars(_state)
        saved = (g["IMPORT_ROOT"], g["MAX_READ_BYTES"], g["RESPONSES"])
        g["IMPORT_ROOT"] = os.path.realpath(home)
        if isinstance(read_most, int):
            g["MAX_READ_BYTES"] = read_most
        g["RESPONSES"] = replayer
        try:
            result = _run_in_process(source, path=entry, budget=asked,
                                     args=args, stdin=stdin, native=True,
                                     seed=seed, freeze_time=frozen, name=name)
        finally:
            g["IMPORT_ROOT"], g["MAX_READ_BYTES"], g["RESPONSES"] = saved
    report["differences"] = compare(receipt,
                                    cast("dict[str, Any]", result.receipt))
    if expect_output is not None:
        with open(expect_output, encoding="utf-8", newline="") as fh:
            expected = fh.read().replace("\r\n", "\n")
        got = result.output.replace("\r\n", "\n")
        if got != expected:
            a, b = expected.split("\n"), got.split("\n")
            at = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y),
                      min(len(a), len(b)))
            report["differences"].append({
                "field": "output", "recorded": expected[:2000],
                "replayed": got[:2000],
                "first_differing_line": at + 1})
    report["output"], report["logs"] = result.output, result.logs
    report["replayed_receipt"] = result.receipt
    report["exit"] = 1 if report["differences"] else 0
    return report


def replay_main(argv: list[Any], program_words: list[str] | None = None) -> int:
    """velaris replay RECEIPT [--root DIR] [--max-allow G] [--stdin FILE]
    [--expect-output FILE] [--responses FILE] [--json] [-- ARGS...]"""
    usage = ("usage: velaris replay <receipt> [--root DIR] [--max-allow G] "
             "[--stdin FILE] [--expect-output FILE] [--responses FILE] "
             "[--json] [-- ARGS]")
    valued = ("--root", "--max-allow", "--stdin", "--expect-output",
              "--responses")
    opts: dict[str, Any] = {}
    receipt = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in valued:
            if i + 1 >= len(argv) or a in opts:
                print(usage, file=sys.stderr)
                return 2
            opts[a] = argv[i + 1]
            i += 2
            continue
        if a == "--json":
            opts[a] = True
        elif a.startswith("-") or receipt is not None:
            print(usage, file=sys.stderr)
            return 2
        else:
            receipt = a
        i += 1
    if receipt is None:
        print(usage, file=sys.stderr)
        return 2
    stdin = ""
    if "--stdin" in opts:
        with open(opts["--stdin"], encoding="utf-8") as fh:
            stdin = fh.read()
    report = replay(receipt, root=opts.get("--root", "."),
                    max_allow=opts.get("--max-allow",
                                       REPLAY_MAX_ALLOW_DEFAULT),
                    stdin=stdin, args=program_words,
                    expect_output=opts.get("--expect-output"),
                    responses=opts.get("--responses"))
    if opts.get("--json"):
        print(json.dumps(report, indent=2, default=str))
        return int(report["exit"])
    if report["refused"]:
        print(log_line(f"velaris replay: refused: {report['refused']}"),
              file=sys.stderr)
        return int(report["exit"])
    sys.stdout.write(report.get("output") or "")
    sys.stderr.write(report.get("logs") or "")
    for d in report["differences"]:
        print(f"  DIFFERS  {d['field']}: recorded {json.dumps(d['recorded'], default=str)[:200]}, "
              f"replayed {json.dumps(d['replayed'], default=str)[:200]}",
              file=sys.stderr)
    print("velaris replay: "
          + ("the same run" if not report["differences"] else
             f"{len(report['differences'])} difference(s)")
          + ("" if report["output_compared"] else
             "; output not compared (a receipt holds none: pass "
             "--expect-output FILE)"), file=sys.stderr)
    return int(report["exit"])
