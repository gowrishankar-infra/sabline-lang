# Names next to sabline-lang

A typo of a package's name is where a malicious package is published to be
installed by mistake. This directory records which names near
`sabline-lang` are open to that, and holds the two packages that close the
ones that are.

Checked on 2026-09-20, against each registry's JSON API, after the project
was renamed Velaris -> Sabline (CHANGELOG 8.6.0):

| Name | PyPI | npm |
|---|---|---|
| `sabline` | **free**: `pypi.org/pypi/sabline/json` answers 404 | **free**: `registry.npmjs.org/sabline` answers 404 |
| `sablinelang` | answers 404, and nobody can register it: PyPI refuses a new project whose "ultranormalized" name matches an existing one's (warehouse's `ultranormalize_name`: `.`, `_` and `-` removed, `l` and `i` read as `1`, lower-cased), and it will match sabline-lang's once that is published | answers 404, and nobody can register it: npm refuses a new name that is identical to an existing one once punctuation is removed ([New Package Moniker Rules](https://blog.npmjs.org/post/168978377570/new-package-moniker-rules.html), 2017) |
| `sabline_lang` | the same project as sabline-lang: PyPI normalizes `_`, `-` and `.` to one name (PEP 503) | nobody can register it, by the same npm rule |

**The old names.** `velaris-lang` is published on both registries and stays
where it is; `packaging/farewell/` is its last release. The bare name
`velaris` was never published on either - both answer 404 - so there is
nothing to move, and nothing under it to deprecate. It is left alone: it
names a company (velaris.io), and this project has no business holding a
package name near theirs now that it has given the name up.

So `sabline` is the one name left to hold, on both registries.

**It is not registered yet.** Publishing a new name takes an account on
the registry, and this repository keeps no publishing credential
(RELEASING.md). The packages are ready:

- [`pypi/sabline`](pypi/sabline) - depends on `sabline-lang` and holds no
  code.
- [`npm/sabline`](npm/sabline) - depends on `sabline-lang` and re-exports
  it. It declares no command, since sabline-lang's `sabline` command would
  clash with one of the same name.

Each installs sabline-lang rather than being empty: PEP 541 lists a project
that "has no functionality or is empty" as invalid, and one that installs
the package its name was mistaken for does something.

## Publishing them

**PyPI**, without a token: on pypi.org, under *Publishing*, add a pending
publisher for the project `sabline` - owner `gowrishankar-infra`,
repository `sabline-lang`, workflow `placeholders.yml`, environment
`placeholders` - create that environment in the repository's settings, and
run the workflow once:

    gh workflow run placeholders.yml

**npm**: npm's trusted publishing is set up on a package that already
exists, so the first publish is by hand, as the owner of sabline-lang:

    npm login
    cd packaging/placeholders/npm/sabline
    npm publish --access public

Neither needs publishing again.
