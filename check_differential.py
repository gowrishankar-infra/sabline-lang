#!/usr/bin/env python3
"""Two versions of Sabline run the same programs; every difference is named.

    python check_differential.py                     # working tree vs the newest older tag
    python check_differential.py --old v8.1.1
    python check_differential.py --new v8.2.0 --old v8.1.1 --benchmark full
    python check_differential.py --corpus examples,conformance --json diff.json

THE TWO VERSIONS. --new is the working tree unless a ref is given. --old is
the newest tag vX.Y.Z whose version is below the new tree's VERSION (read
from sabline/version.py, or from sabline.py where the compiler is one file,
or from velaris/version.py or velaris.py in a tree from before the 8.6
rename,
as it was up to 8.1.1). A ref is checked out with `git worktree add --detach`
into this suite's scratch directory - or, when git refuses that, extracted
from `git archive` - and removed when the suite ends, whether it passed,
failed or was interrupted. Both versions run under one Python (--python, by
default the one running this file) as `python sabline.py`, which starts the
compiler in either layout. The children's environment is this one without
PYTHONPATH, with PYTHONIOENCODING=utf-8, NO_COLOR=1, and both spellings of
the cache directory set to a scratch directory per side (so an 8.1.x proof cache is neither read
from nor written to the user's).

WHAT IS COMPARED, program by program:

  examples     Every program in run_tests.py's EXPECT, run as run_tests.py
               runs it: `python sabline.py examples/NAME` with its ALLOW
               budget, its ARGS and its STDIN (an empty stdin when it has
               none). Each version uses its own run_tests.py and examples/;
               each program runs in a fresh directory of its own, --jobs at
               a time. A program whose budget grants `rand` or `clock` also
               gets `--seed 1 --freeze-time 1767225600` when that version is
               8.0 or later (the flags came in 8.0), so a dice roll or the
               time of day is not a difference. Compared: the exit code,
               stdout and stderr.
  conformance  `python sabline.py conformance --corpus DIR --json` over
               sabline-spec's corpus (--spec; by default sabline-spec/tests
               inside or beside this checkout). Compared: each case id's
               verdict, the report's `result` (pass, fail or skip). The
               detail is shown beside a difference, not compared.
  benchmark    `python benchmark/run.py`, each version its own harness and
               corpus: --benchmark quick (the default, one program per
               category, enough for CI) or --benchmark full (every program,
               the monthly job). Compared: each program's verdict for each
               tool the harness records (sabline, deno, python). Never a
               timing, and never the evidence text.

A program or case present on one side only is a difference too. An argument
in ARGS that is a relative path naming a file in that version's tree (as
run_tests.py wrote sample.txt before 8.1) is passed as that file's absolute
path, since the program no longer runs from the checkout.

UNSTABLE. Every example or benchmark program that differs is run once more
under both versions (a benchmark program with --only). When a version's two
runs of it disagree - a program that reaches the network, a verdict that
turns on the 5 s deadline of a loaded machine - it is reported as UNSTABLE
with the diff between those two runs, and it is not compared: it neither
fails the suite nor counts as named. A conformance case runs once; its
runner has no way to run a single case again.

NORMALISED, identically on both sides and in this order, before stdout,
stderr and a conformance detail are compared or shown:

  1. Line ends: CRLF becomes LF.
  2. Absolute paths: that version's tree -> <root>; the program's own run
     directory -> <work>; the conformance corpus -> <spec>; this suite's
     scratch directory -> <scratch>; the Python installation (prefix,
     base prefix) -> <python>; the system temporary directory -> <tmp>;
     the home directory -> <home>. Longest first. Each is matched with \\, /
     or a doubled \\ (as JSON writes it) between its parts, and without
     regard to case on Windows; the realpath spelling is matched too. A
     directory directly under <tmp> - a mkdtemp name - becomes <tmpdir>.
  3. Separators: what follows one of those placeholders up to the end of
     the path, and a relative path of file-name characters joined by \\ that
     ends in a name with an extension (examples\\hello.vel), is written with
     / instead.
  4. The version string: each side's own VERSION (8.1.1, 8.2.0), standing
     as a whole number, becomes <version>.
  5. Timing text: a number followed by `ms` (as in `[--time] ran in 12.3
     ms`); a decimal number followed by s, sec, secs, second or seconds; the
     number a JSON key ending in _ms, _s or seconds holds; an ISO 8601
     timestamp; and a 0x address of six or more hex digits.

Nothing else is changed: a message reworded, a code renumbered, a line
moved, a verdict turned - each is a difference.

NAMED IN THE CHANGELOG. A difference is allowed only when the new version's
CHANGELOG.md, in its entry for the new version (the section under the
`## X.Y.Z` heading, where `## 8.2` stands for 8.2.0; --entry picks another),
names it:

  an example           its path, as `examples/foo.vel`, appears in the entry;
  a conformance case   its id appears;
  a benchmark program  its name appears;

each as a whole token, backticks allowed. Or the entry has a line

  differential: <path, id or name> - <why>

(a list bullet and backticks allowed; a benchmark program may be given by
its id there), which names it with the reason. Every difference is printed
with a short diff and whether, and how, the CHANGELOG names it.

EXIT: 0 when every difference is named (or there is none); 1 when one is
not; 2 when the comparison could not run - no older tag, a ref git cannot
check out, a Python that does not start, or a corpus or harness that
produced no result.
"""
from __future__ import annotations

