"""Stage 5, the type checker: wrong-type programs refused before they run.
"""
from .errors import SablineError
from .lexer import fmt_fn_type, fn_sig_parts, type_mentions
from .nodes import (
    Assign,
    BinOp,
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
    RecordLit,
    Return,
    Str,
    TryExpr,
    Var,
    While,
)
from .parser import expr_str, nice_name
from .tables import (
    BUILTINS,
    CURRENCIES,
    FALLIBLE_BUILTINS,
    HMAC_BUILTINS,
    KNOWN_TYPES,
    MONEY_BUILTINS,
    ROUNDING,
    SECRET_SOURCES,
    builtin_reached,
    shown_name,
)
from .loader import blame, unknown_function
from .wrappers import (
    SECRET_PREFIX,
    carries_secret,
    clash_error,
    currency_clash,
    currency_generic,
    is_money,
    is_secret,
    records_carrying,
    secret_inner,
    strip_secret,
    wrap_secret,
)
from typing import Any, Callable, cast

# ---------------------------------------------------------------------------
# 4b. TYPE CHECKER — catch wrong-type bugs before the program ever runs
#     Types: Int, Text, Bool.  "Unit" means "returns nothing".
# ---------------------------------------------------------------------------


def check_main(funcs: list[Any], errors: list[Any], *, running: bool = True) -> None:
    """main must exist (when running), take nothing, declare no failure.

    `sabline check library.vel` checks a library as a library - a
    missing main is only an error for the file being run."""
    mains = [f for f in funcs if f.name == "main"]
    if not mains:
        if running:
            errors.append(SablineError("E400",
                "there is no 'main' - a program needs somewhere to start",
                1, fixes=["add one: fn main() uses io { ... }"]))
        return
    m = mains[0]
    if m.params:
        errors.append(SablineError("E401",
            f"'main' takes no parameters, but this one asks for "
            f"{len(m.params)}", m.line,
            fixes=["read the command line with args() instead"]))
    # E524, as check_types says it: until 8.2 this said E523, so `sabline
    # check` and a run gave the same mistake two codes
    if getattr(m, "can_fail", False):
        errors.append(SablineError("E524",
            "'main' cannot fail - there is nobody above it to catch",
            m.line,
            fixes=["handle failures inside main with check",
                   "or exit_with(1) when something goes wrong"]))


