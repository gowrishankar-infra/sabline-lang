#!/usr/bin/env python3
"""A test for every line of a guarantee the monthly mutation run found
untested (8.3 item 12).

check_mutants.py changes the functions a guarantee rests on, one small
change at a time, and runs the suites that should notice. Run 34978389207
(at 9972e41) made 521 mutants, ran 191 of them in its 90 minutes, and 67
survived: 67 changes to sabline/budget.py, effects.py, prover.py and
wrappers.py that every killer suite passed. The rule is that a survivor in
a guarantee-bearing function gets a test in the release. This suite is
those tests. Each case below fails with its mutant applied and passes
without it - checked against the mutants themselves with

    python check_mutants.py --killers check_mutant_kills.py \\
        --only budget:428:return-none --only ...

and check_mutants.py now lists this suite among the killers of the four
modules. What it holds:

  * a server's ceiling (Budget.covers, _fs_grant_covers,
    _net_grant_covers, _host_matches) refuses every effect, module, count,
    path, direction, host, port and wildcard it does not grant, naming
    what it refused, and lets through what it does grant
  * a budget that names something that is not an effect is refused, and
    the refusal names it (Budget.parse)
  * a credential location is refused to a plain read_file even when its
    path is granted, and to read_file_secret unless a grant names it or a
    path within its root - not a broad grant above it, not a sibling file
    (allow_path, with HOME and USERPROFILE pointed at a scratch directory)
  * an ambient HTTP_PROXY the net grants do not cover is refused with E317
    naming its host and port; a granted one is the only proxy used; a host
    NO_PROXY exempts uses none (_proxy_for, guarded_opener)
  * a scheme that is not http(s) is refused naming the scheme; a module
    that does not import fails saying so; an amount one past the 64-bit
    range is refused and one at its edge is not (host_refusal,
    _ffi_resolve, checked_int)
  * the effect checker refuses a function named like an old builtin
    (E204) and not one named like a new one, a pure function that calls a
    builtin through a local that is not a function value, a promise that
    calls a function with effects (E310), and an effect name that does not
    exist (E300), and its E300 names the callee and what the caller
    declares (check_effects)
  * two amounts in different currencies clash inside a Secret and inside
    maps, and a list is not mistaken for a function type (currency_clash)
  * the prover leaves to runtime a counterexample that rests on a
    summarised record, list or list of lists, on a sum or an uninterpreted
    function Z3 knows nothing of, or on an index a summarised call gave;
    it proves a correct loop with a written invariant and one that
    mentions an uninterpreted function; it shows a counterexample's values
    as numbers; an invariant Z3 could not decide is never proven; and a
    promise past a comparison of two maps is never proven (has_fresh,
    uninterpreted_in, prove_invariant, prove_bounds, to_z3)

The test written for prover.py 558 (flip-bool) found a Goal A break in
the prover as it was, not only in the mutant: == and != on two maps, lists
of lists, lists of Bool or Text, compared the prover's Python objects, and
promises past such a branch came back proven. 8.3 leaves those to runtime
(check_prover_lies.py, COMPARED; the CHANGELOG's 8.3 entry). With that
fixed, nothing but a Z3 expression reaches uninterpreted_in from a program
that type-checks, and that mutant joined the equivalent ones below.

Seven survivors change nothing a caller can observe, so no test can kill
them. Line numbers are those of 9972e41, where the run found them. Six
turn `return False` into `return None` where every caller only tests the
result's truth: budget.py 518 (_fs_grant_covers) and 540
(_net_grant_covers), whose one caller is `any(...)` in Budget.covers;
effects.py 149 (calls_a_value, a closure called only as `if ...:` at
lines 156 and 229); prover.py 558 (uninterpreted_in for a non-expression,
read only through `or` and `any(...)` at 562, 1167 and 1168) - and its
flip-bool too, since 8.3, as above; wrappers.py
26 (currency_clash, whose callers are all `if currency_clash(...)` in
checker.py or its own `and`); and wrappers.py 157 (carries_secret of a
function type, read through `if`, `not`, `or`, `any` and a set filter in
checker.py and wrappers.py, and stored as Function.secret_result, which
runtime.py reads only as `secret=` of trace_leave and in `and`). The
package re-exports these names, but STABILITY.md covers none of them.

The prover's cases need z3; without it they are skipped, each saying so,
and everything else runs.

    python check_mutant_kills.py
"""
from __future__ import annotations

