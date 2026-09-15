"""The values a running program holds that are not Python's own: amounts,
records, handles, and the signals that end a call.
"""
import re
from dataclasses import dataclass

from .errors import VelarisError
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
            raise VelarisError("E550",        # this is the second lock
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


class RecordValue:
    def __init__(self, rname: str, fields: dict[Any, Any]) -> None:
        self.rname, self.fields = rname, fields

    def __eq__(self, other: Any) -> bool:
        return (isinstance(other, RecordValue)
                and self.rname == other.rname
                and self.fields == other.fields)


def to_text(v: Any) -> str:
    if v.__class__ is MoneyValue:
        return money_text(v)
    if isinstance(v, Function):
        return f"fn {v.name}"
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
