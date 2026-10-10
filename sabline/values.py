"""The values a running program holds that are not Python's own: amounts,
records, handles, and the signals that end a call.
"""
import re
from dataclasses import dataclass

from .errors import SablineError
from .nodes import Function
from .tables import CURRENCIES, INT_MAX, INT_MIN
from typing import Any


@dataclass(frozen=True, order=True, slots=True)
class MoneyValue:
    """An amount while running: minor units and a currency. Ordering and
    equality compare units within one currency, which is the only kind
    of comparison the type checker lets through."""
    units: int
    currency: str

    def _same(self, other: Any) -> None:
        if other.currency != self.currency:   # kept out before running;
            raise SablineError("E550",        # this is the second lock
                f"an amount in {self.currency} met one in "
                f"{other.currency}", 0)

    def __add__(self, other: Any) -> Any:
        if other.__class__ is not MoneyValue:
            return NotImplemented
        self._same(other)
        return MoneyValue(self.units + other.units, self.currency)

    def __sub__(self, other: Any) -> Any:
        if other.__class__ is not MoneyValue:
            return NotImplemented
        self._same(other)
        return MoneyValue(self.units - other.units, self.currency)

    def __mul__(self, other: Any) -> Any:
        if other.__class__ is not int:
            return NotImplemented
        return MoneyValue(self.units * other, self.currency)

    __rmul__ = __mul__

    def __neg__(self) -> Any:
        return MoneyValue(-self.units, self.currency)

    def __str__(self) -> str:
        return money_text(self)


def money_text(m: "MoneyValue") -> str:
    """INR 12.50, JPY 1250, KWD 1.250, INR -0.05: the code, then the
    amount with exactly as many digits after the point as the currency
    has minor units."""
    digits = CURRENCIES.get(m.currency, 0)
    sign = "-" if m.units < 0 else ""
    whole = abs(m.units)
    if digits == 0:
        return f"{m.currency} {sign}{whole}"
    major, minor = divmod(whole, 10 ** digits)
    return f"{m.currency} {sign}{major}.{minor:0{digits}d}"


# CPython's default sys.get_int_max_str_digits(), from 3.10.7 on
INT_MAX_STR_DIGITS = 4300


def whole_number(digits: str) -> int:
    """int(digits) for a run of ASCII digits, with or without one leading
    minus: what a budget's count and port and a JSON document's whole
    number are read with. CPython refuses more than 4,300 digits, leading
    zeros counted, and words the refusal by version - 3.10 "(4300)", 3.12
    and later "(4300 digits)" - so this refuses first, in 3.12's words, on
    every CPython (9.0, M3), as sabline-rt does."""
    n = len(digits) - (digits[:1] == "-")
    if n > INT_MAX_STR_DIGITS:
        raise ValueError(
            f"Exceeds the limit ({INT_MAX_STR_DIGITS} digits) for integer "
            f"string conversion: value has {n} digits; use "
            f"sys.set_int_max_str_digits() to increase the limit")
    return int(digits)


# CPython 3.13's two messages for a comma before a closing bracket, and
# what 3.10 to 3.12 say there - one place later, at the bracket
_TRAILING_COMMA = {
    "Illegal trailing comma before end of array": "Expecting value",
    "Illegal trailing comma before end of object":
        "Expecting property name enclosed in double quotes",
}


def read_json(text: str) -> Any:
    """json.loads(text), answering as CPython 3.12 does on every CPython
    (9.0, M3), so that a program reading a document is told one thing
    whichever Python runs it, and sabline-rt the same: a whole number is
    read by whole_number - only a text longer than its limit can hold one
    past it, so a shorter one keeps CPython's own fast path - and 3.13's
    trailing-comma message is given in 3.12's words, at 3.12's place."""
    import json
    try:
        if len(text) > INT_MAX_STR_DIGITS:
            return json.loads(text, parse_int=whole_number)
        return json.loads(text)
    except json.JSONDecodeError as e:
        said = _TRAILING_COMMA.get(e.msg)
        if said is None:
            raise
        at = e.pos + 1                 # past the comma and the white space
        while at < len(text) and text[at] in " \t\n\r":
            at += 1
        raise json.JSONDecodeError(said, e.doc, at) from None


