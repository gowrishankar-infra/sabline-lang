#!/usr/bin/env python3
"""Property-based tests: random valid Velaris programs, held to five laws.

fuzz_native.py draws a handful of fixed program shapes; this suite builds
whole programs from Hypothesis strategies - records, functions over Int,
Bool, Text, lists and records, arithmetic and comparisons, `let`,
`if`/`else`, counter loops that end, `for` over ranges and lists, calls
between the generated functions, fallible functions handled with `check`
and `try`, inline function values, contracts the prover settles quickly,
and effectful calls in the functions that declare them. Every program the
strategies make passes `velaris.check`; that is asserted inside the
strategy, so a generator that makes a bad program fails loudly instead of
being filtered away.

The laws:

  1. parse(fmt(p)) == parse(p), comparing syntax trees with every line,
     and anything else that is only a location, ignored
  2. fmt(fmt(p)) == fmt(p)
  3. check(p) twice gives the same problems, proven and runtime lists
  4. the audit's effects are exactly the effects a run attempts, under a
     budget granting every effect
  5. one effect added (and, the converse, removed) changes the audit's
     effects by exactly that effect, and no field that does not follow
     from it
  6. stdlib/csv.vel quotes as RFC 4180 does (8.3): for any row of fields
     holding commas, double quotes, CR and LF, fields(line_of(row)) is the
     row, and rows_of keeps a line feed inside a quoted field in its row

    python check_properties.py                 # CI: 25 examples each
    python check_properties.py --examples 60
    python check_properties.py --seed 7        # a different, fixed draw
    python check_properties.py --long          # a few hundred each
    python check_properties.py --only 4,5
    python check_properties.py --proof-timeout 3   # the prover's default
"""
from __future__ import annotations

import contextlib
import dataclasses
import http.server
import io
import os
import random
import re
import sys
import threading
import time
import warnings
from pathlib import Path
from typing import Any, Callable, cast

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import velaris  # noqa: E402
from velaris import nodes as _nodes  # noqa: E402
from suite_dirs import isolate  # noqa: E402

try:
    from hypothesis import HealthCheck, Phase, given, settings  # noqa: E402
    from hypothesis import seed as hypothesis_seed  # noqa: E402
    from hypothesis import strategies as st  # noqa: E402
    from hypothesis.errors import HypothesisWarning  # noqa: E402
except ImportError:                                   # pragma: no cover
    print("check_properties.py needs hypothesis: pip install hypothesis")
    sys.exit(2)

# velaris raises Python's recursion limit when it loads a program
# (loader.py) and while it runs one (runtime.py); Hypothesis notices after
# every test and warns. Expected here, and noise in the output.
warnings.filterwarnings("ignore", message="The recursion limit will not be "
                        "reset", category=HypothesisWarning)

WORK = isolate("check_properties")
# Hypothesis keeps a cache (the constants it reads out of local source)
# under its home directory, the current one unless told: keep it in this
# suite's own directory, not beside the source
from hypothesis.configuration import set_hypothesis_home_dir  # noqa: E402
set_hypothesis_home_dir(str(WORK / "hypothesis"))

# Nothing here may reach the internet: the one host a program fetches is a
# listener on 127.0.0.1 started below, and no ambient proxy may carry it.
os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1,localhost"

DATA_FILE = WORK / "data.txt"
DATA_FILE.write_text("property data\n", encoding="utf-8")
DATA_PATH = str(DATA_FILE).replace("\\", "/")      # a Velaris text literal


class _Quiet(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:                                  # noqa: N802
        body = b"ok"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:
        pass


_SERVER = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Quiet)
threading.Thread(target=_SERVER.serve_forever, daemon=True).start()
PORT = _SERVER.server_address[1]
URL = f"http://127.0.0.1:{PORT}/"

FREEZE = "2026-01-01T00:00:00Z"
RUN_SEED = 1234


def quietly(fn: Any, *args: Any, **kw: Any) -> Any:
    """Call into velaris with its stderr notes (no z3, no llvmlite) kept
    off the suite's output."""
    with contextlib.redirect_stderr(io.StringIO()):
        return fn(*args, **kw)


def check(src: Any) -> Any:
    return quietly(velaris.check, src, timeout=None, max_memory_mb=None)


def audit(src: Any) -> Any:
    return quietly(velaris.audit, src, timeout=None, max_memory_mb=None)


# ---------------------------------------------------------------------------
# Layout noise: the same tokens, laid out differently
# ---------------------------------------------------------------------------

_WORDY = re.compile(r"[A-Za-z0-9_]")


def _must_separate(prev: str, nxt: str) -> bool:
    """Would writing these two tokens with nothing between them lex as
    something else?"""
    if not prev or not nxt:
        return False
    if _WORDY.match(prev[-1]) and _WORDY.match(nxt[0]):
        return True
    pair = prev[-1] + nxt[0]
    return pair in ("//", "==", "<=", ">=", "!=", "->", "=>") or \
        (prev[-1].isdigit() and nxt[0] == ".") or \
        (prev[-1] == "." and nxt[0].isdigit())


def add_noise(src: str, rng: random.Random, level: int) -> str:
    """Re-lay `src` out without changing its tokens: other spacing between
    tokens, line breaks inside statements, indentation, trailing comments,
    blank and comment-only lines, and CRLF line ends. Whitespace is
    insignificant in Velaris, so the syntax tree is the same up to lines."""
    if level <= 0:
        return src
    toks = velaris.lex(src, keep_trivia=True)
    out = []
    comment_words = ["note", "x = 1", "TODO: {}", "a // b", "-", "fn main"]
    nl = "\n"

    def newline() -> None:
        if rng.random() < 0.1 * level:
            out.append("  // " + rng.choice(comment_words))
        out.append("\r\n" if rng.random() < 0.05 * level else nl)
        if rng.random() < 0.05 * level:
            out.append(rng.choice(["", "// only a comment", "   "]) + nl)
        out.append(rng.choice(["", "  ", "    ", "\t", "        ", " "]))

    prev = None
    for t in toks:
        if t.kind == "EOF":
            break
        if t.kind == "NEWLINE":
            newline()
            prev = None
            continue
        if t.kind == "COMMENT":
            out.append(" " + t.text)
            prev = None
            continue
        if prev is not None:
            r = rng.random()
            if r < 0.04 * level:
                newline()
            elif r < 0.25 * level:
                out.append(rng.choice(["", "  ", "\t", "   "]))
                if out[-1] == "" and _must_separate(prev, t.text):
                    out[-1] = " "
            else:
                out.append(" ")
        out.append(t.text)
        prev = t.text
    return "".join(out)


# ---------------------------------------------------------------------------
# Syntax trees compared up to locations (property 1)
# ---------------------------------------------------------------------------

NODE_TYPES = {cls for cls in vars(_nodes).values()
              if isinstance(cls, type) and dataclasses.is_dataclass(cls)
              and cls.__module__ == _nodes.__name__}
# fields that say only where something is
LOCATION_FIELDS = {"line", "src_file"}
# fields holding [(expr, line)]: the line in each pair is a location too
CLAUSE_FIELDS = {("Function", "requires"), ("Function", "ensures"),
                 ("While", "invariants")}
# names the parser makes up from a counter it never resets (Parser.lambda_n)
GENERATED_NAME = re.compile(r"^(fn|for)#\d+$")

