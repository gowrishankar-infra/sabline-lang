"""Stage 8, the interpreter: every builtin, and the run itself.
"""
import functools
import os
import sys
import threading

from . import state as _state
from .version import VERSION
from .errors import VelarisError
from .nodes import (
    Assign,
    BinOp,
    Bool,
    Call,
    Check,
    Closure,
    ExprStmt,
    FailStmt,
    FieldGet,
    FloatNum,
    Function,
    If,
    Let,
    ListLit,
    MapLit,
    Neg,
    Not,
    Num,
    RecordLit,
    Return,
    Str,
    TryExpr,
    Var,
    While,
)
from .parser import expr_str, expr_vars, nice_name
from .tables import (
    BUILTINS,
    CURRENCIES,
    INT_MAX,
    INT_MIN,
    MONEY_BUILTINS,
    NEW_BUILTINS,
    REDACTED,
    ROUNDING,
)
from .recorder import _note_redirect
from .loader import blame, unknown_function
from .values import (
    log_line,
    FailSignal,
    HandleValue,
    MoneyValue,
    RecordValue,
    ReturnSignal,
    money_text,
    parse_money_text,
    round_ratio,
    to_text,
)
from .budget import (
    _RedirectRefused,
    _ffi_resolve,
    allow_host,
    allow_path,
    checked_int,
    count_op,
    ffi_reach,
    guarded_opener,
    spend,
    trace_enter,
    trace_leave,
)
from typing import Any, Callable, ParamSpec, TypeVar, cast

_P = ParamSpec("_P")
_R = TypeVar("_R")

# ---------------------------------------------------------------------------
# 5. INTERPRETER — actually run the program (main() is the entry point)
# ---------------------------------------------------------------------------


# effects per builtin, sorted once instead of on every call
BUILTIN_EFFECTS = {n: tuple(sorted(d.get("effects", ())))
                   for n, d in BUILTINS.items() if d.get("effects")}


def run_money(name: str, args: list[Any], line: int) -> Any:
    """The Money builtins while running (SPEC.md 4.4). The type checker
    has already seen to the currencies and the written arguments; what
    is left is exact integer arithmetic, and its range."""
    if name == "money":
        cur = str(args[1])
        if cur not in CURRENCIES:              # kept out before running
            raise VelarisError("E551",
                f"'{cur}' is not a currency Velaris knows", line)
        return MoneyValue(int(args[0]), cur)
    if name == "units_of":
        x = args[0]
        if x.__class__ is MoneyValue:
            return x.units
        total = 0
        for m in x:                            # as a loop adding them
            total = checked_int(total + m.units, "units_of", line)
        return total
    if name == "with_units":
        return MoneyValue(int(args[1]), args[0].currency)
    if name == "text_of":
        return money_text(args[0])
    if name == "parse_money":
        return parse_money_text(args[0], str(args[1]))
    mode = str(args[-1])
    if mode not in ROUNDING:                   # kept out before running
        raise VelarisError("E552",
            f"'{mode}' is not a rounding mode", line)
    m = args[0]
    if name == "percent_of":
        num, den = int(args[1]), int(args[2])
        if den == 0:
            raise VelarisError("E403", "percent_of with a denominator of "
                               "zero", line,
                               fixes=["check the denominator first"])
        # the product is exact, however large: only the answer must fit
        return checked_int(MoneyValue(round_ratio(m.units * num, den, mode),
                                      m.currency), "percent_of", line)
    by = int(args[1])                          # divide_or_fail
    if by == 0:
        raise FailSignal("cannot divide an amount by zero")
    units = round_ratio(m.units, by, mode)
    if not INT_MIN <= units <= INT_MAX:
        raise FailSignal(f"dividing {money_text(m)} by {by} makes an "
                         f"amount too big to hold")
    return MoneyValue(units, m.currency)


