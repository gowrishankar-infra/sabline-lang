"""The checkers' corpus for the agreement gate (9.0, M2): type-level
mutations of every example and library, and a table of programs that reach
each refusal the mutations do not.

The gate's other corpora were written to parse, or to be refused while
parsing; most of what they hold is a program the type checker accepts, so
a gate made of them alone says little about the half of the checkers that
refuses. This is that half, made the way `agreement_edges.py` makes the
parser's: a table, not a pass done once by hand.

**The mutations.** Each operator changes one token of a program that
compiles - a number made text, a parameter made `Secret of` its type, a
`try` taken away, an operator swapped, a field renamed - at three fixed
places in each file: the first place it applies, the middle one and the
last. So every program here is one small, plausible mistake away from a
program that compiles, which is the shape of most programs a model writes,
and every one of them is the same on every machine on every run. The
tokens are found with the Python lexer's own pattern (`MASTER_RE`), so an
operator never changes the inside of a text literal or a comment unless
that is the token it is about.

**The edges.** What no mutation of a shipped program reaches: a record
defined twice, an amount of a currency nobody has, a generic function over
a `Secret` or a map, an `hmac_sha256` given the wrong key, a `declassify`
with an empty reason, a loop whose counter is bound again inside it, an
import that is not Sabline source. Each was found by measuring which lines
of `sabline/checker.py`, `effects.py`, `termination.py`, `loader.py` and
`wrappers.py` the rest of the gate never runs, and is named for the rule
it reaches.

**The trees.** A rule one file cannot reach - a library with a function
value imported under a name, a library importing another - is reached by
a program of several files, which the gate writes into a folder of its
own. An import root is a door's setting rather than a program's, and is
not here.
"""
from pathlib import Path
from typing import Any, Callable

from sabline.lexer import KEYWORDS, MASTER_RE

ROOT = Path(__file__).resolve().parent

# Where the programs to mutate come from. Each of these compiles as it is
# (or is refused for a reason of its own), so one change is one mistake.
SOURCES = ("examples", "stdlib")

# How many places each operator is applied at in one file: the first, the
# middle and the last of the places it can apply.
PLACES = 3

Token = tuple[str, str, int, int]          # kind, text, start, end


def tokens(source: str) -> list[Token]:
    """Every token of `source` that is not trivia, with where it is."""
    out: list[Token] = []
    pos = 0
    while pos < len(source):
        m = MASTER_RE.match(source, pos)
        if not m:
            pos += 1
            continue
        kind, text = m.lastgroup or "", m.group()
        if kind == "IDENT" and text in KEYWORDS:
            kind = "KEYWORD"
        if kind not in ("COMMENT", "NEWLINE", "SKIP"):
            out.append((kind, text, m.start(), m.end()))
        pos = m.end()
    return out


Edit = tuple[int, int, str]                # replace source[a:b] with text


def _after(toks: list[Token], i: int) -> str:
    return toks[i + 1][1] if i + 1 < len(toks) else ""


def _before(toks: list[Token], i: int) -> str:
    return toks[i - 1][1] if i > 0 else ""


TYPE_ROTATION = {"Int": "Text", "Text": "Bool", "Bool": "Int", "Float": "Int"}
OP_ROTATION = {"+": "-", "-": "+", "*": "/", "/": "%", "%": "*",
               "==": "<", "<": "==", ">": "!=", "!=": ">", "<=": ">=",
               ">=": "<=", "and": "or", "or": "and"}


def _num_to_text(toks: list[Token]) -> list[Edit]:
    return [(a, b, '"1"') for k, _, a, b in toks if k in ("NUMBER", "FLOAT")]


def _text_to_num(toks: list[Token]) -> list[Edit]:
    return [(a, b, "1") for i, (k, _, a, b) in enumerate(toks)
            if k == "STRING" and _before(toks, i) != "import"]


def _bool_to_num(toks: list[Token]) -> list[Edit]:
    return [(a, b, "0") for k, t, a, b in toks
            if k == "KEYWORD" and t in ("true", "false")]


def _drop_try(toks: list[Token]) -> list[Edit]:
    return [(a, b, "") for k, t, a, b in toks if k == "KEYWORD" and t == "try"]


def _add_try(toks: list[Token]) -> list[Edit]:
    """`try` before a call that is the value of a let or a return."""
    return [(a, a, "try ") for i, (k, _, a, _b) in enumerate(toks)
            if k == "IDENT" and _after(toks, i) == "("
            and _before(toks, i) in ("=", "return")]


def _drop_or_fail(toks: list[Token]) -> list[Edit]:
    return [(a, toks[i + 1][3], "") for i, (k, t, a, _b) in enumerate(toks)
            if t == "or" and _after(toks, i) == "fail"
            and i + 2 < len(toks) and toks[i + 2][1] in ("{", "uses", "requires", "ensures")]


