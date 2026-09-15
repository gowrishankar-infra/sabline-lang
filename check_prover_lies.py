#!/usr/bin/env python3
"""A corpus of lies: false promises that must NEVER come back proven.

Goal A of SECURITY.md is that a promise Velaris reports "proven" never
breaks at run time. This suite is the adversary's side of it: a set of
`requires` / `ensures` / `invariant` clauses that are false, grouped by
what they are about - IEEE-754 floats, 64-bit overflow, Money, all_of and
any_of, recursion, and the rest - each of which must be either refused
before running (E700/E701/E703/E705/E706, with the prover) or left to a
runtime check (without it) - but never listed among the proven.

Three things are asserted about every lie (8.2):

  well-formed   With z3, check() compiles it or refuses it only with
                prover codes (E7xx in ERROR_TABLE); without z3 it
                compiles. A lie that does not parse or type-check is
                never proven either, so without this a typo would pass
                the one assertion that matters and say nothing.
  really a lie  Its main calls the lying function with an input that
                breaks the promise, and run() does not end ok: it is
                refused before running (a prover code) or stopped while
                running with a code the case names - E601 a broken
                ensures, E600 a broken requires, E704 an invariant, E407
                overflow, E403 a zero divisor, E602 a read past the end.
                A run stopped by its own time limit shows nothing, and
                fails.
  never proven  The lying function is not in check(src).proven.

Seeds. Every lie and every IDENTIFIERS case is checked under Z3 random
seeds 0 to 4 (VELARIS_PROVER_SEED, which new_solver() passes to every
solver), with check(src, timeout=None, max_memory_mb=None) so that it
proves in this process and sees the variable. No lie may be proven under
any seed; a true IDENTIFIERS case must be proven under every seed; and
with z3 the verdict - the proven names and the problem codes, sorted -
must be the same under all five. A proof that needs a particular seed is
not one.

Timeouts. A query that spends its budget is abandoned: nothing is proven
and the promise is checked while running, which is still "never proven",
and that assertion is kept under every seed, abandoned or not. But
whether a slow float query finishes in time can depend on the seed and on
how busy the machine is, so a check that abandoned a proof under some
seed is left out of the verdict comparison for that seed, and the summary
lists it. PROOF_SECONDS below is the budget each query gets here.

The invariant holds with AND without z3: without the prover nothing is
proven at all, so a lie cannot be; with it, a lie is refused or falls
back. A lie that ever appears among the proven is a Goal A break and a
security issue.

    python check_prover_lies.py
"""
import contextlib
import io
import os
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import velaris  # noqa: E402
from suite_dirs import isolate  # noqa: E402

isolate("check_prover_lies")          # its own directory

try:
    import z3  # noqa: F401
    HAVE_Z3 = True
    del z3
except ImportError:
    HAVE_Z3 = False

SEEDS = (0, 1, 2, 3, 4)
SEED_ENV = "VELARIS_PROVER_SEED"
# Seconds per query, in this process and in the children run() starts.
# None keeps velaris's own budgets (3s, and 120s for a query with Float).
# They stand: with them the whole suite took under six minutes with z3
# when it was written (8.2), no float lie here needing more than a few
# seconds. One budget for both kinds would either cut the float queries
# short or give every Int query longer.
PROOF_SECONDS = None
RUN_SECONDS = 60
# What check_proofs prints, to stderr, for a proof it abandoned.
ABANDONED_NOTE = "ran out of time"

# Refusals the prover makes before a program runs. E704 starts with E7
# too, but it is the runtime half of E703 - an invariant that broke while
# running - so a case that expects it names it.
PROVER_CODES = frozenset(c for c in velaris.ERROR_TABLE
                         if c.startswith("E7") and c != "E704")

PASS = FAIL = 0
TIMEOUTS: list[Any] = []                   # (case, seed) with a proof abandoned


# Each case: (name, the lying function's name, the code(s) that stop it
# while running, source). The promise in the named function is false; it
# must never be proven, and main calls it with an input that breaks it.
EARLIER = [
    ("int add-off-by-one", "double", "E601", '''
fn double(n: Int) -> Int
  ensures result == n + n
{ return n + 1 }
fn main() uses io { print(to_text(double(3))) }
'''),
    ("int ensures wrong constant", "f", "E601", '''
fn f(n: Int) -> Int ensures result > n { return n }
fn main() uses io { print(to_text(f(1))) }
'''),
    ("division can be zero", "share", "E403", '''
fn share(total: Int, people: Int) -> Int
  ensures result >= 0
{ return total / people }
fn main() uses io { print(to_text(share(10, 0))) }
'''),
    ("remainder can be zero", "bucket", "E403", '''
fn bucket(id: Int, size: Int) -> Int { return id % size }
fn main() uses io { print(to_text(bucket(10, 0))) }
'''),
    ("list read past the end", "last", "E602", '''
fn last(xs: List of Int) -> Int
  requires length(xs) >= 1
{ return get(xs, length(xs)) }
fn main() uses io { print(to_text(last([1, 2, 3]))) }
'''),
    ("caller breaks a requires (E701)", "top", "E600", '''
fn safe(n: Int) -> Int requires n > 0 ensures result > 0 { return n }
fn top() -> Int { return safe(-5) }
fn main() uses io { print(to_text(top())) }
'''),
    ("loop invariant that does not hold", "sum_to", "E704", '''
fn sum_to(n: Int) -> Int
  requires n >= 0
  ensures result >= n
{
  let total = 0
  let i = 0
  while i < n
    invariant total >= i
  { i = i + 1 }
  return total
}
fn main() uses io { print(to_text(sum_to(3))) }
'''),
    ("record field promise swapped", "move", "E601", '''
record P { x: Int  y: Int }
fn move(p: P, dx: Int) -> P
  ensures result.x == p.x + dx
{ return P(x: p.x, y: p.y + dx) }
fn main() uses io { let p = move(P(x: 1, y: 2), 5)  print(to_text(p.x)) }
'''),
    # A Secret is made only by env() or read_file_secret(), so this main
    # needs env to hand one over (ALLOW, below). The variable is never set,
    # so the Secret is the fallback "hi", whose length is not 5.
    ("ensures over a Secret parameter is false", "bad", "E601", '''
fn bad(k: Secret of Text) -> Int
  ensures result == length(k)
{ return 5 }
fn main() uses io, env { print(to_text(bad(env("VELARIS_LIES_NEVER_SET", "hi")))) }
'''),
    ("float promise that is false", "half", "E601", '''
fn half(x: Float) -> Float
  ensures result == x
{ return x / 2.0 }
fn main() uses io { print(to_text(half(4.0))) }
'''),
    ("quantified promise that is false", "all_pos", "E601", '''
fn all_pos(xs: List of Int) -> Bool
  ensures result == all_of(xs, is_pos)
{ return true }
fn is_pos(n: Int) -> Bool { return n > 0 }
fn main() uses io { print(to_text(all_pos([1, -2]))) }
'''),
    # 8.1: until then the prover's own names could be spelled by a program.
    # A parameter named __g_result_1 was the same Z3 constant as the result
    # of the call g(...), so g's promise about its result became a promise
    # about the parameter, and this lie came back proven - and, as a
    # pure-Int function, was compiled to native code and never checked.
    ("a parameter named like the prover's name for a call's result", "f", "E601", '''
fn g(n: Int) -> Int
  ensures result > n
{ return n + 1 }
fn f(__g_result_1: Int) -> Int
  ensures result == __g_result_1 + 5
{ return g(__g_result_1) }
fn main() uses io { print(to_text(f(1))) }
'''),
    # ...and a record field named xs__n was the same constant as the length
    # the prover keeps for the list field xs
    ("a record field named like the prover's length of a list field", "f", "E601", '''
record Box { xs: List of Int  xs__n: Int }
fn f(b: Box) -> Int
  requires b.xs__n == 5
  ensures result == 5
{ return length(b.xs) }
fn main() uses io { print(to_text(f(Box(xs: [1], xs__n: 5)))) }
'''),
    ("a list parameter named like another's per-field array", "f", "E601", '''
record P { x: Int  y: Int }
fn f(ps: List of P, ps__x: List of Int) -> Int
  requires length(ps) == 1 and length(ps__x) == 1 and get(ps__x, 0) == 7
  ensures result == 7
{ return get(ps, 0).x }
fn main() uses io { print(to_text(f([P(x: 1, y: 2)], [7]))) }
'''),
]

