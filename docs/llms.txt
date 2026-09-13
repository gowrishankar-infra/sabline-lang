# Velaris for language models

Paste this whole file into a model before asking it to write Velaris.
It is written to be read by a model, not a person: complete, compact,
and with the failure modes named. `velaris card` prints it.

## This is a real language you can run

`pip install velaris-lang`, then `velaris program.vel`. There is a
browser playground at
<https://gowrishankar-infra.github.io/velaris-lang/playground.html> and
the compiler is one Python file at
<https://github.com/gowrishankar-infra/velaris-lang>. Write code
expecting it to actually execute.

## What Velaris is

A small language where a function's signature declares its types, the
effects it may perform, whether it can fail, and promises a theorem
prover checks before the program runs.

Files end in `.vel`. Execution starts at `main`. Run with
`velaris program.vel`, which grants `io` - print, read a line, read
the arguments - and refuses every other effect at run time. A program
that needs a file, a host, the clock, randomness, the environment or
Python has to be run with `--allow` naming it: `velaris program.vel
--allow io,fs:read:./data`. Check without running:
`velaris check program.vel`.

## The whole syntax

```
// a comment

record Expense {
    label: Text
    amount: Int
}

fn double(n: Int) -> Int {
    return n * 2
}

fn greet(name: Text) uses io {
    print("hello, " + name)
}

fn discount(price: Int) -> Int
    requires price >= 0
    ensures result >= 0
{
    if price < 10 {
        return 0
    }
    return price - 10
}

fn parse_age(text: Text) -> Int or fail {
    return try to_int(text)
}

fn main() uses io {
    let name = "gowri"          // type inferred
    let ages: Map of Text to Int = {}   // annotate empty [] and {}
    let scores = [3, 1, 2]

    for i in 0 to 3 { print(i) }
    for s in scores { print(s) }

    let i = 0
    while i < 3 {
        i = i + 1
    }

    check parse_age("30") {
        ok years { print(format("age {}", years)) }
        fail why { print(format("bad age: {}", why)) }
    }
}
```

Types: `Int` `Float` `Bool` `Text` `Handle` `Money of INR`,
`List of T`, `Map of K to V` (K is `Text` or `Int`), `fn(T) -> R`,
record names. Generic: `fn first(xs: List of T) -> T for any T`, and in
a currency: `fn fee(m: Money of C) -> Money of C for any C`.

## Rules a model gets wrong

These are the mistakes that actually happen. Read them twice.

1. **Every effect must be declared.** `print` needs `uses io`. A
   function without `uses` is pure and cannot call one that has
   effects. Effects: `io` (console: print, read_line, args), `env`
   (environment variables - its own effect since 3.0, so `env()`
   needs `uses env`, not `uses io`), `fs` (files), `net` (network),
   `clock`, `rand`, `ffi` (calling Python), `declassify` (letting a
   `Secret` out, rule 17). Declare all that apply: `uses io, fs`.

2. **Failure cannot be ignored.** These can fail: `to_int`,
   `read_file`, `fetch`, `post`, `fetch_status`, `request`, `get` on a
   **map**, `py`, `py_int`, `py_float`, `py_json`, `py_new`, `py_do`,
   `py_field`, `json_get`, `json_int`, `json_float`, `json_len`.
   Handle with `check`, or pass up with `try` **only inside a function
   whose signature says `or fail`**.

3. **`get` on a list is NOT fallible** — no `try`, no `check`. Bounds
   are the prover's job. `get` on a **map** IS fallible; use
   `get_or(m, key, default)` when you want a fallback instead.

4. **Empty `[]` and `{}` need a type.** Write
   `let xs: List of Int = []`, not `let xs = []`.

5. **Numbers do not mix.** `1 + 1.5` is an error. Use `to_float(x)` or
   `round(x)`.

6. **Whole numbers are 64-bit.** Arithmetic that outgrows that range is
   an error, not a wraparound.

7. **Inline functions capture by value.** `fn(n: Int) -> Bool { ... }`
   may read locals from the surrounding function; their values are
   copied when the function value is made, so later changes to those
   locals do not affect it. Effects still apply: an inline function
   that prints needs the surrounding function to allow it, and a
   function value passed to a library must still be pure. A name that
   exists nowhere is E402 as before.

8. **`main` cannot fail** and takes no parameters.

