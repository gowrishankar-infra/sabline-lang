"""Stage 2, the parser: tokens into a syntax tree, by recursive descent.
"""
from .errors import SablineError
from .lexer import Token, fmt_fn_type, unescape
from .nodes import (
    Assign,
    BinOp,
    Block,
    Bool,
    Call,
    Check,
    Closure,
    ExprStmt,
    FailStmt,
    FieldGet,
    FloatNum,
    Function,
    If,
    Let,
    ListLit,
    MapLit,
    Neg,
    Not,
    Num,
    RecordDef,
    RecordLit,
    Return,
    Str,
    TryExpr,
    Var,
    While,
)
from typing import Any

# ---------------------------------------------------------------------------
# 3. PARSER — recursive descent, one function per grammar rule
# ---------------------------------------------------------------------------


# An expression's tree is walked recursively by every later stage (effect
# checker, type checker, prover, formatter). A pathological source - a chain
# of thousands of operators, or thousands of nested brackets - would build a
# tree deep enough to overflow one of those walks with a Python traceback
# rather than a clean error (fixed in 7.1.2). These caps are far above any
# real expression; past them the parser stops with E102. The compile
# pipeline also raises Python's recursion limit (load_program) so a tree up
# to these depths walks without trouble.
EXPR_CHAIN_LIMIT = 1000       # operators in one left-associative run
EXPR_NEST_LIMIT = 1000        # bracket / unary nesting depth
BLOCK_NEST_LIMIT = 4000       # blocks in blocks, and else-if chains (8.2):
                              # 3,000 deep runs on every leg; 12,000 did not

# E101's fixes for the two keywords a model most put where a value goes
# (evals/roundtrip, 8.7). agent_loop shows a model the first two fixes, so
# each list is two, most useful first. rt/crates/sabline-rt/src/parser.rs
# holds the same words, and the agreement gate compares them.
E101_OR_FAIL = (
    "to handle the failure here, write: check to_int(text) { ok n { ... } "
    "fail why { ... } }",
    "'or fail' goes only in a function's signature, after its return type "
    "- fn parse(text: Text) -> Int or fail - and inside such a function "
    "try to_int(text) passes a failure up; main cannot fail",
)
E101_INVARIANT = (
    "'invariant' is a clause of a loop, written after the loop's header and "
    "before its '{': while i < n invariant total >= 0 { ... }",
    "a promise about what a function returns is 'ensures', in its "
    "signature: fn f(n: Int) -> Int ensures result >= 0 { ... }",
)


