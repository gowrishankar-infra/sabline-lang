"""The syntax tree the parser builds: one dataclass per shape.
"""
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# 2. AST — the tree shapes the parser produces
# ---------------------------------------------------------------------------


@dataclass
class Num:
    value: int
@dataclass
class FloatNum:
    value: float
@dataclass
class Neg:
    value: object
    line: int
@dataclass
class Str:
    value: str
@dataclass
class Bool:
    value: bool
@dataclass
class Closure:
    """A function value that may carry values from around it.

    The function itself was lifted to the top level; this node is what
    the surrounding code evaluates to, and it is where the captured
    values are read - once, at the moment the value is made.
    """
    name: str
    free: list[str]
    line: int


@dataclass
class Var:
    name: str
    line: int
@dataclass
class BinOp:
    op: str
    left: object
    right: object
    line: int
@dataclass
class Call:
    name: str
    args: list[Any]
    line: int
@dataclass
class Let:
    name: str
    value: object
    line: int
    ann: str | None = None             # optional 'let x: Type = ...'
@dataclass
class Return:
    value: object
    line: int
@dataclass
class If:
    cond: object
    then: list[Any]
    other: list[Any]
    line: int
@dataclass
class While:
    cond: object
    body: list[Any]
    line: int
    invariants: list[tuple[Any, int]] = field(default_factory=list)   # [(expr, line)]
@dataclass
class Assign:
    name: str
    value: object
    line: int
@dataclass
class Not:
    value: object
    line: int
@dataclass
class RecordLit:
    name: str
    fields: list[tuple[str, Any]]      # [(fname, expr)]
    line: int
@dataclass
class FieldGet:
    obj: object
    field: str
    line: int
@dataclass
class RecordDef:
    name: str
    fields: list[tuple[str, str]]      # [(fname, type)]
    line: int
    src_file: str = ""
@dataclass
class ListLit:
    items: list[Any]
    line: int
@dataclass
class MapLit:
    entries: list[tuple[Any, Any]]     # [(key_expr, val_expr)]
    line: int
@dataclass
class Block:
    stmts: list[Any]                   # a 'for' unrolled into while
    line: int
@dataclass
class ExprStmt:
    expr: object
    line: int
@dataclass
class FailStmt:
    value: object
    line: int
@dataclass
class TryExpr:
    value: Call                        # the parser makes one of a Call only
    line: int
@dataclass
class Check:
    subject: Call                      # the parser makes one of a Call only
    line: int
    ok_name: str | None = None
    ok_body: list[Any] = field(default_factory=list)
    fail_name: str = ""
    fail_body: list[Any] = field(default_factory=list)

@dataclass
class Function:
    name: str
    params: list[tuple[str, str]]      # (name, type)
    return_type: str | None
    effects: set[str]                  # declared with `uses`
    requires: list[tuple[Any, int]]    # [(expr, line)] promises about inputs
    ensures: list[tuple[Any, int]]     # [(expr, line)] promises about output
    body: list[Any]
    line: int
    src_file: str = ""
    can_fail: bool = False
    type_vars: list[str] = field(default_factory=list)
    is_lambda: bool = False
    captures: list[tuple[str, str]] = field(default_factory=list)   # [(name, type)]