def run_builtin(name: str, args: list[Any], line: int) -> Any:
    # The hot three, before anything else: these are most of the builtin
    # calls in any program and used to sit behind thirty string
    # comparisons and two module imports. None of them has effects, so
    # the budget check does not apply.
    if name == "length":
        a0 = args[0]
        return len(a0) if not isinstance(a0, str) else len(a0)
    if name == "get" and isinstance(args[0], list):
        xs, at = args[0], args[1]
        if not isinstance(at, int) or at < 0 or at >= len(xs):
            raise VelarisError("E602",
                f"this list has {len(xs)} item(s), so there is no "
                f"position {at}", line,
                fixes=["check the length before reading",
                       "or add a 'requires' about the length"])
        return xs[at]
    if name == "push" and isinstance(args[0], list):
        return args[0] + [args[1]]
    if name in MONEY_BUILTINS:
        return run_money(name, args, line)

    import time as _time
    import random as _rand
    for effect in BUILTIN_EFFECTS.get(name, ()):   # precomputed; this
        spend(effect, name, line)                  # ran sorted() on
                                                   # every single call
    if name == "print":
        print(to_text(args[0]))
        return None
    if name == "ask":
        try:
            return input(str(args[0]) + " ")
        except (EOFError, KeyboardInterrupt):
            raise VelarisError("E607", "no input available to read", line,
                               fixes=["run this program in a terminal where "
                                      "you can type an answer"])
    if name == "to_int":
        t = str(args[0]).strip()
        body = t[1:] if t.startswith("-") else t
        # isdecimal, not isdigit: '²' is a digit int() refuses (8.2)
        if not body.isdecimal():
            raise FailSignal(f"'{args[0]}' is not a whole number")
        # a whole number past 64 bits is not an Int; and a text of thousands
        # of digits made Python itself refuse (8.2)
        value: int | float | None = int(t) if len(body.lstrip("0")) <= 19 else None
        if value is None or not INT_MIN <= value <= INT_MAX:
            raise FailSignal(f"'{args[0]}' is a whole number too big to hold "
                             f"(whole numbers go from {INT_MIN} to {INT_MAX})")
        return value
    if name == "to_text":
        return to_text(args[0])
    if name == "to_float":
        return float(args[0])
    if name == "round":
        x = args[0]
        # round of an infinity or NaN has no whole number, and one past 64
        # bits does not fit: E407 (8.2; the first two were Python errors)
        if x != x or x in (float("inf"), float("-inf")) \
                or not INT_MIN <= round(x) <= INT_MAX:
            raise VelarisError("E407", f"round({x!r}) has no whole number "
                               f"that fits in 64 bits (from {INT_MIN} to "
                               f"{INT_MAX})", line,
                               fixes=["check the value is in range before "
                                      "rounding it"])
        return int(round(x))
    if name == "contains":
        return str(args[1]) in str(args[0])
    if name == "split":
        if args[1] == "":
            raise VelarisError("E609", "cannot split by empty text", line,
                               fixes=['use a separator like " " or ","'])
        return str(args[0]).split(str(args[1]))
    if name == "upper":
        return str(args[0]).upper()
    if name == "chars":
        return list(str(args[0]))
    if name == "file_exists":
        if "\x00" in str(args[0]):          # names no file (8.2)
            return False
        real = allow_path("any", str(args[0]), name, line)
        count_op("fs", name, line)
        return os.path.exists(real)
    if name == "lower":
        return str(args[0]).lower()
    if name == "length":
        return len(args[0])
    if name == "pop":
        xs = args[0]
        if not xs:
            raise FailSignal("there is nothing left to take off the end")
        return list(xs[:-1])
    if name == "slice":
        xs, start, stop = args[0], int(args[1]), int(args[2])
        if start < 0 or stop > len(xs) or start > stop:
            raise FailSignal(
                f"a slice from {start} to {stop} does not fit a list of "
                f"{len(xs)}")
        return list(xs[start:stop])
    if name == "set_at":
        xs, at = args[0], int(args[1])
        if at < 0 or at >= len(xs):
            raise FailSignal(
                f"there is no position {at} in a list of {len(xs)}")
        out: Any = list(xs)
        out[at] = args[2]
        return out
    if name in ("div_or_fail", "mod_or_fail"):
        a, b = int(args[0]), int(args[1])
        if b == 0:
            word = "divide" if name == "div_or_fail" else "take a remainder"
            raise FailSignal(f"cannot {word} by zero")
        answer = a // b if name == "div_or_fail" else a % b
        if not INT_MIN <= answer <= INT_MAX:     # the smallest Int by -1
            raise FailSignal(f"dividing {a} by {b} makes a number too big "
                             f"to hold")
        return answer
    if name in ("add_or_fail", "sub_or_fail", "mul_or_fail"):
        a, b = int(args[0]), int(args[1])
        answer = (a + b if name == "add_or_fail" else
                  a - b if name == "sub_or_fail" else a * b)
        if not (-(2 ** 63) <= answer <= 2 ** 63 - 1):
            word = {"add_or_fail": "adding", "sub_or_fail": "subtracting",
                    "mul_or_fail": "multiplying"}[name]
            raise FailSignal(
                f"{word} {a} and {b} makes a number too big to hold")
        return answer
    if name == "push":
        return args[0] + [args[1]]
    if name == "put":
        m, k, v = args
        out = dict(m)
        out[k] = v
        return out
    if name == "has":
        return args[1] in args[0]
    if name == "keys":
        return list(args[0].keys())
    if name in ("py_new", "py_do", "py_field", "py_close"):
        import json as _json

        def resolve(module: str, func: str) -> Any:
            return _ffi_resolve(module, func, name, line)

        def split_args(raw: Any) -> tuple[Any, ...]:
            """A JSON list of arguments; a trailing object is keywords."""
            try:
                vals = _json.loads(str(raw))
            except Exception as e:
                raise FailSignal(f"the arguments are not valid JSON: {e}")
            if not isinstance(vals, list):
                raise FailSignal("the arguments must be a JSON list")
            kwargs = {}
            if (vals and isinstance(vals[-1], dict)
                    and set(vals[-1]) != {"handle"}):
                kwargs = {str(k): v for k, v in vals[-1].items()}
                vals = vals[:-1]
            return [unwrap(v) for v in vals], {k: unwrap(v)
                                               for k, v in kwargs.items()}

        def unwrap(v: Any) -> Any:
            """A handle written as {"handle": 3} becomes the object."""
            if isinstance(v, dict) and set(v) == {"handle"}:
                try:
                    obj = _state.PY_OBJECTS.get(int(v["handle"]))
                except (TypeError, ValueError, OverflowError):
                    obj = None                 # not a handle's number
                if obj is None:
                    raise FailSignal("that handle is closed or unknown")
                return obj
            return v

        def keep(obj: Any) -> "HandleValue":
            _state.PY_NEXT[0] += 1
            _state.PY_OBJECTS[_state.PY_NEXT[0]] = obj
            return HandleValue(_state.PY_NEXT[0], type(obj).__name__)

        def answer_of(out: Any) -> Any:
            if isinstance(out, (bytes, bytearray)):
                out = out.decode("utf-8", errors="replace")
            try:
                return _json.dumps(out, ensure_ascii=False)
            except TypeError:                  # not JSON: keep it alive
                return _json.dumps({"handle": keep(out).id})
            except (ValueError, RecursionError):
                # a cycle, a nesting too deep, a number too long (8.2)
                raise FailSignal("the value Python gave back cannot be "
                                 "made JSON")

        if name == "py_close":
            h = args[0]
            if isinstance(h, HandleValue):
                obj = _state.PY_OBJECTS.pop(h.id, None)
                for closer in ("close", "shutdown", "__exit__"):
                    fn_ = getattr(obj, closer, None)
                    if fn_ is not None:
                        try:
                            fn_() if closer != "__exit__" else fn_(
                                None, None, None)
                        except Exception:
                            pass
                        break
            return None

        if name == "py_new":
            target = resolve(args[0], args[1])
            pos, kw = split_args(args[2])
            try:
                built = target(*pos, **kw)
            except Exception as e:
                raise FailSignal(f"{args[0]}.{args[1]} failed: {e}")
            ffi_reach(built, name, line, "the object it built")
            return keep(built)

        h = args[0]
        if not isinstance(h, HandleValue):
            raise FailSignal("this is not a handle")
        obj = _state.PY_OBJECTS.get(h.id)
        if obj is None:
            raise FailSignal("that handle is closed")
        # a method or field reached through a handle is checked the same
        # way as one reached through a module: a handle to a granted
        # module's object must not be a door into an ungranted one
        if name == "py_field":
            got = getattr(obj, str(args[1]), None)
            if got is None:
                raise FailSignal(f"no '{args[1]}' on {h.what}")
            ffi_reach(got, name, line, f"field '{args[1]}' of {h.what}")
            return answer_of(got)
        method = getattr(obj, str(args[1]), None)
        if method is None:
            raise FailSignal(f"{h.what} has no '{args[1]}'")
        ffi_reach(method, name, line, f"method '{args[1]}' of {h.what}")
        pos, kw = split_args(args[2])
        try:
            produced = method(*pos, **kw)
        except Exception as e:
            raise FailSignal(f"{h.what}.{args[1]} failed: {e}")
        ffi_reach(produced, name, line,
                  f"the object '{args[1]}' returned")
        return answer_of(produced)
    if name.startswith("json_") or name == "py_json":
        import json as _json

        def walk(doc_text: Any, path_text: Any, what: Any) -> Any:
            try:
                cur = _json.loads(str(doc_text))
            except Exception as e:
                raise FailSignal(f"this is not valid JSON: {e}")
            if str(path_text) == "":
                return cur
            for step in str(path_text).replace("[", ".").replace(
                    "]", "").split("."):
                if step == "":
                    continue
                if isinstance(cur, list):
                    try:
                        idx = int(step)
                    except ValueError:
                        raise FailSignal(
                            f"'{step}' is not a position in a list "
                            f"(while looking for '{path_text}')")
                    if not -len(cur) <= idx < len(cur):
                        raise FailSignal(
                            f"position {idx} is outside this list of "
                            f"{len(cur)} (while looking for "
                            f"'{path_text}')")
                    cur = cur[idx]
                elif isinstance(cur, dict):
                    if step not in cur:
                        raise FailSignal(
                            f"there is no '{step}' here (while looking "
                            f"for '{path_text}')")
                    cur = cur[step]
                else:
                    raise FailSignal(
                        f"cannot look inside {type(cur).__name__} "
                        f"(while looking for '{path_text}')")
            return cur

        if name == "json_of":
            def plain(v: Any) -> Any:
                if isinstance(v, dict):
                    return {str(k): plain(x) for k, x in v.items()}
                if isinstance(v, list):
                    return [plain(x) for x in v]
                if isinstance(v, RecordValue):
                    return {f: plain(x) for f, x in v.fields.items()}
                if v.__class__ is MoneyValue:     # exact: never a JSON
                    return {"currency": v.currency,   # number with a point
                            "units": v.units}
                return v
            return _json.dumps(plain(args[0]), ensure_ascii=False)

        if name == "json_has":
            try:
                walk(args[0], args[1], "has")
                return True
            except FailSignal:
                return False

        if name == "json_len":
            got = walk(args[0], args[1], "len")
            if isinstance(got, (list, dict, str)):
                return len(got)
            raise FailSignal("this value has no length")

        if name in ("json_get", "json_int", "json_float"):
            got = walk(args[0], args[1], name)
            if name == "json_get":
                if isinstance(got, bool):
                    return "true" if got else "false"
                if isinstance(got, (dict, list)):
                    return _json.dumps(got, ensure_ascii=False)
                return "" if got is None else str(got)
            try:
                value = int(got) if name == "json_int" else float(got)
            except (TypeError, ValueError, OverflowError):
                raise FailSignal(
                    f"'{args[1]}' is not a "
                    f"{'whole number' if name == 'json_int' else 'decimal'}")
            if name == "json_int" and not INT_MIN <= value <= INT_MAX:
                raise FailSignal(f"'{args[1]}' is a whole number too big to "
                                 f"hold (from {INT_MIN} to {INT_MAX})")
            return value

        # py_json: arguments and answer both travel as JSON, so numbers,
        # lists and nested data survive the trip intact
        module, func, args_json = args[0], args[1], args[2]
        try:
            call_args = _json.loads(str(args_json))
        except Exception as e:
            raise FailSignal(f"the arguments are not valid JSON: {e}")
        if not isinstance(call_args, list):
            raise FailSignal("the arguments must be a JSON list, "
                             'like [1, "two", [3]]')
        def unwrap_handle(v: Any) -> Any:
            if isinstance(v, dict) and set(v) == {"handle"}:
                try:
                    obj = _state.PY_OBJECTS.get(int(v["handle"]))
                except (TypeError, ValueError, OverflowError):
                    obj = None                 # not a handle's number
                if obj is None:
                    raise FailSignal("that handle is closed or unknown")
                return obj
            return v

        kwargs = {}
        if (call_args and isinstance(call_args[-1], dict)
                and set(call_args[-1]) != {"handle"}):
            kwargs = {str(k): unwrap_handle(v)
                      for k, v in call_args[-1].items()}
            call_args = call_args[:-1]
        call_args = [unwrap_handle(v) for v in call_args]
        target = _ffi_resolve(module, func, name, line)

        def call_py_json() -> Any:
            try:
                out = target(*call_args, **kwargs)
            except Exception as e:
                raise FailSignal(f"{module}.{func} failed: {e}")
            if isinstance(out, (bytes, bytearray)):
                out = out.decode("utf-8", errors="replace")
            try:
                return _json.dumps(out, ensure_ascii=False)
            except (ValueError, RecursionError):
                # a cycle, a nesting too deep, a number too long (8.2)
                raise FailSignal(f"{module}.{func} gave back a value that "
                                 f"cannot be made JSON")
            except TypeError:                     # not JSON: keep it alive
                ffi_reach(out, name, line, "the object it returned")
                _state.PY_NEXT[0] += 1
                _state.PY_OBJECTS[_state.PY_NEXT[0]] = out
                return _json.dumps({"handle": _state.PY_NEXT[0]})
        # recorded tool responses (8.3): after the grants are checked
        if _state.RESPONSES is not None:
            return _state.RESPONSES.answer(
                name, [str(module), str(func), str(args_json)],
                call_py_json, line)
        return call_py_json()
    if name in ("py", "py_int", "py_float"):
        module, func, call_args = args[0], args[1], args[2]
        target = _ffi_resolve(module, func, name, line)

        def call_py() -> Any:
            def as_number_if_it_is(text: Any) -> Any:
                """'16' -> 16 and '2.5' -> 2.5, so numeric functions work.

                The arguments arrive as Text (that is the declared type),
                but math.sqrt("16") is a TypeError in Python. A string that
                reads as a number is passed as one; anything else stays
                text. Functions genuinely wanting the text "16" still get
                it via the all-strings retry below.
                """
                s = str(text)
                try:
                    return int(s)
                except ValueError:
                    pass
                try:
                    return float(s)
                except ValueError:
                    return s

            attempts = ([as_number_if_it_is(a) for a in call_args],
                        [str(a) for a in call_args],
                        [str(a).encode("utf-8") for a in call_args])
            out: Any = None
            last_err: Exception | None = None
            for formed in attempts:
                try:
                    out = target(*formed)
                    last_err = None
                    break
                except TypeError as e:
                    last_err = e
                    continue                 # the next shape may fit
                except Exception as e:
                    raise FailSignal(f"{module}.{func} failed: {e}")
            if last_err is not None:
                raise FailSignal(f"{module}.{func} failed: {last_err}")
            if isinstance(out, (bytes, bytearray)):
                out = out.decode("utf-8", errors="replace")
            try:
                if name == "py_int":
                    value = int(out)
                    if not INT_MIN <= value <= INT_MAX:
                        raise FailSignal(f"{module}.{func} gave back a whole "
                                         f"number too big to hold")
                    return value
                if name == "py_float":
                    return float(out)
                return str(out)
            except (TypeError, ValueError, OverflowError, RecursionError):
                raise FailSignal(
                    f"{module}.{func} gave back something that is not a "
                    f"{'whole number' if name == 'py_int' else 'decimal' if name == 'py_float' else 'text'}")
        # recorded tool responses (8.3): after the grants are checked
        if _state.RESPONSES is not None:
            return _state.RESPONSES.answer(
                name, [str(module), str(func), [str(x) for x in call_args]],
                call_py, line)
        return call_py()
    if name == "code_at":
        t, i = args
        if i < 0 or i >= len(t):
            raise VelarisError("E602",
                f"position {i} is outside the text (it has {len(t)} "
                f"character(s))", line,
                fixes=["positions go from 0 to length - 1",
                       "check with length(...) before using code_at"])
        return ord(t[i])
    if name == "get_or":
        m, k, d = args
        return m.get(k, d)
    if name == "get" and isinstance(args[0], dict):
        m, k = args
        if k not in m:
            key_txt = f"'{k}'" if isinstance(k, str) else to_text(k)
            raise FailSignal(f"map has no key {key_txt}")
        return m[k]
    if name == "get":
        xs, i = args
        if i < 0 or i >= len(xs):
            raise VelarisError("E602",
                f"position {i} is outside the list (it has {len(xs)} item(s))",
                line, fixes=["positions go from 0 to length - 1",
                             "check with length(...) before using get"])
        return xs[i]
    if name in ("read_file", "read_file_secret"):
        if "\x00" in str(args[0]):
            # a NUL names no file; until 8.2 it reached os.path and ended
            # the run with a ValueError traceback
            raise FailSignal(f"cannot read file "
                             f"'{str(args[0]).replace(chr(0), chr(92) + '0')}': "
                             f"a path cannot hold a NUL character")
        real = allow_path("read", str(args[0]), name, line)
        count_op("fs", name, line)
        try:
            size = os.path.getsize(real)
        except OSError:
            size = None
        if size is not None and size > _state.MAX_READ_BYTES:
            raise VelarisError("E316",
                f"'{args[0]}' is {size} bytes, over the read ceiling of "
                f"{_state.MAX_READ_BYTES} bytes - a file is read whole, into "
                f"memory, so a large one is capped", line,
                fixes=[f"raise the ceiling: --max-read "
                       f"{max(1, size // (1024 * 1024) + 1)} (megabytes)",
                       "or read less, or read it in another program"])
        try:
            return open(real, encoding="utf-8").read()
        except OSError:
            raise FailSignal(f"cannot read file '{args[0]}'")
    if name == "declassify":
        # the effect was spent before this ran; a Secret is a compile-time
        # distinction, so at this point the value is simply itself. A
        # receipt records that it happened, where, and the reason written
        # in the call (a literal: E561) - never the value (8.1)
        if _state.RUN_RECORDER is not None:
            _state.RUN_RECORDER.note("declassify", reason=str(args[1]), line=line)
        return args[0]
    if name == "write_file":
        if "\x00" in str(args[0]):          # as read_file (8.2)
            raise VelarisError("E608",
                f"could not write "
                f"'{str(args[0]).replace(chr(0), chr(92) + '0')}': a path "
                f"cannot hold a NUL character", line,
                fixes=["build the path from text that holds no NUL"])
        real = allow_path("write", str(args[0]), name, line)
        count_op("fs", name, line)
        try:
            with open(real, "w", encoding="utf-8") as fh:
                fh.write(to_text(args[1]))
            return None
        except OSError as e:
            raise VelarisError("E608",
                f"could not write '{args[0]}': {e.strerror or e}", line,
                fixes=["check the folder exists and is writable",
                       "or write somewhere else"])

    if name == "request":
        import json as _json
        import urllib.request
        import urllib.error
        method, url, body, headers_json = (str(a) for a in args)
        method = method.upper() or "GET"
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        try:
            headers = _json.loads(headers_json) if headers_json.strip() \
                else {}
        except Exception as e:
            raise FailSignal(f"the headers are not valid JSON: {e}")
        if not isinstance(headers, dict):
            raise FailSignal('the headers must be a JSON object, like '
                             '{"Accept": "application/json"}')
        headers = {str(k): str(v) for k, v in headers.items()}
        headers.setdefault("User-Agent", f"velaris/{VERSION}")
        data = body.encode("utf-8") if body else None
        allow_host(url, name, line)
        opener = guarded_opener(url)         # may refuse a proxy (E317)
        count_op("net", name, line)
        req = urllib.request.Request(url, data=data, headers=headers,
                                     method=method)
        try:
            with opener.open(req, timeout=20) as resp:
                reply = {
                    "status": int(resp.status),
                    "body": resp.read(1 << 20).decode("utf-8",
                                                      errors="replace"),
                    "headers": {k: v for k, v in resp.headers.items()}}
        except urllib.error.HTTPError as e:      # a real answer
            reply = {
                "status": int(e.code),
                "body": e.read(1 << 20).decode("utf-8", errors="replace"),
                "headers": {k: v for k, v in (e.headers or {}).items()}}
        except _RedirectRefused as e:     # sent somewhere it may not go
            _note_redirect(line)
            raise FailSignal(f"'{url}' redirected to '{e.target}', which "
                             f"this run does not allow: {e.why}")
        except Exception as e:            # say what happened, not how
            reason = "the address did not resolve"
            text = str(e).lower()
            if "timed out" in text or "timeout" in text:
                reason = "it did not answer in time"
            elif "refused" in text:
                reason = "the connection was refused"
            elif "certificate" in text or "ssl" in text:
                reason = "the certificate was not accepted"
            elif "unreachable" in text or "network" in text:
                reason = "the network is unreachable"
            raise FailSignal(f"cannot reach '{url}': {reason}")
        return _json.dumps(reply, ensure_ascii=False)
    if name in ("fetch", "post", "fetch_status"):
        import urllib.request
        import urllib.error
        url = str(args[0])
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        headers = {"User-Agent": f"velaris/{VERSION}"}
        data = None
        if name == "post":
            body = str(args[1])
            data = body.encode("utf-8")
            headers["Content-Type"] = (
                "application/json" if body.lstrip()[:1] in "{["
                else "text/plain; charset=utf-8")
        allow_host(url, name, line)
        opener = guarded_opener(url)         # may refuse a proxy (E317)
        count_op("net", name, line)
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with opener.open(req, timeout=10) as resp:
                if name == "fetch_status":
                    return int(resp.status)
                return resp.read(1 << 20).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:      # a real answer, not silence
            if name == "fetch_status":
                return int(e.code)
            raise FailSignal(f"'{url}' answered with status {e.code}")
        except _RedirectRefused as e:     # sent somewhere it may not go
            _note_redirect(line)
            raise FailSignal(f"'{url}' redirected to '{e.target}', which "
                             f"this run does not allow: {e.why}")
        except Exception:
            raise FailSignal(f"cannot reach '{url}'")
    if name == "args":
        return list(_state.PROGRAM_ARGS)
    if name == "log":
        # one line per call, whatever the value holds (8.3): a line feed, a
        # carriage return, an escape or a NUL is written as an escape, so a
        # value cannot forge a line of the log
        print(log_line(to_text(args[0])), file=sys.stderr)
        return None
    if name == "env":
        return os.environ.get(str(args[0]), str(args[1]))
    if name == "exit_with":
        code = int(args[0])
        if not 0 <= code <= 255:
            raise VelarisError("E408",
                f"an exit code must be between 0 and 255, not {code}",
                line, fixes=["0 means success; anything else means "
                             "something went wrong"])
        raise SystemExit(code)
    if name == "read_line":
        got = sys.stdin.readline()
        return got.rstrip("\n")
    if name == "format":
        template = str(args[0])
        pieces = template.split("{}")
        holes = len(pieces) - 1
        given = len(args) - 1
        if holes != given:
            raise VelarisError("E406",
                f"format has {holes} placeholder(s) but got {given} "
                f"value(s)", line,
                fixes=[f"pass exactly {holes} value(s) after the text",
                       "each {} in the text takes one value"])
        out = pieces[0]
        for piece, val in zip(pieces[1:], args[1:]):
            out += to_text(val) + piece
        return out
    if name == "now":
        # --freeze-time fixes the instant; it is not a grant, so the clock
        # effect and its budget were already checked above (8.0)
        return _state.FROZEN_TIME if _state.FROZEN_TIME is not None else int(_time.time())
    if name == "random":
        n = args[0]
        if n <= 0:
            raise VelarisError("E405", "random(n) needs n greater than 0", line,
                              fixes=["pass a positive number, e.g. random(6)"])
        # --seed makes the sequence reproducible; still needs `rand` (8.0)
        return _state._RNG.randrange(n) if _state._RNG is not None else _rand.randrange(n)


