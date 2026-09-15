"""Stage 4, the effect checker: a function may cause only the effects it
declares, transitively.
"""
import os

from .version import _INSTALL_DIR
from .errors import VelarisError
from .nodes import (
    Assign,
    BinOp,
    Block,
    Call,
    Check,
    Closure,
    ExprStmt,
    FailStmt,
    FieldGet,
    Function,
    If,
    Let,
    ListLit,
    MapLit,
    Neg,
    Not,
    RecordLit,
    Return,
    TryExpr,
    Var,
    While,
)
from .tables import ALL_EFFECTS, BUILTINS, NEW_BUILTINS, builtin_reached
from .loader import blame, unknown_function
from typing import Any, cast


def local_names_of(fn: Function) -> set[str]:
    out = {p for p, _ in fn.params}

    def gather(stmts: Any) -> None:
        for s in stmts:
            if isinstance(s, (Let, Assign)):
                out.add(s.name)
            elif isinstance(s, If):
                gather(s.then)
                gather(s.other)
            elif isinstance(s, While):
                gather(s.body)
            elif isinstance(s, Check):
                if s.ok_name:
                    out.add(s.ok_name)
                out.add(s.fail_name)
                gather(s.ok_body)
                gather(s.fail_body)
    gather(fn.body)
    return out


def function_locals_of(fn: Function, table: dict[Any, Any]) -> set[str]:
    """The locals of `fn` that hold a function value: a parameter of
    function type, and a `let` whose annotation is a function type or whose
    value is a function value written there - an inline function, the name
    of one of the program's functions, or another such local."""
    out = {p for p, t in fn.params if str(t).startswith("fn(")}

    def gather(stmts: Any) -> None:
        for s in stmts:
            if isinstance(s, Let):
                if (s.ann or "").startswith("fn(") \
                        or isinstance(s.value, Closure) \
                        or (isinstance(s.value, Var)
                            and (s.value.name in table or s.value.name in out)):
                    out.add(s.name)
            elif isinstance(s, If):
                gather(s.then)
                gather(s.other)
            elif isinstance(s, While):
                gather(s.body)
            elif isinstance(s, Block):
                gather(s.stmts)
            elif isinstance(s, Check):
                gather(s.ok_body)
                gather(s.fail_body)
    gather(fn.body)
    return out


