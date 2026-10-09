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


def _caught(expr: str, shown: str = "t") -> str:
    return (f"check {expr} {{\n    ok t {{\n        print({shown})\n    }}\n"
            "    fail w {\n        print(w)\n    }\n}")


class FilesThatAreNotUtf8(Run):
    """9.0: a file that is not UTF-8 is a failure a program handles, and a
    text holding a lone surrogate is not written - until then both ended
    the run with a traceback, the second after the file was emptied."""

    def file(self, name: str, raw: bytes) -> str:
        path = os.path.join(self.dir, name)
        with open(path, "wb") as fh:
            fh.write(raw)
        return path.replace(os.sep, "/")

    def test_a_read_of_one_fails_and_the_run_goes_on(self) -> None:
        for raw in (b"caf\xe9", b"ab\xe2\x82", b"\xed\xa0\x80", b"ok\n" * 9 + b"\xff"):
            path = self.file("bad.txt", raw)
            doc = self.run_text(main_of(
                _caught(f'read_file("{path}")') + "\n"
                + _caught(f'read_file_secret("{path}")', '"a secret"')
                + '\nprint("on")',
                uses="io, fs"), allow="io,fs")
            said = f"cannot read file '{path}': it is not UTF-8 text\n"
            self.assertEqual((doc["raised"], doc["exit"], doc["stdout"]),
                             (None, 0, said + said + "on\n"), raw)

    def write_surrogate(self, path: str) -> dict[str, Any]:
        reader = ("fn half() -> Text or fail {\n"
                  '    return try json_get("[\\"\\\\ud800\\"]", "0")\n}\n')
        return self.run_text(reader + main_of(
            "check half() {\n    ok t {\n"
            f'        write_file("{path}", "a" + t)\n'
            '        print("WROTE IT")\n    }\n'
            "    fail w {\n        print(w)\n    }\n}", uses="io, fs"),
            allow="io,fs")

    def test_a_lone_surrogate_is_e608_and_leaves_a_file_as_it_was(self) -> None:
        path = self.file("kept.txt", b"kept")
        doc = self.write_surrogate(path)
        self.assertEqual((doc["raised"], doc["stdout"], doc["error"]["code"]),
                         (None, "", "E608"))
        self.assertEqual(doc["error"]["message"],
                         f"could not write '{path}': the text holds a lone "
                         "surrogate, which is not UTF-8")
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), b"kept")

    def test_a_lone_surrogate_makes_no_file(self) -> None:
        path = os.path.join(self.dir, "new.txt").replace(os.sep, "/")
        self.assertEqual(self.write_surrogate(path)["error"]["code"], "E608")
        self.assertFalse(os.path.exists(path))


class APromiseNamesItsOwnFile(Run):
    """9.0: a broken promise - and an error raised while one is checked -
    names the file the promise is written in. Until then the caller's frame
    blamed it, so a library's named the importer's file with the library's
    line, and the program's own, called back by a library, the library's."""

    LIB = ("fn half(x: Int) -> Int\n    requires x > 0\n{\n    return x / 2\n}\n"
           "fn negated(x: Int) -> Int\n    ensures result < 0\n{\n    return x\n}\n"
           "fn third(xs: List of Int) -> Int\n    requires get(xs, 2) > 0\n{\n"
           "    return get(xs, 2)\n}\n"
           "fn call_with(f: fn(Int) -> Int, x: Int) -> Int {\n    return f(x)\n}\n")

    def broken(self, imported: str, body: str, own: str = "") -> dict[str, Any]:
        with open(os.path.join(self.dir, "lib.vel"), "w", encoding="utf-8",
                  newline="\n") as fh:
            fh.write(self.LIB)
        return self.run_text(f'import "lib.vel"{imported}\n' + own + main_of(body))["error"]

    def where(self, err: dict[str, Any]) -> tuple[str, str, int]:
        return err["code"], os.path.basename(err["file"]), err["line"]

    def test_a_librarys_requires_and_ensures_flat_and_named(self) -> None:
        for imported, p in (("", ""), (" as lib", "lib.")):
            self.assertEqual(self.where(self.broken(imported, f"print({p}half(0 - 4))")),
                             ("E600", "lib.vel", 2))
            self.assertEqual(self.where(self.broken(imported, f"print({p}negated(1))")),
                             ("E601", "lib.vel", 7))
            self.assertEqual(self.where(self.broken(imported, f"print({p}third([1]))")),
                             ("E602", "lib.vel", 12))

    def test_the_programs_own_promise_called_back(self) -> None:
        own = "fn positive_only(x: Int) -> Int\n    requires x > 0\n{\n    return x\n}\n"
        err = self.broken(" as lib", "print(lib.call_with(positive_only, 0 - 2))", own)
        self.assertEqual(self.where(err), ("E600", "p.vel", 3))