_KNOWN_FIELDS = {"Num": {"value"}, "FloatNum": {"value"},
                 "Neg": {"value", "line"}, "Str": {"value"},
                 "Bool": {"value"}, "Closure": {"name", "free", "line"},
                 "Var": {"name", "line"},
                 "BinOp": {"op", "left", "right", "line"},
                 "Call": {"name", "args", "line"},
                 "Let": {"name", "value", "line", "ann"},
                 "Return": {"value", "line"},
                 "If": {"cond", "then", "other", "line"},
                 "While": {"cond", "body", "line", "invariants"},
                 "Assign": {"name", "value", "line"},
                 "Not": {"value", "line"},
                 "RecordLit": {"name", "fields", "line"},
                 "FieldGet": {"obj", "field", "line"},
                 "RecordDef": {"name", "fields", "line", "src_file"},
                 "ListLit": {"items", "line"},
                 "MapLit": {"entries", "line"},
                 "Block": {"stmts", "line"},
                 "ExprStmt": {"expr", "line"},
                 "FailStmt": {"value", "line"},
                 "TryExpr": {"value", "line"},
                 "Check": {"subject", "line", "ok_name", "ok_body",
                           "fail_name", "fail_body"},
                 "Function": {"name", "params", "return_type", "effects",
                              "requires", "ensures", "body", "line",
                              "src_file", "can_fail", "type_vars",
                              "is_lambda", "captures"}}


def nodes_are_known() -> str | None:
    """The comparison is written over velaris/nodes.py as it is: a node or
    a field added there must be classified here (location or not) before
    this suite can say two trees are the same. None when it is current."""
    have = {c.__name__: {f.name for f in dataclasses.fields(c)}
            for c in NODE_TYPES}
    if have != _KNOWN_FIELDS:
        return (f"velaris/nodes.py changed: {sorted(have.items())} - "
                f"classify the new fields in check_properties.py")
    return None


def shape(node: Any, names: dict[Any, Any]) -> Any:
    """A comparable value for a parsed program, with locations dropped and
    the parser's counter names numbered by first appearance."""
    if isinstance(node, type):
        raise TypeError(f"a class in a syntax tree: {node!r}")
    if dataclasses.is_dataclass(node):
        if type(node) not in NODE_TYPES:
            raise TypeError(f"not a velaris.nodes node: {type(node)}")
        cls = type(node).__name__
        out: list[Any] = [cls]
        declared = set()
        for f in dataclasses.fields(node):
            declared.add(f.name)
            if f.name in LOCATION_FIELDS:
                continue
            value = getattr(node, f.name)
            if (cls, f.name) in CLAUSE_FIELDS:
                out.append((f.name, tuple(shape(e, names)
                                          for e, _line in value)))
            else:
                out.append((f.name, shape(value, names)))
        for extra in sorted(set(vars(node)) - declared):   # free_names
            out.append((extra, shape(getattr(node, extra), names)))
        return tuple(out)
    if isinstance(node, (list, tuple)):
        return (type(node).__name__, tuple(shape(x, names) for x in node))
    if isinstance(node, (set, frozenset)):
        return ("set", tuple(sorted(shape(x, names) for x in node)))
    if isinstance(node, str):
        if GENERATED_NAME.match(node):
            kind = node.split("#")[0]
            if node not in names:
                names[node] = f"{kind}#{len(names) + 1}"
            return ("str", names[node])
        return ("str", node)
    if node is None or isinstance(node, (bool, int, float)):
        return (type(node).__name__, node)
    raise TypeError(f"unexpected value in a syntax tree: {node!r}")


def parse_shape(src: str) -> tuple[Any, ...]:
    funcs, records, imports = velaris.Parser(velaris.lex(src)).parse_program()
    names: dict[Any, Any] = {}
    return (tuple(shape(f, names) for f in funcs),
            tuple(shape(r, names) for r in records),
            tuple((path, alias) for path, _line, alias in imports))


def first_difference(a: Any, b: Any, path: str = "program") -> Any:
    """Where two shapes first differ, for a readable failure."""
    if type(a) is not type(b):
        return f"{path}: {a!r} != {b!r}"
    if isinstance(a, tuple):
        if len(a) != len(b):
            return f"{path}: {len(a)} parts != {len(b)} parts ({a!r:.200} " \
                   f"vs {b!r:.200})"
        for i, (x, y) in enumerate(zip(a, b)):
            label = x[0] if (isinstance(x, tuple) and len(x) == 2
                             and isinstance(x[0], str)) else i
            d = first_difference(x, y, f"{path}/{label}")
            if d:
                return d
        return None
    return None if a == b else f"{path}: {a!r} != {b!r}"


# ---------------------------------------------------------------------------
# The generator: valid programs by construction
#
# Validity is kept by construction rather than by filtering. Every value
# the generator writes has a known bound, so no arithmetic outgrows 64 bits
# while running; divisors are non-zero literals; a list is read at 0 only
# when it is known to hold something; a loop's limit is a small literal and
# its counter moves one step; a call to a function with a `requires` passes
# a literal inside it; an `ensures` is made true by the return that follows
# it. The calls a function makes unconditionally (its "top" calls) come
# first in its body, so what main reaches that way is certain to run.
# ---------------------------------------------------------------------------

PB = 10 ** 6          # the largest Int a variable, field, argument or result holds
TB = 10 ** 5          # the longest Text held anywhere
TP = 1000             # the longest Text passed as an argument
LB = 40               # the longest list
LOOP_MAX = 6


class V:
    """What the generator knows about a value: its type, and a bound -
    magnitude for an Int, length for a Text or a list (with `elem`, the
    bound of its items) - and, for a list, whether it holds anything."""
    __slots__ = ("type", "bound", "elem", "nonempty")

    def __init__(self, type_: Any, bound: int = 0, elem: int = 0, nonempty: bool = False) -> None:
        self.type, self.bound, self.elem, self.nonempty = \
            type_, bound, elem, nonempty


def param_value(t: str) -> V:
    if t == "Int":
        return V(t, PB)
    if t == "Text":
        return V(t, TP)
    if t == "List of Int":
        return V(t, LB, PB, False)
    return V(t)


def fits_param(v: V, t: str) -> bool:
    if t == "Int":
        return v.bound <= PB
    if t == "Text":
        return v.bound <= TP
    if t == "List of Int":
        return v.bound <= LB and v.elem <= PB
    return True


