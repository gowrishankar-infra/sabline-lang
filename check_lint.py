#!/usr/bin/env python3
"""mypy --strict and ruff over every Python file here, and the compiler's
most complex functions.

    python check_lint.py                 lint, then the complexity table
    python check_lint.py --complexity    the complexity table only

The files are every .py file git knows of - tracked, or new and not
ignored (`git ls-files --cached --others --exclude-standard`) - except a
checkout of sabline-spec/ and what a build writes. Without git the same
files are found by walking the tree.

mypy runs as `python -m mypy --strict` with pyproject.toml's [tool.mypy]
(strict, Python 3.10), and ruff as `python -m ruff check` with its
[tool.ruff] (Python 3.10, ruff's default rules), over the same files. The
exit status is 1 if either reports anything, and 0 if neither does.

mypy knows a file by its module name, so two files with one name cannot
be checked in one run: the files are split into as few runs as keep each
name once (the benchmark's dependencies come in two versions, a
pricing.py in each). sabline.py, the launcher, has the name of the
package it starts, and is checked as program text (`mypy -c`), where its
imports reach the package; what mypy finds there is shown against
sabline.py.

Complexity
----------
The table ranks the 20 functions in sabline/ with the highest cyclomatic
complexity, counted from the syntax tree as 1 plus one for each decision
point in the function's body:

  - an `if` or an `elif`
  - a `for` or `async for` loop, and a `while` loop
  - an `except` clause
  - an item of a `with` or `async with` (its exit may swallow an
    exception, so control can leave the block two ways)
  - each operand of a boolean operator after the first (`a and b or c`
    is two)
  - an `if` clause of a comprehension
  - a `case` of a `match`
  - a conditional expression (`x if c else y`)

Every def is a function of its own, methods and nested defs alike, named
Class.method and outer.inner; what is inside a nested def or class counts
for it and not for the def around it. A lambda counts for the def it is
written in. Module-level code is in no function. Equal counts are listed
in file and line order. The table never changes the exit status.
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PYPROJECT = HERE / "pyproject.toml"
TOP = 20

# directories that are not this repository's source: a checkout of the
# spec beside it, and what builds and tools write
SKIP_DIRS = frozenset({"sabline-spec", "_mcpb_build", "build", "dist",
                       "node_modules", "__pycache__"})

FINDING = re.compile(r"^.+?:\d+(?::\d+)?: (?:error|warning):")
RUFF_FINDING = re.compile(r"^.+?:\d+:\d+: ")


def say(text: str = "") -> None:
    """Print ASCII only: a CI console may not take anything else."""
    print(text.encode("ascii", "backslashreplace").decode("ascii"))


# ---- the files ---------------------------------------------------------------

def _git_files() -> list[str] | None:
    try:
        done = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard",
             "-z", "--", "*.py"],
            cwd=HERE, capture_output=True, text=True, encoding="utf-8",
            check=False)
    except OSError:
        return None
    if done.returncode != 0:
        return None
    return [name for name in done.stdout.split("\0") if name]


def _walked_files() -> list[str]:
    found = []
    for root, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs
                   if d not in SKIP_DIRS and not d.startswith((".", "_"))
                   and not d.endswith(".egg-info")]
        for name in files:
            if name.endswith(".py"):
                found.append(
                    (Path(root) / name).relative_to(HERE).as_posix())
    return found


def lint_files() -> list[str]:
    """Every file in scope, as a path relative to here with / between."""
    names = _git_files()
    if names is None:
        names = _walked_files()
    out = set()
    for name in names:
        name = name.replace("\\", "/")
        parts = name.split("/")
        if any(part in SKIP_DIRS for part in parts[:-1]):
            continue
        if (HERE / name).is_file():
            out.add(name)
    return sorted(out)


# ---- mypy ----------------------------------------------------------------------

def module_name(name: str) -> str:
    """The module name mypy gives a file: its stem, under every directory
    above it that holds an __init__.py."""
    path = HERE / name
    parts = [] if path.stem == "__init__" else [path.stem]
    folder = path.parent
    while folder != HERE.parent and (folder / "__init__.py").is_file():
        parts.insert(0, folder.name)
        folder = folder.parent
    return ".".join(parts)


def mypy_runs(files: list[str]) -> tuple[list[list[str]], list[str]]:
    """(runs of files in which no module name appears twice, files that
    have a package's name and are checked as program text)."""
    packages = {module_name(f) for f in files if f.endswith("__init__.py")}
    runs: list[list[str]] = []
    names: list[set[str]] = []
    texts: list[str] = []
    for f in files:
        module = module_name(f)
        if not f.endswith("__init__.py") and module in packages:
            texts.append(f)
            continue
        for run, seen in zip(runs, names):
            if module not in seen:
                run.append(f)
                seen.add(module)
                break
        else:
            runs.append([f])
            names.append({module})
    return runs, texts


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONIOENCODING="utf-8", NO_COLOR="1")
    return subprocess.run(command, cwd=HERE, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env,
                          check=False)


