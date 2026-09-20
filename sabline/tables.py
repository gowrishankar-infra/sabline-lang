"""The builtins, the effects, and the other fixed tables every stage reads.
"""
from typing import Any



FALLIBLE_BUILTINS = {"to_int", "read_file", "read_file_secret",
                     "fetch", "post",
                     "pop", "slice", "set_at",
                     "add_or_fail", "sub_or_fail", "mul_or_fail",
                     "div_or_fail", "mod_or_fail",
                     "fetch_status", "request", "py", "py_int", "py_float",
                     "py_json", "json_get", "json_int", "json_float",
                     "json_len", "py_new", "py_do", "py_field",
                     "divide_or_fail", "parse_money",
                     "hex_decode", "base64_decode",          # 8.5
                     "tool", "tool_secret"}   # + get on maps


# The eight. `declassify` joined the seven in 6.0: it is not a way to
# reach the outside world, it is the one way a Secret becomes an
# ordinary value (SPEC.md 3.1), and it is an effect for the same reason
# the other seven are - so that a signature says a function does it, the
# rule is transitive across the call graph, and an operator can refuse
# to grant it.
ALL_EFFECTS = ("io", "env", "fs", "net", "clock", "rand", "ffi",
               "declassify", "tool")
# `tool` joined in 8.5: a call to a tool the host process offers, through
# the manifest `sabline run --tools` was given (sabline/tools.py). It is an
# effect for the reason the others are - a signature says a function does
# it, the rule is transitive, an operator grants it by name and may narrow
# it - and with no manifest there is no tool to reach, so a program that
# ran under 8.4 meets nothing new.

# The default budget, since 5.0: the console and nothing else. A run
# given no budget used to get all seven effects, which made the one
# thing a capability language must get right - what an operator gets
# when they say nothing - the widest answer instead of the narrowest.
# io rather than nothing so that a refused program can still say why it
# stopped; CHANGELOG 5.0 says why that trade was made.
DEFAULT_ALLOW = "io"
ALLOW_ALL = "all"                       # the CLI shorthand for every effect


INT_MIN, INT_MAX = -(2 ** 63), 2 ** 63 - 1


REDACTED = "<secret>"      # what a trace and a broken promise print in


def _z3_installed() -> bool:
    """Is the prover available, without paying ~350ms to import it?

    importlib.util.find_spec only locates the package; z3 itself is
    imported when a proof actually starts. Programs with no contracts
    never pay for it.
    """
    try:
        import importlib.util
        return importlib.util.find_spec("z3") is not None
    except Exception:
        return False


HAVE_Z3 = _z3_installed()

