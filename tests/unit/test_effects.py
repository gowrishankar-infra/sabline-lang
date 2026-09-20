"""Stage 4, the effect resolver, alone: sabline.effects.check_effects(funcs,
errors) on programs the lexer and parser build.

SPEC.md 7: a function may perform only the effects it declares, calling a
function needs everything it declares, and the eight effects are io, env,
fs, net, clock, rand, ffi and declassify. LLM.md's builtin list says which
effect each builtin needs (sabline.tables.BUILTINS is what the resolver
reads). SPEC.md 9.1 and 12a: promises and function values are pure.
SPEC.md 10.1: builtins and the program's own names (E204, give-way).
"""
import os
import unittest

import _support
from sabline.effects import check_effects
from sabline.lexer import lex
from sabline.parser import Parser
from sabline.tables import BUILTINS
from typing import Any

STAGE = "effects"

# SPEC.md 7, in its order.
SPEC_EFFECTS = ("io", "env", "fs", "net", "clock", "rand", "ffi", "declassify")

# LLM.md rule 1 and "Builtins", SPEC.md 7 and 3.1: the builtins that need
# an effect. Every other builtin is pure.
DOCUMENTED_EFFECTS = {
    "print": "io", "log": "io", "ask": "io", "args": "io",
    "read_line": "io", "exit_with": "io",
    "env": "env",
    "read_file": "fs", "read_file_secret": "fs", "write_file": "fs",
    "file_exists": "fs",
    "fetch": "net", "post": "net", "fetch_status": "net", "request": "net",
    "now": "clock", "random": "rand",
    "py": "ffi", "py_int": "ffi", "py_float": "ffi", "py_json": "ffi",
    "py_new": "ffi", "py_do": "ffi", "py_field": "ffi", "py_close": "ffi",
    "declassify": "declassify",
    # 8.5: a MAC under a Secret key is a way out of Secret, and a tool call
    # is an effect of its own (SPEC.md 3.1, 7)
    "hmac_sha256": "declassify", "hmac_sha256_chain": "declassify",
    "tool": "tool", "tool_secret": "tool",
}

# SPEC.md 10.1, and the Secret builtins of 6.0 (SPEC.md 3.1): added in
# 4.3 or later, so a program's own function of the name is allowed.
GIVE_WAY = ("money", "units_of", "with_units", "percent_of",
            "divide_or_fail", "text_of", "parse_money",
            "read_file_secret", "declassify",
            # 8.5 (SPEC.md 10.1)
            "sha256", "hex_encode", "hex_decode", "base64_encode",
            "base64_decode", "url_encode", "hmac_sha256",
            "hmac_sha256_chain", "tool", "tool_secret")


def parse(source: str) -> list[Any]:
    funcs: list[Any]
    funcs, _records, _imports = Parser(lex(source)).parse_program()
    return funcs


def effect_errors(funcs: Any) -> list[Any]:
    if isinstance(funcs, str):
        funcs = parse(funcs)
    errors: list[Any] = []
    check_effects(funcs, errors)
    return errors


def check_case(self: Any, case: Any) -> None:
    errors = effect_errors(case.source)
    if case.refused:
        self.assertTrue(errors, "the documents refuse this; nothing was "
                                "reported")
        return
    self.assertEqual(_support.codes_and_lines(errors), case.errors,
                     "\n" + _support.describe(errors))


class Cases(unittest.TestCase):
    """fixtures/effects/*.vel, one test per case."""


for _file in ("declared.vel", "purity.vel", "builtin_names.vel"):
    _support.add_case_tests(Cases, STAGE, _file, check_case)


