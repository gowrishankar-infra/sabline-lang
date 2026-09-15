"""The capability ratchet (velaris capabilities), and velaris review.
"""
import json
import os
import re
import sys

from .version import VERSION, _INSTALL_DIR
from .errors import VelarisError
from .nodes import (
    Assign,
    BinOp,
    Block,
    Call,
    Check,
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
    Num,
    RecordLit,
    Return,
    Str,
    TryExpr,
    Var,
    While,
)
from .tables import ALL_EFFECTS, BUILTINS, HAVE_Z3
from .loader import load_program
from .budget import BudgetError, _host_matches, _pct_encode, parse_host_port
from .effects import check_effects
from .checker import check_main, check_types
from .termination import (
    BAD,
    FLIP,
    _conjuncts,
    _names_bound_in,
    _steps_along_paths,
)
from .editor import inspect_source
from .library import _FFI_CALLS, _host_entry
from .findings import _SarifRun, print_sarif_summary
from typing import Any, cast

# ---------------------------------------------------------------------------
# 17. THE CAPABILITY RATCHET
#
#     A repository declares the capability surface it may have in
#     velaris.capabilities, and `velaris capabilities check` fails a
#     working tree that needs more. The comparison is always with that
#     file, never with the previous commit: capability is binary and
#     cumulative, so a surface assembled over forty small commits is
#     reported in full at every one of them - against what was declared -
#     rather than as forty small steps each measured from the last.
#     `velaris review --against REF` reports the delta from a git ref to
#     the working tree, for a pull request; it informs, the check gates.
#
#     What a program needs is read from its text: its functions' `uses`
#     clauses, the literal paths, hosts and modules its calls name, and a
#     bound on the fs and net operations one run can perform. The effect
#     and type checks run and the prover does not, so the answer is the
#     same with and without z3. velaris-spec SPEC.md section 9 states
#     every rule used here.
# ---------------------------------------------------------------------------


CAPABILITIES_SCHEMA = "velaris.capabilities/1"
CAPABILITIES_FILE = "velaris.capabilities"
CAPABILITIES_CHECK_SCHEMA = "velaris.capabilities-check/1"
REVIEW_SCHEMA = "velaris.review/1"
COUNTED_EFFECTS = ("fs", "net")
_OPERATIONS = (("fs", ("read_file", "read_file_secret", "write_file",
                       "file_exists")),
               ("net", ("fetch", "post", "fetch_status", "request")))
_BOUND_LIMIT = 2 ** 53          # a bound past this is recorded as none
_PLAIN_EFFECTS = ("io", "env", "clock", "rand", "declassify")


# ---- grants as a baseline writes them (velaris-spec 9.2, 9.4) --------------

def _grant_parts(g: str) -> tuple[Any, ...]:
    """A baseline grant as a tuple - ("io",), ("ffi", module or None),
    ("fs", direction or None, path or None), ("net", host or None, port
    or None) - or ValueError when it is not one a baseline may hold: no
    count, one module per ffi: grant, no `,` or `@` in a path, hosts
    written as the budget grammar writes them."""
    if not isinstance(g, str) or not g or g != g.strip():
        raise ValueError(f"{g!r} is not a grant")
    if "@" in g:
        raise ValueError(f"'{g}': a baseline grant takes no count; counts "
                         f"go in 'counts'")
    if g in _PLAIN_EFFECTS:
        return (g,)
    if g == "ffi":
        return ("ffi", None)
    if g.startswith("ffi:"):
        m = g[4:]
        if not m or any(ch in m for ch in ",:.") or any(
                ch.isspace() for ch in m):
            raise ValueError(f"'{g}': ffi: names one top-level module")
        return ("ffi", m)
    if g == "fs":
        return ("fs", None, None)
    if g in ("fs:read", "fs:write"):
        return ("fs", g[3:], None)
    if g.startswith("fs:read:") or g.startswith("fs:write:"):
        d, _, p = g[3:].partition(":")
        if not p or "," in p:
            raise ValueError(f"'{g}': a path after fs:{d}: is not empty and "
                             f"holds no ','")
        return ("fs", d, p)
    if g == "net":
        return ("net", None, None)
    if g.startswith("net:"):
        text = g[4:]
        if "," in text:
            raise ValueError(f"'{g}': a host holds no ','")
        try:
            host, port = parse_host_port(text)
        except BudgetError as e:
            raise ValueError(f"'{g}': {e}")
        if host.startswith("*."):
            tail = host[2:]
            if not tail or "*" in tail or "." not in tail or all(
                    lbl.isdigit() for lbl in tail.split(".")):
                raise ValueError(f"'{g}': a wildcard is '*.' and at least "
                                 f"two labels, not over an IP literal")
        elif "*" in host:
            raise ValueError(f"'{g}': only a leading '*.' is a wildcard")
        if any(ch.isspace() for ch in host):
            raise ValueError(f"'{g}': a host holds no space")
        return ("net", _pct_encode(host) if ":" not in host else host, port)
    raise ValueError(f"'{g}' is not a grant; the effects are "
                     f"{', '.join(ALL_EFFECTS)}")


def _norm_path(p: str) -> str:
    """velaris-spec 9.4's N: `/` runs made one, `.` components removed,
    `..` removed with the component before it (never past a leading `/`),
    a trailing `/` removed, nothing made `.`. Text only: nothing is
    resolved against a file system, and `\\` is not a separator."""
    rooted = p.startswith("/")
    out: list[Any] = []
    for part in p.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if out and out[-1] != "..":
                out.pop()
                continue
            if rooted and not out:
                continue
        out.append(part)
    text = "/".join(out)
    return "/" + text if rooted else (text or ".")


def _path_covers(q: str, p: str) -> bool:
    """Does a grant for path q cover path p (velaris-spec 9.4)? A path
    holding a `\\` is compared whole: on Windows `data/..\\..\\x` leaves
    `data`, and text that cannot be read the same way everywhere is
    covered only by the same text."""
    nq, np_ = _norm_path(q), _norm_path(p)
    if nq == np_:
        return True
    if "\\" in nq or "\\" in np_:
        return False
    if nq == ".":
        return not (np_.startswith("/") or np_ == ".."
                    or np_.startswith("../"))
    if nq == "/":
        return np_.startswith("/")
    return np_.startswith(nq + "/")


def _covers(b: tuple[Any, ...], c: tuple[Any, ...]) -> bool:
    """Does grant b cover grant c (both _grant_parts)? velaris-spec 9.4:
    the budget's covering rule of 5.5, grant by grant, with paths compared
    as text."""
    if b[0] != c[0]:
        return False
    if b[0] in _PLAIN_EFFECTS:
        return True
    if b[0] == "ffi":
        return b[1] is None or b[1] == c[1]
    if b[1] is None:                       # plain fs or net: everything
        return True
    if c[1] is None:                       # c is plain, b is scoped
        return False
    if b[0] == "fs":
        if b[1] != c[1]:
            return False
        if b[2] is None:
            return True
        return c[2] is not None and _path_covers(b[2], c[2])
    # net: a grant with a port does not cover one without
    (host, port), (want, want_port) = (b[1], b[2]), (c[1], c[2])
    if port is not None and port != want_port:
        return False
    if host.startswith("*.") and want.startswith("*."):
        return cast(bool, host == want)
    if want.startswith("*."):
        return False
    return _host_matches(host, want)


def _covered(g: str, grants: Any) -> bool:
    """Is grant g covered by any of grants (texts)?"""
    want = _grant_parts(g)
    return any(_covers(_grant_parts(h), want) for h in grants)


def _reduce_grants(grants: Any) -> list[Any]:
    """Sorted, without repeats, and without a grant another one covers
    (velaris-spec 9.2 rule 5). Of two grants that cover each other - two
    spellings of one path - the first in code-point order is kept."""
    uniq = sorted(set(grants))
    parts = {g: _grant_parts(g) for g in uniq}
    keep = []
    for g in uniq:
        if not any(h != g and _covers(parts[h], parts[g])
                   and (not _covers(parts[g], parts[h]) or h < g)
                   for h in uniq):
            keep.append(g)
    return keep


def _effect_of(g: str) -> str:
    return g.split(":", 1)[0]


# ---- what a program needs, from its text (velaris-spec 9.3) ----------------

