# Security policy

Velaris takes "you can trust code you didn't write" seriously - that
includes trusting the compiler itself. [THREAT_MODEL.md](THREAT_MODEL.md)
says what is and is not defended against; this file says how to
report, what is promised in return, and how to check that what you
downloaded is what was released.

## Reporting a vulnerability

Please do NOT open a public issue for security problems. Instead, use
GitHub's private reporting: **Security tab -> Report a vulnerability**
on this repository. **You will get a response within 48 hours** - an
acknowledgement that the report arrived and is being looked at, not
necessarily a fix. This is a single-maintainer project (SUPPORT.md); the
48-hour promise is for the first reply, and a fix to a soundness or
sandbox report is promised within a week (below).

In scope: anything that makes Velaris's guarantees lie - an effect the
checker misses, a "proven" promise that can actually break at runtime,
a way past `--allow`, a sandbox escape through the playground, or
unsafe behavior in `fetch` / `read_file` / `write_file`. From 3.4 also:
a way into the HTTP door without its token, a way past either door's
`--max-allow`, the token appearing in a log, an error message, a
process argument or a program's environment, and a changed MCP tool
description that `velaris mcp-verify` passes. From 4.0 also: a run
through either door that gets more time or memory than its operator's
`--max-timeout` or `--max-memory-mb`, and a change to a repository's
code that needs more than its `velaris.capabilities` declares while
`velaris capabilities check` passes it.

## The three guarantees, and which findings get a CVE

Velaris makes three promises a person relies on to run code they have
not read. A report that breaks one is a security report.

- **Goal A - Soundness.** A promise Velaris reports "proven" never
  breaks at run time. If `check`, `proofs`, `explain`, `audit` or the
  library marks a `requires`/`ensures`/`invariant` proven and a run then
  violates it, Goal A is broken.
- **Goal B - Honesty.** A program's declared effects, and the audit
  built from them, name everything it can do to the outside world - the
  transitive effect rule (SPEC.md 7). If a program performs an effect no
  signature on its call graph declares, Goal B is broken.
- **Goal C - Confinement.** No effect outside the operator's budget
  happens, whatever the source claims. If a program reads a file,
  reaches a host, reads the environment, calls Python or otherwise acts
  outside `--allow` and carries on, Goal C is broken.

**A finding against Goal A or Goal C gets a CVE requested.** Those are
the two guarantees a person leans on when they run unread code: that a
proof is not a lie, and that the budget holds. A report that establishes
one is treated as a security issue, fixed within a week, credited by
name, and a repository security advisory with a CVE is drafted for it
(RELEASING.md says how the release workflow prepares the request).

Goal B findings are fixed too, but the audit is documented as reading a
program's *text*, not running it (THREAT_MODEL.md): it describes what a
program declares, and the budget - Goal C - is the boundary that holds
regardless. A Goal B finding that also lets a program escape its budget
is a Goal C finding, and gets the CVE.

What is **not** a Goal A/B/C finding is anything the "Known open" table
in THREAT_MODEL.md lists as a stated limit - a granted `ffi` module's
behaviour, native code inside one, a timing channel, a secret arriving
outside the two builtins, the absence of OS confinement. Those are
documented as not defended; a report of one is welcome as a
documentation or hardening issue, not a broken guarantee.

## Soundness reports are security reports

If the prover claims something is proven and you can make it false at
runtime, that is a vulnerability in this language's core promise (Goal
A above). These reports get top priority.

## Standing challenge

Anyone who does either of these is credited by name in
[CHANGELOG.md](CHANGELOG.md) and in [HALL_OF_FAME.md](HALL_OF_FAME.md),
and the report is treated as a security issue and fixed within a week:

1. **Make Velaris report "proven"** (in `velaris check`, `velaris
   proofs`, `velaris explain`, `velaris audit` or the library) **for a
   promise that is false at runtime.** A `requires`, `ensures` or
   `invariant` that the compiler marks proven and that a run under
   `--no-native` or with native code then violates, or a division or
   list read the compiler passed that then fails with E403 or E602
   without a runtime-check warning having been issued.

