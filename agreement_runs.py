"""The runs' corpus for the agreement gate (9.0, M3): programs written to be
run, each reaching a place where the interpreter does what CPython does
rather than what a program would guess.

The gate's other corpora run too - every program that compiles is run by
both runtimes - but they were written to compile, to be refused, or to hide
a defect from a tool, and a program written for any of those prints little
and reaches little of the builtins. This is the interpreter's half, made
the way agreement_edges.py makes the parser's: a table, not a pass done
once by hand.

**The texts.** plan/9.0.md puts the text builtins first in M3, against a
generated corpus of exactly the inputs where a Text as CPython holds it -
code points - and a text as Rust holds it - UTF-8 bytes - part: lone
surrogates, characters past the basic plane, combining marks with nothing
to combine with, and the letters whose case CPython maps to more than one
character or by context. TEXTS is that list. A program cannot write a lone
surrogate in its source, which is UTF-8, so each program reads its texts
out of a JSON document with `json_get`, which is where a running program
meets one. Two programs per text: one that passes it through every text
builtin and prints what each gives, and one that breaks a promise about a
list holding it, so that the message shows `repr()` of the text.

Every text is one whose case and whose printability are the same in every
CPython from 3.10 to 3.13 - Unicode 13 to 15.1 - because the gate runs on
those, and on one of them a character assigned since would be a difference
of CPython's with itself.

**The edges.** EDGES: the rest of the interpreter's behaviour that a
program can see and that is the reference's own - arithmetic at the edges
of 64 bits and of IEEE-754, how a float prints, the order of texts, lists
and amounts, a map's order and keys, a record's text, money's rounding and
parsing, every message the JSON reader gives, the encoders, `format`,
`exit_with`, the input, and every kind of value a broken promise's message
can name.
"""
import json
from typing import Any

# The texts, as Python holds them. Each is one whose upper, lower and
# printability CPython 3.10 to 3.13 agree on.
TEXTS = (
    "", "a", "Hello, World", "  padded\t", "a,b,,c", "{}{}", "it's",
    'say "hi"', "back\\slash",
    # Latin: one character that is two in upper case, a sign that is
    # Greek in upper case, a titlecase digraph, a ligature
    "straße", "µ", "ǅ", "ŉ", "ﬃ", "ÿ", "Æsir",
    # Greek: the capital sigma, at the end of a word and not, through an
    # apostrophe and a combining mark; a letter that is three in upper case
    "ΟΔΟΣ", "Σ", "ΑΣ ΑΣ", "Α'Σ", "ΑΣ'Α", "Σ\u0301", "ΑΣ\u0301", "ΐ", "ϐ",
    # Turkish: a capital I with a dot is two characters in lower case
    "İstanbul", "ı",
    # Armenian, Cyrillic, Georgian
    "և", "Ѐѐ", "ა",
    # combining marks, one with nothing to combine with
    "e\u0301", "\u0301", "a\u0308\u0301",
    # past the basic plane: an emoji, one with a modifier, a flag, a
    # Deseret capital (which has a lower case) and a letter with none
    "😀", "👍🏽", "\U0001F1EE\U0001F1F3", "𐐀", "𝔸",
    # lone surrogates, and a pair written as two escapes, which the JSON
    # reader joins into one character, and the same pair the wrong way round
    "\ud800", "a\udc00b", "\U0010FFFF", "\ud83d", "\udfff\ud800",
    # digits: Arabic-Indic, a superscript, white space CPython strips
    "١٢٣", "²", "\u3000 7 \u3000", "\x1c5\x1f", "-0", "+5", "4_2",
    "9223372036854775807", "9223372036854775808", "-9223372036854775808",
    "00000000000000000000001", "٠٠٠٠٠٠٠٠٠٠٠٠٠٠٠٠٠٠٠٠1",
    # the characters a log line escapes, and two that look like space
    "\x00\x07\x7f\x9f", "line\nbreak\rreturn", "\u2028\u2029", "\u0085",
    "\u200b", "\xa0",
    # what the decoders read. Not here: base64 with padding at the start
    # of a quad ("YWJj==", "="), which CPython 3.10 decodes and 3.12 and
    # 3.13 refuse - the reference differs from itself there
    "68656c6c6f", "aGVsbG8=", "YQ", "YQ=", "YWJj", "8J+YgA==", "gA==",
    "ZmY", "Zg==Zg==", "YW=Jj", "YQ===",
)


def lit(text: str) -> str:
    """A Sabline text literal that is `text`: its four escapes, and every
    other character as itself."""
    return '"' + (text.replace("\\", "\\\\").replace('"', '\\"')
                  .replace("\n", "\\n").replace("\t", "\\t")) + '"'


def _doc(texts: Any) -> str:
    """The texts as a JSON document a program reads them from, written in
    ASCII so that a lone surrogate is an escape."""
    return lit(json.dumps(list(texts)))


def _reader(texts: Any) -> str:
    return ("fn the(i: Int) -> Text or fail {\n"
            f"    return try json_get({_doc(texts)}, to_text(i))\n"
            "}\n")