# IEEE-754 binary64, round to nearest even (SPEC.md 4.2). The literal
# grammar has no exponent, so a main that needs an infinity or a NaN
# multiplies its way there: 10.0 multiplied 400 times is past the largest
# float, and infinity minus infinity is NaN.
FLOATS = [
    ("float: 0.1 + 0.2 is not 0.3", "tenths", "E601", '''
fn tenths() -> Float
  ensures result == 0.3
{ return 0.1 + 0.2 }
fn main() uses io { print(to_text(tenths())) }
'''),
    ("float: addition is not associative", "left_first", "E601", '''
fn left_first(a: Float, b: Float, c: Float) -> Float
  ensures result == a + (b + c)
{ return (a + b) + c }
fn main() uses io { print(to_text(left_first(0.1, 0.2, 0.3))) }
'''),
    ("float: multiplication is not associative", "left_first", "E601", '''
fn left_first(a: Float, b: Float, c: Float) -> Float
  ensures result == a * (b * c)
{ return (a * b) * c }
fn main() uses io { print(to_text(left_first(0.1, 0.2, 0.3))) }
'''),
    ("float: adding then subtracting 1.0 is not the identity", "round_trip", "E601", '''
fn round_trip(x: Float) -> Float
  ensures result == x
{ return (x + 1.0) - 1.0 }
fn main() uses io { print(to_text(round_trip(0.1))) }
'''),
    ("float: a large addend swallows a small one", "absorb", "E601", '''
fn absorb(x: Float) -> Float
  requires x > 0.0
  ensures result > 0.0
{ return (x + 10000000000000000.0) - 10000000000000000.0 }
fn main() uses io { print(to_text(absorb(0.5))) }
'''),
    ("float: x + 1.0 is not always larger than x", "bump", "E601", '''
fn bump(x: Float) -> Float
  requires x > 0.0
  ensures result > x
{ return x + 1.0 }
fn main() uses io { print(to_text(bump(10000000000000000.0))) }
'''),
    ("float: NaN is not equal to itself", "same", "E601", '''
fn same(x: Float) -> Bool
  ensures result
{ return x == x }
fn main() uses io {
  let x = 1.0
  for i in 0 to 400 { x = x * 10.0 }
  print(to_text(same(x - x)))
}
'''),
    ("float: NaN is neither below nor at-or-above zero", "sign_known", "E601", '''
fn sign_known(x: Float) -> Bool
  ensures result
{ return x < 0.0 or x >= 0.0 }
fn main() uses io {
  let x = 1.0
  for i in 0 to 400 { x = x * 10.0 }
  print(to_text(sign_known(x - x)))
}
'''),
    ("float: not below zero does not mean at or above zero", "clamp", "E601", '''
fn clamp(x: Float) -> Float
  requires not (x < 0.0)
  ensures result >= 0.0
{ return x }
fn main() uses io {
  let x = 1.0
  for i in 0 to 400 { x = x * 10.0 }
  print(to_text(clamp(x - x)))
}
'''),
    ("float: a square is not always at least zero", "square", "E601", '''
fn square(x: Float) -> Float
  ensures result >= 0.0
{ return x * x }
fn main() uses io {
  let x = 1.0
  for i in 0 to 400 { x = x * 10.0 }
  print(to_text(square(x - x)))
}
'''),
    # -0.0 == 0.0, so the requires lets both zeros in; only the text of
    # the result, or a division, can tell them apart
    ("float: -0.0 equals 0.0 but is not written as 0.0", "negate", "E601", '''
fn negate(x: Float) -> Float
  requires x == 0.0
  ensures to_text(result) == "0.0"
{ return -x }
fn main() uses io { print(to_text(negate(0.0))) }
'''),
    ("float: doubling overflows to infinity", "twice", "E601", '''
fn twice(x: Float) -> Float
  requires x > 0.0
  ensures result - x == x
{ return x + x }
fn main() uses io {
  let x = 1.0
  for i in 0 to 308 { x = x * 10.0 }
  print(to_text(twice(x)))
}
'''),
    ("float: a product of two finite floats is not always finite", "product", "E601", '''
fn product(x: Float, y: Float) -> Float
  requires x > 1.0 and y > 1.0
  ensures result - result == 0.0
{ return x * y }
fn main() uses io {
  let x = 1.0
  for i in 0 to 200 { x = x * 10.0 }
  print(to_text(product(x, x)))
}
'''),
    ("float: a positive square can underflow to zero", "square_pos", "E601", '''
fn square_pos(x: Float) -> Float
  requires x > 0.0
  ensures result > 0.0
{ return x * x }
fn main() uses io {
  let x = 1.0
  for i in 0 to 200 { x = x * 0.1 }
  print(to_text(square_pos(x)))
}
'''),
    ("float: division does not undo multiplication", "ratio", "E601", '''
fn ratio(x: Float, y: Float) -> Float
  requires y > 0.0
  ensures result * y == x
{ return x / y }
fn main() uses io { print(to_text(ratio(1.0, 49.0))) }
'''),
    ("float: 0.1 times 10.0 does not give back the whole", "tenfold", "E601", '''
fn tenfold(x: Float) -> Float
  ensures result == x
{ return x * 0.1 * 10.0 }
fn main() uses io { print(to_text(tenfold(3.0))) }
'''),
    # 1.0000000000000002 is the float after 1.0; half the gap rounds to
    # the even neighbour, which is 1.0 itself
    ("float: the midpoint of adjacent floats is not between them", "midpoint", "E601", '''
fn midpoint(a: Float, b: Float) -> Float
  requires a < b
  ensures result > a
{ return a + (b - a) * 0.5 }
fn main() uses io { print(to_text(midpoint(1.0, 1.0000000000000002))) }
'''),
    ("float: round takes a half to the even neighbour", "nearest", "E601", '''
fn nearest(x: Float) -> Int
  requires x == 2.5
  ensures result == 3
{ return round(x) }
fn main() uses io { print(to_text(nearest(2.5))) }
'''),
    ("float: an Int past 2^53 does not survive a trip through Float", "through_float", "E601", '''
fn through_float(n: Int) -> Int
  requires n == 9007199254740993
  ensures result == n
{ return round(to_float(n)) }
fn main() uses io { print(to_text(through_float(9007199254740993))) }
'''),
    # SPEC.md 4.2 says a Float divided by zero is an infinity; the
    # interpreter stops with E403, as it does for an Int
    ("float: division by a zero Float", "per_unit", "E403", '''
fn per_unit(total: Float, units: Float) -> Float
  requires total > 0.0 and units >= 0.0
  ensures result >= 0.0
{ return total / units }
fn main() uses io { print(to_text(per_unit(1.0, 0.0))) }
'''),
]

