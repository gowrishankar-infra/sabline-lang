# The organisation ceiling

From 9.0 a machine can carry one file that caps what any budget on it may
grant: the **organisation ceiling**. Whoever administers the machine
installs it; nothing on a command line, in a program, in a library call or
in a request to a door can widen it. A developer's `--allow all` is
bounded by something they did not write.

It generalises what was there per door - `sabline serve --max-allow` and
`sabline mcp --max-allow`, and a tool manifest's own grants - to every
entry point: `sabline run`, `sabline test`, `sabline.run` with limits and
without, a `Pool` and a `PoolRegistry` (and so the HTTP door's and the MCP
server's runs), `sabline eval` and `sabline replay`, in either runtime.

## The file

```json
{"schema": "sabline.ceiling/1",
 "allow": "io,fs:read:/srv/data,net:*.corp.com:443@100",
 "description": "what a run on this machine may be given"}
```

`allow` is a budget, written as `--allow` writes one (SPEC.md 7.1): the
most a run's budget may grant, effect by effect, Python module, path,
host, tool and count. `all` caps nothing. Write paths whole: a relative
one is resolved where the run is. `description` is for the people who read
it. Nothing else may be in it.

It is installed at one place per system:

| System | Where |
|---|---|
| Linux and other POSIX systems | `/etc/sabline/ceiling.json` |
| macOS | `/Library/Application Support/Sabline/ceiling.json` |
| Windows | `Sabline\ceiling.json` in the ProgramData folder, as the system names it - not as an environment variable says |

`SABLINE_CEILING` may name one more file. It is held **as well as** the
system's, never instead of it: a ceiling can only narrow, so a second one
cannot widen the first, and nothing a person sets in their environment can
take the system's away.

## What it does

Before a run is given its budget, the budget must sit wholly inside every
ceiling - each grant, at each level, inside a grant of the ceiling: the
rule `--max-allow` already holds a door's requests to. One that does not
is refused before the program is read:

```text
error[E325] the budget's 'fs' grant goes past the organisation ceiling
/etc/sabline/ceiling.json: it does not grant fs:write:/srv/data (it allows:
fs:read:/srv/data,io,net:*.corp.com:443@100)
  how to fix (pick one):
    1. narrow the budget to fit inside it, as --allow fs:read:/srv/data,io,...
    2. or ask whoever administers this machine to widen
       /etc/sabline/ceiling.json: nothing on the command line or in the
       program can
    3. sabline ceiling shows every ceiling installed here
```

What a run may do is then inside every ceiling and its own budget at once.
Each ceiling is asked the same question of the same budget, so no order of
asking them gives a different answer, and a budget inside all of them runs
exactly as it would with none.

**A ceiling that cannot be read refuses every run** - no file where
`SABLINE_CEILING` points, not UTF-8, not JSON, not a ceiling, a field it
does not hold, an `allow` that is not a budget - with E325 saying what is
wrong with it. A ceiling that cannot be read cannot be held, and the one
thing it must never do is let a run through wider than it was meant to.

## Where it is named

A run refused for a reason found in neither the command line nor the
source is the worst refusal Sabline could give, so the ceiling is named
everywhere a run is accounted for:

- **in the refusal**, E325, with the file, the first grant past it and what
  it allows;
- **in the receipt**: `run_parameters.ceilings` lists every ceiling the run
  was held to - `{"path", "sha256", "allow"}`, the sha256 of the file's
  bytes, `allow` null for one that could not be read - for a run refused
  and for one that ran; a refused run's `refusals` holds E325 with the
  effect it is about ([receipts](receipts.md));
- **in `sabline audit`**, which shows each ceiling, what it allows and any
  effect the program needs that it does not grant;
- **by `sabline ceiling`**, which shows what is installed - where, what it
  allows, its sha256, or why it is broken - without anyone having to find
  the file. `--json` gives the same as a document.

## In both runtimes

The Python package finds the file and holds a run to it first. A run
through sabline-rt (`SABLINE_REFERENCE_RUNTIME=rust`) is handed each
ceiling's text with its request; sabline-rt reads it the same way, holds
the budget to it the same way, words a refusal the same way and names it in
its own receipt. The agreement gate holds the two to each other over a
table of ceilings - covering, past an effect, a path, a direction, a count,
a module, a host and a tool, two of them in either order, `all`, nothing,
and every way a file can fail to be one - and `check_ceiling.py` asks every
entry point above, in both runtimes.