import argparse
import atexit
import difflib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, cast

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from suite_dirs import isolate  # noqa: E402

CORPORA = ("examples", "conformance", "benchmark")
BENCH_VERDICTS = ("caught-before-run", "caught-during-run", "missed",
                  "not-applicable", "false-positive", "tool-absent")
EXAMPLE_TIMEOUT = 300           # seconds per example, as run_tests.py
CONFORMANCE_TIMEOUT = 1800
BENCHMARK_TIMEOUT = 4 * 3600
DETERMINISM_FLAGS = (8, 0, 0)   # --seed and --freeze-time exist from here
FROZEN_AT = "1767225600"        # 2026-01-01T00:00:00Z, as epoch seconds
DIFF_LINES = 16                 # lines of a unified diff shown per stream
DETAIL_CHARS = 300


class CannotRun(Exception):
    """The comparison could not be made: exit 2."""


def ascii_text(text: str) -> str:
    return text.encode("ascii", "backslashreplace").decode("ascii")


def say(*parts: Any, err: bool = False) -> None:
    print(ascii_text(" ".join(str(p) for p in parts)),
          file=sys.stderr if err else sys.stdout, flush=True)


def tail(data: bytes, lines: int = 6) -> str:
    text = data.decode("utf-8", "replace").strip().splitlines()
    return " | ".join(text[-lines:]) if text else "(nothing on stderr)"


# ------------------------------------------------------------------- git

def git(args: list[Any], timeout: float = 900) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(["git"] + list(args), cwd=str(HERE),
                              capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise CannotRun(f"git {' '.join(args)} could not run: {e}")


def git_out(args: list[Any], what: str) -> str:
    done = git(args)
    if done.returncode != 0:
        said = done.stderr.decode("utf-8", "replace").strip()
        raise CannotRun(f"{what} (git {' '.join(args)}"
                        + (f": {said}" if said else "") + ")")
    return done.stdout.decode("utf-8", "replace").strip()


VERSION_LINE = re.compile(r'^VERSION\s*=\s*"(\d+(?:\.\d+)*)"', re.M)


def version_tuple(text: str) -> tuple[Any, ...]:
    parts = [int(x) for x in text.split(".")]
    return tuple((parts + [0, 0, 0])[:3])


# Where a checkout keeps the compiler, newest spelling first: the package
# from 8.2, the single file before it, and both under the name the project
# had before 8.6 renamed it Sabline. A tag from 8.5 or earlier is a tree
# with velaris/ and velaris.py in it, and this suite has to run it.
LAYOUTS = (("sabline", "version.py"), ("sabline.py",),
           ("velaris", "version.py"), ("velaris.py",))
ENTRY_POINTS = ("sabline.py", "velaris.py")


def tree_version(root: Path) -> str:
    """VERSION as the tree at `root` declares it, in either layout and
    under either of the project's two names."""
    for rel in LAYOUTS:
        path = root.joinpath(*rel)
        if path.is_file():
            m = VERSION_LINE.search(path.read_text(encoding="utf-8",
                                                   errors="replace"))
            if m:
                return m.group(1)
    raise CannotRun(f"{root} declares no VERSION in "
                    + " or ".join("/".join(r) for r in LAYOUTS))


def entry_point(root: Path) -> Path:
    """The launcher that starts the compiler in the tree at `root`:
    sabline.py, or velaris.py in a tree from before the 8.6 rename."""
    for name in ENTRY_POINTS:
        if (root / name).is_file():
            return root / name
    raise CannotRun(f"{root} holds none of {', '.join(ENTRY_POINTS)}")


def newest_tag_below(version: str) -> str:
    listed = git_out(["tag", "--list", "v*"], "the tags could not be listed")
    tags = [t.strip() for t in listed.splitlines()
            if re.fullmatch(r"v\d+(?:\.\d+){0,2}", t.strip())]
    older = [t for t in tags if version_tuple(t[1:]) < version_tuple(version)]
    if not older:
        raise CannotRun(f"there is no v* tag older than {version} to compare "
                        f"against (a shallow clone has no tags: fetch with "
                        f"fetch-depth 0, or pass --old REF)")
    return max(older, key=lambda t: version_tuple(t[1:]))


class Tree:
    """One version of Sabline on disk."""

    def __init__(self, label: str, root: Path, ref: Any, commit: Any, dirty: bool = False) -> None:
        self.label, self.root, self.ref = label, Path(root), ref
        self.commit, self.dirty = commit, dirty
        self.version = tree_version(self.root)

    def describe(self) -> dict[str, Any]:
        return {"label": self.label, "ref": self.ref, "commit": self.commit,
                "version": self.version, "uncommitted_changes": self.dirty}


class Checkouts:
    """Refs checked out into a scratch directory, and removed again - by
    remove(), and at exit in case remove() was never reached."""

    def __init__(self, scratch: Path) -> None:
        self.scratch = Path(scratch)
        self.worktrees: list[Any] = []
        self._lock = threading.Lock()
        atexit.register(self.remove)

    @staticmethod
    def working_tree() -> Tree:
        commit, dirty = None, False
        try:
            done = git(["rev-parse", "HEAD"])
            if done.returncode == 0:
                commit = done.stdout.decode().strip()
                st = git(["status", "--porcelain", "--untracked-files=no"])
                dirty = bool(st.stdout.strip())
        except CannotRun:
            pass
        return Tree("working tree", HERE, None, commit, dirty)

    def checkout(self, ref: str, name: str) -> Tree:
        commit = git_out(["rev-parse", "--verify", "--quiet",
                          ref + "^{commit}"],
                         f"{ref} is not a commit in this repository")
        dest = self.scratch / name
        done = git(["worktree", "add", "--detach", str(dest), commit])
        if done.returncode == 0:
            with self._lock:
                self.worktrees.append(dest)
            return Tree(ref, dest, ref, commit)
        said = done.stderr.decode("utf-8", "replace").strip()
        shutil.rmtree(dest, ignore_errors=True)
        git(["worktree", "prune"])
        archived = git(["archive", "--format=tar", commit])
        if archived.returncode != 0:
            raise CannotRun(f"{ref} could not be checked out: git worktree "
                            f"add said {said!r}; git archive said "
                            f"{tail(archived.stderr)!r}")
        dest.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(archived.stdout)) as tar:
            if hasattr(tarfile, "data_filter"):
                tar.extractall(str(dest), filter="data")
            else:
                tar.extractall(str(dest))
        say(f"note: git worktree add refused {ref} ({said}); extracted it "
            f"with git archive instead", err=True)
        return Tree(ref, dest, ref, commit)

    def remove(self) -> None:
        with self._lock:
            added, self.worktrees = self.worktrees, []
        for dest in reversed(added):
            try:
                done = git(["worktree", "remove", "--force", str(dest)])
                if done.returncode != 0:
                    shutil.rmtree(dest, ignore_errors=True)
                git(["worktree", "prune"])
            except CannotRun:
                shutil.rmtree(dest, ignore_errors=True)


