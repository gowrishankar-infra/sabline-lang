"""The agreement gate: two runtimes, the same inputs, no difference.

    python check_agreement.py [corpus paths...]

It runs the Python package and sabline-rt over every Sabline source this
project has and fails on any difference. plan/9.0.md designs it, and each
milestone grows it by what that milestone ports: M1 compared the parsers -
the AST dump, the error code, the message, the fixes and the line - and M2
adds the checkers, which is what `sabline check` finds in each program,
stage by stage, and each loop's termination verdict, the builtin tables
both checkers read, and the budget parser. M3 adds the interpreters - every
program run by both, under the budget io, and what each run printed,
the status it ended with and the error it stopped with compared; and from
its second checkpoint the programs written for a budget run under their
own, in a tree of files made afresh for each runtime - and from its third
each run's receipt.

**What it runs over** (plan/9.0.md's table, the rows that hold a program):

    sabline-spec's conformance corpus   every source in every case
    examples/                           the .vel files, lib, ops and runner
    stdlib/                             14 .vel files
    benchmark/corpus/                   85 .vel files
    the lie corpus                      check_prover_lies.py's false promises
    check_sandbox.py                    its escapes and its honest programs

and five more, which are here because the six above hold **no program the
lexer or the parser refuses** - every one of them parses, and is refused
later or not at all. A gate that only ever compared trees would say
nothing at all about the error codes, the messages, the fixes and the
lines, which is half of what this alpha claims:

    tests/error_messages/               one program per error code
    check_refusals.py                   its wrong programs
    check_termination.py                its loops, one per edge of the rule
    truncations                         every example cut at fifteen points
    agreement_edges.py                  the standing adversarial pass, as a
                                        table: the depth caps on each side,
                                        literals at the digit limit, bytes
                                        that are not UTF-8, byte-order
                                        marks, CRLF, NUL, Unicode digits
                                        and identifiers, extreme lines
    paths that are not files            the one refusal that is not about
                                        a program's contents

Together they reach every code the lexer and the parser give: E000, E001,
E002, E100, E101, E102, E407, E511, E512 and E562.

And one for the checkers (M2), because every corpus above was written to
compile or to be refused while parsing, and so reaches little of the half
of the checkers that refuses:

    agreement_checks.py                 a type-level mistake made at fixed
                                        places in every example and library,
                                        a table of programs that reach each
                                        refusal no mistake reaches, and
                                        programs of several files

And one for the interpreters (M3), because a program written to compile
prints little and reaches little of the builtins:

    agreement_runs.py                   every text builtin over texts where
                                        code points and UTF-8 part - lone
                                        surrogates, characters past the
                                        basic plane, combining marks, case
                                        that is more than one character -
                                        and the arithmetic, floats, JSON,
                                        money and messages a run shows

**What it compares.** Three canonical documents per source, each byte for
byte, and one more document for the whole gate:

- the AST dump (sabline/ast_dump.py and the crate's `dump` module say what
  is in it), which holds the whole tree when the source parses and the
  code, message, fixes and line when it does not;
- the check document (sabline/check_dump.py and the crate's `check_dump`
  module), which holds what `sabline check` finds without the prover -
  each stage's problems in the reference's order, every problem once, and
  every loop's verdict and the reason for it;
- the run document (sabline/run_dump.py and the crate's `run_dump`
  module), which holds what `sabline <file>` does with the program under
  the budget io, a fixed input, fixed arguments, a step limit and a size
  limit: the problems that refused it, or what it printed to each channel,
  the status it ended with, the error it stopped with and which limit
  stopped it - for every program but the ones RUN_EXCLUDED names, each
  with its reason;
- the receipt of each of those runs, sabline.receipt/1 - its subjects by
  digest, the budget, the run's parameters, what each effect and grant let
  through, every refusal and declassification by line and count, and how
  it ended - field for field, after normalising exactly the fields
  RECEIPT_NORMALISED names, which are plan/9.0.md's list and nothing else,
  and comparing the confinement fields by rule: sabline-rt's level at least
  Python's, and every receipt where they differ printed;
- the audit stream of each of those runs, sabline.audit-stream/1, event for
  event in order - every effect, grant, refusal and declassification as it
  happened, between a `start` and an `end` that carries the receipt - with
  the same fields normalised where they appear, in `start` and in the
  receipt, and nothing else;
- the builtin tables both runtimes' checkers read, so that a builtin added
  to one and not the other is a difference before any program calls it;
- and for every budget agreement_budgets.py holds - sabline-spec's L1
  budget cases, what is made from them, and its edges - the budget
  document (sabline/check_dump.py's `budget_document`, the crate's
  `budget` module): what the budget parses to, or its refusal word for
  word. Both runtimes resolve its paths in one scratch directory holding a
  small tree of directories and links, since a path is resolved when a
  budget is parsed.

**What it does not read.** Nothing but the paths on its command line. No
environment variable, no configuration file, no flag that skips a corpus or
a comparison, no way to say "compare fewer things". `check_gate.py` scans
this file's syntax tree and fails if that stops being true, builds
sabline-rt with a difference injected and fails if this script does not go
red, and reads test.yml to check the job cannot be skipped. A gate that can
be turned off is a gate that will be.

The one thing it does that is not comparing: it builds sabline-rt if the
binary is not already there, because a gate that passes when there is
nothing to compare against is worse than no gate.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
RT = ROOT / "rt"

# The gate prints characters a program may hold, and a console that cannot
# encode one must not turn a reported difference into a traceback about
# the reporting. `sabline/cli.py` does the same thing for the same reason.
_reconfigure = getattr(sys.stdout, "reconfigure", None)
if _reconfigure is not None:
    try:
        _reconfigure(errors="backslashreplace")
    except Exception:
        pass

# Where sabline-spec's corpus is looked for when no path is given. The
# release and CI check it out beside this repository (test.yml) or one
# directory up (a local clone).
CORPUS_GUESSES = ("sabline-spec/tests", "../sabline-spec/tests")

# Sabline source inside a conformance case lives under one of these keys.
# A case that grows another key adds a line here, and until it does the
# case's programs are not compared - so `_case_sources` says how many
# programs it found and the gate prints it.
CASE_SOURCE_KEYS = ("source", "files", "tree", "change", "baseline")


class Difference(Exception):
    """Two runtimes answered differently about one program."""


# A program the gate deliberately does not write, so that both runtimes are
# asked about a path that is not a file. Every other corpus is a file that
# exists, so nothing else in the gate reaches E001.
MISSING = object()


# ---- finding the programs ---------------------------------------------------

def _vel_files(where: Path) -> list[Path]:
    return sorted(p for p in where.rglob("*.vel") if p.is_file())


def _case_sources(case: Any) -> list[tuple[str, str]]:
    """Every Sabline source in one conformance case, named by where it was."""
    out: list[tuple[str, str]] = []

    def walk(node: Any, where: str) -> None:
        if isinstance(node, str):
            if where.endswith(".vel") or where.endswith("source"):
                out.append((where, node))
            return
        if isinstance(node, dict):
            for key in sorted(node):
                walk(node[key], f"{where}.{key}")
            return
        if isinstance(node, list):
            for i, item in enumerate(node):
                walk(item, f"{where}[{i}]")

    given = case.get("input")
    if isinstance(given, dict):
        for key in CASE_SOURCE_KEYS:
            if key in given:
                walk(given[key], key)
    return out


def _conformance(corpus: Path) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for path in sorted(corpus.rglob("*.json")):
        if path.name == "case.schema.json":
            continue
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if not isinstance(case, dict) or "input" not in case:
            continue
        for where, source in _case_sources(case):
            rows.append((f"conformance/{case.get('id', path.stem)}/{where}",
                         source))
    return rows


def _from_module(name: str, pick: Any) -> list[tuple[str, str]]:
    """Programs a suite holds in a table of its own.

    Imported rather than parsed, so that a table which changes shape stops
    the gate instead of quietly contributing nothing.
    """
    sys.path.insert(0, str(ROOT))
    module = __import__(name)
    return list(pick(module))


# The effects whose builtins' work sabline-rt has (M3, the second
# checkpoint). A program the corpora write for a budget runs under that
# budget when it grants nothing else; one granting the network, Python or a
# tool runs under io alone, as every program does, until that work is
# ported - its refusal under io is compared, its work is not yet.
PORTED_EFFECTS = frozenset({"io", "fs", "clock", "rand", "env", "declassify"})


def _granted(allow: str | None, deny: str | None) -> set[str] | None:
    """The effects a budget's text names, less those denied: each item's
    name before its first ':' or '@'. None for `all`, which grants every
    effect."""
    names = set()
    for item in (DEFAULT_RUN_ALLOW if allow is None else allow).split(","):
        name = item.strip().split(":")[0].split("@")[0].strip()
        if name == "all":
            return None
        if name:
            names.add(name)
    return names - {n.strip() for n in (deny or "").split(",")}


DEFAULT_RUN_ALLOW = "io"


def _ported(allow: str | None, deny: str | None) -> bool:
    granted = _granted(allow, deny)
    return granted is not None and granted <= PORTED_EFFECTS


def _budgeted_corpus(corpus: Path) -> list[tuple[str, str, dict[str, Any]]]:
    """Every program to run under its own budget: the runs' corpus's
    budgeted table, check_sandbox.py's escapes and honest programs, and
    sabline-spec's L2 run cases - each of the last two whose budget grants
    only PORTED_EFFECTS - named, with its source and what the run is given
    (its budget, and agreement_runs.BUDGETED's seed, clock and ceiling)."""
    sys.path.insert(0, str(ROOT))
    import agreement_runs
    out: list[tuple[str, str, dict[str, Any]]] = [
        (f"budgeted/{name}", source, dict(given))
        for name, source, given in agreement_runs.BUDGETED]

    def budget(allow: Any, deny: Any) -> dict[str, Any]:
        return {k: v for k, v in (("allow", allow), ("deny", deny))
                if v is not None}

    sandbox = __import__("check_sandbox")
    for kind in ("ESCAPES", "HONEST"):
        for row in getattr(sandbox, kind, ()):
            name, source = _sandbox_row(row)
            allow, deny = row.get("allow"), row.get("deny")
            if source is not None and allow is not None and _ported(allow, deny):
                out.append((f"sandbox-budgeted/{kind.lower()}/{name}", source,
                            budget(allow, deny)))
    for path in sorted((corpus / "L2").rglob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        given = case.get("input") or {}
        if case.get("kind") == "run" and isinstance(given.get("source"), str) \
                and _ported(given.get("allow"), given.get("deny")):
            out.append((f"L2-budgeted/{case.get('id', path.stem)}",
                        given["source"],
                        budget(given.get("allow"), given.get("deny"))))
    return out


def _filled(text: Any, values: dict[str, str]) -> Any:
    """`text` with each placeholder the tree defines replaced."""
    if not isinstance(text, str):
        return text
    for key, value in values.items():
        text = text.replace(key, value)
    return text


def _lie_corpus() -> list[tuple[str, str]]:
    rows = _from_module(
        "check_prover_lies",
        lambda m: ((f"lie/{name}", case[-1]) for name, *case in m.LIES))
    return rows


def _sandbox_corpus() -> list[tuple[str, str]]:
    def pick(m: Any) -> Any:
        for kind in ("ESCAPES", "HONEST"):
            for row in getattr(m, kind, ()):
                name, source = _sandbox_row(row)
                if source is not None:
                    yield (f"sandbox/{kind.lower()}/{name}", source)
    return _from_module("check_sandbox", pick)


def _sandbox_row(row: Any) -> tuple[str, Any]:
    """A `check_sandbox.py` row's name and its program.

    A row is a mapping with `id`, `name` and `source` among its keys; the
    gate reads it by name so that a row which gains a field still
    contributes its program.
    """
    name = str(row.get("id") or row.get("name") or "?")
    source = row.get("source")
    return name, source if isinstance(source, str) else None


def _refusal_corpus() -> list[tuple[str, str]]:
    return _from_module(
        "check_refusals",
        lambda m: ((f"refusal/{code}/{name}", source)
                   for name, code, _proves, source in m.CASES))


def _termination_corpus() -> list[tuple[str, str]]:
    """check_termination.py's loops, each built to sit on one side of one
    edge of the rule - the input-bounded verdict's near misses among them."""
    return _from_module(
        "check_termination",
        lambda m: ((f"termination/{name}", source.lstrip())
                   for name, _verdicts, source in m.CASES))


# How many pieces every example is cut into. Cutting a program at a point
# inside it is the cheapest way there is to make a parse error that nobody
# wrote by hand, and cutting at the same points every time makes the corpus
# the same on every machine.
TRUNCATIONS = 15


def _truncations(files: list[Path]) -> list[tuple[str, str]]:
    out = []
    for path in files:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for k in range(1, TRUNCATIONS + 1):
            cut = len(source) * k // (TRUNCATIONS + 1)
            if cut:
                out.append((f"truncation/{path.name}/{k}", source[:cut]))
    return out


def collect(paths: list[str]) -> tuple[list[tuple[str, Any]], list[str], Path]:
    """Every program to compare, one line per corpus saying how many, and
    where sabline-spec's corpus was found.

    A program is either a path to a file, which both runtimes read
    themselves, or the **bytes** of one, which the gate writes into a
    directory both runtimes then read, or several files by name - a
    program and the libraries it imports - which the gate writes into a
    folder of their own. Reading a file is the path a user's
    program takes, so it is the path the gate takes too - and bytes rather
    than text because a byte-order mark, a lone carriage return and a
    sequence that is not UTF-8 are three of the things that have to agree.
    """
    files: list[Path] = []
    texts: list[tuple[str, str]] = []
    counts: list[str] = []

    examples: list[Path] = []
    for where in (ROOT / "examples", ROOT / "stdlib",
                  ROOT / "benchmark" / "corpus", ROOT / "tests" / "error_messages"):
        found = _vel_files(where)
        if where.name == "examples":
            examples = list(found)
        files += found
        counts.append(f"{where.relative_to(ROOT).as_posix()}: {len(found)} files")

    corpora = [Path(p) for p in paths] or [
        ROOT / guess for guess in CORPUS_GUESSES]
    corpus = next((c for c in corpora if (c / "L1").is_dir() or
                   any(c.glob("**/*.json"))), None)
    if corpus is None:
        raise SystemExit(
            "check_agreement.py: sabline-spec's corpus is not where it was "
            "looked for (" + ", ".join(str(c) for c in corpora) + "). Give "
            "its path: python check_agreement.py ../sabline-spec/tests")
    cases = _conformance(corpus)
    texts += cases
    counts.append(f"{corpus}: {len(cases)} programs in cases")

    for name, rows in (("the lie corpus", _lie_corpus()),
                       ("check_sandbox.py", _sandbox_corpus()),
                       ("check_refusals.py", _refusal_corpus()),
                       ("check_termination.py", _termination_corpus()),
                       ("truncations of every example", _truncations(examples))):
        texts += rows
        counts.append(f"{name}: {len(rows)} programs")

    edges = _from_module("agreement_edges", lambda m: m.cases())
    counts.append(f"the adversarial corpus: {len(edges)} programs")
    # the checkers' corpus (M2): a mistake made in every example and
    # library at fixed places, and a table of the refusals no mutation
    # reaches - the half of the checkers the corpora above barely touch
    checks = _from_module("agreement_checks", lambda m: m.cases())
    counts.append(f"the checkers' corpus: {len(checks)} programs")
    # the runs' corpus (M3): the text builtins on lone surrogates, astral
    # characters and combining marks, and the rest of what a run does that
    # is CPython's own - every program here is written to be run
    runs = _from_module("agreement_runs", lambda m: m.cases())
    counts.append(f"the runs' corpus: {len(runs)} programs")

    # and the one refusal that is not about a program's contents: a path
    # that is not a file. Both runtimes must give E001 with the same
    # message, and neither corpus above can ask that, because every one of
    # them is a file that exists.
    missing = [("missing/no-such-file", MISSING),
               ("missing/a-directory-not-a-file", MISSING)]
    counts.append(f"paths that are not files: {len(missing)} programs")

    return ([(str(f), None) for f in files]
            + [(n, t.encode("utf-8")) for n, t in texts]
            + list(edges) + list(checks) + list(runs) + missing), counts, corpus


# ---- asking each runtime ----------------------------------------------------

def rt_binary() -> Path:
    """sabline-rt, built if it is not there.

    Release first, then debug: whichever exists is what CI just built. A
    gate that could not find it would be a gate that passes by comparing
    nothing, so not finding it and not being able to build it is a failure.
    """
    exe = "sabline-rt.exe" if os.name == "nt" else "sabline-rt"
    for profile in ("release", "debug"):
        candidate = RT / "target" / profile / exe
        if candidate.exists():
            return candidate
    if shutil.which("cargo") is None:
        raise SystemExit(
            "check_agreement.py: sabline-rt is not built and cargo is not "
            "here, so there is nothing to compare against. Install Rust "
            "(https://rustup.rs) or run: cargo build --release --manifest-path "
            "rt/Cargo.toml")
    print("check_agreement.py: building sabline-rt", flush=True)
    subprocess.run(["cargo", "build", "--release", "--manifest-path",
                    str(RT / "Cargo.toml")], check=True)
    built = RT / "target" / "release" / exe
    if not built.exists():
        raise SystemExit(f"check_agreement.py: cargo built nothing at {built}")
    return built


BATCH_HEADER = b"sabline.ast-batch/1\n"
CHECK_BATCH_HEADER = b"sabline.check-batch/1\n"
BUDGET_BATCH_HEADER = b"sabline.budget-batch/1\n"
RUN_BATCH_HEADER = b"sabline.run-batch/3\n"

# What the gate does not compare in a receipt, and nothing else: plan/9.0.md,
# "What is normalised, and nothing else is". Each is a place the gate stops
# looking, so a field joins this list only with its own argument in the
# pull request that adds it, and check_gate.py holds the list to the plan's.
# The value is replaced where the field is there, never put where it is not,
# so a receipt that drops one of these is still a difference.
RECEIPT_NORMALISED = (
    # sabline-lang and sabline-rt, and their versions: they are supposed to
    # differ
    "predicate.producer.name",
    "predicate.producer.version",
    # a clock and a duration
    "predicate.startedAt",
    "predicate.wall_time_ms",
    # a program given as text: identical in practice, listed because it is
    # derived from a path
    "subject[*].name, where it is <source>",
)
# Compared by rule, not by equality: each is present in both, the level is
# one of CONFINEMENT_LEVELS, and sabline-rt's is at least Python's. M4
# makes it strictly greater on Windows, where equality would fail for the
# right reason. Every receipt where they differ is printed.
CONFINEMENT_FIELDS = ("confinement", "confinement_reason",
                      "confinement_layers", "os_policy_sha256")
CONFINEMENT_LEVELS = ("none", "partial", "full")
NORMALISED = "<normalised>"

# The programs the gate does not run, each with the reason, which the gate
# prints. A program joins this list only with its own argument in the pull
# request that adds it, because each is a place the gate stops looking -
# and it is still parsed and checked like every other program. It is empty:
# the one program it held, tests/error_messages/E611_run_memory_cap.vel,
# which doubles a text forty times, is stopped by the run document's size
# limit from 9.0's second M3 checkpoint, at the same operation in both.
RUN_EXCLUDED: dict[str, str] = {}


def _run_name(name: str) -> str:
    """A program's name as RUN_EXCLUDED writes it: a path under this
    checkout, with forward slashes."""
    try:
        return Path(name).resolve().relative_to(ROOT).as_posix()
    except (ValueError, OSError):
        return name


def _run(command: list[str], cwd: Path | None = None) -> bytes:
    done = subprocess.run(command, capture_output=True, cwd=cwd)
    if done.returncode not in (0, 1):
        raise SystemExit(
            f"check_agreement.py: {command[0]} ended {done.returncode} for "
            f"the whole batch, which is neither 'every program parsed' nor "
            f"'one did not':\n{done.stderr.decode('utf-8', 'replace')[:4000]}")
    return done.stdout


def dumps(runtime: list[str], listing: Path,
          heading: bytes = BATCH_HEADER,
          cwd: Path | None = None) -> list[tuple[str, bytes]]:
    """Each path and the bytes of its canonical document, in order.

    The bytes are kept as bytes: comparing them is the comparison, and a
    document is read only to say where two of them differ.
    """
    stream = _run(runtime + [str(listing)], cwd)
    if not stream.startswith(heading):
        raise SystemExit(
            f"check_agreement.py: {runtime[0]} did not write a batch "
            f"stream:\n{stream[:2000]!r}")
    out: list[tuple[str, bytes]] = []
    at = len(heading)
    while at < len(stream):
        end = stream.find(b"\n", at)
        if end < 0 or not stream.startswith(b"--- ", at):
            raise SystemExit(
                f"check_agreement.py: {runtime[0]}'s batch stream breaks at "
                f"byte {at}:\n{stream[at:at + 400]!r}")
        header = stream[at + 4:end].decode("utf-8", "replace")
        size, _, path = header.partition(" ")
        try:
            length = int(size)
        except ValueError:
            raise SystemExit(f"check_agreement.py: '{header}' is not a record")
        body = stream[end + 1:end + 1 + length]
        if len(body) != length or stream[end + 1 + length:end + 2 + length] != b"\n":
            raise SystemExit(
                f"check_agreement.py: {runtime[0]}'s record for {path} is "
                f"{len(body)} bytes and says {length}")
        out.append((path, body))
        at = end + 2 + length
    return out


# ---- the comparison ---------------------------------------------------------

def _first_difference(a: Any, b: Any, where: str = "") -> str | None:
    if type(a) is not type(b):
        return f"{where or 'the document'}: python has a {type(a).__name__}, " \
               f"sabline-rt a {type(b).__name__}"
    if isinstance(a, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a:
                return f"{where}.{key}: only sabline-rt has it"
            if key not in b:
                return f"{where}.{key}: only python has it"
            found = _first_difference(a[key], b[key], f"{where}.{key}")
            if found:
                return found
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{where}: python has {len(a)} items, sabline-rt {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            found = _first_difference(x, y, f"{where}[{i}]")
            if found:
                return found
        return None
    if a != b:
        return f"{where or 'the document'}: python has {a!r}, sabline-rt {b!r}"
    return None


def _told(left: bytes, right: bytes) -> str:
    """Where two documents differ, said as a path through the tree.

    Reading a document is recursive and a document can be 4,000 levels
    deep, so a document that will not read falls back to the byte the two
    first differ at - which is a worse sentence and never a wrong one.
    """
    try:
        return (_first_difference(json.loads(left), json.loads(right))
                or "the documents differ in bytes but not in content")
    except (ValueError, RecursionError):
        at = next((i for i, (x, y) in enumerate(zip(left, right)) if x != y),
                  min(len(left), len(right)))
        window = slice(max(0, at - 60), at + 60)
        return (f"byte {at}: python has {left[window]!r}, sabline-rt "
                f"{right[window]!r}")


def compare(python: list[tuple[str, bytes]],
            rust: list[tuple[str, bytes]],
            names: list[str]) -> list[str]:
    """Every program the two answered differently about, one line each."""
    if len(python) != len(rust):
        raise SystemExit(f"check_agreement.py: python answered about "
                         f"{len(python)} programs and sabline-rt about "
                         f"{len(rust)}")
    if len(python) != len(names):
        raise SystemExit(f"check_agreement.py: {len(names)} programs were "
                         f"given and {len(python)} answered about")
    out = []
    for (left_path, left), (right_path, right), name in zip(python, rust, names):
        if left_path != right_path:
            raise SystemExit("check_agreement.py: the two batches are not in "
                             "the same order")
        if left != right:
            out.append(f"{name}: {_told(left, right)}")
    return out


def runs_and_receipts(records: list[tuple[str, bytes]]
                      ) -> tuple[list[tuple[str, bytes]],
                                 list[tuple[str, bytes]],
                                 list[tuple[str, bytes]]]:
    """A run batch's records, three a program, as its run documents, its
    receipts and its audit streams."""
    if len(records) % 3:
        raise SystemExit(f"check_agreement.py: a run batch of {len(records)} "
                         f"records is not a document, a receipt and a stream "
                         f"a program")
    documents, receipts, streams = records[::3], records[1::3], records[2::3]
    for (path, _), (again, _), (third, _) in zip(documents, receipts, streams):
        if not path == again == third:
            raise SystemExit(f"check_agreement.py: the receipt and stream after "
                             f"{path}'s run document are {again}'s and "
                             f"{third}'s")
    return documents, receipts, streams


def _normalised(receipt: Any) -> tuple[Any, dict[str, Any] | None]:
    """A receipt with exactly RECEIPT_NORMALISED replaced, and its
    confinement fields taken out to be compared by rule."""
    if not isinstance(receipt, dict):
        return receipt, None
    predicate = receipt.get("predicate")
    if isinstance(predicate, dict):
        producer = predicate.get("producer")
        if isinstance(producer, dict):
            for key in ("name", "version"):
                if key in producer:
                    producer[key] = NORMALISED
        for key in ("startedAt", "wall_time_ms"):
            if key in predicate:
                predicate[key] = NORMALISED
    for subject in receipt.get("subject") or []:
        if isinstance(subject, dict) and subject.get("name") == "<source>":
            subject["name"] = NORMALISED
    parameters = predicate.get("run_parameters") if isinstance(
        predicate, dict) else None
    if not isinstance(parameters, dict):
        return receipt, None
    return receipt, {key: parameters.pop(key) for key in CONFINEMENT_FIELDS
                     if key in parameters}


def _confinement_rule(python: dict[str, Any] | None,
                      rust: dict[str, Any] | None) -> str | None:
    """Why two receipts' confinement fails the rule, or None."""
    if python is None or rust is None:
        return None if python == rust else "only one has run_parameters"
    for name, fields in (("python", python), ("sabline-rt", rust)):
        missing = [k for k in CONFINEMENT_FIELDS if k not in fields]
        if missing:
            return f"{name}'s has no {', '.join(missing)}"
        if fields["confinement"] not in CONFINEMENT_LEVELS:
            return f"{name}'s level is {fields['confinement']!r}"
    if (CONFINEMENT_LEVELS.index(rust["confinement"])
            < CONFINEMENT_LEVELS.index(python["confinement"])):
        return (f"sabline-rt's confinement is {rust['confinement']} where "
                f"python's is {python['confinement']}")
    return None


def compare_receipts(python: list[tuple[str, bytes]],
                     rust: list[tuple[str, bytes]],
                     names: list[str]) -> tuple[list[str], list[str]]:
    """Every program whose receipts differ, after the normalisation, one
    line each; and every one whose confinement differs within the rule."""
    if len(python) != len(rust) or len(python) != len(names):
        raise SystemExit(f"check_agreement.py: {len(names)} runs, "
                         f"{len(python)} python receipts and {len(rust)} "
                         f"sabline-rt receipts")
    out, by_rule = [], []
    for (left_path, left), (right_path, right), name in zip(python, rust,
                                                            names):
        if left_path != right_path:
            raise SystemExit("check_agreement.py: the two batches are not in "
                             "the same order")
        a, held_a = _normalised(json.loads(left))
        b, held_b = _normalised(json.loads(right))
        found = _first_difference(a, b, "receipt")
        if found is None:
            found = _confinement_rule(held_a, held_b)
        if found is not None:
            out.append(f"{name}: {found}")
        elif held_a != held_b:
            by_rule.append(f"{name}: python {held_a}, sabline-rt {held_b}")
    return out, by_rule


def _normalised_stream(stream: Any) -> tuple[Any, dict[str, Any] | None]:
    """An audit stream with exactly RECEIPT_NORMALISED replaced where it
    appears - in `start` and in the receipt `end` carries - and the
    receipt's confinement fields taken out to be compared by rule."""
    if not isinstance(stream, list):
        return stream, None
    held = None
    for event in stream:
        if not isinstance(event, dict):
            continue
        if event.get("event") == "start":
            producer = event.get("producer")
            if isinstance(producer, dict):
                for key in ("name", "version"):
                    if key in producer:
                        producer[key] = NORMALISED
            if "startedAt" in event:
                event["startedAt"] = NORMALISED
        elif event.get("event") == "subjects":
            for subject in event.get("subject") or []:
                if isinstance(subject, dict) and \
                        subject.get("name") == "<source>":
                    subject["name"] = NORMALISED
        elif event.get("event") == "end":
            event["receipt"], held = _normalised(event.get("receipt"))
    return stream, held


def compare_streams(python: list[tuple[str, bytes]],
                    rust: list[tuple[str, bytes]],
                    names: list[str]) -> list[str]:
    """Every program whose audit streams differ, after the normalisation,
    one line each."""
    if len(python) != len(rust) or len(python) != len(names):
        raise SystemExit(f"check_agreement.py: {len(names)} runs, "
                         f"{len(python)} python streams and {len(rust)} "
                         f"sabline-rt streams")
    out = []
    for (_, left), (_, right), name in zip(python, rust, names):
        a, held_a = _normalised_stream(json.loads(left))
        b, held_b = _normalised_stream(json.loads(right))
        if isinstance(a, list) and isinstance(b, list) and len(a) != len(b):
            kinds = [e.get("event") if isinstance(e, dict) else None
                     for e in a]
            others = [e.get("event") if isinstance(e, dict) else None
                      for e in b]
            at = next((i for i, (x, y) in enumerate(zip(kinds, others))
                       if x != y), min(len(kinds), len(others)))
            out.append(f"{name}: python streams {len(a)} events and "
                       f"sabline-rt {len(b)}, first apart at event {at}: "
                       f"{kinds[at] if at < len(kinds) else 'nothing'} and "
                       f"{others[at] if at < len(others) else 'nothing'}")
            continue
        found = _first_difference(a, b, "stream") or _confinement_rule(
            held_a, held_b)
        if found is not None:
            out.append(f"{name}: {found}")
    return out


def tables(binary: Path) -> tuple[bytes, bytes]:
    """The builtin tables each runtime's checkers read, as one document
    each: a builtin added to one and not the other is a difference on the
    commit that adds it, whether or not any program calls it yet."""
    python = _run([sys.executable, str(ROOT / "sabline.py"), "check-dump",
                   "--tables"])
    rust = _run([str(binary), "tables"])
    return python.rstrip(b"\n"), rust.rstrip(b"\n")


def main(argv: list[str]) -> int:
    programs, counts, corpus = collect(argv)
    budgeted_runs = _budgeted_corpus(corpus)
    counts.append(f"programs run under their own budgets: {len(budgeted_runs)}")
    sys.path.insert(0, str(ROOT))
    import agreement_budgets                 # the budgets' corpus (M2)
    budgets, budget_counts = agreement_budgets.cases(corpus)
    binary = rt_binary()
    with tempfile.TemporaryDirectory(prefix="sabline-agreement-") as tmp:
        here = Path(tmp)
        listing = []
        for i, (name, payload) in enumerate(programs):
            if payload is None:
                listing.append(name)
                continue
            if payload is MISSING:
                # named, never written: both runtimes must answer E001
                listing.append(str(here / f"{i:05d}-not-written.vel"))
                continue
            if isinstance(payload, dict):
                # a program of several files: written into a folder of its
                # own, so that each import finds its library beside it, and
                # asked about by its first file
                folder = here / f"{i:05d}"
                folder.mkdir()
                for file_name, data in payload.items():
                    (folder / file_name).write_bytes(data)
                listing.append(str(folder / next(iter(payload))))
                continue
            # a program that is not a file becomes one, because reading a
            # file is the path a user's program takes
            written = here / f"{i:05d}.vel"
            written.write_bytes(payload)
            listing.append(str(written))
        paths = here / "paths.txt"
        paths.write_text("\n".join(listing) + "\n", encoding="utf-8")

        # the parsers: the tree, or the refusal (M1)
        python = dumps([sys.executable, str(ROOT / "sabline.py"), "ast",
                        "--json", "--list"], paths)
        rust = dumps([str(binary), "ast", "--list"], paths)
        # the checkers: what `sabline check` finds, stage by stage, and
        # every loop's verdict (M2). Both are told the same place for the
        # shipped standard library - this checkout, which is where the
        # Python package that runs here keeps its own.
        python_checks = dumps([sys.executable, str(ROOT / "sabline.py"),
                               "check-dump", "--list"], paths,
                              CHECK_BATCH_HEADER)
        rust_checks = dumps([str(binary), "check", "--install-dir",
                             str(ROOT), "--list"], paths, CHECK_BATCH_HEADER)
        # the budget parser (M2): each budget case's document, both
        # runtimes resolving its paths in one scratch directory that holds
        # the tree agreement_budgets.py's paths walk through
        budget_list = here / "budgets.jsonl"
        budget_list.write_text(
            "".join(json.dumps([allow, deny]) + "\n"
                    for _, allow, deny in budgets), encoding="utf-8")
        scratch = here / "cwd"
        scratch.mkdir()
        unmade = agreement_budgets.prepare(scratch)
        python_budgets = dumps([sys.executable, str(ROOT / "sabline.py"),
                                "check-dump", "--budgets"], budget_list,
                               BUDGET_BATCH_HEADER, scratch)
        rust_budgets = dumps([str(binary), "budget", "--list"], budget_list,
                             BUDGET_BATCH_HEADER, scratch)
        # the interpreters (M3): each program run as `sabline <file>` runs
        # it, under io, with a fixed input and arguments and a step limit -
        # sabline/run_dump.py says what is fixed and why
        runs = [(name, path) for (name, _), path in zip(programs, listing)
                if _run_name(name) not in RUN_EXCLUDED]
        run_paths = here / "runs.txt"
        run_paths.write_text("\n".join(path for _, path in runs) + "\n",
                             encoding="utf-8")
        python_runs = dumps([sys.executable, str(ROOT / "sabline.py"),
                             "run-dump", "--list"], run_paths,
                            RUN_BATCH_HEADER)
        rust_runs = dumps([str(binary), "run", "--install-dir", str(ROOT),
                           "--list"], run_paths, RUN_BATCH_HEADER)
        # the interpreters under their budgets (M3): each run in the same
        # tree, made afresh before each runtime's turn, so that what one
        # runtime wrote is not there for the other to find; `~` is the
        # tree's home for both, set by the run document, not by this file
        import agreement_runs
        under = here / "tree"
        values = agreement_runs.tree(under)
        written = here / "budgeted"
        written.mkdir()
        lines = []
        for i, (_, source, given) in enumerate(budgeted_runs):
            program = written / f"{i:05d}.vel"
            program.write_bytes(_filled(source, values).encode("utf-8"))
            entry: dict[str, Any] = {"path": str(program)}
            entry.update({k: _filled(v, values) for k, v in given.items()})
            entry["environ"] = agreement_runs.run_variables(values)
            lines.append(json.dumps(entry))
        budgeted_paths = here / "budgeted.txt"
        budgeted_paths.write_text("\n".join(lines) + "\n", encoding="utf-8")
        python_budgeted = dumps([sys.executable, str(ROOT / "sabline.py"),
                                 "run-dump", "--list"], budgeted_paths,
                                RUN_BATCH_HEADER, under)
        shutil.rmtree(under)
        agreement_runs.tree(under)
        rust_budgeted = dumps([str(binary), "run", "--install-dir", str(ROOT),
                               "--list"], budgeted_paths, RUN_BATCH_HEADER,
                              under)

    # the names the gate reports are the corpus names, not the temporary
    # paths it wrote them to
    names = [name for name, _ in programs]
    parsed = compare(python, rust, names)
    checked = compare(python_checks, rust_checks, names)
    budgeted = compare(python_budgets, rust_budgets,
                       [name for name, _, _ in budgets])
    python_runs, python_receipts, python_streams = runs_and_receipts(
        python_runs)
    rust_runs, rust_receipts, rust_streams = runs_and_receipts(rust_runs)
    (python_budgeted, python_budgeted_receipts,
     python_budgeted_streams) = runs_and_receipts(python_budgeted)
    (rust_budgeted, rust_budgeted_receipts,
     rust_budgeted_streams) = runs_and_receipts(rust_budgeted)
    ran = compare(python_runs, rust_runs, [name for name, _ in runs])
    ran_budgeted = compare(python_budgeted, rust_budgeted,
                           [name for name, _, _ in budgeted_runs])
    receipted, by_rule = compare_receipts(
        python_receipts + python_budgeted_receipts,
        rust_receipts + rust_budgeted_receipts,
        [name for name, _ in runs] + [name for name, _, _ in budgeted_runs])
    streamed = compare_streams(
        python_streams + python_budgeted_streams,
        rust_streams + rust_budgeted_streams,
        [name for name, _ in runs] + [name for name, _, _ in budgeted_runs])
    python_tables, rust_tables = tables(binary)
    tabled = ([] if python_tables == rust_tables else
              [f"the builtin tables: {_told(python_tables, rust_tables)}"])

    for line in counts + budget_counts:
        print(f"  {line}")
    if unmade:
        print(f"  (this system would not make: {', '.join(unmade)}; those "
              f"paths are compared as paths that do not exist)")
    held = {_run_name(name) for name, _ in programs}
    for name, why in RUN_EXCLUDED.items():
        if name not in held:
            # an exclusion that names nothing would outlive its reason
            raise SystemExit(f"check_agreement.py: RUN_EXCLUDED names {name}, "
                             f"which is in no corpus")
        print(f"  (parsed and checked, not run: {name} - {why})")
    rows = (("the parsers", len(programs), parsed),
            ("the checkers", len(programs), checked),
            ("the budget parser", len(budgets), budgeted),
            ("the interpreters", len(runs), ran),
            ("the interpreters, under their budgets", len(budgeted_runs),
             ran_budgeted),
            ("the receipts", len(runs) + len(budgeted_runs), receipted),
            ("the audit streams", len(runs) + len(budgeted_runs), streamed),
            ("the builtin tables", 1, tabled))
    print(f"  receipts normalised: {'; '.join(RECEIPT_NORMALISED)}; "
          f"{', '.join(CONFINEMENT_FIELDS)} by rule")
    for line in by_rule:
        print(f"  (confinement differs, within the rule: {line})")
    for what, many, found in rows:
        print(f"  {what}: {many} compared, {many - len(found)} agree, "
              f"{len(found)} differ")
    total = sum(many for _, many, _ in rows)
    differences = [f"{what}: {line}" for what, _, found in rows[:-1]
                   for line in found] + tabled
    print(f"agreement gate: {total} comparisons, "
          f"{total - len(differences)} agreements, "
          f"{len(differences)} differences")
    if differences:
        print()
        for line in differences[:40]:
            print(f"DIFFERENCE {line}")
        if len(differences) > 40:
            print(f"... and {len(differences) - 40} more")
        print("\nThe two runtimes do not agree. plan/9.0.md: where they "
              "disagree, the Python package is right and sabline-rt has a "
              "defect, until the demotion criteria are met.")
        return 1
    print("the two runtimes agree on every program")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