class Parser:
    lambda_n = 0

    def __init__(self, tokens: list[Token]) -> None:
        self.lifted: list[Any] = []
        self.toks = tokens
        self.i = 0
        self._nest = 0            # current expression nesting depth (E102)
        self._blocks = 0          # current block nesting depth (E102)

    def _too_deep(self, line: int) -> Any:
        return SablineError("E102",
            "this expression nests, or chains operators, too deeply",
            line,
            fixes=["split it into smaller pieces with intermediate 'let' "
                   "bindings",
                   "a single expression this large is almost always a bug"])

    def _too_deep_block(self, line: int) -> Any:
        return SablineError("E102",
            f"blocks nest more than {BLOCK_NEST_LIMIT} deep here (an 'if', "
            f"'while', 'for' or 'else if' inside another)", line,
            fixes=["move the inner part into a function of its own",
                   "a program nested this deeply was almost always generated "
                   "by mistake"])

    def peek(self) -> Token:
        return self.toks[self.i]
    def next(self) -> Token:
        t = self.toks[self.i]
        self.i += 1
        return t

    def expect(self, kind: str, text: str | None = None) -> Token:
        t = self.peek()
        if t.kind != kind or (text is not None and t.text != text):
            want = text or kind.lower()
            raise SablineError("E100", f"expected '{want}' but found '{t.text or 'end of file'}'",
                              t.line, fixes=[f"insert '{want}' here"])
        return self.next()

    def parse_program(self) -> tuple[Any, ...]:
        funcs, records, imports = self.lifted, [], []
        while self.peek().kind != "EOF":
            t = self.peek()
            if t.kind == "KEYWORD" and t.text == "import":
                self.next()
                s = self.expect("STRING")
                alias = None
                if self.peek().kind == "IDENT" and self.peek().text == "as":
                    self.next()
                    alias = self.expect("IDENT").text
                imports.append(
                    (unescape(s.text[1:-1], s.line), t.line, alias))
            elif t.kind == "KEYWORD" and t.text == "record":
                records.append(self.parse_record())
            else:
                funcs.append(self.parse_function())
        return funcs, records, imports

    def parse_record(self) -> RecordDef:
        start = self.expect("KEYWORD", "record")
        name = self.expect("IDENT").text
        self.expect("OP", "{")
        fields = []
        while self.peek().text != "}":
            fname = self.expect("IDENT").text
            self.expect("OP", ":")
            fields.append((fname, self.parse_type()))
        self.expect("OP", "}")
        return RecordDef(name, fields, start.line)

    def parse_function(self) -> Function:
        start = self.expect("KEYWORD", "fn")
        name = self.expect("IDENT").text
        self.expect("OP", "(")
        params = []
        while self.peek().text != ")":
            pname = self.expect("IDENT").text
            self.expect("OP", ":")
            ptype = self.parse_type()
            params.append((pname, ptype))
            if self.peek().text == ",":
                self.next()
        self.expect("OP", ")")
        ret = None
        if self.peek().kind == "ARROW":
            self.next()
            ret = self.parse_type()
        effects: set[str] = set()
        type_vars: list[str] = []
        can_fail = False
        while True:                    # uses / for any / or fail, any order
            t2 = self.peek()
            if t2.kind == "KEYWORD" and t2.text == "uses":
                self.next()
                effects.add(self.expect("IDENT").text)
                while self.peek().text == ",":
                    self.next()
                    effects.add(self.expect("IDENT").text)
            elif t2.kind == "KEYWORD" and t2.text == "for":
                self.next()
                anykw = self.expect("IDENT")
                if anykw.text != "any":
                    raise SablineError("E100", "expected 'any' after 'for'",
                        anykw.line, fixes=["write: for any T"])
                type_vars.append(self.expect("IDENT").text)
                while self.peek().text == ",":
                    self.next()
                    type_vars.append(self.expect("IDENT").text)
            elif (t2.kind == "KEYWORD" and t2.text == "or"
                    and self.toks[self.i + 1].text == "fail"):
                self.next()
                self.next()
                can_fail = True
            else:
                break
        requires_: list[tuple[Any, int]] = []
        ensures_: list[tuple[Any, int]] = []
        while (self.peek().kind == "KEYWORD"
               and self.peek().text in ("requires", "ensures")):
            kw = self.next()
            clause = (self.parse_expr(), kw.line)
            (requires_ if kw.text == "requires" else ensures_).append(clause)
        body = self.parse_block()
        f = Function(name, params, ret, effects, requires_, ensures_,
                     body, start.line)
        f.can_fail = can_fail
        f.type_vars = type_vars
        return f

    def parse_lambda(self, start: Token) -> Any:
        """fn(x: Int) -> Bool { return x > 0 } as a value.

        Lifted to a real top-level function with a generated name, so
        every later stage (types, effects, proofs, native codegen) sees
        an ordinary function. Lambdas are pure, and a local they read from
        around them is captured as its value when the lambda is made
        (SPEC.md 12a): a snapshot, never a reference.
        """
        self.expect("OP", "(")
        params = []
        while self.peek().text != ")":
            pname = self.expect("IDENT").text
            self.expect("OP", ":")
            params.append((pname, self.parse_type()))
            if self.peek().text == ",":
                self.next()
        self.expect("OP", ")")
        if self.peek().text != "->":
            raise SablineError("E100",
                "a function value needs a result type", start.line,
                fixes=["write: fn(x: Int) -> Bool { return x > 0 }"])
        self.next()
        ret = self.parse_type()
        requires_: list[tuple[Any, int]] = []  # a function value can promise too
        ensures_: list[tuple[Any, int]] = []
        while (self.peek().kind == "KEYWORD"
               and self.peek().text in ("requires", "ensures")):
            kw = self.next()
            clause = (self.parse_expr(), kw.line)
            (requires_ if kw.text == "requires" else ensures_).append(clause)
        body = self.parse_block()
        Parser.lambda_n += 1
        name = f"fn#{Parser.lambda_n}"
        f = Function(name, params, ret, set(), requires_, ensures_,
                     body, start.line)
        f.can_fail = False
        f.type_vars = []
        f.is_lambda = True
        # names the body reads that it did not bind itself: candidates
        # for capture. Which are really locals is known only once the
        # surrounding function is type checked, so decide there.
        bound: set[str | None] = {p for p, _ in params}
        free = []

        def look(node: Any) -> None:
            if isinstance(node, Let) or isinstance(node, Assign):
                bound.add(node.name)
            if isinstance(node, Var) and node.name not in bound \
                    and node.name not in free:
                free.append(node.name)
            if isinstance(node, Check):
                bound.add(node.ok_name)
                bound.add(node.fail_name)

        import dataclasses as _dc

        def visit(n: Any) -> None:
            if isinstance(n, (list, tuple)):
                for x in n:
                    visit(x)
                return
            if not _dc.is_dataclass(n):
                return
            look(n)
            for fl in _dc.fields(n):
                visit(getattr(n, fl.name))

        visit(body)
        f.free_names = free  # type: ignore[attr-defined]  # set here, not a dataclass field, so a node's fields, repr and equality stay as they were
        self.lifted.append(f)
        return Closure(name, free, start.line)

    @staticmethod
    def flatten(stmts: list[Any]) -> list[Any]:
        out = []
        for s in stmts:
            if isinstance(s, Block):
                out.extend(Parser.flatten(s.stmts))
            else:
                out.append(s)
        return out

    def parse_block(self) -> list[Any]:
        self.expect("OP", "{")
        stmts = []
        # past BLOCK_NEST_LIMIT the parser stops with E102. Until 8.2 nothing
        # capped blocks: some thousands deep parsed, and then overflowed a
        # later stage's walk with a Python traceback
        self._blocks += 1
        if self._blocks > BLOCK_NEST_LIMIT:
            raise self._too_deep_block(self.peek().line)
        try:
            while self.peek().text != "}":
                stmts.append(self.parse_statement())
        finally:
            self._blocks -= 1
        self.expect("OP", "}")
        return Parser.flatten(stmts)

    def parse_statement(self) -> Any:
        t = self.peek()
        if t.kind == "KEYWORD" and t.text == "let":
            self.next()
            name = self.expect("IDENT").text
            ann = None
            if self.peek().text == ":":
                self.next()
                ann = self.parse_type()
            self.expect("OP", "=")
            return Let(name, self.parse_expr(), t.line, ann)
        if t.kind == "KEYWORD" and t.text == "return":
            self.next()
            if self.peek().text == "}":          # bare 'return' with no value
                return Return(None, t.line)
            return Return(self.parse_expr(), t.line)
        if t.kind == "KEYWORD" and t.text == "fail":
            self.next()
            return FailStmt(self.parse_expr(), t.line)
        if t.kind == "KEYWORD" and t.text == "check":
            self.next()
            subject = self.parse_expr()
            if isinstance(subject, TryExpr) or not isinstance(subject, Call):
                raise SablineError("E100",
                    "'check' needs a call to a function that can fail",
                    t.line, fixes=["write: check f(args) { ok v { ... } "
                                   "fail reason { ... } }"])
            self.expect("OP", "{")
            okkw = self.expect("IDENT")
            if okkw.text != "ok":
                raise SablineError("E100", "expected 'ok' arm first in check",
                    okkw.line, fixes=["write: ok value { ... }"])
            ok_name = None
            if self.peek().kind == "IDENT":
                ok_name = self.next().text
            ok_body = self.parse_block()
            self.expect("KEYWORD", "fail")
            fail_name = self.expect("IDENT").text
            fail_body = self.parse_block()
            self.expect("OP", "}")
            return Check(subject, t.line, ok_name, ok_body,
                         fail_name, fail_body)
        if t.kind == "KEYWORD" and t.text == "for":
            self.next()
            name = self.expect("IDENT").text
            inw = self.expect("IDENT")
            if inw.text != "in":
                raise SablineError("E100", "expected 'in' after the name",
                    inw.line, fixes=["write: for i in 0 to n { ... }",
                                     "or:    for item in xs { ... }"])
            start = self.parse_expr()
            if (self.peek().kind == "IDENT" and self.peek().text == "to"):
                self.next()                       # for i in a to b
                stop = self.parse_expr()
                invs = []
                while (self.peek().kind == "KEYWORD"
                       and self.peek().text == "invariant"):
                    kw = self.next()
                    invs.append((self.parse_expr(), kw.line))
                body = self.parse_block()
                step = Assign(name, BinOp("+", Var(name, t.line),
                                          Num(1), t.line), t.line)
                return Block([
                    Let(name, start, t.line, None),
                    While(BinOp("<", Var(name, t.line), stop, t.line),
                          list(body) + [step], t.line, invs),
                ], t.line)
            Parser.lambda_n += 1                  # for item in xs
            idx = f"for#{Parser.lambda_n}"
            invs = []
            while (self.peek().kind == "KEYWORD"
                   and self.peek().text == "invariant"):
                kw = self.next()
                invs.append((self.parse_expr(), kw.line))
            body = self.parse_block()
            step = Assign(idx, BinOp("+", Var(idx, t.line), Num(1),
                                     t.line), t.line)
            inner = [Let(name, Call("get", [start, Var(idx, t.line)],
                                    t.line), t.line, None)]
            return Block([
                Let(idx, Num(0), t.line, None),
                While(BinOp("<", Var(idx, t.line),
                            Call("length", [start], t.line), t.line),
                      inner + list(body) + [step], t.line, invs),
            ], t.line)
        if t.kind == "KEYWORD" and t.text == "while":
            self.next()
            cond = self.parse_expr()
            invs = []
            while (self.peek().kind == "KEYWORD"
                   and self.peek().text == "invariant"):
                kw = self.next()
                invs.append((self.parse_expr(), kw.line))
            body = self.parse_block()
            return While(cond, body, t.line, invs)
        if t.kind == "IDENT" and self.toks[self.i + 1].text == ".":
            j = self.i + 1                       # looks like p.x(.y)* = ...
            while (self.toks[j].text == "."
                   and self.toks[j + 1].kind == "IDENT"):
                j += 2
            if self.toks[j].text == "=":
                raise SablineError("E511",
                    "records cannot be changed in place", t.line,
                    fixes=["build a new one: let p2 = "
                           "Point(x: new_value, y: p.y)"])
        if t.kind == "IDENT" and self.toks[self.i + 1].text == "=":
            self.next()
            self.expect("OP", "=")
            return Assign(t.text, self.parse_expr(), t.line)
        if t.kind == "KEYWORD" and t.text == "if":
            self.next()
            cond = self.parse_expr()
            then = self.parse_block()
            other = []
            if self.peek().text == "else":
                self.next()
                if (self.peek().kind == "KEYWORD"
                        and self.peek().text == "if"):
                    # an else-if chain nests as blocks do
                    self._blocks += 1
                    if self._blocks > BLOCK_NEST_LIMIT:
                        raise self._too_deep_block(self.peek().line)
                    try:
                        other = [self.parse_statement()]   # else if chain
                    finally:
                        self._blocks -= 1
                else:
                    other = self.parse_block()
            return If(cond, then, other, t.line)
        return ExprStmt(self.parse_expr(), t.line)

    def parse_type(self) -> str:
        if self.peek().kind == "KEYWORD" and self.peek().text == "fn":
            self.next()
            self.expect("OP", "(")
            parts = []
            while self.peek().text != ")":
                parts.append(self.parse_type())
                if self.peek().text == ",":
                    self.next()
            self.expect("OP", ")")
            ret = None
            if self.peek().kind == "ARROW":
                self.next()
                ret = self.parse_type()
            return fmt_fn_type(parts, ret)
        t = self.expect("IDENT")
        if t.text == "Map":
            of = self.expect("IDENT")
            if of.text != "of":
                raise SablineError("E100", "expected 'of' after 'Map'",
                    of.line, fixes=["write map types like: Map of Text to Int"])
            key = self.expect("IDENT").text
            to = self.expect("IDENT")
            if to.text != "to":
                raise SablineError("E100", "expected 'to' after the key type",
                    to.line, fixes=["write map types like: Map of Text to Int"])
            return f"Map of {key} to " + self.parse_type()
        if t.text == "List":
            of = self.expect("IDENT")
            if of.text != "of":
                raise SablineError("E100", "expected 'of' after 'List'", of.line,
                                  fixes=["write list types like: List of Int"])
            return "List of " + self.parse_type()   # nesting allowed
        # an amount: Money of INR, or Money of C in a function generic in
        # its currency (4.3). 'Money' alone stays a name, so a program's
        # own record called Money means what it did - including one
        # followed by a field called 'of'.
        if (t.text == "Money" and self.peek().text == "of"
                and self.toks[self.i + 1].kind == "IDENT"
                and self.toks[self.i + 2].text != ":"):
            self.next()
            return "Money of " + self.next().text
        # a value that must not escape: Secret of Text, Secret of Int,
        # Secret of List of Text (5.1/6.0, SPEC.md 3.1). Like Money,
        # `Secret` alone stays a name, so a program's own record called
        # Secret means what it did.
        if (t.text == "Secret" and self.peek().text == "of"
                and self.toks[self.i + 1].kind == "IDENT"
                and self.toks[self.i + 2].text != ":"):
            self.next()
            inner = self.parse_type()
            if inner.startswith("Secret of "):
                raise SablineError("E562",
                    "a Secret of a Secret is the same secret; write "
                    f"{inner}", t.line,
                    fixes=[f"write {inner}"])
            return "Secret of " + inner
        return t.text

    # expressions: or -> and -> not -> comparison -> add/sub -> mul/div -> atoms
    def parse_expr(self) -> Any:
        left = self.parse_and()
        n = 0
        while self.peek().kind == "KEYWORD" and self.peek().text == "or":
            op = self.next()
            n += 1
            if n > EXPR_CHAIN_LIMIT:
                raise self._too_deep(op.line)
            left = BinOp("or", left, self.parse_and(), op.line)
        return left

    def parse_and(self) -> Any:
        left = self.parse_not()
        n = 0
        while self.peek().kind == "KEYWORD" and self.peek().text == "and":
            op = self.next()
            n += 1
            if n > EXPR_CHAIN_LIMIT:
                raise self._too_deep(op.line)
            left = BinOp("and", left, self.parse_not(), op.line)
        return left

    def parse_not(self) -> Any:
        t = self.peek()
        if t.kind == "KEYWORD" and t.text == "not":
            self.next()
            self._nest += 1
            if self._nest > EXPR_NEST_LIMIT:
                raise self._too_deep(t.line)
            try:
                return Not(self.parse_not(), t.line)
            finally:
                self._nest -= 1
        return self.parse_cmp()

    def parse_cmp(self) -> Any:
        left = self.parse_add()
        n = 0
        while self.peek().text in ("==", "!=", "<", ">", "<=", ">="):
            op = self.next()
            n += 1
            if n > EXPR_CHAIN_LIMIT:
                raise self._too_deep(op.line)
            left = BinOp(op.text, left, self.parse_add(), op.line)
        return left

    def parse_add(self) -> Any:
        left = self.parse_mul()
        n = 0
        while self.peek().text in ("+", "-"):
            op = self.next()
            n += 1
            if n > EXPR_CHAIN_LIMIT:
                raise self._too_deep(op.line)
            left = BinOp(op.text, left, self.parse_mul(), op.line)
        return left

    def parse_mul(self) -> Any:
        left = self.parse_postfix()
        n = 0
        while self.peek().text in ("*", "/", "%"):
            op = self.next()
            n += 1
            if n > EXPR_CHAIN_LIMIT:
                raise self._too_deep(op.line)
            left = BinOp(op.text, left, self.parse_postfix(), op.line)
        return left

    def parse_postfix(self) -> Any:
        e = self.parse_atom()
        while self.peek().text == ".":
            dot = self.next()
            fname = self.expect("IDENT").text
            e = FieldGet(e, fname, dot.line)
        return e

    def parse_atom(self) -> Any:
        self._nest += 1
        if self._nest > EXPR_NEST_LIMIT:
            raise self._too_deep(self.peek().line)
        try:
            return self._parse_atom()
        finally:
            self._nest -= 1

    def _parse_atom(self) -> Any:
        t = self.next()
        if t.kind == "KEYWORD" and t.text == "fn":
            return self.parse_lambda(t)
        if t.kind == "KEYWORD" and t.text == "try":
            inner = self.parse_postfix()
            if not isinstance(inner, Call):
                raise SablineError("E100",
                    "'try' needs a call to a function that can fail",
                    t.line, fixes=["write: try f(args)"])
            return TryExpr(inner, t.line)
        if t.text == "-":                      # negative numbers: -7, -x
            return Neg(self.parse_postfix(), t.line)
        if t.text == "{":                      # map literal: {"a": 1}
            entries = []
            while self.peek().text != "}":
                k = self.parse_expr()
                self.expect("OP", ":")
                entries.append((k, self.parse_expr()))
                if self.peek().text == ",":
                    self.next()
            self.expect("OP", "}")
            return MapLit(entries, t.line)
        if t.text == "[":                      # list literal: [1, 2, 3]
            items = []
            while self.peek().text != "]":
                items.append(self.parse_expr())
                if self.peek().text == ",":
                    self.next()
            self.expect("OP", "]")
            return ListLit(items, t.line)
        if t.kind == "NUMBER":
            try:
                return Num(int(t.text))
            except ValueError:
                # past the digits Python converts (4300 by default); a
                # traceback until 8.2
                raise SablineError(
                    "E407", f"this whole number has {len(t.text)} digits "
                    f"(whole numbers go from -9223372036854775808 to "
                    f"9223372036854775807)", t.line,
                    fixes=["write a smaller number"])
        if t.kind == "FLOAT":
            return FloatNum(float(t.text))
        if t.kind == "STRING":
            return Str(unescape(t.text[1:-1], t.line))
        if t.kind == "KEYWORD" and t.text in ("true", "false"):
            return Bool(t.text == "true")
        if t.text == "(":
            e = self.parse_expr()
            self.expect("OP", ")")
            return e
        if t.kind == "IDENT":
            if (self.peek().text == "." and
                    self.toks[self.i + 1].kind == "IDENT" and
                    self.toks[self.i + 2].text == "("):
                self.next()                        # '.'
                fname = self.next().text           # function in namespace
                self.next()                        # '('
                qargs = []
                while self.peek().text != ")":
                    qargs.append(self.parse_expr())
                    if self.peek().text == ",":
                        self.next()
                self.expect("OP", ")")
                return Call(f"{t.text}.{fname}", qargs, t.line)
            if (self.peek().text == "("
                    and self.toks[self.i + 1].kind == "IDENT"
                    and self.toks[self.i + 2].text == ":"):
                self.next()                        # record literal
                fields = []
                while self.peek().text != ")":
                    fname = self.expect("IDENT").text
                    self.expect("OP", ":")
                    fields.append((fname, self.parse_expr()))
                    if self.peek().text == ",":
                        self.next()
                self.expect("OP", ")")
                return RecordLit(t.text, fields, t.line)
            if self.peek().text == "(":            # function call
                self.next()
                args = []
                while self.peek().text != ")":
                    args.append(self.parse_expr())
                    if self.peek().text == ",":
                        self.next()
                self.expect("OP", ")")
                return Call(t.text, args, t.line)
            return Var(t.text, t.line)
        raise self._unexpected(t)

    def _unexpected(self, t: Token) -> SablineError:
        """E101: a token that cannot start a value. A keyword is told what
        it is for, and never that a call was expected: told that, a model
        wrote `fail(...)` for six rounds (evals/roundtrip, 8.7).
        sabline-rt's parser says the same words (the agreement gate)."""
        before = self.toks[self.i - 2] if self.i >= 2 else None
        if (t.kind == "KEYWORD" and t.text == "fail" and before is not None
                and before.kind == "KEYWORD" and before.text == "or"):
            fixes = list(E101_OR_FAIL)
        elif t.kind == "KEYWORD" and t.text == "invariant":
            fixes = list(E101_INVARIANT)
        elif t.kind == "KEYWORD":
            fixes = [f"'{t.text}' is a keyword: it cannot be used as a "
                     f"value, and writing it as a call does not make it one"]
        else:
            fixes = ["expected a number, string, variable, or function call"]
        return SablineError("E101", f"unexpected '{t.text}'", t.line,
                            fixes=fixes)


