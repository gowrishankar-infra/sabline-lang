#!/usr/bin/env python3
"""Money: exact, in one currency, and rounding only where it is named.

Every case here is a whole program, checked or run by the real compiler.
The suite covers what a currency type has to get right and what a
verifier has to get right about it:

  * arithmetic across two currencies is refused before the program runs,
    and so is an amount times an amount, or one divided with '/'
  * 64-bit edges: an amount that grows past them stops the program
  * split for 3, 7 and 100 ways, for amounts that do not divide, for a
    negative amount, for zero ways - each with the exact sum asserted
  * every rounding mode on a half case, in both signs, against Python's
    decimal module as an independent oracle
  * currencies with 0, 2 and 3 minor units, text and parsing round-trips
  * a property test: 200 random amounts and divisors, parts that always
    add up to the whole
  * the promises of item 2: which prove, and which do not
  * the prover's rounding formulas against the interpreter's

    python check_money.py
"""
import random
import subprocess
import sys
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP
from decimal import getcontext
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
VELARIS = HERE / "velaris.py"

sys.path.insert(0, str(HERE))
import velaris  # noqa: E402
from suite_dirs import isolate  # noqa: E402

# its own directory, so two runs at once do not collide
SCRATCH = isolate("check_money") / "_money_check.vel"

getcontext().prec = 80
PASS = [0]
FAIL = [0]


def ok(label: str, good: bool, detail: object = "") -> None:
    if good:
        PASS[0] += 1
        print(f"  ok    {label}")
    else:
        FAIL[0] += 1
        print(f"  WRONG {label}" + (f"\n          {detail}" if detail else ""))


def without_notes(text: str) -> str:
    """What the program printed, without the compiler's notes about what
    is not installed - so a run without the prover compares the same."""
    return "\n".join(ln for ln in text.splitlines()
                     if not ln.startswith("note: ")).strip()


def run(source: str, *args: str) -> tuple[Any, ...]:
    """Run a program; (exit code, its output)."""
    SCRATCH.write_text(source, encoding="utf-8")
    done = subprocess.run(
        [sys.executable, str(VELARIS), str(SCRATCH), *args],
        capture_output=True, text=True, timeout=600, cwd=str(HERE))
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def check(source: str, *args: str) -> tuple[Any, ...]:
    SCRATCH.write_text(source, encoding="utf-8")
    done = subprocess.run(
        [sys.executable, str(VELARIS), "check", str(SCRATCH), *args],
        capture_output=True, text=True, timeout=600, cwd=str(HERE))
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def refused(label: str, body: str, code: str, imports: str = "") -> None:
    """This program must be refused before it runs, with this code."""
    got_code, out = check(imports + "fn main() uses io {\n" + body + "\n}\n")
    ok(label, got_code != 0 and code in out,
       f"expected {code}, got: {out.strip().splitlines()[:2]}")


def prints(label: str, body: str, want: str, imports: str = "",
           extra: str = "") -> None:
    """This program must run and print exactly this."""
    code, out = run(imports + extra + "fn main() uses io {\n" + body
                    + "\n}\n", "--allow", "io")
    ok(label, code == 0 and without_notes(out) == want,
       f"wanted {want!r}, got {without_notes(out)!r}")


MONEY = 'import "money.vel" as money\n'

print("MONEY")
print("-" * 62)

# ---- 1. two currencies never meet -----------------------------------------
refused("adding INR to USD is refused",
        '    print(money(100, "INR") + money(100, "USD"))', "E550")
refused("subtracting USD from INR is refused",
        '    print(money(100, "INR") - money(100, "USD"))', "E550")
refused("comparing INR with USD is refused",
        '    if money(100, "INR") > money(100, "USD") { print("x") }',
        "E550")
refused("== across currencies is refused",
        '    if money(100, "INR") == money(100, "USD") { print("x") }',
        "E550")
refused("a list cannot hold two currencies",
        '    let xs = [money(1, "INR"), money(1, "JPY")]\n'
        "    print(length(xs))", "E550")
