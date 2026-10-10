"""The canonical run document: what `sabline <file>` does with one program
- its output, its exit status, and the error it stopped with - written so
that a second implementation can be held to it (9.0, M3).

`sabline run-dump --list <paths-file>` writes it from here; `sabline-rt
run --install-dir DIR --list <paths-file>` writes it from the Rust crate.
`check_agreement.py` compares the two over every Sabline source this
project has, the way it compares the check document
(sabline/check_dump.py). It is not a stable interface and is not in
`tests/api/golden.json`: it is a comparison surface, and STABILITY.md's
"anything else in the package" clause covers it.

**What a run here is** is what `sabline <file>` does (cli.py's `_cli_run`)
with five things fixed, so that the same program gives the same document
on every machine and in both runtimes:

    the budget      io, the budget a run with no --allow gets (5.0) -
                    unless the list gives one (below)
    the input       STDIN, read by read_line and ask as the library's
                    `stdin=` is (a StringIO: lines end at \\n alone)
    the arguments   ARGS, what args() answers
    a step limit    STEPS calls and loop turns, after which the run is
                    stopped where it is: a program that does not end
                    stops at the same call or loop turn in both runtimes,
                    which a wall-clock limit cannot promise
    a size limit    SIZE of what the run makes - a text's UTF-8 bytes, a
                    list's or a map's items, counted as runtime.size_of
                    says - after which the run is stopped at the operation
                    that went past it: a program that grows without end
                    stops at the same operation in both, where memory
                    would stop each where its own machine ran out. What an
                    operation writes out is counted before it is made
                    (runtime.ahead), so no one operation makes a value far
                    past it

**A line of the list** is a program's path, run as above; or a JSON object
naming one, `{"path": ...}`, with any of what a command line could add:

    allow, deny     the budget, as --allow and --deny give it
    seed            --seed: what random() is seeded with
    freeze_time     --freeze-time, as epoch seconds: what now() answers
    max_read        the read ceiling, in bytes (--max-read gives megabytes)
    environ         variables set for the run, {name: value}, over the
                    environment the process was started with: what env()
                    reads, and where `~` is
    steps, size     limits of the line's own, in place of STEPS and SIZE:
                    what the differential fuzzer runs under (fuzz_parsers.py
                    --target agreement_runs), which the gate never gives

The document does not repeat them: the gate gives both runtimes the same
line. A budget that does not parse is the document's `raised`,
"BudgetError", and nothing runs.

and with three things left out, each because sabline-rt does not have it
in 9.0: the prover (decisions/0002 keeps it in Python; a run here is
checked as `_cli_run` checks it, less `check_proofs`, so every promise is
left to the run - the lie corpus's point), native code (`--no-native`;
`fuzz_native.py` holds the two engines of the Python runtime to each
other), and the operating system's confinement (M4).

**What is in it:**

    refused     the problems the check found, as `_cli_run` reports them -
                one each, sorted by file and line - when it found any;
                else null and the program ran
    error       the error the run stopped with - code, message, file,
                line, fixes - or null
    exit        the exit status: 0, 1 for an error, exit_with's number;
                null when a limit stopped the run
    stdout      everything the program printed, as text
    stderr      everything it wrote to the error channel (log), as text
    stopped     the line a limit stopped the run at, or null
    stopped_by  which: "steps" or "size", or null
    raised      the name of a Python exception that escaped the run, which
                is a defect in the reference, or null

Text is compared as text - code points, lone surrogates included - and
written as ASCII JSON, so a document says exactly what was printed
whatever the console would have made of it.

**The receipt** (M3, third checkpoint). Each run's document is followed in
the stream by its sabline.receipt/1 Statement - what `sabline <file>
--receipt FILE` writes (cli.py's `_cli_run_with_receipt`), recorded the
same way, of the same run: its subjects by digest, the budget, the run's
parameters, what each effect and grant let through, every refusal and
declassification by line and count, and how it ended. `null` where the
command line would write none: a budget that does not parse, and a Python
exception that escaped the run. Three things differ from a receipt the
command line writes, each because of what the run document fixes:
nothing is asked of the operating system, so the confinement is `none`
with the reason that says so, in both runtimes; a run the step limit stops
is recorded as a timeout (E610) and one the size limit stops as out of
memory (E611), which is how each would have ended without the limit, with
what it used and refused until then; and a frozen clock outside the
years 1 to 9999, which an instant in a receipt cannot say, has no
receipt. check_agreement.py
compares the receipts after normalising exactly plan/9.0.md's list - the
producer's name and version, startedAt, wall_time_ms, a `<source>`
subject's name, and the confinement fields by rule - and nothing else.

**The audit stream** (decisions/0007, 32b) follows the receipt: the same
run's events, as `--audit-stream` writes them a line each, here as one list
- `start`, `subjects`, each `effect`, `grant`, `refusal` and `declassify` as
it happened, and `end` with the receipt - or `null` where the receipt is.
The gate compares it event for event, normalising in `start` and in the
receipt `end` carries exactly what it normalises in a receipt.
"""
import contextlib
import io
import json
import os
import posixpath
import sys
import time
from typing import TYPE_CHECKING, Any

