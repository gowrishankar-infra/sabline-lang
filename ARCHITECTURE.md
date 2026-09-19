# How the compiler works

The compiler is the package `velaris/`, one module per stage, in the order
the compiler uses them (8.2; until 8.1.1 it was one file, `velaris.py`,
in the same order - decisions/0001-split-the-file.md says why it was
split). Read the modules in that order and you follow a program through
the whole pipeline. This document is the map.

    text -> lexer -> parser -> loader -> effects -> checker (types)
         -> termination -> prover -> native codegen -> runtime

`velaris.py` at the top of the repository is a launcher: it puts this
directory first on the path and runs `velaris.cli.main`. `import velaris`
and the `velaris` command are what they were in 8.1.1; `check_api.py`
holds both to a golden.

## The modules, in order

`velaris/__init__.py` imports them in the order of `_MODULES`, and a module
imports only modules before it. The few names a stage needs from a later
one (seven, in `__forward__`) are bound after every module has loaded
(`_bind_forward`). `tests/unit/test_pipeline_order.py` fails when a module
imports one after it.

| Module | Holds |
|---|---|
| `version` | `VERSION`, `SITE` and `REFERENCE_URL`, where the package and its standard library are, `_launch_command` |
| `predicates` | the predicate type names, the earlier names each is read as, `predicate_kind` |
| `errors` | `VelarisError`, `ERROR_TABLE`, `REMOVED_ERRORS` |
| `lexer` | text to tokens |
| `nodes` | the AST dataclasses (`Function`, `Call`, `Let`, `Closure`, ...) |
| `parser` | tokens to the AST; `for` becomes `while`, inline functions are lifted |
| `tables` | `BUILTINS`, `FALLIBLE_BUILTINS`, `NEW_BUILTINS`, `builtin_reached`, the check ceilings |
| `confine` | the confinement levels `velaris eval` gives its worker, and `probe` |
| `state` | everything a run can change: the budget, the program's arguments, Python handles, the import root |
| `recorder` | `_RunRecorder`, the notes a receipt is made from |
| `loader` | imports, blame, `_import_refusal` (E515) |
| `values` | runtime values and `FailSignal` |
| `wrappers` | `Secret of T` and `Money of CUR` over type text |
| `budget` | `Budget`, every grant and refusal, the guarded opener, `checked_int` |
| `effects` | the effect checker, and E204 |
| `checker` | types, the Secret sink check (E560), the rules for `main` |
| `termination` | whether each loop is shown to end |
| `prover` | Z3: `check_proofs` |
| `native` | llvmlite: `compile_native` |
| `runtime` | the interpreter: `interpret`, `run_builtin` |
| `witnesses` | `velaris test --from-contracts` |
| `editor` | `inspect_source`, `editor_answer`, `lsp_serve` |
| `formatter` | `velaris fmt` |
| `project` | `add`, `deps`, `verify`, `build`, `new` |
| `session` | the REPL |
| `results` | `CheckResult`, `AuditResult`, `RunResult`, `Problem` |
| `library` | `check`, `audit`, `run` and what they share |
| `pool` | `Pool`, `pool_worker`, `MUTABLE_GLOBALS`, `reset_program_state` |
| `findings` | SARIF (`_SarifRun`, `sarif_check`, ...) and `InvocationLog` |
| `mcp_manifest` | `mcp-manifest` and `mcp-verify` |
| `doors` | the HTTP door (`serve_main`), `door_ceilings`, `run_limits` |
| `migrate` | `velaris migrate` |
| `ratchet` | the capability ratchet and `review` |
| `conform` | `velaris conformance` |
| `attestation` | `attest_statement` and `attest` |
| `receipts` | `receipt_statement` |
| `statements` | `velaris verify` of an attestation or a receipt |
| `receipt_diff` | `velaris receipts diff` |
| `evaluation` | `velaris eval` and its pool |
| `replay` | `velaris replay` and the recorded tool responses |
| `upgrades` | `deps-diff` |
| `stats` | `velaris stats --ffi` |
| `eject` | `velaris eject` and the launcher it writes |
| `permissions` | the workflow-permissions ratchet |
| `cli` | `main`, `usage_lines`, `--help` |

## The stages

**Lexer** turns text into tokens. Keywords are a fixed set; everything
else is an identifier, a literal, or an operator.

