"""Stage 8, the interpreter, alone: what 9.0's M3 changed in it, held here
as well as by the agreement gate - which shows that the two runtimes agree,
and not what they agree on.

How a function value prints: `fn` and its name, the lifted `fn#N` for one
written inline, carrying names or not, wherever a value is written. all_of
and any_of as a loop, so that a function value reaching them again stops at
the depth limit on every CPython. The run document's size limit: what it
counts, where it stops, and that nothing is counted without it. And the run
document's entries: a budget, a seed, a frozen clock, a read ceiling and
variables over the environment.
"""
import os
import tempfile
import unittest

import _support  # noqa: F401 - puts this checkout first on sys.path
from sabline import run_dump
from sabline import state as _state
from sabline.nodes import Function
from sabline.runtime import SizeLimit, made, size_of
from sabline.values import Bound, to_text
from typing import Any

STAGE = "runtime"


class Run(unittest.TestCase):
    """A program written to a file and run as the run document runs it."""

    def setUp(self) -> None:
        self.dir = tempfile.mkdtemp(prefix="sabline-runtime-")

    def run_text(self, source: str, **given: Any) -> dict[str, Any]:
        path = os.path.join(self.dir, "p.vel")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(source)
        return run_dump.run_document(path, **given)


def main_of(body: str, uses: str = "io") -> str:
    return (f"fn main() uses {uses} {{\n"
            + "".join(f"    {line}\n" for line in body.strip().splitlines())
            + "}\n")


class FunctionValuesPrint(Run):

    def test_a_function_and_a_value_carrying_names_print_their_names(self) -> None:
        f = Function("double", [("x", "Int")], "Int", set(), [], [], [], 1)
        self.assertEqual((to_text(f), repr(f), str([f])),
                         ("fn double", "fn double", "[fn double]"))
        lifted = Function("fn#4", [("x", "Int")], "Int", set(), [], [], [], 1)
        b = Bound(lifted, {"k": 1})
        self.assertEqual((to_text(b), repr(b), str({1: b})),
                         ("fn fn#4", "fn fn#4", "{1: fn fn#4}"))

    def test_a_run_prints_them_so_and_a_promise_names_them_so(self) -> None:
        doc = self.run_text(
            "fn double(x: Int) -> Int {\n    return x * 2\n}\n"
            "fn pick(fs: List of fn(Int) -> Int) -> Int\n"
            "    requires length(fs) > 5\n{\n    return 0\n}\n"
            + main_of("let n = 3\nlet g = fn(x: Int) -> Int { return x + n }\n"
                      "print(double)\nprint(g)\nprint([double, g])\n"
                      "print(pick([double, g]))"))
        self.assertEqual(doc["stdout"], "fn double\nfn fn#1\n[fn double, fn fn#1]\n")
        self.assertEqual(doc["error"]["code"], "E600")
        self.assertIn("(fs = [fn double, fn fn#1])", doc["error"]["message"])


class AllOfAndAnyOf(Run):

    def test_they_stop_at_the_first_answer(self) -> None:
        # the item after the answer would divide by zero
        doc = self.run_text(main_of(
            "print(all_of([1, 0], fn(x: Int) -> Bool { return 10 / x > 100 }))\n"
            "print(any_of([1, 0], fn(x: Int) -> Bool { return 10 / x > 5 }))\n"
            "print(all_of([1, 2], fn(x: Int) -> Bool { return x > 0 }))"))
        self.assertEqual((doc["stdout"], doc["error"]), ("false\ntrue\ntrue\n", None))

    def test_a_value_reaching_them_again_meets_the_depth_limit(self) -> None:
        for builtin in ("all_of", "any_of"):
            doc = self.run_text(
                "fn spin(xs: List of Int) -> Bool {\n"
                f"    return {builtin}(xs, fn(x: Int) -> Bool {{ return spin([x]) }})\n}}\n"
                + main_of("print(spin([1]))"))
            self.assertEqual((doc["error"]["code"], doc["error"]["line"]),
                             ("E609", 2), builtin)
            self.assertIn("called itself 2000 deep", doc["error"]["message"])


class SizeLimitCounts(Run):

    def tearDown(self) -> None:
        vars(_state)["_SIZE_LIMIT"] = None
        _state._SIZE_MADE[0] = 0

    def test_what_a_value_counts(self) -> None:
        self.assertEqual([size_of(v) for v in (
            "abc", "é", "€", "\U0001F600", "\ud800", "", [1, 2],
            {1: 1}, 7, 2.5, True, None)],
                         [3, 2, 3, 4, 3, 0, 2, 1, 0, 0, 0, 0])

    def test_it_stops_past_the_limit_not_at_it(self) -> None:
        vars(_state)["_SIZE_LIMIT"] = 5
        _state._SIZE_MADE[0] = 0
        made("abcde", 1)
        with self.assertRaises(SizeLimit) as stopped:
            made("f", 2)
        self.assertEqual(stopped.exception.line, 2)

    def test_a_run_that_grows_is_stopped_where_it_passes_it(self) -> None:
        doc = self.run_text(main_of(
            'let s = "x"\nwhile true {\n    s = s + s\n    print(length(s))\n}'))
        self.assertEqual((doc["stopped"], doc["stopped_by"], doc["exit"]),
                         (4, "size", None))
        self.assertTrue(doc["stdout"].endswith("\n1048576\n"))

    def test_without_the_limit_nothing_is_counted(self) -> None:
        from sabline.library import run
        result = run(main_of('let s = "abc"\nprint(s + s)'))
        self.assertEqual(result.output, "abcabc\n")
        self.assertEqual(_state._SIZE_MADE[0], 0)


class RunDocumentEntries(Run):

    def test_a_budget_seed_and_clock(self) -> None:
        doc = self.run_text(main_of("print(now())\nprint(random(6))\nprint(random(6))",
                                    uses="io, clock, rand"),
                            allow="io,clock,rand", seed=1, freeze_time=86400)
        self.assertEqual(doc["stdout"], "86400\n1\n4\n")

    def test_a_budget_that_does_not_parse_runs_nothing(self) -> None:
        doc = self.run_text(main_of('print("x")'), allow="io,fs:nowhere")
        self.assertEqual((doc["raised"], doc["exit"], doc["stdout"]),
                         ("BudgetError", None, ""))

    def test_the_read_ceiling(self) -> None:
        data = os.path.join(self.dir, "ten.txt")
        with open(data, "wb") as fh:
            fh.write(b"0123456789")
        source = main_of(f'check read_file("{data.replace(os.sep, "/")}") '
                         "{\n    ok t {\n        print(t)\n    }\n"
                         "    fail w {\n        print(w)\n    }\n}", uses="io, fs")
        self.assertEqual(self.run_text(source, allow="io,fs")["stdout"],
                         "0123456789\n")
        doc = self.run_text(source, allow="io,fs", max_read=9)
        self.assertEqual(doc["error"]["code"], "E316")
        self.assertEqual(_state.MAX_READ_BYTES, 64 * 1024 * 1024)

    def test_variables_over_the_environment_and_put_back(self) -> None:
        name = "SABLINE_UNIT_RUNTIME_VALUE"
        self.assertNotIn(name, os.environ)
        doc = self.run_text(main_of(
            f'print(declassify(env("{name}", "unset"), "a test"))',
            uses="io, env, declassify"),
            allow="io,env,declassify", environ={name: "set here"})
        self.assertEqual(doc["stdout"], "set here\n")
        self.assertNotIn(name, os.environ)


if __name__ == "__main__":
    unittest.main()
