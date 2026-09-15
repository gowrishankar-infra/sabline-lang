"""velaris fmt: one canonical style.
"""
import sys

from .errors import VelarisError
from .lexer import Token, lex
from typing import Any


UNARY_BEFORE = {"(", "[", "{", ",", ":", "=", "==", "!=", "<", ">",
                "<=", ">=", "+", "-", "*", "/", "%"}
UNARY_KEYWORDS = {"return", "fail", "and", "or", "not", "requires",
                  "ensures", "invariant", "while", "if"}


def format_source(source: str) -> str:
    toks = lex(source, keep_trivia=True)
    lines: list[list[Token]] = []
    cur: list[Token] = []
    for t in toks:
        if t.kind == "NEWLINE":
            lines.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        lines.append(cur)

    def render(line_toks: Any) -> str:
        out = ""
        prev = None
        unary = False
        for t in line_toks:
            if t.kind == "COMMENT":
                body = t.text[2:].strip()
                comment = "// " + body if body else "//"
                out = (out.rstrip() + "  " + comment) if out.strip() \
                    else comment
                prev = t
                continue
            if prev is None or unary:
                space = False
            elif t.text in (")", "]", ",", ".", ":"):
                space = False
            elif prev.text in ("(", "[", "."):
                space = False
            elif t.text == "(" and prev.kind == "IDENT":
                space = False
            elif (t.text == "(" and prev.kind == "KEYWORD"
                    and prev.text == "fn"):
                space = False              # lambda value: fn(x: Int)
            else:
                space = True          # includes symmetric { x } spacing
            unary = (t.text == "-" and (
                prev is None or prev.text in UNARY_BEFORE
                or prev.kind == "ARROW"
                or (prev.kind == "KEYWORD" and prev.text in UNARY_KEYWORDS)))
            out += (" " if space else "") + t.text
            prev = t
        return out

    depth = 0
    out_lines: list[str] = []
    blank = False
    for line_toks in lines:
        if not line_toks:
            if out_lines and not blank:
                out_lines.append("")
            blank = True
            continue
        blank = False
        lead = 0
        while lead < len(line_toks) and line_toks[lead].text == "}":
            lead += 1
        d = max(depth - lead, 0)
        # a contract sits between the signature and the body, where no
        # brace has opened yet - indent it under the signature it belongs
        # to rather than flattening it to the margin
        if line_toks[0].text in ("requires", "ensures", "invariant"):
            d += 1
        text = render(line_toks)
        out_lines.append("    " * d + text if text else "")
        for t in line_toks:
            if t.text == "{":
                depth += 1
            elif t.text == "}":
                depth = max(depth - 1, 0)
    while out_lines and out_lines[-1] == "":
        out_lines.pop()
    return "\n".join(out_lines) + "\n"


def fmt_main(argv: list[str]) -> int:
    files = [a for a in argv if not a.startswith("--")]
    if not files:
        print("usage: velaris fmt <file.vel> [--stdout | --check]",
              file=sys.stderr)
        return 1
    status = 0
    for path in files:
        try:
            source = open(path, encoding="utf-8").read()
            formatted = format_source(source)
        except (OSError, VelarisError) as e:
            msg = e.human(path) if isinstance(e, VelarisError) else str(e)
            print(msg, file=sys.stderr)
            status = 1
            continue
        if "--stdout" in argv:
            print(formatted, end="")
        elif "--check" in argv:
            if formatted != source:
                print(f"{path}: needs formatting")
                status = 1
            else:
                print(f"{path}: ok")
        elif formatted != source:
            open(path, "w", encoding="utf-8").write(formatted)
            print(f"formatted {path}")
        else:
            print(f"{path}: already formatted")
    return status
