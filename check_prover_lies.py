#!/usr/bin/env python3
"""A corpus of lies: false promises that must NEVER come back proven.

Goal A of SECURITY.md is that a promise Velaris reports "proven" never
breaks at run time. This suite is the adversary's side of it: a set of
`requires` / `ensures` / `invariant` clauses that are false, one per
shape the prover handles, each of which must be either refused before
running (E700/E701/E703/E705/E706, with the prover) or left to a runtime
check (without it) - but never listed among the proven.

The invariant holds with AND without z3: without the prover nothing is
proven at all, so a lie cannot be; with it, a lie is refused or falls
back, and this suite asserts it is not in `check(src).proven`. A lie
that ever appears there is a Goal A break and a security issue.

    python check_prover_lies.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import velaris  # noqa: E402
from suite_dirs import isolate  # noqa: E402

isolate("check_prover_lies")          # its own proof cache

try:
    import z3  # noqa: F401
    HAVE_Z3 = True
    del z3
except ImportError:
    HAVE_Z3 = False

PASS = FAIL = 0


def ok(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  LIE PROVEN  {label}   {detail}")


# Each case: (name, the lying function's name, source). The promise in
# the named function is false; it must never be proven.
LIES = [
    ("int add-off-by-one", "double", '''
fn double(n: Int) -> Int
  ensures result == n + n
{ return n + 1 }
fn main() uses io { print(to_text(double(3))) }
'''),
    ("int ensures wrong constant", "f", '''
fn f(n: Int) -> Int ensures result > n { return n }
fn main() uses io { print(to_text(f(1))) }
'''),
    ("division can be zero", "share", '''
fn share(total: Int, people: Int) -> Int
  ensures result >= 0
{ return total / people }
fn main() uses io { print(to_text(share(10, 0))) }
'''),
    ("remainder can be zero", "bucket", '''
fn bucket(id: Int, size: Int) -> Int { return id % size }
fn main() uses io { print(to_text(bucket(10, 0))) }
'''),
    ("list read past the end", "last", '''
fn last(xs: List of Int) -> Int
  requires length(xs) >= 1
{ return get(xs, length(xs)) }
fn main() uses io { print(to_text(last([1, 2, 3]))) }
'''),
    ("caller breaks a requires (E701)", "top", '''
fn safe(n: Int) -> Int requires n > 0 ensures result > 0 { return n }
fn top() -> Int { return safe(-5) }
fn main() uses io { print(to_text(top())) }
'''),
    ("loop invariant that does not hold", "sum_to", '''
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
    ("record field promise swapped", "move", '''
record P { x: Int  y: Int }
fn move(p: P, dx: Int) -> P
  ensures result.x == p.x + dx
{ return P(x: p.x, y: p.y + dx) }
fn main() uses io { let p = move(P(x: 1, y: 2), 5)  print(to_text(p.x)) }
'''),
    ("ensures over a Secret parameter is false", "bad", '''
fn bad(k: Secret of Text) -> Int
  ensures result == length(k)
{ return 5 }
fn main() uses io { print("x") }
'''),
    ("float promise that is false", "half", '''
fn half(x: Float) -> Float
  ensures result == x
{ return x / 2.0 }
fn main() uses io { print(to_text(half(4.0))) }
'''),
    ("quantified promise that is false", "all_pos", '''
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
    ("a parameter named like the prover's name for a call's result", "f", '''
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
    ("a record field named like the prover's length of a list field", "f", '''
record Box { xs: List of Int  xs__n: Int }
fn f(b: Box) -> Int
  requires b.xs__n == 5
  ensures result == 5
{ return length(b.xs) }
fn main() uses io { print(to_text(f(Box(xs: [1], xs__n: 5)))) }
'''),
    ("a list parameter named like another's per-field array", "f", '''
record P { x: Int  y: Int }
fn f(ps: List of P, ps__x: List of Int) -> Int
  requires length(ps) == 1 and length(ps__x) == 1 and get(ps__x, 0) == 7
  ensures result == 7
{ return get(ps, 0).x }
fn main() uses io { print(to_text(f([P(x: 1, y: 2)], [7]))) }
'''),
]

# Identifiers spelled like SMT-LIB, and text holding SMT-LIB, are what they
# are in Velaris: names and text. The prover builds its queries from the
# syntax tree through Z3's API, never from contract text (8.1 confirmed it:
# no query is parsed from a string), so `assert` is a parameter and
# "(assert false)" is six words of text. A true promise over them proves;
# a false one does not.
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
fn main() uses io { print(f("(check-sat)")) }
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


def main() -> int:
    print(f"prover-lie corpus ({len(LIES)} lies), z3 "
          + ("present" if HAVE_Z3 else "absent"))
    print("-" * 62)
    for name, liar, src in LIES:
        try:
            result = velaris.check(src.strip() + "\n")
        except Exception as e:            # a crash is not "proven", but say so
            ok(name, False, f"check crashed: {type(e).__name__}: {e}")
            continue
        # the one thing that must never happen: the lying function is
        # reported proven. (It may compile-with-a-runtime-check, or be
        # refused outright; both are fine - proven is not.)
        proven = set(result.proven)
        ok(name, liar not in proven,
           f"'{liar}' was reported proven: {sorted(proven)}")
    print("-" * 62)
    print("identifiers and text spelled like SMT-LIB (8.1)")
    for name, fn, true, src in IDENTIFIERS:
        try:
            result = velaris.check(src.strip() + "\n")
        except Exception as e:
            ok(name, False, f"check crashed: {type(e).__name__}: {e}")
            continue
        proven = set(result.proven)
        if true:
            ok(name + (" - proven" if HAVE_Z3 else
                       " - compiles (no prover: nothing is proven)"),
               result.ok and ((fn in proven) if HAVE_Z3 else not proven),
               f"ok={result.ok} proven={sorted(proven)} "
               f"{[p.code for p in result.problems]}")
        else:
            ok(name + " - never proven", fn not in proven,
               f"'{fn}' was reported proven")
    print("-" * 62)
    print(f"{PASS} lie(s) never proven, {FAIL} proven")
    if not HAVE_Z3:
        print("(without z3 nothing is proven, so this is the weaker half of "
              "the guarantee; the full-prover legs are the strong one)")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
