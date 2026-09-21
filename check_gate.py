"""The agreement gate's own test: that it cannot be turned off, and that
it goes red.

    python check_gate.py [corpus path]

plan/9.0.md asks for three things about `check_agreement.py`, and the
third is the one that matters:

1. **It reads nothing that could disable it.** This script reads the
   gate's syntax tree and fails on `os.environ`, `getenv`, a configuration
   file, or any use of `sys.argv` beyond handing the corpus paths to
   `main`. The same scan covers `agreement_edges.py`, which is part of the
   corpus rather than of the comparison.

2. **The workflow cannot skip it.** `check_workflows.py` holds that: the
   `agreement` job is in test.yml, has no `if:` and no `continue-on-error`,
   runs on push and on pull_request, and is in the release gate's required
   set. It lives there because that is where the rules about workflows are.

3. **It is proven to detect, not merely to run.** This script builds
   sabline-rt with one deliberate difference injected - a single error
   code changed, a single message changed, one field of the tree dropped -
   and asserts the gate goes red for each, one injection per comparison
   class. A gate that has never been shown to fail is a gate nobody has
   tested. `check_mutant_kills.py`'s idea, applied to the gate itself.

And a fourth, from the same section: every environment variable Sabline
reads is set to a plausible disabling value and the number of compared
programs must not change.

Each injection is built in a throwaway copy of this repository, because
the gate finds sabline-rt by looking in its own `rt/target` and takes no
argument that would point it elsewhere. That is the property being
tested, so the test works around it rather than weakening it.
"""
import ast
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
GATE = ROOT / "check_agreement.py"
EDGES = ROOT / "agreement_edges.py"

# What a copy needs to run the gate: the corpora it reads, the suites it
# imports the tables of, the package it runs, and the crate it builds.
NEEDED = ("examples", "stdlib", "benchmark/corpus", "tests/error_messages",
          "sabline", "rt/crates", "rt/Cargo.toml", "rt/rustfmt.toml",
          "rt/deny.toml", "sabline.py", "check_agreement.py",
          "agreement_edges.py", "check_prover_lies.py", "check_sandbox.py",
          "check_refusals.py", "suite_dirs.py")

# Names that would let something outside the gate change what it compares.
FORBIDDEN_ATTRIBUTES = {"environ", "getenv", "putenv", "environb"}
FORBIDDEN_CALLS = {"getenv", "load_dotenv"}
# The one use of the command line the gate is allowed: the corpus paths.
ALLOWED_ARGV = "sys.argv[1:]"

# What plan/9.0.md says to set, to see whether any of it is read.
DISABLING = {
    "SABLINE_REFERENCE_RUNTIME": "python",
    "SKIP_AGREEMENT": "1",
    "SABLINE_NO_AGREEMENT": "1",
    "SABLINE_AGREEMENT": "0",
    "CI": "",
    "SABLINE_FAULT_INJECT": "1",
    "VELARIS_REFERENCE_RUNTIME": "python",
    "NO_COLOR": "1",
}

# One injection per class of thing the gate compares: the error code, the
# error message, and the tree. Each is a replacement in one file of the
# crate, and each must make the gate red.
INJECTIONS: tuple[tuple[str, str, str, str], ...] = (
    (
        "an error code",
        "rt/crates/sabline-rt/src/parser.rs",
        '''        Err(SablineError::with_fixes(
            "E101",''',
        '''        Err(SablineError::with_fixes(
            "E102",''',
    ),
    (
        "an error message",
        "rt/crates/sabline-rt/src/parser.rs",
        'format!("expected \'{want}\' but found \'{found}\'"),',
        'format!("expected \'{want}\' but got \'{found}\'"),',
    ),
    (
        "a field of the tree",
        "rt/crates/sabline-rt/src/dump.rs",
        '        ("type_vars", texts(&f.type_vars)),\n',
        "",
    ),
)


# ---- 1. the gate reads nothing that could disable it ------------------------