def _call_sites(funcs: list[Any]) -> list[Any]:
    """(function, Call) for every call in every loaded function's body,
    in source order."""
    import dataclasses as _dc
    found = []

    def visit(node: Any, fn: Any) -> None:
        if isinstance(node, (list, tuple)):
            for x in node:
                visit(x, fn)
            return
        if not _dc.is_dataclass(node) or isinstance(node, Function):
            return
        if isinstance(node, Call):
            found.append((fn, node))
        for fld in _dc.fields(node):
            visit(getattr(node, fld.name), fn)

    for fn in funcs:
        visit(fn.body, fn)
    return found


def _site(fn: Any, call: Any, literal: Any = None) -> dict[str, Any]:
    return {"file": fn.src_file, "line": call.line, "function": fn.name,
            "call": call.name, "literal": literal}


def _text_value(e: Any, consts: dict[Any, Any]) -> Any:
    """The text an expression always is - a text literal, a variable in
    `consts`, or `+` of two such - or None."""
    if isinstance(e, Str):
        return e.value
    if isinstance(e, Var):
        return consts.get(e.name)
    if isinstance(e, BinOp) and e.op == "+":
        a, b = _text_value(e.left, consts), _text_value(e.right, consts)
        return a + b if a is not None and b is not None else None
    return None


def _text_constants(fn: Any) -> dict[Any, Any]:
    """{name: text} for the variables of fn that are bound exactly once,
    by a `let` whose value is text the program fixes (_text_value), and
    never assigned, bound by a check, or a parameter - so that moving a
    literal path, URL or module name into a variable does not read as a
    value built while running (velaris-spec 9.3)."""
    import dataclasses as _dc
    lets: dict[Any, Any] = {}
    order: list[Any] = []
    other: set[Any] = {n for n, _ in fn.params}

    def walk(node: Any) -> None:
        if isinstance(node, (list, tuple)):
            for x in node:
                walk(x)
            return
        if not _dc.is_dataclass(node) or isinstance(node, Function):
            return
        if isinstance(node, Let):
            lets[node.name] = lets.get(node.name, 0) + 1
            order.append(node)
        elif isinstance(node, Assign):
            other.add(node.name)
        elif isinstance(node, Check):
            other.update(n for n in (node.ok_name, node.fail_name) if n)
        for fld in _dc.fields(node):
            walk(getattr(node, fld.name))

    walk(fn.body)
    consts: dict[Any, Any] = {}
    for node in order:
        if lets[node.name] == 1 and node.name not in other:
            v = _text_value(node.value, consts)
            if v is not None:
                consts[node.name] = v
    return consts


def _literals_named(funcs: list[Any]) -> dict[Any, Any]:
    """What the calls of every loaded function name: fixed paths by
    direction, hosts, modules - each with the call sites that name it -
    and the sites that name one with a value built while running. Fixed
    means a text literal, or a variable bound once to one
    (_text_constants)."""
    lits: dict[Any, Any] = {"read": {}, "write": {}, "read_any": [], "write_any": [],
                  "hosts": {}, "net_any": [], "modules": {}, "ffi_any": []}
    fs_kind = {"read_file": "read", "read_file_secret": "read",
               "file_exists": "read",
               "write_file": "write"}
    url_at = {"fetch": 0, "post": 0, "fetch_status": 0, "request": 1}
    consts_of: dict[Any, Any] = {}
    for fn, call in _call_sites(funcs):
        if fn.name not in consts_of:
            consts_of[fn.name] = _text_constants(fn)
        consts = consts_of[fn.name]
        kind = fs_kind.get(call.name)
        if kind and call.args:
            value = _text_value(call.args[0], consts)
            if value is not None:
                lits[kind].setdefault(value, []).append(
                    _site(fn, call, value))
            else:
                lits[kind + "_any"].append(_site(fn, call))
        at = url_at.get(call.name)
        if at is not None and len(call.args) > at:
            value = _text_value(call.args[at], consts)
            entry = _host_entry(value) if value is not None else None
            if entry:
                lits["hosts"].setdefault(entry, []).append(
                    _site(fn, call, value))
            else:
                lits["net_any"].append(_site(fn, call, value))
        if call.name in _FFI_CALLS and call.args:
            value = _text_value(call.args[0], consts)
            if value is not None:
                lits["modules"].setdefault(value.split(".")[0], []) \
                    .append(_site(fn, call, value))
            else:
                lits["ffi_any"].append(_site(fn, call))
    return lits


def _effect_sites(effect: str, funcs: list[Any], own: list[Any]) -> list[Any]:
    """Where a program comes to need an effect: the calls to a builtin
    that performs it, or - when nothing calls one - the functions of the
    file that declare it without using it."""
    sites = [_site(fn, call) for fn, call in _call_sites(funcs)
             if effect in BUILTINS.get(call.name, {}).get("effects", ())]
    if sites:
        return sites
    return [{"file": f.src_file, "line": f.line, "function": f.name,
             "call": None, "literal": None}
            for f in own if effect in f.effects]


def _needs(effects: Any, lits: dict[Any, Any], funcs: list[Any], own: list[Any]) -> dict[Any, Any]:
    """{grant: [sites]} - the grants velaris-spec 9.3 derives for a
    program, before reduction, each with the call sites that need it. A
    path, host or module the grammar cannot hold as text, or one built
    while running, makes the grant unscoped: wider, so a scoped baseline
    does not cover it and someone has to look."""
    out: dict[Any, Any] = {}
    for e in sorted(effects):
        if e in _PLAIN_EFFECTS:
            out[e] = _effect_sites(e, funcs, own)
        elif e == "ffi":
            mods = lits["modules"]
            if lits["ffi_any"] or not mods or any(
                    not m or any(ch in m for ch in ",@:") or m != m.strip()
                    or any(ch.isspace() for ch in m) for m in mods):
                out["ffi"] = lits["ffi_any"] + [
                    s for ss in mods.values() for s in ss] or \
                    _effect_sites("ffi", funcs, own)
            else:
                for m, sites in mods.items():
                    out[f"ffi:{m}"] = sites
        elif e == "fs":
            made = False
            for d in ("read", "write"):
                paths = lits[d]
                awkward = [p for p in paths
                           if not p or p != p.strip() or "," in p or "@" in p
                           or any(ch in p for ch in "\r\n\t")]
                if lits[d + "_any"] or awkward:
                    out[f"fs:{d}"] = lits[d + "_any"] + [
                        s for p in paths for s in paths[p]]
                    made = True
                elif paths:
                    for p, sites in paths.items():
                        out[f"fs:{d}:{p}"] = sites
                    made = True
            if not made:
                out["fs"] = _effect_sites("fs", funcs, own)
        elif e == "net":
            hosts = lits["hosts"]
            if lits["net_any"] or not hosts or any(
                    "*" in h or "/" in h or (not h.startswith("[")
                                             and h.count(":") > 1)
                    for h in hosts):
                out["net"] = lits["net_any"] + [
                    s for h in hosts for s in hosts[h]] or \
                    _effect_sites("net", funcs, own)
            else:
                for h, sites in hosts.items():
                    out[f"net:{h}"] = sites
    # a grant the baseline grammar cannot hold falls back to its effect
    safe: dict[Any, Any] = {}
    for g, sites in out.items():
        try:
            _grant_parts(g)
        except ValueError:
            g = _effect_of(g)
        safe.setdefault(g, []).extend(sites)
    return safe


# ---- how many fs and net operations one run can perform ---------------------

def _const_int(e: Any, known: dict[Any, Any]) -> Any:
    """The whole number an expression always is, from literals and the
    variables `known` holds, or None. `known` maps a variable to a whole
    number, or to ("items", n) for a list literal of n items, whose
    `length` is then known."""
    if isinstance(e, Num) and isinstance(e.value, int) \
            and not isinstance(e.value, bool):
        return e.value
    if isinstance(e, Neg):
        v = _const_int(e.value, known)
        return None if v is None else -v
    if isinstance(e, Var):
        v = known.get(e.name)
        return v if isinstance(v, int) else None
    if isinstance(e, BinOp) and e.op in ("+", "-", "*"):
        a, b = _const_int(e.left, known), _const_int(e.right, known)
        if a is None or b is None:
            return None
        return a + b if e.op == "+" else a - b if e.op == "-" else a * b
    if isinstance(e, Call) and e.name == "length" and len(e.args) == 1:
        arg = e.args[0]
        if isinstance(arg, ListLit):
            return len(arg.items)
        if isinstance(arg, Var) and isinstance(known.get(arg.name), tuple):
            return known[arg.name][1]
    return None


