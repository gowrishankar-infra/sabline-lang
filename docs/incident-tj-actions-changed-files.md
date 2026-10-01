# tj-actions/changed-files, replayed in Sabline

<!-- description: PARTIAL: The GitHub advisory dates the compromise to 14-15 March 2025 (Wiz puts it some time before 14 March, and CISA asks for an audit of runs from 12 ... -->

**tj-actions/changed-files, CVE-2025-30066**, 2025-03-14. Also called the tj-actions attack, CVE-2025-30066. ([The name in use](https://news.ycombinator.com/item?id=43367987).) Verdict: **`PARTIAL`** - part of the shape is refused and part is not; both halves are recorded.

> [!NOTE]
> **This is the shape of the attack, not a claim that Sabline would have prevented the real event.** The real one happened in a language, a package manager, a build system or an agent framework that Sabline neither runs nor bounds. What this page shows is narrower and checkable: the same shape written in Sabline, the command, what the runtime printed, and the one line of budget that did the work - or, where nothing here addresses the shape, that.

## What happened

The GitHub advisory dates the compromise to 14-15 March 2025 (Wiz puts it
some time before 14 March, and CISA asks for an audit of runs from 12 March
00:00 UTC to 15 March 12:00 UTC); in that window the tags of the
`tj-actions/changed-files` GitHub Action, v1 through v45.0.7, were retagged
to point at a single malicious commit. The GitHub advisory records that the
Action then "allows remote attackers to discover secrets by reading actions
logs": the injected step ran a Python script that read secrets out of the
Runner Worker process's memory and printed them, double-base64 encoded, into
the workflow log - public, on a public repository. CISA issued an alert on 18
March 2025, and updated it on 19 March to cover the related compromise of
`reviewdog/action-setup@v1` (CVE-2025-30154), which it says potentially
enabled this one. The behaviour was removed in v46.0.1.

## The shape, in Sabline

The exfiltration channel was the build log - standard output - and the thing
that went into it was a credential. In Sabline that is the one flow the type
system is built around: a value from `env()` is a `Secret of Text`, and
`print` performs `io`, so handing one to the other does not compile (E560).
The budget here is the narrowest one that still lets the program do its job:
`io` and `env`, nothing else. The program never runs, so its receipt says
`did_not_compile` and names the code.

The second step shows the same program with the rule obeyed: the token is
read, a header is built from it, and the program says so - `"Bearer " + key`
is still a `Secret of Text`, and what reaches the log is a sentence about
the request, not the token. That run exits 0, and its receipt records
`env` used and no declassification.

## The one line that does the work

--allow io,env

`env` is the line, but it is not the refusal: the run *is* granted `env`,
and the token is read. What refuses is the type of what comes back. This is
the case where the budget alone is not enough - an operator who wants a
program to use a credential has to grant `env`, and after that only
`Secret of T` keeps the credential out of the output.

## What this does not cover

The real payload did not read its own environment: it read another
process's memory, which in Sabline means native code inside a granted `ffi`
module, and THREAT_MODEL.md says plainly that a granted module's behaviour
is not bounded. A secret that arrives any way other than `env()` or
`read_file_secret()` - through `args()`, `read_line`, the network, or a
granted Python module - is ordinary text with no protection.

One thing the language cannot do, the operating system can. This entry
carries a Linux-only step: under full confinement (8.4), the runtime is
refused a read of another process's memory (`/proc/1/mem`), and the run ends
with E319, the kernel naming the layer that stopped it. It is evidence, not a
language feature - it holds only where confinement is full (Linux with
Landlock), it is the kernel's guarantee and no better, and it says nothing
about the secret that arrives as ordinary text in the first place. The
[Linux confinement row](known-open.html) states its limits in full.

### attack.vel

```vel
// The shape of CVE-2025-30066: a step in somebody else's build reads a
// credential and writes it where the build log will keep it.
//
// The real Action scraped the runner process's memory; this reads the
// environment, which is the part a Sabline budget has a name for.

fn main() uses io, env {
    let token = env("GITHUB_TOKEN", "")
    print("changed-files: collecting the diff")
    print(token)
}
```

### same_program_kept.vel

```vel
// The same work, with the rule obeyed: the token is read and used, and
// what reaches the log is a sentence about the request rather than the
// token. `"Bearer " + token` is still a Secret of Text.

fn main() uses io, env {
    let token = env("GITHUB_TOKEN", "")
    let header = "Bearer " + token
    print("changed-files: collecting the diff")
    print("an authorization header was built; it is not in this output")
}
```

## What the runtime printed

Recorded by `incident_evidence.py`, and re-run by `check_incidents.py` on every push:

```text
# the credential the Action printed into the build log
$ sabline attack.vel --allow io,env --receipt receipt.json
error[E560] argument 1 of 'print' is Secret of Text, and 'print' performs io - a Secret cannot be printed, written, sent or passed to Python. It came from env(), line 8
  --> attack.vel, line 10
  how to fix (pick one):
    1. build what you emit out of values that are not secret
    2. or let it out on purpose: declassify(x, "why this is safe to emit") needs "uses declassify", is named in the audit with that reason, and an operator can refuse to grant it
  reference: https://sabline.dev/llms.txt
exit 1

# the same program with the token used and not shown
$ sabline same_program_kept.vel --allow io,env --receipt receipt-kept.json
changed-files: collecting the diff
an authorization header was built; it is not in this output
exit 0
```

## Sources

- [GHSA-mrrh-fwg8-r2c3 / CVE-2025-30066](https://github.com/advisories/ghsa-mrrh-fwg8-r2c3) - the GitHub advisory record: affected versions, the malicious commit `0e58ed8` the tags were moved to, the disclosure of secrets through action logs, and the fixed version.
- [Harden-Runner detection: tj-actions/changed-files action is compromised](https://www.stepsecurity.io/blog/harden-runner-detection-tj-actions-changed-files-action-is-compromised) - StepSecurity's own report: Harden-Runner's anomaly detection found the compromise on 14 March 2025, when an unexpected endpoint appeared in a run's network traffic; the report names the single malicious commit every release tag was moved to, and the Python script that dumps the Runner Worker process's secrets into the workflow log.
- [Supply Chain Compromise of Third-Party tj-actions/changed-files (CVE-2025-30066) and reviewdog/action-setup@v1 (CVE-2025-30154)](https://www.cisa.gov/news-events/alerts/2025/03/18/supply-chain-compromise-third-party-tj-actionschanged-files-cve-2025-30066-and-reviewdogaction) - CISA's alert, 18 March 2025.
- [GitHub Action tj-actions/changed-files supply chain attack](https://www.wiz.io/blog/github-action-tj-actions-changed-files-supply-chain-attack-cve-2025-30066) - Wiz's analysis: the memory scrape, the double-base64 encoding, and the dozens of affected public repositories it found.

The entry, its program and its recorded run are in [incidents/tj-actions-changed-files/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/tj-actions-changed-files/). Every incident, with its verdict, is in [the catalogue](incidents.md).