def _uses(tree: Any) -> list[str]:
    """Every way `tree` could read something outside its arguments."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRIBUTES:
            found.append(f"line {node.lineno}: reads {node.attr}")
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_ATTRIBUTES:
            found.append(f"line {node.lineno}: reads {node.id}")
        if isinstance(node, ast.Call):
            name = getattr(node.func, "attr", getattr(node.func, "id", ""))
            if name in FORBIDDEN_CALLS:
                found.append(f"line {node.lineno}: calls {name}()")
        if (isinstance(node, ast.Attribute) and node.attr == "argv"
                and ast.unparse(node) != "sys.argv"):
            found.append(f"line {node.lineno}: reads {ast.unparse(node)}")
    return found


def reads_nothing_that_disables_it() -> list[str]:
    problems = []
    for path in (GATE, EDGES):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for told in _uses(tree):
            problems.append(f"{path.name} {told}")
        argvs = [ast.unparse(n) for n in ast.walk(tree)
                 if isinstance(n, ast.Subscript)
                 and ast.unparse(n).startswith("sys.argv")]
        for used in argvs:
            if used != ALLOWED_ARGV:
                problems.append(f"{path.name}: reads {used}, and the only "
                                f"use of the command line it may make is "
                                f"{ALLOWED_ARGV}")
    return problems


# ---- running the gate -------------------------------------------------------

def _gate(root: Path, corpus: str, env: Any = None) -> tuple[int, str]:
    where = dict(os.environ)
    if env:
        where.update(env)
    done = subprocess.run([sys.executable, str(root / "check_agreement.py"), corpus],
                          capture_output=True, text=True, env=where, cwd=str(root))
    return done.returncode, done.stdout + done.stderr


def _compared(output: str) -> int:
    for line in output.splitlines():
        if line.startswith("agreement gate: "):
            return int(line.split()[2])
    return -1


def _differences(output: str) -> int:
    """How many the gate found, from its own count rather than from the
    lines it printed - it prints at most forty."""
    for line in output.splitlines():
        if line.startswith("agreement gate: "):
            return int(line.split()[-2])
    return -1


# ---- 3. the gate goes red ---------------------------------------------------

def _copy(into: Path) -> None:
    for name in NEEDED:
        source, target = ROOT / name, into / name
        if not source.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target,
                            ignore=shutil.ignore_patterns("__pycache__", "target"))
        else:
            shutil.copy2(source, target)


def _build(root: Path) -> None:
    done = subprocess.run(
        ["cargo", "build", "--release", "--manifest-path", str(root / "rt" / "Cargo.toml")],
        capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit(f"check_gate.py: the copy would not build:\n"
                         f"{done.stderr[-3000:]}")


def detects(corpus: str) -> list[str]:
    """Every injection the gate did not notice, and whether it is green
    without one."""
    problems = []
    with tempfile.TemporaryDirectory(prefix="sabline-gate-") as tmp:
        here = Path(tmp) / "repo"
        here.mkdir(parents=True)
        _copy(here)
        originals = {path: (here / path).read_text(encoding="utf-8")
                     for _, path, _, _ in INJECTIONS}

        _build(here)
        code, output = _gate(here, corpus)
        if code != 0:
            problems.append(
                "the copy with nothing injected is already red, so an "
                "injection going red would say nothing:\n"
                + "\n".join(output.splitlines()[-12:]))
            return problems
        clean = _compared(output)
        print(f"  a copy with nothing injected: green, {clean} programs")

        for what, path, before, after in INJECTIONS:
            file = here / path
            source = originals[path]
            if before not in source:
                problems.append(
                    f"{what}: the text this injection replaces is not in "
                    f"{path} any more, so the injection was not made")
                continue
            file.write_text(source.replace(before, after, 1),
                            encoding="utf-8", newline="\n")
            _build(here)
            code, output = _gate(here, corpus)
            file.write_text(source, encoding="utf-8", newline="\n")
            compared = _compared(output)
            if code == 0:
                problems.append(f"{what}: injected into {path}, and the gate "
                                f"stayed green over {compared} programs")
            elif compared != clean:
                problems.append(f"{what}: the gate went red, but over "
                                f"{compared} programs where it compared "
                                f"{clean} - it stopped early rather than "
                                f"finding a difference")
            else:
                print(f"  {what}: the gate goes red over "
                      f"{_differences(output)} of {compared} programs")
        _build(here)
    return problems


# ---- 4. nothing in the environment changes what it compares -----------------

def environment_changes_nothing(corpus: str) -> list[str]:
    code, output = _gate(ROOT, corpus)
    if code != 0:
        return ["the gate is red before anything was set, so this says "
                "nothing"]
    plain = _compared(output)
    code, output = _gate(ROOT, corpus, DISABLING)
    with_env = _compared(output)
    named = ", ".join(f"{k}={v!r}" for k, v in DISABLING.items())
    if with_env != plain:
        return [f"with {named} the gate compared {with_env} programs where "
                f"it compared {plain}"]
    if code != 0:
        return [f"with {named} the gate went red over the same {plain} "
                f"programs, which means it read one of them"]
    print(f"  with {len(DISABLING)} disabling variables set: still "
          f"{with_env} programs, still green")
    return []


def main(argv: list[str]) -> int:
    # absolute, because the injections run the gate from a copy of this
    # repository in a directory of its own
    corpus = str(Path(argv[0]).resolve()) if argv else ""
    if not corpus:
        for guess in ("sabline-spec/tests", "../sabline-spec/tests"):
            if (ROOT / guess).is_dir():
                corpus = str((ROOT / guess).resolve())
                break
    if not corpus:
        raise SystemExit("check_gate.py: give sabline-spec's corpus path")
    if shutil.which("cargo") is None:
        raise SystemExit("check_gate.py: cargo is needed to build the "
                         "injections (https://rustup.rs)")

    problems: list[str] = []
    print("the gate reads nothing that could disable it")
    told = reads_nothing_that_disables_it()
    problems += told
    if not told:
        print(f"  {GATE.name} and {EDGES.name}: no environment, no "
              f"configuration, one use of the command line")

    print("nothing in the environment changes what it compares")
    problems += environment_changes_nothing(corpus)

    print("the gate goes red for one injection per comparison class")
    problems += detects(corpus)

    if problems:
        print()
        for line in problems:
            print(f"FAILED {line}")
        return 1
    print("\nthe gate cannot be turned off, and it detects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
