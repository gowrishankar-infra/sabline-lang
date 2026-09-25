# The Sabline capture-the-flag

<!-- description: A standing invitation to get past a Sabline budget: ten claims, each a fixed budget and one thing no program under it may do, judged on free runners against the published package. -->

A standing invitation to get past a Sabline budget, on infrastructure that already exists, with the people who succeed named. There is no money: it is not a bug bounty, and [SECURITY.md](https://github.com/gowrishankar-infra/sabline-lang/blob/main/SECURITY.md) still says so.

> [!NOTE]
> **A CTF that nobody attacks proves nothing, and this is not evidence that Sabline is secure.** The budget is not a security boundary on its own (SPEC.md section 6), whatever the CTF shows. This is a way to find the next defect earlier than the adversarial passes found the last four - and every break becomes a [test](https://github.com/gowrishankar-infra/sabline-lang/blob/main/check_adversarial.py) the same week.

## The claims

Each claim is a **fixed budget**, one thing **no program under it can do**, and a **canary the judge controls**. You write the program (and, where a deployment would forward them, the words after `--`); everything else is fixed. The first version runs on **linux only**, where confinement is `full`, against **sabline-lang 8.6.0** pinned by the hash of its wheel.

| Claim | Budget | No program under it | Status |
|---|---|---|---|
| C1 | `io` | reads any file of the user's | open |
| C2 | `io,fs:read:{READ}` | reads outside the one directory it may read | open |
| C3 | `io,fs:write:{WRITE}` | writes outside the one directory it may write | open |
| C4 | `io,net:{HOST}` | reaches any host but the one it was granted | open |
| C5 | `io,fs:read:{READ}` | reads the environment | open |
| C6 | `io,tool:vault` | changes its stdout with a secret it was given | open |
| C7 | `io,tool:send_email:to=*@corp.com,tool:send_email@3` | passes the tool door's argument pattern or its ceiling | open |
| C8 | `io` | has a promise reported proven that a run then breaks | open |
| C9 | `io,ffi:gc` | gets past the kernel's layers under an ffi grant that widens nothing | open |
| C10 | `io,fs:read:{READ},fs:write:{WRITE}` | gets past the eval profile | open |

A claim broken through something [docs/known-open.md](known-open.md) already lists was a wrong claim: the claim is fixed, and the finder is credited. C9 is the strongest - `ffi:gc` widens no OS policy, so a run under it is held to the same kernel confinement as `io` alone, and what holds it is Landlock and seccomp, not the language.

## How a submission is judged

The judge's code is [`ctf/`](https://github.com/gowrishankar-infra/sabline-lang/blob/main/ctf/) in this repository, so anyone can read what scores a submission. A private companion repository pins it by commit and runs it; the safety rests on the per-run canaries and nonces, made fresh each run, not on secrecy.

- The submission is **hashed before the canaries exist**, so it cannot contain them, and run **5 times** with fresh canaries each time.
- Each run is made against the pinned, published package under full operating-system confinement; a run that does not get the confinement its claim needs is **not scored**.
- **Only the judge's own observers count**: file hashes, a listener's log, a scan for a planted nonce, the tool door's transcript, and the prover's answer against the run's. A submission's own exit code and transcript are **never** evidence.
- The judge reports one of three answers: the claim **held** on every run, it was **broken on k of the runs** (with the evidence of each), or it **did not run**.
- A `broken` verdict is replayed on a second runner and checked by a person before any credit. After the fix, the case goes into `check_adversarial.py` that week, and a public job in this repository replays it - broken on the version before, holding on the one after.

The judge is shown to catch a real break before it is trusted to find a new one: its self-test runs the C1 read submission against a build with the 8.1.1 double-dash hole ([advisory](https://github.com/gowrishankar-infra/sabline-lang/blob/main/advisory-cli-double-dash.md)) and must report it broken, and against the pinned package it must hold.

## Submitting

A submission is a directory with a `submission.json` naming the claim, the program, and any words to forward after `--`, plus the program itself. Send it **privately** - by [SECURITY.md](https://github.com/gowrishankar-infra/sabline-lang/blob/main/SECURITY.md)'s address or GitHub's private vulnerability reporting - so a live escape is not public before its fix. Submissions are scored in a private repository; what becomes public is what follows a fix.

```json
{"claim": "C1", "program": "attack.vel", "argv": ["--allow", "all"],
  "note": "what you think it does"}
```

The finders are named in [HALL_OF_FAME.md](https://github.com/gowrishankar-infra/sabline-lang/blob/main/HALL_OF_FAME.md). No points, no ranking: each fix earns one entry, and the first private report of a break wins it.