2. **Escape `io`.** A program run with `velaris program.vel` (which
   grants `io` and nothing else from 5.0), with `--allow io`, or with
   `velaris.run(source, allow={"io"})` or `allow=None`, that reads or
   writes a file, reaches the network, reads the environment, or calls
   a Python module - including one outside a named `ffi:` list - and
   carries on. `args()` and `read_line()` do not count: `io` is the
   console, and THREAT_MODEL.md says so. Since 3.0 `env` is its own
   effect, so `env()` under `io` alone is a refusal like the rest.

There is no money. There is credit, in the file every reader sees, and
a fix within the week, recorded in the changelog with what was found
and what was wrong. Report through the private channel above so the
fix ships before the details do; the credit is public either way.

## Resolved advisories

- **Proof cache poisoning** (challenge #1), affecting 2.29 through 7.1.1,
  fixed in 7.1.2: a `./.velaris/proofs.json` shipped with an untrusted
  program could make a false `ensures` report "proven" and go unenforced
  at run time. The proof cache now lives only in a per-user directory and
  a project-local `./.velaris/` is ignored. See
  [advisory-proof-cache.md](advisory-proof-cache.md) and THREAT_MODEL.md.

What is not in scope of the challenge, because it is documented as not
defended: anything a granted `ffi` module does, resource use below a
limit, the meaning of printed text, the memory cap on macOS (where
RLIMIT_AS is best-effort; it is enforced on Linux and, since 3.1, on
Windows through a job object), and programs not written in Velaris.

## Verifying a download

Every artifact of a release from v2.63 onward is signed keylessly
through sigstore by the release workflow itself, so the signature
proves the file was built by `.github/workflows/release.yml` in this
repository. Which run of it the certificate names changed at 7.2.0:

- **Up to 7.1.2** pushing a tag started a release, and the identity is
  the tag's. For a release `vX.Y`:

      https://github.com/gowrishankar-infra/velaris-lang/.github/workflows/release.yml@refs/tags/vX.Y

- **From 7.2.0** no tag starts a release. The workflow runs on main
  once the tests pass there, tags the commit itself and signs in that
  same run ([RELEASING.md](RELEASING.md)), so the identity names main:

      https://github.com/gowrishankar-infra/velaris-lang/.github/workflows/release.yml@refs/heads/main

  That identity says "the release workflow, on main", not which
  release. The certificate also records the commit the run was on and
  the event that started it; checking both ties a file to the tagged
  commit and to a real release (a release is started only by
  `workflow_run`; a dry run by hand is `workflow_dispatch`):

      sigstore verify github \
        --bundle velaris_lang-7.2.0-py3-none-any.whl.sigstore.json \
        --cert-identity https://github.com/gowrishankar-infra/velaris-lang/.github/workflows/release.yml@refs/heads/main \
        --trigger workflow_run \
        --sha "$(git rev-parse 'v7.2.0^{commit}')" \
        velaris_lang-7.2.0-py3-none-any.whl

  With cosign, add `--certificate-github-workflow-trigger workflow_run`
  and `--certificate-github-workflow-sha <that commit>`.

The OIDC issuer is `https://token.actions.githubusercontent.com` either
way. The commands below name older releases; for 7.2.0 and later give
the main identity instead, with the trigger and the commit.

**The wheel and the sdist** carry a sigstore bundle
(`<file>.sigstore.json`, holding the signature and the certificate
together). With `pip install sigstore`:

    sigstore verify identity \
      --bundle velaris_lang-2.63.0-py3-none-any.whl.sigstore.json \
      --cert-identity https://github.com/gowrishankar-infra/velaris-lang/.github/workflows/release.yml@refs/tags/v2.63 \
      --cert-oidc-issuer https://token.actions.githubusercontent.com \
      velaris_lang-2.63.0-py3-none-any.whl

**The three executables and `velaris.mcpb`** carry a detached
signature (`.sig`), the certificate (`.pem`) and the same bundle
(`.sigstore.json`). With [cosign](https://github.com/sigstore/cosign):

    cosign verify-blob velaris-linux \
      --bundle velaris-linux.sigstore.json \
      --certificate-identity https://github.com/gowrishankar-infra/velaris-lang/.github/workflows/release.yml@refs/tags/v2.63 \
      --certificate-oidc-issuer https://token.actions.githubusercontent.com

or, with the detached files:

    cosign verify-blob velaris-linux \
      --signature velaris-linux.sig \
      --certificate velaris-linux.pem \
      --certificate-identity https://github.com/gowrishankar-infra/velaris-lang/.github/workflows/release.yml@refs/tags/v2.63 \
      --certificate-oidc-issuer https://token.actions.githubusercontent.com

**The MCP tool manifest** (from 3.4). `velaris-mcp-tools-X.Y.Z.json`
lists every tool the MCP server in the wheel offers, with the sha256 of
its description and of its input schema, and is signed like the wheel
(`velaris-mcp-tools-X.Y.Z.json.sigstore.json`). `velaris mcp-verify`
checks that signature against the identity above and then the server
your MCP client runs against the manifest, and names every tool whose
description or schema differs:

    pip install sigstore
    velaris mcp-verify velaris-mcp-tools-3.4.0.json -- python -m velaris_mcp

EMBEDDING.md says what it does and does not tell you. The signature can
also be checked on its own with the `sigstore verify identity` command
above, naming the manifest and its bundle.

**An attestation of one example program** (from 4.2).
`velaris-attestation-X.Y.Z.intoto.json` is the in-toto Statement
`velaris attest examples/effects.vel` writes at the tagged commit, and
the release workflow signs it twice as a DSSE envelope, keylessly: with
cosign (`velaris-attestation-X.Y.Z.cosign.sigstore.json`) and with
sigstore-python (`velaris-attestation-X.Y.Z.sigstore-python.sigstore.json`),
verifying both before it attaches them. With `examples/effects.vel`
from the tagged source:

    cosign verify-blob-attestation \
      --bundle velaris-attestation-4.2.0.cosign.sigstore.json \
      --type https://gowrishankar-infra.github.io/velaris-lang/capability/v1 \
      --certificate-identity https://github.com/gowrishankar-infra/velaris-lang/.github/workflows/release.yml@refs/tags/v4.2.0 \
      --certificate-oidc-issuer https://token.actions.githubusercontent.com \
      examples/effects.vel

It fails when the file is not the one the Statement names, by digest.
What the Statement says, and what it does not, is in EMBEDDING.md.

**Checksums.** `SHA256SUMS` (for the wheel, sdist, SBOM and tool manifest) and
`<asset>.sha256` (for each binary and the bundle) are attached too;
`sha256sum -c` checks them. A checksum proves the file is intact, not
who built it - the signature does that.

**The SBOM.** `velaris-lang-X.Y.Z.cdx.json` is a CycloneDX bill of
materials of an environment holding the wheel and its optional
dependencies (`z3-solver`, `llvmlite`), signed like the wheel. Velaris
itself has no required dependencies.

**Reproducibility.** The release workflow builds the wheel twice with
the same `SOURCE_DATE_EPOCH` and fails if the two differ. To check on
your own machine at the tagged commit:

    SOURCE_DATE_EPOCH=$(git log -1 --format=%ct) python -m build --wheel
    sha256sum dist/*.whl          # compare with SHA256SUMS on the release

**What verification does not tell you:** that the code is correct, or
that the version you verified is the one your agent framework will
import. Pin the version, and run the suites named in THREAT_MODEL.md on
the machine that will run untrusted code.