# --------------------------------------------------------- normalisation

PLACE_NAMES = "root|work|spec|scratch|python|tmp|tmpdir|home"
SEP = r"(?:\\\\|\\|/)"
NAME = r"[A-Za-z0-9_.~\-]"
TMPDIR = re.compile(r"<tmp>" + SEP + r"[^\s\"'\\/<>|:*?]+")
AFTER_PLACE = re.compile(r"(<(?:" + PLACE_NAMES + r")>)((?:" + SEP
                         + r"[A-Za-z0-9_.~<>\-]+)+)")
RELATIVE_BACKSLASHED = re.compile(
    r"(?<![A-Za-z0-9_.~\-\\])" + NAME + r"+(?:(?:\\\\|\\)" + NAME
    + r"+)*(?:\\\\|\\)[A-Za-z0-9_~\-]+\.[A-Za-z0-9]+(?![A-Za-z0-9_])")
TIMING = (
    (re.compile(r"(?<![\w.])\d+(?:\.\d+)?(\s?)ms\b"), r"<n>\1ms"),
    (re.compile(r"(?<![\w.])\d+\.\d+(\s?)(seconds|second|secs|sec|s)\b"),
     r"<n>\1\2"),
    (re.compile(r'("[A-Za-z0-9_]*(?:_ms|_s|seconds)"\s*:\s*)-?\d+(?:\.\d+)?'
                r'(?:[eE][-+]?\d+)?'), r"\1<n>"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?"
                r"(?:Z|[+-]\d{2}:?\d{2})?"), "<timestamp>"),
    (re.compile(r"0x[0-9a-fA-F]{6,}"), "0x<addr>"),
)


def _to_slashes(text: str) -> str:
    return re.sub(r"\\\\|\\", "/", text)


def _path_pattern(path: str) -> str:
    parts = [p for p in re.split(r"[\\/]+", path) if p]
    body = SEP.join(re.escape(p) for p in parts)
    if path[:1] in ("/", "\\"):
        body = SEP + body
    return body + r"(?![A-Za-z0-9_~\-]|\.[A-Za-z0-9])"


