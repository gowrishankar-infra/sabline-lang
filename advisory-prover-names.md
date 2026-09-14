# Security advisory: a name the prover made up could be written by a program, and a false promise came back proven

**Draft for submission through GitHub Security → Report a vulnerability.**
Not published from the repository; the maintainer submits it.

## Summary

Velaris proves a function's promises by translating them into queries for
the Z3 theorem prover. For values the prover introduces itself - the result
of a call it summarizes by the callee's promises, a quantifier's variable,
what a loop leaves in a variable - and for values it derives from a
program's own - the length of a list, one array per field of a list of
records - it made up Z3 constant names: `__g_result_1` for the result of the
first call to `g`, `xs__n` for the length of `xs`, `ps__x` for the `x`
fields of a list of records `ps`. Z3 treats two constants with the same name
and sort as one value, and a Velaris identifier is `[A-Za-z_][A-Za-z0-9_]*`,
so a program could name a parameter `__g_result_1`, or a record field
`xs__n`, and make its own value the same Z3 constant as one of the prover's.

With a parameter named `__g_result_1`, the promise `g` makes about its result
became an assumption about that parameter; with a record field `xs__n` beside
a list field `xs`, the field and the list's length became one value. Either
way the prover could establish a promise that is false, and `velaris check`,
`velaris proofs`, `velaris audit`, `velaris explain` and the library reported
it proven. A proven pure-integer function is compiled to native code, which
does not carry the interpreter's runtime promise check, so in the first case
the false promise also went unenforced when the program ran: it finished
with the wrong result and exit code 0.

This breaks Goal A of SECURITY.md - a promise reported proven never breaks
at run time - and meets its standing challenge #1.

## Affected versions

**0.9 through 8.0.0** (the call-result names date from 0.9, the record-field
names from 2.18). Fixed in **8.1.0**. Every version published to PyPI up to
8.0.0 is affected.

## CVSS

`CVSS:3.1/AV:L/AC:L/PR:N/UI:R/S:U/C:N/I:H/A:N` - **base 5.4 (Medium)**.

- AV:L, UI:R - the program is delivered to someone who checks or runs it.
- AC:L, PR:N - the names are fixed and public; writing one is enough.
- I:H - "proven" is false, and in the native case the promise is not
  enforced at all; confidentiality and availability are unaffected.

As with the proof-cache advisory, scope changed (S:C, about 6.1) is
arguable, since "proven" is what a person uses to decide whether to run
code; the conservative 5.4 is reported.

## Reproduction (against 8.0.0)

`prog.vel`:

```
fn g(n: Int) -> Int
  ensures result > n
{ return n + 1 }

fn f(__g_result_1: Int) -> Int
  ensures result == __g_result_1 + 5      // false: f(x) is x + 1
{ return g(__g_result_1) }

fn main() uses io { print(to_text(f(1))) }
```

- `velaris check prog.vel` reports `f` and `g` proven (exit 0).
- `velaris prog.vel` prints `2` and exits 0: the promise `result == 6` is
  broken and nothing says so.
- With the parameter named `x`, `velaris check` leaves `f` to a runtime
  check, and `velaris prog.vel` stops with E601.

The record case:

```
record Box { xs: List of Int  xs__n: Int }

fn f(b: Box) -> Int
  requires b.xs__n == 5
  ensures result == 5
{ return length(b.xs) }
```

- 8.0.0 reports `f` proven. A run with `Box(xs: [1], xs__n: 5)` stops with
  E601, because a function over a record is interpreted and the runtime
  check still ran.
- 8.1.0 refutes it before running (E700).

Confirmed on CPython 3.13 with z3-solver 5.1.

## Fix (8.1.0)

Every name the prover makes up begins with `!`, and every name it derives
from one of the program's own contains `#` (`xs#n`, `ps#x`). Neither
character can appear in a Velaris identifier, so no parameter, variable or
field can be the same Z3 constant as one of them.

The same release confirmed that the prover builds every query from the
syntax tree through Z3's API and parses no query from text: an identifier
spelled like SMT-LIB (`assert`, `ite`, `select`) is an identifier, and text
holding SMT-LIB is text.

Regression: `check_prover_lies.py` adds the three shapes - a call result's
name, a list length's name, a per-field array's name - to its corpus of lies
that must never be proven, and a set of identifiers and text spelled like
SMT-LIB that must behave as identifiers and text; `check_adversarial.py`
runs the native case and requires the run to stop with E601.

## CWE

CWE-706: Use of Incorrectly-Resolved Name or Reference

## Credit

Found during an internal adversarial pass against 8.0.0.