9. **There are no closures, exceptions, classes, inheritance, `null`,
   threads, `break` or `continue`.** To leave a loop early, put the
   exit in the loop test where the prover can see it:
   `while i < n and not found { ... }` - afterward the prover knows
   `i >= n or found`, so loop promises keep proving. (SPEC.md §13a has
   the full reasoning.)

10. **Strings concatenate with `+`;** use `format("{} and {}", a, b)`
    for anything more, and the number of `{}` must match the number of
    values exactly.

11. **Record fields go one per line.** Commas between fields on one
    line are a parse error.

12. **`%` is remainder** and `/` is whole-number division rounding
    toward minus infinity: `-7 / 2` is `-4` and `-7 % 2` is `1`. Both
    are checked for zero divisors like division.

13. **`random(n)` draws from 0 to n-1** and needs `uses rand`;
    `random(0)` is a runtime error (E405). `now()` gives seconds and
    needs `uses clock`.

14. **Number literals larger than 64 bits are accepted as text-like
    values;** only *arithmetic* is range-checked (E407). Do not rely
    on oversized literals.

15. **Declaring an unused effect is legal but viral** - every caller
    must then declare it too. Declare only what a function does.

16. **Money is not a number and never a Float.** `money(1250, "INR")`
    is 12.50 rupees: whole minor units, with the currency in the type.
    Three rules, each a compile error to break: **no Float** touches an
    amount (E501); **no two currencies** meet (E550 - and there is no
    conversion builtin, because a rate and a rounding policy belong in
    your program); **rounding is always named** - `/` and `%` on an
    amount are refused (E553), so write
    `percent_of(amount, 25, 1000, "half_up")` or
    `divide_or_fail(amount, 3, "half_even")`, mode written in the call
    (`"half_up"`, `"half_even"`, `"down"`; there is no default). An
    amount adds to an amount and multiplies by an `Int`; amount times
    amount is a type error. `units_of(m)` is its minor units and
    `units_of(xs)` what a list of them adds up to (0 when empty); there
    is no Money-valued total, an empty list having no currency. Write
    the currency in the call, one of: AED AUD BHD BRL CAD CHF CNY EUR
    GBP HKD INR JOD JPY KRW KWD MXN OMR SAR SGD USD ZAR (else E551).

17. **`env()` gives a `Secret of Text`, and a Secret cannot be
    printed — or looked at.** This is the one a model gets wrong: you
    write `print(env("API_KEY", ""))`, or `if env("API_KEY", "") == ""
    { ... }`, or `fn config(n: Text) -> Text uses env { return env(n,
    "") }`, and none of the three compiles. `Secret of T` wraps any T;
    `env()` and `read_file_secret()` are the only two builtins that
    make one.

    - **Nothing with an effect takes one.** `print`, `log`, `ask`,
      `exit_with`, `write_file`, `read_file`, `fetch`, `post`,
      `request`, `env` itself, and every `py_*` refuse a Secret
      argument with **E560**. So does the reason given to `fail`.
    - **Nothing that can fail takes one either**, for the same reason:
      a failure's reason is text the program can print and the runtime
      writes it out of what it was given. `to_int`, `parse_money`,
      `json_get`, `pop`, `slice`, `set_at` and the `_or_fail` family
      all refuse a Secret (E560). Declassify first if you need them.
    - **It spreads through pure work and through structures.**
      `"Bearer " + key` is a `Secret of Text`; `length(key)` is a
      `Secret of Int`; `to_text`, `format`, `json_of`, `upper` all
      keep it. A list of them, a map of them, or a record with one
      secret field carries it, and the whole structure is refused at a
      sink - not just the field.
    - **A comparison keeps it too, and you cannot branch on it.**
      `key == ""` is a `Secret of Bool`, not a `Bool`. `if` and
      `while` on one are **E563**. This is the rule a model most often
      trips over after the first: `if key == "" { ... }` does not
      compile. It is deliberate - with `length` and `code_at`, a plain
      Bool from `==` is not one bit, it is a loop that reads the whole
      key out a character at a time.
    - **Say Secret in the signature.** A function that hands one back
      must write `-> Secret of Text`, or it is E503. Pass one along as
      `fn f(k: Secret of Text) -> Secret of Text`.
    - **A promise may be about one.** `requires length(key) > 0` is
      fine: a broken promise stops the run and cannot be caught, so it
      is not a branch.
    - **No generic function takes one.** `first(xs)`, `index_of(...)`,
      `contains_item(...)` and every other `for any T` helper refuse a
      secret (E560) - a generic body was checked without knowing `T`
      could be one, so it could compare it and hand back an ordinary
      answer. Write `fn f(s: Secret of T) -> Secret of T for any T` if
      you need a generic over secrets.
    - **`declassify(value, "why")` is the only way out**, needs
      `uses declassify`, and the reason must be written as text in the
      call (E561) - it goes into the audit. Use it when the value
      genuinely is not a secret (a region, a log level), or when you
      must look at one and are willing to say so.

    So do not write `print(env("API_KEY", ""))`, and do not write
    `if env("API_KEY", "") == "" { ... }` either. Write either of
    these:

    ```
    // hold it, use it, never look at it
    fn main() uses io, env {
        let key = env("API_KEY", "")
        let header = "Bearer " + key      // still a Secret of Text
        print("a request was built; the key is not in this output")
    }

    // or look at it, and say so
    fn main() uses io, env, declassify {
        let key = env("API_KEY", "")
        let missing = declassify(key == "",
        "whether a key is set at all is not the key")
        if missing {
            print("API_KEY is not set")
        } else {
            print("API_KEY is set")
        }
    }
    ```