def nice_name(name: str) -> str:
    """Lifted lambdas get generated names; show something readable."""
    if name.startswith("fn#"):
        return "this function value"
    return f"'{name}'"


def expr_str(e: Any) -> str:
    """Turn an AST expression back into readable source text (for errors)."""
    if isinstance(e, Num):
        return str(e.value)
    if isinstance(e, FloatNum):
        return str(e.value)
    if isinstance(e, Neg):
        return f"-{expr_str(e.value)}"
    if isinstance(e, TryExpr):
        return f"try {expr_str(e.value)}"
    if isinstance(e, Str):
        return f'"{e.value}"'
    if isinstance(e, Bool):
        return "true" if e.value else "false"
    if isinstance(e, Var):
        return e.name
    if isinstance(e, Call):
        return f"{e.name}({', '.join(expr_str(a) for a in e.args)})"
    if isinstance(e, BinOp):
        # keep the meaning: parenthesise operands that bind less tightly,
        # so (result + 1) * count never prints as result + 1 * count
        prec = {"or": 1, "and": 2,
                "==": 3, "!=": 3, "<": 3, ">": 3, "<=": 3, ">=": 3,
                "+": 4, "-": 4, "*": 5, "/": 5, "%": 5}
        here = prec.get(e.op, 6)

        def side(sub: Any, is_right: bool) -> str:
            text = expr_str(sub)
            if isinstance(sub, BinOp):
                there = prec.get(sub.op, 6)
                if there < here or (there == here and is_right):
                    return f"({text})"
            return text
        return f"{side(e.left, False)} {e.op} {side(e.right, True)}"
    if isinstance(e, Not):
        return f"not {expr_str(e.value)}"
    if isinstance(e, ListLit):
        return "[" + ", ".join(expr_str(i) for i in e.items) + "]"
    if isinstance(e, MapLit):
        return "{" + ", ".join(f"{expr_str(k)}: {expr_str(v)}"
                               for k, v in e.entries) + "}"
    if isinstance(e, FieldGet):
        return f"{expr_str(e.obj)}.{e.field}"
    if isinstance(e, RecordLit):
        return e.name + "(" + ", ".join(f"{f}: {expr_str(v)}" for f, v in e.fields) + ")"
    return "?"


def expr_vars(e: Any) -> set[str]:
    if isinstance(e, Var):
        return {e.name}
    if isinstance(e, Not):
        return expr_vars(e.value)
    if isinstance(e, Neg):
        return expr_vars(e.value)
    if isinstance(e, TryExpr):
        return expr_vars(e.value)
    if isinstance(e, ListLit):
        out = set()
        for i in e.items:
            out |= expr_vars(i)
        return out
    if isinstance(e, BinOp):
        return expr_vars(e.left) | expr_vars(e.right)
    if isinstance(e, MapLit):
        out = set()
        for k, v in e.entries:
            out |= expr_vars(k) | expr_vars(v)
        return out
    if isinstance(e, FieldGet):
        return expr_vars(e.obj)
    if isinstance(e, RecordLit):
        out = set()
        for _, v in e.fields:
            out |= expr_vars(v)
        return out
    if isinstance(e, Call):
        out = set()
        for a in e.args:
            out |= expr_vars(a)
        return out
    return set()
