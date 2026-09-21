# Velaris is now Sabline

This project was called Velaris until 8.6.0. The name belongs to an
unrelated company in the same market (velaris.io), so it was given up
rather than contested.

    pip install sabline-lang

This package, `velaris-lang` 8.6.0, is the last release under the old
name. It holds no code: it depends on `sabline-lang`, so installing it
installs Sabline.

**Nothing you have has to change yet.** `sabline-lang` still provides the
`velaris` command, `import velaris`, `velaris.VelarisError`, the
`VELARIS_*` environment variables, a committed `velaris.capabilities`, and
every `velaris.*` document format - each saying once that the name has
changed, and each removed no sooner than 9.0.

Every version of `velaris-lang` published before this one is still on PyPI,
unchanged: a pin to `velaris-lang==8.5.0` resolves to the same file, with
the same digest and the same signature.

- The package: <https://pypi.org/project/sabline-lang/>
- Every address and where it now points: <https://sabline.dev/renamed.html>
- The source: <https://github.com/gowrishankar-infra/sabline-lang>
