"""The agreement gate: two runtimes, the same inputs, no difference.

    python check_agreement.py [corpus paths...]

It runs the Python parser and sabline-rt over every Sabline source this
project has and fails on any difference in the AST dump, the error code,
the error message, the fixes or the line. plan/9.0.md designs it; this is
9.0.0-alpha.1's cut of it, which compares what alpha.1 built - a lexer and
a parser - and is written so that alpha.2 adds verdicts, alpha.3 adds runs
and receipts, and neither has to change what is here.

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

**What it compares.** One canonical document per source (sabline/ast_dump.py
and the crate's `dump` module say what is in it), byte for byte. The
document holds the whole tree when the source parses and the code, message,
fixes and line when it does not, so one comparison covers both.

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


def collect(paths: list[str]) -> tuple[list[tuple[str, Any]], list[str]]:
    """Every program to compare, and one line per corpus saying how many.

    A program is either a path to a file, which both runtimes read
    themselves, or the **bytes** of one, which the gate writes into a
    directory both runtimes then read. Reading a file is the path a user's
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
                       ("truncations of every example", _truncations(examples))):
        texts += rows
        counts.append(f"{name}: {len(rows)} programs")

    edges = _from_module("agreement_edges", lambda m: m.cases())
    counts.append(f"the adversarial corpus: {len(edges)} programs")

    # and the one refusal that is not about a program's contents: a path
    # that is not a file. Both runtimes must give E001 with the same
    # message, and neither corpus above can ask that, because every one of
    # them is a file that exists.
    missing = [("missing/no-such-file", MISSING),
               ("missing/a-directory-not-a-file", MISSING)]
    counts.append(f"paths that are not files: {len(missing)} programs")

    return ([(str(f), None) for f in files]
            + [(n, t.encode("utf-8")) for n, t in texts]
            + list(edges) + missing), counts


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


def _run(command: list[str]) -> bytes:
    done = subprocess.run(command, capture_output=True)
    if done.returncode not in (0, 1):
        raise SystemExit(
            f"check_agreement.py: {command[0]} ended {done.returncode} for "
            f"the whole batch, which is neither 'every program parsed' nor "
            f"'one did not':\n{done.stderr.decode('utf-8', 'replace')[:4000]}")
    return done.stdout


def dumps(runtime: list[str], listing: Path) -> list[tuple[str, bytes]]:
    """Each path and the bytes of its canonical document, in order.

    The bytes are kept as bytes: comparing them is the comparison, and a
    document is read only to say where two of them differ.
    """
    stream = _run(runtime + [str(listing)])
    if not stream.startswith(BATCH_HEADER):
        raise SystemExit(
            f"check_agreement.py: {runtime[0]} did not write a batch "
            f"stream:\n{stream[:2000]!r}")
    out: list[tuple[str, bytes]] = []
    at = len(BATCH_HEADER)
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


def main(argv: list[str]) -> int:
    programs, counts = collect(argv)
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
            # a program that is not a file becomes one, because reading a
            # file is the path a user's program takes
            written = here / f"{i:05d}.vel"
            written.write_bytes(payload)
            listing.append(str(written))
        paths = here / "paths.txt"
        paths.write_text("\n".join(listing) + "\n", encoding="utf-8")

        python = dumps([sys.executable, str(ROOT / "sabline.py"), "ast",
                        "--json", "--list"], paths)
        rust = dumps([str(binary), "ast", "--list"], paths)

    # the names the gate reports are the corpus names, not the temporary
    # paths it wrote them to
    differences = compare(python, rust, [name for name, _ in programs])
    for line in counts:
        print(f"  {line}")
    print(f"agreement gate: {len(programs)} programs, "
          f"{len(programs) - len(differences)} agreements, "
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