from . import state as _state
from .ast_dump import RECURSION_LIMIT, _out, canonical
from .budget import Budget, BudgetError, cli_budget, set_run_params
from .checker import check_types
from .effects import check_effects
from .errors import SablineError, _too_deep_error
from .loader import load_program
from .parser import Parser
from .pool import reset_program_state
from .recorder import _note_error, _note_stop, _RunRecorder, _utc_now_ms
from .results import Problem, RunResult
from .runtime import SizeLimit, StepLimit, interpret
from .tables import DEFAULT_ALLOW
from .values import FailSignal

if TYPE_CHECKING:
    from .receipts import (_receipt_subjects, _run_parameters,
                           receipt_statement, stream_end, stream_start)

# Used inside functions only, from modules after this one: sabline/__init__.py
# binds each here once every module is loaded.
__forward__ = {
    "_receipt_subjects": "receipts",
    "_run_parameters": "receipts",
    "receipt_statement": "receipts",
    "stream_end": "receipts",
    "stream_start": "receipts",
}

USAGE = """usage: sabline run-dump --list <paths-file>

Each line of the file is a program's path, or a JSON object naming one with
the budget, seed, frozen clock and read ceiling to run it under:
{"path": ..., "allow": ..., "deny": ..., "seed": ..., "freeze_time": ...,
"max_read": ...}.

The canonical run document: what `sabline <file>` does with each program,
without the prover, native code or the operating system's confinement,
under the budget io with a fixed input, fixed arguments, a step limit and
a size limit, which check_agreement.py compares with sabline-rt's - each
followed by the run's receipt. rt/README.md states the format. It is not a
stable interface and nothing else reads it.

Exit 0 when every program ran to its end with status 0, 1 when one did
not, 2 when the command line itself was wrong."""

# The format's version, carried in every document: 2 from the size limit,
# whose stop the document names in `stopped_by`.
RUN_VERSION = 2

# The header of the framed stream `--list` writes; the records are framed
# as the AST dump's are, three for each program: its run document, its
# receipt, and its audit stream as a list of events (3, from the stream;
# 2 added the receipt).
BATCH_HEADER = "sabline.run-batch/3"

# What read_line and ask read. Three lines and then the end of the input,
# so that a loop over the input runs and then leaves, and one that waits
# for a line it is never given meets the end.
STDIN = "1\n2\nthree\n"

# What args() answers.
ARGS = ("first", "2")

# How many calls and loop turns before a run is stopped. Every program the
# gate holds that ends, ends well inside it.
STEPS = 20000

# How much a run may make before it is stopped, counted as runtime.size_of
# counts it: 4,194,304. Every program the gate holds that ends makes less
# than a fortieth of that (the most, on 2026-10-09: 100,000, a literal of a
# hundred thousand characters, printed); a text doubled from sixteen bytes
# passes it on its eighteenth doubling. A program that grows without end
# is stopped here rather than by the step limit, and well before either
# runtime's memory is a question.
SIZE = 1 << 22


def _error(e: SablineError, path: str) -> dict[str, Any]:
    """One error as `sabline --json` writes it, less `reference`."""
    return {"code": e.code, "file": e.file or path, "fixes": list(e.fixes),
            "line": e.line, "message": e.message}