import contextlib
import io
import os
import re
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sabline  # noqa: E402
from suite_dirs import isolate  # noqa: E402
from sabline.budget import (  # noqa: E402
    Budget,
    BudgetError,
    _ffi_resolve,
    _host_matches,
    _proxy_for,
    allow_path,
    checked_int,
    guarded_opener,
    host_refusal,
)
from sabline.errors import SablineError  # noqa: E402
from sabline.tables import INT_MAX  # noqa: E402
from sabline.values import FailSignal, MoneyValue  # noqa: E402

try:
    import z3  # noqa: F401
    HAVE_Z3 = True
    del z3
except ImportError:
    HAVE_Z3 = False

WORK = isolate("check_mutant_kills")

PASS = [0]
FAIL = [0]
SKIP = [0]


def say(text: str) -> None:
    """ASCII only: a Windows CI console is cp1252."""
    print(text.encode("ascii", "backslashreplace").decode("ascii"))


def ok(label: str, good: bool, detail: str = "") -> None:
    if good:
        PASS[0] += 1
        say(f"  ok    {label}")
    else:
        FAIL[0] += 1
        say(f"  WRONG {label}" + (f"\n          {detail}" if detail else ""))


def holds(label: str, test: Callable[[], tuple[bool, str]]) -> None:
    """ok(label, ...) of what `test` returns - (good, what was seen) - with
    an exception counted as wrong: a mutant may raise where the code
    returns, and that is a failure to report, not a traceback."""
    try:
        good, seen = test()
    except Exception as e:  # noqa: BLE001 - any exception is a wrong answer
        ok(label, False, f"raised {type(e).__name__}: {e}")
        return
    ok(label, good, seen)


def skip(label: str, why: str) -> None:
    SKIP[0] += 1
    say(f"  skip  {label} ({why})")


# ---- helpers -----------------------------------------------------------------

@contextlib.contextmanager
def environ(values: dict[str, str | None]) -> Iterator[None]:
    """Set (or, for None, remove) environment variables, and put every one
    back afterwards. Removals come first: on Windows the names are not
    case-sensitive, so removing http_proxy after setting HTTP_PROXY would
    remove the one just set."""
    saved = {name: os.environ.get(name) for name in values}
    try:
        for name, value in values.items():
            if value is None:
                os.environ.pop(name, None)
        for name, value in values.items():
            if value is not None:
                os.environ[name] = value
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
        for name, value in saved.items():
            if value is not None:
                os.environ[name] = value


@contextlib.contextmanager
def budget(spec: str) -> Iterator[None]:
    """Install a budget for the duration, and the one before it after."""
    saved = Budget.snapshot()
    try:
        Budget.parse(spec).install()
        yield
    finally:
        Budget.restore(saved)


def refusal(ceiling: str, asked: str) -> str | None:
    return Budget.parse(ceiling).covers(Budget.parse(asked))


def refuses(label: str, ceiling: str, asked: str, fact: str) -> None:
    """The ceiling refuses `asked`, and the sentence names `fact`."""
    def test() -> tuple[bool, str]:
        why = refusal(ceiling, asked)
        return (why is not None and fact in why,
                f"ceiling {ceiling!r}, asked {asked!r}: covers gave {why!r}, "
                f"wanted a refusal naming {fact!r}")
    holds(label, test)


def covers(label: str, ceiling: str, asked: str) -> None:
    def test() -> tuple[bool, str]:
        why = refusal(ceiling, asked)
        return (why is None,
                f"ceiling {ceiling!r}, asked {asked!r}: refused: {why!r}")
    holds(label, test)


def raises(action: Callable[[], Any], code: str, fact: str) -> tuple[bool, str]:
    """(action raised SablineError `code` naming `fact`, what it did)."""
    try:
        got = action()
    except SablineError as e:
        return (e.code == code and fact in e.message,
                f"raised {e.code}: {e.message[:160]}; wanted {code} "
                f"naming {fact!r}")
    return False, f"returned {got!r}; wanted {code} naming {fact!r}"


PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY",
              "http_proxy", "https_proxy", "no_proxy", "all_proxy",
              "REQUEST_METHOD")


def proxies(**values: str) -> dict[str, str | None]:
    """No proxy variable set but the ones given."""
    out: dict[str, str | None] = {name: None for name in PROXY_VARS}
    out.update(values)
    return out


# ---- Budget.covers: the door's ceiling ---------------------------------------

def ceiling_cases() -> None:
    say("a server's ceiling (Budget.covers)")
    refuses("[C1] an io ceiling refuses fs, naming it", "io", "io,fs", "fs")
    refuses("[C2] an ffi:math ceiling refuses plain ffi", "ffi:math", "ffi",
            "named modules only")
    covers("[C3] a plain ffi ceiling covers ffi:json", "ffi", "ffi:json")
    refuses("[C4] an fs@5 ceiling refuses fs with no count", "fs@5", "fs",
            "at most 5")
    covers("[C5] an fs@5 ceiling covers fs@3", "fs@5", "fs@3")
    refuses("[C6] an fs@5 ceiling refuses fs@9", "fs@5", "fs@9", "at most 5")
    refuses("[C7] a net:a.test ceiling refuses net:b.test, naming it",
            "net:a.test", "net:b.test", "net:b.test")
    refuses("[C8] a net@5 ceiling refuses net with no count", "net@5", "net",
            "at most 5")
    covers("[C9] a net@5 ceiling covers net@3", "net@5", "net@3")
    covers("[C10] a plain net ceiling covers plain net", "net", "net")
    refuses("[C11] a net@5 ceiling refuses net@9", "net@5", "net@9",
            "at most 5")

    inside = WORK / "granted"
    other = WORK / "elsewhere"
    for d in (inside, other):
        d.mkdir(exist_ok=True)
    refuses("[C12] an fs:read:<dir> ceiling refuses fs:read of any path",
            f"fs:read:{inside}", "fs:read", "fs:read")
    covers("[C13] a plain fs:read ceiling covers fs:read:<dir>", "fs:read",
           f"fs:read:{inside}")
    refuses("[C14] an fs:read:<dir> ceiling refuses fs:read:<another dir>",
            f"fs:read:{inside}", f"fs:read:{other}", "fs:read:")
    refuses("[C15] an fs:read ceiling refuses fs:write", "fs:read",
            "fs:write", "fs:write")
    covers("[C16] an fs:read:<dir> ceiling covers fs:read:<dir>/sub",
           f"fs:read:{inside}", f"fs:read:{inside / 'sub'}")

    covers("[C17] a net:a.test ceiling covers net:a.test:443", "net:a.test",
           "net:a.test:443")
    refuses("[C18] a net:a.test:443 ceiling refuses net:a.test:80, naming "
            "the port", "net:a.test:443", "net:a.test:80", "a.test:80")
    refuses("[C19] a net:*.a.test ceiling refuses net:*.b.test",
            "net:*.a.test", "net:*.b.test", "*.b.test")
    covers("[C20] a net:*.a.test ceiling covers net:*.a.test", "net:*.a.test",
           "net:*.a.test")
    covers("[C21] a net:a.test ceiling covers net:a.test", "net:a.test",
           "net:a.test")
    refuses("[C22] a net:a.test ceiling refuses net:*.a.test", "net:a.test",
            "net:*.a.test", "*.a.test")
    covers("[C23] a net:*.a.test ceiling covers net:api.a.test",
           "net:*.a.test", "net:api.a.test")
    refuses("[C24] a net:*.a.test ceiling refuses net:.a.test (no label "
            "before the dot)", "net:*.a.test", "net:.a.test", ".a.test")
    covers("[C25] an fs@5 ceiling covers fs@5, a count equal to its own",
           "fs@5", "fs@5")
    covers("[C26] a net@5 ceiling covers net@5, a count equal to its own",
           "net@5", "net@5")