class BuiltinEffects(unittest.TestCase):

    def test_each_builtin_needs_the_effect_documented_for_it(self) -> None:
        self.assertLessEqual(set(DOCUMENTED_EFFECTS), set(BUILTINS))
        for name in sorted(BUILTINS):
            want = DOCUMENTED_EFFECTS.get(name)
            with self.subTest(builtin=name, effect=want):
                errors = effect_errors(f"fn probe() {{\n    {name}()\n}}")
                if want is None:
                    self.assertEqual(errors, [], _support.describe(errors))
                    continue
                self.assertEqual(_support.codes_and_lines(errors),
                                 [("E300", 2)])
                self.assertIn(f"'{want}'" if name != "env" else want,
                              errors[0].message)

    def test_declaring_the_effect_is_enough(self) -> None:
        for name, effect in sorted(DOCUMENTED_EFFECTS.items()):
            with self.subTest(builtin=name):
                errors = effect_errors(
                    f"fn probe() uses {effect} {{\n    {name}()\n}}")
                self.assertEqual(errors, [], _support.describe(errors))

    def test_a_call_is_found_wherever_it_is_written(self) -> None:
        template = ("record R {\n    n: Int\n}\n"
                    "fn make_r() -> R uses io {\n    return R(n: 1)\n}\n"
                    "fn f(xs: List of Int) -> Int or fail {\n"
                    "    STATEMENT\n    return 0\n}\n")
        positions = {
            "if condition": ("if now() > 0 {\n    }", "clock"),
            "else branch": ("if true {\n    } else {\n        print(1)\n    }",
                            "io"),
            "while condition": ("while random(2) > 0 {\n    }", "rand"),
            "while body": ("while false {\n        print(1)\n    }", "io"),
            "check subject": ('check fetch("http://x") {\n        ok v {\n'
                              '        }\n        fail w {\n        }\n    }',
                              "net"),
            "check ok arm": ('check to_int("1") {\n        ok v {\n'
                             '            print(v)\n        }\n'
                             '        fail w {\n        }\n    }', "io"),
            "check fail arm": ('check to_int("1") {\n        ok v {\n'
                               '        }\n        fail w {\n'
                               '            print(w)\n        }\n    }', "io"),
            "fail reason": ("fail read_line()", "io"),
            "return value": ("return random(3)", "rand"),
            "let value": ("let t = now()", "clock"),
            "assignment": ("let t = 0\n    t = now()", "clock"),
            "list item": ("let ys = [now()]", "clock"),
            "map key": ("let m = {read_line(): 1}", "io"),
            "map value": ('let m = {"a": now()}', "clock"),
            "record field": ("let r = R(n: now())", "clock"),
            "field read": ("let n = make_r().n", "io"),
            "not": ('let b = not file_exists("x")', "fs"),
            "negation": ("let n = -now()", "clock"),
            "right of an operator": ("let n = 1 + random(2)", "rand"),
            "call argument": ("let n = length(read_line())", "io"),
            "try": ('let n = try fetch_status("http://x")', "net"),
            "expression statement": ("exit_with(1)", "io"),
        }
        for where, (statement, effect) in positions.items():
            with self.subTest(position=where):
                errors = effect_errors(template.replace("STATEMENT", statement))
                self.assertEqual([e.code for e in errors], ["E300"],
                                 _support.describe(errors))
                self.assertIn("'f'", errors[0].message)
                self.assertIn(f"'{effect}'", errors[0].message)


class Messages(unittest.TestCase):

    def test_E300_names_function_call_missing_effect_and_what_is_declared(self) -> None:
        errors = effect_errors('fn save(t: Text) uses io {\n'
                               '    write_file("out.txt", t)\n}')
        self.assertEqual(errors[0].message,
                         "function 'save' calls 'write_file' which needs "
                         "effect 'fs', but 'save' only declares 'uses io'")

    def test_E300_calls_a_function_without_uses_pure(self) -> None:
        errors = effect_errors("fn f() {\n    print(1)\n}")
        self.assertIn("declares no effects (it is pure)", errors[0].message)

    def test_env_message_is_the_one_documented(self) -> None:
        # LLM.md, the E300 row: "the message is exactly: env() now needs
        # 'uses env'"
        errors = effect_errors('fn f() uses io {\n    let k = env("K", "")\n}')
        self.assertEqual(errors[0].message, "env() now needs 'uses env'")

    def test_a_name_that_is_not_an_effect_is_answered_with_the_eight(self) -> None:
        errors = effect_errors("fn f() uses teleport {\n}")
        self.assertEqual(errors[0].code, "E300")
        self.assertIn("'teleport'", errors[0].message)
        for effect in SPEC_EFFECTS:
            self.assertIn(effect, errors[0].message)

    def test_errors_carry_the_function_s_file(self) -> None:
        funcs = parse("fn f() {\n    print(1)\n}")
        funcs[0].src_file = os.path.join("lib", "tools.vel")
        (error,) = effect_errors(funcs)
        self.assertEqual(error.file, os.path.join("lib", "tools.vel"))


class BuiltinNames(unittest.TestCase):

    def test_every_builtin_from_before_4_3_is_E204(self) -> None:
        for name in sorted(set(BUILTINS) - set(GIVE_WAY)):
            with self.subTest(builtin=name):
                errors = effect_errors(f"fn {name}() {{\n}}")
                self.assertEqual(_support.codes_and_lines(errors),
                                 [("E204", 1)])

    def test_builtins_from_4_3_on_give_way(self) -> None:
        for name in GIVE_WAY:
            with self.subTest(builtin=name):
                self.assertIn(name, BUILTINS)
                self.assertEqual(effect_errors(f"fn {name}() {{\n}}"), [])

    def test_the_standard_library_may_keep_builtin_names(self) -> None:
        funcs = parse("fn split(amount: Int) -> Int {\n    return amount\n}")
        funcs[0].src_file = os.path.join(_support.STDLIB, "money.vel")
        self.assertEqual(effect_errors(funcs), [])
        funcs[0].src_file = "money.vel"
        self.assertEqual([e.code for e in effect_errors(funcs)], ["E204"])

    def test_a_name_with_an_import_prefix_is_not_a_builtin_name(self) -> None:
        funcs = parse('fn get(url: Text) -> Text {\n    return url\n}')
        funcs[0].name = "http.get"       # what import "http.vel" as http gives
        self.assertEqual(effect_errors(funcs), [])


if __name__ == "__main__":
    unittest.main()
