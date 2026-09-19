# Maintaining Velaris

What runs, when, and what to do when it is red (8.2). RELEASING.md is how a
release is made; SECURITY.md is how a report is handled; ARCHITECTURE.md is
where things live. This file is the rest.

## The rule: robots report, people fix

Everything that runs on a schedule - nightly, weekly, monthly - reports what
it found as a GitHub issue and does nothing else. No scheduled job commits,
pushes, tags, publishes, or opens a pull request, and none may:

- the workflow token reads the repository and nothing more;
- only a job named `report` may write, and only issues (`issues: write`);
- every checkout keeps no credential (`persist-credentials: false`);
- `open_issues.py` is the only thing that writes, and its `gh()` refuses any
  command but listing, opening, commenting on and closing issues (a close
  only with a comment), making a label, and reading a run's logs and
  annotations. It closes only an issue it opened, and only for the nightly,
  once a run in which every job passed shows that issue's job passing;
- `check_workflows.py`, on every push, reads the three scheduled workflows
  and fails if any of that stops being true;
- `check_nightly.py`, on every push, runs each of nightly.yml's probes
  against a local install, so a probe that cannot run fails there, not at
  02:23.

Dependabot opens pull requests; a person merges them. A person reproduces
every finding before anything changes, and a fix goes through a pull
request and test.yml like any other change.

## What runs when