## Recursion, loops, and depth

Recursion works and carries contracts like any function:

```
fn count_down(n: Int) -> Int
    requires n >= 0
    ensures result >= 0
{
    if n == 0 {
        return 0
    }
    return count_down(n - 1)
}
```

A recursive call site is checked against the callee's `requires` like
any other call. Depth is limited to 2000 frames: past that the program
stops with E609 rather than crashing, so runaway recursion reports
itself.

`invariant` works on **both** `while` and `for`:

```
for i in 0 to n
invariant sum >= 0
{
    sum = sum + i
}
```

`for i in 0 to n` is **exclusive** - it runs n times, and the last
value of i is n - 1.

## Contracts

```
fn average(total: Int, count: Int) -> Int
    requires count > 0            // what the caller must ensure
    ensures result * count <= total   // what this guarantees
{
    return total / count
}
```

`result` names the return value in `ensures`. Loops may carry
`invariant` clauses, though simple counter bounds are inferred:

```
while i < n
invariant total >= 0
{
    ...
}
```

Contract expressions must be pure. Promises the prover cannot settle
fall back to runtime checks — the program still runs.

**What the prover can and cannot reach.** It is strong on arithmetic
over whole numbers and floats, on list lengths, and on counter loops -
including promises about a list a loop builds, such as
`ensures length(result) == length(xs)`, with no invariant needed. It
also catches the classic off-by-one: `while i <= length(xs)` reading
`get(xs, i)` is refused before running.

It can also prove promises about the contents of a list a loop
builds: `ensures all_of(result, is_positive)` proves when every push
is guarded to satisfy the predicate, with no invariant written. It
still falls back to runtime for: loops whose counter moves by anything
other than one, several counters moving together, and anything reached
through `ffi`. Write contracts freely on arithmetic and on list
lengths; expect runtime checks elsewhere.

**Whole-number overflow is an error, not a failure.** `a * b` that
outgrows 64 bits raises E407 and stops the program - `check` cannot
catch it. When the numbers come from a user, use `add_or_fail`,
`sub_or_fail` and `mul_or_fail`, which fail in the normal way and can
be caught.

Write contracts when the guarantee matters. Do not decorate every
function; an unprovable promise is worse than none.

## Standard library

`import "std.vel"` then call directly:

```
first last reverse index_of contains_item keep_if
map_to(xs, f) - projection that CAN change type: fn(T) -> R
apply_to_each (maps T -> T, same type only)
count_where sum_of max_of min_of is_sorted insert_sorted sort
insert_by sort_by (keys must be Int) join range_list
```

`max_of` and `min_of` require a non-empty list. `sort` promises
`is_sorted(result)`.

Other modules, imported under a name. **Full signatures**, since
guessing them is the commonest source of wasted attempts:

```
import "http.vel" as http     the network, as calls        (below)
import "db.vel" as db         sqlite through ffi           (below)
import "dates.vel" as dates   a Date record, and its parts (below)
import "csv.vel" as csv       comma-separated rows         (below)
import "log.vel" as log       lines on stderr; die STOPS the program,
                              exit 1 - not a catchable failure  (below)
import "env_tools.vel" as sys setting public_setting number_setting
                              succeed give_up
import "money.vel" as money   split(amount, ways) -> List of Money of C
                              requires ways > 0; PROVEN: as many parts
                              as asked, adding up to the amount exactly,
                              none negative when the amount is not.
                              not_negative / not_positive are its
                              predicates, for your own all_of
import "time.vel" as time     today clock_text seconds year_of month_of
                              (time needs 'uses ffi' and its functions
                              CAN FAIL - handle or pass up)

```
http  (uses net, every function CAN FAIL unless noted)
  get(url: Text) -> Text                      the raw body
  get_with(url: Text, headers: Text) -> Text  headers as a JSON object
  send(url: Text, body: Text) -> Text         POST; non-2xx is a failure
  post_json(url: Text, body: Text) -> Text
  status(url: Text) -> Int                    ensures result >= 0
  ok(url: Text) -> Bool                       true for 200..299
  call(method, url, body, headers) -> Answer  the full envelope
  code_of(a: Answer) -> Int                   cannot fail
  body_of(a: Answer) -> Text                  cannot fail
  header_of(a: Answer, name: Text) -> Text    CAN FAIL
  record Answer { status: Int  body: Text  raw: Text }

db  (uses ffi, every function CAN FAIL unless noted)
  open(path: Text) -> Handle                  ":memory:" for a temp one
  run(conn: Handle, sql: Text) -> Text
  rows_json(conn: Handle, sql: Text) -> Text  read with the json builtins
  count(conn: Handle, table: Text) -> Int     ensures result >= 0
  commit(conn: Handle)
  close(conn: Handle)                         cannot fail

dates  (pure unless noted)
  record Date { year: Int  month: Int  day: Int }
  make(y: Int, m: Int, d: Int) -> Date        CAN FAIL; refuses fake dates
  parse(text: Text) -> Date                   CAN FAIL; "2026-08-18"
  text_of(d: Date) -> Text                    zero-padded
  before(a: Date, b: Date) -> Bool
  same(a: Date, b: Date) -> Bool
  next_day(d: Date) -> Date                   CAN FAIL
    requires d.month >= 1 and d.month <= 12
  days_in(year: Int, month: Int) -> Int
    requires month >= 1 and month <= 12
    ensures result >= 28 and result <= 31     (proven)
  today() -> Date                             uses ffi, CAN FAIL

csv  (pure)
  fields(line: Text) -> List of Text          ensures length >= 1
  line_of(values: List of Text) -> Text
  column(line: Text, at: Int) -> Text         CAN FAIL
  column_int(line: Text, at: Int) -> Int      CAN FAIL
  rows_of(text: Text) -> List of Text         splits on newlines

log  (uses io)
  info / warn / error (message: Text)
  event(name: Text, details: Text)
  field(name: Text, value: Text) -> Text      pure
  die(message: Text)                          logs and STOPS, exit 1

env_tools  (uses io)
  setting(name, fallback) -> Secret of Text   (uses env)
  public_setting(name, fallback) -> Text      (uses env, declassify)
  number_setting(name: Text, fallback: Int) -> Int
                                              (uses env, declassify)
  succeed()                                   exits 0
  give_up(why: Text)                          prints and exits 1
```
```

## Builtins