# ---- hosts, schemes, budgets, modules, ranges --------------------------------

def host_cases() -> None:
    say("hosts, schemes, budgets, modules and ranges")
    holds("[H1] *.example.com does not match '.example.com'",
          lambda: (_host_matches("*.example.com", ".example.com") is False,
                   "it matched"))
    holds("[H2] *.example.com matches api.example.com",
          lambda: (_host_matches("*.example.com", "api.example.com") is True,
                   "it did not match"))

    def empty_label() -> tuple[bool, str]:
        with budget("net:*.example.com"):
            why = host_refusal("http://.example.com/")
        return why is not None, f"host_refusal gave {why!r}"
    holds("[H3] under net:*.example.com a request to http://.example.com/ "
          "is refused", empty_label)

    def scheme() -> tuple[bool, str]:
        why = host_refusal("ftp://files.test/x")
        return why is not None and "'ftp'" in why, f"host_refusal gave {why!r}"
    holds("[H4] an ftp:// URL is refused, naming the scheme 'ftp'", scheme)

    def unknown(spec: str, fact: str) -> Callable[[], tuple[bool, str]]:
        def test() -> tuple[bool, str]:
            try:
                got = Budget.parse(spec)
            except BudgetError as e:
                return fact in str(e), f"BudgetError: {e}"
            return False, f"parsed, as {got.spec()!r}"
        return test
    holds("[B1] the budget 'io,teleport' is refused, naming 'teleport'",
          unknown("io,teleport", "'teleport'"))
    holds("[B2] 'all' among other grants is refused as the shorthand it is",
          unknown("io,all", "on its own"))

    def no_module() -> tuple[bool, str]:
        with budget("ffi"):
            try:
                got = _ffi_resolve("sabline_no_such_module_zz", "f", "py", 1)
            except FailSignal as f:
                return ("cannot import" in str(f.reason),
                        f"failed with: {f.reason}")
        return False, f"returned {got!r}"
    holds("[F1] a module that does not import fails saying it cannot be "
          "imported", no_module)

    holds("[R1] an amount of INT_MAX minor units is in range",
          lambda: (checked_int(MoneyValue(INT_MAX, "USD"), "+", 1).units
                   == INT_MAX, "it was refused"))
    holds("[R2] an amount of INT_MAX + 1 minor units is refused (E407)",
          lambda: raises(lambda: checked_int(MoneyValue(INT_MAX + 1, "USD"),
                                             "+", 1), "E407", "amount"))
    holds("[R3] an amount of INT_MIN minor units is in range",
          lambda: (checked_int(MoneyValue(sabline.INT_MIN, "USD"), "-",
                               1).units == sabline.INT_MIN, "it was refused"))
    holds("[R4] an amount of INT_MIN - 1 minor units is refused (E407)",
          lambda: raises(lambda: checked_int(
              MoneyValue(sabline.INT_MIN - 1, "USD"), "-", 1), "E407",
              "amount"))


# ---- credential locations (allow_path) ---------------------------------------

def credential_cases() -> None:
    say("credential locations (allow_path)")
    home = WORK / "home"
    aws = home / ".aws"
    aws.mkdir(parents=True, exist_ok=True)
    cred = aws / "credentials"
    config = aws / "config"
    cred.write_text("[default]\n", encoding="utf-8")
    config.write_text("[default]\n", encoding="utf-8")
    real = os.path.normcase(os.path.realpath(str(cred)))
    at_home = {"HOME": str(home), "USERPROFILE": str(home)}

    def attempt(grant: str, what: str) -> Callable[[], Any]:
        def action() -> Any:
            with environ(dict(at_home)), budget(grant):
                return allow_path("read", str(cred), what, 1)
        return action

    def allowed(grant: str) -> Callable[[], tuple[bool, str]]:
        def test() -> tuple[bool, str]:
            got = attempt(grant, "read_file_secret")()
            return got == real, f"returned {got!r}"
        return test

    holds("[P1] read_file of ~/.aws/credentials is refused (E318) even with "
          "fs:read:~/.aws granted",
          lambda: raises(attempt(f"fs:read:{aws}", "read_file"), "E318",
                         "a plain read"))
    holds("[P2] read_file_secret of it is allowed with fs:read:~/.aws",
          allowed(f"fs:read:{aws}"))
    holds("[P3] read_file_secret of it is allowed with the file itself "
          "granted", allowed(f"fs:read:{cred}"))
    holds("[P4] read_file_secret of it is refused (E318) with only "
          "fs:read:~/.aws/config granted",
          lambda: raises(attempt(f"fs:read:{config}", "read_file_secret"),
                         "E318", "credential"))
    holds("[P5] read_file_secret of it is refused (E318) with fs:read:~ "
          "granted, a broad grant above it",
          lambda: raises(attempt(f"fs:read:{home}", "read_file_secret"),
                         "E318", "credential"))
    holds("[P6] read_file_secret of it is refused (E318) with plain fs",
          lambda: raises(attempt("fs", "read_file_secret"), "E318",
                         "credential"))