BUILTINS = {
    # name          effects needed      argument types        returns
    "log":        {"effects": {"io"},     "types": ["Any"],         "ret": "Unit"},
    "print":      {"effects": {"io"},    "types": ["Any"],         "ret": "Unit"},
    "read_file":  {"effects": {"fs"},    "types": ["Text"],        "ret": "Text"},
    "write_file": {"effects": {"fs"},    "types": ["Text", "Any"], "ret": "Unit"},
    "fetch":      {"effects": {"net"},   "types": ["Text"],        "ret": "Text"},
    "now":        {"effects": {"clock"}, "types": [],              "ret": "Int"},
    "random":     {"effects": {"rand"},  "types": ["Int"],         "ret": "Int"},
    "ask":        {"effects": {"io"},     "types": ["Text"],        "ret": "Text"},
    # pure helpers (no effects) - usable everywhere, including promises
    "to_int":     {"effects": set(),      "types": ["Text"],        "ret": "Int"},
    "to_text":    {"effects": set(),      "types": ["Any"],         "ret": "Text"},
    "to_float":   {"effects": set(),      "types": ["Int"],         "ret": "Float"},
    "round":      {"effects": set(),      "types": ["Float"],       "ret": "Int"},
    "contains":   {"effects": set(),      "types": ["Text", "Text"], "ret": "Bool"},
    "split":      {"effects": set(),      "types": ["Text", "Text"], "ret": "List of Text"},
    "upper":      {"effects": set(),      "types": ["Text"],        "ret": "Text"},
    "chars":      {"effects": set(),      "types": ["Text"],        "ret": "List of Text"},
    "file_exists": {"effects": {"fs"},    "types": ["Text"],        "ret": "Bool"},
    "put":        {"effects": set(),      "types": ["Any", "Any", "Any"], "ret": "Any"},
    "get_or":     {"effects": set(),      "types": ["Any", "Any", "Any"], "ret": "Any"},
    "code_at":    {"effects": set(),      "types": ["Text", "Int"], "ret": "Int"},
    "py":         {"effects": {"ffi"},    "types": ["Text", "Text", "List of Text"], "ret": "Text"},
    "py_int":     {"effects": {"ffi"},    "types": ["Text", "Text", "List of Text"], "ret": "Int"},
    "py_float":   {"effects": {"ffi"},    "types": ["Text", "Text", "List of Text"], "ret": "Float"},
    "py_json":    {"effects": {"ffi"},    "types": ["Text", "Text", "Text"], "ret": "Text"},
    "py_new":     {"effects": {"ffi"},    "types": ["Text", "Text", "Text"], "ret": "Handle"},
    "py_do":      {"effects": {"ffi"},    "types": ["Handle", "Text", "Text"], "ret": "Text"},
    "py_field":   {"effects": {"ffi"},    "types": ["Handle", "Text"], "ret": "Text"},
    "py_close":   {"effects": {"ffi"},    "types": ["Handle"],       "ret": "Unit"},
    "json_get":   {"effects": set(),      "types": ["Text", "Text"], "ret": "Text"},
    "json_int":   {"effects": set(),      "types": ["Text", "Text"], "ret": "Int"},
    "json_float": {"effects": set(),      "types": ["Text", "Text"], "ret": "Float"},
    "json_len":   {"effects": set(),      "types": ["Text", "Text"], "ret": "Int"},
    "json_has":   {"effects": set(),      "types": ["Text", "Text"], "ret": "Bool"},
    "json_of":    {"effects": set(),      "types": ["Any"],          "ret": "Text"},
    "args":       {"effects": {"io"},     "types": [],              "ret": "List of Text"},
    "env":        {"effects": {"env"},    "types": ["Text", "Text"],
                   "ret": "Secret of Text"},
    "exit_with":  {"effects": {"io"},     "types": ["Int"],         "ret": "Unit"},
    "read_line":  {"effects": {"io"},     "types": [],              "ret": "Text"},
    "post":       {"effects": {"net"},    "types": ["Text", "Text"], "ret": "Text"},
    "fetch_status": {"effects": {"net"},  "types": ["Text"],        "ret": "Int"},
    "request":    {"effects": {"net"},    "types": ["Text", "Text", "Text", "Text"], "ret": "Text"},
    "format":     {"effects": set(),      "types": ["Any"],         "ret": "Text"},
    "has":        {"effects": set(),      "types": ["Any", "Any"],  "ret": "Bool"},
    "keys":       {"effects": set(),      "types": ["Any"],         "ret": "Any"},
    "all_of":     {"effects": set(),      "types": ["Any", "Any"],  "ret": "Bool"},
    "any_of":     {"effects": set(),      "types": ["Any", "Any"],  "ret": "Bool"},
    "lower":      {"effects": set(),      "types": ["Text"],        "ret": "Text"},
    "length":     {"effects": set(),      "types": ["Any"],         "ret": "Int"},
    "push":       {"effects": set(),      "types": ["Any", "Any"],  "ret": "Any"},
    "pop":        {"effects": set(),      "types": ["Any"],         "ret": "Any"},
    "slice":      {"effects": set(),      "types": ["Any", "Int", "Int"], "ret": "Any"},
    "set_at":     {"effects": set(),      "types": ["Any", "Int", "Any"], "ret": "Any"},
    "add_or_fail": {"effects": set(),     "types": ["Int", "Int"],  "ret": "Int"},
    "div_or_fail": {"effects": set(),     "types": ["Int", "Int"],  "ret": "Int"},
    "mod_or_fail": {"effects": set(),     "types": ["Int", "Int"],  "ret": "Int"},
    "sub_or_fail": {"effects": set(),     "types": ["Int", "Int"],  "ret": "Int"},
    "mul_or_fail": {"effects": set(),     "types": ["Int", "Int"],  "ret": "Int"},
    "get":        {"effects": set(),      "types": ["Any", "Any"],  "ret": "Any"},
    # Money (4.3), all pure. Their types are checked by their own rules
    # in check_types, because an amount's currency is part of its type;
    # these rows are what the docs and the editor show.
    "money":      {"effects": set(), "types": ["Int", "Text"],
                   "ret": "Money of that currency"},
    "units_of":   {"effects": set(), "types": ["Money of C, or List of Money of C"],
                   "ret": "Int"},
    "with_units": {"effects": set(), "types": ["Money of C", "Int"],
                   "ret": "Money of C"},
    "percent_of": {"effects": set(),
                   "types": ["Money of C", "Int", "Int", "Text"],
                   "ret": "Money of C"},
    "divide_or_fail": {"effects": set(),
                       "types": ["Money of C", "Int", "Text"],
                       "ret": "Money of C"},
    "text_of":    {"effects": set(), "types": ["Money of C"], "ret": "Text"},
    "parse_money": {"effects": set(), "types": ["Text", "Text"],
                    "ret": "Money of that currency"},
    # Secret (6.0). read_file_secret reads a file the way read_file
    # does and calls what it read a secret; declassify is the only way
    # out of Secret, and its types are checked by their own rule in
    # check_types because the result is the argument's inner type.
    "read_file_secret": {"effects": {"fs"}, "types": ["Text"],
                         "ret": "Secret of Text"},
    "declassify": {"effects": {"declassify"},
                   "types": ["Secret of T", "Text"], "ret": "T"},
    # Digests and encoders (8.5), all pure: what stdlib/aws.vel needs to
    # sign a request, and what a reply in base64 needs to be read. Text in,
    # Text out, as UTF-8; a decoder fails on what is not the encoding, or
    # does not decode to UTF-8.
    "sha256":        {"effects": set(), "types": ["Text"], "ret": "Text"},
    "hex_encode":    {"effects": set(), "types": ["Text"], "ret": "Text"},
    "hex_decode":    {"effects": set(), "types": ["Text"], "ret": "Text"},
    "base64_encode": {"effects": set(), "types": ["Text"], "ret": "Text"},
    "base64_decode": {"effects": set(), "types": ["Text"], "ret": "Text"},
    "url_encode":    {"effects": set(), "types": ["Text"], "ret": "Text"},
    # HMAC-SHA256 under a Secret key (8.5). The result is NOT a Secret: a
    # MAC is what a signed request shows the world. That makes each of these
    # a way out of Secret, so each needs the `declassify` effect, is checked
    # by its own rule in check_types, and is named in the audit's secrets
    # with the fixed reason "hmac signature" (THREAT_MODEL.md says why this
    # is sound, and what it leaves). The chain is HMAC applied again and
    # again, each result the next key, as raw bytes: SigV4's derived keys
    # are credentials themselves and never become values of the program.
    "hmac_sha256": {"effects": {"declassify"},
                    "types": ["Secret of Text", "Text"], "ret": "Text"},
    "hmac_sha256_chain": {"effects": {"declassify"},
                          "types": ["Secret of Text", "List of Text"],
                          "ret": "Text"},
    # Tools (8.5): a call to a tool the host process offers. The arguments
    # are a JSON object as Text; what comes back is the tool's result as
    # Text - or a Secret of Text, from tool_secret, which a tool the
    # manifest marks secret has to be called through.
    "tool":        {"effects": {"tool"}, "types": ["Text", "Text"],
                    "ret": "Text"},
    "tool_secret": {"effects": {"tool"}, "types": ["Text", "Text"],
                    "ret": "Secret of Text"},
}