def check_types(funcs: list[Function], records: list[Any], errors: list[Any]) -> None:
    table = {f.name: f for f in funcs}
    rec = {}
    for r in records:
      try:
        if r.name in rec:
            raise SablineError("E507", f"record '{r.name}' is defined twice",
                               r.line, fixes=["rename one of them"])
        if r.name in table:
            raise SablineError("E507",
                f"'{r.name}' is used for both a record and a function",
                r.line, fixes=["rename one of them"])
        seen = set()
        for fname, _ in r.fields:
            if fname in seen:
                raise SablineError("E507",
                    f"record '{r.name}' has field '{fname}' twice", r.line,
                    fixes=["remove the duplicate field"])
            seen.add(fname)
        rec[r.name] = dict(r.fields)
      except SablineError as e:
        errors.append(blame(r, e))

    # ---- Secret (6.0) ----------------------------------------------------
    # Which records hold a secret, so that a structure cannot smuggle one
    # past the sink check, and `carries` in terms of it.
    rec_carries = records_carrying(records)

    def carries(t: str) -> bool:
        return carries_secret(t, rec_carries)

    def sink_builtin(name: str) -> str | None:
        """The name of the emitting builtin this call reaches, or None.
        A builtin that declares an effect is one: it hands what it is
        given to the console, a file, a host, Python or the operating
        system. declassify is the exception - taking a Secret is what it
        is for - and it says so in a signature and in the audit."""
        b = builtin_reached(name, table)
        if b is None or b == "declassify" or b in HMAC_BUILTINS:
            return None                   # hmac_*: its own rule, below
        return b if BUILTINS[b]["effects"] else None

    def secret_enters(name: str, seen: Any = None) -> Any:
        """Where the secret a function hands back first enters the
        program, as 'env(), line 4' - following one call at a time
        through the program's own functions. None when it cannot be
        told, which is no worse than the name of the function itself."""
        import dataclasses as _dc
        seen = set() if seen is None else seen
        f = table.get(name)
        if f is None or name in seen:
            return None
        seen.add(name)
        found: list[str | None] = [None]

        def walk(n: Any) -> None:
            if found[0] is not None:
                return
            if isinstance(n, (list, tuple)):
                for x in n:
                    walk(x)
                return
            if not _dc.is_dataclass(n):
                return
            if isinstance(n, Call):
                b = builtin_reached(n.name, table)
                if b in SECRET_SOURCES:
                    found[0] = f"{b}(), line {n.line}"
                    return
                deeper = table.get(n.name)
                if deeper is not None and carries(deeper.return_type or ""):
                    got = secret_enters(n.name, seen)
                    if got:
                        found[0] = got
                        return
            for fl in _dc.fields(n):
                walk(getattr(n, fl.name))

        walk(f.body)
        return found[0]

    def tattling_builtin(name: str) -> str | None:
        """The fallible builtin this call reaches, or None.

        A failure's reason is Text the program may print, and the
        runtime writes it out of the values it was given - `to_int` and
        `parse_money` quote the text they could not read, and
        `divide_or_fail` the amount it could not divide. Nothing at run
        time knows which of those values the type system called secret,
        so the compiler keeps secrets away from all of them. `get` on a
        map is not one: its reason names the key, and a key is Text or
        Int, never a Secret."""
        b = builtin_reached(name, table)
        return b if b in FALLIBLE_BUILTINS else None

    def leak(what: str, where: str, t: str, origin: str,
             line: int) -> SablineError:
        return SablineError("E560",
            f"{what} is {t}, and {where} - a Secret cannot be printed, "
            f"written, sent or passed to Python. It came from {origin}",
            line,
            fixes=["build what you emit out of values that are not "
                   "secret",
                   'or let it out on purpose: declassify(x, "why this '
                   'is safe to emit") needs "uses declassify", is named '
                   'in the audit with that reason, and an operator can '
                   'refuse to grant it'])

    def no_secret_branch(kind: str, t: str, node: Any, origin: str) -> None:
        """A program does not branch on a secret (6.1, SPEC.md 3.1).

        A comparison over a secret gives a `Secret of Bool`, and this is
        why: with `length` and a loop, `key == c` is not one bit, it is
        a character-by-character oracle that reads the whole key out and
        can then print it. So the branch is where the line is drawn, and
        `declassify` is what a program writes when it means to cross
        it - in the signature, in the audit, and in the operator's
        budget."""
        if not carries(t):
            return
        raise SablineError("E563",
            f"'{kind}' would branch on {t}, which came from {origin} - "
            f"a program does not choose what to do by looking at a "
            f"secret. A comparison over one gives a Secret of Bool "
            f"exactly so that this is refused: in a loop it would read "
            f"the secret out a character at a time", node.line,
            fixes=['say so and branch on the answer: '
                   'declassify(key == "", "whether a key is set is not '
                   'the key") needs "uses declassify", is named in the '
                   'audit with that reason, and an operator can refuse '
                   'to grant it',
                   "or decide without looking: build what you do out of "
                   "values that are not secret"])

    def callee_sig(name: str, line: int = 1) -> tuple[list[str], str]:
        builtin = builtin_reached(name, table)
        if builtin is not None:
            return (cast(list[str], BUILTINS[builtin]["types"]),
                    cast(str, BUILTINS[builtin]["ret"]))
        if name not in table:
            raise unknown_function(name, line, table)
        f = table[name]
        return [t for _, t in f.params], (f.return_type or "Unit")

    def valid_type(t: str, tvars: frozenset[Any] = frozenset()) -> bool:
        if t in KNOWN_TYPES or t in rec or t in tvars:
            return True
        if is_money(t):                 # a currency, or a currency variable
            cur = t[len("Money of "):]
            return cur in CURRENCIES or cur in tvars
        if is_secret(t):
            inner = secret_inner(t)
            return not is_secret(inner) and valid_type(inner, tvars)
        if t.startswith("List of "):
            return valid_type(t[len("List of "):], tvars)
        if t.startswith("Map of "):
            rest = t[len("Map of "):]
            key, sep, val = rest.partition(" to ")
            return sep != "" and key in ("Text", "Int") and \
                valid_type(val, tvars)
        sig = fn_sig_parts(t)
        if sig is not None:
            parts, ret = sig
            return all(valid_type(p, tvars) for p in parts) and (
                ret == "Unit" or valid_type(ret, tvars))
        return False

    TYPE_HINT = ("use Int, Text, Bool, Money of INR, a record name, or "
                 "List of <one of those>")

    def currency_named(t: str, tvars: frozenset[Any] = frozenset()) -> Any:
        """The currency code in type t that is not in the table, if any."""
        if is_money(t):
            cur = t[len("Money of "):]
            return None if cur in CURRENCIES or cur in tvars else cur
        if is_secret(t):
            return currency_named(secret_inner(t), tvars)
        if t.startswith("List of "):
            return currency_named(t[8:], tvars)
        if t.startswith("Map of "):
            return currency_named(t[7:].partition(" to ")[2], tvars)
        sig = fn_sig_parts(t)
        if sig is not None:
            for p in sig[0] + [sig[1]]:
                got = currency_named(p, tvars)
                if got:
                    return got
        return None

    def unknown_currency(code: str, line: int) -> SablineError:
        return SablineError("E551",
            f"'{code}' is not a currency Sabline knows", line,
            fixes=["the currencies are: " + ", ".join(sorted(CURRENCIES)),
                   "a currency is added to sabline.CURRENCIES with the "
                   "minor-unit count ISO 4217 gives it, not by a program"])

    def bad_type(t: str, tvars: Any, message: str, line: int) -> SablineError:
        code = currency_named(t, tvars)
        if code:
            return unknown_currency(code, line)
        return SablineError("E500", message, line, fixes=[TYPE_HINT])

    for r in records:
        for fname, ftype in r.fields:
            if not valid_type(ftype):
                errors.append(blame(r, bad_type(ftype, frozenset(),
                    f"unknown type '{ftype}' for field '{fname}' of "
                    f"record '{r.name}'", r.line)))

    # first: every declared type must be a real type
    for f in funcs:
        tvs = frozenset(f.type_vars)
        for tv in f.type_vars:
            if tv in KNOWN_TYPES or tv in rec:
                errors.append(blame(f, SablineError("E541",
                    f"type variable '{tv}' shadows a real type", f.line,
                    fixes=["pick a fresh name like T, U, or Item"])))
            elif not any(type_mentions(pt, tv) for _, pt in f.params):
                errors.append(blame(f, SablineError("E540",
                    f"type variable '{tv}' must appear in at least one "
                    f"parameter (a {tv} only in the return type cannot be "
                    f"inferred)", f.line,
                    fixes=[f"use {tv} in a parameter type"])))
        for pname, ptype in f.params:
            if not valid_type(ptype, tvs):
                raise bad_type(ptype, tvs, f"unknown type '{ptype}' for "
                               f"parameter '{pname}' of '{f.name}'", f.line)
        if f.return_type is not None and not valid_type(f.return_type, tvs):
            raise bad_type(f.return_type, tvs, f"unknown return type "
                           f"'{f.return_type}' for '{f.name}'", f.line)

    def builtin_call_fallible(node: Any, infer: Callable[..., str]) -> bool:
        if builtin_reached(node.name, table) in FALLIBLE_BUILTINS:
            return True
        if node.name == "get" and node.args:
            try:
                return infer(node.args[0]).startswith("Map of ")
            except SablineError:
                return False
        return False

    NAMESPACES = {n.split(".")[0] for n in table if "." in n}

    def no_shadow(name: str, line: int) -> None:
        if name in NAMESPACES:
            raise SablineError("E514",
                f"'{name}' is the name of an import, so it cannot also be "
                f"a variable", line,
                fixes=["rename the variable",
                       f"or give the import another name: as {name}_lib"])

    lambda_of = {f.name: f for f in funcs if getattr(f, "is_lambda", False)}

    def check_fn(fn: Function) -> None:
        for _pname, _ in fn.params:
            no_shadow(_pname, fn.line)
        env = dict(fn.params)                       # variable -> type
        for cname, ctype in getattr(fn, "captures", []):
            env.setdefault(cname, ctype)            # values carried in
        declared_ret = fn.return_type or "Unit"

        # where each secret-carrying name got its secret, so that E560
        # can name the place rather than only the value. Best effort and
        # never load-bearing: the refusal does not depend on it.
        origins = {p: f"the parameter '{p}' of {nice_name(fn.name)}"
                   for p, t in fn.params if carries(t)}
        origins.update({c: f"'{c}', carried into this function value"
                        for c, t in getattr(fn, "captures", [])
                        if carries(t)})

        def origin_of(node: Any) -> str:
            """Where the secret in this expression came from."""
            if isinstance(node, Var):
                return origins.get(node.name) or f"'{node.name}'"
            if isinstance(node, Call):
                b = builtin_reached(node.name, table)
                if b in SECRET_SOURCES:
                    return f"{b}(), line {node.line}"
                called = table.get(node.name)
                if called is not None and carries(called.return_type or ""):
                    said = (f"{nice_name(node.name)}, which returns "
                            f"{called.return_type} (line {node.line})")
                    # a secret handed in is where this one came from;
                    # otherwise look for where the callee got its own
                    for a in node.args:
                        try:
                            if carries(infer(a, allow_fail=True)):
                                return f"{origin_of(a)}, through {said}"
                        except SablineError:
                            continue
                    deeper = secret_enters(node.name)
                    return f"{deeper}, through {said}" if deeper else said
            if isinstance(node, FieldGet):
                base = origin_of(node.obj)
                return f"the field '{node.field}' of {base}"
            if isinstance(node, TryExpr):
                return origin_of(node.value)
            kids = []
            if isinstance(node, Call):
                kids = list(node.args)
            elif isinstance(node, BinOp):
                kids = [node.left, node.right]
            elif isinstance(node, (Not, Neg)):
                kids = [node.value]
            elif isinstance(node, ListLit):
                kids = list(node.items)
            elif isinstance(node, MapLit):
                kids = [v for _, v in node.entries]
            elif isinstance(node, RecordLit):
                kids = [v for _, v in node.fields]
            for k in kids:
                try:
                    if carries(infer(k, allow_fail=True)):
                        return origin_of(k)
                except SablineError:
                    continue
            return "a secret value"

        def refuse_secret_args(node: Any, said: str, where: str) -> None:
            """No argument of an emitting call may carry a secret."""
            for i, a in enumerate(node.args, 1):
                try:
                    t = infer(a, allow_fail=True)
                except SablineError:
                    continue
                if carries(t):
                    raise leak(f"argument {i} of '{said}'", where, t,
                               origin_of(a), node.line)

        def infer(node: Any, allow_fail: bool = False) -> str:  # type: ignore[return]  # every expression node returns or raises above; no other node is passed
            if isinstance(node, TryExpr):
                if not fn.can_fail:
                    raise SablineError("E521",
                        f"'try' passes failure up, but '{fn.name}' cannot "
                        f"fail", node.line,
                        fixes=[f"add 'or fail' to the signature of "
                               f"'{fn.name}'",
                               "or handle it here with a check block"])
                callee = table.get(node.value.name)
                user_ok = callee is not None and callee.can_fail
                if not user_ok and not builtin_call_fallible(node.value,
                                                             infer):
                    raise SablineError("E522",
                        f"'{shown_name(node.value.name)}' cannot fail - "
                        f"call it directly without 'try'", node.line,
                        fixes=["remove the 'try'"])
                return infer(node.value, allow_fail=True)
            if isinstance(node, Num):
                return "Int"
            if isinstance(node, FloatNum):
                return "Float"
            if isinstance(node, Neg):
                t = infer(node.value)
                bare = strip_secret(t)
                if bare not in ("Int", "Float") and not is_money(bare):
                    raise SablineError("E501",
                        f"'-' needs a number, but this is {t}", node.line,
                        fixes=["negate an Int or Float value"])
                return t
            if isinstance(node, Str):
                return "Text"
            if isinstance(node, Bool):
                return "Bool"
            if isinstance(node, Closure):
                lam = lambda_of.get(node.name)
                if lam is None:
                    raise SablineError("E402",
                        f"unknown function value '{node.name}'", node.line)
                # a name is captured when the surrounding code has it as
                # a local; anything else is a global function or builtin
                caught = []
                for n in node.free:
                    if n in env:
                        caught.append((n, env[n]))
                lam.captures = caught
                check_fn(lam)              # check it where its names mean
                                           # something
                return fmt_fn_type([t for _, t in lam.params],
                                   lam.return_type)
            if isinstance(node, Var):
                if node.name in env:
                    return env[node.name]
                f2 = table.get(node.name)
                if f2 is not None:
                    if f2.type_vars:
                        raise SablineError("E543",
                            f"'{f2.name}' is generic - generic functions "
                            f"cannot be passed as values yet", node.line,
                            fixes=["call it directly instead"])
                    if f2.effects:
                        raise SablineError("E530",
                            f"'{f2.name}' uses effects "
                            f"({', '.join(sorted(f2.effects))}) - only pure "
                            f"functions can be passed as values", node.line,
                            fixes=["pass a function with no 'uses' clause"])
                    if f2.can_fail:
                        raise SablineError("E530",
                            f"'{f2.name}' can fail - only functions that "
                            f"cannot fail can be passed as values", node.line,
                            fixes=["pass a function without 'or fail'"])
                    return fmt_fn_type([t for _, t in f2.params],
                                       f2.return_type)
                if getattr(fn, "is_lambda", False):
                    # a function value takes what the code around it has
                    # where it is written (SPEC.md 12a), so a name reaching
                    # here is defined neither there nor in it (8.2: this
                    # said it could not be used from the code around it)
                    raise SablineError("E402",
                        f"unknown variable '{node.name}': it is not defined "
                        f"where this function value is written, nor in it",
                        node.line,
                        fixes=[f"declare it first: let {node.name} = ...",
                               "or pass it in as a parameter"])
                if node.name in ("break", "continue"):
                    raise SablineError("E402",
                        f"there is no '{node.name}' in this language",
                        node.line,
                        fixes=["use a condition in the loop test instead",
                               "or keep a flag: "
                               "while going and i < n { ... }"])
                raise SablineError("E402",
                                  f"unknown variable '{node.name}'",
                                  node.line,
                                  fixes=[f"declare it first: let {node.name} = ..."])
            if isinstance(node, Not):
                t = infer(node.value)
                if strip_secret(t) != "Bool":
                    raise SablineError("E501",
                        f"'not' needs a yes/no value (Bool), but this is {t}",
                        node.line, fixes=["use it on a comparison like not (x > 0)"])
                return t
            if isinstance(node, RecordLit):
                if node.name not in rec:
                    raise SablineError("E508",
                        f"unknown record '{node.name}'", node.line,
                        fixes=[f"declare it first: record {node.name} {{ ... }}"])
                fields_want = rec[node.name]
                fields_given = {}
                for fname, v in node.fields:
                    if fname not in fields_want:
                        raise SablineError("E509",
                            f"record '{node.name}' has no field '{fname}'",
                            node.line,
                            fixes=[f"its fields are: {', '.join(fields_want)}"])
                    if fname in fields_given:
                        raise SablineError("E509",
                            f"field '{fname}' is given twice", node.line,
                            fixes=["give each field exactly once"])
                    fields_given[fname] = infer(v)
                    if currency_clash(fields_want[fname], fields_given[fname]):
                        raise clash_error(fields_want[fname], fields_given[fname],
                                          node.line, f"field '{fname}'")
                    if fields_given[fname] != fields_want[fname]:
                        raise SablineError("E501",
                            f"field '{fname}' of '{node.name}' holds "
                            f"{fields_want[fname]}, but this is {fields_given[fname]}",
                            node.line,
                            fixes=[f"give {'an' if fields_want[fname] == 'Int' else 'a'} "
                                   f"{fields_want[fname]} value"])
                missing = [f for f in fields_want if f not in fields_given]
                if missing:
                    raise SablineError("E509",
                        f"record '{node.name}' is missing field(s): "
                        f"{', '.join(missing)}", node.line,
                        fixes=["give every field a value"])
                return node.name
            if isinstance(node, FieldGet):
                t = infer(node.obj)
                if t not in rec:
                    raise SablineError("E510",
                        f"{t} has no fields", node.line,
                        fixes=["only records have fields, accessed like p.x"])
                if node.field not in rec[t]:
                    raise SablineError("E510",
                        f"record '{t}' has no field '{node.field}'",
                        node.line,
                        fixes=[f"its fields are: {', '.join(rec[t])}"])
                return cast(str, rec[t][node.field])
            if isinstance(node, MapLit):
                if not node.entries:
                    raise SablineError("E506",
                        "cannot tell what an empty map holds", node.line,
                        fixes=['put at least one entry in it, e.g. {"a": 0}'])
                kt = infer(node.entries[0][0])
                vt = infer(node.entries[0][1])
                if kt not in ("Text", "Int"):
                    raise SablineError("E501",
                        f"map keys must be Text or Int, but this is {kt}",
                        node.line, fixes=["use Text or Int keys"])
                seen_const = set()
                for k, v in node.entries:
                    if infer(k) != kt:
                        raise SablineError("E501",
                            f"a map cannot mix {kt} and {infer(k)} keys",
                            node.line, fixes=["keep every key the same type"])
                    if currency_clash(vt, infer(v)):
                        raise clash_error(vt, infer(v), node.line,
                                          "a value in this map")
                    if infer(v) != vt:
                        raise SablineError("E501",
                            f"a map cannot mix {vt} and {infer(v)} values",
                            node.line, fixes=["keep every value the same type"])
                    if isinstance(k, (Str, Num)):
                        if k.value in seen_const:
                            raise SablineError("E509",
                                f"map key {expr_str(k)} is given twice",
                                node.line, fixes=["give each key once"])
                        seen_const.add(k.value)
                return f"Map of {kt} to {vt}"
            if isinstance(node, ListLit):
                if not node.items:
                    raise SablineError("E506",
                        "cannot tell what an empty list holds", node.line,
                        fixes=["put at least one item in it, e.g. [0]"])
                t0 = infer(node.items[0])
                for it in node.items[1:]:
                    t = infer(it)
                    if currency_clash(t0, t):
                        raise clash_error(t0, t, node.line,
                                          "an item in this list")
                    if t != t0:
                        raise SablineError("E501",
                            f"a list cannot mix {t0} and {t}", node.line,
                            fixes=["keep every item in a list the same type"])
                return "List of " + t0
            # ---- the sink check (6.0), in one place ------------------
            # Every route by which a builtin can put a value in front of
            # somebody is here, so a builtin added later cannot acquire
            # one quietly. A call to a local of function type runs that
            # function value, not a builtin. A call to any other local named
            # like a builtin reaches the builtin when it runs (runtime.py),
            # and is checked as one: until 8.2 `let print = 0` let the next
            # print(k) show a Secret.
            if isinstance(node, Call) and not (
                    node.name in env and env[node.name].startswith("fn(")):
                emits = sink_builtin(node.name)
                if emits is not None:
                    refuse_secret_args(
                        node, shown_name(node.name),
                        f"'{emits}' performs "
                        f"{', '.join(sorted(BUILTINS[emits]['effects']))}")
                tells = tattling_builtin(node.name)
                if tells is not None:
                    refuse_secret_args(
                        node, shown_name(node.name),
                        f"'{tells}' can fail with a reason the runtime "
                        f"builds out of the values it was given, which "
                        f"the program can then print")
            if isinstance(node, Call) and node.name in (
                    "all_of", "any_of"):
                if len(node.args) != 2:
                    raise SablineError("E401",
                        f"'{node.name}' expects 2 argument(s) but got "
                        f"{len(node.args)}", node.line,
                        fixes=["pass a list and a predicate function"])
                t0 = infer(node.args[0])
                if not t0.startswith("List of "):
                    raise SablineError("E501",
                        f"'{node.name}' needs a list first, but this is "
                        f"{t0}", node.line, fixes=["pass a list"])
                elem = t0[len("List of "):]
                want_p = fmt_fn_type([elem], "Bool")
                parg = node.args[1]
                pf = (table.get(parg.name) if isinstance(parg, Var)
                      and parg.name not in env else None)
                if pf is not None and currency_generic(pf) \
                        and is_money(elem):
                    # a predicate generic only in its currency, like
                    # money.vel's not_negative, takes the list's (4.3)
                    ptypes = [t for _, t in pf.params]
                    if (len(ptypes) != 1 or not is_money(ptypes[0])
                            or (pf.return_type or "Unit") != "Bool"):
                        raise SablineError("E501",
                            f"'{node.name}' needs a {want_p} predicate, "
                            f"but '{pf.name}' is not one", node.line,
                            fixes=[f"pass a function taking {elem} and "
                                   f"returning Bool"])
                    if pf.effects or pf.can_fail:
                        raise SablineError("E530",
                            f"'{pf.name}' has effects or can fail - only "
                            f"pure functions can be passed as values",
                            node.line,
                            fixes=["pass a function with no 'uses' clause "
                                   "and no 'or fail'"])
                    cur = ptypes[0][len("Money of "):]
                    if cur not in pf.type_vars and ptypes[0] != elem:
                        raise clash_error(ptypes[0], elem, node.line,
                                          "each item")
                    return "Bool"
                t1 = infer(node.args[1])
                if t1 != want_p:
                    raise SablineError("E501",
                        f"'{node.name}' needs a {want_p} predicate, "
                        f"but this is {t1}", node.line,
                        fixes=[f"pass a function taking {elem} and "
                               f"returning Bool"])
                return wrap_secret("Bool") if carries(t0) else "Bool"
            if isinstance(node, Call) and node.name in (
                    "length", "push", "get", "put", "has", "keys",
                    "get_or", "pop", "slice", "set_at"):
                n_want = {"length": 1, "keys": 1, "push": 2, "get": 2,
                          "has": 2, "put": 3, "get_or": 3, "pop": 1,
                          "slice": 3, "set_at": 3}[node.name]
                if len(node.args) != n_want:
                    raise SablineError("E401",
                        f"'{node.name}' expects {n_want} argument(s) "
                        f"but got {len(node.args)}", node.line,
                        fixes=[f"pass exactly {n_want} argument(s)"])
                t0 = infer(node.args[0])
                # a container that is itself secret is read as what it
                # holds, and everything taken out of it comes back secret
                sec0 = is_secret(t0)
                if sec0:
                    t0 = secret_inner(t0)

                def keep0(t: str) -> str:
                    return (SECRET_PREFIX + t
                            if sec0 and not carries(t) else t)

                def keep_any(t: str) -> str:
                    """For a result that is about the container rather
                    than about what it holds: how many items there are,
                    which keys exist, whether one does.

                    This is secret when the *container* is - the length
                    of a `Secret of Text` is a secret - and not when
                    only its elements are. How many secrets a list holds
                    was decided by the pushes the program made, and a
                    program cannot have made those depend on a secret:
                    that would need a branch on one, which is E563. So
                    `length(List of Secret of Text)` is an ordinary Int,
                    and a program can walk a list of secrets."""
                    return (SECRET_PREFIX + t
                            if sec0 and not carries(t) else t)

                is_map = t0.startswith("Map of ")
                if is_map:
                    key_t, _, val_t = t0[len("Map of "):].partition(" to ")
                if node.name in ("pop", "slice", "set_at"):
                    if not allow_fail:
                        raise SablineError("E520",
                            f"'{node.name}' can fail - that cannot be "
                            f"ignored", node.line,
                            fixes=[f"handle it: check {node.name}(...) "
                                   f"{{ ok v {{ ... }} fail why "
                                   f"{{ ... }} }}",
                                   f"or pass it up (inside a fallible "
                                   f"function): try {node.name}(...)"])
                    if not t0.startswith("List of "):
                        raise SablineError("E501",
                            f"'{node.name}' works on a list, not {t0}",
                            node.line,
                            fixes=[f"pass a list to '{node.name}'"])
                    if node.name == "set_at":
                        want = t0[len("List of "):]
                        got = infer(node.args[2])
                        if currency_clash(want, got):
                            raise clash_error(want, got, node.line)
                        if got != want and want != "Any":
                            raise SablineError("E501",
                                f"this list holds {want}, so 'set_at' "
                                f"cannot put {got} in it", node.line,
                                fixes=[f"pass a {want}"])
                    for arg in node.args[1:3 if node.name == "slice" else 2]:
                        if node.name != "pop" and infer(arg) != "Int":
                            raise SablineError("E501",
                                f"'{node.name}' takes whole-number "
                                f"positions", node.line,
                                fixes=["pass an Int"])
                    return keep0(t0)
                if node.name == "length":
                    if t0 == "Text" or t0.startswith("List of ") or is_map:
                        return keep_any("Int")
                    raise SablineError("E501",
                        f"'length' works on Text, a list, or a map, "
                        f"but this is {t0}",
                        node.line, fixes=["pass a Text value, list, or map"])
                if node.name == "keys":
                    if not is_map:
                        raise SablineError("E501",
                            f"'keys' works on a map, but this is {t0}",
                            node.line, fixes=["pass a map"])
                    return keep_any("List of " + key_t)
                if node.name in ("has", "put"):
                    if not is_map:
                        raise SablineError("E501",
                            f"'{node.name}' works on a map, but this is {t0}",
                            node.line, fixes=["pass a map as the first argument"])
                    if infer(node.args[1]) != key_t:
                        raise SablineError("E501",
                            f"this map has {key_t} keys, but this key is "
                            f"{infer(node.args[1])}", node.line,
                            fixes=[f"use {'an' if key_t == 'Int' else 'a'} {key_t} key"])
                    if node.name == "has":
                        return keep_any("Bool")
                    if currency_clash(val_t, infer(node.args[2])):
                        raise clash_error(val_t, infer(node.args[2]),
                                          node.line)
                    if infer(node.args[2]) != val_t:
                        raise SablineError("E501",
                            f"this map holds {val_t} values, cannot put "
                            f"{infer(node.args[2])}", node.line,
                            fixes=[f"put {'an' if val_t == 'Int' else 'a'} {val_t} value"])
                    return keep0(t0)
                if node.name == "get_or":
                    if not is_map:
                        raise SablineError("E501",
                            f"'get_or' works on a map, but this is {t0}",
                            node.line, fixes=["pass a map first"])
                    if infer(node.args[1]) != key_t:
                        raise SablineError("E501",
                            f"this map has {key_t} keys, but this key is "
                            f"{infer(node.args[1])}", node.line,
                            fixes=[f"use {'an' if key_t == 'Int' else 'a'} "
                                   f"{key_t} key"])
                    if currency_clash(val_t, infer(node.args[2])):
                        raise clash_error(val_t, infer(node.args[2]),
                                          node.line, "the default")
                    if infer(node.args[2]) != val_t:
                        raise SablineError("E501",
                            f"this map holds {val_t} values, but the "
                            f"default is {infer(node.args[2])}", node.line,
                            fixes=[f"use {'an' if val_t == 'Int' else 'a'} "
                                   f"{val_t} default"])
                    return keep0(val_t)
                if node.name == "get" and is_map:
                    if not allow_fail:
                        raise SablineError("E520",
                            "'get' on a map can fail - the key may be "
                            "missing, and that cannot be ignored",
                            node.line,
                            fixes=["handle it: check get(m, key) "
                                   "{ ok v { ... } fail why { ... } }",
                                   "or use get_or(m, key, default) "
                                   "which never fails",
                                   "or pass it up with: try get(m, key)"])
                    if infer(node.args[1]) != key_t:
                        raise SablineError("E501",
                            f"this map has {key_t} keys, but this key is "
                            f"{infer(node.args[1])}", node.line,
                            fixes=[f"use {'an' if key_t == 'Int' else 'a'} {key_t} key"])
                    return keep0(val_t)
                if not t0.startswith("List of "):
                    raise SablineError("E501",
                        f"'{node.name}' needs a list first, but this is {t0}"
                        + (" - use put for maps" if node.name == "push" else ""),
                        node.line, fixes=["pass a list as the first argument"])
                elem = t0[len("List of "):]
                t1 = infer(node.args[1])
                if node.name == "push":
                    if currency_clash(elem, t1):
                        raise clash_error(elem, t1, node.line,
                                          "what is pushed")
                    if t1 != elem:
                        raise SablineError("E501",
                            f"this list holds {elem}, cannot push a {t1} into it",
                            node.line, fixes=[f"push {'an' if elem == 'Int' else 'a'} {elem} value"])
                    return keep0(t0)
                if t1 != "Int":                      # get
                    raise SablineError("E501",
                        f"'get' needs an Int position, but this is {t1}",
                        node.line, fixes=["positions are numbers, e.g. get(xs, 0)"])
                return keep0(elem)
            if isinstance(node, Call) and node.name in env \
                    and env[node.name].startswith("fn("):
                parts, ret = cast(tuple[list[str], str],
                                  fn_sig_parts(env[node.name]))
                if len(node.args) != len(parts):
                    raise SablineError("E401",
                        f"'{node.name}' expects {len(parts)} argument(s) "
                        f"but got {len(node.args)}", node.line,
                        fixes=[f"pass exactly {len(parts)} argument(s)"])
                for i, (a, want) in enumerate(zip(node.args, parts), 1):
                    got = infer(a)
                    if currency_clash(want, got):
                        raise clash_error(want, got, node.line,
                                          f"argument {i}")
                    if got != want:
                        raise SablineError("E501",
                            f"'{node.name}' needs {want} for argument {i}, "
                            f"but this is {got}", node.line,
                            fixes=[f"pass a {want} value"])
                return ret
            if isinstance(node, Call) and not allow_fail and \
                    builtin_reached(node.name, table) in FALLIBLE_BUILTINS:
                said = shown_name(node.name)
                raise SablineError("E520",
                    f"'{said}' can fail - that cannot be ignored",
                    node.line,
                    fixes=[f"handle it: check {said}(...) "
                           f"{{ ok v {{ ... }} fail reason {{ ... }} }}",
                           f"or pass it up (inside a fallible function): "
                           f"try {said}(...)"])
            if isinstance(node, Call) and \
                    builtin_reached(node.name, table) == "declassify":
                said = shown_name(node.name)
                if len(node.args) != 2:
                    raise SablineError("E401",
                        f"'{said}' expects 2 argument(s) but got "
                        f"{len(node.args)}", node.line,
                        fixes=['pass the secret and a reason: '
                               'declassify(key, "the vendor needs it")'])
                t0 = infer(node.args[0])
                if not is_secret(t0):
                    raise SablineError("E561",
                        f"'{said}' takes a Secret, but this is {t0}"
                        + (" - the secret is inside it, so take that out "
                           "first" if carries(t0) else ""), node.line,
                        fixes=["declassify the Secret itself, not what "
                               "holds it"])
                # the reason is written in the call, so that the audit can
                # report it without running the program (sabline-spec 8.6)
                if not isinstance(node.args[1], Str):
                    raise SablineError("E561",
                        f"the reason given to '{said}' must be written as "
                        f"text in the call", node.line,
                        fixes=['write it here: declassify(x, "the vendor '
                               'authenticates with this key")',
                               "a reason built while running cannot be "
                               "read by the audit, so it would say that a "
                               "secret leaves and not why"])
                if not node.args[1].value.strip():
                    raise SablineError("E561",
                        f"the reason given to '{said}' is empty", node.line,
                        fixes=["say why this value is safe to let out; it "
                               "is what an operator reads in the audit"])
                return secret_inner(t0)
            if isinstance(node, Call) and \
                    builtin_reached(node.name, table) in HMAC_BUILTINS:
                # hmac_sha256(key, message) and hmac_sha256_chain(key,
                # messages) (8.5): the key is a Secret of Text and nothing
                # else, the message carries no secret - a MAC of a secret
                # message under a key the program chose would be a digest of
                # that message in the open - and what comes back is a Text.
                # The `declassify` effect it needs is the effect checker's.
                said = shown_name(node.name)
                if len(node.args) != 2:
                    raise SablineError("E401",
                        f"'{said}' expects 2 argument(s) but got "
                        f"{len(node.args)}", node.line,
                        fixes=["pass the key and what to sign: "
                               f"{said}(key, message)"])
                t0 = infer(node.args[0])
                if t0 != wrap_secret("Text"):
                    raise SablineError("E561",
                        f"'{said}' takes its key as a Secret of Text, but "
                        f"this is {t0}", node.line,
                        fixes=["read the key with env() or "
                               "read_file_secret(), which give a Secret of "
                               "Text; a key that is not a secret needs no "
                               "protecting and cannot be given here"])
                want = ("Text" if builtin_reached(node.name, table)
                        == "hmac_sha256" else "List of Text")
                t1 = infer(node.args[1])
                if carries(t1):
                    raise leak(f"argument 2 of '{said}'",
                               f"the result of '{said}' is not a Secret, so "
                               f"what it signs would leave as a digest",
                               t1, origin_of(node.args[1]), node.line)
                if t1 != want:
                    raise SablineError("E501",
                        f"'{said}' needs {want} for argument 2, but this is "
                        f"{t1}", node.line, fixes=[f"pass a {want} value"])
                return "Text"
            if isinstance(node, Call) and \
                    builtin_reached(node.name, table) in MONEY_BUILTINS:
                return money_call(cast(str, builtin_reached(node.name, table)),
                                  node)
            if isinstance(node, Call) and (cg := table.get(node.name)) \
                    is not None and cg.type_vars:
                if cg.can_fail and not allow_fail:
                    raise SablineError("E520",
                        f"'{node.name}' can fail - that cannot be ignored",
                        node.line,
                        fixes=["handle it with a check block",
                               f"or pass it up with try {node.name}(...)"])
                ptypes = [t for _, t in cg.params]
                if len(node.args) != len(ptypes):
                    raise SablineError("E401",
                        f"'{node.name}' expects {len(ptypes)} argument(s) "
                        f"but got {len(node.args)}", node.line,
                        fixes=[f"pass exactly {len(ptypes)} argument(s)"])
                tvset = set(cg.type_vars)
                bind: dict[str, str] = {}

                def unify(want: str, got: str) -> bool:
                    if want in tvset:
                        if want in bind:
                            return bind[want] == got
                        bind[want] = got
                        return True
                    if want == got:
                        return True
                    if is_money(want) and is_money(got):
                        return unify(want[9:], got[9:])   # the currency
                    if is_secret(want) and is_secret(got):
                        return unify(secret_inner(want), secret_inner(got))
                    if want.startswith("List of ") and \
                            got.startswith("List of "):
                        return unify(want[8:], got[8:])
                    if want.startswith("Map of ") and \
                            got.startswith("Map of "):
                        wk, _, wv = want[7:].partition(" to ")
                        gk, _, gv = got[7:].partition(" to ")
                        return unify(wk, gk) and unify(wv, gv)
                    wf, gf = fn_sig_parts(want), fn_sig_parts(got)
                    if wf is not None and gf is not None:
                        (wp, wr), (gp, gr) = wf, gf
                        return len(wp) == len(gp) and all(
                            unify(a, b) for a, b in zip(wp, gp)) and \
                            unify(wr, gr)
                    return False

                def subst(t: str) -> str:
                    if t in bind:
                        return bind[t]
                    if is_secret(t):
                        return SECRET_PREFIX + subst(secret_inner(t))
                    if is_money(t):
                        return "Money of " + subst(t[9:])
                    if t.startswith("List of "):
                        return "List of " + subst(t[8:])
                    if t.startswith("Map of "):
                        k, _, v = t[7:].partition(" to ")
                        return f"Map of {subst(k)} to {subst(v)}"
                    sig = fn_sig_parts(t)
                    if sig is not None:
                        parts, ret = sig
                        return fmt_fn_type([subst(p) for p in parts],
                                           subst(ret))
                    return t

                for i, (a, want) in enumerate(zip(node.args, ptypes), 1):
                    got = infer(a)
                    if not unify(want, got):
                        if currency_clash(subst(want), got):
                            raise clash_error(subst(want), got, node.line,
                                              f"argument {i}")
                        so_far = ", ".join(f"{k} = {v}"
                                           for k, v in bind.items())
                        raise SablineError("E542",
                            f"'{node.name}' argument {i} should look like "
                            f"{want}, but this is {got}"
                            + (f" (so far: {so_far})" if so_far else ""),
                            node.line,
                            fixes=["make the arguments agree on what "
                                   f"{', '.join(cg.type_vars)} is"])

                # A generic body is checked once, with its type
                # variables standing for nothing in particular. Inside
                # it a value of type T can be compared (`got == item`
                # gives a plain Bool there), handed to `to_text`, or
                # printed - none of which the checker can see as
                # touching a secret, because there is no secret in
                # sight. Bind T to one at a call site and those become
                # an oracle that hands the caller an ordinary Bool, Int
                # or Text: `contains_item([guess], key)` is exactly
                # that. So **no type variable is ever bound to a type
                # that carries a secret** (E560).
                #
                # It is a blunt rule and it is the sound one. The way
                # to write a generic function over secrets is to say so
                # in its signature - `fn pass(s: Secret of T) ->
                # Secret of T for any T` binds T to Text, which carries
                # nothing - and then the body is checked knowing what
                # it holds.
                for tv, bound in bind.items():
                    if carries(bound):
                        at = next((j for j, (_, w) in
                                   enumerate(zip(node.args, ptypes), 1)
                                   if type_mentions(w, tv)), 1)
                        raise leak(
                            f"argument {at} of '{node.name}'",
                            f"'{node.name}' is generic, and its body was "
                            f"checked without knowing that {tv} could be "
                            f"a secret - so it may compare one, or hand "
                            f"one to to_text, and give the answer back as "
                            f"an ordinary value", bound,
                            origin_of(node.args[at - 1]), node.line)
                return subst(cg.return_type or "Unit")
            if isinstance(node, Call):
                cfn = table.get(node.name)
                if cfn is not None and cfn.can_fail and not allow_fail:
                    raise SablineError("E520",
                        f"'{node.name}' can fail - that cannot be ignored",
                        node.line,
                        fixes=[f"handle it: check {node.name}(...) "
                               f"{{ ok v {{ ... }} fail reason {{ ... }} }}",
                               f"or pass it up (inside a fallible "
                               f"function): try {node.name}(...)"])
                ptypes, ret = callee_sig(node.name, node.line)
                if node.name == "format":          # text, then one value
                    if not node.args:              # per {} placeholder
                        raise SablineError("E401",
                            "'format' needs the text first", node.line,
                            fixes=['write: format("hi {}", name)'])
                    t_fmt = infer(node.args[0])
                    if strip_secret(t_fmt) != "Text":
                        raise SablineError("E501",
                            "'format' needs Text as its first argument",
                            node.line, fixes=['write: format("hi {}", name)'])
                    secret_in = carries(t_fmt)
                    for a in node.args[1:]:
                        secret_in = carries(infer(a)) or secret_in
                    if isinstance(node.args[0], Str):   # literal: check now
                        holes = node.args[0].value.count("{}")
                        given = len(node.args) - 1
                        if holes != given:
                            raise SablineError("E406",
                                f"this text has {holes} placeholder(s) "
                                f"but got {given} value(s)", node.line,
                                fixes=[f"pass exactly {holes} value(s)",
                                       "each {} takes one value"])
                    return wrap_secret("Text") if secret_in else "Text"
                if len(node.args) != len(ptypes):
                    raise SablineError("E401",
                        f"'{node.name}' expects {len(ptypes)} argument(s) "
                        f"but got {len(node.args)}", node.line,
                        fixes=[f"pass exactly {len(ptypes)} argument(s)"])
                secret_in = False
                for i, (arg, want) in enumerate(zip(node.args, ptypes), 1):
                    got = infer(arg)
                    if got == "Unit":
                        raise SablineError("E502",
                            f"argument {i} of '{node.name}' is a call to a "
                            f"function that returns nothing", node.line,
                            fixes=["call a function that returns a value here"])
                    if currency_clash(want, got):
                        raise clash_error(want, got, node.line,
                                          f"argument {i} of '{node.name}'")
                    # a pure builtin over a secret keeps the secret: what
                    # it hands back was computed from one. The comparison
                    # is on the type underneath, so to_int(key) is the
                    # to_int of a Text and gives a Secret of Int.
                    if carries(got) and builtin_reached(node.name, table) \
                            is not None:
                        if want == "Any":
                            secret_in = True
                        elif strip_secret(got) == want:
                            secret_in = True
                            got = strip_secret(got)
                    if want != "Any" and got != want:
                        if (node.name in table and node.name in BUILTINS
                                and builtin_reached(node.name, table)):
                            raise SablineError("E501",
                                f"'{node.name}' here is the builtin, which "
                                f"needs {want} for argument {i}; the "
                                f"function '{node.name}' of this program "
                                f"is hidden by it", node.line,
                                fixes=[f"rename your '{node.name}'",
                                       "or import its file with a name: "
                                       'import "money.vel" as money'])
                        raise SablineError("E501",
                            f"'{node.name}' needs {want} for argument {i}, "
                            f"but this is {got}", node.line,
                            fixes=[f"pass {'an' if want == 'Int' else 'a'} {want} value instead",
                                   f"or change the parameter type to {got}"])
                return wrap_secret(ret) if secret_in else ret
            if isinstance(node, BinOp):
                l, r = infer(node.left), infer(node.right)  # noqa: E741
                # An operator over a secret works on what is underneath
                # and hands back a secret - except a comparison, which
                # hands back an ordinary Bool. SPEC.md 3.1 states that
                # choice and what it costs: `if key == ""` has to be
                # writable, and refusing the Bool while allowing the
                # branch would stop nothing. A comparison may also put a
                # secret beside a plain value of the same type, which is
                # the only place the two mix.
                secret_in = carries(l) or carries(r)
                if secret_in:
                    l, r = strip_secret(l), strip_secret(r)  # noqa: E741

                def kept(t: str) -> str:
                    """A result computed from a secret is a secret - a
                    Bool from a comparison included (SPEC.md 3.1)."""
                    return (SECRET_PREFIX + t
                            if secret_in and not carries_secret(t) else t)

                if "Unit" in (l, r):
                    raise SablineError("E502",
                        "this expression uses a function that returns nothing",
                        node.line, fixes=["only use functions that return a value in math/text"])
                op = node.op
                if op in ("and", "or"):
                    if l == "Bool" and r == "Bool":
                        # a Bool a program declared secret stays secret
                        # here: only a comparison makes a plain one
                        return kept("Bool")
                    raise SablineError("E501",
                        f"'{op}' needs yes/no values (Bool) on both sides, "
                        f"but this is {l} {op} {r}", node.line,
                        fixes=["use comparisons on both sides, like x > 0 and x < 10"])
                NUM_FIX = ["make both sides the same number type",
                           "convert with to_float(x), or round(x) for an Int"]
                if (is_money(l) or is_money(r)) and not (
                        op == "+" and "Text" in (l, r)):
                    got = money_op(op, l, r, node.line)
                    return got if got == "Bool" else kept(got)
                if op == "+":
                    if l == "Text" or r == "Text":
                        return kept("Text")            # text joining, e.g. "n: " + 5
                    if l == r and l in ("Int", "Float"):
                        return kept(l)
                    raise SablineError("E501", f"cannot add {l} and {r}",
                                       node.line, fixes=NUM_FIX)
                if op == "%":
                    if l == "Int" and r == "Int":
                        return kept("Int")
                    raise SablineError("E501",
                        f"'%' needs Int on both sides, but this is {l} % {r}",
                        node.line, fixes=["make both sides Int"])
                if op in ("-", "*", "/"):
                    if l == r and l in ("Int", "Float"):
                        return kept(l)
                    raise SablineError("E501",
                        f"'{op}' needs matching number types, but this is "
                        f"{l} {op} {r}", node.line, fixes=NUM_FIX)
                if op in ("<", ">", "<=", ">="):
                    if l == r and l in ("Int", "Float", "Text"):
                        return kept("Bool")   # Text compares alphabetically
                    raise SablineError("E501",
                        f"'{op}' compares two Ints, two Floats, or two "
                        f"Texts, but this is {l} {op} {r}", node.line,
                        fixes=NUM_FIX)
                if l != r:                             # == and !=
                    raise SablineError("E501",
                        f"cannot compare {l} with {r}", node.line,
                        fixes=["compare values of the same type"])
                return kept("Bool")

        def check_stmt(node: Any) -> None:
            if isinstance(node, Let):
                no_shadow(node.name, node.line)
                if node.ann is not None:
                    if not valid_type(node.ann, frozenset(fn.type_vars)):
                        raise bad_type(node.ann, frozenset(fn.type_vars),
                                       f"unknown type '{node.ann}'",
                                       node.line)
                    empty_list = (isinstance(node.value, ListLit)
                                  and not node.value.items)
                    empty_map = (isinstance(node.value, MapLit)
                                 and not node.value.entries)
                    if empty_list or empty_map:
                        want_kind = "List of " if empty_list else "Map of "
                        if not node.ann.startswith(want_kind):
                            raise SablineError("E501",
                                f"'{node.name}' is declared {node.ann}, "
                                f"but this is an empty "
                                f"{'list' if empty_list else 'map'}",
                                node.line,
                                fixes=["match the declared type and the "
                                       "value"])
                        env[node.name] = node.ann
                        return
                    t = infer(node.value)
                    if currency_clash(node.ann, t):
                        raise clash_error(node.ann, t, node.line,
                                          f"'{node.name}'")
                    if t != node.ann:
                        raise SablineError("E501",
                            f"'{node.name}' is declared {node.ann}, "
                            f"but this is {t}", node.line,
                            fixes=[f"give {'an' if node.ann == 'Int' else 'a'} "
                                   f"{node.ann} value",
                                   "or fix the declared type"])
                    env[node.name] = t
                    if carries(t):
                        origins[node.name] = origin_of(node.value)
                    return
                t = infer(node.value)
                if t == "Unit":
                    raise SablineError("E502",
                        f"'{node.name}' would hold nothing: that function "
                        f"returns no value", node.line,
                        fixes=["assign a function that returns a value"])
                env[node.name] = t
                if carries(t):
                    origins[node.name] = origin_of(node.value)
            elif isinstance(node, Return):
                if node.value is None:
                    if declared_ret != "Unit":
                        raise SablineError("E503",
                            f"'{fn.name}' promises to return {declared_ret} "
                            f"but this return gives nothing", node.line,
                            fixes=[f"return a {declared_ret} value"])
                    return
                t = infer(node.value)
                if declared_ret == "Unit":
                    raise SablineError("E503",
                        f"'{fn.name}' does not declare a return type "
                        f"but returns a {t}", node.line,
                        fixes=[f"add '-> {t}' to the signature of '{fn.name}'",
                               "or remove the returned value"])
                if currency_clash(declared_ret, t):
                    raise clash_error(declared_ret, t, node.line,
                                      "what this returns")
                if t != declared_ret:
                    raise SablineError("E503",
                        f"'{fn.name}' promises to return {declared_ret} "
                        f"but this returns {t}", node.line,
                        fixes=[f"return a {declared_ret} value",
                               f"or change the signature to '-> {t}'"])
            elif isinstance(node, ExprStmt):
                infer(node.expr)
            elif isinstance(node, FailStmt):
                if not fn.can_fail:
                    raise SablineError("E523",
                        f"'fail' is used, but '{fn.name}' does not declare "
                        f"it can fail", node.line,
                        fixes=[f"add 'or fail' to the signature of "
                               f"'{fn.name}'"])
                t = infer(node.value)
                if carries(t):
                    raise leak("the reason given to 'fail'",
                               "a failure's reason is shown to whoever "
                               "runs the program", t, origin_of(node.value),
                               node.line)
                if t != "Text":
                    raise SablineError("E501",
                        f"'fail' needs a Text reason, but this is {t}",
                        node.line, fixes=['write a message: fail "why"'])
            elif isinstance(node, Check):
                callee = table.get(node.subject.name)
                user_ok = callee is not None and callee.can_fail
                if not user_ok and not builtin_call_fallible(node.subject,
                                                             infer):
                    raise SablineError("E522",
                        f"'{shown_name(node.subject.name)}' cannot fail - "
                        f"call it directly, no check needed", node.line,
                        fixes=["remove the check block"])
                rt = infer(node.subject, allow_fail=True)
                if rt == "Unit" and node.ok_name is not None:
                    raise SablineError("E525",
                        f"'{node.subject.name}' returns nothing - "
                        f"write 'ok {{ ... }}' with no name", node.line,
                        fixes=["remove the name after ok"])
                if rt != "Unit" and node.ok_name is None:
                    raise SablineError("E525",
                        "name the result: 'ok value { ... }'", node.line,
                        fixes=["add a name after ok to hold the result"])
                if node.ok_name is not None:
                    env[node.ok_name] = rt
                    if carries(rt):
                        origins[node.ok_name] = origin_of(node.subject)
                for s in node.ok_body:
                    check_stmt(s)
                env[node.fail_name] = "Text"
                for s in node.fail_body:
                    check_stmt(s)
            elif isinstance(node, If):
                c = infer(node.cond)
                no_secret_branch("if", c, node, origin_of(node.cond))
                if c != "Bool":
                    raise SablineError("E504",
                        f"'if' needs a yes/no condition (Bool), but this is {c}",
                        node.line, fixes=["use a comparison like x > 0"])
                for s in node.then + node.other:
                    check_stmt(s)
            elif isinstance(node, While):
                c = infer(node.cond)
                no_secret_branch("while", c, node, origin_of(node.cond))
                if c != "Bool":
                    raise SablineError("E504",
                        f"'while' needs a yes/no condition (Bool), but this is {c}",
                        node.line, fixes=["use a comparison like i < 10"])
                for inv_expr, iline in node.invariants:
                    if strip_secret(infer(inv_expr)) != "Bool":
                        raise SablineError("E505",
                            "'invariant' must be a yes/no promise (Bool)",
                            iline, fixes=["use a comparison like total >= 0"])
                for s in node.body:
                    check_stmt(s)
            elif isinstance(node, Assign):
                if node.name not in env:
                    raise SablineError("E402",
                        f"unknown variable '{node.name}'", node.line,
                        fixes=[f"declare it first: let {node.name} = ..."])
                t = infer(node.value)
                have = env[node.name]
                if currency_clash(have, t):
                    raise clash_error(have, t, node.line,
                                      f"what is put in '{node.name}'")
                if t != have:
                    raise SablineError("E501",
                        f"'{node.name}' holds {have}, cannot put a {t} in it",
                        node.line,
                        fixes=[f"assign {'an' if have == 'Int' else 'a'} {have} value",
                               f"or make a new variable: let {node.name}2 = ..."])
                if carries(t):
                    origins[node.name] = origin_of(node.value)

        # ---- Money (4.3): the rules an amount's type carries ----------
        UNITS_FIX = ['money(1250, "INR") is an amount of 1250 minor units',
                     "units_of(m) is an amount's minor units, as an Int"]

        def money_op(op: str, l: str, r: str, line: int) -> str:  # noqa: E741
            lm, rm = is_money(l), is_money(r)
            if op in ("/", "%"):
                if lm and not rm:
                    raise SablineError("E553",
                        f"'{op}' on an amount would round without saying "
                        f"how", line,
                        fixes=['divide_or_fail(amount, n, "half_even") '
                               "names the rounding",
                               "money.split(amount, n) makes n parts that "
                               "add up to the amount exactly",
                               'percent_of(amount, numerator, denominator, '
                               '"half_up") for a share'])
                raise SablineError("E501",
                    f"'{op}' cannot divide by an amount: this is "
                    f"{l} {op} {r}", line, fixes=UNITS_FIX)
            if "Float" in (l, r):
                raise SablineError("E501",
                    f"an amount never meets a Float: this is {l} {op} {r}",
                    line, fixes=["a Float cannot hold 0.10 exactly; keep "
                                 "the amount in minor units",
                                 'percent_of(amount, 25, 1000, "half_up") '
                                 "takes 2.5 per cent without one"])
            if op == "*":
                if lm and rm:
                    raise SablineError("E501",
                        f"an amount times an amount has no meaning: this "
                        f"is {l} * {r}", line,
                        fixes=["multiply an amount by an Int: price * 3",
                               'percent_of(amount, numerator, denominator, '
                               '"half_up") for a share of one'])
                other = r if lm else l
                if other != "Int":
                    raise SablineError("E501",
                        f"an amount multiplies by an Int, not {other}",
                        line, fixes=["multiply an amount by an Int: price "
                                     "* 3"])
                return l if lm else r
            if lm and rm:
                if l != r:
                    raise clash_error(l, r, line,
                        "the right side" if op in ("+", "-")
                        else "one side")
                return l if op in ("+", "-") else "Bool"
            if op in ("+", "-"):
                raise SablineError("E501",
                    f"an amount adds only to an amount: this is "
                    f"{l} {op} {r}", line, fixes=UNITS_FIX)
            raise SablineError("E501",
                f"an amount compares only with an amount: this is "
                f"{l} {op} {r}", line,
                fixes=['compare with an amount: m >= money(0, "INR")',
                       "or compare units_of(m) with an Int"])

        def written_currency(arg: Any, line: int) -> str:
            if not isinstance(arg, Str):
                raise SablineError("E551",
                    "the currency must be written in the call, as text",
                    line, fixes=['write it there: money(1250, "INR")'])
            if arg.value not in CURRENCIES:
                raise unknown_currency(arg.value, line)
            return arg.value

        def written_rounding(arg: Any, line: int) -> None:
            if not (isinstance(arg, Str) and arg.value in ROUNDING):
                raise SablineError("E552",
                    "the rounding mode must be written in the call: "
                    '"half_up", "half_even" or "down"', line,
                    fixes=['"half_up" takes a half away from zero, '
                           '"half_even" to the even neighbour, "down" '
                           "toward zero",
                           "there is no default: a division that does "
                           "not come out even says how it rounds"])

        def money_call(b: str, node: Any) -> str:
            want_n = {"money": 2, "units_of": 1, "with_units": 2,
                      "percent_of": 4, "divide_or_fail": 3, "text_of": 1,
                      "parse_money": 2}[b]
            if len(node.args) != want_n:
                raise SablineError("E401",
                    f"'{b}' expects {want_n} argument(s) but got "
                    f"{len(node.args)}", node.line,
                    fixes=[f"pass exactly {want_n} argument(s)"])
            types = [infer(a) for a in node.args]

            def need(i: int, want: str) -> None:
                if types[i] != want:
                    raise SablineError("E501",
                        f"'{b}' needs {want} for argument {i + 1}, but "
                        f"this is {types[i]}", node.line,
                        fixes=[f"pass {'an' if want == 'Int' else 'a'} "
                               f"{want}"])

            def amount(i: int) -> str:
                if not is_money(types[i]):
                    raise SablineError("E501",
                        f"'{b}' needs an amount for argument {i + 1}, but "
                        f"this is {types[i]}", node.line, fixes=UNITS_FIX)
                return types[i]

            if b in ("money", "parse_money"):
                need(0, "Int" if b == "money" else "Text")
                return "Money of " + written_currency(node.args[1],
                                                      node.line)
            if b == "units_of":
                t = types[0]
                if is_money(t) or (t.startswith("List of ")
                                   and is_money(t[8:])):
                    return "Int"
                raise SablineError("E501",
                    f"'units_of' takes an amount or a list of amounts, "
                    f"but this is {t}", node.line, fixes=UNITS_FIX)
            if b == "text_of":
                amount(0)
                return "Text"
            if b == "with_units":
                need(1, "Int")
                return amount(0)
            if b == "percent_of":
                need(1, "Int")
                need(2, "Int")
                written_rounding(node.args[3], node.line)
                return amount(0)
            need(1, "Int")                                  # divide_or_fail
            written_rounding(node.args[2], node.line)
            return amount(0)

        # Contracts are checked first, while env holds exactly the
        # parameters. A promise may be about a secret - `requires
        # length(key) > 0` is exactly the kind of thing to promise -
        # so a `Secret of Bool` is a promise, where it is not a branch
        # (E563). It is not one for a reason: a broken promise stops
        # the run, cannot be caught and cannot accumulate, so it tells
        # a reader at most one bit per run rather than reading a secret
        # out in a loop, and the message it prints redacts the values
        # whose type is secret. SPEC.md 3.1 says so, and THREAT_MODEL.md
        # lists the bit-per-run that remains.
        for expr, cline in fn.requires:
            if strip_secret(infer(expr)) != "Bool":
                raise SablineError("E505",
                    "'requires' must be a yes/no promise (Bool)", cline,
                    fixes=["use a comparison like price >= 0"])
        if fn.ensures:
            if declared_ret != "Unit":
                env["result"] = declared_ret
            for expr, cline in fn.ensures:
                if strip_secret(infer(expr)) != "Bool":
                    raise SablineError("E505",
                        "'ensures' must be a yes/no promise (Bool)", cline,
                        fixes=["use a comparison like result >= 0"])
            env.pop("result", None)

        # Recovery at statement boundaries (8.0): a problem in one
        # top-level statement is recorded and checking goes on to the
        # next, so `sabline check` reports every error it can in one
        # pass rather than only the first. The first error is still the
        # one a single-error run would give - SPEC.md 14 says the first
        # is authoritative - and the rest may be its consequences. A
        # statement that a nested error aborted stops there; the boundary
        # is the top-level statement.
        would_have_bound: set[Any] = set()
        for stmt in fn.body:
            try:
                check_stmt(stmt)
            except SablineError as e:
                # suppress the obvious cascade: an "unknown variable"
                # error for a name an earlier failed `let` would have
                # bound is a consequence of that failure, not a new one
                if e.code == "E402" and any(
                        f"'{n}'" in e.message for n in would_have_bound):
                    pass
                else:
                    errors.append(blame(fn, e))
                if isinstance(stmt, Let):
                    would_have_bound.add(stmt.name)

    m = table.get("main")
    if m is not None and m.can_fail:
        errors.append(blame(m, SablineError("E524",
            "'main' cannot be 'or fail' - there is no one above it to "
            "handle the failure", m.line,
            fixes=["handle failures inside main with check blocks"])))
    # what the tracer and a broken promise must not print (6.0): the
    # names whose type holds a secret, and whether the result does.
    # Nothing refuses a program because of this - it is redaction, and
    # the refusals above are what keeps a secret in.
    for fn in funcs:
        fn.secret_params = {p for p, t in fn.params  # type: ignore[attr-defined]  # set here, not a dataclass field, so a node's fields, repr and equality stay as they were
                            if carries_secret(t, rec_carries)}
        fn.secret_params |= {c for c, t in getattr(fn, "captures", [])  # type: ignore[attr-defined]  # set here, not a dataclass field, so a node's fields, repr and equality stay as they were
                             if carries_secret(t, rec_carries)}
        fn.secret_result = carries_secret(fn.return_type or "", rec_carries)  # type: ignore[attr-defined]  # set here, not a dataclass field, so a node's fields, repr and equality stay as they were

    for fn in funcs:
        if getattr(fn, "is_lambda", False) and getattr(fn, "free_names", []):
            continue      # checked at its creation site, where the names
                          # it carries actually mean something
        try:
            check_fn(fn)
        except SablineError as e:
            errors.append(blame(fn, e))