# ---- ambient proxies (_proxy_for, guarded_opener) ----------------------------

def proxy_cases() -> None:
    say("ambient proxies (_proxy_for, guarded_opener)")
    proxy = "http://proxy.test:3128"

    def found(extra: dict[str, str], want: str | None) -> Callable[[], tuple[bool, str]]:
        def test() -> tuple[bool, str]:
            with environ(proxies(HTTP_PROXY=proxy, **extra)):
                got = _proxy_for("http://api.test/data")
            return got == want, f"_proxy_for gave {got!r}, wanted {want!r}"
        return test
    holds("[X1] with HTTP_PROXY set, a request to api.test goes through it",
          found({}, proxy))
    holds("[X2] a host NO_PROXY names uses no proxy",
          found({"NO_PROXY": "api.test"}, None))

    def ungranted() -> tuple[bool, str]:
        with environ(proxies(HTTP_PROXY=proxy)), budget("net:api.test"):
            return raises(lambda: guarded_opener("http://api.test/data"),
                          "E317", "proxy.test:3128")
    holds("[X3] a proxy outside the net grants is refused (E317), naming "
          "proxy.test:3128", ungranted)

    def granted() -> tuple[bool, str]:
        import urllib.request
        with environ(proxies(HTTP_PROXY=proxy)), \
                budget("net:api.test,net:proxy.test:3128"):
            opener = guarded_opener("http://api.test/data")
        used = [getattr(h, "proxies", None) for h in opener.handlers
                if isinstance(h, urllib.request.ProxyHandler)]
        return used == [{"http": proxy}], f"proxy handlers: {used!r}"
    holds("[X4] a granted proxy is the one proxy the opener uses", granted)


# ---- the effect checker (check_effects) --------------------------------------

def problems(source: str, prove: bool = False) -> sabline.CheckResult:
    """check() in this process, the prover's notes kept off the console."""
    with contextlib.redirect_stderr(io.StringIO()):
        return sabline.check(source.lstrip(), prove=prove, timeout=None,
                             max_memory_mb=None)


def refused_with(label: str, source: str, code: str, fact: str = "",
                 prove: bool = False) -> None:
    def test() -> tuple[bool, str]:
        got = problems(source, prove)
        seen = [(p.code, p.message) for p in got.problems]
        return (any(c == code and fact in m for c, m in seen),
                f"wanted {code}" + (f" naming {fact!r}" if fact else "")
                + f"; got {[(c, m[:120]) for c, m in seen]}")
    holds(label, test)


def compiles(label: str, source: str, prove: bool = False,
             proven: tuple[str, ...] = (), runtime: tuple[str, ...] = ()) -> None:
    """No problem at all, `proven` among the proven and `runtime` left to
    runtime (and so not proven)."""
    def test() -> tuple[bool, str]:
        got = problems(source, prove)
        good = (not got.problems
                and all(name in got.proven for name in proven)
                and all(name in got.runtime_checked
                        and name not in got.proven for name in runtime))
        return good, (f"problems {[(p.code, p.message[:120]) for p in got.problems]}, "
                      f"proven {got.proven}, runtime {got.runtime_checked}")
    holds(label, test)


