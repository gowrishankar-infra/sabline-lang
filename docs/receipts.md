# Receipts

These are two sections of [EMBEDDING.md](../EMBEDDING.md), on a page of their own so that the embedding guide stays inside the size a page of the site may be: what a receipt of one run holds (8.1), and how a receipt is compared with the program's audit and with earlier runs, and a run made again from one (8.3).

## A receipt of what one run did (8.1)

```sh
sabline examples/effects.vel \
    --allow clock,fs:read:report.txt,fs:write:report.txt,io,rand \
    --receipt effects.receipt.json
```

```python
result = sabline.run(source, allow={"io"})
result.receipt               # the same Statement, as a dict
```

An attestation says what a program may do. A receipt says what one run of
it did. It is an in-toto Statement of the predicate type
`https://velaris-lang.dev/receipt/v1`
(sabline-spec section 8.7), whose predicate is `sabline.receipt/1`:

```json
{"_type": "https://in-toto.io/Statement/v1",
 "subject": [{"name": "examples/effects.vel", "digest": {"sha256": "e483..."}}],
 "predicateType": "https://velaris-lang.dev/receipt/v1",
 "predicate": {
   "schema": "sabline.receipt/1",
   "producer": {"name": "sabline-lang", "version": "8.1.0", "uri": "..."},
   "startedAt": "2026-09-14T09:12:03.418Z", "wall_time_ms": 41.7,
   "budget": "clock,fs:read:/work/report.txt,fs:write:/work/report.txt,io,rand",
   "run_parameters": {"seed": null, "freeze_time": null, "timeout": null,
                      "max_memory_mb": null, "max_read_bytes": 67108864,
                      "confinement": "none",
                      "confinement_reason": "a run in the caller's own process is not confined: ...",
                      "confinement_layers": [],
                      "os_policy_sha256": "9f2c..."},
   "effects_used": {"clock": 1, "fs": 2, "io": 4, "rand": 1},
   "refusals": [],
   "declassifications": [],
   "exit": {"status": 0, "outcome": "ok", "code": null},
   "complete": true}}
```

| Field | What it holds |
|---|---|
| `subject` | the program by the sha256 of the text that ran - named as given, or `<source>` - then each file it imported: the subjects `sabline attest` writes for the same bytes, so an attestation and a receipt of one program match by digest |
| `budget` | the budget the run had, in the budget grammar, paths absolute |
| `run_parameters` | `seed` and `freeze_time`; `timeout` and `max_memory_mb`, null when there were none; `max_read_bytes`; and, from 8.4, what the operating system held of the run: `confinement` - `"full"`, `"partial"`, or `"none"` when the budget was the only boundary - `confinement_reason`, `confinement_layers` and `os_policy_sha256` ([docs/confinement.md](confinement.md)). Until 8.4 `confinement` was `"none"` everywhere but under `sabline eval`, where it named a mechanism |
| `effects_used` | each effect and how many operations the budget let through; null when the run was killed before it could say |
| `refusals` | `{"code", "effect", "line", "stopped", "times"}` for each place the budget refused - `stopped` is false for a refused redirect, which the program is told about and may carry on from |
| `grants_used` | `{"grant", "times"}`: what each grant let through, by the grant's own text (8.5; `sabline receipt show` reads it as a page) |
| `declassifications` | `{"reason", "line", "times"}` for each place the program declassified; an hmac call is one, with the reason `hmac signature` and a `key_fingerprint` (8.5) |
| `tool_calls`, `tool_ceiling` | under `--tools`: each call site, and the ceiling (8.5) |
| `exit` | `status`, `outcome` - `ok`, `refused`, `failed`, `did_not_compile`, `timeout` or `out_of_memory` - and the `code` that ended the run |
| `complete` | false when the run was stopped from outside: what is listed happened, and each `times` is at least that |

`run()` and `Pool.run()` always return one. The HTTP door and the MCP
server return one when a request says `"receipt": true`. A run the clock or
the memory cap stopped has one too, marked `complete: false`, holding what
its worker reported before it was killed.

**What is never in a receipt** is a value the program handled: not its
output, input, arguments or environment; not an error message, which can
quote one; not the path, host or module a refused operation named, which
the program may have built from something it declassified; not a
declassified value. A refusal is its code, its effect and its line, and a
declassification is the reason written in the program. **What is in it**,
and is the program's to choose, is everything that is not a value: its exit
status, where it stopped, how often it did something, how long it took. A
program that has declassified a value can choose those from it; do not
grant `declassify` to code whose receipts you will share.

**Signing and verifying** is the attestation's recipe with the receipt's
type:

<!-- illustrative: signs through Sigstore, online -->
```sh
cosign attest-blob --yes --statement effects.receipt.json \
    --bundle effects.receipt.sigstore.json
cosign verify-blob-attestation --bundle effects.receipt.sigstore.json \
    --type https://velaris-lang.dev/receipt/v1 \
    --certificate-identity you@example.com \
    --certificate-oidc-issuer https://github.com/login/oauth \
    examples/effects.vel
```

or sigstore-python's `sign_dsse` and `Verifier.verify_dsse`, as shown for
the attestation; `verify-blob-attestation` fails unless the file named is
the receipt's first subject, by digest. Every release carries
`sabline-receipt-X.Y.Z.intoto.json` for one run of `examples/effects.vel`,
signed both ways and verified in the release workflow before it is attached
([SECURITY.md](../SECURITY.md)).

A signed receipt says its signer ran this Sabline on these bytes, under
this budget, and saw this run. It is no stronger than the machine it ran
on, and it says nothing about any other run.

## A receipt compared, and a run made again (8.3)

<!-- illustrative: needs receipts written by earlier runs -->
```sh
sabline receipts diff run.json --audit task.vel          # against the program's audit
sabline receipts diff run.json --against receipts/       # against earlier runs of the same bytes
sabline replay run.json --max-allow io,fs:read --expect-output run.out
```

`sabline receipts diff` names what a run did that its program's audit
does not say - an effect it used or was refused, a host, path or module its
budget granted that the audit does not name, a declassification the audit
does not record, a count past the audit's bound, bytes other than the
audited ones - and, against earlier receipts of the same bytes, what is new:
a host, a path, a module, a count above the earlier maximum, a first
declassification. A receipt names no path or host a run reached, only what
its budget granted, so that is what is compared. It exits 0 when nothing
differs, 1 when something does, and 2 when it could not compare;
`sabline.receipts-diff/1` is provisional.

`sabline replay` makes the run again from its receipt: each subject is read
from disk under `--root`, held to its digest - a subject that is missing,
different, or named by an absolute path or one that leaves the directory is
refused before anything runs - and copied into a directory of its own, to
which imports are held. The run gets the receipt's budget, no wider than
`--max-allow` (`io` unless raised, since a receipt is text from somewhere
else), its seed, frozen clock, time and memory limits, and eval's profile
when the receipt says it ran under it. The new receipt is compared with the
recorded one and every difference is named. A receipt holds no output or
input: give the input again (`--stdin FILE`, and words after `--`), and the
output with `--expect-output FILE` to have it compared.

A program that calls tools reaches them through Python. `sabline
program.vel --record-responses FILE` records what each `py`, `py_int`,
`py_float` and `py_json` call gave back, in order, and `sabline replay
--responses FILE` gives those back in place of calling Python - after the
budget and the module grants are checked, as for any call. A call that is not
the one recorded in its place stops the run with E616. Handles are not
recorded, and a recording holds values the program handled, so keep it as
you would its output.
