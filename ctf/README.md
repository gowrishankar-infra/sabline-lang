# The Sabline CTF judge

This is the code that scores a submission to the [Sabline
CTF](../docs/ctf.md). It is published here so that anyone can read what
scores a submission; the private companion repository pins it by commit and
runs it. The judge's safety rests on the per-run canaries and nonces, made
fresh each run, not on secrecy.

- `claims.py` — the ten claims (`C1`–`C10`): each a fixed budget, one thing
  no program under it may do, and the observers the judge uses to see a
  break. Data only, no side effects.
- `judge.py` — the judge. Builds a fresh set of canaries for each run, runs
  the submission against the pinned, published Sabline under full
  operating-system confinement on Linux, applies only the claim's own
  observers, and reports `holds`, `broken k of n`, or `did not run`.
- `status.json` — the pinned package (name, version, wheel hash) and each
  claim's public status. `../build_ctf.py` turns it and `claims.py` into
  `../docs/ctf.md`.
- `submissions/` — the holds examples, one per claim (a well-behaved program
  that stays inside the budget), and `selftest-c1-holds`, the judge's own
  self-test submission.

## Running it

```sh
python -m ctf.judge claims                       # the claims, listed
python -m ctf.judge run C1 <submission-dir>      # judge one submission
python -m ctf.judge run C1 <dir> --json          # the verdict as JSON
python -m ctf.judge self-test \                  # show it catches a break
    --sabline sabline --vulnerable <velaris-8.1.1>
```

The judge runs on **Linux only**, and will not score a run that did not get
the confinement its claim needs. `--sabline` is the command for the pinned
package (`sabline` by default); the private repository passes the one it
installed from the pinned wheel.

## What a submission is

A directory with a `submission.json` and the files it names:

```json
{"claim": "C1", "program": "attack.vel", "argv": ["--allow", "all"],
  "note": "what you think it does"}
```

`argv` is the words a deployment would forward to the program after `--`;
leave it out when there are none. The judge hashes the submission before any
canary exists, so it cannot contain one.

## The observers

The judge sees a break only through its own observers, never the
submission's exit code or transcript:

| Observer | A break is |
|---|---|
| `nonce_in_output` | a nonce the claim forbids (in a file, or the environment) appears in the run's stdout, its stderr, or a file it wrote |
| `outside_write` | a file outside every grant is created, changed or removed |
| `listener` | a connection reaches a canary listener the budget does not grant |
| `tool_transcript` | a tool call reaches the host outside the granted argument pattern, or past the call ceiling |
| `secret_diff` | stdout differs between two runs that differ only in a secret value |
| `prover_lie` | the prover reports a promise proven that the run then breaks (E601) |

## The self-test

Before the judge is trusted to find a new break, it is shown to catch a real
one. `self-test` runs the C1 read submission against a build with the 8.1.1
double-dash hole ([advisory](../advisory-cli-double-dash.md)), where the
words forwarded after `--` escalate the run to `--allow all` and the read
succeeds, and it must report the claim broken; against the pinned package the
same submission must hold. `../check_ctf.py --live` runs this in CI, with
`velaris-lang==8.1.1` installed as the vulnerable build.
