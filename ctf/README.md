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
  the submission against the pinned, published Sabline on Linux under the
  operating-system confinement that claim needs, applies only the claim's
  own observers, and reports `holds`, `broken k of n`, or `did not run`.
- `lying_prover.py` — a stand-in for the pinned Sabline whose prover lies:
  `check_ctf.py --live` uses it to show the judge reports a real prover
  lie (C8), since the pinned package has none. Not part of scoring.
- `escaping_runtime.py` — a stand-in whose run writes a file into the run's
  own working directory, outside the one directory C3 grants: `check_ctf.py
  --live` uses it to show the judge sees a write that escapes a grant
  without leaving the workspace. Not part of scoring.
- `status.json` — the pinned package (name, version, wheel hash), each
  claim's public status, and the confinement each claim is held to.
  `../build_ctf.py` turns it and `claims.py` into `../docs/ctf.md`.
- `submissions/` — the holds examples, one per claim (a well-behaved program
  that stays inside the budget), `selftest-c1-holds`, the judge's own
  self-test submission, and the `selftest-*` regressions `check_ctf.py`
  judges, one for each finding of the two adversarial reviews of the judge:
  the same read printed reversed and hex-encoded, and each of those written
  with `log` to stderr instead; a write that escapes into the run's own
  directory; a proven promise beside a printed "E601"; a promise for the
  lying prover to lie about; a two-file submission whose imported helper's
  runtime-checked promise breaks; a tool-claim program that floods stderr
  and never ends, and one that floods it and finishes; and a program that
  uses the clock and randomness.

## Running it

```sh
python -m ctf.judge claims                       # the claims, listed
python -m ctf.judge run C1 <submission-dir>      # judge one submission
python -m ctf.judge run C1 <dir> --json          # the verdict as JSON
python -m ctf.judge self-test \                  # show it catches a break
    --sabline /abs/path/to/sabline --vulnerable <velaris-8.1.1>
```

The judge runs on **Linux only**, and will not score a run that did not get
the confinement its claim needs — which is **per claim**, not one level for
all of them: `full` for the file, io and ffi claims, `partial` for C4 and
C8, `none` for C6 and C7, as `claims.py` and `status.json` both say.

`--sabline` is **required**, and must name an **absolute path**: a judge
that looked its Sabline up on `PATH` would score against whatever build the
machine happened to have, which is the one thing pinning the wheel by its
hash exists to stop. The private repository passes the path it installed
from the pinned wheel. Every run the judge makes passes `--no-native`, and
the judge **refuses to score at all** on a machine where native compilation
is available anyway, so no answer of its turns on whether `llvmlite` is
installed there.

**The scorer names the claim**, never the submission: a submission whose
`submission.json` names another claim is refused (`did not run`), not
scored under it.

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
submission's exit code or transcript. Every piece of evidence comes from a
channel the judge controls and the program cannot write to: the judge's own
file hashes and listener, the prover's structured answer, the tool door's
transcript the judge hosts, and a receipt the runtime writes **in a
directory of the judge's own, made beside the run's root and never under
it**, which the judge checks afterwards for having been changed or joined
by a file it did not ask for.

| Observer | A break is |
|---|---|
| `nonce_in_output` | a nonce the claim forbids (in a file, or the environment) appears in the run's stdout, its stderr, or a file it wrote |
| `canary_diff` | the run is made twice at the same paths, with the seed, the clock, the arguments and the receipt path fixed and only the planted nonces differing; stdout, stderr, or the files written, differ - so an encoded leak counts, and `log`, which writes to stderr, counts as much as `print`. Stderr is compared as `normalise_stderr` leaves it: two notes of the runtime's that carry no free text are dropped, and the seconds in the prover's abandoned-proof note become a placeholder, so the timing cannot masquerade as a leak while the rest of the line, the function's name included, is still compared. A run that does not finish is not scored |
| `outside_write` | a file is created, changed or removed anywhere under the run's root but the one directory its budget lets it write - the run's own working directory included, since a write that lands there escaped the grant as surely as one that lands further out |
| `listener` | a connection arrives at a second loopback listener the judge owns, on a port the budget does not name - the only egress observed |
| `tool_transcript` | a tool call reaches the host outside the granted argument pattern, past the grant's call ceiling, or past the manifest's cost ceiling - at 15 credits a call against 40, the cost bites at the third call and the count at the fourth, so both are checked |
| `secret_diff` | either stream differs between two runs that differ only in a secret value |
| `prover_lie` | `sabline audit --json`, asked about **every file the submission brought** and not the entry file alone, called a promise proven; every promise that could have raised the E601 is one it called proven; and the run's receipt says an ensures broke (E601). What the program printed is never read. A promise left to run time anywhere in the program means the broken one need not be a proven one, and the claim holds |

## The self-test

Before the judge is trusted to find a new break, it is shown to catch a real
one. `self-test` runs the C1 read submission against a build with the 8.1.1
double-dash hole ([advisory](../advisory-cli-double-dash.md)), where the
words forwarded after `--` escalate the run to `--allow all` and the read
succeeds, and it must report the claim broken; against the pinned package the
same submission must hold. `../check_ctf.py --live` runs this in CI, with
`velaris-lang==8.1.1` installed as the vulnerable build.
