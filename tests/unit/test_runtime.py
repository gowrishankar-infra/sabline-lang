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


class WrittenOutIsCountedFirst(Run):
    """9.0, M3 (the maintainer's decision): what an operation writes out is
    counted before it is made. The walks give exactly the bytes their
    writers write, and stop once past the room they are given - so that a
    value holding one text many times, or a list nested two of the level
    below at every level, stops the run at the operation that would write
    it, before it exists."""

    def tearDown(self) -> None:
        vars(_state)["_SIZE_LIMIT"] = None
        _state._SIZE_MADE[0] = 0

    @staticmethod
    def values(seed: int, n: int) -> list[Any]:
        import random
        from sabline.values import MoneyValue, RecordValue
        rng = random.Random(seed)
        texts = ["", "a", "it's", 'say "hi"', "back\\slash", "été",
                 "\U0001F600", "\ud800", "a\udc00b", "\x00\x07\x1f\x7f",
                 "\x85\x9f", "line\nbreak\rreturn\ttab", "  ",
                 "\b\f", "{}", "\xa0​"]
        f = Function("double", [("x", "Int")], "Int", set(), [], [], [], 1)
        leaves = [lambda: rng.choice(texts), lambda: rng.randint(-10**20, 10**20),
                  lambda: rng.choice([0.0, -0.0, 1.5, 1e16, 1e-05, float("nan"),
                                      float("inf"), float("-inf"), 2.5e-300]),
                  lambda: rng.choice([True, False]),
                  lambda: MoneyValue(rng.randint(-10**6, 10**6),
                                     rng.choice(["INR", "JPY", "KWD"])),
                  lambda: f, lambda: Bound(f, {"k": 1})]

        def value(depth: int) -> Any:
            pick = rng.random()
            if depth > 3 or pick < 0.4:
                return rng.choice(leaves)()
            if pick < 0.6:
                return [value(depth + 1) for _ in range(rng.randint(0, 4))]
            if pick < 0.8:
                keys = rng.choice([lambda: rng.choice(texts), lambda: rng.randint(-5, 5),
                                   lambda: rng.choice([1.5, float("nan"), -0.0]),
                                   lambda: rng.choice([True, False])])
                return {keys(): value(depth + 1) for _ in range(rng.randint(0, 4))}
            return RecordValue("Pt", {"x": value(depth + 1), "yé": value(depth + 1)})
        return [value(0) for _ in range(n)]

    def test_each_walk_is_exactly_its_writer(self) -> None:
        from sabline.runtime import run_builtin
        from sabline.values import (json_size, log_line, shown_size,
                                    utf8_size, written_size)
        big = 1 << 40
        for v in self.values(7, 3000):
            self.assertEqual(written_size(v, big), utf8_size(to_text(v)), v)
            self.assertEqual(written_size(v, big, log=True),
                             utf8_size(log_line(to_text(v))), v)
            self.assertEqual(shown_size(v, big), utf8_size(f"{v}"), v)
            try:
                written = run_builtin("json_of", [v], 1)
            except TypeError:            # a function value: json_of refuses it
                continue
            self.assertEqual(json_size(v, big), utf8_size(written), v)

    def test_each_walk_stops_past_its_room_and_not_before(self) -> None:
        from sabline.values import json_size, shown_size, written_size
        for v in self.values(11, 1500):
            for walk in (written_size, shown_size, json_size):
                exact = walk(v, 1 << 40)
                for room in (0, exact // 2, exact - 1, exact, exact + 1):
                    got = walk(v, max(room, 0))
                    self.assertEqual(got > room, exact > room, (walk, v, room))

    def test_a_list_nested_two_of_the_one_below_is_never_made(self) -> None:
        # forty levels: written out, 2^40 copies of the text - a terabyte -
        # where each level costs two items. Every way of writing it out
        # stops the run at that line, under the run document's limit, with
        # nothing made past it
        laughs = 'let a0 = ["ha"]\n' + "".join(
            f"let a{k} = [a{k - 1}, a{k - 1}]\n" for k in range(1, 41))
        for line, op in (("print(a40)", "print"), ("log(a40)", "log"),
                         ('let t = to_text(a40)', "to_text"),
                         ('let t = format("{}", a40)', "format"),
                         ('let t = "x" + to_text(a40)', "to_text"),
                         ('let t = json_of(a40)', "json_of")):
            doc = self.run_text(main_of(laughs + line + "\nprint(\"after\")"))
            self.assertEqual((doc["stopped"], doc["stopped_by"], doc["stdout"]),
                             (43, "size", ""), op)
        doc = self.run_text(laughs.replace("let ", "    let ").join((
            "fn short(xs: " + "List of " * 41 + "Text) -> Int\n    requires length(xs) > 2\n{\n"
            "    return 0\n}\nfn main() uses io {\n", "    print(short(a40))\n}\n")))
        self.assertEqual((doc["stopped"], doc["stopped_by"]), (2, "size"))

    def test_one_text_many_times_stops_where_it_would_be_written(self) -> None:
        # a megabyte, then a list of it eight times: eight items made, and
        # eight megabytes when written - past the limit, so the print stops
        doc = self.run_text(main_of(
            'let s = "x"\nlet i = 0\nwhile i < 20 {\n    s = s + s\n    i = i + 1\n}\n'
            "let xs = [s, s, s, s, s, s, s, s]\nprint(length(xs))\nprint(xs)"))
        self.assertEqual((doc["stdout"], doc["stopped"], doc["stopped_by"]),
                         ("8\n", 10, "size"))


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
        error: dict[str, Any] = self.run_text(
            f'import "lib.vel"{imported}\n' + own + main_of(body))["error"]
        return error

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


class AnAmountPastSixtyFourBits(Run):
    """9.0: an amount's units are an Int's 64 bits (SPEC.md 4.3), so one
    past them is E407 where money() or with_units() makes it. Until then the
    reference held it exactly and only arithmetic on it refused it."""

    def test_money_and_with_units_refuse_it_where_it_is_made(self) -> None:
        for body, line, op in (
                ('print(units_of(money(9223372036854775808, "INR")))', 1, "money"),
                ('let m = money(1, "INR")\nprint(with_units(m, 9223372036854775807))\n'
                 'print(with_units(m, 9223372036854775808))', 3, "with_units")):
            doc = self.run_text(main_of(body))
            self.assertEqual((doc["error"]["code"], doc["error"]["line"]),
                             ("E407", line + 1), doc)
            self.assertIn(f"this '{op}' made an amount too big to hold",
                          doc["error"]["message"])
        doc = self.run_text(main_of('print(money(-9223372036854775807 - 1, "INR"))'))
        self.assertEqual((doc["error"], doc["stdout"]),
                         (None, "INR -92233720368547758.08\n"))


class OneAnswerOnEveryCPython(Run):
    """9.0, M3: the three places the reference answered by CPython version
    answer as 3.12 does on every CPython - json's trailing comma, which
    3.13 words "Illegal trailing comma" a character earlier; int()'s digit
    limit, which 3.10 words "(4300)"; and base64 with padding at the start
    of a quad, which 3.10 decoded. This file runs on every leg, so each
    assertion is made on 3.10, 3.12 and 3.13 alike."""

    LIMIT = ("Exceeds the limit (4300 digits) for integer string conversion: "
             "value has {} digits; use sys.set_int_max_str_digits() to "
             "increase the limit")

    def test_a_trailing_comma_is_said_as_3_12_says_it(self) -> None:
        from sabline.values import read_json
        for text, said in (
                ("[1,]", "Expecting value: line 1 column 4 (char 3)"),
                ("[1, \n ]", "Expecting value: line 2 column 2 (char 6)"),
                ('{"a": 1,}', "Expecting property name enclosed in double "
                              "quotes: line 1 column 9 (char 8)"),
                ('[{"a": [2,],}]', "Expecting value: line 1 column 11 (char 10)")):
            with self.assertRaises(ValueError) as refused:
                read_json(text)
            self.assertEqual(str(refused.exception), said, text)

    def test_a_long_whole_number_is_refused_in_3_12s_words(self) -> None:
        from sabline.values import read_json, whole_number
        self.assertEqual(whole_number("1" * 4300), int("1" * 4300))
        self.assertEqual(whole_number("-" + "1" * 4300), -int("1" * 4300))
        for digits, n in (("1" * 4301, 4301), ("-" + "9" * 4301, 4301),
                          ("0" * 4300 + "1", 4301)):
            with self.assertRaises(ValueError) as refused:
                whole_number(digits)
            self.assertEqual(str(refused.exception), self.LIMIT.format(n))
        with self.assertRaises(ValueError) as refused:
            read_json("[0, " + "7" * 5000 + "]")
        self.assertEqual(str(refused.exception), self.LIMIT.format(5000))
        # a long document of short numbers reads as any other
        self.assertEqual(read_json('{"p": "' + "x" * 5000 + '", "n": [-1, 20]}')["n"],
                         [-1, 20])

    def test_a_budget_count_and_port_past_it(self) -> None:
        from sabline.budget import Budget
        for allow in ("fs@" + "1" * 4301, "net:x:" + "4" * 4301,
                      "net:[::1]:" + "4" * 4301, "tool:t@" + "5" * 4301):
            with self.assertRaises(ValueError) as refused:
                Budget.parse(allow)
            self.assertIn(self.LIMIT.format(4301), str(refused.exception), allow)

    def test_base64_padding_at_the_start_of_a_quad_is_refused(self) -> None:
        doc = self.run_text(main_of(
            'for t in ["YWJj==", "=", "==", "YWJj=", "YWI=", ""] {\n'
            '    check base64_decode(t) {\n'
            '        ok d { print(format("[{}]", d)) }\n'
            '        fail why { print(why) }\n'
            '    }\n'
            '}'))
        self.assertEqual(doc["stdout"], "that text is not base64\n" * 4 + "[ab]\n[]\n")


class ReceiptOfARun(Run):
    """The run document's receipt (M3, third checkpoint): what `sabline
    <file> --receipt` writes of the same run, with nothing asked of the
    operating system, a limit's stop recorded as the end it stands for,
    and none where the command line writes none."""

    def receipt(self, source: str, **given: Any) -> Any:
        path = os.path.join(self.dir, "p.vel")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(source)
        return run_dump.run_recorded(path, **given)[:2]

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
