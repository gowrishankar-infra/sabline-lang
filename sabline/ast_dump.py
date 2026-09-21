"""The canonical AST dump: one document both runtimes write for one file.

`sabline ast --json <file>` writes it from here; `sabline-rt ast <file>`
writes it from the Rust crate. `check_agreement.py` compares the two, byte
for byte, over every Sabline source this project has. rt/README.md states
the format; nothing else in this package reads it.

It is not a stable interface and is not in `tests/api/golden.json`. It is
a comparison surface, and STABILITY.md's "anything else in the package"
clause covers it.

Three things it has to be careful about, because each is a place where
two implementations would differ without ever being wrong:

* **A whole number is decimal text.** `Num(int(t.text))` is an
  arbitrary-precision Python integer, and a literal written in Arabic-Indic
  or Devanagari digits converts like any other, so the dump writes what
  `str(int(...))` gives and not the token's own characters.
* **A float is one written form**, the shortest decimal that reads back as
  the same double, as `d[.ddd]eE`. Neither language's default printing is
  the other's - CPython writes `1.0` and `1e+16`, Rust writes `1` and
  `10000000000000000` - so the dump uses a third form that both can write.
* **`effects` is sorted.** The parser holds them in a `set`, and a set has
  no order to compare.
"""
import json
import math
import sys
from typing import Any

from .errors import SablineError
from .lexer import lex
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
from .parser import Parser

# What `sabline ast --help` says. The command is not in `usage_lines`,
# because the dump is a comparison surface and not a feature; it answers
# for itself all the same, because a command nobody can ask about is worse
# than one nobody advertises (check_cli.py holds both).
USAGE = """usage: sabline ast --json <file.vel>
       sabline ast --json --list <paths-file>

The canonical AST dump: the one document both this package and sabline-rt
write for one program, which check_agreement.py compares byte for byte.
rt/README.md states the format. It is not a stable interface and nothing
else reads it.

  --json            write the document (the only form there is)
  --list FILE       one path per line; writes a framed stream, so that
                    comparing some thousands of files is one process

Exit 0 when every program parsed, 1 when one was refused with a code,
2 when the command line itself was wrong."""

# The format's version, carried in every document, so that a change to the
# format is never read as a difference between two parsers.
DUMP_VERSION = 1

# What `load_program` raises CPython's recursion limit to before it parses.
# An expression may nest 1,000 deep and a block 4,000 deep before E102, and
# every one of those is several Python frames. sabline-rt does the same
# thing with a thread of its own (sabline_rt::PARSE_STACK).
RECURSION_LIMIT = 20000


def canonical_float(value: float) -> str:
    """A float as `d[.ddd]eE`: the shortest decimal that reads back as the
    same double, normalised to one digit before the point.

    It is the form Rust's `{:e}` writes. A literal cannot be negative - the
    parser wraps a minus sign in `Neg` - and cannot be a NaN, but both are
    written rather than refused, because a dump that raised on a value it
    did not expect would be a dump that hid a difference.
    """
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "inf" if value > 0 else "-inf"
    sign = "-" if math.copysign(1.0, value) < 0 else ""
    # repr() gives the shortest decimal that reads back as the same double;
    # what is left to do is move the point to after the first digit.
    mantissa, _, exponent = repr(abs(value)).partition("e")
    whole, _, fraction = mantissa.partition(".")
    digits = whole + fraction
    # value is 0.<digits> x 10 ** point
    point = len(whole) + (int(exponent) if exponent else 0)
    stripped = digits.lstrip("0")
    point -= len(digits) - len(stripped)
    digits = stripped.rstrip("0")
    if not digits:
        return f"{sign}0e0"
    head, rest = digits[0], digits[1:]
    power = point - 1
    return f"{sign}{head}.{rest}e{power}" if rest else f"{sign}{head}e{power}"


def _texts(items: Any) -> list[Any]:
    return [str(x) for x in items]


def _pairs(items: Any) -> list[Any]:
    return [[str(a), str(b)] for a, b in items]


