# Velaris is now Sabline

This project was called **Velaris** from 1.0 to 8.5.0. From **8.6.0** it is
called **Sabline**.

## Why

The name belongs to an unrelated company in the same market — velaris.io,
which sells an agent product with an MCP server. Two things with one name in
one market is a problem for whoever meets the second one, and the company
was there first and is funded. The name was given up rather than contested.

Nothing about the language, the format, the guarantees or the threat model
changed with the name. 8.6.0 renames and nothing else.

## What you have to change: nothing, in 8.x

The rename is additive. STABILITY.md's rule 1 says a break ships only in a
major version, and a rename that stopped a command, an import or a
committed file from working would be a break. So every old name still
works, each saying once on stderr that it has changed, and each goes no
sooner than 9.0.

| What you wrote | Still works in 8.x | Write instead |
|---|---|---|
| `velaris program.vel` | yes, with a notice | `sabline program.vel` |
| `npx velaris ...` | yes, with a notice | `npx sabline ...` |
| `import velaris` | yes, with a notice and a `DeprecationWarning` | `import sabline` |
| `from velaris.budget import Budget` | yes | `from sabline.budget import ...` |
| `except velaris.VelarisError` | yes — it is `SablineError` under the old name | `except sabline.SablineError` |
| `python -m velaris_mcp` | yes, with a notice | `python -m sabline_mcp` |
| `%load_ext velaris_magic` | yes, with a notice | `%load_ext sabline_magic` |
| `VELARIS_TOKEN`, `VELARIS_PROOF_TIMEOUT`, any `VELARIS_*` | yes, when the `SABLINE_*` name is not set | `SABLINE_*` |
| a committed `velaris.capabilities` | yes, read when there is no `sabline.capabilities` beside it | rename the file |
| `velaris.toml`, `velaris.lock` | yes, same rule | rename them |
| a `velaris.audit/1` / `velaris.receipt/1` / `velaris.capabilities/1` document | yes, read as the `sabline.*` format of the same version | nothing; Sabline writes `sabline.*` from 8.6 |
| a Statement of the `velaris-lang.dev` or GitHub Pages predicate type | yes, verified as the same type | nothing; new Statements name `sabline.dev` |

Two names for one thing, set to different values, is an error rather than a
guess: `SABLINE_TOKEN=a VELARIS_TOKEN=b` stops and says so, because a guess
there decides what a run is allowed to do.

`sabline` and `velaris` are the same command, `sabline` and `velaris` are
the same Python module object, and `SablineError` and `VelarisError` are the
same class — not copies, so nothing can drift apart.

## Every published address, and where it now points

### The packages