def _drop_uses(toks: list[Token]) -> list[Edit]:
    """A whole `uses` clause, so a function's effects are undeclared."""
    out = []
    for i, (k, t, a, _b) in enumerate(toks):
        if k == "KEYWORD" and t == "uses":
            j = i + 1
            while j < len(toks) and (toks[j][0] == "IDENT" or toks[j][1] == ","):
                j += 1
            out.append((a, toks[j - 1][3], ""))
    return out


def _swap_type(toks: list[Token]) -> list[Edit]:
    """A type written after `:` or `->`, turned into another."""
    return [(a, b, TYPE_ROTATION[t]) for i, (k, t, a, b) in enumerate(toks)
            if k == "IDENT" and t in TYPE_ROTATION
            and _before(toks, i) in (":", "->", "of", "to")]


def _secret_param(toks: list[Token]) -> list[Edit]:
    """A parameter's type made a Secret of itself, so that what the body
    does with it meets the Secret rules."""
    return [(a, a, "Secret of ") for i, (k, t, a, _b) in enumerate(toks)
            if k == "IDENT" and _before(toks, i) == ":"
            and i >= 2 and toks[i - 2][0] == "IDENT"
            and t not in ("Secret",)]


def _swap_op(toks: list[Token]) -> list[Edit]:
    return [(a, b, f" {OP_ROTATION[t]} ") for k, t, a, b in toks
            if t in OP_ROTATION and k in ("OP", "KEYWORD")]


def _unknown_name(toks: list[Token]) -> list[Edit]:
    """A name read as a value, made a name nothing defines."""
    out = []
    for i, (k, t, a, b) in enumerate(toks):
        if k != "IDENT" or t[:1].isupper():
            continue
        if _before(toks, i) in ("fn", "let", ".", "record", "as", "import"):
            continue
        if _after(toks, i) in ("(", ":", "="):
            continue
        out.append((a, b, "nowhere"))
    return out


def _unknown_call(toks: list[Token]) -> list[Edit]:
    return [(a, b, "no_such_function") for i, (k, t, a, b) in enumerate(toks)
            if k == "IDENT" and _after(toks, i) == "("
            and _before(toks, i) not in ("fn", ".")]


def _extra_arg(toks: list[Token]) -> list[Edit]:
    """One more argument to a call, so its arity is wrong."""
    return [(b, b, "0, ") for i, (k, t, a, b) in enumerate(toks)
            if t == "(" and i > 0 and toks[i - 1][0] == "IDENT"
            and _before(toks, i - 1) != "fn" and _after(toks, i) != ")"]


def _money(toks: list[Token]) -> list[Edit]:
    """A number made an amount, so the Money rules meet it."""
    return [(a, b, 'money(1, "INR")') for k, _, a, b in toks if k == "NUMBER"]


def _field(toks: list[Token]) -> list[Edit]:
    return [(a, b, "no_field") for i, (k, _, a, b) in enumerate(toks)
            if k == "IDENT" and _before(toks, i) == "."
            and _after(toks, i) != "("]


def _empty_list(toks: list[Token]) -> list[Edit]:
    """A list literal's items taken away, so nothing says what it holds."""
    out = []
    for i, (k, t, a, _b) in enumerate(toks):
        if t != "[" or k != "OP":
            continue
        depth, j = 0, i
        while j < len(toks):
            if toks[j][1] == "[":
                depth += 1
            elif toks[j][1] == "]":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if j < len(toks) and j > i + 1:
            out.append((a, toks[j][3], "[]"))
    return out


OPERATORS: tuple[tuple[str, Callable[[list[Token]], list[Edit]]], ...] = (
    ("num-to-text", _num_to_text),
    ("text-to-num", _text_to_num),
    ("bool-to-num", _bool_to_num),
    ("drop-try", _drop_try),
    ("add-try", _add_try),
    ("drop-or-fail", _drop_or_fail),
    ("drop-uses", _drop_uses),
    ("swap-type", _swap_type),
    ("secret-param", _secret_param),
    ("swap-op", _swap_op),
    ("unknown-name", _unknown_name),
    ("unknown-call", _unknown_call),
    ("extra-arg", _extra_arg),
    ("money", _money),
    ("field", _field),
    ("empty-list", _empty_list),
)