refused("a USD amount cannot be passed where INR is asked",
        '    print(text_of(twice(money(5, "USD"))))', "E550",
        imports='fn twice(m: Money of INR) -> Money of INR {\n'
                "    return m * 2\n}\n")
refused("a USD amount cannot be returned where INR is promised", "",
        "E550",
        imports='fn wrong() -> Money of INR {\n'
                '    return money(5, "USD")\n}\n')
refused("a record field keeps its currency",
        '    let r = Row(amount: money(5, "USD"))\n    print(r.amount)',
        "E550",
        imports="record Row {\n    amount: Money of INR\n}\n")
refused("a variable keeps its currency",
        '    let m = money(5, "INR")\n    m = money(5, "USD")\n'
        "    print(m)", "E550")

# ---- 2. an amount is not a number ------------------------------------------
refused("an amount times an amount is refused",
        '    print(money(100, "INR") * money(2, "INR"))', "E501")
refused("an amount plus an Int is refused",
        '    print(money(100, "INR") + 2)', "E501")
refused("an amount and a Float never meet",
        '    print(money(100, "INR") * 1.5)', "E501")
refused("'/' on an amount is refused, and names what to use instead",
        '    print(money(100, "INR") / 3)', "E553")
refused("'%' on an amount is refused",
        '    print(money(100, "INR") % 3)', "E553")
refused("an unknown currency is refused",
        '    print(money(100, "XYZ"))', "E551")
refused("an unknown currency in a type is refused", "    print(1)", "E551",
        imports="fn f(m: Money of XYZ) -> Int {\n"
                "    return units_of(m)\n}\n")
refused("a currency that is not written in the call is refused",
        '    let c = "INR"\n    print(money(100, c))', "E551")
refused("an unknown rounding mode is refused",
        '    print(percent_of(money(100, "INR"), 1, 3, "half_odd"))',
        "E552")
refused("a rounding mode that is not written in the call is refused",
        '    let mode = "half_up"\n'
        '    print(percent_of(money(100, "INR"), 1, 3, mode))', "E552")
refused("percent_of without a rounding mode is refused (it is an "
        "argument, not a default)",
        '    print(percent_of(money(100, "INR"), 1, 3))', "E401")
refused("divide_or_fail without a rounding mode is refused",
        '    check divide_or_fail(money(100, "INR"), 3) {\n'
        "        ok v {\n            print(v)\n        }\n"
        "        fail why {\n            print(why)\n        }\n    }",
        "E401")
refused("an ignored divide_or_fail is refused",
        '    let v = divide_or_fail(money(100, "INR"), 3, "down")\n'
        "    print(v)", "E520")
refused("an ignored parse_money is refused",
        '    let v = parse_money("1.00", "INR")\n    print(v)', "E520")

# ---- 3. the 64-bit edge ----------------------------------------------------
MAX = 9223372036854775807
MIN = -9223372036854775808
code, out = run(f'fn main() uses io {{\n'
                f'    print(money({MAX}, "INR") + money(1, "INR"))\n}}\n',
                "--allow", "io")
ok("an amount past the 64-bit edge stops the program (E407)",
   code != 0 and "E407" in out, out.strip()[:120])
code, out = run(f'fn main() uses io {{\n'
                f'    print(money({MAX}, "INR") * 2)\n}}\n', "--allow", "io")
ok("an amount multiplied past the edge stops the program",
   code != 0 and "E407" in out, out.strip()[:120])
code, out = run(f'fn main() uses io {{\n'
                f'    let m = money({MIN}, "INR")\n    print(0 - 0)\n'
                f'    print(text_of(-m))\n}}\n', "--allow", "io")
ok("negating the smallest amount stops the program",
   code != 0 and "E407" in out, out.strip()[:120])
code, out = run(f'fn main() uses io {{\n'
                f'    let xs = [money({MAX}, "INR"), money(1, "INR")]\n'
                f"    print(units_of(xs))\n}}\n", "--allow", "io")
