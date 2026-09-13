# Security advisory: a project-local proof cache could make a false `ensures` report "proven"

**Draft for submission through GitHub Security → Report a vulnerability.**
Not published from the repository; the maintainer submits it.

## Summary

Velaris caches proof results on disk so a second `velaris check` need not
re-run the theorem prover. Until 7.1.2 that cache lived in
`./.velaris/proofs.json`, read from the directory the compiler ran in - the
directory that holds the program being checked. A cache entry marked
`"proven": true` was trusted verbatim, without re-running Z3.

Because the cache key is a SHA-256 of public, deterministic inputs (the
compiler version, the function's text and contract, its callees' contracts,
and the record definitions), anyone who can place a `./.velaris/proofs.json`
next to a program - by shipping it inside a project directory or tarball, or
by writing a pre-existing shared `.velaris/` - can forge an entry that makes
a **false** `requires`/`ensures`/`invariant` be reported as **proven** by
`velaris check`, `velaris proofs`, `velaris audit`, `velaris explain` and the
library. Worse, at run time a "proven" pure-integer function is compiled to
native code, which does **not** carry the interpreter's runtime promise
check - so the false promise is also unenforced when the program runs, and
the run finishes with the wrong result and exit code 0.

This defeats the language's core guarantee (SPEC.md §9.2: "proven means
established by Z3 before the program runs") and matches SECURITY.md's
standing challenge #1.

## Affected versions

**2.29 through 7.1.1** (the on-disk proof cache was introduced in 2.29).
Fixed in **7.1.2**.

## CVSS

`CVSS:3.1/AV:L/AC:L/PR:N/UI:R/S:U/C:N/I:H/A:N` — **base 5.4 (Medium)**.

- AV:L — the attacker delivers a file/directory to the victim's filesystem
  (the code they were asked to write), not over a network.
- AC:L / PR:N — the cache key is computable offline from the program text and
  version; no privileges beyond delivering the program.
- UI:R — the victim runs `velaris check`/`audit`/the program on it.
- I:H — the integrity of the "proven" guarantee is fully subverted, and the
  native path drops the runtime check too; C and A are unaffected.

If scored as scope-changed (the guarantee is the control a person uses to
decide whether to run *other* untrusted code — S:C), the base is ~6.1. The
conservative 5.4 is reported.

## Route

- `velaris.py`, `_cache_load()` read `CACHE_FILE = ./.velaris/proofs.json`
  from the working directory.
- `check_proofs()` trusted a hit: `if key in cache: ... if
  remembered.get("proven"): proven_out.add(fn.name)` — Z3 never invoked.
- `proof_key()` = `sha256(VERSION + contract + body + callee contracts +
  records)`; all inputs are public and deterministic.
- `compile_native()` compiles a promise-bearing function to native only when
  it is in `proven`; native code has no equivalent of the interpreter's
  runtime `ensures` check (which lives in `call_function`). So a
  cache-"proven" pure-Int function's promise is unenforced at run time.

## Reproduction (against 7.1.1)

`prog.vel`:

```
fn double(n: Int) -> Int
  ensures result == n + n
{ return n + 1000000 }          // false: not n + n
fn main() uses io { print(to_text(double(5))) }
```

1. Honest run refuses: `velaris check prog.vel` → `E700 ... proven without
   running the program: n = 1000001 gives result = 2000001`.
2. Compute the key with the real function and write the poison:
   `.velaris/proofs.json = { "<proof_key(double)>": {"proven": true,
   "errors": []} }`.
3. With the poison present:
   - `velaris check prog.vel` → `ok - ... 1 with proven promises` (exit 0)
   - `velaris audit prog.vel` → `[proven ] double  always: result == n + n`
   - `velaris prog.vel --allow io` → prints `1000005`, exit 0 — the promise
     `result == n + n` is violated with no error.

Confirmed on CPython 3.10 and 3.13.

## Fix (7.1.2)

The program's directory is never trusted for the cache:

- The proof cache moves to a **per-user** directory
  (`%LOCALAPPDATA%\velaris\proofs` on Windows; `$XDG_CACHE_HOME/velaris/proofs`
  or `~/.cache/velaris/proofs` elsewhere), never `./.velaris/`.
- Each cache file is keyed by, and its header re-verified against, the
  **absolute source path + a SHA-256 of the exact bytes + the compiler
  version**; a header that does not match is rejected, so a transplanted or
  hand-edited entry is re-proved rather than trusted.
- A `./.velaris/` present in a project is ignored; `velaris audit` prints
  `ignored: ./.velaris/`.
- If no per-user cache can be written, the run proceeds with no cache.

A poisoned `./.velaris/proofs.json` is therefore never read, so the first run
on a malicious program refutes the false `ensures` (E700 with the prover, or
the runtime check E601 without it) and caches only that.

Regression: `check_adversarial.py` (the `CACHE-1`/`CACHE-2` cases) poisons a
`./.velaris/` with the real `proof_key` and asserts the program is refused
under check/proofs/audit/explain/run on native and interpreted paths, and
that a tampered per-user entry is rejected.

## Credit

Found during an internal adversarial pass against 7.1.1.
