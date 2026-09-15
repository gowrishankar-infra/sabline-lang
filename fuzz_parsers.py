#!/usr/bin/env python3
"""Coverage-guided fuzzing of the parts of Velaris that read what they are given.

A Velaris error is a VelarisError with a stable code, and a fallible
builtin fails with FailSignal. Anything else that escapes - a Python
traceback, a RecursionError, a process that dies or stops making progress
- is a bug, whatever the input. Five targets:

    parser     lex, parse, then check_effects / check_types, on arbitrary
               text and on mutated real programs (examples/, stdlib/)
    json       json_get, json_int, json_float, json_len, json_has (and
               json_of) on arbitrary documents and paths
    csv        stdlib/csv.vel - fields, rows_of, column, column_int,
               line_of - run by the interpreter, so split and to_int too
    py_json    py_json (and py, py_int, py_float) turning arbitrary Python
               values back into Velaris values
    contracts  generated signatures with requires / ensures, well- and
               ill-typed, through check_effects / check_types /
               check_proofs (needs z3-solver; skipped without it)

    python fuzz_parsers.py 30               30 iterations per target
    python fuzz_parsers.py --minutes 20     a time budget, split evenly
    python fuzz_parsers.py 500 --seed 7     reproducible
    python fuzz_parsers.py --target json    one target
    python fuzz_parsers.py --engine builtin (or atheris)
    python fuzz_parsers.py --target json --minimize <saved input>

The engine is atheris when it can be imported (it does not support
Windows). Otherwise it is a small coverage-guided loop of its own: a seed
corpus, byte- and token-level mutations, line coverage of Velaris
(sys.monitoring on 3.12+, sys.settrace before), and an input kept in the
corpus whenever it reaches a line no input reached before. Velaris is
whatever `import velaris` finds: one velaris.py, or a velaris/ package.

Each target runs in a child process that writes the input it is about to
try to a journal first, so an input that kills the process outright (a C
stack overflow, a native crash) or stops it making progress for
--hang-seconds is still caught and saved, and a new child carries on.
Findings are saved to crashes/ in the work directory, which is removed at
exit; --crashes DIR keeps them. An input that took 10s or more is saved
there too and reported, but is not a finding. Exit 1 if there was any
finding, 0 otherwise. Nothing here touches the network.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import random
import re
import struct
import subprocess
import sys
import time
import traceback
import types
from pathlib import Path
from typing import Any, Callable, Iterator, cast

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from suite_dirs import isolate  # noqa: E402

TARGETS = ("parser", "json", "csv", "py_json", "contracts")

# A child is given its parent's work directory; only the parent makes one.
if "--work" in sys.argv[1:-1]:
    WORK = Path(sys.argv[sys.argv.index("--work") + 1])
else:
    WORK = isolate("fuzz_parsers")

V: Any = None            # velaris, imported by the child that fuzzes it
VFILES: dict[Any, Any] = {}        # its files (velaris_files), for coverage and blame
PROOF_SECONDS = 0.25     # per prover query: a fuzzed promise is not worth more
MAX_RESTARTS = 10        # process deaths per target before it is given up
PROGRESS_SECONDS = 15.0  # how often a child reports, so a death loses little
SLOW_SECONDS = 10.0      # an input this slow is saved and reported
FFI_MODULE = "velaris_fuzz_ffi"
NULL_OUT = open(os.devnull, "w", encoding="utf-8", errors="replace")


def load_velaris(instrument: bool = False) -> Any:
    global V, VFILES
    if instrument:
        import atheris
        with atheris.instrument_imports(include=["velaris"]):
            import velaris
    else:
        import velaris
    V, VFILES = velaris, velaris_files(velaris)
    return velaris


def velaris_global(function_name: str) -> dict[Any, Any]:
    """The namespace the run state is read from: velaris/state.py, which
    every module of the package reads as _state.NAME (8.2), or, for a
    single-file velaris.py, that function's own globals. Writing
    `velaris.EFFECT_BUDGET = ...` would only set an attribute of the
    package; writing here reaches what the runtime reads."""
    state = getattr(V, "state", None)
    if state is not None and hasattr(state, "EFFECT_BUDGET"):
        return cast(dict[Any, Any], vars(state))
    return cast(dict[Any, Any], getattr(V, function_name).__globals__)


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def ascii_text(s: object, limit: int = 300) -> str:
    s = str(s)
    if len(s) > limit:
        s = s[:limit] + "..."
    return s.encode("ascii", "backslashreplace").decode("ascii")


def preview(data: bytes, limit: int = 240) -> str:
    r = repr(data)
    return r if len(r) <= limit else r[:limit] + "...'"


def as_text(data: bytes) -> str:
    """Bytes as the text a Velaris value would hold; lone surrogates survive."""
    try:
        return data.decode("utf-8", "surrogatepass")
    except UnicodeDecodeError:
        return data.decode("utf-8", "replace")


def as_bytes(text: str) -> bytes:
    return text.encode("utf-8", "surrogatepass")


def velaris_files(module: Any) -> dict[Any, Any]:
    """The files that are Velaris, found from where it was imported: every
    .py file beside a package's __init__.py, or else the one module file.
    Keyed by normcase(realpath); the value is a short name for reports."""
    origin = Path(module.__file__)
    files = sorted(origin.parent.glob("*.py")) if origin.name == "__init__.py" \
        else [origin]
    return {os.path.normcase(os.path.realpath(str(p))): p.name for p in files}


_FILE_KEYS: dict[Any, Any] = {}


def file_key(filename: Any, files: dict[Any, Any]) -> Any:
    """The short name of `filename` when it is one of `files`, else None."""
    key = _FILE_KEYS.get(filename, False)
    if key is False:
        try:
            key = files.get(os.path.normcase(os.path.realpath(filename)))
        except (TypeError, ValueError, OSError):
            key = None
        _FILE_KEYS[filename] = key
    return key


def child_seed(seed: int, index: int, run: int) -> int:
    return (seed * 1000003 + index * 7919 + run * 104729) % (1 << 32)


# ---------------------------------------------------------------------------
# line coverage of Velaris
# ---------------------------------------------------------------------------

class LineCoverage:
    """The lines of Velaris reached so far, as (file name, line); `fresh`
    counts new ones. A file counts when velaris_files() names it, so the
    one-file layout and the package layout are measured the same way."""

    def __init__(self, files: dict[Any, Any]) -> None:
        self.files = files
        self.seen: set[Any] = set()
        self.fresh = 0
        self.method = "sys.monitoring" if hasattr(sys, "monitoring") \
            else "sys.settrace"
        self._tool: int | None = None
        self._tracer: Callable[[Any, Any, Any], Any] | None = None

    def install(self) -> None:
        if self.method == "sys.monitoring" and self._monitor():
            return
        self.method = "sys.settrace"
        self._settrace()

    def _monitor(self) -> bool:
        mon = sys.monitoring  # type: ignore[attr-defined]  # 3.12+ (hasattr above); mypy checks as 3.10
        for tool in (mon.COVERAGE_ID, 5, 4, 3):
            if mon.get_tool(tool) is None:
                break
        else:
            return False
        mon.use_tool_id(tool, "fuzz_parsers")
        seen, files, disable = self.seen, self.files, mon.DISABLE
        cov = self

        def on_line(code: Any, line: Any) -> Any:
            key = file_key(code.co_filename, files)
            if key is not None and (key, line) not in seen:
                seen.add((key, line))
                cov.fresh += 1
            return disable          # each location reports once, then costs nothing

        mon.register_callback(tool, mon.events.LINE, on_line)
        mon.set_events(tool, mon.events.LINE)
        self._tool = tool
        return True

    def _settrace(self) -> None:
        seen, files = self.seen, self.files
        lines_of: dict[Any, set[Any]]
        done, lines_of = set(), {}
        cov = self

        def local(frame: Any, event: Any, arg: Any) -> Any:
            if event == "line":
                code = frame.f_code
                at = (file_key(code.co_filename, files), frame.f_lineno)
                if at not in seen:
                    seen.add(at)
                    cov.fresh += 1
                    todo = lines_of.get(code)
                    if todo is None:
                        todo = lines_of[code] = {
                            (at[0], n) for _, _, n in code.co_lines() if n is not None}
                    if todo <= seen:
                        done.add(code)      # nothing left to learn in it
            return local

        def on_call(frame: Any, event: Any, arg: Any) -> Any:
            code = frame.f_code
            if code in done:
                return None
            return local if file_key(code.co_filename, files) is not None else None

        self._tracer = on_call
        sys.settrace(on_call)

    def ensure(self) -> None:
        """A tracer that raised (a RecursionError in it) is dropped by
        Python; put it back."""
        if self._tracer is not None and sys.gettrace() is not self._tracer:
            sys.settrace(self._tracer)

    def uninstall(self) -> None:
        if self._tool is not None:
            sys.monitoring.set_events(self._tool, 0)  # type: ignore[attr-defined]  # 3.12+; mypy checks as 3.10
            sys.monitoring.free_tool_id(self._tool)  # type: ignore[attr-defined]  # 3.12+; mypy checks as 3.10
            self._tool = None
        if self._tracer is not None:
            sys.settrace(None)
            self._tracer = None


# ---------------------------------------------------------------------------
# journal (child writes, parent reads) and events
# ---------------------------------------------------------------------------

class Journal:
    """The input about to run, written before it runs: 16 bytes of header
    (iteration, length) and the input. Survives the process dying."""

    def __init__(self, path: Path) -> None:
        flags = os.O_RDWR | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0)
        self.fd = os.open(str(path), flags, 0o600)

    def note(self, n: int, data: bytes) -> None:
        os.lseek(self.fd, 0, 0)
        os.write(self.fd, struct.pack("<QQ", n, len(data)) + data)


def read_journal(path: Path, head_only: bool = False) -> tuple[Any, ...] | None:
    try:
        with open(path, "rb") as fh:
            head = fh.read(16)
            if len(head) < 16:
                return None
            n, size = struct.unpack("<QQ", head)
            if head_only:
                return n, None
            return n, fh.read(size)
    except OSError:
        return None


class Events:
    def __init__(self, path: Any) -> None:
        self.path = path

    def write(self, doc: dict[Any, Any]) -> None:
        if self.path:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(doc) + "\n")


def read_events(path: Path) -> list[Any]:
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


# ---------------------------------------------------------------------------
# findings
# ---------------------------------------------------------------------------

def signature(exc: Any) -> str:
    frames = traceback.extract_tb(exc.__traceback__)
    mine = [f for f in frames if file_key(f.filename, VFILES) is not None]
    where = mine[-1] if mine else (frames[-1] if frames else None)
    kind = type(exc).__name__
    if where is None:
        return kind
    if isinstance(exc, RecursionError) and \
            sum(f.name == where.name for f in mine) > 1:
        return f"{kind} in {where.name}"     # Velaris recursing: the line wanders
    return (f"{kind} at {os.path.basename(where.filename)}:{where.lineno} "
            f"in {where.name}")


def traceback_tail(exc: Any, lines: int = 8) -> list[Any]:
    text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return [ascii_text(t) for t in text.splitlines()[-lines:]]


class Findings:
    """One entry per signature; the smallest input for each is kept.
    `known` (signature -> size) is what earlier children of this run found:
    those are not announced again."""

    def __init__(self, target: str, crashes: Path, events: Events, known: Any = None) -> None:
        self.target, self.crashes, self.events = target, crashes, events
        self.best: dict[Any, Any] = dict(known or {})
        self.hits = 0

    def record(self, data: bytes, exc: Any) -> None:
        self.hits += 1
        sig = signature(exc)
        first = sig not in self.best
        if not first and len(data) >= self.best[sig]:
            return
        self.best[sig] = len(data)
        tail = traceback_tail(exc)
        name = hashlib.sha1(sig.encode()).hexdigest()[:10]
        path = self.crashes / f"{self.target}-{name}.bin"
        try:
            self.crashes.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.with_suffix(".txt").write_text(
                sig + "\n\n" + "\n".join(tail) + "\n", encoding="ascii")
        except OSError as e:
            print(f"  (could not save the input: {ascii_text(e)})", flush=True)
        self.events.write({"event": "finding", "signature": sig,
                           "file": str(path), "size": len(data)})
        if first:
            print(f"\nFINDING [{self.target}] {ascii_text(sig)}", flush=True)
            print(f"  input ({len(data)} bytes): {preview(data)}")
            print(f"  saved: {ascii_text(path)}")
            print("  traceback (last lines):")
            for t in tail:
                print("    " + t)
            sys.stdout.flush()


def run_one(target: Any, data: bytes) -> Any:
    """None, or the exception that is a finding."""
    saved = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = NULL_OUT
    try:
        target.execute(data)
    except target.expected:
        return None
    except KeyboardInterrupt:
        raise
    except BaseException as e:           # RecursionError, SystemExit, anything
        return e
    finally:
        sys.stdout, sys.stderr = saved
    return None


# ---------------------------------------------------------------------------
# mutations
# ---------------------------------------------------------------------------

TOKEN_RE = re.compile(
    rb'\s+|[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|"(?:\\.|[^"\\\n])*"|.', re.S)
NUMBER_RE = re.compile(rb"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")

BOUNDARY_NUMBERS = [
    b"0", b"-0", b"1", b"-1", b"255", b"65536", b"2147483647", b"4294967296",
    b"9223372036854775807", b"9223372036854775808", b"-9223372036854775808",
    b"-9223372036854775809", b"18446744073709551616", b"1" * 40,
    b"1" + b"0" * 400, b"9" * 4301, b"0.0", b"-0.0", b"0.5",
    b"1.7976931348623157e308", b"1e308", b"1e309", b"1e999", b"-1e999",
    b"5e-324", b"1e-400", b"NaN", b"Infinity", b"-Infinity", b"0x10",
    b"1_000", b"007", "\u00b2".encode(), "\u0663".encode(), "\u2460".encode(),
]
UNICODE_EDGES = [
    "\u00e9", "\u6f22", "\U0001F600", "\u00b2", "\u0663", "\u2460", "\u200b",
    "\ufeff", "\u2028", "\u0130", "\u00df", "\x00", "\r", "\t", "\x7f",
    "\ud800", "\udfff", "\uffff", "e\u0301", "\u202e",
]
NEST_DEPTHS = [2, 8, 32, 100, 340, 999, 1000, 1001, 3000, 8000]


class Mutator:
    def __init__(self, rng: Any, tokens: Any, pairs: Any, max_len: Any) -> None:
        self.rng, self.tokens, self.pairs = rng, tokens, pairs
        self.max_len = max_len
        self.ops = [self.flip, self.insert_bytes, self.delete, self.duplicate,
                    self.swap, self.splice, self.boundary, self.nest,
                    self.unicode, self.tok_delete, self.tok_duplicate,
                    self.tok_swap, self.tok_replace, self.tok_insert]

    def mutate(self, data: bytes, corpus: list[Any]) -> bytes:
        rng = self.rng
        for _ in range(1 + min(int(rng.expovariate(0.9)), 6)):
            data = rng.choice(self.ops)(data, corpus)
        return data[:self.max_len]

    def _span(self, data: Any, most: int = 64) -> tuple[Any, ...]:
        if not data:
            return 0, 0
        i = self.rng.randrange(len(data))
        return i, min(len(data), i + self.rng.randint(1, most))

    # byte level
    def flip(self, data: Any, corpus: Any) -> Any:
        if not data:
            return bytes([self.rng.randrange(256)])
        i = self.rng.randrange(len(data))
        b = (data[i] ^ (1 << self.rng.randrange(8)) if self.rng.random() < 0.5
             else self.rng.randrange(256))
        return data[:i] + bytes([b]) + data[i + 1:]

    def insert_bytes(self, data: Any, corpus: Any) -> Any:
        i = self.rng.randint(0, len(data))
        k = self.rng.randint(1, 8)
        lo = 32 if self.rng.random() < 0.7 else 0
        hi = 126 if lo else 255
        return data[:i] + bytes(self.rng.randint(lo, hi) for _ in range(k)) + data[i:]

    def delete(self, data: Any, corpus: Any) -> Any:
        i, j = self._span(data)
        return data[:i] + data[j:]

    def duplicate(self, data: Any, corpus: Any) -> Any:
        i, j = self._span(data, 256)
        at = self.rng.randint(0, len(data))
        return data[:at] + data[i:j] + data[at:]

    def swap(self, data: Any, corpus: Any) -> Any:
        if len(data) < 4:
            return data
        a, b = sorted(self.rng.sample(range(len(data)), 2))
        k = self.rng.randint(1, max(1, min(32, b - a)))
        return data[:a] + data[b:b + k] + data[a + k:b] + data[a:a + k] + data[b + k:]

    def splice(self, data: Any, corpus: Any) -> Any:
        other = self.rng.choice(corpus) if corpus else data
        if self.rng.random() < 0.5:
            return data[:self.rng.randint(0, len(data))] + \
                other[self.rng.randint(0, len(other)):]
        i, j = self._span(other, 512)
        at = self.rng.randint(0, len(data))
        return data[:at] + other[i:j] + data[at:]

    def boundary(self, data: Any, corpus: Any) -> Any:
        num = self.rng.choice(BOUNDARY_NUMBERS)
        lo = self.rng.randrange(max(1, len(data) - 4096))
        spots = [(lo + m.start(), lo + m.end())
                 for m in NUMBER_RE.finditer(data, lo, lo + 4096)]
        if spots and self.rng.random() < 0.7:
            i, j = self.rng.choice(spots)
        else:
            i = j = self.rng.randint(0, len(data))
        return data[:i] + num + data[j:]

    def nest(self, data: Any, corpus: Any) -> Any:
        opener, closer = self.rng.choice(self.pairs)
        depth = self.rng.choice(NEST_DEPTHS)
        i, j = self._span(data, 32)
        return data[:i] + opener * depth + data[i:j] + closer * depth + data[j:]

    def unicode(self, data: Any, corpus: Any) -> Any:
        ch = as_bytes(self.rng.choice(UNICODE_EDGES))
        i = self.rng.randint(0, len(data))
        if data and self.rng.random() < 0.3:
            return data[:i] + ch + data[i + 1:]
        return data[:i] + ch + data[i:]

    # token level
    def _tokens(self, data: Any) -> tuple[Any, ...]:
        if len(data) > 8192:
            lo = self.rng.randrange(len(data) - 4096)
            return data[:lo], TOKEN_RE.findall(data, lo, lo + 4096), data[lo + 4096:]
        return b"", TOKEN_RE.findall(data), b""

    def tok_delete(self, data: Any, corpus: Any) -> Any:
        head, toks, tail = self._tokens(data)
        if toks:
            i = self.rng.randrange(len(toks))
            del toks[i:i + self.rng.choice((1, 1, 2, 5))]
        return head + b"".join(toks) + tail

    def tok_duplicate(self, data: Any, corpus: Any) -> Any:
        head, toks, tail = self._tokens(data)
        if toks:
            i = self.rng.randrange(len(toks))
            run = toks[i:i + self.rng.choice((1, 3, 8))]
            at = self.rng.randint(0, len(toks))
            toks[at:at] = run * self.rng.choice((1, 1, 2, 16))
        return head + b"".join(toks) + tail

    def tok_swap(self, data: Any, corpus: Any) -> Any:
        head, toks, tail = self._tokens(data)
        if len(toks) >= 2:
            a, b = self.rng.sample(range(len(toks)), 2)
            toks[a], toks[b] = toks[b], toks[a]
        return head + b"".join(toks) + tail

    def _word(self, corpus: Any) -> Any:
        if corpus and self.rng.random() < 0.3:
            other = self.rng.choice(corpus)
            toks = TOKEN_RE.findall(other, 0, 2048)
            if toks:
                return self.rng.choice(toks)
        return self.rng.choice(self.tokens) if self.tokens else b" "

    def tok_replace(self, data: Any, corpus: Any) -> Any:
        head, toks, tail = self._tokens(data)
        if not toks:
            return self._word(corpus)
        toks[self.rng.randrange(len(toks))] = self._word(corpus)
        return head + b"".join(toks) + tail

    def tok_insert(self, data: Any, corpus: Any) -> Any:
        head, toks, tail = self._tokens(data)
        at = self.rng.randint(0, len(toks))
        toks[at:at] = [b" ", self._word(corpus), b" "]
        return head + b"".join(toks) + tail


# ---------------------------------------------------------------------------
# targets
# ---------------------------------------------------------------------------

class Target:
    name = ""
    runtime = False     # True: run as a running program runs, not a compile
    max_len = 16384
    tokens: list[Any] = []
    pairs = [(b"(", b")"), (b"[", b"]"), (b"{", b"}")]
    generate: Callable[[Any], bytes] | None = None  # or a function rng -> bytes
    expected: tuple[Any, ...] = ()

    def setup(self) -> None:
        self.expected = (V.VelarisError, V.FailSignal)

    def seeds(self, rng: Any) -> list[Any]:
        return []

    def execute(self, data: bytes) -> None:
        raise NotImplementedError


IMPORT_PLAIN = re.compile(r"[A-Za-z0-9_-]+(/[A-Za-z0-9_-]+)*\.vel\Z")
DEVICE_NAMES = ({"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(10)}
                | {f"lpt{i}" for i in range(10)})


def imports_are_plain(tokens: Any) -> bool:
    """Every import names a relative .vel path with no escapes, drive, '..'
    or device name. Any other path would be opened as written - and a UNC
    path is the network - so such a program is parsed but not loaded."""
    for k, t in enumerate(tokens):
        if t.kind != "KEYWORD" or t.text != "import":
            continue
        nxt = tokens[k + 1] if k + 1 < len(tokens) else None
        if nxt is None or nxt.kind != "STRING":
            continue                     # a parse error; nothing is opened
        path = nxt.text[1:-1]
        if "\\" in path or not IMPORT_PLAIN.match(path):
            return False
        if any(p.split(".")[0].lower() in DEVICE_NAMES for p in path.split("/")):
            return False
    return True


def compile_text(source: str, entry: str, prove: bool) -> None:
    """What `velaris file.vel` does before running: load_program (lex,
    parse, imports; it lifts the recursion limit), then the checkers."""
    tokens = V.lex(source)
    if not imports_are_plain(tokens):
        V.Parser(tokens).parse_program()
        return
    funcs, records = V.load_program(entry, source)
    errors: list[Any] = []
    V.check_main(funcs, errors, running=False)
    V.check_effects(funcs, errors)
    V.check_types(funcs, records, errors)
    if prove and not errors:
        V.check_proofs(funcs, records, errors, set())


PARSER_TOKENS = [
    b"fn", b"let", b"return", b"if", b"else", b"while", b"for", b"in", b"to",
    b"uses", b"io", b"ffi", b"fs", b"requires", b"ensures", b"invariant",
    b"and", b"or", b"not", b"record", b"import", b"as", b"fail", b"or fail",
    b"check", b"ok", b"try", b"true", b"false", b"for any T", b"result",
    b"->", b"==", b"!=", b"<=", b">=", b"<", b">", b"=", b"+", b"-", b"*",
    b"/", b"%", b"(", b")", b"{", b"}", b"[", b"]", b",", b":", b".", b'"',
    b"\\", b"//", b"\n", b"Int", b"Float", b"Text", b"Bool", b"List of Int",
    b"Map of Text to Int", b"Money of INR", b"Money of C", b"Secret of Text",
    b"fn(Int) -> Bool", b"Handle", b"Any", b"main", b'"csv.vel"',
    b'import "std.vel"', b'"\\n"', b'"\\q"', b"0", b"1.5", b"x", b"xs",
    b"p.x", b"Pt(x: 1, y: 2)", b'{"a": 1}', b"fn(x: Int) -> Int { return x }",
]
PARSER_PAIRS = [
    (b"(", b")"), (b"[", b"]"), (b"{", b"}"), (b"not ", b""), (b"-", b""),
    (b"if true { ", b" }"), (b"while x { ", b" }"), (b"f(", b")"),
    (b"fn() -> Int { return ", b" }"), (b"try ", b""), (b"if x { } else ", b""),
    (b"x.", b""), (b"List of ", b""),
]
PARSER_SNIPPETS = [
    b"", b"fn", b"fn main() uses io {\n    print(\"hi\")\n}\n",
    b"record R { a: Int }\nfn main() uses io { print(R(a: 1).a) }\n",
    b'fn f(t: Text) -> Int or fail {\n    return try to_int(t)\n}\n',
    b"fn g() -> fn(Int) -> Int {\n    return fn(x: Int) -> Int { return x + 1 }\n}\n",
]


class ParserTarget(Target):
    name = "parser"
    max_len = 96 * 1024
    pairs = PARSER_PAIRS

    def setup(self) -> None:
        super().setup()
        # never written: it only gives imports a directory to resolve in
        self.entry = str(HERE / "examples" / "_fuzz_input.vel")
        self.tokens = PARSER_TOKENS + sorted(n.encode() for n in V.BUILTINS)
        if sys.getrecursionlimit() < 20000:     # as load_program does
            sys.setrecursionlimit(20000)

    def seeds(self, rng: Any) -> Any:
        files = sorted(HERE.glob("examples/**/*.vel")) + sorted(HERE.glob("stdlib/*.vel"))
        return [p.read_bytes() for p in files] + PARSER_SNIPPETS

    def execute(self, data: Any) -> None:
        compile_text(as_text(data), self.entry, prove=False)


JSON_DOC = b'{"user": {"name": "gowri", "age": 30}, "tags": ["proof", "speed"]}'
JSON_SEEDS = [
    (b"user.name", JSON_DOC), (b"tags[1]", JSON_DOC), (b"user.age", JSON_DOC),
    (b"", b'[1, 2.5, -3, true, false, null, "x"]'), (b"2", b"[1, 2.5, -3]"),
    (b"a.b[0].c", b'{"a": {"b": [{"c": 1e3}]}}'),
    (b"", b'"\\u00e9\\ud83d\\ude00"'), (b"k", b'{"k": 9223372036854775807}'),
    (b"k", b'{"k": 1.5e308}'), (b"", b"-0"), (b"", b"{}"), (b"", b"[]"),
    (b"x", b'{"x": "12"}'), (b"[-1]", b"[[1], [2, 3]]"),
    (b"a.", b'{"a": {"": 1}}'), (b"", b' \t\r\n{"a" : [ ] }\n'),
]


def velaris_value(v: Any, most_depth: int = 64) -> bool:
    """Could a Velaris program hold this (64-bit Ints, no null, not deep)?"""
    stack = [(v, 0)]
    while stack:
        x, d = stack.pop()
        if d > most_depth or x is None:
            return False
        if isinstance(x, bool) or isinstance(x, (str, float)):
            continue
        if isinstance(x, int):
            if not -(1 << 63) <= x < (1 << 63):
                return False
        elif isinstance(x, list):
            stack.extend((y, d + 1) for y in x)
        elif isinstance(x, dict):
            stack.extend((y, d + 1) for y in x.values())
        else:
            return False
    return True


class JsonTarget(Target):
    name = "json"
    runtime = True
    max_len = 32768
    pairs = [(b"[", b"]"), (b'{"a":', b"}"), (b'{"a":[', b"]}"), (b".a", b""),
             (b"[0]", b"")]
    tokens = [b"{", b"}", b"[", b"]", b":", b",", b'"', b'"a"', b'"user"',
              b"true", b"false", b"null", b"NaN", b"Infinity", b"-Infinity",
              b"1e999", b"-0", b"\\u0000", b"\\ud800", b"\\udc00", b'\\"',
              b".", b"[0]", b"[-1]", b"[99]", b"\n", b" ",
              b"9223372036854775808", b"1.5", b"01", b"[1_0]"]

    def setup(self) -> None:
        super().setup()
        # what a running program has: load_program 20000, build_runtime 24000
        if sys.getrecursionlimit() < 24000:
            sys.setrecursionlimit(24000)

    def seeds(self, rng: Any) -> list[Any]:
        return [path + b"\n" + doc for path, doc in JSON_SEEDS]

    def execute(self, data: Any) -> None:
        path_raw, sep, doc_raw = data.partition(b"\n")
        if not sep:
            path_raw, doc_raw = b"", data
        doc, path = as_text(doc_raw), as_text(path_raw)
        run, fail = V.run_builtin, V.FailSignal
        for name in ("json_get", "json_int", "json_float", "json_len", "json_has"):
            try:
                run(name, [doc, path], 1)
            except fail:
                pass
        try:
            value = json.loads(doc)
        except Exception:
            return
        if velaris_value(value):
            text = run("json_of", [value], 1)
            try:
                run("json_get", [text, path], 1)
            except fail:
                pass


CSV_SAMPLES = [
    b"a,b,c", b"chai,2500,1\nbook,450,2\n", b"", b",", b"\n", b"a,,b",
    b'"quoted, field",2', b"name,amount\nrefund,-40\n", b"  12  ,3",
    b"1,2,3\r\n4,5,6\r\n", "\u6f22,\u00e9,\U0001F600".encode(),
    b"9223372036854775807,-9223372036854775808", b"x,+7", b"x,007",
]


class CsvTarget(Target):
    name = "csv"
    runtime = True
    max_len = 16384
    pairs = [(b'"', b'"'), (b",", b""), (b"\n", b""), (b"-", b"")]
    tokens = [b",", b"\n", b"\r\n", b"\r", b'"', b'""', b"-", b"+", b" ",
              b"\t", b"0", b"-0", b"9223372036854775807",
              b"9223372036854775808", "\u00b2".encode(), "\u0663".encode(),
              "\u2460".encode(), b"1_000", b"\xef\xbb\xbf", b"\x00", b"1e3",
              b",,,,"]

    def setup(self) -> None:
        super().setup()
        # the repo's stdlib/ beside this file; else beside velaris (a module
        # file, or a package directory and its parent)
        home = Path(V.__file__).resolve().parent
        candidates = [HERE / "stdlib" / "csv.vel", home / "stdlib" / "csv.vel",
                      home.parent / "stdlib" / "csv.vel"]
        path = str(next((p for p in candidates if p.exists()), candidates[0]))
        funcs, records = V.load_program(path)
        errors: list[Any] = []
        V.check_effects(funcs, errors)
        V.check_types(funcs, records, errors)
        if errors:
            raise RuntimeError(f"stdlib/csv.vel does not check: {errors[0].code} "
                               f"{errors[0].message}")
        self.call = V.build_runtime(funcs)["call"]

    def seeds(self, rng: Any) -> Any:
        return list(CSV_SAMPLES)

    def execute(self, data: Any) -> None:
        text, call, fail = as_text(data), self.call, V.FailSignal
        call("fields", [text], 1)
        for row in call("rows_of", [text], 1)[:16]:
            fields = call("fields", [row], 1)
            call("line_of", [fields], 1)
            for at in sorted({-1, 0, 1, len(fields) - 1, len(fields)}):
                for fn in ("column", "column_int"):
                    try:
                        call(fn, [row, at], 1)
                    except fail:
                        pass


# py_json: a Python value is built from the input by a small stack machine,
# returned by a function of a module that exists only in this process, and
# turned back into a Velaris value by py_json (and py / py_int / py_float).
INT_EDGES = [0, 1, -1, 2 ** 63 - 1, 2 ** 63, -2 ** 63, -2 ** 63 - 1, 2 ** 64,
             10 ** 20, 10 ** 308, 10 ** 400, 10 ** 4299, 10 ** 5000, True, False]
FLOAT_EDGES = [0.0, -0.0, 0.5, 1e308, -1e308, 5e-324, float("inf"),
               float("-inf"), float("nan"), 2.0 ** 63, 1e16]
PY_DEPTHS = [2, 10, 100, 1000, 5000, 30000]
PY_FUNCS = ["produce", "produce", "produce", "Thing", "produce.__call__", "missing"]
PY_BUDGET = 50000   # how big a value may be, walked as a tree (shared parts
                    # counted each time): no value takes long to serialise


def odd_objects(mod: Any) -> tuple[Any, ...]:
    import collections
    import datetime
    import decimal
    import enum
    import fractions
    import pathlib
    import unittest.mock
    import uuid

    class Thing:
        def __repr__(self) -> str:
            return "Thing()"
    Thing.__module__ = mod.__name__
    mod.Thing = Thing

    class Colour(enum.IntEnum):
        RED = 1

    class Words(str):
        pass

    class Odd(float):
        def __repr__(self) -> str:
            return "not a float"

    Pair = collections.namedtuple("Pair", "a b")

    def gen() -> Iterator[Any]:
        yield 1

    return Thing, [
        lambda: decimal.Decimal("1.5"), lambda: decimal.Decimal("NaN"),
        lambda: decimal.Decimal("-Infinity"), lambda: complex(1, 2),
        lambda: fractions.Fraction(1, 3), lambda: datetime.datetime(2026, 9, 14),
        lambda: datetime.date(2026, 9, 14), lambda: datetime.timedelta(seconds=5),
        lambda: uuid.UUID(int=5), lambda: pathlib.PurePosixPath("/a/b"),
        lambda: range(3), lambda: memoryview(b"abc"),
        lambda: types.SimpleNamespace(a=1), lambda: collections.OrderedDict(a=1),
        lambda: collections.defaultdict(list, a=[1]),
        lambda: collections.Counter("aab"), lambda: Pair(1, [2]),
        lambda: Exception("boom"), object, Thing, lambda: Colour.RED,
        lambda: Words("sub"), lambda: Odd(2.5), gen, lambda: (lambda: 1),
        lambda: os.getcwd, lambda: json.dumps, lambda: json, lambda: int,
        lambda: {1, 2}, lambda: frozenset([3]), lambda: {(1, 2): "tuple key"},
        lambda: {None: 1, 1.5: 2, True: 3}, lambda: {float("nan"): 1},
        lambda: b"\xff\xfe not utf-8", lambda: bytearray(b"\x80"),
        lambda: "\ud800 lone surrogate", lambda: [float("nan"), float("inf")],
        lambda: unittest.mock.MagicMock(),
    ]


def build_py_value(program: bytes, extras: list[Any]) -> Any:
    stack: list[Any] = []
    sizes: list[Any] = []            # each entry's size, as PY_BUDGET counts it
    pos = [0]

    def byte() -> Any:
        if pos[0] < len(program):
            pos[0] += 1
            return program[pos[0] - 1]
        return 0

    def push(value: Any, size: Any) -> None:
        stack.append(value)
        sizes.append(size)

    def pop(k: Any) -> tuple[Any, ...]:
        k = min(k, len(stack))
        items, ns = stack[len(stack) - k:], sizes[len(sizes) - k:]
        del stack[len(stack) - k:]
        del sizes[len(sizes) - k:]
        return items, ns

    def text_size(s: Any) -> Any:
        return 1 + len(s) // 100

    steps = 0
    while pos[0] < len(program) and steps < 256:
        steps += 1
        op = byte() % 20
        if op == 0:
            push(byte() - 128, 1)
        elif op == 1:
            push(INT_EDGES[byte() % len(INT_EDGES)], 1)
        elif op == 2:
            push(FLOAT_EDGES[byte() % len(FLOAT_EDGES)], 1)
        elif op in (3, 4):
            k = byte() % 48
            raw = program[pos[0]:pos[0] + k]
            pos[0] += k
            if op == 3:
                push(as_text(raw), 1)
            else:
                push(bytes(raw) if byte() % 2 else bytearray(raw), 1)
        elif op == 5:
            push(None, 1)
        elif op == 6:
            push(bool(byte() % 2), 1)
        elif op in (7, 8):
            items, ns = pop(byte() % 8)
            size = 1 + sum(ns)
            if size > PY_BUDGET:
                push(None, 1)
            else:
                push(items if op == 7 else tuple(items), size)
        elif op == 9:
            items, ns = pop(2 * (byte() % 5))
            d, size = {}, 1 + sum(ns)
            for key, val in zip(items[::2], items[1::2]):
                try:
                    d[key] = val
                except TypeError:            # unhashable: say what it was
                    d[type(key).__name__] = val
            if size > PY_BUDGET:
                push(None, 1)
            else:
                push(d, size)
        elif op == 10:
            items, ns = pop(byte() % 6)
            keep = [x for x in items if isinstance(x, (int, str, float, bytes, tuple))]
            try:
                push(set(keep) if byte() % 2 else frozenset(keep), 1 + sum(ns))
            except TypeError:
                push(set(), 1)
        elif op == 11:
            v = stack.pop() if stack else 0
            size = sizes.pop() if sizes else 1
            depth = PY_DEPTHS[byte() % len(PY_DEPTHS)]
            for _ in range(depth):
                v = [v] if byte() % 2 else {"a": v}
            push(v, size + depth)
        elif op == 12:                      # a cycle: json.dumps and str() stop at it
            if stack and isinstance(stack[-1], list):
                stack[-1].append(stack[-1])
            elif stack and isinstance(stack[-1], dict):
                stack[-1]["self"] = stack[-1]
        elif op == 13:
            push(extras[byte() % len(extras)](), 1)
        elif op == 14 and stack:
            push(stack[-1], sizes[-1])
        elif op == 15 and len(stack) >= 2:
            stack[-1], stack[-2] = stack[-2], stack[-1]
            sizes[-1], sizes[-2] = sizes[-2], sizes[-1]
        elif op == 16:
            key = as_text(bytes([byte()]))
            v, size = (stack.pop(), sizes.pop()) if stack else (None, 1)
            push({key: v}, size + 1)
        elif op == 17:
            s = UNICODE_EDGES[byte() % len(UNICODE_EDGES)] * (1 + byte() % 4)
            push(s, text_size(s))
        elif op == 18:
            s = "x" * (byte() * 1000)
            push(s, text_size(s))
        elif stack:
            stack.pop()
            sizes.pop()
    return stack[-1] if stack else None


def py_seed(args: bytes, knobs: int, ops: list[Any]) -> bytes:
    return args + b"\n" + bytes([knobs]) + bytes(ops)


PY_SEEDS = [
    py_seed(b"[]", 0, [0, 130]),
    py_seed(b'[1, "two", [3]]', 1, [3, 5]) + b"hello",
    py_seed(b"[]", 0, [0, 1, 0, 2, 7, 3]),
    py_seed(b'[{"handle": 1}]', 2, [13, 0]),
    py_seed(b'[{"k": 1}]', 0, [3, 1, 97, 0, 5, 9, 1]),
    py_seed(b"[2.5]", 1, [2, 6, 1, 3, 2, 7, 2]),
    py_seed(b"[]", 0, [4, 3, 255, 254, 253, 1]),
    py_seed(b"[]", 3, [13, 20]),
]


class PyJsonTarget(Target):
    name = "py_json"
    runtime = True
    max_len = 4096
    pairs = [(b"[", b"]"), (b'{"handle": ', b"}")]
    tokens = [b"[", b"]", b"{", b"}", b",", b":", b'{"handle": 1}',
              b'{"handle": 2}', b'{"handle": 99}', b'{"handle": "x"}',
              b'{"handle": null}', b'{"handle": 1e999}', b'{"k": 1}', b"null",
              b"true", b"NaN", b"\n", bytes([11]), bytes([12]), bytes([13])]

    def setup(self) -> None:
        super().setup()
        if sys.getrecursionlimit() < 24000:     # as a running program has
            sys.setrecursionlimit(24000)
        mod = types.ModuleType(FFI_MODULE)
        box = self.box = [None]  # type: list[Any]

        def produce(*args: Any, **kwargs: Any) -> Any:
            return box[0]
        produce.__module__ = FFI_MODULE
        mod.produce = produce  # type: ignore[attr-defined]  # a module made here, at runtime
        self.thing_class, self.extras = odd_objects(mod)
        sys.modules[FFI_MODULE] = mod
        # the run's budget and grants, where the runtime reads them
        velaris_global("spend")["EFFECT_BUDGET"] = {"io", "ffi"}   # --allow io,ffi
        self.grant_spaces = [velaris_global("ffi_reach"), velaris_global("allow_module")]
        self.objects = velaris_global("run_builtin")["PY_OBJECTS"]
        # fuzzing is only worth anything if py_json reaches the module
        self.grant(None)
        box[0] = [1, "two"]
        try:
            got = V.run_builtin("py_json", [FFI_MODULE, "produce", "[]"], 1)
        except (V.VelarisError, V.FailSignal) as e:
            raise RuntimeError("py_json cannot reach the fuzz module: "
                               + str(getattr(e, "message", getattr(e, "reason", e))))
        if got != '[1, "two"]':
            raise RuntimeError("py_json gave back %r for [1, 'two']" % (got,))
        box[0] = None

    def grant(self, modules: Any) -> None:
        for space in self.grant_spaces:
            space["FFI_MODULES"] = modules

    def seeds(self, rng: Any) -> Any:
        return list(PY_SEEDS)

    def execute(self, data: Any) -> None:
        head, _, program = data.partition(b"\n")
        knobs = program[0] if program else 0
        self.grant((None, {FFI_MODULE}, {FFI_MODULE, "json"})[knobs % 3])
        func = PY_FUNCS[(knobs // 3) % len(PY_FUNCS)]
        try:
            self.box[0] = build_py_value(program[1:], self.extras)
        except Exception:
            self.box[0] = None                  # the builder's problem, not Velaris's
        self.objects.clear()
        self.objects[1] = [1, "two"]
        self.objects[2] = self.thing_class()
        run, expected = V.run_builtin, self.expected
        try:
            out = run("py_json", [FFI_MODULE, func, as_text(head)], 1)
        except expected:
            out = None
        if isinstance(out, str):
            for name, path in (("json_get", ""), ("json_len", ""), ("json_int", ""),
                               ("json_float", ""), ("json_has", "0")):
                try:
                    run(name, [out, path], 1)
                except expected:
                    pass
        for name in ("py", "py_int", "py_float"):
            try:
                run(name, [FFI_MODULE, func, ["1", "two"]], 1)
            except expected:
                pass
        self.box[0] = None
        self.objects.clear()


# contracts: generated programs, well-typed most of the time and ill-typed on
# purpose some of the time, through all three checkers.
C_TYPES = ["Int", "Int", "Int", "Bool", "Float", "Text", "List of Int",
           "List of Text", "Map of Text to Int", "Money of INR",
           "Secret of Int", "Pt"]
C_CMP = ["==", "!=", "<", "<=", ">", ">="]
C_PRELUDE = (
    "record Pt {\n    x: Int\n    y: Int\n}\n\n"
    "fn is_pos(n: Int) -> Bool {\n    return n > 0\n}\n\n"
    "fn abs_of(n: Int) -> Int\n    ensures result >= 0\n{\n"
    "    if n < 0 {\n        return 0 - n\n    }\n    return n\n}\n")
CONTRACT_EXAMPLES = [
    "contract.vel", "div_proof.vel", "div_bad.vel", "list_proof.vel",
    "list_proof_bad.vel", "map_proof.vel", "rec_proof.vel", "loop_proof.vel",
    "loop_proof_bad.vel", "fail_proof.vel", "callsite_bad.vel", "conj_bad.vel",
    "quantified.vel", "offbyone_bad.vel", "lambda_contract.vel",
    "text_list_proof.vel",
]


class ContractGen:
    def __init__(self, rng: Any) -> None:
        self.r = rng
        self.ill = False

    def leaf(self, ty: Any) -> Any:
        r = self.r
        if ty == "Int":
            return r.choice(["0", "1", "2", "-1", "7", "100", "-100",
                             "9223372036854775807", "4611686018427387904"])
        if ty == "Bool":
            return r.choice(["true", "false"])
        if ty == "Float":
            return r.choice(["0.0", "0.5", "1.0", "-2.5", "1000000000000000000000.0"])
        if ty == "Text":
            return r.choice(['""', '"a"', '"a,b"', '"\\n"', '"\u00e9"'])
        if ty == "List of Int":
            return r.choice(["[1, 2, 3]", "[0]", "[-1, 5]"])
        if ty == "List of Text":
            return r.choice(['["a"]', '["a", "b"]'])
        if ty == "Map of Text to Int":
            return r.choice(['{"a": 1}', '{"a": 1, "b": 2}'])
        if ty == "Money of INR":
            return "money(" + self.leaf("Int") + ', "INR")'
        if ty == "Pt":
            return "Pt(x: " + self.leaf("Int") + ", y: " + self.leaf("Int") + ")"
        return "0"

    def expr(self, ty: Any, env: Any, depth: int = 0) -> Any:
        r = self.r
        if self.ill and r.random() < 0.06:
            ty = r.choice(C_TYPES)
        names = [n for n, t in env.items() if t == ty]
        if depth >= 3 or r.random() < 0.3:
            if names and r.random() < 0.7:
                return r.choice(names)
            return self.leaf(ty)

        def e(t: Any) -> Any:
            return self.expr(t, env, depth + 1)

        if ty == "Int":
            forms = [
                lambda: "(" + e("Int") + " " + r.choice(["+", "-", "*", "/", "%"]) + " " + e("Int") + ")",
                lambda: "-" + e("Int"),
                lambda: "length(" + e(r.choice(["List of Int", "Text", "List of Text"])) + ")",
                lambda: "get(" + e("List of Int") + ", " + e("Int") + ")",
                lambda: "units_of(" + e("Money of INR") + ")",
                lambda: e("Pt") + "." + r.choice(["x", "y"]),
                lambda: "code_at(" + e("Text") + ", " + e("Int") + ")",
                lambda: "get_or(" + e("Map of Text to Int") + ", " + e("Text") + ", " + e("Int") + ")",
                lambda: "round(" + e("Float") + ")",
                lambda: "abs_of(" + e("Int") + ")",
            ]
        elif ty == "Bool":
            cmp_t = r.choice(["Int", "Int", "Float", "Text", "Money of INR"])
            forms = [
                lambda: "(" + e(cmp_t) + " " + r.choice(C_CMP) + " " + e(cmp_t) + ")",
                lambda: "(" + e("Bool") + " " + r.choice(["and", "or"]) + " " + e("Bool") + ")",
                lambda: "not " + e("Bool"),
                lambda: "contains(" + e("Text") + ", " + e("Text") + ")",
                lambda: "has(" + e("Map of Text to Int") + ", " + e("Text") + ")",
                lambda: "all_of(" + e("List of Int") + ", is_pos)",
                lambda: "any_of(" + e("List of Int") + ", is_pos)",
            ]
        elif ty == "Float":
            forms = [
                lambda: "(" + e("Float") + " " + r.choice(["+", "-", "*", "/"]) + " " + e("Float") + ")",
                lambda: "to_float(" + e("Int") + ")",
                lambda: "-" + e("Float"),
            ]
        elif ty == "Text":
            forms = [
                lambda: "(" + e("Text") + " + " + e("Text") + ")",
                lambda: "upper(" + e("Text") + ")",
                lambda: "to_text(" + e("Int") + ")",
                lambda: "get(" + e("List of Text") + ", " + e("Int") + ")",
            ]
        elif ty == "List of Int":
            forms = [
                lambda: "push(" + e("List of Int") + ", " + e("Int") + ")",
                lambda: "[" + e("Int") + ", " + e("Int") + "]",
            ]
        elif ty == "List of Text":
            forms = [
                lambda: "split(" + e("Text") + ', ",")',
                lambda: "push(" + e("List of Text") + ", " + e("Text") + ")",
            ]
        elif ty == "Map of Text to Int":
            forms = [lambda: "put(" + e("Map of Text to Int") + ", " + e("Text") + ", " + e("Int") + ")"]
        elif ty == "Money of INR":
            forms = [
                lambda: "(" + e("Money of INR") + " + " + e("Money of INR") + ")",
                lambda: "money(" + e("Int") + ', "INR")',
            ]
        elif ty == "Pt":
            forms = [lambda: "Pt(x: " + e("Int") + ", y: " + e("Int") + ")"]
        else:
            forms = [lambda: self.leaf(ty)]
        return r.choice(forms)()

    def function(self, k: Any) -> tuple[Any, ...]:
        r = self.r
        params = [("p%d" % j, r.choice(C_TYPES)) for j in range(r.randint(0, 3))]
        generic = r.random() < 0.08
        if generic:
            params.append(("g", "T"))
        ret = r.choice(C_TYPES + [None])
        can_fail = r.random() < 0.15
        env = dict(params)
        head = "fn f%d(" % k + ", ".join(n + ": " + t for n, t in params) + ")"
        if ret:
            head += " -> " + ret
        if generic:
            head += " for any T"
        if can_fail:
            head += " or fail"
        clauses = ["    requires " + self.expr("Bool", env)
                   for _ in range(r.randint(0, 2))]
        renv = dict(env)
        if ret:
            renv["result"] = ret
        clauses += ["    ensures " + self.expr("Bool", renv)
                    for _ in range(r.randint(0 if clauses else 1, 2))]
        body, local = [], dict(env)
        if r.random() < 0.4:
            body += ["    let i = 0",
                     "    while i < " + self.expr("Int", env),
                     "        invariant i >= 0",
                     "    {", "        i = i + 1", "    }"]
            local["i"] = "Int"
        if ret and r.random() < 0.4:
            body += ["    if " + self.expr("Bool", local) + " {",
                     "        return " + self.expr(ret, local), "    }"]
        if can_fail and r.random() < 0.5:
            body += ["    if " + self.expr("Bool", local) + " {",
                     '        fail "no"', "    }"]
        if ret:
            body.append("    return " + self.expr(ret, local))
        text = head + "\n" + "".join(c + "\n" for c in clauses) + "{\n" + \
            "".join(b + "\n" for b in body) + "}\n"
        return text, ("f%d" % k, params, ret, can_fail)

    def program(self) -> str:
        r = self.r
        self.ill = r.random() < 0.35
        parts, sigs = [C_PRELUDE], []
        for k in range(r.randint(1, 3)):
            text, sig = self.function(k)
            parts.append(text)
            sigs.append(sig)
        if r.random() < 0.7:                    # call sites: E701 and friends
            env = {"a": "Int", "t": "Text", "xs": "List of Int"}
            lines = []
            for name, params, ret, can_fail in sigs:
                call = name + "(" + ", ".join(
                    self.expr("Int" if t == "T" else t, env) for _, t in params) + ")"
                if can_fail:
                    lines += ["    check " + call + " {",
                              "        ok " + ("v " if ret else "") + "{", "        }",
                              "        fail why {", "        }", "    }"]
                elif ret:
                    lines.append("    let v_" + name + " = " + call)
                else:
                    lines.append("    " + call)
            parts.append("fn caller(a: Int, t: Text, xs: List of Int) -> Int\n"
                         "    requires " + self.expr("Bool", env) + "\n{\n"
                         + "".join(x + "\n" for x in lines) + "    return 0\n}\n")
        return "\n".join(parts)


class ContractsTarget(Target):
    name = "contracts"
    max_len = 16384
    pairs = [(b"(", b")"), (b"not ", b""), (b"-", b""), (b"[", b"]")]
    tokens = [b"requires", b"ensures", b"invariant", b"result", b"and", b"or",
              b"not", b"==", b"!=", b"<", b"<=", b"+", b"-", b"*", b"/", b"%",
              b"length", b"get", b"all_of", b"any_of", b"units_of", b"push",
              b"Int", b"Float", b"Text", b"Bool", b"List of Int",
              b"Map of Text to Int", b"Money of INR", b"Secret of Int",
              b"for any T", b"or fail", b"0", b"1", b"-1",
              b"9223372036854775807", b"0.5", b'"a"', b"while", b"if",
              b"return", b"fail", b"try", b"(", b")", b"[", b"]", b"p0", b"xs"]

    def setup(self) -> None:
        super().setup()
        self.entry = str(HERE / "examples" / "_fuzz_input.vel")
        V.set_proof_timeout(PROOF_SECONDS)
        if sys.getrecursionlimit() < 20000:
            sys.setrecursionlimit(20000)

    def seeds(self, rng: Any) -> Any:
        out = [as_bytes(ContractGen(rng).program()) for _ in range(8)]
        for name in CONTRACT_EXAMPLES:
            p = HERE / "examples" / name
            if p.exists():
                out.append(p.read_bytes())
        return out

    def generate(self, rng: Any) -> Any:
        return as_bytes(ContractGen(rng).program())

    def execute(self, data: Any) -> None:
        compile_text(as_text(data), self.entry, prove=True)


def make_target(name: str) -> Target:
    return {"parser": ParserTarget, "json": JsonTarget, "csv": CsvTarget,
            "py_json": PyJsonTarget, "contracts": ContractsTarget}[name]()


# ---------------------------------------------------------------------------
# engines (in the child)
# ---------------------------------------------------------------------------

def fuzz_builtin(target: Any, rng: Any, iterations: Any, seconds: Any, journal: Any, findings: Any, cov: LineCoverage, events: Any,
                 replay_dir: Any = None, replay_seeds: bool = True) -> tuple[Any, ...]:
    """(summary, slowest input). Seeds run first - half the iterations at
    most, all of them under a time budget, none for a restarted child."""
    mutator = Mutator(rng, target.tokens, target.pairs, target.max_len)
    if replay_dir:
        seeds = [p.read_bytes() for p in sorted(Path(replay_dir).iterdir()) if p.is_file()]
    else:
        seeds = [s[:target.max_len] for s in target.seeds(rng)]
    corpus = list(seeds)
    order = list(range(len(seeds)))
    rng.shuffle(order)
    if not replay_seeds:
        order = []
    elif seconds is None and not replay_dir:
        order = order[:iterations // 2 if iterations > 1 else iterations]
    deadline = None if seconds is None else time.monotonic() + seconds
    state: dict[str, Any]
    state = {"n": 0, "seeds": 0, "slowest": 0.0, "slow": b"",
             "reported": time.monotonic()}

    def summary() -> dict[str, Any]:
        return {"iterations": state["n"], "seeds": state["seeds"],
                "corpus": len(corpus), "coverage": cov.method,
                "lines": sorted("%s:%d" % at for at in cov.seen),
                "slowest": round(state["slowest"], 2)}

    def left() -> bool:
        return cast(bool, time.monotonic() < deadline if deadline is not None
                    else state["n"] < iterations)

    def one(data: Any) -> bool:
        journal.note(state["n"], data)
        before = cov.fresh
        started = time.monotonic()
        exc = run_one(target, data)
        took = time.monotonic() - started
        cov.ensure()
        state["n"] += 1
        if took > state["slowest"]:
            state["slowest"], state["slow"] = took, data
        if exc is not None:
            findings.record(data, exc)
        if started - state["reported"] > PROGRESS_SECONDS:
            state["reported"] = started
            doc = summary()
            doc["event"] = "progress"
            events.write(doc)
        return cov.fresh > before

    for k in order:
        if not replay_dir and not left():
            break
        one(seeds[k])
        state["seeds"] += 1
    if not replay_dir:
        while left():
            if target.generate is not None and rng.random() < 0.4:
                data = target.generate(rng)
            else:
                recent = rng.random() < 0.2 and len(corpus) > len(seeds)
                parent = rng.choice(corpus[-16:] if recent else corpus) if corpus else b""
                data = mutator.mutate(parent, corpus)
            if one(data):
                corpus.append(data)
    return summary(), state["slow"]


def libfuzzer_dict_line(token: bytes) -> str:
    out = []
    for b in token:
        c = chr(b)
        if c in '"\\':
            out.append("\\" + c)
        elif 32 <= b < 127:
            out.append(c)
        else:
            out.append("\\x%02X" % b)
    return '"' + "".join(out) + '"\n'


def fuzz_atheris(target: Any, args: Any, journal: Any, findings: Any) -> None:
    import atheris
    corpus_dir = WORK / ("corpus-" + target.name)
    corpus_dir.mkdir(exist_ok=True)
    for k, s in enumerate(target.seeds(random.Random(args.seed))):
        (corpus_dir / ("seed-%04d" % k)).write_bytes(s[:target.max_len])
    dict_path = WORK / (target.name + ".dict")
    dict_path.write_text("".join(libfuzzer_dict_line(t) for t in target.tokens if t),
                         encoding="ascii")
    count = [0]

    def test_one(data: Any) -> None:
        journal.note(count[0], data)
        count[0] += 1
        exc = run_one(target, data)
        if exc is not None:
            findings.record(data, exc)

    budget = (["-runs=%d" % args.iterations] if args.seconds is None
              else ["-max_total_time=%d" % max(1, int(args.seconds))])
    Path(args.crashes).mkdir(parents=True, exist_ok=True)
    argv = [sys.argv[0], str(corpus_dir), "-seed=%d" % (args.seed % (1 << 31) or 1),
            "-max_len=%d" % target.max_len, "-timeout=%d" % int(args.hang_seconds),
            "-rss_limit_mb=4096", "-dict=" + str(dict_path),
            "-artifact_prefix=" + str(Path(args.crashes)) + os.sep] + budget
    atheris.Setup(argv, test_one)
    atheris.Fuzz()                               # exits the process


def child_main(args: Any) -> int:
    name = args.child
    events = Events(args.events)
    try:
        load_velaris(instrument=args.engine == "atheris" and not args.replay)
        target = make_target(name)
        target.setup()
    except Exception as e:
        events.write({"event": "error", "message": ascii_text(
            "".join(traceback.format_exception_only(type(e), e)).strip())})
        return 3
    known = {}
    if args.known:
        try:
            known = json.loads(Path(args.known).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            known = {}
    journal = Journal(WORK / (name + ".journal"))
    findings = Findings(name, Path(args.crashes), events, known)
    if args.engine == "atheris" and not args.replay:
        fuzz_atheris(target, args, journal, findings)
        return 0
    cov = LineCoverage(VFILES)
    rng = random.Random(args.seed)
    t0 = time.monotonic()

    def go() -> Any:
        cov.install()
        try:
            return fuzz_builtin(target, rng, args.iterations or 0, args.seconds,
                                journal, findings, cov, events, args.replay,
                                not args.no_replay)
        finally:
            cov.uninstall()

    # a running program's builtins run where the interpreter runs them: on a
    # big thread stack before 3.11 (_run_on_big_stack); the compiler runs on
    # the calling thread, as `velaris file.vel` runs it
    big = None
    if target.runtime:
        big = getattr(V, "_run_on_big_stack", None) or getattr(
            getattr(V, "interpret", None), "__globals__", {}).get("_run_on_big_stack")
    result, slow = big(go) if big is not None else go()
    if result["slowest"] >= SLOW_SECONDS:
        path = Path(args.crashes) / (name + "-slowest.bin")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(slow)
            result["slow_file"] = str(path)
        except OSError:
            pass
    new = {s for s in findings.best if s not in known}
    result.update(event="done", findings=len(new), hits=findings.hits,
                  seconds=round(time.monotonic() - t0, 2))
    events.write(result)
    return 1 if new else 0


# ---------------------------------------------------------------------------
# the parent: one supervised child per target
# ---------------------------------------------------------------------------

def exit_text(code: Any) -> str:
    if code is None:
        return "unknown"
    if os.name == "nt" and (code < 0 or code > 255):
        u = code & 0xFFFFFFFF
        known = {0xC00000FD: "a stack overflow", 0xC0000005: "an access violation",
                 0xC0000409: "a stack buffer overrun"}
        return "0x%08X" % u + (" (%s)" % known[u] if u in known else "")
    if code < 0:
        return "signal %d" % -code
    return str(code)


def watch(proc: Any, journal_path: Path, hang: float, seconds_left: Any) -> tuple[Any, ...]:
    """Wait for the child. (exit code, stalled): stalled when the journal
    shows no new input for `hang` seconds, or the time budget is long gone."""
    last, since = None, time.monotonic()
    hard = None if seconds_left is None else time.monotonic() + seconds_left + max(hang, 30)
    while True:
        try:
            return proc.wait(timeout=0.25), False
        except subprocess.TimeoutExpired:
            pass
        head = read_journal(journal_path, head_only=True)
        now = time.monotonic()
        if head != last:
            last, since = head, now
        elif now - since > hang or (hard is not None and now > hard):
            proc.kill()
            proc.wait()
            return proc.returncode, True


def child_command(name: Any, args: Any, seed: Any, engine: Any, crashes: Any, events_path: Any, known_path: Any) -> list[Any]:
    return [sys.executable, os.path.abspath(__file__), "--child", name,
            "--work", str(WORK), "--seed", str(seed), "--engine", engine,
            "--crashes", str(crashes), "--events", str(events_path),
            "--known", str(known_path), "--hang-seconds", str(args.hang_seconds)]


def absorb(total: dict[Any, Any], events: list[Any]) -> Any:
    """Fold a child's events into the target's totals; the last progress or
    done event, which is None when the child reported nothing."""
    last = None
    for ev in events:
        kind = ev.get("event")
        if kind == "finding":
            sig, size = ev["signature"], ev["size"]
            total["signatures"][sig] = min(size, total["signatures"].get(sig, size))
        elif kind == "error":
            total["error"] = ev["message"]
        elif kind in ("progress", "done"):
            last = ev
    if last is not None:
        total["seeds"] += last["seeds"]
        total["corpus"] = max(total["corpus"], last["corpus"])
        total["lines"] |= set(last["lines"])
        total["coverage"] = last["coverage"]
        if last.get("slowest", 0) >= total["slowest"]:
            total["slowest"] = last["slowest"]
            total["slow_file"] = last.get("slow_file", total["slow_file"])
    return last


def supervise(index: Any, name: Any, args: Any, engine: Any, seed: Any, iters: Any, secs: Any, crashes: Any) -> dict[Any, Any]:
    total: dict[str, Any]
    total = {"iterations": 0, "seeds": 0, "corpus": 0, "lines": set(),
             "signatures": {}, "error": None, "coverage": "", "slowest": 0.0,
             "slow_file": None}
    t0 = time.monotonic()
    journal_path = WORK / (name + ".journal")
    known_path = WORK / (name + ".known")
    for run in range(MAX_RESTARTS + 1):
        its_left = None if iters is None else iters - total["iterations"]
        secs_left = None if secs is None else secs - (time.monotonic() - t0)
        if run and ((its_left is not None and its_left <= 0)
                    or (secs_left is not None and secs_left < 1)):
            break
        events_path = WORK / ("%s-%d.events" % (name, run))
        known_path.write_text(json.dumps(total["signatures"]), encoding="utf-8")
        cmd = child_command(name, args, child_seed(seed, index, run), engine,
                            crashes, events_path, known_path)
        cmd += ([str(its_left)] if secs_left is None else ["--seconds", "%.1f" % secs_left])
        if run:
            cmd.append("--no-replay")      # the seeds ran already
        try:
            journal_path.unlink()          # never read a previous child's input
        except OSError:
            pass
        env = dict(os.environ)
        if args.seed is not None:
            env["PYTHONHASHSEED"] = str(seed % (1 << 32))
        log = open(WORK / ("%s-%d.log" % (name, run)), "wb") if engine == "atheris" else None
        try:
            proc = subprocess.Popen(cmd, env=env, stderr=log)
            code, stalled = watch(proc, journal_path, args.hang_seconds, secs_left)
        finally:
            if log:
                log.close()
        last = absorb(total, read_events(events_path))
        if last is not None and last.get("event") == "done":
            total["iterations"] += last["iterations"]
            break
        if total["error"]:
            break
        noted = read_journal(journal_path)
        if noted is None:                  # no input ran: the harness failed
            total["error"] = ("the child process %s before it ran an input" % (
                "made no progress" if stalled else "exited with code " + exit_text(code)))
            break
        total["iterations"] += noted[0] + 1
        if engine == "atheris" and code == 0 and not stalled:
            replay(name, args, crashes, total)
            break
        why = ("made no progress for %gs and was stopped" % args.hang_seconds
               if stalled else "died with exit code " + exit_text(code))
        sig, data = "the process " + why, noted[1]
        if sig not in total["signatures"] or len(data) < total["signatures"][sig]:
            path = crashes / ("%s-%s.bin" % (name, hashlib.sha1(sig.encode()).hexdigest()[:10]))
            crashes.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            if sig not in total["signatures"]:
                print("\nFINDING [%s] %s" % (name, sig), flush=True)
                print("  input (%d bytes): %s" % (len(data), preview(data)))
                print("  saved: " + ascii_text(path), flush=True)
            total["signatures"][sig] = len(data)
        if engine == "atheris":
            break                          # libFuzzer wrote its own artifact
        if run == MAX_RESTARTS:
            print("  [%s] stopped after %d process deaths" % (name, run + 1), flush=True)
    total["seconds"] = time.monotonic() - t0
    return total


def replay(name: Any, args: Any, crashes: Any, total: Any) -> None:
    """After atheris: the line coverage of the corpus it grew, measured by
    running every entry once under the built-in collector."""
    corpus_dir = WORK / ("corpus-" + name)
    events_path = WORK / (name + "-replay.events")
    known_path = WORK / (name + ".known")
    known_path.write_text(json.dumps(total["signatures"]), encoding="utf-8")
    cmd = child_command(name, args, 1, "builtin", crashes, events_path, known_path)
    cmd += ["--replay", str(corpus_dir)]
    proc = subprocess.Popen(cmd)
    watch(proc, WORK / (name + ".journal"), args.hang_seconds, None)
    seeds = total["seeds"]
    if absorb(total, read_events(events_path)) is not None:
        total["seeds"] = seeds
        total["coverage"] += " (replayed corpus)"


def minimize(args: Any) -> int:
    """Shrink a saved input while it still gives the same finding."""
    load_velaris()
    target = make_target(args.target)
    target.setup()
    data = Path(args.minimize).read_bytes()
    big = getattr(V, "_run_on_big_stack", None) if target.runtime else None

    def attempt(d: Any) -> Any:
        exc = big(lambda: run_one(target, d)) if big else run_one(target, d)
        return (None, None) if exc is None else (signature(exc), exc)

    want, exc = attempt(data)
    if want is None:
        print("no finding with this input")
        return 0
    tries, chunk = 0, max(1, len(data) // 2)
    while chunk >= 1 and tries < 20000:
        i, changed = 0, False
        while i < len(data) and tries < 20000:
            candidate = data[:i] + data[i + chunk:]
            tries += 1
            if attempt(candidate)[0] == want:
                data, changed = candidate, True
            else:
                i += chunk
        if not changed:
            chunk //= 2
    want, exc = attempt(data)
    out = Path(args.minimize + ".min")
    out.write_bytes(data)
    print("signature: " + ascii_text(want))
    print("minimal input (%d bytes, %d tries): %s" % (len(data), tries, preview(data, 2000)))
    print("saved: " + ascii_text(out))
    for t in traceback_tail(exc):
        print("    " + t)
    return 1


def main(argv: Any = None) -> int:
    ap = argparse.ArgumentParser(
        description="Coverage-guided fuzzing of Velaris's parsers and translators.")
    ap.add_argument("iterations", nargs="?", type=int,
                    help="iterations per target (default 200)")
    ap.add_argument("--minutes", type=float, help="a time budget split across the targets")
    ap.add_argument("--seed", type=int, help="make the run reproducible")
    ap.add_argument("--target", help="one of " + ", ".join(TARGETS) + " (or a comma list)")
    ap.add_argument("--engine", choices=("builtin", "atheris"))
    ap.add_argument("--crashes", help="where findings are saved (default: crashes/ in "
                                      "the work directory, removed at exit)")
    ap.add_argument("--hang-seconds", type=float, default=60.0,
                    help="an input running this long is a finding (default 60)")
    ap.add_argument("--minimize", metavar="FILE", help="shrink a saved input (needs --target)")
    ap.add_argument("--child", help=argparse.SUPPRESS)
    ap.add_argument("--work", help=argparse.SUPPRESS)
    ap.add_argument("--seconds", type=float, help=argparse.SUPPRESS)
    ap.add_argument("--events", help=argparse.SUPPRESS)
    ap.add_argument("--known", help=argparse.SUPPRESS)
    ap.add_argument("--replay", help=argparse.SUPPRESS)
    ap.add_argument("--no-replay", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    if args.child:
        return child_main(args)
    if args.minimize:
        if args.target not in TARGETS:
            ap.error("--minimize needs --target " + "|".join(TARGETS))
        return minimize(args)
    if args.iterations is not None and args.minutes is not None:
        ap.error("give a number of iterations or --minutes, not both")
    if args.iterations is not None and args.iterations < 0:
        ap.error("iterations cannot be negative")
    names = list(TARGETS) if not args.target else [t.strip() for t in args.target.split(",")]
    for target_name in names:
        if target_name not in TARGETS:
            ap.error("unknown target '%s' (choose from %s)" % (target_name, ", ".join(TARGETS)))

    have_atheris = importlib.util.find_spec("atheris") is not None
    if args.engine == "atheris" and not have_atheris:
        print("fuzz_parsers: atheris is not installed (pip install atheris; it does "
              "not support Windows) - use --engine builtin")
        return 2
    engine = args.engine or ("atheris" if have_atheris else "builtin")
    no_z3 = "contracts" in names and importlib.util.find_spec("z3") is None
    if no_z3:
        names.remove("contracts")

    seed = args.seed if args.seed is not None else random.randrange(1 << 30)
    crashes = Path(args.crashes).resolve() if args.crashes else WORK / "crashes"
    iters = None if args.minutes is not None else (200 if args.iterations is None
                                                   else args.iterations)
    secs = None if args.minutes is None else args.minutes * 60.0 / max(1, len(names))
    budget = ("%d iterations per target" % iters if iters is not None
              else "%.1f minutes (%.0fs per target)" % (args.minutes, cast(float, secs)))
    method = "sys.monitoring" if hasattr(sys, "monitoring") else "sys.settrace"
    print("fuzz_parsers: engine %s, line coverage by %s, seed %d, %s, Python %s"
          % (engine, method, seed, budget, sys.version.split()[0]), flush=True)
    if no_z3:
        print("contracts  skipped: z3-solver is not installed, so there is no "
              "contract translator to fuzz (pip install z3-solver)", flush=True)

    found, errors = 0, 0
    for index, name in enumerate(TARGETS):
        if name not in names:
            continue
        t = supervise(index, name, args, engine, seed, iters, secs, crashes)
        if t["error"]:
            errors += 1
            print("%-10s ERROR: %s" % (name, t["error"]), flush=True)
            continue
        found += len(t["signatures"])
        seeds = " (%d seeds)" % t["seeds"] if engine == "builtin" else ""
        print("%-10s iterations %d%s  corpus %d  lines covered %d  findings %d  %.1fs"
              % (name, t["iterations"], seeds, t["corpus"], len(t["lines"]),
                 len(t["signatures"]), t["seconds"]), flush=True)
        if t["slowest"] >= SLOW_SECONDS:
            print("           slowest input took %.1fs (not a finding)%s"
                  % (t["slowest"], "; saved: " + ascii_text(t["slow_file"])
                     if t["slow_file"] else ""), flush=True)
    if found:
        where = ("" if args.crashes else " (the work directory is removed at exit; "
                 "--crashes DIR keeps them)")
        print("\n%d finding(s); inputs saved in %s%s" % (found, ascii_text(crashes), where))
        return 1
    if errors:
        return 2
    print("\nno findings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
