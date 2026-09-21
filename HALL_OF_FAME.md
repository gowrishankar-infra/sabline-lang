# Hall of fame

People and models who made Sabline report something false, or found a
way past what it claimed, and so made it better. The standing
challenge that adds to this list is in [SECURITY.md](SECURITY.md):
credit here and in the changelog, and a fix within a week. There is no
money.

Each line: who, when, what they found. The details are in the
CHANGELOG.md entry named.

## Adversarial reviews by model, August 2026

Three model families - a Gemini model, a ChatGPT model and a Claude
model - each read `sabline card`, wrote programs, and then set out to
break the language. The changelog entries recorded what each review
found and not which family produced it. The names below were added in
3.2 from the maintainer's account, not from a record made at the time,
and the changelog entries now carry them too.

- **First card review** - a Gemini model, then a ChatGPT model -
  2026-08-18 - the first program the Gemini model wrote from the card
  was correct and crashed the prover: a record pushed onto a list
  inside a `check` inside a loop reached a comparison that assumed
  every value has a Z3 sort (2.41.1). The same day the ChatGPT model
  removed a `requires length(items) > 0` guard from its own expense
  report and predicted the compiler would catch the division; it did
  not - the divide-by-zero proof was skipping itself whenever a loop
  had touched the path (2.41.2).
- **Install-and-attack review** - a Claude model - 2026-08-19 - a
  30-function calculator that compiled and ran first try, then a list
  of what was missing or wrong: no way to shrink a list (`pop`,
  `slice`, `set_at`
  were added, and were then found to be unenforced - see the next
  line), overflow that no `check` could catch (`add_or_fail` and
  friends), a `break` that reported "unknown variable", a formatter
  that contradicted the documentation, and the prover going blind
  when a loop mutates a list - which was documented as a limit rather
  than fixed (2.42).
- **86-artifact review** - a Claude model - 2026-08-19 - one production
  program, 34 broken fragments and 52 single-point mutations, scored
  76/100, and
  found the soundness hole of that month: `pop`, `slice` and `set_at`
  were documented fallible but the checker never demanded handling,
  so a clean `sabline check` could be followed by a raw traceback. Also
  a checker that could crash instead of reporting, `main` validated
  only at runtime, and a typed FFI that sent numbers as text (2.44;
  `check_fallible.py` exists because of this review). A third pass by
  the same review held the score at 88 and found five more at the
  edges - a zero divisor from input that no `check` could see, an
  HTTP envelope that was text instead of a record, a `fail_with` that
  did not fail (2.47).

## The spec extraction, September 2026

Writing sabline-spec 0.1 from sabline-lang 3.1.1 - stating each rule of
the capability format precisely enough to implement without the compiler
- turned up five places where the compiler did not do what the format
says. 3.2 recorded them and changed no code; 3.3 fixed all five, and the
spec went to 0.2 resolving the questions they close. Credited here under
the standing challenge to the spec extraction, 2026-09-11. The details
are in the 3.3 CHANGELOG entry.

- **The spec extraction** - 2026-09-11 - `ffi:M` checked the module a
  call named and not the module its attribute chain reached, so
  `py("json", "codecs.encode", ...)` ran codecs code under `ffi:json`
  (sabline-spec Q9); `ffi` grants were not additive, so `ffi,ffi:math`
  granted `math` alone against the reference text (Q2); `safe_command`
  wrote IPv6 hosts without brackets and could not carry a `,` or `@` in a
  path or host, so it did not round-trip (Q5); the budget parser accepted
  an unknown effect name in `uses` and read a count with non-ASCII digits
  (`fs@²` stopped it with an uncaught error) (Q1, Q6); and the command
  line's `audit --json` printed an unversioned shape the schema rejected
  instead of `sabline.audit/1` (Q3).

## The conformance corpus, September 2026

- **Writing sabline-spec's conformance corpus** - 2026-09-11 - an audit
  case for a program whose `uses` clause names something that is not an
  effect (`uses io, teleport`) found that the audit reporting the E300
  still listed `teleport` in `effects` and in its function's `effects`,
  and wrote a `safe_command` that does not parse - where sabline-spec
  said `effects` is always a subset of the seven and `safe_command`
  always parses. 3.3 had fixed the compile check and not the document
  that reports it. Fixed in 4.1; the details are in the 4.1 CHANGELOG
  entry.

## External assessments, September 2026

- **Two independent external assessments of 8.0.0** - reported by
  2026-09-14 - each found that a proof cache entry in the per-user
  directory 7.1.2 had moved the cache to was still believed: a process
  running as the same user, or an `XDG_CACHE_HOME` or `LOCALAPPDATA`
  pointed at a directory it chose, could plant one with the real proof key,
  and a false `ensures` was reported proven by `check`, `proofs` and
  `audit` and, compiled to native code, ran unchecked. Fixed in 8.1.1 by
  believing nothing the cache holds; the details are in the 8.1.1
  CHANGELOG entry and advisory-proof-cache-2.md.

## Automated review, September 2026

- **CodeRabbit, the review bot on the CrewAI pull request
  [crewAIInc/crewAI#7279](https://github.com/crewAIInc/crewAI/pull/7279)**
  on 2026-09-05, flagged what three human reviews had also noted and
  the project kept deferring: nothing bounded how long a program could
  run or how much
  memory it could take. `timeout=` and `max_memory_mb=` in
  `sabline.run` are the result (2.59).