_MONEY_TEXT = re.compile(r"(?:([A-Z]{3}) *)?(-)?([0-9]+)(?:\.([0-9]+))?")


def parse_money_text(text: str, currency: str) -> "MoneyValue":
    """The amount a text names, in `currency`, or a FailSignal saying
    why it names none. Takes what money_text writes, and the same
    without the code or with fewer digits after the point: 12.50, 12.5,
    12, -3.05, INR 12.50. Refuses more digits than the currency has
    (that would round), separators, signs other than a leading minus,
    and an amount too big for 64 bits."""
    t = str(text).strip(" \t\r\n")
    m = _MONEY_TEXT.fullmatch(t)
    if not m:
        raise FailSignal(f"'{text}' is not an amount like 12.50")
    code, minus, whole, frac = m.groups()
    if code is not None and code != currency:
        raise FailSignal(f"'{text}' is in {code}, not {currency}")
    digits = CURRENCIES[currency]
    if frac is not None and digits == 0:
        raise FailSignal(f"'{text}' has digits after the point, and "
                         f"{currency} has no minor unit")
    if frac is not None and len(frac) > digits:
        raise FailSignal(f"'{text}' has {len(frac)} digits after the "
                         f"point, and {currency} has {digits}")
    whole = whole.lstrip("0") or "0"
    if len(whole) > 19:                        # before int(): 10**4300
        raise FailSignal(f"'{text}' is too big to hold")   # digits of
    units = int(whole) * 10 ** digits + int((frac or "").ljust(digits, "0")
                                            or "0")      # input is not
    if minus:                                             # a number
        units = -units
    if not INT_MIN <= units <= INT_MAX:
        raise FailSignal(f"'{text}' is too big to hold")
    return MoneyValue(units, currency)


def round_ratio(p: int, q: int, mode: str) -> int:
    """p / q, exactly, rounded to a whole number by `mode`. q != 0.
    The prover's formulas for percent_of are this, in Z3's integers."""
    if q < 0:
        p, q = -p, -q
    f, r = divmod(p, q)              # floor, and 0 <= r < q
    if r == 0:
        return f
    if mode == "down":               # toward zero
        return f if p >= 0 else f + 1
    if 2 * r > q:
        return f + 1
    if 2 * r < q:
        return f
    if mode == "half_up":            # a half goes away from zero
        return f + 1 if p >= 0 else f
    return f if f % 2 == 0 else f + 1    # half_even


class ReturnSignal(Exception):
    def __init__(self, value: Any) -> None: self.value = value


class RecElem:
    """rows[i] before a field is chosen: .amount selects from the
    field's array at that index."""
    def __init__(self, src: Any, idx: Any) -> None:
        self.src = src
        self.idx = idx


class RecListVal:
    """A list of records, as one array per provable field.

    get(rows, i).amount becomes Select(amount_arr, i) - so bounds are
    checked (the off-by-one over a record list refused before running,
    like the Int-list case) and field arithmetic can prove.
    """
    def __init__(self, rname: Any, arrays: Any, length: Any) -> None:
        self.rname = rname          # the record type's name
        self.arrays = arrays        # field name -> z3 Int array
        self.length = length


class OpaqueList:
    """A list whose contents the prover cannot see - only its length.

    Enough for the contracts people actually write about lists of
    records: length(items) > 0, length(result) == length(items), and
    for a divisor to be provably nonzero.
    """
    def __init__(self, length: Any) -> None:
        self.length = length


class FailSignal(Exception):
    def __init__(self, reason: Any) -> None: self.reason = reason


class HandleValue:
    """A ticket for something living on the Python side of the bridge."""
    __slots__ = ("id", "what")

    def __init__(self, id_: int, what: str) -> None:
        self.id, self.what = id_, what

    def __repr__(self) -> str:
        return f"<{self.what} #{self.id}>"


class Bound:
    """A function value carrying the values it was made with: the lifted
    function, and {name: value} read once when the value was made. It
    prints as the function it is, `fn` and the lifted name (9.0, M3); it
    printed as a Python object, with its address, before."""
    __slots__ = ("fn", "caught")

    def __init__(self, fn: Any, caught: Any) -> None:
        self.fn = fn
        self.caught = caught

    def __repr__(self) -> str:
        return f"fn {self.fn.name}"


