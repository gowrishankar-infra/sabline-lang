# Releasing Velaris

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

1. Put the new version in all six version files: `velaris.py`
   (`VERSION`), `pyproject.toml`, `npm/package.json`,
   `mcpb/manifest.json`, `editor/vscode/package.json` and
   `integrations/mcp_registry/server.json` (three times: its own, and
   the PyPI and npm packages'). `python run_tests.py` holds all of them to
   one version. Leave the Action pins in README.md and EMBEDDING.md where
   they are: they name a commit, which the release commit cannot name for
   itself, so they stay on the previous release until it is tagged (below).
2. Write the CHANGELOG entry, headed `## X.Y.Z - Title`. An X.Y.0
   release may be headed `## X.Y - Title`, as minor releases always
   have been here; `## X.Y` never stands for X.Y.1.
3. Ask the gate what it will decide: `python release_checks.py gate`
   should say `release: X.Y.Z`.
4. Commit and push to main.

GitHub does the rest:

5. `tests` (test.yml) runs its twelve legs on that commit.
6. When it completes with every leg passed, `release` starts. Nothing
   else starts it.
7. **The gate.** It runs `check_release.py`, which holds the gate's own
   logic to fixtures, and then `release_checks.py gate`. The commit is
   a release only when
   - `VERSION` in velaris.py is newer than the newest `v*` tag,
   - CHANGELOG.md has an entry heading for exactly that version, and
   - all six version files agree with it, and the registry manifest
     lists both the PyPI and the npm package.

   Otherwise the run prints one line saying what is missing - `no
   release: CHANGELOG.md has no entry heading for 7.2.1 ...` - and ends
   green having done nothing. That is what every push that is not a
   release looks like.
8. **Only the commit the tests passed on.** A `workflow_run` runs
   against the tip of main, which may have moved while the tests ran.
   If the tip is not the commit whose tests started the run, the gate
   refuses and that run fails; the newer commit's own tests decide
   whether it is the release.
9. **Build, sign, verify.** The wheel and the sdist (the wheel built
   twice and compared), the SBOM, the MCP tool manifest (checked
   against the wheel's own server), the `.mcpb` bundle, the three
   executables, the attestation of `examples/effects.vel` and, from 8.1,
   the receipt of one run of it are built and signed with sigstore. Nothing is published yet, and if any of it
   fails nothing is tagged: fix it and push again with the same version.
10. **Tag.** The commit is tagged `vX.Y.Z`, annotated - not signed; see
    below.
11. **Publish, in this order.** Each step first asks whether the version
    is already there, and skips with a notice if it is.
    1. PyPI, by trusted publishing (OIDC; no token is stored).
    2. npm, from `npm/`, by trusted publishing (OIDC; npm adds
       provenance by itself).
    3. The VS Code Marketplace, with the `VSCE_TOKEN` secret, as before.
       A Marketplace outage is reported in the summary and does not hold
       up the rest.
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
12. **Consistency.** PyPI, npm, the MCP registry and the GitHub release
    must all report this version, and the release must hold all 27
    files (24 before 8.1.0, which added the receipt). The indexes cache, so it keeps asking for fifteen minutes;
    then it fails and names what differs.
13. **Advisory.** If a commit since the previous tag adds an
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
It is scoped to publishing this extension and nothing else, its job
runs `continue-on-error` so a Marketplace outage never holds up a
release, and it is the credential to audit first. When the Marketplace
offers OIDC publishing, this secret should go the way the PyPI and npm
tokens already have.

**A dry run.** Run `release` by hand on any branch (`gh workflow run
release.yml --ref <branch>`). The gate says what it would decide, and
everything is built, signed under that branch's identity and verified.
Nothing is tagged or published.

## After the release: move the Action pins

README.md and EMBEDDING.md show the Action pinned by commit, with the tag in
a comment beside it (`@<commit>  # vX.Y.Z`), and `run_tests.py` fails unless
that commit is the one the newest `v*` tag names. So once the workflow has
tagged a release, the next push to main must move the pins:

    git fetch --tags
    git rev-parse "vX.Y.Z^{commit}"

Put that commit and `# vX.Y.Z` in both files, and the `version:` example
with it. That push is not a release - its version is already tagged - and
its tests are what hold the pins to the tag.

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
shows how to check both, and `velaris mcp-verify` expects the main
identity for 7.2.0 and later.

## When a step fails

Read its log and fix the cause. Then re-run the failed jobs of that same
run: **Re-run failed jobs** on its page, or `gh run rerun <run-id>
--failed`. A re-run uses the same commit, and every publish step skips
what already landed, so it continues where it stopped. Re-running the
whole workflow does nothing, because its gate sees the tag the first
attempt made.

**Never finish a publish by hand with a token.** Trusted publishing
means no long-lived publish token exists; making one to get past a
failure brings it back.

If the fix needs a change to the repository after the tag was made,
that version is spent: bump to the next one, add its CHANGELOG entry and
push. Do not delete or move a tag that has published anything.

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
    gh api --method POST "repos/gowrishankar-infra/velaris-lang/security-advisories/$(gh api --method POST repos/gowrishankar-infra/velaris-lang/security-advisories --input advisory-<name>.json --jq .ghsa_id)/cve"

Both lines work in bash and in PowerShell. The inner POST creates a
**draft** advisory; the outer one requests a CVE for it, which GitHub
reviews. Nothing is public until you read the draft under Security,
Advisories, and publish it yourself. Nothing automated ever publishes an
advisory.

Write the file as [advisory-proof-cache.md](advisory-proof-cache.md) is
written: a `# ` title (the summary; a leading "Security advisory:" is
dropped), the description from its first `## ` section on, a `##
Affected versions` section that says `A through B` and `Fixed in C`
(the package is `velaris-lang` on pip), and, if there are any, a CVSS
vector string and a `## CWE` section naming CWE ids.
`python release_checks.py advisory-body` refuses a file that lacks what
it needs, and says what.

### Yank a release

A published version is never deleted or re-published; it is marked, and
a fixed version follows by the normal path.

- **PyPI:** at https://pypi.org/manage/project/velaris-lang/releases/,
  **Options** beside the release, then **Yank**. PyPI offers this on the
  web only.
- **npm:** `npm deprecate velaris-lang@X.Y.Z "<what is wrong, and which
  version to use>"`, as the package owner. An empty message, `""`,
  lifts it.
- **The MCP registry:** `mcp-publisher login github`, then
  `mcp-publisher status --status deprecated
  io.github.gowrishankar-infra/velaris X.Y.Z`.
- **The GitHub release:** edit its notes to say it is yanked and which
  version replaces it. Leave the tag and the files where they are.
- **The VS Code Marketplace:** publish the fixed version.
