# Names next to velaris-lang

A typo of a package's name is where a malicious package is published to be
installed by mistake. This directory records which names near
`velaris-lang` are open to that, and holds the two packages that close the
ones that are.

Checked on 2026-09-14, against each registry's JSON API:

| Name | PyPI | npm |
|---|---|---|
| `velaris` | **free**: `pypi.org/pypi/velaris/json` answers 404 | **free**: `registry.npmjs.org/velaris` answers 404 |
| `velarislang` | answers 404, and nobody can register it: PyPI refuses a new project whose "ultranormalized" name matches an existing one's (warehouse's `ultranormalize_name`: `.`, `_` and `-` removed, `l` and `i` read as `1`, lower-cased), and it matches velaris-lang's | answers 404, and nobody can register it: npm refuses a new name that is identical to an existing one once punctuation is removed ([New Package Moniker Rules](https://blog.npmjs.org/post/168978377570/new-package-moniker-rules.html), 2017) |
| `velaris_lang` | the same project as velaris-lang: PyPI normalizes `_`, `-` and `.` to one name (PEP 503), and the API answers with velaris-lang | nobody can register it, by the same npm rule |

So `velaris` is the one name left to hold, on both registries.

**It is not registered yet.** Publishing a new name takes an account on
the registry, and this repository keeps no publishing credential
(RELEASING.md). The packages are ready:

- [`pypi/velaris`](pypi/velaris) - depends on `velaris-lang` and holds no
  code.
- [`npm/velaris`](npm/velaris) - depends on `velaris-lang` and re-exports
  it. It declares no command, since velaris-lang's `velaris` command would
  clash with one of the same name.

Each installs velaris-lang rather than being empty: PEP 541 lists a project
that "has no functionality or is empty" as invalid, and one that installs
the package its name was mistaken for does something.

## Publishing them

**PyPI**, without a token: on pypi.org, under *Publishing*, add a pending
publisher for the project `velaris` - owner `gowrishankar-infra`,
repository `velaris-lang`, workflow `placeholders.yml`, environment
`placeholders` - create that environment in the repository's settings, and
run the workflow once:

    gh workflow run placeholders.yml

**npm**: npm's trusted publishing is set up on a package that already
exists, so the first publish is by hand, as the owner of velaris-lang:

    npm login
    cd packaging/placeholders/npm/velaris
    npm publish --access public

Neither needs publishing again.
