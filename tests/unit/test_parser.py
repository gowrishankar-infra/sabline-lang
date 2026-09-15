"""Stage 2, the parser, alone: velaris.parser.Parser over the lexer's tokens.

The syntax tree of each construct (LLM.md "The whole syntax", SPEC.md 9
and 12a, ARCHITECTURE.md "Parser"): signatures with promises, `uses`,
`or fail` and `for any`; records; if / else if; while with invariants;
`for` rewritten to `while`; inline functions lifted to top-level
functions; check and try; list and map literals; precedence. And the
refusals: E100, E101, and E102 at the depth limits.
"""
import dataclasses
import json
import unittest

import _support
from velaris.errors import VelarisError
from velaris.lexer import lex
from velaris.nodes import (
    Assign, BinOp, Block, Call, Check, Closure, ExprStmt, FailStmt,
    FieldGet, FloatNum, If, Let, ListLit, MapLit, Neg, Not, Num,
    RecordLit, Return, Str, TryExpr, While,
)
from velaris.parser import EXPR_CHAIN_LIMIT, EXPR_NEST_LIMIT, Parser, expr_str
from typing import Any, Callable, Iterator, cast

STAGE = "parser"


def parse(source: str) -> Any:
    return Parser(lex(source)).parse_program()


def fixture_functions(name: str) -> dict[Any, Any]:
    funcs, _records, _imports = parse(_support.read_fixture(STAGE, name))
    return {f.name: f for f in funcs}


def expr(text: str) -> Any:
    """The tree of one expression."""
    funcs, _, _ = parse(f"fn probe() {{\n    return {text}\n}}")
    return funcs[-1].body[0].value


def sx(e: Any) -> str:
    """An expression with every operation in brackets: the tree, as text."""
    if isinstance(e, BinOp):
        return f"({sx(e.left)} {e.op} {sx(e.right)})"
    if isinstance(e, Not):
        return f"(not {sx(e.value)})"
    if isinstance(e, Neg):
        return f"(-{sx(e.value)})"
    if isinstance(e, TryExpr):
        return f"(try {sx(e.value)})"
    if isinstance(e, Call):
        return f"{e.name}({', '.join(sx(a) for a in e.args)})"
    if isinstance(e, FieldGet):
        return f"{sx(e.obj)}.{e.field}"
    if isinstance(e, ListLit):
        return "[" + ", ".join(sx(i) for i in e.items) + "]"
    if isinstance(e, MapLit):
        return "{" + ", ".join(f"{sx(k)}: {sx(v)}" for k, v in e.entries) + "}"
    if isinstance(e, RecordLit):
        return e.name + "(" + ", ".join(f"{n}: {sx(v)}"
                                        for n, v in e.fields) + ")"
    return expr_str(e)


def nodes_in(tree: Any) -> Iterator[Any]:
    if isinstance(tree, (list, tuple)):
        for x in tree:
            yield from nodes_in(x)
        return
    if not dataclasses.is_dataclass(tree):
        return
    yield tree
    for f in dataclasses.fields(tree):
        yield from nodes_in(getattr(tree, f.name))


def clauses(pairs: Any) -> list[Any]:
    return [(sx(e), line) for e, line in pairs]


