#!/usr/bin/env python3
"""Mutation testing of the functions a guarantee rests on (8.2 item 10).

A test suite that passes proves little unless it would fail if the code were
wrong. This makes the code wrong on purpose, one small change at a time, in
the functions that carry what SECURITY.md and STABILITY.md promise - the
budget's path, host, proxy, module and count checks, the effect checker, the
Secret rules, the prover's guard against false counterexamples, the import
root, the door's token and limits - and runs the suites that should notice.
A change they notice is a killed mutant. A change they do not is a
surviving one: a line of a guarantee no test holds.

It is the "equivalent" of mutmut the release asked for: mutmut 3 needs
pytest and fork(), and these suites are plain scripts run on Windows too.

How:
- The tree is copied once to a scratch directory; the checkout is never
  changed, so the suites can keep running from it meanwhile.
- The killers are first run on the unchanged copy; if one fails there, the
  run stops (exit 2), since it could not tell a mutant from a broken tree.
- For each mutant, one module of the copy's package is rewritten
  (`ast.unparse` of the module with one node changed) and the killers for
  that function run; any failure or timeout kills it.
- Operators: a comparison flipped (< and <=, == and !=, in and not in, is
  and is not), `and` and `or` swapped, a `not` removed, True and False
  swapped, an `if`'s test negated, a `raise` replaced by `pass`, a `return`
  of a value replaced by `return None`, and + and - swapped.

    python check_mutants.py --list                  the mutants, no runs
    python check_mutants.py --minutes 10            a short local run
    python check_mutants.py --minutes 60 --json mutants.json --issues out/
                                                    the monthly run

--issues DIR writes one Markdown issue body per surviving mutant; the
monthly workflow opens an issue for each (MAINTENANCE.md).
"""
from __future__ import annotations

import ast
import copy
import json
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from suite_dirs import isolate  # noqa: E402

# module -> (the functions a guarantee rests on, the suites that must
# notice a change to them). A name "a.b" is b defined inside a (a nested
# function, or a method of class a).
GUARANTEES: dict[str, tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]] = {
    "budget": (("allow_path", "_credential_root", "host_refusal", "allow_host",
                "count_op", "_proxy_for", "guarded_opener", "allow_module",
                "ffi_reach", "_ffi_resolve", "spend", "checked_int",
                "_fs_grant_covers", "_net_grant_covers", "_host_matches",
                "Budget.covers", "Budget.parse"),
               (("check_sandbox.py",), ("check_refusals.py",))),
    "effects": (("check_effects",),
                (("check_refusals.py",), ("check_secret.py",))),
    "wrappers": (("is_secret", "carries_secret", "strip_secret",
                  "records_carrying", "currency_clash"),
                 (("check_secret.py",), ("check_money.py",))),
    "prover": (("check_proofs.has_fresh", "check_proofs.uninterpreted_in",
                "check_proofs.prove_invariant", "check_proofs.prove_bounds"),
               (("check_refusals.py",), ("check_prover_lies.py",))),
    "loader": (("_import_refusal",), (("check_library.py",),)),
    "doors": (("_token_matches", "run_limits", "_RateLimit.take"),
              (("check_library.py",),)),
}
KILLER_SECONDS = 1800

FLIP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
        ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.In: ast.NotIn,
        ast.NotIn: ast.In, ast.Is: ast.IsNot, ast.IsNot: ast.Is}


def find(tree: ast.Module, dotted: str) -> ast.AST | None:
    """The function (or method, or nested function) a dotted name names."""
    scope: list[ast.stmt] = tree.body
    node: ast.AST | None = None
    for part in dotted.split("."):
        node = None
        for candidate in ast.walk(ast.Module(body=scope, type_ignores=[])):
            if isinstance(candidate, (ast.FunctionDef, ast.ClassDef)) \
                    and candidate.name == part:
                node = candidate
                break
        if node is None:
            return None
        scope = node.body
    return node