# Int is 64 bits and arithmetic past that is E407, never a wrap (SPEC.md
# 4.1). Most of these hold only under two's-complement wraparound, so the
# program stops with E407 before the promise is looked at; the rest sit on
# the boundary. MIN is written -9223372036854775807 - 1 so that only the
# case about a literal past 64 bits uses one.
OVERFLOW = [
    ("overflow: MAX + 1 does not wrap to a negative", "next", "E407", '''
fn next(n: Int) -> Int
  requires n == 9223372036854775807
  ensures result < 0
{ return n + 1 }
fn main() uses io { print(to_text(next(9223372036854775807))) }
'''),
    ("overflow: MAX + 1 is not MIN", "next", "E407", '''
fn next(n: Int) -> Int
  requires n == 9223372036854775807
  ensures result == -9223372036854775807 - 1
{ return n + 1 }
fn main() uses io { print(to_text(next(9223372036854775807))) }
'''),
    ("overflow: MIN - 1 is not MAX", "previous", "E407", '''
fn previous(n: Int) -> Int
  requires n == -9223372036854775807 - 1
  ensures result == 9223372036854775807
{ return n - 1 }
fn main() uses io { print(to_text(previous(-9223372036854775807 - 1))) }
'''),
    ("overflow: MAX + MAX is not -2", "sum", "E407", '''
fn sum(a: Int, b: Int) -> Int
  requires a == 9223372036854775807 and b == 9223372036854775807
  ensures result == -2
{ return a + b }
fn main() uses io { print(to_text(sum(9223372036854775807, 9223372036854775807))) }
'''),
    ("overflow: 2^32 squared is not 0", "square", "E407", '''
fn square(n: Int) -> Int
  requires n == 4294967296
  ensures result == 0
{ return n * n }
fn main() uses io { print(to_text(square(4294967296))) }
'''),
    ("overflow: 3037000500 squared is not negative", "square", "E407", '''
fn square(n: Int) -> Int
  requires n == 3037000500
  ensures result < 0
{ return n * n }
fn main() uses io { print(to_text(square(3037000500))) }
'''),
    ("overflow: doubling past the top does not come back below", "twice", "E407", '''
fn twice(n: Int) -> Int
  requires n > 4611686018427387903
  ensures result < n
{ return n * 2 }
fn main() uses io { print(to_text(twice(4611686018427387904))) }
'''),
    ("overflow: subtracting MAX from a negative does not wrap positive", "far_below", "E407", '''
fn far_below(n: Int) -> Int
  requires n < -1
  ensures result > 0
{ return n - 9223372036854775807 }
fn main() uses io { print(to_text(far_below(-2))) }
'''),
    ("overflow: MIN times -1 is not negative", "flip", "E407", '''
fn flip(n: Int) -> Int
  requires n == -9223372036854775807 - 1
  ensures result < 0
{ return n * -1 }
fn main() uses io { print(to_text(flip(-9223372036854775807 - 1))) }
'''),
    # MIN / -1 and -MIN are 2^63, one past the top. SPEC.md 4.1 makes that
    # E407; the interpreter lets the 2^63 through (found writing this
    # corpus, 8.2), and the runtime check of the ensures then stops it
    # with E601. Either code is a run that did not end ok.
    ("overflow: MIN / -1 is not MIN", "quotient", "E407 E601", '''
fn quotient(a: Int, b: Int) -> Int
  requires a == -9223372036854775807 - 1 and b == -1
  ensures result == a
{ return a / b }
fn main() uses io { print(to_text(quotient(-9223372036854775807 - 1, -1))) }
'''),
    ("overflow: negating MIN is not MIN", "negate", "E407 E601", '''
fn negate(n: Int) -> Int
  requires n == -9223372036854775807 - 1
  ensures result == n
{ return -n }
fn main() uses io { print(to_text(negate(-9223372036854775807 - 1))) }
'''),
    ("overflow: the absolute value of MIN is not negative", "magnitude", "E407 E601", '''
fn magnitude(n: Int) -> Int
  requires n == -9223372036854775807 - 1
  ensures result < 0
{
  if n < 0 { return -n }
  return n
}
fn main() uses io { print(to_text(magnitude(-9223372036854775807 - 1))) }
'''),
    ("overflow: doubling 1 sixty-four times does not wrap to 0", "power_of_two", "E407", '''
fn power_of_two(n: Int) -> Int
  requires n == 64
  ensures result == 0
{
  let x = 1
  let i = 0
  while i < n {
    x = x * 2
    i = i + 1
  }
  return x
}
fn main() uses io { print(to_text(power_of_two(64))) }
'''),
    ("overflow: MAX is not below MAX", "same", "E601", '''
fn same(n: Int) -> Int
  ensures result < 9223372036854775807
{ return n }
fn main() uses io { print(to_text(same(9223372036854775807))) }
'''),
    ("overflow: MIN is not above MIN", "same", "E601", '''
fn same(n: Int) -> Int
  ensures result > -9223372036854775807 - 1
{ return n }
fn main() uses io { print(to_text(same(-9223372036854775807 - 1))) }
'''),
    ("overflow: no Int reaches a literal past 64 bits", "same", "E601", '''
fn same(n: Int) -> Int
  ensures result >= 9223372036854775808
{ return n }
fn main() uses io { print(to_text(same(9223372036854775807))) }
'''),
    ("overflow: a big square is not below 10^18", "square", "E601", '''
fn square(n: Int) -> Int
  requires n > 1000000000
  ensures result < 1000000000000000000
{ return n * n }
fn main() uses io { print(to_text(square(1000000001))) }
'''),
    ("overflow: two positive list items do not add to a negative", "pair_sum", "E407", '''
fn pair_sum(xs: List of Int) -> Int
  requires length(xs) == 2
  requires get(xs, 0) > 0 and get(xs, 1) > 0
  ensures result < 0
{ return get(xs, 0) + get(xs, 1) }
fn main() uses io { print(to_text(pair_sum([9223372036854775807, 1]))) }
'''),
]

