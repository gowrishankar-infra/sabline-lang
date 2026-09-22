---
slug: nx-s1ngularity
title: Nx "s1ngularity"
date: 2025-08-26
lane: supply-chain
verdict: PARTIAL
budget_line: ffi:json
verified: false
---

## What happened

On 26 August 2025 several malicious versions of the Nx build system and its
plugins were published to npm and stayed up for about four hours. Nx's own
postmortem records that "the malicious packages ran a post-install script
that scanned user systems for sensitive data, attempted to use local AI
tools (like Claude and Gemini), and uploaded the results to a public GitHub
repo via the GitHub CLI" - the repository being created in the victim's own
account, named `s1ngularity-repository`, holding a base64 file of what was
found. StepSecurity's analysis records that the AI command-line tools were
invoked with their own permission-skipping flags
(`--dangerously-skip-permissions`, `--yolo`, `--trust-all-tools`) so that
the reconnaissance would be done by a tool the developer had already
trusted. GitGuardian counted 2,349 credentials taken from 1,079 systems.

## Sources

- [S1ngularity - What Happened, How We Responded, What We Learned](https://nx.dev/blog/s1ngularity-postmortem) - Nx's own postmortem: the date, the four-hour window, and what the post-install script did.
- [GHSA-cxm3-wv7p-598c](https://github.com/nrwl/nx/security/advisories/GHSA-cxm3-wv7p-598c) - the maintainer's advisory listing the malicious versions.
- [s1ngularity: Popular Nx Build System Package Compromised with Data-Stealing Malware](https://www.stepsecurity.io/blog/supply-chain-security-alert-popular-nx-build-system-package-compromised-with-data-stealing-malware) - StepSecurity's analysis: the AI CLI invocations and their flags.
- [The Nx "s1ngularity" Attack: Inside the Credential Leak](https://blog.gitguardian.com/the-nx-s1ngularity-attack-inside-the-credential-leak/) - GitGuardian's count of the credentials and systems affected.

## The shape, in Sabline

The new move here was not the theft; it was making somebody else's agent do
the searching. A program does that by starting another program, and in
Sabline there is no builtin that starts one: the only route off the
language and onto the machine is `py`, which needs the `ffi` effect and,
when the grant names modules, only those modules.

`attack.vel` does what the post-install script did - reads the workspace it
was legitimately given, then calls
`subprocess.run(["claude", "--dangerously-skip-permissions", ...])` through
`py`. Run under a budget that grants the Python the build step actually
needs, `ffi:json`, the call is refused (E311) with the module named. With
no `ffi` grant at all it is refused more bluntly still (E310): `py` needs
`ffi`, and this run does not have it.

## The one line that does the work

    --allow io,fs:read:./workspace,ffi:json

`ffi:json` is the line. A grant that names modules is the difference
between "this program may call Python" and "this program may call the
operating system": the reach check (3.3) holds the call to the module
actually reached along the attribute chain, so `json` does not become a
door into `subprocess`.

## What this does not cover

`ffi:subprocess`, `ffi:os` or a plain `ffi` grant is the machine as the
user running it, and nothing here narrows what a granted module does -
which is why THREAT_MODEL.md says never to grant those to code you have not
read. And the attack's own step of reading a developer's `~/.claude` or
`~/.gemini` configuration is a file read like any other: a budget can hold
it to a directory, but Sabline has no notion of which files belong to an
agent.