def _turns(loop: While, known: dict[Any, Any]) -> Any:
    """The most times a loop's body can run, or math.inf. A bound exists
    for the one shape the termination rule shows to end (SPEC.md 9.5) -
    a counter moving one step toward its limit on every path - when the
    counter's value on entry and the limit are whole numbers the text
    fixes, the limit read only from variables the body leaves alone.
    Each qualifying conjunct of the condition bounds the loop on its
    own, so the smallest bound is taken."""
    import math
    best = math.inf
    bound = _names_bound_in(loop.body)
    # the limit is read only from literals and from variables the body
    # leaves alone, so a value found for it holds on every turn
    unchanged = {k: v for k, v in known.items() if k not in bound}
    for c in _conjuncts(loop.cond):
        if not isinstance(c, BinOp) or c.op not in FLIP:
            continue
        for side, other, op in ((c.left, c.right, c.op),
                                (c.right, c.left, FLIP[c.op])):
            if not isinstance(side, Var) or side.name not in bound:
                continue
            steps = _steps_along_paths(loop.body, side.name, op)
            if steps is BAD or (steps and steps != {1}):
                continue
            if not steps:                  # every path leaves the loop
                best = min(best, 1)
                continue
            start = known.get(side.name)
            limit = _const_int(other, unchanged)
            if not isinstance(start, int) or limit is None:
                continue
            n = {"<": limit - start, "<=": limit - start + 1,
                 ">": start - limit, ">=": start - limit + 1}[op]
            best = min(best, max(0, n))
    return best


def _operation_bounds(funcs: list[Any]) -> tuple[Any, ...]:
    """({function: {"fs": n, "net": n}}, {function: {effect: why}}): for
    every loaded function, the most fs and net operations one call to it
    can perform - math.inf when the text sets no bound - and for an
    unbounded one, the first reason. Sums along a path, the larger of two
    branches, a loop's body times its turns (_turns), a callee's bound
    at every call, and no bound through recursion. An operation is a
    call to one of the builtins the runtime counts (_OPERATIONS); a
    function value is pure (SPEC.md 7) and performs none."""
    import math
    INF = math.inf
    table = {f.name: f for f in funcs}
    memo: dict[Any, Any] = {}
    why: dict[Any, Any] = {}
    biggest: dict[Any, Any] = {}           # function -> effect -> (amount, sentence)
    active: list[Any] = []

    def zero() -> dict[str, Any]:
        return {"fs": 0, "net": 0}

    def credit(fn: Any, got: Any, sentence: Any) -> None:
        for k, v in got.items():
            if 0 < v < INF and v > biggest.get(fn.name, {}).get(
                    k, (0, ""))[0]:
                biggest.setdefault(fn.name, {})[k] = (v, sentence)

    def add(a: Any, b: Any) -> dict[Any, Any]:
        return {k: a[k] + b[k] for k in a}

    def most(a: Any, b: Any) -> dict[Any, Any]:
        return {k: max(a[k], b[k]) for k in a}

    def times(a: Any, n: Any) -> dict[Any, Any]:
        return {k: (0 if a[k] == 0 else a[k] * n) for k in a}

    def blame(fn: Any, got: Any, reason: Any) -> None:
        for k, v in got.items():
            if v == INF:
                why.setdefault(fn.name, {}).setdefault(k, reason)

    def of(name: Any, caller: Any) -> Any:
        if name in memo:
            return memo[name]
        f = table[name]
        if name in active:                 # recursion: as many as it
            got = {k: (INF if k in f.effects else 0)   # may declare
                   for k in COUNTED_EFFECTS}
            blame(caller, got, f"'{name}' can call itself again, through "
                               f"'{caller.name}'")
            return got
        active.append(name)
        try:
            got = block(f.body, {}, f)
        finally:
            active.pop()
        memo[name] = got
        return got

    def ex(e: Any, known: Any, fn: Any) -> Any:
        if isinstance(e, Call):
            got = zero()
            for a in e.args:
                got = add(got, ex(a, known, fn))
            for effect, names in _OPERATIONS:
                if e.name in names:
                    got[effect] += 1
            if e.name in table:
                sub = of(e.name, fn)
                if INF in sub.values():
                    blame(fn, sub, f"it calls '{e.name}', which has no "
                                   f"bound: "
                                   + "; ".join(sorted(set(
                                       why.get(e.name, {}).values()))
                                       or ["recursion"]))
                for k, v in sub.items():
                    inner = biggest.get(e.name, {}).get(k)
                    credit(fn, {k: v}, f"it calls '{e.name}'"
                           + (f", where {inner[1]}" if inner else ""))
                got = add(got, sub)
            return got
        if isinstance(e, TryExpr):
            return ex(e.value, known, fn)
        if isinstance(e, BinOp):
            return add(ex(e.left, known, fn), ex(e.right, known, fn))
        if isinstance(e, (Not, Neg)):
            return ex(e.value, known, fn)
        if isinstance(e, FieldGet):
            return ex(e.obj, known, fn)
        if isinstance(e, ListLit):
            got = zero()
            for x in e.items:
                got = add(got, ex(x, known, fn))
            return got
        if isinstance(e, MapLit):
            got = zero()
            for k, v in e.entries:
                got = add(got, add(ex(k, known, fn), ex(v, known, fn)))
            return got
        if isinstance(e, RecordLit):
            got = zero()
            for _name, v in e.fields:
                got = add(got, ex(v, known, fn))
            return got
        return zero()

    def forget(known: Any, names: Any) -> None:
        for n in names:
            known.pop(n, None)

    def st(s: Any, known: Any, fn: Any) -> Any:
        if isinstance(s, (Let, Assign)):
            got = ex(s.value, known, fn)
            v = _const_int(s.value, known)
            if isinstance(s.value, ListLit):
                v = ("items", len(s.value.items))
            if v is None:
                known.pop(s.name, None)
            else:
                known[s.name] = v
            return got
        if isinstance(s, (Return, FailStmt)):
            return zero() if s.value is None else ex(s.value, known, fn)
        if isinstance(s, ExprStmt):
            return ex(s.expr, known, fn)
        if isinstance(s, If):
            got = ex(s.cond, known, fn)
            both = most(block(s.then, known, fn), block(s.other, known, fn))
            forget(known, _names_bound_in(s.then) | _names_bound_in(s.other))
            return add(got, both)
        if isinstance(s, Check):
            got = ex(s.subject, known, fn)
            inner = {k: v for k, v in known.items()
                     if k not in (s.ok_name, s.fail_name)}
            both = most(block(s.ok_body, inner, fn),
                        block(s.fail_body, inner, fn))
            forget(known, _names_bound_in([s]))
            return add(got, both)
        if isinstance(s, While):
            n = _turns(s, known)
            changed = _names_bound_in(s.body)
            inner = {k: v for k, v in known.items() if k not in changed}
            cond, body = ex(s.cond, inner, fn), block(s.body, inner, fn)
            forget(known, changed)
            got = add(times(cond, n + 1), times(body, n))
            where = f"line {s.line} of {os.path.basename(fn.src_file or '?')}"
            if n == INF:
                blame(fn, got, f"the loop at {where} has no fixed number "
                               f"of turns")
            else:
                credit(fn, got, f"the loop at {where} turns at most {n} "
                                f"time(s)")
            return got
        if isinstance(s, Block):
            got = zero()
            for x in s.stmts:
                got = add(got, st(x, known, fn))
            return got
        return zero()

    def block(stmts: Any, known: Any, fn: Any) -> Any:
        known = dict(known)
        got = zero()
        for s in stmts:
            got = add(got, st(s, known, fn))
        return got

    for f in funcs:
        of(f.name, f)
    for name, per in biggest.items():       # where a finite bound comes
        for k, (_amount, sentence) in per.items():   # from, when no
            why.setdefault(name, {}).setdefault(k, sentence)   # infinite
    return memo, why                                          # one does