ok("a total past the edge stops the program",
   code != 0 and "E407" in out, out.strip()[:120])
prints("an amount at the edge is exact",
       f'    print(text_of(money({MAX}, "INR")))',
       "INR 92233720368547758.07")
# percent_of multiplies exactly first: the product is past 64 bits here,
# and the answer is not
prints("percent_of is exact inside, and only its answer must fit",
       f'    print(units_of(percent_of(money({MAX}, "INR"), 1, 1000, '
       f'"down")))', "9223372036854775")
code, out = run(f'fn main() uses io {{\n'
                f'    print(units_of(percent_of(money({MAX}, "INR"), 3, '
                f'1, "down")))\n}}\n', "--allow", "io")
ok("percent_of past the edge stops the program",
   code != 0 and "E407" in out, out.strip()[:120])

# ---- 4. split ---------------------------------------------------------------
SPLIT_SHOW = (
    "fn show(parts: List of Money of INR) -> Text {\n"
    "    let out = \"\"\n"
    "    let i = 0\n"
    "    while i < length(parts) {\n"
    "        out = out + to_text(units_of(get(parts, i))) + \" \"\n"
    "        i = i + 1\n"
    "    }\n"
    "    return out + \"= \" + to_text(units_of(parts))\n"
    "}\n")


def split_case(label: str, units: int, ways: int, want: str) -> None:
    prints(label,
           f'    print(show(money.split(money({units}, "INR"), {ways})))',
           want, imports=MONEY, extra=SPLIT_SHOW)


split_case("split 1000 three ways: 334 333 333, exactly 1000",
           1000, 3, "334 333 333 = 1000")
split_case("split 1002 three ways divides evenly", 1002, 3,
           "334 334 334 = 1002")
split_case("split 100 seven ways: two parts carry the remainder",
           100, 7, "15 15 14 14 14 14 14 = 100")
split_case("split 1 three ways gives the unit to the first", 1, 3,
           "1 0 0 = 1")
split_case("split zero", 0, 3, "0 0 0 = 0")
split_case("split one way is the amount itself", 1234, 1, "1234 = 1234")
split_case("a negative amount splits into the negated parts",
           -1000, 3, "-334 -333 -333 = -1000")
prints("split 100 ways still adds up exactly",
       '    let parts = money.split(money(1003, "INR"), 100)\n'
       "    print(to_text(length(parts)) + \" parts, \"\n"
       "    + to_text(units_of(parts)) + \" total, first \"\n"
       "    + to_text(units_of(get(parts, 0))) + \", last \"\n"
       "    + to_text(units_of(get(parts, 99))))",
       "100 parts, 1003 total, first 11, last 10", imports=MONEY)
code, out = run(MONEY + 'fn main() uses io {\n'
                '    print(length(money.split(money(100, "INR"), 0)))\n}\n',
                "--allow", "io")
ok("split zero ways is refused: with the prover before running (E701), "
   "without it while running (E600)",
   code != 0 and ("E701" in out or "E600" in out), out.strip()[:160])
code, out = check(MONEY + 'fn main() uses io {\n'
                  '    print(length(money.split(money(100, "INR"), 0)))\n}\n')
ok("...and with the prover installed that is a compile error",
   (code != 0 and "E701" in out) or not velaris.HAVE_Z3, out.strip()[:160])

# ---- 5. rounding, against Python's decimal module ---------------------------
MODES = {"half_up": ROUND_HALF_UP, "half_even": ROUND_HALF_EVEN,
         "down": ROUND_DOWN}


def oracle(p: int, q: int, mode: str) -> int:
    return int((Decimal(p) / Decimal(q)).quantize(Decimal(1),
                                                  rounding=MODES[mode]))


halves = [(5, 2), (-5, 2), (7, 2), (-7, 2), (1, 2), (-1, 2), (3, 2),
          (-3, 2), (250, 100), (-250, 100), (350, 100), (-350, 100)]
