# Security advisory: a program given to the library as text imported from the system temp directory, ahead of the standard library

**Draft for submission through GitHub Security → Report a vulnerability.**
Not published from the repository; the maintainer submits it.

## Summary

`velaris.check`, `velaris.audit` and `velaris.run` take a program as text.
Velaris resolves a program's imports against the file it is in, so a program
given with no `path` was written to a temporary file first, and its imports
were resolved beside that file before the shipped standard library was
looked in.

That file was created in the system temp directory itself - `/tmp` on Linux
and macOS - which every local user can write to. A `std.vel`, `money.vel` or
any other name a program imports, planted there by another user, was
imported in place of the standard library module of that name:

- `velaris.run(source)` ran the planted code, under the budget the caller
  granted, in the caller's process.
- `velaris.audit(source)` and `velaris.check(source)` reported the planted
  module's effects, hosts and promises as the program's.

The same held for `velaris.Pool`, bounded runs (`timeout=`, `max_memory_mb=`)
and anything built on them. This breaks Goal C of SECURITY.md - what runs is
the program that was given, under the budget that was granted - and the
audit's honesty (Goal B).

The command line, which runs a file where it is, and the HTTP door and MCP
server, which write each request into the directory they serve, were not
affected. On Windows the temp directory is the user's own, so another user
cannot plant a file there.

## Affected versions

**2.52 through 8.1.1** (2.52 made Velaris a library). Fixed in **8.2.0**.

## CVSS

`CVSS:3.1/AV:L/AC:L/PR:L/UI:R/S:U/C:H/I:H/A:N` - **base 6.6 (Medium)**.

- AV:L, PR:L - a local account that can write to the shared temp directory.
- UI:R - the victim's code checks, audits or runs a program, given as text,
  that imports a module.
- C:H, I:H - the planted code runs with whatever the caller's budget grants,
  and the audit reports it as the program; availability is not the point.

## Reproduction (against 8.1.1)

`std.vel`, planted in the temp directory:

```
fn first(xs: List of T) -> T for any T {
    return get(xs, 1)
}
```

```python
import velaris
src = 'import "std.vel" as std\nfn main() uses io {\n    print(std.first([7, 9]))\n}\n'
print(velaris.run(src, allow={"io"}).output)
```

With the file in `/tmp` (or `TMPDIR`, `TEMP` and `TMP` naming the directory
that holds it) this prints `9`; without it, `7`. Confirmed on CPython 3.13
against 2.52 and 8.1.1, with the standard library each shipped.

## Fix (8.2.0)

- A program given as text is written into a new directory of its own, made
  with `tempfile.mkdtemp` (mode 0700 on POSIX), and the directory is removed
  when the call returns. Its imports resolve in that empty directory and then
  in the standard library, as for a file anywhere else.
- Nothing else changes: a program given a `path` resolves its imports beside
  that path, as before.

Regression: `check_self_budget.py` G5 plants a `std.vel` in the temp
directory and holds the audit and the run - in this process, on a pool
worker, and bounded - to the unplanted baseline.

## CWE

CWE-427: Uncontrolled Search Path Element

## Credit

Found by the self-budget-influence suite written for 8.2
(`check_self_budget.py`).
