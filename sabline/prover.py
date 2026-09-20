"""Stage 6, the prover: contracts translated to Z3 and proven before the
program runs, modularly across calls.
"""
import os
import sys

from . import state as _state
from . import naming
from .errors import SablineError
from .nodes import (
    Assign,
    BinOp,
    Bool,
    Call,
    Check,
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
    RecordLit,
    Return,
    Str,
    TryExpr,
    Var,
    While,
)
from .parser import expr_str, expr_vars, nice_name
from .tables import NEW_BUILTINS, ROUNDING, builtin_reached
from .loader import blame
from .values import OpaqueList, RecElem, RecListVal
from .wrappers import currency_generic, erase_wrappers
from .budget import _ascii_digits
from .effects import local_names_of
from .tables import INT_MAX, INT_MIN
from typing import Any, Callable, cast

# ---------------------------------------------------------------------------
# 4c. PROOF CHECKER (v0.8: modular) — proofs now COMPOSE across functions.
#     * When A calls B, the prover uses B's contract as a summary of B:
#       it assumes B's 'ensures' about the result, and PROVES that A always
#       satisfies B's 'requires' at the call site (error E701 if not).
#     * Sound because Sabline has no global state: a call cannot silently
#       change the caller's variables.
#     * Anything unprovable (loops, lists, text math) falls back silently
#       to runtime promise checks.
# ---------------------------------------------------------------------------


# ---- how long one proof may take --------------------------------------
# A query about Float is decided by bit-blasting - 64-bit values expanded
# into circuits of individual bits - and it is slow: refuting
# examples/fp_proof_bad.vel takes about fifteen seconds on an idle
# machine and several times that on a busy one. Every other query
# finishes in milliseconds. So a function that mentions Float gets two
# minutes and every other function three seconds.
#
# Either can be replaced for one run, when a proof needs longer or a CI
# leg needs to give up sooner:
#
#     sabline check f.vel --proof-timeout 300
#     SABLINE_PROOF_TIMEOUT=300 sabline check f.vel
#
# A proof that spends its budget without an answer is ABANDONED, and
# every report says so in those words. It is never counted as a proof
# that looked and found nothing wrong; docs/floats.md says why that
# distinction is the whole point.
FLOAT_PROOF_SECONDS = 120.0
PROOF_SECONDS = 3.0
PROOF_TIMEOUT_ENV = "SABLINE_PROOF_TIMEOUT"
PROVER_SEED_ENV = "SABLINE_PROVER_SEED"


def set_proof_timeout(seconds: Any) -> None:
    """Give every proof in this process `seconds` instead of the two
    defaults. None restores them. ValueError names what was wrong."""
    if seconds is None:
        _state._proof_timeout = None
        return
    _state._proof_timeout = _proof_seconds(seconds, "--proof-timeout")


def _proof_seconds(value: Any, where: str) -> float:
    try:
        s = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{where} needs a number of seconds greater "
                         f"than 0, as {where} 300")
    if not (s > 0) or s == float("inf"):
        raise ValueError(f"{where} needs a number of seconds greater "
                         f"than 0, as {where} 300")
    return s


def proof_timeout_env() -> float | None:
    """SABLINE_PROOF_TIMEOUT, or None when it is unset or unusable."""
    env = naming.env(PROOF_TIMEOUT_ENV)
    if not env:
        return None
    try:
        return _proof_seconds(env, PROOF_TIMEOUT_ENV)
    except ValueError:
        return None          # said once by check_proofs, not per query


def proof_timeout_seconds(float_heavy: bool) -> float:
    """What one query gets, in seconds: the flag, then the environment,
    then the default for its kind."""
    if _state._proof_timeout is not None:
        return _state._proof_timeout
    from_env = proof_timeout_env()
    if from_env is not None:
        return from_env
    return FLOAT_PROOF_SECONDS if float_heavy else PROOF_SECONDS


def prover_seed() -> int | None:
    """Z3's random seed, from SABLINE_PROVER_SEED, or None for Z3's own.
    A knob for the tests (8.2): check_prover_lies.py proves its corpus
    under five seeds and holds that no verdict moves. A proof that needs
    a particular seed is not one; STABILITY.md does not cover this."""
    text = (naming.env(PROVER_SEED_ENV) or "").strip()
    return int(text) if text and _ascii_digits(text) else None


def _shown_name(z3_name: str) -> str:
    """A Z3 constant's name as a counterexample shows it: `xs#n`, the
    length the prover keeps for a list `xs`, is `length(xs)`."""
    if z3_name.endswith("#n"):
        return f"length({z3_name[:-2]})"
    return z3_name


# what sabline test --from-contracts makes witnesses for (8.3), and how large
WITNESS_TYPES = ("Int", "Bool", "Text", "Float", "List of Int", "List of Text")
WITNESS_TEXT_MOST = 64
WITNESS_LIST_MOST = 16