# Money of CUR is whole minor units (SPEC.md 4.3): rounding only as named,
# percent_of multiplying before it divides, money.split's parts adding up
# exactly. Each lie is what a wrong idea of one of those would promise.
MONEY = [
    ("money: half_up takes 2.5 paise to 3, not 2", "half", "E601", '''
fn half(m: Money of INR) -> Money of INR
  requires units_of(m) == 5
  ensures units_of(result) == 2
{ return percent_of(m, 50, 100, "half_up") }
fn main() uses io { print(to_text(half(money(5, "INR")))) }
'''),
    ("money: half_even takes 7.5 to 8, not 7", "half", "E601", '''
fn half(m: Money of INR) -> Money of INR
  requires units_of(m) == 15
  ensures units_of(result) == 7
{ return percent_of(m, 50, 100, "half_even") }
fn main() uses io { print(to_text(half(money(15, "INR")))) }
'''),
    ("money: half_even takes 2.5 to 2, not 3", "half", "E601", '''
fn half(m: Money of INR) -> Money of INR
  requires units_of(m) == 5
  ensures units_of(result) == 3
{ return percent_of(m, 50, 100, "half_even") }
fn main() uses io { print(to_text(half(money(5, "INR")))) }
'''),
    ("money: down is toward zero, not toward minus infinity", "half", "E601", '''
fn half(m: Money of INR) -> Money of INR
  requires units_of(m) == -5
  ensures units_of(result) == -3
{ return percent_of(m, 50, 100, "down") }
fn main() uses io { print(to_text(half(money(-5, "INR")))) }
'''),
    ("money: half_up takes -2.5 away from zero, to -3", "half", "E601", '''
fn half(m: Money of INR) -> Money of INR
  requires units_of(m) == -5
  ensures units_of(result) == -2
{ return percent_of(m, 50, 100, "half_up") }
fn main() uses io { print(to_text(half(money(-5, "INR")))) }
'''),
    ("money: percent_of multiplies before it divides", "half", "E601", '''
fn half(m: Money of INR) -> Money of INR
  requires units_of(m) == 3
  ensures units_of(result) == 0
{ return percent_of(m, 50, 100, "down") }
fn main() uses io { print(to_text(half(money(3, "INR")))) }
'''),
    ("money: 150 percent is more than the amount", "markup", "E601", '''
fn markup(m: Money of INR) -> Money of INR
  requires m >= money(0, "INR")
  ensures result <= m
{ return percent_of(m, 150, 100, "half_up") }
fn main() uses io { print(to_text(markup(money(100, "INR")))) }
'''),
    ("money: a negative percentage of a positive amount is negative", "cut", "E601", '''
fn cut(m: Money of INR, p: Int) -> Money of INR
  requires m >= money(0, "INR")
  ensures result >= money(0, "INR")
{ return percent_of(m, p, 100, "half_up") }
fn main() uses io { print(to_text(cut(money(100, "INR"), -10))) }
'''),
    ("money: a fee on zero is not less than zero", "fee", "E601", '''
fn fee(m: Money of C) -> Money of C for any C
  requires units_of(m) >= 0
  ensures units_of(result) < units_of(m)
{ return percent_of(m, 10, 100, "half_up") }
fn main() uses io { print(to_text(fee(money(0, "USD")))) }
'''),
    ("money: a percent_of whose denominator can be zero", "share", "E403", '''
fn share(m: Money of INR, d: Int) -> Money of INR
  requires m >= money(0, "INR")
  ensures result <= m
{ return percent_of(m, 1, d, "down") }
fn main() uses io { print(to_text(share(money(100, "INR"), 0))) }
'''),
    ("money: splitting 1 paisa two ways leaves a zero part", "halves", "E601", '''
import "money.vel" as money
fn positive(m: Money of INR) -> Bool { return m > money(0, "INR") }
fn halves(m: Money of INR) -> List of Money of INR
  requires m > money(0, "INR")
  ensures all_of(result, positive)
{ return money.split(m, 2) }
fn main() uses io { print(to_text(halves(money(1, "INR")))) }
'''),
    ("money: the parts of a negative amount are not all non-negative", "parts", "E601", '''
import "money.vel" as money
fn not_negative(m: Money of INR) -> Bool { return m >= money(0, "INR") }
fn parts(m: Money of INR, ways: Int) -> List of Money of INR
  requires ways > 0
  ensures all_of(result, not_negative)
{ return money.split(m, ways) }
fn main() uses io { print(to_text(parts(money(-3, "INR"), 2))) }
'''),
    ("money: 10 paise three ways does not start with 3", "thirds", "E601", '''
import "money.vel" as money
fn thirds(m: Money of INR) -> List of Money of INR
  requires units_of(m) == 10
  ensures units_of(get(result, 0)) == 3
{ return money.split(m, 3) }
fn main() uses io { print(to_text(thirds(money(10, "INR")))) }
'''),
    ("money: a split one way is one part, not two", "parts", "E601", '''
import "money.vel" as money
fn parts(m: Money of INR, ways: Int) -> List of Money of INR
  requires ways > 0
  ensures length(result) >= 2
{ return money.split(m, ways) }
fn main() uses io { print(to_text(parts(money(500, "INR"), 1))) }
'''),
    ("money: a total of amounts is not always non-negative", "total", "E601", '''
fn total(xs: List of Money of INR) -> Money of INR
  ensures result >= money(0, "INR")
{ return money(units_of(xs), "INR") }
fn main() uses io { print(to_text(total([money(-1, "INR")]))) }
'''),
    ("money: non-negative amounts do not add up to more than zero", "total", "E601", '''
fn not_negative(m: Money of INR) -> Bool { return m >= money(0, "INR") }
fn total(xs: List of Money of INR) -> Money of INR
  requires all_of(xs, not_negative)
  ensures result > money(0, "INR")
{ return money(units_of(xs), "INR") }
fn main() uses io {
  let none: List of Money of INR = []
  print(to_text(total(none)))
}
'''),
    ("money: an amount times 2 does not wrap past 64 bits", "doubled", "E407", '''
fn doubled(m: Money of INR) -> Money of INR
  requires units_of(m) == 9223372036854775807
  ensures units_of(result) < 0
{ return m * 2 }
fn main() uses io { print(to_text(doubled(money(9223372036854775807, "INR")))) }
'''),
    ("money: a difference of non-negative amounts can be negative", "change", "E601", '''
fn change(paid: Money of INR, price: Money of INR) -> Money of INR
  requires paid >= money(0, "INR") and price >= money(0, "INR")
  ensures result >= money(0, "INR")
{ return paid - price }
fn main() uses io { print(to_text(change(money(100, "INR"), money(250, "INR")))) }
'''),
    ("money: with_units does not keep the amount", "reset", "E601", '''
fn reset(m: Money of EUR) -> Money of EUR
  ensures result == m
{ return with_units(m, 0) }
fn main() uses io { print(to_text(reset(money(5, "EUR")))) }
'''),
    ("money: divide_or_fail half_up takes 11/3 to 4, not 3", "third", "E601", '''
fn third(m: Money of INR) -> Money of INR or fail
  requires units_of(m) == 11
  ensures units_of(result) == 3
{ return try divide_or_fail(m, 3, "half_up") }
fn main() uses io {
  check third(money(11, "INR")) {
    ok part { print(text_of(part)) }
    fail why { print(why) }
  }
}
'''),
]

QUANTIFIERS = [
    ("all_of: pushing a zero breaks every-element-positive", "stamp", "E601", '''
fn is_pos(n: Int) -> Bool { return n > 0 }
fn stamp(xs: List of Int) -> List of Int
  requires all_of(xs, is_pos)
  ensures all_of(result, is_pos)
{ return push(xs, 0) }
fn main() uses io { print(to_text(stamp([3, 1, 4]))) }
'''),
    ("all_of: every element positive does not mean non-empty", "count", "E601", '''
fn is_pos(n: Int) -> Bool { return n > 0 }
fn count(xs: List of Int) -> Int
  requires all_of(xs, is_pos)
  ensures result > 0
{ return length(xs) }
fn main() uses io {
  let none: List of Int = []
  print(to_text(count(none)))
}
'''),
    ("any_of: one positive does not make all positive", "size", "E601", '''
fn is_pos(n: Int) -> Bool { return n > 0 }
fn size(xs: List of Int) -> Int
  requires any_of(xs, is_pos)
  ensures all_of(xs, is_pos)
{ return length(xs) }
fn main() uses io { print(to_text(size([1, -1]))) }
'''),
    ("any_of: one positive does not make the first positive", "head", "E601", '''
fn is_pos(n: Int) -> Bool { return n > 0 }
fn head(xs: List of Int) -> Int
  requires length(xs) > 0 and any_of(xs, is_pos)
  ensures result > 0
{ return get(xs, 0) }
fn main() uses io { print(to_text(head([-1, 2]))) }
'''),
    ("all_of: non-negative is not positive", "same", "E601", '''
fn is_pos(n: Int) -> Bool { return n > 0 }
fn is_nonneg(n: Int) -> Bool { return n >= 0 }
fn same(xs: List of Int) -> List of Int
  requires all_of(xs, is_nonneg)
  ensures all_of(result, is_pos)
{ return xs }
fn main() uses io { print(to_text(same([0]))) }
'''),
    ("any_of: pushing a zero onto an empty list gives no positive", "with", "E601", '''
fn is_pos(n: Int) -> Bool { return n > 0 }
fn with(xs: List of Int, v: Int) -> List of Int
  requires v >= 0
  ensures any_of(result, is_pos)
{ return push(xs, v) }
fn main() uses io {
  let none: List of Int = []
  print(to_text(with(none, 0)))
}
'''),
    ("any_of: no negatives before a push is not none after", "with", "E601", '''
fn is_neg(n: Int) -> Bool { return n < 0 }
fn with(xs: List of Int, v: Int) -> List of Int
  requires not any_of(xs, is_neg)
  ensures not any_of(result, is_neg)
{ return push(xs, v) }
fn main() uses io { print(to_text(with([1], -1))) }
'''),
    ("all_of: a filter that keeps zero is not all positive", "keep", "E601", '''
fn is_pos(n: Int) -> Bool { return n > 0 }
fn keep(xs: List of Int) -> List of Int
  ensures all_of(result, is_pos)
{
  let out: List of Int = []
  let i = 0
  while i < length(xs) {
    if get(xs, i) >= 0 {
      out = push(out, get(xs, i))
    }
    i = i + 1
  }
  return out
}
fn main() uses io { print(to_text(keep([0, 3]))) }
'''),
    ("all_of: doubling small numbers does not keep them small", "doubled", "E601", '''
fn is_small(n: Int) -> Bool { return n < 100 }
fn doubled(xs: List of Int) -> List of Int
  requires all_of(xs, is_small)
  ensures all_of(result, is_small)
{
  let out: List of Int = []
  for x in xs {
    out = push(out, x * 2)
  }
  return out
}
fn main() uses io { print(to_text(doubled([60]))) }
'''),
    # the prover reads the predicate's body, so a name that says more than
    # the body does must not help
    ("all_of: the predicate's body counts, not its name", "head", "E601", '''
fn is_pos(n: Int) -> Bool { return n >= 0 }
fn head(xs: List of Int) -> Int
  requires length(xs) > 0 and all_of(xs, is_pos)
  ensures result != 0
{ return get(xs, 0) }
fn main() uses io { print(to_text(head([0]))) }
'''),
    ("all_of: adding 2 to odd numbers does not make them even", "bump_all", "E601", '''
fn is_odd(n: Int) -> Bool { return n % 2 == 1 }
fn is_even(n: Int) -> Bool { return n % 2 == 0 }
fn bump_all(xs: List of Int) -> List of Int
  requires all_of(xs, is_odd)
  ensures all_of(result, is_even)
{
  let out: List of Int = []
  for x in xs {
    out = push(out, x + 2)
  }
  return out
}
fn main() uses io { print(to_text(bump_all([1]))) }
'''),
    ("all_of and any_of differ on the empty list", "some", "E601", '''
fn is_pos(n: Int) -> Bool { return n > 0 }
fn some(xs: List of Int) -> Bool
  ensures result == any_of(xs, is_pos)
{ return all_of(xs, is_pos) }
fn main() uses io {
  let none: List of Int = []
  print(to_text(some(none)))
}
'''),
    ("all_of: not all positive does not mean none positive", "size", "E601", '''
fn is_pos(n: Int) -> Bool { return n > 0 }
fn size(xs: List of Int) -> Int
  requires not all_of(xs, is_pos)
  ensures not any_of(xs, is_pos)
{ return length(xs) }
fn main() uses io { print(to_text(size([1, -1]))) }
'''),
    ("all_of: positive items do not add up to more than their count", "sum", "E601", '''
fn is_pos(n: Int) -> Bool { return n > 0 }
fn sum(xs: List of Int) -> Int
  requires all_of(xs, is_pos)
  ensures result > length(xs)
{
  let total = 0
  for x in xs {
    total = total + x
  }
  return total
}
fn main() uses io { print(to_text(sum([1]))) }
'''),
    ("all_of over records: cheap items are not a cheap basket", "basket", "E601", '''
record Item { price: Int }
fn cheap(i: Item) -> Bool { return i.price < 10 }
fn basket(items: List of Item) -> Int
  requires all_of(items, cheap)
  ensures result < 10
{
  let total = 0
  for it in items {
    total = total + it.price
  }
  return total
}
fn main() uses io { print(to_text(basket([Item(price: 6), Item(price: 7)]))) }
'''),
    ("all_of over text: short words and a long one", "with", "E601", '''
fn short(w: Text) -> Bool { return length(w) < 5 }
fn with(ws: List of Text, w: Text) -> List of Text
  requires all_of(ws, short) and short(w)
  ensures all_of(result, short)
{ return push(ws, w + w) }
fn main() uses io { print(to_text(with(["a"], "abcd"))) }
'''),
]