def sites(fn: ast.AST) -> list[tuple[str, int, int, str]]:
    """(operator, line, column, what) for every place an operator applies in
    `fn`, nested functions not named separately included."""
    out = []
    for node in ast.walk(fn):
        where = (getattr(node, "lineno", 0), getattr(node, "col_offset", 0))
        if isinstance(node, ast.Compare):
            for i, op in enumerate(node.ops):
                if type(op) in FLIP:
                    out.append(("flip-compare", *where,
                                f"{type(op).__name__}#{i}"))
        elif isinstance(node, ast.BoolOp):
            out.append(("swap-boolop", *where, type(node.op).__name__))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            out.append(("drop-not", *where, "not"))
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            out.append(("flip-bool", *where, str(node.value)))
        elif isinstance(node, ast.If):
            out.append(("negate-if", *where, "if"))
        elif isinstance(node, ast.Raise):
            out.append(("raise-to-pass", *where, "raise"))
        elif isinstance(node, ast.Return) and node.value is not None and not (
                isinstance(node.value, ast.Constant)
                and node.value.value is None):
            out.append(("return-none", *where, "return"))
        elif isinstance(node, ast.BinOp) and isinstance(node.op,
                                                        (ast.Add, ast.Sub)):
            out.append(("swap-addsub", *where, type(node.op).__name__))
    return out


class Mutate(ast.NodeTransformer):
    """Apply one operator at one (line, column)."""

    def __init__(self, operator: str, line: int, col: int, what: str) -> None:
        self.operator, self.line, self.col, self.what = operator, line, col, what
        self.done = False

    def _here(self, node: ast.AST) -> bool:
        return (not self.done and getattr(node, "lineno", -1) == self.line
                and getattr(node, "col_offset", -1) == self.col)

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        self.generic_visit(node)
        if self.operator == "flip-compare" and self._here(node):
            i = int(self.what.split("#")[1])
            node.ops[i] = FLIP[type(node.ops[i])]()
            self.done = True
        return node

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        self.generic_visit(node)
        if self.operator == "swap-boolop" and self._here(node):
            node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
            self.done = True
        return node

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        self.generic_visit(node)
        if self.operator == "drop-not" and self._here(node):
            self.done = True
            return node.operand
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if self.operator == "flip-bool" and self._here(node):
            self.done = True
            return ast.copy_location(ast.Constant(not node.value), node)
        return node

    def visit_If(self, node: ast.If) -> ast.AST:
        self.generic_visit(node)
        if self.operator == "negate-if" and self._here(node):
            node.test = ast.UnaryOp(ast.Not(), node.test)
            self.done = True
        return node

    def visit_Raise(self, node: ast.Raise) -> ast.AST:
        if self.operator == "raise-to-pass" and self._here(node):
            self.done = True
            return ast.copy_location(ast.Pass(), node)
        return node

    def visit_Return(self, node: ast.Return) -> ast.AST:
        self.generic_visit(node)
        if self.operator == "return-none" and self._here(node):
            node.value = ast.Constant(None)
            self.done = True
        return node

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        self.generic_visit(node)
        if self.operator == "swap-addsub" and self._here(node):
            node.op = ast.Sub() if isinstance(node.op, ast.Add) else ast.Add()
            self.done = True
        return node