```
print(x) uses io              ask(prompt) uses io
log(x) uses io                env(name, fallback) uses env
args() uses io                  -> Secret of Text (rule 17)
read_line() uses io           exit_with(code) uses io
declassify(secret, "why") uses declassify - the only way out of a
  Secret; the reason must be written in the call, and is what
  velaris audit reports

length(x)     get(list, i)    push(list, v)    get(map, k) CAN FAIL
pop(list) CAN FAIL            slice(list, from, to) CAN FAIL
set_at(list, i, v) CAN FAIL   (lists are values; these return new ones)
add_or_fail(a, b) CAN FAIL    sub_or_fail / mul_or_fail CAN FAIL
div_or_fail(a, b) CAN FAIL    mod_or_fail CAN FAIL
(plain / and % on a zero divisor are E403 and STOP the program -
use the _or_fail forms when the divisor comes from input)
put(map, k, v)  get_or(map, k, default)  has(map, k)  keys(map)
all_of(xs, p)   any_of(xs, p)

money(units, "INR")    an amount: whole minor units in that currency
units_of(m)            its minor units; units_of(list) their sum, 0 if
                       empty          with_units(m, n) n units, m's currency
percent_of(m, numerator, denominator, "half_up")   the mode is required
divide_or_fail(m, by, "half_even") CAN FAIL        ("half_up",
                       "half_even", "down"; / and % on an amount are E553)
text_of(m) -> "INR 12.50"      parse_money(t, "INR") CAN FAIL
(a builtin above added in 4.3 gives way to your own function of that name)

to_int(t) CAN FAIL   to_text(x)   to_float(x)   round(f)
upper(t) lower(t) split(t, sep) contains(t, s) chars(t) code_at(t, i)
format(template, ...)

read_file(p) CAN FAIL uses fs
read_file_secret(p) CAN FAIL uses fs   -> Secret of Text (rule 17)
read_file_secret(p) CAN FAIL uses fs  -> Secret of Text (rule 17)
declassify(secret, "why") uses declassify - the reason must be
  written here, not built; it is what velaris audit reports
write_file(p, body) uses fs - does NOT fail catchably; an
  unwritable path or full disk stops the program with E608
file_exists(p) uses fs
fetch(url) CAN FAIL uses net       post(url, body) CAN FAIL uses net
fetch_status(url) CAN FAIL uses net
request(method, url, body, headers_json) CAN FAIL uses net

json_get(doc, path) CAN FAIL       json_int / json_float CAN FAIL
json_len(doc, path) CAN FAIL       json_has(doc, path)
json_of(value)                     paths look like "user.name" or "tags[0]"

py(module, fn, args_list) CAN FAIL uses ffi
py_int / py_float                  same shape, typed result
py_json(module, fn, args_json) CAN FAIL uses ffi   JSON in, JSON out
py_new(module, fn, args_json) -> Handle CAN FAIL uses ffi
py_do(handle, method, args_json) CAN FAIL uses ffi
py_field(handle, name) CAN FAIL uses ffi     py_close(handle) uses ffi

Handle lifecycle: py_close is safe to call twice (the second is a
no-op). Any use after close - py_do, py_field - FAILS catchably with
"that handle is closed". Handles are values; copying one copies the
reference, and closing through either closes both.

now() uses clock                   random(n) uses rand
```

## Running and inspecting

```
velaris program.vel                      run it; since 5.0 it gets io -
                                         print, read_line, args - and
                                         every other effect is refused
                                         (E310), whatever the source says
velaris program.vel --allow io,fs:read:./data
                                         grant exactly this and no more
velaris program.vel --allow all          every effect; one line to stderr
velaris program.vel --allow all --deny net,ffi
                                         everything but these
velaris program.vel --allow io,ffi:math,json
                                         ffi for THOSE modules only (E311
                                         for any other); plain ffi grants
                                         every module
velaris check program.vel [--json]       every problem, as data
velaris check program.vel --strict       refuse ANY promise left to
                                         runtime; without it an
                                         unprovable promise degrades to
                                         a runtime check
velaris audit program.vel                what it touches, before running
velaris proofs program.vel --detail      which promises proved, one by one
velaris explain program.vel              functions, effects, proof status
```

The effect budget (`--allow`/`--deny`) is enforced while the program
runs, whatever the source declares; a refusal cannot be caught.

## The budget grammar

A budget names what a run may touch. Grants are comma-separated and
additive; plain `fs`, `net` or `ffi` grants every path, host or module.

```
io                          the console: print, read_line, args
env                         environment variables (env())
fs                          any file, read and write
fs:read      fs:write       one direction, any path
fs:read:./data              read under that directory only
fs:write:./out              write under that directory only
net                         any host
net:api.example.com         that host, any port
net:api.example.com:443     that host and port only
net:*.example.com           one label in place of the star (a.example.com
                            yes; example.com no; a.b.example.com no)
ffi                         any Python module
ffi:math,json               those top-level modules only
fs:read:./data@50           ...and at most 50 file operations in the run
net:api.example.com@100     ...and at most 100 network operations
clock  rand                 as before
```

Examples: `--allow io,fs:read:./data,net:api.example.com:443@20`;
`velaris.run(source, allow={"io", "env", "fs:write:./out"})`.

Paths are resolved with realpath before every comparison, so `..` and
symlinks cannot reach past a prefix. A redirect to a host the run did
not grant is a failure the program can catch (it asked for one host
and was sent to another); every other refusal stops the program:

| Code | Means |
|---|---|
| E310 | the effect itself is not in the budget |
| E311 | a Python module outside the `ffi:` list |
| E313 | a path outside the `fs:` grants, named in the message |
| E314 | a host or port outside the `net:` grants |
| E315 | the operation count for `fs` or `net` was reached |

A budget with no count is a budget on what, not on how much.

## Errors, and what to do about them

Every error has a stable code. `velaris check program.vel --json` emits
them as structured data for a fix loop.