KNOWN_TYPES = {"Int", "Text", "Bool", "Float", "Handle"}

# ---- Money (4.3) ------------------------------------------------------------
# An amount is a whole number of minor units - paise, cents - and a
# currency. It is an Int underneath, so it is exact and it proves the way
# an Int proves; its currency is part of its type, so an amount in INR
# never meets one in USD; and no Float is part of anything it does
# (SPEC.md 4.3, and 4.4 for the currency table).

# ISO 4217 code -> digits after the point. Not every currency: the ones
# a program here has needed. Adding one is a line here, with the minor
# unit ISO 4217 gives it, and a case in check_money.py. A program cannot
# add its own, because two programs that disagreed about how many digits
# a currency has would print the same amount two ways.
CURRENCIES = {
    "AED": 2, "AUD": 2, "BHD": 3, "BRL": 2, "CAD": 2, "CHF": 2,
    "CNY": 2, "EUR": 2, "GBP": 2, "HKD": 2, "INR": 2, "JOD": 3,
    "JPY": 0, "KRW": 0, "KWD": 3, "MXN": 2, "OMR": 3, "SAR": 2,
    "SGD": 2, "USD": 2, "ZAR": 2,
}

# how a division that does not come out even is rounded; always named in
# the call, never assumed. half_up takes a half away from zero, half_even
# to the even neighbour, down toward zero.
ROUNDING = ("half_up", "half_even", "down")

