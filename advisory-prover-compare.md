# Security advisory: == on two maps, lists or records was a constant to the prover, and a promise past it was reported proven

**Draft for submission through GitHub Security → Report a vulnerability.**
Not published from the repository; the maintainer submits it.

## Summary

The prover translates a function's body into Z3 formulas and asks whether
its `ensures` can be false given its `requires` (SPEC.md 9). A comparison
`a == b` or `a != b` of two whole numbers, floats, texts or Bools becomes a
formula. A comparison of two values the prover holds as its own Python
objects - two maps, two lists of lists, two lists of Bool or of Text, a map
and `put(...)` of it - fell through to Python's `==` on those objects, which
asks whether they are the same object. It is a constant, almost always
False, not a formula.

A branch `if m == n { ... }` on two map parameters was therefore taken never
to run, and every promise past it was reported proven:

```
fn f(m: Map of Text to Int, n: Map of Text to Int) -> Int
    ensures result == 0
{
    if m == n {
        return 1
    }
    return 0
}
```

`velaris check` reports one function with proven promises; called with two
equal maps, `f` returns 1 and the run stops with E601. Two records compared
field by field had the same fault for a `List of Int` field, and for a
`Float` field Z3's equality calls every NaN equal where a run compares two
NaNs made apart as unequal. This breaks Goal A of SECURITY.md - a promise
reported proven never breaks at run time - and meets its standing challenge
#1.

What limits it: the interpreter checks every promise on every run, proven
or not, and only native code omits the check. A function is compiled to
native code only when its parameters are whole numbers, floats, Bools,
texts or lists of whole numbers, its body builds no map, list or record and
reads lists only through `length` and `get` of a parameter, and every
function it calls is native too; none of the comparisons above can occur in
one. So each break was stopped with E601 when it happened. What was false is
the report: `check`, `proofs`, `explain`, `audit`, the attestation's proven
count, the library's `proven`, and the proof of any function that relied on
such a function's `ensures` through its summary.

## Affected versions

**2.6 through 8.2.1** for maps and `put`; 2.6 is the first release with a
command that reports a promise proven (`velaris explain`). Fixed in
**8.3.0**. Releases before 2.6 have no command that reports a proof and were
not examined further. Of the releases sampled below, lists of lists were
reported proven from 2.20 (2.10 does not parse the type), and lists of Bool
in 2.6 to 2.10 and from 2.50, but not in 2.20, 2.30 or 2.40.

## CVSS

`CVSS:3.1/AV:L/AC:L/PR:N/UI:R/S:U/C:N/I:L/A:N` - **base 3.3 (Low)**.

- AV:L, UI:R - the program is delivered to someone who checks, audits or
  attests it and relies on the report.
- AC:L, PR:N - writing the comparison is enough.
- I:L - "proven" is false in the report and in a signed attestation's count,
  but every run still checks the promise, so no execution goes unchecked;
  confidentiality and availability are unaffected.

## Reproduction (against 8.2.1)

`prog.vel` is the function above with:

```
fn main() uses io {
    print(to_text(f({"a": 1}, {"a": 1})))
}
```

- `velaris check prog.vel` prints `ok - 2 function(s), 1 with proven
  promises`; `velaris.check(source).proven` is `{'f'}`.
- `velaris prog.vel` stops with `E601 broken promise: 'f' ensures result ==
  0 (result = 1)`.

The same holds with `List of List of Int`, `List of Bool` or `List of Text`
parameters, with `if put(m, "a", 1) == m` under `requires get_or(m, "a", 0)
== 1 and has(m, "a")`, with a record holding a `List of Int` field, and with
two records whose Float fields are NaNs made apart. The map case was
confirmed on CPython 3.13 with z3-solver against 2.6 (through `velaris
explain`), 2.7, 2.9, 2.10, 2.20, 2.30, 2.40, 2.50, 2.60, 3.0.0, 4.0.0, 5.0.0,
6.0.0, 7.0.0, 8.0.0 and 8.2.1; the record cases against 8.2.1.

## Fix (8.3.0)

- `==`, `!=` and every other operator on a value that is not a Z3 expression
  or a plain constant - a map, a list of lists, a list the prover knows only
  by its length, a list of records - abandon the proof, so the promise is
  checked while the program runs, as every unproven promise is.
- Two records compare field by field as their fields do: a `List of Int`
  field as two such lists, and a record holding a `Float` field is left to
  runtime, since a run compares one NaN with itself as equal and two NaNs
  made apart as unequal.
- A promise past such a comparison that the prover does not settle is
  checked at run time; a false one past a comparison of two records with a
  `List of Int` field can now be refused with E700, as the same comparison
  of two lists has been.

Regression: `check_prover_lies.py`, the COMPARED category, holds nine
comparisons as lies under five Z3 seeds; `check_mutant_kills.py` V6 holds the
map case.

## CWE

CWE-697: Incorrect Comparison

## Credit

Found writing a test for a mutant the monthly mutation run left alive in
`uninterpreted_in` (`check_mutant_kills.py`, 8.3).
