"""Stage 5, the type checker, alone: velaris.checker.check_types(funcs,
records, errors) and check_main, on programs the lexer and parser build
(and the loader, for the one case that needs a named import).

SPEC.md 3 and 4, 3.1 (Secret), 4.3 (Money), 8 (failure) and 12a, and
LLM.md's rules and error table, are what the cases hold it to.
"""
import unittest

import _support
from velaris.checker import check_main, check_types
from velaris.errors import VelarisError
from velaris.lexer import lex
from velaris.loader import load_program
from velaris.parser import Parser
from typing import Any

STAGE = "checker"


def parse(source: str) -> tuple[Any, ...]:
    funcs, records, _imports = Parser(lex(source)).parse_program()
    return funcs, records


def type_errors(funcs: Any, records: Any) -> list[Any]:
    errors: list[VelarisError] = []
    try:
        check_types(funcs, records, errors)
    except VelarisError as e:
        # a signature naming a type that does not exist stops the check
        # rather than being recorded; the command line reports it the same
        errors.append(e)
    return errors


def check_case(self: Any, case: Any) -> None:
    errors = type_errors(*parse(case.source))
    if case.refused:
        self.assertTrue(errors, "the documents refuse this; nothing was "
                                "reported")
        return
    self.assertEqual(_support.codes_and_lines(errors), case.errors,
                     "\n" + _support.describe(errors))


class Cases(unittest.TestCase):
    """fixtures/checker/*.vel, one test per case."""


for _file in ("types.vel", "generics.vel", "fallible.vel", "secret.vel",
              "money.vel", "records.vel", "function_values.vel"):
    _support.add_case_tests(Cases, STAGE, _file, check_case)


# SPEC.md 8 and LLM.md rule 2 and its "Builtins" list: every builtin that
# either document says can fail, called with arguments of the right types.
DOCUMENTED_FALLIBLE = {
    "to_int": 'to_int("1")',
    "read_file": 'read_file("a.txt")',
    "read_file_secret": 'read_file_secret("a.txt")',
    "fetch": 'fetch("http://example.com")',
    "post": 'post("http://example.com", "body")',
    "fetch_status": 'fetch_status("http://example.com")',
    "request": 'request("GET", "http://example.com", "", "{}")',
    "get on a map": 'get(m, "a")',
    "divide_or_fail": 'divide_or_fail(money(100, "INR"), 3, "down")',
    "parse_money": 'parse_money("1.00", "INR")',
    "py": 'py("math", "floor", ["1.5"])',
    "py_int": 'py_int("math", "floor", ["1.5"])',
    "py_float": 'py_float("math", "sqrt", ["2"])',
    "py_json": 'py_json("json", "dumps", "[1]")',
    "py_new": 'py_new("io", "StringIO", "[]")',
    "py_do": 'py_do(h, "getvalue", "[]")',
    "py_field": 'py_field(h, "closed")',
    "json_get": 'json_get("{}", "a")',
    "json_int": 'json_int("{}", "a")',
    "json_float": 'json_float("{}", "a")',
    "json_len": 'json_len("{}", "a")',
    "pop": "pop(xs)",
    "slice": "slice(xs, 0, 1)",
    "set_at": "set_at(xs, 0, 1)",
    "add_or_fail": "add_or_fail(1, 2)",
    "sub_or_fail": "sub_or_fail(1, 2)",
    "mul_or_fail": "mul_or_fail(1, 2)",
    "div_or_fail": "div_or_fail(1, 2)",
    "mod_or_fail": "mod_or_fail(1, 2)",
}

# LLM.md rule 3 and "Builtins": documented as not failing.
DOCUMENTED_TOTAL = {
    "get on a list": "get(xs, 0)",
    "get_or": 'get_or(m, "a", 0)',
    "has": 'has(m, "a")',
    "json_has": 'json_has("{}", "a")',
    "write_file": 'write_file("out.txt", "body")',
    "py_close": "py_close(h)",
    "length": "length(xs)",
}