# A recursive call is assumed to keep its callee's promise, so the base
# case is where each of these is false: a proof by induction with no true
# base must not come back proven.
RECURSION = [
    ("recursion: count_down reaches zero, not above it", "count_down", "E601", '''
fn count_down(n: Int) -> Int
  requires n >= 0
  ensures result > 0
{
  if n == 0 { return 0 }
  return count_down(n - 1)
}
fn main() uses io { print(to_text(count_down(3))) }
'''),
    ("recursion: 1! is not larger than 1", "fact", "E601", '''
fn fact(n: Int) -> Int
  requires n >= 0
  ensures result > n
{
  if n == 0 { return 1 }
  return n * fact(n - 1)
}
fn main() uses io { print(to_text(fact(1))) }
'''),
    ("recursion: a triangle number is not n * (n + 1)", "triangle", "E601", '''
fn triangle(n: Int) -> Int
  requires n >= 0
  ensures result == n * (n + 1)
{
  if n == 0 { return 0 }
  return n + triangle(n - 1)
}
fn main() uses io { print(to_text(triangle(3))) }
'''),
    ("recursion: fib(2) is below 2", "fib", "E601", '''
fn fib(n: Int) -> Int
  requires n >= 0
  ensures result >= n
{
  if n < 2 { return n }
  return fib(n - 1) + fib(n - 2)
}
fn main() uses io { print(to_text(fib(2))) }
'''),
    ("recursion: sum of a list from a position can be negative", "sum_from", "E601", '''
fn sum_from(xs: List of Int, i: Int) -> Int
  requires i >= 0 and i <= length(xs)
  ensures result >= 0
{
  if i == length(xs) { return 0 }
  return get(xs, i) + sum_from(xs, i + 1)
}
fn main() uses io { print(to_text(sum_from([2, -5], 0))) }
'''),
    ("recursion: b to the 0 is 1, not at least b", "power", "E601", '''
fn power(b: Int, e: Int) -> Int
  requires e >= 0
  ensures result >= b
{
  if e == 0 { return 1 }
  return b * power(b, e - 1)
}
fn main() uses io { print(to_text(power(2, 0))) }
'''),
    ("recursion: gcd(0, 0) is 0", "gcd", "E601", '''
fn gcd(a: Int, b: Int) -> Int
  requires a >= 0 and b >= 0
  ensures result > 0
{
  if b == 0 { return a }
  return gcd(b, a % b)
}
fn main() uses io { print(to_text(gcd(0, 0))) }
'''),
    ("recursion: a one-digit number has one digit", "digits", "E601", '''
fn digits(n: Int) -> Int
  requires n >= 0
  ensures result >= 2
{
  if n < 10 { return 1 }
  return 1 + digits(n / 10)
}
fn main() uses io { print(to_text(digits(5))) }
'''),
    ("recursion: halving steps of 2 is 1, and 2 is not below 2", "steps", "E601", '''
fn steps(n: Int) -> Int
  requires n >= 1
  ensures result * 2 < n
{
  if n == 1 { return 0 }
  return 1 + steps(n / 2)
}
fn main() uses io { print(to_text(steps(2))) }
'''),
    ("recursion: a list built to n has n items, not n + 1", "upto", "E601", '''
fn upto(n: Int) -> List of Int
  requires n >= 0
  ensures length(result) == n + 1
{
  if n == 0 {
    let none: List of Int = []
    return none
  }
  return push(upto(n - 1), n)
}
fn main() uses io { print(to_text(upto(2))) }
'''),
    ("recursion: an accumulator is not strictly above its start", "sum_acc", "E601", '''
fn sum_acc(n: Int, acc: Int) -> Int
  requires n >= 0
  ensures result > acc + n
{
  if n == 0 { return acc }
  return sum_acc(n - 1, acc + n)
}
fn main() uses io { print(to_text(sum_acc(2, 0))) }
'''),
    ("recursion: a recursive call that breaks its own requires", "down", "E600", '''
fn down(n: Int) -> Int
  requires n > 0
  ensures result >= 0
{
  if n == 1 { return 0 }
  return down(n - 2)
}
fn main() uses io { print(to_text(down(2))) }
'''),
    ("recursion over Money: nothing taken off is not less", "drain", "E601", '''
fn drain(m: Money of INR, n: Int) -> Money of INR
  requires n >= 0
  ensures result < m
{
  if n == 0 { return m }
  return drain(m - money(1, "INR"), n - 1)
}
fn main() uses io { print(to_text(drain(money(5, "INR"), 2))) }
'''),
    ("mutual recursion: 1 is not even", "is_even", "E601", '''
fn is_even(n: Int) -> Bool
  requires n >= 0
  ensures result
{
  if n == 0 { return true }
  return is_odd(n - 1)
}
fn is_odd(n: Int) -> Bool
  requires n >= 0
{
  if n == 0 { return false }
  return is_even(n - 1)
}
fn main() uses io { print(to_text(is_even(1))) }
'''),
    # is_even's promise is true; is_odd's is is_even's, copied
    ("mutual recursion: is_odd promises the parity of is_even", "is_odd", "E601", '''
fn is_even(n: Int) -> Bool
  requires n >= 0
  ensures result == (n % 2 == 0)
{
  if n == 0 { return true }
  return is_odd(n - 1)
}
fn is_odd(n: Int) -> Bool
  requires n >= 0
  ensures result == (n % 2 == 0)
{
  if n == 0 { return false }
  return is_even(n - 1)
}
fn main() uses io { print(to_text(is_odd(0))) }
'''),
    ("mutual recursion: ping always ends at 0", "ping", "E601", '''
fn ping(n: Int) -> Int
  requires n >= 0
  ensures result >= n
{
  if n == 0 { return 0 }
  return pong(n - 1)
}
fn pong(n: Int) -> Int
  requires n >= 0
  ensures result >= 0
{
  if n == 0 { return 0 }
  return ping(n - 1)
}
fn main() uses io { print(to_text(ping(1))) }
'''),
    ("mutual recursion: three functions, the last promises too much", "three", "E601", '''
fn one(n: Int) -> Int
  requires n >= 0
  ensures result >= 0
{
  if n == 0 { return 0 }
  return two(n - 1) + 1
}
fn two(n: Int) -> Int
  requires n >= 0
  ensures result >= 0
{
  if n == 0 { return 0 }
  return three(n - 1) + 1
}
fn three(n: Int) -> Int
  requires n >= 0
  ensures result > n
{
  if n == 0 { return 0 }
  return one(n - 1) + 1
}
fn main() uses io { print(to_text(three(4))) }
'''),
]