class Fn:
    """A generated function, rendered later: its effects are what its own
    sites and its callees perform, so they are known only then."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.params: list[Any] = []            # [(name, type)]
        self.ret: str | None = None
        self.kind = "plain"               # plain | contract | fallible
        self.lo = self.hi = 0             # contract / fallible first param
        self.clauses: list[Any] = []           # "requires ..." / "ensures ..."
        self.top: list[Any] = []               # lines: unconditional calls, first
        self.body: list[Any] = []              # lines
        self.callees: set[Any] = set()
        self.top_callees: list[Any] = []
        self.ret_v = V("Unit")


class Gen:
    def __init__(self, draw: Any) -> None:
        self.draw = draw
        self.records: list[Any] = []           # [(name, [(field, type)])]
        self.funcs: list[Any] = []             # finished, in order
        self.n = 0
        self.fn: Fn | None = None         # the function being written

    # -- draws ------------------------------------------------------------
    def pick(self, seq: Any) -> Any:
        return self.draw(st.sampled_from(list(seq)))

    def num(self, a: int, b: int) -> int:
        return cast(int, self.draw(st.integers(a, b)))

    def flag(self, p_true_weight: int = 1) -> bool:
        return self.num(0, p_true_weight) > 0

    def fresh(self, stem: str) -> str:
        self.n += 1
        return f"{stem}{self.n}"

    def types(self) -> list[Any]:
        return ["Int", "Bool", "Text", "List of Int"] + \
            [r for r, _ in self.records]

    def fields_of(self, rec: str) -> list[Any]:
        return cast(list[Any], dict(self.records)[rec])

    def field_reads(self, scope: dict[Any, Any], t: str) -> list[Any]:
        """(variable, field) for every record field of type t in scope."""
        recs = dict(self.records)
        return [(n, f) for n, v in scope.items() if v.type in recs
                for f, ft in recs[v.type] if ft == t]

    # -- expressions ------------------------------------------------------
    def int_lit(self, lo: int = -9, hi: int = 60) -> tuple[Any, ...]:
        k = self.num(lo, hi)
        return (str(k) if k >= 0 else f"-{-k}"), V("Int", abs(k))

    def text_lit(self) -> tuple[str, V]:
        pieces = self.draw(st.lists(st.sampled_from(
            ["a", "b", "X", "0", "9", " ", "_", "-", ".", "\\n", "\\t",
             '\\"', "\\\\"]), max_size=5))
        return '"' + "".join(pieces) + '"', V("Text", len(pieces))

    def callable(self, t: str) -> list[Any]:
        return [f for f in self.funcs
                if f.ret == t and f.kind != "fallible"]

    def call(self, f: Fn, scope: dict[Any, Any]) -> str:
        args = []
        for i, (_p, t) in enumerate(f.params):
            if i == 0 and f.kind == "contract":
                args.append(str(self.num(f.lo, f.hi)))
            elif i == 0 and f.kind == "fallible":
                args.append(self.int_lit(-20, 20)[0])
            else:
                args.append(self.atom(t, scope))
        cast(Fn, self.fn).callees.add(f.name)
        return f"{f.name}({', '.join(args)})"

    def atom(self, t: str, scope: dict[Any, Any]) -> str:
        """A variable or a literal of type t that fits a parameter."""
        names = [n for n, v in scope.items()
                 if v.type == t and fits_param(v, t)]
        if names and self.flag():
            return cast(str, self.pick(names))
        return cast(str, self.literal(t, scope)[0])

    def literal(self, t: str, scope: dict[Any, Any]) -> Any:
        if t == "Int":
            return self.int_lit()
        if t == "Bool":
            return self.pick(["true", "false"]), V("Bool")
        if t == "Text":
            return self.text_lit()
        if t == "List of Int":
            items = [self.int_lit()[0] for _ in range(self.num(1, 4))]
            return f"[{', '.join(items)}]", V(t, len(items), 60, True)
        fields = [f"{name}: {self.atom(ft, scope)}"
                  for name, ft in self.fields_of(t)]
        return f"{t}({', '.join(fields)})", V(t)

    def expr(self, t: str, scope: dict[Any, Any], depth: int = 0) -> Any:
        if t == "Int":
            text, v = self.int_expr(scope, depth)
            if v.bound > PB:
                return f"({text} % 1000)", V("Int", 999)
            return text, v
        if t == "Bool":
            return self.bool_expr(scope, depth)
        if t == "Text":
            text, v = self.text_expr(scope, depth)
            return (text, v) if v.bound <= TB else self.text_lit()
        if t == "List of Int":
            return self.list_expr(scope, depth)
        return self.record_expr(t, scope, depth)

    def of_type(self, scope: dict[Any, Any], t: str, pred: Any = lambda v: True) -> list[Any]:
        return [n for n, v in scope.items() if v.type == t and pred(v)]

    def int_expr(self, scope: dict[Any, Any], depth: int) -> Any:
        opts = ["lit"]
        ints = self.of_type(scope, "Int", lambda v: v.bound <= PB)
        if ints:
            opts += ["var", "var"]
        recs = self.field_reads(scope, "Int")
        if recs:
            opts.append("field")
        if depth < 2:
            opts += ["add", "sub", "mul", "div", "mod", "neg"]
            if self.of_type(scope, "Text"):
                opts.append("len_text")
            if self.of_type(scope, "List of Int"):
                opts.append("len_list")
            if self.of_type(scope, "List of Int", lambda v: v.nonempty):
                opts.append("get0")
            if self.callable("Int"):
                opts.append("call")
        k = self.pick(opts)
        if k == "lit":
            return self.int_lit()
        if k == "var":
            name = self.pick(ints)
            return name, V("Int", scope[name].bound)
        if k == "field":
            n, f = self.pick(recs)
            return f"{n}.{f}", V("Int", PB)
        if k in ("add", "sub"):
            a, va = self.int_expr(scope, depth + 1)
            b, vb = self.int_expr(scope, depth + 1)
            op = "+" if k == "add" else "-"
            return f"({a} {op} {b})", V("Int", va.bound + vb.bound)
        if k == "mul":
            a, va = self.int_expr(scope, depth + 1)
            c = self.num(0, 5)
            text = f"({a} * {c})" if self.flag() else f"({c} * {a})"
            return text, V("Int", va.bound * c)
        if k == "div":
            a, va = self.int_expr(scope, depth + 1)
            c = self.num(1, 5)
            return f"({a} / {c})", V("Int", max(va.bound, 1))
        if k == "mod":
            a, _ = self.int_expr(scope, depth + 1)
            c = self.num(1, 9)
            return f"({a} % {c})", V("Int", c)
        if k == "neg":
            a, va = self.int_expr(scope, depth + 1)
            return f"-{a}", va
        if k == "len_text":
            t, vt = self.text_expr(scope, depth + 1)
            return f"length({t})", V("Int", vt.bound)
        if k == "len_list":
            name = self.pick(self.of_type(scope, "List of Int"))
            return f"length({name})", V("Int", LB)
        if k == "get0":
            name = self.pick(self.of_type(scope, "List of Int",
                                          lambda v: v.nonempty))
            return f"get({name}, 0)", V("Int", scope[name].elem)
        f = self.pick(self.callable("Int"))
        return self.call(f, scope), V("Int", f.ret_v.bound)

    def bool_expr(self, scope: dict[Any, Any], depth: int) -> tuple[Any, ...]:
        opts = ["lit", "cmp"]
        if self.of_type(scope, "Bool"):
            opts += ["var", "var"]
        if self.field_reads(scope, "Bool"):
            opts.append("field")
        if depth < 2:
            opts += ["cmp", "text_eq", "text_lt", "not", "and", "or",
                     "contains"]
            if self.of_type(scope, "List of Int"):
                opts.append("all_of")
            if self.callable("Bool"):
                opts.append("call")
        k = self.pick(opts)
        if k == "lit":
            return self.pick(["true", "false"]), V("Bool")
        if k == "var":
            return self.pick(self.of_type(scope, "Bool")), V("Bool")
        if k == "cmp":
            a, _ = self.int_expr(scope, depth + 1)
            b, _ = self.int_expr(scope, depth + 1)
            op = self.pick(["<", ">", "<=", ">=", "==", "!="])
            return f"({a} {op} {b})", V("Bool")
        if k in ("text_eq", "text_lt"):
            a, _ = self.text_expr(scope, depth + 1)
            b, _ = self.text_expr(scope, depth + 1)
            op = self.pick(["==", "!="]) if k == "text_eq" else "<"
            return f"({a} {op} {b})", V("Bool")
        if k == "not":
            a, _ = self.bool_expr(scope, depth + 1)
            return f"not ({a})", V("Bool")
        if k in ("and", "or"):
            a, _ = self.bool_expr(scope, depth + 1)
            b, _ = self.bool_expr(scope, depth + 1)
            return f"({a} {k} {b})", V("Bool")
        if k == "contains":
            a, _ = self.text_expr(scope, depth + 1)
            return f"contains({a}, {self.text_lit()[0]})", V("Bool")
        if k == "all_of":
            xs = self.pick(self.of_type(scope, "List of Int"))
            n = self.fresh("n")
            ints = self.of_type(scope, "Int", lambda v: v.bound <= PB)
            other = (self.pick(ints) if ints and self.flag()
                     else self.int_lit()[0])        # a capture, or not
            which = self.pick(["all_of", "any_of"])
            return (f"{which}({xs}, fn({n}: Int) -> Bool {{ return "
                    f"{n} > {other} }})"), V("Bool")
        if k == "field":
            n, fld = self.pick(self.field_reads(scope, "Bool"))
            return f"{n}.{fld}", V("Bool")
        f = self.pick(self.callable("Bool"))
        return self.call(f, scope), V("Bool")

    def text_expr(self, scope: dict[Any, Any], depth: int) -> Any:
        opts = ["lit"]
        texts = self.of_type(scope, "Text", lambda v: v.bound <= TB)
        if texts:
            opts += ["var", "var"]
        if self.field_reads(scope, "Text"):
            opts.append("field")
        if depth < 2:
            opts += ["concat", "case", "to_text", "format"]
            if self.callable("Text"):
                opts.append("call")
        k = self.pick(opts)
        if k == "lit":
            return self.text_lit()
        if k == "var":
            name = self.pick(texts)
            return name, V("Text", scope[name].bound)
        if k == "concat":
            a, va = self.text_expr(scope, depth + 1)
            b, vb = self.text_expr(scope, depth + 1)
            return f"({a} + {b})", V("Text", va.bound + vb.bound)
        if k == "case":
            a, va = self.text_expr(scope, depth + 1)
            return f"{self.pick(['upper', 'lower'])}({a})", va
        if k == "to_text":
            a, _ = self.int_expr(scope, depth + 1)
            return f"to_text({a})", V("Text", 24)
        if k == "format":
            a, va = self.text_expr(scope, depth + 1)
            b, _ = self.int_expr(scope, depth + 1)
            return (f'format("{{}} is {{}}", {a}, {b})',
                    V("Text", va.bound + 30))
        if k == "field":
            n, fld = self.pick(self.field_reads(scope, "Text"))
            return f"{n}.{fld}", V("Text", TP)
        f = self.pick(self.callable("Text"))
        return self.call(f, scope), V("Text", f.ret_v.bound)

    def list_expr(self, scope: dict[Any, Any], depth: int) -> Any:
        opts = ["lit"]
        lists = self.of_type(scope, "List of Int",
                             lambda v: v.bound < LB and v.elem <= PB)
        if lists:
            opts += ["var", "push"]
        if depth < 2 and self.callable("List of Int"):
            opts.append("call")
        k = self.pick(opts)
        if k == "lit":
            return self.literal("List of Int", scope)
        if k == "var":
            name = self.pick(lists)
            v = scope[name]
            return name, V(v.type, v.bound, v.elem, v.nonempty)
        if k == "push":
            name = self.pick(lists)
            e, ve = self.expr("Int", scope, depth + 1)
            v = scope[name]
            return (f"push({name}, {e})",
                    V(v.type, v.bound + 1, max(v.elem, ve.bound), True))
        f = self.pick(self.callable("List of Int"))
        return self.call(f, scope), V(f.ret_v.type, f.ret_v.bound,
                                      f.ret_v.elem, f.ret_v.nonempty)

    def record_expr(self, t: str, scope: dict[Any, Any], depth: int) -> tuple[Any, ...]:
        opts = ["lit"]
        if self.of_type(scope, t):
            opts.append("var")
        if depth < 2 and self.callable(t):
            opts.append("call")
        k = self.pick(opts)
        if k == "var":
            return self.pick(self.of_type(scope, t)), V(t)
        if k == "call":
            return self.call(self.pick(self.callable(t)), scope), V(t)
        fields = []
        for name, ft in self.fields_of(t):
            text, v = self.expr(ft, scope, max(depth + 1, 1))
            if not fits_param(v, ft):
                text = self.literal(ft, scope)[0]
            fields.append(f"{name}: {text}")
        return f"{t}({', '.join(fields)})", V(t)


def indent(lines: list[Any], times: int = 1) -> list[Any]:
    return ["    " * times + x for x in lines]


def union_v(vs: list[Any], t: str) -> V:
    if not vs:
        return V(t)
    return V(t, max(v.bound for v in vs), max(v.elem for v in vs),
             all(v.nonempty for v in vs))


class Statements(Gen):
    """Statements, functions and main, on top of the expressions."""

    def fallible(self) -> list[Any]:
        return [f for f in self.funcs if f.kind == "fallible"]

    def void(self) -> list[Any]:
        return [f for f in self.funcs if f.ret is None and f.kind == "plain"
                and f.name != "main"]

    def block(self, scope: dict[Any, Any], depth: int, returns: bool,
              least: int = 1) -> list[Any]:
        """A nested block. The names it binds stay inside it; a `return`
        or `fail`, when it has one, is its last statement."""
        inner = dict(scope)
        lines: list[Any] = []
        for _ in range(self.num(least, 2)):
            lines += self.statement(inner, depth)
        f = cast(Fn, self.fn)
        if returns and f.ret is not None and f.kind != "contract" \
                and self.flag():
            text, v = self.expr(f.ret, inner)
            self.ret_vs.append(v)
            lines.append(f"return {text}")
        elif returns and f.kind == "fallible" and self.flag():
            lines.append(f"fail {self.reason(inner)}")
        return lines

    def reason(self, scope: dict[Any, Any]) -> str:
        if self.flag():
            return self.text_lit()[0]
        return f'format("refused {{}}", {self.atom("Int", scope)})'

    def accumulate(self, scope: dict[Any, Any], inner: dict[Any, Any], acc: str, turns: int) -> tuple[Any, ...]:
        e, ve = self.expr("Int", inner, 1)
        total = turns * ve.bound
        if total <= PB:
            step, bound = f"{acc} = {acc} + {e}", total
        else:
            step, bound = f"{acc} = ({acc} + {e}) % 1000", 999
        if not self.flag(2):                  # a third of the time
            cond, _ = self.bool_expr(inner, 1)
            return [f"if {cond} {{", "    " + step, "}"], bound
        return [step], bound

    def statement(self, scope: dict[Any, Any], depth: int) -> list[Any]:
        f = cast(Fn, self.fn)
        kinds = ["let", "let"]
        if depth < 2:
            kinds.append("if")
        if depth == 0 and f.kind != "contract":
            kinds += ["while", "for_range", "text_acc", "list_acc"]
            if self.of_type(scope, "List of Int", lambda v: v.elem <= PB):
                kinds.append("for_each")
        if self.fallible():
            kinds.append("check")
            if f.kind == "fallible":
                kinds.append("try")
        if self.void():
            kinds.append("void")
        k = self.pick(kinds)
        if k == "let":
            t = self.pick(self.types())
            text, v = self.expr(t, scope)
            name = self.fresh("v")
            scope[name] = v
            if self.flag():
                return [f"let {name}: {t} = {text}"]
            return [f"let {name} = {text}"]
        if k == "if":
            cond, _ = self.bool_expr(scope, 0)
            lines = [f"if {cond} {{"] + indent(
                self.block(scope, depth + 1, True)) + ["}"]
            shape_ = self.pick(["none", "else", "else_if"])
            if shape_ == "else":
                lines[-1] = "} else {"
                lines += indent(self.block(scope, depth + 1, False)) + ["}"]
            elif shape_ == "else_if":
                cond2, _ = self.bool_expr(scope, 1)
                lines[-1] = f"}} else if {cond2} {{"
                lines += indent(self.block(scope, depth + 1, False)) + ["}"]
            return lines
        if k == "while":
            turns = self.num(0, LOOP_MAX)
            acc, i = self.fresh("acc"), self.fresh("i")
            inner = dict(scope)
            inner[i] = V("Int", turns)
            body, bound = self.accumulate(scope, inner, acc, turns)
            head = [f"let {acc} = 0", f"let {i} = 0"]
            if self.flag():
                head += [f"while {i} < {turns}", f"invariant {i} >= 0", "{"]
            else:
                head += [f"while {i} < {turns} {{"]
            scope[acc], scope[i] = V("Int", bound), V("Int", turns)
            return head + indent(body + [f"{i} = {i} + 1"]) + ["}"]
        if k == "for_range":
            turns, start = self.num(0, LOOP_MAX), self.num(0, 2)
            acc, kk = self.fresh("acc"), self.fresh("k")
            inner = dict(scope)
            inner[kk] = V("Int", turns)
            body, bound = self.accumulate(scope, inner, acc, turns)
            scope[acc] = V("Int", bound)
            loop_head = f"for {kk} in {start} to {turns}"
            if not self.flag(3):              # a quarter of the time
                return [f"let {acc} = 0", loop_head,
                        f"invariant {kk} >= {start}", "{"] + \
                    indent(body) + ["}"]
            return [f"let {acc} = 0", loop_head + " {"] + indent(body) + ["}"]
        if k == "for_each":
            xs = self.pick(self.of_type(scope, "List of Int",
                                        lambda v: v.elem <= PB))
            acc, x = self.fresh("acc"), self.fresh("x")
            inner = dict(scope)
            inner[x] = V("Int", scope[xs].elem)
            body, bound = self.accumulate(scope, inner, acc, scope[xs].bound)
            scope[acc] = V("Int", bound)
            return [f"let {acc} = 0", f"for {x} in {xs} {{"] + \
                indent(body) + ["}"]
        if k == "text_acc":
            turns = self.num(0, LOOP_MAX)
            s, kk = self.fresh("s"), self.fresh("k")
            if self.flag():
                piece, size = f"to_text({kk})", 24
            else:
                piece, pv = self.text_lit()
                size = pv.bound
            scope[s] = V("Text", turns * size)
            return [f'let {s} = ""', f"for {kk} in 0 to {turns} {{",
                    f"    {s} = {s} + {piece}", "}"]
        if k == "list_acc":
            turns = self.num(0, LOOP_MAX)
            ys, kk = self.fresh("ys"), self.fresh("k")
            inner = dict(scope)
            inner[kk] = V("Int", turns)
            e, ve = self.expr("Int", inner, 1)
            scope[ys] = V("List of Int", turns, ve.bound, False)
            return [f"let {ys}: List of Int = []",
                    f"for {kk} in 0 to {turns} {{",
                    f"    {ys} = push({ys}, {e})", "}"]
        if k == "check":
            return self.check_stmt(scope, depth, self.pick(self.fallible()))
        if k == "try":
            g = self.pick(self.fallible())
            name = self.fresh("t")
            call = self.call(g, scope)
            scope[name] = union_v([g.ret_v], g.ret)
            return [f"let {name} = try {call}"]
        g = self.pick(self.void())
        return [self.call(g, scope)]

    def check_stmt(self, scope: dict[Any, Any], depth: int, g: Fn) -> list[Any]:
        call = self.call(g, scope)
        ok, why = self.fresh("ok"), self.fresh("why")
        ok_scope = dict(scope)
        ok_scope[ok] = union_v([g.ret_v], cast(str, g.ret))
        fail_scope = dict(scope)
        fail_scope[why] = V("Text", 200)
        ok_lines = []
        if self.flag(2):
            t = self.pick([g.ret, "Int", "Text"])
            text, _ = self.expr(t, ok_scope, 1)
            ok_lines = [f"let {self.fresh('w')} = {text}"]
        fail_lines = []
        if self.flag(2):
            text, _ = self.expr("Text", fail_scope, 1)
            fail_lines = [f"let {self.fresh('m')} = {text}"]
        return ([f"check {call} {{", f"    ok {ok} {{"]
                + indent(ok_lines, 2) + ["    }", f"    fail {why} {{"]
                + indent(fail_lines, 2) + ["    }", "}"])

    def top_call(self, g: Fn, scope: dict[Any, Any]) -> list[Any]:
        """A call that runs whenever its caller does: first in the body."""
        if g.kind == "fallible":
            return self.check_stmt(scope, 1, g)
        call = self.call(g, scope)
        if g.ret is None:
            return [call]
        name = self.fresh("u")
        scope[name] = union_v([g.ret_v], g.ret)
        return [f"let {name} = {call}"]

    def record(self) -> None:
        name = self.fresh("R")
        fields = [(self.fresh("fd"), self.pick(["Int", "Text", "Bool"]))
                  for _ in range(self.num(1, 3))]
        self.records.append((name, fields))

    def pick_top(self, most: int) -> list[Any]:
        if not self.funcs or most <= 0:
            return []
        idx = self.draw(st.lists(st.integers(0, len(self.funcs) - 1),
                                 max_size=most, unique=True))
        return [self.funcs[i] for i in idx]

    def function(self, kind: str) -> Fn:
        f = Fn(self.fresh("f"))
        f.kind = kind
        self.fn, self.ret_vs = f, []
        scope: dict[Any, Any] = {}
        first = None
        if kind == "contract":
            first = self.fresh("x")
            f.lo = self.num(-5, 5)
            f.hi = f.lo + self.num(0, 40)
            f.params.append((first, "Int"))
            scope[first] = V("Int", max(abs(f.lo), abs(f.hi)))
            f.ret = "Int"
        elif kind == "fallible":
            first = self.fresh("a")
            f.params.append((first, "Int"))
            scope[first] = V("Int", 20)
            f.ret = self.pick(["Int", "Text"])
        for _ in range(self.num(0, 2 if kind == "plain" else 1)):
            p, t = self.fresh("p"), self.pick(self.types())
            f.params.append((p, t))
            scope[p] = param_value(t)
        if kind == "plain":
            f.ret = self.pick(self.types() + [None])
        for g in self.pick_top(2):
            f.top += self.top_call(g, scope)
            f.top_callees.append(g.name)
        if kind == "fallible":
            f.body += [f"if {first} < {self.num(-10, 10)} {{",
                       f"    fail {self.reason(scope)}", "}"]
        least = 1 if f.ret is None and not f.top else 0
        for _ in range(self.num(least, 3)):
            f.body += self.statement(scope, 0)
        if kind == "contract":
            r = self.fresh("r")
            e, ve = self.expr("Int", scope)
            f.body.append(f"let {r} = {e}")
            k = self.num(-20, 20)
            ks = str(k) if k >= 0 else f"-{-k}"
            form = self.pick(["at_least", "at_most", "at_least_x"])
            f.clauses = [f"requires {first} >= {f.lo} and {first} <= {f.hi}"]
            if form == "at_least":
                f.clauses.append(f"ensures result >= {ks}")
                f.body += [f"if {r} < {ks} {{", f"    return {ks}", "}"]
            elif form == "at_most":
                f.clauses.append(f"ensures result <= {ks}")
                f.body += [f"if {r} > {ks} {{", f"    return {ks}", "}"]
            else:
                f.clauses.append(f"ensures result >= {first}")
                f.body += [f"if {r} < {first} {{", f"    return {first}",
                           "}"]
            f.body.append(f"return {r}")
            f.ret_v = V("Int", max(ve.bound, abs(k), scope[first].bound))
        elif f.ret is not None:
            text, v = self.expr(f.ret, scope)
            self.ret_vs.append(v)
            f.body.append(f"return {text}")
            f.ret_v = union_v(self.ret_vs, f.ret)
        f.callees |= set(f.top_callees)
        self.funcs.append(f)
        self.fn = None
        return f

    def main(self) -> Fn:
        f = Fn("main")
        self.fn, self.ret_vs = f, []
        scope: dict[Any, Any] = {}
        for g in self.pick_top(4):
            f.top += self.top_call(g, scope)
            f.top_callees.append(g.name)
        for _ in range(self.num(0, 2)):
            f.body += self.statement(scope, 0)
        f.callees |= set(f.top_callees)
        self.funcs.append(f)
        self.fn = None
        return f


# ---------------------------------------------------------------------------
# Effect sites, and the program model they are placed in
# ---------------------------------------------------------------------------

def site_text(effect: str, k: int, variant: int) -> str:
    """One call that performs `effect`, written on one line."""
    n = f"s{k}"
    handled = (" {{ ok {n}v {{ let {n}n = {use} }} "
               "fail {n}w {{ let {n}m = {n}w }} }}")
    if effect == "io":
        return (f'print("{n}")', f'log("{n}")')[variant]
    if effect == "env":
        return f'let {n} = env("VELARIS_PROP_{k}", "")'
    if effect == "fs":
        return (f'check read_file("{DATA_PATH}")'
                + handled.format(n=n, use=f"length({n}v)"),
                f'let {n} = file_exists("{DATA_PATH}")')[variant]
    if effect == "net":
        return (f'check fetch("{URL}")'
                + handled.format(n=n, use=f"length({n}v)"),
                f'check fetch_status("{URL}")'
                + handled.format(n=n, use=f"{n}v + 1"))[variant]
    if effect == "clock":
        return f"let {n} = now()"
    if effect == "rand":
        return f"let {n} = random(10)"
    if effect == "ffi":
        return ('check py("math", "floor", ["2.5"])'
                + handled.format(n=n, use=f"length({n}v)"))
    # declassify needs a Secret, and env() is where one comes from
    return (f'let {n} = declassify(env("VELARIS_PROP_{k}", "") == "", '
            f'"property {k}")')


VARIANTS = {"io": 2, "env": 1, "fs": 2, "net": 2, "clock": 1, "rand": 1,
            "ffi": 1, "declassify": 1}


class Site:
    __slots__ = ("effect", "text", "performs")

    def __init__(self, effect: str, k: int, variant: int) -> None:
        self.effect = effect
        self.text = site_text(effect, k, variant)
        self.performs = frozenset({effect, "env"} if effect == "declassify"
                                  else {effect})


class Program:
    """Records and functions as generated, and where effect sites sit.

    A site is written on the line of its function's opening brace, and the
    `uses` clause on the signature line, so adding or removing one moves no
    other line of the program."""

    def __init__(self, gen: Statements, order: list[Any]) -> None:
        self.records = gen.records
        self.funcs = gen.funcs
        self.by = {f.name: f for f in self.funcs}
        self.order = order
        self.sites: dict[str, list[Site]] = {f.name: [] for f in self.funcs}
        self.k = 0
        seen, todo = [], ["main"]
        while todo:                      # what main runs unconditionally
            name = todo.pop()
            if name not in seen:
                seen.append(name)
                todo += self.by[name].top_callees
        self.spine = [f.name for f in self.funcs if f.name in seen]

    def site(self, effect: str, variant: int) -> Site:
        self.k += 1
        return Site(effect, self.k, variant)

    def sites_of(self, name: str, add: Any = None, drop: Any = None) -> list[Any]:
        out = [s for s in self.sites[name]
               if not (drop and drop in s.performs)]
        if add and add[0] == name:
            out.append(add[1])
        return out

    def declared(self, add: Any = None, drop: Any = None) -> dict[Any, Any]:
        """What each function must declare: what its sites perform and its
        callees declare."""
        memo: dict[Any, Any] = {}

        def of(name: Any) -> Any:
            if name not in memo:
                s = set()
                for site in self.sites_of(name, add, drop):
                    s |= site.performs
                for callee in self.by[name].callees:
                    s |= of(callee)
                memo[name] = frozenset(s)
            return memo[name]
        return {f.name: of(f.name) for f in self.funcs}

    def render(self, add: Any = None, drop: Any = None) -> str:
        decl = self.declared(add, drop)
        chunks = []
        for kind, i in self.order:
            if kind == "record":
                name, fields = self.records[i]
                chunks.append("\n".join(
                    [f"record {name} {{"]
                    + [f"    {fname}: {ftype}" for fname, ftype in fields]
                    + ["}"]))
                continue
            f = self.funcs[i]
            sig = f"fn {f.name}(" + ", ".join(
                f"{p}: {t}" for p, t in f.params) + ")"
            if f.ret is not None:
                sig += f" -> {f.ret}"
            if decl[f.name]:
                sig += " uses " + ", ".join(sorted(decl[f.name]))
            if f.kind == "fallible":
                sig += " or fail"
            extra = "".join(" " + s.text
                            for s in self.sites_of(f.name, add, drop))
            if f.clauses:
                lines = [sig] + indent(f.clauses) + ["{" + extra]
            else:
                lines = [sig + " {" + extra]
            chunks.append("\n".join(lines + indent(f.top + f.body) + ["}"]))
        return "\n\n".join(chunks) + "\n"


class Example:
    """What a strategy hands a property; shown as the program itself."""

    # given through **kw, by effect_edits (property 5)
    mode: str
    effect: str
    before: str
    after: str
    declared_before: dict[Any, Any]
    declared_after: dict[Any, Any]

    def __init__(self, source: str, **kw: Any) -> None:
        self.source = source
        self.__dict__.update(kw)

    def __repr__(self) -> str:
        return self.source


def assert_valid(src: str) -> None:
    c = check(src)
    assert c.ok, ("velaris.check refused a generated program - a generator "
                  "bug, or a compiler finding if the program is valid:\n"
                  + src + "\n" + "\n".join(repr(p) for p in c.problems))


def place(draw: Any, prog: Program, effects: Any, most: int = 2) -> None:
    """One or more sites for each effect, on functions main runs."""
    for e in effects:
        for _ in range(draw(st.integers(1, most))):
            host = draw(st.sampled_from(prog.spine))
            variant = draw(st.integers(0, VARIANTS[e] - 1))
            prog.sites[host].append(prog.site(e, variant))


@st.composite
def programs(draw: Any) -> Program:
    g = Statements(draw)
    for _ in range(g.num(0, 2)):
        g.record()
    for _ in range(g.num(1, 4)):
        g.function(g.pick(["plain", "plain", "contract", "fallible"]))
    g.main()
    items = [("record", i) for i in range(len(g.records))] + \
        [("fn", i) for i in range(len(g.funcs))]
    return Program(g, draw(st.permutations(items)))


@st.composite
def valid_sources(draw: Any) -> Example:
    """Properties 1-3: any program, some effects, laid out any way."""
    prog = draw(programs())
    place(draw, prog, draw(st.lists(st.sampled_from(velaris.ALL_EFFECTS),
                                    max_size=3, unique=True)))
    level = draw(st.integers(0, 3))
    rng = random.Random(draw(st.integers(0, 2 ** 16)))
    src = add_noise(prog.render(), rng, level)
    assert_valid(src)
    return Example(src)


@st.composite
def effect_programs(draw: Any) -> Example:
    """Property 4: every effect drawn is performed on a path main runs."""
    prog = draw(programs())
    effects = draw(st.lists(st.sampled_from(velaris.ALL_EFFECTS),
                            min_size=1, unique=True))
    place(draw, prog, effects)
    src = prog.render()
    assert_valid(src)
    return Example(src)


@st.composite
def effect_edits(draw: Any) -> Example:
    """Property 5: a program before and after one effect is added to a
    function main runs (with a call performing it), or removed."""
    prog = draw(programs())
    # one of the sixteen (mode, effect) pairs, drawn from a wide integer so
    # that the draw is not weighted toward the first few; it still shrinks
    combo = draw(st.integers(0, 2 ** 20)) % (2 * len(velaris.ALL_EFFECTS))
    mode = ("add", "remove")[combo % 2]
    effect = velaris.ALL_EFFECTS[combo // 2]
    # a declassify site reads env() as well, so while env is the effect
    # that moves there are none; while declassify moves, env stays put
    others = [e for e in velaris.ALL_EFFECTS if e != effect
              and not (effect == "env" and e == "declassify")]
    base = draw(st.lists(st.sampled_from(others), max_size=4, unique=True))
    if effect == "declassify" and "env" not in base:
        base.append("env")
    add = drop = None
    if mode == "add":
        place(draw, prog, base)
        decl = prog.declared()
        hosts = [h for h in prog.spine
                 if effect != "declassify" or "env" in decl[h]]
        host = draw(st.sampled_from(hosts))
        add = (host, prog.site(effect,
                               draw(st.integers(0, VARIANTS[effect] - 1))))
    else:
        place(draw, prog, base + [effect])
        if effect == "declassify":
            for host, sites in prog.sites.items():
                if any(s.effect == "declassify" for s in sites) and \
                        not any(s.effect == "env" for s in sites):
                    sites.append(prog.site("env", 0))
        drop = effect
    before, after = prog.declared(), prog.declared(add, drop)
    moved = set().union(*before.values()) ^ set().union(*after.values())
    assert moved == {effect}, f"generator: the edit moved {moved}"
    for name in before:
        assert before[name] ^ after[name] <= {effect}, \
            f"generator: {name} moved {before[name] ^ after[name]}"
    src_before, src_after = prog.render(), prog.render(add, drop)
    assert_valid(src_before)
    assert_valid(src_after)
    shown = (f"{mode} {effect}\n--- before ---\n{src_before}"
             f"--- after ---\n{src_after}")
    ex = Example(shown, mode=mode, effect=effect, before=src_before,
                 after=src_after, declared_before=before,
                 declared_after=after)
    return ex


# ---------------------------------------------------------------------------
# The properties
# ---------------------------------------------------------------------------

def prop_parse_after_fmt(ex: Example) -> None:
    formatted = velaris.format_source(ex.source)
    before = parse_shape(ex.source)
    try:
        after = parse_shape(formatted)
    except velaris.VelarisError as e:
        raise AssertionError(
            f"fmt's output does not parse: [{e.code}] line {e.line}: "
            f"{e.message}\n--- fmt output ---\n{formatted}")
    where = first_difference(before, after)
    assert where is None, (f"parse(fmt(p)) != parse(p) at {where}\n"
                           f"--- fmt output ---\n{formatted}")


def prop_fmt_idempotent(ex: Example) -> None:
    once = velaris.format_source(ex.source)
    twice = velaris.format_source(once)
    if twice != once:
        a, b = once.split("\n"), twice.split("\n")
        at = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y),
                  min(len(a), len(b)))
        raise AssertionError(
            f"fmt(fmt(p)) != fmt(p), first at line {at + 1}:\n"
            f"  fmt(p):      {a[at] if at < len(a) else '<end>'!r}\n"
            f"  fmt(fmt(p)): {b[at] if at < len(b) else '<end>'!r}\n"
            f"--- fmt(p) ---\n{once}")


def check_answer(src: str) -> tuple[Any, ...]:
    c = check(src)
    return ([(p.code, p.line, p.message) for p in c.problems],
            list(c.proven), list(c.runtime_checked))


def prop_check_deterministic(ex: Example) -> None:
    first, second = check_answer(ex.source), check_answer(ex.source)
    assert first == second, (f"check(p) answered twice differently:\n"
                             f"  first:  {first}\n  second: {second}")


def prop_audit_says_what_runs(ex: Example) -> None:
    a = audit(ex.source)
    assert a.ok, f"the audit refused it: {a.problems}"
    r = quietly(velaris.run, ex.source, allow=set(velaris.ALL_EFFECTS),
                seed=RUN_SEED, freeze_time=FREEZE)
    assert r.ok and r.exit_code == 0, (
        f"the run did not finish (so it cannot say what it attempts): "
        f"exit {r.exit_code}, refused {r.refused_effect}, {r.problems}\n"
        f"output: {r.output[-400:]!r}\nlogs: {r.logs[-400:]!r}")
    attempted = {k for k, v in (r.effects_used or {}).items() if v}
    assert set(a.effects) == attempted, (
        f"audit(p).effects is {sorted(a.effects)}, the run attempted "
        f"{sorted(attempted)} (effects_used {r.effects_used})")


AUDIT_FIELDS = set(velaris.AuditResult.__slots__)
KNOWN_AUDIT_FIELDS = {
    "schema", "velaris_version", "ok", "problems", "effects", "functions",
    "proven_share", "safe_command", "warnings", "ffi_modules",
    "loops_unshown", "contract_coverage", "fs_paths", "net_hosts",
    "ffi_any", "counts", "prover", "secrets", "ffi_native", "confinement"}
# what moves with any effect (checked in detail below) ...
MOVES_WITH_ANY = {"effects", "safe_command", "functions"}
# ... and what moves with one effect in particular (check_metamorphic.py)
MOVES_WITH = {"io": set(), "clock": set(), "rand": set(),
              "env": {"secrets"}, "declassify": {"secrets"},
              # confinement (8.4) is derived from the budget: a write grant
              # changes what Windows holds, a host what any kernel can, and
              # a Python module widens the OS policy
              "fs": {"fs_paths", "counts", "confinement"},
              "net": {"net_hosts", "counts", "confinement"},
              "ffi": {"ffi_modules", "ffi_native", "warnings",
                      "confinement"}}


def audit_doc(src: str) -> dict[Any, Any]:
    a = audit(src)
    assert a.ok, f"the audit refused a program check accepted: {a.problems}"
    return cast(dict[Any, Any], a.as_dict())


def grants(safe_command: str) -> set[Any]:
    tail = safe_command.split(" --allow ", 1)[1]
    return set() if tail == "''" else set(tail.split(","))


def prop_one_effect(ex: Example) -> None:
    before, after = audit_doc(ex.before), audit_doc(ex.after)
    e = ex.effect
    small, big = (before, after) if ex.mode == "add" else (after, before)
    bad: list[Any] = []

    def expect(cond: Any, what: Any) -> None:
        if not cond:
            bad.append(what)

    verb = "gains" if ex.mode == "add" else "loses"
    expect(set(small["effects"]) <= set(big["effects"])
           and set(big["effects"]) - set(small["effects"]) == {e},
           f"effects {before['effects']} -> {after['effects']}: expected it "
           f"to {verb[:-1]} exactly {e}")
    moved = grants(big["safe_command"]) - grants(small["safe_command"])
    expect(grants(small["safe_command"]) <= grants(big["safe_command"])
           and len(moved) == 1 and next(iter(moved)).split(":")[0] == e,
           f"safe_command {before['safe_command']!r} -> "
           f"{after['safe_command']!r}: expected one {e} grant to move")
    fb, fa = before["functions"], after["functions"]
    expect([f["name"] for f in fb] == [f["name"] for f in fa],
           "functions: the list itself changed")
    # One thing besides the effect may move, and only one way: a promise
    # proven without the effect's call may be left to runtime checks with
    # it. A call the prover does not model (env, read_file, fetch, now, py,
    # declassify, ...) abandons the proof of the function it is in (SPEC.md
    # 9.4), and so does a let-bound call to a function that declares an
    # effect. That is a limit of the prover's precision, not of its
    # soundness; the 8.2 CHANGELOG names it.
    abandoned = False
    small_fns = {f["name"]: f for f in small["functions"]}
    big_fns = {f["name"]: f for f in big["functions"]}
    for x, y in zip(fb, fa):
        name = x["name"]
        for key in x:
            if key == "effects":
                continue
            if key == "status" and small_fns[name].get("status") == "proven" \
                    and big_fns[name].get("status") == "checked at runtime":
                abandoned = True
                continue
            expect(x[key] == y.get(key),
                   f"functions[{name}].{key}: {x[key]!r} -> "
                   f"{y.get(key)!r}")
        expect(set(x["effects"]) == set(ex.declared_before.get(name, ()))
               and set(y["effects"]) == set(ex.declared_after.get(name, ())),
               f"functions[{name}].effects {x['effects']} -> "
               f"{y['effects']}, declared "
               f"{sorted(ex.declared_before.get(name, ()))} -> "
               f"{sorted(ex.declared_after.get(name, ()))}")
    for key in sorted(AUDIT_FIELDS - MOVES_WITH_ANY - MOVES_WITH[e]):
        if key == "proven_share" and abandoned and small[key] is not None \
                and (big[key] is None or big[key] <= small[key]):
            continue                # it follows the status above, and only down
        expect(before[key] == after[key],
               f"{key} {before[key]!r} -> {after[key]!r}, which does not "
               f"follow from {e}")
    # a field that follows from the effect moves only as the effect says
    if e == "fs":
        sp, bp = small["fs_paths"], big["fs_paths"]
        expect(set(bp["read"]) - set(sp["read"]) == {DATA_PATH}
               and set(sp["read"]) <= set(bp["read"])
               and {k: v for k, v in sp.items() if k != "read"}
               == {k: v for k, v in bp.items() if k != "read"},
               f"fs_paths {before['fs_paths']} -> {after['fs_paths']}")
    if e == "net":
        host = f"127.0.0.1:{PORT}"
        expect(set(big["net_hosts"]["hosts"]) - set(small["net_hosts"]
                                                   ["hosts"]) == {host}
               and big["net_hosts"]["any"] == small["net_hosts"]["any"],
               f"net_hosts {before['net_hosts']} -> {after['net_hosts']}")
    if e in ("fs", "net"):
        other = "net" if e == "fs" else "fs"
        expect(small["counts"][e] == 0 and big["counts"][e] != 0
               and small["counts"][other] == big["counts"][other],
               f"counts {before['counts']} -> {after['counts']}")
    if e == "ffi":
        expect(set(big["ffi_modules"]) - set(small["ffi_modules"])
               == {"math"}, f"ffi_modules {before['ffi_modules']} -> "
                            f"{after['ffi_modules']}")
        expect("math" not in small["ffi_native"]
               and {k: v for k, v in big["ffi_native"].items()
                    if k != "math"} == small["ffi_native"],
               f"ffi_native {before['ffi_native']} -> "
               f"{after['ffi_native']}")
        extra = [w for w in big["warnings"] if w not in small["warnings"]]
        expect(all(w in big["warnings"] for w in small["warnings"])
               and all("Python" in w or "native code" in w for w in extra),
               f"warnings {before['warnings']} -> {after['warnings']}")
    if e in ("env", "declassify"):
        ss, bs = small["secrets"], big["secrets"]
        if e == "env":
            expect(set(bs["sources"]) - set(ss["sources"]) == {"env"}
                   and ss["declassifications"] == bs["declassifications"]
                   and ss["declassifies"] == bs["declassifies"],
                   f"secrets {before['secrets']} -> {after['secrets']}")
        else:
            extra = [d for d in bs["declassifications"]
                     if d not in ss["declassifications"]]
            expect(ss["sources"] == bs["sources"] and bs["declassifies"]
                   and all(d in bs["declassifications"]
                           for d in ss["declassifications"])
                   and extra and all(d["reason"].startswith("property ")
                                     for d in extra),
                   f"secrets {before['secrets']} -> {after['secrets']}")
    assert not bad, "the audit moved in more than one place:\n  " + \
        "\n  ".join(bad)


_CSV_CALL: list[Any] = []


def csv_call() -> Any:
    """stdlib/csv.vel's functions, loaded and checked once."""
    if not _CSV_CALL:
        funcs, records = velaris.load_program(str(HERE / "stdlib" / "csv.vel"))
        errors: list[Any] = []
        velaris.check_effects(funcs, errors)
        velaris.check_types(funcs, records, errors)
        assert not errors, f"stdlib/csv.vel does not check: {errors[0].code}"
        _CSV_CALL.append(velaris.build_runtime(funcs, {})["call"])
    return _CSV_CALL[0]