def _places(edits: list[Edit]) -> list[Edit]:
    if not edits:
        return []
    picks = {0, len(edits) // 2, len(edits) - 1}
    return [edits[i] for i in sorted(picks)][:PLACES]


def mutations(source: str) -> list[tuple[str, int, str]]:
    """(operator, place, mutated source) for one program."""
    toks = tokens(source)
    out = []
    for name, operator in OPERATORS:
        for k, (a, b, text) in enumerate(_places(operator(toks))):
            out.append((name, k, source[:a] + text + source[b:]))
    return out


def _main(body: str, uses: str = "io") -> str:
    return "fn main() uses " + uses + " {\n" + body + "\n}\n"


def _fallible(body: str) -> str:
    """A function that may fail, around `body`, and a main that calls it."""
    return ("fn f() -> Int or fail {\n" + body + "\nreturn 1\n}\n"
            + _main("check f() { ok v { print(v) } fail e { print(e) } }"))


IO_ENV = "io, env"
IO_ENV_DECLASSIFY = "io, env, declassify"

# (name, source): a program for each refusal the mutations do not reach.
EDGES: tuple[tuple[str, str], ...] = (
    # ---- records ----
    ("record-twice", "record P { x: Int }\nrecord P { y: Int }\n" + _main("print(1)")),
    ("record-and-function", "record f { x: Int }\nfn f() -> Int { return 1 }\n" + _main("print(f())")),
    ("record-field-twice", "record P { x: Int x: Text }\n" + _main("print(1)")),
    ("record-field-unknown-type", "record P { x: Nope }\n" + _main("print(1)")),
    ("record-field-unknown-currency", "record P { m: Money of XYZ }\n" + _main("print(1)")),
    ("record-no-such-field", "record P { x: Int }\n" + _main("let p = P(y: 1)\nprint(p.x)")),
    ("record-field-given-twice", "record P { x: Int }\n" + _main("let p = P(x: 1, x: 2)\nprint(p.x)")),
    ("record-field-currency-clash", "record P { m: Money of INR }\n"
     + _main('let p = P(m: money(1, "USD"))\nprint(1)')),
    ("record-field-wrong-type", "record P { x: Int }\n" + _main('let p = P(x: "a")\nprint(1)')),
    ("record-missing-field", "record P { x: Int y: Int }\n" + _main("let p = P(x: 1)\nprint(1)")),
    ("field-of-a-number", _main("let x = 1\nprint(x.y)")),
    ("record-unknown-field-read", "record P { x: Int }\n" + _main("let p = P(x: 1)\nprint(p.z)")),
    ("record-holding-a-secret", "record S { k: Secret of Text }\n"
     + _main('print(S(k: env("K", "")))', IO_ENV)),
    # ---- types that are not types ----
    ("param-secret-money-xyz", "fn f(x: Secret of Money of XYZ) -> Int { return 1 }\n" + _main("print(1)")),
    ("param-list-money-xyz", "fn f(x: List of Money of XYZ) -> Int { return 1 }\n" + _main("print(1)")),
    ("param-map-money-xyz", "fn f(x: Map of Text to Money of XYZ) -> Int { return 1 }\n" + _main("print(1)")),
    ("param-fn-money-xyz", "fn f(x: fn(Money of XYZ) -> Int) -> Int { return 1 }\n" + _main("print(1)")),
    ("param-fn-returns-money-xyz", "fn f(x: fn(Int) -> Money of XYZ) -> Int { return 1 }\n" + _main("print(1)")),
    ("param-map-bool-keys", "fn f(m: Map of Bool to Int) -> Int { return 1 }\n" + _main("print(1)")),
    ("return-unknown-type", "fn f() -> Nope { return 1 }\n" + _main("print(1)")),
    ("return-unknown-currency", "fn f() -> Money of XYZ { return 1 }\n" + _main("print(1)")),
    ("let-unknown-type", _main("let x: Nope = 1\nprint(1)")),
    ("type-var-shadows", "fn f(x: Int) -> Int for any Int { return x }\n" + _main("print(f(1))")),
    ("currency-variable", "fn f(m: Money of C) -> Int for any C { return 1 }\n"
     + _main('print(f(money(1, "INR")))')),
    # ---- Secret ----
    ("secret-enters-recursion", "fn k() -> Secret of Text uses env { return k() }\n"
     + _main("print(k())", IO_ENV)),
    ("secret-enters-chain", 'fn a() -> Secret of Text uses env { return env("K", "") }\n'
     "fn b() -> Secret of Text uses env { return a() }\n" + _main("print(b())", IO_ENV)),
    ("declassify-what-holds-it", _main('let ks = [env("K", "")]\nprint(declassify(ks, "r"))', IO_ENV_DECLASSIFY)),
    ("declassify-empty-reason", _main('print(declassify(env("K", ""), "   "))', IO_ENV_DECLASSIFY)),
    ("declassify-reason-built", _main('let r = "x"\nprint(declassify(env("K", ""), r))', IO_ENV_DECLASSIFY)),
    ("declassify-arity", _main('print(declassify(env("K", "")))', IO_ENV_DECLASSIFY)),
    ("hmac-arity", _main('print(hmac_sha256(env("K", "")))', IO_ENV_DECLASSIFY)),
    ("hmac-key-not-secret", _main('print(hmac_sha256("k", "m"))', "io, declassify")),
    ("hmac-message-secret", _main('print(hmac_sha256(env("K", ""), env("M", "")))', IO_ENV_DECLASSIFY)),
    ("hmac-message-wrong-type", _main('print(hmac_sha256(env("K", ""), 1))', IO_ENV_DECLASSIFY)),
    ("hmac-chain", _main('print(hmac_sha256_chain(env("K", ""), ["a", "b"]))', IO_ENV_DECLASSIFY)),
    ("hmac-chain-wrong-type", _main('print(hmac_sha256_chain(env("K", ""), "a"))', IO_ENV_DECLASSIFY)),
    ("secret-list-compared", _main('let a = [env("K", "")]\nlet same = a == a\nprint(1)', IO_ENV)),
    ("secret-map-compared", _main('let a = {"k": env("K", "")}\nlet same = a == a\nprint(1)', IO_ENV)),
    ("secret-while", _main('let k = env("K", "")\nwhile k == "" { print(1) }', IO_ENV)),
    ("secret-bound-to-a-type-variable", "fn same(a: T, b: T) -> Bool for any T { return a == b }\n"
     + _main('print(same(env("K", ""), env("J", "")))', IO_ENV)),
    ("secret-of-a-type-variable", "fn pass(s: Secret of T) -> Secret of T for any T { return s }\n"
     + _main('let k = pass(env("K", ""))\nprint(1)', IO_ENV)),
    ("secret-captured", _main('let k = env("K", "")\nlet f = fn() -> Int { return length(k) }\nprint(f())', IO_ENV)),
    ("secret-length", _main('let k = env("K", "")\nlet n = length(k)\nprint(1)', IO_ENV)),
    ("secret-map-keys", _main('let m = {"a": env("K", "")}\nlet ks = keys(m)\nprint(length(ks))', IO_ENV)),
    # ---- generics ----
    ("generic-over-a-map", 'fn first_value(m: Map of Text to T) -> T or fail for any T { return try get(m, "a") }\n'
     + _main('check first_value({"a": 1}) { ok v { print(v) } fail e { print(e) } }')),
    ("generic-returning-a-map", 'fn wrap(x: T) -> Map of Text to T for any T { return {"a": x} }\n'
     + _main("print(length(wrap(1)))")),
    ("generic-currency-clash", "fn same(a: Money of C, b: Money of C) -> Int for any C { return 1 }\n"
     + _main('print(same(money(1, "INR"), money(1, "USD")))')),
    ("generic-failure-ignored", "fn first(xs: List of T) -> T or fail for any T { return try get(xs, 0) }\n"
     + _main("print(first([1]))")),
    ("generic-arity", "fn id(x: T) -> T for any T { return x }\n" + _main("print(id(1, 2))")),
    ("generic-as-a-value", "fn id(x: T) -> T for any T { return x }\n" + _main("let f = id\nprint(1)")),
    # ---- all_of and any_of with a predicate generic in its currency ----
    ("all-of-currency-generic", "fn pos(m: Money of C) -> Bool for any C { return units_of(m) > 0 }\n"
     + _main('print(all_of([money(1, "INR")], pos))')),
    ("all-of-two-parameters", "fn two(m: Money of C, n: Int) -> Bool for any C { return n > 0 }\n"
     + _main('print(all_of([money(1, "INR")], two))')),
    ("all-of-with-effects", "fn noisy(m: Money of C) -> Bool for any C uses io { print(1)\nreturn true }\n"
     + _main('print(all_of([money(1, "INR")], noisy))')),
    ("all-of-currency-clash", "fn usd(m: Money of USD) -> Bool for any C { return true }\n"
     + _main('print(all_of([money(1, "INR")], usd))')),
    ("all-of-generic-in-t", "fn p(x: T) -> Bool for any T { return true }\n"
     + _main('print(all_of([money(1, "INR")], p))')),
    ("all-of-secret-amount", "fn p(m: Secret of Money of C) -> Bool for any C { return true }\n"
     + _main('print(all_of([money(1, "INR")], p))')),
    ("all-of-list-of-amounts", "fn p(m: List of Money of C) -> Bool for any C { return true }\n"
     + _main('print(all_of([money(1, "INR")], p))')),
    ("all-of-map-of-amounts", "fn p(m: Map of Text to Money of C) -> Bool for any C { return true }\n"
     + _main('print(all_of([money(1, "INR")], p))')),
    ("all-of-function-of-amounts", "fn p(m: fn(Money of C) -> Int) -> Bool for any C { return true }\n"
     + _main('print(all_of([money(1, "INR")], p))')),
    ("any-of-arity", _main("print(any_of([1]))")),
    ("all-of-not-a-list", _main("print(all_of(1, 2))")),
    ("all-of-wrong-predicate", _main("print(all_of([1], 2))")),
    # ---- containers ----
    ("pop-not-a-list", _fallible("let x = try pop(5)")),
    ("set-at-wrong-type", _fallible('let x = try set_at([1], 0, "a")')),
    ("set-at-currency-clash", _fallible('let x = try set_at([money(1, "INR")], 0, money(1, "USD"))')),
    ("slice-text-positions", _fallible('let x = try slice([1], "a", 2)')),
    ("keys-of-a-list", _main("print(keys([1]))")),
    ("has-of-a-list", _main("print(has([1], 1))")),
    ("has-wrong-key", _main('print(has({"a": 1}, 1))')),
    ("put-currency-clash", _main('let m = put({"a": money(1, "INR")}, "b", money(1, "USD"))\nprint(1)')),
    ("put-wrong-value", _main('let m = put({"a": 1}, "b", "x")\nprint(1)')),
    ("get-or-of-a-list", _main("print(get_or([1], 0, 1))")),
    ("get-or-wrong-key", _main('print(get_or({"a": 1}, 1, 2))')),
    ("get-or-currency-clash", _main('let x = get_or({"a": money(1, "INR")}, "a", money(1, "USD"))\nprint(1)')),
    ("get-or-wrong-default", _main('print(get_or({"a": 1}, "a", "x"))')),
    ("get-map-wrong-key", _fallible('let x = try get({"a": 1}, 1)')),
    ("get-map-failure-ignored", _main('print(get({"a": 1}, "a"))')),
    ("push-onto-a-map", _main('print(length(push({"a": 1}, 1)))')),
    ("push-currency-clash", _main('let xs = push([money(1, "INR")], money(1, "USD"))\nprint(1)')),
    ("get-text-position", _main('print(get([1], "a"))')),
    ("length-of-a-number", _main("print(length(1))")),
    ("container-arity", _main("print(length(1, 2))")),
    # ---- literals ----
    ("map-bool-keys", _main("let m = {true: 1}\nprint(1)")),
    ("map-mixed-keys", _main('let m = {"a": 1, 2: 1}\nprint(1)')),
    ("map-currency-clash", _main('let m = {"a": money(1, "INR"), "b": money(1, "USD")}\nprint(1)')),
    ("map-mixed-values", _main('let m = {"a": 1, "b": "x"}\nprint(1)')),
    ("map-key-twice", _main('let m = {"a": 1, "a": 2}\nprint(1)')),
    ("map-number-key-twice", _main("let m = {1: 1, 1: 2}\nprint(1)")),
    ("list-currency-clash", _main('let xs = [money(1, "INR"), money(1, "USD")]\nprint(1)')),
    ("maps-in-maps", _main('let m = {"a": {"b": {"c": 1}}}\nprint(1)')),
    ("empty-map", _main("let m = {}\nprint(1)")),
    # ---- function values ----
    ("fn-value-arity", _main("let f = fn(x: Int) -> Int { return x }\nprint(f(1, 2))")),
    ("fn-value-currency-clash", _main('let f = fn(m: Money of INR) -> Int { return 1 }\nprint(f(money(1, "USD")))')),
    ("fn-value-wrong-type", _main('let f = fn(x: Int) -> Int { return x }\nprint(f("a"))')),
    ("fn-value-that-can-fail", 'fn g() -> Int or fail { fail "x" }\n' + _main("let h = g\nprint(1)")),
    ("fn-value-unknown-name", _main("let f = fn(x: Int) -> Int { return x + nowhere }\nprint(f(1))")),
    ("fn-value-captures", _main("let n = 2\nlet f = fn(x: Int) -> Int { return x + n }\nprint(f(1))")),
    # ---- calls and operators ----
    ("format-nothing", _main("print(format())")),
    ("format-not-text", _main("print(format(1))")),
    ("format-holes", _main('print(format("{} {}", 1))')),
    ("argument-returns-nothing", _main("print(print(1))")),
    ("argument-currency-clash", "fn f(m: Money of INR) -> Int { return 1 }\n" + _main('print(f(money(1, "USD")))')),
    ("arithmetic-on-nothing", _main("print(1 + print(2))")),
    ("and-on-a-number", _main("print(true and 1)")),
    ("not-on-a-number", _main("print(not 1)")),
    ("minus-on-text", _main('print(-"a")')),
    # ---- statements ----
    ("let-annotated", _main("let x: Int = 1\nprint(x)")),
    ("let-annotated-wrong", _main("let x: Text = 1\nprint(x)")),
    ("let-annotated-empty-map-as-list", _main("let xs: List of Int = {}\nprint(1)")),
    ("let-annotated-empty-list", _main("let xs: List of Int = []\nprint(length(xs))")),
    ("let-annotated-currency-clash", _main('let m: Money of INR = money(1, "USD")\nprint(1)')),
    ("let-annotated-secret", _main('let k: Secret of Text = env("K", "")\nprint(1)', IO_ENV)),
    ("let-nothing", _main("let x = print(1)")),
    ("return-nothing", "fn f() -> Int { return }\n" + _main("print(f())")),
    ("return-from-unit", "fn f() { return 1 }\n" + _main("f()")),
    ("return-currency-clash", 'fn f() -> Money of INR { return money(1, "USD") }\n' + _main("print(1)")),
    ("check-names-nothing", 'fn w() or fail { fail "x" }\n'
     + _main("check w() { ok v { print(1) } fail e { print(e) } }")),
    ("check-names-no-result", "fn w() -> Int or fail { return 1 }\n"
     + _main("check w() { ok { print(1) } fail e { print(e) } }")),
    ("check-cannot-fail", _main("check print(1) { ok { print(1) } fail e { print(e) } }")),
    ("while-not-bool", _main("while 1 { print(1) }")),
    ("invariant-not-bool", _main("let i = 0\nwhile i < 3 invariant 1 { i = i + 1 }")),
    ("ensures-not-bool", "fn f() -> Int ensures 1 { return 1 }\n" + _main("print(f())")),
    ("requires-not-bool", "fn f(x: Int) -> Int requires x { return x }\n" + _main("print(f(1))")),
    ("assign-currency-clash", _main('let m = money(1, "INR")\nm = money(1, "USD")\nprint(1)')),
    ("assign-unknown", _main("y = 1")),
    ("fail-not-text", "fn f() -> Int or fail { fail 1 }\n" + _main("print(1)")),
    ("fail-in-a-pure-function", 'fn f() -> Int { fail "x" }\n' + _main("print(1)")),
    ("try-in-a-pure-function", 'fn f() -> Int { return try to_int("1") }\n' + _main("print(1)")),
    ("try-on-what-cannot-fail", "fn f() -> Int or fail { return try length([1]) }\n" + _main("print(1)")),
    ("break", _main("while true { break }")),
    ("unknown-then-its-use", _main("let x = nowhere\nprint(x)")),
    # ---- Money ----
    ("money-times-money", _main('print(text_of(money(1, "INR") * money(1, "INR")))')),
    ("money-times-text", _main('print(text_of(money(1, "INR") * "x"))')),
    ("money-compared-across", _main('print(money(1, "INR") < money(1, "USD"))')),
    ("money-plus-a-number", _main('print(text_of(money(1, "INR") + 1))')),
    ("money-compared-to-a-number", _main('print(money(1, "INR") < 1)')),
    ("money-divided", _main('print(text_of(money(1, "INR") / 2))')),
    ("divided-by-money", _main('print(1 / money(1, "INR"))')),
    ("money-and-a-float", _main('print(text_of(money(1, "INR") + 1.5))')),
    ("text-and-money", _main('print("a" + money(1, "INR"))')),
    ("money-wrong-argument", _main('print(text_of(money("1", "INR")))')),
    ("units-of-a-number", _main("print(units_of(1))")),
    ("text-of-a-number", _main("print(text_of(1))")),
    ("units-of-a-list", _main('print(units_of([money(1, "INR")]))')),
    ("currency-not-written", _main('let c = "INR"\nprint(text_of(money(1, c)))')),
    ("currency-unknown", _main('print(text_of(money(1, "XYZ")))')),
    ("rounding-unknown", _main('print(text_of(percent_of(money(100, "INR"), 1, 2, "up")))')),
    ("divide-or-fail", 'fn f() -> Text or fail { return text_of(try divide_or_fail(money(100, "INR"), 3, "half_up")) }\n'
     + _main("check f() { ok t { print(t) } fail e { print(e) } }")),
    ("with-units", _main('print(text_of(with_units(money(1, "INR"), 5)))')),
    ("money-arity", _main("print(text_of(money(1)))")),
    ("parse-money", 'fn f() -> Text or fail { return text_of(try parse_money("1.00", "INR")) }\n'
     + _main("check f() { ok t { print(t) } fail e { print(e) } }")),
    # ---- the loader ----
    ("import-twice", 'import "std.vel"\nimport "std.vel"\n' + _main("print(1)")),
    ("function-twice", "fn a() -> Int { return 1 }\nfn a() -> Int { return 2 }\n" + _main("print(a())")),
    ("function-in-two-files", 'import "std.vel"\nfn sum_of(xs: List of Int) -> Int { return 0 }\n'
     + _main("print(sum_of([1]))")),
    ("record-in-two-files", 'import "http.vel"\nrecord Answer { x: Int }\n' + _main("print(1)")),
    ("newer-builtin-hidden-from-a-library", 'import "aws.vel" as aws\nfn sha256(x: Text) -> Text { return x }\n'
     + _main('print(sha256("a"))')),
    # ---- the effect checker ----
    ("promise-calls-a-value", "fn f(g: fn(Int) -> Int) -> Int requires g(1) > 0 { return 1 }\n" + _main("print(1)")),
    ("promise-uses-try", "fn f(x: Text) -> Int or fail requires (try to_int(x)) > 0 { return 1 }\n" + _main("print(1)")),
    ("promise-literals", "record P { x: Int }\n"
     'fn f(x: Int) -> Int requires length([x, 1]) > 0 and has({"a": x}, "a") and P(x: x).x >= 0 { return x }\n'
     + _main("print(f(1))")),
    ("promise-with-an-effect", "fn f(x: Int) -> Int requires now() > 0 { return x }\n" + _main("print(1)")),
    # ---- termination ----
    ("loop-negative-limit", _main("let i = 0\nwhile i > -10 { i = i - 1 }\nprint(i)")),
    ("loop-counter-bound-again", _main("let i = 0\nwhile i < 3 { let i = 5\nprint(i) }")),
    ("loop-counter-bound-by-check", _main('let i = 0\nwhile i < 3 { check to_int("1") { ok i { print(i) } fail e { print(e) } } }')),
    ("loop-counter-moved-by-an-inner-loop", _main("let i = 0\nlet j = 0\nwhile i < 10 { while j < 2 { i = i + 1\nj = j + 1 } }")),
    ("loop-path-that-stays", _main("let i = 0\nlet go = true\nwhile i < 10 { if go { i = i + 1 } }")),
)


# Programs of more than one file: the rules a single file cannot reach.
# Each is its files by name, the one the gate asks about first; the gate
# writes them into a folder of their own, so that each import finds its
# library beside it.
LIBRARY_WITH_A_FUNCTION_VALUE = (
    "fn positive(xs: List of Int) -> Bool {\n"
    "    return all_of(xs, fn(x: Int) -> Bool { return x > 0 })\n"
    "}\n")
LIBRARY_MAKING_FUNCTION_VALUES = (
    "fn adder(n: Int) -> fn(Int) -> Int {\n"
    "    return fn(x: Int) -> Int { return x + n }\n}\n"
    "fn any_pair(xss: List of List of Int) -> Bool {\n"
    "    return any_of(xss, fn(xs: List of Int) -> Bool {\n"
    "        return all_of(xs, fn(x: Int) -> Bool { return big(x) })\n    })\n}\n"
    "fn big(x: Int) -> Bool {\n    return x > 1\n}\n"
    "fn apply(f: fn(Int) -> Int, x: Int) -> Int\n"
    "    requires f(x) > 100\n{\n    return f(x)\n}\n")
LIBRARY_MAKING_PROMISES = (
    "fn half(x: Int) -> Int\n    requires x > 0\n{\n    return x / 2\n}\n"
    "fn negated(x: Int) -> Int\n    ensures result < 0\n{\n    return x\n}\n"
    "fn third(xs: List of Int) -> Int\n    requires get(xs, 2) > 0\n{\n"
    "    return get(xs, 2)\n}\n"
    "fn call_with(f: fn(Int) -> Int, x: Int) -> Int {\n    return f(x)\n}\n")
# A program that calls a library's promises, breaking the one `which` names.
# Each break ends the run, so each is a tree of its own.
PROMISES_BROKEN = (
    ("requires", "print({lib}half(4))\nprint({lib}half(0 - 4))"),
    ("ensures", "print({lib}negated(0 - 1))\nprint({lib}negated(1))"),
    ("requires-that-errs", "print({lib}third([1, 2, 3]))\nprint({lib}third([1]))"),
)
# the program's own function, with a promise, called back by the library:
# the promise is the program's, so its file is main.vel
PROMISE_CALLED_BACK = (
    "fn positive_only(x: Int) -> Int\n    requires x > 0\n{\n    return x\n}\n")
TREES: tuple[tuple[str, dict[str, str]], ...] = (
    # a library that makes a function value, imported under a name: the
    # loader renames the library's functions, the lifted one among them,
    # and - from 9.0 - the name the value refers to it by, so it compiles
    # as it does imported flat. Until 9.0 the type checker could not find
    # the lifted function under its new name, and refused the program with
    # E402 "unknown function value 'fn#1'", in both runtimes.
    ("library-function-value-under-a-name", {
        "main.vel": 'import "lib.vel" as lib\n' + _main("print(lib.positive([1, 2]))"),
        "lib.vel": LIBRARY_WITH_A_FUNCTION_VALUE}),
    ("library-function-value-flat", {
        "main.vel": 'import "lib.vel"\n' + _main("print(positive([1, 2]))"),
        "lib.vel": LIBRARY_WITH_A_FUNCTION_VALUE}),
    # the same, further: a value that carries names, one handed back to the
    # program and printed and called, values inside values calling the
    # library's own function by name, and a broken promise about one -
    # under a name and flat
    ("library-function-values-under-a-name", {
        "main.vel": 'import "lib.vel" as lib\n' + _main(
            "let f = lib.adder(2)\nprint(f)\nprint(f(3))\n"
            "print(lib.any_pair([[1, 2], [3, 4]]))\nprint(lib.any_pair([[1]]))\n"
            "print(lib.apply(f, 1))"),
        "lib.vel": LIBRARY_MAKING_FUNCTION_VALUES}),
    ("library-function-values-flat", {
        "main.vel": 'import "lib.vel"\n' + _main(
            "let f = adder(2)\nprint(f)\nprint(f(3))\n"
            "print(any_pair([[1, 2], [3, 4]]))\nprint(any_pair([[1]]))\n"
            "print(apply(f, 1))"),
        "lib.vel": LIBRARY_MAKING_FUNCTION_VALUES}),
    # a library under a name that imports one of its own, flat and named
    ("library-imports-a-library", {
        "main.vel": 'import "outer.vel" as outer\n' + _main("print(outer.twice_of(2))"),
        "outer.vel": 'import "inner.vel" as inner\n'
                     "fn twice_of(n: Int) -> Int {\n    return inner.double(n)\n}\n",
        "inner.vel": "fn double(n: Int) -> Int {\n    return n * 2\n}\n"}),
    # a library's loop, judged where it is written, and its refusal
    # reported against the library's file and line
    ("library-loop-and-refusal", {
        "main.vel": 'import "lib.vel" as lib\n' + _main('print(lib.count("a"))'),
        "lib.vel": "fn count(t: Text) -> Int {\n    let i = 0\n"
                   "    while i < length(t) {\n        i = i + 1\n    }\n"
                   '    return i + "x"\n}\n'}),
)
# A library's broken promise - and an error raised while its promise is
# checked - names the library's file, where the promise's line is: from
# 9.0, in both runtimes. Until then the caller's frame blamed it, and the
# run named the importer's file with the library's line. Flat and named;
# and the program's own promise, broken when the library calls it back,
# names the program's file, which until 9.0 the library's frame took.
TREES += tuple(
    (f"library-promise-broken-{which}-{how}", {
        "main.vel": (f'import "lib.vel"{alias}\n'
                     + _main(body.replace("{lib}", prefix))),
        "lib.vel": LIBRARY_MAKING_PROMISES})
    for which, body in PROMISES_BROKEN
    for how, alias, prefix in (("flat", "", ""), ("named", " as lib", "lib.")))
TREES += (
    ("library-calls-back-a-broken-promise", {
        "main.vel": ('import "lib.vel" as lib\n' + PROMISE_CALLED_BACK
                     + _main("print(lib.call_with(positive_only, 2))\n"
                             "print(lib.call_with(positive_only, 0 - 2))")),
        "lib.vel": LIBRARY_MAKING_PROMISES}),
)


def edges() -> list[tuple[str, Any]]:
    """The table above, the programs of several files - each a mapping of
    file name to bytes, the first the one asked about - and the one edge
    that has to name a real file: an import of something that is not
    Sabline source, which must say so without quoting what the file
    holds."""
    out: list[tuple[str, Any]] = [
        (f"check-edge/{name}", source.encode("utf-8")) for name, source in EDGES]
    out += [(f"check-tree/{name}", {path: text.encode("utf-8")
                                    for path, text in files.items()})
            for name, files in TREES]
    licence = (ROOT / "LICENSE").as_posix()
    out.append(("check-edge/import-of-what-is-not-sabline",
                ('import "' + licence + '"\n' + _main("print(1)")).encode("utf-8")))
    return out


def cases() -> list[tuple[str, Any]]:
    """Every mutation of every program in SOURCES, then every edge, named,
    as file bytes."""
    out: list[tuple[str, Any]] = []
    for where in SOURCES:
        for path in sorted((ROOT / where).rglob("*.vel")):
            try:
                source = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            named = path.relative_to(ROOT).as_posix()
            for name, k, mutated in mutations(source):
                out.append((f"mutation/{named}/{name}/{k}",
                            mutated.encode("utf-8")))
    return out + edges()
