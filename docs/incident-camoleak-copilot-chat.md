# CamoLeak, replayed in Sabline

<!-- description: OUT OF SCOPE: Omer Mayraz of Legit Security reported a vulnerability in GitHub Copilot Chat, which he named CamoLeak. Hidden instructions placed in a pull ... -->

**CamoLeak, in GitHub Copilot Chat**, 2025-10-08. ([The name in use](https://news.ycombinator.com/item?id=45553422).) Verdict: **`OUT OF SCOPE`** - prompt injection where no code ran - listed so the boundary is visible, not counted as a gap.

> [!NOTE]
> **This is the shape of the attack, not a claim that Sabline would have prevented the real event.** The real one happened in a language, a package manager, a build system or an agent framework that Sabline neither runs nor bounds. What this page shows is narrower and checkable: the same shape written in Sabline, the command, what the runtime printed, and the one line of budget that did the work - or, where nothing here addresses the shape, that.

## What happened

Omer Mayraz of Legit Security reported a vulnerability in GitHub Copilot
Chat, which he named CamoLeak. Hidden instructions placed in a pull request
description - using GitHub's invisible comment syntax, so a human reviewer
does not see them - were read by Copilot when a user asked it about the pull
request. To get data out past the content security policy, the exploit
pre-generated a set of GitHub Camo image-proxy URLs standing for individual
characters, and had Copilot render the secret it had read one character at a
time as images. Mayraz reports having Copilot search a victim's codebase for
"AWS_KEY" and exfiltrate the result, and extracting details of undisclosed
vulnerabilities from private repositories. GitHub disabled image rendering in
Copilot Chat on 14 August 2025.

## Sources

- [CamoLeak: Critical GitHub Copilot Vulnerability Leaks Private Source Code](https://www.legitsecurity.com/blog/camoleak-critical-github-copilot-vulnerability-leaks-private-source-code) - the researcher's own write-up: the injection, the Camo encoding, what was extracted, and the fix date.

The entry, its program and its recorded run are in [incidents/camoleak-copilot-chat/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/camoleak-copilot-chat/). Every incident, with its verdict, is in [the catalogue](incidents.md).