PROBE = ("fn probe(h: Handle, xs: List of Int, m: Map of Text to Int) -> Int "
         "or fail uses io, fs, net, ffi {{\n    {statement}\n    return 1\n}}\n")


class Failure(unittest.TestCase):

    def errors_for(self, statement: str) -> list[Any]:
        return type_errors(*parse(PROBE.format(statement=statement)))

    def test_every_documented_fallible_builtin_must_be_handled(self) -> None:
        for name, call in DOCUMENTED_FALLIBLE.items():
            with self.subTest(builtin=name):
                errors = self.errors_for(f"let v = {call}")
                self.assertEqual(_support.codes_and_lines(errors),
                                 [("E520", 2)], _support.describe(errors))

    def test_each_can_be_passed_up_with_try(self) -> None:
        for name, call in DOCUMENTED_FALLIBLE.items():
            with self.subTest(builtin=name):
                errors = self.errors_for(f"let v = try {call}")
                self.assertEqual(errors, [], _support.describe(errors))

    def test_documented_total_builtins_need_neither(self) -> None:
        for name, call in DOCUMENTED_TOTAL.items():
            with self.subTest(builtin=name):
                errors = self.errors_for(call)
                self.assertEqual(errors, [], _support.describe(errors))


def setUpModule() -> None:
    _support.quiet_unclosed_source_files()


class Main(unittest.TestCase):
    """SPEC.md 1 and 8, LLM.md rule 8: main exists, takes no parameters,
    cannot fail."""

    def main_errors(self, source: str, **kw: Any) -> list[Any]:
        errors: list[VelarisError] = []
        check_main(parse(source)[0], errors, **kw)
        return _support.codes_and_lines(errors)

    def test_a_program_needs_main_E400_and_a_library_does_not(self) -> None:
        self.assertEqual(self.main_errors("fn helper() {\n}"), [("E400", 1)])
        self.assertEqual(self.main_errors("fn helper() {\n}", running=False),
                         [])

    def test_main_takes_no_parameters_E401(self) -> None:
        self.assertEqual(self.main_errors("\nfn main(name: Text) uses io {\n}"),
                         [("E401", 2)])

    def test_main_that_can_fail(self) -> None:
        # one mistake, one code, E524, from check_main and from check_types
        # alike (until 8.2 check_main said E523)
        source = "fn main() or fail uses io {\n}"
        self.assertEqual(self.main_errors(source), [("E524", 1)])
        self.assertEqual(_support.codes_and_lines(type_errors(*parse(source))),
                         [("E524", 1)])


class WhatTheCheckerRecords(unittest.TestCase):

    def test_names_holding_a_secret_are_marked_for_redaction(self) -> None:
        # SPEC.md 3.1: velaris trace and a broken promise print <secret>
        funcs, records = parse(
            "fn f(k: Secret of Text, n: Int) -> Secret of Int {\n"
            "    return length(k)\n}\n"
            "fn g(n: Int) -> Int {\n    return n\n}\n")
        self.assertEqual(type_errors(funcs, records), [])
        f, g = funcs
        self.assertEqual((f.secret_params, f.secret_result), ({"k"}, True))
        self.assertEqual((g.secret_params, g.secret_result), (set(), False))

    def test_an_inline_function_captures_the_locals_it_reads(self) -> None:
        # SPEC.md 12a: which of a function value's free names are the
        # surrounding function's locals is decided where it is made
        funcs, records = parse(
            "fn main() uses io {\n    let limit = 10\n"
            "    let small = fn(n: Int) -> Bool { return n < limit }\n"
            "    print(small(3))\n}\n")
        self.assertEqual(type_errors(funcs, records), [])
        (lifted,) = [f for f in funcs if f.is_lambda]
        self.assertEqual(lifted.captures, [("limit", "Int")])

    def test_an_import_s_name_cannot_be_a_variable_E514(self) -> None:
        main = _support.fixture(STAGE, "imports", "main.vel")
        errors = type_errors(*load_program(main))
        self.assertEqual(_support.codes_and_lines(errors), [("E514", 4)])
        self.assertTrue(_support.same_path(errors[0].file, main))


if __name__ == "__main__":
    unittest.main()