def csv_values() -> st.SearchStrategy[Any]:
    """One row of fields, each drawn from the characters RFC 4180 quoting is
    about - the comma, the double quote, CR and LF - and a few it is not."""
    return st.lists(st.text(alphabet='ab ,"\n\r\té ', max_size=8),
                    min_size=1, max_size=6)


def prop_csv_round_trip(values: Any) -> None:
    call = csv_call()
    line = call("line_of", [values], 1)
    back = call("fields", [line], 1)
    assert back == values, (f"line_of({values!r}) is {line!r}, and fields of "
                            f"that is {back!r}")
    rows = call("rows_of", [line + "\n" + line], 1)
    assert rows == [line, line], (f"rows_of of {line!r} twice, a line feed "
                                  f"between, is {rows!r}")


PROPERTIES = [
    (1, "parse(fmt(p)) == parse(p), up to locations", valid_sources,
     prop_parse_after_fmt),
    (2, "fmt(fmt(p)) == fmt(p)", valid_sources, prop_fmt_idempotent),
    (3, "check(p) twice gives the same answer", valid_sources,
     prop_check_deterministic),
    (4, "audit(p).effects == the effects a run attempts", effect_programs,
     prop_audit_says_what_runs),
    (5, "one effect added, or removed, moves the audit by exactly it",
     effect_edits, prop_one_effect),
    (6, "csv.vel: fields(line_of(values)) == values, and rows_of keeps a "
        "quoted line feed in its row (8.3)", csv_values, prop_csv_round_trip),
]