def _through_everything(i: int) -> str:
    """A program that passes TEXTS[i] through every text builtin."""
    return _reader(TEXTS) + f"""
fn main() uses io {{
    check the({i}) {{
        ok t {{
            print(format("length {{}}", length(t)))
            if length(t) > 0 {{
                print(format("first code {{}}, last code {{}}", code_at(t, 0), code_at(t, length(t) - 1)))
            }}
            print(upper(t))
            print(lower(t))
            print(chars(t))
            print(split(t, ","))
            print(contains(t, "a"))
            print(contains(t, t))
            print(t < "m")
            print(t == upper(t))
            print(format("<{{}}>", t))
            print(t + "|" + to_text([t, t]))
            print(json_of([t]))
            print(json_of({{"k": t}}))
            print(sha256(t))
            print(hex_encode(t))
            print(base64_encode(t))
            print(url_encode(t))
            check to_int(t) {{
                ok n {{
                    print(format("to_int {{}}", n))
                }}
                fail why {{
                    print(why)
                }}
            }}
            check hex_decode(t) {{
                ok d {{
                    print(format("hex {{}}", d))
                }}
                fail why {{
                    print(why)
                }}
            }}
            check base64_decode(t) {{
                ok d {{
                    print(format("base64 {{}}", d))
                }}
                fail why {{
                    print(why)
                }}
            }}
            log(t)
        }}
        fail why {{
            print(why)
        }}
    }}
}}
"""


def _named_by_a_promise(i: int) -> str:
    """A program whose broken promise names a list holding TEXTS[i], so
    that its message writes `repr()` of the text."""
    return _reader(TEXTS) + f"""
fn short(xs: List of Text) -> Int
    requires length(xs) > 2
{{
    return 0
}}

fn main() uses io {{
    check the({i}) {{
        ok t {{
            print(short([t, upper(t)]))
        }}
        fail why {{
            print(why)
        }}
    }}
}}
"""


# Documents the JSON programs read, as literals. Here rather than inside
# the f-strings that use them: CPython 3.10 takes no backslash in an
# f-string's expression, and the gate runs there too.
JSON_DOC = lit('{"a": {"b": [1, 2.5, -0, 1e400, true, null, "x\\u00e9"]}, '
               '"n": "12", "a": 3}')
JSON_DEEP = lit('{"a": {"b": [1, 2.5, -0, 1e400, true, null, "x"]}}')
JSON_NUMBERS = lit('["12", " 7 ", "1_0", "1__0", "2.5", "nan", "-Infinity", '
                   '"1e5", "0x10", "\\u0661", 99999999999999999999, '
                   '12345678901234567890123]')

# The largest power of ten a double holds, written as a literal can be:
# Sabline has no exponent in a number.
HUGE = "1" + "0" * 308 + ".0"


def _main(body: str, uses: str = "io") -> str:
    lines = body.strip("\n").splitlines()
    return f"fn main() uses {uses} {{\n" + "".join(
        "    " + line + "\n" for line in lines) + "}\n"


def _each(*lines: str) -> str:
    return _main("\n".join(f"print({x})" for x in lines))


# twenty-one doublings of a one-byte text: 2 + 4 + ... + 2**21 = 4,194,302
# made, two short of run_dump.SIZE
_DOUBLED = 'let s = "x"\nlet i = 0\nwhile i < 21 {\n    s = s + s\n    i = i + 1\n}\n'