class ReceiptOfARun(Run):
    """The run document's receipt (M3, third checkpoint): what `sabline
    <file> --receipt` writes of the same run, with nothing asked of the
    operating system, a limit's stop recorded as the end it stands for,
    and none where the command line writes none."""

    def receipt(self, source: str, **given: Any) -> Any:
        path = os.path.join(self.dir, "p.vel")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(source)
        return run_dump.run_and_receipt(path, **given)

    def test_it_is_what_the_command_line_writes(self) -> None:
        import json
        import subprocess
        import sys
        source = main_of(
            'let k = env("PATH", "")\nlet i = 0\n'
            'while i < 3 {\n    print(length(hmac_sha256(k, "m")))\n    i = i + 1\n}\n'
            'print(length(declassify(k, "a length")))\nprint(now())',
            uses="io, env, declassify, clock")
        _, ours = self.receipt(source, allow="io,env,declassify")
        written = os.path.join(self.dir, "r.json")
        subprocess.run([sys.executable, os.path.join(_support.REPO, "sabline.py"),
                        "p.vel", "--allow", "io,env,declassify", "--no-confine",
                        "--receipt", written], cwd=self.dir, capture_output=True)
        with open(written, encoding="utf-8") as fh:
            theirs = json.load(fh)
        for doc in (ours, theirs):
            for key in ("startedAt", "wall_time_ms", "run_parameters"):
                doc["predicate"].pop(key)
            doc["subject"][0]["name"] = "p.vel"
        self.assertEqual(ours, theirs)
        self.assertEqual(ours["predicate"]["exit"],
                         {"status": 1, "outcome": "refused", "code": "E310"})
        self.assertEqual([d["times"] for d in ours["predicate"]["declassifications"]],
                         [3, 1])

    def test_nothing_is_asked_of_the_operating_system(self) -> None:
        _, receipt = self.receipt(main_of('print("x")'))
        said = receipt["predicate"]["run_parameters"]
        self.assertEqual(
            {k: said[k] for k in ("confinement", "confinement_reason",
                                  "confinement_layers", "os_policy_sha256")},
            {"confinement": "none",
             "confinement_reason": "nothing was asked of the operating system",
             "confinement_layers": [], "os_policy_sha256": None})

    def test_a_limits_stop_is_the_end_it_stands_for(self) -> None:
        _, steps = self.receipt(main_of("while true {\n    print(1)\n}"))
        self.assertEqual(steps["predicate"]["exit"],
                         {"status": None, "outcome": "timeout", "code": "E610"})
        # main's own call is the first of the 20,000 steps
        self.assertEqual(steps["predicate"]["effects_used"], {"io": 19999})
        _, size = self.receipt(main_of('let s = "ab"\nwhile true {\n    s = s + s\n}'))
        self.assertEqual(size["predicate"]["exit"]["outcome"], "out_of_memory")

    def test_none_where_the_command_line_writes_none(self) -> None:
        self.assertIsNone(self.receipt(main_of('print("x")'), allow="io,fs:nowhere")[1])
        # 10000-01-01T00:00:00Z: past what an instant in a receipt can say
        self.assertIsNone(self.receipt(main_of('print("x")'),
                                       freeze_time=253402300800)[1])

    def test_a_frozen_clock_is_said_on_every_system(self) -> None:
        # until 9.0, on Windows, a receipt of a run frozen before
        # 1969-12-31T12:00Z or after 3001-01-19T21:59:59Z was an OSError
        # traceback once the run had ended, and an empty receipt file
        import json
        import subprocess
        import sys
        for epoch, said in ((-315619200, "1960-01-01T00:00:00Z"),
                            (64060588800, "4000-01-01T00:00:00Z"),
                            (253402300799, "9999-12-31T23:59:59Z"),
                            (-62135596800, "0001-01-01T00:00:00Z")):
            _, receipt = self.receipt(main_of('print("x")'), freeze_time=epoch)
            self.assertEqual(receipt["predicate"]["run_parameters"]["freeze_time"],
                             said)
        written = os.path.join(self.dir, "r.json")
        done = subprocess.run(
            [sys.executable, os.path.join(_support.REPO, "sabline.py"), "p.vel",
             "--freeze-time", "1960-01-01T00:00:00Z", "--no-confine",
             "--receipt", written], cwd=self.dir, capture_output=True,
            text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stderr)
        with open(written, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["predicate"]["run_parameters"]
                             ["freeze_time"], "1960-01-01T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