| Code | Means | Fix |
|---|---|---|
| E200 | unknown function | check spelling; import the module |
| E300 | effect not declared (for `env()` since 3.0 the message is exactly: env() now needs 'uses env') | add `uses ...` to the signature |
| E310 | effect not allowed by this run | the person running chose a budget |
| E313 | a path outside the run's `fs:` grants | grant it: `--allow fs:read:<dir>`, or stay inside |
| E314 | a host or port outside the run's `net:` grants | grant it: `--allow net:<host>:<port>` |
| E315 | the run's `fs` or `net` operation count was reached | grant more: `@<count>`, or do less |
| E401 | wrong number of arguments | count them |
| E402 | unknown variable | declare it; inline functions cannot capture |
| E403 | divide by zero at runtime | guard the divisor |
| E406 | `format` holes do not match values | count the `{}` |
| E407 | number too big for 64 bits | use smaller units |
| E500 | unknown type | check the spelling of the type |
| E501 | types do not match | convert on purpose |
| E503 | returns the wrong type | fix the return or the signature |
| E506 | empty `[]` or `{}` with no type | annotate the `let` |
| E507 | a record defined twice, or a duplicate field | rename one |
| E514 | local name collides with an import | rename one |
| E520 | a failure was ignored | wrap in `check`, or `try` inside `or fail` |
| E522 | `try` on something that cannot fail | remove the `try` |
| E600/E601 | a promise broke while running | fix the code or the promise |
| E700 | a promise is provably false | the counterexample is in the message |
| E701 | a call can break the callee's `requires` | check the value first |
| E703/E704 | a loop invariant does not hold, before or while running | weaken it or fix the loop |
| E705 | a list read can go out of range | add a `requires` about the length |
| E706 | a divisor can be zero | add `requires n != 0` or guard it |
| E400 | no `main` | add fn main() |
| E405 | random(0) | pass n >= 1 |
| E509 | unknown record field | check the field name |
| E513 | redefining an imported function | rename yours |
| E521 | `try` outside an `or fail` function | add `or fail`, or use check |
| E523 | `main` declares `or fail` | handle failures inside main |
| E525 | binding the result of a void fallible call | use check without ok-binding |
| E608 | a file could not be written | check the folder exists and is writable |
| E609 | recursion 2000 deep | move toward the base case, or use a loop |
| E612 | a loop's end could not be shown (only under `check --strict`) | make one counter move one step toward a limit the body does not change |
| E542 | function value of the wrong shape | match the parameter's fn type |
| E550 | two currencies met | convert on purpose, or keep one currency |
| E551 | a currency that is not known, or not written in the call | write a listed code: `money(1250, "INR")` |
| E552 | a rounding mode missing or not written in the call | pass `"half_up"`, `"half_even"` or `"down"` |
| E553 | `/` or `%` on an amount | `divide_or_fail(m, n, "half_even")`, `percent_of`, or `money.split` |
| E602 | a list read went out of range while running | fix the index |

## A complete program to imitate

```
import "std.vel"
import "csv.vel" as csv
import "log.vel" as log

record Expense {
    label: Text
    amount: Int
}

fn parse_row(row: Text) -> Expense or fail {
    let parts = csv.fields(row)
    if length(parts) < 2 {
        fail format("not enough columns in: {}", row)
    }
    let amount = try to_int(get(parts, 1))
    if amount < 0 {
        fail format("negative amount in: {}", row)
    }
    return Expense(label: get(parts, 0), amount: amount)
}

fn total_of(items: List of Expense) -> Int
    ensures result >= 0
{
    let total = 0
    for item in items {
        if item.amount > 0 {
            total = total + item.amount
        }
    }
    return total
}

fn main() uses io {
    log.info("reading expenses")
    let rows = ["chai,2500", "book,45000", "auto,12000"]
    let items: List of Expense = []
    for row in rows {
        check parse_row(row) {
            ok item {
                items = push(items, item)
            }
            fail why {
                log.warn(format("skipping: {}", why))
            }
        }
    }
    print(format("{} expense(s), total {}", length(items),
        total_of(items)))
}
```

## Checklist before returning code

- Does every function that prints, reads, fetches or calls Python
  declare the effect? Does `main` declare everything its callees need?
- Is every fallible call wrapped in `check`, or `try` inside a function
  that says `or fail`?
- Do empty `[]` and `{}` have types?
- Do inline functions use only their own parameters?
- Do `format` holes match the values given?
- Would `velaris check` pass? If unsure, prefer fewer contracts and
  simpler code over clever code with promises that may not prove.