class Signatures(unittest.TestCase):
    fns: dict[Any, Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.fns = fixture_functions("contracts.vel")

    def test_requires_and_ensures_in_order_with_their_lines(self) -> None:
        f = self.fns["discount"]
        self.assertEqual(f.params, [("price", "Int"), ("rate", "Int")])
        self.assertEqual((f.return_type, f.line), ("Int", 3))
        self.assertEqual(clauses(f.requires),
                         [("(price >= 0)", 4),
                          ("((rate >= 0) and (rate <= 100))", 5)])
        self.assertEqual(clauses(f.ensures),
                         [("(result >= 0)", 6), ("(result <= price)", 7)])
        self.assertEqual((f.effects, f.can_fail, f.type_vars),
                         (set(), False, []))

    def test_uses_names_each_effect(self) -> None:
        f = self.fns["greet"]
        self.assertEqual(f.effects, {"io", "fs"})
        self.assertIsNone(f.return_type)

    def test_or_fail(self) -> None:
        f = self.fns["parse_age"]
        self.assertTrue(f.can_fail)
        self.assertEqual(sx(f.body[0].value), "(try to_int(text))")

    def test_for_any_type_variables(self) -> None:
        f = self.fns["first"]
        self.assertEqual((f.type_vars, f.params, f.return_type),
                         (["T"], [("xs", "List of T")], "T"))
        self.assertEqual(clauses(f.requires), [("(length(xs) > 0)", 21)])

    def test_signature_clauses_in_any_order(self) -> None:
        f = self.fns["pick"]
        self.assertEqual(f.params, [("a", "Map of K to V"), ("b", "List of K")])
        self.assertEqual((f.return_type, f.can_fail, f.effects, f.type_vars),
                         ("List of V", True, {"io"}, ["K", "V"]))

    def test_bare_return(self) -> None:
        (stmt,) = self.fns["nothing"].body
        self.assertIsInstance(stmt, Return)
        self.assertEqual((stmt.value, stmt.line), (None, 31))


class Records(unittest.TestCase):
    records: dict[Any, Any]

    @classmethod
    def setUpClass(cls) -> None:
        _funcs, records, _ = parse(_support.read_fixture(STAGE, "types.vel"))
        cls.records = {r.name: r for r in records}

    def test_field_types_as_written(self) -> None:
        self.assertEqual(self.records["Holder"].fields, [
            ("grid", "List of List of Int"),
            ("index", "Map of Text to List of Int"),
            ("test", "fn(Int, Text) -> Bool"),
            ("sink", "fn(Int)"),
            ("price", "Money of INR"),
            ("key", "Secret of Text"),
            ("keys", "Secret of List of Text"),
            # 'Money' alone stays a name, even before a field called 'of'
            ("plain", "Money"),
            ("of", "Int"),
        ])
        self.assertEqual(self.records["Holder"].line, 1)

    def test_fields_need_no_line_breaks(self) -> None:
        # SPEC.md 2: whitespace only separates; LLM.md rule 11's refusal
        # is of commas (see refusals.json)
        self.assertEqual(self.records["Point"].fields,
                         [("x", "Int"), ("y", "Int")])

    def test_record_literal_and_field_reads(self) -> None:
        body = fixture_functions("literals.vel")["shapes"].body
        point = body[6].value
        self.assertIsInstance(point, RecordLit)
        self.assertEqual(sx(point), "Point(x: 1, y: (-2))")
        self.assertEqual(sx(body[7].value), "geo.area(p.x, p.y)")
        self.assertIsInstance(body[7].value.args[0], FieldGet)


class Statements(unittest.TestCase):
    fns: dict[Any, Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.fns = fixture_functions("control.vel")

    def test_else_if_is_an_if_in_the_else_branch(self) -> None:
        (top,) = self.fns["classify"].body
        self.assertEqual((sx(top.cond), top.line), ("(n < 0)", 2))
        self.assertEqual(top.then[0].value, Str("negative"))
        (inner,) = top.other
        self.assertIsInstance(inner, If)
        self.assertEqual((sx(inner.cond), inner.line), ("(n == 0)", 4))
        self.assertEqual(inner.then[0].value, Str("zero"))
        self.assertEqual(inner.other[0].value, Str("positive"))

    def test_if_without_else(self) -> None:
        self.assertEqual(self.fns["only_if"].body[0].other, [])

    def test_while_with_invariants(self) -> None:
        body = self.fns["count"].body
        self.assertEqual([type(s) for s in body], [Let, Let, While, Return])
        loop = body[2]
        self.assertEqual((sx(loop.cond), loop.line), ("(i < n)", 16))
        self.assertEqual(clauses(loop.invariants),
                         [("(total >= 0)", 17), ("(i <= n)", 18)])
        self.assertEqual([(type(s), s.name, sx(s.value)) for s in loop.body],
                         [(Assign, "total", "(total + i)"),
                          (Assign, "i", "(i + 1)")])

    def test_let_with_and_without_a_type(self) -> None:
        body = self.fns["count"].body
        self.assertEqual((body[0].name, body[0].ann, body[0].value),
                         ("i", None, Num(0)))
        self.assertEqual((body[1].name, body[1].ann), ("total", "Int"))

    def test_fail_statement(self) -> None:
        f = fixture_functions("check_try.vel")["parse_age"]
        fail = f.body[1].then[0]
        self.assertIsInstance(fail, FailStmt)
        self.assertEqual((sx(fail.value), fail.line),
                         ('("negative age: " + text)', 4))

    def test_expression_statement_and_assignment(self) -> None:
        body = fixture_functions("literals.vel")["shapes"].body
        self.assertIsInstance(body[8], Assign)
        self.assertEqual(sx(body[8].value), "push(xs, 4)")
        main = fixture_functions("lambdas.vel")["main"]
        self.assertIsInstance(main.body[2], ExprStmt)

    def test_imports_with_line_and_name(self) -> None:
        _f, _r, imports = parse(_support.read_fixture(STAGE, "literals.vel"))
        self.assertEqual(imports, [("std.vel", 1, None),
                                   ("lib/geo.vel", 2, "geo")])


class Literals(unittest.TestCase):
    body: list[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.body = fixture_functions("literals.vel")["shapes"].body

    def test_list_literals(self) -> None:
        self.assertEqual(sx(self.body[0].value), "[1, 2, 3]")
        nested = self.body[1].value
        self.assertEqual(sx(nested), "[[1], [2, 3], []]")
        self.assertEqual(nested.items[2].items, [])

    def test_map_literals(self) -> None:
        ages = self.body[2].value
        self.assertIsInstance(ages, MapLit)
        self.assertEqual(ages.entries, [(Str("gowri"), Num(30)),
                                        (Str("asha"), Num(41))])
        self.assertEqual(sx(self.body[3].value), '{1: "one", 2: "two"}')

    def test_empty_literals_keep_their_annotation(self) -> None:
        none, empty = self.body[4], self.body[5]
        self.assertEqual((none.ann, none.value.items), ("List of Int", []))
        self.assertEqual((empty.ann, empty.value.entries),
                         ("Map of Text to Int", []))

    def test_negative_number_is_a_negation(self) -> None:
        e = expr("-7")
        self.assertIsInstance(e, Neg)
        self.assertEqual(e.value, Num(7))

    def test_float_and_text_values(self) -> None:
        self.assertEqual(expr("1.5"), FloatNum(1.5))
        self.assertEqual(expr(r'"a\tb\"c"'), Str('a\tb"c'))

    def test_unknown_escape_in_text_is_E002(self) -> None:
        with self.assertRaises(VelarisError) as caught:
            parse('fn f() {\n    let t = "\\q"\n}')
        self.assertEqual((caught.exception.code, caught.exception.line),
                         ("E002", 2))


class ForLoops(unittest.TestCase):
    """ARCHITECTURE.md: for loops become while loops in the parser, and
    SPEC.md 9.5: `for i in a to b` is exclusive of b."""
    fns: dict[Any, Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.fns = fixture_functions("for_loops.vel")

    def test_range_loop_is_a_let_and_a_while(self) -> None:
        body = self.fns["sum_to"].body
        self.assertEqual([type(s) for s in body], [Let, Let, While, Return])
        start, loop = body[1], body[2]
        self.assertEqual((start.name, start.value, start.line), ("i", Num(0), 3))
        self.assertEqual(sx(loop.cond), "(i < n)")
        self.assertEqual(clauses(loop.invariants), [("(total >= 0)", 4)])
        step = loop.body[-1]
        self.assertIsInstance(step, Assign)
        self.assertEqual((step.name, sx(step.value)), ("i", "(i + 1)"))
        self.assertEqual(sx(loop.body[0].value), "(total + i)")

    def test_each_loop_walks_an_index(self) -> None:
        body = self.fns["sum_of"].body
        self.assertEqual([type(s) for s in body], [Let, Let, While, Return])
        index, loop = body[1].name, body[2]
        self.assertEqual(body[1].value, Num(0))
        self.assertEqual(sx(loop.cond), f"({index} < length(xs))")
        self.assertEqual(clauses(loop.invariants), [("(total >= 0)", 14)])
        item = loop.body[0]
        self.assertEqual((item.name, sx(item.value)),
                         ("x", f"get(xs, {index})"))
        self.assertEqual((loop.body[-1].name, sx(loop.body[-1].value)),
                         (index, f"({index} + 1)"))

    def test_index_name_is_one_a_program_cannot_write(self) -> None:
        index = self.fns["sum_of"].body[1].name
        with self.assertRaises(VelarisError):
            lex(index)

    def test_no_block_is_left_in_the_tree(self) -> None:
        for name, f in self.fns.items():
            with self.subTest(function=name):
                self.assertFalse(any(isinstance(n, Block)
                                     for n in nodes_in(f.body)))
        inner = self.fns["grid"].body[2].body
        self.assertEqual([type(s) for s in inner], [Let, While, Assign])


class InlineFunctions(unittest.TestCase):
    """ARCHITECTURE.md: inline functions are lifted into ordinary
    top-level functions; SPEC.md 12a: they may read locals around them."""
    funcs: list[Any]
    fns: dict[Any, Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.funcs, _, _ = parse(_support.read_fixture(STAGE, "lambdas.vel"))
        cls.fns = {f.name: f for f in cls.funcs}

    def lifted(self) -> list[Any]:
        return [f for f in self.funcs if f.is_lambda]

    def test_lifted_to_top_level_functions(self) -> None:
        self.assertEqual(len(self.lifted()), 2)
        self.assertEqual({"apply", "main"},
                         {f.name for f in self.funcs if not f.is_lambda})
        for f in self.lifted():
            with self.subTest(name=f.name):
                self.assertTrue(f.name.startswith("fn#"))
                self.assertEqual((f.effects, f.can_fail, f.type_vars),
                                 (set(), False, []))

    def test_use_site_is_a_closure_naming_the_lifted_function(self) -> None:
        clamp = self.fns["main"].body[1].value
        self.assertIsInstance(clamp, Closure)
        self.assertIn(clamp.name, {f.name for f in self.lifted()})
        lifted = self.fns[clamp.name]
        self.assertEqual((lifted.params, lifted.return_type, lifted.line),
                         ([("n", "Int")], "Int", 7))
        self.assertEqual(clauses(lifted.ensures), [("(result <= limit)", 8)])

    def test_names_read_from_around_it_are_capture_candidates(self) -> None:
        clamp = self.fns["main"].body[1].value
        self.assertEqual(clamp.free, ["limit"])
        inline = self.fns["main"].body[3].expr.args[0].args[0]
        self.assertIsInstance(inline, Closure)
        self.assertEqual(inline.free, [])

    def test_every_inline_function_gets_its_own_name(self) -> None:
        again, _, _ = parse(_support.read_fixture(STAGE, "lambdas.vel"))
        names = [f.name for f in self.lifted()] + \
            [f.name for f in again if f.is_lambda]
        self.assertEqual(len(names), len(set(names)))


class CheckAndTry(unittest.TestCase):
    fns: dict[Any, Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.fns = fixture_functions("check_try.vel")

    def test_check_with_both_arms(self) -> None:
        c = self.fns["main"].body[0]
        self.assertIsInstance(c, Check)
        self.assertEqual((sx(c.subject), c.line), ('parse_age("30")', 10))
        self.assertEqual((c.ok_name, c.fail_name), ("years", "why"))
        self.assertEqual(sx(c.ok_body[0].expr), "print(years)")
        self.assertEqual(sx(c.fail_body[0].expr), "print(why)")

    def test_ok_arm_without_a_name(self) -> None:
        c = self.fns["main"].body[1]
        self.assertIsNone(c.ok_name)
        self.assertEqual(sx(c.ok_body[0].expr), 'print("done")')

    def test_try_wraps_the_call(self) -> None:
        let = self.fns["parse_age"].body[0]
        self.assertIsInstance(let.value, TryExpr)
        self.assertIsInstance(let.value.value, Call)
        self.assertEqual((let.value.value.name, let.value.line), ("to_int", 2))


class Expressions(unittest.TestCase):

    def load(self, name: str) -> list[Any]:
        with open(_support.fixture(STAGE, name), encoding="utf-8") as f:
            return cast("list[Any]", json.load(f)["cases"])

    def test_precedence(self) -> None:
        for source, tree in self.load("precedence.json"):
            with self.subTest(source=source):
                self.assertEqual(sx(expr(source)), tree)

    def test_expr_str_keeps_the_meaning(self) -> None:
        for source, shown in self.load("expr_str.json"):
            with self.subTest(source=source):
                tree = expr(source)
                self.assertEqual(expr_str(tree), shown)
                self.assertEqual(sx(expr(shown)), sx(tree))


class Refusals(unittest.TestCase):
    """fixtures/parser/refusals.json, one test per entry."""

    def assert_refused(self, source: str, code: str, line: int) -> Any:
        with self.assertRaises(VelarisError) as caught:
            parse(source)
        e = caught.exception
        self.assertEqual((e.code, e.line), (code, line), e.message)
        return e

    def test_E100_says_what_it_expected_and_found(self) -> None:
        e = self.assert_refused("fn f(x: Int { return x }", "E100", 1)
        self.assertEqual(e.message, "expected 'ident' but found '{'")

    def test_E100_at_the_end_of_the_file_says_so(self) -> None:
        e = self.assert_refused("fn f(\n", "E100", 2)
        self.assertIn("found 'end of file'", e.message)

    def test_E101_names_the_token(self) -> None:
        e = self.assert_refused("fn f() {\n    let x = )\n}", "E101", 2)
        self.assertEqual(e.message, "unexpected ')'")


def _add_refusal_tests() -> None:
    with open(_support.fixture(STAGE, "refusals.json"), encoding="utf-8") as f:
        cases = json.load(f)["cases"]
    for case in cases:
        def test(self: Any, case: Any = case) -> None:
            self.assert_refused(case["source"], case["code"], case["line"])
        name = f"test_{case['code']}_{case['name']}"
        test.__name__ = name
        test.__doc__ = f"parser/refusals.json, '{case['name']}'"
        assert not hasattr(Refusals, name), name
        setattr(Refusals, name, test)


_add_refusal_tests()


class DepthLimits(unittest.TestCase):
    """E102 (7.1.2): an expression chaining more than EXPR_CHAIN_LIMIT
    operators, or nesting deeper than EXPR_NEST_LIMIT, is refused rather
    than walked into a Python traceback by a later stage."""

    def outcome(self, expression: str) -> Any:
        source = f"fn f(a: Int, b: Bool) -> Int {{\n    return {expression}\n}}"
        try:
            _support.on_big_stack(lambda: parse(source))
        except VelarisError as e:
            return e.code, e.line
        return "ok"

    def test_operator_chains_up_to_the_limit(self) -> None:
        for op, operand in (("+", "a"), ("*", "a"), ("==", "a"),
                            ("and", "b"), ("or", "b")):
            with self.subTest(op=op):
                at = f" {op} ".join([operand] * (EXPR_CHAIN_LIMIT + 1))
                over = f" {op} ".join([operand] * (EXPR_CHAIN_LIMIT + 2))
                self.assertEqual(self.outcome(at), "ok")
                self.assertEqual(self.outcome(over), ("E102", 2))

    def test_nesting_up_to_the_limit(self) -> None:
        # the innermost operand is a level too: EXPR_NEST_LIMIT - 1
        # brackets around a value parse, EXPR_NEST_LIMIT do not
        shapes: dict[str, Callable[[int], str]] = {
            "brackets": lambda d: "(" * d + "a" + ")" * d,
            "list literals": lambda d: "[" * d + "a" + "]" * d,
            "not": lambda d: "not " * d + "b",
            "minus": lambda d: "-" * d + "a",
        }
        for label, build in shapes.items():
            with self.subTest(shape=label):
                self.assertEqual(self.outcome(build(EXPR_NEST_LIMIT - 1)), "ok")
                self.assertEqual(self.outcome(build(EXPR_NEST_LIMIT)),
                                 ("E102", 2))


if __name__ == "__main__":
    unittest.main()