# how many calls and loop turns pass between two looks for a stop file (8.3)
STOP_EVERY = 256


def build_runtime(funcs: list[Function], native: dict[Any, Any] | None = None) -> dict[str, Any]:
    native = native or {}
    table = {f.name: f for f in funcs}

    # builtins from 4.3 on give way to the program's own function of the
    # same name; '@name' is a library's call bound to the builtin
    hidden = NEW_BUILTINS & set(table)

    # a stop asked for from outside (8.3, velaris eval): the file the parent
    # makes is looked for every STOP_EVERY calls and loop turns, so a program
    # that cooperates - one running interpreted, not blocked in Python - stops
    # at the next of either, with E615, which it cannot catch. STOP_FILE is
    # None everywhere but eval's worker, and then nothing is looked for.
    stop_file = _state.STOP_FILE
    stop_ticks = [0]

    def stop_point(line: int) -> None:
        stop_ticks[0] += 1
        if (stop_file is not None and stop_ticks[0] % STOP_EVERY == 0
                and os.path.exists(stop_file)):
            raise VelarisError(
                "E615", "this run was asked to stop from outside, and "
                "stopped here", line,
                fixes=["whoever runs it asked it to stop; its receipt "
                       "records the stop"])

    def call(name: str, args: list[Any], line: int) -> Any:
        if name in ("all_of", "any_of"):
            xs, p = args
            hits = (call_function(p, [v], line) for v in xs)
            return all(hits) if name == "all_of" else any(hits)
        if name in BUILTINS and name not in hidden:
            return run_builtin(name, args, line)
        if name[0] == "@":
            return run_builtin(name[1:], args, line)
        if name in native:                 # machine code, C-like speed
            if _state.TRACE["on"]:                # still visible when tracing
                fnn = table.get(name)
                trace_enter(name + " (native)",
                            fnn.params if fnn else [], args,
                            getattr(fnn, "secret_params", frozenset()))
                out = native[name](*args)
                trace_leave(name + " (native)", out,
                            secret=getattr(fnn, "secret_result", False))
                return out
            return native[name](*args)
        fn = table.get(name)
        if fn is None:
            raise unknown_function(name, line, table)
        return call_function(fn, args, line)

    depth = [0]
    DEPTH_LIMIT = 2000        # deep enough for real recursion, shallow
                              # enough to report before Python's own
                              # stack gives out with a traceback
    # each Velaris frame costs several Python frames, so lift Python's
    # ceiling high enough that OUR limit is the one that fires
    if sys.getrecursionlimit() < DEPTH_LIMIT * 12:
        try:
            sys.setrecursionlimit(DEPTH_LIMIT * 12)
        except Exception:
            pass

    def call_function(fn: Any, args: list[Any], line: int) -> Any:
        caught = None
        if isinstance(fn, Bound):
            caught, fn = fn.caught, fn.fn
        name = fn.name
        if stop_file is not None:
            stop_point(line)
        if depth[0] >= DEPTH_LIMIT:
            raise VelarisError("E609",
                f"'{name}' called itself {DEPTH_LIMIT} deep - this looks "
                f"like recursion that never stops", line,
                fixes=["make sure the recursive case moves toward the "
                       "base case",
                       "or rewrite it as a loop"])
        if len(args) != len(fn.params):
            raise VelarisError("E401",
                f"'{name}' expects {len(fn.params)} argument(s) but got {len(args)}",
                line, fixes=[f"pass exactly {len(fn.params)} argument(s)"])
        env = {p[0]: a for p, a in zip(fn.params, args)}
        if caught:
            for cn, cv in caught.items():
                env.setdefault(cn, cv)     # values carried in, read once
                                           # when the value was made
        # the snapshot exists so promises can see entry values; a
        # function with no promises was copying its whole scope on
        # every single call for nothing
        entry = dict(env) if (fn.requires or fn.ensures) else env

        # a promise may talk about a secret - `requires length(key) > 0`
        # is exactly the kind of thing to promise - so the message a
        # broken one prints redacts the values whose type is secret (6.0)
        hush: set[str] | frozenset[str] = getattr(fn, "secret_params", frozenset())
        hush_result = getattr(fn, "secret_result", False)

        def vals(expr: Any, extra: Any = None) -> str:
            scope = dict(entry)
            if extra is not None:
                scope["result"] = extra[0]
            names = sorted(n for n in expr_vars(expr) if n in scope)
            return ", ".join(
                f"{n} = " + (REDACTED if (n in hush or
                                          (n == "result" and hush_result))
                             else f"{scope[n]}")
                for n in names)

        for expr, cline in fn.requires:
            if not eval_(expr, dict(entry)):
                raise VelarisError("E600",
                    f"broken promise: {nice_name(name)} requires "
                    f"{expr_str(expr)}  ({vals(expr)})", cline,
                    fixes=["check the value before calling this function",
                           "or loosen the promise if it is too strict"])

        retval = None
        trace_enter(name, fn.params, args, hush)
        depth[0] += 1
        try:
            for stmt in fn.body:
                run(stmt, env)
        except ReturnSignal as r:
            retval = r.value
        except FailSignal as f:
            trace_leave(name, None, failed=str(f.reason))
            raise
        except VelarisError as e:
            trace_leave(name, None, failed=f"[{e.code}] {e.message}")
            raise blame(fn, e)
        finally:
            depth[0] -= 1
        trace_leave(name, retval, secret=hush_result)

        for expr, cline in fn.ensures:
            check_env = dict(entry)
            check_env["result"] = retval
            if not eval_(expr, check_env):
                raise VelarisError("E601",
                    f"broken promise: {nice_name(name)} ensures "
                    f"{expr_str(expr)}  ({vals(expr, (retval,))})", cline,
                    fixes=["the code does not keep this promise - fix the code",
                           "or fix the promise if it is wrong"])
        return retval

    def run(node: Any, env: Any) -> None:
        cls = node.__class__
        if cls is Assign:               # the body of every loop
            env[node.name] = eval_(node.value, env)
            return
        if cls is Let:
            env[node.name] = eval_(node.value, env)
            return
        if cls is Let:
            env[node.name] = eval_(node.value, env)
        elif cls is Return:
            raise ReturnSignal(None if node.value is None else eval_(node.value, env))
        elif cls is ExprStmt:
            eval_(node.expr, env)
        elif cls is FailStmt:
            raise FailSignal(eval_(node.value, env))
        elif cls is Check:
            try:
                val = eval_(node.subject, env)
            except FailSignal as f:
                env[node.fail_name] = f.reason
                for s in node.fail_body:
                    run(s, env)
            else:
                if node.ok_name is not None:
                    env[node.ok_name] = val
                for s in node.ok_body:
                    run(s, env)
        elif cls is If:
            branch = node.then if eval_(node.cond, env) else node.other
            for s in branch:
                run(s, env)
        elif cls is While:
            def check_invariants() -> None:
                for inv_expr, iline in node.invariants:
                    if not eval_(inv_expr, env):
                        names = sorted(n for n in expr_vars(inv_expr)
                                       if n in env)
                        vals = ", ".join(f"{n} = {to_text(env[n])}"
                                         for n in names)
                        raise VelarisError("E704",
                            f"loop broke its promise: invariant "
                            f"{expr_str(inv_expr)}  ({vals})", iline,
                            fixes=["fix the loop body so the promise holds "
                                   "on every step",
                                   "or fix the invariant if it is wrong"])
            check_invariants()
            while eval_(node.cond, env):
                if stop_file is not None:
                    stop_point(node.line)
                for s in node.body:
                    run(s, env)
                check_invariants()
        elif cls is Assign:
            env[node.name] = eval_(node.value, env)

    _hot = (Num, FloatNum, Str, Bool)

    class Bound:
        """A function value carrying the values it was made with."""
        __slots__ = ("fn", "caught")

        def __init__(self, fn: Any, caught: Any) -> None:
            self.fn = fn
            self.caught = caught

    def eval_(node: Any, env: Any) -> Any:
        cls = node.__class__
        if cls is Closure:
            fn = table[node.name]
            caught = {n: env[n] for n in node.free if n in env}
            return Bound(fn, caught) if caught else fn
        if cls is Var:                  # the commonest node by far
            name = node.name
            if name in env:
                return env[name]
            if name in table:
                return table[name]
            raise VelarisError("E402", f"unknown variable '{name}'",
                               node.line,
                               fixes=[f"declare it first: let {name} = ..."])
        if cls in _hot:                 # literals: the value is the node
            return node.value
        if cls is Num:
            return node.value
        if cls is FloatNum:
            return node.value
        if cls is Neg:
            v = -eval_(node.value, env)
            if v.__class__ is float:
                return v
            # -(the smallest Int or amount) does not fit in 64 bits: E407.
            # Until 8.2 an Int came back as 2**63 here, and native code
            # wrapped it to itself, so a promise proven about -n could break
            # when it ran (advisory-int-negation.md)
            return checked_int(v, "-", node.line)
        if cls is TryExpr:
            return eval_(node.value, env)   # a failure keeps rising
        if cls is Str:
            return node.value
        if cls is Bool:
            return node.value
        if cls is Var:
            if node.name in env:
                return env[node.name]
            if node.name in table:
                return table[node.name]        # a function, as a value
            raise VelarisError("E402", f"unknown variable '{node.name}'", node.line,
                              fixes=[f"declare it first: let {node.name} = ..."])
        if cls is Call:
            if node.name in env and isinstance(env[node.name],
                                               (Function, Bound)):
                return call_function(env[node.name],
                                     [eval_(a, env) for a in node.args],
                                     node.line)
            return call(node.name, [eval_(a, env) for a in node.args], node.line)
        if cls is Not:
            return not eval_(node.value, env)
        if cls is RecordLit:
            return RecordValue(node.name,
                               {f: eval_(v, env) for f, v in node.fields})
        if cls is FieldGet:
            return eval_(node.obj, env).fields[node.field]
        if cls is ListLit:
            return [eval_(i, env) for i in node.items]
        if cls is MapLit:
            return {eval_(k, env): eval_(v, env) for k, v in node.entries}
        if cls is BinOp:
            if node.op == "and":
                return eval_(node.left, env) and eval_(node.right, env)
            if node.op == "or":
                return eval_(node.left, env) or eval_(node.right, env)
            l, r = eval_(node.left, env), eval_(node.right, env)  # noqa: E741
            if node.op == "+":
                if isinstance(l, str) or isinstance(r, str):
                    return to_text(l) + to_text(r)
                return checked_int(l + r, "+", node.line)
            if node.op == "-":
                return checked_int(l - r, "-", node.line)
            if node.op == "*":
                return checked_int(l * r, "*", node.line)
            if node.op == "/":
                if r == 0:
                    raise VelarisError("E403", "division by zero", node.line,
                                      fixes=["check the divisor before dividing"])
                if isinstance(l, float):
                    return l / r
                # the smallest Int divided by -1 is 2**63, which does not fit
                return checked_int(l // r, "/", node.line)
            if node.op == "%":
                if r == 0:
                    raise VelarisError("E403", "remainder by zero", node.line,
                                      fixes=["check the divisor before using %"])
                return l % r
            if node.op == "==":
                return l == r
            if node.op == "!=":
                return l != r
            if node.op == "<":
                return l < r
            if node.op == ">":
                return l > r
            if node.op == "<=":
                return l <= r
            return l >= r

    return {"table": table, "call": call, "run": run, "eval": eval_}


# Set on the thread _run_on_big_stack starts, so work already there - a
# command, then the run it makes - does not start another (8.2).
_BIG_STACK = threading.local()


def _needs_big_stack() -> bool:
    """CPython before 3.11 uses much more C stack per Python frame, so with
    the raised recursion limit build_runtime sets, a deeply recursive Velaris
    program can overflow the C stack (a segfault on Windows) before the
    interpreter's DEPTH_LIMIT guard fires E609. 3.11+ handles the same depth
    in place. Running on a worker thread perturbs a memory cap's accounting,
    so we only take that path where the guard would otherwise not be
    reached. 7.1.2."""
    return sys.version_info < (3, 11)


def _run_on_big_stack(fn: Callable[[], _R]) -> _R:
    """On CPython < 3.11, run fn on a thread with a larger C stack and
    re-raise whatever it raised (a VelarisError, a FailSignal, or the
    SystemExit exit_with throws), so a runaway recursion reaches E609 rather
    than overflowing the C stack. Elsewhere - and if the platform will not
    size a thread stack - run in place, which leaves the memory-cap path
    untouched. 7.1.2."""
    if not _needs_big_stack() or getattr(_BIG_STACK, "on", False):
        return fn()
    box: dict[Any, Any] = {}

    def worker() -> None:
        _BIG_STACK.on = True
        try:
            box["value"] = fn()
        except BaseException as e:          # VelarisError/FailSignal/SystemExit
            box["error"] = e

    # Windows CPython rejects very large thread stacks (256 MiB raises on
    # 3.10), so try descending sizes and take the first the platform accepts;
    # 64 MiB holds the ~24000 Python frames DEPTH_LIMIT allows, verified on
    # 3.10.
    prev = None
    for size in (64 * 1024 * 1024, 32 * 1024 * 1024):
        try:
            prev = threading.stack_size(size)
            break
        except (ValueError, RuntimeError, OverflowError):
            continue
    else:
        return fn()                         # cannot size a stack: run here
    started = False
    try:
        t = threading.Thread(target=worker)
        try:
            t.start()
            started = True
        except RuntimeError:
            # "can't start new thread": a big stack can exceed the address
            # space a memory cap (RLIMIT_AS) leaves, especially with llvmlite
            # loaded. Run in place - the big stack is a best-effort guard,
            # never a requirement.
            started = False
        if started:
            t.join()
    finally:
        try:
            threading.stack_size(prev or 0)
        except (ValueError, RuntimeError, OverflowError):
            pass
    if not started:
        return fn()
    if "error" in box:
        raise box["error"]
    return cast(_R, box.get("value"))


def _on_big_stack(fn: Callable[_P, _R]) -> Callable[_P, _R]:
    """fn, run where _run_on_big_stack runs things. From 8.2 a whole command,
    and a check, an audit or a run made in this process, run there on
    CPython before 3.11: a program nested as deep as the parser allows
    (E102) overflowed the main thread's stack in the parser on 3.10 for
    Windows, and the process ended with no error at all."""
    @functools.wraps(fn)
    def on_big_stack(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        return _run_on_big_stack(lambda: fn(*args, **kwargs))
    return on_big_stack


def interpret(funcs: list[Function], native: dict[Any, Any] | None = None) -> None:
    rt = build_runtime(funcs, native)
    if "main" not in rt["table"]:
        raise VelarisError("E400", "no 'main' function found", 1,
                          fixes=["add: fn main() uses io { ... }"])
    _run_on_big_stack(
        lambda: rt["call"]("main", [], rt["table"]["main"].line))