def _as_count(n: Any) -> int | None:
    """A bound as a baseline writes it: a whole number, or None for no
    bound (and for one too large to be useful)."""
    import math
    if n == math.inf or n > _BOUND_LIMIT:
        return None
    return int(n)


def _count_exceeds(now: Any, allowed: Any) -> bool:
    """Is `now` more operations than `allowed`? None is no bound."""
    if allowed is None:
        return False
    return now is None or now > allowed


# ---- one program, and a tree of them ----------------------------------------

def _program_capabilities(path: str, rel: str) -> dict[Any, Any]:
    """What one .vel file needs (velaris-spec 9.3): its grants, reduced;
    how many fs and net operations one call to any of its functions can
    perform; and each of its functions' declared effects. Keys beginning
    with '_' are for reporting and are not written to a baseline. A file
    that does not parse, load, or pass the effect and type checks cannot
    run, and is marked compiles: False with its problems."""
    out: dict[Any, Any] = {"file": rel, "compiles": False, "problems": [],
                 "grants": [], "counts": {}, "functions": {}}
    errors: list[Any] = []
    try:
        funcs, records = load_program(path)
        check_main(funcs, errors, running=False)
        check_effects(funcs, errors)
        if not errors:
            check_types(funcs, records, errors)
    except VelarisError as e:
        errors.append(e)
    except Exception as e:                  # a checker that crashed still
        errors.append(VelarisError(         # means: cannot be compared
            "E000", f"{type(e).__name__}: {e}", 0))
    if errors:
        out["problems"] = [{"code": e.code, "line": e.line,
                            "message": e.message} for e in errors[:5]]
        return out
    here = os.path.abspath(path)
    own = [f for f in funcs if not f.name.startswith("fn#")
           and os.path.abspath(f.src_file or path) == here]
    # running this file runs `main`, wherever it is defined: a file that
    # imports its main from outside the checked tree still needs what
    # that main does
    runs = own + [f for f in funcs if f.name == "main" and f not in own]
    effects = sorted({e for f in runs for e in f.effects})
    lits = _literals_named(funcs)
    needs = _needs(effects, lits, funcs, runs)
    grants = _reduce_grants(needs)
    origins: dict[str, list[Any]] = {g: [] for g in grants}
    for g, sites in needs.items():       # a grant reduced away is needed
        into = g if g in origins else next(   # through the one covering it
            h for h in grants if _covers(_grant_parts(h), _grant_parts(g)))
        origins[into].extend(sites)
    bounds, why = _operation_bounds(funcs)
    counts = {}
    for eff in COUNTED_EFFECTS:
        if eff in effects:
            counts[eff] = _as_count(max([bounds[f.name][eff] for f in runs]
                                      or [0]))
    out.update(compiles=True, grants=grants, counts=counts,
               functions={f.name: sorted(f.effects) for f in own},
               _funcs=funcs, _own=runs, _origins=origins, _lits=lits,
               _bounds=bounds, _why=why, _path=path)
    return out


def _capability_files(root: str, use_git: bool = True) -> list[Any]:
    """Every .vel file under root, as sorted '/'-separated paths relative
    to it - leaving out .git, and files git ignores when root is in a git
    work tree (they are not part of the repository)."""
    import subprocess
    found = []
    for dp, dirs, files in os.walk(root):
        # every directory but git's own: a program committed under
        # .github or .ci is part of the repository like any other
        dirs[:] = sorted(d for d in dirs if d != ".git")
        for f in files:
            if f.endswith(".vel"):
                found.append(os.path.relpath(os.path.join(dp, f), root)
                             .replace(os.sep, "/"))
    found.sort()
    if not found or not use_git:
        return found
    try:
        done = subprocess.run(
            ["git", "-C", root, "check-ignore", "--stdin", "-z"],
            input="\0".join(found).encode("utf-8"), capture_output=True,
            timeout=120)
    except (OSError, subprocess.SubprocessError):
        return found                        # no git: nothing is ignored
    if done.returncode not in (0, 1):
        return found                        # not a work tree
    ignored = {p for p in done.stdout.decode("utf-8", "replace").split("\0")
               if p}
    return [f for f in found if f not in ignored]


def capability_scan(root: str = ".", use_git: bool = True) -> dict[str, Any]:
    """The capability surface of every .vel file under root: {"root",
    "programs": {file: _program_capabilities}, "surface": {"grants",
    "counts"}}. The surface is the union of the grants of the files that
    compile, reduced, and for fs and net the largest count any of them
    has (None - no bound - beats every number)."""
    programs = {rel: _program_capabilities(os.path.join(root, rel), rel)
                for rel in _capability_files(root, use_git)}
    live = [p for p in programs.values() if p["compiles"]]
    grants = _reduce_grants(g for p in live for g in p["grants"])
    counts = {}
    for e in COUNTED_EFFECTS:
        have = [p["counts"][e] for p in live if e in p["counts"]]
        if have:
            counts[e] = None if None in have else max(have)
    return {"root": root, "programs": programs,
            "surface": {"grants": grants, "counts": counts}}


def capabilities_document(scan: dict[Any, Any], date: str | None = None) -> dict[str, Any]:
    """The velaris.capabilities/1 document for a scan: the Velaris that
    wrote it, the date, the surface, and each program's grants, counts
    and functions' effects - or compiles: false."""
    import datetime
    if date is None:
        date = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    programs = []
    for rel in sorted(scan["programs"]):
        p = scan["programs"][rel]
        if not p["compiles"]:
            programs.append({"file": rel, "compiles": False})
            continue
        programs.append({"file": rel, "grants": p["grants"],
                         "counts": p["counts"],
                         "functions": dict(sorted(p["functions"].items()))})
    return {"schema": CAPABILITIES_SCHEMA, "velaris_version": VERSION,
            "date": date, "surface": scan["surface"], "programs": programs}


def capabilities_text(doc: dict[Any, Any]) -> str:
    """A baseline as text: JSON, one grant per line and one function per
    line, so that accepting a widening is a one-line change in review."""
    dump = json.dumps

    def counts(c: Any) -> str:
        return "{" + ", ".join(f"{dump(k)}: {dump(v)}"
                               for k, v in sorted(c.items())) + "}"

    def grant_list(gs: Any, pad: Any) -> str:
        if not gs:
            return "[]"
        inner = ",\n".join(f"{pad}  {dump(g)}" for g in gs)
        return "[\n" + inner + f"\n{pad}]"

    lines = ["{",
             f'  "schema": {dump(doc["schema"])},',
             f'  "velaris_version": {dump(doc["velaris_version"])},',
             f'  "date": {dump(doc["date"])},',
             '  "surface": {',
             f'    "grants": {grant_list(doc["surface"]["grants"], "    ")},',
             f'    "counts": {counts(doc["surface"]["counts"])}',
             "  },"]
    entries = []
    for p in doc["programs"]:
        if p.get("compiles") is False:
            entries.append(f'    {{"file": {dump(p["file"])}, '
                           f'"compiles": false}}')
            continue
        fns = ",\n".join(f"        {dump(n)}: {dump(e)}"
                         for n, e in p["functions"].items())
        entries.append(
            "    {\n"
            f'      "file": {dump(p["file"])},\n'
            f'      "grants": {grant_list(p["grants"], "      ")},\n'
            f'      "counts": {counts(p["counts"])},\n'
            '      "functions": ' + ("{}" if not fns else
                                     "{\n" + fns + "\n      }") + "\n"
            "    }")
    lines.append('  "programs": [' + ("" if not entries else "\n"
                                      + ",\n".join(entries) + "\n  ") + "]")
    lines.append("}")
    return "\n".join(lines) + "\n"


