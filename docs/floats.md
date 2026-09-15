# Your verifier is probably lying to you about floats

Here is a promise that looks obviously true:

```
fn add_twice(x: Float) -> Float
    ensures result == x + 0.2
{
    return x + 0.1 + 0.1
}
```

Adding a tenth twice is the same as adding two tenths. Every algebra
teacher you have ever had agrees. Most program verifiers agree too.

They are wrong, and so is the promise.

Velaris refuses to prove it, and hands back the number that breaks it:

```
error[E700] promise cannot be kept: 'add_twice' ensures result == x + 0.2
  proven without running the program:
    x = -1.207290298954004637010939404717646539211273193359375
    gives result = -1.007290298954004459375255464692600071430206298828125
```

That is not a rounding display artifact. Those are two different
doubles, and the program really does produce the second one.

## Why the lie is tempting

To prove things about numbers, a verifier translates your code into
formulas for a solver. The question is which *theory* to translate
into.

The comfortable choice is the theory of real numbers. Reals are
associative, commutative, infinitely precise, and solvers are fast at
them. Translate `Float` to `Real` and everything works beautifully:
proofs come back in milliseconds, and `x + 0.1 + 0.1 == x + 0.2` is
trivially true.

It is also a statement about a machine that does not exist.

Your processor implements IEEE-754 binary64. In that world `0.1` is not
one tenth — it is the nearest double to one tenth, which is
`0.1000000000000000055511151231257827021181583404541015625`. Every
operation rounds to the nearest representable value. Addition is not
associative. Adding a tenth twice takes two rounding steps; adding two
tenths takes one. For many values of `x` those disagree in the last
bit, and one bit is all it takes for `==` to be false.

So a verifier that models floats as reals will happily certify code
that fails on the machine it is compiled for. The proof is valid. The
theorem is about the wrong object.

## What honesty costs

Z3 has a floating-point theory that implements IEEE-754 exactly:
rounding modes, subnormals, infinities, NaN, signed zero. Velaris
translates `Float` into that theory rather than into `Real`.

The bill arrives immediately.

**It is slow.** The FP theory is decided by bit-blasting — expanding
64-bit values into circuits of individual bits and handing the result
to a SAT solver. The refutation above takes about fifteen seconds on an
idle machine and several times that on a busy one. Integer proofs in
the same compiler finish in milliseconds. Velaris gives float queries a
**120 second** budget and everything else three seconds, and only pays
the larger cost for functions that actually mention floats. Either
budget can be replaced for one run:

```
velaris check f.vel --proof-timeout 300
VELARIS_PROOF_TIMEOUT=300 velaris check f.vel
```

**A budget that runs out says so.** If the solver spends its whole
budget without an answer, the proof is *abandoned* — nothing proven,
nothing refuted — and every report says that in those words:

```
note: the proof of 'add_twice' ran out of time after 120s and was
abandoned - nothing was proven and nothing was refuted, so its promises
are checked while running instead. This is not 'the prover found
nothing wrong'.
```

`velaris check` marks the file `1 proof(s) abandoned: out of time,
nothing settled`, `velaris proofs --detail` marks the function
`[timeout]` rather than `[runtime]`, and `--strict` fails and says the
proof was abandoned rather than unprovable. The next run spends the
budget again: no proof is kept between runs. A slow machine must never be able to make a lost refutation look like a
clean bill of health — that is the same commitment as the one below,
read from the other side.

**Fewer things are provable.** Plenty of true-in-the-reals facts are
simply false in IEEE-754, and plenty of true-in-IEEE facts are too
expensive to establish. A verifier that pretends floats are reals has a
much better success rate on paper. It is winning a game nobody should
want to play.

**Equality gets strange, correctly.** Velaris compares floats with
`fpEQ`, not structural equality, which means NaN is not equal to itself
and positive zero equals negative zero. Both are IEEE behaviour, and
both surprise people. Using structural equality would have been faster
and easier to explain, and would have quietly produced false results at
the edges.

There is a bonus that only shows up once you are honest: comparison
constraints start doing real work. A precondition like `requires
x >= 0.0` silently rules out NaN, because NaN fails every comparison.
The prover knows that, so a promise you could not otherwise establish
sometimes becomes provable for free.

## The rule underneath

Velaris has one commitment it will not trade away: **it never claims
something is proven unless the claim is literally true.**

That single rule decided the float design by itself. If you model
floats as reals, "proven" starts meaning "proven about an idealised
machine that does not exist," and the word has quietly been devalued.
Everything after that is negotiation.

The same rule shows up elsewhere in the compiler. Division and modulo
are not native-compiled, because a native `fdiv` by zero yields
infinity while the language promises a clean error, and two execution
modes that disagree are worse than one slow mode. A premise the solver
cannot translate aborts the whole proof rather than being silently
dropped, because proving with dropped premises manufactures false
counterexamples. Anything unprovable degrades to a runtime check rather
than being waved through.

None of these make the demo look better. All of them are the reason the
demo can be believed.

## Money is not a float, and Velaris will not let you pretend

Everything above is about being honest when a program genuinely needs
IEEE-754. Currency is the case where it does not.

`0.10` is not a double any more than `0.1` is. A hundred-rupee balance
built out of ten-rupee floats is not a hundred rupees, and the error
compounds quietly: it never trips an exception, it just ends the quarter
a few paise off, in a direction nobody chose. The proof story makes it
worse, not better. `ensures total >= 0.0` about floats is provable and
almost worthless, because the number it is proving things about is
already not the amount you meant.

So an amount in Velaris is not a `Float` at all. `Money of INR` (SPEC.md
§4.3) is a whole number of minor units - paise, cents, fils - with the
currency in its type:

```
let claim = money(125075, "INR")           // 1250.75, exactly
let fee = percent_of(claim, 25, 1000, "half_up")   // 2.5%, rounded
                                                   // the way you said
let parts = money.split(claim, 3)          // and they add up to claim
```

It is an `Int` underneath, so it proves the way whole numbers prove -
the same solver, the same milliseconds, none of the bit-blasting the
first half of this page is about. `money.split` promises that its parts
add up to exactly what it was given, and that promise is **proven**,
before your program runs, by the prover you already have.

Three things are compile errors rather than surprises: a `Float`
anywhere near an amount, two currencies in one sum, and `/` on an
amount - because dividing 100 paise three ways has to round, and Velaris
will not pick the rounding for you. You write `"half_up"`,
`"half_even"` or `"down"` in the call, or you use `money.split`, which
does not round at all.

If you are holding money in a `Float` today, that is the one case on
this page where the answer is not "be careful with floats" but "do not
use them".

## Try it

The compiler runs in your browser, no install:
<https://gowrishankar-infra.github.io/velaris-lang/playground.html>

Paste the function at the top of this page and watch it refuse. Then
change `ensures result == x + 0.2` to something IEEE actually
guarantees — say `ensures result >= x` — and watch it go through.

If you can make Velaris say "proven" about something that is false at
runtime, that is a soundness bug, and this project treats those as
security reports.

<https://github.com/gowrishankar-infra/velaris-lang>