# A program per behaviour, named for it. Most print what they reach and end
# with status 0; the ones that end otherwise end there on purpose.
EDGES: tuple[tuple[str, str], ...] = (
    # ---- whole numbers --------------------------------------------------
    ("int-floor-division-and-remainder", _each(
        "7 / 2", "-7 / 2", "7 / -2", "-7 / -2", "7 % 3", "-7 % 3", "7 % -3",
        "-7 % -3", "0 % 5", "-9223372036854775807 / 2")),
    ("int-past-64-bits-adding", _each("9223372036854775807 + 1")),
    ("int-past-64-bits-subtracting", _each("-9223372036854775807 - 2")),
    ("int-past-64-bits-multiplying", _each("4294967296 * 4294967296")),
    ("int-smallest-divided-by-minus-one", _main(
        "let small = -9223372036854775807 - 1\nprint(small)\nprint(small / -1)")),
    ("int-smallest-negated", _main(
        "let small = -9223372036854775807 - 1\nprint(-small)")),
    ("int-literal-past-64-bits", _main(
        "let big = 99999999999999999999\nprint(big)\nprint(big - big)\n"
        "print(big % 7)\nprint(-7 % big)\nprint(big > 5)\nprint([big])\n"
        "print(big + 1)")),
    ("int-division-by-zero", _each("1 / 0")),
    ("int-remainder-by-zero", _each("1 % 0")),
    ("int-the-or-fail-family", _main('''
check div_or_fail(-7, 2) {
    ok q { print(q) }
    fail why { print(why) }
}
check mod_or_fail(-7, 0) {
    ok q { print(q) }
    fail why { print(why) }
}
check add_or_fail(9223372036854775807, 1) {
    ok q { print(q) }
    fail why { print(why) }
}
check sub_or_fail(-9223372036854775807, 5) {
    ok q { print(q) }
    fail why { print(why) }
}
check mul_or_fail(3037000500, 3037000500) {
    ok q { print(q) }
    fail why { print(why) }
}
''')),
    # ---- floats ---------------------------------------------------------
    ("float-printing", _each(
        "0.1 + 0.2", "1.0", "-0.0", "0.0 - 0.0", "10000000000000000.0",
        "1234567890123456.7", "0.0001", "0.00001",
        "1.5 * 10000000000000000000000.0",
        "2.0 / 3.0", "100.0 / 7.0", "to_float(9223372036854775807)",
        "to_float(-3)", "-7.5 / 2.0", "[1.5, 2.0]", "to_float(7) / 2.0",
        "0.1 * 3.0", "1.0 / 3.0 * 3.0")),
    ("float-infinity-and-nan", _main(
        f"let x = {HUGE} * 10.0\nprint(x)\nprint(-x)\nlet n = x - x\nprint(n)\n"
        "print(n == n)\nprint(n != n)\nprint(n < 1.0)\nprint([n] == [n])\n"
        f"print(x > {HUGE})")),
    ("float-rounding", _each(
        "round(0.5)", "round(1.5)", "round(2.5)", "round(-0.5)", "round(-1.5)",
        "round(2.675)", "round(9000000000000000000.0)")),
    ("float-rounding-past-64-bits", _each("round(10000000000000000000.0)")),
    ("float-rounding-infinity", _main(
        f"let x = {HUGE} * 10.0\nprint(round(x))")),
    ("float-division-by-zero", _each("1.0 / 0.0")),
    ("float-from-whole-rounds", _each(
        "to_float(9007199254740993)", "to_float(9007199254740993) == 9007199254740992.0",
        "round(to_float(9007199254740993))")),
    # ---- texts ------------------------------------------------------------
    ("text-order", _each(
        '"B" < "a"', '"ä" > "z"', '"" < "a"', '"ab" < "abc"', '"😀" > "\uffff"',
        '"a" == "a"', 'upper("ﬃ") == "FFI"')),
    ("text-joined-with-values", _each(
        '"n=" + 1', '1.5 + "x"', '"b=" + true', '"l=" + [1, 2]',
        '"m=" + {"a": 1}', '"" + ""')),
    ("text-split-by-empty", _each('split("abc", "")')),
    ("text-code-past-the-end", _each('code_at("abc", 3)')),
    ("text-code-before-the-start", _each('code_at("abc", -1)')),
    ("format-placeholders", _each(
        'format("{} and {}", 1, "two")', 'format("{}", ["a", "b"])',
        'format("{{}}", 5)', 'format("none")', 'format("{}{}", "", "")')),
    # a template the checker can count is refused before running (E406);
    # one it cannot is refused while running, with the same code
    ("format-too-few-values", _main('let template = "{} " + "{}"\nprint(format(template, 1))')),
    # ---- lists, maps, records -----------------------------------------
    ("list-equality", _each(
        '["a"] == ["a"]', "[1, 2] == [1, 2]", "[1, 2] == [2, 1]",
        "[[1], [2, 3]] == [[1], [2, 3]]", "push([1], 2)", "push(push([[1]], [2]), [3, 4])")),
    ("list-get-past-the-end", _each("get([1, 2], 2)")),
    ("list-get-before-the-start", _each("get([1, 2], -1)")),
    ("list-pop-slice-set", _main('''
check pop([1, 2, 3]) {
    ok xs { print(xs) }
    fail why { print(why) }
}
check pop([0]) {
    ok xs { print(xs) }
    fail why { print(why) }
}
check slice([1, 2, 3, 4], 1, 3) {
    ok xs { print(xs) }
    fail why { print(why) }
}
check slice([1, 2], 1, 5) {
    ok xs { print(xs) }
    fail why { print(why) }
}
check set_at([1, 2, 3], 1, 9) {
    ok xs { print(xs) }
    fail why { print(why) }
}
check set_at([1, 2, 3], 3, 9) {
    ok xs { print(xs) }
    fail why { print(why) }
}
''')),
    ("map-order-keys-and-misses", _main('''
let m = {"b": 1, "a": 2}
let m2 = put(m, "c", 3)
let m3 = put(m2, "b", 9)
print(m3)
print(keys(m3))
print(has(m3, "a"))
print(get_or(m3, "z", 0))
print(m == {"a": 2, "b": 1})
let counts = {1: "one", 2: "two"}
print(counts)
check get(m3, "zz") {
    ok v { print(v) }
    fail why { print(why) }
}
check get(counts, 7) {
    ok v { print(v) }
    fail why { print(why) }
}
''')),
    ("record-text-and-equality", "record Pt {\n    x: Int\n    y: Int\n}\n" + _main('''
let p = Pt(y: 2, x: 1)
print(p)
print(p == Pt(x: 1, y: 2))
print(p.x + p.y)
print([p, p])
print(json_of(p))
''')),
    # ---- money ------------------------------------------------------------
    ("money-text-and-arithmetic", _each(
        'money(1250, "INR")', 'money(-5, "INR")', 'money(1250, "JPY")',
        'money(1250, "KWD")', 'money(1, "INR") + money(2, "INR")',
        'money(7, "INR") * 3', '3 * money(7, "INR")',
        'money(1, "INR") < money(2, "INR")', 'units_of(money(150, "USD"))',
        'units_of([money(1, "INR"), money(2, "INR")])',
        'text_of(with_units(money(1, "EUR"), 999))',
        'json_of([money(150, "USD")])')),
    ("money-rounding", _each(
        'percent_of(money(250, "INR"), 1, 100, "half_up")',
        'percent_of(money(250, "INR"), 1, 100, "half_even")',
        'percent_of(money(350, "INR"), 1, 100, "half_even")',
        'percent_of(money(-250, "INR"), 1, 100, "half_up")',
        'percent_of(money(-250, "INR"), 1, 100, "down")',
        'percent_of(money(999, "INR"), 33, 100, "down")')),
    ("money-percent-of-zero", _each('percent_of(money(1, "INR"), 1, 0, "half_up")')),
    ("money-negated-past-64-bits", _main(
        'let m = money(-9223372036854775807 - 1, "INR")\nprint(m)\nprint(-m)')),
    ("money-added-past-64-bits", _main(
        'let m = money(9223372036854775807, "INR")\nprint(m + money(1, "INR"))')),
    ("money-parse-and-divide", _main('''
check parse_money("12.50", "INR") {
    ok m { print(m) }
    fail why { print(why) }
}
check parse_money(" INR 12.5 ", "INR") {
    ok m { print(m) }
    fail why { print(why) }
}
check parse_money("USD 1.00", "INR") {
    ok m { print(m) }
    fail why { print(why) }
}
check parse_money("1.234", "INR") {
    ok m { print(m) }
    fail why { print(why) }
}
check parse_money("1.5", "JPY") {
    ok m { print(m) }
    fail why { print(why) }
}
check parse_money("1,000", "INR") {
    ok m { print(m) }
    fail why { print(why) }
}
check parse_money("-0.05", "INR") {
    ok m { print(m) }
    fail why { print(why) }
}
check parse_money("99999999999999999999", "JPY") {
    ok m { print(m) }
    fail why { print(why) }
}
check divide_or_fail(money(100, "INR"), 3, "half_up") {
    ok m { print(m) }
    fail why { print(why) }
}
check divide_or_fail(money(100, "INR"), 0, "half_up") {
    ok m { print(m) }
    fail why { print(why) }
}
''')),
    # ---- JSON -------------------------------------------------------------
    ("json-reads-and-writes", _main(f'''
let doc = {JSON_DOC}
check json_get(doc, "a") {{
    ok v {{ print(v) }}
    fail why {{ print(why) }}
}}
check json_len(doc, "") {{
    ok v {{ print(v) }}
    fail why {{ print(why) }}
}}
check json_int(doc, "n") {{
    ok v {{ print(v) }}
    fail why {{ print(why) }}
}}
let deep = {JSON_DEEP}
check json_get(deep, "a.b[3]") {{
    ok v {{ print(v) }}
    fail why {{ print(why) }}
}}
check json_get(deep, "a.b[-1]") {{
    ok v {{ print(v) }}
    fail why {{ print(why) }}
}}
check json_get(deep, "a.b[9]") {{
    ok v {{ print(v) }}
    fail why {{ print(why) }}
}}
check json_get(deep, "a.b[x]") {{
    ok v {{ print(v) }}
    fail why {{ print(why) }}
}}
check json_get(deep, "a.c") {{
    ok v {{ print(v) }}
    fail why {{ print(why) }}
}}
check json_get(deep, "a.b.0.z") {{
    ok v {{ print(v) }}
    fail why {{ print(why) }}
}}
check json_get(deep, "a") {{
    ok v {{ print(v) }}
    fail why {{ print(why) }}
}}
check json_float(deep, "a.b[1]") {{
    ok v {{ print(v) }}
    fail why {{ print(why) }}
}}
check json_int(deep, "a.b[1]") {{
    ok v {{ print(v) }}
    fail why {{ print(why) }}
}}
check json_int(deep, "a.b[3]") {{
    ok v {{ print(v) }}
    fail why {{ print(why) }}
}}
check json_int(deep, "a.b[4]") {{
    ok v {{ print(v) }}
    fail why {{ print(why) }}
}}
check json_int(deep, "a.b[5]") {{
    ok v {{ print(v) }}
    fail why {{ print(why) }}
}}
check json_len(deep, "a.b[0]") {{
    ok v {{ print(v) }}
    fail why {{ print(why) }}
}}
print(json_has(deep, "a.b[6]"))
print(json_has(deep, "a.b[7]"))
''')),
    ("json-numbers-as-text", _main(f'''
let doc = {JSON_NUMBERS}
let i = 0
while i < 12 {{
    check json_int(doc, to_text(i)) {{
        ok v {{ print(v) }}
        fail why {{ print(why) }}
    }}
    check json_float(doc, to_text(i)) {{
        ok v {{ print(v) }}
        fail why {{ print(why) }}
    }}
    i = i + 1
}}
''')),
    ("json-what-it-refuses", _reader([
        "", " ", "[1 2]", '{"a" 1}', "{", "[", '"abc', '"a\\q"', '"\\u12"',
        '"\\ud800\\u12"', "1 2", "\n\n  x", '"a\x01"', "-", "[-]", "1.e5",
        "01", "nul", "\ufeff1", "{1: 2}", "[1, 2", "tru", "NaN", "-Infinity",
        "[[[]]]"]) + _main('''
let i = 0
while i < 25 {
    check the(i) {
        ok doc {
            check json_get(doc, "") {
                ok v { print(v) }
                fail why { print(why) }
            }
        }
        fail why { print(why) }
    }
    i = i + 1
}
''')),
    # ---- the run itself ----------------------------------------------------
    ("input-read-to-the-end", _main('''
let line = read_line()
while length(line) > 0 {
    print(format("read [{}]", line))
    line = read_line()
}
print(format("then [{}]", read_line()))
print(args())
''')),
    ("input-asked-past-the-end", _main('''
print(ask("first?"))
print(ask("second?"))
print(ask("third?"))
print(ask("fourth?"))
''')),
    ("exit-with-a-number", _main('print("before")\nexit_with(3)\nprint("after")')),
    ("exit-with-too-large", _main("exit_with(256)")),
    ("log-lines", _main('log("plain")\nlog("two\\nlines")\nlog(["a", "b"])\nlog(true)\nlog(1.5)')),
    ("recursion-too-deep", "fn down(n: Int) -> Int {\n    return down(n + 1)\n}\n"
     + _main("print(down(0))")),
    # programs that do not end and print on every turn, so that where the
    # step limit stops them - one call or loop turn either way - shows in
    # what they printed (check_gate.py's injection into the limit)
    ("never-ends-printing-each-turn", _main(
        "let i = 0\nwhile true {\n    i = i + 1\n    print(i)\n}")),
    ("never-ends-calling-each-turn",
     "fn tick(n: Int) -> Int uses io {\n    print(n)\n    return n + 1\n}\n"
     + _main("let i = 0\nwhile true {\n    i = tick(i)\n}")),
    ("main-with-a-parameter", "fn main(x: Int) uses io {\n    print(x)\n}\n"),
    # ---- the size limit (run_dump.SIZE, 4,194,304) ------------------------
    # programs that grow without end, each stopped where what it has made
    # passes the limit, and each printing on every turn so that where shows
    ("grows-a-text-forever", _main(
        'let s = "ab"\nwhile true {\n    s = s + s\n    print(length(s))\n}')),
    # a two-byte character, then a lone surrogate (three): bytes, not
    # characters, are what is counted, so each stops a doubling earlier
    ("grows-a-text-of-two-byte-characters-forever", _main(
        'let s = "\u00e9\u00e9"\nwhile true {\n    s = s + s\n    print(length(s))\n}')),
    ("grows-a-text-of-lone-surrogates-forever", _reader(["\ud800"]) + _main(
        'check the(0) {\n    ok s {\n        let t = s\n        while true {\n'
        '            t = t + t\n            print(length(t))\n        }\n    }\n'
        '    fail why {\n        print(why)\n    }\n}')),
    ("grows-a-list-by-push-forever", _main(
        "let xs = [1]\nwhile true {\n    xs = push(xs, 1)\n"
        "    if length(xs) % 500 == 0 {\n        print(length(xs))\n    }\n}")),
    ("grows-a-map-forever", _main(
        "let m = {0: 0}\nlet i = 0\nwhile true {\n    i = i + 1\n"
        "    m = put(m, i, i)\n    if i % 250 == 0 {\n        print(length(keys(m)))\n    }\n}")),
    ("grows-a-text-by-format-forever", _main(
        'let s = "x"\nwhile true {\n    s = format("{}{}", s, s)\n    print(length(s))\n}')),
    # the boundary itself: twenty-one doublings of "x" make 4,194,302, two
    # short of the limit. What comes after is exactly at it, or one past
    ("size-two-short-then-ends", _main(_DOUBLED + "print(1)")),
    ("size-exactly-at-the-limit-ends", _main(_DOUBLED + "let xs = [1, 2]\nexit_with(4)")),
    ("size-one-past-the-limit-stops", _main(_DOUBLED + "let xs = [1, 2, 3]\nexit_with(4)")),
    ("size-a-map-one-past-stops", _main(_DOUBLED + "let m = {1: 1, 2: 2, 3: 3}\nexit_with(4)")),
    # what print, log and ask write is made; the one past the limit is not
    # written
    ("size-print-writes-then-stops", _main(_DOUBLED + 'print("x")\nprint("yz")')),
    # with two bytes left: a two-byte character fits exactly and a
    # three-byte one does not - what is counted is UTF-8, not characters
    ("size-a-two-byte-character-counts-two", _main(_DOUBLED + 'print("\u00e9")\nprint("x")')),
    ("size-a-three-byte-character-counts-three", _main(_DOUBLED + 'print("\u20ac")\nexit_with(7)')),
    ("size-log-writes-then-stops", _main(_DOUBLED + 'log("x")\nlog("yz")')),
    ("size-ask-asks-then-stops", _main(_DOUBLED + 'print(ask(""))\nprint(ask("q"))')),
    # what a builtin hands back is not made: an item, a default, a text's own
    # text - and what it makes is
    ("size-a-value-handed-back-is-not-made", _main(
        _DOUBLED + 'let xs = [s]\nlet t = get(xs, 0)\nlet u = get_or({"a": s}, "b", s)\n'
        'let v = to_text(s)\nexit_with(5)')),
    ("size-what-a-builtin-makes-is", _main(
        _DOUBLED + 'let xs = split("a,b,c", ",")\nexit_with(5)')),
    ("size-a-literal-is-not-made", _main(
        _DOUBLED + 'let t = "a literal far longer than the two bytes left"\nlet n = 7\nexit_with(6)')),
    ("function-values-carry-names", "fn apply(f: fn(Int) -> Int, x: Int) -> Int {\n"
     "    return f(x)\n}\n" + _main('''
let k = 10
print(apply(fn(x: Int) -> Int { return x + k }, 1))
print(all_of([1, 2, 3], fn(n: Int) -> Bool { return n > k - 10 }))
let none: List of Int = []
print(any_of(none, fn(n: Int) -> Bool { return n > 0 }))
''')),
    # a function value prints as `fn` and its name - its own, or the lifted
    # `fn#N` - whether it carries names or not, everywhere a value is
    # written (9.0, M3: it printed the node's dataclass fields, or a Python
    # object's address, before)
    ("function-values-print-as-their-names",
     "record Holder {\n    f: fn(Int) -> Int\n}\n"
     "fn double(x: Int) -> Int {\n    return x * 2\n}\n" + _main('''
let n = 3
let g = fn(x: Int) -> Int { return x + n }
let plain = fn(x: Int) -> Int { return x }
print(double)
print(g)
print(plain)
print([double, g, plain])
print({ 1: double, 2: g })
print(Holder(f: g))
print("" + to_text(g))
print(format("{} and {}", g, double))
log(g)
''')),
    ("function-values-in-a-broken-promise",
     "record Holder {\n    f: fn(Int) -> Int\n}\n"
     "fn double(x: Int) -> Int {\n    return x * 2\n}\n"
     "fn pick(fs: List of fn(Int) -> Int, h: Holder, f: fn(Int) -> Int) -> Int\n"
     "    requires length(fs) > 5 and length(to_text(h)) > 0 and f(1) > 100\n{\n    return 1\n}\n"
     + _main('''
let n = 3
let g = fn(x: Int) -> Int { return x + n }
print(pick([double, g, fn(y: Int) -> Int { return y }], Holder(f: g), double))
''')),
    # a function value that calls the function that made it, through all_of:
    # the depth limit, in both and on every CPython (3.12's C recursion
    # limit stopped the reference's all() first, until 9.0)
    ("recursion-through-all-of-too-deep",
     "fn spin(xs: List of Int) -> Bool {\n"
     "    return all_of(xs, fn(x: Int) -> Bool { return spin([x]) })\n}\n"
     + _main("print(spin([1]))")),
    ("recursion-through-any-of-too-deep",
     "fn spin(xs: List of Int) -> Bool {\n"
     "    return any_of(xs, fn(x: Int) -> Bool { return spin([x]) })\n}\n"
     + _main("print(spin([1]))")),
    # ---- broken promises, naming each kind of value -----------------------
    ("promise-names-numbers", "fn f(a: Int, b: Float, c: Bool) -> Int\n"
     "    requires a > 100 or b > 100.0 or c\n{\n    return 0\n}\n"
     + _main("print(f(1, 2.5, false))")),
    ("promise-names-texts-and-lists", "fn f(t: Text, xs: List of Text, ys: List of Float) -> Int\n"
     "    requires length(t) + length(xs) + length(ys) > 100\n{\n    return 0\n}\n"
     + _main('print(f("it\'s", ["a", "b\\"c", "\\n"], [1.0, 0.1]))')),
    ("promise-names-maps-and-money", "fn f(m: Map of Text to Int, a: Money of INR, l: List of Money of INR) -> Int\n"
     "    requires length(keys(m)) > 100 and units_of(a) > 0 and length(l) > 0\n{\n    return 0\n}\n"
     + _main('print(f({"a": 1, "b": 2}, money(150, "INR"), [money(1, "INR")]))')),
    ("promise-names-records", "record Pt {\n    x: Int\n    y: Text\n}\n"
     "fn f(p: Pt) -> Int\n    requires p.x > 100\n{\n    return 0\n}\n"
     + _main('print(f(Pt(x: 1, y: "z")))')),
    ("promise-on-the-result", "fn f(x: Int) -> List of Int\n    ensures length(result) > x\n{\n"
     "    return [x]\n}\n" + _main("print(f(3))")),
    ("promise-keeps-a-secret", "fn f(key: Secret of Text) -> Int\n"
     "    requires length(key) > 100\n{\n    return 0\n}\n"
     + _main('print(f(env("HOME", "")))', uses="io, env")),
    ("invariant-names-values", _main('''
let i = 0
let seen = ["a"]
while i < 5
    invariant i < 3
{
    i = i + 1
    seen = push(seen, "b")
}
''')),
)