bad = [f"{p}/{q} {m}: {velaris.round_ratio(p, q, m)} not {oracle(p, q, m)}"
       for p, q in halves for m in MODES
       if velaris.round_ratio(p, q, m) != oracle(p, q, m)]
ok("every rounding mode on a half case, both signs, matches decimal",
   not bad, "; ".join(bad[:4]))
rng = random.Random(43)
pairs = [(rng.randint(-10 ** 12, 10 ** 12), rng.randint(1, 10 ** 6))
         for _ in range(600)]
bad = [f"{p}/{q} {m}" for p, q in pairs for m in MODES
       if velaris.round_ratio(p, q, m) != oracle(p, q, m)]
ok("600 random ratios in three modes match decimal", not bad,
   "; ".join(bad[:4]))
prints("half_up takes a half away from zero, in the language",
       '    print(to_text(units_of(divide_ok(money(5, "INR"), 2, '
       '"half_up")))\n'
       '    + " " + to_text(units_of(divide_ok(money(-5, "INR"), 2, '
       '"half_up"))))',
       "3 -3", extra=(
           'fn divide_ok(m: Money of INR, by: Int, mode: Text) '
           "-> Money of INR {\n"
           '    check divide_or_fail(m, by, "half_up") {\n'
           "        ok v {\n            return v\n        }\n"
           "        fail why {\n            return m\n        }\n    }\n"
           "    return m\n}\n"))
prints("half_even goes to the even neighbour",
       '    print(to_text(units_of(percent_of(money(5, "INR"), 1, 2, '
       '"half_even")))\n'
       '    + " " + to_text(units_of(percent_of(money(7, "INR"), 1, 2, '
       '"half_even"))))', "2 4")
prints("down goes toward zero, on both sides",
       '    print(to_text(units_of(percent_of(money(-5, "INR"), 1, 2, '
       '"down")))\n'
       '    + " " + to_text(units_of(percent_of(money(5, "INR"), 1, 2, '
       '"down"))))', "-2 2")
code, out = run('fn main() uses io {\n'
                '    check divide_or_fail(money(10, "INR"), 0, "down") {\n'
                "        ok v {\n            print(v)\n        }\n"
                "        fail why {\n            print(why)\n        }\n"
                "    }\n}\n", "--allow", "io")
ok("dividing an amount by zero is a failure the program can catch",
   code == 0 and "zero" in out, out.strip()[:120])
code, out = run('fn main() uses io {\n'
                '    print(percent_of(money(10, "INR"), 1, 0, "down"))\n}\n',
                "--allow", "io")
ok("percent_of with a denominator of zero stops the program (E403/E706)",
   code != 0 and ("E403" in out or "E706" in out), out.strip()[:120])

# ---- 6. currencies with 0, 2 and 3 minor units ------------------------------
prints("JPY has no minor unit", '    print(text_of(money(1250, "JPY")))',
       "JPY 1250")
prints("KWD has three", '    print(text_of(money(1250, "KWD")))',
       "KWD 1.250")
prints("INR and USD have two",
       '    print(text_of(money(1250, "INR")) + " "\n'
       '    + text_of(money(5, "USD")))', "INR 12.50 USD 0.05")
prints("a negative amount keeps its sign with the number",
       '    print(text_of(money(-1250, "INR")) + " "\n'
       '    + text_of(money(-5, "INR")))', "INR -12.50 INR -0.05")
prints("an amount prints the same way through to_text and format",
       '    print(format("{} {}", money(1250, "INR"), '
       'to_text(money(1250, "INR"))))', "INR 12.50 INR 12.50")

PARSE = ("fn amount(t: Text) -> Text {\n"
         '    check parse_money(t, "INR") {\n'
         "        ok m {\n            return text_of(m)\n        }\n"
         "        fail why {\n            return \"no: \" + why\n        }\n"
         "    }\n    return \"\"\n}\n")
prints("parse_money takes 12.50, 12.5, 12 and a leading minus",
       '    print(amount("12.50") + " | " + amount("12.5") + " | "\n'
       '    + amount("12") + " | " + amount("-3.05"))',
       "INR 12.50 | INR 12.50 | INR 12.00 | INR -3.05", extra=PARSE)