EFFECTS = {
    "shadow_old": '''
fn length(x: Int) -> Int {
    return x
}
fn main() uses io {
    print("hi")
}
''',
    "shadow_new": '''
fn text_of(x: Int) -> Int {
    return x
}
fn main() uses io {
    print(to_text(text_of(1)))
}
''',
    "local_not_a_function": '''
fn helper() -> Int {
    let print = 0
    print("leak")
    return print
}
fn main() uses io {
    print(to_text(helper()))
}
''',
    "local_function_named_print": '''
fn quiet() -> Int {
    return 2
}
fn helper() -> Int {
    let print = quiet
    return print()
}
fn main() uses io {
    print(to_text(helper()))
}
''',
    "env_through_callee": '''
fn touch() uses env {
    let k = env("HOME")
}
fn main() uses io {
    touch()
}
''',
    "pure_prints": '''
fn shout(x: Int) -> Int {
    print("x")
    return x
}
fn main() uses io {
    print(to_text(shout(1)))
}
''',
    "io_reads": '''
fn peek() -> Text or fail uses io {
    return try read_file("a.txt")
}
fn main() uses io {
    print("x")
}
''',
    "promise_with_effect": '''
fn noisy(x: Int) -> Bool uses io {
    print("checked")
    return x > 0
}
fn f(x: Int) -> Int
    requires noisy(x)
{
    return x
}
fn main() uses io {
    print(to_text(f(1)))
}
''',
    "no_such_effect": '''
fn main() uses io, teleport {
    print("hi")
}
''',
}


def effect_cases() -> None:
    say("the effect checker (check_effects)")
    refused_with("[E1] a function named 'length' is refused (E204)",
                 EFFECTS["shadow_old"], "E204", "'length'")
    compiles("[E2] a function named 'text_of', a 4.3 builtin, is allowed",
             EFFECTS["shadow_new"])
    refused_with("[E3] a pure function calling print through 'let print = 0' "
                 "is refused (E300)", EFFECTS["local_not_a_function"], "E300",
                 "'print'")
    compiles("[E4] a pure function calling a pure function held in a local "
             "named print compiles", EFFECTS["local_function_named_print"])
    refused_with("[E5] E300 for a callee needing env names the callee",
                 EFFECTS["env_through_callee"], "E300", "'touch'")
    refused_with("[E6] E300 says a pure function declares no effects",
                 EFFECTS["pure_prints"], "E300", "declares no effects")
    refused_with("[E7] E300 says what a function with effects declares",
                 EFFECTS["io_reads"], "E300", "only declares 'uses io'")
    refused_with("[E8] a requires that calls a function with effects is "
                 "refused (E310)", EFFECTS["promise_with_effect"], "E310",
                 "'noisy'")
    refused_with("[E9] 'uses teleport' is refused (E300), naming it",
                 EFFECTS["no_such_effect"], "E300", "'teleport'")


# ---- currencies (currency_clash) ---------------------------------------------

WRAPPERS = {
    "secret_amounts": '''
fn f(s: Secret of Money of INR) -> Secret of Money of USD {
    return s
}
fn main() uses io {
    print("hi")
}
''',
    "list_for_function": '''
fn f(g: fn() -> Money of USD) -> Int {
    return 0
}
fn main() uses io {
    let xs = [money(1, "INR")]
    print(to_text(f(xs)))
}
''',
    "map_amounts": '''
fn f(m: Map of Text to Money of INR) -> Map of Text to Money of USD {
    return m
}
fn main() uses io {
    print("hi")
}
''',
}


def wrapper_cases() -> None:
    say("currencies (currency_clash)")
    refused_with("[W1] a Secret of Money of INR where a Secret of Money of "
                 "USD is needed is a currency clash (E550)",
                 WRAPPERS["secret_amounts"], "E550", "Money of USD")
    refused_with("[W2] a List of Money of INR passed as fn() -> Money of USD "
                 "is a type mismatch (E501), not a currency clash",
                 WRAPPERS["list_for_function"], "E501", "fn() -> Money of USD")

    def not_clash() -> tuple[bool, str]:
        got = problems(WRAPPERS["list_for_function"])
        codes = [p.code for p in got.problems]
        return "E550" not in codes, f"codes {codes}"
    holds("[W3] ... and says nothing of currencies", not_clash)
    refused_with("[W4] a Map of Text to Money of INR where one of USD is "
                 "needed is a currency clash (E550)", WRAPPERS["map_amounts"],
                 "E550", "Money of USD")


