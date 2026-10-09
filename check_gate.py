"""The agreement gate's own test: that it cannot be turned off, and that
it goes red.

    python check_gate.py [corpus path]

plan/9.0.md asks for three things about `check_agreement.py`, and the
third is the one that matters:

1. **It reads nothing that could disable it.** This script reads the
   gate's syntax tree and fails on `os.environ`, `getenv`, a configuration
   file, or any use of `sys.argv` beyond handing the corpus paths to
   `main`. The same scan covers `agreement_edges.py`,
   `agreement_checks.py` and `agreement_budgets.py`, which are part of the
   corpus rather than of the comparison.

2. **The workflow cannot skip it.** `check_workflows.py` holds that: the
   `agreement` job is in test.yml, has no `if:` and no `continue-on-error`,
   runs on push and on pull_request, and is in the release gate's required
   set. It lives there because that is where the rules about workflows are.

3. **It is proven to detect, not merely to run.** This script builds
   sabline-rt with one deliberate difference injected - a single error
   code changed, a single message changed, one field of the tree dropped,
   and from M2 a checker's code, a checker's message, a loop's verdict, a
   row of the builtin tables, one shape of the input-bounded loop
   verdict, a budget refusal's message and a budget's count, and from M3
   a value a run prints, a run's error code and message, where the
   step limit stops a run, where the size limit stops one and what it
   counts of a text - and asserts the gate goes red for each,
   one injection per comparison class. A gate that has never been shown
   to fail is a gate nobody has tested. `check_mutant_kills.py`'s idea,
   applied to the gate itself.

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
CHECKS = ROOT / "agreement_checks.py"
BUDGETS = ROOT / "agreement_budgets.py"
RUNS = ROOT / "agreement_runs.py"

# What a copy needs to run the gate: the corpora it reads, the suites it
# imports the tables of, the package it runs, and the crate it builds.
NEEDED = ("examples", "stdlib", "benchmark/corpus", "tests/error_messages",
          "sabline", "rt/crates", "rt/Cargo.toml", "rt/rustfmt.toml",
          "rt/deny.toml", "sabline.py", "check_agreement.py",
          "agreement_edges.py", "agreement_checks.py", "agreement_budgets.py",
          "agreement_runs.py",
          "check_prover_lies.py",
          "check_sandbox.py", "check_refusals.py", "check_termination.py",
          "suite_dirs.py",
          "suite_runtime.py", "LICENSE")

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

# One injection per class of thing the gate compares: the parser's error
# code, its message and the tree (M1); the checkers' codes, their messages,
# a loop's verdict and the tables they read (M2). Each is a replacement in
# one file of the crate, and each must make the gate red.
INJECTIONS: tuple[tuple[str, str, str, str], ...] = (
    (
        "an error code",
        "rt/crates/sabline-rt/src/parser.rs",
        '''SablineError::with_fixes("E101", format!("unexpected '{}'", t.text), t.line, &fixes)''',
        '''SablineError::with_fixes("E102", format!("unexpected '{}'", t.text), t.line, &fixes)''',
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
    # The checkers (9.0, M2): a code the type checker gives, a message the
    # effect checker gives, a loop's verdict, and a row of the builtin
    # tables both checkers read.
    (
        "a type checker's error code",
        "rt/crates/sabline-rt/src/checker.rs",
        '"E520",\n                format!("\'{said}\' can fail - that cannot be ignored"),',
        '"E521",\n                format!("\'{said}\' can fail - that cannot be ignored"),',
    ),
    (
        "an effect checker's message",
        "rt/crates/sabline-rt/src/effects.rs",
        "which needs effect '{eff}'",
        "which needs the effect '{eff}'",
    ),
    (
        "a loop's termination verdict",
        "rt/crates/sabline-rt/src/termination.rs",
        "moves one step toward '{}' every turn",
        "moves a step toward '{}' every turn",
    ),
    (
        "a row of the builtin tables",
        "rt/crates/sabline-rt/src/tables.rs",
        'b("to_float", NONE, &["Int"], "Float"),',
        'b("to_float", NONE, &["Float"], "Float"),',
    ),
    # The budget parser (9.0, M2): a refusal's text, and the rule that the
    # smallest count written is the one that holds.
    # The third loop verdict (9.0): one of its two flag shapes, the clear in
    # the else arm of a not-empty test, taken away from sabline-rt.
    (
        "the input-bounded verdict's else arm",
        "rt/crates/sabline-rt/src/termination.rs",
        "Some(false) => other,",
        "Some(false) => &[],",
    ),
    (
        "a budget refusal's message",
        "rt/crates/sabline-rt/src/budget.rs",
        "no wildcard over an IP literal",
        "no wildcard over an IP address",
    ),
    (
        "a budget's count",
        "rt/crates/sabline-rt/src/budget.rs",
        "Some(cur) if cur <= &n => cur.clone(),",
        "Some(cur) if cur >= &n => cur.clone(),",
    ),
    # The interpreter (9.0, M3): what a run prints, the code a run stops
    # with, the message it stops with, and where the step limit stops a
    # program that does not end.
    (
        "a value a run prints",
        "rt/crates/sabline-rt/src/value.rs",
        'Value::Bool(b) => out.push_str(if *b { "true" } else { "false" }),',
        'Value::Bool(b) => out.push_str(if *b { "True" } else { "false" }),',
    ),
    (
        "a run's error code",
        "rt/crates/sabline-rt/src/interp.rs",
        '"E403",\n                    "division by zero",',
        '"E404",\n                    "division by zero",',
    ),
    (
        "a run's error message",
        "rt/crates/sabline-rt/src/interp.rs",
        '"broken promise: {} requires {}  (",',
        '"broken promise: {} requires {} (",',
    ),
    (
        "where the step limit stops a run",
        "rt/crates/sabline-rt/src/interp.rs",
        "Some(limit) if self.ticks > limit => Err(Stop::Steps(line)),",
        "Some(limit) if self.ticks >= limit => Err(Stop::Steps(line)),",
    ),
    # The size limit (9.0, M3): where it stops a run - at the operation that
    # takes what was made past it, not the one that reaches it - and what it
    # counts of a text, which is UTF-8's bytes and not its characters.
    (
        "where the size limit stops a run",
        "rt/crates/sabline-rt/src/interp.rs",
        "Some(limit) if self.size_made > limit => Err(Stop::Size(line)),",
        "Some(limit) if self.size_made >= limit => Err(Stop::Size(line)),",
    ),
    (
        "what the size limit counts of a text",
        "rt/crates/sabline-rt/src/interp.rs",
        "0x80..=0x7FF => 2,",
        "0x80..=0x7FF => 1,",
    ),
    # The runs under their own budgets (9.0, M3): a file grant's refusal,
    # and randomness under a seed, which is CPython's Mersenne Twister.
    (
        "a file grant's refusal",
        "rt/crates/sabline-rt/src/interp.rs",
        'reaches("which this run\'s fs grants do not cover")',
        'reaches("which the fs grants of this run do not cover")',
    ),
    (
        "randomness under a seed",
        "rt/crates/sabline-rt/src/host.rs",
        "1_812_433_253u32",
        "1_812_433_255u32",
    ),
    # The third checkpoint (9.0, M3): the file a library's broken promise
    # names, and the receipt - one field dropped, which is plan/9.0.md's own
    # example; a field beside the normalised ones, so that the
    # normalisation is shown to take exactly what it names; and how many
    # keys one place may name before the receipt says "many".
    (
        "the file a broken promise names",
        "rt/crates/sabline-rt/src/interp.rs",
        'src,\n                    error(\n                        "E600",',
        '"",\n                    error(\n                        "E600",',
    ),
    (
        "a receipt's field dropped",
        "rt/crates/sabline-rt/src/receipt.rs",
        '                ("complete", Json::Bool(true)),\n',
        "",
    ),
    (
        "a receipt's field beside the normalised ones",
        "rt/crates/sabline-rt/src/receipt.rs",
        '("uri", Json::text(REPOSITORY)),',
        '("uri", Json::text("https://example.invalid/sabline-rt")),',
    ),
    (
        "how many keys a receipt names at one place",
        "rt/crates/sabline-rt/src/receipt.rs",
        "seen.len() >= FINGERPRINTS_PER_SITE",
        "seen.len() > FINGERPRINTS_PER_SITE",
    ),
    # The audit stream (decisions/0007, 32b): one event dropped - a grant's,
    # which every receipt still counts, so only the stream's row can see it.
    (
        "an audit stream's event dropped",
        "rt/crates/sabline-rt/src/interp.rs",
        "self.recorder.grant(&grant); // the audit stream (9.0)",
        "// the audit stream (9.0)",
    ),
)

# plan/9.0.md's list of what the gate normalises in a receipt, and nothing
# else is: check_agreement.py's RECEIPT_NORMALISED and CONFINEMENT_FIELDS
# must name exactly the fields the plan's section names, so that a field
# cannot join the gate's list without joining the plan's.
PLAN = ROOT / "plan" / "9.0.md"
NORMALISED_SECTION = ("### What is normalised, and nothing else is",
                      "### That it cannot be turned off")
# what the section quotes that is not a field: the two producers' names,
# and the name a program given as text has
NOT_FIELDS = {"sabline-lang", "sabline-rt", "<source>"}


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
    for path in (GATE, EDGES, CHECKS, BUDGETS, RUNS):
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


def normalises_only_the_plans_list() -> list[str]:
    """That the gate's receipt normalisation names exactly the fields
    plan/9.0.md's section does."""
    import re
    plan = PLAN.read_text(encoding="utf-8")
    start, end = (plan.find(heading) for heading in NORMALISED_SECTION)
    if start < 0 or end < start:
        return [f"plan/9.0.md has no section '{NORMALISED_SECTION[0]}'"]
    planned = set(re.findall(r"`([^`]+)`", plan[start:end])) - NOT_FIELDS
    tree = ast.parse(GATE.read_text(encoding="utf-8"))
    said: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and \
                isinstance(node.targets[0], ast.Name) and \
                node.targets[0].id in ("RECEIPT_NORMALISED", "CONFINEMENT_FIELDS"):
            said[node.targets[0].id] = ast.literal_eval(node.value)
    if len(said) != 2:
        return ["check_agreement.py has no RECEIPT_NORMALISED or no "
                "CONFINEMENT_FIELDS"]
    gate = {entry.split(",")[0].removeprefix("predicate.")
            for entry in said["RECEIPT_NORMALISED"]} | set(said["CONFINEMENT_FIELDS"])
    if gate != planned:
        return [f"the gate normalises {sorted(gate)} and plan/9.0.md names "
                f"{sorted(planned)}"]
    print(f"  the gate's receipt normalisation is plan/9.0.md's list: "
          f"{len(gate)} fields")
    return []


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
        print(f"  a copy with nothing injected: green, {clean} comparisons")

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
                                f"stayed green over {compared} comparisons")
            elif compared != clean:
                problems.append(f"{what}: the gate went red, but over "
                                f"{compared} comparisons where it made "
                                f"{clean} - it stopped early rather than "
                                f"finding a difference")
            else:
                print(f"  {what}: the gate goes red over "
                      f"{_differences(output)} of {compared} comparisons")
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
        return [f"with {named} the gate made {with_env} comparisons where "
                f"it made {plain}"]
    if code != 0:
        return [f"with {named} the gate went red over the same {plain} "
                f"comparisons, which means it read one of them"]
    print(f"  with {len(DISABLING)} disabling variables set: still "
          f"{with_env} comparisons, still green")
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
        print(f"  {GATE.name}, {EDGES.name}, {CHECKS.name}, "
              f"{BUDGETS.name} and {RUNS.name}: no environment, no "
              f"configuration, one use of the command line")
    problems += normalises_only_the_plans_list()

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
