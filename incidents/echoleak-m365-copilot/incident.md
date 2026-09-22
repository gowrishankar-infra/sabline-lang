---
slug: echoleak-m365-copilot
title: EchoLeak, CVE-2025-32711
date: 2025-06-11
lane: agent
verdict: OUT OF SCOPE
budget_line: none
verified: false
---

## What happened

Aim Labs reported a zero-click vulnerability in Microsoft 365 Copilot,
assigned CVE-2025-32711 with a CVSS score of 9.3. An email sent to the
target, worded to pass the prompt-injection classifiers and never opened by
the victim, was retrieved by Copilot's ordinary retrieval-augmented
generation pass when the user later asked an unrelated question; the
injected instructions then caused Copilot to include data from the user's
own context - chat history, OneDrive, SharePoint, Teams - in a request that
left the tenant. The researchers call the underlying pattern an "LLM scope
violation". Microsoft fixed it server-side and states there was no
exploitation in the wild.

## Sources

- [Breaking down 'EchoLeak', the first zero-click AI vulnerability enabling data exfiltration in Microsoft 365 Copilot](https://www.aim.security/lp/aim-labs-echoleak-blogpost) - Aim Labs' own report: the vector, the scope-violation framing, and the disclosure.
- [CVE-2025-32711](https://msrc.microsoft.com/update-guide/vulnerability/CVE-2025-32711) - Microsoft's record.

## Why this is out of scope

No code ran. The model was steered by text it retrieved, and the data left
through the rendering of the assistant's own answer - not through a program,
a tool call a budget could name, or an effect. Sabline bounds what a program
may do; where there is no program there is nothing for it to bound, and
counting this as a gap would make the catalogue's "not covered" column mean
two different things at once.

It is listed rather than omitted because the boundary matters. An injection
that ends in an effect - a file read, a request, a command - is in this
catalogue and gets a verdict. An injection that ends in the model saying
something is not, however serious it is, and this one is serious.