# Loops and invariants, lists, maps, records, text, generics, a caller
# breaking a requires, division.
OTHER = [
    ("loop: an invariant false on entry", "climb", "E704", '''
fn climb(n: Int) -> Int
  requires n >= 1
  ensures result >= 0
{
  let i = 0
  while i < n
    invariant i > 0
  { i = i + 1 }
  return i
}
fn main() uses io { print(to_text(climb(3))) }
'''),
    ("loop: an invariant a step breaks", "running", "E704", '''
fn running(n: Int) -> Int
  requires n >= 0
  ensures result >= 0
{
  let total = 0
  for i in 0 to n
    invariant total <= 10
  { total = total + i }
  return total
}
fn main() uses io { print(to_text(running(7))) }
'''),
    ("loop: 0 to n runs n times, not n + 1", "turns", "E601", '''
fn turns(n: Int) -> Int
  requires n >= 0
  ensures result == n + 1
{
  let c = 0
  for i in 0 to n { c = c + 1 }
  return c
}
fn main() uses io { print(to_text(turns(3))) }
'''),
    ("loop: counting down stops at zero, not one", "countdown", "E601", '''
fn countdown(n: Int) -> Int
  requires n >= 1
  ensures result == 1
{
  let i = n
  while i > 0 { i = i - 1 }
  return i
}
fn main() uses io { print(to_text(countdown(3))) }
'''),
    ("loop: a list built n times has n items", "built", "E601", '''
fn built(n: Int) -> List of Int
  requires n >= 1
  ensures length(result) == n - 1
{
  let out: List of Int = []
  for i in 0 to n { out = push(out, i) }
  return out
}
fn main() uses io { print(to_text(built(2))) }
'''),
    ("loop: a search that finds nothing returns -1", "find", "E601", '''
fn find(xs: List of Int, wanted: Int) -> Int
  ensures result >= 0
{
  let i = 0
  let found = false
  let at = -1
  while i < length(xs) and not found {
    if get(xs, i) == wanted {
      found = true
      at = i
    }
    i = i + 1
  }
  return at
}
fn main() uses io { print(to_text(find([1, 2], 9))) }
'''),
    ("loop: reading up to and including the length", "total", "E602", '''
fn total(xs: List of Int) -> Int {
  let s = 0
  let i = 0
  while i <= length(xs) {
    s = s + get(xs, i)
    i = i + 1
  }
  return s
}
fn main() uses io { print(to_text(total([1, 2]))) }
'''),
    ("list: push does not keep the length", "grow", "E601", '''
fn grow(xs: List of Int, v: Int) -> List of Int
  ensures length(result) == length(xs)
{ return push(xs, v) }
fn main() uses io { print(to_text(grow([1], 2))) }
'''),
    ("list: the first item of a list that can be empty", "head", "E602", '''
fn head(xs: List of Int) -> Int { return get(xs, 0) }
fn main() uses io {
  let none: List of Int = []
  print(to_text(head(none)))
}
'''),
    ("list: the last item is not the first", "first", "E601", '''
fn first(xs: List of Int) -> Int
  requires length(xs) >= 1
  ensures result == get(xs, 0)
{ return get(xs, length(xs) - 1) }
fn main() uses io { print(to_text(first([1, 2]))) }
'''),
    ("list: a position below the length can be negative", "at", "E602", '''
fn at(xs: List of Int, i: Int) -> Int
  requires i < length(xs)
{ return get(xs, i) }
fn main() uses io { print(to_text(at([1], -1))) }
'''),
    ("map: a count goes up by one, not two", "bump", "E601", '''
fn bump(counts: Map of Text to Int, word: Text) -> Map of Text to Int
  ensures get_or(result, word, 0) == get_or(counts, word, 0) + 2
{ return put(counts, word, get_or(counts, word, 0) + 1) }
fn main() uses io { print(to_text(get_or(bump({ "a": 1 }, "a"), "a", 0))) }
'''),
    ("map: put makes one key present, not another", "store", "E601", '''
fn store(m: Map of Text to Int, k: Text, other: Text) -> Map of Text to Int
  ensures has(result, other)
{ return put(m, k, 1) }
fn main() uses io { print(to_text(store({ "a": 1 }, "a", "b"))) }
'''),
    ("map: get_or of a present key is its value, not the default", "lookup", "E601", '''
fn lookup(m: Map of Text to Int, k: Text, fallback: Int) -> Int
  ensures result == fallback
{ return get_or(m, k, fallback) }
fn main() uses io { print(to_text(lookup({ "a": 1 }, "a", 5))) }
'''),
    ("map: put overwrites the value that was there", "overwrite", "E601", '''
fn overwrite(m: Map of Int to Int, k: Int) -> Map of Int to Int
  requires has(m, k)
  ensures get_or(result, k, 0) == get_or(m, k, 0)
{ return put(m, k, 7) }
fn main() uses io { print(to_text(overwrite({ 1: 1 }, 1))) }
'''),
    ("record: fields swapped in the constructor", "shift", "E601", '''
record Point { x: Int  y: Int }
fn shift(p: Point, dx: Int) -> Point
  ensures result.x == p.x + dx
{ return Point(x: p.y + dx, y: p.x) }
fn main() uses io { print(to_text(shift(Point(x: 3, y: 4), 10))) }
'''),
    ("record: a list field grows by one, not two", "add_item", "E601", '''
record Basket { owner: Text  items: List of Int }
fn add_item(b: Basket, price: Int) -> Basket
  ensures length(result.items) == length(b.items) + 2
{ return Basket(owner: b.owner, items: push(b.items, price)) }
fn main() uses io { print(to_text(add_item(Basket(owner: "gowri", items: [1]), 2))) }
'''),
    ("record: a text field that is not kept", "rename", "E601", '''
record Basket { owner: Text  items: List of Int }
fn rename(b: Basket) -> Basket
  ensures result.owner == b.owner
{ return Basket(owner: "someone", items: b.items) }
fn main() uses io { print(to_text(rename(Basket(owner: "gowri", items: [1])))) }
'''),
    ("text: joining two texts is longer than the first", "join", "E601", '''
fn join(a: Text, b: Text) -> Text
  ensures length(result) == length(a)
{ return a + b }
fn main() uses io { print(join("x", "y")) }
'''),
    # Z3 does not settle this within the 3s a query gets (upper is only
    # known to keep the length), so the proof is abandoned under every
    # seed - the path "abandoned is not proven" goes through
    ("text: upper keeps the length, not the text", "shout", "E601", '''
fn shout(t: Text) -> Text
  ensures result == t
{ return upper(t) }
fn main() uses io { print(shout("abc")) }
'''),
    ("text: a text that does not contain the mark", "marked", "E601", '''
fn marked(t: Text) -> Text
  ensures contains(result, "!")
{ return t }
fn main() uses io { print(marked("hi")) }
'''),
    ("generic: the last item is not the first, for any T", "pick", "E601", '''
fn pick(xs: List of T) -> T for any T
  requires length(xs) > 0
  ensures result == get(xs, 0)
{ return get(xs, length(xs) - 1) }
fn main() uses io { print(to_text(pick([1, 2]))) }
'''),
    ("generic: a push changes the length, for any T", "again", "E601", '''
fn again(xs: List of T) -> List of T for any T
  requires length(xs) > 0
  ensures length(result) == length(xs)
{ return push(xs, get(xs, 0)) }
fn main() uses io { print(to_text(again(["a"]))) }
'''),
    ("requires: a caller that can pass zero to a positive requires", "caller", "E600", '''
fn per_head(n: Int) -> Int
  requires n > 0
{ return 100 / n }
fn caller(k: Int) -> Int
  requires k >= 0
{ return per_head(k) }
fn main() uses io { print(to_text(caller(0))) }
'''),
    ("requires: a caller that can pass an empty list", "caller", "E600", '''
fn head(xs: List of Int) -> Int
  requires length(xs) > 0
{ return get(xs, 0) }
fn caller(xs: List of Int) -> Int { return head(xs) }
fn main() uses io {
  let none: List of Int = []
  print(to_text(caller(none)))
}
'''),
    ("requires: a loop counter that starts at zero", "caller", "E600", '''
fn per_head(n: Int) -> Int
  requires n > 0
{ return 100 / n }
fn caller(m: Int) -> Int
  requires m >= 0
{
  let total = 0
  for i in 0 to m {
    total = total + per_head(i)
  }
  return total
}
fn main() uses io { print(to_text(caller(2))) }
'''),
    ("division: a difference that can be zero", "rate", "E403", '''
fn rate(a: Int, b: Int) -> Int
  requires a >= b
{ return 100 / (a - b) }
fn main() uses io { print(to_text(rate(3, 3))) }
'''),
    ("division: an average over a count that can be zero", "average", "E403", '''
fn average(total: Int, count: Int) -> Int
  requires count >= 0
  ensures result * count <= total
{ return total / count }
fn main() uses io { print(to_text(average(10, 0))) }
'''),
    ("division: -7 / 2 floors to -4, not -3", "half", "E601", '''
fn half(n: Int) -> Int
  requires n == -7
  ensures result == -3
{ return n / 2 }
fn main() uses io { print(to_text(half(-7))) }
'''),
    ("division: -7 % 2 takes the divisor's sign, 1 not -1", "parity", "E601", '''
fn parity(n: Int) -> Int
  requires n == -7
  ensures result == -1
{ return n % 2 }
fn main() uses io { print(to_text(parity(-7))) }
'''),
    ("division: 7 / -2 floors to -4, not -3", "split_by", "E601", '''
fn split_by(d: Int) -> Int
  requires d == -2
  ensures result == -3
{ return 7 / d }
fn main() uses io { print(to_text(split_by(-2))) }
'''),
    ("bool: not (a and b) is not (not a and not b)", "nand", "E601", '''
fn nand(a: Bool, b: Bool) -> Bool
  ensures result == (not a and not b)
{ return not (a and b) }
fn main() uses io { print(to_text(nand(true, false))) }
'''),
]

