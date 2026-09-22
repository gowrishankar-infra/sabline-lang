---
slug: camoleak-copilot-chat
title: CamoLeak, in GitHub Copilot Chat
date: 2025-10-08
lane: agent
verdict: OUT OF SCOPE
budget_line: none
verified: false
---

## What happened

Omer Mayraz of Legit Security reported a vulnerability in GitHub Copilot
Chat, which he named CamoLeak. Hidden instructions placed in a pull request
description - using GitHub's invisible comment syntax, so a human reviewer
does not see them - were read by Copilot when a user asked it about the pull
request. To get data out past the content security policy, the exploit
pre-generated a set of GitHub Camo image-proxy URLs standing for individual
characters, and had Copilot render the secret it had read one character at a
time as images. Mayraz reports extracting AWS keys and details of
undisclosed vulnerabilities from private repositories. GitHub disabled image
rendering in Copilot Chat on 14 August 2025.

## Sources

- [CamoLeak: Critical GitHub Copilot Vulnerability Leaks Private Source Code](https://www.legitsecurity.com/blog/camoleak-critical-github-copilot-vulnerability-leaks-private-source-code) - the researcher's own write-up: the injection, the Camo encoding, what was extracted, and the fix date.

## Why this is out of scope

Nothing executed. The exfiltration channel was the chat client rendering an
image, one character per URL - the model's own output, not a program's
effect. As with `echoleak-m365-copilot`, a budget has nothing to bound here,
and the honest thing is to say so rather than to record a gap that is not
one.

It earns a place in the list for a second reason: the character-at-a-time
encoding is exactly the pattern Sabline's rule against branching on a
`Secret of Bool` exists to stop (E563, 7.0), where a program reads a
credential out one comparison at a time. That rule applies to a value inside
a Sabline program. It says nothing about a model rendering a string it was
given.
