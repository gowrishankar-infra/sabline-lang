"""The adversarial corpus the agreement gate carries.

plan/9.0.md's standing adversarial pass, aimed at the parser and written
down as a table rather than done once by hand: deep nesting, huge
literals, invalid UTF-8, byte-order marks, CRLF, NUL, pathological Unicode
identifiers and extreme line lengths. Every one of them must be the same
coded error in both runtimes - never a panic, never a stack overflow,
never a hang - and `check_agreement.py` is what says so, on every push.

These are **bytes**, not text, because that is the only way to ask what a
byte-order mark, a lone carriage return or a sequence that is not UTF-8
does. The gate writes each one into a file and hands both runtimes the
path, which is the way a user's program arrives.

A case added here is a case both runtimes answer on every commit, so the
cost of keeping it is nothing and the cost of leaving one out is a hole.
"""
from typing import Any

# The caps `sabline/parser.py` holds, and the crate's copies of them. A
# case sits on each side of each one.
BLOCK_NEST_LIMIT = 4000
EXPR_NEST_LIMIT = 1000
EXPR_CHAIN_LIMIT = 1000
INT_MAX_STR_DIGITS = 4300

HELLO = 'fn main() uses io {\n    print("hi")\n}\n'


def _ifs(depth: int) -> str:
    return "fn main() {" + "if true {" * depth + "}" * depth + "}"


def _text(source: str) -> bytes:
    return source.encode("utf-8")


