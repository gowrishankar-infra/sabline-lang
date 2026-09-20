"""Release 8.2, item 32: the compiler's modules in pipeline order.

sabline/__init__.py: "The compiler, one module per stage, in the order a
program goes through them; _MODULES names them in that order. A module
imports only from the modules before it, but for the names its
__forward__ lists, which this file binds once all are loaded."

These read each module's syntax tree for its imports, and the package
after `import sabline` for what __forward__ binds.
"""
import ast
import os
import sys
import unittest

import _support
import sabline
from sabline import cli
from typing import Any, Callable, cast

PACKAGE = os.path.join(_support.REPO, "sabline")
MODULES = sabline._MODULES
POSITION = {name: i for i, name in enumerate(MODULES)}

STAGES = ("lexer", "parser", "loader", "effects", "checker", "prover",
          "native", "runtime", "cli")
CLI_RUN_STAGES = ("load_program", "check_effects", "check_types",
                  "check_proofs", "compile_native", "interpret")


def syntax_tree(name: str) -> ast.Module:
    path = os.path.join(PACKAGE, name + ".py")
    with open(path, encoding="utf-8") as f:
        return ast.parse(f.read(), filename=path)


def is_type_checking(test: Any) -> bool:
    return ((isinstance(test, ast.Name) and test.id == "TYPE_CHECKING")
            or (isinstance(test, ast.Attribute)
                and test.attr == "TYPE_CHECKING"))


def import_targets(node: Any) -> list[Any]:
    """[(sabline module, names imported from it)] for one import
    statement; [] when it imports nothing of sabline. "sabline" stands for
    the package itself, which loads every module."""
    if isinstance(node, ast.Import):
        out: list[tuple[str, list[str]]] = []
        for alias in node.names:
            if alias.name == "sabline":
                out.append(("sabline", []))
            elif alias.name.startswith("sabline."):
                out.append((alias.name.split(".")[1], []))
        return out
    names = [alias.name for alias in node.names]
    if node.level == 1 and node.module is None:        # from . import x
        return [(n, []) for n in names]
    if node.level == 1:                                 # from .x import y
        return [(node.module.split(".")[0], names)]
    if node.level > 1:
        return [("<beyond the package>", names)]
    if node.module == "sabline":
        return [(n, []) if n in POSITION else ("sabline", [n]) for n in names]
    if node.module and node.module.startswith("sabline."):
        return [(node.module.split(".")[1], names)]
    return []


def module_level_imports(tree: Any) -> list[Any]:
    """(module, names, line, under TYPE_CHECKING) for every import of a
    sabline module outside a function body: what runs when the module is
    imported, and what a type checker reads under `if TYPE_CHECKING:`."""
    found: list[tuple[str, list[str], int, bool]] = []

    def walk(node: Any, guarded: Any) -> None:
        child: ast.AST
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.Lambda)):
            return
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            found.extend((module, names, node.lineno, guarded)
                         for module, names in import_targets(node))
            return
        if isinstance(node, ast.If) and is_type_checking(node.test):
            for child in node.body:
                walk(child, True)
            for child in node.orelse:
                walk(child, guarded)
            return
        for child in ast.iter_child_nodes(node):
            walk(child, guarded)

    walk(tree, False)
    return found


def declared_forward(tree: Any) -> dict[Any, Any]:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "__forward__"
                for t in node.targets):
            return cast("dict[Any, Any]", ast.literal_eval(node.value))
    return {}


def position(module: str) -> int:
    return len(MODULES) if module == "sabline" else POSITION[module]