def check_proofs(funcs: list[Function], records: list[Any],
                 errors: list[Any], proven_out: set[Any] | None = None,
                 timeouts_out: list[Any] | None = None,
                 witnesses_out: dict[str, Any] | None = None,
                 witness_count: int = 20) -> None:
    # Nothing to prove means nothing to import. Loading z3 costs about
    # 350ms, and most programs - every hello world, every script whose
    # functions carry no promises - were paying it for no work at all.
    # Division, list reads and calls into contracted functions still
    # create obligations, so this asks about those too.
    def needs_proving(fn: Any) -> bool:
        if fn.requires or fn.ensures:
            return True
        found = [False]

        def look(node: Any) -> None:
            if isinstance(node, BinOp) and node.op in ("/", "%"):
                found[0] = True
            if isinstance(node, While) and node.invariants:
                found[0] = True
            if isinstance(node, Call):
                if node.name in ("get", "pop", "slice", "set_at"):
                    found[0] = True
                if builtin_reached(node.name, table_all) == "percent_of":
                    found[0] = True           # a divisor, like '/'
                callee = table_all.get(node.name)
                if callee is not None and (callee.requires or callee.ensures):
                    found[0] = True

        import dataclasses as _dc

        def visit(node: Any) -> None:
            if isinstance(node, (list, tuple)):
                for x in node:
                    visit(x)
                return
            if not _dc.is_dataclass(node):
                return
            look(node)
            for f in _dc.fields(node):
                visit(getattr(node, f.name))

        visit(fn.body)
        return found[0]

    table_all = {f.name: f for f in funcs}
    if not any(needs_proving(f) for f in funcs):
        if proven_out is not None:
            proven_out.clear()
        return

    try:
        import z3
    except ImportError:
        print("note: z3-solver is not installed, so promises are checked "
              "while running instead of proven beforehand "
              "(install with: pip install z3-solver)", file=sys.stderr)
        return

    if (_state._proof_timeout is None and naming.env(PROOF_TIMEOUT_ENV)
            and proof_timeout_env() is None):
        print(f"note: {PROOF_TIMEOUT_ENV}="
              f"{naming.env(PROOF_TIMEOUT_ENV)!r} is not a number of "
              f"seconds greater than 0, so the default proof budgets "
              f"apply ({FLOAT_PROOF_SECONDS:.0f}s with Float, "
              f"{PROOF_SECONDS:.0f}s without)", file=sys.stderr)

    table = {f.name: f for f in funcs}
    # an amount is its minor units here: the type checker has already
    # kept every currency apart, so what is left is Int arithmetic
    rec_fields = {r.name: [(f, erase_wrappers(t)) for f, t in r.fields]
                  for r in records}

    def provable_rec(name: str, seen: Any = frozenset()) -> bool:
        if name in seen:
            return False
        fs = rec_fields.get(name)
        if fs is None:
            return False
        return all(ft in ("Int", "Bool", "Float", "Text",
                          "List of Int")
                   or provable_rec(ft, seen | {name})
                   for _, ft in fs)

    class Unprovable(Exception):
        pass

    FELL_OFF = object()
    FAILED = object()
    saw_fp = [False]                   # FP queries earn a bigger budget

    def query_seconds() -> float:
        """What one query gets, in seconds."""
        return proof_timeout_seconds(saw_fp[0])

    def solver_budget() -> int:
        return int(query_seconds() * 1000)

    # 'unknown' has two meanings and they are nothing alike. Z3 says it
    # when the question is outside what it decides - and it says it when
    # the clock ran out, which is not an answer at all. Telling them
    # apart is the difference between "this cannot be proven, so it is
    # checked while running" and "nobody looked".
    ran_out = [False]                  # this function's clock ran out
    timed_out: dict[Any, Any] = {}               # function name -> what it got

    def verdict_of(solver: Any) -> Any:
        """solver.check(), remembering an answer that was a clock."""
        v = solver.check()
        if v == z3.unknown:
            try:
                why = solver.reason_unknown()
            except z3.Z3Exception:
                why = ""
            if "timeout" in why or "canceled" in why:
                ran_out[0] = True
                fn_ = current_fn[0]
                timed_out.setdefault(
                    fn_.name if fn_ is not None else "?",
                    {"name": fn_.name if fn_ is not None else "?",
                     "line": fn_.line if fn_ is not None else 0,
                     "file": (fn_.src_file if fn_ is not None else None),
                     "seconds": query_seconds(),
                     "float": bool(saw_fp[0])})
        return v
    counter = [0]

    class RecVal:
        """A symbolic record: one Z3 value per field."""
        def __init__(self, rname: str, fields: dict[Any, Any]) -> None:
            self.rname, self.fields = rname, fields

    class ListVal:
        """A symbolic list: a Z3 array of Ints plus a length. `total`,
        when the list was built here, is what its items add up to - or a
        function giving it, so a list nobody asks units_of about never
        pays for the sum."""
        def __init__(self, arr: Any, length: Any, total: Any = None) -> None:
            self.arr, self.length, self.total = arr, length, total

    class GridVal:
        """A symbolic list of lists: rows, row lengths, and how many."""
        def __init__(self, rows: Any, lens: Any, length: Any) -> None:
            self.rows, self.lens, self.length = rows, lens, length

    class MapVal:
        """A symbolic map: values, plus which keys are actually there."""
        def __init__(self, vals: Any, present: Any, key_t: Any, val_t: Any) -> None:
            self.vals, self.present = vals, present
            self.key_t, self.val_t = key_t, val_t

    MAP_SORTS = {"Int": lambda: z3.IntSort(), "Bool": lambda: z3.BoolSort(),
                 "Text": lambda: z3.StringSort()}
    CODE_AT = z3.Function("code_at", z3.StringSort(), z3.IntSort(),
                          z3.IntSort())
    SPLIT = z3.Function("split", z3.StringSort(), z3.StringSort(),
                        z3.ArraySort(z3.IntSort(), z3.StringSort()))
    SPLIT_N = z3.Function("split_count", z3.StringSort(),
                          z3.StringSort(), z3.IntSort())
    # Functions Z3 is told next to nothing about. A model's value for one is
    # not what the real split, upper, lower or code_at gives, so a
    # counterexample that uses one is not a counterexample (8.2: a correct
    # program was refused, E700 and E703, over split).
    UNINTERPRETED = ("split", "split_count", "upper", "lower", "code_at")
    # Every name the prover makes up for itself - a quantifier's variable,
    # a call's result, a loop's havoc value - starts with "!", and every
    # name it derives from one of the program's own ("xs#n", the length of
    # a list xs) holds "#". Neither character can appear in a Sabline
    # identifier ([A-Za-z_][A-Za-z0-9_]*), so no parameter, variable or
    # field can be the same Z3 constant as one of them. Until 8.1 these
    # were spelled "__g_result_1" and "xs__n", which a program could
    # write: a parameter named __g_result_1 was the same constant as the
    # result of the call g(...), and a record field named xs__n the same
    # as the length of its list field xs, and both made a false promise
    # come back proven (SECURITY.md challenge #1; advisory-prover-names.md).
    _st, _ss = z3.String("!split_t"), z3.String("!split_s")
    SPLIT_AXIOMS = [z3.ForAll([_st, _ss], SPLIT_N(_st, _ss) >= 1)]
    UPPER = z3.Function("upper", z3.StringSort(), z3.StringSort())
    LOWER = z3.Function("lower", z3.StringSort(), z3.StringSort())
    _t = z3.String("!case_t")
    CASE_AXIOMS = [                     # changing case keeps the length
        z3.ForAll([_t], z3.Length(UPPER(_t)) == z3.Length(_t)),
        z3.ForAll([_t], z3.Length(LOWER(_t)) == z3.Length(_t)),
    ]
    # units_of(xs) for a list the prover did not build - a parameter, a
    # loop's list, a call's result - is TOTAL(its array, its length),
    # a value Z3 is told nothing about except the three facts below,
    # stated about that list alone: nothing adds up to 0, and items that
    # are all >= 0 (all <= 0) add up to something >= 0 (<= 0). Each is a
    # theorem about a real sum. Stating them for every list at once, as
    # one axiom, made Z3 answer 'unknown' to questions it used to settle,
    # which would have cost refutations elsewhere in the same program.
    # A sum is still not defined by them, so a counterexample that
    # mentions TOTAL may be one no real list has: has_fresh says so.
    TOTAL = z3.Function("!total", z3.ArraySort(z3.IntSort(), z3.IntSort()),
                        z3.IntSort(), z3.IntSort())
    total_facts: list[Any] = []
    _total_seen: set[Any] = set()

    def list_total(lv: Any) -> Any:
        """What the items of a symbolic list add up to."""
        t = lv.total
        if t is None:
            if lv.arr.sort().range() != z3.IntSort():
                raise Unprovable()
            term = TOTAL(lv.arr, lv.length)
            key = str(term)
            if key not in _total_seen:
                _total_seen.add(key)
                k = z3.Int(f"!total_k{len(_total_seen)}")

                def every(cmp: Any, k: Any = k, lv: Any = lv) -> Any:
                    return z3.ForAll([k], z3.Implies(
                        z3.And(k >= 0, k < lv.length),
                        cmp(z3.Select(lv.arr, k))))

                total_facts.extend([
                    z3.Implies(lv.length <= 0, term == 0),
                    z3.Implies(every(lambda v: v >= 0), term >= 0),
                    z3.Implies(every(lambda v: v <= 0), term <= 0),
                ])
            return term
        if callable(t):
            t = lv.total = t()
        return t

    def new_solver() -> Any:
        """A solver that knows what is known about the sums seen so far."""
        s = z3.Solver()
        s.set("timeout", solver_budget())
        seed = prover_seed()
        if seed is not None:
            s.set("random_seed", seed)
        if total_facts:
            s.add(*total_facts)
        return s

    def mentions_total(e: Any) -> bool:
        if not z3.is_expr(e):
            return False
        if z3.is_app(e) and e.num_args() and \
                e.decl().name() == "!total":
            return True
        return any(mentions_total(c) for c in e.children())

    # The Money builtins the prover models, exactly as the interpreter
    # runs them. parse_money and divide_or_fail are modelled on the path
    # where they did not fail (money_fallible, below; SPEC.md 9.3);
    # text_of is not modelled.
    MONEY_Z3 = ("money", "units_of", "with_units", "percent_of")
    # a parameter or local named like one of them is called as itself
    money_shadowed = NEW_BUILTINS & set().union(
        *(local_names_of(f) for f in funcs))

    def money_z3(b: str, node: Any, env: Any, ctx: Any) -> Any:
        if b == "money":                  # the currency is in the type
            return to_z3(node.args[0], env, ctx)
        if b == "units_of":
            v = to_z3(node.args[0], env, ctx)
            if isinstance(v, ListVal):
                return list_total(v)
            if z3.is_int(v):
                return v
            raise Unprovable()
        if b == "with_units":
            to_z3(node.args[0], env, ctx)
            return to_z3(node.args[1], env, ctx)
        # percent_of: amount * numerator / denominator, rounded as named,
        # in the formulas round_ratio computes while running. Like '/',
        # it is translated only for a denominator shown positive.
        mode = node.args[3].value if isinstance(node.args[3], Str) else None
        if mode not in ROUNDING:
            raise Unprovable()
        a = to_z3(node.args[0], env, ctx)
        num = to_z3(node.args[1], env, ctx)
        den = to_z3(node.args[2], env, ctx)
        if not all(z3.is_int(x) for x in (a, num, den)):
            raise Unprovable()
        constant = z3.is_int_value(den) and den.as_long() > 0
        if ctx is not None:
            prove_nonzero(den, ctx, node.line, "/")
        if not constant and (ctx is None or not provably_positive(den, ctx)):
            raise Unprovable()
        return rounded(a * num, den, mode)

    def rounded(p: Any, den: Any, mode: str) -> Any:
        """p / den rounded as `mode` says, for den > 0: round_ratio, in
        Z3's integers. Z3's div and mod agree with Sabline's for a
        positive divisor, which is the only case translated."""
        q, r = p / den, p % den
        if mode == "down":                           # toward zero
            return z3.If(z3.Or(p >= 0, r == 0), q, q + 1)
        if mode == "half_up":                        # a half: away from 0
            return z3.If(2 * r > den, q + 1, z3.If(2 * r < den, q,
                         z3.If(p >= 0, q + 1, q)))
        return z3.If(2 * r > den, q + 1, z3.If(2 * r < den, q,  # half_even
                     z3.If(q % 2 == 0, q, q + 1)))

    def money_fallible(mb: str, node: Any, env: Any, ctx: Any) -> Any:
        """parse_money and divide_or_fail on the path where they did not
        fail. An amount parsed out of text is simply unknown; a division
        that did not fail is the exact rounding, when the divisor is
        shown positive (the other side of zero stays unknown)."""
        for a in node.args:
            try:
                to_z3(a, env, ctx)       # what is inside still gets checked
            except Unprovable:
                pass
        if mb == "divide_or_fail":
            mode = node.args[2].value if isinstance(node.args[2], Str) \
                else None
            try:
                a = to_z3(node.args[0], env, ctx)
                by = to_z3(node.args[1], env, ctx)
            except Unprovable:
                a = by = None
            if mode in ROUNDING and a is not None and z3.is_int(a) \
                    and z3.is_int(by) and provably_positive(by, ctx):
                return rounded(a, by, mode)
        counter[0] += 1
        return z3.Int(f"!{mb}.result{counter[0]}")

    def map_parts(t: str) -> tuple[Any, ...] | None:
        """('Map of Text to Int') -> ('Text', 'Int') if both are modelable."""
        if not t.startswith("Map of "):
            return None
        key, sep, val = t[len("Map of "):].partition(" to ")
        if not sep or key not in MAP_SORTS or val not in MAP_SORTS:
            return None
        return key, val

    def mk_map(name: str, t: str) -> Any:
        parts = map_parts(t)
        if parts is None:
            return None
        key_t, val_t = parts
        ks, vs = MAP_SORTS[key_t](), MAP_SORTS[val_t]()
        return MapVal(z3.Array(name, ks, vs),
                      z3.Array(name + "#has", ks, z3.BoolSort()),
                      key_t, val_t)

    def mk(name: str, t: str) -> Any:
        if t == "Int":
            return z3.Int(name)
        if t == "Float":
            saw_fp[0] = True
            return z3.FP(name, z3.Float64())
        if t == "Text":
            return z3.String(name)
        return z3.Bool(name)

    def mk_rec(prefix: str, rname: str) -> "RecVal":
        out = {}
        for f, ft in rec_fields[rname]:
            if ft in ("Int", "Bool", "Float", "Text"):
                out[f] = mk(f"{prefix}.{f}", ft)
            elif ft == "List of Int":
                arr = z3.Array(f"{prefix}.{f}", z3.IntSort(), z3.IntSort())
                out[f] = ListVal(arr, z3.Int(f"{prefix}.{f}#n"))
            else:
                out[f] = mk_rec(f"{prefix}.{f}", ft)
        return RecVal(rname, out)

    def symbolic(v: Any) -> bool:
        """Whether Python's operators on `v` mean what Sabline's do: a Z3
        expression, or a plain constant. A MapVal, GridVal, ListVal,
        RecVal, RecListVal or OpaqueList is not - == on two of them asks
        whether they are the same Python object (8.3)."""
        return z3.is_expr(v) or isinstance(v, (bool, int, float, str))

    def rec_eq(l: "RecVal", r: "RecVal") -> Any:  # noqa: E741
        parts = []
        for f, ft in rec_fields[l.rname]:
            a, b = l.fields[f], r.fields[f]
            if isinstance(a, RecVal) and isinstance(b, RecVal):
                parts.append(rec_eq(a, b))
            elif isinstance(a, ListVal) and isinstance(b, ListVal):
                # a List of Int field: as == on two lists, below
                parts.append(z3.And(a.arr == b.arr, a.length == b.length))
            elif symbolic(a) and symbolic(b) and not (z3.is_fp(a)
                                                      or z3.is_fp(b)):
                parts.append(a == b)
            else:
                # A Float field is left to runtime (8.3). A run compares
                # two records by Python's == over their fields, which
                # calls one NaN equal to itself and two NaNs made apart
                # unequal - neither IEEE's rule (fpEQ) nor Z3's `=`, and a
                # proof under either could be false.
                raise Unprovable()
        return z3.And(*parts) if parts else z3.BoolVal(True)

    def fresh(t: str, base: str) -> Any:
        counter[0] += 1
        return mk(f"!{base}.result{counter[0]}", t)

    class Ctx:
        """Per-path proof state: path conditions + facts assumed so far.
        param_assum holds only facts about the caller's own parameters
        (never about summarized call results), so violations proven from
        it alone are guaranteed real - never false alarms."""
        def __init__(self, conds: Any, assum: Any, param_assum: Any, caller: Any) -> None:
            self.conds, self.assum = conds, assum
            self.param_assum, self.caller = param_assum, caller

        def fork(self, extra: Any) -> Any:
            return Ctx(self.conds + [extra], list(self.assum),
                       list(self.param_assum), self.caller)

    def has_fresh(e: Any) -> bool:
        """Does this Z3 expression mention a summarized/havoc value?"""
        if isinstance(e, RecVal):
            return any(has_fresh(v) for v in e.fields.values())
        if isinstance(e, ListVal):
            return has_fresh(e.arr) or has_fresh(e.length)
        if isinstance(e, OpaqueList):
            return has_fresh(e.length)
        if isinstance(e, RecListVal):
            return has_fresh(e.length) or any(
                has_fresh(a) for a in e.arrays.values())
        if isinstance(e, RecElem):
            return has_fresh(e.idx) or has_fresh(e.src.length)
        if z3.is_app(e) and e.num_args() and \
                e.decl().name() == "!total":
            return True              # a sum Z3 was never told the value of
        if isinstance(e, MapVal):
            return has_fresh(e.vals) or has_fresh(e.present)
        if isinstance(e, GridVal):
            return (has_fresh(e.rows) or has_fresh(e.lens)
                    or has_fresh(e.length))
        if z3.is_app(e) and e.num_args() and \
                e.decl().name() in UNINTERPRETED:
            return True              # a model of it is not the real one
        if z3.is_const(e) and e.decl().name().startswith("!"):
            return True
        return any(has_fresh(c) for c in e.children())

    def uninterpreted_in(e: Any) -> bool:
        """Does this Z3 expression apply a function in UNINTERPRETED?"""
        if not z3.is_expr(e):
            return False
        if z3.is_app(e) and e.num_args() and \
                e.decl().name() in UNINTERPRETED:
            return True
        return any(uninterpreted_in(c) for c in e.children())

    def show_val(name: Any, v: Any, model: Any) -> str:
        # Printed after the verdict is reached, and never part of it. A
        # value the model cannot name - an argument the prover did not
        # translate, such as put(...) of a map - is shown as <unknown>.
        # Until 8.2.1 it reached model.eval(None), and the command ended
        # in an AttributeError traceback instead of its E701.
        def shown(e: Any) -> str:
            if e is None:
                return "<unknown>"
            try:
                return str(model.eval(e, model_completion=True))
            except (z3.Z3Exception, AttributeError, TypeError):
                return "<unknown>"

        if isinstance(v, RecVal):
            def field_text(f: Any, x: Any) -> Any:
                if isinstance(x, RecVal):
                    return show_val(f, x, model).split(" = ", 1)[-1]
                if isinstance(x, ListVal):
                    return f"{f}: a list of {shown(x.length)}"
                if isinstance(x, MapVal):
                    return f"{f}: a map"
                return f"{f}: {shown(x)}"
            inner = ", ".join(field_text(f, x) for f, x in v.fields.items())
            return f"{name} = {v.rname}({inner})"
        if isinstance(v, ListVal):
            return f"length({name}) = {shown(v.length)}"
        if isinstance(v, MapVal):
            return f"{name} = a map"        # keys are symbolic here
        if isinstance(v, GridVal):
            return f"length({name}) = {shown(v.length)}"
        if isinstance(v, (RecListVal, OpaqueList)):
            # a list of records, or one whose items are not modelled: its
            # length is what the prover knows (8.2; printing it crashed)
            return f"length({name}) = {shown(v.length)}"
        return f"{name} = {shown(v)}"

    def bind_params(fnB: Function, args_z3: list[Any]) -> dict[Any, Any]:
        return {pname: a for (pname, _), a in zip(fnB.params, args_z3)}

    def check_requires_at(fnB: Any, args_z3: Any, ctx: Any, line: Any) -> None:
        """Prove the caller always satisfies fnB's requires here (E701)."""
        def names_in(e: Any, out: Any = None) -> Any:
            if out is None:
                out = set()
            if isinstance(e, Var):
                out.add(e.name)
            import dataclasses as _dc
            if _dc.is_dataclass(e):
                for f in _dc.fields(e):
                    v = getattr(e, f.name)
                    if isinstance(v, (list, tuple)):
                        for x in v:
                            names_in(x, out)
                    else:
                        names_in(v, out)
            return out

        def conjuncts(e: Any) -> Any:
            """a and b and c -> [a, b, c], so one untranslatable part
            does not throw away the checkable ones. A single length()
            over a record list used to mask a divisor > 0 sitting right
            next to it."""
            if isinstance(e, BinOp) and e.op == "and":
                return conjuncts(e.left) + conjuncts(e.right)
            return [e]

        parts = [p for r_expr, _ in fnB.requires
                 for p in conjuncts(r_expr)]
        bound = bind_params(fnB, [a for a in args_z3])
        for r_expr in parts:
            names = names_in(r_expr)
            involved = [a for (pname, _), a in zip(fnB.params, args_z3)
                        if pname in names]
            if any(a is None for a in involved):
                continue        # this conjunct mentions an unknown
            try:
                need = to_z3(r_expr, bound, None)
            except Unprovable:
                continue
            if any(a is not None and has_fresh(a) for a in involved) or \
                    any(has_fresh(c) for c in ctx.conds) or has_fresh(need):
                continue        # could be a false alarm; runtime will guard
            solver = new_solver()
            solver.add(*ctx.param_assum)
            solver.add(*ctx.conds)
            solver.add(z3.Not(need))
            if verdict_of(solver) == z3.sat:
                m = solver.model()
                vals = ", ".join(
                    show_val(pname, a, m)
                    for (pname, _), a in zip(fnB.params, args_z3))
                raise SablineError("E701",
                    f"this call can break a promise: '{fnB.name}' requires "
                    f"{expr_str(r_expr)}, but '{ctx.caller}' can call it "
                    f"with {vals} - proven without running the program",
                    line,
                    fixes=["make sure the value meets the promise before "
                           "calling",
                           "or strengthen the caller's own 'requires' to "
                           "rule this out"])

    def predicate_formula(pfn: Function, val: Any) -> Any:
        """Translate a predicate's body into 'returns true' as a Z3
        formula over val. Only simple pure predicates qualify: one Int
        parameter, Bool result, no loops, no calls, no failure. An
        amount is an Int parameter here, whatever its currency."""
        if (pfn.effects or pfn.can_fail
                or (pfn.type_vars and not currency_generic(pfn))
                or len(pfn.params) != 1
                or erase_wrappers(pfn.params[0][1]) != "Int"
                or pfn.return_type != "Bool"):
            raise Unprovable()

        def paths(stmts: Any, penv: Any, conds: Any) -> Any:
            out = []
            for i, s in enumerate(stmts):
                if isinstance(s, (Let, Assign)):
                    penv = dict(penv)
                    penv[s.name] = to_z3(s.value, penv, None)
                elif isinstance(s, Return):
                    out.append((conds, to_z3(s.value, penv, None)))
                    return out
                elif isinstance(s, If):
                    c = to_z3(s.cond, penv, None)
                    rest = stmts[i + 1:]
                    out += paths(s.then + rest, dict(penv), conds + [c])
                    out += paths(s.other + rest, dict(penv),
                                 conds + [z3.Not(c)])
                    return out
                else:
                    raise Unprovable()  # loops etc.: too clever to inline
            raise Unprovable()          # fell off without returning
        branches = paths(pfn.body, {pfn.params[0][0]: val}, [])
        return z3.Or(*[z3.And(*(cs + [r])) if cs else r
                       for cs, r in branches])

    def summarize_call(node: Call, env: Any, ctx: Any, allow_fail: bool = False) -> Any:
        """Model a call to a pure user function by its contract."""
        if node.name not in money_shadowed and builtin_reached(
                node.name, table) in ("parse_money", "divide_or_fail"):
            if not allow_fail or ctx is None:
                raise Unprovable()
            return money_fallible(cast(str, builtin_reached(node.name, table)), node,
                                  env, ctx)
        fnB = table.get(node.name)

        def summarizable(t: Any) -> Any:
            t = erase_wrappers(t)
            return t in ("Int", "Bool", "Float", "Text") or (
                map_parts(t) is not None) or (
                t in rec_fields and provable_rec(t))

        # a list of amounts comes back as a fresh list whose length and
        # sum the callee's promises describe (4.3) - how money.split's
        # promises reach its caller. Other lists still do not: summarizing
        # them would move verdicts of programs written before it.
        ret_t = (fnB.return_type or "") if fnB is not None else ""
        amounts_back = ret_t.startswith("List of Money of ")
        if (fnB is None or fnB.effects
                or (fnB.type_vars and not currency_generic(fnB))
                or (fnB.can_fail and not allow_fail)
                or not (summarizable(ret_t) or amounts_back)
                or any(not summarizable(pt) for _, pt in fnB.params)):
            raise Unprovable()
        args_z3 = [to_z3(a, env, ctx) for a in node.args]
        check_requires_at(fnB, args_z3, ctx, node.line)
        if amounts_back:
            counter[0] += 1
            base = f"!{fnB.name}.result{counter[0]}"
            rv: Any = ListVal(z3.Array(base, z3.IntSort(), z3.IntSort()),
                         z3.Int(base + "#n"))
            ctx.assum.append(rv.length >= 0)
        elif fnB.return_type in rec_fields:
            counter[0] += 1
            rv = mk_rec(f"!{fnB.name}.result{counter[0]}",
                        cast(str, fnB.return_type))
        else:
            rv = fresh(erase_wrappers(cast(str, fnB.return_type)), fnB.name)
        for ens_expr, _ in fnB.ensures:
            e2 = bind_params(fnB, args_z3)
            e2["result"] = rv
            try:
                ctx.assum.append(to_z3(ens_expr, e2, None))
            except Unprovable:
                pass
        return rv

    def to_z3(node: Any, env: Any, ctx: Any) -> Any:
        if isinstance(node, Num):
            return z3.IntVal(node.value)
        if isinstance(node, FloatNum):
            saw_fp[0] = True
            return z3.FPVal(node.value, z3.Float64())
        if isinstance(node, Str):
            return z3.StringVal(node.value)
        if isinstance(node, Bool):
            return z3.BoolVal(node.value)
        if isinstance(node, Var):
            if node.name not in env:
                raise Unprovable()
            return env[node.name]
        if isinstance(node, Not):
            return z3.Not(to_z3(node.value, env, ctx))
        if isinstance(node, Neg):
            v = to_z3(node.value, env, ctx)
            if isinstance(v, ListVal):
                raise Unprovable()
            return -v
        if isinstance(node, RecordLit):
            if not provable_rec(node.name):
                raise Unprovable()
            vals = {}
            for f, v in node.fields:
                vals[f] = to_z3(v, env, ctx)
            return RecVal(node.name, vals)
        if isinstance(node, FieldGet):
            obj = to_z3(node.obj, env, ctx)
            if isinstance(obj, RecElem):
                arr = obj.src.arrays.get(node.field)
                if arr is None:
                    raise Unprovable()   # a field the model skipped
                return z3.Select(arr, obj.idx)
            if not isinstance(obj, RecVal):
                raise Unprovable()
            got = obj.fields.get(node.field)
            if got is None:
                raise Unprovable()
            return got
        if isinstance(node, ListLit):
            items_z3 = [to_z3(it, env, ctx) for it in node.items]
            if items_z3 and all(z3.is_string(v) for v in items_z3):
                arr = z3.K(z3.IntSort(), z3.StringVal(""))
            else:
                arr = z3.K(z3.IntSort(), z3.IntVal(0))
            for idx, item in enumerate(items_z3):
                if not (z3.is_int(item) or z3.is_string(item)):
                    raise Unprovable()      # lists of lists, records, ...
                if item.sort() != arr.sort().range():
                    raise Unprovable()      # a list cannot mix sorts
                arr = z3.Store(arr, z3.IntVal(idx), item)
            return ListVal(arr, z3.IntVal(len(node.items)),
                           total=lambda vals=items_z3: sum(vals[1:], vals[0])
                           if vals else z3.IntVal(0))
        if isinstance(node, Call) and node.name in ("all_of", "any_of"):
            a0 = to_z3(node.args[0], env, ctx)
            if not isinstance(a0, ListVal):
                raise Unprovable()
            parg = node.args[1]
            if not isinstance(parg, Var):
                raise Unprovable()
            pfn = table.get(parg.name)
            if pfn is None:
                raise Unprovable()      # predicate came through a variable
            counter[0] += 1
            k = z3.Int(f"!q{counter[0]}")
            body = predicate_formula(pfn, z3.Select(a0.arr, k))
            inside = z3.And(k >= 0, k < a0.length)
            if node.name == "all_of":
                return z3.ForAll([k], z3.Implies(inside, body))
            return z3.Exists([k], z3.And(inside, body))
        if isinstance(node, Call) and node.name == "split":
            t = to_z3(node.args[0], env, ctx)
            sep = to_z3(node.args[1], env, ctx)
            if not (z3.is_string(t) and z3.is_string(sep)):
                raise Unprovable()
            return ListVal(SPLIT(t, sep), SPLIT_N(t, sep))
        if isinstance(node, Call) and node.name in ("upper", "lower"):
            t = to_z3(node.args[0], env, ctx)
            if not z3.is_string(t):
                raise Unprovable()
            return (UPPER if node.name == "upper" else LOWER)(t)
        if isinstance(node, Call) and node.name == "split":
            t = to_z3(node.args[0], env, ctx)
            sep = to_z3(node.args[1], env, ctx)
            if not (z3.is_string(t) and z3.is_string(sep)):
                raise Unprovable()
            # the pieces are unknown, but there is always at least one
            return ListVal(SPLIT(t, sep), SPLIT_N(t, sep))
        if isinstance(node, Call) and node.name == "contains":
            hay = to_z3(node.args[0], env, ctx)
            needle = to_z3(node.args[1], env, ctx)
            if z3.is_string(hay) and z3.is_string(needle):
                return z3.Contains(hay, needle)
            raise Unprovable()
        if isinstance(node, Call) and node.name == "code_at":
            t = to_z3(node.args[0], env, ctx)
            i = to_z3(node.args[1], env, ctx)
            if not (z3.is_string(t) and z3.is_int(i)):
                raise Unprovable()
            # the exact character is unknown to the prover, but it IS a
            # value - enough to reason about the code around it
            return CODE_AT(t, i)
        if isinstance(node, Call) and node.name in ("put", "get_or", "has"):
            base = to_z3(node.args[0], env, ctx)
            if isinstance(base, MapVal):
                k = to_z3(node.args[1], env, ctx)
                if node.name == "has":
                    return z3.Select(base.present, k)
                if node.name == "get_or":
                    d = to_z3(node.args[2], env, ctx)
                    return z3.If(z3.Select(base.present, k),
                                 z3.Select(base.vals, k), d)
                v = to_z3(node.args[2], env, ctx)        # put
                return MapVal(z3.Store(base.vals, k, v),
                              z3.Store(base.present, k, z3.BoolVal(True)),
                              base.key_t, base.val_t)
            if node.name != "put":
                raise Unprovable()
        if isinstance(node, MapLit):
            raise Unprovable()          # literal maps: runtime for now
        if isinstance(node, Call) and node.name in ("length", "get",
                                                    "push"):
            g0 = to_z3(node.args[0], env, ctx) if node.args else None
            if isinstance(g0, GridVal):
                if node.name == "length":
                    return g0.length
                if node.name == "get":
                    idx = to_z3(node.args[1], env, ctx)
                    if ctx is not None:
                        prove_bounds(idx, g0.length, ctx, node.line)
                    return ListVal(z3.Select(g0.rows, idx),
                                   z3.Select(g0.lens, idx))
                row = to_z3(node.args[1], env, ctx)      # push
                if not isinstance(row, ListVal):
                    raise Unprovable()
                return GridVal(
                    z3.Store(g0.rows, g0.length, row.arr),
                    z3.Store(g0.lens, g0.length, row.length),
                    g0.length + 1)
        if isinstance(node, Call) and node.name in ("length", "get", "push"):
            a0 = to_z3(node.args[0], env, ctx)
            if isinstance(a0, OpaqueList):
                if node.name == "length":
                    return a0.length
                raise Unprovable()      # contents are invisible
            if isinstance(a0, RecListVal):
                if node.name == "length":
                    return a0.length
                if node.name == "get":
                    a1 = to_z3(node.args[1], env, ctx)
                    if not hasattr(a1, "sort") or not z3.is_int(a1):
                        raise Unprovable()
                    if ctx is not None:
                        prove_bounds(a1, a0.length, ctx, node.line)
                    return RecElem(a0, a1)
                if node.name == "push":
                    a1 = to_z3(node.args[1], env, ctx)
                    if not isinstance(a1, RecVal) \
                            or a1.rname != a0.rname:
                        raise Unprovable()
                    new_arrays = {}
                    for fname, arr in a0.arrays.items():
                        fv = a1.fields.get(fname)
                        if fv is None or not hasattr(fv, "sort") \
                                or not z3.is_int(fv):
                            raise Unprovable()
                        new_arrays[fname] = z3.Store(arr, a0.length, fv)
                    return RecListVal(a0.rname, new_arrays,
                                      a0.length + 1)
            if not isinstance(a0, ListVal):
                if z3.is_string(a0):
                    return z3.Length(a0)        # characters in the text
                raise Unprovable()
            if node.name == "length":
                return a0.length
            a1 = to_z3(node.args[1], env, ctx)
            # lists are modelled as arrays of Ints; anything else (Text,
            # records, nested lists) stays runtime-checked rather than
            # being forced into a sort it does not fit
            if node.name == "push":
                # a record, a nested list or a map has no Z3 sort at all;
                # ask before assuming, or the translator crashes
                if not hasattr(a1, "sort") or \
                        a1.sort() != a0.arr.sort().range():
                    raise Unprovable()
                return ListVal(z3.Store(a0.arr, a0.length, a1),
                               a0.length + 1,
                               total=lambda a0=a0, a1=a1: list_total(a0) + a1)
            if not hasattr(a1, "sort") or not z3.is_int(a1):
                raise Unprovable()          # an index is always an Int
            # get: prove the read stays inside the list (E705)
            if ctx is not None:
                prove_bounds(a1, a0.length, ctx, node.line)
            return z3.Select(a0.arr, a1)
        if isinstance(node, Call) and node.name not in money_shadowed and \
                builtin_reached(node.name, table) in MONEY_Z3:
            return money_z3(cast(str, builtin_reached(node.name, table)), node, env,
                            ctx)
        if isinstance(node, Call):
            if ctx is None:            # inside a contract: no call summaries
                raise Unprovable()
            return summarize_call(node, env, ctx)
        if isinstance(node, BinOp):
            op = node.op
            if op == "and":
                return z3.And(to_z3(node.left, env, ctx),
                              to_z3(node.right, env, ctx))
            if op == "or":
                return z3.Or(to_z3(node.left, env, ctx),
                             to_z3(node.right, env, ctx))
            l = to_z3(node.left, env, ctx)  # noqa: E741
            r = to_z3(node.right, env, ctx)
            if isinstance(l, RecVal) or isinstance(r, RecVal):
                if not (isinstance(l, RecVal) and isinstance(r, RecVal)):
                    raise Unprovable()
                if op == "==":
                    return rec_eq(l, r)
                if op == "!=":
                    return z3.Not(rec_eq(l, r))
                raise Unprovable()
            if isinstance(l, ListVal) or isinstance(r, ListVal):
                if not (isinstance(l, ListVal) and isinstance(r, ListVal)):
                    raise Unprovable()
                if op == "==":
                    return z3.And(l.arr == r.arr, l.length == r.length)
                if op == "!=":
                    return z3.Not(z3.And(l.arr == r.arr,
                                         l.length == r.length))
                raise Unprovable()
            if not (symbolic(l) and symbolic(r)):
                # a map, a list of lists, a list of records, a list known
                # only by its length: Python's == would compare the two
                # objects rather than what they hold - a constant False,
                # which made a branch on it look unreachable and its
                # promises proven (8.3). Nothing here models them.
                raise Unprovable()
            if op == "+":
                return l + r
            if op == "-":
                return l - r
            if op == "*":
                return l * r
            if op == "==":
                if z3.is_fp(l) or z3.is_fp(r):
                    return z3.fpEQ(l, r)     # IEEE: NaN != NaN, +0 == -0
                return l == r
            if op == "!=":
                if z3.is_fp(l) or z3.is_fp(r):
                    return z3.Not(z3.fpEQ(l, r))
                return l != r
            if op == "<":
                return l < r
            if op == ">":
                return l > r
            if op == "<=":
                return l <= r
            if op == ">=":
                return l >= r
            if op in ("/", "%") and not (z3.is_fp(l) or z3.is_fp(r)):
                if ctx is not None:        # divide by zero, proven early
                    prove_nonzero(r, ctx, node.line, op)
                # Sabline divides the way Python does: the result floors
                # toward minus infinity. That matches Z3's integer
                # division only when the divisor is POSITIVE, so that is
                # the only case translated - a negative divisor falls
                # back to a runtime check rather than a formula that
                # would quietly disagree with the interpreter.
                if ctx is None or not provably_positive(r, ctx):
                    raise Unprovable()
                return (l / r) if op == "/" else (l % r)
        raise Unprovable()             # Str, ListLit, floats, anything else

    def provably_positive(divisor: Any, ctx: Any) -> bool:
        """True only if the divisor cannot be zero or negative here.

        Until 4.3 a divisor, or a path, that mentioned a loop's values
        was never shown positive, so no division by a loop counter was
        translated. The facts on such a path are the loop's condition and
        invariants, which hold on every real turn (an inferred one is
        proven inductive, a written one is proven or the function is
        not), and the question is only whether the divisor can be <= 0
        under them - a no there is a no in every run. A callee's promise
        is not among them: it sits in assum, which this does not read."""
        solver = new_solver()
        solver.add(*ctx.param_assum)
        solver.add(*ctx.conds)
        solver.add(divisor <= 0)
        return cast(bool, verdict_of(solver) == z3.unsat)

    def prove_nonzero(divisor: Any, ctx: Any, line: Any, op: str) -> None:
        """Prove the divisor is never zero; only report real violations."""
        if has_fresh(divisor):
            return          # the divisor itself is unknown here; the
                            # runtime check still guards it
        # conditions mentioning havoc'd values stay in the solver rather
        # than cancelling the proof: dropping them would invent
        # counterexamples, and keeping them costs nothing. Without this a
        # loop anywhere before the division hid the check entirely -
        # which is the shape of nearly every average.
        solver = new_solver()
        solver.add(*ctx.param_assum)
        solver.add(*ctx.conds)
        solver.add(divisor == 0)
        if verdict_of(solver) == z3.sat:
            m = solver.model()
            names = sorted({d.name() for d in m.decls()
                            if not d.name().startswith("!")})
            shown = ", ".join(
                f"{_shown_name(n)} = "
                f"{m.eval(z3.Int(n), model_completion=True)}"
                for n in names[:3])
            word = "divide by" if op == "/" else "take the remainder of"
            raise SablineError("E706",
                f"this can {word} zero"
                + (f": {shown}" if shown else "")
                + " - proven without running the program", line,
                fixes=["guard it: if d != 0 { ... }",
                       "or add a 'requires' that rules out zero"])

    pinned_counter = [False]   # True while checking a real final turn

    def prove_bounds(idx: Any, length: Any, ctx: Any, line: Any) -> None:
        """Prove 0 <= idx < length; report only provably-real violations."""
        if not pinned_counter[0] and (
                has_fresh(idx) or has_fresh(length)
                or any(has_fresh(c) for c in ctx.conds)):
            return                       # runtime bounds check still guards
        if has_fresh(length) and not pinned_counter[0]:
            return
        solver = new_solver()
        solver.add(*ctx.param_assum)
        solver.add(*ctx.conds)
        solver.add(z3.Not(z3.And(idx >= 0, idx < length)))
        if verdict_of(solver) == z3.sat:
            m = solver.model()
            raise SablineError("E705",
                f"this 'get' can reach position "
                f"{m.eval(idx, model_completion=True)}, but the list has "
                f"{m.eval(length, model_completion=True)} item(s) - proven "
                f"without running the program", line,
                fixes=["positions go from 0 to length - 1",
                       "guard the read: if i < length(xs) { ... }"])

    def scan_calls(node: Any, env: Any, ctx: Any) -> None:
        """Inside expressions we cannot fully model (like text joining),
        still find user-function calls and prove their requires hold,
        and prove every 'get' stays inside its list."""
        if isinstance(node, Call):
            for a in node.args:
                scan_calls(a, env, ctx)
            if node.name == "get" and len(node.args) == 2:
                try:
                    a0 = to_z3(node.args[0], env, ctx)
                    a1 = to_z3(node.args[1], env, ctx)
                    if isinstance(a0, ListVal):
                        prove_bounds(a1, a0.length, ctx, node.line)
                except Unprovable:
                    pass
            fnB = table.get(node.name)
            if (fnB is not None and fnB.requires
                    and len(fnB.params) == len(node.args)):
                # translate what translates; an argument the prover
                # cannot see becomes an unknown rather than cancelling
                # the whole check - so 'divisor > 0' is still enforced
                # when it sits beside a record list
                args_z3 = []
                for a, (_, pt) in zip(node.args, fnB.params):
                    try:
                        v = to_z3(a, env, ctx)
                    except Unprovable:
                        if pt.startswith("List of "):
                            counter[0] += 1
                            ln = z3.Int(f"!arg_len{counter[0]}")
                            v = OpaqueList(ln)
                        else:
                            v = None
                    args_z3.append(v)
                check_requires_at(fnB, args_z3, ctx, node.line)
        elif isinstance(node, BinOp):
            scan_calls(node.left, env, ctx)
            scan_calls(node.right, env, ctx)
        elif isinstance(node, (Not, Neg, TryExpr)):
            scan_calls(node.value, env, ctx)
        elif isinstance(node, ListLit):
            for it in node.items:
                scan_calls(it, env, ctx)
        elif isinstance(node, MapLit):
            for k, v in node.entries:
                scan_calls(k, env, ctx)
                scan_calls(v, env, ctx)
        elif isinstance(node, FieldGet):
            scan_calls(node.obj, env, ctx)
        elif isinstance(node, RecordLit):
            for _, v in node.fields:
                scan_calls(v, env, ctx)

    def assigned_names(stmts: Any, out: Any) -> Any:
        for s in stmts:
            if isinstance(s, (Let, Assign)):
                out.add(s.name)
            elif isinstance(s, If):
                assigned_names(s.then, out)
                assigned_names(s.other, out)
            elif isinstance(s, While):
                assigned_names(s.body, out)
        return out

    def prove_invariant(inv_expr: Any, iline: Any, env: Any, ctx: Any, where: Any) -> None:
        """Prove one invariant under the given state; honest wording only."""
        try:
            goal = to_z3(inv_expr, env, None)
        except Unprovable:
            return                       # can't model it; runtime will check
        solver = new_solver()
        solver.add(*ctx.assum)
        solver.add(*ctx.conds)
        solver.add(z3.Not(goal))
        verdict = verdict_of(solver)
        if verdict == z3.sat and (
                mentions_total(goal) or uninterpreted_in(goal)
                or any(uninterpreted_in(c) for c in ctx.conds)):
            raise Unprovable()       # a sum Z3 was not given, or a split it
                                     # knows nothing of: the state it found
                                     # may be one no program is in
        if verdict == z3.sat:
            m = solver.model()
            names = sorted(n for n in expr_vars(inv_expr) if n in env)
            vals = ", ".join(
                f"{n} = {m.eval(env[n], model_completion=True)}"
                for n in names)
            raise SablineError("E703",
                f"cannot prove the loop keeps 'invariant "
                f"{expr_str(inv_expr)}' {where} in '{ctx.caller}' - "
                f"the promises allow: {vals}", iline,
                fixes=["fix the loop so the invariant always holds",
                       "or strengthen the invariant(s) to rule this "
                       "state out",
                       "or remove the invariant (it will then be checked "
                       "at runtime instead)"])
        if verdict != z3.unsat:
            raise Unprovable()

    def bound_of(s: Any, env: Any, ctx: Any, changed: Any) -> tuple[Any, ...] | None:
        """(counter, its last value in the loop, its starting value).

        Only for the simple shape: one Int compared against something the
        loop does not change, stepping by one.
        """
        if not isinstance(s.cond, BinOp) or s.cond.op not in ("<", "<="):
            return None
        left, right = s.cond.left, s.cond.right
        if not isinstance(left, Var) or left.name not in changed:
            return None
        start = env.get(left.name)
        if start is None or not z3.is_int(start) or has_fresh(start):
            return None
        try:
            limit = to_z3(right, env, None)
        except (Unprovable, KeyError):
            return None
        if not z3.is_int(limit) or has_fresh(limit):
            return None
        steps = [st for st in s.body
                 if isinstance(st, Assign) and st.name == left.name]
        if len(steps) != 1:
            return None                  # not a plain one-step counter
        step = steps[0].value
        if not (isinstance(step, BinOp) and step.op == "+"
                and isinstance(step.left, Var)
                and step.left.name == left.name
                and isinstance(step.right, Num) and step.right.value == 1):
            return None
        last = limit - 1 if s.cond.op == "<" else limit
        return (left.name, last, start)

    current_fn: list[Function | None] = [None]   # the function being proven, for its ensures

    def quantified_candidates(env: Any, changed: Any) -> Any:
        """all_of(x, P) in the current ensures becomes a candidate
        invariant over every changed list: everything in it so far
        satisfies P. Entry is vacuous (empty list); preservation asks
        the solver whether each pushed element satisfies P on its path;
        afterward the promise follows directly. This is what lets
        'ensures all_of(result, is_positive)' prove through a loop."""
        fn = current_fn[0]
        if fn is None or not fn.ensures:
            return []
        preds = []
        def harvest(e: Any) -> None:
            if isinstance(e, Call) and e.name in ("all_of", "any_of") \
                    and len(e.args) == 2 and isinstance(e.args[1], Var):
                pfn = table.get(e.args[1].name)
                if pfn is not None:
                    preds.append(pfn)
            import dataclasses as _dc
            if _dc.is_dataclass(e):
                for f in _dc.fields(e):
                    v = getattr(e, f.name)
                    if isinstance(v, (list, tuple)):
                        for x in v:
                            if _dc.is_dataclass(x):
                                harvest(x)
                    elif _dc.is_dataclass(v):
                        harvest(v)
        for e_expr, _ in fn.ensures:
            harvest(e_expr)
        if not preds:
            return []
        cands: list[tuple[str, Callable[..., Any]]] = []
        for n in sorted(changed):
            v = env.get(n)
            if not isinstance(v, ListVal):
                continue
            for pfn in preds:
                def c(e: Any, n: Any = n, pfn: Any = pfn) -> Any:
                    lv = e[n]
                    if not isinstance(lv, ListVal):
                        raise KeyError(n)
                    counter[0] += 1
                    k = z3.Int(f"!qq{counter[0]}")
                    return z3.ForAll([k], z3.Implies(
                        z3.And(k >= 0, k < lv.length),
                        predicate_formula(pfn, z3.Select(lv.arr, k))))
                cands.append((f"everything in '{n}' satisfies "
                              f"'{pfn.name}'", c))
        return cands

    def infer_invariants(env: Any, changed: Any, s: Any, ctx: Any) -> Any:
        """Guess the boring invariants so people stop writing them.

        Candidates are simple bounds on the counters a loop moves: each
        changed Int either never goes below or never goes above the
        value it had on entry, and lists keep their length. Everything
        is assumed together, one loop step is explored, and whatever a
        step can break is dropped - repeating until the set is stable.
        (This is the Houdini algorithm, kept deliberately small.)
        """
        snap = {}
        for n in sorted(changed):
            v = env.get(n)
            if v is not None and z3.is_int(v) and not has_fresh(v):
                snap[n] = v
        if not snap:
            return []
        cands: list[tuple[str, Callable[..., Any]]] = []
        for n, start in snap.items():
            cands.append((f"{n} never goes below its starting value",
                          lambda e, n=n, s0=start: e[n] >= s0))
            cands.append((f"{n} never goes above its starting value",
                          lambda e, n=n, s0=start: e[n] <= s0))

        # A counter walking toward a limit stops AT the limit, not past
        # it. Without this the state after a loop only says i >= limit,
        # so 'the loop ran exactly limit times' can never follow - which
        # is what almost every list-building loop needs.
        bound = None
        if isinstance(s.cond, BinOp) and s.cond.op in ("<", "<=", ">", ">="):
            for side, other, op in ((s.cond.left, s.cond.right, s.cond.op),
                                    (s.cond.right, s.cond.left,
                                     {"<": ">", "<=": ">=", ">": "<",
                                      ">=": "<="}[s.cond.op])):
                if isinstance(side, Var) and side.name in snap:
                    try:
                        limit = to_z3(other, env, None)
                    except (Unprovable, KeyError):
                        continue
                    if not z3.is_int(limit) or has_fresh(limit):
                        continue
                    counter = side.name
                    step = 1 if op in ("<", "<=") else -1
                    # 'while i < E' exits with i at most E; 'while i <= E'
                    # exits with i at most E + 1. Off by one here and the
                    # bound is too weak to pin the counter at exit.
                    edge = (limit if op == "<" else limit + 1) if step > 0 \
                        else (limit if op == ">" else limit - 1)
                    bound = (counter, edge, step)
                    label = (f"{counter} never passes the limit the loop "
                             f"tests against")
                    if step > 0:
                        cands.append((label,
                                      lambda e, n=counter, b=edge: e[n] <= b))
                    else:
                        cands.append((label,
                                      lambda e, n=counter, b=edge: e[n] >= b))
                    break

        try:
            cands.extend(quantified_candidates(env, changed))
        except Unprovable:
            pass

        # A list built one item per turn has exactly as many items as the
        # counter has turns. This is the bridge the prover was missing
        # between a loop and the length of what it produced.
        if bound is not None:
            counter, _, _ = bound
            for n in sorted(changed):
                v = env.get(n)
                if not isinstance(v, ListVal) or has_fresh(v.length):
                    continue
                start_len = v.length
                start_counter = snap.get(counter)
                if start_counter is None:
                    continue
                cands.append((
                    f"'{n}' grows one item for each turn of '{counter}'",
                    lambda e, n=n, c=counter, l0=start_len,
                    c0=start_counter: e[n].length == l0 + (e[c] - c0)))
                cands.append((
                    f"'{n}' never outgrows the turns of '{counter}'",
                    lambda e, n=n, c=counter, l0=start_len,
                    c0=start_counter: e[n].length <= l0 + (e[c] - c0)))
                cands.append((f"'{n}' never shrinks",
                              lambda e, n=n, l0=start_len:
                              e[n].length >= l0))

        for _round in range(3):
            env_h, hfacts = havoc_like(env, changed)
            try:
                facts = list(hfacts) + [c(env_h) for _, c in cands]
                cond_h = to_z3(s.cond, env_h, ctx)
            except (Unprovable, KeyError):
                return []
            ctx_body = Ctx(ctx.conds + facts + [cond_h],
                           list(ctx.assum) + facts + [cond_h],
                           list(ctx.param_assum), ctx.caller)
            try:
                paths = explore(list(s.body), dict(env_h), ctx_body)
            except (Unprovable, SablineError):
                return []
            if naming.env("SABLINE_DEBUG_INV"):
                print("  candidates this round:",
                      [lab for lab, _ in cands], file=sys.stderr)
            keep = []
            for label, c in cands:
                ok = True
                for pctx, ret, penv in paths:
                    if ret is not FELL_OFF:
                        continue
                    try:
                        goal = c(penv)
                    except KeyError:
                        ok = False
                        break
                    solver = new_solver()
                    solver.add(*pctx.assum)
                    solver.add(*pctx.conds)
                    solver.add(z3.Not(goal))
                    if verdict_of(solver) != z3.unsat:
                        ok = False
                        break
                if ok:
                    keep.append((label, c))
            if len(keep) == len(cands):
                return cands
            cands = keep
            if not cands:
                return []
        return cands

    def havoc_like(env: Any, names: Any) -> tuple[Any, ...]:
        """Fresh unknowns for every variable the loop can change.
        Returns (new_env, facts) - facts like 'list lengths stay >= 0'."""
        out = dict(env)
        facts = []
        for n in names:
            old = env.get(n)
            if isinstance(old, RecVal):
                counter[0] += 1
                out[n] = mk_rec(f"!{n}.{counter[0]}", old.rname)
            elif isinstance(old, ListVal):
                counter[0] += 1
                arr = z3.Array(f"!{n}.arr{counter[0]}",
                               z3.IntSort(), z3.IntSort())
                ln = z3.Int(f"!{n}.len{counter[0]}")
                out[n] = ListVal(arr, ln)
                facts.append(ln >= 0)
            elif old is not None and z3.is_bool(old):
                out[n] = fresh("Bool", n)
            elif old is not None and isinstance(old, GridVal):
                counter[0] += 1
                base = f"!{n}.grid{counter[0]}"
                inner = z3.ArraySort(z3.IntSort(), z3.IntSort())
                gl = z3.Int(base + "#n")
                out[n] = GridVal(z3.Array(base, z3.IntSort(), inner),
                                 z3.Array(base + "#lens", z3.IntSort(),
                                          z3.IntSort()), gl)
                facts.append(gl >= 0)
            elif old is not None and isinstance(old, RecListVal):
                counter[0] += 1
                arrays = {f: z3.Array(f"!{n}.{f}{counter[0]}",
                                      z3.IntSort(), z3.IntSort())
                          for f in old.arrays}
                ln = z3.Int(f"!{n}.rlen{counter[0]}")
                out[n] = RecListVal(old.rname, arrays, ln)
                facts.append(ln >= 0)
            elif old is not None and isinstance(old, OpaqueList):
                counter[0] += 1
                ln = z3.Int(f"!{n}.olen{counter[0]}")
                out[n] = OpaqueList(ln)
                facts.append(ln >= 0)
            elif old is not None and isinstance(old, MapVal):
                counter[0] += 1
                out[n] = mk_map(f"!{n}.havoc{counter[0]}",
                                f"Map of {old.key_t} to {old.val_t}")
            elif old is not None and z3.is_string(old):
                out[n] = fresh("Text", n)
            elif old is not None and z3.is_fp(old):
                out[n] = fresh("Float", n)
            else:
                out[n] = fresh("Int", n)
        return out, facts

    def explore(stmts: Any, env: Any, ctx: Any) -> Any:
        i = 0
        while i < len(stmts):
            s = stmts[i]
            if isinstance(s, FailStmt):
                return [(ctx, FAILED, dict(env))]  # this path never returns
            if isinstance(s, Check):
                rest = stmts[i + 1:]
                rv = summarize_call(s.subject, env, ctx, allow_fail=True)
                env_ok = dict(env)
                if s.ok_name is not None:
                    env_ok[s.ok_name] = rv
                ok_paths = explore(list(s.ok_body) + rest, env_ok, ctx)
                env_fail = dict(env)
                env_fail.pop(s.fail_name, None)   # a Text reason: unmodeled
                fail_paths = explore(list(s.fail_body) + rest, env_fail,
                                     ctx)
                return ok_paths + fail_paths
            if (isinstance(s, (Let, Assign)) and
                    isinstance(s.value, TryExpr)):
                rest = stmts[i + 1:]
                rv = summarize_call(s.value.value, env, ctx,
                                    allow_fail=True)
                env2 = dict(env)
                env2[s.name] = rv
                return (explore(rest, env2, ctx)
                        + [(ctx, FAILED, dict(env))])
            if isinstance(s, Return) and isinstance(s.value, TryExpr):
                rv = summarize_call(s.value.value, env, ctx,
                                    allow_fail=True)
                return [(ctx, rv, dict(env)), (ctx, FAILED, dict(env))]
            if (isinstance(s, ExprStmt)
                    and isinstance(s.expr, TryExpr)):
                rest = stmts[i + 1:]
                summarize_call(s.expr.value, env, ctx, allow_fail=True)
                return (explore(rest, dict(env), ctx)
                        + [(ctx, FAILED, dict(env))])
            if isinstance(s, (Let, Assign)):
                env[s.name] = to_z3(s.value, env, ctx)
            elif isinstance(s, Return):
                r = FELL_OFF if s.value is None else to_z3(s.value, env, ctx)
                return [(ctx, r, dict(env))]
            elif isinstance(s, If):
                c = to_z3(s.cond, env, ctx)
                rest = stmts[i + 1:]
                yes = explore(list(s.then) + rest, dict(env), ctx.fork(c))
                no = explore(list(s.other) + rest, dict(env),
                             ctx.fork(z3.Not(c)))
                return yes + no
            elif isinstance(s, While):
                changed = assigned_names(s.body, set())
                inferred = infer_invariants(env, changed, s, ctx)
                if not s.invariants and not inferred:
                    raise Unprovable()   # no bridge across this loop
                # 1. ENTRY: every written invariant must hold before the
                #    first spin (inferred ones hold by construction)
                for inv_expr, iline in s.invariants:
                    prove_invariant(inv_expr, iline, env, ctx,
                                    "when the loop starts")
                # 2. PRESERVATION: from ANY state the invariants allow,
                #    one loop step must land back inside the invariants
                env_h, hfacts = havoc_like(env, changed)
                facts = list(hfacts)
                for _, c in inferred:
                    try:
                        facts.append(c(env_h))
                    except KeyError:
                        pass
                for inv_expr, _ in s.invariants:
                    try:
                        facts.append(to_z3(inv_expr, env_h, None))
                    except Unprovable:
                        pass
                cond_h = to_z3(s.cond, env_h, ctx)
                ctx_body = Ctx(ctx.conds + facts + [cond_h],
                               list(ctx.assum) + facts + [cond_h],
                               list(ctx.param_assum), ctx.caller)
                exits = []
                for pctx, ret, penv in explore(list(s.body), dict(env_h),
                                               ctx_body):
                    if ret is FELL_OFF:
                        for inv_expr, iline in s.invariants:
                            prove_invariant(inv_expr, iline, penv, pctx,
                                            "after one loop step")
                    else:
                        exits.append((pctx, ret, penv))  # return inside loop
                # 2b. THE LAST TURN. A counter that starts inside the
                #     loop's limit and steps by exactly one takes every
                #     value up to the largest the condition allows - so
                #     that turn really happens, and a read on it is a
                #     real read. Pinning the counter there turns "might
                #     be out of range somewhere" into a fact.
                if bound_of(s, env, ctx, changed) is not None:
                    counter, last, start = cast(tuple[Any, Any, Any],
                                                bound_of(s, env, ctx, changed))
                    reach = new_solver()
                    reach.add(*ctx.param_assum)
                    reach.add(*ctx.conds)
                    reach.add(z3.Not(start <= last))
                    if verdict_of(reach) == z3.unsat:      # the turn happens
                        env_last, lfacts = havoc_like(env, changed)
                        env_last[counter] = last
                        ctx_last = Ctx(
                            ctx.conds + lfacts,
                            list(ctx.assum) + lfacts,
                            list(ctx.param_assum), ctx.caller)
                        pinned_counter[0] = True
                        try:
                            explore(list(s.body), dict(env_last), ctx_last)
                        except Unprovable:
                            pass
                        finally:
                            pinned_counter[0] = False

                # 3. AFTERWARD: all we know is invariants hold, cond is false
                env_a, hfacts_a = havoc_like(env, changed)
                facts_a = list(hfacts_a)
                for _, c in inferred:
                    try:
                        facts_a.append(c(env_a))
                    except KeyError:
                        pass
                for inv_expr, _ in s.invariants:
                    try:
                        facts_a.append(to_z3(inv_expr, env_a, None))
                    except Unprovable:
                        pass
                cond_a = to_z3(s.cond, env_a, ctx)
                ctx_after = Ctx(ctx.conds + facts_a + [z3.Not(cond_a)],
                                list(ctx.assum) + facts_a + [z3.Not(cond_a)],
                                list(ctx.param_assum), ctx.caller)
                return exits + explore(stmts[i + 1:], env_a, ctx_after)
            elif isinstance(s, ExprStmt):
                try:
                    to_z3(s.expr, env, ctx)
                except Unprovable:
                    scan_calls(s.expr, env, ctx)   # still verify call sites
            else:
                raise Unprovable()
            i += 1
        return [(ctx, FELL_OFF, dict(env))]

    def find_witnesses(fn: Any, env: Any, ctx: Any,
                       count: int) -> dict[str, Any]:
        """Up to `count` argument lists the function's requires allow, as Z3
        finds them (8.3, sabline test --from-contracts): first the least
        and the greatest each whole number, text length and list length
        can be, then others, each differing from those before in a whole
        number, a truth, a text, a decimal or a list's length. Whole numbers
        are held to 64 bits, texts to WITNESS_TEXT_MOST characters and lists
        to WITNESS_LIST_MOST items."""
        import struct
        kinds = []
        for pname, ptype in fn.params:
            t = erase_wrappers(ptype)
            if "Money" in ptype or t not in WITNESS_TYPES or pname not in env:
                return {"skipped": f"parameter {pname} is {ptype}, for which "
                                   f"no witness is made"}
            kinds.append((pname, t))
        base = list(ctx.assum)
        for pname, t in kinds:
            v = env[pname]
            if t == "Int":
                base += [v >= INT_MIN, v <= INT_MAX]
            elif t == "Text":
                base.append(z3.Length(v) <= WITNESS_TEXT_MOST)
            elif t.startswith("List of "):
                base.append(v.length <= WITNESS_LIST_MOST)
                k = z3.Int(f"!{pname}#witness")
                item = z3.Select(v.arr, k)
                bound = (z3.And(item >= INT_MIN, item <= INT_MAX)
                         if t == "List of Int"
                         else z3.Length(item) <= WITNESS_TEXT_MOST)
                base.append(z3.ForAll([k], z3.Implies(
                    z3.And(k >= 0, k < v.length), bound)))

        def value(m: Any, pname: str, t: str) -> Any:
            v = env[pname]
            if t == "Int":
                return m.eval(v, model_completion=True).as_long()
            if t == "Bool":
                return bool(z3.is_true(m.eval(v, model_completion=True)))
            if t == "Text":
                return m.eval(v, model_completion=True).as_string()
            if t == "Float":
                bits = m.eval(z3.fpToIEEEBV(v), model_completion=True).as_long()
                return struct.unpack(">d", bits.to_bytes(8, "big"))[0]
            n = max(0, m.eval(v.length, model_completion=True).as_long())
            items = [m.eval(z3.Select(v.arr, z3.IntVal(i)),
                            model_completion=True) for i in range(n)]
            return ([x.as_long() for x in items] if t == "List of Int"
                    else [x.as_string() for x in items])

        found: list[dict[str, Any]] = []
        seen: set[str] = set()

        def take(m: Any, why: str) -> None:
            args = [value(m, pname, t) for pname, t in kinds]
            key = repr(args)
            if key not in seen:
                seen.add(key)
                found.append({"args": args, "why": why})

        for pname, t in kinds:
            v = env[pname]
            target = (v if t == "Int" else z3.Length(v) if t == "Text"
                      else v.length if t.startswith("List of ") else None)
            if target is None:
                continue
            what = ("value of " if t == "Int" else "length of ") + pname
            for goal in ("minimize", "maximize"):
                if len(found) >= count:
                    break
                o = z3.Optimize()
                o.set("timeout", solver_budget())
                o.add(*base)
                getattr(o, goal)(target)
                if o.check() == z3.sat:
                    take(o.model(), f"the {'least' if goal == 'minimize' else 'greatest'} "
                                    f"{what} the requires allow")
        s = new_solver()
        s.add(*base)
        while len(found) < count:
            if s.check() != z3.sat:
                break
            m = s.model()
            take(m, "a value the requires allow")
            block = []
            for pname, t in kinds:
                v = env[pname]
                if t == "Float":
                    block.append(z3.fpToIEEEBV(v) != m.eval(
                        z3.fpToIEEEBV(v), model_completion=True))
                elif t.startswith("List of "):
                    block.append(v.length != m.eval(v.length,
                                                    model_completion=True))
                else:
                    block.append(v != m.eval(v, model_completion=True))
            if not block:
                break
            s.add(z3.Or(*block))
        return {"witnesses": found,
                "uninterpreted": any(uninterpreted_in(a) for a in ctx.assum)}

    for fn in funcs:
        current_fn[0] = fn
        saw_fp[0] = False              # FP budget only when FP appears
        ran_out[0] = False             # and a fresh clock with it
        total_facts.clear()            # the sums of the last function's
        _total_seen.clear()            # lists say nothing about this one's
        env = {}
        list_facts = []
        for pname, ptype in fn.params:
            ptype = erase_wrappers(ptype)   # an amount is its minor units;
                                            # a secret is what it wraps
            if ptype in ("Int", "Bool", "Float", "Text"):
                env[pname] = mk(pname, ptype)
            elif ptype == "List of Int":
                arr = z3.Array(pname, z3.IntSort(), z3.IntSort())
                ln = z3.Int(pname + "#n")
                env[pname] = ListVal(arr, ln)
                list_facts.append(ln >= 0)
            elif ptype == "List of Text":
                arr = z3.Array(pname, z3.IntSort(), z3.StringSort())
                ln = z3.Int(pname + "#n")
                env[pname] = ListVal(arr, ln)
                list_facts.append(ln >= 0)
            elif ptype == "List of List of Int":
                inner = z3.ArraySort(z3.IntSort(), z3.IntSort())
                rows = z3.Array(pname, z3.IntSort(), inner)
                lens = z3.Array(pname + "#lens", z3.IntSort(),
                                z3.IntSort())
                ln = z3.Int(pname + "#n")
                env[pname] = GridVal(rows, lens, ln)
                list_facts.append(ln >= 0)
                k0 = z3.Int(pname + "#k")
                list_facts.append(z3.ForAll(
                    [k0], z3.Select(lens, k0) >= 0))
            elif ptype in rec_fields and provable_rec(ptype):
                env[pname] = mk_rec(pname, ptype)
            elif (ptype.startswith("List of ")
                  and ptype[len("List of "):] in rec_fields
                  and provable_rec(ptype[len("List of "):])):
                rname = ptype[len("List of "):]
                arrays = {}
                for fname, ftype in rec_fields[rname]:
                    if ftype == "Int":
                        arrays[fname] = z3.Array(
                            f"{pname}#{fname}", z3.IntSort(),
                            z3.IntSort())
                ln = z3.Int(pname + "#n")
                env[pname] = RecListVal(rname, arrays, ln)
                list_facts.append(ln >= 0)
            elif ptype.startswith("List of "):
                # the contents cannot be modelled, but the LENGTH can -
                # and length is what contracts about lists usually say.
                # Without this, one length(items) in a conjunction threw
                # the whole requires away, checkable parts included.
                ln = z3.Int(pname + "#n")
                env[pname] = OpaqueList(ln)
                list_facts.append(ln >= 0)
            elif ptype.startswith("Map of "):
                mv = mk_map(pname, ptype)
                if mv is not None:
                    env[pname] = mv
        import dataclasses as _dc

        def mentions_case(node: Any) -> bool:
            if isinstance(node, (list, tuple)):
                return any(mentions_case(x) for x in node)
            if not _dc.is_dataclass(node):
                return False
            if isinstance(node, Call) and node.name in ("upper", "lower"):
                return True
            return any(mentions_case(getattr(node, f.name))
                       for f in _dc.fields(node))

        def mentions(node: Any, names: Any) -> bool:
            if isinstance(node, (list, tuple)):
                return any(mentions(x, names) for x in node)
            if not _dc.is_dataclass(node):
                return False
            if isinstance(node, Call) and node.name in names:
                return True
            return any(mentions(getattr(node, f.name), names)
                       for f in _dc.fields(node))

        parts = [fn.body, [e for e, _ in fn.ensures],
                 [e for e, _ in fn.requires]]
        if any(mentions(p, ("upper", "lower")) for p in parts):
            list_facts.extend(CASE_AXIOMS)   # only where they matter
        if any(mentions(p, ("split",)) for p in parts):
            list_facts.extend(SPLIT_AXIOMS)
        ctx = Ctx([], list(list_facts), list(list_facts), fn.name)
        if witnesses_out is not None and fn.requires:
            witnesses_out[fn.name] = {
                "skipped": "its requires could not be given to the prover"}
        try:
            for r_expr, _ in fn.requires:
                # If a premise cannot be translated, the whole proof is
                # off: proving with dropped premises would manufacture
                # false counterexamples. Runtime checks still guard.
                fact = to_z3(r_expr, dict(env), None)
                ctx.assum.append(fact)
                ctx.param_assum.append(fact)
            if witnesses_out is not None and fn.requires:
                try:
                    witnesses_out[fn.name] = find_witnesses(
                        fn, env, ctx, witness_count)
                except z3.Z3Exception as e:
                    witnesses_out[fn.name] = {
                        "skipped": f"the prover could not make witnesses: "
                                   f"{e}"}
            paths = explore(list(fn.body), dict(env), ctx)
            if not fn.ensures:
                continue
            for pctx, ret, _ in paths:
                if ret is FAILED:
                    continue           # ensures speaks only of returns
                if ret is FELL_OFF:
                    raise Unprovable()
                for ens_expr, cline in fn.ensures:
                    e2 = dict(env)
                    e2["result"] = ret
                    goal = to_z3(ens_expr, e2, None)
                    solver = new_solver()
                    solver.add(*pctx.assum)
                    solver.add(*pctx.conds)
                    solver.add(z3.Not(goal))
                    verdict = verdict_of(solver)
                    if verdict == z3.sat:
                        if has_fresh(ret) or has_fresh(goal) or any(
                                has_fresh(c) for c in pctx.conds):
                            # counterexample depends on a summarized call:
                            # might be impossible in reality - never claim
                            # "proven"; fall back to runtime checks instead
                            raise Unprovable()
                        m = solver.model()
                        vals = ", ".join(
                            show_val(p, v, m)
                            for p, v in sorted(env.items()))
                        if isinstance(ret, RecVal):
                            rv = show_val("r", ret, m).split(" = ", 1)[-1]
                        elif isinstance(ret, ListVal):
                            rv = "a list"
                        elif isinstance(ret, MapVal):
                            rv = "a map"
                        elif isinstance(ret, GridVal):
                            rv = "a list of lists"
                        else:
                            rv = m.eval(ret, model_completion=True)
                        raise SablineError("E700",
                            f"promise cannot be kept: {nice_name(fn.name)} ensures "
                            f"{expr_str(ens_expr)} - proven without running "
                            f"the program: {vals} gives result = {rv}",
                            cline,
                            fixes=["fix the code so the promise holds for "
                                   "every allowed input",
                                   "or add a 'requires' that rules out "
                                   "such inputs"])
                    if verdict != z3.unsat:
                        raise Unprovable()
            if proven_out is not None and (fn.ensures or fn.requires):
                proven_out.add(fn.name)   # every obligation discharged
        except Unprovable:
            continue                    # runtime promise checks still guard
        except z3.Z3Exception:
            continue                    # solver hiccup: runtime still guards
        except SablineError as e:
            errors.append(blame(fn, e))
            continue

    # A proof that ran out of time says so, here and in every report
    # built from this run. Silence would read exactly like the prover
    # looking and finding nothing wrong, which is the one thing it must
    # never be mistaken for.
    left = [t for name, t in sorted(timed_out.items())
            if proven_out is None or name not in proven_out]
    if timeouts_out is not None:
        timeouts_out.extend(left)
    for t in left:
        spent = (f"{t['seconds']:.0f}" if t["seconds"] >= 1
                 else f"{t['seconds']:g}")
        print(f"note: the proof of {nice_name(t['name'])} ran out of time "
              f"after {spent}s and was abandoned - nothing was proven and "
              f"nothing was refuted, so its promises are checked while "
              f"running instead. This is not 'the prover found nothing "
              f"wrong'. Give it longer with --proof-timeout "
              f"{max(2, int(t['seconds'] * 2))} (or "
              f"{PROOF_TIMEOUT_ENV}={max(2, int(t['seconds'] * 2))}).",
              file=sys.stderr)
