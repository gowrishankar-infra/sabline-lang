# Security advisory: an import could read any file the process could read, and the error quoted what it found

**Draft for submission through GitHub Security → Report a vulnerability.**
Not published from the repository; the maintainer submits it.

## Summary

A Velaris program imports another file with `import "path"`, and the
compiler reads that file when it compiles the program - before any budget
applies, since the budget governs what a program does when it runs.
THREAT_MODEL.md listed this as not defended, and said such a read "reads
Velaris source, not data". That was not true. Nothing required the imported
path to be a `.vel` file, and when the file was not Velaris source the lexer
or parser error named what it found there: `import "/home/me/.env"` answered
`E100 expected 'fn' but found 'API_KEY'`, and a password file answered with
its first word.

Where the person compiling the program is the person who owns the disk, that
tells them nothing new. It is not so for the three ways Velaris compiles a
program someone else sent:

- **The HTTP door** (`velaris serve`). Anyone holding its token - under its
  default `io` ceiling, with no `fs` grant at all - could send a program
  importing any path the door's user can read, to `/check`, `/audit` or
  `/run`, and read the problem it answered with.
- **The MCP server.** Whatever the MCP client lets the model send could do
  the same through `velaris_check`, `velaris_audit` or `velaris_run`.
- **The library**, used as a platform uses it: `velaris.audit(source)` on a
  customer's text, with the problems returned to the customer - which is
  what `examples/platform` does.

What leaks is limited: the first token of a file, or the first character
the lexer cannot read, with its line, and whether a path exists (a missing
file is a different error). It is still a read of a file outside every
budget, answered to the caller, which is Goal C of SECURITY.md.

## Affected versions

**0.16 through 8.0.0** (imports arrived in 0.16; the HTTP door in 2.54 and
the MCP server before it). Fixed in **8.1.0**.

## CVSS

`CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N` - **base 5.3 (Medium)**, for a
platform that audits a customer's source through the library and returns the
problems, as `examples/platform` does.

Through the HTTP door on its default loopback address, with the token, it is
`CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:L/I:N/A:N` - 3.3 (Low).

## Reproduction (against 8.0.0)

```python
import velaris
src = 'import "/home/me/.env"\nfn main() uses io { print("x") }\n'
print(velaris.check(src).problems)
# [E100] line 1: expected 'fn' but found 'API_KEY'
```

The same source sent to `POST /check` of `velaris serve --max-allow io`, with
the token, answers with the same problem.

## Fix (8.1.0)

- **Everywhere:** an error inside an imported file that is not a `.vel` file
  names the file and says it is not Velaris source; it shows nothing of what
  the file holds. A file that is not UTF-8 is refused the same way.
- **The doors** hold imports to the directory they serve: `--root`, the
  directory they were started in by default. An import must be a `.vel` file
  at or under it - resolved with realpath, so `..` and a symbolic link cannot
  leave it - or a file of the shipped standard library; anything else is
  refused with **E515** before the file is opened, so whether it exists is
  not told either. A program sent as text is compiled as a file in that
  directory, so its relative imports resolve there.
- **The library** takes `import_root=` on `check`, `audit`, `run` and `Pool`,
  with the same rule.

This refuses, on the doors, an import that 8.0.0 accepted: one outside the
directory the door serves. The CHANGELOG says so.

Regression: `check_library.py` sends the door and the MCP server programs
importing a path outside the root, an absolute path, a non-`.vel` file inside
it and a symbolic link out of it, and requires E515 with nothing of the file
in the answer; `check_adversarial.py` keeps the original probe.

## CWE

CWE-209: Generation of Error Message Containing Sensitive Information
CWE-22: Improper Limitation of a Pathname to a Restricted Directory

## Credit

Found during an internal adversarial pass against 8.0.0.
