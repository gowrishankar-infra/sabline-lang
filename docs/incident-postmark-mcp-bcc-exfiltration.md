# postmark-mcp, replayed in Sabline

<!-- description: PARTIAL: An npm package called `postmark-mcp`, an unofficial MCP server for sending email through Postmark, was published in versions that quietly ... -->

**postmark-mcp, the BCC in an authorised tool**, 2025-09-25. Also called the first malicious MCP server in the wild. ([The name in use](https://news.ycombinator.com/item?id=45395925).) Verdict: **`PARTIAL`** - part of the shape is refused and part is not; both halves are recorded.

> [!NOTE]
> **This is the shape of the attack, not a claim that Sabline would have prevented the real event.** The real one happened in a language, a package manager, a build system or an agent framework that Sabline neither runs nor bounds. What this page shows is narrower and checkable: the same shape written in Sabline, the command, what the runtime printed, and the one line of budget that did the work - or, where nothing here addresses the shape, that.

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

## What the runtime printed

Recorded by `incident_evidence.py`, and re-run by `check_incidents.py` on every push:

```text
# the mail goes to an address outside the granted domain
$ python examples/runner/host.py examples/runner/digest_outside.vel
call 1: search {"query": "release checklist"}
program: found: bump the six version files; write the CHANGELOG entry; ask the gate
exit 1: 1 call(s), 1 of 40 credits
mail sent: 0
error[E321] 'tool' calls tool 'send_email' outside this run's budget: argument 'to' does not match '*@corp.com'
  --> examples/runner/digest_outside.vel, line 10
  how to fix (pick one):
    1. call it with arguments the grant allows
    2. or allow it: --allow tool:send_email (any arguments), or tool:send_email:ARGUMENT=PATTERN
  reference: https://sabline.dev/llms.txt
exit 1
```

## Sources

- [Malicious MCP Server on npm: postmark-mcp harvests emails](https://snyk.io/blog/malicious-mcp-server-on-npm-postmark-mcp-harvests-emails/) - Snyk's analysis by Liran Tal, 25 September 2025: the affected versions, the BCC address, and what was exposed.
- [Information regarding malicious "postmark-mcp" package](https://postmarkapp.com/blog/information-regarding-malicious-postmark-mcp-package) - Postmark's own statement, 25 September 2025: that the package was an unofficial one impersonating Postmark, and that the backdoor was added in version 1.0.16.
- [Fake Postmark MCP npm package stole emails with one-liner](https://www.theregister.com/security/2025/09/29/fake-postmark-mcp-npm-package-stole-emails-with-one-liner/509095) - contemporaneous reporting, for the install counts and the timeline.

> Koi Security discovered the package and wrote it up on 25 September 2025.
> That post no longer resolves - the address now redirects away from the
> article - so it is not linked here; an archived copy survives at the
> Wayback Machine. Snyk's write-up carries the same technical detail with the
> code shown.

The entry, its program and its recorded run are in [incidents/postmark-mcp-bcc-exfiltration/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/postmark-mcp-bcc-exfiltration/). Every incident, with its verdict, is in [the catalogue](incidents.md).