class RecordValue:
    def __init__(self, rname: str, fields: dict[Any, Any]) -> None:
        self.rname, self.fields = rname, fields

    def __eq__(self, other: Any) -> bool:
        return (isinstance(other, RecordValue)
                and self.rname == other.rname
                and self.fields == other.fields)

    def __repr__(self) -> str:
        # What a broken promise's message shows of a record (9.0, M3): its
        # name and fields, as Python writes a dataclass and as the message
        # shows an amount beside it. It was object.__repr__, whose address
        # changed from run to run, so the same broken promise gave a
        # different message every time and no second runtime could give
        # the one the reference gave.
        inner = ", ".join(f"{k}={v!r}" for k, v in self.fields.items())
        return f"{self.rname}({inner})"


def to_text(v: Any) -> str:
    if v.__class__ is MoneyValue:
        return money_text(v)
    if isinstance(v, (Function, Bound)):
        return repr(v)
    if isinstance(v, dict):
        return "{" + ", ".join(f"{to_text(k)}: {to_text(x)}"
                               for k, x in v.items()) + "}"
    if isinstance(v, RecordValue):
        inner = ", ".join(f"{k}: {to_text(x)}" for k, x in v.fields.items())
        return f"{v.rname}({inner})"
    if isinstance(v, HandleValue):
        return f"<{v.what} #{v.id}>"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, list):
        return "[" + ", ".join(to_text(x) for x in v) + "]"
    return str(v)


# ---- what writing a value out makes, counted before it is made (9.0, M3) ----
#
# The size limit counts what a run makes (runtime.size_of). Writing a value
# out makes a text as long as everything in it, and a value can hold one
# text many times - a list of the same text n times costs n items, and a
# list of two of the level below, nested, doubles at every level - so the
# operations that write a value out count what they are about to make
# before they make it (runtime.ahead), by these walks. Each gives exactly
# the UTF-8 bytes - a lone surrogate three, as size_of counts it - of what
# its writer writes, so stopping before writing stops where counting after
# would have; and each stops once its count passes `room`, so it costs no
# more than the limit allows whatever the value holds. test_runtime.py
# holds each to its writer.

def utf8_size(text: str) -> int:
    """A text's UTF-8 bytes, a lone surrogate three: runtime.size_of's."""
    return len(text) if text.isascii() else len(text.encode("utf-8",
                                                            "surrogatepass"))


def written_size(v: Any, room: int, log: bool = False) -> int:
    """What to_text(v) is, in bytes - and with `log`, what log_line makes
    of it - counted without writing it, stopping past `room`."""
    size = log_size if log else utf8_size
    total, todo = 0, [v]
    while todo and total <= room:
        x = todo.pop()
        if x.__class__ is MoneyValue:
            total += len(money_text(x))
        elif isinstance(x, (Function, Bound)):
            total += size(repr(x))
        elif isinstance(x, dict):      # {k: v, ...}: the brackets, ": " each
            total += 4 * len(x) if x else 2      # and ", " between
            if total <= room:
                for k, y in x.items():
                    todo += (k, y)
        elif isinstance(x, RecordValue):         # name(k: v, ...)
            total += size(x.rname) + (4 * len(x.fields) if x.fields else 2)
            for k in x.fields:
                total += size(k)
            if total <= room:
                todo += x.fields.values()
        elif isinstance(x, HandleValue):
            total += size(f"<{x.what} #{x.id}>")
        elif isinstance(x, bool):
            total += 4 if x else 5
        elif isinstance(x, list):      # [a, b]: the brackets, ", " between
            total += 2 * len(x) if x else 2
            if total <= room:
                todo += x
        else:
            total += size(str(x))
    return total


