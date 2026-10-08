"""Which loops provably end: syntactic, the same with and without the prover.
"""
from .nodes import (
    Assign,
    BinOp,
    Block,
    Bool,
    Call,
    Check,
    FailStmt,
    FieldGet,
    FloatNum,
    If,
    Let,
    Neg,
    Num,
    Return,
    Str,
    Var,
    While,
)
from .parser import expr_str
from .tables import BUILTINS, FALLIBLE_BUILTINS, builtin_reached
from typing import Any, cast


# ---------------------------------------------------------------------------
# Termination: which loops provably end
# ---------------------------------------------------------------------------

def _names_bound_in(stmts: Any) -> set[Any]:
    """Every name assigned or (re)bound anywhere inside these statements,
    nested blocks included."""
    out: set[Any] = set()

    def walk(node: Any) -> None:
        if isinstance(node, (list, tuple)):
            for x in node:
                walk(x)
        elif isinstance(node, (Assign, Let)):
            out.add(node.name)
            walk(node.value)
        elif isinstance(node, If):
            walk(node.then)
            walk(node.other)
        elif isinstance(node, While):
            walk(node.body)
        elif isinstance(node, Check):
            if node.ok_name:
                out.add(node.ok_name)
            out.add(node.fail_name)
            walk(node.ok_body)
            walk(node.fail_body)
        elif isinstance(node, Block):
            walk(node.stmts)
    walk(stmts)
    return out


def _limit_is_invariant(expr: Any, bound: set[Any], table: dict[Any, Any] | None) -> bool:
    """A loop limit counts as unchanging when it mentions no name the body
    binds and calls only functions that read their arguments and touch
    nothing. Anything the analysis does not recognise makes it False."""
    if isinstance(expr, (Num, FloatNum, Str, Bool)):
        return True
    if isinstance(expr, Var):
        return expr.name not in bound
    if isinstance(expr, Neg):
        return _limit_is_invariant(expr.value, bound, table)
    if isinstance(expr, BinOp):
        return (expr.op in ("+", "-", "*", "/", "%")
                and _limit_is_invariant(expr.left, bound, table)
                and _limit_is_invariant(expr.right, bound, table))
    if isinstance(expr, FieldGet):
        return _limit_is_invariant(expr.obj, bound, table)
    if isinstance(expr, Call):
        # a builtin counts when the BUILTINS table says it has no
        # effects and it cannot fail (`length`, `split`, `keys`, ...);
        # a user function when it declares no effects and cannot fail
        reached = builtin_reached(expr.name, table)
        builtin = BUILTINS.get(reached) if reached else None
        if builtin is not None:
            pure = (not builtin["effects"]
                    and reached not in FALLIBLE_BUILTINS)
        else:
            fn = (table or {}).get(expr.name)
            pure = fn is not None and not fn.effects and not fn.can_fail
        return pure and all(_limit_is_invariant(a, bound, table)
                            for a in expr.args)
    return False


BAD = object()


def _steps_along_paths(stmts: Any, v: str, op: str) -> set[Any] | object:
    """The number of one-step moves of v on every path that runs to the
    end of stmts, as a set ({1} is what a terminating loop needs), or
    BAD when v is touched in any other way. A path that leaves through
    `return` or `fail` leaves the loop too, so it drops out of the set.
    """
    want = "+" if op in ("<", "<=") else "-"
    counts = {0}
    for st in stmts:
        if isinstance(st, Assign) and st.name == v:
            val = st.value
            if not (isinstance(val, BinOp) and val.op == want
                    and isinstance(val.left, Var) and val.left.name == v
                    and isinstance(val.right, Num) and val.right.value == 1):
                return BAD
            counts = {c + 1 for c in counts}
        elif isinstance(st, Let) and st.name == v:
            return BAD
        elif isinstance(st, (Return, FailStmt)):
            return set()                      # every path here has left
        elif isinstance(st, If):
            a = _steps_along_paths(st.then, v, op)
            b = _steps_along_paths(st.other, v, op)
            if a is BAD or b is BAD:
                return BAD
            counts = {c + x for c in counts
                      for x in (cast(set[int], a) | cast(set[int], b))}
        elif isinstance(st, Check):
            if v in (st.ok_name, st.fail_name):
                return BAD
            a = _steps_along_paths(st.ok_body, v, op)
            b = _steps_along_paths(st.fail_body, v, op)
            if a is BAD or b is BAD:
                return BAD
            counts = {c + x for c in counts
                      for x in (cast(set[int], a) | cast(set[int], b))}
        elif isinstance(st, While):
            if v in _names_bound_in(st.body):
                return BAD                    # moved a number of times
        elif isinstance(st, Block):
            inner = _steps_along_paths(st.stmts, v, op)
            if inner is BAD:
                return BAD
            counts = {c + x for c in counts
                      for x in cast(set[int], inner)}
        if any(c > 1 for c in counts):
            return BAD
    return counts