def ascii_text(s: str) -> str:
    return str(s).encode("ascii", "backslashreplace").decode("ascii")


def run_property(number: Any, title: Any,
                 strategy: Callable[[], st.SearchStrategy[Any]], body: Any,
                 examples: Any, base_seed: Any) -> bool:
    from hypothesis import Verbosity
    state: dict[str, Any] = {"calls": 0, "failed_at": None, "last": None}

    def test(example: Any) -> None:
        state["calls"] += 1
        state["last"] = example
        try:
            body(example)
        except BaseException:
            if state["failed_at"] is None:
                state["failed_at"] = state["calls"]
            raise

    test.__name__ = test.__qualname__ = f"property_{number}"
    wrapped = given(strategy())(test)
    wrapped = settings(max_examples=examples, deadline=None, database=None,
                       derandomize=False, report_multiple_bugs=False,
                       suppress_health_check=[HealthCheck.too_slow],
                       print_blob=False, verbosity=Verbosity.quiet,
                       phases=[Phase.generate, Phase.shrink])(wrapped)
    wrapped = hypothesis_seed(base_seed * 10 + number)(wrapped)
    t0 = time.monotonic()
    error = None
    try:
        wrapped()
    except Exception as exc:          # the shrunk failure, re-raised
        error = exc
    secs = time.monotonic() - t0
    if error is None:
        print(f"  ok    {number}. {title}: {state['calls']} examples, "
              f"{secs:.1f}s", flush=True)
        return True
    print(f"  FAIL  {number}. {title}: failed first at example "
          f"{state['failed_at']}, {state['calls']} run with shrinking, "
          f"{secs:.1f}s")
    if state["failed_at"] is not None and state["last"] is not None:
        print("  the shrunk counterexample:")
        print("\n".join("    | " + line for line in
                        ascii_text(repr(state["last"])).rstrip().split("\n")))
    else:
        print("  (the strategy itself failed: it made no program to test)")
    print("  what went wrong:")
    message = ascii_text(f"{type(error).__name__}: {error}")
    if len(message) > 6000:
        message = message[:6000] + " ..."
    print("\n".join("    " + line for line in message.split("\n")),
          flush=True)
    return False


