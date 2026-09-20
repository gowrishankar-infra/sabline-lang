# Sabline for VS Code

Language support for [Sabline](https://sabline.dev/) —
the language where a function's signature declares its types, its
effects, whether it can fail, and promises that a theorem prover checks
before the program runs.

## What you get

- **Live errors as you type**, from the real compiler — including
  promises proven false, with the exact input that breaks them
- **Proof status above every function**: "promises proven before
  running" or "promises checked while running"
- **Completion** for functions in scope (with their contracts) and
  every builtin (with its effects and whether it can fail)
- **Hover** for any function: signature, effects, requires and ensures
- **Go to definition**, across imported files
- **Rename** a function everywhere it is used
- **An outline** of the file's functions
- **17 snippets**: `fnp` for a function with promises, `check` for
  handling failure, `whileinv` for a loop the prover can follow,
  `record`, `test`, `json`, `py`, and more
- Syntax highlighting, comment toggling, bracket matching

## Requirements

Sabline itself:

```
pip install sabline-lang
sabline doctor
```

If `sabline` is not on your PATH, set `sabline.command` in settings.

## Settings

| Setting | Default | What it does |
|---|---|---|
| `sabline.command` | `sabline` | How to run Sabline |
| `sabline.checkOnSave` | `true` | Check and prove on save |

MIT licensed. Issues and ideas:
[github.com/gowrishankar-infra/sabline-lang](https://github.com/gowrishankar-infra/sabline-lang/issues)