def mutants(chosen: list[str]) -> list[dict[Any, Any]]:
    out = []
    for module in chosen:
        functions, _ = GUARANTEES[module]
        source = (HERE / "velaris" / f"{module}.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        lines = source.splitlines()
        for name in functions:
            fn = find(tree, name)
            if fn is None:
                print(f"  note    {module}.{name} not found; skipped")
                continue
            for operator, line, col, what in sites(fn):
                out.append({"module": module, "function": name,
                            "operator": operator, "line": line, "col": col,
                            "what": what,
                            "text": lines[line - 1].strip()[:120]})
    return out


def mutated_source(m: dict[Any, Any]) -> str | None:
    source = (HERE / "velaris" / f"{m['module']}.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    changer = Mutate(m["operator"], m["line"], m["col"], m["what"])
    new = changer.visit(copy.deepcopy(tree))
    if not changer.done:
        return None
    ast.fix_missing_locations(new)
    return ast.unparse(new)


def run_killers(tree: Path, killers: Any, deadline: float) -> tuple[bool, str]:
    """(every killer passed, the first that did not and why)."""
    for words in killers:
        left = max(60.0, min(KILLER_SECONDS, deadline - time.monotonic()))
        try:
            done = subprocess.run([sys.executable, *words], cwd=str(tree),
                                  capture_output=True, text=True,
                                  timeout=left)
        except subprocess.TimeoutExpired:
            return False, f"{' '.join(words)}: timed out"
        if done.returncode != 0:
            tail = (done.stdout + done.stderr).strip().splitlines()[-1:]
            return False, f"{' '.join(words)}: exit {done.returncode} " \
                          f"{tail[0][:160] if tail else ''}"
    return True, ""


def main(argv: list[str]) -> int:
    chosen = (argv[argv.index("--modules") + 1].split(",")
              if "--modules" in argv else list(GUARANTEES))
    minutes = float(argv[argv.index("--minutes") + 1]) \
        if "--minutes" in argv else 30.0
    seed = int(argv[argv.index("--seed") + 1]) if "--seed" in argv else 8
    every = mutants(chosen)
    random.Random(seed).shuffle(every)          # a fair sample when cut short
    if "--list" in argv:
        for m in every:
            print(f"{m['module']}.{m['function']} line {m['line']} "
                  f"{m['operator']}: {m['text']}")
        print(f"{len(every)} mutant(s)")
        return 0
    deadline = time.monotonic() + minutes * 60
    tree = isolate("check_mutants") / "tree"
    # docs/ is copied: check_library.py holds attestations to the schemas
    # under docs/capability and docs/receipt
    shutil.copytree(HERE, tree, ignore=shutil.ignore_patterns(
        ".git", "__pycache__", "playground", "paper", "node_modules",
        "*.exe", "*.mcpb", "dist", "build", "velaris-spec"))
    killers_of = {module: GUARANTEES[module][1] for module in chosen}
    print(f"mutation testing: {len(every)} mutant(s) in "
          f"{', '.join(chosen)}; {minutes:g} minute(s)")
    for module in chosen:
        passed, why = run_killers(tree, killers_of[module], deadline + 3600)
        if not passed:
            print(f"  the unchanged tree fails its own killers: {why}")
            return 2
    results = []
    for m in every:
        if time.monotonic() >= deadline:
            break
        new = mutated_source(m)
        if new is None:
            continue
        target = tree / "velaris" / f"{m['module']}.py"
        original = target.read_text(encoding="utf-8")
        target.write_text(new, encoding="utf-8")
        shutil.rmtree(tree / "velaris" / "__pycache__", ignore_errors=True)
        try:
            passed, why = run_killers(tree, killers_of[m["module"]], deadline)
        finally:
            target.write_text(original, encoding="utf-8")
        m = dict(m, killed=not passed, by=why)
        results.append(m)
        print(f"  {'killed  ' if not passed else 'SURVIVED'} "
              f"{m['module']}.{m['function']} line {m['line']} "
              f"{m['operator']}: {m['text'][:70]}")
    killed = sum(r["killed"] for r in results)
    score = 100.0 * killed / len(results) if results else 0.0
    print(f"{killed} of {len(results)} mutant(s) killed ({score:.1f}%); "
          f"{len(every) - len(results)} not run within the time")
    if "--json" in argv:
        Path(argv[argv.index("--json") + 1]).write_text(json.dumps({
            "score": round(score, 1), "run": len(results), "killed": killed,
            "total": len(every), "results": results}, indent=2),
            encoding="utf-8")
    if "--issues" in argv:
        out = Path(argv[argv.index("--issues") + 1])
        out.mkdir(parents=True, exist_ok=True)
        for r in results:
            if r["killed"]:
                continue
            name = f"{r['module']}-{r['function']}-{r['line']}-{r['operator']}"
            (out / f"{name}.md").write_text(
                f"A surviving mutant in `velaris/{r['module']}.py`, in "
                f"`{r['function']}`, which a guarantee rests on.\n\n"
                f"Line {r['line']}: `{r['text']}`\n\n"
                f"Operator: `{r['operator']}` ({r['what']}). With this change "
                f"the suites that should notice it - "
                f"{', '.join(' '.join(k) for k in killers_of[r['module']])} - "
                f"all pass. Either a test is missing for this line, or the "
                f"change is equivalent to the original (say which, and "
                f"close).\n\nFound by `check_mutants.py` in the monthly "
                f"workflow. A robot reports this and fixes nothing "
                f"(MAINTENANCE.md).\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