def run_document(path: str, allow: str | None = None, deny: str | None = None,
                 seed: int | None = None, freeze_time: int | None = None,
                 max_read: int | None = None,
                 environ: dict[str, str] | None = None,
                 steps: int | None = None,
                 size: int | None = None) -> dict[str, Any]:
    """The document for one program, run as `sabline <path>` runs it, with
    the five things above fixed - the budget, seed, clock and read ceiling
    as given - and the three left out."""
    return run_recorded(path, allow=allow, deny=deny, seed=seed,
                        freeze_time=freeze_time, max_read=max_read,
                        environ=environ, steps=steps, size=size)[0]


def run_recorded(path: str, allow: str | None = None,
                 deny: str | None = None, seed: int | None = None,
                 freeze_time: int | None = None,
                 max_read: int | None = None,
                 environ: dict[str, str] | None = None,
                 steps: int | None = None, size: int | None = None
                 ) -> tuple[dict[str, Any], dict[str, Any] | None,
                            list[dict[str, Any]] | None]:
    """The run document, the receipt of the same run (the module's
    docstring says how it differs from the command line's) and its audit
    stream, each event as a dict - the last two None where the command
    line writes no receipt."""
    if sys.getrecursionlimit() < RECURSION_LIMIT:
        try:
            sys.setrecursionlimit(RECURSION_LIMIT)
        except Exception:
            pass
    Parser.lambda_n = 0
    document: dict[str, Any] = {"run": RUN_VERSION, "refused": None,
                                "error": None, "exit": 0, "stdout": "",
                                "stderr": "", "stopped": None,
                                "stopped_by": None, "raised": None}
    argv = (["--allow", allow] if allow is not None else []) + (
        ["--deny", deny] if deny is not None else [])
    try:
        budget = cli_budget(argv)
    except BudgetError:
        document["raised"] = "BudgetError"
        document["exit"] = None
        return document, None, None
    # read before the run, as the command line reads it for the receipt
    try:
        with open(path, "rb") as fh:
            entry_bytes = fh.read()
    except OSError:
        entry_bytes = b""
    reset_program_state(budget)
    set_run_params(seed, freeze_time)
    loaded: list[Any] = []
    limit = None
    overlaid = {name: os.environ.get(name) for name in environ or {}}
    os.environ.update(environ or {})
    ceiling = _state.MAX_READ_BYTES
    if max_read is not None:
        vars(_state)["MAX_READ_BYTES"] = max_read
    try:
        # nothing is asked of the operating system: the confinement is
        # none, and says why (the module's docstring)
        parameters: dict[str, Any] | None = _run_parameters(
            _state.SEED, _state.FROZEN_TIME, None, None, confinement={})
    except (ValueError, OverflowError, OSError):
        parameters = None                      # no instant: no receipt
    events: list[dict[str, Any]] = []
    recorder = _RunRecorder(stream=events.append if parameters else None)
    name = posixpath.normpath(path.replace(os.sep, "/"))
    _state.PROGRAM_ARGS[:] = list(ARGS)
    vars(_state)["_STEP_LIMIT"] = STEPS if steps is None else steps
    vars(_state)["_SIZE_LIMIT"] = SIZE if size is None else size
    vars(_state)["BEFORE_FIRST_STATEMENT"] = None
    vars(_state)["RUN_RECORDER"] = recorder
    out, err = io.StringIO(), io.StringIO()
    old_stdin = sys.stdin
    running = False
    started_at, t0 = _utc_now_ms(), time.monotonic()
    if parameters is not None:
        stream_start(recorder, budget=budget.spec(), parameters=parameters,
                     started_at=started_at)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            sys.stdin = io.StringIO(STDIN)
            try:
                try:
                    funcs, records = load_program(path, loaded=loaded)
                finally:
                    # the audit stream's subjects, once loading is over
                    if loaded and recorder.stream is not None:
                        recorder.set_subjects(_receipt_subjects(
                            path, name, entry_bytes, loaded))
                errors: list[SablineError] = []
                check_effects(funcs, errors)
                check_types(funcs, records, errors)
                if errors:
                    # one each, in file and line order: what _cli_run prints
                    seen, unique = set(), []
                    for e in errors:
                        key = (e.code, e.file or path, e.line, e.message)
                        if key not in seen:
                            seen.add(key)
                            unique.append(e)
                    unique.sort(key=lambda e: (e.file or path, e.line))
                    document["refused"] = [_error(e, path) for e in unique]
                    document["exit"] = 1
                    _note_stop(unique[0].code, unique[0].line)
                else:
                    recorder.compiled = True
                    running = True
                    interpret(funcs, {})
            except SystemExit as e:
                document["exit"] = (e.code if isinstance(e.code, int)
                                    else 0 if e.code is None else 1)
            except SablineError as e:
                _note_error(e)
                document["error"] = _error(e, path)
                document["exit"] = 1
            except RecursionError:
                deep = _too_deep_error(running)
                _note_error(deep)
                document["error"] = _error(deep, path)
                document["exit"] = 1
            except StepLimit as e:
                document["stopped"] = e.line
                document["stopped_by"] = "steps"
                document["exit"] = None
                limit = "steps"
            except SizeLimit as e:
                document["stopped"] = e.line
                document["stopped_by"] = "size"
                document["exit"] = None
                limit = "size"
            except (FailSignal, Exception) as e:   # a defect in the reference
                document["raised"] = type(e).__name__
                document["exit"] = None
        wall_time_ms = (time.monotonic() - t0) * 1000
        # what the receipt reads of the run, before it is all put back
        recorder.close()
        effects_used = dict(_state.EFFECT_USES)
    finally:
        vars(_state)["RUN_RECORDER"] = None
        sys.stdin = old_stdin
        vars(_state)["_STEP_LIMIT"] = None
        vars(_state)["_SIZE_LIMIT"] = None
        vars(_state)["MAX_READ_BYTES"] = ceiling
        for variable, was in overlaid.items():
            if was is None:
                os.environ.pop(variable, None)
            else:
                os.environ[variable] = was
        reset_program_state(Budget.parse(DEFAULT_ALLOW))
    document["stdout"] = out.getvalue()
    document["stderr"] = err.getvalue()
    if document["raised"] is not None or parameters is None:
        return document, None, None            # the command line wrote none
    if loaded:
        recorder.subjects = _receipt_subjects(path, name, entry_bytes, loaded)
    stop = recorder.stop or {}
    status = document["exit"]
    result = RunResult(status == 0 and not stop, "", "",
                       [Problem(stop["code"], "", stop.get("line"), path, [])]
                       if stop else [], None, status,
                       timed_out=limit == "steps",
                       out_of_memory=limit == "size",
                       effects_used=effects_used)
    receipt = receipt_statement(
        recorder, name=name, entry_bytes=entry_bytes, budget=budget.spec(),
        parameters=parameters, result=result, started_at=started_at,
        wall_time_ms=wall_time_ms)
    stream_end(recorder, receipt)
    return document, receipt, events


def run_dump_main(argv: Any) -> int:
    """`sabline run-dump --list <paths-file>`."""
    words = list(argv)
    if not words or words[0] in ("--help", "-h"):
        print(USAGE)
        return 0
    if words[:1] == ["--list"] and len(words) == 2:
        try:
            with open(words[1], encoding="utf-8") as fh:
                listed = fh.read()
        except OSError as e:
            print(f"sabline run-dump: cannot read the list '{words[1]}': "
                  f"{e}", file=sys.stderr)
            return 2
        every = True
        _out(BATCH_HEADER.encode("ascii") + b"\n")
        for line in listed.splitlines():
            path = line.rstrip("\r")
            if not path:
                continue
            given: dict[str, Any] = {}
            if path.startswith("{"):
                given = json.loads(path)
                path = given.pop("path")
            document, receipt, events = run_recorded(path, **given)
            every = every and document["exit"] == 0
            for record in (document, receipt, events):
                body = canonical(record).encode("ascii")
                _out(f"--- {len(body)} {path}\n".encode("utf-8"))
                _out(body + b"\n")
        return 0 if every else 1
    print(USAGE, file=sys.stderr)
    return 2