**Parser** builds an AST of dataclasses (`Function`, `Call`, `BinOp`,
`If`, `While`, ...). Two things are desugared here so nothing later
has to know about them: `for` loops become `while` loops, and inline
functions are lifted into ordinary top-level functions. That is why
proofs and native compilation work on them unchanged.

**Loader** resolves `import`, tracks which file each function came
from (for error blame), and prefixes names for a named import.

**Effect checker** walks the call graph. A function may only perform
effects it declares, transitively. This runs before types because a
missing effect is a clearer error than a type mismatch downstream. A call
to a local is a call to a function value only when that local holds one;
a local of any other kind named like a built-in or like one of the
program's functions does not hide the call (8.2).

**Type checker** infers local types, checks calls, unifies generics at
call sites, and decides which builtins are fallible in context (`get`
on a map can fail; on a list it cannot). It also carries `Secret of T`
(6.0, SPEC.md §3.1): which record types hold a secret is a fixpoint
computed once per program; every pure operation over a secret gives
one, a comparison included; no builtin that declares an effect or can
fail accepts an argument carrying one (E560); no type variable is bound
to one; and no `if` or `while` branches on one (E563). `declassify` is
the only way out, and it is an effect, so the effect checker above
enforces it like any other.

**Prover** is the interesting part. For each function it explores the
body symbolically, building Z3 formulas, and asks whether the
`ensures` can be false given the `requires`. Calls use *summaries*:
the callee's contract is assumed, its body is never inlined. Loops use
invariants — written, or inferred for simple counter bounds. The rules
that matter most are in SPEC.md §9; the one to internalise is that an
untranslatable premise abandons the proof rather than dropping it.

**Native codegen** (llvmlite) compiles pure functions over Int, Float,
Bool, list reads and text reads — and functions whose contracts are
proven, since a proven promise needs no runtime check. Anything that
cannot be made identical to the interpreter is not compiled. Whole-number
arithmetic, unary minus included, stops with E407 outside 64 bits in both.

**Interpreter** runs everything, with runtime checks for promises the
prover could not settle.

z3 and llvmlite are imported only when a check has a promise to prove or a
run has a function to compile (`check_cli.py` measures it).

## Where things live