def read_capabilities(path: str) -> dict[Any, Any]:
    """A velaris.capabilities/1 document, checked; ValueError naming the
    first thing wrong with it. velaris.capabilities/0, the spec's
    provisional form, was never written by Velaris and is refused."""
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except OSError as e:
        raise ValueError(f"cannot read {path}: {e.strerror or e}")
    except ValueError as e:
        raise ValueError(f"{path} is not JSON: {e}")
    if not isinstance(doc, dict):
        raise ValueError(f"{path} is not a {CAPABILITIES_SCHEMA} document")
    if doc.get("schema") == "velaris.capabilities/0":
        raise ValueError(f"{path} is velaris.capabilities/0, the "
                         f"provisional form velaris-spec 0.2 described and "
                         f"no Velaris wrote; write a {CAPABILITIES_SCHEMA} "
                         f"one with: velaris capabilities init --force")
    if doc.get("schema") != CAPABILITIES_SCHEMA:
        raise ValueError(f"{path} is not a {CAPABILITIES_SCHEMA} document "
                         f"(its schema is {doc.get('schema')!r})")

    def check_grants(gs: Any, where: Any) -> None:
        if not isinstance(gs, list):
            raise ValueError(f"{where}: grants is a list")
        for g in gs:
            try:
                _grant_parts(g)
            except ValueError as e:
                raise ValueError(f"{where}: {e}")

    def check_counts(c: Any, where: Any) -> None:
        if not isinstance(c, dict):
            raise ValueError(f"{where}: counts is an object")
        for k, v in c.items():
            if k not in COUNTED_EFFECTS or not (
                    v is None or (isinstance(v, int)
                                  and not isinstance(v, bool) and v >= 0)):
                raise ValueError(f"{where}: counts holds fs and net only, "
                                 f"each a whole number or null")

    surface = doc.get("surface")
    if not isinstance(surface, dict):
        raise ValueError(f"{path}: no surface")
    check_grants(surface.get("grants"), "surface")
    check_counts(surface.get("counts", {}), "surface")
    programs = doc.get("programs")
    if not isinstance(programs, list):
        raise ValueError(f"{path}: programs is a list")
    seen = set()
    for p in programs:
        f = p.get("file") if isinstance(p, dict) else None
        if not isinstance(f, str) or not f or f.startswith("/") \
                or "\\" in f or any(part in ("", ".", "..")
                                    for part in f.split("/")):
            raise ValueError(f"{path}: a program's file is a '/'-separated "
                             f"path under the baseline's directory")
        if f in seen:
            raise ValueError(f"{path}: {f} is listed twice")
        seen.add(f)
        if p.get("compiles") is False:
            continue
        check_grants(p.get("grants"), f)
        check_counts(p.get("counts", {}), f)
        fns = p.get("functions", {})
        if not isinstance(fns, dict) or not all(
                isinstance(v, list) and all(e in ALL_EFFECTS for e in v)
                for v in fns.values()):
            raise ValueError(f"{f}: functions maps each name to its "
                             f"effects")
    return doc


# ---- the ratchet: the tree against the baseline (velaris-spec 9.5) ----------

def _version_tuple(v: Any) -> tuple[Any, ...]:
    return tuple(int(x) if x.isdigit() else 0
                 for x in re.split(r"[.+-]", str(v))[:3])


def _chain(table: dict[Any, Any], starts: list[Any], goal: str) -> list[Any]:
    """The shortest chain of calls from one of `starts` to `goal`, as
    function names, or []."""
    from collections import deque
    callees: dict[Any, Any] = {}

    def of(name: Any) -> Any:
        if name not in callees:
            fn = table.get(name)
            callees[name] = [] if fn is None else sorted(
                {c.name for _, c in _call_sites([fn]) if c.name in table})
        return callees[name]

    for start in starts:
        seen, todo = {start: None}, deque([start])
        while todo:
            at = todo.popleft()
            if at == goal:
                path = []
                while at is not None:
                    path.append(at)
                    at = seen[at]
                return path[::-1]
            for nxt in of(at):
                if nxt not in seen:
                    seen[nxt] = at
                    todo.append(nxt)
    return []


def _shown_path(file: str, root: str) -> str:
    """A file as a report shows it: relative to the checked root when it
    is under it, else from the standard library, else as it is."""
    full = os.path.abspath(file)
    try:
        rel = os.path.relpath(full, os.path.abspath(root))
    except ValueError:
        rel = None
    if rel is not None and not rel.startswith(".."):
        return rel.replace(os.sep, "/")
    std = os.path.join(_INSTALL_DIR, "stdlib")
    if full.startswith(std + os.sep):
        return "<stdlib>/" + os.path.relpath(full, std).replace(os.sep, "/")
    return full.replace(os.sep, "/")


def _because(fn: Any, effect: str, table: dict[Any, Any]) -> list[Any]:
    """Why a function needs an effect: the builtins it calls that perform
    it, and the functions it calls that declare it."""
    said = []
    for _, call in _call_sites([fn]):
        if effect in BUILTINS.get(call.name, {}).get("effects", ()):
            said.append(f"calls {call.name} at line {call.line}")
        elif call.name in table and effect in table[call.name].effects:
            said.append(f"calls {call.name} at line {call.line}, which "
                        f"declares {effect}")
    return sorted(set(said), key=said.index) or [
        f"declares {effect} in its uses clause"]