class Normaliser:
    """The docstring's steps 1 to 5 for one side of the comparison."""

    def __init__(self, places: list[Any], version: Any) -> None:
        spellings: dict[Any, Any] = {}
        for path, mark in places:
            if not path:
                continue
            for p in (str(path), os.path.realpath(str(path))):
                if len(p) > 3:                  # never a bare drive or /
                    spellings.setdefault(p, mark)
        flags = re.I if os.name == "nt" else 0
        self.paths = [(re.compile(_path_pattern(p), flags), f"<{mark}>")
                      for p, mark in sorted(spellings.items(),
                                            key=lambda kv: -len(kv[0]))]
        self.version = (re.compile(r"(?<![\d.])" + re.escape(version)
                                   + r"(?!\d|\.\d)") if version else None)

    def __call__(self, text: str) -> str:
        text = text.replace("\r\n", "\n")
        for rx, mark in self.paths:
            text = rx.sub(cast("Callable[[re.Match[str]], str]",
                               lambda _m, mark=mark: mark), text)
        text = TMPDIR.sub("<tmp>/<tmpdir>", text)
        text = AFTER_PLACE.sub(lambda m: m.group(1) + _to_slashes(m.group(2)),
                               text)
        text = RELATIVE_BACKSLASHED.sub(lambda m: _to_slashes(m.group(0)),
                                        text)
        if self.version is not None:
            text = self.version.sub("<version>", text)
        for rx, repl in TIMING:
            text = rx.sub(repl, text)
        return text


# -------------------------------------------------------------- CHANGELOG

class Entry:
    """The new version's CHANGELOG entry, and what it names."""

    HEADING = re.compile(r"^##[ \t]+v?(\d+(?:\.\d+){0,2})\b.*$", re.M)
    LINE = re.compile(r"^[ \t]*(?:[-*+][ \t]+)?`?differential:[ \t]*`?"
                      r"([^\s`]+)`?[ \t]+-+[ \t]+(.+?)[ \t]*$", re.M)

    def __init__(self, changelog: Path, version: str) -> None:
        self.version, self.heading, self.text = version, None, ""
        try:
            whole = changelog.read_text(encoding="utf-8")
        except OSError:
            whole = ""
        heads = list(self.HEADING.finditer(whole))
        for i, h in enumerate(heads):
            if version_tuple(h.group(1)) == version_tuple(version):
                end = heads[i + 1].start() if i + 1 < len(heads) \
                    else len(whole)
                self.heading = h.group(0).strip()
                self.text = whole[h.start():end]
                break
        self.reasons: dict[str, str] = {}
        for m in self.LINE.finditer(self.text):
            self.reasons.setdefault(m.group(1), m.group(2))

    def names(self, in_text: list[Any], in_line: list[Any]) -> str | None:
        """How the entry names a difference, or None."""
        for key in in_line:
            if key in self.reasons:
                return f"differential: {key} - {self.reasons[key]}"
        for key in in_text:
            if re.search(r"(?<![A-Za-z0-9_./\-])" + re.escape(key)
                         + r"(?![A-Za-z0-9_/\-]|\.[A-Za-z0-9])", self.text):
                return f"named in the entry {self.heading!r}"
        return None


# ---------------------------------------------------------------- running

class Run:
    """What every corpus needs: the Python, the scratch directory, the
    places to normalise."""

    def __init__(self, args: Any, scratch: Path) -> None:
        self.python = args.python
        self.scratch = scratch
        self.jobs = max(1, args.jobs)
        self.benchmark = args.benchmark
        self.spec = None
        try:
            done = subprocess.run(
                [self.python, "-c", "import json, sys; print(json.dumps("
                 "[sys.prefix, sys.base_prefix, sys.version.split()[0]]))"],
                capture_output=True, timeout=120)
            prefix, base, self.python_version = json.loads(done.stdout)
        except (OSError, ValueError, subprocess.TimeoutExpired) as e:
            raise CannotRun(f"the Python {self.python} does not start: {e}")
        self.python_places = [(prefix, "python"), (base, "python")]

    def env(self, side: str) -> dict[Any, Any]:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        # both spellings: a tree from before the 8.6 rename reads
        # VELARIS_CACHE_DIR, and neither side may reach the user's cache
        cache = str(self.scratch / "cache" / side)
        env.update(PYTHONIOENCODING="utf-8", NO_COLOR="1",
                   SABLINE_CACHE_DIR=cache, VELARIS_CACHE_DIR=cache)
        return env

    def normaliser(self, tree: Tree, work: Any = None) -> Normaliser:
        places = [(tree.root, "root"), (work, "work"), (self.spec, "spec"),
                  (self.scratch, "scratch")] + self.python_places + [
                  (tempfile.gettempdir(), "tmp"),
                  (os.path.expanduser("~"), "home")]
        return Normaliser(places, tree.version)


TABLES = ("import json, runpy, sys\n"
          "ns = runpy.run_path(sys.argv[1], run_name='check_differential')\n"
          "print(json.dumps({k: ns.get(k) or {} for k in "
          "('EXPECT', 'ALLOW', 'ARGS', 'STDIN')}))\n")


