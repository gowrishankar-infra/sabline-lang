# Security advisory: negating the smallest whole number was not range-checked, and a promise proven about -n broke when it ran

**Draft for submission through GitHub Security → Report a vulnerability.**
Not published from the repository; the maintainer submits it.

## Summary

A Velaris whole number is 64 bits, and arithmetic that leaves that range
is an error, E407, in the interpreter and in native code alike (SPEC.md
4.1). Addition, subtraction and multiplication were checked. Unary minus
was not. `-n` of the smallest whole number, -9223372036854775808, is 2^63,
which does not fit: the interpreter returned 2^63, and native code wrapped
it back to -9223372036854775808. Integer division of the smallest whole
number by -1 was unchecked in the interpreter in the same way.

The prover reasons about whole numbers as unbounded integers, and relies on
the runtime stopping any arithmetic that leaves the 64-bit range: a promise
it proves holds for every result a function returns, because a result
outside the range is never returned. For unary minus that reliance failed.
`requires n < 0 ensures result > 0 { return -n }` is reported proven, which
is right for every value that fits, and a pure whole-number function with
its promises proven is compiled to native code, which carries no runtime
promise check. Called with the smallest whole number, that function returned
-9223372036854775808 and the run exited 0: a promise reported proven broke
while the program ran. This breaks Goal A of SECURITY.md - a promise
reported proven never breaks at run time - and meets its standing challenge
#1.

A whole number outside the range could also enter a program other ways,
and reach a proven native function that wrapped it: `to_int` of a longer
text, `json_int` and `py_int` of a larger number, `round` of a large float,
and `div_or_fail` of the smallest number by -1.

## Affected versions

**2.14 through 8.1.1** (2.14 made functions whose contracts are proven
eligible for native code). Fixed in **8.2.0**. From 2.7 to 2.13 the same
function was reported proven and stayed interpreted, where it returned
2^63: a whole number outside the language's range, though not one that
breaks that promise.

## CVSS

`CVSS:3.1/AV:L/AC:L/PR:N/UI:R/S:U/C:N/I:H/A:N` - **base 5.5 (Medium)**.

- AV:L, UI:R - the program is delivered to someone who checks or runs it,
  or its input reaches a program they rely on.
- AC:L, PR:N - the value is a constant of the language; writing it, or
  sending it as input, is enough.
- I:H - "proven" is false for that input, and native code does not check the
  promise at all; confidentiality and availability are unaffected.

## Reproduction (against 8.1.1)

`prog.vel`:

```
fn negate(n: Int) -> Int
    requires n < 0
    ensures result > 0
{
    return -n
}

fn main() uses io {
    let smallest = -9223372036854775807 - 1
    print(negate(smallest))
}
```

- `velaris check prog.vel` reports one function with proven promises.
- `velaris prog.vel` prints `-9223372036854775808` and exits 0.
- `velaris prog.vel --no-native` prints `9223372036854775808`: past the 64
  bits a whole number has, with no E407.

The same holds for the absolute value written as `if n < 0 { return -n }
return n` with `ensures result >= 0`. Confirmed on CPython 3.13 with
z3-solver 5.1 and llvmlite 0.49 against 2.14, 2.15.1, 2.20, 4.0.0, 6.0.0 and
8.1.1; 2.13 leaves the function interpreted and prints 9223372036854775808.

## Fix (8.2.0)

- Unary minus on a whole number is checked, in the interpreter and in native
  code (an overflow-reporting subtraction from zero): the smallest whole
  number negated stops with E407, as the largest plus one always did.
- The smallest whole number divided by -1 stops with E407; `div_or_fail`
  fails.
- `to_int`, `json_int` and `py_int` fail on a number outside the range,
  `round` of a value with no whole number in range stops with E407, and
  native code refuses an argument outside the range (E407) instead of
  wrapping it.
- The prover is unchanged. A promise about `-n` that holds for every value
  that fits is still proven, and is now true of every value returned.

Regression: `check_adversarial.py` N1 to N4 run the reproduction, the
absolute value, the division, `round` and `to_int` with native code and
without; `check_prover_lies.py` holds twenty overflow lies and the two
64-bit edges above.

## CWE

CWE-190: Integer Overflow or Wraparound

## Credit

Found by the corpus of false promises written for 8.2
(`check_prover_lies.py`).
