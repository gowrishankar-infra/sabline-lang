# Releasing Sabline

**Nobody tags a release by hand** - not a maintainer, not an agent, not
to help one along. A release is made by
[`.github/workflows/release.yml`](.github/workflows/release.yml) after
the tests pass on main, and by nothing else. A tag pushed by hand
publishes nothing, because no workflow listens for tags. It does block
the real release of that version, because the gate refuses a version
that is already tagged. If one is pushed by mistake, delete it
(`git push origin :refs/tags/vX.Y.Z`) before that commit's tests finish.

## Making a release

Everything a person does happens before the push:

1. Put the new version in all six version files: `sabline/version.py`
   (`VERSION`; it was `sabline.py` until 8.2), `pyproject.toml`,
   `npm/package.json`, `mcpb/manifest.json`, `editor/vscode/package.json`
   and `integrations/mcp_registry/server.json` (three times: its own, and
   the PyPI and npm packages'). `python run_tests.py` holds all of them to
   one version. Leave the Action pins in README.md and EMBEDDING.md where
   they are: they name a commit, which the release commit cannot name for
   itself, so they stay on the previous release until it is tagged (below).
2. Write the CHANGELOG entry, headed `## X.Y.Z - Title`. An X.Y.0
   release may be headed `## X.Y - Title`, as minor releases always
   have been here; `## X.Y` never stands for X.Y.1. Two kinds of line in
   it are read by the gate (below): a line beginning `compatibility:`,
   and a line beginning `api:`.
3. Ask the gate what it will decide: `python release_checks.py gate`
   should say `release: X.Y.Z`. `python release_checks.py covered vA.B.C`
   lists what the release changes that a minor or patch release must
   explain, against the previous tag.
4. Commit and push to main.

GitHub does the rest:

5. `tests` (test.yml) runs its eighteen legs on that commit, and the job
   that runs suites twice at once.
6. When it completes with every leg passed, `release` starts. Nothing
   else starts it. (The legs on Python 3.14 may fail without failing the
   run; they are reported, not required.)
7. **The gate.** It runs `check_release.py`, which holds the gate's own
   logic to fixtures, and then `release_checks.py gate`. The commit is
   a release only when
   - `VERSION` is newer than the newest `v*` tag,
   - CHANGELOG.md has an entry heading for exactly that version, and
   - all six version files agree with it, and the registry manifest
     lists both the PyPI and the npm package.

   Otherwise the run prints one line saying what is missing - `no
   release: CHANGELOG.md has no entry heading for 7.2.1 ...` - and ends
   green having done nothing. That is what every push that is not a
   release looks like.

   Two more conditions refuse a release - exit 1, red, and one line naming
   what is wrong (8.2):
   - **A minor or patch release that changes what STABILITY.md covers
     without saying why that is not a break.** Against the previous tag,
     the gate reads the compiler's source, every module of the package:
     - an error code added - any text in the source that is one code, so
       a code added to `ERROR_TABLE` by a subscript, by `update()` or in
       another module counts as one in the literal table does;
     - a `--flag` the command line or the MCP server no longer knows;
     - a default that is not what it was: a module-level constant named
       `DEFAULT_*` or `*_DEFAULT`, the few in `KNOWN_DEFAULTS`, every
       variable of the run state (`sabline/state.py`, `EFFECT_BUDGET`
       among them), and each parameter default of the library STABILITY.md
       covers, read through any constant it names; and a parameter that
       loses its default.

     If it finds one, the entry must hold a line beginning
     `compatibility:` that explains why the change does not break a user
     of the previous version - `compatibility: E615 is given only to a
     program that stopped with a Python error in 8.1`. The line is prose:
     at the start of a line, with at least four words after the colon,
     not in a code block or an HTML comment, and not a placeholder such as
     TODO. A major release needs no such line: it is where a break may be.
     What the gate does not see: a default computed in a function body,
     and a code built from pieces while running.
   - **An API golden that moved without an `api:` line.** When
     `tests/api/golden.json` (check_api.py) differs from the previous
     tag's, the entry must hold a line beginning `api:`, read as the
     `compatibility:` line is, saying what changed. Every release, major
     included.

   A commit whose sources the gate cannot read - a module that is not
   UTF-8, one that does not parse - is refused in one line, and a VERSION
   that is not `X.Y.Z` writes no step output.
8. **Only the commit the tests passed on.** A `workflow_run` runs
   against the tip of main, which may have moved while the tests ran.
   If the tip is not the commit whose tests started the run, the gate
   refuses and that run fails; the newer commit's own tests decide
   whether it is the release.
9. **Build, sign, verify.** The wheel and the sdist (the wheel built
   twice and compared), the SBOM, the MCP tool manifest (checked
   against the wheel's own server), the `.mcpb` bundle, the three
   executables, the attestation of `examples/effects.vel` and, from 8.1,
   the receipt of one run of it are built and signed with sigstore. Beside
   them, from 8.2, this commit is held to the previous tag twice: its
   pure-numeric time (`perf`; Performance, below) and every output that
   differs from the previous release's (`differential`; Differences from
   the previous release, below). Nothing is published yet, and if any of
   it fails nothing is tagged: fix it and push again with the same
   version.
10. **Paused?** If the `release` environment's variable `RELEASE_PAUSED`
    is set (below), the run says so and stops here.
11. **Tag.** The commit is tagged `vX.Y.Z`, annotated - not signed; see
    below.
12. **Publish, in this order.** Each step first asks whether the version
    is already there, and skips with a notice if it is.
    1. PyPI, by trusted publishing (OIDC; no token is stored).
    2. npm, from `npm/`, by trusted publishing (OIDC; npm adds
       provenance by itself).
    3. The VS Code Marketplace, with the `VSCE_TOKEN` secret. A timeout
       is tried again up to five times, 30 s, 60 s, 120 s, 240 s and 480 s
       apart; then the job asks the Marketplace, for up to fifteen
       minutes, whether it lists the version, and fails if it does not
       (8.2.1; until then the job ended green after three timeouts). The
       steps after it run either way. Re-run the failed jobs once the
       Marketplace answers.
    4. The GitHub release, with the CHANGELOG entry as its notes and
       every file: the wheel, the sdist, the SBOM, the MCP tool manifest,
       the `.mcpb` bundle and the three executables, each with its
       signature, and the checksums.
    5. The MCP registry, logged in by GitHub OIDC, from
       `integrations/mcp_registry/server.json` listing both the PyPI and
       the npm package. It first waits until PyPI and npm serve this
       version naming the server, because the registry checks exactly
       that.
    6. The attestation and the receipt, attached to the release.

    A step that fails stops the ones after it (the Marketplace aside).
13. **Consistency.** PyPI, npm, the MCP registry, the GitHub release and
    the VS Code Marketplace must all report this version as their latest,
    and the release must hold all 27 files (24 before 8.1.0, which added
    the receipt). The indexes cache, so it keeps asking for fifteen
    minutes; then it fails and names what differs. The Marketplace was
    added after 8.2.1: until then a release whose extension never
    published passed here. A Marketplace outage that outlasts the vscode
    job therefore fails this job too; re-run the failed jobs once the
    extension is listed.
14. **Advisory.** If a commit since the previous tag adds an
    `advisory-*.md`, see below.

The environment `release` holds no secrets. PyPI, npm and the MCP
registry take a short-lived OIDC token from the run; the trusted
publishers on PyPI and npm name this repository, the workflow file
`release.yml` and the environment `release`, so renaming either breaks
publishing. The one stored credential a release uses is `VSCE_TOKEN`.

**`VSCE_TOKEN` is the one remaining long-lived secret, and it is here
because the VS Code Marketplace has no OIDC trusted publishing.** PyPI,
npm and the MCP registry all take a short-lived token minted for the run
from the workflow's GitHub identity, so no publish credential for them
is stored anywhere and none can leak from the repository. The
Marketplace has no equivalent: `vsce publish` needs a personal access
token, which must be stored as a repository secret and rotated by hand.
It is scoped to publishing this extension and nothing else, a
Marketplace outage never holds up the rest of a release (its job fails,
and the jobs after it run), and it is the credential to audit first. When the Marketplace
offers OIDC publishing, this secret should go the way the PyPI and npm
tokens already have.

**A dry run.** Run `release` by hand on any branch (`gh workflow run
release.yml --ref <branch>`). The gate says what it would decide, and
everything is built, signed under that branch's identity and verified.
Nothing is tagged or published.

## Pausing releases: RELEASE_PAUSED

`RELEASE_PAUSED` is a variable of the `release` environment (Settings,
Environments, `release`, Environment variables). Set to anything but
empty, `0`, `false`, `no` or `off` - an unclear value pauses rather than
publishes - the `paused` job says so in the run's summary, and the tag
and every publish after it are skipped. The tests still run on every
push, and the build, sign and verify jobs still run on a release commit,
so a paused release is a checked one.

Use it when something outside this repository makes publishing wrong for
a while: a registry is known to be misbehaving, a credential is being
rotated, an advisory is being coordinated with a reporter.

To release a commit that was pushed while paused: clear the variable, open
that commit's `release` run, and **re-run all jobs**. The gate decides
again - the version is not tagged yet - and the release proceeds. Re-running
only failed jobs does not, because a paused run has none.

`check_release.py` holds this to the workflow: the `paused` job reads the
environment's variable, the tag needs it and runs only when it says not
paused, every job that publishes comes after the tag, and no build job
waits on it.

## After the release: the workflow moves the Action pins

README.md and EMBEDDING.md show the Action pinned by commit, with the tag in
a comment beside it (`@<commit>  # vX.Y.Z`), and `run_tests.py` fails unless
that commit is the one the newest `v*` tag names. A release commit cannot
name its own hash, so from the moment the tag exists main's first test step
fails until the pins name it. Until 8.4 a person made that commit, and main
was red until they did - twenty of twenty-one jobs, after 8.3.1.

From 8.4 the run that made the tag makes the commit. The `move_pins` job
runs once the tag exists, whatever the publishes after it did. It checks out
main, runs `python3 release_checks.py move-pins vX.Y.Z --commit <sha>` - the
pins in both files, the `version:` example beside them, the pre-commit
`rev:` - rebuilds the pages with `build_docs.py`, and commits exactly that:
it fails if anything outside README.md, EMBEDDING.md and docs/ changed. The
message is `Move the Action pins to vX.Y.Z`. Before pushing it asks the gate
about the new commit, and pushes only when the gate says it is not a release
(its version is already tagged). If main moved meanwhile, it does it again
on top of the new tip, up to five times. A push made with GITHUB_TOKEN starts
no workflow, so the job then starts `tests` on main by name
(`workflow_dispatch`); the `release` run that follows those tests is skipped
at its gate, which takes only a push's tests.

Run again - a re-run of failed jobs reaches it - it finds the pins already
moved and pushes nothing. `check_release.py` runs the job's own steps in
bash on a throwaway copy of this repository with a simulated tag, and holds
the result to be that one commit and nothing else: five lines in the two
documents, pages under docs/, no tag made or moved, the tests started once.

If the job fails, move the pins by hand, the same way:

    git fetch --tags
    python release_checks.py move-pins vX.Y.Z --commit "$(git rev-parse 'vX.Y.Z^{commit}')"
    python build_docs.py

## Why the tag is not signed

This repository has no tag-signing setup: no earlier tag is signed. A
signature made in Actions would need either a key stored in the
repository - the long-lived credential this workflow exists to avoid -
or gitsign's keyless signature, which GitHub does not show as verified.
So the tag is annotated, and the release notes say it is not signed.
What is signed is every file the release publishes.

From 7.2.0 those signatures name `release.yml@refs/heads/main`, not the
tag, because a `workflow_run` runs on main. The certificate also names
the commit and the `workflow_run` trigger; [SECURITY.md](SECURITY.md)
shows how to check both, and `sabline mcp-verify` expects the main
identity for 7.2.0 and later.

## When a step fails

Read its log and fix the cause. Then re-run the failed jobs of that same
run: **Re-run failed jobs** on its page, or `gh run rerun <run-id>
--failed`. A re-run uses the same commit, and every publish step skips
what already landed, so it continues where it stopped. Re-running the
whole workflow does nothing, because its gate sees the tag the first
attempt made.

`check_release.py` holds this to release.yml itself (8.2): it runs the
jobs from the tag on against a stand-in for PyPI, npm, the Marketplace,
GitHub and the MCP registry, makes one publish fail - npm, the
Marketplace, the registry, the GitHub release - re-runs the failed jobs
and the jobs after them, as GitHub does, and checks that every publish
was made exactly once, none was skipped, and the consistency check
passes; and that a whole second run publishes nothing again. From 8.2.1
it also runs the Marketplace job's own steps in bash, with stand-ins for
`vsce`, `npm` and `sleep`: a timeout on every attempt, timeouts that
clear, a version listed after a timeout, a refused token, no token, and
a version already listed. The job must be red whenever the Marketplace
does not list the version at its end.

**Never finish a publish by hand with a token.** Trusted publishing
means no long-lived publish token exists; making one to get past a
failure brings it back.

If the fix needs a change to the repository after the tag was made,
that version is spent: bump to the next one, add its CHANGELOG entry and
push. Do not delete or move a tag that has published anything.

## Performance

Every release's CHANGELOG entry carries the numbers `perf_gates.py`
measures on the machine the release was built on (MAINTENANCE.md says
which): the cold start of `sabline --version` and of `sabline check` on a
one-line file, a check per 1,000 lines, proof time p50 and p95 over the
examples, the native compiler's compile time against what it saves on
`examples/bench.vel`, and a pool's memory after 1,000 runs. The release
workflow runs `perf_gates.py --against <previous tag>` before tagging and
fails the release if the pure-numeric benchmark is more than 25% slower
than the previous tag on the same runner.

## Differences from the previous release

Before tagging, the `differential` job runs `check_differential.py`: the
examples, sabline-spec's conformance corpus and the quick benchmark, each
run under this commit and under the previous tag, compared once what is not
output (paths, the version string, timings) is taken out. A difference the
CHANGELOG entry does not name stops the release. Name one on a line of the
entry beginning `differential:`, in the form the script's docstring gives.
The monthly workflow runs the same comparison over every benchmark program.

## What a person still does

### Publish a security advisory

When a release adds `advisory-<name>.md` - anywhere in the tree, in any
commit since the previous tag - the `advisory` job prints a warning and
two commands, and keeps the request body as the `advisory-requests`
artifact. It cannot run them: creating a repository security advisory
and requesting its CVE need the "Repository security advisories"
permission, and GITHUB_TOKEN cannot be given it. From a checkout of the
release, logged in to gh as an administrator or security manager of the
repository:

    python release_checks.py advisory-body advisory-<name>.md -o advisory-<name>.json
    gh api --method POST "repos/gowrishankar-infra/sabline-lang/security-advisories/$(gh api --method POST repos/gowrishankar-infra/sabline-lang/security-advisories --input advisory-<name>.json --jq .ghsa_id)/cve"

Both lines work in bash and in PowerShell. The inner POST creates a
**draft** advisory; the outer one requests a CVE for it, which GitHub
reviews. Nothing is public until you read the draft under Security,
Advisories, and publish it yourself. Nothing automated ever publishes an
advisory.

Write the file as [advisory-proof-cache.md](advisory-proof-cache.md) is
written: a `# ` title (the summary; a leading "Security advisory:" is
dropped), the description from its first `## ` section on, a `##
Affected versions` section that says `A through B` and `Fixed in C`
(the package is `sabline-lang` on pip), and, if there are any, a CVSS
vector string and a `## CWE` section naming CWE ids.
`python release_checks.py advisory-body` refuses a file that lacks what
it needs, and says what.

### Yank a release

A published version is never deleted or re-published; it is marked, and
a fixed version follows by the normal path.

- **PyPI:** at https://pypi.org/manage/project/sabline-lang/releases/,
  **Options** beside the release, then **Yank**. PyPI offers this on the
  web only.
- **npm:** `npm deprecate sabline-lang@X.Y.Z "<what is wrong, and which
  version to use>"`, as the package owner. An empty message, `""`,
  lifts it.
- **The MCP registry:** `mcp-publisher login github`, then
  `mcp-publisher status --status deprecated
  io.github.gowrishankar-infra/sabline X.Y.Z`.
- **The GitHub release:** edit its notes to say it is yanked and which
  version replaces it. Leave the tag and the files where they are.
- **The VS Code Marketplace:** publish the fixed version.