# ---- the prover (has_fresh, uninterpreted_in, prove_*) ------------------------

PROVER = {
    "record_summary": '''
record P {
    x: Int
}
fn mk(n: Int) -> P
    ensures result.x == n
{
    return P(x: n)
}
fn f(n: Int) -> P
    ensures n > 0
{
    return mk(n)
}
fn main() uses io {
    print(to_text(f(1).x))
}
''',
    "list_summary": '''
fn g(n: Int) -> List of Money of USD {
    return [money(n, "USD")]
}
fn f(n: Int) -> List of Money of USD
    ensures n > 0
{
    return g(n)
}
fn main() uses io {
    print(to_text(length(f(1))))
}
''',
    "grid_summary": '''
fn g(n: Int) -> List of Money of USD {
    return [money(n, "USD")]
}
fn f(rows: List of List of Money of USD, n: Int) -> List of List of Money of USD
    ensures n > 0
{
    return push(rows, g(n))
}
fn main() uses io {
    print(to_text(length(f([[money(1, "USD")]], 1))))
}
''',
    "sum_never_given": '''
fn sum_one(xs: List of Money of USD) -> Int
    requires length(xs) == 1
    ensures result == units_of(get(xs, 0))
{
    return units_of(xs)
}
fn main() uses io {
    print(to_text(sum_one([money(5, "USD")])))
}
''',
    "code_at_result": '''
fn code(t: Text, i: Int) -> Int
    ensures result >= 0
{
    return code_at(t, i)
}
fn main() uses io {
    print(to_text(code("a", 0)))
}
''',
    # Until 8.3, == on two maps was Python's comparison of two prover
    # objects - a constant False - so the branch looked unreachable and f
    # came back proven, and it breaks when it runs (check_prover_lies.py,
    # COMPARED). Written for the mutant at prover.py 558, it found that.
    "maps_compared": '''
fn f(m: Map of Text to Int, n: Map of Text to Int) -> Int
    ensures result == 0
{
    if m == n {
        return 1
    }
    return 0
}
fn main() uses io {
    print(to_text(f({"a": 1}, {"a": 2})))
}
''',
    "index_from_summary": '''
fn pick(n: Int) -> Int
    requires n > 0
    ensures result >= 0 and result < n
{
    return 0
}
fn first(xs: List of Int) -> Int
    requires length(xs) > 0
{
    return get(xs, pick(length(xs)))
}
fn main() uses io {
    print(to_text(first([4, 5])))
}
''',
    "invariant_uninterpreted_true": '''
fn walk(t: Text, n: Int) -> Int
    requires n >= 0 and length(t) > 0
    ensures result >= 0
{
    let i = 0
    while i < n
        invariant i >= 0 and code_at(t, 0) == code_at(t, 0)
    {
        i = i + 1
    }
    return i
}
fn main() uses io {
    print(to_text(walk("a", 2)))
}
''',
    "invariant_uninterpreted_unknown": '''
fn walk2(t: Text, n: Int) -> Int
    requires length(t) > 0
{
    let i = 0
    while i < n
        invariant code_at(t, 0) >= 0
    {
        i = i + 1
    }
    return i
}
fn main() uses io {
    print(to_text(walk2("a", 2)))
}
''',
    "invariant_false_values": '''
fn f(n: Int) -> Int {
    let i = 0
    while i < 10
        invariant i >= 1 and n >= n
    {
        i = i + 1
    }
    return i
}
fn main() uses io {
    print(to_text(f(1)))
}
''',
    "invariant_written": '''
fn total_to(n: Int) -> Int
    requires n >= 0
    ensures result >= 0
{
    let total = 0
    let i = 1
    while i <= n
        invariant total >= 0
        invariant i >= 1
    {
        total = total + i
        i = i + 1
    }
    return total
}
fn main() uses io {
    print(to_text(total_to(3)))
}
''',
    # x^3 + y^3 + z^3 = 33 has integer solutions (Booker, 2019), but no
    # solver finds one: the invariant is false at entry for them and Z3
    # can only say 'unknown'. Everything after entry is easy, so an
    # 'unknown' taken for 'holds' would prove f.
    "invariant_undecided": '''
fn f(x: Int, y: Int, z: Int) -> Int
    ensures result >= 5
{
    let i = 0
    while i < 10
        invariant i >= 5 or x * x * x + y * y * y + z * z * z != 33
    {
        i = i + 1
    }
    return i
}
fn main() uses io {
    print(to_text(f(1, 2, 3)))
}
''',
}