def capabilities_compare(baseline: dict[Any, Any], scan: dict[Any, Any],
                         baseline_file: str = CAPABILITIES_FILE) -> dict[str, Any]:
    """The ratchet (velaris-spec 9.5): the tree in `scan` against the
    declared surface in `baseline` - never against a previous commit.

    Three rules, and a change widens the surface when any of them fails:
      S  every grant a program under the root needs is covered by the
         baseline's surface, and no program performs more fs or net
         operations in a run than the surface's count;
      P  a program the baseline records needs nothing its own entry does
         not give, and no more operations than its entry's count;
      F  a function the baseline records declares no effect it did not
         declare there.
    A program or function the baseline does not record is held to S
    alone: a new program that stays inside the surface the repository
    already declared does not widen it. Narrowing is never a failure;
    it is reported so the baseline can be tightened."""
    root = scan["root"]
    base_surface = baseline["surface"]["grants"]
    base_counts = baseline["surface"].get("counts", {})
    base_effects = {_effect_of(g) for g in base_surface}
    recorded = {p["file"]: p for p in baseline["programs"]
                if p.get("compiles") is not False}
    programs = scan["programs"]
    findings: list[Any] = []
    narrowed: list[Any] = []
    notes: list[Any] = []
    warnings: list[Any] = []

    written_by = baseline.get("velaris_version")
    if written_by != VERSION:
        older = _version_tuple(written_by) < _version_tuple(VERSION)
        warnings.append(
            f"{baseline_file} was written by Velaris {written_by}, "
            f"{'an older' if older else 'a different'} version than this "
            f"one ({VERSION}); the comparison uses this version's "
            f"derivation and standard library, so a difference between "
            f"the two can show up as a change. Read any finding with that "
            f"in mind, then record the surface again with: velaris "
            f"capabilities init --force")

    broken_as_recorded = {p["file"] for p in baseline["programs"]
                          if p.get("compiles") is False}
    for rel, p in sorted(programs.items()):
        if not p["compiles"] and rel not in broken_as_recorded:
            notes.append(f"{rel} does not compile, so it cannot run and "
                         f"adds nothing; it was not compared")
    for rel in sorted(set(recorded) - set(programs)):
        notes.append(f"{baseline_file} records {rel}, which is not there "
                     f"now; not a failure")

    # S and P, grant by grant
    by_grant: dict[Any, Any] = {}
    for rel, p in sorted(programs.items()):
        if not p["compiles"]:
            continue
        entry = recorded.get(rel)
        table = {f.name: f for f in p["_funcs"]}
        starts = ["main"] if "main" in table else sorted(p["functions"])
        for g in p["grants"]:
            out_surface = not _covered(g, base_surface)
            out_entry = entry is not None and not _covered(
                g, entry["grants"])
            if not (out_surface or out_entry):
                continue
            item = by_grant.setdefault(g, {
                "kind": "grant", "grant": g, "effect": _effect_of(g),
                "new_effect": _effect_of(g) not in base_effects,
                "outside_surface": False, "programs": []})
            item["outside_surface"] |= out_surface
            origins = [dict(s, file=_shown_path(s["file"], root))
                       for s in p["_origins"].get(g, [])]
            reach = []
            if origins and origins[0]["function"] not in starts:
                reach = _chain(table, starts, origins[0]["function"])
            item["programs"].append({
                "file": rel, "recorded": entry is not None,
                "outside_entry": out_entry, "origins": origins[:8],
                "reached_from": reach})
    for g, item in sorted(by_grant.items()):
        accept = []
        if item["outside_surface"]:
            accept.append(f'add "{g}" to surface.grants')
        for q in item["programs"]:
            if q["outside_entry"]:
                accept.append(f'add "{g}" to the grants of {q["file"]}')
        item["accept"] = accept
        item["rules"] = (["W1"] if item["outside_surface"] else []) + (
            ["W3"] if any(q["outside_entry"] for q in item["programs"])
            else [])
        findings.append(item)

    # S and P, counts
    for rel, p in sorted(programs.items()):
        if not p["compiles"]:
            continue
        entry = recorded.get(rel)
        entry_effects = {_effect_of(g) for g in entry["grants"]} \
            if entry else set()
        for e, now in sorted(p["counts"].items()):
            out_surface = e in base_effects and _count_exceeds(
                now, base_counts.get(e))
            out_entry = e in entry_effects and _count_exceeds(
                now, cast(dict[str, Any], entry).get("counts", {}).get(e))
            if not (out_surface or out_entry):
                continue
            own = p["_own"]
            worst = max(own, key=lambda f: (p["_bounds"][f.name][e],
                                            -f.line))
            reason = p["_why"].get(worst.name, {}).get(e)
            accept = []
            if out_surface:
                accept.append(f"set surface.counts.{e} to "
                              f"{json.dumps(now)}")
            if out_entry:
                accept.append(f"set counts.{e} of {rel} to "
                              f"{json.dumps(now)}")
            findings.append({
                "kind": "count", "effect": e, "file": rel, "current": now,
                "surface_allows": base_counts.get(e),
                "entry_allows": (entry or {}).get("counts", {}).get(e),
                "outside_surface": out_surface, "outside_entry": out_entry,
                "rules": (["W2"] if out_surface else [])
                + (["W4"] if out_entry else []),
                "function": worst.name, "line": worst.line,
                "why": reason, "accept": accept})

    # F, function by function
    for rel, entry in sorted(recorded.items()):
        p = programs.get(rel)
        if not p or not p["compiles"]:
            continue
        table = {f.name: f for f in p["_funcs"]}
        for name, had in sorted(entry.get("functions", {}).items()):
            now = p["functions"].get(name)
            if now is None:
                continue
            gained = sorted(set(now) - set(had))
            if not gained:
                continue
            fn = table[name]
            findings.append({
                "kind": "function", "file": rel, "function": name,
                "line": fn.line, "had": sorted(had), "now": now,
                "gained": gained, "rules": ["W5"],
                "because": [f"{e}: " + "; ".join(_because(fn, e, table))
                            for e in gained],
                "accept": [f"set functions.{name} of {rel} to "
                           f"{json.dumps(now)}"]})

    # what narrowed - never a failure
    needed = [g for p in programs.values() if p["compiles"]
              for g in p["grants"]]
    for b in base_surface:
        bp = _grant_parts(b)
        if not any(_covers(bp, _grant_parts(g)) for g in needed):
            narrowed.append(f'surface: "{b}" is no longer needed')
    now_counts = scan["surface"]["counts"]
    for e, allowed in sorted(base_counts.items()):
        if e in now_counts and allowed is None and now_counts[e] is not None:
            narrowed.append(f"surface: {e} now has a bound, "
                            f"{now_counts[e]}")
        elif e in now_counts and allowed is not None and \
                now_counts[e] is not None and now_counts[e] < allowed:
            narrowed.append(f"surface: {e} count {allowed} -> "
                            f"{now_counts[e]}")
    for rel, entry in sorted(recorded.items()):
        p = programs.get(rel)
        if not p or not p["compiles"]:
            continue
        for name, had in sorted(entry.get("functions", {}).items()):
            now = p["functions"].get(name)
            if now is not None and set(had) - set(now):
                narrowed.append(f"{rel}: {name} no longer declares "
                                f"{', '.join(sorted(set(had) - set(now)))}")

    live = sum(1 for p in programs.values() if p["compiles"])
    still_broken = sum(1 for rel, p in programs.items()
                       if not p["compiles"] and rel in broken_as_recorded)
    if still_broken:
        notes.append(f"{still_broken} file(s) do not compile, as "
                     f"{baseline_file} records")
    return {"schema": CAPABILITIES_CHECK_SCHEMA, "velaris_version": VERSION,
            "root": root,
            "baseline": {"file": baseline_file,
                         "velaris_version": written_by,
                         "date": baseline.get("date")},
            "widened": bool(findings), "findings": findings,
            "narrowed": narrowed, "notes": notes, "warnings": warnings,
            "programs": len(programs), "compared": live}


def _finding_lines(item: dict[Any, Any]) -> list[Any]:
    """A finding as the report prints it: what widened, where, and the
    edit to the baseline that would accept it."""
    out = []
    if item["kind"] == "grant":
        what = (f"a new effect, {item['effect']}" if item["new_effect"]
                else "not in the surface" if item["outside_surface"]
                else "inside the surface, not in a program's entry")
        out.append(f"WIDENED  {item['grant']} - {what}")
        for q in item["programs"]:
            where = ("its entry does not grant it" if q["outside_entry"]
                     else "not recorded in the baseline" if not q["recorded"]
                     else "its entry grants it")
            out.append(f"    needed by {q['file']} ({where})")
            for s in q["origins"][:4]:
                lit = f'("{s["literal"]}")' if s.get("literal") else ""
                call = f" calls {s['call']}{lit}" if s.get("call") \
                    else " declares it"
                out.append(f"      {s['file']}:{s['line']}  "
                           f"{s['function']}{call}")
            if q["reached_from"]:
                out.append(f"      reached from "
                           f"{' -> '.join(q['reached_from'])}")
    elif item["kind"] == "count":
        now = ("no bound" if item["current"] is None
               else f"at most {item['current']}")
        allows = item["surface_allows"] if item["outside_surface"] \
            else item["entry_allows"]
        out.append(f"WIDENED  {item['effect']} operations in "
                   f"{item['file']}: {now} in a run; the baseline allows "
                   f"{allows}")
        out.append(f"    {item['function']} (line {item['line']})"
                   + (f": {item['why']}" if item.get("why") else ""))
    else:
        out.append(f"WIDENED  {item['file']}: function {item['function']} "
                   f"gained {', '.join(item['gained'])} (it declared "
                   f"{', '.join(item['had']) or 'nothing'})")
        for b in item["because"]:
            effect, _, rest = b.partition(": ")
            out.append(f"    {effect}: {item['function']} {rest}")
    out.append("    if intended: " + "; ".join(item["accept"]))
    return out


def sarif_capabilities(result: dict[Any, Any]) -> dict[Any, Any]:
    """`velaris capabilities check --sarif`: each widening as an error at
    the line that introduced it - the call that names a new host, the
    function that gained an effect - each narrowing as a note, and the
    check's whole JSON result in the run's property bag."""
    run = _SarifRun("capabilities")
    root = result["root"]

    def at(file: Any) -> Any:
        return file if os.path.isabs(file) or file.startswith("<") \
            else os.path.join(root, file)

    for item in result["findings"]:
        if item["kind"] == "grant":
            for q in item["programs"]:
                s = (q["origins"] or [{"file": q["file"], "line": None}])[0]
                where, line, via = s["file"], s.get("line"), ""
                if where.startswith("<"):     # the standard library: the
                    via = f", through {where}:{line}"   # program is where
                    where, line = q["file"], None       # it is reached
                gap = ("not in the surface" if item["outside_surface"]
                       else "not in its entry")
                run.add("capability-widened",
                        f"{item['grant']} is needed by {q['file']}{via}, "
                        f"{gap} of {result['baseline']['file']}"
                        + (f" (a new effect, {item['effect']})"
                           if item["new_effect"] else ""),
                        at(where), line,
                        fixes=["if intended: " + "; ".join(item["accept"])])
        elif item["kind"] == "count":
            now = ("no bound" if item["current"] is None
                   else f"at most {item['current']}")
            run.add("capability-widened",
                    f"{item['file']} performs {now} {item['effect']} "
                    f"operations in a run, more than "
                    f"{result['baseline']['file']} allows"
                    + (f": {item['why']}" if item.get("why") else ""),
                    at(item["file"]), item["line"],
                    fixes=["if intended: " + "; ".join(item["accept"])])
        else:
            run.add("capability-effect-gained",
                    f"'{item['function']}' now declares "
                    f"{', '.join(item['gained'])}, which it did not in "
                    f"{result['baseline']['file']}: "
                    + "; ".join(item["because"]),
                    at(item["file"]), item["line"],
                    fixes=["if intended: " + "; ".join(item["accept"])])
    for text in result["narrowed"]:
        run.add("capability-narrowed", text,
                at(result["baseline"]["file"]), None)
    run.properties["capabilities"] = result
    return run.log()