def _clauses(items: Any) -> list[Any]:
    return [[_expr(e), int(line)] for e, line in items]


def _body(items: Any) -> list[Any]:
    return [_stmt(s) for s in items]


def _expr(e: Any) -> Any:
    if isinstance(e, Num):
        return {"kind": "Num", "value": str(e.value)}
    if isinstance(e, FloatNum):
        return {"kind": "FloatNum", "value": canonical_float(e.value)}
    if isinstance(e, Neg):
        return {"kind": "Neg", "line": e.line, "value": _expr(e.value)}
    if isinstance(e, Str):
        return {"kind": "Str", "value": e.value}
    if isinstance(e, Bool):
        return {"kind": "Bool", "value": bool(e.value)}
    if isinstance(e, Closure):
        return {"kind": "Closure", "line": e.line, "name": e.name,
                "free": _texts(e.free)}
    if isinstance(e, Var):
        return {"kind": "Var", "line": e.line, "name": e.name}
    if isinstance(e, BinOp):
        return {"kind": "BinOp", "line": e.line, "op": e.op,
                "left": _expr(e.left), "right": _expr(e.right)}
    if isinstance(e, Call):
        return {"kind": "Call", "line": e.line, "name": e.name,
                "args": [_expr(a) for a in e.args]}
    if isinstance(e, Not):
        return {"kind": "Not", "line": e.line, "value": _expr(e.value)}
    if isinstance(e, RecordLit):
        return {"kind": "RecordLit", "line": e.line, "name": e.name,
                "fields": [[str(f), _expr(v)] for f, v in e.fields]}
    if isinstance(e, FieldGet):
        return {"kind": "FieldGet", "line": e.line, "field": e.field,
                "obj": _expr(e.obj)}
    if isinstance(e, ListLit):
        return {"kind": "ListLit", "line": e.line,
                "items": [_expr(i) for i in e.items]}
    if isinstance(e, MapLit):
        return {"kind": "MapLit", "line": e.line,
                "entries": [[_expr(k), _expr(v)] for k, v in e.entries]}
    if isinstance(e, TryExpr):
        return {"kind": "TryExpr", "line": e.line, "value": _expr(e.value)}
    raise SablineError("E000", f"the dump has no shape for {type(e).__name__}",
                       getattr(e, "line", 1))


def _stmt(s: Any) -> Any:
    if isinstance(s, Let):
        return {"kind": "Let", "line": s.line, "name": s.name,
                "ann": s.ann, "value": _expr(s.value)}
    if isinstance(s, Return):
        return {"kind": "Return", "line": s.line,
                "value": None if s.value is None else _expr(s.value)}
    if isinstance(s, If):
        return {"kind": "If", "line": s.line, "cond": _expr(s.cond),
                "then": _body(s.then), "other": _body(s.other)}
    if isinstance(s, While):
        return {"kind": "While", "line": s.line, "cond": _expr(s.cond),
                "body": _body(s.body), "invariants": _clauses(s.invariants)}
    if isinstance(s, Assign):
        return {"kind": "Assign", "line": s.line, "name": s.name,
                "value": _expr(s.value)}
    if isinstance(s, Block):
        return {"kind": "Block", "line": s.line, "stmts": _body(s.stmts)}
    if isinstance(s, ExprStmt):
        return {"kind": "ExprStmt", "line": s.line, "expr": _expr(s.expr)}
    if isinstance(s, FailStmt):
        return {"kind": "FailStmt", "line": s.line, "value": _expr(s.value)}
    if isinstance(s, Check):
        return {"kind": "Check", "line": s.line, "subject": _expr(s.subject),
                "ok_name": s.ok_name, "ok_body": _body(s.ok_body),
                "fail_name": s.fail_name, "fail_body": _body(s.fail_body)}
    raise SablineError("E000", f"the dump has no shape for {type(s).__name__}",
                       getattr(s, "line", 1))