def prover_cases() -> None:
    say("the prover (has_fresh, uninterpreted_in, prove_invariant, "
        "prove_bounds)")
    labels = [
        "[V1] a counterexample through a summarised record is left to runtime",
        "[V2] a counterexample through a summarised list is left to runtime",
        "[V3] a counterexample through a list of lists holding a summarised "
        "list is left to runtime",
        "[V4] a sum Z3 was never given is not refuted: a correct sum_one is "
        "left to runtime",
        "[V5] code_at, uninterpreted, is not refuted: a correct code() is "
        "left to runtime",
        "[V6] a promise past a comparison of two maps is left to runtime, "
        "never proven (8.3)",
        "[V7] an index a summarised call gave is left to runtime, not E705",
        "[V8] a true invariant mentioning code_at is proven",
        "[V9] an invariant Z3 cannot settle over code_at is left to runtime, "
        "not E703",
        "[V10] E703 shows every value as a number",
        "[V11] a loop with written invariants is proven",
        "[V12] an invariant Z3 could not decide is never proven",
    ]
    if not HAVE_Z3:
        for label in labels:
            skip(label, "needs the prover: z3 is not installed")
        return
    compiles(labels[0], PROVER["record_summary"], prove=True, proven=("mk",),
             runtime=("f",))
    compiles(labels[1], PROVER["list_summary"], prove=True, runtime=("f",))
    compiles(labels[2], PROVER["grid_summary"], prove=True, runtime=("f",))
    compiles(labels[3], PROVER["sum_never_given"], prove=True,
             runtime=("sum_one",))
    compiles(labels[4], PROVER["code_at_result"], prove=True,
             runtime=("code",))
    compiles(labels[5], PROVER["maps_compared"], prove=True, runtime=("f",))
    compiles(labels[6], PROVER["index_from_summary"], prove=True,
             proven=("pick",), runtime=("first",))
    compiles(labels[7], PROVER["invariant_uninterpreted_true"], prove=True,
             proven=("walk",))
    compiles(labels[8], PROVER["invariant_uninterpreted_unknown"], prove=True,
             runtime=("walk2",))

    def values_shown() -> tuple[bool, str]:
        got = problems(PROVER["invariant_false_values"], prove=True)
        said = [p.message for p in got.problems if p.code == "E703"]
        allowed = said[0].rsplit("allow:", 1)[-1] if said else ""
        pairs = re.findall(r"(\w+) = (\S+?)(?:,|$)", allowed.strip())
        return (bool(said) and {n for n, _ in pairs} == {"i", "n"}
                and all(re.fullmatch(r"-?\d+", v) for _, v in pairs),
                f"E703 said: {said}")
    holds(labels[9], values_shown)
    compiles(labels[10], PROVER["invariant_written"], prove=True,
             proven=("total_to",))
    with environ({sabline.prover.PROOF_TIMEOUT_ENV: "1"}):
        compiles(labels[11], PROVER["invariant_undecided"], prove=True,
                 runtime=("f",))


def main() -> int:
    ceiling_cases()
    host_cases()
    credential_cases()
    proxy_cases()
    effect_cases()
    wrapper_cases()
    prover_cases()
    note = f", {SKIP[0]} skipped (no prover installed)" if SKIP[0] else ""
    say(f"{PASS[0]} ok, {FAIL[0]} wrong{note}")
    return 1 if FAIL[0] else 0


if __name__ == "__main__":
    sys.exit(main())