CATEGORIES = [
    ("before 8.2", EARLIER),
    ("floats", FLOATS),
    ("overflow", OVERFLOW),
    ("money", MONEY),
    ("quantifiers", QUANTIFIERS),
    ("recursion", RECURSION),
    ("loops, lists, maps, records, text, generics, requires, division",
     OTHER),
]
LIES = [case for _, cases in CATEGORIES for case in cases]

# Found writing this corpus (8.2), and a Goal A break: unary minus on an Int
# was not range-checked. The prover reads -n as a whole number's negation,
# positive for every n < 0, and reports both promises below proven - which is
# right of every value that fits. But -MIN is 2^63, which does not fit: the
# interpreter returned it, and native code wrapped it back to MIN, so a run
# printed -9223372036854775808 for a result promised positive
# (advisory-int-negation.md). From 8.2 -MIN stops with E407 in both engines,
# as MAX + 1 always did. Each promise is then true of every return, so it
# may be proven, and these are not lies; what must hold is that no run
# returns what the promise denies.
EDGES = [
    ("negating MIN stops (E407), and never returns a number that is not "
     "positive", '''
fn negate(n: Int) -> Int
  requires n < 0
  ensures result > 0
{ return -n }
fn main() uses io { print(to_text(negate(-9223372036854775807 - 1))) }
'''),
    ("the absolute value of MIN stops (E407), and never returns a negative "
     "number", '''
fn magnitude(n: Int) -> Int
  ensures result >= 0
{
  if n < 0 { return -n }
  return n
}
fn main() uses io { print(to_text(magnitude(-9223372036854775807 - 1))) }
'''),
]

# The effects a case's run is granted, where io is not enough.
ALLOW = {"ensures over a Secret parameter is false": {"io", "env"}}

# Identifiers spelled like SMT-LIB, and text holding SMT-LIB, are what they
# are in Velaris: names and text. The prover builds its queries from the
# syntax tree through Z3's API, never from contract text (8.1 confirmed it:
# no query is parsed from a string), so `assert` is a parameter and
# "(assert false)" is six words of text. A true promise over them proves;
# a false one does not, and breaks when main runs it (E601).
IDENTIFIERS = [
    ("parameters named assert, ite, select, store, forall, distinct",
     "f", True, '''
fn f(assert: Int, ite: Int, select: Int, store: Int, forall: Int, distinct: Int) -> Int
  requires assert > 0 and ite > 0
  ensures result > select + store + forall + distinct
{ return select + store + forall + distinct + assert + ite }
fn main() uses io { print(to_text(f(1, 1, 1, 1, 1, 1))) }
'''),
    ("a false promise over a parameter named assert", "f", False, '''
fn f(assert: Int, ite: Int) -> Int
  ensures result == assert
{ return ite }
fn main() uses io { print(to_text(f(1, 2))) }
'''),
    ("text holding SMT-LIB is text", "f", False, '''
fn f(t: Text) -> Text
  ensures result != "(assert false)"
{ return t }
fn main() uses io { print(f("(assert false)")) }
'''),
    ("a field named xs__n beside a list xs, with a true promise", "f", True, '''
record Box { xs: List of Int  xs__n: Int }
fn f(b: Box) -> Int
  requires length(b.xs) == 2
  ensures result == 2
{ return length(b.xs) }
fn main() uses io { print(to_text(f(Box(xs: [1, 2], xs__n: 9)))) }
'''),
]


def check_here(src: str) -> tuple[Any, ...]:
    """check() in this process with no ceiling, so VELARIS_PROVER_SEED
    reaches every solver. (result or None, whether a proof was abandoned,
    what a crash said.)"""
    notes = io.StringIO()
    try:
        with contextlib.redirect_stderr(notes):
            result = velaris.check(src, timeout=None, max_memory_mb=None)
    except Exception as e:            # a crash is not "proven", but say so
        return None, False, f"{type(e).__name__}: {e}"
    return result, ABANDONED_NOTE in notes.getvalue(), ""


def sweep(src: str) -> dict[Any, Any]:
    """{seed: check_here(src)} for every seed, putting the variable back
    as it was afterwards."""
    saved = os.environ.get(SEED_ENV)
    try:
        seen = {}
        for seed in SEEDS:
            os.environ[SEED_ENV] = str(seed)
            seen[seed] = check_here(src)
        return seen
    finally:
        if saved is None:
            os.environ.pop(SEED_ENV, None)
        else:
            os.environ[SEED_ENV] = saved


def verdict(result: Any) -> tuple[Any, ...]:
    return (tuple(sorted(result.proven)),
            tuple(sorted(p.code for p in result.problems)))


