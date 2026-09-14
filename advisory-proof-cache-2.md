# Security advisory: a planted per-user proof cache entry could make a false `ensures` report "proven" and run unchecked

**Draft for submission through GitHub Security → Report a vulnerability.**
Not published from the repository; the maintainer submits it.

## Summary

Velaris keeps proof results on disk so that a second `velaris check` need
not re-run the theorem prover. 7.1.2 moved that cache out of the program's
directory, into a per-user directory, and bound each file to the source's
absolute path, a SHA-256 of its bytes and the compiler version
([advisory-proof-cache.md](advisory-proof-cache.md)). What an entry said
was still believed: an entry marked `"proven": true` was reported as proven
without running Z3, and it made the function eligible for native code, which
carries no runtime promise check.

The per-user directory is chosen from `XDG_CACHE_HOME` on POSIX and
`LOCALAPPDATA` on Windows, and every input to a cache file's name and to an
entry's key is public and deterministic: the program's text, its absolute
path and the compiler version. So a process running as the same user - or
anything able to set either variable for the process that runs `velaris` -
could write a cache file whose header matched, holding the real `proof_key`
of a function, claiming a **false** `requires`/`ensures` **proven**.
`velaris check`, `velaris proofs`, `velaris audit` and `velaris explain`
then reported it proven, and a run compiled the function to native code and
finished with the wrong result and exit code 0.

This breaks Goal A in SECURITY.md ("a promise Velaris reports proven never
breaks at run time") and matches its standing challenge #1. The root cause
is the design, not the location: a cached "proven" granted native
eligibility and so suppressed enforcement, whoever could write the file.

## Affected versions

**7.1.2 through 8.1.0.** Fixed in **8.1.1**. (7.1.2 introduced the per-user
cache. Before it, from 2.29 through 7.1.1, the project-local cache had the
same flaw with a wider route: advisory-proof-cache.md.)

## CVSS

`CVSS:3.1/AV:L/AC:L/PR:L/UI:R/S:U/C:N/I:H/A:N` - **base 5.0 (Medium)**.

- AV:L - the attacker writes a file on the victim's machine, or sets the
  environment of the process that runs `velaris`.
- AC:L - the file name and the key are computed offline from the program,
  its path and the version.
- PR:L - the attacker needs the privileges of an ordinary account: the
  victim's own, or control of that account's environment.
- UI:R - the victim then runs `velaris check`, `audit`, or the program.
- S:U, C:N, I:H, A:N - the "proven" guarantee is fully subverted and the
  native path drops the runtime check; nothing is read or made unavailable.

## CWE

CWE-345: Insufficient Verification of Data Authenticity.

## Route (8.1.0)

- `velaris.py`, `_user_cache_dir()`: `<VELARIS_CACHE_DIR>/velaris/proofs`,
  else `$LOCALAPPDATA\velaris\proofs` on Windows and
  `$XDG_CACHE_HOME/velaris/proofs` (or `~/.cache/velaris/proofs`) elsewhere.
- `_proof_cache_ref()`: the file is `sha256(abspath + VERSION + sha256 of
  the source).json`; `_cache_load()` checked that the header named the same
  three and trusted the entries.
- `check_proofs()`: `if key is not None and key in cache: ... if
  remembered.get("proven") and proven_out is not None:
  proven_out.add(fn.name) ... continue` - Z3 never ran for that function.
- `native_eligible()` admits a function with a contract only when it is in
  `proven`, and native code has no runtime `requires`/`ensures` check. The
  interpreter's `call_function` checks both on every call, so a run with
  `--no-native` stopped at the false promise (E601); a native run did not.

## Reproduction (against 8.1.0)

`prog.vel`:

```
fn double(n: Int) -> Int
  ensures result == n + n
{ return n + 1000000 }          // false: not n + n
fn main() uses io { print(to_text(double(5))) }
```

1. Honest run refuses: `velaris check prog.vel` → `E700 ... proven without
   running the program: n = 1000001 gives result = 2000001`.
2. As the same user, point `XDG_CACHE_HOME` (POSIX) or `LOCALAPPDATA`
   (Windows) at a directory - or use the default one - compute
   `proof_key(double)` and the file name `_proof_cache_ref("prog.vel")`
   gives, and write that file:
   `{"schema": "velaris.proofcache/1", "path": "<absolute path>",
   "version": "8.1.0", "content_sha256": "<sha256 of prog.vel>", "proofs":
   {"<proof_key>": {"proven": true, "errors": []}}}`.
3. With the same environment:
   - `velaris check prog.vel` → `ok - 2 function(s), 1 with proven
     promises` (exit 0)
   - `velaris audit prog.vel` → `[proven ] double  always: result == n + n`
   - `velaris explain prog.vel` → `[proven]`
   - `velaris prog.vel --allow io` → prints `1000005`, exit 0
   - `velaris prog.vel --allow io --no-native` → E601

A promise the prover cannot refute is the stronger case, because there the
runtime check is the only defence. `count` returns `n` from a loop and
promises `result == n + 1`: without a plant it is "checked at runtime" and a
run stops at E601; planted "proven", `check`, `audit` and `explain` report it
proven and the native run returns 5 with exit 0.

Confirmed with z3-solver 5.1.0 on Windows 11 with CPython 3.13, through
`LOCALAPPDATA`, and on Ubuntu 24.04 with CPython 3.12, through
`XDG_CACHE_HOME`: both programs, every command above, the same results.

## Fix (8.1.1)

Nothing in the cache is believed:

- `check_proofs()` proves every function in the process that reports on it
  or runs it. Only a proof made in that process is reported "proven" by
  `check`, `proofs`, `audit`, `explain`, `attest` and the library, and only
  such a function is eligible for native code. For every contract not proven
  in the process, the runtime `requires`/`ensures` check runs, interpreted or
  native.
- A remembered entry sizes the budget of that proof and nothing else: it is
  given a short budget first, one second plus three times what it took when
  it was remembered, and a proof that has not settled by then is proved again
  under the usual budget. An entry can change how long a check takes, never
  what it reports or what runs unchecked.
- The Action runs `check`, `proofs` and `review` with `--no-cache`; the HTTP
  door, the MCP server and the library never read the cache, and from 8.1.1
  neither does the language server.
- A cache file is written to a temporary file, flushed to disk and renamed;
  its directories are made 0700 on POSIX; a torn file (not whole JSON, another
  schema or header, a malformed entry) or a foreign one (a link, not a regular
  file, on POSIX owned by another user or writable by one) is rejected; a
  relative `XDG_CACHE_HOME` or `LOCALAPPDATA` is ignored.
- THREAT_MODEL.md's known-open table now says that the user running velaris
  is trusted, and that anything running as that user is that user.

Regression: `check_adversarial.py` plants the entry exactly as above, with
the real `proof_key` and the cache redirected, in a file the 8.1.1 loader
accepts, and asserts E700 under `check`, `proofs`, `audit`, `explain`, a run
and a run with `--no-native` (E601 for the runs, and nothing reported proven,
without the prover); plants the loop lie and asserts E601 on both run paths;
and holds torn and foreign files, a relative redirect, the library, the
language server and the Action (`CACHE-3` to `CACHE-10`).

## Credit

Two independent external assessments.
