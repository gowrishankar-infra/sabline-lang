# EchoLeak, replayed in Sabline

<!-- description: OUT OF SCOPE: Aim Labs reported a zero-click vulnerability in Microsoft 365 Copilot, assigned CVE-2025-32711 with a CVSS score of 9.3. An email worded to read ... -->

**EchoLeak, CVE-2025-32711**, 2025-06-11. Also called CVE-2025-32711, the zero-click Microsoft 365 Copilot leak. ([The name in use](https://news.ycombinator.com/item?id=44250774).) Verdict: **`OUT OF SCOPE`** - prompt injection where no code ran - listed so the boundary is visible, not counted as a gap.

> [!NOTE]
> **This is the shape of the attack, not a claim that Sabline would have prevented the real event.** The real one happened in a language, a package manager, a build system or an agent framework that Sabline neither runs nor bounds. What this page shows is narrower and checkable: the same shape written in Sabline, the command, what the runtime printed, and the one line of budget that did the work - or, where nothing here addresses the shape, that.

## What happened

Aim Labs reported a zero-click vulnerability in Microsoft 365 Copilot,
assigned CVE-2025-32711 with a CVSS score of 9.3. An email worded to read
as a normal request to the recipient (bypassing Microsoft's XPIA
classifier), needing no action from the victim, was pulled in by Copilot's
retrieval when the user later asked Copilot a question; its hidden
instructions made Copilot put sensitive data from the user's context into
an image link, fetched automatically through a Microsoft Teams URL allowed
by the content security policy, sending the data to the attacker's server.
The researchers call the underlying pattern an "LLM scope violation".
Microsoft fixed it server-side and states there was no exploitation in the
wild.

## Sources

- [CVE-2025-32711](https://msrc.microsoft.com/update-guide/vulnerability/CVE-2025-32711) - Microsoft's advisory and CVE record (Microsoft is the CNA): the CVE id, the CVSS score, the acknowledgement of Aim Labs, the server-side fix, and that there was no exploitation in the wild.
- [EchoLeak: The First Real-World Zero-Click Prompt Injection Exploit in a Production LLM System](https://arxiv.org/abs/2509.10540) - Pavan Reddy and Aditya Sanjay Gujral, arXiv:2509.10540, published at the AAAI Fall Symposium Series 2025: the email phrased as a normal request to the human recipient and so past the XPIA classifier, the ordinary retrieval pass that pulled it into Copilot's context, the reference-style image link the chat UI fetches as it renders, and the Microsoft Teams preview URL allowed by the content security policy. The account above rests on this paper.
- [Breaking down 'EchoLeak', the first zero-click AI vulnerability enabling data exfiltration in Microsoft 365 Copilot](https://www.aim.security/lp/aim-labs-echoleak-blogpost) - Aim Labs' own report, which describes the vector and the scope-violation framing. **The page has not served the article since August 2025** (it answers HTTP 403 now); it is cited as an archived copy, read through the Wayback Machine.

The entry, its program and its recorded run are in [incidents/echoleak-m365-copilot/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/echoleak-m365-copilot/). Every incident, with its verdict, is in [the catalogue](incidents.md).