def cases() -> list[tuple[str, bytes]]:
    """Every program here, named, as file bytes."""
    out: list[tuple[str, bytes]] = []
    for i, text in enumerate(TEXTS):
        out.append((f"run-text/{i}/{ascii(text)}",
                    _through_everything(i).encode("utf-8")))
        out.append((f"run-text-repr/{i}/{ascii(text)}",
                    _named_by_a_promise(i).encode("utf-8")))
    out += [(f"run-edge/{name}", source.encode("utf-8"))
            for name, source in EDGES]
    return out


# ---- runs under their own budgets (9.0, M3, the second checkpoint) ---------
#
# Every program above runs under the budget `io`. These run under the budget
# each names, in a tree of files the gate makes afresh for each runtime - the
# fixture check_sandbox.py and sabline-spec's L2 cases name with {ROOT},
# {DATA}, {OUT} and {OUTSIDE}, and beside it a home directory, {HOME}, holding
# every credential location sabline/budget.py documents, which the gate makes
# `~` for both runtimes. They reach the work of each builtin a budget can
# grant short of the network, Python and a tool: a file read, written and
# looked for, under grants and counts and the read ceiling; the credential
# rule; the clock frozen and randomness seeded; the environment; declassify
# and the two HMACs.

# What every run here is given besides its budget: where `~` is, on each
# system's own variable, and one variable of the gate's own for env() to find.
GATE_VALUE = "a value the gate set"