def _function(f: Function) -> Any:
    return {
        "kind": "Function",
        "line": f.line,
        "name": f.name,
        "params": _pairs(f.params),
        "return_type": f.return_type,
        # a set, so the dump sorts it: there is no order to compare
        "effects": sorted(f.effects),
        "requires": _clauses(f.requires),
        "ensures": _clauses(f.ensures),
        "body": _body(f.body),
        "src_file": f.src_file,
        "can_fail": bool(f.can_fail),
        "type_vars": _texts(f.type_vars),
        "is_lambda": bool(f.is_lambda),
        "captures": _pairs(f.captures),
        # set on a lifted function value as a plain attribute rather than a
        # field, so that a node's fields, repr and equality stay as they
        # were; every reader asks for it with a default of the empty list
        "free_names": _texts(getattr(f, "free_names", [])),
    }


def _record(r: RecordDef) -> Any:
    return {"kind": "RecordDef", "line": r.line, "name": r.name,
            "fields": _pairs(r.fields), "src_file": r.src_file}


def _import(row: Any) -> Any:
    path, line, alias = row
    return {"path": path, "line": line, "alias": alias}


def program_document(funcs: Any, records: Any, imports: Any) -> Any:
    """The document for a file that parsed."""
    return {
        "dump": DUMP_VERSION,
        "ok": True,
        "program": {
            "funcs": [_function(f) for f in funcs],
            "records": [_record(r) for r in records],
            "imports": [_import(i) for i in imports],
        },
    }


def error_document(error: SablineError) -> Any:
    """The document for a file the lexer or the parser refused."""
    return {
        "dump": DUMP_VERSION,
        "ok": False,
        "error": {
            "code": error.code,
            "message": error.message,
            "line": error.line,
            "fixes": list(error.fixes),
        },
    }


def dump_source(source: str) -> Any:
    """The document for one program's text.

    `Parser.lambda_n` is a class attribute the parser never resets, so a
    generated `fn#N` or `for#N` would otherwise depend on how many function
    values this process had parsed before. It is set to zero here, so that
    the dump of one file is a function of that file and of nothing else.

    The recursion limit is raised here rather than by the caller, because
    the parser accepts a program 4,000 blocks deep and every one of those
    is several Python frames - `load_program` does the same thing before it
    parses, for the same reason. sabline-rt does it with a thread of its
    own (`sabline_rt::on_parse_stack`).
    """
    if sys.getrecursionlimit() < RECURSION_LIMIT:
        try:
            sys.setrecursionlimit(RECURSION_LIMIT)
        except Exception:
            pass
    Parser.lambda_n = 0
    try:
        funcs, records, imports = Parser(lex(source)).parse_program()
    except SablineError as refused:
        return error_document(refused)
    return program_document(funcs, records, imports)