def capabilities_main(argv: list[Any]) -> int:
    """velaris capabilities init [path] [--force]
    velaris capabilities check [path] [--json | --sarif]"""
    usage = ("usage: velaris capabilities init [path] [--force]\n"
             "       velaris capabilities check [path] [--json | --sarif]")
    if not argv or argv[0] not in ("init", "check"):
        print(usage, file=sys.stderr)
        return 2
    sub, rest = argv[0], argv[1:]
    allowed = {"init": {"--force"}, "check": {"--json", "--sarif"}}[sub]
    flags = {a for a in rest if a.startswith("-")}
    places = [a for a in rest if not a.startswith("-")]
    if flags - allowed or len(places) > 1 or flags >= {"--json", "--sarif"}:
        print(usage, file=sys.stderr)
        return 2
    root = places[0] if places else "."
    if not os.path.isdir(root):
        print(f"velaris capabilities: {root} is not a directory",
              file=sys.stderr)
        return 2
    target = os.path.join(root, CAPABILITIES_FILE)

    if sub == "init":
        if os.path.exists(target) and "--force" not in flags:
            print(f"{target} already exists, and it is the surface this "
                  f"repository declared: init does not replace it. To "
                  f"record the surface again, pass --force; the file's "
                  f"diff then shows what changed.", file=sys.stderr)
            return 1
        scan = capability_scan(root)
        doc = capabilities_document(scan)
        with open(target, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(capabilities_text(doc))
        broken = [p for p in doc["programs"] if p.get("compiles") is False]
        print(f"wrote {target}: {len(doc['programs'])} program(s), "
              f"Velaris {VERSION}, {doc['date']}")
        print(f"  surface: {', '.join(doc['surface']['grants']) or 'nothing'}")
        for e, n in sorted(doc["surface"]["counts"].items()):
            print(f"  {e} operations in a run: "
                  f"{'no bound' if n is None else f'at most {n}'}")
        if broken:
            print(f"  {len(broken)} file(s) do not compile; recorded as "
                  f"such, and not compared until they do")
        return 0

    if not os.path.exists(target):
        print(f"no {CAPABILITIES_FILE} in {root}: write one with velaris "
              f"capabilities init {root}", file=sys.stderr)
        return 2
    try:
        baseline = read_capabilities(target)
    except ValueError as e:
        print(f"velaris capabilities check: {e}", file=sys.stderr)
        return 2
    result = capabilities_compare(baseline, capability_scan(root),
                                  CAPABILITIES_FILE)
    code = 1 if result["widened"] else 0
    if "--json" in flags:
        print(json.dumps(result, indent=2))
        return code
    if "--sarif" in flags:
        log = sarif_capabilities(result)
        print(json.dumps(log, indent=2))
        print_sarif_summary(log)
        for w in result["warnings"]:
            print(f"warning: {w}", file=sys.stderr)
        return code
    print(f"velaris capabilities check: {result['programs']} program(s) "
          f"under {root}, {result['compared']} compared, against "
          f"{CAPABILITIES_FILE} (Velaris {baseline.get('velaris_version')}, "
          f"{baseline.get('date')})")
    for w in result["warnings"]:
        print(f"warning: {w}")
    for item in result["findings"]:
        print()
        print("\n".join(_finding_lines(item)))
    if result["narrowed"]:
        print()
        print("narrowed (not a failure):")
        for n in result["narrowed"]:
            print(f"  {n}")
    if result["notes"]:
        print()
        for n in result["notes"][:20]:
            print(f"note: {n}")
        if len(result["notes"]) > 20:
            print(f"note: and {len(result['notes']) - 20} more")
    print()
    if result["widened"]:
        print(f"{len(result['findings'])} widening(s): the code needs more "
              f"than {CAPABILITIES_FILE} declares. If it is all intended, "
              f"make the edits above, or record the surface again and "
              f"commit the file so the widening shows in review:\n"
              f"    velaris capabilities init {root} --force")
    else:
        print(f"no widening: every program is inside {CAPABILITIES_FILE}")
    return code


# ---- review: a git ref against the working tree -----------------------------

def _git(args: list[Any], cwd: str, binary: bool = False) -> Any:
    import subprocess
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          timeout=300)
    if done.returncode != 0:
        raise RuntimeError(done.stderr.decode("utf-8", "replace").strip()
                           or f"git {' '.join(args)} failed")
    return done.stdout if binary else done.stdout.decode("utf-8", "replace")


def _review_side(root: str, use_git: bool = True) -> dict[str, Any]:
    """What review compares on one side: the capability scan, and for
    every file the functions' promise statuses and fallibility, as
    `velaris proofs` counts them."""
    scan = capability_scan(root, use_git)
    proven = runtime = 0
    functions = {}
    for rel in scan["programs"]:
        rep = inspect_source(os.path.join(root, rel))
        here = os.path.abspath(os.path.join(root, rel))
        for f in rep["functions"]:
            if os.path.abspath(f["file"]) != here:
                continue
            functions[(rel, f["name"])] = f
            proven += f["status"] == "proven"
            runtime += f["status"] == "checked at runtime"
    share = round(100.0 * proven / (proven + runtime), 1) \
        if proven + runtime else None
    lits: dict[Any, Any] = {"hosts": set(), "read": set(), "write": set(),
                  "modules": set()}
    for p in scan["programs"].values():
        if p["compiles"]:
            for k in lits:
                lits[k] |= set(p["_lits"][k])
    return {"scan": scan, "functions": functions, "proven_share": share,
            "lits": lits}