def _conjuncts(cond: Any) -> list[Any]:
    if isinstance(cond, BinOp) and cond.op == "and":
        return _conjuncts(cond.left) + _conjuncts(cond.right)
    return [cond]


FLIP = {"<": ">", "<=": ">=", ">": "<", ">=": "<="}


# ---- the third verdict (9.0): bounded by its input ---------------------------
#
# decisions/0006 section c, as amended 2026-10-08, and SPEC.md 9.5. A loop
# gets it only when its exit is keyed to the read's empty result:
# `read_line()` answers "" at the end of input and on every call after it,
# so a loop that leaves on any other text (`line == "quit"`) runs forever
# once its input does, and is not bounded by anything.

INPUT_BOUNDED = "input-bounded"


def _reads_a_line(expr: Any, table: dict[Any, Any] | None) -> bool:
    return (isinstance(expr, Call) and not expr.args
            and builtin_reached(expr.name, table) == "read_line")


def _length_of(expr: Any, name: str, table: dict[Any, Any] | None) -> bool:
    return (isinstance(expr, Call) and len(expr.args) == 1
            and builtin_reached(expr.name, table) == "length"
            and isinstance(expr.args[0], Var) and expr.args[0].name == name)


def _tests_empty(expr: Any, name: str,
                 table: dict[Any, Any] | None) -> bool | None:
    """True when `expr` tests `name` for empty, False when it tests it for
    not empty, None for anything else. The shapes are SPEC.md 9.5's, and
    no others: `r == ""`, `length(r) == 0`; `r != ""`, `length(r) > 0`,
    `length(r) != 0` - each with its sides either way round."""
    if not isinstance(expr, BinOp) or expr.op not in ("==", "!=", "<", ">"):
        return None
    turned = {"<": ">", ">": "<"}.get(expr.op, expr.op)
    for side, op, other in ((expr.left, expr.op, expr.right),
                            (expr.right, turned, expr.left)):
        if (isinstance(side, Var) and side.name == name
                and isinstance(other, Str) and other.value == ""):
            if op == "==":
                return True
            if op == "!=":
                return False
        if (_length_of(side, name, table) and isinstance(other, Num)
                and other.value == 0):
            if op == "==":
                return True
            if op in ("!=", ">"):
                return False
    return None


def _bindings_of(stmts: Any, name: str) -> list[Any]:
    """Every statement anywhere inside these that binds `name`, nested
    blocks and loops included - the statements `_names_bound_in` reads."""
    out: list[Any] = []

    def walk(node: Any) -> None:
        if isinstance(node, (list, tuple)):
            for x in node:
                walk(x)
        elif isinstance(node, (Assign, Let)):
            if node.name == name:
                out.append(node)
        elif isinstance(node, If):
            walk(node.then)
            walk(node.other)
        elif isinstance(node, While):
            walk(node.body)
        elif isinstance(node, Check):
            if name in (node.ok_name, node.fail_name):
                out.append(node)
            walk(node.ok_body)
            walk(node.fail_body)
        elif isinstance(node, Block):
            walk(node.stmts)
    walk(stmts)
    return out