| Was | Is | What happens to the old one |
|---|---|---|
| PyPI `velaris-lang` | PyPI [`sabline-lang`](https://pypi.org/project/sabline-lang/) | a final release that depends on `sabline-lang` and prints the rename notice; earlier versions stay exactly where they are |
| npm `velaris-lang` | npm [`sabline-lang`](https://www.npmjs.com/package/sabline-lang) | the same, and marked deprecated with `npm deprecate` |
| PyPI/npm `velaris` (the bare name, a placeholder) | PyPI/npm `sabline` | kept, pointing at `sabline-lang` |
| MCP registry `io.github.gowrishankar-infra/velaris` | `io.github.gowrishankar-infra/sabline` | the old server keeps its published versions and is marked deprecated |
| VS Code `gowrishankar-infra.velaris` | [`gowrishankar-infra.sabline`](https://marketplace.visualstudio.com/items?itemName=gowrishankar-infra.sabline) | a Marketplace extension id cannot be renamed, so the old one gets a final version whose README says to install Sabline |

Nothing published under the old name is deleted, yanked or moved. A pin to
`velaris-lang==8.5.0` resolves to the same file it always did, with the same
digest and the same signature — that is the rule this project has kept since
3.4 and is not breaking now.

### The repositories

| Was | Is |
|---|---|
| `gowrishankar-infra/velaris-lang` | [`gowrishankar-infra/sabline-lang`](https://github.com/gowrishankar-infra/sabline-lang) |
| `gowrishankar-infra/velaris-spec` | [`gowrishankar-infra/sabline-spec`](https://github.com/gowrishankar-infra/sabline-spec) |
| `gowrishankar-infra/velaris-kit` | [`gowrishankar-infra/sabline-kit`](https://github.com/gowrishankar-infra/sabline-kit) |
| `gowrishankar-infra/velaris-canary` | [`gowrishankar-infra/sabline-canary`](https://github.com/gowrishankar-infra/sabline-canary) |

Each was renamed in place, so GitHub redirects the old URL — the web page,
`git clone`, and `uses: gowrishankar-infra/velaris-lang@<commit>` in a
workflow. A pin by commit keeps naming the same commit. The redirect lasts
only as long as nobody creates a repository at the old name, and nobody
will.

### The site

| Address | Now |
|---|---|
| `velaris-lang.dev/...` | 301 to `sabline.dev/...`, path for path |
| `gowrishankar-infra.github.io/sabline-lang/...` | 301 to `sabline.dev/...` |
| `gowrishankar-infra.github.io/velaris-lang/...` | **404 — this one could not be kept** |
| `sabline.dev` | the site |

`velaris-lang.dev` is kept and will go on redirecting, so an error printed
by 8.3 to 8.5 still leads a reader to the card.

**The one address the rename broke.** A GitHub Pages site is served at
`<owner>.github.io/<repo>`, so renaming the repository moved it:
`gowrishankar-infra.github.io/velaris-lang/...` answers 404, and the
`reference:` line in every error and refusal printed by **8.0 to 8.2.1**
points there. The only way to serve that path again is a repository called
`velaris-lang`, and creating one would end GitHub's redirect from every old
repository URL — `git clone`, every link, and every workflow that says
`uses: gowrishankar-infra/velaris-lang@<commit>`. Those are worth more than
one address, so it was left broken rather than traded for them. A reader
who meets an 8.0-to-8.2.1 error can read the card at
<https://sabline.dev/llms.txt>, and upgrading fixes the line.

This does **not** affect the predicate type named at that address. A
predicate type is a name, not a page: nothing is fetched from it to verify
a Statement, and `sabline verify` reads the name as it always did. Every
attestation and receipt signed by 4.2 to 8.2.1 still verifies.

### The predicate types

An in-toto predicate type is a name, and this project has named its two
types at three addresses. Every Statement ever signed still verifies,
because a reader takes all three as the same type:

| Written by | capability/v1 | receipt/v1 |
|---|---|---|
| 4.2 – 8.2.1 | `https://gowrishankar-infra.github.io/velaris-lang/capability/v1` | `.../receipt/v1` (from 8.1) |
| 8.3 – 8.5 | `https://velaris-lang.dev/capability/v1` | `https://velaris-lang.dev/receipt/v1` |
| 8.6 on | `https://sabline.dev/capability/v1` | `https://sabline.dev/receipt/v1` |

`sabline verify`, `sabline receipts diff`, `sabline replay` and the OPA
policy read all three. A verifier outside Sabline that pins one type name —
cosign's `--type`, the Kyverno policy — takes the name the Statement
actually carries; the Kyverno policy in `policies/` shows how.

`velaris.dev` was never this project's domain. It is registered to someone
else, no release ever wrote a type under it, and a Statement naming one is
refused like any other type Sabline does not define. Neither is velaris.io.

### Security contact

`security@velaris-lang.dev` still reaches the maintainer. New reports should
go to **security@sabline.dev**; SECURITY.md says so.

## What is not renamed

- **`.vel`** stays the file extension. It is name-neutral, and changing it
  would break every program that exists.
- **The eight published advisories** keep their text and their GHSA ids. An
  advisory records what was wrong with a release that was called Velaris,
  and its affected package really is `velaris-lang` on PyPI.
- **The CHANGELOG before 8.6.0** keeps the old name throughout. It is a
  record of what happened.
- **The documentation of 8.3, 8.4 and 8.5** under `/8.3/`, `/8.4/` and
  `/8.5/` is left as those releases published it, at the address they were
  published at. Its links redirect.
- **Git history**, which is why every file was moved with `git mv`.

## How it was done

`scripts/rename.py`, committed, so the diff is reviewable as a set of rules
rather than as 27,000 changed lines. The same script, run with no arguments,
is the drift test: it fails on any occurrence of the old name that the rules
do not account for, and `check_rename.py` runs it in CI beside the cases
that prove every alias in the table above still works.