def check_effects(funcs: list[Function], errors: list[Any]) -> None:
    table = {f.name: f for f in funcs}

    # A function named like a built-in is refused (E204, 8.0), rather than
    # silently shadowed by the built-in as it was through 7.x. The one
    # exception is the rule of SPEC.md 10.1: a built-in added in 4.3 or
    # later (NEW_BUILTINS - the Money and Secret builtins) gives way to a
    # program's own function of the same name, so that adding one did not
    # break a program that had used the name. Those are still allowed; the
    # older built-ins, which a program could never have shadowed anyway
    # (the built-in always won), are now a clear error rather than a name
    # that reads as a call to code that never runs. A namespaced function
    # (`http.get`, from `import "http.vel" as http`) carries its prefix and
    # is not a bare built-in name, so it is unaffected.
    _stdlib_dir = os.path.join(_INSTALL_DIR,
                               "stdlib")
    for f in funcs:
        n = f.name
        try:
            in_stdlib = os.path.realpath(f.src_file or "").startswith(
                os.path.realpath(_stdlib_dir) + os.sep)
        except (OSError, ValueError):
            in_stdlib = False
        # the shipped standard library is always imported under a name, so
        # its `split`/`get` become `money.split`/`http.get`; it may keep the
        # built-in names it was written with, and only a program's own file
        # is held to E204
        if in_stdlib:
            continue
        if ("." not in n and n in BUILTINS and n not in NEW_BUILTINS):
            errors.append(blame(f, VelarisError("E204",
                f"'{n}' is the name of a built-in, so a function called "
                f"'{n}' would shadow it; through 7.x the built-in silently "
                f"won and this function was never reached", f.line,
                fixes=[f"rename the function (a built-in named '{n}' already "
                       f"does that job)",
                       "or import it under a name, so it is reached as "
                       "prefix." + n])))

    def effects_of_callee(name: str, line: int) -> set[str]:
        builtin = builtin_reached(name, table)
        if builtin is not None:
            return cast(set[str], BUILTINS[builtin]["effects"])
        if name in table:
            return table[name].effects
        raise unknown_function(name, line, table)

    locals_cache: dict[str, set[Any]] = {}
    value_locals: dict[str, set[Any]] = {}

    def calls_a_value(node: Call, fn: Function) -> bool:
        """Whether a call runs a function value held in a local, rather than
        a built-in or one of the program's functions. The runtime calls a
        local only when it holds a function value (runtime.py), so a local
        holding anything else does not hide the call from this check when
        it is named like a built-in or like a function of the program:
        until 8.2, `let print = 0` let a pure function print, and `let
        shout = 0` let it call a function with effects."""
        if fn.name not in locals_cache:
            locals_cache[fn.name] = local_names_of(fn)
            value_locals[fn.name] = function_locals_of(fn, table)
        if node.name not in locals_cache[fn.name]:
            return False
        return node.name in value_locals[fn.name] or (
            builtin_reached(node.name, table) is None
            and node.name not in table)

    def walk(node: Any, fn: Function) -> None:
        if isinstance(node, Call):
            if calls_a_value(node, fn):
                for a in node.args:          # a passed-in function is pure
                    walk(a, fn)
                return
            needed = effects_of_callee(node.name, node.line)
            missing = needed - fn.effects
            if missing == {"env"} and node.name == "env":
                # since 3.0 the environment is its own effect, so an
                # io-only budget cannot read secrets; the message says
                # exactly what changed
                raise VelarisError(
                    "E300", "env() now needs 'uses env'", node.line,
                    fixes=[f"add 'uses env' to the signature of "
                           f"'{fn.name}' (and to every function that "
                           f"calls it)",
                           "run it with --allow io,env, or drop the "
                           "env() call"])
            if missing:
                eff = ", ".join(sorted(missing))
                declared = ("declares no effects (it is pure)" if not fn.effects
                            else f"only declares 'uses {', '.join(sorted(fn.effects))}'")
                raise VelarisError(
                    "E300",
                    f"function '{fn.name}' calls '{node.name}' which needs "
                    f"effect '{eff}', but '{fn.name}' {declared}",
                    node.line,
                    fixes=[f"add 'uses {eff}' to the signature of '{fn.name}'",
                           f"remove the call to '{node.name}'"],
                )
            for a in node.args:
                walk(a, fn)
        elif isinstance(node, BinOp):
            walk(node.left, fn)
            walk(node.right, fn)
        elif isinstance(node, (Let, Return, ExprStmt, FailStmt)):
            inner = node.expr if isinstance(node, ExprStmt) else node.value
            if inner is not None:
                walk(inner, fn)
        elif isinstance(node, TryExpr):
            walk(node.value, fn)
        elif isinstance(node, Check):
            walk(node.subject, fn)
            for s in node.ok_body + node.fail_body:
                walk(s, fn)
        elif isinstance(node, If):
            walk(node.cond, fn)
            for s in node.then + node.other:
                walk(s, fn)
        elif isinstance(node, While):
            walk(node.cond, fn)
            for inv_expr, _ in node.invariants:
                walk_pure(inv_expr, fn, "invariant")
            for s in node.body:
                walk(s, fn)
        elif isinstance(node, Assign):
            walk(node.value, fn)
        elif isinstance(node, (Not, Neg)):
            walk(node.value, fn)
        elif isinstance(node, ListLit):
            for it in node.items:
                walk(it, fn)
        elif isinstance(node, MapLit):
            for k, v in node.entries:
                walk(k, fn)
                walk(v, fn)
        elif isinstance(node, FieldGet):
            walk(node.obj, fn)
        elif isinstance(node, RecordLit):
            for _, v in node.fields:
                walk(v, fn)

    def walk_pure(node: Any, fn: Function, where: str) -> None:
        if isinstance(node, Call):
            if calls_a_value(node, fn):
                for a in node.args:
                    walk_pure(a, fn, where)
                return
            eff = effects_of_callee(node.name, node.line)
            if eff:
                raise VelarisError("E310",
                    f"the '{where}' promise of '{fn.name}' calls "
                    f"'{node.name}' which has effects "
                    f"({', '.join(sorted(eff))}); promises must be pure",
                    node.line,
                    fixes=["only use pure functions and math inside promises"])
            for a in node.args:
                walk_pure(a, fn, where)
        elif isinstance(node, BinOp):
            walk_pure(node.left, fn, where)
            walk_pure(node.right, fn, where)
        elif isinstance(node, (Not, Neg)):
            walk_pure(node.value, fn, where)
        elif isinstance(node, TryExpr):
            raise VelarisError("E310",
                f"the '{where}' promise of '{fn.name}' uses 'try'; "
                f"promises must be simple and pure", node.line,
                fixes=["only use plain values and pure functions in promises"])
        elif isinstance(node, ListLit):
            for it in node.items:
                walk_pure(it, fn, where)
        elif isinstance(node, MapLit):
            for k, v in node.entries:
                walk_pure(k, fn, where)
                walk_pure(v, fn, where)
        elif isinstance(node, FieldGet):
            walk_pure(node.obj, fn, where)
        elif isinstance(node, RecordLit):
            for _, v in node.fields:
                walk_pure(v, fn, where)

    for fn in funcs:
        try:
            # a uses clause names effects, and only the seven exist. Until
            # 3.3 any identifier was accepted: `uses io, teleport`
            # compiled, reached velaris.audit/1's effects, and made its
            # safe_command a budget that does not parse (spec Q1). An
            # unknown name is now a compile error naming the seven.
            unknown = [e for e in sorted(fn.effects) if e not in ALL_EFFECTS]
            if unknown:
                raise VelarisError("E300",
                    f"function '{fn.name}' declares '{unknown[0]}', which "
                    f"is not an effect; the effects are "
                    f"{', '.join(ALL_EFFECTS)}", fn.line,
                    fixes=[f"remove '{unknown[0]}' from the uses clause",
                           f"or use one of: {', '.join(ALL_EFFECTS)}"])
            for stmt in fn.body:
                walk(stmt, fn)
            for expr, _ in fn.requires:
                walk_pure(expr, fn, "requires")
            for expr, _ in fn.ensures:
                walk_pure(expr, fn, "ensures")
        except VelarisError as e:
            errors.append(blame(fn, e))
