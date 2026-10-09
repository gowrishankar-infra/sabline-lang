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
    ("function-values-carry-names", "fn apply(f: fn(Int) -> Int, x: Int) -> Int {\n"
     "    return f(x)\n}\n" + _main('''
let k = 10
print(apply(fn(x: Int) -> Int { return x + k }, 1))
print(all_of([1, 2, 3], fn(n: Int) -> Bool { return n > k - 10 }))
let none: List of Int = []
print(any_of(none, fn(n: Int) -> Bool { return n > 0 }))
''')),
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
