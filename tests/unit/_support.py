"""What the stage-isolated unit tests share (release 8.2, item 4).

Where the repository and each stage's fixtures are, the case-file format
several stages use, and one way to run a deep parse. Importing this
module imports no part of the compiler: each test module imports its own
stage, and the earlier stages that build its input.

A case file holds several small programs. Each opens with a marker line

    // ==== name

and says what it expects in comment lines of its own:

    // expect: ok              nothing is reported
    // expect: refused         something is reported, whatever its code
    // expect: E300 line 4     this error; several lines, in this order
    // expect: proven f        (prover) f's promises are proven
    // expect: runtime g       (prover) g's are left to runtime checks
    // discrepancy: why        SPEC.md or LLM.md says what the expect
                               lines say and the stage does otherwise;
                               the test asserts the documents and is
                               marked an expected failure

A case's source is every line after its marker, so line 1 is the line
after the marker and an expect line's line number counts from there.
Every one of these lines is a comment to the lexer.
"""
import os
import re
import sys
import threading
import unittest
from dataclasses import dataclass, field
from typing import Any

UNIT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(UNIT_DIR))
FIXTURES = os.path.join(UNIT_DIR, "fixtures")
STDLIB = os.path.join(REPO, "stdlib")

# this checkout's compiler, never one installed elsewhere
if sys.path[:1] != [REPO]:
    sys.path.insert(0, REPO)


def fixture(stage: str, *parts: str) -> str:
    """The path of a fixture of `stage`."""
    return os.path.join(FIXTURES, stage, *parts)


def read_fixture(stage: str, *parts: str) -> str:
    with open(fixture(stage, *parts), encoding="utf-8") as f:
        return f.read()


def same_path(a: str, b: str) -> bool:
    return os.path.normcase(os.path.realpath(a)) == \
        os.path.normcase(os.path.realpath(b))


@dataclass
class Case:
    name: str
    file: str
    line: int                        # the marker's line in its file
    source: str
    errors: list[Any] = field(default_factory=list)      # [(code, line)]
    proven: set[Any] = field(default_factory=set)
    runtime: set[Any] = field(default_factory=set)
    refused: bool = False
    discrepancy: str = ""


MARKER = re.compile(r"^// ==== ([A-Za-z0-9_]+)\s*$")
EXPECT = re.compile(r"^\s*// expect: (.*?)\s*$")
DISCREPANCY = re.compile(r"^\s*// discrepancy: (.*?)\s*$")


def load_cases(stage: str, filename: str) -> list[Any]:
    """The cases of one case file, in file order."""
    lines = read_fixture(stage, filename).split("\n")
    cases: list[Case]
    body: list[str]
    cases, current, body = [], None, []

    def close() -> None:
        if current is None:
            return
        current.source = "\n".join(body) + "\n"
        said_ok = False
        for text in body:
            m = EXPECT.match(text)
            if m:
                said = m.group(1)
                if said == "ok":
                    said_ok = True
                elif said == "refused":
                    current.refused = True
                elif re.fullmatch(r"E\d{3} line \d+", said):
                    code, _, at = said.split()
                    current.errors.append((code, int(at)))
                elif re.fullmatch(r"(proven|runtime) [A-Za-z_][\w.#]*", said):
                    kind, name = said.split()
                    getattr(current, kind).add(name)
                else:
                    raise ValueError(f"{filename}, case '{current.name}': "
                                     f"cannot read 'expect: {said}'")
            d = DISCREPANCY.match(text)
            if d:
                current.discrepancy = d.group(1)
        said_more = (current.errors or current.proven or current.runtime
                     or current.refused)
        if said_ok and said_more:
            raise ValueError(f"{filename}, case '{current.name}': 'ok' "
                             f"beside other expectations")
        if not (said_ok or said_more):
            raise ValueError(f"{filename}, case '{current.name}' expects "
                             f"nothing")
        cases.append(current)

    for number, text in enumerate(lines, 1):
        m = MARKER.match(text)
        if m:
            close()
            current, body = Case(m.group(1), filename, number, ""), []
        elif current is not None:
            body.append(text)
        elif text.strip() and not text.lstrip().startswith("//"):
            raise ValueError(f"{filename}, line {number}: code before the "
                             f"first case marker")
    close()
    names = [c.name for c in cases]
    if len(names) != len(set(names)):
        raise ValueError(f"{filename}: two cases share a name")
    return cases


def add_case_tests(cls: Any, stage: str, filename: str, check: Any) -> None:
    """One test method on `cls` per case of the file, named
    test_<file>__<case>, calling check(self, case). A case with a
    discrepancy line is an expected failure."""
    stem = os.path.splitext(filename)[0]
    for case in load_cases(stage, filename):
        name = f"test_{stem}__{case.name}"
        if hasattr(cls, name):
            raise ValueError(f"{cls.__name__} already has {name}")

        def test(self: Any, case: Any = case) -> None:
            check(self, case)

        test.__name__ = name
        test.__doc__ = (f"{stage}/{filename}, case '{case.name}' "
                        f"(line {case.line})"
                        + (f" - documented, not done: {case.discrepancy}"
                           if case.discrepancy else ""))
        if case.discrepancy:
            test = unittest.expectedFailure(test)
        setattr(cls, name, test)


def quiet_unclosed_source_files() -> None:
    """Silence the ResourceWarning sabline/loader.py causes. It reads each
    source with open(path).read() and leaves the file for the garbage
    collector to close, which unittest's warning filter prints once per
    file read. That is reported with these tests, not tested by them.
    Call it from setUpModule, where it outlasts the runner's own filter."""
    import warnings
    warnings.filterwarnings("ignore", category=ResourceWarning,
                            message=r"unclosed file",
                            module=r"sabline\.loader")


def codes_and_lines(errors: Any) -> list[Any]:
    return [(e.code, e.line) for e in errors]


def describe(errors: Any) -> str:
    return "\n".join(f"  {e.code} line {e.line}: {e.message}"
                     for e in errors) or "  (none)"


def on_big_stack(fn: Any, recursion_limit: int = 20000) -> Any:
    """fn() on a thread with a 64 MiB C stack, under a raised recursion
    limit, returning or raising what it did.

    The parser caps nesting at EXPR_NEST_LIMIT and the pipeline raises
    Python's recursion limit to walk a tree that deep (load_program).
    CPython 3.10 on Windows overflows its main thread's C stack a few
    hundred brackets in, well short of the cap, and the process dies
    without an error; the command line checks where that cannot happen
    (see sabline/runtime.py, _run_on_big_stack), and so do these tests."""
    box: dict[Any, Any] = {}

    def work() -> None:
        try:
            box["value"] = fn()
        except BaseException as e:           # re-raised on this thread
            box["error"] = e

    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old_limit, recursion_limit))
    try:
        previous = None
        for size in (64 * 1024 * 1024, 32 * 1024 * 1024):
            try:
                previous = threading.stack_size(size)
                break
            except (ValueError, RuntimeError, OverflowError):
                continue
        try:
            worker = threading.Thread(target=work, name="unit-big-stack")
            worker.start()
        finally:
            if previous is not None:
                threading.stack_size(previous)
        worker.join()
    finally:
        sys.setrecursionlimit(old_limit)
    if "error" in box:
        raise box["error"]
    return box.get("value")