def main(argv: Any = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--examples", type=int, default=None,
                    help="examples per property (default 25, --long 300)")
    ap.add_argument("--seed", type=int, default=82,
                    help="the fixed seed the draws come from")
    ap.add_argument("--long", action="store_true",
                    help="a few hundred examples each, for a local run")
    ap.add_argument("--only", default="",
                    help="comma-separated property numbers")
    ap.add_argument("--proof-timeout", type=float, default=1.0,
                    help="seconds per proof query (default 1; the "
                         "generated promises prove in well under 0.1s)")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    # Proofs stay on. The budget per query is shortened because a valid
    # program the generator does make - a loop with a written invariant
    # beside upper()/lower() - sends the prover through its whole budget
    # with nothing to prove, three seconds a query by default, and
    # property 5's shrinking meets that hundreds of times. The promises the
    # generator writes settle far inside one second, so what is proven
    # does not change; only an abandoned proof is abandoned sooner.
    velaris.set_proof_timeout(args.proof_timeout)
    examples = args.examples or (300 if args.long else 25)
    only = {int(x) for x in args.only.split(",") if x.strip()}
    stale = nodes_are_known()
    if stale:
        print(stale)
        return 1
    missing = KNOWN_AUDIT_FIELDS ^ AUDIT_FIELDS
    if missing:
        print(f"velaris.audit/1 fields changed: {sorted(missing)} - say in "
              f"check_properties.py which move with an effect")
        return 1
    print(f"property tests: {examples} examples each, seed {args.seed}, "
          f"prover {'on, ' + format(args.proof_timeout, 'g') + 's a query' if velaris.HAVE_Z3 else 'absent (no z3)'}, "
          f"Python {sys.version.split()[0]}")
    print("-" * 62)
    t0 = time.monotonic()
    results = []
    try:
        for number, title, strategy, body in PROPERTIES:
            if only and number not in only:
                continue
            results.append(run_property(number, title, strategy, body,
                                        examples, args.seed))
    finally:
        _SERVER.shutdown()
    print("-" * 62)
    print(f"{results.count(True)} held, {results.count(False)} failed, "
          f"{time.monotonic() - t0:.1f}s")
    return 0 if results and all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