class ModuleOrder(unittest.TestCase):

    def test_every_module_is_listed_once(self) -> None:
        self.assertEqual(len(MODULES), len(set(MODULES)))
        on_disk = {name[:-3] for name in os.listdir(PACKAGE)
                   if name.endswith(".py")} - {"__init__", "__main__"}
        self.assertEqual(sorted(set(MODULES) ^ on_disk), [],
                         "in _MODULES or in sabline/, not both")

    def test_the_stages_appear_in_pipeline_order(self) -> None:
        self.assertEqual([s for s in STAGES if s not in POSITION], [])
        at = [POSITION[s] for s in STAGES]
        self.assertEqual(at, sorted(set(at)),
                         f"_MODULES has them in the order "
                         f"{sorted(STAGES, key=cast('Callable[[str], int]', POSITION.get))}")

    def test_no_module_level_import_from_a_later_module(self) -> None:
        problems = []
        for name in MODULES:
            for module, names, line, guarded in \
                    module_level_imports(syntax_tree(name)):
                if guarded:
                    continue
                if module != "sabline" and module not in POSITION:
                    problems.append(f"sabline/{name}.py:{line} imports from "
                                    f"{module}, which _MODULES does not list")
                elif position(module) >= POSITION[name]:
                    what = ", ".join(names) or "the module"
                    problems.append(f"sabline/{name}.py:{line} imports {what} "
                                    f"from {module}, which is not before it")
        self.assertEqual(problems, [])

    def test_type_checking_imports_from_later_modules_are_forward_names(self) -> None:
        problems, seen = [], 0
        for name in MODULES:
            tree = syntax_tree(name)
            forward = declared_forward(tree)
            for module, names, line, guarded in module_level_imports(tree):
                if not guarded or (module in POSITION
                                   and POSITION[module] < POSITION[name]):
                    continue
                seen += 1
                if not names:
                    problems.append(f"sabline/{name}.py:{line} imports the "
                                    f"module {module} under TYPE_CHECKING")
                for n in names:
                    if forward.get(n) != module:
                        problems.append(
                            f"sabline/{name}.py:{line} imports {n} from "
                            f"{module} under TYPE_CHECKING, and __forward__ "
                            f"says {forward.get(n)!r}")
        self.assertEqual(problems, [])
        self.assertGreater(seen, 0, "no import under TYPE_CHECKING was found; "
                                    "the rule this test reads is gone")

    def test_forward_names_are_bound_after_import_sabline(self) -> None:
        bound = 0
        for name in MODULES:
            module = sys.modules[f"sabline.{name}"]
            forward = getattr(module, "__forward__", {})
            self.assertEqual(forward, declared_forward(syntax_tree(name)))
            for used, owner in sorted(forward.items()):
                with self.subTest(module=name, name=used):
                    self.assertIn(owner, POSITION)
                    self.assertGreater(POSITION[owner], POSITION[name],
                                       "a forward name comes from a later "
                                       "module")
                    source = sys.modules[f"sabline.{owner}"]
                    self.assertTrue(hasattr(module, used))
                    self.assertIs(getattr(module, used),
                                  getattr(source, used))
                    bound += 1
        self.assertGreater(bound, 0)

    def test_cli_run_calls_the_stages_in_this_order(self) -> None:
        tree = syntax_tree("cli")
        run = next(node for node in ast.walk(tree)
                   if isinstance(node, ast.FunctionDef)
                   and node.name == "_cli_run")
        first: dict[str, tuple[int, int]] = {}
        for node in ast.walk(run):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in CLI_RUN_STAGES):
                at = (node.lineno, node.col_offset)
                first[node.func.id] = min(first.get(node.func.id, at), at)
        self.assertEqual(sorted(first, key=cast("Callable[[str], tuple[int, int]]",
                                                first.get)),
                         list(CLI_RUN_STAGES))

    def test_cli_run_stages_are_defined_in_modules_in_that_order(self) -> None:
        owners = []
        for stage in CLI_RUN_STAGES:
            defined_in = getattr(cli, stage).__module__
            self.assertTrue(defined_in.startswith("sabline."), defined_in)
            owners.append(defined_in.split(".", 1)[1])
        at = [POSITION[m] for m in owners]
        self.assertEqual(at, sorted(set(at)),
                         f"defined in {dict(zip(CLI_RUN_STAGES, owners))}")


if __name__ == "__main__":
    unittest.main()
