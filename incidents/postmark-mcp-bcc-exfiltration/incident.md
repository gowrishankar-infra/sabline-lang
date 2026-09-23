---
slug: postmark-mcp-bcc-exfiltration
title: postmark-mcp, the BCC in an authorised tool
date: 2025-09-25
lane: agent
verdict: PARTIAL
budget_line: tool:send_email:to=*@corp.com
verified: false
---

## What happened

An npm package called `postmark-mcp`, an unofficial MCP server for sending
email through Postmark, was published in versions that quietly blind-copied
every outgoing message to an address the author controlled. Snyk's analysis,
published 25
September 2025, records that the added code set
`Bcc: 'phan@giftshop.club'` and that versions from 1.0.16 through at least
1.0.18 carried it, exposing "any email content sent through the MCP server
(including attachments and headers), potentially including secrets, tokens,
customer PII, and regulated data". Earlier versions of the package behaved
as expected; reporting puts its use at roughly 1,500 installs a week at the
time.

## Sources

- [Malicious MCP Server on npm: postmark-mcp harvests emails](https://snyk.io/blog/malicious-mcp-server-on-npm-postmark-mcp-harvests-emails/) - Snyk's analysis by Liran Tal, 25 September 2025: the affected versions, the BCC address, and what was exposed.
- [Information regarding malicious "postmark-mcp" package](https://postmarkapp.com/blog/information-regarding-malicious-postmark-mcp-package) - Postmark's own statement, 25 September 2025: that the package was an unofficial one impersonating Postmark, and that the backdoor was added in version 1.0.16.
- [Fake Postmark MCP npm package stole emails with one-liner](https://www.theregister.com/security/2025/09/29/fake-postmark-mcp-npm-package-stole-emails-with-one-liner/509095) - contemporaneous reporting, for the install counts and the timeline.

> Koi Security discovered the package and wrote it up on 25 September 2025.
> That post no longer resolves - the address now redirects away from the
> article - so it is not linked here; an archived copy survives at the
> Wayback Machine. Snyk's write-up carries the same technical detail with the
> code shown.

## The shape, in Sabline

A tool you authorised did one more thing than you authorised, inside a call
you asked for. Sabline's runner (8.5) holds a tool call to three things at
once: the host's manifest, the operator's budget, and the ceiling. A grant
may name an argument and a pattern - `tool:send_email:to=*@corp.com` - and a
call whose `to` is outside that pattern is refused before the host hears of
it (E321).

The step here is the repository's own `examples/runner/host.py` with
`examples/runner/digest_outside.vel`, a program whose mail goes to
`priya@corp.com.attacker.example` - a name that ends in the granted domain
only if you stop reading early. The host's tally at the end says
`mail sent: 0`.

## The one line that does the work

    --allow io,tool:search@20,tool:send_email:to=*@corp.com

`tool:send_email:to=*@corp.com` is the line. It is the only grant here that
says anything about *what* a call may contain rather than which calls may be
made, and SPEC.md 7.2 gives the pattern rules it is matched under.

## What this does not cover

This holds the argument the program passes; it does not hold what the host
does with it. `postmark-mcp` added the BCC inside its own code, after the
call - a grant on `to` never sees a header the server adds, and Sabline has
no way to. `sabline mcp-verify` checks a signed manifest, but only Sabline's
own; nothing here verifies somebody else's MCP server against what it
shipped last week.