def review(against: str, root: str = ".") -> dict[str, Any]:
    """The delta from a git ref to the working tree, as facts: whether
    the capability surface changed, the proven share before and after,
    the functions that became fallible, the hosts, paths and modules
    newly named, and a one-word risk computed from those facts alone -
    `high` when the surface widened, `medium` when it did not but a
    program or function the ref had came to need more or the proven
    share fell, `low` otherwise. The ref's files are read with
    `git show REF:PATH` into a scratch directory; nothing is checked
    out. RuntimeError when git cannot answer."""
    import shutil
    import tempfile
    top = _git(["rev-parse", "--show-toplevel"], root).strip()
    try:
        commit = _git(["rev-parse", "--verify", "--quiet",
                       f"{against}^{{commit}}"], root).strip()
    except RuntimeError:
        raise RuntimeError(f"no commit called '{against}' in this "
                           f"repository (a shallow clone may need: git "
                           f"fetch --depth=1 origin {against})")
    # where root sits in the repository, as git itself says - not by
    # comparing paths, which differ when one side is a Windows short
    # name (RUNNER~1) or a link (macOS's /var is /private/var)
    rel_root = _git(["rev-parse", "--show-prefix"], root).strip() \
        .rstrip("/") or "."
    listed = _git(["ls-tree", "-r", "--name-only", "-z", commit], top)
    scratch = tempfile.mkdtemp(prefix="velaris-review-")
    try:
        for name in (n for n in listed.split("\0") if n.endswith(".vel")):
            blob = _git(["show", f"{commit}:{name}"], top, binary=True)
            dest = os.path.join(scratch, *name.split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as fh:
                fh.write(blob)
        before_root = os.path.join(scratch, *([] if rel_root == "."
                                              else rel_root.split("/")))
        os.makedirs(before_root, exist_ok=True)
        declared_name = CAPABILITIES_FILE if rel_root == "." \
            else f"{rel_root}/{CAPABILITIES_FILE}"
        declared_before = None
        if declared_name in listed.split("\0"):
            declared_before = _git(["show", f"{commit}:{declared_name}"],
                                   top)
        before = _review_side(before_root, use_git=False)
        before_doc = capabilities_document(before["scan"], "")
        after = _review_side(root)
        delta = capabilities_compare(before_doc, after["scan"],
                                     f"{against} ({commit[:7]})")
        backwards = capabilities_compare(
            capabilities_document(after["scan"], ""), before["scan"])
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    surface_widened = [f for f in delta["findings"]
                       if f.get("outside_surface")]
    others = [f for f in delta["findings"] if not f.get("outside_surface")]
    narrowed = [f for f in backwards["findings"]
                if f.get("outside_surface")]
    change = ("widened and narrowed" if surface_widened and narrowed
              else "widened" if surface_widened
              else "narrowed" if narrowed else "unchanged")
    b_share, a_share = before["proven_share"], after["proven_share"]
    fell = (b_share is not None and a_share is not None
            and a_share < b_share) or (
        b_share is not None and b_share > 0 and a_share is None)
    new_fallible = sorted(
        ({"file": rel, "function": name, "line": f["line"]}
         for (rel, name), f in after["functions"].items()
         if f["can_fail"] and not before["functions"].get(
             (rel, name), {}).get("can_fail")),
        key=lambda x: (x["file"], x["line"]))
    newly = {k: sorted(after["lits"][k] - before["lits"][k])
             for k in after["lits"]}
    because = []
    for f in surface_widened:
        because.append("the capability surface widened: " + (
            f"{f['grant']}" + (" (a new effect)" if f["new_effect"] else "")
            if f["kind"] == "grant" else
            f"{f['effect']} operations in {f['file']}"))
    for f in others:
        because.append(
            f"{f['file']}: {f['function']} gained "
            f"{', '.join(f['gained'])}" if f["kind"] == "function" else
            f"{', '.join(q['file'] for q in f['programs'])} came to "
            f"need {f['grant']}" if f["kind"] == "grant" else
            f"{f['file']}: more {f['effect']} operations in a run")
    if fell:
        because.append(f"the proven share fell from {b_share}% to "
                       f"{a_share if a_share is not None else 'none'}"
                       + ("%" if a_share is not None else ""))
    declared = _declared_change(declared_before,
                                os.path.join(root, CAPABILITIES_FILE))
    if declared["removed"]:
        because.append(f"{CAPABILITIES_FILE} was removed, which turns "
                       f"the capability ratchet off")
    if declared["widened"]:
        because.append(f"the surface declared in {CAPABILITIES_FILE} "
                       f"widened: " + ", ".join(declared["widened"]))
    risk = ("high" if surface_widened or declared["removed"]
            or declared["widened"] else
            "medium" if others or fell else "low")
    return {"schema": REVIEW_SCHEMA, "velaris_version": VERSION,
            "declared": declared,
            "against": against, "commit": commit, "root": root,
            "prover": bool(HAVE_Z3),
            "surface": {"change": change,
                        "before": before["scan"]["surface"],
                        "after": after["scan"]["surface"],
                        "widened": surface_widened,
                        "narrowed": [f["grant"] if f["kind"] == "grant"
                                     else f"{f['effect']} operations in "
                                          f"{f['file']}"
                                     for f in narrowed]},
            "programs_came_to_need_more": others,
            "proven_share": {"before": b_share, "after": a_share,
                             "fell": fell},
            "new_fallible": new_fallible,
            "new_hosts": newly["hosts"],
            "new_paths": {"read": newly["read"], "write": newly["write"]},
            "new_modules": newly["modules"],
            "does_not_compile": sorted(
                rel for rel, p in after["scan"]["programs"].items()
                if not p["compiles"]
                and before["scan"]["programs"].get(rel, {}).get(
                    "compiles", True)),
            "risk": risk, "risk_because": because}


def _declared_change(before_text: Any, after_path: str) -> dict[Any, Any]:
    """How the declared surface - velaris.capabilities - changed between
    the ref (its text, or None) and the working tree: whether it was
    added or removed, and the surface grants and counts it widened or
    narrowed. A baseline widened in a pull request is the acceptance of
    a widening, and a reviewer should see it named."""
    def surface(text: Any) -> tuple[Any, ...] | None:
        try:
            doc = json.loads(text)
            got = doc["surface"]
            for g in got["grants"]:
                _grant_parts(g)
            return got["grants"], got.get("counts", {})
        except (ValueError, KeyError, TypeError):
            return None

    after_text = None
    if os.path.exists(after_path):
        with open(after_path, encoding="utf-8") as fh:
            after_text = fh.read()
    out: dict[str, Any] = {"before": before_text is not None, "after": after_text is not None,
           "removed": before_text is not None and after_text is None,
           "added": before_text is None and after_text is not None,
           "widened": [], "narrowed": []}
    b = surface(before_text) if before_text is not None else None
    a = surface(after_text) if after_text is not None else None
    if b is None or a is None:
        if before_text is not None and after_text is not None:
            out["widened"].append("the file could not be read on one side")
        return out
    (bg, bc), (ag, ac) = b, a
    out["widened"] += [g for g in ag if not _covered(g, bg)]
    out["narrowed"] += [g for g in bg if not _covered(g, ag)]
    for e in COUNTED_EFFECTS:
        if e in ac and e in bc:
            if _count_exceeds(ac[e], bc[e]):
                out["widened"].append(f"{e} count {bc[e]} -> "
                                      f"{'none' if ac[e] is None else ac[e]}")
            elif _count_exceeds(bc[e], ac[e]):
                out["narrowed"].append(f"{e} count {bc[e]} -> {ac[e]}")
    return out


def review_main(argv: list[Any]) -> int:
    """velaris review --against REF [path] [--json]"""
    usage = "usage: velaris review --against REF [path] [--json]"
    ref = None
    places, as_json = [], False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--against":
            if i + 1 >= len(argv):
                print(usage, file=sys.stderr)
                return 2
            ref = argv[i + 1]
            i += 2
            continue
        if a == "--json":
            as_json = True
        elif a.startswith("-"):
            print(usage, file=sys.stderr)
            return 2
        else:
            places.append(a)
        i += 1
    if ref is None or len(places) > 1:
        print(usage, file=sys.stderr)
        return 2
    root = places[0] if places else "."
    try:
        got = review(ref, root)
    except (RuntimeError, OSError) as e:
        print(f"velaris review: {e}", file=sys.stderr)
        return 2
    if as_json:
        print(json.dumps(got, indent=2))
        return 0

    def share(v: Any) -> Any:
        return "no promises" if v is None else f"{v}%"

    print(f"velaris review: {root} against {ref} ({got['commit'][:7]})")
    print(f"  capability surface: {got['surface']['change']}")
    for f in got["surface"]["widened"]:
        print("\n".join("    " + line for line in _finding_lines(f)[:-1]))
    for n in got["surface"]["narrowed"]:
        print(f"    - {n}")
    for f in got["programs_came_to_need_more"]:
        print("\n".join("    " + line for line in _finding_lines(f)[:-1]))
    ps = got["proven_share"]
    print(f"  proven share: {share(ps['before'])} -> {share(ps['after'])}"
          + (" (fell)" if ps["fell"] else "")
          + ("" if got["prover"] else
             "   (no prover here: every promise counts as checked at "
             "runtime, on both sides)"))
    print("  new fallible functions: " + (", ".join(
        f"{x['file']}: {x['function']}" for x in got["new_fallible"])
        or "none"))
    print("  new hosts: " + (", ".join(got["new_hosts"]) or "none"))
    paths = [f"{p} (read)" for p in got["new_paths"]["read"]] + \
        [f"{p} (write)" for p in got["new_paths"]["write"]]
    print("  new paths: " + (", ".join(paths) or "none"))
    print("  new modules: " + (", ".join(got["new_modules"]) or "none"))
    if got["does_not_compile"]:
        print("  no longer compiles, or new and does not: "
              + ", ".join(got["does_not_compile"]))
    d = got["declared"]
    if d["removed"]:
        print(f"  {CAPABILITIES_FILE}: REMOVED - the ratchet is off")
    elif d["added"]:
        print(f"  {CAPABILITIES_FILE}: added")
    elif d["widened"] or d["narrowed"]:
        print(f"  {CAPABILITIES_FILE}: "
              + "; ".join([f"+ {w}" for w in d["widened"]]
                          + [f"- {n}" for n in d["narrowed"]]))
    print(f"risk: {got['risk']}" + (
        " - " + "; ".join(got["risk_because"]) if got["risk_because"]
        else " - nothing widened and the proven share did not fall"))
    return 0
