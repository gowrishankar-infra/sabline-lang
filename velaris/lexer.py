"""Stage 1, the lexer: source text into tokens.
"""
import re
from dataclasses import dataclass

from .errors import VelarisError
from typing import Any, cast

# ---------------------------------------------------------------------------
# 1. LEXER — turn raw text into a list of tokens
# ---------------------------------------------------------------------------


KEYWORDS = {"fn", "let", "return", "if", "else", "uses", "true", "false", "while", "requires", "ensures", "and", "or", "not", "invariant", "record", "import", "fail", "check", "try", "for"}

TOKEN_SPEC = [
    ("COMMENT", r"//[^\n]*"),
    ("NEWLINE", r"\n"),
    ("SKIP",    r"[ \t\r]+"),
    ("ARROW",   r"->"),
    ("FLOAT",   r"\d+\.\d+"),
    ("NUMBER",  r"\d+"),
    ("STRING",  r'"(?:\\.|[^"\\\n])*"'),
    ("IDENT",   r"[A-Za-z_][A-Za-z0-9_]*"),
    ("OP",      r"==|!=|<=|>=|[+\-*/%<>=(){},:\[\].]"),
]

MASTER_RE = re.compile("|".join(f"(?P<{n}>{p})" for n, p in TOKEN_SPEC))


@dataclass
class Token:
    kind: str          # NUMBER, STRING, IDENT, KEYWORD, OP, ARROW
    text: str
    line: int


def lex(source: str, keep_trivia: bool = False) -> list[Token]:
    tokens, line = [], 1
    pos = 0
    while pos < len(source):
        m = MASTER_RE.match(source, pos)
        if not m:
            raise VelarisError("E000", f"unexpected character {source[pos]!r}", line,
                              fixes=["remove or replace this character"])
        kind, text = m.lastgroup, m.group()
        pos = m.end()
        if kind == "NEWLINE":
            if keep_trivia:
                tokens.append(Token("NEWLINE", "", line))
            line += 1
        elif kind == "COMMENT":
            if keep_trivia:
                tokens.append(Token("COMMENT", text.rstrip(), line))
        elif kind == "SKIP":
            pass
        elif kind == "IDENT" and text in KEYWORDS:
            tokens.append(Token("KEYWORD", text, line))
        else:
            tokens.append(Token(cast(str, kind), text, line))
    tokens.append(Token("EOF", "", line))
    return tokens


def fmt_fn_type(param_types: list[Any], ret: str | None) -> str:
    s = "fn(" + ", ".join(param_types) + ")"
    if ret and ret != "Unit":
        s += f" -> {ret}"
    return s


def type_mentions(t: str, tv: str) -> bool:
    if t == tv:
        return True
    if t.startswith("Money of "):           # a currency variable
        return t[len("Money of "):] == tv
    if t.startswith("Secret of "):          # Secret of T, the way a
        return type_mentions(t[len("Secret of "):], tv)   # generic says
                                            # it holds a secret on purpose
    if t.startswith("List of "):
        return type_mentions(t[len("List of "):], tv)
    if t.startswith("Map of "):
        key, _, val = t[len("Map of "):].partition(" to ")
        return type_mentions(key, tv) or type_mentions(val, tv)
    sig = fn_sig_parts(t)
    if sig is not None:
        parts, ret = sig
        return any(type_mentions(p, tv) for p in parts) or \
            type_mentions(ret, tv)
    return False


def fn_sig_parts(t: str) -> tuple[list[str], str] | None:
    """Split 'fn(A, B) -> R' into ([A, B], R). None if not a fn type."""
    if not t.startswith("fn("):
        return None
    depth, i, start, parts = 0, 3, 3, []
    while i < len(t):
        c = t[i]
        if c == "(":
            depth += 1
        elif c == ")":
            if depth == 0:
                break
            depth -= 1
        elif c == "," and depth == 0:
            parts.append(t[start:i].strip())
            start = i + 1
        i += 1
    last = t[start:i].strip()
    if last:
        parts.append(last)
    rest = t[i + 1:]
    ret = rest[4:].strip() if rest.startswith(" -> ") else "Unit"
    return parts, ret


ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}


def unescape(raw: str, line: int) -> str:
    out, i = [], 0
    while i < len(raw):
        c = raw[i]
        if c == "\\":
            i += 1
            e = raw[i] if i < len(raw) else ""
            if e not in ESCAPES:
                raise VelarisError("E002",
                    f"unknown escape '\\{e}' in text", line,
                    fixes=['known escapes: \\n (newline), \\t (tab), '
                           '\\" (quote), \\\\ (backslash)'])
            out.append(ESCAPES[e])
        else:
            out.append(c)
        i += 1
    return "".join(out)