def run_mypy(files: list[str]) -> tuple[list[str], bool]:
    """(what mypy found, one line each with its notes, whether mypy itself
    failed to run)."""
    runs, texts = mypy_runs(files)
    base = [sys.executable, "-m", "mypy", "--strict",
            "--config-file", str(PYPROJECT), "--no-color-output",
            "--no-error-summary"]
    lines: list[str] = []
    broke = False
    jobs: list[tuple[list[str], str | None]] = [(base + run, None)
                                                 for run in runs]
    for name in texts:
        text = (HERE / name).read_text(encoding="utf-8")
        jobs.append((base + ["-c", text], name))
    for command, as_file in jobs:
        done = _run(command)
        if done.returncode not in (0, 1):
            broke = True
            lines.append(f"mypy stopped ({done.returncode}): "
                         f"{(done.stderr or done.stdout).strip()[-800:]}")
            continue
        keep = False
        for line in done.stdout.splitlines():
            if as_file is not None:
                # only what is in the text; its imports are in the runs
                if not line.startswith("<string>:"):
                    continue
                line = as_file + line[len("<string>"):]
            if FINDING.match(line):
                keep = True
                lines.append(line)
            elif keep and re.match(r"^.+?:\d+(?::\d+)?: note:", line):
                lines.append(line)
            elif line.strip() and not line.startswith("Success:"):
                keep = False
                lines.append(line)
        for line in done.stderr.splitlines():
            if line.strip():
                lines.append(line)
    return lines, broke


# ---- ruff ----------------------------------------------------------------------

def run_ruff(files: list[str]) -> tuple[list[str], bool]:
    """(what ruff found, one line each, whether ruff failed to run)."""
    done = _run([sys.executable, "-m", "ruff", "check", "--no-fix",
                 "--output-format", "concise", *files])
    lines = [line for line in done.stdout.splitlines()
             if RUFF_FINDING.match(line)]
    lines += [line for line in done.stderr.splitlines() if line.strip()]
    broke = done.returncode not in (0, 1)
    if done.returncode == 1 and not lines:
        lines.append(done.stdout.strip()[-800:])
    return lines, broke


# ---- complexity ----------------------------------------------------------------

def decisions(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """The decision points in a function's body, as the docstring counts
    them."""
    count = 0
    stack: list[ast.AST] = list(function.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            continue
        if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While,
                             ast.ExceptHandler, ast.IfExp, ast.match_case)):
            count += 1
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            count += len(node.items)
        elif isinstance(node, ast.BoolOp):
            count += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            count += len(node.ifs)
        stack.extend(ast.iter_child_nodes(node))
    return count


class _Functions(ast.NodeVisitor):
    """Every def in a module: (complexity, qualified name, line)."""

    def __init__(self) -> None:
        self.scope: list[str] = []
        self.found: list[tuple[int, str, int]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        name = ".".join([*self.scope, node.name])
        self.found.append((1 + decisions(node), name, node.lineno))
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._function(node)


def most_complex(top: int = TOP) -> list[tuple[int, str, str, int]]:
    """The `top` most complex functions in sabline/: (complexity, name,
    module path, line)."""
    rows: list[tuple[int, str, str, int]] = []
    for path in sorted((HERE / "sabline").glob("*.py")):
        where = path.relative_to(HERE).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=where)
        functions = _Functions()
        functions.visit(tree)
        rows += [(c, name, where, line) for c, name, line in functions.found]
    rows.sort(key=lambda row: (-row[0], row[2], row[3]))
    return rows[:top]


def complexity_table(top: int = TOP) -> str:
    lines = ["| rank | function | module:line | cyclomatic complexity |",
             "|---:|---|---|---:|"]
    for rank, (count, name, where, line) in enumerate(most_complex(top), 1):
        lines.append(f"| {rank} | `{name}` | {where}:{line} | {count} |")
    return "\n".join(lines)


# ---- the run -------------------------------------------------------------------

def main(argv: list[str]) -> int:
    if "--complexity" in argv:
        say(complexity_table())
        return 0
    files = lint_files()
    runs, texts = mypy_runs(files)
    say(f"mypy --strict over {len(files)} file(s), in {len(runs)} run(s) "
        f"and {len(texts)} as program text")
    mypy_lines, mypy_broke = run_mypy(files)
    for line in mypy_lines:
        say(f"  {line}")
    mypy_count = sum(1 for line in mypy_lines if FINDING.match(line))
    say(f"mypy: {mypy_count} finding(s)")
    say()
    say(f"ruff check over the same {len(files)} file(s)")
    ruff_lines, ruff_broke = run_ruff(files)
    for line in ruff_lines:
        say(f"  {line}")
    say(f"ruff: {len(ruff_lines)} finding(s)")
    say()
    say(f"The {TOP} most complex functions in sabline/")
    say()
    say(complexity_table())
    failed = (bool(mypy_lines) or bool(ruff_lines) or mypy_broke
              or ruff_broke)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