def cases() -> list[tuple[str, bytes]]:
    """Every adversarial input, named, as the bytes of a file."""
    out: list[tuple[str, bytes]] = []

    def case(name: str, payload: Any) -> None:
        out.append((f"edge/{name}",
                    payload if isinstance(payload, bytes) else _text(payload)))

    # --- what a file may begin or end with ---------------------------------
    case("empty", b"")
    case("only-a-newline", b"\n")
    case("only-spaces", b"   \t  \n\n  ")
    case("bom-then-program", b"\xef\xbb\xbf" + _text(HELLO))
    case("bom-alone", b"\xef\xbb\xbf")
    case("utf16-bom", b"\xff\xfe" + _text(HELLO))
    case("comment-with-no-newline", b"// the last line has no newline")
    case("program-with-no-final-newline", _text(HELLO.rstrip("\n")))

    # --- line endings -------------------------------------------------------
    case("crlf", _text(HELLO.replace("\n", "\r\n")))
    case("lone-cr", _text(HELLO.replace("\n", "\r")))
    case("mixed-cr-and-lf", _text(HELLO.replace("\n", "\r\n\r")))
    case("cr-inside-a-literal", b'fn main() uses io {\n print("a\rb")\n}\n')
    case("cr-at-the-end", _text(HELLO) + b"\r")

    # --- bytes that are not UTF-8 ------------------------------------------
    case("lone-ff", b'fn main() uses io {\n print("a\xffb")\n}\n')
    case("truncated-sequence", b'fn main() { let x = "\xe2\x82" }\n')
    case("overlong-encoding", b'fn main() { let x = "\xc0\xaf" }\n')
    case("surrogate-in-cesu8", b'fn main() { let x = "\xed\xa0\x80" }\n')
    case("continuation-byte-alone", b"\x80" + _text(HELLO))

    # --- NUL ----------------------------------------------------------------
    case("nul-between-statements", _text(HELLO) + b"\x00\n")
    case("nul-inside-a-literal", b'fn main() uses io {\n print("a\x00b")\n}\n')
    case("nul-first", b"\x00" + _text(HELLO))

    # --- whole numbers at the edge of what CPython converts -----------------
    for digits in (INT_MAX_STR_DIGITS - 1, INT_MAX_STR_DIGITS,
                   INT_MAX_STR_DIGITS + 1, INT_MAX_STR_DIGITS + 700):
        case(f"int-{digits}-digits", "fn main() { let x = " + "1" * digits + " }")
    case("int-leading-zeros",
         "fn main() { let x = " + "0" * 40 + "7 }")
    case("int-all-zeros-past-the-limit",
         "fn main() { let x = " + "0" * (INT_MAX_STR_DIGITS + 1) + " }")
    case("int-64-bit-edges",
         "fn main() { let a = 9223372036854775807 let b = 9223372036854775808 "
         "let c = -9223372036854775808 }")

    # --- floats -------------------------------------------------------------
    case("float-overflows-to-inf",
         "fn main() { let x = " + "9" * 400 + ".0 }")
    case("float-underflows-to-zero",
         "fn main() { let x = 0." + "0" * 400 + "1 }")
    case("float-many-digits",
         "fn main() { let x = 3." + "1415926535897932384626433832795" * 8 + " }")
    case("float-shortest-forms",
         "fn main() { let a = 1.0 let b = 0.1 let c = 100.0 let d = 0.00001 "
         "let e = 123456789012345678.0 let f = 0.0001 }")
    case("float-then-dot", "fn main() { let x = 1.2.3 }")
    case("number-then-dot", "fn main() { let x = 12. }")

    # --- the depth caps, on each side --------------------------------------
    case("blocks-at-the-cap", _ifs(BLOCK_NEST_LIMIT - 1))
    case("blocks-one-past-the-cap", _ifs(BLOCK_NEST_LIMIT))
    case("blocks-far-past-the-cap", _ifs(BLOCK_NEST_LIMIT + 2000))
    case("else-if-chain-past-the-cap",
         "fn main() { " + "if true { } else " * (BLOCK_NEST_LIMIT + 1)
         + "if true { } }")
    for n, label in ((EXPR_NEST_LIMIT - 1, "at-the-cap"),
                     (EXPR_NEST_LIMIT, "one-past-the-cap")):
        case(f"brackets-{label}",
             "fn main() { let x = " + "(" * n + "1" + ")" * n + " }")
        case(f"nots-{label}",
             "fn main() { let x = " + "not " * n + "true }")
        case(f"lists-{label}",
             "fn main() { let x = " + "[" * n + "]" * n + " }")
    for n, label in ((EXPR_CHAIN_LIMIT, "at-the-cap"),
                     (EXPR_CHAIN_LIMIT + 1, "one-past-the-cap")):
        case(f"plus-chain-{label}", "fn main() { let x = 1" + " + 1" * n + " }")
        case(f"or-chain-{label}",
             "fn main() { let x = true" + " or true" * n + " }")
        case(f"compare-chain-{label}", "fn main() { let x = 1" + " < 1" * n + " }")
    case("unclosed-blocks-past-the-cap",
         "fn main() {" + "if true {" * (BLOCK_NEST_LIMIT + 10))
    case("unclosed-brackets-past-the-cap",
         "fn main() { let x = " + "(" * (EXPR_NEST_LIMIT + 10))

    # --- extreme line lengths ----------------------------------------------
    case("one-line-of-a-hundred-thousand-characters",
         "fn main() uses io {" + " " * 100_000 + 'print("hi") }')
    case("a-literal-of-a-hundred-thousand-characters",
         'fn main() uses io { print("' + "a" * 100_000 + '") }')
    case("an-identifier-of-ten-thousand-characters",
         "fn main() { let " + "a" * 10_000 + " = 1 }")
    case("a-comment-of-a-hundred-thousand-characters",
         "//" + "x" * 100_000 + "\n" + HELLO)
    case("ten-thousand-statements",
         "fn main() {" + "let x = 1 " * 10_000 + "}")

    # --- Unicode ------------------------------------------------------------
    case("non-ascii-letter", "fn main() { let café = 1 }")
    case("arabic-indic-digits", "fn main() { let x = ١٢ }")
    case("devanagari-digits", "fn main() { let x = ०१२ }")
    case("fullwidth-digits", "fn main() { let x = １２ }")
    case("mixed-digit-scripts", "fn main() { let x = 1١० }")
    case("arabic-indic-float", "fn main() { let x = ١.٢ }")
    case("superscript-two", "fn main() { let x = ² }")
    case("combining-marks", "fn main() { let á = 1 }")
    case("zero-width-joiner", "fn main() { let a‍b = 1 }")
    case("right-to-left-override", "fn main() { let a‮b = 1 }")
    case("astral-character", "fn main() { let x = \U0001f600 }")
    case("line-separator", "fn main() { let x = 1   let y = 2 }")
    case("paragraph-separator", "fn main() { let x = 1   let y = 2 }")
    case("ideographic-space", "fn main() {　let x = 1 }")
    case("non-ascii-inside-a-literal",
         'fn main() uses io { print("café \U0001f600 中") }')
    case("non-ascii-in-a-comment", "// café \U0001f600\n" + HELLO)
    case("non-ascii-after-a-backslash", 'fn main() { let x = "a\\éb" }')

    # --- text literals ------------------------------------------------------
    case("unterminated-literal", 'fn main() { let x = "abc }')
    case("literal-with-a-newline-in-it", 'fn main() { let x = "ab\ncd" }')
    case("backslash-at-the-end", 'fn main() { let x = "ab\\" }')
    case("escaped-quote-then-end", 'fn main() { let x = "ab\\"')
    case("every-known-escape", 'fn main() { let x = "a\\nb\\tc\\"d\\\\e" }')
    case("unknown-escape", 'fn main() { let x = "a\\qb" }')
    case("escape-of-a-newline", 'fn main() { let x = "a\\\nb" }')
    case("empty-literal", 'fn main() { let x = "" }')
    case("quote-alone", 'fn main() { let x = " }')

    # --- shapes the grammar reaches rarely ----------------------------------
    case("bang-alone", "fn main() { let x = 1 ! 2 }")
    case("money-truncated", "fn f(x: Money of")
    case("secret-of-secret", "fn f(x: Secret of Secret of Text) { }")
    case("secret-of-secret-of-secret",
         "fn f(x: Secret of Secret of Secret of Text) { }")
    case("money-followed-by-a-field", "record R { Money: Int }")
    case("map-type-truncated", "fn f(x: Map of")
    case("list-type-truncated", "fn f(x: List of")
    case("record-with-commas", "record R { a: Int, b: Int }")
    case("record-write", "fn main() { p.x = 1 }")
    case("record-write-deep", "fn main() { p.x.y.z = 1 }")
    case("check-on-a-try", "fn main() { check try f() { ok v { } fail w { } } }")
    case("check-on-a-variable", "fn main() { check v { ok v { } fail w { } } }")
    case("try-on-a-variable", "fn main() { let x = try v }")
    case("lambda-with-no-result-type", "fn main() { let f = fn(x: Int) { } }")
    case("lambda-that-captures",
         "fn main() { let a = 1 let f = fn(x: Int) -> Int { return x + a } }")
    case("nested-lambdas",
         "fn main() { let a = 1 let f = fn(x: Int) -> Int { let g = "
         "fn(y: Int) -> Int { return y + a } return x } }")
    case("for-over-a-list", "fn main() { for item in xs { } }")
    case("for-over-a-range", "fn main() { for i in 0 to 10 { } }")
    case("for-with-no-in", "fn main() { for i of xs { } }")
    case("generic-with-no-any", "fn f() for T { }")
    case("import-with-an-escape", 'import "a\\tb.vel"\n' + HELLO)
    case("import-with-an-unknown-escape", 'import "a\\qb.vel"\n' + HELLO)
    case("import-with-an-alias", 'import "lib.vel" as lib\n' + HELLO)
    case("or-fail-at-the-end", "fn f() -> Int or fail")
    case("uses-at-the-end", "fn f()\n    uses")
    case("keyword-as-a-name", "fn main() { let ok = 1 let as = 2 }")
    case("qualified-call", "fn main() uses io { lib.thing(1) }")
    case("record-literal", "fn main() { let p = Point(x: 1, y: 2) }")
    case("empty-map-and-list", "fn main() { let a = {} let b = [] }")
    case("trailing-commas", "fn main() { let a = [1, 2,] let b = {\"k\": 1,} }")

    return out