def example_tables(tree: Tree, run: Run, side: str) -> dict[Any, Any]:
    """EXPECT, ALLOW, ARGS and STDIN as that version's run_tests.py has
    them, read in a child so its imports stay out of this process."""
    script = tree.root / "run_tests.py"
    if not script.is_file():
        raise CannotRun(f"{tree.label} has no run_tests.py")
    try:
        done = subprocess.run([run.python, "-c", TABLES, str(script)],
                              capture_output=True, cwd=str(tree.root),
                              env=run.env(side), timeout=120)
        tables: dict[str, Any] = json.loads(done.stdout.decode("utf-8"))
    except (OSError, ValueError, subprocess.TimeoutExpired) as e:
        raise CannotRun(f"run_tests.py of {tree.label} could not be read: "
                        f"{e}")
    if not tables.get("EXPECT"):
        raise CannotRun(f"run_tests.py of {tree.label} lists no examples "
                        f"({tail(done.stderr)})")
    return tables


def run_examples(tree: Tree, run: Run, side: str) -> dict[str, Any]:
    tables = example_tables(tree, run, side)
    env = run.env(side)

    def one(name: str, attempt: int = 1) -> dict[str, Any]:
        work = run.scratch / "work" / side / f"{Path(name).stem}-{attempt}"
        work.mkdir(parents=True, exist_ok=True)
        cmd = [run.python, str(entry_point(tree.root)),
               str(tree.root / "examples" / name)]
        if name in tables["ALLOW"]:
            cmd += ["--allow", tables["ALLOW"][name]]
            granted = {g.strip().split(":")[0].split("@")[0]
                       for g in tables["ALLOW"][name].split(",")}
            if granted & {"rand", "clock"} and \
                    version_tuple(tree.version) >= DETERMINISM_FLAGS:
                cmd += ["--seed", "1", "--freeze-time", FROZEN_AT]
        for arg in tables["ARGS"].get(name, []):
            # before 8.1 run_tests.py named sample.txt relative to the
            # checkout it was started in; here each program runs elsewhere
            if arg and not os.path.isabs(arg) and (tree.root / arg).exists():
                arg = str(tree.root / arg)
            cmd.append(arg)
        stdin = (tables["STDIN"].get(name) or "").encode("utf-8")
        code: int | str
        try:
            done = subprocess.run(cmd, input=stdin, capture_output=True,
                                  cwd=str(work), env=env,
                                  timeout=EXAMPLE_TIMEOUT)
            code, out, err = done.returncode, done.stdout, done.stderr
        except subprocess.TimeoutExpired as e:
            code = f"timed out after {EXAMPLE_TIMEOUT} s"
            out, err = e.stdout or b"", e.stderr or b""
        norm = run.normaliser(tree, work)
        return {"exit": code,
                "stdout": norm(out.decode("utf-8", "replace")),
                "stderr": norm(err.decode("utf-8", "replace"))}

    def many(names: list[Any], attempt: int = 1) -> dict[Any, Any]:
        with ThreadPoolExecutor(max_workers=run.jobs) as pool:
            return dict(zip(names, pool.map(lambda n: one(n, attempt),
                                            names)))

    names = list(tables["EXPECT"])
    norm = run.normaliser(tree)
    shown = {key: {n: norm(json.dumps(v)) for n, v in tables[key].items()}
             for key in ("ALLOW", "ARGS", "STDIN")}
    return {"results": many(names), "names": names, "tables": shown,
            "again": lambda keys: many(keys, 2)}


