# Velaris, the programming language, is now called Sabline

<!-- description: Velaris was renamed Sabline in 8.6.0 because the name belongs to an unrelated company. The language, its guarantees and everything written for the old name still work. -->

If you are looking for **Velaris, the programming language for running code
an AI wrote** - effects in signatures, a budget the runtime enforces, the
`velaris` command - you are in the right place. From release 8.6.0 (20
September 2026) it is called **Sabline**. Nothing about the language changed
with the name.

It is not the customer-success company at velaris.io, which is unrelated and
is the reason for the change: the name was theirs first, in the same market,
so it was given up rather than contested.

## The new names

| Was | Is |
|---|---|
| `pip install velaris-lang` | `pip install sabline-lang` |
| the `velaris` command | the `sabline` command |
| `import velaris` | `import sabline` |
| github.com/gowrishankar-infra/velaris-lang | [github.com/gowrishankar-infra/sabline-lang](https://github.com/gowrishankar-infra/sabline-lang) (the old address redirects) |
| velaris-lang.dev | sabline.dev (the old address redirects, page for page) |
| the Velaris VS Code extension | the Sabline extension |

Programs keep the `.vel` extension.

## What you have to change: nothing, in 8.x

Every old name still works through 8.x, each saying once that it has
changed: the `velaris` command, `import velaris`, the `VELARIS_*` environment
variables, a committed `velaris.capabilities`, and `velaris.audit/1` or
`velaris.receipt/1` documents. They go no sooner than 9.0.
[Velaris is now Sabline](renamed.md) lists every one, and every published
address with where it now points.

## Where to start

- [See it refuse, in one command](https://sabline.dev/) -
  `pip install sabline-lang`, then `sabline demo`.
- [The guides](guide-network-access.md), starting from how people describe
  the problem.
- [The changelog](../CHANGELOG.md): releases before 8.6 are recorded under the
  name they had.