def environ(values: dict[str, str]) -> dict[str, str]:
    """The variables both runtimes set for a run in the tree."""
    return {"HOME": values["{HOME}"], "USERPROFILE": values["{HOME}"],
            "SABLINE_GATE_VALUE": GATE_VALUE}


def tree(root: Any) -> dict[str, str]:
    """Make the fixture under `root` (a pathlib.Path that does not exist),
    and give back what each placeholder is. Paths are written with "/", as
    check_sandbox.py writes them. {DATA}/link.txt is a symbolic link to
    {OUTSIDE} where the system will make one; where it will not, the link is
    missing in both runtimes' tree alike."""
    data, out, home = root / "box" / "data", root / "box" / "out", root / "home"
    for d in (data / "sub", out, home / ".aws", home / ".ssh",
              home / ".config" / "gcloud", home / ".docker", home / ".kube"):
        d.mkdir(parents=True, exist_ok=True)
    files = {
        data / "a.txt": b"inside\n",
        root / "outside.txt": b"outside\n",
        data / "crlf.txt": b"one\r\ntwo\rthree\n",
        data / "bom.txt": b"\xef\xbb\xbfmarked",
        data / "empty.txt": b"",
        data / "latin1.txt": b"caf\xe9",
        data / "hundred.txt": b"x" * 100,
        data / "sub" / "deep.txt": b"deep",
        data / ".env": b"TOKEN=t\n",
        data / "server.pem": b"-----BEGIN-----\n",
        data / "signing.KEY": b"k",
        home / ".aws" / "credentials": b"[default]\n",
        home / ".ssh" / "id_ed25519": b"key",
        home / ".netrc": b"machine m\n",
        home / ".docker" / "config.json": b"{}",
        home / ".kube" / "config": b"kind: Config\n",
        home / ".config" / "gcloud" / "credentials.db": b"db",
    }
    for path, raw in files.items():
        path.write_bytes(raw)
    try:
        (data / "link.txt").symlink_to(root / "outside.txt")
    except (OSError, NotImplementedError):
        pass
    return {"{ROOT}": root.as_posix(), "{DATA}": data.as_posix(),
            "{OUT}": out.as_posix(), "{OUTSIDE}": (root / "outside.txt").as_posix(),
            "{HOME}": home.as_posix(), "{PORT_A}": "9", "{PORT_B}": "9"}


