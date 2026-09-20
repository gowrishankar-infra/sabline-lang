"""Stage 6, the prover, alone: sabline.prover.check_proofs(funcs, records,
errors, proven) on programs the lexer, parser, effect checker and type
checker build (those two only to hold each fixture to being a well-formed
program, which SPEC.md 11 says a proof assumes).

The translation to Z3 is a closure inside check_proofs, not something
the module exposes, so each expression form is reached through a small
contract that must prove and one that must be refuted: Int, Bool, Float,
Text, lists, records, maps, quantifiers, loops, calls, failure paths and
amounts (SPEC.md 9). Skipped as a whole when z3 is not installed.
"""
import importlib.util
import os
import re
import unittest
from unittest import mock

import _support
from typing import Any

if importlib.util.find_spec("z3") is None:
    raise unittest.SkipTest("z3-solver is not installed: there is no prover "
                            "to test")

from sabline.checker import check_types  # noqa: E402
from sabline.effects import check_effects  # noqa: E402
from sabline.lexer import lex  # noqa: E402
from sabline.parser import Parser  # noqa: E402
from sabline.prover import (  # noqa: E402
    FLOAT_PROOF_SECONDS, PROOF_SECONDS, PROOF_TIMEOUT_ENV, check_proofs,
    proof_timeout_seconds, set_proof_timeout,
)

STAGE = "prover"
CASE_FILES = ("arithmetic.vel", "floats.vel", "text.vel", "lists.vel",
              "records.vel", "maps.vel", "quantifiers.vel", "loops.vel",
              "calls.vel", "failure.vel", "money.vel")


def build(source: str) -> tuple[Any, ...]:
    """(funcs, records) of a well-formed program, or AssertionError."""
    funcs, records, _imports = Parser(lex(source)).parse_program()
    before: list[Any] = []
    check_effects(funcs, before)
    check_types(funcs, records, before)
    if before:
        raise AssertionError("the fixture is not a well-formed program:\n"
                             + _support.describe(before))
    return funcs, records


def prove(source: str) -> tuple[Any, ...]:
    funcs, records = build(source)
    errors: list[Any]
    proven: set[str]
    errors, proven = [], set()
    check_proofs(funcs, records, errors, proven)
    return funcs, errors, proven


def check_case(self: Any, case: Any) -> None:
    funcs, errors, proven = prove(case.source)
    self.assertEqual(_support.codes_and_lines(errors), case.errors,
                     "\n" + _support.describe(errors))
    self.assertEqual(proven, case.proven)
    promised = {f.name for f in funcs if f.requires or f.ensures}
    for name in case.runtime:
        self.assertIn(name, promised, f"'{name}' makes no promise")
        self.assertNotIn(name, proven)


class Cases(unittest.TestCase):
    """fixtures/prover/*.vel, one test per case."""


for _file in CASE_FILES:
    _support.add_case_tests(Cases, STAGE, _file, check_case)


class Reports(unittest.TestCase):

    def test_nothing_to_prove_empties_the_proven_set(self) -> None:
        funcs, records = build("fn plain(a: Int) -> Int {\n    return a + 1\n}")
        errors: list[Any]
        errors, proven = [], {"left over from another program"}
        check_proofs(funcs, records, errors, proven)
        self.assertEqual((errors, proven), ([], set()))

    def test_a_function_without_promises_is_never_listed(self) -> None:
        # a division is an obligation, but only a promise is "proven"
        _funcs, errors, proven = prove(
            "fn halve(n: Int) -> Int {\n    return n / 2\n}")
        self.assertEqual((errors, proven), ([], set()))

    def test_E700_shows_the_counterexample(self) -> None:
        _f, errors, _p = prove("fn bump(n: Int) -> Int\n"
                               "    ensures result > n\n{\n    return n\n}")
        self.assertRegex(errors[0].message,
                         r"'bump' ensures result > n - proven without running "
                         r"the program: n = -?\d+ gives result = -?\d+$")

    def test_E701_names_the_requires_and_the_caller(self) -> None:
        _f, errors, _p = prove(
            "fn half(n: Int) -> Int\n    requires n > 0\n{\n    return n\n}\n"
            "fn caller(n: Int) -> Int\n    requires n >= 0\n{\n"
            "    return half(n)\n}")
        self.assertEqual(errors[0].code, "E701")
        self.assertIn("'half' requires n > 0, but 'caller' can call it with "
                      "n = 0", errors[0].message)

    def test_E703_quotes_the_invariant_and_when_it_fails(self) -> None:
        source = _support.load_cases(STAGE, "loops.vel")[1].source
        _f, errors, _p = prove(source)
        self.assertIn("'invariant i > 0' when the loop starts in 'count'",
                      errors[0].message)

    def test_E705_names_the_position_and_the_length(self) -> None:
        _f, errors, _p = prove("fn last_bad(xs: List of Int) -> Int {\n"
                               "    return get(xs, length(xs))\n}")
        self.assertRegex(errors[0].message,
                         r"can reach position -?\d+, but the list has -?\d+ "
                         r"item\(s\)")

    def test_E706_names_the_divisor_that_is_zero(self) -> None:
        _f, errors, _p = prove("fn ratio(a: Int, b: Int) -> Int {\n"
                               "    return a / b\n}")
        self.assertIn("divide by zero: b = 0", errors[0].message)


class Budgets(unittest.TestCase):
    """SPEC.md 9.3: 120 seconds for a function that mentions Float and 3
    otherwise, either replaced for one run by --proof-timeout or
    SABLINE_PROOF_TIMEOUT."""

    def setUp(self) -> None:
        set_proof_timeout(None)
        self.addCleanup(set_proof_timeout, None)
        environment = mock.patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop(PROOF_TIMEOUT_ENV, None)

    def test_the_documented_defaults(self) -> None:
        self.assertEqual((PROOF_SECONDS, FLOAT_PROOF_SECONDS), (3.0, 120.0))
        self.assertEqual(proof_timeout_seconds(False), 3.0)
        self.assertEqual(proof_timeout_seconds(True), 120.0)

    def test_the_environment_replaces_both_and_the_flag_comes_first(self) -> None:
        os.environ[PROOF_TIMEOUT_ENV] = "7.5"
        self.assertEqual((proof_timeout_seconds(False),
                          proof_timeout_seconds(True)), (7.5, 7.5))
        set_proof_timeout(300)
        self.assertEqual((proof_timeout_seconds(False),
                          proof_timeout_seconds(True)), (300.0, 300.0))
        set_proof_timeout(None)
        self.assertEqual(proof_timeout_seconds(False), 7.5)

    def test_a_budget_is_a_number_of_seconds_greater_than_zero(self) -> None:
        for bad in (0, -1, "soon", float("inf"), float("nan")):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError) as caught:
                    set_proof_timeout(bad)
                self.assertTrue(re.search(r"greater than 0",
                                          str(caught.exception)))


if __name__ == "__main__":
    unittest.main()
