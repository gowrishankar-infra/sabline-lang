---
slug: solana-web3js-backdoor
title: The @solana/web3.js backdoor, 1.95.6 and 1.95.7
date: 2024-12-03
lane: supply-chain
verdict: STOPPED
budget_line: sabline.lock
verified: false
---

## What happened

On 3 December 2024 an account with publish rights to `@solana/web3.js` was
compromised through a spear-phishing email, and two unauthorised versions,
1.95.6 and 1.95.7, were put on npm. The maintainers' advisory records that
the injected code stole private key material and that the risk fell on
applications which handle private keys directly, such as bots. The versions
went up at about 3:20pm UTC; a clean 1.95.8 was published at 8:25pm UTC, and
npm removed 1.95.6 and 1.95.7 entirely at about 12:22am UTC on 4 December.
Code added to five existing key-handling methods, including
`Keypair.fromSecretKey()` and `Keypair.fromSeed()`, captured private key
material and sent it to a server the attacker controlled.

## Sources

- [GHSA-jcxm-7wvp-g6p5](https://github.com/solana-labs/solana-web3.js/security/advisories/GHSA-jcxm-7wvp-g6p5) - the maintainers' own advisory: the compromised publish account, the affected versions, and what the injected code did.
- [web3.js Exploit: Root Cause Analysis](https://www.anza.xyz/blog/web3-js-exploit-root-cause-analysis) - Anza's post-mortem: the window the versions were live, and the exfiltration path.

## The shape, in Sabline

A library you already had was republished with something extra in it, and
the extra thing sent a value you passed in to somewhere you never named.
Sabline vendors a library as source into `lib/` and records its sha256 in
`sabline.lock`, so this shape meets three separate refusals, each of which
is enough on its own.

`sabline deps --verify` compares the bytes on disk against the lockfile and
says `CHANGED`, with both digests. `sabline deps-diff` compares the
reviewed version against the new one and reports what the newer one gained
- here, by name: `GAINED net:attacker.example.net`, with the file and line
of the `post` that reaches it. And the program that uses the library stops
compiling: `sign` now declares `uses net`, `main` declares `uses io`, and a
caller cannot silently inherit an effect its callee gained (E300). A
backdoor that reaches the network cannot hide behind a function signature,
because the signature is what the compiler checks the call against.

## The one line that does the work

    sabline.lock

Not a grant this time but a file: the lockfile `sabline add` writes, and
`sabline deps --verify` reads in CI. It holds the digest of every vendored
library and the Sabline that added it, and `sabline add` refuses to replace
one with different bytes without `--force`.

## What the budget must be for this to hold

The E300 refusal holds under any budget, because it is the compiler and not
the runtime. The other two hold only if the lockfile is committed and
`sabline deps --verify` actually runs - and the comparison is against what
was vendored, so a library that was already backdoored when it was first
added locks the backdoor in. Sabline also has no registry: a library is a
file in the project, not a name resolved over the network, which is why
this entry's shape is a file changing rather than a version being
republished. That difference is the reason the refusals work, and it is
also the reason they say nothing about npm.
