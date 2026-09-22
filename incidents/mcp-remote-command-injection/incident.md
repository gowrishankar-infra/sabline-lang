---
slug: mcp-remote-command-injection
title: mcp-remote, CVE-2025-6514
date: 2025-07-09
lane: agent
verdict: STOPPED
budget_line: ffi:json
verified: false
---

## What happened

JFrog's security research team found an OS command injection in
`mcp-remote`, the npm proxy that lets MCP clients such as Claude Desktop
reach a remote MCP server. It is triggered when the proxy connects to an
untrusted MCP server: the server's OAuth metadata response - specifically
the `authorization_endpoint` URL - reaches an operating-system command
without being sanitised, which lets the server run arbitrary commands on the
machine the proxy is on. It affects versions 0.0.5 through 0.1.15 and is
fixed in 0.1.16; the advisory rates it 9.6.

## Sources

- [OS command injection in mcp-remote when connecting to untrusted MCP servers (JFSA-2025-001290844)](https://research.jfrog.com/vulnerabilities/mcp-remote-command-injection-rce-jfsa-2025-001290844/) - JFrog's own research advisory, which found and reported it.
- [GHSA-6xpm-ggf7-wc3p / CVE-2025-6514](https://github.com/advisories/GHSA-6xpm-ggf7-wc3p) - the advisory record: affected versions, severity, and the fixed release.

## The shape, in Sabline

A field from a server the client does not control reaches a shell. In
Sabline the first half is ordinary - text arrives, from the network or a
file, and is text like any other - and the second half has no builtin. There
is no `exec`, no `shell`, no `system`. The only route from the language to
the operating system is `py`, which needs the `ffi` effect, and a grant that
names modules reaches only the modules it names.

`attack.vel` reads the server's answer - here from a file, so the entry runs
without a network - and hands it to `py("os", "system", ...)`. The run is
given the Python a real MCP proxy would need to parse that answer,
`ffi:json`, and the call is refused with the module named (E311). Nothing
narrower than that grant was needed; the operator did not have to guess that
`os` was the danger, only to say which module the task uses.

## The one line that does the work

    --allow io,fs:read:.,ffi:json

`ffi:json` is the line. `ffi` with no module list is every module, and
THREAT_MODEL.md says so; `ffi:json` is a door to one. The reach check (3.3)
holds a call to the module actually reached along the attribute chain, and
refuses rather than allows where it cannot tell which module that is.

## What the budget must be for this to hold

`--allow all`, plain `ffi`, `ffi:os` or `ffi:subprocess` runs the command.
Sabline does not detect injection, does not sanitise anything, and has no
notion of which text came from a server - a tool result is a `Text` like any
other, which `docs/runner.md` says outright. What it has is that reaching
the operating system is an effect somebody has to grant by name.
