# Velaris in an hour

Velaris is a language where a function's first line tells you
everything: what it takes, what it gives back, what it is allowed to
touch, whether it can fail, and what it promises about its answer.
Those promises are checked by a theorem prover before your program
runs.

You can follow along in the browser — the
[playground](https://velaris-lang.dev/playground.html)
runs the real compiler — or install it:

```
pip install velaris-lang
velaris doctor
velaris new hello && cd hello && velaris main.vel
```

## 1. Hello

```
fn main() uses io {
    print("hello!")
}
```

`main` is where a program starts. `uses io` is a declaration: this
function is allowed to talk to the outside world. Remove it and the
program will not compile, because `print` needs it.

That is the whole idea of Velaris in one line — **abilities are
declared, not assumed**.

## 2. Values and types

```
fn main() uses io {
    let name = "Gowri"           // Text
    let age = 30                 // Int
    let ratio = 1.5              // Float
    let happy = true             // Bool
    let scores = [10, 8, 9]      // List of Int
    let ages = {"a": 1, "b": 2}  // Map of Text to Int
    let fee = money(1250, "INR") // Money of INR - 12.50, as 1250 paise
    print(format("{} is {}", name, age))
}
```

Types are inferred for locals and written down for parameters. Numbers
do not mix silently: `1 + 1.5` is an error, because rounding surprises
are how money goes missing. Convert on purpose with `to_float(x)` or
`round(x)`.

Actual money never becomes a `Float` at all: an amount is whole minor
units with its currency in the type, two currencies never mix, and a
division that could round says how (SPEC.md §4.3).

`format` fills each `{}` with a value, and the compiler counts the
holes for you — the wrong number of values is a compile error, not a
mess at runtime.

## 3. Functions and effects

```
fn double(n: Int) -> Int {
    return n * 2
}

fn greet(name: Text) uses io {
    print("hello, " + name)
}
```

`double` is **pure**: no `uses`, so it cannot print, read files, or
reach the network — and neither can anything it calls. The checker
follows the whole call chain, so a pure function cannot sneak an effect
in through a helper.

The effects are `io`, `fs` (files), `net` (network), `clock` (the
time), and `rand` (randomness).

## 4. Promises, proven

```
fn discount(price: Int) -> Int
    requires price >= 0
    ensures result >= 0
{
    return price - 10
}
```

`requires` is what the function needs from you. `ensures` is what it
promises in return. Run this and the compiler answers:

```
error[E700] promise cannot be kept: 'discount' ensures result >= 0
  proven without running the program: price = 5 gives result = -5
```

It did not test the function. It proved the promise false and handed
back the input that breaks it. Fix the code, or fix the promise:

```
fn discount(price: Int) -> Int
    requires price >= 0
    ensures result >= 0
{
    if price < 10 {
        return 0
    }
    return price - 10
}
```

Now it compiles, and `velaris explain` will say `[proven]`.

Promises can talk about lists, maps, records and floats too:

```
fn bump(counts: Map of Text to Int, word: Text) -> Map of Text to Int
    ensures get_or(result, word, 0) == get_or(counts, word, 0) + 1
{
    return put(counts, word, get_or(counts, word, 0) + 1)
}
```

Floats are proven in real IEEE-754, which means Velaris will *refuse*
to prove `x + 0.1 + 0.1 == x + 0.2` — because on a real machine it is
false. See [docs/floats.md](docs/floats.md) for why that matters.

## 5. Loops

```
fn count_up(n: Int) -> Int
    requires n >= 0
    ensures result >= 0
{
    let total = 0
    let i = 0
    while i < n {
        total = total + 1
        i = i + 1
    }
    return total
}
```

No `invariant` line needed: the compiler works out the boring ones
itself (each counter never goes below where it started). When you need
something richer — "this total stays positive" — write it:

```
    while i < length(xs)
    invariant total >= 0
    {
        ...
    }
```

## 6. Failure

Some things genuinely fail. In Velaris that is part of the signature,
and ignoring it does not compile:

```
fn parse_age(t: Text) -> Int or fail {
    return try to_int(t)
}

fn main() uses io {
    check parse_age(ask("your age?")) {
        ok n {
            print(format("you are {}", n))
        }
        fail why {
            print(format("that was not a number: {}", why))
        }
    }
}
```

`check` handles it here. `try` passes it up to your caller (only inside
a function that says `or fail`). The built-ins that fail in ordinary
life — `to_int`, `read_file`, `fetch`, and `get` on a map — all say so,
and `get_or(m, key, default)` is there when you would rather have a
fallback than a failure.

## 7. Records and lists

```
record Expense {
    what: Text
    amount: Int
}

fn describe(e: Expense) -> Text {
    return format("{}: {}", e.what, e.amount)
}
```

Records are immutable: `Expense(what: "chai", amount: 25)` makes one,
`e.what` reads a field, and nothing can change it underneath someone.
Lists work the same way — `push` gives you a new list.

Reading past the end of a list is caught before the program runs when
the compiler can prove it, and reported cleanly when it cannot.

## 8. Function values

```
import "std.vel"

fn main() uses io {
    let xs = [5, 3, 8, 1]
    print(keep_if(xs, fn(n: Int) -> Bool { return n > 4 }))
    print(sort_by(xs, fn(n: Int) -> Int { return -n }))
}
```

Inline functions are pure and cannot use variables from around them —
pass what they need as parameters. They can carry their own promises,
proven like any other function's.

## 9. Using libraries

```
import "std.vel"                    // sort(xs), first(xs), join(...)
import "lib/geo.vel" as geo         // geo.distance(a, b)
```

A named import keeps a library's functions behind its own name, so two
libraries that both define `distance` can be used in one file. The
standard library is written in Velaris and keeps its own promises:
`sort` carries `ensures is_sorted(result)`.

## 10. The tools

```
velaris program.vel          run it, with io and nothing else
velaris program.vel --allow io,fs:read:./data   grant exactly that
velaris program.vel --allow all                every effect (it says so)
velaris migrate --to 5.0 .   the budget each program here needs
velaris check program.vel    compile it without running
velaris explain program.vel  what each function does, needs and promises
velaris explain .            the same for a whole project
velaris trace program.vel    watch every call as it happens
velaris repl                 try things, proofs and all
velaris fmt program.vel      canonical formatting
velaris doctor               check your setup
velaris new myproject        start something
velaris build program.vel    one executable you can give to anyone
velaris add <url or path>    vendor a library into lib/
velaris verify               check your libraries are unchanged
```

`velaris explain` is the one to reach for when you meet unfamiliar
code: it lists every function with its effects, its promises, and
whether those promises were **proven** or are being checked while
running.

## Where to go next

- [The language reference](SPEC.md) — what all of this means, precisely.

- `examples/ledger.vel` — an expense tracker: records, files, reports.
- `examples/wordcount.vel` — text analysis: maps, lambdas, failure.
- `examples/fetcher.vel` — an HTTP tool: the network, honestly declared.
- [The error index](https://velaris-lang.dev/errors.html)
  — every message Velaris can give, scraped from the compiler itself.

If you can make the prover claim something is proven when it is false,
that is a security bug and the project wants to hear about it.