| What | Where to look |
|---|---|
| Adding a builtin | `BUILTINS` (`tables`), then `run_builtin` (`runtime`) |
| Making a builtin fallible | `FALLIBLE_BUILTINS` (`tables`) |
| A new proof capability | `to_z3` in `prover` |
| A new statement | `parser`, then `explore` (`prover`), the interpreter (`runtime`), and `native` |
| Editor features | `editor_answer` and `lsp_serve` (`editor`) |
| CLI commands | `main` (`cli`), near the other `argv[:1] == [...]` checks, and a line in `usage_lines` so `--help` has it |
| Anything a program can leave behind | `state`, `MUTABLE_GLOBALS` and `reset_program_state` (`pool`), and the scan in `check_pool.py` that fails when a new module-level container appears in neither list |
| A new error code | `ERROR_TABLE` (`errors`): one line saying what it means. `check_library.py` fails if a code is raised that is not there; the errors page and the SARIF rules are built from it; `check_error_messages.py` needs a case for it. In a minor or patch release it needs a `compatibility:` line in the CHANGELOG (RELEASING.md) |
| The HTTP door | `serve_main` (`doors`): the token, `--no-auth`, the ceilings, the endpoints. The time and memory ceilings both doors share are `door_ceilings` and `run_limits` |
| SARIF, the invocation log, the MCP tool manifest | `findings`: `_SarifRun` and `sarif_check`/`sarif_proofs`/`sarif_audit`, `InvocationLog`; `mcp_manifest`: `mcp_manifest_main` and `mcp_verify_main`, kept out of `velaris_mcp.py` so the server file cannot vouch for itself |
| The capability ratchet | `ratchet`: `_program_capabilities` derives one file's needs (`_needs` for the grants, `_operation_bounds` for the counts), `capability_scan` a tree's, `capabilities_compare` holds a tree to a baseline - never to a previous commit - and `review` compares a git ref with the working tree. velaris-spec section 9 is the text of every rule there |
| A removed error code | `REMOVED_ERRORS` (`errors`): STABILITY.md rule 3 |
| Conformance | `conform`: `conformance` runs velaris-spec's corpus through the budget parser, the audit, the command line and the baseline writer and check; `build_conformance.py` writes that corpus from the tables of `check_sandbox.py`, `check_library.py` and `check_ratchet.py` |
| The attestation | `attestation`: `attest_statement` wraps `audit()`'s own output in an in-toto Statement, the audited file and its imports as subjects by sha256; `attest` does a file or a directory. It signs nothing; the release workflow's `attestation` job signs one with cosign and with sigstore-python and verifies both |
| A run's receipt | `recorder`: `_RunRecorder` notes each refusal and declassification as it happens, once per place with a count; `receipts`: `receipt_statement` makes the Statement; `_run_in_process` (`library`) attaches one to every run, and a pool worker streams its notes over the protocol pipe so a run killed by its limit keeps them. Nothing there may hold a value the program handled |
| Checks and audits under a ceiling | `check`, `audit` and `attest` hand the work to a one-worker `Pool` unless both limits are None; `Pool.check` and `Pool.audit` send an `op` request to `pool_worker`, which calls `_check_here` or `_audit_here`, and a kill becomes E613 or E614. `_run_bounded` is a one-worker pool too. `_IN_CHILD` (`state`) keeps a call inside a worker from starting another |
| Where imports may come from | `IMPORT_ROOT` (`state`) and `_import_refusal` (`loader`), checked in `load_program` before a file is opened (E515). The doors set it to the directory they serve and compile a request as a file there; a program given to the library as text is written into a directory of its own (`_source_to_file`, 8.2) |
| The command line's own flags | `main` (`cli`): on a run, `--` ends them, and every word after it is the program's `args()` (8.2) |
| What an upgrade gained | `upgrades`: `deps_diff` reads two versions of one dependency; `_deps_velaris` runs the ratchet's `capabilities_compare` with the older version as the baseline; `_hooks_diff` and `_declared_diff` compare install-time scripts and declared dependencies. Nothing there derives an effect from code that is not Velaris |
| A predicate type's name | `predicates`: the capability/v1 and receipt/v1 names on velaris-lang.dev, the earlier names each is also read as, and `predicate_kind`, which every reader asks - `statements`, `receipt_diff`, `replay` - so a type Velaris does not define is refused in one place (8.3) |
| The evaluation profile | `evaluation`: `eval_budget` refuses what the profile does not take before the program is read; `_EvalPool` starts a one-process worker with `--stop-file` and `--confine`; `confine` holds each level (`confine_linux`, the job object's one-process limit from `library`, `mac_wrapper`) and `probe`. The stop is `stop_point` (`runtime`), polled every `STOP_EVERY` calls and loop turns (8.3) |
| Comparing, replaying and verifying receipts | `receipt_diff`: `against_audit` and `against_receipts`; `replay`: `snapshot` holds each subject to its digest and copies it, `compare` names every field that differs, `ResponseLog` and `ResponseReplay` record and give back `py` calls (E616); `statements`: `unwrap`, `subject_file` and `verify_file` (8.3) |
| Witnesses from contracts | `find_witnesses` inside `check_proofs` (`prover`) asks Z3 for argument lists the `requires` allows, boundaries first; `witnesses`: `from_contracts` runs each, interpreted, with no effect granted (8.3) |
| A value in a log line | `log_line` (`values`): `log`, `stdlib/log.vel` and `velaris trace` write every control character, DEL, U+2028 and U+2029 escaped, so a call writes one line (8.3) |
| The workflow-permissions ratchet | `permissions`: `read_workflow` reads each `permissions:` block with no YAML dependency, `permissions_compare` holds the head to the base; the Action's `permissions-ratchet` input runs it (8.3) |
| Ejecting | `eject`: `eject_main` copies the program, its imports, the package and the standard library files it uses, and writes `main.py` from `_EJECT_LAUNCHER`, which fixes the budget, checks the digests, and refuses a budget that writes into its own directory or where Python imports from |
| Keeping suites apart | `suite_dirs.py`: each suite's own temporary directory, so two runs from one checkout never write the same file |
| The release gate | `release_checks.py`; its fixtures are `check_release.py` (RELEASING.md) |
| What runs on a schedule, and what to do when it fails | MAINTENANCE.md |

## The suites, and what each one is for

| Suite | Asks |
|---|---|
| `run_tests.py` | do all 97 examples reach their expected verdict |
| `run_unit_tests.py` | does each stage, on its own, do what SPEC.md and LLM.md say (`tests/unit`), and does each module import only those before it |
| `fuzz_native.py` | do the native and interpreted engines agree exactly |
| `fuzz_parsers.py` | do the parser, JSON, CSV, `py_json` and the contract translator end every input in a value or a coded error (coverage-guided) |
| `check_refusals.py` | is each wrong program refused with the RIGHT code |
| `check_error_messages.py` | is every error code's message what its golden says (`tests/error_messages`) |
| `check_sandbox.py` | can the effect budget be escaped |
| `check_fallible.py` | is every fallible builtin actually enforced |
| `check_library.py` | do the library and MCP server keep the same promises |
| `check_api.py` | is what the library, the command line, the doors and the Action offer what `tests/api/golden.json` records |
| `check_cli.py` | does every command answer `--help`, and are z3 and llvmlite imported only when used |
| `check_pool.py` | can a pooled worker leak anything to the next program |
| `check_pool_soak.py` | does a pool stay flat, survive kills and leak nothing over thousands of runs (monthly) |
| `check_termination.py` | does each loop get the termination verdict it must |
| `check_money.py` | are amounts exact, kept to one currency, and rounded only where the call says so |
| `check_secret.py` | can a `Secret` reach anything that emits it, and is `declassify` the only way out |
| `check_ratchet.py` | does every widening of the capability surface fail, against the declared baseline and not the previous commit, and does every change that does not widen pass |
| `check_deps.py` | does `deps-diff` report what an upgrade gained - a Velaris library's declared surface; for anything else only its install-time scripts and declared dependencies, with the surface said to be unknown - and is its pull-request comment edited rather than duplicated |
| `check_adversarial.py` | do the attempts of every adversarial pass stay refused - the proof cache that is gone, the proxy, the prover's names, imports, receipts, eject, the door's rate, 64-bit edges, names that shadow, and 8.3's eval, receipts diff, replay, witnesses, log lines and verifier |
| `check_prover_lies.py` | is a false promise ever reported proven, under five Z3 seeds |
| `check_metamorphic.py` | is the audit unchanged by renaming, reordering and splitting, and changed by exactly one added effect |
| `check_properties.py` | over generated programs: does the formatter round-trip, is check deterministic, does the audit match what a run did |
| `check_hostile.py` | does every hostile resource end in a coded error, never a traceback |
| `check_self_budget.py` | can anything a program or its surroundings control - arguments, the working directory, the environment, files beside it - widen its budget or change its audit |
| `check_docs.py` | are the documents true: code blocks, commands, counts, error codes, paths |
| `check_identical.py` | are the audit and SARIF the same bytes on Linux, Windows and macOS |
| `check_differential.py` | does every difference from the previous release appear in the CHANGELOG |
| `perf_gates.py` | the numbers each release publishes, and pure-numeric time against the previous tag |
| `check_mutants.py` | would the suites notice a change to a line a guarantee rests on (monthly) |
| `check_mutant_kills.py` | does a test now fail for every mutant a monthly run found surviving - the ceiling, credential, proxy, range, effect, currency and prover lines - where it is not shown equivalent |
| `check_release.py` | does the release gate decide what RELEASING.md says, and does the kill switch stop a release |
| `check_workflows.py` | do the scheduled workflows report and change nothing |
| `check_install.py` | does every artefact, installed as a user installs it, run discount.vel and refuse the network (nightly) |
| `check_nightly.py` | does every probe nightly.yml runs pass against a local install, and is a program that is not there one BROKEN line rather than a traceback |
| `check_urls.py` | does every URL the documents name still answer (monthly) |
| `check_lint.py` | mypy --strict and ruff over the package and every script, and the complexity report |
| `check_platform.py` | does the reference platform refuse at submission, at run time and at its audit limit what it says it refuses |
| `check_eject.py` | does an ejected program run from a fresh virtual environment with nothing from here, and hold its budget |
| `check_policies.py` | do the OPA policy and its Kyverno twin ask what they say (`opa` when installed) |
| `check_eval.py` | does `velaris eval` refuse every relaxation of its profile, honour a stop from outside, kill a worker past its grace, and write a receipt that names its confinement - and does each refusal that confinement claims hold |
| `check_receipts.py` | does `receipts diff` name each kind of difference from an audit and from earlier receipts, does `replay` run the recorded bytes or refuse, and does `verify` refuse what it says it refuses |
| `check_from_contracts.py` | does a witness the prover finds break an `ensures` left to runtime, pass a true one, and is a function with effects refused |
| `check_impossible.py` | is each class docs/structurally-impossible.md lists tried, and refused |
| `check_permissions.py` | does every widening of a workflow's `permissions:` fail, and nothing else, from 30 base and head fixtures |
| `velaris test examples/std_test.vel` | does the standard library behave |
| `velaris conformance` | does this implementation pass velaris-spec's corpus, at L1, L2 and L3 |
| `velaris migrate --to 5.0` | the narrowest budget each program needs, now that a run with no `--allow` gets `io` |
| `build_conformance.py --check` | is velaris-spec's corpus still what these suites' tables say |

Conformance to [velaris-spec](https://github.com/gowrishankar-infra/velaris-spec),
the capability format published separately, is its corpus: from 4.1,
456 JSON cases in velaris-spec's `tests/`, at three levels its
CONFORMANCE.md defines, which an implementation in any language runs
its own way. Until 4.1 it was six suites of this repository -
`check_termination.py`, `check_sandbox.py`, `check_refusals.py`,
`check_fallible.py`, `check_library.py` and `check_ratchet.py` - run
without the prover, which only an implementation driven through this
command line and library could run. The corpus is written by
`build_conformance.py` from the tables of three of those suites -
`check_sandbox.py` for level 2, `check_library.py` and
`check_ratchet.py` for levels 1 and 3 - where each entry is asserted
against this implementation, so a case says what its suite says.
`velaris conformance` runs the corpus against this implementation, and
CI runs it and `build_conformance.py --check` on every leg. None of it
needs the prover.

## The rules this project holds

1. **Never claim something is proven when it is not.** If a premise
   cannot be translated, abandon the proof; runtime checks still guard.
2. **Native and interpreted must agree.** If they cannot, do not
   compile that case. `fuzz_native.py` checks this on every leg.
3. **Every new example gets `velaris fmt`** before it ships.
4. **A moved or deleted file needs an explicit `git rm`** — release
   archives overlay, they do not delete.
5. **Write the limitation down.** The changelog records mistakes on
   purpose; a project that only lists wins cannot be trusted about
   anything else.

6. **A worker pool must reset every mutable global between programs.**
   `velaris.Pool` runs one program after another in one process, which
   is exactly where one program's leftovers become the next program's
   starting state. Anything a running program can change lives in
   `velaris/state.py`, and belongs in `MUTABLE_GLOBALS` and in
   `reset_program_state`; `check_pool.py` reads the package's
   module-level assignments and fails if a mutable one is in neither
   that list nor its list of constants. Speed is never the reason to
   skip a reset - a fast sandbox that leaks state between programs is
   worse than a slow one.

7. **Run every new suite WITHOUT the prover before wiring it into CI.**
   This has been got wrong three times - v2.39.1, v2.44, v2.53.1 - and
   always the same way: a suite passes locally, joins CI, and every
   no-solver leg fails because some check quietly depended on proofs.
   Make a Python with no z3 and run the suite there first:

       python -m venv /tmp/bare && /tmp/bare/bin/pip install ".[test]"
       /tmp/bare/bin/python check_whatever.py

   (`[test]` is what the suites need and Velaris does not; it brings no
   solver.)

   Better than skipping the proof-dependent checks is asserting the
   FALLBACK - that the promise breaks while running instead - which is
   what `check_library.py` does now.

8. **A scenario in a suite's table is a conformance case.** An entry
   added to or changed in `ESCAPES`/`HONEST` (`check_sandbox.py`),
   `BUDGETS`/`AUDITS`/`malformed_budgets()` (`check_library.py`), or a
   table of `check_ratchet.py` changes velaris-spec's corpus. Regenerate
   it (`python build_conformance.py ../velaris-spec/tests`) and commit it
   there in step; CI's drift test fails until the two agree. A case
   that depends on Python itself says so in `not_in_corpus`, and is left
   out with the reason.

9. **Robots report; people fix.** The nightly, monthly and adversarial
   workflows open issues and never commit; the nightly closes the ones it
   opened once a run passes in full (MAINTENANCE.md, `check_workflows.py`).

## Working on it

    pip install -e ".[full,test]"
    python run_tests.py          # 97 examples, expected verdicts
    python run_unit_tests.py     # each stage on its own
    velaris test examples/std_test.vel
    python fuzz_native.py 60     # both engines must agree
    velaris fmt examples/*.vel stdlib/*.vel --check
    python check_lint.py         # mypy --strict, ruff

CI runs these and every suite above on Linux, Windows and macOS (x64 and
arm64), with and without the optional solver: test.yml, and RELEASING.md
for what a release needs beyond it.