def _try(expr: str, shown: str = "t") -> str:
    """A check of `expr` that prints what it gave, or why it failed."""
    return (f"check {expr} {{\n    ok t {{\n        print({shown})\n    }}\n"
            f"    fail why {{\n        print(\"failed: \" + why)\n    }}\n}}")


def _reads(*paths: str) -> str:
    return "\n".join(_try(f'read_file("{p}")') for p in paths)


def _secret(*paths: str) -> str:
    return "\n".join(_try(f'read_file_secret("{p}")', '"a secret read"')
                     for p in paths)


# (name, source, what the run is given)
BUDGETED: tuple[tuple[str, str, dict[str, Any]], ...] = (
    # ---- a file read, and what is read ------------------------------------
    ("read-what-a-file-holds", _main(_reads(
        "{DATA}/a.txt", "box/data/a.txt", "{DATA}/crlf.txt", "{DATA}/bom.txt",
        "{DATA}/empty.txt", "{DATA}/sub/deep.txt", "{DATA}/sub/../a.txt",
        "{DATA}/missing.txt", "{DATA}/sub", "{DATA}"), uses="io, fs"),
     {"allow": "io,fs:read:{DATA}"}),
    ("read-lines-as-universal-newlines", _main(_try(
        'read_file("{DATA}/crlf.txt")', "split(t, \"\\n\")"), uses="io, fs"),
     {"allow": "io,fs:read:{DATA}"}),
    ("read-what-is-not-utf8", _main(_reads("{DATA}/latin1.txt"), uses="io, fs"),
     {"allow": "io,fs:read:{DATA}"}),
    ("read-outside-the-grant", _main(_reads(
        "{DATA}/a.txt", "{OUTSIDE}", "{DATA}/../../outside.txt",
        "{DATA}/link.txt"), uses="io, fs"),
     {"allow": "io,fs:read:{DATA}"}),
    ("read-under-a-write-grant", _main(_reads("{DATA}/a.txt"), uses="io, fs"),
     {"allow": "io,fs:write:{DATA}"}),
    ("read-under-plain-fs", _main(_reads("{OUTSIDE}", "box/data/a.txt"),
                                  uses="io, fs"), {"allow": "io,fs"}),
    ("read-the-ceiling", _main(_reads("{DATA}/a.txt", "{DATA}/hundred.txt"),
                               uses="io, fs"),
     {"allow": "io,fs:read:{DATA}", "max_read": 99}),
    ("read-the-ceiling-exactly", _main(_try(
        'read_file("{DATA}/hundred.txt")', "length(t)"), uses="io, fs"),
     {"allow": "io,fs:read:{DATA}", "max_read": 100}),
    ("read-fs-denied", _main(_reads("{DATA}/a.txt"), uses="io, fs"),
     {"allow": "io,fs:read:{DATA}", "deny": "fs"}),
    # ---- written, and looked for ------------------------------------------
    ("write-then-read-back", _main(
        'write_file("{OUT}/w.txt", "first\\nsecond")\n'
        'write_file("{OUT}/n.txt", 42)\n'
        'write_file("{OUT}/l.txt", [1, 2])\n'
        + _reads("{OUT}/w.txt", "{OUT}/n.txt", "{OUT}/l.txt")
        + '\nprint(file_exists("{OUT}/w.txt"))', uses="io, fs"),
     {"allow": "io,fs:write:{OUT},fs:read:{OUT}"}),
    ("write-over-what-is-there", _main(
        'write_file("{OUT}/o.txt", "long text")\nwrite_file("{OUT}/o.txt", "x")\n'
        + _reads("{OUT}/o.txt"), uses="io, fs"),
     {"allow": "io,fs:write:{OUT},fs:read:{OUT}"}),
    ("write-outside-the-grant", _main(
        'write_file("{OUT}/fine.txt", "x")\nprint("wrote one")\n'
        'write_file("{DATA}/new.txt", "x")\nprint("WROTE IT")', uses="io, fs"),
     {"allow": "io,fs:write:{OUT}"}),
    ("write-where-there-is-no-folder", _main(
        'write_file("{OUT}/no/such/folder.txt", "x")', uses="io, fs"),
     {"allow": "io,fs:write:{OUT}"}),
    ("write-a-folder", _main('write_file("{OUT}", "x")', uses="io, fs"),
     {"allow": "io,fs"}),
    ("exists-under-each-grant", _main(
        'print(file_exists("{DATA}/a.txt"))\nprint(file_exists("{DATA}/nope"))\n'
        'print(file_exists("{DATA}/sub"))\nprint(file_exists("{DATA}/link.txt"))\n'
        'print(file_exists("{OUTSIDE}"))', uses="io, fs"),
     {"allow": "io,fs:write:{DATA}"}),
    ("exists-outside", _main('print(file_exists("{OUTSIDE}"))', uses="io, fs"),
     {"allow": "io,fs:read:{DATA}"}),
    # ---- the count ----------------------------------------------------------
    ("count-of-two", _main(
        'print(file_exists("{DATA}/a.txt"))\nprint(file_exists("{DATA}/b.txt"))\n'
        'print("two")\nprint(file_exists("{DATA}/c.txt"))\nprint("CARRIED ON")',
        uses="io, fs"), {"allow": "io,fs:read:{DATA}@2"}),
    ("count-spent-by-a-failed-read", _main(
        _reads("{DATA}/missing.txt") + '\n' + _reads("{DATA}/a.txt"),
        uses="io, fs"), {"allow": "io,fs:read:{DATA}@1"}),
    ("count-of-none", _main(_reads("{DATA}/a.txt"), uses="io, fs"),
     {"allow": "io,fs:read:{DATA}@0"}),
    ("count-the-smallest-holds", _main(
        _reads("{DATA}/a.txt", "{OUT}/x.txt", "{DATA}/a.txt", "{DATA}/a.txt"),
        uses="io, fs"), {"allow": "io,fs:read:{DATA}@3,fs:read:{OUT}@9"}),
    ("count-past-twenty", _main(
        "let i = 0\nwhile i < 23 {\n    i = i + 1\n"
        '    print(file_exists("{DATA}/a.txt"))\n}', uses="io, fs"),
     {"allow": "io,fs:read:{DATA}@21"}),
    # ---- the credential rule ------------------------------------------------
    ("credential-plain-read", _main(_reads(
        "{HOME}/.aws/credentials"), uses="io, fs"), {"allow": "io,fs"}),
    ("credential-plain-read-of-a-pattern", _main(_reads(
        "{DATA}/server.pem"), uses="io, fs"), {"allow": "io,fs:read:{DATA}"}),
    # each documented location, read as a secret under a grant broad enough
    # to cover it and naming none of them: refused, one program each so that
    # each is reached
    *((f"credential-secret-read-broad/{where}", _main(_secret(where), uses="io, fs"),
       {"allow": "io,fs"})
      for where in ("{DATA}/.env", "{DATA}/server.pem", "{DATA}/signing.KEY",
                    "{HOME}/.aws/credentials", "{HOME}/.ssh/id_ed25519",
                    "{HOME}/.netrc", "{HOME}/.docker/config.json",
                    "{HOME}/.kube/config", "{HOME}/.config/gcloud/credentials.db",
                    "{HOME}/.config/other.txt")),
    ("credential-secret-read-named", _main(_secret(
        "{DATA}/.env", "{HOME}/.aws/credentials", "{HOME}/.netrc"),
        uses="io, fs"),
     {"allow": "io,fs:read:{DATA}/.env,fs:read:{HOME}/.aws,fs:read:{HOME}/.netrc"}),
    ("credential-secret-read-under-its-family", _main(_secret(
        "{HOME}/.aws/credentials", "{HOME}/.ssh/id_ed25519"), uses="io, fs"),
     {"allow": "io,fs:read:{HOME}/.aws"}),
    ("credential-looked-for", _main(
        'print(file_exists("{HOME}/.aws/credentials"))', uses="io, fs"),
     {"allow": "io,fs:read:{HOME}"}),
    ("credential-looked-for-named", _main(
        'print(file_exists("{HOME}/.aws/credentials"))', uses="io, fs"),
     {"allow": "io,fs:read:{HOME}/.aws"}),
    # ---- the clock, randomness, the environment ------------------------------
    ("clock-frozen", _main("print(now())\nprint(now() + 1)", uses="io, clock"),
     {"allow": "io,clock", "freeze_time": 1767225600}),
    ("random-seeded", _main(
        "print(random(6))\nprint(random(6))\nprint(random(1))\n"
        "print(random(1000000007))\nprint(random(9223372036854775807))\n"
        "print(random(4294967296))\nprint(random(4294967297))",
        uses="io, rand"), {"allow": "io,rand", "seed": 2026}),
    ("random-seeded-negative", _main(
        "let i = 0\nwhile i < 12 {\n    print(random(100))\n    i = i + 1\n}",
        uses="io, rand"), {"allow": "io,rand", "seed": -5}),
    ("random-seeded-zero", _main("print(random(10))\nprint(random(10))",
                                 uses="io, rand"),
     {"allow": "io,rand", "seed": 0}),
    ("random-needs-a-positive", _main("print(random(0))", uses="io, rand"),
     {"allow": "io,rand", "seed": 1}),
    ("random-needs-a-positive-unseeded", _main("print(random(-3))",
                                               uses="io, rand"),
     {"allow": "io,rand"}),
    ("env-read-and-declassified", _main(
        'print(declassify(env("SABLINE_GATE_VALUE", "unset"), "a test value"))\n'
        'print(declassify(env("sabline_gate_value", "unset"), "a test value"))\n'
        'print(declassify(env("SABLINE_NO_SUCH_VARIABLE", "the default"), "a default"))',
        uses="io, env, declassify"), {"allow": "io,env,declassify"}),
    ("env-without-declassify", _main(
        'let v = env("SABLINE_GATE_VALUE", "")\nprint(declassify(v, "x"))',
        uses="io, env, declassify"), {"allow": "io,env"}),
    ("hmac-of-a-secret-key", _main(
        'let k = env("SABLINE_GATE_VALUE", "")\n'
        'print(hmac_sha256(k, "message"))\n'
        'print(hmac_sha256(k, ""))\n'
        'print(hmac_sha256(k, "é and \U0001F600"))\n'
        'print(hmac_sha256_chain(k, ["20261009", "region", "service", "request"]))\n'
        'print(hmac_sha256_chain(k, ["one"]))',
        uses="io, env, declassify"), {"allow": "io,env,declassify"}),
    ("hmac-of-a-long-key", _main(
        'let k = env("SABLINE_NO_SUCH_VARIABLE", "' + "k" * 100 + '")\n'
        'print(hmac_sha256(k, "message"))',
        uses="io, env, declassify"), {"allow": "io,env,declassify"}),
    ("hmac-of-nothing", _main(
        'let k = env("SABLINE_GATE_VALUE", "")\nlet none: List of Text = []\n'
        'print(hmac_sha256_chain(k, none))', uses="io, env, declassify"),
     {"allow": "io,env,declassify"}),
    ("hmac-without-declassify", _main(
        'let k = env("SABLINE_GATE_VALUE", "")\nprint(hmac_sha256(k, "m"))',
        uses="io, env, declassify"), {"allow": "io,env"}),
    ("budget-of-nothing", _main('print("never")'), {"allow": ""}),
)
