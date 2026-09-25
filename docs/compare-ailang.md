# Sabline compared with AILANG

<!-- description: AILANG 0.42.0 and Sabline, from AILANG's documentation read in full: where AILANG is ahead comes first, then where the two differ. -->

Like AILANG, Sabline puts effects in signatures and refuses what a run was
not granted, and both let the person running a program narrow it. Sabline's
refusals cannot be caught by the program, its grants name several paths,
read or write, and a host with its port, and `sabline audit` shows what a
program can touch before it runs.

AILANG is the language nearest to Sabline's: a purely functional,
effect-typed language "designed as a deterministic execution substrate for
AI-generated code" (its README). This page is drawn from its own
documentation, read in full - every page of its documentation site, its
README, CHANGELOG, SECURITY.md and `docs/LIMITATIONS.md` - and it starts
with where AILANG is ahead.

> [!NOTE]
> **Last verified:** 2026-09-25, against **AILANG 0.42.0** (released
> 2026-09-23) and **Sabline 8.6.0**. Nothing here was measured by running
> AILANG; every statement about it is what its documentation says, with the
> page and that page's date. Where its documentation describes no
> equivalent of something, this page says "its documentation describes no"
> and means only that - it names what was searched for, not a claim about
> what AILANG cannot do. AILANG moves quickly (173 releases in a year), so
> read this against its [changelog](https://github.com/sunholo-data/ailang/blob/dev/CHANGELOG.md).

## Where AILANG is ahead

- **Information flow with labels you name.** Values can carry labels -
  `<pii>`, `<email>`, a tenant's name - that "are not a fixed vocabulary";
  a sink can refuse a label (`T{not LABEL}`), and changing a label is an
  effect of its own, `! {Declassify}`, checked when the program is compiled
  ([IFC labels](https://ailang.sunholo.com/docs/guides/ifc-labels), page of
  2026-08-17). Sabline has one label: `Secret of T`.
- **Processes, narrowed to the subcommand.** A process allowlist is pinned
  at start-up and can name subcommands: `git:status,gh:pr:list` "allows
  `git status …` … and refuses every other invocation"
  ([effects](https://ailang.sunholo.com/docs/reference/effects), page of
  2026-09-11). Sabline has no model of a subprocess: its `ffi:` grants a
  whole Python module, and `ffi:subprocess` is a shell.
- **More effects.** Besides files, network, environment, clock and
  randomness: a process effect, streams, a typed `AI` effect across
  Anthropic, OpenAI, Gemini, Ollama and OpenRouter, a `Secret` effect that
  resolves 1Password references behind an approval pushed to a phone
  ("code-complete - deploy-gated", on its own page), and shared memory for
  agents.
- **Counts on both sides.** A function's signature can carry a maximum and
  a minimum - `! {IO @limit=5, Net @min=1 @limit=3}` - charged per call and
  to every enclosing call
  ([capability budgets](https://ailang.sunholo.com/docs/reference/capability-budgets),
  page of 2026-07-24); and in its policy mode the operator sets a count per
  effect for the whole run, which "a source @limit can only tighten"
  ([agent tool policy](https://ailang.sunholo.com/docs/guides/agent-tool-policy),
  page of 2026-09-23). Sabline's counts are the operator's alone.
- **Package effect ceilings.** A package declares the most it may do
  (`max = ["IO"]`), the compiler holds it, and the package registry checks
  it again and warns when a new version widens it
  ([packages](https://ailang.sunholo.com/docs/guides/packages), page of
  2026-09-17). Sabline has `deps-diff` and a committed capability baseline,
  but no registry.
- **A prover that gates publishing.** `ailang verify` uses Z3 over
  strings, lists, records and algebraic types, inlines calls across
  functions and unrolls recursion to a bounded depth, with counterexamples
  ([contracts](https://ailang.sunholo.com/docs/guides/contracts), page of
  2026-04-30), and the registry refuses to publish a package whose contract
  is refuted.
- **Property-based tests**, with shrinking to a minimal counterexample.
- **A much larger public evaluation of how well models write it**: 18
  models and several agent harnesses against a pinned Python baseline, with
  its losses published beside its wins - in its dashboard data for 0.32.0
  (2026-08-27), AILANG 92.1% and Python 89.4% on its core tier, and 68.3%
  against 82.8% on first attempts overall
  ([benchmark data](https://ailang.sunholo.com/benchmarks/latest.json)).
  Sabline's own [round trip](roundtrip.md) is far smaller.
- **Reach beyond the language.** One command serves any module as an MCP,
  A2A or REST server; there are plugins for Claude Code and Codex, Go code
  generation, and an orchestration layer for fleets of agents with
  approvals and a messaging bus.

## Where they are alike

Effects are declared in signatures and checked by the compiler, a program
running with an effect it was not granted is stopped, and the person running
it can narrow what it may reach below the effect: AILANG's domain allowlist
(`--net-allow-domains`), filesystem root (`AILANG_FS_SANDBOX`) and process
allowlist belong to the invocation rather than the type, as Sabline's
`--allow` grants do. Both re-check a redirect's host (AILANG since 0.41.0)
and refuse to send through a proxy they cannot see past (AILANG in its
policy mode), and both prove `requires` and `ensures` with Z3.

## Where they differ

As its documentation describes it, read 2026-09-25:

| | AILANG 0.42.0 | Sabline |
|---|---|---|
| A refused host or command | comes back as an error value the program can match on and carry on from (`DisallowedHost`, `NotAllowed`) - [effects](https://ailang.sunholo.com/docs/reference/effects) | ends the run; the program cannot catch it (E310, E313, E314, E315) |
| Files | one root per run; write-protected paths inside it in policy mode | several grants, each read or write: `fs:read:./data,fs:write:./out` |
| Network | a domain allowlist; its documentation describes no grant by port | a host and its port: `net:api.example.com:443` |
| Counts | per function in the signature; per effect for a whole run in policy mode | per grant, set by the operator on any run: `net:api.example.com@100` |
| Before running | a policy admission check that names what is missing; its documentation describes no report of everything a program can touch | `sabline audit`: every effect, which functions reach it, and every declassification with its reason |
| Under the interpreter | Go's `os.Root` for its filesystem root; "host isolation is the container's job", and no OS sandbox is described ([agent tool policy](https://ailang.sunholo.com/docs/guides/agent-tool-policy)) | the operating system holds the same budget - Landlock and seccomp on Linux, fully; partly on macOS and Windows - and each run says which it got |
| Time and memory | a whole-run timeout in policy mode; memory is Go's soft target | a timeout and a memory cap the OS enforces (best-effort on macOS), through the library and every door |
| Contracts the prover cannot settle | runtime checking is a flag (`--verify-contracts`); effectful functions are skipped | checked at run time automatically |
| Failures | `Result` values | `or fail` in the signature, and a failure left unhandled is refused (E520) |
| Python or Go called from the program | its documentation describes no effect for `extern func` | `ffi:` is an effect, granted per module |
| A record of a run | traces, and unsigned receipts for agent dispatch | a receipt of a run when asked (`--receipt`), and in-toto attestations of the declared surface |

AILANG's own security audit found that its filesystem root could be left
through `../` and symbolic links, and its domain allowlist through a
redirect, until version 0.41.0 (2026-09-21), which fixed both
([its CHANGELOG](https://github.com/sunholo-data/ailang/blob/dev/CHANGELOG.md)).
Sabline's [known-open table](known-open.md) lists what is open in Sabline
the same way.

## Which to use

- **AILANG**, to write whole agent programs in a language with effects:
  model calls, tools, processes, labelled data flowing between them, a
  package ecosystem and a fleet to run them in.
- **Sabline**, to run a script a model wrote under a budget someone else
  sets, where a refusal must end the run and the budget should be held by
  the operating system too - and to see, before running it, what it can
  touch.
- Both bound only programs written in themselves.