prints("parse_money takes what text_of writes, code and all",
       '    print(amount("INR 12.50"))', "INR 12.50", extra=PARSE)
prints("parse_money refuses another currency's text",
       '    print(amount("USD 12.50"))',
       "no: 'USD 12.50' is in USD, not INR", extra=PARSE)
prints("parse_money refuses digits it would have to round away",
       '    print(amount("12.505"))',
       "no: '12.505' has 3 digits after the point, and INR has 2",
       extra=PARSE)
prints("parse_money refuses a separator, a plus and an empty text",
       '    print(amount("1,250.00"))\n    print(amount("+5"))\n'
       '    print(amount(""))',
       "no: '1,250.00' is not an amount like 12.50\n"
       "no: '+5' is not an amount like 12.50\n"
       "no: '' is not an amount like 12.50", extra=PARSE)
prints("parse_money refuses an amount too big to hold",
       '    print(amount("99999999999999999999"))',
       "no: '99999999999999999999' is too big to hold", extra=PARSE)
prints("a currency with no minor unit refuses a point",
       '    check parse_money("12.5", "JPY") {\n'
       "        ok m {\n            print(text_of(m))\n        }\n"
       "        fail why {\n            print(why)\n        }\n    }",
       "'12.5' has digits after the point, and JPY has no minor unit")

round_trip = []
for cur, digits in sorted(velaris.CURRENCIES.items()):
    for units in (0, 1, -1, 5, -5, 1250, -999999, 10 ** 12):
        m = velaris.MoneyValue(units, cur)
        back = velaris.parse_money_text(velaris.money_text(m), cur)
        if back != m:
            round_trip.append(f"{cur} {units} -> {velaris.money_text(m)} "
                              f"-> {back}")
ok(f"text and parse round-trip for all {len(velaris.CURRENCIES)} "
   f"currencies, 8 amounts each", not round_trip, "; ".join(round_trip[:3]))

# ---- 7. the property test: the parts always add up to the whole -------------
rng = random.Random(7)
cases = [(rng.randint(-10 ** 11, 10 ** 11), rng.randint(1, 40))
         for _ in range(200)]
lines = []
for units, ways in cases:
    lines.append(f'    check_split({units}, {ways})')
program = (MONEY + SPLIT_SHOW.replace("show", "unused_show")
           + "fn check_split(units: Int, ways: Int) uses io\n"
             "    requires ways > 0\n"
             "{\n"
             '    let parts = money.split(money(units, "INR"), ways)\n'
             "    let total = units_of(parts)\n"
             "    let biggest = units_of(get(parts, 0))\n"
             "    let smallest = units_of(get(parts, length(parts) - 1))\n"
             "    if total != units {\n"
             '        print(format("SUM {} {} -> {}", units, ways, total))\n'
             "    }\n"
             "    if length(parts) != ways {\n"
             '        print(format("LEN {} {}", units, ways))\n'
             "    }\n"
             "    if biggest - smallest > 1 or smallest - biggest > 1 {\n"
             '        print(format("SPREAD {} {}", units, ways))\n'
             "    }\n"
             "}\n"
             "fn main() uses io {\n" + "\n".join(lines) + "\n"
             '    print("all 200 add up")\n}\n')
code, out = run(program, "--allow", "io")
ok("200 random amounts and divisors: every split adds up to its amount, "
   "has as many parts as asked, and spreads them by at most one unit",
   code == 0 and without_notes(out) == "all 200 add up",
   without_notes(out)[:200])

