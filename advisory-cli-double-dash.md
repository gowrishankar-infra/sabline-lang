# Security advisory: words after `--` on the command line were read as Velaris's own flags, and `-- --allow all` granted every effect

**Draft for submission through GitHub Security → Report a vulnerability.**
Not published from the repository; the maintainer submits it.

## Summary

`velaris program.vel` runs a program under an effect budget. With no
`--allow`, the budget is io, the console, and every other effect is refused
(5.0). The words after `--` are meant for the program, which reads them with
`args()`.

Every flag read in the command line's `main()` scanned the whole command
line, `--` included, and the first occurrence of a flag won. A word after
`--` that looked like a flag was taken as the operator's:

- `velaris program.vel -- --allow all` granted every effect - files, the
  network, the environment, Python through `ffi` - to a run whose operator
  named no budget and so meant io.
- `-- --receipt x` made the run write a receipt to a file named `x` in the
  working directory, a write the budget did not grant.
- `-- --max-read 99999` raised the read ceiling (E316) the operator relied on
  when they did not set it.
- `-- --deny io` and similar words narrowed the budget, and `args()` received
  `[--]` instead of the words.

A wrapper, service or agent tool that forwards someone else's words to a
Velaris program after `--`, as the convention asks, handed that person the
budget. This breaks Goal C of SECURITY.md - a program cannot do what its
budget does not grant.

`velaris.run`, `velaris.Pool`, bounded runs, the HTTP door and the MCP server
take a program's arguments as a list and were never affected.

## Affected versions

**5.0.0 through 8.1.1.** 5.0.0 made io the budget of a run with no `--allow`;
before it, such a run was granted every effect already, and a word after `--`
could only narrow it (`--allow all` did not exist). `--max-read` arrived in
7.1.2 and `--receipt` in 8.1.0. Fixed in **8.2.0**.

## CVSS

`CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H` - **base 8.1 (High)**.

- AV:N, PR:N, UI:N - the words come from whoever a deployment forwards
  arguments for, commonly over the network.
- AC:H - it needs a deployment that names no `--allow` of its own and puts
  another party's words after `--`.
- C:H, I:H, A:H - `--allow all` includes `ffi`, which is everything Python can
  do.

## Reproduction (against 8.1.1)

`a.vel`:

```
fn main() uses io, env {
    print(format("args: {}", args()))
    let k = env("PATH", "")
    print("env granted")
}
```

- `velaris a.vel` stops with E310: `'env' needs the 'env' effect, which this
  run does not allow (it allows: io)`.
- `velaris a.vel -- --allow all` prints the `--allow all` notice, `args: [--]`
  and `env granted`, and exits 0.

Confirmed on CPython 3.13 against 5.0.0, 7.1.2 and 8.1.1; 4.4.0 answers
`'all' is not an effect`.

## Fix (8.2.0)

- On a run - a file, `velaris run` or `velaris trace` - `--` ends Velaris's
  flags. It is taken off the command line before any flag is read, and every
  word after it goes to `args()` as written: `velaris a.vel -- --allow all`
  runs under io, is refused `env` (E310), and the program's `args()` is
  `[--allow, all]`.
- `mcp-verify` and `mcp-manifest`, whose `--` comes before a server command,
  are unchanged.
- A flag written before `--` is still the operator's, wherever it stands. A
  wrapper that passes another party's words should put them after `--`.

This changes what `args()` holds for a program run with `--`: the `--` itself
is no longer one of them. The CHANGELOG entry for 8.2 says so on its
compatibility: line.

Regression: `check_self_budget.py` B4 and B5 run the reproduction, `--receipt`
and `--max-read` after `--`, and hold the words after `--` to `args()`.

## CWE

CWE-88: Improper Neutralization of Argument Delimiters in a Command
('Argument Injection')

## Credit

Found by the self-budget-influence suite written for 8.2
(`check_self_budget.py`).