| When | Workflow | What | Issues it opens |
|---|---|---|---|
| Every push to main and every pull request | `test.yml` | 18 legs - Linux, Windows and macOS x64, Python 3.10 and 3.12, with and without z3 and llvmlite; Linux and macOS arm64 on 3.12; Python 3.14 on Linux, allowed to fail - each running every suite (ARCHITECTURE.md lists them); the same audit and SARIF bytes on three systems (`identical`); mypy --strict and ruff (`lint`); suites twice at once (`concurrent`) | none: a red run is the report |
| A push to main whose tests passed | `release.yml` | the gate, then - for a release - pure-numeric time against the previous tag (`perf`), every difference from the previous tag named (`differential`), the builds and signatures, the kill switch, the tag and every publish (RELEASING.md) | none |
| Every night, 02:23 UTC | `nightly.yml` | every artefact built from main and installed as a user installs it - the wheel and the sdist on three systems, the MCP bundle, the npm wrapper from the registry, the standalone executables, the Docker image, the pre-commit hooks, the Action, the VS Code extension's language server - each running `examples/discount.vel` and refusing a program that fetches a URL (`check_install.py`) | one per failed job, label `nightly`; the next run in which every job passes closes them, naming itself |
| Every Monday, 04:11 UTC | `adversarial-models.yml` | the standing adversarial prompt (`.github/adversarial/PROMPT.md`), this week's area of the compiler, sent to Claude (Claude Code), Gemini (Gemini CLI) and Grok (xAI API); a model whose key is not set is skipped | one per finding, label `adversarial:claude`, `adversarial:gemini` or `adversarial:grok` |
| Every Monday | Dependabot | z3-solver and llvmlite as CI pins them (`requirements/ci.txt`), and every action every workflow uses | pull requests, which run test.yml in full, the benchmark's verdict check included |
| The 1st of each month, 03:41 UTC | `monthly.yml` | coverage-guided fuzzing for 20 minutes (`fuzz_parsers.py`, atheris); mutation testing for 90 minutes (`check_mutants.py`); the worker pool for 5,000 runs (`check_pool_soak.py`); every URL the documents name, and llms.txt (`check_urls.py`); the previous release against main over the full benchmark (`check_differential.py`); native code and the parsers under AddressSanitizer and UndefinedBehaviorSanitizer on Linux | one per failed job, label `monthly`; one per surviving mutant, label `mutation` |
| Every day, from outside | [velaris-canary](https://github.com/gowrishankar-infra/velaris-canary) | the newest release, from PyPI, npm, Docker, the Action (holding a committed `velaris.capabilities`) and the standalone executables, running `discount.vel` and refusing the network | one, in the canary repository |
| A security report | a person | SECURITY.md: reproduce, say which goal it breaks (A, B or C), fix within a week, an `advisory-*.md` for A and C (the release workflow prints the commands that draft it) | - |

Each scheduled workflow also runs by hand: Actions, the workflow, Run
workflow. The adversarial pass takes an area to attack.

## When something is red

| Red | What it means | First step |
|---|---|---|
| a `test.yml` leg | a suite failed on that system, Python or dependency set | the step's name says which suite; run it locally with the same Python. A leg without z3 that alone fails usually means a check quietly depended on the prover (ARCHITECTURE.md rule 7) |
| the 3.14 leg only | Python 3.14 behaves differently | not a release blocker; open an issue if it is Velaris's |
| `identical` | an audit or SARIF document differs between Linux, Windows and macOS | download the three `identical-*` artefacts; `check_identical.py --compare` names the file and the first differing byte |
| `lint` | mypy --strict or ruff found something | `python check_lint.py` locally, with the versions the job pins |
| `check_api.py` | the library, the command line, a door or the Action changed shape | if it is meant: `python check_api.py --update`, and an `api:` line in the CHANGELOG entry |
| `check_error_messages.py` | a message changed | if it is meant: `--update`, which never changes a code |
| `check_docs.py` | a document says something the code does not | fix the document, or run `python build_readme.py --write` for a generated count |
| the release gate | not a release, or a release it refuses | its one line says why; a refusal for a new error code, a removed flag or a changed default needs a `compatibility:` line (RELEASING.md) |
| release `perf` | pure-numeric time is more than 25% slower than the previous tag | run `python perf_gates.py --only numeric --against vX.Y.Z` on a quiet machine; a real regression is fixed, not waived |
| release `differential` | an output differs from the previous tag and the CHANGELOG entry does not name it | name it with a `differential:` line if it is meant (`check_differential.py`'s docstring), or fix it |
| a `nightly` issue | an artefact built from main does not install or does not behave - or the probe is wrong, which `check_nightly.py` exists to catch first | the issue links the job and holds its failure annotations, one per broken check (the report runs before the run ends, and gh reads no log until then); `python check_install.py` runs the same checks against any command. The next run in which every job passes closes the issue; leave the closing to it |
| a `monthly` issue | a long check failed | the issue names the job; each runs locally (below) |
| a `mutation` issue | a line a guarantee rests on can change without any suite noticing | write the test that fails with the mutant in `check_mutant_kills.py`, and check that it does with `python check_mutants.py --only MODULE:LINE:OPERATOR --killers check_mutant_kills.py` (the issue names all three); or say in that suite's docstring why the mutant is equivalent. Then close it |
| an `adversarial:*` issue | a model claims a hole | reproduce it against main first; most are not holes. A real one is a security report (SECURITY.md) |
| a canary issue | the newest release, as a user gets it, fails | the same check against main is the nightly; if main is fine, the release needs a patch |

## The kill switch: RELEASE_PAUSED

`RELEASE_PAUSED` is a variable of the `release` environment. Set to anything
but empty, `0`, `false`, `no` or `off`, the release workflow still runs the
tests, the gate and every build, and stops before the tag: nothing is
tagged or published.

    gh variable set RELEASE_PAUSED --env release --body 1     # pause
    gh variable delete RELEASE_PAUSED --env release           # resume

Use it when a release must not go out while main keeps moving: a registry
outage, a key being rotated, a report being investigated. RELEASING.md,
"Pausing releases: RELEASE_PAUSED", says how to release the commit once it
is cleared. `check_release.py` holds the switch: a paused run tags and
publishes nothing.

## The reference-runtime variable, for 9.0

`VELARIS_REFERENCE_RUNTIME` is reserved, and nothing reads it in 8.2. From
9.0 it is the repository variable that names which runtime the conformance,
differential and benchmark jobs treat as the reference when there is more
than one; its only value today would be `python`, the package in `velaris/`,
and unset means that. Until 9.0 says otherwise, do not set it, and do not
use the name for anything else.

## Secrets and variables

| Name | Kind | Used by |
|---|---|---|
| `RELEASE_PAUSED` | variable, `release` environment | release.yml, the kill switch |
| `VSCE_TOKEN` | secret | release.yml, the VS Code Marketplace (PyPI, npm and the MCP registry use OIDC, with no token stored) |
| `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `XAI_API_KEY` | secrets | adversarial-models.yml, one model each; each job skips without its key |
| `ADVERSARIAL_CLAUDE_MODEL`, `ADVERSARIAL_GEMINI_MODEL`, `ADVERSARIAL_GROK_MODEL` | variables | adversarial-models.yml; unset uses the defaults written there |
| `VELARIS_REFERENCE_RUNTIME` | variable, reserved | nothing until 9.0 (above) |

## Pins

- CI's z3-solver and llvmlite: `requirements/ci.txt`, moved by Dependabot.
  Users are not pinned; pyproject.toml keeps ranges.
- mypy and ruff: the `lint` job's install line.
- Actions: by commit in release.yml, nightly.yml, monthly.yml and
  adversarial-models.yml (the jobs that sign, publish or write issues), by
  tag in test.yml; Dependabot moves both.
- After a release, the Action pins in the README move to the new commit
  (RELEASING.md).

## Measured, and where it is kept

| What | Where | 8.2 |
|---|---|---|
| Mutation score | the monthly run's summary and `mutants.json` artefact; below | local, 25 minutes on `wrappers`: 9 of 17 mutants killed (52.9%), 30 not reached; the 8 survivors are in `strip_secret`, `currency_clash` and `carries_secret`, where `check_secret.py` and `check_money.py` do not yet reach every branch |
| Complexity | `python check_lint.py --complexity`; below | below |
| Proven share | README, generated by `build_readme.py` and held by `check_docs.py` | 70 of 99 promise-carrying functions (70.7%) |
| Model round trip | `python agent_loop.py --metric` (with a key), `--offline` in CI | offline, recorded replies: 10 of 10 compile, every one in its second round, effects as each task needs in 10 |
| Performance | the CHANGELOG entry of each release, from `perf_gates.py` | the 8.2 entry |
| ffi grants over examples/ | `velaris stats --ffi examples`, in the CHANGELOG entry | the 8.2 entry |

### The 20 most complex functions

Cyclomatic complexity as `check_lint.py --complexity` counts it (its
docstring says how). A function high on this list is where a change most
needs a test first.

| Rank | Function | Where | Complexity |
|---:|---|---|---:|
| 1 | `main` | velaris/cli.py | 268 |
| 2 | `check_types.check_fn.infer` | velaris/checker.py | 214 |
| 3 | `run_builtin` | velaris/runtime.py | 181 |
| 4 | `check_proofs.to_z3` | velaris/prover.py | 133 |
| 5 | `editor_answer` | velaris/editor.py | 65 |
| 6 | `capabilities_compare` | velaris/ratchet.py | 64 |
| 7 | `eject_main` | velaris/eject.py | 58 |
| 8 | `check_types.check_fn.check_stmt` | velaris/checker.py | 54 |
| 9 | `check_proofs` | velaris/prover.py | 51 |
| 10 | `serve_main` | velaris/doors.py | 50 |
| 11 | `_compile_native.ee` | velaris/native.py | 46 |
| 12 | `build_runtime.eval_` | velaris/runtime.py | 46 |
| 13 | `_parse_lockfile` | velaris/upgrades.py | 46 |
| 14 | `migrate_main` | velaris/migrate.py | 42 |
| 15 | `review` | velaris/ratchet.py | 42 |
| 16 | `Parser.parse_statement` | velaris/parser.py | 41 |
| 17 | `packages` | velaris/project.py | 41 |
| 18 | `serve_main.Door.route` | velaris/doors.py | 38 |
| 19 | `mcp_verify_main` | velaris/mcp_manifest.py | 38 |
| 20 | `check_proofs.infer_invariants` | velaris/prover.py | 38 |

Measured for 8.2.0. The four at the top are dispatchers - a command per
branch, a builtin per branch, a node kind per branch - where the count
measures breadth more than tangle; each new command, builtin or node adds
to them, and each has suites that name its branches. A function that climbs
this list without adding a branch of that kind is the one to look at.

`check_lint.py` also runs `mypy --strict` and `ruff check` over the package
and every script, 182 files at 8.2.0, with 0 findings. Each
`# type: ignore` in them names its code and says why; most are Windows-only
`ctypes` calls, which mypy checks as Linux.

## Running the scheduled checks locally

    python check_install.py --name local --command "python velaris.py"
    python fuzz_parsers.py --minutes 20
    python check_mutants.py --minutes 30 --modules budget
    python check_mutants.py --only budget:428:return-none --killers check_mutant_kills.py
    python check_pool_soak.py --runs 5000
    python check_urls.py
    python check_differential.py --spec ../velaris-spec/tests
    python perf_gates.py --against v8.2.1 --markdown
    python adversarial_models.py prompt --focus budget
    python agent_loop.py --metric --offline

None of them writes into the repository.
