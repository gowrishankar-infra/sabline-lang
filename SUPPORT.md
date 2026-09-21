# Support

## What you can expect

Sabline is maintained by one person, Palakurthi Gowri Shankar, in his own time.
Being honest about what that means:

- **Bugs**: reported bugs get looked at, usually within a few days. A
  soundness bug - the prover claiming something is proven when it is
  false - is treated as a security issue and comes first
  (see [SECURITY.md](SECURITY.md)).
- **Questions**: open a GitHub issue. There is no chat, forum or
  mailing list, and pretending otherwise would waste your time.
- **Guarantees**: none. There is no commercial support, no SLA, and no
  contract. If your organisation needs those, this project cannot
  offer them today, and you should weigh that before depending on it.

## Releases

Releases happen when something is ready, not on a schedule. Every
release is tagged, published to PyPI automatically, tested on Linux,
Windows and macOS with and without the optional solver, and described
in [CHANGELOG.md](CHANGELOG.md) - including the mistakes.

Semantic versioning is followed strictly: breaking changes only at
major versions, and the last one (2.0) shipped with compiler-guided
migration that pointed at every call site needing an edit.

## If you are evaluating Sabline for an organisation

Read [SPEC.md](SPEC.md), especially §13 (no concurrency) and §16 (what
the language does not have). The effect budget can now name Python
modules (`ffi:math,json`) and bound time and memory; see EMBEDDING.md. Then consider the real risk, which is not
technical: one maintainer, few users, and a young ecosystem. That risk
is genuine, and no feature list removes it.

Sabline is a reasonable choice today for tools, scripts, data work and
teaching - things where a single person owns the code and wants to be
able to prove what it does. It is not yet a reasonable choice for
systems your business depends on.

## Contributing

The whole compiler is one readable file. [CONTRIBUTING.md](CONTRIBUTING.md)
explains how to work on it. A second maintainer would change several of
the answers above, and that is an open invitation.