def run_conformance(tree: Tree, run: Run, side: str) -> dict[str, Any]:
    cwd = run.scratch / "conformance" / side
    cwd.mkdir(parents=True, exist_ok=True)
    cmd = [run.python, str(entry_point(tree.root)), "conformance",
           "--corpus", str(run.spec), "--json"]
    try:
        done = subprocess.run(cmd, capture_output=True, cwd=str(cwd),
                              env=run.env(side), timeout=CONFORMANCE_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise CannotRun(f"conformance under {tree.label} did not finish: {e}")
    try:
        report = json.loads(done.stdout.decode("utf-8", "replace"))
        rows = report["results"]
    except (ValueError, KeyError, TypeError):
        raise CannotRun(f"conformance under {tree.label} exited "
                        f"{done.returncode} without a report: "
                        f"{tail(done.stderr)}")
    norm = run.normaliser(tree)
    return {"results": {row["id"]: {"result": row.get("result"),
                                    "detail": norm(str(row.get("detail")
                                                       or ""))}
                        for row in rows},
            "again": None}      # the runner has no way to run one case


def run_benchmark(tree: Tree, run: Run, side: str, only: Any = None) -> dict[str, Any]:
    out_dir = run.scratch / "benchmark" / (side if only is None
                                           else side + "-again")
    out_dir.mkdir(parents=True, exist_ok=True)
    results = out_dir / "results.json"
    harness = tree.root / "benchmark" / "run.py"
    if not harness.is_file():
        raise CannotRun(f"{tree.label} has no benchmark/run.py")
    # --json and --md always point into scratch: a full run would otherwise
    # rewrite the tree's own results.json and RESULTS.md
    cmd = [run.python, str(harness), "--json", str(results),
           "--md", str(out_dir / "RESULTS.md")]
    if only:
        cmd += ["--only", ",".join(only)]
    elif run.benchmark == "quick":
        cmd.append("--quick")
    try:
        done = subprocess.run(cmd, capture_output=True, cwd=str(out_dir),
                              env=run.env(side), timeout=BENCHMARK_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise CannotRun(f"the benchmark under {tree.label} did not finish: "
                        f"{e}")
    if done.returncode != 0:
        raise CannotRun(f"the benchmark under {tree.label} exited "
                        f"{done.returncode}: {tail(done.stderr)}")
    rows = {}
    if run.benchmark == "full" and not only and results.is_file():
        data = json.loads(results.read_text(encoding="utf-8"))
        for p in data["programs"]:
            rows[p["id"]] = {"name": p["name"],
                             "verdicts": {t: v["verdict"]
                                          for t, v in p["tools"].items()}}
    else:                       # --quick writes no file: read its table
        tools = None
        for line in done.stdout.decode("utf-8", "replace").splitlines():
            parts = line.split()
            if parts[:1] == ["program"]:
                tools = parts[1:]
            elif tools and len(parts) == 2 + len(tools) \
                    and all(v in BENCH_VERDICTS for v in parts[2:]):
                rows[parts[0]] = {"name": parts[1],
                                  "verdicts": dict(zip(tools, parts[2:]))}
    if not rows:
        raise CannotRun(f"the benchmark under {tree.label} recorded no "
                        f"verdicts: {tail(done.stdout)}")
    return {"results": rows,
            "again": lambda keys: run_benchmark(tree, run, side,
                                                only=keys)["results"]}


# ------------------------------------------------------------- comparing

def short_diff(a: str, b: str, old: str, new: str) -> list[Any]:
    lines = list(difflib.unified_diff(a.splitlines(), b.splitlines(), old,
                                      new, lineterm="", n=1))
    if len(lines) > DIFF_LINES:
        lines = lines[:DIFF_LINES] + [f"... {len(lines) - DIFF_LINES} more "
                                      f"diff line(s)"]
    return lines


def clip(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= DETAIL_CHARS else text[:DETAIL_CHARS] + "..."


def compare_examples(old: Any, new: Any, labels: Any) -> list[Any]:
    old_names, old_tables, old_res = (old["names"], old["tables"],
                                      old["results"])
    new_names, new_tables, new_res = (new["names"], new["tables"],
                                      new["results"])
    found = []
    for name in new_names + [n for n in old_names if n not in new_res]:
        a, b = old_res.get(name), new_res.get(name)
        lines = []
        if a is None or b is None:
            lines.append(f"in run_tests.py of {labels[1] if a is None else labels[0]} only")
        else:
            if a["exit"] != b["exit"]:
                lines.append(f"exit: {a['exit']} -> {b['exit']}")
            for stream in ("stdout", "stderr"):
                if a[stream] != b[stream]:
                    lines.append(f"{stream}:")
                    lines += ["  " + ln for ln in short_diff(
                        a[stream], b[stream], labels[0], labels[1])]
        if not lines:
            continue
        for key in ("ALLOW", "ARGS", "STDIN"):
            was, now = old_tables[key].get(name), new_tables[key].get(name)
            if was != now:
                lines.append(f"note: run_tests.py's {key} for it changed: "
                             f"{was} -> {now}")
        path = f"examples/{name}"
        found.append({"corpus": "examples", "id": name, "key": path,
                      "lines": lines,
                      "text_keys": [path], "line_keys": [path]})
    return found


def compare_conformance(old: dict[Any, Any], new: dict[Any, Any], labels: Any) -> list[Any]:
    old, new = old["results"], new["results"]
    found = []
    for cid in list(new) + [c for c in old if c not in new]:
        a, b = old.get(cid), new.get(cid)
        if a is not None and b is not None and a["result"] == b["result"]:
            continue
        lines = [f"verdict: {a['result'] if a else 'absent'} -> "
                 f"{b['result'] if b else 'absent'}"]
        for label, side in zip(labels, (a, b)):
            if side and side["detail"]:
                lines.append(f"detail under {label}: {clip(side['detail'])}")
        found.append({"corpus": "conformance", "id": cid, "key": cid,
                      "lines": lines,
                      "text_keys": [cid], "line_keys": [cid]})
    return found


def compare_benchmark(old: dict[Any, Any], new: dict[Any, Any], labels: Any) -> list[Any]:
    old, new = old["results"], new["results"]
    found = []
    for pid in list(new) + [p for p in old if p not in new]:
        a, b = old.get(pid), new.get(pid)
        # pid is a key of new or of old, so one of the two is there
        name = cast("dict[str, Any]", b or a)["name"]
        lines = []
        if a is None or b is None:
            lines.append(f"in the benchmark of "
                         f"{labels[1] if a is None else labels[0]} only")
        else:
            for tool in list(b["verdicts"]) + [t for t in a["verdicts"]
                                               if t not in b["verdicts"]]:
                was = a["verdicts"].get(tool, "absent")
                now = b["verdicts"].get(tool, "absent")
                if was != now:
                    lines.append(f"{tool}: {was} -> {now}")
        if lines:
            found.append({"corpus": "benchmark", "id": pid,
                          "key": f"{pid} {name}",
                          "lines": lines, "text_keys": [name],
                          "line_keys": [name, pid]})
    return found


# ------------------------------------------------------------------ main

def find_spec(given: Any) -> Any:
    if given:
        return Path(given).resolve()
    for candidate in (HERE / "sabline-spec" / "tests",
                      HERE.parent / "sabline-spec" / "tests"):
        if (candidate / "index.json").is_file():
            return candidate
    return None


def compare(args: Any, corpora: list[Any], scratch: Path, checkouts: Checkouts,
            report: dict[Any, Any]) -> int:
    run = Run(args, scratch)
    if "conformance" in corpora:
        run.spec = find_spec(args.spec)
        if run.spec is None or not (run.spec / "index.json").is_file():
            raise CannotRun("sabline-spec's conformance corpus was not found: "
                            "pass --spec sabline-spec/tests, or leave "
                            "--corpus out of conformance")
    new = (checkouts.checkout(args.new, "new") if args.new
           else checkouts.working_tree())
    old_ref = args.old or newest_tag_below(new.version)
    old = checkouts.checkout(old_ref, "old")
    labels = [old.label, new.label]
    if labels[0] == labels[1]:
        labels = [labels[0] + " (old)", labels[1] + " (new)"]
    entry = Entry(new.root / "CHANGELOG.md", args.entry or new.version)
    report.update(old=old.describe(), new=new.describe(),
                  python={"path": run.python, "version": run.python_version},
                  corpora=corpora, benchmark=run.benchmark,
                  changelog_entry=entry.heading,
                  normalised=NORMALISED)
    said_new = new.label + (f" at {new.commit[:12]}" if new.commit else "") \
        + (" with uncommitted changes" if new.dirty else "")
    say(f"check_differential: {said_new} (Sabline {new.version}) against "
        f"{old.label} at {old.commit[:12]} (Sabline {old.version}), Python "
        f"{run.python_version}")
    if entry.heading is None:
        say(f"note: CHANGELOG.md of {new.label} has no entry for "
            f"{entry.version}, so no difference can be named")
    else:
        say(f"CHANGELOG entry read: {entry.heading}")
    if version_tuple(new.version) <= version_tuple(old.version):
        say(f"note: {new.label} says {new.version}, which is not newer than "
            f"{old.label}'s {old.version}; the entry read is that version's. "
            f"Bump VERSION, or pass --entry X.Y.Z")

    runners: dict[str, Callable[[Tree, Run, str], dict[str, Any]]] = {
        "examples": run_examples, "conformance": run_conformance,
        "benchmark": run_benchmark}
    comparers = {"examples": compare_examples,
                 "conformance": compare_conformance,
                 "benchmark": compare_benchmark}
    differences, unstable, counts = [], [], {}
    for corpus in corpora:
        sides = []
        for side, tree in (("old", old), ("new", new)):
            began = time.monotonic()
            say(f"  {corpus} under {tree.label} ...", err=True)
            sides.append(runners[corpus](tree, run, side))
            say(f"  {corpus} under {tree.label}: "
                f"{time.monotonic() - began:.0f} s", err=True)
        compare_them = comparers[corpus]
        found = compare_them(sides[0], sides[1], labels)
        # each program that differs runs once more under both versions; one
        # whose two runs under one version differ is unstable, not compared
        shaky: dict[Any, Any] = {}
        again = [d["id"] for d in found if d["id"] in sides[0]["results"]
                 and d["id"] in sides[1]["results"]]
        if again and all(s["again"] for s in sides):
            say(f"  {corpus}: running the {len(again)} that differ again "
                f"under both versions ...", err=True)
            for label, s in zip(labels, sides):
                second = s["again"](again)
                for key in again:
                    if key in shaky or key not in second:
                        continue
                    own = compare_them(
                        dict(s, results={key: s["results"][key]},
                             names=[key]),
                        dict(s, results={key: second[key]}, names=[key]),
                        [f"{label}, run 1", f"{label}, run 2"])
                    if own:
                        shaky[key] = own[0]
        unstable += [shaky[d["id"]] for d in found if d["id"] in shaky]
        found = [d for d in found if d["id"] not in shaky]
        compared = len(set(sides[0]["results"]) | set(sides[1]["results"]))
        counts[corpus] = {"compared": compared, "different": len(found),
                          "unstable": len(shaky)}
        differences += found

    say("")
    for d in unstable:
        d.pop("text_keys", None)
        d.pop("line_keys", None)
        say(f"UNSTABLE {d['corpus']}: {d['key']}  [not compared: two runs "
            f"under one version differ]")
        for line in d["lines"]:
            say("    " + line)
    for d in differences:
        how = entry.names(d.pop("text_keys"), d.pop("line_keys"))
        d["named"], d["named_by"] = how is not None, how
        say(f"DIFF {d['corpus']}: {d['key']}  ["
            + (how if how else "NOT named in the CHANGELOG") + "]")
        for line in d["lines"]:
            say("    " + line)
    unnamed = [d for d in differences if not d["named"]]
    say("")
    for corpus in corpora:
        mine = [d for d in differences if d["corpus"] == corpus]
        counts[corpus]["named"] = sum(d["named"] for d in mine)
        say(f"{corpus}: {counts[corpus]['compared']} compared, "
            f"{len(mine)} differ, {counts[corpus]['named']} of them named"
            + (f"; {counts[corpus]['unstable']} unstable, not compared"
               if counts[corpus]["unstable"] else ""))
    report.update(counts=counts, differences=differences, unstable=unstable,
                  unnamed=[f"{d['corpus']}: {d['key']}" for d in unnamed])
    if unstable:
        say(f"note: {len(unstable)} program(s) gave two different results "
            f"under one version, so they could not be compared: "
            + ", ".join(d["key"] for d in unstable))
    if unnamed:
        say(f"FAIL: {len(unnamed)} difference(s) the CHANGELOG entry does not "
            f"name. Name each in the {entry.version} entry, or add a line "
            f"'differential: <path or id> - <why>'.")
        return 1
    say("ok: every difference is named in the CHANGELOG" if differences
        else "ok: no differences")
    return 0


NORMALISED = [
    "CRLF line ends become LF",
    "absolute paths: the tree -> <root>, the program's run directory -> "
    "<work>, the conformance corpus -> <spec>, the scratch directory -> "
    "<scratch>, the Python installation -> <python>, the temporary "
    "directory -> <tmp> (a directory directly under it -> <tmpdir>), the "
    "home directory -> <home>; any separator spelling, case-insensitive on "
    "Windows",
    "separators: the rest of a path after a placeholder, and a relative "
    "backslashed path ending in name.ext, written with /",
    "the side's own VERSION string -> <version>",
    "timing: N ms, N.N s/sec/secs/second/seconds, JSON *_ms/*_s/*seconds "
    "values, ISO 8601 timestamps, 0x addresses of 6+ hex digits",
]


def main(argv: Any = None) -> int:
    ap = argparse.ArgumentParser(
        description="Run the examples, the conformance corpus and the "
                    "benchmark under two versions of Sabline; every "
                    "difference must be named in the CHANGELOG.")
    ap.add_argument("--new", metavar="REF",
                    help="the new version (default: the working tree)")
    ap.add_argument("--old", metavar="REF",
                    help="the old version (default: the newest v* tag older "
                         "than the new version)")
    ap.add_argument("--corpus", default=",".join(CORPORA),
                    help="which to run, comma-separated: "
                         + ",".join(CORPORA) + " (default: all)")
    ap.add_argument("--benchmark", choices=("quick", "full"), default="quick",
                    help="quick: one program per category (CI); full: every "
                         "program (the monthly job)")
    ap.add_argument("--spec", metavar="DIR",
                    help="sabline-spec's tests/ directory")
    ap.add_argument("--entry", metavar="X.Y.Z",
                    help="the CHANGELOG entry to read (default: the new "
                         "version's)")
    ap.add_argument("--python", default=sys.executable,
                    help="the Python both versions run under")
    ap.add_argument("--jobs", type=int, default=2,
                    help="examples run at once per version (default 2)")
    ap.add_argument("--json", metavar="FILE", help="write the report here")
    args = ap.parse_args(argv)
    corpora = [c.strip() for c in args.corpus.split(",") if c.strip()]
    unknown = [c for c in corpora if c not in CORPORA]
    if unknown or not corpora:
        ap.error(f"--corpus takes {', '.join(CORPORA)}; not {unknown or '(nothing)'}")

    scratch = isolate("check_differential")
    checkouts = Checkouts(scratch)
    report: dict[Any, Any] = {"schema": "sabline.differential/1"}
    try:
        code = compare(args, corpora, scratch, checkouts, report)
    except CannotRun as e:
        say(f"check_differential: could not run: {e}", err=True)
        report["error"] = str(e)
        code = 2
    finally:
        checkouts.remove()
    report["exit"] = code
    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(report, fh, indent=1)
            fh.write("\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
