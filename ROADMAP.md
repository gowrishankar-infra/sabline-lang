# Roadmap

What is planned, what is deliberately not, and how to influence both.
Dates are absent on purpose: this is maintained by one person, and a
date would be a guess dressed as a promise.

## Now

- Answering issues and fixing what people actually hit. A reported bug
  from a real user outranks everything below it.
- Editor depth: completion, and rename.
- A Docker image, and cross-compilation for `sabline build` (today it
  builds only for the machine it runs on).

## Next

- Logging conventions and structured output for programs that run
  unattended.
- More of the standard library over FFI: CSV, dates as values rather
  than text, a small HTTP client with headers.
- Proof reporting: a summary of which promises in a project are proven
  and which fall back to runtime, so a team can watch that number.

## Later, and honestly uncertain

- Native `push` (building lists in machine code), which needs an
  ownership design the language has deliberately avoided so far.
- Richer text proofs.
- Self-hosting: writing the Sabline compiler in Sabline.

## Not planned

- **Concurrency.** See [SPEC.md §13](SPEC.md#13-concurrency): the
  effect system cannot currently describe data races, and threads
  without that would break the language's central claim.
- **A package registry.** Libraries are vendored with a recorded
  hash (`sabline add`), which is auditable and does not require
  anyone to run infrastructure forever.
- **Exceptions**, closures, inheritance, macros, operator overloading.
  Each was considered and left out; SPEC.md §16 lists them.

## How this changes

Open an issue. A concrete use case that Sabline handles badly is the
most persuasive thing you can send, and it is how most of the last
thirty releases were chosen.
