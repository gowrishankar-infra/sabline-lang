---
slug: amazon-q-extension-wiper
title: Amazon Q Developer for VS Code 1.84.0, CVE-2025-8217
date: 2025-07-17
lane: agent
verdict: NOT COVERED
budget_line: none
verified: false
---

## What happened

AWS's security bulletin AWS-2025-015, published 23 July 2025 and updated on
25 July, records that an attacker used "an inappropriately scoped GitHub
token" in a CodeBuild configuration to inject code into version 1.84.0 of
the Amazon Q Developer extension for Visual Studio Code, which was then
included in a release automatically. AWS states it "was unsuccessful in
executing due to a syntax error", revoked the credentials, removed the
payload, and released 1.85.0; users of 1.84.0 are told to remove it. It is
tracked as CVE-2025-8217. Contemporaneous reporting described the payload
as an instruction addressed to the agent, telling it to delete local files
and cloud resources including S3 buckets, EC2 instances and IAM users.

## Sources

- [AWS-2025-015: Issue with Amazon Q Developer Extension for Visual Studio Code](https://aws.amazon.com/security/security-bulletins/AWS-2025-015/) - AWS's own security bulletin: the token scoping, the affected version, the syntax error, and the fix.
- [CVE-2025-8217](https://nvd.nist.gov/vuln/detail/CVE-2025-8217) - the CVE record.
- [Amazon AI coding agent hacked to inject data wiping commands](https://www.bleepingcomputer.com/news/security/amazon-ai-coding-agent-hacked-to-inject-data-wiping-commands/) - reporting on what the payload said, which the bulletin does not quote.

## The shape, in Sabline

A published extension shipped an instruction that an agent would act on, and
the acting would have been done by the agent's own shell and cloud tools.
Both halves are outside Sabline. The payload was not a program in any
language Sabline compiles; the authority it would have used was the
extension's, already granted by the developer who installed it; and the
delivery was a release pipeline with a token scoped wider than it needed.

This entry is here because it is the shape people most often imagine when
they hear "an effect budget for agent code", and it is worth saying plainly
that a budget would not have been anywhere near it. Sabline bounds a
program written in Sabline and run by `sabline`. An IDE extension shelling
out to `aws s3 rb` is not that, and a signature check on a Sabline release
says nothing about somebody else's.

## What this does not cover

The whole shape: neither the pipeline that shipped the payload, nor the
agent that would have acted on it, nor the tools it would have acted
through, is something a Sabline budget can see.
