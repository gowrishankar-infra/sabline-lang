---
slug: tj-actions-changed-files
title: tj-actions/changed-files, CVE-2025-30066
date: 2025-03-14
lane: supply-chain
verdict: PARTIAL
budget_line: env
verified: false
---

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

## Sources

- [GHSA-mrrh-fwg8-r2c3 / CVE-2025-30066](https://github.com/advisories/ghsa-mrrh-fwg8-r2c3) - the GitHub advisory record: affected versions, the malicious commit `0e58ed8` the tags were moved to, the disclosure of secrets through action logs, and the fixed version.
- [Supply Chain Compromise of Third-Party tj-actions/changed-files (CVE-2025-30066) and reviewdog/action-setup@v1 (CVE-2025-30154)](https://www.cisa.gov/news-events/alerts/2025/03/18/supply-chain-compromise-third-party-tj-actionschanged-files-cve-2025-30066-and-reviewdogaction) - CISA's alert, 18 March 2025.
- [GitHub Action tj-actions/changed-files supply chain attack](https://www.wiz.io/blog/github-action-tj-actions-changed-files-supply-chain-attack-cve-2025-30066) - Wiz's analysis: the memory scrape, the double-base64 encoding, and the dozens of affected public repositories it found.

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
[Linux confinement row](../../docs/known-open.md) states its limits in full.