def shared_findings(name: str, seen: dict[Any, Any]) -> list[Any]:
    """What every case is held to whatever its promise: it compiles, or
    is refused only by the prover; and with z3 its verdict does not move
    with the seed. A list of (word, detail) for what failed."""
    bad = []
    crashed = [s for s, (r, _, _) in seen.items() if r is None]
    wrong = {}
    for s, (r, _, _) in seen.items():
        if r is None:
            continue
        codes = sorted(p.code for p in r.problems)
        # without the prover it must compile; with it, only E7xx may refuse
        off = [c for c in codes if not (HAVE_Z3 and c in PROVER_CODES)]
        if off:
            wrong[s] = [f"{p.code} line {p.line}: {p.message[:120]}"
                        for p in r.problems if p.code in off]
    if crashed:
        bad.append(("MALFORMED", f"check crashed under seed(s) {crashed}: "
                                 f"{seen[crashed[0]][2]}"))
    if wrong:
        first = sorted(wrong)[0]
        bad.append(("MALFORMED", f"refused by more than the prover under "
                                 f"seed(s) {sorted(wrong)}: {wrong[first]}"))
    for s, (r, abandoned, _) in seen.items():
        if abandoned:
            TIMEOUTS.append((name, s))
    if HAVE_Z3:
        settled = {s: verdict(r) for s, (r, abandoned, _) in seen.items()
                   if r is not None and not abandoned}
        if len(set(settled.values())) > 1:
            shown = "; ".join(f"seed {s}: proven {list(v[0])} codes "
                              f"{list(v[1])}" for s, v in settled.items())
            bad.append(("SEED-DEPENDENT", shown))
    return bad


def run_findings(name: str, src: str, stops: str) -> list[Any]:
    """The promise really is false: run, main hands over the input that
    breaks it, and the run must not end ok."""
    allowed = set(stops.split()) | (set(PROVER_CODES) if HAVE_Z3 else set())
    try:
        r = velaris.run(src, allow=ALLOW.get(name, {"io"}),
                        timeout=RUN_SECONDS)
    except Exception as e:
        return [("NOT A LIE", f"run crashed: {type(e).__name__}: {e}")]
    codes = sorted({p.code for p in r.problems})
    if r.ok:
        return [("NOT A LIE", f"ran to the end and printed "
                              f"{r.output.strip()!r}")]
    if r.timed_out or r.out_of_memory:
        return [("NOT A LIE", "the run hit its own time or memory limit, "
                              "which shows nothing about the promise")]
    if not codes or set(codes) - allowed:
        detail = "; ".join(f"{p.code}: {p.message[:120]}" for p in r.problems)
        return [("NOT A LIE", f"stopped with {codes or 'no code'}, not "
                              f"{stops} or a prover refusal: {detail}")]
    return []


def tally(name: str, asserted: int, bad: list[Any]) -> None:
    global PASS, FAIL
    failed = len({word for word, _ in bad})    # one word, one assertion
    FAIL += failed
    PASS += asserted - failed
    if not bad:
        print(f"  ok    {name}")
    for word, detail in bad:
        # a compiler message can hold any character; a cp1252 console
        # cannot print them all
        detail = detail.encode("ascii", "backslashreplace").decode("ascii")
        print(f"  {word}  {name}   {detail}")


def judge_lie(name: str, liar: str, stops: str, src: str) -> None:
    src = src.strip() + "\n"
    seen = sweep(src)
    bad = []
    # the one thing that must never happen: the lying function is reported
    # proven, under any seed. (It may compile with a runtime check, or be
    # refused outright; both are fine - proven is not.)
    proven_under = [s for s, (r, _, _) in seen.items()
                    if r is not None and liar in r.proven]
    if proven_under:
        bad.append(("LIE PROVEN", f"'{liar}' was reported proven under "
                                  f"seed(s) {proven_under}"))
    bad += shared_findings(name, seen)
    bad += run_findings(name, src, stops)
    # never proven, well-formed, really a lie; and with z3 one verdict
    tally(name, 4 if HAVE_Z3 else 3, bad)


def judge_edge(name: str, src: str) -> None:
    """A promise true of every value that fits, given one that does not: it
    is well-formed and one verdict under every seed, and both runs - native
    code and the interpreter - stop with E407 having printed nothing."""
    src = src.strip() + "\n"
    bad = shared_findings(name, sweep(src))
    for native in (True, False):
        engine = "native" if native else "interpreted"
        try:
            r = velaris.run(src, allow={"io"}, native=native,
                            timeout=RUN_SECONDS)
        except Exception as e:
            bad.append(("WRONG RUN", f"{engine}: {type(e).__name__}: {e}"))
            continue
        codes = sorted({p.code for p in r.problems})
        if r.ok or codes != ["E407"] or r.output.strip():
            bad.append(("WRONG RUN", f"{engine}: ok={r.ok} codes={codes} "
                                     f"printed {r.output.strip()!r}"))
    # well-formed, the runs stop, and with z3 one verdict
    tally(name, 3 if HAVE_Z3 else 2, bad)


def judge_identifier(name: str, fn: str, true: bool, src: str) -> None:
    src = src.strip() + "\n"
    seen = sweep(src)
    bad = shared_findings(name, seen)
    results = [(s, r) for s, (r, _, _) in seen.items() if r is not None]
    if true:
        label = name + (" - proven" if HAVE_Z3 else
                        " - compiles (no prover: nothing is proven)")
        missed = [s for s, r in results
                  if not r.ok or ((fn not in r.proven) if HAVE_Z3
                                  else bool(r.proven))]
        if missed:
            s, r = [x for x in results if x[0] == missed[0]][0]
            bad.append(("NOT PROVEN", f"under seed(s) {missed}: ok={r.ok} "
                                      f"proven={list(r.proven)} "
                                      f"{[p.code for p in r.problems]}"))
    else:
        label = name + " - never proven"
        proven_under = [s for s, r in results if fn in r.proven]
        if proven_under:
            bad.append(("LIE PROVEN", f"'{fn}' was reported proven under "
                                      f"seed(s) {proven_under}"))
        bad += run_findings(name, src, "E601")
    # the promise's verdict, well-formed, and with z3 one verdict; a false
    # one is also run
    tally(label, (3 if HAVE_Z3 else 2) + (0 if true else 1), bad)


def main() -> int:
    started = time.monotonic()
    if PROOF_SECONDS is not None:
        velaris.set_proof_timeout(PROOF_SECONDS)
        # and for the children run() starts, which prove the program again
        os.environ["VELARIS_PROOF_TIMEOUT"] = str(PROOF_SECONDS)
    counts = ", ".join(f"{len(cases)} {what}" for what, cases in CATEGORIES)
    print(f"prover-lie corpus ({len(LIES)} lies: {counts}), z3 "
          + ("present" if HAVE_Z3 else "absent")
          + f", seeds {SEEDS[0]}-{SEEDS[-1]}")
    budget = (f"{PROOF_SECONDS:g}s a query" if PROOF_SECONDS is not None
              else "velaris's own budgets")
    print(f"proofs get {budget}")
    for what, cases in CATEGORIES:
        print("-" * 62)
        print(f"{what} ({len(cases)})")
        for name, liar, stops, src in cases:
            judge_lie(name, liar, stops, src)
    print("-" * 62)
    print(f"64-bit edges that were lies until 8.2 ({len(EDGES)})")
    for name, src in EDGES:
        judge_edge(name, src)
    print("-" * 62)
    print("identifiers and text spelled like SMT-LIB (8.1)")
    for name, fn, true, src in IDENTIFIERS:
        judge_identifier(name, fn, true, src)
    print("-" * 62)
    if TIMEOUTS:
        print(f"{len(TIMEOUTS)} check(s) abandoned a proof, and were left out "
              f"of the seed comparison for that seed:")
        for name, seed in TIMEOUTS:
            print(f"    seed {seed}: {name}")
    print(f"{PASS} assertion(s) held, {FAIL} failed "
          f"({time.monotonic() - started:.0f}s)")
    if not HAVE_Z3:
        print("(without z3 nothing is proven, so this is the weaker half of "
              "the guarantee; the full-prover legs are the strong one)")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