MONEY_BUILTINS = frozenset({"money", "units_of", "with_units", "percent_of",
                            "divide_or_fail", "text_of", "parse_money"})

# Builtins added from 4.3 on give way to a function of the same name that
# a program defines (SPEC.md 10.1). A program written before a builtin
# existed can have used its name, and a minor version must not change
# what that program means. The older builtins keep the precedence they
# always had.
SECRET_BUILTINS = frozenset({"read_file_secret", "declassify"})

# Builtins that hand back a Secret. The audit's secrets.sources lists
# the ones a program reaches (sabline-spec 8.6).
SECRET_SOURCES = ("env", "read_file_secret", "tool_secret")

# 8.5. HMAC_REASON is the reason the audit and a receipt give for an
# hmac_sha256 or hmac_sha256_chain call: fixed, because the call has no
# reason of its own to write.
DIGEST_BUILTINS = frozenset({"sha256", "hex_encode", "hex_decode",
                             "base64_encode", "base64_decode", "url_encode"})
HMAC_BUILTINS = frozenset({"hmac_sha256", "hmac_sha256_chain"})
HMAC_REASON = "hmac signature"
TOOL_BUILTINS = frozenset({"tool", "tool_secret"})

NEW_BUILTINS = (MONEY_BUILTINS | SECRET_BUILTINS | DIGEST_BUILTINS
                | HMAC_BUILTINS | TOOL_BUILTINS)


def builtin_reached(name: str, table: Any) -> str | None:
    """The builtin a call to `name` reaches in this program, or None when
    it reaches a function of the program's own. `table` is the program's
    functions by name. A call written '@name' was bound to the builtin
    when the program was loaded (_bind_new_builtins)."""
    if name[:1] == "@":
        return name[1:]
    if name in NEW_BUILTINS and table and name in table:
        return None
    return name if name in BUILTINS else None


def shown_name(name: str) -> str:
    """A call's name as the program wrote it."""
    return name[1:] if name[:1] == "@" else name


# check and audit read untrusted source (a hostile contract can send the
# prover into a long search; a crafted expression a long walk). The prover
# has a per-query budget and the parser caps expression depth, but the
# whole operation had no ceiling until 8.0. `sabline check` and `sabline
# audit` now run under a wall-clock and memory ceiling, so a platform that
# audits before running cannot be stalled by the source it audits. The
# defaults are generous; --check-timeout raises the clock.
CHECK_TIMEOUT_DEFAULT = 60          # seconds, the whole check or audit
CHECK_MEMORY_MB_DEFAULT = 2048      # MB, the whole check or audit