# ---- 8. the promises of item 2 ---------------------------------------------
CONTRACTS = MONEY + '''
fn not_negative(m: Money of INR) -> Bool {
    return m >= money(0, "INR")
}

fn total_of(xs: List of Money of INR) -> Money of INR
    requires all_of(xs, not_negative)
    ensures result >= money(0, "INR")
{
    let sum = money(0, "INR")
    for x in xs {
        sum = sum + x
    }
    return sum
}

fn total_units(xs: List of Money of INR) -> Int
    requires all_of(xs, not_negative)
    ensures result >= 0
{
    return units_of(xs)
}

fn shares(payout: Money of INR) -> List of Money of INR
    requires payout >= money(0, "INR")
    ensures units_of(result) == units_of(payout)
    ensures all_of(result, not_negative)
{
    return money.split(payout, 3)
}

fn share_of(amount: Money of INR, numerator: Int, denominator: Int)
-> Money of INR
    requires amount >= money(0, "INR")
    requires numerator >= 0
    requires numerator <= denominator
    requires denominator > 0
    ensures result <= amount
    ensures result >= money(0, "INR")
{
    return percent_of(amount, numerator, denominator, "half_up")
}

fn net_of(gross: Money of INR, fee: Money of INR) -> Money of INR
    requires fee <= gross
    requires fee >= money(0, "INR")
    ensures result >= money(0, "INR")
{
    return gross - fee
}

fn main() uses io {
    print("ok")
}
'''
SCRATCH.write_text(CONTRACTS, encoding="utf-8")
report = velaris.inspect_source(str(SCRATCH))
status = {f["name"]: f["status"] for f in report["functions"]}
if not velaris.HAVE_Z3:
    print("  note  z3-solver is absent: the promises below are checked "
          "while running, and are not asserted here")
    for _ in range(7):
        ok("(skipped without the prover)", True)
else:
    ok("a total over a list of amounts is non-negative when every item "
       "is - the loop that adds them", status.get("total_of") == "proven",
       str(status))
    ok("...and units_of over the same list, through the sum facts",
       status.get("total_units") == "proven", str(status))
    ok("split's parts add up to its amount, at the caller",
       status.get("shares") == "proven", str(status))
    ok("...and no part of a non-negative amount is negative",
       status.get("shares") == "proven", str(status))
    ok("percent_of never exceeds its amount for a numerator at most the "
       "denominator", status.get("share_of") == "proven", str(status))
    ok("a subtraction guarded by a requires cannot go negative",
       status.get("net_of") == "proven", str(status))
    ok("money.split itself proves, where it is written",
       all(f["status"] == "proven"
           for f in velaris.inspect_source(
               str(HERE / "stdlib" / "money.vel"))["functions"]
           if f["name"] == "split"))

# ---- 9. the prover's formulas are the interpreter's -------------------------
if not velaris.HAVE_Z3:
    ok("(the prover's rounding is not checked without z3)", True)
else:
    import z3
    disagree = []
    rng = random.Random(11)
    for _ in range(150):
        p = rng.randint(-10 ** 9, 10 ** 9)
        d = rng.randint(1, 10 ** 5)
        for mode in MODES:
            want = velaris.round_ratio(p, d, mode)
            q, r = z3.IntVal(p) / z3.IntVal(d), z3.IntVal(p) % z3.IntVal(d)
            pz = z3.IntVal(p)
            if mode == "down":
                f = z3.If(z3.Or(pz >= 0, r == 0), q, q + 1)
            elif mode == "half_up":
                f = z3.If(2 * r > d, q + 1, z3.If(2 * r < d, q,
                          z3.If(pz >= 0, q + 1, q)))
            else:
                f = z3.If(2 * r > d, q + 1, z3.If(2 * r < d, q,
                          z3.If(q % 2 == 0, q, q + 1)))
            got = z3.simplify(f)
            if got.as_long() != want:
                disagree.append(f"{p}/{d} {mode}: z3 {got} != {want}")
    ok("the prover's rounding formulas and the interpreter's agree on "
       "450 cases", not disagree, "; ".join(disagree[:3]))

