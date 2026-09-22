---
slug: shai-hulud-npm-worm
title: The Shai-Hulud npm worm
date: 2025-09-14
lane: supply-chain
verdict: PARTIAL
budget_line: fs:read:.
verified: false
---

## What happened

On 14 September 2025 GitHub was notified of Shai-Hulud, described in its own
write-up as "a self-replicating worm that infiltrated the npm ecosystem via
compromised maintainer accounts by injecting malicious post-install scripts
into popular JavaScript packages"; GitHub removed more than 500 compromised
packages from the registry. StepSecurity's analysis of the payload reports
that it "repurposes open-source tools like TruffleHog to scan the filesystem
for high-entropy secrets", read cloud metadata endpoints and AWS Secrets
Manager, and uploaded what it found to a public repository created in the
victim's own GitHub account. It also wrote a workflow file,
`.github/workflows/shai-hulud-workflow.yml`, that exfiltrates repository
secrets with `${{ toJSON(secrets) }}`, and republished itself into other
packages the compromised maintainer owned.

## Sources

- [Our plan for a more secure npm supply chain](https://github.blog/security/supply-chain-security/our-plan-for-a-more-secure-npm-supply-chain/) - GitHub's own post, 22 September 2025: the notification date, the description of the worm, and the 500+ packages removed.
- [Shai-Hulud: Self-Replicating Worm Compromises 500+ NPM Packages](https://www.stepsecurity.io/blog/ctrl-tinycolor-and-40-npm-packages-compromised) - StepSecurity's analysis of the payload: TruffleHog, the cloud metadata and Secrets Manager calls, the injected workflow file, and the self-propagation.

## The shape, in Sabline

Two moves a budget can see. First: find credentials lying in the working
directory and send them out. `attack.vel` reads `.env` and posts it to a
collector. The run is given a *wide* read grant - `fs:read:.`, the whole
working directory - and the attacker's own host is granted too, so nothing
about the budget is narrow except the one rule that matters: a documented
credential location is not covered by a broad grant that merely sits above
it, and a plain `read_file` of one is refused outright (E318), because what
it returns is ordinary text the program could then print or send.

Second: `inject_workflow.vel` writes the workflow file. The run has a write
grant - `fs:write:./dist`, where a build's output belongs - and the write
lands outside it (E313).

## The one line that does the work

    --allow io,fs:read:.,net:webhook.example.net:443

`fs:read:.` is the line. It grants the whole working directory and still
does not reach `.env`, because credential locations are checked before the
ordinary grant rule (`_credential_root` in `sabline/budget.py`, 8.0). The
program has to name the file exactly, and then read it with
`read_file_secret`, which hands back a `Secret of Text` that the compiler
will not let reach `post`.

## What this does not cover

Sabline bounds programs written in Sabline; a post-install script is
JavaScript run by npm, which Sabline neither sees nor runs, and nothing
here would have stopped this worm on a real machine. The propagation step
- publishing new versions of other packages with a stolen token - is not an
effect a budget has a name for at all.