def _bounded_by_input(loop: While,
                      table: dict[Any, Any] | None) -> tuple[Any, ...] | None:
    """The input-bounded verdict and its reason, or None. A statement of
    the body itself binds r to `read_line()` and nothing else in the body
    binds r, so every turn that reaches the end of the body reads a line;
    and either the condition (or an `and` conjunct of it) tests that r is
    not empty, or it is a flag f whose only assignment in the body is
    `f = false`, a statement of the arm of a later `if` of the body that
    is taken when r is empty."""
    body = loop.body
    for i, read in enumerate(body):
        if not (isinstance(read, (Let, Assign))
                and _reads_a_line(read.value, table)):
            continue
        r = read.name
        bound = _bindings_of(body, r)
        if len(bound) != 1 or bound[0] is not read:
            continue
        for c in _conjuncts(loop.cond):
            if _tests_empty(c, r, table) is False:
                return (INPUT_BOUNDED, f"every turn reads a line into "
                                       f"'{r}', and the loop leaves on the "
                                       f"first empty read")
            if not isinstance(c, Var):
                continue
            flags = _bindings_of(body, c.name)
            if not (len(flags) == 1 and isinstance(flags[0], Assign)
                    and isinstance(flags[0].value, Bool)
                    and flags[0].value.value is False):
                continue
            for later in body[i + 1:]:
                if not isinstance(later, If):
                    continue
                empty = _tests_empty(later.cond, r, table)
                arm = (later.then if empty is True else
                       later.other if empty is False else [])
                if any(s is flags[0] for s in arm):
                    return (INPUT_BOUNDED, f"every turn reads a line into "
                                           f"'{r}', and '{c.name}' is "
                                           f"cleared on the first empty "
                                           f"read")
    return None


def loop_termination(fn: Any, table: dict[Any, Any] | None = None) -> list[Any]:
    """For every loop in fn: {"line", "verdict", "why"}.

    verdict is "terminates" for exactly one shape, "input-bounded" (9.0)
    for a loop that leaves on the first empty `read_line()` - the shapes
    `_bounded_by_input` names, which only a loop the counter rule does not
    reach is asked about - and "unshown" for everything else. The
    counter's shape: the condition is, or has as an `and`
    conjunct, `v < E`, `v <= E`, `v > E` or `v >= E` (v on either
    side), where E mentions nothing the body binds and calls only pure
    functions, and every path through the body moves v by exactly one
    step toward E - `v = v + 1` for < and <=, `v = v - 1` for > and >= -
    with v assigned nowhere else in the body. A path that returns or
    fails leaves the loop and needs no step. Extra `and` conjuncts can
    only end the loop sooner; an `or` cannot, so it does not qualify.

    A `for` is a while loop by the time this runs (see the parser), and
    goes through the same rule: it qualifies unless the body assigns
    the counter or grows what the loop ranges over. This is purely
    syntactic and needs no solver, so it is the same with and without
    the prover installed.
    """
    out = []

    def judge(loop: While) -> tuple[Any, ...]:
        bound = _names_bound_in(loop.body)
        for c in _conjuncts(loop.cond):
            if not isinstance(c, BinOp) or c.op not in FLIP:
                continue
            for side, other, op in ((c.left, c.right, c.op),
                                    (c.right, c.left, FLIP[c.op])):
                if not isinstance(side, Var):
                    continue
                v = side.name
                if v not in bound:
                    continue                  # never moves: not a counter
                if not _limit_is_invariant(other, bound, table):
                    return ("unshown", f"the limit '{expr_str(other)}' "
                                       f"changes inside the loop")
                steps = _steps_along_paths(loop.body, v, op)
                if steps is BAD:
                    return ("unshown", f"'{v}' is not moved by exactly "
                                       f"one step toward the limit on "
                                       f"every path")
                if steps and steps != {1}:
                    return ("unshown", f"some path through the body "
                                       f"leaves '{v}' where it was")
                return ("terminates", f"'{v}' moves one step toward "
                                      f"'{expr_str(other)}' every turn")
        return ("unshown", "no counter walking toward a limit in the "
                           "loop's condition")

    def walk(node: Any) -> None:
        if isinstance(node, (list, tuple)):
            for x in node:
                walk(x)
        elif isinstance(node, While):
            verdict, why = judge(node)
            if verdict == "unshown":
                bounded = _bounded_by_input(node, table)
                if bounded is not None:
                    verdict, why = bounded
            out.append({"line": node.line, "verdict": verdict, "why": why})
            walk(node.body)
        elif isinstance(node, If):
            walk(node.then)
            walk(node.other)
        elif isinstance(node, Check):
            walk(node.ok_body)
            walk(node.fail_body)
        elif isinstance(node, Block):
            walk(node.stmts)
    walk(fn.body)
    return out