def dump_file(path: str) -> Any:
    """The document for one file, read the way the loader reads a program.

    `open(path, encoding="utf-8")` is what `load_program` uses, and its
    defaults are load-bearing: strict UTF-8, universal newlines, and a
    byte-order mark left in place. The two refusals are the loader's, for
    the entry file, wording included - E512 says "cannot import" about a
    file nothing imported, because the entry goes through that branch.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
    except UnicodeDecodeError:
        return error_document(SablineError(
            "E512",
            f"cannot import '{path}': it is not UTF-8 text, so it is not "
            f"Sabline source", 1,
            fixes=["an import names a .vel file"]))
    except OSError:
        return error_document(SablineError(
            "E001", f"cannot find file '{path}'", 1,
            fixes=["check the file name spelling",
                   "make sure you are in the folder that contains it"]))
    return dump_source(source)


def canonical(document: Any) -> str:
    """The document as bytes both runtimes write: keys sorted, no
    whitespace, every character outside space to tilde escaped.

    What `json.dumps(document, sort_keys=True, separators=(",", ":"))`
    writes, written with a stack of its own rather than with the call
    stack, because the encoder in the standard library recurses once per
    level and the parser accepts a program 4,000 levels deep.

    **No indentation**, and that is a decision rather than a default. Two
    spaces a level makes a document O(depth squared): the dump of the
    deepest program the parser accepts - 40 KB of source, and a case the
    adversarial corpus holds on purpose - was 352 MB of mostly spaces, and
    the gate writes it twice on every leg of CI. Compact, the same document
    is 1 MB. Nothing reads the dump but `check_agreement.py`, which reports
    a difference as a path through the tree rather than by eye.
    """
    out: list[str] = []
    # "raw" is text already written; "value" is something still to write
    work: list[Any] = [("value", document)]
    while work:
        kind, value = work.pop()
        if kind == "raw":
            out.append(value)
            continue
        if isinstance(value, str):
            out.append(_STRING(value))
            continue
        if value is True:
            out.append("true")
            continue
        if value is False:
            out.append("false")
            continue
        if value is None:
            out.append("null")
            continue
        if isinstance(value, int):
            out.append(str(value))
            continue
        if isinstance(value, list):
            if not value:
                out.append("[]")
                continue
            tasks: list[Any] = [("raw", "[")]
            for i, item in enumerate(value):
                tasks.append(("value", item))
                tasks.append(("raw", "," if i + 1 < len(value) else "]"))
            work.extend(reversed(tasks))
            continue
        if isinstance(value, dict):
            if not value:
                out.append("{}")
                continue
            keys = sorted(value)
            tasks = [("raw", "{")]
            for i, key in enumerate(keys):
                tasks.append(("raw", _STRING(key) + ":"))
                tasks.append(("value", value[key]))
                tasks.append(("raw", "," if i + 1 < len(keys) else "}"))
            work.extend(reversed(tasks))
            continue
        raise SablineError(
            "E000", f"the dump has no shape for {type(value).__name__}", 1)
    return "".join(out)


_STRING = json.encoder.encode_basestring_ascii

# The header of the framed stream `--list` writes. Each record after it is
#
#     --- <bytes> <path>\n
#     <that many bytes of canonical document>\n
#
# A length rather than a separator, so that the record's bytes are the
# document's bytes and a reader never has to parse one to find the next.
# The gate compares those bytes; it reads a document only to say where two
# of them first differ, and a document 4,000 levels deep is deeper than a
# JSON reader's own recursion.
BATCH_HEADER = "sabline.ast-batch/1"


def _out(payload: bytes) -> None:
    r"""Write bytes to standard output.

    Not `print`, and not `sys.stdout.write`: on Windows a text stream turns
    every \n into \r\n, and the gate compares bytes. A document is ASCII by
    construction, so the encoding cannot differ either.
    """
    sys.stdout.flush()
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def _write(text: str) -> None:
    """Write one document and the newline after it."""
    _out(text.encode("ascii") + b"\n")


def ast_main(argv: Any) -> int:
    """`sabline ast --json <file>`, and `--list` for many at once.

    It is not in `usage_lines`: it exists for `check_agreement.py`, which
    compares some hundreds of files on every commit, and a process per file
    would make the gate the slowest thing in CI.
    """
    words = [a for a in argv if a != "--json"]
    if not words or words[0] in ("--help", "-h"):
        print(USAGE)
        return 0
    if words[:1] == ["--list"] and len(words) == 2:
        try:
            with open(words[1], encoding="utf-8") as fh:
                listed = fh.read()
        except OSError as e:
            print(f"sabline ast: cannot read the list '{words[1]}': {e}",
                  file=sys.stderr)
            return 2
        every = True
        _out(BATCH_HEADER.encode("ascii") + b"\n")
        for line in listed.splitlines():
            path = line.rstrip("\r")
            if not path:
                continue
            document = dump_file(path)
            every = every and bool(document.get("ok"))
            body = canonical(document).encode("ascii")
            _out(f"--- {len(body)} {path}\n".encode("utf-8"))
            _out(body + b"\n")
        return 0 if every else 1
    if len(words) == 1 and not words[0].startswith("-"):
        document = dump_file(words[0])
        _write(canonical(document))
        return 0 if document.get("ok") else 1
    print(USAGE, file=sys.stderr)
    return 2