def shown_size(v: Any, room: int) -> int:
    """What str(v) is, in bytes - how a broken promise's message names a
    value: a text as itself, an amount as money_text writes it, anything
    else as repr() writes it, and so each text inside a list, a map or a
    record quoted and escaped - counted without writing it, stopping past
    `room`."""
    total, todo = 0, [(v, True)]
    while todo and total <= room:
        x, top = todo.pop()
        cls = x.__class__
        if cls is str:
            total += utf8_size(x) if top else len(repr(x).encode(
                "utf-8", "surrogatepass"))
        elif cls is MoneyValue:
            total += len(money_text(x) if top else repr(x))
        elif cls is list:
            total += 2 * len(x) if x else 2
            if total <= room:
                todo += ((y, False) for y in x)
        elif cls is dict:
            total += 4 * len(x) if x else 2
            if total <= room:
                for k, y in x.items():
                    todo += ((k, False), (y, False))
        elif cls is RecordValue:                 # name(k=v, ...)
            total += utf8_size(x.rname) + (3 * len(x.fields)
                                           if x.fields else 2)
            for k in x.fields:
                total += utf8_size(k)
            if total <= room:
                todo += ((y, False) for y in x.fields.values())
        else:
            total += utf8_size(repr(x))
    return total


# what json.dumps writes a character of a text as, past the character
# itself: a quote and a backslash one more, five control characters as a
# two-character escape, the rest of C0 as \u00XX
_JSON_ESCAPED = re.compile(r'[\x00-\x1f\\"]')


def _json_text_size(text: str) -> int:
    extra = 0
    for c in _JSON_ESCAPED.findall(text):
        extra += 1 if c in '"\\\n\r\t\b\f' else 5
    return 2 + utf8_size(text) + extra


def json_size(v: Any, room: int) -> int:
    """What json_of(v) is, in bytes - json.dumps(ensure_ascii=False) of
    what runtime's plain() makes of v: a map's keys as str() writes them,
    and two that write alike one key, as plain's dict makes them; a record
    an object of its fields; an amount {"currency": ..., "units": ...} -
    counted without writing it, stopping past `room`. A value json.dumps
    has no form for counts nothing: json_of refuses it."""
    import json
    total, todo = 0, [v]
    while todo and total <= room:
        x = todo.pop()
        if isinstance(x, (dict, RecordValue)):
            entries = ({str(k): y for k, y in x.items()}
                       if isinstance(x, dict) else x.fields)
            total += 4 * len(entries) if entries else 2
            for k in entries:
                total += _json_text_size(k)
            if total <= room:
                todo += entries.values()
        elif isinstance(x, list):
            total += 2 * len(x) if x else 2
            if total <= room:
                todo += x
        elif x.__class__ is MoneyValue:
            total += len(json.dumps({"currency": x.currency,
                                     "units": x.units}))
        elif isinstance(x, str):
            total += _json_text_size(x)
        elif x is None or x is True:
            total += 4
        elif x is False:
            total += 5
        elif isinstance(x, int):
            total += len(str(x))
        elif isinstance(x, float):
            total += len(json.dumps(x))
    return total


# What one line of a log may not hold (8.3): a character that ends the line
# it is on or starts another in whatever reads the error channel - every C0
# control but tab, DEL, the C1 controls, and the two Unicode separators some
# viewers break lines at.
_LOG_CONTROL = re.compile(r"[\x00-\x08\x0a-\x1f\x7f-\x9f\u2028\u2029]")


def log_line(text: str) -> str:
    r"""`text` as one line of a log: each character _LOG_CONTROL matches is
    written as an escape - \n, \r, or \xNN and \uNNNN - so no value can end
    the line it is on, begin a line of its own, or move a terminal's cursor
    back over one already written. A backslash is left as it is, so an
    escape and the same characters typed in a value read alike: what is
    promised is one line per call, not an encoding that can be reversed."""
    def one(m: "re.Match[str]") -> str:
        c = m.group(0)
        if c == "\n":
            return "\\n"
        if c == "\r":
            return "\\r"
        return ("\\x%02x" % ord(c) if ord(c) < 0x100
                else "\\u%04x" % ord(c))
    return _LOG_CONTROL.sub(one, text)


def log_size(text: str) -> int:
    """What log_line(text) is, in UTF-8 bytes, counted without writing it:
    each character _LOG_CONTROL matches is its escape - \\n and \\r two
    bytes for one, the rest of C0 and DEL four for one, C1 four for two,
    the two separators six for three."""
    n = utf8_size(text)
    for m in _LOG_CONTROL.finditer(text):
        o = ord(m.group(0))
        n += 1 if o in (0x0A, 0x0D) else 3 if o < 0x80 else 2 if o < 0x100 else 3
    return n