# ---- 10. amounts in the shapes a program keeps them in ----------------------
prints("an amount lives in a record, a list and a map",
       '    let r = Row(party: "asha", amount: money(1250, "INR"))\n'
       '    let xs = [r.amount, money(750, "INR")]\n'
       '    let m: Map of Text to Money of INR = {"asha": r.amount}\n'
       '    print(text_of(units_sum(xs)) + " "\n'
       '    + text_of(get_or(m, "asha", money(0, "INR"))))',
       "INR 20.00 INR 12.50",
       imports='record Row {\n    party: Text\n    amount: Money of INR\n}\n'
               "fn units_sum(xs: List of Money of INR) -> Money of INR {\n"
               '    return money(units_of(xs), "INR")\n}\n')
prints("amounts compare and sort by their units",
       '    let xs = [money(300, "INR"), money(100, "INR"), '
       'money(200, "INR")]\n'
       "    let sorted = sort_by(xs, fn(m: Money of INR) -> Int {\n"
       "        return units_of(m)\n    })\n"
       "    print(text_of(get(sorted, 0)) + \" \"\n"
       "    + text_of(get(sorted, 2)))", "INR 1.00 INR 3.00",
       imports='import "std.vel"\n')
prints("json_of writes an amount as its units and its currency, never "
       "as a number with a point",
       '    print(json_of(money(1250, "INR")))',
       '{"currency": "INR", "units": 1250}')
prints("a function generic in its currency serves every currency",
       '    print(text_of(twice(money(50, "JPY"))) + " "\n'
       '    + text_of(twice(money(50, "KWD"))))', "JPY 100 KWD 0.100",
       imports="fn twice(m: Money of C) -> Money of C for any C {\n"
               "    return m * 2\n}\n")
prints("units_of over an empty list of amounts is zero",
       "    let xs: List of Money of INR = []\n"
       "    print(units_of(xs))", "0")

# ---- 11. a builtin gives way to a program's own function --------------------
prints("a program's own 'money' function is the one it calls (the "
       "builtins added in 4.3 give way)",
       "    print(money(2500))",
       "25.00",
       imports="fn money(cents: Int) -> Text {\n"
               "    let whole = cents / 100\n"
               "    let part = cents % 100\n"
               "    if part < 10 {\n"
               '        return whole + ".0" + part\n    }\n'
               '    return whole + "." + part\n}\n')
prints("...and a library imported with a name still reaches the builtin "
       "it was written against",
       '    let parts = money.split(money(1000, "INR"), 3)\n'
       '    print(to_text(units_of(41)) + " "\n'
       "    + text_of(get(parts, 0)))",
       "42 INR 3.34",
       imports=MONEY + "fn units_of(n: Int) -> Int {\n"
               "    return n + 1\n}\n")

# ---- 12. Money changes nothing about effects or the audit -------------------
audit = velaris.audit((HERE / "examples" / "settlement.vel").read_text(
    encoding="utf-8"), path=str(HERE / "examples" / "settlement.vel"))
doc = audit.as_dict()
ok("a program full of amounts still declares only io",
   sorted(doc["effects"]) == ["io"], str(doc["effects"]))
ok("its safe_command grants io alone",
   doc["safe_command"].endswith("--allow io"), doc["safe_command"])
ok("velaris.audit/1 is unchanged in shape",
   doc["schema"] == "velaris.audit/1" and "counts" in doc
   and "prover" in doc, sorted(doc))
# Money added no effect of its own. The list is the seven of 3.0 plus
# declassify, which 6.0 added for Secret - nothing here is Money's.
ok("Money added no effect", velaris.ALL_EFFECTS == (
    "io", "env", "fs", "net", "clock", "rand", "ffi", "declassify"),
   str(velaris.ALL_EFFECTS))
ok("no Money builtin has an effect",
   all(not velaris.BUILTINS[n]["effects"] for n in velaris.MONEY_BUILTINS),
   str(velaris.MONEY_BUILTINS))

SCRATCH.unlink(missing_ok=True)
print("-" * 62)
print(f"{PASS[0]} right, {FAIL[0]} wrong")
if FAIL[0] == 0:
    print("amounts are exact, one currency at a time, and round only "
          "where the call says so")
sys.exit(1 if FAIL[0] else 0)
