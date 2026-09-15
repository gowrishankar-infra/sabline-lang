"""Money of C and Secret of T: the two types that wrap another, and the
rules that keep currencies apart and secrets in.
"""
from .errors import VelarisError
from .lexer import fn_sig_parts
from typing import Any


def is_money(t: str) -> bool:
    return t.startswith("Money of ")


def currency_clash(a: str, b: str) -> bool:
    """Two types that differ only in the currency of an amount: Money of
    INR and Money of USD, or lists, maps or secrets of them."""
    if a.startswith(SECRET_PREFIX) and b.startswith(SECRET_PREFIX):
        return currency_clash(secret_inner(a), secret_inner(b))
    if is_money(a) and is_money(b):
        return a != b
    if a.startswith("List of ") and b.startswith("List of "):
        return currency_clash(a[8:], b[8:])
    if a.startswith("Map of ") and b.startswith("Map of "):
        ak, _, av = a[7:].partition(" to ")
        bk, _, bv = b[7:].partition(" to ")
        return ak == bk and currency_clash(av, bv)
    return False


def clash_error(want: str, got: str, line: int, what: str = "") -> VelarisError:
    return VelarisError("E550",
        (what or "this") + f" is {got}, where {want} is needed - amounts "
        f"in two currencies do not mix", line,
        fixes=["convert on purpose: a rate and a rounding mode are a "
               "program's decision, so there is no conversion builtin",
               "or keep both sides in one currency"])


def _outside_money(t: str, tv: str) -> bool:
    """Does type t mention type variable tv anywhere other than as the
    currency of an amount?"""
    if t == tv:
        return True
    if is_money(t):
        return False
    if t.startswith(SECRET_PREFIX):
        return _outside_money(secret_inner(t), tv)
    if t.startswith("List of "):
        return _outside_money(t[8:], tv)
    if t.startswith("Map of "):
        k, _, v = t[7:].partition(" to ")
        return _outside_money(k, tv) or _outside_money(v, tv)
    sig = fn_sig_parts(t)
    if sig is not None:
        parts, ret = sig
        return any(_outside_money(p, tv) for p in parts) or \
            _outside_money(ret, tv)
    return False


def currency_generic(fn: Any) -> bool:
    """True when every type variable of fn stands only for the currency
    of an amount. Such a function means the same to the prover whatever
    the currency, since an amount is its minor units there."""
    types = [t for _, t in fn.params] + [fn.return_type or "Unit"]
    return bool(fn.type_vars) and not any(
        _outside_money(t, tv) for tv in fn.type_vars for t in types)


def erase_wrappers(t: str) -> str:
    """The prover's view of a type: an amount is its minor units, an
    Int, and a secret is whatever it wraps. The type checker has already
    kept every currency apart and kept every secret away from a sink, so
    neither distinction means anything to the solver - a Secret of Int
    proves exactly as an Int does."""
    if t.startswith("Secret of "):
        return erase_wrappers(t[len("Secret of "):])
    if is_money(t):
        return "Int"
    if t.startswith("List of "):
        return "List of " + erase_wrappers(t[8:])
    if t.startswith("Map of "):
        k, _, v = t[7:].partition(" to ")
        return f"Map of {k} to {erase_wrappers(v)}"
    return t


# ---- Secret (6.0) -----------------------------------------------------------
# A value the type system tracks so that it cannot reach anything that
# emits it. `Secret of T` wraps any T; it is made by env() and
# read_file_secret(), it survives every pure operation over it, and
# declassify() - which needs the `declassify` effect and a written
# reason - is the only way out. SPEC.md 3.1 states the rules; this is
# the type-level half of them.

SECRET_PREFIX = "Secret of "


def is_secret(t: str) -> bool:
    return t.startswith(SECRET_PREFIX)


def secret_inner(t: str) -> str:
    return t[len(SECRET_PREFIX):]


def wrap_secret(t: str) -> str:
    """A result derived from a secret is a secret. No exceptions - a
    Bool least of all. A comparison is not a one-bit channel: with
    `length` and a loop, `secret == c` reads the value out character by
    character, and a program that could print that Bool could print the
    whole key. So a Bool derived from a Secret is a `Secret of Bool`,
    which nothing prints and nothing branches on (E560, E563), and
    `declassify` is what a program writes when it means to act on one.
    SPEC.md 3.1 states the choice. `Unit` is not a value.

    `Secret of Secret of T` is the same secret, so a type that already
    carries one is left alone."""
    if t in ("Unit", "") or carries_secret(t):
        return t
    return SECRET_PREFIX + t


def strip_secret(t: str) -> str:
    """The type underneath, with every Secret wrapper removed and
    everything else - an amount's currency above all - left alone."""
    if t.startswith(SECRET_PREFIX):
        return strip_secret(secret_inner(t))
    if t.startswith("List of "):
        return "List of " + strip_secret(t[8:])
    if t.startswith("Map of "):
        k, _, v = t[7:].partition(" to ")
        return f"Map of {k} to {strip_secret(v)}"
    return t


def carries_secret(t: str, records: Any = None) -> bool:
    """Does a value of this type hold a secret anywhere inside it?

    A list of secrets, a map whose values are secrets and a record with
    a secret field all answer yes, so a structure cannot be used to
    smuggle one past the sink check. `records` maps a record name to
    whether it carries one; without it a record name answers no, which
    is only right where records cannot appear."""
    if t.startswith(SECRET_PREFIX):
        return True
    if t.startswith("List of "):
        return carries_secret(t[8:], records)
    if t.startswith("Map of "):
        return carries_secret(t[7:].partition(" to ")[2], records)
    sig = fn_sig_parts(t)
    if sig is not None:
        # A function value is a name, not the values it would return:
        # printing one prints nothing a caller did not already have,
        # and it cannot be called without its result being checked
        # where it is used. Its parameter and result types are not
        # walked for that reason.
        return False
    return bool(records) and bool(records.get(t))


def records_carrying(records: Any) -> dict[Any, Any]:
    """Which record types hold a secret, directly or through another
    record, a list or a map. A fixpoint, so a record that holds a list
    of records that hold a secret is one too."""
    carry = {r.name: False for r in records}
    changed = True
    while changed:
        changed = False
        for r in records:
            if carry[r.name]:
                continue
            if any(carries_secret(ft, carry) for _, ft in r.fields):
                carry[r.name] = True
                changed = True
    return carry
